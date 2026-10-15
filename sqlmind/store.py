"""SqlMind: SQL-native agent memory with bounded differential consolidation."""

import json
import sqlite3

from . import consolidate as C
from .schema import SCHEMA
from .trigrams import trigrams

DEFAULT_K = 500       # consolidation window (steps)
DEFAULT_TAU = 0.3     # novelty threshold
DEFAULT_MF = 2000     # hard cap: core facts
DEFAULT_MD = 200      # hard cap: digests


class SqlMind:
    """Agent episodic/semantic memory as plain SQL tables.

    Parameters
    ----------
    path : sqlite file path, or ":memory:"
    k : consolidate every k steps
    tau : novelty threshold in [0, 1]; memories with novelty < tau merge
    max_facts / max_digests : hard caps giving the bounded-growth guarantee
    """

    def __init__(self, path=":memory:", k=DEFAULT_K, tau=DEFAULT_TAU,
                 max_facts=DEFAULT_MF, max_digests=DEFAULT_MD):
        self.path = path
        self.k = k
        self.tau = tau
        self.max_facts = max_facts
        self.max_digests = max_digests
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self.con.execute("PRAGMA journal_mode=WAL")
        self._step = 0
        self._since_commit = 0
        row = self.con.execute("SELECT value FROM meta WHERE key='step'").fetchone()
        if row:
            self._step = int(row["value"])

    # -- writes ---------------------------------------------------------
    def _bump(self):
        self._step += 1
        self.con.execute(
            "INSERT INTO meta(key, value) VALUES('step', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(self._step),),
        )
        return self._step

    def _add_memory(self, kind, text, confidence, agent_id):
        step = self._bump()
        tgs = trigrams(text)
        cur = self.con.execute(
            "INSERT INTO memories(kind, step, agent_id, text, confidence,"
            " valid_from, valid_to, tier, n_tri) VALUES(?,?,?,?,?,?,NULL,'hot',?)",
            (kind, step, agent_id, text, confidence, step, len(tgs)),
        )
        mid = cur.lastrowid
        self.con.executemany(
            "INSERT INTO memory_trigrams(memory_id, trigram) VALUES(?, ?)",
            [(mid, t) for t in tgs],
        )
        # Batched commits: the same connection sees uncommitted writes, so
        # recall/as_of stay fresh; fsync cost amortizes over 100 steps.
        self._since_commit += 1
        if self._since_commit >= 100:
            self.con.commit()
            self._since_commit = 0
        if self._step % self.k == 0:
            self.consolidate()
        return mid, step

    def record_episode(self, observation, action, reward=0.0, agent_id="agent"):
        """Record one agent step. Returns (memory_id, step)."""
        text = f"obs: {observation} | act: {action} | reward: {reward}"
        return self._add_memory("episode", text, 1.0, agent_id)

    def add_fact(self, subject, predicate, obj, confidence=1.0, agent_id="agent"):
        """Record one semantic fact. Returns (memory_id, step)."""
        text = f"{subject} {predicate} {obj}"
        return self._add_memory("fact", text, confidence, agent_id)

    # -- consolidation (pure-SQL scoring) --------------------------------
    def novelty_scores(self):
        """Pure-SQL novelty scores over all live memories: [(id, novelty, nearest_id)]."""
        rows = self.con.execute(C.NOVELTY_SQL).fetchall()
        return [(r["id"], r["novelty"], r["nearest_id"]) for r in rows]

    def _live_survivor(self, mid):
        """Follow superseded_by chain to the live survivor (None if dead end)."""
        seen = set()
        while mid and mid not in seen:
            seen.add(mid)
            r = self.con.execute(
                "SELECT valid_to, superseded_by FROM memories WHERE id=?",
                (mid,)).fetchone()
            if not r or r["valid_to"] is None:
                return mid
            mid = r["superseded_by"]
        return None

    def consolidate(self):
        """One differential-consolidation pass. Returns stats dict."""
        stats = {"merged_facts": 0, "digested_episodes": 0,
                 "capped_facts": 0, "capped_digests": 0}
        now = self._step
        # 1. score ALL live memories (pure SQL); low novelty => redundant
        scored = self.novelty_scores()
        by_id = {}
        kinds = {}
        for i, n, nb in scored:
            by_id[i] = (n, nb)
        low = [(i, n, nb) for i, n, nb in scored if n < self.tau and nb]
        # newest first so merge targets are usually still live
        low.sort(key=lambda t: self.con.execute(
            "SELECT step FROM memories WHERE id=?", (t[0],)).fetchone()[0],
            reverse=True)
        # 2a. redundant facts -> supersede into nearest live neighbor
        for i, n, nb in low:
            kind = self.con.execute(
                "SELECT kind FROM memories WHERE id=?", (i,)).fetchone()["kind"]
            if kind != "fact":
                continue
            live_nb = self._live_survivor(nb)
            if live_nb is None or live_nb == i:
                continue
            self.con.execute(
                "UPDATE memories SET valid_to=?, tier='merged',"
                " superseded_by=?, novelty=? WHERE id=? AND valid_to IS NULL",
                (now, live_nb, n, i),
            )
            stats["merged_facts"] += 1
        # 2b. redundant episodes -> extractive digest (no LLM)
        ep_ids = []
        for i, n, nb in low:
            r = self.con.execute(
                "SELECT kind FROM memories WHERE id=? AND valid_to IS NULL",
                (i,)).fetchone()
            if r and r["kind"] == "episode":
                ep_ids.append(i)
        if ep_ids:
            q = C.DIGEST_SQL.format(ids=",".join("?" * len(ep_ids)))
            summary = self.con.execute(q, ep_ids).fetchone()[0] or ""
            lo = self.con.execute(
                "SELECT MIN(step), MAX(step) FROM memories WHERE id IN (%s)"
                % ",".join("?" * len(ep_ids)), ep_ids).fetchone()
            self.con.execute(
                "INSERT INTO digests(from_step, to_step, summary, n_merged,"
                " created_step, valid_to) VALUES(?,?,?,?,?,NULL)",
                (lo[0], lo[1], summary[:2000], len(ep_ids), now),
            )
            self.con.execute(
                "UPDATE memories SET valid_to=?, tier='merged' WHERE id IN (%s)"
                % ",".join("?" * len(ep_ids)), (now, *ep_ids))
            self.con.execute(
                "DELETE FROM memory_trigrams WHERE memory_id IN (%s)"
                % ",".join("?" * len(ep_ids)), ep_ids)
            stats["digested_episodes"] = len(ep_ids)
        # 2c. survivors graduate hot -> core
        self.con.execute("UPDATE memories SET tier='core' WHERE tier='hot'"
                         " AND valid_to IS NULL")
        # 3. hard caps (bounded growth)
        stats["capped_facts"] = self._enforce_cap(
            "memories", "tier='core' AND kind='fact' AND valid_to IS NULL",
            self.max_facts, now, kind="fact")
        stats["capped_digests"] = self._enforce_cap(
            "digests", "valid_to IS NULL", self.max_digests, now, kind="digest")
        self.con.commit()
        return stats

    def _enforce_cap(self, table, where, cap, now, kind):
        n = self.con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
        if n <= cap:
            return 0
        over = n - cap
        if kind == "fact":
            # supersede lowest-novelty core facts beyond the cap
            scored = self.novelty_scores()
            scored.sort(key=lambda t: (t[1] is None, t[1] or 0.0))
            victims = [i for i, _, _ in scored[:over]]
            for i in victims:
                nb = self.con.execute(
                    "SELECT id FROM memories WHERE tier='core' AND kind='fact'"
                    " AND valid_to IS NULL AND id != ?"
                    " ORDER BY step DESC LIMIT 1", (i,)).fetchone()
                self.con.execute(
                    "UPDATE memories SET valid_to=?, tier='merged',"
                    " superseded_by=? WHERE id=?",
                    (now, nb["id"] if nb else None, i))
            return len(victims)
        # digests: merge oldest into one row
        rows = self.con.execute(
            f"SELECT id, summary FROM {table} WHERE {where}"
            " ORDER BY created_step ASC LIMIT ?", (over + 1,)).fetchall()
        merged = " | ".join(r["summary"] for r in rows)[:2000]
        self.con.execute(
            "INSERT INTO digests(from_step, to_step, summary, n_merged,"
            " created_step, valid_to) VALUES(0, ?, ?, ?, ?, NULL)",
            (now, merged, sum(1 for _ in rows), now))
        ids = [r["id"] for r in rows]
        self.con.execute(
            f"UPDATE {table} SET valid_to=? WHERE id IN"
            f" ({','.join('?' * len(ids))})", (now, *ids))
        return over

    # -- reads ----------------------------------------------------------
    def recall(self, query, k=10, kind=None):
        """Trigram-Jaccard recall over live memories. Returns [row]."""
        qts = sorted(trigrams(query))
        if not qts:
            return []
        rows = self.con.execute(C.RECALL_SQL, {
            "qtrigrams": json.dumps(qts), "qn": len(qts), "k": k,
        }).fetchall()
        out = [dict(r) for r in rows]
        if kind:
            out = [r for r in out if r["kind"] == kind]
        return out[:k]

    def as_of(self, step):
        """Time-travel: every memory/fact live at agent step `step`."""
        rows = self.con.execute(
            "SELECT id, kind, step, text, confidence, tier, superseded_by"
            " FROM memories WHERE valid_from <= ?"
            " AND (valid_to IS NULL OR valid_to > ?) ORDER BY step",
            (step, step)).fetchall()
        return [dict(r) for r in rows]

    def belief_at(self, step, kind="fact"):
        """Facts the agent held at step `step` (the debugging superpower)."""
        return [r for r in self.as_of(step) if r["kind"] == kind]

    def live_counts(self):
        rows = self.con.execute(C.COUNT_SQL).fetchall()
        return {r["tier"]: r[1] for r in rows}

    def total_live(self):
        return sum(self.live_counts().values())

    # -- LangGraph interop ----------------------------------------------
    def as_langgraph_node(self, name="sqlmind"):
        """Return a LangGraph node function: (state) -> state.

        Drop into any graph: workflow.add_node("memory", mind.as_langgraph_node())
        The node records the state's observation/action and injects top-k recall.
        """
        def node(state: dict) -> dict:
            obs = state.get("observation", "")
            act = state.get("action", "")
            if obs or act:
                self.record_episode(obs, act, state.get("reward", 0.0))
            hits = self.recall(obs or act, k=5) if (obs or act) else []
            return {"memory_hits": [
                {"text": h["text"], "score": round(h["score"], 4)}
                for h in hits]}
        node.__name__ = name
        return node

    def close(self):
        self.con.commit()
        self.con.close()
