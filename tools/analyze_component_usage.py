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


def component_roots(discovery):
    """Return adapter-proven component roots without treating ownership as reachability."""
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
            proven.append(item["path"])
    return proven


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
        kind = "component" if os.path.splitext(path)[1].lower() not in STYLE_EXTENSIONS else "style-surface"
    slug = slug.strip("/") or stem
    key = "%s::%s" % (owner.lower(), slug.lower())
    return key, "%s / %s" % (owner, slug), kind


def co_named_files(root, paths):
    """Add adjacent component source/style files that normalize to the same identity."""
    expanded = set(paths)
    for path in list(paths):
        key = component_identity(path)[0]
        directory = os.path.dirname(os.path.join(root, path))
        try:
            names = os.listdir(directory)
        except OSError:
            continue
        for name in names:
            candidate = os.path.relpath(os.path.join(directory, name), root)
            if (os.path.isfile(os.path.join(root, candidate)) and
                    os.path.splitext(name)[1].lower() in SOURCE_EXTENSIONS and
                    not is_excluded(candidate) and component_identity(candidate)[0] == key):
                expanded.add(candidate)
    return sorted(expanded)


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


def analyze(root, discovery, tokens, limit=20):
    root = os.path.abspath(root)
    concepts = {item["id"]: item for item in tokens.get("concepts", [])}
    definition_paths = {
        item.get("path") for item in tokens.get("sources", [])
        if item.get("role") in ("canonical", "alias")
    }
    paths = co_named_files(root, analysis_files(root, discovery))
    groups = {}
    for path in paths:
        key, name, kind = component_identity(path)
        group = groups.setdefault(key, {"name": name, "kind": kind, "paths": set()})
        group["paths"].add(path)
        if kind == "component":
            group["kind"] = "component"
        if os.path.splitext(path)[1].lower() not in STYLE_EXTENSIONS:
            group["kind"] = "component"
            group["confidence"] = "co-named-source"
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
