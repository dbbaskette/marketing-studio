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

    return k;
  }

  return { DIFF_LIMIT, SAVE_WAIT, POLL, make, add, words, diffWords, age, kit };
})();
if (typeof module === 'object' && module.exports) module.exports = Drafting;
