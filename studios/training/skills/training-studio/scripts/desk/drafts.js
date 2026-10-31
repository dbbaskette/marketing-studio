// The training desk: a new training's start in three numbered steps, and one desk per
// training started there. The desk shows the start's progress band, what needs the person,
// the level and material tabs, one section or slide at a time, Research & sources,
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
  beads: { writing: 'current', queued: 'none', decide: 'review', draft: 'none', ready: 'done',
    held: 'late', needs: 'late', 'left-out': 'out' },
  // A material tab's state, as the runner's one standing names it (runner/drafts.py).
  tabs: { writing: 'Writing', queued: 'Not written yet', decide: 'Needs your text approval',
    needs: 'Needs attention', held: 'Needs updating', ready: 'Ready', draft: 'Draft' },
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
const DESK_TYPES = ['.txt', '.md', '.html', '.htm', '.docx', '.pdf'];
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
    DESK.held[path] = { view: null, level: null, sources: false, material: {}, said: '', unsent: null,
      drawn: '', materials: {}, recovery: readDeskRecovery(path) };
  }
  return DESK.held[path];
}

// The way to the person's next action from another screen or from the needs line: its
// level, its material and, for a deck review finding, its slide. Opening never starts work.
function deskGoTo(held, standing, name) {
  const next = standing && standing.next;
  if (!next || !next.material || (name && next.material !== name)) return;
  held.level = next.level || '';
  held.sources = false;
  held.material[held.level] = next.material;
  if (next.slide) {
    held.slide ||= {};
    held.slide[next.material] = next.slide;
  }
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
  const item = deskItem(id), material = deskHeld(item.path).materials[item.name];
  if (endpoint === 'drafts/restore' && Object.keys(material?.pending || {}).length) {
    throw new Error('Save or reload your pending text before restoring a version.');
  }
  if (endpoint === 'drafts/save' && material?.editSeen?.[rest.part] !== undefined) {
    rest.seen = material.editSeen[rest.part];
  }
  if (material?.view.whole && ['drafts/note', 'drafts/revise', 'drafts/layout'].includes(endpoint)) {
    rest.seen = material.view.seen;
  }
  const body = { ...item, ...rest };
  return send(endpoint, body, endpoint === 'drafts/save' && smallDeskSave(body)
    ? { keepalive: true } : {});
}

// The shared kit is loaded before this script; without it there is no desk to draw.
if (typeof Drafting === 'undefined') {
  throw new Error('Training Studio’s desk needs drafting.js, loaded before drafts.js.');
}

const deskKit = Drafting.kit({
  ui: {
    button: (label, action, kind) => {
      const node = capsule(label, kind === 'filled' && view.sheet ? 'filled' : 'quiet', () => action(node));
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
  share: (id) => send('drafts/share', { path: deskItem(id).path }),
  canEdit: (held) => deskCanChange() && !held.view.readonly,
  current: (held) => view.screen === 'run' && deskItem(held.id).path === view.path,
  page: () => main(),
  hooks: {
    saved: (held, part) => {
      // Only an acknowledged save of our text advances an outstanding edit's basis.
      if (held.pending[part]) held.editSeen[part] = held.view.revision;
      else if (held.editSeen) delete held.editSeen[part];
      if (!held.pending[part] && held.recoveredParts) delete held.recoveredParts[part];
      keepDeskRecovery(deskItem(held.id).path);
      if (held.view.desk) {
        // A save to a Ready material makes it a draft again: said once, as it happens.
        const desk = deskHeld(deskItem(held.id).path), name = deskItem(held.id).name;
        const was = list(desk.view?.cards).find((one) => one.name === name);
        const now = list(held.view.desk.cards).find((one) => one.name === name);
        desk.view = held.view.desk;
        if (was?.state === 'ready' && now && now.state !== 'ready') {
          toast(backToDraftWords(now, held.view.desk));
          // Drawn again at once, the typing kept where it is, so the card says Draft.
          deskMaterialChanged(held);
        }
      }
    },
    render: (held) => deskMaterialChanged(held),
    refresh: (held) => deskMaterialChanged(held),
    reload: async (held) => {
      held.view = await ask('drafts/card', deskItem(held.id));
      held.pending = {}; held.editSeen = {}; held.recoveredParts = {};
      keepDeskRecovery(deskItem(held.id).path);
      held.stale = false; held.saved = '';
      deskMaterialChanged(held);
    },
    beforeJob: (held) => {
      if (Object.keys(held.pending).length || pendingDeckWords(held)) throw new Error('Save your text before starting a change.');
    },
    extra: (held, part) => {
      const section = list(held.view.sections).find((one) => one.id === part);
      return section && list(section.covers).length
        ? make('p', 'quiet', 'Covers ' + section.covers.join(', ')) : null;
    },
  },
  parts: {
    title: (found, part) => part === 'opening' ? (found.whole ? 'Whole file' : 'Opening') : part === 'title' ? 'Title'
      : (list(found.sections).find((one) => one.id === part) || {}).heading || '',
    textOf: (found, part) => part === 'opening' ? found.opening || '' : part === 'title'
      ? found.title || '' : (list(found.sections).find((one) => one.id === part) || {}).text || '',
    nameOf: (found, part) => part === 'opening' ? (found.whole ? 'Whole file' : 'Opening')
      : (list(found.sections).find((one) => one.id === part) || {}).heading || 'this section',
    single: (part) => part === 'title',
    noted: (found) => deskCanChange() && !found.readonly && !found.whole && found.kind !== 'blueprint',
  },
  words: () => ({ thing: 'material', sources: { save: 'Saved', rewrite: 'Rewritten',
    google: "Before Google's text", earlier: 'An earlier version', restore: 'Restored',
    selection: 'Selection', finishing: 'Finishing', 'revise-all': 'Revised with the whole note' }, doing: {}, steps: {}, named: [],
    withOpening: [], chain: [], ready: () => 'It is on the desk.' }),
  tools: () => finishingTools(),
  progress: { stopped: () => null, show: () => paintDesk(false) },
});

const FINISHING_TOOLS = [
  { key: 'sources', name: 'Check against sources', kinds: ['document', 'brief'], run: 'Check against sources',
    says: 'Check each claim against the saved research. This does not run research.',
    verdicts: { supported: 'Supported', 'not in the sources': 'Not in the sources', contradicted: 'Contradicted' } },
  { key: 'time', name: 'Fit the learner’s time', kinds: ['document', 'deck'], run: 'Fit the time',
    says: 'Propose cuts or additions for the time in your intake.' },
  { key: 'answers', name: 'Check the answer key', kinds: ['document'], run: 'Check answers',
    says: 'Explain why each answer is right and a plausible alternative is wrong.' },
  { key: 'humanize', name: 'Humanize', kinds: ['document', 'brief'], run: 'Humanize wording',
    says: 'Make the wording natural while keeping facts and references.', start: { level: 'medium' },
    data(f) { return { level: f.level }; } },
  { key: 'level', name: 'Level check', kinds: ['document', 'brief'], run: 'Check the level',
    says: 'Find passages that teach what an earlier level already taught.' },
  { key: 'proofread', name: 'Proofread', kinds: ['document', 'brief'], run: 'Proofread',
    says: 'Mechanical checks, sentence by sentence. Fix rewrites only that sentence.' },
  { key: 'coverage', name: 'Coverage', kinds: ['document'], run: 'Check coverage',
    says: 'Objectives and key points no section teaches.' },
  { key: 'claims', name: 'Claims with no reference', kinds: ['document', 'brief'], run: 'Check references',
    says: 'Sentences that state a fact with no reference.' },
  { key: 'practice', name: 'Scenario format', kinds: ['scenario'], run: 'Check scenario format',
    says: 'What each scenario is missing for Yoodli.' },
  { key: 'yoodli', name: 'Yoodli limits', kinds: ['yoodli'], run: 'Check Yoodli limits',
    says: 'Fields over Yoodli’s limits.' },
].map((tool) => ({ ...tool, doing: 'Checking…', empty: 'Nothing found by this check.' }));

function pendingDeckWords(material) {
  if (material.view.kind !== 'deck') return false;
  const held = deskHeld(deskItem(material.id).path);
  return Object.keys(held.slideText || {}).some((key) => key.startsWith(material.view.name + ':'));
}

function finishingMaterial() {
  const held = deskHeld(view.path);
  return Object.values(held.materials).find((material) => material.finish
    && (material.view.level || '') === held.level && material.view.name === held.material[held.level]);
}

function finishingTools() {
  const kind = finishingMaterial()?.view.kind;
  return FINISHING_TOOLS.filter((tool) => !kind || tool.kinds.includes(kind)).map((tool) => ({
    ...tool, options: (held, f) => {
      const price = held.view.finish_prices?.[tool.key];
      const rows = price ? [make('p', 'quiet', 'Expect about ' + Math.max(1, Math.round(price.minutes)) + ' minutes.')] : [];
      const job = held.view.working;
      if (job?.kind === 'finish-' + tool.key) {
        const stop = capsule('Stop check', 'quiet', () => stopDeskChange(held, job.id, stop));
        rows.push(stop);
      }
      if (tool.key === 'humanize') {
        rows.push(segmented('Humanize level', ['Light', 'Medium', 'Strong'],
          ['light', 'medium', 'strong'].indexOf(f.level || 'medium'), (index) => {
            f.level = ['light', 'medium', 'strong'][index]; deskKit.panelShow(held);
          }, 'humanize-level'));
      }
      return rows;
    },
  }));
}

// Finishing opens on the material in front of the person, with no second choice; All
// materials is the way to another material of the level. `choose` asks which.
function openFinishing(choose = false) {
  const held = deskHeld(view.path);
  const choices = Object.values(held.materials).filter((material) =>
    (material.view.level || '') === held.level && !material.view.readonly
      && FINISHING_TOOLS.some((tool) => tool.kinds.includes(material.view.kind)));
  const open = (material) => {
    for (const other of Object.values(held.materials)) other.finish = null;
    held.sources = false;
    held.material[held.level] = material.view.name;
    closeSheet(); deskKit.finishOpen(material);
  };
  const current = !held.sources && choices.find((material) =>
    material.view.name === held.material[held.level]);
  if (!choose && current) { open(current); return; }
  if (choices.length === 1) { open(choices[0]); return; }
  DESK.kitSheet = [sheetTitle('Finishing'), make('p', '', 'Choose the material to check.'),
    make('h3', 'sheet-part', '1. Choose a material'),
    ...choices.map((material) => capsule(cardTitle(material.view), 'quiet', () => open(material))),
    choices.length ? null : make('p', '', 'A guide, brief, practice or Yoodli layout opens here once it is written.'),
    capsule('Cancel', 'quiet', () => closeSheet())].filter(Boolean);
  openSheet('desk-kit', '')();
}

// Before/after are labels inside a proposal card, keeping one heading level per card.
const finishingSides = deskKit.sides;
deskKit.sides = (before, after) => {
  const sides = finishingSides(before, after);
  for (const label of sides.querySelectorAll('h4')) label.replaceWith(make('p', 'sheet-part', label.textContent));
  return sides;
};

const finishingProposal = deskKit.proposal;
deskKit.proposal = (held, set, item, key) => {
  if (!item.instruction) {
    const card = finishingProposal(held, set, item, key);
    if (!('after' in item) && item.state === 'open' && item.present && held.finish.editing[item.id] === undefined) {
      const apply = capsule('Apply', 'quiet', () => deskKit.apply(held, set, [{ id: item.id }], apply));
      apply.disabled = !deskCanChange() || !!held.view.working || !!held.view.readonly;
      card.append(add(make('div', 'bar'), apply));
    }
    return card;
  }
  const card = add(make('section', 'card desk-proposal'),
    make('h3', 'card-title', item.note), make('p', 'quiet', item.instruction));
  if (item.state !== 'open') return add(card, make('p', 'quiet', 'Skipped.'));
  const apply = capsule('Apply', 'quiet', () => deskKit.apply(held, set, [{ id: item.id }], apply));
  apply.disabled = !deskCanChange() || !!held.view.working || !!held.view.readonly || !item.present;
  const skip = capsule('Skip', 'quiet', () => deskKit.skip(held, set, [item.id], skip));
  skip.disabled = !deskCanChange();
  return add(card, !item.present ? make('p', 'quiet', 'This part changed since the check. Check again.') : null,
    add(make('div', 'bar'), apply, skip));
};

deskKit.apply = async (held, set, items, control) => {
  control.disabled = true;
  try {
    await deskKit.flush(held);
    if (held.stale || Object.keys(held.pending).length || pendingDeckWords(held)) throw new Error('Save your text before applying a suggestion.');
    held.view = await deskApi('drafts/apply', { id: held.id, seen: held.view.revision, job: set.job, items });
    for (const item of items) delete held.finish.editing[item.id];
    if (held.view.slide_result) {
      const found = held.view.desk.cards.find((card) => card.name === held.view.name);
      const sent = held.view.slide_edit, slide = found.slides.find((one) => one.id === sent.slide);
      await slideWordResult(found, slide, sent, held.view.slide_result, () => { deskMaterialChanged(held); });
      deskMaterialChanged(held);
      return;
    }
    const note = held.view.note;
    if (note) {
      // Existing author notes survive a proposal handoff, just as pending text does.
      if (held.view.whole) held.wholeNote = [held.wholeNote, note.text].filter(Boolean).join('\n');
      else held.notes[note.part] = [held.notes[note.part], note.text].filter(Boolean).join('\n');
      held.finish = null;
      toast('The note is ready to edit. Rewrite when you are ready.');
    } else toast(held.view.queued ? 'The sentence fix was requested.' : 'Applied. The earlier text is in History.');
    deskMaterialChanged(held);
    if (note) focusKey(held.id + ':' + (held.view.whole ? 'whole-note' : note.part + ':note'));
    deskKit.watch(held);
  } catch (error) {
    deskHeld(view.path).said = error.message;
    deskHeld(view.path).drawn = ''; paintDesk(false);
  } finally { control.disabled = false; }
};

// Plan changes are whole-plan jobs; its parts can be typed but not sent as jobs.
const selectDeskPart = deskKit.selected;
deskKit.selected = (held, part, input) => {
  if (held.view.kind !== 'blueprint' && !held.view.whole) selectDeskPart(held, part, input);
};

// A pending edit keeps the revision of the text the person actually saw. Job polling
// may replace the card view, but must never rebase text whose save was refused.
// Recovery is reviewed part by part. Every kit save path (timer, flush, History and
// polling) goes through this guard; typing one part never authorizes another.
function hasDeskRecovery(held) { return Object.keys(held.recoveredParts || {}).length > 0; }
const saveDeskPart = deskKit.save;
deskKit.save = (held, part) => held.recoveredParts?.[part]
  ? Promise.resolve() : saveDeskPart(held, part);
const typeDeskPart = deskKit.typed;
deskKit.typed = (held, part, text) => {
  held.editSeen = held.editSeen || {};
  if (held.editSeen[part] === undefined) held.editSeen[part] = held.view.revision;
  if (held.recoveredParts) delete held.recoveredParts[part];
  typeDeskPart(held, part, text);
  keepDeskRecovery(deskItem(held.id).path);
};

const RECOVERY_PREFIX = 'training-studio-unsaved:';
let recoverySequence = 0;
function recoveryPrefix(path) { return RECOVERY_PREFIX + encodeURIComponent(path) + ':'; }
function readDeskRecovery(path) {
  const edits = [];
  try {
    const storage = window.localStorage, prefix = recoveryPrefix(path);
    for (let index = 0; index < storage.length; index++) {
      const key = storage.key(index);
      if (!key?.startsWith(prefix)) continue;
      // One damaged entry must not hide other sessions' recoverable text.
      try {
        const edit = JSON.parse(storage.getItem(key));
        if (edit && typeof edit.name === 'string' && typeof edit.part === 'string'
            && typeof edit.text === 'string' && Number.isInteger(edit.seen)
            && typeof edit.session === 'string' && Number.isFinite(edit.at)) {
          edits.push({ ...edit, recoveryKey: key });
        }
      } catch (_) { /* Keep unreadable entries untouched. */ }
    }
  } catch (_) { /* Storage may be unavailable in this browser. */ }
  return edits.sort((left, right) => left.at - right.at);
}
function pendingDeskEdits(path) {
  const held = DESK.held[path];
  const edits = (held.recovery || []).filter((edit) => !held.materials[edit.name]);
  for (const material of Object.values(held.materials)) {
    for (const [part, pending] of Object.entries(material.pending)) edits.push({
      ...deskItem(material.id), part, text: pending.text,
      seen: material.editSeen?.[part] ?? material.view.revision, session: material.session });
  }
  return edits;
}
function keepDeskRecovery(path) {
  try {
    const held = DESK.held[path], storage = window.localStorage;
    for (const material of Object.values(held.materials)) {
      material.recoveryOwn ||= {};
      material.recoveryFrom ||= {};
      for (const [part, pending] of Object.entries(material.pending)) {
        if (material.recoveredParts?.[part] && material.recoveryFrom[part]
            && storage.getItem(material.recoveryFrom[part]) !== null) continue;
        const edit = { ...deskItem(material.id), part, text: pending.text,
          seen: material.editSeen?.[part] ?? material.view.revision, session: material.session };
        const serialized = JSON.stringify(edit), previous = material.recoveryOwn[part];
        if (previous?.serialized === serialized && storage.getItem(previous.key) !== null) continue;
        // Immutable snapshots let another tab acknowledge exactly what it recovered,
        // without deleting newer typing from the original session. Write before removing.
        const key = recoveryPrefix(path) + encodeURIComponent(material.session) + ':'
          + Date.now() + ':' + (++recoverySequence);
        storage.setItem(key, JSON.stringify({ ...edit, at: Date.now() }));
        material.recoveryOwn[part] = { key, serialized };
        if (previous) storage.removeItem(previous.key);
      }
      for (const part of new Set([...Object.keys(material.recoveryOwn),
        ...Object.keys(material.recoveryFrom)])) {
        if (material.pending[part]) continue;
        // Only an acknowledged save or explicit Reload clears this session's entries.
        const keys = [material.recoveryOwn[part]?.key, material.recoveryFrom[part]].filter(Boolean);
        for (const key of keys) storage.removeItem(key);
        held.recovery = held.recovery.filter((edit) => !keys.includes(edit.recoveryKey));
        delete material.recoveryOwn[part];
        delete material.recoveryFrom[part];
      }
    }
    return true;
  } catch (_) { return false; }
}
function recoverDeskMaterial(path, material) {
  const name = deskItem(material.id).name;
  for (const edit of deskHeld(path).recovery.filter((edit) => edit.name === name)) {
    material.pending[edit.part] = { text: edit.text };
    material.editSeen = { ...material.editSeen, [edit.part]: edit.seen };
    material.recoveryFrom = { ...material.recoveryFrom, [edit.part]: edit.recoveryKey };
    material.recoveredParts = { ...material.recoveredParts, [edit.part]: true };
    material.saved = 'Recovered unsaved text. Review it before saving.';
  }
}
function smallDeskSave(body) {
  // Fetch keepalive has a 64 KiB shared queue. Large edits remain in browser recovery.
  return new TextEncoder().encode(JSON.stringify(body)).length <= 60000;
}

// Start every pending write during pagehide itself, not after awaiting another request.
// Unacknowledged text stays in browser recovery, including conflicts, network failures,
// keepalive queue overflow and edits too large for the browser's keepalive allowance.
function leaveDesk(path) {
  const held = DESK.held[path];
  if (!held) return;
  keepDeskRecovery(path);
  const edits = pendingDeskEdits(path);
  const requests = edits.map((edit) => {
    const material = held.materials[edit.name];
    if (!material || material.recoveredParts?.[edit.part]) return Promise.reject(
      new Error('Review recovered text before saving it.'));
    if (material?.pending[edit.part]?.timer) clearTimeout(material.pending[edit.part].timer);
    const body = { ...edit, path };
    if (!smallDeskSave(body)) return Promise.reject(new Error('This edit is too large to save while closing.'));
    return send('drafts/save', body, { keepalive: true }).then((answer) => {
      if (material && material.pending[edit.part]?.text === edit.text) {
        delete material.pending[edit.part];
        if (material.editSeen) delete material.editSeen[edit.part];
        material.view = answer;
        material.saved = 'Saved.';
      }
      keepDeskRecovery(path);
    });
  });
  return Promise.allSettled(requests).then(async (results) => {
    if (results.some((one) => one.status === 'rejected') || pendingDeskEdits(path).length) {
      held.said = 'Some text could not be saved. It is kept in this browser; return to this training to save it.';
      if (!keepDeskRecovery(path)) held.said = 'Some text could not be saved or kept in this browser. Keep this page open and copy your text.';
      if (view.path === path && view.screen === 'run') paintDesk(false);
      return;
    }
    try { await send('drafts/share', { path }, { keepalive: true }); }
    catch (_) { held.said = 'Your text was saved, but sharing did not finish.'; }
  });
}

async function stopDeskChange(material, job, control) {
  control.disabled = true;
  try {
    material.view = await send('drafts/stop', { path: deskItem(material.id).path, job });
    deskMaterialChanged(material);
  } catch (error) { deskHeld(view.path).said = error.message; paintDesk(false); }
  finally { control.disabled = false; }
}

// --- the start ----------------------------------------------------------------------------

function timeField(draft) {
  return field('new-time', 'How long it should take (optional)', draft, 'time',
    { hint: 'The learner’s time, including examples and practice: “30 minutes” or “a '
      + 'half-day workshop”.' });
}

// The documents, added here before Start and listed with Remove. The page holds the files
// until the training is made; Start then adds each, and says they are all added.
// With `keep`, the Keep in library choice is offered for what is added (Add a source).
function documentsPart(draft, changed = retell, keep = false) {
  const node = make('div', 'fields desk-documents');
  const fill = () => {
    const files = list(draft.files);
    const items = make('ul', 'rows');
    for (const file of files) {
      const remove = capsule('Remove', 'quiet', () => {
        draft.files = list(draft.files).filter((one) => one !== file);
        fill();
        changed();
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
        changed();
        focusKey('new-documents');
      },
      accept: DESK_TYPES.join(',') + ',application/pdf', hint: DESK_WORDS.documentsHint }),
    files.length ? add(make('div', 'card-part'), make('p', 'row-title',
      count(files.length, 'document', 'documents') + ' to add'), items) : null,
    keep ? keepChoice('new-documents-keep') : null, make('p', 'quiet', DESK_WORDS.kept));
  };
  fill();
  return node;
}

// Where research looks, in one line, said again whenever a document or a choice changes.
function researchLine(draft, line) {
  if (draft.sourceEditor) {
    const chosen = draft.sourceEditor.choice();
    draft.research = {documents: chosen.documents, sites: Boolean(chosen.sites.length), web: chosen.web, picked: chosen.sites, added: []};
  } else draft.research.documents = list(draft.files).length > 0;
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
  if (!draft.sourceEditor && typeof StudioResearch !== 'undefined') {
    // Training Studio offers Keep in library for each file the editor captures.
    draft.sourceEditor = new StudioResearch.Editor({request: sent => send('research-sources', sent), keepChoice: true,
      onChange: () => { if (draft.retell) draft.retell(); }});
  }
  return [draft.sourceEditor ? draft.sourceEditor.node : documentsPart(draft, retell, true),
    ...(draft.sourceEditor ? [] : [researchFields(draft, retell, ['documents'])]), looks,
    questionsField(draft), brand, copiesOption(draft),
    trainingOptions('Assistant and limits', 'training-assistant',
      ...agentFields(draft, 'new', 'For this training', told), drafted,
      make('p', 'quiet', limitsSays(limits) || 'No limits are set for this computer.'),
      make('p', 'quiet', 'Limits are changed in Settings.'))];
}

// The new-training sheet: three numbered steps in the order they are filled in, then Start
// and Cancel together. The runner prepares one topics review before building the
// selected materials. Saved runs keep their original review behavior.
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
    research_from: draft.sourceEditor ? draft.sourceEditor.choice() : researchChoice(draft),
    ...(draft.sourceEditor ? {research_inputs: draft.sourceEditor.spec()} : {}),
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
      await send('documents', { path, action: 'add', name: file.name, content,
        keep: keepUploads() });
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

// Ownership still permits explicit Ready; page typing and jobs require runner ownership.
function deskCanChange() {
  return deskOurs() && deskHeld(view.path).view?.execution !== 'conversation';
}

async function drawDesk(fresh) {
  const turn = view.turn;
  const path = view.path;
  const held = deskHeld(path);
  try {
    const found = await ask('drafts', { path });
    if (turn !== view.turn) return;
    held.view = found;
    await loadDeskMaterials(path, held, found);
    if (turn !== view.turn) return;
  } catch (failure) {
    if (turn !== view.turn) return;
    unopened(failure, Boolean(held.view), fresh,
      { said: 'Nothing was changed. The training itself is as it was.' });
    if (!held.view) return;
  }
  if (!view.busy && !view.sheet) paintDesk(fresh);
}

// Each editable material keeps its own revision and pending typing across redraws.
async function loadDeskMaterials(path, held, found) {
  await Promise.all(list(found.cards).filter((one) =>
    ['blueprint', 'document', 'brief', 'scenario', 'yoodli', 'deck'].includes(one.kind) && one.seen)
    .map(async (one) => {
      let heldMaterial = held.materials[one.name];
      // A pending save owns its revision until it succeeds or explicitly reloads.
      if (heldMaterial && (heldMaterial.saving || Object.keys(heldMaterial.pending).length
          || heldMaterial.stale)) return;
      try {
        const material = await ask('drafts/card', { path, name: one.name });
        if (!Number.isInteger(material.revision)) return;
        heldMaterial = held.materials[one.name];
        if (heldMaterial) {
          // Typing may have started while this request was in flight.
          if (heldMaterial.saving || Object.keys(heldMaterial.pending).length
              || heldMaterial.stale) return;
          if (JSON.stringify(heldMaterial.view) !== JSON.stringify(material)) held.drawn = '';
          heldMaterial.view = material;
        } else {
          held.materials[one.name] = { id: JSON.stringify([path, one.name]), view: material,
          pending: {}, notes: {}, session: String(Date.now()) + Math.random(), tab: 'draft' };
          recoverDeskMaterial(path, held.materials[one.name]);
        }
      } catch (_) { /* A material still being written has no editor yet. */ }
    }));
}

function deskMaterialChanged(material) {
  const item = deskItem(material.id), held = deskHeld(item.path);
  if (material.view.desk) held.view = material.view.desk;
  held.drawn = '';
  if (view.path === item.path && view.screen === 'run') paintDesk(false);
}

async function shareDesk(path) {
  const held = DESK.held[path];
  if (!held || !Object.keys(held.materials).length) return;
  try {
    await flushDesk(held);
    await send('drafts/share', { path }, { keepalive: true });
  } catch (_) { /* The next change will share what remains. */ }
}

// The level a desk shows, and whether a phone shows its Sources in place of the cards.
// Where the level shown stands, from the runner's one standing: how many of its materials
// are Ready, still to write, drafts to mark ready, or need attention or a decision. A
// material is Ready on its own; the level is complete once all of its materials are.
function levelStanding(found, level) {
  const counts = found.standing && found.standing.levels && found.standing.levels[level || ''];
  if (!counts || !counts.materials) return null;
  const parts = [counts.ready + ' of ' + count(counts.materials, 'material', 'materials')
    + ' ready'];
  if (counts.to_write) parts.push(counts.to_write + ' still to write');
  if (counts.drafts) parts.push(count(counts.drafts, 'draft', 'drafts') + ' to mark ready');
  if (counts.attention) parts.push(counts.attention + (counts.attention === 1 ? ' needs'
    : ' need') + ' attention');
  if (counts.decision) parts.push(counts.decision + (counts.decision === 1 ? ' waits'
    : ' wait') + ' for your decision');
  const whole = counts.ready === counts.materials
    ? (level ? 'This level is complete.' : 'Every material is ready.')
    : (level ? 'This level is complete' : 'The training is complete')
      + ' once every material is ready. Ready is your approval of the version you read; a '
      + 'material is still changed, checked or downloaded on its own, and Google Docs are '
      + 'optional.';
  const node = make('p', 'quiet desk-level-standing', (level ? 'Level ' + level + ': ' : '')
    + parts.join(' · ') + '. ' + whole);
  node.setAttribute('role', 'status');
  return node;
}

function deskTabs(found, held) {
  const named = list(found.levels).filter(Boolean);
  if (!named.includes(held.level)) held.level = named[0] || '';
  if (named.length < 2) return null;
  return segmented('Level', named, Math.max(0, named.indexOf(held.level)), (index) => {
    held.sources = false;
    held.level = named[index];
    paintDesk(false);
    focusKey('desk-level ' + index);
  }, 'desk-level');
}

// One material at a time. Reading navigation never approves or starts work.
function workspaceTabs(label, options, selected, choose, key) {
  const bar = make('div', 'desk-workspace-tabs');
  bar.setAttribute('role', 'tablist'); bar.setAttribute('aria-label', label);
  options.forEach((option, index) => {
    const go = capsule(option.label, 'quiet', () => {
      choose(option.id); byId(key + '-' + index)?.focus();
    }, key + ' ' + index);
    go.setAttribute('role', 'tab'); go.id = key + '-' + index;
    go.setAttribute('aria-selected', String(option.id === selected));
    go.tabIndex = option.id === selected ? 0 : -1;
    go.setAttribute('aria-controls', key + '-panel');
    go.addEventListener('keydown', event => {
      const step = {ArrowRight: 1, ArrowLeft: -1}[event.key];
      if (!step && !['Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1
        : (index + step + options.length) % options.length;
      choose(options[next].id); byId(key + '-' + next)?.focus();
    });
    bar.append(go);
  });
  return bar;
}

function workspacePanel(key, index, node) {
  const panel = make('section', 'stack'); panel.id = key + '-panel';
  panel.setAttribute('role', 'tabpanel'); panel.setAttribute('aria-labelledby', key + '-' + index);
  return add(panel, node);
}

function cardTitle(found) {
  const kind = DESK_WORDS.kinds[found.kind] || capital(found.kind);
  const ident = String(found.name).split('@')[0].split(':')[1];
  return ident && ident !== 'main' ? kind + ' “' + ident + '”' : kind;
}

function headingId(name) {
  return 'desk-card-' + String(name).replace(/[^A-Za-z0-9_-]/g, '-');
}

// What a material is called in a sentence: "this guide", "the plan".
function deskNoun(found) {
  return { blueprint: 'plan', document: 'guide', brief: 'brief', deck: 'deck',
    scenario: 'scenario', yoodli: 'Yoodli layout' }[found.kind] || 'material';
}

// What Mark this level ready would mark: the level's drafts, each with the version shown.
function levelWaiting(cards) {
  return list(cards).filter(one => one.state === 'draft' && one.seen);
}

function levelCanBeReviewed(cards) {
  const selected = list(cards).filter(one => one.state !== 'left-out');
  return selected.length > 0 && selected.every(one => one.seen && ['draft', 'ready'].includes(one.state));
}

function levelMaterialsAvailable(cards) {
  const selected = list(cards).filter(one => one.state !== 'left-out');
  return selected.length > 0 && selected.every(one => one.seen && one.state !== 'writing');
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
  const levelCards = list(deskHeld(view.path).view?.cards).filter(one => (one.level || '') === (found.level || ''));
  if (actions.includes('ready') && (deskHeld(view.path).view?.execution === 'conversation'
    || levelMaterialsAvailable(levelCards))) {
    bar.append(press('Mark ready', 'ready', { name: found.name, seen: found.seen },
      'desk-ready ' + found.name));
  }
  // The way back from Ready, on purpose: quiet, and bound to the version shown. What the
  // Document Library keeps is said beside it.
  if (actions.includes('draft')) {
    const back = capsule('Return to draft', 'quiet', () => deskDecide('draft',
      { seen: { [found.name]: found.seen } }, back), 'desk-draft ' + found.name);
    if ((deskHeld(view.path).view?.library || {})[found.name]?.state === 'kept') {
      back.setAttribute('aria-describedby', headingId(found.name) + '-library');
    }
    bar.append(back);
  }
  if (actions.includes('update')) {
    const update = capsule(updateLabel(found), '', () => {
      if (['document', 'brief', 'deck'].includes(found.kind)) previewUpdate(found);
      else deskDecide('update', { name: found.name }, update);
    }, 'desk-update ' + found.name);
    bar.append(update);
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
  // A deck waiting for its slide text to be approved: nothing is writing it, and the one
  // way on is the decision, which this takes the person straight to.
  const text = view.run && view.run.outline;
  if (found.state === 'decide' && text && text.content_first && text.waiting) {
    // Quiet: the approval itself holds the screen's one filled button.
    bar.append(capsule('Review slide text', 'quiet', () => {
      const review = byId('slide-text-review');
      const title = review && review.querySelector('h2, h3');
      if (title) { title.tabIndex = -1; title.focus(); }
    }, 'desk-text ' + found.name));
  }
  const material = deskHeld(view.path).materials[found.name];
  if (material && found.kind === 'document' && deskCanChange() && !material.view.readonly) {
    const menu = make('details', 'menu'); menu.dataset.key = 'whole-menu ' + found.name;
    const again = capsule('Write the whole guide again', 'quiet', () => {
      menu.open = false;
      return deskKit.job(material, again, 'drafts/write-whole', {});
    });
    again.disabled = !!material.view.working;
    bar.append(add(menu, make('summary', 'button button-quiet', 'Guide actions'),
      add(make('div', 'menu-list'), again)));
  }
  const editing = found.kind === 'deck' ? deckParts(found) : material ? materialParts(material, found) : null;
  add(node, state(DESK_WORDS.beads[found.state] || 'none', found.says),
    checkedPart(found.checks), bar.childNodes.length ? bar : null, deskLibraryKept(found));
  if (list(found.needs).length) add(node, add(make('details', 'card-part'),
    make('summary', '', 'Detailed review notes'), bullets(found.needs, 'reasons')));
  if (found.kind === 'blueprint') add(node, updateChainPart(found.level));
  return editing ? add(make('div', 'desk-material-group stack'), node, editing) : node;
}

function updateChainPart(level) {
  if (!deskCanChange()) return null;
  const updates = deskHeld(view.path).view?.sources?.updates;
  if (!updates) return null;
  const chain = updates.chain;
  if (chain?.status === 'working' && (level === undefined || chain.level == null || chain.level === level)) {
    const stop = capsule('Stop updates', 'quiet', () =>
      deskDecide('stop-updates', { chain: chain.id }, stop, { flush: false }));
    return add(make('div', 'card-part'),
      make('p', 'quiet', 'Updating in order. Stop leaves the update under way to finish.'), stop);
  }
  const preview = level === undefined ? updates.all : updates.levels?.[level];
  if (!preview?.names?.length || updates.busy) return null;
  const label = level === undefined ? 'Update every level' : 'Update everything below';
  return add(make('div', 'card-part'), bullets(preview.names),
    make('p', 'quiet', preview.price), capsule(label, 'quiet', async () => {
      const path = view.path;
      try {
        await flushDesk(deskHeld(path));
        const fresh = await ask('drafts', { path });
        if (view.path !== path) return;
        deskHeld(path).view = fresh;
        const priced = level === undefined ? fresh.sources?.updates?.all
          : fresh.sources?.updates?.levels?.[level];
        if (!priced?.names?.length) throw new Error('Nothing needs updating now.');
        const go = capsule('Update', 'filled', async () => {
          const result = await deskDecide('update-all', level === undefined ? {} : { level }, go);
          if (result) closeSheet();
        });
        DESK.kitSheet = [sheetTitle(label), make('h3', 'sheet-part', '1. Materials to update'),
          bullets(priced.names), make('p', 'quiet', 'Newly affected materials follow in order. You can stop the waiting updates.'),
          make('h3', 'sheet-part', '2. Estimated price'), make('p', '', priced.price),
          add(make('div', 'bar'), go, capsule('Cancel', 'quiet', () => closeSheet()))];
        openSheet('desk-kit', '')();
      } catch (failure) {
        deskHeld(path).said = failure.message;
        paintDesk(false);
      }
    }));
}

// Slide cards keep their writing opaque; approval, History and looks use the shared sheet.
function slidePicture(found, number, section) {
  return pictureAt({ path: view.path, artifact: found.name, number,
    ...(section ? { section } : {}) }, section ? 'Look sample ' + number : 'Slide ' + number,
    found.seen, { again: true });
}

function slideWordsText(value) {
  return typeof value === 'object' && value ? value.text || '' : value || '';
}

function slideWordsLines(words) {
  return [words.title, words.subtitle,
    ...list(words.points).map((point) => [point.label, point.text].filter(Boolean).join(': ')),
    slideWordsText(words.caveat), slideWordsText(words.source), words.notes].filter(Boolean).join('\n');
}

function deckOutline(found) {
  const held = deskHeld(view.path); held.outlines ||= {};
  const original = list(found.outline?.slides || found.slides);
  let edit = held.outlines[found.name];
  if (!edit || edit.seen !== found.seen) edit = held.outlines[found.name] = {
    seen: found.seen, work: JSON.parse(JSON.stringify(original)), priced: '' };
  const editable = !held.view.readonly && found.local && found.change?.status !== 'working';
  const rows = make('ol', 'plain');
  const said = make('p', 'quiet'); said.setAttribute('role', 'status');
  const error = make('p', 'notice'); error.setAttribute('role', 'alert');
  const now = () => JSON.stringify(edit.work);
  const save = capsule('Save outline', 'filled', async () => {
    const sent = { level: found.level, slides: edit.work, seen: found.seen };
    const result = await deskDecide('deck-outline', sent, save);
    if (!result) { error.textContent = held.said; return; }
    slideWordResult(found, {}, sent, result, () => { delete held.outlines[found.name]; });
  });
  const price = async () => {
    save.disabled = true; error.textContent = '';
    const asked = now(); edit.asking = asked;
    const result = await deskDecide('deck-outline-price', { level: found.level,
      slides: JSON.parse(asked), seen: found.seen });
    if (edit.asking !== asked) return;
    if (!result) { error.textContent = held.said; return; }
    edit.priced = asked; said.textContent = result.price;
    save.disabled = !editable || now() !== asked || asked === JSON.stringify(original);
  };
  const paint = () => {
    rows.replaceChildren(); save.disabled = true;
    edit.work.forEach((slide, index) => {
      const row = make('li', 'outline-slide');
      row.append(make('p', 'quiet', 'Slide ' + (index + 1)));
      if (editable) {
        const box = make('input', 'input'); box.value = slide.title; box.maxLength = 300;
        box.setAttribute('aria-label', 'Outline title of slide ' + (index + 1));
        box.addEventListener('input', () => { slide.title = box.value;
          if (!original.some((item) => item.id === slide.id)) slide.understand = box.value;
          save.disabled = true; });
        box.addEventListener('change', price);
        row.append(add(make('label', 'field'), make('span', 'field-label', 'Title'), box));
      } else row.append(make('p', 'row-title', slide.title));
      add(row, make('p', 'desk-plain', slideWordsLines({ ...slide, title: '' })),
        make('p', '', slide.understand || ''),
        make('p', 'quiet', 'Serves: ' + list(slide.sources || slide.serves).join(', ')));
      if (editable) {
        const move = (by) => { const [one] = edit.work.splice(index, 1);
          edit.work.splice(index + by, 0, one); paint(); price(); };
        const up = capsule('Move up', 'quiet', () => move(-1)); up.disabled = index === 0;
        const down = capsule('Move down', 'quiet', () => move(1)); down.disabled = index === edit.work.length - 1;
        const remove = capsule('Remove slide', 'quiet', () => { edit.work.splice(index, 1); paint(); price(); });
        remove.disabled = edit.work.length < 2;
        up.setAttribute('aria-label', 'Move up: ' + slide.title);
        down.setAttribute('aria-label', 'Move down: ' + slide.title);
        remove.setAttribute('aria-label', 'Remove slide: ' + slide.title);
        row.append(add(make('div', 'bar'), up, down, remove));
      }
      rows.append(row);
    });
  };
  const adding = make('div', 'paper stack');
  if (editable) {
    const title = make('input', 'input'); title.maxLength = 300;
    const objectives = make('input', 'input');
    const notes = make('textarea', 'input'); notes.rows = 3; notes.maxLength = 2000;
    const field = (label, box) => { box.setAttribute('aria-label', label);
      adding.append(add(make('label', 'field'), make('span', 'field-label', label), box)); };
    field('A new slide’s title', title); field('Objectives for the new slide', objectives);
    adding.append(make('p', 'quiet', 'Choose objectives separated by commas: '
      + [...new Set(original.flatMap((slide) => list(slide.sources)))].join(', ')));
    field('What the presenter says on it', notes);
    adding.append(make('p', 'quiet', 'Speaker notes are required for a deck presented live.'));
    adding.append(capsule('Add slide', 'quiet', () => {
      if (found.outline_delivery === 'live' && !notes.value.trim()) {
        error.textContent = 'Write what the presenter says on this slide.'; return;
      }
      if (!title.value.trim() || !objectives.value.trim()) {
        error.textContent = 'Give the new slide a title and the objectives it serves.'; return;
      }
      const base = 'added-' + (title.value.toLowerCase().replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '').slice(0, 35) || 'slide');
      let id = base, number = 2;
      while (edit.work.some((slide) => slide.id === id)) {
        const suffix = '-' + number++;
        id = base.slice(0, 41 - suffix.length) + suffix;
      }
      const slide = { id, kind: 'content', title: title.value.trim(), understand: title.value.trim(),
        relation: 'none', rhythm: 'breathing', points: [],
        sources: objectives.value.split(',').map((value) => value.trim()).filter(Boolean),
        ...(notes.value.trim() ? { notes: notes.value.trim() } : {}) };
      const closing = edit.work.findIndex((item) => item.kind === 'closing');
      edit.work.splice(closing < 0 ? edit.work.length : closing, 0, slide);
      title.value = ''; objectives.value = ''; notes.value = ''; paint(); price();
    }));
  }
  paint();
  DESK.kitSheet = [sheetTitle('Slide text'), make('p', '', 'Each slide’s words, in order. Saving redraws only changed sections.'),
    rows, adding, said, error, add(make('div', 'bar'), editable ? save : null,
      editable ? capsule('Put it back as it was', 'quiet', () => { edit.work = JSON.parse(JSON.stringify(original));
        edit.priced = ''; said.textContent = ''; error.textContent = ''; paint(); }) : null,
      capsule('Close', 'quiet', () => closeSheet()))];
  openSheet('desk-kit', '')();
}

function wholeDeckNote(found) {
  const held = deskHeld(view.path); held.deckNotes ||= {};
  const box = make('textarea', 'input'); box.rows = 3; box.maxLength = 4000;
  box.setAttribute('aria-label', 'Note for the whole deck'); box.value = held.deckNotes[found.name] || '';
  box.dataset.key = found.name + ':whole-note';
  box.addEventListener('input', () => { held.deckNotes[found.name] = box.value; });
  const go = capsule('Revise the whole deck', 'quiet', async () => {
    const result = await deskDecide('deck-note', { level: found.level, seen: found.seen, note: box.value }, go);
    if (result) delete held.deckNotes[found.name];
  });
  go.disabled = found.change?.status === 'working';
  const node = add(card('Note for the whole deck'), box, make('p', 'quiet', found.look_price), go);
  if (found.change) {
    const progress = make('p', '', found.change.done + ' of ' + found.change.total + ' sections'
      + (found.change.status === 'stopped' ? ' · Stopped' : found.change.status === 'done' ? ' · Done' : ''));
    progress.setAttribute('role', 'status'); node.append(progress);
    if (found.change.status === 'working') node.append(capsule('Stop deck change', 'quiet', () =>
      deskDecide('deck-stop', { level: found.level })));
  }
  return node;
}

function slideSelectionBar(found) {
  const bar = make('div', 'desk-selection glass'); bar.hidden = true;
  bar.setAttribute('role', 'toolbar'); bar.setAttribute('aria-label', 'Change selected slide words');
  const selected = (slide, field, box, savedText) => {
    const start = box.selectionStart, end = box.selectionEnd;
    if (start === end) { bar.hidden = true; return; }
    const passage = box.value.slice(start, end);
    const run = async (action, instruction = '') => {
      if (box.value !== savedText) { toast('Save this field before changing a selection.'); return; }
      const answer = await deskDecide('slide-selection', { level: found.level, slide: slide.id,
        field, action, start, passage, text: box.value, seen: found.seen, instruction });
      if (answer) bar.hidden = true;
    };
    bar.replaceChildren(...[['rephrase', 'Rephrase'], ['shorten', 'Shorten'], ['expand', 'Expand'],
      ['fix', 'Fix']].map(([action, label]) => capsule(label, 'quiet', () => run(action))),
      capsule('Ask…', 'quiet', () => {
        const question = make('textarea', 'input'); question.rows = 2;
        question.setAttribute('aria-label', 'What should change in the selected text?');
        bar.replaceChildren(question, capsule('Go', 'quiet', () => run('ask', question.value)),
          capsule('Cancel', 'quiet', () => { bar.hidden = true; }));
      }));
    bar.hidden = false;
  };
  return { bar, selected };
}

function deckParts(found) {
  const area = make('div', 'stack desk-slide-cards');
  const ours = deskCanChange();
  const selection = slideSelectionBar(found);
  if (ours) area.append(selection.bar);
  if (list(found.slides).length) area.append(capsule('Review slide text', 'quiet', () => deckOutline(found)));
  if (ours && found.local && list(found.slides).length) area.append(add(make('details', 'card-part'),
    make('summary', '', 'Change the whole deck'), wholeDeckNote(found)));
  if (found.selection) {
    const job = found.selection, result = job.result;
    const status = make('p', 'quiet', job.error || (['queued', 'working'].includes(job.status)
      ? job.says : result?.error || (result?.cancelled ? 'Selected words discarded.' : result?.fits
        ? 'Selected words saved.' : result?.approval || result?.fits === false
          ? 'Selected words are ready to review.' : 'This selection did not finish. Select the words again.')));
    status.setAttribute('role', job.error || result?.error ? 'alert' : 'status'); area.append(status);
    if (ours && result && (result.approval || result.fits === false)) area.append(
      capsule('Review selected words', 'quiet', () => slideWordResult(found,
        list(found.slides).find((slide) => slide.id === job.part),
        { ...result.sent, selection: job.id }, result, () => {})));
  }
  if (ours && list(found.slides).length) {
    const again = capsule(found.local ? 'Try another look' : 'Draw it here', 'quiet', async () => {
      if (!found.local) return deskDecide('draw-here', { level: found.level, seen: found.seen }, again);
      const answer = await deskDecide('look-samples', { level: found.level }, again);
      if (answer) lookSheet(found, answer.look);
    });
    add(area, add(make('div', 'bar'), again), make('p', 'quiet', found.look_price));
  }
  const slides = list(found.slides), heldDeck = deskHeld(view.path);
  heldDeck.slide ||= {};
  const issues = list(found.proposals?.review?.items).filter(item => item.state === 'open' && item.present !== false);
  if (!slides.some(slide => slide.id === heldDeck.slide[found.name])) {
    heldDeck.slide[found.name] = slides.find(slide => issues.some(item => item.part === slide.id))?.id || slides[0]?.id;
  }
  if (slides.length) {
    const label = make('label', 'field'), select = make('select', 'input');
    select.setAttribute('aria-label', 'Slide to review');
    for (const slide of slides) {
      const option = make('option', '', slide.number + '. ' + slide.title
        + (issues.some(item => item.part === slide.id) ? ' · Review suggestion' : ''));
      option.value = slide.id; select.append(option);
    }
    select.value = heldDeck.slide[found.name];
    select.addEventListener('change', () => { heldDeck.slide[found.name] = select.value; paintDesk(true); });
    area.append(add(label, make('span', 'field-label', 'Slide to review'), select));
  }
  for (const slide of slides.filter(slide => slide.id === heldDeck.slide[found.name])) {
    const node = card(slide.number + '. ' + slide.title, 'desk-slide-card');
    if (slide.picture) node.append(slidePicture(found, slide.number));
    else node.append(make('p', 'quiet', 'Words only. The drawing is kept on the computer that made it.'));
    const history = capsule(slide.history ? 'History (' + slide.history + ')' : 'History',
      'quiet', () => slideHistory(found, slide));
    history.disabled = !slide.history;
    node.append(history);
    const words = add(make('details', 'card-part'), make('summary', '', 'Edit slide text and speaker notes'));
    if (found.state === 'ready' && ours && found.local) words.append(readyEditWarning(found));
    const fields = [['title', 'Title'], ['subtitle', 'Subtitle']];
    list(slide.points).forEach((point, i) => fields.push(
      ['points[' + i + '].label', 'Point ' + (i + 1) + ' label'],
      ['points[' + i + '].text', 'Point ' + (i + 1) + ' text']));
    fields.push(['caveat', 'Caveat'], ['source', 'Source'], ['notes', 'Speaker notes']);
    for (const [field, label] of fields) {
      const match = /^points\[(\d+)\]\.(label|text)$/.exec(field);
      const text = slideWordsText(match ? slide.points[Number(match[1])][match[2]] : slide[field]);
      if (!ours || !found.local) {
        if (field !== 'title' && text) add(words, make('p', 'sheet-part', label), make('p', 'desk-plain', text));
        continue;
      }
      const box = make('textarea', 'input');
      box.rows = field === 'notes' ? 3 : 2;
      box.maxLength = field === 'notes' ? 4000 : 2000;
      box.value = text;
      box.setAttribute('aria-label', 'Slide ' + slide.number + ' ' + label.toLowerCase());
      box.dataset.key = found.name + ':' + slide.id + ':' + field;
      const saved = deskHeld(view.path);
      saved.slideText ||= {};
      if (saved.slideText[box.dataset.key] !== undefined) box.value = saved.slideText[box.dataset.key];
      box.addEventListener('input', () => { saved.slideText[box.dataset.key] = box.value; });
      for (const event of ['select', 'mouseup', 'keyup']) box.addEventListener(event,
        () => selection.selected(slide, field, box, text));
      const go = capsule('Save ' + label.toLowerCase(), 'quiet', async () => {
        const sent = { level: found.level, slide: slide.id, seen: found.seen, field, text: box.value };
        const answer = await deskDecide(field === 'notes' ? 'slide-speaker-notes' : 'slide-words', sent, go);
        if (answer) slideWordResult(found, slide, sent, answer, () => { delete saved.slideText[box.dataset.key]; });
      });
      add(words, add(make('label', 'field'), make('span', 'field-label', label), box), go);
    }
    node.append(words);
    const proposals = found.proposals?.review;
    for (const proposal of list(proposals?.items).filter((item) => item.part === slide.id && item.state === 'open' && item.present !== false)) {
      const row = add(make('section', 'card-part'), make('p', 'sheet-part', 'Review suggestion'),
        make('p', '', proposal.reason || proposal.says), make('p', '', proposal.after),
        make('p', 'quiet', proposal.price));
      if (ours) {
        const decide = (action) => deskDecide('finding', { level: found.level, seen: found.seen,
          job: proposals.job, ids: [proposal.id], action });
        row.append(add(make('div', 'bar'), capsule('Apply fix to this slide', 'quiet', () => decide('apply')),
          capsule('Dismiss suggestion', 'quiet', () => decide('skip'))));
      }
      node.append(row);
    }
    if (ours && found.local && slide.redraw !== false && slide.price) {
      const note = make('textarea', 'input'); note.rows = 2; note.maxLength = 4000;
      note.setAttribute('aria-label', 'How should slide ' + slide.number + ' change?');
      const held = deskHeld(view.path); held.slideNotes ||= {};
      const noteKey = found.name + ':' + slide.id;
      note.value = held.slideNotes[noteKey] || '';
      note.dataset.key = found.name + ':' + slide.id + ':note';
      note.addEventListener('input', () => { held.slideNotes[noteKey] = note.value; });
      const go = capsule('Redraw slide ' + slide.number, 'quiet', async () => {
        if (!note.value.trim()) { toast('Write a note first.'); return; }
        const answer = await deskDecide('slide-note', { level: found.level, slide: slide.id,
          note: note.value, seen: found.seen }, go);
        if (answer) delete held.slideNotes[noteKey];
      });
      add(node, add(make('label', 'field'), make('span', 'field-label', 'How should this slide change?'), note),
        make('p', 'quiet', slide.price), go);
    }
    area.append(node);
  }
  return area;
}

async function slideWordResult(found, slide, sent, answer, saved) {
  const settle = async (action) => !sent.selection || deskDecide(
    'slide-selection-settle', { job: sent.selection, action });
  if (answer.approval) { slideApproval(found, slide, sent, answer.approval, saved); return; }
  if (answer.fits === false) {
    const error = make('p', 'notice'); error.setAttribute('role', 'alert');
    const redraw = capsule('Redraw with these words', 'filled', async () => {
      const route = sent.approval ? 'slide-words-decide' : sent.stamp ? 'slide-restore' : 'slide-words';
      const { approval, ...words } = sent;
      const result = await deskDecide(route, { ...(approval || words), redraw: true }, redraw);
      if (result && await settle('saved')) { saved(); closeSheet(); }
      else error.textContent = deskHeld(view.path).said;
    });
    DESK.kitSheet = [sheetTitle('These words need another drawing'),
      make('h3', 'sheet-part', '1. Your words'), make('p', 'desk-plain', sent.text),
      make('p', '', answer.said), make('h3', 'sheet-part', '2. Redraw this section'),
      make('p', 'quiet', answer.price || slide.price),
      answer.can_redraw === false ? make('p', '', 'This slide uses a fixed layout. Shorten its words before saving.') : null,
      error, add(make('div', 'bar'), answer.can_redraw === false ? null : redraw,
        capsule('Discard', 'quiet', async () => {
          if (sent.approval) {
            const result = await deskDecide('slide-words-decide', { proposal: sent.approval.proposal, decision: 'cancel' });
            if (!result) { error.textContent = deskHeld(view.path).said; return; }
          }
          if (!await settle('discard')) { error.textContent = deskHeld(view.path).said; return; }
          saved(); closeSheet();
        }))].filter(Boolean);
    openSheet('desk-kit', '')();
  } else if (await settle('saved')) { saved(); closeSheet(); }
}

function slideApproval(found, slide, sent, approval, saved) {
  const response = make('textarea', 'input'); response.rows = 3; response.maxLength = 4000;
  response.setAttribute('aria-label', 'Your response');
  const error = make('p', 'notice'); error.setAttribute('role', 'alert');
  const cancel = capsule('Cancel', 'quiet', async () => {
    const result = await deskDecide('slide-words-decide', { proposal: approval.token, decision: 'cancel' }, cancel);
    if (result) closeSheet(); else error.textContent = deskHeld(view.path).said;
  });
  const approve = capsule('Approve updated words', 'filled', async () => {
    if (!response.value.trim()) { error.textContent = 'Answer the displayed design question first.'; return; }
    const answer = await deskDecide('slide-words-decide', { proposal: approval.token,
      decision: 'approve', seen: sent.seen, question: approval.question.id,
      revision: approval.revision, response: response.value }, approve);
    if (answer) slideWordResult(found, slide, { ...sent, approval: { proposal: approval.token,
      decision: 'approve', seen: sent.seen, question: approval.question.id,
      revision: approval.revision, response: response.value } }, answer, saved);
    else error.textContent = deskHeld(view.path).said;
  });
  const question = approval.question;
  const options = make('div', 'stack');
  for (const option of list(question.options)) {
    const text = typeof option === 'string' ? option : option.label || option.text || option.title || '';
    if (text) options.append(/^Approve\b/i.test(text)
      ? capsule(text, 'quiet', () => { response.value = text; }) : make('p', '', text));
  }
  DESK.kitSheet = [sheetTitle('Approve updated words'),
    make('h3', 'sheet-part', '1. Exact change'), make('p', 'quiet', 'Before'),
    make('p', 'desk-plain', approval.before), make('p', 'quiet', 'After'),
    make('p', 'desk-plain', approval.after), make('h3', 'sheet-part', '2. Design question'),
    make('p', 'desk-plain', question.text || question.prompt || question.question || ''), options,
    add(make('label', 'field'), make('span', 'field-label', 'Your response'), response), error,
    add(make('div', 'bar'), approve, cancel)];
  openSheet('desk-kit', '')();
}

async function slideHistory(found, slide) {
  try {
    const answer = await ask('drafts/slide-versions', { path: view.path, level: found.level, slide: slide.id });
    const rows = make('div', 'stack');
    const error = make('p', 'notice'); error.setAttribute('role', 'alert');
    for (const version of list(answer.versions)) {
      const row = add(make('section', 'card'), make('h3', 'card-title', version.at),
        make('p', 'quiet', ({save: 'Saved', selection: 'Selection', note: 'Slide note',
          redraw: 'Redrawn', restore: 'Restored', outline: 'Outline changed', finishing: 'Finishing',
          open: 'Opened on the desk', update: 'Updated'})[version.source] || 'An earlier version'), make('p', 'desk-plain', version.words.title),
        make('p', 'quiet', version.drawing ? 'Words and drawing' : 'Words only'));
      if (version.picture) row.append(pictureAt({ path: view.path, artifact: found.name,
        number: slide.number, version: slide.id + '/' + version.stamp }, 'Earlier slide ' + slide.number, version.stamp));
      for (const [key, value] of Object.entries(version.words || {})) {
        if (key === 'title' || !value) continue;
        row.append(make('p', 'desk-plain', key === 'points'
          ? list(value).map((point) => [point.label, point.text].filter(Boolean).join(': ')).join('\n')
          : slideWordsText(value)));
      }
      const comparison = make('div');
      row.append(capsule('Compare', 'quiet', () => comparison.replaceChildren(
        make('p', 'quiet', 'Struck words are in this version only; marked words were added since.'),
        deskKit.compare(slideWordsLines(version.words), slideWordsLines(slide)))));
      row.append(comparison);
      if (deskCanChange()) {
        const restore = capsule('Restore', 'quiet', async () => {
          const sent = { level: found.level, slide: slide.id, stamp: version.stamp, seen: found.seen };
          const result = await deskDecide('slide-restore', sent, restore);
          if (result) slideWordResult(found, slide, { ...sent, text: JSON.stringify(version.words) }, result, () => {});
          else error.textContent = deskHeld(view.path).said;
        });
        row.append(restore);
      }
      rows.append(row);
    }
    DESK.kitSheet = [sheetTitle('Slide ' + slide.number + ' History'), error, rows,
      add(make('div', 'bar'), capsule('Close', 'quiet', () => closeSheet()))];
    openSheet('desk-kit', '')();
  } catch (failure) { deskHeld(view.path).said = failure.message; paintDesk(false); }
}

function lookSheet(found, look) {
  const picked = { choice: '', words: '' };
  const options = window.DeckPanels.lookPicker({ name: found.name, looks: list(look?.looks),
    defaultId: look?.default, sheet: look?.sheet, notes: list(look?.notes), failed: look?.failed,
    picked, changed: (now) => Object.assign(picked, now),
    picture: (number, alt) => pictureAt({ path: view.path, artifact: found.name,
      section: 'look', number }, alt, look?.at || found.seen, { again: true }) });
  const error = make('p', 'notice'); error.setAttribute('role', 'alert');
  const retry = capsule('Try again', 'quiet', async () => {
    const answer = await deskDecide('look-samples', { level: found.level }, retry);
    if (answer) lookSheet(found, answer.look); else error.textContent = deskHeld(view.path).said;
  });
  const fallback = capsule('Carry on in the brand’s default look', 'quiet', async () => {
    const answer = await deskDecide('look', { level: found.level, choice: 'default', seen: found.seen }, fallback);
    if (answer) closeSheet(); else error.textContent = deskHeld(view.path).said;
  });
  const apply = capsule('Use this look', 'filled', async () => {
    if (!picked.choice) { error.textContent = 'Choose a look first.'; return; }
    const answer = await deskDecide('look', { level: found.level, choice: picked.choice,
      words: picked.words, seen: found.seen }, apply);
    if (answer) closeSheet(); else error.textContent = deskHeld(view.path).said;
  });
  DESK.kitSheet = [sheetTitle('Try another look'), make('h3', 'sheet-part', '1. Choose a look'),
    make('p', '', look?.message), options, make('h3', 'sheet-part', '2. Redraw the whole deck'),
    make('p', '', found.look_price), error, add(make('div', 'bar'), list(look?.looks).length ? apply : null,
      look?.failed ? retry : null, look?.default_available ? fallback : null,
      capsule('Cancel', 'quiet', () => closeSheet()))];
  openSheet('desk-kit', '')();
}

// Whether a material is open for editing. It opens to read, as learners will receive it;
// Edit opens its parts. Text not saved yet, recovered text, a selection or a change note (one
// Finishing opened, say) keeps it open, so nothing typed is ever hidden. The choice outlives a change of tab, level or check.
function deskEditing(held, found) {
  if (!deskCanChange() || held.view.readonly) return false;
  const desk = deskHeld(deskItem(held.id).path);
  return Boolean((desk.editing || {})[found.name] || keptOpen(held));
}

// Why a material stays open for editing whatever the person chose, in a sentence, or ''.
function keptOpen(held) {
  if (Object.keys(held.pending || {}).length) {
    return hasDeskRecovery(held) ? 'Recovered text is waiting to be saved, so it stays open '
      + 'for editing. Save it, or change it, first.'
      : 'Your text is not saved yet, so it stays open for editing.';
  }
  if (hasDeskRecovery(held)) return 'Recovered text is waiting to be saved, so it stays open '
    + 'for editing. Save it, or change it, first.';
  if (String(held.wholeNote || '').trim()
      || Object.values(held.notes || {}).some((note) => String(note || '').trim())) {
    return 'A change note is written and not sent, so it stays open for editing. Send it or '
      + 'clear it first.';
  }
  if (held.selection) return 'A passage is selected for a change, so it stays open for editing.';
  return '';
}

function editToggle(held, found, editing) {
  if (!deskCanChange() || held.view.readonly) return null;
  const go = capsule(editing ? 'Done editing' : 'Edit ' + cardTitle(found), 'quiet', async () => {
    const desk = deskHeld(deskItem(held.id).path);
    desk.editing ||= {};
    if (editing) {
      // What was typed is saved before the reading view shows the saved text.
      try { await deskKit.flush(held); } catch (failure) { /* said below */ }
      desk.editing[found.name] = false;
      const why = keptOpen(held);
      if (why) {
        desk.said = why;
        paintDesk(true);
        return;
      }
      paintDesk(true);
      focusKey('desk-edit ' + found.name);
      return;
    }
    desk.editing[found.name] = !editing;
    paintDesk(true);
    focusKey('desk-edit ' + found.name);
  }, 'desk-edit ' + found.name);
  return go;
}

// One part as learners receive it: its Markdown rendered on an opaque reading surface, the
// exact saved text to copy, and its teaching details folded away.
function readingPart(held, found, section) {
  const text = section.id === 'opening' ? held.view.opening || '' : section.text || '';
  const node = make('article', 'paper doc desk-reading');
  node.setAttribute('aria-label', section.heading);
  add(node, make('h2', 'doc-title', section.heading));
  if (held.view.working && (held.view.working.part === section.id
      || held.view.working.part === 'whole')) {
    const working = make('p', 'quiet', 'Being changed now. The saved text is shown.');
    working.setAttribute('role', 'status');
    node.append(working);
  }
  node.append(text.trim() ? window.StudioMarkdown.render(text)
    : make('p', 'quiet', 'Nothing is written here yet.'));
  if (list(section.covers).length) {
    node.append(add(make('details', 'card-part'), make('summary', '', 'Teaching details'),
      make('p', 'quiet', 'Covers ' + section.covers.join(', '))));
  }
  return add(node, add(make('div', 'bar'),
    copyButton('Copy text', 'Copied.', text, 'desk-copy ' + found.name + ' ' + section.id)));
}

function materialParts(held, found) {
  const area = make('div', 'desk-material stack');
  held.area = area;
  const editing = deskEditing(held, found);
  const status = make('p', 'quiet desk-save-state', held.saved || '');
  status.setAttribute('role', 'status');
  held.status = status;
  const toggle = editToggle(held, found, editing);
  add(area, toggle ? add(make('div', 'bar'), toggle) : null,
    editing && found.state === 'ready' ? readyEditWarning(found) : null, status,
    editing ? deskKit.selectionBar(held) : null, held.view.readonly
      ? make('p', 'quiet', held.view.readonly) : null);
  if (editing) {
    const whole = add(make('details', 'card-part'),
      make('summary', '', 'Change the whole ' + cardTitle(found).toLowerCase()),
      materialNote(held, found));
    // A note for the whole material, from Finishing or typed earlier, is never folded away.
    if (String(held.wholeNote || '').trim()) whole.open = true;
    area.append(whole);
  } else if (hasDeskRecovery(held)) {
    // Text recovered here that cannot be saved now is shown as it is, to be copied.
    const kept = card('Recovered text not saved');
    kept.append(make('p', 'quiet', 'It cannot be saved here now. Copy it to keep it.'));
    for (const [part, edit] of Object.entries(held.pending || {})) {
      if (!(held.recoveredParts || {})[part]) continue;
      const heading = part === 'opening' ? 'Opening'
        : list(held.view.sections).find((section) => section.id === part)?.heading || part;
      kept.append(add(make('div', 'card-part'), make('p', 'row-title', heading),
        make('p', 'desk-plain', edit.text),
        copyButton('Copy', 'Copied.', edit.text, 'desk-recovered ' + part)));
    }
    area.append(kept);
  }
  if (hasDeskRecovery(held) && deskCanChange() && !held.view.readonly) {
    const save = capsule('Save recovered text', 'quiet', async () => {
      held.recoveredParts = {};
      await deskKit.flush(held);
      deskMaterialChanged(held);
    });
    area.append(save);
  }
  const item = deskItem(held.id);
  const otherRecovery = deskHeld(item.path).recovery.filter((edit) => edit.name === item.name
    && held.recoveryFrom?.[edit.part] !== edit.recoveryKey);
  if (otherRecovery.length) {
    const copies = add(make('details', 'card'), make('summary', '', 'Other recovered text'));
    for (const edit of otherRecovery) copies.append(add(make('section', 'card-part'),
      make('h3', 'card-title', edit.part === 'opening' ? 'Opening'
        : list(held.view.sections).find((section) => section.id === edit.part)?.heading || edit.part),
      make('p', 'desk-plain', edit.text), copyButton('Copy', 'Copied.', edit.text)));
    area.append(copies);
  }
  const sections = [...(held.view.opening || held.view.whole ? [{id: 'opening', heading: held.view.whole ? 'Whole file' : 'Opening'}] : []),
    ...list(held.view.sections)];
  if (!sections.some(section => section.id === held.section)) held.section = sections[0]?.id;
  const sectionKey = headingId(found.name) + '-sections';
  if (sections.length > 1) area.append(workspaceTabs('Section of ' + cardTitle(found),
    sections.map(section => ({id: section.id, label: section.heading})), held.section,
    id => { held.section = id; paintDesk(true); }, sectionKey));
  for (const section of sections.filter(section => section.id === held.section)) {
    let part;
    if (!editing) {
      part = readingPart(held, found, section);
    } else if (section.locked) {
      part = add(make('section', 'card desk-part'), make('h2', 'card-title', section.heading),
        make('p', 'quiet', 'Kept from the findings cited.'), make('p', 'desk-plain', section.text));
    } else part = materialPart(held, section.id);
    area.append(sections.length > 1 ? workspacePanel(sectionKey, sections.indexOf(section), part) : part);
  }
  if (found.kind === 'yoodli') {
    for (const field of list(held.view.fields)) {
      const title = list(field.heading).join(' / ');
      area.append(add(make('section', 'card'), make('h2', 'card-title', title),
        make('p', 'desk-plain', field.text), field.limit
          ? make('p', 'quiet', field.text.length + ' of ' + field.limit.toLocaleString('en-US')
            + ' characters') : null, copyButton('Copy', 'Copied.', field.text)));
    }
  }
  const job = held.view.working || list(held.view.jobs).at(-1);
  if (job) {
    const checks = make('div', 'card');
    add(checks, make('h2', 'card-title', 'Checked for you'));
    if (job.chain && job.total) checks.append(make('p', '',
      Math.min(job.index + 1, job.total) + ' of ' + job.total + ' sections'));
    if (job.says) checks.append(make('p', '', job.says));
    if (job.error) checks.append(make('p', 'notice', job.error));
    const flags = Array.isArray(job.checks) ? job.checks : job.checks ? [job.checks] : [];
    for (const flag of flags) checks.append(make('p', 'quiet', String(flag)));
    if (list(job.dropped).length) {
      if (!job.says) checks.append(make('p', '', job.dropped.map((number) =>
        'This change dropped reference [' + number + '].').join(' ')));
      checks.append(capsule('Restore', 'quiet', () => deskKit.history(held,
        job.part === 'whole' ? 'opening' : job.part)));
    }
    if (deskCanChange()) {
      const working = ['queued', 'working'].includes(job.status);
      if (working || ['stopped', 'failed'].includes(job.status) || (job.applied === false && !job.proposed)) {
        const route = working ? 'stop' : 'retry';
        const go = capsule(working ? 'Stop change' : 'Retry change', 'quiet', () =>
          working ? stopDeskChange(held, job.id, go)
            : deskKit.job(held, go, 'drafts/' + route, { job: job.id }));
        checks.append(go);
      }
    }
    if (checks.childNodes.length > 1) area.append(checks);
  }
  const problem = deskKit.problem(held);
  if (problem) area.append(problem);
  if (held.stale) deskKit.stale(held);
  if (!hasDeskRecovery(held)) deskKit.watch(held);
  return area;
}

// Said as a Ready material opens for editing, before anything is typed: a saved change
// makes it a draft again, and what the Document Library keeps meanwhile.
function readyEditWarning(found) {
  const kept = (deskHeld(view.path).view?.library || {})[found.name];
  return make('p', 'desk-ready-edit', 'Saving a change returns this ' + deskNoun(found)
    + ' to Draft.' + (kept && kept.state === 'kept' ? ' The Document Library keeps revision '
      + kept.revision + ' until you mark it ready again.' : ''));
}

// Said once a save made a Ready material a draft again, with what the library keeps.
function backToDraftWords(found, desk) {
  const kept = (desk.library || {})[found.name];
  return capital(cardTitle(found)) + ' is back to Draft. Mark it ready again once you have read it.'
    + (kept && kept.state === 'earlier' ? ' ' + libraryEarlier(found, kept) : '');
}

function materialPart(held, part) {
  const node = deskKit.part(held, part);
  // A person may keep typing while a rewrite runs; the server compares the part before landing.
  node.deskInput.dataset.key = held.id + ':' + part + ':text';
  const note = node.querySelector('.desk-note-text');
  if (note) note.dataset.key = held.id + ':' + part + ':note';
  node.deskInput.readOnly = !deskCanChange() || !!held.view.readonly;
  return node;
}

deskKit.counts = (held) => {
  for (const node of held.area?.querySelectorAll('.desk-part') || []) {
    const count = (held.view.versions || {})[node.dataset.part] || 0;
    const button = node.querySelector('button');
    if (button) { button.textContent = count ? 'History (' + count + ')' : 'History'; button.disabled = !count; }
  }
};

async function flushDesk(held) {
  await Promise.all(Object.values(held.materials).map((material) => deskKit.flush(material)));
  if (Object.values(held.materials).some((material) => Object.keys(material.pending).length)) {
    throw new Error('Save your text before continuing. Your text is kept here.');
  }
}

function materialNote(held, found) {
  const own = held.view.own;
  const noun = found.kind === 'blueprint' ? 'plan' : found.kind === 'document' ? 'guide'
    : found.kind === 'yoodli' ? 'Yoodli layout' : found.kind === 'scenario' ? 'scenario' : 'brief';
  const title = own ? 'Lay out this scenario in your words' : 'Note for the whole ' + noun;
  const box = make('textarea', 'input'); box.rows = 2; box.maxLength = 4000;
  box.dataset.key = held.id + ':whole-note';
  box.setAttribute('aria-label', title); box.value = held.wholeNote || '';
  box.addEventListener('input', () => { held.wholeNote = box.value; });
  const go = capsule(own ? 'Lay out in my words' : 'Revise the ' + noun, 'quiet', () => {
    const note = (held.wholeNote || '').trim();
    if (!note) { toast('Write a note first.'); return; }
    return deskKit.job(held, go, own ? 'drafts/layout' : 'drafts/revise',
      { note, ...(held.view.whole ? { seen: held.view.seen } : {}) },
      () => { held.wholeNote = ''; });
  });
  go.disabled = !!held.view.working;
  return add(card(title), own ? make('p', 'quiet', 'Your words are kept. Only the layout changes.')
    : null, box, go);
}

async function previewUpdate(found) {
  const path = view.path;
  try {
    await flushDesk(deskHeld(path));
    const preview = await ask('drafts/update-preview', { path, name: found.name });
    if (view.path !== path || view.screen !== 'run') return;
    if (preview.message) {
      const keep = capsule('Keep as it is', 'filled', async () => {
        const answer = await deskDecide('keep', { name: found.name, seen: found.seen }, keep);
        if (answer) closeSheet();
      });
      DESK.kitSheet = [sheetTitle(updateLabel(found)), make('p', '', preview.message),
        add(make('div', 'bar'), keep)];
      openSheet('desk-kit', '')();
      return;
    }
    const update = capsule('Update', 'filled', async () => {
      const answer = await deskDecide('update', { name: found.name }, update);
      if (answer) closeSheet();
    });
    DESK.kitSheet = [sheetTitle(updateLabel(found)),
      make('h3', 'sheet-part', '1. Sections to update'),
      list(preview.parts).length ? bullets(preview.parts, 'reasons')
        : make('p', 'quiet', 'No sections need updating.'),
      make('h3', 'sheet-part', '2. Estimated price'), make('p', '', preview.price),
      add(make('div', 'bar'), update, capsule('Cancel', 'quiet', () => closeSheet()))];
    openSheet('desk-kit', '')();
  } catch (failure) {
    deskHeld(path).said = failure.message;
    paintDesk(false);
  }
}

function downloadButton(found) {
  const name = String(found.name).replace(/[^A-Za-z0-9._-]+/g, '-')
    + (found.kind === 'deck' ? '.pptx' : '.md');
  const control = capsule('Download ' + cardTitle(found), 'quiet', (event) => downloadFile(view.path,
    { artifact: found.name }, name, event.currentTarget), 'desk-download ' + found.name);
  control.setAttribute('aria-label', 'Download ' + found.label + ', as saved');
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
        held.material[held.level || ''] = one.name;
        deskGoTo(held, found.standing, one.name);
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
  const run = view.run;
  const controls = make('div', 'bar');
  if (deskOurs()) {
    if (['working', 'waiting', 'paused'].includes(run.state)) controls.append(
      capsule('Stop training', 'quiet', openSheet('stop-run', 'stop'), 'stop'));
    if (['paused', 'stopped'].includes(run.state)) {
      const resume = capsule('Resume training', 'quiet', () => steer('resume', resume), 'resume');
      controls.append(resume);
    }
  }
  if (!progress.running && !controls.childNodes.length) return null;
  if (run.research_progress && run.research_progress.phase !== 'complete'
      && typeof StudioResearch !== 'undefined') return researchActivity(run, controls);
  // The line is blank while something on the desk needs the person.
  const line = progress.line ? make('p', '', progress.line) : null;
  if (line) line.setAttribute('role', 'status');
  const building = progress.running ? make('h3', 'card-title', progress.doing || 'Preparing your training') : null;
  const materials = list(found.cards).filter(one => one.state !== 'left-out');
  const available = materials.filter(one => one.seen).length;
  const status = progress.running ? make('p', 'quiet', run.training_plan_pending
    ? 'Next: review the topics and teaching plan before the materials are built.'
    : materials.length ? available + ' of ' + materials.length + ' drafts available. New drafts appear below as they finish.'
      : 'Preparing the first material. It will appear here when it is ready.') : null;
  return add(make('div'), callout('', building, line, status, controls.childNodes.length ? controls : null,
    // Time is a detail, never an estimate of what is left: elapsed time keeps growing.
    run.timing ? (!run.research_progress || run.research_progress.phase === 'complete'
      ? timeDetails(measuredTime(run)) : null) : progress.started_at
      ? timeDetails(make('p', 'quiet desk-clock', deskKit.clock(progress))) : null),
  researchActivity(run));
}

function timeDetails(line) {
  if (!line) return null;
  return add(make('details', 'card-part desk-time'), make('summary', '', 'Time so far'), line,
    make('p', 'quiet', 'Elapsed time includes waiting. It is not an estimate of what is left.'));
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

async function addSource() {
  const path = view.path;
  try {
    const price = await ask('drafts/source-price', { path });
    if (view.path !== path || view.screen !== 'run') return;
    const chosen = { files: [] };
    const status = make('p', 'notice');
    status.setAttribute('role', 'status');
    let sending = false;
    const update = capsule('Update the research', 'filled', async () => {
      if (sending || !chosen.files.length) return;
      sending = true;
      update.disabled = true;
      say(status, 'Adding documents and updating the research…');
      try {
        const files = await Promise.all(chosen.files.map(async (file) =>
          ({ name: file.name, content: await base64Of(file) })));
        if (view.path !== path) return;
        const answer = await deskDecide('source', { files, keep: keepUploads() }, update);
        if (answer) {
          closeSheet();
          const kept = list(answer.library_kept);
          const missed = kept.filter((one) => one.state !== 'kept');
          if (kept.length) {
            toast(missed.length ? 'Added, but not kept in the Document Library: '
              + missed.map((one) => one.problem).join(' ') : 'Kept in the Document Library too.');
          }
        } else say(status, deskHeld(path).said || 'The source could not be added. Try again.');
      } catch (failure) {
        say(status, failure.message);
      } finally {
        sending = false;
        update.disabled = !chosen.files.length;
      }
    });
    update.disabled = true;
    DESK.kitSheet = [sheetTitle('Add a source'),
      make('p', 'quiet', 'Add documents and read what updating the research will change.'),
      make('h3', 'sheet-part', '1. Add'),
      documentsPart(chosen, () => { update.disabled = sending || !chosen.files.length; }, true),
      make('h3', 'sheet-part', '2. What it changes'), make('p', '', price.words),
      make('p', '', price.afterwards), price.widened ? make('p', '', price.widened) : null,
      status, add(make('div', 'bar'), update, capsule('Cancel', 'quiet', () => {
        if (!sending) closeSheet();
      }))].filter(Boolean);
    openSheet('desk-kit', '')();
  } catch (failure) {
    deskHeld(path).said = failure.message;
    paintDesk(false);
  }
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
  const marks = sources.marked || {};
  for (const [id, mark] of Object.entries(marks)) {
    const finding = list(account && account.findings).find((one) => one.id === id);
    add(node, make('p', 'quiet', (mark === 'new' ? 'New: ' : 'Changed: ')
      + (finding ? finding.title : id)));
  }
  if (deskCanChange()) add(node, capsule('Add a source', 'quiet', addSource));
  add(node, updateChainPart());
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
  add(node, deskLibraryPart());
  const aside = make('aside', 'desk-aside');
  aside.setAttribute('aria-label', 'Sources');
  return add(aside, node);
}

// The Document Library on the desk's Sources: documents pinned from it, a newer revision
// taken only when pressed, and Add from library. What is added waits, unread, until Update
// the research, which says first what it changes. Offered only where the research reads
// documents: Add a source is the way to widen it.
function deskLibraryPart() {
  const run = view.run || {};
  const held = run.documents;
  if (!deskCanChange() || !held || held.waiting) return null;
  const path = view.path;
  const after = (answer) => {
    view.run = answer;
    drawDesk(false);
  };
  const part = add(make('div', 'card-part desk-library'), make('p', 'row-title', 'From the Document Library'));
  const pinned = list(held.added).filter((one) => one.library);
  if (pinned.length) {
    const rows = make('ul', 'rows');
    for (const one of pinned) {
      rows.append(add(make('li', 'row'), add(make('div', 'row-text'),
        make('p', 'step-name', one.title || one.name), libraryWords(one)),
      one.update ? libraryUpdate(path, one, after) : null));
    }
    part.append(rows);
  } else {
    part.append(make('p', 'quiet', 'Choose documents kept on this computer for this training only.'));
  }
  const later = list(held.later).map((one) => one.name);
  const bar = add(make('div', 'bar'), libraryAdd(path, 'desk-library-add', after));
  if (later.length) {
    part.append(make('p', '', 'Not read yet: ' + series(later) + '. The research reads '
      + (later.length === 1 ? 'it' : 'them') + ' once you update it.'));
    bar.append(capsule('Update the research', '', openSheet('update-research',
      'desk-update-research'), 'desk-update-research'));
  }
  return add(part, bar);
}

// What the Document Library holds of a Ready guide or brief: kept, or the retry. Keeping it
// again changes no material and starts no job, so, like Mark ready, the person who runs the
// training is offered it while it is worked on in a conversation too; a teammate reads it.
function deskLibraryKept(found) {
  const kept = (deskHeld(view.path).view?.library || {})[found.name];
  if (!kept) return null;
  if (kept.state === 'kept') {
    // Return to draft keeps the revision: nothing in the library is removed.
    const line = make('p', 'quiet', 'Kept in the Document Library as Markdown, revision '
      + kept.revision + '.' + (list(found.actions).includes('draft')
        ? ' Return to draft leaves that revision in the library.' : ''));
    line.id = headingId(found.name) + '-library';
    return line;
  }
  // A draft again, after an edit, Undo or Return to draft: the library still has it.
  if (kept.state === 'earlier') {
    return make('p', 'quiet', libraryEarlier(found, kept));
  }
  const said = kept.state === 'failed'
    ? make('p', 'problem', 'Not kept in the Document Library: ' + kept.problem)
    : make('p', 'quiet', 'Not kept in the Document Library yet.');
  if (!deskOurs()) return add(make('div', 'card-part'), said);
  const again = capsule(kept.state === 'failed' ? 'Keep in library again' : 'Keep in library', 'quiet',
    () => deskDecide('library-keep', { name: found.name }, again), 'desk-library-keep ' + found.name);
  return add(make('div', 'card-part'), said, add(make('div', 'bar'), again));
}

// What the Document Library holds of a guide or brief that is a draft again.
function libraryEarlier(found, kept) {
  return 'The Document Library keeps revision ' + kept.revision + ' of this '
    + deskNoun(found) + ' until you mark it ready again.';
}

function deskLead(run, held, ours) {
  if (view.sheet || view.after || !ours) return '';
  if (held.unsent) return 'unsent';
  if (run.question) return 'answer';
  if (run.problem && run.problem.action) return 'problem';
  if (adding(run)) return 'documents';
  if (run.training_plan && run.state === 'waiting') return 'training-plan';
  if (run.outline?.content_first && run.outline.waiting) return 'slide-text';
  // Mark this level ready leads only while something of the level waits for it.
  const shown = list(held.view?.cards).filter((one) => (one.level || '') === (held.level || ''));
  return levelCanBeReviewed(shown) && levelWaiting(shown).length ? 'ready' : '';
}

function slideTextReview(outline, held) {
  const path = view.path, turn = view.turn;
  const review = Drafting.slideContent({slides: outline.slides,
    label: 'Review slide text' + (outline.level ? ' · Level ' + outline.level : ''),
    note: held.slideTextNote || '', onNote: note => { held.slideTextNote = note; },
    onDecision: async (decision, note) => {
      const result = await send('outline', {path, level: outline.level || null,
        decision: decision === 'changes' ? 'revise' : 'approve', note, seen: outline.sha256});
      if (view.turn !== turn) return;
      held.slideTextNote = ''; view.run = result; await drawDesk(true);
    }});
  review.id = 'slide-text-review';
  // The note's label wraps it; it is also named by id, so every reader finds its name.
  const note = review.querySelector('textarea');
  const label = note && note.parentNode;
  if (note && label && label.tagName === 'LABEL') {
    note.id = 'slide-text-note';
    label.htmlFor = note.id;
    note.dataset.key = 'slide-text-note';
  }
  return review;
}

function trainingPlanReview(plan, held) {
  const path = view.path, turn = view.turn;
  const box = add(make('section', 'paper slide-text-review'),
    make('h2', 'doc-title', 'Here’s what this training will cover'),
    make('p', 'quiet', 'Check the topics, depth and order. Ask for changes, or let me build the selected materials from this plan.'));
  for (const level of list(plan.levels)) {
    if (level.level) box.append(make('h3', 'sheet-part', 'Level ' + level.level));
    if (list(level.objectives).length) box.append(bullets(level.objectives, 'outline-points'));
    const modules = make('ol', 'slide-text-list');
    for (const module of list(level.modules)) {
      const row = add(make('li', 'slide-text-item'), make('h3', 'row-title', module.title),
        make('p', 'quiet', module.minutes + ' minutes'), bullets(module.items, 'outline-points'));
      const practice = make('details', 'outline-notes');
      add(practice, make('summary', '', 'Examples and exercises'),
        module.example ? make('p', '', module.example) : null,
        ...list(module.practice).map(text => make('p', '', text)));
      row.append(practice); modules.append(row);
    }
    box.append(modules);
    if (level.gaps && level.gaps.trim()) box.append(add(make('details'),
      make('summary', '', 'Source gaps and exclusions'), make('p', 'desk-plain', level.gaps)));
  }
  const label = make('label', 'field');
  const input = make('textarea', 'input'); input.rows = 3; input.value = held.planNote || '';
  input.id = 'training-plan-note'; input.maxLength = 4000; label.htmlFor = input.id;
  input.dataset.key = 'training-plan-note';
  input.addEventListener('input', () => { held.planNote = input.value; });
  add(label, make('span', 'field-label', 'Anything to change?'), input);
  const levels = list(plan.levels).map(level => level.level).filter(Boolean);
  const scope = make('label', 'field');
  const select = make('select', 'input'); select.dataset.key = 'training-plan-scope';
  select.setAttribute('aria-label', 'Apply changes to');
  select.setAttribute('aria-describedby', 'training-plan-scope-help');
  for (const [value, text] of [['auto', 'Automatic — from my request'], ...levels.map(level => [level, 'Level ' + level + ' only']), ['all', 'All levels']]) {
    const option = make('option', '', text); option.value = value; select.append(option);
  }
  select.value = held.planScope || 'auto';
  const scopeNote = make('p', 'field-hint');
  scopeNote.id = 'training-plan-scope-help';
  const scopeChanged = () => {
    held.planScope = select.value;
    scopeNote.textContent = select.value === 'auto' ? 'Name a level in your request to revise only that plan. Choose All levels for broader changes.' : select.value === 'all' ? 'Revise every level’s plan. The research is kept.' : 'Revise only level ' + select.value + '. Other levels and the research are kept.';
  };
  select.addEventListener('change', scopeChanged); scopeChanged();
  add(scope, make('span', 'field-label', 'Apply changes to'), select, scopeNote);
  const problem = make('p', 'problem'); problem.setAttribute('role', 'alert');
  const change = capsule('Ask for changes', '', () => decide('changes'), 'training-plan-changes');
  const build = capsule('Build the training', 'filled', () => decide('approve'), 'training-plan-build');
  async function decide(decision) {
    if (view.busy) return;
    if (decision === 'changes' && !input.value.trim()) { problem.textContent = 'Say which topics, depth or examples should change.'; input.focus(); return; }
    view.busy = true; build.disabled = change.disabled = true; problem.textContent = '';
    try {
      const run = await send('training-plan', {path, expected: plan.expected, decision,
        note: decision === 'changes' ? input.value.trim() : null,
        ...(decision === 'changes' && select.value !== 'auto' ? {levels: select.value === 'all' ? levels : [select.value]} : {})});
      if (view.turn !== turn) return;
      held.planNote = ''; held.planScope = 'auto'; view.run = run;
    } catch (error) { problem.textContent = error.message; }
    finally { view.busy = false; build.disabled = change.disabled = false; }
    if (view.turn === turn && !problem.textContent) await drawDesk(true);
  }
  return add(box, label, levels.length > 1 ? scope : null, problem, add(make('div', 'bar'), change, build));
}

function paintDesk(fresh) {
  const active = document.activeElement;
  const editing = !fresh && active && ['TEXTAREA', 'INPUT'].includes(active.tagName)
    && main().contains(active) ? { key: active.dataset.key, start: active.selectionStart,
      end: active.selectionEnd } : null;
  const run = view.run;
  const held = deskHeld(view.path);
  const found = held.view;
  if (!run || !found) return;
  const ours = deskOurs();
  const conversation = found.execution === 'conversation';
  // The level is settled first: what leads depends on what of it waits for Mark ready.
  const tabs = deskTabs(found, held);
  const lead = deskLead(run, held, ours);
  const drawn = JSON.stringify([found, run.state, run.question, run.problem, run.documents,
    run.mine, run.driver, run.taken, run.notice, run.outline, run.training_plan, run.training_plan_pending,
    run.research_progress, run.timing, held.level, held.sources, held.material, held.said,
    held.unsent && list(held.unsent.files).map((file) => file.name), held.unsent
      && held.unsent.why, lead, narrow()]);
  if (!fresh && drawn === held.drawn) return;
  held.drawn = drawn;
  const named = list(found.levels).filter(Boolean);
  const level = held.level;
  const shown = list(found.cards).filter((one) => (one.level || '') === level);
  const waitingPlan = ours && run.training_plan && run.state === 'waiting';
  const preparingPlan = ours && run.training_plan_pending && !list(found.cards).some(one => one.kind !== 'blueprint' && one.seen);
  const actions = [];
  // Offered only while something of the level waits for it, and confirmed in a sheet that
  // names each material, whether it was opened, and what the Document Library keeps.
  const waiting = levelWaiting(shown);
  if (ours && !conversation && lead !== 'slide-text' && !preparingPlan && !waitingPlan
      && levelCanBeReviewed(shown) && waiting.length) {
    const mark = capsule(named.length ? 'Mark this level ready' : 'Mark every material ready',
      lead === 'ready' ? 'filled' : '', () => confirmLevel(level, waiting), 'desk-level-ready');
    actions.push(mark);
  }
  // The toolbar's Download is the whole level's; each material's own is on its card.
  if (!preparingPlan && !waitingPlan) actions.push(capsule(level ? 'Download level ' + level
    : 'Download all', '', openSheet('desk-download', 'desk-download-all'), 'desk-download-all'));
  if (ours && !conversation && !preparingPlan && !waitingPlan) {
    actions.push(capsule('Google Doc', '', openSheet('desk-copies', 'desk-copies'),
      'desk-copies'));
    actions.push(capsule('Finishing', '', () => openFinishing(), 'desk-finishing'));
  }
  const notice = held.said ? make('p', 'notice', held.said) : null;
  if (notice) notice.setAttribute('role', 'alert');
  const available = shown.filter(one => one.state !== 'left-out');
  if (!available.some(one => one.name === held.material[level])) {
    held.material[level] = (available.find(one => (one.seen && ['needs', 'held'].includes(one.state))
      || one.state === 'decide')
      || available.find(one => one.seen) || available[0])?.name;
  }
  const selected = held.sources ? 'sources' : held.material[level];
  // The version of each material shown here, for the Mark this level ready sheet.
  const opened = !held.sources && available.find((one) => one.name === selected);
  if (opened && opened.seen) (held.opened ||= {})[opened.name] = opened.seen;
  const options = [...available.map(one => ({id: one.name, label: cardTitle(one) + ' · '
    + (DESK_WORDS.tabs[one.state] || 'Draft')})),
    {id: 'sources', label: 'Research & sources'}];
  const materials = workspaceTabs('Training material', options, selected, id => {
    held.sources = id === 'sources';
    if (!held.sources) held.material[level] = id;
    paintDesk(true);
  }, 'desk-material');
  const column = add(make('div', 'desk-column'), ...shown.filter(one => one.name === selected).map(deskCard));
  if (!shown.length) column.append(make('p', 'quiet', 'Nothing is made at this level.'));
  const finishing = finishingMaterial();
  if (finishing) {
    finishing.panel = deskKit.panel(finishing); finishing.panelKey = deskKit.panelKey(finishing);
    // Finishing is scoped to this material; All materials is the way to check another.
    const others = capsule('All materials', 'quiet', () => openFinishing(true), 'desk-finishing-all');
    others.setAttribute('aria-label', 'Finishing: choose another material of this level');
    finishing.scope = add(make('p', 'quiet desk-finishing-scope'),
      'Checking ' + cardTitle(finishing.view) + ' only. ', others);
  }
  const layout = workspacePanel('desk-material', options.findIndex(one => one.id === selected),
    held.sources ? sourcesPart(found) : add(make('div', 'stack'), column,
      finishing ? finishing.scope : null, finishing ? finishing.panel : null));
  place({ title: found.title || 'Untitled', back: true,
    above: named.length ? [make('span', '', levelsText(named))] : [], actions }, [
    waitingPlan ? null : pageHead(preparingPlan ? 'I’ll prepare the topics and teaching plan for you to check, then build the training.' : conversation ? 'Read the retained materials. Make checked edits in conversation; only you mark a material ready.' : DESK_WORDS.lede),
    notice,
    conversation ? add(card('Editing in conversation'), make('p', '', 'No work is scheduled. Checked edits to the listed existing material parts and explicit broader scope changes happen in conversation; Mark ready is your decision.')) : null,
    found.saved_status ? add(card('Saved runner history'), make('p', '', 'The earlier runner was ' + found.saved_status.halt + '. That status remains in the original saved records; no work was resumed.')) : null,
    !ours && run.mine === false ? theirsPart(run, !view.sheet && !run.driver) : null,
    ours && run.notice ? noticePart(run) : null,
    ours ? needsPart(found, held, run) : null,
    conversation || waitingPlan ? null : progressPart(found, held, lead),
    waitingPlan ? trainingPlanReview(run.training_plan, held) : null,
    ours && run.outline?.content_first && run.outline.waiting ? slideTextReview(run.outline, held) : null,
    run.question && ours ? questionPart(run, found.title) : null,
    run.problem ? problemPart(run, lead === 'problem') : null,
    adding(run) && ours && !held.unsent ? documentsCard(run, lead === 'documents') : null,
    preparingPlan || waitingPlan ? null : tabs,
    preparingPlan || waitingPlan ? null : levelStanding(found, level),
    preparingPlan || waitingPlan ? null : materials,
    preparingPlan || waitingPlan ? null : layout,
  ], fresh);
  if (editing?.key && focusKey(editing.key) && typeof editing.start === 'number') {
    document.activeElement.selectionStart = editing.start;
    document.activeElement.selectionEnd = editing.end;
  }
}

// One of the person's decisions on the desk, answered with the desk again. What it was
// refused for, or where Mark this level ready stopped, is said on the desk.
async function deskDecide(route, sent, pressed, { flush = true } = {}) {
  if (view.busy) return null;
  const turn = view.turn;
  const path = view.path;
  const held = deskHeld(path);
  view.busy = true;
  held.said = '';
  if (pressed) pressed.disabled = true;
  let answer = null;
  // What was Ready before, so a change that makes one a draft again says so.
  const wasReady = new Set(list(held.view?.cards).filter((one) => one.state === 'ready')
    .map((one) => one.name));
  try {
    if (flush) await flushDesk(held);
    if (sent.seen && typeof sent.seen === 'string' && held.materials[sent.name]) {
      sent = { ...sent, seen: held.materials[sent.name].view.seen };
    }
    if (route === 'level-ready' || (route === 'draft' && !sent.undo)) {
      sent = { ...sent, seen: { ...sent.seen } };
      for (const name of Object.keys(sent.seen)) {
        if (held.materials[name]) sent.seen[name] = held.materials[name].view.seen;
      }
    }
    const { undo, ...body } = sent;
    answer = await send('drafts/' + route, { path, ...body });
    if (turn === view.turn) held.view = answer;
  } catch (failure) {
    if (turn === view.turn) held.said = failure.message;
  }
  view.busy = false;
  if (turn !== view.turn) return null;
  if (answer && route === 'level-ready') {
    if (answer.stopped) held.said = answer.stopped.said;
    if (list(answer.marked).length) readyToast(answer, answer.marked);
    else if (!answer.stopped) toast('Nothing here was waiting to be marked ready.');
  } else if (answer && route === 'ready') {
    readyToast(answer, [sent.name]);
  } else if (answer && route === 'draft') {
    draftToast(answer, list(answer.returned), sent.undo);
  } else if (answer && route === 'keep') {
    toast('Kept as it is.');
  } else if (answer && route === 'library-keep') {
    toast('Kept in the Document Library.');
  } else if (answer && route === 'update') {
    toast('It is being made again from what it is built from now.');
  } else if (answer && route === 'send') {
    // What Google refused is said by material: {name: sentence}.
    const problems = answer.problems && typeof answer.problems === 'object'
      ? Object.values(answer.problems).filter(Boolean).map(String) : [];
    toast(problems.length ? problems.join(' ') : 'Sent to its copies.');
  }
  // Any other change that made a Ready material a draft again, slide words among them.
  if (answer && route !== 'draft') {
    for (const one of list(answer.cards)) {
      if (wasReady.has(one.name) && one.state !== 'ready') toast(backToDraftWords(one, answer));
    }
  }
  if (pressed) pressed.disabled = false;
  if (view.sheet && DESK_SHEETS.includes(view.sheet)) drawSheet();
  paintDesk(false);
  // A card's Mark ready or Return to draft is gone once pressed: the toast's Undo, or the
  // card's Mark ready again, or its heading, takes the focus.
  if (answer && route === 'ready' && !focusKey('desk-ready ' + sent.name)) focusKey('desk-undo');
  if (answer && route === 'draft' && !sent.undo) {
    const name = Object.keys(sent.seen || {})[0];
    if (name && !focusKey('desk-ready ' + name)) byId(headingId(name))?.focus();
  }
  return answer;
}

// Mark this level ready: the drafts the sheet named, each with the version shown on it.
function markLevel(level, shown, pressed) {
  const seen = {};
  for (const one of shown) if (one.seen) seen[one.name] = one.seen;
  return deskDecide('level-ready', { level, seen }, pressed);
}

// The confirmation before Mark this level ready: each material it marks, whether it was
// opened here in the version shown, and which are kept in the Document Library. Nothing is
// sent until the person confirms; Cancel changes nothing and returns to the button.
function confirmLevel(level, waiting) {
  const held = deskHeld(view.path);
  const opened = held.opened || {};
  const rows = make('ul', 'rows');
  const unread = [];
  for (const one of waiting) {
    const read = opened[one.name] === one.seen;
    if (!read) unread.push(cardTitle(one));
    const open = read ? null : capsule('Open ' + cardTitle(one), 'quiet', () => {
      closeSheet();
      held.sources = false;
      held.material[level] = one.name;
      paintDesk(true);
      const heading = byId(headingId(one.name));
      if (heading) heading.focus();
    }, 'desk-level-open ' + one.name);
    rows.append(add(make('li', 'row step'), add(make('div', 'row-text'),
      make('p', 'step-name', cardTitle(one)), make('p', 'quiet', read ? 'Opened'
        : opened[one.name] ? 'Changed since you opened it' : 'Not opened yet')), open));
  }
  const kept = waiting.filter((one) => ['document', 'brief'].includes(one.kind)).map(cardTitle);
  const go = capsule('Mark ' + count(waiting.length, 'material', 'materials') + ' ready', 'filled',
    async () => {
      const answer = await markLevel(level, waiting, go);
      if (view.sheet === 'desk-kit') closeSheet();
      // The button is gone once nothing waits: the toast's Undo is the way back.
      if (answer && !focusKey('desk-level-ready')) focusKey('desk-undo');
    }, 'desk-level-ready-confirm');
  DESK.kitSheet = [sheetTitle(level ? 'Mark level ' + level + ' ready?' : 'Mark every material ready?'),
    make('p', '', 'Ready is your approval of the version you read.' + (unread.length
      ? ' Not opened yet: ' + series(unread) + '.' : ' You opened each of them.')),
    make('h3', 'sheet-part', '1. Materials to mark ready'), rows,
    make('h3', 'sheet-part', '2. The Document Library'),
    make('p', '', kept.length ? series(kept) + (kept.length === 1 ? ' is' : ' are')
      + ' kept in the Document Library as Markdown, as learners read '
      + (kept.length === 1 ? 'it.' : 'them.')
      : 'Nothing here goes to the Document Library: only a guide or a brief does.'),
    add(make('div', 'bar'), go, capsule('Cancel', 'quiet', () => closeSheet(), 'cancel'))];
  openSheet('desk-kit', 'desk-level-ready')();
}

// What Mark ready did, said with Undo while each version is the one marked: Undo returns
// them to exactly what they were, and says what the Document Library keeps.
function readyToast(answer, names) {
  const cards = list(answer.cards).filter((one) => list(names).includes(one.name)
    && one.state === 'ready');
  if (!cards.length) {
    toast('Marked ready.');
    return;
  }
  const library = answer.library || {};
  const kept = cards.filter((one) => (library[one.name] || {}).state === 'kept').map(cardTitle);
  const text = (cards.length === 1 ? cardTitle(cards[0]) + ' is marked ready.'
    : count(cards.length, 'material is', 'materials are') + ' marked ready.')
    + (kept.length ? ' ' + series(kept) + (kept.length === 1 ? ' is' : ' are')
      + ' kept in the Document Library.' : '');
  const undoable = cards.filter((one) => list(one.actions).includes('draft'));
  if (!undoable.length) {
    toast(text);
    return;
  }
  const seen = Object.fromEntries(undoable.map((one) => [one.name, one.seen]));
  toast(text, { label: 'Undo', key: 'desk-undo', run: async (control) => {
    const undone = await deskDecide('draft', { seen, undo: true }, control);
    if (undone && !focusKey('desk-level-ready')) {
      if (!focusKey('desk-ready ' + undoable[0].name)) byId('title').focus({ preventScroll: true });
    }
  } });
}

// What Return to draft or Undo did, with what the Document Library still keeps.
function draftToast(answer, names, undo) {
  const cards = list(answer.cards).filter((one) => names.includes(one.name));
  const library = answer.library || {};
  const text = (undo ? 'Undone. ' : '') + (cards.length === 1
    ? cardTitle(cards[0]) + ' is a draft again.'
    : count(cards.length, 'material is a draft', 'materials are drafts') + ' again.')
    + cards.filter((one) => (library[one.name] || {}).state === 'earlier')
      .map((one) => ' ' + (cards.length === 1 ? libraryEarlier(one, library[one.name])
        : 'The Document Library keeps revision ' + library[one.name].revision + ' of '
          + cardTitle(one) + ' until you mark it ready again.')).join('');
  toast(text);
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
    return [sheetTitle(level ? 'Download level ' + level : 'Download all'),
      make('p', '', 'Every written material of ' + where + ', one file each, exactly as it is '
      + 'saved now, Ready or a draft. Downloading marks nothing ready and sends nothing. One '
      + 'material alone downloads from its own card.'),
    ready.length ? items : make('p', 'quiet', 'Nothing of ' + where + ' is written yet.'),
    add(make('div', 'bar'), close)];
  }
  const docs = found.docs || {};
  const automatic = Object.values(docs).some((doc) => doc.automatic);
  if (automatic) {
    // A training started with Google Docs keeps them as it always did.
    const copied = shown.filter((one) => list(one.actions).includes('send'));
    const items = make('ul', 'rows');
    for (const one of copied) {
      const go = capsule('Send', '', () => deskDecide('send', { name: one.name }, go),
        'desk-send ' + one.name);
      go.setAttribute('aria-label', 'Send ' + one.label + ' to its Google Doc');
      items.append(add(make('li', 'row step'), add(make('div', 'row-text'),
        make('p', 'step-name', cardTitle(one)), make('p', 'quiet', one.says)), go));
    }
    return [sheetTitle('Google Doc'), make('p', '', 'This training keeps its Google Docs up '
      + 'to date by itself: marking a guide or brief Ready updates its Doc. Send updates it '
      + 'now, as it stands, before it is Ready.'),
    copied.length ? items : make('p', 'quiet', 'Every Google Doc of ' + where + ' is up to '
      + 'date, or waits for its material to be written.'),
    add(make('div', 'bar'), close)];
  }
  // Made with local copies: Ready is the person's approval here and sends nothing. A Doc of
  // one guide or brief is made, or updated, only when they ask, one version at a time.
  const items = make('ul', 'rows');
  const offered = shown.filter((one) => docs[one.name]);
  for (const one of offered) {
    const doc = docs[one.name];
    const text = add(make('div', 'row-text'), make('p', 'step-name', cardTitle(one)),
      make('p', 'quiet', doc.problem || docWords(doc)), copyLink({ link: doc.url }, 'Google Doc',
        'Google Doc of ' + one.label));
    const bar = make('div', 'bar');
    const offer = (label, act, key) => {
      const go = capsule(label, 'quiet', act, key + ' ' + one.name);
      go.setAttribute('aria-label', label + ' of ' + one.label);
      bar.append(go);
      return go;
    };
    if (!doc.problem && deskOurs()) {
      if (doc.changed) {
        // Changed in Google: bring its changes in, or leave it and make a new Doc.
        const pull = offer('Bring the Doc’s changes in', () => pullDoc(one.name, pull), 'desk-doc-pull');
        offer('Make a new Google Doc', () => docSheet(one.name, { fresh: true }), 'desk-doc-new');
      } else {
        offer(doc.action === 'update' ? 'Update the Google Doc' : 'Make a Google Doc',
          () => docSheet(one.name), 'desk-doc');
      }
    }
    items.append(add(make('li', 'row step'), text, bar.childNodes.length ? bar : null));
  }
  return [sheetTitle('Google Doc'), make('p', '', 'This training keeps its materials on this '
    + 'computer. Ready is your approval here and sends nothing. Make a Google Doc of a guide '
    + 'or brief when you want one; it is updated only when you ask.'),
  offered.length ? items : make('p', 'quiet', 'Nothing of ' + where + ' goes to a Google Doc: '
    + 'only a learner guide or a brief does.'),
  add(make('div', 'bar'), close)];
}

// Where one guide or brief stands in Google Docs, in a sentence.
function docWords(doc) {
  if (doc.uncertain) return 'The last try may have made a Doc: Google did not say.';
  if (!doc.url) return 'No Google Doc yet. Your download stays as it is.';
  if (doc.changed || doc.conflict) return 'Someone changed the Google Doc since it was last '
    + 'sent, so it is left as it is. Bring its changes in here, or make a new Google Doc; '
    + 'the edited Doc is kept either way.';
  return doc.current ? 'Its Google Doc has this version.'
    : 'Its Google Doc has an earlier version.';
}

// Bring a Doc's changes in from Google, as the person asks on the Google Doc sheet. Where
// both sides changed, the Doc's version is chosen only on a second, explicit press; this
// version stays in History.
async function pullDoc(name, control, choose) {
  const path = view.path, turn = view.turn;
  if (view.busy) return;
  view.busy = true; control.disabled = true;
  let answer = null, said = '';
  try {
    await flushDesk(deskHeld(path));
    answer = await send('copies', { path, pull: name, ...(choose ? { choose } : {}) });
    said = answer.said || '';
    deskHeld(path).view = await ask('drafts', { path });
  } catch (failure) {
    said = failure.message;
  } finally {
    view.busy = false; control.disabled = false;
  }
  if (view.turn !== turn) return;
  const both = answer && !choose && /Choose which to keep/.test(said);
  const theirs = both ? capsule('Use the Google Doc’s version', 'filled',
    () => pullDoc(name, theirs, 'theirs'), 'desk-doc-theirs') : null;
  DESK.kitSheet = [sheetTitle('Bring the Doc’s changes in'), make('p', '', said),
    both ? make('p', 'quiet', 'Your version on the desk stays in History.') : null,
    add(make('div', 'bar'), theirs, capsule('Close', 'quiet', closeSheet, 'cancel'))]
    .filter(Boolean);
  openSheet('desk-kit', '')();
  paintDesk(false);
}

// The one explicit delivery: which material, which version, where it goes, and whether it
// makes a new Doc or updates the linked one. The filled button authorizes exactly that.
// `fresh` makes a new Doc beside one that was changed in Google, which is left as it is.
// `said` is what the last try was answered with, shown again on the sheet drawn afresh.
async function docSheet(name, { fresh = false, said = '' } = {}) {
  const path = view.path, turn = view.turn;
  let doc;
  try {
    // The last seconds of typing are saved first, so the version shown is the one sent.
    await flushDesk(deskHeld(path));
    doc = await ask('drafts/doc-preview', { path, name });
  } catch (failure) {
    deskHeld(path).said = failure.message; closeSheet(); paintDesk(false); return;
  }
  if (view.turn !== turn) return;
  const status = make('p', 'notice', said);
  status.setAttribute('role', 'status');
  const creating = fresh || doc.action !== 'update';
  const facts = add(make('dl', 'about'),
    make('dt', '', 'Material'), make('dd', '', capital(doc.label)),
    make('dt', '', 'Version'), make('dd', '', 'As it is saved on the desk now ('
      + String(doc.seen).slice(0, 8) + ')'),
    make('dt', '', 'Goes to'), make('dd', '', creating ? 'A new Google Doc named “' + doc.title
      + '”, in the Google Drive this computer is signed in to'
      : 'The Google Doc “' + doc.title + '” it is linked to'));
  const deliver = async (control, again) => {
    if (view.busy) return;
    view.busy = true; control.disabled = true;
    say(status, creating ? 'Making the Google Doc…' : 'Updating the Google Doc…');
    let refused = null;
    try {
      const answer = await send('drafts/doc', { path, name, seen: doc.seen, again, fresh });
      if (view.turn !== turn) return;
      deskHeld(path).view = answer;
      const done = answer.doc;
      DESK.kitSheet = [sheetTitle(done.result === 'created' ? 'Google Doc made'
        : 'Google Doc updated'),
      make('p', '', (done.result === 'created' ? 'Made “' : 'Updated “') + done.title
        + '” with the version saved at ' + when(done.at) + '. Nothing was marked ready.'),
      copyLink({ link: done.url }, 'Google Doc', 'Google Doc of ' + doc.label),
      add(make('div', 'bar'), capsule('Close', 'quiet', closeSheet, 'cancel'))];
      openSheet('desk-kit', '')();
      paintDesk(false);
    } catch (failure) {
      refused = failure.message;
      say(status, refused);
    } finally {
      view.busy = false; control.disabled = false;
    }
    // Drawn again from what is true now: after an answer Google never gave, the one way on
    // is Make the Doc anyway; after a change in Google, the sheet's own two ways.
    if (refused && view.turn === turn) docSheet(name, { fresh, said: refused });
  };
  const label = doc.uncertain && creating ? 'Make the Doc anyway'
    : fresh ? 'Make a new Doc' : creating ? 'Make the Doc' : 'Update the Doc';
  const go = doc.changed && !fresh ? null : capsule(label, 'filled',
    () => deliver(go, Boolean(doc.uncertain)), 'desk-doc-go');
  DESK.kitSheet = [sheetTitle(fresh ? 'Make a new Google Doc' : creating ? 'Make a Google Doc'
    : 'Update the Google Doc'), facts,
  make('p', '', (fresh ? 'It makes one new Doc of exactly this version. The Doc that was '
    + 'changed in Google is left exactly as it is, and this material is linked to the new one.'
    : creating ? 'It makes one new Doc of exactly this version.'
      : 'It replaces the Doc’s text with exactly this version, unless someone changed the Doc '
      + 'since it was last sent.') + ' Nothing is marked ready, your file is kept as it is, '
    + 'and nothing else is sent.'),
  doc.uncertain ? make('p', 'notice', 'The last try may have made a Google Doc named “'
    + doc.title + '”: Google did not say. Look in Google Drive first. If there is none, '
    + 'make it anyway.') : null,
  doc.changed && !fresh ? make('p', 'notice', docWords(doc)) : null,
  status, add(make('div', 'bar'), go, capsule(go ? 'Cancel' : 'Close', 'quiet', closeSheet,
    'cancel'))].filter(Boolean);
  openSheet('desk-kit', '')();
}
