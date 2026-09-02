# Environment adapters

Profiles change how evidence is found, never what an audit may claim.
Every adapter records the same evidence ledger and uses the same confidence
labels: `framework-registered`, `import-graph verified`, `static candidate`,
`runtime verified`, or `blocked`.

## Executable profile contract

`assets/framework-profiles.json` is the executable registry. Profiles are
composable: a run can activate a product framework, asset pipeline, build
tool, Storybook surface, and monorepo structure together. Deterministic
priority controls contribution order, not winner selection.

Each profile declares detection signals, product-root hints, evidenced
component roots, supplemental route/template/demo surfaces, and guidance for
the capabilities below. `tools/framework_profiles.py` validates the schema,
retains partial matches as candidates, and accepts extensions through
`--profile-file`. A profile selected with `--profile` is labelled
user-selected; it does not gain evidence the repository did not provide.

Profiles may also declare `extractors`. These are small, reusable discovery
operations—not framework names hidden in engine code:

| Type | Purpose | Required fields |
|---|---|---|
| `regex_roots` | Read registration calls or other literal config syntax with a named `spec` group | `files`, `regex`, `evidence`; optionally `line_comments`, `path_template`, `root_type_group`, `style_only` |
| `config_array_roots` | Read quoted style paths from a JavaScript/TypeScript config array | `files`, `key`, `evidence`; optionally `strip_prefixes`, `style_only` |
| `json_build_roots` | Read application entries and global style arrays from workspace build JSON | `files`, `evidence`; optionally `target_names` (defaults to `build`), `entry_keys`, `style_key` |

Every extractor also accepts `confidence`, `ownership`, `scope`, and
`root_type`. Paths that escape the application, remote URLs, and dynamic
expressions are rejected. Extracted paths still need to exist, and ownership
still obeys the run's explicit `--owned` boundary. Prefer one of these
generic extractors in a custom profile before adding framework-specific code.
Profiles may also contribute `load_paths` for framework-proven Sass search
roots, `import_rewrites` for virtual framework module names, and conservative
`capability_contributions`. Aliases, rewrites, and load paths are scoped to
the importing application so repeated embedded apps cannot overwrite one
another. Conflicting rewrite destinations block resolution instead of using
profile priority as a winner. Conflicting capability
states compose to the most conservative state and remain visible under
`profile_composition.conflicts`; priority never erases a blocker.
Every capability contribution needs explicit string evidence. Every named
placeholder in an import-rewrite replacement must exist as a named group in
that rewrite's regular expression; invalid profile contracts fail before an
audit begins.
Every built-in and custom profile registry input is recorded with an ordered
SHA-256 digest in report provenance so custom overrides cannot disappear from
comparisons.

Product roots enter reachability. Supplemental and demo surfaces guide the
investigation but cannot enter product reachability. Component roots enter
adoption analysis only with strong evidence and owned scope.
Static convention matches that cannot be reached remain in `root_candidates`.
Evidenced component directories outside owned scope remain in
`component_root_candidates`. The HTML must render both sets with the reason
they were not promoted.

## Adapter questions

An adapter must answer these questions with evidence:

1. **Detection:** Which framework, styling layers, and versions are present?
   Several can apply together.
2. **Production roots:** Which common, desktop, mobile, admin, theme,
   plugin, route, component, or lazy assets are registered to ship? A
   filename alone is a static candidate, never a proven root.
3. **Import resolution:** How do CSS, preprocessors, JS/TS, aliases,
   generated output, and dynamic imports resolve? Classify unresolved specs
   by reason rather than treating all of them as missing files.
4. **Token sources:** Where are primitives, semantic aliases, projections,
   and component overrides declared across CSS, preprocessors, JS/TS, JSON,
   and framework configuration?
5. **Ownership:** Which paths are authored, generated, vendor, upstream,
   test/demo, unknown, or exempt? Unknown ownership stays visible.
6. **Modes:** Which bundle × scheme pairs have resolved output? State the
   exact build artifact, URL, or runtime endpoint required when blocked.
7. **Runtime verification:** When a local build, preview, Storybook, or
   browser is available, compare computed values with static results. Label
   results static-only, build-verified, or runtime-verified.

Templates and routes can reveal conditional or lazy assets. They are never
standalone proof that an asset ships.

## Generic fallback

When no adapter matches, inspect manifests, lockfiles, build files, server
templates, HTML entry points, application boot files, route definitions, and
style-bearing source files. Produce ranked framework/root hypotheses with
evidence. Ask one narrow question only when competing production-root models
would materially change scope.

## Adding a profile and adapter

Add the executable profile to the built-in JSON registry or supply a registry
extension with `--profile-file`. Use a validated extractor when a framework
registers styles in config rather than imports. Give every contribution evidence and all six
post-detection guidance fields. Add a focused adapter reference only when the
JSON guidance cannot explain a framework's non-obvious mechanism. Do not
hard-code token filenames: reachability and classification still decide
which candidates are active sources.
