# design-token-vitals

An agent skill that grades the health of a codebase's design token layer —
eight fixed checks, each backed by real evidence from your repository,
never a guess and never an average.

## Principles

Every skill in this family holds itself to the eight in
[`PRINCIPLES.md`](PRINCIPLES.md): render the thing as itself; say what is
worst first; orient every section with what, why, and what to do; explain
once and trust the reader; show the arithmetic; never let unknown read as
zero; rules in code, teaching in prose; say where they are and where next
is. Each names what it forbids and how it is checked.

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

- **Reproducibility, measured three times.** Six blind runs against
  shadcn-ui/ui at `63c1308`, in three pairs. Each pair agreed on seven of
  eight grades and split on one word neither the prose nor a test had
  pinned down: whether a framework's derived scale offers swap targets,
  what a leakage "finding" counts, whether a redeclared framework name is
  a project token. Each of those is now pinned and asked by
  `fixtures/repo`, and each pin held on the following pair. A fourth pair
  is the next measurement. The grades that matter have been stable across
  all six — only `leakage` has ever moved.
- **The earlier picture, kept for the record.** Four blind runs
  against shadcn-ui/ui at `63c1308` on 2026-09-01. The morning pair, against
  a skill of about 9,500 words, agreed on all eight grades and counted 114
  tokens both times. The afternoon pair, after the discovery stage and the
  actionable-report layer had grown the skill to about 14,600 words, agreed
  on seven of eight and counted 82 and 77. The one that split was
  `leakage`, on a decision both runs named as their closest call: whether a
  framework's own spacing scale counts as tokens available to authors.
  Neither the grade nor the count is stable yet, and this line will change
  again when that is fixed.
- **What caused it, as far as the evidence goes.** The skill has no written
  rule for the framework-scale question, and no written rule for which
  utility-local custom properties count as tokens. Two careful runs read
  each differently. Both rules are being pinned in prose and exercised in
  `fixtures/repo`, and the pair gets re-run before that merges.
- **What still moves between runs even when the grades agree.**
  `files_scanned`, `family_count`, and the specific evidence lines cited
  under matching grades. Scope and reachability now come from
  `tools/import_graph.py` rather than prose, which is aimed at this.
- **The rendering forms are new.** The display-density work landed
  recently and has had little use in the field. The two runs picked
  different forms for the same leakage data, which is a real gap in the
  form-choice rule.

Issues and pull requests are welcome, and so is a report that came out
wrong — a case where the skill graded something you know to be untrue is
more useful than one where it agreed with you.

## What you get on the first run

Before it counts anything, the skill runs a universal discovery engine. It
composes evidence-backed framework profiles rather than choosing one label:
a Discourse app may also use Rails/Sprockets and a monorepo may contain a
Next.js app with Storybook. Profiles guide where to investigate manifests,
build config, dependency locks, asset registration, route and component
trees, entry points, theme structure, and plugin boundaries. Reusable profile
extractors turn registration calls, config arrays, and build JSON into
evidenced roots; project-specific profiles get the same capability without
editing the engine. Disconnected root hypotheses and component locations
outside owned scope stay visible as candidates instead of becoming false
facts or silent omissions. The engine then
finds every candidate token source rather than matching one filename, builds
the style-bearing import graph from the entry points the product actually
ships, and keeps only the sources something reaches. A
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

The report opens with an **at-a-glance strip**: the maturity stage as a
six-tick ladder, the eight grades as one segmented bar, confirmed against
blocked and unmeasured as another, leakage's three tiers as a third, the
automatable share of the fix queue as a ring, and the counts as tiles.
Every mark carries its number. The report ships one fixed, validated script
for accessible inventory-family tabs; repository content can never enter it.

Below it, an executive summary — the highest-impact problem,
how many owned files and components it touches, what to fix first, and how
many results are confirmed against blocked or unmeasured. Below that sits a
**fix queue**: every finding with a canonical replacement, ranked by
`(n + 2f + 3b) x c` over occurrences, affected files, breadth and confidence,
with the inputs shown beside the score so you can re-rank on your own
weights. Each entry says whether the swap is safe to automate — and only a
value one of your tokens already holds ever is — and carries an effort
class, `S`, `M` or `L`, derived from that and the file count rather than
from an invented hour estimate. Impact and effort are the two halves of
the decision, and the queue shows both.

A **stage line** names where the system is on a six-step trajectory and
the one threshold that moves it: `declared` → clear the redundant leaks →
`adopted`. It is derived from the eight grades, so you can check it, and
it is never a number. A **decisions region** lists every close call the
run made, what each one moved, and the other reading — because a grade
that rests on a judgment is a grade you should be able to overturn. Findings group by owning
component, plugin and route as well as by value, so an engineer can start
from what they maintain. Token lineage traces primitive to semantic alias to
projection to consumers, which is what separates a deliberate alias from a
duplicate definition. A coverage matrix crosses every entry bundle with
every mode and every family, so a gap in what the run could see reads as a
shape rather than as an absence you have to notice.

See a real one: [`examples/shadcn-ui/report.html`](examples/shadcn-ui/report.html)
(GitHub renders this as raw HTML rather than a page, so download it and open it locally).

## The tools

Deterministic scripts ship with the skill because a discovery rule or audit
guardrail the run re-derives each time is a rule that drifts.

| Tool | What it does |
|---|---|
| `tools/discover_environment.py` | Runs the universal capability ladder, composes matching framework profiles, selects an application boundary, and records product roots, component roots, supplemental surfaces, ownership, and evidence |
| `tools/framework_profiles.py` | Loads and validates the built-in profile registry plus optional project profiles, then evaluates repository signals without turning partial matches into facts |
| `tools/profile_extractors.py` | Executes validated profile-declared registration, config-array, and build-JSON root extractors for built-in and custom frameworks |
| `tools/discover_tokens.py` | Finds CSS, Sass, DTCG, Style Dictionary, conservative JS/TS theme, and component-embedded declarations; classifies canonical sources, projections, overrides, and unverified candidates |
| `tools/render_discovery.py` | Rebuilds finished runs from the current template; keeps summaries, decisions, ownership, lineage, coverage, discovery, identity, token inventory, leakage, and provenance identical in report JSON and HTML; Color, Typography, and Foundation use accessible tabs while long token tables use a first-20 plus “See more” disclosure without dropping rows |
| `tools/findings.py` | Stable, path-independent finding ids, and the priority score `(n + 2f + 3b) x c` over occurrences, affected owned files, breadth, and confidence in the fix |
| `tools/trend.py` | New, resolved, count changes and regressions between two runs. Refuses when framework, adapters, owned paths, scope or token sources diverge |
| `tools/import_graph.py` | Walks stylesheet and JS-entry imports from owned production entry points. Reports what is reachable, what is orphaned, and what resolves outside the repository. Reachability is what makes a candidate source an active one |
| `tools/validate_run.py` | Fails an audit that uses one presumed token file with no discovery evidence, inventories an unreachable source, claims mode coverage without resolved output, reports zero for an unmeasured category, omits a foundational family, truncates in the HTML while the JSON holds more, is stale against its discovery/token/component/leakage or browser-interaction artifacts, or renders typography/brand identity without independently recomputed repository evidence and a verified self-contained font specimen |
| `tools/compare_runs.py` | Diffs two runs on scope, counts, the eight grades, per-vital evidence, and rendering forms. Exits non-zero when the grades disagree |
| `tools/check_voice.py` | The copy standard for generated reports. Skips fenced blocks and inline code, so a document can name a banned word as data |
| `tools/palette.py` | Checks every status color against its own tint, in all three theme blocks. WCAG AA, and the report grades others on this |
| `tools/taxonomy.py` | The nineteen foundational families, defined once. `--check` compares the code against the reference Markdown |
| `tools/version.py` | The skill's own version, stamped into every report as `provenance.skill_version` |
| `tools/cli.py` | What every tool agrees on: `--json PATH`, and exit 0 nothing found / 1 something found / 2 refused |

```bash
python3 tools/discover_environment.py <repo> --owned 'src/**' --json discovery.json
python3 tools/discover_tokens.py <repo> --discovery discovery.json --update-discovery --json tokens.json
python3 tools/audit_literal_colors.py <repo> --discovery discovery.json --tokens tokens.json --json literal-colors.json
python3 tools/import_graph.py <repo> --entry app/globals.css --json graph.json
python3 tools/render_discovery.py --refresh-template --discovery discovery.json --tokens tokens.json --leakage literal-colors.json --report-json report.json --html report.html
python3 tools/validate_run.py .token-vitals/report.json --html .token-vitals/report.html --discovery .token-vitals/discovery.json --tokens .token-vitals/tokens.json --components .token-vitals/components.json --leakage .token-vitals/literal-colors.json --current-skill
python3 tools/compare_runs.py run-a/report.json run-b/report.json
python3 tools/trend.py baseline/report.json .token-vitals/report.json
python3 tools/palette.py
python3 tools/taxonomy.py --check
```

Baselines are passed explicitly, so the skill never writes state into the
repository it audits. Commit `.token-vitals/report.json` and any past commit
becomes a baseline.

## Install

The skill is a directory, not a package. Copy the entire
`design-token-vitals/` directory — including `SKILL.md`, `tools/`, `assets/`,
and `references/` — into `.claude/skills/` (Claude Code) or the equivalent
skills directory for the agent you use. There is nothing to build and no
third-party dependency to install: the agent reads `SKILL.md` and runs the
bundled tools directly against your repository.

## How it works

1. **Discover the codebase** — compose every evidenced framework profile, select the application boundary, and separate product roots from component and supplemental surfaces.
2. **Detect the styling stack** — match CSS-vars, Tailwind, SCSS, DTCG, and framework-specific mechanisms; profiles and adapters can all apply at once.
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
