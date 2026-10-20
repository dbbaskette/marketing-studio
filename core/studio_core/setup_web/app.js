'use strict';
const $ = selector => document.querySelector(selector);
const standalone = document.body.dataset.standalone === 'true';
const product = document.body.dataset.product;
const tokenHeader = document.body.dataset.tokenHeader;
const sessionKey = standalone ? product.toLowerCase().replaceAll(' ', '-') + '-setup-token' : 'marketing-studio-token';
const launchOptions = new URLSearchParams(location.hash.slice(1));
const requestedView = launchOptions.get('view') === 'settings' ? 'settings' : 'home';
const tokenInLink = launchOptions.get('token') || (standalone && /^[A-Za-z0-9_-]+$/.test(location.hash.slice(1)) ? location.hash.slice(1) : '');
if (tokenInLink) { sessionStorage.setItem(sessionKey, tokenInLink); history.replaceState(null, '', location.pathname); }
const token = tokenInLink || sessionStorage.getItem(sessionKey) || '';
let snapshot, setup = false, step = 0, view = 'home', profileAgent;
const labels = ['You and your assistant', 'Your workspace', 'Brand and delivery'];
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
  view = setup ? 'settings' : next;
  for (const name of ['loading', 'home', 'settings', 'computer']) $(`#${name}`).hidden = name !== view;
  $('#view-title').textContent = setup ? `Welcome to ${product}` : ({home: 'Studios', settings: 'Shared settings', computer: 'This computer'})[view];
  document.querySelectorAll('[data-view]').forEach(button => {
    if (button.classList.contains('nav-item')) {
      button.toggleAttribute('disabled', setup);
      if (button.dataset.view === view && !setup) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    }
  });
  $('#settings-title').textContent = setup ? labels[step] : 'Shared settings';
  $('#settings-intro').textContent = setup ? 'Set up once. Your studios will start with these choices.' : 'New work in every studio starts with these choices.';
  $('#step-label').textContent = setup ? `Step ${step + 1} of 3` : '';
  $('#setup-progress').hidden = !setup;
  $('#setup-progress').querySelectorAll('li').forEach((node, index) => {
    if (index === step) node.setAttribute('aria-current', 'step'); else node.removeAttribute('aria-current');
  });
  form.querySelectorAll('[data-step]').forEach(section => { section.hidden = setup && Number(section.dataset.step) !== step; });
  $('#back').hidden = !setup || step === 0;
  $('#save').textContent = setup ? (step === 2 ? 'Finish setup' : 'Continue') : 'Save settings';
  $('#installations').hidden = setup || standalone;
  if (standalone) {
    document.querySelectorAll('nav [data-view]').forEach(node => { node.hidden = true; });
    $('#home-name').textContent = product;
    $('#prepare-note').textContent = 'Finish setup prepares this studio. Other studios will use these settings when you open them.';
    $('#save').textContent = setup && step < 2 ? 'Continue' : `Save and open ${product}`;
  }
  $('#prepare-note').hidden = !setup || step !== 2;
  if (view === 'settings' && (!setup || step === 0)) loadModels();
  // As in every studio, focus moves to the toolbar title. The step is announced.
  if (snapshot) $('#view-title').focus({preventScroll: true});
  $('#announce').textContent = setup ? `Step ${step + 1} of 3: ${labels[step]}` : '';
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
    value ??= ({'assistant.agent': 'claude', 'review.level': 'balanced', 'local.root': '~/Studios', 'team.branch': 'main', output: 'pptx', share: 'decision'})[input.name] || '';
    input.value = value;
  }
  form.elements.storage.value = shared.team?.repository ? 'remote' : 'local';
  efforts(shared.assistant?.effort); storage(); fillProfiles();
  for (const picker of modelPickers.values()) renderModelPicker(picker);
}
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
    const card = element('section', '', 'paper profile-card'); card.dataset.profile = name;
    card.append(element('h5', title, 'sheet-part'), element('p', descriptions[name], 'field-hint quiet'));
    const choice = element('div', '', 'field');
    const choiceLabel = element('label', 'Model choice', 'field-label'); choiceLabel.htmlFor = `models-${name}-selection`;
    const selection = element('select', '', 'input'); selection.id = choiceLabel.htmlFor; selection.name = `models.${name}.selection`;
    for (const [value, text] of [['inherit', 'Use shared model above'], ['provider_default', 'Assistant’s default'], ['explicit', 'Choose a model']]) selection.add(new Option(text, value));
    selection.value = saved.selection || 'inherit'; selection.addEventListener('change', profilesChanged);
    choice.append(choiceLabel, selection); card.append(choice);
    const fields = element('div', '', 'profile-explicit');
    const modelField = element('div', '', 'field'), modelLabel = element('label', 'Model', 'field-label');
    const input = element('input', '', 'input'); input.id = modelLabel.htmlFor = `models-${name}-model`;
    input.name = `models.${name}.model`; input.maxLength = 100; input.autocomplete = 'off'; input.value = saved.model || '';
    modelField.append(modelLabel, input);
    const effortField = element('div', '', 'field'), effortLabel = element('label', 'Reasoning', 'field-label');
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
  blog: '<path d="M5 4h10l4 4v14H5zM14 4v5h5M8 13h8M8 17h6"/>',
  presentation: '<path d="M3 5h20v14H3zM13 19v5M8 24h10M7 14l4-4 4 3 4-5"/>',
  training: '<path d="m2 9 11-5 11 5-11 5zM6 12v7c4 3 10 3 14 0v-7M24 9v10"/>'
};
const ownStudio = {'Blog Studio': 'blog', 'Presentation Studio': 'presentation', 'Training Studio': 'training'}[product];
// Standalone setup shows the studio's own symbol, as its sidebar and its home card do.
if (ownStudio) $('#home-symbol').innerHTML = `<svg class="icon" viewBox="0 0 26 28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${drawings[ownStudio]}</svg>`;
function renderHome() {
  const list = $('#studio-list'); list.replaceChildren();
  for (const studio of snapshot.studios) {
    const card = element('article', '', 'card studio-card');
    card.dataset.studio = studio.id;
    const icon = element('div', '', 'studio-icon'); icon.setAttribute('aria-hidden', 'true');
    // Drawings are static application assets; user and repository text use textContent.
    icon.innerHTML = `<svg viewBox="0 0 26 28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${drawings[studio.id]}</svg>`;
    card.append(icon, element('h3', studio.name, 'studio-name'), element('p', studio.description, 'studio-says'));
    const status = element('p', studio.running ? 'Running' : studio.installed ? `Ready${studio.version ? ` · ${studio.version}` : ''}` : 'Not installed', 'studio-status');
    status.dataset.running = String(studio.running); card.append(status);
    if (studio.installed) {
      const label = studio.running ? `Return to ${studio.name}` : `Open ${studio.name}`;
      const button = element('button', label, 'button button-filled');
      button.addEventListener('click', async () => {
        // Reserve the named tab during the click so popup protection does not lose it.
        const tab = window.open('about:blank', `marketing-${studio.id}`);
        button.disabled = true; button.textContent = 'Opening…'; $('#problem').hidden = true; $('#message').hidden = true;
        try {
          const result = await api('open', {studio: studio.id});
          if (tab) tab.location.href = result.link;
          else {
            const link = element('a', `Open ${studio.name}`); link.href = result.link; link.target = `marketing-${studio.id}`; link.rel = 'noreferrer';
            const message = $('#message'); message.replaceChildren(document.createTextNode('Your browser blocked the new tab. '), link); message.hidden = false;
          }
          snapshot = await api('home'); renderHome();
        } catch (error) { if (tab && tab.location.href === 'about:blank') tab.close(); inform(error.message, true); }
        finally { button.disabled = false; button.textContent = label; }
      }); card.append(button);
    } else {
      const link = element('a', 'Install studio', 'button'); link.href = studio.repository; link.target = '_blank'; link.rel = 'noreferrer'; card.append(link);
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
  const fields = $('#path-fields'); fields.replaceChildren();
  for (const studio of snapshot.studios) {
    const field = element('div', '', 'field full');
    const label = element('label', studio.name, 'field-label'); label.htmlFor = `path-${studio.id}`;
    const input = element('input', '', 'input'); input.id = label.htmlFor; input.name = studio.id;
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
    wanted.review = {level: value('review.level')};
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
    wanted.output = value('output');
    wanted.render = {previews: value('render.previews')};
  }
  // Send just the leaves changed from what this form was shown.
  function changed(wanted, seen) {
    const result = {};
    for (const [key, value] of Object.entries(wanted)) {
      if (value !== null && typeof value === 'object') {
        const inner = changed(value, seen?.[key]);
        if (Object.keys(inner).length) result[key] = inner;
      } else if (value !== (seen?.[key] ?? null)) result[key] = value;
    }
    return result;
  }
  const diff = changed(wanted, snapshot.shared);
  return diff;
}
form.addEventListener('submit', async event => {
  event.preventDefault(); $('#save').disabled = true; $('#problem').hidden = true;
  try {
    const changes = changesForStep(); snapshot = await api('shared', {changes, seen: snapshot.shared});
    if (setup && step < 2) { step++; show('settings'); }
    else if (setup) { snapshot = await api('setup', {done: true, prepare: true}); if (standalone) return openNative(); setup = false; renderHome(); show('home'); inform('Your studios are ready.'); }
    else { if (standalone) { await api('setup', {done: true}); return openNative(); } fill(); renderHome(); inform('Shared settings saved.'); }
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
      const label = element('label', `${skill.name} · ${brand.name}`, 'field-label');
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
$('#home-link').addEventListener('click', event => { event.preventDefault(); if (standalone) return openNative(); show('home'); });
$('#check').addEventListener('click', async () => {
  $('#check').disabled = true;
  try {
    const result = await api('computer', {}); const list = $('#computer-results'); list.replaceChildren();
    for (const item of result.computer.items) {
      const kind = item.ready ? 'done' : item.optional ? 'none' : 'review';
      const row = element('li', '', 'computer-item'), top = element('div', '', 'computer-top');
      top.append(element('h4', item.name, 'row-title'), stateLine(kind, item.ready ? 'Available' : item.optional ? 'Optional' : 'Needs setup'));
      row.append(top, element('p', item.detail, 'facts')); list.append(row);
    }
  } catch (error) { inform(error.message, true); } finally { $('#check').disabled = false; }
});
$('#paths-form').addEventListener('submit', async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try { snapshot = await api('paths', {paths: Object.fromEntries(new FormData(event.target))}); renderHome(); inform('Installation folders saved.'); }
  catch (error) { inform(error.message, true); } finally { button.disabled = false; }
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
  try { snapshot = await api('home'); setup = !snapshot.setup.done; fill(); renderHome(); show(setup || standalone ? 'settings' : requestedView); if (snapshot.shared_problem) inform(snapshot.shared_problem, true); }
  catch (error) { $('#loading').hidden = true; inform(error.message, true); }
})();
