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
      const run = (action, instruction = '') => async control => { const chosen = held.selection; if (!chosen) return; await a.hooks.job(held, control, a.routes.selection, { part: chosen.part, text: chosen.text, start: chosen.start, action, ...(action === 'ask' ? { instruction } : {}) }, () => { held.selection = null; held.asking = false; }); };
      if (held.asking) {
        const box = make('input', 'input'); box.type = 'text'; box.maxLength = 2000; box.placeholder = 'What should change?'; box.setAttribute('aria-label', 'What should change in the selected text?');
        bar.replaceChildren(box, a.ui.button('Go', async control => { const instruction = box.value.trim(); if (!instruction) { a.ui.notice('Say what to do with the passage.', true); return; } await run('ask', instruction)(control); }, 'filled'), a.ui.button('Cancel', () => { held.asking = false; bar.hidden = true; }));
        return;
      }
      bar.replaceChildren(...SELECTION.map(([action, label]) => a.ui.button(label, run(action))), a.ui.button('Ask…', () => { held.asking = true; k.barContent(held); }));
    };

    return k;
  }

  return { DIFF_LIMIT, SAVE_WAIT, POLL, SELECTION, make, add, words, diffWords, age, kit };
})();
if (typeof module === 'object' && module.exports) module.exports = Drafting;
