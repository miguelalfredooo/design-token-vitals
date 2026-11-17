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
import freshness  # noqa: E402
from cli import EXIT_OK  # noqa: E402
from adoption_strategy import (  # noqa: E402
    ACTIONABLE_UNRESOLVED_REASONS,
    derive as derive_adoption_strategy,
    render as render_adoption_strategy,
)
from discover_tokens import (  # noqa: E402
    MAX_EMBEDDED_FONT_BYTES,
    matching_font_asset_evidence,
    verified_font_file,
)
from version import describe  # noqa: E402
import chapters  # noqa: E402
import draw  # noqa: E402
import moves  # noqa: E402
from vocab import fmt, plain, plural  # noqa: E402


SECTION = re.compile(r'\n\s*<section id="discovery-engine"[^>]*>.*?</section>\n', re.S)
LEAKAGE_SECTION = re.compile(
    r'\n\s*<section id="leakage"[^>]*>.*?</section>\n', re.S)
MEASUREMENT_MARKER = '<section id="measurement"'
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
# Every id a reader may have linked to. A report keeps all of them: sections
# were merged into chapters and moved, and none was deleted, so a link saved
# from an earlier report still lands. `confidence` and `summary` used to be
# sections and are now blocks of the verdict; an id resolves either way.
SECTION_IDS = (
    "glance", "fix-queue", "ownership", "leakage", "decisions", "unlock",
    "component-usage", "vitals", "architecture", "inventory", "lineage",
    "coverage", "modes", "orphans", "measurement", "discovery-engine",
    "start", "strategy", "trend", "working-set",
)
ANCHOR_IDS = SECTION_IDS + ("confidence", "summary", "about-run", "verdict")
# The chapters, in reading order: number, id, name.
CHAPTERS = (
    ("00", "verdict", "Verdict"), ("01", "fix-now", "Fix now"),
    ("02", "decide", "Decide"), ("03", "unlock-chapter", "Unlock"),
    ("04", "components", "Components"), ("05", "checks", "Checks"),
    ("06", "architecture-chapter", "Architecture"),
    ("07", "inventory-chapter", "Inventory"),
    ("08", "sources", "Sources"),
    ("09", "coverage-chapter", "Coverage"), ("10", "themes", "Themes"),
    ("11", "unused", "Unused"), ("12", "method", "Method"),
    ("13", "next", "Next"),
)

DETAILS_TAG = re.compile(r"<details\b([^>]*)>", re.I)


INVENTORY_TABS_SCRIPT = """<script data-token-vitals-ui="report-controller">
(() => {
  const disclosures = Array.from(
    document.querySelectorAll("details[data-report-default-open]")
  );

  disclosures.forEach((disclosure) => {
    disclosure.open = disclosure.dataset.reportDefaultOpen === "true";
  });

  // A link into a closed disclosure opens every disclosure around its target.
  const revealHashTarget = () => {
    const id = decodeURIComponent(window.location.hash.slice(1));
    let node = id && document.getElementById(id);
    if (!node) {
      return;
    }
    const target = node;
    let opened = false;
    while (node) {
      if (node.tagName === "DETAILS" && !node.open) {
        node.open = true;
        opened = true;
      }
      node = node.parentElement;
    }
    if (opened) {
      window.requestAnimationFrame(() => target.scrollIntoView({ block: "start" }));
    }
  };

  document.documentElement.classList.add("report--ready");

  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", () => {
      const source = button.parentElement.querySelector("[data-copy-source]");
      if (!source || !navigator.clipboard) {
        return;
      }
      navigator.clipboard.writeText(source.textContent).then(() => {
        const label = button.textContent;
        button.textContent = "Copied";
        window.setTimeout(() => { button.textContent = label; }, 1600);
      });
    });
  });

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
    revealHashTarget();
    roots.forEach((root) => {
      const tab = tabForHash(root);
      if (tab) {
        activate(root, tab, false, false);
      }
    });
  });

  revealHashTarget();

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


def prepare_progressive_disclosures(document):
    """Keep evidence open without JS, then restore authored states on enhancement."""
    def prepare(match):
        attributes = match.group(1)
        if re.search(r'\bdata-report-default-open=', attributes, re.I):
            return match.group(0)
        default_open = bool(re.search(r'(?:^|\s)open(?:\s|=|$)', attributes, re.I))
        attributes = re.sub(
            r'\s+open(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s]+))?',
            "",
            attributes,
            count=1,
            flags=re.I,
        )
        return '<details open data-report-default-open="%s"%s>' % (
            str(default_open).lower(), attributes,
        )

    return DETAILS_TAG.sub(prepare, document)


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


def confirmed_definition_count(records):
    return sum(
        1 for item in records
        if (item.get("role") or item.get("classification"))
        in {"canonical", "alias"}
    )


def unresolved_import_summary(discovery):
    unresolved = discovery.get("import_graph", {}).get("unresolved", [])
    by_reason = {}
    for item in unresolved:
        reason = item.get("reason") or "unclassified"
        by_reason[reason] = by_reason.get(reason, 0) + 1
    return {
        "total": len(unresolved),
        "actionable": sum(
            count for reason, count in by_reason.items()
            if reason in ACTIONABLE_UNRESOLVED_REASONS
        ),
        "by_reason": dict(sorted(by_reason.items())),
    }


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
            "not-visible"
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
            # A profile passed from outside the repository is named by its
            # file, never by where it sat on the machine that ran the audit.
            esc(os.path.basename(str(item.get("path")))
                if os.path.isabs(str(item.get("path"))) else item.get("path")),
            esc(item.get("sha256")),
        )
        for item in discovery.get("profile_composition", {}).get(
            "registry_sources", [])
    )


# A capability is something the run could or couldn't see. The raw state
# stays in the row's data attribute for the gate.
CAPABILITY_STATE = {"verified": "We could see it", "not-visible": "Blocked"}


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
                esc(step.get("capability")),
                esc(CAPABILITY_STATE.get(step.get("state"), step.get("state"))),
                contributors,
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
        '<thead><tr><th>Token</th><th>Family</th><th>Written as</th>'
        '<th>Values</th><th>Declared at</th></tr></thead>'
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
    specimen_state = "verified" if embedded else "not-visible"
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
        '<p class="sub">%d tokens · %s</p>%s%s'
        '<div class="stack-16">%s</div></div>' % (
            esc(identity.get("state", "not-visible")), esc(family or ""),
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
    state = identity.get("state", "not-visible")
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
        '<p class="sub">%d tokens · repository values</p>'
        '%s</div>' % (
            esc(state), esc(confidence), json_attr(subject_namespaces), brand_content,
            len(concepts), concept_inventory_table(concepts),
        )
    )


def family_states(tokens):
    """The state of every family, from discovery when it reports one.

    Older token artifacts carry only `family_counts`, where a family the
    run never resolved and one it proved empty are both 0. Fall back to the
    conservative reading of that: without a state, zero means unmeasured.
    """
    states = tokens.get("family_states")
    if states:
        return states
    return {family: ({"state": "counted", "count": count} if count
                     else {"state": "not-visible"})
            for family, count in tokens.get("family_counts", {}).items()}


def family_block(tokens, report):
    states = family_states(tokens)
    concepts = normalized_concepts(tokens)
    existing = report.get("inventory", {}).get("families", {}) or {}
    total_concepts = len(concepts)
    rows = []
    # Largest first: the bars then read as a ranking, top to bottom.
    for family in sorted(states, key=lambda name: (
            -(states[name].get("count") or 0), name)):
        state = states[family]["state"]
        count = states[family].get("count")
        # `none-used` is the one state that has earned the number 0. An
        # `not-visible` family shows the word, never a figure it cannot back.
        if state == "none-used":
            shown = "0"
        elif count:
            shown = draw.share(count, total_concepts or count, fmt(count))
        else:
            shown = draw.hatch()
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
                '<details><summary>Show %s</summary><div>%s</div></details>' % (
                    plural(len(source_tags) - 4, "more file"),
                    "<br>".join(source_tags[4:]))
            )
        elif source_tags:
            note = "<br>".join(source_tags)
        else:
            note = esc(
                existing.get(family, {}).get("note") or
                "We found no token of this family."
            )
        rows.append(
            '<tr data-family="%s" data-family-state="%s" data-family-count="%s" '
            'data-family-sources-json="%s">'
            '<td>%s</td><td>%s</td><td>%s</td></tr>' % (
                esc(family), esc(state),
                esc("" if count is None else count),
                json_attr(sources),
                esc(family), shown,
                note,
            )
        )
    unclassified = len([item for item in concepts
                        if item.get("family") == "unclassified"])
    rows.append(
        '<tr data-family="unclassified" data-family-state="counted" '
        'data-family-count="%d"><td>unclassified</td><td>%s</td>'
        '<td>Tokens we could not place in a family. They are listed in the '
        'inventory.</td></tr>' %
        (unclassified, draw.share(unclassified, total_concepts or 1,
                                  fmt(unclassified)))
    )
    return (
        '<div class="tbl-scroll"><table class="fam"><thead><tr><th>Family</th>'
        '<th>Tokens, as a share of all of them</th><th>Declared in</th></tr></thead>'
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
            "state": "not-visible", "confidence": "unresolved",
            "family": None, "token": None, "evidence": [],
            "note": "Identity evidence was not produced by token discovery.",
        },
        "brand_colors": {
            "state": "not-visible", "confidence": "unresolved", "colors": [],
            "note": "Identity evidence was not produced by token discovery.",
        },
    })
    families = inventory.setdefault("families", {})
    for family, state in family_states(tokens).items():
        entry = families.setdefault(family, {})
        family_concepts = [item for item in concepts
                           if item.get("family") == family]
        sources = sorted({
            site.rsplit(":", 1)[0]
            for item in family_concepts for site in item.get("sites", [])
        })
        tiers = {"primitive": 0, "semantic": 0, "component": 0, "untraced": 0}
        for item in family_concepts:
            if item.get("tier") in tiers:
                tiers[item["tier"]] += 1
        entry.clear()
        if state["state"] == "counted":
            entry.update({
                "state": "counted", "count": state["count"],
                "sources": sources, "tiers": tiers, "note": None,
            })
        elif state["state"] == "none-used":
            entry.update({
                "state": "none-used", "count": 0, "sources": [],
                "tiers": tiers,
                "note": "No token of this family was found in any source the run read, held-out sources included.",
            })
        else:
            entry.update({
                "state": "not-visible", "sources": [],
                "tiers": tiers,
                "note": "No canonical concept was confirmed; held-out candidates may still contain local decisions.",
            })
    run = report.setdefault("run", {})
    run["token_count"] = tokens.get("concept_count", len(concepts))
    run["family_count"] = len(family_states(tokens))
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

    def state_of(key):
        entry = leakage.get(key)
        return entry.get("state") if isinstance(entry, dict) else entry

    # `redundant` is the tier the grade reads, and it is only a number once
    # semantic equivalence has been settled. This used to be hardcoded to
    # None whatever the audit reported, which silently defeated the audit's
    # own "measured, none found" result: a repository with no literal left to
    # compare still could not grade the vital, and no input would ever
    # change that. Now the renderer reports what the audit measured.
    semantic_settled = (state_of("semantic_equivalence") == "counted" and
                        not exact)
    if scanned and semantic_settled:
        near = state_of("near_miss")
        note = (
            "No hardcoded color has the same value as a token, so there is "
            "nothing to replace. %s no token at all, and colors that "
            "are only close to a token were %s."
        ) % ("One hardcoded color matches" if uncovered == 1
             else "%s match" % plural(uncovered, "hardcoded color"),
             "checked, with none found" if near == "counted"
             else "not checked")
        tiers = {
            "redundant": 0,
            "exact-value candidate": exact,
            "near-miss": 0 if near == "counted" else None,
            "uncovered": None,
            "uncovered candidate": uncovered,
        }
        leakage_vital.setdefault("grade", "healthy")
        leakage_vital["tiers"] = tiers
        leakage_vital["note"] = leakage_vital.get("note") or note
        return
    if scanned:
        note = (
            "%s the same value as a token, and %s no token at all. We can't "
            "say whether a match is the same decision, and we did not check "
            "for colors that are only close to a token."
        ) % ("One hardcoded color has" if exact == 1
             else "%s have" % plural(exact, "hardcoded color"),
             "one matches" if uncovered == 1 else "%s match" % fmt(uncovered))
        tiers = {
            "redundant": None,
            "exact-value candidate": exact,
            "near-miss": None,
            "uncovered": None,
            "uncovered candidate": uncovered,
        }
    else:
        # Rule 4, applied to this skill's own output: zero states the project
        # has none, which a run that opened no consumer style never
        # established. Reporting 0 here put "exact-value candidate 0" beside
        # "redundant unmeasured" in one sentence of the strategy section.
        note = (
            "We found no stylesheet of yours that uses the tokens, so we "
            "couldn't look for hardcoded colors. That is not the same as "
            "finding none: a color written straight into a template or a "
            "component is not checked here."
        )
        tiers = {
            "redundant": None,
            "exact-value candidate": None,
            "near-miss": None,
            "uncovered": None,
            "uncovered candidate": None,
        }
    leakage_vital.update({
        "grade": "not-visible", "evidence": [], "note": note, "tiers": tiers,
    })


def next_step_items(report):
    """The ranked moves as `[title, where]` rows: the JSON twin of the list."""
    return moves.as_rows(report)


def render_confidence_slots(document, report, lineage):
    """The verdict's sentence, the blocked checks, what we verified, and reach."""
    document = replace_slot(document, "headline", chapters.render_headline(report))
    document = replace_slot(document, "unlock-path", chapters.render_unlock(report))
    document = replace_slot(document, "sub-unlock", esc(chapters.sub_unlock(report)))
    document = replace_slot(document, "wins", chapters.render_wins(report))
    document = replace_slot(document, "blast-radius", chapters.render_reach(lineage))
    document = replace_slot(
        document, "lineage-lead", chapters.render_lineage_lead(report, set()))
    document = replace_slot(document, "sub-lineage", esc(chapters.sub_lineage(report)))
    return document


def family_subtitle(tokens):
    states = family_states(tokens)
    counted = sorted(((item.get("count") or 0, name)
                      for name, item in states.items()), reverse=True)
    line = plural(len(states), "family", "families")
    if counted and counted[0][0]:
        line += " · %s is the largest" % counted[0][1]
    return line


def inventory_subtitle(tokens):
    concepts = normalized_concepts(tokens)
    color = len([item for item in concepts if item.get("family") == "color"])
    typography = len([item for item in concepts
                      if item.get("family") == "typography"])
    return "%s · %s · %s, drawn as what they are" % (
        plural(color, "color"), plural(typography, "type token"),
        plural(len(concepts) - color - typography, "other"))


def render_report_slots(document, report, tokens, discovery):
    strategy = derive_adoption_strategy(report)
    report["adoption_strategy"] = strategy
    repository = discovery.get("repository", {}) or {}
    title = "Design Token Vitals — %s @ %s" % (
        os.path.basename(str(repository.get("root") or "repository")),
        str(repository.get("ref") or "unknown")[:10],
    )
    document = replace_slot(document, "doc-title", '<title>%s</title>' % esc(title))
    document = replace_slot(document, "at-a-glance", chapters.render_glance(report))
    document = replace_slot(
        document, "exec-summary", chapters.render_first_move(report))
    document = replace_slot(document, "sub-fix-now", esc(chapters.sub_fix_now(report)))
    document = replace_slot(document, "fix-queue", chapters.render_fix_now(report))
    document = replace_slot(document, "groups", chapters.render_groups(report))
    document = replace_slot(document, "sub-decide", esc(chapters.sub_decide(report)))
    document = replace_slot(
        document, "decide-calls", chapters.render_decide_calls(report))
    document = replace_slot(document, "decisions", chapters.render_decisions(report))
    document = replace_slot(
        document, "adoption-strategy", render_adoption_strategy(strategy))
    document = replace_slot(document, "sub-next", esc(chapters.sub_next(report)))
    document = replace_slot(document, "next-steps", chapters.render_next_steps(report))
    document = replace_slot(document, "stage", chapters.render_stage(report))
    document = replace_slot(document, "lineage", chapters.render_lineage(report))
    document = replace_slot(document, "sub-coverage", esc(chapters.sub_coverage(report)))
    document = replace_slot(
        document, "coverage-matrix", chapters.render_coverage_matrix(report))
    modes_coverage, modes_gaps = chapters.render_modes(report)
    document = replace_slot(document, "sub-modes", esc(chapters.sub_modes(report)))
    document = replace_slot(document, "modes-coverage", modes_coverage)
    document = replace_slot(document, "modes-gaps", modes_gaps)
    orphan_html, enforcement_html = chapters.render_orphans_and_enforcement(report)
    document = replace_slot(document, "sub-orphans", esc(chapters.sub_orphans(report)))
    document = replace_slot(document, "orphans", orphan_html)
    document = replace_slot(document, "enforcement", enforcement_html)
    document = replace_slot(
        document, "inventory-tabs-script", INVENTORY_TABS_SCRIPT)
    if tokens:
        document = replace_slot(
            document, "family-coverage", family_block(tokens, report))
        document = replace_slot(
            document, "sub-architecture", esc(family_subtitle(tokens)))
        document = replace_slot(
            document, "sub-inventory", esc(inventory_subtitle(tokens)))
    document = strip_trend_without_a_baseline(document, report)
    return document


def strip_trend_without_a_baseline(document, report):
    """Remove the trend section unless a baseline actually produced a comparison.

    The test used to be `if not report.get("trend")`, which only caught a
    missing key. A schema-shaped block of nulls — what the capability map
    ships and what a run with no baseline carries — is truthy, so the
    section survived with the template's own sample comparison in it, and
    the validation gate caught it as leftover sample content on every fresh
    report.
    """
    trend = report.get("trend") or {}
    if isinstance(trend, dict):
        movement = any(
            trend.get(key) for key in
            ("new", "resolved", "grew", "shrank", "regressions"))
        has_baseline = bool(trend.get("baseline_ref")) or movement
    else:
        has_baseline = bool(trend)
    if has_baseline:
        return document
    # The section stays, emptied: `#trend` still resolves, and a link saved
    # from a report that had a comparison lands where the next one will be.
    return re.sub(
        r'(\n\s*<section id="trend"[^>]*>).*?(</section>\n)',
        lambda match: match.group(1) +
        '\n      <h3 class="part">What moved since the last run</h3>'
        '\n      <p class="quiet">This is the first run we have for this '
        'repository, so there is nothing to compare it to yet.</p>\n    ' +
        match.group(2),
        document, count=1, flags=re.S)


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


def run_summary(discovery, tokens, report):
    """The counts About this run shows, and the gate checks it against."""
    roots = discovery.get("roots", [])
    unresolved = unresolved_import_summary(discovery)
    return {
        "profiles": discovery.get("environment", []),
        "roots": len(roots),
        "owned_roots": len([item for item in roots
                            if item.get("ownership") == "owned"]),
        "unknown_roots": len([item for item in roots
                              if item.get("ownership") == "unknown"]),
        "reachable": len(discovery.get("import_graph", {}).get("reachable", {})),
        "owned_reachable": len(discovery.get("owned_import_graph", {}).get(
            "reachable", {})),
        "unresolved_total": unresolved["total"],
        "unresolved_actionable": unresolved["actionable"],
        "unresolved_by_reason": unresolved["by_reason"],
        "concepts": (tokens or {}).get(
            "concept_count", report.get("run", {}).get("token_count")),
        "token_sources": confirmed_definition_count(
            (tokens or {}).get("sources", [])),
        "held_out_sources": len((tokens or {}).get(
            "candidate_or_local_override_sources", [])),
    }


def render_runhead(discovery, tokens, report, skill_version):
    """The one fact line under the title."""
    full = run_summary(discovery, tokens, report)
    summary = {key: full[key] for key in (
        "profiles", "roots", "owned_roots", "reachable", "owned_reachable",
        "token_sources", "concepts")}
    return '<span data-runhead-summary-json="%s">%s</span>' % (
        json_attr(summary), chapters.factline(report))


def render_footer(discovery, tokens, skill_version):
    """Nothing a reader needs: the counts live in About this run.

    The summary stays as a data attribute, because the gate compares it with
    the JSON and a script may read it.
    """
    summary = {
        "profiles": discovery.get("environment", []),
        "concepts": (tokens or {}).get("concept_count", "not-visible"),
        "owned_reachable": len(discovery.get("owned_import_graph", {}).get(
            "reachable", {})),
        "owned_roots": len([item for item in discovery.get("roots", [])
                            if item.get("ownership") == "owned"]),
        "skill_version": skill_version,
    }
    return '<span data-footer-summary-json="%s">design-token-vitals</span>' % (
        json_attr(summary))


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
    <details class="chapter-fold"><summary>How we found your app</summary><div class="details-body">
    <p class="quiet">%d framework profiles agreed on %d entry files and %d component folders you own. We kept %d possible entries we could not reach, %d registered entries missing from disk and %d possible component folders as leads, and we left %d demo or template surfaces out.</p>
    <div class="note"><b>Which app we audited:</b> %s%s</div>
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
    </div></details>
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


def fill_document(document, report, discovery, tokens=None, leakage=None,
                  skill_version="unrecorded"):
    """Every region of the page, filled from one report.

    Split from `augment` so the page can be rendered without files on disk:
    the tests hold a whole rendered report to its rules this way.
    """
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
    document = render_confidence_slots(
        document, report, report.get("token_chains"))
    document = render_token_slots(document, tokens, report)
    document = replace_slot(
        document, "vitals-grid", chapters.render_checks(report))
    if leakage:
        leakage_section = chapters.render_leakage(report, leakage)
        if LEAKAGE_SECTION.search(document):
            document = LEAKAGE_SECTION.sub(leakage_section, document, count=1)
        else:
            document += leakage_section
    document = replace_slot(document, "runhead-tag", "")
    document = replace_slot(
        document, "runhead-meta",
        render_runhead(discovery, tokens, report, skill_version),
    )
    document = replace_slot(
        document, "about-run",
        chapters.about_run(
            report, run_summary(discovery, tokens, report), skill_version),
    )
    document = replace_slot(
        document, "measurement", chapters.render_method(report))
    document = replace_slot(
        document, "footer-meta",
        render_footer(discovery, tokens, skill_version),
    )
    return document


def augment(discovery_path, report_path, html_path, tokens_path=None,
            leakage_path=None, refresh_template=False,
            unlock_path_file=None, lineage_path=None):
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
    unlock = None
    if unlock_path_file:
        with open(unlock_path_file, encoding="utf-8") as handle:
            unlock = json.load(handle)
    lineage = None
    if lineage_path:
        with open(lineage_path, encoding="utf-8") as handle:
            lineage = json.load(handle)
    discovery = enrich(discovery, tokens)
    with open(report_path, encoding="utf-8") as handle:
        report = json.load(handle)
    # The page is one document read top to bottom. An older report's choice
    # of "view" has nothing left to choose between.
    rendering = report.setdefault("rendering", {})
    rendering.pop("view", None)
    rendering.pop("available_views", None)
    old_generated = report.get("run", {}).get("generated_at")
    old_version = report.get("provenance", {}).get("skill_version")
    generated = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    skill_version = describe()["version"]
    report["discovery"] = discovery
    sync_token_inventory(report, tokens)
    sync_leakage(report, leakage)
    # The JSON duplicates exactly what the page shows, so the confidence and
    # lineage evidence lands in both or in neither. Freshness is measured
    # here rather than carried, because it is a fact about now.
    if unlock:
        report["confidence"] = unlock
    if lineage:
        report["token_chains"] = lineage
    repository_root = (discovery.get("repository") or {}).get("root")
    if repository_root:
        report["freshness"] = freshness.measure(
            repository_root, (discovery.get("repository") or {}).get("ref"))
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
    document = fill_document(
        document, report, discovery, tokens, leakage, skill_version)
    document = sync_document_metadata(
        document, old_generated, generated, old_version, skill_version
    )
    document = prepare_progressive_disclosures(document)
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
    parser.add_argument("--unlock",
                        help="the tools/unlock_path.py output for this run")
    parser.add_argument("--lineage",
                        help="the tools/lineage_map.py output for this run")
    parser.add_argument(
        "--refresh-template", action="store_true",
        help="start from the current report template before rendering every region",
    )
    args = parser.parse_args(argv)
    augment(args.discovery, args.report_json, args.html, args.tokens,
            args.leakage, args.refresh_template,
            args.unlock, args.lineage)
    print("rendered universal discovery into %s and %s" % (
        args.report_json, args.html))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
