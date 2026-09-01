# Discovery

This is the depth behind Stage 1 in `SKILL.md`. Before you count a single
token, do six jobs, in order. Skip any of them and every stage after
measures the wrong thing — a coverage grade against the wrong build step, a
leakage count full of code nobody here can fix, an inventory of a file the
browser never receives.

The rule underneath all six: **discover sources from evidence, and prove
they ship before grading them.**

## Job one — detect the framework and styling system

The framework decides where the real token source lives, whether a build
step resolves values before they reach the browser, and how modes get
expressed. Guess wrong and every later stage grades the wrong artifact.

Read evidence, in this order, and record every signal you find:

| Evidence | What to read |
|---|---|
| Manifests | `package.json`, `Gemfile`, `composer.json`, `pubspec.yaml`, `*.gemspec` |
| Build config | `next.config.*`, `vite.config.*`, `webpack.*`, `rollup.*`, `astro.config.*`, `tailwind.config.*`, `postcss.config.*` |
| Dependency locks | `pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`, `Gemfile.lock` — the version an importer resolves, rather than the range a manifest requests |
| Asset registration | `register_asset`, `register_css`, Sprockets manifests, `content_for`, theme and plugin registration APIs |
| Stylesheet entry points | the roots in `tools/import_graph.py`'s conventions table |
| Template conventions | `app/views/`, `templates/`, `pages/`, `app/` route directories |
| Theme and plugin structure | `plugins/`, `themes/`, `about.json`, theme manifests |
| Source extensions | which of `.css`, `.scss`, `.sass`, `.less`, `.ts`, `.tsx`, `.json` actually carry declarations |

| Signal | Environment |
|---|---|
| `plugins/` beside `app/assets/stylesheets/`, and `dark-light-choose()` or `$light-theme-*` / `$dark-theme-*` in SCSS | Discourse |
| `next.config.*` | Next.js |
| `tailwind.config.*`, or `@theme` in CSS | Tailwind |
| `Gemfile` with `app/assets/stylesheets/` | Rails with Sprockets |
| `vite.config.*` with `src/index.css` or `src/main.*` | Vite |
| `workspaces` in `package.json`, `pnpm-workspace.yaml`, or `turbo.json` | a monorepo — the scope is one app, so ask which |
| `.storybook/` | Storybook is present; stories are not product code |
| nothing above matches | use `references/adapters/generic.md` |

More than one row can match, and that is normal. Record the framework, the
adapters, the confidence, and the evidence path for each — into
`discovery.environment`, `discovery.detected_by`, `discovery.confidence`,
and `discovery.evidence`, and into the report's measurement section. A
framework you concluded with nothing to point at is a guess.

### Discourse

Discourse theming runs through `dark-light-choose()` and `$light-theme-*` /
`$dark-theme-*` in SCSS, and the values that ship come from a compiled
per-site theme rather than from the SCSS source. Before choosing token
sources here, inspect plugin asset registration, the core stylesheet bundle
roots, `common.scss`, `desktop.scss`, `mobile.scss`, the theme color
definitions, `dark-light-choose()`, and `schemeType()`.

Grading mode parity from source alone is out of reach: the SCSS defines the
mechanism, and the resolved light and dark values live somewhere this run
cannot see. Either locate the compiled theme output and grade
`mode-completeness` against that, or grade it `blocked` with that reason on
record. Job six covers this in general.

## Job two — discover every candidate token source

Search the whole owned tree for every kind of source below. Never match a
filename and stop: a system whose color lives in `_colors.scss`, whose type
scale lives in a JS theme object, and whose spacing comes from a Style
Dictionary JSON has three sources, and matching one of them reports a third
of a system as the whole of it.

- **CSS custom properties** — `--*` declarations in any selector, plus
  `@property` registrations
- **Preprocessor variables** — SCSS and Less `$`/`@` variables, Sass maps,
  `@each` loops that generate names, `@use` and `@forward` module members
- **JS and TS token objects** — theme objects, `as const` token maps,
  `createTheme` calls, config exports
- **JSON token files** — DTCG (`$value`/`$type`), Style Dictionary, Tokens
  Studio exports
- **Every foundational family** in `references/token-taxonomy.md`, searched
  by its common names

Record each hit as a candidate with its path and what matched. A candidate
is a claim about where tokens might live, and job three decides which
claims hold.

## Job three — build the import graph and prove reachability

Run `tools/import_graph.py` against the repository:

```
python3 tools/import_graph.py <root> --entry <owned entry point> --json .token-vitals/graph.json
```

Find the roots the framework registers — build entry points, asset
registration calls, stylesheet bundle roots — and traverse from each. Cover
the bundles a framework registers separately: common, desktop, mobile,
theme, plugin, component, and route-specific.

**A candidate becomes an active source when it is reachable from an owned
production entry point.** Anything else is unverified or orphaned source
material, and it is reported as such rather than inventoried as if it
shipped. A stylesheet full of beautiful token declarations that no bundle
imports contributes nothing to the running product, and counting it inflates
the system's apparent size while hiding that nobody wired it up.

Templates, routes and page registrations are **supplemental evidence only**,
for conditional, route-specific, component-specific or lazily loaded styles.
A template that references a stylesheet is a reason to look, and it never
by itself proves production inclusion.

Record the graph roots, the reachable set, the unresolved specs and the
orphans in `discovery.import_graph`, and put the same evidence in the
report.

## Job four — classify every source

| Class | Meaning | How it is used |
|---|---|---|
| `canonical` | The definition. The value originates here | Inventoried; the token count counts these |
| `alias` | A semantic or projected restatement of a canonical token | Inventoried, linked to its canonical |
| `consumer` | Uses tokens rather than defining them | Leakage scope, never inventory |
| `generated` | Build output | Excluded; grade the source that produced it |
| `unverified` | A candidate with no path to an owned entry point | Reported as unverified, never counted |

Record the class, the reachability path, and the alias relationship for
each source. `tools/validate_run.py` rule 2 fails an audit that inventories
a `canonical` or `alias` source with no `reachable_from`.

## Job five — deduplicate projections, and derive the scope

A SCSS variable and the custom property it emits are one token concept.
So are a DTCG entry and the CSS variable a build step generates from it.
Collapse them into one concept, keep every source location, and record the
alias relationship. **The token count counts concepts; the source list
keeps every site.** Counting both sides doubles a system's apparent size
and invents duplicate-token findings that describe the build step rather
than the design system.

Then derive the scope. Exclude by default, recording a reason for each:

- **`node_modules/`, `vendor/`, `third_party/`.** Dependencies.
- **Git submodules.** Read `.gitmodules`.
- **`dist/`, `build/`, `.next/`, `out/`, and compiled CSS carrying a source
  map.** Generated output — grade the source that produced it.
- **Test fixtures and starter templates.** Scaffolding for other people's
  projects.
- **Upstream plugins and themes.** In Discourse, `plugins/` holds both code
  this project wrote and code it installed. Tell them apart by presence in
  `.gitmodules`, the plugin's own `about.json` authorship, and
  `git log --oneline -- <path>` — an authored plugin has a history of its
  own changes, an installed one usually has a single vendoring commit.
- **Framework defaults**, unless the user asks for them.
- **Any path the project marks exempt.**

Leakage and usage analysis run against owned, reachable consumer styles
only. State the exact scope and the file count it resolves to *before*
measuring anything against it. A scope you cannot state is a scope you
cannot defend.

If more than one app in a monorepo plausibly qualifies, ask rather than
guessing. A guess here produces a complete-looking report graded against
the wrong application, and nothing downstream flags it.

## Job six — discover modes, and find out whether they resolve

Find every registered theme scheme and token override root: the declared
modes, the selectors or media queries that carry them, per-theme color
definitions, and any scheme-selection mechanism the framework provides.

Then answer one question per scheme: **does resolved output exist for it?**

- **Yes for every audited scheme** — grade `mode-completeness` normally, and
  record the resolved schemes in `discovery.resolved_modes`.
- **No for any scheme** — grade `blocked`, name the missing artifact, and
  say what would produce it. Never infer a pass from source declarations
  alone: a mechanism that exists proves a mechanism exists, and says
  nothing about whether every token has a value in every scheme.

`tools/validate_run.py` rule 3 fails an audit that grades
`mode-completeness` as anything but `blocked` while a declared scheme has
no resolved output.

## Recording the outcome

Record all six jobs in `assets/capability-map.yml`'s `discovery` block
before moving on. Then run:

```
python3 tools/validate_run.py .token-vitals/report.json --html .token-vitals/report.html
```

An audit that cannot pass those six rules is not ready to ship.
