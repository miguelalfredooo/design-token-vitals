#!/usr/bin/env python3
"""Resolve Tailwind utility classes back to the tokens they name.

This is a name-resolution layer over concepts discovery already found, not
a second parser and not a Tailwind emulator. It maps a class name onto a
theme key, or declines.
"""
from collections import namedtuple
import json
import os
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

# Namespaces the prefix table deliberately does not cover yet. Empty today.
# An entry here is a recorded decision; a namespace missing from BOTH this
# set and UTILITY_PREFIXES fails the table guard, which is how a new
# Tailwind version's namespace gets noticed instead of silently uncounted.
TABLE_GAPS = frozenset()

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
    # Fall back to first dash-segment for unknown namespaces.
    if "-" in bare:
        parts = bare.split("-", 1)
        return parts[0], parts[1]
    return bare, ""


def parse_theme(text):
    theme = {}
    for block in THEME_BLOCK.findall(text):
        for name, value in DECLARATION.findall(block):
            namespace, key = split_name(name)
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
