#!/usr/bin/env python3
"""Build the stylesheet import graph for a repository.

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
import glob
import json
import os
import re
import sys

STYLE_EXT = {".css", ".scss", ".sass", ".less"}

# @import "a", @use "b" as c, @forward "d", @import url("e"), composes from "f"
IMPORT_RE = re.compile(
    r"""^\s*@(?:import|use|forward)\s+(?:\(\s*[\w\s,]*\s*\)\s+)?(?P<q>['"])(?P<spec>[^'"]+)(?P=q)"""
    r"""|^\s*@import\s+url\(\s*(?P<q2>['"]?)(?P<spec2>[^'")]+)(?P=q2)\s*\)""",
    re.M,
)

# import "./x.css" / import x from "./x.css" — a JS or TS entry pulling styles
JS_STYLE_IMPORT_RE = re.compile(
    r"""^\s*import\s+(?:[^'";]*\s+from\s+)?(?P<q>['"])(?P<spec>[^'"]+\.(?:css|scss|sass|less))(?P=q)""",
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


def is_ignored(rel, ignores):
    parts = rel.split(os.sep)
    return any(part in ignores for part in parts)


def walk_files(root, ignores):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ignores]
        for name in filenames:
            full = os.path.join(dirpath, name)
            yield full, os.path.relpath(full, root)


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


def candidate_paths(spec, from_path, packages=None):
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
    here = os.path.dirname(from_path)
    bases = []
    if spec.startswith((".", "/")):
        bases.append(os.path.normpath(os.path.join(here, spec.lstrip("/"))))
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
        bases.append(os.path.normpath(spec))
        for prefix in ("app/assets/stylesheets", "assets/stylesheets", "src", "styles"):
            bases.append(os.path.normpath(os.path.join(prefix, spec)))
    out = []
    for base in bases:
        head, tail = os.path.split(base)
        stems = [tail, "_" + tail] if not tail.startswith("_") else [tail]
        for stem in stems:
            if os.path.splitext(stem)[1] in STYLE_EXT:
                out.append(os.path.join(head, stem))
            else:
                for ext in (".scss", ".css", ".sass", ".less"):
                    out.append(os.path.join(head, stem + ext))
                out.append(os.path.join(head, stem, "index.scss"))
                out.append(os.path.join(head, stem, "_index.scss"))
    return [p.replace(os.sep, "/") for p in out]


def imports_in(path, text):
    specs = []
    if os.path.splitext(path)[1] in STYLE_EXT:
        for m in IMPORT_RE.finditer(text):
            specs.append(m.group("spec") or m.group("spec2"))
    else:
        for m in JS_STYLE_IMPORT_RE.finditer(text):
            specs.append(m.group("spec"))
    return [s for s in specs if s]


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


def build(root, entries=None, ignores=None):
    root = os.path.abspath(root)
    ignores = set(ignores or DEFAULT_IGNORES)

    all_files = {rel.replace(os.sep, "/") for _, rel in walk_files(root, ignores)}
    style_files = {f for f in all_files if os.path.splitext(f)[1] in STYLE_EXT}
    packages = workspace_packages(root)

    if entries:
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
        for spec in imports_in(current, text):
            hit = None
            for cand in candidate_paths(spec, current, packages):
                if cand in all_files:
                    hit = cand
                    break
            if hit is None:
                unresolved.append({
                    "from": current, "spec": spec,
                    "reason": "no file in the repository matches this spec",
                })
                continue
            if hit not in reachable:
                reachable[hit] = {"depth": depth + 1, "via": chain}
                queue.append((hit, depth + 1, chain + [hit]))

    orphans = sorted(style_files - set(reachable))
    return {
        "workspace_packages": packages,
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
    ap.add_argument("--json", dest="out")
    args = ap.parse_args(argv)

    graph = build(args.root, args.entry or None, DEFAULT_IGNORES + args.ignore)
    text = json.dumps(graph, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print("wrote %s — %d root(s), %d reachable, %d orphan stylesheet(s)"
              % (args.out, len(graph["roots"]), len(graph["reachable"]), len(graph["orphans"])))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
