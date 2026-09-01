# Principles

What every skill in this family holds itself to. Written once, copied into
each skill verbatim, and pointed at from its `SKILL.md`. A skill that
cannot say how it meets one of these has found its next piece of work.

Each principle names what it forbids and how it is checked, because a
principle nobody can check is a mood.

## The eight

### 1. Render the thing as itself

A color is a swatch. A type step is set at its size. A spacing step is a
bar drawn to width. A ranking is a bar drawn to its score. The reader's
eye catches what a table of numbers hides, and a near-miss between two
shades only communicates when the two shades sit side by side.

**Forbids:** a hex string where a swatch would do; a number where a
specimen would do; a table for data that has a shape.
**Checked by:** the density rules in `references/report.md`, and a review
of any new region against the form table there.

### 2. Say what is worst first

The reader came to learn one thing: what is wrong, how much it touches,
and what to do first. That goes at the top, in a sentence. The inventory,
the evidence, and the detail follow, and they are there for the reader who
keeps going.

**Forbids:** a report that opens with an inventory; a terminal summary
that lists what the report contains.
**Checked by:** the executive summary's four questions; a terminal summary
of five lines or fewer.

### 3. Orient every section: what, why, what to do

Every section opens by answering three things before showing anything:
what you are looking at, why it matters, and what to do with it. Then it
stops orienting and shows the data. A reader who arrives at a section from
a link gets the same three answers as one who read the whole page.

**Forbids:** a table with no lede; a lede that explains and never says
what to do next.
**Checked by:** `tools/test_template.py` asserts every section carries an
eyebrow, a heading and a lede.

### 4. Explain once, at first need, then trust the reader

A term gets one sentence the first time it appears, at the point the
reader needs it, using the real vocabulary — semantic token, primitive,
mode, ramp, orphan. Then it is never explained again. Talking down is
re-explaining, hedging, and softening. Nothing is anyone's fault: an
uncovered value is a gap in the system and never a mistake by whoever
wrote the component.

**Forbids:** re-explaining; the words on the banned list in
`references/voice.md`; a definition that lives only in a hover tooltip.
**Checked by:** `tools/check_voice.py`; the print stylesheet, which
renders every tooltip inline.

### 5. Show the arithmetic

Every ranking shows its inputs beside its result, so a reader who
disagrees with the order can see which input drove it and an agent can
re-rank on its own weights. A number the reader cannot take apart asks
for trust the report has not earned.

**Forbids:** an opaque score; a composite of any kind, ever; a rank with
no visible inputs.
**Checked by:** `findings.priority()` returns its inputs with its score;
the executive summary and the maturity stage carry no number.

### 6. Never let unknown read as zero

Measured, unmeasured, and absent are three different claims, and the page
keeps them apart. A category the run could not resolve says so and names
what would resolve it. Silence reads as a pass, and nothing in the report
may let silence do that job.

**Forbids:** `0` for a family the run did not measure; a grade on a mode
with no resolved output; a summary quiet about what was blocked.
**Checked by:** `validate_run.py` rules 3 and 4; the confidence split in
the executive summary.

### 7. Rules in code, teaching in prose

A rule an agent has to remember drifts. A rule a tool checks holds. Prose
exists for the reader — to orient, explain, and motivate — and every
sentence in it that is secretly a rule belongs in a test instead. The
skill grew 86% in prose in one day and its reproducibility fell from 8 of
8 to 7 of 8; this is the principle that day taught.

**Forbids:** a "must" or "never" in `SKILL.md` with no test behind it; a
pull request that grows `SKILL.md` or `references/` without re-measuring.
**Checked by:** the word count of `SKILL.md` and `references/` may not
rise across a pull request without two fresh blind runs recorded in the
changelog.

### 8. Say where they are and where next is

A grade describes a position. Momentum needs a direction and a distance.
The report names the stage the system is at, the one threshold that moves
it, and what crossing that threshold costs — never as a number, always as
a structural fact the reader can check against the grades.

**Forbids:** a grade with no next threshold; impact with no effort; a
healthy system with nothing to read.
**Checked by:** the stage line in the executive summary; an effort class
beside every fix-queue entry; a next action on every run, including one
that finds nothing wrong.

## The section pattern

The three orienting lines, in order, before any data:

| Line | Answers | In the template |
|---|---|---|
| Eyebrow | What am I looking at | `.eyebrow` |
| Heading and lede | Why it matters | `h2` and `.lede` |
| The move | What to do with it | the lede's last sentence |

A section that cannot fill the third line is describing something the
reader has no use for, and that is a reason to cut the section rather
than to leave the line out.

## Adopting these in a new skill

Copy this file. Keep the eight and the section pattern as written. Replace
each "Checked by" with the mechanism in the new skill that does the
checking, and where there is none yet, say so in that line rather than
deleting it. The gaps are the roadmap.

Run `tools/check_voice.py` against this file after every edit. It bans a
handful of words that sound strong and mean nothing, and this document
has to pass the same lint it recommends.
