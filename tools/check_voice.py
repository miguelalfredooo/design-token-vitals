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


# British -> American. Invariant: no entry's British spelling may be a
# substring of an earlier entry's British spelling, or the earlier match
# fires first and reports the wrong replacement.
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

# An inline code span holds code, the same as a fenced block does. A token
# name, a config key, or an identifier a reader has to type verbatim is not
# prose, and policing it forces the writer to either weaken the document or
# smuggle the word past the lint. `references/token-taxonomy.md` has to list
# "colour" as a name to search for, because codebases spell it that way.
INLINE_CODE = re.compile(r"`+[^`]*`+")


def strip_inline_code(line):
    """Blank out inline code spans, keeping the line length so columns hold."""
    return INLINE_CODE.sub(lambda m: " " * len(m.group(0)), line)


def _fence_skip_lines(lines):
    """Pair up fence delimiters (0-based line indices). Returns (skip, unbalanced)
    where skip is the set of 0-based indices to exclude from checks (both the
    delimiter lines and everything strictly between a matched pair), and
    unbalanced is the 0-based index of a trailing unmatched delimiter, or
    None if every fence closes.
    """
    fence_lines = [i for i, line in enumerate(lines) if line.strip().startswith("```")]
    skip = set()
    pending_open = None
    for idx in fence_lines:
        if pending_open is None:
            pending_open = idx
        else:
            skip.update(range(pending_open, idx + 1))
            pending_open = None
    unbalanced = pending_open
    if unbalanced is not None:
        skip.add(unbalanced)
    return skip, unbalanced


def check_text(text):
    findings = []
    lines = text.split("\n")
    skip, unbalanced = _fence_skip_lines(lines)
    for i, raw in enumerate(lines, start=1):
        idx = i - 1
        if idx == unbalanced:
            findings.append(Finding(
                i, "error", "unbalanced-fence",
                "fence opened here never closes",
            ))
        if idx in skip:
            continue
        prose = strip_inline_code(raw)
        for old, new in SPELLING:
            if old in prose:
                findings.append(Finding(
                    i, "error", "us-english",
                    "'%s' is British; use '%s'" % (old, new),
                ))
                break
        low = prose.lower()
        for phrase in BANNED:
            if re.search(r"\b%s\b" % re.escape(phrase), low):
                findings.append(Finding(
                    i, "error", "banned-phrase",
                    "'%s' is on the banned list" % phrase,
                ))
                break
        if NEG_PARALLEL.search(prose):
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
