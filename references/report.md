# The report

One run of design-token-vitals produces three outputs, and each is built for
a different reader.

| Output | Path | Audience |
|---|---|---|
| Report | `.token-vitals/report.html` | People. Single self-contained file |
| Summary | stdout | Terminal output and PR comments |
| Working set | `.token-vitals/report.json` | Codemods, triage, and the future `contract` stage |

## Why the HTML file is self-contained

`.token-vitals/report.html` carries its own fonts, styles and markup in one
file — nothing loads from a server at read time. That is on purpose: you
attach it to CI as a build artifact, forward it by email, and open it on a
machine with no dev server running, and it renders the same way every time.

## Why HTML is the primary output

A token system communicates best rendered as the thing it describes. Your
color tokens read as color swatches, not hex strings in a list. Your type
scale sets each step at its real size, so a step that drifted off the ratio
is visible before you read a single number. Your spacing scale draws each
step to its actual width, so a missing step in the middle of the scale shows
up as a gap in a row of bars. A near-miss pair — a hardcoded value one shade
off a token that already exists — renders as two adjacent swatches, and your
eye catches the drift that a table of hex codes would hide. A mode gap shows
up as a red cell in a light/dark/high-contrast matrix. Near-miss drift
especially barely communicates in plain text: the whole finding is that the
difference is too small to describe in words, only to see.

Stdout and the JSON working set sit alongside the HTML, not in place of it.
Stdout gives you the same eight grades wherever a terminal or a PR comment
is already open. The JSON gives a codemod or a triage session everything the
HTML page could not fit on screen.

## Rendering tiers

The report changes shape as your token system grows. Every tier grades the
same eight vitals from `references/vitals.md` — what changes is how much
evidence renders inline versus rolls up into a count.

| Tokens | Tier ID | Treatment |
|---|---|---|
| Under 150 | `full` | Everything rendered |
| 150 to 600 inclusive | `collapsed` | Families collapsed by default, exceptions expanded, top-N tables |
| Over 600 | `family-only` | Family rows only, palette as ramps, modes as an exception report, full data in the JSON |

`full` is what a small system earns: every color as its own swatch, every
leakage finding as its own row, the whole mode matrix laid out top to
bottom. `collapsed` groups your tokens by family and opens only the
families with something wrong, because 400 tokens do not need 400 rows to
show you the dozen that matter. `family-only` stops listing individual
tokens altogether — a family row carries a count, a health indicator per
vital, and one real `file:line`, and your palette renders as ramps instead
of a wall of chips. The health indicator is five pips, one for each vital
that is meaningful per family: `tier-integrity`, `leakage`,
`mode-completeness`, `naming-coherence`, and `orphans`. `coverage`,
`single-source`, and `enforcement` grade the system as a whole rather than
any one family, so they do not appear in a family row.

### Two findings that only exist at scale

At `family-only`, two kinds of finding appear that a small system rarely
produces enough of to matter:

- **Outliers** — a color belonging to no ramp, added by hand outside the
  system that generated the rest of your palette. In a 20-token palette
  this is one odd swatch you would spot yourself. In an 840-token palette
  built from generated ramps, it hides in plain sight until the report
  groups the ramps and shows you what falls outside them.
- **Duplicates** — two token names that resolve to the same value, so
  whoever writes the next component picks between them at random. A
  handful of tokens makes this collision unlikely; a few hundred makes it
  close to certain, and once it happens your system carries two names for
  one decision with no way to tell which one is current.

## The two invariants

Every rendering tier, from `full` down to `family-only`, follows the same
two rules. They are what keeps a summarized report honest instead of just
shorter.

### Aggregate the count, never the evidence

A family row, a truncated table, and a "see all" details block can each
roll many findings into one number. None of them may roll away the
evidence: every rolled-up finding still shows at least one real `file:line`
you can open. A finding that cannot point at code is an opinion.

### Truncation is always declared

Whenever the report shows fewer rows than exist, it says so in the same
line: `Showing 12 of 247` — never a silent cut that leaves you assuming you
saw everything. This is the same principle behind `blocked` in
`references/vitals.md`: silence reads as a pass, and nothing in this report
is allowed to let silence do that job. A truncated section always names
where the rest lives — usually `.token-vitals/report.json`.
