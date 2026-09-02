# Discourse

## Detection

Treat Discourse as detected when `plugins/` appears beside
`app/assets/stylesheets/`, with supporting evidence such as `Gemfile`,
`register_asset`, `dark-light-choose()`, `schemeType()`, or theme SCSS.

## Production roots

Read core stylesheet roots and every owned plugin's `plugin.rb` asset
registrations, including `register_asset`, `register_css`, theme-component
assets, and client-side lazy or route imports. Record each root with
`file:line` registration evidence and type: common, desktop, mobile, admin,
theme, plugin, route, component, or lazy. Inspect conditional assets
separately; do not mark a stylesheet orphan only because its route is not
loaded by the common bundle.

Discourse injects `app/assets/stylesheets/common/foundation/variables.scss`
into every theme CSS file. Treat this as a framework-registered implicit
root even though no ordinary Sass import reaches it. Record the source
comment or framework implementation as the evidence for that edge.

## Imports and ownership

Resolve Sass partials, `@use`, `@forward`, and `@import`. Classify `sass:*`
modules as framework built-ins and remote font URLs as remote dependencies.
Determine plugin ownership from `.gitmodules`, plugin metadata, and git
history; keep upstream plugins out of owned consumer scope unless requested.

## Modes and runtime

Inspect `dark-light-choose()`, `$light-theme-*`, `$dark-theme-*`,
`schemeType()`, theme color definitions, and selectors that select schemes.
Source proves a mechanism, not parity. Grade mode completeness only after
reading compiled per-site output for every audited bundle × scheme pair;
otherwise record the missing output and grade `blocked`.
