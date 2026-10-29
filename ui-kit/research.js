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

  class Editor {
    constructor(adapter) {
      this.a = adapter;
      this.value = adapter.value || null;
      this.urls = ''; this.text = ''; this.name = 'Pasted notes'; this.busy = false; this.problem = ''; this.reading = '';
      this.node = make('section', 'research-source-editor stack');
      this.node.setAttribute('aria-label', adapter.label || 'Research sources');
      this.render();
      if (!this.value) this.load();
    }
    async load() {
      if (this.busy) return;
      this.busy = true; this.render();
      try { this.value = await this.a.request(this.value ? {action: 'read', id: this.value.id} : {action: 'create'}); this.problem = ''; this.changed(); }
      catch (error) { this.problem = message(error); }
      finally { this.busy = false; this.render(); }
    }
    changed() { if (this.a.onChange) this.a.onChange(this.value); }
    async act(action, data = {}) {
      if (this.busy || !this.value) return false;
      this.busy = true; this.problem = ''; this.reading = action === 'capture' || action === 'tabs' ? 'Reading source…' : 'Saving source choices…'; this.render();
      try { this.value = await this.a.request({action, id: this.value.id, expected: this.value.revision, ...data}); this.changed(); return true; }
      catch (error) { this.problem = message(error); return false; }
      finally { this.busy = false; this.reading = ''; this.render(); }
    }
    async links() {
      const links = this.urls.trim().split(/\s+/).filter(Boolean);
      if (!links.length) { this.problem = 'Paste one or more links first.'; this.render(); return; }
      for (const url of links) {
        let parsed; try { parsed = new URL(url); } catch (_) { this.problem = 'Check this link: ' + url; this.render(); return; }
        if (parsed.protocol !== 'https:' || parsed.username || parsed.password) { this.problem = 'Use HTTPS links without embedded credentials.'; this.render(); return; }
      }
      for (const url of links) {
        if (!await this.act('capture', {kind: 'url', url})) break;
        this.urls = this.urls.split(/\s+/).filter(v => v && v !== url).join('\n');
      }
      this.render();
    }
    async files(files) {
      for (const file of Array.from(files || [])) {
        if (file.size > 8_000_000) { this.problem = file.name + ': choose a source within 8 MB.'; this.render(); continue; }
        const bytes = new Uint8Array(await file.arrayBuffer()); let binary = '';
        for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
        if (!await this.act('capture', {kind: 'file', name: file.name, content: btoa(binary)})) break;
      }
    }
    spec() { return this.value ? {id: this.value.id, expected: this.value.revision} : null; }
    valid(hasPrimary = false) {
      return !!this.value && !this.busy && !this.problem && array(this.value.sources).every(s => ['ready', 'excluded'].includes(s.status))
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
    render() {
      const focused = this.node.contains(document.activeElement) ? document.activeElement.dataset.key : '';
      if (focused) this.focused = focused;
      const restore = focused || (document.activeElement === document.body ? this.focused : '');
      const opened = Array.from(this.node.querySelectorAll('details[open][data-key]')).map(n => n.dataset.key);
      const scroll = this.node.scrollTop;
      this.node.replaceChildren();
      const state = this.value;
      const panel = make('div', 'research-sources paper');
      add(panel, make('h3', 'card-title', this.a.label || 'Your sources'));
      if (this.a.primarySummary) panel.append(make('p', 'quiet', this.a.primarySummary));
      const links = field('Web pages or Google Docs links', this.urls, 'research-urls', true);
      links.input.placeholder = 'Paste one or several links'; links.input.addEventListener('input', () => this.urls = links.input.value);
      add(links.wrap, make('p', 'field-hint', 'Uses your existing Google sign-in and shared defaults.'));
      const addLinks = button('Add links', () => this.links(), 'research-add-links');
      add(panel, add(make('div', 'research-link-entry'), links.wrap, addLinks));
      const file = make('input'); file.type = 'file'; file.multiple = true; file.hidden = true;
      file.accept = '.pdf,.docx,.txt,.md,.markdown,.html,.htm'; file.addEventListener('change', () => this.files(file.files));
      const actions = add(make('div', 'bar'), button('Choose files', () => file.click(), 'research-files'),
        button(this.pasting ? 'Close pasted text' : 'Paste text', () => { this.pasting = !this.pasting; this.render(); }, 'research-paste'));
      actions.append(button('Use saved research', async () => {
        if (this.a.savedResearch) return this.a.savedResearch(this);
        try { this.saved = await this.a.request({action:'saved'}); this.render(); }
        catch(error) { this.problem=message(error); this.render(); }
      }, 'research-saved'));
      add(panel, actions, file);
      if (this.pasting) {
        const name = field('Source name', this.name, 'research-text-name'); name.input.addEventListener('input', () => this.name = name.input.value);
        const text = field('Source text', this.text, 'research-text', true); text.input.rows = 6; text.input.addEventListener('input', () => this.text = text.input.value);
        add(panel, name.wrap, text.wrap, button('Add text', async () => { if (await this.act('capture', {kind: 'text', name: this.name, text: this.text})) { this.text = ''; this.pasting = false; this.render(); } }, 'research-add-text'));
      }
      const list = make('ul', 'research-source-list'); for (const source of array(state && state.sources)) list.append(this.source(source));
      if (!state || !state.sources.length) list.append(make('li', 'quiet', state ? 'Add material here, or allow external search below.' : 'Loading the source draft…'));
      add(panel, list); this.node.append(panel);
      if (this.saved) {
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
        add(policy, check('Search for additional external sources', state.external, external => this.act('configure', {external}), 'research-external'),
          make('p', 'field-hint', summary(state)));
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
      for (const control of this.node.querySelectorAll('button, input, textarea, select')) control.disabled = this.busy || !state;
      if (this.problem) { const reload = Array.from(this.node.querySelectorAll('button')).find(n => n.dataset.key === 'research-reload'); if (reload) reload.disabled = this.busy; }
      for (const detail of this.node.querySelectorAll('details[data-key]')) detail.open = opened.includes(detail.dataset.key);
      if (restore) { const target = Array.from(this.node.querySelectorAll('[data-key]')).find(n => n.dataset.key === restore); if (target && !target.disabled) target.focus(); }
      this.node.scrollTop = scroll;
    }
  }

  function progress(state, hooks = {}) {
    if (!state) return null;
    const phase = state.phase || 'investigate';
    const titles = {investigate: 'Collecting evidence', 'investigating': 'Collecting evidence', synthesize: 'Combining findings', 'combining-findings': 'Combining findings', review: 'Independent check', 'independent-check': 'Independent check', complete: 'Research is ready', 'ready-for-review': 'Research is ready', 'needs-attention': 'Research needs attention', 'needs-revision': 'Research needs correction', 'stopping': 'Stopping research', paused: 'Research paused', stopped: 'Research stopped'};
    const box = add(make('section', 'research-progress paper'), make('h3', 'card-title', titles[phase] || 'Research'));
    const list = make('ul', 'research-source-list');
    for (const area of array(state.streams || state.workstreams)) {
      const label = array(area.questions).join(' · ') || area.title || area.id;
      const words = {kept: 'Evidence kept', accepted: 'Evidence kept', waiting: 'Waiting', pending: 'Waiting', running: 'Working', working: 'Working', failed: 'Needs retry', refused: 'Needs retry', cancelled: 'Stopped', 'termination-unconfirmed': 'Waiting for termination confirmation'};
      list.append(add(make('li', 'research-area'), make('span', '', label), make('span', 'quiet', words[area.status] || area.status)));
    }
    add(box, list);
    const timing = hooks.timing || state.timing;
    if (timing) {
      const minutes = value => Math.round(value / 60) + ' minutes';
      const elapsed = timing.elapsed_seconds, active = timing.active_wall_seconds ?? timing.active_seconds;
      add(box, make('p', 'quiet', [elapsed != null ? minutes(elapsed) + ' elapsed' : '', active != null ? minutes(active) + ' actively working' : 'Active time awaiting terminal confirmation'].filter(Boolean).join(' · ')));
      const details = add(make('details', 'research-options'), make('summary', '', 'Research details'));
      if (timing.assistant_seconds != null) details.append(make('p', 'quiet', minutes(timing.assistant_seconds) + ' total assistant time'));
      details.append(make('p', 'field-hint', 'Elapsed includes waiting; assistant time adds overlapping jobs. Dollar cost is shown only when reported.'));
      box.append(details);
    }
    const actions = make('div', 'bar');
    for (const [key, label] of [['pause', 'Pause research'], ['resume', 'Resume research'], ['stop', 'Stop research'], ['retry', 'Retry affected area'], ['report', 'Open report'], ['brief', 'Open brief'], ['use', 'Use research']]) if (hooks[key]) actions.append(button(label, hooks[key], 'research-' + key));
    if (actions.childNodes.length) box.append(actions);
    return box;
  }
  return {Editor, progress, summary};
})();
if (typeof module === 'object' && module.exports) module.exports = StudioResearch;
