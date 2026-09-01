# Changelog

What changed, by version. The skill stamps its version into every report
as `provenance.skill_version`, so a report can be traced back to the rules
that produced it.

## Unreleased

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
