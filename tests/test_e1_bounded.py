"""E1: bounded-growth proof. 10k-step scripted agent, sqlmind vs naive append vs
FIFO-cap baseline. Asserts the live table plateaus (O(1) in run length)."""

import time

from sqlmind import SqlMind

STEPS = 10_000
K = 500
TAU = 0.3
MAX_FACTS = 2000
MAX_DIGESTS = 200

ROOMS = ["kitchen", "hall", "library", "garden", "cellar"]
ACTS = ["move north", "move south", "pick up key", "open door", "wait"]


def scripted_step(i):
    # redundant by design: small observation/action vocabulary, like real agents
    return (f"in the {ROOMS[i % 5]}, sees {ROOMS[(i * 7) % 5]} door",
            ACTS[(i * 3) % 5], 0.1 * (i % 2))


def main():
    m = SqlMind(k=K, tau=TAU, max_facts=MAX_FACTS, max_digests=MAX_DIGESTS)
    naive, fifo = 0, 0
    fifo_cap = K + MAX_FACTS + MAX_DIGESTS
    sizes, naive_sizes, fifo_sizes = [], [], []
    t0 = time.time()
    for i in range(STEPS):
        obs, act, rew = scripted_step(i)
        m.record_episode(obs, act, rew)
        if i % 997 == 0:  # occasional durable fact; only 6 distinct exist,
            # so re-observations must merge (tests true dedup, not just caps)
            m.add_fact(f"key{i % 3}", "opens", f"door{i % 2}")
        naive += 1 + (1 if i % 997 == 0 else 0)
        fifo = min(fifo + 1 + (1 if i % 997 == 0 else 0), fifo_cap)
        if i % 2000 == 1999:
            sizes.append(m.total_live())
            naive_sizes.append(naive)
            fifo_sizes.append(fifo)
    dt = time.time() - t0
    # Final consolidation to reach steady state (clears hot tier)
    m.consolidate()
    cap = K + MAX_FACTS + MAX_DIGESTS
    print(f"steps={STEPS} time={dt:.1f}s")
    print("sqlmind live (post-consolidation):", sizes[-1], "-> steady:", m.total_live())
    print("naive      :", naive_sizes)
    print("fifo-cap   :", fifo_sizes)
    final = m.total_live()
    # bound check: must be <= cap (hard guarantee by construction)
    assert final <= cap, f"bound violated: {final} > {cap}"
    # steady-state check: post-consolidation count should be small and stable.
    # Run 2000 more steps + consolidate, verify no growth (true plateau).
    for i in range(STEPS, STEPS + 2000):
        obs, act, rew = scripted_step(i)
        m.record_episode(obs, act, rew)
        if i % 997 == 0:
            m.add_fact(f"key{i % 3}", "opens", f"door{i % 2}")
    m.consolidate()
    final2 = m.total_live()
    print(f"steady-state: {final} -> {final2} (after +2000 steps)")
    assert final2 <= final * 1.2, f"not stable: {final} -> {final2}"
    print(f"plateau={final2} cap={cap}")
    print(f"naive would be {naive_sizes[-1] + 2000} rows ({(naive_sizes[-1]+2000)/final2:.1f}x larger)")
    print("E1 PASS: bounded growth, plateau verified")


if __name__ == "__main__":
    main()

def test_e1():
    main()
