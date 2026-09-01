---
name: design-token-vitals
description: Grade the health of a codebase's design token layer and report what it can and cannot prove about itself. Use when auditing design tokens, checking token adoption, investigating theme or dark-mode bugs, or before adopting a design system. Runs on any web codebase with no setup.
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Design Token Vitals

You are grading a codebase's design token layer against eight fixed vitals
and reporting what you found — with evidence, never an average. Work through
the seven stages below in order.

## Stage 1 — Discover the codebase

Before you count a single token, do the three jobs in
`references/discovery.md`: work out what owns theming, work out what the
project actually authored, and derive the scope those two answers leave
you with. Skip this stage and every stage after it measures the wrong
thing — a coverage grade against the wrong build step, a leakage count
padded with code nobody here can fix, a mode check graded against a
mechanism the project doesn't even run.

Record `discovery.environment`, `discovery.detected_by`,
`discovery.confidence`, `discovery.owned_paths`, and
`discovery.excluded_paths` (each with its reason) in
`assets/capability-map.yml`'s schema before moving on.

If the derived scope is ambiguous — more than one app in a monorepo
plausibly qualifies — or the environment doesn't match anything in
`references/discovery.md`'s table, say so to the reader before continuing.
Proceeding on a guess here is exactly the failure mode this stage exists
to prevent.

## Stage 2 — Detect the stack

Match the repository against `references/adapters/css-vars.md`,
`references/adapters/tailwind.md`, `references/adapters/scss.md`, and
`references/adapters/dtcg.md`, using each file's own Detection section.
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

Five status values only: `pass`, `attention`, `fail`, `blocked`,
`not_applicable`. Attach at least one real `file:line` to every grade that
reports a finding. A clean `pass` and a `blocked` check may carry an empty
evidence list instead, with a note explaining why — there is nothing to
point at when nothing was found, or when the check could not run. A vital
with a count and no reachable instance is `blocked`, never `fail` —
silence is not evidence.

## Stage 5 — Choose the rendering tier

Count the tokens the stack detected and choose the tier from
`references/report.md`: under 150 tokens is `full`; 150 to 600 inclusive is
`collapsed`; over 600 is `family-only`. A count of exactly 150 is
`collapsed`; a count of exactly 600 is `collapsed`. Record the tier in
`assets/capability-map.yml`'s `rendering.tier`.

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

- [ ] `doc-title` — the project name and the short commit ref, using the
      same "`<repo>` @ `<short-sha>`" pattern as `runhead-tag`.
- [ ] `runhead-tag` — ships reading "Sample report · representative data";
      replace it with something that names the actual subject (for example
      "Live report · `<repo>` @ `<short-sha>`") so a real run always
      carries the subject it describes.
- [ ] `runhead-meta`
- [ ] `vitals-grid`
- [ ] `next-steps` — the ranked next-actions list; derive it using the
      order defined in "Deriving the next-steps list" in
      `references/report.md`.
- [ ] `inventory-color`
- [ ] `inventory-type`
- [ ] `inventory-space`
- [ ] `families`
- [ ] `leak-redundant`
- [ ] `leak-near-miss`
- [ ] `leak-uncovered`
- [ ] `modes-coverage`
- [ ] `modes-gaps`
- [ ] `orphans`
- [ ] `enforcement`
- [ ] `measurement` — the token sources and count, the analysis scope and
      files searched, the adapters used and their confidence, any
      framework version consulted, and the environment, what proved it,
      and the owned and excluded paths from Stage 1, all read back from
      `assets/capability-map.yml`.
- [ ] `footer-meta`

For a generated sentence, use the slot templates in `references/voice.md`
verbatim, filling only the named placeholders. For a vital card, set its
`data-grade` attribute and its nested chip's `data-g` attribute from one
grade value, in one place — never compute them separately. Set a family
row's `.pip[data-s]` the same way, from the one grade value that vital
earned for that family. A card whose stripe and chip disagree, or a pip
that disagrees with the card it summarizes, is exactly the drift this
skill exists to catch.

### Completeness check — required before writing the report

This skill asserts things about other people's codebases. Before writing
`.token-vitals/report.html`, verify these are all true of the file you are
about to write. If any fails, fix it and check again — do not write the
report while one of these is still failing:

- No region still holds template sample content. The tell-tale strings are
  `northwind-ds`, `acme-storefront`, `Sample report · representative
  data`, `7f0c22ab`, `a91f4c07`, `color.primitive.json`, `src/**/*.{ts,tsx}`.
- Every `SLOT` region present in the file (after tier removal) has real
  content between its markers — none are empty.
- Every vital card's `data-grade` matches its chip's `data-g`.
- The leading instruction comment is gone.

## Stage 7 — Write the outputs

Write `.token-vitals/report.html` (from Stage 6) and `.token-vitals/report.json`
(the filled-in `assets/capability-map.yml` schema, as JSON). The HTML report
is the deliverable — it is what a stakeholder opens, reads, and acts on.

Then print a short terminal summary that points at the report rather than
standing in for it: the tier chosen, the count of vitals at each grade, the
token count and the number of files leakage searched, the single action
worth doing first from `next-steps`, and the report's path. Tell the user
what the report itself contains, so the summary reads as a
pointer, not a replacement: the eight vitals, the rendered token
inventory, the three leakage tiers, mode coverage, orphans, enforcement,
the "Where to start" section ranking what to do first, and the "How this
was measured" section recording what this run counted, scanned, and
checked.

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
