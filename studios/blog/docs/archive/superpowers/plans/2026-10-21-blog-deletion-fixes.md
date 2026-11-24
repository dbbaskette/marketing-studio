# Blog Deletion Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The delete sheet accepts the title as a person types it, says when the text does not match yet, and every card on the Blogs page can open it.

**Architecture:** Both the page (`runner.js`) and the server (`blog_delete.py`) compare a normalized form of the title (NFKC, plain quotes and dashes, collapsed whitespace, case-folded); the server stays the authority. The Blogs page reuses the existing `sDeleteSheet`, which already fetches the blog's version token when a card has none.

**Tech Stack:** Python 3.11 standard library, vanilla browser JavaScript, `unittest`, the Node browser-script check `scripts/ci/check-management.cjs`.

Spec: `docs/superpowers/specs/2026-10-21-voices-styles-and-blog-deletion-design.md`, sections 1 and 2.

All paths below are relative to `studios/blog/`. Run commands from that folder. Tests write only to temporary folders; never point them at a real workspace.

---

### Task 1: The server accepts a normalized title

**Files:**
- Modify: `skills/blog-studio/scripts/blog_delete.py:70-82` (`check`)
- Test: `tests/test_blog_runner.py` (class `RunnerCase`, next to `test_delete_needs_the_shown_version_and_the_typed_title` near line 1335)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_blog_runner.py`, directly after `test_delete_needs_the_shown_version_and_the_typed_title`:

```python
    def test_delete_accepts_the_title_as_a_person_types_it(self):
        # Curly quotes, an en dash and a double space in the stored title; plain typing deletes it.
        found = self.create(page=True, title='From agent “pilots” to governed  production – 2026')
        with self.assertRaisesRegex(ValueError, 'title'):
            self.delete(found, title='From agent pilots to production')
        result = self.delete(found, title='  from agent "pilots" to governed production - 2026 ')
        self.assertTrue(result['deleted'])
        self.assertEqual([row['id'] for row in runner.catalog(self.root)['deleted']], [found['id']])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_blog_runner.RunnerCase.test_delete_accepts_the_title_as_a_person_types_it -v`
Expected: FAIL with `ValueError: That is not the title of this blog` on the plain-typed delete.

- [ ] **Step 3: Add the normalization and use it in `check`**

In `skills/blog-studio/scripts/blog_delete.py`, add after the imports (`import time`):

```python
import unicodedata

# Typographic marks a person types as their plain forms.
PLAIN_MARKS = str.maketrans(
    {
        '‘': "'",
        '’': "'",
        '‚': "'",
        '“': '"',
        '”': '"',
        '„': '"',
        '–': '-',
        '—': '-',
    }
)


def plain_title(value):
    """A title as a person would type it: NFKC, plain quotes and dashes, one space between
    words, no case. Both the typed text and the stored title go through this."""
    value = unicodedata.normalize('NFKC', value).translate(PLAIN_MARKS)
    return ' '.join(value.split()).casefold()


def same_title(typed, stored):
    return isinstance(typed, str) and plain_title(typed) == plain_title(stored)
```

Then in `check`, replace:

```python
    if data['title'] != record['title']:
        raise ValueError(MISTITLED)
```

with:

```python
    if not same_title(data['title'], record['title']):
        raise ValueError(MISTITLED)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_blog_runner.RunnerCase.test_delete_accepts_the_title_as_a_person_types_it tests.test_blog_runner.RunnerCase.test_delete_needs_the_shown_version_and_the_typed_title -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/blog-studio/scripts/blog_delete.py tests/test_blog_runner.py
git commit -m "Accept a blog's title as a person types it when deleting

A stored title with curly quotes, a dash, a double space or different case
could never be matched exactly, so the Delete button never enabled. Both
sides are now compared after NFKC normalization, plain quotes and dashes,
collapsed whitespace and case folding.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: The page enables Delete on the same match and says when it does not match yet

**Files:**
- Modify: `skills/blog-studio/assets/management/runner.js:634-642` (`sDeleteSheet`)
- Test: `scripts/ci/check-management.cjs` (the block beginning `// Delete names the blog, says what is running stops, and waits for the typed title.` near line 1214)

- [ ] **Step 1: Extend the browser check so it fails**

In `scripts/ci/check-management.cjs`, replace these two lines inside that block:

```js
  const typed=sheet().find(e=>e.id==='delete-title');typed.value='Synthetic';typed.listeners.input();assert.equal(confirm.disabled,true);
  typed.value='Synthetic blog';typed.listeners.input();assert.equal(confirm.disabled,false);
```

with:

```js
  const typed=sheet().find(e=>e.id==='delete-title'),hint=()=>sheet().find(e=>e.id==='delete-title-hint');
  assert.equal(hint().hidden,true,'no hint before anything is typed');
  typed.value='Synthetic';typed.listeners.input();assert.equal(confirm.disabled,true);
  assert.equal(hint().hidden,false,'a partial title says it is not the title yet');assert.equal(hint().textContent,'Not the title yet.');
  typed.value='  synthetic  BLOG ';typed.listeners.input();assert.equal(confirm.disabled,false,'case and spacing do not matter');assert.equal(hint().hidden,true);
  typed.value='“Synthetic” blog';typed.listeners.input();assert.equal(confirm.disabled,true,'added characters still do not match');
  typed.value='Synthetic blog';typed.listeners.input();assert.equal(confirm.disabled,false);
```

- [ ] **Step 2: Run the check to verify it fails**

Run: `node scripts/ci/check-management.cjs`
Expected: an `AssertionError` from `hint().hidden` (the hint element does not exist yet, so `hint()` is undefined and the property read throws).

- [ ] **Step 3: Add the page-side normalization and the hint**

In `skills/blog-studio/assets/management/runner.js`, add this function directly above `function sDeleteSheet(found){`:

```js
// The same match the server makes: NFKC, plain quotes and dashes, one space between words, no case.
function sPlainTitle(value){return value.normalize('NFKC').replace(/[‘’‚]/g,"'").replace(/[“”„]/g,'"').replace(/[–—]/g,'-').replace(/\s+/g,' ').trim().toLowerCase();}
```

Then replace the whole `sDeleteSheet` function with:

```js
function sDeleteSheet(found){
  const title=found.title||'this blog',running=['working','queued'].includes(found.status),held={title:''},problem=sNode('p','sheet-error');problem.setAttribute('role','alert');
  const matches=()=>sPlainTitle(held.title)===sPlainTitle(title);
  const confirm=sButton('Delete '+title,async button=>{if(!matches())return;await busy(button,'Deleting…',async()=>{try{const expected=found.expected||(await api('article?'+new URLSearchParams({id:found.id,location:'local'}))).expected;const result=await api('blog-delete',{id:found.id,expected,title:held.title.trim()});sCloseSheet();studio.found=null;sToast('Deleted '+title+'.'+(result?.notice?' '+result.notice:''));await sRoute('blogs');}catch(error){problem.textContent=error.message+(/deleted/.test(error.message)?'':' Nothing was deleted.');}});},'danger');confirm.disabled=true;
  const hint=sNode('p','quiet field-hint','Not the title yet.');hint.id='delete-title-hint';hint.hidden=true;
  const goes=[running?'What’s running will stop, and nothing more of it is kept.':null,'It leaves your lists, and its folder goes'+(found.team?' from the team repository as one recorded change.':'.'),'What only this computer kept for it: its run state, receipts and tool jobs.'].filter(Boolean);
  sOpenSheet('Delete '+title+'?',running?sStatus('late','It is working now. What’s running will stop.'):null,
    sNode('h3','sheet-part','What goes'),sAdd(sNode('ul',''),...goes.map(words=>sNode('li','',words))),
    sNode('h3','sheet-part','What stays'),sAdd(sNode('ul',''),sNode('li','','It is kept for 30 days under Recently deleted on the Blogs page, where Restore brings it back.'),sNode('li','','Anything published elsewhere, or shared with a Team Hub, is not touched.')),
    sField('delete-title','Type the title to confirm',held,'title',{required:true,max:500,changed:()=>{const same=matches();confirm.disabled=!same;hint.hidden=same||!held.title.trim();}}),hint,problem,sAdd(sNode('div','bar'),confirm,sButton('Cancel',sCloseSheet)));
}
```

- [ ] **Step 4: Run the check to verify it passes**

Run: `node scripts/ci/check-management.cjs`
Expected: exits 0 with no assertion output. Also run `python3 -m unittest tests.test_management_ui -v` (it runs the same script) and expect PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/blog-studio/assets/management/runner.js scripts/ci/check-management.cjs
git commit -m "Enable Delete on the title as typed, and say when it is not the title yet

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Delete from the Blogs page

**Files:**
- Modify: `skills/blog-studio/assets/management/runner.js:125` (`sBlogCard`) and `:127` (`sBlogs`)
- Modify: `README.md:103-104` and `docs/runner.md` (the paragraph that starts `**Blogs** holds your saved`, if present; otherwise the "Run and review" section)
- Test: `scripts/ci/check-management.cjs` (the line `f.run('studio.ordinary=[];sBlogs()');assert.equal(f.get('title').textContent,'Your blogs');` near line 932)

- [ ] **Step 1: Extend the browser check so it fails**

In `scripts/ci/check-management.cjs`, directly after the line

```js
  f.run('studio.ordinary=[];sBlogs()');assert.equal(f.get('title').textContent,'Your blogs');
```

add:

```js
  // Every card on Blogs can delete its blog through the same sheet as the run's last screen.
  {
    const remove=descendants(content).find(e=>e.textContent==='Delete');
    assert.ok(remove,'a Blogs card offers Delete');assert.equal(remove.className,'button button-quiet');
    await remove.listeners.click();
    const open=descendants(f.get('sheet'));
    assert.ok(open.some(e=>e.textContent==='Delete Synthetic blog?'),open.map(e=>e.textContent).join('|'));
    f.run('sCloseSheet()');
    f.run("studio.ordinary=[{id:'plain',title:'A saved draft',author:'Avery',mode:'existing'}];sBlogs()");
    assert.equal(descendants(content).filter(e=>e.textContent==='Delete').length,2,'saved drafts get Delete too');
    f.run('access.actions.edit=false;sBlogs()');
    assert.ok(descendants(content).filter(e=>e.textContent==='Delete').every(e=>e.disabled),'Delete follows edit access');
    f.run('access.actions.edit=true;studio.ordinary=[];sBlogs()');
  }
```

(`content` in that block is `f.get('studio-page')`; check the surrounding lines and reuse the variable name they use for the page element.)

- [ ] **Step 2: Run the check to verify it fails**

Run: `node scripts/ci/check-management.cjs`
Expected: `AssertionError: a Blogs card offers Delete`.

- [ ] **Step 3: Add the Delete action to both kinds of card**

In `skills/blog-studio/assets/management/runner.js`, replace the `sBlogCard` line (125) with:

```js
function sDeleteAction(found){const remove=sButton('Delete',()=>sDeleteSheet({id:found.id,title:found.title,status:found.status||'',team:!!found.team}));remove.disabled=!access.actions.edit;return remove;}
function sBlogCard(found){return sCard(found.title,sNode('p','quiet',sEditingRun(found)?'Editing a manuscript':BLOG_MODES.find(([mode])=>mode===found.mode)?.[1]||'Saved draft'),sStatus(sNeeds(found)?'review':found.complete?'done':found.status==='working'?'current':'none',sWords(found)),sAdd(sNode('div','bar'),sButton(sEditingRun(found)?'Continue editing':found.status==='waiting-for-approval'?'Continue review':'Continue',sReview(found),'filled'),sDeleteAction(found)));}
```

and in `sBlogs` (line 127) replace the ordinary-card expression

```js
grid.append(sCard(found.title,sNode('p','quiet',found.author||'Saved draft'),sButton(found.mode==='interview'?'Resume interview':'Continue editing',()=>found.mode==='interview'?sInterview(found.id):sRoute('editor',found.id),'filled')));
```

with:

```js
grid.append(sCard(found.title,sNode('p','quiet',found.author||'Saved draft'),sAdd(sNode('div','bar'),sButton(found.mode==='interview'?'Resume interview':'Continue editing',()=>found.mode==='interview'?sInterview(found.id):sRoute('editor',found.id),'filled'),sDeleteAction(found))));
```

- [ ] **Step 4: Run the check to verify it passes**

Run: `node scripts/ci/check-management.cjs`
Expected: exits 0.

- [ ] **Step 5: Look at it on a phone width**

Open the page against a disposable workspace (see `docs/development.md`, "To try the skill from a checkout") or trust the `.bar` layout, which already wraps buttons on narrow widths elsewhere on the page (the done card uses it). If the two buttons overflow a card at 375px, change `sNode('div','bar')` in both cards to `sNode('div','bar file-actions')`; `.file-actions{flex-wrap:wrap}` is in `assets/management/blog.css:11`.

- [ ] **Step 6: Document it**

In `README.md`, change

```
**Blogs** holds your saved
runs.
```

to

```
**Blogs** holds your saved
runs; each card has **Delete**, which asks for the blog's title and keeps the
blog for 30 days under **Recently deleted**.
```

In `docs/runner.md`, find the sentence in "Run and review" that describes **Blogs** (search for `Blogs`), and append the same clause. If no sentence describes Blogs there, add this paragraph at the end of "Run and review":

```
**Blogs** lists every saved blog. Each card has **Delete**, which asks for the
blog's title, stops anything running for it and keeps it for 30 days under
**Recently deleted**, where **Restore** brings it back.
```

- [ ] **Step 7: Commit**

```bash
git add skills/blog-studio/assets/management/runner.js scripts/ci/check-management.cjs README.md docs/runner.md
git commit -m "Delete a blog from its card on the Blogs page

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Full check

- [ ] **Step 1: Run the project checks in a disposable results folder**

Run: `bash scripts/ci/check.sh "$(command -v python3)" "$TMPDIR/blog-studio-deletion-checks"`
Expected: ends with the unittest summary `OK`. If ruff is not installed the lint step prints `SKIPPED`, which is acceptable locally.

- [ ] **Step 2: Add the changelog entry**

In `CHANGELOG.md`, under the `# Changelog` introduction and above `## 4.3.0 — 2026-10-20`, add (or extend, if an unreleased heading already exists):

```
## Unreleased

- Deleting a blog accepts its title as you type it: case, spacing, curly quotes and
  dashes no longer have to match the stored title exactly, and the sheet says when
  the text is not the title yet. Every card on **Blogs** has **Delete**.
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "Note the deletion fixes in the changelog

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
