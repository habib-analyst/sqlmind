"""E2: recall quality. Needle-in-haystack: plant P distinct facts among redundant
episodes, consolidate, and measure recall@k of the planted facts vs the
unconsolidated baseline. Target: recall@10 >= 0.95 of baseline."""

from sqlmind import SqlMind

P = 40            # planted needles
FILLER_STEPS = 3000
K = 500
TAU = 0.3


def build(consolidate):
    m = SqlMind(k=K if consolidate else 10**9, tau=TAU,
                max_facts=5000, max_digests=500)
    needles = []
    for j in range(P):
        # distinctive facts unlikely to collide with filler trigrams
        subj = f"vault{j:02d}"
        m.add_fact(subj, "contains", f"artifact-{j:03d}-zxq", confidence=0.95)
        needles.append((subj, f"what does {subj} contain"))
    for i in range(FILLER_STEPS):
        m.record_episode(f"patrolling sector {i % 7}", "scan", 0.0)
    return m, needles


def recall_at_k(m, queries, k=10):
    hits = 0
    for subj, q in queries:
        res = m.recall(q, k=k, kind="fact")
        if any(subj in r["text"] for r in res):
            hits += 1
    return hits / len(queries)


def main():
    base, needles = build(consolidate=False)
    rb = recall_at_k(base, needles)
    m, _ = build(consolidate=True)
    rm = recall_at_k(m, needles)
    print(f"baseline recall@10 : {rb:.3f}")
    print(f"consolidated recall@10: {rm:.3f}")
    print(f"live rows: baseline={base.total_live()} consolidated={m.total_live()}")
    ratio = rm / rb if rb else 0
    print(f"retention ratio: {ratio:.3f} (target >= 0.95)")
    assert ratio >= 0.95, f"recall degraded: {ratio:.3f}"
    print("E2 PASS")


if __name__ == "__main__":
    main()

def test_e2():
    main()
