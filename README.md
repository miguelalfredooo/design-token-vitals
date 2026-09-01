# design-token-vitals

An agent skill that grades the health of a codebase's design token layer —
eight fixed checks, each backed by real evidence from your repository,
never a guess and never an average.

## What you get on the first run

Point it at a repository and it reads what your project actually declares —
its token sources, its modes, its categories — then grades eight vitals
against that declaration and shows its work: every finding carries at least
one real `file:line` you can open and check yourself — a clean pass or a
blocked check carries a note instead. The report also ranks those findings
into a "Where to start" plan — a short, ordered list of concrete actions,
each with an owner and a real `file:line` — so you leave with a next move,
not just a diagnosis. The output is a single self-contained HTML report, a
JSON working set for tooling, and a short terminal summary naming the one
thing worth doing first.

See a real one: [`examples/shadcn-ui/report.html`](examples/shadcn-ui/report.html)
(GitHub renders this as raw HTML rather than a page, so download it and open it locally).

## Install

The skill is a directory, not a package. Copy `SKILL.md`, `references/`,
and `assets/` into `.claude/skills/design-token-vitals/` (Claude Code) or
the equivalent skills directory for the agent you use. There is nothing to
build and nothing to install — the agent reads `SKILL.md` and runs the six
stages directly against your repository.

## How it works

1. **Detect the stack** — match the repository against the CSS-vars, Tailwind, SCSS, and DTCG adapters; more than one can apply at once.
2. **Read what the project declares** — modes, categories, and any accessibility target, taken from the repository, never assumed.
3. **Grade the eight vitals** — each one graded against the stack and declarations from the first two stages, with at least one real `file:line` attached to every grade.
4. **Choose the rendering tier** — the token count decides how much evidence renders inline versus rolls up into a count.
5. **Fill the template** — the self-contained report is built by filling named slots in a fixed template, never by writing free-form HTML.
6. **Write the outputs** — the HTML report, the JSON working set, and a terminal summary naming one next step.

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
