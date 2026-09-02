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
from version import describe  # noqa: E402


SECTION = re.compile(r"\n\s*<section id=\"component-usage\">.*?</section>\n", re.S)
LEAKAGE_MARKER = '<section><div class="eyebrow">Leakage</div>'
MEASUREMENT_MARKER = '<section id="measurement">'


def esc(value):
    return html.escape(str(value), quote=True)


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


def render_section(usage):
    measured = [item for item in usage.get("measurement", []) if item.get("state") == "measured"]
    incomplete = [item for item in usage.get("measurement", []) if item.get("state") != "measured"]
    boundary = "; ".join("%s: %s (%s)" % (
        esc(item.get("syntax")), esc(item.get("state")), esc(item.get("evidence")))
        for item in measured + incomplete)
    rows = []
    details = []
    for component in usage.get("top_20", []):
        paths = "<br>".join('<span class="path" data-component-path="%s">%s</span>' % (
                            esc(path), esc(path))
                            for path in component.get("paths", []))
        most_used = " · ".join('<span class="tok">%s</span> × %d' % (
            esc(token_name(token)), token.get("references", 0))
            for token in component.get("tokens", [])[:5])
        rows.append(
            '<tr data-component="%s" data-component-kind="%s" '
            'data-component-references="%d" data-component-distinct-tokens="%d">'
            '<td class="num">%d</td><td><code>%s</code>'
            '<br><span class="p-mute">%s · %s</span><br>%s</td><td class="num">%d</td>'
            '<td class="num">%d</td><td>%s</td><td>%s</td></tr>' % (
                esc(component.get("id")), esc(component.get("kind")),
                component.get("references", 0), component.get("distinct_tokens", 0),
                component.get("rank", 0),
                esc(component.get("name")), esc(component.get("kind")),
                esc(component.get("confidence")), paths,
                component.get("references", 0), component.get("distinct_tokens", 0),
                family_text(component.get("families")), most_used,
            )
        )
        token_rows = []
        for token in component.get("tokens", []):
            locations = "<br>".join('<span class="path" data-token-location="%s">%s</span>' % (
                                      esc(location), esc(location))
                                      for location in token.get("locations", []))
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
            '<details data-component-detail="%s"><summary>#%d %s — %d references across %d tokens</summary>'
            '<div class="details-body"><div class="tbl-scroll"><table><thead><tr>'
            '<th>Token</th><th>Family</th><th class="num">References</th><th>Locations</th>'
            '</tr></thead><tbody>%s</tbody></table></div></div></details>' % (
                esc(component.get("id")), component.get("rank", 0), esc(component.get("name")),
                component.get("references", 0), component.get("distinct_tokens", 0),
                "".join(token_rows),
            )
        )
    return """
  <section id="component-usage">
    <div class="eyebrow">Token adoption</div>
    <h2>The 20 components using the most tokens</h2>
    <p class="lede">Found %d identified components with confirmed token usage across %d files in the declared scope, plus %d broader stylesheet surfaces. The table shows %d components; %d lower-volume components sit below this intentionally ranked view.%s</p>
    <div class="note"><b>Measurement boundary:</b> %s</div>
    <div class="tbl-scroll stack-16"><table><thead><tr><th class="num">Rank</th><th>Component or surface</th><th class="num">References</th><th class="num">Tokens</th><th>Families</th><th>Most-used tokens</th></tr></thead><tbody>%s</tbody></table></div>
    <div class="stack-16"><h3>Every token and evidence location for the Top 20</h3>%s</div>
  </section>
""" % (
        usage.get("total_components_with_token_usage", 0), usage.get("files_scanned", 0),
        usage.get("additional_style_surfaces", 0), usage.get("shown_components", 0),
        usage.get("not_shown", 0),
        (" %d fallback stylesheet surface(s) fill the remaining slots because fewer than 20 components were identified." % usage.get("fallback_surfaces", 0)) if usage.get("fallback_surfaces") else "",
        boundary,
        "".join(rows), "".join(details),
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
    if isinstance(report.get("run"), dict):
        report["run"]["generated_at"] = generated
    if isinstance(report.get("provenance"), dict):
        report["provenance"]["generated_at"] = generated
        report["provenance"]["skill_version"] = skill_version

    with open(html_path, encoding="utf-8") as handle:
        document = handle.read()
    section = render_section(usage)
    if SECTION.search(document):
        document = SECTION.sub("\n" + section, document, count=1)
    else:
        marker = LEAKAGE_MARKER if LEAKAGE_MARKER in document else MEASUREMENT_MARKER
        if marker not in document:
            raise ValueError("report has no component-usage, leakage, or measurement insertion point")
        document = document.replace(marker, section + "\n  " + marker, 1)
    document = sync_document_metadata(
        document, old_generated, generated, old_version, skill_version
    )
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
