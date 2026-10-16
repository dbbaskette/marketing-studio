'use strict';
const $ = selector => document.querySelector(selector);
const launchOptions = new URLSearchParams(location.hash.slice(1));
const requestedView = launchOptions.get('view') === 'settings' ? 'settings' : 'home';
const tokenInLink = launchOptions.get('token');
if (tokenInLink) { sessionStorage.setItem('marketing-studio-token', tokenInLink); history.replaceState(null, '', location.pathname); }
const token = tokenInLink || sessionStorage.getItem('marketing-studio-token') || '';
let snapshot, setup = false, step = 0, view = 'home';
const labels = ['You and your assistant', 'Your workspace', 'Brand and delivery'];
const form = $('#settings-form');
function inform(message, error = false) {
  const node = $(error ? '#problem' : '#message');
  node.textContent = message; node.hidden = false;
  if (!error) setTimeout(() => { node.hidden = true; }, 5000);
}
async function api(path, body) {
  const response = await fetch(`/api/${path}`, { method: body === undefined ? 'GET' : 'POST',
    headers: { 'X-Marketing-Studio-Token': token, ...(body === undefined ? {} : {'Content-Type': 'application/json'}) },
    ...(body === undefined ? {} : {body: JSON.stringify(body)}) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'This request could not be completed.');
  return result;
}
function element(tag, text, className) {
  const node = document.createElement(tag); if (text) node.textContent = text;
  if (className) node.className = className; return node;
}
function show(next) {
  window.scrollTo(0, 0);
  view = setup ? 'settings' : next;
  for (const name of ['loading', 'home', 'settings', 'computer']) $(`#${name}`).hidden = name !== view;
  $('#view-title').textContent = setup ? 'Welcome to Marketing Studio' : ({home: 'Studios', settings: 'Shared settings', computer: 'This computer'})[view];
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
  $('#installations').hidden = setup;
  $('#prepare-note').hidden = !setup || step !== 2;
}
function efforts(selected) {
  const agent = form.elements['assistant.agent'].value;
  const select = form.elements['assistant.effort'];
  select.replaceChildren(new Option('Assistant’s default', ''));
  for (const value of snapshot.efforts[agent]) select.add(new Option(value, value));
  select.value = selected || '';
}
function storage() {
  const local = form.elements.storage.value === 'local';
  $('#local-fields').hidden = !local; $('#remote-fields').hidden = local;
}
function fill() {
  const shared = snapshot.shared;
  for (const input of form.querySelectorAll('input[name], select[name]')) {
    if (input.name === 'storage' || input.name === 'assistant.effort') continue;
    const keys = input.name.split('.'); let value = keys.length === 2 ? shared[keys[0]]?.[keys[1]] : shared[keys[0]];
    value ??= ({'assistant.agent': 'claude', 'local.root': '~/Studios', 'team.branch': 'main', output: 'pptx', share: 'decision'})[input.name] || '';
    input.value = value;
  }
  form.elements.storage.value = shared.team?.repository ? 'remote' : 'local';
  efforts(shared.assistant?.effort); storage();
}
const drawings = {
  blog: '<path d="M5 4h10l4 4v14H5zM14 4v5h5M8 13h8M8 17h6"/>',
  presentation: '<path d="M3 5h20v14H3zM13 19v5M8 24h10M7 14l4-4 4 3 4-5"/>',
  training: '<path d="m2 9 11-5 11 5-11 5zM6 12v7c4 3 10 3 14 0v-7M24 9v10"/>'
};
function renderHome() {
  const list = $('#studio-list'); list.replaceChildren();
  for (const studio of snapshot.studios) {
    const card = element('article', '', 'studio-card');
    const icon = element('div', '', 'studio-icon'); icon.setAttribute('aria-hidden', 'true');
    // Drawings are static application assets; user and repository text use textContent.
    icon.innerHTML = `<svg viewBox="0 0 26 28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${drawings[studio.id]}</svg>`;
    card.append(icon, element('h3', studio.name), element('p', studio.description));
    const status = element('p', studio.running ? 'Running' : studio.installed ? `Ready${studio.version ? ` · ${studio.version}` : ''}` : 'Not installed', 'studio-status');
    status.dataset.running = String(studio.running); card.append(status);
    if (studio.installed) {
      const button = element('button', studio.running ? 'Return to studio' : 'Open studio');
      button.setAttribute('aria-label', `Open ${studio.name}`);
      button.addEventListener('click', async () => {
        // Reserve the named tab during the click so popup protection does not lose it.
        const tab = window.open('about:blank', `marketing-${studio.id}`);
        button.disabled = true; button.textContent = 'Opening…'; $('#problem').hidden = true;
        try {
          const result = await api('open', {studio: studio.id});
          if (tab) tab.location.href = result.link;
          else {
            const link = element('a', `Open ${studio.name}`); link.href = result.link; link.target = `marketing-${studio.id}`; link.rel = 'noreferrer';
            const message = $('#message'); message.replaceChildren(document.createTextNode('Your browser blocked the new tab. '), link); message.hidden = false;
          }
          snapshot = await api('home'); renderHome();
        } catch (error) { if (tab && tab.location.href === 'about:blank') tab.close(); inform(error.message, true); }
        finally { button.disabled = false; button.textContent = 'Open studio'; }
      }); card.append(button);
    } else {
      const link = element('a', 'Install studio'); link.href = studio.repository; link.target = '_blank'; link.rel = 'noreferrer'; card.append(link);
    }
    list.append(card);
  }
  const shared = snapshot.shared;
  const assistant = shared.assistant?.agent === 'codex' ? 'Codex' : 'Claude Code';
  const workspace = shared.team?.repository ? `Repository: ${shared.team.repository}` : `Local Git: ${shared.local?.root || '~/Studios'}`;
  $('#summary-text').textContent = `${assistant}${shared.assistant?.model ? ` (${shared.assistant.model})` : ''}. ${workspace}.`;
  const fields = $('#path-fields'); fields.replaceChildren();
  for (const studio of snapshot.studios) {
    const label = element('label', studio.name, 'full'); const input = element('input'); input.name = studio.id;
    input.value = studio.configured_path; input.placeholder = studio.path || 'Absolute path to the studio installation'; label.append(input); fields.append(label);
  }
}
function changesForStep() {
  const value = name => form.elements[name].value.trim() || null;
  const wanted = {};
  if (!setup || step === 0) {
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
    wanted.brand = Object.fromEntries(['repository', 'release', 'brand', 'variant'].map(key => [key, value(`brand.${key}`)]));
    wanted.output = value('output');
  }
  // Send just the leaves changed from what this form was shown.
  const diff = {};
  for (const [group, value] of Object.entries(wanted)) {
    if (typeof value === 'object' && value !== null) {
      const members = Object.fromEntries(Object.entries(value).filter(([key, inner]) => inner !== (snapshot.shared[group]?.[key] ?? null)));
      if (Object.keys(members).length) diff[group] = members;
    } else if (value !== (snapshot.shared[group] ?? null)) diff[group] = value;
  }
  return diff;
}
form.addEventListener('submit', async event => {
  event.preventDefault(); $('#save').disabled = true; $('#problem').hidden = true;
  try {
    const changes = changesForStep(); snapshot = await api('shared', {changes, seen: snapshot.shared});
    if (setup && step < 2) { step++; show('settings'); }
    else if (setup) { snapshot = await api('setup', {done: true, prepare: true}); setup = false; renderHome(); show('home'); inform('Your studios are ready.'); }
    else { fill(); renderHome(); inform('Shared settings saved.'); }
  } catch (error) { inform(error.message, true); }
  finally { $('#save').disabled = false; }
});
$('#back').addEventListener('click', () => { step--; show('settings'); });
form.elements['assistant.agent'].addEventListener('change', () => { efforts(''); form.elements['assistant.model'].value = ''; });
form.querySelectorAll('[name="storage"]').forEach(input => input.addEventListener('change', storage));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => show(button.dataset.view)));
$('#home-link').addEventListener('click', event => { event.preventDefault(); show('home'); });
$('#check').addEventListener('click', async () => {
  $('#check').disabled = true;
  try {
    const result = await api('computer', {}); const list = $('#computer-results'); list.replaceChildren();
    for (const item of result.computer.items) {
      const row = element('div', '', 'check-row'); const details = element('div'); details.append(element('h2', item.name), element('p', item.detail));
      row.append(details, element('span', item.ready ? 'Available' : item.optional ? 'Optional' : 'Needs setup', `check-state${item.ready ? '' : ' missing'}`)); list.append(row);
    }
  } catch (error) { inform(error.message, true); } finally { $('#check').disabled = false; }
});
$('#paths-form').addEventListener('submit', async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try { snapshot = await api('paths', {paths: Object.fromEntries(new FormData(event.target))}); renderHome(); inform('Installation folders saved.'); }
  catch (error) { inform(error.message, true); } finally { button.disabled = false; }
});
(async () => {
  try { snapshot = await api('home'); setup = !snapshot.setup.done; fill(); renderHome(); show(setup ? 'settings' : requestedView); if (snapshot.shared_problem) inform(snapshot.shared_problem, true); }
  catch (error) { $('#loading').hidden = true; inform(error.message, true); }
})();
