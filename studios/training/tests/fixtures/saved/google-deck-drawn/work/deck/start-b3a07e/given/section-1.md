# Section 1 of Rolling restarts

You are building one section of a deck. Other sections are being built at the same time. Your instructions say how to work; `list_inputs` shows what you can read.

## The deck

Rolling restarts, delivered reading. The user has approved what each slide says. How each is drawn is yours to design.

## What you write

One JSON object, the section, handed in with `submit_section`:

```json
{"version": 1, "title": "Rolling restarts", "direction": {"focal": "headingPrimary", "neutral": "canvasSecondary"}, "slides": ["your slides, in order"]}
```

Each slide is `{"id", "title", "sources", "brief": {"relation", "focal": the ID of the node that carries the point, "rhythm"}, "canvas", "connect"?, "caveat"?, "source"?, "notes"}`. Copy each slide's `id`, `title`, `sources`, caveat, source line and notes exactly as they are given below, and keep every word of every point. The input "composition contract" has the exact format.

## Direction, to copy unchanged

```json
{"focal": "headingPrimary", "neutral": "canvasSecondary"}
```

## House style

- A caveat and a source line go in the slide's own caveat and source fields, never in the drawing.
- A point is one sentence: keep its text whole in one shape, with its label in that shape or right beside it. Never split a sentence across boxes. Where a point gives short `parts` labels, draw them as the parts of its diagram and keep the sentence whole once on the slide, unless the brief says it is in the notes.

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

`preview_section` renders your whole section and returns a picture of every slide, with what the renderer found. You have 4 previews. `check_section` is free: use it until the section compiles before you spend a preview.

## Return

Hand the section in with `submit_section`. It must be the version you last previewed. Say what you changed after looking at the pictures and what still bothers you, naming your weakest slide.

## Colour

`headingPrimary` marks the one node that carries a slide's point. Panels start as `canvasSecondary`.
