# Changelog

What changed, by version. The skill stamps its version into every report
as `provenance.skill_version`, so a report can be traced back to the rules
that produced it.

## 0.2.0 — 2026-09-15

Three things landed on top of the entries below, all on 2026-09-15.

### The Tailwind utility adapter (#31)

`tools/tailwind_adapter.py` resolves a Tailwind utility class to a theme key, or
declines. Longest prefix wins, ambiguity is reported as `ambiguous` with its
candidates rather than resolved to a guess, and an arbitrary value is classified
by spelling: `bg-[#ff0000]` is a literal leak, `bg-[var(--brand)]` is a reference
and is not.

**It is not yet wired into the audit path**, so it changes no grade on its own.

### `TRIGGERS.md` (#32)

Six prompts the skill should answer, four it should decline, each declining row
naming what owns the request instead. Both sets are data rather than prose, so
they can be counted. `check_voice.py` now covers the file in CI.

### Exit 2 means could not run (#33)

Four cases were driven before they were fixed, and **two returned a clean verdict
over a file nobody read**: `check_voice.py` with no arguments printed
`voice: clean (0 file(s))`, and `palette.py` announced that text clears AA in
every theme on a document containing no color at all. The other two raised, and
an uncaught raise exits 1 — the same code as "found problems", so a missing file
arrived as a finding.

`0` clean · `1` findings · **`2` could not run**, with the reason on stderr.
Scoped to the two tools CI gates on; the rest of `tools/` is not audited for this.

### Everything below was already merged and unreleased

These shipped to `main` between 0.1.0 and now and had accumulated under an
`Unreleased` heading. They are part of this release.

### Fixed — a frozen object kept its keys but lost its path

`Object.freeze({` never matched the object-open pattern, because that pattern
required a line ending in a bare `{`. So a frozen object never entered the
nesting stack and **every leaf inside it got a bare name**. Four different
components each declaring a `height` collapsed into one concept called
`height`, which was then reported as a duplicate definition: two distinct
tokens merged and a false conflict invented in the same line of code. And
`Object.freeze` is the common idiom in a token module, so this hit the normal
case rather than an exotic one.

```
production-ds  concepts  1,071 -> 1,104     conflicts  87 -> 80
```

A key spelled `--foo` stays global, though. It names a CSS custom property, so
prefixing it with the JS object that happens to carry it would break the link
to the same variable declared in a stylesheet — which is the only reason a
profile module writes keys in that spelling.

**Two of this repository's own tests were green because of the bug**, their
fixtures relying on a frozen object flattening its keys.

Three more defects from the same audit:

- **The stamped banner said "all 18 rules" while nineteen ran** — the same
  drift as the summary line's `17`, in the one place a reader actually sees it.
  Both are derived now, and a guard fails on any rule-count literal left in the
  source.
- **Eleven `ResourceWarning`s** from unclosed reads of the report template.
  Noise in a test run is where a real warning hides.
- **`tools/rendering_choices.py` accepted only a bare token count**, so
  per-section forms still had to be applied by hand from the reference
  thresholds — the exact authoring decision the module exists to remove. It
  now reads `--tokens`, `--leakage` and `--discovery`, and prints the count
  each form was chosen from. A family the run could not see contributes
  nothing rather than a zero.

The published example moved with the reader change, since shipping the old
file would recreate the staleness this fixes:

```
shadcn-ui   concepts  1,185 -> 1,197   conflicts  102 -> 103
            58 conflicts now attributed to registry/themes.ts, was 44
```

604 tests, 45 mutations bite, 2 controls hold, and all nineteen rules still
pass on the regenerated example.

### The audit says whose problem it is

A repository whose token layer is in good shape read as mostly blocked. It
was not failing anything — the audit could not see far enough yet. Now that
the ratings say which is which, three things follow from it.

**`tools/unlock_path.py` splits and orders the gaps.** The two kinds are
counted as **two numbers that are never summed** — closing an audit gap and
fixing a real problem are different work by different people, and one figure
tells a reader neither which they did nor which is left. Capability gaps are
a path rather than a list: each step names the action, the checks it unlocks,
and the command that shows whether it worked, ordered by how many it moves.
A `next_15_minutes` card leads with one of them. On the audited repository
the line reads `5 healthy · 1 to fix in your code · 2 the audit cannot see
yet`, where it had read as six blocked vitals. `framework_versions` — an
input the operator did not supply rather than a capability the engine lacks
— is named alongside the rest, because a blocked `coverage` with every
capability verified was the one line in the whole report that gave a reader
nothing to do.

**`tools/lineage_map.py` draws what the system IS.** A rating says how a
system is doing; the map joins the three files nobody read together — the
tier and alias on each concept, the site that defines it, the components
that spend it — into one chain. 768 tokens trace to a primitive, 303 stop
before one, 204 have a named consumer, the longest chain is four hops, and
twelve families are traceable end to end. A family counts only when **every**
token in it does. Walked the other way it answers the question a designer
actually arrives with: changing `color-surface` touches three components
through twenty dependent tokens.

**`tools/freshness.py` dates the evidence** — fresh against the commit
discovery recorded, or so many commits and a dirty tree behind it. A dirty
tree is never fresh: the edit in it is exactly the change the audit did not
see.

And the report opens on a sentence rather than a grid: "5 of 8 checks look
healthy; 2 the audit cannot see yet — that is a limit of this run, not of
your code."

### Every line is an observation, or it is not shipped

An audit pass over what this tool says to a reader found four sentences that
asserted more than the run had established.

- **A win carries the measurement behind it, or is not emitted.** They were
  generic sentences fired by a capability flag: "Framework detected — the
  adapters that ran are the right ones" is an interpretation that detection
  cannot support. Each renders its claim beside a real number or path —
  "Import graph verified · 291 file(s) reached; 147 import(s) classified, 0
  unresolved as a missing local file" — and a capability with no measurement
  produces no win at all. A congratulation nobody can check is worse than
  silence.
- **The first version of that rule suppressed a true win.**
  `token_source_discovery` records its evidence on its capability ladder step
  rather than under a key of its own, so looking in one place turned a fully
  established result into nothing. It falls back to whatever the run itself
  recorded — a false zero being exactly what this tool exists to stop.
- **Three sentences restated a grade as a measurement.** "Checked against
  evidence, nothing to fix" claimed evidence a clean check is allowed not to
  have; "the codebase has a real finding here" editorialized about somebody
  else's judgment; "a boundary, not a hole" characterized a decision instead
  of quoting the reason recorded for it.
- **A verify command with `<root>` in it is not a command.** The card told a
  reader to run something and check the result, and handed them a template.

### One answer to "what do I do next"

The report had grown five differently-shaped answers to the most obvious
question a reader has. One card leads — `next_15_minutes` — and the others
are named as the rest of *that* queue rather than as parallel
recommendations. A reader who cannot tell a fifteen-minute task from a
quarter-long programme will do neither.

Two presentation axes stopped being authoring decisions: `tools/rendering_choices.py`
derives the list size from the token count and each section's form from that
section's own count, both from rules that were already deterministic and
already written down. The only axis still chosen is `rendering.view`,
because it encodes what the run is for rather than how much data came back.
A new Stage 0 asks that once, up front: `baseline`, `adoption`, `themes` or
`release` — and two runs with different intents now refuse to diff, the same
refusal the scope gate already made.

### Rule 19, and a count that had already drifted

The confidence evidence lived only in JSON, which by this skill's own
standard means it did not exist. `render_discovery.py` gained `--unlock` and
`--lineage` and four report regions; **rule 19** fails a report that holds
that evidence in the JSON and not in the HTML, that renders a merged `total`
where the two gap counts belong, that disagrees with its own JSON about
either count, or that switches a check off with `not-needed` and no rationale
on record. An unexplained N/A is how a check gets switched off quietly.

`trend.py` opens on the movement rather than a finding count — "Nothing got
worse. Healthy checks went up from 0 to 5." — with the two deltas reported
separately underneath. `--ci` prints one line and exits non-zero **only** on
a regression: a gate that fails an absolute threshold fails the build every
day until somebody deletes it, and a missing baseline is a first run, not a
failure.

The rule count in the summary line was a literal and had already drifted —
it said 17 while eighteen rules ran. It is counted from the list now.

### The audit stops reporting absences it never measured

A run against a 75-component design system was audited finding by finding.
Six of its conclusions were wrong, and every one was wrong in the same
direction: the tool reported an absence where it had a gap. The numbers
below are that repository before and after, from the skill's own Stage 1.

**An existing asset is no longer a missing import.** 186 of 333 unresolved
imports — 56% of the list — were `.png`, `.svg`, `.webp`, `.mp4` and `.jpg`
files that were all on disk. The probe only ever appended *source*
extensions, so `./logo.svg` was looked for at `logo.svg.ts` and
`logo.svg/index.tsx`. An asset spec now resolves to its own literal path and
terminates the walk: reachable, never opened, never scanned for imports it
cannot have. 333 unresolved became 147, and 162 reachable files became 291.

**A checkout of the repository inside itself is not the codebase.**
`.worktrees`, `test-results`, `playwright-report`, `storybook-static`,
`.svelte-kit`, `.nuxt`, `.output`, `.astro`, `.vercel`, `.netlify` and the
Python equivalents are now ignored; `worktrees` and `target` at the
repository root only, because each is a plausible name for a real source
directory one level down. This one is **reported, not reproduced** — the
repository measured here has no such directories, so it is guarded by
`TestGeneratedTreesAreNotScanned` rather than by a before-and-after count,
and no number is claimed for it.

**`--owned` now constrains what an orphan IS.** The owned graph honoured the
scope; the full graph computed orphans over every stylesheet in the tree,
and the full list is what a report cited. Discovery publishes an `orphans`
block split into `owned` and `outside_owned_scope`, with the basis that
produced the split. The out-of-scope half stays visible and stops being a
finding.

**A token module is admitted by the company it keeps AND by where it keeps
it.** In one real `src/tokens/` directory that admitted `colors.js`, `spacing.js` and
`typography.js` and rejected `interaction.js`, `effects.js`,
`componentGeometry.js`, `composition.js` and `visualSystemProfiles.js` —
five reachable modules, imported by the same application, holding between
them the opacity, aspect-ratio, z-index and blur values the run then
reported as zero of. A module in a directory that already holds a confirmed
canonical source is admitted on that evidence and says so in `admitted_by`.
Admission is **not** transitive.

Both signals are required, and the second one was learned the expensive way.
Co-location alone — any directory holding one confirmed token file vouching
for its neighbours — admitted **136 of 154 sources** in a second repository,
including a generated `registry/__index__.tsx` carrying 455 declarations and
an `examples/aria/radio-group-rtl.tsx`. One file in those directories
happened to carry a token-ish name. A directory now has to be *named* for
tokens as well as hold a confirmed source: the name alone is a guess,
co-location alone admits a monorepo, and together they are evidence. The
directory-name list is deliberately short — `styles/` and `lib/` hold
component CSS and everything else.

749 canonical concepts became 1,071 in the first repository, and the second
went from 163 admitted sources to 27.

**No family is a bare zero.** `family_states` applies the rule SKILL.md
already stated: `counted` carries a count, `not-visible` carries **no number
at all**, and `none-used` is the one state that has earned the number 0.
Five families read `0` before and now read: aspect 2, density 4, layer 5,
opacity 2, and blur `not-visible` — because `backdropBlur: spacing[2]` is a
real blur token whose value the reader is right to refuse to invent.

**Identity reads the spelling a token was declared in.** The font-family
selector tested the concept id, which `normalize()` has already lowercased,
so `typography.fontFamily.sans` was stored as `typography.fontfamily.sans`,
the word boundary was gone, and the family the application actually loads
was invisible — the product's typeface was reported as the one in a legacy
JSON export instead. Concepts keep their declared `names` beside the
normalized id. The result is `not-visible` with both candidates shown, which
is what SKILL.md asks for when two equally strong declarations disagree.

**Every concept carries a tier.** 749 carried none, so `tier-integrity` and
`single-source` had no field to read. `tier` and `tier_evidence` are derived
in an order of evidence — a name that states its layer is a declaration, a
reference to another token is structural proof of an alias, a concrete value
with neither is a primitive, anything else stays `untraced`. That
repository: 606 primitive, 230 semantic, 189 component, 46 untraced, with
162 resolved alias edges and 10 that reference a token this run did not find.

**Leakage can now pass.** `near_miss` and `semantic_equivalence` returned the
string `"unmeasured"` unconditionally, and `validate_run` rejects a leakage
grade while semantic equivalence is unmeasured — so a codebase whose every
color already came from its token source could not grade the vital at all,
and no input would ever change the answer. With no literal in any consumer
style nothing can be a near-miss, and with no exact-value candidate no
replacement's semantic role is in question.

**And a token defined twice is a finding.** 87 concepts carried more than one
value — 46 a literal beside an alias, 26 two literals, 15 two aliases — with
`--button-outline-border` defined three times across a stylesheet and two
visual-system profiles. The evidence was recorded per definition and never
surfaced. Three different things live in that list and only a person can
tell them apart: a per-profile variant, a redundant literal, and a real
clash. The run names which shape it is and leaves the judgment — and a
concept whose definitions disagree about the layer is `untraced` rather than
filed by whichever definition the walk reached last.

### One set of rating words a person can read out loud

The ratings were three vocabularies wearing one coat: a school report card
(`pass` / `attention` / `fail`), lab notes (`measured` / `unmeasured` /
`absent`), and a rendering implementation detail (`collapsed` /
`family-only`). `blocked` meant two unrelated things depending on which
field you read it in — your system has a problem, and this audit cannot see
far enough yet — and `not_applicable` and `not-applicable` differed only in
punctuation.

One set now, and each word says whose problem it is:

| Rating | Means |
|---|---|
| `healthy` | Checked, nothing to fix |
| `watch` | Checked, worth a look |
| `needs-work` | Checked, and there are findings in your code |
| `not-visible` | The audit could not see enough to check this |
| `not-needed` | Does not apply here, by decision |

Families rate on the same scale — `counted`, `not-visible`, `none-used` —
and how much of a list is shown is `full` / `short` / `summary`. The
provenance line reads "short list" rather than "collapsed density".

607 replacements across 37 files, applied only to quoted string literals,
attribute values and backticked prose, never to bare identifiers — so
Python's own `pass` and every `test_..._fails` are untouched.

Two things the merge exposed, both fixed here. Capability states had three
values where nothing downstream ever told two of them apart, so `state_rank`
is two levels instead of a dict with a duplicate key. And several value
lists named the merged word twice, which reads as a fourth state that does
not exist.

`examples/shadcn-ui/` is deliberately **not** renamed: rewriting the words in
a finished report would edit a measurement after the fact, which is the one
thing this skill exists to prevent. Its README says so, and says how to tell
what has moved.


### Measured — `naming-coherence` does not need a tool yet

`naming-coherence` is graded by judgment, which principle 7 says is a rule
that drifts. A grammar counter was built to settle it: separator and case
per token name, counted inside each syntax, with a `file:line` per grammar.
It works, 21 tests cover it, and nine mutations were watched going red.

Across twelve repositories with a measurable token layer, the graded signal
fired **zero** times. Every one reported a single grammar. The only run that
ever went red was a mutant written by hand for the purpose. The one real
finding it produced in twelve runs was a spelling pair — `bg` beside
`background` in one stylesheet — which two of the twelve shared because one
inherited the file from the other.

So the tool stays on `feat/naming-coherence-detector`, unmerged. Six hundred
lines to reproduce the answer an agent already reaches by eye, on the vital
this skill twice names as the one that would be buried in a blended score, is
a trade worth refusing. The sample is a real limit on that conclusion: all
twelve are one author's, recent, and written under a house rule that mandates
kebab names. A legacy codebase with two decades of naming in it is the case
that would fire, and none was reachable to test.

Two facts the build turned up, either of which would cost a session to
rediscover:

- Grammars have to be counted **inside** a syntax. A JS identifier cannot
  hold a hyphen, so a system that writes kebab in CSS and camel in a theme
  object has one convention in two languages. Counted across syntaxes, a
  codebase whose 365 custom properties agree with each other grades `fail`
  because four object keys are camel — which grades the language.
- Discovery reports theme objects, DTCG files and scss maps as dotted paths.
  The dots are the structure the value sits in; the name is the **leaf**. Read
  whole, a group named `brand-colors` lends its hyphen to every single-word
  token underneath it, and the file grades `pass` on a grammar none of its
  tokens use.

### Changed — the published tree carries no client identifiers

The repository is public, and five spots in it named a client, its brand
color, or the machine a report was produced on. None were introduced by the
work above; all had been on `main` since the example was first committed.

- A client name in `references/report.md` and `tools/test_discover_tokens.py`.
- That client's brand hex in `assets/report-template.html` and six fixtures.
- `examples/shadcn-ui/report.json` recorded `discovery.repository.root` as an
  absolute path carrying a username and a session UUID.

The example report is 121,727 lines. Re-dumping it to change one value
produced a diff that changed every line, which in a public repository is the
thing people actually read — so it was rebuilt from the original bytes with a
single string replacement, and parsing both trees confirms exactly one
semantic difference. One line changed instead of 121,682.

### Added — the repository runs its own checks

This repository ships a skill whose first rule is that a guard nobody has
watched fail is a guard nobody has tested, and it had no CI. Every merge so
far rested on someone pasting a local run into a pull request.

`.github/workflows/checks.yml` runs, on every push to `main` and every pull
request: the full `unittest` suite, `tools/palette.py`, `tools/taxonomy.py
--check`, and `tools/check_voice.py`. No third-party dependency, on a stock
interpreter — the same constraint the skill itself runs under in the
repositories it audits.

It deliberately does **not** gate `examples/shadcn-ui/`, which would be the
obvious fifth step. That report passes the gate only on the machine that
produced it: rule 16 recomputes brand identity by reading
`discovery.repository.root` off disk, and the audited checkout is not there on
a runner. The local run that appeared to verify the step was reading a
scratchpad tree left over from the session that generated the example — a
green check bought with local state, which is the failure mode this skill
exists to catch. A published report not being independently re-checkable is a
real gap; it is recorded here rather than hidden behind a step that could
never have passed.

### Fixed — an owned scope that excludes the framework entry no longer measures nothing

Found by running the skill against a Vite + React design system whose
registered entry is `index.html` at the repository root.
With `--owned 'src/**'`, `discover_environment.py` reported a healthy
"3 roots, 92 reachable" and `discover_tokens.py` then returned **0 canonical
concepts across 0 reachable sources**. Nothing errored. Every tool that reads
`owned_import_graph.reachable` — token discovery, component adoption, literal
colors — measured nothing, and the run would have graded a design system with
222 tokens as having none.

`owned_seed_roots` was filtered out of `seed_roots`, which is built *before*
the full graph is walked. A root found by convention is still a
`static candidate` at that point and only earns `import-graph verified` once
the walk has proved it, so `src/globals.css` and `src/main.jsx` never entered
the owned list. The only seed root was `index.html`, which is not under
`src/**`, leaving the owned graph with no roots at all.

- `tools/discovery_engine.py` now seeds the owned graph from `product_roots`,
  after the promotion, which is the same list `owned_roots` already used for
  inferred ownership patterns.
- `tools/test_discover_environment.py` gains a test built on that exact shape,
  asserting the owned graph has roots, that `index.html` stays out of it, and
  that token discovery finds the source — the harm was downstream and silent,
  so it is asserted downstream too. Watched it fail first, then mutation-tested
  it: the original bug and a second spelling (narrowing to
  `framework-registered`) both turn it red, and an equivalent no-op mutation
  leaves it green.
- `test_explicit_owned_scope_excludes_unmatched_framework_roots` still passes,
  which is what keeps the fix from over-broadening: an owned scope pointing at
  a directory that does not exist still yields an empty owned graph.

Against that repository, `--owned 'src/**'` alone now discovers 222 concepts
across 7 sources, with 91 owned reachable files and `index.html` correctly
excluded.
### Fixed — a font family declared as a JS token array is no longer invisible

`identity.typography` came back `blocked` — "No concrete reachable font-family
token was confirmed" — on a design system whose typeface is a token. The
declaration was `fontFamily.sans = ['"DM Sans"', 'ui-sans-serif', 'system-ui',
'sans-serif']` in a reachable, canonical JS source, and the concept was
discovered; only the value shape defeated the reader. `concrete_font_family`
treated the literal as one CSS value, so the leading bracket failed the family
name pattern and the whole stack was discarded.

It now unwraps one array layer and lets the first entry answer exactly as it
would in CSS: a stack leading with a generic is still rejected, an unresolved
`var()` is still rejected, and a plain CSS stack is unchanged. Watched red
first, then mutation-tested — reverting the unwrap and dropping the quote strip
each turn it red, and an equivalent condition leaves it green.

Found by running the skill against a Tailwind repository, where a JS token
layer projected into `tailwind.config.js` is the normal shape rather than the
exception.

### Package cleanup

- Removed the superseded reference reports (`assets/reference/`) and the
  implementation-plan and spec files under `docs/`, none of which participate
  in the skill any more; `references/voice.md` and `references/leakage.md`
  now point at `assets/report-template.html` as the one maintained copy
  reference. `examples/shadcn-ui/` stays: it is the only end-to-end report a
  reader can open before running anything.
- Made run comparison view-aware and aligned the renderer's documented
  Snapshot default with its behavior.
- Replaced stale fixture counts and made report provenance show both the
  initial view and rendering density.
- Limited confirmed-source totals to canonical and alias definitions, and
  separated actionable imports from the complete unresolved-reason breakdown.

### Fixed — four things a run against a real repository surfaced

All four were found by driving the pipeline end to end rather than by reading it.

- **A count of one now reads as one.** The strategy section is written for a
  stakeholder and said "1 components with confirmed token usage", "1 active
  framework profiles", "1 confirmed token-definition sources feed 1 styling or
  framework adapters". A `count()` helper carries the noun and the verb, and a
  test asserts no plural noun follows a count of one anywhere in the section.
- **A run that scanned nothing no longer reports zero.** `sync_leakage` wrote
  `exact-value candidate: 0` beside `redundant: unmeasured` when it had opened
  no consumer style at all, so one sentence answered the same question two ways.
  This is rule 4 applied to the skill's own output: zero states the project has
  none, which a run that scanned nothing never established. With
  `consumer_files_scanned` at zero, every tier is `null` and the note says why.
- **Leftover template sample content is its own rule.** The sentinel sweep lived
  inside rule 16, so a report still carrying `a91f4c07` was told it had an
  "identity integrity problem" — which points the reader at the font and brand
  evidence instead of at the region they forgot to fill. Now rule 18, and the
  gate is eighteen rules.
- **An empty trend block is as absent as a missing one.** The stripper tested
  `if not report.get("trend")`, which only catches a missing key; the
  schema-shaped block of nulls a no-baseline run carries is truthy, so the
  section survived carrying the template's own sample comparison — and rule 16
  then caught it, once, on every fresh report. `strip_trend_without_a_baseline`
  decides on the baseline and the movement, not on the key.

One thing that looked like a fifth was not. `start with src / MobileBottomNavigation`
is the deliberate `owner / slug` component-name format, degrading where the owner
is a source directory rather than a package. Left alone.

### Fixed — a standards id is not a finding id

`collect_ids` treated any object with a twelve-character `id` as a finding.
The unification strategy's standards baseline carries two that are twelve
characters and not hex — `dtcg-2025.10` and `semver-2.0.0` — so validate_run
rule 8 reported them as findings the HTML had failed to render. Wrong, and
unreadable to anyone trying to act on it. `collect_ids` now matches the shape
a finding id actually has: `sha1[:12]`, twelve hex characters. Found while
re-integrating the validation gate onto this wave, by a test that went red.

### Three report views

- Added Snapshot, Action Plan, and Evidence as progressive-disclosure views
  over one complete, validated audit.
- Added `--report-view snapshot|action|evidence`, with Snapshot as the default,
  and recorded the selection separately from token-count rendering density.
- Added deep-link promotion, view-aware contents navigation, no-script full
  evidence, and print output that always includes every report section.
- Enforced the view contract for every finished report, not only universal
  discovery runs. No-script output hides inert view controls and authors every
  disclosure open; enhancement restores the intended default state.
- Added a browser-level regression for view switching, deep-link promotion,
  inventory-tab hashes, and before/after-print disclosure restoration.

### Stable component-location rows

- Grouped repeated Top 20 token locations by file and collapsed each file's
  tail after two visible references, while preserving every `file:line` in
  HTML, JSON, and print.
- Added structural validation for the preview and disclosure tail, exact
  `file:line` print output, and singular/plural disclosure labels.

### Evidence-derived unification strategy

- Added the report's final **Unification strategy** section. It selects a
  token-first foundation or token-led hybrid from measured framework,
  delivery, reachability, mode, inventory, and component-adoption facts.
- Added five evidence-derived integration constraints, five target-architecture
  layers, six gated rollout phases, explicit component-replacement limits, six
  guardrails, and five baseline-to-target success measures.
- Added a standards baseline covering the Design Tokens Format Module
  2025.10, CSS Custom Properties Level 1, WCAG 2.2, and Semantic Versioning.
- Added `references/adoption-strategy.md`, deterministic
  `tools/adoption_strategy.py`, and validation rule 17 for JSON/HTML parity,
  standard URLs, rollout order, and evidence freshness.

### Wave 4 — a report can no longer look finished when it isn't

A report handed to a reader with the validation gate never run looked
identical to one that passed it — the only difference was a sentence in a
footnote, easy to skim past. Found live: a run against alfredo-studio
skipped `validate_run.py` entirely, built its own report by hand instead of
through the render pipeline, and was presented as finished until a human
caught the gap by actually reading the "not completed" section.

- `assets/report-template.html` ships a `validation-banner` region, present
  by default, that only `tools/validate_run.py --stamp` can clear — and
  only on a pass. No other tool, and no report generator, writes to it.
- `assets/capability-map.yml` gained `provenance.validation_gate`
  (`passed`, `exit_code`, `checked_at`) — the one field a report must never
  set itself.
- `tools/validate_run.py --stamp`: on a passing run, writes that field and
  replaces the HTML banner with a small "validated, at ‹timestamp›" note.
  A failing run is never stamped, and running without `--stamp` still
  checks status without writing anything.
- `SKILL.md`'s Stage 6 checklist and Stage 7 command both updated: the
  finished report is the one produced by `--stamp` actually passing, not
  the one a plain `validate_run.py` invocation happened to run against.
- Five new tests in `tools/test_validate_run.py` covering: stamp writes on
  pass, banner clears on pass, a failing run is never stamped, no `--stamp`
  leaves the file untouched, and stamping works with no `report.html`
  present. Watched all three of the meaningful ones go red first, against
  a mutation that no-oped the stamp call while still reporting pass.

### Wave 3 — framework-aware discovery, environment adapters, and component/literal-color analysis

A required discovery stage now runs in front of grading. Source discovery
stops matching one filename per framework and instead discovers every
candidate, proves which are reachable from an owned production entry point,
and classifies each as `canonical`, `alias`, `consumer`, `generated`, or
`unverified` before anything is counted. Two blind runs against
shadcn-ui/ui had already agreed on all eight grades and still disagreed on
`files_scanned` (3,686 vs 3,400) and `family_count` (13 vs 24) — the grades
survived, the measurements underneath them did not. The design is recorded in the pull request that introduced it (#14).

Added:

- `tools/discover_environment.py` and `tools/framework_profiles.py` —
  identify the framework and monorepo shape before any source search,
  driven by executable profiles in `assets/framework-profiles.json` rather
  than prose adapter guidance.
- `tools/discover_tokens.py` rewritten to discover every candidate source,
  build an import graph, and deduplicate a definition from its projection
  into one token concept.
- `tools/analyze_component_usage.py` and `tools/render_component_usage.py`
  — rank which components use the confirmed token concepts, with real
  locations and reference syntaxes measured vs. unresolved.
- `tools/audit_literal_colors.py` — literal-color leakage as its own
  auditable stage; exact-value matches stay manual-review candidates until
  semantic equivalence is proven.
- Six adapter references — Next.js, Vite, Storybook, Rails/Sprockets,
  Discourse, and monorepo (`references/adapters/`) — plus
  `references/component-usage.md` and `references/environment-adapters.md`
  documenting the profile contract.
- `tools/render_discovery.py` — merges discovery, capability, and
  component-adoption evidence into the report template deterministically.

Changed:

- `validate_run.py` gained rules covering discovery evidence, reachability,
  component-usage ranking, and literal-color measurement — a report can no
  longer pass by presuming one token file with no discovery evidence
  behind it.
- `SKILL.md` Stage 1 is now required and runs before any inventory or
  grading; Stage 2 (stack detection) narrows to only the adapters the
  recorded environment makes plausible.

No blind-pair run has been logged against this wave the way Waves 1–2
were; the next entry should carry that result.

### Wave 2 — prose, and four rules pinned

Net **-119 words** across `SKILL.md` and `references/`, with a new
499-word reference included. Principle 7 gates growth; this wave shrinks.

Four rules that two runs could read two ways, each found by a blind pair
and each pinned in prose and asked by the fixture:

- **`redundant` requires a named token.** A framework's derived scale is
  one token — the multiplier — and a generated step has no name to swap
  to, so a value only that scale covers is `uncovered`. Runs C and D
  graded `attention` and `fail` on this.
- **The token count excludes by selector scope, never by file.** A
  property under `:root`, a scheme class, `@theme` or a mode media query
  is a token; one inside a component rule or `@utility` block is local
  state. C and D counted 82 and 77 on this.
- **A leakage finding is one distinct literal-to-token pair.**
  Occurrences and files are its blast radius, never the number the grade
  reads. Runs E and F graded `attention` and `fail` on this one word.
- **A framework name the project redeclares at an owned theme root is a
  project token**, counted once however many roots declare it. E and F
  counted 56 and 78 on this.

Added:

- `references/maturity.md` — six stages, each a structural claim derived
  from the eight grades, never a number. A system that satisfies a later
  condition while missing an earlier one is told what it already has.
- A **decisions** region: every close call the run made, what it moved,
  and the other reading. Both runs in every pair had been recording nine
  or ten of these in note fields where no reader saw them.
- **Effort** classes beside every fix-queue entry, derived from
  `safe_to_automate` and file count, never an hour estimate.
- An **at-a-glance** strip above the summary: stage ladder, three
  segmented bars, a ring, and count tiles. Inline SVG and CSS only.
- `tools/test_template_styles.py`, which caught the new strip
  reintroducing two of the sixty inline layout styles wave 1 removed.

Changed:

- Stage 7's terminal summary is five lines — the worst thing, the first
  move, the stage, the confidence split, the path — in place of a list of
  what the report contains.
- Stages 1 and 2 point at `references/discovery.md` rather than restating
  it; the region checklist is one line per region. `SKILL.md` 3,242 → 2,510.
- Repository values are escaped on fill, and `provenance.skill_version` is
  stamped from `tools/version.py`.

**Measurement.** Six blind runs against shadcn-ui/ui at `63c1308` on
2026-09-01, in three pairs. Each pair agreed on seven of eight grades, and
each split on a different unpinned word — the pin from the previous pair
held every time. A fourth pair against the last two pins was in flight when
this merged; its result belongs in the next entry, whichever way it goes.

### Wave 1 — code only, from the 2026-09-01 review

- Every status color clears WCAG AA in every theme, and `tools/palette.py`
  keeps it there. Three of four were below the floor.
- Sixty layout decisions leave the template's markup for a spacing scale.
  282 inline styles to 228, every remaining one data-driven.
- A contents rail, an id on every section, an anchor on every fix-queue
  finding, and a print stylesheet.
- The taxonomy is defined once, in `tools/taxonomy.py`; the Markdown and
  the fixture are tested against it.
- `import_graph.py` resolves workspace packages by name. A real run had
  proved a file reachable that the tool called an orphan.
- One CLI convention across the tools: `--json PATH` everywhere, exit
  codes 0 / 1 / 2 with the same meanings, in `tools/cli.py`.
- `validate_run.py` rule 9: no unescaped repository markup in the report.
  The fixture carries a decoy.
- `tools/version.py` supplies `provenance.skill_version`, which the schema
  required from the start and nothing filled.

### Wave 0

- The README states the current reproducibility result — 7 of 8 and a
  5-token spread — rather than the morning's 8 of 8.

## 0.1.0 — 2026-09-01

The first day. Seven pull requests.

- **#1** Display density — change the mark rather than cutting the data.
- **#2, #3** The README and `SKILL.md` say the skill is still evolving.
- **#4** Framework-aware, evidence-based token discovery: six jobs before
  any counting, an import graph, source classification, a foundational
  taxonomy of nineteen families, and six validation rules as code.
- **#5** An actionable report: executive summary, ranked priority with
  visible inputs, a fix queue, ownership grouping, lineage, a coverage
  matrix, stable finding ids and trend comparison.
- **#6** A spec, "from diagnosis to momentum", recording a critique through
  three design-systems lenses as thirteen sequenced changes.
- **#7** A fixture repository with a golden output, and twenty tests over
  the half of it that needs no language model.

Measured twice against shadcn-ui/ui at `63c1308`: the morning pair agreed
8 of 8 on grades and 114/114 on tokens; the afternoon pair, after #4 and
#5, agreed 7 of 8 and 82/77.
