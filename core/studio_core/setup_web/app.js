'use strict';
const $ = selector => document.querySelector(selector);
const standalone = document.body.dataset.standalone === 'true';
const product = document.body.dataset.product;
if (['Marketing Studio', 'Infographic Studio'].includes(product)) document.body.dataset.pilot = 'liquid';
const tokenHeader = document.body.dataset.tokenHeader;
const sessionKey = standalone ? product.toLowerCase().replaceAll(' ', '-') + '-setup-token' : 'marketing-studio-token';
const launchOptions = new URLSearchParams(location.hash.slice(1));
const requestedView = launchOptions.get('view') === 'settings' ? 'settings' : 'home';
// A studio can open one part of Shared settings, such as the workspace repository a Team
// library uses. Only a part this page lists is accepted, and only after first-run setup.
function launchPart(options, known) {
  const part = options.get('part') || '';
  return known.includes(part) ? part : '';
}
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
  // Leaving the form keeps what was typed on it; say so, since nothing was saved.
  if (previousView === 'settings' && view !== 'settings' && unsaved()) inform('Your shared settings changes are not saved yet. They stay on the Shared settings page until you save or reload.');
  if (view === 'computer' && snapshot?.computer) renderComputer(snapshot.computer);
  if (view === 'library') void openLibrary();
  for (const name of ['loading', 'home', 'settings', 'computer', 'library']) $(`#${name}`).hidden = name !== view;
  $('#view-title').textContent = setup ? `Welcome to ${product}` : ({home: 'Studios', settings: 'Shared settings', computer: 'This computer', library: 'Library'})[view];
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
  // The Library's one filled action is its toolbar's too: Add documents.
  $('#library-add-open').hidden = view !== 'library';
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
  // Setup asks the four everyday choices; section links, owners and Advanced come after it.
  $('#settings-nav').hidden = setup;
  $('#settings-owners').hidden = setup;
  $('#nav-installations').hidden = standalone;
  $('#done-settings').hidden = setup || standalone;
  // After setup, Save and its state stay in view: toolbar material, as a selection bar has.
  for (const name of ['save-bar', 'glass']) $('#save-bar').classList.toggle(name, !setup);
  if (standalone) {
    $('#prepare-note').textContent = 'Finish setup prepares this studio. Other studios will use these settings when you open them. Models and research sites are under Shared settings, Advanced, afterwards.';
    $('#save').textContent = setup && step < 2 ? 'Continue' : `Save and open ${product}`;
  }
  $('#prepare-note').hidden = !setup || step !== 2;
  describeAdvanced(); saveState();
  // Model lists are read only when Models and reasoning is open: browsing asks no assistant.
  if (view === 'settings' && !setup && $('#models-more').open) loadModels();
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

// Saved or not: the form as it was last filled from the shared settings, against what it holds
// now. Typed values, the research list and the installation folders all count.
let savedForm = '', savedAt = '';
function formState() {
  const named = [...form.querySelectorAll('input[name], select[name]')]
    .filter(input => input.type !== 'radio' || input.checked).map(input => [input.name, input.value]);
  const folders = [...$('#path-fields').children].map(field => field.children?.[1]?.value ?? '');
  return JSON.stringify([named, researchSites, folders, profileAgent ?? null]);
}
function unsaved() { return Boolean(snapshot) && !setup && formState() !== savedForm; }
function markSaved(when = '') { savedForm = formState(); savedAt = when; rememberShown(); saveState(); }
function saveState(saving = false) {
  const node = $('#save-state');
  node.hidden = setup || !snapshot;
  if (node.hidden) return;
  const pending = unsaved();
  node.dataset.pending = String(pending);
  node.replaceChildren(saving ? stateLine('current', 'Saving…')
    : pending ? stateLine('review', 'Unsaved changes')
      : stateLine('done', savedAt ? `Saved at ${savedAt}` : 'All changes saved'));
  describeAdvanced();
}
// Each Advanced part says what it holds while it is closed, and whether it overrides an
// automatic choice, so an override is never hidden by the disclosure.
function owner(id, override, plain = 'Shared') { const tag = $(id); tag.textContent = override ? 'Override' : plain; tag.dataset.override = String(override); }
function describeAdvanced() {
  const value = name => (form.elements[name]?.value || '').trim();
  const byTask = form.elements['models.mode']?.value === 'by_task';
  const model = value('assistant.model'), effort = value('assistant.effort');
  const single = `${model || 'the assistant’s default model'}${effort ? `, ${effort} reasoning` : model ? '' : ' and reasoning'}`;
  const chosen = profileNames.filter(name => (form.elements[`models.${name}.selection`]?.value || 'inherit') !== 'inherit').length;
  $('#models-state').textContent = !byTask ? `One model: ${single}`
    : chosen ? `By task: ${chosen} of 3 tasks have their own model; the rest use ${single}` : `By task: every task uses ${single}`;
  owner('#models-owner', byTask || Boolean(model || effort));
  $('#models-pointer').textContent = `Uses ${byTask ? 'models chosen by task' : single}. ${setup ? 'You can change this in Shared settings, Advanced, after setup.' : 'Change it under Advanced: Models and reasoning.'}`;
  const release = value('brand.release');
  $('#release-state').textContent = release ? `Pinned to ${release}` : 'Newest release';
  owner('#release-owner', Boolean(release));
  $('#research-state').textContent = researchSites.length ? `${researchSites.length} ${researchSites.length === 1 ? 'site' : 'sites'}` : 'No sites yet';
  const folders = [...$('#path-fields').children].filter(field => (field.children?.[1]?.value || '').trim()).length;
  $('#installations-state').textContent = folders ? `${folders} ${folders === 1 ? 'folder' : 'folders'} set by you` : 'Every studio found automatically';
  owner('#installations-owner', Boolean(folders), 'Found automatically');
}
// Section links: a part is brought into view and focused; an Advanced part opens.
function goToPart(id) {
  const part = $(`#${id}`); if (!part) return;
  const more = part.querySelector('details');
  if (more) more.open = true;
  part.scrollIntoView({block: 'start', behavior: calm() ? 'auto' : 'smooth'});
  const target = more ? more.querySelector('summary') : part.querySelector('.card-title');
  if (!more) target.setAttribute('tabindex', '-1');
  target.focus({preventScroll: true});
}
document.querySelectorAll('[data-part]').forEach(button => button.addEventListener('click', () => goToPart(button.dataset.part)));
form.addEventListener('input', () => saveState());
form.addEventListener('change', () => saveState());
$('#models-more').addEventListener('toggle', () => { if ($('#models-more').open && snapshot) loadModels(); });
$('#done-settings').addEventListener('click', () => show('home'));
// A reload or a closed tab would lose typed changes: the browser asks first.
window.addEventListener('beforeunload', event => { if (unsaved()) { event.preventDefault(); event.returnValue = ''; } });

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
  // A site added or removed by its button changes the form as typing does.
  saveState();
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
$('#confirm-profiles').addEventListener('click', () => { profileAgent = form.elements['assistant.agent'].value; profilesChanged(); saveState(); });
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

const studioPurposes = {
  blog: 'Draft a new blog or polish someone else’s writing.',
  presentation: 'Turn ideas and reference material into a branded deck.',
  training: 'Create a lesson, learner guide, slides and practice.',
  infographic: 'Explain an idea with diagrams, charts and concise labels.'
};
// Small output-format illustrations, never generated work or project previews.
function studioPreview(id) {
  const node = element('div', '', 'studio-preview'); node.setAttribute('aria-hidden', 'true');
  const space = 'http://www.w3.org/2000/svg', svg = document.createElementNS(space, 'svg');
  for (const [key, value] of Object.entries({viewBox:'0 0 160 108',fill:'none',stroke:'currentColor',
    'stroke-width':'1.8','stroke-linecap':'round','stroke-linejoin':'round'})) svg.setAttribute(key,value);
  const shapes = {
    blog: [['path',{d:'M48 9h63l17 17v72H48z',fill:'var(--card)'}],['path',{d:'M111 9v18h17'}],
      ['path',{d:'M62 39h44', 'stroke-width':'4'}],['path',{d:'M62 51h50M62 60h42M62 69h50M62 78h31',opacity:'.5'}],
      ['rect',{x:'22',y:'46',width:'38',height:'23',rx:'5',fill:'var(--studio-wash)'}],['path',{d:'m32 58 5 5 10-11'}]],
    presentation: [['rect',{x:'17',y:'19',width:'127',height:'77',rx:'6',fill:'var(--card)'}],
      ['path',{d:'M31 34h45', 'stroke-width':'4'}],['path',{d:'M31 45h69',opacity:'.4'}],
      ['rect',{x:'32',y:'66',width:'17',height:'16',rx:'2',fill:'var(--studio-wash)'}],
      ['rect',{x:'58',y:'56',width:'17',height:'26',rx:'2',fill:'var(--studio-wash)'}],
      ['rect',{x:'84',y:'49',width:'17',height:'33',rx:'2',fill:'var(--studio-wash)'}],['path',{d:'m109 71 10-10 10 5'}]],
    training: [['path',{d:'M29 48h31V25h35v23h27',opacity:'.5'}],
      ['rect',{x:'12',y:'37',width:'32',height:'25',rx:'5',fill:'var(--studio-wash)'}],
      ['rect',{x:'63',y:'13',width:'32',height:'25',rx:'5',fill:'var(--studio-wash)'}],
      ['rect',{x:'114',y:'37',width:'32',height:'25',rx:'5',fill:'var(--studio-wash)'}],
      ['path',{d:'m23 49 4 4 8-9m47-20h-8m-42 31h-8'}],
      ['path',{d:'M48 78c10-5 21-5 31 0 10-5 21-5 31 0v20c-10-5-21-5-31 0-10-5-21-5-31 0z',fill:'var(--card)'}],['path',{d:'M79 78v20'}]],
    infographic: [['rect',{x:'44',y:'8',width:'74',height:'93',rx:'5',fill:'var(--card)'}],
      ['path',{d:'M58 23h38','stroke-width':'4'}],['path',{d:'M58 32h46',opacity:'.4'}],
      ['circle',{cx:'63',cy:'51',r:'9',fill:'var(--studio-wash)'}],['circle',{cx:'99',cy:'51',r:'9',fill:'var(--studio-wash)'}],
      ['path',{d:'M72 51h18m-12-4 5 4-5 4'}],['rect',{x:'57',y:'75',width:'11',height:'12',rx:'2',fill:'var(--studio-wash)'}],
      ['rect',{x:'75',y:'68',width:'11',height:'19',rx:'2',fill:'var(--studio-wash)'}],['rect',{x:'93',y:'72',width:'11',height:'15',rx:'2',fill:'var(--studio-wash)'}]]
  };
  for (const [tag, attrs] of shapes[id] || []) {
    const shape = document.createElementNS(space,tag);
    for (const [key,value] of Object.entries(attrs)) shape.setAttribute(key,value);
    svg.append(shape);
  }
  node.append(svg); return node;
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
  return studio.readiness || (studio.installed
    ? {state: 'none', label: 'Not checked', detail: 'Marketing Studio has not said what this studio needs yet.', action: null}
    : {state: 'off', label: 'Not installed', detail: 'Install it yourself to open it here.', action: null});
}
// What a card can honestly say before its studio opens, in words on the card rather than a
// tooltip, with the one way to fix what is missing. Opening, sign-in and paid work are not
// part of it: each studio checks those when a task needs them.
function readinessBlock(studio) {
  const ready = studioReadiness(studio), block = element('div', '', 'studio-readiness');
  block.dataset.ready = JSON.stringify(ready);
  block.append(stateLine(ready.state, ready.label), element('p', ready.detail, 'studio-readiness-detail quiet'));
  if (ready.action) {
    const fix = element('button', ready.action.label, 'button button-quiet studio-recover'); fix.type = 'button';
    fix.addEventListener('click', () => recover(ready.action.view));
    block.append(fix);
  }
  return block;
}
// The recovery actions: shared settings, or a look at this computer that changes nothing.
function recover(where) {
  show(where);
  if (where === 'computer') void checkComputer();
}
function renderReadinessSummary() {
  const installed = snapshot.studios.filter(studio => studio.installed);
  const states = installed.map(studio => studioReadiness(studio).state);
  const [kind, words] = !installed.length ? ['off', 'Not installed'] : states.includes('review') ? ['review', 'Needs setup']
    : states.every(state => state === 'done') ? ['done', 'Can open'] : ['none', 'Not checked'];
  $('#ready-open').replaceChildren(stateLine(kind, words));
  const look = snapshot.computer, needs = (look?.items || []).filter(item => !item.ready && !item.optional);
  $('#ready-computer').replaceChildren(stateLine(!look ? 'none' : needs.length ? 'review' : 'done',
    !look ? 'Not checked' : needs.length ? 'Needs setup' : 'Checked'));
  const when = look?.checked_at ? new Date(look.checked_at).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'}) : '';
  $('#computer-summary').textContent = !look
    ? 'Git identity, Node.js and the other tools are checked only when you ask. A check reads this computer and changes nothing.'
    : needs.length ? `Missing: ${needs.map(item => item.name).join(', ')}. This computer says how to fix ${needs.length === 1 ? 'it' : 'each'}.`
      : `Checked${when ? ` at ${when}` : ''}: the tools every studio needs are here.`;
  $('#go-check').textContent = look ? 'Check again' : 'Check this computer';
  $('#ready-accounts').replaceChildren(stateLine('none', 'Checked when used'));
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
    if('computer' in found)snapshot.computer=found.computer;
    if(structural){renderHome(false);return;}
    renderReadinessSummary();
    for(const studio of found.studios){
      const card=$(`#studio-list [data-studio="${studio.id}"]`);if(!card)continue;
      const line=card.querySelector('.studio-readiness');
      // Rebuilt only when it changed, so a focused recovery button keeps its focus.
      if(line&&line.dataset.ready!==JSON.stringify(studioReadiness(studio)))line.replaceWith(readinessBlock(studio));
      const running=card.querySelector('.studio-running');if(running)running.textContent=`${studio.running?'Running · ':''}${studio.version||''}`;
      const button=card.querySelector('.studio-open');if(studio.installed&&button&&!button.disabled){button.textContent=studio.running?'Return':'Open';button.setAttribute('aria-label',studio.running?`Return to ${studio.name}`:`Open ${studio.name}`);}
    }
  }catch(failure){
    // Retain the last readable state while reconnecting, but never show stale green lights.
    for(const line of document.querySelectorAll('.studio-readiness')){const studio=snapshot.studios.find(s=>s.id===line.closest('[data-studio]')?.dataset.studio)||{installed:true};line.replaceWith(readinessBlock({...studio,readiness:{state:'review',label:'Not checked',detail:'Marketing Studio did not answer, so this was not checked. If it was restarted, open the new private link from its terminal.',action:null}}));}
  }finally{homeRefreshing=false;}
}
function renderHome(refreshPaths = true) {
  const list = $('#studio-list'); list.replaceChildren();
  for (const studio of snapshot.studios) {
    const card = element('article', '', 'card studio-card');
    card.dataset.studio = studio.id;
    card.append(studioSymbol(studio.id), element('h3', studio.name, 'studio-name'),
      element('p', studioPurposes[studio.id] || studio.description, 'studio-says'), studioPreview(studio.id));
    card.append(readinessBlock(studio));
    const footer = element('div','','studio-footer'), actions = element('div','','studio-actions');
    const details = element('details','','studio-repository');
    const summary = element('summary','Details'); summary.setAttribute('aria-label',`Details for ${studio.name}`);
    details.append(summary,element('p',`${studio.running?'Running · ':''}${studio.version||'Version not reported'}`,'quiet studio-running'));
    const link = studio.workspace;
    if (link) {
      // Where its work lives, read from the studio's own records.
      const line = element('div', '', 'studio-link');
      const connected=link.state === 'connected' && product === 'Marketing Studio';
      line.append(stateLine(link.state === 'connected' ? 'done' : link.state === 'disconnected' ? 'review' : 'none', connected ? 'Shared repository connected' : link.summary));
      if (connected) line.append(element('p',[link.summary,link.detail].filter(Boolean).join('\n'),'studio-link-detail quiet'));
      else if (link.detail) line.append(element('span', link.detail, 'studio-link-detail quiet'));
      details.append(line);
      if (link.state === 'disconnected') {
        const warning=stateLine('review',link.summary);warning.classList.add('studio-warning');card.append(warning);
      }
    }
    if (link || studio.version) footer.append(details);
    footer.append(actions); card.append(footer);
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
      actions.append(connect);
    }
    if (studio.installed) {
      const label = studio.running ? `Return to ${studio.name}` : `Open ${studio.name}`;
      const words = studio.running ? 'Return' : 'Open';
      const button = element('button', words, (link?.connect ? 'button' : 'button button-filled')+' studio-open');
      button.setAttribute('aria-label',label);
      button.addEventListener('click', async () => {
        if (inThisTab((query) => window.matchMedia(query).matches)) {
          button.disabled = true; button.textContent = 'Opening…'; $('#problem').hidden = true;
          try { location.href = withHome((await api('open', {studio: studio.id})).link, true); }
          catch (error) { inform(error.message, true); button.disabled = false; button.textContent = words; }
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
        finally { button.disabled = false; button.textContent = words; }
      }); actions.append(button);
    } else {
      const link = element('a', 'Install', 'button studio-open'); link.setAttribute('aria-label',`Install ${studio.name}`);link.href = studio.repository; link.target = '_blank'; link.rel = 'noreferrer'; actions.append(link);
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
  renderReadinessSummary();
  if(!refreshPaths)return;
  const fields = $('#path-fields'); fields.replaceChildren();
  for (const studio of snapshot.studios) {
    const field = element('div', '', 'field full');
    const label = element('label', studio.name, 'field-label'); label.htmlFor = `path-${studio.id}`;
    const input = element('input', '', 'input'); input.id = label.htmlFor; input.dataset.studio = studio.id;
    input.value = studio.configured_path; input.placeholder = studio.path || 'Absolute path to the studio installation';
    field.append(label, input); fields.append(field);
  }
  saveState();
}
// What the form holds, group by group, shaped as the studios config is.
function wantedValues() {
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
  return wanted;
}
// The groups as the form was last filled, after setup: a group nobody changed sends nothing,
// so the defaults the form fills in for a value the config lacks are never written unasked.
let shownWanted = null;
function rememberShown() {
  try { shownWanted = setup ? null : wantedValues(); } catch (error) { shownWanted = null; }
}
function changesForStep() {
  validateModelChoices();
  const wanted = wantedValues();
  for (const group of Object.keys(wanted)) {
    if (shownWanted && !setup && JSON.stringify(wanted[group]) === JSON.stringify(shownWanted[group])) delete wanted[group];
  }
  // Send just the leaves changed from what this form was shown. A group that was changed
  // sends every leaf that differs from the config, as before, so it stays complete.
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
const clock = () => new Date().toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});
form.addEventListener('submit', async event => {
  event.preventDefault(); $('#save').disabled = true; $('#problem').hidden = true; saveState(true);
  try {
    const folders = folderChanges();
    const changes = changesForStep(); snapshot = await api('shared', {changes, seen: snapshot.shared});
    // One save: the folders go after the shared settings, and a refusal says what was kept.
    if (folders) {
      try { snapshot = await api('paths', {paths: folders}); }
      catch (error) { fill(); renderHome(); markSaved(); inform(`Your shared settings were saved. The installation folders were not: ${error.message}`, true); return; }
    }
    if (setup && step < 2) { step++; show('settings'); }
    else if (setup) { snapshot = await api('setup', {done: true, prepare: true}); if (standalone) return openNative(); setup = false; fill(); renderHome(); markSaved(); show('home'); showNotices(); inform('Your studios are ready.'); }
    else { if (standalone) { await api('setup', {done: true}); markSaved(); return openNative(); } fill(); renderHome(); markSaved(clock());
      // The save bar already says Saved at…; a toast says only what still needs doing.
      const words = savedWords(); if (words !== 'Shared settings saved.') inform(words); }
  } catch (error) { inform(error.message, true); }
  finally { $('#save').disabled = false; saveState(); }
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
        saveState();
      });
      field.append(label, select); row.append(field, use); holder.append(row);
    }
    $('#brand-catalog-status').textContent = found.problem || 'Choose a brand and variant. Your saved choices change only when you save.';
  } catch (error) { $('#brand-catalog-status').textContent = `${error.message} Your form is kept; you can enter the IDs below.`; }
  finally { button.disabled = false; }
});
form.elements['assistant.agent'].addEventListener('change', () => { efforts(''); form.elements['assistant.model'].value = ''; for (const name of profileNames) { const select = form.elements[`models.${name}.effort`]; profileLevels(select, select.value); } for (const picker of modelPickers.values()) renderModelPicker(picker); profilesChanged(); if ($('#models-more').open) loadModels(); });
form.querySelectorAll('[name="storage"]').forEach(input => input.addEventListener('change', storage));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => show(button.dataset.view)));
$('#home-link').addEventListener('click', event => { event.preventDefault(); show('home'); });
$('#back-to-studio').addEventListener('click', () => openNative());
function renderComputer(look) {
  const list = $('#computer-results'); list.replaceChildren();
  for (const item of look.items) {
    const kind = item.ready ? 'done' : item.optional ? 'none' : 'review';
    const row = element('li', '', 'computer-item'), top = element('div', '', 'computer-top');
    top.append(element('p', item.name, 'row-title'), stateLine(kind, item.ready ? 'Available' : item.optional ? 'Optional' : 'Needs setup'));
    row.append(top, element('p', item.detail, 'facts')); list.append(row);
  }
}
// A look at this computer: local commands and Git settings only. Nothing signs in or installs.
async function checkComputer() {
  $('#check').disabled = true;
  try {
    const result = await api('computer', {}); snapshot.computer = result.computer;
    renderComputer(result.computer); renderReadinessSummary();
  } catch (error) { inform(error.message, true); } finally { $('#check').disabled = false; }
}
$('#check').addEventListener('click', checkComputer);
// Its data-view shows This computer first; the look runs there, where its results are listed.
$('#go-check').addEventListener('click', () => void checkComputer());
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
// The Document Library screen: the list first, Add documents as the toolbar's one filled
// action, and Add existing work beside the lede. It selects nothing for a project; each
// studio's Add from library does that for its own work.
let libraryCatalog = null;
function libraryKit() {
  if (window.StudioLibrary) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = '/library.js';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('The library page could not be loaded. Reload this page.'));
    document.head.append(script);
  });
}
// Add existing work is a one-time step: prominent until something has been added from a
// studio's workspace, then a quiet button.
function libraryIntake(answer) {
  if (!answer) return;
  const imported = Boolean(answer.imported);
  $('#library-existing-open').className = imported ? 'button button-quiet' : 'button';
  $('#library-existing-hint').hidden = imported;
  if (answer.location) $('#library-where').textContent = `Kept in ${answer.location} on this computer.`;
}
async function openLibrary() {
  if (standalone) return;
  try {
    await libraryKit();
    if (!libraryCatalog) {
      libraryCatalog = new window.StudioLibrary.Catalog({
        studio: 'marketing',
        manage: true,      // Remove from library, Show hidden and Restore
        said: message => inform(message),
        post: (route, body) => api(route, body),
        download: async (row, format) => {
          try {
            const found = await api('library-download', {id: row.id, revision: row.revision, format});
            const bytes = Uint8Array.from(atob(found.content), c => c.charCodeAt(0));
            const link = document.createElement('a');
            link.href = URL.createObjectURL(new Blob([bytes], {type: found.media}));
            link.download = found.name; document.body.append(link); link.click(); link.remove();
            setTimeout(() => URL.revokeObjectURL(link.href), 1000);
          } catch (error) { inform(error.message, true); }
        },
      }, {onChange: () => libraryIntake(libraryCatalog && libraryCatalog.answer)});
      $('#library-catalog').replaceChildren(libraryCatalog.node);
    } else void libraryCatalog.load();
  } catch (error) { inform(error.message, true); }
}
// The Library's two sheets. Escape and Close return focus to what opened them; neither
// closes while its work is landing.
const librarySheets = {busy: false};
function openLibrarySheet(dialog, opener, first) {
  dialog.returnTo = opener;
  dialog.showModal();
  if (first) first.focus();
}
function closeLibrarySheet(dialog) { if (!librarySheets.busy) dialog.close(); }
for (const dialog of [$('#library-add-sheet'), $('#library-existing')]) {
  dialog.addEventListener('cancel', event => { if (librarySheets.busy) event.preventDefault(); });
  dialog.addEventListener('close', () => {
    const back = dialog.returnTo;
    if (back && document.body.contains(back) && !back.hidden) back.focus();
  });
}
$('#library-existing-open').addEventListener('click', () => {
  $('#library-existing-result').replaceChildren();
  openLibrarySheet($('#library-existing'), $('#library-existing-open'), $('#library-existing-preview'));
});
$('#library-existing-close').addEventListener('click', () => closeLibrarySheet($('#library-existing')));
// Add existing work to library: a preview of what the studios' remembered workspaces hold,
// then an import only when it is confirmed. The confirm carries the preview's signature, so
// it adds exactly what was shown or refuses when the workspaces changed since.
function existingRow(title, lines, tagText) {
  const item = element('li', '', 'library-row');
  const text = element('div', '', 'library-row-text');
  text.append(element('span', title, 'row-title'));
  for (const [line, kind] of lines) if (line) text.append(element('span', line, kind || 'quiet'));
  item.append(text);
  if (tagText) item.append(element('span', tagText, 'tag'));
  return item;
}
function showExisting(found) {
  const box = $('#library-existing-result');
  const places = element('ul', '', 'library-list');
  places.setAttribute('aria-label', 'Workspaces looked at');
  for (const place of found.workspaces) {
    places.append(existingRow(place.label, [[place.summary], [place.shown ? `Workspace: ${place.shown}` : ''],
      ...place.gaps.map(gap => [gap])]));
  }
  // Said to a screen reader as the confirm's result is: what the preview found.
  const said = element('p', found.adding ? `${found.adding === 1 ? '1 item' : `${found.adding} items`} can be added. Nothing is added until you confirm.`
    : found.total ? 'Everything found is already in the library.' : 'No existing work was found to add.', 'quiet');
  said.setAttribute('role', 'status');
  said.tabIndex = -1; said.id = 'library-existing-said';
  const parts = [said, element('h4', 'Workspaces', 'card-subtitle'), places];
  if (found.total) {
    const counts = [found.new && `${found.new} new`, found.changed && `${found.changed} with a newer revision`,
      found.kept && `${found.kept} already in the library`].filter(Boolean).join(', ');
    parts.push(element('h4', `${found.total === 1 ? '1 item' : `${found.total} items`} found: ${counts}`, 'card-subtitle'));
    const items = element('ul', '', 'library-list');
    items.setAttribute('aria-label', 'Existing work found');
    for (const item of found.items) {
      const meta = [item.kind_label, item.studio_label, item.note, item.format_labels.join(', ')].filter(Boolean).join(' · ');
      items.append(existingRow(item.title, [[meta], ...item.gaps.map(gap => [gap])], item.state_label));
    }
    parts.push(items);
    if (found.total > found.items.length) parts.push(element('p', `${found.total - found.items.length} more are not listed here; adding includes them.`, 'quiet'));
  }
  const bar = element('div', '', 'bar');
  if (found.adding) {
    const go = element('button', found.adding === 1 ? 'Add 1 to library' : `Add ${found.adding} to library`, 'button button-filled');
    go.type = 'button'; go.id = 'library-existing-add';
    go.addEventListener('click', () => adoptExisting(found.signature, go));
    bar.append(go);
  }
  const cancel = element('button', found.adding ? 'Cancel' : 'Close', 'button button-quiet');
  cancel.type = 'button';
  cancel.addEventListener('click', () => { box.replaceChildren(); $('#library-existing-preview').focus(); });
  bar.append(cancel);
  parts.push(element('p', 'Adding keeps a local copy in the Document Library. Nothing is shared with your team or changed in a studio.', 'field-hint quiet'), bar);
  box.replaceChildren(...parts);
}
async function adoptExisting(signature, button) {
  const box = $('#library-existing-result'), label = button.textContent;
  button.disabled = true; button.textContent = 'Adding…'; librarySheets.busy = true;
  try {
    const done = await api('library-adopt', {signature});
    const said = [done.added && `${done.added} added`, done.revised && `${done.revised} with a new revision`,
      done.unchanged && `${done.unchanged} already there`].filter(Boolean).join(', ') || 'Nothing to add';
    const parts = [element('p', `${said}.`, '')];
    parts[0].setAttribute('role', 'status');
    for (const failed of done.failed) parts.push(element('p', `${failed.title}: ${failed.problem}`, 'problem'));
    if (done.failed.length) parts.push(element('p', 'Preview again to try those once more; what was added is not added twice.', 'quiet'));
    box.replaceChildren(...parts);
    inform(done.failed.length ? 'Some existing work could not be added.' : 'Existing work was added to the library.');
    if (libraryCatalog) void libraryCatalog.load();
    $('#library-existing-preview').focus();
  } catch (error) {
    const problem = element('p', error.message, 'problem');
    problem.setAttribute('role', 'alert');
    box.prepend(problem);
    button.disabled = false; button.textContent = label;
  } finally { librarySheets.busy = false; }
}
// The button is disabled while the preview loads, so focus moves to what it found.
$('#library-existing-preview').addEventListener('click', async () => {
  const button = $('#library-existing-preview');
  button.disabled = true;
  try { showExisting(await api('library-existing', {})); }
  catch (error) {
    const problem = element('p', error.message, 'problem');
    problem.setAttribute('role', 'alert'); problem.tabIndex = -1; problem.id = 'library-existing-said';
    $('#library-existing-result').replaceChildren(problem);
  }
  finally { button.disabled = false; }
  const result = $('#library-existing-said');
  if (result) result.focus();
});
// Add documents: each file is added on its own and reported by name, and a refusal never
// stops the rest. A file keeps its operation ID for as long as this page is open, so a retry
// (or choosing it again) is the same upload and never keeps it twice; what was added leaves
// the selection, so Add to library again tries only what was refused.
const libraryOperations = new Map(), libraryKept = new Map();
const fileKey = file => [file.name, file.size, file.lastModified].join('|');
function operationId(file) {
  const key = fileKey(file);
  if (!libraryOperations.has(key)) {
    const bytes = new Uint8Array(16); crypto.getRandomValues(bytes);
    libraryOperations.set(key, [...bytes].map(b => b.toString(16).padStart(2, '0')).join(''));
  }
  return libraryOperations.get(key);
}
async function uploadOne(file) {
  const key = fileKey(file);
  if (libraryKept.has(key)) return {state: 'already', detail: `Already added as “${libraryKept.get(key)}”, so it was not added again.`};
  if (file.size > 8_000_000) return {state: 'refused', detail: 'It is larger than 8 MB, the most one document can be.'};
  try {
    const bytes = new Uint8Array(await file.arrayBuffer()); let binary = '';
    for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
    const found = await api('library-upload', {operation: operationId(file), name: file.name, content: btoa(binary)});
    const kept = found.document;
    libraryKept.set(key, kept.title);
    $('#library-where').textContent = `Kept in ${found.location} on this computer.`;
    if (kept.already) return {state: 'already', detail: `Already in the library as “${kept.title}”${kept.restored ? ', and shown again: it had been removed' : ''}.`};
    const note = kept.restored ? ' It had been removed from the library and is shown again.' : '';
    return {state: 'added', detail: kept.readable ? `Added as “${kept.title}”.${note}` : `Added as “${kept.title}”, but ${kept.problem}${note}`};
  } catch (error) { return {state: 'refused', detail: error.message}; }
}
$('#library-add-open').addEventListener('click', () => {
  $('#library-add-results').replaceChildren();
  $('#library-add-cancel').textContent = 'Cancel';
  openLibrarySheet($('#library-add-sheet'), $('#library-add-open'), $('#library-files'));
});
for (const id of ['#library-add-close', '#library-add-cancel']) $(id).addEventListener('click', () => closeLibrarySheet($('#library-add-sheet')));
$('#library-add').addEventListener('click', async () => {
  const input = $('#library-files'), box = $('#library-add-results'), button = $('#library-add');
  const files = [...input.files];
  if (librarySheets.busy) return;
  if (!files.length) {
    const said = element('p', 'Choose one or more files first.', 'problem'); said.setAttribute('role', 'alert');
    box.replaceChildren(said); input.focus(); return;
  }
  librarySheets.busy = true; button.disabled = true; button.textContent = 'Adding…';
  const outcomes = [];
  try { for (const file of files) outcomes.push({file, ...await uploadOne(file)}); }
  finally { librarySheets.busy = false; button.disabled = false; button.textContent = 'Add to library'; }
  const refused = outcomes.filter(one => one.state === 'refused');
  try {
    const left = new DataTransfer();
    for (const one of refused) left.items.add(one.file);
    input.files = left.files;
  } catch (error) { if (!refused.length) input.value = ''; }
  const count = state => outcomes.filter(one => one.state === state).length;
  const added = count('added'), already = count('already');
  const said = element('p', [added && `${added} added`, already && `${already} already in the library`,
    refused.length && `${refused.length} not added`].filter(Boolean).join(', ') + '.', '');
  said.setAttribute('role', 'status'); said.tabIndex = -1;
  const list = element('ul', '', 'library-list');
  list.setAttribute('aria-label', 'Files');
  for (const one of outcomes) {
    list.append(existingRow(one.file.name, [[one.detail, one.state === 'refused' ? 'problem' : 'quiet']],
      ({added: 'Added', already: 'Already there', refused: 'Not added'})[one.state]));
  }
  const parts = [said, list];
  if (refused.length) parts.push(element('p', 'The files not added are still chosen. Fix them, or choose others, then add again; what was added is not added twice.', 'field-hint quiet'));
  box.replaceChildren(...parts);
  if (added || already) $('#library-add-cancel').textContent = 'Done';
  said.focus();
  if (added) inform(added === 1 ? 'Added 1 document to the library.' : `Added ${added} documents to the library.`);
  if (libraryCatalog) void libraryCatalog.load();
});
modelPicker(form.elements['assistant.model'], 'Shared model');
$('#refresh-models').addEventListener('click', () => loadModels(true));
(async () => {
  try {
    if (!token) { $('#loading').hidden = true; inform(`This page needs its private link. Run ${standalone ? 'the studio command' : 'marketing-studio'} in your terminal to open it again.`, true); return; }
    snapshot = await api('home'); setup = !snapshot.setup.done; fill(); renderHome(); markSaved(); show(setup || standalone ? 'settings' : requestedView); if (snapshot.shared_problem) inform(snapshot.shared_problem, true);
    const part = setup ? '' : launchPart(launchOptions, [...document.querySelectorAll('[data-part]')].map(button => button.dataset.part));
    if (part) { if (view !== 'settings') show('settings'); goToPart(part); }
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
