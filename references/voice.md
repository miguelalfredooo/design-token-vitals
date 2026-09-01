# Voice

The copy standard for every report design-token-vitals generates. It keeps a
report written by three different mechanisms — static HTML, filled templates,
and generated prose — in one voice.

## Three kinds of copy

| Kind | Where | How the voice is guaranteed |
|---|---|---|
| Static chrome | Headings, ledes, tooltips, legend, panel titles | Ships in `assets/report-template.html`; identical every run |
| Slotted sentences | Vital cards, truncation lines, family rows | Slot templates below; fill the slots, never rewrite the sentence |
| Generated | A callout connecting two findings | The rules below, plus `assets/reference/*.html` as worked examples |

## Rules

- Write in second person. Say what a finding means for the reader before stating the principle.
- Explain a term the first time it appears. Keep the real vocabulary: semantic token, primitive, mode, ramp, orphan.
- State the positive instead of denying an alternative.
- Say "hardcoded values" in prose. Use "literal" only as a table label for a code value.
- Nothing is anyone's fault. An uncovered value is a gap in the system, not a mistake by whoever wrote the component.
- US English. The full swap list lives in `tools/check_voice.py`.

## Banned

`s⁠imply`, `u⁠tilize`, `u⁠tilise`, `l⁠everage`, `in o⁠rder to`, `s⁠eamlessly`, `e⁠ffortlessly`, `r⁠obust`.

"S⁠imply" and "e⁠ffortlessly" tell the reader their difficulty is imaginary.

## Slot templates

The exact sentences, verbatim, that the skill fills. Sentence slots are
placeholders inside a fixed sentence — never a region of the page layout;
that meaning belongs to `assets/report-template.html`.

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

## Worked examples

`assets/reference/small.html` and `assets/reference/large.html` are worked
examples of a finished report. A few dozen real sentences constrain tone
better than a paragraph of description.
