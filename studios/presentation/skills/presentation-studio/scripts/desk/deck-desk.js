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

  window.deckDesk = { init, opens, start };
  // The page waits for this script before it begins; it begins now.
  if (typeof window.deckDeskWaits === 'function') window.deckDeskWaits();
}());
