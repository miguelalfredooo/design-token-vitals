#!/usr/bin/env python3
"""Discover reachable token sources and collapse projections into concepts."""
import argparse
from collections import Counter
import hashlib
import json
import os
import re
import sys
import subprocess
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cli import EXIT_OK, add_json_flag, emit_json  # noqa: E402
from taxonomy import FAMILIES  # noqa: E402
from analyze_component_usage import strip_comments_preserving_lines  # noqa: E402


CSS_DECL_START = re.compile(
    r"(?m)(?:^|[;{])[ \t]*(--[a-zA-Z0-9_-]+)\s*:\s*"
)
SCSS_DECL = re.compile(r"(?m)^\s*(\$[a-zA-Z0-9_-]+)\s*:\s*([^;\n]+?)(?:\s*!default)?\s*;")
MAP_START = re.compile(r"(?m)^\s*\$([a-zA-Z0-9_-]+)\s*:\s*\(\s*$")
MAP_BRANCH = re.compile(r"^\s*['\"]?([a-zA-Z0-9_-]+)['\"]?\s*:\s*\(\s*$")
MAP_LEAF = re.compile(r"^\s*['\"]?([a-zA-Z0-9_-]+)['\"]?\s*:\s*([^,()]+),?\s*$")
SOURCE_NAME = re.compile(r"(?:token|variable|definition|primitive|semantic|palette|color|typograph|font|spacing|layout|radius|theme)", re.I)
ROOT_START = re.compile(r":root\b[^\{]*\{")
COLOR_VALUE = re.compile(r"(?:#[0-9a-f]{3,8}\b|(?:rgb|hsl|oklch|lab|color)\()", re.I)
CONCRETE_COLOR = re.compile(
    r"^\s*(?:#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})|"
    r"(?:rgba?|hsla?|oklch|lab|color)\([^;{}]+\))\s*$",
    re.I,
)
BRAND_CONTEXT = re.compile(r"\b(?:brand|visual[ -]identity)\b", re.I)
FONT_FACE = re.compile(r"@font-face\s*\{(.*?)\}", re.I | re.S)
FONT_FACE_FAMILY = re.compile(r"font-family\s*:\s*([^;]+)", re.I)
FONT_FACE_URL = re.compile(r"url\(\s*(['\"]?)([^)'\"]+)\1\s*\)", re.I)
FONT_MAGIC = {
    "woff2": (b"wOF2",),
    "woff": (b"wOFF",),
    "ttf": (b"\x00\x01\x00\x00", b"true"),
    "otf": (b"OTTO",),
}
MAX_EMBEDDED_FONT_BYTES = 5 * 1024 * 1024
THIRD_PARTY_BRAND_NAMES = {
    "adobe", "apple", "discord", "facebook", "github", "google",
    "instagram", "linkedin", "microsoft", "pinterest", "reddit",
    "slack", "snapchat", "spotify", "tiktok", "twitch", "twitter",
    "youtube",
}
JS_SOURCE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".gjs", ".gts", ".mjs", ".cjs"}
EMBEDDED_STYLE_EXTENSIONS = {".vue", ".svelte", ".astro"}
JSON_EXTENSIONS = {".json", ".jsonc"}
JS_OBJECT_START = re.compile(
    r"^\s*(?:(?:export\s+)?(?:const|let|var)\s+)?['\"]?([a-zA-Z0-9_-]+)['\"]?\s*(?::|=)\s*\{\s*,?\s*$"
)
JS_LITERAL = re.compile(
    r"^\s*['\"]?([a-zA-Z0-9_-]+)['\"]?\s*:\s*("
    r"(?:['\"`])[^'\"`\n]+(?:['\"`])|"
    r"-?[0-9.]+(?:px|rem|em|ms|s|%|vh|vw|deg)?|"
    r"\[[^\]\n]+\])\s*,?\s*$"
)
JS_DESIGN_VALUE = re.compile(
    r"(?:#[0-9a-f]{3,8}\b|(?:rgb|hsl|oklch|lab|color|var|calc|min|max|clamp|"
    r"cubic-bezier)\(|-?(?:\d*\.)?\d+(?:px|rem|em|ms|s|%|vh|vw|vmin|vmax|"
    r"deg)\b|\b(?:sans-serif|serif|monospace)\b)",
    re.I,
)

FAMILY_NAMES = {
    "typography": ("font", "typography", "typeset", "text-size",
                   "line-height", "letter-spacing", "text-case",
                   "text-decoration", "paragraph-spacing"),
    "spacing": ("space", "spacing", "gap", "padding", "margin", "inset"),
    "sizing": ("size", "width", "height", "measure", "dimension"),
    "radius": ("radius", "rounded", "corner"),
    "border": ("border", "stroke", "outline", "divider"),
    "elevation": ("shadow", "elevation", "depth", "box-shadow"),
    "opacity": ("opacity", "alpha", "transparency"),
    "layer": ("z-index", "zindex", "layer", "layers", "stacking", "elevation-z"),
    "motion": ("motion", "duration", "easing", "delay", "transition",
               "animation", "spring"),
    "breakpoint": ("breakpoint", "screen", "viewport", "media"),
    "grid": ("grid", "column", "columns", "gutter", "container", "layout",
             "wrapper"),
    "focus": ("focus", "focus-ring", "outline-focus"),
    "target": ("target", "touch", "hit-area", "min-target"),
    "state": ("state", "state-layer", "interaction", "overlay"),
    "icon": ("icon", "iconography", "glyph"),
    "aspect": ("aspect", "ratio", "aspect-ratio"),
    "blur": ("blur", "backdrop", "frost"),
    "density": ("density", "compact", "comfortable"),
}
COLOR_NAMES = (
    "color", "colour", "palette", "fill", "bg", "background", "surface",
    "content", "primary", "secondary", "neutral",
)


def normalize(name):
    return name.lstrip("-$").replace("_", "-").lower()


def family_key(name):
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name.lstrip("-$"))
    return re.sub(r"[_.\s]+", "-", name).lower()


def has_signal(key, signal):
    return re.search(r"(?:^|-)%s(?:-|$)" % re.escape(signal), key) is not None


def family_for(name, value):
    key = family_key(name)
    # Specific structural concepts take precedence over a value's syntax.
    for family in ("focus", "target", "aspect", "blur", "density", "state", "layer",
                   "motion", "breakpoint", "grid", "radius", "border",
                   "elevation"):
        if any(has_signal(key, signal) for signal in FAMILY_NAMES[family]):
            return family
    if (COLOR_VALUE.search(value) or
            any(has_signal(key, signal) for signal in COLOR_NAMES)):
        return "color"
    if any(has_signal(key, signal) for signal in FAMILY_NAMES["icon"]):
        return "icon"
    if (any(has_signal(key, signal) for signal in FAMILY_NAMES["typography"]) or
            key == "type" or key.startswith("type-")):
        return "typography"
    for family in ("spacing", "sizing", "opacity"):
        if any(has_signal(key, signal) for signal in FAMILY_NAMES[family]):
            return family
    return "unclassified"


def concrete_font_family(value):
    value = str(value).strip()
    if not value or "var(" in value or "#{" in value:
        return None
    generic = {
        "serif", "sans-serif", "monospace", "cursive", "fantasy",
        "system-ui", "ui-serif", "ui-sans-serif", "ui-monospace",
        "inherit", "initial", "unset",
    }
    first = re.match(
        r"\s*(?:\"((?:[^\"\\]|\\.)+)\"|'((?:[^'\\]|\\.)+)'|([^,]+))",
        value,
    )
    if not first:
        return None
    candidate = next((item for item in first.groups() if item is not None), "").strip()
    if (candidate.lower() in generic or
            not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9 _-]*", candidate)):
        return None
    return candidate


def concrete_color_value(value):
    """Return a self-contained color, never an unresolved color expression."""
    value = str(value).strip()
    if not CONCRETE_COLOR.fullmatch(value):
        return None
    if re.search(
            r"(?:\b(?:var|env|calc|min|max|clamp)\s*\(|#\{|\$[a-z_-]|"
            r"\b(?:rgba?|hsla?|oklch|lab|color)\s*\(\s*from\b)",
            value, re.I):
        return None
    if value.startswith("#"):
        return value
    function = re.fullmatch(r"([a-z]+)\((.*)\)", value, re.I)
    if not function:
        return None
    name, body = function.group(1).lower(), function.group(2).strip()
    if name == "color":
        profile = re.match(r"([a-z0-9-]+)\s+", body, re.I)
        allowed_profiles = {
            "srgb", "srgb-linear", "display-p3", "a98-rgb",
            "prophoto-rgb", "rec2020", "xyz", "xyz-d50", "xyz-d65",
        }
        if not profile or profile.group(1).lower() not in allowed_profiles:
            return None
        body = body[profile.end():]
    number = r"[+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?"

    def channel(token, units):
        match = re.fullmatch("(%s)([a-z%%]*)" % number, token, re.I)
        return bool(match and match.group(2).lower() in units)

    if "," in body:
        if name not in {"rgb", "rgba", "hsl", "hsla"} or "/" in body:
            return None
        parts = [part.strip() for part in body.split(",")]
        required = {"rgba": 4, "hsla": 4}.get(name)
        if (any(not part for part in parts) or
                (required and len(parts) != required) or
                (not required and len(parts) not in {3, 4})):
            return None
        color_channels, alpha = parts[:3], parts[3:]
    else:
        slash_parts = body.split("/")
        if len(slash_parts) > 2:
            return None
        color_channels = slash_parts[0].split()
        alpha = slash_parts[1].split() if len(slash_parts) == 2 else []
        if len(color_channels) != 3 or len(alpha) > 1:
            return None
    if name in {"rgb", "rgba", "color"}:
        valid_channels = all(channel(item, {"", "%"}) for item in color_channels)
    elif name in {"hsl", "hsla"}:
        valid_channels = (
            channel(color_channels[0], {"", "deg", "grad", "rad", "turn"}) and
            all(channel(item, {"%"}) for item in color_channels[1:])
        )
    elif name == "oklch":
        valid_channels = (
            channel(color_channels[0], {"", "%"}) and
            channel(color_channels[1], {""}) and
            channel(color_channels[2], {"", "deg", "grad", "rad", "turn"})
        )
    else:  # lab
        valid_channels = (
            channel(color_channels[0], {"", "%"}) and
            all(channel(item, {"", "%"}) for item in color_channels[1:])
        )
    if (not valid_channels or
            any(not channel(item, {"", "%"}) for item in alpha)):
        return None
    return value


def resolve_font_asset(root, style_path, url):
    if not url or re.match(r"^(?:data:|https?:|//)", url, re.I):
        return None
    clean_url = re.split(r"[?#]", url, maxsplit=1)[0]
    candidates = []
    if clean_url.startswith("/"):
        relative = clean_url.lstrip("/")
        candidates.append(relative)
        parts = relative.split("/")
        if len(parts) >= 3 and parts[0] == "plugins":
            plugin = parts[1]
            tail = os.path.join(*parts[2:])
            candidates.extend([
                os.path.join("plugins", plugin, "public", tail),
                os.path.join("plugins", plugin, "assets", tail),
            ])
        candidates.append(os.path.join("public", relative))
    else:
        candidates.extend([
            os.path.normpath(os.path.join(os.path.dirname(style_path), clean_url)),
            os.path.normpath(os.path.join("public", clean_url)),
        ])
    real_root = os.path.realpath(root)
    for candidate in candidates:
        full = os.path.realpath(os.path.join(root, candidate))
        if (os.path.commonpath([real_root, full]) == real_root
                and os.path.isfile(full)):
            return os.path.relpath(full, real_root)
    return None


def verified_font_file(path, font_format):
    if font_format not in FONT_MAGIC:
        return False
    size = os.path.getsize(path)
    if not size or size > MAX_EMBEDDED_FONT_BYTES:
        return False
    with open(path, "rb") as handle:
        magic = handle.read(4)
    return magic in FONT_MAGIC[font_format]


def font_face_evidence(root, path, text):
    faces = []
    clean = strip_comments_preserving_lines(text)
    for match in FONT_FACE.finditer(clean):
        block = match.group(1)
        family_match = FONT_FACE_FAMILY.search(block)
        url_match = FONT_FACE_URL.search(block)
        if not family_match or not url_match:
            continue
        family = concrete_font_family(family_match.group(1))
        if not family:
            continue
        url = url_match.group(2).strip()
        asset_path = resolve_font_asset(root, path, url)
        font_format = os.path.splitext(url.split("?", 1)[0])[1].lstrip(".").lower()
        asset = {
            "state": "blocked",
            "family": family,
            "declaration": "%s:%d" % (path, line_for(clean, match.start())),
            "url": url,
            "path": asset_path,
            "format": font_format,
            "sha256": None,
            "size_bytes": None,
        }
        if asset_path and verified_font_file(
                os.path.join(root, asset_path), font_format):
            full = os.path.join(root, asset_path)
            digest = hashlib.sha256()
            with open(full, "rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
            asset.update({
                "state": "verified",
                "sha256": digest.hexdigest(),
                "size_bytes": os.path.getsize(full),
            })
        elif asset_path:
            asset["reason"] = "unsupported, oversized, or invalid font asset"
        faces.append(asset)
    return faces


def matching_font_asset_evidence(root, family, expected):
    """Re-read the declaring stylesheet and reproduce one exact font binding."""
    if (not isinstance(expected, dict) or expected.get("state") != "verified" or
            str(expected.get("family", "")).lower() != str(family).lower()):
        return None
    declaration = expected.get("declaration")
    if not declaration or ":" not in declaration:
        return None
    style_path, line = declaration.rsplit(":", 1)
    if not line.isdigit():
        return None
    real_root = os.path.realpath(root)
    full = os.path.realpath(os.path.join(real_root, style_path))
    try:
        contained = os.path.commonpath([real_root, full]) == real_root
    except ValueError:
        contained = False
    if not contained or not os.path.isfile(full):
        return None
    with open(full, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    fields = (
        "state", "family", "declaration", "url", "path", "format",
        "sha256", "size_bytes",
    )
    for actual in font_face_evidence(root, style_path, text):
        if all(actual.get(field) == expected.get(field) for field in fields):
            return actual
    return None


def identity_context(text, offset):
    """Return the nearest explicit brand/identity section heading, if any."""
    lines = text[:offset].splitlines()
    lower_bound = max(0, len(lines) - 80)
    index = len(lines) - 1
    while index >= lower_bound:
        stripped = lines[index].strip()
        if not stripped:
            index -= 1
            continue
        if stripped.endswith("*/") or stripped.startswith("*"):
            comment_lines = []
            while index >= lower_bound:
                part = lines[index].strip()
                comment_lines.append(part)
                if "/*" in part:
                    break
                index -= 1
            if index < lower_bound or "/*" not in lines[index]:
                return None
            label = " ".join(reversed(comment_lines))
            label = re.sub(r"^/\*+\s*", "", label)
            label = re.sub(r"\s*\*/$", "", label)
            label = re.sub(r"\s*\*\s*", " ", label).strip(" -")
            if BRAND_CONTEXT.search(label):
                return {"kind": "brand", "label": label, "line": index + 1}
            return None
        if stripped.startswith(("//", "#")):
            label = re.sub(r"^(?://+|/\*+|\*+|#+)\s*", "", stripped)
            label = re.sub(r"\s*\*/\s*$", "", label).strip(" -")
            if not label:
                index -= 1
                continue
            if BRAND_CONTEXT.search(label):
                return {
                    "kind": "brand",
                    "label": label,
                    "line": index + 1,
                }
            return None
        index -= 1
    return None


def product_brand_context(name, context, subject_names=None):
    """Reject generic sections that often hold third-party service colors."""
    subject_words = {
        word for subject in (subject_names or set())
        for word in family_key(subject).split("-")
    }
    label = str(context.get("label", ""))
    if re.search(r"\b(?:design system|visual[ -]identity)\b", label, re.I):
        return True
    before_brand = re.split(r"\bbrand\b", label, maxsplit=1, flags=re.I)[0]
    prefix_words = re.findall(r"[a-z0-9]+", before_brand.lower())
    generic = {"the", "our", "product", "application", "app", "site"}
    prefix_words = [word for word in prefix_words if word not in generic]
    key_segments = family_key(name).split("-")
    return bool(
        prefix_words and
        any(word in key_segments for word in prefix_words) and
        any(word in subject_words for word in prefix_words)
    )


def subject_namespace_evidence(root, discovery=None):
    """Infer audited-product namespaces from repository/package evidence."""
    evidence = {}
    strong_namespaces = set()

    def add(value, source, strong=False):
        value = family_key(value).strip("-")
        if not value:
            return
        evidence.setdefault(value, []).append(source)
        if strong:
            strong_namespaces.add(value)
        shortened = re.sub(r"(?:-?(?:hq|inc|labs|org))$", "", value)
        if shortened and shortened != value:
            evidence.setdefault(shortened, []).append(
                "%s (normalized from %s)" % (source, value))
            if strong:
                strong_namespaces.add(shortened)

    add(os.path.basename(os.path.abspath(root)), "repository directory")
    try:
        result = subprocess.run(
            ["git", "-C", root, "config", "--get", "remote.origin.url"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            universal_newlines=True, timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    remote = result.stdout.strip() if result and result.returncode == 0 else ""
    if remote:
        match = re.search(r"(?:[:/])([^/:]+)/([^/]+?)(?:\.git)?$", remote)
        if match:
            add(match.group(1), "git remote owner: %s" % remote, strong=True)
            add(match.group(2), "git remote repository: %s" % remote)
    package_path = os.path.join(root, "package.json")
    try:
        with open(package_path, encoding="utf-8") as handle:
            package_name = json.load(handle).get("name")
    except (OSError, ValueError, AttributeError):
        package_name = None
    if package_name:
        package_text = str(package_name).lower()
        if package_text.startswith("@") and "/" in package_text:
            package_namespace = package_text[1:].split("/", 1)[0]
            package_namespace_strong = True
        else:
            package_namespace = package_text
            package_namespace_strong = False
        add(
            package_namespace, "root package.json namespace: %s" % package_name,
            strong=package_namespace_strong)
    plugins_path = os.path.join(root, "plugins")
    try:
        plugin_names = [
            name for name in os.listdir(plugins_path)
            if os.path.isdir(os.path.join(plugins_path, name))
        ]
    except OSError:
        plugin_names = []
    prefixes = Counter(
        family_key(name).split("-")[0] for name in plugin_names if "-" in name)
    for prefix, count in prefixes.items():
        if count >= 3 and prefix not in THIRD_PARTY_BRAND_NAMES:
            add(prefix, "%d top-level plugin directories use this prefix" % count)
    return [
        {"namespace": name, "evidence": list(dict.fromkeys(sources))}
        for name, sources in sorted(evidence.items())
        if name not in THIRD_PARTY_BRAND_NAMES or name in strong_namespaces
    ]


def identity_summary(concepts, font_faces=None, subject_namespaces=None):
    """Resolve identity-critical typography and brand colors conservatively."""
    font_candidates = []
    font_priority = {
        "font-family": 100,
        "base-font-family": 90,
        "body-font-family": 90,
        "heading-font-family": 80,
    }
    for concept in concepts:
        name = concept.get("id", "")
        if "font-family" not in name:
            continue
        definitions = concept.get("definitions") or []
        for definition in definitions:
            if not all(definition.get(field) for field in (
                    "value", "site", "representation")):
                continue
            value = definition.get("value")
            family = concrete_font_family(value)
            if family:
                font_candidates.append({
                    "family": family,
                    "token": name,
                    "priority": font_priority.get(name, 60),
                    "evidence": [definition.get("site")],
                })
    merged_candidates = {}
    for item in font_candidates:
        key = (item["family"], item["token"], item["priority"])
        merged = merged_candidates.setdefault(key, dict(item, evidence=[]))
        merged["evidence"].extend(
            evidence for evidence in item["evidence"] if evidence)
    font_candidates = list(merged_candidates.values())
    for item in font_candidates:
        item["evidence"] = list(dict.fromkeys(item["evidence"]))
    font_candidates.sort(key=lambda item: (-item["priority"], item["token"]))
    typography = {
        "state": "blocked",
        "family": None,
        "token": None,
        "confidence": "unresolved",
        "evidence": [],
        "candidates": font_candidates,
        "specimen": {
            "state": "blocked", "asset": None,
            "note": "No verified font asset was found for a self-contained specimen.",
        },
        "note": "No concrete reachable font-family token was confirmed.",
    }
    if font_candidates:
        highest = font_candidates[0]["priority"]
        strongest = [item for item in font_candidates
                     if item["priority"] == highest]
        families = {item["family"] for item in strongest}
        if len(families) == 1:
            selected = strongest[0]
            typography.update({
                "state": "verified",
                "family": selected["family"],
                "token": selected["token"],
                "confidence": "explicit-family-token",
                "evidence": selected["evidence"],
                "note": "Selected from the strongest concrete font-family token.",
            })
            matching_faces = [
                item for item in (font_faces or [])
                if (item.get("family", "").lower() ==
                    selected["family"].lower() and item.get("state") == "verified")
            ]
            unique_assets = {
                item.get("sha256"): item for item in matching_faces
                if item.get("sha256")
            }
            if len(unique_assets) == 1:
                typography["specimen"] = {
                    "state": "verified",
                    "asset": next(iter(unique_assets.values())),
                    "note": "The repository font asset can be embedded in the report.",
                }
            elif len(unique_assets) > 1:
                typography["specimen"]["note"] = (
                    "Multiple different font assets declare the selected family."
                )
        else:
            typography["note"] = (
                "Conflicting font families share the strongest semantic priority."
            )

    subject_namespaces = subject_namespaces or []
    subject_names = {
        item.get("namespace") for item in subject_namespaces
        if isinstance(item, dict) and item.get("namespace")
    }
    subject_words = {
        word for subject in subject_names for word in family_key(subject).split("-")
    }
    generic_brand_prefixes = {
        "accent", "active", "app", "application", "base", "black", "blue",
        "brand", "color", "component", "content", "cool", "core", "dark",
        "danger", "data", "default", "design", "disabled", "error", "focus",
        "global", "gray", "green", "hover", "icon", "info", "inverse", "light",
        "logo", "muted", "orange",
        "pink", "primary", "product", "quarternary", "quaternary", "red",
        "secondary", "semantic", "site", "success", "surface", "system",
        "tertiary", "text", "theme", "ui", "viz", "visualization", "warm",
        "warning", "white", "yellow",
    }
    brand_colors = []
    brand_conflicts = []
    for concept in concepts:
        if concept.get("family") != "color":
            continue
        name = concept.get("id", "")
        explicit_name = has_signal(family_key(name), "brand")
        key_segments = family_key(name).split("-")
        foreign_namespace = {
            word for word in key_segments
            if (not word.isdigit() and word not in generic_brand_prefixes and
                word not in subject_words)
        }
        owned_explicit_name = explicit_name and not foreign_namespace
        service_names = (
            set(key_segments) & THIRD_PARTY_BRAND_NAMES)
        service_named = bool(service_names - subject_names)
        if service_named or foreign_namespace:
            continue
        definitions = concept.get("definitions") or []
        qualified = []
        for definition in definitions:
            if not all(definition.get(field) for field in (
                    "value", "site", "representation")):
                continue
            value = concrete_color_value(definition.get("value"))
            context = definition.get("identity_context")
            contexts = [context] if (
                isinstance(context, dict) and
                context.get("kind") == "brand" and
                product_brand_context(name, context, subject_names)
            ) else []
            if value and (owned_explicit_name or contexts):
                qualified.append({
                    "value": value,
                    "site": definition.get("site"),
                    "contexts": contexts,
                })
        if not qualified:
            continue
        values = list(dict.fromkeys(item["value"] for item in qualified))
        if len(values) > 1:
            brand_conflicts.append({
                "token": name,
                "values": values,
                "evidence": list(dict.fromkeys(
                    item["site"] for item in qualified if item.get("site")
                )),
                "reason": "multiple concrete values lack explicit mode provenance",
            })
            continue
        value = values[0]
        selected = [item for item in qualified if item["value"] == value]
        contexts = [
            context for item in selected for context in item["contexts"]
        ]
        confidence = (
            "explicit-brand-name-and-source-section"
            if owned_explicit_name and contexts else
            "explicit-brand-token-name"
            if owned_explicit_name else
            "explicit-brand-source-section"
        )
        evidence = [item["site"] for item in selected if item.get("site")]
        evidence.extend(
            "%s:%s — %s" % (
                item.get("path"), item.get("line"), item.get("label"))
            for item in contexts
        )
        brand_colors.append({
            "token": name,
            "value": value,
            "confidence": confidence,
            "evidence": list(dict.fromkeys(evidence)),
        })
    brand_colors.sort(key=lambda item: (
        0 if has_signal(family_key(item["token"]), "brand") else 1,
        item["token"],
    ))
    brand = {
        "state": "verified" if brand_colors else "blocked",
        "confidence": "explicit-brand-semantics" if brand_colors else "unresolved",
        "colors": brand_colors,
        "conflicts": brand_conflicts,
        "subject_namespaces": subject_namespaces,
        "note": (
            "Only tokens with explicit brand semantics and unambiguous concrete values are included."
            if brand_colors else
            "No concrete reachable color carried an explicit brand token name or brand/visual-identity source heading; no palette was inferred."
        ),
    }
    return {"typography": typography, "brand_colors": brand}


def map_declarations(text):
    found = []
    lines = text.splitlines(True)
    offsets = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    index = 0
    while index < len(lines):
        start = MAP_START.match(lines[index].rstrip("\n"))
        if not start:
            index += 1
            continue
        map_name = start.group(1)
        stack = []
        index += 1
        while index < len(lines):
            stripped = lines[index].strip()
            if stripped.startswith(");"):
                break
            branch = MAP_BRANCH.match(lines[index].rstrip("\n"))
            if branch:
                stack.append(branch.group(1))
            elif stripped.startswith("),") or stripped == ")":
                if stack:
                    stack.pop()
            else:
                leaf = MAP_LEAF.match(lines[index].rstrip("\n"))
                if leaf:
                    name = "$" + ".".join([map_name] + stack + [leaf.group(1)])
                    found.append((name, leaf.group(2).strip(), "scss-map-entry", offsets[index]))
            index += 1
        index += 1
    return found


def style_declarations(text):
    clean = strip_comments_preserving_lines(text)
    return css_declarations(clean) + [
        (m.group(1), m.group(2).strip(), "scss-variable", m.start(1))
        for m in SCSS_DECL.finditer(clean)
    ] + map_declarations(clean)


def css_declarations(text):
    """Read custom-property values through balanced multiline functions."""
    found = []
    for match in CSS_DECL_START.finditer(text):
        index = match.end()
        start = index
        quote = None
        escaped = False
        parens = 0
        brackets = 0
        interpolation = 0
        while index < len(text):
            char = text[index]
            pair = text[index:index + 2]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
            elif char in ("'", '"'):
                quote = char
            elif pair == "#{":
                interpolation += 1
                index += 1
            elif char == "}" and interpolation:
                interpolation -= 1
            elif char == "(":
                parens += 1
            elif char == ")" and parens:
                parens -= 1
            elif char == "[":
                brackets += 1
            elif char == "]" and brackets:
                brackets -= 1
            elif char == ";" and not (parens or brackets or interpolation):
                break
            elif char == "}" and not (parens or brackets or interpolation):
                break
            index += 1
        value = text[start:index].strip()
        if value:
            found.append((match.group(1), value, "css-custom-property",
                          match.start(1)))
    return found


def json_declarations(text):
    try:
        data = json.loads(strip_comments_preserving_lines(text))
    except ValueError:
        return []
    found = []

    def walk(value, path):
        if not isinstance(value, dict):
            return
        representation = None
        raw = None
        if "$value" in value:
            representation = "dtcg-json"
            raw = value["$value"]
        elif "value" in value and ("type" in value or path):
            representation = "style-dictionary-json"
            raw = value["value"]
        if representation and path:
            name = ".".join(path)
            needle = json.dumps(path[-1])
            offset = max(0, text.find(needle))
            found.append((name, json.dumps(raw, sort_keys=True), representation, offset))
            return
        for key, child in value.items():
            if not str(key).startswith("$"):
                walk(child, path + [str(key)])

    walk(data, [])
    return found


def js_declarations(text, source_name=False):
    clean = strip_comments_preserving_lines(text)
    if not source_name and not re.search(r"\b(?:createTheme|defineTheme|tokens|designTokens)\b", clean):
        return []
    found = []
    stack = []
    offset = 0
    for line in clean.splitlines(True):
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        while stack and indent <= stack[-1][0] and stripped.startswith(("}", "];")):
            stack.pop()
        start = JS_OBJECT_START.match(line)
        if start:
            while stack and indent <= stack[-1][0]:
                stack.pop()
            stack.append((indent, start.group(1)))
            offset += len(line)
            continue
        literal = JS_LITERAL.match(line)
        if literal:
            while stack and indent <= stack[-1][0]:
                stack.pop()
            name = ".".join([item[1] for item in stack] + [literal.group(1)])
            found.append((name, literal.group(2).strip("'\"`"),
                          "js-theme-object", offset + literal.start()))
        offset += len(line)
    # A family-flavoured filename can still be ordinary application code (for
    # example, markdown typographer replacement tables). Keep only entries
    # whose path or value carries design-token evidence.
    return [
        item for item in found
        if family_for(item[0], item[1]) != "unclassified" or
        JS_DESIGN_VALUE.search(item[1])
    ]


def declarations(text, path=""):
    extension = os.path.splitext(path)[1].lower()
    if extension in JSON_EXTENSIONS:
        return json_declarations(text)
    if extension in JS_SOURCE_EXTENSIONS:
        return js_declarations(text, bool(SOURCE_NAME.search(os.path.basename(path))))
    if extension in EMBEDDED_STYLE_EXTENSIONS or extension in (".css", ".scss", ".sass", ".less"):
        return style_declarations(text)
    return []


def line_for(text, offset):
    return text.count("\n", 0, offset) + 1


def root_css_declaration_count(text):
    """Count custom properties inside balanced :root blocks, including nesting."""
    text = strip_comments_preserving_lines(text)
    total = 0
    for match in ROOT_START.finditer(text):
        start = match.end()
        depth = 1
        index = start
        quote = None
        escaped = False
        while index < len(text) and depth:
            character = text[index]
            if quote:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
            elif character in {'"', "'"}:
                quote = character
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
            index += 1
        total += len(CSS_DECL_START.findall(text[start:index - 1]))
    return total


def source_role(path, decls, text, forced=False):
    if forced:
        return "canonical"
    if not decls:
        return "consumer"
    local = any(part in path for part in ("/components/", "/component/"))
    if local and len(decls) < 20:
        return "consumer-override"
    representations = {representation for _, _, representation, _ in decls}
    css_count = sum(1 for _, _, representation, _ in decls
                    if representation == "css-custom-property")
    root_css_count = root_css_declaration_count(text)
    if representations & {"dtcg-json", "style-dictionary-json", "js-theme-object"}:
        return "canonical" if SOURCE_NAME.search(os.path.basename(path)) else "candidate"
    source_shaped_styles = (
        len(decls) >= 2 and
        bool(representations & {"scss-variable", "scss-map-entry"})
    )
    source_shaped_css = css_count >= 5 and ":root" in text
    if ((SOURCE_NAME.search(os.path.basename(path)) and
         (source_shaped_styles or root_css_count > 0)) or
            source_shaped_css):
        values = [value for _, value, _, _ in decls]
        if values and all("var(" in value or re.search(r"\$[\w-]+", value) for value in values):
            return "alias"
        return "canonical"
    return "candidate"


def discover(root, discovery, forced_sources=None):
    root = os.path.abspath(root)
    forced_sources = set(forced_sources or [])
    reachable = discovery.get("owned_import_graph", {}).get("reachable", {})
    concepts = {}
    sources = []
    local_overrides = []
    font_faces = []
    for path, reach in sorted(reachable.items()):
        if os.path.splitext(path)[1].lower() not in (
                {".css", ".scss", ".sass", ".less"} |
                JS_SOURCE_EXTENSIONS | EMBEDDED_STYLE_EXTENSIONS | JSON_EXTENSIONS):
            continue
        full = os.path.join(root, path)
        try:
            with open(full, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        if os.path.splitext(path)[1].lower() in (
                {".css", ".scss", ".sass", ".less"} | EMBEDDED_STYLE_EXTENSIONS):
            font_faces.extend(font_face_evidence(root, path, text))
        decls = declarations(text, path)
        role = source_role(path, decls, text, path in forced_sources)
        if not decls:
            continue
        source = {
            "path": path, "role": role, "declarations": len(decls),
            "reachable_from": reach.get("via") or [path],
            "confidence": "import-graph verified",
        }
        sources.append(source)
        if role in ("consumer-override", "candidate"):
            local_overrides.append(source)
            continue
        for name, value, representation, offset in decls:
            key = normalize(name)
            detected_family = family_for(name, value)
            item = concepts.setdefault(key, {
                "id": key, "family": detected_family, "sites": [],
                "representations": [], "values": [], "alias_of": None,
                "identity_contexts": [],
                "definitions": [],
            })
            if item["family"] == "unclassified" and detected_family != "unclassified":
                item["family"] = detected_family
            item["sites"].append("%s:%d" % (path, line_for(text, offset)))
            context = identity_context(text, offset)
            if context:
                context = dict(context, path=path)
            definition = {
                "value": value,
                "site": "%s:%d" % (path, line_for(text, offset)),
                "representation": representation,
                "offset": offset,
                "identity_context": context,
            }
            if definition not in item["definitions"]:
                item["definitions"].append(definition)
            if context:
                if context not in item["identity_contexts"]:
                    item["identity_contexts"].append(context)
            if representation not in item["representations"]:
                item["representations"].append(representation)
            if value not in item["values"]:
                item["values"].append(value)
            ref = re.search(r"var\(\s*--([\w-]+)\s*\)|\$([\w-]+)", value)
            if ref:
                item["alias_of"] = normalize(ref.group(1) or ref.group(2))
    family_counts = {family: 0 for family in FAMILIES}
    unclassified = 0
    for item in concepts.values():
        if item["family"] in family_counts:
            family_counts[item["family"]] += 1
        else:
            unclassified += 1
    sorted_concepts = sorted(concepts.values(), key=lambda item: item["id"])
    subject_namespaces = subject_namespace_evidence(root, discovery)
    return {
        "sources": sources,
        "concepts": sorted_concepts,
        "concept_count": len(concepts),
        "family_counts": family_counts,
        "unclassified": unclassified,
        "candidate_or_local_override_sources": local_overrides,
        "forced_sources": sorted(forced_sources),
        "identity": identity_summary(
            sorted_concepts, font_faces, subject_namespaces),
        "measurement": [
            {"syntax": "css-custom-property", "state": "measured"},
            {"syntax": "scss-variable-and-map", "state": "measured"},
            {"syntax": "dtcg-and-style-dictionary-json", "state": "measured"},
            {"syntax": "conservative-js-theme-object", "state": "measured"},
            {"syntax": "runtime-generated-theme-values", "state": "unmeasured"},
        ],
    }


def update_discovery(path, result):
    with open(path, encoding="utf-8") as handle:
        discovery = json.load(handle)
    confirmed = [item for item in result.get("sources", [])
                 if item.get("role") in ("canonical", "alias")]
    capabilities = discovery.setdefault("capabilities", {})
    roots_complete = capabilities.get("production_roots") == "verified"
    imports_complete = capabilities.get("import_resolution") == "verified"
    state = (
        "verified" if confirmed and roots_complete and imports_complete else
        "blocked"
    )
    capabilities["token_source_discovery"] = state
    ladder = discovery.get("capability_ladder", {})
    for step in ladder.get("steps", []):
        if step.get("capability") == "token_source_discovery":
            step["state"] = state
            step["evidence"] = [item["path"] for item in confirmed[:8]]
            step["limitation"] = (
                None if state == "verified" else
                ("Reachable token sources were found, but production-root or import-graph evidence is incomplete."
                 if confirmed else
                 "No reachable canonical token source was confirmed.")
            )
            step["next_step"] = (
                "Deduplicate projections and classify every foundational family."
                if state == "verified" else
                "Confirm a reachable token source or provide --source evidence."
            )
            break
    directory = os.path.dirname(os.path.abspath(path))
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False,
                                     encoding="utf-8") as handle:
        json.dump(discovery, handle, indent=2, sort_keys=False)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, path)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("root")
    parser.add_argument("--discovery", required=True)
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--update-discovery", action="store_true")
    add_json_flag(parser)
    args = parser.parse_args(argv)
    with open(args.discovery, encoding="utf-8") as handle:
        discovery = json.load(handle)
    result = discover(args.root, discovery, args.source)
    emit_json(args.json_out, result)
    if args.update_discovery:
        update_discovery(args.discovery, result)
    print("discovered %d canonical concepts across %d reachable sources; %d candidate/override source(s) held out" % (
        result["concept_count"], len(result["sources"]),
        len(result["candidate_or_local_override_sources"])))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
