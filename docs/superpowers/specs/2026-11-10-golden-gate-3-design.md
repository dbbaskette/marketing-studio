# Golden Gate 3: one signature and a shell kit

Approved direction, 10 November 2026: evolve Golden Gate rather than replace it. The
layout rules, the materials and each studio's colour stay. What changes is one signature
element, the progress track, and four features every studio gets from one shared script.

## What a person sees

- **The progress track.** A project's stages as one drawn line in its studio's colour:
  filled where done, larger where the work is now, amber and breathing where it waits for
  the person. In a list only the stage that matters is named. It replaces rows of beads.
- **A Home that speaks.** The Home headline is set in the system serif. Nothing else in
  the shell is; documents keep their own type.
- **Search and jump.** Cmd or Ctrl+K opens a palette of the page's screens, its toolbar's
  actions, the way back to Marketing Studio, and whatever a studio adds (its projects, its
  ways to start). `?` lists the shortcuts.
- **Appearance.** Light, Dark or Auto at the foot of every sidebar and in the palette. It
  is one shared setting, so every studio opens the same way.
- **Finish card.** Shown once when work is marked ready, delivered or published: what was
  made, where it went, one next action.

## How it is built

`core/studio_core/deck_web/shell.js` holds all of it as `StudioShell`, served beside
`lists.js` by every page server and the phone bridge, and loaded before each page's own
script. Its styles are in `ui-kit/style.css` under "The shell kit".

- `appearance` is a word in the studios config (`light`, `dark`, or absent for this
  computer's own), checked in `studio_core.preferences` and saved with the same
  stale-form refusal as every shared value. The server writes it on `<body
  data-appearance>` as a page is served. No page address survives a launch, so nothing is
  kept in the browser.
- A forced appearance rewrites each `prefers-color-scheme` media condition to `all` or
  `not all`, so no token is written twice.
- A page hands the kit its key with `StudioShell.connect` and may add commands with
  `StudioShell.commands`. A command only presses what the page already offers; none
  starts an assistant.
- Motion is one breath on the waiting stage and one rise of the finish card, both off
  under reduced motion.

## The workbench (approved 10 November 2026, after the first look)

The first pass changed how the studios looked and left how they worked. The second
reorganises every desk around the person's work and next move instead of the pipeline's
steps:

- **One arc.** Brief, Plan, Make, Ship replaces each studio's own stage list as the first
  thing said about a project. The detailed steps stay, one press down.
- **Work first.** The document, deck or page is the middle of the screen. Status moves
  to a rail on the right, or a band above where the desk already has a side panel.
- **One move.** A single card says what waits for the person, what it sets going, and
  offers one action. Where nothing waits, the same card says so.
- **Home marks moves.** Marketing Studio's saved work is amber where it is the person's
  move and in the studio's colour while in progress.

Not built: answering a decision from Marketing Studio's home, and starting work from
there. Each studio keeps its own start.

## Order of work

1. The kit, the appearance setting, and Training Studio's stages on the track.
2. Marketing Studio's home and Training Studio's desk: the track at the top of a desk,
   each studio's projects in the palette, the finish card on Mark ready.
3. Blog Studio, Presentation Studio and Infographic Studio, with the open audit items:
   one primary action a screen, Updates off Home, tool errors said plainly.

## Limits

- The serif is the system's: New York on a Mac, Georgia elsewhere. No font is shipped.
- A studio's palette lists that studio's work. Each studio is its own local server.
- The page harness that tests run pages in does not load the kit, so those tests see the
  beads the track replaces; the kit has its own tests in `tests/test_shell_kit.py`.
