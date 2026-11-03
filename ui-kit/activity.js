/* What an assistant is doing while it works, and a project's Activity log (#294).
 * Shared by every studio that runs assistant jobs. Plain browser JavaScript: no framework,
 * no build step, no request of its own; the studio passes in how to read what it needs.
 *
 *   StudioActivity.live(workers, {load})   the running jobs: label, start, "Now:" and Show
 *                                          activity, or null when none runs
 *   StudioActivity.update(holder, workers, {load})   the same, drawn into `holder` again,
 *                                          keeping the focus, what is open and its scroll
 *   StudioActivity.logCard({key, load, entry})       the Activity log, a card that reads the
 *                                          log when it is opened, and each job's lines when
 *                                          that job is opened
 *
 * A worker is {id, label, started_at, now: {at, text}, count}, as the page polls it
 * (studio_core.activity_log.live): never its lines. While a job's Show activity is open,
 * `load(id, since)` is asked for the lines from the `since`th on ({lines, count, start}); the
 * lines already had are kept here, so each new line is fetched once and the list, its scroll
 * and what was read stay as they were when the page draws it again. A worker may instead
 * carry its `lines` (each {at, text} or a plain string), which are shown as they are.
 * `load.scope`, when the studio sets it, names the project the jobs belong to: a job's kept
 * lines are its project's, its id's and its start's, so another try of the same step, or the
 * same step of another project, starts afresh. Jobs no longer drawn are let go.
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
  const logs = new Map();       // log key -> {view, problem, at, loading, load, entry}
  const jobs = new Map();       // scope, id -> {started, lines, count, list, scroll, loading}
  const finished = new Map();   // scope -> [{label, at}]: jobs that ended while shown open
  const KEEP = 200;             // lines this page keeps of one running job, newest
  const ENDED_FOR = 30000;      // ms a job that ended while open is said to have ended
  const entries = new Map();    // a finished job's key -> {lines, dropped, loading, problem}
  const STALE = 5000;           // ms before an open log is read again when drawn
  const ENDINGS = {finished: 'done', failed: 'late', stopped: 'review', timeout: 'late', limit: 'review'};
  const later = (fn) => (typeof requestAnimationFrame === 'function' ? requestAnimationFrame(fn) : setTimeout(fn, 0));

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

  const steps = (count) => count + (count === 1 ? ' step' : ' steps');

  // A disclosure that remembers being open, keyed for the page's own keeping too. `opening`
  // is called each time it opens.
  function disclosure(cls, key, summary, opening) {
    const node = make('details', cls);
    node.dataset.key = key;
    const head = make('summary', '', summary);
    head.dataset.key = key + ' toggle';
    node.append(head);
    if (opened.has(key)) node.open = true;
    node.addEventListener('toggle', () => {
      if (node.open) { opened.add(key); if (opening) opening(); } else opened.delete(key);
    });
    return node;
  }

  function lineItem(one) {
    const item = make('li');
    const at = stamp(one.at);
    if (at) {
      const time = make('time', 'activity-time', clock(one.at));
      time.dateTime = at.toISOString();
      time.dataset.clock = '';   // a clock time to the second: a page's "minutes ago" leaves it be
      item.append(time);
    }
    item.append(make('span', 'activity-text', one.text));
    return item;
  }

  // The lines a job said, newest first, each with its time.
  function lineList(lines) {
    const list = make('ol', 'activity-lines');
    for (const one of [...lines].reverse()) list.append(lineItem(one));
    return list;
  }

  // A running job's lines, kept across drawings: the same list, with the newest added at its
  // top, and the place it was scrolled to kept.
  function heldLines(key, started = null, count = 0) {
    let held = jobs.get(key);
    // Another try of the same step, started again or counting from the beginning: afresh.
    if (held && (held.started !== started || count < held.count)) {
      jobs.delete(key);
      held = null;
    }
    if (!held) {
      held = {started, lines: [], count: 0, start: 0, list: make('ol', 'activity-lines'), scroll: 0, loading: false};
      held.key = key;
      held.list.addEventListener('scroll', () => { held.scroll = held.list.scrollTop; });
      jobs.set(key, held);
    }
    return held;
  }

  function took(held, found) {
    const arrived = array(found && found.lines).map(line).filter((one) => one.text);
    if (!arrived.length) { held.count = Math.max(held.count, Number(found && found.count) || 0); return; }
    const before = held.list.scrollHeight || 0;
    const first = held.list.firstChild;
    for (const one of arrived) held.list.insertBefore(lineItem(one), held.list.firstChild || null);
    // Someone reading further down keeps reading the same line as new ones arrive above.
    if (first && held.scroll > 0 && held.list.scrollHeight) {
      held.scroll += held.list.scrollHeight - before;
      held.list.scrollTop = held.scroll;
    }
    if (!held.lines.length) held.start = Number(found.start) || 0;   // lines dropped before it was opened
    held.lines.push(...arrived);
    held.count = Number(found.count) || held.lines.length;
    // A long job: only its newest KEEP lines are kept here, as the runner keeps them.
    while (held.list.children.length > KEEP) held.list.removeChild(held.list.lastChild);
    if (held.lines.length > KEEP) {
      held.start += held.lines.length - KEEP;
      held.lines = held.lines.slice(-KEEP);
    }
  }

  async function fetchLines(held, worker, load) {
    if (held.loading || !load) return;
    held.loading = true;
    try {
      const found = await load(worker.id, held.count);
      if (jobs.get(held.key) === held) took(held, found);   // not for a try since let go
    } catch (failure) {
      held.problem = (failure && failure.message) || 'What it did could not be read.';
    } finally {
      held.loading = false;
    }
  }

  function job(worker, load) {
    const given = worker.lines !== undefined ? array(worker.lines).map(line).filter((one) => one.text) : null;
    const now = worker.now ? line(worker.now) : given && given[given.length - 1];
    const item = make('li', 'activity-job');
    const head = add(make('p', 'activity-job-head'), make('span', 'row-title', worker.label || 'An assistant job'));
    if (worker.started_at) add(head, make('span', 'quiet', 'Started ' + clock(worker.started_at, false)));
    item.append(head);
    if (!now || !now.text) return add(item, make('p', 'quiet', 'Just starting.'));
    item.append(add(make('p', 'activity-now'), make('strong', '', 'Now: '), now.text));
    const count = Number.isInteger(worker.count) ? worker.count : given ? given.length : 0;
    const key = 'activity ' + (worker.id || worker.label);
    if (given) {
      const shown = disclosure('activity-more', key, 'Show activity (' + steps(count) + ')');
      shown.append(lineList(given));
      return add(item, shown);
    }
    const held = heldLines(scopeOf(load) + '\n' + (worker.id || worker.label), worker.started_at || null, count);
    held.label = worker.label || 'An assistant job';
    const ask = () => { if (count > held.count) fetchLines(held, worker, load); };
    const shown = disclosure('activity-more', key, 'Show activity (' + steps(count) + ')', ask);
    shown.append(held.list);
    if (held.start > 0) shown.append(make('p', 'quiet activity-note', 'Showing the latest '
      + held.lines.length + '. The Activity log keeps them when the job ends.'));
    if (shown.open) {
      ask();
      // The list was moved here from the last drawing: put it back where it was scrolled to.
      if (held.scroll) later(() => { held.list.scrollTop = held.scroll; });
    }
    return add(item, shown);
  }

  const scopeOf = (load) => String((load && load.scope) || '');

  // Let go of the kept lines of this project's jobs that are no longer drawn; one that was
  // open is said, for a little while, to have ended, so its lines do not just vanish.
  function letGo(scope, found) {
    const drawn = new Set(found.map((worker) => scope + '\n' + (worker.id || worker.label)));
    const now = Date.now();
    const said = (finished.get(scope) || []).filter((one) => now - one.at < ENDED_FOR);
    for (const [key, held] of jobs) {
      if (!key.startsWith(scope + '\n') || drawn.has(key)) continue;
      if (held.label && opened.has('activity ' + key.slice(scope.length + 1))) said.push({label: held.label, at: now});
      jobs.delete(key);
    }
    if (said.length) finished.set(scope, said); else finished.delete(scope);
    return said;
  }

  // The running jobs, or null when none runs. `title` heads them, when given.
  function live(workers, {title = null, load = null} = {}) {
    const found = array(workers);
    const gone = load ? letGo(scopeOf(load), found) : [];
    if (!found.length) return null;
    const box = make('section', 'activity-live');
    box.setAttribute('aria-label', 'What the assistant is doing');
    if (title) box.append(make('h3', 'card-title', title));
    const list = make('ul', 'activity-jobs');
    for (const worker of found) list.append(job(worker, load));
    add(box, list);
    for (const one of gone) {
      box.append(make('p', 'quiet activity-note', one.label + ' ended. What it did is in the Activity log.'));
    }
    return box;
  }

  // The running jobs drawn into `holder` again: the control that had the focus has it again.
  function update(holder, workers, options = {}) {
    const active = typeof document.activeElement === 'object' ? document.activeElement : null;
    const focused = active && holder.contains && holder.contains(active) && active.dataset ? active.dataset.key : '';
    const shown = live(workers, options);
    holder.replaceChildren(...(shown ? [shown] : []));
    holder.hidden = !shown;
    if (focused) {
      const again = Array.from(holder.querySelectorAll('[data-key]')).find((n) => n.dataset.key === focused);
      if (again) again.focus({preventScroll: true});
    }
    return shown;
  }

  function ended(entry) {
    const words = entry.words || {finished: 'Finished', failed: 'Failed', stopped: 'Stopped',
      timeout: 'Out of time', limit: 'Reached a limit'}[entry.outcome] || 'Ended';
    const mark = make('span', 'bead');
    mark.dataset.state = ENDINGS[entry.outcome] || 'none';
    mark.setAttribute('aria-hidden', 'true');
    return add(make('span', 'state activity-ending'), mark, make('span', '', words));
  }

  // A finished job's lines, read when it is first opened and kept.
  function entryBody(body, entry, logKey) {
    const key = logKey + ' ' + entry.id;
    const held = entries.get(key) || {};
    const given = entry.lines !== undefined ? {lines: entry.lines, dropped: entry.dropped} : held.lines ? held : null;
    const parts = [entry.detail ? make('p', 'activity-why', entry.detail) : null];
    if (given) {
      const lines = array(given.lines).map(line).filter((one) => one.text);
      parts.push(lines.length ? lineList(lines) : make('p', 'quiet', 'It said nothing it did.'));
      if (given.dropped) parts.push(make('p', 'quiet activity-note', given.dropped + ' earlier steps are not kept.'));
    } else if (held.problem) {
      parts.push(make('p', 'problem', held.problem));
    } else {
      parts.push(make('p', 'quiet', 'Reading what it did…'));
    }
    body.replaceChildren(...parts.filter(Boolean));
  }

  async function readEntry(body, entry, logKey) {
    const kept = logs.get(logKey);
    const key = logKey + ' ' + entry.id;
    const held = entries.get(key) || {};
    if (entry.lines !== undefined || held.lines || held.loading || !kept || !kept.entry) return;
    held.loading = true; entries.set(key, held);
    try {
      const found = await kept.entry(entry.id);
      held.lines = array(found && found.lines); held.dropped = found && found.dropped; held.problem = '';
    } catch (failure) {
      held.problem = (failure && failure.message) || 'What it did could not be read.';
    } finally {
      held.loading = false;
      entryBody(body, entry, logKey);
    }
  }

  function logged(entry, logKey) {
    const item = make('li', 'activity-entry');
    const count = Number.isInteger(entry.steps) ? entry.steps : array(entry.lines).length;
    const times = [clock(entry.started_at, false), clock(entry.ended_at, false)].filter(Boolean);
    const body = make('div', 'activity-entry-body');
    const node = disclosure('activity-entry-lines', 'activity-log ' + (entry.id || entry.ended_at), '',
      () => readEntry(body, entry, logKey));
    const head = node.querySelector('summary');
    add(head, add(make('span', 'activity-entry-head'), make('span', 'row-title', entry.label || 'An assistant job'),
      ended(entry)),
    make('span', 'quiet activity-entry-when', [times.join('–'), day(entry.ended_at || entry.started_at)].filter(Boolean).join(', ')
      + ' · ' + steps(count)));
    entryBody(body, entry, logKey);
    node.append(body);
    if (node.open) readEntry(body, entry, logKey);
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
    // A job still running is shown where the page shows its work, not again here.
    const running = array(view.running).length;
    parts.push(make('p', 'quiet', 'Each assistant job that ended, newest first, with what it did. '
      + 'It is kept on this computer for the latest ' + (view.limit || 200) + ' jobs.'
      + (running ? ' ' + running + (running === 1 ? ' job is' : ' jobs are') + ' still working and will appear here when '
        + (running === 1 ? 'it ends.' : 'they end.') : '')));
    const found = array(view.jobs);
    if (found.length) {
      const list = make('ol', 'activity-entries');
      for (const entry of found) list.append(logged(entry, key));
      parts.push(list);
    } else {
      parts.push(make('p', 'activity-empty', view.empty || 'No activity recorded yet.'));
    }
    const refresh = make('button', 'button button-quiet', 'Refresh');
    refresh.type = 'button';
    refresh.dataset.key = key + ' refresh';
    refresh.addEventListener('click', () => read(key, true));
    parts.push(add(make('div', 'bar'), refresh));
    // Redrawn in place: the control that had the focus has it again.
    const active = document.activeElement;
    const focused = active && body.contains && body.contains(active) && active.dataset ? active.dataset.key : '';
    body.replaceChildren(...parts);
    if (focused) {
      const again = Array.from(body.querySelectorAll('[data-key]')).find((n) => n.dataset.key === focused);
      if (again) again.focus({preventScroll: true});
    }
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
  // page is drawn while it is open and what it showed is a few seconds old. `entry(id)` reads
  // one finished job's lines when the person opens that job.
  function logCard({key, load, entry = null, title = 'Activity log', about = null}) {
    const kept = logs.get(key) || {view: null, problem: '', at: 0, loading: false};
    kept.load = load;
    kept.entry = entry;
    logs.set(key, kept);
    const node = disclosure('card activity-log', key, '', () => read(key, !kept.view));
    const head = node.querySelector('summary');
    head.className = 'activity-log-summary';
    add(head, make('span', 'card-title', title),
      make('span', 'quiet', about || 'What the assistant did in each job, newest first'));
    const body = make('div', 'activity-log-body');
    body.dataset.log = key;
    node.append(body);
    fill(body, key);
    if (node.open) setTimeout(() => read(key), 0);
    return node;
  }

  return {live, update, logCard, lineList};
})();
if (typeof module === 'object' && module.exports) module.exports = StudioActivity;
