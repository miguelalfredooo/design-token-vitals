#!/usr/bin/env python3
"""Join tier, definition site and component usage into one readable chain.

    python3 tools/lineage_map.py --tokens .token-vitals/tokens.json \
        --components .token-vitals/components.json --json .token-vitals/lineage.json

A grade says how a system is doing; a lineage map says what the system IS.
Every part of the chain already exists in a run — the tier and alias on each
concept, the site that defines it, the components that spend it — in three
files nobody reads together. Walking it produces the one artifact a designer
can act on without knowing what a vital is: this value, under this role,
carried by this variable, spent by these components.

A chain that leaves the run stops where it leaves, and says so. A chain that
loops terminates at the loop. Neither is guessed past.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_OK, add_json_flag, emit_json  # noqa: E402


def consumers_by_token(components):
    """token id -> [{component, references, locations}], from the ranked view."""
    found = {}
    for entry in components.get("top_20", []) or []:
        for token in entry.get("tokens", []) or []:
            found.setdefault(token.get("id"), []).append({
                "component": entry.get("name"),
                "references": token.get("references", 0),
                "locations": token.get("locations", []),
            })
    return found


def walk(concept, index):
    """Follow alias edges to a definition, a boundary, or a cycle."""
    hops = []
    seen = set()
    current = concept
    note = None
    stops_at = None
    while current is not None:
        key = current["id"]
        if key in seen:
            stops_at = key
            note = "The alias chain forms a cycle and was not followed past it."
            break
        seen.add(key)
        hops.append({
            "token": key,
            "tier": current.get("tier"),
            "value": (current.get("values") or [None])[0],
            "site": (current.get("sites") or [None])[0],
            "family": current.get("family"),
        })
        alias = current.get("alias_of")
        if not alias:
            break
        following = index.get(alias)
        if following is None:
            stops_at = alias
            note = ("The chain references %s, which this run did not find — "
                    "reported as untraced rather than assumed." % alias)
            break
        current = following
    complete = stops_at is None and hops and hops[-1]["tier"] == "primitive"
    return hops, complete, stops_at, note


def blast_radius(concepts, consumers):
    """Everything that moves when one token's value changes.

    The lineage chain answers "where did this come from"; walked the other
    way it answers the question a designer actually arrives with, and that
    one needs no grade at all. A component is in a token's radius when it
    spends that token OR anything downstream of it — the indirect consumers
    are the ones a change surprises somebody with.
    """
    dependents = {}
    for item in concepts:
        alias = item.get("alias_of")
        if alias:
            dependents.setdefault(alias, []).append(item["id"])
    rows = []
    for item in concepts:
        seen = set()
        queue = [item["id"]]
        while queue:
            current = queue.pop()
            for child in dependents.get(current, []):
                # A cycle would otherwise walk forever. Visiting once is
                # also the right answer: reach is a set, not a path count.
                if child not in seen and child != item["id"]:
                    seen.add(child)
                    queue.append(child)
        components = sorted({entry["component"]
                             for token in seen
                             for entry in consumers.get(token, [])
                             if entry.get("component")})
        rows.append({
            "token": item["id"],
            "tier": item.get("tier"),
            "family": item.get("family"),
            "dependent_tokens": sorted(seen),
            "components": components,
            "component_count": len(components),
        })
    rows.sort(key=lambda row: (-row["component_count"],
                               -len(row["dependent_tokens"]), row["token"]))
    return rows


def build(tokens, components):
    concepts = tokens.get("concepts", []) or []
    index = {item["id"]: item for item in concepts}
    consumers = consumers_by_token(components or {})
    chains = []
    for item in concepts:
        hops, complete, stops_at, note = walk(item, index)
        chains.append({
            "token": item["id"],
            "family": item.get("family"),
            "tier": item.get("tier"),
            "hops": hops,
            "root": hops[-1] if complete else None,
            "complete": complete,
            "stops_at": stops_at,
            "note": note,
            "consumers": consumers.get(item["id"], []),
        })
    chains.sort(key=lambda chain: (-len(chain["consumers"]), chain["token"]))

    by_family = {}
    for chain in chains:
        by_family.setdefault(chain["family"], []).append(chain["complete"])
    # A family is a win only when EVERY token in it traces. One untraced
    # token in a family is the one a change will surprise someone with, so a
    # majority does not earn the claim.
    fully_traceable = sorted(family for family, flags in by_family.items()
                             if family and all(flags))
    return {
        "chains": chains,
        "summary": {
            "traced_to_a_primitive": sum(1 for c in chains if c["complete"]),
            "stops_before_a_primitive": sum(1 for c in chains
                                            if not c["complete"]),
            "with_a_named_consumer": sum(1 for c in chains if c["consumers"]),
            "longest_chain": max((len(c["hops"]) for c in chains), default=0),
        },
        "fully_traceable_families": fully_traceable,
        "blast_radius": blast_radius(concepts, consumers),
    }


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tokens", required=True)
    parser.add_argument("--components")
    add_json_flag(parser)
    args = parser.parse_args(argv)
    with open(args.tokens, encoding="utf-8") as handle:
        tokens = json.load(handle)
    components = {}
    if args.components:
        with open(args.components, encoding="utf-8") as handle:
            components = json.load(handle)
    result = build(tokens, components)
    emit_json(args.json_out, result)
    summary = result["summary"]
    print("%d token(s) trace to a primitive · %d stop before one · "
          "%d have a named consumer · longest chain %d hop(s)"
          % (summary["traced_to_a_primitive"],
             summary["stops_before_a_primitive"],
             summary["with_a_named_consumer"], summary["longest_chain"]))
    widest = result["blast_radius"][0] if result["blast_radius"] else None
    if widest and widest["component_count"]:
        print("widest reach: changing %s touches %d component(s) through "
              "%d dependent token(s)"
              % (widest["token"], widest["component_count"],
                 len(widest["dependent_tokens"])))
    if result["fully_traceable_families"]:
        print("fully traceable: %s"
              % ", ".join(result["fully_traceable_families"]))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
