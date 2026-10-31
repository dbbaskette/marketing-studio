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
// For the rest of the form: the plan may set {product, standalone}; {run: code} runs code in
// the page's scope; {responses: {path: answer}} answers /api/<path> posts (an answer with
// `error` is refused); {submit: true} submits the settings form; and a snapshot with
// {read: [selector, ...]} adds each element's text and whether it is hidden, with every
// request the page made. {show: view} runs show(view); {home: snapshot} hands the page that
// snapshot and runs renderHome(). A snapshot with {ids: [id, ...]} adds `hidden` and `words`
// for each (`words` includes the children's words), and every snapshot has `cards`: each
// launch card's studio, its filled and plain buttons, the class of each of its parts in
// order, its status line's bead and words, its readiness sentence and recovery action; and
// `toasts`, the words of each toast shown. The form's named controls and its parts with a
// setup step are read from index.html, so fill(), show() and the saved state see them all.
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
  before() {} after() {} remove() {} replaceWith() {} focus() { focused = this; } select() {} setSelectionRange() {}
  // A named control is the form's, as in a page: form.elements finds the one made last.
  get name() { return this._name; }
  set name(value) { this._name = value; named.set(value, this); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  removeAttribute(name) { delete this.attributes[name]; }
  add() {}
  querySelector() { return new El(); }
  querySelectorAll(selector) {
    if (selector === '.site-row .button') return this.children.map(row => row.children[1].children[0]);
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
// Every control the page's form names, so fill() and the saved-state check see them all, and
// every part with a setup step, so show() hides and shows them as the page does.
const html = fs.readFileSync(path.join(__dirname, '..', 'core', 'studio_core', 'setup_web', 'index.html'), 'utf8');
for (const [, name] of html.matchAll(/\bname="([^"]+)"/g)) void form.elements[name];
const stepped = [...html.matchAll(/<(?:section|div)\b[^>]*\bid="([^"]+)"[^>]*\bdata-step="([^"]+)"/g)]
  .map(([, id, step]) => { const part = find('#' + id); part.dataset.step = step; return part; });
form.querySelectorAll = selector => selector === 'input[name], select[name]' ? [...named.values()]
  : selector === '[data-step]' ? stepped : [];
// The words an element shows, its children's included.
const deep = node => (node.textContent || '') + (node.children || []).map(deep).join('');
const early = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let responses = {};
const document = {
  body: { dataset: { standalone: String(Boolean(early.standalone)),
    product: early.product || 'Marketing Studio', tokenHeader: 'X-Test' }, classList: { toggle() {} } },
  addEventListener() {},
  querySelector: find, querySelectorAll: () => [], createElement: tag => new El(tag),
  createElementNS: (space, tag) => new El(tag), createTextNode: text => ({ textContent: text }),
};
const context = {
  document, console, setInterval: () => 0, setTimeout: () => 0, clearTimeout() {}, URL, URLSearchParams, JSON,
  location: { hash: '', pathname: '/', origin: 'http://127.0.0.1:1', hostname: '127.0.0.1' },
  history: { replaceState() {} }, sessionStorage: { getItem: () => '', setItem() {} },
  navigator: {}, Option: class extends El { constructor(text, value) { super('option'); this.text = text; this.value = value; } },
  // Only the one-site check is answered, from the plan's {answers: {typed: {site} or {error}}}.
  fetch: async (url, options) => {
    const sent = JSON.parse(options.body || '{}');
    asked.push({ url, sent });
    const route = String(url).split('/api/').pop();
    const answer = route in responses ? responses[route]
      : answers[sent.site] || { error: 'Not in this plan.' };
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
  } else if (step.show) {
    run(`show(${JSON.stringify(step.show)})`);
  } else if (step.home) {
    context.homeSnapshot = step.home;
    run('snapshot = homeSnapshot; renderHome();');
  } else if (step.run) {
    await run(step.run);
  } else if (step.responses) {
    responses = step.responses;
  } else if (step.submit) {
    form.fire('submit'); for (let i = 0; i < 6; i += 1) await settle();
  } else if ('type' in step) {
    find('#research-site-input').value = step.type;
  } else if (step.click === 'add') {
    find('#research-site-add').fire('click'); await settle(); await settle();
  } else if (step.click === 'remove') {
    find('#research-site-list').children[step.index].children[1].children[0].fire('click');
  } else if (step.key) {
    find('#research-site-input').fire('keydown', { key: step.key }); await settle(); await settle();
  } else if (step.snapshot) {
    let change;
    try { change = run('changesForStep()').research ?? null; } catch (error) { change = 'error: ' + error.message; }
    shots[step.snapshot] = {
      rows: find('#research-site-list').children.map(row => row.children[0].textContent),
      removeLabels: find('#research-site-list').children.map(row => row.children[1].children[0].getAttribute('aria-label')),
      hint: find('#research-site-hint').textContent,
      emptyHidden: find('#research-site-empty').hidden,
      input: find('#research-site-input').value,
      change,
      asked: asked.length,
      cards: find('#studio-list').children.map(card => {
        const descendants = node => (node.children || []).flatMap(child => [child, ...descendants(child)]);
        const parts = descendants(card);
        const buttons = parts.filter(part => part.tagName === 'BUTTON' || part.tagName === 'A');
        const state = parts.find(part => part.className === 'state');
        const detail = parts.find(part => /\bstudio-readiness-detail\b/.test(part.className || ''));
        const recover = parts.find(part => /\bstudio-recover\b/.test(part.className || ''));
        return { studio: card.dataset.studio,
          filled: buttons.filter(part => /\bbutton-filled\b/.test(part.className)).map(part => part.textContent),
          plain: buttons.filter(part => !/\bbutton-filled\b/.test(part.className)).map(part => part.textContent),
          actions: buttons.map(part => part.textContent),
          order: card.children.map(part => part.className),
          status: state ? [state.children[0].dataset.state, state.children[1].textContent] : null,
          detail: detail ? detail.textContent : null, recover: recover ? recover.textContent : null,
          running: parts.find(part => /\bstudio-running\b/.test(part.className || ''))?.textContent || '' };
      }),
      toasts: find('#toasts').children.map(toast => toast.textContent),
      ...(step.ids ? { hidden: Object.fromEntries(step.ids.map(id => [id, find('#' + id).hidden])),
        words: Object.fromEntries(step.ids.map(id => [id, deep(find('#' + id))])) } : {}),
      ...(step.read ? { read: Object.fromEntries(step.read.map(selector => [selector,
        { text: find(selector).textContent, hidden: find(selector).hidden }])),
      requests: asked.map(({ url, sent }) => ({ url: String(url), sent })) } : {}),
    };
  }
}
process.stdout.write(JSON.stringify(shots));
})();
