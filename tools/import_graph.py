#!/usr/bin/env python3
"""Build the style-bearing source import graph for a repository.

A token source earns its place in the inventory by being reachable from an
entry point the project owns and ships. This walks that graph so the answer
comes from the repository rather than from a judgment made fresh each run.

    python3 tools/import_graph.py <repo-root> [--entry PATH]... [--json OUT]

With no --entry, it detects entry points from framework conventions and
reports what it found and what proved it. Output is JSON on stdout:

    {
      "workspace_packages": {"<name>": "<dir>"},
      "roots":      [{"path", "detected_by"}],
      "reachable":  {"<path>": {"depth", "via": [...]}},
      "unresolved": [{"from", "spec", "reason"}],
      "orphans":    [<path>],
      "files_scanned": <int>
    }

`orphans` is the finding that matters: a stylesheet holding token
declarations that no entry point reaches. It ships nothing, so grading it
as an active source reports a system the browser never sees.
"""
import argparse
import fnmatch
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_OK, add_json_flag, emit_json  # noqa: E402

STYLE_EXT = {".css", ".scss", ".sass", ".less"}
MODULE_EXT = {
    ".js", ".jsx", ".ts", ".tsx", ".gjs", ".gts", ".mjs", ".cjs",
    ".vue", ".svelte", ".astro", ".html", ".htm", ".hbs", ".erb",
}
SOURCE_EXT = STYLE_EXT | MODULE_EXT | {".json"}

# @import "a", @use "b" as c, @forward "d", @import url("e"), composes from "f"
IMPORT_RE = re.compile(
    r"""^\s*@(?:import|use|forward)\s+(?:\(\s*[\w\s,]*\s*\)\s+)?(?P<q>['"])(?P<spec>[^'"]+)(?P=q)"""
    r"""|^\s*@import\s+url\(\s*(?P<q2>['"]?)(?P<spec2>[^'")]+)(?P=q2)\s*\)""",
    re.M,
)

# Static JS/TS imports and re-exports. Following source modules matters because
# a route often imports a component which imports its own CSS module.
JS_IMPORT_RE = re.compile(
    r"""^\s*(?:import|export)\s+(?:[^\n\r'";]*?\s+from\s+)?(?P<q>['"])(?P<spec>[^'"]+)(?P=q)""",
    re.M,
)
HTML_SCRIPT_RE = re.compile(
    r"""<script\b[^>]*?src\s*=\s*(?P<q>['"])(?P<spec>[^'"]+)(?P=q)""",
    re.I,
)
HTML_LINK_RE = re.compile(r"<link\b(?P<attrs>[^>]*)>", re.I)
HTML_ATTRIBUTE_RE = re.compile(
    r"""(?P<name>[a-zA-Z:-]+)\s*=\s*(?P<q>['"])(?P<value>[^'"]+)(?P=q)""",
    re.I,
)
STYLE_SRC_RE = re.compile(r"""<style\b[^>]*?src\s*=\s*(?P<q>['"])(?P<spec>[^'"]+)(?P=q)""", re.I)
ANGULAR_STYLE_BLOCK_RE = re.compile(
    r"""\bstyleUrls?\s*:\s*(?P<value>\[[^\]]*\]|['"][^'"]+['"])""", re.S
)
QUOTED_SPEC_RE = re.compile(r"""(?P<q>['"])(?P<spec>[^'"]+)(?P=q)""")
SPROCKETS_RE = re.compile(
    r"""^\s*(?://|/\*+|\*)?\s*=\s*(?P<directive>require_tree|require|link_tree|link_directory|link)\s+(?P<spec>[^\s*]+)""",
    re.M,
)

# Conventional entry points, most specific first. Each entry is
# (glob-ish relative path, what finding it proves).
ENTRY_CONVENTIONS = [
    ("app/globals.css", "Next.js app-router global stylesheet"),
    ("src/app/globals.css", "Next.js app-router global stylesheet"),
    ("app/layout.tsx", "Next.js root layout; styles imported here ship on every route"),
    ("src/app/layout.tsx", "Next.js root layout; styles imported here ship on every route"),
    ("styles/globals.css", "Next.js pages-router global stylesheet"),
    ("src/styles/globals.css", "conventional global stylesheet"),
    ("src/index.css", "Vite or CRA entry stylesheet"),
    ("src/main.css", "conventional entry stylesheet"),
    ("src/index.tsx", "application entry module"),
    ("src/main.tsx", "application entry module"),
    ("src/main.ts", "application entry module"),
    ("app/assets/stylesheets/common.scss", "Rails or Discourse common bundle root"),
    ("app/assets/stylesheets/desktop.scss", "Discourse desktop bundle root"),
    ("app/assets/stylesheets/mobile.scss", "Discourse mobile bundle root"),
    ("app/assets/stylesheets/application.scss", "Sprockets application bundle root"),
    ("app/assets/stylesheets/application.css", "Sprockets application bundle root"),
    ("assets/stylesheets/common.scss", "plugin common bundle root"),
    ("assets/stylesheets/desktop.scss", "plugin desktop bundle root"),
    ("assets/stylesheets/mobile.scss", "plugin mobile bundle root"),
]

DEFAULT_IGNORES = [
    "node_modules", ".git", "dist", "build", ".next", "out", "coverage",
    "vendor", "third_party", "tmp", ".turbo", ".cache",
]
ROOT_ONLY_IGNORES = {"vendor", "third_party"}
ORPHAN_EXCLUDED_PARTS = {
    "test", "tests", "spec", "specs", "fixtures", "snapshots",
    "__fixtures__", "generated",
}

SOURCE_EXTENSION_ORDER = (
    ".ts", ".tsx", ".js", ".jsx", ".gjs", ".gts", ".mjs", ".cjs",
    ".vue", ".svelte", ".astro", ".css", ".scss", ".sass", ".less", ".json",
)


def is_ignored(rel, ignores):
    parts = rel.split(os.sep)
    return any(
        part in ignores and (part not in ROOT_ONLY_IGNORES or index == 0)
        for index, part in enumerate(parts)
    )


def walk_files(root, ignores):
    for dirpath, dirnames, filenames in os.walk(root):
        at_root = os.path.relpath(dirpath, root) == "."
        dirnames[:] = [
            directory for directory in dirnames
            if directory not in ignores or
            (directory in ROOT_ONLY_IGNORES and not at_root)
        ]
        for name in filenames:
            full = os.path.join(dirpath, name)
            yield full, os.path.relpath(full, root)


def matches_pattern(path, pattern):
    path = path.replace(os.sep, "/")
    pattern = pattern.replace(os.sep, "/")
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    return fnmatch.fnmatch(path, pattern) or path.startswith(pattern.rstrip("/") + "/")


def orphan_candidate(path, patterns=None):
    if any(part in ORPHAN_EXCLUDED_PARTS for part in path.split("/")):
        return False
    if patterns is None:
        return True
    return any(matches_pattern(path, pattern) for pattern in patterns)


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def workspace_packages(root):
    """name -> repository-relative dir, for every workspace package.

    A monorepo imports its own packages by name — "shadcn/tailwind.css" —
    and the file lives at packages/shadcn/src/tailwind.css. Without this
    map that import reads as external and the file reads as an orphan,
    which is how a real run found this gap on the day the tool shipped.
    """
    globs = []
    ws = os.path.join(root, "pnpm-workspace.yaml")
    if os.path.isfile(ws):
        for line in read(ws).splitlines():
            m = re.match(r"""\s*-\s*['"]?([^'"#]+?)['"]?\s*$""", line)
            if m and not m.group(1).startswith("!"):
                globs.append(m.group(1).strip())
    pkg = os.path.join(root, "package.json")
    if os.path.isfile(pkg):
        try:
            data = json.loads(read(pkg))
            wsf = data.get("workspaces")
            if isinstance(wsf, dict):
                wsf = wsf.get("packages", [])
            globs.extend(wsf or [])
        except ValueError:
            pass
    out = {}
    for pattern in globs:
        for d in glob.glob(os.path.join(root, pattern)):
            pj = os.path.join(d, "package.json")
            if os.path.isdir(d) and os.path.isfile(pj):
                try:
                    name = json.loads(read(pj)).get("name")
                except ValueError:
                    continue
                if name:
                    out[name] = os.path.relpath(d, root).replace(os.sep, "/")
    return out


def split_package_spec(spec):
    """("@org/pkg", "rest/of/path") or ("pkg", "rest"), or (None, spec)."""
    if spec.startswith("@"):
        parts = spec.split("/", 2)
        if len(parts) >= 2:
            return "/".join(parts[:2]), (parts[2] if len(parts) == 3 else "")
        return None, spec
    parts = spec.split("/", 1)
    return parts[0], (parts[1] if len(parts) == 2 else "")


def strip_comments_preserving_lines(text, line_markers=("//",)):
    """Remove JS/JSON comments without changing strings or line numbers."""
    output = []
    quote = None
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if quote:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            index += 1
            continue
        if character in {'"', "'", "`"}:
            quote = character
            output.append(character)
            index += 1
            continue
        line_marker = next(
            (marker for marker in line_markers
             if marker and text.startswith(marker, index)), None)
        if line_marker:
            output.extend(" " * len(line_marker))
            index += len(line_marker)
            while index < len(text) and text[index] != "\n":
                output.append(" ")
                index += 1
            continue
        if character == "/" and following == "*":
            output.extend("  ")
            index += 2
            while index < len(text):
                if text[index:index + 2] == "*/":
                    output.extend("  ")
                    index += 2
                    break
                output.append("\n" if text[index] == "\n" else " ")
                index += 1
            continue
        output.append(character)
        index += 1
    return "".join(output)


def strip_json_comments(text):
    """Normalize JSONC comments and trailing commas for the JSON parser."""
    text = strip_comments_preserving_lines(text)
    output = []
    quote = None
    escaped = False
    for index, character in enumerate(text):
        if quote:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character == '"':
            quote = character
            output.append(character)
            continue
        if character == ",":
            following = index + 1
            while following < len(text) and text[following].isspace():
                following += 1
            if following < len(text) and text[following] in "}]":
                output.append(" ")
                continue
        output.append(character)
    return "".join(output)


def mask_quoted_spans(text):
    """Blank strings/templates while retaining offsets and line breaks."""
    output = list(text)
    index = 0
    while index < len(text):
        if text[index] not in {'"', "'", "`"}:
            index += 1
            continue
        quote = text[index]
        output[index] = " "
        index += 1
        escaped = False
        while index < len(text):
            character = text[index]
            output[index] = "\n" if character == "\n" else " "
            index += 1
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                break
    return "".join(output)


def configured_aliases(root):
    """Read only aliases the repository explicitly declares."""
    aliases = {}
    for name in ("tsconfig.json", "jsconfig.json"):
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        try:
            data = json.loads(strip_json_comments(read(path)))
        except ValueError:
            continue
        compiler = data.get("compilerOptions", {}) or {}
        base = compiler.get("baseUrl", ".")
        for alias, targets in (compiler.get("paths", {}) or {}).items():
            if not targets:
                continue
            target = targets[0]
            aliases[alias] = os.path.normpath(
                os.path.join(base, target)).replace(os.sep, "/")
    for name in ("vite.config.js", "vite.config.mjs", "vite.config.ts"):
        text = read(os.path.join(root, name))
        for match in re.finditer(
                r"['\"](?P<key>[^'\"]+)['\"]\s*:\s*(?:path\.)?resolve\([^,]+,\s*['\"](?P<target>[^'\"]+)['\"]",
                text):
            aliases[match.group("key")] = match.group("target").lstrip("./")
    return aliases


def apply_alias(spec, aliases):
    for key in sorted((aliases or {}), key=len, reverse=True):
        target = aliases[key]
        if "*" in key:
            before, after = key.split("*", 1)
            if (not spec.startswith(before) or not spec.endswith(after) or
                    len(spec) <= len(before) + len(after)):
                continue
            wildcard = spec[len(before):len(spec) - len(after) if after else None]
            return target.replace("*", wildcard)
        if spec == key:
            return target
    return spec


def apply_rewrites(spec, rewrites):
    destinations = rewrite_destinations(spec, rewrites)
    return destinations[0]["path"] if len(destinations) == 1 else spec


def rewrite_destinations(spec, rewrites):
    destinations = {}
    for rewrite in rewrites or []:
        match = re.match(rewrite["regex"], spec)
        if match:
            try:
                destination = rewrite["replacement"].format(**match.groupdict())
            except (KeyError, ValueError):
                continue
            item = destinations.setdefault(destination, {
                "path": destination, "profiles": [],
            })
            profile = rewrite.get("profile")
            if profile and profile not in item["profiles"]:
                item["profiles"].append(profile)
    return [destinations[key] for key in sorted(destinations)]


def scoped_values(path, contexts):
    """Merge resolver values from broad to importer-specific contexts."""
    matched = []
    for prefix, values in (contexts or {}).items():
        normalized = prefix.strip("/")
        if not normalized or path == normalized or path.startswith(normalized + "/"):
            matched.append((len(normalized), values))
    return [values for _, values in sorted(matched, key=lambda item: item[0])]


def call_import_records(text):
    """Read import()/require() calls while ignoring examples inside strings."""
    records = []
    index = 0
    length = len(text)

    def quoted_end(start):
        quote = text[start]
        cursor = start + 1
        escaped = False
        while cursor < length:
            character = text[cursor]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                return cursor
            cursor += 1
        return length - 1

    while index < length:
        if text[index] in {'"', "'", "`"}:
            index = quoted_end(index) + 1
            continue
        keyword = next(
            (name for name in ("import", "require")
             if text.startswith(name, index) and
             (index == 0 or not (text[index - 1].isalnum() or text[index - 1] in "_$")) and
             (index + len(name) == length or
              not (text[index + len(name)].isalnum() or
                   text[index + len(name)] in "_$"))),
            None,
        )
        if not keyword:
            index += 1
            continue
        cursor = index + len(keyword)
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor >= length or text[cursor] != "(":
            index += len(keyword)
            continue
        cursor += 1
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor < length and text[cursor] in {'"', "'"}:
            end = quoted_end(cursor)
            spec = text[cursor + 1:end]
            after = end + 1
            while after < length and text[after].isspace():
                after += 1
            if after < length and text[after] == ")":
                records.append({"spec": spec, "kind": "import"})
                index = after + 1
                continue
        elif keyword == "import":
            end = text.find(")", cursor)
            if end != -1:
                expression = text[cursor:end].strip()
                records.append({
                    "spec": "<dynamic:%s>" % expression,
                    "kind": "dynamic",
                })
                index = end + 1
                continue
        index += len(keyword)
    return records


def candidate_paths(spec, from_path, packages=None, aliases=None, rewrites=None,
                    load_paths=None):
    """Every repository-relative path a stylesheet spec could mean.

    Every value in and out of here is relative to the repository root.
    Mixing a root-relative path with an absolute one silently resolves
    against the working directory instead, which reads as an unresolved
    import rather than as an error.

    Sass partials resolve with a leading underscore and an implied
    extension, so "tokens" can mean _tokens.scss in the importing file's
    directory. A spec that resolves to nothing is reported, never dropped.
    """
    spec = spec.split("?")[0].split("#")[0].strip()
    if not spec or spec.startswith(("http://", "https://", "//", "data:")):
        return []
    if spec.startswith("~"):
        spec = spec[1:]
    rewritten = apply_rewrites(spec, rewrites)
    aliased = apply_alias(
        rewritten,
        aliases if os.path.splitext(from_path)[1].lower() not in STYLE_EXT else {},
    )
    here = os.path.dirname(from_path)
    importer_is_style = os.path.splitext(from_path)[1].lower() in STYLE_EXT
    bases = []
    if aliased != spec:
        bases.append(os.path.normpath(aliased))
    elif spec.startswith("/"):
        bases.append(os.path.normpath(spec.lstrip("/")))
    elif spec.startswith("."):
        bases.append(os.path.normpath(os.path.join(here, spec)))
    else:
        # A workspace package by name resolves inside that package, and a
        # package commonly keeps its stylesheets under src/. dist/ is not
        # tried: it is build output, ignored by the walk on purpose, and the
        # source that produced it is what gets graded.
        name, rest = split_package_spec(spec)
        if packages and name in packages:
            base = packages[name]
            for sub in ("", "src", "styles", "css"):
                bases.append(os.path.normpath(os.path.join(base, sub, rest)) if rest
                             else os.path.normpath(os.path.join(base, sub, "index")))
        bases.append(os.path.normpath(os.path.join(here, spec)))
        if importer_is_style:
            for prefix in load_paths or []:
                bases.append(os.path.normpath(os.path.join(prefix, spec)))
    out = []
    for base in bases:
        head, tail = os.path.split(base)
        stems = [tail]
        if importer_is_style and not tail.startswith("_"):
            stems.append("_" + tail)
        for stem in stems:
            if os.path.splitext(stem)[1] in SOURCE_EXT:
                out.append(os.path.join(head, stem))
            else:
                extensions = ((".scss", ".css", ".sass", ".less")
                              if importer_is_style else SOURCE_EXTENSION_ORDER)
                for ext in extensions:
                    out.append(os.path.join(head, stem + ext))
                for ext in extensions:
                    out.append(os.path.join(head, stem, "index" + ext))
                if importer_is_style:
                    out.append(os.path.join(head, stem, "_index.scss"))
    return list(dict.fromkeys(p.replace(os.sep, "/") for p in out))


def import_records_in(path, text):
    records = []
    raw_text = text
    text = strip_comments_preserving_lines(text)
    text = re.sub(
        r"<!--.*?-->",
        lambda match: "".join("\n" if char == "\n" else " "
                              for char in match.group(0)),
        text,
        flags=re.S,
    )
    if os.path.splitext(path)[1] in STYLE_EXT:
        for m in IMPORT_RE.finditer(text):
            records.append({"spec": m.group("spec") or m.group("spec2"), "kind": "import"})
    else:
        masked_strings = mask_quoted_spans(text)
        for match in JS_IMPORT_RE.finditer(text):
            masked_match = masked_strings[match.start():match.end()]
            if re.search(r"\b(?:import|export)\b", masked_match):
                records.append({"spec": match.group("spec"), "kind": "import"})
        for pattern in (HTML_SCRIPT_RE, STYLE_SRC_RE):
            for match in pattern.finditer(text):
                records.append({"spec": match.group("spec"), "kind": "import"})
        records.extend(call_import_records(text))
        for match in HTML_LINK_RE.finditer(text):
            attrs = {
                item.group("name").lower(): item.group("value")
                for item in HTML_ATTRIBUTE_RE.finditer(match.group("attrs"))
            }
            href = attrs.get("href")
            rel = attrs.get("rel", "").lower().split()
            style_link = (
                "stylesheet" in rel or attrs.get("as", "").lower() == "style" or
                attrs.get("type", "").lower() == "text/css" or
                (href and os.path.splitext(href.split("?", 1)[0])[1].lower()
                 in STYLE_EXT)
            )
            if href and style_link:
                records.append({"spec": href, "kind": "import"})
        for block in ANGULAR_STYLE_BLOCK_RE.finditer(text):
            for match in QUOTED_SPEC_RE.finditer(block.group("value")):
                records.append({"spec": match.group("spec"), "kind": "import"})
    for match in SPROCKETS_RE.finditer(raw_text):
        directive = match.group("directive")
        records.append({
            "spec": match.group("spec"),
            "kind": "tree" if directive in ("require_tree", "link_tree", "link_directory") else "import",
            "directive": directive,
        })
    unique = []
    seen = set()
    for record in records:
        key = (record["spec"], record["kind"], record.get("directive"))
        if record["spec"] and key not in seen:
            unique.append(record)
            seen.add(key)
    return unique


def imports_in(path, text):
    return [record["spec"] for record in import_records_in(path, text)]


def unresolved_reason(spec, packages):
    """Classify a miss without claiming an external dependency is local."""
    if spec.startswith(("http://", "https://", "//", "data:")):
        return "remote dependency"
    if spec.startswith("sass:"):
        return "framework built-in"
    if spec.startswith("<dynamic:"):
        return "dynamic runtime import"
    name, _ = split_package_spec(spec.lstrip("~"))
    if not spec.startswith((".", "/")) and (not packages or name not in packages):
        return "external package"
    return "missing local source"


def candidate_directories(spec, from_path):
    spec = spec.strip().strip("'\"")
    here = os.path.dirname(from_path)
    if spec.startswith((".", "/")):
        return [os.path.normpath(os.path.join(here, spec.lstrip("/"))).replace(os.sep, "/")]
    return [
        os.path.normpath(os.path.join(here, spec)).replace(os.sep, "/"),
        os.path.normpath(spec).replace(os.sep, "/"),
    ]


def detect_roots(root, ignores):
    found = []
    for rel, why in ENTRY_CONVENTIONS:
        full = os.path.join(root, rel)
        if os.path.isfile(full):
            found.append({"path": rel.replace(os.sep, "/"), "detected_by": why})
    # A monorepo puts the same conventions one or two levels down.
    if not found:
        for full, rel in walk_files(root, ignores):
            base = os.path.basename(rel)
            if base in ("globals.css", "common.scss", "application.scss", "index.css"):
                found.append({
                    "path": rel.replace(os.sep, "/"),
                    "detected_by": "conventional entry filename found by search",
                })
    return found


def build(root, entries=None, ignores=None, aliases=None, orphan_patterns=None,
          rewrites=None, alias_contexts=None, rewrite_contexts=None,
          load_paths=None, load_path_contexts=None):
    root = os.path.abspath(root)
    ignores = set(ignores or DEFAULT_IGNORES)

    all_files = {rel.replace(os.sep, "/") for _, rel in walk_files(root, ignores)}
    style_files = {f for f in all_files if os.path.splitext(f)[1] in STYLE_EXT}
    packages = workspace_packages(root)
    declared_aliases = configured_aliases(root)
    declared_aliases.update(aliases or {})

    if entries is not None:
        roots = [{"path": e.replace(os.sep, "/"), "detected_by": "given on the command line"}
                 for e in entries]
    else:
        roots = detect_roots(root, ignores)

    reachable = {}
    unresolved = []
    queue = []
    for r in roots:
        if r["path"] in all_files:
            reachable[r["path"]] = {"depth": 0, "via": []}
            queue.append((r["path"], 0, [r["path"]]))
        else:
            unresolved.append({"from": None, "spec": r["path"], "reason": "entry point does not exist"})

    while queue:
        current, depth, chain = queue.pop(0)
        text = read(os.path.join(root, current))
        current_aliases = dict(declared_aliases)
        for scoped_aliases in scoped_values(current, alias_contexts):
            current_aliases.update(scoped_aliases)
        current_rewrites = list(rewrites or [])
        for scoped_rewrites in scoped_values(current, rewrite_contexts):
            current_rewrites.extend(scoped_rewrites)
        current_load_paths = list(load_paths or [])
        for scoped_load_paths in scoped_values(current, load_path_contexts):
            current_load_paths.extend(scoped_load_paths)
        for record in import_records_in(current, text):
            spec = record["spec"]
            if record["kind"] == "dynamic":
                unresolved.append({
                    "from": current, "spec": spec,
                    "reason": "dynamic runtime import",
                })
                continue
            if record["kind"] == "tree":
                hits = []
                for directory in candidate_directories(spec, current):
                    prefix = directory.rstrip("/") + "/"
                    hits.extend(path for path in all_files
                                if path.startswith(prefix) and
                                os.path.splitext(path)[1].lower() in SOURCE_EXT)
                if not hits and record.get("directive", "").startswith("link"):
                    continue
                if not hits:
                    unresolved.append({
                        "from": current, "spec": spec,
                        "reason": "missing local source",
                    })
                    continue
                for hit in sorted(set(hits)):
                    if hit not in reachable:
                        reachable[hit] = {"depth": depth + 1, "via": chain}
                        queue.append((hit, depth + 1, chain + [hit]))
                continue
            rewrite_options = rewrite_destinations(spec, current_rewrites)
            if len(rewrite_options) > 1:
                unresolved.append({
                    "from": current, "spec": spec,
                    "reason": "ambiguous profile rewrite",
                    "candidates": rewrite_options,
                })
                continue
            hit = None
            for cand in candidate_paths(
                    spec, current, packages, current_aliases, current_rewrites,
                    current_load_paths):
                if cand in all_files:
                    hit = cand
                    break
            if hit is None:
                unresolved.append({
                    "from": current, "spec": spec,
                    "reason": unresolved_reason(spec, packages),
                })
                continue
            if hit not in reachable:
                reachable[hit] = {"depth": depth + 1, "via": chain}
                queue.append((hit, depth + 1, chain + [hit]))

    orphan_pool = {
        path for path in style_files
        if orphan_candidate(path, orphan_patterns)
    }
    orphans = sorted(orphan_pool - set(reachable))
    return {
        "workspace_packages": packages,
        "aliases": declared_aliases,
        "alias_contexts": alias_contexts or {},
        "load_paths": load_paths or [],
        "load_path_contexts": load_path_contexts or {},
        "roots": roots,
        "reachable": {k: reachable[k] for k in sorted(reachable)},
        "unresolved": unresolved,
        "orphans": orphans,
        "files_scanned": len(all_files),
        "style_files": len(style_files),
    }


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root")
    ap.add_argument("--entry", action="append", default=[])
    ap.add_argument("--ignore", action="append", default=[])
    add_json_flag(ap)
    args = ap.parse_args(argv)

    graph = build(args.root, args.entry or None, DEFAULT_IGNORES + args.ignore)
    if args.json_out:
        emit_json(args.json_out, graph)
        print("wrote %s — %d root(s), %d reachable, %d orphan stylesheet(s)"
              % (args.json_out, len(graph["roots"]), len(graph["reachable"]), len(graph["orphans"])))
    else:
        print(json.dumps(graph, indent=2, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
