#!/usr/bin/env python3
"""Fail an audit that cannot support what it claims.

    python3 tools/validate_run.py .token-vitals/report.json [--html report.html]

Eight rules, from the framework-aware discovery and actionable-report
designs. Each one describes a report that looks finished and is not, and
every one of them has produced a plausible-looking report at some point.
Exit status is 1 when any rule fails.

These run as code rather than as prose the agent checks itself against,
because a rule the run re-derives each time is a rule that drifts.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from findings import collect_ids, is_automatable  # noqa: E402

TAXONOMY_TIER_ONE = [
    "color", "typography", "spacing", "sizing", "radius", "border",
    "elevation", "opacity", "layer", "motion", "breakpoint",
]
TAXONOMY_TIER_TWO = [
    "grid", "focus", "target", "state", "icon", "aspect", "blur", "density",
]
FAMILIES = TAXONOMY_TIER_ONE + TAXONOMY_TIER_TWO

ACTIVE_CLASSES = {"canonical", "alias"}
MEASURE_STATES = {"measured", "unmeasured", "absent"}


class Failure(object):
    def __init__(self, rule, message, detail=None):
        self.rule = rule
        self.message = message
        self.detail = detail or []


def get(doc, *path, **kw):
    cur = doc
    for key in path:
        if not isinstance(cur, dict):
            return kw.get("default")
        cur = cur.get(key)
    return cur if cur is not None else kw.get("default")


def rule_1_discovery_evidence(doc):
    """One presumed token file, with nothing showing how it was found."""
    sources = get(doc, "discovery", "token_sources", default=None)
    if sources is None:
        sources = get(doc, "stack", "token_sources", default=[]) or []
    if not sources:
        return Failure("1-discovery-evidence",
                       "no token sources recorded at all")
    detected = get(doc, "discovery", "detected_by")
    graph = get(doc, "discovery", "import_graph", default={}) or {}
    roots = graph.get("roots") or []
    if len(sources) == 1 and not roots:
        return Failure(
            "1-discovery-evidence",
            "one token source, and no import-graph roots recorded to show it was discovered",
            ["source: %s" % json.dumps(sources[0])],
        )
    if not detected and not roots:
        return Failure("1-discovery-evidence",
                       "neither discovery.detected_by nor an import graph is recorded")
    return None


def rule_2_reachability(doc):
    """A source inventoried without a path to an owned production root."""
    sources = get(doc, "discovery", "token_sources", default=[]) or []
    bad = []
    for src in sources:
        if not isinstance(src, dict):
            bad.append({"path": src, "why": "source recorded without a classification"})
            continue
        cls = src.get("classification")
        if cls in ACTIVE_CLASSES and not src.get("reachable_from"):
            bad.append({"path": src.get("path"), "why": "classified %s with no reachable_from" % cls})
        if cls not in ACTIVE_CLASSES | {"consumer", "generated", "unverified"}:
            bad.append({"path": src.get("path"), "why": "unknown classification %r" % cls})
    if bad:
        return Failure("2-reachability",
                       "%d source(s) inventoried without a path to an owned entry point" % len(bad),
                       ["%s — %s" % (b["path"], b["why"]) for b in bad[:8]])
    return None


def rule_3_mode_resolution(doc):
    """Complete mode coverage claimed without resolved output per scheme."""
    grade = get(doc, "vitals", "mode-completeness", "grade")
    if grade not in ("pass", "attention", "fail"):
        return None
    schemes = get(doc, "declared", "modes", default=[]) or []
    resolved = get(doc, "discovery", "resolved_modes", default=None)
    if resolved is None:
        return Failure("3-mode-resolution",
                       "mode-completeness graded %r with no discovery.resolved_modes recorded" % grade)
    missing = [s for s in schemes if s not in resolved]
    if missing:
        return Failure("3-mode-resolution",
                       "mode-completeness graded %r while %d declared scheme(s) have no resolved output"
                       % (grade, len(missing)),
                       ["no resolved output for: %s" % ", ".join(missing)])
    return None


def rule_4_no_zero_for_unmeasured(doc):
    """An unmeasured category rendered as zero, which claims none exist."""
    fams = get(doc, "inventory", "families", default={}) or {}
    bad = []
    for name, entry in fams.items():
        if not isinstance(entry, dict):
            continue
        state = entry.get("state")
        if state not in MEASURE_STATES:
            bad.append("%s: state %r is not one of %s" % (name, state, sorted(MEASURE_STATES)))
        elif state == "unmeasured" and entry.get("count") == 0:
            bad.append("%s: unmeasured and reported as 0" % name)
        elif state == "unmeasured" and not entry.get("note"):
            bad.append("%s: unmeasured with no note saying what is missing" % name)
    if bad:
        return Failure("4-unmeasured-as-zero",
                       "%d family/families report a count they never measured" % len(bad), bad[:8])
    return None


def rule_5_family_coverage(doc):
    """Typography or another foundational family missing from the report."""
    fams = get(doc, "inventory", "families", default=None)
    if fams is None:
        return Failure("5-family-coverage",
                       "no inventory.families block; the taxonomy was never searched")
    missing = [f for f in FAMILIES if f not in fams]
    if "typography" in missing:
        return Failure("5-family-coverage",
                       "typography is missing from the inventory",
                       ["also missing: %s" % ", ".join(m for m in missing if m != "typography")])
    if missing:
        return Failure("5-family-coverage",
                       "%d foundational family/families never searched" % len(missing),
                       ["missing: %s" % ", ".join(missing)])
    return None


def rule_6_html_matches_json(doc, html):
    """The HTML truncated something the JSON still holds, without saying so."""
    if html is None:
        return None
    declared = get(doc, "rendering", "truncated", default=[]) or []
    # Every truncation the HTML performs has to be declared in the JSON.
    shown = re.findall(r'class="trunc"[^>]*>(.*?)</div>', html, re.S)
    if shown and not declared:
        return Failure("6-html-json-parity",
                       "the HTML declares %d truncation(s) that rendering.truncated does not record" % len(shown),
                       [re.sub(r"<[^>]+>", "", s).strip()[:90] for s in shown[:4]])
    for entry in declared:
        if not isinstance(entry, dict):
            return Failure("6-html-json-parity",
                           "rendering.truncated holds a bare value rather than {section, shown, withheld, summary}",
                           [repr(entry)])
        if not entry.get("summary"):
            return Failure("6-html-json-parity",
                           "a truncated section records no summary of what the remainder holds",
                           [json.dumps(entry)])
    return None


CONFIDENCES = {
    "exact static match", "import-graph verified",
    "compiled-runtime verified", "manual review",
}


def rule_7_fix_queue_integrity(doc):
    """A fix queue that cannot be acted on, or that promises too much."""
    queue = get(doc, "fix_queue", default=None)
    if queue is None:
        return None
    bad = []
    for item in queue:
        if not isinstance(item, dict):
            bad.append("a queue entry is not an object")
            continue
        label = item.get("id") or item.get("literal") or "?"
        conf = item.get("confidence")
        if conf not in CONFIDENCES:
            bad.append("%s: confidence %r is not one of the four levels" % (label, conf))
        if not item.get("replacement"):
            bad.append("%s: no canonical replacement token" % label)
        if not item.get("locations"):
            bad.append("%s: no file:line locations to act on" % label)
        auto = item.get("safe_to_automate")
        if auto is None:
            bad.append("%s: does not say whether the swap is safe to automate" % label)
        elif auto and not is_automatable(item.get("tier"), conf):
            bad.append("%s: marked safe to automate at tier %r, confidence %r"
                       % (label, item.get("tier"), conf))
    if bad:
        return Failure("7-fix-queue", "%d fix-queue entry problem(s)" % len(bad), bad[:8])
    return None


def rule_8_html_holds_every_finding(doc, html):
    """The HTML rendered less than the JSON holds."""
    if html is None:
        return None
    json_ids = collect_ids(doc)
    if not json_ids:
        return None
    missing = sorted(fid for fid in json_ids if fid not in html)
    if missing:
        return Failure(
            "8-html-completeness",
            "%d finding(s) exist in the JSON and appear nowhere in the HTML" % len(missing),
            missing[:8],
        )
    return None


def validate(doc, html=None):
    checks = [
        rule_1_discovery_evidence(doc),
        rule_2_reachability(doc),
        rule_3_mode_resolution(doc),
        rule_4_no_zero_for_unmeasured(doc),
        rule_5_family_coverage(doc),
        rule_6_html_matches_json(doc, html),
        rule_7_fix_queue_integrity(doc),
        rule_8_html_holds_every_finding(doc, html),
    ]
    return [c for c in checks if c is not None]


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("report_json")
    ap.add_argument("--html", dest="html")
    args = ap.parse_args(argv)

    with open(args.report_json, encoding="utf-8") as fh:
        doc = json.load(fh)
    html = None
    if args.html:
        with open(args.html, encoding="utf-8") as fh:
            html = fh.read()

    failures = validate(doc, html)
    if not failures:
        print("validate: pass — all eight rules hold")
        return 0
    for f in failures:
        print("FAIL  %-22s %s" % (f.rule, f.message))
        for line in f.detail:
            print("%26s%s" % ("", line))
    print("\n%d of 8 rules failed. The report claims more than the run established." % len(failures))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
