"""sqlmind quickstart: record, consolidate, recall, time-travel. ~2 minutes."""

from sqlmind import SqlMind

m = SqlMind(k=200, tau=0.3)  # consolidate every 200 steps

# 1. record episodes + facts as your agent runs
for i in range(600):
    m.record_episode(f"checked room {i % 4}", "scan", reward=0.1)
m.add_fact("vault", "contains", "the amethyst key", confidence=0.95)
m.add_fact("guard", "patrols", "the north hall", confidence=0.8)

print("live memories:", m.live_counts(), "total:", m.total_live())

# 2. recall: trigram-Jaccard over live memories, pure SQL
for hit in m.recall("where is the amethyst key", k=3):
    print(f"  [{hit['score']:.3f}] {hit['text']}")

# 3. time-travel: what did the agent believe at step 100?
print("beliefs at step 100:", len(m.belief_at(100)))

# 4. force a consolidation pass and watch the bound hold
stats = m.consolidate()
print("consolidation:", stats)
print("live after:", m.total_live())
