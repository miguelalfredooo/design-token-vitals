# An actionable report — design

**Date:** 2026-09-01
**Status:** approved, implementation in progress
**Builds on:** `2026-09-01-framework-aware-discovery.md` and
`2026-09-01-display-density-design.md`, both of which stay in force

---

## The problem

The report grades well and hands off badly.

A reader who opens it learns eight grades, an inventory, three leakage
tiers and a five-item plan. What they cannot get without reading the whole
page is the one answer they came for: *what is worst, how much of my code
does it touch, and what do I fix first?* An agent picking the report up
gets less — findings keyed by literal value, no stable identity across
runs, no statement of which results are confirmed against which are
blocked, and no way to tell whether a swap is safe to automate.

The detailed inventory and the evidence stay. This adds the layer above
them.

## The principle

**Say what is worst, show the arithmetic, and never let an unknown read as
a zero.**

Every ranking in this report shows its inputs. A reader who disagrees with
the order can see which input drove it, and an agent consuming the JSON can
re-rank on its own weights rather than trusting an opaque number.

## What gets added

### 1. Executive summary

First thing on the page, answering four questions in this order:

1. What is the highest-impact problem?
2. How many owned files and components does it affect?
3. What should be fixed first?
4. Which results are confirmed, and which are blocked or unmeasured?

Question four carries equal weight with the other three. A summary that
reports six confirmed grades while staying quiet about two blocked ones
describes a healthier system than the run established.

### 2. Ranked remediation priority, with visible inputs

Four inputs per finding, all recorded:

| Input | Symbol | Why it counts |
|---|---|---|
| Occurrences | `n` | Raw size of the change |
| Affected owned files | `f` | A fix lands per file, so files are the unit of work |
| Breadth across components, plugins, routes and bundles | `b` | Crossing boundaries makes it systemic rather than local |
| Confidence in the proposed fix | `c` | A high-count finding nobody can safely change ranks below a smaller certain one |

```
priority = (n + 2f + 3b) × c
```

Files outweigh occurrences because ten occurrences in one file is one
edit. Breadth outweighs both because a value crossing six components is a
missing system decision rather than a local slip. Confidence multiplies
rather than adds, so an unsafe finding cannot rank first on volume alone.

The report shows `n`, `f`, `b`, `c` and the product. The formula is in
`references/report.md` so two runs rank identically.

### 3. Fix queue

Every finding safe enough to act on mechanically, with:

- the current literal or token
- the canonical replacement token
- affected files and locations
- occurrence and file counts
- confidence, one of `exact static match`, `import-graph verified`,
  `compiled-runtime verified`, `manual review`
- whether the replacement is safe to automate

Safe to automate means the `redundant` tier — a token already holds this
exact value — at a confidence other than `manual review`. Near-miss drift
and uncovered values are never automatable: one needs a person to decide
what was intended, the other needs a token to exist first.

Emitted in both HTML and JSON.

### 4. Grouping by owner, not only by value

Findings group three ways: by literal value (today), and additionally by
owning component, plugin, and route or bundle. An engineer who owns one
component starts from that component and sees its token debt.

### 5. Token lineage

Where the chain can be traced:

```
primitive definition → semantic alias → custom-property projection → consumer usage
```

Lineage is what separates an intentional semantic alias from a duplicate
definition. Two names for one value with a lineage edge between them is a
system working as designed; two names with no edge is the duplicate finding
`single-source` exists to catch. It also carries the typography and
foundational relationships that a flat token list flattens away.

### 6. Coverage matrix

`entry bundle × theme or mode × token family`, covering at least color,
typography, spacing, radius, border, elevation, opacity, z-index,
breakpoint and motion.

Every cell is `measured`, `unmeasured`, `not_applicable` or `blocked`,
carrying its evidence. The matrix is where a gap in what the run could see
becomes visible as a shape rather than as an absence.

### 7. Uncertainty is first-class

- An unknown never renders as zero, passing, or complete.
- Confirmed findings are visually separated from blocked and unmeasured
  areas.
- Every blocked or unmeasured result names the missing artifact and what
  would produce it.

This extends the measured/unmeasured/absent split already in
`references/token-taxonomy.md` to every part of the report.

### 8. Trend support

Findings carry stable ids, so two runs can be compared across commits:

```
id = sha1(tier | family | normalized literal | canonical token)[:12]
```

Path-independent on purpose. A file rename would otherwise resolve every
finding in it and create the same number of new ones, which reads as
churn where nothing changed. Counts move; identity holds.

`tools/trend.py baseline.json current.json` reports new, resolved, count
changes and regressions — a regression being a resolved id that came back,
or a count that grew.

**The comparison is gated.** Scope, framework adapter and token-source
discovery must be compatible, and the tool refuses rather than producing a
diff between two different questions.

Baselines are passed explicitly. The skill never writes state into the
repository it audits, and a stale auto-detected baseline silently changing
what "new" means is exactly the failure this avoids.

### 9. Reproducibility metadata

In both HTML and JSON: report schema version, skill and adapter version,
framework detection evidence, discovered entry points and import roots,
token sources, exclusions, exact scan scope with file count, commit ref,
and timestamp.

Most of this already lands in `discovery` and `run`. This gives it one home
and makes it required rather than customary.

### 10. The HTML holds everything the JSON does

The HTML may collapse long evidence behind `<details>`. It may not hold
less than the JSON. `tools/validate_run.py` checks the finding ids present
in each and fails on any the HTML omits.

## Priorities for this repository

- A fix queue for exact color replacements, the highest-confidence,
  highest-volume class of finding.
- Richer typography lineage, since type scales are where alias chains are
  deepest and least visible.
- A Discourse bundle and theme coverage matrix. The matrix is generic —
  bundle × mode × family for any framework — and the Discourse shape
  (`common`, `desktop`, `mobile` × light and dark × ten families) ships as
  a **documented worked example marked unverified**, because the adapter is
  still held pending a real checkout.

## What stays

Framework-aware discovery and the import-graph reachability requirement are
unchanged and remain prerequisites. The detailed inventory, the evidence
rule, the density forms and the eight vitals all stay as they are.
