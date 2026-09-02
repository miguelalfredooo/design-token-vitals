#!/usr/bin/env python3
"""Discover environment layers, production style roots, and evidence.

Framework profiles teach this tool where to look. The output stays universal:
the same capability and confidence fields describe Discourse, Next.js, Rails,
Vite, a monorepo, or an unknown application.
"""
import argparse
import fnmatch
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_OK, add_json_flag, emit_json  # noqa: E402
import import_graph  # noqa: E402
import discovery_engine  # noqa: E402


ADAPTERS = {
    "discourse": "references/adapters/discourse.md",
    "rails-sprockets": "references/adapters/rails-sprockets.md",
    "nextjs": "references/adapters/nextjs.md",
    "vite": "references/adapters/vite.md",
    "storybook": "references/adapters/storybook.md",
    "monorepo": "references/adapters/monorepo.md",
}

REGISTER_RE = re.compile(
    r"register_(?P<api>asset|css)\s*(?:\(\s*)?['\"](?P<spec>[^'\"]+)['\"]"
    r"(?:\s*,\s*:(?P<kind>[a-zA-Z0-9_-]+))?"
)


def exists(root, path):
    return os.path.exists(os.path.join(root, path))


def evidence(claim, kind, path, matched, confidence, line=None,
             method="repository inspection", artifact_needed=None):
    return {
        "claim": claim,
        "kind": kind,
        "path": path,
        "line": line,
        "matched": matched,
        "method": method,
        "confidence": confidence,
        "reachable_from": [],
        "artifact_needed": artifact_needed,
    }


def detect_layers(root):
    layers = []
    ev = []

    discourse_layout = exists(root, "app/assets/stylesheets") and exists(root, "plugins")
    discourse_theme = False
    if discourse_layout:
        for rel in ("app/assets/stylesheets/color_definitions.scss",
                    "app/assets/stylesheets/common/foundation/variables.scss"):
            if exists(root, rel):
                text = import_graph.read(os.path.join(root, rel))
                if "schemeType(" in text or "dark-light-choose(" in text:
                    discourse_theme = True
                    ev.append(evidence("Discourse theme mechanism", "theme-structure", rel,
                                       "schemeType() or dark-light-choose()", "framework-registered"))
                    break
        if not discourse_theme:
            for full, rel in import_graph.walk_files(root, import_graph.DEFAULT_IGNORES):
                if rel.endswith(".scss"):
                    text = import_graph.read(full)
                    if "dark-light-choose(" in text or "$light-theme-" in text:
                        discourse_theme = True
                        ev.append(evidence("Discourse theme mechanism", "theme-structure", rel,
                                           "dark/light Sass mechanism", "framework-registered"))
                        break
    if discourse_layout and discourse_theme:
        layers.append("discourse")
        ev.append(evidence("Discourse application layout", "theme-structure", "plugins/",
                           "plugins beside app/assets/stylesheets", "framework-registered"))

    if exists(root, "Gemfile") and exists(root, "app/assets/stylesheets"):
        layers.append("rails-sprockets")
        ev.append(evidence("Rails asset layer", "manifest", "Gemfile",
                           "Gemfile with app/assets/stylesheets", "static candidate"))
    if any(exists(root, p) for p in ("next.config.js", "next.config.mjs", "next.config.ts")):
        layers.append("nextjs")
        path = next(p for p in ("next.config.js", "next.config.mjs", "next.config.ts") if exists(root, p))
        ev.append(evidence("Next.js application", "build-config", path,
                           "next.config.*", "framework-registered"))
    if any(exists(root, p) for p in ("vite.config.js", "vite.config.ts", "vite.config.mjs")):
        layers.append("vite")
        path = next(p for p in ("vite.config.js", "vite.config.ts", "vite.config.mjs") if exists(root, p))
        ev.append(evidence("Vite application", "build-config", path,
                           "vite.config.*", "framework-registered"))
    if exists(root, ".storybook"):
        layers.append("storybook")
        ev.append(evidence("Storybook supplemental surface", "build-config", ".storybook/",
                           "Storybook configuration", "static candidate"))
    if any(exists(root, p) for p in ("pnpm-workspace.yaml", "turbo.json")):
        layers.append("monorepo")
        path = "pnpm-workspace.yaml" if exists(root, "pnpm-workspace.yaml") else "turbo.json"
        ev.append(evidence("Workspace layout", "manifest", path,
                           "workspace configuration", "framework-registered"))
    if not layers:
        layers.append("unknown")
        ev.append(evidence("Unknown environment", "fallback", ".",
                           "no framework profile matched", "blocked",
                           artifact_needed="confirmed production entry point"))
    return layers, ev


def root_type(path, declared=None):
    if declared in ("desktop", "mobile", "admin"):
        return declared
    low = path.lower()
    for kind in ("desktop", "mobile", "admin", "theme"):
        if kind in low:
            return kind
    return "common"


def discourse_roots(root, owned_patterns):
    roots = []
    for rel, kind, proof in (
        ("app/assets/stylesheets/color_definitions.scss", "theme", "Discourse core color-definition bundle"),
        ("app/assets/stylesheets/common/foundation/variables.scss", "theme", "Discourse injects this foundation into every theme CSS file"),
        ("app/assets/stylesheets/admin.scss", "admin", "Discourse core admin bundle"),
    ):
        if exists(root, rel):
            roots.append({
                "path": rel, "root_type": kind,
                "detected_by": "Discourse core bundle convention",
                "evidence": proof,
                "confidence": "static candidate", "ownership": "owned",
                "exists": True,
            })
    plugin_dir = os.path.join(root, "plugins")
    if not os.path.isdir(plugin_dir):
        return roots
    for name in sorted(os.listdir(plugin_dir)):
        plugin_rb = os.path.join(plugin_dir, name, "plugin.rb")
        if not os.path.isfile(plugin_rb):
            continue
        rel_plugin = "plugins/%s" % name
        ownership = "owned" if any(fnmatch.fnmatch(rel_plugin, p.rstrip("/")) for p in owned_patterns) else "unknown"
        for lineno, line in enumerate(import_graph.read(plugin_rb).splitlines(), 1):
            match = REGISTER_RE.search(line)
            if not match:
                continue
            spec = match.group("spec")
            if os.path.splitext(spec)[1] not in import_graph.STYLE_EXT:
                continue
            rel = os.path.join(rel_plugin, "assets", spec).replace(os.sep, "/")
            roots.append({
                "path": rel,
                "root_type": root_type(rel, match.group("kind")),
                "detected_by": "%s:%d" % (os.path.join(rel_plugin, "plugin.rb"), lineno),
                "evidence": "register_%s %s" % (match.group("api"), spec),
                "confidence": "framework-registered",
                "ownership": ownership,
                "exists": exists(root, rel),
            })
    return roots


def discover(root, owned_patterns=None, profile_ids=None, app_root=None,
             profile_files=None):
    return discovery_engine.discover(
        root, owned_patterns, profile_ids, app_root, profile_files)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--owned", action="append", default=[])
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument("--profile-file", action="append", default=[])
    parser.add_argument("--app")
    add_json_flag(parser)
    args = parser.parse_args(argv)
    result = discover(
        args.root, args.owned, args.profile, args.app, args.profile_file)
    emit_json(args.json_out, result)
    print("detected %s — %d profile(s), %d roots, %d reachable, %d unresolved" % (
        " + ".join(result["environment"]),
        len(result["profile_composition"]["active"]), len(result["roots"]),
        len(result["import_graph"]["reachable"]), len(result["import_graph"]["unresolved"])))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
