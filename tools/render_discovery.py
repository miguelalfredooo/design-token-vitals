#!/usr/bin/env python3
"""Merge universal discovery results into JSON and render profile evidence."""
import argparse
import base64
import datetime
import hashlib
import html
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_OK  # noqa: E402
from discover_tokens import (  # noqa: E402
    MAX_EMBEDDED_FONT_BYTES,
    matching_font_asset_evidence,
    verified_font_file,
)
from version import describe  # noqa: E402


SECTION = re.compile(r'\n\s*<section id="discovery-engine">.*?</section>\n', re.S)
LEAKAGE_SECTION = re.compile(
    r'\n\s*<section(?: id="leakage")?>\s*<div class="eyebrow">Leakage</div>.*?</section>\n', re.S)
MEASUREMENT_MARKER = '<section id="measurement">'
LEGACY_MEASUREMENT_MARKER = '<section>\n    <div class="eyebrow">Measurement</div>'
SLOT = r'(<!-- SLOT:%s -->).*?(<!-- /SLOT:%s -->)'
TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "report-template.html",
)
TEMPLATE_INSTRUCTIONS = re.compile(
    r'(\A<!doctype html>\s*)<!--\s*design-token-vitals report template\..*?-->\s*',
    re.S,
)
VITAL_ORDER = [
    "tier-integrity", "leakage", "coverage", "mode-completeness",
    "naming-coherence", "single-source", "orphans", "enforcement",
]


INVENTORY_TABS_SCRIPT = """<script data-token-vitals-ui="inventory-tabs">
(() => {
  const roots = Array.from(document.querySelectorAll("[data-token-inventory-tabs]"));

  const activate = (root, tab, moveFocus, updateHash) => {
    const tabs = Array.from(root.querySelectorAll('[role="tab"]'));
    const panels = Array.from(root.querySelectorAll('[role="tabpanel"]'));
    const panelId = tab.getAttribute("aria-controls");

    tabs.forEach((item) => {
      const selected = item === tab;
      item.setAttribute("aria-selected", String(selected));
      item.tabIndex = selected ? 0 : -1;
    });
    panels.forEach((panel) => {
      panel.hidden = panel.id !== panelId;
    });
    if (moveFocus) {
      tab.focus();
    }
    if (updateHash && window.location.hash !== `#${panelId}`) {
      window.history.replaceState(null, "", `#${panelId}`);
    }
  };

  const tabForHash = (root) => {
    const panelId = window.location.hash.slice(1);
    return Array.from(root.querySelectorAll('[role="tab"]')).find(
      (tab) => tab.getAttribute("aria-controls") === panelId
    );
  };

  roots.forEach((root) => {
    const tabs = Array.from(root.querySelectorAll('[role="tab"]'));
    if (!tabs.length) {
      return;
    }
    root.classList.add("token-tabs--ready");
    activate(
      root,
      tabForHash(root) || tabs.find((tab) => tab.getAttribute("aria-selected") === "true") || tabs[0],
      false,
      false
    );

    root.addEventListener("click", (event) => {
      const tab = event.target.closest('[role="tab"]');
      if (tab && root.contains(tab)) {
        activate(root, tab, false, true);
      }
    });

    root.addEventListener("keydown", (event) => {
      const tab = event.target.closest('[role="tab"]');
      if (!tab || !root.contains(tab)) {
        return;
      }
      const current = tabs.indexOf(tab);
      let next = current;
      if (event.key === "ArrowRight") {
        next = (current + 1) % tabs.length;
      } else if (event.key === "ArrowLeft") {
        next = (current - 1 + tabs.length) % tabs.length;
      } else if (event.key === "Home") {
        next = 0;
      } else if (event.key === "End") {
        next = tabs.length - 1;
      } else {
        return;
      }
      event.preventDefault();
      activate(root, tabs[next], true, true);
    });
  });

  window.addEventListener("hashchange", () => {
    roots.forEach((root) => {
      const tab = tabForHash(root);
      if (tab) {
        activate(root, tab, false, false);
      }
    });
  });

  let printDisclosureState = [];
  window.addEventListener("beforeprint", () => {
    if (printDisclosureState.length) {
      return;
    }
    printDisclosureState = Array.from(document.querySelectorAll("details")).map(
      (disclosure) => [disclosure, disclosure.open]
    );
    printDisclosureState.forEach(([disclosure]) => {
      disclosure.open = true;
    });
  });
  window.addEventListener("afterprint", () => {
    printDisclosureState.forEach(([disclosure, wasOpen]) => {
      disclosure.open = wasOpen;
    });
    printDisclosureState = [];
  });
})();
</script>"""


def esc(value):
    return html.escape(str(value), quote=True)


def json_attr(value):
    return esc(json.dumps(value, sort_keys=True, separators=(",", ":")))


def token_sources(tokens):
    sources = []
    for item in tokens.get("sources", []) if tokens else []:
        role = item.get("role")
        classification = role if role in {"canonical", "alias"} else "consumer"
        sources.append({
            "path": item.get("path"),
            "classification": classification,
            "reachable_from": item.get("reachable_from") or [],
            "confidence": item.get("confidence"),
            "declarations": item.get("declarations"),
        })
    return sources


def enrich(discovery, tokens=None):
    result = json.loads(json.dumps(discovery))
    if tokens is not None:
        sources = token_sources(tokens)
        result["token_sources"] = sources
        confirmed_sources = [
            item for item in sources
            if item["classification"] in {"canonical", "alias"}
        ]
        has_sources = bool(confirmed_sources)
        capabilities = result.get("capabilities", {})
        roots_complete = capabilities.get("production_roots") == "verified"
        imports_complete = capabilities.get("import_resolution") == "verified"
        state = (
            "verified" if has_sources and roots_complete and imports_complete else
            "blocked"
        )
        result.setdefault("capabilities", {})["token_source_discovery"] = state
        for step in result.get("capability_ladder", {}).get("steps", []):
            if step.get("capability") == "token_source_discovery":
                step["state"] = state
                step["evidence"] = [
                    item["path"] for item in confirmed_sources[:8]
                ]
                step["limitation"] = (
                    None if state == "verified" else
                    ("Reachable token sources were found, but production-root or import-graph evidence is incomplete."
                     if has_sources else
                     "No reachable canonical token source was confirmed.")
                )
                step["next_step"] = (
                    "Deduplicate projections and classify every foundational family."
                    if state == "verified" else
                    "Confirm a reachable token source before grading."
                )
                break
    return result


def profile_cards(discovery):
    cards = []
    for profile in discovery.get("profile_composition", {}).get("active", []):
        evidence = "<br>".join(
            '<span class="path">%s%s</span> — %s' % (
                esc(item.get("path", "?")),
                (":%s" % esc(item["line"]) if item.get("line") else ""),
                esc(item.get("matched", "evidence")),
            ) for item in profile.get("evidence", [])
        ) or "Explicitly selected; repository evidence remains to be confirmed."
        cards.append(
            '<div class="panel" data-profile="%s" data-profile-confidence="%s" '
            'data-profile-kind="%s" data-profile-activation="%s" '
            'data-profile-score="%s" data-profile-evidence-json="%s" '
            'data-profile-contexts-json="%s">'
            '<h3>%s</h3><p class="sub">%s · %s · confidence %s · contexts %s</p>'
            '<p>%s</p></div>' % (
                esc(profile.get("id")), esc(profile.get("confidence")),
                esc(profile.get("kind")), esc(profile.get("activation")),
                esc(profile.get("score")), json_attr(profile.get("evidence", [])),
                json_attr(profile.get("contexts", [])),
                esc(profile.get("id")), esc(profile.get("kind")),
                esc(profile.get("activation")), esc(profile.get("confidence")),
                esc(", ".join(profile.get("contexts", [])) or "."), evidence,
            )
        )
    return "".join(cards)


def candidate_rows(discovery):
    rows = []
    for profile in discovery.get("profile_composition", {}).get("candidates", []):
        evidence = " · ".join(
            "%s%s" % (
                esc(item.get("path", "?")),
                (":%s" % esc(item["line"]) if item.get("line") else ""),
            ) for item in profile.get("evidence", [])
        ) or "—"
        missing = " · ".join(
            esc(json.dumps(item, sort_keys=True, separators=(",", ":")))
            for item in profile.get("missing_signals", [])
        ) or "—"
        rows.append(
            '<tr data-profile-candidate="%s" data-profile-candidate-kind="%s" '
            'data-profile-candidate-score="%s" data-profile-candidate-evidence-json="%s" '
            'data-profile-candidate-missing-json="%s"><td><code>%s</code></td>'
            '<td>%s</td><td>%.3f</td><td>%s</td><td>%s</td></tr>' % (
                esc(profile.get("id")), esc(profile.get("kind")),
                esc(profile.get("score")), json_attr(profile.get("evidence", [])),
                json_attr(profile.get("missing_signals", [])), esc(profile.get("id")),
                esc(profile.get("kind")), float(profile.get("score", 0)),
                evidence, missing,
            )
        )
    return "".join(rows)


def application_rows(discovery):
    rows = []
    composition = discovery.get("profile_composition", {})
    selected = (composition.get("application_selection", {}) or {}).get("selected")
    embedded = {item.get("path") for item in
                composition.get("embedded_applications", [])}
    for application in composition.get("application_candidates", []):
        path = application.get("path")
        selection = ("selected" if path == selected else
                     ("embedded layer" if path in embedded else "candidate"))
        rows.append(
            '<tr data-application-candidate="%s" data-application-package="%s" '
            'data-application-markers-json="%s" data-application-profiles-json="%s" '
            'data-application-selection="%s"><td><code>%s</code></td>'
            '<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                esc(path), esc(application.get("package") or ""),
                json_attr(application.get("markers", [])),
                json_attr(application.get("profiles", [])), esc(selection), esc(path),
                esc(application.get("package") or "—"),
                esc(", ".join(application.get("markers", [])) or "—"),
                esc(", ".join(application.get("profiles", [])) or "—"),
                esc(selection),
            )
        )
    return "".join(rows)


def registry_rows(discovery):
    return "".join(
        '<tr data-registry-source="%s" data-registry-sha256="%s">'
        '<td><code>%s</code></td><td><code>%s</code></td></tr>' % (
            esc(item.get("path")), esc(item.get("sha256")),
            esc(item.get("path")), esc(item.get("sha256")),
        )
        for item in discovery.get("profile_composition", {}).get(
            "registry_sources", [])
    )


def capability_rows(discovery):
    rows = []
    for step in discovery.get("capability_ladder", {}).get("steps", []):
        evidence = " · ".join(esc(item) for item in step.get("evidence", [])) or "—"
        limitation = esc(step.get("limitation") or "None recorded")
        contributors = ", ".join(esc(item) for item in step.get("contributors", []))
        rows.append(
            '<tr data-capability="%s" data-capability-state="%s" '
            'data-capability-contributors-json="%s" data-capability-evidence-json="%s" '
            'data-capability-limitation="%s" data-capability-next-step="%s">'
            '<td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                esc(step.get("capability")), esc(step.get("state")),
                json_attr(step.get("contributors", [])),
                json_attr(step.get("evidence", [])),
                esc(step.get("limitation") or ""), esc(step.get("next_step")),
                esc(step.get("capability")), esc(step.get("state")), contributors,
                evidence, limitation + " Next: " + esc(step.get("next_step")),
            )
        )
    return "".join(rows)


def conflict_rows(discovery):
    rows = []
    for item in discovery.get("profile_composition", {}).get("conflicts", []):
        rows.append(
            '<tr data-capability-conflict="%s" data-conflict-profiles-json="%s" '
            'data-conflict-states-json="%s" data-conflict-resolution="%s">'
            '<td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                esc(item.get("capability")), json_attr(item.get("profiles", [])),
                json_attr(item.get("states", [])), esc(item.get("resolution")),
                esc(item.get("capability")), esc(", ".join(item.get("profiles", []))),
                esc(", ".join(item.get("states", []))), esc(item.get("resolution")),
            )
        )
    return "".join(rows)


def root_rows(items, attribute="data-discovery-root"):
    rows = []
    for item in items:
        profiles = ", ".join(item.get("profiles", []))
        rows.append(
            '<tr %s="%s" data-root-type="%s" data-root-ownership="%s" '
            'data-root-confidence="%s" data-root-profiles-json="%s" '
            'data-root-evidence="%s"><td><code>%s</code></td><td>%s</td>'
            '<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                attribute, esc(item.get("path")), esc(item.get("root_type")),
                esc(item.get("ownership")), esc(item.get("confidence")),
                json_attr(item.get("profiles", [])), esc(item.get("evidence")),
                esc(item.get("path")),
                esc(item.get("root_type")), esc(item.get("ownership")),
                esc(item.get("confidence")), esc(profiles), esc(item.get("evidence")),
            )
        )
    return "".join(rows)


def auxiliary_rows(items, attribute):
    rows = []
    for item in items:
        rows.append(
            '<tr %s="%s" data-root-scope="%s" data-root-ownership="%s" '
            'data-root-confidence="%s" data-root-profiles-json="%s" '
            'data-root-evidence="%s"><td><code>%s</code></td><td>%s</td><td>%s</td>'
            '<td>%s</td><td>%s</td><td>%s</td></tr>' % (
                attribute, esc(item.get("path")),
                esc(item.get("scope", "component")), esc(item.get("ownership")),
                esc(item.get("confidence")), json_attr(item.get("profiles", [])),
                esc(item.get("evidence")), esc(item.get("path")),
                esc(item.get("scope", "component")), esc(item.get("ownership")),
                esc(item.get("confidence")),
                esc(", ".join(item.get("profiles", [])) or "—"),
                esc(item.get("evidence")),
            )
        )
    return "".join(rows)


def guidance_blocks(discovery):
    blocks = []
    for profile, guidance in discovery.get("profile_guidance", {}).items():
        rows = "".join(
            '<tr><td><code>%s</code></td><td>%s</td></tr>' % (esc(name), esc(value))
            for name, value in guidance.items()
        )
        blocks.append(
            '<details data-profile-guidance="%s"><summary>%s investigation guide</summary>'
            '<div class="details-body"><table><tbody>%s</tbody></table></div></details>' % (
                esc(profile), esc(profile), rows,
            )
        )
    return "".join(blocks)


def unresolved_rows(discovery):
    rows = []
    for item in discovery.get("import_graph", {}).get("unresolved", []):
        rows.append(
            '<tr data-unresolved-from="%s" data-unresolved-spec="%s" '
            'data-unresolved-reason="%s">'
            '<td><code>%s</code></td><td><code>%s</code></td><td>%s</td></tr>' % (
                esc(item.get("from") or "root"), esc(item.get("spec")),
                esc(item.get("reason")),
                esc(item.get("from") or "root"), esc(item.get("spec")),
                esc(item.get("reason")),
            )
        )
    return "".join(rows)


def replace_slot(document, name, body):
    pattern = re.compile(SLOT % (re.escape(name), re.escape(name)), re.S)
    if not pattern.search(document):
        return document
    return pattern.sub(lambda match: match.group(1) + body + match.group(2),
                       document, count=1)


def normalized_concepts(tokens):
    concepts = []
    for concept in tokens.get("concepts", []) if tokens else []:
        item = dict(concept)
        item["name"] = item.pop("id", item.get("name"))
        concepts.append(item)
    return concepts


def concept_rows(concepts):
    rows = []
    for concept in concepts:
        rows.append(
            '<tr data-token-concept="%s" data-token-family="%s" '
            'data-token-representations-json="%s" data-token-sites-json="%s" '
            'data-token-values-json="%s" data-token-definitions-json="%s">'
            '<td><code>%s</code></td><td>%s</td>'
            '<td>%s</td><td>%s</td><td>%s</td></tr>' % (
                esc(concept.get("name")), esc(concept.get("family")),
                json_attr(concept.get("representations", [])),
                json_attr(concept.get("sites", [])),
                json_attr(concept.get("values", [])),
                json_attr(concept.get("definitions", [])), esc(concept.get("name")),
                esc(concept.get("family")),
                esc(" · ".join(concept.get("representations", [])) or "—"),
                esc(" · ".join(str(value) for value in concept.get("values", [])) or "—"),
                "<br>".join('<span class="path">%s</span>' % esc(site)
                             for site in concept.get("sites", [])) or "—",
            )
        )
    return "".join(rows)


def concept_inventory_table(concepts, initial=20):
    headings = (
        '<thead><tr><th>Concept</th><th>Family</th><th>Representations</th>'
        '<th>Values</th><th>Canonical sites</th></tr></thead>'
    )
    visible = concepts[:initial]
    remainder = concepts[initial:]
    table = (
        '<div class="tbl-scroll"><table>%s<tbody>%s</tbody></table></div>' % (
            headings, concept_rows(visible))
    )
    if not remainder:
        return table
    return (
        '%s<details class="stack-16" data-token-inventory-more="%d">'
        '<summary>See %d more tokens</summary><div class="details-body">'
        '<div class="tbl-scroll"><table>%s<tbody>%s</tbody></table></div>'
        '</div></details>' % (
            table, len(remainder), len(remainder), headings,
            concept_rows(remainder),
        )
    )


def inventory_block(title, lede, concepts):
    return (
        '<div class="panel"><h3>%s</h3><p class="sub">%s</p>'
        '%s</div>' % (
            esc(title), esc(lede), concept_inventory_table(concepts))
    )


def embedded_font_asset(identity, repository_root):
    specimen = identity.get("specimen", {}) or {}
    asset = specimen.get("asset", {}) or {}
    if specimen.get("state") != "verified" or not repository_root:
        return None
    if not matching_font_asset_evidence(
            repository_root, identity.get("family"), asset):
        return None
    relative_path = asset.get("path")
    expected_sha = asset.get("sha256")
    if not relative_path or not expected_sha:
        return None
    root = os.path.realpath(repository_root)
    path = os.path.realpath(os.path.join(root, relative_path))
    try:
        contained = os.path.commonpath([root, path]) == root
    except ValueError:
        contained = False
    if not contained or not os.path.isfile(path):
        return None
    font_format = (asset.get("format") or os.path.splitext(path)[1].lstrip(".")).lower()
    if (os.path.getsize(path) > MAX_EMBEDDED_FONT_BYTES or
            not verified_font_file(path, font_format)):
        return None
    with open(path, "rb") as handle:
        payload = handle.read()
    actual_sha = hashlib.sha256(payload).hexdigest()
    if actual_sha != expected_sha:
        return None
    mime = {
        "woff2": "font/woff2", "woff": "font/woff", "ttf": "font/ttf",
        "otf": "font/otf",
    }.get(font_format)
    if not mime:
        return None
    return {
        "asset": asset,
        "data_uri": "data:%s;base64,%s" % (
            mime, base64.b64encode(payload).decode("ascii")),
        "format": font_format,
    }


def typography_block(concepts, identity, repository_root=None):
    identity = identity or {}
    verified = identity.get("state") == "verified"
    family = identity.get("family") if verified else None
    family_source = identity.get("token") if verified else None
    confidence = identity.get("confidence", "unresolved")
    identity_evidence = identity.get("evidence", []) or []
    embedded = embedded_font_asset(identity, repository_root) if verified else None
    specimen_state = "verified" if embedded else "blocked"
    candidates = identity.get("candidates", []) or []
    specimens = []
    for concept in concepts:
        if "font-size" not in concept.get("name", ""):
            continue
        concrete = next((
            str(value) for value in concept.get("values", [])
            if re.fullmatch(r"\d+(?:\.\d+)?(?:px|rem|em)", str(value).strip())
        ), None)
        if not concrete:
            continue
        unit = re.search(r"[a-z]+$", concrete).group(0)
        amount = float(re.match(r"\d+(?:\.\d+)?", concrete).group(0))
        pixels = amount * 16 if unit in {"rem", "em"} else amount
        specimens.append((pixels, concept.get("name"), concrete))
    specimen_rows = "".join(
        '<div class="ts-row" data-type-specimen-token="%s" '
        'data-type-specimen-value="%s" data-type-specimen-family="%s">'
        '<span class="tk">%s / %s</span><span class="spec" '
        'style="font-family:%s;font-size:%s">%s</span></div>' % (
            esc(name), esc(value), esc(family or "unresolved"), esc(name),
            esc(value), "Token Vitals Identity",
            esc(value), esc(family or "Font family unresolved"),
        )
        for _, name, value in sorted(specimens)[:12]
    ) if embedded else ""
    if embedded and not specimen_rows:
        specimen_rows = (
            '<div class="ts-row" data-type-specimen-token="%s" '
            'data-type-specimen-value="repository-family" '
            'data-type-specimen-family="%s"><span class="tk">%s</span>'
            '<span class="spec" style="font-family:Token Vitals Identity">%s</span>'
            '</div>' % (
                esc(family_source), esc(family), esc(family_source), esc(family),
            )
        )
    evidence_paths = "<br>".join(
        '<span class="path" data-typography-evidence="%s">%s</span>' % (
            esc(site), esc(site))
        for site in identity_evidence
    )
    candidate_rows = []
    for candidate in candidates:
        candidate_id = "%s:%s:%s" % (
            candidate.get("token"), candidate.get("family"),
            candidate.get("priority"),
        )
        candidate_evidence = candidate.get("evidence", []) or []
        candidate_rows.append(
            '<tr data-typography-candidate="%s" '
            'data-typography-candidate-token="%s" '
            'data-typography-candidate-family="%s" '
            'data-typography-candidate-priority="%s" '
            'data-typography-candidate-evidence-json="%s"><td><code>%s</code></td>'
            '<td>%s</td><td>%s</td><td>%s</td></tr>' % (
                esc(candidate_id), esc(candidate.get("token")),
                esc(candidate.get("family")), esc(candidate.get("priority")),
                json_attr(candidate_evidence), esc(candidate.get("token")),
                esc(candidate.get("family")), esc(candidate.get("priority")),
                "<br>".join(
                    '<span class="path" data-typography-candidate-evidence="%s">%s</span>' % (
                        esc(site), esc(site)) for site in candidate_evidence
                ) or "—",
            )
        )
    candidate_content = (
        '<details class="stack-16" data-typography-candidates="%d"%s>'
        '<summary>Typography identity candidates (%d)</summary><div class="details-body">'
        '<div class="tbl-scroll"><table><thead><tr><th>Token</th><th>Family</th>'
        '<th>Priority</th><th>Evidence</th></tr></thead><tbody>%s</tbody></table>'
        '</div></div></details>' % (
            len(candidates), " open" if not verified else "", len(candidates),
            "".join(candidate_rows),
        )
        if candidates else ""
    )
    evidence = (
        '<div class="note stack-16"><b>Verified family: %s.</b> '
        'Selected from <code>%s</code> with %s confidence. The specimen uses '
        'the verified repository font asset, never a local or generic fallback.%s</div>' % (
            esc(family), esc(family_source), esc(confidence),
            ("<br>" + evidence_paths) if evidence_paths else "",
        )
        if verified and embedded else
        '<div class="note stack-16"><b>Verified family: %s; specimen blocked.</b> '
        '%s No local or generic fallback is rendered.%s</div>' % (
            esc(family), esc((identity.get("specimen", {}) or {}).get("note") or
                             "The repository font asset could not be verified."),
            ("<br>" + evidence_paths) if evidence_paths else "",
        )
        if verified else
        '<div class="note stack-16"><b>Typography identity is blocked.</b> %s '
        'No substitute or inherited font is rendered.</div>' % esc(
            identity.get("note") or
            "No concrete reachable font-family token was confirmed."
        )
    )
    font_style = (
        '<style data-typography-font-asset="%s" data-font-sha256="%s">'
        '@font-face{font-family:"Token Vitals Identity";src:url("%s") format("%s");'
        'font-style:normal;font-weight:100 1000;font-display:block}</style>' % (
            esc(embedded["asset"].get("path")),
            esc(embedded["asset"].get("sha256")),
            embedded["data_uri"], esc(embedded["format"]),
        )
        if embedded else ""
    )
    specimen = (
        '%s<div class="typescale">%s</div>%s' % (
            font_style, specimen_rows, evidence)
        if embedded else evidence
    )
    return (
        '<div class="panel" data-typography-state="%s" '
        'data-typography-family="%s" data-typography-token="%s" '
        'data-typography-confidence="%s" data-typography-evidence-json="%s" '
        'data-typography-specimen-state="%s" data-typography-font-asset="%s" '
        'data-typography-font-sha256="%s">'
        '<h3>Typography identity</h3>'
        '<p class="sub">%d canonical concepts · %s</p>%s%s'
        '<div class="stack-16">%s</div></div>' % (
            esc(identity.get("state", "blocked")), esc(family or ""),
            esc(family_source or ""), esc(confidence), json_attr(identity_evidence),
            esc(specimen_state),
            esc(embedded["asset"].get("path") if embedded else ""),
            esc(embedded["asset"].get("sha256") if embedded else ""),
            len(concepts), esc(family or "identity not verified"), specimen,
            candidate_content,
            concept_inventory_table(concepts),
        )
    )


def color_block(concepts, identity):
    identity = identity or {}
    colors = identity.get("colors", []) or []
    conflicts = identity.get("conflicts", []) or []
    subject_namespaces = identity.get("subject_namespaces", []) or []
    subject_labels = [
        item.get("namespace") for item in subject_namespaces
        if isinstance(item, dict) and item.get("namespace")
    ]
    state = identity.get("state", "blocked")
    confidence = identity.get("confidence", "unresolved")
    swatches = []
    evidence_rows = []
    for item in colors:
        token = item.get("token")
        value = item.get("value")
        item_confidence = item.get("confidence")
        evidence = item.get("evidence", []) or []
        swatches.append(
            '<div class="sw" data-brand-color="%s" data-brand-value="%s" '
            'data-brand-confidence="%s" data-brand-evidence-json="%s">'
            '<i style="background:%s" title="%s"></i><b>%s</b><span>%s</span>'
            '</div>' % (
                esc(token), esc(value), esc(item_confidence), json_attr(evidence),
                esc(value), esc(value), esc(token), esc(value),
            )
        )
        evidence_rows.append(
            '<tr data-brand-evidence-token="%s"><td><code>%s</code></td>'
            '<td><span class="out out--mini"><i style="background:%s"></i></span> '
            '<code>%s</code></td><td>%s</td><td>%s</td></tr>' % (
                esc(token), esc(token), esc(value), esc(value),
                esc(item_confidence),
                "<br>".join(
                    '<span class="path" data-brand-evidence="%s">%s</span>' % (
                        esc(site), esc(site))
                    for site in evidence
                ) or "—",
            )
        )
    conflict_rows = []
    for item in conflicts:
        token = item.get("token")
        values = item.get("values", []) or []
        evidence = item.get("evidence", []) or []
        conflict_rows.append(
            '<tr data-brand-conflict="%s" data-brand-conflict-values-json="%s" '
            'data-brand-conflict-evidence-json="%s"><td><code>%s</code></td>'
            '<td>%s</td><td>%s</td><td>%s</td></tr>' % (
                esc(token), json_attr(values), json_attr(evidence), esc(token),
                " · ".join("<code>%s</code>" % esc(value) for value in values),
                esc(item.get("reason") or "ambiguous brand value"),
                "<br>".join(
                    '<span class="path" data-brand-conflict-evidence="%s">%s</span>' % (
                        esc(site), esc(site)) for site in evidence
                ) or "—",
            )
        )
    conflict_content = (
        '<div class="note stack-16" data-brand-conflicts-blocked="%d">'
        '<b>%d brand token%s blocked by conflicting values.</b> These are not '
        'silently promoted into the palette.</div>'
        '<div class="tbl-scroll stack-16"><table><thead><tr><th>Blocked token</th>'
        '<th>Conflicting values</th><th>Reason</th><th>Evidence</th></tr></thead>'
        '<tbody>%s</tbody></table></div>' % (
            len(conflicts), len(conflicts), "s" if len(conflicts) != 1 else "",
            "".join(conflict_rows),
        )
        if conflicts else ""
    )
    if colors:
        brand_content = (
            '<p class="sub">%d explicitly declared brand tokens · %s%s</p>'
            '<div class="swatches" data-brand-swatches>%s</div>'
            '<div class="note stack-16"><b>Repository brand palette.</b> %s '
            'Broad names such as <code>primary</code> and <code>accent</code> are not '
            'included without explicit brand evidence.</div>'
            '<details class="stack-16"><summary>Why these colors qualify as brand</summary>'
            '<div class="details-body"><div class="tbl-scroll"><table><thead><tr>'
            '<th>Token</th><th>Color</th><th>Confidence</th><th>Evidence</th>'
            '</tr></thead><tbody>%s</tbody></table></div></div></details>%s' % (
                len(colors), esc(confidence),
                esc(" · audited product namespaces: %s" % ", ".join(subject_labels)
                    if subject_labels else ""),
                "".join(swatches),
                esc(identity.get("note") or "Explicit brand semantics confirmed."),
                "".join(evidence_rows), conflict_content,
            )
        )
    else:
        brand_content = (
            '<div class="note"><b>Brand color identity is blocked.</b> %s '
            'No generic palette is substituted.</div>%s' % (esc(
                identity.get("note") or
                "No concrete reachable color carried explicit brand semantics."
            ), conflict_content)
        )
    return (
        '<div class="panel" data-brand-state="%s" data-brand-confidence="%s" '
        'data-brand-subject-namespaces-json="%s">'
        '<h3>Brand identity colors</h3>%s</div>'
        '<div class="panel stack-26"><h3>Full color inventory</h3>'
        '<p class="sub">%d canonical concepts · repository values</p>'
        '%s</div>' % (
            esc(state), esc(confidence), json_attr(subject_namespaces), brand_content,
            len(concepts), concept_inventory_table(concepts),
        )
    )


def family_block(tokens, report):
    counts = tokens.get("family_counts", {})
    concepts = normalized_concepts(tokens)
    existing = report.get("inventory", {}).get("families", {}) or {}
    rows = []
    for family in sorted(counts):
        count = counts[family]
        state = "measured" if count else existing.get(family, {}).get(
            "state", "unmeasured")
        sources = sorted({site.rsplit(":", 1)[0]
                          for concept in concepts if concept.get("family") == family
                          for site in concept.get("sites", [])})
        source_tags = [
            '<span class="path" data-family-source="%s">%s</span>' % (
                esc(source), esc(source))
            for source in sources
        ]
        if len(source_tags) > 4:
            note = (
                "<br>".join(source_tags[:4]) +
                '<details><summary>Show %d more sources</summary><div>%s</div></details>' % (
                    len(source_tags) - 4, "<br>".join(source_tags[4:]))
            )
        elif source_tags:
            note = "<br>".join(source_tags)
        else:
            note = esc(
                existing.get(family, {}).get("note") or
                "No canonical concept was confirmed."
            )
        rows.append(
            '<tr data-family="%s" data-family-state="%s" data-family-count="%s" '
            'data-family-sources-json="%s">'
            '<td>%s</td><td>%s</td><td class="num">%s</td><td>%s</td></tr>' % (
                esc(family), esc(state), esc(count if count else ""),
                json_attr(sources),
                esc(family), esc(state), esc(count if count else "unmeasured"),
                note,
            )
        )
    unclassified = len([item for item in concepts
                        if item.get("family") == "unclassified"])
    rows.append(
        '<tr data-family="unclassified" data-family-state="measured" '
        'data-family-count="%d"><td>unclassified</td><td>measured</td>'
        '<td class="num">%d</td><td>Listed in the foundational inventory for review</td></tr>' %
        (unclassified, unclassified)
    )
    return (
        '<div class="tbl-scroll"><table class="fam"><thead><tr><th>Family</th>'
        '<th>State</th><th class="num">Concepts</th><th>Sources</th></tr></thead>'
        '<tbody>%s</tbody></table></div>' % "".join(rows)
    )


def sync_token_inventory(report, tokens):
    if not tokens:
        return
    concepts = normalized_concepts(tokens)
    inventory = report.setdefault("inventory", {})
    inventory["concepts"] = concepts
    inventory["unclassified_count"] = len([
        item for item in concepts if item.get("family") == "unclassified"])
    inventory["candidate_or_local_override_sources"] = tokens.get(
        "candidate_or_local_override_sources", [])
    inventory["identity"] = tokens.get("identity", {
        "typography": {
            "state": "blocked", "confidence": "unresolved",
            "family": None, "token": None, "evidence": [],
            "note": "Identity evidence was not produced by token discovery.",
        },
        "brand_colors": {
            "state": "blocked", "confidence": "unresolved", "colors": [],
            "note": "Identity evidence was not produced by token discovery.",
        },
    })
    families = inventory.setdefault("families", {})
    for family, count in tokens.get("family_counts", {}).items():
        entry = families.setdefault(family, {})
        family_concepts = [item for item in concepts
                           if item.get("family") == family]
        sources = sorted({
            site.rsplit(":", 1)[0]
            for item in family_concepts for site in item.get("sites", [])
        })
        entry.clear()
        if count:
            entry.update({
                "state": "measured", "count": count, "sources": sources,
                "tiers": {"primitive": None, "semantic": None},
                "note": None,
            })
        else:
            entry.update({
                "state": "unmeasured", "sources": [],
                "tiers": {"primitive": None, "semantic": None},
                "note": "No canonical concept was confirmed; held-out candidates may still contain local decisions.",
            })
    run = report.setdefault("run", {})
    run["token_count"] = tokens.get("concept_count", len(concepts))
    run["family_count"] = len(tokens.get("family_counts", {}))
    valid_names = {item.get("name") for item in concepts}
    if isinstance(report.get("lineage"), list):
        report["lineage"] = [item for item in report["lineage"]
                             if item.get("token") in valid_names]


def sync_leakage(report, leakage):
    if not leakage:
        return
    report["leakage_analysis"] = leakage
    scanned = leakage.get("consumer_files_scanned", 0)
    exact = len(leakage.get("exact_value_candidates", []))
    uncovered = len(leakage.get("uncovered_candidates", []))
    report.setdefault("run", {})["files_scanned"] = scanned
    report["run"]["scope"] = [
        "owned consumer style files reachable from proven product roots"
    ]
    report.setdefault("executive_summary", {}).setdefault(
        "affected", {})["owned_files"] = scanned
    leakage_vital = report.setdefault("vitals", {}).setdefault("leakage", {})
    leakage_vital.update({
        "grade": "blocked",
        "evidence": [],
        "note": (
            "%d exact-value candidate groups and %d uncovered candidate groups "
            "were measured across %d owned reachable consumer styles, but "
            "semantic equivalence and near misses remain unmeasured."
        ) % (exact, uncovered, scanned),
        "tiers": {
            "redundant": None,
            "exact-value candidate": exact,
            "near-miss": None,
            "uncovered": None,
            "uncovered candidate": uncovered,
        },
    })


def render_vitals(report):
    cards = []
    vitals = report.get("vitals", {}) or {}
    for name in VITAL_ORDER:
        vital = vitals.get(name, {}) or {}
        grade = vital.get("grade", "blocked")
        note = vital.get("note") or "No current evidence was recorded."
        evidence = vital.get("evidence") or []
        evidence_text = (
            ' <code>%s</code>' % esc(evidence[0]) if evidence else ""
        )
        cards.append(
            '<article class="vital" data-vital="%s" data-grade="%s">'
            '<span class="grade" data-g="%s">%s</span><h3>%s</h3>'
            '<p>%s%s</p></article>' % (
                esc(name), esc(grade), esc(grade), esc(grade),
                esc(name.replace("-", " ")), esc(note), evidence_text,
            )
        )
    return '<div class="vitals">%s</div>' % "".join(cards)


def stage_summary(report):
    stage = report.get("stage", {}) or {}
    current = stage.get("current") or "unresolved"
    next_stage = stage.get("next")
    threshold = stage.get("threshold") or "No next threshold was recorded."
    if next_stage:
        return (
            '<p class="stage-line"><code>%s</code> — current maturity stage. '
            '<b>Next:</b> %s. <b>Then:</b> <code>%s</code>.</p>' % (
                esc(current), esc(threshold.rstrip().rstrip(".!?")), esc(next_stage))
        )
    return '<p class="stage-line"><code>%s</code> — %s</p>' % (
        esc(current), esc(threshold))


def render_at_a_glance(report):
    stage = report.get("stage", {}) or {}
    vitals = report.get("vitals", {}) or {}
    grades = {}
    for vital in vitals.values():
        grade = vital.get("grade", "blocked")
        grades[grade] = grades.get(grade, 0) + 1
    confidence = report.get("executive_summary", {}).get(
        "confidence_split", {}) or {}
    leakage = report.get("leakage_analysis", {}) or {}
    run = report.get("run", {}) or {}
    families = report.get("inventory", {}).get("families", {}) or {}
    measured_families = len([
        item for item in families.values() if item.get("state") == "measured"
    ])
    grade_text = " · ".join(
        "%d %s" % (grades.get(name, 0), name)
        for name in ("pass", "attention", "fail", "blocked", "not_applicable")
        if grades.get(name, 0)
    ) or "No vitals graded"
    stage_order = ("scattered", "declared", "adopted", "layered", "complete", "held")
    current_stage = stage.get("current") or "unresolved"
    current_index = stage_order.index(current_stage) if current_stage in stage_order else -1
    ladder = "".join(
        '<i class="%s"></i>' % (
            "now" if index == current_index else "done" if index < current_index else "")
        for index in range(len(stage_order))
    )
    vital_total = max(sum(grades.values()), 1)
    grade_segments = "".join(
        '<i data-g="%s" style="width:%.3f%%"></i>' % (
            esc(name), 100.0 * grades.get(name, 0) / vital_total)
        for name in ("fail", "attention", "pass", "blocked", "not_applicable")
        if grades.get(name, 0)
    )
    confidence_keys = ("confirmed", "blocked", "unmeasured")
    confidence_total = max(sum(int(confidence.get(name, 0) or 0)
                               for name in confidence_keys), 1)
    confidence_segments = "".join(
        '<i data-k="%s" style="width:%.3f%%"></i>' % (
            name, 100.0 * int(confidence.get(name, 0) or 0) / confidence_total)
        for name in confidence_keys if confidence.get(name, 0)
    )
    exact_count = len(leakage.get("exact_value_candidates", []) or [])
    uncovered_count = len(leakage.get("uncovered_candidates", []) or [])
    leakage_total = max(exact_count + uncovered_count, 1)
    leakage_segments = (
        '<i data-t="candidate" style="width:%.3f%%"></i>'
        '<i data-t="uncovered" style="width:%.3f%%"></i>' % (
            100.0 * exact_count / leakage_total,
            100.0 * uncovered_count / leakage_total,
        )
    )
    queue = report.get("fix_queue", []) or []
    verified = len([item for item in queue if item.get("safe_to_automate")])
    ring_length = 125.7
    ring_filled = ring_length * verified / len(queue) if queue else 0
    return (
        '<div class="glance" data-report-region="at-a-glance" '
        'data-stage-json="%s">'
        '<div class="gcard"><div class="gt"><span>Stage</span><span>next: %s</span></div>'
        '<div class="gv"><code class="gstage">%s</code></div>'
        '<div class="ladder" data-glance-mark="stage" aria-label="Current maturity stage: %s">%s</div>'
        '<div class="gd">%s</div></div>'
        '<div class="gcard"><div class="gt"><span>Eight vitals</span><span>%d checks</span></div>'
        '<div class="seg" data-glance-mark="vitals">%s</div><div class="gd">%s</div></div>'
        '<div class="gcard"><div class="gt"><span>Confidence</span><span>evidence units</span></div>'
        '<div class="seg" data-glance-mark="confidence">%s</div>'
        '<div class="gd"><b>%s</b> confirmed · <b>%s</b> blocked · <b>%s</b> unmeasured</div></div>'
        '<div class="gcard"><div class="gt"><span>Leakage</span><span>%d consumer styles</span></div>'
        '<div class="seg" data-glance-mark="leakage">%s</div>'
        '<div class="gd"><b>%d</b> exact-value candidates · <b>%d</b> uncovered candidates</div></div>'
        '<div class="gcard"><div class="gt"><span>Fix queue</span><span>%d verified entries</span></div>'
        '<div class="ring" data-glance-mark="fix-queue" data-fix-total="%d" data-fix-verified="%d">'
        '<svg viewBox="0 0 52 52" aria-hidden="true"><circle class="track" cx="26" cy="26" r="20"></circle>'
        '<circle class="fill" cx="26" cy="26" r="20" stroke-dasharray="%.1f %.1f"></circle></svg>'
        '<div><div class="rv">%d<small> / %d</small></div><div class="rd">semantically verified</div></div></div></div>'
        '<div class="gcard" data-glance-mark="counted"><div class="gt"><span>Counted</span><span>%s tier</span></div>'
        '<div class="gv">%d<small>tokens</small></div><div class="gd"><b>%d</b> measured families · '
        '<b>%d</b> files scanned</div></div></div>' % (
            json_attr(stage), esc(stage.get("next") or "none"),
            esc(current_stage), esc(current_stage), ladder,
            esc(stage.get("threshold") or "No threshold recorded."),
            len(vitals), grade_segments, esc(grade_text), confidence_segments,
            esc(confidence.get("confirmed", 0)), esc(confidence.get("blocked", 0)),
            esc(confidence.get("unmeasured", 0)),
            leakage.get("consumer_files_scanned", 0), leakage_segments,
            exact_count, uncovered_count, verified,
            len(queue), verified, ring_filled, ring_length - ring_filled,
            verified, len(queue),
            esc(report.get("rendering", {}).get("tier", "unresolved")),
            run.get("token_count", 0), measured_families,
            run.get("files_scanned", 0),
        )
    )


def render_exec_summary(report):
    summary = report.get("executive_summary", {}) or {}
    highest = summary.get("highest_impact", {}) or {}
    affected = summary.get("affected", {}) or {}
    first = summary.get("fix_first", {}) or {}
    confidence = summary.get("confidence_split", {}) or {}
    waiting = confidence.get("waiting_on", []) or []
    return (
        '<div data-report-region="exec-summary" data-executive-summary-json="%s">%s'
        '<div class="exec"><div><dt>Highest impact</dt><dd><b>%s</b><br>'
        '<span class="p-mute">Finding %s · blast radius %s</span></dd></div>'
        '<div><dt>Affected</dt><dd><span class="big">%s</span> owned files<br>'
        '<span class="big">%s</span> components</dd></div>'
        '<div><dt>Fix first</dt><dd>%s<br><span class="path">%s</span></dd></div>'
        '<div><dt>Confidence of these results</dt><dd>%s confirmed · %s blocked · '
        '%s unmeasured<div class="p-mute">Waiting on: %s</div></dd></div></div></div>' % (
            json_attr(summary), stage_summary(report),
            esc(highest.get("statement") or "No highest-impact finding recorded."),
            esc(highest.get("finding_id") or "—"), esc(highest.get("blast_radius") or "—"),
            esc(affected.get("owned_files", 0)), esc(affected.get("components", 0)),
            esc(first.get("action") or "No semantically verified replacement is ready."),
            esc(first.get("file_line") or "—"),
            esc(confidence.get("confirmed", 0)), esc(confidence.get("blocked", 0)),
            esc(confidence.get("unmeasured", 0)),
            esc(" · ".join(waiting) or "nothing recorded"),
        )
    )


def render_decisions(report):
    decisions = report.get("decisions", []) or []
    if not decisions:
        body = '<div class="note">No close-call decisions were recorded.</div>'
    else:
        rows = []
        for index, item in enumerate(decisions):
            rows.append(
                '<div class="dec-row" data-decision-index="%d" data-decision-json="%s">'
                '<div><div class="what">%s</div><div class="moved">%s</div></div>'
                '<span class="vitals">%s</span><div class="other">%s</div></div>' % (
                    index, json_attr(item), esc(item.get("decision")),
                    esc(item.get("moved")),
                    esc(" · ".join(item.get("vitals", []) or []) or "report"),
                    esc(item.get("other_reading")),
                )
            )
        body = '<div class="dec">%s</div>' % "".join(rows)
    return '<div data-report-region="decisions">%s</div>' % body


def next_step_items(report):
    summary = report.get("executive_summary", {}) or {}
    first = summary.get("fix_first", {}) or {}
    discovery = report.get("discovery", {}) or {}
    roots = discovery.get("roots", []) or []
    unknown = [item for item in roots if item.get("ownership") == "unknown"]
    held_out = report.get("inventory", {}).get(
        "candidate_or_local_override_sources", []) or []
    mode_evidence = report.get("vitals", {}).get(
        "mode-completeness", {}).get("evidence", []) or []
    enforcement_evidence = report.get("vitals", {}).get(
        "enforcement", {}).get("evidence", []) or []
    unknown_start = "—"
    if unknown:
        evidence = unknown[0].get("evidence") or []
        unknown_start = evidence[0] if evidence else unknown[0].get("path", "—")
    held_start = held_out[0].get("path", "—") if held_out else "—"
    return [
        (first.get("action") or "Review the highest-impact candidate by semantic role.",
         first.get("file_line") or "—"),
        ("Produce compiled light and dark theme output for the registered bundle set.",
         mode_evidence[0] if mode_evidence else "—"),
        ("Resolve ownership for %d registered roots." % len(unknown), unknown_start),
        ("Classify %d held-out declaration sources as reusable tokens or local overrides." % len(held_out), held_start),
        ("Add token-aware lint enforcement after semantic replacement policy is defined.",
         enforcement_evidence[0] if enforcement_evidence else "package.json"),
    ]


def render_next_steps(report):
    items = next_step_items(report)
    rows = [
        '<tr><td>%s</td><td><span class="path">%s</span></td></tr>' % (
            esc(action), esc(location))
        for action, location in items
    ]
    return (
        '<div data-report-region="next-steps" data-next-steps-json="%s">'
        '<div class="tbl-scroll"><table>'
        '<thead><tr><th>Action</th><th>Evidence</th></tr></thead><tbody>%s</tbody>'
        '</table></div><div class="note stack-16"><b>The list stops at five.</b> '
        'Blocked measurements lead; reviewed replacements follow only when semantic intent is proven.'
        '</div></div>' % (json_attr(items), "".join(rows))
    )


def render_fix_queue(report):
    queue = report.get("fix_queue", []) or []
    if not queue:
        body = (
            '<div class="note"><b>No automatic fixes are ready.</b> Exact value equality '
            'does not prove semantic equivalence, so this run keeps every candidate out of the queue.</div>'
        )
    else:
        rows = []
        for index, item in enumerate(queue):
            location = (item.get("locations") or ["—"])[0]
            rows.append(
                '<tr data-finding="%s" data-fix-queue-index="%d" data-fix-queue-json="%s">'
                '<td><code>%s</code></td><td><span class="lit">%s</span></td>'
                '<td><span class="tok">%s</span></td><td>%s</td><td>%s</td>'
                '<td>%s</td><td><span class="path">%s</span></td></tr>' % (
                    esc(item.get("id")), index, json_attr(item), esc(item.get("id")),
                    esc(item.get("literal")), esc(item.get("replacement")),
                    esc(item.get("confidence")), esc(item.get("effort", "—")),
                    "automatable" if item.get("safe_to_automate") else "needs a person",
                    esc(location),
                )
            )
        body = (
            '<div class="tbl-scroll"><table><thead><tr><th>Finding</th><th>Literal</th>'
            '<th>Replacement</th><th>Confidence</th><th>Effort</th><th>Automation</th>'
            '<th>First location</th></tr></thead><tbody>%s</tbody></table></div>' % "".join(rows)
        )
    return '<div data-report-region="fix-queue">%s</div>' % body


def render_groups(report):
    groups = report.get("groups", {}) or {}
    rows = []
    index = 0
    for kind, items in groups.items():
        for item in items or []:
            name = item.get("name") or item.get("owner") or item.get("id") or "unnamed"
            findings = item.get("findings", []) or []
            rows.append(
                '<tr data-group-index="%d" data-group-kind="%s" data-group-json="%s">'
                '<td><code>%s</code></td><td>%s</td><td class="num">%d</td></tr>' % (
                    index, esc(kind), json_attr(item), esc(name), esc(kind), len(findings))
            )
            index += 1
    if rows:
        body = (
            '<div class="tbl-scroll"><table><thead><tr><th>Owner</th><th>Group</th>'
            '<th>Findings</th></tr></thead><tbody>%s</tbody></table></div>' % "".join(rows)
        )
    else:
        body = (
            '<div class="note">No ownership groups are claimed because no finding has a '
            'semantically verified replacement in the fix queue.</div>'
        )
    return '<div data-report-region="groups">%s</div>' % body


def lineage_rows(items, start=0):
    rows = []
    for index, item in enumerate(items, start=start):
        consumers = item.get("consumers", []) or []
        rows.append(
            '<tr data-lineage-index="%d" data-lineage-token="%s" data-lineage-json="%s">'
            '<td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td>'
            '<td class="num">%d</td><td>%s</td><td>%s</td></tr>' % (
                index, esc(item.get("token")), json_attr(item), esc(item.get("token")),
                esc(item.get("primitive") or "untraced"),
                esc(item.get("semantic") or "untraced"),
                esc(item.get("projection") or "untraced"), len(consumers),
                "complete" if item.get("complete") else "untraced",
                esc(item.get("note") or "—"),
            )
        )
    return "".join(rows)


def render_lineage(report, initial=20):
    lineage = report.get("lineage", []) or []
    headings = (
        '<thead><tr><th>Token</th><th>Primitive</th><th>Semantic</th><th>Projection</th>'
        '<th>Consumers</th><th>State</th><th>Note</th></tr></thead>'
    )
    body = '<div class="tbl-scroll"><table>%s<tbody>%s</tbody></table></div>' % (
        headings, lineage_rows(lineage[:initial]))
    if len(lineage) > initial:
        tail = lineage[initial:]
        body += (
            '<details class="stack-16"><summary>See %d more lineage records</summary>'
            '<div class="details-body"><div class="tbl-scroll"><table>%s<tbody>%s</tbody>'
            '</table></div></div></details>' % (
                len(tail), headings, lineage_rows(tail, start=initial))
        )
    if not lineage:
        body = '<div class="note">No lineage records were produced.</div>'
    return '<div data-report-region="lineage">%s</div>' % body


def render_coverage_matrix(report):
    matrix = report.get("coverage_matrix", {}) or {}
    bundles = matrix.get("bundles", []) or []
    modes = matrix.get("modes", []) or []
    families = matrix.get("families", []) or []
    cells = matrix.get("cells", []) or []
    keyed = {
        (item.get("bundle"), item.get("mode"), item.get("family")): item
        for item in cells
    }
    headers = "".join('<th class="fam">%s</th>' % esc(family) for family in families)
    rows = []
    for bundle in bundles:
        for mode in modes:
            columns = []
            for family in families:
                item = keyed.get((bundle, mode, family), {
                    "bundle": bundle, "mode": mode, "family": family,
                    "state": "unmeasured", "evidence": [],
                    "note": "No coverage cell was recorded.",
                })
                state = item.get("state", "unmeasured")
                label = {
                    "measured": "ok", "unmeasured": "?",
                    "blocked": "blk", "not_applicable": "n/a",
                }.get(state, "?")
                cell_id = "%s|%s|%s" % (bundle, mode, family)
                columns.append(
                    '<td class="cell" data-coverage-cell="%s" data-coverage-json="%s">'
                    '<span class="c" data-s="%s">%s</span></td>' % (
                        esc(cell_id), json_attr(item), esc(state), esc(label))
                )
            rows.append('<tr><td>%s · %s</td>%s</tr>' % (
                esc(bundle), esc(mode), "".join(columns)))
    return (
        '<div data-report-region="coverage-matrix"><div class="tbl-scroll"><table class="cm">'
        '<thead><tr><th>Bundle · mode</th>%s</tr></thead><tbody>%s</tbody></table></div>'
        '<div class="split stack-12"><span class="ok">measured</span>'
        '<span class="unk">unmeasured</span><span class="block">blocked</span></div></div>' % (
            headers, "".join(rows))
    )


def render_modes(report):
    matrix = report.get("coverage_matrix", {}) or {}
    cells = matrix.get("cells", []) or []
    states = {}
    for item in cells:
        state = item.get("state", "unmeasured")
        states[state] = states.get(state, 0) + 1
    coverage = (
        '<div data-report-region="modes-coverage" data-modes-json="%s" class="note">'
        '<b>Mode coverage is source-limited.</b> '
        '%d bundle × mode × family cells are recorded: %s. No source-only declaration is promoted '
        'to compiled runtime proof.</div>' % (
            json_attr(matrix), len(cells),
            esc(" · ".join("%d %s" % (count, state)
                           for state, count in sorted(states.items()))))
    )
    gaps = (
        '<div data-report-region="modes-gaps" data-modes-json="%s" class="note">'
        '<b>No mode gaps are claimed.</b> Provide compiled output for every registered bundle '
        'and scheme before individual missing values are graded.</div>' % json_attr(matrix)
    )
    return coverage, gaps


def render_orphans_and_enforcement(report):
    vitals = report.get("vitals", {}) or {}
    orphans = vitals.get("orphans", {}) or {}
    enforcement = vitals.get("enforcement", {}) or {}
    orphan_html = (
        '<div class="panel" data-report-region="orphans" data-vital-json="%s">'
        '<h3>Orphan measurement</h3>'
        '<p class="sub">%s</p><div class="note">%s</div></div>' % (
            json_attr(orphans), esc(orphans.get("grade", "blocked")),
            esc(orphans.get("note") or "No orphan evidence was recorded."))
    )
    enforcement_html = (
        '<div class="panel" data-report-region="enforcement" data-vital-json="%s">'
        '<h3>What protects this today</h3>'
        '<p class="sub">%s</p><div class="note">%s</div></div>' % (
            json_attr(enforcement), esc(enforcement.get("grade", "blocked")),
            esc(enforcement.get("note") or "No enforcement evidence was recorded."))
    )
    return orphan_html, enforcement_html


def render_report_slots(document, report, tokens, discovery):
    repository = discovery.get("repository", {}) or {}
    title = "Design Token Vitals — %s @ %s" % (
        os.path.basename(str(repository.get("root") or "repository")),
        str(repository.get("ref") or "unknown")[:10],
    )
    document = replace_slot(document, "doc-title", '<title>%s</title>' % esc(title))
    document = replace_slot(document, "at-a-glance", render_at_a_glance(report))
    document = replace_slot(document, "exec-summary", render_exec_summary(report))
    document = replace_slot(document, "decisions", render_decisions(report))
    document = replace_slot(document, "next-steps", render_next_steps(report))
    document = replace_slot(document, "fix-queue", render_fix_queue(report))
    document = replace_slot(document, "groups", render_groups(report))
    document = replace_slot(document, "lineage", render_lineage(report))
    document = replace_slot(
        document, "coverage-matrix", render_coverage_matrix(report))
    modes_coverage, modes_gaps = render_modes(report)
    document = replace_slot(document, "modes-coverage", modes_coverage)
    document = replace_slot(document, "modes-gaps", modes_gaps)
    orphan_html, enforcement_html = render_orphans_and_enforcement(report)
    document = replace_slot(document, "orphans", orphan_html)
    document = replace_slot(document, "enforcement", enforcement_html)
    document = replace_slot(
        document, "inventory-tabs-script", INVENTORY_TABS_SCRIPT)
    if tokens:
        document = replace_slot(
            document, "family-coverage", family_block(tokens, report))
    if not report.get("trend"):
        document = re.sub(r'\n\s*<section id="trend">.*?</section>\n', "\n", document, count=1, flags=re.S)
        document = re.sub(r'\s*<a href="#trend"[^>]*>.*?</a>', "", document, count=1)
    return document


def render_leakage(leakage):
    exact = leakage.get("exact_value_candidates", [])
    uncovered = leakage.get("uncovered_candidates", [])
    rows = []
    for item in exact + uncovered:
        candidates = " ".join(
            '<span class="tok">%s</span>' % esc(token)
            for token in item.get("token_candidates", [])
        ) or "—"
        locations = item.get("locations", [])
        location_tags = [
            '<span class="path" data-finding-location="%s">%s</span>' % (
                esc(location), esc(location))
            for location in locations
        ]
        if len(location_tags) > 1:
            location_html = (
                location_tags[0] +
                '<details><summary>Show %d more locations</summary><div>%s</div></details>' % (
                    len(location_tags) - 1, "<br>".join(location_tags[1:]))
            )
        else:
            location_html = location_tags[0] if location_tags else "—"
        rows.append(
            '<tr data-finding="%s" data-finding-tier="%s" '
            'data-finding-locations-json="%s" '
            'data-finding-token-candidates-json="%s" '
            'data-finding-properties-json="%s">'
            '<td><code>%s</code></td><td>%s</td><td>%s</td>'
            '<td class="num">%d</td><td class="num">%d</td>'
            '<td>%s</td><td>%s</td><td>%s</td></tr>' % (
                esc(item.get("id")), esc(item.get("tier")),
                json_attr(locations),
                json_attr(item.get("token_candidates", [])),
                json_attr(item.get("properties", [])),
                esc(item.get("literal")), esc(item.get("tier")), candidates,
                item.get("occurrences", 0), item.get("files", 0),
                esc(", ".join(item.get("properties", [])) or "unknown"),
                location_html,
                esc(item.get("note") or "Manual semantic review required."),
            )
        )
    return (
        '\n  <section id="leakage"><div class="eyebrow">Leakage</div>'
        '<h2>Hardcoded values, separated by what this run can prove</h2>'
        '<p class="lede">The fresh scan covers %d owned, graph-reachable consumer '
        'styles. It found %d exact-value candidate groups and %d groups with no '
        'exact reachable custom-property value. Semantic equivalence and near '
        'misses remain unmeasured.</p>'
        '<div class="note"><b>No automatic replacements are proposed.</b> '
        'Value equality is evidence for review, not proof of design intent.</div>'
        '<details open><summary>All %d measured leakage candidates</summary>'
        '<div class="details-body"><div class="tbl-scroll"><table><thead><tr>'
        '<th>Literal</th><th>Tier</th><th>Possible tokens</th><th>Uses</th>'
        '<th>Files</th><th>Properties</th><th>Locations</th><th>Interpretation</th>'
        '</tr></thead><tbody>%s</tbody></table></div></div></details></section>\n' % (
            leakage.get("consumer_files_scanned", 0), len(exact), len(uncovered),
            len(exact) + len(uncovered), "".join(rows),
        )
    )


def render_token_slots(document, tokens, report):
    if not tokens:
        return document
    concepts = normalized_concepts(tokens)
    document = replace_slot(document, "families", family_block(tokens, report))
    color = [item for item in concepts if item.get("family") == "color"]
    typography = [item for item in concepts
                  if item.get("family") == "typography"]
    foundation = [item for item in concepts
                  if item.get("family") not in {"color", "typography"}]
    identity = tokens.get("identity", {}) or {}
    document = replace_slot(
        document, "inventory-color",
        color_block(color, identity.get("brand_colors")))
    document = replace_slot(
        document, "inventory-type",
        typography_block(
            typography, identity.get("typography"),
            report.get("discovery", {}).get("repository", {}).get("root")))
    document = replace_slot(
        document, "inventory-space",
        inventory_block("Foundational inventory",
                        "%d non-color and non-typography concepts" % len(foundation),
                        foundation))
    return document


def sync_count_narratives(document, tokens):
    if not tokens:
        return document
    held_out = len(tokens.get("candidate_or_local_override_sources", []))
    return re.sub(
        r"Classify \d+ held-out declaration sources",
        "Classify %d held-out declaration sources" % held_out,
        document,
    )


def render_measurement(discovery, tokens, report, skill_version, generated):
    roots = discovery.get("roots", [])
    owned_roots = [item for item in roots if item.get("ownership") == "owned"]
    unknown_roots = [item for item in roots if item.get("ownership") == "unknown"]
    full_reachable = len(discovery.get("import_graph", {}).get("reachable", {}))
    owned_reachable = len(discovery.get("owned_import_graph", {}).get("reachable", {}))
    unresolved = discovery.get("import_graph", {}).get("unresolved", [])
    concept_count = (tokens or {}).get(
        "concept_count", report.get("run", {}).get("token_count"))
    source_count = len((tokens or {}).get("sources", []))
    held_out = len((tokens or {}).get("candidate_or_local_override_sources", []))
    adapters = report.get("provenance", {}).get("adapter_versions", {})
    summary = {
        "profiles": discovery.get("environment", []),
        "roots": len(roots), "owned_roots": len(owned_roots),
        "unknown_roots": len(unknown_roots),
        "reachable": full_reachable, "owned_reachable": owned_reachable,
        "unresolved": len(unresolved), "concepts": concept_count,
        "token_sources": source_count, "held_out_sources": held_out,
    }
    return (
        '<div class="panel" data-measurement-summary-json="%s"><h3>Measured scope</h3>'
        '<p>%d profiles proved %d product roots: %d owned and %d unresolved in '
        'ownership. The full graph reaches %d files; the owned graph reaches %d. '
        '%d imports remain classified, %s canonical concepts came from %d reachable '
        'token-bearing sources, and %d candidate or override sources were held out.</p>'
        '</div><div class="panel" style="margin-top:18px" '
        'data-adapter-versions-json="%s"><h3>Provenance</h3>'
        '<dl class="meta"><dt>schema</dt><dd>%s</dd><dt>skill</dt><dd>%s</dd>'
        '<dt>adapters</dt><dd>%s</dd><dt>repo</dt><dd>%s</dd>'
        '<dt>generated</dt><dd>%s</dd><dt>rendering</dt><dd>%s</dd></dl></div>' % (
            json_attr(summary), len(discovery.get("environment", [])), len(roots),
            len(owned_roots), len(unknown_roots), full_reachable, owned_reachable,
            len(unresolved), esc(concept_count if concept_count is not None else "unmeasured"),
            source_count, held_out,
            json_attr(adapters),
            esc(report.get("schema_version")), esc(skill_version),
            esc(" · ".join(sorted(adapters)) or "none"),
            esc(report.get("provenance", {}).get("repo_ref") or "unrecorded"),
            esc(generated), esc(report.get("rendering", {}).get("tier") or "unrecorded"),
        )
    )


def render_runhead(discovery, tokens, report, skill_version):
    roots = discovery.get("roots", [])
    summary = {
        "profiles": discovery.get("environment", []),
        "roots": len(roots),
        "owned_roots": len([item for item in roots
                            if item.get("ownership") == "owned"]),
        "reachable": len(discovery.get("import_graph", {}).get("reachable", {})),
        "owned_reachable": len(discovery.get("owned_import_graph", {}).get(
            "reachable", {})),
        "token_sources": len((tokens or {}).get("sources", [])),
        "concepts": (tokens or {}).get(
            "concept_count", report.get("run", {}).get("token_count")),
    }
    return (
        '<dl class="meta" data-runhead-summary-json="%s">'
        '<dt>profiles</dt><dd>%s</dd><dt>product roots</dt><dd>%d total · %d owned</dd>'
        '<dt>reachable source files</dt><dd>%d total · %d owned</dd>'
        '<dt>token inventory</dt><dd>%s concepts · %d token-bearing sources</dd>'
        '<dt>repository</dt><dd>%s</dd><dt>skill</dt><dd>%s</dd></dl>' % (
            json_attr(summary), esc(" · ".join(summary["profiles"])),
            summary["roots"], summary["owned_roots"], summary["reachable"],
            summary["owned_reachable"],
            esc(summary["concepts"] if summary["concepts"] is not None else "unmeasured"),
            summary["token_sources"],
            esc(report.get("provenance", {}).get("repo_ref") or "unrecorded"),
            esc(skill_version),
        )
    )


def render_footer(discovery, tokens, skill_version):
    owned_roots = len([item for item in discovery.get("roots", [])
                       if item.get("ownership") == "owned"])
    concept_count = (tokens or {}).get("concept_count", "unmeasured")
    summary = {
        "profiles": discovery.get("environment", []),
        "concepts": concept_count,
        "owned_reachable": len(discovery.get("owned_import_graph", {}).get(
            "reachable", {})),
        "owned_roots": owned_roots,
        "skill_version": skill_version,
    }
    return (
        '<span data-footer-summary-json="%s">profiles: %s</span>'
        '<span>%s concepts · %d owned reachable files · '
        '%d owned roots</span><span>%s</span>' % (
            json_attr(summary),
            esc(" · ".join(discovery.get("environment", []))), esc(concept_count),
            len(discovery.get("owned_import_graph", {}).get("reachable", {})),
            owned_roots, esc(skill_version),
        )
    )


def render_section(discovery):
    composition = discovery.get("profile_composition", {})
    selection = composition.get("application_selection", {}) or {}
    active = composition.get("active", [])
    roots = discovery.get("roots", [])
    root_candidates = discovery.get("root_candidates", [])
    missing_roots = discovery.get("missing_registered_roots", [])
    component_roots = discovery.get("component_roots", [])
    component_candidates = discovery.get("component_root_candidates", [])
    surfaces = discovery.get("surface_roots", [])
    unresolved = discovery.get("import_graph", {}).get("unresolved", [])
    candidates = composition.get("candidates", [])
    applications = composition.get("application_candidates", [])
    conflicts = composition.get("conflicts", [])
    registry_sources = composition.get("registry_sources", [])
    return """
  <section id="discovery-engine">
    <div class="eyebrow">Universal discovery</div>
    <h2>How the audit found the application</h2>
    <p class="lede">%d framework profiles composed into one evidence model. They proved %d product roots and %d owned component roots, while retaining %d disconnected root candidates, %d missing registered roots, and %d component-location candidates instead of silently promoting or discarding them. The report also keeps %d route, template, or demo surfaces outside production reachability.</p>
    <div class="note"><b>Application selection:</b> %s%s</div>
    <div class="grid-2 stack-16">%s</div>
    <details><summary>All %d framework-profile inputs</summary><div class="details-body"><div class="tbl-scroll"><table><thead><tr><th>Registry source</th><th>SHA-256</th></tr></thead><tbody>%s</tbody></table></div></div></details>
    <details><summary>All %d partial profile candidates retained as leads</summary><div class="details-body"><div class="tbl-scroll"><table><thead><tr><th>Profile</th><th>Kind</th><th>Signal score</th><th>Evidence found</th><th>Evidence still missing</th></tr></thead><tbody>%s</tbody></table></div></div></details>
    <details><summary>All %d workspace application candidates considered</summary><div class="details-body"><div class="tbl-scroll"><table><thead><tr><th>Path</th><th>Package</th><th>Framework markers</th><th>Profiles</th><th>Selection</th></tr></thead><tbody>%s</tbody></table></div></div></details>
    <div class="tbl-scroll stack-16"><table><thead><tr><th>Capability</th><th>State</th><th>Contributors</th><th>Evidence</th><th>Limitation and next move</th></tr></thead><tbody>%s</tbody></table></div>
    <details><summary>All %d profile capability conflicts</summary><div class="details-body"><div class="tbl-scroll"><table><thead><tr><th>Capability</th><th>Profiles</th><th>States</th><th>Resolution</th></tr></thead><tbody>%s</tbody></table></div></div></details>
    <details><summary>All %d product roots and their profile contributors</summary><div class="details-body"><div class="tbl-scroll"><table><thead><tr><th>Path</th><th>Type</th><th>Ownership</th><th>Confidence</th><th>Profiles</th><th>Evidence</th></tr></thead><tbody>%s</tbody></table></div></div></details>
    <details><summary>All %d disconnected product-root candidates</summary><div class="details-body"><p class="sub">These paths matched a convention or profile hint but were not proven reachable from a registered application entry.</p><div class="tbl-scroll"><table><thead><tr><th>Path</th><th>Type</th><th>Ownership</th><th>Confidence</th><th>Profiles</th><th>Evidence</th></tr></thead><tbody>%s</tbody></table></div></div></details>
    <details><summary>All %d registered roots missing from disk</summary><div class="details-body"><p class="sub">The framework or profile registered these paths, but the source file was absent. They block completeness until corrected or explicitly exempted.</p><div class="tbl-scroll"><table><thead><tr><th>Path</th><th>Type</th><th>Ownership</th><th>Confidence</th><th>Profiles</th><th>Evidence</th></tr></thead><tbody>%s</tbody></table></div></div></details>
    <details><summary>All %d evidenced component roots</summary><div class="details-body"><div class="tbl-scroll"><table><thead><tr><th>Path</th><th>Scope</th><th>Ownership</th><th>Confidence</th><th>Profiles</th><th>Evidence</th></tr></thead><tbody>%s</tbody></table></div></div></details>
    <details><summary>All %d component-root candidates outside owned scope</summary><div class="details-body"><p class="sub">These component locations are useful investigation leads, but they are excluded from owned grading until ownership is established.</p><div class="tbl-scroll"><table><thead><tr><th>Path</th><th>Scope</th><th>Ownership</th><th>Confidence</th><th>Profiles</th><th>Evidence</th></tr></thead><tbody>%s</tbody></table></div></div></details>
    <details><summary>All %d supplemental and demo surfaces</summary><div class="details-body"><div class="tbl-scroll"><table><thead><tr><th>Path</th><th>Scope</th><th>Ownership</th><th>Confidence</th><th>Profiles</th><th>Evidence</th></tr></thead><tbody>%s</tbody></table></div></div></details>
    <details><summary>All %d classified unresolved imports</summary><div class="details-body"><div class="tbl-scroll"><table><thead><tr><th>From</th><th>Spec</th><th>Reason</th></tr></thead><tbody>%s</tbody></table></div></div></details>
    <div class="stack-16">%s</div>
  </section>
""" % (
        len(active), len(roots), len(component_roots), len(root_candidates),
        len(missing_roots), len(component_candidates), len(surfaces),
        esc(selection.get("state")),
        (" — %s" % esc(selection.get("selected") or selection.get("reason"))
         if selection.get("selected") or selection.get("reason") else ""),
        profile_cards(discovery),
        len(registry_sources), registry_rows(discovery),
        len(candidates), candidate_rows(discovery),
        len(applications), application_rows(discovery),
        capability_rows(discovery),
        len(conflicts), conflict_rows(discovery),
        len(roots), root_rows(roots),
        len(root_candidates), root_rows(root_candidates, "data-root-candidate"),
        len(missing_roots), root_rows(missing_roots, "data-missing-root"),
        len(component_roots), auxiliary_rows(component_roots, "data-component-root"),
        len(component_candidates), auxiliary_rows(
            component_candidates, "data-component-root-candidate"),
        len(surfaces), auxiliary_rows(surfaces, "data-surface-root"),
        len(unresolved), unresolved_rows(discovery), guidance_blocks(discovery),
    )


def write_json(path, value):
    directory = os.path.dirname(os.path.abspath(path))
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False,
                                     encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=False)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, path)


def sync_document_metadata(document, old_generated, generated,
                           old_version, skill_version):
    if old_generated and old_generated in document:
        document = document.replace(old_generated, generated)
    else:
        document = re.sub(
            r'(<dt>generated</dt><dd>)[^<]+',
            lambda match: match.group(1) + esc(generated),
            document,
            count=1,
        )
    if old_version and old_version in document:
        document = document.replace(old_version, skill_version)
    else:
        document = re.sub(r'local-[0-9a-f]{12}', skill_version, document)
    return document


def augment(discovery_path, report_path, html_path, tokens_path=None,
            leakage_path=None, refresh_template=False):
    with open(discovery_path, encoding="utf-8") as handle:
        discovery = json.load(handle)
    tokens = None
    if tokens_path:
        with open(tokens_path, encoding="utf-8") as handle:
            tokens = json.load(handle)
    leakage = None
    if leakage_path:
        with open(leakage_path, encoding="utf-8") as handle:
            leakage = json.load(handle)
    discovery = enrich(discovery, tokens)
    with open(report_path, encoding="utf-8") as handle:
        report = json.load(handle)
    old_generated = report.get("run", {}).get("generated_at")
    old_version = report.get("provenance", {}).get("skill_version")
    generated = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    skill_version = describe()["version"]
    report["discovery"] = discovery
    sync_token_inventory(report, tokens)
    sync_leakage(report, leakage)
    if isinstance(report.get("run"), dict):
        report["run"]["generated_at"] = generated
        report["run"]["repo_ref"] = discovery.get("repository", {}).get("ref")
        versions = report["run"].get("framework_versions")
        if isinstance(versions, dict):
            versions = {
                name: version for name, version in versions.items()
                if not str(version).startswith("repository checkout ")
            }
            if versions:
                report["run"]["framework_versions"] = versions
            else:
                report["run"].pop("framework_versions", None)
    if isinstance(report.get("provenance"), dict):
        report["provenance"]["generated_at"] = generated
        report["provenance"]["skill_version"] = skill_version
        report["provenance"]["repo_ref"] = discovery.get(
            "repository", {}).get("ref")
        adapters = set(discovery.get("adapters", []))
        adapters.update(report.get("stack", {}).get("adapters", []) or [])
        report["provenance"]["adapter_versions"] = {
            adapter: skill_version for adapter in sorted(adapters)
        }
        report["provenance"]["profile_registry_sources"] = (
            discovery.get("profile_composition", {}).get("registry_sources", [])
        )

    document_path = TEMPLATE_PATH if refresh_template else html_path
    with open(document_path, encoding="utf-8") as handle:
        document = handle.read()
    if refresh_template:
        document = TEMPLATE_INSTRUCTIONS.sub(r'\1', document, count=1)
    section = render_section(discovery)
    if SECTION.search(document):
        document = SECTION.sub("\n" + section, document, count=1)
    elif MEASUREMENT_MARKER in document:
        document = document.replace(MEASUREMENT_MARKER, section + "\n  " + MEASUREMENT_MARKER, 1)
    elif LEGACY_MEASUREMENT_MARKER in document:
        document = document.replace(
            LEGACY_MEASUREMENT_MARKER,
            section + "\n  " + LEGACY_MEASUREMENT_MARKER,
            1,
        )
    else:
        raise ValueError("report has no discovery-engine or measurement insertion point")
    document = render_report_slots(document, report, tokens, discovery)
    document = render_token_slots(document, tokens, report)
    document = sync_count_narratives(document, tokens)
    document = replace_slot(document, "vitals-grid", render_vitals(report))
    if leakage:
        leakage_section = render_leakage(leakage)
        if LEAKAGE_SECTION.search(document):
            document = LEAKAGE_SECTION.sub(leakage_section, document, count=1)
        else:
            document += leakage_section
    document = replace_slot(
        document, "runhead-tag",
        '<span class="sampletag">Generated repository audit</span>',
    )
    document = replace_slot(
        document, "runhead-meta",
        render_runhead(discovery, tokens, report, skill_version),
    )
    document = replace_slot(
        document, "measurement",
        render_measurement(discovery, tokens, report, skill_version, generated),
    )
    document = replace_slot(
        document, "footer-meta",
        render_footer(discovery, tokens, skill_version),
    )
    document = sync_document_metadata(
        document, old_generated, generated, old_version, skill_version
    )
    write_json(report_path, report)
    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write(document)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--discovery", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--html", required=True)
    parser.add_argument("--tokens")
    parser.add_argument("--leakage")
    parser.add_argument(
        "--refresh-template", action="store_true",
        help="start from the current report template before rendering every region",
    )
    args = parser.parse_args(argv)
    augment(args.discovery, args.report_json, args.html, args.tokens,
            args.leakage, args.refresh_template)
    print("rendered universal discovery into %s and %s" % (
        args.report_json, args.html))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
