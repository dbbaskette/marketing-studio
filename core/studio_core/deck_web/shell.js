/* The shell kit every studio page shows, in plain JavaScript with no build step:

     StudioShell.connect({header, token, home})   the page's key, so a choice can be saved
     StudioShell.commands(() => [...])            the page's own work and actions, for the palette
     StudioShell.palette()                        open the command palette (also Cmd or Ctrl+K)
     StudioShell.track(stages, label, compact)    a project's stages as one drawn line
     StudioShell.arc(), .pulse(), .move()         a workbench's phases, its line of light, its one move
     StudioShell.parts({label, groups, chosen, choose})   the open project's parts, down the left
     StudioShell.appearance(), .setAppearance()   light, dark, or this computer's own
     StudioShell.continueLink({id, revision})     Continue in another studio, for a document
                                                  this studio kept in the Document Library

   Appearance is one shared setting, `appearance` in the studios config. The server writes
   it on <body data-appearance> as the page is served, so a page opens already looking as
   chosen. A choice made here is applied at once and saved through the page's shared
   settings route; where it cannot be saved it holds for this page and says so.

   A command is {title, hint, group, keywords, run}. Nothing here starts an assistant, and
   every command does only what a control already on the page does. A page's list is asked
   for each time the palette opens, so it holds what the page holds then: a studio names the
   work its own page lists (group Blogs, Decks, Trainings or Infographics, the state as the
   hint) and `run` opens it as that work's own card does. For example:

     StudioShell.commands(() => projects.map(project => ({ title: project.title,
       group: 'Infographics', hint: project.state, keywords: 'infographic work',
       run: () => openProject(project.id) })));  */
const StudioShell = (() => {
  const APPEARANCES = [['light', 'Light'], ['dark', 'Dark'], ['', 'Auto']];
  const providers = [];
  let link = null, chosen = document.body.dataset.appearance || '', opened = null;

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  // --- appearance -------------------------------------------------------------------

  // The stylesheet switches the tokens from <body data-appearance>: `light` and `dark` are a
  // choice, and no value follows this computer. Nothing here reads or rewrites a stylesheet.
  function paint() {
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

  // --- Continue in another studio ------------------------------------------------------

  // Marketing Studio opens a studio with `home=<its origin>&homeToken=<its key>` in the link's
  // fragment. The shell reads it as it loads and, when both are valid, keeps them in this
  // tab's memory at once (`marketing-studio-return`, {home, token}: what each studio's way
  // back keeps there too), so continueLink still works after the page clears its fragment or
  // is reloaded. For that, a studio page loads shell.js before any script that clears the
  // fragment (an earlier `<script defer>`, as every studio page does now), or it keeps
  // `marketing-studio-return` in sessionStorage itself before clearing it. A page that does
  // neither gets null.
  const here = () => (typeof location !== 'undefined' && location) || { hash: '', protocol: '', hostname: '', port: '' };
  const launchHash = String(here().hash || '').replace(/^#/, '');   // read once, parsed when asked
  const KEY = /^[A-Za-z0-9_-]{8,256}$/;
  // Marketing Studio's home: the same scheme and host as this page, on another port.
  function homeOrigin(named) {
    const found = /^(https?:)\/\/([^/:?#@\s]+):(\d{1,5})\/?$/.exec(String(named || ''));
    const page = here();
    return found && found[1] === page.protocol && found[2] === page.hostname
      && found[3] !== page.port && Number(found[3]) > 0 && Number(found[3]) < 65536
      ? found[1] + '//' + found[2] + ':' + found[3] : '';
  }
  (function remember() {
    try {
      const launched = new URLSearchParams(launchHash);
      const home = homeOrigin(launched.get('home')), key = launched.get('homeToken') || '';
      if (home && KEY.test(key)) sessionStorage.setItem('marketing-studio-return', JSON.stringify({ home, token: key }));
    } catch (_) { /* no tab memory here: the fragment read above still serves this page */ }
  })();
  // The home page's link that opens its Library on a document with Continue in another
  // studio showing: `<home>/#token=<home key>&continue=<id>@<revision>`. Null when this studio
  // runs alone (Marketing Studio did not open it), or the document is not named as the
  // Document Library names one: its id and a revision number. `document` is accepted for the
  // id too, as a studio's own record of what the library kept says it.
  function continueLink(doc) {
    const id = doc && (doc.id || doc.document), revision = doc && doc.revision;
    if (typeof id !== 'string' || !/^[a-z0-9][a-z0-9-]{0,63}$/.test(id)
        || !Number.isInteger(revision) || revision < 1 || revision > 1000) return null;
    const launched = new URLSearchParams(launchHash);
    let home = homeOrigin(launched.get('home')), key = home ? launched.get('homeToken') || '' : '';
    if (!home || !KEY.test(key)) {
      try {
        const saved = JSON.parse(sessionStorage.getItem('marketing-studio-return') || 'null');
        home = saved ? homeOrigin(saved.home) : '';
        key = home && saved.home === home ? saved.token || '' : '';
      } catch (_) { home = ''; key = ''; }
    }
    if (!home || !KEY.test(key)) return null;
    return home + '/#token=' + encodeURIComponent(key) + '&continue=' + id + '@' + revision;
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

  // Put away (Escape, a press outside it, Cmd or Ctrl+K again), a sheet gives the focus back
  // to what opened it. A chosen command takes the person on and places the focus itself, so
  // then nothing is given back; a sheet opened from another gives it to the first one's opener.
  function sheet(className, label) {
    const opener = opened ? opened.opener : document.activeElement;
    const dialog = make('dialog', 'dialog ' + className);
    dialog.opener = opener; dialog.ran = false;
    dialog.setAttribute('aria-label', label);
    dialog.addEventListener('close', () => {
      dialog.remove(); if (opened === dialog) opened = null;
      if (!dialog.ran && !opened && opener && opener !== document.body && opener.isConnected !== false
          && typeof opener.focus === 'function') opener.focus();
    });
    // A press on the dimmed page around it closes it, as Escape does.
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
    document.body.append(dialog);
    opened = dialog;
    return dialog;
  }

  const SHOWN = 40;
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
    // Past the first SHOWN results the palette says how many more there are, never cuts silently.
    const more = make('p', 'quiet shell-palette-none shell-palette-more'); more.setAttribute('role', 'status');
    let shown = [], at = 0;

    // The keyboard brings the chosen row into view; a pointer resting on a row only marks it,
    // so the list never moves under the pointer.
    const mark = scroll => {
      Array.from(list.children).forEach((row, index) => {
        row.setAttribute('aria-selected', String(index === at));
        if (index === at) {
          input.setAttribute('aria-activedescendant', row.id);
          if (scroll) row.scrollIntoView({ block: 'nearest' });
        }
      });
      if (!shown.length) input.removeAttribute('aria-activedescendant');
    };
    const run = command => { dialog.ran = true; dialog.close(); command.run(); };
    const draw = () => {
      const found = matching(all, input.value);
      shown = found.slice(0, SHOWN); at = 0;
      more.hidden = found.length <= SHOWN;
      more.textContent = more.hidden ? '' : 'Showing ' + SHOWN + ' of ' + found.length
        + '. Type more of a name to find the rest.';
      list.replaceChildren(...shown.map((command, index) => {
        const row = make('li', 'shell-palette-row'); row.id = 'shell-palette-' + index;
        row.setAttribute('role', 'option');
        row.append(make('span', 'shell-palette-group', command.group || ''),
          make('span', 'shell-palette-title', command.title),
          make('span', 'shell-palette-hint', command.hint || ''));
        row.addEventListener('click', () => run(command));
        row.addEventListener('mousemove', () => { if (at !== index) { at = index; mark(false); } });
        return row;
      }));
      none.hidden = shown.length > 0;
      mark(true);
    };
    input.addEventListener('input', draw);
    input.addEventListener('keydown', event => {
      const move = { ArrowDown: 1, ArrowUp: -1 }[event.key];
      if (move && shown.length) {
        event.preventDefault(); at = (at + move + shown.length) % shown.length; mark(true);
      } else if (event.key === 'Enter' && shown[at]) {
        event.preventDefault(); run(shown[at]);
      }
    });
    const foot = make('p', 'quiet shell-palette-foot', '↑ ↓ to choose · Return to go · Esc to close');
    dialog.append(input, list, more, none, foot);
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

  // Reading alone: on a workbench, its parts and its rail step aside for the work itself, at
  // every width. While it lasts one quiet button closes the content and brings them back, so
  // the way out is in view and in the keyboard's order, not only F and Escape.
  const reading = () => document.body.dataset.focus === 'reading';
  let exit = null;
  function toggleReading() {
    if (reading()) delete document.body.dataset.focus; else document.body.dataset.focus = 'reading';
    if (reading() && !exit) {
      exit = make('button', 'button glass reading-exit'); exit.type = 'button';
      exit.setAttribute('aria-keyshortcuts', 'F Escape');
      const key = make('kbd', '', 'F'); key.setAttribute('aria-hidden', 'true');
      exit.append(make('span', '', 'Show everything'), key);
      exit.addEventListener('click', toggleReading);
      (document.querySelector('.content') || document.body).append(exit);
    } else if (!reading() && exit) {
      const held = document.activeElement === exit;
      exit.remove(); exit = null;
      // Focus never falls to the page's start: it goes to the work the person was reading.
      const work = document.querySelector('#main, [data-zone="work"]');
      if (held && work) { if (!work.hasAttribute('tabindex')) work.setAttribute('tabindex', '-1'); work.focus({ preventScroll: true }); }
    }
    say(reading() ? 'Reading alone. Press F or Escape, or Show everything, to bring everything back.' : 'Everything is back.');
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
  // What each phase is, said under its name so the line reads as a route, not four words.
  const PHASE_SAYS = ['What it is for', 'Its outline and sources', 'Drafts, checks and review', 'Finish and share'];
  function arc({ at = 0, yours = false, finished = false, note = '' } = {}, label) {
    const line = track(PHASES.map((name, index) => ({ label: name,
      state: finished || index < at ? 'done' : index > at ? 'todo' : yours ? 'yours' : 'current',
      note: index === at && !finished ? note : '' })), label || 'Where this work is');
    line.classList.add('track-arc');
    // Each mark carries its number until it is done, and each phase says what it is. A note
    // means the assistant is at work in the phase in hand: the line onward from it moves.
    Array.from(line.children).forEach((item, index) => {
      const mark = item.querySelector('.track-mark');
      if (mark && item.dataset.state !== 'done') mark.textContent = String(index + 1);
      const says = make('span', 'track-says', PHASE_SAYS[index]); says.setAttribute('aria-hidden', 'true');
      const at_note = item.querySelector('.track-note');
      if (at_note) item.insertBefore(says, at_note); else item.insertBefore(says, item.querySelector('.offscreen'));
    });
    line.dataset.live = note && !yours && !finished ? 'true' : 'false';
    line.style.setProperty('--arc-reach', (finished ? 100 : Math.round((Math.min(at, 3) + 0.5) * 25)) + '%');
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
  // With `working` it says what the assistant is doing instead, and that nothing is asked.
  let lastMove = '';
  function move({ title, text = '', action = null, calm = false, working = false } = {}) {
    // The assistant's turn: what it is doing, in the studio's colour, with a moving mark.
    if (working) {
      const busy = make('section', 'move-card move-card-working');
      busy.dataset.zone = 'rail'; busy.dataset.key = 'workbench-move';
      busy.setAttribute('aria-label', 'Working');
      const mark = make('span', 'move-working-mark'); mark.setAttribute('aria-hidden', 'true');
      const label = make('p', 'move-label'); label.append(mark, 'Working');
      busy.append(label, make('h2', 'move-title', title || 'Working on it'));
      if (text) busy.append(make('p', 'quiet', text));
      lastMove = '';
      return busy;
    }
    const card = make('section', 'move-card' + (calm ? ' move-card-calm' : ''));
    card.dataset.zone = 'rail'; card.dataset.key = 'workbench-move';
    // A desk draws its move again whenever anything changes. It arrives only when it is a
    // different move, so one that is drawn again under the person stays still.
    const said = calm ? '' : (title || '') + '\n' + text;
    if (said && said !== lastMove) card.classList.add('move-card-new');
    lastMove = said;
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

  // --- the parts of a project ------------------------------------------------------------
  // One list of the open project's parts, down the left of a workbench from 72rem and one
  // control above the work narrower (docs/design/ui-kit.md, "The parts of a project"):
  //
  //   StudioShell.parts({label, groups, chosen, choose, key})
  //     label    the list's name for a screen reader: "Parts of this training"
  //     groups   [{title, parts: [{id, name, state, count, busy}]}], in order; a group with
  //              no parts is left out. `state` is one word of PART_STATES or nothing;
  //              `count` ("3 sources") is said where there is no state; `busy` (true for
  //              Writing unless said otherwise) is the one thing that moves
  //     chosen   the id of the part shown in the middle
  //     choose   choose(id), called whenever a part is chosen, the one shown too; the studio
  //              shows it, keeps it in its address and draws the list again
  //     key      what the list's controls are known by when it is drawn again (data-key);
  //              by default the label
  //
  // It returns a <nav data-zone="parts">, placed as a part of the page like any other. The
  // studio draws nothing of its own for it.
  const PART_STATES = { Writing: 'working', Queued: 'queued', 'Needs you': 'yours', Draft: 'draft',
    Ready: 'done', 'Out of date': 'stale', 'Left out': 'out' };
  // Lists open on a narrow screen, by key, so drawing one again never closes it.
  const openParts = new Set();
  const shown = node => !node || typeof node.getClientRects !== 'function' || node.getClientRects().length > 0;
  const slug = text => String(text || 'parts').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'parts';

  // A part's name, then its state in words: a screen reader hears "Guide, Draft".
  function partWords(node, part) {
    node.append(make('span', 'parts-name', part.name));
    const state = Object.hasOwn(PART_STATES, part.state) ? part.state : '';
    const said = state || (part.count === undefined || part.count === null ? '' : String(part.count));
    if (said) {
      const words = make('span', 'parts-state', said);
      words.dataset.state = state ? PART_STATES[state] : 'count';
      node.append(make('span', 'offscreen', ', '), words);
    }
    return node;
  }

  function parts({ label = 'Parts', groups = [], chosen = null, choose = () => {}, key = '' } = {}) {
    const named = key || label;
    const nav = make('nav', 'parts');
    nav.setAttribute('aria-label', label);
    nav.dataset.zone = 'parts'; nav.dataset.key = named;
    const listId = 'parts-' + slug(named);
    const filled = (groups || []).map(group => ({ title: group && group.title,
      parts: ((group && group.parts) || []).filter(part => part && part.id !== undefined && part.name) }))
      .filter(group => group.parts.length);
    const all = filled.flatMap(group => group.parts);
    const current = all.find(part => part.id === chosen) || null;

    // Narrower than 72rem: one control naming the part shown and its state, opening the list.
    const toggle = make('button', 'parts-toggle'); toggle.type = 'button';
    toggle.dataset.key = named + ' toggle';
    toggle.setAttribute('aria-controls', listId);
    toggle.append(make('span', 'parts-toggle-label', current ? 'Showing' : 'Parts'));
    if (current) partWords(toggle, current);
    const mark = make('span', 'parts-toggle-mark'); mark.setAttribute('aria-hidden', 'true');
    toggle.append(mark);
    const list = make('div', 'parts-list'); list.id = listId;
    const open = value => {
      toggle.setAttribute('aria-expanded', String(value));
      if (value) openParts.add(named); else openParts.delete(named);
    };
    open(openParts.has(named));
    toggle.addEventListener('click', () => {
      const opening = toggle.getAttribute('aria-expanded') !== 'true';
      open(opening);
      if (opening) {
        const at = list.querySelector('[aria-current="true"]') || list.querySelector('.parts-item');
        if (at) at.focus();
      }
    });

    const items = [];
    filled.forEach((group, index) => {
      const box = make('div', 'parts-group');
      const heading = make('h2', 'parts-group-title', group.title || label);
      heading.id = listId + '-' + index;
      const rows = make('ul', 'parts-items'); rows.setAttribute('aria-labelledby', heading.id);
      for (const part of group.parts) {
        const item = make('button', 'parts-item'); item.type = 'button';
        item.dataset.part = String(part.id); item.dataset.key = named + ' ' + part.id;
        partWords(item, part);
        const busy = part.busy === undefined ? part.state === 'Writing' : Boolean(part.busy);
        if (busy) item.dataset.making = 'true';   // work under way is the one thing that moves
        if (part === current) item.setAttribute('aria-current', 'true');
        // Tab enters the list at the part shown; the arrow keys move from there.
        item.tabIndex = part === current || (!current && !items.length) ? 0 : -1;
        item.addEventListener('click', () => {
          const fromToggle = toggle.getAttribute('aria-expanded') === 'true';
          open(false);
          choose(part.id);
          // Unless choosing took the focus somewhere of its own, it stays on the part chosen,
          // or on the control above the work where the list was opened from there.
          const at = document.activeElement;
          if (at && at !== document.body && at.isConnected !== false && !(at.closest && at.closest('.parts'))) return;
          const again = Array.from(document.querySelectorAll('.parts-item, .parts-toggle'))
            .filter(node => node.isConnected !== false && node.closest && node.closest('.parts'));
          const toggled = again.find(node => node.dataset.key === named + ' toggle');
          const target = fromToggle && toggled && shown(toggled) ? toggled
            : again.find(node => node.dataset.key === named + ' ' + part.id);
          if (target) target.focus();
        });
        items.push(item);
        rows.append(add(make('li'), item));
      }
      box.append(heading, rows);
      list.append(box);
    });
    list.addEventListener('keydown', event => {
      const at = items.indexOf(event.target);
      if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
        event.preventDefault(); open(false); toggle.focus(); return;
      }
      if (at < 0) return;
      const to = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: items.length - 1 }[event.key];
      if (to === undefined) return;
      event.preventDefault();
      items[Math.max(0, Math.min(items.length - 1, to))].focus();
    });
    nav.append(toggle, list);
    return nav;
  }

  function add(node, ...children) {
    for (const child of children) if (child) node.append(child);
    return node;
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
    // On a phone the sidebar is the bar of screens along the bottom, with no room for these.
    // There they close every page instead, under its content.
    const content = document.querySelector('.content');
    if (content) {
      const under = make('div', 'shell-foot shell-foot-page');
      const find = make('button', 'shell-search', 'Search and jump'); find.type = 'button';
      find.addEventListener('click', palette);
      const said = make('p', 'quiet shell-note'); said.setAttribute('aria-hidden', 'true');
      under.append(find, appearanceSwitch(), said);
      content.append(under);
    }
  }

  paint();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();

  return {
    connect(found) {
      if (found && found.header && found.token) link = { header: found.header, token: found.token, home: found.home || '/onboarding/api/' };
    },
    commands(provide) { if (typeof provide === 'function') providers.push(provide); },
    appearance: () => chosen,
    setAppearance, appearanceSwitch, palette, shortcuts, track, arc, pulse, move, continueLink,
    parts, PART_STATES: Object.freeze({ ...PART_STATES }),
  };
})();
