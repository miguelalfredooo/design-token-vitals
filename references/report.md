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
is already open. The JSON is a machine-readable duplicate of exactly what
the HTML shows, plus the full detail behind every `<details>` disclosure in
it — see "The JSON duplicates the report" below. It gives a codemod or a
triage session the same findings in a shape a script can consume; it is
never where a finding lives and nowhere else.

## The JSON duplicates the report

Nothing in a run's findings exists only in `.token-vitals/report.json`.
Every finding the run produced is in the HTML report too — directly, if the
section is under the 40-row rule's cap, or behind a `<details>` element if
it is not. A reader who never opens the JSON still sees everything the run
found; the JSON exists so a codemod or a triage script can consume the same
findings without parsing HTML, not because the HTML left anything out.

This replaces an older framing of the two outputs — "the HTML is the
diagnosis, the JSON is the working set" — that read as license to move
content out of the report rather than disclose it inline. The JSON is a
duplicate with extra machine-readability, not a second, fuller destination.

## The inventory always renders

A token inventory is the tokens, shown — never a summary written about
them — at `full`, `collapsed`, and `family-only` alike:

- **Color** renders as swatches. Where token names form a ramp — `blue-50`
  through `blue-900` — render the ramp as one strip instead of ten separate
  chips; that compression is what a ramp rendering is for. A token that
  belongs to no ramp gets its own swatch. Every color token appears
  somewhere on the page, subject to the 40-row rule below, with the
  remainder disclosed in a `<details>` element.
- **Typography** renders as the scale itself: each step set at its real
  size, next to its token name.
- **Spacing and size** render as bars drawn to width, each one labeled with
  its token name and value.

A sentence may introduce or annotate what is rendered — calling out the
step that breaks the ratio, say — but a sentence never replaces the
rendering. "27 custom properties: a base size, up/down scale, rem scale,
and line heights" describes a type scale; it does not show one, and it
hides the exact thing a reader needs to see — the step that lands at 26px
when a 1.25 ratio from the step below says it should land at 25.

At `family-only`, the ramp form is what makes a large palette practical to
render in full: 840 colors as 840 individual swatches would be a wall of
chips, but the same 840 colors grouped into a few dozen ramps render as a
few dozen strips. The answer to a large palette is a better rendering,
never a smaller one — the inventory does not regress to prose as the
system grows, it compresses through a form built for exactly that.

## Rendering tiers

The report changes shape as your token system grows. Every tier grades the
same eight vitals from `references/vitals.md` — what changes is how much
evidence renders inline versus rolls up into a count.

| Tokens | Tier ID | Treatment |
|---|---|---|
| Under 150 | `full` | Everything rendered |
| 150 to 600 inclusive | `collapsed` | Families collapsed by default, exceptions expanded, tables under the 40-row rule |
| Over 600 | `family-only` | Family rows only, palette as ramps, modes as an exception report, tables under the 40-row rule |

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

## Deriving the next-steps list

Eight grades and three leakage tiers are more than most readers can turn
into a plan on their own. The `next-steps` region orders the findings
already in the report into a concrete list of actions, so two runs against
the same repository always produce the same plan.

Order by class first, then by blast radius descending within each class:

1. **Unblock measurement.** Any vital graded `blocked` comes first — you
   cannot improve what you cannot measure. For `enforcement` specifically,
   a single rule both unblocks the check and stops every other finding in
   the report from regressing, so a `blocked` enforcement grade earns the
   first action even when another vital's raw finding count is larger.
2. **Mechanical fixes.** `redundant` leaks from `references/leakage.md` —
   a token already holds the value, so no judgment is required, only a
   swap. Rank these by blast radius, highest first.
3. **System gaps.** `uncovered` leaks and any category missing from
   `coverage`. Someone has to decide on a token here, and that one
   decision typically unblocks many findings at once.
4. **Judgment calls.** `near-miss` drift and naming-coherence
   reconciliation. These need a person to decide what was intended, so
   they carry the least certainty and sort last.

Show every action up to 40, ranked in the order above. Past 40, apply the
40-row rule below: render the first 40 and put the remainder in a
`<details>` element right after the table, declaring the truncation the
same way every other truncated section does — "Showing the 40
highest-impact of `<n>` actions" — never a silent cut.

An action must carry a real `file:line`, the same evidence rule as every
other finding in this report. An action with no reachable instance to
point at does not appear on the list.

## The two invariants

Every rendering tier, from `full` down to `family-only`, follows the same
two rules. They are what keeps a summarized report honest instead of just
shorter.

### Aggregate the count, never the evidence

A family row, a truncated table, and a "see all" details block can each
roll many findings into one number. None of them may roll away the
evidence: every rolled-up finding still shows at least one real `file:line`
you can open. A finding that cannot point at code is an opinion.

### The 40-row rule

Every section that lists findings — leakage's three tiers, orphans, mode
gaps, duplicates, outliers, the family table, the color inventory, the
next-steps plan, and any other row-based table this report produces —
shows every row up to 40. Past 40, render the first 40 by the section's own
ranking or ordering, and put the remainder in a `<details>` element on the
same page: closed by default, its `<summary>` naming the count, open and
the rest is right there. The remainder is one disclosure away, never in
another file.

A summary that withholds what would have fit on the page costs the reader
a second tool for no reason. Truncation exists to stop a genuine wall of
noise from swamping the page — a codebase with 1,645 leaked values needs
it. Twenty-four leak groups, seventeen orphan names, or seven next-steps do
not: a reader takes in 24 rows in about the time it takes to scroll past
them, so a cap tuned for the 1,645-finding case has no business firing on
the 24-row one. Where a section below refers to "the 40-row rule," this is
the rule it means.

### Truncation is always declared

Whenever a section shows fewer rows than the 40-row rule above capped it
to, it says so in the same line: `Showing 40 of 247`. This is the same
principle behind `blocked` in `references/vitals.md`: silence reads as a
pass, and nothing in this report is allowed to let silence do that job. A
truncated section always names where the rest lives: the `<details>`
element immediately below the truncation line — never a pointer to another
file.
