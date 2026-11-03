# Harness Brand: a brand skill that reads brand packs kept with the studios' storage

Date: 2026-11-03

## Why

Marketing Studio's brand skill today is Tanzu Brand (`dbbaskette/tanzu-brand`, 0.14.1). It
keeps its brand data inside the skill, taken from the corporate Google Slides templates on
6 October 2026, and it has grown to about twenty commands, of which the studios use eight.
The brand data is now the design-system exports made in Claude Design on 3 November 2026,
which sit in `dbbaskette/harness-brand-skill` beside the apply-brand skill.

Harness Brand replaces Tanzu Brand as the studios' brand skill. It is written fresh, with
only what the studios use plus apply-brand's restyling, and it holds no brand data: it reads
brand packs from the `brands` folder of whichever storage Marketing Studio is set to use.

## Goals

- A brand pack format, written down so that someone who does not use Claude Design can make
  a pack by hand or with other tools.
- The three packs (Tanzu Division, VMware by Broadcom, Broadcom), with their separate icon
  archives, made from the 3 November exports.
- Harness Brand: a worker that serves the studios' brand-skill contract from those packs.
- Marketing Studio finds the packs in its storage, local or repository, and tells Harness
  Brand where they are.
- Harness Brand 1.0.0 released with an archive Marketing Studio's installer accepts.

Not in scope: web, video and browser branding, the demo project, scenes, bumpers, the brand
precedence ladder, and installing Harness Research. Tanzu Brand keeps those until it is
retired, which is a later decision.

## 1. Where the pieces live

```
<storage>/brands/                 brand data, the team's or the person's own
  tanzu/
    design-system.zip             the design system: Claude Design export or hand-made
    icons.zip                     the icon library
    brand.json                    the profile: short, written by a person
  vmware/ ...
  broadcom/ ...

harness-brand-skill/              the worker, code only
  SKILL.md
  scripts/harness-brand.mjs       the companion command the studios run
  scripts/install-mac.mjs, scripts/install-skill.mjs
  scripts/lib/harness-install-sources.json
  docs/brand-pack-format.md       the definition (section 2)
  tests/, tests/fixtures/example-pack/   a made-up brand, Example Co
```

`<storage>` follows Marketing Studio's storage setting:

| Storage setting | Brand packs |
|---|---|
| Team repository (`team.repository`) | `brands/` at the root of the repository, in the studio's own workspace checkout of it |
| Local Git (`local.root`, default `~/Studios`) | `<local.root>/brands/`, shared by every studio |

So changing storage between local and repository changes where packs are looked for, and
nothing else. For the current setup that is `brands/` in `dbbaskette/tanzu-marketing-hub`.

The three design-system zips and `apply-brand/brands/` are removed from
harness-brand-skill. Updating a brand means replacing a file in `brands/<id>/` and, with a
repository, committing it. Harness Brand never runs Git and never writes into `brands/`.

## 2. The brand pack format (`docs/brand-pack-format.md`)

The definition is written from what the Claude Design exports hold, and says for each file
what is required, what is optional, and an example. One pack is one folder,
`brands/<id>/`, where `<id>` is lower case letters, digits and hyphens. A pack holds three
files.

### design-system.zip

One top folder (any name) holding:

| Path | Required | What it is |
|---|---|---|
| `tokens.json` | yes | `name`, `version`, and the groups below |
| `README.md` | yes | the brand book: rules in plain words; the naming and voice rules come from here |
| `assets/Logos/` | yes | the logo files, SVG or PNG, with a `README.md` saying which is for light and which for dark grounds |
| `tokens.css` | no | the same tokens as CSS custom properties, with `[data-theme="dark"]` overrides |
| `components/<Name>/README.md` | no | layout guidelines for one component (cover, section, content, card, steps...) |
| `components/<Name>/preview.html` | no | a preview; never read by Harness Brand |
| `assets/<Group>/` | no | supergraphics, imagery, backgrounds, avatars |
| `template.pptx` or `assets/*.pptx` | no | a native PowerPoint template, used as is when `brand.json` names it |

`tokens.json` groups:

- `color.themes`: `[{"id": "light", "name": "Light"}, {"id": "dark", "name": "Dark"}]`; at
  least one theme.
- `color.tokens`: `[{"name", "value", "usage", "dark"?}]`. `value` is the light value, in
  `#rrggbb`. `dark` is the dark value when it differs. An export that has no `dark` fields
  is still accepted: dark values are read from the `[data-theme="dark"]` block of
  `tokens.css`, which is how the 3 November exports hold them.
- `type.families`: `{"sans": "Arial, ..."}`; `type.groups[].styles[]`: `name`, `fontSize`
  (px, where 1 px is 1 pt on the slide canvas), `lineHeight`, `fontWeight`, `usage`.
- `spacing.tokens`, `radius.tokens`: `[{"name", "value", "usage"}]`.
- `gradient`, `shadow`, `stroke`, `borderWidth`: optional, same shape.

### icons.zip

| Path | Required | What it is |
|---|---|---|
| `icons.json` | yes | the index and the shapes |
| `svg/<category>/<slug>.svg` | no | the source drawings, for people; never read by Harness Brand |

`icons.json` is the shape Broadcom's export already uses:

```json
{"source": "...", "viewBox": "0 0 100 100", "note": "...",
 "icons": [{"slug": "cloud-1", "name": "Cloud 1", "category": "Cloud",
            "keywords": ["hybrid", "multi-cloud"], "bounds": [x0, y0, x1, y1],
            "d": "M..Z"}]}
```

Each icon is one single-colour glyph: one SVG path (`d`, several subpaths allowed, filled
even-odd) in a 0 to 100 box, without its container circle. `slug` is unique within the
pack. `keywords` is optional. Colour is never stored; it comes from the brand's roles when
an icon is placed.

### brand.json

Written by a person; `harness-brand pack scaffold` drafts one. It holds what an export does
not say:

- `id`, `name`, `aliases` (the words a request may use for the brand), `schema: 1`.
- `canvas`: `[960, 540]` or the brand's own, in points.
- `variants`: per theme id, the role each token plays. Roles are the contract's: the canvas
  colours, ink, heading, accents, status, chart series and table header. Plus the theme
  colours for PowerPoint (`dk1` ... `folHlink`).
- `slides`: geometry (title box, content box, reserved footer area, margins) and, for each
  of `cover`, `section`, `content`, `closing`, `thanks`, the background, logo and art from
  `assets/`.
- `template`: the path of a native template inside `design-system.zip`, when the pack has
  one. Its layouts are then used as they are.
- `voice`: headline case and the naming rules, when they are not to be taken from the
  brand book alone.

`harness-brand pack check <folder>` reads a pack, lists each missing or wrong part in a
sentence, and exits non-zero when anything required is missing.

### Making the icon archives

The Tanzu Division and VMware by Broadcom exports hold their icons only as SVG files, laid
out differently (`assets/Functional <Category>/` and `assets/Icons <Category>/`). Broadcom's
holds `assets/Icons/icons.json` and coloured SVG sets under `icons/svg/`.

`harness-brand pack icons <design-system.zip> --output icons.zip` builds the archive:

- Takes `assets/Icons/icons.json` as it is when the export has one.
- Otherwise reads each icon SVG: its `path` elements, transforms applied, scaled from its
  view box into the 0 to 100 box, joined into one even-odd path. A drawing made as a filled
  mask (the Tanzu Division icons) uses the mask's white paths as the glyph and its black
  paths as cut-outs. A drawing that holds the container circle (the VMware by Broadcom
  icons) drops it.
- Category comes from the folder name, with the `Functional ` or `Icons ` prefix removed;
  `name` from the file's row in its folder's `README.md`, else from the file name.
- An icon that cannot be expressed as one glyph is left out and named in what the command
  prints. The command never stops on one icon.
- Copies the source SVGs to `svg/<category>/`.

Before the archives are kept, each is drawn as a contact sheet (the glyphs on a grid) and
looked at against the export's own previews, to catch a glyph converted wrongly.

## 3. The worker: Harness Brand

Node 20 or newer, with no npm packages: Node's own `zlib` reads and writes PowerPoint and
zip files. This also replaces apply-brand's Python and its python-pptx environment.

### Finding the packs

`HARNESS_BRAND_DATA`, else `--data <folder>`, names the `brands` folder. With neither, or a
folder with no pack, a command that needs a brand refuses in one sentence that says what to
set. `version` and `doctor` work without packs; `doctor` reports them as missing.

### Commands

| Command | What it does |
|---|---|
| `version` | `Harness Brand <version>` |
| `brands [--json]` | each pack: `brand`, `name`, `variants` |
| `contract export --medium slides\|blog --brand B [--variant V] [--delivery live\|reading] [--voice-profile FILE] --output NEW_DIR` | writes `brand-contract.json`, `DESIGN.md` and the voice and naming guide; the contract records the SHA-256 of the pack's three files |
| `contract check --file brand-contract.json` | refuses a contract whose pack has changed since |
| `icons --query WORDS \| --id ID [--output icon.pptx \| --into deck.pptx --slide N --x --y --width] [--limit N] [--json]` | searches `icons.json` by name, category and keywords; places an icon as a native shape coloured by role |
| `presentation --brand B [--variant V] --file deck.pptx [--json] [--strict]` | the brand audit: `PASS`, `WARN` or `BLOCKED`, with findings by slide number |
| `doctor [--json]` | readiness: Node, Arial, LibreOffice and pdftoppm for previews, the packs |
| `guidance locate\|start\|resume\|cached ...` | the brand's entry to slide building, as the studios call it today |
| `look samples\|choose\|status ...` | deck directions and the person's pick |
| `restyle --file deck.pptx --brand B [--variant V] [--output FILE]` | apply-brand's window dressing; a Google Slides deck by link, in and out through gcloud |
| `pack check \| scaffold \| icons` | section 2 |

The exact arguments, outputs and refusals of the commands the studios call are the ones the
studios' stand-in (`studios/presentation/tests/stand_ins/brand.py`) and
`core/studio_core/shared_runner/brand.py` expect; `brand-contract.json` is the shape
Harness Slides accepts from a brand adapter. Where Tanzu Brand's behaviour and the stand-in
differ, the stand-in is the specification and the difference is noted in the plan.

### Generated parts

Harness Slides builds from a native template and a native icon library. Harness Brand
builds both from a pack and keeps them under `~/Library/Caches/harness-brand/<pack hash>/`
(`$XDG_CACHE_HOME/harness-brand/` elsewhere):

- The template: a master and the layouts for cover, section, content, closing and thanks,
  per variant, from `brand.json`'s geometry, the colour roles, the type styles and the
  logos and art. When `brand.json` names a template in the pack, that is used instead.
- The icon library: each `icons.json` glyph as a native shape, with the index Harness
  Slides reads.

A changed pack has a new hash, so its parts are built again.

## 4. Installing and releasing

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

## 5. Marketing Studio changes

- The runner gives the brand command `HARNESS_BRAND_DATA`, the `brands` folder of section
  1, where it already gives `HARNESS_SLIDES_ROOT`: Presentation Studio, Training Studio,
  Blog Studio and Infographic Studio.
- When that folder is missing or holds no pack, Setup says so in one line, with a link to
  the format, and changes nothing.
- `scripts/sync_repos.py`, `sync.cfg.sample`, `studio-package.example.json`,
  `presentation-studio-package.example.json` and the docs name harness-brand-skill in place
  of tanzu-brand.
- With both brand skills installed, Settings' existing choice of brand skill covers it.
- A person's own settings are never changed: the person changes the brand skill's
  repository in Settings to `https://github.com/dbbaskette/harness-brand-skill` once 1.0.0
  is released.

## 6. Testing

- Harness Brand, with `node --test` on the Example Co pack: `pack check` on a good and a
  broken pack; `pack icons` on a small SVG export of each kind (plain, masked, with a
  container circle); contract export and check, including the refusal after the pack
  changes; icon search and placement; the audit; restyle; the installer into a disposable
  home folder.
- Once with the three real packs, in a disposable home: `pack check` passes, a contract
  exports for each brand and variant, and Harness Slides accepts each.
- Marketing Studio: focused tests that the data folder is given for local and repository
  storage, and that a missing folder is reported. Disposable settings and workspaces only.

## 7. Order of work

1. Write `docs/brand-pack-format.md` in harness-brand-skill.
2. Build `pack icons`, `pack check` and `pack scaffold`; make the three icon archives and
   `brand.json` files and look at the contact sheets.
3. Build the rest of Harness Brand and its installer.
4. Put the three packs in `brands/` of tanzu-marketing-hub, after the person says yes to
   that push.
5. The Marketing Studio changes.
6. Tag and release harness-brand-skill 1.0.0 with the Mac archive and its checksum.
