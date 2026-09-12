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

## Stage 0 — Ask what this run is for

**One question, before anything runs.** The same eight vitals answer four
different questions, and the one being asked decides which finding leads,
what counts as done, and what the report should say about a gap.

| Intent | Leads with | Done when |
|---|---|---|
| `baseline` | What can be proven today, and what cannot yet | Every vital has a confidence state and the unlock path is written down |
| `adoption` | Component token usage and the leakage ranking | The `assess-first` band is worked through |
| `themes` | Mode resolution and cross-mode parity | Every declared mode resolves with real output |
| `release` | Regressions against the stored baseline | No vital moved backwards |

Default to `baseline` for a first run on a repository and to `release` when a
baseline was given. Record it as `run.intent`. **Never diff two runs with
different intents** — they were scoped to answer different questions, and
`tools/trend.py` already refuses on a scope divergence for the same reason.

A first run is almost always `baseline`, and saying so out loud matters: it
sets the expectation that gaps in what the audit can SEE are the expected
output of a first run rather than a verdict on the codebase.

## Stage 1 — Framework and token-source discovery

**Required, and it runs before any inventory or grading.** Start with:

```
python3 tools/discover_environment.py <root> [--owned <glob>]... [--app <workspace-app>] [--profile <id>]... [--profile-file <profiles.json>]... --json .token-vitals/discovery.json
```

Then discover reachable sources and collapse projections with:

```
python3 tools/discover_tokens.py <root> --discovery .token-vitals/discovery.json [--source <confirmed-source>]... --update-discovery --json .token-vitals/tokens.json
```

Then measure which component surfaces use those confirmed concepts:

```
python3 tools/analyze_component_usage.py <root> --discovery .token-vitals/discovery.json --tokens .token-vitals/tokens.json --json .token-vitals/components.json
```

Use the framework-neutral component definition and measurement boundaries in
`references/component-usage.md`. Framework adapters may add resolvers for
utility classes or runtime styling, but may not replace the universal output
shape or silently count an unresolved class as a token reference. Adoption
analysis starts from proven production reachability; ownership alone never
admits a file. Adapters may publish evidenced `component_roots` for framework
component trees that the style import graph cannot see.

For color leakage, run:

```
python3 tools/audit_literal_colors.py <root> --discovery .token-vitals/discovery.json --tokens .token-vitals/tokens.json --json .token-vitals/literal-colors.json
```

Its exact-value
matches remain manual-review candidates until semantic equivalence is
proven; value equality alone never authorizes a replacement. `near_miss` and
`semantic_equivalence` come back as states, not as a bare string: with no
literal in any consumer style nothing can be a near-miss, and with no
exact-value candidate no replacement's semantic role is in question, so both
read `counted` with none found and leakage becomes gradeable. Where
literals do exist both stay `not-visible` and say how many remain to compare.

Typography and brand color are identity-critical outputs, not decorative
examples. Token discovery must produce `identity.typography` and
`identity.brand_colors` with a state, confidence, and real evidence. Select a
font only from the strongest concrete reachable `font-family` token; if two
equally strong declarations disagree, mark identity `not-visible` and do not
render an inherited or substitute specimen. A verified specimen must embed a
reachable repository-owned WOFF2, WOFF, TTF, or OTF asset whose format, magic
bytes, size, and hash were checked; otherwise keep the family evidence visible
but mark the specimen `not-visible`. Select brand colors only when a
concrete reachable value has an explicit `brand` token name or lives under a
source heading that explicitly says brand or visual identity. Never infer a
brand palette from broad names such as `primary`, `secondary`, or `accent`
alone. Infer audited-product namespaces from repository, package, and repeated
owned-package evidence; use that recorded evidence to exclude known third-party
service namespaces without suppressing the audited product's own name. Keep
every color tied to the exact definition, site, and heading that qualified it.
If one brand token has multiple concrete values without explicit mode
provenance, render it as a blocked conflict rather than choosing one.

Then do the six jobs
in `references/discovery.md`, in order — detect the framework, discover
every candidate source, build the import graph with `tools/import_graph.py`
and prove reachability, classify every source, deduplicate projections and
derive the scope, discover modes and whether they resolve. The rule under
all six: discover sources from evidence, and prove they ship before grading
them.

The tool returns capability facts in one universal shape. Executable,
composable profiles in `assets/framework-profiles.json` teach it where to
find evidence. Profile-declared extractor hooks read config arrays, build
JSON, and registration calls, so framework registration is executable rather
than prose guidance. Static roots that cannot be reached stay visible as
`root_candidates`; component locations outside owned scope stay visible as
`component_root_candidates`. Orphan stylesheets arrive split by the scope
the run was given, in the `orphans` block: report the `owned` half, and keep
`outside_owned_scope` visible as evidence that is not this run's finding. Adapters explain how to investigate what each
profile finds.
Use `references/environment-adapters.md` for the profile contract and read
only the adapters listed in the discovery output. When a monorepo has
several plausible applications, stop at the engine's blocked selection and
ask which `--app` to audit. Record the whole `discovery` block of
`assets/capability-map.yml`; use `references/adapters/generic.md` when no
profile matches.

## Stage 2 — Detect the stack

Match the repository against `references/adapters/css-vars.md`,
`references/adapters/tailwind.md`, `references/adapters/scss.md`, and
`references/adapters/dtcg.md`, plus every active framework profile and
adapter returned by Stage 1. Built-in profiles cover Discourse,
Rails/Sprockets, Next.js, Vite, SvelteKit, Nuxt, Astro, Angular, Remix,
Ember, React Scripts, Storybook, and monorepos. An adapter says where to look; **no adapter names a token file**, and Stage
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
whether a missing high-contrast mode is `needs-work` or `not-needed`: a mode
the project never declared cannot be missing from it. Record these under
`declared` in the capability map before grading anything.

## Stage 4 — Grade the eight vitals

Grade each vital in `references/vitals.md` — tier-integrity, leakage,
coverage, mode-completeness, naming-coherence, single-source, orphans,
enforcement — against the stack and declarations from Stages 2 and 3. For
leakage, classify every hardcoded value through the cascade in
`references/leakage.md`: `redundant`, `exact-value candidate`, `near-miss`,
then `uncovered`, in that order, and rank findings by the six-key total
order there. Equal values alone prove only an `exact-value candidate`;
`redundant` additionally requires evidence that the token and literal carry
the same semantic role at that consumer.

For `coverage`, when the active adapter says a category can come from a
framework's own default theme, checking that framework's installed version
is required before grading — not optional. If `run.framework_versions` was
not recorded in Stage 2 and the version cannot be determined now, grade
`coverage` as `not-visible` with a note saying so; never `healthy` on an unchecked
assumption. See `references/vitals.md`'s `coverage` vital.

Inventory every foundational family in `references/token-taxonomy.md`, and
record each as `counted`, `not-visible`, or `none-used` under
`inventory.families`, with a count where measured and a note saying what is
missing where unmeasured. **A family the run could not resolve is never
reported as `0`** — zero states that the project has none, which is a claim
this run did not establish. A family found only in an unverified source is
`not-visible`, because reachability decides here the same as everywhere else.

`discover_tokens.py` decides this for you and publishes it as
`family_states`: `counted` carries a count, `not-visible` carries **no
number at all**, and `none-used` is the one state that has earned the number 0.
Read that block rather than `family_counts`, which cannot tell a family the
run proved empty from one it never reached — and note that a family is also
`not-visible` when a confirmed source declared it with a value the reader
would not invent, as `backdropBlur: spacing[2]` does. `render_discovery.py`
fills `inventory.families` from it.

Five status values only: `healthy`, `watch`, `needs-work`, `not-visible`,
`not-needed`. Attach at least one real `file:line` to every grade that
reports a finding. A clean `healthy` and a `not-visible` check may carry an empty
evidence list instead, with a note explaining why — there is nothing to
point at when nothing was found, or when the check could not run. A vital
with a count and no reachable instance is `not-visible`, never `needs-work` —
silence is not evidence.

## Stage 5 — Choose the report view (everything else is derived)

Choose the report's initial view independently of its data density:

- `snapshot` — open on the dashboard: what matters now.
- `action` — open the working plan: the one card that leads, then priorities,
  owners, component roadmap, gaps, and rollout guidance.
- `evidence` — open the complete audit: inventory, lineage, discovery,
  provenance, and every implementation detail.

Default to `snapshot` unless the user asks for another view. Record the
selection as `rendering.view` and the fixed ordered list
`[snapshot, action, evidence]` as `rendering.available_views`. Keep every
section and finding in the one self-contained HTML file regardless of the
initial view. Treat the view as progressive disclosure, never as permission
to omit evidence. Make a deep link reveal the least-detailed view containing
its target, and show every section when printing.

**The list size and the per-section form are derived, not chosen.** Run:

```
python3 tools/rendering_choices.py
```

`rendering_choices.apply()` writes both into `rendering`: the list size from
the token count (`full` under 150, `short` through 600 inclusive, `summary`
above), and one form per section from **that section's own** count, using
the table in `references/report.md`. A small repository can still have a
leakage section large enough to need the densest form, which is why the
token total never decides a section.

These were two hand-set axes — three list sizes and thirteen form values
across seven sections — where a wrong value is a silent formatting bug
rather than an error, and both rules were already deterministic and written
down. The only axis still chosen is `rendering.view`, because it encodes
what the run is FOR rather than how much data came back.

Recording the view, tier, and forms lets two runs be compared on presentation
as well as on findings. A run that grades the same and renders differently has
diverged, and the `rendering` block is where that shows up.

## Stage 5b — Rank, queue, and trace

Before writing anything, build the five layers that sit above the raw
findings. All of them go into both the HTML and the JSON.

- **Score every finding** with `tools/findings.py`: occurrences, affected
  owned files, breadth across components, plugins, routes and bundles, and
  confidence in the fix. The formula is `(n + 2f + 3b) x c` and it is fixed,
  so two runs rank identically. **Render the inputs beside the score** — an
  opaque number cannot be argued with or re-weighted.
- **Build the fix queue** from findings with a canonical replacement.
  Mark `safe_to_automate` only when the finding is `redundant`, its
  `semantic_role_verified` flag is true, and its confidence is not
  `manual review`. A raw exact-value match is a review candidate, not a
  replacement instruction. Lead with the highest-impact verified fixes;
  list unverified exact matches separately as decisions.
- **Group by owner** as well as by value — component, plugin, route or
  bundle — so an engineer can start from what they maintain.
- **Rank component token usage** with `tools/analyze_component_usage.py`.
  Show identified components before generic style surfaces, then rank within
  each kind by reference occurrences, distinct token count, and stable key.
  Use generic surfaces only to fill a list shorter than 20 and label the
  fallback. Render every token used by each entry, its family, syntax, count,
  and real locations. State which reference syntaxes were measured and which
  remain unresolved. Group repeated locations by file, show the first two,
  and keep the remainder in a default-closed, accessible “See N more locations” disclosure;
  preserve every full `file:line` value in HTML, JSON, and print. Validate the
  one-file-label, two-location preview, hidden count, default-closed state, and
  disclosure tail.
  Split the ranked view into cumulative-use roadmap bands: the rows that carry
  the first roughly 50% of confirmed references are `assess-first`, the rows
  through roughly 80% are `plan-next`, and the remainder are
  `focused-follow-up`. Show the first five on the dashboard and all ranked rows
  in the component section. This orders investigation by token footprint.
  Runtime frequency, migration safety, and component quality require separate
  evidence.
- **Split the gaps, and build the unlock path**, with
  `tools/unlock_path.py`. `not-visible` says two unrelated things in one word —
  *your system has a problem* and *this audit cannot see far enough yet* —
  and a repository whose token layer is in good shape reads as mostly
  blocked, which is both wrong and the reason a reader closes the tab. Every
  vital gets one of four confidence states: `verified`,
  `needs-work`, `not-visible`, `not-needed`. **Report
  the two kinds of gap as two numbers and never sum them.** Order the
  capability gaps by how many vitals each unlocks, give each one an action
  and the command that shows whether it worked, and lead the dashboard with
  the single `next_15_minutes` card. A `not-needed` vital is a declared
  boundary and belongs with the wins, not with the holes.

  ```
  python3 tools/unlock_path.py .token-vitals/report.json --discovery .token-vitals/discovery.json --json .token-vitals/unlock.json
  ```

- **Draw the blast radius** from the same map. "Changing
  `--color-action-primary` touches 11 components" is the question a designer
  actually arrives with, and it needs no grade at all. A component is in a
  token's radius when it spends that token **or anything downstream of it** —
  the indirect consumers are the ones a change surprises somebody with.

- **Draw the lineage map**, with `tools/lineage_map.py`. A rating says how a
  system is doing; the map says what the system IS — this value, under this
  role, carried by this variable, spent by these components — and it is the
  one output a designer can act on without knowing what a check is. Render
  the chain, not the count. A family where **every** token traces to a
  primitive is a real win and is named as one; a majority is not.

  The tiers it draws are already on the concepts: discovery derives `tier`
  and `tier_evidence` in an order of evidence — a name that states its layer
  is a declaration, a reference to another token is structural proof of an
  alias, a concrete value with neither is a primitive, anything else stays
  `untraced`. A lineage edge is what separates a deliberate alias from a
  duplicate definition, so mark an untraced link untraced rather than
  guessing at it, and never overwrite a tier with a reading of your own — if
  the evidence is wrong, fix what produced it.

  ```
  python3 tools/lineage_map.py --tokens .token-vitals/tokens.json --components .token-vitals/components.json --json .token-vitals/lineage.json
  ```

- **Fill the coverage matrix**: entry bundle by mode by family, every cell
  `counted`, `not-visible` or `not-needed`, with evidence.
- **Derive the unification strategy** from the same measured facts. Follow
  `references/adoption-strategy.md`: recommend a framework-neutral token
  contract, generated delivery adapters, and shared components only where
  ownership is proven. Never infer that a token audit established component
  behavior. Record the selected model, its exact evidence, five integration
  constraints, five architecture layers, the standards baseline, six gated
  rollout phases, guardrails, and success measures under `adoption_strategy`.

Assign every finding a stable id with `findings.finding_id()`; ids are
path-independent so a rename moves counts rather than re-creating findings.
Derive the stage from `references/maturity.md`, and collect every close
call you recorded in a `note` into `decisions` — each with what it moved
and the other reading.

**Date the evidence.** `tools/freshness.py` places the run in history:
fresh against the commit it measured, or so many commits and a dirty tree
behind it. A report with no age on its numbers is trusted for as long as
somebody leaves the tab open, and a token audit goes stale the next time
anyone touches a stylesheet. `render_discovery.py` measures this for you.

If the user gave a baseline, run:

```
python3 tools/trend.py <baseline>/report.json .token-vitals/report.json
```

In CI, use `--ci`: one line, and a non-zero exit **only** on a regression.
A gate that fails an absolute threshold — forty leaked values, say — fails
the build every day until somebody deletes the gate; a gate that fails only
when the number grows is one a team keeps. A missing baseline is a first
run, not a failure.

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

Work through the regions below as a checklist. Every region still
present after tier removal must be filled with real findings from this run
— leaving every other line of the template — headings, ledes, legend, panel
titles — unchanged. A region that still holds the template's own sample
data once you are done is a bug, not an acceptable gap: it means the
report ships describing a codebase that was never scanned.

Every region that lists findings — `inventory-color`, `inventory-type`,
`inventory-space`, `family-coverage`, `families`, `leak-ranked`,
`leak-redundant`, `leak-exact-value-candidates`, `leak-near-miss`,
`leak-uncovered`, `modes-gaps`, and
`orphans` — enumerates
what the run found, in the form you chose for it in Stage 5. When a section
outgrows its form, move to the denser form from the table in
`references/report.md`; showing fewer findings is the wrong answer to more
data. The template carries markup for every form, so this is a choice of
which block to keep, never a rewrite.

After filling the template, merge and render the deterministic discovery and
component-adoption views:

```
python3 tools/render_discovery.py --refresh-template --report-view snapshot --discovery .token-vitals/discovery.json --tokens .token-vitals/tokens.json --leakage .token-vitals/literal-colors.json --unlock .token-vitals/unlock.json --lineage .token-vitals/lineage.json --report-json .token-vitals/report.json --html .token-vitals/report.html
```

`--unlock` and `--lineage` carry the confidence split, the unlock path, the
wins and the blast radius into the page, and measure evidence freshness
against the commit discovery recorded. Rule 19 fails a report that holds
that evidence in the JSON and not in the HTML.

```
python3 tools/render_component_usage.py --components .token-vitals/components.json --report-json .token-vitals/report.json --html .token-vitals/report.html
```

These replace existing regions when present and insert them into older report
shells. Run both before the validation gate so profiles, capability states,
roots, unresolved imports, components, and token details are checked for
HTML/JSON parity.

`--refresh-template` is required for a finished stakeholder report. It starts
from the installed current template, strips its contributor-only instruction
comment, fills the mandatory summary, decision, ownership, lineage, coverage,
mode, orphan, and enforcement regions from `report.json`, and prevents an old
partial shell from silently dropping rich JSON-only evidence.

`next-steps` is the one exception, and it goes the other way: it shows five
ranked actions, because its value comes from what it leaves out.

### One answer to "what do I do next"

The report grew five differently-shaped answers to the most obvious question
a reader has: `next_15_minutes`, `next-steps`, `fix-queue`, the roadmap
bands, and the rollout phases in `adoption_strategy`. Someone opening the
page and asking what to do got five, in five places, with no stated relation
between them. That is not thoroughness; it is a reader deciding which list
to believe.

**One card leads: `next_15_minutes`.** It is the only action on the
dashboard, and everything else is framed as the rest of *that* queue rather
than as a parallel recommendation:

| Surface | What it is, said out loud |
|---|---|
| `next_15_minutes` | The one thing to do now. On the dashboard. |
| `next-steps` | The next five, once that one is done. |
| `fix-queue` | Every mechanical fix, ranked — the long tail of `next-steps`. |
| roadmap bands | Which components to *look at* first. Not a to-do list. |
| `adoption_strategy` | The quarter-scale plan. Not this week's work. |

Say which one a section is when you render it. A reader who cannot tell a
fifteen-minute task from a quarter-long programme will do neither.

Where a section exceeds even its densest form, a `<details>` element on the
same page holds the tail, and the truncation line above it characterizes
the remainder using the `truncation` slot in `references/voice.md` — what
the hidden findings are, never only how many. Never point a reader at the
JSON for something the page itself has room to show.

Canonical token inventory tables show the first 20 rows and place every
remaining row in a collapsed `<details>` disclosure labeled “See N more
tokens.” This is progressive disclosure, not data truncation: every token and
its structured parity attributes remain in the HTML. Present Color,
Typography, and Foundation as inventory-family tabs with tablist/tabpanel
relationships, Arrow/Home/End keyboard navigation, hash deep links, all panels
visible without scripting and all panels visible in print. Author every report
disclosure open, record its enhanced default state, and let the verified
controller restore that state when scripting is available. Before printing,
open every report disclosure so no evidence tail is omitted; after printing,
restore each disclosure's prior state. Tabs select token families; they never
paginate arbitrary table rows.

- [ ] `validation-banner` — leave it exactly as shipped. Do not fill it,
      remove it, or hand-edit `provenance.validation_gate` — only a passing
      `validate_run.py --stamp` run may clear it (see below)
- [ ] `doc-title`, `runhead-tag`, `runhead-meta` — the subject, never
      "Sample report · representative data"
- [ ] `report-view-switcher` — Snapshot, Action Plan, and Evidence from one
      complete evidence set; selected view matches `rendering.view`
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
- [ ] `unlock-path` — the two gap counts side by side and never summed, the
      ordered capability steps with what each unlocks, and the single
      `next_15_minutes` card with its action, payoff and verify command
- [ ] `wins` — ground gained, in the run's own words: capabilities verified,
      families fully traceable, declared boundaries named as decisions
- [ ] `groups`, `discovery-engine`, `component-usage`, `lineage`, `coverage-matrix`
- [ ] `inventory-color`, `inventory-type`, `inventory-space`,
      `family-coverage` — every taxonomy family as measured, unmeasured or
      absent; never `0` for unmeasured
- [ ] identity — render the verified font family and every explicitly declared
      brand color prominently, with confidence and source evidence; embed only
      a repository font proven by its reachable `@font-face`; show all competing
      typography candidates and brand-value conflicts; if identity or its
      specimen is blocked, show the block and render no generic substitute
- [ ] `families`, `leak-ranked`, `leak-redundant`,
      `leak-exact-value-candidates`, `leak-near-miss`, `leak-uncovered`,
      `modes-coverage`, `modes-gaps`, `orphans`,
      `enforcement`
- [ ] `measurement` — everything in `provenance` and `discovery`, including
      the capability table, root evidence, ownership split, unresolved
      imports by reason, and bundle × scheme verification; plus the
      initial report view, rendering tier, and forms, read back from the
      capability map
- [ ] `discovery-capabilities` — the seven universal capabilities, each
      with state, strongest evidence, and current limitation
- [ ] `adoption-strategy` — the final report section; the evidence-derived
      unification model, integration constraints, target architecture,
      standards, six-phase rollout, guardrails, and measurable outcomes from
      `references/adoption-strategy.md`
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

Run the nineteen rules as code, rather than checking yourself against them. The
source-artifact inputs prevent an internally consistent but stale report from
passing after a newer discovery or analysis step:

```
python3 tools/validate_run.py .token-vitals/report.json --html .token-vitals/report.html --discovery .token-vitals/discovery.json --tokens .token-vitals/tokens.json --components .token-vitals/components.json --leakage .token-vitals/literal-colors.json --current-skill --stamp
```

It fails an audit that uses one presumed token file with no discovery
evidence; inventories a source with no path to an owned production import
root; claims complete mode coverage without resolved output for every
audited scheme; reports zero for an unmeasured category or grades leakage
while semantic equivalence is unmeasured; omits typography
or any foundational family from the taxonomy; truncates findings in the
HTML while the JSON holds more; ships a fix-queue entry with no replacement
token, no locations, an unrecognized confidence level, or a safe-to-automate
flag without verified semantic equivalence; renders less in the HTML than
the JSON holds, checked by finding id; publishes a Top 20 component list
without deterministic ranking, token details, paths, and locations; or lets
the discovery profile stack, capability ladder, production roots,
supplemental surfaces, and rendered evidence drift apart.
It also fails when typography or brand colors are generic, inferred without
explicit semantic evidence, missing from the visible HTML, or inconsistent
with the source token artifact. It fails when the closing unification strategy
is absent, generic, stale against the report evidence, missing an integration
constraint, architecture layer, or rollout phase, or inconsistent between JSON
and HTML.
It fails, as rule 19, when the confidence evidence is absent, when the HTML merges the two gap counts into one or disagrees with the JSON about either, or when a vital is switched off with `not-needed` and no rationale on record.
It fails, as its own rule, when any region still holds the template's sample
content — `a91f4c07` and the rest — rather than folding that into an identity
complaint, because the fix is a region you did not fill, not the font evidence.
With `--current-skill`, it also refuses a report stamped by an older copy of
the skill, which prevents a stale report from passing after discovery logic
changes.

A non-zero exit means the report claims more than the run established. Fix
the run, never the assertion — and never write the report while it fails.

`--stamp` is what actually finishes the report: on a pass, it writes
`provenance.validation_gate` into the JSON and replaces the `report.html`
validation banner with a small "validated" note — the one field and the one
region a report generator must never touch directly (see the `assets/report-template.html`
validation-banner region and `assets/capability-map.yml`'s
`provenance.validation_gate`). Every report ships the banner by default; a
report handed to a reader still showing it was written without the gate,
regardless of what the surrounding prose claims — and a partial or
time-boxed run must say so out loud rather than let the banner speak for it
implicitly. Running the plain command without `--stamp` is a legitimate way
to check status without writing anything — the finished report is the one
produced by the `--stamp` invocation actually passing.

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
- The three report-view buttons are present once, the selected button matches
  `rendering.view`, and every section declares its allowed views.
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
<n> verified · <n> need system work · <n> need audit capability · <n> not applicable
next 15 min: <the card's action> → <its payoff>
unlock: <first capability step> unlocks <n> vital(s): <which>
<worst vital> <grade> — <one sentence on what it found>
<path to report.html>
```

Where a baseline was given, replace the first line with what
`tools/trend.py` leads with — "No regressions. Evidence coverage improved
from 1 to 6 verifiable vital(s)." — because on a follow-up run the movement
is the finding.

The split, the next move, what it unlocks, the worst thing, the path. The
two kinds of gap stay two numbers on that first line: a reader who cannot
tell "we could not see this" from "you have a problem here" learns the wrong
thing about their own codebase, which is the failure this whole skill is
against.

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
