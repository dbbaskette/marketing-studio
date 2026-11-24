// The desk base Presentation Studio's and Training Studio's pages both load, served by the
// shared page server beside the deck panels, after the shell kit and before each page's
// app.js: the small parts both pages draw and speak with, once, in place of a copy in each.
// Each part is plain: it is handed everything it works on and keeps no page state. A page
// takes them by name from window.StudioDesk. Plain DOM, no build step, and no markup: every
// value is set as text.
(function () {
  'use strict';

  const byId = (id) => document.getElementById(id);

  const main = () => byId('main');

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function add(parent, ...children) {
    for (const child of children) {
      if (child) parent.append(child);
    }
    return parent;
  }

  function count(number, one, many) {
    return number + ' ' + (number === 1 ? one : many);
  }

  function list(value) {
    return Array.isArray(value) ? value : [];
  }

  // Several things named in a row: "one, two and three".
  function series(items) {
    return items.length < 2 ? items.join('')
      : items.slice(0, -1).join(', ') + ' and ' + items[items.length - 1];
  }

  function ago(then) {
    const minutes = Math.round((Date.now() - then) / 60000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return count(minutes, 'minute', 'minutes') + ' ago';
    const hours = Math.round(minutes / 60);
    if (hours < 24) return count(hours, 'hour', 'hours') + ' ago';
    const days = Math.round(hours / 24);
    if (days < 30) return count(days, 'day', 'days') + ' ago';
    return new Date(then).toLocaleDateString(undefined,
      { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function when(stamp) {
    const then = Date.parse(stamp);
    if (Number.isNaN(then)) return make('span', 'quiet', 'not recorded');
    const node = make('time', '', ago(then));
    node.dateTime = new Date(then).toISOString();
    node.title = new Date(then).toLocaleString();
    return node;
  }

  // A limit, in the round numbers a limit is set in: 8,000,000 bytes is 8 MB.
  function megabytes(bytes) {
    return String(Math.round(bytes / 100000) / 10) + ' MB';
  }

  function pathInto(node, path) {
    String(path).split('/').forEach((part, index) => {
      if (index) add(node, '/', document.createElement('wbr'));
      add(node, part);
    });
    return node;
  }

  function button(label, className, action, key) {
    const node = make('button', className, label);
    node.type = 'button';
    if (key) node.dataset.key = key;
    node.addEventListener('click', action);
    return node;
  }

  // A capsule of glass. The highlight on it follows the pointer.
  function capsule(label, kind, action, key) {
    return button(label, 'button shine' + (kind ? ' button-' + kind : ''), action, key);
  }

  // The filled button of a form. Pressing it, or Enter in one of the form's boxes, sends it.
  function submitButton(label, key) {
    const node = make('button', 'button shine button-filled', label);
    node.type = 'submit';
    node.dataset.key = key;
    return node;
  }

  // A form in the page's narrow column. The browser checks nothing in it: `sent` does, and
  // says what is wrong beside each box.
  function pageForm(sent) {
    const node = make('form', 'narrow');
    node.noValidate = true;
    node.addEventListener('submit', (event) => {
      event.preventDefault();
      sent();
    });
    return node;
  }

  function card(title, className) {
    const node = make('section', 'card shine' + (className ? ' ' + className : ''));
    return add(node, make('h2', 'card-title', title));
  }

  function bullets(items, className) {
    const node = make('ul', className || 'plain');
    for (const item of items) node.append(make('li', '', item));
    return node;
  }

  function callout(kind, ...children) {
    const node = make('div', 'paper callout');
    if (kind) node.dataset.kind = kind;
    return add(node, ...children);
  }

  // A control with two answers, or three. Its glass thumb slides to the one that is chosen.
  function segmented(label, options, at, choose, key) {
    const node = make('div', 'segmented');
    node.setAttribute('role', 'group');
    node.setAttribute('aria-label', label);
    node.dataset.at = String(at);
    node.dataset.count = String(options.length);
    const thumb = make('span', 'seg-thumb');
    thumb.setAttribute('aria-hidden', 'true');
    node.append(thumb);
    options.forEach((text, index) => {
      const option = button(text, 'seg-option', () => {
        if (index !== Number(node.dataset.at)) choose(index, node);
      }, key + ' ' + index);
      option.setAttribute('aria-pressed', String(index === at));
      node.append(option);
    });
    return node;
  }

  function slide(node, at) {
    node.dataset.at = String(at);
    node.querySelectorAll('.seg-option').forEach((option, index) => {
      option.setAttribute('aria-pressed', String(index === at));
    });
  }

  // A line beside a control that says why it was refused. It is read out when it appears.
  function alertLine(id) {
    const node = make('p', 'problem');
    node.id = id;
    node.setAttribute('role', 'alert');
    node.hidden = true;
    return node;
  }

  // A phone: the page's own width query for the narrow layout matches.
  function narrow() {
    return Boolean(window.matchMedia && window.matchMedia('(max-width: 52rem)').matches);
  }

  function money(dollars) {
    return '$' + Number(dollars).toFixed(2);
  }

  function lasted(seconds) {
    const whole = Math.round(Number(seconds));
    if (whole < 60) return count(whole, 'second', 'seconds');
    const minutes = Math.round(whole / 60);
    if (minutes < 60) return count(minutes, 'minute', 'minutes');
    return count(Math.floor(minutes / 60), 'hour', 'hours') + ' '
      + count(minutes % 60, 'minute', 'minutes');
  }

  function lower(text) {
    return String(text).charAt(0).toLowerCase() + String(text).slice(1);
  }

  function capital(text) {
    return String(text).charAt(0).toUpperCase() + String(text).slice(1);
  }

  // A word the runner uses for a kind or a state, as a person would write it.
  function spoken(word) {
    return capital(String(word).replace(/[-_]+/g, ' '));
  }

  function given(value) {
    return value !== null && value !== undefined;
  }

  function cell(label, ...children) {
    const node = make('td');
    node.dataset.label = label;
    return add(node, ...children);
  }

  async function saidBy(response) {
    try {
      return await response.json();
    } catch (failure) {
      return null;
    }
  }

  function notify(text) {
    byId('notice').textContent = text;
    byId('notice').hidden = !text;
  }

  function copyBySelection(text) {
    const holder = make('textarea', 'offscreen');
    holder.value = text;
    holder.readOnly = true;
    holder.setAttribute('aria-hidden', 'true');
    document.body.append(holder);
    holder.select();
    let copied = false;
    try {
      copied = document.execCommand('copy');
    } catch (failure) {
      copied = false;
    }
    holder.remove();
    return copied;
  }

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (failure) {
      return copyBySelection(text);
    }
  }

  // A toolbar's actions: the one filled action first, then the rest, each quiet. A screen
  // passes at most one filled action. On a phone they wrap under the title.
  function ordered(actions) {
    actions = list(actions).filter(Boolean);
    const filled = (node) => Boolean(node.classList && node.classList.contains('button-filled'));
    const lead = actions.filter(filled);
    const rest = actions.filter((node) => !filled(node));
    for (const node of rest) {
      const control = node.tagName === 'DETAILS' ? node.querySelector('summary') : node;
      if (control && control.classList && control.classList.contains('button')
          && !control.classList.contains('button-danger')) control.classList.add('button-quiet');
    }
    return [...lead, ...rest];
  }

  // A screen's header: the one sentence that says what the screen is for, and the view's own
  // actions in a bar beside it.
  function pageHead(lede, beside) {
    const actions = list(beside).filter(Boolean);
    return add(make('div', 'page-head'), typeof lede === 'string' ? make('p', 'lede', lede) : lede,
      actions.length ? add(make('div', 'bar'), ...actions) : null);
  }

  function focusKey(key) {
    for (const node of document.querySelectorAll('[data-key]')) {
      if (node.dataset.key === key && !node.disabled) {
        node.focus({ preventScroll: true });
        return true;
      }
    }
    return false;
  }

  // Puts each held question back among `nodes`, in place. One whose part has gone goes too;
  // Drafting.confirmInPlace then answers it with its way out, so nothing is discarded.
  function placeAsking(nodes, pending) {
    for (const [node, after] of pending) {
      if (after === null) { nodes.unshift(node); continue; }
      const at = nodes.indexOf(after);
      if (at < 0) node.remove();
      else nodes.splice(at + 1, 0, node);
    }
  }

  function sheetTitle(text) {
    const node = make('h2', 'sheet-title', text);
    node.id = 'sheet-title';
    return node;
  }

  function problemLine() {
    const node = make('p', 'problem');
    node.id = 'sheet-problem';
    node.setAttribute('role', 'alert');
    node.hidden = true;
    return node;
  }

  // A question asked in place (Drafting.confirmInPlace): beside the control that asked; under
  // its row where it sits in a list row, which lays its parts out in a line; or at the top of
  // the page where the control is in the toolbar or there is none. `ask(place)` asks it.
  function askedFrom(control) {
    return control && control.closest && control.closest('main') ? null : main();
  }

  function alerts() {
    return typeof Notification === 'undefined' ? 'none' : Notification.permission;
  }

  function about(pairs) {
    const node = make('dl', 'about');
    for (const [name, value] of pairs) {
      if (given(value) && value !== '') add(node, make('dt', '', name), make('dd', '', value));
    }
    return node;
  }

  // What is asked of the check: exactly where the work would be kept, and nothing else.
  // A folder or a branch that nobody has chosen is not asked about: the check says what it found.
  function placeAsked(form) {
    const text = (value) => String(value).trim() || null;
    const chosen = (name) => (form.touched[name] || form.existing ? text(form[name]) : null);
    return { repository: form.where ? null : text(form.repository),
      path: form.where ? text(form.path) : null,
      folder: chosen('folder'), branch: chosen('branch') };
  }

  // A different place was named. What was found in the last one says nothing about this one.
  function forgetFound(form) {
    for (const name of ['folder', 'branch', 'name']) {
      if (!form.existing && form.touched[name]) continue;
      form[name] = '';
      form.touched[name] = false;
    }
    form.existing = false;
    form.check = null;
  }

  // A numbered step of a sheet that makes something: "2. What it is about", then its parts.
  function createStep(number, title, ...nodes) {
    return add(make('section', 'create-step'), make('h3', 'sheet-part', number + '. ' + title),
      ...nodes);
  }

  // A file as the runner takes it, in base64. The browser reads it, and puts a few words about
  // its kind in front, up to a comma, which are left off.
  function base64Of(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const read = String(reader.result);
        const at = read.indexOf(',');
        resolve(at < 0 ? '' : read.slice(at + 1));
      };
      reader.onerror = () => reject(new Error('This browser could not read it.'));
      reader.readAsDataURL(file);
    });
  }

  function slideName(slide) {
    return 'Slide ' + slide.number + (slide.title ? ': ' + slide.title : '');
  }

  // Slides by their numbers: "slide 3", "slides 3 to 5", or "slides 3, 5 and 8".
  function slidesNamed(numbers) {
    const held = list(numbers);
    if (held.length < 2) return held.length ? 'slide ' + held[0] : 'no slide';
    const row = held.length > 2 && held.every((number, index) => !index
      || number === held[index - 1] + 1);
    return 'slides ' + (row ? held[0] + ' to ' + held[held.length - 1]
      : series(held.map(String)));
  }

  // A note as the hint repeats it: the first line and a half, at most.
  function shortNote(text) {
    const flat = String(text || '').replace(/\s+/g, ' ').trim();
    return flat.length > 160 ? flat.slice(0, 159).trimEnd() + '…' : flat;
  }

  // What a stop kept: a sentence and, where it names things one a line, those as a list.
  function keptPart(text) {
    const lines = String(text || '').split('\n').map((line) => line.trim()).filter(Boolean);
    const items = lines.filter((line) => line.startsWith('- ')).map((line) => line.slice(2));
    const said = lines.filter((line) => !line.startsWith('- ')).join(' ');
    return add(make('div', 'kept'), add(make('p', ''), make('strong', '', 'What was kept: '), said),
      items.length ? bullets(items, 'plain kept-list') : null);
  }

  function nameOf(driver) {
    return String((driver && driver.name) || '').trim() || 'A teammate';
  }

  // What this computer knows of work a teammate runs: when it was last shared and where it
  // stood then. It never says what is happening now, because that is not known here.
  function lastLine(last, className) {
    if (!last) return null;
    const node = make('p', className);
    if (!Number.isNaN(Date.parse(last.at))) add(node, 'Last shared ', when(last.at), '. ');
    return add(node, (last.says ? String(last.says).trim() + ' ' : '')
      + 'It may have moved on since: this computer knows only what was shared.');
  }

  // A run that waits for its turn, and how many are ahead of it.
  function queued(run) {
    return Boolean(run && run.queue && given(run.queue.ahead));
  }

  function spentSays(spent) {
    // A cost of nothing is never said as $0.00.
    if (given(spent.dollars) && Number(spent.dollars) > 0) {
      return Number(spent.dollars) < 0.005 ? 'less than $0.01' : money(spent.dollars);
    }
    return given(spent.tokens) ? Number(spent.tokens).toLocaleString() + ' tokens'
      : 'Not reported yet';
  }

  function wantedCompanions(found) {
    return list(found && found.companions).filter((one) => ['missing', 'older']
      .includes(one.state));
  }

  function updating(found) {
    return Boolean(found && found.update && found.update.state === 'running');
  }

  function upgradeOf(found) {
    return (found && found.upgrade) || {};
  }

  // The brand skill's install: what it would install, from where, and how the last one went.
  function brandOf(found) {
    return (found && found.brand) || {};
  }

  function wantedRows(found) {
    return list(found && found.rows).filter((row) => ['update', 'missing'].includes(row.state));
  }

  function releasesLine(found) {
    const releases = (found && found.releases) || {};
    if (releases.on === false) {
      return make('p', 'quiet', 'Looking online for updates is turned off, in Settings.');
    }
    if (releases.problem) return make('p', 'fix', releases.problem);
    if (!releases.at || Number.isNaN(Date.parse(releases.at))) {
      return make('p', 'quiet', 'Updates have not been looked for yet.');
    }
    return add(make('p', 'quiet'), 'Updates were last looked for ', when(releases.at),
      list(releases.newer).length ? '.' : '. Nothing newer was found.');
  }

  function linkToken() {
    const found = /(?:^#|&)token=([A-Za-z0-9_-]+)/.exec(window.location.hash);
    return found ? found[1] : '';
  }

  function forgetLibraryLink() {
    try {
      const params = new URLSearchParams(String(window.location.hash || '').replace(/^#/, ''));
      if (!params.has('library')) return;
      params.delete('library');
      const kept = params.toString();
      window.history.replaceState(window.history.state, '', (window.location.pathname || '')
        + (window.location.search || '') + (kept ? '#' + kept : ''));
    } catch (failure) {
      // A browser that cannot change its address keeps it: the sheet opens once per load.
    }
  }

  function libraryFromLink(hash) {
    const given = new URLSearchParams(String(hash || '').replace(/^#/, '')).get('library') || '';
    const found = /^([a-z0-9][a-z0-9-]{0,63})@([1-9][0-9]{0,3})$/.exec(given);
    if (!found || Number(found[2]) > 1000) return null;
    return { id: found[1], revision: Number(found[2]) };
  }

  window.StudioDesk = Object.freeze({ byId, main, make, add, count, list, series, ago, when,
    megabytes, pathInto, button, capsule, submitButton, pageForm, card, bullets, callout,
    segmented, slide, alertLine, narrow, money, lasted, lower, capital, spoken, given, cell,
    saidBy, notify, copyBySelection, copy, ordered, pageHead, focusKey, placeAsking, sheetTitle,
    problemLine, askedFrom, alerts, about, placeAsked, forgetFound, createStep, base64Of,
    slideName, slidesNamed, shortNote, keptPart, nameOf, lastLine, queued, spentSays,
    wantedCompanions, updating, upgradeOf, brandOf, wantedRows, releasesLine, linkToken,
    forgetLibraryLink, libraryFromLink });
})();
