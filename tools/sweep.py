#!/usr/bin/env python3
"""Run every self-check at once and write the result up plainly.

The per-change checks answer "did this edit break anything". Nothing asked
"what is the standing state of everything here", so nothing answered it.

THE REPORT IS FOR SOMEBODY WHO HAS NEVER SEEN THIS PROJECT. What was found
comes before what it means, no term appears without a plain phrase first, and
every line says what would fix it. Exit codes and command names go in a
collapsed section at the bottom for anyone who wants them.

A CHECK THAT COULD NOT RUN IS NOT A PASS, and the closing count says so.

    python3 tools/sweep.py

EXIT: 0 always. A report that fails a build is a report somebody turns off.
"""

import datetime
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today().isoformat()


def run(*args):
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr)


# name, plain description of what it checks, command, what fixes it
CHECKS = [
    ("Everything still works",
     "Runs every test in the project.",
     [sys.executable, "-m", "unittest", "discover", "-s", "tools", "-p", "test_*.py"],
     "A test is failing. The name of the failing test says which behavior changed."),
    ("Colors are readable",
     "Checks that text in the report has enough contrast against its background.",
     [sys.executable, "tools/palette.py"],
     "A text and background pair is too close in brightness. Darken or lighten one."),
    ("The word list matches the code",
     "The written list of token families and the one in the code must agree.",
     [sys.executable, "tools/taxonomy.py", "--check"],
     "The two lists have drifted. Make the written one follow the code."),
    ("The writing reads plainly",
     "Checks the main documents for jargon and for words that make claims without evidence.",
     [sys.executable, "tools/check_voice.py", "SKILL.md", "README.md", "TRIGGERS.md"],
     "A flagged phrase is doing work a plain one would do better. Reword it."),
]


def main():
    rows = []
    for name, what, cmd, fix in CHECKS:
        code, out = run(*cmd)
        if code == 2:
            rows.append((name, what, "not-examined", "the check could not start", fix, code, out))
        elif code == 0:
            rows.append((name, what, "verified", "nothing", "—", code, out))
        else:
            rows.append((name, what, "partial", "something was found", fix, code, out))

    # The version and the written history must agree, and this is checked
    # separately because a disagreement is not a failing test — it is a report
    # citing a version nobody can read about.
    code, out = run(sys.executable, "-m", "unittest", "discover", "-s", "tools",
                    "-p", "test_version_and_changelog_agree.py")
    rows.append(("The version matches the written history",
                 "Every released version named in the history must have been tagged.",
                 "verified" if code == 0 else "partial",
                 "nothing" if code == 0 else "the two disagree",
                 "—" if code == 0 else "Tag the released version, or correct the history.",
                 code, out))

    version = run(sys.executable, "tools/version.py")[1].strip() or "unknown"
    verified = sum(1 for r in rows if r[2] == "verified")
    partial = sum(1 for r in rows if r[2] == "partial")
    unexamined = sum(1 for r in rows if r[2] == "not-examined")
    openish = partial + unexamined

    L = []
    L.append("# Project check — %s" % TODAY)
    L.append("")
    L.append("This project grades how healthy a codebase's design tokens are — the named")
    L.append("colors, sizes and spacings a team agrees to use instead of typing values by")
    L.append("hand. This run checks the project itself rather than anybody's codebase.")
    L.append("")
    L.append("Running version **%s**." % version)
    L.append("")
    L.append("## What was found")
    L.append("")
    L.append("**Passed** means checked and nothing wrong. **Needs attention** means something")
    L.append("was found. **Could not check** means it did not run, and those count as open below.")
    L.append("")
    L.append("| Check | What it looks at | Result | What would fix it |")
    L.append("|---|---|---|---|")
    mark = {"verified": "Passed", "partial": "Needs attention", "not-examined": "Could not check"}
    for name, what, state, _found, fix, _c, _o in rows:
        L.append("| %s | %s | %s | %s |" % (name, what, mark[state], fix))
    L.append("")
    L.append("## How close this is to clean")
    L.append("")
    if openish == 0:
        L.append("Everything was checked and everything passed.")
    else:
        L.append("**%d of %d lines are open**, counting the **%d** that could not be checked."
                 % (openish, len(rows), unexamined))
        L.append("")
        for name, _w, state, _f, fix, _c, _o in rows:
            if state != "verified":
                L.append("- **%s** — %s" % (name, fix))
    L.append("")
    L.append("## If you only do one thing")
    L.append("")
    first = next((r for r in rows if r[2] == "not-examined"), None) or next((r for r in rows if r[2] == "partial"), None)
    L.append(first[4] if first else "Nothing needs doing.")
    L.append("")
    L.append("<details>")
    L.append("<summary>Details for anyone who wants them</summary>")
    L.append("")
    L.append("| Check | Exit | Last line |")
    L.append("|---|---|---|")
    for name, _w, state, _f, _fix, code, out in rows:
        last = (out.strip().split("\n") or [""])[-1][:90].replace("|", "\\|")
        L.append("| %s | %s | %s |" % (name, code, last))
    L.append("")
    L.append("Generated by `tools/sweep.py`. It never merges anything and never fails a build.")
    L.append("</details>")
    L.append("")

    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    out_path = os.path.join(ROOT, "reports", "sweep-%s.md" % TODAY)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))
    print("\nwrote reports/sweep-%s.md" % TODAY, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
