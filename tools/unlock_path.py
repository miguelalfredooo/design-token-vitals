#!/usr/bin/env python3
"""Separate "your system has a problem" from "this audit cannot see yet".

    python3 tools/unlock_path.py .token-vitals/report.json \
        --discovery .token-vitals/discovery.json --json .token-vitals/unlock.json

`not-visible` carries two unrelated meanings in one word, and the report used
it for both. A codebase whose token layer is in good shape but whose modes
live in a build step reads as mostly blocked — which is not what it means,
and is the difference between a reader fixing something and a reader
closing the tab. Every vital gets a confidence state that says which of the
two it is, the capability gaps are ordered by how many vitals each one
unlocks, and a declared boundary is counted as a decision rather than
as a hole.

Nothing here re-grades a vital. It reads the grades a run produced and the
capability ladder that run recorded, and says what they mean together.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_OK, add_json_flag, emit_json  # noqa: E402
from vocab import (  # noqa: E402
    GRADE_LABEL, breakdown, fmt, grade_counts, measured, plural,
)

VITALS = (
    "tier-integrity", "leakage", "coverage", "mode-completeness",
    "naming-coherence", "single-source", "orphans", "enforcement",
)

# There is ONE vocabulary, and it is the rating a vital already carries.
# A separate set of "confidence states" sat beside these saying the same
# thing in different words, so a reader had to learn both and the mapping
# between them. The rating now says whose problem it is on its own:
# `needs-work` and `watch` are yours, `not-visible` is the audit's, and
# `not-needed` is a decision somebody made.
RATINGS = ("healthy", "watch", "needs-work", "not-visible", "not-needed")

# Kept as an alias so an older caller does not break on the rename.
CONFIDENCE_STATES = RATINGS
assert set(RATINGS) == set(GRADE_LABEL), "the ratings and their labels drifted"

# What each vital needs the run to have been able to SEE. This is not the
# vital's subject matter — it is the capability whose absence stops the
# check running at all, which is the only thing that turns a grade into an
# audit gap rather than a system one.
VITAL_CAPABILITIES = {
    "tier-integrity": ("token_source_discovery",),
    "leakage": ("import_resolution", "token_source_discovery"),
    # `framework_versions` is not a capability the engine lacks — it is an
    # input the operator did not supply, and `coverage` cannot be graded
    # without it when an adapter draws a category from a framework default.
    # Named here so a blocked coverage has an action instead of a shrug.
    "coverage": ("token_source_discovery", "framework_versions"),
    "mode-completeness": ("mode_resolution",),
    "naming-coherence": ("token_source_discovery",),
    "single-source": ("token_source_discovery", "import_resolution"),
    "orphans": ("import_resolution", "ownership"),
    "enforcement": ("detection",),
}

# One action per capability, in the imperative, with the command that shows
# whether it worked. A step a reader cannot verify is a suggestion.
CAPABILITY_ACTIONS = {
    "detection": (
        "Name the framework you build with, or pass --profile so we stop guessing",
        "python3 tools/discover_environment.py <root> --json .token-vitals/discovery.json",
    ),
    "production_roots": (
        "Point us at the entry your product loads, with --app or an explicit root",
        "python3 tools/discover_environment.py <root> --app <workspace-app> "
        "--json .token-vitals/discovery.json",
    ),
    "import_resolution": (
        "Resolve the imports we couldn't follow: an alias your config "
        "declares, or a path we couldn't reach",
        "python3 tools/import_graph.py <root> --json .token-vitals/graph.json",
    ),
    "token_source_discovery": (
        "Confirm a token file we can reach, or name one with --source",
        "python3 tools/discover_tokens.py <root> --discovery "
        ".token-vitals/discovery.json --json .token-vitals/tokens.json",
    ),
    "ownership": (
        "Say which paths your team owns with --owned, so we grade your code "
        "and not a dependency's",
        "python3 tools/discover_environment.py <root> --owned '<glob>' "
        "--json .token-vitals/discovery.json",
    ),
    "framework_versions": (
        "Record the installed version of each framework whose defaults we read",
        "python3 -c \"import json;print(json.load(open('package.json'))"
        "['devDependencies'])\"",
    ),
    "mode_resolution": (
        "Give us the resolved output for each theme: the built CSS, or the "
        "step that makes it",
        "python3 tools/discover_environment.py <root> --json .token-vitals/discovery.json",
    ),
    "runtime_verification": (
        "Give us a build to read, so we can check computed values instead of "
        "inferring them",
        "python3 tools/discover_environment.py <root> --json .token-vitals/discovery.json",
    ),
}

# The end of the sentence "blocked until ...", for each capability.
CAPABILITY_UNTIL = {
    "detection": "the framework is named",
    "production_roots": "the product entry is named",
    "import_resolution": "imports resolve",
    "token_source_discovery": "token files are found",
    "ownership": "ownership is stated",
    "framework_versions": "framework versions are recorded",
    "mode_resolution": "themes resolve",
    "runtime_verification": "a build is read",
}

# What each capability is called when a person reads it. The snake_case key
# is the machine's name for it and was being printed straight at the reader,
# which made a coaching line read like a stack trace.
CAPABILITY_LABELS = {
    "detection": "knowing which framework this is",
    "production_roots": "knowing what actually ships",
    "import_resolution": "following your imports",
    "token_source_discovery": "finding your token files",
    "ownership": "knowing which code is yours",
    "mode_resolution": "seeing your themes resolve",
    "runtime_verification": "reading computed values from a build",
    "framework_versions": "knowing your framework versions",
}


def label_for(capability):
    return CAPABILITY_LABELS.get(capability, capability.replace("_", " "))


# A win is a claim about the reader's codebase, so it ships only when the
# run can put a measurement next to it. The previous set were generic
# sentences fired by a capability flag alone — "Framework detected — the
# adapters that ran are the right ones" is an interpretation detection
# cannot support, and a congratulation nobody can check is worse than
# silence. Each entry now says what to claim and where the number comes
# from; a capability whose number is missing produces no win at all.
WIN_CLAIMS = {
    "detection": "Framework detected",
    "production_roots": "Production roots verified",
    "import_resolution": "Import graph verified",
    "token_source_discovery": "Token sources verified",
    "ownership": "Ownership established",
    "mode_resolution": "Modes resolve",
    "runtime_verification": "Runtime values read from a build",
}


def ladder_evidence(capability, discovery):
    """Whatever the run itself recorded against this capability step."""
    for step in ((discovery or {}).get("capability_ladder") or {}).get("steps", []):
        if step.get("capability") == capability:
            found = step.get("evidence") or []
            if found:
                return ["%s: %s" % (plural(len(found), "source"),
                                    ", ".join(str(item) for item in found[:4]))]
    return []


def win_evidence(capability, discovery):
    """The measurement behind a win, or nothing — never a stand-in."""
    discovery = discovery or {}
    graph = discovery.get("import_graph") or {}
    if capability == "detection":
        found = discovery.get("environment") or []
        if not found:
            return []
        # `detected_by` is the file that actually proved it. Saying "from
        # this repository's own config" without naming the file described
        # the method rather than showing the evidence.
        proof = discovery.get("detected_by")
        if isinstance(proof, (list, tuple)):
            proof = ", ".join(str(item) for item in proof)
        return ["%s%s" % (", ".join(found),
                          ", from %s" % proof if proof else "")]
    if capability == "production_roots":
        roots = discovery.get("roots") or []
        return ["%s: %s" % (plural(len(roots), "root"), ", ".join(
            str(item.get("path")) for item in roots[:4]))] if roots else []
    if capability == "import_resolution":
        unresolved = graph.get("unresolved") or []
        reachable = graph.get("reachable") or {}
        if not reachable:
            return []
        stuck = [item for item in unresolved
                 if item.get("reason") == "missing local source"]
        return ["%s reached; %s classified, %s of them a missing local file"
                % (plural(len(reachable), "file"),
                   plural(len(unresolved), "import"), fmt(len(stuck)))]
    if capability == "token_source_discovery":
        sources = discovery.get("token_sources") or []
        if sources:
            return [plural(len(sources), "confirmed source")]
        # Token discovery records its evidence on the ladder step rather
        # than under a key of its own. Looking in one place suppressed a win
        # the run had fully established — a false zero of exactly the kind
        # this tool exists to stop.
        return ladder_evidence(capability, discovery)
    if capability == "ownership":
        patterns = ((discovery.get("ownership") or {}).get("owned_patterns")
                    or (discovery.get("ownership") or {}).get(
                        "inferred_owned_patterns") or [])
        return ["scoped to %s" % ", ".join(patterns)] if patterns else []
    if capability == "mode_resolution":
        modes = discovery.get("resolved_modes") or []
        return ["%s resolve with real output" % ", ".join(modes)] if modes else []
    if capability == "runtime_verification":
        artifact = discovery.get("runtime_artifact")
        return ["read from %s" % artifact] if artifact else []
    return []

def until(steps):
    """`imports resolve`: what the first unlock step is waiting for."""
    if not steps:
        return ""
    return CAPABILITY_UNTIL.get(steps[0].get("capability"), "")


def headline(counts, steps=()):
    """One line before any grid: how many checks we measured, how many we couldn't see.

    Blocked means we couldn't see it. It never means the code is wrong, so
    the line counts the two apart and never adds them.
    """
    total = sum(counts.values())
    seen = measured(counts)
    blocked = counts["not-visible"]
    if not blocked and seen and seen == counts["healthy"]:
        return "All %s are healthy" % plural(seen, "check")
    line = "%s of %s measured" % (fmt(seen), plural(total, "check"))
    if blocked:
        waiting = until(steps)
        line += " · %s blocked%s" % (
            fmt(blocked), " until %s" % waiting if waiting else "")
    if counts["not-needed"]:
        line += " · %s not needed" % fmt(counts["not-needed"])
    return line


def ladder_order(capabilities):
    """Capability order as the run recorded it, falling back to the map."""
    return list(capabilities) or list(CAPABILITY_ACTIONS)


def substitute_root(command, discovery=None):
    """A verify command with `<root>` left in it is not a command.

    The root is written as `.`: the reader runs it from the top of their own
    repository. An absolute path would name the machine the audit ran on,
    which is no use on anybody else's and says more than a report should.
    """
    return command.replace("<root>", ".") if command else command


def build(report, capabilities, ladder=None, discovery=None):
    grades = {name: (report.get("vitals", {}).get(name) or {}).get("grade")
              for name in VITALS}
    order = ladder or ladder_order(capabilities)

    confidence = {}
    for name in VITALS:
        grade = grades.get(name)
        # The rating IS the state. Anything unrecognized reads as something
        # the run could not see, which is the conservative direction.
        state = grade if grade in RATINGS else "not-visible"
        missing = [capability
                   for capability in VITAL_CAPABILITIES.get(name, ())
                   if capabilities.get(capability) != "verified"]
        entry = {"grade": grade, "state": state, "blocked_by": []}
        if state == "not-visible":
            entry["blocked_by"] = missing
            entry["reason"] = (
                "We couldn't see this. It is waiting on %s."
                % " and ".join(label_for(item) for item in missing) if missing else
                "We couldn't see this, and nothing says why. That is a gap in "
                "this tool, not in your code.")
        elif state in ("needs-work", "watch"):
            # States the grade back, and nothing more. Calling a finding
            # "real" was this tool editorializing about a judgment somebody
            # else made.
            entry["reason"] = "Checked. We found something in your code."
        elif state == "healthy":
            # Not "checked against evidence": a clean check is allowed to
            # carry an empty evidence list, so that phrasing could be false.
            entry["reason"] = "Checked, and nothing to fix."
        else:
            # `not-needed` is the one grade that removes a vital from the
            # report without anybody fixing anything, so it is the one grade
            # that owes a reason. An unexplained N/A is how a check gets
            # switched off quietly and stays off.
            vital = report.get("vitals", {}).get(name) or {}
            entry["rationale"] = vital.get("rationale") or vital.get("note")
            entry["reason"] = (
                # Quote the reason somebody recorded rather than
                # characterizing it. Whether a boundary is healthy is their
                # call, and this tool has not measured it.
                "Marked not needed here: %s" % entry["rationale"]
                if entry["rationale"] else
                "Marked not needed here, with no reason on record.")
        confidence[name] = entry

    decisions_owed = sorted(
        name for name, entry in confidence.items()
        if entry["state"] == "not-needed" and not entry.get("rationale"))

    # ONE breakdown, and it sums to the number of checks. The four-way split
    # this used to return put Watch and Fix in one bucket called "to fix in
    # your code", so the page showed `2 · 3 · 3` here and `2 · 2 · 1 · 3` two
    # sections later and a reader could not make them agree.
    split = grade_counts(report)

    waiting = {}
    for name, entry in confidence.items():
        for capability in entry["blocked_by"]:
            waiting.setdefault(capability, []).append(name)
    steps = []
    for capability, unlocked in waiting.items():
        action, verify = CAPABILITY_ACTIONS.get(
            capability, ("Establish %s" % capability, ""))
        steps.append({
            "capability": capability,
            "label": label_for(capability),
            "action": action,
            "verify": substitute_root(verify, discovery),
            "unlocks": sorted(unlocked),
            "unlocks_count": len(unlocked),
        })
    # Most unlocked first; the run's own ladder order breaks every tie, so
    # two runs of the same repository produce the same path.
    steps.sort(key=lambda item: (-item["unlocks_count"],
                                 order.index(item["capability"])
                                 if item["capability"] in order else len(order)))

    wins = []
    for capability in order:
        if (capabilities.get(capability) != "verified" or
                capability not in WIN_CLAIMS):
            continue
        evidence = win_evidence(capability, discovery)
        if not evidence:
            continue
        wins.append({"claim": WIN_CLAIMS[capability], "evidence": evidence})
    wins.extend(
        {"claim": "%s: not needed here" % name,
         "evidence": [entry["rationale"]]}
        for name, entry in sorted(confidence.items())
        if entry["state"] == "not-needed" and entry.get("rationale"))

    return {
        "headline": headline(split, steps),
        "confidence": confidence,
        "decisions_owed": decisions_owed,
        "split": split,
        "unlock_path": steps,
        "wins": wins,
    }


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("report")
    parser.add_argument("--discovery", required=True)
    add_json_flag(parser)
    args = parser.parse_args(argv)
    with open(args.report, encoding="utf-8") as handle:
        report = json.load(handle)
    with open(args.discovery, encoding="utf-8") as handle:
        discovery = json.load(handle)
    capabilities = dict(discovery.get("capabilities", {}))
    # Run inputs sit beside engine capabilities: both are things the run
    # needed and either had or did not, and a reader wants one list.
    capabilities.setdefault(
        "framework_versions",
        "verified" if (report.get("run") or {}).get("framework_versions")
        else "not-visible")
    ladder = [step.get("capability")
              for step in discovery.get("capability_ladder", {}).get("steps", [])]
    if ladder and "framework_versions" not in ladder:
        ladder.append("framework_versions")
    result = build(report, capabilities, ladder or None, discovery)
    emit_json(args.json_out, result)
    print(breakdown(result["split"], zeros=True))
    for step in result["unlock_path"]:
        print("  unlock %-36s -> %s: %s"
              % (label_for(step["capability"]),
                 plural(step["unlocks_count"], "more check"),
                 ", ".join(step["unlocks"])))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
