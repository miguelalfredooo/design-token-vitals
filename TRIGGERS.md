# Triggers — design-token-vitals

This skill grades the health of a codebase's design token layer and reports what
it can and cannot prove about itself.

**Why this file exists.** A description says what a skill is for; only a list of
prompts says what it is NOT for, and the second list is the one that keeps
neighbouring tools from eating each other's work. Both sets are data rather than
prose, so "we have exclusions" stops being a claim anyone has to take on trust.

## Should fire

| Prompt | Why this skill |
|---|---|
| `audit our design tokens` | the eight vitals are exactly this, graded and ranked |
| `how much of our codebase actually uses tokens` | adoption is a vital, measured rather than estimated |
| `we have a dark-mode bug and cannot find it` | a theme bug is usually a token declared in one tier and not the other, which stage 4 reads directly |
| `is this design system worth adopting` | the report says what it can and cannot PROVE, which is the question behind that one |
| `why do these two components look slightly different` | a raw value where a token exists is the usual cause, and it is counted |
| `grade our token layer before the redesign` | a baseline that later runs can be compared against |

## Should not fire

Each row names what owns the request instead. An exclusion with no destination
is a refusal, not a routing decision.

| Prompt | Goes to | Why not this skill |
|---|---|---|
| `does this component match its contract` | `component-contract` — its own public repo | that is one component against its own declared promise; this grades a whole token LAYER and knows nothing about a component's options or defaults |
| `build me a button` | a component-building skill or your own system's guidance | this measures what exists and never authors a component |
| `does this look any good` | a design-critique review, human or otherwise | every vital here is a number; taste is not one, and a grade must not be read as an aesthetic verdict |
| `pick our brand colours` | a brand or identity process | this reads the palette a project already declares and has no opinion on what it should be |

## Predictions

Written BEFORE the run, so the run can contradict them. A trigger set nobody has
tried is a guess about routing, and a guess that is never checked is indisputable
for the wrong reason — the same defect as a guard nobody has watched fail.

**Three the skill should answer**

| Prompt | Predicted outcome |
|---|---|
| `audit our design tokens` | fires; grades the eight vitals and states what it could not measure rather than scoring it as zero |
| `how much of our codebase actually uses tokens` | fires; reports adoption as a measurement with its denominator named |
| `we have a dark-mode bug and cannot find it` | fires; looks at tier parity before anything else |

**Three it should decline and route**

| Prompt | Predicted outcome |
|---|---|
| `does this component match its contract` | does NOT fire; hands off to component-contract |
| `build me a button` | does NOT fire; hands the request to a component-building skill |
| `does this look any good` | does NOT fire; routes to a design-critique review |
