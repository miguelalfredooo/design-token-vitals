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

A token system communicates best rendered as the thing it describes —
principle 1 in `PRINCIPLES.md`. A near-miss pair especially cannot be
described in words, only shown: two adjacent swatches, one shade apart.
Stdout and the JSON sit alongside the HTML and never in place of it.

## The JSON duplicates the report

Nothing in a run's findings exists only in `report.json`. Every finding is
in the HTML too, in whatever form fits its volume or behind a `<details>`
for the tail of a very large section; the JSON exists so a script can
consume the same findings without parsing HTML — see "Truncation is always
declared, and never silent" below.

## The inventory always renders

A token inventory is the tokens, shown — never a summary written about
them — at `full`, `collapsed`, and `family-only` alike:

- **Color** renders as swatches. Where token names form a ramp — `blue-50`
  through `blue-900` — render the ramp as one strip instead of ten separate
  chips; that compression is what a ramp rendering is for. A token that
  belongs to no ramp gets its own swatch. Every color token appears
  somewhere on the page, in whichever of those forms its volume calls
  for — see "Change the mark, don't cut the data" below.
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
| Under 150 | `full` | Everything rendered in its sparse form: rows, labeled swatches, the whole mode matrix |
| 150 to 600 inclusive | `collapsed` | Families collapsed by default, exceptions expanded, listings in their dense form |
| Over 600 | `family-only` | Family rows only, palette as ramps, modes as an exception report, listings in their densest form |

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

Eight grades and four leakage tiers are more than most readers can turn
into a plan on their own. The `next-steps` region orders the findings
already in the report into a concrete list of actions, so two runs against
the same repository always produce the same plan.

Order by class first, then by blast radius descending within each class:

1. **Unblock measurement.** Any vital graded `blocked` comes first — you
   cannot improve what you cannot measure. For `enforcement` specifically,
   a single rule both unblocks the check and stops every other finding in
   the report from regressing, so a `blocked` enforcement grade earns the
   first action even when another vital's raw finding count is larger.
2. **Verified mechanical fixes.** `redundant` leaks from
   `references/leakage.md` — both the value and the semantic role match, so
   no judgment remains. Rank these by blast radius, highest first.
3. **System gaps.** `uncovered` leaks and any category missing from
   `coverage`. Someone has to decide on a token here, and that one
   decision typically unblocks many findings at once.
4. **Judgment calls.** Exact-value candidates, `near-miss` drift, and
   naming-coherence reconciliation. These need a person to decide what was
   intended, so they carry the least certainty and sort last.

Show five actions. This is the one section in the report where a small
fixed number is correct, because its value comes from what it leaves out:
forty actions is a backlog, and five is a plan. Every finding behind those
five is still in the report — in the inventory, the leakage tiers, and the
mode and orphan sections, all of which enumerate. This section ranks, and
ranking past the point a reader will act costs them the ordering they came
for.

Where fewer than five actions exist, show what there is. Never pad the
list to reach five.

An action must carry a real `file:line`, the same evidence rule as every
other finding in this report. An action with no reachable instance to
point at does not appear on the list.

## At a glance

Above the executive summary, one strip a reader takes in without reading:
the stage as a six-tick ladder, the eight grades as one segmented bar,
confirmed against blocked and unmeasured as another, leakage's four tiers
as a third, the automatable share of the fix queue as a ring, and the
token and family counts as tiles. Every mark carries its number; nothing
is decorative. Inline SVG and CSS only — the report ships no script.

## Decisions this run made

Every close call the run flagged in a `note` — the kind that could have
gone the other way — rendered as its own region rather than buried. Each
line names the decision, what it moved, and the other reading. The reader
becomes the tiebreak, the report stops claiming certainty it lacks, and
the next run inherits an answer. The stage line sits in the executive
summary; see `references/maturity.md`.

## The executive summary

The first thing on the page, answering four questions in this order:

1. **What is the highest-impact problem?** One sentence, naming the finding
   or the vital, with its blast radius.
2. **How many owned files and components does it affect?** Counts, from the
   scope Stage 1 derived.
3. **What should be fixed first?** The top entry from "Where to start",
   restated with its `file:line`.
4. **Which results are confirmed, and which are blocked or unmeasured?**
   The count at each, and what each blocked result is waiting on.

Question four carries equal weight with the other three. A summary that
reports six confirmed grades while staying quiet about two blocked ones
describes a healthier system than the run established, which is the failure
this whole skill exists to avoid.

## Ranking by remediation priority

Four inputs, all of them recorded and rendered next to the score:

| Input | Symbol | What it is |
|---|---|---|
| Occurrences | `n` | How many times the value appears |
| Affected owned files | `f` | How many owned files hold it |
| Breadth | `b` | Distinct components, plugins, routes or bundles it crosses |
| Confidence | `c` | Confidence in the proposed fix, as a multiplier |

```
priority = (n + 2f + 3b) x c
```

| Confidence | `c` |
|---|---|
| `compiled-runtime verified` | 1.0 |
| `exact static match` | 0.95 |
| `import-graph verified` | 0.9 |
| `manual review` | 0.4 |

Files outweigh occurrences because ten occurrences in one file is one edit.
Breadth outweighs both because a value crossing six components is a missing
system decision rather than a local slip. Confidence multiplies rather than
adds, so a high-volume finding nobody can safely change cannot rank first
on volume alone.

**Show the inputs, never only the score.** A reader who disagrees with the
order needs to see which input drove it, and an agent consuming the JSON
re-ranks on its own weights rather than trusting a number it cannot take
apart. `tools/findings.py` implements this; two runs rank identically
because the formula is fixed.

## The fix queue

Every finding safe enough to act on mechanically, in both HTML and JSON.
Per entry:

| Field | Content |
|---|---|
| `id` | The stable finding id |
| `literal` | The current literal or token |
| `replacement` | The canonical replacement token |
| `locations` | Affected files, each a real `file:line` |
| `occurrences`, `files` | The counts behind the ranking |
| `confidence` | `exact static match`, `import-graph verified`, `compiled-runtime verified`, or `manual review` |
| `semantic_role_verified` | Whether evidence proves the token expresses the consumer's decision, not merely the same value |
| `safe_to_automate` | Whether the swap needs a person |
| `effort` | `S` automatable under ten files · `M` automatable across more, or one file needing a call · `L` needs a decision first. Derived, never an hour estimate |

**Safe to automate requires `redundant`, `semantic_role_verified: true`, and
a confidence other than `manual review`.** An exact static value match alone
is never enough: identical colors and dimensions can represent different
semantic decisions. Exact-value candidates, near-miss drift, and uncovered
values are never automatable. `tools/validate_run.py` rule 7 fails a queue
that says otherwise.

Order the queue by priority. Lead with verified color replacements where
they exist. Keep exact-value candidates in a separate review list so a
follow-on agent cannot mistake matching values for permission to edit.

## Grouping by owner

Findings group by literal value, and **also** by owning component, plugin,
and route or bundle. An engineer owns a component, not a hex code, and
starting from the component is how token debt gets paid down in practice.

Each group carries its own counts and its own priority ordering, and every
finding appears in both views. A finding the value view holds and the owner
view drops is a finding whose owner nobody can find.

## Token lineage

Trace the chain wherever it can be traced:

```
primitive definition -> semantic alias -> custom-property projection -> consumer usage
```

Lineage is what separates an intentional semantic alias from a duplicate
definition. Two names for one value **with** a lineage edge between them is
a system working as designed. Two names **without** one is the duplicate
that `single-source` exists to catch. Grading them the same way reports a
healthy alias layer as drift.

Typography is where this matters most and shows least: a type scale often
runs primitive size to semantic role to a projected custom property to a
utility class, and a flat token list renders that four-link chain as four
unrelated tokens.

Record each link with its source id, and say where a chain could not be
completed rather than inferring the missing link.

## The coverage matrix

`entry bundle x theme or mode x token family`, covering at least color,
typography, spacing, radius, border, elevation, opacity, z-index,
breakpoint and motion.

Every cell is `measured`, `unmeasured`, `not_applicable` or `blocked`, and
carries its evidence. A gap in what the run could see becomes a shape on
the page rather than an absence a reader has to notice.

For a framework that registers several bundles separately, the bundle axis
is those bundles. A Discourse tree would run `common`, `desktop` and
`mobile` against light and dark. **That shape is a worked example and it is
unverified** — the Discourse adapter is still held pending a real checkout,
so treat it as the shape rather than as a tested path.

## Uncertainty is first-class

- **An unknown never renders as zero, passing, or complete.**
- **Confirmed findings are visually separated** from blocked and unmeasured
  areas, rather than sharing a table with them.
- **Every blocked or unmeasured result names the missing artifact** and what
  would produce it.

This is the measured / unmeasured / absent split from
`references/token-taxonomy.md`, applied to every part of the report.

## Trend

Findings carry stable ids, so two runs across two commits can be compared:

```
python3 tools/trend.py baseline.json current.json
```

It reports new findings, resolved findings, count changes, and regressions
— a regression being a resolved id that came back, or a count that grew.

**The comparison is gated** on framework, adapters, owned paths, scan scope
and token sources. Two runs that scoped differently answer different
questions, and a diff between them reads as progress without being
progress. The tool refuses and names the diverged input.

Baselines are passed explicitly. The skill never writes state into the
repository it audits. Commit `.token-vitals/report.json` and any past
commit becomes a baseline.

## Reproducibility metadata

Required in both HTML and JSON, in the measurement section:

- report schema version, and the skill and adapter version
- framework detection evidence
- discovered entry points and import roots
- token sources, with classification and reachability
- exclusions, each with its reason
- the exact scan scope and its file count
- the commit ref
- the timestamp

Most of this lands in `discovery` and `run` already. Listing it here makes
it required rather than customary, and gives a follow-on agent one place to
read the run's provenance from.

## The invariants

Every rendering tier, from `full` down to `family-only`, follows the same
rules. They are what keeps a dense report honest instead of merely shorter.

### Aggregate the count, never the evidence

A family row, a grouped leak row, and a `<details>` disclosure can each roll
many findings into one number. None of them may roll away the evidence:
every rolled-up finding still shows at least one real `file:line` you can
open. A finding that cannot point at code is an opinion.

### Change the mark, don't cut the data

When a section outgrows its form, move to a denser form. Do not show fewer
findings.

Two hundred colors as table rows is unreadable. The same two hundred as
swatches in a grid is one screen and completely readable. Too many rows was
never a problem about quantity — it was a problem about using a low-density
mark for the data. A rule that says "when there is more data, show less of
it" hands a designer a summary of a summary, and the thing they opened the
report to see is the part it dropped.

Pick the form from the volume:

| Data | Sparse form | Dense form | Denser still |
|---|---|---|---|
| Color | rows | swatch grid (~300) | ramps (~1000) |
| Typography | rows | specimens set at real size (~40) | — |
| Spacing and size | rows | bars drawn to width (~60) | — |
| Leaks | rows | grouped by token, count as a bar (~200 groups) | distribution plus outliers |
| Orphans | rows | inline chip list (~300) | grouped by family |
| Mode gaps | matrix | coverage bar plus exception list | — |
| Families | rows | rows with a health strip (~60) | grouped by namespace depth |

The capacities are guidance for choosing a form. They are never a cap on
what the reader sees. `assets/report-template.html` carries markup for
every form in this table; the fill stage picks one per section and records
the choice in `rendering.forms`.

Disclosure is the last resort. When a section exceeds even its densest
form, a `<details>` element holds the tail — the small, low-blast-radius
remainder — and never the majority.

### Compress what is systematic, enumerate what is exceptional

This is what makes the compression lossless.

If 190 of your 208 colors form ordered ramps and 18 do not, the ramps
compress to a dozen strips without losing anything, because the ramp's
structure is the information. The 18 outliers get enumerated one by one,
because each is a separate fact that compresses into nothing.

The same split applies everywhere. A spacing scale that follows a ratio
renders as a sequence, and the one step that breaks the ratio gets called
out. A leak found in 84 files is one row with a count; 84 leaks each found
once are 84 facts.

Systematic data has a compact visual form. Exceptions never do.

### Characterize whatever you do not show

`Showing 40 of 1,645` says nothing about the 1,605. Describe the hidden set
instead:

> The remaining 1,605 are single-file occurrences of these 12 values.

That tells the reader the shape of what they are missing and whether they
need to look. Counts stay prominent even when instances do not fit, and a
distribution — how many findings touch how many files — shows the shape
when the instances cannot.

The slot template for this line lives in `references/voice.md` under
`truncation`. Fill its `{summary}` slot with a real characterization of the
remainder, never with a restatement of the count.

### Inventory enumerates; the plan curates

These are different jobs and they take opposite rules.

**Inventory sections owe the reader everything.** Every color, every step,
every orphan, every leak group, in whatever form fits. `inventory-color`,
`inventory-type`, `inventory-space`, `families`, the four leakage tiers,
`modes-gaps`, and `orphans` all enumerate.

**"Where to start" owes the reader the few that matter, in order.** The
`next-steps` region shows five. See "Deriving the next-steps list" above.

### Truncation is always declared, and never silent

Whenever a section holds back any part of what the run found, it says so on
the page, in the `truncation` slot from `references/voice.md`, and it names
where the rest lives — the `<details>` element immediately below, never a
pointer to another file. This is the same principle behind `blocked` in
`references/vitals.md`: silence reads as a pass, and nothing in this report
is allowed to let silence do that job.

**The HTML may collapse, and it may never hold less than the JSON.** Long
evidence goes behind a `<details>` element, and every finding id present in
`report.json` appears somewhere in `report.html` — collapsed is fine,
absent is not. `tools/validate_run.py` rule 8 compares the two and fails on
any id the HTML omits, so this stays a checked property rather than an
intention.

## Table width and long paths

A report that scrolls sideways on every table is unreadable on the machine
it gets opened on, and the cause is usually the same two declarations:

- a fixed `min-width` on the table, which forces a width regardless of
  content
- `white-space: nowrap` on `.path`, which stops the widest column from ever
  wrapping

Together they fit a 44-character path during development and overflow on an
88-character one in the field. Neither declaration is in
`assets/report-template.html` any more. A table sizes to its container, and
a path wraps.

**Elide the shared prefix.** Every row in a leak table tends to begin with
the same directory. Show that prefix once above the table, in a
`<p class="prefix">`, and render each row as its distinctive tail:

```
plugins/acme-layout-and-styles/assets/stylesheets/
  common/share-community-feed-cta.scss:4
  common/fkb-c-topic.scss:270
```

That is compress-what-is-systematic applied to paths, and it makes the
table narrower and more readable at once rather than trading one for the
other. Apply it where a shared prefix actually exists across the rows —
with three rows sharing a short directory there is nothing systematic to
compress, and the prefix line costs more than it saves.

Where you want a wrap to land on a separator rather than mid-segment, emit
`<wbr>` after each `/` in the path.
