// Runs the shared settings page's script without a browser, for tests/test_research_sites.py.
//
//   node settings_page_harness.js STEPS.json
//
// The document here is a small stand-in: every element the script asks for exists, keeps
// what is set on it and its children, and remembers its listeners. STEPS is a list of
// {sites: [...]} (the saved list the page was shown), {type: text} into the Add a site box,
// {click: 'add'} or {click: 'remove', index}, {key: 'Enter'} in the box, and {snapshot: name}.
// The plan is {steps, answers}: what the server's one-site check answers for each typed text.
// A snapshot prints the rows shown, the hint, whether the empty line is hidden, and the
// research change Save settings would send.
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

class El {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this.dataset = {};
    this.attributes = {}; this.hidden = false; this.value = ''; this.textContent = ''; this.disabled = false;
    this.classList = { add() {}, remove() {}, toggle() {}, contains: () => false };
    this.style = {};
  }
  addEventListener(name, listener) { (this.listeners[name] ||= []).push(listener); }
  fire(name, event = {}) { for (const listener of this.listeners[name] || []) listener({ preventDefault() {}, key: event.key, target: this, ...event }); }
  append(...nodes) { for (const node of nodes) this.children.push(node); }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  before() {} after() {} remove() {} focus() { focused = this; } select() {} setSelectionRange() {}
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  removeAttribute(name) { delete this.attributes[name]; }
  add() {}
  querySelector() { return new El(); }
  querySelectorAll(selector) {
    if (selector === '.site-row .button') return this.children.map(row => row.children[1]);
    return [];
  }
}
let focused = null;
let answers = {};
const asked = [];
const byId = new Map();
function find(selector) {
  if (!byId.has(selector)) byId.set(selector, new El());
  return byId.get(selector);
}
const form = find('#settings-form');
const named = new Map();
form.elements = new Proxy({}, { get: (target, name) => {
  if (!named.has(name)) { const input = new El('input'); input.name = String(name); named.set(name, input); }
  return named.get(name);
} });
const document = {
  body: { dataset: { standalone: 'false', product: 'Marketing Studio', tokenHeader: 'X-Test' }, classList: { toggle() {} } },
  querySelector: find, querySelectorAll: () => [], createElement: tag => new El(tag),
};
const context = {
  document, console, setTimeout: () => 0, clearTimeout() {}, URL, URLSearchParams, JSON,
  location: { hash: '', pathname: '/', origin: 'http://127.0.0.1:1', hostname: '127.0.0.1' },
  history: { replaceState() {} }, sessionStorage: { getItem: () => '', setItem() {} },
  navigator: {}, Option: class extends El { constructor(text, value) { super('option'); this.text = text; this.value = value; } },
  // Only the one-site check is answered, from the plan's {answers: {typed: {site} or {error}}}.
  fetch: async (url, options) => {
    const sent = JSON.parse(options.body || '{}');
    asked.push({ url, sent });
    const answer = answers[sent.site] || { error: 'Not in this plan.' };
    return { ok: !answer.error, json: async () => answer };
  },
};
context.window = { addEventListener() {}, matchMedia: () => ({ matches: false }), scrollTo() {}, open() {} };
vm.createContext(context);
const script = fs.readFileSync(path.join(__dirname, '..', 'core', 'studio_core', 'setup_web', 'app.js'), 'utf8');
vm.runInContext(script, context, { filename: 'app.js' });

const plan = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const steps = plan.steps;
answers = plan.answers || {};
const settle = () => new Promise(resolve => setImmediate(resolve));
const shots = {};
const run = code => vm.runInContext(code, context);
(async () => {
for (const step of steps) {
  if (step.sites) {
    context.shownSites = step.sites;
    form.elements.storage.value = 'local';
    run("snapshot = {shared: {research: {sites: shownSites}}, efforts: {claude: []}}; setup = false; researchSites = [...shownSites]; renderSites();");
  } else if ('type' in step) {
    find('#research-site-input').value = step.type;
  } else if (step.click === 'add') {
    find('#research-site-add').fire('click'); await settle(); await settle();
  } else if (step.click === 'remove') {
    find('#research-site-list').children[step.index].children[1].fire('click');
  } else if (step.key) {
    find('#research-site-input').fire('keydown', { key: step.key }); await settle(); await settle();
  } else if (step.snapshot) {
    let change;
    try { change = run('changesForStep()').research ?? null; } catch (error) { change = 'error: ' + error.message; }
    shots[step.snapshot] = {
      rows: find('#research-site-list').children.map(row => row.children[0].textContent),
      removeLabels: find('#research-site-list').children.map(row => row.children[1].getAttribute('aria-label')),
      hint: find('#research-site-hint').textContent,
      emptyHidden: find('#research-site-empty').hidden,
      input: find('#research-site-input').value,
      change,
      asked: asked.length,
    };
  }
}
process.stdout.write(JSON.stringify(shots));
})();
