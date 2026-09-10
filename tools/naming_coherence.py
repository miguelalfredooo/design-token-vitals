#!/usr/bin/env python3
"""Measure how many naming grammars live inside one token system.

`references/vitals.md` grades `naming-coherence` on the count of distinct
naming grammars: pass at one, attention at two, fail at three or more.
Until this tool existed that count was a judgment call, which principle 7
says is a rule that drifts. This is the count, with a `file:line` per
grammar so the grade can be checked.

A grammar here is the pair of axes a machine can read without an opinion:
the separator between segments and the case of them. `--btn-pad-x` and
`--btnPadX` are two grammars. `--btn-pad-x` and `--button-padding-inline`
are one grammar spelled two ways, which is a different finding and is
reported separately as a spelling pair rather than folded into the count.

The tool never says which grammar is correct. Where the project declares
one — a stylelint `custom-property-pattern`, a scss dollar pattern — it is
read and conformance is reported against it. Where it does not, the
dominant grammar is reported as inferred and nothing is graded against it.

    python3 tools/naming_coherence.py <root> --tokens .token-vitals/tokens.json
    python3 tools/naming_coherence.py <root> --tokens tokens.json --json out.json
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cli
import discover_tokens

# The source roles whose names are the system's own. A consumer override
# spells a token to match whatever it is overriding, so its grammar is
# evidence about that other system and not about this one.
CANONICAL_ROLES = ("canonical", "alias")

# A JS identifier cannot be spelled with a hyphen and a CSS custom
# property is rarely spelled with a capital, so a system that writes
# kebab in CSS and camel in a theme object has one convention expressed
# in two languages. Counting those as two grammars grades the language.
# Grammars are counted inside a syntax, and the grade reads the syntax
# that holds the most.
SYNTAX_OF = {
    "css-custom-property": "css",
    "scss-variable": "scss",
    "scss-map-entry": "scss",
    "js-theme-object": "js",
    "conservative-js-theme-object": "js",
    "dtcg-json": "json",
    "style-dictionary-json": "json",
}


# One word written two ways inside one system. Both forms must appear as
# whole segments before a pair is reported, so a system that consistently
# says `btn` everywhere is never told it has a problem.
SPELLING_PAIRS = {
    "btn": "button", "bg": "background", "fg": "foreground",
    "pad": "padding", "mrg": "margin", "clr": "color", "col": "column",
    "txt": "text", "sz": "size", "wt": "weight", "img": "image",
    "ico": "icon", "hdr": "header", "ftr": "footer", "brd": "border",
    "rad": "radius", "elev": "elevation", "anim": "animation",
    "dur": "duration", "opac": "opacity", "spc": "spacing",
}
# The same axis named physically and logically. This is the pair the
# vitals reference uses as its worked example.
AXIS_PAIRS = {"x": "inline", "y": "block"}

# Where a stylelint configuration states a name pattern, that is the
# project declaring its grammar rather than the run guessing at one.
STYLELINT_FILES = (
    ".stylelintrc", ".stylelintrc.json", ".stylelintrc.js",
    ".stylelintrc.cjs", ".stylelintrc.yml", ".stylelintrc.yaml",
    "stylelint.config.js", "stylelint.config.cjs", "stylelint.config.mjs",
)
PATTERN_RULES = ("custom-property-pattern", "scss/dollar-variable-pattern")

CAMEL = re.compile(r"[a-z0-9][A-Z]")


def leaf(name):
    """The token's own name, with any nesting path removed.

    Discovery reports a JS theme object, a DTCG file and an scss map as a
    dotted path — `tokens.colorAccent`, `color.primitive.blue.500`. The
    dots are the structure the value sits in, and the last part is what
    the token is called. A CSS custom property cannot hold a dot at all,
    so nothing here loses a real separator.

    Reading the path as a grammar is what made a real repository grade
    `fail` on two JS object keys while its 365 custom properties agreed
    with each other.
    """
    return name.lstrip("-$@").rsplit(".", 1)[-1]


def segments(name):
    """The name's parts, however it happens to spell the boundaries."""
    name = leaf(name)
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name)
    return [part for part in re.split(r"[-_.\s]+", name) if part]


def separator_of(name):
    """kebab, snake, camel, or unsegmented.

    Unsegmented earns no grammar. A one-word name carries no evidence
    about how this system spells a boundary, and counting it as its own
    grammar would fail every system that owns a `--brand` token.
    """
    body = leaf(name)
    if "-" in body:
        return "kebab"
    if "_" in body:
        return "snake"
    if CAMEL.search(body):
        return "camel"
    return "unsegmented"


def case_of(name):
    body = leaf(name)
    letters = [character for character in body if character.isalpha()]
    if not letters:
        return "caseless"
    if all(character.islower() for character in letters):
        return "lower"
    if all(character.isupper() for character in letters):
        return "upper"
    return "mixed"


def grammar_of(name):
    separator = separator_of(name)
    if separator == "unsegmented":
        return None
    return "%s-%s" % (separator, case_of(name))


def family_position(name):
    """Whether the family word leads the name, trails it, or is absent.

    Reported, never graded. Which end a system puts its family word on is
    a decision the system is entitled to make either way; a system that
    makes it both ways is the finding, and that is for a reader to weigh.
    """
    parts = [part.lower() for part in segments(name)]
    if not parts:
        return "absent"
    signals = set()
    for words in discover_tokens.FAMILY_NAMES.values():
        signals.update(words)
    signals.update(discover_tokens.COLOR_NAMES)
    hits = [index for index, part in enumerate(parts) if part in signals]
    if not hits:
        return "absent"
    if hits[0] == 0:
        return "leading"
    if hits[-1] == len(parts) - 1:
        return "trailing"
    return "internal"


def read_sources(root, tokens):
    """(names, unmeasured) — every declared name in a canonical source.

    `tokens.json` normalizes a name to compare concepts, which is right
    for every other measurement and wrong for this one: normalizing is
    what erases the spelling this vital is about. The raw declaration is
    re-read here through the same parser discovery used.
    """
    names, unmeasured = [], []
    for source in tokens.get("sources", []):
        if source.get("role") not in CANONICAL_ROLES:
            continue
        path = source.get("path", "")
        absolute = path if os.path.isabs(path) else os.path.join(root, path)
        try:
            with open(absolute, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as error:
            unmeasured.append({"path": path, "note": str(error)})
            continue
        for name, _value, _representation, offset in discover_tokens.declarations(text, path):
            names.append({
                "name": name,
                "syntax": SYNTAX_OF.get(_representation, _representation),
                "site": "%s:%d" % (path, discover_tokens.line_for(text, offset)),
            })
    return names, unmeasured


def declared_pattern(root):
    """The grammar the project states for itself, where it states one."""
    candidates = [(os.path.join(root, name), name) for name in STYLELINT_FILES]
    candidates.append((os.path.join(root, "package.json"), "package.json"))
    for absolute, relative in candidates:
        if not os.path.isfile(absolute):
            continue
        try:
            with open(absolute, encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            continue
        for rule in PATTERN_RULES:
            found = re.search(
                r'["\']%s["\']\s*:\s*\[?\s*["\'](.+?)["\']' % re.escape(rule),
                text,
            )
            if found:
                line = text.count("\n", 0, found.start()) + 1
                return {
                    "state": "declared", "rule": rule,
                    "pattern": found.group(1),
                    "site": "%s:%d" % (relative, line),
                }
    return None


def spelling_findings(names):
    """Pairs where one system says the same word two ways."""
    seen = {}
    for entry in names:
        for part in segments(entry["name"]):
            seen.setdefault(part.lower(), []).append(entry["site"])
    findings = []
    for kind, table in (("abbreviation", SPELLING_PAIRS), ("axis", AXIS_PAIRS)):
        for short, long in sorted(table.items()):
            if short in seen and long in seen:
                findings.append({
                    "kind": kind, "short": short, "long": long,
                    "short_evidence": sorted(set(seen[short]))[:3],
                    "long_evidence": sorted(set(seen[long]))[:3],
                })
    return findings


def measure(root, tokens):
    names, unmeasured = read_sources(root, tokens)
    grammars, unsegmented = {}, []
    for entry in names:
        grammar = grammar_of(entry["name"])
        if grammar is None:
            unsegmented.append(entry["site"])
            continue
        key = (entry["syntax"], grammar)
        record = grammars.setdefault(key, {
            "id": grammar, "syntax": entry["syntax"], "count": 0,
            "evidence": [], "examples": []})
        record["count"] += 1
        if len(record["evidence"]) < 3:
            record["evidence"].append(entry["site"])
            record["examples"].append(entry["name"])
    ordered = sorted(grammars.values(), key=lambda item: (-item["count"], item["id"]))
    for record in ordered:
        record["separator"], _, record["case"] = record["id"].partition("-")

    # The grade reads the syntax that holds the most grammars. A reader
    # learning this system learns one spelling per language; two
    # spellings inside one language is what makes a name unguessable.
    per_syntax = {}
    for record in ordered:
        per_syntax.setdefault(record["syntax"], []).append(record["id"])

    positions = {"leading": 0, "trailing": 0, "internal": 0, "absent": 0}
    for entry in names:
        positions[family_position(entry["name"])] += 1

    count = max((len(ids) for ids in per_syntax.values()), default=0)
    if not names or (count == 0 and unmeasured):
        grade, note = "blocked", (
            "No canonical source could be read, so no name was seen."
            if unmeasured else
            "No declared token name was found in a canonical source.")
    elif count == 0:
        grade, note = "blocked", (
            "Every name found is a single word, which carries no evidence "
            "about how this system spells a segment boundary.")
    elif count == 1:
        grade, note = "pass", "One grammar across every name."
    elif count == 2:
        grade, note = "attention", (
            "Two grammars. A reader can hold two patterns in their head, "
            "and the smaller one names where to start.")
    else:
        grade, note = "fail", (
            "%d grammars. Knowing one token's name tells you nothing "
            "about how to guess another's." % count)

    declared = declared_pattern(root) or {"state": "inferred"}
    if declared["state"] == "inferred" and ordered:
        declared["pattern"] = ordered[0]["id"]
        declared["note"] = (
            "The project states no name pattern, so the most common "
            "grammar is reported as its convention and nothing is graded "
            "against it.")
    conformance = None
    if declared["state"] == "declared":
        expression = re.compile(declared["pattern"])
        outside = [entry for entry in names
                   if not expression.search(leaf(entry["name"]))]
        conformance = {
            "pattern": declared["pattern"], "site": declared["site"],
            "checked": len(names), "outside": len(outside),
            "evidence": [entry["site"] for entry in outside[:5]],
            "examples": [entry["name"] for entry in outside[:5]],
        }

    return {
        "vital": "naming-coherence",
        "grade": grade,
        "note": note,
        "names_seen": len(names),
        "grammar_count": count,
        "grammars_per_syntax": {syntax: sorted(ids)
                                for syntax, ids in sorted(per_syntax.items())},
        "grammars": ordered,
        "unsegmented": {"count": len(unsegmented),
                        "evidence": sorted(set(unsegmented))[:3]},
        "spelling_pairs": spelling_findings(names),
        "family_position": positions,
        "declared": declared,
        "conformance": conformance,
        "unmeasured": unmeasured,
    }


def summarize(result):
    lines = ["naming-coherence: %s — %s" % (result["grade"], result["note"])]
    for record in result["grammars"]:
        lines.append("  %-5s %-14s %4d  %s  %s" % (
            record["syntax"], record["id"], record["count"],
            record["examples"][0], record["evidence"][0]))
    for pair in result["spelling_pairs"]:
        lines.append("  same word two ways: %s and %s  %s / %s" % (
            pair["short"], pair["long"],
            pair["short_evidence"][0], pair["long_evidence"][0]))
    if result["conformance"] and result["conformance"]["outside"]:
        conformance = result["conformance"]
        lines.append("  %d of %d names sit outside the declared pattern %s (%s)" % (
            conformance["outside"], conformance["checked"],
            conformance["pattern"], conformance["site"]))
    for entry in result["unmeasured"]:
        lines.append("  unmeasured: %s — %s" % (entry["path"], entry["note"]))
    return "\n".join(lines)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root")
    parser.add_argument("--tokens", required=True,
                        help="the JSON written by tools/discover_tokens.py")
    cli.add_json_flag(parser)
    args = parser.parse_args(argv)

    try:
        with open(args.tokens, encoding="utf-8") as handle:
            tokens = json.load(handle)
    except (OSError, ValueError) as error:
        print("cannot read %s: %s" % (args.tokens, error), file=sys.stderr)
        return cli.EXIT_REFUSED

    result = measure(args.root, tokens)
    print(summarize(result))
    cli.emit_json(args.json_out, result)
    return cli.EXIT_OK if result["grade"] == "pass" else cli.EXIT_FINDING


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
