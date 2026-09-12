#!/usr/bin/env python3
"""Restore each bug a guard claims to catch, and confirm the guard goes red.

    python3 tools/mutate.py tools/mutations.json

Each entry names a file, the exact text to put back, and the tests that are
supposed to notice. The harness restores the original whether the run passes
or fails, so a mutation is never left in the tree — which also means its
evidence lives in the run and never in the history.

A guard nobody has watched fail is a guard nobody has tested — and a
mutation that APPLIES can still be a runtime no-op, so the exit code of the
targeted test is the only evidence that counts. A replacement that changes
nothing is reported as NO-OP rather than as a pass, and one whose old text
is not found is reported as COULD-NOT-APPLY, because both look identical to
a guard that simply did not fire.

Two of the sixteen guards written for this release stayed green on the
first sweep, and both were guarding a property a comment claimed:

- `ROOT_ONLY_IGNORES` — moving `target` and `worktrees` out of the root-only
  set ignored them at every depth, and nothing noticed. `src/target/` is
  somebody's code.
- Sibling admission — the negative test was vacuous, because the module it
  named had no declarations and so was never admitted whatever the rule
  said. Letting ANY directory with declarations vouch for its neighbours
  stayed green through it.
"""
import json, os, subprocess, sys

MUTATIONS = json.load(open(sys.argv[1]))
root = os.getcwd()
results = []

for m in MUTATIONS:
    path = m["file"]
    original = open(path, encoding="utf-8").read()
    if m["old"] not in original:
        results.append((m["name"], "COULD-NOT-APPLY", "old text not found"))
        continue
    mutated = original.replace(m["old"], m["new"], 1)
    if mutated == original:
        results.append((m["name"], "NO-OP", "replacement changed nothing"))
        continue
    open(path, "w", encoding="utf-8").write(mutated)
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest"] + m["tests"],
            cwd=os.path.join(root, "tools"), capture_output=True, text=True)
        went_red = proc.returncode != 0
        # A control entry is a change that must NOT matter. If one goes red
        # the harness is reporting its own noise as a guard biting, and the
        # whole sweep is worthless — a clean result has to be falsifiable.
        if m.get("expect") == "green":
            results.append((m["name"], "control ok" if not went_red else "HARNESS-BROKEN",
                            "" if not went_red else "a no-op change went red"))
        else:
            results.append((m["name"], "bites" if went_red else "WEAK",
                            "" if went_red else "guard stayed GREEN with the bug restored"))
    finally:
        open(path, "w", encoding="utf-8").write(original)

width = max(len(r[0]) for r in results)
weak = 0
for name, verdict, detail in results:
    if verdict not in ("bites", "control ok"):
        weak += 1
    print("  %-*s  %-16s %s" % (width, name, verdict, detail))
controls = sum(1 for r in results if r[1] == "control ok")
print("\n%d mutation(s): %d bite, %d control(s) held, %d need attention" %
      (len(results) - controls, len(results) - weak - controls, controls, weak))
sys.exit(1 if weak else 0)
