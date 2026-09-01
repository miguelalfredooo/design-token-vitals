#!/usr/bin/env python3
"""The report's own palette, checked against the standard it grades others on.

    python3 tools/palette.py [assets/report-template.html]

Reads every theme block in the template — the bare :root, the
prefers-color-scheme override, and the explicit data-theme override — and
checks each status foreground against its own tint and each ink against
the grounds it sits on. WCAG AA for text is 4.5:1. Exit status is 1 when
any pair falls below it.

A tool that grades codebases on their token discipline and ships a status
chip below the contrast floor has no standing. This keeps that from
happening quietly.
"""
import re
import sys

AA = 4.5

# foreground token -> the backgrounds it must be legible on
PAIRS = {
    "--pass": ["--pass-bg"],
    "--warn": ["--warn-bg"],
    "--fail": ["--fail-bg"],
    "--na": ["--na-bg"],
    "--block": ["--surface"],
    "--ink": ["--ground", "--surface"],
    "--ink-soft": ["--ground", "--surface"],
    "--ink-mute": ["--ground", "--surface"],
    "--accent": ["--ground", "--surface"],
}

HEX = re.compile(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})")
BLOCK = re.compile(r"(:root(?:[^{]*)\{)(.*?)\n  \}", re.S)


def luminance(hex6):
    r, g, b = [int(hex6[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def theme_blocks(html):
    """Every theme block as (label, {token: hex})."""
    out = []
    for head, body in BLOCK.findall(html):
        tokens = dict(HEX.findall(body))
        if tokens:
            out.append((head.strip().rstrip("{").strip(), tokens))
    return out


def check(html):
    """Every (theme, fg, bg, ratio) below AA, plus the full table."""
    table, failures = [], []
    for label, tokens in theme_blocks(html):
        for fg, bgs in PAIRS.items():
            if fg not in tokens:
                continue
            for bg in bgs:
                if bg not in tokens:
                    continue
                ratio = contrast(tokens[fg], tokens[bg])
                row = (label, fg, tokens[fg], bg, tokens[bg], ratio)
                table.append(row)
                if ratio < AA:
                    failures.append(row)
    return table, failures


def main(argv):
    path = argv[0] if argv else "assets/report-template.html"
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    table, failures = check(html)
    for label, fg, fh_, bg, bh, ratio in table:
        mark = "  ok " if ratio >= AA else " LOW "
        print("%s %-34s %-10s %s on %-10s %s  %.2f:1" % (mark, label[:34], fg, fh_, bg, bh, ratio))
    if failures:
        print("\n%d pair(s) below %.1f:1. The report grades others on this." % (len(failures), AA))
        return 1
    print("\npalette: every pair clears %.1f:1 in every theme" % AA)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
