#!/usr/bin/env python3
"""Execute validated, declarative root extractors from framework profiles."""
import glob
import json
import os
import re

import import_graph


EXTRACTOR_TYPES = {
    "regex_roots", "config_array_roots", "json_build_roots",
}


def clean(path):
    path = path.replace(os.sep, "/")
    return path[2:] if path.startswith("./") else path


def files(root, patterns):
    found = []
    for pattern in patterns:
        for path in glob.glob(os.path.join(root, pattern), recursive=True):
            if os.path.isfile(path):
                found.append(path)
    return sorted(set(found))


def safe_relative(root, value):
    """Return a repository-relative path, rejecting URLs and path escapes."""
    if not isinstance(value, str):
        return None
    value = value.strip().split("?", 1)[0].split("#", 1)[0]
    if (not value or value.startswith(("http:", "https:", "//", "data:")) or
            "${" in value or "#{" in value):
        return None
    candidate = os.path.normpath(os.path.join(root, value))
    try:
        if os.path.commonpath((os.path.abspath(root), os.path.abspath(candidate))) != os.path.abspath(root):
            return None
    except ValueError:
        return None
    return clean(os.path.relpath(candidate, root))


def item(root, prefix, profile, extractor, local, detected_by, evidence,
         root_type=None):
    for alias_prefix in extractor.get("strip_prefixes", []):
        if local.startswith(alias_prefix):
            local = local[len(alias_prefix):]
            break
    local = safe_relative(root, local)
    if local is None:
        return None
    path = clean(os.path.join(prefix, local)) if prefix else local
    return {
        "path": path,
        "root_type": root_type or extractor.get("root_type", "common"),
        "detected_by": detected_by,
        "evidence": evidence,
        "confidence": extractor.get("confidence", "framework-registered"),
        "ownership": extractor.get("ownership", "unknown"),
        "scope": extractor.get("scope", "product"),
        "profile": profile["id"],
        "profiles": [profile["id"]],
        "exists": os.path.isfile(os.path.join(root, local)),
    }


def regex_roots(root, prefix, profile, extractor):
    output = []
    expression = re.compile(extractor["regex"], re.M | re.S)
    for full in files(root, extractor["files"]):
        source = clean(os.path.relpath(full, root))
        text = import_graph.strip_comments_preserving_lines(
            import_graph.read(full), tuple(extractor.get(
                "line_comments", ["//"])))
        for match in expression.finditer(text):
            groups = match.groupdict()
            spec = groups.get(extractor.get("spec_group", "spec"))
            if not spec:
                continue
            if (extractor.get("style_only") and
                    os.path.splitext(spec)[1].lower() not in import_graph.STYLE_EXT):
                continue
            values = dict(groups)
            values.update({
                "spec": spec,
                "file": source,
                "file_dir": os.path.dirname(source),
            })
            try:
                local = extractor.get("path_template", "{spec}").format(**values)
                evidence = extractor["evidence"].format(**values)
            except (KeyError, ValueError):
                continue
            kind = groups.get(extractor.get("root_type_group", ""))
            line = text.count("\n", 0, match.start()) + 1
            found = item(
                root, prefix, profile, extractor, local,
                "%s:%d" % (clean(os.path.join(prefix, source)), line),
                evidence, kind,
            )
            if found:
                output.append(found)
    return output


def config_array_roots(root, prefix, profile, extractor):
    output = []
    key = re.escape(extractor["key"])
    block = re.compile(r"\b%s\s*:\s*\[(?P<value>.*?)\]" % key, re.S)
    quoted = re.compile(r"""(?P<q>['"])(?P<spec>[^'"]+)(?P=q)""")
    for full in files(root, extractor["files"]):
        source = clean(os.path.relpath(full, root))
        text = import_graph.strip_comments_preserving_lines(
            import_graph.read(full), tuple(extractor.get(
                "line_comments", ["//"])))
        for match in block.finditer(text):
            for value in quoted.finditer(match.group("value")):
                spec = value.group("spec")
                if (extractor.get("style_only", True) and
                        os.path.splitext(spec)[1].lower() not in import_graph.STYLE_EXT):
                    continue
                line = text.count("\n", 0, match.start() + value.start()) + 1
                try:
                    evidence = extractor["evidence"].format(
                        spec=spec, key=extractor["key"])
                except (KeyError, ValueError):
                    evidence = extractor["evidence"]
                found = item(
                    root, prefix, profile, extractor, spec,
                    "%s:%d" % (clean(os.path.join(prefix, source)), line),
                    evidence,
                )
                if found:
                    output.append(found)
    return output


def json_build_roots(root, prefix, profile, extractor):
    output = []
    for full in files(root, extractor["files"]):
        source = clean(os.path.relpath(full, root))
        try:
            with open(full, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        for project_name, project in (data.get("projects", {}) or {}).items():
            targets = project.get("architect") or project.get("targets") or {}
            for target_name, target in targets.items():
                if target_name not in extractor.get("target_names", ["build"]):
                    continue
                options = target.get("options", {}) or {}
                candidates = []
                for key in extractor.get("entry_keys", ["main", "browser"]):
                    if isinstance(options.get(key), str):
                        candidates.append((options[key], "common"))
                        break
                for value in options.get(extractor.get("style_key", "styles"), []) or []:
                    spec = value.get("input") if isinstance(value, dict) else value
                    if isinstance(spec, str):
                        candidates.append((spec, "theme"))
                for spec, kind in candidates:
                    found = item(
                        root, prefix, profile, extractor, spec,
                        "%s:projects.%s.%s.options" % (
                            clean(os.path.join(prefix, source)), project_name, target_name),
                        extractor["evidence"], kind,
                    )
                    if found:
                        output.append(found)
    return output


HANDLERS = {
    "regex_roots": regex_roots,
    "config_array_roots": config_array_roots,
    "json_build_roots": json_build_roots,
}


def extract(root, prefix, profile):
    output = []
    for extractor in profile.get("extractors", []):
        output.extend(HANDLERS[extractor["type"]](
            root, prefix, profile, extractor))
    return output
