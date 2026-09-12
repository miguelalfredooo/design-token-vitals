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
