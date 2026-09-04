#!/usr/bin/env python3
"""Merge component usage into report JSON and render its HTML section."""
import argparse
import datetime
import html
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_OK  # noqa: E402
from adoption_strategy import derive as derive_adoption_strategy  # noqa: E402
from adoption_strategy import render as render_adoption_strategy  # noqa: E402
from version import describe  # noqa: E402


SECTION = re.compile(r"\n\s*<section id=\"component-usage\"[^>]*>.*?</section>\n", re.S)
LEAKAGE_MARKER = '<section id="leakage"'
LEGACY_LEAKAGE_MARKER = '<section><div class="eyebrow">Leakage</div>'
MEASUREMENT_MARKER = '<section id="measurement"'
ADOPTION_SLOT = re.compile(
    r'(<!-- SLOT:adoption-strategy -->).*?(<!-- /SLOT:adoption-strategy -->)',
    re.S,
)
AT_A_GLANCE_SLOT = re.compile(
    r'(<!-- SLOT:at-a-glance -->).*?(<!-- /SLOT:at-a-glance -->)',
    re.S,
)
LOCATION_SITE = re.compile(r"^(.*):(\d+(?::\d+)?)$")
LOCATION_PREVIEW_LIMIT = 2


def esc(value):
    return html.escape(str(value), quote=True)


def json_attr(value):
    return esc(json.dumps(value, sort_keys=True, separators=(",", ":")))


def family_text(families):
    return " · ".join("%s %s" % (esc(name), count)
                      for name, count in sorted((families or {}).items(),
                                                key=lambda item: (-item[1], item[0])))


def token_name(token):
    name = token.get("id", "?")
    syntaxes = token.get("syntaxes") or []
    forms = []
    if "css-custom-property" in syntaxes:
        forms.append("--" + name)
    if "scss-variable" in syntaxes:
        forms.append("$" + name)
    return " / ".join(forms) if forms else name


def location_span(location):
    return '<span class="path" data-token-location="%s">%s</span>' % (
        esc(location), esc(location)
    )


def compact_location_span(location, line):
    return (
        '<span class="path location-line" data-token-location="%s" '
        'aria-label="%s">line %s</span>'
        % (esc(location), esc(location), esc(line))
    )


def grouped_locations(locations):
    groups = []
    indexes = {}
    for location in locations or []:
        value = str(location)
        match = LOCATION_SITE.match(value)
        if not match:
            groups.append((None, [(value, None)]))
            continue
        path = match.group(1)
        if path not in indexes:
            indexes[path] = len(groups)
            groups.append((path, []))
        groups[indexes[path]][1].append((value, match.group(2)))
    return groups


def render_locations(locations):
    rendered = []
    for path, group in grouped_locations(locations):
        if path is None:
            body = "<br>".join(
                location_span(location) for location, _line in group
            )
        elif len(group) == 1:
            body = location_span(group[0][0])
        else:
            visible = group[:LOCATION_PREVIEW_LIMIT]
            hidden = group[LOCATION_PREVIEW_LIMIT:]
            body = (
                '<span class="path location-file">%s</span>'
                '<div class="location-lines">%s</div>'
                % (
                    esc(path), "".join(
                        compact_location_span(location, line)
                        for location, line in visible
                    )
                )
            )
            if hidden:
                noun = "location" if len(hidden) == 1 else "locations"
                body += (
                    '<details class="location-disclosure" data-location-file="%s" '
                    'data-location-hidden="%d"><summary>See %d more %s in %s</summary>'
                    '<div class="details-body location-lines">%s</div></details>'
                    % (
                        esc(path),
                        len(hidden),
                        len(hidden),
                        noun,
                        esc(os.path.basename(path)),
                        "".join(
                            compact_location_span(location, line)
                            for location, line in hidden
                        ),
                    )
                )
        attributes = ""
        if path:
            attributes = (
                ' data-location-file="%s" data-location-count="%d" '
                'data-location-preview="%d"'
                % (esc(path), len(group), min(len(group), LOCATION_PREVIEW_LIMIT))
            )
        rendered.append('<div class="location-group"%s>%s</div>' % (attributes, body))
    return "".join(rendered)


def render_component_paths(paths):
    return "<br>".join(
        '<span class="path" data-component-path="%s">%s</span>' % (
            esc(path), esc(path)
        )
        for path in paths or []
    )


def render_roadmap(usage):
    roadmap = usage.get("roadmap", {}) or {}
    components = {
        item.get("id"): item for item in usage.get("top_20", [])
        if isinstance(item, dict) and item.get("id")
    }
    band_sections = []
    for band in roadmap.get("bands", []) or []:
        band_id = esc(band.get("id"))
        heading_id = "component-roadmap-band-%s-title" % band_id
        rows = []
        for component_id in band.get("component_ids", []) or []:
            component = components.get(component_id)
            if not component:
                continue
            rows.append(
                '<tr id="component-roadmap-%s" data-component="%s" '
                'data-component-kind="%s" data-component-references="%d" '
                'data-component-distinct-tokens="%d" data-component-roadmap-band="%s" '
                'data-component-share="%.1f">'
                '<td class="num">%d</td><td><a class="component-roadmap-link" '
                'href="#component-detail-%s"><code>%s</code></a>'
                '<br><span class="p-mute">%s · %s</span></td>'
                '<td class="num">%d</td><td class="num">%d</td><td class="num">%d</td>'
                '<td><span class="component-share-label">%.1f%%</span></td></tr>' % (
                    esc(component_id), esc(component_id), esc(component.get("kind")),
                    component.get("references", 0), component.get("distinct_tokens", 0),
                    esc(component.get("roadmap_band")),
                    component.get("share_of_ranked_references", 0.0),
                    component.get("rank", 0), esc(component_id),
                    esc(component.get("name")),
                    esc(component.get("kind")), esc(component.get("confidence")),
                    component.get("references", 0),
                    component.get("distinct_tokens", 0),
                    len(component.get("paths", []) or []),
                    component.get("share_of_ranked_references", 0.0),
                )
            )
        band_sections.append(
            '<article class="component-roadmap-band" data-roadmap-band="%s" '
            'aria-labelledby="%s">'
            '<header><span class="component-roadmap-kicker">%s</span>'
            '<h3 id="%s">%s</h3><p>%s</p><strong>%.1f%% of the ranked view</strong></header>'
            '<div class="tbl-scroll" role="region" tabindex="0" aria-labelledby="%s">'
            '<table aria-labelledby="%s"><thead><tr><th class="num">#</th>'
            '<th>Component or surface</th><th class="num">Token refs</th><th class="num">Tokens</th>'
            '<th class="num">Paths</th><th>Share</th></tr></thead><tbody>%s</tbody></table></div></article>' % (
                band_id, heading_id,
                "%d–%d" % (band.get("start_rank", 0), band.get("end_rank", 0)),
                heading_id, esc(band.get("label")), esc(band.get("description")),
                band.get("share_of_ranked_references", 0.0),
                heading_id, heading_id, "".join(rows),
            )
        )
    return (
        '<div class="component-roadmap" data-component-roadmap-json="%s">'
        '<div class="component-roadmap-intro"><h3>Plan by token footprint</h3>'
        '<p>%s</p><span>%d confirmed token references in this ranked view</span></div>'
        '<div class="component-roadmap-grid">%s</div></div>' % (
            json_attr(roadmap), esc(roadmap.get("basis") or
                "Confirmed token use orders the review."),
            roadmap.get("ranked_references", 0), "".join(band_sections),
        )
    )


def render_section(usage):
    measured = [item for item in usage.get("measurement", []) if item.get("state") == "measured"]
    incomplete = [item for item in usage.get("measurement", []) if item.get("state") != "measured"]
    boundary = "; ".join("%s: %s (%s)" % (
        esc(item.get("syntax")), esc(item.get("state")), esc(item.get("evidence")))
        for item in measured + incomplete)
    details = []
    for component in usage.get("top_20", []):
        token_rows = []
        for token in component.get("tokens", []):
            locations = render_locations(token.get("locations", []))
            token_rows.append(
                '<tr data-component-token="%s:%s" data-token-id="%s" '
                'data-token-family="%s" data-token-syntaxes="%s" '
                'data-token-references="%d"><td><span class="tok">%s</span></td><td>%s</td>'
                '<td class="num">%d</td><td>%s</td></tr>' % (
                    esc(component.get("id")), esc(token.get("id")), esc(token.get("id")),
                    esc(token.get("family", "unclassified")),
                    esc(",".join(token.get("syntaxes", []))), token.get("references", 0),
                    esc(token_name(token)), esc(token.get("family", "unclassified")),
                    token.get("references", 0), locations,
                )
            )
        details.append(
            '<details id="component-detail-%s" data-component-detail="%s">'
            '<summary>#%d %s — %d references across %d tokens</summary>'
            '<div class="details-body"><p class="component-detail-paths"><b>Owned paths</b><br>%s</p>'
            '<p class="component-detail-families"><b>Families</b> · %s</p>'
            '<div class="tbl-scroll"><table class="component-token-table"><thead><tr>'
            '<th>Token</th><th>Family</th><th class="num">References</th><th>Locations</th>'
            '</tr></thead><tbody>%s</tbody></table></div></div></details>' % (
                esc(component.get("id")), esc(component.get("id")),
                component.get("rank", 0), esc(component.get("name")),
                component.get("references", 0), component.get("distinct_tokens", 0),
                render_component_paths(component.get("paths", [])),
                family_text(component.get("families")), "".join(token_rows),
            )
        )
    return """
  <section id="component-usage" data-report-views="action evidence">
    <div class="eyebrow">Component roadmap</div>
    <h2>Which components carry the largest token footprint</h2>
    <p class="lede">Found %d identified components with confirmed token usage across %d files in the declared scope, plus %d broader stylesheet surfaces. The roadmap shows %d components; %d lower-volume components sit below this intentionally ranked view. This measures token references inside code rather than runtime impressions or screen frequency.%s</p>
    <div class="note"><b>Measurement boundary:</b> %s</div>
    %s
    <div class="stack-16"><h3>Every token and evidence location for the ranked components</h3>%s</div>
  </section>
""" % (
        usage.get("total_components_with_token_usage", 0), usage.get("files_scanned", 0),
        usage.get("additional_style_surfaces", 0), usage.get("shown_components", 0),
        usage.get("not_shown", 0),
        (" %d fallback stylesheet surface(s) fill the remaining slots because fewer than 20 components were identified." % usage.get("fallback_surfaces", 0)) if usage.get("fallback_surfaces") else "",
        boundary,
        render_roadmap(usage), "".join(details),
    )


def write_json(path, value):
    directory = os.path.dirname(os.path.abspath(path))
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False,
                                     encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=False)
        handle.write("\n")
        temp_path = handle.name
    os.replace(temp_path, path)


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


def augment(components_path, report_path, html_path):
    with open(components_path, encoding="utf-8") as handle:
        usage = json.load(handle)
    with open(report_path, encoding="utf-8") as handle:
        report = json.load(handle)
    old_generated = report.get("run", {}).get("generated_at")
    old_version = report.get("provenance", {}).get("skill_version")
    generated = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    skill_version = describe()["version"]
    report["component_usage"] = usage
    report.setdefault("executive_summary", {}).setdefault(
        "affected", {})["components"] = usage.get(
            "total_components_with_token_usage", 0)
    strategy = derive_adoption_strategy(report)
    report["adoption_strategy"] = strategy
    if isinstance(report.get("run"), dict):
        report["run"]["generated_at"] = generated
    if isinstance(report.get("provenance"), dict):
        report["provenance"]["generated_at"] = generated
        report["provenance"]["skill_version"] = skill_version

    with open(html_path, encoding="utf-8") as handle:
        document = handle.read()
    if AT_A_GLANCE_SLOT.search(document):
        from render_discovery import render_at_a_glance
        document = AT_A_GLANCE_SLOT.sub(
            lambda match: match.group(1) + render_at_a_glance(report) + match.group(2),
            document,
            count=1,
        )
    section = render_section(usage)
    if SECTION.search(document):
        document = SECTION.sub("\n" + section, document, count=1)
    else:
        marker = next(
            (candidate for candidate in (
                LEAKAGE_MARKER, LEGACY_LEAKAGE_MARKER, MEASUREMENT_MARKER,
            ) if candidate in document),
            None,
        )
        if marker is None:
            raise ValueError("report has no component-usage, leakage, or measurement insertion point")
        document = document.replace(marker, section + "\n  " + marker, 1)
    if not ADOPTION_SLOT.search(document):
        raise ValueError("report has no adoption-strategy region")
    document = ADOPTION_SLOT.sub(
        lambda match: match.group(1) + render_adoption_strategy(strategy) + match.group(2),
        document,
        count=1,
    )
    document = sync_document_metadata(
        document, old_generated, generated, old_version, skill_version
    )
    from render_discovery import prepare_progressive_disclosures
    document = prepare_progressive_disclosures(document)
    write_json(report_path, report)
    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write(document)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--components", required=True)
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--html", required=True)
    args = parser.parse_args(argv)
    augment(args.components, args.report_json, args.html)
    print("rendered component usage into %s and %s" % (args.report_json, args.html))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
