# Changelog

Releases are published from `VERSION`. Each entry says what changes for people
making decks first, then what changes for maintainers.

## Unreleased

- **Start a deck from its source and goal, and see its stops before Start.**
  New deck now asks what the deck starts from, with the brief, the document or
  the deck itself, then the audience and goal, then research and settings. The
  brand, variant, output and assistant start as your defaults under **Brand,
  output and assistant**. **What happens after Start** lists, from your
  choices, research when asked for, **Approve the slide text** wherever slide
  text is drafted, the look to pick or the brand's default, then reviewing the
  deck and delivering. The "stops once" promise is gone from the sheet and from
  Home. Changing the kind of deck keeps everything typed and chosen, research
  and where it may look included, and each kind keeps its own file. Saved decks
  keep their decisions and run nothing again. A document's research sources
  still say the document is included, and the document picker still takes PDF
  files.

  For maintainers: the start-form code in `deck-desk.js` (`start`,
  `sourceStep`, `goalStep`, `settingsStep`, `roadmap`) builds the list from the
  route, level, research, reading and look; `chooseRoute` in `app.js` no longer
  resets research and keeps each kind's file and link.
