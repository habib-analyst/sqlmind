# sqlmind

**Your agent's memory is a SQL database now.** Episodic + semantic memory as plain SQLite tables, with *differential consolidation* — pure-SQL novelty scoring that merges redundant memories and guarantees bounded table growth — plus time-travel queries ("what did the agent believe at step N?").

No vector DB. No LLM in the consolidation loop. No black-box memory API.

## The idea in 30 seconds

Every K steps, one pure-SQL pass scores each memory's novelty:

```sql
novelty(m) = 1 - max trigram-Jaccard(m, n)   -- over all newer live memories n
```

Memories below threshold τ merge into their nearest neighbor (facts) or roll into an extractive digest (episodes). Hard caps on each tier give the bound:

```
|hot| <= K  +  |core facts| <= M_f  +  |digests| <= M_d     (independent of run length)
```

The novelty scoring decides *which* memories survive (quality); the caps give the hard bound (quantity). Time-travel falls out of the temporal columns for free.

## Quickstart

```bash
pip install sqlmind   # (or: pip install -e .)
python examples/quickstart.py
```

```python
from sqlmind import SqlMind

m = SqlMind(k=500, tau=0.3)          # consolidate every 500 steps
m.record_episode("checked room 3", "scan", reward=0.1)
m.add_fact("vault", "contains", "the amethyst key", confidence=0.95)

m.recall("where is the amethyst key", k=5)   # trigram-Jaccard, pure SQL
m.belief_at(100)                             # facts live at step 100
m.as_of(250)                                 # everything live at step 250
```

Drop into LangGraph:

```python
workflow.add_node("memory", m.as_langgraph_node())
```

## Measured results (CPU-only, SQLite)

| Experiment | Result |
|---|---|
| E1 bounded growth (10k steps) | live table plateaus at ~12 rows vs 10,011 naive (834x smaller); bound holds |
| E2 recall quality (40 needles) | recall@10 = 1.000 after consolidation (1.000 baseline); 81 rows vs 3,040 |
| E3 time-travel debugging | 3/3 failure traces pinpointed to the exact step |
| E4 per-step overhead | mean 1.1ms, p95 2.0ms on SQLite (< 5ms budget); real LangGraph node tested |

## Honest limitations

- Similarity is trigram-Jaccard, not embeddings: catches lexical redundancy, misses paraphrase-level duplication. Embedding cosine is future work.
- The analytic bound (K + M_f + M_d) is a loose worst-case guarantee; the effective plateau (~12 rows here) comes from τ-separated packing of the workload, which we report empirically.
- Consolidation is O(n²) in live memories per pass — fine as a background batch job (15s per 500-step pass here), not per-step.
- Long natural-language queries can make recall slower (common-trigram fan-out); short agent-style queries stay <1ms.
- Digests are extractive (first sentences), not abstractive — no LLM, by design.

## Prior art

SQLite agent-memory systems exist (engram-ts, memoryjs, hippo-memory) and some have time-travel. None do pure-SQL differential novelty scoring with a provable bounded-growth guarantee and zero LLM in the consolidation loop. See `KILLGATE.md` and `PAPER.md` §7.

## Layout

```
sqlmind/          # the package (stdlib + sqlite3 only)
tests/            # E1–E4, run with pytest
examples/         # quickstart.py, timetravel_demo.py
PAPER.md          # the consolidation bound + full results
```
