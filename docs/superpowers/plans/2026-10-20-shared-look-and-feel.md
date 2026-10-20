# Shared look and feel implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every web page in the repository uses the shared `ui-kit` Golden Gate-inspired shell and control set, and each product keeps its colour from the Marketing Studio home page.

**Architecture:** `ui-kit/style.css` owns the tokens, the shell and every reusable control. Page stylesheets (`home.css`, `blog.css`, `deck.css`, and inline styles on two static pages) only lay out page-specific parts. A guard test enforces this:

- no bare control or heading selectors at the top level;
- only layout properties on shared classes and control elements;
- no literal colours.

Marketing Studio home and setup move onto the shell. Blog Studio's editorial screens move onto shared controls. Presentation Studio and Training Studio get small alignment fixes.

**Tech stack:** Python 3.11 standard library (`unittest`), vanilla HTML/CSS/JavaScript, no build step. Node is used by the existing page checks.

**Spec:** [`docs/superpowers/specs/2026-10-20-shared-look-and-feel-design.md`](../specs/2026-10-20-shared-look-and-feel-design.md)

**Repository rules (from AGENTS.md):**
- Use full product names.
- Use the standard library only.
- No frontend build step.
- Tests use disposable settings and never start provider jobs.
- Run targeted checks at milestones and the full suite once before completion.

---

## File map

| File | Change |
| --- | --- |
| `tests/test_ui_consistency.py` | **Create.** The guard test for stylesheets and page shells. |
| `ui-kit/style.css` | Add the shared choice card, workflow steps, dialog, label field, radio segmented control, typed input, link and checkbox colour, and forced-colour edges. Remove the Training-only material-choice rules. |
| `core/studio_core/setup_web/index.html` | Rebuild on `.window`/`.sidebar.glass`/`.toolbar.glass`/`.page` with shared fields. |
| `core/studio_core/setup_web/home.css` | Replace with layout-only rules for studio cards, setup grid and profiles. |
| `core/studio_core/setup_web/app.js` | Shared classes; focus and announcement on view and step change; toasts; a readable lost-connection message; segmented radios; studio symbol in standalone setup. |
| `studios/blog/skills/blog-studio/assets/management/index.html` | Editorial screen and dialogs on shared controls. |
| `studios/blog/skills/blog-studio/assets/management/blog.css` | Remove legacy controls, dialogs and moved rules; keep Blog Studio layouts. |
| `studios/blog/skills/blog-studio/assets/management/app.js` | Shared classes on editorial buttons, fields, table and textarea. |
| `studios/blog/skills/blog-studio/assets/management/runner.js` | Start tasks as shared choice cards; fix the undefined `button-outlined`. |
| `studios/presentation/skills/presentation-studio/scripts/desk/deck.css` | Remove the choice card (moved to `ui-kit`) and resize the storyboard frame. |
| `studios/presentation/skills/presentation-studio/scripts/desk/app.js` | Remove the inert `followPointer()`. |
| `studios/training/skills/training-studio/scripts/desk/app.js` | Material choices use the shared `chip()`. |
| `studios/blog/preview/blog-studio.html` | Shared stylesheet, toolbar, cards and fields. |
| `studios/blog/docs/development.md` | Serve the beginner page from the Blog Studio root. |
| `docs/design/unified-settings-preview.html` | Rebuild on the shared stylesheet. |
| `docs/design/golden-gate.md` | Component inventory and the layout-only rule. |
| `docs/design/*.jpg` | Regenerate the three screenshots. |

Do not rename `index.html`, `app.js`, `home.css`, `style.css`, `blog.css` or `deck.css`. The static file maps (`marketing_studio/server.py`, `core/studio_core/onboarding.py`), the network allowlist (`marketing_studio/network.py`) and the packaging link rules (`core/studio_core/packaging.py`) name them.

---

### Task 1: Guard test (done)

**Files:**
- Create: `tests/test_ui_consistency.py`

- [x] **Step 1: Write the failing guard.** Done in `641398e`. After code review, `ea6c742` made it precise:
  - failures name each selector and property;
  - `:is()`/`:where()`, statement at-rules, custom properties on shared classes, and `:root`/`body`/`*` can no longer slip through;
  - colours are read from declarations only;
  - shell markers are matched as class sets;
  - static pages must link the kit inside the folder they are served from.

  `SHARED` also covers tables, titles, tags, states and the other shared components, and `ELEMENTS` covers table elements. The committed file is the reference.
- [x] **Step 2: Confirm it fails for real reasons.** `python3 -m unittest tests.test_ui_consistency -v` reports 8 failures:
  - the missing kit components;
  - the `home.css`, `blog.css` and `deck.css` redraws and literal colours;
  - the setup page without the shell;
  - both static pages;
  - four Blog Studio dialogs without `class="dialog"`.
- [x] **Step 3: Commit.**

---

### Task 2: Shared components in `ui-kit`

**Files:**
- Modify: `ui-kit/style.css`. All four studios link it, through symlinks to the same file.

- [ ] **Step 1: Add link and checkbox colour to the base rules.** Insert after the `button, input, textarea { font: inherit; color: inherit; }` rule (around line 189):

```css
a {
  color: var(--link);
}

input[type="checkbox"],
input[type="radio"] {
  accent-color: var(--accent);
}

summary {
  cursor: pointer;
}
```

- [ ] **Step 2: Add the new component section.** Insert immediately before the line `/* --- fallbacks: each one swaps the glass for something solid --------------------------- */`:

```css
/* --- shared choices, steps, fields and dialogs ------------------------------------------- */

/* A card that is a button: one of several to pick from. The tick and its words say it is
   picked, not colour alone. */
.pick-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 15rem), 1fr));
  gap: 0.8rem;
  margin-top: 0.6rem;
}

.pick-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  width: 100%;
  padding: 0.9rem 1rem;
  background: var(--paper);
  color: var(--ink);
  font: inherit;
  font-weight: 650;
  text-align: left;
  white-space: normal;
  border: 1px solid var(--hair);
  border-radius: 10px;
  cursor: pointer;
}

.pick-card:hover {
  border-color: var(--selection-line);
}

.pick-card:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.pick-card[aria-pressed="true"] {
  background: var(--selection);
  border-color: var(--focus);
  box-shadow: inset 0 0 0 1px var(--focus);
}

.pick-top {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.pick-card[aria-pressed="false"] .icon {
  display: none;
}

.pick-title {
  font-weight: 650;
}

.pick-says {
  color: var(--quiet);
  font-size: 0.93rem;
  font-weight: 400;
}

/* Where a person is in a short run of steps: setup, a new blog, the beginner page. */
.workflow-steps {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: 0 0 1.2rem;
  padding: 0 0 0.6rem;
  list-style: none;
  border-bottom: 1px solid var(--hair);
}

.workflow-steps .button,
.workflow-step {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 2.75rem;
  padding: 0.5rem 0.7rem;
  background: transparent;
  border: 0;
  border-radius: 8px;
  box-shadow: none;
  font-size: 0.88rem;
  line-height: 1.3;
  text-align: center;
  white-space: normal;
}

.workflow-steps [aria-current="step"] {
  background: var(--selection);
  color: var(--link);
  font-weight: 700;
}

/* A label that holds its own control: its words, then the box. */
label.field {
  display: block;
  font-weight: 650;
}

label.field > .input,
label.field > .field-hint {
  margin-top: 0.4rem;
  font-weight: 400;
}

/* Radio buttons drawn as a segmented control. The radios stay real for the keyboard. */
label.seg-option {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.seg-option > input[type="radio"] {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.seg-option:has(> input:checked) {
  color: var(--link);
}

.seg-option:has(> input:focus-visible) {
  outline: 3px solid var(--focus);
  outline-offset: 2px;
  box-shadow: 0 0 0 7px var(--focus-halo);
}

/* A box holding something to copy exactly, such as a private link. */
.input-typed {
  font-family: var(--typed);
  font-size: 0.85rem;
}

/* The brand in the sidebar can also be the way home. */
a.brand {
  text-decoration: none;
}

.large-title:focus {
  outline: none;
  box-shadow: none;
}

/* A dialog the browser keeps: on the sheet's surface, its title bar held at the top. */
.dialog {
  width: min(46rem, calc(100% - 1.5rem));
  max-height: calc(100dvh - 1.5rem);
  padding: 0;
  overflow: auto;
  background: var(--sheet-fill);
  color: var(--ink);
  border: 1px solid var(--glass-line);
  border-radius: 22px;
  box-shadow: var(--edge), var(--lift);
}

.dialog::backdrop {
  background: rgb(15 20 40 / 0.35);
  -webkit-backdrop-filter: blur(4px);
  backdrop-filter: blur(4px);
}

.dialog-header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.3rem;
  background: var(--sheet-fill);
  border-bottom: 1px solid var(--hair);
}

.dialog-header > h2 {
  font-size: 1.12rem;
  font-weight: 700;
}

.dialog-content {
  padding: 1.3rem;
}

.dialog-form {
  padding: 0 1.3rem 1.3rem;
}

.dialog-form > .dialog-header {
  margin: 0 -1.3rem;
}

.dialog-content > * + *,
.dialog-form > * + * {
  margin-top: 0.9rem;
}

@media (max-width: 37.5rem) {
  .workflow-steps .button,
  .workflow-step {
    padding: 0.5rem 0.3rem;
    font-size: 0.82rem;
  }
}

@media (forced-colors: active) {
  .card,
  .paper,
  .sheet,
  .dialog,
  .pick-card {
    border-color: CanvasText;
  }

  .sidebar {
    border-right-color: CanvasText;
  }

  .toolbar {
    border-bottom-color: CanvasText;
  }
}
```

- [ ] **Step 3: Let the dialog backdrop follow reduced transparency.** In the existing `@media (prefers-reduced-transparency: reduce), (prefers-contrast: more)` block, after the `.glass { … }` rule, add:

```css
  .dialog::backdrop {
    -webkit-backdrop-filter: none;
    backdrop-filter: none;
  }
```

- [ ] **Step 4: Run the component test**

Run: `python3 -m unittest tests.test_ui_consistency.SharedLookTests.test_kit_defines_every_shared_component -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui-kit/style.css
git commit -m "Share choice cards, steps, dialogs and radio segments in ui-kit

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Presentation Studio alignment

**Files:**
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/deck.css`
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/app.js:6027-6037,6090`

- [ ] **Step 1: Remove the moved choice card from `deck.css`.** Delete everything from the comment `/* A card that is a button: one of several to pick from.` through the end of the `.pick-says { … }` rule (lines 6-52). `ui-kit` now provides the rules unchanged.

Also delete the rule `.steps > summary { cursor: pointer; }`. `ui-kit` now gives every `summary` that cursor.

- [ ] **Step 2: Size the storyboard frame as a reading surface.** Replace the last rule of `deck.css`:

```css
/* The outline engine's self-contained wireframe is isolated from application DOM. */
.storyboard { width: 100%; height: min(72vh, 48rem); border: 1px solid var(--hair); border-radius: 8px; background: var(--paper); margin-top: 12px; }
```

with:

```css
/* The outline engine's self-contained wireframe is isolated from the page, so it cannot
   report its own height. It fills the reading column, and on a phone the screen above the
   bottom bar, rather than nesting a short scroll area. */
.storyboard {
  display: block;
  width: 100%;
  height: min(80vh, 56rem);
  margin-top: 0.75rem;
  background: var(--paper);
  border: 1px solid var(--paper-line);
  border-radius: 14px;
}

@media (max-width: 52rem) {
  .storyboard {
    height: calc(100dvh - 12rem);
  }
}
```

- [ ] **Step 3: Remove the inert pointer listener from `app.js`.** Delete the whole function (lines 6027-6037):

```js
// A highlight on glass that follows the pointer. Not when the person asked for less motion.
function followPointer() {
  if (calm()) return;
  document.addEventListener('pointermove', (event) => {
    const lit = event.target && event.target.closest ? event.target.closest('.shine') : null;
    if (!lit) return;
    const box = lit.getBoundingClientRect();
    lit.style.setProperty('--mx', (event.clientX - box.left) + 'px');
    lit.style.setProperty('--my', (event.clientY - box.top) + 'px');
  }, { passive: true });
}
```

and delete its call in `begin()`: the line `  followPointer();`. Confirm nothing else calls it:

Run: `grep -n "followPointer" studios/presentation/skills/presentation-studio/scripts/desk/app.js`
Expected: no output.

- [ ] **Step 4: Run Presentation Studio's suite and the guard**

Run: `(cd studios/presentation && python3 scripts/ci/run_tests.py)`
Expected: all tests OK. Tests that need a local port may report as skipped or errored inside a sandbox, and the same tests did so before the change.

Run: `node --check studios/presentation/skills/presentation-studio/scripts/desk/app.js && python3 -m unittest tests.test_ui_consistency -v 2>&1 | grep deck.css`
Expected: no `deck.css` failure.

- [ ] **Step 5: Commit**

```bash
git add studios/presentation/skills/presentation-studio/scripts/desk/deck.css studios/presentation/skills/presentation-studio/scripts/desk/app.js
git commit -m "Use shared choice cards and a reading-size storyboard in Presentation Studio

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Training Studio material choices use shared chips

**Files:**
- Modify: `studios/training/skills/training-studio/scripts/desk/app.js:4072-4094` (`materialChoices`)
- Modify: `ui-kit/style.css` (remove the Training-only material-choice rules)

- [ ] **Step 1: Replace `materialChoices`** with a version built on the existing `chip(label, on, flip, key)` helper (line 688):

```js
function materialChoices(draft) {
  const node = make('div', 'chips material-choices');
  node.setAttribute('role', 'group');
  node.setAttribute('aria-label', 'Materials to make');
  for (const [id, label] of MATERIALS) {
    node.append(chip(label, draft.materials.includes(id), (selected) => {
      draft.materials = MATERIALS.map(([key]) => key)
        .filter((key) => key === id ? selected : draft.materials.includes(key));
      // Yoodli's knowledge and scenario dependencies are explicit selections.
      if (!selected && ['brief', 'scenario'].includes(id)) {
        draft.yoodli = false;
        const yoodli = Array.from(main().querySelectorAll('.chip')).find((item) => item.dataset.key === 'practice yoodli');
        if (yoodli) yoodli.setAttribute('aria-pressed', 'false');
      }
      say(byId('new-problem'), '');
    }, 'material ' + id));
  }
  return node;
}
```

- [ ] **Step 2: Remove the four Training-only material-choice rules from `ui-kit/style.css`.** Delete these, and keep the `.training-options` rules:

```css
body[data-product="Training Studio"] .material-choices { … }
body[data-product="Training Studio"] .material-choice { … }
body[data-product="Training Studio"] .material-choice[aria-pressed="true"]::before { … }
body[data-product="Training Studio"] .material-choice[aria-pressed="true"] { … }
```

- [ ] **Step 3: Run Training Studio's desk tests**

Run: `node --check studios/training/skills/training-studio/scripts/desk/app.js && (cd studios/training && python3 scripts/ci/run_tests.py test_desk)`
Expected: OK. If a step in `tests/test_desk.py` clicks a material by its old capsule name, update it to the label text: a chip's accessible name is its label.

Run: `grep -rn "material-choice\|capsule material" studios/training ui-kit`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add studios/training/skills/training-studio/scripts/desk/app.js ui-kit/style.css
git commit -m "Use shared chips for Training Studio material choices

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Marketing Studio home and shared setup on the shell

**Files:**
- Replace: `core/studio_core/setup_web/index.html`
- Replace: `core/studio_core/setup_web/home.css`
- Modify: `core/studio_core/setup_web/app.js`

`marketing_studio/web/{index.html,app.js,home.css}` are symlinks to these files. Each studio's standalone setup is served from the same files, with `Marketing Studio` replaced by the studio's name (`core/studio_core/onboarding.py:90`).

- [ ] **Step 1: Replace `index.html`**

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="color-scheme" content="light dark">
  <title>Marketing Studio</title>
  <link rel="stylesheet" href="/style.css">
  <link rel="stylesheet" href="/home.css">
  <script src="/app.js" defer></script>
</head>
<body data-product="Marketing Studio" data-token-header="X-Marketing-Studio-Token" data-standalone="false">
<a class="skip" href="#content">Skip to content</a><div class="backdrop" aria-hidden="true"></div>
<div class="window">
  <nav class="sidebar glass" aria-label="Main navigation">
    <a href="#" class="brand" id="home-link"><span id="home-symbol" class="studio-symbol" aria-hidden="true">M</span><span id="home-name">Marketing Studio</span></a>
    <button type="button" data-view="home" class="nav-item"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></svg><span class="nav-label">Studios</span></button>
    <button type="button" data-view="settings" class="nav-item"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 7.5h7"/><path d="M16.5 7.5h3"/><path d="M14 5.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/><path d="M4.5 16.5h3"/><path d="M12.5 16.5h7"/><path d="M10 14.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg><span class="nav-label">Shared settings</span></button>
    <button type="button" data-view="computer" class="nav-item"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4.5h18v13H3z"/><path d="M8 21h8"/><path d="M12 17.5V21"/></svg><span class="nav-label">This computer</span></button>
    <p class="sidebar-foot">One place to get ready.<br>Three places to create.</p>
  </nav>
  <div class="content">
    <div class="toolbar-wrap"><header class="toolbar glass"><div class="toolbar-title"><h1 id="view-title" class="title" tabindex="-1">Studios</h1></div><div class="toolbar-actions"><span id="where" class="tag">On this computer</span></div></header></div>
    <p id="problem" class="notice" role="alert" hidden></p>
    <main id="content" class="page" tabindex="-1">
      <p id="announce" class="offscreen" role="status" aria-live="polite"></p>
      <div id="message" class="paper callout" role="status" hidden></div>
      <section id="loading"><p class="large-title">Opening your studios…</p></section>
      <section id="home" hidden>
        <div class="intro"><h2 class="large-title">What will you make?</h2><p class="lede">Your settings are shared. Each studio has its own space to work.</p></div>
        <div id="studio-list" class="studio-list"></div>
        <section class="card settings-summary"><div><h3 class="card-title">Ready when you are</h3><p id="summary-text"></p></div><button type="button" data-view="settings" class="button">Change settings</button></section>
        <section id="network-access" class="card" hidden aria-labelledby="network-heading">
          <h3 id="network-heading" class="card-title">Continue on your phone</h3>
          <p>Connect to the same trusted Wi-Fi and open this private link. Your work and assistant stay on this computer.</p>
          <div class="field"><label class="field-label" for="network-link">Private session link</label>
            <div class="copy-row"><input id="network-link" class="input input-typed" type="text" readonly autocomplete="off" spellcheck="false"><button type="button" id="copy-network" class="button">Copy link</button></div></div>
          <p class="field-hint quiet">Anyone with this link has full studio access. HTTP is unencrypted. Keep it on a trusted network; stop Marketing Studio to disconnect.</p>
        </section>
        <p class="quiet launch-note">Leave the Marketing Studio terminal open while you work. You can also open each studio with its own launcher.</p>
      </section>
      <section id="settings" hidden>
        <div class="intro"><p id="step-label" class="quiet"></p><h2 id="settings-title" class="large-title" tabindex="-1">Shared settings</h2><p id="settings-intro" class="lede">New work in every studio starts with these choices.</p></div>
        <ol id="setup-progress" class="workflow-steps" aria-label="Setup progress" hidden><li class="workflow-step">You and your assistant</li><li class="workflow-step">Your workspace</li><li class="workflow-step">Brand and delivery</li></ol>
        <form id="settings-form" class="setup-form">
          <section class="card" data-step="0"><h3 class="card-title">You and your assistant</h3><p class="quiet">Use your signed-in assistant for research, writing, and slide work.</p>
            <div class="field-grid">
              <div class="field"><label class="field-label" for="person-name">Your name</label><input id="person-name" class="input" name="person.name" autocomplete="name" maxlength="100"></div>
              <div class="field"><label class="field-label" for="assistant-agent">Assistant</label><select id="assistant-agent" class="input" name="assistant.agent"><option value="claude">Claude Code</option><option value="codex">Codex</option></select></div>
              <div class="field"><label class="field-label" for="assistant-model">Model <span class="quiet">(optional)</span></label><input id="assistant-model" class="input" name="assistant.model" maxlength="100" placeholder="Use the assistant’s default" autocomplete="off"><p class="field-hint quiet">Use an ID available in your account. All three studios use these choices for the selected assistant.</p></div>
              <div class="field"><label class="field-label" for="assistant-effort">Reasoning</label><select id="assistant-effort" class="input" name="assistant.effort"></select></div>
            </div>
            <div class="model-catalog-bar"><p id="model-catalog-status" class="field-hint quiet" role="status">Loading model choices…</p><button type="button" id="refresh-models" class="button">Refresh models</button></div>
            <div class="setup-part">
              <div class="model-heading"><div><h4 class="sheet-part">Models for your work</h4><p class="quiet">Keep one model for everything, or choose a model for each kind of task.</p></div>
                <div class="field"><p class="field-label" id="model-mode-label">Model routing</p><div class="segmented" data-count="2" data-at="0" role="radiogroup" aria-labelledby="model-mode-label"><span class="seg-thumb" aria-hidden="true"></span><label class="seg-option"><input type="radio" name="models.mode" value="single" checked>One model</label><label class="seg-option"><input type="radio" name="models.mode" value="by_task">By task</label></div></div></div>
              <div id="model-profiles" hidden>
                <p class="field-hint quiet">Quick handles extraction, classification and Presentation Studio outlines. Main handles research, drafting, slides, review and the first repair. Complex handles repeated slide findings and other dedicated repairs. New work saves these choices; existing work keeps its models.</p>
                <div id="profile-cards" class="profile-cards"></div>
                <div id="profile-review" class="paper callout" data-kind="yours" role="status" hidden><p>The assistant changed. Check the model IDs and reasoning levels before using these profiles with this assistant.</p><button type="button" id="confirm-profiles" class="button">Use these profiles with this assistant</button></div>
                <p class="field-hint quiet">Use model IDs available in your signed-in account. The studios send your choice directly to the selected assistant and stop if it cannot be used.</p>
              </div>
            </div>
            <div class="setup-part"><h4 class="sheet-part">Review level</h4>
              <div class="field"><label class="field-label" for="review-level">When should work stop for your review?</label><select id="review-level" class="input" name="review.level" aria-describedby="review-level-help"><option value="balanced">Balanced — direction and finished work</option><option value="automatic">Automatic draft — finished work only</option><option value="step_by_step">Step by step — every stage</option></select>
                <p id="review-level-help" class="field-hint quiet">Balanced brings research and the planned direction together for one review, then shows the finished work. Automatic draft continues to the finished draft. Checks, visual review, repairs and spending limits still apply. Publishing is a separate action. New work saves this choice; existing runs keep their review level.</p></div>
            </div>
          </section>
          <section class="card" data-step="1"><h3 class="card-title">Where your work lives</h3><p class="quiet">Keep a Git history on this computer, or share work through a repository.</p>
            <div class="field"><p class="field-label" id="storage-label">Workspace storage</p><div class="segmented" data-count="2" data-at="0" role="radiogroup" aria-labelledby="storage-label"><span class="seg-thumb" aria-hidden="true"></span><label class="seg-option"><input type="radio" name="storage" value="local" checked>Local Git on this computer</label><label class="seg-option"><input type="radio" name="storage" value="remote">Shared repository</label></div></div>
            <div id="local-fields" class="field"><label class="field-label" for="local-root">Work folder</label><input id="local-root" class="input" name="local.root" placeholder="~/Studios"><p class="field-hint quiet">Each studio keeps a local repository inside this folder.</p></div>
            <div id="remote-fields" class="field-grid" hidden>
              <div class="field full"><label class="field-label" for="team-repository">Repository address</label><input id="team-repository" class="input" name="team.repository" placeholder="https://github.com/your-team/studio-work.git" autocomplete="off"><p class="field-hint quiet">Use an existing repository without credentials in its address.</p></div>
              <div class="field"><label class="field-label" for="team-branch">Branch</label><input id="team-branch" class="input" name="team.branch" placeholder="main"></div>
              <div class="field"><label class="field-label" for="share">Share changes</label><select id="share" class="input" name="share"><option value="decision">After each decision</option><option value="asked">When I ask</option></select></div>
            </div>
            <p class="field-hint quiet">Finishing setup prepares installed studios that have no workspace yet. Existing work stays where it is.</p>
          </section>
          <section class="card" data-step="2"><h3 class="card-title">Brand and delivery</h3><p class="quiet">Choose the brand new work starts with. You can change it for each blog, presentation, or training. Existing work keeps its saved choice.</p>
            <h4 class="sheet-part">Where is your brand skill?</h4>
            <div class="bar"><button type="button" id="find-brands" class="button">Find installed brands</button></div>
            <p id="brand-catalog-status" role="status" class="field-hint quiet">Look up brand and variant IDs from installed skills, or enter them below. This does not install anything.</p>
            <div id="brand-choices" hidden></div>
            <p class="field-hint quiet">Give a Git repository address, or choose an installed skill folder. Both are optional. A repository does not need a folder path.</p>
            <div class="field-grid">
              <div class="field"><label class="field-label" for="brand-repository">Git repository <span class="quiet">(optional)</span></label><input id="brand-repository" class="input" name="brand.repository" placeholder="https://github.com/your-team/brand-skill.git" autocomplete="off"><p class="field-hint quiet">Use an HTTPS or SSH Git address. Save it here, then install or update the brand skill from a studio’s settings.</p></div>
              <div class="field"><label class="field-label" for="brand-skill">Installed skill folder <span class="quiet">(optional)</span></label><input id="brand-skill" class="input" name="brand.skill" placeholder="~/path/to/installed-brand-skill" autocomplete="off"><p class="field-hint quiet">For a skill already on this computer. Use an absolute folder path or one beginning with ~/. Leave blank to find installed skills automatically.</p></div>
              <div class="field"><label class="field-label" for="brand-brand">Default brand <span class="quiet">(optional)</span></label><input id="brand-brand" class="input" name="brand.brand" placeholder="For example, tanzu" aria-describedby="brand-default-help"><p id="brand-default-help" class="field-hint quiet">Use a brand name offered by your installed skill. For example, tanzu starts new work with Tanzu branding.</p></div>
              <div class="field"><label class="field-label" for="brand-variant">Default variant <span class="quiet">(optional)</span></label><input id="brand-variant" class="input" name="brand.variant" placeholder="For example, light"><p class="field-hint quiet">Use a variant offered by that brand, such as light or dark. Leave blank to use the brand’s first variant.</p></div>
            </div>
            <details class="setup-more"><summary class="setup-more-label">Brand skill release options</summary>
              <div class="field"><label class="field-label" for="brand-release">Brand skill release <span class="quiet">(optional)</span></label><input id="brand-release" class="input" name="brand.release" placeholder="Newest release"><p class="field-hint quiet">Pin a release tag from the repository, such as v1.4.0, or leave blank for the newest release.</p></div>
            </details>
            <div class="setup-part"><h4 class="sheet-part">Delivery and previews</h4>
              <div class="field-grid">
                <div class="field"><label class="field-label" for="output">Deliver as</label><select id="output" class="input" name="output"><option value="pptx">PowerPoint and Word files</option><option value="google">Google Slides and Docs</option></select></div>
                <div class="field"><label class="field-label" for="render-previews">Slide previews</label><select id="render-previews" class="input" name="render.previews"><option value="">Match delivery format</option><option value="local">Local rendering (LibreOffice)</option><option value="drive">Google Drive</option></select><p class="field-hint quiet">Local rendering needs LibreOffice and image tools; Google Drive needs sign-in. Each studio checks availability.</p></div>
              </div>
            </div>
          </section>
          <p id="prepare-note" class="field-hint quiet" hidden>Finish setup will prepare installed studios with these choices. Your existing workspaces stay in place. For a shared repository, this creates a separate clone for each studio.</p>
          <div class="bar form-actions"><button type="button" id="back" class="button" hidden>Back</button><button type="submit" id="save" class="button button-filled">Save settings</button></div>
        </form>
        <section id="installations" class="card" hidden><h3 class="card-title">Studio installations</h3><p class="quiet">Installed studios and sibling checkouts are found automatically. Set a folder if yours is somewhere else.</p><form id="paths-form"><div id="path-fields" class="field-grid"></div><div class="bar form-actions"><button type="submit" class="button">Save installation folders</button></div></form></section>
      </section>
      <section id="computer" hidden>
        <div class="intro"><h2 class="large-title">This computer</h2><p class="lede">Check the tools available to your studios. Each studio checks sign-in when you use it.</p></div>
        <section class="card"><h3 class="card-title">Tools</h3><ul id="computer-results" class="computer-items"><li class="quiet">Run a check to see what is installed.</li></ul><div class="bar"><button id="check" type="button" class="button button-filled">Check computer</button></div></section>
      </section>
    </main>
  </div>
</div>
<div id="toasts" class="toasts" role="status" aria-live="polite"></div>
</body>
</html>
```

`scripts/ci/shared_setup_acceptance.py:111` requires `name="local.root"` and `name="assistant.model"` in the served page. Both remain.

- [ ] **Step 2: Replace `home.css`**

```css
/* Marketing Studio home and shared setup. The shell, the controls and every colour come
   from style.css. This file lays out what only these pages have: the studio launch cards,
   the setup form's grid and the model profiles. */

.sidebar-foot {
  margin-top: auto;
  padding: 0 0.75rem;
  color: var(--quiet);
  font-size: 0.85rem;
  line-height: 1.6;
}

/* --- studios: one card each, in the colour that studio uses for itself ---------------- */

.studio-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.studio-card {
  --studio-color: var(--blog);
  --studio-wash: var(--blog-wash);
  --accent: var(--studio-color);
  --on-accent: var(--on-studio);
  --link: var(--studio-color);
  --focus: var(--studio-color);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-height: 19rem;
  transition: border-color 180ms ease;
}

.studio-card[data-studio="presentation"] {
  --studio-color: var(--presentation);
  --studio-wash: var(--presentation-wash);
}

.studio-card[data-studio="training"] {
  --studio-color: var(--training);
  --studio-wash: var(--training-wash);
}

.studio-card:hover {
  border-color: var(--studio-color);
}

.studio-icon {
  display: grid;
  place-items: center;
  width: 3.25rem;
  height: 3.25rem;
  background: var(--studio-wash);
  color: var(--studio-color);
  border-radius: 15px;
}

.studio-icon > svg {
  width: 1.6rem;
  height: 1.6rem;
}

.studio-name {
  padding-top: 0.6rem;
  font-size: 1.35rem;
  font-weight: 650;
  letter-spacing: -0.025em;
  line-height: 1.25;
}

.studio-says {
  color: var(--quiet);
  font-size: 0.93rem;
}

.studio-status {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding-bottom: 0.6rem;
  color: var(--quiet);
  font-size: 0.8rem;
}

.studio-status::before {
  content: "";
  flex: none;
  width: 6px;
  height: 6px;
  background: currentColor;
  border-radius: 50%;
}

.studio-status[data-running="true"] {
  color: var(--done);
}

.studio-card > .button {
  width: 100%;
  margin-top: auto;
}

.settings-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem 1.5rem;
}

.settings-summary > * + * {
  margin-top: 0;
}

.settings-summary > div {
  flex: 1 1 20rem;
  min-width: 0;
}

.copy-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
}

.copy-row > .input {
  flex: 1 1 16rem;
  width: auto;
}

/* --- setup: a card for each step, its fields two to a row -------------------------- */

#home > * + *,
#settings > * + *,
#computer > * + *,
.setup-form > * + * {
  margin-top: 1.1rem;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.1rem 1.4rem;
  align-items: start;
}

.field-grid > .full {
  grid-column: 1 / -1;
}

.setup-part {
  padding-top: 1.1rem;
  border-top: 1px solid var(--hair);
}

.setup-more-label {
  display: list-item;
  min-height: 2.75rem;
  font-weight: 600;
  cursor: pointer;
}

.model-heading {
  display: flex;
  flex-wrap: wrap;
  align-items: start;
  justify-content: space-between;
  gap: 1rem 1.5rem;
}

.model-heading > div:first-child {
  flex: 1 1 20rem;
}

.model-catalog-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem 1.2rem;
}

.model-catalog-bar > .field-hint {
  flex: 1 1 18rem;
}

.profile-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.8rem;
}

.profile-card {
  min-width: 0;
  padding: 1rem;
}

.profile-card > * + *,
.profile-explicit > * + * {
  margin-top: 0.8rem;
}

.brand-choice {
  align-items: end;
}

.form-actions {
  justify-content: flex-end;
}

.launch-note {
  font-size: 0.85rem;
}

@media (max-width: 70rem) {
  .studio-list,
  .profile-cards {
    grid-template-columns: 1fr;
  }

  .studio-card {
    display: grid;
    grid-template-columns: 3.25rem minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.25rem 1.2rem;
    min-height: 0;
  }

  .studio-card > * + * {
    margin-top: 0;
  }

  .studio-icon {
    grid-row: 1 / 4;
  }

  .studio-name,
  .studio-says,
  .studio-status {
    grid-column: 2;
    padding: 0;
  }

  .studio-card > .button {
    grid-column: 3;
    grid-row: 1 / 4;
    width: auto;
    margin: 0;
  }
}

@media (max-width: 52rem) {
  .sidebar-foot {
    display: none;
  }
}

@media (max-width: 40rem) {
  .field-grid {
    grid-template-columns: 1fr;
  }

  .studio-card {
    grid-template-columns: 2.5rem minmax(0, 1fr);
  }

  .studio-icon {
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 11px;
  }

  .studio-card > .button {
    grid-column: 1 / -1;
    grid-row: auto;
    width: 100%;
    margin-top: 0.6rem;
  }
}
```

- [ ] **Step 3: Update `app.js`.** Make each change below. Line numbers refer to the current file.

**3a. Messages, the lost connection, and segments** (replace `inform` and `api`, lines 18-30):

```js
const calm = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function inform(message, error = false) {
  if (error) { const node = $('#problem'); node.textContent = message; node.hidden = false; return; }
  // Toasts are timed as they are in every studio; anything with a link stays in #message.
  const node = element('p', message, 'toast glass'); $('#toasts').append(node);
  setTimeout(() => { node.classList.add('toast-leaving'); setTimeout(() => node.remove(), calm() ? 0 : 260); }, 4200);
}
async function api(path, body) {
  let response;
  try {
    response = await fetch(`${standalone ? "/onboarding" : ""}/api/${path}`, { method: body === undefined ? 'GET' : 'POST',
      headers: { [tokenHeader]: token, ...(body === undefined ? {} : {'Content-Type': 'application/json'}) },
      ...(body === undefined ? {} : {body: JSON.stringify(body)}) });
  } catch (error) {
    throw new Error(`This page has lost touch with ${product}, so it cannot read or save anything. Run ${standalone ? 'the studio command' : 'marketing-studio'} again in your terminal and use the new link.`);
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'This request could not be completed.');
  return result;
}
function syncSegments() {
  for (const group of form.querySelectorAll('.segmented')) {
    const options = [...group.querySelectorAll('input[type="radio"]')];
    group.dataset.at = String(Math.max(0, options.findIndex(option => option.checked)));
  }
}
```

`element()` is declared with `function`, so it is hoisted and callable here.

**3b. Focus and announcements** in `show()`:
- Replace `$('#home-link').textContent = product;` with `$('#home-name').textContent = product;`.
- Append these two lines as the last statements of `show()`, after `if (view === 'settings' && …) loadModels();`:

```js
  if (snapshot) (setup ? $('#settings-title') : $('#view-title')).focus({preventScroll: true});
  $('#announce').textContent = setup ? `Step ${step + 1} of 3: ${labels[step]}` : '';
```

**3c. Model pickers** carry the shared class and take over a label that points at their input. Replace the first two lines of `modelPicker`:

```js
function modelPicker(input, title) {
  const select = element('select', '', 'input'); select.setAttribute('aria-label', title);
```

with:

```js
function modelPicker(input, title) {
  const select = element('select', '', 'input');
  const named = input.id ? document.querySelector(`label[for="${input.id}"]`) : null;
  if (named) { select.id = `${input.id}-choice`; named.htmlFor = select.id; } else select.setAttribute('aria-label', title);
```

`element('select', '', 'input')` works because `element(tag, text, className)` skips empty text.

**3d. Model routing through radios.** Replace each use of `$('#model-mode')`:
- Line 129: `$('#model-mode').value !== 'by_task'` becomes `form.elements['models.mode'].value !== 'by_task'`.
- Line 161: `const byTask = $('#model-mode').value === 'by_task';` becomes `const byTask = form.elements['models.mode'].value === 'by_task';`.
- Line 171: `$('#model-mode').value = snapshot.shared.models?.mode || 'single';` becomes `form.elements['models.mode'].value = snapshot.shared.models?.mode || 'single';`.
- Line 189: `$('#model-mode').addEventListener('change', profilesChanged);` becomes `form.querySelectorAll('[name="models.mode"]').forEach(input => input.addEventListener('change', profilesChanged));`.
- Line 250: `mode: $('#model-mode').value,` becomes `mode: form.elements['models.mode'].value,`.

Then append `syncSegments();` as the last statement of `profilesChanged()` and of `storage()`.

Run: `grep -n "model-mode" core/studio_core/setup_web/app.js`
Expected: only `model-mode-label`, if anything.

**3e. Profile cards** on shared fields. Replace the body of the loop in `fillProfiles()` (lines 175-185) with:

```js
    const saved = snapshot.shared.models?.profiles?.[name] || {};
    const title = name[0].toUpperCase() + name.slice(1);
    const card = element('section', '', 'paper profile-card'); card.dataset.profile = name;
    card.append(element('h5', title, 'sheet-part'), element('p', descriptions[name], 'field-hint quiet'));
    const choice = element('div', '', 'field');
    const choiceLabel = element('label', 'Model choice', 'field-label'); choiceLabel.htmlFor = `models-${name}-selection`;
    const selection = element('select', '', 'input'); selection.id = choiceLabel.htmlFor; selection.name = `models.${name}.selection`;
    for (const [value, text] of [['inherit', 'Use shared model above'], ['provider_default', 'Assistant’s default'], ['explicit', 'Choose a model']]) selection.add(new Option(text, value));
    selection.value = saved.selection || 'inherit'; selection.addEventListener('change', profilesChanged);
    choice.append(choiceLabel, selection); card.append(choice);
    const fields = element('div', '', 'profile-explicit');
    const modelField = element('div', '', 'field'), modelLabel = element('label', 'Model', 'field-label');
    const input = element('input', '', 'input'); input.id = modelLabel.htmlFor = `models-${name}-model`;
    input.name = `models.${name}.model`; input.maxLength = 100; input.autocomplete = 'off'; input.value = saved.model || '';
    modelField.append(modelLabel, input);
    const effortField = element('div', '', 'field'), effortLabel = element('label', 'Reasoning', 'field-label');
    const effort = element('select', '', 'input'); effort.id = effortLabel.htmlFor = `models-${name}-effort`; effort.name = `models.${name}.effort`;
    profileLevels(effort, saved.effort, saved.model); effortField.append(effortLabel, effort);
    fields.append(modelField, effortField); card.append(fields); cards.append(card);
    modelPicker(input, `${title} model`);
```

**3f. Studio cards and the standalone symbol.** Immediately after the `drawings` object (line 195), add:

```js
const ownStudio = {'Blog Studio': 'blog', 'Presentation Studio': 'presentation', 'Training Studio': 'training'}[product];
// Standalone setup shows the studio's own symbol, as its sidebar and its home card do.
if (ownStudio) $('#home-symbol').innerHTML = `<svg class="icon" viewBox="0 0 26 28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${drawings[ownStudio]}</svg>`;
```

In `renderHome()`, replace the card construction and button code (lines 199-227) with:

```js
    const card = element('article', '', 'card studio-card');
    card.dataset.studio = studio.id;
    const icon = element('div', '', 'studio-icon'); icon.setAttribute('aria-hidden', 'true');
    // Drawings are static application assets; user and repository text use textContent.
    icon.innerHTML = `<svg viewBox="0 0 26 28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${drawings[studio.id]}</svg>`;
    card.append(icon, element('h3', studio.name, 'studio-name'), element('p', studio.description, 'studio-says'));
    const status = element('p', studio.running ? 'Running' : studio.installed ? `Ready${studio.version ? ` · ${studio.version}` : ''}` : 'Not installed', 'studio-status');
    status.dataset.running = String(studio.running); card.append(status);
    if (studio.installed) {
      const label = studio.running ? `Return to ${studio.name}` : `Open ${studio.name}`;
      const button = element('button', label, 'button button-filled');
      button.addEventListener('click', async () => {
        // Reserve the named tab during the click so popup protection does not lose it.
        const tab = window.open('about:blank', `marketing-${studio.id}`);
        button.disabled = true; button.textContent = 'Opening…'; $('#problem').hidden = true; $('#message').hidden = true;
        try {
          const result = await api('open', {studio: studio.id});
          if (tab) tab.location.href = result.link;
          else {
            const link = element('a', `Open ${studio.name}`); link.href = result.link; link.target = `marketing-${studio.id}`; link.rel = 'noreferrer';
            const message = $('#message'); message.replaceChildren(document.createTextNode('Your browser blocked the new tab. '), link); message.hidden = false;
          }
          snapshot = await api('home'); renderHome();
        } catch (error) { if (tab && tab.location.href === 'about:blank') tab.close(); inform(error.message, true); }
        finally { button.disabled = false; button.textContent = label; }
      }); card.append(button);
    } else {
      const link = element('a', 'Install studio', 'button'); link.href = studio.repository; link.target = '_blank'; link.rel = 'noreferrer'; card.append(link);
    }
```

In the same function:
- Replace `$('.local-badge').textContent = …` with `$('#where').textContent = remote ? 'On your local network' : 'On this computer';`.
- Replace the installation-folder loop (lines 240-243) with:

```js
  for (const studio of snapshot.studios) {
    const field = element('div', '', 'field full');
    const label = element('label', studio.name, 'field-label'); label.htmlFor = `path-${studio.id}`;
    const input = element('input', '', 'input'); input.id = label.htmlFor; input.name = studio.id;
    input.value = studio.configured_path; input.placeholder = studio.path || 'Absolute path to the studio installation';
    field.append(label, input); fields.append(field);
  }
```

**3g. Brand choices** (lines 299-312). Replace the loop body with:

```js
    let index = 0;
    for (const skill of found.skills || []) for (const brand of skill.brands || []) {
      const row = element('div', '', 'field-grid brand-choice'), field = element('div', '', 'field');
      const label = element('label', `${skill.name} · ${brand.name}`, 'field-label');
      const select = element('select', '', 'input'); select.id = label.htmlFor = `brand-choice-${index++}`;
      for (const variant of brand.variants?.length ? brand.variants : ['']) select.add(new Option(variant || 'Default variant', variant));
      const use = element('button', `Use ${brand.name}`, 'button'); use.type = 'button';
      use.addEventListener('click', () => {
        form.elements['brand.skill'].value = skill.path;
        form.elements['brand.brand'].value = brand.brand;
        form.elements['brand.variant'].value = select.value;
        $('#brand-catalog-status').textContent = `${brand.name} selected. Save settings to keep this choice.`;
      });
      field.append(label, select); row.append(field, use); holder.append(row);
    }
```

**3h. The computer check** (lines 324-328). Add a helper after `element()`:

```js
function stateLine(kind, text) {
  const node = element('span', '', 'state'), mark = element('span', '', 'bead');
  mark.dataset.state = kind; mark.setAttribute('aria-hidden', 'true');
  node.append(mark, element('span', text)); return node;
}
```

Then replace the loop in the `#check` handler with:

```js
    for (const item of result.computer.items) {
      const kind = item.ready ? 'done' : item.optional ? 'none' : 'review';
      const row = element('li', '', 'computer-item'), top = element('div', '', 'computer-top');
      top.append(element('h4', item.name, 'row-title'), stateLine(kind, item.ready ? 'Available' : item.optional ? 'Optional' : 'Needs setup'));
      row.append(top, element('p', item.detail, 'facts')); list.append(row);
    }
```

- [ ] **Step 4: Syntax and behaviour checks**

Run: `node --check core/studio_core/setup_web/app.js`
Expected: no output.

Run: `python3 -m unittest tests.test_shared_setup tests.test_ui_consistency -v 2>&1 | tail -20`
Expected:
- `test_browser_finish_loads_native_page_even_when_setup_uses_root` passes, because `openNative` is unchanged.
- The `home.css` and `index.html` cases of the guard pass.

Run: `python3 -m unittest tests.test_home tests.test_suite tests.test_launcher -v 2>&1 | tail -5`
Expected: OK. Inside a sandbox without `/tmp` or local ports, tests that error with `PermissionError` or "Operation not permitted" errored the same way before this change. Record that rather than treating it as a regression.

- [ ] **Step 5: Commit**

```bash
git add core/studio_core/setup_web/index.html core/studio_core/setup_web/home.css core/studio_core/setup_web/app.js
git commit -m "Build Marketing Studio home and shared setup on the shared shell

Setup moves focus to each step and announces it, names studio buttons as
they read, and says plainly when Marketing Studio has stopped.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Blog Studio desk on shared controls

**Files:**
- Modify: `studios/blog/skills/blog-studio/assets/management/index.html:17-75`
- Replace: `studios/blog/skills/blog-studio/assets/management/blog.css`
- Modify: `studios/blog/skills/blog-studio/assets/management/app.js` at lines 73-80, 128, 175, 199, 203, 211, 222, 313, 316, 317 and 427
- Modify: `studios/blog/skills/blog-studio/assets/management/runner.js` at lines 11, 110, 123, 229, 231 and 416
- Modify: `studios/blog/scripts/ci/check-management.cjs` at lines 915-916

- [ ] **Step 1: Editorial screen and dialogs in `index.html`.** Replace lines 17-75, from `<main id="main" …` through the closing `</dialog>` of `import-dialog`, with:

```html
<main id="main" class="page" tabindex="-1"><noscript>This page needs JavaScript. Nothing is loaded from anywhere but this computer.</noscript><div id="studio-page"></div><section id="editorial-screen" hidden><header><div><h2 id="heading" class="editorial-title">Blogs in progress</h2><p id="subtitle" class="quiet">Plan the next handoff. Open a Doc. Keep writing.</p></div><div class="actions"><button id="new-blog" class="button button-filled">＋ New blog</button><button id="refresh-hub" class="button">Refresh Hub</button><button id="upload-open" class="button">Upload</button></div></header>

<section class="access-panel" aria-label="Workspace access">
<div class="access-lines">
<p id="access-status" role="status" aria-live="polite">Checking Hub access…</p>
<p id="analysis-status" class="help" hidden></p>
<p id="desk-identity" class="help" hidden></p>
</div>
<button id="check-access" class="button">Check access</button></section>

<section id="sync-status" class="sync-status" aria-label="Sharing status" aria-live="polite" hidden></section>

<section class="filter-bar" aria-label="Filter results"><label class="field search">Search this view<input id="query" class="input" type="search" placeholder="Title, author, topic…"></label><label id="stage-filter" class="field">Stage<select id="stage" class="input"><option value="">All stages</option><option>idea</option><option>draft</option><option>review</option><option>ready</option><option>published</option></select></label><label id="library-status-filter" class="field" hidden>Status<select id="library-status" class="input"><option value="">All active references</option><option value="ready">Readable</option><option value="pending">Pending extraction</option><option value="unavailable">Unavailable</option><option value="needs-analysis">Needs analysis</option><option value="retired">Retired</option></select></label><label id="library-collection-filter" class="field" hidden>Collection ID<input id="library-collection" class="input" maxlength="200" placeholder="Any collection"></label><button id="search-go" class="button">Search</button><button id="import-open" class="button button-filled" hidden>＋ Import old blogs</button><button id="memory-open" class="button button-filled" hidden>＋ Add memory</button></section>

<section class="card desk-panel"><div class="panel-heading"><h3 id="section-title" class="card-title">Writing pipeline</h3><span id="count"></span></div><p id="loading" role="status" aria-live="polite" hidden></p><div id="results" class="table-wrap" aria-live="polite"></div><footer class="pagination"><button id="previous" class="button">← Previous</button><span id="page-label"></span><button id="next" class="button">Next →</button></footer></section>

<p class="footnote" id="observation">Saved metadata. Google Docs status is checked only when you request it in chat.</p>
</section></main>
</div></div>

<dialog id="detail-dialog" class="dialog"><div class="dialog-header"><h2 id="detail-title">Blog details</h2><button data-close class="button button-quiet button-round" aria-label="Close dialog">×</button></div><div id="detail-content" class="dialog-content"></div></dialog>

<dialog id="upload-dialog" class="dialog"><form id="upload-form" class="dialog-form"><div class="dialog-header"><h2>Bring in your work</h2><button type="button" data-close class="button button-quiet button-round" aria-label="Close dialog">×</button></div><p>Upload a reference, or start an editable blog from a draft. The original stays saved.</p><label class="field">File<input id="upload-file" class="input" type="file" accept=".md,.txt,.html,.htm,.docx,.pdf" required></label><label class="field">Title<input id="upload-title" class="input" maxlength="500" placeholder="Use the filename"></label><label class="field">Author, if known<input id="upload-author" class="input" maxlength="200" placeholder="Leave blank if unknown"></label><label class="field">Use this file as<select id="upload-purpose" class="input"><option value="reference">Factual reference</option><option value="voice-sample">Authored voice sample</option></select></label><label class="check"><input id="upload-blog" type="checkbox">Start an editable blog from this file</label>
<label class="check" id="upload-analyze-field" hidden><input id="upload-analyze" type="checkbox" checked><span id="upload-analyze-label">Summarize and tag with your analysis CLI</span></label>
<p class="help" id="upload-analysis-note" hidden></p>
<p class="help">Markdown, text, HTML and DOCX can supply text. PDF needs extraction in chat.
Files are saved in this workspace and your selected private Hub.
When an analysis CLI is configured and “Summarize and tag” stays checked, text from a readable file
(up to 24,000 characters per file) is also sent through that signed-in CLI to its model provider.</p>
<div class="bar form-actions"><button class="button button-filled" type="submit">Upload and save</button></div></form></dialog>

<dialog id="memory-dialog" class="dialog"><form id="memory-form" class="dialog-form"><div class="dialog-header"><h2 id="memory-title">Add shared memory</h2><button type="button" data-close class="button button-quiet button-round" aria-label="Close dialog">×</button></div><p>Notes and context help the team. A rule governs future writing when selected; existing blog pins stay intact.</p><label class="field">Title<input id="memory-name" class="input" required maxlength="200"></label><label class="field">Kind<select id="memory-kind" class="input"><option value="note">Note</option><option value="context">Context</option><option value="rule">Writing rule</option></select></label><label class="field">Applies to<select id="memory-scope" class="input"><option value="team">Whole team</option><option value="project">Project</option><option value="author">Author</option><option value="article">Blog</option></select></label><label class="field">Scope key (for a project, author or blog)<input id="memory-key" class="input" maxlength="200"></label><label class="field">Memory<textarea id="memory-body" class="input" rows="8" required maxlength="16000"></textarea></label><p class="help" id="memory-truncated" hidden>Only the first 16,000 characters of this memory are shown. Leave the text as it is to keep the rest; a changed text replaces the whole memory.</p><div class="bar form-actions"><button class="button button-filled" type="submit">Save shared memory</button></div></form></dialog>

<dialog id="import-dialog" class="dialog"><div class="dialog-header"><h2>Import old blogs</h2><button id="import-close" data-close class="button button-quiet button-round" aria-label="Close dialog">×</button></div><div class="dialog-content">
<p>Build a collection of past posts your team can find and learn from. Review the preview before importing.</p>
<form id="import-form">
<label class="field">Where are your blogs?<select id="import-type" class="input"><option value="folder">Folder on this computer</option><option value="archive">Website / blog archive</option><option value="feed">RSS or Atom feed</option><option value="export">JSON export</option><option value="sitemap">Sitemap</option><option value="urls">List of post links</option><option value="collection">Refresh an existing collection</option></select></label>
<label id="import-name-field" class="field">Collection name<input id="import-name" class="input" maxlength="200" required placeholder="Our engineering blogs"></label>
<label id="import-folder-field" class="field">Choose a folder<input id="import-folder" class="input" type="file" webkitdirectory multiple><span class="help field-hint" id="import-folder-help">Markdown, text, HTML, DOCX and PDF. Up to 500 files and 10 MiB in total. For larger folders, import in chat.</span></label>
<label id="import-export-field" class="field" hidden>Choose a JSON export<input id="import-export" class="input" type="file" accept=".json,application/json"><span class="help field-hint" id="import-export-help">A list of posts with title, text, and a URL or external_id. Author, dates, topics and products are optional.</span></label>
<label id="import-url-field" class="field" hidden><span id="import-url-label">Website URL</span><input id="import-url" class="input" type="url" placeholder="https://example.com/blog"></label>
<label id="import-links-field" class="field" hidden>Post links, one per line<textarea id="import-links" class="input" rows="4" placeholder="https://example.com/blog/first-post"></textarea></label>
<label id="import-scope-field" class="field" hidden>Only import posts under this URL<input id="import-scope" class="input" type="url" placeholder="https://example.com/blog"><span class="help field-hint">Choose the website and path that contain your team's posts. Other links are excluded.</span></label>
<label id="import-collection-field" class="field" hidden>Collection<select id="import-collection" class="input"></select></label>
<p class="help">Files are saved in this local workspace and your selected private Hub.
Website imports read the public URLs you select. PDFs may need text extraction in chat.
When an analysis CLI is configured and “Summarize and tag” stays checked at import, text from each readable post
(up to 24,000 characters per file) is also sent through that signed-in CLI to its model provider.</p>
<div class="bar form-actions"><button id="import-preview-button" class="button button-filled" type="submit">Preview blogs</button></div>
</form>
<button id="import-new" class="button" hidden>Choose another source</button>
<p id="import-progress" role="status" aria-live="polite" hidden></p>
<section id="import-preview" aria-label="Import preview" hidden></section>
<label class="check" id="import-analyze-field" hidden><input id="import-analyze" type="checkbox" checked><span id="import-analyze-label">Summarize and tag with your analysis CLI</span></label>
<p class="help" id="import-analysis-note" hidden></p>
<div class="import-actions"><button id="import-save" class="button button-filled" hidden>Import first batch</button><button id="import-retry" class="button" hidden>Retry failed posts</button><button id="import-reload" class="button" hidden>Reload saved preview</button></div>
</div></dialog>
```

The hidden `chat-tip` section and the `eyebrow` line are removed. Both were hidden by CSS and referenced by no script.

`#import-url-field` keeps `<span id="import-url-label">` because the script changes that text.

Check with grep that no script looks up the removed `section.toolbar` by its class:

Run: `grep -n "querySelector('.toolbar\|'.toolbar'\|chat-tip\|eyebrow" studios/blog/skills/blog-studio/assets/management/*.js`
Expected: no output.

- [ ] **Step 2: Editorial controls in `app.js`.** Make these exact replacements:

| Line | Old | New |
| --- | --- | --- |
| 75 | `const field=element('textarea');` | `const field=element('textarea',undefined,'input');` |
| 80 | `},'primary');` | `},'button button-filled');` |
| 128 | `function button(text, action, cls='secondary') {` | `function button(text, action, cls='button') {` |
| 175 | `table.className='view-'+view;` | `table.className='table view-'+view;` |
| 199 | `const field=element('label',label),input=element('input');` | `const field=element('label',label,'field'),input=element('input',undefined,'input');` |
| 203 | `const field=element('label','Editorial stage'),select=element('select');` | `const field=element('label','Editorial stage','field'),select=element('select',undefined,'input');` |
| 222 | `save=element('button','Save editorial decision','primary');` | `save=element('button','Save editorial decision','button button-filled');` |
| 222 | `element('div',undefined,'form-actions')` | `element('div',undefined,'bar form-actions')` |
| 313 | `l=element('label','Curation'),select=element('select');` | `l=element('label','Curation','field'),select=element('select',undefined,'input');` |
| 316 | `const field=element('label',label),input=element(key==='note'?'textarea':'input');` | `const field=element('label',label,'field'),input=element(key==='note'?'textarea':'input',undefined,'input');` |
| 317 | `const save=element('button','Save curation','primary');` | `const save=element('button','Save curation','button button-filled');` |
| 317 | `const actions=element('div',undefined,'form-actions');` | `const actions=element('div',undefined,'bar form-actions');` |
| 427 | `element('button','Select all','import-select-control'),clear=element('button','Clear selection','import-select-control')` | `element('button','Select all','button button-quiet import-select-control'),clear=element('button','Clear selection','button button-quiet import-select-control')` |

Line 211 keeps `element('label',undefined,'check')`. A checkbox row is not a field.

Run: `grep -n "'primary'\|'secondary'\|cls='secondary'" studios/blog/skills/blog-studio/assets/management/app.js`
Expected: no output.

- [ ] **Step 3: Start tasks as shared choice cards in `runner.js`.**

Line 229: `const list=sNode('div','task-list');` becomes `const list=sNode('div','pick-cards');`.

Line 231: replace the loop

```js
  for(const [title,description,action] of tasks){const button=sButton(title,action);button.className+=' task-choice';button.append(sNode('span','quiet',description));button.disabled=!access.actions.edit;list.append(button);}return sCard('What would you like to do?',list);
```

with

```js
  for(const [title,description,action] of tasks){const button=sChoice(title,description,action);button.disabled=!access.actions.edit;list.append(button);}return sCard('What would you like to do?',list);
```

Line 416: replace

```js
    const task=(title,detail,action,ready=true)=>{const button=sButton(title,action);button.disabled=!ready;button.append(sNode('span','quiet',detail));button.className+=' task-choice';return button;};
```

with

```js
    const task=(title,detail,action,ready=true)=>{const button=sChoice(title,detail,action);button.disabled=!ready;return button;};
```

The tasks at line 416 are direct children of the "More tools" sheet, with no list container. As choice cards they stack at full width, spaced by the sheet's own rule.

Run: `grep -c "task-list\|task-choice" studios/blog/skills/blog-studio/assets/management/runner.js`
Expected: `0`

Add the helper right after the `sButton` definition (line 11):

```js
function sChoice(title,says,action){const node=sNode('button','pick-card',title);node.type='button';node.append(sNode('span','pick-says',says));node.addEventListener('click',async()=>{try{await action(node);}catch(error){notice(error.message,true);}});return node;}
```

The title is the button's own text, as with Blog Studio's other buttons. `scripts/ci/check-management.cjs` finds a start task by its button text and clicks it. `.pick-card` sets the title weight and `.pick-says` resets its own.

Line 123: in `sNode('a','button button-outlined','Change shared settings')`, replace `'button button-outlined'` with `'button'`. `button-outlined` is defined nowhere.

- [ ] **Step 3b: Blog Studio's home follows the studio home pattern.** Presentation Studio and Training Studio title their home "Home" and greet with a large title that counts what needs the person. They put "New …" and "Review …" in the toolbar and group work as "Needs you" first. Blog Studio titles its toolbar "Blog Studio" and starts straight with cards.

First, let `sButton` make a plain button. Replace the class expression in `sButton` (line 11):

```js
function sButton(label,action,kind='quiet'){const node=sNode('button','button button-'+kind,label);
```

with:

```js
function sButton(label,action,kind='quiet'){const node=sNode('button','button'+(kind?' button-'+kind:''),label);
```

Then replace `sHome` (line 110) with:

```js
function sGreeting(needs){const hour=new Date().getHours(),hello=hour<12?'Good morning.':hour<18?'Good afternoon.':'Good evening.',counted=['Nothing needs','One thing needs','Two things need','Three things need','Four things need','Five things need','Six things need','Seven things need','Eight things need','Nine things need','Ten things need'];return hello+' '+(needs<counted.length?counted[needs]:needs+' things need')+' you'+(needs?'.':' right now.');}
function sHome(){const open=studio.listing.filter(found=>!found.complete),waiting=open.filter(sNeeds),first=waiting[0];sFrame('Home',[sButton('New blog',()=>newBlog(),first?'':'filled'),first?sButton('Review '+first.title,sReview(first),'filled'):null]);sPage(sNode('p','large-title',sGreeting(waiting.length)),sGroup('Needs you',waiting,'card-needs'),sStartTasks(),sGroup('In progress',open.filter(found=>!sNeeds(found))),studio.ordinary.length?sCard('Saved drafts',...studio.ordinary.slice(0,5).map(found=>sAdd(sNode('div','row'),sNode('h3','row-title',found.title),sButton('Continue editing',()=>sRoute('editor',found.id))))):null,sGroup('Finished drafts',studio.listing.filter(found=>found.complete)),sNode('p','foot quiet','Your writing is saved as you work. Google feedback is sent only when you choose Send.'));}
```

`sReview(found)` already returns the click handler. `newBlog()` is the existing New blog entry point.

Update the two home assertions in `studios/blog/scripts/ci/check-management.cjs`, around lines 915-916. The behaviour changed on purpose:

```js
  assert.equal(f.get('title').textContent,'Home');assert.equal(f.get('needs-count').textContent,'1');
  assert.ok(descendants(content).some(e=>e.textContent==='Needs you'));
```

- [ ] **Step 4: Replace `blog.css`**

```css
/* Blog Studio's own layouts on the shared Golden Gate-inspired shell. Controls, dialogs,
   steps, choice cards, tables and every colour come from style.css. */
.studio-hidden-controls{display:none}
.studio-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(12rem,1fr));gap:1rem}
.blog-search{max-width:28rem}
.wizard-foot{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}
.source-choices{display:grid;gap:.5rem;max-height:20rem;overflow:auto}
.source-choice{display:flex;gap:.7rem;align-items:flex-start;padding:.7rem;border:1px solid var(--hair);border-radius:12px;background:var(--paper)}
.source-choice input{width:1.2rem;height:1.2rem;flex:none;margin-top:.2rem}
.stage-link{background:none;border:0;color:inherit;font:inherit;padding:0;text-align:left;cursor:pointer}
.stage-link:disabled{cursor:default}.file-actions{flex-wrap:wrap}
.review-compare{overflow:auto;max-height:65vh;font:.88rem/1.6 var(--typed);padding:1rem;white-space:pre-wrap;overflow-wrap:anywhere}
.diff-add{color:var(--done)}.diff-remove{color:var(--late)}
.decision-notice{padding:1rem;border:1px solid var(--yours);border-radius:10px;background:var(--yours-wash)}
.sheet .input{max-width:none}.sheet-error{color:var(--late)}
.empty-invite{max-width:46rem}.blog-facts{display:flex;gap:.6rem;flex-wrap:wrap;color:var(--quiet);font-size:.9rem}
.studio-loading{padding:2rem;color:var(--quiet)}
#studio-page>*+*{margin-top:1.1rem}
/* The reference library and team tools keep their existing operations in the same shell. */
#editorial-screen>header{display:flex;justify-content:space-between;align-items:start;gap:1rem;margin-bottom:1rem}
.editorial-title{font-size:1.4rem;font-weight:650}
#editorial-screen .actions,.filter-bar,.access-panel,.access-lines{display:flex;gap:.7rem;flex-wrap:wrap}
.filter-bar{align-items:end;margin:1rem 0}
.filter-bar .search{flex:1;min-width:12rem}
.access-panel{padding:1rem 0;justify-content:space-between;border-bottom:1px solid var(--hair)}
.access-lines{flex-direction:column;max-width:70ch}
.desk-panel{overflow:hidden}
.panel-heading,.pagination{display:flex;justify-content:space-between;gap:1rem;align-items:center}
.pagination{padding-top:.8rem}
#editorial-screen td p{font-size:.9rem;color:var(--quiet);margin-top:.3rem}
.title-button{background:none;border:0;color:var(--link);font:inherit;font-weight:650;text-align:left;cursor:pointer;padding:.3rem 0}
.help,.footnote{font-size:.9rem;color:var(--quiet)}.empty{padding:2.5rem;text-align:center}
.context-note,.dialog-notice,.sync-status{padding:1rem;border:1px solid var(--hair);background:var(--solid);border-radius:10px;margin:.7rem 0}
.error,.problem{color:var(--late)}.table-wrap{overflow:auto}
#editorial-screen .badge{display:inline-block;background:var(--well);color:var(--ink);white-space:normal}
.check{display:flex;gap:.7rem;align-items:center;font-weight:400}.check input{width:auto}
.source-excerpt,.manuscript-preview{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--paper);padding:1rem;border-radius:12px;max-height:28rem;overflow:auto;font:.9rem/1.6 var(--typed)}
.continuation{margin:1rem 0}
.detail-list,.import-post-list{padding:0;list-style:none}.detail-list li,.import-post-list li{padding:.8rem 0;border-bottom:1px solid var(--hair)}
.import-post-list label{display:flex;align-items:start;gap:.7rem}.import-post-list input{width:auto}.import-post-list a{display:block}
.import-selection-tools,.import-actions{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;margin:1rem 0}
@media(min-width:1100px){.gate{grid-template-columns:minmax(0,1fr) 18rem}}
@media(max-width:600px){#editorial-screen>header{flex-wrap:wrap}#editorial-screen .actions{width:100%}.wizard-foot>*{flex:1}.pagination{flex-wrap:wrap}}

.manuscript-input { width:100%; min-height:22rem; resize:vertical; font:inherit; line-height:1.6; box-sizing:border-box; }
.manuscript-original { white-space:pre-wrap; overflow-wrap:anywhere; max-height:24rem; overflow:auto; }
.editor-suggestions { display:grid; gap:1rem; }

/* Task-first writing: quiet reading surfaces, one next action per step. */
.workflow-next{border-top:1px solid var(--hair);padding-top:1rem;display:flex;justify-content:flex-end}
.writing-changes{background:var(--paper);border:1px solid var(--hair);border-radius:12px;overflow:hidden}
.writing-change{padding:1.2rem;border-bottom:1px solid var(--hair);overflow-wrap:anywhere}
.writing-change:last-child{border-bottom:0}
.change-select{display:flex;align-items:center;gap:.65rem;font-weight:650;min-height:44px;margin-bottom:.5rem}
.change-select input{width:1.25rem;height:1.25rem;flex:none}
.change-caption{font-size:.8rem;color:var(--quiet);margin:.8rem 0 .3rem}
.change-before{margin:0;padding:.5rem .8rem;border-left:3px solid var(--hair);white-space:pre-wrap}
.change-after{padding:.65rem .8rem;background:var(--selection);border-radius:6px;white-space:pre-wrap}
.change-reason{margin-top:.75rem;font-size:.95rem}
.finish-summary{padding-left:1.25rem}.finish-summary li{padding:.5rem 0;border-bottom:1px solid var(--hair);overflow-wrap:anywhere}
@media(max-width:600px){.workflow-next .button{width:100%}.writing-change{padding:1rem}}
.finish-selection{display:grid;gap:.8rem}.finish-change{padding:.8rem 0;border-bottom:1px solid var(--hair);overflow-wrap:anywhere}
.writing-change details{margin-top:.8rem}.finish-change:last-child{border-bottom:0}

/* The existing toolbar owns the review action, even while reading a long list. */
.review-continue{white-space:normal}
.review-selection{justify-content:flex-end;gap:.3rem .65rem}
.review-selection>p{margin-right:auto}
.writing-change[data-selected=false]{background:var(--solid)}
.writing-change[data-selected=false] .change-select{color:var(--quiet)}
.polish-intake #draft-content{min-height:12rem;resize:vertical}
@media(max-width:600px){
  #studio-toolbar[data-workflow=review] .toolbar-actions{flex-basis:100%;width:100%}
  #studio-toolbar[data-workflow=review] .review-continue{width:100%;min-height:44px}
  .review-selection .button{padding-inline:.65rem}
  .polish-intake>.button-filled{width:100%}
  .polish-intake .seg-option{padding-inline:.45rem;white-space:normal}
}
@media(max-width:360px){
  .review-selection{display:grid;grid-template-columns:1fr 1fr}
  .review-selection>p{grid-column:1/-1;margin:0}
}

.sheet-heading{position:sticky;top:0;z-index:1;display:flex;align-items:center;justify-content:space-between;gap:1rem;background:var(--paper);border-bottom:1px solid var(--hair);padding-bottom:.75rem}
.sheet-heading .sheet-title{margin:0;min-width:0;overflow-wrap:anywhere}
.sheet-heading .button{flex-shrink:0}
```

The narrow-screen table rules are gone. With `class="table"`, the editorial table takes the kit's own phone layout: cells stack with their `data-label`, at 52rem like every other table. Blog Studio's summary keeps the shared large-title size.

The old `blog.css` still has rules this replacement drops; copy any that apply. The dropped sets are:
- **Dead or unused:** `.mode-grid`/`.mode-choice*` (unused) and `.chat-tip`.
- **Moved to `ui-kit`:** the workflow steps, dialog and backdrop rules, `.primary/.secondary` and `.close`.
- **Replaced by the card:** `.task-list`/`.task-choice*`.
- **Replaced by `.table`:** the editorial `table`/`th`/`td` appearance rules.
- **Bare elements:** `button:disabled`, `a`.

Compare first:

Run: `git show HEAD:studios/blog/skills/blog-studio/assets/management/blog.css | tr '}' '\n' | grep -o '^[^{]*' | sort -u > /tmp/blog-before.txt; tr '}' '\n' < studios/blog/skills/blog-studio/assets/management/blog.css | grep -o '^[^{]*' | sort -u > /tmp/blog-after.txt; comm -23 /tmp/blog-before.txt /tmp/blog-after.txt`

Expected: only selectors from the dropped sets above. In a sandbox, use `$TMPDIR` instead of `/tmp`.

- [ ] **Step 5: Run Blog Studio's page checks and the guard**

Run: `node --check studios/blog/skills/blog-studio/assets/management/app.js && node --check studios/blog/skills/blog-studio/assets/management/runner.js`
Expected: no output.

Run: `(cd studios/blog && node scripts/ci/check-management.cjs > /dev/null && echo management-ok)`
Expected: `management-ok`. One kind of failure points at test code: an assertion that reads `className` and expects `'primary'` or `'secondary'`. In that case, update the assertion to the new shared class. Shared classes are this change's intent.

Run: `python3 -m unittest tests.test_ui_consistency -v 2>&1 | grep -E "blog|FAIL|OK"`
Expected: no Blog Studio failures remain.

- [ ] **Step 6: Commit**

```bash
git add studios/blog/skills/blog-studio/assets/management/
git commit -m "Move Blog Studio editorial screens and dialogs onto shared controls

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Blog Studio beginner page

**Files:**
- Modify: `studios/blog/preview/blog-studio.html`
- Modify: `studios/blog/docs/development.md:31-38`

- [ ] **Step 1: Replace everything from `<head>` through `<footer>…</footer>`** with the version below. Keep the `<script>` contents except the four edits in Step 2.

```html
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="color-scheme" content="light dark"><title>Blog Studio — Workflow Preview</title>
<link rel="stylesheet" href="../skills/blog-studio/assets/management/style.css">
<style>
.beginner-layout{display:grid;grid-template-columns:minmax(0,1fr) 19rem;gap:1.2rem;align-items:start}
.panel-title{font-size:1.25rem;font-weight:650;letter-spacing:-.015em}
.pick-number{color:var(--quiet);font-size:.85rem;font-variant-numeric:tabular-nums}
.plan{margin:0}.plan dt{margin-top:1rem;color:var(--quiet);font-size:.78rem;font-weight:650;letter-spacing:.06em;text-transform:uppercase}.plan dd{margin:.2rem 0 0}
.prompt{white-space:pre-wrap;padding:1rem 1.2rem;font:inherit;font-size:.93rem}
.beginner-actions{justify-content:space-between}
.beginner-foot{max-width:76rem;margin:2rem auto 0;font-size:.85rem}
#panel>*+*{margin-top:.9rem}
@media(max-width:52rem){.beginner-layout{grid-template-columns:1fr}}
</style></head><body data-product="Blog Studio">
<div class="backdrop" aria-hidden="true"></div>
<div class="content">
<div class="toolbar-wrap"><header class="toolbar glass"><div class="toolbar-lead"><span class="studio-symbol" aria-hidden="true"><svg class="icon" viewBox="0 0 24 24"><path d="M5 3h10l4 4v14H5z"/><path d="M14 3v5h5"/><path d="M8 12h8"/><path d="M8 16h6"/></svg></span></div><div class="toolbar-title"><p class="above">A writing partner, at your pace</p><p class="title">Blog Studio</p></div></header></div>
<main class="page">
<div class="intro"><p class="card-title">Your ideas. Your voice.</p><h1 class="large-title">Start where you are.</h1><p class="lede">Bring a rough idea, a stack of notes, or something you've already written. We'll choose the next useful step together.</p></div>
<div class="beginner-layout"><section class="card"><ol class="workflow-steps" aria-label="Steps"><li class="workflow-step step" aria-current="step">01 · Start</li><li class="workflow-step step">02 · Material</li><li class="workflow-step step">03 · Voice</li><li class="workflow-step step">04 · Next step</li></ol><div id="panel"></div><div class="bar beginner-actions"><button class="button" id="back" hidden>Back</button><button class="button button-filled" id="next" disabled>Continue →</button></div></section>
<aside class="card"><h2 class="card-title">Your plan</h2><dl class="plan"><dt>Starting point</dt><dd id="plan-mode">Choose what you need today.</dd><dt>Material</dt><dd id="plan-material">Optional: attachments, notes, or links.</dd><dt>Voice</dt><dd id="plan-voice">Choose or learn a voice.</dd><dt>We'll stop at</dt><dd id="plan-stop">Your chosen outcome.</dd></dl><p class="field-hint quiet">Your real work can be saved in an article workspace and reopened in another chat. This preview stays in this browser tab.</p></aside></div></main>
<p class="quiet beginner-foot">Interactive workflow preview. It does not read links, upload files, generate an article, or save a real profile. Copy your choices into chat to start the actual skill.</p>
</div>
```

The page's body script stays the only inline `<script>`, so `check-newcomer.cjs`, which runs the first `<script>…</script>`, still finds it.

- [ ] **Step 2: Four edits inside the `<script>`**

1. In `cards()`, replace the template so each option is a shared choice card:

```js
function cards(items,key){return '<div class="pick-cards">'+items.map((m,i)=>`<button type="button" class="pick-card" data-key="${key}" data-value="${m[0]}" aria-pressed="${state[key]===m[0]}"><span class="pick-top"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5.5 12.5 10 17l8.5-10"/></svg><span class="pick-number">${String(i+1).padStart(2,'0')}</span></span><span class="pick-title">${esc(m[1])}</span><span class="pick-says">${esc(m[2])}</span></button>`).join('')+'</div>'}
```

2. In `input()`, use shared fields:

```js
function input(id,label,placeholder,area=false){return `<div class="field"><label class="field-label" for="${id}">${label}</label>${area?`<textarea class="input" id="${id}" placeholder="${placeholder}">${esc(state[id])}</textarea>`:`<input class="input" type="text" id="${id}" placeholder="${placeholder}" value="${esc(state[id])}">`}</div>`}
```

3. In `render()`, mark the current step for assistive technology instead of toggling a class: replace `document.querySelectorAll('.step').forEach((e,i)=>e.classList.toggle('active',i===state.step));` with `document.querySelectorAll('.step').forEach((e,i)=>{if(i===state.step)e.setAttribute('aria-current','step');else e.removeAttribute('aria-current')});`.

4. In `render()`, update the panel markup:
- Every `'<h2>` becomes `'<h2 class="panel-title">`.
- Every `<p class="note">` becomes `<p class="field-hint quiet">`.
- `<div class="prompt" id="prompt">` becomes `<pre class="paper prompt" id="prompt">`, and its closing `</div>` becomes `</pre>`.
- `<button class="primary" id="copy" style="margin-top:18px">Copy starting request</button>` becomes `<div class="bar"><button type="button" class="button button-filled" id="copy">Copy starting request</button></div>`.
- The copy status paragraph after it gets `class="quiet" role="status"` in place of `class="status"`.

Run: `grep -c 'class="choice\|class="note"\|class="primary\|class="secondary\|class="status"\|Georgia' studios/blog/preview/blog-studio.html`
Expected: `0`

- [ ] **Step 3: Serve the page from the Blog Studio root** in `studios/blog/docs/development.md`. Replace:

````markdown
```sh
python3 -m http.server 8896 --bind 127.0.0.1 --directory preview
```

Visit `http://127.0.0.1:8896/blog-studio.html`.
````

with:

````markdown
```sh
python3 -m http.server 8896 --bind 127.0.0.1
```

Run it from this directory, so the page can reach the shared stylesheet, and visit
`http://127.0.0.1:8896/preview/blog-studio.html`.
````

- [ ] **Step 4: Run the checks**

Run: `(cd studios/blog && node scripts/ci/check-newcomer.cjs > /dev/null && echo newcomer-ok)`
Expected: `newcomer-ok`

Run: `python3 -m unittest tests.test_ui_consistency.SharedLookTests.test_static_pages_use_the_kit -v 2>&1 | grep blog-studio`
Expected: no `blog-studio.html` failure.

- [ ] **Step 5: Commit**

```bash
git add studios/blog/preview/blog-studio.html studios/blog/docs/development.md
git commit -m "Give the Blog Studio beginner page the shared look

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7A: A way back to Marketing Studio

**Files:**
- Create: `tests/test_suite_link.py`
- Modify: `core/studio_core/setup_web/app.js`
- Modify: `ui-kit/style.css`
- Modify: `studios/blog/skills/blog-studio/assets/management/index.html`, `app.js`, `runner.js`
- Modify: `studios/presentation/skills/presentation-studio/scripts/desk/index.html`, `app.js`
- Modify: `studios/training/skills/training-studio/scripts/desk/index.html`, `app.js`

Marketing Studio opens each studio in a tab of its own (`window.open('about:blank', 'marketing-<id>')`), so the studio tab's opener is the Marketing Studio tab. None of the servers sends `Cross-Origin-Opener-Policy`, so a link in the studio that targets the window named `marketing-studio` brings that tab forward. It reloads at its own address, and its key is already in its `sessionStorage`.

- [ ] **Step 1: Write the failing test** `tests/test_suite_link.py`:

```python
"""Each studio offers a way back to the Marketing Studio tab that opened it.

Marketing Studio adds its own address to the link of a studio it opens. The studio accepts
it only for the same scheme and host on another port, and then shows a link that targets
the Marketing Studio tab by name.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'core/studio_core/setup_web/app.js'
STUDIOS = (
    ROOT / 'studios/blog/skills/blog-studio/assets/management',
    ROOT / 'studios/presentation/skills/presentation-studio/scripts/desk',
    ROOT / 'studios/training/skills/training-studio/scripts/desk',
)
HERE = {'protocol': 'http:', 'hostname': '127.0.0.1', 'port': '8791'}
CASES = [
    ('#token=abc&home=http%3A%2F%2F127.0.0.1%3A8790', 'http://127.0.0.1:8790'),
    ('#abc&home=http%3A%2F%2F127.0.0.1%3A8790', 'http://127.0.0.1:8790'),
    ('#token=abc', ''),
    ('', ''),
    ('#token=abc&home=http%3A%2F%2Felsewhere.example%3A8790', ''),
    ('#token=abc&home=https%3A%2F%2F127.0.0.1%3A8790', ''),
    ('#token=abc&home=http%3A%2F%2F127.0.0.1%3A8791', ''),
    ('#token=abc&home=http%3A%2F%2F127.0.0.1%3A8790%2Fapi', ''),
    ('#token=abc&home=javascript%3Aalert(1)', ''),
]
LINK = ('<a id="go-suite" class="nav-item suite-link" target="marketing-studio" hidden>'
        '<span class="nav-label">Marketing Studio</span></a>')


def function(source: str, name: str) -> str:
    found = re.search(r'function ' + name + r'\([^)]*\) \{[\s\S]*?\n\}', source)
    if not found:
        raise AssertionError(name + ' is not defined as a top-level function')
    return found.group(0)


@unittest.skipUnless(shutil.which('node'), 'needs Node.js')
class SuiteLinkTests(unittest.TestCase):
    def evaluate(self, source: str, expression: str):
        done = subprocess.run(['node', '-e', source + '\nprocess.stdout.write(JSON.stringify('
                               + expression + '));'], capture_output=True, text=True, timeout=10)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_studios_accept_only_marketing_studio_on_the_same_host(self):
        for folder in STUDIOS:
            with self.subTest(studio=folder.relative_to(ROOT).as_posix()):
                source = function((folder / 'app.js').read_text(), 'suiteHome')
                found = self.evaluate(source, json.dumps([hash for hash, _ in CASES])
                                      + '.map((hash) => suiteHome(hash, ' + json.dumps(HERE) + '))')
                self.assertEqual(found, [wanted for _, wanted in CASES])

    def test_marketing_studio_names_itself_in_studio_links(self):
        text = HOME.read_text()
        self.assertIn("if (!standalone) window.name = 'marketing-studio';", text)
        source = 'const location = {origin: "http://127.0.0.1:8790"};\n' + function(text, 'withHome')
        found = self.evaluate(source, '[withHome("http://127.0.0.1:8791/#token=abc"), '
                                      'withHome("http://127.0.0.1:8792/#abc")]')
        self.assertEqual(found, ['http://127.0.0.1:8791/#token=abc&home=http%3A%2F%2F127.0.0.1%3A8790',
                                 'http://127.0.0.1:8792/#abc&home=http%3A%2F%2F127.0.0.1%3A8790'])

    def test_studio_pages_hold_a_hidden_link_back(self):
        for folder in STUDIOS:
            with self.subTest(studio=folder.relative_to(ROOT).as_posix()):
                self.assertIn(LINK, (folder / 'index.html').read_text())


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run it and confirm it fails.** `python3 -m unittest tests.test_suite_link -v` fails because `suiteHome`, `withHome`, `window.name` and the link are missing.

- [ ] **Step 3: Marketing Studio names itself** (`core/studio_core/setup_web/app.js`).
  - After the line `const token = tokenInLink || sessionStorage.getItem(sessionKey) || '';`, add:

```js
// Studios opened from here link back to this tab by its name.
if (!standalone) window.name = 'marketing-studio';
function withHome(link) {
  return link + (link.includes('#') ? '&' : '#') + 'home=' + encodeURIComponent(location.origin);
}
```

  - In the studio button's click handler, `if (tab) tab.location.href = result.link;` becomes `if (tab) tab.location.href = withHome(result.link);`. In the blocked-tab fallback, `link.href = result.link;` becomes `link.href = withHome(result.link);`.
  - In the startup function at the end of the file, before `snapshot = await api('home')`, add a check for a tab opened without its key:

```js
  if (!token) { $('#loading').hidden = true; inform(`This page needs its private link. Run ${standalone ? 'the studio command' : 'marketing-studio'} in your terminal to open it again.`, true); return; }
```

- [ ] **Step 4: The link's place in the shell** (`ui-kit/style.css`). Add to the shared components section:

```css
/* The way back to Marketing Studio, shown only when Marketing Studio opened this studio. */
.suite-link {
  margin-top: auto;
  color: inherit;
  text-decoration: none;
}

@media (max-width: 52rem) {
  .suite-link {
    margin-top: 0;
  }
}
```

- [ ] **Step 5: The link in each studio page.** In each of the three `index.html` files, add this as the last child of the sidebar `<nav>`, after the `go-settings` button:

```html
<a id="go-suite" class="nav-item suite-link" target="marketing-studio" hidden><span class="nav-label">Marketing Studio</span></a>
```

- [ ] **Step 6: Presentation Studio and Training Studio** (`scripts/desk/app.js` in each).
  - Add the same entry to `ICONS`, after `settings`: `suite: ['M4 4h6v6H4z', 'M14 4h6v6h-6z', 'M4 14h6v6H4z', 'M14 14h6v6h-6z'],`. This is the Marketing Studio "Studios" drawing.
  - Add this function just above `function linkToken()`:

```js
// Marketing Studio names its own address when it opens this studio, so the page can link back
// to that tab. Only the same scheme and host on another port is accepted.
function suiteHome(hash, here) {
  const named = new URLSearchParams(String(hash).replace(/^#/, '')).get('home') || '';
  const found = /^(https?:)\/\/([^/:?#@\s]+):(\d{1,5})\/?$/.exec(named);
  return found && found[1] === here.protocol && found[2] === here.hostname && found[3] !== here.port
    ? found[1] + '//' + found[2] + ':' + found[3] : '';
}
```

  - In `begin()`, after the `for (const [id, screen, drawing] of NAV) { … }` loop, add:

```js
  const suite = byId('go-suite');
  const home = suiteHome(window.location.hash, window.location);
  if (suite && home) {
    suite.href = home + '/';
    suite.prepend(icon('suite'));
    suite.hidden = false;
  }
```

  These desks keep their link's fragment in the address, so a reload still has `home`.

- [ ] **Step 7: Blog Studio.** Blog Studio removes the fragment after reading it, so it keeps the address for the tab in `sessionStorage`.
  - In `assets/management/app.js`, replace lines 3-4:

```js
const token = location.hash.slice(1) || sessionStorage.getItem('blog-studio-session') || '';
if(token)sessionStorage.setItem('blog-studio-session',token);
```

    with:

```js
// Marketing Studio names its own address when it opens this studio, so the page can link back
// to that tab. Only the same scheme and host on another port is accepted.
function suiteHome(hash, here) {
  const named = new URLSearchParams(String(hash).replace(/^#/, '')).get('home') || '';
  const found = /^(https?:)\/\/([^/:?#@\s]+):(\d{1,5})\/?$/.exec(named);
  return found && found[1] === here.protocol && found[2] === here.hostname && found[3] !== here.port
    ? found[1] + '//' + found[2] + ':' + found[3] : '';
}
const token = location.hash.slice(1).split('&')[0] || sessionStorage.getItem('blog-studio-session') || '';
const suite = suiteHome(location.hash, location) || sessionStorage.getItem('marketing-studio-home') || '';
if(token)sessionStorage.setItem('blog-studio-session',token);
if(suite)sessionStorage.setItem('marketing-studio-home',suite);
```

  - In `assets/management/runner.js`, after the line `STUDIO_ICONS.studio=['M5 3h10l4 4v14H5z','M14 3v5h5','M8 12h8','M8 16h6'];`, add:

```js
STUDIO_ICONS.suite=['M4 4h6v6H4z','M14 4h6v6h-6z','M4 14h6v6H4z','M14 14h6v6h-6z'];
{const back=$('go-suite');if(back&&suite){back.href=suite+'/';back.prepend(sIcon('suite'));back.hidden=false;}}
```

- [ ] **Step 8: Run the checks**

Run: `python3 -m unittest tests.test_suite_link tests.test_shared_setup tests.test_ui_consistency -v 2>&1 | grep -E "ok$|FAIL|ERROR|^Ran"`
Expected: `test_suite_link` passes. `test_shared_setup` passes; `openNative` is unchanged.

Run: `for f in core/studio_core/setup_web/app.js studios/*/skills/*/assets/management/*.js studios/*/skills/*/scripts/desk/app.js; do node --check "$f" || echo "FAILED $f"; done`
Expected: no `FAILED`.

Run: `(cd studios/blog && node scripts/ci/check-management.cjs >/dev/null && echo blog-ok); (cd studios/presentation && python3 scripts/ci/run_tests.py test_desk test_page_app) 2>&1 | tail -2; (cd studios/training && python3 scripts/ci/run_tests.py test_desk) 2>&1 | tail -2`
Expected: `blog-ok` and OK, apart from socket tests that the sandbox cannot run.

- [ ] **Step 9: Commit**

```bash
git add tests/test_suite_link.py core/studio_core/setup_web/app.js ui-kit/style.css studios/blog/skills/blog-studio/assets/management studios/presentation/skills/presentation-studio/scripts/desk studios/training/skills/training-studio/scripts/desk
git commit -m "Offer a way back to Marketing Studio from each studio it opens

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Design documents

**Files:**
- Modify: `docs/design/unified-settings-preview.html`
- Modify: `docs/design/golden-gate.md`
- Replace: `docs/design/unified-settings-home.jpg`, `docs/design/unified-settings-models.jpg`, `docs/design/golden-gate-presentation.jpg`

- [ ] **Step 1: Link the shared stylesheet in the design preview.** In `<head>`, before its `<style>`, add `<link rel="stylesheet" href="../../ui-kit/style.css">`.

- [ ] **Step 2: Map its classes to shared components.** The preview is a single file whose script builds every screen. Change these class names, both in the HTML and in the script's template strings:

| Preview class | Shared class |
| --- | --- |
| `topbar` | `toolbar glass` (wrapped in `<div class="toolbar-wrap">`) |
| the sidebar container | `sidebar glass`, inside a `window` grid with a `content` column and a `page` main |
| `primary` | `button button-filled` |
| `secondary`, `quiet-button` | `button` and `button button-quiet` |
| `panel` | `card` |
| `field` (label with control) | `field` with `field-label` and `input` |
| `pill`, `status-dot` | `tag`, and `state` with a `bead` |
| `switch` | `segmented` with `seg-option` radios, as in Task 5 |
| `setup-steps` | `workflow-steps` with `workflow-step` items |
| `toast` | `toast glass` inside a `toasts` region |
| `heading`, `eyeline` | `large-title` and `lede` |

Also add `<div class="backdrop" aria-hidden="true"></div>` at the start of `<body>`.

- [ ] **Step 3: Reduce the preview's `<style>` to layout.** Delete its own tokens, colours and control rules. Keep grid and flex placement for preview-only parts, such as the studio grid, scope tabs, connection rows and the home facts.

Run: `python3 -m unittest tests.test_ui_consistency.SharedLookTests.test_static_pages_use_the_kit -v`
Expected: PASS. Each remaining failure names one selector and the drawn properties; move that property into a shared class, or delete it.

- [ ] **Step 4: Open the preview in a browser** at a desktop width and at 390 px, in light and dark appearance. Confirm the following, and fix any broken layout before continuing:
- the sidebar becomes the bottom bar at 390 px;
- forms are opaque;
- the "Design preview" note is still visible.

- [ ] **Step 5: Document the inventory in `docs/design/golden-gate.md`.** Append:

```markdown
## Shared components and page stylesheets

`ui-kit/style.css` holds every token, the shell and the controls used by Marketing Studio,
shared setup, Blog Studio, Presentation Studio and Training Studio:

| Need | Component |
| --- | --- |
| Shell | `.backdrop`, `.window`, `.sidebar.glass`, `.content`, `.toolbar-wrap`, `.toolbar.glass`, `.page` |
| Actions | `.button`, `.button-filled`, `.button-quiet`, `.button-danger`, `.button-round` |
| Fields | `.field`, `.field-label`, `.input`, `.field-hint`, `label.field`, `.input-typed` |
| Exclusive choices | `.segmented` with buttons or radio `label.seg-option` |
| Independent choices | `.chips`, `.chip` |
| Object choices | `.pick-cards`, `.pick-card`, `.pick-title`, `.pick-says` |
| Steps | `.workflow-steps`, `.workflow-step` |
| Surfaces | `.card`, `.paper`, `.table`, `.callout` |
| Headings | `.large-title`, `.lede`, `.card-title`, `.sheet-part` |
| Status | `.state` with `.bead`, `.tag`, `.toasts`/`.toast`, `.notice` |
| Transient | `.sheet`, `.dialog`, `.menu` |

A page stylesheet (`home.css`, `blog.css`, `deck.css`, or an inline style on a static page)
lays out its own parts. It may size and place a shared control, but never draws one, never
styles bare controls or headings for the whole page, and takes every colour from a token.
`tests/test_ui_consistency.py` enforces this.

![Marketing Studio home](unified-settings-home.jpg)
![Shared settings, models](unified-settings-models.jpg)
![Presentation Studio](golden-gate-presentation.jpg)
```

- [ ] **Step 6: Regenerate the three screenshots.** Use synthetic data only. Take each at 1440×900 in light appearance:
- `unified-settings-home.jpg`: the Marketing Studio home with three studios.
- `unified-settings-models.jpg`: shared settings with "By task" selected.
- `golden-gate-presentation.jpg`: a Presentation Studio deck at a review gate.

Use the scratch preview harness from the review session if it is available. Otherwise use the disposable acceptance setup in `scripts/ci/native_launch_acceptance.py` with `HOME`, `STUDIOS_CONFIG` and each `*_STUDIO_DATA` pointing at a temporary folder. Never use the real settings file or real workspaces.

- [ ] **Step 7: Commit**

```bash
git add docs/design/
git commit -m "Rebuild the settings design preview on the shared look and document it

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Verify the whole change

- [ ] **Step 1: Guard and root suite**

Run: `python3 -m unittest tests.test_ui_consistency tests.test_suite_link -v`
Expected: all tests PASS.

Run: `python3 -m unittest discover -s tests -t . 2>&1 | tail -15`
Expected: OK. If a test fails or errors, check whether it failed the same way at the base commit (`git stash` is not used; check out the base in a scratch worktree). Record only those as sandbox limits.

- [ ] **Step 2: Native suites**

Run: `(cd studios/presentation && python3 scripts/ci/run_tests.py) 2>&1 | tail -3`
Run: `(cd studios/training && python3 scripts/ci/run_tests.py) 2>&1 | tail -3`
Run: `(cd studios/blog && python3 scripts/ci/run_tests.py && node scripts/ci/check-management.cjs >/dev/null && node scripts/ci/check-newcomer.cjs >/dev/null && echo blog-ok) 2>&1 | tail -3`
Expected: OK in each, apart from limits recorded in Step 1.

- [ ] **Step 3: Visual check of every page.** Use synthetic data at 1440×900 and 390×844, in light and dark appearance. Cover:
- Marketing Studio home, first-run setup (each step) and "This computer";
- standalone setup for one studio, which shows that studio's symbol and colour;
- a studio opened from Marketing Studio, whose "Marketing Studio" item brings the home tab forward, and the same studio opened on its own, which shows no such item;
- Blog Studio Home, a run's review step, the editorial board and the upload dialog;
- Presentation Studio Home and a deck at its review gate, including the storyboard;
- Training Studio Home, the new-training form with material chips, and a gate;
- the Blog Studio beginner page and the design preview.

For each, confirm the checklist below. Fix anything that differs.

  - The same sidebar (bottom bar at 390 px) and toolbar material.
  - The same button, field, card and heading treatment.
  - Only the accent colour changes between products.
  - Focus rings are visible.
  - No horizontal page scroll.
  - Long paths wrap.

- [ ] **Step 4: Full suite where ports are available.** Run `bash scripts/ci/check.sh`, or the Tart runner `scripts/ci/tart-macos.sh` (inspect it with `--dry-run` first), on a machine that allows local ports. Record the result in the pull request description.

- [ ] **Step 5: Final commit, if Step 3 needed fixes**

```bash
git add -A ui-kit core studios docs tests
git commit -m "Align remaining details found in the visual check

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
