# Harness Brand Plan 7: Brands in Marketing Studio

**Goal:** A Brands section in Marketing Studio, beside Shared settings and This computer, that
makes and updates brand packs and icon libraries in the storage's `brands` folder: add
sources, extract with Harness Brand's `pack` commands, have the person's assistant propose
the judgement files, review them a part at a time, and save with a commit (and, with a team
repository, a push after the person's yes).

**Spec:** [2026-11-03-harness-brand-design.md](../specs/2026-11-03-harness-brand-design.md),
sections 1 to 3 and 7. Earlier plans: [1](2026-11-03-harness-brand-1-icon-libraries.md) to
[5](2026-11-03-harness-brand-5-worker.md); the brands folder for Marketing Studio is
`studio_core.brand_data.unplaced`.

## Files

| File | Responsibility |
|---|---|
| `marketing_studio/brand_skill.py` | The brand skill in use (Shared settings' brand skill, else the first installed one that lists brands, else an installed Harness Brand), whether it is Harness Brand, and running its command under a time limit that Stop ends |
| `marketing_studio/brand_store.py` | Where the brands folder is (local Git or a studio's checkout of the team repository), the listing, working copies, sources, Extract, the parts, Save (check, seal, copy, commit) and Push |
| `marketing_studio/brand_job.py` | The assistant job: the prompt from Harness Brand's guide and format, the confined Claude Code or Codex command, its answer read as JSON and applied to the judgement files only |
| `marketing_studio/page.py` | The `/api/brand-*` routes |
| `marketing_studio/web/brands.js` | The Brands screen, loaded only in Marketing Studio when it is opened |
| `core/studio_core/setup_web/index.html`, `app.js`, `home.css` | The sidebar item, the section, the toolbar actions and the layout of the screen's parts |
| `tests/brand_stand_in/` | A stand-in Harness Brand (Node wrapper, Python logic) answering `version`, `brands --json` and the `pack` commands |
| `tests/test_brands.py` | The focused tests |

## Decisions

- **Working copy.** Each brand or library being made or updated has one working copy in
  Marketing Studio's own data folder, `brand-work/<brand|library>-<id>/`, laid out as the
  brands folder is (`brands/<id>/sources`, `brands/<id>/pack`, and copies of the icon
  libraries), because `pack check` and `pack seal` find sources and libraries beside the
  pack. Added sources go into the working copy's `sources/` and reach storage with the
  pack at Save, so storage changes only on Save and a Discard leaves it as it was.
- **Taken names.** A source whose name is taken waits beside the working copy until the
  person keeps the one there, the new one, or both (the new one renamed `name (2).ext`).
- **Extract and the job run in the background**, one at a time per working copy, with
  plain progress lines and Stop. A record left `running` by a Marketing Studio that closed
  is read as stopped.
- **Extract** asks which source is the design-system export and which variant each template
  is (guessed from its name), and which icon libraries the brand uses; it runs `pack
  tokens`, `pack measure` per template, `pack previews` per variant (a missing LibreOffice
  or Poppler is reported and the rest goes on) and `pack scaffold` when there is no
  `brand.json` yet. On Update, the pack's judgement files are kept and the measured parts
  are made again.
- **The assistant has no tools.** It is given Harness Brand's `references/building-a-pack.md`
  and `docs/brand-pack-format.md`, the extracted files, the drafts and the text of the
  sources (text files and the text files inside archives), and answers one JSON object.
  Marketing Studio writes from it only the judgement files: `brand.json` (without seal
  fields, its id kept), the judgement fields of `layouts.json` (never the measured ones),
  `guide.md`, `directions.json`, `audit.json`, and copies into `assets/` of files from
  `sources/` (or inside an archive there). Nothing is written unless the whole answer
  passes; a failed or stopped job changes nothing. The command lines are those Infographic
  Studio and the shared runner use for confined workers (`claude -p --restricted --tools ""`;
  `codex exec --sandbox read-only` with the shared runner's features switched off), with the
  shared settings' Main model and reasoning.
- **Parts:** colour roles and slide settings (`brand.json`), layouts, guide, deck
  directions, audit limits. Each is accepted, edited (counts as accepted) or sent back with
  a note, which runs the job for that part alone. On Update a part equal to the current
  pack's is marked unchanged and folded away.
- **Save** refuses while a part waits for review, then removes the old seal, runs `pack
  check` (its sentences are shown until it passes), `pack seal`, `pack check` again, and
  refuses when storage's copy of the brand changed since the working copy was made (a
  fingerprint of its files). It replaces `brands/<id>` (or the library's folder) with the
  working copy, adds `brands/.gitattributes` (`* -text`) when missing, and commits only
  those paths under the shared workspace write lock. Local Git storage with no repository
  yet gets one at the brands folder, on this explicit Save.
- **Push** is offered only for a team repository, after the commit, and runs only on the
  person's yes: never forced, and it says how many commits it sends (a studio's own unshared
  commits on that checkout go with it). A refusal leaves the commit on this computer.
- **Over the network** the Brands section is refused: sources, the assistant and Git stay
  on the computer Marketing Studio runs on.
- When the brand skill in use is not Harness Brand, the screen says so in one line with
  where to get Harness Brand and offers nothing else.

## Tasks

1. The brand skill in use and its command (`brand_skill.py`), with the stand-in.
2. Storage, listing, working copies, sources and Extract (`brand_store.py`).
3. The assistant job and the parts (`brand_job.py`).
4. Save and Push.
5. The routes and the screen.
6. Tests, the Marketing Studio suite, and a look at the page in a browser.

## Outcome

To be written when the work is done.
