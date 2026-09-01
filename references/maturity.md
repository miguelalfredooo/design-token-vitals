# The maturity trajectory

Eight grades say where a system stands. This says where it is going and
what the next move is.

## Never a score

A stage is a structural claim: a thing that is true of the system or is
not. It is never rendered as a number, a percentage, `3 of 6`, or a
progress bar, and it is never averaged with anything. A number buries the
finding that matters; a stage names one fact and points at one threshold.
If you find yourself wanting a fraction, render the threshold instead.

## The stages

| Stage | What is true | Threshold to leave it |
|---|---|---|
| `scattered` | No token layer the product actually loads | One canonical source, reachable from an owned production entry point |
| `declared` | Tokens exist and ship, and components go around them | `leakage` out of `fail`, with `redundant` cleared |
| `adopted` | Components use the tokens | `tier-integrity` out of `fail` — components reach for roles over primitives |
| `layered` | A semantic layer exists and holds | `mode-completeness` and `coverage` both graded, and neither at `fail` |
| `complete` | Every declared mode resolves, every declared family has tokens | `enforcement` passing |
| `held` | Nothing above can regress without someone being told | — |

Each threshold is derived from the eight vitals, so a reader can check the
stage against the grades rather than take it on trust.

## The ladder is ordered, and a system is not

A system can satisfy a later condition while missing an earlier one — a
semantic layer no component uses is `declared` with the `layered`
condition already met. **Report the earliest unmet stage, and name what the
system already has:**

> You are at `declared`. Components go around the tokens in 84 files, so
> adoption is the gap. You already satisfy the `layered` condition — the
> semantic layer is there and waiting.

That is credit for real work rather than a demotion, and it points at the
one thing that unblocks the most.

The ordering is an opinion, stated here: adoption before layering, because
a semantic layer nothing uses is worth less than primitives everything
uses; enforcement last, because holding a system at `scattered` holds
nothing.

## Three vitals gate nothing

`naming-coherence`, `single-source` and `orphans` describe how tidy a
system is rather than how far along it is. A system at `held` can carry
two names for one color. They stay graded and never move the stage, and
the report says so, so `orphans: attention` beside an unmoved stage reads
as intended.

## What the report says

In the executive summary, above the four questions, one line:

> **`declared`** — tokens exist and ship, and components go around them.
> Next: clear the 3 redundant leak groups, and `adopted` follows.

At `held` there is no next threshold, and the line becomes what protects
the system and what would break it.
