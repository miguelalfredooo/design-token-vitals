# DTCG (Design Tokens Community Group)

The adapter for a token layer authored as W3C-format JSON and compiled by a
build pipeline before anything ships.

## Where tokens live

Look for JSON files carrying `$value` and `$type` keys, typically under a
`tokens/` directory, built by Style Dictionary or a comparable pipeline into
the formats your components actually import.

## Detection

A JSON file containing `$value` tells you this is the adapter. A
`config.json` or `sd.config.*` naming Style Dictionary confirms the build
step that turns those files into output.

## What a leak looks like

Check the build output as well as the source, because the generated CSS or
JS is what your components import — a source token can be perfectly formed
and still ship a leak if the build step drops or flattens it. Run the
matching output adapter (`css-vars.md` for generated CSS, for example) on
the generated file, then attribute each finding back to the source token
that produced it, so the fix lands in the file a person actually edits.

## How modes are expressed

Modes come from separate token sets composed at build time, or from
`$extensions` carrying mode-specific values inside a single token. Read the
build config to learn which modes are declared and how they compose — do
not infer modes from directory names, since a folder named `dark` tells you
someone's naming convention, not what the pipeline actually wires together.

## Idiomatic enforcement

A build-time validation step against the DTCG schema catches malformed
tokens before they compile. Pair it with whatever lint already runs on the
generated output, since that is the layer your components consume.

## The one real advantage

This is the only adapter where tier structure is explicit: an alias is
written as `{color.primitive.blue.500}`, naming its own tier in the
reference. Tier integrity is directly readable from the token file itself,
rather than something you infer from naming convention or usage patterns.
