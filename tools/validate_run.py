#!/usr/bin/env python3
"""Fail an audit that cannot support what it claims.

    python3 tools/validate_run.py .token-vitals/report.json [--html report.html]

Seventeen rules, from the framework-aware discovery and actionable-report
designs. Each one describes a report that looks finished and is not, and
every one of them has produced a plausible-looking report at some point.
Exit status is 1 when any rule fails, 2 on bad arguments — see tools/cli.py.

These run as code rather than as prose the agent checks itself against,
because a rule the run re-derives each time is a rule that drifts.
"""
import argparse
import base64
import binascii
import datetime
import hashlib
import html as html_tools
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_FINDING, EXIT_OK, add_json_flag, emit_json  # noqa: E402
from adoption_strategy import (  # noqa: E402
    CONSTRAINT_IDS,
    PHASE_IDS,
    STANDARDS,
    derive as derive_adoption_strategy,
)
from findings import collect_ids, is_automatable  # noqa: E402
from analyze_component_usage import build_roadmap  # noqa: E402
from discover_tokens import (  # noqa: E402
    MAX_EMBEDDED_FONT_BYTES,
    concrete_color_value,
    concrete_font_family,
    declarations,
    identity_summary,
    identity_context,
    matching_font_asset_evidence,
    normalize,
    subject_namespace_evidence,
    verified_font_file,
)
from render_discovery import (  # noqa: E402
    INVENTORY_TABS_SCRIPT,
    REPORT_VIEWS,
    REPORT_VIEW_SECTIONS,
    confirmed_definition_count,
    enrich,
    next_step_items,
    normalized_concepts,
    unresolved_import_summary,
)
from render_component_usage import (  # noqa: E402
    LOCATION_PREVIEW_LIMIT,
    grouped_locations,
)

from taxonomy import FAMILIES  # noqa: E402
from version import describe  # noqa: E402

ACTIVE_CLASSES = {"canonical", "alias"}
MEASURE_STATES = {"measured", "unmeasured", "absent"}


class Failure(object):
    def __init__(self, rule, message, detail=None):
        self.rule = rule
        self.message = message
        self.detail = detail or []


def get(doc, *path, **kw):
    cur = doc
    for key in path:
        if not isinstance(cur, dict):
            return kw.get("default")
        cur = cur.get(key)
    return cur if cur is not None else kw.get("default")


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


VALIDATION_BANNER_SLOT = re.compile(
    r'(<!-- SLOT:validation-banner -->).*?(<!-- /SLOT:validation-banner -->)', re.S)


def stamp_pass(report_json_path, doc, report_html_path, report_html_text):
    """Record that THIS report_json, byte for byte, passed the gate just now.

    Called only after `validate` returns no failures. Writes
    provenance.validation_gate into the JSON and clears the report.html
    banner — the one field a report generator must never set itself, so a
    report that was never actually gated cannot claim otherwise by copying
    a passing report's JSON shape.
    """
    checked_at = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    doc.setdefault("provenance", {})["validation_gate"] = {
        "passed": True, "exit_code": 0, "checked_at": checked_at,
    }
    with open(report_json_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")

    if report_html_path and report_html_text is not None:
        ok_note = (
            '<div class="validation-ok">&#10003; Validated &mdash; '
            'all 18 rules passed %s</div>' % html_tools.escape(checked_at)
        )
        stamped = VALIDATION_BANNER_SLOT.sub(
            lambda m: m.group(1) + ok_note + m.group(2), report_html_text, count=1)
        if stamped != report_html_text:
            with open(report_html_path, "w", encoding="utf-8") as fh:
                fh.write(stamped)
    return checked_at


def rule_1_discovery_evidence(doc):
    """One presumed token file, with nothing showing how it was found."""
    sources = get(doc, "discovery", "token_sources", default=None)
    if sources is None:
        sources = get(doc, "stack", "token_sources", default=[]) or []
    if not sources:
        return Failure("1-discovery-evidence",
                       "no token sources recorded at all")
    detected = get(doc, "discovery", "detected_by")
    graph = get(doc, "discovery", "import_graph", default={}) or {}
    roots = graph.get("roots") or []
    if len(sources) == 1 and not roots:
        return Failure(
            "1-discovery-evidence",
            "one token source, and no import-graph roots recorded to show it was discovered",
            ["source: %s" % json.dumps(sources[0])],
        )
    if not detected and not roots:
        return Failure("1-discovery-evidence",
                       "neither discovery.detected_by nor an import graph is recorded")
    return None


def rule_2_reachability(doc):
    """A source inventoried without a path to an owned production root."""
    sources = get(doc, "discovery", "token_sources", default=[]) or []
    bad = []
    for src in sources:
        if not isinstance(src, dict):
            bad.append({"path": src, "why": "source recorded without a classification"})
            continue
        cls = src.get("classification")
        if cls in ACTIVE_CLASSES and not src.get("reachable_from"):
            bad.append({"path": src.get("path"), "why": "classified %s with no reachable_from" % cls})
        if cls not in ACTIVE_CLASSES | {"consumer", "generated", "unverified"}:
            bad.append({"path": src.get("path"), "why": "unknown classification %r" % cls})
    if bad:
        return Failure("2-reachability",
                       "%d source(s) inventoried without a path to an owned entry point" % len(bad),
                       ["%s — %s" % (b["path"], b["why"]) for b in bad[:8]])
    return None


def rule_3_mode_resolution(doc):
    """Complete mode coverage claimed without resolved output per bundle and scheme."""
    grade = get(doc, "vitals", "mode-completeness", "grade")
    if grade not in ("pass", "attention", "fail"):
        return None
    resolution = get(doc, "discovery", "mode_resolution", default=None)
    if resolution is not None:
        audited = resolution.get("audited_pairs") or []
        resolved = resolution.get("resolved_pairs") or []
        if not audited:
            return Failure("3-mode-resolution",
                           "mode-completeness graded %r with no bundle x scheme pairs audited" % grade)
        resolved_keys = {(p.get("bundle"), p.get("mode")) for p in resolved
                         if isinstance(p, dict) and p.get("artifact")}
        missing = [p for p in audited if (p.get("bundle"), p.get("mode")) not in resolved_keys]
        if missing:
            return Failure("3-mode-resolution",
                           "mode-completeness graded %r while %d bundle x scheme pair(s) lack resolved output"
                           % (grade, len(missing)),
                           ["%s / %s" % (p.get("bundle"), p.get("mode")) for p in missing[:8]])
        return None
    schemes = get(doc, "declared", "modes", default=[]) or []
    resolved = get(doc, "discovery", "resolved_modes", default=None)
    if resolved is None:
        return Failure("3-mode-resolution",
                       "mode-completeness graded %r with no discovery.resolved_modes recorded" % grade)
    missing = [s for s in schemes if s not in resolved]
    if missing:
        return Failure("3-mode-resolution",
                       "mode-completeness graded %r while %d declared scheme(s) have no resolved output"
                       % (grade, len(missing)),
                       ["no resolved output for: %s" % ", ".join(missing)])
    return None


DISCOVERY_CONFIDENCE = {
    "framework-registered", "import-graph verified", "static candidate",
    "runtime verified", "blocked",
}
CAPABILITY_STATES = {"verified", "unmeasured", "blocked"}
UNRESOLVED_REASONS = {
    "entry point does not exist", "framework built-in", "remote dependency",
    "external package or unsupported resolver", "external package",
    "dynamic runtime import", "ambiguous profile rewrite",
    "unsupported resolver", "missing local source",
}


def rule_10_root_evidence(doc):
    """Universal discovery roots must carry type, evidence, confidence, and ownership."""
    environments = get(doc, "discovery", "environment")
    if not isinstance(environments, list):
        return None  # legacy schema
    roots = get(doc, "discovery", "import_graph", "roots", default=[]) or []
    bad = []
    for root in roots:
        if not isinstance(root, dict):
            bad.append("root is not an object")
            continue
        label = root.get("path") or "?"
        for field in ("root_type", "evidence", "confidence", "ownership"):
            if not root.get(field):
                bad.append("%s: missing %s" % (label, field))
        if root.get("confidence") not in DISCOVERY_CONFIDENCE:
            bad.append("%s: unknown confidence %r" % (label, root.get("confidence")))
    if bad:
        return Failure("10-root-evidence", "%d production-root evidence problem(s)" % len(bad), bad[:8])
    return None


def rule_11_capability_contract(doc):
    """Every environment reports the same seven discovery capabilities."""
    environments = get(doc, "discovery", "environment")
    if not isinstance(environments, list):
        return None
    capabilities = get(doc, "discovery", "capabilities", default={}) or {}
    expected = {"detection", "production_roots", "import_resolution",
                "token_source_discovery", "ownership", "mode_resolution",
                "runtime_verification"}
    bad = ["missing: %s" % name for name in sorted(expected - set(capabilities))]
    bad.extend("%s: invalid state %r" % (name, state)
               for name, state in capabilities.items()
               if name in expected and state not in CAPABILITY_STATES)
    if bad:
        return Failure("11-capability-contract", "%d capability contract problem(s)" % len(bad), bad[:8])
    return None


def rule_12_unresolved_classification(doc):
    """An unresolved import must say why rather than impersonating a missing file."""
    environments = get(doc, "discovery", "environment")
    if not isinstance(environments, list):
        return None
    unresolved = get(doc, "discovery", "import_graph", "unresolved", default=[]) or []
    bad = []
    for item in unresolved:
        if not isinstance(item, dict):
            bad.append("unresolved entry is not an object")
        elif item.get("reason") not in UNRESOLVED_REASONS:
            bad.append("%s: %r" % (item.get("spec"), item.get("reason")))
    if bad:
        return Failure("12-unresolved-classification",
                       "%d unresolved import(s) lack a useful reason" % len(bad), bad[:8])
    return None


def component_usage_section(document):
    if document is None:
        return None
    match = re.search(r'<section id="component-usage"[^>]*>.*?</section>', document, re.S)
    return match.group(0) if match else ""


def html_attribute(name, value):
    return '%s="%s"' % (name, html_tools.escape(str(value), quote=True))


def json_html_attribute(name, value):
    compact = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return html_attribute(name, compact)


def structured_tag(section, tag, marker_name, marker_value):
    marker = html_attribute(marker_name, marker_value)
    match = re.search(r'<%s\b[^>]*%s[^>]*>' % (
        tag, re.escape(marker)), section)
    return match.group(0) if match else None


def component_detail_block(section, component_id):
    marker = html_attribute("data-component-detail", component_id)
    opening = re.search(
        r'<details\b[^>]*%s[^>]*>' % re.escape(marker), section
    )
    if not opening:
        return None
    tail = section[opening.end():]
    next_component = re.search(
        r'<details\b[^>]*data-component-detail=', tail
    )
    return tail[:next_component.start()] if next_component else tail


def displayed_token_name(token):
    forms = []
    if "css-custom-property" in token.get("syntaxes", []):
        forms.append("--" + token.get("id", ""))
    if "scss-variable" in token.get("syntaxes", []):
        forms.append("$" + token.get("id", ""))
    return " / ".join(forms) if forms else token.get("id", "")


def rule_13_component_usage(doc, html=None):
    """A Top 20 adoption view that cannot be reproduced or inspected."""
    usage = doc.get("component_usage")
    if usage is None:
        return None
    if not isinstance(usage, dict):
        return Failure("13-component-usage", "component_usage is not an object")
    state = usage.get("state")
    if state not in {"measured", "unmeasured", "blocked"}:
        return Failure("13-component-usage", "component_usage has invalid state %r" % state)
    if state != "measured":
        if not usage.get("note"):
            return Failure("13-component-usage", "%s component usage has no explanation" % state)
        return None
    rows = usage.get("top_20") or []
    bad = []
    section = component_usage_section(html)
    if html is not None and not section:
        bad.append("HTML has no component-usage section")
    if len(rows) > 20:
        bad.append("top_20 contains %d rows" % len(rows))
    if usage.get("shown") != len(rows):
        bad.append("shown does not equal the rendered row count")
    expected_ranks = list(range(1, len(rows) + 1))
    actual_ranks = [row.get("rank") for row in rows if isinstance(row, dict)]
    if actual_ranks != expected_ranks:
        bad.append("ranks are not consecutive from 1")
    order = [(0 if row.get("kind") == "component" else 1,
              -row.get("references", 0), -row.get("distinct_tokens", 0), row.get("key", ""))
             for row in rows if isinstance(row, dict)]
    if order != sorted(order):
        bad.append("rows do not follow the documented stable ranking")
    roadmap = usage.get("roadmap")
    if not isinstance(roadmap, dict):
        bad.append("measured component usage has no roadmap object")
    else:
        expected_rows = [{
            "id": row.get("id"),
            "rank": row.get("rank"),
            "references": row.get("references", 0),
        } for row in rows if isinstance(row, dict)]
        expected_roadmap = build_roadmap(expected_rows)
        if roadmap != expected_roadmap:
            bad.append("component roadmap does not match ranked reference evidence")
        for row, expected in zip(rows, expected_rows):
            for field in (
                    "roadmap_band", "share_of_ranked_references",
                    "cumulative_share_of_ranked_references"):
                if row.get(field) != expected.get(field):
                    bad.append("%s: %s does not match ranked reference evidence" % (
                        row.get("name") or row.get("id") or "?", field))
    if section and isinstance(roadmap, dict):
        marker = json_html_attribute("data-component-roadmap-json", roadmap)
        if marker not in section:
            bad.append("HTML component roadmap is missing or stale")
    for row in rows:
        if not isinstance(row, dict):
            bad.append("a component row is not an object")
            continue
        label = row.get("name") or row.get("id") or "?"
        if not row.get("id") or not row.get("name") or not row.get("paths"):
            bad.append("%s: missing id, name, or paths" % label)
        if not row.get("kind") or not row.get("confidence"):
            bad.append("%s: missing kind or confidence" % label)
        tokens = row.get("tokens") or []
        if row.get("distinct_tokens") != len(tokens):
            bad.append("%s: distinct token count does not match token rows" % label)
        if row.get("references") != sum(token.get("references", 0) for token in tokens
                                         if isinstance(token, dict)):
            bad.append("%s: reference total does not match token rows" % label)
        family_counts = {}
        for token in tokens:
            if (not isinstance(token, dict) or not token.get("id") or
                    not token.get("family") or not token.get("locations") or
                    not token.get("syntaxes")):
                bad.append("%s: token without id, family, syntax, or locations" % label)
                continue
            family = token["family"]
            family_counts[family] = family_counts.get(family, 0) + token.get("references", 0)
        if row.get("families") != family_counts:
            bad.append("%s: family distribution does not match token rows" % label)
        if section:
            component_id = row.get("id", "")
            row_match = re.search(
                r'(<tr[^>]*%s[^>]*>)(.*?)</tr>' % re.escape(
                    html_attribute("data-component", component_id)),
                section, re.S,
            )
            if not row_match:
                bad.append("%s: HTML has no ranked component row" % label)
            else:
                tag = row_match.group(1)
                row_body = row_match.group(2)
                for name, value in (
                    ("data-component-kind", row.get("kind")),
                    ("data-component-references", row.get("references")),
                    ("data-component-distinct-tokens", row.get("distinct_tokens")),
                    ("data-component-roadmap-band", row.get("roadmap_band")),
                    ("data-component-share", "%.1f" % row.get(
                        "share_of_ranked_references", 0.0)),
                ):
                    if html_attribute(name, value) not in tag:
                        bad.append("%s: HTML component %s does not match JSON" % (label, name))
                visible_numbers = re.findall(
                    r'<td class="num">\s*([^<]+?)\s*</td>', row_body)
                expected_numbers = [str(value) for value in (
                    row.get("rank", 0), row.get("references", 0),
                    row.get("distinct_tokens", 0),
                    len(row.get("paths", []) or []),
                )]
                if visible_numbers != expected_numbers:
                    bad.append("%s: HTML visible roadmap counts do not match JSON" % label)
                for visible in (
                    '<code>%s</code>' % html_tools.escape(str(label)),
                    '<span class="component-share-label">%.1f%%</span>' % row.get(
                        "share_of_ranked_references", 0.0),
                    'href="#component-detail-%s"' % html_tools.escape(
                        str(component_id), quote=True),
                ):
                    if visible not in row_body:
                        bad.append("%s: HTML visible roadmap value does not match JSON" % label)
            for path in row.get("paths") or []:
                marker = html_attribute("data-component-path", path)
                visible = ">%s</span>" % html_tools.escape(str(path))
                if marker not in section or visible not in section:
                    bad.append("%s: HTML is missing component path %s" % (label, path))
            detail = component_detail_block(section, component_id)
            if detail is None:
                bad.append("%s: HTML has no token-detail block" % label)
                continue
            for token in tokens:
                if not isinstance(token, dict):
                    continue
                token_id = token.get("id", "")
                token_match = re.search(
                    r'(<tr[^>]*%s[^>]*>)(.*?)</tr>' % re.escape(html_attribute(
                        "data-component-token", "%s:%s" % (component_id, token_id))),
                    detail, re.S,
                )
                if not token_match:
                    bad.append("%s: HTML is missing token %s" % (label, token_id))
                    continue
                tag = token_match.group(1)
                token_body = token_match.group(2)
                for name, value in (
                    ("data-token-id", token_id),
                    ("data-token-family", token.get("family")),
                    ("data-token-syntaxes", ",".join(token.get("syntaxes", []))),
                    ("data-token-references", token.get("references")),
                ):
                    if html_attribute(name, value) not in tag:
                        bad.append("%s / %s: HTML %s does not match JSON" % (
                            label, token_id, name))
                if html_tools.escape(displayed_token_name(token)) not in token_body:
                    bad.append("%s / %s: token syntax is not visible in HTML" % (label, token_id))
                if html_tools.escape(str(token.get("family", ""))) not in token_body:
                    bad.append("%s / %s: token family is not visible in HTML" % (label, token_id))
                for location in token.get("locations") or []:
                    marker = html_attribute("data-token-location", location)
                    visible = ">%s</span>" % html_tools.escape(str(location))
                    accessible = html_attribute("aria-label", location)
                    if (token_body.count(marker) != 1 or
                            (visible not in token_body and accessible not in token_body)):
                        bad.append("%s / %s: HTML is missing location %s" % (
                            label, token_id, location))
                for path, group in grouped_locations(token.get("locations") or []):
                    if path is None or len(group) < 2:
                        continue
                    expected_preview = min(len(group), LOCATION_PREVIEW_LIMIT)
                    expected_hidden = len(group) - expected_preview
                    wrapper = structured_tag(
                        token_body, "div", "data-location-file", path
                    )
                    if wrapper is None or 'class="location-group"' not in wrapper:
                        bad.append("%s / %s: repeated locations are not grouped for %s" % (
                            label, token_id, path))
                        continue
                    for name, value in (
                        ("data-location-count", len(group)),
                        ("data-location-preview", expected_preview),
                    ):
                        if html_attribute(name, value) not in wrapper:
                            bad.append("%s / %s: %s has wrong %s" % (
                                label, token_id, path, name))
                    file_label = '<span class="path location-file">%s</span>' % (
                        html_tools.escape(path)
                    )
                    if token_body.count(file_label) != 1:
                        bad.append("%s / %s: %s is not shown once as a file label" % (
                            label, token_id, path))
                    disclosure = re.search(
                        r'<details\b[^>]*%s[^>]*>' % re.escape(
                            html_attribute("data-location-file", path)
                        ),
                        token_body,
                    )
                    if expected_hidden == 0:
                        if disclosure:
                            bad.append("%s / %s: %s has an unnecessary location disclosure" % (
                                label, token_id, path))
                        continue
                    if disclosure is None:
                        bad.append("%s / %s: %s has no location disclosure tail" % (
                            label, token_id, path))
                        continue
                    authored_open = re.search(
                        r"\sopen(?:\s|=|>)", disclosure.group(0)
                    )
                    enhanced_closed = html_attribute(
                        "data-report-default-open", "false"
                    ) in disclosure.group(0)
                    if authored_open and not enhanced_closed:
                        bad.append("%s / %s: %s location disclosure is open by default" % (
                            label, token_id, path))
                    if html_attribute("data-location-hidden", expected_hidden) not in disclosure.group(0):
                        bad.append("%s / %s: %s has the wrong hidden-location count" % (
                            label, token_id, path))
                    noun = "location" if expected_hidden == 1 else "locations"
                    summary = "<summary>See %d more %s in %s</summary>" % (
                        expected_hidden, noun, html_tools.escape(os.path.basename(path))
                    )
                    disclosure_end = token_body.find("</details>", disclosure.end())
                    if disclosure_end < 0:
                        bad.append("%s / %s: %s location disclosure is not closed" % (
                            label, token_id, path))
                        continue
                    disclosure_body = token_body[disclosure.start():disclosure_end]
                    if summary not in disclosure_body:
                        bad.append("%s / %s: %s location disclosure has the wrong summary" % (
                            label, token_id, path))
                    for index, (location, _line) in enumerate(group):
                        marker = html_attribute("data-token-location", location)
                        in_tail = marker in disclosure_body
                        if index < expected_preview and in_tail:
                            bad.append("%s / %s: %s preview location is hidden" % (
                                label, token_id, location))
                        if index >= expected_preview and not in_tail:
                            bad.append("%s / %s: %s disclosure location is visible by default" % (
                                label, token_id, location))
    if bad:
        return Failure("13-component-usage", "%d component-usage problem(s)" % len(bad), bad[:8])
    return None


def rule_14_profile_engine(doc, html=None, current_skill=False):
    """The universal engine must preserve profile composition and its ladder."""
    discovery = doc.get("discovery", {}) or {}
    engine = discovery.get("engine", {}) or {}
    if engine.get("name") != "universal-profile-engine":
        return None
    bad = []
    section = ""

    def check_tag(label, tag, marker_name, marker_value, attributes):
        if not section:
            return
        rendered = structured_tag(
            section, tag, marker_name, marker_value)
        if rendered is None:
            bad.append("%s is missing from HTML" % label)
            return
        for name, value, is_json in attributes:
            expected_attribute = (
                json_html_attribute(name, value) if is_json else
                html_attribute(name, value)
            )
            if expected_attribute not in rendered:
                bad.append("%s has wrong %s in HTML" % (label, name))

    if html is not None:
        match = re.search(r'<section id="discovery-engine"[^>]*>.*?</section>', html, re.S)
        section = match.group(0) if match else ""
        if not section:
            bad.append("HTML has no discovery-engine section")
    if current_skill:
        recorded = get(doc, "provenance", "skill_version")
        current = describe()["version"]
        if recorded != current:
            bad.append(
                "report skill version %r is stale; current skill is %r" %
                (recorded, current)
            )
        expected_adapters = set(discovery.get("adapters", []) or [])
        expected_adapters.update(get(doc, "stack", "adapters", default=[]) or [])
        adapter_versions = get(doc, "provenance", "adapter_versions", default={}) or {}
        if set(adapter_versions) != expected_adapters:
            bad.append("provenance adapter versions do not match active adapters")
        elif any(value != current for value in adapter_versions.values()):
            bad.append("one or more adapter versions are stale")
    repository = discovery.get("repository", {}) or {}
    repository_ref = repository.get("ref")
    if get(doc, "run", "repo_ref") != repository_ref:
        bad.append("run repository ref disagrees with discovery")
    if ("provenance" in doc and
            get(doc, "provenance", "repo_ref") != repository_ref):
        bad.append("report provenance repository ref disagrees with discovery")
    for framework, version in (get(
            doc, "run", "framework_versions", default={}) or {}).items():
        if (repository_ref and repository_ref in str(version)) or str(
                version).startswith("repository checkout "):
            bad.append(
                "%s: repository ref was substituted for a framework version" %
                framework
            )
    if current_skill and repository.get("root") and repository_ref:
        try:
            current_repo_ref = subprocess.run(
                ["git", "-C", repository["root"], "rev-parse", "--short=12", "HEAD"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            bad.append("audited repository ref could not be verified")
        else:
            if current_repo_ref != repository_ref:
                bad.append("audited repository ref is stale")
    composition = discovery.get("profile_composition")
    if not isinstance(composition, dict) or composition.get("schema_version") != 1:
        return Failure("14-profile-engine", "profile composition is missing or has the wrong schema")
    active = composition.get("active") or []
    active_ids = [item.get("id") for item in active if isinstance(item, dict)]
    environment = discovery.get("environment") or []
    if environment != (["unknown"] if not active_ids else active_ids):
        bad.append("environment does not match active profile order")
    if composition.get("order") != active_ids:
        bad.append("profile composition order does not match active profiles")
    registry_sources = composition.get("registry_sources")
    if not isinstance(registry_sources, list) or not registry_sources:
        bad.append("profile registry provenance is missing")
        registry_sources = []
    if ("provenance" in doc and
            get(doc, "provenance", "profile_registry_sources", default=[]) !=
            registry_sources):
        bad.append("report provenance disagrees with profile registry inputs")
    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for source in registry_sources:
        if (not isinstance(source, dict) or not source.get("path") or
                not re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", ""))):
            bad.append("profile registry source is malformed")
            continue
        check_tag(
            "%s: profile registry source" % source["path"], "tr",
            "data-registry-source", source["path"], [
                ("data-registry-sha256", source["sha256"], False),
            ],
        )
        if current_skill:
            source_path = (
                source["path"] if os.path.isabs(source["path"]) else
                os.path.join(skill_root, source["path"])
            )
            try:
                digest = hashlib.sha256()
                with open(source_path, "rb") as handle:
                    for chunk in iter(lambda: handle.read(65536), b""):
                        digest.update(chunk)
                current_digest = digest.hexdigest()
            except OSError:
                bad.append("%s: profile registry source is unavailable" % source["path"])
            else:
                if current_digest != source["sha256"]:
                    bad.append("%s: profile registry digest is stale" % source["path"])
    if len(active_ids) != len(set(active_ids)):
        bad.append("active framework profiles are duplicated")
    for item in active:
        if not isinstance(item, dict):
            bad.append("active profile is not an object")
            continue
        if not item.get("adapter") or not item.get("kind") or not item.get("confidence"):
            bad.append("%s: profile lacks adapter, kind, or confidence" % item.get("id", "?"))
        if item.get("activation") != "user-selected" and not item.get("evidence"):
            bad.append("%s: detected profile has no evidence" % item.get("id", "?"))
        check_tag(
            "%s: active profile" % item.get("id", "?"), "div",
            "data-profile", item.get("id"), [
                ("data-profile-confidence", item.get("confidence"), False),
                ("data-profile-kind", item.get("kind"), False),
                ("data-profile-activation", item.get("activation"), False),
                ("data-profile-score", item.get("score"), False),
                ("data-profile-evidence-json", item.get("evidence", []), True),
                ("data-profile-contexts-json", item.get("contexts", []), True),
            ],
        )
    candidate_ids = [item.get("id") for item in composition.get("candidates", [])
                     if isinstance(item, dict)]
    if set(active_ids) & set(candidate_ids):
        bad.append("a profile is both active and a candidate")
    if section:
        for candidate in composition.get("candidates", []) or []:
            if not isinstance(candidate, dict):
                continue
            check_tag(
                "%s: partial profile candidate" % candidate.get("id"), "tr",
                "data-profile-candidate", candidate.get("id"), [
                    ("data-profile-candidate-kind", candidate.get("kind"), False),
                    ("data-profile-candidate-score", candidate.get("score"), False),
                    ("data-profile-candidate-evidence-json",
                     candidate.get("evidence", []), True),
                    ("data-profile-candidate-missing-json",
                     candidate.get("missing_signals", []), True),
                ],
            )
        embedded_paths = {
            item.get("path") for item in
            composition.get("embedded_applications", []) or []
            if isinstance(item, dict)
        }
        selected_path = (composition.get("application_selection", {}) or {}).get(
            "selected")
        for application in composition.get("application_candidates", []) or []:
            if not isinstance(application, dict):
                continue
            path = application.get("path")
            selection_label = (
                "selected" if path == selected_path else
                ("embedded layer" if path in embedded_paths else "candidate")
            )
            check_tag(
                "%s: application candidate" % path, "tr",
                "data-application-candidate", path, [
                    ("data-application-package", application.get("package") or "", False),
                    ("data-application-markers-json",
                     application.get("markers", []), True),
                    ("data-application-profiles-json",
                     application.get("profiles", []), True),
                    ("data-application-selection", selection_label, False),
                ],
            )
    selection = composition.get("application_selection", {}) or {}
    if selection.get("state") not in {
            "root-application", "selected", "auto-selected", "blocked"}:
        bad.append("application selection has an invalid state")
    if selection.get("state") == "blocked":
        if get(doc, "discovery", "capabilities", "production_roots") != "blocked":
            bad.append("ambiguous application selection did not block production roots")
        if discovery.get("roots"):
            bad.append("ambiguous application selection still published product roots")
    for conflict in composition.get("conflicts", []) or []:
        if not isinstance(conflict, dict) or not conflict.get("capability"):
            bad.append("profile capability conflict is malformed")
            continue
        check_tag(
            "%s: capability conflict" % conflict.get("capability"), "tr",
            "data-capability-conflict", conflict.get("capability"), [
                ("data-conflict-profiles-json", conflict.get("profiles", []), True),
                ("data-conflict-states-json", conflict.get("states", []), True),
                ("data-conflict-resolution", conflict.get("resolution"), False),
            ],
        )

    ladder = discovery.get("capability_ladder", {}) or {}
    expected = [
        "detection", "production_roots", "import_resolution",
        "token_source_discovery", "ownership", "mode_resolution",
        "runtime_verification",
    ]
    if ladder.get("order") != expected:
        bad.append("capability ladder order is not the universal order")
    steps = ladder.get("steps") or []
    if [step.get("capability") for step in steps if isinstance(step, dict)] != expected:
        bad.append("capability ladder steps are missing, duplicated, or out of order")
    capabilities = discovery.get("capabilities", {}) or {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        name = step.get("capability")
        if step.get("state") != capabilities.get(name):
            bad.append("%s: ladder state disagrees with capabilities" % name)
        if not step.get("contributors"):
            bad.append("%s: ladder has no contributing profile or scope" % name)
        if not step.get("next_step"):
            bad.append("%s: ladder has no next step" % name)
        if step.get("state") != "verified" and not step.get("limitation"):
            bad.append("%s: incomplete capability has no limitation" % name)
        check_tag(
            "%s: capability" % name, "tr", "data-capability", name, [
                ("data-capability-state", step.get("state"), False),
                ("data-capability-contributors-json",
                 step.get("contributors", []), True),
                ("data-capability-evidence-json", step.get("evidence", []), True),
                ("data-capability-limitation", step.get("limitation") or "", False),
                ("data-capability-next-step", step.get("next_step"), False),
            ],
        )

    allowed_profiles = set(active_ids) | {"convention"}
    graph_reachable = get(doc, "discovery", "import_graph", "reachable", default={}) or {}
    for root in discovery.get("roots", []) or []:
        profiles = set(root.get("profiles") or []) if isinstance(root, dict) else set()
        if not profiles or not profiles <= allowed_profiles:
            bad.append("%s: product root has invalid profile contributors" % (
                root.get("path", "?") if isinstance(root, dict) else "?"))
        if isinstance(root, dict):
            check_tag(
                "%s: product root" % root.get("path"), "tr",
                "data-discovery-root", root.get("path"), [
                    ("data-root-type", root.get("root_type"), False),
                    ("data-root-ownership", root.get("ownership"), False),
                    ("data-root-confidence", root.get("confidence"), False),
                    ("data-root-profiles-json", root.get("profiles", []), True),
                    ("data-root-evidence", root.get("evidence"), False),
                ],
            )
    for root in discovery.get("root_candidates", []) or []:
        if not isinstance(root, dict):
            bad.append("product-root candidate is not an object")
            continue
        path = root.get("path")
        for field in ("path", "root_type", "ownership", "confidence",
                      "profiles", "evidence"):
            if not root.get(field):
                bad.append("%s: root candidate lacks %s" % (path or "?", field))
        if not set(root.get("profiles") or []) <= allowed_profiles:
            bad.append("%s: root candidate has invalid profile contributors" % path)
        if root.get("confidence") != "static candidate":
            bad.append("%s: root candidate is not a static candidate" % path)
        if path in graph_reachable:
            bad.append("%s: reachable root was left among candidates" % path)
        check_tag(
            "%s: product-root candidate" % path, "tr",
            "data-root-candidate", path, [
                ("data-root-type", root.get("root_type"), False),
                ("data-root-ownership", root.get("ownership"), False),
                ("data-root-confidence", root.get("confidence"), False),
                ("data-root-profiles-json", root.get("profiles", []), True),
                ("data-root-evidence", root.get("evidence"), False),
            ],
        )
    for root in discovery.get("missing_registered_roots", []) or []:
        if not isinstance(root, dict):
            bad.append("missing registered root is not an object")
            continue
        path = root.get("path")
        if root.get("exists") is not False:
            bad.append("%s: missing registered root is not marked absent" % path)
        check_tag(
            "%s: missing registered root" % path, "tr",
            "data-missing-root", path, [
                ("data-root-type", root.get("root_type"), False),
                ("data-root-ownership", root.get("ownership"), False),
                ("data-root-confidence", root.get("confidence"), False),
                ("data-root-profiles-json", root.get("profiles", []), True),
                ("data-root-evidence", root.get("evidence"), False),
            ],
        )
    for root in discovery.get("component_roots", []) or []:
        if (not isinstance(root, dict) or not root.get("path") or
                not root.get("evidence") or not root.get("profiles")):
            bad.append("component root lacks path, evidence, or profile")
        elif root.get("ownership") != "owned":
            bad.append("%s: non-owned component root entered adoption scope" % root.get("path"))
        elif not set(root.get("profiles") or []) <= set(active_ids):
            bad.append("%s: component root has invalid profile contributors" %
                       root.get("path"))
        if isinstance(root, dict):
            check_tag(
                "%s: component root" % root.get("path"), "tr",
                "data-component-root", root.get("path"), [
                    ("data-root-scope", root.get("scope", "component"), False),
                    ("data-root-ownership", root.get("ownership"), False),
                    ("data-root-confidence", root.get("confidence"), False),
                    ("data-root-profiles-json", root.get("profiles", []), True),
                    ("data-root-evidence", root.get("evidence"), False),
                ],
            )
    for root in discovery.get("component_root_candidates", []) or []:
        if (not isinstance(root, dict) or not root.get("path") or
                not root.get("evidence") or not root.get("profiles")):
            bad.append("component-root candidate lacks path, evidence, or profile")
            continue
        if root.get("ownership") == "owned":
            bad.append("%s: owned component root was left among candidates" %
                       root.get("path"))
        if not set(root.get("profiles") or []) <= set(active_ids):
            bad.append("%s: component-root candidate has invalid profiles" %
                       root.get("path"))
        check_tag(
            "%s: component-root candidate" % root.get("path"), "tr",
            "data-component-root-candidate", root.get("path"), [
                ("data-root-scope", root.get("scope", "component"), False),
                ("data-root-ownership", root.get("ownership"), False),
                ("data-root-confidence", root.get("confidence"), False),
                ("data-root-profiles-json", root.get("profiles", []), True),
                ("data-root-evidence", root.get("evidence"), False),
            ],
        )
    for root in discovery.get("surface_roots", []) or []:
        if not isinstance(root, dict):
            bad.append("surface root is not an object")
            continue
        if root.get("scope") not in {"supplemental", "demo"}:
            bad.append("%s: surface root is not supplemental or demo" % root.get("path"))
        if root.get("path") in graph_reachable:
            bad.append("%s: supplemental surface was promoted to product reachability" % root.get("path"))
        if not root.get("profiles") or not set(root.get("profiles")) <= set(active_ids):
            bad.append("%s: supplemental surface has invalid profiles" % root.get("path"))
        check_tag(
            "%s: supplemental surface" % root.get("path"), "tr",
            "data-surface-root", root.get("path"), [
                ("data-root-scope", root.get("scope", "component"), False),
                ("data-root-ownership", root.get("ownership"), False),
                ("data-root-confidence", root.get("confidence"), False),
                ("data-root-profiles-json", root.get("profiles", []), True),
                ("data-root-evidence", root.get("evidence"), False),
            ],
        )
    if section:
        for item in get(doc, "discovery", "import_graph", "unresolved", default=[]) or []:
            from_value = item.get("from") or "root"
            from_marker = html_attribute("data-unresolved-from", from_value)
            spec_marker = html_attribute("data-unresolved-spec", item.get("spec"))
            match = re.search(r'<tr[^>]*%s[^>]*%s[^>]*>' % (
                re.escape(from_marker), re.escape(spec_marker)), section)
            if not match or html_attribute(
                    "data-unresolved-reason", item.get("reason")) not in match.group(0):
                bad.append("%s -> %s: unresolved import is missing from HTML" % (
                    from_value, item.get("spec")))
    inventory = doc.get("inventory", {}) or {}
    concepts = inventory.get("concepts")
    if isinstance(concepts, list):
        if get(doc, "run", "token_count") != len(concepts):
            bad.append("run token_count disagrees with canonical concept inventory")
        names = [item.get("name") for item in concepts if isinstance(item, dict)]
        if len(names) != len(set(names)):
            bad.append("canonical concept inventory contains duplicate names")
        for family, entry in (inventory.get("families", {}) or {}).items():
            if not isinstance(entry, dict) or entry.get("state") != "measured":
                continue
            actual = len([item for item in concepts
                          if isinstance(item, dict) and item.get("family") == family])
            if entry.get("count") != actual:
                bad.append("%s: family count disagrees with concept inventory" % family)
            expected_sources = sorted({
                site.rsplit(":", 1)[0]
                for item in concepts
                if isinstance(item, dict) and item.get("family") == family
                for site in item.get("sites", [])
            })
            if entry.get("sources") != expected_sources:
                bad.append("%s: family sources disagree with concept inventory" % family)
            if html is not None:
                family_tag = structured_tag(html, "tr", "data-family", family)
                expected_attribute = json_html_attribute(
                    "data-family-sources-json", expected_sources)
                if family_tag is None or expected_attribute not in family_tag:
                    bad.append("%s: family sources are missing or stale in HTML" % family)
                family_row = re.search(
                    r'<tr\b[^>]*%s[^>]*>(.*?)</tr>' % re.escape(
                        html_attribute("data-family", family)),
                    html, re.S,
                )
                for source in expected_sources:
                    marker = html_attribute("data-family-source", source)
                    if family_row is None or marker not in family_row.group(1):
                        bad.append(
                            "%s: family source is not visibly rendered: %s" %
                            (family, source)
                        )
        if html is not None:
            for concept in concepts:
                if not isinstance(concept, dict):
                    continue
                name = concept.get("name")
                check = structured_tag(
                    html, "tr", "data-token-concept", name)
                expected_attributes = [
                    html_attribute("data-token-family", concept.get("family")),
                    json_html_attribute(
                        "data-token-representations-json",
                        concept.get("representations", [])),
                    json_html_attribute("data-token-sites-json",
                                        concept.get("sites", [])),
                    json_html_attribute("data-token-values-json",
                                        concept.get("values", [])),
                    json_html_attribute("data-token-definitions-json",
                                        concept.get("definitions", [])),
                ]
                if check is None or any(value not in check
                                        for value in expected_attributes):
                    bad.append("%s: canonical concept is missing or stale in HTML" % name)
    if html is not None and isinstance(concepts, list):
        roots = discovery.get("roots", []) or []
        unresolved = unresolved_import_summary(discovery)
        summary = {
            "profiles": discovery.get("environment", []),
            "roots": len(roots),
            "owned_roots": len([item for item in roots
                                if item.get("ownership") == "owned"]),
            "unknown_roots": len([item for item in roots
                                  if item.get("ownership") == "unknown"]),
            "reachable": len(discovery.get("import_graph", {}).get(
                "reachable", {})),
            "owned_reachable": len(discovery.get("owned_import_graph", {}).get(
                "reachable", {})),
            "unresolved_total": unresolved["total"],
            "unresolved_actionable": unresolved["actionable"],
            "unresolved_by_reason": unresolved["by_reason"],
            "concepts": len(concepts),
            "token_sources": confirmed_definition_count(
                discovery.get("token_sources", []) or []
            ),
            "held_out_sources": len(inventory.get(
                "candidate_or_local_override_sources", []) or []),
        }
        if json_html_attribute("data-measurement-summary-json", summary) not in html:
            bad.append("measurement summary is missing or stale in HTML")
        adapter_versions = get(doc, "provenance", "adapter_versions", default={}) or {}
        if json_html_attribute(
                "data-adapter-versions-json", adapter_versions) not in html:
            bad.append("adapter provenance is missing or stale in HTML")
        footer = {
            "profiles": discovery.get("environment", []),
            "concepts": len(concepts),
            "owned_reachable": summary["owned_reachable"],
            "owned_roots": summary["owned_roots"],
            "skill_version": get(doc, "provenance", "skill_version"),
        }
        if json_html_attribute("data-footer-summary-json", footer) not in html:
            bad.append("footer summary is missing or stale in HTML")
        runhead = {
            "profiles": discovery.get("environment", []),
            "roots": summary["roots"],
            "owned_roots": summary["owned_roots"],
            "reachable": summary["reachable"],
            "owned_reachable": summary["owned_reachable"],
            "token_sources": summary["token_sources"],
            "concepts": len(concepts),
        }
        if json_html_attribute("data-runhead-summary-json", runhead) not in html:
            bad.append("run header summary is missing or stale in HTML")
        held_out = len(inventory.get(
            "candidate_or_local_override_sources", []) or [])
        for rendered_count in re.findall(
                r"Classify (\d+) held-out declaration sources", html):
            if int(rendered_count) != held_out:
                bad.append("held-out source count is stale in next steps")
    if bad:
        return Failure("14-profile-engine", "%d profile-engine problem(s)" % len(bad), bad[:8])
    return None


def rule_4_no_zero_for_unmeasured(doc):
    """An unmeasured category rendered as zero or graded as if measured."""
    fams = get(doc, "inventory", "families", default={}) or {}
    bad = []
    for name, entry in fams.items():
        if not isinstance(entry, dict):
            continue
        state = entry.get("state")
        if state not in MEASURE_STATES:
            bad.append("%s: state %r is not one of %s" % (name, state, sorted(MEASURE_STATES)))
        elif state == "unmeasured" and entry.get("count") == 0:
            bad.append("%s: unmeasured and reported as 0" % name)
        elif state == "unmeasured" and not entry.get("note"):
            bad.append("%s: unmeasured with no note saying what is missing" % name)
    leakage = get(doc, "vitals", "leakage", default=None)
    if isinstance(leakage, dict):
        grade = leakage.get("grade")
        tiers = leakage.get("tiers") or {}
        if grade not in {"blocked", "not_applicable"} and tiers.get("redundant") is None:
            bad.append(
                "leakage: graded %r while semantic-equivalence/redundant tier is unmeasured"
                % grade)
    if bad:
        return Failure("4-unmeasured-as-zero",
                       "%d result(s) claim a measurement the run did not establish" % len(bad), bad[:8])
    return None


def rule_5_family_coverage(doc):
    """Typography or another foundational family missing from the report."""
    fams = get(doc, "inventory", "families", default=None)
    if fams is None:
        return Failure("5-family-coverage",
                       "no inventory.families block; the taxonomy was never searched")
    missing = [f for f in FAMILIES if f not in fams]
    if "typography" in missing:
        return Failure("5-family-coverage",
                       "typography is missing from the inventory",
                       ["also missing: %s" % ", ".join(m for m in missing if m != "typography")])
    if missing:
        return Failure("5-family-coverage",
                       "%d foundational family/families never searched" % len(missing),
                       ["missing: %s" % ", ".join(missing)])
    return None


def report_view_contract_problems(doc, html):
    """Validate the progressive report shell for every finished HTML document."""
    if not re.search(r'<(?:!doctype|html|body)\b', html, re.I):
        return []
    bad = []
    selected_view = get(doc, "rendering", "view")
    available_views = get(doc, "rendering", "available_views", default=[])
    if selected_view not in REPORT_VIEWS:
        bad.append("rendering.view is missing or invalid")
    if available_views != list(REPORT_VIEWS):
        bad.append("rendering.available_views does not declare the three report views")
    body_tag = re.search(r'<body\b[^>]*>', html)
    if not body_tag or html_attribute(
            "data-report-view", selected_view or "") not in body_tag.group(0):
        bad.append("HTML initial report view disagrees with JSON")
    switcher = re.search(r'<nav\b[^>]*class="report-view-switcher"[^>]*>', html)
    if not switcher:
        bad.append("HTML has no report-view switcher")
    else:
        switcher_tag = switcher.group(0)
        if html_attribute("data-report-view-default", selected_view or "") not in switcher_tag:
            bad.append("report-view switcher default disagrees with JSON")
        if json_html_attribute(
                "data-report-views-json", list(REPORT_VIEWS)) not in switcher_tag:
            bad.append("report-view switcher does not declare all three views")
    view_buttons = re.findall(r'<button\b[^>]*data-report-view-button="[^"]+"[^>]*>', html)
    button_views = [
        re.search(r'data-report-view-button="([^"]+)"', tag).group(1)
        for tag in view_buttons
    ]
    if button_views != list(REPORT_VIEWS):
        bad.append("report-view buttons are missing, duplicated, or out of order")
    selected_buttons = [
        tag for tag in view_buttons if html_attribute("aria-pressed", "true") in tag
    ]
    if (len(selected_buttons) != 1 or selected_view is None or
            html_attribute("data-report-view-button", selected_view) not in
            selected_buttons[0]):
        bad.append("report-view button selection disagrees with JSON")
    section_tags = re.findall(r'<section\b[^>]*\bid="([^"]+)"[^>]*>', html)
    for section_id in section_tags:
        expected_views = REPORT_VIEW_SECTIONS.get(section_id)
        if expected_views is None:
            bad.append("%s section has no report-view contract" % section_id)
            continue
        tag = re.search(
            r'<section\b[^>]*\bid="%s"[^>]*>' % re.escape(section_id), html
        ).group(0)
        if html_attribute(
                "data-report-views", " ".join(expected_views)) not in tag:
            bad.append("%s section has the wrong report-view visibility" % section_id)
    for marker, label in (
            (".report-view-switcher { display: none; }",
             "no-script report-view control hiding"),
            (".report-views--ready .report-view-switcher { display: block; }",
             "script-ready report-view control display")):
        if marker not in html:
            bad.append("report views lack %s" % label)
    disclosure_tags = re.findall(r'<details\b[^>]*>', html, re.I)
    for tag in disclosure_tags:
        if not re.search(r'\sopen(?:\s|=|>)', tag, re.I):
            bad.append("a disclosure is closed in the no-script document")
            break
        if not re.search(
                r'\bdata-report-default-open="(?:true|false)"', tag, re.I):
            bad.append("a disclosure does not record its enhanced default state")
            break
    if disclosure_tags and (
            "disclosure.dataset.reportDefaultOpen" not in html or
            "disclosure.open = disclosure.dataset.reportDefaultOpen" not in html):
        bad.append("the report controller does not restore disclosure defaults")
    return bad


def rule_6_html_matches_json(doc, html):
    """The HTML truncated something the JSON still holds, without saying so."""
    if html is None:
        return None
    view_bad = report_view_contract_problems(doc, html)
    if get(doc, "discovery", "engine", "name") == "universal-profile-engine":
        required = (
            "at-a-glance", "exec-summary", "decisions", "fix-queue",
            "groups", "lineage", "coverage-matrix", "next-steps",
            "modes-coverage", "modes-gaps", "orphans", "enforcement",
        )
        regions = {}
        bad = list(view_bad)
        for name in required:
            match = re.search(
                r'<!-- SLOT:%s -->(.*?)<!-- /SLOT:%s -->' % (
                    re.escape(name), re.escape(name)),
                html, re.S,
            )
            if not match:
                bad.append("required HTML region is absent: %s" % name)
                continue
            regions[name] = match.group(1)
            if html_attribute("data-report-region", name) not in match.group(1):
                bad.append("required HTML region is unrendered: %s" % name)

        tab_tags = re.findall(r'<button\b[^>]*role="tab"[^>]*>', html)
        panel_tags = re.findall(r'<div\b[^>]*role="tabpanel"[^>]*>', html)
        if 'role="tablist"' not in html or len(tab_tags) != 3 or len(panel_tags) != 3:
            bad.append("inventory tabs lack one tablist, three tabs, or three panels")
        for family in ("color", "typography", "foundation"):
            tab_id = "inventory-tab-%s" % family
            panel_id = "inventory-panel-%s" % family
            if not any(
                    html_attribute("id", tab_id) in tag and
                    html_attribute("aria-controls", panel_id) in tag
                    for tag in tab_tags):
                bad.append("%s inventory tab lacks its panel relationship" % family)
            if not any(
                    html_attribute("id", panel_id) in tag and
                    html_attribute("aria-labelledby", tab_id) in tag
                    for tag in panel_tags):
                bad.append("%s inventory panel lacks its tab relationship" % family)
        if any(re.search(r"\shidden(?:\s|=|>)", tag) for tag in panel_tags):
            bad.append("inventory panels are hidden in the no-script document")
        for marker, label in (
                ("display: none; gap: 4px;", "no-script tab-list hiding"),
                (".token-tabs--ready .token-tabs__list { display: flex; }",
                 "script-ready tab-list display"),
                (".token-tabs__list { display: none !important; }",
                 "print tab-list hiding"),
                (".token-tabs__panel { display: block !important; padding-top: 12px; }",
                 "print panel visibility")):
            if marker not in html:
                bad.append("inventory tabs lack %s" % label)
        if html.count(INVENTORY_TABS_SCRIPT) != 1:
            bad.append("inventory tabs lack exactly one verified controller")

        if "at-a-glance" in regions and json_html_attribute(
                "data-stage-json", doc.get("stage", {})) not in regions["at-a-glance"]:
            bad.append("at-a-glance stage disagrees with JSON")
        component_usage = doc.get("component_usage", {}) or {}
        component_roadmap = component_usage.get("roadmap", {}) or {}
        if ("at-a-glance" in regions and
                component_usage.get("state") == "measured" and
                component_usage.get("top_20") and
                json_html_attribute(
                    "data-dashboard-component-roadmap-json",
                    component_roadmap,
                ) not in regions["at-a-glance"]):
            bad.append("at-a-glance component roadmap disagrees with JSON")
        if ("at-a-glance" in regions and
                component_usage.get("state") == "measured" and
                component_usage.get("top_20")):
            dashboard_region = regions["at-a-glance"]
            dashboard_rows = component_usage.get("top_20", [])[:5]
            if dashboard_region.count('data-dashboard-component="') != len(
                    dashboard_rows):
                bad.append("at-a-glance component row count disagrees with JSON")
            band_labels = {
                item.get("id"): item.get("label")
                for item in component_roadmap.get("bands", [])
                if isinstance(item, dict)
            }
            for row in dashboard_rows:
                if not isinstance(row, dict):
                    continue
                label = row.get("name") or row.get("id") or "?"
                marker = html_attribute(
                    "data-dashboard-component", row.get("id", ""))
                rendered = re.search(
                    r'<tr\b[^>]*%s[^>]*>(.*?)</tr>' % re.escape(marker),
                    dashboard_region, re.S,
                )
                if not rendered:
                    bad.append("%s: dashboard row is missing" % label)
                    continue
                tag = rendered.group(0).split(">", 1)[0] + ">"
                body = rendered.group(1)
                for name, value in (
                    ("data-roadmap-band", row.get("roadmap_band")),
                    ("data-component-references", row.get("references")),
                    ("data-component-distinct-tokens", row.get("distinct_tokens")),
                    ("data-component-paths", len(row.get("paths", []) or [])),
                    ("data-component-share", "%.1f" % row.get(
                        "share_of_ranked_references", 0.0)),
                ):
                    if html_attribute(name, value) not in tag:
                        bad.append("%s: dashboard %s disagrees with JSON" % (
                            label, name))
                visible_numbers = re.findall(
                    r'<td class="num">\s*([^<]+?)\s*</td>', body)
                expected_numbers = [str(value) for value in (
                    row.get("rank", 0), row.get("references", 0),
                    row.get("distinct_tokens", 0),
                    len(row.get("paths", []) or []),
                )]
                if visible_numbers != expected_numbers:
                    bad.append("%s: dashboard visible counts disagree with JSON" % label)
                for visible in (
                    '<code>%s</code>' % html_tools.escape(str(label)),
                    '<span class="component-share-label">%.1f%%</span>' % row.get(
                        "share_of_ranked_references", 0.0),
                    '<span class="component-roadmap-state">%s</span>' %
                    html_tools.escape(str(band_labels.get(
                        row.get("roadmap_band"), "Review"))),
                ):
                    if visible not in body:
                        bad.append("%s: dashboard visible value disagrees with JSON" % label)
        if "exec-summary" in regions and json_html_attribute(
                "data-executive-summary-json",
                doc.get("executive_summary", {})) not in regions["exec-summary"]:
            bad.append("executive summary disagrees with JSON")
        if "next-steps" in regions and json_html_attribute(
                "data-next-steps-json", next_step_items(doc)) not in regions["next-steps"]:
            bad.append("next steps disagree with JSON")
        for name in ("modes-coverage", "modes-gaps"):
            if name in regions and json_html_attribute(
                    "data-modes-json",
                    doc.get("coverage_matrix", {})) not in regions[name]:
                bad.append("%s disagrees with coverage JSON" % name)
        for name in ("orphans", "enforcement"):
            if name in regions and json_html_attribute(
                    "data-vital-json",
                    get(doc, "vitals", name, default={}) or {}) not in regions[name]:
                bad.append("%s panel disagrees with vital JSON" % name)

        structured = (
            ("decisions", doc.get("decisions", []) or [], "data-decision-json"),
            ("fix-queue", doc.get("fix_queue", []) or [], "data-fix-queue-json"),
            ("lineage", doc.get("lineage", []) or [], "data-lineage-json"),
            ("coverage-matrix", get(
                doc, "coverage_matrix", "cells", default=[]) or [],
             "data-coverage-json"),
        )
        for region_name, items, attribute in structured:
            region = regions.get(region_name, "")
            rendered = region.count(attribute + '="')
            if rendered != len(items):
                bad.append(
                    "%s renders %d structured records; JSON has %d" % (
                        region_name, rendered, len(items)))
                continue
            for item in items:
                if json_html_attribute(attribute, item) not in region:
                    bad.append("%s omits or changes a JSON record" % region_name)
                    break

        group_items = []
        for items in (doc.get("groups", {}) or {}).values():
            group_items.extend(items or [])
        group_region = regions.get("groups", "")
        if group_region.count('data-group-json="') != len(group_items):
            bad.append("groups HTML count disagrees with JSON")
        else:
            for item in group_items:
                if json_html_attribute("data-group-json", item) not in group_region:
                    bad.append("groups HTML omits or changes a JSON record")
                    break
        if bad:
            return Failure(
                "6-html-json-parity",
                "%d required HTML region/parity problem(s)" % len(bad),
                bad[:12],
            )
    elif view_bad:
        return Failure(
            "6-html-json-parity",
            "%d report-view contract problem(s)" % len(view_bad),
            view_bad[:12],
        )
    declared = get(doc, "rendering", "truncated", default=[]) or []
    # Every truncation the HTML performs has to be declared in the JSON.
    shown = re.findall(r'class="trunc"[^>]*>(.*?)</div>', html, re.S)
    if shown and not declared:
        return Failure("6-html-json-parity",
                       "the HTML declares %d truncation(s) that rendering.truncated does not record" % len(shown),
                       [re.sub(r"<[^>]+>", "", s).strip()[:90] for s in shown[:4]])
    for entry in declared:
        if not isinstance(entry, dict):
            return Failure("6-html-json-parity",
                           "rendering.truncated holds a bare value rather than {section, shown, withheld, summary}",
                           [repr(entry)])
        if not entry.get("summary"):
            return Failure("6-html-json-parity",
                           "a truncated section records no summary of what the remainder holds",
                           [json.dumps(entry)])
    return None


CONFIDENCES = {
    "exact static match", "import-graph verified",
    "compiled-runtime verified", "manual review",
}


def rule_7_fix_queue_integrity(doc):
    """A fix queue that cannot be acted on, or that promises too much."""
    queue = get(doc, "fix_queue", default=None)
    if queue is None:
        return None
    bad = []
    for item in queue:
        if not isinstance(item, dict):
            bad.append("a queue entry is not an object")
            continue
        label = item.get("id") or item.get("literal") or "?"
        conf = item.get("confidence")
        if conf not in CONFIDENCES:
            bad.append("%s: confidence %r is not one of the four levels" % (label, conf))
        if not item.get("replacement"):
            bad.append("%s: no canonical replacement token" % label)
        if not item.get("locations"):
            bad.append("%s: no file:line locations to act on" % label)
        auto = item.get("safe_to_automate")
        if auto is None:
            bad.append("%s: does not say whether the swap is safe to automate" % label)
        elif auto and not is_automatable(
                item.get("tier"), conf, item.get("semantic_role_verified", False)):
            bad.append(
                "%s: marked safe to automate without redundant-tier, confidence, "
                "and semantic-role proof" % label)
    if bad:
        return Failure("7-fix-queue", "%d fix-queue entry problem(s)" % len(bad), bad[:8])
    return None


def rule_8_html_holds_every_finding(doc, html):
    """The HTML rendered less than the JSON holds."""
    if html is None:
        return None
    json_ids = collect_ids(doc)
    if not json_ids:
        return None
    missing = sorted(fid for fid in json_ids if fid not in html)
    if missing:
        return Failure(
            "8-html-completeness",
            "%d finding(s) exist in the JSON and appear nowhere in the HTML" % len(missing),
            missing[:8],
        )
    bad = []
    leakage = doc.get("leakage_analysis", {}) or {}
    for item in ((leakage.get("exact_value_candidates", []) or []) +
                 (leakage.get("uncovered_candidates", []) or [])):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        marker = html_attribute("data-finding", item["id"])
        match = re.search(
            r'<tr\b[^>]*%s[^>]*>(.*?)</tr>' % re.escape(marker), html, re.S)
        if not match:
            bad.append("%s: no structured leakage row" % item["id"])
            continue
        tag = match.group(0).split(">", 1)[0] + ">"
        body = match.group(1)
        for name, value in (
                ("data-finding-locations-json", item.get("locations", [])),
                ("data-finding-token-candidates-json",
                 item.get("token_candidates", [])),
                ("data-finding-properties-json", item.get("properties", []))):
            if json_html_attribute(name, value) not in tag:
                bad.append("%s: stale %s" % (item["id"], name))
        for location in item.get("locations", []) or []:
            location_marker = html_attribute("data-finding-location", location)
            if location_marker not in body:
                bad.append("%s: missing location %s" % (item["id"], location))
    if bad:
        return Failure(
            "8-html-completeness",
            "%d leakage evidence item(s) are missing or stale in HTML" % len(bad),
            bad[:8],
        )
    return None


# What the template never contains beyond the exact, static inventory-tab
# controller owned by this skill. Repository content — a literal, a path,
# a note — is rendered into the report, and a CSS string holding markup
# reaches the page as-is unless the fill stage escapes it.
INJECTION = re.compile(r"<script\b|<iframe\b|\son(?:error|load|mouseover|click|focus)\s*=|javascript:", re.I)


def rule_9_no_unescaped_markup(html):
    """Repository content rendered into the page without escaping."""
    if html is None:
        return None
    trusted_count = html.count(INVENTORY_TABS_SCRIPT)
    inspected = html.replace(INVENTORY_TABS_SCRIPT, "", 1)
    hits = INJECTION.findall(inspected)
    if hits:
        return Failure("9-unescaped-markup",
                       "%d untrusted executable-markup pattern(s) in the HTML" % len(hits),
                       sorted(set(h.strip() for h in hits))[:6])
    if trusted_count > 1:
        return Failure(
            "9-unescaped-markup",
            "the verified inventory-tab controller appears more than once",
        )
    return None


def rule_15_source_artifact_parity(doc, artifacts=None):
    """A consistent report must still agree with the files that produced it."""
    if not artifacts:
        return None
    discovery = artifacts.get("discovery")
    tokens = artifacts.get("tokens")
    components = artifacts.get("components")
    leakage = artifacts.get("leakage")
    interaction = artifacts.get("interaction")
    bad = []
    if discovery is not None:
        expected_discovery = enrich(discovery, tokens)
        if doc.get("discovery") != expected_discovery:
            bad.append("report discovery does not match discovery.json plus token evidence")
    if tokens is not None:
        expected_concepts = normalized_concepts(tokens)
        inventory = doc.get("inventory", {}) or {}
        if inventory.get("concepts") != expected_concepts:
            bad.append("canonical concept inventory does not match tokens.json")
        expected_held_out = tokens.get(
            "candidate_or_local_override_sources", [])
        if inventory.get("candidate_or_local_override_sources") != expected_held_out:
            bad.append("held-out source inventory does not match tokens.json")
        if inventory.get("identity") != tokens.get("identity"):
            bad.append("identity inventory does not match tokens.json")
        if get(doc, "run", "token_count") != tokens.get(
                "concept_count", len(expected_concepts)):
            bad.append("run token count does not match tokens.json")
    if components is not None and doc.get("component_usage") != components:
        bad.append("component usage does not match components.json")
    if leakage is not None:
        if doc.get("leakage_analysis") != leakage:
            bad.append("leakage analysis does not match literal-colors.json")
        if get(doc, "run", "files_scanned") != leakage.get(
                "consumer_files_scanned"):
            bad.append("run file denominator does not match literal-colors.json")
    if interaction is not None:
        if interaction.get("skill_version") != get(
                doc, "provenance", "skill_version"):
            bad.append("interaction evidence skill version is stale")
        if interaction.get("generated_at") != get(
                doc, "provenance", "generated_at"):
            bad.append("interaction evidence timestamp is stale")
        if interaction.get("report_json_sha256") != artifacts.get(
                "_report_json_sha256"):
            bad.append("interaction evidence report JSON hash is stale")
        if interaction.get("report_html_sha256") != artifacts.get(
                "_report_html_sha256"):
            bad.append("interaction evidence report HTML hash is stale")
        expected_controller = hashlib.sha256(
            INVENTORY_TABS_SCRIPT.encode("utf-8")).hexdigest()
        if interaction.get("controller_sha256") != expected_controller:
            bad.append("interaction evidence controller hash is stale")
        browser = interaction.get("browser", {}) or {}
        if not browser.get("name") or not browser.get("version"):
            bad.append("interaction evidence lacks browser name or version")
        repository_root = get(doc, "discovery", "repository", "root")
        screenshots = interaction.get("screenshots")
        if not isinstance(screenshots, list) or not screenshots:
            bad.append("interaction evidence has no screenshot artifacts")
            screenshots = []
        for screenshot in screenshots:
            relative_path = screenshot.get("path") if isinstance(
                screenshot, dict) else None
            expected_sha = screenshot.get("sha256") if isinstance(
                screenshot, dict) else None
            if not repository_root or not relative_path or not expected_sha:
                bad.append("interaction screenshot lacks path, hash, or repository root")
                continue
            root = os.path.realpath(repository_root)
            path = os.path.realpath(os.path.join(root, relative_path))
            try:
                contained = os.path.commonpath([root, path]) == root
            except ValueError:
                contained = False
            if not contained or not os.path.isfile(path):
                bad.append("interaction screenshot is unavailable: %s" % relative_path)
                continue
            if file_sha256(path) != expected_sha:
                bad.append("interaction screenshot hash is stale: %s" % relative_path)
        print_pdf = interaction.get("print_pdf")
        if not isinstance(print_pdf, dict):
            bad.append("interaction evidence has no print PDF regression artifact")
        else:
            relative_path = print_pdf.get("path")
            expected_sha = print_pdf.get("sha256")
            verified_text = print_pdf.get("verified_text")
            if not repository_root or not relative_path or not expected_sha:
                bad.append("interaction print PDF lacks path, hash, or repository root")
            else:
                root = os.path.realpath(repository_root)
                path = os.path.realpath(os.path.join(root, relative_path))
                try:
                    contained = os.path.commonpath([root, path]) == root
                except ValueError:
                    contained = False
                if not contained or not os.path.isfile(path):
                    bad.append("interaction print PDF is unavailable: %s" % relative_path)
                elif file_sha256(path) != expected_sha:
                    bad.append("interaction print PDF hash is stale: %s" % relative_path)
            if not isinstance(verified_text, list) or not verified_text:
                bad.append("interaction print PDF records no verified disclosure text")
    if bad:
        return Failure(
            "15-source-artifact-parity",
            "%d source-artifact parity problem(s)" % len(bad),
            bad,
        )
    return None


FINISHED_REPORT_SENTINELS = (
    "northwind-ds", "acme-storefront", "Sample report · representative data",
    "7f0c22ab", "a91f4c07", "color.primitive.json", "src/**/*.{ts,tsx}",
    "color.semantic.brand.base", "motion.ease.emphasized", "1,645",
)


def rule_16_identity_integrity(doc, html=None):
    """Typography and brand color must be evidenced, explicit, and non-generic."""
    universal = get(doc, "discovery", "engine", "name") == "universal-profile-engine"
    identity = get(doc, "inventory", "identity", default=None)
    if identity is None and not universal:
        return None
    bad = []
    if not isinstance(identity, dict):
        return Failure("16-identity-integrity", "identity inventory is missing")

    typography = identity.get("typography", {}) or {}
    if typography.get("state") not in {"verified", "blocked"}:
        bad.append("typography identity must be verified or blocked")
    if typography.get("state") == "verified":
        for field in ("family", "token", "confidence", "evidence"):
            if not typography.get(field):
                bad.append("verified typography identity lacks %s" % field)
        if typography.get("confidence") != "explicit-family-token":
            bad.append("verified typography has an unsupported confidence")
        if concrete_font_family(typography.get("family")) is None:
            bad.append("verified typography selects a generic or unresolved family")
    elif typography.get("family") or typography.get("token"):
        bad.append("blocked typography identity still selects a family or token")
    elif typography.get("confidence") != "unresolved":
        bad.append("blocked typography must use unresolved confidence")

    specimen = typography.get("specimen", {}) or {}
    if specimen.get("state") not in {"verified", "blocked"}:
        bad.append("typography specimen must be verified or blocked")
    if typography.get("state") == "blocked" and specimen.get("state") == "verified":
        bad.append("blocked typography cannot verify a specimen")

    brand = identity.get("brand_colors", {}) or {}
    colors = brand.get("colors", []) or []
    if brand.get("state") not in {"verified", "blocked"}:
        bad.append("brand color identity must be verified or blocked")
    if brand.get("state") == "verified" and not colors:
        bad.append("verified brand color identity has no colors")
    if brand.get("state") == "blocked" and colors:
        bad.append("blocked brand color identity still publishes colors")
    if (brand.get("state") == "verified" and
            brand.get("confidence") != "explicit-brand-semantics"):
        bad.append("verified brand colors have an unsupported confidence")
    if brand.get("state") == "blocked" and brand.get("confidence") != "unresolved":
        bad.append("blocked brand colors must use unresolved confidence")
    allowed_color_confidence = {
        "explicit-brand-token-name", "explicit-brand-source-section",
        "explicit-brand-name-and-source-section",
    }
    for item in colors:
        if not isinstance(item, dict):
            bad.append("brand color is not an object")
            continue
        for field in ("token", "value", "confidence", "evidence"):
            if not item.get(field):
                bad.append("brand color lacks %s" % field)
        if item.get("confidence") not in allowed_color_confidence:
            bad.append("brand color has an unsupported confidence")
        if concrete_color_value(item.get("value")) is None:
            bad.append("brand color is not a self-contained concrete value")

    conflicts = brand.get("conflicts", []) or []
    for item in conflicts:
        if (not isinstance(item, dict) or not item.get("token") or
                len(item.get("values", [])) < 2 or not item.get("evidence") or
                not item.get("reason")):
            bad.append("brand conflict lacks token, values, evidence, or reason")

    concepts = get(doc, "inventory", "concepts", default=[]) or []
    if concepts:
        identity_tokens = {
            item.get("token") for item in typography.get("candidates", [])
            if isinstance(item, dict) and item.get("token")
        }
        identity_tokens.update(
            item.get("token") for item in colors + conflicts
            if isinstance(item, dict) and item.get("token")
        )
        source_cache = {}
        repository_root = get(doc, "discovery", "repository", "root")
        reachable_sources = get(
            doc, "discovery", "owned_import_graph", "reachable",
            default={}) or {}
        if identity_tokens and not repository_root:
            bad.append("verified identity has no repository root for source binding")

        def bound_source_definition(concept, definition):
            if not repository_root:
                return None
            site = str(definition.get("site", ""))
            if ":" not in site:
                return None
            source_path, source_line = site.rsplit(":", 1)
            if source_path not in reachable_sources:
                return None
            root = os.path.realpath(repository_root)
            full = os.path.realpath(os.path.join(root, source_path))
            try:
                contained = os.path.commonpath([root, full]) == root
            except ValueError:
                contained = False
            if not contained or not os.path.isfile(full):
                return None
            if source_path not in source_cache:
                with open(full, encoding="utf-8", errors="replace") as handle:
                    source_text = handle.read()
                source_cache[source_path] = (
                    source_text, declarations(source_text, source_path))
            source_text, source_declarations = source_cache[source_path]
            offset = definition.get("offset")
            if (not isinstance(offset, int) or offset < 0 or
                    offset > len(source_text) or not source_line.isdigit() or
                    source_text.count("\n", 0, offset) + 1 != int(source_line)):
                return None
            expected = (
                concept.get("name"), definition.get("value"),
                definition.get("representation"), offset,
            )
            if not any(
                    (normalize(name), value, representation, found_offset) == expected
                    for name, value, representation, found_offset in source_declarations):
                return None
            return source_path, source_text, offset

        canonical = []
        for concept in concepts:
            definitions = concept.get("definitions", []) or []
            if definitions:
                if any(
                        not isinstance(definition, dict) or
                        not all(definition.get(field) for field in (
                            "value", "site", "representation"))
                        for definition in definitions):
                    bad.append("%s has an incomplete definition" % concept.get("name"))
                else:
                    projections = {
                        "values": list(dict.fromkeys(
                            definition["value"] for definition in definitions)),
                        "sites": list(dict.fromkeys(
                            definition["site"] for definition in definitions)),
                        "representations": list(dict.fromkeys(
                            definition["representation"] for definition in definitions)),
                        "identity_contexts": list(dict.fromkeys(
                            json.dumps(definition["identity_context"], sort_keys=True)
                            for definition in definitions
                            if definition.get("identity_context") is not None)),
                    }
                    projections["identity_contexts"] = [
                        json.loads(item) for item in projections["identity_contexts"]
                    ]
                    for field, expected_values in projections.items():
                        if concept.get(field, []) != expected_values:
                            bad.append(
                                "%s %s disagree with per-definition evidence" % (
                                    concept.get("name"), field))
                    for definition in definitions:
                        binding = None
                        if concept.get("name") in identity_tokens and repository_root:
                            binding = bound_source_definition(concept, definition)
                            if binding is None:
                                bad.append(
                                    "%s identity definition is not reproducible from source" %
                                    concept.get("name"))
                        context = definition.get("identity_context")
                        if (context is None or
                                concept.get("name") not in identity_tokens):
                            continue
                        if binding is None:
                            bad.append("%s brand context has no repository source" % concept.get("name"))
                            continue
                        source_path, source_text, offset = binding
                        if context.get("path") != source_path:
                            bad.append("%s brand context source is missing or mismatched" % concept.get("name"))
                            continue
                        actual_context = identity_context(source_text, offset)
                        if actual_context:
                            actual_context = dict(actual_context, path=source_path)
                        if actual_context != context:
                            bad.append("%s brand context heading is not reproducible" % concept.get("name"))
            item = dict(concept)
            item["id"] = item.pop("name", item.get("id"))
            canonical.append(item)
        repository_root = get(doc, "discovery", "repository", "root")
        subjects = (
            subject_namespace_evidence(repository_root, doc.get("discovery"))
            if repository_root else []
        )
        recomputed = identity_summary(
            canonical, subject_namespaces=subjects)
        expected_type = recomputed["typography"]
        for field in ("state", "family", "token", "confidence", "evidence", "candidates"):
            if typography.get(field) != expected_type.get(field):
                bad.append("typography %s does not match canonical concepts" % field)
        expected_brand = recomputed["brand_colors"]
        for field in (
                "state", "confidence", "colors", "conflicts",
                "subject_namespaces"):
            if brand.get(field, [] if field in {"colors", "conflicts"} else None) != expected_brand.get(field):
                bad.append("brand color %s does not match canonical concepts" % field)

    embedded_payload = None
    embedded_asset = None
    if specimen.get("state") == "verified":
        asset = specimen.get("asset", {}) or {}
        repository_root = get(doc, "discovery", "repository", "root")
        path = asset.get("path")
        expected_sha = asset.get("sha256")
        font_format = asset.get("format")
        if not repository_root or not path or not expected_sha or not font_format:
            bad.append("verified specimen lacks repository, path, hash, or format")
        else:
            root = os.path.realpath(repository_root)
            full = os.path.realpath(os.path.join(root, path))
            try:
                contained = os.path.commonpath([root, full]) == root
            except ValueError:
                contained = False
            if (not contained or not os.path.isfile(full) or
                    os.path.getsize(full) > MAX_EMBEDDED_FONT_BYTES or
                    not verified_font_file(full, font_format)):
                bad.append("verified specimen font asset is missing or invalid")
            else:
                with open(full, "rb") as handle:
                    embedded_asset = handle.read()
                if hashlib.sha256(embedded_asset).hexdigest() != expected_sha:
                    bad.append("verified specimen font hash is stale")
                if not matching_font_asset_evidence(
                        repository_root, typography.get("family"), asset):
                    bad.append(
                        "verified specimen is not bound to the selected family by its declaration")
                declaration_path = str(asset.get("declaration", "")).rsplit(":", 1)[0]
                reachable = get(
                    doc, "discovery", "owned_import_graph", "reachable",
                    default={}) or {}
                if declaration_path not in reachable:
                    bad.append("verified specimen declaration is not product-reachable")

    if html is not None:
        type_match = re.search(
            r'<!-- SLOT:inventory-type -->.*?<!-- /SLOT:inventory-type -->',
            html, re.S,
        )
        type_section = type_match.group(0) if type_match else ""
        if not type_section:
            bad.append("HTML has no typography identity section")
        else:
            type_tag = structured_tag(
                type_section, "div", "data-typography-state",
                typography.get("state"),
            )
            expected = [
                html_attribute("data-typography-family",
                               typography.get("family") or ""),
                html_attribute("data-typography-token",
                               typography.get("token") or ""),
                html_attribute("data-typography-confidence",
                               typography.get("confidence")),
                json_html_attribute("data-typography-evidence-json",
                                    typography.get("evidence", [])),
                html_attribute("data-typography-specimen-state",
                               specimen.get("state", "blocked")),
            ]
            if type_tag is None or any(value not in type_tag for value in expected):
                bad.append("typography identity HTML disagrees with JSON")
            if specimen.get("state") == "blocked":
                if ('class="typescale"' in type_section or
                        "data:font/" in type_section):
                    bad.append("blocked typography renders or embeds a specimen")
            else:
                asset = specimen.get("asset", {}) or {}
                for attribute in (
                        html_attribute("data-typography-font-asset", asset.get("path")),
                        html_attribute("data-typography-font-sha256", asset.get("sha256"))):
                    if type_tag is None or attribute not in type_tag:
                        bad.append("verified typography specimen HTML is stale")
                style_match = re.search(
                    r'<style\b[^>]*data-typography-font-asset="[^"]+"[^>]*>'
                    r'.*?url\("(data:font/[^;]+;base64,([A-Za-z0-9+/=]+))"\).*?</style>',
                    type_section, re.S,
                )
                if not style_match:
                    bad.append("verified typography specimen is not embedded")
                else:
                    try:
                        embedded_payload = base64.b64decode(
                            style_match.group(2), validate=True)
                    except (ValueError, binascii.Error):
                        bad.append("embedded typography specimen is not valid base64")
                    if (embedded_payload is not None and embedded_asset is not None and
                            embedded_payload != embedded_asset):
                        bad.append("embedded typography specimen differs from repository asset")
            for evidence in typography.get("evidence", []) or []:
                if html_attribute("data-typography-evidence", evidence) not in type_section:
                    bad.append("typography evidence is missing from HTML: %s" % evidence)
            candidates = typography.get("candidates", []) or []
            if candidates and html_attribute(
                    "data-typography-candidates", len(candidates)) not in type_section:
                bad.append("typography candidate count is missing from HTML")
            for candidate in candidates:
                candidate_id = "%s:%s:%s" % (
                    candidate.get("token"), candidate.get("family"),
                    candidate.get("priority"),
                )
                candidate_tag = structured_tag(
                    type_section, "tr", "data-typography-candidate", candidate_id)
                if candidate_tag is None:
                    bad.append("typography candidate is missing from HTML: %s" % candidate_id)
                    continue
                for attribute in (
                        html_attribute("data-typography-candidate-token",
                                       candidate.get("token")),
                        html_attribute("data-typography-candidate-family",
                                       candidate.get("family")),
                        html_attribute("data-typography-candidate-priority",
                                       candidate.get("priority")),
                        json_html_attribute("data-typography-candidate-evidence-json",
                                            candidate.get("evidence", []))):
                    if attribute not in candidate_tag:
                        bad.append("typography candidate HTML is stale: %s" % candidate_id)
                for evidence in candidate.get("evidence", []) or []:
                    if html_attribute(
                            "data-typography-candidate-evidence", evidence) not in type_section:
                        bad.append("typography candidate evidence is missing: %s" % evidence)

        color_match = re.search(
            r'<!-- SLOT:inventory-color -->.*?<!-- /SLOT:inventory-color -->',
            html, re.S,
        )
        color_section = color_match.group(0) if color_match else ""
        if not color_section:
            bad.append("HTML has no brand color identity section")
        elif html_attribute("data-brand-state", brand.get("state")) not in color_section:
            bad.append("brand color identity state disagrees with HTML")
        brand_tag = structured_tag(
            color_section, "div", "data-brand-state", brand.get("state"))
        if (brand_tag is None or
                json_html_attribute("data-brand-subject-namespaces-json",
                                    brand.get("subject_namespaces", [])) not in brand_tag):
            bad.append("brand product-namespace evidence disagrees with HTML")
        if (brand.get("state") == "blocked" and
                ('data-brand-color="' in color_section or
                 "data-brand-swatches" in color_section or
                 re.search(r'class="[^"]*\bsw\b', color_section))):
            bad.append("blocked brand identity renders a generic swatch")
        for item in colors:
            marker = html_attribute("data-brand-color", item.get("token"))
            match = re.search(
                r'<div\b[^>]*%s[^>]*>' % re.escape(marker), color_section)
            if not match:
                bad.append("brand color is missing from HTML: %s" % item.get("token"))
                continue
            tag = match.group(0)
            for attribute in (
                    html_attribute("data-brand-value", item.get("value")),
                    html_attribute("data-brand-confidence", item.get("confidence")),
                    json_html_attribute("data-brand-evidence-json",
                                        item.get("evidence", []))):
                if attribute not in tag:
                    bad.append("brand color HTML is stale: %s" % item.get("token"))
            for evidence in item.get("evidence", []) or []:
                if html_attribute("data-brand-evidence", evidence) not in color_section:
                    bad.append("brand evidence is missing from HTML: %s" % evidence)
        for item in conflicts:
            conflict_tag = structured_tag(
                color_section, "tr", "data-brand-conflict", item.get("token"))
            if conflict_tag is None:
                bad.append("brand conflict is missing from HTML: %s" % item.get("token"))
                continue
            for attribute in (
                    json_html_attribute("data-brand-conflict-values-json",
                                        item.get("values", [])),
                    json_html_attribute("data-brand-conflict-evidence-json",
                                        item.get("evidence", []))):
                if attribute not in conflict_tag:
                    bad.append("brand conflict HTML is stale: %s" % item.get("token"))
            for evidence in item.get("evidence", []) or []:
                if html_attribute("data-brand-conflict-evidence", evidence) not in color_section:
                    bad.append("brand conflict evidence is missing from HTML: %s" % evidence)
    if bad:
        return Failure(
            "16-identity-integrity",
            "%d identity integrity problem(s)" % len(bad),
            bad[:12],
        )
    return None


def rule_17_adoption_strategy(doc, html=None):
    """The closing unification strategy must be evidence-derived and complete."""
    if get(doc, "discovery", "engine", "name") != "universal-profile-engine":
        return None
    actual = doc.get("adoption_strategy")
    expected = derive_adoption_strategy(doc)
    bad = []
    if not isinstance(actual, dict):
        return Failure(
            "17-adoption-strategy",
            "the universal report has no adoption_strategy object",
        )
    if actual != expected:
        bad.append("adoption_strategy does not match the report evidence")
    if [item.get("id") for item in actual.get("rollout", [])] != PHASE_IDS:
        bad.append("rollout phases are missing, duplicated, or out of order")
    expected_standards = [item["id"] for item in STANDARDS]
    if [item.get("id") for item in actual.get("standards", [])] != expected_standards:
        bad.append("standards baseline is missing or reordered")
    if actual.get("standards") != STANDARDS:
        bad.append("standard names, roles, or URLs have drifted")
    if len(actual.get("target_architecture", [])) != 5:
        bad.append("target architecture does not contain all five layers")
    if [item.get("id") for item in actual.get(
            "integration_constraints", [])] != CONSTRAINT_IDS:
        bad.append("integration constraints are missing, duplicated, or out of order")
    if len(actual.get("success_metrics", [])) != 5:
        bad.append("success measures do not contain all five baselines")
    if len(actual.get("guardrails", [])) != 6:
        bad.append("strategy guardrails do not contain all six rules")

    if html is not None:
        section_match = re.search(
            r'<section id="strategy"[^>]*>.*?</section>', html, re.S)
        section = section_match.group(0) if section_match else ""
        if not section:
            bad.append("HTML has no final strategy section")
        else:
            if section_match.start() > html.find("<footer>"):
                bad.append("strategy section does not appear before the footer")
            if json_html_attribute("data-adoption-strategy-json", actual) not in section:
                bad.append("structured strategy JSON is missing or stale in HTML")
            if html_attribute("data-report-region", "adoption-strategy") not in section:
                bad.append("adoption strategy region is unrendered")
            for item in actual.get("target_architecture", []):
                if html_attribute("data-strategy-layer", item.get("id")) not in section:
                    bad.append("architecture layer is missing from HTML: %s" % item.get("id"))
            for item in actual.get("integration_constraints", []):
                if html_attribute(
                        "data-strategy-constraint", item.get("id")) not in section:
                    bad.append(
                        "integration constraint is missing from HTML: %s"
                        % item.get("id")
                    )
            for item in actual.get("rollout", []):
                marker = html_attribute("data-rollout-phase", item.get("id"))
                order = html_attribute("data-rollout-order", item.get("phase"))
                if marker not in section or order not in section:
                    bad.append("rollout phase is missing or stale in HTML: %s" % item.get("id"))
            for item in actual.get("standards", []):
                if html_attribute("data-strategy-standard", item.get("id")) not in section:
                    bad.append("standard is missing from HTML: %s" % item.get("id"))
                if html_attribute("href", item.get("url")) not in section:
                    bad.append("standard URL is missing from HTML: %s" % item.get("id"))
            for item in actual.get("success_metrics", []):
                if html_attribute("data-strategy-metric", item.get("id")) not in section:
                    bad.append("success measure is missing from HTML: %s" % item.get("id"))
    if bad:
        return Failure(
            "17-adoption-strategy",
            "%d adoption-strategy problem(s)" % len(bad),
            bad[:12],
        )
    return None


def validate(doc, html=None, current_skill=False, artifacts=None):
    checks = [
        rule_1_discovery_evidence(doc),
        rule_2_reachability(doc),
        rule_3_mode_resolution(doc),
        rule_4_no_zero_for_unmeasured(doc),
        rule_5_family_coverage(doc),
        rule_6_html_matches_json(doc, html),
        rule_7_fix_queue_integrity(doc),
        rule_8_html_holds_every_finding(doc, html),
        rule_9_no_unescaped_markup(html),
        rule_10_root_evidence(doc),
        rule_11_capability_contract(doc),
        rule_12_unresolved_classification(doc),
        rule_13_component_usage(doc, html),
        rule_14_profile_engine(doc, html, current_skill),
        rule_15_source_artifact_parity(doc, artifacts),
        rule_16_identity_integrity(doc, html),
        rule_17_adoption_strategy(doc, html),
        rule_18_no_template_sample_content(html),
    ]
    return [c for c in checks if c is not None]


def rule_18_no_template_sample_content(html):
    """The report still describes the template's imaginary codebase.

    This lived inside rule 16, so a report carrying `a91f4c07` was told it
    had an identity-integrity problem — which points a reader at the font
    and brand evidence rather than at the region they forgot to fill.
    """
    if html is None:
        return None
    sentinels = [value for value in FINISHED_REPORT_SENTINELS if value in html]
    if not sentinels:
        return None
    return Failure(
        "18-template-sample-content",
        "%d region(s) still hold the template's own sample content" % len(sentinels),
        sentinels[:8],
    )


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("report_json")
    ap.add_argument("--html", dest="html")
    ap.add_argument("--discovery")
    ap.add_argument("--tokens")
    ap.add_argument("--components")
    ap.add_argument("--leakage")
    ap.add_argument("--interaction")
    ap.add_argument(
        "--current-skill", action="store_true",
        help="fail when provenance.skill_version differs from this installed skill",
    )
    ap.add_argument(
        "--stamp", action="store_true",
        help="on a passing run, write provenance.validation_gate into report_json and "
             "clear the report.html validation banner. Never stamps a failing run.",
    )
    add_json_flag(ap)
    args = ap.parse_args(argv)

    with open(args.report_json, encoding="utf-8") as fh:
        doc = json.load(fh)
    html = None
    if args.html:
        with open(args.html, encoding="utf-8") as fh:
            html = fh.read()

    directory = os.path.dirname(os.path.abspath(args.report_json))
    artifact_paths = {
        "discovery": args.discovery or os.path.join(directory, "discovery.json"),
        "tokens": args.tokens or os.path.join(directory, "tokens.json"),
        "components": args.components or os.path.join(directory, "components.json"),
        "leakage": args.leakage or os.path.join(directory, "literal-colors.json"),
        "interaction": args.interaction or os.path.join(directory, "interaction-check.json"),
    }
    artifacts = {}
    for name, path in artifact_paths.items():
        explicit = getattr(args, name) is not None
        if explicit or os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                artifacts[name] = json.load(fh)
    artifacts["_report_json_sha256"] = file_sha256(args.report_json)
    report_html_path = args.html or os.path.join(directory, "report.html")
    if os.path.exists(report_html_path):
        artifacts["_report_html_sha256"] = file_sha256(report_html_path)

    failures = validate(doc, html, args.current_skill, artifacts)
    emit_json(args.json_out, {
        "passed": not failures,
        "failures": [{"rule": f.rule, "message": f.message, "detail": f.detail} for f in failures],
    })
    if not failures:
        print("validate: pass — all eighteen rules hold")
        if args.stamp:
            checked_at = stamp_pass(
                args.report_json, doc,
                report_html_path if os.path.exists(report_html_path) else None,
                html)
            print("stamp: provenance.validation_gate.passed = true (%s)" % checked_at)
        return EXIT_OK
    for f in failures:
        print("FAIL  %-22s %s" % (f.rule, f.message))
        for line in f.detail:
            print("%26s%s" % ("", line))
    print("\n%d of 17 rules failed. The report claims more than the run established." % len(failures))
    return EXIT_FINDING


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
