#!/usr/bin/env python3
"""Load, validate and evaluate composable framework discovery profiles."""
import glob
import hashlib
import json
import os
import re
import string

import profile_extractors


CAPABILITIES = [
    "detection", "production_roots", "import_resolution",
    "token_source_discovery", "ownership", "mode_resolution",
    "runtime_verification",
]
CONFIDENCE = {
    "framework-registered", "import-graph verified", "static candidate",
    "runtime verified", "blocked",
}
CAPABILITY_STATES = {"verified", "unmeasured", "blocked"}
SIGNAL_TYPES = {
    "path_any", "content_any", "package_dependency_any", "package_json_key",
}
PROFILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "framework-profiles.json",
)
IGNORED_PARTS = {
    ".git", ".next", ".nuxt", ".svelte-kit", "node_modules", "vendor",
    "dist", "build", "out", "coverage", "tmp", ".turbo", ".cache",
    "test", "tests", "spec", "specs", "fixtures", "snapshots",
}


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def formatter_fields(value):
    return {
        field_name
        for _, field_name, _, _ in string.Formatter().parse(value)
        if field_name
    }


def file_digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_registry(registry):
    errors = []
    if registry.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if registry.get("capability_order") != CAPABILITIES:
        errors.append("capability_order must match the universal ladder")
    seen = set()
    for profile in registry.get("profiles", []):
        profile_id = profile.get("id")
        if not profile_id:
            errors.append("profile without id")
            continue
        if profile_id in seen:
            errors.append("duplicate profile id %s" % profile_id)
        seen.add(profile_id)
        for field in ("kind", "priority", "adapter", "detection", "guidance"):
            if field not in profile:
                errors.append("%s missing %s" % (profile_id, field))
        if ("embedded_applications" in profile and
                (not isinstance(profile["embedded_applications"], list) or
                 not all(isinstance(item, str) and item
                         for item in profile["embedded_applications"]))):
            errors.append("%s embedded_applications must be path patterns" % profile_id)
        contributions = profile.get("capability_contributions", {})
        if not isinstance(contributions, dict):
            errors.append("%s capability_contributions must be an object" % profile_id)
            contributions = {}
        for capability, contribution in contributions.items():
            if capability not in CAPABILITIES:
                errors.append("%s contributes unknown capability %s" % (
                    profile_id, capability))
                continue
            if (not isinstance(contribution, dict) or
                    contribution.get("state") not in CAPABILITY_STATES):
                errors.append("%s has invalid %s contribution" % (
                    profile_id, capability))
                continue
            if (contribution["state"] != "verified" and
                    not contribution.get("limitation")):
                errors.append("%s %s contribution lacks a limitation" % (
                    profile_id, capability))
            evidence = contribution.get("evidence")
            if (not isinstance(evidence, list) or not evidence or
                    not all(isinstance(item, str) and item for item in evidence)):
                errors.append("%s %s contribution requires string evidence" % (
                    profile_id, capability))
            if not contribution.get("next_step"):
                errors.append("%s %s contribution lacks a next step" % (
                    profile_id, capability))
        rewrites = profile.get("import_rewrites", [])
        if not isinstance(rewrites, list):
            errors.append("%s import_rewrites must be a list" % profile_id)
            rewrites = []
        for rewrite in rewrites:
            if not isinstance(rewrite, dict) or not rewrite.get("replacement"):
                errors.append("%s import rewrite is malformed" % profile_id)
                continue
            try:
                expression = re.compile(rewrite.get("regex", ""))
            except re.error as error:
                errors.append("%s import rewrite is invalid: %s" % (
                    profile_id, error))
                continue
            try:
                fields = {
                    field_name
                    for _, field_name, _, _ in string.Formatter().parse(
                        rewrite["replacement"])
                    if field_name
                }
            except ValueError as error:
                errors.append("%s import rewrite replacement is invalid: %s" % (
                    profile_id, error))
                continue
            missing_fields = fields - set(expression.groupindex)
            if missing_fields:
                errors.append(
                    "%s import rewrite references unknown groups: %s" % (
                        profile_id, ", ".join(sorted(missing_fields))))
        load_paths = profile.get("load_paths", [])
        if (not isinstance(load_paths, list) or
                not all(isinstance(item, str) and item for item in load_paths)):
            errors.append("%s load_paths must be path strings" % profile_id)
        extractors = profile.get("extractors", [])
        if not isinstance(extractors, list):
            errors.append("%s extractors must be a list" % profile_id)
            extractors = []
        for extractor in extractors:
            if not isinstance(extractor, dict):
                errors.append("%s extractor must be an object" % profile_id)
                continue
            extractor_type = extractor.get("type")
            if extractor_type not in profile_extractors.EXTRACTOR_TYPES:
                errors.append("%s has unsupported extractor %s" % (
                    profile_id, extractor_type))
                continue
            if (not extractor.get("files") or
                    not all(isinstance(item, str) and item
                            for item in extractor.get("files", []))):
                errors.append("%s %s extractor requires file patterns" % (
                    profile_id, extractor_type))
            if (not isinstance(extractor.get("evidence"), str) or
                    not extractor.get("evidence")):
                errors.append("%s %s extractor requires evidence" % (
                    profile_id, extractor_type))
            if ("style_only" in extractor and
                    not isinstance(extractor["style_only"], bool)):
                errors.append("%s %s extractor style_only must be boolean" % (
                    profile_id, extractor_type))
            if ("strip_prefixes" in extractor and
                    (not isinstance(extractor["strip_prefixes"], list) or
                     not all(isinstance(item, str) and item
                             for item in extractor["strip_prefixes"]))):
                errors.append("%s %s extractor has invalid strip_prefixes" % (
                    profile_id, extractor_type))
            if ("line_comments" in extractor and
                    (not isinstance(extractor["line_comments"], list) or
                     not all(isinstance(item, str) and item
                             for item in extractor["line_comments"]))):
                errors.append("%s %s extractor has invalid line_comments" % (
                    profile_id, extractor_type))
            if extractor.get("confidence", "framework-registered") not in CONFIDENCE:
                errors.append("%s %s extractor has invalid confidence" % (
                    profile_id, extractor_type))
            if extractor.get("ownership", "unknown") not in {"owned", "unknown"}:
                errors.append("%s %s extractor has invalid ownership" % (
                    profile_id, extractor_type))
            if extractor.get("scope", "product") != "product":
                errors.append("%s %s extractor must emit product roots" % (
                    profile_id, extractor_type))
            if extractor_type == "regex_roots":
                expression = None
                try:
                    expression = re.compile(extractor.get("regex", ""))
                    if extractor.get("spec_group", "spec") not in expression.groupindex:
                        errors.append("%s regex extractor requires its spec group" % profile_id)
                except re.error as error:
                    errors.append("%s regex extractor is invalid: %s" % (
                        profile_id, error))
                if expression is not None:
                    root_type_group = extractor.get("root_type_group")
                    if (root_type_group and
                            root_type_group not in expression.groupindex):
                        errors.append(
                            "%s regex extractor has unknown root_type_group %s" %
                            (profile_id, root_type_group))
                    allowed_fields = set(expression.groupindex) | {
                        "spec", "file", "file_dir",
                    }
                    for field_name in ("path_template", "evidence"):
                        value = extractor.get(
                            field_name, "{spec}" if field_name == "path_template" else "")
                        if not isinstance(value, str):
                            errors.append("%s regex extractor %s must be a string" %
                                          (profile_id, field_name))
                            continue
                        try:
                            unknown = formatter_fields(value) - allowed_fields
                        except ValueError as error:
                            errors.append("%s regex extractor %s is invalid: %s" %
                                          (profile_id, field_name, error))
                            continue
                        if unknown:
                            errors.append(
                                "%s regex extractor %s references unknown groups: %s" %
                                (profile_id, field_name,
                                 ", ".join(sorted(unknown))))
            if (extractor_type == "config_array_roots" and
                    (not isinstance(extractor.get("key"), str) or
                     not extractor.get("key"))):
                errors.append("%s config array extractor requires key" % profile_id)
            if extractor_type == "config_array_roots":
                try:
                    unknown = formatter_fields(extractor.get("evidence", "")) - {
                        "spec", "key",
                    }
                except ValueError as error:
                    errors.append("%s config array evidence is invalid: %s" %
                                  (profile_id, error))
                else:
                    if unknown:
                        errors.append(
                            "%s config array evidence references unknown fields: %s" %
                            (profile_id, ", ".join(sorted(unknown))))
            if extractor_type == "json_build_roots":
                for field_name in ("target_names", "entry_keys"):
                    if (field_name in extractor and
                            (not isinstance(extractor[field_name], list) or
                             not all(isinstance(item, str) and item
                                     for item in extractor[field_name]))):
                        errors.append("%s JSON build extractor has invalid %s" %
                                      (profile_id, field_name))
                if ("style_key" in extractor and
                        (not isinstance(extractor["style_key"], str) or
                         not extractor["style_key"])):
                    errors.append("%s JSON build extractor has invalid style_key" %
                                  profile_id)
        detection = profile.get("detection", {})
        if detection.get("confidence") not in CONFIDENCE:
            errors.append("%s has invalid detection confidence" % profile_id)
        for group in ("required", "supporting"):
            for signal in detection.get(group, []):
                if signal.get("type") not in SIGNAL_TYPES:
                    errors.append("%s has unsupported %s signal" % (
                        profile_id, signal.get("type")))
        guidance = profile.get("guidance", {})
        for capability in CAPABILITIES[1:]:
            if not guidance.get(capability):
                errors.append("%s missing %s guidance" % (profile_id, capability))
        for group in ("roots", "component_roots", "surface_roots"):
            for hint in profile.get(group, []):
                if not hint.get("patterns") or not hint.get("evidence"):
                    errors.append("%s %s hint lacks patterns or evidence" % (
                        profile_id, group))
                if hint.get("confidence") not in CONFIDENCE:
                    errors.append("%s %s hint has invalid confidence" % (
                        profile_id, group))
    if errors:
        raise ValueError("invalid framework profile registry: " + "; ".join(errors))
    return registry


def load_registry(extra_paths=None):
    registry = read_json(PROFILE_PATH)
    sources = [{
        "path": "assets/framework-profiles.json",
        "sha256": file_digest(PROFILE_PATH),
    }]
    profiles = {item["id"]: item for item in registry.get("profiles", [])}
    for path in extra_paths or []:
        extra = read_json(path)
        sources.append({
            "path": os.path.abspath(path),
            "sha256": file_digest(path),
        })
        for item in extra.get("profiles", []):
            profiles[item["id"]] = item
    registry["profiles"] = sorted(
        profiles.values(), key=lambda item: (-item.get("priority", 0), item["id"])
    )
    registry["_sources"] = sources
    return validate_registry(registry)


def clean_path(path):
    path = path.replace(os.sep, "/")
    return path[2:] if path.startswith("./") else path


def excluded(path):
    return any(part in IGNORED_PARTS for part in clean_path(path).split("/"))


class Probe(object):
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self._glob = {}
        self._text = {}
        self._package = None

    def paths(self, patterns):
        key = tuple(patterns)
        if key not in self._glob:
            found = []
            for pattern in patterns:
                for path in glob.glob(os.path.join(self.root, pattern), recursive=True):
                    rel = clean_path(os.path.relpath(path, self.root))
                    if not excluded(rel):
                        found.append(rel)
            self._glob[key] = sorted(set(found))
        return self._glob[key]

    def text(self, path):
        if path not in self._text:
            try:
                with open(os.path.join(self.root, path), encoding="utf-8",
                          errors="replace") as handle:
                    self._text[path] = handle.read()
            except OSError:
                self._text[path] = ""
        return self._text[path]

    def package(self):
        if self._package is None:
            path = os.path.join(self.root, "package.json")
            try:
                self._package = read_json(path)
            except (OSError, ValueError):
                self._package = {}
        return self._package

    def signal(self, signal):
        signal_type = signal.get("type")
        if signal_type == "path_any":
            paths = self.paths(signal.get("patterns", []))
            if paths:
                return {"type": signal_type, "path": paths[0],
                        "matched": "existing path"}
        elif signal_type == "content_any":
            for path in self.paths(signal.get("patterns", [])):
                text = self.text(path)
                for needle in signal.get("contains", []):
                    offset = text.find(needle)
                    if offset >= 0:
                        return {
                            "type": signal_type, "path": path,
                            "line": text.count("\n", 0, offset) + 1,
                            "matched": needle,
                        }
        elif signal_type == "package_dependency_any":
            package = self.package()
            dependencies = {}
            for field in ("dependencies", "devDependencies", "peerDependencies"):
                dependencies.update(package.get(field, {}) or {})
            for name in signal.get("packages", []):
                if name in dependencies:
                    return {"type": signal_type, "path": "package.json",
                            "matched": "%s dependency" % name}
        elif signal_type == "package_json_key":
            key = signal.get("key")
            if key in self.package():
                return {"type": signal_type, "path": "package.json",
                        "matched": "%s key" % key}
        return None


def match_profile(profile, probe, forced=False):
    detection = profile["detection"]
    required = [(signal, probe.signal(signal))
                for signal in detection.get("required", [])]
    supporting = [(signal, probe.signal(signal))
                  for signal in detection.get("supporting", [])]
    required_ok = all(result is not None for _, result in required)
    supporting_hits = [result for _, result in supporting if result is not None]
    minimum = detection.get("minimum_supporting", 0)
    natural_match = required_ok and len(supporting_hits) >= minimum
    total = len(required) + max(minimum, len(supporting))
    hits = sum(result is not None for _, result in required) + len(supporting_hits)
    evidence = [result for _, result in required + supporting if result is not None]
    missing = []
    for signal, result in required:
        if result is None:
            missing.append(signal)
    if len(supporting_hits) < minimum:
        missing.extend(signal for signal, result in supporting if result is None)
    return {
        "id": profile["id"],
        "kind": profile["kind"],
        "priority": profile["priority"],
        "adapter": profile["adapter"],
        "active": natural_match or forced,
        "activation": "user-selected" if forced and not natural_match else "detected",
        "confidence": (detection["confidence"] if natural_match else "static candidate"),
        "claim": detection["claim"],
        "score": 1.0 if total == 0 and natural_match else round(hits / float(total or 1), 3),
        "evidence": evidence,
        "missing_signals": missing,
        "guidance": profile["guidance"],
    }


def match_profiles(root, registry, forced=None):
    forced = set(forced or [])
    profiles = {item["id"]: item for item in registry["profiles"]}
    unknown = sorted(forced - set(profiles))
    if unknown:
        raise ValueError("unknown framework profile(s): %s" % ", ".join(unknown))
    probe = Probe(root)
    results = [match_profile(profile, probe, profile["id"] in forced)
               for profile in registry["profiles"]]
    active = [item for item in results if item["active"]]
    candidates = [item for item in results if not item["active"] and item["score"] > 0]
    return active, sorted(candidates, key=lambda item: (-item["score"], -item["priority"], item["id"]))


def prefixed(path, prefix):
    return clean_path(os.path.join(prefix, path)) if prefix else clean_path(path)


def expand_hints(root, prefix, profile, field, directories=False):
    probe = Probe(root)
    output = []
    for hint in profile.get(field, []):
        for path in probe.paths(hint["patterns"]):
            full = os.path.join(root, path)
            if directories and not os.path.isdir(full):
                continue
            if not directories and not os.path.isfile(full):
                continue
            item = {key: value for key, value in hint.items() if key != "patterns"}
            item.update({
                "path": prefixed(path, prefix),
                "profile": profile["id"],
                "profiles": [profile["id"]],
                "detected_by": "framework profile: %s" % profile["id"],
                "exists": True,
            })
            output.append(item)
    return output


def workspace_globs(root):
    patterns = []
    pnpm = os.path.join(root, "pnpm-workspace.yaml")
    try:
        with open(pnpm, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip().lstrip("-").strip().strip("'\"")
                if stripped and not stripped.startswith(("packages:", "!", "#")):
                    patterns.append(stripped)
    except OSError:
        pass
    try:
        package = read_json(os.path.join(root, "package.json"))
        workspaces = package.get("workspaces", [])
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("packages", [])
        patterns.extend(workspaces or [])
    except (OSError, ValueError):
        pass
    if os.path.isdir(os.path.join(root, "apps")):
        patterns.append("apps/*")
    return sorted(set(pattern for pattern in patterns if pattern and not pattern.startswith("!")))


def application_candidates(root, registry=None):
    registry = registry or load_registry()
    definitions = {item["id"]: item for item in registry["profiles"]}
    candidates = []
    markers = (
        "next.config.js", "next.config.mjs", "next.config.ts", "vite.config.js",
        "vite.config.ts", "svelte.config.js", "svelte.config.ts", "nuxt.config.js",
        "nuxt.config.ts", "astro.config.mjs", "astro.config.ts", "angular.json",
        "ember-cli-build.js", "remix.config.js", "remix.config.ts",
    )
    for pattern in workspace_globs(root):
        for directory in glob.glob(os.path.join(root, pattern)):
            if not os.path.isdir(directory):
                continue
            rel = clean_path(os.path.relpath(directory, root))
            package_path = os.path.join(directory, "package.json")
            package_name = None
            try:
                package_name = read_json(package_path).get("name")
            except (OSError, ValueError):
                pass
            found_markers = [name for name in markers if os.path.exists(os.path.join(directory, name))]
            active, _ = match_profiles(directory, registry)
            application_profiles = []
            for match in active:
                if match["kind"] in ("structure", "supplemental"):
                    continue
                profile = definitions[match["id"]]
                roots = (expand_hints(directory, "", profile, "roots") +
                         profile_extractors.extract(directory, "", profile))
                if any(root.get("exists") and
                       root.get("confidence") in {
                           "framework-registered", "import-graph verified",
                           "runtime verified",
                       } for root in roots):
                    application_profiles.append(match["id"])
            if application_profiles:
                candidates.append({
                    "path": rel,
                    "package": package_name,
                    "markers": found_markers,
                    "profiles": application_profiles,
                })
    unique = {item["path"]: item for item in candidates}
    return [unique[path] for path in sorted(unique)]
