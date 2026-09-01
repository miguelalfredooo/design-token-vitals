# design-token-vitals

An agent skill that grades the health of a codebase's design token layer —
eight fixed checks, each backed by real evidence from your repository,
never a guess and never an average.

## Status: a working skill, still evolving

This skill is in active development and it is not finalized. Treat it as
something in use and under revision at the same time, rather than a
finished tool with settled behavior.

What is stable: the eight vitals, the five status values
(`pass`, `attention`, `fail`, `blocked`, `not_applicable`), the refusal to
produce a composite score, and the rule that every finding carries a real
`file:line`. Those are the design, and changing them would make it a
different skill.

What is still moving: the rendering forms, the discovery stage, the leakage
cascade's borderline cases, and the reproducibility work. A later version
can change what a report looks like, and it can change how a genuinely
close call gets graded.

So: trust a report the way you would trust a colleague's reading of your
codebase — check it. Every finding points at a line you can open, which is
the whole reason the evidence rule exists. If you need two runs months
apart to be comparable, pin the version you ran.

Open work, in the order it matters:

- **Reproducibility, measured.** Two blind runs against shadcn-ui/ui at
  `63c1308` on 2026-09-01 agreed on all eight grades and on the token count
  (114 both times). An earlier pair disagreed on three of eight grades and
  reported 53 against 114. The grades reproduce.
- **What still moves between runs.** Those same two runs disagreed on
  `files_scanned` (3,686 against 3,400) and `family_count` (13 against 24),
  and cited largely different evidence lines under matching grades. Scope
  and reachability now come from `tools/import_graph.py` rather than from
  prose reasoned out fresh each run, which is aimed squarely at this.
- **One judgment call decides a grade, and the skill does not pin it down.**
  Counting a framework's own scales as tokens available to authors moves
  leakage from `attention` to `fail`. Both runs chose the same way, so they
  agreed — by agreement rather than by rule.
- **The rendering forms are new.** The display-density work landed
  recently and has had little use in the field. The two runs picked
  different forms for the same leakage data, which is a real gap in the
  form-choice rule.

Issues and pull requests are welcome, and so is a report that came out
wrong — a case where the skill graded something you know to be untrue is
more useful than one where it agreed with you.

## What you get on the first run

Before it counts anything, the skill runs a discovery stage: it detects
your framework and styling system from repository evidence — manifests,
build config, dependency locks, asset registration, entry points, theme and
plugin structure — then finds every candidate token source rather than
matching one filename, builds the stylesheet import graph from the entry
points you actually ship, and keeps only the sources something reaches. A
token file nothing imports gets reported as orphaned source material rather
than counted as your system. It works out which paths this project authored
against which it installed, so a hardcoded value in a dependency or an
upstream plugin is never reported as yours.

It searches for every foundational token family — color, typography,
spacing, sizing, radius, border, elevation, opacity, layer, motion,
breakpoints, grid and columns, focus, target size, state, iconography,
aspect ratio, blur and density — and tells you which it measured, which
your project declares nothing for, and which it could not resolve. Those
are three different answers, and a category it could not measure never
renders as zero.

Point it at a repository and it reads what your project actually declares —
its token sources, its modes, its categories — then grades eight vitals
against that declaration and shows its work: every finding carries at least
one real `file:line` you can open and check yourself — a clean pass or a
blocked check carries a note instead. The report also ranks those findings
into a "Where to start" plan — a short, ordered list of concrete actions,
each with an owner and a real `file:line` — so you leave with a next move,
not just a diagnosis. The report shows every finding it
produced: when a section outgrows a table it changes to a denser mark —
colors to swatches, leaks to ranked bars — rather than to a shorter list,
and the tail of a very large section sits behind a `<details>` element on
the same page rather than filed away in another file. The output is a single
self-contained HTML report, a JSON working set that duplicates exactly what
the HTML shows in a machine-readable form for tooling, and a short terminal
summary naming the one thing worth doing first.

The report opens with an executive summary — the highest-impact problem,
how many owned files and components it touches, what to fix first, and how
many results are confirmed against blocked or unmeasured. Below that sits a
**fix queue**: every finding with a canonical replacement, ranked by
`(n + 2f + 3b) x c` over occurrences, affected files, breadth and confidence,
with the inputs shown beside the score so you can re-rank on your own
weights. Each entry says whether the swap is safe to automate, and only a
value one of your tokens already holds ever is. Findings group by owning
component, plugin and route as well as by value, so an engineer can start
from what they maintain. Token lineage traces primitive to semantic alias to
projection to consumers, which is what separates a deliberate alias from a
duplicate definition. A coverage matrix crosses every entry bundle with
every mode and every family, so a gap in what the run could see reads as a
shape rather than as an absence you have to notice.

See a real one: [`examples/shadcn-ui/report.html`](examples/shadcn-ui/report.html)
(GitHub renders this as raw HTML rather than a page, so download it and open it locally).

## The tools

Four scripts ship with the skill. The first two are the audit's own
guardrails, and they run as code because a rule the run re-derives each
time is a rule that drifts.

| Tool | What it does |
|---|---|
| `tools/findings.py` | Stable, path-independent finding ids, and the priority score `(n + 2f + 3b) x c` over occurrences, affected owned files, breadth, and confidence in the fix |
| `tools/trend.py` | New, resolved, count changes and regressions between two runs. Refuses when framework, adapters, owned paths, scope or token sources diverge |
| `tools/import_graph.py` | Walks stylesheet and JS-entry imports from owned production entry points. Reports what is reachable, what is orphaned, and what resolves outside the repository. Reachability is what makes a candidate source an active one |
| `tools/validate_run.py` | Fails an audit that uses one presumed token file with no discovery evidence, inventories an unreachable source, claims mode coverage without resolved output, reports zero for an unmeasured category, omits a foundational family, or truncates in the HTML while the JSON holds more |
| `tools/compare_runs.py` | Diffs two runs on scope, counts, the eight grades, per-vital evidence, and rendering forms. Exits non-zero when the grades disagree |
| `tools/check_voice.py` | The copy standard for generated reports |

```bash
python3 tools/import_graph.py <repo> --entry app/globals.css --json graph.json
python3 tools/validate_run.py .token-vitals/report.json --html .token-vitals/report.html
python3 tools/compare_runs.py run-a/report.json run-b/report.json
python3 tools/trend.py baseline/report.json .token-vitals/report.json
```

Baselines are passed explicitly, so the skill never writes state into the
repository it audits. Commit `.token-vitals/report.json` and any past commit
becomes a baseline.

## Install

The skill is a directory, not a package. Copy `SKILL.md`, `references/`,
and `assets/` into `.claude/skills/design-token-vitals/` (Claude Code) or
the equivalent skills directory for the agent you use. There is nothing to
build and nothing to install — the agent reads `SKILL.md` and runs the seven
stages directly against your repository.

## How it works

1. **Discover the codebase** — work out what owns theming, what the project actually authored, and the scope those two answers leave you with.
2. **Detect the stack** — match the repository against the CSS-vars, Tailwind, SCSS, and DTCG adapters; more than one can apply at once.
3. **Read what the project declares** — modes, categories, and any accessibility target, taken from the repository, never assumed.
4. **Grade the eight vitals** — each one graded against the stack and declarations from the prior stages, with at least one real `file:line` attached to every grade.
5. **Choose the rendering tier** — the token count decides how much evidence renders inline versus rolls up into a count.
6. **Fill the template** — the self-contained report is built by filling named slots in a fixed template, never by writing free-form HTML.
7. **Write the outputs** — the HTML report, a JSON working set that duplicates it for tooling, and a terminal summary naming one next step.

## The eight vitals

| Vital | Catches |
|---|---|
| Tier integrity | Components reaching past your semantic layer to grab a primitive-tier name or a raw value directly, skipping the layer built to carry meaning. |
| Leakage | Hardcoded values in code where a token was already available to express the same thing. |
| Coverage | Whole categories of design decision with no tokens defined at all, which forces every value in that category to be hardcoded by necessity rather than by oversight. |
| Mode completeness | A token defined in one mode and silently missing in another — the gap does not error at build time, it falls back to the other mode's value and ships wrong. |
| Naming coherence | More than one naming grammar living inside a single token system, which means knowing one token's name tells you nothing about how to guess another's. |
| Single source of truth | The same design concept defined in more than one place, which opens the door for the definitions to drift out of agreement with each other. |
| Orphans | Tokens that are defined but that nothing in the codebase references — they make the system look bigger and more capable than it is, and they are safe to delete once you can see they are unused. |
| Enforcement | Whether any of the other seven vitals could regress without anyone noticing — a system with no guardrail can drift right back to where it started the day after a report is read. |

## What it does not do

- **No composite score, ever.** Averaging hides the finding that matters — a system with thousands of leaked values and perfect naming would land in the middle of a blended score, burying the one thing that needed fixing first.
- **Web only in v1.** iOS, Android, and Flutter adapters are not written yet.
- **It grades against what your project declares.** It reads your modes and categories from your repository and grades against those — it never imposes a standard you did not choose.
- **It measures, ranks what to do first, and stops short of changing your code.** The report tells you where to start — a ranked list of concrete actions, each with an owner and a real `file:line` — but refactoring your tokens stays your decision to make and carry out.
- **Two runs can disagree, because a language model runs this skill.** The same repository, at the same commit, with the same scope, can produce different grades or a different token count on two separate runs. Every report records what it measured, so a difference can be attributed to what each run actually looked at. See [Status](#status-a-working-skill-still-evolving) for where that work stands.

## The honest-gaps example

Mode completeness is graded per mode your project actually declares. Say
one project declares only `light` and `dark`: it never claimed a
high-contrast mode, so a high-contrast check has nothing to grade against
and comes back `not_applicable` — not counted against the project. Say a
second project declares `light`, `dark`, and `high-contrast` in its own
config, and its token source defines that third mode for some tokens but
not others: the same check now finds a real gap, and grades `fail`, with
the token name and the mode it's missing from attached as evidence.

Same check, opposite verdicts, and the difference never comes from an
assumption the tool made — it comes entirely from what the project itself
promised. A grade this skill produces is only ever a comparison against a
target the project set for itself.

## A real run: shadcn-ui/ui

`examples/shadcn-ui/` is a full run against a public repository
(shadcn-ui/ui, commit `63c1308`), so every finding in it is independently
checkable. It came back with no failures: four vitals at `attention`
(tier integrity, leakage, coverage, single source of truth), three at
`pass` (mode completeness, naming coherence, orphans), and one `blocked`
(enforcement).

`blocked`, not `fail`, matters here: nothing in that repository's lint
config or CI reads the token layer at all, so there is nothing to grade —
a check that could not run is never reported as a silent pass. A mostly
healthy system with one real gap in its guardrails is a more useful,
more credible result than a report tuned to look dramatic, and it is
exactly what the skill found and nothing more.

Read the full breakdown, with every `file:line`, in
[`examples/shadcn-ui/README.md`](examples/shadcn-ui/README.md),
[`report.json`](examples/shadcn-ui/report.json), or the rendered
[`report.html`](examples/shadcn-ui/report.html).

## License

MIT. See [`LICENSE`](LICENSE).
