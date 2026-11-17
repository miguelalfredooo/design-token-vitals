#!/usr/bin/env python3
"""The one ranked list of what to do next.

The report used to answer "what do I do first" in four places, each in its
own words, and they disagreed. This module is the only place that answers
it. The verdict, the three action chapters and the closing list all read
`rank(report)` and render what it returns, so they cannot drift apart.

The order is a rule and never a score:

1. fix      a confirmed defect: a check graded Fix, with a place to point at
2. decide   a call only you can make: something we found and cannot judge
3. unlock   a blocked check: something we couldn't see, and what would show it

Inside a kind the order is stable. Fixes follow the fixed order of the eight
checks. Decisions run from the one a grade is waiting on to the ones that
only tidy the record. Unlocks put the step that frees the most checks first,
in the order `unlock_path.py` already settled.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vocab import (  # noqa: E402
    CHECK_NAME, CHECK_ORDER, CHECK_PHRASE, first_sentence, join_and, plural,
    sentence,
)

KINDS = ("fix", "decide", "unlock")
VERB = {"fix": "Fix", "decide": "Decide", "unlock": "Unlock"}
CHAPTER = {"fix": "#fix-now", "decide": "#decide", "unlock": "#unlock"}


def _vital(report, name):
    return (report.get("vitals") or {}).get(name) or {}


def _move(kind, key, title, **extra):
    move = {
        "id": "%s:%s" % (kind, key), "kind": kind, "verb": VERB[kind],
        "title": sentence(title), "action": "", "detail": "", "where": None,
        "command": None, "check": None, "unlocks": [], "href": CHAPTER[kind],
    }
    move.update(extra)
    move["detail"] = sentence(move["detail"])
    # A fix says what was found and then what to do. A decision or an unlock
    # is already an instruction, so its title is its action.
    move["action"] = sentence(move["action"]) or move["title"]
    return move


def fix_moves(report):
    """One move for each check graded Fix, in the order of the eight."""
    summary = report.get("executive_summary") or {}
    highest = summary.get("highest_impact") or {}
    first = summary.get("fix_first") or {}
    moves = []
    for name in CHECK_ORDER:
        vital = _vital(report, name)
        if vital.get("grade") != "needs-work":
            continue
        evidence = vital.get("evidence") or []
        lead = not moves
        # The run's own "fix first" belongs to the first defect. A later one
        # is described from its own check and never borrows that text.
        title = (vital.get("headline")
                 or (highest.get("statement") if lead else None)
                 or first_sentence(vital.get("note"))
                 or "%s has a confirmed defect" % CHECK_NAME[name])
        moves.append(_move(
            "fix", name, title, check=name,
            action=(vital.get("fix") or (first.get("action") if lead else "")
                    or "Make one of them the only one"),
            where=(vital.get("where")
                   or (first.get("file_line") if lead else None)
                   or (evidence[0] if evidence else None)),
            reach=(highest.get("blast_radius") if lead else None),
            declarations=vital.get("declarations") or [],
        ))
    return moves


def decide_moves(report):
    """Calls only the reader can make, most consequential first."""
    moves = []
    leakage = report.get("leakage_analysis") or {}
    exact = leakage.get("exact_value_candidates") or []
    if exact:
        blocked = _vital(report, "leakage").get("grade") == "not-visible"
        one = len(exact) == 1
        moves.append(_move(
            "decide", "matching-colors",
            "Decide what the %s %s" % (
                plural(len(exact), "matching color"), "is" if one else "are"),
            check="leakage",
            detail=("Leakage stays blocked until you do" if blocked else
                    "Each is the same value as a token. Only you know if it "
                    "is the same decision"),
            where=(exact[0].get("locations") or [None])[0],
            unlocks=["leakage"] if blocked else [], count=len(exact),
            anchor="#leakage",
        ))
    roots = (report.get("discovery") or {}).get("roots") or []
    unknown = [item for item in roots if item.get("ownership") == "unknown"]
    if unknown:
        moves.append(_move(
            "decide", "root-owners",
            "Say who owns %s" % plural(len(unknown), "entry file"),
            detail="We only grade code you own, so an entry with no owner is left out",
            where=unknown[0].get("path"), count=len(unknown),
            anchor="#about-run",
        ))
    held = (report.get("inventory") or {}).get(
        "candidate_or_local_override_sources") or []
    if held:
        moves.append(_move(
            "decide", "held-out-sources",
            "Decide whether %s %s tokens or local overrides" % (
                plural(len(held), "held-out file"),
                "holds" if len(held) == 1 else "hold"),
            detail="They set values that look like tokens. We counted none of them",
            where=held[0].get("path"), count=len(held), anchor="#inventory",
        ))
    owed = (report.get("confidence") or {}).get("decisions_owed") or []
    if owed:
        moves.append(_move(
            "decide", "reasons-owed",
            "Say why %s %s not needed" % (
                join_and([CHECK_PHRASE.get(name, name) for name in owed]),
                "is" if len(owed) == 1 else "are"),
            detail="A check switched off with no reason on record stays off quietly",
            count=len(owed), anchor="#vitals",
        ))
    return moves


def unlock_moves(report):
    """One move for each thing we couldn't see, in the order that frees most."""
    steps = (report.get("confidence") or {}).get("unlock_path") or []
    moves = []
    for step in steps:
        unlocks = [name for name in CHECK_ORDER if name in (step.get("unlocks") or [])]
        moves.append(_move(
            "unlock", step.get("capability") or "unknown",
            step.get("action") or "", unlocks=unlocks,
            detail=("Unblocks %s" % join_and(
                [CHECK_PHRASE.get(name, name) for name in unlocks])
                if unlocks else ""),
            command=step.get("verify") or None,
            capability=step.get("capability"),
        ))
    return moves


def rank(report):
    """Every move, in the one order the report uses."""
    return fix_moves(report) + decide_moves(report) + unlock_moves(report)


def first(report):
    """The first move, or None when nothing is waiting."""
    ranked = rank(report)
    return ranked[0] if ranked else None


def blocked_checks(report):
    """The checks we couldn't see, in the order of the eight."""
    return [name for name in CHECK_ORDER
            if _vital(report, name).get("grade", "not-visible") == "not-visible"]


def counters(report):
    """What is waiting on the reader, in units they can count.

    Fix and Unlock count checks, so both agree with the strip of eight.
    Decide counts calls, because one check can wait on several.
    """
    fixes = fix_moves(report)
    decisions = decide_moves(report)
    blocked = blocked_checks(report)
    return [
        {"kind": "fix", "label": "Fix now", "count": len(fixes),
         "unit": plural(len(fixes), "confirmed defect", count=False),
         "href": CHAPTER["fix"]},
        {"kind": "decide", "label": "Decide", "count": len(decisions),
         "unit": plural(len(decisions), "call to make", "calls to make", count=False),
         "href": CHAPTER["decide"]},
        {"kind": "unlock", "label": "Unlock", "count": len(blocked),
         "unit": plural(len(blocked), "blocked check", count=False),
         "href": CHAPTER["unlock"]},
    ]


def as_rows(report):
    """`[title, where]` for every move: the shape the JSON twin of the list keeps."""
    return [[move["title"], move["where"] or move["command"] or ""]
            for move in rank(report)]
