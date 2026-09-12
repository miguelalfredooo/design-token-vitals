# The Tailwind utility adapter

**Status:** design, approved 2026-09-12. Working document — prune it when the
work ships, the way #18 pruned the specs that had stopped participating in the
skill.

## 1. The finding this closes

On a repository whose consumption path is Tailwind utility classes, this tool
reports adoption near zero and is not wrong about anything it measured. It is
blind to the only syntax that repository uses.

`analyze_component_usage.references_in_text()` recognizes two syntaxes:

```python
CSS_REFERENCE  = re.compile(r"var\(\s*--([a-zA-Z0-9_-]+)")
SCSS_REFERENCE = re.compile(r"(?<![\w-])\$([a-zA-Z0-9_-]+)")
```

A component written as `<div className="bg-muted text-muted-foreground">`
matches neither, so it contributes no references, and its file counts as one
that does not use tokens. The run then declares the blindness honestly —
`{"syntax": "framework-generated-utility", "state": "not-visible"}` — which is
the correct answer and an unhelpful one.

There is a second, sharper consequence. `audit_literal_colors.audit()` skips
every path outside a stylesheet:

```python
if path in source_paths or os.path.splitext(path)[1] not in (".css", ".scss", ".sass", ".less"):
    continue
```

So `className="bg-[#0F8A83]"` in a `.tsx` file is not merely uncounted, it is
unreachable. A repository can hold dozens of bracket-arbitrary literals and
still receive a clean leakage result. Both halves of that sentence are true at
once, and a reader has no way to tell. That single `continue` is the mechanism
behind the paradox deferred out of #29.

## 2. What the adapter is, and is not

**It is a name-resolution layer over concepts discovery has already found.**
`discover_tokens.py` records `--color-muted` as the concept `color-muted`
(`normalize()` strips leading dashes and lowercases). The adapter's whole job
is to know that the class `bg-muted` names that concept. Families, alias
chains, grades and roadmaps then work unchanged.

**Never a second parser.** It reads no token file of its own. If discovery did
not find a concept, the adapter cannot resolve to it, and says so.

**Never a Tailwind emulator.** It does not expand utilities into CSS,
evaluate JavaScript, run plugins, or attempt arbitrary properties. It maps a
class name to a theme key or declines.

### Resolution stops at the theme key, deliberately

`bg-background` resolves to `color-background` and stops. The existing alias
machinery walks `--color-background: var(--background)` onward to whatever
canonical token sits at the end, exactly as it does for a `var()` reference
written by hand. A utility must behave like the syntaxes already counted rather
than get a private path to the answer, or two runs of the same repository
through different syntaxes would disagree about where a reference landed.

## 3. The module

`tools/tailwind_adapter.py`. Four pure functions, no I/O of its own — callers
pass in text, and the discovery record supplies paths.

### `detect(root, discovery) -> ThemeSource | None`

v4: an `@import "tailwindcss"` or an `@theme` block in a stylesheet discovery
already reached. v3: a `tailwind.config.*` at a discovered root (designed for,
not built — §8). Returns the theme source path, the framework version read from
the lockfile or `package.json`, and which shape was detected. Returns `None`
when nothing matches, and every downstream behavior below is conditioned on
that `None`.

### `theme_map(theme_text, default_theme_text) -> {namespace: {key: concept}}`

Every `--namespace-key` declared in the project's `@theme`, merged over the
installed version's default theme read from `node_modules/tailwindcss/theme.css`
— which is 419 plain-CSS declarations in tailwindcss 4.2.1, the version measured while writing
this, so the framework-default check `references/adapters/tailwind.md` already
requires stops being a manual step.

Project declarations win over defaults. A default-theme key that the project
never overrides still resolves, because the utility it generates is real.

### `resolve(class_name, theme_map) -> Resolution`

A `Resolution` is one of: a concept id, `AMBIGUOUS`, or `None`. Peeling order,
which is also the test order:

1. strip variants — everything before the last unbracketed `:` (`dark:`,
   `hover:`, `md:`, `group-hover:`, and stacked combinations);
2. strip a trailing opacity modifier (`/50`, `/[.06]`);
3. strip `!` in either position;
4. strip one leading `-` (negative utilities) and remember it;
5. split the remainder into the longest utility prefix that the table knows and
   a key;
6. look the key up in every namespace that prefix draws from.

### `classify(class_name) -> Leak | None`

Bracket-arbitrary values, in three kinds:

| Spelling | Kind | Why it matters |
|---|---|---|
| `bg-[#0F8A83]`, `p-[15px]` | `literal` | A raw value on a path the token layer was supposed to own |
| `bg-[--brand]` | `redundant` | Compiles to invalid CSS and is dropped with no error. The element ships unstyled and nothing warns |
| `bg-[var(--brand)]`, `bg-(--brand)` | not a leak | A reference. Clears the bar |

`redundant` is reported first among leaks. It is the only finding here where
the page is already visibly broken.

## 4. Two resolution rules that are not obvious

### Ambiguity is a feature, not an edge

In v4 the prefix `text-` draws from two namespaces: `--text-*` (font size) and
`--color-*`. `text-muted-foreground` is a color; `text-sm` is a size; a project
that declares both `--text-brand` and `--color-brand` has written a class whose
meaning depends on Tailwind's internal ordering.

When exactly one namespace holds the key, resolve. When more than one does,
return `AMBIGUOUS`, **count it as nothing**, and report it under its own
heading with the competing candidates named. A guess here would be a reference
attributed to the wrong family, which is worse than a reference not counted —
and worse still because it would look like a measurement.

### A derived scale is one token, and a step off it has no name

`--spacing: 0.25rem` is a namespace *root*, not a keyed namespace. Tailwind
multiplies it, so `p-4` is the multiplier times four and names nothing of its
own. This repository has already ruled on exactly that shape: `fixtures/README.md`
holds `20px` as `uncovered` and never `redundant`, because "a derived scale is
one token, the multiplier, and a step generated from it has no name to swap to."

The adapter follows the existing ruling rather than inventing a second one.
`p-4` resolves to the `spacing` concept — the multiplier is a real token and the
utility really does consume it — but the reference is recorded as **derived**,
so no report can offer it as a named token to swap to. A project that declares
`--spacing-lg` gives `p-lg` an ordinary keyed resolution. The two must never be
conflated in one count, or a derived step would inflate named adoption.

## 5. Where it plugs in — three call sites

1. **`analyze_component_usage.references_in_text()`** gains a third branch
   emitting `(concept, line, "tailwind-utility")`. It scans **string literals in
   source files**, not only `className="…"`, because `cn("bg-muted", cond &&
   "text-foreground")` is the dominant idiom in real code. A match requires an
   exact theme-key hit, which makes a stray prose string very unlikely to
   resolve — see the guard for "very unlikely" in §9.
2. **`analyze_component_usage.analyze()`'s `measurement` block** flips
   `framework-generated-utility` from `not-visible` to `counted` **only when
   `detect()` returned a source**, carrying that source path and the version as
   evidence. When it returns `None` the existing wording stands, untouched.
   `render_component_usage.py` already partitions measured from incomplete, so
   the report follows without a renderer change.
3. **`audit_literal_colors.audit()`** accepts utility-bracket literals from
   source files as an additional origin for its existing finding groups, tagged
   with their own tier so a JSX bypass is never silently averaged into a
   stylesheet one. The stylesheet `continue` stays exactly as it is for
   everything else; this adds a second, explicitly-scoped intake rather than
   widening the first.

## 6. The honesty contract

The utility-prefix to namespace mapping cannot be derived. It exists only
inside Tailwind's minified distribution chunks, and parsing those would be
brittle in a way this tool has no way to detect when it breaks. So the table is
authored — and made falsifiable instead of trusted:

- **A guard asserts every namespace the table names exists in the installed
  `theme.css`.** A namespace invented or misspelled fails the suite.
- **The run reports every namespace present in the installed default theme that
  the table does not cover**, so an unresolvable utility is declared rather than
  counted as zero. Namespaces measured in the installed 4.2.1 default theme, from its 419
  declarations:
  `color` (288 declarations), `text` (31), `container` (13), `font` (12),
  `shadow` (9), `radius` (9), `blur` (8), `drop-shadow` (7), `tracking` (6),
  `perspective` (5), `leading` (5), `breakpoint` (5), `animate` (4),
  `inset-shadow` (3), `ease` (3), `max-width` (1), `aspect` (1), and `spacing`
  (1), which is the derived-scale root of §4 rather than a keyed namespace.
- **Not every namespace is a utility namespace.** `--default-*` configures
  Tailwind itself and generates no utility; `--breakpoint-*` generates variants,
  not classes. The coverage report distinguishes *not covered* from *not a
  utility namespace*, because collapsing the two would make the report
  permanently and falsely incomplete.
- **The version is recorded** in `run.framework_versions`, which
  `references/adapters/tailwind.md` already demands and no tool has been able to
  satisfy mechanically until now.

## 7. Error handling and refusal

Every failure degrades to the state that existed before the adapter, never to a
guess:

| Condition | Behavior |
|---|---|
| No Tailwind detected | Adapter does not run. Every output byte-identical to today |
| Detected, `node_modules/tailwindcss` absent | Resolve against the project `@theme` only; the coverage report says the default theme was not readable and names the version it could not check |
| Detected, version unreadable | Resolve; record the version as `unrecorded` and say so in evidence. Never invent one |
| A class resolves to a concept discovery never found | Not a reference. Counted under unresolved, with the key named |
| Theme block unparseable | Adapter reports `not-visible` with the parse failure as evidence — the state it already has, now with a reason |

## 8. Tailwind v3 — designed for, not built

v3 puts the theme in `tailwind.config.*`, commonly by importing JavaScript
token modules and spreading them into `theme.extend`. Resolution there is the
same problem with one extra hop: bind an imported identifier to a theme key,
then map the dotted concept path discovery already produced (`colors.brand.500`)
onto the dash-joined utility suffix (`bg-brand-500`), dropping a `DEFAULT` key.

It is not built here because no repository in reach needs it, and because a
config that computes its theme cannot be read statically at all — the adapter
would have to decline for exactly the repositories most likely to want it. The
`detect()` return shape carries the shape it found so that adding v3 later is
an addition and not a redesign.

## 9. Testing

The fixture repository already pins `tailwindcss 4.3.0` for this purpose. It
gains:

- a component consuming utilities that resolve, including one behind a `dark:`
  variant and one with an opacity modifier;
- a `node_modules/tailwindcss/theme.css` stub, so the default-theme merge is
  exercised rather than assumed;
- a project `@theme` declaring both `--text-brand` and `--color-brand`, so the
  ambiguous case has a fixture;
- a derived step (`p-4`) beside a named one (`p-lg`, from a declared
  `--spacing-lg`), so the two are proven to count differently;
- all three bracket spellings from §3;
- a string literal that looks like a utility but names no theme key, proving
  the scanner declines it.

Guards follow this repository's own rules. Each is watched failing **by exit
code**. Each mutation is injected in both spellings a person might write, and
checked for whether it could actually bite rather than merely apply. And per
the standing rule about perceptual work, the assertions are written as
**variety, not presence**:

- not "the adapter resolves classes" but **no two namespaces resolve to the
  same concept**;
- not "ambiguity is handled" but **the ambiguous class resolves to nothing, and
  specifically not to the first candidate**;
- not "leaks are found" but **the three bracket spellings produce three
  different verdicts**;
- not "spacing resolves" but **a derived step and a named step land in
  different counts**.

One guard exists only for the false-positive risk in §5: a fixture file
containing prose that includes a utility-shaped word must contribute zero
references. If that guard ever fails, the scanner is widened, not the fixture.

## 10. Blast radius

Adoption, component usage and the ranked top-20 move on any Tailwind
repository. Leakage gains a JSX-bypass tier. The nineteen validation rules are
re-run against the regenerated example; any that shift are explained in the PR
rather than adjusted.

`examples/shadcn-ui/` is regenerated, because shadcn is a Tailwind codebase and
shipping the old numbers beside an adapter that changes them is the exact
staleness #29 fixed.

**Privacy.** design-token-vitals is public. The local proving ground for this
work is a private repository, so it supplies figures quoted in the pull request
and nothing else. The committed fixture and the committed example stay
synthetic. This repository has paid for that lesson once already, in #21.

## 11. Out of scope

Named here so they are declined on purpose rather than forgotten:

- theme keys no utility ever uses (orphans from the Tailwind side);
- `dark:` variants whose underlying property has no dark definition (mode gaps);
- arbitrary properties (`[mask-type:luminance]`);
- plugin-generated utilities;
- `@apply`;
- Tailwind v3.

Each would move a further vital. The scope approved for this work is
resolution plus leaks.
