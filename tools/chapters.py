#!/usr/bin/env python3
"""The report's front: what a reader sees before any evidence.

A person who audited your system and is telling a colleague what they found
opens with the finding, shows where each check stands, says what is waiting
on you and names the first move. Then they stop, and the evidence follows
for whoever keeps reading. This module renders that order.

Three rules hold it together, and each is checked in code elsewhere:

- every label for a grade comes from `vocab`, so there is one vocabulary;
- every first move comes from `moves.rank`, so there is one answer;
- a fact true of the whole run is rendered once, by `about_run`, and every
  other place links to it with `run_fact`.
"""
import datetime
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import draw  # noqa: E402
import moves  # noqa: E402
from vocab import (  # noqa: E402
    CHECK_ASKS, CHECK_LINE, CHECK_NAME, CHECK_ORDER, CHECK_PHRASE, GRADE_LABEL,
    GRADE_MEANING, GRADES, first_sentence, fmt, grade_counts, grade_of,
    join_and, measured, of, pct, plain, plural, sentence,
)

STAGES = ("scattered", "declared", "adopted", "layered", "complete", "held")

# Terms that stay because they are the real vocabulary. Each gets one
# sentence, the first time it appears, and is never explained again.
TERMS = {
    "token": "A named design decision, such as a color or a spacing step, "
             "that code refers to by name.",
    "primitive": "A token that holds a raw value, such as one hex color.",
    "semantic": "A token named for its job, such as text color, that points "
                "at a primitive.",
}


def esc(value):
    return html.escape(str(value), quote=True)


def json_attr(value):
    return esc(json.dumps(value, sort_keys=True, separators=(",", ":")))


def root_of(report):
    return (((report.get("discovery") or {}).get("repository") or {})
            .get("root"))


def words(report, text):
    """An audit note, escaped, in the report's vocabulary, with relative paths."""
    return esc(plain(text, root_of(report)))


def info(term, used=None):
    """The `(i)` beside a term, on its first use only."""
    if used is not None:
        if term in used:
            return ""
        used.add(term)
    return ('<span class="ihelp"><button type="button" class="info" '
            'aria-label="What %s means"></button><span class="tip" '
            'role="tooltip">%s</span></span>' % (esc(term), esc(TERMS[term])))


def run_fact(text):
    """A fact about the whole run, said elsewhere only as a link back to it."""
    return '<a class="runfact" href="#about-run">%s</a>' % esc(text)


def lower_first(text):
    """Lower the first letter so a sentence can follow a colon."""
    text = str(text or "")
    if len(text) > 1 and text[0].isupper() and not text[1].isupper():
        return text[0].lower() + text[1:]
    return text


# ─── The header: one fact line, and everything true of the whole run ───────

def repo_name(report):
    return os.path.basename(str(root_of(report) or "").rstrip("/")) or "repository"


def run_date(report):
    stamp = ((report.get("run") or {}).get("generated_at")
             or (report.get("provenance") or {}).get("generated_at") or "")
    try:
        when = datetime.datetime.strptime(stamp[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return "%s %d, %d" % (when.strftime("%b"), when.day, when.year)


def tree_state(report):
    """`uncommitted`, `3 commits behind`, or nothing when the run is at the commit."""
    fresh = report.get("freshness") or {}
    parts = []
    if fresh.get("dirty"):
        parts.append("uncommitted")
    behind = int(fresh.get("commits_since") or 0)
    if behind:
        parts.append("%s behind" % plural(behind, "commit"))
    return " · ".join(parts)


def tree_sentence(report):
    fresh = report.get("freshness") or {}
    behind = int(fresh.get("commits_since") or 0)
    if fresh.get("dirty") and behind:
        return ("Measured against your uncommitted changes, %s behind where "
                "the code is now." % plural(behind, "commit"))
    if fresh.get("dirty"):
        return "Measured against your uncommitted changes, not a commit."
    if behind:
        return "Measured %s ago. The code has moved since." % plural(behind, "commit")
    if fresh:
        return "Measured at the commit named above, with nothing uncommitted."
    return "We did not record whether the code has moved since this run."


def files_in_scope(report):
    discovery = report.get("discovery") or {}
    return len((discovery.get("owned_import_graph") or {}).get("reachable") or {})


def factline(report):
    """`agnostic @ 158abe57 · uncommitted · Nov 17, 2026 · 1,129 files · ...`."""
    run = report.get("run") or {}
    ref = str(((report.get("discovery") or {}).get("repository") or {})
              .get("ref") or run.get("repo_ref") or "")[:8]
    counts = grade_counts(report)
    total = sum(counts.values())
    parts = ["<b>%s</b>%s" % (esc(repo_name(report)),
                              " @ %s" % esc(ref) if ref else "")]
    state = tree_state(report)
    if state:
        parts.append(esc(state))
    if run_date(report):
        parts.append(esc(run_date(report)))
    scope = files_in_scope(report)
    if scope:
        parts.append(esc(plural(scope, "file")))
    if run.get("token_count") is not None:
        parts.append(esc(plural(run.get("token_count"), "token")))
    parts.append(esc("%s of %s measured" % (
        fmt(measured(counts)), plural(total, "check"))))
    return " · ".join(parts)


def about_run(report, summary, skill_version):
    """Everything that is true of the whole run, in the one place it is said."""
    discovery = report.get("discovery") or {}
    run = report.get("run") or {}
    usage = report.get("component_usage") or {}
    inventory = report.get("inventory") or {}
    roots = discovery.get("roots") or []
    owned = [item for item in roots if item.get("ownership") == "owned"]
    unknown = [item for item in roots if item.get("ownership") == "unknown"]
    scope = files_in_scope(report)

    # The denominators, named. Three different counts of files sat in three
    # sections under one word, and a reader could not tell which a share was of.
    file_rows = [("source files in scope", scope,
                  "Everything your entry files reach, in code you own.")]
    if run.get("files_scanned"):
        file_rows.append(("CSS files scanned", run.get("files_scanned"),
                          "Where we looked for hardcoded colors."))
    if run.get("token_consumer_files"):
        file_rows.append(("files that use a token", run.get("token_consumer_files"),
                          "Where a token is referenced by name."))
    if usage.get("files_scanned"):
        file_rows.append(("files read for component use", usage.get("files_scanned"),
                          "Where we counted token use by component."))
    biggest = max([count for _name, count, _why in file_rows] or [1]) or 1
    files_html = "".join(
        '<div class="about-fact" data-run-fact="%s"><span class="about-n">%s</span>'
        '<span class="about-what">%s</span>%s<span class="about-why">%s</span></div>'
        % (esc(name.replace(" ", "-")), esc(fmt(count)), esc(name),
           draw.bar(count, biggest, name), esc(why))
        for name, count, why in file_rows if count)

    profiles = " + ".join(str(item).replace("-", " ").title()
                          for item in discovery.get("environment") or [])
    versions = " · ".join("%s %s" % (name, version) for name, version in sorted(
        (run.get("framework_versions") or {}).items()))
    setup = [("framework", " · ".join(item for item in (profiles, versions) if item)
              or "not confirmed")]
    entry = plural(len(roots), "entry file")
    if roots:
        entry += " (%s owned%s)" % (
            fmt(len(owned)),
            ", %s with no owner" % fmt(len(unknown)) if unknown else "")
    setup.append(("entry files", entry))
    setup.append(("token files", plural(summary.get("token_sources", 0),
                                        "confirmed source")))
    declared = (report.get("declared") or {}).get("modes") or []
    if declared:
        setup.append(("themes you declared", ", ".join(declared)))
    patterns = ((discovery.get("ownership") or {}).get("owned_patterns")
                or (discovery.get("ownership") or {}).get("inferred_owned_patterns")
                or [])
    setup_html = "".join("<dt>%s</dt><dd>%s</dd>" % (esc(name), esc(value))
                         for name, value in setup)
    if patterns:
        setup_html += (
            '<dt>code you own</dt><dd>%s<details class="about-more"><summary>'
            'Show them</summary><div class="details-body">%s</div></details></dd>'
            % (esc(plural(len(patterns), "path pattern")),
               "<br>".join('<span class="path">%s</span>' % esc(item)
                           for item in patterns)))

    left_out = [words(report, line) for line in run.get("scope") or []]
    held = inventory.get("candidate_or_local_override_sources") or []
    if held:
        left_out.append(
            "%s held out: %s values that look like tokens, and we counted none of them."
            % (esc(plural(len(held), "file")),
               "it sets" if len(held) == 1 else "they set"))
    stuck = summary.get("unresolved_actionable", 0)
    if stuck:
        left_out.append("%s we couldn't follow." % esc(plural(stuck, "import")))
    left_html = "".join("<li>%s</li>" % line for line in left_out) or (
        "<li>Nothing was left out on purpose.</li>")

    adapters = (report.get("provenance") or {}).get("adapter_versions") or {}
    version_rows = [
        ("report format", report.get("schema_version")),
        ("design-token-vitals", skill_version),
        ("adapters", " · ".join(sorted(adapters)) or "none"),
        ("generated", (run.get("generated_at") or "")[:19].replace("T", " ")
         + (" UTC" if run.get("generated_at") else "")),
    ]
    versions_html = "".join(
        "<dt>%s</dt><dd>%s</dd>" % (esc(name), esc(value))
        for name, value in version_rows if value not in (None, ""))

    return (
        '<details class="about" id="about-run" data-measurement-summary-json="%s" '
        'data-adapter-versions-json="%s" data-held-out-sources="%d">'
        '<summary>About this run</summary><div class="details-body about-grid">'
        '<div class="about-block about-files"><h3>What we read</h3>%s</div>'
        '<div class="about-block"><h3>Your setup</h3><dl class="facts">%s</dl></div>'
        '<div class="about-block"><h3>What we left out</h3><ul>%s</ul></div>'
        '<div class="about-block"><h3>How current it is</h3><p>%s</p>'
        '<!-- SLOT:validation-note --><p class="about-validation" '
        'data-validated="false">Not validated yet.</p><!-- /SLOT:validation-note -->'
        '</div><div class="about-block"><h3>Versions</h3><dl class="facts">%s</dl>'
        '</div></div></details>'
        % (json_attr(summary), json_attr(adapters), len(held), files_html,
           setup_html, left_html, esc(tree_sentence(report)), versions_html))


# ─── 00 Verdict ───────────────────────────────────────────────────────────

def verdict_sentence(report):
    """The one sentence the page opens on: what we found."""
    fixes = moves.fix_moves(report)
    if fixes:
        lead = lower_first(plain(fixes[0]["title"], root_of(report)))
        if len(fixes) == 1:
            return "One confirmed defect: %s" % lead
        return "%s. The first: %s" % (
            plural(len(fixes), "confirmed defect"), lead)
    counts = grade_counts(report)
    decisions = moves.decide_moves(report)
    blocked = counts["not-visible"]
    if decisions:
        return "Nothing confirmed to fix. %s" % plain(
            decisions[0]["title"], root_of(report))
    if blocked:
        return ("Nothing to fix in what we could see. We couldn't see %s."
                % plural(blocked, "check"))
    if counts["watch"]:
        return "Nothing to fix. %s worth a look." % (
            "One check is" if counts["watch"] == 1
            else "%s are" % plural(counts["watch"], "check"))
    return "Every check is healthy."


def render_headline(report):
    return ('<p class="verdict-line" data-report-region="headline">%s</p>'
            % esc(verdict_sentence(report)))


def states(report):
    return [(name, CHECK_NAME[name], grade_of(report, name))
            for name in CHECK_ORDER]


def render_move(move, report, position=None, inline_command=False):
    """One move, the same wherever it is shown."""
    root = root_of(report)
    fix = move["kind"] == "fix"
    lead = move.get("action") if fix else move["title"]
    rest = "" if fix else move.get("detail") or ""
    where = move.get("where")
    parts = ['<span class="move-verb" data-kind="%s">%s</span>'
             % (esc(move["kind"]), esc(move["verb"]))]
    parts.append('<span class="move-do">%s</span>' % esc(plain(lead, root)))
    if rest:
        parts.append('<span class="move-why">%s</span>' % esc(plain(rest, root)))
    if where:
        parts.append('<span class="path">%s</span>' % esc(plain(where, root)))
    if move.get("command") and inline_command:
        parts.append(command_row(move["command"], root))
    number = ('<span class="move-n">%d</span>' % position
              if position is not None else "")
    return ('<div class="move" data-move="%s" data-move-kind="%s">%s'
            '<div class="move-body">%s</div></div>'
            % (esc(move["id"]), esc(move["kind"]), number, "".join(parts)))


def command_row(command, root=None):
    """A command as something to copy, never as a sentence to read."""
    text = plain(command, root)
    return ('<div class="cmd-row"><code data-copy-source>%s</code>'
            '<button type="button" class="copy" data-copy '
            'aria-label="Copy command">Copy</button></div>' % esc(text))


def render_glance(report):
    """The strip of eight, what blocked means, and the three counters."""
    counts = grade_counts(report)
    count_attrs = " ".join(
        'data-count-%s="%d"' % (grade, counts[grade]) for grade in GRADES)
    legend = "".join(
        "<span><b>%s</b> %s</span>" % (esc(GRADE_LABEL[grade]),
                                       esc(GRADE_MEANING[grade]))
        for grade in GRADES)
    blocked_line = (
        '<p class="verdict-means">Blocked means we couldn’t see it — not that '
        'your code is wrong.</p>' if counts["not-visible"] else "")
    counters = "".join(
        '<a class="counter" data-kind="%s" data-count="%d" href="%s">'
        '<b>%s</b><span><strong>%s</strong>%s</span></a>'
        % (esc(item["kind"]), item["count"], esc(item["href"]),
           esc(fmt(item["count"])), esc(item["label"]), esc(item["unit"]))
        for item in moves.counters(report))
    return (
        '<div class="verdict-glance" data-report-region="at-a-glance">'
        '<div class="verdict-strip" id="confidence" data-check-total="%d" %s>'
        '%s<div class="verdict-notes">%s<details class="legend-more"><summary>'
        'What the five states mean</summary><div class="details-body legend">'
        '%s</div></details></div></div>'
        '<div class="counters">%s</div></div>'
        % (sum(counts.values()), count_attrs, draw.strip(states(report)),
           blocked_line or '<p class="verdict-means"></p>', legend, counters))


def render_first_move(report):
    """The first move. Inline command only when the move is an unlock."""
    summary = report.get("executive_summary") or {}
    move = moves.first(report)
    if not move:
        body = ('<p class="move-none">Nothing is waiting on you. Run this again '
                'after your next token change.</p>')
        move_id = ""
    else:
        body = render_move(move, report, inline_command=move["kind"] == "unlock")
        body += ('<a class="move-more" href="%s">See the evidence</a>'
                 % esc(move["href"]))
        move_id = move["id"]
    return (
        '<div class="first-move" id="summary" data-report-region="exec-summary" '
        'data-first-move="%s" data-executive-summary-json="%s">'
        '<h3>First move</h3>%s</div>'
        % (esc(move_id), json_attr(summary), body))


# ─── 01 Fix now ───────────────────────────────────────────────────────────

def sub_fix_now(report):
    fixes = moves.fix_moves(report)
    return (plural(len(fixes), "confirmed defect") if fixes
            else "Nothing confirmed to fix")


def render_fix_now(report):
    root = root_of(report)
    cards = []
    for move in moves.fix_moves(report):
        drawing = ""
        if move.get("declarations"):
            drawing = draw.figure(
                draw.declarations([
                    dict(item, location=plain(item.get("location"), root))
                    for item in move["declarations"]]),
                means=esc("Both set the same thing in the same place. "
                          "Only the last one takes effect."),
                kind="pair")
        reach = ""
        if move.get("reach"):
            reach = ('<p class="fix-reach"><b>How far the fix reaches</b> %s</p>'
                     % esc(sentence(plain(move["reach"], root))))
        cards.append(
            '<article class="fix-card" id="fix-%s" data-fix-check="%s">'
            '<h3>%s</h3>%s%s%s<a class="move-more" href="#vital-%s">'
            'What we measured</a></article>'
            % (esc(move["check"]), esc(move["check"]),
               esc(plain(move["title"], root)), drawing,
               render_move(move, report), reach, esc(move["check"])))
    if not cards:
        cards.append('<p class="quiet">We found nothing we can call a defect '
                     'with a place to point at.</p>')

    queue = report.get("fix_queue") or []
    if queue:
        rows = []
        for index, item in enumerate(queue):
            location = (item.get("locations") or ["—"])[0]
            rows.append(
                '<tr data-finding="%s" data-fix-queue-index="%d" '
                'data-fix-queue-json="%s"><td><code>%s</code></td>'
                '<td><span class="lit">%s</span></td><td><span class="tok">%s'
                '</span></td><td>%s</td><td>%s</td><td>%s</td>'
                '<td><span class="path">%s</span></td></tr>'
                % (esc(item.get("id")), index, json_attr(item),
                   esc(item.get("id")), esc(item.get("literal")),
                   esc(item.get("replacement")), esc(item.get("confidence")),
                   esc(item.get("effort", "—")),
                   "a script can do it" if item.get("safe_to_automate")
                   else "needs a person", esc(plain(location, root))))
        table = (
            '<h3 class="part">Replacements ready to make</h3>'
            '<div class="tbl-scroll"><table><thead><tr><th>Finding</th>'
            '<th>Hardcoded value</th><th>Use this token</th><th>How sure</th>'
            '<th>Effort</th><th>Who</th><th>First place</th></tr></thead>'
            '<tbody>%s</tbody></table></div>' % "".join(rows))
    else:
        table = ('<p class="quiet">No replacement is ready to make by script. '
                 'A matching value is not yet a matching decision, so each '
                 'match waits in <a href="#decide">Decide</a>.</p>')
    return '<div data-report-region="fix-queue">%s%s</div>' % (
        "".join(cards), table)


def render_groups(report):
    groups = report.get("groups") or {}
    rows = []
    index = 0
    for kind, items in groups.items():
        for item in items or []:
            name = (item.get("name") or item.get("owner") or item.get("id")
                    or "unnamed")
            rows.append(
                '<tr data-group-index="%d" data-group-kind="%s" '
                'data-group-json="%s"><td><code>%s</code></td><td>%s</td>'
                '<td class="num">%d</td></tr>'
                % (index, esc(kind), json_attr(item), esc(name), esc(kind),
                   len(item.get("findings") or [])))
            index += 1
    if rows:
        body = (
            '<details><summary>The same fixes, grouped by who owns them'
            '</summary><div class="details-body"><div class="tbl-scroll"><table>'
            '<thead><tr><th>Owner</th><th>Group</th><th class="num">Findings'
            '</th></tr></thead><tbody>%s</tbody></table></div></div></details>'
            % "".join(rows))
    else:
        body = ('<p class="quiet">Nothing is grouped by owner yet, because '
                'nothing is ready to replace.</p>')
    return '<div data-report-region="groups">%s</div>' % body


# ─── 02 Decide ────────────────────────────────────────────────────────────

LEAK_GROUP = {
    "exact-value-candidate": "matches a token",
    "exact-value candidate": "matches a token",
    "uncovered-candidate": "no matching token",
    "uncovered candidate": "no matching token",
    "near-miss": "close to a token",
    "redundant": "same as a token",
}


def sub_decide(report):
    leakage = report.get("leakage_analysis") or {}
    exact = len(leakage.get("exact_value_candidates") or [])
    uncovered = len(leakage.get("uncovered_candidates") or [])
    calls = len(report.get("decisions") or [])
    parts = []
    if exact or uncovered:
        parts.append("%s %s a token" % (
            plural(exact, "hardcoded color"), "matches" if exact == 1 else "match"))
        parts.append("%s match nothing" % fmt(uncovered))
    if calls:
        parts.append(plural(calls, "close call"))
    return " · ".join(parts) or "Nothing is waiting on your call"


def render_decide_calls(report):
    calls = moves.decide_moves(report)
    if not calls:
        return ('<div class="moves" data-report-region="decide-calls">'
                '<p class="quiet">Nothing is waiting on your call.</p></div>')
    return '<div class="moves" data-report-region="decide-calls">%s</div>' % "".join(
        render_move(move, report) for move in calls)


def render_leakage(report, leakage):
    """Hardcoded colors: the ones that match a token, drawn beside it."""
    root = root_of(report)
    exact = leakage.get("exact_value_candidates") or []
    uncovered = leakage.get("uncovered_candidates") or []
    scanned = leakage.get("consumer_files_scanned", 0)
    total = len(exact) + len(uncovered)
    if not scanned:
        lead = draw.figure(
            draw.hatch("We read no CSS that uses your tokens"),
            means="We found no stylesheet of yours to check, so we can’t say "
                  "whether colors are hardcoded. That is not the same as none.",
            kind="hatch")
    elif not total:
        lead = ('<p class="quiet">We found no hardcoded color in %s.</p>'
                % run_fact("the %s" % plural(scanned, "CSS file") + " scanned"))
    else:
        lead = draw.figure(
            draw.stack([("match a token", len(exact), "warn"),
                        ("match nothing", len(uncovered), "mute")], total),
            "%s · %s" % (of(len(exact), total), "the rest match nothing"),
            "%s the same value as a token. Whether %s the same decision is "
            "your call. Found in %s."
            % ("One hardcoded color has" if len(exact) == 1
               else "%s have" % esc(plural(len(exact), "hardcoded color")),
               "it means" if len(exact) == 1 else "they mean",
               run_fact("the %s scanned" % plural(scanned, "CSS file"))),
            kind="stack")

    pairs = []
    for item in exact:
        tokens = item.get("token_candidates") or []
        first = (item.get("locations") or [""])[0]
        pairs.append(
            '<div class="match" data-match="%s">%s<span class="match-eq" '
            'aria-hidden="true">=</span><span class="match-tokens">%s</span>'
            '<span class="match-uses">%s in %s</span><span class="path">%s</span>'
            '</div>'
            % (esc(item.get("id")), draw.swatch(item.get("literal")),
               " ".join('<span class="tok">%s</span>' % esc(token)
                        for token in tokens) or "—",
               esc(plural(item.get("occurrences", 0), "use")),
               esc(plural(item.get("files", 0), "file")),
               esc(plain(first, root))))
    pairs_html = ('<div class="matches">%s</div>' % "".join(pairs)) if pairs else ""

    rows = []
    for item in exact + uncovered:
        candidates = " ".join(
            '<span class="tok">%s</span>' % esc(token)
            for token in item.get("token_candidates", [])) or "—"
        locations = item.get("locations", [])
        tags = ['<span class="path" data-finding-location="%s">%s</span>'
                % (esc(location), esc(plain(location, root)))
                for location in locations]
        if len(tags) > 1:
            where = (tags[0] + '<details><summary>Show %s</summary><div>%s</div>'
                     '</details>' % (esc(plural(len(tags) - 1, "more place")),
                                     "<br>".join(tags[1:])))
        else:
            where = tags[0] if tags else "—"
        rows.append(
            '<tr data-finding="%s" data-finding-tier="%s" '
            'data-finding-locations-json="%s" '
            'data-finding-token-candidates-json="%s" '
            'data-finding-properties-json="%s"><td>%s</td><td>%s</td><td>%s</td>'
            '<td class="num">%d</td><td class="num">%d</td><td>%s</td><td>%s</td>'
            '</tr>'
            % (esc(item.get("id")), esc(item.get("tier")), json_attr(locations),
               json_attr(item.get("token_candidates", [])),
               json_attr(item.get("properties", [])),
               draw.swatch(item.get("literal")),
               esc(LEAK_GROUP.get(str(item.get("tier")), str(item.get("tier")))),
               candidates, item.get("occurrences", 0), item.get("files", 0),
               esc(", ".join(item.get("properties", [])) or "unknown"), where))
    table = ""
    if rows:
        table = (
            '<details><summary>All %s, with every place</summary>'
            '<div class="details-body"><div class="tbl-scroll"><table><thead><tr>'
            '<th>Hardcoded color</th><th>What we found</th><th>Possible tokens</th>'
            '<th class="num">Uses</th><th class="num">Files</th><th>Used for</th>'
            '<th>Where</th></tr></thead><tbody>%s</tbody></table></div></div>'
            '</details>' % (esc(plural(total, "hardcoded color")), "".join(rows)))
    return ('\n  <section id="leakage"><h3 class="part">Hardcoded colors that '
            'match a token</h3>%s%s%s</section>\n' % (lead, pairs_html, table))


def render_decisions(report):
    """The close calls: this reading and the other one, as two dots each."""
    decisions = report.get("decisions") or []
    root = root_of(report)
    if not decisions:
        return ('<div data-report-region="decisions"><p class="quiet">We made '
                'no call that could have gone the other way.</p></div>')
    rows = []
    for index, item in enumerate(decisions):
        checks = [name for name in item.get("vitals") or [] if name in CHECK_NAME]
        other = item.get("other_grade")
        this_dots, other_dots = [], []
        for name in checks:
            this_dots.append(draw.grade_dot(
                grade_of(report, name),
                "%s: %s" % (CHECK_NAME[name], GRADE_LABEL.get(
                    grade_of(report, name), "Blocked"))))
            grade = other.get(name) if isinstance(other, dict) else other
            other_dots.append(draw.grade_dot(
                grade, "%s: %s" % (CHECK_NAME[name], GRADE_LABEL[grade])
                if grade in GRADES else
                "%s: we did not grade the other reading" % CHECK_NAME[name]))
        decision = plain(item.get("decision"), root)
        lead = first_sentence(decision)
        rest = decision[len(lead):].strip()
        rows.append(
            '<tr data-decision-index="%d" data-decision-json="%s">'
            '<td class="num">%d</td><td><span class="call">%s</span>'
            '<details class="call-more"><summary>Why, and the other reading'
            '</summary><div class="details-body">%s<p><b>What it moved</b> %s</p>'
            '<p><b>The other reading</b> %s</p></div></details></td>'
            '<td>%s</td><td class="dots">%s</td><td class="dots">%s</td></tr>'
            % (index, json_attr(item), index + 1, esc(lead),
               "<p>%s</p>" % esc(rest) if rest else "",
               esc(plain(item.get("moved"), root)),
               esc(plain(item.get("other_reading"), root)),
               esc(", ".join(CHECK_NAME[name] for name in checks)
                   or "The whole run"),
               "".join(this_dots) or "—", "".join(other_dots) or "—"))
    return (
        '<div data-report-region="decisions"><div class="tbl-scroll">'
        '<table class="calls"><thead><tr><th class="num">#</th>'
        '<th>The call we made</th><th>Check</th><th>This reading</th>'
        '<th>Other reading</th></tr></thead><tbody>%s</tbody></table></div>'
        '<p class="mk-means">A dot is the grade under that reading. A ring '
        'means we did not grade it that way. If the other reading fits your '
        'system better, say so and the next run starts from your answer.</p>'
        '</div>' % "".join(rows))


# ─── 03 Unlock ────────────────────────────────────────────────────────────

def blocked_until(report, name):
    """`imports resolve and token files are found`, for one blocked check."""
    from unlock_path import CAPABILITY_UNTIL
    entry = ((report.get("confidence") or {}).get("confidence") or {}).get(name) or {}
    return join_and([CAPABILITY_UNTIL.get(item, item.replace("_", " "))
                     for item in entry.get("blocked_by") or []])


def sub_unlock(report):
    from unlock_path import until
    blocked = moves.blocked_checks(report)
    if not blocked:
        return "Nothing is blocked"
    waiting = until((report.get("confidence") or {}).get("unlock_path") or [])
    return "%s blocked%s" % (plural(len(blocked), "check"),
                             " until %s" % waiting if waiting else "")


def render_unlock(report):
    """Each blocked check once: one sentence, and its command behind a button."""
    root = root_of(report)
    confidence = report.get("confidence") or {}
    steps = {step.get("capability"): step
             for step in confidence.get("unlock_path") or []}
    states_by_check = confidence.get("confidence") or {}
    items = []
    for name in moves.blocked_checks(report):
        entry = states_by_check.get(name) or {}
        needs = [steps[item] for item in entry.get("blocked_by") or []
                 if item in steps]
        waiting = blocked_until(report, name)
        line = ('<a href="#vital-%s"><b>%s</b></a> is blocked%s.'
                % (esc(name), esc(CHECK_NAME[name]),
                   " until %s" % esc(waiting) if waiting else
                   ", and nothing we recorded says why"))
        commands = "".join(
            '<p>%s</p>%s' % (esc(sentence(plain(step.get("action"), root))),
                             command_row(step.get("verify"), root)
                             if step.get("verify") else "")
            for step in needs)
        disclosure = ""
        if commands:
            disclosure = ('<details class="cmd"><summary>Show command</summary>'
                          '<div class="details-body">%s</div></details>' % commands)
        items.append(
            '<li data-blocked-check="%s" data-unlock-capabilities="%s">%s'
            '<div class="unlock-body"><p>%s</p>%s</div></li>'
            % (esc(name), esc(" ".join(entry.get("blocked_by") or [])),
               draw.hatch(), line, disclosure))
    if items:
        body = ('<ul class="unlock-list">%s</ul><p class="mk-means">Hatched '
                'means we couldn’t see it. None of this says your code is '
                'wrong.</p>' % "".join(items))
    else:
        body = '<p class="quiet">We could see everything we needed to.</p>'
    owed = confidence.get("decisions_owed") or []
    owed_html = ""
    if owed:
        owed_html = (
            '<p class="quiet" data-decisions-owed="%d">%s marked not needed '
            'with no reason on record. A check switched off without one stays '
            'off quietly.</p>'
            % (len(owed), esc(join_and([CHECK_NAME.get(name, name)
                                        for name in owed])
                              + (" is" if len(owed) == 1 else " are"))))
    return ('<div data-report-region="unlock-path" data-split-json="%s">%s%s</div>'
            % (json_attr(confidence.get("split") or {}), body, owed_html))


# ─── 05 Checks ────────────────────────────────────────────────────────────

def render_measure(report, vital, grade):
    """The drawing for one check, from the reading the run recorded."""
    measure = vital.get("measure") or {}
    form = measure.get("form")
    root = root_of(report)
    part, whole, noun = measure.get("part"), measure.get("whole"), measure.get("noun")
    tone = {"healthy": "pass", "watch": "warn", "needs-work": "fail"}.get(grade, "ink")
    mark, text = "", None
    if form == "threshold" and measure.get("value") is not None:
        mark = draw.threshold(measure["value"], measure.get("max") or 0,
                              measure.get("lines") or [], measure.get("unit", ""),
                              noun)
        reading = "%s%s" % (draw._trim(measure["value"]), measure.get("unit", ""))
        # The reading is printed as measured. Rounding 4.7% to 5% would put
        # it on a line it is under.
        text = ("%s of %s%s (%s)" % (fmt(part), fmt(whole),
                                     " %s" % noun if noun else "", reading)
                if part is not None and whole
                else "%s%s" % (reading, " %s" % noun if noun else ""))
    elif form == "cells" and part is not None and whole:
        mark = draw.cells(part, whole, noun, tone)
        text = "%s of %s%s" % (fmt(part), fmt(whole), " %s" % noun if noun else "")
    elif form == "dots" and part is not None and whole:
        mark = draw.dots(part, whole, noun, measure.get("mark", "hollow"))
        text = of(part, whole, noun)
    elif form == "bar" and part is not None and whole:
        mark = draw.bar(part, whole, noun, tone)
        text = of(part, whole, noun)
    means = esc(plain(measure.get("means"), root)) if measure.get("means") else None
    if not mark:
        if grade == "not-visible":
            return draw.figure(draw.hatch(), kind="hatch")
        return ""
    kind = form
    if grade == "not-visible":
        # A count we have, behind a grade we don't: drawn, and marked as unseen.
        mark = draw.hatch("Not graded") + mark
        kind = "hatch-" + form
    return draw.figure(mark, text, means, kind=kind)


def render_checks(report):
    """The eight cards: what each check asks, and what we measured. No grade word.

    The grade is stated once, in the verdict strip. A card keeps the stripe,
    which is a drawing of it, and links back to the strip for the word.
    """
    root = root_of(report)
    cards = []
    for name in CHECK_ORDER:
        vital = (report.get("vitals") or {}).get(name) or {}
        grade = vital.get("grade", "not-visible")
        note = plain(vital.get("note") or "We recorded nothing for this check.", root)
        evidence = [plain(item, root) for item in vital.get("evidence") or []]
        drawing = render_measure(report, vital, grade)
        # One line under a drawing. When the drawing already carries its
        # line, the longer note and the other places wait behind a disclosure.
        has_line = 'class="mk-means"' in drawing
        places = "<br>".join('<span class="path">%s</span>' % esc(item)
                             for item in evidence[1:])
        behind = "".join(part for part in (
            '<p>%s</p>' % esc(note) if has_line else "",
            '<p>%s</p>' % places if places else "") if part)
        more = ""
        if behind:
            more = ('<details class="evidence-more"><summary>%s</summary>'
                    '<div class="details-body">%s</div></details>'
                    % ("What we found, in full" if has_line else
                       esc(plural(len(evidence) - 1, "more place")), behind))
        where = ('<p class="vital-where"><span class="path">%s</span></p>'
                 % esc(evidence[0])) if evidence else ""
        cards.append(
            '<article class="vital" id="vital-%s" data-vital="%s" data-grade="%s">'
            '<h3>%s</h3><p class="vital-asks">%s</p>%s%s%s%s'
            '<a class="vital-back" href="#confidence">Its grade, in the verdict'
            '</a></article>'
            % (esc(name), esc(name), esc(grade), esc(CHECK_NAME[name]),
               esc(CHECK_ASKS[name]), drawing,
               "" if has_line else '<p class="vital-note">%s</p>' % esc(note),
               where, more))
    return '<div class="vitals">%s</div>' % "".join(cards)


# ─── 08 to 11: evidence chapters that open with a drawing ─────────────────

def sub_lineage(report):
    summary = (report.get("token_chains") or {}).get("summary") or {}
    traced = summary.get("traced_to_a_primitive")
    if traced is None:
        return "Where each token gets its value"
    total = traced + summary.get("stops_before_a_primitive", 0)
    return "%s trace back to a raw value" % of(traced, total, "tokens")


def render_lineage_lead(report, used=None):
    summary = (report.get("token_chains") or {}).get("summary") or {}
    traced = summary.get("traced_to_a_primitive")
    if traced is None:
        return ""
    stops = summary.get("stops_before_a_primitive", 0)
    total = traced + stops
    means = ("Most tokens%s lead back to a primitive%s. %s"
             % (info("token", used), info("primitive", used),
                "%s before one, so we can’t say where %s from."
                % ("One stops" if stops == 1 else "%s stop" % esc(fmt(stops)),
                   "its value comes" if stops == 1 else "their values come")
                if stops else "None stops short."))
    return draw.figure(draw.bar(traced, total, "tokens", "pass"),
                       of(traced, total), means)


def lineage_rows(items, report, start=0):
    root = root_of(report)
    rows = []
    for index, item in enumerate(items, start=start):
        origin = item.get("root") or {}
        consumers = item.get("consumers") or []
        hops = item.get("hops") or []
        stops = item.get("stops_at")
        rows.append(
            '<tr data-lineage-index="%d" data-lineage-token="%s" '
            'data-lineage-json="%s"><td><code>%s</code></td><td>%s</td>'
            '<td>%s</td><td class="num">%d</td><td class="num">%d</td><td>%s</td>'
            '</tr>'
            % (index, esc(item.get("token")), json_attr(item),
               esc(item.get("token")), esc(item.get("tier") or "—"),
               ('<code>%s</code> <span class="path">%s</span>'
                % (esc(origin.get("token") or ""),
                   esc(plain(origin.get("site") or "", root))))
               if origin else "—",
               max(len(hops) - 1, 0), len(consumers),
               "yes" if item.get("complete") else esc(
                   "stops at %s" % plain(stops, root) if stops
                   else plain(item.get("note") or "no", root))))
    return "".join(rows)


def render_lineage(report, initial=20):
    lineage = report.get("lineage") or []
    if not lineage:
        return ('<div data-report-region="lineage"><p class="quiet">We traced '
                'no token to its source.</p></div>')
    headings = (
        '<thead><tr><th>Token</th><th>Layer</th><th>Where its value starts</th>'
        '<th class="num">Steps</th><th class="num">Used by</th>'
        '<th>Traced to a raw value</th></tr></thead>')
    body = ('<div class="tbl-scroll"><table>%s<tbody>%s</tbody></table></div>'
            % (headings, lineage_rows(lineage[:initial], report)))
    if len(lineage) > initial:
        tail = lineage[initial:]
        body += (
            '<details class="stack-16"><summary>See %s</summary>'
            '<div class="details-body"><div class="tbl-scroll"><table>%s<tbody>%s'
            '</tbody></table></div></div></details>'
            % (esc(plural(len(tail), "more token")), headings,
               lineage_rows(tail, report, start=initial)))
    return (
        '<div data-report-region="lineage"><details><summary>Every token, and '
        'where its value comes from</summary><div class="details-body">%s</div>'
        '</details></div>' % body)


def render_reach(lineage):
    """How far a change to one token reaches: the components that would move."""
    rows = (lineage or {}).get("blast_radius") or []
    reaching = [row for row in rows if row.get("component_count")]
    if not reaching:
        return ('<div data-report-region="blast-radius" data-radius-rows="0">'
                '<p class="quiet">We could not tie a token to the components '
                'that use it, so we can’t draw how far a change reaches.</p></div>')
    widest = max(row["component_count"] for row in reaching) or 1
    body = "".join(
        '<tr data-token="%s" data-component-count="%d"><td><code class="path">%s'
        '</code></td><td>%s</td><td>%s</td><td class="num">%d</td><td>%s</td></tr>'
        % (esc(row["token"]), row["component_count"], esc(row["token"]),
           esc(row.get("tier") or ""),
           draw.share(row["component_count"], widest,
                      fmt(row["component_count"])),
           len(row.get("dependent_tokens") or []),
           esc(", ".join(row.get("components") or [])))
        for row in reaching[:20])
    tail = ""
    if len(reaching) > 20:
        tail = ('<details><summary>See %s</summary><div class="details-body">%s'
                '</div></details>'
                % (esc(plural(len(reaching) - 20, "more token")),
                   "<br>".join(esc("%s: %s" % (
                       row["token"], plural(row["component_count"], "component")))
                       for row in reaching[20:])))
    return (
        '<div data-report-region="blast-radius" data-radius-rows="%d">'
        '<h3 class="part">How far a change reaches</h3><div class="tbl-scroll">'
        '<table><thead><tr><th>Token</th><th>Layer</th><th>Components that '
        'would move</th><th class="num">Tokens built on it</th><th>Which '
        'components</th></tr></thead><tbody>%s</tbody></table></div>%s'
        '<p class="mk-means">Change one of these and every component in its '
        'row changes with it. The longest bar is the widest reach.</p></div>'
        % (len(reaching), body, tail))


CELL_LABEL = {"counted": "Measured", "not-visible": "Blocked",
              "not-needed": "Not needed"}
CELL_TONE = {"counted": "pass", "not-visible": "hatch", "not-needed": "mute"}


def cell_counts(report):
    cells = (report.get("coverage_matrix") or {}).get("cells") or []
    counts = {"counted": 0, "not-visible": 0, "not-needed": 0}
    for item in cells:
        state = item.get("state", "not-visible")
        counts[state if state in counts else "not-visible"] += 1
    return counts


def sub_coverage(report):
    matrix = report.get("coverage_matrix") or {}
    counts = cell_counts(report)
    total = sum(counts.values())
    if not total:
        return "We recorded no coverage"
    return "%s × %s × %s" % (
        plural(len(matrix.get("bundles") or []), "bundle"),
        plural(len(matrix.get("modes") or []), "theme"),
        plural(len(matrix.get("families") or []), "family", "families"))


def render_coverage_matrix(report):
    matrix = report.get("coverage_matrix") or {}
    bundles = matrix.get("bundles") or []
    modes = matrix.get("modes") or []
    families = matrix.get("families") or []
    keyed = {(item.get("bundle"), item.get("mode"), item.get("family")): item
             for item in matrix.get("cells") or []}
    counts = cell_counts(report)
    total = sum(counts.values())
    headers = "".join('<th class="fam">%s</th>' % esc(family) for family in families)
    rows = []
    for bundle in bundles:
        for mode in modes:
            columns = []
            for family in families:
                item = keyed.get((bundle, mode, family), {
                    "bundle": bundle, "mode": mode, "family": family,
                    "state": "not-visible", "evidence": [],
                    "note": "No coverage cell was recorded.",
                })
                state = item.get("state", "not-visible")
                label = CELL_LABEL.get(state, "Blocked")
                columns.append(
                    '<td class="cell" data-coverage-cell="%s" '
                    'data-coverage-json="%s"><span class="c" data-s="%s" '
                    'title="%s"><span class="sr">%s</span></span></td>'
                    % (esc("%s|%s|%s" % (bundle, mode, family)), json_attr(item),
                       esc(state), esc(label), esc(label)))
            rows.append('<tr><td>%s · %s</td>%s</tr>' % (
                esc(bundle), esc(mode), "".join(columns)))
    lead = ""
    if total:
        lead = draw.figure(
            draw.stack([(CELL_LABEL[state].lower(), counts[state], CELL_TONE[state])
                        for state in ("counted", "not-visible", "not-needed")],
                       total),
            " · ".join("%s %s" % (fmt(counts[state]), CELL_LABEL[state].lower())
                       for state in ("counted", "not-visible", "not-needed")),
            "Each cell is one bundle in one theme for one family. Hatched is "
            "where we couldn’t see; empty is where a theme doesn’t apply.",
            kind="stack")
    return (
        '<div data-report-region="coverage-matrix">%s<div class="tbl-scroll">'
        '<table class="cm"><thead><tr><th>Bundle · theme</th>%s</tr></thead>'
        '<tbody>%s</tbody></table></div><div class="split stack-12">'
        '<span class="ok">Measured</span><span class="block">Blocked</span>'
        '<span class="unk">Not needed</span></div></div>'
        % (lead, headers, "".join(rows)))


def theme_pairs(report):
    resolution = (report.get("discovery") or {}).get("mode_resolution") or {}
    audited = resolution.get("audited_pairs") or []
    resolved = {(item.get("bundle"), item.get("mode"))
                for item in resolution.get("resolved_pairs") or []}
    return audited, resolved, resolution.get("blocked_reason")


def sub_modes(report):
    audited, resolved, _reason = theme_pairs(report)
    if not audited:
        return "We recorded no themes to check"
    return "%s resolved" % of(len(resolved), len(audited),
                              "bundle and theme pairs")


def render_modes(report):
    matrix = report.get("coverage_matrix") or {}
    audited, resolved, reason = theme_pairs(report)
    bundles = list(dict.fromkeys(item.get("bundle") for item in audited))
    themes = list(dict.fromkeys(item.get("mode") for item in audited))
    grid = ""
    if audited:
        head = "".join("<th>%s</th>" % esc(theme) for theme in themes)
        body = "".join(
            "<tr><td>%s</td>%s</tr>" % (esc(bundle), "".join(
                '<td class="cell"><span class="c" data-s="%s" title="%s">'
                '<span class="sr">%s</span></span></td>'
                % (("counted", "Resolved", "Resolved")
                   if (bundle, theme) in resolved
                   else ("not-visible", "Blocked", "Blocked"))
                for theme in themes))
            for bundle in bundles)
        means = (words(report, first_sentence(reason)) if reason and
                 len(resolved) < len(audited) else
                 "Every theme resolved, so each token could be checked in each.")
        grid = draw.figure(
            '<table class="cm cm-themes"><thead><tr><th>Bundle</th>%s</tr>'
            '</thead><tbody>%s</tbody></table>' % (head, body),
            of(len(resolved), len(audited)), means, kind="matrix")
    else:
        grid = draw.figure(draw.hatch("No themes to check"), kind="hatch")
    coverage = ('<div data-report-region="modes-coverage" data-modes-json="%s">'
                '%s</div>' % (json_attr(matrix), grid))
    gaps = (
        '<div data-report-region="modes-gaps" data-modes-json="%s">'
        '<p class="quiet">%s</p></div>'
        % (json_attr(matrix),
           "We name a missing value only after every theme resolves, so no "
           "gap is claimed here." if len(resolved) < len(audited) or not audited
           else "Every theme resolved. Any gap is listed with its check."))
    return coverage, gaps


def sub_orphans(report):
    measure = ((report.get("vitals") or {}).get("orphans") or {}).get("measure") or {}
    if measure.get("part") is not None and measure.get("whole"):
        return "%s look unused" % of(measure["part"], measure["whole"],
                                     measure.get("noun"))
    return "Tokens nothing uses, and what stops them coming back"


def render_orphans_and_enforcement(report):
    root = root_of(report)
    vitals = report.get("vitals") or {}
    orphans = vitals.get("orphans") or {}
    enforcement = vitals.get("enforcement") or {}
    candidates = orphans.get("candidates") or []
    listing = ""
    if candidates:
        listing = (
            '<details><summary>The %s</summary><div class="details-body">'
            '<div class="tbl-scroll"><table><thead><tr><th>Token</th>'
            '<th>Family</th><th>Declared at</th></tr></thead><tbody>%s</tbody>'
            '</table></div></div></details>'
            % (esc(plural(len(candidates), "token")), "".join(
                '<tr><td><code>%s</code></td><td>%s</td><td><span class="path">'
                '%s</span></td></tr>'
                % (esc(item.get("token")), esc(item.get("family") or "—"),
                   esc(plain(item.get("site") or "", root)))
                for item in candidates)))
    orphan_html = (
        '<div class="panel" data-report-region="orphans" data-vital-json="%s">'
        '<h3>Tokens nothing uses</h3>%s<p class="vital-note">%s</p>%s</div>'
        % (json_attr(orphans),
           render_measure(report, orphans, orphans.get("grade", "not-visible")),
           esc(plain(orphans.get("note") or "We recorded nothing here.", root)),
           listing))
    enforcement_html = (
        '<div class="panel" id="enforcement" data-report-region="enforcement" '
        'data-vital-json="%s"><h3>What stops this coming back</h3>%s'
        '<p class="vital-note">%s</p></div>'
        % (json_attr(enforcement),
           render_measure(report, enforcement,
                          enforcement.get("grade", "not-visible")),
           esc(plain(enforcement.get("note") or "We recorded nothing here.",
                     root))))
    return orphan_html, enforcement_html


# ─── 12 Method ────────────────────────────────────────────────────────────

def render_method(report):
    """How each check is graded. Facts about this run live in About this run."""
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (esc(CHECK_NAME[name]), esc(CHECK_ASKS[name]), esc(CHECK_LINE[name]))
        for name in CHECK_ORDER)
    rendering = report.get("rendering") or {}
    forms = rendering.get("forms") or {}
    drawn = ""
    if forms:
        drawn = ('<p class="quiet">How long lists were drawn: %s.</p>'
                 % esc(", ".join("%s as %s" % (name, form)
                                 for name, form in sorted(forms.items()))))
    return (
        '<div class="method" data-report-region="method">'
        '<div class="tbl-scroll"><table><thead><tr><th>Check</th>'
        '<th>What it asks</th><th>Where the lines are</th></tr></thead>'
        '<tbody>%s</tbody></table></div><p class="mk-means">Each check is '
        'graded alone. There is no overall score, because an average would '
        'hide the one thing you need to see. Blocked is never counted as '
        'zero.</p>%s<p class="quiet">The files we read, what we left out and '
        'the versions used are in %s.</p></div>'
        % (rows, drawn, run_fact("About this run")))


def render_wins(report):
    """What we could verify, each with the measurement that backs it."""
    root = root_of(report)
    confidence = report.get("confidence") or {}
    wins = [dict(win) for win in confidence.get("wins") or []
            if isinstance(win, dict)]
    families = (report.get("token_chains") or {}).get("fully_traceable_families") or []
    if families:
        wins.append({
            "claim": "%s traced end to end" % plural(
                len(families), "token family", "token families"),
            "evidence": [", ".join(families)]})
    if not wins:
        return ('<div data-report-region="wins" data-win-count="0"><p '
                'class="quiet">We recorded nothing as verified for this run.</p>'
                '</div>')
    rows = "".join(
        '<li><strong>%s</strong> <span class="sub">%s</span></li>'
        % (esc(plain(win.get("claim", ""), root)),
           esc(plain(" · ".join(win.get("evidence") or []), root)))
        for win in wins)
    return ('<div data-report-region="wins" data-win-count="%d">'
            '<h3 class="part">What we could verify</h3><ul class="wins">%s</ul>'
            '</div>' % (len(wins), rows))


# ─── 13 Next ──────────────────────────────────────────────────────────────

def sub_next(report):
    stage = report.get("stage") or {}
    ranked = moves.rank(report)
    parts = []
    current = stage.get("current")
    if current in STAGES:
        parts.append("Stage %d of %d" % (STAGES.index(current) + 1, len(STAGES)))
    parts.append("%s ranked" % plural(len(ranked), "move"))
    return " · ".join(parts)


def render_next_steps(report):
    """Every move, in the one order, drawn the same way as the first."""
    ranked = moves.rank(report)
    if ranked:
        body = "".join(render_move(move, report, position=index + 1)
                       for index, move in enumerate(ranked))
        body += ('<p class="mk-means">Confirmed defects come first, then calls '
                 'only you can make, then what we couldn’t see.</p>')
    else:
        body = '<p class="quiet">Nothing is waiting on you.</p>'
    return ('<div class="moves" data-report-region="next-steps" '
            'data-next-steps-json="%s">%s</div>'
            % (json_attr(moves.as_rows(report)), body))


def _prompt_block(summary, prompt, name):
    return ('<details class="cmd" data-agent-prompt="%s"><summary>%s</summary>'
            '<div class="details-body"><div class="cmd-row prompt-row">'
            '<pre data-copy-source>%s</pre><button type="button" class="copy" '
            'data-copy aria-label="Copy the prompt">Copy</button></div></div>'
            '</details>' % (esc(name), esc(summary), esc(prompt)))


def render_agent_prompt(report):
    """Two prompts for an agent, each behind a button, each with copy.

    The first hands over the ranked moves: the one confirmed fix, the
    questions, what to leave alone. The second is the long road to every
    check Healthy. Both are written by `moves` from the same report, so
    neither can say something the page above it does not.
    """
    root = root_of(report)
    first = moves.agent_prompt(report, root)
    road = moves.healthy_prompt(report, root)
    ids = " ".join(move["id"] for move in moves.rank(report))
    if not (first or road):
        return ('<div class="agent-prompt" data-report-region="agent-prompt" '
                'data-agent-prompt-moves=""></div>')
    blocks = ""
    if first:
        blocks += _prompt_block("Show the prompt for the first moves", first, "moves")
    if road:
        blocks += _prompt_block(
            "Show the prompt to get every check to Healthy", road, "healthy")
    return (
        '<div class="agent-prompt" data-report-region="agent-prompt" '
        'data-agent-prompt-moves="%s"><h3 class="part">Hand this to your '
        'design system agent</h3><p class="mk-means">Two briefs. The first is '
        'the moves above: what to fix, what to ask you, what to leave alone. '
        'The second is the longer road: see what we couldn’t, gather what you '
        'need to decide, then move each check to Healthy.</p>%s</div>'
        % (esc(ids), blocks))


def render_stage(report):
    stage = report.get("stage") or {}
    current = stage.get("current") or "unresolved"
    following = stage.get("next")
    threshold = sentence(plain(stage.get("threshold")
                               or "We recorded no next threshold.",
                               root_of(report)))
    line = ("<b>To reach %s</b> %s" % (esc(following), esc(lower_first(threshold)))
            if following else esc(threshold))
    met = stage.get("already_met") or []
    met_html = ""
    if met:
        met_html = ('<details><summary>Already met</summary><div class='
                    '"details-body"><ul>%s</ul></div></details>'
                    % "".join("<li>%s</li>" % words(report, item) for item in met))
    return ('<div class="stage" data-report-region="stage" data-stage-json="%s">'
            '<h3 class="part">Where your system stands</h3>%s'
            '<p class="mk-means">%s</p>%s</div>'
            % (json_attr(stage), draw.ladder(list(STAGES), current), line,
               met_html))
