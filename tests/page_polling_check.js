/* Background polling on Infographic Studio's research sheet and activity recovery, and on
 * Marketing Studio's Brands working copy: the real functions, cut from each page's script,
 * over a disposable stand-in page. No browser, server, provider or studio state.
 *
 *   node page_polling_check.js
 *
 * It checks that no read is made while the page is hidden, that the read is made at once when
 * it is shown again with no second timer, and that a live update keeps what the person opened,
 * focused and scrolled. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');

class Element {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase(); this.children = []; this.parent = null; this.dataset = {}; this.attributes = {};
    this.listeners = {}; this.className = ''; this._text = ''; this.hidden = false; this.disabled = false; this.open = false;
    this.scrollTop = 0; this.value = '';
  }
  get parentNode() { return this.parent; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  set textContent(value) { this.children = []; this._text = String(value); }
  get classList() { const node = this; return { contains: c => node.className.split(' ').includes(c), add: c => { node.className = (node.className + ' ' + c).trim(); } }; }
  append(...nodes) { for (let n of nodes) { if (typeof n === 'string') { const t = new Element('#text'); t._text = n; n = t; } if (n.parent) n.remove(); n.parent = this; this.children.push(n); } }
  prepend(...nodes) { for (const n of nodes.reverse()) { if (n.parent) n.remove(); n.parent = this; this.children.unshift(n); } }
  replaceChildren(...nodes) { for (const c of this.children) c.parent = null; this.children = []; this._text = ''; this.append(...nodes); }
  replaceWith(n) { const p = this.parent; if (!p) return; if (n.parent) n.remove(); p.children[p.children.indexOf(this)] = n; n.parent = p; this.parent = null; }
  after(n) { const p = this.parent; if (n.parent) n.remove(); p.children.splice(p.children.indexOf(this) + 1, 0, n); n.parent = p; }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(c => c !== this); this.parent = null; }
  contains(n) { return this === n || this.children.some(c => c.contains(n)); }
  closest(selector) { for (let n = this; n; n = n.parent) if (matches(n, selector)) return n; return null; }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k] ?? null; }
  addEventListener(kind, fn) { (this.listeners[kind] ||= []).push(fn); }
  async fire(kind, event = {}) { for (const fn of this.listeners[kind] || []) await fn({ target: this, currentTarget: this, preventDefault() {}, stopPropagation() {}, ...event }); }
  focus(options) { document.activeElement = this; document.focusedWith = options; }
  querySelectorAll(selector) { return every(this).filter(n => matches(n, selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
function every(n) { return n.children.flatMap(c => [c, ...every(c)]); }
function matches(n, selector) {
  return selector.split(',').some(one => {
    const m = /^([a-z]*)((?:\.[\w-]+)*)$/i.exec(one.trim());
    if (!m) throw Error('The stand-in page does not read ' + one);
    return (!m[1] || n.tagName === m[1].toUpperCase()) && m[2].split('.').filter(Boolean).every(c => n.className.split(' ').includes(c));
  });
}
const document = {
  hidden: false, activeElement: null, focusedWith: null, seen: {},
  createElement: tag => new Element(tag),
  createTextNode: text => { const t = new Element('#text'); t._text = text; return t; },
  addEventListener(kind, fn) { (this.seen[kind] ||= []).push(fn); },
  removeEventListener(kind, fn) { this.seen[kind] = (this.seen[kind] || []).filter(f => f !== fn); },
  listening(kind) { return (this.seen[kind] || []).length; },
  show() { this.hidden = false; for (const fn of [...(this.seen.visibilitychange || [])]) fn(); },
};
// Timers run only when a check says, so it can see each one waiting.
const timers = new Map(); let timerId = 0;
const setTimeout = (fn, ms) => { const id = ++timerId; timers.set(id, { fn, ms }); return id; };
const clearTimeout = id => { timers.delete(id); };
const waiting = () => [...timers.values()].map(t => t.ms);
async function settle() { for (let i = 0; i < 40; i++) await Promise.resolve(); }
async function run(ms) { for (const [id, t] of [...timers.entries()]) if (t.ms === ms) { timers.delete(id); t.fn(); } await settle(); }

// One function, as written in a page's script: from `function name(` to its closing brace.
function cut(source, name) {
  const start = source.search(new RegExp('(async )?function ' + name + '\\s*\\('));
  assert.ok(start >= 0, name + ' is in the script');
  let depth = 0, at = start + /\)\s*\{/.exec(source.slice(start)).index;   // the body, after any default {}
  for (let i = source.indexOf('{', at); i < source.length; i++) { if (source[i] === '{') depth++; else if (source[i] === '}' && --depth === 0) return source.slice(start, i + 1); }
  throw Error('Unbalanced ' + name);
}
const root = path.join(__dirname, '..');
const base = { document, console, JSON, Object, Array, String, Number, Math, Map, Set, Promise, Error, Date, URLSearchParams, setTimeout, clearTimeout };
const kit = vm.createContext({ ...base });
kit.window = kit;
vm.runInContext(fs.readFileSync(path.join(root, 'ui-kit/drafting.js'), 'utf8') + '\nthis.Drafting = Drafting;', kit);
const Drafting = kit.Drafting;

async function infographicResearch() {
  const source = fs.readFileSync(path.join(root, 'studios/infographic/runner/web/app.js'), 'utf8');
  const asked = [];
  let state = { state: 'working', progress: { phase: 'investigate', timing: {} }, elapsed_seconds: 1, workers: [] };
  const sheetNode = Object.assign(new Element('dialog'), { open: true }), body = new Element('div');
  sheetNode.append(body);
  // The research panel's own parts: a keyed disclosure with a scrolled list and a control.
  const progress = () => {
    const box = new Element('section'), more = new Element('details'), head = new Element('summary'), list = new Element('ol'), go = new Element('button');
    more.dataset.key = 'research-collected'; head.textContent = 'View collected evidence'; go.dataset.key = 'research-pause'; go.textContent = 'Pause';
    for (let i = 0; i < 5; i++) { const row = new Element('li'); row.textContent = 'Finding ' + i + ' at ' + state.elapsed_seconds; list.append(row); }
    more.append(head, list); box.append(more, go); return box;
  };
  const page = vm.createContext({
    ...base, Drafting, make: Drafting.make, add: Drafting.add,
    $: id => ({ sheet: sheetNode, 'sheet-body': body })[id],
    held: { project: { id: 'synthetic', revision: 1, sources: [] } },
    request: async route => { asked.push(route); return JSON.parse(JSON.stringify(state)); },
    StudioResearch: { Editor: class { constructor() { this.node = new Element('div'); } }, progress },
    button: (label, action) => { const b = new Element('button'); b.textContent = label; b.addEventListener('click', action); return b; },
    detail: (title, ...parts) => { const d = new Element('details'); d.append(...parts); return d; },
    sheet: (title, ...nodes) => body.replaceChildren(...nodes), closeSheet: () => { sheetNode.open = false; },
    sourceImportSheet: () => {}, researchImportSheet: () => {},
  });
  vm.runInContext(cut(source, 'researchSheet'), page);
  await vm.runInContext('researchSheet()', page); await settle();
  const reads = () => asked.filter(r => r.startsWith('/api/research-status')).length;
  assert.equal(reads(), 1);
  assert.deepEqual(waiting(), [1500], 'one read waits while the research works');
  // The person opens the evidence, scrolls its list and focuses Pause.
  const keyed = key => every(body).find(n => n.dataset.key === key);
  let panel = keyed('research-collected');
  panel.open = true; panel.querySelector('ol').scrollTop = 40; keyed('research-pause').focus();
  const focused = document.activeElement;
  state = { ...state, elapsed_seconds: 2 };
  await run(1500);
  assert.equal(reads(), 2);
  panel = keyed('research-collected');
  assert.ok(panel.textContent.includes('at 2'), 'the update was drawn');
  assert.equal(panel.open, true, 'an open disclosure stays open across a live update');
  assert.equal(panel.querySelector('ol').scrollTop, 40, 'and its list stays where it was scrolled');
  assert.notEqual(document.activeElement, focused);
  assert.equal(document.activeElement.dataset.key, 'research-pause', 'the focused control keeps the focus');
  assert.equal(document.focusedWith?.preventScroll, true, 'without scrolling the page');
  // Shut by the person, it stays shut.
  panel.open = false; await run(1500);
  assert.equal(keyed('research-collected').open, false, 'a shut disclosure stays shut');
  // Hidden: no read, and no second timer, until the page is shown again.
  document.hidden = true;
  await run(1500);
  assert.equal(reads(), 3, 'no read while the page is hidden');
  assert.deepEqual(waiting(), [], 'nothing waits on a timer while hidden');
  assert.equal(document.listening('visibilitychange'), 1);
  document.show(); await settle();
  assert.equal(reads(), 4, 'shown again, it reads at once');
  assert.deepEqual(waiting(), [1500], 'with one read waiting after it');
  assert.equal(document.listening('visibilitychange'), 0);
  // Finished research is read no more.
  state = { ...state, state: 'complete' };
  await run(1500);
  assert.deepEqual(waiting(), []);
  timers.clear();
}

async function infographicRecovery() {
  const source = fs.readFileSync(path.join(root, 'studios/infographic/runner/web/app.js'), 'utf8');
  const asked = [];
  let left = 2;
  const page = vm.createContext({
    ...base, Drafting,
    request: async route => { asked.push(route); return { activity: { state: --left > 0 ? 'running' : 'complete' } }; },
    progressNotice: () => {}, connectionUncertain: () => {},
  });
  vm.runInContext(cut(source, 'recoverActivity'), page);
  document.hidden = true;
  const done = vm.runInContext("recoverActivity('synthetic', {})", page);
  await settle();
  assert.equal(asked.length, 0, 'recovery reads nothing while the page is hidden');
  document.show(); await settle();
  assert.equal(asked.length, 1, 'and reads at once when it is shown');
  await run(2000);
  assert.equal(asked.length, 2);
  assert.equal((await done).state, 'complete');
}

async function brandsTask() {
  const source = fs.readFileSync(path.join(root, 'marketing_studio/web/brands.js'), 'utf8');
  const holder = new Element('main');
  const asked = [];
  const make = (tag, text, cls) => { const node = new Element(tag); if (text) node.textContent = text; if (cls) node.className = cls; return node; };
  let work = { key: 'k', kind: 'brand', name: 'Synthetic', task: { kind: 'extract', state: 'running', lines: ['Reading', 'Looking at slides'] }, ready: false };
  const page = vm.createContext({
    ...base, window: { scrollY: 0, scrollTo() {} },
    ctx: { element: make, here: () => true, api: async (route, sent) => { asked.push([route, sent]); return JSON.parse(JSON.stringify(work)); },
      problem: error => { throw error; }, stateLine: (state, words) => make('p', words, 'state'), busy: () => () => {}, isBusy: () => false },
    key: 'k', timer: null, waiting: false, lastBasis: null, words: { brand: 'brand pack' },
    body: () => holder,
    saveCard: () => make('section', 'Save', 'card brand-save'),
  });
  for (const name of ['el', 'button', 'card', 'bar', 'taskCard', 'swap', 'refresh', 'render', 'ask', 'discard']) vm.runInContext(cut(source, name), page);
  // The working copy as already drawn: the task card with Show activity and the save card.
  page.lastBasis = JSON.stringify({ ...work, task: null, ready: null });
  holder.dataset.work = 'k';
  holder.append(vm.runInContext('taskCard', page)(work), make('section', 'Save', 'card brand-save'));
  let more = holder.querySelector('details');
  assert.equal(more.className, 'brand-lines');
  more.open = true; more.querySelector('ol').scrollTop = 25;
  holder.querySelector('button').focus();
  // A live update with nothing new draws nothing again.
  await vm.runInContext("refresh('k')", page); await settle();
  const drawn = holder.querySelector('.brand-task');
  await vm.runInContext("refresh('k')", page); await settle();
  assert.equal(holder.querySelector('.brand-task'), drawn, 'an unchanged task is not drawn again');
  // A new line draws the task again, keeping Show activity open, its scroll and the focus.
  work = { ...work, task: { ...work.task, lines: [...work.task.lines, 'Writing the pack'] } };
  await vm.runInContext("refresh('k')", page); await settle();
  more = holder.querySelector('details.brand-lines');
  assert.notEqual(holder.querySelector('.brand-task'), drawn, 'the new line is drawn');
  assert.equal(more.querySelectorAll('li').length, 3);
  assert.equal(more.open, true, 'Show activity stays open across a live update');
  assert.equal(more.querySelector('ol').scrollTop, 25);
  assert.equal(document.activeElement.dataset.action, 'Stop', 'Stop keeps the focus');
  // Hidden: no read, one wait for the page to be shown, then a read at once.
  timers.clear();
  const reads = () => asked.filter(([route]) => route === 'brand-work').length, before = reads();
  document.hidden = true;
  await vm.runInContext("refresh('k')", page); await vm.runInContext("refresh('k')", page); await settle();
  assert.equal(reads(), before, 'no read while the page is hidden');
  assert.equal(document.listening('visibilitychange'), 1, 'one wait, however often it is asked');
  document.show(); await settle();
  assert.equal(reads(), before + 1, 'shown again, it reads at once');
  assert.deepEqual(waiting(), [1500], 'and one read waits after it');
  timers.clear();
  // Discard asks in place, after the control's row; Keep it gives the focus back.
  const row = make('div', '', 'bar'), discard = vm.runInContext('button', page)('Discard', 'button-quiet', node => vm.runInContext('discard', page)(work, node));
  const list = make('li'); row.append(discard); list.append(row);
  page.showList = async () => {}; page.ctx.inform = () => {};
  const pressing = discard.fire('click'); await settle();
  const question = list.children[1];
  assert.ok(question && question.className.includes('confirm-in-place'), 'the question follows the row');
  assert.equal(question.dataset.kind, 'yours');
  assert.equal(discard.hidden, true);
  assert.equal(document.activeElement.textContent, 'Keep it', 'Keep it has the focus');
  await document.activeElement.fire('click'); await pressing;
  assert.equal(list.children.length, 1, 'the question goes once answered');
  assert.equal(document.activeElement, discard, 'Keep it returns the focus');
  assert.ok(!asked.some(([route]) => route === 'brand-discard'), 'Keep it discards nothing');
  const again = discard.fire('click'); await settle();
  await list.children[1].querySelector('button').fire('click'); await again;
  assert.equal(JSON.stringify(asked.at(-1)), JSON.stringify(['brand-discard', { key: 'k' }]), 'its action discards');
}

// Blog Studio's runner: the page's poll says a failure once and waits longer each time, and a
// voice guide's follow reads nothing while the page is hidden.
async function blogRunner() {
  const source = fs.readFileSync(path.join(root, 'studios/blog/skills/blog-studio/assets/management/runner.js'), 'utf8');
  const asked = [], notices = [];
  let now = 1000, offline = true;
  const page = vm.createContext({
    ...base, Date: { now: () => now }, S_POLL: 3000, S_POLL_MOST: 60000,
    studio: { screen: 'status', turn: 1, brand: { name: 'Synthetic' } },
    api: async route => { asked.push(route); if (offline) throw Error('Offline'); return { name: 'Synthetic' }; },
    notice: (text, bad) => notices.push([text, bad]), sStatusPage: () => {}, sGuideDraw: () => {},
  });
  for (const name of ['sShown', 'sPoll', 'sVisibilityChanged', 'sGuideFollow']) vm.runInContext(cut(source, name), page);
  const reads = () => asked.filter(route => route === 'brand').length;
  const poll = async () => { await vm.runInContext('sPoll()', page); await settle(); };
  await poll();
  assert.equal(reads(), 1); assert.equal(notices.length, 1, 'a failure is said');
  now += 2000; await poll();
  assert.equal(reads(), 1, 'the next read waits');
  now += 1500; await poll();
  assert.equal(reads(), 2); assert.equal(notices.length, 1, 'the same failure is not said again');
  now += 3500; await poll();
  assert.equal(reads(), 2, 'each wait is longer than the last');
  now += 3000; await poll(); assert.equal(reads(), 3);
  // Shown again, it reads at once; the first answer resets the wait.
  offline = false; document.hidden = true; await poll();
  assert.equal(reads(), 3, 'nothing is read while the page is hidden');
  document.hidden = false; await vm.runInContext('sVisibilityChanged()', page); await settle();
  assert.equal(reads(), 4, 'shown again, it reads at once');
  assert.equal(page.studio.pollFailures, 0); assert.equal(page.studio.pollAfter, 0);
  await poll(); assert.equal(reads(), 5, 'and reads at the usual pace after an answer');
  // A voice guide being learned is followed only while the page is shown.
  const held = { job: { id: 'j', status: 'working' }, sheet: 'guide', guide: '' };
  Object.assign(page.studio, { guideDraft: held, sheet: 'guide' });
  asked.length = 0; document.hidden = true;
  vm.runInContext('sGuideFollow', page)(held);
  assert.deepEqual(waiting(), [2000]);
  await run(2000);
  assert.equal(asked.length, 0, 'no read while the page is hidden');
  vm.runInContext('sGuideFollow', page)(held);
  assert.deepEqual(waiting(), [], 'and no second follow while it waits');
  document.show(); await settle();
  assert.equal(asked.length, 1, 'shown again, it reads at once');
  timers.clear();
}

(async () => {
  for (const check of [infographicResearch, infographicRecovery, brandsTask, blogRunner]) { await check(); document.hidden = false; timers.clear(); }
  console.log('PASS page polling: nothing read while hidden, a prompt read when shown, and live updates keep what is open, scrolled and focused');
})().catch(error => { console.error(error); process.exitCode = 1; });
