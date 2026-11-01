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
  // Text is a text node among the children, as in a page, so text and children can sit together.
  get textContent() { return this.tagName === '#text' ? this._text : this.children.map(c => c.textContent).join(''); }
  set textContent(value) { if (this.tagName === '#text') { this._text = String(value); return; } this.children = []; if (String(value)) { const node = new Element('#text'); node._text = String(value); node.parent = this; this.children.push(node); } }
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
    words: () => ({ thing: 'piece', sources: { save: 'Before your edit', rewrite: 'Before a rewrite' }, doing: { 'piece-section': 'Rewriting', 'piece-whole': 'Revising the piece' }, steps: { gather: 'Gathering', write: 'Writing' }, named: ['piece-section'], chain: ['piece-whole'], ready: tab => tab === 'plan' ? 'The plan is ready.' : 'The piece is ready.' }),
    tools: () => a.toolList || [],
    progress: {
      stopped: held => { const node = own('div', 'piece-stopped'); node.append(own('p', '', held.view.start.problem), a.ui.button('Try again', () => {})); return node; },
      show: () => { said.shows++; },
    },
  };
  return { a, said, page, setNarrow: value => { narrow = value; } };
}

const groups = {
  async slideContent() {
    const decisions = [], notes = [];
    const panel = Drafting.slideContent({slides: [{title: '<unsafe>', points: [{label: 'Claim', text: 'A short supported claim.'}], notes: 'Presenter explanation.'}],
      onNote: text => notes.push(text), onDecision: async (...args) => { decisions.push(args); }});
    assert.ok(panel.textContent.includes('<unsafe>'));
    assert.equal(all(panel).filter(n => n.tagName === 'img' || n.tagName === 'iframe').length, 0);
    const buttons = all(panel).filter(n => n.tagName === 'button');
    assert.equal(buttons[1].textContent, 'Approve text & design deck');
    await buttons[0].fire('click'); assert.equal(decisions.length, 0);
    const input = all(panel).find(n => n.tagName === 'textarea');
    input.value = 'Shorten slide one.'; await input.fire('input'); await buttons[0].fire('click');
    same(decisions[0], ['changes', 'Shorten slide one.']);
    assert.equal(notes[0], input.value);
    // Approve with a change still typed drops nothing: it asks first, and sends only what the
    // person chooses.
    const pending = panel.querySelector('.slide-text-pending');
    assert.equal(pending.hidden, true);
    await buttons[1].fire('click');
    assert.equal(decisions.length, 1);
    assert.equal(pending.hidden, false);
    assert.equal(context.document.activeElement, buttons[2]);
    same([buttons[2].textContent, buttons[3].textContent], ['Send these changes first', 'Approve without them']);
    await buttons[2].fire('click'); same(decisions[1], ['changes', 'Shorten slide one.']);
    await buttons[1].fire('click'); await buttons[3].fire('click');
    same(decisions[2], ['approve', null]);
    assert.equal(input.value, ''); assert.equal(notes[notes.length - 1], '');
    // With nothing typed, Approve approves at once, and the panel's decide is the same.
    await buttons[1].fire('click'); same(decisions[3], ['approve', null]);
    await panel.decide('approve'); same(decisions[4], ['approve', null]);
    // A studio that takes edits gets a box for each word, and the edited slides with its
    // decision; one that does not gets none.
    assert.equal(all(panel).filter(n => n.tagName === 'input').length, 0);
    const edited = [];
    const editable = Drafting.slideContent({slides: [{title: 'Why restarts rol', points: [{label: 'Claim', text: 'Capacity'}, 'Plain point'], notes: 'Say it.'}],
      toolbar: true, onEdit: slides => edited.push(slides), onDecision: async (...args) => { decisions.push(args); }});
    const boxes = all(editable).filter(n => n.tagName === 'input' || n.tagName === 'textarea');
    same(boxes.map(n => n.value), ['Why restarts rol', 'Claim', 'Capacity', 'Plain point', 'Say it.', '']);
    assert.ok(!all(editable).filter(n => n.tagName === 'button').some(n => n.className.includes('button-filled') && n.textContent.startsWith('Approve')));
    boxes[0].value = 'Why restarts roll'; await boxes[0].fire('input');
    boxes[3].value = 'Plain points'; await boxes[3].fire('input');
    assert.equal(edited[edited.length - 1][0].title, 'Why restarts roll');
    await editable.decide('approve');
    same(decisions[5], ['approve', null, [{title: 'Why restarts roll', points: [{label: 'Claim', text: 'Capacity'}, 'Plain points'], notes: 'Say it.'}]]);
    // Put back as it was, it sends no edit.
    boxes[0].value = 'Why restarts rol'; await boxes[0].fire('input');
    boxes[3].value = 'Plain point'; await boxes[3].fire('input');
    assert.equal(edited[edited.length - 1], null);
    await editable.decide('approve'); same(decisions[6], ['approve', null, null]);
  },
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
    same(said.requests.at(-1), { route: 'piece-selection', data: { id: 'p1', seen: 3, part: 's1', text: 'one two', start: 0, action: 'shorten' } });
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
    same(said.requests.at(-1), { route: 'piece-selection', data: { id: 'p1', seen: 3, part: 's1', text: 'one two', start: 0, action: 'ask', instruction: 'Say it plainly.' } });
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

Object.assign(groups, {
  async cards() {
    const { a, said } = studio({ 'piece-note': () => view({ revision: 4 }) });
    const kit = Drafting.kit(a), held = desk(kit);
    held.view.versions = { s1: 2 };
    const first = kit.part(held, 's1');
    assert.equal(first.className, 'card desk-part'); assert.equal(first.dataset.part, 's1');
    assert.equal(first.querySelector('h2.card-title').textContent, 'First');
    assert.equal(button(first, 'History (2)').disabled, false);
    const text = first.querySelector('textarea.desk-text');
    assert.equal(text.value, 'one two one'); assert.equal(text.getAttribute('aria-label'), 'Text of First'); assert.equal(text.readOnly, false);
    const note = first.querySelector('textarea.desk-note-text');
    assert.equal(note.placeholder, 'How should this change?'); assert.equal(note.getAttribute('aria-label'), 'How should First change?'); assert.equal(note.maxLength, 4000);
    assert.ok(button(first, 'Write again'));
    note.value = 'Shorter, please.'; await note.fire('input');
    assert.ok(button(first, 'Rewrite')); assert.equal(held.notes.s1, 'Shorter, please.');
    await button(first, 'Rewrite').fire('click'); await settle();
    same(said.requests.find(r => r.route === 'piece-note').data, { id: 'p1', seen: 3, part: 's1', note: 'Shorter, please.' });
    assert.equal(held.notes.s1, undefined);
    assert.equal(said.extras.includes('s1'), true, 'the studio adds its own nodes to a card');
    const second = kit.part(held, 's2');
    assert.equal(button(second, 'History').disabled, true);
    // Typed text waiting to save is what the card shows.
    held.pending.s2 = { text: 'Typed.' }; assert.equal(kit.part(held, 's2').querySelector('textarea.desk-text').value, 'Typed.');
    delete held.pending.s2;
    // While a job works on a section its card says so, with the note it works from.
    held.view.working = { id: 'j1', kind: 'piece-section', part: 's1', note: 'Shorter, please.' };
    const working = kit.part(held, 's1');
    assert.equal(working.className, 'card desk-part desk-working');
    assert.equal(working.querySelector('textarea.desk-text').readOnly, true);
    assert.ok(texts(working).includes('Working on this section'));
    assert.ok(texts(working).includes('Your note: Shorter, please.'));
    assert.equal(button(working, 'Write again').disabled, true);
    assert.equal(kit.workingIn(held.view, 's1'), true); assert.equal(kit.workingIn(held.view, 's2'), false);
    held.view.working = { id: 'j2', kind: 'piece-pass', part: 'sections' };
    assert.equal(kit.workingIn(held.view, 's2'), true); assert.equal(kit.workingIn(held.view, 'title'), false);
    held.view.working = null;
    // A one-line part is an input of up to 500 characters, with no note box.
    const title = kit.part(held, 'title');
    const input = title.querySelector('input.desk-text');
    assert.equal(input.type, 'text'); assert.equal(input.maxLength, 500); assert.equal(input.getAttribute('aria-label'), 'Name');
    assert.equal(title.querySelector('textarea.desk-note-text'), null);
    // The note for the whole piece.
    const whole = kit.whole(held);
    assert.equal(whole.querySelector('h2').textContent, 'Note for the whole piece');
    const box = whole.querySelector('textarea');
    assert.equal(box.id, 'desk-whole-note'); assert.equal(box.getAttribute('aria-label'), 'Note for the whole piece');
    assert.equal(box.placeholder, 'For example: tighten throughout, or make it more casual.');
    assert.ok(texts(whole).includes('Each section is revised for the note with the whole piece in view. Your text is kept as a version first.'));
    await button(whole, 'Revise the piece').fire('click');
    same(said.notices.at(-1), ['Write the note for the whole piece.', true]);
    box.value = 'Warmer.'; await box.fire('input');
    await button(whole, 'Revise the piece').fire('click'); await settle();
    same(said.requests.at(-1), { route: 'piece-revise', data: { id: 'p1', seen: 4, note: 'Warmer.' } });
    assert.equal(held.wholeNote, '');
    // What the last job left: a result not applied, named by its Finishing tool.
    a.toolList = [{ key: 'polish', name: 'Polish' }];
    held.view.jobs = [{ id: 'j3', kind: 'finish-polish', status: 'failed', error: 'It stopped.' }];
    const problem = kit.problem(held);
    assert.equal(problem.className, 'decision-notice desk-problem');
    assert.equal(problem.children[0].textContent, 'Polish did not finish: It stopped.');
    await button(problem, 'Dismiss').fire('click');
    assert.equal(held.dismissed, 'j3'); assert.equal(kit.problem(held), null);
    held.view.jobs = [{ id: 'j4', kind: 'piece-section', status: 'ready', applied: false, error: 'The piece changed.' }];
    assert.equal(kit.problem(held).children[0].textContent, 'The last change was not applied: The piece changed.');
    held.view.jobs = [{ id: 'j5', kind: 'piece-whole', chain: 'c', status: 'ready' }];
    held.view.chain = { total: 3, revised: 2, working: false, problems: [{ part: 's2', heading: 'Second', error: 'Too long.' }] };
    const chain = kit.problem(held);
    assert.equal(chain.querySelector('p').textContent, 'Revised 2 of 3 sections for your note. These were not:');
    same(chain.querySelector('ul.gap-items').children.map(n => n.textContent), ['“Second”: Too long.']);
  },
  async job() {
    let answer = () => view({ revision: 4, working: { id: 'j', kind: 'piece-section', part: 's2' } });
    const { a, said } = studio({ 'piece-note': () => answer(), piece: () => view({ revision: 5, jobs: [{ id: 'j', kind: 'piece-section', applied: true }] }) });
    const kit = Drafting.kit(a), held = desk(kit);
    held.view.working = { id: 'j', kind: 'piece-whole', part: 's2', total: 3, index: 1 };
    assert.equal(kit.statusWords(held), 'Revising section 2 of 3…');
    held.view.working = { id: 'j', kind: 'piece-section', part: 's2' };
    assert.equal(kit.statusWords(held), 'Rewriting “Second”…');
    held.view.working = { id: 'j', kind: 'piece-whole', part: 'opening', total: 1 };
    assert.equal(kit.statusWords(held), 'Revising “opening”…');
    // A whole-item note's job recorded without its order still names the opening.
    held.view.working = { id: 'j', kind: 'piece-whole', part: 'opening' };
    assert.equal(kit.statusWords(held), 'Revising “opening”…');
    held.view.working = { id: 'j', kind: 'piece-section', part: 'opening', total: 2, index: 0 };
    assert.notEqual(kit.statusWords(held), 'Revising “opening”…');
    held.view.working = { id: 'j', kind: 'other' };
    assert.equal(kit.statusWords(held), 'Working…');
    held.view.working = null; assert.equal(kit.statusWords(held), '');
    let done = 0;
    const control = a.ui.button('Rewrite', () => {});
    a.hooks.beforeJob = async () => { said.before++; assert.equal(said.requests.length, 0, 'the studio flushes before the job is sent'); };
    await kit.job(held, control, 'piece-note', { part: 's2', note: '' }, () => { done++; });
    same(said.requests.map(r => r.route), ['piece-note']);
    same(said.requests[0].data, { id: 'p1', seen: 3, part: 's2', note: '' });
    assert.equal(said.before, 1); assert.equal(done, 1); assert.equal(said.refreshes, 1);
    a.hooks.beforeJob = async () => { said.before++; };
    // The desk follows the job until it ends, then says where the earlier text is.
    same(waiting(), [3000]); assert.equal(held.watching, true);
    await tick();
    same(said.requests.at(-1).route, 'piece?id=p1');
    same(said.toasts, ['Done. The earlier text is in History.']);
    assert.equal(held.watching, false);
    // A Finishing job's suggestions wait in the panel; a studio may say it its own way.
    held.view.working = { id: 'k' }; a.answers = null;
    said.toasts.length = 0;
    const { a: b, said: told } = studio({ piece: () => view({ jobs: [{ id: 'k', kind: 'finish-polish', applied: true }] }) });
    const other = Drafting.kit(b), followed = desk(other); followed.view.working = { id: 'k' };
    other.watch(followed); await tick();
    same(told.toasts, ['Suggestions are ready in Finishing.']);
    b.hooks.landed = (shown, last) => 'Marked in your ' + last.kind + '.';
    followed.view.working = { id: 'k' }; other.watch(followed); await tick();
    same(told.toasts.at(-1), 'Marked in your finish-polish.');
    // A refusal for a changed piece shows the banner; any other is a notice.
    answer = () => new Error('This draft changed since you opened it. Reload to see the latest.');
    await kit.job(held, control, 'piece-note', { part: 's2', note: '' });
    assert.equal(held.stale, true);
    held.stale = false; answer = () => new Error('Busy.');
    await kit.job(held, control, 'piece-note', { part: 's2', note: '' });
    same(said.notices.at(-1), ['Busy.', true]);
  },
  async progress() {
    const minutes = n => new Date(Date.now() - n * 60000).toISOString();
    const { a, said } = studio({ piece: () => view({ start: { ended_at: 'x', open: 'plan' } }), 'piece-stop': () => view() });
    const kit = Drafting.kit(a);
    assert.equal(kit.estimate({ minutes_left: 3 }, 'The piece'), 'Nothing needed from you. The piece opens here when it is ready, in about 3 minutes.');
    assert.equal(kit.estimate({ minutes_left: 1 }, 'The piece'), 'Nothing needed from you. The piece opens here when it is ready, in about 1 minute.');
    assert.equal(kit.estimate({ over: true, started_at: new Date().toISOString() }, 'The piece'), 'Nothing needed from you. Taking longer than usual; still working, under a minute so far. The piece opens here when it is ready.');
    assert.equal(kit.clock({ started_at: minutes(2) }), '2 minutes so far, for the whole start.');
    assert.equal(kit.clock({ started_at: minutes(1) }), '1 minute so far, for the whole start.');
    assert.equal(kit.spent({}), 'under a minute');
    const held = desk(kit);
    held.view.start = { steps: ['gather', 'write'], step: 'write', status: 'working', busy: true, job: 'j', started_at: minutes(2), minutes_left: 3, phase: '' };
    const shownStart = held.view.start, shown = kit.progress(held, 'The piece');
    assert.equal(shown.above, 'Writing on its own');
    assert.equal(shown.lede.textContent, 'Nothing needed from you. The piece opens here when it is ready, in about 3 minutes.');
    assert.equal(shown.lede.getAttribute('role'), 'status');
    assert.equal(shown.stopped, null);
    const steps = shown.card.querySelector('ol.desk-steps');
    assert.equal(steps.getAttribute('aria-label'), 'Steps of this start');
    same(steps.children.map(row => [row.querySelector('h3').textContent, row.children[0].dataset.state]), [['Gathering', 'done'], ['Writing', 'current']]);
    assert.equal(steps.children[1].querySelector('p.row-says').textContent, 'Under way');
    assert.equal(shown.card.querySelector('h2').textContent, 'Progress');
    assert.equal(shown.card.querySelector('p.desk-clock').textContent, '2 minutes so far, for the whole start.');
    await shown.stop.fire('click'); await settle();
    same(said.requests.at(-1), { route: 'piece-stop', data: { id: 'p1', job: 'j' } });
    assert.equal(said.shows, 1);
    // A stopped start: the studio's own exits in the notice.
    held.view.start = { ...shownStart, busy: false, problem: 'It stopped.' };
    const stopped = kit.progress(held, 'The piece');
    assert.equal(stopped.above, 'Stopped'); assert.equal(stopped.stop, null);
    assert.equal(stopped.lede.textContent, 'This start stopped before the piece was ready. Retry the step when you are ready.');
    assert.ok(button(stopped.stopped, 'Try again'));
    same(stopped.card.querySelector('ol').children.map(row => row.children[0].dataset.state), ['done', 'late']);
    assert.equal(stopped.card.querySelector('p.row-says'), null);
    // Followed until the piece opens, then the studio's ready line.
    kit.followStart(held); kit.followStart(held);
    same(waiting(), [3000]);
    await tick();
    same(said.started, ['plan']); assert.equal(said.renders, 1);
    same(said.toasts, ['The plan is ready.']);
  },
});

// Finishing tools of a studio that is not Blog Studio, in an order of its own.
function finishing(kit, said) {
  return [
    { key: 'publish', name: 'Before it goes', says: 'Checks before it goes out.', view: () => [Drafting.make('p', 'piece-publish', 'Its own view')] },
    { key: 'proofread', name: 'Check', says: 'Mechanical checks.', view: held => kit.proofView(held), opened: (held, first) => { said.opened.push(['proofread', first]); } },
    { key: 'humanize', name: 'Humanise', says: 'Sentences to rewrite.', run: 'Find', doing: 'Finding sentences…', start: { level: 'light' }, options: () => [Drafting.make('p', 'piece-options', 'Its options')], data: f => ({ level: f.level }), ready: f => f.level !== 'none', applyAll: true },
    { key: 'facts', name: 'Facts', says: 'Each claim checked.', run: 'Check', doing: 'Checking…', verdicts: { supported: 'Backed', 'not-in-sources': 'Not found', contradicted: 'Contradicted' }, counted: [' claim checked', ' claims checked'], empty: 'No claims to check.', source: () => { said.sources++; } },
    { key: 'headline', name: 'Names', says: 'Other names.', run: 'Suggest', doing: 'Suggesting…', groups: [['title', 'Name']] },
    { key: 'notes', name: 'Notes', says: 'Comments only.', run: 'Get notes', doing: 'Reading…', comments: { shape: 'Shape', argument: 'Argument' } },
    { key: 'review', name: 'Review', says: 'Reviewed in the text.', open: () => { said.opened.push(['review']); } },
  ];
}
function item(id, extra = {}) { return { id, part: 's1', before: 'one two', after: 'one 2', state: 'open', present: true, ...extra }; }

Object.assign(groups, {
  async tools() {
    const proof = { revision: 3, findings: [{ part: 's1', rule: 'dash', label: 'A dash.', fix: 'Replace the dash.', target: 'one', sentence: 'one two one', start: 0, at: 8 }], more: 2, limitations: 'Hints only.' };
    const { a, said, page } = studio({ 'piece-proofread': proof, 'piece-finish': () => view({ working: null }), 'piece-selection': () => view() });
    said.opened = []; const kit = Drafting.kit(a), held = desk(kit);
    a.toolList = finishing(kit, said);
    kit.finishOpen(held);
    assert.equal(said.renders, 1); assert.equal(held.finish.tool, null); assert.equal(held.finish.level, 'light');
    held.panel = kit.panel(held); page.append(held.panel);
    assert.equal(held.panel.className, 'desk-finish'); assert.equal(held.panel.getAttribute('aria-label'), 'Finishing');
    assert.equal(held.panel.querySelector('h2.desk-finish-title').textContent, 'Finishing');
    const list = held.panel.querySelector('.desk-finish-tools');
    assert.equal(list.className, 'pick-cards desk-finish-tools');
    same(list.children.map(card => card.children[0].textContent), ['Before it goes', 'Check', 'Humanise', 'Facts', 'Names', 'Notes', 'Review']);
    same(list.children.map(card => card.querySelector('span.piece-says').textContent), ['Checks before it goes out.', 'Mechanical checks.', 'Sentences to rewrite.', 'Each claim checked.', 'Other names.', 'Comments only.', 'Reviewed in the text.']);
    // A tool that takes over its own opening is not drawn in the panel.
    kit.finishTool(held, 'review'); same(said.opened, [['review']]); assert.equal(held.finish.tool, null);
    // Quick check, found by its key wherever it sits in the list, opens with its own words.
    await kit.finishTool(held, 'proofread');
    same(said.opened.at(-1), ['proofread', false]);
    assert.equal(held.panel.querySelector('h2.desk-finish-title').textContent, 'Check');
    assert.ok(button(held.panel, 'All tools'));
    const body = held.panel.querySelector('.desk-finish-body');
    assert.equal(body.children[0].textContent, 'Mechanical checks. Fix rewrites only the sentence a finding is in, and keeps the earlier text in History.');
    await button(body, 'Check now').fire('click'); await settle();
    same(said.requests.at(-1), { route: 'piece-proofread?id=p1' });
    const checked = held.panel.querySelector('.desk-finish-body');
    assert.ok(texts(checked).includes('1 finding, and 2 more. Hints only.'));
    const card = checked.querySelector('section.desk-proposal');
    assert.equal(card.querySelector('h3').textContent, 'In “First”');
    assert.equal(card.querySelector('mark').textContent, 'one');
    await button(card, 'Fix').fire('click'); await settle();
    same(said.requests.find(r => r.route === 'piece-selection').data, { id: 'p1', seen: 3, part: 's1', text: 'one two one', start: 0, action: 'fix', instruction: 'Replace the dash.' });
    // Opening the panel at Quick check reads it again.
    kit.finishOpen(held, 'proofread'); same(said.opened.at(-1), ['proofread', true]);
    // A tool's own view, and a tool that runs a job with its options, data and readiness.
    kit.finishTool(held, 'publish');
    assert.equal(held.panel.querySelector('p.piece-publish').textContent, 'Its own view');
    held.view.finishing = { humanize: { job: 'h', items: [item('p1'), item('p2', { state: 'skipped' })] } };
    held.view.working = { id: 'w', kind: 'finish-facts' };
    held.finish.tool = null; kit.panelShow(held);
    same(held.panel.querySelectorAll('span.piece-says').map(n => n.textContent).slice(2, 4), ['1 to review.', 'Working on it…']);
    held.view.working = null; held.view.finishing = {};
    kit.finishTool(held, 'humanize');
    const tool = held.panel.querySelector('.desk-finish-body');
    same(tool.children.slice(0, 2).map(n => n.textContent), ['Sentences to rewrite.', 'Its options']);
    await button(tool, 'Find').fire('click'); await settle();
    same(said.requests.at(-1), { route: 'piece-finish', data: { id: 'p1', seen: 3, tool: 'humanize', level: 'light' } });
    held.finish.level = 'none'; kit.panelShow(held);
    assert.equal(button(held.panel, 'Find').disabled, true);
    held.finish.level = 'light'; held.view.working = { id: 'w', kind: 'finish-humanize' }; kit.panelShow(held);
    assert.ok(texts(held.panel).includes('Finding sentences…'));
    held.view.working = { id: 'w', kind: 'piece-section' }; kit.panelShow(held);
    assert.ok(texts(held.panel).includes('Another change is under way. This can run when it ends.'));
    held.view.working = null; held.view.jobs = [{ id: 'x', kind: 'finish-humanize', busy: false, error: 'It failed.' }]; kit.panelShow(held);
    assert.ok(texts(held.panel).includes('It failed.'));
    await button(held.panel, 'Close').fire('click');
    assert.equal(held.finish, null);
  },
  async proposals() {
    let applied = { applied: 1, left: [] };
    const { a, said, page } = studio({ 'piece-apply': () => view({ finished: applied }), 'piece-skip': () => view() });
    said.opened = []; said.sources = 0;
    const kit = Drafting.kit(a), held = desk(kit);
    a.toolList = finishing(kit, said);
    held.finish = { tool: 'humanize', editing: {}, noted: {} };
    const set = { job: 'j'.repeat(32), level: 'light', dropped: 1, items: [item('p1'), item('p2', { flag: 'Check the facts: this changes a number.' }), item('p3', { part: 's2', before: 'three', after: '3' })] };
    held.view.finishing = { humanize: set };
    held.panel = kit.panel(held); page.append(held.panel);
    const body = held.panel.querySelector('.desk-finish-body');
    assert.ok(texts(body).includes('Found at light · 3 suggestions · 3 to review · 1 left out because it did not match the text.'));
    assert.ok(button(body, 'Apply all (2)'));
    assert.ok(texts(body).includes('1 flagged suggestion is left for you to check one by one.'));
    const cards = body.querySelectorAll('section.desk-proposal');
    same(cards.map(card => card.dataset.item), ['p1', 'p2', 'p3']);
    assert.equal(cards[0].querySelector('h3').textContent, 'In “First”');
    assert.equal(cards[1].querySelector('p.decision-notice').textContent, 'Check the facts: this changes a number.');
    assert.ok(cards[0].querySelector('.desk-sides'));
    await button(cards[0], 'Apply').fire('click'); await settle();
    same(said.requests.at(-1), { route: 'piece-apply', data: { id: 'p1', seen: 3, job: set.job, items: [{ id: 'p1' }] } });
    same(said.toasts.at(-1), 'Applied. The earlier text is in History.');
    applied = { applied: 2, left: ['p2'] };
    held.view.finishing = { humanize: set }; kit.panelShow(held);
    await button(held.panel, 'Apply all (2)').fire('click'); await settle();
    same(said.requests.at(-1).data.items, [{ id: 'p1' }, { id: 'p3' }]);
    same(said.toasts.at(-1), 'Applied 2. The earlier text is in History. 1 no longer fits and is left for you.');
    // Edit puts the person's wording beside the text, then Apply this sends it.
    held.view.finishing = { humanize: set }; kit.panelShow(held);
    await button(held.panel.querySelectorAll('section.desk-proposal')[0], 'Edit').fire('click');
    const box = held.panel.querySelector('textarea.desk-edit');
    assert.equal(box.id, 'desk-edit-p1'); assert.equal(box.value, 'one 2'); assert.equal(box.getAttribute('aria-label'), 'Your wording');
    box.value = 'one, two'; await box.fire('input');
    await button(held.panel, 'Apply this').fire('click'); await settle();
    same(said.requests.at(-1).data.items, [{ id: 'p1', after: 'one, two' }]);
    held.view.finishing = { humanize: set }; kit.panelShow(held);
    await button(held.panel.querySelectorAll('section.desk-proposal')[2], 'Skip').fire('click'); await settle();
    same(said.requests.at(-1), { route: 'piece-skip', data: { id: 'p1', job: set.job, items: ['p3'] } });
    // A suggestion whose words changed since, and ones already decided.
    held.view.finishing = { humanize: { ...set, items: [item('p1', { present: false }), item('p2', { state: 'applied' }), item('p3', { state: 'retired' })] } }; kit.panelShow(held);
    const later = held.panel.querySelectorAll('section.desk-proposal');
    assert.ok(texts(later[0]).includes('The text changed since this was suggested, so it no longer fits.'));
    assert.ok(texts(later[1]).includes('Applied. The earlier text is in History.'));
    assert.ok(texts(later[2]).includes('No longer fits: another change replaced these words.'));
    // Facts: a tag per claim, supported ones folded away, Keep it, and Add a source.
    held.finish.tool = 'facts';
    held.view.finishing = { facts: { job: 'f', items: [item('p1', { verdict: 'supported' }), item('p2', { verdict: 'contradicted', after: undefined, passage: 'It says three.', source: 'Notes' }), item('p3', { verdict: 'not-in-sources' })] } };
    delete held.view.finishing.facts.items[1].after;
    kit.panelShow(held);
    const facts = held.panel.querySelector('.desk-finish-body');
    assert.ok(texts(facts).includes('3 claims checked · 2 to review.'));
    const folded = facts.querySelector('details');
    assert.equal(folded.children[0].textContent, 'Supported (1)');
    const claim = facts.querySelectorAll('section.desk-proposal').find(card => card.dataset.item === 'p2');
    assert.equal(claim.querySelector('span.tag').textContent, 'Contradicted');
    assert.equal(claim.querySelector('blockquote.desk-quote').textContent, 'one two');
    assert.ok(texts(claim).includes('From Notes: “It says three.”'));
    assert.ok(button(claim, 'Keep it')); assert.ok(button(claim, 'Fix the wording'));
    await button(claim, 'Add a source').fire('click'); assert.equal(said.sources, 1);
    const missing = facts.querySelectorAll('section.desk-proposal').find(card => card.dataset.item === 'p3');
    assert.ok(texts(missing).includes('No passage in your sources says this.'));
    held.view.finishing = { facts: { job: 'f', items: [] } }; kit.panelShow(held);
    assert.ok(texts(held.panel).includes('No claims to check.'));
    // Alternatives in groups: Use this.
    held.finish.tool = 'headline';
    held.view.finishing = { headline: { job: 'n', items: [item('p1', { part: 'title', group: 'title', whole: true }), item('p2', { part: 'title', group: 'title', whole: true })] } };
    kit.panelShow(held);
    assert.ok(texts(held.panel).includes('Name alternatives'));
    const alternative = held.panel.querySelector('section.desk-proposal');
    assert.equal(alternative.querySelector('h3').textContent, 'Alternative');
    assert.ok(button(alternative, 'Use this'));
    assert.equal(button(held.panel, 'Apply all (2)'), undefined, 'only tools that apply all offer it');
  },
  async feedback() {
    const { a, said, page } = studio({ 'piece-skip': () => view() });
    said.opened = []; said.sources = 0;
    const kit = Drafting.kit(a), held = desk(kit);
    a.toolList = finishing(kit, said);
    const set = { job: 'f', summary: 'Good overall.', items: [{ id: 'p1', part: 's1', quote: 'one two', aspect: 'argument', comment: 'Say why.', state: 'open' }, { id: 'p2', part: 'whole', quote: '', aspect: 'odd', comment: 'Shorter.', state: 'open' }] };
    held.view.finishing = { notes: set };
    const box = kit.comments(held, 's1');
    assert.equal(box.className, 'desk-comments'); assert.equal(box.getAttribute('aria-label'), 'Feedback on this part');
    assert.equal(box.children[0].textContent, 'Feedback');
    const comment = box.querySelector('.desk-comment');
    assert.equal(comment.className, 'desk-comment');
    assert.equal(comment.querySelector('blockquote.desk-quote').textContent, 'one two');
    assert.ok(button(comment, 'Make it a note')); assert.ok(button(comment, 'Dismiss'));
    assert.equal(kit.comments(held, 's2'), null);
    assert.equal(kit.commentKey(held.view, 's1'), '["p1"]');
    assert.equal(kit.commentKey(held.view, 's2'), '[]');
    // The card shows the comment, and the panel the summary and every comment with its aspect.
    assert.ok(kit.part(held, 's1').querySelector('.desk-comments'));
    held.finish = { tool: 'notes', editing: {}, noted: {} };
    held.panel = kit.panel(held); page.append(held.panel);
    const panel = held.panel.querySelector('.desk-finish-body');
    assert.equal(panel.querySelector('section.card').querySelector('h2').textContent, 'Overall');
    const shown = panel.querySelectorAll('section.desk-comment');
    same(shown.map(card => card.querySelector('h3').textContent), ['The whole piece', 'In “First”']);
    same(shown.map(card => card.querySelector('span.tag').textContent), ['Shape', 'Argument']);
    assert.ok(button(shown[0], 'Make it the whole-piece note'));
    // Make it a note adds the comment to what was typed, never over it.
    held.notes = { s1: 'Keep this.' }; held.tab = 'draft';
    held.cards = { s1: kit.part(held, 's1') }; held.wholeCard = kit.whole(held); page.append(held.cards.s1, held.wholeCard);
    kit.toNote(held, set.items[0]);
    assert.equal(held.notes.s1, 'Keep this.\n\nSay why. (About: “one two”)');
    assert.equal(held.finish.noted.p1, true);
    assert.equal(held.cards.s1.querySelector('textarea.desk-note-text').value, 'Keep this.\n\nSay why. (About: “one two”)');
    assert.equal(document.activeElement, held.cards.s1.querySelector('textarea.desk-note-text'));
    same(said.toasts.at(-1), 'Now the note for “First”. Choose Rewrite when you are ready.');
    assert.ok(button(held.panel, 'In the note'));
    kit.toNote(held, set.items[1]);
    assert.equal(held.wholeNote, 'Shorter.');
    same(said.toasts.at(-1), 'Now the note for the whole piece. Choose Revise the piece when you are ready.');
    // From another tab the parts are drawn again first.
    held.tab = 'plan'; const renders = said.renders; kit.toNote(held, set.items[1]);
    assert.equal(held.tab, 'draft'); assert.equal(said.renders, renders + 1);
    await button(shown[1], 'Dismiss').fire('click'); await settle();
    same(said.requests.at(-1), { route: 'piece-skip', data: { id: 'p1', job: 'f', items: ['p1'] } });
  },
  async layout() {
    const { a, setNarrow } = studio();
    const kit = Drafting.kit(a), held = desk(kit);
    a.toolList = [];
    let wide = true; context.window.matchMedia = query => ({ matches: query === '(max-width: 1099px)' && !wide });
    assert.equal(kit.layout(), 'wide'); assert.equal(kit.floating(), false);
    wide = false; assert.equal(kit.layout(), 'drawer'); assert.equal(kit.floating(), true);
    setNarrow(true); assert.equal(kit.layout(), 'phone');
    held.finish = { tool: null, editing: {}, noted: {} };
    assert.equal(kit.panel(held).className, 'desk-finish desk-finish-sheet');
    setNarrow(false); assert.equal(kit.panel(held).className, 'desk-finish');
    held.panelUnder = true; assert.equal(kit.panel(held).hidden, true);
    delete context.window.matchMedia; wide = true; assert.equal(kit.layout(), 'wide');
  },
});

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
