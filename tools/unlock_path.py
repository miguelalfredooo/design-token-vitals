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
        "Name the framework this repository builds with, or pass --profile "
        "so discovery stops guessing",
        "python3 tools/discover_environment.py <root> --json .token-vitals/discovery.json",
    ),
    "production_roots": (
        "Point the run at the entry the product actually loads, with --app "
        "or an explicit root",
        "python3 tools/discover_environment.py <root> --app <workspace-app> "
        "--json .token-vitals/discovery.json",
    ),
    "import_resolution": (
        "Resolve the imports the graph could not follow — an alias the "
        "config declares, or a path the walk cannot reach",
        "python3 tools/import_graph.py <root> --json .token-vitals/graph.json",
    ),
    "token_source_discovery": (
        "Confirm a reachable token source, or name one with --source",
        "python3 tools/discover_tokens.py <root> --discovery "
        ".token-vitals/discovery.json --json .token-vitals/tokens.json",
    ),
    "ownership": (
        "State which paths this team owns with --owned, so the run grades "
        "your code and not a dependency's",
        "python3 tools/discover_environment.py <root> --owned '<glob>' "
        "--json .token-vitals/discovery.json",
    ),
    "framework_versions": (
        "Record the installed version of every framework whose default theme "
        "an adapter reads a category from",
        "python3 -c \"import json;print(json.load(open('package.json'))"
        "['devDependencies'])\"",
    ),
    "mode_resolution": (
        "Give the run a resolved output per mode — the built CSS for each "
        "theme, or the mechanism that produces it",
        "python3 tools/discover_environment.py <root> --json .token-vitals/discovery.json",
    ),
    "runtime_verification": (
        "Give the run a built artifact to read, so computed values can be "
        "checked rather than inferred",
        "python3 tools/discover_environment.py <root> --json .token-vitals/discovery.json",
    ),
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
                return ["%d source(s): %s"
                        % (len(found), ", ".join(str(item) for item in found[:4]))]
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
        return ["%d root(s): %s" % (len(roots), ", ".join(
            str(item.get("path")) for item in roots[:4]))] if roots else []
    if capability == "import_resolution":
        unresolved = graph.get("unresolved") or []
        reachable = graph.get("reachable") or {}
        if not reachable:
            return []
        stuck = [item for item in unresolved
                 if item.get("reason") == "missing local source"]
        return ["%d file(s) reached; %d import(s) classified, %d unresolved "
                "as a missing local file"
                % (len(reachable), len(unresolved), len(stuck))]
    if capability == "token_source_discovery":
        sources = discovery.get("token_sources") or []
        if sources:
            return ["%d confirmed source(s)" % len(sources)]
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

def headline(split):
    """One sentence, before any grid.

    The first thing a reader sees decides what they think the report is
    about. A grid of eight grades reads as a scorecard; a sentence that
    separates what is proven from what the audit cannot yet see reads as a
    status, which is what it is.
    """
    total = len(VITALS)
    healthy = split["healthy"]
    if healthy + split["not_needed"] == total and not split["your_code"]:
        return ("Everything that applies here is healthy — all %d checks "
                "passed." % total)
    parts = ["%d of %d checks look healthy" % (healthy, total)]
    if split["not_visible"]:
        parts.append("%d the audit cannot see yet — that is a limit of this "
                     "run, not of your code" % split["not_visible"])
    if split["your_code"]:
        parts.append("%d with something to fix in your code"
                     % split["your_code"])
    if split["not_needed"]:
        parts.append("%d you have decided you do not need"
                     % split["not_needed"])
    return "; ".join(parts) + "."


def ladder_order(capabilities):
    """Capability order as the run recorded it, falling back to the map."""
    return list(capabilities) or list(CAPABILITY_ACTIONS)


def substitute_root(command, discovery):
    """A verify command with `<root>` left in it is not a command.

    The card tells a reader to run something and check the result. Handing
    them a template makes that step unrunnable, which quietly turns a
    verification into a suggestion.
    """
    root = ((discovery or {}).get("repository") or {}).get("root")
    return command.replace("<root>", root) if root and command else command


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
                "Waiting on %s — the run could not see enough to check this."
                % ", ".join(label_for(item) for item in missing) if missing else
                "The check could not run, and nothing explains why. That is "
                "a gap in this tool, not in your code.")
        elif state in ("needs-work", "watch"):
            # States the grade back, and nothing more. Calling a finding
            # "real" was this tool editorializing about a judgment somebody
            # else made.
            entry["reason"] = "Checked. This one has findings in your code."
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

    # Never summed. `your_code` is work on the design system, `not_visible`
    # is work on the audit, and a reader who cannot tell them apart learns
    # the wrong thing about their own codebase. The keys say which is which
    # without anybody having to look up what a "gap" was.
    split = {
        "healthy": sum(1 for item in confidence.values()
                       if item["state"] == "healthy"),
        "your_code": sum(1 for item in confidence.values()
                         if item["state"] in ("needs-work", "watch")),
        "not_visible": sum(1 for item in confidence.values()
                           if item["state"] == "not-visible"),
        "not_needed": sum(1 for item in confidence.values()
                          if item["state"] == "not-needed"),
    }

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

    card = None
    if steps:
        first = steps[0]
        card = {
            "action": first["action"],
            "payoff": ("Unlocks %d more check(s): %s"
                       % (first["unlocks_count"], ", ".join(first["unlocks"]))),
            "verify": first["verify"],
            "kind": "not-visible",
        }
    else:
        worst = next((name for name in VITALS
                      if confidence[name]["grade"] == "needs-work"), None)
        worst = worst or next((name for name in VITALS
                               if confidence[name]["grade"] == "watch"), None)
        if worst:
            card = {
                "action": "Take the top-ranked %s finding from the fix queue"
                          % worst,
                "payoff": "Moves %s to healthy with one bounded change"
                          % worst,
                "verify": "python3 tools/validate_run.py .token-vitals/report.json",
                "kind": "system-work",
            }
    return {
        "headline": headline(split),
        "confidence": confidence,
        "decisions_owed": decisions_owed,
        "split": split,
        "unlock_path": steps,
        "wins": wins,
        "next_15_minutes": card,
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
    split = result["split"]
    print("%d healthy · %d to fix in your code · %d the audit cannot see yet "
          "· %d not needed"
          % (split["healthy"], split["your_code"], split["not_visible"],
             split["not_needed"]))
    for step in result["unlock_path"]:
        print("  unlock %-36s -> %d more check(s): %s"
              % (label_for(step["capability"]), step["unlocks_count"],
                 ", ".join(step["unlocks"])))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
