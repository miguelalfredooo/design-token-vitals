# Worked example: shadcn-ui/ui

A real run of `design-token-vitals` against a public repository, so every
finding here is independently checkable.

- **Subject:** https://github.com/shadcn-ui/ui
- **Commit:** `63c1308` (`63c1308d112b6b1205d86244a156cca1abef5087`)
- **Run date:** 2026-09-01
- **Adapter detected:** `tailwind` + `css-vars` (dual — Tailwind v4's `@theme inline`
  block sits directly on top of a `:root` block with 41 custom properties,
  so both adapters ran and their findings were merged, as `references/adapters/tailwind.md`
  directs)
- **Rendering tier:** `full` (53 tokens, under the 150-token threshold)

## Scope

shadcn-ui/ui is a monorepo: the CLI (`packages/shadcn`), its docs-and-demo
site (`apps/v4`), and a set of framework fixtures and starter templates used
only to test the CLI's own project scaffolding
(`packages/shadcn/test/fixtures/**`, `templates/**`). This run graded
`apps/v4` — the real Next.js application, its `app/globals.css` token
layer, and the `registry/new-york-v4` component source that ships through
the CLI — and excluded the fixtures and templates as test scaffolding for
*other* people's projects, not this repository's own consuming code. File
counts below (for example "1,230 files") are `apps/v4` only.

## The eight vitals

| Vital | Grade | One line |
|---|---|---|
| Tier integrity | Attention | 26 of 1,230 files (2.1%) reach past the semantic layer for a raw Tailwind palette color where a token already covers the case. |
| Leakage | Attention | 2 exact-match redundant findings (both dimensions — no hardcoded hex or oklch color exists anywhere in the scanned surface), plus 3 uncovered dimension gaps. |
| Coverage | Attention | 9 of 11 categories resolve to a real token. z-index and opacity do not — Tailwind v4 has no `--z-*` or `--opacity-*` scale to reach for. |
| Mode completeness | Pass | Zero gaps across all 34 color-bearing tokens between `:root` and `.dark`. |
| Naming coherence | Pass | One grammar throughout: a kebab-case role name, optionally paired with `-foreground`. |
| Single source of truth | Attention | The default chart palette is declared independently in four places; all four currently agree. |
| Orphans | Pass | All ~53 declared tokens resolve to at least one real reference. |
| Enforcement | Blocked | No lint rule or CI gate in the repository reads the token layer. |

Full evidence — every `file:line`, every note explaining a `blocked` grade
or a judgment call — is in [`report.json`](./report.json) and rendered in
[`report.html`](./report.html).

## What this says, and what it does not

This describes commit `63c1308` and nothing else. shadcn-ui/ui is under
active development; a later commit can move any of these grades in either
direction. Nothing here is a statement about the project's overall quality
— it is eight specific, evidenced checks against one snapshot of one
directory tree.

A reader can re-run this and check every number:

```bash
git clone --filter=blob:none https://github.com/shadcn-ui/ui.git && cd ui && git checkout 63c1308
```

Then follow `SKILL.md` by hand against `apps/v4` in the cloned tree, the
same way this run did.
