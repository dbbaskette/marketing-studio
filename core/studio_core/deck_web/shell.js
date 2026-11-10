/* The shell kit every studio page shows, in plain JavaScript with no build step:

     StudioShell.connect({header, token, home})   the page's key, so a choice can be saved
     StudioShell.commands(() => [...])            more commands for the palette
     StudioShell.palette()                        open the command palette (also Cmd or Ctrl+K)
     StudioShell.track(stages, label, compact)    a project's stages as one drawn line
     StudioShell.arc(), .pulse(), .move()         a workbench's phases, its line of light, its one move
     StudioShell.finish({title, lines, action})   the card shown once when work is finished
     StudioShell.appearance(), .setAppearance()   light, dark, or this computer's own

   Appearance is one shared setting, `appearance` in the studios config. The server writes
   it on <body data-appearance> as the page is served, so a page opens already looking as
   chosen. A choice made here is applied at once and saved through the page's shared
   settings route; where it cannot be saved it holds for this page and says so.

   A command is {title, hint, group, keywords, run}. Nothing here starts an assistant, and
   every command does only what a control already on the page does. */
const StudioShell = (() => {
  const APPEARANCES = [['light', 'Light'], ['dark', 'Dark'], ['', 'Auto']];
  const SCHEME = /\(\s*prefers-color-scheme\s*:\s*(dark|light)\s*\)/g;
  const providers = [];
  const original = new WeakMap();   // each colour-scheme media rule's own condition
  let link = null, chosen = document.body.dataset.appearance || '', opened = null;

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  // --- appearance -------------------------------------------------------------------

  // Every rule written for one colour scheme, wherever it is: the kit's and each page's.
  function schemeRules(rules, found) {
    for (const rule of Array.from(rules || [])) {
      if (rule.media && /prefers-color-scheme/.test(original.get(rule) || rule.media.mediaText)) found.push(rule);
      if (rule.cssRules && !(rule.media && found.includes(rule))) schemeRules(rule.cssRules, found);
    }
    return found;
  }

  // A forced appearance answers each colour-scheme condition itself: `all` where it matches
  // the one chosen, `not all` where it does not. Auto puts every condition back.
  function paint() {
    for (const sheet of Array.from(document.styleSheets)) {
      let rules;
      try { rules = sheet.cssRules; } catch (_) { continue; }   // not this page's own
      for (const rule of schemeRules(rules, [])) {
        if (!original.has(rule)) original.set(rule, rule.media.mediaText);
        const own = original.get(rule);
        rule.media.mediaText = chosen
          ? own.replace(SCHEME, (_, scheme) => scheme === chosen ? 'all' : 'not all') : own;
      }
    }
    document.documentElement.style.colorScheme = chosen || 'light dark';
    if (chosen) document.body.dataset.appearance = chosen;
    else delete document.body.dataset.appearance;
    for (const button of document.querySelectorAll('[data-appearance-choice]')) {
      button.setAttribute('aria-pressed', String(button.dataset.appearanceChoice === chosen));
    }
    for (const group of document.querySelectorAll('.appearance-switch')) {
      group.dataset.at = String(APPEARANCES.findIndex(([value]) => value === chosen));
    }
  }

  async function ask(path, body) {
    const reply = await fetch(link.home + path, {
      method: body ? 'POST' : 'GET', cache: 'no-store',
      headers: { [link.header]: typeof link.token === 'function' ? link.token() : link.token, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined });
    const answer = await reply.json().catch(() => ({}));
    if (!reply.ok) throw Error(answer.error || 'The appearance could not be saved.');
    return answer;
  }

  // Saved against what the file holds now, so nothing else in it is touched.
  async function setAppearance(value) {
    chosen = value === 'light' || value === 'dark' ? value : '';
    paint();
    if (!link) return say('Set for this page. Shared settings keeps it for every studio.');
    try {
      const seen = (await ask('home')).shared || {};
      if ((seen.appearance || '') !== chosen) {
        await ask('shared', { changes: { appearance: chosen || null }, seen });
      }
      say(chosen ? 'Every studio now opens in the ' + chosen + ' appearance.'
        : 'Every studio now follows this computer’s appearance.');
    } catch (failure) {
      say('Set for this page only. ' + failure.message);
    }
  }

  function appearanceSwitch() {
    const group = make('div', 'segmented appearance-switch');
    group.setAttribute('role', 'group'); group.setAttribute('aria-label', 'Appearance');
    group.dataset.count = String(APPEARANCES.length);
    group.dataset.at = String(APPEARANCES.findIndex(([value]) => value === chosen));
    group.append(make('span', 'seg-thumb'));
    for (const [value, label] of APPEARANCES) {
      const button = make('button', 'seg-option', label); button.type = 'button';
      button.dataset.appearanceChoice = value;
      button.setAttribute('aria-pressed', String(value === chosen));
      button.addEventListener('click', () => setAppearance(value));
      group.append(button);
    }
    return group;
  }

  let status = null;
  function say(text) {
    if (!status) {
      status = make('p', 'offscreen'); status.setAttribute('role', 'status');
      document.body.append(status);
    }
    status.textContent = text;
    for (const note of document.querySelectorAll('.shell-note')) note.textContent = text;
  }

  // --- the command palette ------------------------------------------------------------

  const visible = node => Boolean(node && node.getClientRects().length && !node.disabled);
  // A control's own name: its label, or its text without a count or a note for a screen reader.
  const words = node => {
    if (node.getAttribute('aria-label')) return node.getAttribute('aria-label').trim();
    const copy = node.cloneNode(true);
    for (const extra of copy.querySelectorAll('.offscreen, .badge, .count, [aria-hidden="true"]')) extra.remove();
    return (copy.textContent || '').replace(/\s+/g, ' ').trim();
  };

  // What the page already offers: its screens, its toolbar's actions and the way back.
  function pageCommands() {
    const found = [];
    for (const node of document.querySelectorAll('.sidebar button, .sidebar a[href]')) {
      if (!visible(node) || node.closest('.shell-foot') || !words(node)) continue;
      found.push({ title: words(node), group: node.classList.contains('suite-link') ? 'Back' : 'Go to',
        hint: node.getAttribute('aria-current') === 'page' ? 'You are here' : '', run: () => node.click() });
    }
    for (const node of document.querySelectorAll('.toolbar button')) {
      if (!visible(node) || !words(node) || node.closest('.shell-foot')) continue;
      found.push({ title: words(node), group: 'On this screen', run: () => node.click() });
    }
    return found;
  }

  function shellCommands() {
    return [...APPEARANCES.map(([value, label]) => ({
      title: value ? label + ' appearance' : 'Match this computer’s appearance', group: 'Appearance',
      hint: value === chosen ? 'In use' : '', keywords: 'theme mode colour color dark light',
      run: () => setAppearance(value) })),
    ...(document.querySelector('[data-zone="work"]') ? [{
      title: reading() ? 'Show the parts and the assistant again' : 'Read without distractions',
      group: 'View', keywords: 'focus reading mode zen', hint: 'F', run: toggleReading }] : []),
    { title: 'Keyboard shortcuts', group: 'Help', keywords: 'keys help', run: shortcuts }];
  }

  function gathered() {
    const seen = new Set(), all = [];
    for (const provide of [...providers, pageCommands, shellCommands]) {
      let listed = [];
      try { listed = provide() || []; } catch (_) { listed = []; }   // one page's list never hides the rest
      for (const command of listed) {
        if (!command || !command.title || typeof command.run !== 'function') continue;
        const key = (command.group || '') + '\n' + command.title;
        if (seen.has(key)) continue;
        seen.add(key); all.push(command);
      }
    }
    return all;
  }

  // Every word typed must be found; a title that starts with what was typed comes first.
  function matching(all, typed) {
    const terms = typed.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) return all;
    return all.map((command, order) => {
      const title = command.title.toLowerCase();
      const hay = title + ' ' + (command.group || '').toLowerCase() + ' ' + (command.keywords || '').toLowerCase()
        + ' ' + (command.hint || '').toLowerCase();
      if (!terms.every(term => hay.includes(term))) return null;
      const rank = title.startsWith(terms[0]) ? 0 : title.includes(terms[0]) ? 1 : 2;
      return { command, rank, order };
    }).filter(Boolean).sort((a, b) => a.rank - b.rank || a.order - b.order).map(found => found.command);
  }

  function sheet(className, label) {
    const dialog = make('dialog', 'dialog ' + className);
    dialog.setAttribute('aria-label', label);
    dialog.addEventListener('close', () => { dialog.remove(); if (opened === dialog) opened = null; });
    // A press on the dimmed page around it closes it, as Escape does.
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
    document.body.append(dialog);
    opened = dialog;
    return dialog;
  }

  function palette() {
    if (opened) return;
    const all = gathered();
    const dialog = sheet('shell-palette', 'Search and jump');
    const input = make('input', 'shell-palette-input'); input.type = 'text';
    input.placeholder = 'Search screens, work and actions';
    input.setAttribute('role', 'combobox'); input.setAttribute('aria-expanded', 'true');
    input.setAttribute('aria-controls', 'shell-palette-list'); input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-label', 'Search screens, work and actions');
    input.autocomplete = 'off'; input.spellcheck = false;
    const list = make('ul', 'shell-palette-list'); list.id = 'shell-palette-list';
    list.setAttribute('role', 'listbox');
    const none = make('p', 'quiet shell-palette-none', 'Nothing matches. Try a screen or project name.');
    let shown = [], at = 0;

    const mark = () => {
      Array.from(list.children).forEach((row, index) => {
        row.setAttribute('aria-selected', String(index === at));
        if (index === at) { input.setAttribute('aria-activedescendant', row.id); row.scrollIntoView({ block: 'nearest' }); }
      });
      if (!shown.length) input.removeAttribute('aria-activedescendant');
    };
    const run = command => { dialog.close(); command.run(); };
    const draw = () => {
      shown = matching(all, input.value).slice(0, 40); at = 0;
      list.replaceChildren(...shown.map((command, index) => {
        const row = make('li', 'shell-palette-row'); row.id = 'shell-palette-' + index;
        row.setAttribute('role', 'option');
        row.append(make('span', 'shell-palette-group', command.group || ''),
          make('span', 'shell-palette-title', command.title),
          make('span', 'shell-palette-hint', command.hint || ''));
        row.addEventListener('click', () => run(command));
        row.addEventListener('mousemove', () => { if (at !== index) { at = index; mark(); } });
        return row;
      }));
      none.hidden = shown.length > 0;
      mark();
    };
    input.addEventListener('input', draw);
    input.addEventListener('keydown', event => {
      const move = { ArrowDown: 1, ArrowUp: -1 }[event.key];
      if (move && shown.length) {
        event.preventDefault(); at = (at + move + shown.length) % shown.length; mark();
      } else if (event.key === 'Enter' && shown[at]) {
        event.preventDefault(); run(shown[at]);
      }
    });
    const foot = make('p', 'quiet shell-palette-foot', '↑ ↓ to choose · Return to go · Esc to close');
    dialog.append(input, list, none, foot);
    draw();
    dialog.showModal();
    input.focus();
  }

  const MOD = /Mac|iPhone|iPad/.test(navigator.platform || '') ? '⌘' : 'Ctrl';
  function shortcuts() {
    if (opened) opened.close();
    const dialog = sheet('shell-shortcuts', 'Keyboard shortcuts');
    const rows = [[MOD + ' K', 'Search screens, work and actions'], ['?', 'Show these shortcuts'], ['F', 'Read without distractions, on a desk'],
      ['Esc', 'Close a sheet or this list'], ['↑ ↓ then Return', 'Choose in a list']];
    const table = make('dl', 'shell-keys');
    for (const [keys, does] of rows) table.append(make('dt', '', keys), make('dd', '', does));
    const close = make('button', 'button button-quiet', 'Close'); close.type = 'button';
    close.addEventListener('click', () => dialog.close());
    dialog.append(make('h2', 'card-title', 'Keyboard shortcuts'), table, close);
    dialog.showModal();
    close.focus();
  }

  // Reading alone: on a workbench, its parts and its rail step aside for the work itself.
  const reading = () => document.body.dataset.focus === 'reading';
  function toggleReading() {
    if (reading()) delete document.body.dataset.focus; else document.body.dataset.focus = 'reading';
    say(reading() ? 'Reading alone. Press F or Escape to bring everything back.' : 'Everything is back.');
  }

  const typing = node => Boolean(node && (node.isContentEditable
    || /^(INPUT|TEXTAREA|SELECT)$/.test(node.tagName)));
  document.addEventListener('keydown', event => {
    if ((event.metaKey || event.ctrlKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (opened && opened.classList.contains('shell-palette')) opened.close(); else palette();
    } else if ((event.key === 'f' || event.key === 'F' || (event.key === 'Escape' && reading()))
        && !event.metaKey && !event.ctrlKey && !event.altKey && !typing(event.target)
        && document.querySelector('[data-zone="work"]')
        && !document.querySelector('dialog[open], .sheet:not([hidden])')) {
      if (event.key !== 'Escape') event.preventDefault();
      toggleReading();
    } else if (event.key === '?' && !event.metaKey && !event.ctrlKey && !typing(event.target)
        && !document.querySelector('dialog[open], .sheet:not([hidden])')) {
      event.preventDefault(); shortcuts();
    }
  });

  // --- the progress track --------------------------------------------------------------

  // stages: [{label, state, note}], state one of done, current, yours, todo, skipped.
  // `yours` is the stage waiting on the person; `note` is said beside its label.
  const STATES = { done: 'done', current: 'in progress', yours: 'needs you', todo: 'not started', skipped: 'left out' };
  function track(stages, label, compact) {
    const line = make('ol', 'track' + (compact ? ' track-compact' : ''));
    line.setAttribute('aria-label', label || 'Progress');
    for (const stage of stages || []) {
      const state = Object.hasOwn(STATES, stage.state) ? stage.state : 'todo';
      const item = make('li', 'track-stage'); item.dataset.state = state;
      if (state === 'current' || state === 'yours') item.setAttribute('aria-current', 'step');
      const dot = make('span', 'track-mark', state === 'done' ? '✓' : ''); dot.setAttribute('aria-hidden', 'true');
      item.append(dot, make('span', 'track-label', stage.label),
        stage.note ? make('span', 'track-note', stage.note) : '',
        make('span', 'offscreen', ': ' + STATES[state]));
      line.append(item);
    }
    return line;
  }

  // --- the workbench ----------------------------------------------------------------------
  // A desk whose parts name their zone (`data-zone`: top, parts, work-top, work, rail) is
  // laid out by the shared stylesheet as a workbench. These are the three things every
  // workbench says the same way.

  // The one arc every studio shares. `at` is the phase in hand, 0 to 3; `yours` marks it as
  // waiting for the person, `finished` fills all four, `note` is said under the phase in hand.
  const PHASES = ['Brief', 'Plan', 'Make', 'Ship'];
  function arc({ at = 0, yours = false, finished = false, note = '' } = {}, label) {
    const line = track(PHASES.map((name, index) => ({ label: name,
      state: finished || index < at ? 'done' : index > at ? 'todo' : yours ? 'yours' : 'current',
      note: index === at && !finished ? note : '' })), label || 'Where this work is');
    line.classList.add('track-arc');
    line.dataset.zone = 'rail'; line.dataset.key = 'workbench-arc';
    return line;
  }

  // A line of light across the top of a desk: `working`, `yours` or `still`.
  function pulse(state) {
    const node = make('div', 'workbench-pulse');
    node.setAttribute('aria-hidden', 'true');
    node.dataset.state = ['working', 'yours'].includes(state) ? state : 'still';
    node.dataset.zone = 'top';
    return node;
  }

  // The one thing waiting for the person: {title, text, action: {label, run}}. With `calm`
  // it says that nothing is, in the same place, so the rail never leaves that in doubt.
  function move({ title, text = '', action = null, calm = false } = {}) {
    const card = make('section', 'move-card' + (calm ? ' move-card-calm' : ''));
    card.dataset.zone = 'rail'; card.dataset.key = 'workbench-move';
    if (!calm) { card.setAttribute('aria-label', 'Your move'); card.append(make('p', 'move-label', 'Your move')); }
    card.append(make('h2', 'move-title', title || (calm ? 'Nothing is yours right now' : 'Your move')));
    if (text) card.append(make('p', calm ? 'quiet' : '', text));
    if (!calm && action && action.label && typeof action.run === 'function') {
      const go = make('button', 'button', action.label); go.type = 'button';
      go.addEventListener('click', action.run);
      const bar = make('div', 'bar'); bar.append(go); card.append(bar);
    }
    return card;
  }

  // --- the finish card -------------------------------------------------------------------

  // Shown once when work is marked ready, delivered or published: what was made, where it
  // went, and one thing to do next. It leaves on Dismiss, on its action, or after a while.
  function finish({ title, lines = [], action = null, seconds = 14 } = {}) {
    document.querySelector('.finish-card')?.remove();
    const card = make('section', 'finish-card glass'); card.setAttribute('role', 'status');
    const seal = make('span', 'finish-seal', '✓'); seal.setAttribute('aria-hidden', 'true');
    const text = make('div', 'finish-text');
    text.append(make('h2', 'finish-title', title || 'Finished'), ...lines.filter(Boolean).map(line => make('p', 'quiet', line)));
    const bar = make('div', 'bar');
    const leave = () => card.remove();
    if (action && action.label && typeof action.run === 'function') {
      const go = make('button', 'button button-filled', action.label); go.type = 'button';
      go.addEventListener('click', () => { leave(); action.run(); }); bar.append(go);
    }
    const dismiss = make('button', 'button button-quiet', 'Dismiss'); dismiss.type = 'button';
    dismiss.addEventListener('click', leave); bar.append(dismiss);
    card.append(seal, text, bar);
    document.body.append(card);
    let timer = setTimeout(leave, seconds * 1000);
    for (const name of ['pointerenter', 'focusin']) card.addEventListener(name, () => clearTimeout(timer));
    return card;
  }

  // --- in the sidebar --------------------------------------------------------------------

  function mount() {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar || sidebar.querySelector('.shell-foot')) return;
    const foot = make('div', 'shell-foot');
    const search = make('button', 'shell-search'); search.type = 'button';
    search.append(make('span', '', 'Search and jump'), make('kbd', '', MOD + ' K'));
    search.addEventListener('click', palette);
    const note = make('p', 'quiet shell-note'); note.setAttribute('aria-hidden', 'true');
    foot.append(search, appearanceSwitch(), note);
    sidebar.append(foot);
  }

  paint();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
  // A page stylesheet that loads late is painted too.
  window.addEventListener('load', paint);

  return {
    connect(found) {
      if (found && found.header && found.token) link = { header: found.header, token: found.token, home: found.home || '/onboarding/api/' };
    },
    commands(provide) { if (typeof provide === 'function') providers.push(provide); },
    appearance: () => chosen,
    setAppearance, appearanceSwitch, palette, shortcuts, track, finish, arc, pulse, move,
  };
})();
