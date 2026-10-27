// The deck desk: a new deck's start in three steps, a desk deck's progress until it reaches
// the desk, and the desk itself, with a card per slide under its section, a note on a slide
// or on the whole deck, Stop, the Outline tab and Deliver.
//
// It draws with the page's own parts: app.js hands them to deckDesk.init once, before the
// page begins, so nothing here is a second copy of how the page makes a box, a button or a
// picture, or of how it talks to the server. The progress line is said in piece 3's words,
// from the shared desk kit (ui-kit/drafting.js). Every value from the server is set as text.
'use strict';

(function () {
  // What a step of the start, a pause and a line on the desk say.
  const KINDS_OF_DECK = [
    ['scratch', 'An idea', 'Say what it is about and who it is for. It is researched if you '
      + 'like, outlined, designed and built.'],
    ['document', 'A document', 'A script, notes or a write-up. It is read first, to tell a '
      + 'finished script from material to build from.'],
    ['existing', 'An existing deck', 'A .pptx or a Google Slides deck. The original is never '
      + 'changed: a new copy is made.'],
  ];
  const LOOKS = [['pick', 'Pick it when the samples are drawn'],
    ['default', 'Use the brand’s default look']];
  const READINGS = [['spec', 'It lays out the slides'], ['material', 'It is material to build from']];
  const READ_AS = { spec: 'Read as a script for the slides.',
    material: 'Read as material to build from.' };
  // Which gap the start puts the focus in first, in the order the sheet is filled.
  const GAPS = ['research-documents', 'research-sites', 'new-minutes', 'new-title', 'new-file',
    'new-text', 'new-link'];
  const NOTHING_NEEDED = 'Nothing needed from you. The deck opens here when it is ready.';
  const NO_RECORD = 'This computer has no record yet of how long that takes.';
  const LOOK_PAUSE = 'One thing needs you: pick the look. The deck is drawn in it.';
  const DESK_LEDE = 'A card for each slide. A note on a slide redraws only its section; '
    + 'Deliver sends the deck.';
  const WORDS_LINE = 'A note changes how the slide is drawn. To change its words, edit them on '
    + 'the Outline tab.';
  const NO_NOTE = 'Say how the slide should change.';
  const NO_DECK_NOTE = 'Say how the whole deck should change.';
  const NOTE_SAYS = {
    waiting: 'Your note waits to be drawn: ',
    drawing: 'Being redrawn with your note: ',
    done: 'Redrawn with your note: ',
    'set aside': 'Not redrawn: you stopped the whole-deck note.',
  };

  // The page's parts, from app.js, and the shared desk kit's progress words.
  let h = null;
  let kit = null;
  // What the person has typed or chosen and not sent: kept for each deck, so that a screen
  // drawn again, because the deck moved on, still has it.
  const held = { notes: {}, deck: {}, previews: {}, looks: {}, outlines: {}, tabs: {} };

  function init(parts) {
    h = parts;
    kit = typeof Drafting === 'undefined' ? null : Drafting.kit({});
  }

  function opens(run) {
    return Boolean(run && run.desk);
  }

  function make(tag, className, text) {
    return h.make(tag, className, text);
  }

  function bar(...children) {
    return h.add(make('div', 'bar'), ...children);
  }

  // A box whose label reads the same on every card, with the slide named for a screen reader.
  function noteField(id, label, kept, named, spec) {
    const node = h.field(id, label, kept, 'note', { long: true, limit: 4000, ...(spec || {}) });
    if (named) node.querySelector('label').append(make('span', 'offscreen', ' ' + named));
    return node;
  }

  // --- the start -----------------------------------------------------------------------------
  // Three numbered steps: the kind of deck, its sources and settings, and what you have. Start
  // sends it as a desk deck. An existing deck keeps the page's own form for now.

  function start() {
    const draft = h.view.draft;
    if (!draft.look) draft.look = 'pick';
    if (draft.readAs === undefined) draft.readAs = '';
    const go = h.submitButton('Start', 'continue');
    const cancel = h.capsule('Cancel', 'quiet', h.closeSheet, 'cancel');
    const drafted = make('span', '');
    const told = () => {
      drafted.textContent = 'It is drafted by ' + h.words.AGENT_NAMES[draft.agent]
        + h.draftModelWords(draft) + '.';
    };
    told();
    const form = make('form', 'create-flow');
    form.noValidate = true;
    // Enter in a box starts the deck, as Start does: every step is checked first.
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      h.startDeck(go, { ready, form: formFor });
    });
    h.add(form, h.createStep(1, 'Kind of deck', kindCards(draft)));
    if (draft.route) {
      h.add(form, h.createStep(2, 'Sources and settings', ...settingsStep(draft, told)),
        h.createStep(3, 'What you have', ...haveStep(draft)));
    }
    const says = make('span', '', startsSays(draft));
    says.id = 'new-starts';
    h.add(form, draft.route ? h.add(make('p', 'quiet'), says, ' ', drafted, ' You can close '
      + 'this page meanwhile.') : null, h.alertLine('new-problem'),
    h.add(make('div', 'bar create-foot'), draft.route ? go : null, cancel));
    return [h.add(make('div', 'sheet-heading'), h.sheetTitle('New deck')), form];
  }

  function kindCards(draft) {
    const node = make('div', 'pick-cards');
    node.setAttribute('role', 'group');
    node.setAttribute('aria-label', 'Kind of deck');
    for (const [route, title, says] of KINDS_OF_DECK) {
      h.add(node, h.pickCard(title, says, draft.route === route, () => {
        h.chooseRoute(route);
        h.paintNew(false);
        h.readAgents();
        h.readModels(draft.agent);
      }, 'kind ' + route));
    }
    return node;
  }

  // What happens once it starts, as the look chosen says.
  function startsSays(draft) {
    return draft.look === 'default'
      ? 'It starts at once and runs on its own, with no stops. The deck opens here when it is '
        + 'ready, for you to change and deliver.'
      : 'It starts at once and runs on its own. It stops once, for you to pick the look when '
        + 'the samples are drawn; then the deck opens here, for you to change and deliver.';
  }

  function settingsStep(draft, told) {
    const limits = (h.view.setup && h.view.setup.limits) || {};
    const words = h.words;
    const research = h.chip('Research first', draft.research, (on) => {
      draft.research = on;
      h.paintNew(false);
    }, 'research');
    const options = make('details', 'new-options');
    options.dataset.key = 'new-options';
    const summary = make('summary', '', 'Options');
    summary.dataset.key = 'new-options-summary';
    h.add(options, summary,
      make('p', 'quiet', [words.AGENT_NAMES[draft.agent] + h.draftModelWords(draft),
        h.limitsSays(limits) || 'no limits'].join(' · ')),
      ...h.agentFields(draft, 'new', 'For this deck', told),
      make('p', 'quiet', (h.limitsSays(limits) || 'No limits are set for this computer.')
        + ' A deck that reaches a limit stops and asks you. The limits are changed in '
        + 'Settings.'));
    return [
      h.add(make('div', 'field'), research, make('p', 'quiet field-hint',
        (draft.route === 'document' ? 'Only where your document turns out to be material to '
          + 'build from. ' : '') + 'The research is planned from your questions, or from the '
          + 'goal, and done on its own. What it found is kept with the deck.')),
      draft.research ? h.researchFromField(draft) : null,
      draft.research ? h.field('research-questions', 'What should the research answer? '
        + '(optional)', draft, 'researchQuestions', { long: true, rows: 4,
        hint: 'One question a line, at most 8.' }) : null,
      h.field('new-minutes', 'About how long, in minutes (optional)', draft, 'minutes',
        { short: true, mode: 'numeric' }),
      h.field('new-audience', 'Who is it for?', draft, 'audience', { long: true, limit: 2000,
        hint: 'Their role, and what they already know.' }),
      h.choice('Is this deck for a talk or a handout?', words.DELIVERIES.map((one) => one[1]),
        h.deliveryOf(draft), (index) => { draft.delivery = index; }, 'delivery',
        'A talk is presented, with fewer words on each slide; a handout is read on its own.'),
      h.brandFields(draft, 'new'),
      ...h.explained('Delivered as', words.OUTPUTS.map((one) => one[1]), words.OUTPUT_SAYS,
        draft.output, (index) => {
          draft.output = index;
          h.paintNew(false);
        }, 'new-output'),
      words.OUTPUTS[draft.output][0] === 'google' && !h.googleReady()
        ? make('p', '', words.NOT_CONNECTED) : null,
      h.choice('The look', LOOKS.map((one) => one[1]),
        Math.max(0, LOOKS.findIndex((one) => one[0] === draft.look)), (index) => {
          draft.look = LOOKS[index][0];
          const said = h.byId('new-starts');
          if (said) said.textContent = startsSays(draft);
        }, 'new-look', 'The brand draws a slide of your outline in each of its looks. Pick '
          + 'one then, or leave it to the brand.'),
      options,
    ];
  }

  function haveStep(draft) {
    const nodes = [
      h.field('new-title', 'A short title', draft, 'title', { limit: 120,
        hint: 'What it is called in every list, for example “Rolling restarts”.' }),
      h.field('new-goal', 'What should they take away?', draft, 'goal', { long: true,
        limit: 2000, hint: 'A sentence or two is enough.' }),
    ];
    if (draft.route === 'scratch') {
      nodes.push(h.field('new-notes', 'What should it cover? (optional)', draft, 'notes',
        { long: true, limit: 4000, hint: 'Points, examples or a rough order. It goes to the '
          + 'research and the outline.' }));
    }
    if (draft.route === 'document') {
      nodes.push(make('p', '', 'The document: a script, notes, a write-up or a transcript.'),
        ...h.sourceFields(draft), readingField(draft));
    }
    return nodes;
  }

  // How the document is read, when you know: it lays out the slides, or it is material to
  // build from. Left unset, it is read first, to tell which.
  function readingField(draft) {
    const at = READINGS.findIndex((one) => one[0] === draft.readAs);
    const node = h.choice('How it is read (optional)', READINGS.map((one) => one[1]), at,
      (index) => {
        draft.readAs = READINGS[index][0];
        h.paintNew(false);
      }, 'new-reading', 'Left unset, it is read first, to tell a finished script from '
        + 'material to build from.');
    if (draft.readAs) {
      h.add(node, bar(h.capsule('Leave it to the reading', 'quiet', () => {
        draft.readAs = '';
        h.paintNew(false);
      }, 'new-reading-unset')));
    }
    return node;
  }

  // Every step is checked before anything is sent; the first gap, in the order the sheet is
  // filled, has the focus.
  function ready(draft) {
    const names = ['What it is about', ...(draft.route === 'document' ? ['Your document'] : [])];
    const rank = (key) => (GAPS.includes(key) ? GAPS.indexOf(key) : GAPS.length);
    const missing = names.flatMap((name) => h.missingIn(draft, name))
      .sort((one, other) => rank(one) - rank(other));
    h.say(h.byId('new-problem'), missing.length ? 'Something above is missing.' : '');
    if (missing.length && !h.focusKey(missing[0]) && h.byId(missing[0])) {
      h.byId(missing[0]).focus();
    }
    return !missing.length;
  }

  // The form as the runner takes a desk deck: its flow, its look and, for a document, how it
  // is read when that was said. A desk deck has no review level and no first-draft choice.
  function formFor(draft) {
    const [form, uploads] = h.formOf(draft);
    for (const gone of ['review_level', 'review_seen', 'review_default', 'initial_review']) {
      delete form[gone];
    }
    form.flow = 'desk';
    form.look = draft.look === 'default' ? 'default' : 'pick';
    if (draft.route === 'document' && draft.readAs) form.reading = draft.readAs;
    return [form, uploads];
  }

  // --- what both screens share --------------------------------------------------------------

  // A change sent from the desk. Its answer is the deck's view, drawn at once. A refusal is
  // said beside what was pressed, or as a toast, and nothing changes.
  async function act(route, body, pressed, done, problem) {
    if (h.view.busy) return null;
    const turn = h.view.turn;
    const path = h.view.path;
    h.view.busy = true;
    if (pressed) pressed.disabled = true;
    let found;
    try {
      found = await h.send(route, body);
    } catch (failure) {
      h.view.busy = false;
      if (pressed) pressed.disabled = false;
      if (problem) h.say(problem, failure.message + ' Nothing was changed.');
      else h.toast(failure.message + ' Nothing was changed.');
      return null;
    }
    h.view.busy = false;
    if (done) h.toast(done);
    if (turn === h.view.turn && h.view.screen === 'deck' && h.view.path === path) {
      h.view.run = found;
      h.paintDeck(false);
    }
    h.refresh();
    return found;
  }

  // What comes before everything else: a teammate's hold, a question, a step that stopped
  // (with Try again, Give it more time, or Resume at the spend limit) and a team notice.
  function interruptions(run, lead, title) {
    const read = h.theirs(run);
    return [
      read && (run.driver || run.state !== 'finished') ? ['theirs', [run.driver, run.taken,
        run.notice, run.last_shared, run.kept, title], () => h.theirsPart(run, false)] : null,
      run.question && !read ? ['question', [run.question, title],
        () => h.questionPart(run, title)] : null,
      run.problem ? ['problem', [run.problem, lead, read, run.build_sections],
        () => h.problemPart(run, lead === 'problem')] : null,
      !read && run.notice ? ['notice', [run.notice, run.clash, run.kept],
        () => h.noticePart(run)] : null,
    ];
  }

  function above(run) {
    const route = h.routeWords(run);
    const runs = h.theirs(run) ? (run.driver ? 'Run by ' + h.nameOf(run.driver)
      : 'Nobody is running it') : run.driver ? 'Runs on this computer' : '';
    return [make('span', '', [route, 'On the desk', runs].filter(Boolean).join(' · '))];
  }

  // Pause, Resume and Delete, under More. Stop on the desk is the redraw's own, on its line.
  function moreFor(run) {
    if (h.theirs(run)) return null;
    const items = [];
    const steer = (label, action) => {
      const node = h.button(label, 'menu-item', () => h.steer(action, node), 'desk ' + action);
      items.push(node);
    };
    if (run.state === 'working') steer('Pause', 'pause');
    if (['paused', 'stopped'].includes(run.state) && !(run.problem && run.problem.action)) {
      steer('Resume', 'resume');
    }
    items.push(h.button('Delete this deck', 'menu-item', h.askDelete('delete'), 'delete'));
    return h.moreMenu('More', items, 'desk-more');
  }

  // --- progress: before the deck reaches the desk -------------------------------------------

  function progress(run, fresh) {
    const read = h.theirs(run);
    const gate = run.gate;
    const pause = !read && gate && gate.name === 'gate:look' && gate.offered
      && !gate.offered.chosen;
    const lead = h.view.sheet || read ? '' : run.question ? 'answer'
      : run.problem && run.problem.action ? 'problem' : pause ? 'look'
        : ['paused', 'stopped'].includes(run.state) ? 'resume' : '';
    h.view.lead = lead;
    const title = run.title || 'Untitled';
    const desk = run.desk;
    const previews = run.build_progress && h.list(run.build_progress.slides).length;
    h.placeParts({ title, above: above(run), back: true, actions: progressActions(run, lead),
      mark: ['progress', title, run.state, lead, read, run.driver, Boolean(run.question),
        run.problem] }, [
      ...interruptions(run, lead, title),
      pause ? ['look-pause', [gate, lead], () => lookPause(run, lead === 'look')]
        : ['progress', [run.state, run.sentence, desk.progress, Boolean(run.question),
          run.problem], () => progressPart(run)],
      previews ? ['previews', [run.build_progress, read, run.mine],
        () => previewsCard(run)] : null,
    ], fresh);
    h.tidyPictures();
  }

  // Pause and Stop while it works, Resume once it is paused or stopped, then More.
  function progressActions(run, lead) {
    if (h.theirs(run)) return [];
    const actions = [];
    const press = (label, kind, action) => {
      const node = h.capsule(label, kind, () => h.steer(action, node), action);
      actions.push(node);
    };
    if (run.state === 'working') press('Pause', '', 'pause');
    if (['working', 'waiting', 'paused'].includes(run.state)) press('Stop', 'quiet', 'stop');
    if (['paused', 'stopped'].includes(run.state) && !(run.problem && run.problem.action)) {
      press('Resume', lead === 'resume' ? 'filled' : '', 'resume');
    }
    actions.push(h.moreMenu('More', [h.button('Delete this deck', 'menu-item',
      h.askDelete('delete'), 'delete')], 'desk-more'));
    return actions;
  }

  // The progress line: nothing is needed, and about how long, in piece 3's words; then the
  // step it is at, in words, and how long it has taken.
  function progressPart(run) {
    const found = run.desk.progress || {};
    const node = make('div', 'intro');
    const asked = Boolean(run.question || (run.problem && run.problem.action));
    if (run.state === 'working' && !asked) {
      const left = found.minutes_left;
      const timed = typeof left === 'number' && left > 0;
      const lede = make('p', 'lede', timed && kit ? kit.estimate({ minutes_left: left },
        'The deck') : NOTHING_NEEDED);
      lede.setAttribute('role', 'status');
      h.add(node, lede, timed ? null : make('p', 'quiet', NO_RECORD));
    } else if (run.state === 'paused') {
      h.add(node, make('p', 'lede', 'Paused. Nothing more is started until you resume it. '
        + 'Everything made so far is kept.'));
    } else if (['stopped', 'failed'].includes(run.state) && !run.problem) {
      h.add(node, make('p', 'lede', 'Stopped before the deck was ready. Everything made so far '
        + 'is kept; Resume carries on from where it stopped.'));
    } else {
      h.add(node, make('p', 'lede', 'The deck opens here when it is ready.'));
    }
    if (run.state === 'working' && run.sentence) h.add(node, make('p', '', run.sentence));
    if (run.state === 'working' && found.started_at && kit) {
      h.add(node, make('p', 'quiet desk-clock', kit.clock(found)));
    }
    return node;
  }

  // The one pause a desk deck makes, when its start chose to pick the look. It leads the
  // screen, and nothing else on it asks for a decision.
  function lookPause(run, lead) {
    const gate = run.gate;
    const offered = gate.offered;
    const path = h.view.path;
    const key = path + '\n' + gate.round;
    const pick = held.looks[key] || (held.looks[key] = { look: '', words: '' });
    const node = h.card('Pick the look', 'card-needs');
    h.add(node, make('p', '', LOOK_PAUSE),
      make('p', 'quiet', 'Made in ' + (gate.made_in || 'your brand') + '. The brand drew one '
        + 'slide of your outline in each of its looks. The look you pick sets the colours, '
        + 'what each colour means and how cards are drawn on every slide.'),
      window.DeckPanels.lookPicker({
        name: 'the deck', looks: h.list(offered.looks), defaultId: offered.default,
        sheet: offered.sheet, notes: h.list(offered.notes), failed: offered.failed,
        picked: { choice: pick.look, words: pick.words },
        changed: (now) => {
          pick.look = now.choice;
          pick.words = now.words;
        },
        picture: (number, alt) => h.picture({ kind: 'look', ref: number === 0 ? 'sheet'
          : number }, alt, gate.round) }));
    const problem = h.alertLine('look-problem');
    if (offered.failed) {
      const again = h.capsule('Draw the looks again', '', () => act('desk-look-again',
        { path }, again, 'The looks are being drawn again.', problem), 'look-again');
      const plain = h.capsule('Use the brand’s default look', lead ? 'filled' : '', () => act(
        'desk-look', { path, look: 'default' }, plain, 'The deck is drawn in the brand’s '
          + 'default look.', problem), 'look-default');
      return h.add(node, problem, bar(plain, again));
    }
    const go = h.capsule('Draw the deck in this look', lead ? 'filled' : '', () => {
      if (!pick.look) {
        h.say(problem, 'Pick a look first.');
        return;
      }
      const named = h.list(offered.looks).find((one) => one.id === pick.look);
      const words = (pick.words || '').trim();
      act('desk-look', { path, look: pick.look, ...(words ? { note: words } : {}) }, go,
        'The deck is drawn in ' + (named ? named.name : 'that look') + ' now.', problem);
    }, 'look-pick');
    return h.add(node, problem, bar(go));
  }

  // The slides as they are drawn, each with one box for a note to its section.
  function previewsCard(run) {
    const found = run.build_progress;
    const read = h.theirs(run);
    const node = h.card('Slides taking shape');
    h.add(node, make('p', 'quiet', found.incomplete ? 'The render stopped before it '
      + 'finished. These previews are kept so you can look at them.'
      : 'Each slide shows here as it is drawn. A note on one goes to the part of the deck '
        + 'that draws it.'));
    const slides = h.list(found.slides).map((one) => ({ ...one, partial: true,
      where: h.pictureOf(h.view.path, { kind: 'progress', ref: one.ref }), mark: one.ref }));
    if (slides.length) {
      h.add(node, h.pager(slides, (one) => [one.part !== 'whole' && run.mine && !read
        ? previewNote(one) : null]));
    }
    return node;
  }

  function previewNote(one) {
    const path = h.view.path;
    const key = path + '\n' + one.ref;
    const kept = held.previews[key] || (held.previews[key] = { note: '' });
    const id = 'preview-note-' + one.ref;
    const box = noteField(id, 'How should this slide change?', kept, 'Slide ' + one.number);
    const go = h.capsule('Send note', '', async () => {
      const note = kept.note.trim();
      if (!note) {
        h.refuse(id, NO_NOTE);
        return;
      }
      const sent = await sendFeedback(path, one, note, go);
      if (!sent) return;
      kept.note = '';
      const input = h.byId(id);
      if (input) input.value = '';
    }, 'preview-send ' + one.ref);
    return h.add(make('div', 'answer'), box, bar(go));
  }

  // A note on a slide while it is drawn: kept for its section, as the page always sent it.
  async function sendFeedback(path, one, note, pressed) {
    if (h.view.busy) return false;
    h.view.busy = true;
    pressed.disabled = true;
    try {
      // Its number too: a note that comes after the section is drawn is kept for the desk.
      const found = await h.send('build-feedback', {path, ref: one.ref, note, number: one.number});
      h.view.busy = false;
      h.toast('Your note on slide ' + one.number + ' is kept for the part of the deck that '
        + 'draws it.');
      if (path === h.view.path) {
        h.view.run = found;
        h.paintDeck(false);
      }
      return true;
    } catch (failure) {
      h.view.busy = false;
      h.refuse('preview-note-' + one.ref, failure.message + ' Your note is still here.');
      return false;
    } finally {
      pressed.disabled = false;
    }
  }

  window.deckDesk = { init, opens, start, progress };
  // The page waits for this script before it begins; it begins now.
  if (typeof window.deckDeskWaits === 'function') window.deckDeskWaits();
}());
