#!/usr/bin/env python3
"""The report's page as data: what a reader sees first, without the HTML.

`report.json` already holds every measurement. What it did not hold is the
page itself: the one line of facts, About this run, the verdict, the chapters
with the line under each name, and the two short texts an agent reads first.
Those lived only in the rendered HTML, so another page could not draw this
report without running the renderer.

`build` returns that page as one object, kept in `report.json` under `page`.
Nothing in it is computed a second way: the sentence, the states, the
counters and the moves come from the functions the HTML is rendered from,
and the chapter lines and About this run are read back out of the rendered
document. `problems` is the checker; `assets/page.schema.json` is the same
contract for a reader that is not Python.

Usage:
  family.py report.json --html report.html     write `page`, VERDICT.md, ASK.md
  family.py report.json --check                exit 1 and list what is wrong
"""
import argparse
import html as html_tools
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chapters  # noqa: E402
import moves  # noqa: E402
from vocab import (  # noqa: E402
    CHECK_NAME, CHECK_ORDER, GRADE_LABEL, GRADES, breakdown, grade_counts,
    grade_of, plain,
)

SHAPE = 1
STATES = tuple(GRADE_LABEL[grade] for grade in GRADES)
VERDICT_LIMIT = 600
ASK_LIMIT = 900
FIRST_MOVES = 3

# The worst state a strip holds, worst first. Blocked outranks Watch: a check
# we couldn't see is a larger unknown than one that is worth a look.
SEVERITY = ("needs-work", "not-visible", "watch", "healthy", "not-needed")

EXIT_OK, EXIT_PROBLEMS, EXIT_USAGE = 0, 1, 2

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def text_of(fragment):
    """The words in a piece of markup, on one line."""
    fragment = re.sub(r"<!--.*?-->", "", fragment or "", flags=re.S)
    return _SPACE.sub(" ", html_tools.unescape(_TAG.sub(" ", fragment))).strip()


def state_of(grade):
    return GRADE_LABEL.get(grade, GRADE_LABEL["not-visible"])


def strip(report):
    """The eight checks in their fixed order, each with its one state."""
    return [{"key": name, "name": CHECK_NAME[name],
             "grade": grade_of(report, name) if grade_of(report, name) in GRADES
             else "not-visible",
             "state": state_of(grade_of(report, name))}
            for name in CHECK_ORDER]


def counters(report):
    return [{"kind": item["kind"], "label": item["label"],
             "count": item["count"], "unit": item["unit"]}
            for item in moves.counters(report)]


def first_moves(report):
    """The first three of the one ranked list, in the report's words."""
    root = chapters.root_of(report)
    out = []
    for move in moves.rank(report)[:FIRST_MOVES]:
        item = {"kind": move["kind"], "verb": move["verb"],
                "title": plain(move["title"], root)}
        for key in ("action", "where", "command"):
            if move.get(key) and plain(move[key], root) != item["title"]:
                item[key] = plain(move[key], root)
        out.append(item)
    return out


def worst(report):
    counts = grade_counts(report)
    for grade in SEVERITY:
        if counts[grade]:
            return state_of(grade)
    return state_of("healthy")


def chapter_states(report):
    """The state of the chapters that are lists of things waiting. Others have none.

    Fix now, Decide and Unlock are each a queue. An empty queue is Healthy; a
    full one takes the state of what waits in it. The evidence chapters carry
    no state of their own: a grade is stated once, in the verdict.
    """
    waiting = {item["kind"]: item["count"] for item in moves.counters(report)}
    return {
        "verdict": worst(report),
        "fix-now": state_of("needs-work") if waiting["fix"] else state_of("healthy"),
        "decide": state_of("watch") if waiting["decide"] else state_of("healthy"),
        "unlock-chapter": (state_of("not-visible") if waiting["unlock"]
                           else state_of("healthy")),
    }


_CHAPTER = re.compile(
    r'<div class="chapter[^"]*" id="([^"]+)" data-chapter="(\d\d)">\s*'
    r'<header class="chapter-head">(.*?)</header>', re.S)


def read_chapters(document, report):
    """Number, id, name and the one line under the name, as the page shows them."""
    states = chapter_states(report)
    out = []
    for chapter_id, number, head in _CHAPTER.findall(document or ""):
        name = re.search(r"<h2[^>]*>(.*?)</h2>", head, re.S)
        sub = re.search(r'<p class="chapter-sub">(.*?)</p>', head, re.S)
        stat = text_of(sub.group(1)) if sub else ""
        if chapter_id == "verdict":
            stat = breakdown(grade_counts(report))
        out.append({"n": number, "id": chapter_id,
                    "name": text_of(name.group(1)) if name else "",
                    "stat": stat, "state": states.get(chapter_id)})
    return out


_ABOUT = re.compile(r'<details[^>]*\bid="about-run"[^>]*>(.*?)</details>\s*'
                    r'(?:<!-- /SLOT:about-run -->|</header>)', re.S)
_BLOCK = re.compile(r'<div class="about-block[^"]*">\s*<h3>(.*?)</h3>(.*?)'
                    r'(?=<div class="about-block|\Z)', re.S)
_FACT = re.compile(r'<span class="about-n">(.*?)</span>\s*<span class="about-what">'
                   r'(.*?)</span>.*?<span class="about-why">(.*?)</span>', re.S)


def read_about(document):
    """About this run, grouped as the page groups it."""
    match = _ABOUT.search(document or "")
    if not match:
        return []
    groups = []
    for title, body in _BLOCK.findall(match.group(1)):
        body = re.sub(r"<details.*?</details>", "", body, flags=re.S)
        items = [{"label": text_of(what), "value": text_of(number),
                  "note": text_of(why)}
                 for number, what, why in _FACT.findall(body)]
        items += [{"label": text_of(name), "value": text_of(value)}
                  for name, value in re.findall(
                      r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", body, re.S)]
        items += [{"value": text_of(line)}
                  for line in re.findall(r"<li>(.*?)</li>", body, re.S)]
        items += [{"value": text_of(line)}
                  for line in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
        groups.append({"group": text_of(title),
                       "items": [item for item in items if item.get("value")]})
    return groups


def _clip(text, limit):
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + "…"


def verdict_text(report):
    """VERDICT: the page's front in plain text, short enough to read first."""
    lines = [
        "Design Token Vitals: %s" % text_of(chapters.factline(report)),
        "",
        chapters.verdict_sentence(report),
        breakdown(grade_counts(report)) + ".",
        " · ".join("%s %s" % (item["label"], item["count"])
                   for item in moves.counters(report)) + ".",
    ]
    first = first_moves(report)
    if first:
        move = first[0]
        where = " (%s)" % move["where"] if move.get("where") else ""
        lines.append("First move: %s. %s%s" % (
            move["verb"], move.get("action") or move["title"], where))
    return _clip("\n".join(lines), VERDICT_LIMIT)


def ask_text(report):
    """ASK: what would make the next report sharper, as a brief an agent can take.

    It asks for evidence, never for a fix: the three first moves by name, how
    many more wait, and where to start reading. Paths are relative and each
    command is the one the report already offers.
    """
    ranked = moves.rank(report)
    root = chapters.root_of(report)
    if not ranked:
        return ("Nothing is waiting in this report. Run the audit again after "
                "the next change to the tokens, and compare the two runs.\n"
                "Start from VERDICT.md.")
    lines = ["Next: ask the system. Gather this evidence; change no product code."]
    budget = ASK_LIMIT - 120
    for move in ranked[:FIRST_MOVES]:
        if move["kind"] == "fix":
            line = "- Confirm: %s" % plain(move["title"], root)
        elif move["kind"] == "decide":
            line = "- Put to a person: %s" % plain(move["title"], root)
        else:
            line = "- Unblock: %s" % plain(move["title"], root)
        tail = move.get("command") or move.get("where")
        if tail:
            line += "\n    %s" % plain(tail, root)
        if len("\n".join(lines + [line])) > budget:
            line = _clip(line.split("\n")[0], 140)
        lines.append(line)
    rest = len(ranked) - min(len(ranked), FIRST_MOVES)
    if rest:
        lines.append("- %d more in the report, under Fix now, Decide and Unlock."
                     % rest)
    lines.append("Start from VERDICT.md.")
    return _clip("\n".join(lines), ASK_LIMIT)


def build(report, document):
    """The page as data. `document` is the rendered HTML it was read from."""
    return {
        "shape": SHAPE,
        "id": "vitals",
        "title": "Design Token Vitals",
        "factLine": text_of(chapters.factline(report)),
        "about": read_about(document),
        "verdict": {
            "sentence": chapters.verdict_sentence(report),
            "state": worst(report),
            "strip": strip(report),
            "counters": counters(report),
            "firstMoves": first_moves(report),
        },
        "chapters": read_chapters(document, report),
        "verdictText": verdict_text(report),
        "askText": ask_text(report),
    }


def problems(page):
    """What is wrong with a page object, one line each. Empty means sound."""
    bad = []
    if not isinstance(page, dict):
        return ["page is not an object"]
    if page.get("shape") != SHAPE:
        bad.append("shape is %r, not %d" % (page.get("shape"), SHAPE))
    for key in ("id", "title", "factLine", "verdictText", "askText"):
        if not isinstance(page.get(key), str) or not page.get(key).strip():
            bad.append("%s is missing or empty" % key)
    if len(page.get("verdictText") or "") > VERDICT_LIMIT:
        bad.append("verdictText is over %d characters" % VERDICT_LIMIT)
    if len(page.get("askText") or "") > ASK_LIMIT:
        bad.append("askText is over %d characters" % ASK_LIMIT)
    for key in ("verdictText", "askText", "factLine"):
        if re.search(r"(?:/Users/|/home/|[A-Za-z]:\\\\)", str(page.get(key) or "")):
            bad.append("%s holds an absolute path" % key)

    about = page.get("about")
    if not isinstance(about, list) or not about:
        bad.append("about has no groups")
    else:
        for group in about:
            if not isinstance(group, dict) or not group.get("group"):
                bad.append("an about group has no name")
            elif not group.get("items"):
                bad.append("about group %r is empty" % group.get("group"))

    verdict = page.get("verdict")
    if not isinstance(verdict, dict):
        return bad + ["verdict is missing"]
    if not str(verdict.get("sentence") or "").strip():
        bad.append("verdict.sentence is empty")
    if verdict.get("state") not in STATES:
        bad.append("verdict.state %r is not one of the five states"
                   % verdict.get("state"))
    cells = verdict.get("strip") or []
    if [cell.get("key") for cell in cells if isinstance(cell, dict)] != list(CHECK_ORDER):
        bad.append("verdict.strip is not the eight checks in order")
    for cell in cells:
        if isinstance(cell, dict) and cell.get("state") not in STATES:
            bad.append("strip state %r is not one of the five states"
                       % cell.get("state"))
        elif isinstance(cell, dict) and cell.get("state") != state_of(cell.get("grade")):
            bad.append("strip cell %r says %r for the grade %r"
                       % (cell.get("key"), cell.get("state"), cell.get("grade")))
    kinds = [item.get("kind") for item in verdict.get("counters") or []
             if isinstance(item, dict)]
    if kinds != list(moves.KINDS):
        bad.append("verdict.counters are not Fix now, Decide, Unlock in order")
    else:
        by_kind = {item["kind"]: item.get("count") for item in verdict["counters"]}
        for item in verdict["counters"]:
            if not isinstance(item.get("count"), int) or item["count"] < 0:
                bad.append("counter %r has no count" % item.get("kind"))
        fixes = sum(1 for cell in cells if isinstance(cell, dict)
                    and cell.get("grade") == "needs-work")
        blocked = sum(1 for cell in cells if isinstance(cell, dict)
                      and cell.get("grade") == "not-visible")
        if isinstance(by_kind.get("unlock"), int) and by_kind["unlock"] != blocked:
            bad.append("the Unlock counter says %s and the strip has %d blocked"
                       % (by_kind["unlock"], blocked))
        if isinstance(by_kind.get("fix"), int) and by_kind["fix"] > 0 and fixes == 0:
            bad.append("the Fix now counter is %s and no check is graded Fix"
                       % by_kind["fix"])
    first = verdict.get("firstMoves")
    if not isinstance(first, list):
        bad.append("verdict.firstMoves is missing")
    else:
        if len(first) > FIRST_MOVES:
            bad.append("verdict.firstMoves holds %d moves; the most is %d"
                       % (len(first), FIRST_MOVES))
        order = [moves.KINDS.index(move.get("kind")) for move in first
                 if isinstance(move, dict) and move.get("kind") in moves.KINDS]
        if len(order) != len(first):
            bad.append("a first move has no kind")
        elif order != sorted(order):
            bad.append("verdict.firstMoves is not in the order fix, decide, unlock")
        for move in first:
            if isinstance(move, dict) and not str(move.get("title") or "").strip():
                bad.append("a first move has no title")

    listed = page.get("chapters")
    if not isinstance(listed, list) or not listed:
        bad.append("chapters is empty")
    else:
        numbers = [chapter.get("n") for chapter in listed if isinstance(chapter, dict)]
        if numbers != ["%02d" % index for index in range(len(listed))]:
            bad.append("chapters are not numbered 00 upward in order")
        for chapter in listed:
            if not isinstance(chapter, dict):
                continue
            if not chapter.get("id") or not chapter.get("name"):
                bad.append("chapter %s has no id or no name" % chapter.get("n"))
            if not str(chapter.get("stat") or "").strip():
                bad.append("chapter %s has no line under its name" % chapter.get("n"))
            if chapter.get("state") is not None and chapter.get("state") not in STATES:
                bad.append("chapter %s state %r is not one of the five states"
                           % (chapter.get("n"), chapter.get("state")))
    return bad


def attach(report, document):
    """Put the page into the report. Called wherever `report.json` is written."""
    report["page"] = build(report, document)
    return report["page"]


def write_beside(report_path, page):
    """VERDICT.md and ASK.md next to report.json, for a reader with no page."""
    directory = os.path.dirname(os.path.abspath(report_path))
    for name, text in (("VERDICT.md", page["verdictText"]), ("ASK.md", page["askText"])):
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False,
                                         encoding="utf-8") as handle:
            handle.write(text.rstrip("\n") + "\n")
            temporary = handle.name
        os.replace(temporary, os.path.join(directory, name))


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("report_json")
    parser.add_argument("--html", help="the rendered report to read the page from")
    parser.add_argument("--check", action="store_true",
                        help="check the page already in report.json; write nothing")
    args = parser.parse_args(argv)
    with open(args.report_json, encoding="utf-8") as handle:
        report = json.load(handle)
    if args.check:
        found = problems(report.get("page"))
        for line in found:
            print(line)
        if not found:
            print("page: sound (%d chapters)" % len(report["page"]["chapters"]))
        return EXIT_PROBLEMS if found else EXIT_OK
    if not args.html:
        print("give --html <report.html> to build the page, or --check")
        return EXIT_USAGE
    with open(args.html, encoding="utf-8") as handle:
        page = attach(report, handle.read())
    found = problems(page)
    for line in found:
        print(line)
    if found:
        return EXIT_PROBLEMS
    directory = os.path.dirname(os.path.abspath(args.report_json))
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False,
                                     encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=False)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, args.report_json)
    write_beside(args.report_json, page)
    print("wrote page, VERDICT.md and ASK.md beside %s" % args.report_json)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
