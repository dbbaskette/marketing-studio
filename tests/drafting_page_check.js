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
