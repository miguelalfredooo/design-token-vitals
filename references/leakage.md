# Leakage

The depth behind the `leakage` vital in `references/vitals.md`. This file
defines how a hardcoded value gets found, and which of three tiers it lands
in once found.

## Why tiering, not just counting

Counting every hardcoded value in a codebase punishes correct code along
with the real findings. A 1px hairline rarely needs a token — the value is
too small for a scale to cover usefully, and forcing one into existence adds
a token nobody else will reuse. What matters is not that a value is
hardcoded. What matters is whether the system already offered a token for
that exact concept and the code went around it anyway. Tiering separates
those two situations so a reader can act on the first without wading through
the second.

## The three tiers

| Tier | Condition | What it means | Fix owner |
|---|---|---|---|
| `redundant` | A token holds this exact value | Someone bypassed the system | Component author — mechanical, no discussion |
| `near-miss` | Within a small delta of a token | Value drift: invisible to search and to code review | Design — reconcile or accept |
| `uncovered` | No token exists for this concept | A hole in the token layer | System owner — add the token |

`redundant` is the tier `leakage`'s grading reads from — see
`references/vitals.md`, since it is the count you can act on immediately: a
grep-and-replace with no design decision attached. `near-miss` and
`uncovered` still get reported, with at least one real `file:line` per tier,
but they call for a person's judgment rather than a mechanical fix, so they
do not drive the pass/attention/fail line.

A `redundant` finding means the value already had a name it could carry —
nothing stopped the component author from using it except that the token
was not top of mind at the moment of writing. Tokens exist to make exactly
this kind of gap cheap to fix, once someone can see it.

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
  near it, so the threshold only applies once the scale's own granularity
  makes a 2px gap meaningful.
- **Duration:** flag a literal **within 50ms** of a motion token.

A value outside these thresholds belongs to one of the other two tiers: it
either matches a token exactly (`redundant`) or sits far enough from every
token to mean something different (`uncovered`).

## Category weighting

When a report has to choose what to show first, order categories by
consequence, highest first:

1. **color** — breaks theming outright; a color that skips the token layer
   cannot follow a mode switch.
2. **motion** — timing and easing drift are felt before they are seen.
3. **elevation** — shadow and layering values compound visibly when they
   disagree.
4. **z-index** — a magic number here can collide with another magic number
   nobody meant to compare against it.
5. **typography** — visible, but usually caught the first time a designer
   looks at the screen.
6. **breakpoint** — narrow blast radius; a mismatch shows up at one viewport
   width.
7. **dimension** — grade last and gently. This category is the noisiest and
   the most exception-prone: spacing and sizing values have the most
   legitimate one-off reasons to sit outside the scale, so a dimension
   finding needs more scrutiny per instance, not less.

## Escape hatches

A declared exception clears a hardcoded value as a finding — one with a
named owner and a review date on record, wherever the codebase keeps that
kind of note. A declared exception says the token system considered
this value and chose not to cover it yet, on purpose, with someone
accountable for revisiting it. An undeclared exception is still a finding:
the absence of an owner and a date is what tells you nobody has actually
decided this value should stay hardcoded.

Never grade three kinds of value, declared or not:

- A `1px` hairline.
- An optical nudge — a value chosen to correct how something looks rather
  than to express a design decision.
- A value inside a file the repository has marked exempt.

## Ranking

Order findings by blast radius — the count of files a value affects —
descending. Where two findings tie on blast radius, break the tie by token
name, ascending. The tiebreak is what keeps the order deterministic: without
it, two findings with the same blast radius could swap positions on a
re-run for no reason a reader could see, and the report would look like it
was reshuffling for no reason.

`assets/reference/small.html` renders all three tiers as tables, one row per
finding, inside the Leakage section. `assets/reference/large.html` shows the
same three tiers ranked by blast radius, truncated to the largest few with a
summary line for the rest — the shape a report takes once a codebase has too
many findings to show in full.
