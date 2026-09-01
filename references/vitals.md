# The eight vitals

Every report grades eight checks against your token system. Each one gets
its own verdict, pulled from real evidence in your repository — never a
guess and never an average.

## Grading vocabulary

- `pass` — checked, nothing to fix
- `attention` — worth a look, not urgent
- `fail` — real problems with a clear fix
- `blocked` — could not check this one
- `not_applicable` — does not apply to this setup

Five status values, and that is the full set — no fractional grade and no
extra label sits between them.

There is no composite score. Averaging these hides the one finding that
matters: a system with 1,645 leaked values and perfect naming would land in
the middle of a blended number, and the leakage is what you needed to see
first. If your setup has no dark mode, mode completeness is
`not_applicable` on that mode rather than counted against you. If a check
could not run — no CI config to read, no build output to scan — it is
`blocked`, never averaged in as a silent pass.

Each vital below has four parts: **Catches** (what it looks for), **Signal**
(what gets counted), **Grading** (the thresholds that produce a verdict),
and **Evidence** (the real instance backing that verdict).

## tier-integrity

**Catches:** components reaching past your semantic layer to grab a
primitive-tier name or a raw value directly, skipping the layer built to
carry meaning.

**Signal:** the count of component styles that reference a primitive-tier
token or a literal value where a semantic token already covers that case.

**Grading:** `pass` when zero component styles skip the semantic layer;
`attention` from one skip up to and including 5% of component styles;
`fail` above 5%.

**Evidence:** at least one real `file:line` where a component style reaches
past the semantic tier — for example `bg-neutral-800` in a component that
has `--surface-raised` available. A vital with a count and no reachable
instance is graded `blocked`, never `fail`.

## leakage

**Catches:** hardcoded values in code where a token was already available
to express the same thing.

**Signal:** see `references/leakage.md` for how findings are classified —
redundant (an exact match to an existing token), near miss (close to a
token without matching it), and uncovered (no token exists yet).

**Grading:** driven by the redundant tier, since that is the count you can
act on immediately: `pass` at zero redundant findings; `attention` from 1
to 10 inclusive; `fail` at 11 or more.

**Evidence:** at least one real `file:line` per tier reported. A vital with
a count and no reachable instance is graded `blocked`, never `fail`.

## coverage

**Catches:** whole categories of design decision with no tokens defined at
all, which forces every value in that category to be hardcoded by
necessity rather than by oversight.

**Signal:** presence per category, checked against eleven: color,
typography, space, size, radius, border, elevation, motion, z-index,
opacity, breakpoint.

**Grading:** `pass` at 11 of 11 categories present; `attention` at 8–10;
`fail` below 8.

**Evidence:** at least one real `file:line` for a missing category — the
first place a value in that category appears hardcoded, since the category
itself has no token to point at. A vital with a count and no reachable
instance is graded `blocked`, never `fail`.

## mode-completeness

**Catches:** a token defined in one mode and silently missing in another —
the gap does not error at build time, it falls back to the other mode's
value and ships wrong.

**Signal:** the set difference across mode blocks, computed per declared
mode.

**Grading:** `pass` at 0 gaps; `fail` at any gap in a declared mode;
`not_applicable` for a mode you have not declared, so an undeclared mode is
never counted against you.

**Evidence:** at least one real `file:line` naming the token and the mode
it is missing from. A vital with a count and no reachable instance is
graded `blocked`, never `fail`.

## naming-coherence

**Catches:** more than one naming grammar living inside a single token
system, which means knowing one token's name tells you nothing about how
to guess another's.

**Signal:** the count of distinct segment patterns across all token names —
for example `--btn-pad-x` and `--button-padding-inline` naming the same
kind of thing two different ways.

**Grading:** `pass` at one grammar; `attention` at two; `fail` at three or
more. A second grammar that belongs to one named legacy family — tokens
carried over from before a naming convention existed — is worth calling
out by name in the finding, but it does not change the grade: two grammars
is `attention` either way, because the count is still bounded and a reader
can hold two patterns in their head.

**Evidence:** at least one real `file:line` per grammar found. A vital with
a count and no reachable instance is graded `blocked`, never `fail`.

## single-source

**Catches:** the same design concept defined in more than one place, which
opens the door for the definitions to drift out of agreement with each
other.

**Signal:** the count of independent definition sites per concept, and
whether those sites currently agree.

**Grading:** `pass` at 1 site; `attention` if duplicated but every site
still agrees; `fail` if any duplicated site disagrees with another.

**Evidence:** at least one real `file:line` per definition site for a
duplicated concept. A vital with a count and no reachable instance is
graded `blocked`, never `fail`.

## orphans

**Catches:** tokens that are defined but that nothing in the codebase
references — they make the system look bigger and more capable than it
is, and they are safe to delete once you can see they are unused.

**Signal:** defined tokens minus referenced tokens.

**Grading:** `pass` below 2% orphaned; `attention` from 2% up to and
including 10%; `fail` above 10%.

**Evidence:** at least one real `file:line` where the orphaned token is
defined. A vital with a count and no reachable instance is graded
`blocked`, never `fail`.

## enforcement

**Catches:** whether any of the other seven vitals could regress without
anyone noticing — a system with no guardrail can drift right back to where
it started the day after a report is read.

**Signal:** lint rules and CI gates that actually read tokens, rather than
rules that exist for unrelated reasons.

**Grading:** `pass` at 2 or more such rules; `attention` at 1; `blocked` at
0 — with nothing in place, there is nothing to verify as protected, so this
is the one vital where the worst outcome is `blocked` rather than `fail`.

**Evidence:** at least one real `file:line` for each rule counted — the
lint rule definition or the CI step that runs it. A vital with a count and
no reachable instance is graded `blocked`, never `fail`.

## Held for a later release

**Contrast guarantees.** Grading contrast needs a declared WCAG target,
and most repositories scanned so far do not have one on record. Without a
target to check against, a contrast ratio is just a number with nothing to
compare it to.

**Lifecycle and deprecation.** Tracking a token's deprecation path only
means something once a system has consumers who could be broken by a
change to it. A freshly introduced token system has no lifecycle to
report on yet.
