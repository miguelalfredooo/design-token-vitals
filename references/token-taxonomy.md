# Foundational token families

The canonical list of what a design token layer is expected to cover, drawn
from what the major design systems treat as foundations — Material 3,
Carbon, Polaris, Primer, Fluent, Salesforce Lightning, Atlassian, Adobe
Spectrum, and the US Web Design System.

Discovery searches for every family here. The report says which were
measured and which were not, and `coverage` grades against the families
this project declares rather than against the whole list — a system that
never claimed a motion scale is missing nothing.

## Why a fixed list

Two runs that search for different families produce different coverage
grades on the same repository, and neither is wrong on its own terms. A
fixed list makes the search reproducible and makes an omission visible:
validation rule 5 fails an audit that skips typography or any family below
without recording why.

## The families

### Tier one — every system has these

| Family | Covers | Common names |
|---|---|---|
| `color` | Primitives, semantic roles, and state variants | `color`, `palette`, `colour`, `fill`, `bg`, `surface`, `content` |
| `typography` | Family, size, weight, line height, letter spacing, text case, text decoration, paragraph spacing | `type`, `font`, `text`, `typeset` |
| `spacing` | The space scale, and inset, stack and inline applications | `space`, `spacing`, `gap`, `padding`, `margin` |
| `sizing` | Component sizes, control heights, icon sizes, min and max widths | `size`, `dimension`, `measure` |
| `radius` | Corner radii, including the pill and circle ends of the scale | `radius`, `corner`, `rounded`, `border-radius` |
| `border` | Width, style, and the border color roles when separate from `color` | `border`, `stroke`, `outline`, `divider` |
| `elevation` | Shadows, and the elevation levels they express | `elevation`, `shadow`, `depth`, `boxShadow` |
| `opacity` | Alpha values used as system decisions | `opacity`, `alpha`, `transparency` |
| `layer` | Stacking order | `z-index`, `zIndex`, `layer`, `elevation-z`, `stacking` |
| `motion` | Duration, easing, delay, and named transitions | `motion`, `duration`, `easing`, `transition`, `animation` |
| `breakpoint` | The viewport thresholds the layout responds to | `breakpoint`, `screen`, `media`, `viewport` |

### Tier two — foundations the strongest systems define, and weaker ones leak

| Family | Covers | Common names |
|---|---|---|
| `grid` | Column count, gutter, margin, container max width, and the layout scale | `grid`, `column`, `columns`, `gutter`, `container`, `layout`, `wrapper` |
| `focus` | Focus ring color, width, offset, and style | `focus`, `focus-ring`, `outline-focus`, `ring` |
| `target` | Minimum hit area and touch target size | `target`, `touch`, `hit-area`, `min-target` |
| `state` | The state layer opacities and overlays for hover, focus, pressed, dragged, selected, and disabled | `state`, `state-layer`, `interaction`, `overlay` |
| `icon` | The icon size scale and stroke width, where separate from `sizing` | `icon`, `iconography`, `glyph` |
| `aspect` | Named aspect ratios | `aspect`, `ratio`, `aspect-ratio` |
| `blur` | Backdrop and layer blur radii | `blur`, `backdrop`, `frost` |
| `density` | The multiplier a system applies to switch between comfortable and compact | `density`, `scale`, `compact`, `comfortable` |

`grid` deserves the attention it rarely gets. Column counts, gutters and
container widths are system decisions as much as any color is, and a
codebase that tokenizes color perfectly and writes `max-width: 1280px` in
nine files has a real gap. Look for it explicitly.

## Primitive and semantic are recorded separately

Every family above can appear at two tiers, and they are graded differently
by `tier-integrity`:

- **Primitive** — a raw value with a descriptive name. `blue-500`,
  `space-4`, `font-size-3`.
- **Semantic or alias** — a role name pointing at a primitive.
  `color-action-primary`, `space-inset-comfortable`, `text-heading-lg`.

Record which tier each token sits at. A system with primitives alone has
no semantic layer for a component to reach for, and a system whose
components reach past the semantic layer into the primitives is what
`tier-integrity` measures.

## Measured, unmeasured, and absent

Three different states, and the report keeps them apart:

| State | Meaning | How it renders |
|---|---|---|
| Measured | The run found this family and counted it | The count, and the tokens |
| Unmeasured | The run could not resolve this family — an unreachable source, an uncompiled theme, a build step it could not run | Named as unmeasured, with what is missing |
| Absent | The project declares no tokens for this family | `not_applicable`, and nothing counted against the project |

Rendering an unmeasured family as `0` states that the project has none,
which is a claim the run never established. Validation rule 4 fails an
audit that does it.

## Applying this in discovery

For each family, search the candidate sources found in
`references/discovery.md` for its common names, in every source kind — CSS
custom properties, preprocessor variables and maps, JS and TS theme
objects, and JSON token files. Record per family:

- `state`: `measured`, `unmeasured`, or `absent`
- `count`: tokens found, where measured
- `tiers`: how many sit at primitive and how many at semantic
- `sources`: the source ids that define it
- `note`: what is missing, where unmeasured

A family found only in an unverified source is `unmeasured`, never
`measured` — reachability decides, the same as everywhere else.
