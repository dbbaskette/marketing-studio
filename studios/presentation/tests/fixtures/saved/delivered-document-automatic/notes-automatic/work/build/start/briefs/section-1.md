# Section 1 of Rolling restarts

You are building one section of a deck. Other sections are being built at the same time. Read `references/parallel-build.md`, the part headed "If you are a worker", in the guidance for this task, and follow what it tells you to read.

## The deck

Rolling restarts, delivered for reading. The user has approved what each slide says. How each is drawn is yours to design.

## Paths

- Runtime: `stand-in`
- Brand contract: `@DECK@/brand/brand-contract.json`
- Work directory: `@DECK@/work/build/start`
- Write your section to `section-1.json`, and keep your builds and previews under `w1/`. Touch nothing else in the work directory.


## Direction, to copy unchanged

```json
{"focal":"headingPrimary","meanings":{"accentAqua":"Example Platform: the product this deck is about"},"motif":"A strip on each card says what it is about.","neutral":"canvasSecondary"}
```

## House style

- Fill cards: a supporting card is a solid neutral box or a bar card.
- Icons: each card that names a concrete concept gets one approved icon.
- A caveat and a source line go in the slide's own caveat and source fields, never in the drawing.

## Your slides, in order

Prefix every node and edge ID you create with `s1_`. Slide IDs, titles, wording and order are fixed.

1. **`what-it-does`: "A rolling restart replaces instances one batch at a time"**
   - The audience must understand: Instances are replaced in batches while the app keeps serving.
   - Relation `order`. The point of the slide: One batch at a time.
   - Batch: Instances are replaced one batch at a time.
   - Traffic: The app keeps serving while it restarts.
   - Source line, to set on the slide as `source`: "Platform documentation: restarts"
   - Speaker notes, to go in the slide's `notes`: 6 min. Walk the three-instance example.
   - Sources: ["O1"]

2. **`when-capacity-holds`: "Capacity holds only with more than one instance"**
   - The audience must understand: A single instance has nothing to hold capacity while it restarts.
   - Relation `contrast`. The point of the slide: More than one instance.
   - Several: The others carry the load.
   - One: Requests are dropped while it restarts.
   - Caveat, to set on the slide as `caveat`: "A single-instance app still drops requests while it restarts."
   - Speaker notes, to go in the slide's `notes`: 7 min. Health checks start the next batch.
   - Sources: ["O2"]

3. **`the-objection`: "Rolling does not always mean zero downtime"**
   - The audience must understand: The claim is true only for an app with several instances.
   - Relation `contrast`, rhythm `breathing`. The point of the slide: It depends on the instance count.
   - Claim: Rolling always means zero downtime.
   - Correction: Only with more than one instance.
   - Speaker notes, to go in the slide's `notes`: 7 min. Correct the claim without dismissing the customer.
   - Sources: ["O3"]

Before your section comes a cover slide; after it comes the slide "Check what you can now explain", built by another worker. Do not echo a neighbour, and make your own slides differ from each other.

## Preview

Use one Drive preview file of your own for every preview, and say which it was.

## Return

The section file, your final preview directory, the Drive file ID, what you changed after looking, and what still bothers you.
