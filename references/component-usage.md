# Component token usage

This report view answers a concrete adoption question: which UI ownership
units use the token system most, and which canonical tokens do they use?
It is a derived view, not a ninth vital and not a quality score.

## Universal component definition

Use the narrowest framework-neutral ownership unit the repository proves:

1. A component directory or file identified by the active framework profile.
2. A co-named group of component source, template and style files.
3. When neither exists, one stylesheet or template surface.

Group common, desktop and mobile variants only when owner and normalized name
match. Never merge units across plugins, packages or applications merely
because their filenames match. Record the inferred paths and confidence so a
reader can correct the boundary.

The base analyzer begins with files reachable from owned production roots.
An adapter may add `component_roots`, but only with `framework-registered`,
`import-graph verified` or `runtime-verified` evidence. Ownership by itself
does not prove a file ships. Adjacent files whose normalized names match are
grouped so patterns such as `Button.tsx`, `Button.module.css`,
`Button.component.ts` and `Button/index.tsx` describe one component rather
than unrelated surfaces.

## What counts as usage

Count a reference only when it resolves to a concept in the confirmed token
inventory. The base analyzer measures:

- CSS custom-property references such as `var(--surface-raised)`.
- Sass variable references such as `$space-sm`, excluding declaration
  left-hand sides.

Ignore references inside line, block and markup comments. Preserve line
numbers while stripping comments so every surviving evidence location still
points to the exact consumer line.

An adapter may additionally resolve Tailwind utilities, CSS-in-JS theme
accessors, generated classes, template helpers or runtime theme APIs. Record
each syntax separately as `measured`, `unmeasured` or `blocked`. A class that
looks token-like but has no proven mapping is unmeasured, never usage.

Exclude canonical and alias declaration sources from consumer counts. Keep
component-local overrides in scope: their references still show what the
component consumes even though their declarations are not canonical tokens.

## Ranking and output

Rank identified components by this stable order:

1. Canonical token reference occurrences, descending.
2. Distinct canonical tokens, descending.
3. Stable component key, ascending.

Render the first 20 identified components. If the repository proves fewer
than 20, fill the remaining positions with ranked stylesheet or template
surfaces and label that fallback explicitly. Never let a high-volume generic
surface displace an identified component from this view. For every row include rank, component or surface name,
kind, all contributing paths, total references, distinct token count, family
distribution and every referenced token. Each token carries its reference
count and real `file:line` locations. Put the same 20 records in JSON and
HTML; do not leave token details only in the working set.
Preserve the syntax used at each consumer so `$space-sm` is not presented as
`--space-sm`, and show both when a component consumes both projections.

Report the total number of identified components, additional measured style
surfaces, and how many components sit below the Top 20.
That remainder is not a hidden finding: Top 20 is intentionally a ranked
adoption view. The raw counts still make its selection reproducible.

## Reading the result

High usage is not automatically good or bad. It can mean a foundational
component correctly centralizes design decisions, or a broad component has
too much responsibility. Pair this view with tier integrity and lineage:

- Many semantic references with complete lineage indicate healthy adoption.
- Many primitive references indicate a tier-integrity risk.
- High reference volume with few distinct tokens often indicates a stable,
  repeated component pattern.
- High diversity across many families may identify a component worth
  splitting or documenting, but the report must present that as an
  investigation lead rather than a defect.
