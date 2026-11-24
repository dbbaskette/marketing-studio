/* Infographic Studio's page script, its real functions cut from runner/web/app.js, over a
 * disposable stand-in page: what Search and jump lists and what each entry does, and a story
 * card's Use this story as a choice among peers, and the list of an infographic's parts (the
 * shell kit's own StudioShell.parts) over the page's one column. No browser, server, provider
 * or studio state.
 *
 *   node page_check.js
 */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');

class Element {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase(); this.children = []; this.parent = null; this.dataset = {};
    this.attributes = {}; this.listeners = {}; this.className = ''; this._text = '';
  }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  set textContent(value) { this.children = []; this._text = String(value); }
  get classList() { const node = this; return { add: c => { node.className = (node.className + ' ' + c).trim(); } }; }
  get parentElement() { return this.parent; }
  append(...nodes) { for (const n of nodes) { if (n.parent) n.remove(); n.parent = this; this.children.push(n); } }
  prepend(...nodes) { for (const n of nodes.reverse()) { if (n.parent) n.remove(); n.parent = this; this.children.unshift(n); } }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(c => c !== this); this.parent = null; }
  after(node) { const parent = this.parent; if (node.parent) node.remove(); parent.children.splice(parent.children.indexOf(this) + 1, 0, node); node.parent = parent; }
  replaceWith(node) { const parent = this.parent; parent.children[parent.children.indexOf(this)] = node; node.parent = parent; this.parent = null; }
  contains(node) { for (let at = node; at; at = at.parent) if (at === this) return true; return false; }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k] ?? null; }
  addEventListener(kind, fn) { (this.listeners[kind] ||= []).push(fn); }
  click() { for (const fn of this.listeners.click || []) fn({ target: this, currentTarget: this }); }
  focus() { document.activeElement = this; }
  scrollIntoView() { this.scrolled = true; }
  getClientRects() { return [this]; }
  // Selectors as the page's script and the shell kit ask them: a tag, classes, attributes,
  // `:scope > ` and lists.
  matches(selector) {
    return selector.split(',').some(one => {
      const parts = one.trim().match(/^[a-z0-9]+|[.#][\w-]+|\[[^\]]+\]/gi) || [];
      return parts.every(part => part[0] === '.' ? this.className.split(' ').includes(part.slice(1))
        : part[0] === '#' ? this.id === part.slice(1)
        : part[0] === '[' ? (([, key, value]) => key.startsWith('data-')
          ? (value === undefined ? this.dataset[key.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase())] !== undefined
            : this.dataset[key.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase())] === value)
          : (value === undefined ? key in this.attributes : this.attributes[key] === value))(part.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/))
        : this.tagName === part.toUpperCase());
    });
  }
  querySelectorAll(selector) {
    if (selector.startsWith(':scope > ')) return this.children.filter(c => c.matches(selector.slice(9)));
    const found = [], walk = node => { for (const c of node.children) { if (c.matches(selector)) found.push(c); walk(c); } };
    walk(this); return found;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
const document = { createElement: tag => new Element(tag),
  createTextNode: text => { const t = new Element('#text'); t._text = text; return t; },
  addEventListener() {}, removeEventListener() {}, hidden: false, activeElement: null };

// One function, as written in the page's script: from `function name(` to its closing brace.
function cut(source, name) {
  const start = source.search(new RegExp('(async )?function ' + name + '\\s*\\('));
  assert.ok(start >= 0, name + ' is in the script');
  let depth = 0;
  const at = start + /\)\s*\{/.exec(source.slice(start)).index;
  for (let i = source.indexOf('{', at); i < source.length; i++) {
    if (source[i] === '{') depth++;
    else if (source[i] === '}' && --depth === 0) return source.slice(start, i + 1);
  }
  throw Error('Unbalanced ' + name);
}

// The page's values come from another realm: compare them as plain data.
const same = (actual, expected, message) => assert.deepEqual(JSON.parse(JSON.stringify(actual)), expected, message);
const root = path.join(__dirname, '..', '..');
const source = fs.readFileSync(path.join(root, 'runner/web/app.js'), 'utf8');
const done = [];
const page = vm.createContext({ document, console, JSON, Object, Array, String, Promise, Error, Set, Map });
page.window = page;
vm.runInContext(fs.readFileSync(path.join(root, 'runner/web/drafting.js'), 'utf8') + '\nthis.Drafting = Drafting;', page);
const main = new Element('main');
Object.assign(page, {
  $: id => (id === 'main' ? main : null),
  openProject: id => done.push(['open', id]),
  startNewIntake: (control, place) => done.push(['new', control, place === main]),
  action: (name, values) => done.push([name, values]),
  listedProjects: [],
  screen: 'home',
  running: new Map(),
});
vm.runInContext('const {make, add} = Drafting;', page);
for (const name of ['button', 'chosenMark', 'useStory', 'workingNow', 'infographicCommands']) vm.runInContext(cut(source, name), page);

// The page hands its list to the shell kit, which asks for it each time the palette opens.
assert.match(source, /StudioShell\.commands\(infographicCommands\)/);
assert.match(source, /listedProjects = data\.projects;/, 'the list is what Home last drew');

// Before Home is read, only the way to start.
let listed = vm.runInContext('infographicCommands()', page);
same(listed.map(one => [one.group, one.title]), [['Start', 'New infographic']]);

// Each infographic Home lists, named and in its group, with what its card says of it.
page.listedProjects = [
  { id: 'one', title: 'Synthetic chart', readiness: { summary: 'Ready to review' } },
  { id: 'two', title: 'Busy chart', activity: { state: 'running' } },
  { id: 'three', title: '', problem: 'This infographic could not be read.' },
  { id: 'four', title: 'New chart' }];
listed = vm.runInContext('infographicCommands()', page);
same(listed.map(one => [one.group, one.title, one.hint || '']), [
  ['Infographics', 'Synthetic chart', 'Ready to review'], ['Infographics', 'Busy chart', 'Working now'],
  ['Infographics', 'Unreadable infographic', 'Needs attention'], ['Infographics', 'New chart', 'Saved'],
  ['Start', 'New infographic', '']]);
assert.ok(listed.every(one => typeof one.keywords === 'string' && typeof one.run === 'function'));
// Run as its card's Open runs, and New infographic as Home's button does (asked over <main>).
listed[0].run(); listed[4].run();
assert.deepEqual(done.splice(0), [['open', 'one'], ['new', null, true]]);

// Work this page started is working now, as its card says, though its saved state is not yet.
assert.match(source, /const working=workingNow\(p\);/, 'the card asks the same question');
page.running.set('one', { label: 'Building the page' });
same(vm.runInContext('infographicCommands()', page).map(one => one.hint || ''),
  ['Working now', 'Working now', 'Needs attention', 'Saved', '']);
page.running.clear();

// A page lists only what it shows: on an infographic's own screen, Home's list is not shown,
// so only the way to start is there.
page.screen = 'project';
same(vm.runInContext('infographicCommands()', page).map(one => [one.group, one.title]), [['Start', 'New infographic']]);
page.screen = 'home';

// A story is one choice among peers: Use this story is a quiet button named for its story,
// never a second filled one; the story in use is a Selected tag, not a button.
const use = vm.runInContext("useStory({id: 's2', headline: 'Synthetic headline'})", page);
assert.equal(use.tagName, 'BUTTON');
assert.equal(use.className, 'button button-quiet');
assert.equal(use.getAttribute('aria-label'), 'Use this story: Synthetic headline');
use.click();
same(done.splice(0), [['select', { story_id: 's2' }]]);
const chosen = vm.runInContext('chosenMark()', page);
assert.equal(chosen.tagName, 'SPAN'); assert.equal(chosen.textContent, 'Selected');
assert.doesNotMatch(source, /button\('Use this story',[^)]*\),\s*true\)/, 'no filled Use this story');
// Continue in another studio: the Document Library item in the link is read and checked
// before the fragment is cleared, then New infographic opens with it picked, saying so.
assert.ok(source.indexOf('const libraryStart') < source.indexOf('history.replaceState'), 'read before the fragment is cleared');
vm.runInContext(cut(source, 'libraryLink'), page);
same(vm.runInContext("libraryLink('notes-1@3')", page), { id: 'notes-1', revision: 3 });
for (const bad of ['Notes@1', 'notes@0', 'notes@1001', 'notes', '../x@1', 'notes@1@2', ''])
  same(vm.runInContext('libraryLink(' + JSON.stringify(bad) + ')', page), { invalid: true }, bad);
const intake = { opened: 0 };
Object.assign(page, {
  privateIntake: { startFresh: async () => true }, resetIntake: () => { page.draft.library = []; },
  draft: { library: [] }, intakeLoaded: false, startingFrom: '',
  newSheet: async () => { intake.opened += 1; }, error: message => { intake.error = message; },
  libraryRows: async picks => {
    if (picks[0].id === 'gone') throw Error('That document is hidden in the Document Library.');
    return [{ id: picks[0].id, revision: picks[0].revision, title: 'Launch notes', characters: 40, gaps: [] }];
  },
});
vm.runInContext('let startingFrom = "";' + cut(source, 'startFromLibrary'), page);
(async () => {
  await vm.runInContext("startFromLibrary({id: 'notes-1', revision: 3})", page);
  same(page.draft.library, [{ id: 'notes-1', revision: 3, title: 'Launch notes', characters: 40, gaps: [], acknowledged: false }]);
  assert.equal(vm.runInContext('startingFrom', page), 'Launch notes');
  assert.equal(intake.opened, 1); assert.equal(intake.error, undefined);
  assert.match(source, /'Starting from: '\),document\.createTextNode\(startingFrom\+', from the Document Library\./);
  // Hidden, missing or unreadable: said plainly, and the sheet opens empty.
  await vm.runInContext("startFromLibrary({id: 'gone', revision: 1})", page);
  same(page.draft.library, []);
  assert.equal(intake.opened, 2);
  assert.match(intake.error, /could not be used: That document is hidden/);
  assert.match(intake.error, /open without it/);
  await vm.runInContext('startFromLibrary({invalid: true})', page);
  assert.match(intake.error, /could not be read, so nothing was picked/);

  // Out-of-date work: each part has Update and Keep as it is, saying what changed.
  page.calm = () => true; page.stateLine = (kind, words) => { const n = new Element('p'); n.textContent = words; return n; };
  page.card = (title, ...parts) => { const n = new Element('section'); n.title = title; n.append(...parts.filter(Boolean)); return n; };
  page.list = () => new Element('ul');
  vm.runInContext("const STALE_ORDER=['facts','stories','page','artwork'];const STALE_WHAT={facts:'The facts',stories:'The story',page:'The page',artwork:'The artwork'};" + cut(source, 'staleCard'), page);
  assert.equal(vm.runInContext('staleCard({})', page), null, 'nothing out of date, no card');
  const card = vm.runInContext("staleCard({stale:{stories:{because:'brief',revision:4},page:{because:'brief',revision:4}}})", page);
  const buttons = [];
  const walk = node => { if (node.tagName === 'BUTTON') buttons.push(node); node.children.forEach(walk); };
  walk(card);
  same(buttons.map(b => b.textContent), ['Update the story', 'Keep as it is', 'Update the page', 'Keep as it is']);
  assert.match(card.textContent, /The story was made before the brief changed\./);
  assert.ok(buttons.every(b => !b.className.includes('button-filled')), 'one main action per view: no filled button here');
  buttons[1].click(); buttons[2].click();
  same(done.splice(0), [['keep-stale', { part: 'stories' }], ['refresh-page', null]]);

  // The list of an infographic's parts (StudioShell.parts, the shell kit's own, loaded here by
  // itself over this stand-in page). The page stays one column: each part's place carries
  // data-ig-part, and choosing one brings it into view, opened, its heading focused.
  const kit = vm.createContext({ document: { createElement: tag => new Element(tag),
    get activeElement() { return document.activeElement; }, body: { dataset: {} },
    querySelector: s => main.querySelector(s), querySelectorAll: s => main.querySelectorAll(s),
    documentElement: { style: {} }, readyState: 'loading', addEventListener() {} },
    navigator: { platform: '' }, location: { hash: '', protocol: '', hostname: '', port: '' },
    sessionStorage: { getItem: () => null, setItem() {} }, URLSearchParams });
  vm.runInContext(fs.readFileSync(path.join(root, 'runner', 'studio_core', 'deck_web', 'shell.js'), 'utf8')
    + '\nthis.StudioShell = StudioShell;', kit);
  const pushed = [];
  Object.assign(page, { StudioShell: { parts: kit.StudioShell.parts }, screen: 'project', scrolledTop: 0,
    history: { state: null, pushState(state) { this.state = state; pushed.push(state); } },
    scrollTo() { page.scrolledTop += 1; }, openProject: async () => {}, here: () => true,
    workLabels: { suggest: 'Finding the story', build: 'Building the page', review: 'Recording your review and running checks' },
    held: { project: { id: 'p1', stale: { page: { because: 'brief' } }, scene: { width: 800, height: 1000 }, sources: [{}, {}] },
      roadmap: { stage: 'review' }, deliveries: [{ current: true, draft: true }] } });
  page.$ = id => (id === 'main' ? main : main.querySelector('#' + id));
  vm.runInContext('function free(node){node.dataset.free="";return node;}', page);
  for (const name of ['PART_NAMES', 'WORK_PARTS', 'STALE_PARTS']) {
    const at = source.indexOf('const ' + name + '='); assert.ok(at >= 0, name);
    vm.runInContext(source.slice(at, source.indexOf('\n', at)), page);
  }
  vm.runInContext("let partShown=null,partsSaid='';", page);
  for (const name of ['partAt', 'partWorking', 'partState', 'partGroups', 'drawParts', 'revealPart', 'choosePart', 'partsReturn']) vm.runInContext(cut(source, name), page);
  // The page: a line of light, then each part where it is (some inside a disclosure).
  main.children = [];
  const light = new Element('div'); light.id = 'ig-pulse'; main.append(light);
  const place = (tag, id, title) => { const node = new Element(tag); node.dataset.igPart = id;
    const head = new Element(tag === 'details' ? 'summary' : 'h2'); head.textContent = title; node.append(head); main.append(node); return node; };
  const story = place('details', 'story', 'Story: Keep serving'), view = place('div', 'page', 'Draft page'),
    review = place('section', 'review', 'Review and finish'), files = place('details', 'files', 'Saved files');
  place('details', 'brief', 'Brief and requirements'); const sources = place('details', 'sources', 'Sources and facts'); place('details', 'history', 'History');
  const list = () => main.querySelectorAll('.parts-group').map(group => [group.querySelector('.parts-group-title').textContent,
    group.querySelectorAll('.parts-item').map(item => [item.querySelector('.parts-name').textContent,
      item.querySelector('.parts-state')?.textContent || '', item.getAttribute('aria-current') === 'true'])]);
  // Building the page: the page says Writing, the one part that moves.
  page.running = new Map([['p1', { label: 'Building the page' }]]);
  vm.runInContext('drawParts()', page);
  const nav = main.children[1];
  assert.equal(nav.tagName, 'NAV'); assert.equal(nav.getAttribute('aria-label'), 'Parts of this infographic');
  assert.equal(nav.dataset.zone, 'parts', 'in the parts zone, after the line of light');
  same(list(), [['Infographic', [['Story', '', false], ['Page', 'Writing', false], ['Review and checks', 'Needs you', false], ['Saved files', '1 revision', false]]],
    ['Behind it', [['Brief', '', false], ['Sources and facts', '2 sources', false], ['History', '', false]]]]);
  assert.equal(main.querySelector('.parts-item[data-part="page"]').dataset.making, 'true');
  assert.ok(nav.querySelectorAll('button').every(b => b.dataset.free === ''), 'the list stays free while work runs');
  // The work ends: the page made before the brief changed is Out of date; said again in place.
  page.running = new Map();
  vm.runInContext('drawParts()', page);
  assert.equal(main.children.filter(n => n.tagName === 'NAV').length, 1, 'one list');
  same(list()[0][1][1], ['Page', 'Out of date', false]);
  const said = main.children[1]; vm.runInContext('drawParts()', page);
  assert.equal(main.children[1], said, 'nothing changed: the list is not drawn again');
  // Sources and facts chosen: opened, in view, its heading focused, marked, one history entry.
  main.querySelectorAll('.parts-item').find(n => n.dataset.part === 'sources').click();
  assert.equal(sources.open, true); assert.equal(sources.scrolled, true);
  assert.equal(document.activeElement, sources.children[0], 'the focus is on its heading');
  same(pushed, [{ infographicPart: { project: 'p1', part: 'sources' } }]);
  same(list()[1][1][1], ['Sources and facts', '2 sources', true]);
  // The review card chosen: its title focused; a story inside a disclosure opened.
  main.querySelectorAll('.parts-item').find(n => n.dataset.part === 'review').click();
  assert.equal(document.activeElement, review.children[0]); assert.equal(review.children[0].tabIndex, -1);
  assert.equal(pushed.length, 2);
  main.querySelectorAll('.parts-item').find(n => n.dataset.part === 'review').click();
  assert.equal(pushed.length, 2, 'the part shown chosen again: brought into view, no new entry');
  // Back: the part the entry names, marked and brought into view; before the first, the top.
  sources.open = false;
  await vm.runInContext('partsReturn', page)({ state: pushed[0] });
  assert.equal(sources.open, true); same(list()[1][1][1], ['Sources and facts', '2 sources', true]);
  await vm.runInContext('partsReturn', page)({ state: null });
  assert.equal(page.scrolledTop, 1); assert.ok(list().every(([, rows]) => rows.every(row => !row[2])), 'nothing marked');
  // A reload marks the part the history entry kept; the fragment is never used for it.
  assert.match(source, /const kept=history\.state\?\.infographicPart;partShown=kept&&kept\.project===p\.id/);
  assert.match(source, /window\.addEventListener\('popstate',partsReturn\);/);
  void story; void view; void files;

  // Running background work has Stop beside Stop waiting.
  assert.match(source, /if\(work\.id&&work\.stoppable\)\{const end=button\('Stop',async\(\)=>\{if\(!await Drafting\.confirmInPlace\(end,/);
  assert.match(source, /stopWork\(work\);\}\);/);
  console.log('PASS Infographic Studio page: Search and jump lists and opens its work; Use this story is quiet; '
    + 'a Document Library link opens New infographic with its item; out-of-date work has Update and Keep as it is; '
    + 'the list of its parts says each one\'s state and brings the part chosen into view, opened, with Back');
})().catch(failure => { console.error(failure); process.exit(1); });
