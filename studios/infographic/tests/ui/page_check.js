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
});
vm.runInContext('const {make, add} = Drafting;', page);
for (const name of ['button', 'chosenMark', 'useStory', 'infographicCommands']) vm.runInContext(cut(source, name), page);

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
console.log('PASS Infographic Studio page: Search and jump lists and opens its work; Use this story is quiet');
