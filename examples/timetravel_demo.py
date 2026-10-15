"""Time-travel debugging demo: find the exact step a false belief entered."""

from sqlmind import SqlMind

m = SqlMind(k=10**9)  # no auto-consolidation: keep full history for the demo

m.record_episode("at entrance", "look around", 0.0)
m.add_fact("door", "is", "locked")            # true belief, step 2
m.record_episode("tried the handle", "push", -1.0)
m.record_episode("a stranger winks", "ignore", 0.0)
m.add_fact("door", "is", "unlocked")          # FALSE belief enters, step 5
m.record_episode("walked straight in", "move", 1.0)
m.record_episode("alarms blare", "freeze", -5.0)

print("The agent failed at step 7. What did it believe, and when did it go wrong?\n")
for step in (4, 5):
    beliefs = [r["text"] for r in m.belief_at(step)]
    print(f"  step {step}: {beliefs}")

print("\nThe false belief 'door is unlocked' entered at step 5.")
print("as_of(4) shows the truth; as_of(5) shows the corruption.")
print("That is the whole debugging story, as a SQL query.")
