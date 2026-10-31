// The Document Library's shared catalog and its Add from library sheet, for every studio
// page and Marketing Studio's Library screen. Plain DOM, no build step, no markup: every
// title and passage is set as text, never as HTML.
//
//   StudioLibrary.pick(adapter)    -> Promise: the sheet, resolved once Use selected worked
//   new StudioLibrary.Catalog(adapter).node   -> browsing only (Marketing Studio)
//
// adapter: {studio, post(route, body) -> Promise of the answer, use(picks) -> Promise,
//           roles: [[value, label]] (optional), max (optional), download(row, format),
//           manage (optional: Remove from library, Show hidden and Restore), said(text),
//           noun (optional: what the studio calls one piece of work, default 'project'),
//           unavailable(row) (optional: {label, detail} for a row that cannot be chosen,
//           such as a studio's own kept export, else null; the server must refuse it too)}
// `post` is sent 'library', 'library-document', 'library-filters' or 'library-matching',
// and with `manage` also 'library-hide' ({id, hidden}).
//
// Browsing chooses nothing: a remembered filter is only a filter, and a project's context
// changes only when Use selected succeeds. Cancel and Escape change nothing.
//
// Each row has one action, Preview, which opens the document's preview just below its row;
// the downloads (and, with `manage`, Remove from library or Restore) are in the preview, and
// Close preview returns to the row's Preview. On a phone only the search shows, with a
// Filters button that opens the rest and counts those set.
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
  const FORMATS = { markdown: 'Markdown', original: 'original', pdf: 'PDF' };
  const SET = ['kind', 'studio', 'origin', 'state', 'author'];   // what Filters counts
  // Focus a control and bring it into view without jumping further than needed.
  const land = (node) => {
    if (!node) return;
    node.focus();
    if (node.scrollIntoView) node.scrollIntoView({ block: 'nearest' });
  };
  const day = (stamp) => {
    const when = stamp ? new Date(stamp) : null;
    return when && !isNaN(when) ? when.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : '';
  };
  // Element IDs are this catalog's own (`doclib<n>-…`): a page may already use library-*
  // IDs for something else, as Blog Studio's team library filters do. Keys stay stable.
  let instances = 0;
  const choice = (ns, key, label, options, value, changed) => {
    const id = ns + key;
    const title = make('label', 'field-label', label);
    title.htmlFor = id;
    const select = make('select', 'input');
    select.id = id;
    select.dataset.key = 'library-' + key;
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
      this.turn = 0;                    // only the newest load's answer is drawn
      this.ns = 'doclib' + (++instances) + '-';
      this.typed = { query: '', author: '' };   // typed, not yet searched: kept across redraws
      this.preview = null;              // {row, found | problem | loading, confirming, failed}
      this.manage = Boolean(adapter.manage) && !this.selectable;
      this.unavailable = (row) => (this.selectable && adapter.unavailable && adapter.unavailable(row)) || null;
      this.showHidden = false;          // Marketing Studio's Show hidden
      this.filtersOpen = false;         // a phone's Filters
      this.moreOpen = null;             // More filters, once the person opened or closed it
      this.focusAfter = null;           // a control's key to land on once a load is drawn
      this.onChange = options.onChange || (() => {});
      this.node = make('section', 'library-catalog stack');
      this.node.setAttribute('aria-label', 'Document Library');
      this.load();
    }

    async load() {
      const turn = ++this.turn;
      this.loading = true;
      this.render();
      try {
        const sent = { filters: this.sent(), offset: this.offset, limit: PAGE };
        if (this.showHidden) sent.hidden = true;
        const answer = await this.a.post('library', sent);
        if (turn !== this.turn) return;           // a newer load answers instead
        if (this.first && answer.remembered && Object.keys(answer.remembered).length) {
          this.first = false;
          Object.assign(this.filters, answer.remembered);    // a filter, never a selection
          return this.load();
        }
        this.first = false;
        this.answer = answer;
        this.problem = '';
        // A preview stays open while its document is still on this page, with its new row.
        if (this.preview) {
          const again = (answer.items || []).find((row) => row.id === this.preview.row.id);
          if (again) this.preview.row = again;
          else this.preview = null;
        }
      } catch (error) {
        if (turn === this.turn) this.problem = message(error);
      } finally {
        if (turn === this.turn) {
          this.loading = false;
          this.render();
          this.onChange();      // the selection bar counts what this page no longer shows
          if (this.focusAfter) {
            const key = this.focusAfter;
            this.focusAfter = null;
            land(this.node.querySelector('[data-key="' + key + '"]') || this.node.querySelector('[data-key="library-count"]'));
          }
        }
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

    // Preview opens below its row, and pressing Preview again closes it.
    async show(row) {
      if (this.preview && this.preview.row.id === row.id) { this.closePreview(); return; }
      const opened = { row, loading: true };
      this.preview = opened;
      this.render();
      try {
        Object.assign(opened, { loading: false, found: await this.a.post('library-document', { id: row.id, revision: row.revision }) });
      } catch (error) {
        Object.assign(opened, { loading: false, problem: message(error) });
      }
      if (this.preview !== opened) return;      // closed, or another opened, meanwhile
      this.render();
      land(this.node.querySelector('[data-key="library-preview-heading"]'));
    }

    // Back to the row's Preview, in view, so the person keeps their place.
    closePreview() {
      const id = this.preview && this.preview.row.id;
      this.preview = null;
      this.render();
      if (id) land(this.node.querySelector('[data-key="library-preview-' + id + '"]'));
    }

    // Remove from library (hidden) or Restore. Nothing is deleted: the server only hides the
    // document from browsing and from every studio's Add from library.
    async hide(row, hidden) {
      const held = this.preview;
      if (!held || held.busy) return;
      held.busy = true; held.failed = '';
      this.render();
      try {
        await this.a.post('library-hide', { id: row.id, hidden });
      } catch (error) {
        held.busy = false; held.failed = message(error);
        if (this.preview === held) this.render();
        return;
      }
      const items = (this.answer && this.answer.items) || [];
      const at = items.findIndex((one) => one.id === row.id);
      const stays = !hidden || this.showHidden;
      const next = stays ? row : (items[at + 1] || items[at - 1]);
      this.preview = null;
      this.focusAfter = next ? 'library-preview-' + next.id : 'library-count';
      if (this.a.said) {
        this.a.said(hidden
          ? '“' + row.title + '” was removed from the library. Projects that use it keep their copy.'
          : '“' + row.title + '” is back in the library.');
      }
      await this.load();
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
        if (this.ticked.size + found.matching.filter((one) => !this.ticked.has(one.id) && !this.unavailable(one)).length > max) {
          throw new Error('That would be more than ' + max + ' documents. Narrow the filters first.');
        }
        const titles = new Map(((this.answer && this.answer.items) || []).map((row) => [row.id, row.title]));
        for (const one of found.matching) {
          if (this.unavailable(one)) continue;
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
      const form = make('form', 'filter-bar' + (this.filtersOpen ? ' filters-open' : ''));
      form.setAttribute('role', 'search');
      form.noValidate = true;
      const title = make('label', 'field-label', 'Search');
      title.htmlFor = this.ns + 'query';
      const box = make('input', 'input');
      box.type = 'search';
      box.id = this.ns + 'query';
      box.dataset.key = 'library-query';
      box.maxLength = 200;
      box.autocomplete = 'off';
      box.placeholder = 'Title or words in the document';
      box.value = this.typed.query;
      box.addEventListener('input', () => { this.typed.query = box.value; });
      const go = make('button', 'button', 'Search');
      go.type = 'submit';
      go.dataset.key = 'library-search';
      // On a phone only the search shows; Filters opens the rest (ui-kit's .filters-toggle,
      // as deck_web/lists.js draws it) and counts those set, remembered ones included.
      const set = SET.filter((key) => this.filters[key]).length;
      const toggle = button(set ? 'Filters (' + set + ')' : 'Filters', 'button filters-toggle', () => {
        this.filtersOpen = !this.filtersOpen;
        this.render();
      }, 'library-filters-toggle');
      toggle.setAttribute('aria-expanded', String(this.filtersOpen));
      add(form, add(make('div', 'field search'), title, box), toggle,
        choice(this.ns, 'kind', 'Type', options(labels.kinds, 'All types'), this.filters.kind, (k, v) => this.changed(k, v)),
        choice(this.ns, 'studio', 'From', options(labels.studios, 'All studios'), this.filters.studio, (k, v) => this.changed(k, v)),
        go);
      const more = make('details', 'more-filters');
      more.dataset.key = 'library-more';
      // Filters opens Origin, Status and Author too; otherwise it stays as the person left it.
      more.open = this.filtersOpen || (this.moreOpen !== null ? this.moreOpen
        : Boolean(this.filters.origin || this.filters.state || this.filters.author));
      more.addEventListener('toggle', () => { if (!this.filtersOpen) this.moreOpen = more.open; });
      const authorTitle = make('label', 'field-label', 'Author');
      authorTitle.htmlFor = this.ns + 'author';
      const author = make('input', 'input');
      author.id = this.ns + 'author';
      author.dataset.key = 'library-author';
      author.maxLength = 100;
      author.value = this.typed.author;
      author.addEventListener('input', () => { this.typed.author = author.value; });
      add(more, make('summary', '', 'More filters'),
        choice(this.ns, 'origin', 'Origin', options(labels.origins, 'Any origin'), this.filters.origin, (k, v) => this.changed(k, v)),
        choice(this.ns, 'state', 'Status', options(labels.states, 'Any status'), this.filters.state, (k, v) => this.changed(k, v)),
        add(make('div', 'field'), authorTitle, author));
      form.append(more);
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        this.filters.query = this.typed.query.trim();
        this.filters.author = this.typed.author.trim();
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
      if (row.hidden) text.append(add(make('span', 'quiet'), make('span', 'tag', 'Hidden'), ' Not listed or offered in Add from library.'));
      const unavailable = this.unavailable(row);
      if (unavailable) text.append(add(make('span', 'quiet'), make('span', 'tag', unavailable.label), unavailable.detail ? ' ' + unavailable.detail : ''));
      if (this.selectable) {
        const tick = make('label', 'check library-tick');
        const box = make('input');
        box.type = 'checkbox';
        box.dataset.key = 'library-tick-' + row.id;
        box.checked = on;
        box.disabled = !row.readable || Boolean(unavailable);
        box.setAttribute('aria-label', unavailable ? row.title + ' is unavailable: ' + unavailable.label
          : (on ? 'Selected: ' : 'Select ') + row.title);
        box.addEventListener('change', () => this.tick(row, box.checked));
        add(item, add(tick, box, text));
      } else {
        item.append(text);
      }
      // One action a row: Preview, which holds the downloads (and Remove from library).
      const open = Boolean(this.preview && this.preview.row.id === row.id);
      const look = button('Preview', 'button button-quiet', () => this.show(row), 'library-preview-' + row.id);
      look.setAttribute('aria-expanded', String(open));
      look.setAttribute('aria-label', 'Preview ' + row.title);
      const actions = add(make('div', 'bar library-row-actions'), look);
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
      return add(item, actions);
    }

    // The preview, in its own list item just below its row: the text, then every download,
    // then (Marketing Studio) Remove from library or Restore, confirmed in place.
    previewPart() {
      if (!this.preview) return null;
      const held = this.preview;
      const { row, found, problem, loading } = held;
      const part = make('section', 'library-preview');
      const headingId = this.ns + 'preview-title';
      part.setAttribute('aria-labelledby', headingId);
      const heading = make('h3', '', row.title);
      heading.id = headingId;
      heading.tabIndex = -1;
      heading.dataset.key = 'library-preview-heading';
      const head = add(make('div', 'panel-heading'), heading,
        button('Close preview', 'button button-quiet', () => this.closePreview(), 'library-preview-close'));
      part.append(head);
      if (loading) part.append(make('p', 'quiet', 'Reading the document…'));
      if (problem) part.append(make('p', 'problem', problem));
      if (found) {
        if (!found.readable) part.append(make('p', 'problem', found.problem || 'It has no readable text.'));
        for (const gap of found.gaps || []) part.append(make('p', 'quiet', gap));
        if (found.text) {
          const passage = make('pre', 'library-preview-text', found.text);
          passage.tabIndex = 0;     // it scrolls, so the keyboard can scroll it
          passage.setAttribute('aria-label', 'Text of ' + row.title);
          part.append(passage);
        }
        if (found.truncated) part.append(make('p', 'quiet', 'Only the beginning is shown here: ' + found.characters.toLocaleString() + ' characters in all.'));
      }
      const formats = (found && found.formats) || row.formats || [];
      if (!this.selectable && this.a.download && formats.length) {
        part.append(add(make('div', 'bar library-preview-actions'), ...formats.map((format) =>
          button('Download ' + FORMATS[format], 'button button-quiet', () => this.a.download(row, format), 'library-download-' + format + '-' + row.id))));
      }
      if (this.manage && !loading) part.append(this.removal(held));
      return part;
    }

    // Remove from library says what it does before it does it; Restore undoes it.
    removal(held) {
      const { row } = held;
      const part = make('div', 'library-removal');
      if (held.failed) {
        const said = make('p', 'problem', held.failed);
        said.setAttribute('role', 'alert');
        part.append(said);
      }
      if (row.hidden) {
        const restore = button(held.busy ? 'Restoring…' : 'Restore to library', 'button button-quiet', () => this.hide(row, false), 'library-restore-' + row.id);
        restore.disabled = Boolean(held.busy);
        return add(part, make('p', 'quiet', 'Removed from the library: it is not listed here or offered in any studio’s Add from library. Projects that already use it keep their copy.'),
          add(make('div', 'bar'), restore));
      }
      if (!held.confirming) {
        return add(part, add(make('div', 'bar'), button('Remove from library…', 'button button-quiet', () => {
          held.confirming = true;
          this.render();
          land(this.node.querySelector('[data-key="library-remove-cancel"]'));
        }, 'library-remove-' + row.id)));
      }
      const said = make('p', '', 'Remove “' + row.title + '” from the library? It will no longer be listed here or offered in any studio’s Add from library. Nothing is deleted: every revision is kept, projects that already use it keep their copy and keep working, and no studio workspace is changed. Show hidden can restore it.');
      said.setAttribute('role', 'status');
      const go = button(held.busy ? 'Removing…' : 'Remove from library', 'button button-danger', () => this.hide(row, true), 'library-remove-confirm');
      const keep = button('Keep it', 'button button-quiet', () => {
        held.confirming = false; held.failed = '';
        this.render();
        land(this.node.querySelector('[data-key="library-remove-' + row.id + '"]'));
      }, 'library-remove-cancel');
      go.disabled = keep.disabled = Boolean(held.busy);
      return add(part, said, add(make('div', 'bar'), go, keep));
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
      const count = make('h3', '', answer ? (total === 1 ? '1 document' : total + ' documents') : 'Documents');
      count.tabIndex = -1;
      count.dataset.key = 'library-count';
      heading.append(count);
      // Show hidden lists what Remove from library hid, so it can be restored.
      if (this.manage && answer && (answer.hidden || this.showHidden)) {
        const shown = make('label', 'check select-page');
        const box = make('input');
        box.type = 'checkbox';
        box.dataset.key = 'library-show-hidden';
        box.checked = this.showHidden;
        box.addEventListener('change', () => { this.showHidden = box.checked; this.offset = 0; this.load(); });
        heading.append(add(shown, box, make('span', '', 'Show hidden (' + (answer.hidden || 0) + ')')));
      }
      if (this.selectable && items.length) {
        const shown = items.filter((row) => row.readable && !this.unavailable(row));
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
      else if (answer && !answer.available) list.append(make('li', answer.problem ? 'problem' : 'quiet', answer.problem || 'Nothing has been kept in the Document Library yet. Uploads, finished blogs and delivered decks appear here.'));
      else if (answer && !items.length) list.append(make('li', 'quiet', 'No documents match these filters.'));
      const preview = this.previewPart();
      for (const row of items) {
        list.append(this.row(row));
        if (preview && this.preview.row.id === row.id) list.append(add(make('li', 'library-preview-item'), preview));
      }
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
      const titleId = 'doclib-sheet-title-' + (++instances);
      dialog.setAttribute('aria-labelledby', titleId);
      const title = make('h2', '', adapter.title || 'Add from library');
      const noun = adapter.noun || 'project';
      title.id = titleId;
      const bar = make('div', 'library-selection');
      let problem = '';
      let busy = false;
      const close = button('Close', 'button button-quiet', () => dismiss(), 'library-close');
      const catalog = new Catalog(adapter, { selectable: true, onChange: () => draw() });
      // After Use selected, focus goes where the page says (its redrawn Add from library),
      // else back to what opened the sheet, while it is still on the page.
      const finish = (value) => {
        dialog.close(); dialog.remove();
        const back = (value && adapter.refocus && adapter.refocus())
          || (opener && document.body.contains(opener) ? opener : null);
        if (back && back.focus) back.focus();
        resolve(value);
      };
      const dismiss = () => { if (!busy) finish(false); };   // never while choices are landing
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
        const cancel = button('Cancel', 'button button-quiet', dismiss, 'library-cancel');
        cancel.disabled = busy;
        close.disabled = busy;
        parts.push(add(make('div', 'create-foot bar'), go, cancel));
        bar.replaceChildren(...parts);
      }
      add(dialog, add(make('header', 'dialog-header'), title, close),
      add(make('div', 'dialog-content'),
        make('p', 'quiet', 'Choose documents for this ' + noun + ' only. Adding them starts nothing, sends nothing to an assistant and changes no research settings. A new ' + noun + ' starts with none.'),
        catalog.node, bar));
      dialog.addEventListener('cancel', (event) => { event.preventDefault(); dismiss(); });
      document.body.append(dialog);
      draw();
      dialog.showModal();
      const first = dialog.querySelector('[data-key="library-query"]');
      if (first) first.focus();
    });
  }

  window.StudioLibrary = { Catalog, pick };
}());
