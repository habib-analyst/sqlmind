# Kill-gate: sqlmind novelty check (2026-10-15)

**Claim under test:** a pure-SQL agent-memory system with (a) differential
consolidation via window-function novelty scoring, (b) a provable
bounded-growth guarantee, (c) zero LLM in the consolidation loop, and
(d) temporal time-travel queries — does not already exist.

**Verdict: PASS (build).** Prior art exists for each *component*; the
*combination* — especially (a)+(b) — was not found.

## Prior art reviewed

| System | SQL-native | Time-travel | Consolidation | Pure-SQL novelty scoring + bound |
|---|---|---|---|---|
| engram-ts (Ghost-Frame) | SQLite | yes | FSRS decay | no (embeddings + TS engine) |
| memoryjs (danielsimonjr) | SQLite | yes (bitemporal) | "recursive consolidation", entropy filtering | no (TS engine, no published bound) |
| chitragupta/smriti | SQLite (3 DBs) | yes (bi-temporal edges) | "Samskaara" pattern detection | no (pattern rules, no bound) |
| hippo-memory | SQLite | no | biological decay | no |
| engram (octo-patch) | SQLite | no | FSRS decay | no |
| Memory Sentinel (dev.to) | no (JSON file) | no | bounded importance eviction | no (not SQL) |
| MemGPT / Letta | no | no | LLM summarization | no (LLM in the loop) |
| mem0 | no (vector DB) | no | LLM extraction | no |
| LangGraph checkpointing | SQLite/Postgres | yes (state history) | n/a (checkpoints, not memory) | no |

## Differentiation

1. **Novelty scoring is a SQL query**, not application code: one statement with
   window functions scores every memory's novelty = 1 − max trigram-Jaccard
   vs newer memories. memoryjs's "recursive consolidation" and chitragupta's
   "Samskaara" run in TypeScript/Python with no published formalism.
2. **The bound is stated and proved**: |hot| ≤ K, |core| ≤ M_f,
   |digests| ≤ M_d ⇒ total O(1) in run length (PAPER.md §3). No reviewed
   system publishes a bounded-growth guarantee; most grow unboundedly or
   evict by recency/importance heuristics.
3. **Zero LLM in the loop**: consolidation uses trigram statistics and
   extractive digests only. MemGPT/mem0-class systems call an LLM to
   summarize/extract.
4. **Time-travel is a `WHERE` clause**: `valid_from <= n AND (valid_to IS NULL
   OR valid_to > n)`. engram-ts and memoryjs have the feature; sqlmind's
   contribution is pairing it with (1)–(3), which none do.

## Honest limits of the novelty claim

- SQLite-backed agent memory per se is not novel (many systems above).
- Time-travel queries per se are not novel (engram-ts, memoryjs).
- Trigram similarity per se is not novel (pg_trgm, BM25-adjacent).
- The novelty is the *combination*: differential consolidation as pure SQL
  with a provable bound, no LLM, plus time-travel — verified absent above.
