# Section 2 of Rolling restarts

You are building one section of a deck. Other sections are being built at the same time. Read `references/parallel-build.md`, the part headed "If you are a worker", in the guidance for this task, and follow what it tells you to read.

## The deck

Rolling restarts, delivered for reading. The user has approved what each slide says. How each is drawn is yours to design.

## Paths

- Runtime: `stand-in`
- Brand contract: `@DECK@/brand/brand-contract.json`
- Work directory: `@DECK@/work/build/start`
- Write your section to `section-2.json`, and keep your builds and previews under `w2/`. Touch nothing else in the work directory.


## Direction, to copy unchanged

```json
{"focal":"headingPrimary","meanings":{"accentAqua":"Example Platform: the product this deck is about"},"motif":"A strip on each card says what it is about.","neutral":"canvasSecondary"}
```

## House style

- Fill cards: a supporting card is a solid neutral box or a bar card.
- Icons: each card that names a concrete concept gets one approved icon.
- A caveat and a source line go in the slide's own caveat and source fields, never in the drawing.

## Your slides, in order

Prefix every node and edge ID you create with `s2_`. Slide IDs, titles, wording and order are fixed.

1. **`check-yourself`: "Check what you can now explain"**
   - The audience must understand: Each question checks one point.
   - Relation `order`. The point of the slide: Say it aloud.
   - Describe: What happens to the instances?
   - Explain: Why does one instance lose capacity?
   - Speaker notes, to go in the slide's `notes`: 3 min. One question for each point.
   - Sources: ["O1","O2","O3"]

2. **`health-checks`: "Health checks start the next batch"**
   - The audience must understand: The next batch waits for the last one to report healthy.
   - Relation `order`, rhythm `breathing`. The point of the slide: Health first.
   - Health first: A batch is replaced only once the last one is healthy.
   - Wait: A failing check holds the restart.
   - Speaker notes, to go in the slide's `notes`: 4 min. Show the check in the log.
   - Sources: ["O1"]

3. **`rolling-back`: "A failed batch is rolled back, not pushed on"**
   - The audience must understand: A batch that fails its check is put back as it was.
   - Relation `contrast`, rhythm `breathing`. The point of the slide: Roll back.
   - Roll back: The failed batch returns to the last version.
   - Push on: Carrying on would take capacity down.
   - Speaker notes, to go in the slide's `notes`: 3 min. One example.
   - Sources: ["O2"]

Before your section comes the slide "Rolling does not always mean zero downtime", built by another worker; after it comes a closing slide. Do not echo a neighbour, and make your own slides differ from each other.

## Preview

Use one Drive preview file of your own for every preview, and say which it was.

## Return

The section file, your final preview directory, the Drive file ID, what you changed after looking, and what still bothers you.
