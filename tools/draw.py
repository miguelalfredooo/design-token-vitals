#!/usr/bin/env python3
"""The marks the report draws instead of writing a number into a sentence.

A sentence may name a thing or state a conclusion. A number the page could
draw is drawn here: a share is a bar, a count out of a whole is a grid of
dots, a threshold is a tick on a track, a pair is two things side by side,
and something we couldn't see is hatched.

Every mark carries its figure as text beside it (`1,088 of 1,216 (89%)`) and
as an `aria-label`, so nothing is readable only by eye. The line of plain
words under a mark says what it means and never repeats the figure.

Inline styles here carry data and nothing else: a width, a color, a position.
Layout lives in the template's stylesheet.
"""
import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vocab import GRADE_LABEL, GRADES, fmt, of, pct  # noqa: E402

# A grid of dots stops being a drawing and becomes a texture somewhere past
# this many; the same figure is drawn as a bar instead.
MAX_DOTS = 1500


def esc(value):
    return html.escape(str(value), quote=True)


def _width(part, whole):
    if not whole:
        return 0.0
    return max(0.0, min(100.0, 100.0 * float(part) / float(whole)))


def figure(mark, figure_text=None, means=None, kind="bar"):
    """A mark, its figure in digits beside it, and one line saying what it means."""
    number = ('<span class="mk-num">%s</span>' % esc(figure_text)
              if figure_text else "")
    caption = ('<figcaption class="mk-means">%s</figcaption>' % means
               if means else "")
    return ('<figure class="mk" data-mark="%s"><div class="mk-row">%s%s</div>'
            '%s</figure>' % (esc(kind), mark, number, caption))


def bar(part, whole, noun=None, tone="ink"):
    """A share of a whole: `1,088 of 1,216 (89%)` as a filled track."""
    text = of(part, whole, noun)
    return ('<span class="mk-bar" data-tone="%s" role="img" aria-label="%s">'
            '<i style="width:%.3f%%"></i></span>'
            % (esc(tone), esc(text), _width(part, whole)))


def share(part, whole, label=None):
    """A small bar for a table cell, drawn against the same whole in every row."""
    text = label or pct(part, whole, 1)
    return ('<span class="mk-share" role="img" aria-label="%s">'
            '<i style="width:%.3f%%"></i></span>'
            '<span class="mk-share-num">%s</span>'
            % (esc(text), _width(part, whole), esc(text)))


def stack(segments, whole=None, label=None):
    """Parts that visibly add up to the whole.

    `segments` is a list of `(name, value, tone)`. A remainder is drawn when
    the parts stop short of `whole`, so the bar is always the whole thing.
    """
    total = float(whole if whole is not None else
                  sum(value for _name, value, _tone in segments))
    drawn = sum(value for _name, value, _tone in segments)
    cells = "".join(
        '<i data-tone="%s" style="width:%.3f%%" title="%s"></i>'
        % (esc(tone), _width(value, total), esc("%s: %s" % (name, fmt(value))))
        for name, value, tone in segments if value)
    if total > drawn:
        cells += ('<i data-tone="rest" style="width:%.3f%%"></i>'
                  % _width(total - drawn, total))
    text = label or " · ".join(
        "%s %s" % (fmt(value), name) for name, value, _tone in segments)
    return ('<span class="mk-stack" role="img" aria-label="%s">%s</span>'
            % (esc(text), cells))


def dots(part, whole, noun=None, mark="hollow"):
    """A count out of a whole, one dot each: the `part` drawn hollow or solid.

    The marked dots come first so they sit together where the eye lands.
    """
    part, whole = int(part), int(whole)
    if whole <= 0:
        return ""
    if whole > MAX_DOTS:
        return bar(part, whole, noun)
    columns = 54 if whole > 400 else 36 if whole > 120 else 24
    step, radius = 7, 2.4
    rows = -(-whole // columns)
    circles = []
    for index in range(whole):
        x = (index % columns) * step + step / 2.0
        y = (index // columns) * step + step / 2.0
        circles.append('<circle cx="%.1f" cy="%.1f" r="%.1f" class="%s"/>' % (
            x, y, radius, "mk-dot-mark" if index < part else "mk-dot-rest"))
    return ('<svg class="mk-dots" data-dots="%s" viewBox="0 0 %d %d" '
            'width="%d" height="%d" role="img" aria-label="%s">%s</svg>'
            % (esc(mark), columns * step, rows * step, columns * step,
               rows * step, esc(of(part, whole, noun)), "".join(circles)))


def cells(part, whole, noun=None, tone="pass"):
    """A handful of things, each one a cell: `11 of 11 categories`."""
    part, whole = int(part), int(whole)
    body = "".join('<i class="%s"></i>' % ("on" if index < part else "off")
                   for index in range(whole))
    return ('<span class="mk-cells" data-tone="%s" role="img" aria-label="%s">'
            '%s</span>' % (esc(tone), esc(of(part, whole, noun)), body))


def threshold(value, maximum, lines, unit="", noun=None):
    """Where a reading sits against the lines between the states.

    `lines` is a list of `{"at": number, "label": "Fix"}`. The marker is
    placed; the distance to a line is something the eye reads off the track.
    """
    maximum = float(maximum or 0) or 1.0
    ticks = "".join(
        '<i class="mk-tick" style="left:%.3f%%"><b>%s</b></i>'
        % (_width(line.get("at", 0), maximum),
           esc("%s %s%s" % (line.get("label", ""), _trim(line.get("at", 0)), unit)))
        for line in lines or [])
    reading = "%s%s" % (_trim(value), unit)
    label = "%s%s" % (reading, " %s" % noun if noun else "")
    marker = ('<i class="mk-marker" style="left:%.3f%%"></i>'
              % _width(value, maximum))
    return ('<span class="mk-threshold" role="img" aria-label="%s">'
            '<span class="mk-track">%s%s</span></span>'
            % (esc("%s. Lines: %s" % (label, ", ".join(
                "%s at %s%s" % (line.get("label", ""), _trim(line.get("at", 0)), unit)
                for line in lines or []))), ticks, marker))


def _trim(number):
    """`5`, `4.7`: a number without a trailing `.0`."""
    try:
        number = float(number)
    except (TypeError, ValueError):
        return str(number)
    return ("%d" % number) if number == int(number) else ("%.1f" % number)


def hatch(text="We couldn't see it"):
    """Where a value would be, when we couldn't see it. Hatched, never zero."""
    return '<span class="mk-hatch" role="img" aria-label="%s"><span>%s</span></span>' % (
        esc(text), esc(text))


def grade_dot(grade, title=None):
    """A state as a dot. The word is in the label; the page states it once elsewhere."""
    if grade not in GRADES:
        return ('<span class="mk-dot" data-g="none" role="img" '
                'aria-label="%s" title="%s"></span>'
                % (esc(title or "Not graded this way"),
                   esc(title or "Not graded this way")))
    text = title or GRADE_LABEL[grade]
    return ('<span class="mk-dot" data-g="%s" role="img" aria-label="%s" '
            'title="%s"></span>' % (esc(grade), esc(text), esc(text)))


def strip(states, link=True):
    """The eight checks as one row of cells: the only place a grade is stated.

    `states` is a list of `(name, label, grade)` in the fixed order.
    """
    cells_html = []
    for name, label, grade in states:
        inner = ('<span class="mk-strip-name">%s</span>'
                 '<span class="mk-strip-state">%s</span>'
                 % (esc(label), esc(GRADE_LABEL.get(grade, GRADE_LABEL["not-visible"]))))
        if link:
            cells_html.append(
                '<a class="mk-strip-cell" data-grade="%s" data-check="%s" '
                'href="#vital-%s">%s</a>' % (esc(grade), esc(name), esc(name), inner))
        else:
            cells_html.append(
                '<span class="mk-strip-cell" data-grade="%s" data-check="%s">%s</span>'
                % (esc(grade), esc(name), inner))
    return '<div class="mk-strip" role="list">%s</div>' % "".join(
        '<div role="listitem">%s</div>' % cell for cell in cells_html)


def swatch(value, label=None):
    """A color shown as the color."""
    return ('<span class="mk-swatch"><i style="background:%s" aria-hidden="true">'
            '</i><code>%s</code></span>' % (esc(value), esc(label or value)))


def declarations(items):
    """Two places that set the same thing, side by side, the loser struck through.

    `items` is a list of `{"location", "code", "wins": bool, "note"}`.
    """
    rows = []
    for item in items or []:
        wins = bool(item.get("wins"))
        code = esc(item.get("code") or "")
        rows.append(
            '<div class="mk-decl" data-wins="%s"><span class="path">%s</span>'
            '%s<span class="mk-decl-note">%s</span></div>'
            % ("true" if wins else "false", esc(item.get("location") or ""),
               ('<code>%s</code>' % code) if wins else ('<s><code>%s</code></s>' % code),
               esc(item.get("note") or ("this one wins" if wins else "never applies"))))
    return '<div class="mk-decls">%s</div>' % "".join(rows)


def ladder(stages, current):
    """Where a system stands on a short ordered scale."""
    index = stages.index(current) if current in stages else -1
    steps = "".join(
        '<li class="%s"><i></i><span>%s</span></li>'
        % ("now" if position == index else "done" if position < index else "",
           esc(stage))
        for position, stage in enumerate(stages))
    return ('<ol class="mk-ladder" aria-label="%s">%s</ol>'
            % (esc("Stage %d of %d: %s" % (index + 1, len(stages), current)
                   if index >= 0 else "Stage not settled"), steps))
