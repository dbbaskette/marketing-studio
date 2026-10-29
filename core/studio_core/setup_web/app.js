'use strict';
const $ = selector => document.querySelector(selector);
const standalone = document.body.dataset.standalone === 'true';
const product = document.body.dataset.product;
const tokenHeader = document.body.dataset.tokenHeader;
const sessionKey = standalone ? product.toLowerCase().replaceAll(' ', '-') + '-setup-token' : 'marketing-studio-token';
const launchOptions = new URLSearchParams(location.hash.slice(1));
const requestedView = launchOptions.get('view') === 'settings' ? 'settings' : 'home';
// The private key in a link's fragment: `token=…`, or for a standalone studio's setup the bare key.
function linkKey(hash, bare) {
  const fragment = String(hash).replace(/^#/, '');
  const first = fragment.split('&')[0];
  return new URLSearchParams(fragment).get('token') || (bare && /^[A-Za-z0-9_-]+$/.test(first) ? first : '');
}
const tokenInLink = linkKey(location.hash, standalone);
if (tokenInLink) { sessionStorage.setItem(sessionKey, tokenInLink); history.replaceState(null, '', location.pathname); }
const token = tokenInLink || sessionStorage.getItem(sessionKey) || '';
// A new link opened in a tab that already shows this page changes only the fragment, which
// does not reload it: after a restart the page would keep the old key. Start again with the new one.
window.addEventListener('hashchange', () => {
  const next = linkKey(location.hash, standalone);
  if (next && next !== token) location.reload();
});
// Studios opened from here link back to this tab by its name.
if (!standalone) window.name = 'marketing-studio';
function withHome(link, tab = false) {
  return link + (link.includes('#') ? '&' : '#') + 'home=' + encodeURIComponent(location.origin)
    + '&homeToken=' + encodeURIComponent(token) + (tab ? '&back=tab' : '');
}
// A phone cannot bring another tab forward, so a studio opens in this tab there and its way
// back returns to this tab, which still holds this page's key.
function inThisTab(media) {
  return media('(pointer: coarse)') || media('(max-width: 52rem)');
}
let snapshot, setup = false, step = 0, view = 'home', profileAgent;
const labels = ['You and your assistant', 'Your workspace', 'Brand and delivery'];  // announced
// Blog Studio's own setup: a blog on the writing desk has no stops and no slides.
const blogAlone = () => setup && standalone && ['Blog Studio', 'Infographic Studio'].includes(product);
const form = $('#settings-form');
const modelPickers = new Map(), catalogs = {};
const customModel = '__manual model__';
let modelRequest = 0;
const calm = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function inform(message, error = false) {
  if (error) { const node = $('#problem'); node.textContent = message; node.hidden = false; return; }
  // Toasts are timed as they are in every studio; anything with a link stays in #message.
  const node = element('p', message, 'toast glass'); $('#toasts').append(node);
  setTimeout(() => { node.classList.add('toast-leaving'); setTimeout(() => node.remove(), calm() ? 0 : 260); }, 4200);
}
async function api(path, body) {
  let response;
  try {
    response = await fetch(`${standalone ? "/onboarding" : ""}/api/${path}`, { method: body === undefined ? 'GET' : 'POST',
      headers: { [tokenHeader]: token, ...(body === undefined ? {} : {'Content-Type': 'application/json'}) },
      ...(body === undefined ? {} : {body: JSON.stringify(body)}) });
  } catch (error) {
    throw new Error(`This page has lost touch with ${product}, so it cannot read or save anything. Run ${standalone ? 'the studio command' : 'marketing-studio'} again in your terminal and use the new link.`);
  }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'This request could not be completed.');
  return result;
}
function syncSegments() {
  for (const group of form.querySelectorAll('.segmented')) {
    const options = [...group.querySelectorAll('input[type="radio"]')];
    group.dataset.at = String(Math.max(0, options.findIndex(option => option.checked)));
  }
}
function element(tag, text, className) {
  const node = document.createElement(tag); if (text) node.textContent = text;
  if (className) node.className = className; return node;
}
function stateLine(kind, text) {
  const node = element('span', '', 'state'), mark = element('span', '', 'bead');
  mark.dataset.state = kind; mark.setAttribute('aria-hidden', 'true');
  node.append(mark, element('span', text)); return node;
}
function show(next) {
  window.scrollTo(0, 0);
  const previousView=view;
  view = setup ? 'settings' : next;
  if(view==='home'&&previousView!=='home'&&snapshot)void refreshHomeStatus();
  for (const name of ['loading', 'home', 'settings', 'computer']) $(`#${name}`).hidden = name !== view;
  $('#view-title').textContent = setup ? `Welcome to ${product}` : ({home: 'Studios', settings: 'Shared settings', computer: 'This computer'})[view];
  document.querySelectorAll('[data-view]').forEach(button => {
    if (button.classList.contains('nav-item')) {
      if (button.dataset.view === view && !setup) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    }
  });
  // Before setup, and in a studio's own setup, there is one screen and no sidebar to leave it by.
  document.querySelector('.sidebar').hidden = setup || standalone;
  document.body.classList.toggle('alone', setup || standalone);
  $('#back-to-studio').hidden = !(standalone && !setup);
  $('#back-to-studio').textContent = `Back to ${product}`;
  // In setup the numbered list names the step, and the step's card is titled with it.
  $('#settings-title').textContent = 'Shared settings';
  $('#settings-title').hidden = setup;
  $('#settings-intro').textContent = setup ? 'Set up once, and every studio starts with these choices.' : 'New work in every studio starts with these choices.';
  $('#step-label').textContent = '';
  $('#step-label').hidden = true;
  // This computer's one action is its toolbar's.
  $('#check').hidden = view !== 'computer';
  $('#setup-progress').hidden = !setup;
  $('#setup-progress').querySelectorAll('li').forEach((node, index) => {
    if (index === step) node.setAttribute('aria-current', 'step'); else node.removeAttribute('aria-current');
  });
  form.querySelectorAll('[data-step]').forEach(section => { section.hidden = setup && Number(section.dataset.step) !== step; });
  // Blog Studio's own first run asks only what Blog Studio uses.
  $('#delivery-part').hidden = blogAlone() || (setup && step !== 2);
  $('#back').hidden = !setup || step === 0;
  $('#save').textContent = setup ? (step === 2 ? 'Finish setup' : 'Continue') : 'Save settings';
  $('#installations').hidden = setup || standalone;
  if (standalone) {
    $('#prepare-note').textContent = 'Finish setup prepares this studio. Other studios will use these settings when you open them.';
    $('#save').textContent = setup && step < 2 ? 'Continue' : `Save and open ${product}`;
  }
  $('#prepare-note').hidden = !setup || step !== 2;
  if (view === 'settings' && (!setup || step === 0)) loadModels();
  // As in every studio, focus moves to the toolbar title. The step is announced.
  if (snapshot) $('#view-title').focus({preventScroll: true});
  // A moment after the focus move, so a screen reader does not drop it behind the title.
  setTimeout(() => { $('#announce').textContent = setup ? `Step ${step + 1} of 3: ${labels[step]}` : ''; }, 150);
}
function efforts(selected) {
  profileLevels(form.elements['assistant.effort'], selected, form.elements['assistant.model'].value);
}
function catalogModel(value) {
  return catalogs[form.elements['assistant.agent'].value]?.models.find(model => model.name === value);
}
function modelPicker(input, title) {
  const select = element('select', '', 'input');
  const named = input.id ? document.querySelector(`label[for="${input.id}"]`) : null;
  if (named) { select.id = `${input.id}-choice`; named.htmlFor = select.id; } else select.setAttribute('aria-label', title);
  if (input.getAttribute('aria-describedby')) select.setAttribute('aria-describedby', input.getAttribute('aria-describedby'));
  input.setAttribute('aria-label', `Custom model ID for ${title}`);
  input.before(select);
  const picker = {select, input, title, manual: false}; modelPickers.set(input.name, picker);
  select.addEventListener('change', () => {
    picker.manual = select.value === customModel;
    if (!picker.manual) input.value = select.value;
    input.hidden = !picker.manual;
    if (picker.manual) input.focus();
    updateModelLevels(picker);
  });
  input.addEventListener('input', () => updateModelLevels(picker));
  renderModelPicker(picker);
}
function updateModelLevels(picker) {
  const name = picker.input.name.replace(/model$/, 'effort');
  const effort = form.elements[name];
  if (effort && snapshot) profileLevels(effort, effort.value, picker.input.value);
}
function renderModelPicker(picker) {
  const {select, input} = picker, value = input.value;
  const entries = catalogs[form.elements['assistant.agent'].value]?.models || [];
  select.replaceChildren(new Option(input.name === 'assistant.model' ? 'Assistant’s default' : 'Choose a model…', ''));
  for (const model of entries) select.add(new Option(model.label || model.name, model.name));
  if (value && !entries.some(model => model.name === value)) select.add(new Option(`${value} (saved or custom)`, value));
  select.add(new Option('Enter a model ID…', customModel));
  select.value = picker.manual ? customModel : value;
  input.hidden = !picker.manual;
  updateModelLevels(picker);
}
function renderCatalogStatus(result) {
  $('#model-catalog-status').textContent = result.problem || (result.agent === 'claude'
    ? `${result.source}. Reference choices; availability depends on your account.`
    : `${result.source}. You can also enter a model ID.`);
}
async function loadModels(refresh = false) {
  const agent = form.elements['assistant.agent'].value;
  if (!refresh && catalogs[agent]) { renderCatalogStatus(catalogs[agent]); return; }
  const request = ++modelRequest;
  $('#refresh-models').disabled = true;
  $('#model-catalog-status').textContent = 'Loading model choices… You can keep working.';
  try {
    const result = await api(refresh ? 'models' : `models?agent=${encodeURIComponent(agent)}`, refresh ? {agent} : undefined);
    if (request !== modelRequest || agent !== form.elements['assistant.agent'].value) return;
    catalogs[agent] = result;
    for (const picker of modelPickers.values()) renderModelPicker(picker);
    renderCatalogStatus(result);
  } catch (error) {
    if (request !== modelRequest) return;
    $('#model-catalog-status').textContent = 'Model choices could not be loaded. Your selections are kept; use Enter a model ID or Refresh models.';
  } finally { if (request === modelRequest) $('#refresh-models').disabled = false; }
}
function validateModelChoices() {
  for (const picker of modelPickers.values()) {
    const name = picker.input.name;
    if (name.startsWith('models.') && (form.elements['models.mode'].value !== 'by_task'
      || form.elements[name.replace(/model$/, 'selection')].value !== 'explicit')) continue;
    const model = catalogModel(picker.input.value), effort = form.elements[name.replace(/model$/, 'effort')].value;
    if (model && effort && !model.levels.includes(effort)) throw new Error(`Choose a supported reasoning level for ${picker.title}, or use the assistant’s default.`);
  }
}

function storage() {
  const local = form.elements.storage.value === 'local';
  $('#local-fields').hidden = !local; $('#remote-fields').hidden = local;
  syncSegments();
}
function fill() {
  const shared = snapshot.shared;
  for (const input of form.querySelectorAll('input[name], select[name]')) {
    if (input.name === 'storage' || input.name === 'assistant.effort' || input.name.startsWith('models.')) continue;
    const keys = input.name.split('.'); let value = keys.length === 2 ? shared[keys[0]]?.[keys[1]] : shared[keys[0]];
    value ??= ({'assistant.agent': 'claude', 'local.root': '~/Studios', 'team.branch': 'main', output: 'pptx', share: 'decision'})[input.name] || '';
    input.value = value;
  }
  form.elements.storage.value = shared.team?.repository ? 'remote' : 'local';
  researchSites = [...(shared.research?.sites || [])]; renderSites();
  efforts(shared.assistant?.effort); storage(); fillProfiles();
  for (const picker of modelPickers.values()) renderModelPicker(picker);
}
// Research sites: canonical https://host[/path], shown as host/path. Each site is checked
// by the server when it is added (core/studio_core/research_sites.py), and again on save:
// one rule everywhere.
let researchSites = [];
const MOST_SITES = 50;
function siteShown(site) { return site.replace(/^https:\/\//, ''); }
function renderSites() {
  const list = $('#research-site-list'); list.replaceChildren();
  researchSites.forEach((site, index) => {
    const row = element('tr', '', 'site-row'), remove = element('button', 'Remove', 'button button-quiet');
    remove.type = 'button'; remove.setAttribute('aria-label', `Remove ${siteShown(site)}`);
    remove.addEventListener('click', () => {
      researchSites.splice(index, 1); renderSites();
      $('#research-site-hint').textContent = `${siteShown(site)} removed. Save settings to keep the list.`;
      (list.querySelectorAll('.site-row .button')[Math.min(index, researchSites.length - 1)] || $('#research-site-input')).focus();
    });
    const shown = element('td', siteShown(site)), action = element('td');
    shown.dataset.label = 'Site'; action.append(remove);
    row.append(shown, action); list.append(row);
  });
  $('#research-site-table').hidden = researchSites.length === 0;
  $('#research-site-empty').hidden = researchSites.length > 0;
}
async function addSite() {
  const input = $('#research-site-input'), button = $('#research-site-add');
  const typed = input.value.trim();
  if (!typed) { $('#research-site-hint').textContent = 'Type a site first, such as docs.example.com/guide.'; input.focus(); return; }
  button.disabled = true;
  try {
    const {site} = await api('research-site', {site: typed});
    if (researchSites.includes(site)) throw new Error(`${siteShown(site)} is already in your list.`);
    if (researchSites.length >= MOST_SITES) throw new Error(`Keep at most ${MOST_SITES} research sites.`);
    researchSites.push(site); renderSites(); input.value = '';
    $('#research-site-hint').textContent = `${siteShown(site)} added. Save settings to keep the list.`;
  } catch (error) { $('#research-site-hint').textContent = error.message; }
  finally { button.disabled = false; }
  input.focus();
}
$('#research-site-add').addEventListener('click', addSite);
$('#research-site-input').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); addSite(); } });
const profileNames = ['quick', 'main', 'complex'];
function profileLevels(select, selected, model = null) {
  const levels = catalogModel(model)?.levels || snapshot.efforts[form.elements['assistant.agent'].value];
  select.replaceChildren(new Option('Assistant’s default', ''));
  for (const level of levels) select.add(new Option(level, level));
  if (selected && !levels.includes(selected)) select.add(new Option(`${selected} (review for this model)`, selected));
  select.value = selected || '';
}
function profilesChanged() {
  const byTask = form.elements['models.mode'].value === 'by_task';
  $('#model-profiles').hidden = !byTask;
  $('#profile-review').hidden = !byTask || profileAgent === form.elements['assistant.agent'].value;
  for (const name of profileNames) {
    const explicit = form.elements[`models.${name}.selection`].value === 'explicit';
    document.querySelector(`[data-profile="${name}"] .profile-explicit`).hidden = !explicit;
  }
  syncSegments();
}
function fillProfiles() {
  profileAgent = snapshot.shared.models?.agent || form.elements['assistant.agent'].value;
  form.elements['models.mode'].value = snapshot.shared.models?.mode || 'single';
  const cards = $('#profile-cards'); cards.replaceChildren();
  const descriptions = {quick: 'Extraction and classification', main: 'Research, writing and slides', complex: 'Dedicated repair work'};
  for (const name of profileNames) {
    const saved = snapshot.shared.models?.profiles?.[name] || {};
    const title = name[0].toUpperCase() + name.slice(1);
    const card = element('fieldset', '', 'paper profile-card'); card.dataset.profile = name;
    card.append(element('legend', title, 'field-label'), element('p', descriptions[name], 'field-hint quiet'));
    const choice = element('div', '', 'field');
    const choiceLabel = element('label', `${title} model choice`, 'field-label'); choiceLabel.htmlFor = `models-${name}-selection`;
    const selection = element('select', '', 'input'); selection.id = choiceLabel.htmlFor; selection.name = `models.${name}.selection`;
    for (const [value, text] of [['inherit', 'Use shared model above'], ['provider_default', 'Assistant’s default'], ['explicit', 'Choose a model']]) selection.add(new Option(text, value));
    selection.value = saved.selection || 'inherit'; selection.addEventListener('change', profilesChanged);
    choice.append(choiceLabel, selection); card.append(choice);
    const fields = element('div', '', 'profile-explicit');
    const modelField = element('div', '', 'field'), modelLabel = element('label', `${title} model`, 'field-label');
    const input = element('input', '', 'input'); input.id = modelLabel.htmlFor = `models-${name}-model`;
    input.name = `models.${name}.model`; input.maxLength = 100; input.autocomplete = 'off'; input.value = saved.model || '';
    modelField.append(modelLabel, input);
    const effortField = element('div', '', 'field'), effortLabel = element('label', `${title} reasoning`, 'field-label');
    const effort = element('select', '', 'input'); effort.id = effortLabel.htmlFor = `models-${name}-effort`; effort.name = `models.${name}.effort`;
    profileLevels(effort, saved.effort, saved.model); effortField.append(effortLabel, effort);
    fields.append(modelField, effortField); card.append(fields); cards.append(card);
    modelPicker(input, `${title} model`);
  }
  profilesChanged();
}
form.querySelectorAll('[name="models.mode"]').forEach(input => input.addEventListener('change', profilesChanged));
$('#confirm-profiles').addEventListener('click', () => { profileAgent = form.elements['assistant.agent'].value; profilesChanged(); });
const drawings = {
  blog: 'M5 4h10l4 4v14H5zM14 4v5h5M8 13h8M8 17h6',
  presentation: 'M3 5h20v14H3zM13 19v5M8 24h10M7 14l4-4 4 3 4-5',
  training: 'm2 9 11-5 11 5-11 5zM6 12v7c4 3 10 3 14 0v-7M24 9v10',
  infographic: 'M4 3h18v22H4zM8 8h10M8 13h4M8 18h10M15 12v4h4v-4z'
};
// A studio's tile: ui-kit's .studio-symbol, in the card's studio colours, its drawing an svg.
function studioSymbol(id) {
  const tile = element('div', '', 'studio-symbol'); tile.setAttribute('aria-hidden', 'true');
  const space = 'http://www.w3.org/2000/svg', drawing = document.createElementNS(space, 'svg');
  for (const [name, value] of Object.entries({class: 'icon', viewBox: '0 0 26 28', fill: 'none', stroke: 'currentColor',
    'stroke-width': '1.6', 'stroke-linecap': 'round', 'stroke-linejoin': 'round'})) drawing.setAttribute(name, value);
  const line = document.createElementNS(space, 'path'); line.setAttribute('d', drawings[id] || '');
  drawing.append(line); tile.append(drawing); return tile;
}
// What a Connect action did, in one message that stays on the page.
function connectedWords(done) {
  const to = done.to?.repository ? `${done.to.repository} (${done.to.branch})` : `local Git at ${done.to?.root}`;
  if (done.already) return `${done.name} is already connected to ${to}.`;
  const counts = Object.entries(done.carried || {}).filter(([, count]) => count).map(([noun, count]) => `${count} ${count === 1 ? noun.replace(/s$/, '') : noun}`);
  let text = `${done.name} is connected to ${to}. ${counts.length ? `Carried over: ${counts.join(', ')}.` : 'There was nothing to carry over.'}`;
  if (done.left?.length) text += ` Left where it was: ${done.left.map(item => `${item.id} (${item.why})`).join('; ')}`;
  if (done.from?.root) text += ` Your earlier workspace stays at ${done.from.root}.`;
  if (done.notice) text += ` ${done.notice}`;
  if (done.stopped) text += ` ${done.name} was stopped to connect it; open it again.`;
  return text;
}
// What preparing the studios said that should stay on the page: a join whose first push was refused.
function showNotices() {
  const studioName = id => snapshot.studios.find(studio => studio.id === id)?.name || id;
  const notices = Object.entries(snapshot.prepared || {}).filter(([, result]) => result.notice).map(([id, result]) => `${studioName(id)}: ${result.notice}`);
  if (snapshot.prepare_problem) inform(snapshot.prepare_problem, true);
  if (!notices.length) return;
  const message = $('#message'); message.textContent = notices.join(' '); message.hidden = false;
}
function savedWords() {
  const names = Object.entries(snapshot.prepared || {}).filter(([, result]) => result.connect).map(([id]) => snapshot.studios.find(studio => studio.id === id)?.name).filter(Boolean);
  showNotices();
  return names.length ? `Shared settings saved. Connect ${names.join(' and ')} from the studio cards to use the new storage.` : 'Shared settings saved.';
}
function studioReadiness(studio){
  return studio.readiness || (studio.installed?{state:'done',label:'Ready to open',detail:'Local launch available; account access is checked when used.'}:{state:'off',label:'Not installed',detail:'Install this studio explicitly.'});
}
let homeRefreshing=false;
async function refreshHomeStatus(){
  if(standalone||!snapshot||setup||view!=='home'||document.hidden||homeRefreshing)return;
  homeRefreshing=true;
  try{
    const found=await api('home');
    if(setup||view!=='home'||document.hidden)return;
    const structural=JSON.stringify(snapshot.studios.map(s=>[s.id,s.installed,s.path]))!==JSON.stringify(found.studios.map(s=>[s.id,s.installed,s.path]));
    snapshot.studios=found.studios;
    if(structural){renderHome(false);return;}
    for(const studio of found.studios){
      const card=$(`#studio-list [data-studio="${studio.id}"]`);if(!card)continue;
      const ready=studioReadiness(studio),line=card.querySelector('.studio-readiness');
      if(line){line.querySelector('.bead').dataset.state=ready.state;line.lastElementChild.textContent=ready.label;line.title=ready.detail;}
      const running=card.querySelector('.studio-running');if(running)running.textContent=`${studio.running?'Running · ':''}${studio.version||''}`;
      const button=card.querySelector('.studio-open');if(button&&!button.disabled)button.textContent=studio.running?`Return to ${studio.name}`:`Open ${studio.name}`;
    }
  }catch(failure){
    // Retain the last readable state while reconnecting, but never show stale green lights.
    for(const line of document.querySelectorAll('.studio-readiness')){line.querySelector('.bead').dataset.state='review';line.lastElementChild.textContent='Status unavailable';line.title='Reopen the current private link if the app was restarted.';}
  }finally{homeRefreshing=false;}
}
function renderHome(refreshPaths = true) {
  const list = $('#studio-list'); list.replaceChildren();
  for (const studio of snapshot.studios) {
    const card = element('article', '', 'card studio-card');
    card.dataset.studio = studio.id;
    card.append(studioSymbol(studio.id), element('h3', studio.name, 'studio-name'), element('p', studio.description, 'studio-says'));
    const readiness=studioReadiness(studio);
    const readyLine=stateLine(readiness.state,readiness.label);readyLine.classList.add('studio-readiness');readyLine.title=readiness.detail;
    card.append(readyLine,element('p',`${studio.running?'Running · ':''}${studio.version||''}`,'quiet studio-running'));
    const link = studio.workspace;
    if (link) {
      // Where its work lives, read from the studio's own records.
      const line = element('p', '', 'studio-link');
      line.append(stateLine(link.state === 'connected' ? 'done' : link.state === 'disconnected' ? 'review' : 'none', link.summary));
      if (link.detail) line.append(element('span', link.detail, 'studio-link-detail quiet'));
      card.append(line);
    }
    if (studio.installed && link?.connect) {
      const connect = element('button', 'Connect', 'button studio-connect button-filled'); connect.type = 'button';
      connect.setAttribute('aria-label', `Connect ${studio.name} to the shared storage`);
      connect.addEventListener('click', async () => {
        connect.disabled = true; connect.textContent = 'Connecting…'; $('#problem').hidden = true; $('#message').hidden = true;
        try {
          snapshot = await api('connect', {studio: studio.id});
          const done = snapshot.connected; renderHome();
          const message = $('#message'); message.textContent = connectedWords(done); message.hidden = false;
          $(`#studio-list [data-studio="${studio.id}"] .button`)?.focus();
        } catch (error) { inform(error.message, true); connect.disabled = false; connect.textContent = 'Connect'; }
      });
      card.append(connect);
    }
    if (studio.installed) {
      const label = studio.running ? `Return to ${studio.name}` : `Open ${studio.name}`;
      const button = element('button', label, (link?.connect ? 'button' : 'button button-filled')+' studio-open');
      button.addEventListener('click', async () => {
        if (inThisTab((query) => window.matchMedia(query).matches)) {
          button.disabled = true; button.textContent = 'Opening…'; $('#problem').hidden = true;
          try { location.href = withHome((await api('open', {studio: studio.id})).link, true); }
          catch (error) { inform(error.message, true); button.disabled = false; button.textContent = label; }
          return;
        }
        let blocked = false;
        // Reserve the named tab during the click so popup protection does not lose it.
        const tab = window.open('about:blank', `marketing-${studio.id}`);
        button.disabled = true; button.textContent = 'Opening…'; $('#problem').hidden = true; $('#message').hidden = true;
        try {
          const result = await api('open', {studio: studio.id});
          if (tab) tab.location.href = withHome(result.link);
          else {
            const link = element('a', `Open ${studio.name}`); link.href = withHome(result.link); link.target = `marketing-${studio.id}`;
            const message = $('#message'); message.replaceChildren(document.createTextNode('Your browser blocked the new tab. '), link); message.hidden = false;
            link.focus(); blocked = true;
          }
          snapshot = await api('home'); renderHome();
          // The card was rebuilt, so put focus back on its button, unless the link above has it.
          if (!blocked) $(`#studio-list [data-studio="${studio.id}"] .button`)?.focus();
        } catch (error) { if (tab && tab.location.href === 'about:blank') tab.close(); inform(error.message, true); }
        finally { button.disabled = false; button.textContent = label; }
      }); card.append(button);
    } else {
      const link = element('a', `Install ${studio.name}`, 'button'); link.href = studio.repository; link.target = '_blank'; link.rel = 'noreferrer'; card.append(link);
    }
    list.append(card);
  }
  const network = snapshot.network;
  $('#network-access').hidden = standalone || !network;
  $('#network-link').value = network?.url || '';
  const remote = !['127.0.0.1', 'localhost', '[::1]'].includes(location.hostname);
  $('#where').textContent = remote ? 'On your local network' : 'On this computer';
  const shared = snapshot.shared;
  const assistant = shared.assistant?.agent === 'codex' ? 'Codex' : 'Claude Code';
  const workspace = shared.team?.repository ? `Repository: ${shared.team.repository}` : `Local Git: ${shared.local?.root || '~/Studios'}`;
  $('#summary-text').textContent = `${assistant}${shared.models?.mode === 'by_task' ? ' · Models by task' : ''}${shared.assistant?.model ? ` (${shared.assistant.model})` : ''}. ${workspace}.`;
  if(!refreshPaths)return;
  const fields = $('#path-fields'); fields.replaceChildren();
  for (const studio of snapshot.studios) {
    const field = element('div', '', 'field full');
    const label = element('label', studio.name, 'field-label'); label.htmlFor = `path-${studio.id}`;
    const input = element('input', '', 'input'); input.id = label.htmlFor; input.dataset.studio = studio.id;
    input.value = studio.configured_path; input.placeholder = studio.path || 'Absolute path to the studio installation';
    field.append(label, input); fields.append(field);
  }
}
function changesForStep() {
  validateModelChoices();
  const value = name => form.elements[name].value.trim() || null;
  const wanted = {};
  if (!setup || step === 0) {
    wanted.models = {schema: 1, agent: profileAgent, mode: form.elements['models.mode'].value, profiles: {}};
    for (const name of profileNames) wanted.models.profiles[name] = {selection: value(`models.${name}.selection`), model: value(`models.${name}.model`), effort: value(`models.${name}.effort`)};
    wanted.person = {name: value('person.name')};
    wanted.assistant = {agent: value('assistant.agent'), model: value('assistant.model'), effort: value('assistant.effort')};
  }
  if (!setup || step === 1) {
    const local = form.elements.storage.value === 'local';
    wanted.local = {root: value('local.root') || '~/Studios'};
    wanted.team = {repository: local ? null : value('team.repository'), branch: value('team.branch') || 'main'};
    if (!local && !wanted.team.repository) throw new Error('Give a repository address, or choose local Git.');
    wanted.share = value('share');
  }
  if (!setup || step === 2) {
    wanted.brand = Object.fromEntries(['repository', 'release', 'brand', 'variant', 'skill'].map(key => [key, value(`brand.${key}`)]));
    if (!blogAlone()) {
      wanted.output = value('output');
      wanted.render = {previews: value('render.previews')};
    }
  }
  // Research sites are kept in Shared settings, not in first-run setup.
  if (!setup) wanted.research = {sites: [...researchSites]};
  // Send just the leaves changed from what this form was shown.
  function changed(wanted, seen) {
    const result = {};
    for (const [key, value] of Object.entries(wanted)) {
      if (Array.isArray(value)) {
        if (JSON.stringify(value) !== JSON.stringify(seen?.[key] ?? [])) result[key] = value;
      } else if (value !== null && typeof value === 'object') {
        const inner = changed(value, seen?.[key]);
        if (Object.keys(inner).length) result[key] = inner;
      } else if (value !== (seen?.[key] ?? null)) result[key] = value;
    }
    return result;
  }
  const diff = changed(wanted, snapshot.shared);
  return diff;
}
// The installation folders, when one was changed on this form: every studio's, as the
// form now has them. Null when none changed.
function folderChanges() {
  if (setup || standalone) return null;
  const inputs = [...$('#path-fields').children].map(field => field.children[1]);
  const shown = Object.fromEntries((snapshot.studios || []).map(studio => [studio.id, studio.configured_path || '']));
  const now = Object.fromEntries(inputs.filter(Boolean).map(input => [input.dataset.studio, input.value.trim()]));
  return Object.keys(now).some(id => now[id] !== (shown[id] ?? '')) ? now : null;
}
form.addEventListener('submit', async event => {
  event.preventDefault(); $('#save').disabled = true; $('#problem').hidden = true;
  try {
    const folders = folderChanges();
    const changes = changesForStep(); snapshot = await api('shared', {changes, seen: snapshot.shared});
    // One save: the folders go after the shared settings, and a refusal says what was kept.
    if (folders) {
      try { snapshot = await api('paths', {paths: folders}); }
      catch (error) { fill(); renderHome(); inform(`Your shared settings were saved. The installation folders were not: ${error.message}`, true); return; }
    }
    if (setup && step < 2) { step++; show('settings'); }
    else if (setup) { snapshot = await api('setup', {done: true, prepare: true}); if (standalone) return openNative(); setup = false; renderHome(); show('home'); showNotices(); inform('Your studios are ready.'); }
    else { if (standalone) { await api('setup', {done: true}); return openNative(); } fill(); renderHome(); inform(savedWords()); }
  } catch (error) { inform(error.message, true); }
  finally { $('#save').disabled = false; }
});
$('#back').addEventListener('click', () => { step--; show('settings'); });
$('#find-brands').addEventListener('click', async () => {
  const button = $('#find-brands'); button.disabled = true;
  $('#brand-catalog-status').textContent = 'Looking up installed brands… Your form is kept.';
  try {
    const found = await api('brands', {skill: form.elements['brand.skill'].value.trim() || null});
    const holder = $('#brand-choices'); holder.replaceChildren(); holder.hidden = false;
    let index = 0;
    for (const skill of found.skills || []) for (const brand of skill.brands || []) {
      const row = element('div', '', 'field-grid brand-choice'), field = element('div', '', 'field');
      const label = element('label', `${skill.name} · ${brand.name} variant`, 'field-label');
      const select = element('select', '', 'input'); select.id = label.htmlFor = `brand-choice-${index++}`;
      for (const variant of brand.variants?.length ? brand.variants : ['']) select.add(new Option(variant || 'Default variant', variant));
      const use = element('button', `Use ${brand.name}`, 'button'); use.type = 'button';
      use.addEventListener('click', () => {
        form.elements['brand.skill'].value = skill.path;
        form.elements['brand.brand'].value = brand.brand;
        form.elements['brand.variant'].value = select.value;
        $('#brand-catalog-status').textContent = `${brand.name} selected. Save settings to keep this choice.`;
      });
      field.append(label, select); row.append(field, use); holder.append(row);
    }
    $('#brand-catalog-status').textContent = found.problem || 'Choose a brand and variant. Your saved choices change only when you save.';
  } catch (error) { $('#brand-catalog-status').textContent = `${error.message} Your form is kept; you can enter the IDs below.`; }
  finally { button.disabled = false; }
});
form.elements['assistant.agent'].addEventListener('change', () => { efforts(''); form.elements['assistant.model'].value = ''; for (const name of profileNames) { const select = form.elements[`models.${name}.effort`]; profileLevels(select, select.value); } for (const picker of modelPickers.values()) renderModelPicker(picker); profilesChanged(); loadModels(); });
form.querySelectorAll('[name="storage"]').forEach(input => input.addEventListener('change', storage));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => show(button.dataset.view)));
$('#home-link').addEventListener('click', event => { event.preventDefault(); show('home'); });
$('#back-to-studio').addEventListener('click', () => openNative());
$('#check').addEventListener('click', async () => {
  $('#check').disabled = true;
  try {
    const result = await api('computer', {}); const list = $('#computer-results'); list.replaceChildren();
    for (const item of result.computer.items) {
      const kind = item.ready ? 'done' : item.optional ? 'none' : 'review';
      const row = element('li', '', 'computer-item'), top = element('div', '', 'computer-top');
      top.append(element('p', item.name, 'row-title'), stateLine(kind, item.ready ? 'Available' : item.optional ? 'Optional' : 'Needs setup'));
      row.append(top, element('p', item.detail, 'facts')); list.append(row);
    }
  } catch (error) { inform(error.message, true); } finally { $('#check').disabled = false; }
});
$('#copy-network').addEventListener('click', async () => {
  const input = $('#network-link');
  try { await navigator.clipboard.writeText(input.value); inform('Private link copied. Open it on your phone.'); }
  catch (error) { input.focus(); input.select(); input.setSelectionRange(0, input.value.length); inform('Select and copy the private link, then open it on your phone.'); }
});
function openNative() {
  const samePage = location.pathname === '/' && !location.search;
  location.replace('/#' + (product === 'Blog Studio' ? token : 'token=' + token));
  // Setup can be served at the native root. A fragment change alone keeps its DOM.
  if (samePage) location.reload();
}
modelPicker(form.elements['assistant.model'], 'Shared model');
$('#refresh-models').addEventListener('click', () => loadModels(true));
(async () => {
  try {
    if (!token) { $('#loading').hidden = true; inform(`This page needs its private link. Run ${standalone ? 'the studio command' : 'marketing-studio'} in your terminal to open it again.`, true); return; }
    snapshot = await api('home'); setup = !snapshot.setup.done; fill(); renderHome(); show(setup || standalone ? 'settings' : requestedView); if (snapshot.shared_problem) inform(snapshot.shared_problem, true);
  }
  catch (error) { $('#loading').hidden = true; inform(error.message, true); }
})();

// Local inventory only: never launches studios, reads credentials or starts providers.
if(!standalone){
  setInterval(refreshHomeStatus,5000);
  window.addEventListener('focus',refreshHomeStatus);
  window.addEventListener('pageshow',refreshHomeStatus);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)void refreshHomeStatus();});
}
