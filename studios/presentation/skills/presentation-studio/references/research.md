# Synthesis research

Only do research when the person requests it, the deck's form enables it and its current scope includes the relevant submitted kind. Preserve the pinned document, site and public-web permissions; an outline request never adds research.

Read `studio desk context --folder PATH --target research` for the allowed source scope and requirements. Follow the installed Harness Research synthesis workflow in a separate local case. Send the presentation audience and actual goal as free-text purpose; keep scope and source permissions separate. Obtain independent evidence and semantic review of the exact report and authored brief. A readable draft is not checked research.

Submit through `studio desk submit --folder PATH --input FILE`:

```json
{"kind":"research","target":"research","expected_basis":"<returned basis>","payload":{"case":"/absolute/local/reviewed-case"}}
```

The Studio verifies the owned complete bundle, source captures and source scope before retaining it. It preserves the case and reviewed bundle; inputs changing before save cause refusal. Read the report, prioritized brief, evidence relationships, conditions, counterfacts and gaps in subsequent outline context. Never put private evidence identifiers into reader-facing words.

For planning only, use text target `research-plan`; its payload is `{plan}` with purpose `planning`, pinned scope, topic and up to eight identified questions. No worker executes a saved plan automatically. Existing legacy research keeps its supported old helper commands and saved format; never convert its records by hand.
