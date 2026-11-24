# Section 2 of Rolling restarts

You are building one section of a deck. Other sections are being built at the same time. Your instructions say how to work; `list_inputs` shows what you can read.

## The deck

Rolling restarts, delivered live. The user has approved what each slide says. How each is drawn is yours to design.

## What you write

One JSON object, the section, handed in with `submit_section`:

```json
{"version": 1, "title": "Rolling restarts", "direction": {"focal": "headingPrimary", "meanings": {"accentAqua": "Example Platform: the product this deck is about"}, "motif": "A strip on each card says what it is about.", "neutral": "canvasSecondary"}, "slides": ["your slides, in order"]}
```

Each slide is `{"id", "title", "sources", "brief": {"relation", "focal": the ID of the node that carries the point, "rhythm"}, "canvas", "connect"?, "caveat"?, "source"?, "notes"}`. Copy each slide's `id`, `title`, `sources`, caveat, source line and notes exactly as they are given below, and keep every word of every point. Where your task gives a slide whole (a template `layout`, a `picture`) or gives an image node to place, copy it exactly as given. The input "composition contract" has the exact format.

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

`preview_section` renders your whole section and returns a picture of every slide, with what the renderer found. You have 4 previews. `check_section` is free: use it until the section compiles before you spend a preview.

## Return

Hand the section in with `submit_section`. It must be the version you last previewed. Say what you changed after looking at the pictures and what still bothers you, naming your weakest slide.

## Colour

`headingPrimary` marks the one node that carries a slide's point. Panels start as `canvasSecondary`.
Each of these colours means one thing on every slide; use it for that thing and nothing else, with its name in words too:
- `accentAqua`: Example Platform: the product this deck is about
The deck's recurring device: A strip on each card says what it is about.
