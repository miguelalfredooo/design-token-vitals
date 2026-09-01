#!/usr/bin/env python3
"""Compare two runs across commits: what is new, fixed, and back again.

    python3 tools/trend.py baseline.json current.json

Baselines are passed explicitly. This never writes state into the
repository it audits, and it never guesses which past run to compare
against — a stale baseline silently changing what "new" means is the
failure this avoids. Commit `.token-vitals/report.json` and any past
commit becomes a baseline.

**The comparison is gated.** Two runs that scoped differently, detected a
different framework, or discovered different token sources are answering
different questions, and diffing them produces a number that looks like
progress and is not. This refuses instead, and says which input diverged.
Pass --force to diff anyway, clearly labeled.

Exit status is 1 on a regression, 2 when the two runs are incompatible.
"""
import argparse
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from findings import collect_ids  # noqa: E402


def get(doc, *path, **kw):
    cur = doc
    for key in path:
        if not isinstance(cur, dict):
            return kw.get("default")
        cur = cur.get(key)
    return cur if cur is not None else kw.get("default")


def norm_set(value):
    if isinstance(value, list):
        return {json.dumps(v, sort_keys=True) if not isinstance(v, str) else v for v in value}
    return set()


def compatibility(base, cur):
    """What must match before a diff means anything."""
    problems = []
    checks = [
        ("framework", get(base, "discovery", "environment"), get(cur, "discovery", "environment")),
        ("adapters", sorted(norm_set(get(base, "stack", "adapters", default=[]))),
         sorted(norm_set(get(cur, "stack", "adapters", default=[])))),
        ("owned paths", sorted(norm_set(get(base, "discovery", "owned_paths", default=[]))),
         sorted(norm_set(get(cur, "discovery", "owned_paths", default=[])))),
        ("scan scope", sorted(norm_set(get(base, "run", "scope", default=[]))),
         sorted(norm_set(get(cur, "run", "scope", default=[])))),
    ]
    for label, a, b in checks:
        if a != b:
            problems.append({"input": label, "baseline": a, "current": b})

    base_src = {s.get("path") for s in get(base, "discovery", "token_sources", default=[]) or []
                if isinstance(s, dict)}
    cur_src = {s.get("path") for s in get(cur, "discovery", "token_sources", default=[]) or []
               if isinstance(s, dict)}
    if base_src != cur_src:
        problems.append({
            "input": "token sources",
            "baseline": sorted(x for x in base_src if x),
            "current": sorted(x for x in cur_src if x),
        })
    return problems


def index_findings(doc):
    """id -> {occurrences, files, title}, from wherever findings are recorded."""
    out = {}

    def take(entry):
        if not isinstance(entry, dict):
            return
        fid = entry.get("id")
        if not (isinstance(fid, str) and len(fid) == 12):
            return
        prio = entry.get("priority") or {}
        out.setdefault(fid, {
            "occurrences": entry.get("occurrences", prio.get("occurrences", 0)),
            "files": entry.get("files", prio.get("files", 0)),
            "title": entry.get("literal") or entry.get("title") or fid,
            "tier": entry.get("tier"),
        })

    def walk(node):
        if isinstance(node, dict):
            take(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    return out


def diff(base, cur):
    b = index_findings(base)
    c = index_findings(cur)
    base_ids, cur_ids = set(b), set(c)

    new = sorted(cur_ids - base_ids)
    resolved = sorted(base_ids - cur_ids)
    grew, shrank = [], []
    for fid in sorted(base_ids & cur_ids):
        was, now = b[fid].get("occurrences", 0) or 0, c[fid].get("occurrences", 0) or 0
        if now > was:
            grew.append({"id": fid, "title": c[fid]["title"], "was": was, "now": now})
        elif now < was:
            shrank.append({"id": fid, "title": c[fid]["title"], "was": was, "now": now})

    # A regression is a finding that came back, or one that grew.
    previously_resolved = set(get(base, "trend", "resolved", default=[]) or [])
    returned = sorted(previously_resolved & cur_ids)

    return {
        "new": [{"id": i, "title": c[i]["title"], "occurrences": c[i]["occurrences"]} for i in new],
        "resolved": [{"id": i, "title": b[i]["title"]} for i in resolved],
        "grew": grew,
        "shrank": shrank,
        "regressions": ([{"id": i, "title": c[i]["title"], "why": "resolved earlier, back now"}
                         for i in returned] +
                        [dict(g, why="count grew") for g in grew]),
        "baseline_total": len(base_ids),
        "current_total": len(cur_ids),
    }


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("baseline")
    ap.add_argument("current")
    ap.add_argument("--force", action="store_true",
                    help="diff incompatible runs anyway, clearly labeled")
    ap.add_argument("--json", dest="out")
    args = ap.parse_args(argv)

    with open(args.baseline, encoding="utf-8") as fh:
        base = json.load(fh)
    with open(args.current, encoding="utf-8") as fh:
        cur = json.load(fh)

    problems = compatibility(base, cur)
    if problems and not args.force:
        print("These two runs answer different questions, so a diff between them")
        print("would read as progress without being progress.\n")
        for p in problems:
            print("  %s" % p["input"])
            print("    baseline: %s" % json.dumps(p["baseline"]))
            print("    current:  %s" % json.dumps(p["current"]))
        print("\nRe-run the baseline under the current scope, or pass --force to")
        print("diff anyway with the divergence on record.")
        return 2

    result = diff(base, cur)
    if problems:
        result["incompatible"] = problems

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, sort_keys=True)

    if problems:
        print("WARNING: forced across an incompatible baseline — %d input(s) diverged\n"
              % len(problems))
    print("baseline %d finding(s) -> current %d" % (result["baseline_total"], result["current_total"]))
    print("  new:         %d" % len(result["new"]))
    print("  resolved:    %d" % len(result["resolved"]))
    print("  grew:        %d" % len(result["grew"]))
    print("  shrank:      %d" % len(result["shrank"]))
    print("  regressions: %d" % len(result["regressions"]))
    for r in result["regressions"][:10]:
        print("    %s  %s — %s" % (r["id"], r["title"], r["why"]))

    missing = collect_ids(cur) - set(index_findings(cur))
    if missing:
        print("\n%d id(s) appear in the current report outside any finding entry" % len(missing))

    return 1 if result["regressions"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
