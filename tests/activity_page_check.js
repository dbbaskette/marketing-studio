/* The shared activity lines and Activity log (ui-kit/activity.js), and the research panel that
 * shows them (ui-kit/research.js), with synthetic workers and a synthetic log only (#294). */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');

class Node {
  constructor(tag) {
    this.tagName = tag.toUpperCase(); this.children = []; this.parent = null; this.dataset = {};
    this.listeners = {}; this.attributes = {}; this.className = ''; this.textContent = ''; this.open = false;
    this.scrollTop = 0; this.hidden = false;
  }
  append(...nodes) { for (const n of nodes) this.insertBefore(n, null); }
  insertBefore(n, before) {
    if (typeof n === 'string') n = Object.assign(new Node('#text'), { textContent: n });
    if (n.parent) n.parent.children = n.parent.children.filter((c) => c !== n);
    n.parent = this;
    const at = before ? this.children.indexOf(before) : -1;
    if (at < 0) this.children.push(n); else this.children.splice(at, 0, n);
    return n;
  }
  get firstChild() { return this.children[0] || null; }
  get lastChild() { return this.children[this.children.length - 1] || null; }
  removeChild(n) { this.children = this.children.filter((c) => c !== n); n.parent = null; return n; }
  // Each line is 20px tall here, so a list's height says how many it holds.
  get scrollHeight() { return this.children.length * 20; }
  replaceChildren(...nodes) { for (const c of this.children) c.parent = null; this.children = []; this.append(...nodes); }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return this.attributes[k]; }
  addEventListener(k, fn) { (this.listeners[k] = this.listeners[k] || []).push(fn); }
  dispatch(k) { for (const fn of this.listeners[k] || []) fn({ target: this }); }
  get childNodes() { return this.children; }
  set innerHTML(value) { this.markup = value; }
  get text() { return this.tagName === '#TEXT' ? this.textContent : this.textContent + this.children.map((c) => c.text).join(' '); }
  contains(n) { for (let at = n; at; at = at.parent) if (at === this) return true; return false; }
  focus() { document.activeElement = this; }
  matches(selector) {
    const s = selector.trim();
    if (s === '[data-key]') return this.dataset.key !== undefined;
    if (s.startsWith('.')) return this.className.split(/\s+/).includes(s.slice(1));
    return this.tagName === s.toUpperCase();
  }
  querySelectorAll(selector) { return all(this).filter((n) => selector.split(',').some((s) => n.matches(s))); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  // A click on a summary opens or closes its disclosure, as a browser's does.
  click() { this.dispatch('click'); if (this.tagName === 'SUMMARY') { this.parent.open = !this.parent.open; this.parent.dispatch('toggle'); } }
}
const all = (n) => n.children.flatMap((c) => [c, ...all(c)]);
const document = { createElement: (t) => new Node(t), body: new Node('body'), activeElement: null };
document.querySelectorAll = (s) => document.body.querySelectorAll(s);
const timers = [];
const context = vm.createContext({ document, JSON, Object, Array, String, Number, Math, Set, Map, Date, Promise, Error,
  setTimeout: (fn) => timers.push(fn), requestAnimationFrame: (fn) => timers.push(fn), module: { exports: {} } });
const load = (name) => { context.module.exports = {}; vm.runInContext(fs.readFileSync(path.join(__dirname, '../ui-kit', name), 'utf8'), context); return context.module.exports; };
const activity = load('activity.js');
context.StudioActivity = activity;
const research = load('research.js');
const settle = async () => { for (let n = 0; n < 20; n++) await Promise.resolve(); };
const tick = () => { while (timers.length) timers.shift()(); };
const keyed = (root, key) => all(root).find((n) => n.dataset.key === key);
const texts = (root, cls) => root.querySelectorAll(cls).map((n) => n.text.replace(/\s+/g, ' ').trim());
const said = (root) => root.querySelectorAll('.activity-text').map((n) => n.textContent);

(async () => {
  const lines = ['Started', 'Looking at what it was given', 'Searching the web: rolling restart capacity',
    'Reading saved source S1', 'Handing back research-result'].map((text, n) => ({ at: '2030-01-02T03:04:0' + n + 'Z', text }));
  // The server's side of an open Show activity: the lines from the `since`th on.
  const asked = [];
  let said_so_far = 3;
  const jobLines = async (id, since) => {
    asked.push([id, since]);
    return { lines: lines.slice(since, said_so_far), count: said_so_far, start: 0, running: true };
  };
  const polled = (count) => ({ id: 'research:investigate-1-area1', label: 'Investigating research area 1',
    started_at: '2030-01-02T03:04:00Z', now: lines[count - 1], count });

  // No job runs: nothing is drawn.
  assert.equal(activity.live([]), null);
  assert.equal(activity.live(undefined), null);

  // A running job, as a poll carries it: its label, its start, "Now:" and Show activity. No
  // line is read until Show activity is opened.
  const holder = new Node('div'); document.body.replaceChildren(holder);
  let box = activity.update(holder, [polled(3)], { load: jobLines });
  assert.equal(box.attributes['aria-label'], 'What the assistant is doing');
  assert.match(box.text, /Investigating research area 1/);
  assert.match(box.text, /Started /);
  assert.deepEqual(texts(box, '.activity-now'), ['Now: Searching the web: rolling restart capacity']);
  const summary = () => holder.querySelector('summary');
  assert.equal(summary().textContent, 'Show activity (3 steps)');
  assert.equal(holder.querySelector('details').dataset.key, 'activity research:investigate-1-area1');
  assert.deepEqual(asked, [], 'a closed Show activity reads nothing');

  // Opened by the keyboard's control, it reads the lines so far, newest first, each with its time.
  summary().focus(); summary().click(); await settle();
  assert.deepEqual(asked, [['research:investigate-1-area1', 0]]);
  assert.deepEqual(said(holder), [lines[2].text, lines[1].text, lines[0].text]);
  assert.ok(holder.querySelectorAll('time').every((t) => t.dateTime.startsWith('2030-01-02T03:04:0')));

  // A new line: the page draws it again. It stays open, the focus stays on Show activity, only
  // the new line is read, and the list keeps the place it was scrolled to.
  const list = holder.querySelector('.activity-lines');
  list.scrollTop = 20; list.dispatch('scroll');
  said_so_far = 4;
  box = activity.update(holder, [polled(4)], { load: jobLines });
  await settle(); tick();
  assert.equal(holder.querySelector('details').open, true);
  assert.equal(document.activeElement && document.activeElement.dataset.key, 'activity research:investigate-1-area1 toggle');
  assert.deepEqual(asked.at(-1), ['research:investigate-1-area1', 3], 'only the lines it has not had');
  assert.equal(holder.querySelector('.activity-lines'), list, 'the same list, moved, not drawn again');
  assert.deepEqual(said(holder), [lines[3].text, lines[2].text, lines[1].text, lines[0].text]);
  assert.equal(list.scrollTop, 40, 'reading further down, the same line stays in view');
  assert.equal(summary().textContent, 'Show activity (4 steps)');
  // Drawn again with nothing new, nothing is read.
  const before = asked.length;
  activity.update(holder, [polled(4)], { load: jobLines }); await settle();
  assert.equal(asked.length, before);
  // Closed, it stays closed when drawn again.
  summary().click();
  assert.equal(activity.update(holder, [polled(4)], { load: jobLines }).querySelector('details').open, false);

  // A job that has said nothing yet, and lines carried with the worker, still read.
  assert.match(activity.live([{ id: 'x', label: 'Drafting', started_at: null }]).text, /Just starting\./);
  const carried = activity.live([{ id: 'y', label: 'Drafting', lines: ['Writing'] }]);
  assert.deepEqual(texts(carried, '.activity-now'), ['Now: Writing']);
  assert.deepEqual(said(carried), ['Writing']);
  // Opened late, a long job says that its earliest lines are not here.
  const late = async () => ({ lines: lines.slice(0, 2), count: 250, start: 248, running: true });
  const longOne = new Node('div');
  const first = activity.update(longOne, [{ id: 'long', label: 'Long', now: lines[1], count: 250 }], { load: late });
  first.querySelector('summary').click(); await settle();
  activity.update(longOne, [{ id: 'long', label: 'Long', now: lines[1], count: 250 }], { load: late });
  assert.match(longOne.text, /Showing the latest 2\./);

  // Another try of the same step, with the same id: its lines are its own, read from the start,
  // not the earlier try's (#294 review).
  const tries = { 1: lines.slice(0, 5), 2: lines.slice(0, 2).map((one) => ({ ...one, text: 'Try 2: ' + one.text })) };
  let trying = 1;
  const triedAsked = [];
  const tried = async (id, since) => { triedAsked.push([trying, since]); return { lines: tries[trying].slice(since), count: tries[trying].length, start: 0 }; };
  tried.scope = '/work/rolling-restarts';
  const step = (n, count) => ({ id: 'research-plan', label: 'Drafting the research plan', started_at: '2030-01-02T0' + n + ':00:00Z',
    now: tries[n][count - 1], count });
  const retry = new Node('div');
  activity.update(retry, [step(1, 5)], { load: tried }).querySelector('summary').click(); await settle();
  assert.equal(said(retry).length, 5);
  trying = 2;
  activity.update(retry, [step(2, 2)], { load: tried }); await settle();
  assert.equal(retry.querySelector('summary').textContent, 'Show activity (2 steps)');
  assert.deepEqual(triedAsked.at(-1), [2, 0], 'the new try is read from its first line');
  assert.deepEqual(said(retry), ['Try 2: ' + lines[1].text, 'Try 2: ' + lines[0].text]);

  // The same step of another training is another job: switching shows each its own lines.
  const elsewhere = async (id, since) => ({ lines: [{ at: lines[0].at, text: 'Elsewhere: ' + id }].slice(since), count: 1, start: 0 });
  elsewhere.scope = '/work/canary-releases';
  const other = new Node('div');
  activity.update(other, [{ ...step(2, 2), now: { at: lines[0].at, text: 'Elsewhere' }, count: 1 }], { load: elsewhere }); await settle();
  assert.deepEqual(said(other), ['Elsewhere: research-plan']);
  activity.update(retry, [step(2, 2)], { load: tried }); await settle();
  assert.deepEqual(said(retry), ['Try 2: ' + lines[1].text, 'Try 2: ' + lines[0].text], 'each training keeps its own');

  // A job that ends while its Show activity is open is said to have ended, while others run.
  activity.update(retry, [{ id: 'research:author-1', label: 'Researching', started_at: lines[0].at, now: lines[0], count: 1 }], { load: tried });
  assert.match(retry.text, /Drafting the research plan ended\. What it did is in the Activity log\./);

  // A long job keeps its newest 200 lines here, and says so.
  const many = Array.from({ length: 250 }, (_, n) => ({ at: lines[0].at, text: 'Line ' + n }));
  const long = async (id, since) => ({ lines: many.slice(since), count: many.length, start: 0 });
  long.scope = '/work/long';
  const longer = new Node('div');
  const big = { id: 'section-1', label: 'Drawing section 1', started_at: lines[0].at, now: many[249], count: 250 };
  activity.update(longer, [big], { load: long }).querySelector('summary').click(); await settle();
  activity.update(longer, [big], { load: long });
  assert.equal(longer.querySelectorAll('.activity-text').length, 200);
  assert.equal(said(longer)[0], 'Line 249');
  assert.match(longer.text, /Showing the latest 200\./);

  // The research panel shows the same while it collects evidence, combines findings and checks
  // sources, and reads lines through the studio's own hook.
  const panel = research.progress({ phase: 'investigate', agents: { count: 1, active: [] },
    streams: [{ id: 'area1', status: 'working', questions: ['Capacity'] }] }, { workers: [polled(3)], lines: jobLines });
  assert.match(panel.text, /Collecting evidence/);
  const inside = panel.querySelector('.activity-live');
  assert.ok(inside, 'the research panel holds the live lines');
  assert.match(inside.text, /What the assistant is doing/);
  assert.deepEqual(texts(inside, '.activity-now'), ['Now: Searching the web: rolling restart capacity']);
  for (const phase of ['synthesize', 'review']) {
    assert.ok(research.progress({ phase, agents: { count: 1 } }, { workers: [polled(3)] }).querySelector('.activity-live'));
  }
  assert.equal(research.progress({ phase: 'investigate' }).querySelector('.activity-live'), null);

  // The Activity log: headers read when opened, newest first, each job with how it ended; a
  // job's lines are read when that job is opened, once.
  let readLog = 0, readEntry = [];
  const answer = { jobs: [
    { id: 'b', label: 'Investigating research area 1', step: 'research:investigate-1-area1', started_at: '2030-01-02T03:04:00Z',
      ended_at: '2030-01-02T03:09:00Z', outcome: 'stopped', words: 'Stopped', steps: 3, dropped: 0 },
    { id: 'a', label: 'Drafting the research plan', step: 'research-plan', started_at: '2030-01-02T02:50:00Z',
      ended_at: '2030-01-02T02:59:00Z', outcome: 'timeout', words: 'Out of time', detail: 'It did not finish in 600 seconds.',
      steps: 0, dropped: 0 }], running: [polled(3)], empty: null, limit: 200 };
  const options = { key: 'activity-log /work/rolling-restarts', load: async () => { readLog += 1; return answer; },
    entry: async (id) => { readEntry.push(id); return { id, lines: id === 'b' ? lines.slice(0, 3) : [], dropped: 0 }; } };
  const card = activity.logCard(options);
  document.body.replaceChildren(card);
  assert.equal(readLog, 0, 'nothing is read until the log is opened');
  assert.ok(card.className.includes('card'), 'an opaque card');
  card.querySelector('summary').click();
  await settle();
  assert.equal(readLog, 1);
  const entries = card.querySelectorAll('.activity-entry');
  assert.deepEqual(entries.map((n) => n.querySelector('.activity-ending').text.trim()), ['Stopped', 'Out of time']);
  assert.match(entries[0].text, /3 steps/);
  assert.match(entries[1].text, /It did not finish in 600 seconds\./);
  assert.deepEqual(readEntry, [], 'a job\'s lines are read only when it is opened');
  assert.match(card.querySelector('.activity-log-body').text, /1 job is still working and will appear here when it ends\./);
  assert.equal(card.querySelector('.activity-live'), null, 'a running job is shown with the work, not again in the log');
  entries[0].querySelector('summary').click(); await settle();
  assert.deepEqual(readEntry, ['b']);
  assert.deepEqual(said(entries[0]), [lines[2].text, lines[1].text, lines[0].text]);
  // Drawn again, the log and the job stay open, and nothing is read again.
  const again = activity.logCard(options);
  document.body.replaceChildren(again);
  assert.equal(again.open, true, 'the log stays open when the page is drawn again');
  assert.equal(again.querySelectorAll('.activity-entry')[0].querySelector('details').open, true);
  assert.deepEqual(said(again.querySelectorAll('.activity-entry')[0]), [lines[2].text, lines[1].text, lines[0].text]);
  assert.deepEqual(readEntry, ['b']);
  // Refresh reads it again, and keeps the focus on Refresh.
  const refresh = keyed(again, 'activity-log /work/rolling-restarts refresh');
  refresh.focus(); refresh.dispatch('click'); await settle();
  assert.equal(readLog, 2);
  assert.equal(document.activeElement.dataset.key, 'activity-log /work/rolling-restarts refresh');

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
