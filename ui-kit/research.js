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
      try { this.value = await this.a.request(this.value ? {action: 'read', id: this.value.id} : {action: 'create'}); this.problem = ''; }
      catch (error) { this.problem = message(error); }
      finally { this.busy = false; this.render(); this.changed(); }
    }
    changed() { if (this.a.onChange) this.a.onChange(this.value); }
    async act(action, data = {}) {
      if (this.busy || !this.value) return false;
      this.busy = true; this.problem = ''; this.reading = action === 'capture' || action === 'tabs' ? 'Reading source…' : 'Saving source choices…'; this.render();
      try { this.value = await this.a.request({action, id: this.value.id, expected: this.value.revision, ...data}); return true; }
      catch (error) { this.problem = message(error); return false; }
      finally { this.busy = false; this.reading = ''; this.render(); this.changed(); }
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
    const titles = {investigate: 'Collecting evidence', 'investigating': 'Collecting evidence', synthesize: 'Combining findings', 'combining-findings': 'Combining findings', review: 'Independent check', 'independent-check': 'Independent check', complete: 'Research is ready', 'ready-for-review': 'Research is ready', 'needs-attention': 'Research needs attention', 'needs-revision': 'Research needs correction', 'stopping': 'Stopping research', 'pausing': 'Finishing active research before pausing', paused: 'Research paused', stopped: 'Research stopped'};
    const box = make('section', 'research-progress paper'); box.setAttribute('aria-label', 'Research progress');
    const stage = {investigate:0, investigating:0, synthesize:1, 'combining-findings':1, review:2, 'independent-check':2, complete:3, 'ready-for-review':3}[phase];
    const heading = add(make('div', 'research-progress-heading'),
      make('p', 'quiet research-stage-label', stage < 3 ? 'Research · Stage ' + (stage + 1) + ' of 3' : stage === 3 ? 'Research complete' : 'Research progress'),
      make('h3', 'card-title', titles[phase] || 'Research'));
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
    const agentNote = count === null ? (agents?.unconfirmed ? 'Awaiting confirmation' : 'Count unavailable') : count === 0 ? (['complete','ready-for-review'].includes(phase) ? 'All agents finished' : ['paused','stopped'].includes(phase) ? 'Progress saved' : 'Preparing next step') : ['review','independent-check'].includes(phase) ? 'Independent review' : ['synthesize','combining-findings'].includes(phase) ? 'Combining findings' : 'Investigating sources';
    add(toggle, faces, make('span', 'research-agent-count', count === null ? '—' : String(count)),
      add(make('span', 'research-agent-caption'), make('span', '', 'Agents assisting'), make('small', 'quiet', agentNote)));
    toggle.setAttribute('aria-label', 'Agents assisting: ' + (count === null ? agentNote : count + '. ' + agentNote) + '. Show roles');
    team.append(toggle);
    const roles = make('ul', 'research-agent-roles');
    const roleNames = {investigate:'Investigator', synthesize:'Synthesis', review:'Independent reviewer'};
    for (const agent of array(agents?.active)) roles.append(make('li', '', (roleNames[agent.phase] || 'Research agent') + (agent.stream ? ' · ' + agent.stream : '') + (agent.status === 'termination-unconfirmed' ? ' · termination unconfirmed' : '')));
    if (!roles.childNodes.length) roles.append(make('li', '', count === null ? 'Live agent activity is not available for this saved run.' : 'No agents are currently working.'));
    team.append(roles); header.append(team);
    const actions = hooks.controls || make('div', 'bar');
    for (const [key, label] of [['pause', 'Pause research'], ['resume', 'Resume research'], ['stop', 'Stop research'], ['retry', 'Retry affected area'], ['report', 'Open report'], ['brief', 'Open brief'], ['use', 'Use research']]) if (hooks[key]) actions.append(button(label, hooks[key], 'research-' + key));
    if (actions.childNodes.length) header.append(actions);
    box.append(header);
    const steps = make('ol', 'research-stages'); steps.setAttribute('aria-label', 'Research stages');
    for (const [index, label] of ['Gather evidence', 'Combine findings', 'Check sources'].entries()) {
      const item = add(make('li'), make('span', 'research-stage-name', label),
        make('small', 'research-stage-state', stage > index ? 'Complete' : stage === index ? 'Working now' : 'Still to do'));
      item.dataset.state = stage > index ? 'done' : stage === index ? 'current' : 'waiting';
      if (stage === index) item.setAttribute('aria-current', 'step');
      item.setAttribute('aria-label', label + ': ' + (stage > index ? 'complete' : stage === index ? 'in progress' : 'not completed'));
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
    const areas = array(state.streams || state.workstreams);
    const kept = areas.filter(a => ['kept', 'accepted'].includes(a.status)).length;
    const working = areas.filter(a => ['running', 'working'].includes(a.status)).length;
    const failed = areas.filter(a => ['failed', 'refused'].includes(a.status)).length;
    const activity = stage === 0 ? (count > 0 ? count + (count === 1 ? ' investigator is' : ' investigators are') + ' reading sources and checking the research questions.' : 'Preparing the remaining investigations. Collected evidence is kept.') : stage === 1 ? 'Evidence collection is complete. The synthesis agent is turning it into one report and reference brief.' : stage === 2 ? 'The independent reviewer is checking the report and brief against the captured sources. Research is not finished until this check passes.' : stage === 3 ? 'The report and reference brief have passed the independent source check.' : phase === 'needs-revision' ? 'The independent check requested corrections. Collected evidence is kept while the affected work is revised.' : 'Collected evidence is kept. Continue when you are ready.';
    const next = stage === 0 ? 'Still to do: combine the findings, then run an independent source check.' : stage === 1 ? 'Still to do: independently check the finished report and brief.' : stage === 2 ? 'Next: hand the checked research back to the studio. Any required corrections will be explained here.' : stage === 3 ? 'The studio can now use the checked research.' : 'Next: resume the remaining work from the saved evidence.';
    box.append(add(make('div', 'research-current-activity'), make('p', 'research-progress-note', activity), make('p', 'quiet research-next', next)));
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
  return {Editor, progress, summary};
})();
if (typeof module === 'object' && module.exports) module.exports = StudioResearch;
