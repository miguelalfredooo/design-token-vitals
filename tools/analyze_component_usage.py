#!/usr/bin/env python3
"""Rank framework-neutral component surfaces by canonical token usage."""
import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_OK, add_json_flag, emit_json  # noqa: E402


SOURCE_EXTENSIONS = {
    ".css", ".scss", ".sass", ".less", ".styl",
    ".js", ".jsx", ".ts", ".tsx", ".gjs", ".gts",
    ".vue", ".svelte", ".html", ".hbs", ".erb", ".liquid",
}
STYLE_EXTENSIONS = {".css", ".scss", ".sass", ".less", ".styl"}
EXCLUDED_PARTS = {
    ".git", ".token-vitals", "node_modules", "vendor", "dist", "build",
    "coverage", "tmp", "test", "tests", "spec", "specs", "fixtures",
    "snapshots",
}
CSS_REFERENCE = re.compile(r"var\(\s*--([a-zA-Z0-9_-]+)")
SCSS_REFERENCE = re.compile(r"(?<![\w-])\$([a-zA-Z0-9_-]+)")
SCSS_DECLARATION = re.compile(r"^\s*\$([a-zA-Z0-9_-]+)\s*:")
DEVICE_SEGMENTS = {"common", "desktop", "mobile", "admin", "styles", "style"}
DEVICE_SUFFIX = re.compile(r"[-_](?:mobile|desktop)$", re.I)
COMPOUND_STEM_SUFFIX = re.compile(r"\.(?:module|component|styles?|style)$", re.I)
PROVEN_COMPONENT_ROOT_CONFIDENCE = {
    "framework-registered", "import-graph verified", "runtime verified",
}
COMPONENT_CONFIDENCE_RANK = {
    "path-inferred": 0,
    "co-named-source": 1,
    "framework-registered": 2,
    "import-graph verified": 3,
    "runtime verified": 4,
}
ROADMAP_BANDS = (
    {
        "id": "assess-first",
        "label": "Assess first",
        "threshold": 50,
        "description": (
            "The components that make up the first half of confirmed token use "
            "in this ranked view."
        ),
    },
    {
        "id": "plan-next",
        "label": "Plan next",
        "threshold": 80,
        "description": (
            "The components that move the cumulative total from roughly 50% "
            "to 80%."
        ),
    },
    {
        "id": "focused-follow-up",
        "label": "Focused follow-up",
        "threshold": 100,
        "description": (
            "The remaining ranked components, where confirmed token use is "
            "more focused."
        ),
    },
)


def normalize(name):
    return str(name).lstrip("-$").replace("_", "-").lower()


def stable_id(key):
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def is_excluded(path):
    return any(part in EXCLUDED_PARTS for part in path.split(os.sep))


def add_tree(files, path, root):
    if os.path.isfile(path):
        rel = os.path.relpath(path, root)
        if os.path.splitext(rel)[1].lower() in SOURCE_EXTENSIONS and not is_excluded(rel):
            files.add(rel)
        return
    if not os.path.isdir(path):
        return
    for current, dirs, names in os.walk(path):
        dirs[:] = [name for name in dirs if name not in EXCLUDED_PARTS]
        for name in names:
            full = os.path.join(current, name)
            rel = os.path.relpath(full, root)
            if os.path.splitext(name)[1].lower() in SOURCE_EXTENSIONS and not is_excluded(rel):
                files.add(rel)


def component_root_records(discovery):
    """Return adapter-proven component roots with their actual evidence."""
    roots = discovery.get("component_roots")
    if roots is None:
        roots = (discovery.get("components", {}) or {}).get("roots", [])
    proven = []
    for item in roots or []:
        if isinstance(item, str):
            continue
        if (item.get("path") and
                item.get("confidence") in PROVEN_COMPONENT_ROOT_CONFIDENCE and
                item.get("ownership") == "owned"):
            proven.append(item)
    return proven


def component_roots(discovery):
    """Return adapter-proven component-root paths."""
    return [item["path"] for item in component_root_records(discovery)]


def strongest_component_root_confidence(path, records):
    """Preserve the strongest proven root confidence covering a path."""
    matches = [
        item["confidence"] for item in records
        if path_is_within(path, item["path"])
    ]
    return max(
        matches,
        key=lambda confidence: COMPONENT_CONFIDENCE_RANK[confidence],
    ) if matches else None


def analysis_files(root, discovery):
    """Use production reachability plus component roots proven by an adapter."""
    files = set()
    reachable = discovery.get("owned_import_graph", {}).get("reachable", {}) or {}
    for path in reachable:
        if os.path.splitext(path)[1].lower() in SOURCE_EXTENSIONS and not is_excluded(path):
            files.add(path)
    for path in component_roots(discovery):
        add_tree(files, os.path.join(root, path), root)
    return sorted(files)


def owner_for(parts):
    if len(parts) > 1 and parts[0] in ("plugins", "packages", "apps"):
        return parts[1]
    if parts and parts[0] == "app":
        return "core"
    return parts[0] if parts else "root"


def component_identity(path):
    """Infer one stable UI ownership unit without assuming a framework."""
    normalized_path = path.replace("\\", "/")
    parts = normalized_path.split("/")
    owner = owner_for(parts)
    raw_stem = os.path.splitext(parts[-1])[0].lstrip("_")
    is_index = raw_stem.lower() == "index"
    stem = parts[-2] if is_index and len(parts) > 1 else raw_stem
    stem = COMPOUND_STEM_SUFFIX.sub("", stem)
    stem = DEVICE_SUFFIX.sub("", stem)

    marker = next((i for i, part in enumerate(parts[:-1])
                   if part in ("components", "component")), None)
    if marker is not None:
        tail = [part for part in parts[marker + 1:-1] if part not in DEVICE_SEGMENTS]
        slug_parts = tail if is_index else tail + [stem]
        if len(slug_parts) > 1 and normalize(slug_parts[-2]) == normalize(slug_parts[-1]):
            slug_parts.pop()
        slug = "/".join(slug_parts)
        kind = "component"
    elif "stylesheets" in parts:
        marker = parts.index("stylesheets")
        tail = [part for part in parts[marker + 1:-1] if part not in DEVICE_SEGMENTS]
        slug = "/".join(tail + [stem])
        kind = "style-surface"
    else:
        tail = [part for part in parts[:-1]
                if part not in DEVICE_SEGMENTS and part not in ("plugins", "packages", "apps", owner)]
        slug_parts = tail[-2:] if is_index else tail[-2:] + [stem]
        if len(slug_parts) > 1 and normalize(slug_parts[-2]) == normalize(slug_parts[-1]):
            slug_parts.pop()
        slug = "/".join(slug_parts)
        kind = "surface"
    slug = slug.strip("/") or stem
    key = "%s::%s" % (owner.lower(), slug.lower())
    return key, "%s / %s" % (owner, slug), kind


def path_is_within(path, directory):
    """Return whether a repository-relative path is inside a proven root."""
    normalized_path = path.replace("\\", "/").strip("/")
    normalized_directory = directory.replace("\\", "/").strip("/")
    return (normalized_path == normalized_directory or
            normalized_path.startswith(normalized_directory + "/"))


def strip_comments_preserving_lines(text):
    """Blank CSS, Sass, JS and markup comments without changing line numbers."""
    chars = list(text)
    result = []
    index = 0
    quote = None
    escaped = False
    block_end = None
    line_comment = False
    while index < len(chars):
        char = chars[index]
        pair = text[index:index + 2]
        quad = text[index:index + 4]
        if line_comment:
            if char == "\n":
                line_comment = False
                result.append(char)
            else:
                result.append(" ")
            index += 1
            continue
        if block_end:
            if text.startswith(block_end, index):
                result.extend(" " * len(block_end))
                index += len(block_end)
                block_end = None
            else:
                result.append("\n" if char == "\n" else " ")
                index += 1
            continue
        if quote:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            result.append(char)
            index += 1
        elif quad == "<!--":
            result.extend(" " * 4)
            index += 4
            block_end = "-->"
        elif pair == "/*":
            result.extend("  ")
            index += 2
            block_end = "*/"
        elif pair == "//" and (index == 0 or text[index - 1] != ":"):
            result.extend("  ")
            index += 2
            line_comment = True
        else:
            result.append(char)
            index += 1
    return "".join(result)


def references_in_text(text, concepts):
    """Return canonical token references with exact line evidence."""
    found = []
    for number, original in enumerate(strip_comments_preserving_lines(text).splitlines(), 1):
        line = original
        declaration = SCSS_DECLARATION.match(line)
        if declaration:
            line = line[declaration.end():]
        for match in CSS_REFERENCE.finditer(line):
            token = normalize(match.group(1))
            if token in concepts:
                found.append((token, number, "css-custom-property"))
        for match in SCSS_REFERENCE.finditer(line):
            token = normalize(match.group(1))
            if token in concepts:
                found.append((token, number, "scss-variable"))
    return found


def rounded_percent(numerator, denominator):
    return round(100.0 * numerator / denominator, 1) if denominator else 0.0


def build_roadmap(rows):
    """Split the ranked view into cumulative-use bands without claiming quality."""
    total = sum(item.get("references", 0) for item in rows)
    band_rows = {item["id"]: [] for item in ROADMAP_BANDS}
    running = 0
    for row in rows:
        band = ROADMAP_BANDS[-1]
        if total:
            for candidate in ROADMAP_BANDS:
                if running * 100 < candidate["threshold"] * total:
                    band = candidate
                    break
        running += row.get("references", 0)
        row["share_of_ranked_references"] = rounded_percent(
            row.get("references", 0), total
        )
        row["cumulative_share_of_ranked_references"] = rounded_percent(
            running, total
        )
        row["roadmap_band"] = band["id"]
        band_rows[band["id"]].append(row)

    bands = []
    for band in ROADMAP_BANDS:
        members = band_rows[band["id"]]
        if not members:
            continue
        references = sum(item.get("references", 0) for item in members)
        bands.append({
            "id": band["id"],
            "label": band["label"],
            "description": band["description"],
            "start_rank": members[0]["rank"],
            "end_rank": members[-1]["rank"],
            "component_ids": [item["id"] for item in members],
            "references": references,
            "share_of_ranked_references": rounded_percent(references, total),
        })
    return {
        "state": "measured",
        "basis": (
            "Confirmed canonical token-reference occurrences in the ranked "
            "component view. This ranks investigation by token footprint. "
            "Migration safety, runtime frequency, and component quality need "
            "separate evidence."
        ),
        "ranked_references": total,
        "bands": bands,
    }


def analyze(root, discovery, tokens, limit=20):
    root = os.path.abspath(root)
    concepts = {item["id"]: item for item in tokens.get("concepts", [])}
    definition_paths = {
        item.get("path") for item in tokens.get("sources", [])
        if item.get("role") in ("canonical", "alias")
    }
    paths = analysis_files(root, discovery)
    proven_component_roots = component_root_records(discovery)
    groups = {}
    for path in paths:
        key, name, kind = component_identity(path)
        group = groups.setdefault(key, {
            "name": name, "kind": kind, "paths": set(),
            "has_source": False, "has_style": False, "confidences": set(),
        })
        group["paths"].add(path)
        is_style = os.path.splitext(path)[1].lower() in STYLE_EXTENSIONS
        group["has_style"] = group["has_style"] or is_style
        group["has_source"] = group["has_source"] or not is_style
        root_confidence = strongest_component_root_confidence(
            path, proven_component_roots
        )
        if kind == "component":
            group["confidences"].add("path-inferred")
        if kind == "component" or root_confidence:
            group["kind"] = "component"
        if root_confidence:
            group["confidences"].add(root_confidence)
    for group in groups.values():
        if group["has_source"] and group["has_style"]:
            group["kind"] = "component"
            group["confidences"].add("co-named-source")
        group["confidence"] = max(
            group["confidences"] or {"path-inferred"},
            key=lambda confidence: COMPONENT_CONFIDENCE_RANK[confidence],
        )
    units = {}
    scanned = 0
    for path in paths:
        if path in definition_paths:
            continue
        full = os.path.join(root, path)
        try:
            with open(full, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        scanned += 1
        refs = references_in_text(text, concepts)
        if not refs:
            continue
        key, name, kind = component_identity(path)
        group = groups[key]
        unit = units.setdefault(key, {
            "id": stable_id(key), "key": key, "name": group["name"],
            "kind": group["kind"],
            "confidence": group.get("confidence", "path-inferred"),
            "paths": set(group["paths"]), "references": 0,
            "tokens": {}, "syntaxes": set(),
        })
        for token, line, syntax in refs:
            unit["references"] += 1
            unit["syntaxes"].add(syntax)
            detail = unit["tokens"].setdefault(token, {
                "id": token,
                "family": concepts[token].get("family", "unclassified"),
                "references": 0,
                "locations": [],
                "syntaxes": set(),
            })
            detail["references"] += 1
            detail["syntaxes"].add(syntax)
            location = "%s:%d" % (path, line)
            if location not in detail["locations"]:
                detail["locations"].append(location)

    ranked = []
    for unit in units.values():
        token_rows = sorted(unit["tokens"].values(),
                            key=lambda item: (-item["references"], item["id"]))
        token_rows = [dict(item, syntaxes=sorted(item["syntaxes"])) for item in token_rows]
        family_counts = {}
        for item in token_rows:
            family_counts[item["family"]] = family_counts.get(item["family"], 0) + item["references"]
        ranked.append({
            "id": unit["id"], "key": unit["key"], "name": unit["name"],
            "kind": unit["kind"], "confidence": unit["confidence"],
            "paths": sorted(unit["paths"]), "references": unit["references"],
            "distinct_tokens": len(token_rows), "families": family_counts,
            "syntaxes": sorted(unit["syntaxes"]), "tokens": token_rows,
        })
    ranked.sort(key=lambda item: (-item["references"], -item["distinct_tokens"], item["key"]))
    components = [item for item in ranked if item["kind"] == "component"]
    surfaces = [item for item in ranked if item["kind"] != "component"]
    selected = components[:limit]
    if len(selected) < limit:
        selected.extend(surfaces[:limit - len(selected)])
    for index, item in enumerate(selected, 1):
        item["rank"] = index
    roadmap = build_roadmap(selected)
    shown_components = sum(1 for item in selected if item["kind"] == "component")
    fallback_surfaces = len(selected) - shown_components
    return {
        "state": "measured",
        "component_definition": (
            "A framework-neutral UI ownership unit inferred from component paths; "
            "otherwise a stylesheet or template surface. Device variants with the same owner and name are grouped."
        ),
        "rank_by": "identified components first, then fallback surfaces; within each, token reference occurrences descending, distinct tokens descending, stable component key ascending",
        "files_scanned": scanned,
        "total_usage_units": len(ranked),
        "total_components_with_token_usage": len(components),
        "additional_style_surfaces": len(surfaces),
        "shown": len(selected),
        "shown_components": shown_components,
        "fallback_surfaces": fallback_surfaces,
        "not_shown": max(0, len(components) - shown_components),
        "measurement": [
            {"syntax": "css-custom-property", "state": "measured", "evidence": "var(--token)"},
            {"syntax": "scss-variable", "state": "measured", "evidence": "$token references excluding declaration left-hand sides"},
            {"syntax": "framework-generated-utility", "state": "unmeasured", "evidence": "requires an active adapter to resolve utility output to canonical tokens"},
        ],
        "roadmap": roadmap,
        "top_20": selected,
    }


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--discovery", required=True)
    parser.add_argument("--tokens", required=True)
    parser.add_argument("--limit", type=int, default=20)
    add_json_flag(parser)
    args = parser.parse_args(argv)
    with open(args.discovery, encoding="utf-8") as handle:
        discovery = json.load(handle)
    with open(args.tokens, encoding="utf-8") as handle:
        tokens = json.load(handle)
    result = analyze(args.root, discovery, tokens, max(1, args.limit))
    emit_json(args.json_out, result)
    print("measured token usage in %d identified component(s); showing %d with %d fallback surface(s)" % (
        result["total_components_with_token_usage"], result["shown_components"],
        result["fallback_surfaces"]))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
