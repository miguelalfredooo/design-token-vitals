# Discovery

This is the depth behind Stage 1 in `SKILL.md`. Before you count a single
token, do three jobs, in order: work out what owns theming, work out what
the project actually authored, and derive the scope those two answers
leave you with. Skip any of the three and the stages that follow measure
the wrong thing — a coverage grade against the wrong build step, a leakage
count that includes code nobody at this project can fix, a mode check
graded `blocked` for the wrong reason.

## Job one — what owns the theming

The framework a codebase runs on decides where its real token source
lives, whether a build step resolves values before they reach the browser,
and how modes get expressed. Guess wrong here and every later stage grades
the wrong artifact.

| Signal | Environment |
|---|---|
| `plugins/` beside `app/assets/stylesheets/`, and `dark-light-choose()` or `$light-theme-*` / `$dark-theme-*` in SCSS | Discourse |
| `next.config.*` | Next.js |
| `tailwind.config.*`, or `@theme` in CSS | Tailwind |
| `Gemfile` with `app/assets/stylesheets/` | Rails with Sprockets |
| `workspaces` in `package.json`, `pnpm-workspace.yaml`, or `turbo.json` | a monorepo — the scope is one app, so ask which |
| `.storybook/` | Storybook is present; stories are not product code |

More than one row can match. A Rails app with a Tailwind config still runs
Sprockets for the rest of its stylesheets; a monorepo signal narrows scope
without telling you the environment underneath it. Record every signal you
found and the environment (or environments) you concluded from them.

### Discourse

Discourse theming runs through `dark-light-choose()` and `$light-theme-*` /
`$dark-theme-*` in SCSS, and the values that actually ship come from a
compiled per-site theme, not from the SCSS source alone. Grading mode
parity from source is not something you can do here: the SCSS defines the
*mechanism*, not the resolved light and dark values a browser receives.

Either locate the compiled theme output and grade `mode-completeness`
against that, or grade it `blocked` with the reason stated: source-only
SCSS cannot tell you whether a given token's light and dark values agree,
because the values themselves live somewhere this run cannot see. A
`blocked` grade with that reason on record is the correct outcome here,
and a better one than a guess dressed up as a `pass`.

## Job two — what the project owns

A design-token report only helps the reader where the reader can act.
Exclude the following by default, and record why for each path you
exclude:

- **`node_modules/`, `vendor/`, `third_party/`.** Dependencies. Nobody at
  this project edits them.
- **Git submodules.** Read `.gitmodules` — a submodule is a separate
  repository with its own owners, checked out at a path inside this one.
- **`dist/`, `build/`, `.next/`, `out/`, and compiled CSS carrying a source
  map.** Generated output. A literal value found there came from
  somewhere else — the source that produced it, which is the file worth
  grading instead.
- **Upstream plugins and themes.** In Discourse, `plugins/` holds both
  code this project wrote and code it only installed. Tell them apart by:
  - presence in `.gitmodules`;
  - the plugin's own `about.json` authorship against the project's;
  - `git log --oneline -- <path>` — a plugin this project authored has a
    commit history of its own changes; an installed one usually has a
    single vendoring commit, or none at all.
- **Any path the project marks exempt.**

State the rule this serves plainly: a leak is only a finding if the reader
can fix it. A hardcoded color in someone else's plugin is a fact about
that plugin, not about your design system — reporting it as a finding
about your system inflates a real, unrelated project's problem into a
number that reads as yours.

## Job three — the derived scope

Build the scope from what jobs one and two just told you, rather than
accepting a scope handed to you or guessing one from the directory
listing. Show the reader the scope and the file count it resolves to
*before* measuring anything against it — a scope you cannot state is a
scope you cannot defend, and a reader who cannot see it has no way to
tell whether the report that follows covers their code or someone else's.

If more than one app in a monorepo plausibly qualifies, ask which one
rather than guessing. A guess here does not fail loudly — it produces a
complete-looking report graded against the wrong application, and nothing
downstream will flag that for you.

Record the outcome of all three jobs in `assets/capability-map.yml`'s
`discovery` block before moving on to Stage 2.
