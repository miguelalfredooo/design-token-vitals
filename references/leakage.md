# Leakage

This file is the depth behind the `leakage` vital in `references/vitals.md`.
It defines how a hardcoded value in your codebase gets found, and which of
three tiers it lands in once found.

## Why tiering, not just counting

Counting every hardcoded value in your codebase punishes correct code along
with the real findings. A 1px hairline rarely needs a token — the value is
too small for a scale to cover usefully, and forcing one into existence adds
a token nobody else will reuse. What matters is not that a value is
hardcoded. What matters is whether your token system already offered a
token for that exact concept and the code went around it anyway. Tiering
separates those two situations so you can act on the first without wading
through the second.

## Classifying a finding

Classify a finding with an ordered cascade. Evaluate the three tiers in this
order, and the first one that matches wins:

1. If the value exactly matches any token in your system, classify it
   `redundant`. An exact match always wins, even when the value also sits
   within the near-miss threshold of a different token.
2. Otherwise, if the value falls within the near-miss threshold of any token
   in the same category, classify it `near-miss`, reported against the
   single closest token.
3. Otherwise, classify it `uncovered`.

| Tier | Condition | What it means | Fix owner |
|---|---|---|---|
| `redundant` | An exact match to a token exists | Someone bypassed the system | Component author — mechanical, no discussion |
| `near-miss` | No exact match, but a token sits within the near-miss threshold | Value drift: invisible to search and to code review | Design — reconcile or accept |
| `uncovered` | No token exists for this concept | A hole in the token layer | System owner — add the token |

`redundant` is the tier `leakage`'s grading reads from — see
`references/vitals.md` — since it is the count you can act on immediately: a
grep-and-replace with no design decision attached. `near-miss` and
`uncovered` still get reported, with at least one real `file:line` per tier,
but they call for your judgment rather than a mechanical fix, so they do not
drive the pass/attention/fail line.

A `redundant` finding means the value already had a name it could carry in
your token system — nothing stopped the component author from using it
except that the token was not top of mind at the moment of writing. Tokens
exist to make exactly this kind of gap cheap to fix, once you can see it.

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
  Flag values **2px or less** from a step, and only where the step itself is
  **4px or larger** — a scale stepping by 2px would flag nearly every value
  near it, so the threshold only applies once your scale's own granularity
  makes a 2px gap meaningful.
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

Never grade three kinds of value, declared or not:

- A `1px` hairline.
- An optical nudge — a value chosen to correct how something looks rather
  than to express a design decision.
- A value inside a file your repository has marked exempt.

## Ranking

Rank findings with a total order, applying these keys in sequence until one
of them breaks the tie:

1. Blast radius — the count of files the value affects — descending.
2. Tier, in this order: `redundant`, `near-miss`, `uncovered`.
3. Nearest token name, ascending. An `uncovered` finding has no token by
   definition, so it always sorts after every finding that has one.
4. The literal value itself, ascending.
5. Representative file path, ascending.
6. Line number, ascending.

This is a total order: two findings identical on all six keys are the same
finding. Nothing about your codebase can leave two distinct findings tied
all the way down, so a re-run of the report always shows you the same
order.

`assets/reference/small.html` renders all three tiers as tables, one row
per finding, inside the Leakage section. `assets/reference/large.html`
shows the same three tiers ranked by blast radius, truncated to the largest
few with a summary line for the rest — the shape your report takes once
your codebase has too many findings to show in full.
