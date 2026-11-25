# Section 2 of Rolling restarts

You are building one section of a deck. Other sections are being built at the same time. Read `references/parallel-build.md`, the part headed "If you are a worker", in the guidance for this task, and follow what it tells you to read.

## The deck

Rolling restarts, delivered reading. The user has approved what each slide says. How each is drawn is yours to design.

## Paths

- Runtime: `/opt/slides-tool/versions/0.13.0`
- Brand contract: `@SAVED_TRAINING_FOLDER@/work/deck/brand-30ff3e/brand-contract.json`
- Work directory: `@SAVED_TRAINING_FOLDER@/work/deck/start-b3a07e`
- Write your section to `section-2.json`, and keep your builds and previews under `w2/`.

## Direction, to copy unchanged

```json
{"focal": "headingPrimary", "neutral": "canvasSecondary"}
```

## House style

None given beyond the direction.

## Your slides, in order

Prefix every node and edge ID you create with `s2_`. Slide IDs, titles, wording and order are fixed.

1. **`the-objection`: "Rolling does not always mean zero downtime"**
   - The audience must understand: The claim is true only for an app with several instances.
   - Claim: Rolling always means zero downtime.
   - Correction: Only with more than one instance.
   - Sources: ["O3"]

2. **`check-yourself`: "Check what you can now explain"**
   - The audience must understand: Each question tests one objective.
   - Describe: What happens to the instances?
   - Explain: Why does one instance lose capacity?
   - Sources: ["O1", "O2", "O3"]

## Preview

Use one Drive preview file of your own for every preview, and say which it was.

## Return

The section file, your final preview directory, the Drive file ID, what you changed after looking, and what still bothers you.
