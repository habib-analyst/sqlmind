"""Pure-SQL differential consolidation for sqlmind.

Every novelty score, ranking, and merge decision below is a SQL statement —
no Python loop over memories, no LLM anywhere in the consolidation path.

Definitions
-----------
novelty(m) = 1 - max trigram-Jaccard(m, n) over all *newer* live memories n.
A memory with novelty < tau is redundant: it merges into its nearest newer
neighbor (facts: superseded, episodes: rolled into an extractive digest).

Bound (by construction, proved in PAPER.md):
    |hot| <= K  (consolidation window)
    |core facts| <= M_f
    |digests| <= M_d
so total rows <= K + M_f + M_d, independent of run length. The differential
novelty scoring decides *which* memories survive the bound (quality); the
caps give the hard bound (quantity).
"""

# Novelty scores for every live memory (hot + core), in one query.
# Scoring ALL live memories (not just hot) is what makes re-observations
# merge old duplicates: a new fact has nothing newer, but the OLD duplicate
# sees the new fact as newer and merges into it.
NOVELTY_SQL = """
WITH cand AS (
    SELECT id, step FROM memories
    WHERE tier IN ('hot', 'core') AND valid_to IS NULL
),
-- trigram matches first (index-driven), then step-ordering filter.
-- Avoids the cartesian (candidate x newer) pairs CTE.
inter AS (
    SELECT t1.memory_id AS hid, t2.memory_id AS nid, COUNT(*) AS ic
    FROM memory_trigrams t1
    JOIN memory_trigrams t2
      ON t2.trigram = t1.trigram AND t2.memory_id != t1.memory_id
    JOIN memories m1 ON m1.id = t1.memory_id
    JOIN memories m2 ON m2.id = t2.memory_id
    WHERE m1.id IN (SELECT id FROM cand)
      AND m2.valid_to IS NULL
      AND (m2.step > m1.step OR (m2.step = m1.step AND m2.id > m1.id))
    GROUP BY t1.memory_id, t2.memory_id
),
sizes AS (
    SELECT id AS memory_id, n_tri AS n FROM memories
),
sim AS (
    SELECT i.hid, i.nid,
           i.ic * 1.0 / (s1.n + s2.n - i.ic) AS jaccard,
           ROW_NUMBER() OVER (PARTITION BY i.hid ORDER BY i.ic * 1.0 / (s1.n + s2.n - i.ic) DESC) AS rn
    FROM inter i
    JOIN sizes s1 ON s1.memory_id = i.hid
    JOIN sizes s2 ON s2.memory_id = i.nid
)
SELECT c.id,
       1.0 - COALESCE(MAX(s.jaccard), 0.0) AS novelty,
       MAX(CASE WHEN s.rn = 1 THEN s.nid END) AS nearest_id
FROM cand c
LEFT JOIN sim s ON s.hid = c.id
GROUP BY c.id
"""

# Trigram-Jaccard recall: top-k live memories for a query's trigram set.
# Query trigrams bound as JSON; the trigram index drives the join, and each
# memory's trigram count is read from its row (no recount CTE).
RECALL_SQL = """
WITH q(t) AS (
    SELECT value FROM json_each(:qtrigrams)
),
hits AS (
    SELECT t.memory_id AS id, COUNT(*) AS ic
    FROM memory_trigrams t
    JOIN q ON q.t = t.trigram
    GROUP BY t.memory_id
)
SELECT m.id, m.kind, m.text, m.confidence, m.step,
       h.ic * 1.0 / (:qn + m.n_tri - h.ic) AS score
FROM hits h
JOIN memories m ON m.id = h.id AND m.valid_to IS NULL
ORDER BY score DESC, m.confidence DESC
LIMIT :k
"""

# Extractive digest text for a set of episode ids: first sentences joined.
# Pure SQL string aggregation — no LLM summarization.
DIGEST_SQL = """
SELECT group_concat(substr(text, 1, instr(text || '.', '.') - 1), ' | ')
FROM memories WHERE id IN ({ids})
"""

# Live row counts per tier (for the bound check).
COUNT_SQL = """
SELECT tier, COUNT(*) FROM memories WHERE valid_to IS NULL GROUP BY tier
"""
