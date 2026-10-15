"""E3: time-travel debugging. Three scripted failure traces where a false belief
enters at a known step; as_of()/belief_at() must pinpoint the exact step."""

from sqlmind import SqlMind


def trace_false_door():
    m = SqlMind(k=10**9)  # no consolidation: keep full history
    steps = {}
    m.record_episode("at entrance", "look", 0.0); steps["s1"] = m._step
    m.add_fact("door", "is", "locked");           steps["fact_locked"] = m._step
    m.record_episode("tried handle", "push", -1.0)
    m.record_episode("guard nods", "ask", 0.0);   steps["s4"] = m._step
    # BUG: mis-observation writes a false belief at this step
    m.add_fact("door", "is", "unlocked");         steps["false"] = m._step
    m.record_episode("walked through", "move", 1.0)
    m.record_episode("alarm sounds", "freeze", -5.0)
    return m, steps, "false"


def trace_poisoned_tool():
    m = SqlMind(k=10**9)
    steps = {}
    m.add_fact("calculator", "is", "trusted");    steps["t0"] = m._step
    for i in range(3):
        m.record_episode(f"computed {i}+{i}", "calc", 1.0)
    # BUG: tool output hijacked -> false belief recorded here
    m.add_fact("calculator", "is", "compromised"); steps["false"] = m._step
    m.record_episode("used calc for dosage", "calc", -10.0)
    return m, steps, "false"


def trace_stale_map():
    m = SqlMind(k=10**9)
    steps = {}
    m.add_fact("bridge", "is", "open");          steps["t0"] = m._step
    m.record_episode("crossed bridge", "move", 1.0)
    # BUG: stale map tile re-asserts an outdated fact
    m.add_fact("bridge", "is", "open");          steps["dup"] = m._step
    m.add_fact("bridge", "is", "closed");        steps["false"] = m._step
    m.record_episode("turned back", "move", -1.0)
    return m, steps, "false"


def diagnose(m, steps):
    """Find the step where a contradictory/low-confidence belief entered."""
    facts = m.belief_at(m._step)
    # group by (subject, predicate): find predicates with conflicting objects
    seen = {}
    culprit = None
    for f in facts:
        parts = f["text"].split(" ", 2)
        if len(parts) < 3:
            continue
        key = (parts[0], parts[1])
        seen.setdefault(key, []).append(f)
    for key, fs in seen.items():
        objs = {f["text"] for f in fs}
        if len(objs) > 1:
            # contradiction: the false one is the min-confidence latest entry
            fs.sort(key=lambda r: (r["confidence"], -r["step"]))
            culprit = fs[0]
            break
    if culprit is None:
        return None
    # time-travel: when did this exact belief first appear?
    first = min(r["step"] for r in m.as_of(m._step)
                if r["text"] == culprit["text"])
    return first


def main():
    ok = 0
    for name, fn in [("false-door", trace_false_door),
                     ("poisoned-tool", trace_poisoned_tool),
                     ("stale-map", trace_stale_map)]:
        m, steps, _ = fn()
        found = diagnose(m, steps)
        want = steps["false"]
        status = "OK " if found == want else "MISS"
        print(f"{name}: diagnosed step={found} actual={want} [{status}]")
        # show the time-travel evidence
        before = m.belief_at(want - 1)
        after = m.belief_at(want)
        print(f"  beliefs at step {want-1}: {[r['text'][:32] for r in before][:2]}")
        print(f"  beliefs at step {want}:   {[r['text'][:32] for r in after][:2]}")
        ok += (found == want)
    assert ok == 3, f"only {ok}/3 traces diagnosed"
    print("E3 PASS: 3/3 failure traces pinpointed via as_of()")


if __name__ == "__main__":
    main()

def test_e3():
    main()
