# Changelog

What changed, by version. The skill stamps its version into every report
as `provenance.skill_version`, so a report can be traced back to the rules
that produced it.

## Unreleased

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

**Measurement.** Eight blind runs against shadcn-ui/ui at `63c1308` on
2026-09-01, in four pairs: 8 of 8, then 7, then 7, then 6. The fourth pair
was in flight when wave 2 merged and came back worse, so the result is
recorded here as promised.

Seven vitals have been stable across every pair. Leakage split in all four,
each time on a different unwritten question, and the pin from each pair
held on the next one. G and H both applied all four pins correctly and then
split on the fifth question along the same axis: whether a framework's
**named** tokens — Tailwind's `--container-xs`, `--radius-xs`, its palette —
are part of your system for the purpose of a redundant finding. G said the
project's own roles only; H said any named token the framework ships. That
is 3 findings against 12, and `attention` against `fail`.

G and H also split on `coverage` for the first time, which is downstream of
the same question: a category a framework's named tokens cover reads as
present to one run and missing to the other.

The lesson is not that another word needs pinning. Four pins in a row have
each held and each revealed the next, which says the question is
structural: **the skill has never defined whose token layer it is grading**
when a framework ships one and the project extends it. That belongs in a
design decision, not another sentence, and it is the next piece of work.

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
