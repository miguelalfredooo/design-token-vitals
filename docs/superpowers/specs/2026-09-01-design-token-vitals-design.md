# design-token-vitals — design

**Date:** 2026-09-01
**Status:** approved, not yet implemented
**Repo:** `design-token-vitals` (public, standalone)

---

## 1. What it is

An agent skill that inspects any front-end codebase and reports the health of its
design token layer. It runs with no setup, on a repo it has never seen, and produces
a graded report plus a machine-readable record of what that codebase can and cannot
prove about itself.

It descends from a `component-contract-parity` skill that assumed Figma as a
canonical source, Storybook, visual-regression tooling and an accessibility test
matrix. Applied to a real production Next.js app, four of its twelve gates were
`blocked` on day one because none of that infrastructure existed. The lesson drove
this design: **infer what the repo can prove, then only claim that.**

### Shape

A bootstrapper wrapping a source-agnostic assessment. The skill's first act is to
inspect — token source, tiering, modes, enforcement, naming — and emit findings
calibrated to what it actually found, never to an assumed standard.

Three stages were designed. **Release one ships only the first.**

| Stage | Ships | Purpose |
|---|---|---|
| `assess` | **v1** | Token vitals + capability map |
| `contract` | later | Component contract, calibrated by the capability map |
| `verify` | later | Parity gates, filtered by the capability map |

The capability map is the interface between them, so the later stages never
re-derive the inspection. `component-contract-parity` becomes a sibling skill that
consumes it.

---

## 2. The eight vitals

Each is graded independently, with evidence. Grades: `pass`, `attention`, `fail`,
`blocked`, `not_applicable`.

| # | Vital | Catches |
|---|---|---|
| 1 | Tier integrity | Components reaching past semantic tokens to primitives or raw values |
| 2 | Leakage | Hardcoded values where a token was available |
| 3 | Coverage | Categories with no tokens at all (motion, elevation, z-index, opacity are the usual gaps) |
| 4 | Mode completeness | A token defined in one mode and not another — inherits silently, ships wrong |
| 5 | Naming coherence | Two or more grammars in one system, so no name is guessable |
| 6 | Single source of truth | The same concept defined in more than one place, free to disagree |
| 7 | Orphans | Tokens nothing references |
| 8 | Enforcement | Whether any of the above can regress without a signal |

Held as advanced, not in v1: **contrast guarantees** on semantic foreground/background
pairs (needs a declared WCAG target most repos don't have) and **lifecycle/deprecation**
(only meaningful once a system has consumers to break).

### No composite score

Deliberate. A single 0–100 number would average away the one finding that matters, and
would score a repo with no dark mode at 60% rather than marking that check
`not_applicable`. An unrun check is `blocked`, never an implicit pass.

### Open: duplicates

Two semantic tokens resolving to the same value is a real defect that only becomes
visible at scale, and it fits none of the eight. Either it becomes a ninth vital, or
**naming coherence widens to "coherence" and absorbs it**. Current lean: the latter,
to keep "eight vitals" stable. Not yet decided.

---

## 3. Leakage: three tiers

Counting hardcoded values punishes correct code — a 1px hairline rarely needs a token.
The signal is whether the system offered a token and the code went around it.

| Tier | Condition | Fix owner |
|---|---|---|
| **Redundant** | A token holds this exact value | Component author — mechanical |
| **Near miss** | Within a small delta of a token (ΔE for color, distance to nearest step for dimension) | Design — reconcile or accept |
| **Uncovered** | No token exists for this concept | System — add the token |

The near-miss tier is the one that justifies the HTML report: drift is invisible to
grep and to code review, and is the usual reason a system stops feeling consistent.

Graded per category, weighted: **color** and **motion** above **dimension**, which is
the noisiest and most exception-prone. Declared escape hatches (an exception with an
owner and a deadline) are not findings; undeclared ones are.

---

## 4. Adapters

The skill's content — the eight vitals, the four grades, the report — is
stack-independent. Adapters are where-to-look tables, ~30–50 lines each, answering the
same four questions per ecosystem: where do tokens live, what does a raw-value leak
look like, how are modes expressed, what enforcement is idiomatic.

**v1 ships web only:** CSS custom properties, Tailwind, SCSS/Less, Style Dictionary /
DTCG JSON.

Deferred: iOS, Android, Flutter. The adapter interface proves itself on web first.

**Unknown stack → interview, never guess.** What can't be determined is `unknown`, not
zero.

DTCG emit is an opt-in output once tokens are located, not an input requirement —
requiring it would make run one "build a token file first" and would miss implicit
tokens entirely.

---

## 5. Report

Three outputs from one run:

| Output | Audience |
|---|---|
| `.token-vitals/report.html` | People. Single self-contained file, no server, no build step |
| markdown summary | Terminal and PR comments |
| `.token-vitals/report.json` | The capability map, plus every finding and location |

Precedent is Lighthouse: run it, get a page, read the page. Self-contained matters
practically — it attaches to CI as a build artifact and survives being emailed.

### Why HTML is primary

Half the findings are only legible visually: the token inventory rendered as itself
(color as color, type scale at real sizes, spacing drawn to width), near-miss pairs as
adjacent swatches, and mode gaps as a matrix.

### Rendering tiers

The report adapts to data volume the same way the skill adapts to repo capability.

| Tokens | Treatment |
|---|---|
| < 150 | Everything rendered |
| 150–600 | Families collapsed, exceptions expanded, top-N tables |
| 600+ | Family rows only, palette as ramps, mode as an exception report, full data in the JSON sidecar |

At 600+: namespaces become one row each with their own health line; palettes render as
ramps (which surfaces two findings that don't exist at small scale — **outliers**
belonging to no ramp, and **duplicates**); the mode matrix becomes a coverage bar plus
only the gaps; leakage ranks by blast radius with a deterministic order so re-running
never reshuffles.

### Two invariants that survive any summarization

1. **Aggregate the count, never the evidence.** Every rolled-up finding shows at least
   one real `file:line`. A finding that can't point at code is an opinion.
2. **Truncation is always declared.** `Showing 12 of 247` — never a silent cut. Same
   principle as `blocked` never being an implicit pass.

### Reference implementations

Two worked report templates exist and are the visual and copy standard:
- small system (214 tokens, all sections rendered)
- large system (840 tokens, all three scale treatments)

Both carry 42 tooltips: one per data table explaining what a row is, one per column
explaining what that column means.

---

## 6. Voice

Report copy divides three ways, and only the first is free:

1. **Static chrome** — headings, ledes, tooltips, legend. Ships in the template,
   identical every run by construction. The majority of the words.
2. **Slotted sentences** — vital cards, truncation lines, family rows. These read as
   prose but are data. They must be **slot templates in the skill**, not an instruction
   to summarize in a friendly tone; an instruction produces a different register every
   run.
3. **Generated** — the small residue that connects two findings. Governed by
   `references/voice.md` plus the two reference reports as worked examples.

### Rules

- Second person. Name the consequence before the principle.
- Explain a term at first use; keep correct terminology (semantic token, mode, ramp,
  orphan, primitive).
- **No "X is not Y, it's Z" constructions.** The single biggest fix in the copy pass.
- "Hardcoded values" in prose; "literal" only where it labels a code value in a table.
- **US English.** `color`, `tokenized`, `summarized`. Enforced as a lint step on the
  template — "color" is the most frequent noun in the report, so one British spelling
  would appear a dozen times per run.

---

## 7. Repo

```
design-token-vitals/            public, standalone, self-contained
  README.md                     what it does on first run, install, worked example, honest limits
  SKILL.md                      the workflow
  references/
    vitals.md                   the eight attributes, signals, grading rules
    voice.md                    the copy standard
    adapters/                   css-vars, tailwind, scss, dtcg
  assets/
    report-template.html
    capability-map.yml
  examples/                     one worked run against a public repo
  LICENSE
```

`agent-skills` (private) holds everything not yet published. Visibility is
per-repository, so a public skill lives in its own repo and is self-contained; the
adapters are duplicated rather than shared across a repo boundary if the sibling ever
goes public.

### Worked example

Runs against a **public** repo so findings are real and a reader can re-run them to
check. No private codebase is described, named or anonymized-but-recognizable.

---

## 8. Out of scope for v1

- `contract` and `verify` stages
- Mobile adapters
- DTCG generation as an input requirement
- Contrast and lifecycle vitals
- Hardcoded strings / i18n — a real dimension, but it belongs to content, not tokens
- A composite score, in any release

---

## 9. Open decisions

| # | Decision | Lean |
|---|---|---|
| 1 | Duplicates: ninth vital, or absorbed into a widened "coherence" | Absorb |
| 2 | 42 info icons may read as noisy on a seven-column table; alternative is a dotted-underline header label as the hover target | See it first |
| 3 | Whether the Uncovered tier should suggest token names at all — it crosses from measuring into prescribing | Behind an opt-in |
