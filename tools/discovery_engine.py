#!/usr/bin/env python3
"""Universal discovery engine composed from executable framework profiles."""
import fnmatch
import glob
import json
import os
import subprocess

import framework_profiles
import import_graph
import profile_extractors


CONFIDENCE_RANK = {
    "blocked": 0, "static candidate": 1, "import-graph verified": 2,
    "framework-registered": 3, "runtime verified": 4,
}
ROOT_SEED_CONFIDENCE = {
    "framework-registered", "runtime verified", "import-graph verified",
}


def repository_ref(root):
    try:
        result = subprocess.run(
            ["git", "-C", root, "rev-parse", "--short=12", "HEAD"],
            check=True, capture_output=True, text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def exists(root, path):
    return os.path.exists(os.path.join(root, path))


def evidence(claim, kind, path, matched, confidence, line=None,
             method="repository inspection", artifact_needed=None,
             profiles=None):
    return {
        "claim": claim, "kind": kind, "path": path, "line": line,
        "matched": matched, "method": method, "confidence": confidence,
        "reachable_from": [], "artifact_needed": artifact_needed,
        "profiles": profiles or [],
    }


def root_type(path, declared=None):
    known = {
        "common", "desktop", "mobile", "admin", "theme", "route",
        "component", "lazy", "manifest", "template", "demo",
    }
    if declared in known:
        return declared
    low = path.lower()
    for kind in ("desktop", "mobile", "admin", "theme"):
        if kind in low:
            return kind
    return "common"


def pattern_matches(path, pattern):
    normalized = path.replace(os.sep, "/")
    pattern = pattern.replace(os.sep, "/")
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return normalized == prefix or normalized.startswith(prefix + "/")
    return (fnmatch.fnmatch(normalized, pattern) or
            normalized.startswith(pattern.rstrip("/") + "/"))


def ownership_for(path, owned_patterns, default="unknown"):
    if owned_patterns:
        return ("owned" if any(pattern_matches(path, pattern)
                                for pattern in owned_patterns) else "unknown")
    return default


def prefix_path(path, prefix):
    if not prefix:
        return path.replace(os.sep, "/")
    return os.path.join(prefix, path).replace(os.sep, "/")


def inferred_owned_patterns(roots, scope_prefix=""):
    if scope_prefix:
        return [scope_prefix.rstrip("/") + "/**"]
    patterns = set()
    for item in roots:
        path = item.get("path", "")
        if "/" in path:
            patterns.add(path.split("/", 1)[0] + "/**")
        elif path:
            patterns.add(path)
    return sorted(patterns)


def prefixed_aliases(scope_root, prefix):
    aliases = import_graph.configured_aliases(scope_root)
    if not prefix:
        return aliases
    return {key: prefix_path(value, prefix) for key, value in aliases.items()}


def profile_ledger(active, prefix=""):
    ledger = []
    for match in active:
        for item in match.get("evidence", []):
            ledger.append(evidence(
                match["claim"], "profile-detection",
                prefix_path(item["path"], prefix), item.get("matched"),
                match["confidence"], line=item.get("line"),
                method="framework profile", profiles=[match["id"]],
            ))
    return ledger


def merge_items(items, key="path"):
    merged = {}
    for item in items:
        identifier = item.get(key)
        if not identifier:
            continue
        if identifier not in merged:
            merged[identifier] = dict(item)
            merged[identifier]["profiles"] = list(item.get("profiles", []))
            continue
        current = merged[identifier]
        current["profiles"] = sorted(
            set(current.get("profiles", [])) | set(item.get("profiles", [])))
        if CONFIDENCE_RANK.get(item.get("confidence"), -1) > CONFIDENCE_RANK.get(
                current.get("confidence"), -1):
            preserved_profiles = current["profiles"]
            current.update(item)
            current["profiles"] = preserved_profiles
        if current.get("ownership") != "owned" and item.get("ownership") == "owned":
            current["ownership"] = "owned"
    return [merged[name] for name in sorted(merged)]


def compact_match(item, prefix=""):
    return {
        "id": item["id"], "kind": item["kind"],
        "adapter": item["adapter"], "activation": item["activation"],
        "confidence": item["confidence"], "score": item["score"],
        "evidence": [dict(ev, path=prefix_path(ev["path"], prefix))
                     for ev in item.get("evidence", [])],
        "missing_signals": item.get("missing_signals", []),
    }


def merge_compact_match(target, item):
    target["score"] = max(target.get("score", 0), item.get("score", 0))
    target["evidence"] = list({
        json.dumps(evidence_item, sort_keys=True): evidence_item
        for evidence_item in target.get("evidence", []) + item.get("evidence", [])
    }.values())
    target["missing_signals"] = list({
        json.dumps(signal, sort_keys=True): signal
        for signal in target.get("missing_signals", []) +
        item.get("missing_signals", [])
    }.values())
    return target


def next_step(capability, state):
    if state == "verified":
        return {
            "detection": "Use every active profile; do not choose only the most specific one.",
            "production_roots": "Traverse every owned product root and keep supplemental surfaces separate.",
            "import_resolution": "Continue token discovery from the resolved graph; keep external imports classified.",
            "token_source_discovery": "Classify and deduplicate reachable token declarations.",
            "ownership": "Keep unknown and demo roots visible outside owned grading scope.",
            "mode_resolution": "Compare every declared bundle and scheme.",
            "runtime_verification": "Record the inspected build or runtime artifact.",
        }[capability]
    return {
        "detection": "Confirm a production framework or explicit profile.",
        "production_roots": "Confirm the application entry point or select a monorepo app.",
        "import_resolution": "Resolve or explicitly exempt every missing local, unsupported, or dynamic import.",
        "token_source_discovery": "Run discover_tokens.py after reachability is established.",
        "ownership": "Pass --owned patterns or confirm the authored application boundary.",
        "mode_resolution": "Provide resolved output for every declared bundle and scheme.",
        "runtime_verification": "Provide a local build, preview, Storybook or browser artifact.",
    }[capability]


def capability_ladder(capabilities, active_ids, roots, graph, ownership,
                      mode_resolution, profile_contributions=None,
                      actionable_unresolved=None,
                      missing_registered_roots=None):
    profile_contributions = profile_contributions or {}
    actionable_unresolved = actionable_unresolved or []
    missing_registered_roots = missing_registered_roots or []
    evidence_by_capability = {
        "detection": active_ids,
        "production_roots": [root["path"] for root in roots[:8]],
        "import_resolution": [
            "%d reachable source files" % len(graph.get("reachable", {})),
            "%d actionable unresolved imports" % len(actionable_unresolved),
        ],
        "token_source_discovery": [],
        "ownership": (ownership.get("owned_patterns", []) or
                      ownership.get("inferred_owned_roots", [])[:8]),
        "mode_resolution": [pair.get("artifact")
                            for pair in mode_resolution.get("resolved_pairs", [])
                            if pair.get("artifact")],
        "runtime_verification": [],
    }
    limitations = {
        "detection": (None if capabilities.get("detection") == "verified" else
                      "No framework profile matched."),
        "production_roots": (
            "%d framework-registered product roots are missing from disk." %
            len(missing_registered_roots)
            if missing_registered_roots else
            (None if roots else "No product root was proven.")
        ),
        "import_resolution": (
            "%d local, dynamic, or unsupported imports still block completeness." %
            len(actionable_unresolved)
            if actionable_unresolved else
            ("%d external or framework imports remain classified; none blocks the local graph." %
             len(graph.get("unresolved", [])) if graph.get("unresolved") else None)
        ),
        "token_source_discovery": "Token candidates have not yet been classified by discover_tokens.py.",
        "ownership": None if ownership.get("owned_patterns") else "No explicit owned patterns were supplied.",
        "mode_resolution": mode_resolution.get("blocked_reason"),
        "runtime_verification": "No build, preview or browser artifact was inspected.",
    }
    return {
        "order": framework_profiles.CAPABILITIES,
        "steps": [{
            "capability": name,
            "state": capabilities[name],
            "contributors": (
                profile_contributions[name]["profiles"]
                if name in profile_contributions else
                (active_ids if name != "ownership" else
                 [ownership.get("basis", "unmeasured")])
            ),
            "evidence": (
                profile_contributions[name].get("evidence", [])
                if name in profile_contributions else
                evidence_by_capability[name]
            ),
            "limitation": (
                profile_contributions[name].get("limitation")
                if name in profile_contributions else limitations[name]
            ),
            "next_step": (
                profile_contributions[name].get("next_step")
                if name in profile_contributions else
                next_step(name, capabilities[name])
            ),
        } for name in framework_profiles.CAPABILITIES],
    }


def discover(root, owned_patterns=None, profile_ids=None, app_root=None,
             profile_files=None):
    root = os.path.abspath(root)
    owned_patterns = owned_patterns or []
    registry = framework_profiles.load_registry(profile_files)
    definitions = {item["id"]: item for item in registry["profiles"]}
    root_active, root_candidates = framework_profiles.match_profiles(
        root, registry, profile_ids)
    root_primary = [
        item for item in root_active
        if item["kind"] not in ("structure", "supplemental") and
        any(root_hint.get("exists") and
            root_hint.get("confidence") in ROOT_SEED_CONFIDENCE
            for root_hint in (
                framework_profiles.expand_hints(
                    root, "", definitions[item["id"]], "roots") +
                profile_extractors.extract(
                    root, "", definitions[item["id"]])
            ))
    ]
    applications = framework_profiles.application_candidates(root, registry)
    selection = {
        "requested": app_root, "selected": None,
        "state": "root-application", "reason": None,
    }
    scope_prefix = ""
    if app_root:
        requested_path = os.path.abspath(os.path.join(root, app_root))
        try:
            inside_root = os.path.commonpath((root, requested_path)) == root
        except ValueError:
            inside_root = False
        if not inside_root:
            raise ValueError("selected application escapes repository: %s" % app_root)
        scope_prefix = os.path.relpath(requested_path, root).replace(os.sep, "/")
        if scope_prefix == "." or not os.path.isdir(requested_path):
            raise ValueError("selected application does not exist: %s" % app_root)
        selection.update({"selected": scope_prefix, "state": "selected"})
    elif any(item["id"] == "monorepo" for item in root_active) and not root_primary:
        if len(applications) == 1:
            scope_prefix = applications[0]["path"]
            selection.update({
                "selected": scope_prefix, "state": "auto-selected",
                "reason": "one application candidate",
            })
        elif len(applications) > 1:
            selection.update({
                "state": "blocked",
                "reason": "multiple application candidates; rerun with --app",
            })

    contexts = [(root, "", root_active, root_candidates)]
    embedded_applications = []
    if root_primary:
        embedded_patterns = [
            pattern
            for match in root_primary
            for pattern in definitions[match["id"]].get(
                "embedded_applications", [])
        ]
        embedded_paths = []
        for pattern in embedded_patterns:
            embedded_paths.extend(
                path for path in glob.glob(os.path.join(root, pattern))
                if os.path.isdir(path)
            )
        application_by_path = {item["path"]: item for item in applications}
        for embedded_root in sorted(set(embedded_paths)):
                embedded_path = os.path.relpath(
                    embedded_root, root).replace(os.sep, "/")
                embedded_active, embedded_candidates = (
                    framework_profiles.match_profiles(
                        embedded_root, registry, profile_ids
                    )
                )
                if not embedded_active:
                    continue
                application = application_by_path.get(embedded_path, {
                    "path": embedded_path,
                    "package": None,
                    "markers": ["profile-declared embedded application"],
                    "profiles": [item["id"] for item in embedded_active],
                })
                if embedded_path not in application_by_path:
                    applications.append(application)
                    application_by_path[embedded_path] = application
                embedded_applications.append(application)
                contexts.append((
                    embedded_root, embedded_path,
                    embedded_active, embedded_candidates,
                ))
    if scope_prefix:
        scope_root = os.path.join(root, scope_prefix)
        scoped_active, scoped_candidates = framework_profiles.match_profiles(
            scope_root, registry, profile_ids)
        contexts.append((scope_root, scope_prefix, scoped_active, scoped_candidates))

    active_by_id = {}
    candidate_by_id = {}
    active_instances = []
    ledger = []
    for scope_root, prefix, active, candidates in contexts:
        ledger.extend(profile_ledger(active, prefix))
        for item in active:
            active_instances.append((item, scope_root, prefix))
            if item["id"] not in active_by_id:
                active_by_id[item["id"]] = item
        for item in candidates:
            compact = compact_match(item, prefix)
            if item["id"] in candidate_by_id:
                merge_compact_match(candidate_by_id[item["id"]], compact)
            else:
                candidate_by_id[item["id"]] = compact
    active = sorted(
        active_by_id.values(), key=lambda item: (-item["priority"], item["id"]))
    active_ids = [item["id"] for item in active]
    if not active:
        ledger.append(evidence(
            "Unknown environment", "fallback", ".",
            "no framework profile matched", "blocked",
            artifact_needed="confirmed production entry point",
            profiles=["generic"],
        ))

    roots = []
    surface_roots = []
    component_roots = []
    for match, scope_root, prefix in active_instances:
        profile = definitions[match["id"]]
        for item in framework_profiles.expand_hints(
                scope_root, prefix, profile, "roots"):
            item["root_type"] = root_type(item["path"], item.get("root_type"))
            item["scope"] = item.get("scope", "product")
            item["ownership"] = ownership_for(
                item["path"], owned_patterns,
                item.get("ownership", "unknown"))
            roots.append(item)
        for item in framework_profiles.expand_hints(
                scope_root, prefix, profile, "surface_roots"):
            item["root_type"] = root_type(item["path"], item.get("root_type"))
            item["ownership"] = (
                "demo" if item.get("scope") == "demo" else
                ownership_for(item["path"], owned_patterns, "unknown")
            )
            surface_roots.append(item)
        for item in framework_profiles.expand_hints(
                scope_root, prefix, profile, "component_roots", directories=True):
            item["ownership"] = ownership_for(
                item["path"], owned_patterns,
                item.get("ownership", "unknown"))
            component_roots.append(item)
        for item in profile_extractors.extract(scope_root, prefix, profile):
            item["root_type"] = root_type(item["path"], item.get("root_type"))
            item["ownership"] = ownership_for(
                item["path"], owned_patterns,
                item.get("ownership", "unknown"))
            roots.append(item)

    if selection["state"] != "blocked":
        conventional_root = os.path.join(root, scope_prefix) if scope_prefix else root
        for item in import_graph.detect_roots(
                conventional_root, import_graph.DEFAULT_IGNORES):
            path = prefix_path(item["path"], scope_prefix)
            roots.append({
                "path": path, "root_type": root_type(path),
                "detected_by": item["detected_by"],
                "evidence": item["detected_by"],
                "confidence": "static candidate",
                "ownership": ownership_for(
                    path, owned_patterns,
                    "owned" if path.startswith(("app/", "src/")) else "unknown"),
                "scope": "product", "profile": "convention",
                "profiles": ["convention"], "exists": True,
            })

    root_records = merge_items(roots)
    surface_roots = merge_items(surface_roots)
    component_root_records = merge_items(component_roots)
    component_roots = [item for item in component_root_records
                       if item.get("ownership") == "owned"]
    component_root_candidates = [item for item in component_root_records
                                 if item.get("ownership") != "owned"]
    seed_roots = [
        item for item in root_records
        if item.get("exists") and item.get("scope") == "product" and
        item.get("confidence") in ROOT_SEED_CONFIDENCE
    ]
    aliases = {}
    alias_contexts = {}
    for context_root, context_prefix, _, _ in contexts:
        context_aliases = prefixed_aliases(context_root, context_prefix)
        if context_prefix:
            alias_contexts[context_prefix] = context_aliases
        else:
            aliases.update(context_aliases)
    rewrites = []
    rewrite_contexts = {}
    load_paths = []
    load_path_contexts = {}
    for match, _, prefix in active_instances:
        profile = definitions[match["id"]]
        for rewrite in profile.get("import_rewrites", []):
            item = dict(rewrite)
            item["profile"] = match["id"]
            item["replacement"] = prefix_path(item["replacement"], prefix)
            if prefix:
                rewrite_contexts.setdefault(prefix, []).append(item)
            else:
                rewrites.append(item)
        profile_load_paths = [
            prefix_path(path, prefix) for path in profile.get("load_paths", [])
        ]
        if prefix:
            load_path_contexts.setdefault(prefix, []).extend(profile_load_paths)
        else:
            load_paths.extend(profile_load_paths)
    graph = import_graph.build(
        root, [item["path"] for item in seed_roots], aliases=aliases,
        rewrites=rewrites, alias_contexts=alias_contexts,
        rewrite_contexts=rewrite_contexts, load_paths=load_paths,
        load_path_contexts=load_path_contexts)
    surface_roots = [
        item for item in surface_roots
        if item.get("path") not in graph.get("reachable", {})
    ]
    for item in root_records:
        if (item["path"] in graph["reachable"] and
                item.get("confidence") == "static candidate"):
            item["confidence"] = "import-graph verified"
    product_roots = [
        item for item in root_records
        if item.get("exists") and item.get("scope") == "product" and
        item.get("confidence") in ROOT_SEED_CONFIDENCE
    ]
    root_candidates = [
        item for item in root_records
        if item.get("exists") and item.get("scope") == "product" and
        item.get("confidence") == "static candidate"
    ]
    owned_roots = [item for item in product_roots
                   if item.get("ownership") == "owned"]
    owned_seed_roots = [item for item in seed_roots
                        if item.get("ownership") == "owned"]
    inferred_patterns = inferred_owned_patterns(owned_roots, scope_prefix)
    owned_graph = import_graph.build(
        root, [item["path"] for item in owned_seed_roots], aliases=aliases,
        orphan_patterns=(owned_patterns or inferred_patterns),
        rewrites=rewrites, alias_contexts=alias_contexts,
        rewrite_contexts=rewrite_contexts, load_paths=load_paths,
        load_path_contexts=load_path_contexts)
    graph["roots"] = product_roots
    owned_graph["roots"] = owned_seed_roots

    ownership = {
        "owned_patterns": owned_patterns,
        "basis": ("user-supplied scope" if owned_patterns else
                  ("framework profile" if owned_roots else "unmeasured")),
        "inferred_owned_roots": ([] if owned_patterns else
                                 [item["path"] for item in owned_roots]),
        "inferred_owned_patterns": ([] if owned_patterns else inferred_patterns),
        "unknown_roots": [item["path"] for item in product_roots
                          if item.get("ownership") == "unknown"],
        "demo_roots": [item["path"] for item in surface_roots
                       if item.get("ownership") == "demo"],
    }
    profile_contributions = {}
    state_rank = {"verified": 0, "unmeasured": 1, "blocked": 2}
    for profile_id in active_ids:
        for capability, contribution in definitions[profile_id].get(
                "capability_contributions", {}).items():
            if capability not in profile_contributions:
                profile_contributions[capability] = {
                    "profiles": [], "evidence": [],
                    "states": [],
                    "state": contribution["state"],
                    "limitation": contribution.get("limitation"),
                    "next_step": contribution.get("next_step"),
                }
            merged = profile_contributions[capability]
            if state_rank[contribution["state"]] > state_rank[merged["state"]]:
                merged["state"] = contribution["state"]
                merged["limitation"] = contribution.get("limitation")
                merged["next_step"] = contribution.get("next_step")
            merged["profiles"].append(profile_id)
            merged["states"].append(contribution["state"])
            merged["evidence"].extend(contribution.get("evidence", []))
    capability_conflicts = [
        {
            "capability": capability,
            "profiles": contribution["profiles"],
            "states": sorted(set(contribution["states"])),
            "resolution": "most conservative state",
        }
        for capability, contribution in profile_contributions.items()
        if len(set(contribution["states"])) > 1
    ]
    rewrite_conflicts = [
        item for item in graph.get("unresolved", [])
        if item.get("reason") == "ambiguous profile rewrite"
    ]
    if rewrite_conflicts:
        profiles = sorted({
            profile
            for conflict in rewrite_conflicts
            for candidate in conflict.get("candidates", [])
            for profile in candidate.get("profiles", [])
        })
        existing = next((
            item for item in capability_conflicts
            if item["capability"] == "import_resolution"
        ), None)
        resolution = "%d ambiguous profile rewrite(s) blocked" % len(
            rewrite_conflicts)
        if existing:
            existing["profiles"] = sorted(set(existing["profiles"] + profiles))
            existing["states"] = sorted(set(existing["states"] + ["blocked"]))
            existing["resolution"] += "; " + resolution
        else:
            capability_conflicts.append({
                "capability": "import_resolution", "profiles": profiles,
                "states": ["blocked"], "resolution": resolution,
            })
    mode_contribution = profile_contributions.get("mode_resolution")
    mode_resolution = {
        "audited_pairs": [], "resolved_pairs": [],
        "mechanisms": (
            mode_contribution.get("evidence", []) if mode_contribution else []),
        "blocked_reason": (
            mode_contribution.get("limitation") if mode_contribution else
            "No declared mode mechanism or resolved output was inspected."
        ),
    }
    actionable_reasons = {
        "missing local source", "unsupported resolver", "dynamic runtime import",
        "ambiguous profile rewrite",
    }
    actionable_unresolved = [
        item for item in graph.get("unresolved", [])
        if item.get("reason") in actionable_reasons
    ]
    missing_registered_roots = [
        item for item in root_records if not item.get("exists")
    ]
    capabilities = {
        "detection": "verified" if active else "blocked",
        "production_roots": (
            "verified" if product_roots and not missing_registered_roots else
            "blocked"
        ),
        "import_resolution": (
            "blocked" if actionable_unresolved else
            ("verified" if graph["reachable"] else "blocked")
        ),
        "token_source_discovery": "unmeasured",
        "ownership": "verified" if owned_roots else "unmeasured",
        "mode_resolution": "unmeasured",
        "runtime_verification": "unmeasured",
    }
    for capability, contribution in profile_contributions.items():
        if state_rank[contribution["state"]] > state_rank[capabilities[capability]]:
            capabilities[capability] = contribution["state"]
    ladder = capability_ladder(
        capabilities, active_ids or ["generic"], product_roots, graph, ownership,
        mode_resolution, profile_contributions, actionable_unresolved,
        missing_registered_roots)
    adapters = []
    for item in active:
        if item["adapter"] not in adapters:
            adapters.append(item["adapter"])
    if not adapters:
        adapters = ["references/adapters/generic.md"]
    composition = {
        "schema_version": registry["schema_version"],
        "registry": "assets/framework-profiles.json",
        "registry_sources": registry.get("_sources", []),
        "active": [],
        "candidates": sorted(
            candidate_by_id.values(), key=lambda item: (-item["score"], item["id"])),
        "order": active_ids,
        "application_candidates": applications,
        "embedded_applications": embedded_applications,
        "application_selection": selection,
        "conflicts": capability_conflicts,
    }
    for item in active:
        instances = [instance for instance in active_instances
                     if instance[0]["id"] == item["id"]]
        compact = compact_match(instances[0][0], instances[0][2])
        compact["contexts"] = [prefix or "." for _, _, prefix in instances]
        for instance, _, prefix in instances[1:]:
            merge_compact_match(compact, compact_match(instance, prefix))
        composition["active"].append(compact)
    return {
        "engine": {"name": "universal-profile-engine", "schema_version": 1},
        "repository": {"root": root, "ref": repository_ref(root)},
        "environment": active_ids or ["unknown"],
        "adapters": adapters,
        "detected_by": [item["path"] for item in ledger],
        "confidence": [item["confidence"] for item in ledger],
        "profile_composition": composition,
        "profile_guidance": {item["id"]: item["guidance"] for item in active},
        "capabilities": capabilities,
        "capability_ladder": ladder,
        "evidence": ledger,
        "roots": product_roots,
        "root_candidates": root_candidates,
        "surface_roots": surface_roots,
        "component_roots": component_roots,
        "component_root_candidates": component_root_candidates,
        "import_graph": graph,
        "owned_import_graph": owned_graph,
        "ownership": ownership,
        "missing_registered_roots": missing_registered_roots,
        "mode_resolution": mode_resolution,
    }
