/* Infographic Studio's page script, its real functions cut from runner/web/app.js, over a
 * disposable stand-in page: what Search and jump lists and what each entry does, and a story
 * card's Use this story as a choice among peers. No browser, server, provider or studio state.
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
  append(...nodes) { for (const n of nodes) { n.parent = this; this.children.push(n); } }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k] ?? null; }
  addEventListener(kind, fn) { (this.listeners[kind] ||= []).push(fn); }
  click() { for (const fn of this.listeners.click || []) fn({ target: this, currentTarget: this }); }
}
const document = { createElement: tag => new Element(tag),
  createTextNode: text => { const t = new Element('#text'); t._text = text; return t; },
  addEventListener() {}, removeEventListener() {}, hidden: false };

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

  // Running background work has Stop beside Stop waiting.
  assert.match(source, /if\(work\.id&&work\.stoppable\)\{const end=button\('Stop',\(\)=>stopWork\(work\)\)/);
  console.log('PASS Infographic Studio page: Search and jump lists and opens its work; Use this story is quiet; '
    + 'a Document Library link opens New infographic with its item; out-of-date work has Update and Keep as it is');
})().catch(failure => { console.error(failure); process.exit(1); });
