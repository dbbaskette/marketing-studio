# Piece 3, the shared desk: design

**Date:** 2026-10-26, at main cc53056 plus the audit docs. **Owner's words:** "Lets apply our
UI changes to blog studio to the other studios. We also need to do an audit of workflow and
clean it up", and, asked whether that meant the layout rules or the writing desk as well:
"1 and 2".

Piece 3 of [the audit's order of work](2026-10-26-workflow-audit.md). The audit settled
that Blog Studio's desk parts move to `core/studio_core/drafting` and `ui-kit/drafting.js`
before a deck desk (piece 5) or a training desk (piece 6) is built, so the text-keeping
rules are written once. This piece moves them and switches Blog Studio over. Nothing a
person sees in Blog Studio changes: the same words, the same controls, the same files on
disk. Presentation Studio and Training Studio are not touched; they gain the parts to use
in pieces 5 and 6.

Pieces 1 and 2 merge first. Piece 1 fixes the Proofread description and gives a stopped
start its exits; piece 2 deletes dead Blog page code and CSS. Line references here are at
cc53056. Re-read every named file on this piece's own base.

## What is wrong now

### Every desk part is Blog Studio's own, and imports Blog's storage

- `desk.py:13`, `desk_jobs.py:18-21` and `desk_finish.py:14-15` (all under
  `studios/blog/skills/blog-studio/scripts/`) import `studio`, whose helpers assume
  `articles/<id>/session.json` and `.blog-runs/` (`studio.py:97-188`). `studio.atomic`
  runs the team workspace's `guard_path` (`studio.py:121`) and `read_json` goes through
  `local_reads` (`studio.py:139`). No other studio can call them.
- The page parts are "Built with runner.js's helpers" (`assets/management/desk.js:2`):
  about 30 of them (`sNode`, `sAdd`, `sButton`, `sCard`, `sOpenSheet`, `sChoice`,
  `sPickCard`, `sBead`, `busy`, `notice`, `api`, `disclosure`) and the globals `access`,
  `studio` and `token`. Presentation's and Training's `app.js` have their own helper set
  (`make`, `button`, `card`), and theirs have drifted from each other.
- `ui-kit/` holds only `style.css` and `markdown.js`.

### The other studios keep one-off versions of the same rules

- Training Studio compares whole files with a line diff, `changes` (`studios/training/
  skills/training-studio/scripts/desk.py:435`).
- Presentation Studio checks a form against one-off signatures per stop:
  `_direction_signature` (`studios/presentation/runner/engine.py:2802`) and
  `NOTE_CHANGED` "The note changed since this page read it" (`engine.py:245`). Its time
  for a redo is the last try only (`_redo`, `engine.py:3135`).

### The surgical rule is enforced by the prompt only

`desk_finish.changes_facts` and `changes_structure` (`desk_finish.py:738`, `:821`) flag a
Finishing proposal that changes a number, a link, a quotation, a name, code or the part's
shape. A section rewrite, a whole-draft revision, a first pass and a selection edit land
without them (`desk_jobs.py:1448-1520`). Presentation's outline step already enforces kept
words in code (`steps/outline.py` `verbatim`); a shared desk should check every rewrite.

### The Finishing tool list is read by position

`sDeskProofView` reads `DESK_TOOLS[1][2]` (`desk.js:813`), the second tool, so the
Proofread panel opens with Apply a voice's description, "The draft rewritten in one of
your voice guides, section by section." Piece 1 fixes the words. A shared panel must find
a tool by its name.

### The desk styles are in a page stylesheet

`.desk-*` rules are in `blog.css:168-225`, `.gap-items` at `:100-103` and `.diff-add` and
`.diff-remove` at `:11`. `docs/design/golden-gate.md` says a page stylesheet "never draws"
a shared control. A second studio would copy about 30 rules.

### Two names to keep apart

"Desk" already means Training Studio's whole page (`scripts/desk.py`, `scripts/desk/`) and
Presentation Studio's (`scripts/desk/`). A `studio_core/desk.py` would read as a page
module.

### The gateway lists page files by name

`marketing_studio/network.py:26-29` lets only listed files through to a phone. A page file
missing from it fails with "Can't find variable: sDeskBegin" (commit 4f6eb53). A new
`drafting.js` must be on that list, and `core/studio_core/packaging.py:23` must accept its
link.

## The design

### 1. Names and places

- Python: the package `core/studio_core/drafting/` with `store.py`, `parts.py`,
  `record.py`, `versions.py`, `basis.py`, `prompts.py`, `guards.py`, `proposals.py` and
  `proofread.py`.
- Two modules that are not only for desks sit beside `stops.py`:
  `core/studio_core/text_checks.py` (moved from Blog Studio unchanged; Blog's runs use it
  too) and `core/studio_core/step_times.py` (deck runner steps can use it outside a desk).
- Page: `ui-kit/drafting.js`, reached from Blog's page by a link like `style.css` and
  `markdown.js`. The desk's styles join `ui-kit/style.css`.
- People still see "the desk". Code says "drafting" for the shared parts. Blog's
  modules keep their names (`desk.py`, `desk_jobs.py`, `desk_finish.py`, `desk.js`) and
  every name they export today, so callers and tests need no change.
- The shared parts read no settings and start no job.

### 2. The store a studio passes in

Core never imports a studio. Each function that touches disk takes a store object. Its
interface, in `drafting/store.py` as a documented base class:

| Member | Meaning | Blog Studio's |
| --- | --- | --- |
| `product` | The product name, in prompts | `'Blog Studio'` |
| `word` | The item word, in sentences | `'blog'` ("Choose a blog on the desk.") |
| `held()` | Whether the studio lock is held | `studio.lock_held()` |
| `folder(ident)` | The item's drafting folder: `draft.json`, `versions/`, `removed.json` | `articles/<id>/desk` (or the team layout `studio.inside` maps), via `desk._paths` |
| `local(ident)` | This computer's folder for the item's waiting proposals; never shared | `.blog-runs/desk-proposals/<id>` |
| `write(ident, draft, parts)` | One revision on, then the studio's own files | `desk._write` |
| `read_json`, `write_json`, `atomic` | Reads and atomic writes | `studio.read_json`, `write_json`, `atomic` |
| `now()` | An ISO time | `studio.now()` |

`write` is the one hook with the studio's layout in it. Every studio's `write` starts with
`record.advance(draft, parts, now)`: revision plus one, `updated_at`, and the `changed`
map. Blog's then writes `draft.json`, `DRAFT.md`, `session.json` and keeps text changed
outside the desk in `history/`, as now (`desk.py:627-663`). A studio without an export
file writes `draft.json` only.

Blog's store is `desk.BlogStore(root)`. Its `write` calls the module's `_write` at call
time, so a test that patches `desk._write` still reaches it.

### 3. Parts and the codec

`drafting/parts.py` holds the parts model: an item is `title`, `opening` and `sections`,
each section `{id, heading, brief, text}`, with `revision` and `changed`.

- The Markdown codec is Blog's code moved: `split`, `join`, `has_heading`,
  `outline_from`, `title_line`, `new_id`, `tidy` and the `FENCE`, `TITLE`, `HEADING`,
  `ANY_HEADING` and `ITEM` patterns (`desk.py:44-202`), byte for byte.
- `Codec` is the hook a deck uses later. It names the fixed parts (`('title',
  'opening')` for Markdown), the parts that are one line (`('title',)`), the part id
  pattern (`[a-f0-9]{8}`), `split`, `join`, and `breaks(text)` (whether text would start a
  new part; Markdown: a `## ` heading outside code). Piece 5 adds an outline codec where a
  slide is a part and `fixed` is empty.
- `section`, `text_of` and `set_text` read and write one part through a codec
  (`desk.py:604-624`).

### 4. The record: the per-part check, save, versions, removed parts

`drafting/record.py` and `drafting/versions.py`, over a store and a codec:

- **The per-part check**, `checked(draft, seen, parts=None)` (`desk.py:666-681`): with no
  parts named the whole item must be as the form saw it; with parts, a form that saw
  revision `seen` may change a part nothing else changed after it. The refusal reads
  "This draft changed since you opened it. Reload to see the latest." with the item's
  thing word ("draft" in Blog).
- `checked_text(part, text)`: a part under 200,000 characters, a one-line part up to 500
  characters, and the codec's `breaks` refusal ("A ## heading would start a new section.
  Use ### for a heading inside this part.").
- `Desk(store, codec, sources)`: `read`, `save` (the same text again is not refused),
  `restore`, and the removed parts `removed`, `keep_removed` and `unremove` (20 kept;
  a section comes back where it was, with its id, so its History comes too;
  `desk.py:880-927`).
- `Versions(store, codec, sources)`: `keep`, `versions`, `counts`
  (`desk.py:1005-1071`). One JSON line per version in `versions/<part>.jsonl`, 20 per
  part, newest last; saves from one editing session keep only the text before the first;
  a torn line never hides the others; a link or a non-file in the path is refused. The
  list of version sources is the caller's: Blog passes its ten, including `chat` and
  `google`.
- Blog-only parts stay in Blog: `create` and the start, `open_run`, `outline_save`,
  `reimport`, `add_sources`, `keep_in_library`, the create ledger and `ROUTES`. They call
  the shared parts.

### 5. The settle and basis rule; the job queues stay per studio

`drafting/basis.py` is "a job lands only if its part is unchanged":

- `fingerprint(value)` (SHA-256 of sorted JSON) and `sections_basis(draft)`
  (`desk_jobs.py:206-211`).
- `ACTIVE`, `unsettled(job)` and `busy(job)`: a ready result not yet landed is still the
  item's job under way (`desk_jobs.py:192-198`).
- `land_part`, `land_selection` and `land_sections`: pure functions that check the basis,
  clean the result, refuse a new heading, check the text and return what to write, with
  the guard's flag (item 7). They are the middle of `desk_jobs._apply`
  (`desk_jobs.py:1448-1520`), including the selection's start offset, the
  single-occurrence fallback and the passage's own spaces around its replacement. The
  refusal reads "The draft changed while this was being written. Run it again."
- `clean`, `no_heading`, `section_texts` and `merge_gaps` (50 kept).
- `settle(job, apply, now)`: the frame that runs a studio's apply and settles the job
  once, with a readable problem whatever goes wrong ("This result could not be saved: …
  Nothing was changed; run it again.", `desk_jobs.py:1532-1543`).

The job queues are not shared. Blog's `tool_jobs` runs one worker with JSON results;
Presentation's and Training's engines run confined workers side by side. Each studio keeps
its queue, its kinds, its index of jobs per item, its whole-draft chain and its start
chain, and calls the basis rule when a result lands.

### 6. Prompts

`drafting/prompts.py`, with the product and thing words passed in:

- `edit_rule(thing)`: the text of `references/modules/desk-edit.md` with "blog draft"
  replaced by `thing`. `edit_rule('blog draft')` is that file's text exactly, so Blog's
  workers get the same guidance. The file is deleted; nothing else reads it.
- `ACTIONS` (rephrase, shorten, expand, fix), `ASK`, `REVISE_ONE`, `WHOLE` and
  `passage_task(line)` (the selection's "Act on the passage only: …").
- `request(label, text, scope, product)`: the author's words fenced as an instruction,
  "AUTHOR’S NOTE FOR THIS SECTION, from the author through Blog Studio. …".
- `SURGICAL`, `SURGICAL_PART`, `FOLLOW`, `ONLY_PASSAGE` and `ALSO_FIX`, the five scope
  sentences Blog uses now (`desk_jobs.py:330-332, 384, 390, 432`), word for word.
- Blog's writing context stays in Blog: `_context`, `WRITE_AGAIN`, `TIGHTEN`, `RESHAPE`,
  `RETURN` and the writing guides.

### 7. Guards, now on rewrites too

`drafting/guards.py` holds `changes_facts`, `changes_structure`, `flags` and `STRUCTURE`
(`desk_finish.py:720-836`). `land_part` and `land_selection` run `flags(before, after)`
on every section rewrite, whole-draft revision, first-pass section and selection edit, and
return the line ("Check the facts: this changes a number.").

In Blog Studio the flag is recorded and not shown, so nothing a person sees changes: the
job keeps `checks: {part: line}` and the desk view's job row carries it. The rewrite still
lands. Pieces 5 and 6 decide how a deck or a training shows or holds a flagged rewrite.
Showing it on Blog's desk is a one-line follow-up for the owner to choose.

### 8. Finishing proposals

`drafting/proposals.py`, `Proposals(store, desk, tools, owner)`:

- The store: `keep`, `latest`, `prune`, `read`, `sets`, `forget`, `present` and
  `summary` (`desk_finish.py:42-180`). Sets wait in the store's `local` folder, never in
  the item's folder, so a team workspace records only what Apply writes. `tools` maps a
  job kind to its panel name (`finish-<name>` by convention). `owner` is the key a set
  names its item by: Blog passes `'blog'`, so saved sets keep working.
- `apply(ident, seen, job, chosen, working)` and `skip(ident, job, ids)`
  (`desk_finish.py:194-296`): one proposal that no longer fits is refused with nothing
  changed; Apply all applies what fits and counts the rest in `left`; a part with a job
  under way is refused (`working`, the parts the studio's busy jobs name); an alternative
  in the same group is skipped; each changed part keeps one `finishing` version first; the
  set is marked applied only after the item is written.
- Two hooks a studio may pass, for proposals that are not text swaps: `present(draft,
  item)` (whether a proposal still fits) and `fit(draft, item, after, text)` (the part's
  new text, or a `ValueError` saying why it no longer fits). Their defaults are Blog's text
  swaps, so Blog passes neither. Piece 5 passes its own for a slide's notes or composition.
- `read_result(content, unreadable)`, `rows` and `located`: the strict JSON frame, fences
  allowed, and the row helpers.
- The tool prompts and readers (`HUMANIZE`, `FACTS`, `_read_humanize`, `request`), the
  voice guides, Google suggestions and Repurpose stay in Blog.

### 9. Proofread and text_checks

- `text_checks.py` moves to `core/studio_core/text_checks.py` unchanged. Blog's
  `scripts/text_checks.py` becomes a shim that imports every public name and keeps the
  command line, so `python3 <runtime>/text_checks.py lint …`
  (`references/workspace/checks.md:6-8`) and `from text_checks import lint` keep working.
- `drafting/proofread.py` holds the in-process Proofread (`desk_finish.py:300-538`):
  sentences, offsets, the rule labels, indented-code masking, repetition, openers and
  `check(draft, rules, starters, ident)`. The rule lists are passed in. Blog keeps reading
  BlogForge's `ai-tells` lists (`references/blogforge/voice/assets/ai-tells/`), which are
  vendored under `blogforge.lock.json` and counted in the guidance inventory; moving them
  would change Blog's guidance.

### 10. Step-time estimates

`core/studio_core/step_times.py`, beside `stops.py`: `seconds(job)`, `note(store, path,
key, seconds)` (20 kept per key, best effort), `expected(store, path, key, guess)` (the
median of recent runs here, in minutes, at least 1, else the guess) and `left(expected,
job, now)` (`{'minutes_left', 'over'}`), from `desk_jobs.py:1195-1288`. Blog keeps its
path (`.blog-runs/desk-step-times.json`), its keys (`draft:short`) and its guesses
(`desk.MINUTES`).

### 11. The page kit and its adapter

`ui-kit/drafting.js` defines one global, `Drafting`. It has its own two DOM helpers,
`make(tag, cls, text)` and `add(parent, ...children)`, with `sNode`'s and `sAdd`'s exact
behaviour, and pure functions: `words`, `diffWords`, `age`. Everything else comes from
`Drafting.kit(adapter)`, which returns the desk's parts bound to what the studio passes:

| Adapter member | What it is | Blog Studio passes |
| --- | --- | --- |
| `ui` | `button`, `card`, `pickCard`, `choice`, `disclosure`, `bead`, `openSheet`, `closeSheet`, `toast`, `notice`, `busy`, `narrow` | `sButton`, `sCard`, `sPickCard`, `sChoice`, `disclosure`, `sBead`, `sOpenSheet`, `sCloseSheet`, `sToast`, `notice`, `busy`, `sNarrow` |
| `api(route, data)` | The page's request, throwing `Error(message)` | `api` |
| `routes` | Route names: `view`, `save`, `versions`, `restore`, `note`, `revise`, `selection`, `stop`, `retry`, `finish`, `apply`, `skip`, `proofread` | `'desk'`, `'desk-save'`, … |
| `share(id)` | The keepalive request when the person leaves | `fetch('/api/desk-share', …)` with `X-Blog-Studio-Token` |
| `canEdit()` | Whether this computer may change the item | `access.actions.edit` |
| `current(held)` | Whether `held` is still the screen shown | `sDeskCurrent` |
| `page()` | The node the cards sit in | `$('studio-page')` |
| `hooks` | `render(held)`, `refresh(held, before)`, `reload(held)`, `beforeJob(held)` | `sDeskRender`, `sDeskRefresh`, `sDesk(held.id)`, `sDeskOutlineFlush` |
| `parts` | `title`, `textOf`, `nameOf`, `single`, `noted` | Title, Opening, the heading; one-line title; a note box on sections |
| `words` | Version labels, what a job is doing, step names, the kinds that name their part, the ready toast | `DESK_SOURCES`, `DESK_DOING`, `DESK_STEPS`, `['desk-section','desk-selection']` |
| `tools` | The Finishing tools, each found by `key` | Blog's seven, with their options and views |
| `progress.actions(held, start)` | The exits a stopped start offers | Retry, and what piece 1 adds |

Every adapter member is a small arrow that looks the studio's function up when called, so
a page check that swaps a global still reaches it.

The kit holds, from `desk.js`:

1. **Autosave and the changed-elsewhere banner**: `typed`, `save`, `flush`, `counts`,
   `stale`, `share` (one second after the last keystroke, against the revision last seen,
   with the session token; one save at a time).
2. **History**: `compare`, `history` (the word diff of each version against now, and
   Restore).
3. **Section cards with notes**: `part`, `whole`, `problem`, `workingIn`, `statusWords`,
   `job`, `watch`.
4. **The selection bar**: `selected`, `selectionBar`, `barContent`.
5. **The progress line and clock**: `elapsed`, `spent`, `clock`, `estimate`, `progress`,
   `followStart`. `progress` returns its parts; the studio frames the page.
6. **The Finishing panel, keyed by name**: `tool(key)`, `finishOpen`, `finishClose`, `finishTool`,
   `panel`, `panelKey`, `panelShow`, `panelSync`, `toolList`, `toolSays`, `toolView`,
   `proposals`, `sides`, `proposal`, `apply`, `skip`, `commentKey`, `comments`,
   `comment`, `toNote`, `proofread`, `proofView`, `finding`, `floating`, `layout`. A tool
   is `{key, name, says, run, doing}` plus optional `options(held, f)`, `data(f)`,
   `ready(f)`, `opened(held)`, `view(held)` and the shape flags `verdicts`, `groups`,
   `comments`, `applyAll`, `counted` and `empty`. Nothing reads a tool by position.

Each kit function takes Blog's `held` object with the field names it has today (`view`,
`pending`, `status`, `stale`, `saving`, `saved`, `session`, `bar`, `selection`, `asking`,
`notes`, `wholeNote`, `finish`, `panel`, `panelKey`, `panelStale`, `panelUnder`, `cards`,
`wholeCard`, `tab`, `watching`, `startWatching`, `dismissed`).

The kit builds the same elements, classes, attributes and words Blog builds now. The
studio composes the page: Blog keeps `sDesk`, `sDeskRender`, `sDeskRefresh`, the toolbar,
the aside, the Outline tab, the start, the publish view, the voice guides, the resize and
sheet glue. Each of Blog's `sDesk*` names the kit took becomes a one-line call into it.

The kit keeps today's `decision-notice` class on its notices. Piece 4 folds that class
into `.callout[data-kind="yours"]`, in the kit, once.

### 12. Styles

The desk's rules move from `blog.css` to `ui-kit/style.css`, in ui-kit's one-property-per-
line form, under a "The desk (drafting.js)" heading: `.desk-layout`, `.desk-column`,
`.desk-aside`, `.desk-part-head`, `.desk-text`, `.desk-note`, `.desk-note-text`,
`.desk-working`, `.desk-working-note`, `.desk-problem`, `.desk-stale`, `.desk-save-state`,
`.desk-selection`, `.desk-versions`, `.desk-version`, `.desk-compare-area`,
`.desk-compare`, `.desk-plain`, `.desk-steps`, `.desk-clock`, `.desk-finishing`,
`.desk-finish` and its `-head`, `-title`, `-body`, `-sheet` and `-tools`,
`.desk-proposal`, `.desk-sides`, `.desk-side`, `.desk-quote`, `.desk-edit`,
`.desk-comments`, `.desk-comment`, `.gap-items`, `.diff-add` and `.diff-remove`. The same
media queries and values. The start's `.desk-angles`, `.desk-angle`, `.desk-angle-picked`
and the Outline tab's `.desk-outline-part` stay in `blog.css`. No class name changes. The
library's selection bar (`.library-selection`) is piece 4's.

### 13. Blog Studio switched over

- `desk.py` imports the parts, builds `BlogStore` and a `Desk`, and keeps every name it
  exports today as an alias or a one-line wrapper (`split`, `join`, `checked`, `save`,
  `keep`, `versions`, `counts`, `restore`, `removed`, `unremove`, `PARTS`, `PART`,
  `SOURCES`, `KEEP`, `LIMIT`, …).
- `desk_jobs.py` uses `basis`, `prompts` and `step_times`; `_apply`, `_settle`, `_guard`
  and its other names stay, so the tests that patch them still do.
- `desk_finish.py` uses `proposals`, `guards` and `proofread` and keeps its names.
- The page loads `/drafting.js` before `/desk.js`: `index.html`, `management.py`'s
  `STATIC`, a link `assets/management/drafting.js -> ../../../../../../ui-kit/drafting.js`,
  `marketing_studio/network.py`'s `STATIC` and `packaging.shared_link`. Blog's page check
  loads `drafting.js` before `desk.js`; no check changes otherwise.

### 14. Saved work

Nothing on disk changes shape. `draft.json`, `versions/*.jsonl`, `removed.json`, the
proposal sets (still keyed `blog`), `desk-step-times.json` and the job records read as
before. The only new field is `checks` on a desk job, which older code ignores.

## Out of scope

- The deck desk and the outline codec where a slide is a part (piece 5).
- The training desk, Training's per-section History from its content-addressed history,
  and its citation rule for rewrites (piece 6).
- The shared layout components: the filter row, the library selection bar, numbered sheet
  steps, `.decision-notice` and the other duplicates (piece 4). The desk's own selection
  bar, `.desk-selection`, is part of the kit.
- Sharing the job queues, the start chain and the whole-draft chain. Each studio keeps its
  own.
- The sources aside, the start's frame and the create ledger. Each studio's intake
  differs; pieces 5 and 6 share them if they turn out the same.
- Finishing tool prompts and result readers, voice guides, Google suggestions and
  Repurpose. They stay in Blog until a second studio needs one.
- Showing a rewrite's guard flag on Blog's desk (a choice for the owner after this piece).
- Retiring Blog's old flow (piece 7).

## Testing

- **Core, one file per part**, all with disposable folders and a `FolderStore` test store
  (`tests/drafting_fixtures.py`) that holds a flag for the lock: `test_drafting_parts`,
  `test_drafting_record`, `test_drafting_versions`, `test_drafting_basis`,
  `test_drafting_prompts`, `test_drafting_guards`, `test_drafting_proposals`,
  `test_drafting_proofread`, `test_text_checks`, `test_step_times`. Each moved rule gets
  the case that protects text: a form older than one part may still change another; a
  torn version line hides nothing; a result whose part changed is refused; a selection in
  a repeated word lands on the one chosen; one stale proposal refuses Apply and Apply all
  leaves it open; an item written outside the lock is refused. A second codec with no fixed
  parts proves the slide hook.
- **Core page kit**, `tests/drafting_page_check.js` driven by `tests/test_drafting_page.py`
  with a stand-in DOM and a fake adapter that is not Blog's: autosave waits a second and
  sends the revision seen; a refused save shows Reload; History compares and restores;
  the selection bar sends the trimmed passage and its start; the progress line says "in
  about 3 minutes" and "Taking longer than usual"; the Finishing panel finds Proofread by
  name with a tool list in another order.
- **Styles**: `tests/test_ui_consistency.py` passes, and a new test checks the moved
  selectors are in `ui-kit/style.css` and not in `blog.css`.
- **Gateway and packaging**: `tests/test_network_static.py` passes with `/drafting.js`
  loaded; `tests/test_packaging_links.py` accepts the `drafting.js` link and refuses a
  link to another ui-kit name.
- **Blog Studio, unchanged in behaviour**: `python studios/blog/scripts/ci/run_tests.py`
  and `(cd studios/blog && node scripts/ci/check-management.cjs)` pass with no test
  edited except the page check's loader line. New Blog tests: a flagged rewrite still
  lands and its job keeps `checks`; the section job's guidance starts with
  `prompts.edit_rule('blog draft')`; `scripts/text_checks.py lint` still runs from the
  command line.
- **Presentation Studio and Training Studio** suites pass untouched.
- No provider, Google or assistant job runs; workers are never started.
