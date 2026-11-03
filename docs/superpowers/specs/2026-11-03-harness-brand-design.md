# Harness Brand: a brand skill that reads brand packs kept with the studios' storage

Date: 2026-11-03

## Why

Marketing Studio's brand skill today is Tanzu Brand (`dbbaskette/tanzu-brand`, 0.14.1). It
keeps its brand data inside the skill and has grown to about twenty commands, of which the
studios use eight. Newer brand material now exists: the design-system exports made in
Claude Design on 3 November 2026, which sit in `dbbaskette/harness-brand-skill` beside the
apply-brand skill.

Those exports are built for HTML and React. They improve the colours (usage notes, contrast,
dark themes for Tanzu Division and Broadcom), the brand books and the component guidance,
but they hold less of what editable slides are built from than Tanzu Brand does: no native
PowerPoint templates except Broadcom's, no measured layouts, no catalog of which layout
fits which content, no deck directions and no audit rules. Making slides from the exports
alone would rebuild, imperfectly, what the corporate templates already hold.

So Harness Brand reads a brand pack in a schema of our own. A pack is built from whatever
source files a brand has (corporate templates, a Claude Design export, an icon library,
brand guides): scripts do the exact parts and Claude or Codex does the judgement parts,
following a written guide, and a person reviews the result. Harness Brand holds no brand
data; it reads packs from the `brands` folder of whichever storage Marketing Studio uses.

## Goals

- The pack schema, written down so that a pack can be made by hand, with any tools, or by
  Claude or Codex from source files.
- Pack-building commands for the exact parts, and an authoring guide for the rest.
- Packs for Tanzu Division, VMware by Broadcom, Broadcom and TrueSource by Broadcom, sharing
  one icon library.
- Harness Brand: a worker that serves the studios' brand-skill contract from packs, plus
  apply-brand's restyling.
- Marketing Studio finds the packs in its storage, local or repository, and tells Harness
  Brand where they are.
- A Brands section in Marketing Studio to make and update packs: add sources, see what is
  extracted, review the assistant's proposals, and save to local or repository storage.
- Harness Brand 1.0.0 released with an archive Marketing Studio's installer accepts.

Not in scope: web, video and browser branding, the demo project, scenes, bumpers, the brand
precedence ladder, and installing Harness Research. Tanzu Brand keeps those until it is
retired, which is a later decision.

## 1. Where the pieces live

```
<storage>/brands/
  tanzu/
    sources/          what the pack is built from, kept as received
    pack/             what Harness Brand reads (section 2)
  vmware/ ...
  broadcom/ ...
  icon-libraries/     reserved name, never a brand id (section 2)
    vmware-functional/
      sources/        SVGs or an icons.json, as received
      library.zip     the library
    <any later library>/

harness-brand-skill/                 the worker, code only
  SKILL.md
  scripts/harness-brand.mjs          the companion command the studios run
  scripts/install-mac.mjs, scripts/install-skill.mjs
  scripts/lib/harness-install-sources.json
  docs/brand-pack-format.md          the pack schema (section 2)
  docs/icon-library-format.md        the icon library schema (section 2), linked from it
  references/building-a-pack.md      the authoring guide for Claude or Codex (section 3)
  tests/, tests/fixtures/example/    a made-up brand, Example Co: sources and pack
```

`<storage>` follows Marketing Studio's storage setting:

| Storage setting | Brand packs |
|---|---|
| Team repository (`team.repository`) | `brands/` at the root of the repository, in the studio's own workspace checkout of it |
| Local Git (`local.root`, default `~/Studios`) | `<local.root>/brands/`, shared by every studio |

Changing storage between local and repository changes where packs are looked for, and
nothing else. For the current setup that is `brands/` in `dbbaskette/tanzu-marketing-hub`.

The three design-system zips and `apply-brand/brands/` leave harness-brand-skill and become
sources in the packs and the icon library. Harness Brand never runs Git and never writes
into `brands/`; the pack-building commands write only into the `pack/` or library folder
they are given.

## 2. The pack schema (`docs/brand-pack-format.md`)

The format document defines each file with its required and optional fields and an
example, and lists the accepted sources. A pack is one folder; every path inside it is
relative to it.

| File | Required | What it holds | Made by |
|---|---|---|---|
| `brand.json` | yes | `schema: 1`, `id`, `name`, `aliases`, `variants`, `defaultVariant`, the colour roles and PowerPoint theme colours per variant, fonts, canvas, the icon libraries it uses (below), the files below with their SHA-256, and the sources each was made from with theirs | person or agent; `pack scaffold` drafts it |
| `tokens.json` | yes | colours (light and dark values), type styles, spacing, radius, gradients, each with a usage note | `pack tokens` from a design-system export, else by hand |
| `templates/<variant>.pptx` | yes, for slides | the native template: master, layouts and their artwork | the corporate template, as is |
| `layouts.json` | yes, for slides | per variant: each template layout as measured (id, name, part, placeholders with bounds, size, colour and font, artwork to keep) and, for each, `relationship`, `contentRange`, `components`, `searchTerms` and `delivery` | `pack measure` writes the measured part; agent writes the rest |
| `compositions/` | no | authored example slides (`compositions.pptx`) and `compositions.json`, in the shape of `layouts.json` | agent, from example decks |
| `guide.md` | yes | brand rules, voice and naming, slide recipes and standards, in plain words; the source of `DESIGN.md` and the voice guide in an exported contract | agent, from brand books and guides |
| `directions.json` | yes, for slides | deck directions per variant: a default and alternatives, each with focal and neutral roles, meanings, motif and the cover, section, closing and thanks layouts; house rules | agent |
| `audit.json` | yes | the checks the brand audit runs: smallest text, most words on a slide, allowed fonts, allowed colours (by role), corners, starter text, logo rules | agent; `pack scaffold` drafts the defaults |
| `assets/` | yes | logos for light and dark grounds; art and supergraphics `brand.json` names | copied from sources |
| `previews/` | no | a PNG per layout and an icon contact sheet, for review and for look samples | `pack previews` |

A brand without a template (`templates/` empty) is a brand for blogs only: `brands` lists
it without slides, and a slides contract for it is refused in a sentence.

### Icon libraries (`docs/icon-library-format.md`)

An icon library is kept once, in `brands/icon-libraries/<id>/`, and any brand may use it.
All three brands use the one VMware by Broadcom functional library (July 2025), so it is
one library, `vmware-functional`, not three copies. Others (product logos, partner or
architecture icons) are added the same way.

`library.zip` holds:

- `library.json`: `schema: 1`, `id`, `name`, `version`, `source` (where it came from),
  `usage` (its rules in plain words, such as "recolour only to brand colours; never
  outline"), and `kind`:
  - `glyph`: single-colour shapes, coloured by the brand and placed in slides as native
    shapes.
  - `picture`: artwork kept as drawn, in its own colours. Placed as a picture: blogs and
    infographics use it; Harness Slides does not place it as an icon (`native: false` in
    what `icons` returns).
- `icons.json`: `{"schema": 1, "icons": [...]}`, each with `slug` (unique in the library),
  `name`, `category` and, optionally, `keywords`. A glyph adds `bounds` and `paths`: a list
  of path data in a 0 to 100 box, each filled even-odd on its own and all painted together
  in one colour (so overlapping shapes add up), without its container circle, and no
  colour. A picture adds `file`, its path in the archive.
- `svg/<category>/<slug>.svg`: the drawings; required for pictures, optional for glyphs.

```json
{"schema": 1,
 "icons": [{"slug": "cloud-1", "name": "Cloud 1", "category": "Cloud",
            "keywords": ["hybrid", "multi-cloud"], "bounds": [19.5, 15.7, 83.6, 85.2],
            "paths": ["M..Z"]}]}
```

A brand names the libraries it uses in `brand.json`, with the roles a glyph may be drawn
in:

```json
"icons": [{"library": "vmware-functional", "default": true,
           "roles": ["headingPrimary", "accentAqua", "inkDeep"]}]
```

Icon search covers every library the brand names, its default first. `pack check` refuses
a brand that names a library that is missing or does not pass, and a role the brand does
not have. A brand's contract records each library's SHA-256 with the pack's, so a changed
library makes contracts made before it out of date.

### Accepted sources

| Source | Gives |
|---|---|
| Corporate PowerPoint template, one per variant | `templates/`, the measured part of `layouts.json`, theme colours |
| Claude Design export (`*-design-system.zip`) | `tokens.json` (dark values read from `tokens.css` when `tokens.json` has none), `assets/`, the brand book and component guidance for `guide.md` |
| An export's `assets/Icons/icons.json`, or SVG icons (an export's, or any folder of them) | an icon library's `library.zip` |
| Example decks of authored slides | `compositions/` |
| Brand guides (PDF, Markdown, slides) | `guide.md`, `audit.json`, `directions.json` |

Sources are kept in `sources/` as received. `brand.json` records each one's SHA-256, so a
pack says what it was made from and `pack check` notices a source that changed since.

## 3. Building a pack

`references/building-a-pack.md`, in Harness Brand, is written for Claude or Codex and is
what the person points them at: "build the Tanzu pack from brands/tanzu/sources". The steps:

1. **Exact parts, by command** (Harness Brand's `pack` commands, run on the sources):
   - `pack measure <template.pptx> --variant V --into PACK`: copies the template into
     `templates/` and writes each layout's measured part into `layouts.json`.
   - `pack tokens <design-system.zip> --into PACK`: writes `tokens.json`.
   - `pack icons <source>... --library ID --name NAME [--kind glyph|picture] [--fill F]
     --into brands/icon-libraries/ID`: writes `library.zip` from one or more sources, the
     first one's icons winning where slugs meet. A source that holds
     `assets/Icons/icons.json` (Broadcom's export) is taken as it is. For a glyph library,
     SVGs are converted: `path`, `rect`, `circle`, `ellipse`, `polygon` and `polyline` elements
     with their transforms, scaled so the view box fills `F` of the 0 to 100 box (default
     1; the Tanzu Division icons are cut at 0.88 of their circle, as their README says); a
     drawing made as a filled mask (the Tanzu Division icons) uses its mask's paths as the
     glyph; a container circle (the VMware by Broadcom icons) is dropped. Category from
     the folder name, `name` from the folder's `README.md` row, else the file name. An icon
     that cannot be one glyph is left out and named; the command never stops on one icon.
     A picture library keeps each SVG as it is. The first `vmware-functional` is made from
     Broadcom's `icons.json` with the icons only the Tanzu Division and VMware by Broadcom
     SVG sets have added. A PowerPoint icon deck is not a source.
   - `pack scaffold --into PACK`: drafts `brand.json` and `audit.json` from what is there.
2. **Judgement parts, by the agent**, following the guide: the colour roles, each layout's
   relationship, content range and search terms, `guide.md`, `directions.json` and the
   rest of `audit.json`. The guide says what each field means, gives Tanzu Brand's current
   values as worked examples, and says to quote the source for each rule rather than
   invent one.
3. `pack previews --into PACK` renders each layout and the icon contact sheet.
4. `pack check PACK` checks every file against the schema, the hashes, that every layout
   and asset named exists, that every role has a token, and that text roles pass WCAG AA
   on their backgrounds. It lists each problem in a sentence and fails on any.
5. `pack seal PACK`, once `pack check` passes but for the hashes, writes each file's and
   source's SHA-256 into `brand.json`, so no one computes a hash by hand.
6. The person looks at the previews, the contact sheet and the diff, then commits.

The first four packs are built this way from: Tanzu Brand's templates
(`tanzu-presentation-template.pptx`, `vmware-light-template.pptx`,
`vmware-dark-template.pptx`, `broadcom-template.pptx`) and example compositions, the three 3 November Claude
Design exports, and Tanzu Brand's brand rules, recipes, directions and audit values as the
starting point for the judgement parts. Where an export and Tanzu Brand disagree on a
colour or rule, the newer export wins and the change is listed for the person.
TrueSource by Broadcom, added on 3 November, is Broadcom's template with a denser layer for
TrueSource customer decks: its pack is built from `broadcom-template.pptx`, the TrueSource
`tokens.json` and brand book (`README.md`) and the Broadcom logos, all as committed in
harness-brand-skill's `truesource-brand` branch (commit 605a6e5).

## 4. The worker: Harness Brand

Node 20 or newer, with no npm packages: Node's own `zlib` reads and writes PowerPoint and
zip files. This also replaces apply-brand's Python and its python-pptx environment.

### Finding the packs

`HARNESS_BRAND_DATA`, else `--data <folder>`, names the `brands` folder; each
`brands/<id>/pack/` is a brand. With neither, or no pack, a command that needs a brand
refuses in one sentence that says what to set. `version` and `doctor` work without packs;
`doctor` reports them missing. A pack that fails `pack check` is listed by `brands` as
unusable, with the first problem, and is never used.

### Commands

| Command | What it does |
|---|---|
| `version` | `Harness Brand <version>` |
| `brands [--json]` | each pack: `brand`, `name`, `variants`, and whether it does slides |
| `contract export --medium slides\|blog --brand B [--variant V] [--delivery live\|reading] [--voice-profile FILE] --output NEW_DIR` | writes `brand-contract.json`, `DESIGN.md` and the voice and naming guide from the pack; the contract records the pack's hashes |
| `contract check --file brand-contract.json` | refuses a contract whose pack has changed since |
| `layouts --brand B [--variant V] [--query WORDS \| --id ID] [--relationship R] [--json]` | the layouts and compositions, for slide building |
| `icons --query WORDS \| --id ID [--role R] [--output icon.pptx \| --into deck.pptx --slide N --x --y --width] [--limit N] [--json]` | searches the brand's icon libraries; places a glyph as a native shape in one of the brand's icon roles, or a picture as a picture |
| `presentation --brand B [--variant V] --file deck.pptx [--json] [--strict]` | the brand audit from `audit.json`: `PASS`, `WARN` or `BLOCKED`, findings by slide number |
| `doctor [--json]` | readiness: Node, Arial, LibreOffice and pdftoppm for previews, the packs |
| `guidance locate\|start\|resume\|cached ...` | the brand's entry to slide building, as the studios call it today |
| `look samples\|choose\|status ...` | deck directions from `directions.json` and the person's pick |
| `restyle --file deck.pptx --brand B [--variant V] [--output FILE]` | apply-brand's window dressing, from the pack; a Google Slides deck by link, in and out through gcloud |
| `pack measure\|tokens\|icons\|scaffold\|previews\|check\|seal` | section 3 |

The exact arguments, outputs and refusals of the commands the studios call are the ones the
studios' stand-in (`studios/presentation/tests/stand_ins/brand.py`) and
`core/studio_core/shared_runner/brand.py` expect; `brand-contract.json` is the shape
Harness Slides accepts from a brand adapter. Where Tanzu Brand's behaviour and the stand-in
differ, the stand-in is the specification and the difference is noted in the plan.

Harness Brand builds the native icon deck Harness Slides places icons from out of each
glyph library, and keeps it under `~/Library/Caches/harness-brand/<library hash>/`
(`$XDG_CACHE_HOME/harness-brand/` elsewhere). A changed library has a new hash.

## 5. Installing and releasing

- Each release has `harness-brand-<version>-mac.zip` with the skill folder at its root and
  `harness-brand-<version>-mac.zip.sha256` beside it: what Marketing Studio's installer
  downloads and checks (`core/studio_core/shared_runner/brand_source.py`).
- `scripts/install-mac.mjs --yes --research skip` and `scripts/install-skill.mjs
  --research skip` copy the skill to `~/.claude/skills/harness-brand`,
  `~/.codex/skills/harness-brand` and, when `~/.agents` exists,
  `~/.agents/skills/harness-brand`. `--research` is accepted and nothing is done with it.
- When no usable Harness Slides is installed, the installer installs the one pinned in
  `scripts/lib/harness-install-sources.json`, as Tanzu Brand's does.
- The first release is 1.0.0, newer than the brand skill version Marketing Studio's pins
  require today, so no pin has to change.

## 6. Marketing Studio changes

- The runner gives the brand command `HARNESS_BRAND_DATA`, the `brands` folder of section
  1, where it already gives `HARNESS_SLIDES_ROOT`: Presentation Studio, Training Studio,
  Blog Studio and Infographic Studio.
- When that folder is missing or holds no usable pack, Setup says so in one line, with a
  link to the format, and changes nothing.
- `scripts/sync_repos.py`, `sync.cfg.sample`, `studio-package.example.json`,
  `presentation-studio-package.example.json` and the docs name harness-brand-skill in place
  of tanzu-brand.
- With both brand skills installed, Settings' existing choice of brand skill covers it.
- A person's own settings are never changed: the person changes the brand skill's
  repository in Settings to `https://github.com/dbbaskette/harness-brand-skill` once 1.0.0
  is released.

## 7. Brands in Marketing Studio

Making and updating packs is a section of Marketing Studio, beside Settings and Setup. It is
a front for section 3's steps, not another way of doing them: Harness Brand never calls an
assistant, and Marketing Studio never writes pack files itself except through the `pack`
commands and the assistant's job. The page follows `docs/design/golden-gate.md`.

1. **Brands** lists the packs in the storage's `brands` folder, each with its name, its
   variants, whether it does slides, and what `pack check` says, and the icon libraries,
   each with its kind, its count and the brands that use it. It offers New brand and New
   icon library and, on each, Update.
2. **Sources.** The person adds files: templates, a design-system export, guides; for an
   icon library, SVGs or an `icons.json`. They are copied into `brands/<id>/sources/` or
   `brands/icon-libraries/<id>/sources/`; a file whose name is taken is kept beside the old
   one only after the person says which to keep. New asks for the id and name first, and
   a library's kind.
3. **Extract.** Marketing Studio runs `pack measure`, `pack tokens` and `pack previews`
   for a brand, or `pack icons` for a library, into a working copy outside `brands/`, and
   shows what came out: colour swatches for light and dark, the type styles, each layout
   with its preview; for a library, the contact sheet and the icons left out with why. A
   brand's libraries and their roles are chosen on its page, from the libraries there are.
   A library needs no assistant: after Extract it goes to Save.
4. **Interpret.** Marketing Studio runs the person's assistant (the `assistant` setting:
   Claude Code or Codex) as a job on the working copy, told to follow
   `references/building-a-pack.md`. The job may write only the pack's judgement files.
   The page shows its proposals a part at a time (colour roles, layout relationships and
   content ranges, `guide.md`, deck directions, audit limits), each rule with the source
   it quotes. The person edits, accepts or sends a part back with a note, which runs the
   job again for that part only. On Update, only what changed from the current pack is
   shown.
5. **Save.** `pack check` must pass; its problems are shown in its own sentences until it
   does. Save copies the working copy into `brands/<id>/pack/` and commits sources and pack
   together. With a team repository, the push happens only after the person's yes, as
   other studio work does; with local Git, the commit is the save.

A job that fails or is stopped leaves `brands/` untouched and the working copy as it was,
so the person can try again or discard it. The working copy is removed after a save or a
discard. Two people updating one brand is caught as the studios catch it today: the save
refuses when the pack in storage changed after the working copy was made.

Building the first four packs (section 3) is done by hand in a session, with the commands
and the guide, before this section is built, so that the guide is tried on real material
first.

## 8. Testing

- Harness Brand, with `node --test` on Example Co, whose sources are a small template, a
  small design-system zip, a small `icons.json`, SVG icons of each kind (plain, masked,
  with a container circle) and a picture library: each `pack` command, including a library
  made from two sources; `pack check` on a good pack and on broken ones;
  contract export and check, including the refusal after the pack changes; layouts, icon
  search and placement; the audit; restyle; the installer into a disposable home folder.
- Once with the four real packs, in a disposable home: `pack check` passes, a contract
  exports for each brand and variant, Harness Slides accepts each, and one deck per brand
  builds and passes the audit.
- Marketing Studio: focused tests that the data folder is given for local and repository
  storage, and that a missing folder is reported. Brands: listing, adding sources,
  extracting into a working copy, a stand-in assistant job that writes the judgement files,
  sending one part back, the save refused by `pack check`, the save refused after the pack
  changed in storage, and the commit in local and repository storage. Disposable settings,
  workspaces and Git identities only; no real assistant job is started.

## 9. Order of work

1. Write `docs/brand-pack-format.md` and `references/building-a-pack.md`; make Example Co.
2. Build the `pack` commands.
3. Build the `vmware-functional` icon library and the four packs from their sources; the
   person reviews the contact sheet, the previews and the listed differences from Tanzu
   Brand.
4. Build the rest of Harness Brand and its installer.
5. Put the sources and packs in `brands/` of tanzu-marketing-hub, after the person says yes
   to that push.
6. The Marketing Studio changes: the data folder for the studios (section 6), then Brands
   (section 7).
7. Tag and release harness-brand-skill 1.0.0 with the Mac archive and its checksum.
