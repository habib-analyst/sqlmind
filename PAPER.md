# sqlmind: SQL-native agent memory with bounded differential consolidation

**Habib Ur Rehman** · 2026-10-15 · Project #33 (SQL × agents trilogy #1)

## 1. Problem

Agent memory today is a black-box API. MemGPT/Letta hide state behind
summarization calls; mem0-class systems hide it behind a vector DB and an
LLM extraction loop. Three consequences: (i) nobody can query *why* the
agent believes something without replaying the world; (ii) storage grows
without a published bound; (iii) every framework reimplements memory badly
because there is no droppable substrate.

## 2. Idea

Implement episodic + semantic memory as plain SQL tables, and make
*consolidation* a SQL query. Every K steps, one pure-SQL pass scores each
memory's novelty:

```
novelty(m) = 1 − max trigram-Jaccard(m, n)   over all newer live memories n
```

computed with window functions (`ROW_NUMBER() OVER (PARTITION BY ...)` picks
the nearest neighbor; the max gives novelty). Memories with novelty < τ
merge: facts are superseded into their nearest live neighbor (temporal
`valid_to` set, `superseded_by` pointer kept); episodes roll into an
extractive digest (first sentences, no LLM). Zero LLM calls in the loop;
zero Python loops over memories.

Time-travel is then a `WHERE` clause:

```sql
SELECT * FROM memories
WHERE valid_from <= :n AND (valid_to IS NULL OR valid_to > :n);
```

## 3. The bound

**Theorem (bounded growth, by construction).** Let K be the consolidation
window, M_f the core-fact cap, M_d the digest cap. At all times:

```
|hot| ≤ K,  |core facts| ≤ M_f,  |digests| ≤ M_d
```

so total live rows ≤ K + M_f + M_d, independent of run length.

*Proof.* Hot holds at most K steps' writes by construction (consolidation
runs every K steps and graduates survivors). `consolidate()` supersedes
lowest-novelty core facts whenever |core| > M_f, and merges oldest digests
whenever |digests| > M_d. Both operations strictly decrease the count, so
the caps are invariants. ∎

**On the role of differential scoring.** The caps alone give a bound, but a
bound alone is trivial (FIFO eviction is also bounded). The contribution is
*which* memories survive: greedy newest→oldest τ-separated construction —
each survivor is τ-novel against all newer survivors — so the retained set
is a τ-packing of the workload's memory distribution. The cap is the
worst-case guarantee; the packing is the effective behavior. We report both
(§5, E1).

## 4. Method

Schema: `memories(id, kind, step, agent_id, text, confidence, valid_from,
valid_to, tier, superseded_by, novelty, n_tri)`, `memory_trigrams` (trigram
sets per memory, driving all similarity joins), `digests` (extractive
rollups). Backends: SQLite (zero-dependency; this paper) — Postgres is a
drop-in (same SQL; pg_trgm can replace the trigram table).

Consolidation pass (every K steps):
1. Pure-SQL novelty scoring over all live memories (§2).
2. Facts with novelty < τ → `valid_to=now`, `superseded_by=nearest`.
3. Episodes with novelty < τ → one `digests` row (extractive), rows retired.
4. Survivors graduate `hot → core`; caps enforced (§3).

Recall is trigram-Jaccard top-k, also pure SQL.

## 5. Experiments (CPU-only, SQLite 3.45)

**E1 — bounded growth.** Scripted agent, 10,000 steps, 5×5 room/action
vocabulary (high redundancy) + 6 distinct durable facts re-observed
throughout. K=500, τ=0.3, caps (2000, 200). Measured 2026-10-15.

| steps | 2k | 4k | 6k | 8k | 10k |
|---|---|---|---|---|---|
| sqlmind live rows (mid-window) | — | — | — | — | 19 |
| sqlmind live rows (steady state, post-consolidation) | — | — | — | — | **8** |
| naive append | 2003 | 4005 | 6007 | 8009 | 10011 |

Result: steady-state live table = **8 rows** (5 episode patterns + 3 facts)
vs 10,011 naive (**1,251× smaller**; 1,501× after +2,000 extra steps).
Extended run (+2,000 steps, re-consolidated): 8 → 8, zero growth —
true O(1) plateau. Bound K+M_f+M_d=2700 holds with 337× margin. The
plateau reflects τ-separated packing of the workload; the cap is the
worst-case guarantee, the packing is the effective behavior.

**E2 — recall quality.** 40 planted needle facts among 3,000 filler
episodes; recall@10 for needle queries, consolidated vs unconsolidated.
Measured 2026-10-15.

| | recall@10 | live rows |
|---|---|---|
| unconsolidated baseline | 1.000 | 3,040 |
| sqlmind (consolidated) | 1.000 | 81 |

Result: retention ratio **1.000** (target ≥ 0.95) — 37× compression with
zero recall loss on this workload.

**E3 — time-travel debugging.** Three scripted failure traces (false door
belief, poisoned calculator trust, stale bridge map). For each, `belief_at`
before/after the corruption step; the exact step where the false belief
entered was identified in 3/3 traces via `as_of()` queries.

**E4 — integration latency.** 2,000 steps, record+recall per step on SQLite:
mean **2.47ms**, p95 **4.18ms** (budget <5ms). LangGraph `StateGraph`
integration test with `as_langgraph_node()` passes against the real
langgraph package. Measured 2026-10-15.

## 6. Honest limitations

- Trigram-Jaccard catches lexical redundancy, not paraphrase-level
  duplication; embedding cosine is future work.
- The analytic bound is loose by design (worst-case); effective size is
  workload-dependent (τ-packing) — reported, not hidden.
- Consolidation is O(n²) in live memories per pass (background batch job;
  ~15s per 500-step pass here) — not per-step.
- Long natural-language queries stress recall (common-trigram fan-out);
  short agent-style queries stay <1ms.
- Digests are extractive, never abstractive — a deliberate no-LLM choice.

## 7. Related work

SQLite agent memories exist (engram-ts, memoryjs, chitragupta/smriti,
hippo-memory, octo-patch/engram); engram-ts and memoryjs have time-travel;
MemGPT/mem0 use LLM-driven consolidation with no published bound. None
combine pure-SQL differential novelty scoring with a provable bounded-growth
guarantee and zero LLM in the loop. Full analysis: KILLGATE.md.

## 8. Reproduce

```bash
pip install -e .
python -m pytest tests/ -q        # E1–E4
python examples/quickstart.py
python examples/timetravel_demo.py
```
