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
import sys

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


def main(argv):
    count = int(argv[0]) if argv else 0
    print("list size for %d token(s): %s" % (count, list_size(count)))
    for section, form in sorted(forms({}).items()):
        print("  %-12s %s" % (section, form))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
