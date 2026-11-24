/* Search and jump (core/studio_core/deck_web/shell.js) over a disposable DOM stand-in: a
 * page's own work found by name, focus given back, a pointer that never scrolls the list,
 * and a count of results past the first forty. No studio, no network. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');

let document;
const report = { scrolled: 0 };
class Node {
  constructor(tag) {
    this.tagName = tag.toUpperCase(); this.children = []; this.parent = null; this.dataset = {};
    this.listeners = {}; this.attributes = {}; this.text = ''; this.hidden = false; this.disabled = false;
    this.open = false; this.value = ''; this.style = { setProperty: (name, value) => { this.style[name] = value; } };
    const node = this;
    this.classList = {
      add: (...names) => { node.className = [...new Set([...node.classes(), ...names])].join(' '); },
      contains: (name) => node.classes().includes(name),
    };
  }
  classes() { return (this.attributes.class || '').split(/\s+/).filter(Boolean); }
  get className() { return this.attributes.class || ''; }
  set className(value) { this.attributes.class = String(value); }
  get id() { return this.attributes.id || ''; }
  set id(value) { this.attributes.id = String(value); }
  get textContent() { return this.text + this.children.map((child) => child.textContent).join(''); }
  set textContent(value) { this.children = []; this.text = String(value); }
  get isConnected() { let at = this; while (at.parent) at = at.parent; return at === document.body; }
  append(...nodes) {
    for (let node of nodes) {
      if (node === '' || node === null || node === undefined) continue;
      if (typeof node === 'string') { const words = new Node('#text'); words.text = node; node = words; }
      node.remove(); node.parent = this; this.children.push(node);
    }
  }
  insertBefore(node, before) {
    if (!before) return this.append(node);
    node.remove(); node.parent = this; this.children.splice(this.children.indexOf(before), 0, node);
  }
  replaceChildren(...nodes) { for (const child of this.children.slice()) child.remove(); this.text = ''; this.append(...nodes); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((child) => child !== this); this.parent = null; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener(type, listener) { (this.listeners[type] = this.listeners[type] || []).push(listener); }
  dispatch(type, event = {}) { for (const listener of this.listeners[type] || []) listener({ target: this, preventDefault() {}, ...event }); }
  focus() { document.activeElement = this; }
  click() { document.activeElement = this; this.dispatch('click'); }
  scrollIntoView() { report.scrolled += 1; }
  getClientRects() { for (let at = this; at; at = at.parent) if (at.hidden) return []; return [{}]; }
  cloneNode() { const copy = new Node(this.tagName); copy.attributes = { ...this.attributes }; copy.text = this.text; copy.append(...this.children.map((child) => child.cloneNode())); return copy; }
  showModal() { this.open = true; }
  // A browser says a dialog closed a moment later, after the code that closed it.
  close() { if (!this.open) return; this.open = false; queueMicrotask(() => this.dispatch('close')); }
  all() { return this.children.flatMap((child) => [child, ...child.all()]); }
  querySelectorAll(selector) { return this.all().filter((node) => selector.split(',').some((one) => matches(node, one.trim()))); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) { for (let at = this; at && at.tagName !== 'BODY'; at = at.parent) if (matches(at, selector)) return at; return null; }
}
function one(node, simple) {
  if (simple.endsWith(':not([hidden])')) return !node.hidden && one(node, simple.slice(0, -14));
  return (simple.match(/^[a-z]+|\.[\w-]+|\[[^\]]+\]/gi) || []).every((part) => {
    if (part.startsWith('.')) return node.classes().includes(part.slice(1));
    if (part.startsWith('[')) {
      const [name, value] = part.slice(1, -1).split('=');
      const held = name.startsWith('data-') ? node.dataset[name.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase())]
        : name === 'open' ? (node.open ? '' : undefined) : name === 'hidden' ? (node.hidden ? '' : undefined) : node.attributes[name];
      return held !== undefined && (value === undefined || held === value.replace(/^"|"$/g, ''));
    }
    return node.tagName === part.toUpperCase();
  });
}
function matches(node, selector) {
  const chain = selector.split(/\s+/);
  if (!one(node, chain.pop())) return false;
  for (let at = node.parent; chain.length && at; at = at.parent) if (one(at, chain[chain.length - 1])) chain.pop();
  return !chain.length;
}

const documentListeners = {};
document = {
  body: new Node('body'), activeElement: null, readyState: 'complete', styleSheets: [],
  documentElement: { style: {} },
  createElement: (tag) => new Node(tag),
  querySelector: (selector) => document.body.querySelector(selector),
  querySelectorAll: (selector) => document.body.querySelectorAll(selector),
  addEventListener: (type, listener) => { (documentListeners[type] = documentListeners[type] || []).push(listener); },
};
const sidebar = new Node('nav'); sidebar.className = 'sidebar glass';
const home = new Node('button'); home.className = 'nav-item'; home.textContent = 'Trainings'; sidebar.append(home);
const content = new Node('div'); content.className = 'content';
const opener = new Node('button'); opener.textContent = 'Something on the page'; content.append(opener);
document.body.append(sidebar, content);

const context = vm.createContext({ document, navigator: { platform: 'MacIntel' }, window: { addEventListener() {} },
  fetch: () => { throw new Error('No request is made here.'); }, queueMicrotask, Object, Array, String, Number, Math,
  Set, Map, WeakMap, Promise, Error, JSON, Boolean });
const source = fs.readFileSync(path.join(__dirname, '../core/studio_core/deck_web/shell.js'), 'utf8');
vm.runInContext(source + '\nthis.StudioShell = StudioShell;', context);
const shell = context.StudioShell;
const settle = async () => { for (let n = 0; n < 10; n++) await Promise.resolve(); };
const palette = () => document.body.children.find((node) => node.classList.contains('shell-palette') && node.open);
const typeIn = (dialog, words) => { const input = dialog.querySelector('.shell-palette-input'); input.value = words; input.dispatch('input'); return input; };
const rows = (dialog) => dialog.querySelectorAll('.shell-palette-row').map((row) => [
  row.querySelector('.shell-palette-group').textContent, row.querySelector('.shell-palette-title').textContent]);
const nothing = (dialog) => dialog.children.find((node) => node.classList.contains('shell-palette-none')
  && !node.classList.contains('shell-palette-more'));
const key = (node, name) => node.dispatch('keydown', { key: name });

async function check() {
  assert.equal(shell.finish, undefined, 'the unused finish card is gone');
  assert.ok(sidebar.querySelector('.shell-search'), 'Search and jump sits in the sidebar');

  // A studio lists its own work; one list that fails never hides the rest.
  const opened = [];
  const work = [{ title: 'Rolling restarts', hint: 'Waiting for you' }, { title: 'Blue green deploys', hint: 'In progress' }];
  shell.commands(() => work.map((training) => ({ title: training.title, group: 'Trainings', hint: training.hint,
    keywords: 'training work', run: () => { opened.push(training.title); home.focus(); } })));
  shell.commands(() => { throw new Error('This list could not be read.'); });
  shell.commands('not a function');

  opener.focus();
  shell.palette();
  let dialog = palette();
  assert.ok(dialog, 'the palette opens');
  assert.equal(document.activeElement, dialog.querySelector('.shell-palette-input'));
  let input = typeIn(dialog, 'rolling');
  assert.deepEqual(rows(dialog), [['Trainings', 'Rolling restarts']], 'a piece of work is found by its name');
  assert.equal(nothing(dialog).hidden, true);
  input = typeIn(dialog, 'waiting');
  assert.deepEqual(rows(dialog), [['Trainings', 'Rolling restarts']], 'and by what its state says');
  input = typeIn(dialog, 'deploys');
  key(input, 'Enter');
  await settle();
  assert.deepEqual(opened, ['Blue green deploys'], 'Return opens it');
  assert.equal(palette(), undefined, 'and puts the palette away');
  assert.equal(document.activeElement, home, 'the command places the focus, and nothing takes it back');

  // Put away with nothing chosen: the focus goes back to what opened it.
  opener.focus();
  shell.palette();
  dialog = palette();
  typeIn(dialog, 'nothing like this');
  assert.equal(nothing(dialog).hidden, false, 'nothing matches, and it says so');
  dialog.close();
  await settle();
  assert.equal(document.activeElement, opener, 'closing the palette gives the focus back to its opener');
  opener.focus();
  for (const listener of documentListeners.keydown) listener({ key: 'k', metaKey: true, preventDefault() {} });
  assert.ok(palette(), 'Cmd+K opens it');
  for (const listener of documentListeners.keydown) listener({ key: 'k', metaKey: true, preventDefault() {} });
  await settle();
  assert.equal(palette(), undefined, 'and Cmd+K again closes it');
  assert.equal(document.activeElement, opener, 'giving the focus back');

  // The keyboard brings a row into view; a resting pointer only marks it.
  opener.focus();
  shell.palette();
  dialog = palette();
  input = typeIn(dialog, '');
  const listed = dialog.querySelectorAll('.shell-palette-row');
  assert.ok(listed.length >= 3);
  const before = report.scrolled;
  listed[2].dispatch('mousemove');
  assert.equal(listed[2].getAttribute('aria-selected'), 'true', 'the row under the pointer is marked');
  assert.equal(input.getAttribute('aria-activedescendant'), listed[2].id);
  assert.equal(report.scrolled, before, 'and the list does not move under the pointer');
  key(input, 'ArrowDown');
  assert.equal(listed[3].getAttribute('aria-selected'), 'true');
  assert.equal(report.scrolled, before + 1, 'the arrow keys bring the chosen row into view');
  dialog.close();
  await settle();

  // Past forty, the palette says how many more there are.
  const many = Array.from({ length: 57 }, (_, index) => ({ title: 'Saved deck ' + (index + 1), group: 'Decks', run() {} }));
  shell.commands(() => many);
  shell.palette();
  dialog = palette();
  const more = dialog.querySelector('.shell-palette-more');
  typeIn(dialog, 'saved deck');
  assert.equal(rows(dialog).length, 40);
  assert.equal(more.hidden, false);
  assert.equal(more.getAttribute('role'), 'status');
  assert.equal(more.textContent, 'Showing 40 of 57. Type more of a name to find the rest.');
  typeIn(dialog, 'saved deck 5');
  assert.equal(rows(dialog).length, 13, 'decks 5, 15, 25, 35, 45 and 50 to 57');
  assert.equal(rows(dialog)[0][1], 'Saved deck 5');
  assert.equal(more.hidden, true, 'with every result shown, nothing more is said');
  dialog.close();
  await settle();

  // Keyboard shortcuts chosen in the palette give the focus back to the palette's opener.
  opener.focus();
  shell.palette();
  dialog = palette();
  key(typeIn(dialog, 'keyboard shortcuts'), 'Enter');
  await settle();
  const keys = document.body.children.find((node) => node.classList.contains('shell-shortcuts') && node.open);
  assert.ok(keys, 'the shortcuts open');
  keys.close();
  await settle();
  assert.equal(document.activeElement, opener, 'and put away, they give the focus back');

  // The parts of a project: groups with visible headings, each part one control saying its
  // name then its state, the one shown marked, Tab entering there and the arrow keys moving.
  const chosen = [];
  let shownPart = 'guide';
  let place = new Node('main'); content.append(place);
  const draw = () => {
    const nav = shell.parts({ label: 'Parts of this training', key: 'training-parts', chosen: shownPart,
      choose: (id) => { chosen.push(id); shownPart = id; draw(); },
      groups: [{ title: 'Level 101', parts: [{ id: 'plan', name: 'Plan', state: 'Ready' },
        { id: 'guide', name: 'Guide', state: 'Draft' }, { id: 'deck', name: 'Deck', state: 'Writing' },
        { id: 'brief', name: 'Brief', state: 'Done at last' }] },
      { title: 'Empty', parts: [] },
      { title: 'Behind it', parts: [{ id: 'sources', name: 'Research & sources', count: '3 sources' }] }] });
    place.replaceChildren(nav);
    return nav;
  };
  let nav = draw();
  const named = (node) => node.textContent;
  const items = () => nav.querySelectorAll('.parts-item');
  assert.equal(nav.tagName, 'NAV');
  assert.equal(nav.getAttribute('aria-label'), 'Parts of this training');
  assert.equal(nav.dataset.zone, 'parts', 'it sits in the workbench’s parts zone, so reading alone hides it');
  assert.deepEqual(nav.querySelectorAll('.parts-group-title').map(named), ['Level 101', 'Behind it'],
    'each group has a visible heading, and an empty group is left out');
  assert.deepEqual(items().map(named), ['Plan, Ready', 'Guide, Draft', 'Deck, Writing', 'Brief',
    'Research & sources, 3 sources'], 'a screen reader hears the name, then the state; a word '
    + 'outside the vocabulary is not shown, and a count stands where there is no state');
  assert.deepEqual(items().map((item) => item.type), ['button', 'button', 'button', 'button', 'button']);
  assert.deepEqual(items().filter((item) => item.getAttribute('aria-current') === 'true').map(named), ['Guide, Draft']);
  assert.deepEqual(items().map((item) => item.tabIndex), [-1, 0, -1, -1, -1], 'Tab enters at the part shown');
  assert.deepEqual(items().filter((item) => item.dataset.making === 'true').map(named), ['Deck, Writing'],
    'only the part being written moves');
  assert.deepEqual(nav.querySelector('.parts-list').querySelectorAll('.parts-state').map((node) => node.dataset.state),
    ['done', 'draft', 'working', 'count']);
  const toggle = nav.querySelector('.parts-toggle');
  assert.equal(toggle.type, 'button');
  assert.equal(named(toggle), 'Showing Guide, Draft', 'narrower, one control names the part shown and its state');
  assert.equal(toggle.getAttribute('aria-expanded'), 'false');
  assert.equal(toggle.getAttribute('aria-controls'), nav.querySelector('.parts-list').id);
  const keyOn = (node, name) => nav.querySelector('.parts-list').dispatch('keydown', { key: name, target: node, preventDefault() {} });
  items()[1].focus();
  keyOn(items()[1], 'ArrowDown');
  assert.equal(document.activeElement, items()[2], 'Down moves to the next part');
  keyOn(items()[2], 'ArrowDown');
  keyOn(items()[3], 'ArrowDown');
  assert.equal(document.activeElement, items()[4], 'across a group, to the next one');
  keyOn(items()[4], 'ArrowDown');
  assert.equal(document.activeElement, items()[4], 'and stops at the last');
  keyOn(items()[4], 'Home');
  assert.equal(document.activeElement, items()[0]);
  keyOn(items()[0], 'ArrowUp');
  assert.equal(document.activeElement, items()[0]);
  keyOn(items()[0], 'End');
  assert.equal(document.activeElement, items()[4]);
  assert.deepEqual(chosen, [], 'moving chooses nothing');
  items()[4].click();
  nav = place.children[0];
  assert.deepEqual(chosen, ['sources'], 'a press (Enter or Space on the button) chooses');
  assert.deepEqual(items().filter((item) => item.getAttribute('aria-current') === 'true').map(named),
    ['Research & sources, 3 sources'], 'drawn again, the part chosen is the one marked');
  assert.equal(document.activeElement, items()[4], 'the focus stays on the part chosen, drawn again');
  // Narrower: the control opens the list at the part shown; Escape puts it away again.
  nav.querySelector('.parts-toggle').click();
  assert.equal(nav.querySelector('.parts-toggle').getAttribute('aria-expanded'), 'true');
  assert.equal(document.activeElement, items()[4], 'opened, the focus is on the part shown');
  draw(); nav = place.children[0];
  assert.equal(nav.querySelector('.parts-toggle').getAttribute('aria-expanded'), 'true',
    'drawn again by a refresh, an open list stays open');
  items()[4].focus();
  keyOn(items()[4], 'Escape');
  assert.equal(nav.querySelector('.parts-toggle').getAttribute('aria-expanded'), 'false');
  assert.equal(document.activeElement, nav.querySelector('.parts-toggle'), 'Escape gives the focus to the control');
  nav.querySelector('.parts-toggle').click();
  items()[0].click();
  nav = place.children[0];
  assert.deepEqual(chosen, ['sources', 'plan']);
  assert.equal(nav.querySelector('.parts-toggle').getAttribute('aria-expanded'), 'false', 'choosing closes it');
  assert.equal(document.activeElement, nav.querySelector('.parts-toggle'), 'and the focus is back on the control');
  // A studio that takes the focus elsewhere when it shows a part keeps it there.
  const heading = new Node('h2'); content.append(heading);
  const elsewhere = shell.parts({ label: 'Parts of this infographic', chosen: 'brief', choose: () => heading.focus(),
    groups: [{ title: 'Infographic', parts: [{ id: 'brief', name: 'Brief' }, { id: 'page', name: 'Page', state: 'Out of date' }] }] });
  place.replaceChildren(elsewhere);
  elsewhere.querySelectorAll('.parts-item')[1].click();
  assert.equal(document.activeElement, heading);
  assert.equal(elsewhere.querySelector('.parts-list').querySelectorAll('.parts-state')[0].dataset.state, 'stale');
  assert.equal(Object.keys(shell.PART_STATES).join(', '), 'Writing, Queued, Needs you, Draft, Ready, Out of date, Left out');
  place.remove(); heading.remove();

  // The deck panels, served beside the kit: two pickers of looks for one deck (a sheet over
  // the panel it came from) never share an id, and each label still names its own box.
  const panels = vm.createContext({ document, window: {} });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../core/studio_core/deck_web/deck-panels.js'), 'utf8'), panels);
  const spec = { name: 'Rolling restarts deck', defaultId: 'calm',
    looks: [{ id: 'calm', name: 'Calm', number: 1 }, { id: 'bold', name: 'Bold', number: 2 }] };
  const pickers = [panels.window.DeckPanels.lookPicker(spec), panels.window.DeckPanels.lookPicker(spec)];
  const ids = pickers.flatMap((picker) => picker.all().map((node) => node.id).filter(Boolean));
  assert.equal(ids.length, 4);
  assert.equal(new Set(ids).size, 4, 'every id is its own: ' + ids.join(', '));
  for (const picker of pickers) {
    const box = picker.querySelector('textarea');
    assert.equal(picker.querySelector('label').htmlFor, box.id);
    const option = picker.querySelector('.deck-look');
    assert.ok(picker.all().some((node) => node.id === option.getAttribute('aria-describedby')));
  }
  console.log('shell page check passed');
}

check().catch((failure) => { console.error(failure); process.exit(1); });
