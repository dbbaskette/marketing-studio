// The training desk: a new training's start in three numbered steps, and one desk per
// training started there. The desk shows the start's progress band, what needs the person,
// the level tabs, a card for each material of the level in order, the Sources beside them,
// and Mark this level ready. It reads GET /api/drafts (runner/drafts.py `view`) and sends
// the person's decisions to /api/drafts/*, each answered with the desk again.
//
// It is loaded after app.js and draws with app.js's own parts (make, add, button, capsule,
// card, segmented, openSheet and the rest), so nothing here is a second copy of how the page
// makes a box, a button or a request. The shared desk kit (ui-kit/drafting.js) is bound to
// this page in deskKit. Every value from the server is set as text: nothing here writes
// markup.
'use strict';

const DESK_WORDS = {
  lede: 'Each level’s materials, built from the shared research. Edit any part. Nothing is '
    + 'ready until you mark it.',
  steps: ['Goal and audience', 'Materials and levels', 'Sources and settings'],
  // What each card is called, by the kind of material it holds.
  kinds: { blueprint: 'Plan', document: 'Guide', brief: 'Brief', deck: 'Deck',
    scenario: 'Practice', yoodli: 'Yoodli' },
  // The shape beside a card's state; its words are the card's own sentence.
  beads: { writing: 'current', draft: 'none', ready: 'done', held: 'late', needs: 'late',
    'left-out': 'out' },
  noResearch: 'The research is not written yet. It opens here when it is.',
  kept: 'Your documents stay on this computer and are never shared with your team. Passages '
    + 'quoted from them appear in the research report, which is shared.',
  documentsHint: 'Optional. Research reads them first, and starts once they are all added. '
    + 'You can choose several at once.',
};
// The sheets the desk opens over itself: a level's downloads, its Google Docs, and one the
// shared kit asks for.
const DESK_SHEETS = ['desk-download', 'desk-copies', 'desk-kit'];
// The files the runner reads as documents (runner/documents.py).
const DESK_TYPES = ['.txt', '.md', '.html', '.htm', '.docx'];
// The desk's routes, as the shared kit names them: `view` is one card with its parts (the
// whole desk is `drafts`). Note, revise, selection and the rest are served once their jobs
// and Finishing come.
const DESK_ROUTES = { view: 'drafts/card', save: 'drafts/save', versions: 'drafts/versions',
  restore: 'drafts/restore', note: 'drafts/note', revise: 'drafts/revise',
  selection: 'drafts/selection', stop: 'drafts/stop', retry: 'drafts/retry',
  finish: 'drafts/finish', apply: 'drafts/apply', skip: 'drafts/skip',
  proofread: 'drafts/proofread' };

// What this page holds of each desk, by the training's folder: the desk as last read, the
// level shown, whether a phone shows Sources, what the last decision said, and documents the
// start could not add. It outlives a screen change, so a start's documents are still known
// on the desk it opens.
const DESK = { held: {}, kitSheet: [] };

function deskHeld(path) {
  if (!DESK.held[path]) {
    DESK.held[path] = { view: null, level: null, sources: false, said: '', unsent: null,
      drawn: '' };
  }
  return DESK.held[path];
}

// A training started on the desk: the runner's view of its run says so in `flow`.
function onTheDesk(run) {
  return Boolean(run) && run.flow === 'desk';
}

// --- the shared kit, bound to this page -------------------------------------------------
// The kit names each item by one id: here the JSON of [the training's folder, the material's
// name or null]. Its requests are translated to the {path, name} the runner takes, with
// every other field the kit sent, from a query or a body alike.

const NO_ID = 'The desk asked about something it does not name.';

function deskItem(id) {
  let found = null;
  try {
    found = JSON.parse(id);
  } catch (failure) {
    found = null;
  }
  if (!Array.isArray(found) || typeof found[0] !== 'string' || !found[0]
      || (found[1] !== null && typeof found[1] !== 'string')) {
    throw new Error(NO_ID);
  }
  return found[1] ? { path: found[0], name: found[1] } : { path: found[0] };
}

function deskApi(route, data) {
  const [endpoint, query] = String(route).split('?');
  if (!data) {
    const asked = Object.fromEntries(new URLSearchParams(query || ''));
    const { id, ...rest } = asked;
    return ask(endpoint, { ...rest, ...deskItem(id) });
  }
  const { id, ...rest } = data;
  return send(endpoint, { ...deskItem(id), ...rest });
}

// The shared kit is loaded before this script; without it there is no desk to draw.
if (typeof Drafting === 'undefined') {
  throw new Error('Training Studio’s desk needs drafting.js, loaded before drafts.js.');
}

const deskKit = Drafting.kit({
  ui: {
    button: (label, action, kind) => {
      const node = capsule(label, kind === 'filled' ? 'filled' : 'quiet', () => action(node));
      return node;
    },
    card: (title, ...nodes) => add(card(title), ...nodes),
    pickCard: (title, says, action) => add(button('', 'pick-card', action),
      make('span', 'pick-title', title), make('span', 'pick-says', says)),
    choice: (label, options, held, key, changed) => choice(label, options,
      Math.max(0, options.indexOf(held[key])), (index) => {
        held[key] = options[index];
        if (changed) changed();
      }, key),
    disclosure: (label, ...nodes) => add(make('details', 'card-part'), make('summary', '', label),
      ...nodes),
    bead: (kind) => bead(kind),
    openSheet: (title, ...nodes) => {
      DESK.kitSheet = [sheetTitle(title), ...nodes];
      openSheet('desk-kit', '')();
    },
    closeSheet: () => closeSheet(),
    toast: (text) => toast(text),
    notice: (text) => {
      deskHeld(view.path).said = text;
      paintDesk(false);
    },
    busy: async (control, label, action) => {
      const was = control.textContent;
      control.disabled = true;
      control.textContent = label;
      try {
        await action();
      } finally {
        control.disabled = false;
        control.textContent = was;
      }
    },
    narrow: () => narrow(),
  },
  api: deskApi,
  routes: DESK_ROUTES,
  share: () => undefined,
  canEdit: () => deskOurs(),
  current: (held) => view.screen === 'run' && deskItem(held.id).path === view.path,
  page: () => main(),
  hooks: {
    render: () => paintDesk(false),
    refresh: () => paintDesk(false),
    reload: () => drawDesk(false),
    beforeJob: () => undefined,
  },
  parts: {
    title: (found, part) => (list(found.sections).find((one) => one.id === part) || {}).heading
      || '',
    textOf: (found, part) => (list(found.sections).find((one) => one.id === part) || {}).text
      || '',
    nameOf: (found, part) => part,
    single: () => false,
    noted: () => deskOurs(),
  },
  words: () => ({ thing: 'material', sources: {}, doing: {}, steps: {}, named: [],
    withOpening: [], chain: [], ready: () => 'It is on the desk.' }),
  tools: () => [],
  progress: { stopped: () => null, show: () => paintDesk(false) },
});

// --- the start ----------------------------------------------------------------------------

function timeField(draft) {
  return field('new-time', 'How long it should take (optional)', draft, 'time',
    { hint: 'The learner’s time, including examples and practice: “30 minutes” or “a '
      + 'half-day workshop”.' });
}

// The documents, added here before Start and listed with Remove. The page holds the files
// until the training is made; Start then adds each, and says they are all added.
function documentsPart(draft) {
  const node = make('div', 'fields desk-documents');
  const fill = () => {
    const files = list(draft.files);
    const items = make('ul', 'rows');
    for (const file of files) {
      const remove = capsule('Remove', 'quiet', () => {
        draft.files = list(draft.files).filter((one) => one !== file);
        fill();
        retell();
        focusKey('new-documents');
      }, 'remove ' + file.name);
      remove.setAttribute('aria-label', 'Remove ' + file.name);
      items.append(add(make('li', 'row step'), add(make('div', 'row-text'),
        make('p', 'step-name', file.name), make('p', 'quiet', size(Number(file.size) || 0))),
      remove));
    }
    node.replaceChildren();
    add(node, field('new-documents', 'Add documents', {}, '', {
      picked: (input) => {
        const chosen = Array.from(input.files || []);
        const names = chosen.map((file) => file.name);
        // A file chosen again under the same name takes the place of the one held.
        draft.files = [...list(draft.files).filter((file) => !names.includes(file.name)),
          ...chosen];
        input.value = '';
        fill();
        retell();
        focusKey('new-documents');
      },
      accept: DESK_TYPES.join(','), hint: DESK_WORDS.documentsHint }),
    files.length ? add(make('div', 'card-part'), make('p', 'row-title',
      count(files.length, 'document', 'documents') + ' to add'), items) : null,
    make('p', 'quiet', DESK_WORDS.kept));
  };
  fill();
  return node;
}

// Where research looks, in one line, said again whenever a document or a choice changes.
function researchLine(draft, line) {
  draft.research.documents = list(draft.files).length > 0;
  line.textContent = researchProblem(draft)
    || 'Research ' + researchSummary(researchChoice(draft)) + '.';
}

function sourcesStep(draft, brand, looks) {
  const limits = (view.setup && view.setup.limits) || {};
  const drafted = make('p', 'quiet');
  const told = () => {
    drafted.textContent = 'It is drafted by ' + AGENT_NAMES[draft.agent]
      + draftModelWords(draft) + '.';
  };
  told();
  researchLine(draft, looks);
  return [documentsPart(draft), researchFields(draft, retell, ['documents']), looks,
    questionsField(draft), brand, copiesOption(draft),
    trainingOptions('Assistant and limits', 'training-assistant',
      ...agentFields(draft, 'new', 'For this training', told), drafted,
      make('p', 'quiet', limitsSays(limits) || 'No limits are set for this computer.'),
      make('p', 'quiet', 'Limits are changed in Settings.'))];
}

// The new-training sheet: three numbered steps in the order they are filled in, then Start
// and Cancel together. Enter in a box starts it, as the filled button does, after every
// step is checked. There is no review level: nothing stops for the person.
function deskStart() {
  const draft = view.draft;
  const problem = alertLine('new-problem');
  if (draft.start_problem) say(problem, draft.start_problem);
  const status = make('p', 'quiet');
  status.id = 'new-status';
  status.setAttribute('role', 'status');
  status.hidden = true;
  const go = submitButton('Start', 'continue');
  const form = make('form', 'create-flow');
  form.noValidate = true;
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    startTraining(go);
  });
  const [title, topic, audience, purpose] = topicStep(draft);
  const brand = brandOption(draft);
  const looks = make('p', 'quiet research-line');
  // A deck chosen or put away shows or hides its brand, a step on; a document or a source
  // changed says again where research looks.
  draft.retell = () => {
    if (brand) brand.hidden = DECKS[draft.deck][0] === null;
    researchLine(draft, looks);
  };
  add(form,
    createStep(1, DESK_WORDS.steps[0], title, topic, audience, timeField(draft), purpose),
    createStep(2, DESK_WORDS.steps[1], ...shapeStep(draft)),
    createStep(3, DESK_WORDS.steps[2], ...sourcesStep(draft, brand, looks)),
    problem, status,
    add(make('div', 'bar create-foot'), go, capsule('Cancel', 'quiet', closeSheet, 'cancel')));
  return [add(make('div', 'sheet-heading'), sheetTitle('New training')), form];
}

// What Start sends: the form, as a desk training, with no review level.
function deskBody(draft) {
  const deck = DECKS[settleDeck(draft).deck][0];
  return {
    title: draft.title.trim(), topic: draft.topic.trim(), audience: draft.audience.trim(),
    purpose: PURPOSES[draft.purpose],
    levels: LEVELS.filter((level) => draft.levels.includes(level)),
    brief_kind: draft.brief ? 'competitive' : 'product',
    time_limit: draft.time.trim() || null,
    research_from: researchChoice(draft),
    research_questions: (draft.researchQuestions || '').split('\n'),
    deck_target: deck,
    brand: deck ? { brand: draft.brand, variant: draft.variant || null } : null,
    ...(deck ? { delivery: DELIVERIES[draft.delivery || 0][0],
      walkthrough: Boolean(draft.walkthrough) } : {}),
    copies: COPIES.map((kind) => kind[0]).filter((kind) => draft.copies.includes(kind)),
    yoodli: draft.yoodli, materials: draft.materials,
    agent: draft.agent, model: draft.model.trim() || null, effort: draft.effort || null,
    flow: 'desk',
  };
}

// Each held document, added in turn. What could not be added is kept for the desk to offer
// again; once all are in, the runner is told that is all of them and research starts.
async function addHeld(path, files, status) {
  const held = deskHeld(path);
  const left = [];
  const why = [];
  for (const [index, file] of files.entries()) {
    if (status) say(status, 'Adding ' + (index + 1) + ' of ' + files.length + ': ' + file.name);
    try {
      const content = await base64Of(file);
      await send('documents', { path, action: 'add', name: file.name, content });
    } catch (failure) {
      left.push(file);
      why.push(failure.message);
      // With no answer at all, there is nobody to send the rest to.
      if (failure.kind === 'stopped') {
        left.push(...files.slice(index + 1));
        break;
      }
    }
  }
  if (status) say(status, '');
  if (left.length) {
    held.unsent = { files: left, why: why.join(' ') };
    return false;
  }
  return allAdded(path);
}

async function allAdded(path) {
  const held = deskHeld(path);
  try {
    await send('documents', { path, action: 'done' });
  } catch (failure) {
    // With no answer, saying it again is all there is to do. A refusal is the runner's own
    // sentence, said on the desk, whose documents card then shows what is added.
    if (failure.kind === 'stopped') {
      held.unsent = { files: [], why: failure.message };
    } else {
      held.unsent = null;
      held.said = failure.message;
    }
    return false;
  }
  // Said, it carries on: what an earlier attempt was refused for is no longer so.
  held.unsent = null;
  held.said = '';
  return true;
}

async function startOnDesk(pressed) {
  const draft = view.draft;
  if (!draft || draft.starting) return;
  const turn = view.turn;
  const problem = byId('new-problem');
  draft.start_problem = '';
  say(problem, '');
  const files = list(draft.files);
  // The documents research reads are the files held here.
  draft.research.documents = files.length > 0;
  if (!startReady(draft)) return;
  // Somewhere research may look, or it does not start; the runner refuses the same.
  const nowhere = researchProblem(draft);
  if (nowhere) {
    say(problem, nowhere);
    focusKey(draft.research.sites ? 'research-sites' : 'research-web');
    return;
  }
  const asked = questionsProblem(draft.researchQuestions);
  if (asked) {
    say(problem, asked);
    refuse('research-questions', asked).focus();
    return;
  }
  const body = deskBody(draft);
  draft.starting = true;
  pressed.disabled = true;
  const form = byId('sheet').querySelector('form');
  if (form) form.inert = true;
  let started;
  try {
    started = await send('trainings', body);
  } catch (failure) {
    draft.starting = false;
    if (turn !== view.turn || view.draft !== draft) return;
    draft.start_problem = failure.message + (failure.kind === 'stopped' ? ''
      : ' Nothing was started.') + ' Your answers are still here.';
    // A shared preference may have changed. Reload it before another start, keeping every
    // answer.
    const setup = await ask('setup').catch(() => null);
    if (turn !== view.turn || view.draft !== draft) return;
    if (setup) view.setup = setup;
    paintNew();
    focusKey('continue');
    return;
  }
  // Research waits for the documents, so each is added before the desk opens on it.
  const added = files.length ? await addHeld(started.path, files, byId('new-status')) : true;
  if (view.draft === draft) view.draft = null;
  view.sheet = '';
  if (turn !== view.turn) {
    drawSheet();
    refresh();
    return;
  }
  toast(added ? 'Started. It is working on its own now.'
    : 'Started. It waits for your documents.');
  show('run', { path: started.path }, true);
  refresh();
}

// --- the desk -----------------------------------------------------------------------------

function deskOurs() {
  const found = deskHeld(view.path).view;
  return Boolean(found && found.team && found.team.ours !== false)
    && !(view.run && view.run.mine === false);
}

async function drawDesk(fresh) {
  const turn = view.turn;
  const path = view.path;
  const held = deskHeld(path);
  try {
    const found = await ask('drafts', { path });
    if (turn !== view.turn) return;
    held.view = found;
  } catch (failure) {
    if (turn !== view.turn) return;
    unopened(failure, Boolean(held.view), fresh,
      { said: 'Nothing was changed. The training itself is as it was.' });
    if (!held.view) return;
  }
  if (!view.busy && !view.sheet) paintDesk(fresh);
}

// The level a desk shows, and whether a phone shows its Sources in place of the cards.
function deskTabs(found, held) {
  const named = list(found.levels).filter(Boolean);
  if (!named.includes(held.level)) held.level = named[0] || '';
  const phone = narrow();
  if (!phone) held.sources = false;
  const options = phone ? [...(named.length ? named : ['Materials']), 'Sources'] : named;
  const at = held.sources ? options.length - 1 : Math.max(0, named.indexOf(held.level));
  if (options.length < 2) return null;
  return segmented(named.length ? 'Level' : 'Show', options, at, (index) => {
    held.sources = phone && index === options.length - 1;
    if (!held.sources && named.length) held.level = named[index];
    paintDesk(false);
    focusKey('desk-level ' + index);
  }, 'desk-level');
}

function cardTitle(found) {
  const kind = DESK_WORDS.kinds[found.kind] || capital(found.kind);
  const ident = String(found.name).split('@')[0].split(':')[1];
  return ident && ident !== 'main' ? kind + ' “' + ident + '”' : kind;
}

function headingId(name) {
  return 'desk-card-' + String(name).replace(/[^A-Za-z0-9_-]/g, '-');
}

// What was checked for you, from the checks that take milliseconds.
function checkedPart(checks) {
  const passed = Number(checks && checks.passed) || 0;
  const problems = list(checks && checks.problems);
  if (!passed && !problems.length) return null;
  const node = make('div', 'card-part');
  add(node, make('p', 'quiet', 'Checked for you: ' + count(passed, 'check passed', 'checks passed')
    + (problems.length ? '; ' + count(problems.length, 'check', 'checks') + ' did not.' : '.')));
  const said = problems.flatMap((problem) => list(problem.problems).map(String));
  if (said.length) add(node, bullets(said, 'reasons'));
  return node;
}

// What updating a held card makes it again from, in the words of its sentence.
function updateLabel(found) {
  const from = /^Built from an earlier (.+?)\./.exec(found.says || '');
  return from ? 'Update from the ' + from[1] : 'Update it';
}

function deskCard(found) {
  if (found.state === 'left-out') return make('p', 'quiet desk-left-out', found.says);
  const node = card(cardTitle(found), 'desk-card' + (['held', 'needs'].includes(found.state)
    ? ' card-needs' : ''));
  const heading = node.querySelector('.card-title');
  heading.id = headingId(found.name);
  heading.tabIndex = -1;
  node.setAttribute('aria-labelledby', heading.id);
  const actions = list(found.actions);
  const press = (label, route, sent, key) => {
    const control = capsule(label, '', () => deskDecide(route, sent, control), key);
    return control;
  };
  const bar = make('div', 'bar');
  if (actions.includes('ready')) {
    bar.append(press('Mark ready', 'ready', { name: found.name, seen: found.seen },
      'desk-ready ' + found.name));
  }
  if (actions.includes('update')) {
    bar.append(press(updateLabel(found), 'update', { name: found.name },
      'desk-update ' + found.name));
  }
  if (actions.includes('keep')) {
    bar.append(press('Keep as it is', 'keep', { name: found.name, seen: found.seen },
      'desk-keep ' + found.name));
  }
  if (actions.includes('send')) {
    bar.append(press('Send to its copies', 'send', { name: found.name },
      'desk-send ' + found.name));
  }
  if (actions.includes('download')) bar.append(downloadButton(found));
  return add(node, state(DESK_WORDS.beads[found.state] || 'none', found.says),
    checkedPart(found.checks), bar.childNodes.length ? bar : null);
}

function downloadButton(found) {
  const name = String(found.name).replace(/[^A-Za-z0-9._-]+/g, '-')
    + (found.kind === 'deck' ? '.pptx' : '.md');
  const control = capsule('Download', 'quiet', (event) => downloadFile(view.path,
    { artifact: found.name }, name, event.currentTarget), 'desk-download ' + found.name);
  control.setAttribute('aria-label', 'Download ' + found.label);
  return control;
}

// The one line that names the cards needing the person, each a way to its card, then
// anything else that keeps the training from being ready.
function needsPart(found, held, run) {
  const needs = list(found.needs);
  if (!needs.length) return null;
  const cards = list(found.cards);
  const asked = run.question ? 'A question is waiting for you: ' + run.question.text : '';
  const stopped = run.problem ? run.problem.what : '';
  const named = needs.map((need) => cards.find((one) => one.label === need)).filter(Boolean);
  const rest = needs.filter((need) => !cards.some((one) => one.label === need)
    && need !== asked && need !== stopped);
  const node = make('div', 'desk-needs');
  if (named.length) {
    const line = add(make('p', ''), make('strong', '', 'Needs you: '));
    named.forEach((one, index) => {
      if (index) line.append(index === named.length - 1 ? ' and ' : ', ');
      line.append(capsule(capital(one.label), 'quiet', () => {
        held.level = one.level;
        held.sources = false;
        paintDesk(false);
        const heading = byId(headingId(one.name));
        if (heading) heading.focus();
      }, 'desk-jump ' + one.name));
    });
    node.append(line);
  }
  for (const need of rest) node.append(make('p', '', need));
  return node.childNodes.length ? node : null;
}

// The start's progress band, while it works: whether the person is needed, the step in
// hand, and one clock for the whole start. Documents the start could not add come first.
function progressPart(found, held, lead) {
  if (held.unsent) return unsentPart(held, lead === 'unsent');
  const progress = found.progress || {};
  if (!progress.running) return null;
  // The line is blank while something on the desk needs the person.
  const line = progress.line ? make('p', '', progress.line) : null;
  if (line) line.setAttribute('role', 'status');
  return callout('', line, progress.doing ? make('p', 'row-says', progress.doing) : null,
    progress.started_at ? make('p', 'quiet desk-clock', deskKit.clock(progress))
      : null);
}

function unsentPart(held, lead) {
  const path = view.path;
  const files = list(held.unsent.files);
  const again = async (control, sent) => {
    if (view.busy) return;
    const turn = view.turn;
    view.busy = true;
    control.disabled = true;
    const added = sent.length ? await addHeld(path, sent) : await allAdded(path);
    view.busy = false;
    if (turn !== view.turn) return;
    if (added) toast('That is all of them. It carries on from here.');
    paintDesk(false);
    refresh();
  };
  if (!files.length) {
    const done = capsule('That is all of them', lead ? 'filled' : '',
      () => again(done, []), 'desk-all-added');
    return callout('late', make('p', '', 'Your documents are added, but saying that is all '
      + 'of them did not reach Training Studio.'), make('p', 'quiet', held.unsent.why),
    add(make('div', 'bar'), done));
  }
  const names = files.map((file) => file.name);
  const one = files.length === 1;
  const retry = capsule(one ? 'Add it again' : 'Add them again', lead ? 'filled' : '',
    () => again(retry, files), 'desk-add-again');
  const without = capsule(one ? 'Start without it' : 'Start without them', '',
    () => again(without, []), 'desk-without');
  return callout('late', make('p', '', (one ? 'One document could not be added: '
    : count(files.length, 'document', 'documents') + ' could not be added: ') + series(names)
    + (one ? '. Add it again, or start without it.' : '. Add them again, or start without them.')),
  held.unsent.why ? make('p', 'quiet', held.unsent.why) : null,
  add(make('div', 'bar'), retry, without));
}

// The Sources, shared by every level: the account of the research, the research plan and
// the documents.
function sourcesPart(found) {
  const sources = found.sources || {};
  const account = sources.account;
  const node = card('Sources', 'desk-sources');
  if (account) {
    add(node, make('p', '', account.check && account.check.said), make('p', 'quiet', account.read),
      list(account.gaps).length ? add(make('div', 'card-part'),
        make('p', 'row-title', 'What the research could not settle'), bullets(account.gaps))
        : null,
      add(make('details', 'card-part'), make('summary', '', 'Read the research'),
        researchReading(account)));
  } else {
    add(node, make('p', 'quiet', DESK_WORDS.noResearch));
  }
  const plan = list(sources.plan).map((item) => (item && item.question) || String(item || ''))
    .filter(Boolean);
  if (plan.length) {
    add(node, add(make('div', 'card-part'), make('p', 'row-title', 'The research plan'),
      bullets(plan)));
  }
  const documents = list(sources.documents);
  if (documents.length) {
    add(node, add(make('div', 'card-part'), make('p', 'row-title', 'Your documents'),
      bullets(documents.map((one) => one.name + (one.readable === false
        ? ': it could not be read' : '')))));
  }
  const aside = make('aside', 'desk-aside');
  aside.setAttribute('aria-label', 'Sources');
  return add(aside, node);
}

function deskLead(run, held, ours) {
  if (view.sheet || view.after || !ours) return '';
  if (held.unsent) return 'unsent';
  if (run.question) return 'answer';
  if (run.problem && run.problem.action) return 'problem';
  if (adding(run)) return 'documents';
  return 'ready';
}

function paintDesk(fresh) {
  const run = view.run;
  const held = deskHeld(view.path);
  const found = held.view;
  if (!run || !found) return;
  const ours = deskOurs();
  const lead = deskLead(run, held, ours);
  const tabs = deskTabs(found, held);
  const drawn = JSON.stringify([found, run.state, run.question, run.problem, run.documents,
    run.mine, run.driver, run.taken, run.notice, held.level, held.sources, held.said,
    held.unsent && list(held.unsent.files).map((file) => file.name), held.unsent
      && held.unsent.why, lead, narrow()]);
  if (!fresh && drawn === held.drawn) return;
  held.drawn = drawn;
  const named = list(found.levels).filter(Boolean);
  const level = held.level;
  const shown = list(found.cards).filter((one) => (one.level || '') === level);
  const actions = [];
  if (ours) {
    const mark = capsule(named.length ? 'Mark this level ready' : 'Mark every material ready',
      lead === 'ready' ? 'filled' : '', () => markLevel(level, shown, mark), 'desk-level-ready');
    actions.push(mark);
  }
  actions.push(capsule('Download', '', openSheet('desk-download', 'desk-download-all'),
    'desk-download-all'));
  if (ours) {
    actions.push(capsule('Google Doc', '', openSheet('desk-copies', 'desk-copies'),
      'desk-copies'));
  }
  const notice = held.said ? make('p', 'notice', held.said) : null;
  if (notice) notice.setAttribute('role', 'alert');
  const column = add(make('div', 'desk-column'), ...shown.map(deskCard));
  if (!shown.length) column.append(make('p', 'quiet', 'Nothing is made at this level.'));
  const layout = held.sources ? add(make('div', 'desk-layout'), sourcesPart(found))
    : add(make('div', 'desk-layout'), column, narrow() ? null : sourcesPart(found));
  place({ title: found.title || 'Untitled', back: true,
    above: named.length ? [make('span', '', levelsText(named))] : [], actions }, [
    pageHead(DESK_WORDS.lede),
    notice,
    !ours && run.mine === false ? theirsPart(run, !view.sheet && !run.driver) : null,
    ours && run.notice ? noticePart(run) : null,
    ours ? needsPart(found, held, run) : null,
    progressPart(found, held, lead),
    run.question && ours ? questionPart(run, found.title) : null,
    run.problem ? problemPart(run, lead === 'problem') : null,
    adding(run) && ours && !held.unsent ? documentsCard(run, lead === 'documents') : null,
    tabs,
    layout,
  ], fresh);
}

// One of the person's decisions on the desk, answered with the desk again. What it was
// refused for, or where Mark this level ready stopped, is said on the desk.
async function deskDecide(route, sent, pressed) {
  if (view.busy) return null;
  const turn = view.turn;
  const path = view.path;
  const held = deskHeld(path);
  view.busy = true;
  held.said = '';
  if (pressed) pressed.disabled = true;
  let answer = null;
  try {
    answer = await send('drafts/' + route, { path, ...sent });
    if (turn === view.turn) held.view = answer;
  } catch (failure) {
    if (turn === view.turn) held.said = failure.message;
  }
  view.busy = false;
  if (turn !== view.turn) return null;
  if (answer && route === 'level-ready') {
    if (answer.stopped) held.said = answer.stopped.said;
    else if (list(answer.marked).length) {
      toast(count(answer.marked.length, 'material is', 'materials are') + ' marked ready.');
    } else toast('Nothing here was waiting to be marked ready.');
  } else if (answer && route === 'ready') {
    toast('Marked ready.');
  } else if (answer && route === 'keep') {
    toast('Kept as it is.');
  } else if (answer && route === 'update') {
    toast('It is being made again from what it is built from now.');
  } else if (answer && route === 'send') {
    // What Google refused is said by material: {name: sentence}.
    const problems = answer.problems && typeof answer.problems === 'object'
      ? Object.values(answer.problems).filter(Boolean).map(String) : [];
    toast(problems.length ? problems.join(' ') : 'Sent to its copies.');
  }
  if (pressed) pressed.disabled = false;
  if (view.sheet && DESK_SHEETS.includes(view.sheet)) drawSheet();
  paintDesk(false);
  return answer;
}

// Mark this level ready: every card of the level, each with the version shown on it.
function markLevel(level, shown, pressed) {
  const seen = {};
  for (const one of shown) if (one.seen) seen[one.name] = one.seen;
  return deskDecide('level-ready', { level, seen }, pressed);
}

// --- the desk's sheets --------------------------------------------------------------------

function deskSheet(kind) {
  if (kind === 'desk-kit') return DESK.kitSheet;
  const held = deskHeld(view.path);
  const found = held.view || { cards: [] };
  const level = held.level || '';
  const shown = list(found.cards).filter((one) => (one.level || '') === level);
  const where = level ? 'level ' + level : 'this training';
  const close = capsule('Close', 'quiet', closeSheet, 'cancel');
  if (kind === 'desk-download') {
    const ready = shown.filter((one) => list(one.actions).includes('download'));
    const items = make('ul', 'rows');
    for (const one of ready) {
      items.append(add(make('li', 'row step'), add(make('div', 'row-text'),
        make('p', 'step-name', cardTitle(one)), make('p', 'quiet', one.says)),
      downloadButton(one)));
    }
    return [sheetTitle('Download'), make('p', '', 'Each material of ' + where + ', as it stands '
      + 'now. Nothing is marked ready by downloading it.'),
    ready.length ? items : make('p', 'quiet', 'Nothing of ' + where + ' is written yet.'),
    add(make('div', 'bar'), close)];
  }
  const copied = shown.filter((one) => list(one.actions).includes('send'));
  const items = make('ul', 'rows');
  for (const one of copied) {
    const go = capsule('Send', '', () => deskDecide('send', { name: one.name }, go),
      'desk-send ' + one.name);
    go.setAttribute('aria-label', 'Send ' + one.label + ' to its Google Doc');
    items.append(add(make('li', 'row step'), add(make('div', 'row-text'),
      make('p', 'step-name', cardTitle(one)), make('p', 'quiet', one.says)), go));
  }
  return [sheetTitle('Google Doc'), make('p', '', 'Send a material of ' + where + ' to its '
    + 'Google Doc now, as it stands. A Ready material is sent by itself.'),
  copied.length ? items : make('p', 'quiet', 'Nothing of ' + where + ' has a Google Doc '
    + 'waiting for it. A guide or a brief is kept in Google Docs when the training is started '
    + 'with that copy.'),
  add(make('div', 'bar'), close)];
}
