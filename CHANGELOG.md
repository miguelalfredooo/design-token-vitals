# Changelog

What changed, by version. The skill stamps its version into every report
as `provenance.skill_version`, so a report can be traced back to the rules
that produced it.

## Unreleased

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
survived, the measurements underneath them did not. See
`docs/superpowers/specs/2026-09-01-framework-aware-discovery.md`.

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
