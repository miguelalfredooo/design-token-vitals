# design-token-vitals v1 Implementation Plan

**Status:** All twelve tasks shipped and published 2026-09-01.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a public, standalone agent skill that inspects any web codebase and reports the health of its design token layer, with no setup required.

**Architecture:** A markdown skill (`SKILL.md` + `references/`) that carries a self-contained HTML report template and four "where to look" stack adapters. The skill inspects first and grades only what the repo can actually prove, recording the rest as `blocked` or `not_applicable`. One small Python tool enforces the copy standard on the repo's own prose.

**Tech Stack:** Markdown, HTML/CSS (no framework, no build step), Python 3 stdlib only (`unittest`) for the voice lint. No npm dependencies. No runtime dependencies of any kind — the skill is read by an agent, not executed.

**Spec:** `docs/superpowers/specs/2026-09-01-design-token-vitals-design.md`

## Global Constraints

Every task's requirements implicitly include this section.

- **US English.** Enforced by `tools/check_voice.py`, which swaps each British spelling below for the American one shown beside it:

  ```
  color, tokenized, summarized, judgment, center, gray, catalog, labeled,
  canceled, acknowledgment, behavior, while (not whilst), among (not
  amongst), learned (not learnt).
  ```
- **No "X is not Y, it's Z" constructions** in any prose. Rewrite as a positive statement.
- **Second person.** Address the reader as "you"; name the consequence before the principle.
- **"Hardcoded values"** in prose. The word "literal" appears only where it labels a code value inside a table.
- **No composite score**, in any output, in any release. Grades are per-vital only.
- **Five status values:** `pass`, `attention`, `fail`, `blocked`, `not_applicable`. An unrun check is `blocked`, never an implicit pass.
- **Aggregate the count, never the evidence.** Every rolled-up finding carries at least one real `file:line`.
- **Truncation is always declared.** Never a silent cut.
- **The HTML report is a single self-contained file.** No external CSS, JS, fonts, or images. No server, no build step.
- **Web adapters only in v1:** CSS custom properties, Tailwind, SCSS/Less, Style Dictionary/DTCG.
- **No codebase is named** in any shipped file except the public repo used for the worked example.
- **Commit format:** `type(scope): description` — types `feat`, `fix`, `chore`, `docs`, `refactor`, `test`.

---

## File Structure

| Path | Responsibility |
|---|---|
| `SKILL.md` | The workflow: detect stack, load adapter, grade the eight vitals, emit three outputs |
| `references/vitals.md` | The eight attributes: what each catches, its signal, its grading rule |
| `references/leakage.md` | The three leakage tiers, category weighting, near-miss math, escape hatches |
| `references/report.md` | Output contract, the three rendering tiers, the two evidence invariants |
| `references/voice.md` | Copy standard and the slot templates for generated sentences |
| `references/adapters/css-vars.md` | Where tokens live, what a leak looks like, how modes are expressed, idiomatic enforcement |
| `references/adapters/tailwind.md` | Same four questions, Tailwind |
| `references/adapters/scss.md` | Same four questions, SCSS/Less |
| `references/adapters/dtcg.md` | Same four questions, Style Dictionary / DTCG JSON |
| `assets/report-template.html` | The self-contained report, with named slots |
| `assets/capability-map.yml` | Schema for what the repo can and cannot prove |
| `assets/reference/small.html` | Reference rendering, 214-token system (durable input for the template) |
| `assets/reference/large.html` | Reference rendering, 840-token system |
| `tools/check_voice.py` | Copy-standard lint: US spelling, banned phrases, negative-parallelism warning |
| `tools/test_check_voice.py` | Its tests |
| `examples/shadcn-ui/` | One worked run against a public repo |
| `README.md` | What run one gives you, install, worked example, honest limits |
| `LICENSE` | MIT |

---

## Task 1: Repo scaffold and the voice lint

**Files:**
- Create: `tools/check_voice.py`
- Test: `tools/test_check_voice.py`
- Create: `LICENSE`, `.gitignore`
- Create: `assets/reference/small.html`, `assets/reference/large.html` (copied, not authored)

**Interfaces:**
- Consumes: nothing.
- Produces: `check_voice.check_text(text: str) -> list[Finding]` where `Finding` is a `NamedTuple(line: int, level: str, rule: str, message: str)`; `level` is `"error"` or `"warning"`. CLI: `python3 tools/check_voice.py <path>...` exits `1` if any `error` is found, `0` otherwise. Every later task runs this CLI as its verification step.

- [x] **Step 1: Copy the two reference reports into the repo**

These are the durable visual and copy standard for Task 8. They must live in the repo, not in a temp directory.

```bash
cd ~/Code/design-token-vitals
mkdir -p assets/reference tools
cp <path-to-reference-reports>/token-vitals-report.html assets/reference/small.html
cp <path-to-reference-reports>/token-vitals-large.html assets/reference/large.html
wc -l assets/reference/*.html
```

Expected: two files, roughly 700 and 800 lines. If the source paths no longer exist, stop and ask — these cannot be reconstructed from the plan.

- [x] **Step 2: Write the failing test**

Create `tools/test_check_voice.py`:

```python
import unittest
from check_voice import check_text


class TestBritishSpelling(unittest.TestCase):
    def test_flags_colour(self):
        findings = check_text("The colour token is missing.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].level, "error")
        self.assertEqual(findings[0].rule, "us-english")
        self.assertIn("color", findings[0].message)

    def test_flags_capitalized_colour(self):
        findings = check_text("Colour matters most.")
        self.assertEqual(len(findings), 1)
        self.assertIn("Color", findings[0].message)

    def test_flags_tokenised(self):
        findings = check_text("7 of 11 categories are tokenised.")
        self.assertEqual(len(findings), 1)
        self.assertIn("tokenized", findings[0].message)

    def test_does_not_flag_css_color_property(self):
        findings = check_text("  color: var(--ink);")
        self.assertEqual(findings, [])

    def test_reports_line_number(self):
        findings = check_text("fine\nfine\nthe colour is wrong")
        self.assertEqual(findings[0].line, 3)


class TestBannedPhrases(unittest.TestCase):
    def test_flags_simply(self):
        findings = check_text("Simply swap the token.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "banned-phrase")

    def test_flags_utilize(self):
        findings = check_text("Utilize the semantic layer.")
        self.assertEqual(findings[0].rule, "banned-phrase")

    def test_does_not_flag_just_as_adjective_context(self):
        findings = check_text("This is the just-in-time path.")
        self.assertEqual(findings, [])


class TestNegativeParallelism(unittest.TestCase):
    def test_warns_on_is_not_a(self):
        findings = check_text("A list of hex codes is not a review.")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].level, "warning")
        self.assertEqual(findings[0].rule, "negative-parallelism")

    def test_warning_does_not_fail_the_run(self):
        from check_voice import has_errors
        self.assertFalse(has_errors(check_text("This is not a problem.")))


class TestClean(unittest.TestCase):
    def test_clean_text_returns_nothing(self):
        findings = check_text(
            "Each row is a hardcoded value that one of your tokens already holds."
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 3: Run the test to verify it fails**

Run: `cd ~/Code/design-token-vitals/tools && python3 -m unittest test_check_voice -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'check_voice'`

- [x] **Step 4: Write the implementation**

Create `tools/check_voice.py`:

```python
#!/usr/bin/env python3
"""Copy-standard lint for design-token-vitals.

Errors fail the run. Warnings are advisory.
"""
import re
import sys
from typing import NamedTuple


class Finding(NamedTuple):
    line: int
    level: str
    rule: str
    message: str


# British -> American. Longest first so plurals win over singulars.
SPELLING = [
    ("Colours", "Colors"), ("colours", "colors"),
    ("Colour", "Color"), ("colour", "color"),
    ("untokenised", "untokenized"), ("tokenised", "tokenized"),
    ("summarised", "summarized"), ("normalised", "normalized"),
    ("organised", "organized"), ("recognised", "recognized"),
    ("prioritised", "prioritized"), ("standardised", "standardized"),
    ("acknowledgement", "acknowledgment"), ("judgement", "judgment"),
    ("catalogue", "catalog"), ("cancelled", "canceled"),
    ("labelled", "labeled"), ("behaviour", "behavior"),
    ("centre", "center"), ("grey", "gray"),
    ("whilst", "while"), ("amongst", "among"), ("learnt", "learned"),
]

BANNED = [
    "simply", "utilize", "utilise", "leverage",
    "in order to", "seamlessly", "effortlessly", "robust",
]

NEG_PARALLEL = re.compile(r"\b(?:is|are|was|were)\s+not\s+(?:a|an|the)\b", re.I)


def check_text(text):
    findings = []
    for i, raw in enumerate(text.split("\n"), start=1):
        for old, new in SPELLING:
            if old in raw:
                findings.append(Finding(
                    i, "error", "us-english",
                    "'%s' is British; use '%s'" % (old, new),
                ))
                break
        low = raw.lower()
        for phrase in BANNED:
            if re.search(r"\b%s\b" % re.escape(phrase), low):
                findings.append(Finding(
                    i, "error", "banned-phrase",
                    "'%s' is on the banned list" % phrase,
                ))
                break
        if NEG_PARALLEL.search(raw):
            findings.append(Finding(
                i, "warning", "negative-parallelism",
                "rewrite as a positive statement",
            ))
    return findings


def has_errors(findings):
    return any(f.level == "error" for f in findings)


def main(paths):
    failed = False
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            findings = check_text(fh.read())
        for f in findings:
            print("%s:%d  %-8s %-20s %s" % (path, f.line, f.level, f.rule, f.message))
        if has_errors(findings):
            failed = True
    if not failed:
        print("voice: clean (%d file(s))" % len(paths))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [x] **Step 5: Run the tests to verify they pass**

Run: `cd ~/Code/design-token-vitals/tools && python3 -m unittest test_check_voice -v`
Expected: PASS, 10 tests.

- [x] **Step 6: Add LICENSE and .gitignore**

`LICENSE` — MIT, copyright holder `Miguel Arias`, year `2026`. Use the standard MIT text verbatim from https://opensource.org/license/mit with those two substitutions.

`.gitignore`:

```
__pycache__/
*.pyc
.DS_Store
.token-vitals/
```

- [x] **Step 7: Commit**

```bash
cd ~/Code/design-token-vitals
git add tools/check_voice.py tools/test_check_voice.py LICENSE .gitignore assets/reference/
git commit -m "feat(tools): voice lint, license, reference renderings"
```

---

## Task 2: references/voice.md

**Files:**
- Create: `references/voice.md`

**Interfaces:**
- Consumes: `tools/check_voice.py` CLI from Task 1.
- Produces: the slot-template vocabulary every later prose file and the report template quote. Slot names are `{n}`, `{a}`, `{b}`, `{c}`, `{worst}`, `{shown}`, `{total}`, `{family}`, `{path}`.

- [x] **Step 1: Write the file**

`references/voice.md` must contain these five sections, with this content:

**Section "Three kinds of copy"** — a table:

| Kind | Where | How the voice is guaranteed |
|---|---|---|
| Static chrome | Headings, ledes, tooltips, legend, panel titles | Ships in `assets/report-template.html`; identical every run |
| Slotted sentences | Vital cards, truncation lines, family rows | Slot templates below; fill the slots, never rewrite the sentence |
| Generated | A callout connecting two findings | The rules below, plus `assets/reference/*.html` as worked examples |

**Section "Rules"** — one line each:

- Write in second person. Say what a finding means for the reader before stating the principle.
- Explain a term the first time it appears. Keep the real vocabulary: semantic token, primitive, mode, ramp, orphan.
- Never write "X is not Y, it's Z". State the positive.
- Say "hardcoded values" in prose. Use "literal" only as a table label for a code value.
- Nothing is anyone's fault. An uncovered value is a gap in the system, not a mistake by whoever wrote the component.
- US English. The full swap list lives in `tools/check_voice.py`.

**Section "Banned"** — the `BANNED` list from `tools/check_voice.py`, with one line explaining that the first and seventh entries tell the reader their difficulty is imaginary:

```
simply, effortlessly
```

**Section "Slot templates"** — the exact sentences, verbatim, that the skill fills:

```
leakage-card:    {n} hardcoded values where a token already existed. {a} are exact
                 matches you can swap today, {b} have drifted slightly, and {c} have
                 no token yet. {worst} are worst affected.

modes-card:      {n} tokens have a light value but no dark one. Nothing errors — they
                 quietly fall back to the light value, so people in dark mode see
                 faint, hard-to-read text.

orphans-card:    {n} tokens are defined but nothing uses them. They are safe to
                 delete, and removing them makes the system easier to learn.

enforcement-card-blocked:
                 Nothing in your lint setup or CI looks at tokens, so everything above
                 can come back tomorrow without anyone noticing. One rule would change
                 that.

truncation:      Showing the {shown} largest {noun}. The other {rest} hold {summary}.

family-evidence: {path}
```

**Section "Worked examples"** — point at `assets/reference/small.html` and `assets/reference/large.html`, and state that a few dozen real sentences constrain tone better than a paragraph of description.

- [x] **Step 2: Verify the file passes its own lint**

Run: `python3 tools/check_voice.py references/voice.md`
Expected: `voice: clean (1 file(s))`, exit 0.

If it reports errors, the file violates the standard it defines. Fix the file, not the lint.

- [x] **Step 3: Commit**

```bash
git add references/voice.md
git commit -m "docs(references): copy standard and slot templates"
```

---

## Task 3: references/vitals.md

**Files:**
- Create: `references/vitals.md`

**Interfaces:**
- Consumes: `references/voice.md` (Task 2) for tone.
- Produces: the canonical vital IDs used by `assets/capability-map.yml` (Task 6) and `SKILL.md` (Task 9): `tier-integrity`, `leakage`, `coverage`, `mode-completeness`, `naming-coherence`, `single-source`, `orphans`, `enforcement`.

- [x] **Step 1: Write the file**

Open with the grading vocabulary, stated once:

- `pass` — checked, nothing to fix
- `attention` — worth a look, not urgent
- `fail` — real problems with a clear fix
- `blocked` — could not check this one
- `not_applicable` — does not apply to this setup

Then: **there is no composite score.** Averaging these hides the one finding that matters, and a system with no dark mode is `not_applicable` on that vital rather than a percentage. An unrun check is `blocked`.

Then one subsection per vital, each with exactly four parts — **Catches**, **Signal**, **Grading**, **Evidence**:

| ID | Catches | Signal | Grading |
|---|---|---|---|
| `tier-integrity` | Components reaching past semantic tokens to primitives or raw values | Count of component styles referencing a primitive-tier name or a raw value | `pass` at 0; `attention` under 5% of component styles; `fail` above |
| `leakage` | Hardcoded values where a token was available | See `references/leakage.md` | Driven by the redundant tier: `pass` at 0, `attention` under 10 findings, `fail` above |
| `coverage` | Categories with no tokens at all | Presence per category: color, typography, space, size, radius, border, elevation, motion, z-index, opacity, breakpoint | `pass` at 11/11; `attention` at 8–10; `fail` below 8 |
| `mode-completeness` | A token defined in one mode and not another | Set difference across mode blocks, per declared mode | `pass` at 0 gaps; `fail` at any gap in a declared mode; `not_applicable` for an undeclared mode |
| `naming-coherence` | More than one grammar in one system | Count of distinct segment patterns across token names | `pass` at 1 grammar; `attention` at 2 where one is a named legacy family; `fail` otherwise |
| `single-source` | The same concept defined in more than one place | Count of independent definition sites per concept, and whether they agree | `pass` at 1 site; `attention` if duplicated but agreeing; `fail` if any disagree |
| `orphans` | Tokens nothing references | Defined minus referenced | `pass` under 2%; `attention` under 10%; `fail` above |
| `enforcement` | Whether any of the above can regress silently | Lint rules and CI gates that read tokens | `pass` at 2+ rules; `attention` at 1; `blocked` at 0 — nothing could be verified as protected |

**Evidence** for every vital: at least one real `file:line`. A vital with a count and no reachable instance is graded `blocked`, not `fail`.

Close with a short section, **Held for a later release**: contrast guarantees (needs a declared WCAG target the repo usually does not have) and lifecycle/deprecation (only meaningful once a system has consumers to break).

- [x] **Step 2: Verify all eight vitals are present and lint-clean**

```bash
python3 tools/check_voice.py references/vitals.md
for v in tier-integrity leakage coverage mode-completeness naming-coherence single-source orphans enforcement; do
  grep -q "$v" references/vitals.md || echo "MISSING: $v"
done
```

Expected: `voice: clean (1 file(s))` and no `MISSING` lines.

- [x] **Step 3: Commit**

```bash
git add references/vitals.md
git commit -m "docs(references): the eight vitals with signals and grading rules"
```

---

## Task 4: references/leakage.md

**Files:**
- Create: `references/leakage.md`

**Interfaces:**
- Consumes: `references/vitals.md` (Task 3) — this file is the depth behind vital `leakage`.
- Produces: tier IDs `redundant`, `near-miss`, `uncovered`, used by `assets/report-template.html` (Task 8) and `assets/capability-map.yml` (Task 6).

- [x] **Step 1: Write the file**

Open with the reason the tiering exists: counting hardcoded values punishes correct code, because a 1px hairline rarely needs a token. What matters is whether the system offered a token and the code went around it.

Then the three tiers:

| Tier | Condition | What it means | Fix owner |
|---|---|---|---|
| `redundant` | A token holds this exact value | Someone bypassed the system | Component author — mechanical, no discussion |
| `near-miss` | Within a small delta of a token | Value drift: invisible to search and to code review | Design — reconcile or accept |
| `uncovered` | No token exists for this concept | A hole in the token layer | System owner — add the token |

**Near-miss math**, stated exactly:

- Color: CIEDE2000 ΔE against every token in the same category. Flag below **ΔE 3.0**. Report the value to one decimal. Under ΔE 2 is invisible to most people, which is why this drift survives review.
- Dimension: absolute distance to the nearest scale step. Flag at **2px or less** where the step itself is 4px or larger.
- Duration: flag within **50ms** of a motion token.

**Category weighting**, highest consequence first: `color` (breaks theming outright), `motion`, `elevation`, `z-index` (magic numbers collide), `typography`, `breakpoint`, `dimension` (noisiest, most exception-prone — grade last and gently).

**Escape hatches:** a declared exception with an owner and a review date is not a finding. An undeclared one is. Never grade a `1px` hairline, an optical nudge, or a value inside a file the repo has marked exempt.

**Ranking:** order findings by blast radius (files affected), descending, then by token name ascending. The tiebreak makes the order deterministic, so re-running never reshuffles what the reader sees.

- [x] **Step 2: Verify**

Run: `python3 tools/check_voice.py references/leakage.md`
Expected: `voice: clean (1 file(s))`.

- [x] **Step 3: Commit**

```bash
git add references/leakage.md
git commit -m "docs(references): three leakage tiers, near-miss math, ranking"
```

---

## Task 5: references/report.md

**Files:**
- Create: `references/report.md`

**Interfaces:**
- Consumes: `references/vitals.md`, `references/leakage.md`.
- Produces: the rendering-tier names `full`, `collapsed`, `family-only` and the output paths `.token-vitals/report.html`, `.token-vitals/report.json`, used by `SKILL.md` (Task 9).

- [x] **Step 1: Write the file**

**Outputs** — three from one run:

| Output | Path | Audience |
|---|---|---|
| Report | `.token-vitals/report.html` | People. Single self-contained file |
| Summary | stdout | Terminal and PR comments |
| Working set | `.token-vitals/report.json` | Codemods, triage, and the future `contract` stage |

State that the HTML is self-contained on purpose: it attaches to CI as a build artifact, survives being emailed, and needs no server.

**Why HTML is the primary output:** the token inventory rendered as itself (color as color, type scale at real sizes, spacing drawn to width), near-miss pairs as adjacent swatches, and mode gaps as a matrix. Near-miss drift barely communicates in plain text.

**Rendering tiers:**

| Tokens | Tier ID | Treatment |
|---|---|---|
| Under 150 | `full` | Everything rendered |
| 150–600 | `collapsed` | Families collapsed by default, exceptions expanded, top-N tables |
| Over 600 | `family-only` | Family rows only, palette as ramps, modes as an exception report, full data in the JSON |

At `family-only`, note the two findings that only exist at scale: **outliers** (a color belonging to no ramp was added by hand, outside the system that generated the rest) and **duplicates** (two names for one value, so consumers pick at random).

**The two invariants**, stated as the section's own heading:

1. **Aggregate the count, never the evidence.** Every rolled-up finding shows at least one real `file:line`. A finding that cannot point at code is an opinion.
2. **Truncation is always declared.** `Showing 12 of 247` — never a silent cut. Same principle as `blocked` never being an implicit pass.

- [x] **Step 2: Verify**

Run: `python3 tools/check_voice.py references/report.md`
Expected: `voice: clean (1 file(s))`.

- [x] **Step 3: Commit**

```bash
git add references/report.md
git commit -m "docs(references): output contract, rendering tiers, evidence invariants"
```

---

## Task 6: assets/capability-map.yml

**Files:**
- Create: `assets/capability-map.yml`

**Interfaces:**
- Consumes: vital IDs from Task 3, tier IDs from Task 4, rendering-tier IDs from Task 5.
- Produces: the schema that `SKILL.md` (Task 9) writes and that the future `contract` stage reads. Top-level keys: `schema_version`, `run`, `stack`, `declared`, `vitals`, `rendering`.

- [x] **Step 1: Write the file**

```yaml
schema_version: 1

# What this run looked at. Every value is observed, never assumed.
run:
  generated_at: null        # ISO 8601
  repo_ref: null            # git SHA, or null if not a git repo
  token_count: null
  family_count: null

stack:
  adapter: null             # css-vars | tailwind | scss | dtcg | unknown
  token_sources: []         # paths that define tokens
  detected_by: null         # what proved it — a filename, a config key
  confidence: null          # certain | inferred | interviewed

# What the project promises. Read from the repo, never guessed.
# A mode the project does not declare is not_applicable, never a gap.
declared:
  modes: []                 # e.g. [light, dark]
  categories: []            # the token categories this system claims
  accessibility_target: null

vitals:
  tier-integrity:   { grade: null, evidence: [], note: null }
  leakage:          { grade: null, evidence: [], note: null,
                      tiers: { redundant: 0, near-miss: 0, uncovered: 0 } }
  coverage:         { grade: null, evidence: [], note: null }
  mode-completeness:{ grade: null, evidence: [], note: null }
  naming-coherence: { grade: null, evidence: [], note: null }
  single-source:    { grade: null, evidence: [], note: null }
  orphans:          { grade: null, evidence: [], note: null }
  enforcement:      { grade: null, evidence: [], note: null }

# grade: pass | attention | fail | blocked | not_applicable
# evidence: a list of "path:line" strings. A grade with an empty
#           evidence list must be blocked, never fail.
# note:     why, when the grade is blocked or not_applicable.

rendering:
  tier: null                # full | collapsed | family-only
  truncated: []             # every section that showed fewer rows than it holds
```

- [x] **Step 2: Verify it parses and every vital ID matches Task 3**

```bash
python3 -c "
import yaml, sys
d = yaml.safe_load(open('assets/capability-map.yml'))
want = {'tier-integrity','leakage','coverage','mode-completeness',
        'naming-coherence','single-source','orphans','enforcement'}
got = set(d['vitals'])
assert got == want, 'mismatch: %s' % (got ^ want)
assert set(d) == {'schema_version','run','stack','declared','vitals','rendering'}
print('capability map: 8 vitals, keys ok')
"
```

Expected: `capability map: 8 vitals, keys ok`.

If `yaml` is not installed, run `python3 -m pip install --user pyyaml` first. PyYAML is a verification-time convenience only; the shipped skill has no dependencies.

- [x] **Step 3: Commit**

```bash
git add assets/capability-map.yml
git commit -m "feat(assets): capability map schema"
```

---

## Task 7: The four web adapters

**Files:**
- Create: `references/adapters/css-vars.md`, `references/adapters/tailwind.md`, `references/adapters/scss.md`, `references/adapters/dtcg.md`

**Interfaces:**
- Consumes: vital IDs (Task 3), tier IDs (Task 4).
- Produces: adapter IDs `css-vars`, `tailwind`, `scss`, `dtcg` — the allowed values of `stack.adapter` in the capability map.

Each adapter answers the same four questions in the same four headings, so they stay swappable. Keep each under 60 lines; these are lookup tables, not logic.

- [x] **Step 1: Write `references/adapters/css-vars.md`**

Four headings:

**Where tokens live** — `--*` custom property declarations in `:root`, `[data-theme]`, and `@media (prefers-color-scheme:)` blocks. Typically one `globals.css`, `tokens.css`, or `theme.css`.
**Detection** — a `.css` file containing 20 or more `--` declarations inside a `:root` block.
**What a leak looks like** — a hex, `rgb()`, `hsl()`, `oklch()`, `px`, `rem`, or `ms` value in a component file where a `var(--…)` was available. Ignore values inside the token source itself: those are definitions, not leaks.
**How modes are expressed** — a second `:root` block under `[data-theme="dark"]` or `@media (prefers-color-scheme: dark)`. A mode gap is a custom property present in one block and absent from another.
**Idiomatic enforcement** — stylelint `declaration-property-value-disallowed-list`, or a custom rule banning raw hex outside the token file.

- [x] **Step 2: Write `references/adapters/tailwind.md`**

**Where tokens live** — `@theme` in Tailwind v4, or `theme.extend` in `tailwind.config.*` for v3. Both usually reference CSS custom properties, so run the `css-vars` checks as well and report one merged set.
**Detection** — a `tailwind.config.*` file, or an `@import "tailwindcss"` / `@theme` block in CSS.
**What a leak looks like** — a bracket-arbitrary value carrying a raw measurement or color: `bg-[#0F8A83]`, `p-[15px]`, `duration-[240ms]`. A bracket value referencing a variable is not a leak.
**How modes are expressed** — the `dark:` variant, plus whatever the underlying custom properties do. A token used with `dark:` but with no dark definition is a gap.
**Idiomatic enforcement** — `eslint-plugin-tailwindcss`, or a custom rule banning bracket-arbitrary literals.

Add one gotcha, because it is silent and common: **a bracket-arbitrary value holding a bare custom-property name compiles to invalid CSS and is dropped with no error.** `bg-[--brand]` renders transparent; it must be `bg-[var(--brand)]` or Tailwind v4's parenthesis shorthand. Report these as `redundant` leaks with high severity, because the element renders unstyled and nothing warns.

- [x] **Step 3: Write `references/adapters/scss.md`**

**Where tokens live** — `$variable` declarations, `@use`/`@forward` module members, and `map.get()` lookups against a token map. Usually `_variables.scss`, `_tokens.scss`, or a `tokens/` directory.
**Detection** — a `.scss` or `.less` file with 20 or more variable declarations, or a file whose name matches `_?(tokens|variables|theme)`.
**What a leak looks like** — a raw measurement or color in a rule where a variable of that value exists in scope.
**How modes are expressed** — usually a mixin or a class-scoped override rather than a second block. If no mode mechanism is found, `mode-completeness` is `not_applicable`, not `fail`. Say so in the note.
**Idiomatic enforcement** — stylelint with `scss/dollar-variable-pattern`, plus a disallowed-list rule for raw values.

Add the caution that SCSS variables are compile-time, so a runtime theme switch is usually implemented some other way. Find that mechanism before grading modes.

- [x] **Step 4: Write `references/adapters/dtcg.md`**

**Where tokens live** — JSON files with `$value` and `$type` keys (W3C Design Tokens Community Group format), typically under `tokens/`, built by Style Dictionary or a similar pipeline.
**Detection** — a JSON file containing `$value`, or a `config.json`/`sd.config.*` naming Style Dictionary.
**What a leak looks like** — check the *build output* as well as the source, because the generated CSS or JS is what components import. Run the matching output adapter on the generated file and attribute findings back to the source token.
**How modes are expressed** — separate token sets composed at build time, or `$extensions` carrying mode values. Read the build config to learn which modes are declared; do not infer them from directory names.
**Idiomatic enforcement** — a build-time validation step, plus whatever lint runs on the generated output.

Note the one real advantage: this is the only adapter where the tier structure is explicit, since aliases are written as `{color.primitive.blue.500}`. Tier integrity is directly readable rather than inferred.

- [x] **Step 5: Verify all four exist, are lint-clean, and share the four headings**

```bash
python3 tools/check_voice.py references/adapters/*.md
for f in css-vars tailwind scss dtcg; do
  for h in "Where tokens live" "Detection" "What a leak looks like" "How modes are expressed" "Idiomatic enforcement"; do
    grep -q "$h" "references/adapters/$f.md" || echo "MISSING in $f: $h"
  done
done
```

Expected: `voice: clean (4 file(s))` and no `MISSING` lines.

- [x] **Step 6: Commit**

```bash
git add references/adapters/
git commit -m "docs(adapters): css-vars, tailwind, scss, dtcg"
```

---

## Task 8: assets/report-template.html

**Files:**
- Create: `assets/report-template.html`
- Read: `assets/reference/small.html`, `assets/reference/large.html`

**Interfaces:**
- Consumes: `assets/reference/*.html` as the visual and copy standard; slot names from `references/voice.md` (Task 2).
- Produces: the slot vocabulary the skill fills. Slots are HTML comments of the form `<!-- SLOT:name -->…<!-- /SLOT:name -->` so the template stays a valid, openable HTML file with its sample content in place.

- [x] **Step 1: Derive the template from the reference renderings**

Start from `assets/reference/large.html`, because it contains every component the small one has plus the three scale treatments. Keep verbatim:

- The full token block: `:root`, `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { … } }`, and `:root[data-theme="dark"]`. All three are required; a color defined only inside a media or `[data-theme]` block never applies in the un-stamped default state.
- `body { background: var(--ground); }` — a transparent body borrows the host's ground.
- The `.grade`, `.vital`, `.pip`, `.trunc`, `.ramp`, `.cov`, `.tip` component CSS.
- All 42 tooltips, verbatim. They are static chrome and must not vary between runs.

- [x] **Step 2: Mark the slots**

Wrap every run-varying region. The complete slot list:

```
runhead-meta        project, stack, adapter, commit, modes
vitals-grid         the eight cards
inventory-color     swatches or ramps, per rendering tier
inventory-type      the type scale
inventory-space     the spacing scale
families            the family table (family-only and collapsed tiers)
leak-redundant      table rows
leak-near-miss      table rows
leak-uncovered      table rows
modes-coverage      the coverage bars
modes-gaps          the enumerated exceptions
orphans             the chip list
enforcement         what guards this today
footer-meta         token count, family count, rendering tier
```

Leave the reference sample content inside each slot. The template must open in a browser and look finished — that is how a contributor checks a change without running the skill.

- [x] **Step 3: Add the three rendering-tier switches**

Three sections carry a `data-tier` attribute listing the tiers in which they render:

```html
<section data-tier="full collapsed">          <!-- full swatch inventory -->
<section data-tier="collapsed family-only">   <!-- family table -->
<section data-tier="family-only">             <!-- ramps, outliers, duplicates -->
```

The skill removes sections whose `data-tier` does not include the chosen tier. Document this in a comment at the top of the file.

- [x] **Step 4: Verify the template**

```bash
python3 tools/check_voice.py assets/report-template.html
python3 - <<'EOF'
s = open('assets/report-template.html', encoding='utf-8').read()
slots = ['runhead-meta','vitals-grid','inventory-color','inventory-type',
         'inventory-space','families','leak-redundant','leak-near-miss',
         'leak-uncovered','modes-coverage','modes-gaps','orphans',
         'enforcement','footer-meta']
for n in slots:
    assert s.count('<!-- SLOT:%s -->' % n) == 1, 'open slot missing: ' + n
    assert s.count('<!-- /SLOT:%s -->' % n) == 1, 'close slot missing: ' + n
assert s.count('<th') - s.count('<thead') == s.count('</th>'), 'unbalanced th'
assert s.count('<span') == s.count('</span>'), 'unbalanced span'
assert s.count('class="tip"') == 42, 'expected 42 tooltips, got %d' % s.count('class="tip"')
for guard in ['prefers-color-scheme: dark', ':root[data-theme="dark"]',
              'background: var(--ground)']:
    assert guard in s, 'missing theme guard: ' + guard
print('template: 14 slots, 42 tooltips, theme guards present, markup balanced')
EOF
```

Expected: `template: 14 slots, 42 tooltips, theme guards present, markup balanced`.

- [x] **Step 5: Open it and look at it**

```bash
open assets/report-template.html
```

Check both themes by toggling your OS appearance. The page must be legible in each, and the body must never show the host's background through it.

- [x] **Step 6: Commit**

```bash
git add assets/report-template.html
git commit -m "feat(assets): self-contained report template with 14 slots"
```

---

## Task 9: SKILL.md

**Files:**
- Create: `SKILL.md`

**Interfaces:**
- Consumes: every reference file and asset from Tasks 2–8.
- Produces: the skill's public contract — its frontmatter `name` and `description`, which is what an agent matches against.

- [x] **Step 1: Write the frontmatter**

```yaml
---
name: design-token-vitals
description: Grade the health of a codebase's design token layer and report what it can and cannot prove about itself. Use when auditing design tokens, checking token adoption, investigating theme or dark-mode bugs, or before adopting a design system. Runs on any web codebase with no setup.
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash, Write
---
```

- [x] **Step 2: Write the workflow**

Six numbered stages, each one screen or less:

1. **Detect the stack.** Match against `references/adapters/*.md`. Record `stack.adapter`, `stack.detected_by`, and `stack.confidence`. On no match, interview the user — never guess. Confidence `interviewed` is a valid outcome; a wrong guess is not.
2. **Read what the project declares.** Modes, categories, accessibility target. This is the step that decides whether a missing high-contrast mode is `fail` or `not_applicable`. Read it from the repo; never assume a standard.
3. **Grade the eight vitals** per `references/vitals.md`, with leakage detail from `references/leakage.md`. Attach at least one `file:line` to every grade. A count with no reachable instance is `blocked`.
4. **Choose the rendering tier** from the token count, per `references/report.md`.
5. **Fill the template.** Copy `assets/report-template.html`, drop sections whose `data-tier` excludes the chosen tier, replace each slot's contents, and use the slot templates in `references/voice.md` verbatim for generated sentences. Never rewrite static chrome.
6. **Write the outputs.** `.token-vitals/report.html`, `.token-vitals/report.json`, and a short terminal summary. Tell the user the path and the one thing worth doing first.

- [x] **Step 3: Write the stop conditions**

Stop and ask when: no token source can be located; two sources disagree and neither is obviously canonical; the repo declares a mode with no discoverable mechanism; or the user asks for a single score.

On the last one, explain rather than comply: a single number would average away the finding that matters, and would score a repo with no dark mode as partially unhealthy when that check does not apply to it.

- [x] **Step 4: Verify**

```bash
python3 tools/check_voice.py SKILL.md
head -8 SKILL.md
grep -c "references/" SKILL.md
```

Expected: lint clean; frontmatter present with `name: design-token-vitals`; at least 5 references to `references/`.

- [x] **Step 5: Commit**

```bash
git add SKILL.md
git commit -m "feat: SKILL.md workflow"
```

---

## Task 10: The worked example

**Files:**
- Create: `examples/shadcn-ui/report.html`, `examples/shadcn-ui/report.json`, `examples/shadcn-ui/README.md`

**Interfaces:**
- Consumes: the whole skill, Tasks 2–9.
- Produces: the artifact the README links to. This is the task that proves the skill works.

- [x] **Step 1: Clone the subject**

A public repo, so every finding is verifiable and no private codebase is described.

```bash
cd /tmp && rm -rf dtv-example && git clone --depth 1 https://github.com/shadcn-ui/ui.git dtv-example
cd dtv-example && git rev-parse --short HEAD
```

Record that SHA. It goes in `examples/shadcn-ui/README.md` so a reader can reproduce the run.

- [x] **Step 2: Run the skill against it**

Follow `SKILL.md` end to end, by hand, against `/tmp/dtv-example`. Do not shortcut a stage — this run is also the skill's first real test, and any stage that turns out to be unexecutable is a bug in `SKILL.md`, to be fixed there before continuing.

- [x] **Step 3: Copy the outputs into the repo**

```bash
cd ~/Code/design-token-vitals
mkdir -p examples/shadcn-ui
cp /tmp/dtv-example/.token-vitals/report.html examples/shadcn-ui/report.html
cp /tmp/dtv-example/.token-vitals/report.json examples/shadcn-ui/report.json
```

- [x] **Step 4: Write `examples/shadcn-ui/README.md`**

It must contain: the subject repo URL, the exact commit SHA from Step 1, the date of the run, the adapter that was detected, the grade of each of the eight vitals as a table, and the reproduction command. State plainly that the findings describe that commit and nothing else, and that a reader can re-run to check them.

- [x] **Step 5: Verify the example is honest**

```bash
python3 - <<'EOF'
import json
d = json.load(open('examples/shadcn-ui/report.json'))
for name, v in d['vitals'].items():
    assert v['grade'] in {'pass','attention','fail','blocked','not_applicable'}, name
    if v['grade'] in {'fail','attention'}:
        assert v['evidence'], '%s is %s with no evidence' % (name, v['grade'])
    if v['grade'] in {'blocked','not_applicable'}:
        assert v['note'], '%s is %s with no note' % (name, v['grade'])
print('example: 8 vitals, every graded finding carries evidence')
EOF
python3 tools/check_voice.py examples/shadcn-ui/README.md examples/shadcn-ui/report.html
```

Expected: both pass. **If a vital is `fail` with no evidence, the skill has a bug** — fix `SKILL.md` or `references/vitals.md` and re-run, rather than editing the output by hand.

- [x] **Step 6: Commit**

```bash
git add examples/
git commit -m "docs(examples): worked run against shadcn-ui"
```

---

## Task 11: README.md

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: the worked example from Task 10 for its screenshots and numbers.
- Produces: the repo's front door.

- [x] **Step 1: Write it**

In this order:

**What you get on the first run** — before install instructions, before anything else. Three sentences and a link to `examples/shadcn-ui/report.html`.

**Install** — the skill is a directory. Copy it into `.claude/skills/` (Claude Code) or the equivalent for the agent in use. No dependencies, no build.

**How it works** — the six stages from `SKILL.md`, one line each.

**The eight vitals** — the table from `references/vitals.md`, `Catches` column only.

**What it does not do** — stated plainly, because this is what stops the skill reading as generic advice:
- No composite score, ever. Averaging hides the finding that matters.
- Web only in v1. iOS, Android and Flutter adapters are not written yet.
- It reads what your project declares and grades against that. It does not impose a standard you did not choose.
- It measures. It does not refactor your tokens for you.

**The honest-gaps example** — the clearest single illustration, worth its own short section: the same high-contrast check is `not_applicable` in a project declaring two modes and `fail` in one declaring three. The difference comes from what the project promises, never from an assumption.

**License** — MIT.

- [x] **Step 2: Verify**

```bash
python3 tools/check_voice.py README.md
grep -q "examples/shadcn-ui" README.md || echo "MISSING example link"
grep -qi "composite score" README.md || echo "MISSING the no-score statement"
```

Expected: lint clean, no `MISSING` lines.

- [x] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README"
```

---

## Task 12: Publish

**Files:** none created; this task publishes the repo.

**Interfaces:**
- Consumes: everything.
- Produces: a public GitHub repository.

**This task requires the user's explicit go before Step 2.** A public repo is indexable from the first push. Do not run `gh repo create` on your own judgment.

- [x] **Step 1: Full verification pass**

```bash
cd ~/Code/design-token-vitals
python3 tools/check_voice.py $(find . -name "*.md" -not -path "./.git/*") assets/report-template.html
cd tools && python3 -m unittest test_check_voice -q && cd ..
find . -type f -not -path "./.git/*" -not -name ".DS_Store" | sort
git status --short
```

Expected: lint clean across every markdown file and the template; 10 tests pass; a clean working tree; the file list matches the File Structure table at the top of this plan.

- [x] **Step 2: Ask the user to confirm publication**

Show them the file list and the README. Ask directly whether to create the public repository. Wait for a yes.

- [x] **Step 3: Create and push**

```bash
cd ~/Code/design-token-vitals
gh repo create design-token-vitals --public --source=. --remote=origin \
  --description "Grade the health of your design tokens. Runs on any web codebase, no setup."
git push -u origin main
gh repo view --web
```

- [x] **Step 4: Confirm what is public**

```bash
gh repo view design-token-vitals --json visibility,name,description
```

Expected: `"visibility": "PUBLIC"`. Open the repo and read the README as a stranger would, checking that no private codebase is named anywhere.

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: shape and stages → Task 9; the eight vitals and the no-score rule → Tasks 3 and 6; leakage tiers → Task 4; adapters → Task 7; capability map → Task 6; report outputs, rendering tiers and the two invariants → Tasks 5 and 8; voice → Tasks 1 and 2; repo layout and visibility → Tasks 1, 11, 12; worked example against a public repo → Task 10; out-of-scope items appear as the README's "what it does not do" in Task 11.

**Open decisions from the spec § 9 are deliberately not resolved here.** Duplicates stay inside `naming-coherence` for v1 (the spec's lean), the tooltip-density question needs the template open in front of a person (Task 8, Step 5), and the Uncovered tier's suggested token names ship as-is with the caveat written into `references/leakage.md`. Any of these can change without restructuring a task.

**Type consistency.** Vital IDs are identical in Tasks 3, 6, 9 and 10. Tier IDs `redundant` / `near-miss` / `uncovered` are identical in Tasks 4, 6 and 8. Rendering-tier IDs `full` / `collapsed` / `family-only` are identical in Tasks 5, 8 and 9. Adapter IDs match between Tasks 6 and 7. `check_voice.check_text` and `has_errors` are defined in Task 1 and used unchanged in every later verification step.

**Known risk.** Task 10 is the only task that can invalidate earlier ones: running the skill for real is where an unexecutable instruction in `SKILL.md` surfaces. That is why it comes before the README and before publication, and why its Step 2 says to fix the skill rather than the output.
