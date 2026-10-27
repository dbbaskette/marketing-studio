// The list kit both deck studios' pages load, served by the shared page server beside the
// deck panels: one filter row, a tick, Select all on this page, and the selection bar shown
// while something is ticked. Plain DOM, no build step, and no markup: every word is text.
// The page keeps what is ticked and what is filtered; these only draw it and say what
// changed. ui-kit/style.css draws them (.filter-bar, .check, .selection-bar and the rest).
(function () {
  'use strict';

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function add(parent, ...children) {
    for (const child of children) if (child) parent.append(child);
    return parent;
  }

  function button(label, className, action, key) {
    const node = make('button', className, label);
    node.type = 'button';
    if (key) node.dataset.key = key;
    if (action) node.addEventListener('click', action);
    return node;
  }

  function number(count, noun) {
    return count + ' ' + (count === 1 ? noun[0] : noun[1]);
  }

  // One choice filter: its name above the browser's own list.
  function choiceField(key, choice, changed) {
    const id = key + '-' + choice.id;
    const title = make('label', 'field-label', choice.label);
    title.htmlFor = id;
    const select = make('select', 'input');
    select.id = id;
    select.dataset.key = id;
    for (const [value, text] of choice.options || []) {
      const option = make('option', '', text);
      option.value = value;
      select.append(option);
    }
    select.value = choice.value || '';
    select.addEventListener('change', () => { if (changed) changed(choice.id, select.value); });
    return add(make('div', 'field'), title, select);
  }

  // spec: {key, search: {id, label, hint, value}, choices: [{id, label, options: [[value,
  //        text]], value}], more: [the same], open, changed(name, value), searched(text),
  //        toggled()}
  // One row: the search first and widest, then a choice per filter, then Search. Rarely
  // used filters fold under More filters. A choice applies when it is changed; the search
  // when Search or Enter is pressed. On a phone only the search shows, with a Filters
  // button that opens the rest and counts those that are set.
  function filterRow(spec) {
    const key = spec.key || 'filters';
    const form = make('form', 'filter-bar' + (spec.open ? ' filters-open' : ''));
    form.dataset.key = key;
    form.noValidate = true;
    form.setAttribute('role', 'search');
    const search = spec.search || {};
    const searchId = key + '-' + (search.id || 'search');
    const title = make('label', 'field-label', search.label || 'Search');
    title.htmlFor = searchId;
    const box = make('input', 'input');
    box.type = 'search';
    box.id = searchId;
    box.dataset.key = searchId;
    box.value = search.value || '';
    box.maxLength = 200;
    box.autocomplete = 'off';
    if (search.hint) box.placeholder = search.hint;
    const choices = spec.choices || [];
    const more = spec.more || [];
    const set = [...choices, ...more].filter((choice) => choice.value).length;
    const toggle = button(set ? 'Filters (' + set + ')' : 'Filters', 'button filters-toggle',
      () => {
        const open = !form.classList.contains('filters-open');
        if (open) form.classList.add('filters-open');
        else form.classList.remove('filters-open');
        toggle.setAttribute('aria-expanded', String(open));
        if (spec.toggled) spec.toggled(open);
      }, key + '-toggle');
    toggle.setAttribute('aria-expanded', String(Boolean(spec.open)));
    const go = make('button', 'button', 'Search');
    go.type = 'submit';
    go.dataset.key = key + '-go';
    add(form, add(make('div', 'field search'), title, box), toggle,
      ...choices.map((choice) => choiceField(key, choice, spec.changed)), go);
    if (more.length) {
      const fold = make('details', 'more-filters');
      fold.dataset.key = key + '-more';
      fold.open = more.some((choice) => choice.value);
      add(fold, make('summary', '', 'More filters'),
        ...more.map((choice) => choiceField(key, choice, spec.changed)));
      form.append(fold);
    }
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (spec.searched) spec.searched(box.value.trim());
    });
    return form;
  }

  // spec: {id, label, on, flip(on)}
  // A tick with its label, as tall as any control.
  function tick(spec) {
    const node = make('label', 'check');
    const box = make('input');
    box.type = 'checkbox';
    if (spec.id) {
      box.id = spec.id;
      box.dataset.key = spec.id;
    }
    box.checked = Boolean(spec.on);
    box.addEventListener('change', () => { if (spec.flip) spec.flip(box.checked); });
    return add(node, box, make('span', '', spec.label));
  }

  // spec: {id, label, shown: [id], ticked: Set, flip(on)}
  // Select all on this page, on a list's heading: ticked when every item shown is, and
  // mixed when some are.
  function selectPage(spec) {
    const shown = spec.shown || [];
    const ticked = spec.ticked || new Set();
    const some = shown.filter((id) => ticked.has(id)).length;
    const node = tick({ id: spec.id, label: spec.label || 'Select all on this page',
      on: shown.length > 0 && some === shown.length, flip: spec.flip });
    node.classList.add('select-page');
    const box = node.querySelector('input');
    box.indeterminate = some > 0 && some < shown.length;
    box.disabled = !shown.length;
    return node;
  }

  // spec: {ticked: Set, shown: [id], noun: ['deck', 'decks'], actions: [{label, kind, run,
  //        key}], selectShown(), clear(), key}
  // The selection bar, only while something is ticked: how many, how many of them the
  // filters hide, Select all on this page while some shown are not ticked, Clear, then the
  // actions. Ticks stay through filter changes, and the bar says so.
  function selectionBar(spec) {
    const ticked = spec.ticked || new Set();
    if (!ticked.size) return null;
    const shown = spec.shown || [];
    const noun = spec.noun || ['item', 'items'];
    const key = spec.key || 'selection';
    const bar = make('section', 'selection-bar glass');
    bar.dataset.key = key;
    bar.setAttribute('aria-label', 'Selected ' + noun[1]);
    const out = [...ticked].filter((id) => !shown.includes(id)).length;
    const unticked = shown.filter((id) => !ticked.has(id)).length;
    const counted = add(make('p', 'selection-count'), make('strong', '', ticked.size + ' selected'));
    counted.setAttribute('role', 'status');
    if (out) {
      counted.append(' ', make('span', 'quiet', out === 1 ? '1 of them is not in this view.'
        : out + ' of them are not in this view.'));
    }
    const picks = add(make('div', 'bar selection-picks'),
      unticked ? button('Select all ' + shown.length + ' on this page', 'button button-quiet',
        () => { if (spec.selectShown) spec.selectShown(); }, key + '-shown') : null,
      button('Clear', 'button button-quiet', () => { if (spec.clear) spec.clear(); }, key + '-clear'));
    const actions = add(make('div', 'bar selection-actions'),
      ...(spec.actions || []).map((action) => button(action.label,
        'button' + (action.kind ? ' button-' + action.kind : ''), action.run, action.key)));
    return add(bar, counted, picks, actions);
  }

  window.StudioLists = { filterRow, tick, selectPage, selectionBar, number };
}());
