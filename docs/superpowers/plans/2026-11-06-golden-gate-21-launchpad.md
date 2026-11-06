# Marketing Studio Golden Gate 2.1 launchpad

Issue #414; audit implementation and merge authorized. Uses the installed
`macos-golden-gate-design` 2.1.0 skill.

## Direction and material map

An editorial launchpad led by the four creative formats: blue writing, orange
presentations, violet training and teal infographics. Stronger studio icons and
filled launch actions anchor softly tinted, opaque format cards. The main question
leads; saved work follows with concise, honest status. Selected navigation has an
accent edge as well as a selected fill and label weight.

Navigation, toolbars and transient controls retain the existing material. Launch
cards, forms, documents and reading surfaces remain opaque. No continuous motion,
new libraries, fonts or build tools. Reduced effects retain the same identity.

## Changes and checks

- Keep each card's Can open state; disclose its repeated healthy explanation in
  Details. Setup, unavailable and connection problems remain visible with recovery.
- Preserve Details/focus through polling and refresh its explanation when readiness
  changes. A lost connection removes stale success details.
- Distinguish no saved work, unavailable work, limited recent work and reconnecting.
- Collapse completed Recent work behind a keyboard-accessible summary; preserve its
  disclosure through polling. Remove copy that duplicates a row's action button.
- Remove an orphaned CSS closing block in the home layout stylesheet.
- Check actual desktop/phone light/dark layouts, keyboard, contrast, reduced effects
  and 200% equivalent viewport; check representative native studio journeys.
- Keep launch, setup, settings and work-resume contracts unchanged.

## Verification

The focused shared-module suite passed all 125 tests. One older Blog Studio
settings test expected every section visible at once; the same failure reproduced
on unchanged main. Its journey now selects Delivery before checking that section,
matching the previously merged section navigation.

The home browser journey passed at 320/390/800/1440/1920px in light/dark,
including keyboard Details and Recent work, retained focus on updates, setup and
connection recovery, unavailable/limited/empty saved-work states, 200% equivalent
viewport and reduced transparency/stronger contrast. Filled launch labels and
selected navigation meet 4.5:1 contrast in both appearances. Screenshots were
inspected at phone/desktop widths.

The existing four-studio visual journey passed, including Infographic Studio
intake/story/rendered preview, shared settings, opaque forms, 44px targets,
320/390/768/1440px, light/dark, reduced effects, keyboard dialogs and no overflow.
The shared disposable Tart run passed its home/recovery browser journeys, 58 shared
UI/work-overview tests and 40 Infographic Studio recovery/rendering checks. It used
macOS 27.0, Python 3.13.15 and Node 22.23.2, then deleted its VM. All workspaces,
settings and authors were synthetic; live provider performance is outside this check.
