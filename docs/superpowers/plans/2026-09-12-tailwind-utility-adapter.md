# Tailwind Utility Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Tailwind utility classes count as token references, and make bracket-arbitrary literals in source files reachable as leaks.

**Architecture:** One new pure module, `tools/tailwind_adapter.py`, that maps a class name onto a concept id discovery already found. Three existing call sites consume it: the usage scanner gains a third syntax, the usage report flips one measurement state, and the literal audit gains a second, explicitly-scoped intake. The adapter never parses a token file, never expands a utility into CSS, and declines rather than guesses.

**Tech Stack:** Python 3 standard library only. `unittest`. No third-party dependency, by design — the skill runs on a stock interpreter in whatever repository it audits, and so does its suite.

**Spec:** `docs/superpowers/specs/2026-09-12-tailwind-utility-adapter-design.md`

## Global Constraints

- **Python standard library only.** No new imports beyond `os`, `re`, `json`, `collections`. `subprocess` is reserved for `git` and must not be used here.
- **Exit codes mean one thing** (`tools/cli.py`): `0` ran and found nothing, `1` ran and found something, `2` refused to run.
- **American spellings.** `tools/check_voice.py` is the authority; run it on any prose you write.
- **Every guard is watched failing by exit code**, never by reading output, and every mutation is injected in both spellings a person might write.
- **Assertions are written as variety, not presence** — "no two namespaces resolve to the same concept", never "resolution works".
- **Resolution stops at the theme key.** `bg-background` resolves to `color-background`; the existing alias machinery walks onward. Never resolve through an alias chain inside the adapter.
- **A derived step is never a named step.** `p-4` carries `derived=True`; `p-lg` from a declared `--spacing-lg` does not.
- **The adapter degrades to the state that existed before it**, never to a guess. When `detect()` returns `None`, every output byte is what it is today.
- **design-token-vitals is public.** Committed fixtures and examples stay synthetic. No private repository's paths, names or report content enters the tree.

---

### Task 1: The theme map and the authored namespace table

**Files:**
- Create: `tools/tailwind_adapter.py`
- Create: `tools/test_tailwind_adapter.py`
- Create: `fixtures/tailwind/theme-4.2.1-excerpt.css`

**Interfaces:**
- Produces: `parse_theme(text) -> {namespace: {key: value}}`, `theme_map(project_text, default_text) -> {namespace: {key: value}}`, `namespace_coverage(theme) -> {"covered": [...], "uncovered": [...], "non_utility": [...]}`, the constants `UTILITY_PREFIXES`, `KNOWN_NAMESPACES`, `NON_UTILITY_NAMESPACES`, and `concept_id(namespace, key) -> str`.

**Why a committed excerpt exists.** The guard that falsifies the authored table has to read a real Tailwind default theme, and CI installs no npm packages. So a version-stamped excerpt — one representative declaration per namespace — is committed and the guard always runs against it. A second, opt-in check compares the excerpt against an installed package when one is present, so version drift is caught without making the first guard skippable.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for resolving Tailwind utility classes back to canonical tokens."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tailwind_adapter  # noqa: E402

EXCERPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fixtures", "tailwind", "theme-4.2.1-excerpt.css",
)


class TestThemeMap(unittest.TestCase):
    def test_multi_word_namespaces_survive_the_split(self):
        # Splitting on the first dash buckets --drop-shadow-md under "drop"
        # and --font-weight-bold under "font". Both are wrong, and both are
        # silent: the key still parses and still resolves to something.
        theme = tailwind_adapter.parse_theme(
            "@theme {\n"
            "  --drop-shadow-md: 0 3px 3px #0003;\n"
            "  --font-weight-bold: 700;\n"
            "  --font-sans: Geist, sans-serif;\n"
            "}\n"
        )
        self.assertEqual(sorted(theme), ["drop-shadow", "font", "font-weight"])
        self.assertEqual(list(theme["drop-shadow"]), ["md"])
        self.assertEqual(list(theme["font-weight"]), ["bold"])
        self.assertEqual(list(theme["font"]), ["sans"])

    def test_a_derived_root_is_its_own_key(self):
        theme = tailwind_adapter.parse_theme("@theme {\n  --spacing: 0.25rem;\n}\n")
        self.assertEqual(theme["spacing"], {"": "0.25rem"})

    def test_project_theme_wins_over_the_default_theme(self):
        merged = tailwind_adapter.theme_map(
            "@theme {\n  --color-red-500: #ff0000;\n}\n",
            "@theme default {\n  --color-red-500: #ef4444;\n  --color-blue-500: #3b82f6;\n}\n",
        )
        self.assertEqual(merged["color"]["red-500"], "#ff0000")
        self.assertEqual(merged["color"]["blue-500"], "#3b82f6")

    def test_coverage_separates_not_covered_from_not_a_utility_namespace(self):
        # Collapsing these two would make the report permanently and falsely
        # incomplete: --breakpoint-* can never be covered, because it
        # generates variants rather than classes.
        theme = tailwind_adapter.parse_theme(
            "@theme {\n"
            "  --color-brand: #123456;\n"
            "  --breakpoint-md: 48rem;\n"
            "  --perspective-near: 300px;\n"
            "}\n"
        )
        coverage = tailwind_adapter.namespace_coverage(theme)
        self.assertIn("color", coverage["covered"])
        self.assertIn("breakpoint", coverage["non_utility"])
        self.assertNotIn("breakpoint", coverage["uncovered"])
        self.assertIn("perspective", coverage["uncovered"])

    def test_every_namespace_in_the_table_exists_in_a_real_default_theme(self):
        # The prefix-to-namespace mapping is authored, because it lives only
        # inside Tailwind's minified distribution. This is what keeps it
        # falsifiable: a namespace invented or misspelled fails here.
        with open(EXCERPT, encoding="utf-8") as handle:
            real = tailwind_adapter.parse_theme(handle.read())
        named = set()
        for namespaces in tailwind_adapter.UTILITY_PREFIXES.values():
            named.update(namespaces)
        self.assertTrue(named)
        self.assertEqual(sorted(named - set(real)), [])

    def test_no_two_prefixes_resolve_the_same_key_to_the_same_concept(self):
        # Variety, not presence: a table whose entries all collapsed onto one
        # namespace would satisfy every other test in this class.
        concepts = {
            prefix: tailwind_adapter.concept_id(namespaces[0], "x")
            for prefix, namespaces in tailwind_adapter.UTILITY_PREFIXES.items()
        }
        self.assertGreater(len(set(concepts.values())), 1)
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python3 -m unittest tools.test_tailwind_adapter -v` from the repo root, or `cd tools && python3 -m unittest test_tailwind_adapter -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tailwind_adapter'`

- [ ] **Step 3: Write the excerpt fixture**

`fixtures/tailwind/theme-4.2.1-excerpt.css` — one representative declaration per namespace, copied verbatim from `node_modules/tailwindcss/theme.css` of the recorded version. Keep the header; it is what makes the file checkable.

```css
/* Excerpt of tailwindcss 4.2.1's default theme — one representative
   declaration per namespace, copied verbatim.
   Purpose: the namespace table in tools/tailwind_adapter.py is authored,
   and this is what falsifies it in an environment that installs no npm
   packages. Regenerate with tools/tailwind_adapter.py --refresh-excerpt
   against an installed copy, and record the new version here. */
@theme default {
  --color-red-500: oklch(63.7% 0.237 25.331);
  --text-sm: 0.875rem;
  --font-sans: ui-sans-serif, system-ui, sans-serif;
  --font-weight-bold: 700;
  --leading-normal: 1.5;
  --tracking-tight: -0.025em;
  --radius-md: 0.375rem;
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  --inset-shadow-sm: inset 0 2px 4px rgb(0 0 0 / 0.05);
  --drop-shadow-md: 0 3px 3px rgb(0 0 0 / 0.12);
  --blur-sm: 8px;
  --perspective-near: 300px;
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --animate-spin: spin 1s linear infinite;
  --container-sm: 24rem;
  --max-width-prose: 65ch;
  --aspect-video: 16 / 9;
  --breakpoint-md: 48rem;
  --spacing: 0.25rem;
  --default-transition-duration: 150ms;
}
```

- [ ] **Step 4: Write the module**

```python
#!/usr/bin/env python3
"""Resolve Tailwind utility classes back to the tokens they name.

This is a name-resolution layer over concepts discovery already found, not
a second parser and not a Tailwind emulator. It maps a class name onto a
theme key, or declines.
"""
import re

THEME_BLOCK = re.compile(r"@theme[^{]*\{(.*?)\n\}", re.S)
DECLARATION = re.compile(r"^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);", re.M)

# Namespaces that generate no utility class. Reported as such, never as a
# gap — counting them as uncovered would make the report permanently and
# falsely incomplete.
NON_UTILITY_NAMESPACES = {
    "default": "configures Tailwind itself and generates no utility",
    "breakpoint": "generates variants, not utility classes",
}

# Longest match wins, so multi-word namespaces are listed and a bare
# partition on the first dash is never used.
KNOWN_NAMESPACES = (
    "color", "text", "font-weight", "font", "leading", "tracking", "radius",
    "inset-shadow", "drop-shadow", "shadow", "blur", "perspective", "ease",
    "animate", "container", "max-width", "aspect", "spacing", "breakpoint",
    "default",
)

# prefix -> the namespaces that prefix draws from. Authored: this mapping
# exists only inside Tailwind's minified distribution, and parsing that
# would break in ways this tool could not detect. Falsified instead by
# test_every_namespace_in_the_table_exists_in_a_real_default_theme.
UTILITY_PREFIXES = {
    "bg": ("color",),
    "text": ("color", "text"),
    "border": ("color",),
    "ring": ("color",),
    "fill": ("color",),
    "stroke": ("color",),
    "outline": ("color",),
    "accent": ("color",),
    "caret": ("color",),
    "decoration": ("color",),
    "divide": ("color",),
    "font": ("font", "font-weight"),
    "leading": ("leading",),
    "tracking": ("tracking",),
    "rounded": ("radius",),
    "shadow": ("shadow",),
    "inset-shadow": ("inset-shadow",),
    "drop-shadow": ("drop-shadow",),
    "blur": ("blur",),
    "perspective": ("perspective",),
    "ease": ("ease",),
    "animate": ("animate",),
    "aspect": ("aspect",),
    "max-w": ("container", "max-width"),
    "p": ("spacing",), "px": ("spacing",), "py": ("spacing",),
    "pt": ("spacing",), "pr": ("spacing",), "pb": ("spacing",), "pl": ("spacing",),
    "m": ("spacing",), "mx": ("spacing",), "my": ("spacing",),
    "mt": ("spacing",), "mr": ("spacing",), "mb": ("spacing",), "ml": ("spacing",),
    "gap": ("spacing",), "gap-x": ("spacing",), "gap-y": ("spacing",),
    "space-x": ("spacing",), "space-y": ("spacing",),
    "w": ("spacing", "container"), "h": ("spacing",), "size": ("spacing",),
}


def concept_id(namespace, key):
    """The id discovery gave the custom property this key generates."""
    return namespace if key == "" else "%s-%s" % (namespace, key)


def split_name(name):
    """--drop-shadow-md -> ('drop-shadow', 'md'). Longest namespace wins."""
    bare = name[2:] if name.startswith("--") else name
    for namespace in sorted(KNOWN_NAMESPACES, key=len, reverse=True):
        if bare == namespace:
            return namespace, ""
        if bare.startswith(namespace + "-"):
            return namespace, bare[len(namespace) + 1:]
    return None, bare


def parse_theme(text):
    theme = {}
    for block in THEME_BLOCK.findall(text):
        for name, value in DECLARATION.findall(block):
            namespace, key = split_name(name)
            if namespace is None:
                continue
            theme.setdefault(namespace, {})[key] = value.strip()
    return theme


def theme_map(project_text, default_text=""):
    merged = parse_theme(default_text or "")
    for namespace, keys in parse_theme(project_text or "").items():
        merged.setdefault(namespace, {}).update(keys)
    return merged


def namespace_coverage(theme):
    covered, uncovered, non_utility = [], [], []
    known = set()
    for namespaces in UTILITY_PREFIXES.values():
        known.update(namespaces)
    for namespace in sorted(theme):
        if namespace in NON_UTILITY_NAMESPACES:
            non_utility.append(namespace)
        elif namespace in known:
            covered.append(namespace)
        else:
            uncovered.append(namespace)
    return {"covered": covered, "uncovered": uncovered, "non_utility": non_utility}
```

- [ ] **Step 5: Run the tests and watch them pass**

Run: `cd tools && python3 -m unittest test_tailwind_adapter -v`
Expected: PASS, 6 tests.

- [ ] **Step 6: Watch the falsifier actually fail**

Add `"colour"` to one entry of `UTILITY_PREFIXES`, run the suite, and confirm **exit code 1** — `echo $?` on its own line, never inside a `printf` argument list. Then remove it and confirm exit code 0. A guard nobody has watched fail is a guard nobody has tested.

- [ ] **Step 7: Commit**

```bash
git add tools/tailwind_adapter.py tools/test_tailwind_adapter.py fixtures/tailwind/theme-4.2.1-excerpt.css
git commit -m "feat(tailwind): the theme map, and a namespace table that can be proven wrong"
```

---

### Task 2: `resolve()` — peeling, ambiguity, and the derived scale

**Files:**
- Modify: `tools/tailwind_adapter.py` (append)
- Test: `tools/test_tailwind_adapter.py` (append a second `TestCase`)

**Interfaces:**
- Consumes: `theme_map()`, `concept_id()`, `UTILITY_PREFIXES` from Task 1.
- Produces: `Resolution = namedtuple("Resolution", "state concept candidates derived")` where `state` is one of `"resolved"`, `"ambiguous"`, `"unresolved"`; `resolve(class_name, theme) -> Resolution`; `peel(class_name) -> (base, negative)`.

- [ ] **Step 1: Write the failing tests**

```python
class TestResolve(unittest.TestCase):
    def theme(self):
        return tailwind_adapter.theme_map(
            "@theme {\n"
            "  --color-muted: #eee;\n"
            "  --color-brand: #123456;\n"
            "  --text-brand: 2rem;\n"
            "  --spacing: 0.25rem;\n"
            "  --spacing-lg: 2rem;\n"
            "  --radius-md: 6px;\n"
            "}\n"
        )

    def test_variants_modifiers_and_important_all_peel_to_the_same_base(self):
        theme = self.theme()
        spellings = [
            "bg-muted", "dark:bg-muted", "dark:hover:bg-muted", "md:bg-muted",
            "group-hover:bg-muted", "bg-muted/50", "!bg-muted", "bg-muted!",
            "supports-[display:grid]:bg-muted",
        ]
        results = {s: tailwind_adapter.resolve(s, theme) for s in spellings}
        for spelling, result in results.items():
            self.assertEqual(result.concept, "color-muted", spelling)

    def test_an_ambiguous_prefix_resolves_to_nothing_and_names_both(self):
        # text- draws from --color-* and --text-*. Guessing here attributes a
        # reference to the wrong family, which is worse than not counting it,
        # because it looks like a measurement.
        result = tailwind_adapter.resolve("text-brand", self.theme())
        self.assertEqual(result.state, "ambiguous")
        self.assertIsNone(result.concept)
        self.assertEqual(result.candidates, ("color-brand", "text-brand"))
        self.assertNotEqual(result.concept, result.candidates[0])

    def test_a_derived_step_and_a_named_step_land_differently(self):
        # Variety, not presence: both resolve, and they must not be the same
        # kind of thing, or a derived step would inflate named adoption.
        theme = self.theme()
        derived = tailwind_adapter.resolve("p-4", theme)
        named = tailwind_adapter.resolve("p-lg", theme)
        self.assertEqual(derived.concept, "spacing")
        self.assertTrue(derived.derived)
        self.assertEqual(named.concept, "spacing-lg")
        self.assertFalse(named.derived)
        self.assertNotEqual(derived.concept, named.concept)

    def test_a_key_the_theme_never_declared_resolves_to_nothing(self):
        result = tailwind_adapter.resolve("bg-nonexistent", self.theme())
        self.assertEqual(result.state, "unresolved")
        self.assertIsNone(result.concept)

    def test_an_unknown_prefix_resolves_to_nothing(self):
        result = tailwind_adapter.resolve("scroll-mt-md", self.theme())
        self.assertEqual(result.state, "unresolved")

    def test_no_two_distinct_classes_collapse_onto_one_concept(self):
        theme = self.theme()
        classes = ["bg-muted", "bg-brand", "rounded-md", "p-lg"]
        concepts = [tailwind_adapter.resolve(c, theme).concept for c in classes]
        self.assertEqual(len(set(concepts)), len(classes))
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd tools && python3 -m unittest test_tailwind_adapter.TestResolve -v`
Expected: FAIL — `AttributeError: module 'tailwind_adapter' has no attribute 'resolve'`

- [ ] **Step 3: Implement**

```python
from collections import namedtuple

Resolution = namedtuple("Resolution", "state concept candidates derived")
UNRESOLVED = Resolution("unresolved", None, (), False)
DERIVED_STEP = re.compile(r"^\d+(?:\.\d+)?$")


def strip_variants(class_name):
    """Everything after the last colon that is not inside brackets.

    supports-[display:grid]:bg-muted has two colons and only the second
    separates a variant.
    """
    depth = 0
    cut = -1
    for index, char in enumerate(class_name):
        if char in "[(":
            depth += 1
        elif char in "])":
            depth -= 1
        elif char == ":" and depth == 0:
            cut = index
    return class_name[cut + 1:]


def peel(class_name):
    base = strip_variants(class_name.strip())
    base = base.strip("!")
    depth = 0
    for index, char in enumerate(base):
        if char in "[(":
            depth += 1
        elif char in "])":
            depth -= 1
        elif char == "/" and depth == 0:
            base = base[:index]
            break
    negative = base.startswith("-")
    return (base[1:] if negative else base), negative


def resolve(class_name, theme):
    base, _negative = peel(class_name)
    if not base or "[" in base or "(" in base:
        return UNRESOLVED
    for prefix in sorted(UTILITY_PREFIXES, key=len, reverse=True):
        if base != prefix and not base.startswith(prefix + "-"):
            continue
        key = base[len(prefix):].lstrip("-")
        named, derived = [], []
        for namespace in UTILITY_PREFIXES[prefix]:
            keys = theme.get(namespace) or {}
            if key in keys:
                named.append(concept_id(namespace, key))
            elif "" in keys and DERIVED_STEP.match(key):
                derived.append(concept_id(namespace, ""))
        if len(named) > 1:
            return Resolution("ambiguous", None, tuple(sorted(named)), False)
        if named:
            return Resolution("resolved", named[0], (), False)
        if derived:
            return Resolution("resolved", derived[0], (), True)
        return UNRESOLVED
    return UNRESOLVED
```

- [ ] **Step 4: Run and watch them pass**

Run: `cd tools && python3 -m unittest test_tailwind_adapter -v`
Expected: PASS, 12 tests.

- [ ] **Step 5: Watch two guards fail, in both spellings**

Mutation A, the ambiguity guess — replace the ambiguous branch with `return Resolution("resolved", sorted(named)[0], (), False)`, and separately with `return Resolution("resolved", named[0], (), False)`. Both must go red by exit code.

Mutation B, the derived collapse — replace `Resolution("resolved", derived[0], (), True)` with `... , False)`. Must go red.

Control: a no-op mutation — reorder the two `if named:` / `if derived:` blocks' internal comments — must stay green. Confirm each mutation could actually bite by diffing against a backup; `perl -0pi` exits 0 on no match, so a clean exit proves nothing.

- [ ] **Step 6: Commit**

```bash
git add tools/tailwind_adapter.py tools/test_tailwind_adapter.py
git commit -m "feat(tailwind): resolve a class to a theme key, or decline"
```

---

### Task 3: `classify()` — the three bracket spellings

**Files:**
- Modify: `tools/tailwind_adapter.py` (append)
- Test: `tools/test_tailwind_adapter.py` (append a `TestCase`)

**Interfaces:**
- Consumes: `peel()` from Task 2.
- Produces: `Leak = namedtuple("Leak", "kind value prefix")` where `kind` is `"literal"` or `"redundant"`; `classify(class_name) -> Leak | None`.

- [ ] **Step 1: Write the failing tests**

```python
class TestClassify(unittest.TestCase):
    def test_the_bracket_spellings_produce_different_verdicts(self):
        # Variety, not presence. A classifier that returned "literal" for
        # everything would pass a presence test on each spelling separately.
        verdicts = {
            "bg-[#0F8A83]": tailwind_adapter.classify("bg-[#0F8A83]"),
            "bg-[--brand]": tailwind_adapter.classify("bg-[--brand]"),
            "bg-[var(--brand)]": tailwind_adapter.classify("bg-[var(--brand)]"),
        }
        self.assertEqual(verdicts["bg-[#0F8A83]"].kind, "literal")
        self.assertEqual(verdicts["bg-[--brand]"].kind, "redundant")
        self.assertIsNone(verdicts["bg-[var(--brand)]"])
        kinds = {v.kind if v else None for v in verdicts.values()}
        self.assertEqual(len(kinds), 3)

    def test_the_v4_parenthesis_shorthand_is_a_reference_not_a_leak(self):
        self.assertIsNone(tailwind_adapter.classify("bg-(--brand)"))

    def test_a_measurement_literal_is_a_leak_in_any_family(self):
        self.assertEqual(tailwind_adapter.classify("p-[15px]").kind, "literal")
        self.assertEqual(tailwind_adapter.classify("duration-[240ms]").kind, "literal")

    def test_a_variant_does_not_hide_a_leak(self):
        self.assertEqual(tailwind_adapter.classify("dark:hover:bg-[#0F8A83]").kind, "literal")

    def test_an_ordinary_class_is_not_a_leak(self):
        self.assertIsNone(tailwind_adapter.classify("bg-muted"))
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd tools && python3 -m unittest test_tailwind_adapter.TestClassify -v`
Expected: FAIL — `AttributeError: module 'tailwind_adapter' has no attribute 'classify'`

- [ ] **Step 3: Implement**

```python
Leak = namedtuple("Leak", "kind value prefix")

ARBITRARY = re.compile(r"^(?P<prefix>[a-z-]+)-\[(?P<value>[^\]]*)\]$")
PAREN_SHORTHAND = re.compile(r"^(?P<prefix>[a-z-]+)-\((?P<value>[^)]*)\)$")


def classify(class_name):
    """A bracket-arbitrary value: a raw literal, a dropped reference, or fine.

    bg-[--brand] compiles to invalid CSS and is dropped with no error. The
    element ships unstyled and nothing in the build warns you, which is why
    it is reported ahead of an ordinary literal.
    """
    base, _negative = peel(class_name)
    if PAREN_SHORTHAND.match(base):
        return None
    match = ARBITRARY.match(base)
    if not match:
        return None
    value = match.group("value").strip()
    if value.startswith("var("):
        return None
    if value.startswith("--"):
        return Leak("redundant", value, match.group("prefix"))
    return Leak("literal", value, match.group("prefix"))
```

- [ ] **Step 4: Run and watch them pass**

Run: `cd tools && python3 -m unittest test_tailwind_adapter -v`
Expected: PASS, 17 tests.

- [ ] **Step 5: Watch it fail**

Remove the `value.startswith("--")` branch so a dropped reference is reported as an ordinary literal. The three-verdict test must go red by exit code — if it stays green, the assertion is counting presence and needs rewriting before the branch goes back.

- [ ] **Step 6: Commit**

```bash
git add tools/tailwind_adapter.py tools/test_tailwind_adapter.py
git commit -m "feat(tailwind): three bracket spellings, three verdicts"
```

---

### Task 4: `detect()` and the refusal table

**Files:**
- Modify: `tools/tailwind_adapter.py` (append)
- Test: `tools/test_tailwind_adapter.py` (append a `TestCase`)

**Interfaces:**
- Consumes: `theme_map()` from Task 1.
- Produces: `ThemeSource = namedtuple("ThemeSource", "shape path version theme coverage default_theme_read")`; `detect(root, discovery, read_text=None) -> ThemeSource | None`.

**Deliberate refinement of the spec.** §3 describes the module as having no I/O of its own. Detection has to read stylesheets, so `detect()` takes an injectable `read_text(path)` that defaults to reading from disk. The other three functions stay pure. This is recorded here rather than silently diverging.

- [ ] **Step 1: Write the failing tests**

```python
class TestDetect(unittest.TestCase):
    def discovery(self, *paths):
        return {"owned_import_graph": {"reachable": {p: {"via": []} for p in paths}}}

    def reader(self, files):
        def read_text(path):
            if path not in files:
                raise OSError(path)
            return files[path]
        return read_text

    def test_no_tailwind_means_no_adapter(self):
        files = {"app/main.css": ":root { --brand: #123456; }"}
        found = tailwind_adapter.detect(
            "/repo", self.discovery(*files), self.reader(files))
        self.assertIsNone(found)

    def test_an_at_theme_block_is_enough(self):
        files = {"app/globals.css": '@import "tailwindcss";\n@theme {\n  --color-brand: #123456;\n}\n'}
        found = tailwind_adapter.detect(
            "/repo", self.discovery(*files), self.reader(files))
        self.assertEqual(found.shape, "v4-theme-block")
        self.assertEqual(found.path, "app/globals.css")
        self.assertEqual(found.theme["color"]["brand"], "#123456")

    def test_an_unreadable_default_theme_is_recorded_never_invented(self):
        files = {"app/globals.css": "@theme {\n  --color-brand: #123456;\n}\n"}
        found = tailwind_adapter.detect(
            "/repo", self.discovery(*files), self.reader(files))
        self.assertFalse(found.default_theme_read)
        self.assertEqual(found.version, "unrecorded")

    def test_the_version_comes_from_the_manifest_when_there_is_one(self):
        files = {
            "app/globals.css": "@theme {\n  --color-brand: #123456;\n}\n",
            "package.json": '{"devDependencies": {"tailwindcss": "^4.2.1"}}',
        }
        found = tailwind_adapter.detect(
            "/repo", self.discovery("app/globals.css"), self.reader(files))
        self.assertEqual(found.version, "4.2.1")

    def test_an_unparseable_theme_block_declines_rather_than_half_resolving(self):
        files = {"app/globals.css": "@theme {\n  --color-brand: #123456\n"}
        found = tailwind_adapter.detect(
            "/repo", self.discovery(*files), self.reader(files))
        self.assertIsNone(found)
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd tools && python3 -m unittest test_tailwind_adapter.TestDetect -v`
Expected: FAIL — `AttributeError: module 'tailwind_adapter' has no attribute 'detect'`

- [ ] **Step 3: Implement**

```python
import json
import os

ThemeSource = namedtuple(
    "ThemeSource", "shape path version theme coverage default_theme_read")

TAILWIND_MARKER = re.compile(r'@import\s+["\']tailwindcss["\']|@theme\b')
VERSION = re.compile(r"[\^~>=<\s]*([0-9]+\.[0-9]+\.[0-9]+)")
DEFAULT_THEME_PATH = os.path.join("node_modules", "tailwindcss", "theme.css")
STYLE_SUFFIXES = (".css", ".scss", ".sass", ".less")


def _disk_reader(root):
    def read_text(path):
        with open(os.path.join(root, path), encoding="utf-8", errors="replace") as handle:
            return handle.read()
    return read_text


def _version_from_manifest(read_text):
    try:
        manifest = json.loads(read_text("package.json"))
    except (OSError, ValueError):
        return "unrecorded"
    for field in ("dependencies", "devDependencies"):
        pinned = (manifest.get(field) or {}).get("tailwindcss")
        if pinned:
            match = VERSION.search(pinned)
            if match:
                return match.group(1)
    return "unrecorded"


def detect(root, discovery, read_text=None):
    """The theme source, or None. None means every output stays as it is."""
    read_text = read_text or _disk_reader(root)
    reachable = (discovery.get("owned_import_graph") or {}).get("reachable") or {}
    for path in sorted(reachable):
        if not path.endswith(STYLE_SUFFIXES):
            continue
        try:
            text = read_text(path)
        except OSError:
            continue
        if not TAILWIND_MARKER.search(text):
            continue
        project = parse_theme(text)
        if not project:
            continue
        try:
            default_text = read_text(DEFAULT_THEME_PATH)
            default_read = True
        except OSError:
            default_text, default_read = "", False
        theme = theme_map(text, default_text)
        return ThemeSource(
            shape="v4-theme-block",
            path=path,
            version=_version_from_manifest(read_text),
            theme=theme,
            coverage=namespace_coverage(theme),
            default_theme_read=default_read,
        )
    return None
```

- [ ] **Step 4: Run and watch them pass**

Run: `cd tools && python3 -m unittest test_tailwind_adapter -v`
Expected: PASS, 22 tests.

- [ ] **Step 5: Watch it fail**

Make `detect()` return a `ThemeSource` with an empty theme instead of `None` when no marker is found. `test_no_tailwind_means_no_adapter` must go red — that guard is the one protecting every "nothing changes when there is no Tailwind" promise downstream.

- [ ] **Step 6: Commit**

```bash
git add tools/tailwind_adapter.py tools/test_tailwind_adapter.py
git commit -m "feat(tailwind): detection, and a refusal that degrades to today"
```

---

### Task 5: The usage scanner gains a third syntax

**Files:**
- Modify: `tools/analyze_component_usage.py` — `references_in_text()` at `:262`, `analyze()` at `:336`, the `measurement` block at `:454`
- Test: `tools/test_analyze_component_usage.py` (append a `TestCase`)

**Interfaces:**
- Consumes: `tailwind_adapter.detect()`, `.resolve()`, `.classify()`.
- Produces: `references_in_text(text, concepts, theme=None, scan_classes=False)` — the two existing positional arguments keep their meaning, so every current caller is unchanged. The result grows a `utility_leaks` list and the `measurement` entry for `framework-generated-utility` changes state when an adapter ran.

**Only quoted string literals are scanned.** `cn("bg-muted", cond && "text-foreground")` is the dominant idiom, so scanning `className="…"` alone would miss most real usage. Scanning quoted strings also excludes JSX text nodes by construction, which is what keeps prose out. The residual risk — a quoted prose string containing an exact theme key — is declared in the measurement evidence rather than pretended away.

- [ ] **Step 1: Share the existing test helper**

`repo()` currently lives on `TestComponentUsage`. Lift it into a mixin so the
new class can build a repository the same way, and change the existing class to
use it. No test body changes.

```python
class RepoFixture:
    def repo(self, files, concepts=None, sources=None, owned=None,
             reachable_paths=None, component_roots=None):
        ...the existing body, moved verbatim...


class TestComponentUsage(RepoFixture, unittest.TestCase):
    ...unchanged...
```

Run `cd tools && python3 -m unittest test_analyze_component_usage -v` and expect
the existing tests to pass before writing a new one. A refactor and a feature
must not fail together, or neither can be diagnosed.

- [ ] **Step 3: Write the failing tests**

```python
class TestTailwindUtilities(RepoFixture, unittest.TestCase):
    THEME = '@import "tailwindcss";\n@theme {\n  --color-muted: #eee;\n  --spacing: 0.25rem;\n}\n'

    def test_a_utility_class_counts_as_a_reference(self):
        root, discovery, tokens = self.repo({
            "app/globals.css": self.THEME,
            "components/card.tsx": 'export const Card = () => <div className="bg-muted p-4" />;',
        }, concepts=[{"id": "color-muted", "family": "color"},
                     {"id": "spacing", "family": "spacing"}])
        result = analyze_component_usage.analyze(root, discovery, tokens)
        card = [u for u in result["top_20"] if u["name"] == "card"][0]
        self.assertIn("tailwind-utility", card["syntaxes"])
        self.assertEqual({t["id"] for t in card["tokens"]}, {"color-muted", "spacing"})

    def test_a_class_inside_a_helper_call_counts_too(self):
        root, discovery, tokens = self.repo({
            "app/globals.css": self.THEME,
            "components/badge.tsx": 'const c = cn("bg-muted", active && "p-4");',
        }, concepts=[{"id": "color-muted", "family": "color"},
                     {"id": "spacing", "family": "spacing"}])
        result = analyze_component_usage.analyze(root, discovery, tokens)
        badge = [u for u in result["top_20"] if u["name"] == "badge"][0]
        self.assertEqual(badge["references"], 2)

    def test_without_tailwind_nothing_about_the_result_changes(self):
        files = {"app/card.scss": ".card { color: var(--brand-primary); }"}
        root, discovery, tokens = self.repo(files)
        result = analyze_component_usage.analyze(root, discovery, tokens)
        states = {m["syntax"]: m["state"] for m in result["measurement"]}
        self.assertEqual(states["framework-generated-utility"], "not-visible")

    def test_the_measurement_state_flips_only_when_an_adapter_ran(self):
        root, discovery, tokens = self.repo({
            "app/globals.css": self.THEME,
            "components/card.tsx": 'const c = "bg-muted";',
        }, concepts=[{"id": "color-muted", "family": "color"}])
        result = analyze_component_usage.analyze(root, discovery, tokens)
        entry = [m for m in result["measurement"]
                 if m["syntax"] == "framework-generated-utility"][0]
        self.assertEqual(entry["state"], "counted")
        self.assertIn("app/globals.css", entry["evidence"])

    def test_an_ambiguous_class_is_reported_and_counted_as_nothing(self):
        theme = ('@theme {\n  --color-brand: #123456;\n  --text-brand: 2rem;\n}\n')
        root, discovery, tokens = self.repo({
            "app/globals.css": theme,
            "components/card.tsx": 'const c = "text-brand";',
        }, concepts=[{"id": "color-brand", "family": "color"},
                     {"id": "text-brand", "family": "typography"}])
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["top_20"], [])
        self.assertEqual(result["utility_ambiguous"][0]["class"], "text-brand")

    def test_a_utility_shaped_string_naming_no_key_contributes_nothing(self):
        root, discovery, tokens = self.repo({
            "app/globals.css": self.THEME,
            "components/card.tsx": 'const help = "pass bg-notatoken to the wrapper";',
        }, concepts=[{"id": "color-muted", "family": "color"}])
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["top_20"], [])

    def test_the_detected_version_is_handed_on_for_run_framework_versions(self):
        # validate_run's coverage grade depends on this, and until now a
        # person typed it in by hand.
        root, discovery, tokens = self.repo({
            "app/globals.css": self.THEME,
            "package.json": '{"devDependencies": {"tailwindcss": "^4.2.1"}}',
            "components/card.tsx": 'const c = "bg-muted";',
        }, concepts=[{"id": "color-muted", "family": "color"}])
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["framework_versions"], {"tailwindcss": "4.2.1"})

    def test_the_three_syntaxes_do_not_collapse_into_one_count(self):
        # Variety, not presence: a scanner that tagged every reference
        # "tailwind-utility" would satisfy the first test in this class.
        root, discovery, tokens = self.repo({
            "app/globals.css": self.THEME,
            "components/card.tsx": 'const c = "bg-muted";',
            "components/card.scss": ".card { color: var(--color-muted); gap: $space-sm; }",
        }, concepts=[{"id": "color-muted", "family": "color"},
                     {"id": "space-sm", "family": "spacing"}])
        result = analyze_component_usage.analyze(root, discovery, tokens)
        card = [u for u in result["top_20"] if u["name"] == "card"][0]
        self.assertEqual(sorted(card["syntaxes"]),
                         ["css-custom-property", "scss-variable", "tailwind-utility"])
```

- [ ] **Step 3: Run and watch them fail**

Run: `cd tools && python3 -m unittest test_analyze_component_usage.TestTailwindUtilities -v`
Expected: FAIL — `KeyError: 'utility_ambiguous'` and a missing `tailwind-utility` syntax.

- [ ] **Step 4: Implement the scanner branch**

```python
import tailwind_adapter  # noqa: E402  (beside the existing cli import)

STRING_LITERAL = re.compile(r"""(?P<quote>['"`])(?P<body>[^'"`\n]*)(?P=quote)""")
CLASS_TOKEN = re.compile(r"[A-Za-z0-9:_\-\[\]\(\)./#!%]+")


def utility_references(text, concepts, theme):
    """Canonical references, ambiguities and leaks from quoted class strings."""
    refs, ambiguous, leaks = [], [], []
    for number, line in enumerate(strip_comments_preserving_lines(text).splitlines(), 1):
        for literal in STRING_LITERAL.finditer(line):
            for candidate in CLASS_TOKEN.findall(literal.group("body")):
                leak = tailwind_adapter.classify(candidate)
                if leak:
                    leaks.append((leak, candidate, number))
                    continue
                result = tailwind_adapter.resolve(candidate, theme)
                if result.state == "ambiguous":
                    ambiguous.append((candidate, result.candidates, number))
                elif result.state == "resolved" and result.concept in concepts:
                    refs.append((result.concept, number, "tailwind-utility"))
    return refs, ambiguous, leaks
```

Then extend the existing function, leaving both current branches exactly as they are:

```python
def references_in_text(text, concepts, theme=None, scan_classes=False):
    """Return canonical token references with exact line evidence."""
    found = []
    ...unchanged CSS and SCSS branches...
    if theme and scan_classes:
        refs, _ambiguous, _leaks = utility_references(text, concepts, theme)
        found.extend(refs)
    return found
```

In `analyze()`, detect once before the file loop and collect the extra findings:

```python
    source = tailwind_adapter.detect(root, discovery)
    theme = source.theme if source else None
    ambiguous_seen, leaks_seen = [], []
    ...
        scan_classes = os.path.splitext(path)[1].lower() not in STYLE_EXTENSIONS
        refs = references_in_text(text, concepts, theme, scan_classes)
        if theme and scan_classes:
            _r, ambiguous, leaks = utility_references(text, concepts, theme)
            ambiguous_seen.extend({"class": c, "candidates": list(k),
                                   "location": "%s:%d" % (path, n)}
                                  for c, k, n in ambiguous)
            leaks_seen.extend({"kind": leak.kind, "value": leak.value,
                               "prefix": leak.prefix, "class": c,
                               "location": "%s:%d" % (path, n)}
                              for leak, c, n in leaks)
```

And the measurement entry, replacing only the third row:

```python
            utility_measurement(source),
```

```python
def utility_measurement(source):
    if source is None:
        return {"syntax": "framework-generated-utility", "state": "not-visible",
                "evidence": "requires an active adapter to resolve utility output to canonical tokens"}
    return {
        "syntax": "framework-generated-utility", "state": "counted",
        "evidence": (
            "resolved against %s (%s, tailwindcss %s); default theme %s. "
            "Quoted string literals are scanned, so a JSX text node is excluded "
            "by construction and a quoted prose string naming an exact theme key "
            "would be counted."
            % (source.path, source.shape, source.version,
               "read" if source.default_theme_read else "not readable")),
    }
```

Add `"utility_ambiguous": ambiguous_seen`, `"utility_leaks": leaks_seen`,
`"utility_namespace_coverage": source.coverage if source else None`, and
`"framework_versions": {"tailwindcss": source.version} if source else {}` to the
returned dict.

**That last field is a spec requirement, not a convenience.** §6 says the version
is recorded in `run.framework_versions`, which `SKILL.md` Stage 2 currently asks
a human to fill in by hand and `validate_run` depends on for the `coverage`
grade. `detect()` reads it mechanically, so it must be handed onward rather than
kept inside the measurement string. Task 8 changes the Stage 2 instruction to
read this field.

- [ ] **Step 5: Run the whole suite**

Run: `python3 -m unittest discover -s tools -p 'test_*.py'`
Expected: PASS. The count is 604 plus the tests added in Tasks 1–5. If an existing test fails, the two-positional-argument contract was broken — fix that rather than the test.

- [ ] **Step 6: Watch three guards fail**

Mutate `scan_classes` to `True` for stylesheets — `test_the_three_syntaxes_do_not_collapse_into_one_count` should still pass, which proves it is **not** the guard for that; find the test that does go red, and if none does, the suite is missing one. Mutate `result.concept in concepts` to `True` so unknown keys count; `test_a_utility_shaped_string_naming_no_key_contributes_nothing` must go red. Mutate `utility_measurement` to always return the `counted` row; `test_without_tailwind_nothing_about_the_result_changes` must go red.

- [ ] **Step 7: Commit**

```bash
git add tools/analyze_component_usage.py tools/test_analyze_component_usage.py
git commit -m "feat(usage): a Tailwind utility is a token reference, and says how it was counted"
```

---

### Task 6: A bracket literal in a .tsx file becomes reachable

**Files:**
- Modify: `tools/audit_literal_colors.py` — `audit()` at `:37`, the stylesheet filter at `:43`
- Test: `tools/test_audit_literal_colors.py` (append a `TestCase`)

**Interfaces:**
- Consumes: `utility_leaks` rows produced by Task 5 (`{"kind", "value", "prefix", "class", "location"}`).
- Produces: `audit(root, discovery, tokens, utility_leaks=None)` — the fourth argument defaults to `None`, so the current call site is unchanged. Adds the tier `utility-bypass-candidate`.

**Scope note.** This audit is color-only: its `HEX` pattern is what it knows how to compare. So only bracket values that are hex colors enter it. Non-color bracket literals (`p-[15px]`, `duration-[240ms]`) and every `redundant` finding stay in Task 5's `utility_leaks`, which is reported whole — nothing is dropped, and nothing is filed under a comparison that was never made.

- [ ] **Step 1: Write the failing tests**

```python
class TestUtilityBypass(unittest.TestCase):
    def setUp(self):
        # One stylesheet leak already present, so the utility finding has
        # something to stay distinguishable from.
        self.root = tempfile.mkdtemp()
        path = os.path.join(self.root, "app/card.scss")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(".card { color: #ffffff; }")
        self.discovery = {"owned_import_graph": {"reachable": {"app/card.scss": {}}}}
        self.tokens = {"sources": [], "concepts": [
            {"id": "surface", "family": "color",
             "representations": ["css-custom-property"], "values": ["#ffffff"]}]}

    def test_a_hex_in_a_bracket_class_becomes_a_finding(self):
        leaks = [{"kind": "literal", "value": "#0F8A83", "prefix": "bg",
                  "class": "bg-[#0F8A83]", "location": "components/card.tsx:12"}]
        result = audit_literal_colors.audit(
            self.root, self.discovery, self.tokens, leaks)
        tiers = {f["tier"] for f in result["exact_value_candidates"] + result["uncovered_candidates"]}
        self.assertIn("utility-bypass-candidate", tiers)

    def test_a_stylesheet_finding_and_a_utility_finding_stay_distinguishable(self):
        # Variety, not presence. Averaging a JSX bypass into a stylesheet
        # leak is how a clean CSS result and eleven bypasses were both true.
        leaks = [{"kind": "literal", "value": "#0F8A83", "prefix": "bg",
                  "class": "bg-[#0F8A83]", "location": "components/card.tsx:12"}]
        result = audit_literal_colors.audit(
            self.root, self.discovery, self.tokens, leaks)
        rows = result["exact_value_candidates"] + result["uncovered_candidates"]
        tiers = [f["tier"] for f in rows]
        self.assertEqual(len(set(tiers)), 2)

    def test_a_utility_bypass_is_never_safe_to_automate(self):
        from findings import is_automatable
        self.assertFalse(is_automatable("utility-bypass-candidate", "manual review"))

    def test_passing_no_leaks_leaves_the_result_byte_identical(self):
        before = audit_literal_colors.audit(self.root, self.discovery, self.tokens)
        after = audit_literal_colors.audit(self.root, self.discovery, self.tokens, None)
        self.assertEqual(before, after)
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd tools && python3 -m unittest test_audit_literal_colors.TestUtilityBypass -v`
Expected: FAIL — `TypeError: audit() takes 3 positional arguments but 4 were given`

- [ ] **Step 3: Implement**

Take the new argument, and fold hex-valued utility leaks into the same `groups` dict the stylesheet walk builds, before candidates are matched:

```python
def audit(root, discovery, tokens, utility_leaks=None):
    ...
    for leak in utility_leaks or []:
        if leak.get("kind") != "literal" or not HEX.fullmatch(leak["value"].strip()):
            continue
        literal = normalize_literal(leak["value"])
        path = leak["location"].rsplit(":", 1)[0]
        item = groups.setdefault(literal, {"literal": literal, "locations": [],
                                           "files": set(), "properties": set()})
        item["locations"].append(leak["location"])
        item["files"].add(path)
        item["properties"].add("%s (utility)" % leak["prefix"])
        item["utility"] = True
```

Then, where the payload is built, choose the tier from that mark:

```python
        tier = ("utility-bypass-candidate" if group.get("utility")
                else ("exact-value-candidate" if candidates else "uncovered-candidate"))
```

Leave `AUTOMATABLE_TIERS` in `findings.py` untouched: a tier absent from that set is non-automatable by construction, which is the correct default and what `test_a_utility_bypass_is_never_safe_to_automate` pins.

- [ ] **Step 4: Run the whole suite**

Run: `python3 -m unittest discover -s tools -p 'test_*.py'`
Expected: PASS.

- [ ] **Step 5: Watch it fail**

Add `"utility-bypass-candidate"` to `AUTOMATABLE_TIERS`; the automation guard must go red. Remove the `HEX.fullmatch` filter so `p-[15px]` enters a color audit; the two-tier test must go red.

- [ ] **Step 6: Wire the two together in the runner**

`audit_literal_colors.main()` gains an optional `--usage PATH` reading the usage JSON Task 5 writes, passing `usage["utility_leaks"]` into `audit()`. Without the flag, behavior is exactly as it is today.

- [ ] **Step 7: Commit**

```bash
git add tools/audit_literal_colors.py tools/test_audit_literal_colors.py
git commit -m "fix(leakage): a bracket literal in a .tsx file stops being unreachable"
```

---

### Task 7: The fixture repository gains a Tailwind surface

**Files:**
- Create: `fixtures/repo/components/toolbar.tsx`
- Create: `fixtures/repo/node_modules/tailwindcss/theme.css`
- Modify: `fixtures/repo/app/globals.css` (the existing `@theme` block)
- Modify: `fixtures/expected.json`
- Modify: `fixtures/README.md`
- Test: `tools/test_fixture.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: no new code interface. This task proves the pieces work together on the shared fixture rather than on temp directories.

**This task changes golden numbers, and that is the risk.** `test_fixture.py:173` asserts `token_count == 21` against `fixtures/expected.json`. Adding two declarations to the fixture's `@theme` makes it **23**. Update the golden file **in the same commit**, and extend its `_token_count_note` to say what the two new ones are and why. A golden number changed without a note is indistinguishable from a regression, and this repository has twice had older work quietly undo newer work.

- [ ] **Step 1: Write the failing tests**

```python
class TestTailwindSurface(unittest.TestCase):
    def test_the_theme_declares_the_ambiguous_pair_on_purpose(self):
        text = read("app/globals.css")
        self.assertIn("--color-brand:", text)
        self.assertIn("--text-brand:", text)

    def test_the_toolbar_consumes_every_shape_the_adapter_must_handle(self):
        text = read("components/toolbar.tsx")
        for spelling in ("bg-muted", "dark:bg-muted", "p-4", "p-lg",
                         "text-brand", "bg-[#0F8A83]", "bg-[--brand]",
                         "bg-[var(--blue-500)]"):
            self.assertIn(spelling, text, spelling)

    def test_the_vendored_default_theme_is_present_for_the_merge(self):
        self.assertTrue(os.path.exists(
            os.path.join(FIXTURE, "node_modules", "tailwindcss", "theme.css")))

    def test_the_golden_token_count_matches_what_the_theme_now_declares(self):
        self.assertEqual(len(declared_tokens()), EXPECTED["counts"]["token_count"])
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd tools && python3 -m unittest test_fixture -v`
Expected: FAIL — the toolbar does not exist, and once the theme gains two declarations, `test_the_golden_token_count_matches_what_the_theme_now_declares` fails at 23 against a golden 21.

- [ ] **Step 3: Write the fixture surface**

Append to the `@theme` block in `fixtures/repo/app/globals.css`:

```css
  --color-brand: #2563eb;
  --text-brand: 2rem;
```

`fixtures/repo/components/toolbar.tsx`:

```tsx
// Every shape the Tailwind adapter has to handle, in one file.
// bg-[--brand] is deliberate: it compiles to invalid CSS and is dropped
// with no error, so the element ships unstyled and nothing warns you.
export const Toolbar = ({ active }) => (
  <div
    className={cn(
      "bg-muted dark:bg-muted p-4 p-lg",
      active && "text-brand",
      "bg-[#0F8A83] bg-[--brand] bg-[var(--blue-500)]",
    )}
  />
);
```

`fixtures/repo/node_modules/tailwindcss/theme.css` — a copy of the excerpt written in Task 1, so the default-theme merge is exercised on the fixture rather than assumed. `node_modules` is already in `EXCLUDED_PARTS`, so this file is never scanned as a consumer; it is read only by `detect()`, by path.

- [ ] **Step 4: Update the golden file**

In `fixtures/expected.json`, set `counts.token_count` to `23` and extend `_token_count_note`:

```
"23 concepts. 21 from before, plus --color-brand and --text-brand, declared
together on purpose: text- draws from both --color-* and --text-*, so
text-brand is the fixture's ambiguous case and must resolve to nothing."
```

Add a `tailwind` block recording what the surface proves, alongside the existing `leaks` block:

```json
"tailwind": {
  "theme_source": "app/globals.css",
  "shape": "v4-theme-block",
  "version": "4.3.0",
  "resolved": ["bg-muted", "dark:bg-muted", "p-4", "p-lg", "bg-[var(--blue-500)]"],
  "ambiguous": ["text-brand"],
  "leaks": {"literal": ["bg-[#0F8A83]"], "redundant": ["bg-[--brand]"]},
  "_note": "p-4 is a derived step off --spacing and p-lg is a named step off --spacing-lg. They must not land in the same count."
}
```

Document the new surface in `fixtures/README.md` in the same style as the existing rows.

- [ ] **Step 5: Run everything**

Run: `python3 -m unittest discover -s tools -p 'test_*.py'`
Expected: PASS.

Then run the fixture end to end and read the result rather than trusting it:

```bash
python3 tools/discover_environment.py fixtures/repo --json /tmp/env.json
python3 tools/discover_tokens.py fixtures/repo --json /tmp/tokens.json
python3 tools/analyze_component_usage.py fixtures/repo --discovery /tmp/disc.json --tokens /tmp/tokens.json --json /tmp/usage.json
python3 -c "import json; u=json.load(open('/tmp/usage.json')); print(json.dumps({k: u[k] for k in ('measurement','utility_ambiguous','utility_leaks','utility_namespace_coverage')}, indent=2))"
```

Confirm by eye: `text-brand` is in `utility_ambiguous` and in no token's reference list; both leak kinds appear; `p-4` and `p-lg` resolved to different concepts.

- [ ] **Step 6: Commit**

```bash
git add fixtures tools/test_fixture.py
git commit -m "test(fixture): a Tailwind surface, and the golden count that moves with it"
```

---

### Task 8: Register the mutations, regenerate the example, and tell the reader

**Files:**
- Modify: `tools/mutations.json`
- Modify: `references/adapters/tailwind.md`
- Modify: `README.md`, `CHANGELOG.md`
- Regenerate: `examples/shadcn-ui/`
- Delete: `docs/superpowers/specs/2026-09-12-tailwind-utility-adapter-design.md`, `docs/superpowers/plans/2026-09-12-tailwind-utility-adapter.md`

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces: the shipped state.

- [ ] **Step 1: Register the mutations**

`tools/mutations.json` is a list of `{"name", "file", "old", "new", "tests"}`. Add one entry per mutation watched in Tasks 1–6, plus one control that must stay green:

```json
{
  "name": "ambiguous class resolves to its first candidate",
  "file": "tools/tailwind_adapter.py",
  "old": "            return Resolution(\"ambiguous\", None, tuple(sorted(named)), False)",
  "new": "            return Resolution(\"resolved\", sorted(named)[0], (), False)",
  "tests": ["test_tailwind_adapter.TestResolve"]
},
{
  "name": "a derived step is recorded as a named one",
  "file": "tools/tailwind_adapter.py",
  "old": "            return Resolution(\"resolved\", derived[0], (), True)",
  "new": "            return Resolution(\"resolved\", derived[0], (), False)",
  "tests": ["test_tailwind_adapter.TestResolve"]
},
{
  "name": "a dropped reference is reported as an ordinary literal",
  "file": "tools/tailwind_adapter.py",
  "old": "    if value.startswith(\"--\"):",
  "new": "    if False:",
  "tests": ["test_tailwind_adapter.TestClassify"]
},
{
  "name": "the measurement claims counted with no adapter",
  "file": "tools/analyze_component_usage.py",
  "old": "    if source is None:",
  "new": "    if False:",
  "tests": ["test_analyze_component_usage.TestTailwindUtilities"]
},
{
  "name": "a utility bypass becomes safe to automate",
  "file": "tools/audit_literal_colors.py",
  "old": "        tier = (\"utility-bypass-candidate\" if group.get(\"utility\")",
  "new": "        tier = (\"exact-value-candidate\" if group.get(\"utility\")",
  "tests": ["test_audit_literal_colors.TestUtilityBypass"]
}
```

- [ ] **Step 2: Run the mutation harness and read what it says**

Run: `python3 tools/mutate.py`
Expected: every new mutation **bites**, controls hold, zero weak. A mutation that applies and leaves the suite green gets its injected code read before anything is written down — it may be a runtime no-op rather than a weak guard.

- [ ] **Step 3: Regenerate the shadcn-ui example**

shadcn-ui is a Tailwind codebase, so its numbers move. Against a fresh
`shadcn-ui/ui` checkout, run Stage 1 as `SKILL.md` documents it:

```bash
python3 tools/discover_environment.py <root> --json .token-vitals/discovery.json
python3 tools/discover_tokens.py <root> --discovery .token-vitals/discovery.json --update-discovery --json .token-vitals/tokens.json
python3 tools/analyze_component_usage.py <root> --discovery .token-vitals/discovery.json --tokens .token-vitals/tokens.json --json .token-vitals/components.json
python3 tools/audit_literal_colors.py <root> --discovery .token-vitals/discovery.json --tokens .token-vitals/tokens.json --usage .token-vitals/components.json --json .token-vitals/literal-colors.json
```

Stages 2–7 are judgment, not scripts — the published example's `decisions`
array is where its exclusions live, and no flag reproduces them. Carry those
decisions forward rather than re-deriving them; re-running Stage 1 alone
reports every concept the tools can see, which is not what the example claims.

Record before and after for the PR body — concepts, conflicts, adoption, and
the new utility figures. Shipping the old numbers beside an adapter that
changes them recreates exactly the staleness #29 fixed.

**Do not use `render_discovery.py --refresh-template` to update the example.**
It fills only the discovery region and replaces real findings with demo
content.

- [ ] **Step 4: Re-run the nineteen validation rules**

Run: `python3 tools/validate_run.py examples/shadcn-ui/report.json`
Expected: all nineteen hold. If one shifts, explain it in the PR — never adjust the rule to match the new output.

- [ ] **Step 5: Tell the reader**

- `references/adapters/tailwind.md` — a short section saying the resolution and leak checks now have a tool behind them, what it declines (ambiguous classes, derived steps as named steps), and that the namespace table is authored and version-stamped. Keep the existing prose; this is an addition.
- `SKILL.md` Stage 2 — `run.framework_versions` is filled from the usage
  tool's `framework_versions` field when an adapter detected one, and typed in
  by hand only when it did not. This is the sentence §6 of the spec was about.
- `README.md` — a row for `tools/tailwind_adapter.py` in the tools table.
- `CHANGELOG.md` — an entry naming the two mechanisms closed: utility classes were invisible to the usage scanner, and `audit_literal_colors.py`'s stylesheet filter made a bracket literal in a `.tsx` file unreachable rather than merely uncounted.

Run `python3 tools/check_voice.py SKILL.md README.md references/adapters/tailwind.md` and expect exit 0.

- [ ] **Step 6: Prune the working documents**

Delete the spec and this plan, and say so in the changelog entry. #18 removed the earlier specs because they had stopped participating in the skill; these stop participating the moment the work ships, and the repository ships as a skill package.

- [ ] **Step 7: Full suite, then commit**

```bash
python3 -m unittest discover -s tools -p 'test_*.py'
python3 tools/palette.py && python3 tools/taxonomy.py --check
git add -A
git commit -m "docs(tailwind): the adapter's record, and the example regenerated against it"
```

- [ ] **Step 8: Open the pull request**

Push the branch and open a PR whose body names: the two mechanisms closed, the before/after figures from the regenerated example, the mutation result, and what stays out of scope (orphans from the Tailwind side, mode gaps, arbitrary properties, plugins, `@apply`, v3). Quote figures from the private proving-ground run without naming its paths or shipping its report.
