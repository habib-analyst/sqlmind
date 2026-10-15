"""E4: integration latency. Per-step overhead of SqlMind on SQLite must be <5ms,
and the LangGraph node wrapper must run (real langgraph if installed, else a
protocol-compatible stub is exercised and the skip is reported)."""

import statistics
import time

from sqlmind import SqlMind


def main():
    m = SqlMind(k=10**9)  # no consolidation: pure per-step cost
    # warmup (JIT, caches, allocator)
    for i in range(200):
        m.record_episode(f"warm {i}", "act", 0.0)
        m.recall("warm", k=5)
    lat = []
    for i in range(2000):
        t0 = time.perf_counter()
        m.record_episode(f"obs {i % 13}", f"act {i % 7}", 0.1)
        m.recall(f"obs {i % 13}", k=5)
        lat.append((time.perf_counter() - t0) * 1000)
    # drop first 100 (steady state)
    lat = lat[100:]
    mean = statistics.mean(lat)
    p95 = statistics.quantiles(lat, n=100)[94]
    mx = max(lat)
    print(f"per-step record+recall: mean={mean:.2f}ms p95={p95:.2f}ms max={mx:.2f}ms")
    assert p95 < 5.0, f"p95 {p95:.2f}ms exceeds 5ms budget"
    print("E4a PASS: <5ms/step on SQLite")

    # LangGraph interop
    node = m.as_langgraph_node()
    out = node({"observation": "door is locked", "action": "push", "reward": -1.0})
    assert "memory_hits" in out and isinstance(out["memory_hits"], list)
    print(f"node output keys: {list(out)}; hits: {len(out['memory_hits'])}")
    try:
        from langgraph.graph import StateGraph
        from typing import TypedDict

        class S(TypedDict, total=False):
            observation: str
            action: str
            reward: float
            memory_hits: list

        g = StateGraph(S)
        g.add_node("memory", m.as_langgraph_node())
        g.set_entry_point("memory")
        g.set_finish_point("memory")
        app = g.compile()
        res = app.invoke({"observation": "test obs", "action": "test act"})
        assert "memory_hits" in res
        print("E4b PASS: real LangGraph StateGraph integration")
    except ImportError:
        print("E4b SKIP: langgraph not installed; node protocol verified standalone")


if __name__ == "__main__":
    main()

def test_e4():
    main()
