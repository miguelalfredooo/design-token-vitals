#!/usr/bin/env python3
"""Derive the list size and per-section form, instead of typing them.

Both were authoring decisions the report author had to get right by hand:
three list sizes and thirteen form values across seven sections, where a
wrong value is a silent formatting bug rather than an error. Both rules were
already deterministic and already written down — `references/report.md` — and
both are functions of a count the run already has. Nobody should be typing
them, and two runs of the same repository should never present differently.

The one axis left as a choice is `rendering.view`, because it encodes what
the run is FOR rather than how much data came back.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_OK, add_json_flag, emit_json  # noqa: E402

# references/report.md, "Pick the form from the volume". The threshold is the
# point at which the sparser form stops being readable, taken from that table.
SECTIONS = ("color", "typography", "spacing", "leaks", "orphans", "modes",
            "families")

FORMS = {
    "color": ("rows", "swatches", "ramps"),
    "typography": ("rows", "specimens"),
    "spacing": ("rows", "bars"),
    "leaks": ("rows", "grouped", "distribution"),
    "orphans": ("rows", "chips", "by-family"),
    "modes": ("matrix", "coverage-bar"),
    "families": ("rows", "health-strip", "by-namespace"),
}

# Where each form gives way to the next, from the same table.
THRESHOLDS = {
    "color": (300, 1000),
    "typography": (40,),
    "spacing": (60,),
    "leaks": (200, 1000),
    "orphans": (300, 1000),
    "modes": (1,),
    "families": (60, 400),
}


def list_size(token_count):
    """`full` under 150, `short` through 600, `summary` above it.

    The boundaries are inclusive as written: exactly 150 is `short`, and so
    is exactly 600.
    """
    if token_count < 150:
        return "full"
    if token_count <= 600:
        return "short"
    return "summary"


def form_for(section, count):
    options = FORMS[section]
    steps = THRESHOLDS[section]
    index = sum(1 for step in steps if count > step)
    return options[min(index, len(options) - 1)]


def forms(section_counts):
    """One form per section, each from that section's OWN count.

    Not from the token total: a repository can be small and still have a
    leakage section large enough to need the densest form in the table.
    """
    return {section: form_for(section, (section_counts or {}).get(section, 0))
            for section in SECTIONS}


def apply(report, token_count, section_counts):
    rendering = report.setdefault("rendering", {})
    rendering["tier"] = list_size(token_count)
    rendering["forms"] = forms(section_counts)
    return report


def section_counts(tokens, leakage, discovery):
    """Each section's own measured count, from the artifacts the run wrote.

    A family the run could not see contributes nothing rather than a zero:
    `not-visible` carries no number, and inventing one here would pick a
    rendering form on evidence that does not exist.
    """
    families = (tokens or {}).get("family_states") or {}

    def family(name):
        return (families.get(name) or {}).get("count", 0)

    leakage = leakage or {}
    orphans = ((discovery or {}).get("orphans") or {}).get("owned") or []
    return {
        "color": family("color"),
        "typography": family("typography"),
        "spacing": family("spacing"),
        "leaks": (len(leakage.get("exact_value_candidates") or []) +
                  len(leakage.get("uncovered_candidates") or [])),
        "orphans": len(orphans),
        "modes": len(((discovery or {}).get("mode_resolution") or {})
                     .get("resolved_pairs") or []),
        "families": len(families),
    }


def load(path):
    if not path:
        return {}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tokens", help="tools/discover_tokens.py output")
    parser.add_argument("--leakage", help="tools/audit_literal_colors.py output")
    parser.add_argument("--discovery", help="tools/discover_environment.py output")
    parser.add_argument("--token-count", type=int,
                        help="use instead of --tokens to ask about a bare count")
    add_json_flag(parser)
    args = parser.parse_args(argv)

    tokens = load(args.tokens)
    counts = section_counts(tokens, load(args.leakage), load(args.discovery))
    total = (args.token_count if args.token_count is not None
             else tokens.get("concept_count", 0))
    result = {"tier": list_size(total), "forms": forms(counts),
              "measured_counts": counts, "token_count": total}
    emit_json(args.json_out, result)
    print("list size for %d token(s): %s" % (total, result["tier"]))
    for section, form in sorted(result["forms"].items()):
        print("  %-12s %-14s from %d finding(s)"
              % (section, form, counts[section]))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
