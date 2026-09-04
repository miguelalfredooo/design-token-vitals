# Voice

The copy standard for every report design-token-vitals generates. It keeps a
report written by three different mechanisms — static HTML, filled templates,
and generated prose — in one voice.

## Three kinds of copy

| Kind | Where | How the voice is guaranteed |
|---|---|---|
| Static chrome | Headings, ledes, tooltips, legend, panel titles | Ships in `assets/report-template.html`; identical every run |
| Slotted sentences | Vital cards, truncation lines, family rows | Slot templates below; fill the slots, never rewrite the sentence |
| Generated | A callout connecting two findings | The rules below, checked against the maintained report template |

## Rules

- Write in second person. Say what a finding means for the reader before stating the principle.
- On the dashboard, lead with the plain-language meaning and keep the audit term as secondary evidence. For example, show `Needs evidence` before `blocked`, and `Worth a look` before `attention`.
- Pair every concern with a concrete next action. A reader should never have to translate a status into what to do next.
- Use calm, specific labels that answer the reader's question: `You’re here`, `How the system is doing`, `What we could verify`, and `Start here`.
- Describe component planning as token footprint: `Where component token work has the widest footprint`, `Assess first`, `Plan next`, and `Focused follow-up`. State that this measures references inside code rather than runtime impressions or screen frequency.
- Be confident only where the evidence is confident. Name the verified type family, brand colors, framework profiles, and component counts; when proof is missing, name the missing evidence instead of showing generic sample content.
- Explain a term the first time it appears. Keep the real vocabulary: semantic token, primitive, mode, ramp, orphan.
- State the positive instead of denying an alternative.
- Say "hardcoded values" in prose. Use "literal" only as a table label for a code value.
- Nothing is anyone's fault. An uncovered value is a gap in the system, not a mistake by whoever wrote the component.
- US English. The full swap list lives in `tools/check_voice.py`.

## Banned

```
simply
utilize
utilise
leverage
in order to
seamlessly
effortlessly
robust
```

The first and seventh entries above tell the reader their difficulty is imaginary.

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

## Maintained reference

`assets/report-template.html` is the only maintained report and copy
reference. Generated prose should sound at home beside its static chrome.
