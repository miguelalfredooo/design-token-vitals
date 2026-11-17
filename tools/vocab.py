#!/usr/bin/env python3
"""One vocabulary for the report: five states, real plurals, one way to count.

Every word a reader sees for a grade comes from GRADE_LABEL. The raw grade
names (`needs-work`, `not-visible`) stay in data attributes and JSON, where a
script reads them, and never reach a heading, a chip or a sentence.

    healthy     Healthy
    watch       Watch
    needs-work  Fix
    not-visible Blocked     we could not see it; never "your code is wrong"
    not-needed  Not needed

The word for one of the eight is "check". The section id `vitals`, the
`vital-<name>` anchors and the JSON keys keep the old noun, because links and
tools depend on them; a reader never sees it.
"""
import re

GRADES = ("healthy", "watch", "needs-work", "not-visible", "not-needed")

GRADE_LABEL = {
    "healthy": "Healthy",
    "watch": "Watch",
    "needs-work": "Fix",
    "not-visible": "Blocked",
    "not-needed": "Not needed",
}

# What each state means, said once, beside the strip that states the grades.
GRADE_MEANING = {
    "healthy": "nothing to fix",
    "watch": "worth a look, not urgent",
    "needs-work": "a real problem with a clear fix",
    "not-visible": "we couldn't see it, which doesn't mean your code is wrong",
    "not-needed": "doesn't apply to your setup",
}

# The eight checks in their fixed order, with the name a reader sees.
CHECK_ORDER = (
    "tier-integrity", "leakage", "coverage", "mode-completeness",
    "naming-coherence", "single-source", "orphans", "enforcement",
)
CHECK_NAME = {
    "tier-integrity": "Tier integrity",
    "leakage": "Leakage",
    "coverage": "Coverage",
    "mode-completeness": "Themes",
    "naming-coherence": "Naming",
    "single-source": "Single source",
    "orphans": "Unused tokens",
    "enforcement": "Enforcement",
}
# The same names for the middle of a sentence.
CHECK_PHRASE = {
    "tier-integrity": "tier integrity",
    "leakage": "leakage",
    "coverage": "coverage",
    "mode-completeness": "themes",
    "naming-coherence": "naming",
    "single-source": "single source",
    "orphans": "unused tokens",
    "enforcement": "enforcement",
}
# What each check asks, in one question. Shown once, on its card.
CHECK_ASKS = {
    "tier-integrity": "Do components reach for a role, or skip to a raw value?",
    "leakage": "Are colors hardcoded where a token already exists?",
    "coverage": "Does every kind of design decision have a token?",
    "mode-completeness": "Does every token have a value in each of your themes?",
    "naming-coherence": "Do token names follow one pattern?",
    "single-source": "Is each token set in one place?",
    "orphans": "Are there tokens nothing uses?",
    "enforcement": "Does anything stop this drifting back?",
}
# Where the lines between the states sit, for the method chapter.
CHECK_LINE = {
    "tier-integrity": "Healthy at 0 files, Watch up to 5%, Fix above 5%",
    "leakage": "Healthy at 0 proven matches, Watch up to 10, Fix at 11 or more",
    "coverage": "Healthy at 11 of 11 categories, Watch at 8 to 10, Fix below 8",
    "mode-completeness": "Healthy at 0 gaps in every theme",
    "naming-coherence": "Healthy at 1 pattern, Watch at 2, Fix at 3 or more",
    "single-source": "Healthy at 1 place, Watch when copies agree, Fix when they differ",
    "orphans": "Healthy under 2%, Watch up to 10%, Fix above 10%",
    "enforcement": "Healthy at 2 or more automatic checks, Watch at 1",
}


def label(grade):
    """The word a reader sees for a raw grade."""
    return GRADE_LABEL.get(grade, GRADE_LABEL["not-visible"])


def fmt(n):
    """A count with a thousands separator."""
    try:
        return "{:,}".format(int(n))
    except (TypeError, ValueError):
        return str(n)


def plural(n, singular, many=None, count=True):
    """`1 check`, `3 checks`. A count of one never gets an s."""
    try:
        one = int(n) == 1
    except (TypeError, ValueError):
        one = False
    word = singular if one else (many or singular + "s")
    return "%s %s" % (fmt(n), word) if count else word


def pct(part, whole, places=0):
    """`89%`, or an empty string when there is no whole to divide by."""
    if not whole:
        return ""
    return ("%." + str(places) + "f%%") % (100.0 * part / whole)


def of(part, whole, noun=None):
    """`1,088 of 1,216 tokens (89%)`: a count with its denominator and its share."""
    text = "%s of %s" % (fmt(part), fmt(whole))
    if noun:
        text += " " + noun
    share = pct(part, whole)
    return "%s (%s)" % (text, share) if share else text


def join_and(items):
    """`a`, `a and b`, `a, b and c`."""
    items = [str(item) for item in items if item]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def sentence(text):
    """Trimmed, with one full stop."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return ""
    return text if text[-1] in ".!?" else text + "."


def first_sentence(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    match = re.match(r"(.+?[.!?])(?:\s|$)", text)
    return match.group(1) if match else text


# Words an audit's own notes carry that a reader should never meet. The notes
# are written by whoever ran the audit, so the renderer cannot trust them to
# keep the vocabulary; this is the net under them.
_PLAIN = (
    (re.compile(r"\bnot[- ]visible\b", re.I), "blocked"),
    (re.compile(r"\bneeds[- ]work\b", re.I), "fix"),
    (re.compile(r"\bnot[- ]needed\b", re.I), "not needed"),
    (re.compile(r"\bunmeasured\b", re.I), "not measured"),
    (re.compile(r"\bblast radius\b", re.I), "reach"),
    (re.compile(r"\bvital\(s\)", re.I), "checks"),
    (re.compile(r"\bcheck\(s\)", re.I), "checks"),
    (re.compile(r"\bvitals\b"), "checks"),
    (re.compile(r"\bvital\b"), "check"),
    (re.compile(r"\b(\w+)\(s\)"), r"\1s"),
)


def plain(text, root=None):
    """An audit note in the report's words, with paths made relative.

    `root` is the audited repository's absolute path. A path that starts
    there is shown from the repository's own top, because the reader is
    standing in it and an absolute path names somebody's machine.
    """
    text = str(text or "")
    if root:
        root = str(root).rstrip("/")
        text = text.replace(root + "/", "").replace(root, ".")
    for pattern, word in _PLAIN:
        text = pattern.sub(word, text)
    return text


def grade_of(report, name):
    return ((report.get("vitals") or {}).get(name) or {}).get("grade", "not-visible")


def grade_counts(report):
    """The one breakdown of the eight checks. It always sums to eight.

    A grade the run does not recognize counts as blocked, the conservative
    reading, so no check ever falls out of the total.
    """
    counts = {grade: 0 for grade in GRADES}
    for name in CHECK_ORDER:
        grade = grade_of(report, name)
        counts[grade if grade in counts else "not-visible"] += 1
    return counts


def measured(counts):
    """How many checks returned a reading: healthy, watch or fix."""
    return counts["healthy"] + counts["watch"] + counts["needs-work"]


def breakdown(counts, zeros=False):
    """`2 Healthy · 2 Watch · 1 Fix · 3 Blocked`, in the fixed order."""
    return " · ".join(
        "%s %s" % (fmt(counts[grade]), GRADE_LABEL[grade])
        for grade in GRADES if zeros or counts[grade])
