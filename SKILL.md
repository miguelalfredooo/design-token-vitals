---
name: design-token-vitals
description: Grade the health of a codebase's design token layer and report what it can and cannot prove about itself. Use when auditing design tokens, checking token adoption, investigating theme or dark-mode bugs, or before adopting a design system. Runs on any web codebase with no setup.
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Design Token Vitals

> **A working skill, still evolving.** What is stable, what is moving, and
> the current reproducibility measurement are in `README.md`. The eight
> principles every stage below answers to are in `PRINCIPLES.md`.

You are grading a codebase's design token layer against eight fixed vitals
and reporting what you found — with evidence, never an average. Work through
the seven stages below in order.

## Stage 1 — Framework and token-source discovery

**Required, and it runs before any inventory or grading.** Do the six jobs
in `references/discovery.md`, in order — detect the framework, discover
every candidate source, build the import graph with `tools/import_graph.py`
and prove reachability, classify every source, deduplicate projections and
derive the scope, discover modes and whether they resolve. The rule under
all six: discover sources from evidence, and prove they ship before grading
them.

Record the whole `discovery` block of `assets/capability-map.yml` before
moving on. Where the scope is ambiguous, say so to the reader rather than
guessing; where no framework matches, use `references/adapters/generic.md`.

## Stage 2 — Detect the stack

Match the repository against `references/adapters/css-vars.md`,
`references/adapters/tailwind.md`, `references/adapters/scss.md`, and
`references/adapters/dtcg.md`, using each file's own Detection section. An adapter says where to look; **no adapter names a token file**, and Stage
1 decides which sources are real.
More than one adapter can apply at once — Tailwind sits on top of custom
properties in most repositories, and both should run. The environment you
recorded in Stage 1 narrows which adapters are even plausible — a
Discourse plugin tree is not going to resolve its tokens through a Next.js
build step, so don't spend time matching adapters the environment already
rules out.

Record `stack.adapters`, `stack.detected_by` (the filename or config key that
proved it), and `stack.confidence` in `assets/capability-map.yml`'s schema.
If nothing matches, do not guess: interview the user about where their
tokens live and how modes are expressed, then record what they tell you with
confidence `interviewed`. A wrong guess costs more than an admitted gap —
it grades code against a system that was never there.

Also record `run.scope` — the globs or directories this run analyzes — and,
for any framework whose default theme the active adapter can draw
categories from, `run.framework_versions` with the installed version you
checked. Stage 4's `coverage` step depends on `framework_versions` already
being recorded here; see the framework-default rule in
`references/vitals.md`'s `coverage` vital and `references/adapters/tailwind.md`.

## Stage 3 — Read what the project declares

Read the repository for its declared modes, categories, and accessibility
target — never assume a standard. This is the step that decides, later,
whether a missing high-contrast mode is `fail` or `not_applicable`: a mode
the project never declared cannot be missing from it. Record these under
`declared` in the capability map before grading anything.

## Stage 4 — Grade the eight vitals

Grade each vital in `references/vitals.md` — tier-integrity, leakage,
coverage, mode-completeness, naming-coherence, single-source, orphans,
enforcement — against the stack and declarations from Stages 2 and 3. For
leakage, classify every hardcoded value through the cascade in
`references/leakage.md`: `redundant`, `near-miss`, then `uncovered`, in that
order, and rank findings by the six-key total order there.

For `coverage`, when the active adapter says a category can come from a
framework's own default theme, checking that framework's installed version
is required before grading — not optional. If `run.framework_versions` was
not recorded in Stage 2 and the version cannot be determined now, grade
`coverage` as `blocked` with a note saying so; never `pass` on an unchecked
assumption. See `references/vitals.md`'s `coverage` vital.

Inventory every foundational family in `references/token-taxonomy.md`, and
record each as `measured`, `unmeasured`, or `absent` under
`inventory.families`, with a count where measured and a note saying what is
missing where unmeasured. **A family the run could not resolve is never
reported as `0`** — zero states that the project has none, which is a claim
this run did not establish. A family found only in an unverified source is
`unmeasured`, because reachability decides here the same as everywhere else.

Five status values only: `pass`, `attention`, `fail`, `blocked`,
`not_applicable`. Attach at least one real `file:line` to every grade that
reports a finding. A clean `pass` and a `blocked` check may carry an empty
evidence list instead, with a note explaining why — there is nothing to
point at when nothing was found, or when the check could not run. A vital
with a count and no reachable instance is `blocked`, never `fail` —
silence is not evidence.

## Stage 5 — Choose the rendering tier and the form per section

Count the tokens the stack detected and choose the tier from
`references/report.md`: under 150 tokens is `full`; 150 to 600 inclusive is
`collapsed`; over 600 is `family-only`. A count of exactly 150 is
`collapsed`; a count of exactly 600 is `collapsed`. Record the tier in
`assets/capability-map.yml`'s `rendering.tier`.

Then choose a rendering form for each listing section, from the form table
in "Change the mark, don't cut the data" (`references/report.md`). The
input is that section's own finding count, not the token total: a repo can
land in `collapsed` on token count and still have a leakage section large
enough to need the densest form. Record one form per section under
`rendering.forms` — `color`, `typography`, `spacing`, `leaks`, `orphans`,
`modes`, `families` — using the value names in that table's columns:
`rows`, `swatches`, `ramps`, `specimens`, `bars`, `grouped`,
`distribution`, `chips`, `by-family`, `matrix`, `coverage-bar`,
`health-strip`, `by-namespace`.

Recording the form is what lets two runs be compared on presentation as
well as on findings. A run that grades the same and renders differently has
diverged, and `rendering.forms` is where that shows up.

## Stage 5b — Rank, queue, and trace

Before writing anything, build the four layers that sit above the raw
findings. All of them go into both the HTML and the JSON.

- **Score every finding** with `tools/findings.py`: occurrences, affected
  owned files, breadth across components, plugins, routes and bundles, and
  confidence in the fix. The formula is `(n + 2f + 3b) x c` and it is fixed,
  so two runs rank identically. **Render the inputs beside the score** — an
  opaque number cannot be argued with or re-weighted.
- **Build the fix queue** from every finding with a canonical replacement.
  Mark `safe_to_automate` only for the `redundant` tier at a confidence
  other than `manual review`; drift and uncovered values always need a
  person. Lead with exact color replacements.
- **Group by owner** as well as by value — component, plugin, route or
  bundle — so an engineer can start from what they maintain.
- **Trace lineage** from primitive to semantic alias to projection to
  consumers. A lineage edge is what separates a deliberate alias from a
  duplicate definition; mark an untraced link as untraced rather than
  guessing at it.
- **Fill the coverage matrix**: entry bundle by mode by family, every cell
  `measured`, `unmeasured`, `not_applicable` or `blocked`, with evidence.

Assign every finding a stable id with `findings.finding_id()`; ids are
path-independent so a rename moves counts rather than re-creating findings.
Derive the stage from `references/maturity.md`, and collect every close
call you recorded in a `note` into `decisions` — each with what it moved
and the other reading.

If the user gave a baseline, run:

```
python3 tools/trend.py <baseline>/report.json .token-vitals/report.json
```

It refuses when the framework, adapters, owned paths, scan scope or token
sources diverge. **Take the refusal.** A forced diff across incompatible
runs reads as progress without being progress. Where no baseline was given,
remove the `trend` region rather than filling it.

## Stage 6 — Fill the template

Copy `assets/report-template.html` to `.token-vitals/report.html`, and strip
the leading `<!-- … -->` instruction comment at the top of the copy — it
tells a contributor how to fill the template, and a finished report goes to
a stakeholder instead. Leave that comment in place in the template itself.

Remove every element whose `data-tier` list excludes the chosen tier. A
region that belongs to a section the chosen tier removed is gone along with
its section — that is expected, not an omission.

Work through the eighteen regions below as a checklist. Every region still
present after tier removal must be filled with real findings from this run
— leaving every other line of the template — headings, ledes, legend, panel
titles — unchanged. A region that still holds the template's own sample
data once you are done is a bug, not an acceptable gap: it means the
report ships describing a codebase that was never scanned.

Every region that lists findings — `inventory-color`, `inventory-type`,
`inventory-space`, `family-coverage`, `families`, `leak-ranked`,
`leak-redundant`, `leak-near-miss`, `leak-uncovered`, `modes-gaps`, and
`orphans` — enumerates
what the run found, in the form you chose for it in Stage 5. When a section
outgrows its form, move to the denser form from the table in
`references/report.md`; showing fewer findings is the wrong answer to more
data. The template carries markup for every form, so this is a choice of
which block to keep, never a rewrite.

`next-steps` is the one exception, and it goes the other way: it shows five
ranked actions, because its value comes from what it leaves out.

Where a section exceeds even its densest form, a `<details>` element on the
same page holds the tail, and the truncation line above it characterizes
the remainder using the `truncation` slot in `references/voice.md` — what
the hidden findings are, never only how many. Never point a reader at the
JSON for something the page itself has room to show.

- [ ] `doc-title`, `runhead-tag`, `runhead-meta` — the subject, never
      "Sample report · representative data"
- [ ] `at-a-glance` — the strip above the summary; every mark carries its
      number
- [ ] `exec-summary` — the stage line, then the four questions
- [ ] `decisions` — every close call, with what it moved and the other
      reading
- [ ] `trend` — remove when no baseline was given; never fill it with a
      comparison the gate refused
- [ ] `vitals-grid`, `next-steps` (five, in the documented order)
- [ ] `fix-queue` — priority inputs beside the score, confidence, effort,
      `safe_to_automate`, `data-finding` on every row
- [ ] `groups`, `lineage`, `coverage-matrix`
- [ ] `inventory-color`, `inventory-type`, `inventory-space`,
      `family-coverage` — every taxonomy family as measured, unmeasured or
      absent; never `0` for unmeasured
- [ ] `families`, `leak-ranked`, `leak-redundant`, `leak-near-miss`,
      `leak-uncovered`, `modes-coverage`, `modes-gaps`, `orphans`,
      `enforcement`
- [ ] `measurement` — everything in `provenance` and `discovery`, the
      rendering tier and forms, read back from the capability map
- [ ] `footer-meta`

For a generated sentence, use the slot templates in
`references/voice.md` verbatim, filling only the named placeholders. For a vital card, set its
`data-grade` attribute and its nested chip's `data-g` attribute from one
grade value, in one place — never compute them separately. Set a family
row's `.pip[data-s]` the same way, from the one grade value that vital
earned for that family. A card whose stripe and chip disagree, or a pip
that disagrees with the card it summarizes, is exactly the drift this
skill exists to catch.

### Validation gate — required before writing the report

Run the eight rules as code, rather than checking yourself against them:

```
python3 tools/validate_run.py .token-vitals/report.json --html .token-vitals/report.html
```

It fails an audit that uses one presumed token file with no discovery
evidence; inventories a source with no path to an owned production import
root; claims complete mode coverage without resolved output for every
audited scheme; reports zero for an unmeasured category; omits typography
or any foundational family from the taxonomy; truncates findings in the
HTML while the JSON holds more; ships a fix-queue entry with no replacement
token, no locations, an unrecognized confidence level, or a safe-to-automate
flag on a tier that needs a person's decision; or renders less in the HTML
than the JSON holds, checked by finding id.

A non-zero exit means the report claims more than the run established. Fix
the run, never the assertion — and never write the report while it fails.

### Completeness check — required before writing the report

This skill asserts things about other people's codebases. Before writing
`.token-vitals/report.html`, verify these are all true of the file you are
about to write. If any fails, fix it and check again — do not write the
report while one of these is still failing:

- No region still holds template sample content. The tell-tale strings are
  `northwind-ds`, `acme-storefront`, `Sample report · representative
  data`, `7f0c22ab`, `a91f4c07`, `color.primitive.json`, `src/**/*.{ts,tsx}`,
  `color.semantic.brand.base`, `motion.ease.emphasized`, and `1,645`.
- Every truncation line names what the remainder holds, not only how many
  it holds.
- `rendering.forms` records one form per listing section, and each form
  named there matches the block actually left in the file.
- Every `SLOT` region present in the file (after tier removal) has real
  content between its markers — none are empty.
- Every vital card's `data-grade` matches its chip's `data-g`.
- The leading instruction comment is gone.

## Stage 7 — Write the outputs

Write `.token-vitals/report.html` (from Stage 6) and `.token-vitals/report.json`
(the filled-in `assets/capability-map.yml` schema, as JSON). The HTML report
is the deliverable — it is what a stakeholder opens, reads, and acts on. The
JSON is a machine-readable duplicate of exactly what the HTML shows, plus
the full detail behind every `<details>` disclosure in it — see "The JSON
duplicates the report" in `references/report.md`. No finding may exist only
in the JSON: render every listing region in the form its volume calls for
(`references/report.md`), so a reader who never opens the JSON still sees
everything the run found, directly or one `<details>` away.

Stamp `provenance.skill_version` from `python3 tools/version.py` before
writing. Then print five lines and stop:

```
<worst vital> <grade> — <one sentence on what it found>
start: <the first fix-queue action, with its file:line>
stage: <stage> → <next stage> after <the threshold>
<n> confirmed · <n> blocked (<which>) · <n> unmeasured (<which>)
<path to report.html>
```

The worst thing, the first move, the stage, the confidence split, the
path. The report is the deliverable; the summary points at it.

## Stop and ask

Stop and ask the user rather than proceeding when:

- No token source can be located, even after checking every adapter.
- Two sources disagree about a token's value and neither is obviously
  canonical.
- The repository declares a mode with no discoverable mechanism for it.
- The user asks for a single score.

On that last one, explain rather than comply. A single number would average
away the finding that matters — a system with thousands of leaked values
and perfect naming would land in the middle of a blended score, hiding the
one thing that needed fixing first. It would also score a repository with
no dark mode as partially unhealthy for a check that does not apply to it.
Offer the eight grades instead, and point to the one vital worth acting on
first.
