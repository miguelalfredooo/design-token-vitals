#!/usr/bin/env python3
"""Copy-standard lint for design-token-vitals.

Errors fail the run. Warnings are advisory.
"""
import re
import sys
from typing import NamedTuple


class Finding(NamedTuple):
    line: int
    level: str
    rule: str
    message: str


# British -> American. Longest first so plurals win over singulars.
SPELLING = [
    ("Colours", "Colors"), ("colours", "colors"),
    ("Colour", "Color"), ("colour", "color"),
    ("untokenised", "untokenized"), ("tokenised", "tokenized"),
    ("summarised", "summarized"), ("normalised", "normalized"),
    ("organised", "organized"), ("recognised", "recognized"),
    ("prioritised", "prioritized"), ("standardised", "standardized"),
    ("acknowledgement", "acknowledgment"), ("judgement", "judgment"),
    ("catalogue", "catalog"), ("cancelled", "canceled"),
    ("labelled", "labeled"), ("behaviour", "behavior"),
    ("centre", "center"), ("grey", "gray"),
    ("whilst", "while"), ("amongst", "among"), ("learnt", "learned"),
]

BANNED = [
    "simply", "utilize", "utilise", "leverage",
    "in order to", "seamlessly", "effortlessly", "robust",
]

NEG_PARALLEL = re.compile(r"\b(?:is|are|was|were)\s+not\s+(?:a|an|the)\b", re.I)


def check_text(text):
    findings = []
    for i, raw in enumerate(text.split("\n"), start=1):
        for old, new in SPELLING:
            if old in raw:
                findings.append(Finding(
                    i, "error", "us-english",
                    "'%s' is British; use '%s'" % (old, new),
                ))
                break
        low = raw.lower()
        for phrase in BANNED:
            if re.search(r"\b%s\b" % re.escape(phrase), low):
                findings.append(Finding(
                    i, "error", "banned-phrase",
                    "'%s' is on the banned list" % phrase,
                ))
                break
        if NEG_PARALLEL.search(raw):
            findings.append(Finding(
                i, "warning", "negative-parallelism",
                "rewrite as a positive statement",
            ))
    return findings


def has_errors(findings):
    return any(f.level == "error" for f in findings)


def main(paths):
    failed = False
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            findings = check_text(fh.read())
        for f in findings:
            print("%s:%d  %-8s %-20s %s" % (path, f.line, f.level, f.rule, f.message))
        if has_errors(findings):
            failed = True
    if not failed:
        print("voice: clean (%d file(s))" % len(paths))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
