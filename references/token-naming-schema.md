# The naming grammar

`references/token-taxonomy.md` says what a token layer should cover.
This says how the run reads the way a system spells those tokens, and
grades `naming-coherence` against it.

The measurement is `tools/naming_coherence.py`. This page is the reader's
version — the vocabulary a finding uses, and the reasoning behind the one
decision that shaped the tool.

## The skill states no correct grammar

A token layer that names everything `--btn-pad-x` is coherent. So is one
that names everything `--button-padding-inline`. A system where both
appear is the finding, and which of the two it should settle on belongs
to the people who maintain it.

This follows the rule Stage 3 already applies to modes and Stage 4
applies to families: grade a project against what it declares, never
against a standard it never adopted. Ranking naming conventions against
each other would be the first opinion in a skill built on evidence, and
a reader who disagreed with the ranking would have no way to check it.

So the tool measures two things and offers a third:

| What | How it is used |
|---|---|
| How many grammars are in play | The graded signal — pass at one, attention at two, fail at three or more |
| The same word spelled two ways | Evidence beside the grade, with a `file:line` from both spellings |
| Conformance to a declared pattern | Reported where the project states a pattern, and absent where it states none |

## The four axes

A finding names the axis it found, so a reader knows which part of a name
moved.

| Axis | Values | Graded |
|---|---|---|
| Separator | `kebab`, `snake`, `camel`, `unsegmented` | Yes, paired with case |
| Case | `lower`, `upper`, `mixed`, `caseless` | Yes, paired with separator |
| Family position | `leading`, `trailing`, `internal`, `absent` | No — reported as a distribution |
| Spelling | Full word, abbreviation, or axis shorthand | No — reported as pairs |

Separator and case are the pair a machine reads with no judgment: a name
either spells its boundary with a hyphen or it spells it with a capital.
Those two make the grammar id — `kebab-lower`, `snake-upper`,
`camel-mixed` — and their count is the grade.

Family position and spelling carry real signal and no clean threshold.
`--color-bg` and `--bg-color` are one grammar with the family word at
opposite ends, and a system may hold both for good reasons. They are
shown so a reader can weigh them.

## Grammars are counted inside a syntax

A JS identifier cannot hold a hyphen, and a CSS custom property cannot
hold a dot. A system that writes kebab in CSS and camel in a theme object
has one convention expressed in two languages, and counting those as two
grammars grades the language.

So the count runs inside each syntax — `css`, `scss`, `js`, `json` — and
the grade reads whichever holds the most. A reader learning this system
learns one spelling per language; two spellings inside one language is
what makes a name unguessable.

The dot follows from the same fact. Discovery reports a theme object, a
DTCG file and an scss map as a path — `tokens.colorAccent`,
`color.primitive.blue.500` — where the dots are the structure the value
sits in and the last part is what the token is called. The grammar is
read from that last part.

Both rules came from one run against a real repository, which graded
`fail` on a system whose 365 custom properties agree with each other,
because four JS object keys and a dotted path were counted beside them.

## An unsegmented name is evidence about nothing

A one-word token — `--brand`, `--surface` — spells no boundary, so it
says nothing about how this system spells one. Counting it as a grammar
of its own would fail every system that owns a top-level token, which is
most of them.

The tool records unsegmented names with a count and leaves them out of
the grammar tally. A system whose names are **all** unsegmented grades
`blocked` with that reason, rather than `pass`: zero grammars measured
and one grammar found are two different claims, and principle 6 keeps
them apart.

## Declared, inferred, and the difference

| State | How it is reached | What the report may say |
|---|---|---|
| Declared | A stylelint `custom-property-pattern` or `scss/dollar-variable-pattern`, cited by `file:line` | Names outside the pattern, as conformance findings against a rule the project wrote |
| Inferred | No pattern found; the most common grammar stands in | The dominant grammar, labeled inferred, with nothing graded against it |

The distinction carries the whole argument of the previous section. A
declared pattern is the project's own rule, so a name outside it is a
finding the project already agreed to. An inferred one is this run's
observation, so a name outside it is a minority convention and reported
as one.

A consumer override is read for neither. It spells its names to match
whatever it overrides, so its grammar is evidence about that other
system.

## What this does not yet do

`tier-integrity` needs each token sorted into primitive or semantic, and
`references/token-taxonomy.md` asks for that tier to be recorded. Nothing
computes it. Name shape is the obvious signal — a trailing number reads
as primitive, a role word reads as semantic — and it is the same class of
opinion this page declines everywhere else. The tier is left to the
agent, and this line is the roadmap entry rather than a plan.
