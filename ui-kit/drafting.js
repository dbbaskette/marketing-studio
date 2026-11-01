// The shared desk kit: the parts of a writing desk any studio's page can use, drawn the way
// Blog Studio's desk draws them. Plain JavaScript with no build step; it defines one global,
// Drafting.
//
// Drafting.make and Drafting.add are the kit's own two DOM helpers. Everything else that
// draws comes from Drafting.kit(adapter), which returns the desk's parts bound to what the
// studio passes: its controls (ui), its requests (api, routes), its words, its parts and its
// Finishing tools. kit() reads no member of the adapter when it is called; each part reads
// what it needs when it runs, so a studio may build its kit before it defines the functions
// its adapter names. Every text from a draft is set with textContent, never as markup.
'use strict';
const Drafting = (() => {
  'use strict';
  const DIFF_LIMIT = 4000, SAVE_WAIT = 1000, POLL = 3000;
  // The selection bar's actions, as studio_core.drafting.prompts.ACTIONS names them.
  const SELECTION = [['rephrase', 'Rephrase'], ['shorten', 'Shorten'], ['expand', 'Expand'], ['fix', 'Fix']];

  // A node with its text (when given) and class (when given), and a parent with its children
  // (null and undefined left out).
  function make(tag, cls, text) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (cls) node.className = cls; return node; }
  function add(parent, ...children) { parent.append(...children.filter(child => child !== null && child !== undefined)); return parent; }

  // Shared content-only approval. Rendering and design belong to the adapter after
  // the exact version shown here has been accepted by the person.
  //
  // A change typed in the box is never dropped by Approve: it asks whether to send it first
  // or approve without it. With `onEdit`, each slide's title, points and speaker notes are
  // boxes the person corrects in place, with no assistant: `edits` is the slides as edited so
  // far (or null), onEdit(slides) is told each change, and onDecision gets the edited slides
  // as a third argument (null when nothing changed). `toolbar` says the studio shows Approve
  // as its toolbar's filled action, so the panel's own is not filled. The panel's `decide`
  // makes a decision as its own buttons do, for that toolbar button.
  function slideContent({slides, label, note = '', onNote = () => {}, onDecision, edits = null,
    onEdit = null, toolbar = false}) {
    const box = add(make('section', 'paper slide-text-review'),
      make('h2', 'doc-title', label || 'Review slide text'),
      make('p', 'quiet', 'Check the message, slide order, copy and speaker notes. Design and rendering start only after you approve this text.'));
    const editing = typeof onEdit === 'function';
    const given = JSON.stringify(slides || []);
    const work = editing ? JSON.parse(Array.isArray(edits) ? JSON.stringify(edits) : given) : null;
    const edited = () => editing && JSON.stringify(work) !== given;
    if (editing) box.append(make('p', 'quiet', 'Correct a word here and approve: your edits go with your decision, and no assistant redrafts them.'));
    const items = make('ol', 'slide-text-list');
    // A box of one slide's words, named for its slide. Its words go into the edited slides.
    let boxes = 0;
    const wordBox = (slide, number, name, value, long, put) => {
      const id = 'slide-text-' + (++boxes);
      const field = make('label', 'field');
      field.htmlFor = id;
      const input = make(long ? 'textarea' : 'input', 'input');
      input.id = id;
      if (long) input.rows = 2; else input.type = 'text';
      input.value = value || '';
      input.dataset.key = 'slide-text ' + number + ' ' + name;
      input.addEventListener('input', () => { put(input.value); onEdit(edited() ? work : null); });
      return add(field, add(make('span', 'field-label', name), make('span', 'offscreen', ' of slide ' + number)), input);
    };
    (editing ? work : slides || []).forEach((slide, index) => {
      const number = index + 1;
      const row = make('li', 'slide-text-item');
      if (editing) row.append(wordBox(slide, number, 'Title', slide.title, false, (value) => { slide.title = value; }));
      else row.append(make('h3', 'row-title', slide.title || 'Untitled slide'));
      for (const key of ['subtitle', 'detail', 'focal', 'caveat', 'source']) {
        if (typeof slide[key] === 'string' && slide[key].trim()) row.append(make('p', 'desk-plain', slide[key]));
      }
      const points = make(editing ? 'div' : 'ul', editing ? 'fields' : 'outline-points');
      (slide.points || []).forEach((point, at) => {
        if (!editing) {
          const text = typeof point === 'string' ? point : [point.label, point.text].filter(Boolean).join(': ');
          points.append(make('li', '', text));
          return;
        }
        const name = 'Point ' + (at + 1);
        if (typeof point === 'string') { points.append(wordBox(slide, number, name, point, true, (value) => { slide.points[at] = value; })); return; }
        if (point && point.label) points.append(wordBox(slide, number, name + ' label', point.label, false, (value) => { point.label = value; }));
        if (point && typeof point.text === 'string') points.append(wordBox(slide, number, name, point.text, true, (value) => { point.text = value; }));
      });
      if (points.children.length) row.append(points);
      if (editing) row.append(wordBox(slide, number, 'Speaker notes', slide.notes, true, (value) => { slide.notes = value; }));
      else if (slide.notes) row.append(add(make('details', 'outline-notes'), make('summary', '', 'Speaker notes'), make('p', 'desk-plain', slide.notes)));
      items.append(row);
    });
    const field = make('label', 'field');
    const text = make('textarea', 'input'); text.value = note; text.rows = 3;
    text.dataset.key = 'slide-text-note';
    add(field, make('span', 'field-label', 'Changes to slide text'), text);
    const problem = make('p', 'problem'); problem.setAttribute('role', 'alert');
    const actions = make('div', 'bar');
    const ask = make('button', 'button', 'Ask for changes');
    const approve = make('button', 'button' + (toolbar ? '' : ' button-filled'), 'Approve text & design deck');
    ask.dataset.key = 'slide-text-changes';
    approve.dataset.key = 'slide-text-approve';
    // Approve with a change still typed asks first: send it, or approve without it.
    const pending = make('div', 'paper callout slide-text-pending');
    pending.setAttribute('role', 'group');
    pending.setAttribute('aria-label', 'Your typed change');
    pending.hidden = true;
    const sendFirst = make('button', 'button', 'Send these changes first');
    const without = make('button', 'button', 'Approve without them');
    sendFirst.dataset.key = 'slide-text-send-first';
    without.dataset.key = 'slide-text-without';
    add(pending, make('p', '', 'You typed a change to the slide text. Send these changes first, or approve without them?'), add(make('div', 'bar'), sendFirst, without));
    const controls = [ask, approve, text, sendFirst, without];
    let busy = false;
    const off = (state) => { busy = state; for (const control of controls) control.disabled = state; };
    text.addEventListener('input', () => { onNote(text.value); if (!text.value.trim()) pending.hidden = true; });
    async function decide(kind, typed = 'ask') {
      if (busy) return;
      if (kind === 'changes' && !text.value.trim()) { problem.textContent = 'Say what should change in the slide text.'; text.focus(); return; }
      if (kind === 'approve' && typed === 'ask' && text.value.trim()) {
        problem.textContent = ''; pending.hidden = false; sendFirst.focus();
        // Asked from the toolbar, the question is far down: it is brought to the middle, clear of
        // the toasts at the foot of a phone.
        if (typeof pending.scrollIntoView === 'function') pending.scrollIntoView({ block: 'center' });
        return;
      }
      if (kind === 'approve' && typed === 'drop') { text.value = ''; onNote(''); }
      pending.hidden = true;
      off(true); problem.textContent = '';
      try {
        const said = kind === 'changes' ? text.value.trim() : null;
        if (editing) await onDecision(kind, said, edited() ? work : null);
        else await onDecision(kind, said);
      }
      catch (error) { problem.textContent = error.message; }
      finally { off(false); }
    }
    ask.addEventListener('click', () => decide('changes'));
    approve.addEventListener('click', () => decide('approve'));
    sendFirst.addEventListener('click', () => decide('changes'));
    without.addEventListener('click', () => decide('approve', 'drop'));
    box.decide = decide;
    return add(box, items, field, problem, add(actions, ask, approve), pending);
  }

  // Words compared by a longest common subsequence, after the words both texts start and end
  // with are set aside; a comparison over about four million word pairs is shown side by side.
  function words(text) { return String(text || '').split(/\s+/).filter(Boolean); }
  function diffWords(before, after) {
    const a = words(before), b = words(after);
    if (a.length > DIFF_LIMIT || b.length > DIFF_LIMIT) return null;
    let head = 0; while (head < a.length && head < b.length && a[head] === b[head]) head++;
    let tail = 0; while (tail < a.length - head && tail < b.length - head && a[a.length - 1 - tail] === b[b.length - 1 - tail]) tail++;
    const x = a.slice(head, a.length - tail), y = b.slice(head, b.length - tail);
    if (x.length * y.length > DIFF_LIMIT * 1000) return null;
    const cols = y.length + 1, table = new Uint16Array((x.length + 1) * cols);
    for (let i = x.length - 1; i >= 0; i--) for (let j = y.length - 1; j >= 0; j--) table[i * cols + j] = x[i] === y[j] ? table[(i + 1) * cols + j + 1] + 1 : Math.max(table[(i + 1) * cols + j], table[i * cols + j + 1]);
    const out = [], push = (op, word) => { const last = out[out.length - 1]; if (last && last.op === op) last.text += ' ' + word; else out.push({ op, text: word }); };
    for (const word of a.slice(0, head)) push('same', word);
    let i = 0, j = 0;
    while (i < x.length && j < y.length) { if (x[i] === y[j]) { push('same', x[i]); i++; j++; } else if (table[(i + 1) * cols + j] >= table[i * cols + j + 1]) { push('removed', x[i]); i++; } else { push('added', y[j]); j++; } }
    while (i < x.length) push('removed', x[i++]); while (j < y.length) push('added', y[j++]);
    for (const word of a.slice(a.length - tail)) push('same', word);
    return out;
  }
  function age(at) { const then = Date.parse(at || ''); if (!then) return ''; const minutes = Math.round((Date.now() - then) / 60000); if (minutes < 1) return 'just now'; if (minutes < 60) return minutes + (minutes === 1 ? ' minute ago' : ' minutes ago'); const hours = Math.round(minutes / 60); if (hours < 24) return hours + (hours === 1 ? ' hour ago' : ' hours ago'); const days = Math.round(hours / 24); return days + (days === 1 ? ' day ago' : ' days ago'); }

  // The adapter a studio passes to kit():
  //   ui        button(label, action, kind), card(title, ...nodes), pickCard(title, says,
  //             action), choice(label, options, held, key, changed), disclosure(label,
  //             ...nodes), bead(state), openSheet(title, ...nodes), closeSheet(), toast(text),
  //             notice(text, isError), busy(control, label, action), narrow()
  //   api(route, data)  the page's request; throws Error(message) when refused
  //   routes    route names: view, save, versions, restore, note, revise, selection, stop,
  //             retry, finish, apply, skip, proofread
  //   share(id)         the keepalive request when the person leaves
  //   canEdit(held), current(held), page()
  //   hooks     render(held), refresh(held, before), reload(held), beforeJob(held); and, when
  //             the studio has them: beforeFlush(held), saved(held, part, text),
  //             versionNote(version), extra(held, part), left(held, part, card),
  //             started(held, view), landed(held, job)
  //   parts     title(view, part), textOf(view, part), nameOf(view, part), single(part),
  //             noted(view, part)
  //   words()   {thing, sources, doing, steps, named, withOpening, chain, ready(tab)}
  //   tools()   the Finishing tools, in panel order (see the Finishing parts below)
  //   progress  stopped(held), show(held)
  // `held` is the studio's screen state for one item, with the field names Blog Studio's desk
  // uses: view, pending, status, stale, saving, saved, session, bar, selection, asking, notes,
  // wholeNote, wholeGo, finish, panel, panelKey, panelStale, panelUnder, cards, wholeCard, tab
  // ('draft' shows the part cards), watching, startWatching and dismissed.
  function kit(a) {
    const k = {};

    // A version compared with the current text: struck words in the version only, marked
    // words added since; too long to compare word by word, the two side by side.
    k.compare = (before, after) => {
      const found = diffWords(before, after), box = make('div', 'paper desk-compare');
      if (!found) { box.append(add(make('div', 'desk-side'), make('h3', 'sheet-part', 'Before'), make('p', 'desk-plain', before)), add(make('div', 'desk-side'), make('h3', 'sheet-part', 'Now'), make('p', 'desk-plain', after))); return box; }
      const text = make('p', 'desk-plain'); text.setAttribute('aria-label', 'Changes from this version to the current text');
      found.forEach((piece, index) => { if (index) text.append(document.createTextNode(' ')); text.append(make(piece.op === 'same' ? 'span' : piece.op === 'added' ? 'ins' : 'del', piece.op === 'same' ? '' : piece.op === 'added' ? 'diff-add' : 'diff-remove', piece.text)); });
      return add(box, text);
    };
    // Before and after side by side: struck words only before, marked words only after.
    k.sides = (before, after) => {
      const found = diffWords(before, after), box = make('div', 'desk-sides');
      const side = (title, shown) => add(make('div', 'paper desk-side'), make('h4', 'sheet-part', title), shown);
      const was = make('p', 'desk-plain'), now = make('p', 'desk-plain');
      if (!found) { was.textContent = before; now.textContent = after; }
      else {
        let x = 0, y = 0; for (const piece of found) {
          if (piece.op !== 'added') { if (x++) was.append(document.createTextNode(' ')); was.append(piece.op === 'removed' ? make('del', 'diff-remove', piece.text) : make('span', '', piece.text)); }
          if (piece.op !== 'removed') { if (y++) now.append(document.createTextNode(' ')); now.append(piece.op === 'added' ? make('ins', 'diff-add', piece.text) : make('span', '', piece.text)); }
        }
      }
      if (!String(before).trim()) was.textContent = '(Nothing yet)';
      if (!String(after).trim()) now.textContent = '(Removed)';
      return add(box, side('Before', was), side('After', now));
    };

    // A hook the studio may leave out.
    const hook = (name, ...x) => { const found = a.hooks && a.hooks[name]; return typeof found === 'function' ? found(...x) : undefined; };
    const stale = error => /changed since/.test(error.message);

    // Saving as you type: one second after the last keystroke, against the revision last
    // seen, with the editing session's token; one save at a time, each against the latest.
    k.typed = (held, part, text) => {
      held.pending[part] = { text, timer: held.pending[part]?.timer };
      if (held.pending[part].timer && typeof clearTimeout === 'function') clearTimeout(held.pending[part].timer);
      held.pending[part].timer = setTimeout(() => k.save(held, part), SAVE_WAIT);
      if (held.status) held.status.textContent = 'Saving…';
    };
    k.save = async (held, part) => {
      if (!held.pending[part] || held.stale) return;
      while (held.saving) await held.saving;
      const pending = held.pending[part]; if (!pending || held.stale) return;
      const text = pending.text;
      held.saving = (async () => {
        try {
          const view = await a.api(a.routes.save, { id: held.id, seen: held.view.revision, part, text, session: held.session });
          if (held.pending[part]?.text === text) delete held.pending[part];
          const before = held.view; held.view = view; held.saved = 'Saved.';
          if (held.status && !held.stale) held.status.textContent = 'Saved.';
          k.counts(held);
          await hook('saved', held, part, text);  // The studio's own follow-up, such as a pasted image.
          // A job starting or ending, or parts added, removed or moved elsewhere, is drawn.
          const order = found => (found?.sections || []).map(section => section.id).join(',');
          if ((!!before.working !== !!view.working || order(before) !== order(view)) && a.current(held)) a.hooks.refresh(held, before);
        } catch (error) {
          if (stale(error)) { held.stale = true; k.stale(held); }
          else if (held.status) held.status.textContent = error.message + ' Your text is kept here.';
        } finally { held.saving = null; }
      })();
      await held.saving;
      if (held.pending[part] && held.pending[part].text !== text && !held.stale) return k.save(held, part);
    };
    k.flush = async held => {
      await hook('beforeFlush', held);  // The studio's own editors first.
      for (const part of Object.keys(held.pending)) { if (held.pending[part]?.timer && typeof clearTimeout === 'function') clearTimeout(held.pending[part].timer); await k.save(held, part); }
    };
    // Each part card's History button follows the view's version counts.
    k.counts = held => { for (const card of a.page().querySelectorAll('.desk-part')) { const count = (held.view.versions || {})[card.dataset.part] || 0, button = card.querySelectorAll('button')[0]; if (button && /^History/.test(button.textContent)) { button.textContent = count ? 'History (' + count + ')' : 'History'; button.disabled = !count; } } };
    // Changed in another window or job: the save state says so, with Reload.
    k.stale = held => {
      if (!held.status) return; held.status.className = 'desk-save-state decision-notice desk-stale';
      held.status.replaceChildren(make('span', '', 'This ' + a.words().thing + ' changed in another window or job. Reload to see the latest; your unsaved text is shown until you do. '), a.ui.button('Reload', async () => { await a.hooks.reload(held); }, 'filled'));
    };
    // Leaving the desk, or hiding its tab, shares the edits typing kept on this computer.
    k.share = async held => { if (!held) return; try { await k.flush(held); await a.share(held.id); } catch (_) { /* Shared with the next change instead. */ } };

    // History: each kept version with its words compared to the current text, and Restore.
    k.history = async (held, part) => {
      await k.flush(held);
      const found = await a.api(a.routes.versions + '?' + new URLSearchParams({ id: held.id, part }));
      const current = a.parts.textOf(held.view, part), list = make('div', 'desk-versions'), compare = make('div', 'desk-compare-area');
      const sources = a.words().sources || {};
      found.versions.forEach((version, index) => {
        const note = hook('versionNote', version) || '';
        const row = add(make('div', 'desk-version'), add(make('div', 'row-text'), make('h3', 'row-title', sources[version.source] || 'Earlier text'), make('p', 'quiet', [age(version.at), version.words + (version.words === 1 ? ' word' : ' words')].filter(Boolean).join(' · ')), note ? make('p', 'quiet', note) : null));
        const restore = a.ui.button('Restore', async control => {
          await a.ui.busy(control, 'Restoring…', async () => {
            try { held.view = await a.api(a.routes.restore, { id: held.id, seen: held.view.revision, part, index }); delete held.pending[part]; a.ui.closeSheet(); a.ui.toast('Restored. The text it replaced is in History.'); a.hooks.render(held); }
            catch (error) { if (stale(error)) { a.ui.closeSheet(); held.stale = true; k.stale(held); } else a.ui.notice(error.message, true); }
          });
        });
        restore.disabled = !a.canEdit(held) || !!held.view.working;
        row.append(add(make('div', 'bar'), a.ui.button('Compare', () => { compare.replaceChildren(make('h3', 'sheet-part', 'This version compared with now'), make('p', 'quiet', 'Struck words are in this version only; marked words were added since.'), k.compare(version.text, current)); }), restore));
        list.append(row);
      });
      a.ui.openSheet('History of ' + a.parts.nameOf(held.view, part), found.versions.length ? list : make('p', '', 'Nothing kept yet.'), compare);
    };

    // A small bar for the selected passage: Rephrase, Shorten, Expand, Fix and Ask….
    k.selected = (held, part, input) => {
      // The selection without the spaces around it, and where it starts in the saved text (a
      // part is kept without its leading spaces), so a repeated word is the one chosen.
      const value = input.value; let start = input.selectionStart, end = input.selectionEnd;
      if (typeof start !== 'number' || typeof end !== 'number') start = end = 0;
      while (start < end && /\s/.test(value[start])) start++; while (end > start && /\s/.test(value[end - 1])) end--;
      const text = value.slice(start, end), lead = value.length - value.replace(/^\s+/, '').length;
      if (!text || held.view.working || !a.canEdit(held)) { if (held.bar && !held.asking) held.bar.hidden = true; return; }
      held.selection = { part, text, start: start - lead }; held.asking = false; k.barContent(held); held.bar.hidden = false;
    };
    k.selectionBar = held => { const bar = make('div', 'desk-selection glass'); bar.setAttribute('role', 'toolbar'); bar.setAttribute('aria-label', 'Change the selected text'); bar.hidden = true; held.bar = bar; k.barContent(held); return bar; };
    k.barContent = held => {
      const bar = held.bar; if (!bar) return;
      const run = (action, instruction = '') => async control => { const chosen = held.selection; if (!chosen) return; await k.job(held, control, a.routes.selection, { part: chosen.part, text: chosen.text, start: chosen.start, action, ...(action === 'ask' ? { instruction } : {}) }, () => { held.selection = null; held.asking = false; }); };
      if (held.asking) {
        const box = make('input', 'input'); box.type = 'text'; box.maxLength = 2000; box.placeholder = 'What should change?'; box.setAttribute('aria-label', 'What should change in the selected text?');
        bar.replaceChildren(box, a.ui.button('Go', async control => { const instruction = box.value.trim(); if (!instruction) { a.ui.notice('Say what to do with the passage.', true); return; } await run('ask', instruction)(control); }, 'filled'), a.ui.button('Cancel', () => { held.asking = false; bar.hidden = true; }));
        return;
      }
      bar.replaceChildren(...SELECTION.map(([action, label]) => a.ui.button(label, run(action))), a.ui.button('Ask…', () => { held.asking = true; k.barContent(held); }));
    };

    // A Finishing tool by its key; nothing reads a tool by its place in the list.
    k.tool = key => (a.tools() || []).find(tool => tool.key === key) || null;
    // Whether the job under way changes this part: its own, or every section (and the
    // opening too for the kinds the studio names in words().withOpening).
    k.workingIn = (view, part) => { const job = view?.working; if (!job) return false; return job.part === part || job.part === 'sections' && !a.parts.single(part) && (part !== 'opening' || (a.words().withOpening || []).includes(job.kind)); };
    // The toolbar's line for the job under way: a note for the whole draft says which
    // section of how many; a kind in words().named says which part.
    k.statusWords = held => {
      const view = held.view, job = view.working; if (!job) return '';
      const chain = (a.words().chain || []).includes(job.kind);
      if (chain && job.part === 'opening') return 'Revising ' + a.parts.nameOf(view, 'opening') + '…';
      if (chain && job.total) return 'Revising section ' + (job.index + 1) + ' of ' + job.total + '…';
      const said = a.words();
      return ((said.doing || {})[job.kind] || 'Working') + ((said.named || []).includes(job.kind) ? ' ' + a.parts.nameOf(view, job.part) : '') + '…';
    };
    // What the last job left: a note for the whole draft that missed some sections, a result
    // not applied, or a job that failed, with Dismiss.
    k.problem = held => {
      const last = (held.view.jobs || []).at(-1); if (!last || held.dismissed === last.id) return null;
      const dismiss = () => a.ui.button('Dismiss', () => { held.dismissed = last.id; a.hooks.render(held); });
      const chain = held.view.chain;
      if (last.chain && chain) {
        if (chain.working || !chain.problems.length) return null;
        const opening = a.parts.nameOf(held.view, 'opening'), named = opening.charAt(0).toUpperCase() + opening.slice(1);
        return add(make('div', 'decision-notice desk-problem'), add(make('div', ''), make('p', '', chain.total === 1 && chain.problems[0].part === 'opening' ? 'Your note was not applied:' : 'Revised ' + chain.revised + ' of ' + chain.total + ' sections for your note. These were not:'), add(make('ul', 'gap-items'), ...chain.problems.map(problem => make('li', '', (problem.part === 'opening' ? named : '“' + problem.heading + '”') + ': ' + problem.error)))), dismiss());
      }
      const failed = last.status === 'failed' || last.status === 'ready' && last.applied === false; if (!failed || !last.error) return null;
      const tool = /^finish-/.test(last.kind || '') ? k.tool(last.kind.slice(7)) : null;
      return add(make('div', 'decision-notice desk-problem'), make('p', '', (tool ? tool.name + ' did not finish: ' : last.status === 'failed' ? 'The last change could not finish: ' : 'The last change was not applied: ') + last.error), dismiss());
    };
    // The note for the whole draft: each section revised for it in turn.
    k.whole = held => {
      const thing = a.words().thing, card = a.ui.card('Note for the whole ' + thing);
      const box = make('textarea', 'input'); box.id = 'desk-whole-note'; box.rows = 2; box.maxLength = 4000; box.setAttribute('aria-label', 'Note for the whole ' + thing); box.value = held.wholeNote || ''; box.placeholder = 'For example: tighten throughout, or make it more casual.';
      box.addEventListener('input', () => { held.wholeNote = box.value; });
      const go = a.ui.button('Revise the ' + thing, async control => { const text = (held.wholeNote || '').trim(); if (!text) { a.ui.notice('Write the note for the whole ' + thing + '.', true); return; } await k.job(held, control, a.routes.revise, { note: text }, () => { held.wholeNote = ''; }); }, 'filled');
      go.disabled = !a.canEdit(held) || !!held.view.working; held.wholeGo = go;
      return add(card, box, make('p', 'quiet field-hint', 'Each section is revised for the note with the whole ' + thing + ' in view. Your text is kept as a version first.'), add(make('div', 'bar'), go));
    };
    // A part's card: its name and History, its text typed in place (one line for a single
    // part), what the studio adds under it, feedback on it, the job working on it, and for a
    // part that takes a note, the note box with Rewrite or Write again.
    k.part = (held, part) => {
      const view = held.view, working = k.workingIn(view, part), noted = a.parts.noted(view, part), single = a.parts.single(part), title = a.parts.title(view, part);
      const card = make('section', 'card desk-part' + (working ? ' desk-working' : '')); card.dataset.part = part;
      const heading = make('h2', 'card-title', title);
      const count = (view.versions || {})[part] || 0, history = a.ui.button(count ? 'History (' + count + ')' : 'History', () => k.history(held, part)); history.disabled = !count;
      card.append(add(make('div', 'desk-part-head'), heading, history));
      const text = held.pending[part]?.text ?? a.parts.textOf(view, part);
      const input = make(single ? 'input' : 'textarea', 'input desk-text'); input.value = text; input.setAttribute('aria-label', noted ? 'Text of ' + title : title);
      if (single) { input.type = 'text'; input.maxLength = 500; } else { input.rows = Math.min(24, Math.max(3, Math.ceil(text.length / 90) + text.split('\n').length)); }
      input.readOnly = working || !a.canEdit(held); card.deskInput = input;
      input.addEventListener('input', () => k.typed(held, part, input.value));
      if (!single) { for (const kind of ['select', 'mouseup', 'keyup']) input.addEventListener(kind, () => k.selected(held, part, input)); }
      else input.addEventListener('select', () => k.selected(held, part, input));
      card.append(input);
      const extra = hook('extra', held, part); if (extra) card.append(extra);
      const comments = k.comments(held, part); if (comments) card.append(comments);
      if (working) { const note = make('p', 'desk-working-note', 'Working on this section'); note.setAttribute('role', 'status'); card.append(note); card.deskWorkingNotes = [note]; if (view.working.note) { const said = make('p', 'quiet', 'Your note: ' + view.working.note); card.append(said); card.deskWorkingNotes.push(said); } }
      if (noted) {
        const typed = (held.notes || {})[part] || '', row = make('div', 'desk-note');
        const box = make('textarea', 'input desk-note-text'); box.rows = typed.includes('\n') ? 4 : 1; box.maxLength = 4000; box.value = typed; box.placeholder = 'How should this change?'; box.setAttribute('aria-label', 'How should ' + title + ' change?');
        const go = a.ui.button(typed.trim() ? 'Rewrite' : 'Write again', async control => { const note = ((held.notes || {})[part] || '').trim(); await k.job(held, control, a.routes.note, { part, note }, () => { if (held.notes) delete held.notes[part]; }); });
        go.disabled = !a.canEdit(held) || !!view.working; card.deskGo = go;
        box.addEventListener('input', () => { held.notes = held.notes || {}; held.notes[part] = box.value; go.textContent = box.value.trim() ? 'Rewrite' : 'Write again'; });
        card.append(add(row, box, go));
      }
      card.addEventListener('focusout', () => hook('left', held, part, card));
      return card;
    };
    // Notes and selection edits start a job; the desk follows it until it ends.
    k.job = async (held, control, route, data, done) => {
      await a.ui.busy(control, 'Starting…', async () => {
        try {
          await k.flush(held); await a.hooks.beforeJob(held); if (held.stale) return;
          const before = held.view; held.view = await a.api(route, { id: held.id, seen: held.view.revision, ...data }); if (done) done();
          a.hooks.refresh(held, before); k.watch(held);
        } catch (error) { if (stale(error)) { held.stale = true; k.stale(held); } else a.ui.notice(error.message, true); }
      });
    };
    k.watch = held => {
      if (!held.view.working || held.watching) return; held.watching = true;
      const follow = async () => {
        if (!a.current(held)) { held.watching = false; return; }
        try {
          await k.flush(held); const view = await a.api(a.routes.view + '?id=' + encodeURIComponent(held.id)); if (!a.current(held)) { held.watching = false; return; }
          const ended = !view.working, before = held.view; held.view = view; a.hooks.refresh(held, before);
          if (ended) {
            held.watching = false; const last = (view.jobs || []).at(-1);
            if (last?.applied) a.ui.toast(hook('landed', held, last) || (/^finish-/.test(last.kind) ? 'Suggestions are ready in Finishing.' : 'Done. The earlier text is in History.'));
            if (held.finish?.tool === 'proofread' && !/^finish-/.test(last?.kind || '')) await k.proofread(held);
            return;
          }
        } catch (error) { if (held.status) held.status.textContent = error.message; }
        setTimeout(follow, POLL);
      };
      setTimeout(follow, POLL);
    };

    // A start under way: nothing is needed from the person; the draft opens on its own.
    k.starting = view => !!view?.start && !view.start.ended_at;
    k.elapsed = start => { const then = Date.parse(start.started_at || ''); return then ? Math.max(0, (Date.now() - then) / 60000) : 0; };
    k.spent = start => { const minutes = Math.floor(k.elapsed(start)); return minutes < 1 ? 'under a minute' : minutes + (minutes === 1 ? ' minute' : ' minutes'); };
    k.clock = start => { const spent = k.spent(start); return spent.charAt(0).toUpperCase() + spent.slice(1) + ' so far, for the whole start.'; };
    // About how long is left, from recent runs of each step here; an overrun step says so.
    k.estimate = (start, what) => { if (start.over) return 'Nothing needed from you. Taking longer than usual; still working, ' + k.spent(start) + ' so far. ' + what + ' opens here when it is ready.'; const left = Math.max(1, start.minutes_left || start.minutes || 1); return 'Nothing needed from you. ' + what + ' opens here when it is ready, in about ' + left + (left === 1 ? ' minute.' : ' minutes.'); };
    // The progress screen's parts; the studio frames the page. `what` names what opens, as
    // "The draft". A stopped start's notice and its exits are the studio's (progress.stopped).
    k.progress = (held, what) => {
      const view = held.view, start = view.start, problem = start.problem;
      const stop = start.busy ? a.ui.button('Stop', async control => { await a.ui.busy(control, 'Stopping…', async () => { try { held.view = await a.api(a.routes.stop, { id: held.id, job: start.job }); a.progress.show(held); } catch (error) { a.ui.notice(error.message, true); } }); }) : null;
      if (stop) stop.disabled = !a.canEdit(held);
      const lede = make('p', 'lede', problem ? 'This start stopped before ' + what.toLowerCase() + ' was ready. Retry the step when you are ready.' : k.estimate(start, what));
      lede.setAttribute('role', 'status');
      const steps = make('ol', 'rows desk-steps'), at = start.steps.indexOf(start.step), names = a.words().steps || {}; steps.setAttribute('aria-label', 'Steps of this start');
      start.steps.forEach((step, index) => {
        const state = index < at ? 'done' : index === at ? (problem ? 'late' : 'current') : 'none';
        const now = index === at && !problem ? (start.phase || (start.status === 'queued' ? 'Reading your sources' : 'Under way')) : '';
        steps.append(add(make('li', 'row step'), a.ui.bead(state), add(make('div', 'row-text'), make('h3', 'row-title', names[step] || step), now ? make('p', 'row-says', now) : null)));
      });
      return { stop, above: problem ? 'Stopped' : 'Writing on its own', lede, stopped: problem ? a.progress.stopped(held) : null, card: a.ui.card('Progress', steps, make('p', 'quiet desk-clock', k.clock(start))) };
    };
    // Followed until the draft (or the outline) opens, then the studio's ready line.
    k.followStart = held => {
      if (held.startWatching) return; held.startWatching = true;
      setTimeout(async () => {
        held.startWatching = false; if (!a.current(held)) return;
        try {
          const view = await a.api(a.routes.view + '?id=' + encodeURIComponent(held.id)); if (!a.current(held)) return; held.view = view;
          if (k.starting(view)) return a.progress.show(held);
          a.hooks.started(held, view); a.hooks.render(held); k.watch(held); a.ui.toast(a.words().ready(held.tab));
        } catch (error) { a.ui.notice(error.message, true); k.followStart(held); }
      }, POLL);
    };

    // Finishing: an optional side panel of tools that propose. Each proposal is previewed
    // before and after, then applied, edited or skipped; nothing changes until Apply, and each
    // Apply keeps the earlier text in History. On a phone the panel is a full-screen sheet.
    //
    // A tool, as a.tools() lists them in panel order: {key, name, says}; for one that runs a
    // job, run (its button) and doing (its working line), sent as `finish` with {tool: key}
    // and data(f); optional start (the panel state it begins with), options(held, f) (controls
    // above run), ready(f) (whether run is on), open(held) (takes over its own opening, in
    // place of the panel), opened(held, first) (called once it shows: first when the panel
    // opens at it), view(held) (a whole view in place of proposals), and the shape of its
    // proposals: verdicts (a tag per claim, supported ones folded, Keep it, and source(held)
    // for Add a source), groups ([[part, name]] of alternatives, Use this), comments ({aspect:
    // name}, feedback that can become a note), applyAll, counted ([one, many]), empty (the
    // line for an empty set), said(set, said) (more of the set's line) and flagged(n).
    const commenting = () => (a.tools() || []).find(tool => tool.comments) || null;
    k.finishOpen = (held, key = null) => {
      const tool = key ? k.tool(key) : null;
      if (tool && tool.open) return tool.open(held);
      if (!held.finish) { held.finish = { tool: null, editing: {}, noted: {} }; for (const each of a.tools() || []) Object.assign(held.finish, each.start || {}); }
      held.finish.tool = key; a.hooks.render(held);
      if (tool && tool.opened) return tool.opened(held, true);
    };
    k.finishClose = held => { held.finish = null; a.hooks.render(held); hook('finishClosed',held); };
    k.finishTool = (held, key) => {
      const tool = k.tool(key);
      if (tool.open) return tool.open(held);
      held.finish.tool = key; k.panelShow(held);
      if (tool.opened) return tool.opened(held, false);
    };
    k.panel = held => {
      const f = held.finish, tool = f.tool ? k.tool(f.tool) : null;
      const panel = make('aside', 'desk-finish' + (a.ui.narrow() ? ' desk-finish-sheet' : '')); panel.setAttribute('aria-label', 'Finishing');
      const head = make('div', 'desk-finish-head glass');
      if (tool) head.append(a.ui.button('All tools', () => { f.tool = null; k.panelShow(held); }));
      head.append(make('h2', 'desk-finish-title', tool ? tool.name : 'Finishing'), a.ui.button('Close', () => k.finishClose(held)));
      const body = make('div', 'desk-finish-body'); body.append(...(tool ? k.toolView(held, f.tool) : k.toolList(held)));
      panel.addEventListener('focusout', () => setTimeout(() => { if (held.panelStale && held.panel === panel) k.panelSync(held, true); }, 0));
      panel.hidden = !!held.panelUnder;  // Under a sheet opened from it, on a narrower screen.
      return add(panel, head, body);
    };
    // What the panel shows, so a poll redraws it only when that changed.
    k.panelKey = held => { const view = held.view, f = held.finish || {}; return JSON.stringify([f.tool, view.finishing || {}, view.working && [view.working.id, view.working.kind, view.working.status], (view.jobs || []).filter(job => /^finish-/.test(job.kind)).slice(-4).map(job => [job.id, job.status, job.error]), view.google_suggestions, view.revision, view.source_names?.length]); };
    k.panelShow = held => { if (!held.finish || !held.panel) return; const panel = k.panel(held); held.panel.replaceWith(panel); held.panel = panel; held.panelKey = k.panelKey(held); held.panelStale = false; };
    // A redraw the person did not ask for waits while they use a control in the panel, and
    // happens as soon as focus leaves it.
    k.panelSync = (held, force = false) => {
      if (!held.finish || !held.panel || (!force && k.panelKey(held) === held.panelKey)) return true;
      const focused = typeof document.activeElement === 'object' ? document.activeElement : null;
      if (focused && ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'SUMMARY'].includes(String(focused.tagName).toUpperCase()) && typeof held.panel.contains === 'function' && held.panel.contains(focused)) { held.panelStale = true; return false; }
      k.panelShow(held); return true;
    };
    k.toolList = held => {
      const list = make('div', 'pick-cards desk-finish-tools');
      const groups=new Map();
      for(const tool of a.tools() || []){const group=tool.group||'';if(!groups.has(group))groups.set(group,[]);groups.get(group).push(tool);}
      for(const [group,tools] of groups){
        if(group)list.append(make('h3','desk-tool-group',group));
        for(const tool of tools)list.append(a.ui.pickCard(tool.name, k.toolSays(held, tool.key) || tool.says, () => k.finishTool(held, tool.key)));
      }
      return [make('p', 'quiet', 'Each tool proposes changes. Preview each one, then apply, edit or skip it. Nothing changes until you apply, and the earlier text stays in History.'), list];
    };
    k.toolSays = (held, key) => {
      const job = held.view.working; if (job && job.kind === 'finish-' + key) return 'Working on it…';
      const set = (held.view.finishing || {})[key]; if (!set) return '';
      const open = set.items.filter(item => item.state === 'open').length;
      return open ? open + ' to review.' : 'Nothing left to review.';
    };
    k.toolView = (held, key) => {
      const tool = k.tool(key);
      if (tool.view) return tool.view(held);
      const view = held.view, f = held.finish, kind = 'finish-' + key, set = (view.finishing || {})[key], working = view.working;
      const parts = [make('p', 'quiet', tool.says)];
      if (tool.options) parts.push(...tool.options(held, f));
      const run = a.ui.button(set ? tool.run + ' again' : tool.run, control => k.job(held, control, a.routes.finish, { tool: key, ...(tool.data ? tool.data(f) : {}) }), 'filled');
      run.disabled = !a.canEdit(held) || !!working || (tool.ready ? !tool.ready(f) : false);
      parts.push(add(make('div', 'bar'), run));
      if (working && working.kind === kind) { const note = make('p', 'desk-working-note', tool.doing); note.setAttribute('role', 'status'); parts.push(note); }
      else if (working) parts.push(make('p', 'quiet', 'Another change is under way. This can run when it ends.'));
      const last = (view.jobs || []).filter(job => job.kind === kind).at(-1);
      if (last && !last.busy && last.error && (!set || set.job !== last.id)) parts.push(make('p', 'problem', last.error));
      if (set) parts.push(...k.proposals(held, key, set));
      return parts;
    };
    k.proposals = (held, key, set) => {
      const tool = k.tool(key), items = set.items, open = items.filter(item => item.state === 'open'), out = [];
      if (tool.comments) {
        if (set.summary) out.push(a.ui.card('Overall', make('p', '', set.summary)));
        if (!items.length) out.push(make('p', '', 'No comments.'));
        const order = ['whole', 'title', 'opening', ...(held.view.sections || []).map(section => section.id)];
        for (const item of [...items].sort((x, y) => order.indexOf(x.part) - order.indexOf(y.part))) out.push(k.comment(held, set, item, true));
        return out;
      }
      const checked = tool.verdicts ? open.filter(item => item.verdict !== 'supported') : open;
      const [one, many] = tool.counted || [' suggestion', ' suggestions'];
      const said = [items.length + (items.length === 1 ? one : many), checked.length + ' to review'];
      if (set.level) said.unshift('Found at ' + set.level);
      if (tool.said) tool.said(set, said);
      if (set.dropped) said.push(set.dropped + ' left out because ' + (set.dropped === 1 ? 'it did not' : 'they did not') + ' match the text');
      out.push(make('p', 'quiet', said.join(' · ') + '.'));
      if (!items.length) { out.push(make('p', '', tool.empty || 'Nothing to change at this level.')); return out; }
      // Apply all: every open proposal that still fits; flagged ones wait to be checked one by one.
      const ready = open.filter(item => item.present && !item.flag && 'after' in item);
      if (tool.applyAll && ready.length > 1) {
        const flagged = open.filter(item => item.flag).length;
        const all = a.ui.button('Apply all (' + ready.length + ')', control => k.apply(held, set, ready.map(item => ({ id: item.id })), control)); all.disabled = !a.canEdit(held) || !!held.view.working;
        out.push(add(make('div', 'bar'), all), flagged ? make('p', 'quiet', tool.flagged ? tool.flagged(flagged) : flagged + (flagged === 1 ? ' flagged suggestion is' : ' flagged suggestions are') + ' left for you to check one by one.') : null);
      }
      if (tool.groups) {
        for (const [part, name] of tool.groups) { const group = items.filter(item => item.part === part); if (group.length) out.push(make('h3', 'sheet-part', name + ' alternatives'), ...group.map(item => k.proposal(held, set, item, key))); }
        return out.filter(Boolean);
      }
      const supported = items.filter(item => item.verdict === 'supported');
      out.push(...items.filter(item => item.verdict !== 'supported').map(item => k.proposal(held, set, item, key)));
      if (supported.length) out.push(a.ui.disclosure('Supported (' + supported.length + ')', ...supported.map(item => k.proposal(held, set, item, key))));
      return out.filter(Boolean);
    };
    k.proposal = (held, set, item, key) => {
      const tool = k.tool(key), f = held.finish, card = make('section', 'card desk-proposal'); card.dataset.item = item.id;
      const head = add(make('div', 'desk-part-head'), make('h3', 'row-title', tool.groups ? 'Alternative' : 'In ' + a.parts.nameOf(held.view, item.part)));
      if (item.verdict) head.append(make('span', 'tag', (tool.verdicts || {})[item.verdict]));
      card.append(head);
      if (item.flag) card.append(make('p', 'decision-notice', item.flag));
      const editing = f.editing[item.id], hasAfter = 'after' in item;
      let sides = null;
      if (hasAfter || editing !== undefined) { sides = k.sides(item.before, editing !== undefined ? editing : item.after); card.append(sides); }
      else card.append(make('blockquote', 'desk-quote', item.before));
      if (item.note) card.append(make('p', 'quiet', item.note));
      if (item.verdict && item.verdict !== 'supported' && !item.passage) card.append(make('p', 'quiet', 'No passage in your sources says this.'));
      if (item.passage) card.append(make('p', 'quiet', 'From ' + (item.source || 'your sources') + ': “' + item.passage + '”'));
      if (item.state !== 'open') { card.append(make('p', 'quiet', item.state === 'applied' ? 'Applied. The earlier text is in History.' : item.state === 'retired' ? k.noLonger(item) : item.verdict ? 'Kept as it is.' : 'Skipped.')); return card; }
      const skip = a.ui.button(item.verdict ? 'Keep it' : 'Skip', control => k.skip(held, set, [item.id], control)); skip.disabled = !a.canEdit(held);
      if (!item.present) { card.append(make('p', 'quiet', 'The text changed since this was suggested, so it no longer fits.'), add(make('div', 'bar'), skip)); return card; }
      if (item.verdict === 'supported') return card;
      const editable = a.canEdit(held) && !held.view.working;
      if (editing !== undefined) {
        const box = make('textarea', 'input desk-edit'); box.id = 'desk-edit-' + item.id; box.rows = Math.min(12, Math.max(3, Math.ceil(editing.length / 60))); box.value = editing; box.setAttribute('aria-label', 'Your wording');
        box.addEventListener('input', () => { f.editing[item.id] = box.value; const next = k.sides(item.before, box.value); if (sides) sides.replaceWith(next); sides = next; });
        const use = a.ui.button('Apply this', control => k.apply(held, set, [{ id: item.id, after: f.editing[item.id] }], control), 'filled'); use.disabled = !editable;
        card.append(box, add(make('div', 'bar'), use, a.ui.button('Cancel', () => { delete f.editing[item.id]; k.panelShow(held); })));
        return card;
      }
      const edit = a.ui.button(hasAfter ? 'Edit' : 'Fix the wording', () => { f.editing[item.id] = hasAfter ? item.after : item.before; k.panelShow(held); }); edit.disabled = !editable;
      const apply = hasAfter ? a.ui.button(tool.groups ? 'Use this' : 'Apply', control => k.apply(held, set, [{ id: item.id }], control), 'filled') : null; if (apply) apply.disabled = !editable;
      const source = item.verdict && tool.source ? a.ui.button('Add a source', () => tool.source(held)) : null; if (source) source.disabled = !a.canEdit(held);
      card.append(add(make('div', 'bar'), apply, edit, source, skip));
      return card;
    };
    // Why a retired proposal no longer fits: the suggestion that changed its words, by the
    // number a screen gave it (`byNumber`), else the reason the studio kept with it.
    k.noLonger = item => {
      if (item.byNumber) return 'No longer fits: its words were changed by suggestion #' + item.byNumber + '.';
      const reason = String(item.reason || '');
      return reason ? 'No longer fits: ' + reason.charAt(0).toLowerCase() + reason.slice(1) : 'No longer fits: another change replaced these words.';
    };
    // What an apply did to the other proposals, when the studio says: the ones that took in
    // its words (`carried`), and the ones whose words it changed (`retired`).
    k.finishedSaid = done => {
      const carried = (done && done.carried) || 0, retired = (done && done.retired) || 0;
      return (carried ? ' ' + carried + (carried === 1 ? ' other suggestion was updated to fit.' : ' other suggestions were updated to fit.') : '') + (retired ? ' ' + retired + (retired === 1 ? ' suggestion no longer fits: its words were changed.' : ' suggestions no longer fit: their words were changed.') : '');
    };
    k.apply = async (held, set, items, control) => {
      await a.ui.busy(control, 'Applying…', async () => {
        try {
          await k.flush(held); if (held.stale) return;
          const before = held.view; held.view = await a.api(a.routes.apply, { id: held.id, seen: held.view.revision, job: set.job, items });
          for (const chosen of items) delete held.finish.editing[chosen.id];
          const done = held.view.finished || { applied: items.length, left: [] }, left = (done.left || []).length;
          a.ui.toast((done.applied === 1 ? 'Applied.' : 'Applied ' + done.applied + '.') + ' The earlier text is in History.' + k.finishedSaid(done) + (left ? ' ' + left + (left === 1 ? ' no longer fits and is' : ' no longer fit and are') + ' left for you.' : ''));
          a.hooks.refresh(held, before); k.panelShow(held);
        } catch (error) { if (stale(error)) { held.stale = true; k.stale(held); } else a.ui.notice(error.message, true); }
      });
    };
    k.skip = async (held, set, ids, control) => {
      await a.ui.busy(control, 'Setting aside…', async () => { try { const before = held.view; held.view = await a.api(a.routes.skip, { id: held.id, job: set.job, items: ids }); a.hooks.refresh(held, before); k.panelShow(held); } catch (error) { a.ui.notice(error.message, true); } });
    };
    // Feedback: comments shown in the panel and in their part's card, each a note in one click.
    k.commentKey = (view, part) => { const tool = commenting(), set = tool && (view?.finishing || {})[tool.key]; return set ? JSON.stringify(set.items.filter(item => item.part === part && item.state === 'open').map(item => item.id)) : ''; };
    k.comments = (held, part) => {
      const tool = commenting(), set = tool && (held.view.finishing || {})[tool.key]; if (!set) return null;
      const items = set.items.filter(item => item.part === part && item.state === 'open'); if (!items.length) return null;
      const box = make('div', 'desk-comments'); box.setAttribute('aria-label', 'Feedback on this part');
      box.append(make('h3', 'sheet-part', 'Feedback'), ...items.map(item => k.comment(held, set, item, false)));
      return box;
    };
    k.comment = (held, set, item, inPanel) => {
      const thing = a.words().thing, aspects = (commenting() || {}).comments || {};
      const card = make(inPanel ? 'section' : 'div', inPanel ? 'card desk-proposal desk-comment' : 'desk-comment'); card.dataset.item = item.id;
      if (inPanel) card.append(add(make('div', 'desk-part-head'), make('h3', 'row-title', item.part === 'whole' ? 'The whole ' + thing : 'In ' + a.parts.nameOf(held.view, item.part)), make('span', 'tag', aspects[item.aspect] || Object.values(aspects)[0])));
      if (item.quote) card.append(make('blockquote', 'desk-quote', item.quote));
      card.append(make('p', '', item.comment));
      if (item.state !== 'open') { card.append(make('p', 'quiet', 'Dismissed.')); return card; }
      const section = (held.view.sections || []).some(found => found.id === item.part), noted = (held.finish?.noted || {})[item.id];
      const turn = a.ui.button(noted ? 'In the note' : section ? 'Make it a note' : 'Make it the whole-' + thing + ' note', () => k.toNote(held, item)); turn.disabled = !a.canEdit(held);
      const dismiss = a.ui.button('Dismiss', control => k.skip(held, set, [item.id], control)); dismiss.disabled = !a.canEdit(held);
      card.append(add(make('div', 'bar'), turn, dismiss));
      return card;
    };
    // A comment made a note: added to whatever note is there already, never over it. The
    // parts are drawn on the `draft` tab.
    k.toNote = (held, item) => {
      const thing = a.words().thing, section = (held.view.sections || []).find(found => found.id === item.part);
      const comment = item.comment + (item.quote ? ' (About: “' + item.quote + '”)' : ''), join = had => (had.trim() ? had.replace(/\s+$/, '') + '\n\n' : '') + comment;
      if (section) { held.notes = held.notes || {}; held.notes[item.part] = join(held.notes[item.part] || '').slice(0, 4000); } else held.wholeNote = join(held.wholeNote || '').slice(0, 4000);
      if (held.finish) held.finish.noted[item.id] = true;
      if (held.finish && a.ui.narrow()) held.finish = null;  // On a phone the sheet steps aside for the note.
      const prepared = hook('noteTarget', held, item);
      if (prepared || held.tab !== 'draft' || !held.cards || (section && !held.cards[item.part]) || a.ui.narrow()) { held.tab = 'draft'; a.hooks.render(held); }
      else {
        if (section) { const card = k.part(held, item.part); held.cards[item.part].replaceWith(card); held.cards[item.part] = card; }
        else { const whole = k.whole(held); held.wholeCard.replaceWith(whole); held.wholeCard = whole; }
        k.panelShow(held);
      }
      const target = section ? held.cards?.[item.part]?.querySelector('.desk-note-text') : held.wholeCard?.querySelector('textarea');
      if (target) { target.focus(); if (typeof target.scrollIntoView === 'function') target.scrollIntoView({ block: 'center' }); }
      a.ui.toast(section ? 'Now the note for “' + section.heading + '”. Choose Rewrite when you are ready.' : 'Now the note for the whole ' + thing + '. Choose Revise the ' + thing + ' when you are ready.');
    };
    // Quick check (the key and route say proofread): in place, at once; Fix rewrites only the
    // sentence a finding is in.
    k.proofread = async (held, control) => {
      const go = async () => { try { await k.flush(held); const found = await a.api(a.routes.proofread + '?' + new URLSearchParams({ id: held.id })); if (!held.finish) return; held.finish.proof = found; held.finish.proofProblem = ''; } catch (error) { if (held.finish) held.finish.proofProblem = error.message; } k.panelShow(held); };
      if (control) await a.ui.busy(control, 'Checking…', go); else await go();
    };
    k.proofView = held => {
      const f = held.finish, found = f.proof;
      const again = a.ui.button(found ? 'Check again' : 'Check now', control => k.proofread(held, control), 'filled');
      const parts = [make('p', 'quiet', k.tool('proofread').says + ' Fix rewrites only the sentence a finding is in, and keeps the earlier text in History.'), add(make('div', 'bar'), again)];
      if (f.proofProblem) parts.push(make('p', 'problem', f.proofProblem));
      if (!found) return parts;
      if (found.revision !== held.view.revision) parts.push(make('p', 'quiet', 'The ' + a.words().thing + ' changed since this check. Check again for the latest.'));
      if (!found.findings.length) { parts.push(make('p', '', 'Nothing found by these checks.')); return parts; }
      parts.push(make('p', 'quiet', found.findings.length + (found.findings.length === 1 ? ' finding' : ' findings') + (found.more ? ', and ' + found.more + ' more' : '') + '. ' + found.limitations));
      for (const finding of found.findings) parts.push(k.finding(held, finding));
      return parts;
    };
    k.finding = (held, finding) => {
      const card = make('section', 'card desk-proposal');
      card.append(add(make('div', 'desk-part-head'), make('h3', 'row-title', 'In ' + a.parts.nameOf(held.view, finding.part))), make('p', '', finding.label));
      const said = make('p', 'desk-plain desk-quote'), at = finding.at - finding.start;
      if (at >= 0 && finding.sentence.slice(at, at + finding.target.length) === finding.target) said.append(document.createTextNode(finding.sentence.slice(0, at)), make('mark', '', finding.target), document.createTextNode(finding.sentence.slice(at + finding.target.length)));
      else said.textContent = finding.sentence;
      const still = a.parts.textOf(held.view, finding.part).slice(finding.start, finding.start + finding.sentence.length) === finding.sentence;
      const fix = a.ui.button('Fix', control => k.job(held, control, a.routes.selection, { part: finding.part, text: finding.sentence, start: finding.start, action: 'fix', instruction: finding.fix })); fix.disabled = !a.canEdit(held) || !!held.view.working || !still;
      return add(card, said, add(make('div', 'bar'), fix), still ? null : make('p', 'quiet', 'This sentence changed since the check.'));
    };
    // Where Finishing sits: a full-screen sheet on a phone, a drawer below 1100 pixels, else
    // beside the draft.
    k.floating = () => a.ui.narrow() || (typeof window === 'object' && typeof window.matchMedia === 'function' && !!window.matchMedia('(max-width: 1099px)').matches);
    k.layout = () => a.ui.narrow() ? 'phone' : k.floating() ? 'drawer' : 'wide';

    return k;
  }

  return { DIFF_LIMIT, SAVE_WAIT, POLL, SELECTION, make, add, words, diffWords, age, kit, slideContent };
})();
if (typeof module === 'object' && module.exports) module.exports = Drafting;
