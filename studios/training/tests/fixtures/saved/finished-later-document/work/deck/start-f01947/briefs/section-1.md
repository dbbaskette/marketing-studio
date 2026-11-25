# Section 1 of Rolling restarts

You are building one section of a deck. Other sections are being built at the same time. Read `references/parallel-build.md`, the part headed "If you are a worker", in the guidance for this task, and follow what it tells you to read.

## The deck

Rolling restarts, delivered reading. The user has approved what each slide says. How each is drawn is yours to design.

## Paths

- Runtime: `/opt/slides-tool/versions/0.13.0`
- Brand contract: `@SAVED_TRAINING_FOLDER@/work/deck/brand-a17b3f/brand-contract.json`
- Work directory: `@SAVED_TRAINING_FOLDER@/work/deck/start-f01947`
- Write your section to `section-1.json`, and keep your builds and previews under `w1/`.

## Direction, to copy unchanged

```json
{"focal": "headingPrimary", "neutral": "canvasSecondary"}
```

## House style

None given beyond the direction.

## Your slides, in order

Prefix every node and edge ID you create with `s1_`. Slide IDs, titles, wording and order are fixed.

1. **`what-it-does`: "A rolling restart replaces instances one batch at a time"**
   - The audience must understand: Instances are replaced in batches while the app keeps serving.
   - Batch: Instances are replaced one batch at a time.
   - Traffic: The app keeps serving while it restarts.
   - Sources: ["O1"]

2. **`when-capacity-holds`: "Capacity holds only with more than one instance"**
   - The audience must understand: A single instance has nothing to hold capacity while it restarts.
   - Several: The others carry the load.
   - One: Requests are dropped while it restarts.
   - Sources: ["O2"]

## Preview

Use one Drive preview file of your own for every preview, and say which it was.

## Return

The section file, your final preview directory, the Drive file ID, what you changed after looking, and what still bothers you.
