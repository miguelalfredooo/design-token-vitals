#!/usr/bin/env python3
"""Find hardcoded color groups without confusing value equality for intent."""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_OK, add_json_flag, emit_json  # noqa: E402
from findings import finding_id, normalize_literal, priority, rank  # noqa: E402


HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"//[^\n]*")
PROPERTY = re.compile(r"([a-zA-Z-]+)\s*:\s*[^;]*$")


def blank_comments(text):
    def blank(match):
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))
    return LINE_COMMENT.sub(blank, BLOCK_COMMENT.sub(blank, text))


def token_colors(tokens):
    colors = {}
    for concept in tokens.get("concepts", []):
        if concept.get("family") != "color" or "css-custom-property" not in concept.get("representations", []):
            continue
        for value in concept.get("values", []):
            if HEX.fullmatch(value.strip()):
                colors.setdefault(normalize_literal(value), []).append("--" + concept["id"])
    return colors


def audit(root, discovery, tokens):
    root = os.path.abspath(root)
    source_paths = {s["path"] for s in tokens.get("sources", []) if s.get("role") in ("canonical", "alias")}
    reachable = discovery.get("owned_import_graph", {}).get("reachable", {})
    groups = {}
    for path in sorted(reachable):
        if path in source_paths or os.path.splitext(path)[1] not in (".css", ".scss", ".sass", ".less"):
            continue
        try:
            with open(os.path.join(root, path), encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        clean = blank_comments(text)
        for match in HEX.finditer(clean):
            literal = normalize_literal(match.group(0))
            line = clean.count("\n", 0, match.start()) + 1
            line_prefix = clean[clean.rfind("\n", 0, match.start()) + 1:match.start()]
            prop = PROPERTY.search(line_prefix)
            item = groups.setdefault(literal, {"literal": literal, "locations": [], "files": set(), "properties": set()})
            item["locations"].append("%s:%d" % (path, line))
            item["files"].add(path)
            if prop:
                item["properties"].add(prop.group(1))
    available = token_colors(tokens)
    findings = []
    unmatched = []
    for literal, group in groups.items():
        files = sorted(group["files"])
        breadth = len({path.split("/")[1] if path.startswith("plugins/") else "core" for path in files})
        candidates = sorted(set(available.get(literal, [])))
        payload = {
            "id": finding_id("exact-value-candidate", "color", literal, ",".join(candidates)),
            "tier": "exact-value-candidate" if candidates else "uncovered-candidate",
            "family": "color", "literal": literal, "token_candidates": candidates,
            "locations": group["locations"], "occurrences": len(group["locations"]),
            "files": len(files), "affected_files": files, "breadth": breadth,
            "properties": sorted(group["properties"]), "confidence": "manual review",
            "safe_to_automate": False,
            "note": "Value equality is proven; semantic equivalence is not." if candidates
                    else "No reachable CSS custom-property token has this exact value.",
        }
        payload["priority"] = priority(payload["occurrences"], payload["files"], breadth, "manual review")
        (findings if candidates else unmatched).append(payload)
    return {
        "consumer_files_scanned": len([p for p in reachable if p not in source_paths and os.path.splitext(p)[1] in (".css", ".scss", ".sass", ".less")]),
        "exact_value_candidates": rank(findings),
        "uncovered_candidates": rank(unmatched),
        "semantic_equivalence": "unmeasured",
        "near_miss": "unmeasured",
    }


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--discovery", required=True)
    parser.add_argument("--tokens", required=True)
    add_json_flag(parser)
    args = parser.parse_args(argv)
    with open(args.discovery, encoding="utf-8") as handle:
        discovery = json.load(handle)
    with open(args.tokens, encoding="utf-8") as handle:
        tokens = json.load(handle)
    result = audit(args.root, discovery, tokens)
    emit_json(args.json_out, result)
    print("scanned %d owned reachable consumer styles — %d exact-value candidate group(s), %d uncovered candidate group(s)" % (
        result["consumer_files_scanned"], len(result["exact_value_candidates"]),
        len(result["uncovered_candidates"])))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
