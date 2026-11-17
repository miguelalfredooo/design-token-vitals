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
import draw  # noqa: E402
from vocab import fmt, pct, plural  # noqa: E402


SECTION = re.compile(r"\n\s*<section id=\"component-usage\"[^>]*>.*?</section>\n", re.S)
LEAKAGE_MARKER = '<section id="leakage"'
LEGACY_LEAKAGE_MARKER = '<section><div class="eyebrow">Leakage</div>'
MEASUREMENT_MARKER = '<section id="measurement"'
ADOPTION_SLOT = re.compile(
    r'(<!-- SLOT:adoption-strategy -->).*?(<!-- /SLOT:adoption-strategy -->)',
    re.S,
)
SUBTITLE_SLOT = re.compile(
    r'(<!-- SLOT:sub-components -->).*?(<!-- /SLOT:sub-components -->)',
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


def share_whole(usage):
    """What a share is a share of, and the words for it.

    Every component's token references, when the run recorded that total.
    An older run recorded only the rows it ranked, and a share of those is
    said to be exactly that.
    """
    roadmap = usage.get("roadmap", {}) or {}
    fallback = int(usage.get("fallback_surfaces", 0) or 0) > 0
    total = usage.get("usage_references_total" if fallback
                      else "component_references_total")
    if total:
        count = usage.get("total_usage_units" if fallback
                          else "total_components_with_token_usage", 0)
        noun = "component or surface" if fallback else "component"
        return int(total), "all %s" % plural(
            count, noun, "components and surfaces" if fallback else None)
    return int(roadmap.get("ranked_references", 0) or 0), "the %s shown" % plural(
        usage.get("shown", 0), "row")


def share_label(component, usage):
    """`7.1%`: this row's share of the whole `share_whole` names."""
    whole, _words = share_whole(usage)
    return pct(component.get("references", 0), whole, 1) or "0.0%"


def top_share(usage, limit=5):
    """`(count, share text, whole words)` for the first few rows together."""
    rows = (usage.get("top_20") or [])[:limit]
    whole, words = share_whole(usage)
    carried = sum(int(item.get("references", 0) or 0) for item in rows)
    return len(rows), pct(carried, whole), words, carried, whole


def subtitle(usage):
    if usage.get("state") != "counted" or not usage.get("top_20"):
        return "We could not count token use by component"
    count, share, _words, _carried, _whole = top_share(usage)
    fallback = int(usage.get("fallback_surfaces", 0) or 0) > 0
    total = usage.get("total_usage_units" if fallback
                      else "total_components_with_token_usage", 0)
    return "%s · top %d carry %s of token use" % (
        plural(total, "component"), count, share)


def render_roadmap(usage):
    roadmap = usage.get("roadmap", {}) or {}
    whole, whole_words = share_whole(usage)
    components = {
        item.get("id"): item for item in usage.get("top_20", [])
        if isinstance(item, dict) and item.get("id")
    }
    rows = []
    for component in sorted(components.values(), key=lambda item: item.get("rank", 0)):
        component_id = component.get("id")
        rows.append(
            '<tr id="component-roadmap-%s" data-component="%s" '
            'data-component-kind="%s" data-component-references="%d" '
            'data-component-distinct-tokens="%d" data-component-roadmap-band="%s" '
            'data-component-share="%.1f">'
            '<td class="num">%d</td><td><a class="component-roadmap-link" '
            'href="#component-detail-%s"><code>%s</code></a></td>'
            '<td class="num">%d</td><td class="num">%d</td><td class="num">%d</td>'
            '<td class="share">%s<span class="component-share-label">%s</span></td></tr>' % (
                esc(component_id), esc(component_id), esc(component.get("kind")),
                component.get("references", 0), component.get("distinct_tokens", 0),
                esc(component.get("roadmap_band")),
                component.get("share_of_ranked_references", 0.0),
                component.get("rank", 0), esc(component_id),
                esc(component.get("name")),
                component.get("references", 0),
                component.get("distinct_tokens", 0),
                len(component.get("paths", []) or []),
                '<span class="mk-share" aria-hidden="true"><i style="width:%.3f%%">'
                '</i></span>' % (
                    100.0 * component.get("references", 0) / whole if whole else 0),
                share_label(component, usage),
            )
        )
    # ONE table. The rows used to be cut into three bands named "assess
    # first", "plan next" and "focused follow-up": an order to act in, drawn
    # from a count of token uses, which says nothing about what is safe to
    # change. The band each row falls in stays in its data attribute and in
    # the JSON for anything that reads it.
    table = (
        '<div class="tbl-scroll" role="region" tabindex="0" '
        'aria-labelledby="component-table-title">'
        '<table class="component-table" aria-labelledby="component-table-title">'
        '<caption id="component-table-title" class="sr">Components by token use'
        '</caption><thead><tr><th class="num">#</th><th>Component</th>'
        '<th class="num">Token uses</th><th class="num">Tokens</th>'
        '<th class="num">Files</th><th>Share of all token uses</th></tr></thead>'
        '<tbody>%s</tbody></table></div>' % "".join(rows))
    count, share, _words, carried, _whole = top_share(usage)
    lead = draw.figure(
        draw.stack([("top %d" % count, carried, "ink")], whole),
        "%s of %s (%s)" % (fmt(carried), fmt(whole), share),
        "The dark part is the %d components that use tokens most, out of the "
        "token uses in %s. This counts uses in code, not how often a screen "
        "is seen." % (count, esc(whole_words)),
        kind="stack")
    return (
        '<div class="component-roadmap" data-component-roadmap-json="%s">%s%s</div>' % (
            json_attr(roadmap), lead, table,
        )
    )


MEASURED_AS = {
    "css-custom-property": "CSS custom properties",
    "scss-variable": "Sass variables",
    "framework-generated-utility": "framework utility classes",
}


def boundary(usage):
    """What counted as a token use, and what we couldn't see."""
    counted = [MEASURED_AS.get(item.get("syntax"), item.get("syntax"))
               for item in usage.get("measurement", [])
               if item.get("state") == "counted"]
    unseen = [MEASURED_AS.get(item.get("syntax"), item.get("syntax"))
              for item in usage.get("measurement", [])
              if item.get("state") != "counted"]
    line = "We counted %s." % (" and ".join(counted) or "nothing")
    if unseen:
        line += " We couldn’t see %s, so a component styled that way looks smaller here than it is." % " or ".join(unseen)
    return line


def render_section(usage):
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
            '<summary>#%d %s: %s of %s</summary>'
            '<div class="details-body"><p class="component-detail-paths"><b>Files</b><br>%s</p>'
            '<p class="component-detail-families"><b>Families</b> · %s</p>'
            '<div class="tbl-scroll"><table class="component-token-table"><thead><tr>'
            '<th>Token</th><th>Family</th><th class="num">Uses</th><th>Where</th>'
            '</tr></thead><tbody>%s</tbody></table></div></div></details>' % (
                esc(component.get("id")), esc(component.get("id")),
                component.get("rank", 0), esc(component.get("name")),
                esc(plural(component.get("references", 0), "use")),
                esc(plural(component.get("distinct_tokens", 0), "token")),
                render_component_paths(component.get("paths", [])),
                family_text(component.get("families")), "".join(token_rows),
            )
        )
    fallback = usage.get("fallback_surfaces")
    return """
    <section id="component-usage">
    %s
    <p class="quiet">%s%s</p>
    <div class="stack-16"><h3 class="part">Every token each of these uses, and where</h3>%s</div>
    </section>
""" % (
        render_roadmap(usage), esc(boundary(usage)),
        (" %s the list because fewer than 20 components were found." % esc(
            "One stylesheet fills out" if fallback == 1
            else "%s fill out" % plural(fallback, "stylesheet"))) if fallback else "",
        "".join(details),
    )


ABOUT_SLOT = re.compile(
    r'(<!-- SLOT:about-run -->)(.*?)(<!-- /SLOT:about-run -->)', re.S)


def refresh_about_run(document, report, skill_version):
    """Add the files read for component use to About this run.

    This tool runs after the page is first rendered, so the one place that
    names every count of files was written before this count existed.
    """
    match = ABOUT_SLOT.search(document)
    summary = re.search(r'data-measurement-summary-json="([^"]*)"',
                        match.group(2)) if match else None
    if not summary:
        return document
    import chapters
    about = chapters.about_run(
        report, json.loads(html.unescape(summary.group(1))), skill_version)
    # Keep whatever the gate has already written about this run's validation.
    note = re.search(r'<!-- SLOT:validation-note -->.*?<!-- /SLOT:validation-note -->',
                     match.group(2), re.S)
    if note:
        about = re.sub(r'<!-- SLOT:validation-note -->.*?<!-- /SLOT:validation-note -->',
                       lambda _m: note.group(0), about, count=1, flags=re.S)
    return ABOUT_SLOT.sub(lambda m: m.group(1) + about + m.group(3), document, count=1)


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
    if SUBTITLE_SLOT.search(document):
        document = SUBTITLE_SLOT.sub(
            lambda match: match.group(1) + esc(subtitle(usage)) + match.group(2),
            document,
            count=1,
        )
    document = refresh_about_run(document, report, skill_version)
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
    import family
    page = family.attach(report, document)
    write_json(report_path, report)
    family.write_beside(report_path, page)
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
