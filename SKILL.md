---
name: design-token-vitals
description: Grade the health of a codebase's design token layer and report what it can and cannot prove about itself. Use when auditing design tokens, checking token adoption, investigating theme or dark-mode bugs, or before adopting a design system. Runs on any web codebase with no setup.
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Design Token Vitals

You are grading a codebase's design token layer against eight fixed vitals
and reporting what you found — with evidence, never an average. Work through
the six stages below in order.

## Stage 1 — Detect the stack

Match the repository against `references/adapters/css-vars.md`,
`references/adapters/tailwind.md`, `references/adapters/scss.md`, and
`references/adapters/dtcg.md`, using each file's own Detection section.
More than one adapter can apply at once — Tailwind sits on top of custom
properties in most repositories, and both should run.

Record `stack.adapter`, `stack.detected_by` (the filename or config key that
proved it), and `stack.confidence` in `assets/capability-map.yml`'s schema.
If nothing matches, do not guess: interview the user about where their
tokens live and how modes are expressed, then record what they tell you with
confidence `interviewed`. A wrong guess costs more than an admitted gap —
it grades code against a system that was never there.

## Stage 2 — Read what the project declares

Read the repository for its declared modes, categories, and accessibility
target — never assume a standard. This is the step that decides, later,
whether a missing high-contrast mode is `fail` or `not_applicable`: a mode
the project never declared cannot be missing from it. Record these under
`declared` in the capability map before grading anything.

## Stage 3 — Grade the eight vitals

Grade each vital in `references/vitals.md` — tier-integrity, leakage,
coverage, mode-completeness, naming-coherence, single-source, orphans,
enforcement — against the stack and declarations from Stages 1 and 2. For
leakage, classify every hardcoded value through the cascade in
`references/leakage.md`: `redundant`, `near-miss`, then `uncovered`, in that
order, and rank findings by the six-key total order there.

Five status values only: `pass`, `attention`, `fail`, `blocked`,
`not_applicable`. Attach at least one real `file:line` to every grade. A
vital with a count and no reachable instance is `blocked`, never `fail` —
silence is not evidence.

## Stage 4 — Choose the rendering tier

Count the tokens the stack detected and choose the tier from
`references/report.md`: under 150 tokens is `full`; 150 to 600 inclusive is
`collapsed`; over 600 is `family-only`. A count of exactly 150 is
`collapsed`; a count of exactly 600 is `collapsed`. Record the tier in
`assets/capability-map.yml`'s `rendering.tier`.

## Stage 5 — Fill the template

Copy `assets/report-template.html` to `.token-vitals/report.html`. Remove
every element whose `data-tier` list excludes the chosen tier. Replace the
contents of each `<!-- SLOT:name --> … <!-- /SLOT:name -->` region with real
findings, leaving every other line of the template — headings, ledes,
legend, panel titles — unchanged. One exception: the `.sampletag` span next
to the `<h1>` ships reading "Sample report · representative data" and sits
outside every named region, but it must never survive into a real run —
replace its text with something that names the actual subject (for example
"Live report · `<repo>` @ `<short-sha>`") even though it has no `SLOT`
comment of its own.

For a generated sentence, use the slot templates in `references/voice.md`
verbatim, filling only the named placeholders. For a vital card, set its
`data-grade` attribute and its nested chip's `data-g` attribute from one
grade value, in one place — never compute them separately. A card whose
stripe and chip disagree is exactly the drift this skill exists to catch.

## Stage 6 — Write the outputs

Write `.token-vitals/report.html` (from Stage 5), `.token-vitals/report.json`
(the filled-in `assets/capability-map.yml` schema, as JSON), and a short
terminal summary: the tier chosen, each vital's grade, and the one thing
worth doing first. Tell the user the report path and that one next step.

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
