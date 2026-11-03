/* What an assistant is doing while it works, and a project's Activity log (#294).
 * Shared by every studio that runs assistant jobs. Plain browser JavaScript: no framework,
 * no build step, no request of its own; the studio passes in how to read its log.
 *
 *   StudioActivity.live(workers)          the running jobs: label, start, "Now:" and
 *                                         Show activity, or null when none runs
 *   StudioActivity.logCard({key, load})   the Activity log, a card that reads the log
 *                                         through load() when it is opened
 *
 * A worker is {id, label, started_at, now: {at, text}, lines: [{at, text}], count}, oldest
 * line first, as studio_core.activity_log.live sends it; a line may also be a plain string.
 * Every disclosure is a native <details> with a data-key, and stays open when the page draws
 * it again, whether or not the page keeps open disclosures itself. */
'use strict';
const StudioActivity = (() => {
  const make = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  };
  const add = (n, ...children) => { n.append(...children.filter((c) => c != null)); return n; };
  const array = (value) => Array.isArray(value) ? value : [];
  const opened = new Set();     // the data-keys of the disclosures open on this page
  const logs = new Map();       // key -> {view, problem, at, loading, load}
  const STALE = 5000;           // ms before an open log is read again when drawn
  const ENDINGS = {finished: 'done', failed: 'late', stopped: 'review', timeout: 'late', limit: 'review'};

  function line(found) {
    if (found && typeof found === 'object') return {at: found.at || null, text: String(found.text || '')};
    return {at: null, text: String(found || '')};
  }

  function stamp(value) {
    const found = value ? new Date(value) : null;
    return found && !Number.isNaN(found.getTime()) ? found : null;
  }

  function clock(value, seconds = true) {
    const found = stamp(value);
    if (!found) return '';
    const options = {hour: 'numeric', minute: '2-digit'};
    if (seconds) options.second = '2-digit';
    return found.toLocaleTimeString([], options);
  }

  function day(value) {
    const found = stamp(value);
    if (!found) return '';
    const today = new Date();
    if (found.toDateString() === today.toDateString()) return 'today';
    return found.toLocaleDateString([], {day: 'numeric', month: 'short',
      ...(found.getFullYear() !== today.getFullYear() ? {year: 'numeric'} : {})});
  }

  // A disclosure that remembers being open, keyed for the page's own keeping too.
  function disclosure(cls, key, summary) {
    const node = make('details', cls);
    node.dataset.key = key;
    const head = make('summary', '', summary);
    head.dataset.key = key + ' toggle';
    node.append(head);
    if (opened.has(key)) node.open = true;
    node.addEventListener('toggle', () => {
      if (node.open) opened.add(key); else opened.delete(key);
    });
    return node;
  }

  // The lines a job said, newest first, each with its time.
  function lineList(lines) {
    const list = make('ol', 'activity-lines');
    for (const one of [...lines].reverse()) {
      const item = make('li');
      const at = stamp(one.at);
      if (at) {
        const time = make('time', 'activity-time', clock(one.at));
        time.dateTime = at.toISOString();
        item.append(time);
      }
      item.append(make('span', 'activity-text', one.text));
      list.append(item);
    }
    return list;
  }

  function job(worker) {
    const lines = array(worker.lines).map(line).filter((one) => one.text);
    const now = worker.now ? line(worker.now) : lines[lines.length - 1];
    const item = make('li', 'activity-job');
    const head = add(make('p', 'activity-job-head'), make('span', 'row-title', worker.label || 'An assistant job'));
    if (worker.started_at) add(head, make('span', 'quiet', 'Started ' + clock(worker.started_at, false)));
    item.append(head);
    if (!now || !now.text) return add(item, make('p', 'quiet', 'Just starting.'));
    item.append(add(make('p', 'activity-now'), make('strong', '', 'Now: '), now.text));
    const count = Number.isInteger(worker.count) ? worker.count : lines.length;
    const shown = disclosure('activity-more', 'activity ' + (worker.id || worker.label),
      'Show activity (' + count + (count === 1 ? ' step' : ' steps') + ')');
    shown.append(lineList(lines));
    if (count > lines.length) {
      shown.append(make('p', 'quiet activity-note', 'Showing the latest ' + lines.length
        + '. The Activity log keeps them when the job ends.'));
    }
    return add(item, shown);
  }

  // The running jobs, or null when none runs. `title` heads them, when given.
  function live(workers, {title = null} = {}) {
    const found = array(workers);
    if (!found.length) return null;
    const box = make('section', 'activity-live');
    box.setAttribute('aria-label', 'What the assistant is doing');
    if (title) box.append(make('h3', 'card-title', title));
    const list = make('ul', 'activity-jobs');
    for (const worker of found) list.append(job(worker));
    return add(box, list);
  }

  function ended(entry) {
    const words = entry.words || {finished: 'Finished', failed: 'Failed', stopped: 'Stopped',
      timeout: 'Out of time', limit: 'Reached a limit'}[entry.outcome] || 'Ended';
    const mark = make('span', 'bead');
    mark.dataset.state = ENDINGS[entry.outcome] || 'none';
    mark.setAttribute('aria-hidden', 'true');
    return add(make('span', 'state activity-ending'), mark, make('span', '', words));
  }

  function logged(entry) {
    const item = make('li', 'activity-entry');
    const lines = array(entry.lines).map(line).filter((one) => one.text);
    const times = [clock(entry.started_at, false), clock(entry.ended_at, false)].filter(Boolean);
    const node = disclosure('activity-entry-lines', 'activity-log ' + (entry.id || entry.ended_at), '');
    const head = node.querySelector('summary');
    add(head, add(make('span', 'activity-entry-head'), make('span', 'row-title', entry.label || 'An assistant job'),
      ended(entry)),
    make('span', 'quiet activity-entry-when', [times.join('–'), day(entry.ended_at || entry.started_at)].filter(Boolean).join(', ')
      + ' · ' + (lines.length === 1 ? '1 step' : lines.length + ' steps')));
    if (entry.detail) node.append(make('p', 'activity-why', entry.detail));
    node.append(lines.length ? lineList(lines) : make('p', 'quiet', 'It said nothing it did.'));
    if (entry.dropped) node.append(make('p', 'quiet activity-note', entry.dropped + ' earlier steps are not kept.'));
    return add(item, node);
  }

  function fill(body, key) {
    const kept = logs.get(key) || {};
    const view = kept.view;
    const parts = [];
    if (kept.problem) {
      const again = make('button', 'button button-quiet', 'Try again');
      again.type = 'button';
      again.dataset.key = key + ' again';
      again.addEventListener('click', () => read(key, true));
      parts.push(add(make('div', 'activity-problem'), make('p', 'problem', kept.problem), again));
    }
    if (!view) {
      if (!kept.problem) parts.push(make('p', 'quiet', 'Reading the Activity log…'));
      body.replaceChildren(...parts);
      return;
    }
    parts.push(make('p', 'quiet', 'Each assistant job that ended, newest first, with what it did. '
      + 'It is kept on this computer for the latest ' + (view.limit || 200) + ' jobs.'));
    const running = live(view.running, {title: 'Working now'});
    if (running) parts.push(running);
    const jobs = array(view.jobs);
    if (jobs.length) {
      const list = make('ol', 'activity-entries');
      for (const entry of jobs) list.append(logged(entry));
      parts.push(list);
    } else {
      parts.push(make('p', 'activity-empty', view.empty || 'No activity recorded yet.'));
    }
    const refresh = make('button', 'button button-quiet', 'Refresh');
    refresh.type = 'button';
    refresh.dataset.key = key + ' refresh';
    refresh.addEventListener('click', () => read(key, true));
    parts.push(add(make('div', 'bar'), refresh));
    body.replaceChildren(...parts);
  }

  function paint(key) {
    for (const body of document.querySelectorAll('.activity-log-body')) {
      if (body.dataset.log === key) fill(body, key);
    }
  }

  async function read(key, fresh = false) {
    const kept = logs.get(key);
    if (!kept || kept.loading) return;
    if (!fresh && kept.view && Date.now() - kept.at < STALE) return;
    kept.loading = true;
    try {
      kept.view = await kept.load();
      kept.problem = '';
      kept.at = Date.now();
    } catch (error) {
      kept.problem = (error && error.message) || 'The Activity log could not be read.';
    } finally {
      kept.loading = false;
      paint(key);
    }
  }

  // The Activity log, as a card the person opens. It is read when opened, and again when the
  // page is drawn while it is open and what it showed is a few seconds old.
  function logCard({key, load, title = 'Activity log', about = null}) {
    const kept = logs.get(key) || {view: null, problem: '', at: 0, loading: false};
    kept.load = load;
    logs.set(key, kept);
    const node = disclosure('card activity-log', key, '');
    const head = node.querySelector('summary');
    head.className = 'activity-log-summary';
    add(head, make('span', 'card-title', title),
      make('span', 'quiet', about || 'What the assistant did in each job, newest first'));
    const body = make('div', 'activity-log-body');
    body.dataset.log = key;
    node.append(body);
    fill(body, key);
    node.addEventListener('toggle', () => { if (node.open) read(key, !kept.view); });
    if (node.open) setTimeout(() => read(key), 0);
    return node;
  }

  return {live, logCard, lineList};
})();
if (typeof module === 'object' && module.exports) module.exports = StudioActivity;
