# Explicit completion and setting aside a local deck

Saving a checked draft never means the person approved it. After the person reads it and explicitly marks it Ready, use the main desk's Mark ready button. This works while conversation owns execution, without runner handoff, research runtime pin or jobs.

For browser-free approval, read `studio desk context --folder PATH --target ready/document` (or another current material, with @level). Submit `studio desk ready --folder PATH --input FILE`:

```json
{"target":"document","expected_basis":"<basis>","seen":"<shown version>","response":"<person’s explicit approval>"}
```

Never infer that response from permission to draft. Missing dependencies, holds, changed versions, active workers and another driver refuse. Undelivered Google drafts cannot become Ready. This operation approves one actual material; it creates no copies or jobs and keeps conversation ownership. The retained helper page still serves saved work, but cannot mutate conversation work or move its approval mode.

Google-target edits preserve the original delivered link/baseline and keep a separate local draft. No automatic delivery follows. To resolve that draft without publishing, ask only when the person has not already requested it. Read `studio desk context --folder PATH --target return-delivered@101` (omit @level for a plain training). Explain its summary: return to the previously delivered deck, or set aside the local draft when no delivered deck exists. Local work is retained in History.

Submit `studio desk return-delivered --folder PATH --input FILE`:

```json
{"target":"return-delivered@101","expected_basis":"<basis>","seen":"<local version>","response":"<person’s explicit resolution>"}
```

This restores proven pre-edit active metadata, outline/design/build pointers and genuine historical decisions, or their prior absence. It preserves unrelated materials/settings and Google baselines. It does not approve the local draft, fabricate Ready, convert the target or deliver anything. With no prior deck, explicitly select local PPTX afterward if requested. Changed dependencies, link, snapshot, ownership, worker or seen state refuse without mutation. An older draft lacking original-state proof refuses restoration. Training Studio has no page/CLI delivery action for these local drafts; return/set-aside is the supported lossless exit.
