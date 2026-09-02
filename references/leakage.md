# Leakage

This file is the depth behind the `leakage` vital in `references/vitals.md`.
It defines how a hardcoded value in your codebase gets found, and which of
four evidence tiers it lands in once found.

## Why tiering, not just counting

Counting every hardcoded value in your codebase punishes correct code along
with the real findings. A 1px hairline rarely needs a token — the value is
too small for a scale to cover usefully, and forcing one into existence adds
a token nobody else will reuse. What matters is not that a value is
hardcoded. What matters is whether your token system already offered a
token for that exact concept and the code went around it anyway. Tiering
separates those two situations so you can act on the first without wading
through the second.

## Where to search

Search the project's own UI source files inside the declared analysis
scope — the globs or directories the run recorded before scanning. Exclude:

- **The token source files themselves.** A declaration is a definition,
  not a leak — see "What counts as a token" in `references/vitals.md` for
  what a token source is.
- **Test files, fixtures, and snapshots.** They exercise behavior; they do
  not ship it.
- **Generated or build output, and vendored or `node_modules` code.**
  Nobody edits these by hand, so a finding there has no fix owner.
- **Any path the project has declared exempt.**

Record the number of files searched and the scope glob in the report —
`run.files_scanned` and `run.scope` in `assets/capability-map.yml`. A run
reporting zero leaks must still report how many files it searched: zero
findings from an unstated scope proves nothing, and a reader has no way to
tell "nothing wrong" from "nothing looked."

## Classifying a finding

Classify a finding with an ordered cascade. Evaluate the four tiers in this
order, and the first one that matches wins:

1. If the value exactly matches a **named** token and the consumer's semantic
   role is proven to match that token's role, classify it `redundant`.
   Semantic proof can come from an existing alias/utility mapping, an
   equivalent consumer in the same component contract, or an explicit
   repository declaration. Value equality by itself is not semantic proof.
2. If the value exactly matches a named token but semantic equivalence is
   not proven, classify it `exact-value candidate`. An exact-value match
   always wins over near-miss, even when the value also sits within the
   near-miss threshold of a different token. Named means a
   token the author can type in place of the value: `--space-4`, `$blue-500`.
   A framework's derived scale is one token — the multiplier — and a step
   generated from it has no name to swap to, so a value that only that
   scale would cover is `uncovered`, never `redundant`. Two runs graded
   leakage `attention` and `fail` on this one question; this settles it.
3. Otherwise, if the value falls within the near-miss threshold of any token
   in the same category, classify it `near-miss`, reported against the
   single closest token.
4. Otherwise, classify it `uncovered`.

| Tier | Condition | What it means | Fix owner |
|---|---|---|---|
| `redundant` | Exact value and semantic role both match a token | The token existed and is proven equivalent here | Component author — verified mechanical change |
| `exact-value candidate` | Exact value matches, semantic role is unresolved | A possible replacement that may encode a different decision | Component and system owners — verify intent |
| `near-miss` | No exact match, but a token sits within the near-miss threshold | Value drift: invisible to search and to code review | Design — reconcile or accept |
| `uncovered` | No token exists for this concept | A hole in the token layer | System owner — add the token |

`redundant` is the tier `leakage`'s grading reads from — see
`references/vitals.md` — since it is the count backed by both value and
semantic evidence. `exact-value candidate`, `near-miss`, and `uncovered`
still get reported, with at least one real `file:line` per tier, but they
call for judgment rather than a mechanical fix, so they do not drive the
pass/attention/fail line.

A `redundant` finding means the value already had a name for the same
decision in the token system. An `exact-value candidate` means only that
the numbers match. For example, white text, a white canvas, and a third-party
brand mark may share `#fff` without being interchangeable. Never promote a
candidate to `redundant` from value equality alone.

## Near-miss math

A near miss only counts as a finding when it clears a stated threshold — not
"a small delta," but the number below, per category.

- **Color:** compute CIEDE2000 ΔE between the literal and every token in the
  same category. Flag anything under **ΔE 3.0**. Report the value to one
  decimal place. Below ΔE 2, the difference is invisible to most people —
  which is exactly why this kind of drift survives code review: nobody
  looking at the screen can see the gap, only a tool comparing the numbers
  can.
- **Dimension:** compute the absolute distance to the nearest scale step.
  Flag a value that sits **2px or less** from a step, but only where
  **adjacent steps in that scale are themselves spaced 4px or more apart**.
  The comparison is between neighboring steps in the scale — never between
  the step's own numeric value and 4px. Where steps sit closer together
  than 4px, a 2px difference identifies a different step, not drift, so
  the value is uncovered or exact, never near-miss, on a scale that tight.

  Worked examples:
  - Scale `4, 8, 12, 16` (adjacent steps are 4px apart, so the threshold
    applies). A literal `13px` sits 1px from the `12px` step, well within
    the 2px threshold, so — absent an exact match elsewhere — it is
    `near-miss` against `12px`.
  - Scale `2, 4, 6, 8` (adjacent steps are only 2px apart, so the threshold
    does **not** apply). A literal `5px` sits 1px from both `4px` and
    `6px`; on this scale that gap is the normal distance between
    legitimate steps, not drift. `5px` falls through to `uncovered` — it
    does not exactly match a step, and near-miss cannot fire on a scale
    this tight.
- **Duration:** flag a literal **within 50ms** of a motion token.

When a value sits within the near-miss threshold of more than one token in
the same category, report it against the single closest one — the smallest
ΔE, the smallest pixel distance, or the smallest millisecond gap.

A value that clears none of these thresholds, and does not exactly match a
token either, is `uncovered` — per the cascade above, it has run out of
tiers that would explain it as an existing token used slightly wrong.

## Category weighting

When you choose what to show first in a report, order categories by
consequence, highest first:

1. **color** — breaks theming outright; a color that skips your token layer
   cannot follow a mode switch.
2. **motion** — timing and easing drift are felt before they are seen.
3. **elevation** — shadow and layering values compound visibly when they
   disagree.
4. **z-index** — a magic number here can collide with another magic number
   nobody meant to compare against it.
5. **typography** — visible, but usually caught the first time you look at
   the screen.
6. **breakpoint** — narrow blast radius; a mismatch shows up at one
   viewport width.
7. **dimension** — grade last and gently. This category is the noisiest and
   the most exception-prone: spacing and sizing values have the most
   legitimate one-off reasons to sit outside your scale, so a dimension
   finding needs more scrutiny per instance, not less.

## Escape hatches

A declared exception clears a hardcoded value as a finding — one with a
named owner and a review date on record, wherever your codebase keeps that
kind of note. A declared exception says your token system considered this
value and chose not to cover it yet, on purpose, with someone accountable
for revisiting it. An undeclared exception is still a finding: the absence
of an owner and a date is what tells you nobody has actually decided this
value should stay hardcoded.

Never grade four kinds of value, declared or not:

- A `1px` hairline.
- An optical nudge — a value chosen to correct how something looks rather
  than to express a design decision.
- A value inside a file your repository has marked exempt.
- A literal inside a selector that matches markup you do not control — for
  example `[stroke='#ccc']` targeting a charting library's DOM. The literal
  has to match a string that library emits, so tokenizing it would break
  the match.

## Ranking

Rank findings with a total order, applying these keys in sequence until one
of them breaks the tie:

1. Blast radius — the count of files the value affects — descending.
2. Tier, in this order: `redundant`, `exact-value candidate`, `near-miss`,
   `uncovered`.
3. Nearest token name, ascending. An `uncovered` finding has no token by
   definition, so it always sorts after every finding that has one.
4. The literal value itself, ascending.
5. Representative file path, ascending.
6. Line number, ascending.

This is a total order: two findings identical on all six keys are the same
finding. Nothing about your codebase can leave two distinct findings tied
all the way down, so a re-run of the report always shows you the same
order.

`assets/reference/small.html` renders the tiers as tables, one row
per finding, inside the Leakage section. `assets/reference/large.html`
shows the same tiers ranked by blast radius, truncated to the largest
few with a summary line for the rest — the shape your report takes once
your codebase has too many findings to show in full.
