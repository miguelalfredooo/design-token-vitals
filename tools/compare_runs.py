#!/usr/bin/env python3
"""Compare two design-token-vitals runs.

A run claims to be evidence, and evidence that shifts between two runs on
the same input has stopped being evidence. This compares the two
report.json files a pair of runs produced and reports where they agree.

    python3 tools/compare_runs.py a/report.json b/report.json

Exit status is 1 when the two runs disagree on any graded vital, 0
otherwise, and 2 on bad arguments — see tools/cli.py. Divergence below the grade level — a different evidence line for
the same grade, a different rendering form — is reported and does not fail
the comparison on its own, because it does not change what the report says
about the codebase.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_FINDING, EXIT_OK, add_json_flag, emit_json  # noqa: E402

VITALS = [
    "tier-integrity", "leakage", "coverage", "mode-completeness",
    "naming-coherence", "single-source", "orphans", "enforcement",
]

# Fields whose disagreement means the two runs measured different things,
# which explains almost every downstream difference. Checked first.
SCOPE_FIELDS = [
    ("discovery", "environment"),
    ("discovery", "owned_paths"),
    ("discovery", "excluded_paths"),
    ("stack", "adapters"),
    ("run", "scope"),
    ("run", "framework_versions"),
]

COUNT_FIELDS = [("run", "token_count"), ("run", "family_count"), ("run", "files_scanned")]

FORM_SECTIONS = ["color", "typography", "spacing", "leaks", "orphans", "modes", "families"]


def get(doc, *path):
    cur = doc
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def norm(value):
    """Order-insensitive for lists, so a reshuffle reads as agreement."""
    if isinstance(value, list):
        return sorted(json.dumps(v, sort_keys=True) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return value


def row(label, a, b):
    same = norm(a) == norm(b)
    mark = "  ok  " if same else " DIFF "
    if same:
        return same, f"{mark} {label:<34} {shorten(a)}"
    return same, f"{mark} {label:<34} A: {shorten(a)}\n{'':41}B: {shorten(b)}"


def shorten(value, width=76):
    text = json.dumps(value, sort_keys=True) if isinstance(value, (list, dict)) else str(value)
    return text if len(text) <= width else text[: width - 1] + "…"


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_a")
    ap.add_argument("run_b")
    add_json_flag(ap)
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2
    with open(args.run_a, encoding="utf-8") as fh:
        a = json.load(fh)
    with open(args.run_b, encoding="utf-8") as fh:
        b = json.load(fh)

    grade_diffs = 0
    other_diffs = 0

    print("\n── what each run measured " + "─" * 46)
    for section, field in SCOPE_FIELDS:
        same, line = row(f"{section}.{field}", get(a, section, field), get(b, section, field))
        other_diffs += not same
        print(line)

    print("\n── what each run counted " + "─" * 47)
    for section, field in COUNT_FIELDS:
        same, line = row(f"{section}.{field}", get(a, section, field), get(b, section, field))
        other_diffs += not same
        print(line)

    print("\n── the eight grades " + "─" * 52)
    for vital in VITALS:
        ga, gb = get(a, "vitals", vital, "grade"), get(b, "vitals", vital, "grade")
        same, line = row(vital, ga, gb)
        grade_diffs += not same
        print(line)

    print("\n── evidence attached to each grade " + "─" * 37)
    for vital in VITALS:
        ea = get(a, "vitals", vital, "evidence") or []
        eb = get(b, "vitals", vital, "evidence") or []
        shared = set(ea) & set(eb)
        if set(ea) == set(eb):
            print(f"  ok   {vital:<34} {len(ea)} item(s), identical")
        else:
            other_diffs += 1
            print(f" DIFF  {vital:<34} A: {len(ea)}  B: {len(eb)}  shared: {len(shared)}")
            for item in sorted(set(ea) - set(eb))[:3]:
                print(f"{'':41}only in A: {item}")
            for item in sorted(set(eb) - set(ea))[:3]:
                print(f"{'':41}only in B: {item}")

    print("\n── how each run rendered " + "─" * 47)
    same, line = row("rendering.tier", get(a, "rendering", "tier"), get(b, "rendering", "tier"))
    other_diffs += not same
    print(line)
    for section in FORM_SECTIONS:
        fa, fb = get(a, "rendering", "forms", section), get(b, "rendering", "forms", section)
        if fa is None and fb is None:
            continue
        same, line = row(f"forms.{section}", fa, fb)
        other_diffs += not same
        print(line)

    print("\n" + "─" * 72)
    agreed = len(VITALS) - grade_diffs
    print(f"grades agreed:      {agreed} of {len(VITALS)}")
    print(f"other divergences:  {other_diffs}")
    emit_json(args.json_out, {
        "grades_agreed": agreed, "grades_total": len(VITALS),
        "grade_divergences": [v for v in VITALS if get(a, "vitals", v, "grade") != get(b, "vitals", v, "grade")],
        "other_divergences": other_diffs,
    })
    if grade_diffs:
        print("\nThe two runs disagree on what this codebase is. Read the scope block")
        print("first — a different owned path or adapter set explains most of the rest.")
        return EXIT_FINDING
    if other_diffs:
        print("\nThe two runs agree on all eight grades. The divergences above sit below")
        print("the grade level and change nothing the report claims about the codebase.")
        return EXIT_OK
    print("\nThe two runs are identical.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
