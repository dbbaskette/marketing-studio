# Section 1 of Rolling restarts

You are building one section of a deck. Other sections are being built at the same time. Your instructions say how to work; `list_inputs` shows what you can read.

## The deck

Rolling restarts, delivered for reading. The user has approved what each slide says. How each is drawn is yours to design.

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

`preview_section` renders your whole section and returns a picture of every slide, with what the renderer found. You have 4 previews. `check_section` is free: use it until the section compiles before you spend a preview.

## Return

Hand the section in with `submit_section`. It must be the version you last previewed. Say what you changed after looking at the pictures and what still bothers you, naming your weakest slide.

## Colour

`headingPrimary` marks the one node that carries a slide's point. Panels start as `canvasSecondary`.
Each of these colours means one thing on every slide; use it for that thing and nothing else, with its name in words too:
- `accentAqua`: Example Platform: the product this deck is about
The deck's recurring device: A strip on each card says what it is about.
