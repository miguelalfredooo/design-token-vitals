#!/usr/bin/env python3
"""Stable finding identity, and the remediation priority score.

Two runs across two commits have to agree on which findings are the same
finding, or a trend report reads as churn. Identity here is deliberately
path-independent: a file rename would otherwise resolve every finding in
that file and create the same number of new ones.

The priority score is a published formula over four recorded inputs rather
than an opaque number, so a reader who disagrees with the order can see
which input drove it and an agent can re-rank on its own weights.
"""
import hashlib
import re

SCHEMA_VERSION = 2

# Confidence in the proposed fix. The multiplier keeps a high-volume
# finding nobody can safely change below a smaller certain one.
CONFIDENCE = {
    "compiled-runtime verified": 1.0,
    "exact static match": 0.95,
    "import-graph verified": 0.9,
    "manual review": 0.4,
}

# A value match is necessary but not sufficient. Semantic equivalence must
# be established at the consumer before a replacement can be mechanical.
AUTOMATABLE_TIERS = {"redundant"}

HEX3 = re.compile(r"^#([0-9a-f])([0-9a-f])([0-9a-f])$", re.I)
WS = re.compile(r"\s+")
# Drop any space sitting next to punctuation, so rgb( 255 , 0 , 0 ) and
# rgb(255,0,0) fold to one spelling.
PUNCT_SPACE = re.compile(r"\s*([(),])\s*")


def normalize_literal(literal):
    """Fold the spellings of one value together.

    #FFF, #ffffff and  rgb( 255 , 255 , 255 ) are one decision written three
    ways. Treating them as three findings triples the apparent problem and
    breaks identity across runs that happen to quote a different instance.
    """
    if literal is None:
        return ""
    text = WS.sub(" ", str(literal).strip()).lower()
    text = PUNCT_SPACE.sub(r"\1", text)
    m = HEX3.match(text)
    if m:
        return "#" + "".join(ch * 2 for ch in m.groups())
    return text


def finding_id(tier, family, literal, token=None):
    """A stable id for one finding, independent of where it appears."""
    parts = [
        str(tier or ""),
        str(family or ""),
        normalize_literal(literal),
        str(token or ""),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:12]


def confidence_weight(confidence):
    return CONFIDENCE.get(confidence, CONFIDENCE["manual review"])


def is_automatable(tier, confidence, semantic_role_verified=False):
    """Safe to apply without a person deciding what was intended."""
    return (
        tier in AUTOMATABLE_TIERS
        and semantic_role_verified is True
        and confidence != "manual review"
    )


def effort(tier, confidence, files, semantic_role_verified=False):
    """S, M or L — derived from what the run already holds, never hours.

    S: safe to automate and under ten files. M: safe to automate across
    more, or a single file that needs a person's call. L: needs a decision
    before any edit — drift to reconcile, or a token to design.
    """
    auto = is_automatable(tier, confidence, semantic_role_verified)
    f = int(files or 0)
    if auto and f < 10:
        return "S"
    if auto or f <= 1:
        return "M"
    return "L"


def priority(occurrences, files, breadth, confidence):
    """priority = (n + 2f + 3b) x c — see references/report.md.

    Files outweigh occurrences because ten occurrences in one file is one
    edit. Breadth outweighs both because a value crossing six components is
    a missing system decision rather than a local slip.
    """
    n = int(occurrences or 0)
    f = int(files or 0)
    b = int(breadth or 0)
    c = confidence_weight(confidence)
    return {
        "occurrences": n,
        "files": f,
        "breadth": b,
        "confidence": confidence,
        "confidence_weight": c,
        "formula": "(n + 2f + 3b) x c",
        "score": round((n + 2 * f + 3 * b) * c, 2),
    }


def rank(findings):
    """Order findings by priority score, descending, deterministically.

    Ties break on id so two runs over the same findings produce the same
    order rather than whatever order the dict happened to hold.
    """
    def key(item):
        score = item.get("priority", {}).get("score", 0)
        return (-score, item.get("id", ""))
    return sorted(findings, key=key)


# A finding id is sha1[:12] — twelve hex characters, always. Matching on
# length alone collected the adoption strategy's `dtcg-2025.10` and
# `semver-2.0.0`, which are twelve characters and not findings, and
# validate_run rule 8 then reported them as findings the HTML had dropped.
FINDING_ID = re.compile(r"^[0-9a-f]{12}$")


def collect_ids(doc):
    """Every finding id anywhere in a report document.

    validate_run compares this against what the HTML rendered, so a
    finding that exists only in the JSON is caught.
    """
    ids = set()

    def walk(node):
        if isinstance(node, dict):
            if FINDING_ID.match(str(node.get("id", ""))):
                ids.add(node["id"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(doc)
    return ids
