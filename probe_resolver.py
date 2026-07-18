"""Check resolver leak rate. The gate is immune (it scores the raw query), but
a resolved query containing its own answer still corrupts OT selection.
"""
import sys
sys.path.insert(0, ".")
from test_flow import new_session, ask

RUNS = 6
leaks = 0

for i in range(1, RUNS + 1):
    sid = new_session()
    ask(sid, "what is my name")
    r = ask(sid, "what is my name")

    resolved = r["gate"].get("resolved_query", "")
    leaked = "sabharish" in resolved.lower()
    leaks += leaked

    print(f"  {'LEAK' if leaked else 'ok  '}  {resolved!r}")

print(f"\n{leaks}/{RUNS} leaked")