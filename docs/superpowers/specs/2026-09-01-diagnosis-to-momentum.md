# From diagnosis to momentum — design

**Date:** 2026-09-01
**Status:** proposed, awaiting approval
**Builds on:** `2026-09-01-design-token-vitals-design.md`,
`2026-09-01-display-density-design.md`,
`2026-09-01-framework-aware-discovery.md`,
`2026-09-01-actionable-report.md`

---

## The problem

The skill establishes what is true and stops short of what to do about it
and where you are going.

Everything built so far serves one job: an evidence rule on every grade,
`blocked` in preference to a guess, reachability before inventory, measured
kept apart from unmeasured. That is an epistemics engine, and it works.
Sitting beside it is nothing that models progress.

Search all 14,600 words of `SKILL.md` and `references/` for a target state,
a benchmark, a maturity level, a milestone or a roadmap and you find none of
them. `pass` is defined as "checked, nothing to fix" — an absence rather
than a destination. Eight grades tell you where you stand against nothing.

What that costs, concretely:

- A designer who fixes all 84 instances of a leaked brand color gets the
  same report back with one fewer row. Nothing marks that they crossed from
  *tokens exist* into *the semantic layer holds*.
- Every finding carries blast radius and no cost. "84 files" is twenty
  minutes with a codemod or two weeks of coordination, and the report cannot
  say which. Impact without effort is half of a decision.
- A healthy codebase gets a wall of green and a "Where to start" section it
  cannot fill. The skill currently only has something to say to systems with
  problems.
- A returning reader re-reads a first-look diagnosis, hunting for what
  changed.

## The principle

**Say where they are, say where next is, and say what it costs to get
there.**

A grade describes a position. Momentum needs a direction and a distance as
well.

## What changes

### 1. A maturity trajectory

Named stages, and no score of any kind — the ban on a composite number
stands and this must never become one. A score averages the finding that
matters into the middle. A stage names a structural fact about the system.

A first cut at the ladder:

| Stage | What is true |
|---|---|
| `scattered` | Values live in components. No token layer to speak of |
| `declared` | Tokens exist and are reachable, and components still go around them |
| `semantic` | A role layer exists, and components reach for roles over primitives |
| `resolved` | Every declared mode resolves, and coverage holds across families |
| `held` | Enforcement stops all of the above from regressing |

The report names the current stage, and the single threshold that moves it
to the next one. The stage is **derived from the graded vitals**, never
asserted: `declared` needs reachable canonical sources, `semantic` needs
`tier-integrity` out of `fail`, `resolved` needs `mode-completeness` and
`coverage` graded rather than blocked, `held` needs `enforcement` passing.

**Acceptance:** the report names a stage and the next threshold; a reader
can check the stage against the eight grades themselves; no number
summarizes the system.

### 2. Effort beside impact

Effort classes derived from data the run already holds, never invented
hours:

| Class | Derivation |
|---|---|
| `S` | `safe_to_automate`, under ~10 files |
| `M` | `safe_to_automate` across many files, or a single-file judgment call |
| `L` | Needs a decision before any edit — drift to reconcile, a token to design |

Impact against effort is the decision a designer actually makes when
choosing what to bring to a team. Shipping impact alone leaves them to guess
the other axis.

**Acceptance:** every fix-queue entry carries an effort class; the queue can
be read as impact against effort; no hour estimate appears anywhere.

### 3. Something to say to a healthy system

A `pass` gains two lines: what protects this today, and what would break it.
Where all eight vitals pass, the report leads with what to protect and the
next horizon rather than with an empty plan.

**Acceptance:** a run that finds nothing wrong still produces a page with a
concrete next action.

### 4. The returning reader's report

Where a baseline was given, movement leads and diagnosis follows. The
executive summary opens with what changed, and the inventory sits below it.

**Acceptance:** with a baseline present, the first thing on the page is
what moved since it.

### 5. Render the system, and not only its tokens

Swatches, ramps, specimens and bars render the *parts*. Nothing renders the
*shape*: how much of the system is primitive against semantic, where a
layer is thin, what the silhouette looks like. Lineage lists chains, which
is a table rather than a picture.

Add one structural rendering — primitive layer, semantic layer, consumers,
sized by count, with the gaps visible. A design-systems reader takes in
structure visually, and one diagram carries more than the inventory
section does.

**Acceptance:** a reader can see which layer is thin without reading a
count.

### 6. Severity drives the layout

A `fail` on leakage and a `pass` on naming currently get the same section
size and the same typographic weight. Severity lives in a chip while the
page treats everything as a peer.

Order sections by severity, give the worst the most room, and collapse the
passing ones.

**Acceptance:** the page order follows the grades; the worst finding is the
largest thing on it.

### 7. The vitals are a dependency graph, drawn as a flat grid

`enforcement` blocked means every other finding comes back next sprint.
Discovery gates all eight. That structure exists and the eight-cell grid
hides it.

Show the dependency, so a reader can see that fixing enforcement protects
the other seven rather than adding a ninth chore.

**Acceptance:** a reader can tell from the page which vitals protect which.

### 8. Re-measure determinism

Two blind runs agreed 8 of 8 on grades and on token count. That result
predates roughly forty percent growth in the skill's text, across the
density work, the discovery stage and the actionable-report layer. The
README currently states it as current, and nobody has re-measured.

It is entirely possible that capability was bought with reproducibility.
There is no evidence either way, which is the problem.

**Acceptance:** two fresh blind runs against the current skill, with the
result recorded in `README.md` whichever way it goes.

### 9. A fixture repository, and a golden output

122 tests cover the tools. Zero cover the skill. Every rule in
`references/` is prose that nothing verifies.

Build a small fixture repository with a known token layer — a canonical
source, an orphaned one, a projection pair, a mode that resolves and one
that does not — and record the expected findings. Then a change to the
rules can be checked rather than reasoned about.

**Acceptance:** a fixture repository exists with an expected result, and a
test compares a run against it.

### 10. One taxonomy, defined once

Nineteen families live in `references/token-taxonomy.md` and nineteen in
`tools/validate_run.py`. They agree today. Nothing makes them agree, so
when they drift, rule 5 either fails a correct report or passes an
incomplete one, and does it quietly.

**Acceptance:** one artifact generates the other, or a test asserts they
match.

### 11. The fix queue emits something applicable

The queue marks findings `safe_to_automate` and then hands over a table.
For a section aimed at follow-on agents, the distance between "safe to
automate" and an applied change is where the momentum goes.

Emit a machine-applicable artifact for the automatable subset — a patch
set, or a codemod stub. Even unapplied, it turns a reading task into a
reviewing task.

**Acceptance:** an agent can act on the automatable subset without
re-deriving any of it.

### 12. Derive confidence rather than asserting it

`exact static match` against `import-graph verified` is currently the
agent's declaration. Nothing computes it. That is a soft spot in precisely
the layer that decides what gets automated.

**Acceptance:** confidence is computed from the match type and the import
graph, and the agent records rather than chooses it.

### 13. A pipeline story, and a ratchet

Exit codes exist and no worked pipeline example does. Separately, a team
adopting this on a legacy codebase meets 1,600 findings with no way to say
"these are accepted, tell me about new ones." Trend detects regressions,
and a backlog with no ratchet drowns the signal anyway.

**Acceptance:** a documented pipeline example; an accepted-baseline
mechanism that still surfaces new findings.

## Sequencing

| Order | Item | Why here |
|---|---|---|
| 1 | Re-measure determinism (8) | Every other claim rests on it, and it is currently unverified |
| 2 | Maturity trajectory (1) | Moves momentum the most, and it is a documentation change |
| 3 | Effort classes (2) | Cheap, derived from data already held |
| 4 | Returning-reader report (4) | Completes the trend work already built |
| 5 | Fixture and golden output (9) | Makes every later change checkable |
| 6 | One taxonomy (10) | Small, and it closes a silent-failure path |
| 7 | Applicable patch set (11) | The largest remaining gap for follow-on agents |
| 8 | Healthy-system path (3), structure rendering (5), severity layout (6), dependency graph (7) | Presentation, once the model underneath is right |
| 9 | Derived confidence (12), pipeline and ratchet (13) | Durability, once the output is stable |

Items 1, 9 and 10 are about whether the skill holds up. Items 2, 3 and 4
are about whether it helps anyone move.

## What stays

No composite score, ever — the maturity stage is a structural claim and it
must never be rendered as a number or a percentage. The evidence rule.
`blocked` in preference to a guess. Framework-aware discovery and
import-graph reachability. The density forms. Measured, unmeasured and
absent as three separate answers.

## Open questions

- **The stage names.** `scattered`, `declared`, `semantic`, `resolved`,
  `held` is a first cut. These become product vocabulary the moment they
  ship, and they need to read as recognizable to a design-systems audience
  rather than as invented jargon.
- **Where effort classes live.** In `capability-map.yml` beside the
  priority inputs, or derived at render time from what is already there.
- **Where a ratchet is allowed to live.** An accepted-baseline file wants
  to sit in the repository being audited, and the trend design deliberately
  says this skill never writes state into that repository. Resolving that
  tension is a real decision rather than a detail: either the rule bends
  for an explicitly user-created file, or the ratchet lives wherever the
  pipeline keeps its baselines.
