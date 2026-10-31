/* The Document Library sheet (core/studio_core/deck_web/library.js) with a synthetic
 * adapter only: no studio, no library folder, no network. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');

let document;
class Node {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.parent = null; this.dataset = {}; this.listeners = {};
    this.value = ''; this.className = ''; this.textContent = ''; this.disabled = false; this.checked = false;
    this.attributes = {}; this.open = false;
    const node = this;
    this.classList = { add: (c) => { if (!node.className.split(' ').includes(c)) node.className = (node.className + ' ' + c).trim(); },
      contains: (c) => node.className.split(' ').includes(c) };
  }
  append(...nodes) { for (let n of nodes) { if (typeof n === 'string') n = Object.assign(new Node('#text'), { textContent: n }); if (n.parent) n.parent.children = n.parent.children.filter((c) => c !== n); n.parent = this; this.children.push(n); } }
  prepend(n) { this.append(n); this.children.unshift(this.children.pop()); }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  addEventListener(k, fn) { this.listeners[k] = fn; }
  replaceChildren(...nodes) { for (const c of this.children) c.parent = null; this.children = []; this.append(...nodes); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this); this.parent = null; }
  contains(n) { return this === n || this.children.some((c) => c.contains(n)); }
  focus() { document.activeElement = this; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  get text() { return this.textContent + this.children.map((c) => c.text).join(''); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    const chain = selector.trim().split(/\s+/);
    return all(this).filter((n) => matches(n, chain[chain.length - 1]) && ancestors(n, chain.slice(0, -1), this));
  }
}
function all(n) { return n.children.flatMap((c) => [c, ...all(c)]); }
function matches(n, simple) {
  const key = simple.match(/^\[data-key="(.*)"\]$/);
  if (key) return n.dataset.key === key[1];
  if (simple.startsWith('#')) return n.id === simple.slice(1);
  if (simple.startsWith('.')) return n.className.split(' ').includes(simple.slice(1));
  return n.tagName === simple;
}
function ancestors(n, chain, top) {
  if (!chain.length) return true;
  for (let up = n.parent; up && up !== top.parent; up = up.parent) if (matches(up, chain[chain.length - 1])) return ancestors(up, chain.slice(0, -1), top);
  return false;
}
document = { createElement: (t) => new Node(t), body: new Node('body'), activeElement: null };
const opener = new Node('button');
document.body.append(opener);
const context = vm.createContext({ document, JSON, Object, Array, String, Number, Math, Set, Map, Promise, Error, Date, isNaN });
context.window = context;
const source = fs.readFileSync(path.join(__dirname, '../core/studio_core/deck_web/library.js'), 'utf8');
assert.ok(!/innerHTML|insertAdjacentHTML|outerHTML/.test(source), 'Titles and passages are set as text only');
vm.runInContext(source, context);
const kit = context.StudioLibrary;
const settle = async () => { for (let n = 0; n < 60; n++) await Promise.resolve(); };
const find = (node, key) => all(node).find((n) => n.dataset.key === key);
const click = async (node) => { assert.ok(node, 'the control is there'); assert.ok(!node.disabled, 'the control is enabled'); node.listeners.click(); await settle(); };
const tick = async (node, on) => { node.checked = on; node.listeners.change(); await settle(); };

const docs = [];
for (let i = 0; i < 30; i++) {
  docs.push({ id: 'doc-' + i, revision: 1 + (i % 2), title: 'Synthetic <b>document</b> ' + i, kind: i % 2 ? 'blog' : 'upload',
    kind_label: i % 2 ? 'Blog' : 'Uploaded document', studio: i % 2 ? 'blog' : 'marketing', studio_label: i % 2 ? 'Blog Studio' : 'Marketing Studio',
    updated_at: '2026-10-30T10:00:00Z', formats: ['markdown'], format_labels: ['Markdown'], readable: i !== 3,
    state: i === 3 ? 'needs-text' : 'readable', state_label: i === 3 ? 'Needs text' : 'Readable', problem: i === 3 ? 'It has no readable text yet.' : null });
}
const requests = [];
let remembered = { kind: 'upload' };
const hidden = new Set();
async function post(route, body) {
  requests.push([route, JSON.parse(JSON.stringify(body))]);
  if (route === 'library') {
    const f = body.filters || {};
    const rows = docs.filter((d) => (!f.kind || d.kind === f.kind) && (!f.query || d.title.includes(f.query))
      && (body.hidden || !hidden.has(d.id))).map((d) => ({ ...d, hidden: hidden.has(d.id) }));
    const answer = { available: true, items: rows.slice(body.offset, body.offset + body.limit), total: rows.length, offset: body.offset,
      limit: body.limit, remembered, hidden: hidden.size, kinds: { upload: 'Uploaded document', blog: 'Blog' }, studios: { blog: 'Blog Studio' }, origins: {}, states: {} };
    return answer;
  }
  if (route === 'library-hide') { if (body.hidden) hidden.add(body.id); else hidden.delete(body.id); return { document: { id: body.id, hidden: body.hidden } }; }
  if (route === 'library-document') return { ...docs.find((d) => d.id === body.id), text: '<script>not run</script> words', truncated: false, characters: 30, gaps: [] };
  if (route === 'library-matching') {
    if (body.filters.kind !== 'blog') throw new Error('30 documents match. Narrow the filters.');
    return { matching: docs.filter((d) => d.kind === 'blog').slice(0, 3).map((d) => ({ id: d.id, revision: d.revision })) };
  }
  if (route === 'library-filters') { remembered = body.filters; return { remembered }; }
  throw new Error('unknown route ' + route);
}

(async () => {
  // Browsing (Marketing Studio): a remembered filter is applied once and selects nothing.
  const downloads = [], said = [];
  const browse = new kit.Catalog({ studio: 'marketing', post, manage: true, said: (text) => said.push(text),
    download: (row, format) => downloads.push([row.id, format]) });
  await settle();
  assert.deepEqual(requests.map((r) => r[0]), ['library', 'library']);
  assert.deepEqual(requests[1][1].filters, { kind: 'upload' });
  assert.equal(browse.ticked.size, 0);
  assert.equal(all(browse.node).filter((n) => n.type === 'checkbox').length, 0, 'browsing has no ticks, and nothing is hidden yet');
  // One action a row: Preview. The downloads are in the preview, two activations away.
  const rows = all(browse.node).filter((n) => n.className === 'library-row');
  assert.ok(rows.length > 1);
  for (const row of rows) assert.deepEqual(all(row).filter((n) => n.tagName === 'button').map((n) => n.textContent), ['Preview']);
  assert.ok(!find(browse.node, 'library-download-markdown-doc-0'), 'no download on the row');
  // On a phone, Filters opens the rest and counts those set: the remembered Type is one.
  const toggle = find(browse.node, 'library-filters-toggle');
  assert.equal(toggle.textContent, 'Filters (1)');
  assert.equal(toggle.attributes['aria-expanded'], 'false');
  assert.ok(toggle.className.split(' ').includes('filters-toggle'));
  toggle.focus(); await click(toggle);
  const bar = all(browse.node).find((n) => n.tagName === 'form');
  assert.ok(bar.className.split(' ').includes('filters-open'), 'Filters opens the filter row');
  assert.ok(find(browse.node, 'library-more').open, 'with Origin, Status and Author');
  assert.equal(find(browse.node, 'library-filters-toggle').attributes['aria-expanded'], 'true');
  assert.equal(document.activeElement.dataset.key, 'library-filters-toggle', 'focus stays on Filters');
  assert.equal(find(browse.node, 'library-kind').value, 'upload', 'the remembered filter still applies');
  // Preview opens just below its row; Close preview lands on the same row's Preview.
  const listOf = () => all(browse.node).find((n) => n.className === 'library-list');
  const opener6 = find(browse.node, 'library-preview-doc-10');
  opener6.focus(); await click(opener6);
  const items = listOf().children;
  const at = items.findIndex((n) => n.dataset.key === 'library-row-doc-10');
  assert.equal(items[at + 1].className, 'library-preview-item', 'the preview is the next item after its row');
  assert.equal(find(browse.node, 'library-preview-doc-10').attributes['aria-expanded'], 'true');
  assert.equal(document.activeElement.dataset.key, 'library-preview-heading', 'focus moves to the preview');
  await click(find(browse.node, 'library-download-markdown-doc-10'));
  assert.deepEqual(downloads, [['doc-10', 'markdown']]);
  await click(find(browse.node, 'library-preview-close'));
  assert.ok(!all(browse.node).some((n) => n.className === 'library-preview-item'));
  assert.equal(document.activeElement.dataset.key, 'library-preview-doc-10', 'focus returns to the row');
  // Remove from library says what it does, confirms in place, and hides; Restore undoes it.
  await click(find(browse.node, 'library-preview-doc-10'));
  await click(find(browse.node, 'library-remove-doc-10'));
  assert.equal(document.activeElement.dataset.key, 'library-remove-cancel', 'the safe choice has focus');
  assert.match(all(browse.node).find((n) => n.className === 'library-removal').text, /Nothing is deleted.*projects that already use it keep their copy/);
  await click(find(browse.node, 'library-remove-cancel'));
  assert.equal(hidden.size, 0, 'Keep it changes nothing');
  await click(find(browse.node, 'library-remove-doc-10'));
  await click(find(browse.node, 'library-remove-confirm'));
  assert.deepEqual(requests.find((r) => r[0] === 'library-hide')[1], { id: 'doc-10', hidden: true });
  assert.ok(!find(browse.node, 'library-row-doc-10'), 'a removed document leaves the list');
  assert.equal(document.activeElement.dataset.key, 'library-preview-doc-12', 'focus goes to the next row');
  assert.match(said.at(-1), /removed from the library. Projects that use it keep their copy/);
  const show = find(browse.node, 'library-show-hidden');
  assert.ok(show, 'Show hidden appears once something is hidden');
  show.checked = true; show.listeners.change(); await settle();
  assert.equal(requests.at(-1)[1].hidden, true);
  assert.ok(find(browse.node, 'library-row-doc-10'), 'Show hidden lists it');
  await click(find(browse.node, 'library-preview-doc-10'));
  await click(find(browse.node, 'library-restore-doc-10'));
  assert.equal(hidden.size, 0);
  assert.match(said.at(-1), /is back in the library/);
  assert.equal(document.activeElement.dataset.key, 'library-preview-doc-10');
  const plain = new kit.Catalog({ studio: 'blog', post, download: () => {} });
  await settle();
  await click(find(plain.node, 'library-preview-doc-0'));
  assert.ok(!find(plain.node, 'library-remove-doc-0'), 'only Marketing Studio removes documents');

  // The sheet: open, tick, page, change filters, keep ticks, cancel changes nothing.
  remembered = {};
  requests.length = 0;
  opener.focus();
  const used = [];
  let refuse = true;
  const adapter = { studio: 'presentation', post, max: 40, roles: [['facts', 'Facts'], ['example', 'Example']],
    use: async (picks) => { used.push(JSON.parse(JSON.stringify(picks))); if (refuse) { refuse = false; throw new Error('"Synthetic" is already in this deck.'); } } };
  const first = kit.pick(adapter);
  await settle();
  const sheet = document.body.children.find((n) => n.tagName === 'dialog');
  assert.ok(sheet && sheet.open, 'the sheet opens as a modal dialog');
  assert.equal(document.activeElement.dataset.key, 'library-query', 'focus starts in the search');
  assert.ok(all(sheet).filter((n) => n.id).every((n) => n.id.startsWith('doclib')), 'IDs are the sheet\'s own');
  assert.ok(all(sheet).filter((n) => n.htmlFor).every((n) => all(sheet).some((m) => m.id === n.htmlFor)), 'every label names a field in the sheet');
  assert.ok(find(sheet, 'library-use').disabled, 'Use selected waits for a tick');
  assert.ok(find(sheet, 'library-tick-doc-3').disabled, 'an unreadable revision cannot be ticked');
  assert.ok(all(sheet).some((n) => n.textContent === 'Synthetic <b>document</b> 0'), 'a title is text');
  await tick(find(sheet, 'library-tick-doc-0'), true);
  assert.match(all(sheet).find((n) => n.className === 'selection-count').text, /1 selected/);
  await click(find(sheet, 'library-next'));
  assert.equal(requests.at(-1)[1].offset, 25);
  assert.match(all(sheet).find((n) => n.className === 'selection-count').text, /1 of them is not in this view/);
  // A filter change keeps the tick and is remembered as a filter only.
  // Text typed in the search but not searched yet survives a filter change and a tick.
  const box = find(sheet, 'library-query');
  box.value = 'Synth'; box.listeners.input();
  const kind = find(sheet, 'library-kind');
  kind.value = 'blog'; kind.listeners.change(); await settle();
  assert.equal(find(sheet, 'library-query').value, 'Synth');
  assert.equal(find(sheet, 'library-filters-toggle').textContent, 'Filters (1)', 'the sheet has Filters too, counting the Type');
  assert.equal(requests.at(-1)[1].filters.query, undefined, 'not searched until Search');
  assert.deepEqual(requests.find((r) => r[0] === 'library-filters')[1].filters, { kind: 'blog', studio: '', origin: '', state: '' });
  assert.equal(requests.at(-1)[1].offset, 0);
  assert.match(all(sheet).find((n) => n.className === 'selection-count').text, /1 selected/);
  // Select all matching is bounded by the server, with the current filters.
  await click(find(sheet, 'library-all-matching'));
  assert.deepEqual(requests.at(-1), ['library-matching', { filters: { kind: 'blog' } }]);
  assert.match(all(sheet).find((n) => n.className === 'selection-count').text, /4 selected/);
  // A preview is plain text.
  await click(find(sheet, 'library-preview-doc-1'));
  const passage = all(sheet).find((n) => n.className === 'library-preview-text');
  assert.equal(passage.textContent, '<script>not run</script> words');
  assert.equal(passage.children.length, 0);
  assert.ok(!all(sheet).some((n) => /^library-(remove|restore|download|show-hidden)/.test(n.dataset.key || '')), 'the sheet only chooses');
  // A role per ticked document, the first role by default.
  const role = find(sheet, 'library-role-doc-1');
  role.value = 'example'; role.listeners.change();
  // Use selected: a refusal keeps the sheet open, with the reason and the ticks.
  await click(find(sheet, 'library-use'));
  assert.ok(sheet.open);
  assert.ok(all(sheet).some((n) => n.className === 'problem' && /already in this deck/.test(n.textContent)));
  assert.equal(used[0].length, 4);
  assert.deepEqual(used[0].find((p) => p.id === 'doc-1'), { id: 'doc-1', revision: 2, role: 'example' });
  assert.deepEqual(used[0].find((p) => p.id === 'doc-0'), { id: 'doc-0', revision: 1, role: 'facts' });
  await click(find(sheet, 'library-use'));
  assert.equal(await first, true);
  assert.ok(!sheet.open && !document.body.children.includes(sheet), 'the sheet is gone');
  assert.equal(document.activeElement, opener, 'focus returns to what opened it');

  // Cancel, Close and Escape change nothing.
  for (const how of ['library-cancel', 'library-close', 'escape']) {
    const before = used.length;
    const again = kit.pick(adapter);
    await settle();
    const open = document.body.children.find((n) => n.tagName === 'dialog');
    // The studio's remembered filter is back (Blog); nothing is ticked until the person ticks.
    assert.equal(find(open, 'library-kind').value, 'blog');
    assert.ok(find(open, 'library-use').disabled);
    await tick(find(open, 'library-tick-doc-1'), true);
    if (how === 'escape') { let prevented = false; open.listeners.cancel({ preventDefault: () => { prevented = true; } }); assert.ok(prevented); }
    else await click(find(open, how));
    assert.equal(await again, false, how + ' resolves without a choice');
    assert.equal(used.length, before, how + ' sends nothing');
  }
  // A studio names its own work, and a row it cannot use (its own kept export) is shown as
  // unavailable: it cannot be ticked, and Select all matching leaves it out.
  {
    const own = kit.pick({ ...adapter, noun: 'infographic',
      unavailable: (row) => (row.id === 'doc-1' ? { label: 'This infographic', detail: 'Its own approved page cannot be a source for it.' } : null) });
    await settle();
    const open = document.body.children.find((n) => n.tagName === 'dialog');
    assert.ok(all(open).some((n) => /^Choose documents for this infographic only\..*A new infographic starts with none\.$/.test(n.textContent)));
    const box = find(open, 'library-tick-doc-1');
    assert.ok(box.disabled, 'its own export cannot be ticked');
    assert.equal(box.attributes['aria-label'], 'Synthetic <b>document</b> 1 is unavailable: This infographic');
    assert.ok(all(open).some((n) => n.textContent === 'This infographic'));
    // Select all on this page leaves it out too.
    await tick(find(open, 'library-select-page'), true);
    assert.ok(!find(open, 'library-tick-doc-1').checked, 'select page skips its own export');
    assert.ok(find(open, 'library-tick-doc-5').checked);
    await tick(find(open, 'library-select-page'), false);
    await tick(find(open, 'library-tick-doc-5'), true);
    await click(find(open, 'library-all-matching'));
    assert.match(all(open).find((n) => n.className === 'selection-count').text, /2 selected/);
    await click(find(open, 'library-cancel'));
    assert.equal(await own, false);
    const plainSheet = kit.pick(adapter);
    await settle();
    const usual = document.body.children.find((n) => n.tagName === 'dialog');
    assert.ok(all(usual).some((n) => /^Choose documents for this project only\./.test(n.textContent)), 'the default noun is project');
    assert.ok(!find(usual, 'library-tick-doc-1').disabled);
    await click(find(usual, 'library-cancel'));
    assert.equal(await plainSheet, false);
  }
  // While Use selected is landing, Cancel, Close and Escape wait; then focus goes where the
  // page says (its redrawn Add from library).
  let land;
  const target = new Node('button');
  document.body.append(target);
  const slow = kit.pick({ ...adapter, use: () => new Promise((resolve) => { land = resolve; }), refocus: () => target });
  await settle();
  const busy = document.body.children.find((n) => n.tagName === 'dialog');
  await tick(find(busy, 'library-tick-doc-1'), true);
  find(busy, 'library-use').listeners.click(); await settle();
  assert.ok(find(busy, 'library-cancel').disabled && find(busy, 'library-close').disabled);
  find(busy, 'library-cancel').listeners.click();
  find(busy, 'library-close').listeners.click();
  busy.listeners.cancel({ preventDefault: () => {} });
  await settle();
  assert.ok(busy.open, 'the sheet stays while the choice lands');
  land(); assert.equal(await slow, true);
  assert.equal(document.activeElement, target, 'focus goes to the redrawn Add from library');

  // Only the newest load is drawn: an older, slower answer is ignored.
  const waiting = [];
  const racing = new kit.Catalog({ studio: 'blog', post: (route, body) => new Promise((resolve) => waiting.push([body, resolve])) });
  racing.filters.kind = 'blog'; racing.load();
  await settle();
  const answer = (rows) => ({ available: true, items: rows, total: rows.length, offset: 0, limit: 25, remembered: {} });
  waiting[1][1](answer([docs[1]]));
  await settle();
  waiting[0][1](answer([docs[0], docs[2]]));
  await settle();
  assert.deepEqual(racing.shownIds(), ['doc-1'], 'a late answer from an older load is not drawn');
  console.log('library page check passed');
})().catch((error) => { console.error(error); process.exit(1); });
