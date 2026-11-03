/* The shared activity lines and Activity log (ui-kit/activity.js), and the research panel that
 * shows them (ui-kit/research.js), with synthetic workers and a synthetic log only (#294). */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');

class Node {
  constructor(tag) {
    this.tagName = tag.toUpperCase(); this.children = []; this.parent = null; this.dataset = {};
    this.listeners = {}; this.attributes = {}; this.className = ''; this.textContent = ''; this.open = false;
  }
  append(...nodes) {
    for (let n of nodes) {
      if (typeof n === 'string') n = Object.assign(new Node('#text'), { textContent: n });
      if (n.parent) n.parent.children = n.parent.children.filter((c) => c !== n);
      n.parent = this; this.children.push(n);
    }
  }
  replaceChildren(...nodes) { for (const c of this.children) c.parent = null; this.children = []; this.append(...nodes); }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k]; }
  addEventListener(k, fn) { (this.listeners[k] = this.listeners[k] || []).push(fn); }
  dispatch(k) { for (const fn of this.listeners[k] || []) fn({ target: this }); }
  get childNodes() { return this.children; }
  set innerHTML(value) { this.markup = value; }
  get text() { return this.tagName === '#TEXT' ? this.textContent : this.textContent + this.children.map((c) => c.text).join(' '); }
  matches(selector) {
    const s = selector.trim();
    if (s.startsWith('.')) return this.className.split(/\s+/).includes(s.slice(1));
    return this.tagName === s.toUpperCase();
  }
  querySelectorAll(selector) { return all(this).filter((n) => selector.split(',').some((s) => n.matches(s))); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  // A click on a summary opens or closes its disclosure, as a browser's does.
  click() { this.dispatch('click'); if (this.tagName === 'SUMMARY') { this.parent.open = !this.parent.open; this.parent.dispatch('toggle'); } }
}
const all = (n) => n.children.flatMap((c) => [c, ...all(c)]);
const document = { createElement: (t) => new Node(t), body: new Node('body') };
document.querySelectorAll = (s) => document.body.querySelectorAll(s);
const timers = [];
const context = vm.createContext({ document, JSON, Object, Array, String, Number, Math, Set, Map, Date, Promise, Error,
  setTimeout: (fn) => timers.push(fn), module: { exports: {} } });
const load = (name) => { context.module.exports = {}; vm.runInContext(fs.readFileSync(path.join(__dirname, '../ui-kit', name), 'utf8'), context); return context.module.exports; };
const activity = load('activity.js');
context.StudioActivity = activity;
const research = load('research.js');
const settle = async () => { for (let n = 0; n < 20; n++) await Promise.resolve(); };
const keyed = (root, key) => all(root).find((n) => n.dataset.key === key);
const texts = (root, cls) => root.querySelectorAll(cls).map((n) => n.text.replace(/\s+/g, ' ').trim());

(async () => {
  const lines = ['Started', 'Looking at what it was given', 'Searching the web: rolling restart capacity']
    .map((text, n) => ({ at: '2030-01-02T03:04:0' + n + 'Z', text }));
  const worker = { id: 'research:investigate-1-area1', label: 'Investigating research area 1',
    started_at: '2030-01-02T03:04:00Z', now: lines[2], lines, count: 3 };

  // No job runs: nothing is drawn.
  assert.equal(activity.live([]), null);
  assert.equal(activity.live(undefined), null);

  // A running job: its label, when it started, its latest line as "Now:", and Show activity.
  const box = activity.live([worker]);
  assert.equal(box.attributes['aria-label'], 'What the assistant is doing');
  assert.match(box.text, /Investigating research area 1/);
  assert.match(box.text, /Started /);
  assert.equal(texts(box, '.activity-now')[0], 'Now: Searching the web: rolling restart capacity');
  const more = box.querySelector('details');
  assert.equal(more.dataset.key, 'activity research:investigate-1-area1');
  assert.equal(more.querySelector('summary').textContent, 'Show activity (3 steps)');
  assert.ok(more.querySelector('summary').dataset.key, 'the summary is reachable and keyed');
  // Every line so far, newest first, each with its time.
  const shown = more.querySelectorAll('li');
  assert.deepEqual(shown.map((li) => li.querySelector('.activity-text').textContent), [lines[2].text, lines[1].text, lines[0].text]);
  assert.ok(shown.every((li) => li.querySelector('time') && li.querySelector('time').dateTime.startsWith('2030-01-02T03:04:0')));

  // Opened, it stays open when the page draws it again, as on every refresh.
  more.querySelector('summary').click();
  assert.equal(more.open, true);
  assert.equal(activity.live([{ ...worker, lines: [...lines, { at: '2030-01-02T03:04:09Z', text: 'Reading saved source S1' }], count: 4 }])
    .querySelector('details').open, true);
  more.querySelector('summary').click();
  assert.equal(activity.live([worker]).querySelector('details').open, false);

  // A job that has said nothing yet, and lines kept as plain strings, still read.
  assert.match(activity.live([{ id: 'x', label: 'Drafting', started_at: null, lines: [] }]).text, /Just starting\./);
  assert.deepEqual(texts(activity.live([{ id: 'y', label: 'Drafting', lines: ['Writing'] }]), '.activity-now'), ['Now: Writing']);
  // A long job says how many of its lines are shown.
  assert.match(activity.live([{ ...worker, count: 250 }]).text, /Showing the latest 3\./);

  // The research panel shows the same lines while it collects evidence.
  const panel = research.progress({ phase: 'investigate', agents: { count: 1, active: [] },
    streams: [{ id: 'area1', status: 'working', questions: ['Capacity'] }] }, { workers: [worker] });
  assert.match(panel.text, /Collecting evidence/);
  const inside = panel.querySelector('.activity-live');
  assert.ok(inside, 'the research panel holds the live lines');
  assert.match(inside.text, /What the assistant is doing/);
  assert.deepEqual(texts(inside, '.activity-now'), ['Now: Searching the web: rolling restart capacity']);
  // ...while combining findings and checking sources too, and none without workers.
  for (const phase of ['synthesize', 'review']) {
    assert.ok(research.progress({ phase, agents: { count: 1 } }, { workers: [worker] }).querySelector('.activity-live'));
  }
  assert.equal(research.progress({ phase: 'investigate' }).querySelector('.activity-live'), null);

  // The Activity log: read when opened, newest first, each job with how it ended and its lines.
  let asked = 0, answer = { jobs: [
    { id: 'b', label: 'Investigating research area 1', step: 'research:investigate-1-area1', started_at: '2030-01-02T03:04:00Z',
      ended_at: '2030-01-02T03:09:00Z', outcome: 'stopped', words: 'Stopped', lines, dropped: 0 },
    { id: 'a', label: 'Drafting the research plan', step: 'research-plan', started_at: '2030-01-02T02:50:00Z',
      ended_at: '2030-01-02T02:59:00Z', outcome: 'timeout', words: 'Out of time', detail: 'It did not finish in 600 seconds.',
      lines: [], dropped: 0 }], running: [worker], empty: null, limit: 200 };
  const card = activity.logCard({ key: 'activity-log /work/rolling-restarts', load: async () => { asked += 1; return answer; } });
  document.body.replaceChildren(card);
  assert.equal(asked, 0, 'nothing is read until the log is opened');
  assert.ok(card.className.includes('card'), 'an opaque card');
  card.querySelector('summary').click();
  await settle();
  assert.equal(asked, 1);
  const entries = card.querySelectorAll('.activity-entry');
  assert.deepEqual(entries.map((n) => n.querySelector('.activity-ending').text.trim()), ['Stopped', 'Out of time']);
  assert.match(entries[1].text, /It did not finish in 600 seconds\./);
  assert.deepEqual(entries[0].querySelectorAll('.activity-text').map((n) => n.textContent), [lines[2].text, lines[1].text, lines[0].text]);
  assert.match(card.querySelector('.activity-log-body').text, /Working now/);
  // A job in the log opens too, and stays open when the page is drawn again.
  entries[0].querySelector('summary').click();
  const again = activity.logCard({ key: 'activity-log /work/rolling-restarts', load: async () => { asked += 1; return answer; } });
  document.body.replaceChildren(again);
  assert.equal(again.open, true, 'the log stays open when the page is drawn again');
  assert.equal(again.querySelectorAll('.activity-entry')[0].querySelector('details').open, true);
  assert.equal(again.querySelectorAll('.activity-entry').length, 2, 'what was read is shown at once');
  // Refresh reads it again.
  keyed(again, 'activity-log /work/rolling-restarts refresh').dispatch('click');
  await settle();
  assert.equal(asked, 2);

  // A project with no log says so; one that cannot be read says why, and can be tried again.
  const empty = activity.logCard({ key: 'activity-log /work/old', load: async () => ({ jobs: [], running: [], empty: 'No activity recorded yet.' }) });
  document.body.replaceChildren(empty);
  empty.querySelector('summary').click(); await settle();
  assert.match(empty.text, /No activity recorded yet\./);
  let fail = true;
  const broken = activity.logCard({ key: 'activity-log /work/broken', load: async () => { if (fail) throw new Error('No run is driving this training.'); return answer; } });
  document.body.replaceChildren(broken);
  broken.querySelector('summary').click(); await settle();
  assert.match(broken.text, /No run is driving this training\./);
  fail = false;
  keyed(broken, 'activity-log /work/broken again').dispatch('click'); await settle();
  assert.equal(broken.querySelectorAll('.activity-entry').length, 2);
  console.log('activity page check passed');
})().catch((error) => { console.error(error); process.exit(1); });
