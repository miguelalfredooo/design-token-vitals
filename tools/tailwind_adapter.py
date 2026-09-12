#!/usr/bin/env python3
"""Resolve Tailwind utility classes back to the tokens they name.

This is a name-resolution layer over concepts discovery already found, not
a second parser and not a Tailwind emulator. It maps a class name onto a
theme key, or declines.
"""
import re
from collections import namedtuple

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
