# design-token-vitals

Grade the health of a codebase's design token layer, and report what it can and cannot prove about itself.

Most token audits answer the wrong question. They tell you a system exists, or count how many variables it has, and leave you to guess whether any of it reaches the browser. This one grades eight fixed vitals against evidence in your repository, cites a `file:line` for every finding, and says `blocked` out loud when a check could not run.

---

## The central diagnostic has three edges

**Does the system have an answer?** A category with no token is a decision nobody made. Coverage and mode completeness measure what your system claims to handle.

**Does the code reach for it?** A token nothing uses is a token that does not exist. Leakage and tier integrity measure the distance between what you declared and what your components actually do.

**Can this run prove either?** A check that could not run is never reported as a pass. Measured, unmeasured and absent are three different claims, and the report keeps them apart.

---

## What this project provides

- **An agent skill** you install into Claude Code or any agent that reads a `SKILL.md`
  - Seven stages, from framework discovery through writing the report
  - No build step, no dependencies beyond Python 3 for the tools
- **Eight fixed vitals**: tier integrity, leakage, coverage, mode completeness, naming coherence, single source, orphans, enforcement
- **Five status values** — `pass`, `attention`, `fail`, `blocked`, `not_applicable` — and **no composite score, ever**
- **A 19-family foundational taxonomy**, from color and typography through grid, focus, target size and density
- **Three leakage tiers** — `redundant`, `near-miss`, `uncovered` — each with a different owner and a different fix
- **Five source classifications** — `canonical`, `alias`, `consumer`, `generated`, `unverified` — assigned by reachability, not by filename
- **A 6-stage maturity trajectory**: `scattered` → `declared` → `adopted` → `layered` → `complete` → `held`
- **Nine validation rules** that fail a report claiming more than the run established
- **Ten tools**, including an import-graph builder, a run comparator and a trend differ
- **A fixture repository** with a golden output, so a change to the rules is checked rather than argued about

The skill grades a token layer. It does not replace usability review, accessibility audit, security review, or design critique. It reports on the web only: iOS, Android and Flutter adapters are unwritten.

---

## Install for Claude Code

The skill is a directory, not a package.

```
git clone https://github.com/miguelalfredooo/design-token-vitals.git
cd design-token-vitals
mkdir -p ~/.claude/skills/design-token-vitals
cp -R SKILL.md PRINCIPLES.md references assets tools ~/.claude/skills/design-token-vitals/
```

Then invoke it against any repository:

```
/design-token-vitals audit the token layer in ~/code/my-app
```

The agent reads `SKILL.md`, works through the seven stages, and writes `.token-vitals/report.html` and `.token-vitals/report.json`.

## Use with another agent

Copy the same files into whatever directory your agent reads skills from. Nothing in the skill is Claude-specific — `SKILL.md` is instructions, `references/` is the knowledge base, and `tools/` is plain Python with no third-party imports.

---

## Useful prompts

```
/design-token-vitals audit the token layer in ~/code/my-app
```

```
/design-token-vitals audit ~/code/my-app and lead with what I can automate
```

What happens: the fix queue orders by `(n + 2f + 3b) × c`, marks each entry `S`, `M` or `L`, and flags only the swaps a token already covers as safe to automate.

```
/design-token-vitals audit ~/code/my-app, then compare against last month's report.json
```

What happens: `trend.py` reports new, resolved and regressed findings — and refuses the comparison outright if the scope, adapters or token sources moved between the two runs.

```
/design-token-vitals why is our dark mode inconsistent in ~/code/my-app
```

What happens: mode completeness grades only where resolved output exists for every declared scheme. Where it does not, the answer is `blocked` and the name of the missing artifact.

---

## What you get back

### The HTML report

A single self-contained file — its own fonts, styles and markup, nothing loaded at read time. Attach it to CI, forward it by email, open it on a machine with no dev server.

It opens with an at-a-glance strip: the maturity stage as a six-tick ladder, the eight grades as a segmented bar, confirmed against blocked and unmeasured as another, leakage's three tiers as a third, the automatable share as a ring. Below that: an executive summary, a decisions region listing every close call the run made and the other reading of each, a ranked fix queue, findings grouped by owning component, token lineage from primitive to consumer, and a bundle × mode × family coverage matrix.

Colors render as swatches, type steps at their real size, spacing as bars drawn to width. A near-miss renders as two adjacent shades, because that finding cannot be described in words.

### The JSON working set

`report.json` duplicates exactly what the HTML shows, plus the full detail behind every disclosure. Rule 8 compares finding ids across both files and fails the run if the HTML holds fewer. Nothing exists only in the JSON.

### The terminal summary

Five lines: the worst vital, the first move with its `file:line`, the maturity stage and its next threshold, the confidence split, and the path to the report.

### Verification

Every grade that reports a finding carries at least one real `file:line`. A clean pass or a blocked check may carry an empty evidence list with a note saying why — there is nothing to point at when nothing was found. **A vital with a count and no reachable instance is graded `blocked`, never `fail`.** Silence is not evidence.

---

## How the knowledge base works

The skill is deliberately split: `SKILL.md` holds the stages and stays short, and `references/` holds the depth each stage needs. An agent reads only what a stage sends it to.

- `references/discovery.md` — the six jobs of Stage 1: detect the framework, discover every candidate source, build the import graph, classify each source, deduplicate projections and derive scope, discover whether modes resolve
- `references/vitals.md` — what each of the eight vitals catches, its signal, and its grading thresholds
- `references/leakage.md` — the ordered cascade that sorts every hardcoded value into one of three tiers
- `references/token-taxonomy.md` — the 19 foundational families and the names to search for
- `references/maturity.md` — the six stages and the threshold that leaves each one
- `references/report.md` — the report's structure, the density rules, and the priority formula
- `references/voice.md` — the copy standard, including the slot templates a generated sentence fills
- `references/adapters/` — five adapters: `css-vars`, `tailwind`, `scss`, `dtcg`, and a `generic` fallback

The run walks the stages in order, records everything into the schema in `assets/capability-map.yml`, fills `assets/report-template.html`, and runs the validation gate before writing anything.

Two constraints hold throughout. **An adapter never names a token file** — discovery decides which sources are real, by reachability from an owned production entry point. And **the skill never invents a grade value, a family name or a principle number**: the five statuses, the 19 families and the eight principles are fixed lists, and `tools/taxonomy.py --check` fails the build if the prose and the code disagree.

---

## Repository map

```
.
├── SKILL.md                     seven stages, read first
├── PRINCIPLES.md                eight principles, each with what it forbids
├── CHANGELOG.md
├── references/
│   ├── discovery.md             Stage 1: six jobs before any counting
│   ├── vitals.md                the eight vitals and their thresholds
│   ├── leakage.md               the three-tier cascade
│   ├── token-taxonomy.md        19 foundational families
│   ├── maturity.md              six stages, derived from the grades
│   ├── report.md                structure, density, priority formula
│   ├── voice.md                 copy standard and slot templates
│   └── adapters/                css-vars, tailwind, scss, dtcg, generic
├── assets/
│   ├── report-template.html     28 fillable regions
│   ├── capability-map.yml       the schema every run records into
│   └── reference/               small.html, large.html — worked examples
├── tools/
│   ├── import_graph.py          reachability from owned entry points
│   ├── validate_run.py          the nine rules, as a gate
│   ├── findings.py              stable ids, priority score, effort class
│   ├── trend.py                 new, resolved, regressed, with a compatibility gate
│   ├── compare_runs.py          do two runs of the same code agree?
│   ├── taxonomy.py              the 19 families, defined once
│   ├── palette.py               WCAG AA across all three theme blocks
│   ├── version.py               stamped into every report
│   ├── check_voice.py           the copy standard
│   └── cli.py                   shared exit codes and --json
├── fixtures/
│   ├── repo/                    a known codebase with six deliberate traps
│   └── expected.json            the golden output
└── examples/shadcn-ui/          a run against a public repository
```

---

## Validate the project

```
cd tools && for t in test_*.py; do python3 -m unittest "${t%.py}"; done
python3 tools/palette.py
python3 tools/taxonomy.py --check
python3 tools/check_voice.py $(git ls-files '*.md' '*.html' '*.yml')
```

That runs 183 tests across ten tools and checks four things the skill asserts about others:

- every status color clears WCAG AA on its own tint, in light, dark and the explicit theme override
- the 19 families in the reference Markdown match the list in code, exactly and in order
- every section of the report template opens with an eyebrow, a heading and a lede
- no layout decision is hardcoded inline in the template

To check a report the skill produced:

```
python3 tools/validate_run.py .token-vitals/report.json --html .token-vitals/report.html
```

Exit 0 means nothing to report, 1 means a rule failed, 2 means the tool refused to run.

---

## Status and limitations

**This skill is in active development and it is not finalized.** Treat it as something in use and under revision at the same time.

What is stable: the eight vitals, the five status values, the refusal to produce a composite score, and the rule that every finding carries a real `file:line`. What is still moving: the rendering forms, the leakage cascade's borderline cases, and reproducibility.

**Reproducibility, measured four times.** Eight blind runs against shadcn-ui/ui at `63c1308`, in four pairs, each pair sharing no context:

| Pair | Skill size | Grades agreed | Tokens | Split on |
|---|---|---|---|---|
| A / B | ~9,500 words | 8 of 8 | 114 / 114 | — |
| C / D | ~14,600 words | 7 of 8 | 82 / 77 | leakage |
| E / F | ~14,400 words | 7 of 8 | 56 / 78 | leakage |
| G / H | ~14,500 words | 6 of 8 | 74 / 78 | leakage, coverage |

Seven of the eight vitals have been stable across every pair. **Leakage has split in all four**, each time on a different unwritten question — whether a framework's derived scale offers swap targets, what a "finding" counts, whether a redeclared framework name is a project token, and now whether a framework's *named* tokens are part of your system at all. Four of those are pinned in prose and asked by `fixtures/repo`. Each pin held on the pair that followed it, and the next pair found the next question one sentence away.

The honest reading: the grades that describe your architecture reproduce. **The leakage grade does not yet, and a report should be read with that in mind** — its evidence is real and checkable, and the threshold it crosses depends on a judgment the skill has not finished specifying. Every run records its close calls in a decisions region for exactly this reason.

Other known limits: web only; the Discourse adapter is unwritten; `examples/shadcn-ui/` predates the current rules and is stale.

---

## License

MIT. See [LICENSE](LICENSE).

The skill has no third-party dependencies. The tools use the Python standard library, and the report template embeds no external assets.
