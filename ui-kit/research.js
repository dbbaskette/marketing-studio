/* Shared research sources and progress, using authenticated product adapters.
 * Capture is read-only. Only the parent's Start action may launch research.
 * No framework, provider call, Google write, or stylesheet fork lives here. */
'use strict';
const StudioResearch = (() => {
  const make = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
  const add = (n, ...children) => { n.append(...children.filter(c => c != null)); return n; };
  const button = (text, fn, key) => { const n = make('button', 'button button-quiet', text); n.type = 'button'; n.dataset.key = key || text; n.addEventListener('click', fn); return n; };
  const field = (label, value, key, multiline = false) => { const wrap = make('label', 'field'); const input = make(multiline ? 'textarea' : 'input', 'input'); input.value = value || ''; input.dataset.key = key; if (multiline) input.rows = 3; return { wrap: add(wrap, make('span', 'field-label', label), input), input }; };
  const check = (text, on, fn, key) => { const n = make('label', 'check'); const input = make('input'); input.type = 'checkbox'; input.checked = !!on; input.dataset.key = key; input.addEventListener('change', () => fn(input.checked)); return add(n, input, make('span', '', text)); };
  const array = value => Array.isArray(value) ? value : [];
  const message = error => error && error.message || String(error || 'This action could not finish.');
  const summary = state => !state ? 'Loading sources…' : state.external ? (state.restricted ? 'Use supplied sources and search approved sites.' : 'Use supplied sources and search the public web.') : 'Use supplied sources only.';

  // Every web link in a file a person chose: a plain list, a spreadsheet export, notes or a
  // saved page. Order kept, each link once; http is asked for as https, and a link carrying a
  // sign-in is left out. `left` counts what was found and not kept.
  const LINK_FILE_BYTES = 256 * 1024, LONG_LIST = 8;
  function linksIn(text) {
    const links = [], seen = new Set(); let left = 0;
    for (const found of String(text || '').match(/https?:\/\/[^\s<>"'`|\\^{}]+/gi) || []) {
      let link = found.replace(/^http:/i, 'https:');
      // Punctuation and a closing bracket after a link belong to the sentence around it.
      for (;;) { const cut = link.replace(/[.,;:!?*]+$/, '').replace(/&(?:amp|quot|gt|lt);?$/i, '');
        const close = cut.slice(-1), open = {')': '(', ']': '['}[close];
        const next = open && cut.split(open).length < cut.split(close).length ? cut.slice(0, -1) : cut;
        if (next === link) break; link = next; }
      link = link.replace(/&amp;/gi, '&');
      let parsed; try { parsed = new URL(link); } catch (_) { left += 1; continue; }
      if (parsed.username || parsed.password || !parsed.hostname.includes('.')) { left += 1; continue; }
      if (seen.has(parsed.href)) continue;
      seen.add(parsed.href); links.push(link);
    }
    return {links, left};
  }
  async function linksInFile(file) {
    if (!file) return {links: [], left: 0, problem: 'Choose a file first.'};
    if (file.size > LINK_FILE_BYTES) return {links: [], left: 0, problem: file.name + ': choose a file of links within 256 KB.'};
    const found = linksIn(await file.text());
    return found.links.length ? found : {...found, problem: file.name + ' has no web links in it. Links start with https://.'};
  }

  const queuedNotes = new Map();
  function noteEditor(row, hooks) {
    if (typeof Drafting === 'undefined' || !hooks.notes || !hooks.notesScope) return null;
    const key = hooks.notesScope + '\n' + row.id;
    let held = queuedNotes.get(key);
    if (!held) {
      class Note extends Drafting.Intake {
        constructor() { super(sent => hooks.notes(row.id, sent));this.state={basis:row.preview.basis,note:''};this.hydrated=false;this.notify=()=>{}; }
        snapshot(value) { return {basis:value.basis,note:value.note}; }
        status() { this.notify(); }
        async loadNote() { const saved=await this.load();if(!this.hydrated){this.hydrated=true;if(saved)Object.assign(this.state,saved);}return this.state; }
      }
      held=new Note();queuedNotes.set(key,held);
    }
    const box=make('div','paper research-queued-note'),entry=field('Note for the next research change',held.state.note,'research-queued-note-'+row.id,true);
    entry.input.disabled=!held.hydrated;
    const status=make('p','quiet field-hint');status.setAttribute('role','status');
    const save=button('Save queued note',async()=>{
      save.disabled=true;
      try { await held.loadNote();held.state={basis:row.preview.basis,note:entry.input.value};await held.keep(held.state); }
      finally { save.disabled=false;held.notify(); }
    },'research-queue-save-'+row.id);
    entry.input.addEventListener('input',()=>{held.state.note=entry.input.value;show();});
    const show=()=>{const dirty=held.state.note!==(held.saved?.note||'')||(!!held.saved&&held.state.basis!==held.saved.basis);status.textContent=held.problem||((held.writing||held.pending)?'Saving queued note…':dirty?'Note is not queued until you save.':held.saved?'Queued privately. Evidence and scope are unchanged.':'No queued note.');if(held.saved?.basis&&held.saved.basis!==row.preview.basis)status.textContent+=' This note belongs to an earlier section revision; review it before applying a change.';};
    held.notify=show;
    const copy=button('Copy note for research refresh',async()=>{
      try { if(typeof navigator!=='undefined'&&navigator.clipboard){await navigator.clipboard.writeText(entry.input.value);status.textContent='Copied. Use the research refresh impact preview to apply an explicit change.';}else{entry.input.focus();entry.input.select?.();status.textContent='Copy the selected note, then use the research refresh impact preview.';} }
      catch { status.textContent='Copy the note manually, then use the research refresh impact preview.'; }
    },'research-queue-copy-'+row.id);
    add(box,entry.wrap,add(make('div','bar'),save,copy),status,make('p','quiet field-hint','Saving queues a concern only. After research pauses or finishes, use the existing research refresh to preview affected sections and approve the actual change. Notes never alter in-flight evidence or final checked output.'));
    held.loadNote().then(()=>{entry.input.value=held.state.note;entry.input.disabled=false;show();}).catch(error=>{status.textContent=message(error);});
    return box;
  }

  class Editor {
    constructor(adapter) {
      this.a = adapter;
      // Optional, per studio: the Keep in library / Only this project choice for an uploaded
      // file. Off unless the adapter turns it on; then it starts at Keep in library.
      this.keep = adapter.keepChoice ? true : null;
      this.kept = {};     // source id -> what the Document Library said of its file
      this.value = adapter.value || null;
      this.resume = adapter.resume || null;
      this.urls = ''; this.text = ''; this.name = 'Pasted notes'; this.busy = false; this.problem = ''; this.reading = ''; this.said = '';
      for(const key of ['urls','text','name','pasting','keep']) if(adapter.entry && adapter.entry[key] !== null && adapter.entry[key] !== undefined) this[key] = adapter.entry[key];
      this.node = make('section', 'research-source-editor stack');
      this.node.setAttribute('aria-label', adapter.label || 'Research sources');
      this.render();
      if (!this.value) this.load();
    }
    async load() {
      if (this.busy) return;
      this.busy = true; this.render();
      try { this.value = await this.a.request(this.value || this.resume ? {action: 'read', id: (this.value || this.resume).id} : {action: 'create'}); this.resume = null; this.problem = ''; }
      catch (error) { this.problem = message(error); }
      finally { this.busy = false; this.render(); this.changed(); }
    }
    changed() { if (this.a.onChange) this.a.onChange(this.value); }
    async act(action, data = {}, saying = '') {
      if (this.busy || !this.value) return false;
      this.busy = true; this.problem = ''; this.reading = saying || (action === 'capture' || action === 'tabs' ? 'Reading source…' : 'Saving source choices…'); this.render();
      try {
        const { library_kept: kept, ...value } = await this.a.request({action, id: this.value.id, expected: this.value.revision, ...data});
        this.value = value;
        if (kept && kept.source) this.kept[kept.source] = kept;
        return true;
      }
      catch (error) { this.problem = message(error); return false; }
      finally { this.busy = false; this.reading = ''; this.render(); this.changed(); }
    }
    // Links and files are read one after another. What is added while a long list of links
    // is still being read waits its turn; nothing chosen is dropped.
    run(job) { const next = (this.chain || Promise.resolve()).then(job, job); this.chain = next.catch(() => {}); return next; }
    links() { return this.run(() => this.readLinks()); }
    files(files) { const chosen = Array.from(files || []); return this.run(() => this.readFiles(chosen)); }
    linkFile(file) { return this.run(() => this.readLinkFile(file)); }
    // Leave out every source that could not be read, in one go, so a few bad links among
    // hundreds do not each need a press before starting.
    excludeUnread() {
      return this.run(async () => {
        const ids = array(this.value && this.value.sources).filter(source => source.status === 'needs-attention').map(source => source.id);
        for (const [at, id] of ids.entries()) if (!await this.act('exclude', {source: id}, 'Excluding ' + (at + 1) + ' of ' + ids.length + '…')) break;
      });
    }
    async readLinks() {
      const links = this.urls.trim().split(/\s+/).filter(Boolean);
      if (!links.length) { this.problem = 'Paste one or more links first.'; this.render(); return; }
      for (const url of links) {
        let parsed; try { parsed = new URL(url); } catch (_) { this.problem = 'Check this link: ' + url; this.render(); return; }
        if (parsed.protocol !== 'https:' || parsed.username || parsed.password) { this.problem = 'Use HTTPS links without embedded credentials.'; this.render(); return; }
      }
      let added = 0;
      for (const url of links) {
        this.progress = links.length > 1 ? {done: added, total: links.length} : null;
        if (!await this.act('capture', {kind: 'url', url}, links.length > 1 ? 'Reading link ' + (added + 1) + ' of ' + links.length + '…' : '')) break;
        added += 1;
        this.urls = this.urls.split(/\s+/).filter(v => v && v !== url).join('\n');
      }
      this.progress = null;
      this.render();
      return added;
    }
    // A file of links: every link in it goes into the box and is added, like pasted ones.
    async readLinkFile(file) {
      if (!this.value) return;
      let found; try { found = await linksInFile(file); } catch (_) { found = {links: [], left: 0, problem: 'This file could not be read as text.'}; }
      if (found.problem) { this.problem = found.problem; this.said = ''; this.render(); return; }
      const have = new Set(array(this.value.sources).map(source => source.origin)), fresh = found.links.filter(link => !have.has(link));
      const already = found.links.length - fresh.length;
      if (!fresh.length) { this.problem = ''; this.said = 'Every link in ' + file.name + ' is already a source here.'; this.render(); return; }
      const typed = this.urls.trim().split(/\s+/).filter(Boolean);
      this.urls = [...typed, ...fresh.filter(link => !typed.includes(link))].join('\n');
      this.said = '';
      const added = await this.readLinks();
      const unread = array(this.value.sources).filter(source => fresh.includes(source.origin) && source.status === 'needs-attention').length;
      this.said = (added || 0) + ' of ' + fresh.length + (fresh.length === 1 ? ' link' : ' links') + ' in ' + file.name + ' added.'
        + (unread ? ' ' + unread + ' could not be read: each says why below.' : '')
        + (already ? ' ' + already + (already === 1 ? ' was' : ' were') + ' already here.' : '')
        + (found.left ? ' ' + found.left + (found.left === 1 ? ' was' : ' were') + ' not usable and left out.' : '');
      this.render();
    }
    async readFiles(files) {
      for (const file of files) {
        if (file.size > 8_000_000) { this.problem = file.name + ': choose a source within 8 MB.'; this.render(); continue; }
        const bytes = new Uint8Array(await file.arrayBuffer()); let binary = '';
        for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
        if (!await this.act('capture', {kind: 'file', name: file.name, content: btoa(binary), ...(this.keep === null ? {} : {keep: this.keep})})) break;
      }
    }
    spec() { return this.value ? {id: this.value.id, expected: this.value.revision} : null; }
    valid(hasPrimary = false) {
      return !!this.value && !this.busy && !this.problem && !this.value.over && array(this.value.sources).every(s => ['ready', 'excluded'].includes(s.status))
        && (hasPrimary || this.value.external || this.value.sources.some(s => s.status === 'ready'));
    }
    choice(hasPrimary = false) { const s = this.value || {}; return {documents: hasPrimary || array(s.sources).some(s => s.status === 'ready'), sites: s.external && s.restricted ? array(s.sites) : [], web: !!s.external && !s.restricted}; }
    async preview(source) {
      if (this.busy) return;
      try {
        const found = await this.a.request({action: 'preview', id: this.value.id, source: source.id});
        if (this.a.preview) return this.a.preview(source, found);
        this.previewed = {source, ...found}; this.render();
      } catch (error) { this.problem = message(error); this.render(); }
    }
    source(source) {
      const row = make('li', 'research-source-row');
      const copy = add(make('div', 'research-source-copy'), make('p', 'row-title', source.name),
        make('p', 'quiet', source.origin || source.kind));
      // Say that the text itself was read, and how much: a link's row is more than its address.
      if (source.status === 'ready' && source.characters) copy.append(make('p', 'quiet', (['url', 'google-doc', 'google-slides'].includes(source.kind) ? 'Page text read' : 'Text read') + ' · ' + Number(source.characters).toLocaleString('en-US') + ' characters'));
      if (source.kind === 'google-doc' || source.kind === 'google-slides') {
        const tabs = array(source.tabs), selected = array(source.selected_tabs);
        const detail = make('details', 'research-tabs'); detail.dataset.key = 'tabs-' + source.id;
        const word = source.kind === 'google-slides' ? 'slides' : 'tabs';
        add(detail, make('summary', '', selected.length === tabs.length ? 'All ' + tabs.length + ' ' + word + ' included · choose ' + word : selected.length + ' of ' + tabs.length + ' ' + word + ' selected'),
          make('p', 'quiet', 'Only selected content is retained and passed to research.'));
        for (const tab of tabs) detail.append(check(tab.title, selected.includes(tab.id), on => {
          const values = on ? [...selected, tab.id] : selected.filter(id => id !== tab.id);
          if (!values.length) { this.problem = 'Keep at least one tab or remove this source.'; this.render(); return; }
          this.act('tabs', {source: source.id, selected: values});
        }, 'tab-' + source.id + '-' + tab.id));
        copy.append(detail);
      }
      if (source.status === 'needs-attention') add(copy, make('p', 'problem', source.problem || 'This source could not be read.'),
        make('p', 'quiet', 'Other captured sources are kept. Retry, remove or exclude this source.'));
      if (source.status === 'excluded') copy.append(make('p', 'quiet', 'Excluded from this request.'));
      const kept = this.kept[source.id];
      if (kept && kept.state === 'kept') copy.append(make('p', 'quiet', 'Kept in the Document Library too.'));
      if (kept && kept.state === 'failed') add(copy, make('p', 'problem', 'Not kept in the Document Library: ' + (kept.problem || 'it could not be kept.')),
        button('Keep in library again', () => this.act('library-keep', {source: source.id}), 'library-keep-' + source.id));
      if (array(source.warnings).length) copy.append(make('p', 'quiet', source.warnings.join(' ')));
      const tools = make('div', 'bar');
      if (source.status === 'ready') tools.append(button('Preview text', () => this.preview(source), 'preview-' + source.id));
      if (source.status === 'needs-attention') {
        if (source.kind === 'url' || source.kind === 'google-doc' || source.kind === 'google-slides') tools.append(button('Try reading again', () => this.act('capture', {kind: 'url', source: source.id, url: source.origin}), 'retry-' + source.id));
        tools.append(button('Exclude source', () => this.act('exclude', {source: source.id}), 'exclude-' + source.id));
      }
      add(copy, tools);
      const remove = button('Remove', () => this.act('remove', {source: source.id}), 'remove-' + source.id);
      remove.setAttribute('aria-label', 'Remove ' + source.name);
      return add(row, copy, remove);
    }
    keepChoice() {
      const options = ['Keep in library', 'Only this project'];
      const says = ['A copy of each file is also kept in the Document Library on this computer, for other projects. It is not shared with your team.',
        'Files are kept in this project only.'];
      const at = this.keep ? 0 : 1;
      const group = make('div', 'segmented'); group.setAttribute('role', 'group'); group.setAttribute('aria-label', 'Where an uploaded file is kept');
      group.dataset.at = String(at); group.dataset.count = '2';
      const thumb = make('span', 'seg-thumb'); thumb.setAttribute('aria-hidden', 'true'); group.append(thumb);
      options.forEach((text, index) => {
        const option = button(text, () => { if (this.keep !== (index === 0)) { this.keep = index === 0; this.render(); this.changed(); } }, 'research-keep-' + index);
        option.className = 'seg-option'; option.setAttribute('aria-pressed', String(index === at)); group.append(option);
      });
      return add(make('div', 'field research-keep'), make('p', 'field-label', 'Where an uploaded file is kept'), group, make('p', 'field-hint', says[at]));
    }
    render() {
      const focused = this.node.contains(document.activeElement) ? document.activeElement.dataset.key : '';
      if (focused) this.focused = focused;
      const restore = focused || (document.activeElement === document.body ? this.focused : '');
      const opened = Array.from(this.node.querySelectorAll('details[open][data-key]')).map(n => n.dataset.key);
      const scroll = this.node.scrollTop;
      let keptListScroll = 0;
      this.node.replaceChildren();
      const state = this.value;
      const panel = make('div', 'research-sources paper');
      add(panel, make('h3', 'card-title', this.a.label || 'Your sources'));
      if (this.a.primarySummary) panel.append(make('p', 'quiet', this.a.primarySummary));
      if (!this.a.policyOnly) {
      const links = field('Web pages or Google Docs links', this.urls, 'research-urls', true);
      links.input.placeholder = 'Paste one or several links'; links.input.addEventListener('input', () => this.urls = links.input.value);
      add(links.wrap, make('p', 'field-hint', 'Uses your existing Google sign-in and shared defaults.'));
      const addLinks = button('Add links', () => this.links(), 'research-add-links');
      add(panel, add(make('div', 'research-link-entry'), links.wrap, addLinks));
      const file = make('input'); file.type = 'file'; file.multiple = true; file.hidden = true;
      file.accept = '.pdf,application/pdf,.docx,.txt,.md,.markdown,.html,.htm';
      file.setAttribute('aria-label', 'Upload source files');
      file.addEventListener('change', () => this.files(file.files));
      const linkFile = make('input'); linkFile.type = 'file'; linkFile.hidden = true;
      linkFile.accept = '.txt,.md,.markdown,.csv,.html,.htm,text/plain,text/csv';
      linkFile.setAttribute('aria-label', 'Upload a file of links');
      linkFile.addEventListener('change', () => { const chosen = linkFile.files && linkFile.files[0]; if (chosen) this.linkFile(chosen); });
      const actions = add(make('div', 'bar'), button('Choose files', () => file.click(), 'research-files'),
        button('Add links from a file', () => linkFile.click(), 'research-links-file'),
        button(this.pasting ? 'Close pasted text' : 'Paste text', () => { this.pasting = !this.pasting; this.render(); this.changed(); }, 'research-paste'));
      // Optional, per studio: Add from library, which the studio's own adapter opens (the
      // shared StudioLibrary.pick) and whose picks it lists under the sources (`extra`).
      if (this.a.library) actions.append(button('Add from library', () => this.a.library(this), 'research-library'));
      actions.append(button('Use saved research', async () => {
        if (this.a.savedResearch) return this.a.savedResearch(this);
        try { this.saved = await this.a.request({action:'saved'}); this.render(); }
        catch(error) { this.problem=message(error); this.render(); }
      }, 'research-saved'));
      add(panel, actions, file, linkFile);
      if (this.said) { const said = make('p', 'quiet field-hint', this.said); said.setAttribute('role', 'status'); said.dataset.key = 'research-links-said'; panel.append(said); }
      if (this.keep !== null) panel.append(this.keepChoice());
      if (this.pasting) {
        const name = field('Source name', this.name, 'research-text-name'); name.input.addEventListener('input', () => this.name = name.input.value);
        const text = field('Source text', this.text, 'research-text', true); text.input.rows = 6; text.input.addEventListener('input', () => this.text = text.input.value);
        add(panel, name.wrap, text.wrap, button('Add text', async () => {
          if (await this.act('capture', {kind: 'text', name: this.name, text: this.text})) {
            this.text = ''; this.pasting = false; this.render();
            // The submit was removed with the pasted-text fields. Return to a stable
            // source action, rather than leaving keyboard focus on the page body.
            Array.from(this.node.querySelectorAll('[data-key]')).find(n => n.dataset.key === 'research-paste')?.focus();
          }
        }, 'research-add-text'));
      }
      // Many sources: one line says how many there are and how they stand, the list scrolls in
      // its own box and can be searched, and what could not be read can be shown alone.
      const sources = array(state && state.sources), unread = sources.filter(source => source.status === 'needs-attention');
      const long = sources.length > LONG_LIST;
      if (this.only === 'unread' && !unread.length) this.only = '';
      if (sources.length) {
        const ready = sources.filter(source => source.status === 'ready').length, excluded = sources.filter(source => source.status === 'excluded').length;
        const overview = make('div', 'research-overview');
        const said = make('p', 'row-title', sources.length + (sources.length === 1 ? ' source' : ' sources') + ' · ' + ready + ' read'
          + (unread.length ? ' · ' + unread.length + ' could not be read' : '') + (excluded ? ' · ' + excluded + ' excluded' : ''));
        said.dataset.key = 'research-overview'; said.setAttribute('role', 'status'); overview.append(said);
        if (this.progress) {
          const bar = make('progress', 'research-reading'); bar.max = this.progress.total; bar.value = this.progress.done;
          bar.setAttribute('aria-label', 'Links read');
          const now = make('p', 'quiet', 'Reading link ' + Math.min(this.progress.done + 1, this.progress.total) + ' of ' + this.progress.total + '. You can keep scrolling and searching; files you choose now are added when the links finish.');
          now.dataset.key = 'research-reading-now';
          add(overview, bar, now);
        }
        // Too many for one research run: said here, while it can still be put right.
        if (state.over) { const much = make('p', 'problem', state.over); much.dataset.key = 'research-over'; much.setAttribute('role', 'alert'); overview.append(much); }
        panel.append(overview);
      }
      const list = make('ul', 'research-source-list' + (long ? ' research-source-scroll' : ''));
      if (long) { list.tabIndex = 0; list.setAttribute('aria-label', 'Your sources. Scroll to see all ' + sources.length + '.'); }
      const shown = make('p', 'quiet field-hint'); shown.dataset.key = 'research-shown'; shown.setAttribute('role', 'status');
      const sift = () => {
        const words = (this.find || '').trim().toLowerCase(); let seen = 0;
        for (const row of list.children) { if (row.dataset.find === undefined) continue; row.hidden = !!words && !row.dataset.find.includes(words); if (!row.hidden) seen += 1; }
        const total = this.only === 'unread' ? unread.length : sources.length;
        shown.textContent = words ? 'Showing ' + seen + ' of ' + total + '.' : this.only === 'unread' ? 'Showing the ' + total + ' that could not be read.' : '';
        shown.hidden = !shown.textContent;
      };
      if (long) {
        const find = field('Find a source', this.find || '', 'research-find'); find.input.type = 'search'; find.input.placeholder = 'Part of a title or address';
        find.input.dataset.free = 'true'; find.input.addEventListener('input', () => { this.find = find.input.value; sift(); });
        const tools = make('div', 'bar');
        if (unread.length) {
          const all = button('All ' + sources.length, () => { this.only = ''; this.render(); }, 'research-show-all');
          const bad = button('Could not be read ' + unread.length, () => { this.only = 'unread'; this.render(); }, 'research-show-unread');
          all.dataset.free = bad.dataset.free = 'true';
          all.setAttribute('aria-pressed', String(this.only !== 'unread')); bad.setAttribute('aria-pressed', String(this.only === 'unread'));
          add(tools, all, bad, button('Exclude all ' + unread.length + ' that could not be read', () => this.excludeUnread(), 'research-exclude-unread'));
        }
        add(panel, find.wrap, unread.length ? tools : null, shown);
      }
      for (const source of this.only === 'unread' ? unread : sources) { const row = this.source(source); row.dataset.find = ((source.name || '') + ' ' + (source.origin || '')).toLowerCase(); list.append(row); }
      sift();
      keptListScroll = this.listNode ? this.listNode.scrollTop : 0; this.listNode = list;
      const extra = this.a.extra ? this.a.extra(this) : null;
      if (!state || (!state.sources.length && !extra)) list.append(make('li', 'quiet', state ? 'Add material here, or allow external search below.' : 'Loading the source draft…'));
      add(panel, list, extra); this.node.append(panel);
      }
      if (this.saved && !this.a.policyOnly) {
        const choices = add(make('section', 'paper stack'), make('h3','card-title','Saved research'));
        choices.append(make('p','quiet','Choose a reviewed result as reference material. Its original audience, purpose and qualifications are kept. Research for a different purpose is checked again.'));
        for(const item of array(this.saved.items)) choices.append(button(item.name+' · '+item.purpose, async()=>{
          if(await this.act('capture',{kind:'saved', source:item.id, revision:item.revision})) {this.saved=null;this.render();}
        },'research-saved-'+item.id));
        if(!array(this.saved.items).length) choices.append(make('p','quiet','No complete reviewed research is saved in this workspace yet.'));
        choices.append(button('Close saved research',()=>{this.saved=null;this.render();},'research-close-saved'));
        this.node.append(choices);
      }
      if (this.previewed) {
        const p = this.previewed;
        add(this.node, add(make('section', 'paper research-captured'), make('h3', 'card-title', p.source.name),
          make('p', 'quiet', array(p.warnings).join(' ')), make('pre', 'research-preview-text', p.text),
          p.total > p.text.length ? make('p', 'quiet', 'Showing the first ' + p.text.length.toLocaleString() + ' characters of ' + p.total.toLocaleString() + '.') : null,
          button('Close preview', () => { this.previewed = null; this.render(); }, 'research-close-preview')));
      }
      if (state) {
        const policy = make('div', 'research-policy');
        // A studio may say the choice in its own words (`policyHint`), as long as they say what will happen.
        add(policy, check('Search for additional external sources', state.external, external => this.act('configure', {external}), 'research-external'),
          make('p', 'field-hint', this.a.policyHint ? this.a.policyHint(state) : summary(state)));
        if (state.external && state.sites.length) add(policy, check('Limit additional searches to my approved sites', state.restricted, restricted => this.act('configure', {restricted}), 'research-restricted'));
        add(this.node, policy);
        const advanced = make('details', 'research-options'); advanced.dataset.key = 'research-options'; advanced.append(make('summary', '', 'Research options'));
        const workers = field('Research workers', '', 'research-workers'); const select = make('select', 'input'); select.dataset.key = 'research-workers';
        for (const [value, text] of [[3, 'Automatic · up to 3'], [1, '1 · sequential'], [2, 'Up to 2']]) { const option = make('option', '', text); option.value = String(value); select.append(option); }
        select.value = String(state.workers); select.addEventListener('change', () => this.act('configure', {workers: Number(select.value)})); workers.input.replaceWith(select);
        const focus = field('Focus or topics to avoid', state.focus, 'research-focus', true); focus.input.addEventListener('change', () => this.act('configure', {focus: focus.input.value}));
        add(advanced, workers.wrap, make('p', 'field-hint', 'Bounded by existing assistant capacity and supported limits. Independent review remains separate.'), focus.wrap);
        if (state.sites.length) advanced.append(make('p', 'quiet', 'Approved sites: ' + state.sites.join(', ')));
        this.node.append(advanced);
      }
      const status = make('p', this.problem ? 'problem' : 'quiet', this.problem || this.reading); status.setAttribute('role', this.problem ? 'alert' : 'status'); status.hidden = !status.textContent; this.node.append(status);
      if (this.problem) this.node.append(button('Reload sources', () => this.load(), 'research-reload'));
      // Looking through the list never waits on a source being read.
      for (const control of this.node.querySelectorAll('button, input, textarea, select')) control.disabled = (this.busy || !state) && !control.dataset.free;
      if (this.listNode) this.listNode.scrollTop = keptListScroll;
      // A studio whose library choices are full says so beside them (`libraryFull`), and Add from library waits.
      if (this.a.library && this.a.libraryFull && this.a.libraryFull()) { const more = Array.from(this.node.querySelectorAll('button')).find(n => n.dataset.key === 'research-library'); if (more) more.disabled = true; }
      if (this.problem) { const reload = Array.from(this.node.querySelectorAll('button')).find(n => n.dataset.key === 'research-reload'); if (reload) reload.disabled = this.busy; }
      for (const detail of this.node.querySelectorAll('details[data-key]')) detail.open = opened.includes(detail.dataset.key);
      if (restore) { const target = Array.from(this.node.querySelectorAll('[data-key]')).find(n => n.dataset.key === restore); if (target && !target.disabled) target.focus(); }
      this.node.scrollTop = scroll;
    }
  }

  function workingDraft(state) {
    if (['creator-approved','stopped','stopping','paused','pausing','invalidated','complete','ready-for-review'].includes(state.phase)) return null;
    const rows = array(state.combining).filter(row => row.status === 'kept' && row.preview);
    if (!rows.length) return null;
    const lines = ['# Working draft — independent check pending', '',
      'Incomplete, unreviewed research prose. This is not a finished learner guide or approved material.', '',
      rows.length + ' of ' + array(state.combining).length + ' section drafts available.', ''];
    for (const row of array(state.combining)) {
      if (row.status !== 'kept' || !row.preview) {
        const question = array(row.questions)[0];
        lines.push('## Section pending', '', typeof question === 'string' ? question : question?.question || question?.text || row.id, '', 'Status: ' + row.status, '');
        continue;
      }
      lines.push('Revision: ' + row.preview.basis, '');
      for (const section of array(row.preview.sections)) lines.push('## ' + section.title, '', section.text || '', '');
      lines.push('Sources:', ...array(row.preview.sources).map(source => '- ' + source.title + ' (' + source.permission + ')' + (source.origin ? ': ' + source.origin : '')), '');
      if (row.preview.truncated) lines.push('This preview is shortened; the complete contribution remains saved.', '');
    }
    return {rows, text: lines.join('\n')};
  }

  function progress(state, hooks = {}) {
    if (!state) return null;
    const phase = state.phase || 'investigate';
    const incomplete = ['check-incomplete', 'creator-review'].includes(phase);
    const assembling = array(state.agents?.active).some(agent => agent.section === 'final' || agent.stream === 'final');
    const titles = {'creator-review': 'Research needs your decision', 'creator-approved': 'Research choices saved', read: 'Reading your documents', investigate: 'Collecting evidence', 'investigating': 'Collecting evidence', synthesize: 'Combining findings', 'combining-findings': 'Combining findings', review: 'Independent check', 'independent-check': 'Independent check', complete: 'Research is ready', 'ready-for-review': 'Research is ready', 'needs-attention': 'Research needs attention', 'needs-revision': 'Research needs correction', 'stopping': 'Stopping research', 'pausing': 'Finishing active research before pausing', paused: 'Research paused', stopped: 'Research stopped'};
    const box = make('section', 'research-progress paper'); box.setAttribute('aria-label', 'Research progress');
    const stage = {read:0, investigate:0, investigating:0, synthesize:1, 'combining-findings':1, review:2, 'independent-check':2, 'check-incomplete':2, 'creator-review':2, complete:3, 'ready-for-review':3}[phase];
    const heading = add(make('div', 'research-progress-heading'),
      make('p', 'quiet research-stage-label', stage < 3 ? 'Research · Stage ' + (stage + 1) + ' of 3' : stage === 3 ? 'Research complete' : 'Research progress'),
      make('h3', 'card-title', phase === 'check-incomplete' ? 'Independent check incomplete' : assembling ? 'Assembling the final brief' : titles[phase] || 'Research'));
    // More than fifty documents are read in groups first: how far that has got, and which
    // documents are open now. Afterwards, one line on what the reading found.
    if (state.reading && state.reading.total) {
      const r = state.reading, working = array(r.groups).filter(group => group.status === 'working');
      const spans = working.map(group => group.from + '–' + group.to);
      const note = make('div', 'research-reading-progress'); note.dataset.key = 'research-reading-progress';
      if (phase === 'read' || r.read < r.total) {
        const bar = make('progress', 'research-reading'); bar.max = r.total; bar.value = r.read; bar.setAttribute('aria-label', 'Documents read');
        add(note, bar, make('p', 'quiet', r.read + ' of ' + r.total + ' documents read, in groups of up to 50, one reader to a group.'
          + (spans.length ? ' Reading documents ' + (spans.length === 1 ? spans[0] : spans.slice(0, -1).join(', ') + ' and ' + spans.at(-1)) + ' now.' : '')));
      } else {
        add(note, make('p', 'quiet', 'All ' + r.total + ' documents were read in groups of up to 50. Each research area was given the ones that bear on it most, 50 at most.'
          + (r.unused ? ' ' + r.unused + (r.unused === 1 ? ' bears' : ' bear') + ' on no research area and ' + (r.unused === 1 ? 'was' : 'were') + ' not passed on.' : '')
          + (r.dropped ? ' ' + r.dropped + ' more were relevant to an area that already had 50.' : '')));
      }
      heading.append(note);
    }
    const header = add(make('div', 'research-progress-header'), heading);
    const agents = state.agents;
    const count = Number.isInteger(agents?.count) && agents.count >= 0 ? agents.count : null;
    const team = make('details', 'research-agents'); team.dataset.key = 'research-agents';
    const toggle = make('summary', 'research-agent-counter'); toggle.dataset.key = 'research-agents-toggle';
    const faces = make('span', 'research-agent-faces'); faces.setAttribute('aria-hidden', 'true');
    for (let i = 0; i < Math.max(1, Math.min(count || 0, 3)); i++) {
      const robot = make('span', 'research-agent-robot');
      robot.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect x="4" y="8" width="16" height="12" rx="3"/><path d="M2 12v4m20-4v4M9 13v2m6-2v2"/></svg>';
      faces.append(robot);
    }
    const agentNote = count === null ? (agents?.unconfirmed ? 'Awaiting confirmation' : 'Count unavailable') : count === 0 ? (incomplete ? 'Check needs attention' : ['complete','ready-for-review'].includes(phase) ? 'All agents finished' : ['creator-approved','paused','stopped'].includes(phase) ? 'Progress saved' : 'Preparing next step') : ['review','independent-check'].includes(phase) ? 'Independent review' : ['synthesize','combining-findings'].includes(phase) ? 'Combining findings' : 'Investigating sources';
    add(toggle, faces, make('span', 'research-agent-count', count === null ? '—' : String(count)),
      add(make('span', 'research-agent-caption'), make('span', '', 'Agents assisting'), make('small', 'quiet', agentNote)));
    toggle.setAttribute('aria-label', 'Agents assisting: ' + (count === null ? agentNote : count + '. ' + agentNote) + '. Show roles');
    team.append(toggle);
    const roles = make('ul', 'research-agent-roles');
    const roleNames = {investigate:'Investigator', synthesize:'Synthesis', review:'Independent reviewer'};
    for (const agent of array(agents?.active)) roles.append(make('li', '', (agent.section === 'final' || agent.stream === 'final' ? 'Final brief author' : roleNames[agent.phase] || 'Research agent') + (agent.stream ? ' · ' + agent.stream : '') + (agent.status === 'termination-unconfirmed' ? ' · termination unconfirmed' : '')));
    if (!roles.childNodes.length) roles.append(make('li', '', count === null ? 'Live agent activity is not available for this saved run.' : 'No agents are currently working.'));
    team.append(roles); header.append(team);
    const actions = hooks.controls || make('div', 'bar');
    for (const [key, label] of [['pause', 'Pause research'], ['resume', 'Resume research'], ['stop', 'Stop research'], ['retry', 'Retry affected area'], ['report', 'Open report'], ['brief', 'Open brief'], ['use', 'Use research']]) if (hooks[key]) actions.append(button(label, hooks[key], 'research-' + key));
    if (actions.childNodes.length) header.append(actions);
    box.append(header);
    if (phase === 'creator-approved') return add(box, make('p', '', 'Your choices are saved in the research report. Warnings appear only where you requested them.'));
    const draft = workingDraft(state);
    if (draft) {
      const reader = make('details', 'research-correction-details'); reader.dataset.key = 'research-working-draft';
      const toggle = make('summary', '', 'Read working draft · ' + draft.rows.length + (draft.rows.length === 1 ? ' section available' : ' sections available')); toggle.dataset.key = 'research-working-draft-toggle';
      add(reader, toggle, make('p', 'quiet', 'Incomplete, unreviewed research prose. This is not a finished learner guide or approved material.'));
      for (const row of draft.rows) for (const section of array(row.preview.sections)) {
        reader.append(make('h4', 'row-title', section.title));
        for (const text of String(section.text || '').split('\n\n')) reader.append(make('p', '', text));
        if (row.preview.truncated) reader.append(make('p', 'quiet', 'Preview shortened; the complete contribution remains saved.'));
      }
      const download = button('Download working draft (.md)', () => {
        const url = URL.createObjectURL(new Blob([draft.text], {type:'text/markdown;charset=utf-8'}));
        const link = make('a'); link.href = url; link.download = 'working-research-draft.md';
        document.body.append(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }, 'research-working-draft-download');
      box.append(add(make('div', 'bar'), download), reader);
    }
    if (state.review_coverage && phase === 'check-incomplete') {
      box.append(make('p', 'research-progress-note', state.review_coverage.read + ' of ' + state.review_coverage.total + ' required sources checked. The check stopped before finishing; unread does not mean incorrect. Evidence and drafts are kept. Retry repeats the independent check, not research or writing.'));
    }
    const steps = make('ol', 'research-stages'); steps.setAttribute('aria-label', 'Research stages');
    for (const [index, label] of ['Gather evidence', 'Combine findings', 'Check sources'].entries()) {
      const item = add(make('li'), make('span', 'research-stage-name', label),
        make('small', 'research-stage-state', stage > index ? 'Complete' : stage === index ? (incomplete ? 'Incomplete' : 'Working now') : 'Still to do'));
      item.dataset.state = stage > index ? 'done' : stage === index ? 'current' : 'waiting';
      if (stage === index) item.setAttribute('aria-current', 'step');
      item.setAttribute('aria-label', label + ': ' + (stage > index ? 'complete' : stage === index ? (incomplete ? 'incomplete' : 'in progress') : 'not completed'));
      steps.append(item);
    }
    box.append(steps);
    if (state.correction && !['complete','ready-for-review'].includes(phase)) {
      const correction = make('section', 'research-correction');
      const round = Number.isInteger(state.round) ? state.round : 1;
      add(correction, make('p', 'research-correction-title', 'Correction round ' + round + (state.round_limit ? ' of ' + state.round_limit : '')),
        make('p', '', array(state.correction.areas).length ? 'The independent check requested changes in ' + state.correction.areas.length + ' research areas. Other collected evidence is kept.' : 'The independent check requested changes to the report. Collected evidence is kept; sources are not being researched again.'));
      const notes = array(state.correction.notes);
      if (notes.length) {
        const why = make('details', 'research-correction-details'); why.dataset.key = 'research-correction';
        const whyToggle = make('summary', '', 'Why another round?'); whyToggle.dataset.key = 'research-correction-toggle';
        const list = make('ul'); for (const note of notes) list.append(make('li', '', note));
        add(why, whyToggle, list); correction.append(why);
      }
      box.append(correction);
    }
    const evidenceRows=array(state.streams).filter(row=>row.status==='kept'&&row.evidence);
    if(evidenceRows.length&&!['stopped','stopping','paused','pausing','invalidated'].includes(phase)){
      const evidence=make('details','research-correction-details');evidence.dataset.key='research-evidence';
      const toggle=make('summary','',phase==='complete'?'Earlier investigator evidence':'Read accepted findings — unreviewed');toggle.dataset.key='research-evidence-toggle';evidence.append(toggle);
      evidence.append(make('p','field-label',phase==='complete'?'Superseded by the checked research report.':'Unreviewed evidence draft — incomplete; synthesis and independent check pending.'));
      evidence.append(make('p','quiet','Read-only accepted packets. '+(array(state.streams).length-evidenceRows.length)+' research areas remain without a readable accepted packet. These findings cannot be approved or delivered as a final report.'));
      for(const row of evidenceRows){
        const value=row.evidence,part=make('section','paper research-section-preview');
        part.append(make('h4','row-title',array(row.questions).map(q=>typeof q==='string'?q:q.question||q.text||q.id).join('; ')));
        part.append(make('p','quiet','Source basis '+String(value.basis).slice(0,12)+' · generation '+value.generation+' · attempt '+value.attempt));
        for(const fact of array(value.facts)){
          part.append(make('p','',fact.statement));
          for(const citation of array(fact.citations)){const source=array(value.sources).find(s=>s.id===citation.source);part.append(make('p','quiet',(source?source.title: citation.source)+': '+citation.quote+(citation.locator?' — '+citation.locator:'')));}
        }
        for(const source of array(value.sources))part.append(make('p','quiet','Source: '+source.title+' · '+source.origin+' · '+source.permission+' · '+source.context+(source.context_note?' — '+source.context_note:'')));
        for(const limitation of array(value.limitations))part.append(make('p','quiet','Limitation: '+limitation));
        if(value.truncated)part.append(make('p','quiet','Preview shortened; the complete accepted evidence is retained.'));
        evidence.append(part);
      }
      box.append(evidence);
      if(Number.isFinite(state.first_finding_seconds))box.append(make('p','quiet','First accepted finding readable at '+state.first_finding_seconds+' seconds.'));
    }
    const combining = array(state.combining);
    if (combining.length) {
      const keptDrafts = combining.filter(row => row.status === 'kept').length;
      const details = make('details', 'research-correction-details'); details.dataset.key = 'research-combining';
      const summary = make('summary', '', phase==='complete'?'Earlier drafts and queued notes':keptDrafts + ' of ' + combining.length + ' section drafts kept');
      summary.dataset.key = 'research-combining-toggle'; details.append(summary);
      const list = make('ul');
      for (const row of combining) {
        if(phase==='complete'&&!row.preview)continue;
        const item=make('li','',array(row.questions).map(q => typeof q === 'string' ? q : q.question || q.text || q.id).join('; ') + ' · ' + (phase==='complete'?'Earlier draft':row.status === 'kept' ? 'Draft kept' : row.status === 'working' ? 'Combining' : row.status === 'failed' ? 'Retry needed' : 'Waiting'));
        if(row.preview){
          const preview=make('details','paper research-section-preview');preview.dataset.key='research-preview-'+row.id;
          const toggle=make('summary','',phase==='complete'?'Earlier section draft and queued note':'Read saved section draft');toggle.dataset.key='research-preview-toggle-'+row.id;preview.append(toggle);
          add(preview,make('p','field-label',phase==='complete'?'Superseded by the checked research report.':'Draft—independent check pending'),make('p','quiet','Read-only saved prose for this approved section. Not eligible for final delivery. Revision '+String(row.preview.basis).slice(0,12)+'.'));
          for(const section of array(row.preview.sections)){preview.append(make('h4','row-title',section.title));for(const text of String(section.text||'').split('\n\n'))preview.append(make('p','',text));}
          if(row.preview.truncated)preview.append(make('p','quiet','Preview shortened; the complete saved draft is retained.'));
          preview.append(make('p','quiet','Sources: '+array(row.preview.sources).map(source=>source.title+' ('+source.permission+')').join('; ')+'. Preview adds no sources or permissions.'));
          preview.append(...[noteEditor(row,hooks)].filter(Boolean));item.append(preview);
        }
        list.append(item);
      }
      details.append(list); box.append(details);
      if(Number.isFinite(state.first_readable_seconds))box.append(make('p','quiet','First saved section readable at '+state.first_readable_seconds+' seconds'+(Number.isFinite(state.checked_result_seconds)?'; checked result at '+state.checked_result_seconds+' seconds.':'; final independent check still pending.')));
      if (phase !== 'complete') box.append(make('p', 'quiet', 'Section drafts are kept for retry. The assembled research still needs its independent check.'));
    }
    const areas = array(state.streams || state.workstreams);
    const kept = areas.filter(a => ['kept', 'accepted'].includes(a.status)).length;
    const working = areas.filter(a => ['running', 'working'].includes(a.status)).length;
    const failed = areas.filter(a => ['failed', 'refused'].includes(a.status)).length;
    const activity = phase === 'creator-review' ? 'The draft and independent-check notes are saved. Choose what to include, include with a warning, or exclude; no correction loop is running.' : phase === 'creator-approved' ? 'The creator decided which flagged content to use. The saved report follows those choices.' : incomplete ? 'The check did not finish reading its required sources. Evidence and draft prose are retained; no correction round was started.' : stage === 0 ? (count > 0 ? count + (count === 1 ? ' investigator is' : ' investigators are') + ' reading sources and checking the research questions.' : 'Preparing the remaining investigations. Collected evidence is kept.') : stage === 1 ? (assembling ? 'Section drafts are saved. One author is assembling the final brief; no new research is needed for this step.' : 'Evidence collection is complete. Section authors are writing the working draft; saved sections are readable now.') : stage === 2 ? 'The independent reviewer is checking the report and brief against the captured sources. Research is not finished until this check passes.' : stage === 3 ? 'The report and reference brief have passed the independent source check.' : phase === 'needs-revision' ? 'The independent check requested corrections. Collected evidence is kept while the affected work is revised.' : 'Collected evidence is kept. Continue when you are ready.';
    const next = phase === 'creator-review' ? 'Next: choose flagged content, or explicitly request one correction attempt.' : phase === 'creator-approved' ? 'Next: continue when ready to review the report and create materials.' : incomplete ? 'Next: resolve the checking limit or source-access problem, then retry the independent check.' : stage === 0 ? 'Still to do: combine the findings, then run an independent source check.' : stage === 1 ? 'Still to do: independently check the finished report and brief.' : stage === 2 ? 'Next: hand the checked research back to the studio. Any required corrections will be explained here.' : stage === 3 ? 'The studio can now use the checked research.' : 'Next: resume the remaining work from the saved evidence.';
    box.append(add(make('div', 'research-current-activity'), make('p', 'research-progress-note', activity), make('p', 'quiet research-next', next)));
    // What each assistant working now is doing: its latest line and Show activity (activity.js),
    // whose lines `hooks.lines(id, since)` reads while it is open.
    const doing = typeof StudioActivity !== 'undefined' ? StudioActivity.live(hooks.workers, {title: 'What the assistant is doing', load: hooks.lines}) : null;
    if (doing) box.append(doing);
    if (areas.length) {
      const status = make('p', 'research-progress-summary', kept + ' of ' + areas.length + ' areas collected' + (working ? ' · ' + working + ' working' : '') + (failed ? ' · ' + failed + ' need retry' : ''));
      status.setAttribute('role', 'status'); box.append(status);
      if (stage === 0) {
        const meter = make('progress', 'research-evidence-meter'); meter.max = areas.length; meter.value = kept;
        meter.setAttribute('aria-label', 'Research areas with collected evidence'); box.append(meter);
      }
      const list = make('ul', 'research-areas');
      const words = {kept: 'Evidence kept', accepted: 'Evidence kept', waiting: 'Waiting', pending: 'Waiting', running: 'Working', working: 'Working', failed: 'Needs retry', refused: 'Needs retry', cancelled: 'Stopped', 'termination-unconfirmed': 'Waiting for termination confirmation'};
      for (const [index, area] of areas.entries()) {
        const questions = array(area.questions).map(q => typeof q === 'string' ? q : q.question || q.text || q.id).filter(Boolean);
        const item = make('li', 'research-area');
        item.dataset.state = ['kept','accepted'].includes(area.status) ? 'done' : ['failed','refused','termination-unconfirmed'].includes(area.status) ? 'review' : ['running','working'].includes(area.status) ? 'current' : 'none';
        const mark = make('span', 'bead'); mark.dataset.state = item.dataset.state; mark.setAttribute('aria-hidden', 'true');
        add(item, add(make('p', 'state research-area-state'), mark, make('span', '', words[area.status] || 'Status unavailable')),
          make('p', 'research-area-question', area.title || questions[0] || 'Preparing this investigation'));
        if (questions.length) {
          const detail = make('details', 'research-area-details'); detail.dataset.key = 'research-area-' + (area.id || index);
          const toggle = make('summary', '', questions.length === 1 ? 'View question' : 'View ' + questions.length + ' questions'); toggle.dataset.key = detail.dataset.key + '-toggle';
          const full = make('ul', 'research-questions'); for (const question of questions) full.append(make('li', '', question));
          item.append(add(detail, toggle, full));
        }
        list.append(item);
      }
      if (stage === 1 || stage === 2) {
        const collected = make('details', 'research-collected'); collected.dataset.key = 'research-collected';
        const toggle = make('summary', '', 'View collected evidence'); toggle.dataset.key = 'research-collected-toggle';
        add(collected, toggle, list); box.append(collected);
      } else box.append(list);
    }
    const timing = hooks.timing || state.timing;
    if (timing) {
      const duration = value => { const seconds = Math.max(0, Math.round(value)); if (seconds < 60) return seconds + (seconds === 1 ? ' second' : ' seconds'); const minutes = Math.round(seconds / 60); return minutes + (minutes === 1 ? ' minute' : ' minutes'); };
      const elapsed = timing.elapsed_seconds, active = timing.active_wall_seconds ?? timing.active_seconds;
      add(box, make('p', 'quiet research-timing', [elapsed != null ? duration(elapsed) + ' elapsed' : '', active != null ? duration(active) + ' actively working' : 'Active time awaiting terminal confirmation'].filter(Boolean).join(' · ')));
      const details = make('details', 'research-options'); details.dataset.key = 'research-timing';
      const toggle = make('summary', '', 'Timing details'); toggle.dataset.key = 'research-timing-toggle'; details.append(toggle);
      if (timing.assistant_seconds != null) details.append(make('p', 'quiet', duration(timing.assistant_seconds) + ' total assistant time'));
      details.append(make('p', 'field-hint', 'Elapsed includes waiting; assistant time adds overlapping jobs. Dollar cost is shown only when reported.'));
      box.append(details);
    }
    return box;
  }
  function impact(plan, selected) {
    if (!plan) return null;
    const ids = selected || new Set(array(plan.sections).map(row => row.id));
    const box = make('section', 'paper stack'); box.setAttribute('aria-label', 'Affected work preview');
    add(box, make('h3', 'card-title', 'Review affected work'), make('p', 'quiet', plan.reuse_note));
    const inputs = array(plan.changed_inputs);
    box.append(make('p', '', inputs.length ? inputs.map(row => row.name + ' · ' + row.kind).join('; ') : 'Refreshing existing evidence may change every section.'));
    for (const row of array(plan.sections)) {
      if (row.required) ids.add(row.id);
      const label = check(row.title + (row.required ? ' · Required' : ''), ids.has(row.id), on => on ? ids.add(row.id) : ids.delete(row.id), 'impact-' + row.id);
      label.querySelector('input').disabled = !!row.required;
      box.append(label);
    }
    box.append(make('p', 'quiet', 'Unselected evidence and drafts stay reusable. Only dependent material sections and slide drawings need changes; wording or notes edits do not collect evidence.'));
    if (array(plan.outputs).length) {
      const outputs = make('ul');
      for (const row of plan.outputs) outputs.append(make('li', '', typeof row === 'string' ? row : row.name + ' · ' + row.scope));
      box.append(outputs);
    }
    box.append(make('p', 'field-hint', plan.final_check));
    return {node: box, selected: ids, value: () => ({expected: plan.expected, sections: [...ids]})};
  }
  return {Editor, progress, summary, impact, workingDraft, linksIn, linksInFile};
})();
if (typeof module === 'object' && module.exports) module.exports = StudioResearch;
