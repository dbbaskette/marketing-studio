// The Document Library's shared catalog and its Add from library sheet, for every studio
// page and Marketing Studio's Library screen. Plain DOM, no build step, no markup: every
// title and passage is set as text, never as HTML.
//
//   StudioLibrary.pick(adapter)    -> Promise: the sheet, resolved once Use selected worked
//   new StudioLibrary.Catalog(adapter).node   -> browsing only (Marketing Studio)
//
// adapter: {studio, post(route, body) -> Promise of the answer, use(picks) -> Promise,
//           roles: [[value, label]] (optional), max (optional), download(row, format)}
// `post` is sent 'library', 'library-document', 'library-filters' or 'library-matching'.
//
// Browsing chooses nothing: a remembered filter is only a filter, and a project's context
// changes only when Use selected succeeds. Cancel and Escape change nothing.
(function () {
  'use strict';

  const PAGE = 25;
  const make = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  };
  const add = (parent, ...children) => { for (const child of children) if (child) parent.append(child); return parent; };
  const button = (label, cls, run, key) => {
    const node = make('button', cls || 'button button-quiet', label);
    node.type = 'button';
    if (key) node.dataset.key = key;
    node.addEventListener('click', run);
    return node;
  };
  const message = (error) => (error && error.message) || String(error || 'The library could not be read.');
  const day = (stamp) => {
    const when = stamp ? new Date(stamp) : null;
    return when && !isNaN(when) ? when.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
  };
  const choice = (key, label, options, value, changed) => {
    const id = 'library-' + key;
    const title = make('label', 'field-label', label);
    title.htmlFor = id;
    const select = make('select', 'input');
    select.id = id;
    select.dataset.key = id;
    for (const [optionValue, text] of options) {
      const option = make('option', '', text);
      option.value = optionValue;
      select.append(option);
    }
    select.value = value || '';
    select.addEventListener('change', () => changed(key, select.value));
    return add(make('div', 'field'), title, select);
  };

  class Catalog {
    constructor(adapter, options = {}) {
      this.a = adapter;
      this.selectable = Boolean(options.selectable);
      this.ticked = new Map();          // id -> {id, revision, title, role}
      this.filters = { query: '', kind: '', studio: '', origin: '', state: '', author: '' };
      this.offset = 0;
      this.answer = null;
      this.problem = '';
      this.loading = false;
      this.first = true;
      this.preview = null;
      this.onChange = options.onChange || (() => {});
      this.node = make('section', 'library-catalog stack');
      this.node.setAttribute('aria-label', 'Document Library');
      this.load();
    }

    async load() {
      this.loading = true;
      this.render();
      try {
        const sent = { filters: this.sent(), offset: this.offset, limit: PAGE };
        const answer = await this.a.post('library', sent);
        if (this.first && answer.remembered && Object.keys(answer.remembered).length) {
          this.first = false;
          Object.assign(this.filters, answer.remembered);    // a filter, never a selection
          return this.load();
        }
        this.first = false;
        this.answer = answer;
        this.problem = '';
      } catch (error) {
        this.problem = message(error);
      } finally {
        this.loading = false;
        this.render();
        this.onChange();      // the selection bar counts what this page no longer shows
      }
    }

    sent() {
      const sent = {};
      for (const [key, value] of Object.entries(this.filters)) if (value) sent[key] = value;
      return sent;
    }

    changed(key, value) {
      this.filters[key] = value;
      this.offset = 0;
      const { query, author, ...kept } = this.filters;
      this.a.post('library-filters', { filters: kept }).catch(() => {});   // a convenience only
      this.load();
    }

    async show(row) {
      this.preview = { row, loading: true };
      this.render();
      try {
        this.preview = { row, found: await this.a.post('library-document', { id: row.id, revision: row.revision }) };
      } catch (error) {
        this.preview = { row, problem: message(error) };
      }
      this.render();
      const heading = this.node.querySelector('.library-preview h3');
      if (heading) heading.focus();
    }

    tick(row, on) {
      if (on) this.ticked.set(row.id, { id: row.id, revision: row.revision, title: row.title, role: (this.a.roles || [[null]])[0][0] });
      else this.ticked.delete(row.id);
      this.onChange();
      this.render();
    }

    async allMatching() {
      try {
        const found = await this.a.post('library-matching', { filters: this.sent() });
        const max = this.a.max || 40;
        if (this.ticked.size + found.matching.filter((one) => !this.ticked.has(one.id)).length > max) {
          throw new Error('That would be more than ' + max + ' documents. Narrow the filters first.');
        }
        const titles = new Map(((this.answer && this.answer.items) || []).map((row) => [row.id, row.title]));
        for (const one of found.matching) {
          if (!this.ticked.has(one.id)) this.ticked.set(one.id, { ...one, title: titles.get(one.id) || 'Library document', role: (this.a.roles || [[null]])[0][0] });
        }
        this.problem = '';
      } catch (error) {
        this.problem = message(error);
      }
      this.onChange();
      this.render();
    }

    filterRow() {
      const labels = this.answer || {};
      const options = (map, all) => [['', all], ...Object.entries(map || {})];
      const form = make('form', 'filter-bar');
      form.setAttribute('role', 'search');
      form.noValidate = true;
      const title = make('label', 'field-label', 'Search');
      title.htmlFor = 'library-query';
      const box = make('input', 'input');
      box.type = 'search';
      box.id = 'library-query';
      box.dataset.key = 'library-query';
      box.maxLength = 200;
      box.autocomplete = 'off';
      box.placeholder = 'Title or words in the document';
      box.value = this.filters.query;
      const go = make('button', 'button', 'Search');
      go.type = 'submit';
      add(form, add(make('div', 'field search'), title, box),
        choice('kind', 'Type', options(labels.kinds, 'All types'), this.filters.kind, (k, v) => this.changed(k, v)),
        choice('studio', 'From', options(labels.studios, 'All studios'), this.filters.studio, (k, v) => this.changed(k, v)),
        go);
      const more = make('details', 'more-filters');
      more.dataset.key = 'library-more';
      more.open = Boolean(this.filters.origin || this.filters.state || this.filters.author);
      const authorTitle = make('label', 'field-label', 'Author');
      authorTitle.htmlFor = 'library-author';
      const author = make('input', 'input');
      author.id = 'library-author';
      author.dataset.key = 'library-author';
      author.maxLength = 100;
      author.value = this.filters.author;
      add(more, make('summary', '', 'More filters'),
        choice('origin', 'Origin', options(labels.origins, 'Any origin'), this.filters.origin, (k, v) => this.changed(k, v)),
        choice('state', 'Status', options(labels.states, 'Any status'), this.filters.state, (k, v) => this.changed(k, v)),
        add(make('div', 'field'), authorTitle, author));
      form.append(more);
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        this.filters.query = box.value.trim();
        this.filters.author = author.value.trim();
        this.offset = 0;
        this.load();
      });
      return form;
    }

    row(row) {
      const item = make('li', 'library-row');
      item.dataset.key = 'library-row-' + row.id;
      const on = this.ticked.has(row.id);
      if (on) item.classList.add('is-selected');
      const meta = [row.kind_label, row.studio_label, row.updated_at ? 'Updated ' + day(row.updated_at) : '',
        (row.format_labels || []).join(', ')].filter(Boolean).join(' · ');
      const text = add(make('div', 'library-row-text'), make('span', 'row-title', row.title), make('span', 'quiet', meta));
      if (row.revision > 1) text.append(make('span', 'quiet', 'Revision ' + row.revision));
      if (!row.readable) text.append(add(make('span', 'problem'), make('span', 'tag', row.state_label), ' ' + (row.problem || '')));
      if (row.pdf === 'needs-export') text.append(make('span', 'quiet', 'PDF needs export. ' + (row.pdf_note || '')));
      if (this.selectable) {
        const tick = make('label', 'check library-tick');
        const box = make('input');
        box.type = 'checkbox';
        box.dataset.key = 'library-tick-' + row.id;
        box.checked = on;
        box.disabled = !row.readable;
        box.setAttribute('aria-label', (on ? 'Selected: ' : 'Select ') + row.title);
        box.addEventListener('change', () => this.tick(row, box.checked));
        add(item, add(tick, box, text));
      } else {
        item.append(text);
      }
      const actions = add(make('div', 'bar library-row-actions'),
        button('Preview', 'button button-quiet', () => this.show(row), 'library-preview-' + row.id));
      if (on && this.a.roles) {
        const held = this.ticked.get(row.id);
        const select = make('select', 'input');
        select.dataset.key = 'library-role-' + row.id;
        select.setAttribute('aria-label', 'What ' + row.title + ' is for');
        for (const [value, label] of this.a.roles) { const option = make('option', '', label); option.value = value; select.append(option); }
        select.value = held.role;
        select.addEventListener('change', () => { held.role = select.value; });
        actions.prepend(select);
      }
      if (!this.selectable && this.a.download) {
        for (const format of row.formats || []) {
          actions.append(button('Download ' + ({ markdown: 'Markdown', original: 'original', pdf: 'PDF' })[format], 'button button-quiet',
            () => this.a.download(row, format), 'library-download-' + format + '-' + row.id));
        }
      }
      return add(item, actions);
    }

    previewPart() {
      if (!this.preview) return null;
      const { row, found, problem, loading } = this.preview;
      const part = make('section', 'library-preview paper');
      const heading = make('h3', '', row.title);
      heading.tabIndex = -1;
      const head = add(make('div', 'panel-heading'), heading,
        button('Close preview', 'button button-quiet', () => { this.preview = null; this.render(); }, 'library-preview-close'));
      part.append(head);
      if (loading) part.append(make('p', 'quiet', 'Reading the document…'));
      if (problem) part.append(make('p', 'problem', problem));
      if (found) {
        if (!found.readable) part.append(make('p', 'problem', found.problem || 'It has no readable text.'));
        for (const gap of found.gaps || []) part.append(make('p', 'quiet', gap));
        if (found.text) part.append(make('pre', 'library-preview-text', found.text));
        if (found.truncated) part.append(make('p', 'quiet', 'Only the beginning is shown here: ' + found.characters.toLocaleString() + ' characters in all.'));
      }
      return part;
    }

    render() {
      const focused = document.activeElement && this.node.contains(document.activeElement) ? document.activeElement.dataset.key : null;
      const answer = this.answer;
      const parts = [this.filterRow()];
      if (this.problem) parts.push(add(make('div', 'notice problem'), make('span', '', this.problem), ' ',
        button('Try again', 'button button-quiet', () => this.load(), 'library-retry')));
      const items = (answer && answer.items) || [];
      const heading = make('div', 'panel-heading');
      const total = answer ? answer.total : 0;
      heading.append(make('h3', '', answer ? (total === 1 ? '1 document' : total + ' documents') : 'Documents'));
      if (this.selectable && items.length) {
        const shown = items.filter((row) => row.readable);
        const some = shown.filter((row) => this.ticked.has(row.id)).length;
        const tick = make('label', 'check select-page');
        const box = make('input');
        box.type = 'checkbox';
        box.dataset.key = 'library-select-page';
        box.checked = shown.length > 0 && some === shown.length;
        box.indeterminate = some > 0 && some < shown.length;
        box.disabled = !shown.length;
        box.addEventListener('change', () => { for (const row of shown) { if (box.checked) { if (!this.ticked.has(row.id)) this.tick(row, true); } else this.ticked.delete(row.id); } this.onChange(); this.render(); });
        heading.append(add(tick, box, make('span', '', 'Select all on this page')));
      }
      parts.push(heading);
      const list = make('ul', 'library-list');
      list.setAttribute('aria-busy', String(this.loading));
      if (this.loading && !answer) list.append(make('li', 'quiet', 'Loading the library…'));
      else if (answer && !answer.available) list.append(make('li', 'quiet', 'Nothing has been kept in the Document Library yet. Uploads, finished blogs and delivered decks appear here.'));
      else if (answer && !items.length) list.append(make('li', 'quiet', 'No documents match these filters.'));
      for (const row of items) list.append(this.row(row));
      parts.push(list);
      if (answer && total > PAGE) {
        const end = Math.min(total, this.offset + items.length);
        parts.push(add(make('div', 'bar library-pages'),
          button('Previous', 'button button-quiet', () => { this.offset = Math.max(0, this.offset - PAGE); this.load(); }, 'library-previous'),
          make('span', 'quiet', (this.offset + 1) + '–' + end + ' of ' + total),
          button('Next', 'button button-quiet', () => { this.offset += PAGE; this.load(); }, 'library-next')));
        parts[parts.length - 1].querySelector('[data-key="library-previous"]').disabled = this.offset === 0;
        parts[parts.length - 1].querySelector('[data-key="library-next"]').disabled = end >= total;
      }
      const preview = this.previewPart();
      if (preview) parts.splice(1, 0, preview);
      this.node.replaceChildren(...parts);
      if (focused) { const again = this.node.querySelector('[data-key="' + focused + '"]'); if (again) again.focus(); }
    }

    shownIds() { return ((this.answer && this.answer.items) || []).map((row) => row.id); }
  }

  // The Add from library sheet: the catalog with ticks, and the selection bar.
  function pick(adapter) {
    return new Promise((resolve) => {
      const opener = document.activeElement;
      const dialog = make('dialog', 'dialog library-sheet');
      dialog.setAttribute('aria-labelledby', 'library-sheet-title');
      const title = make('h2', '', adapter.title || 'Add from library');
      title.id = 'library-sheet-title';
      const bar = make('div', 'library-selection');
      let problem = '';
      let busy = false;
      const catalog = new Catalog(adapter, { selectable: true, onChange: () => draw() });
      const finish = (value) => { dialog.close(); dialog.remove(); if (opener && opener.focus) opener.focus(); resolve(value); };
      const use = async () => {
        if (busy || !catalog.ticked.size) return;
        busy = true; problem = ''; draw();
        try {
          const picks = [...catalog.ticked.values()].map(({ id, revision, role }) => (adapter.roles ? { id, revision, role } : { id, revision }));
          const done = await adapter.use(picks);
          busy = false;
          finish(done === undefined ? true : done);
          return;
        } catch (error) {
          problem = message(error);
        }
        busy = false;
        draw();
      };
      function draw() {
        const ticked = catalog.ticked;
        const shown = catalog.shownIds();
        const parts = [];
        if (ticked.size) {
          const out = [...ticked.keys()].filter((id) => !shown.includes(id)).length;
          const count = add(make('p', 'selection-count'), make('strong', '', ticked.size + ' selected'));
          count.setAttribute('role', 'status');
          if (out) count.append(' ', make('span', 'quiet', out === 1 ? '1 of them is not in this view.' : out + ' of them are not in this view.'));
          count.append(' ', make('span', 'quiet', 'Ticks stay when you change the filters or the page.'));
          parts.push(add(make('section', 'selection-bar glass'), count,
            add(make('div', 'bar selection-picks'),
              catalog.answer && catalog.answer.total ? button('Select all ' + catalog.answer.total + ' matching', 'button button-quiet', () => catalog.allMatching(), 'library-all-matching') : null,
              button('Clear', 'button button-quiet', () => { ticked.clear(); catalog.render(); draw(); }, 'library-clear'))));
        }
        if (problem) parts.push(make('p', 'problem', problem));
        const go = button(busy ? 'Adding…' : 'Use selected', 'button button-filled', use, 'library-use');
        go.disabled = busy || !ticked.size;
        parts.push(add(make('div', 'create-foot bar'), go, button('Cancel', 'button button-quiet', () => finish(false), 'library-cancel')));
        bar.replaceChildren(...parts);
      }
      add(dialog, add(make('header', 'dialog-header'), title,
        button('Close', 'button button-quiet', () => finish(false), 'library-close')),
      add(make('div', 'dialog-content'),
        make('p', 'quiet', 'Choose documents for this project only. Adding them starts nothing, sends nothing to an assistant and changes no research settings. A new project starts with none.'),
        catalog.node, bar));
      dialog.addEventListener('cancel', (event) => { event.preventDefault(); finish(false); });
      document.body.append(dialog);
      draw();
      dialog.showModal();
      const first = dialog.querySelector('#library-query');
      if (first) first.focus();
    });
  }

  window.StudioLibrary = { Catalog, pick };
}());
