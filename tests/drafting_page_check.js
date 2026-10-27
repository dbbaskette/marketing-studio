// Runs the shared desk kit, ui-kit/drafting.js, without a browser, for test_drafting_page.py.
//
//   node drafting_page_check.js GROUP
//
// The document is a small stand-in: elements keep their children, class, text, attributes
// and listeners. The adapter is a studio that is not Blog Studio: its controls are plain
// elements of its own, its requests answer from a script and are recorded, and its words
// name a "piece". Each group asserts with node:assert and exits 1 on the first failure.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor(tag = 'div') {
    this.tagName = tag; this.children = []; this.attributes = {}; this.listeners = {};
    this.dataset = {}; this.hidden = false; this.disabled = false; this.readOnly = false;
    this.value = ''; this.className = ''; this._text = ''; this.parent = null;
  }
  get textContent() { return this.children.length ? this.children.map(c => c.textContent).join('') : this._text; }
  set textContent(value) { this.children = []; this._text = String(value); }
  append(...nodes) { for (const node of nodes) { if (node.parent) node.remove(); node.parent = this; this.children.push(node); } }
  prepend(...nodes) { for (const node of nodes) node.parent = this; this.children.unshift(...nodes); }
  replaceChildren(...nodes) { for (const child of this.children) child.parent = null; this.children = []; this._text = ''; this.append(...nodes); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(c => c !== this); this.parent = null; }
  replaceWith(node) { const parent = this.parent; if (!parent) return; const at = parent.children.indexOf(this); if (node.parent) node.remove(); parent.children[at] = node; node.parent = parent; this.parent = null; }
  before(...nodes) { this.place(nodes, 0); }
  after(...nodes) { this.place(nodes, 1); }
  place(nodes, offset) { const parent = this.parent; if (!parent) return; for (const node of nodes) if (node.parent) node.remove(); parent.children.splice(parent.children.indexOf(this) + offset, 0, ...nodes); for (const node of nodes) node.parent = parent; }
  contains(node) { return node === this || all(this).includes(node); }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return key in this.attributes ? this.attributes[key] : null; }
  removeAttribute(key) { delete this.attributes[key]; }
  addEventListener(kind, fn) { (this.listeners[kind] ||= []).push(fn); }
  async fire(kind) { for (const fn of this.listeners[kind] || []) await fn({ target: this, preventDefault() {} }); }
  querySelectorAll(selector) { return all(this).filter(node => matches(node, selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  focus() { context.document.activeElement = this; }
  scrollIntoView() {}
}
function all(node) { return node.children.flatMap(child => [child, ...all(child)]); }
function classes(node) { return String(node.className || '').split(' ').filter(Boolean); }
function matches(node, selector) {
  if (selector.startsWith('.')) return selector.slice(1).split('.').every(name => classes(node).includes(name));
  const [tag, cls] = selector.split('.');
  return node.tagName === tag && (!cls || classes(node).includes(cls));
}

// The kit's values come from another realm: compare them as plain data.
const same = (actual, expected, message) => assert.deepEqual(JSON.parse(JSON.stringify(actual)), expected, message);
const timers = new Map();
const document = {
  activeElement: null,
  createElement: tag => new Element(tag),
  createTextNode: text => { const node = new Element('#text'); node.textContent = text; return node; },
};
const context = vm.createContext({
  document, console, Date, JSON, Math, Promise, Error, Object, Array, String, Number, Uint16Array, Proxy, Set, Map, URLSearchParams,
  setTimeout: (fn, ms) => { const id = ++timerId; timers.set(id, { fn, ms }); return id; },
  clearTimeout: id => { timers.delete(id); },
  window: {},
});
let timerId = 0;
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'ui-kit', 'drafting.js'), 'utf8'), context);
const Drafting = vm.runInContext('Drafting', context);

// Run the timers queued so far (not the ones they queue), and wait for what they started.
async function tick() { const due = [...timers.entries()]; for (const [id] of due) timers.delete(id); for (const [, timer] of due) await timer.fn(); await settle(); }
const waiting = () => [...timers.values()].map(timer => timer.ms);
async function settle() { for (let i = 0; i < 20; i++) await Promise.resolve(); }
const texts = node => all(node).map(n => n.textContent);
const find = (node, test) => all(node).find(test);
const button = (node, label) => find(node, n => n.tagName === 'button' && n.textContent === label);

// A studio that is not Blog Studio: its own controls, requests, words and tools.
function studio(answers = {}) {
  const said = { requests: [], toasts: [], notices: [], sheets: [], renders: 0, reloads: 0, refreshes: 0, before: 0, flushed: 0, saved: [], jobs: [], extras: [], started: [], shows: 0 };
  const own = (tag, cls, text) => { const node = new Element(tag); node.className = cls; if (text !== undefined) node.textContent = text; return node; };
  const page = own('main', 'piece-page');
  let narrow = false;
  const a = {
    ui: {
      button: (label, action, kind = '') => { const node = own('button', 'piece-button' + (kind ? ' piece-' + kind : ''), label); node.addEventListener('click', () => action(node)); return node; },
      card: (title, ...nodes) => { const node = own('section', 'card'); node.append(own('h2', 'card-title', title), ...nodes.filter(Boolean)); return node; },
      pickCard: (title, says, action) => { const node = own('button', 'piece-pick', title); node.append(own('span', 'piece-says', says)); node.addEventListener('click', () => action(node)); return node; },
      choice: (label, options, held, key) => { const node = own('div', 'piece-choice'); node.setAttribute('aria-label', label); for (const [value, text] of options) { const b = own('button', 'piece-option', text); b.addEventListener('click', () => { held[key] = value; }); node.append(b); } return node; },
      disclosure: (label, ...nodes) => { const node = own('details', ''); node.append(own('summary', '', label), ...nodes); return node; },
      bead: state => { const node = own('span', 'piece-bead'); node.dataset.state = state; return node; },
      openSheet: (title, ...nodes) => { const sheet = own('div', 'piece-sheet'); sheet.append(own('h2', '', title), ...nodes.filter(Boolean)); said.sheets.push({ title, sheet, open: true }); },
      closeSheet: () => { for (const sheet of said.sheets) sheet.open = false; },
      toast: text => said.toasts.push(text),
      notice: (text, isError) => said.notices.push([text, !!isError]),
      busy: async (control, label, action) => { control.disabled = true; try { await action(); } finally { control.disabled = false; } },
      narrow: () => narrow,
    },
    api: async (route, data) => {
      said.requests.push({ route, data });
      const answer = answers[route.split('?')[0]];
      const value = typeof answer === 'function' ? await answer(data, route) : answer;
      if (value instanceof Error) throw value;
      return value === undefined ? {} : value;
    },
    routes: { view: 'piece', save: 'piece-save', versions: 'piece-versions', restore: 'piece-restore', note: 'piece-note', revise: 'piece-revise', selection: 'piece-selection', stop: 'piece-stop', retry: 'piece-retry', finish: 'piece-finish', apply: 'piece-apply', skip: 'piece-skip', proofread: 'piece-proofread' },
    share: id => { said.requests.push({ route: 'share', data: { id } }); },
    canEdit: () => a.editable !== false,
    current: () => true,
    page: () => page,
    hooks: {
      render: () => { said.renders++; },
      refresh: () => { said.refreshes++; },
      reload: () => { said.reloads++; },
      beforeJob: async () => { said.before++; },
      beforeFlush: async () => { said.flushed++; },
      saved: async (held, part, text) => { said.saved.push([part, text]); },
      versionNote: version => (version.divided || []).length ? 'A note on ' + version.divided.length : '',
      job: async (held, control, route, data, done) => { said.jobs.push([route, data]); if (done) done(); },
      extra: (held, part) => { said.extras.push(part); return own('div', 'piece-extra'); },
      left: () => {},
      started: (held, shown) => { said.started.push(shown.start.open); held.tab = shown.start.open; },
    },
    parts: {
      title: (view, part) => part === 'title' ? 'Name' : part === 'opening' ? 'Lead' : ((view.sections || []).find(s => s.id === part) || {}).heading,
      textOf: (view, part) => part === 'title' || part === 'opening' ? view[part] || '' : ((view.sections || []).find(s => s.id === part) || {}).text || '',
      nameOf: (view, part) => part === 'title' ? 'the name' : '“' + (((view.sections || []).find(s => s.id === part) || {}).heading || part) + '”',
      single: part => part === 'title',
      noted: (view, part) => (view.sections || []).some(s => s.id === part),
    },
    words: () => ({ thing: 'piece', sources: { save: 'Before your edit', rewrite: 'Before a rewrite' }, doing: { 'piece-section': 'Rewriting', 'piece-whole': 'Revising the piece' }, steps: { gather: 'Gathering', write: 'Writing' }, named: ['piece-section'], ready: tab => tab === 'plan' ? 'The plan is ready.' : 'The piece is ready.' }),
    tools: () => a.toolList || [],
    progress: {
      stopped: held => { const node = own('div', 'piece-stopped'); node.append(own('p', '', held.view.start.problem), a.ui.button('Try again', () => {})); return node; },
      show: () => { said.shows++; },
    },
  };
  return { a, said, page, setNarrow: value => { narrow = value; } };
}

const groups = {
  async diff() {
    same(Drafting.diffWords('one two three', 'one 2 three').map(p => p.op), ['same', 'removed', 'added', 'same']);
    assert.equal(Drafting.diffWords('a '.repeat(5000), 'b'), null);
    same([...Drafting.words('  one  two ')], ['one', 'two']);
    assert.equal(Drafting.DIFF_LIMIT, 4000); assert.equal(Drafting.SAVE_WAIT, 1000); assert.equal(Drafting.POLL, 3000);
    const { a } = studio(), kit = Drafting.kit(a);
    const box = kit.compare('one two three', 'one 2 three');
    assert.equal(box.className, 'paper desk-compare');
    const plain = box.querySelector('p.desk-plain');
    assert.equal(plain.getAttribute('aria-label'), 'Changes from this version to the current text');
    same(plain.querySelectorAll('del.diff-remove').map(n => n.textContent), ['two']);
    same(plain.querySelectorAll('ins.diff-add').map(n => n.textContent), ['2']);
    const wide = kit.compare('a '.repeat(5000), 'b');
    same(wide.querySelectorAll('.desk-side').map(n => n.children[0].textContent), ['Before', 'Now']);
    const sides = kit.sides('one two', 'one 2');
    assert.equal(sides.className, 'desk-sides');
    same(sides.querySelectorAll('.desk-side').map(n => n.children[0].textContent), ['Before', 'After']);
    assert.equal(kit.sides('', 'x').querySelectorAll('p.desk-plain')[0].textContent, '(Nothing yet)');
    assert.equal(kit.sides('x', ' ').querySelectorAll('p.desk-plain')[1].textContent, '(Removed)');
    assert.equal(Drafting.age(new Date(Date.now() - 3600_000).toISOString()), '1 hour ago');
    assert.equal(Drafting.age(new Date().toISOString()), 'just now');
    assert.equal(Drafting.age(''), '');
    const made = Drafting.make('p', 'quiet', 'Hello');
    assert.equal(made.className, 'quiet'); assert.equal(made.textContent, 'Hello');
    assert.equal(Drafting.make('p').className, '');
    assert.equal(Drafting.add(Drafting.make('div'), null, made, undefined).children.length, 1);
  },
  async lazy() {
    // Building the kit reads nothing of the adapter, so a studio may pass members it defines later.
    Drafting.kit(new Proxy({}, { get() { throw new Error('read'); } }));
  },
  async autosave() {
    let answer = data => view({ revision: 4 });
    const { a, said, page } = studio({ 'piece-save': data => answer(data) });
    const kit = Drafting.kit(a), held = desk(kit);
    page.append(held.status);
    kit.typed(held, 'opening', 'A new lead.');
    assert.equal(held.status.textContent, 'Saving…');
    same(waiting(), [1000]);
    await tick();
    same(said.requests, [{ route: 'piece-save', data: { id: 'p1', seen: 3, part: 'opening', text: 'A new lead.', session: 'a'.repeat(16) } }]);
    assert.equal(held.status.textContent, 'Saved.');
    assert.equal(held.view.revision, 4);
    assert.equal(held.pending.opening, undefined);
    same(said.saved, [['opening', 'A new lead.']]);
    // A second edit while a save is under way is sent after it, against the revision it saw.
    let release; answer = () => new Promise(done => { release = () => done(view({ revision: 5 })); });
    said.requests.length = 0;
    kit.typed(held, 'opening', 'One.'); await tick();
    kit.typed(held, 'opening', 'Two.'); await tick();
    assert.equal(said.requests.length, 1);
    answer = () => view({ revision: 6 });
    release(); await settle(); await settle();
    same(said.requests.map(r => [r.data.text, r.data.seen]), [['One.', 4], ['Two.', 5]]);
    // A refusal because the draft changed elsewhere shows the banner with Reload.
    answer = () => new Error('This draft changed since you opened it. Reload to see the latest.');
    kit.typed(held, 'opening', 'Three.'); await tick();
    assert.equal(held.stale, true);
    assert.equal(held.status.className, 'desk-save-state decision-notice desk-stale');
    assert.equal(held.status.children[0].textContent, 'This piece changed in another window or job. Reload to see the latest; your unsaved text is shown until you do. ');
    await button(held.status, 'Reload').fire('click');
    assert.equal(said.reloads, 1);
    // Any other refusal keeps the text and says why.
    const other = desk(kit); page.append(other.status);
    answer = () => new Error('The disk is full.');
    kit.typed(other, 'opening', 'Four.'); await tick();
    assert.equal(other.status.textContent, 'The disk is full. Your text is kept here.');
    // Flush sends what waits, after the studio's own step; History counts follow the view.
    const third = desk(kit); answer = () => view({ revision: 4, versions: { opening: 2 } });
    kit.typed(third, 'opening', 'Five.'); said.requests.length = 0;
    const card = Drafting.make('section', 'card desk-part'); card.dataset.part = 'opening';
    card.append(a.ui.button('History', () => {})); page.append(card);
    await kit.flush(third);
    assert.equal(said.flushed, 1);
    same(said.requests.map(r => r.data.text), ['Five.']);
    assert.equal(button(card, 'History (2)').disabled, false);
    // Leaving shares what was typed: flushed first, then the studio's keepalive request.
    said.requests.length = 0; kit.typed(third, 'title', 'Name.');
    await kit.share(third);
    same(said.requests.map(r => r.route), ['piece-save', 'share']);
    await kit.share(null);
  },
  async history() {
    const versions = [{ source: 'save', at: new Date().toISOString(), words: 3, text: 'one two three' }, { source: 'rewrite', at: '', words: 1, text: 'one', divided: ['x'] }, { source: 'odd', words: 2, text: 'a b' }];
    let restore = () => view({ revision: 4 });
    const { a, said } = studio({ 'piece-versions': { versions }, 'piece-restore': data => restore(data) });
    const kit = Drafting.kit(a), held = desk(kit);
    await kit.history(held, 'title');
    same(said.requests[0], { route: 'piece-versions?id=p1&part=title' });
    const sheet = said.sheets.at(-1);
    assert.equal(sheet.title, 'History of the name');
    const rows = sheet.sheet.querySelectorAll('.desk-version');
    same(rows.map(row => row.querySelector('h3.row-title').textContent), ['Before your edit', 'Before a rewrite', 'Earlier text']);
    same(rows.map(row => row.querySelectorAll('p.quiet')[0].textContent), ['just now · 3 words', '1 word', '2 words']);
    assert.equal(rows[1].querySelectorAll('p.quiet')[1].textContent, 'A note on 1');
    await button(rows[0], 'Compare').fire('click');
    const area = sheet.sheet.querySelector('.desk-compare-area');
    assert.equal(area.children[0].textContent, 'This version compared with now');
    assert.equal(area.children[1].textContent, 'Struck words are in this version only; marked words were added since.');
    assert.ok(area.querySelector('.desk-compare'));
    await button(rows[1], 'Restore').fire('click'); await settle();
    same(said.requests.at(-1), { route: 'piece-restore', data: { id: 'p1', seen: 3, part: 'title', index: 1 } });
    same(said.toasts, ['Restored. The text it replaced is in History.']);
    assert.equal(sheet.open, false); assert.equal(said.renders, 1);
    restore = () => new Error('This draft changed since you opened it. Reload to see the latest.');
    await kit.history(held, 'title');
    await button(said.sheets.at(-1).sheet.querySelectorAll('.desk-version')[0], 'Restore').fire('click'); await settle();
    assert.equal(said.sheets.at(-1).open, false); assert.equal(held.stale, true);
    assert.equal(held.status.className, 'desk-save-state decision-notice desk-stale');
    // Nothing kept yet, and Restore off while a job works or when the person may not edit.
    const { a: b, said: told } = studio({ 'piece-versions': { versions: [] } });
    const empty = Drafting.kit(b), none = desk(empty);
    await empty.history(none, 'opening');
    assert.equal(told.sheets[0].sheet.children[1].textContent, 'Nothing kept yet.');
    const { a: c, said: locked } = studio({ 'piece-versions': { versions } }); c.editable = false;
    const read = Drafting.kit(c), only = desk(read);
    await read.history(only, 'title');
    assert.equal(button(locked.sheets[0].sheet, 'Restore').disabled, true);
  },
  async selection() {
    const { a, said } = studio({ 'piece-selection': () => view() });
    const kit = Drafting.kit(a), held = desk(kit);
    const bar = kit.selectionBar(held);
    assert.equal(bar.className, 'desk-selection glass');
    assert.equal(bar.getAttribute('role'), 'toolbar');
    assert.equal(bar.getAttribute('aria-label'), 'Change the selected text');
    assert.equal(bar.hidden, true);
    const input = Drafting.make('textarea', 'input'); input.value = '  one two  '; input.selectionStart = 0; input.selectionEnd = 11;
    kit.selected(held, 's1', input);
    same(held.selection, { part: 's1', text: 'one two', start: 0 });
    assert.equal(bar.hidden, false);
    same(bar.children.map(n => n.textContent), ['Rephrase', 'Shorten', 'Expand', 'Fix', 'Ask…']);
    await button(bar, 'Shorten').fire('click');
    same(said.jobs.at(-1), ['piece-selection', { part: 's1', text: 'one two', start: 0, action: 'shorten' }]);
    assert.equal(held.selection, null);
    kit.selected(held, 's1', input);
    await button(bar, 'Ask…').fire('click');
    same(bar.children.map(n => n.tagName + ':' + n.textContent), ['input:', 'button:Go', 'button:Cancel']);
    const box = bar.children[0];
    assert.equal(box.placeholder, 'What should change?');
    assert.equal(box.getAttribute('aria-label'), 'What should change in the selected text?');
    assert.equal(box.maxLength, 2000);
    await button(bar, 'Go').fire('click');
    same(said.notices, [['Say what to do with the passage.', true]]);
    box.value = ' Say it plainly. ';
    await button(bar, 'Go').fire('click');
    same(said.jobs.at(-1), ['piece-selection', { part: 's1', text: 'one two', start: 0, action: 'ask', instruction: 'Say it plainly.' }]);
    kit.selected(held, 's1', input); await button(bar, 'Ask…').fire('click'); await button(bar, 'Cancel').fire('click');
    assert.equal(bar.hidden, true);
    // A selection inside a part with leading spaces starts where the saved text does.
    const later = Drafting.make('textarea', 'input'); later.value = '  one two one'; later.selectionStart = 10; later.selectionEnd = 13;
    kit.selected(held, 's1', later);
    same(held.selection, { part: 's1', text: 'one', start: 8 });
    // Nothing selected, a job under way, or a desk this computer may not change: no bar.
    later.selectionEnd = 10; kit.selected(held, 's1', later); assert.equal(bar.hidden, true);
    held.view.working = { id: 'j' }; later.selectionEnd = 13; kit.selected(held, 's1', later); assert.equal(bar.hidden, true);
    held.view.working = null; a.editable = false; kit.selected(held, 's1', later); assert.equal(bar.hidden, true);
  },
};

// A desk's view with two sections, and the screen state a studio keeps for it.
function view(extra = {}) {
  return { id: 'p1', revision: 3, title: 'A name', opening: 'A lead.', sections: [{ id: 's1', heading: 'First', text: 'one two one' }, { id: 's2', heading: 'Second', text: '' }], versions: {}, jobs: [], working: null, ...extra };
}
function desk(kit, extra = {}) {
  const status = Drafting.make('p', 'quiet desk-save-state');
  return { id: 'p1', view: view(), pending: {}, session: 'a'.repeat(16), status, ...extra };
}

(async () => {
  const name = process.argv[2];
  if (!groups[name]) { console.error('Unknown group: ' + name); process.exit(2); }
  await groups[name]();
})().catch(error => { console.error(error && error.stack || error); process.exit(1); });
