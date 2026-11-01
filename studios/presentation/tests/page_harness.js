// Runs the page's own scripts without a browser, for tests/test_desk.py.
//
//   node page_harness.js markdown        reads markdown on standard input, prints the tree
//                                        markdown.js builds from it
//   node page_harness.js app FILE        runs app.js against the answers in FILE, follows its
//                                        steps, and prints what was on the page at each one
//   node page_harness.js kit FILE        draws the shared list kit's parts (lists.js) on an
//                                        empty page, as FILE's steps say, and prints them
//
// A step is one of: {snapshot: name}, {click: the name of a control}, {fill: the label of a
// box, value: what is typed}, {type: text} for the note in the sheet, {enter: the label of a
// box} for Enter pressed in it, {poll: true} for the page's own refresh, {key: 'Escape'},
// {notification: which one} for a click on a notification the page showed, {attach: the
// label of a file picker, files: what is chosen in it}, {polls: how many} for the page's own
// refresh asked for that many times at once, {hidden: true or false} for the tab put behind
// another or brought back, {timer: a function's name} for the last timer the page set to
// call it, {tick: the name of a check box} for a click on that box, {select: the label of a
// box, start, end} for words selected in it, {press: a key, on: the name of a control} for
// that key pressed on it, and {hold: the name of
// a control} to follow that very node: each
// snapshot then says, in `still`, which of those held are still on the page, and in `asked`
// how many requests had been made by then. A box that is filled is left as a
// person leaves it, unless the step says {stay: true}: then they are still typing in it. A chosen file is {name, text} or {name,
// bytes}; {size} says how large it claims to be, for one too large to write out here.
//
// An answer may be a picture: {status: 200, picture: its bytes in base64}. The page keeps
// one in memory under an address it makes up, and each snapshot says which pictures are on
// the screen and which are still held; what was let go is listed beside the requests.
// Nothing is laid out here, so nothing scrolls into view by itself: {see: the words a
// picture's place begins with} says that it has. A plan with {unwatched: true} is a browser
// that cannot say when anything comes into view. A plan with {narrow: true} is a phone:
// the page's own width queries match, and what the kit's stylesheet hides on a phone (the
// filters behind Filters) or shows only there (Filters itself) is hidden or shown here too.
//
// Each snapshot also says how the screen is laid out: the toolbar's controls in order, each
// filled or quiet; the ledes; the heading tags of each card; how many cards sit inside
// another; the parts' names in order (card titles, sheet parts and a selection's count); the
// boxes that are ticked; the words of the selection bar; and every heading on the screen.
//
// The document here has no HTML parser at all. A script that tried to set innerHTML would
// throw, so anything that reaches the page as markup fails the test that runs this.
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const PAGE = path.join(__dirname, '..', 'skills', 'presentation-studio', 'scripts', 'desk');
const NATIVE = ['BUTTON', 'A', 'SUMMARY', 'INPUT', 'TEXTAREA', 'SELECT'];
const report = { errors: [], requests: [], notifications: [], strayListeners: [], paces: [],
  released: [], reloads: 0 };
// Each notification the page showed, to be clicked by a step.
const shown = [];
// The pictures the page holds in memory: the address it made up for each, and what it is of.
const kept = new Map();
const watchers = [];
// The nodes a step said to follow, each with its name when it was held.
const followed = [];

// --- a document with no parser -------------------------------------------------------

class FakeNode {
  constructor() {
    this.childNodes = [];
    this.parentNode = null;
  }

  remove() {
    if (!this.parentNode) return;
    const held = this.parentNode.childNodes;
    held.splice(held.indexOf(this), 1);
    this.parentNode = null;
  }

  contains(node) {
    for (let at = node; at; at = at.parentNode) if (at === this) return true;
    return false;
  }

  replaceWith(node) {
    if (!this.parentNode) return;
    const parent = this.parentNode;
    const held = parent.childNodes;
    node.remove();
    node.parentNode = parent;
    held.splice(held.indexOf(this), 1, node);
    this.parentNode = null;
  }

  get nextSibling() {
    if (!this.parentNode) return null;
    const held = this.parentNode.childNodes;
    return held[held.indexOf(this) + 1] || null;
  }
}

class FakeText extends FakeNode {
  constructor(text) {
    super();
    this.nodeType = 3;
    this.data = String(text);
  }

  get textContent() {
    return this.data;
  }
}

function refuseMarkup() {
  throw new Error('The page tried to write markup. It must only ever set text.');
}

class FakeElement extends FakeNode {
  constructor(tag) {
    super();
    this.nodeType = tag === '#fragment' ? 11 : 1;
    this.tagName = tag.toUpperCase();
    this.attributes = {};
    this.dataset = {};
    this.listeners = {};
    this.style = {};
    this.hidden = false;
    this.off = false;
    this.readOnly = false;
    this.inert = false;
    this.open = false;
    this.value = '';
    this.checked = false;
    this.indeterminate = false;
    const owner = this;
    this.classList = {
      add: (...names) => { owner.className = [...new Set([...owner.classes(), ...names])].join(' '); },
      remove: (...names) => {
        owner.className = owner.classes().filter((name) => !names.includes(name)).join(' ');
      },
      contains: (name) => owner.classes().includes(name),
    };
  }

  classes() {
    return (this.attributes.class || '').split(/\s+/).filter(Boolean);
  }

  get disabled() {
    return this.off;
  }

  // A control that is switched off while it has the focus loses it, as it does in a browser.
  set disabled(value) {
    this.off = Boolean(value);
    if (this.off && document.activeElement === this) document.activeElement = document.body;
  }

  get className() {
    return this.attributes.class || '';
  }

  set className(value) {
    this.attributes.class = String(value);
  }

  get id() {
    return this.attributes.id || '';
  }

  set id(value) {
    this.attributes.id = String(value);
  }

  set innerHTML(value) { refuseMarkup(); }

  set outerHTML(value) { refuseMarkup(); }

  insertAdjacentHTML() { refuseMarkup(); }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  getAttribute(name) {
    return name in this.attributes ? this.attributes[name] : null;
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  append(...nodes) {
    for (const given of nodes) {
      const node = typeof given === 'string' ? new FakeText(given) : given;
      if (node.nodeType === 11) {
        this.append(...node.childNodes.slice());
        continue;
      }
      node.remove();
      node.parentNode = this;
      this.childNodes.push(node);
    }
  }

  prepend(node) {
    const held = this.childNodes.slice();
    this.replaceChildren(node, ...held);
  }

  get firstChild() {
    return this.childNodes[0] || null;
  }

  insertBefore(node, before) {
    if (!before) {
      this.append(node);
      return node;
    }
    node.remove();
    node.parentNode = this;
    this.childNodes.splice(this.childNodes.indexOf(before), 0, node);
    return node;
  }

  replaceChildren(...nodes) {
    for (const child of this.childNodes.slice()) child.remove();
    this.append(...nodes);
  }

  get children() {
    return this.childNodes.filter((node) => node.nodeType === 1);
  }

  get textContent() {
    return this.childNodes.map((node) => node.textContent).join('');
  }

  set textContent(value) {
    this.replaceChildren(new FakeText(value));
  }

  addEventListener(type, listener) {
    (this.listeners[type] = this.listeners[type] || []).push(listener);
    if (type === 'click' && this.nodeType === 1 && !NATIVE.includes(this.tagName)) {
      report.strayListeners.push(this.tagName);
    }
  }

  dispatch(type, event) {
    if (event) event.currentTarget = this;
    for (const listener of this.listeners[type] || []) listener(event);
  }

  // Behind an inert part of the page, as everything is behind an open sheet.
  get behind() {
    for (let at = this; at; at = at.parentNode) if (at.inert) return true;
    return false;
  }

  // What a click, or Enter or Space on a native control, does. The control has the focus,
  // as it does for anyone who reached it with the keyboard. Nothing inert can be reached.
  click() {
    if (this.disabled || this.behind) return;
    document.activeElement = this;
    const event = { target: this, preventDefault() {} };
    this.dispatch('click', event);
    if (this.tagName === 'SUMMARY' && this.parentNode) this.parentNode.open = !this.parentNode.open;
    if (this.tagName === 'BUTTON' && this.type === 'submit') {
      for (let at = this.parentNode; at; at = at.parentNode) {
        if (at.tagName === 'FORM') at.dispatch('submit', event);
      }
    }
  }

  focus() {
    document.activeElement = this;
  }

  select() {}

  all() {
    const found = [];
    for (const child of this.children) found.push(child, ...child.all());
    return found;
  }

  querySelectorAll(selector) {
    return this.all().filter((node) => selector.split(',').some((one) => matches(node, one.trim())));
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }
}

// Selectors as the page uses them: tag, .class, #id, [attribute] and [attribute="value"],
// together or one inside another.
function matchesOne(node, simple) {
  const parts = simple.match(/^[a-z0-9]+|[.#][\w-]+|\[[^\]]+\]/gi) || [];
  return parts.every((part) => {
    if (part.startsWith('.')) return node.classes().includes(part.slice(1));
    if (part.startsWith('#')) return node.id === part.slice(1);
    if (part.startsWith('[')) {
      const [name, value] = part.slice(1, -1).split('=');
      const held = name.startsWith('data-')
        ? node.dataset[name.slice(5).replace(/-(\w)/g, (whole, letter) => letter.toUpperCase())]
        : name === 'open' ? (node.open ? '' : undefined) : node.attributes[name];
      if (held === undefined) return false;
      return value === undefined || held === value.replace(/^"|"$/g, '');
    }
    return node.tagName === part.toUpperCase();
  });
}

function matches(node, selector) {
  const chain = selector.replace(/\s*>\s*/g, ' ').split(/\s+/);
  if (!matchesOne(node, chain.pop())) return false;
  let at = node.parentNode;
  while (chain.length && at) {
    if (at.nodeType === 1 && matchesOne(at, chain[chain.length - 1])) chain.pop();
    at = at.parentNode;
  }
  return !chain.length;
}

const documentListeners = {};
const windowListeners = {};
const document = {
  body: new FakeElement('body'),
  activeElement: null,
  hidden: false,
  title: '',
  createElement: (tag) => new FakeElement(tag),
  createElementNS: (space, tag) => new FakeElement(tag),
  createTextNode: (text) => new FakeText(text),
  createDocumentFragment: () => new FakeElement('#fragment'),
  getElementById: (id) => document.body.all().find((node) => node.id === id) || null,
  querySelector: (selector) => document.body.querySelector(selector),
  querySelectorAll: (selector) => document.body.querySelectorAll(selector),
  addEventListener: (type, listener) => {
    (documentListeners[type] = documentListeners[type] || []).push(listener);
  },
  execCommand: () => false,
};

function tree(node) {
  if (node.nodeType === 3) return node.data;
  const shown = { tag: node.tagName.toLowerCase() };
  for (const name of ['href', 'rel', 'target', 'start', 'scope']) {
    if (node[name] !== undefined) shown[name] = node[name];
  }
  if (node.className) shown.class = node.className;
  if (node.childNodes.length) shown.children = node.childNodes.map(tree);
  return shown;
}

// --- markdown ----------------------------------------------------------------------

function markdown() {
  global.document = document;
  const renderer = require(path.join(PAGE, 'markdown.js'));
  const text = fs.readFileSync(0, 'utf8');
  // A third word, "files", draws it as a document that lists its own files.
  console.log(JSON.stringify(tree(renderer.render(text, { files: process.argv[3] === 'files' }))));
}

// --- the page itself ---------------------------------------------------------------

function settle() {
  return new Promise((resolve) => setImmediate(() => setImmediate(() => setImmediate(resolve))));
}

// The kit's phone rules for a filter row: on a phone only the search shows until Filters
// opens the rest; on a desktop there is no Filters button.
let phone = false;
// Where the page sent the browser, when it set location.href: a page of its own is not left.
let here = null;
// The browser's history: what it keeps with the screen is what a reload opens the page at.
let travelled = null;

function styledAway(at) {
  if (at.nodeType !== 1) return false;
  const classes = at.classes();
  if (classes.includes('filters-toggle')) return !phone;
  const row = at.parentNode;
  if (!phone || !row || row.nodeType !== 1 || !row.classes().includes('filter-bar')) return false;
  if (row.classes().includes('filters-open')) return false;
  return classes.includes('more-filters') || (classes.includes('field') && !classes.includes('search'));
}

function visible(node) {
  for (let at = node; at; at = at.parentNode) {
    if (at.hidden || styledAway(at) || (at.tagName === 'DETAILS' && !at.open && node !== at
        && !at.children.filter((child) => child.tagName === 'SUMMARY').some((s) => s.contains(node)))) {
      return false;
    }
  }
  return true;
}

function labelOf(node) {
  for (let at = node.parentNode; at; at = at.parentNode) if (at.tagName === 'LABEL') return at;
  if (!node.id) return null;
  return document.body.querySelectorAll('label').find((label) => label.htmlFor === node.id) || null;
}

function name(node) {
  if (node.tagName === 'INPUT' && !node.getAttribute('aria-label')) {
    const label = labelOf(node);
    return label ? (label.textContent || '').trim() : '';
  }
  return (node.getAttribute('aria-label') || node.textContent || '').trim();
}

// A check box, by the words of its label.
function checkbox(label) {
  const all = document.body.querySelectorAll('input').filter((node) => node.type === 'checkbox'
    && visible(node));
  const exact = all.filter((node) => name(node) === label);
  const found = exact.length ? exact : all.filter((node) => name(node).startsWith(label));
  if (!found.length) throw new Error('No check box on the page is labelled "' + label + '".');
  return found[0];
}

// How the screen is laid out, for the layout rules the tests hold every screen to.
const HEADINGS = ['H1', 'H2', 'H3', 'H4', 'H5', 'H6'];

function inside(node, root, className) {
  for (let at = node.parentNode; at && at !== root; at = at.parentNode) {
    if (at.nodeType === 1 && at.classes().includes(className)) return true;
  }
  return false;
}

function layout() {
  const main = document.getElementById('main');
  const sheet = document.getElementById('sheet');
  const actions = document.getElementById('actions');
  const cards = main.querySelectorAll('.card').filter(visible);
  const bar = document.body.querySelectorAll('.selection-bar').filter(visible)[0];
  return {
    toolbar: actions.querySelectorAll('button, a, summary').filter(visible).map((node) => ({
      name: name(node), filled: node.classes().includes('button-filled'),
      quiet: node.classes().includes('button-quiet') })),
    ledes: [main, sheet].filter((part) => visible(part))
      .flatMap((part) => part.querySelectorAll('.lede').filter(visible))
      .map((node) => node.textContent.trim()),
    cardHeadings: cards.map((card) => [...new Set(card.all()
      // A document's own headings (markdown.js's .md) are what it says, not the card's.
      .filter((node) => HEADINGS.includes(node.tagName) && visible(node)
        && !inside(node, card, 'card') && !inside(node, card, 'md'))
      .map((node) => node.tagName.toLowerCase()))].sort()),
    nested: cards.filter((card) => inside(card, main, 'card')).length,
    // Every heading on the screen, in order, cards and all: what a reader's headings list
    // shows.
    headings: main.all().filter((node) => HEADINGS.includes(node.tagName) && visible(node)
      && !inside(node, main, 'md')).map((node) => words(node).replace(/\s+/g, ' ').trim()),
    parts: document.body.querySelectorAll('.card-title, .sheet-part, .selection-count')
      .filter(visible).map((node) => words(node).replace(/\s+/g, ' ').trim()),
    ticked: document.body.querySelectorAll('input')
      .filter((node) => node.type === 'checkbox' && node.checked && visible(node)).map(name),
    bar: bar ? words(bar).replace(/\n+/g, '\n').trim() : '',
    // Each desk layout on the screen: its classes, and the classes of what it lays out side
    // by side.
    desks: main.querySelectorAll('.desk-layout').filter(visible).map((node) => ({
      classes: node.classes(), children: node.children.map((child) => child.classes()) })),
  };
}

function words(node) {
  if (node.nodeType === 3) return node.data;
  if (node.hidden || styledAway(node)) return '';
  const inline = ['SPAN', 'CODE', 'STRONG', 'EM', 'A', 'BUTTON', 'P', 'LI', 'H1', 'H2', 'H3',
    'TIME', 'TH', 'TD', 'LABEL', 'SUMMARY'];
  return node.childNodes.map(words).join(inline.includes(node.tagName) ? '' : '\n');
}

// The boxes a person can type in, each under the words of its label: a label for the box,
// or one the box sits in, as the shared source editor's are, named by its own words.
function boxes() {
  const found = [];
  for (const label of document.body.querySelectorAll('label').filter(visible)) {
    const box = label.htmlFor ? document.getElementById(label.htmlFor)
      : label.querySelectorAll('input, textarea, select')
        .filter((node) => node.type !== 'checkbox')[0] || null;
    const words = label.htmlFor ? null : label.querySelector('.field-label');
    if (box && visible(box)) found.push([words ? words.textContent.trim() : name(label), box]);
  }
  return found;
}

function box(label) {
  const all = boxes();
  const exact = all.filter(([words]) => words === label);
  const found = exact.length ? exact : all.filter(([words]) => words.startsWith(label));
  if (!found.length) throw new Error('No box on the page is labelled "' + label + '".');
  return found[0][1];
}

// There are no object URLs here. The page is handed a made-up address for what it fetched,
// and letting go of one is remembered, so a test can see what is held and what was let go.
const objects = {
  made: 0,
  createObjectURL(fetched) {
    this.made += 1;
    kept.set('memory:' + this.made, fetched.from);
    return 'memory:' + this.made;
  },
  revokeObjectURL(address) {
    if (kept.has(address)) report.released.push(kept.get(address));
    kept.delete(address);
  },
};

// What says a picture's place has come into view. Here only a step says so.
class IntersectionObserver {
  constructor(seen) {
    this.seen = seen;
    this.watched = [];
    watchers.push(this);
  }

  observe(node) { this.watched.push(node); }

  unobserve(node) { this.watched = this.watched.filter((other) => other !== node); }

  disconnect() { this.watched = []; }
}

function see(words) {
  for (const watcher of watchers) {
    const found = watcher.watched.filter((node) => document.body.contains(node)
      && visible(node) && name(node).startsWith(words));
    if (found.length) watcher.seen(found.map((target) => ({ target, isIntersecting: true })));
  }
}

// A picture is the page's own when it is shown from memory. Any other is from somewhere else.
// The one frame is the storyboard's: sandboxed, with no srcdoc, opened at the runner's own
// framed address with a ticket.
function own(node) {
  return node.tagName === 'IMG' && kept.has(node.src)
    || node.tagName === 'IFRAME' && node.className === 'deck-storyboard-frame'
      && node.getAttribute('sandbox') === '' && node.srcdoc === undefined
      && String(node.src).startsWith('/api/deck-draft?ticket=');
}

function snapshot() {
  const controls = document.body.querySelectorAll('button, a, summary, textarea, input');
  const unnamed = [];
  for (const control of controls) {
    if (control.tagName === 'TEXTAREA' || control.tagName === 'INPUT') {
      if (control.getAttribute('aria-hidden') === 'true') continue;
      const around = labelOf(control);
      const labelled = document.body.querySelectorAll('label')
        .some((label) => label.htmlFor && label.htmlFor === control.id && name(label))
        || Boolean(control.tagName === 'INPUT' && name(control))
        || Boolean(around && !around.htmlFor && name(around));
      if (!labelled && !control.getAttribute('aria-label')) unnamed.push(control.tagName);
    } else if (!name(control)) {
      unnamed.push(control.tagName + '.' + control.className);
    }
  }
  const sheet = document.getElementById('sheet');
  const badge = document.getElementById('needs-count');
  return {
    title: document.title,
    heading: document.getElementById('title').textContent,
    tip: document.getElementById('title').title || '',
    text: words(document.body).replace(/\n+/g, '\n'),
    buttons: controls.filter((node) => node.tagName !== 'A' && visible(node)).map(name),
    filled: document.body.querySelectorAll('.button-filled').filter(visible).map(name),
    pressed: document.body.querySelectorAll('.seg-option').filter(visible)
      .filter((node) => node.getAttribute('aria-pressed') === 'true').map(name),
    beads: [...new Set(document.body.querySelectorAll('.bead').map((node) => node.dataset.state))],
    // What a phone reads under a row of beads, where their names have no room.
    captions: document.body.querySelectorAll('.beads-caption').filter(visible)
      .map((node) => node.textContent),
    bareBeads: document.body.querySelectorAll('.bead')
      .filter((node) => !name(node.parentNode)).length,
    unnamed,
    foreign: document.body.querySelectorAll('img, script, iframe, object, embed')
      .filter((node) => !own(node)).length,
    pictures: document.body.querySelectorAll('img').filter((node) => own(node) && visible(node))
      .map((node) => ({ alt: node.alt || '', of: kept.get(node.src) })),
    held: [...kept.values()],
    focus: document.activeElement === document.body ? '(nowhere)'
      : document.activeElement ? (document.activeElement.id || name(document.activeElement)) : '',
    focusKey: (document.activeElement && document.activeElement.dataset
      && document.activeElement.dataset.key) || '',
    notice: document.getElementById('notice').hidden ? '' : document.getElementById('notice').textContent,
    current: document.body.querySelectorAll('[aria-current]').map(name),
    // Each dialog on the page that is not the sheet: whether it is modal, and what names it.
    dialogs: document.body.querySelectorAll('[role="dialog"]').filter(visible)
      .filter((node) => node.id !== 'sheet')
      .map((node) => [node.getAttribute('aria-modal'), node.getAttribute('aria-labelledby')]),
    // Each radio of a radio group: its name, whether it is checked, and its place for Tab.
    radios: document.body.querySelectorAll('[role="radio"]').filter(visible)
      .map((node) => [name(node), node.getAttribute('aria-checked'), node.tabIndex]),
    sheet: sheet.hidden ? '' : words(sheet).replace(/\n+/g, '\n'),
    sheetCards: sheet.hidden ? 0 : sheet.querySelectorAll('.card').filter(visible).length,
    toasts: document.body.querySelectorAll('.toast').map((node) => node.textContent),
    links: document.body.querySelectorAll('a').filter((node) => visible(node) && node.href)
      .map((node) => ({ name: name(node), href: node.href, rel: node.rel,
        target: node.target })),
    off: controls.filter((node) => visible(node) && node.disabled)
      .map((node) => name(node) || node.id),
    posts: report.requests.filter((request) => request.method === 'POST').length,
    badge: badge.hidden ? '' : badge.textContent,
    fields: Object.fromEntries(boxes().map(([label, held]) => [label, held.value])),
    // How many characters each box takes, under the words of its label.
    limits: Object.fromEntries(boxes().map(([label, held]) => [label, held.maxLength])),
    // What each of the browser's own lists offers, in order, under the words of its label.
    lists: Object.fromEntries(boxes().filter(([, held]) => held.tagName === 'SELECT')
      .map(([label, held]) => [label, held.querySelectorAll('option')
        .map((option) => option.textContent)])),
    // The groups a list puts its entries in, each with its name, where it has any.
    groups: Object.fromEntries(boxes().filter(([, held]) => held.tagName === 'SELECT'
      && held.querySelector('optgroup'))
      .map(([label, held]) => [label, held.children.map((part) => (part.tagName === 'OPTGROUP'
        ? [part.label, part.children.map((option) => option.textContent)]
        : part.textContent))])),
    locked: boxes().filter(([, held]) => held.readOnly).map(([label]) => label),
    invalid: boxes().filter(([, held]) => held.getAttribute('aria-invalid') === 'true')
      .map(([label]) => label),
    chosen: document.body.querySelectorAll('.chip').filter(visible)
      .filter((node) => node.getAttribute('aria-pressed') === 'true').map(name),
    working: document.body.querySelectorAll('.working').filter(visible).length,
    sidebar: !document.getElementById('sidebar').hidden,
    inert: document.body.all().filter((node) => node.inert).map((node) => node.id),
    pace: report.paces[report.paces.length - 1] || 0,
    asked: report.requests.length,
    still: followed.filter(([node]) => document.body.contains(node)).map(([, named]) => named),
    href: (here && here.href) || '',
    // What the browser keeps with the screen, for a reload to open the page at it again.
    state: travelled ? travelled.state : null,
    // A key two parts of the page share: focus kept by that key may land on the wrong one.
    keyedTwice: [...document.body.all().filter((node) => node.dataset && node.dataset.key
      && visible(node)).map((node) => node.dataset.key)
      .reduce((seen, key) => seen.set(key, (seen.get(key) || 0) + 1), new Map())]
      .filter(([, times]) => times > 1).map(([key]) => key),
    ...layout(),
  };
}

// There is no File API here. A chosen file is its name, its size and its bytes, and the one
// way the page reads a file is stood in for: the bytes, in base64, after a few words and a
// comma, handed over a moment later.
function chosen(file) {
  const bytes = Buffer.from(file.bytes || file.text || '');
  return { name: file.name, type: file.type || '', bytes,
    size: file.size === undefined ? bytes.length : file.size };
}

class FileReader {
  readAsDataURL(file) {
    queueMicrotask(() => {
      this.result = 'data:' + (file.type || 'application/octet-stream') + ';base64,'
        + file.bytes.toString('base64');
      if (this.onload) this.onload();
    });
  }
}

// Enter in a box. In a single line of a form it does what a browser does: it clicks the
// form's first submit button, unless that is switched off, and the form is sent. The focus
// stays in the box. In a textarea Enter starts a new line, and nothing is sent.
function enter(held) {
  held.focus();
  if (held.tagName !== 'INPUT') return;
  let form = held.parentNode;
  while (form && form.tagName !== 'FORM') form = form.parentNode;
  const first = form ? form.all().find((node) => node.tagName === 'BUTTON'
    && node.type === 'submit') : null;
  if (!first || first.disabled || first.behind) return;
  const event = { target: first, preventDefault() {} };
  first.dispatch('click', event);
  form.dispatch('submit', event);
}

// A control by its name. What is inert, behind an open sheet, cannot be reached, so a name
// shared with something behind the sheet is the sheet's.
function control(label) {
  const all = document.body.querySelectorAll('button, summary, a')
    .filter((node) => visible(node) && !node.behind);
  const exact = all.filter((node) => name(node) === label);
  const found = exact.length ? exact : all.filter((node) => name(node).startsWith(label));
  if (!found.length) throw new Error('Nothing on the page is named "' + label + '".');
  return found[0];
}

// The page's own shell, read from index.html. It is the one piece of markup there is, it is
// ours, and it is read here only to stand the document up: the scripts never parse any.
function build(shell) {
  const [, bodyAttributes, body] = /<body\b([^>]*)>([\s\S]*)<\/body>/.exec(shell);
  for (const [, key, value] of bodyAttributes.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) {
    document.body.setAttribute(key, value || '');
  }
  const open = [document.body];
  const token = /<!--[\s\S]*?-->|<\/(\w+)>|<(\w+)((?:\s+[\w-]+(?:="[^"]*")?)*)\s*>|([^<]+)/g;
  for (const [, closing, tag, attributes, text] of body.matchAll(token)) {
    const parent = open[open.length - 1];
    if (closing) {
      open.pop();
    } else if (tag) {
      const node = new FakeElement(tag);
      for (const [, key, value] of (attributes || '').matchAll(/([\w-]+)(?:="([^"]*)")?/g)) {
        if (key === 'hidden') node.hidden = true;
        else if (key === 'type') node.type = value;
        else node.setAttribute(key, value || '');
      }
      if (tag === 'noscript') node.hidden = true;
      parent.append(node);
      open.push(node);
    } else if (text && text.trim()) {
      parent.append(new FakeText(text.trim()));
    }
  }
}

async function app(file) {
  const plan = JSON.parse(fs.readFileSync(file, 'utf8'));
  const answers = plan.answers;
  const timers = [];
  phone = Boolean(plan.narrow);
  build(fs.readFileSync(path.join(PAGE, 'index.html'), 'utf8'));

  class Notification {
    constructor(title, options) {
      report.notifications.push({ title, body: options && options.body });
      this.onclick = null;
      shown.push(this);
    }

    close() {
      report.notifications[shown.indexOf(this)].closed = true;
    }

    static requestPermission() {
      Notification.permission = 'granted';
      return Promise.resolve('granted');
    }
  }
  Notification.permission = plan.notifications || 'default';

  const window = {
    document,
    Notification,
    location: { hash: plan.hash === undefined ? '#token=the-test-key' : plan.hash,
      reload() { report.reloads += 1; } },
    // A plan with {state} opens the page as a reload does, at the screen that state names.
    history: {
      state: plan.state || null,
      // A plan with {earlier: [states]} has been there before: Back goes to them in turn.
      earlier: (plan.earlier || []).slice(),
      pushState(state) {
        this.earlier.push(this.state);
        this.state = state;
      },
      replaceState(state) { this.state = state; },
      // The browser's own way back: the state before this one, announced to the page.
      back() {
        if (!this.earlier.length) return;
        this.state = this.earlier.pop();
        for (const listener of windowListeners.popstate || []) listener({ state: this.state });
      },
    },
    navigator: { clipboard: { writeText: () => Promise.resolve() } },
    FileReader,
    addEventListener: (type, listener) => {
      (windowListeners[type] = windowListeners[type] || []).push(listener);
    },
    scrollTo() {},
    focus() {},
    // A plan with {narrow: true} is a phone: the page's width queries match.
    matchMedia: (query) => ({ matches: Boolean(plan.narrow) && /max-width/.test(query) }),
    setTimeout: (callback, delay) => {
      if (callback.name === 'refresh') report.paces.push(delay);
      return timers.push(callback);
    },
    clearTimeout() {},
    URLSearchParams,
    URL: objects,
    ...(plan.unwatched ? {} : { IntersectionObserver }),
    console,
    fetch: async (address, options) => {
      const method = (options && options.method) || 'GET';
      const key = method + ' ' + address.split('?')[0];
      report.requests.push({ method, address, headers: (options && options.headers) || {},
        body: options && options.body ? JSON.parse(options.body) : null });
      // An answer can be kept for one address, query and all, or for every query of it.
      const held = answers[method + ' ' + address] || answers[key];
      if (!held && key === 'GET /api/storyboard') return {ok: true, status: 200, json: async () => ({html:'<h1>Fixture storyboard</h1>'})};
      if (!held) return { ok: false, status: 404, json: async () => ({ error: 'No answer for ' + key }) };
      const answer = held.length > 1 ? held.shift() : held[0];
      // {pending: true} is an answer that has not come yet, and never does here.
      if (answer.pending) return new Promise(() => {});
      if (answer.picture === undefined) {
        return { ok: answer.status === 200, status: answer.status, json: async () => answer.body };
      }
      // A picture is answered as bytes: what the page is handed says what kind they are, how
      // many there are, and which request they answer.
      return { ok: true, status: 200, json: async () => { throw new Error('Not JSON.'); },
        blob: async () => ({ type: answer.type || 'image/png',
          size: Buffer.from(answer.picture, 'base64').length, from: address }) };
    },
  };
  // A plan with {transitions: true} is a browser with view transitions: the new screen is
  // drawn a moment after it is asked for, as startViewTransition does.
  if (plan.transitions) {
    document.startViewTransition = (update) => {
      const done = new Promise((resolve) => setImmediate(resolve)).then(update);
      return { ready: done, finished: done, updateCallbackDone: done };
    };
  }
  window.window = window;
  here = window.location;
  travelled = window.history;
  window.navigator.clipboard.writeText = () => Promise.resolve();
  const context = vm.createContext(window);
  context.navigator = window.navigator;
  // The deck panels are the shared core's, served beside the page.
  const panels = path.join(PAGE, '..', 'studio_core', 'deck_web', 'deck-panels.js');
  vm.runInContext(fs.readFileSync(panels, 'utf8'), context, { filename: 'deck-panels.js' });
  const lists = path.join(PAGE, '..', 'studio_core', 'deck_web', 'lists.js');
  vm.runInContext(fs.readFileSync(lists, 'utf8'), context, { filename: 'lists.js' });
  // The Document Library's sheet is the shared core's, checked on its own by the
  // repository's tests/library_page_check.js. A plan with {library: picks} stands in for it,
  // as Training Studio's harness does: Add from library hands the page those picks as Use
  // selected does, and the report says which studio asked and where focus went afterwards.
  if (plan.library) {
    window.StudioLibrary = { pick: async (adapter) => {
      report.library = [...(report.library || []), { studio: adapter.studio, max: adapter.max }];
      try {
        await adapter.use(plan.library);
      } catch (failure) {
        report.library[report.library.length - 1].refused = failure.message;
        return false;
      }
      const back = adapter.refocus && adapter.refocus();
      if (back) back.focus();
      report.library[report.library.length - 1].refocus = back ? back.dataset.key : null;
      return true;
    } };
  }
  // The shared desk kit (drafting.js, linked from ui-kit), then the page, then the deck desk,
  // in the order index.html loads them. A plan with {research: true} loads the shared source
  // editor (research.js) first, as the page does: Research first then offers it, and asks
  // POST /api/research-sources for its draft as soon as it is drawn.
  for (const script of [...(plan.research ? ['research.js'] : []), 'markdown.js', 'drafting.js',
    'app.js', 'deck-desk.js']) {
    vm.runInContext(fs.readFileSync(path.join(PAGE, script), 'utf8'), context, { filename: script });
  }
  await settle();
  const shots = {};
  for (const step of plan.steps) {
    try {
      if (step.snapshot) shots[step.snapshot] = snapshot();
      if (step.click) control(step.click).click();
      if (step.type !== undefined) {
        const held = document.getElementById('note-text');
        held.value = step.type;
        held.dispatch('input', { target: held });
      }
      if (step.enter !== undefined) enter(box(step.enter));
      if (step.notification !== undefined) shown[step.notification].onclick({});
      if (step.fill !== undefined) {
        const held = box(step.fill);
        held.focus();
        held.value = step.value;
        held.dispatch('input', { target: held });
        if (!step.stay) held.dispatch('change', { target: held });
      }
      if (step.attach !== undefined) {
        const held = box(step.attach);
        held.focus();
        held.files = step.files.map(chosen);
        held.dispatch('change', { target: held });
      }
      if (step.see !== undefined) see(step.see);
      // {select: the label of a box, start, end}: those characters of it are selected, as a
      // person drags across them, and the box says so.
      if (step.select !== undefined) {
        const held = box(step.select);
        held.focus();
        held.selectionStart = step.start;
        held.selectionEnd = step.end;
        held.dispatch('select', { target: held });
      }
      if (step.poll) await timers.filter((timer) => timer.name === 'refresh').pop()();
      if (step.timer) await timers.filter((timer) => timer.name === step.timer).pop()();
      if (step.polls) {
        const refresh = timers.filter((timer) => timer.name === 'refresh').pop();
        await Promise.all(Array.from({ length: step.polls }, () => refresh()));
      }
      if (step.hidden !== undefined) {
        document.hidden = step.hidden;
        for (const listener of documentListeners.visibilitychange || []) listener({});
      }
      if (step.tick !== undefined) {
        const held = checkbox(step.tick);
        if (!held.disabled && !held.behind) {
          held.focus();
          held.checked = !held.checked;
          held.indeterminate = false;
          held.dispatch('change', { target: held, currentTarget: held });
        }
      }
      if (step.hold !== undefined) followed.push([control(step.hold), step.hold]);
      // The browser's own Back.
      if (step.back) window.history.back();
      if (step.key) for (const listener of documentListeners.keydown || []) listener({ key: step.key });
      // {press: a key, on: the name of a control}: that key pressed while the control has the
      // focus.
      if (step.press) {
        const held = control(step.on);
        held.focus();
        held.dispatch('keydown', { key: step.press, target: held, preventDefault() {} });
      }
    } catch (failure) {
      report.errors.push(String(failure && failure.stack ? failure.stack : failure));
    }
    await settle();
  }
  console.log(JSON.stringify({ ...report, snapshots: shots }));
}

process.on('unhandledRejection', (failure) => {
  report.errors.push('Unhandled: ' + String(failure && failure.stack ? failure.stack : failure));
});

// --- the list kit on its own ---------------------------------------------------------
//
// A step {build: 'filterRow' | 'tick' | 'selectPage' | 'selectionBar', spec} draws that part
// in place of the last one. Each function a part is handed is one that writes down what it
// was called with, in `calls`; a list named `ticked` is handed over as a set. The other
// steps are the page's: {fill}, {click}, {tick}, {enter} and {snapshot}.
async function kit(file) {
  const plan = JSON.parse(fs.readFileSync(file, 'utf8'));
  phone = Boolean(plan.narrow);
  const calls = [];
  const main = new FakeElement('main');
  main.id = 'main';
  document.body.append(main);
  const window = { document, console,
    matchMedia: (query) => ({ matches: phone && /max-width/.test(query) }) };
  window.window = window;
  const context = vm.createContext(window);
  const lists = path.join(PAGE, '..', 'studio_core', 'deck_web', 'lists.js');
  vm.runInContext(fs.readFileSync(lists, 'utf8'), context, { filename: 'lists.js' });
  const recorder = (named) => (...args) => { calls.push([named, ...args]); };
  const shots = {};
  for (const step of plan.steps) {
    try {
      if (step.build) {
        const spec = { ...step.spec };
        for (const named of ['changed', 'searched', 'toggled', 'flip', 'selectShown', 'clear']) {
          spec[named] = recorder(named);
        }
        if (spec.ticked) spec.ticked = new Set(spec.ticked);
        if (spec.actions) {
          spec.actions = spec.actions.map((action) => ({ ...action,
            run: () => { calls.push([action.label]); } }));
        }
        const made = window.StudioLists[step.build](spec);
        main.replaceChildren(...(made ? [made] : []));
      }
      if (step.snapshot) {
        const controls = main.querySelectorAll('input, select, button, summary').filter(visible);
        shots[step.snapshot] = {
          controls: controls.map((node) => ({ tag: node.tagName.toLowerCase(),
            name: node.tagName === 'SELECT' ? (labelOf(node) ? labelOf(node).textContent : '')
              : name(node), type: node.type || '',
            checked: Boolean(node.checked), indeterminate: Boolean(node.indeterminate),
            classes: node.className })),
          text: words(main).replace(/\n+/g, '\n').trim(),
          empty: !main.children.length,
          calls: calls.slice(),
          bar: main.querySelectorAll('.selection-bar').filter(visible)
            .map((node) => words(node).replace(/\n+/g, '\n').trim())[0] || '',
        };
      }
      if (step.click) control(step.click).click();
      if (step.fill !== undefined) {
        const held = box(step.fill);
        held.focus();
        held.value = step.value;
        held.dispatch('input', { target: held });
        if (!step.stay) held.dispatch('change', { target: held });
      }
      if (step.enter !== undefined) enter(box(step.enter));
      if (step.tick !== undefined) {
        const held = checkbox(step.tick);
        held.checked = !held.checked;
        held.indeterminate = false;
        held.dispatch('change', { target: held, currentTarget: held });
      }
    } catch (failure) {
      report.errors.push(String(failure && failure.stack ? failure.stack : failure));
    }
    await settle();
  }
  console.log(JSON.stringify({ errors: report.errors, snapshots: shots }));
}

const [mode, file] = process.argv.slice(2);
if (mode === 'markdown') markdown();
else if (mode === 'kit') kit(file).catch((failure) => {
  console.log(JSON.stringify({ errors: [String(failure.stack)], snapshots: {} }));
});
else app(file).catch((failure) => {
  console.log(JSON.stringify({ ...report, errors: [...report.errors, String(failure.stack)] }));
});
