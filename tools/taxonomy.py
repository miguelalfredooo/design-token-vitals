#!/usr/bin/env python3
"""The foundational token families, defined once.

`references/token-taxonomy.md` is the reader's version, with what each
family covers and the names to search for. This is the machine's version.
A test parses the Markdown table and asserts the two agree, so the prose
can be edited freely and any drift fails loudly.

    python3 tools/taxonomy.py          # print the list
    python3 tools/taxonomy.py --check  # compare against the Markdown
"""
import os
import re
import sys

TIER_ONE = [
    "color", "typography", "spacing", "sizing", "radius", "border",
    "elevation", "opacity", "layer", "motion", "breakpoint",
]
TIER_TWO = [
    "grid", "focus", "target", "state", "icon", "aspect", "blur", "density",
]
FAMILIES = TIER_ONE + TIER_TWO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKDOWN = os.path.join(ROOT, "references", "token-taxonomy.md")

# A family row in the reference tables: | `name` | covers | names |
ROW = re.compile(r"^\| `([a-z]+)` \|", re.M)


def families_in_markdown(path=MARKDOWN):
    with open(path, encoding="utf-8") as fh:
        return ROW.findall(fh.read())


def drift(path=MARKDOWN):
    """(only in code, only in prose, order differs)."""
    prose = families_in_markdown(path)
    only_code = [f for f in FAMILIES if f not in prose]
    only_prose = [f for f in prose if f not in FAMILIES]
    order_differs = (not only_code and not only_prose and prose != FAMILIES)
    return only_code, only_prose, order_differs


def main(argv):
    if "--check" in argv:
        only_code, only_prose, order = drift()
        if only_code or only_prose or order:
            if only_code:
                print("in tools/taxonomy.py and not in the Markdown: %s" % ", ".join(only_code))
            if only_prose:
                print("in the Markdown and not in tools/taxonomy.py: %s" % ", ".join(only_prose))
            if order:
                print("same families, different order — the Markdown tables should follow the code")
            return 1
        print("taxonomy: %d families, prose and code agree" % len(FAMILIES))
        return 0
    for f in FAMILIES:
        print(f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
