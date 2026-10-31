// The deck desk: a new deck's start in three steps, a desk deck's progress until it reaches
// the desk, and the desk itself, with a card per slide under its section, a note on a slide
// or on the whole deck, Stop, the Outline tab and Deliver.
//
// It draws with the page's own parts: app.js hands them to deckDesk.init once, before the
// page begins, so nothing here is a second copy of how the page makes a box, a button or a
// picture, or of how it talks to the server. The progress line is said in piece 3's words,
// from the shared desk kit (ui-kit/drafting.js), and so are the selection bar's actions and
// History's word compare. Every value from the server is set as text.
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
  const GAPS = ['new-file', 'new-text', 'new-link', 'level brand-only', 'new-selected',
    'new-title', 'new-minutes', 'research-urls', 'research-documents', 'research-sites'];
  // The levels of an existing deck whose looks are drawn, for the person to pick from.
  const LOOKED_LEVELS = ['redesign', 'rework'];
  const NOTHING_NEEDED = 'Nothing needed from you. The deck opens here when it is ready.';
  const CONTENT_NEXT = 'Drafting the slide text. You will approve it before design starts.';
  const NO_RECORD = 'This computer has no record yet of how long that takes.';
  const LOOK_PAUSE = 'One thing needs you: pick the look. The deck is drawn in it.';
  const DESK_LEDE = 'Choose a slide to read it and change it. A note on a slide redraws only '
    + 'its section; Deliver sends the deck.';
  const OWN_LEDE = 'Choose a slide of your deck to read it and change its words, or note it to '
    + 'plan its changes again: only a copy is changed, and Deliver sends it.';
  // A slide's words, each a box on its card, in the order the slide reads: the field the
  // runner names it by, and what its box is called.
  const WORD_FIELDS = [['title', 'Title'], ['subtitle', 'Subtitle'], ['detail', 'Detail'],
    ['caveat', 'Caveat'], ['source', 'Source']];
  const SAVE_WAIT = 1000;   // a typed edit is saved one second after the last key
  // What each kept version of a slide's words was kept before.
  const VERSION_SOURCES = {
    save: 'Before words you typed', selection: 'Before a change to selected words',
    note: 'Before a note redrew the slide', redraw: 'Before the slide was redrawn with new words',
    restore: 'Before an earlier version was restored', outline: 'Before the outline was saved',
    finishing: 'Before a change from Finishing', open: 'As it was when it came to the desk',
  };
  const NO_NOTE = 'Say how the slide should change.';
  const NO_DECK_NOTE = 'Say how the whole deck should change.';
  const NOT_DELIVERABLE = 'The deck cannot be delivered yet: a change to it is still waiting '
    + 'or under way. Deliver when it is done.';
  // The runner's own refusal of a save while the deck is redrawn (desk.OUTLINE_BUSY).
  const OUTLINE_BUSY = 'The deck is being redrawn now. Save the outline when that ends.';
  const NOTE_SAYS = {
    waiting: 'Your note waits to be drawn: ',
    drawing: 'Being redrawn with your note: ',
    done: 'Redrawn with your note: ',
    'set aside': 'Not redrawn: you stopped the whole-deck note.',
  };

  // Sources, research and Finishing.
  const SOURCE_TYPES = '.txt,.md,.html,.htm,.docx,.pdf,application/pdf';
  const SOURCES_SAY = 'The words jobs and the speaker notes read your sources, and so does the '
    + 'outline when it is written again. Adding one runs no research: Research again does, '
    + 'when you ask.';
  const NO_TEXT = 'Paste the text of the source first.';
  // Where a file added here is kept: the deck has it either way.
  const KEEP_CHOICES = ['Keep in library', 'Only this project'];
  const KEEP_SAYS = 'Keep in library also saves the file in the Document Library on this '
    + 'computer, for any studio to use. It is shared with no one either way.';
  const FINISH_TOOLS = [
    ['brand', 'Brand check', 'What the brand’s check says of each slide, what blocks '
      + 'delivery first. Check it again in seconds.'],
    ['review', 'Review the deck', 'A reviewer looks at every slide. What it finds comes back '
      + 'here, slide by slide.'],
    ['notes', 'Speaker notes', 'Notes proposed for every slide. Applying them redraws nothing.'],
    ['rehearse', 'Rehearse', 'How long your speaker notes take to say, against your minutes.'],
  ];
  const BRAND_SAYS = 'The last render’s brand check, slide by slide, what blocks delivery '
    + 'first. Apply redraws a slide’s section with the check’s words as its note.';
  const KIND_TAGS = { blocker: 'Blocks delivery', warning: 'Warning' };

  // The page's parts, from app.js, and the shared desk kit's progress words.
  let h = null;
  let kit = null;
  // What the person has typed or chosen and not sent: kept for each deck, so that a screen
  // drawn again, because the deck moved on, still has it.
  const held = { notes: {}, deck: {}, previews: {}, looks: {}, outlines: {}, tabs: {},
    // Typed words not saved yet, by deck, slide and field; the words selected now; the
    // History sheet's slide and what it read; and the slide chosen on the desk, by deck.
    edits: {}, selection: null, history: null, slide: {},
    // A source being added, the findings ticked to leave out, and Finishing: the panel's
    // state as the shared kit holds it, the proposal whose price is shown before it is
    // applied, and the words of a proposal being edited.
    sources: {}, leave: {}, finish: {}, confirm: {}, editing: {} };

  // The shared kit's Finishing panel, bound to this page: its shell and its list of tools
  // are the kit's, and each tool's view is the deck's own (`finishView`).
  const FINISHING = {
    ui: {
      button: (label, action) => h.capsule(label, 'quiet', () => action()),
      pickCard: (title, says, action) => h.pickCard(title, says, false, action,
        'desk-finish ' + title),
      narrow: () => false,
    },
    hooks: { render: () => h.paintDeck(false) },
    tools: () => FINISH_TOOLS.map(([key, name, says]) => ({ key, name, says,
      open: (state) => openTool(state, key), view: () => finishView(key) })),
  };
  // This page's editing session: the saves made in it keep one version of a slide.
  const SESSION = Array.from({ length: 16 },
    () => '0123456789abcdef'[Math.floor(Math.random() * 16)]).join('');
  let saving = null;

  function init(parts) {
    h = parts;
    kit = typeof Drafting === 'undefined' ? null : Drafting.kit(FINISHING);
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
  // Three numbered steps, in the order a deck is thought of: what it starts from, with the
  // material itself; who it is for and what they should take away; then research and the
  // settings, with the defaults folded away. Under them, what happens after Start, said from
  // the choices made, and Start. Start sends it as a desk deck.

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
    const plan = make('div', 'new-plan');
    plan.id = 'new-roadmap';
    const retell = () => plan.replaceChildren(...roadmapParts(draft));
    retell();
    const form = make('form', 'create-flow');
    form.noValidate = true;
    // Enter in a box starts the deck, as Start does: every step is checked first.
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      h.startDeck(go, { ready, form: formFor });
    });
    h.add(form, h.createStep(1, 'What you start from', kindCards(draft),
      ...(draft.route ? sourceStep(draft) : [])));
    if (draft.route) {
      h.add(form, h.createStep(2, 'Audience and goal', ...goalStep(draft)),
        h.createStep(3, 'Research and settings', ...settingsStep(draft, told, retell)),
        h.add(make('section', 'create-step'), make('h3', 'sheet-part', 'What happens after Start'),
          plan, h.add(make('p', 'quiet'), drafted, ' You can close this page meanwhile.')));
    }
    h.add(form, h.alertLine('new-problem'),
      h.add(make('div', 'bar create-foot'), draft.route ? go : null, cancel));
    return [h.add(make('div', 'sheet-heading'), h.sheetTitle('New deck')), form];
  }

  function kindCards(draft) {
    const node = make('div', 'pick-cards');
    node.setAttribute('role', 'group');
    node.setAttribute('aria-label', 'What you start from');
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

  // The material the deck starts from, under its kind: what an idea should cover, the
  // document and how it is read, or the deck and how much of it changes.
  function sourceStep(draft) {
    if (draft.route === 'scratch') {
      return [h.field('new-notes', 'What should it cover? (optional)', draft, 'notes',
        { long: true, limit: 4000, hint: 'Points, examples or a rough order. It goes to the '
          + 'research and the outline.' })];
    }
    if (draft.route === 'document') {
      return [make('p', '', 'The document: a script, notes, a write-up or a transcript.'),
        ...h.sourceFields(draft), readingField(draft)];
    }
    return [make('p', '', 'Your deck: the original is never changed. What you get is always '
      + 'a new copy.'), ...h.sourceFields(draft), ...levelCards(draft)];
  }

  // How much of an existing deck changes: five cards, under the deck. Selected changes adds
  // its box under them.
  function levelCards(draft) {
    const node = make('div', 'pick-cards');
    node.setAttribute('role', 'group');
    node.setAttribute('aria-label', 'How much changes');
    for (const [level, title, says] of h.words.LEVELS) {
      h.add(node, h.pickCard(title, says, draft.level === level, () => {
        draft.level = level;
        h.paintNew(false);
      }, 'level ' + level));
    }
    const selected = draft.level === 'selected' ? h.field('new-selected',
      'Which slides, and what to fix', draft, 'selected', { long: true, limit: 4000,
        hint: 'For example: “Slides 3 and 7: the chart is unreadable. Slide 12: shorten the '
          + 'bullets.” Only those slides change.' }) : null;
    return [make('p', 'field-label', 'How much changes'), node,
      h.alertLine('new-level-problem'), selected];
  }

  // Whether the deck's looks are drawn for it: from an idea or a document, and an existing
  // deck redesigned or reworked.
  function looked(draft) {
    return draft.route !== 'existing' || LOOKED_LEVELS.includes(draft.level);
  }

  // Whether its slide text is drafted, for the person to approve before anything is
  // designed: wherever an outline is written, from an idea, a document or a full rework.
  function outlined(draft) {
    return draft.route !== 'existing' || draft.level === 'rework';
  }

  // What happens after Start, from what the start says now: research where it is asked for,
  // the slide text to approve wherever it is drafted, the look where one is drawn, then the
  // desk and Deliver. Every deck from this start approves its text before it is designed;
  // a deck saved before keeps the decisions it was saved with. Null until an existing deck
  // says how much changes.
  function roadmap(draft) {
    const existing = draft.route === 'existing';
    if (existing && !draft.level) return null;
    const text = outlined(draft);
    const picks = looked(draft) && draft.look !== 'default';
    const steps = [];
    // How the document is read is kept when the kind changes, and matters only for one.
    const script = draft.route === 'document' && draft.readAs === 'spec';
    if (!existing && draft.research && !script) {
      steps.push(['Research.', (draft.route === 'document' && !draft.readAs
        ? 'Only if your document turns out to be material to build from. ' : '')
        + 'It is planned from your questions, or from the goal, and done on its own.']);
    }
    if (text) {
      steps.push(['Approve the slide text.', 'The titles, the words on each slide, their '
        + 'order and the speaker notes are drafted first. Read them, ask for changes, or '
        + 'choose Approve text & design deck. Nothing is designed until you approve.']);
    }
    if (looked(draft)) {
      const after = text ? 'once the text is approved, ' : '';
      // A brand that has no looks to show draws the deck in its own, with no stop.
      steps.push(picks ? ['Pick the look.', capital(after + 'the brand draws a slide in each '
        + 'of its looks, and the deck is drawn in the one you pick. A brand with no looks to '
        + 'show uses its own, with no stop.')]
        : ['The brand’s default look.', capital(after + 'the slides are designed in it, with '
          + 'no stop.')]);
    }
    // An existing deck kept as it says is changed after its look, the way the runner goes.
    if (!text) steps.push(['The changes are made.', 'On a copy of your deck, on its own.']);
    steps.push(['Review the deck.', 'It opens on the desk, a card for each slide: change its '
      + 'words, or note a slide to redraw it.'],
    ['Deliver.', 'Always yours, when the deck is right.']);
    const waits = [text ? 'approve the slide text' : '', picks ? 'pick the look' : '']
      .filter(Boolean);
    return { steps, says: waits.length ? 'Before the desk, it waits for you '
      + (waits.length > 1 ? 'twice: to ' + waits.join(', then to ') : 'to ' + waits[0]) + '.'
      : 'It runs on its own until the deck opens on the desk.' };
  }

  function capital(said) {
    return said.charAt(0).toUpperCase() + said.slice(1);
  }

  function roadmapParts(draft) {
    const found = roadmap(draft);
    if (!found) {
      return [make('p', '', 'Choose how much changes, and what happens after Start is listed '
        + 'here.')];
    }
    return [make('p', '', found.says), h.add(make('ol', 'new-roadmap'),
      ...found.steps.map(([name, says]) => h.add(make('li', ''), make('strong', '', name),
        ' ' + says)))];
  }

  // Who it is for and what they should take away: the title, the audience, the goal, how
  // long and whether it is presented.
  function goalStep(draft) {
    const words = h.words;
    return [
      h.field('new-title', 'A short title', draft, 'title', { limit: 120,
        hint: 'What it is called in every list, for example “Rolling restarts”.' }),
      h.field('new-audience', 'Who is it for?', draft, 'audience', { long: true, limit: 2000,
        hint: 'Their role, and what they already know.' }),
      h.field('new-goal', 'What should they take away?', draft, 'goal', { long: true,
        limit: 2000, hint: 'A sentence or two is enough.' }),
      h.field('new-minutes', 'About how long, in minutes (optional)', draft, 'minutes',
        { short: true, mode: 'numeric' }),
      h.choice('Is this deck for a talk or a handout?', words.DELIVERIES.map((one) => one[1]),
        h.deliveryOf(draft), (index) => { draft.delivery = index; }, 'delivery',
        'A talk is presented, with fewer words on each slide; a handout is read on its own.'),
    ];
  }

  // The brand and variant and how it is delivered, as the draft has them: "Made in Acme
  // (dark), delivered as Google Slides.", then whether those are the defaults still.
  function defaultsSays(draft) {
    const found = h.brandsFound();
    const brand = found.find((one) => one.brand === draft.brand);
    const named = brand ? (brand.name || brand.brand) + (draft.variant ? ' (' + draft.variant
      + ')' : '') : '';
    const output = h.words.OUTPUTS[draft.output][1];
    return (named ? 'Made in ' + named + ', delivered as ' : 'Delivered as ') + output
      + (changedFromDefaults(draft, found) ? '. Changed for this deck.'
        : '. These start as your defaults.');
  }

  // Whether the brand, its variant or the output differ from what Settings starts a deck
  // with. A default brand this computer does not have is not counted as changed.
  function changedFromDefaults(draft, found) {
    const setup = h.view.setup || {};
    const chosen = (setup.brand && setup.brand.default) || {};
    const output = setup.output === 'pptx' ? 1 : 0;
    const known = found.some((one) => one.brand === chosen.brand);
    return draft.output !== output || (known && (draft.brand !== chosen.brand
      || Boolean(chosen.variant) && draft.variant !== chosen.variant));
  }

  function settingsStep(draft, told, retell) {
    const limits = (h.view.setup && h.view.setup.limits) || {};
    const words = h.words;
    // An existing deck has no research: what it says is the deck's own.
    const researched = draft.route !== 'existing';
    const research = researched ? h.chip('Research first', draft.research, (on) => {
      draft.research = on;
      h.paintNew(false);
    }, 'research') : null;
    const branded = h.brandsFound().length > 0;
    const defaults = make('p', 'quiet', defaultsSays(draft));
    // The brand, the output and the assistant start as the defaults, and change for this
    // deck alone under one disclosure, which the line above it keeps up with.
    const options = make('details', 'new-options');
    options.dataset.key = 'new-options';
    options.addEventListener('change', () => { defaults.textContent = defaultsSays(draft); });
    const summary = make('summary', '', 'Brand, output and assistant');
    summary.dataset.key = 'new-options-summary';
    h.add(options, summary,
      branded ? h.brandFields(draft, 'new') : null,
      ...h.explained('Delivered as', words.OUTPUTS.map((one) => one[1]), words.OUTPUT_SAYS,
        draft.output, (index) => {
          draft.output = index;
          h.paintNew(false);
        }, 'new-output'),
      make('p', 'quiet', [words.AGENT_NAMES[draft.agent] + h.draftModelWords(draft),
        h.limitsSays(limits) || 'no limits'].join(' · ')),
      ...h.agentFields(draft, 'new', 'For this deck', told),
      make('p', 'quiet', (h.limitsSays(limits) || 'No limits are set for this computer.')
        + ' A deck that reaches a limit stops and asks you. The limits are changed in '
        + 'Settings.'));
    const asked = researched && draft.research;
    const text = outlined(draft);
    return [
      researched ? h.add(make('div', 'field'), research, make('p', 'quiet field-hint',
        (draft.route === 'document' ? 'Only where your document turns out to be material to '
          + 'build from. ' : '') + 'The research is planned from your questions, or from the '
          + 'goal, and done on its own. What it found is kept with the deck.')) : null,
      asked ? h.researchFromField(draft) : null,
      asked ? h.field('research-questions', 'What should the research answer? '
        + '(optional)', draft, 'researchQuestions', { long: true, rows: 4,
        hint: 'One question a line, at most 8.' }) : null,
      looked(draft) ? h.choice('The look', LOOKS.map((one) => one[1]),
        Math.max(0, LOOKS.findIndex((one) => one[0] === draft.look)), (index) => {
          draft.look = LOOKS[index][0];
          retell();
        }, 'new-look', (text ? 'Once the slide text is approved, the' : 'The') + ' brand '
          + 'draws a slide in each of its looks. Pick one then, or leave it to the brand.')
        : null,
      // With no brand skill to choose from, what to do about it is said in the open.
      branded ? null : h.brandFields(draft, 'new'),
      words.OUTPUTS[draft.output][0] === 'google' && !h.googleReady()
        ? make('p', '', words.NOT_CONNECTED) : null,
      defaults,
      options,
    ];
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
    const names = ['What it is about', ...(draft.route === 'document' ? ['Your document']
      : draft.route === 'existing' ? ['Your deck and what changes'] : [])];
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
    const runs = run.execution === 'conversation' ? 'In conversation' : h.theirs(run) ? (run.driver ? 'Run by ' + h.nameOf(run.driver)
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

  // The look waits for the person's pick: at the start's pause, or on the desk after Change
  // the look, or after the document is read the other way on a deck that picks.
  function pausedAtLook(run) {
    const gate = run.gate;
    return !h.theirs(run) && Boolean(gate && gate.name === 'gate:look' && gate.offered
      && !gate.offered.chosen);
  }

  function progress(run, fresh) {
    const read = h.theirs(run);
    const gate = run.gate;
    const pause = pausedAtLook(run);
    const lead = h.view.sheet || read ? '' : run.question ? 'answer'
      : run.problem && run.problem.action ? 'problem' : pause ? 'look'
        : ['paused', 'stopped'].includes(run.state) ? 'resume' : '';
    h.view.lead = lead;
    const title = run.title || 'Untitled';
    const desk = run.desk;
    const previews = run.build_progress && h.list(run.build_progress.slides).length;
    h.placeParts({ title, above: above(run), back: true, actions: progressActions(run, lead),
      mark: ['progress', title, run.state, lead, read, run.driver, Boolean(run.question),
        run.problem, gate] }, [
      ...interruptions(run, lead, title),
      gate?.content_first && gate.name === 'gate:outline' ? ['slide-text', [gate, read], () => slideTextReview(run, read)] : null,
      pause ? ['look-pause', [gate, lead], () => lookPause(run, lead === 'look')]
        : ['progress', [run.state, run.sentence, desk.progress, Boolean(run.question),
          run.problem], () => progressPart(run)],
      previews ? ['previews', [run.build_progress, read, run.mine],
        () => previewsCard(run)] : null,
    ], fresh);
    h.tidyPictures();
  }

  function slideTextReview(run, read) {
    const gate = run.gate, path = h.view.path;
    if (read) return h.make('p', 'quiet', 'Slide text is waiting for approval on its owner’s computer.');
    return Drafting.slideContent({slides: gate.slides,
      note: held.deck[path]?.slideTextNote || '',
      onNote: note => { (held.deck[path] ||= {}).slideTextNote = note; },
      onDecision: async (decision, note) => {
        const found = await h.send('decide', {path, gate: 'gate:outline', decision, note, expected: gate.expected});
        if (h.view.path !== path) return;
        (held.deck[path] ||= {}).slideTextNote = ''; h.view.run = found; h.refresh();
      }});
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
      const pending = run.desk.content_pending;
      const timed = !pending && typeof left === 'number' && left > 0;
      const lede = make('p', 'lede', timed && kit ? kit.estimate({ minutes_left: left },
        'The deck') : pending ? CONTENT_NEXT : NOTHING_NEEDED);
      lede.setAttribute('role', 'status');
      h.add(node, lede, timed || pending ? null : make('p', 'quiet', NO_RECORD));
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

  // --- the desk -----------------------------------------------------------------------------

  function desk(run, fresh) {
    const found = run.desk;
    const read = h.theirs(run);
    const path = h.view.path;
    const title = run.title || 'Untitled';
    const working = Boolean(found.working);
    const pause = pausedAtLook(run);
    const lead = h.view.sheet || read ? '' : run.question ? 'answer'
      : run.problem && run.problem.action ? 'problem' : pause ? 'look'
        : run.execution === 'conversation' ? (found.can_mark_ready ? 'ready' : '')
          : found.delivered || found.deliverable === false ? '' : 'deliver';
    h.view.lead = lead;
    const own = found.level === 'selected';
    const tab = !own && held.tabs[path] === 'outline' ? 'outline' : 'slides';
    const can = !read && found.drawn_here && run.execution !== 'conversation';
    const finish = can && !own && kit && finishing();
    h.placeParts({ title, above: above(run), back: true, actions: deskActions(run, lead),
      mark: ['desk', title, run.state, lead, read, run.driver, working, found.drawn_here,
        Boolean(found.delivered), found.expected, h.view.downloading, finish] }, [
      ...interruptions(run, lead, title),
      pause ? ['look-pause', [run.gate, lead], () => lookPause(run, lead === 'look')] : null,
      working ? ['working', [found.working, read], () => workingPart(run)] : null,
      !found.drawn_here ? ['away', [found.no_drawing, found.draw_here_price, read, working],
        () => run.execution === 'conversation' ? h.add(h.card('Drawing'),
          make('p', '', 'No checked drawing is available here. Continue the focused work in conversation.')) : awayPart(run)] : null,
      found.delivered ? ['delivered', [found.delivered, title], () => deliveredPart(run)]
        : null,
      run.execution === 'conversation' ? ['conversation', [found.ready, found.ready_problem],
        () => h.add(make('div', 'intro'), make('p', '', found.ready
          ? 'Ready. Your approval is recorded; nothing has been delivered.'
          : 'Work continues in conversation. Mark ready after reviewing the checked deck.'),
        found.ready_problem ? make('p', 'quiet', found.ready_problem) : null)] : null,
      found.saved_status ? ['saved-status', [found.saved_status], () => h.add(h.card('Saved runner history'),
        make('p', '', found.saved_status.why || 'The previous runner stopped.'),
        make('p', 'quiet', 'That stop is retained in History. Conversation editing will not resume that runner.'))] : null,
      found.revision ? ['revision', [found.revision], () => make('p', 'quiet', found.revision)]
        : null,
      ['head', [tab, own, run.execution], () => headPart(tab, own, run.execution === 'conversation')],
      can && tab === 'slides' && !found.words_locked ? ['selection-bar', [path],
        () => selectionBar()] : null,
      layoutPart(run, tab, own, can, working, finish, fresh),
    ], fresh);
    h.tidyPictures();
  }

  // The slides, or the Outline tab, in a column, and beside it on a wide screen the aside
  // with Sources and Research, or Finishing while it is open (the aside then ends the
  // column). Each part in them is drawn again only when what it shows changed, as every part
  // of the page is.
  function layoutPart(run, tab, own, can, working, finish, fresh) {
    const read = h.theirs(run);
    const column = tab === 'outline' ? outlineParts(run, can, working)
      : slideParts(run, can, working);
    const aside = !read && tab === 'slides' && !own ? ['aside', asideKey(run),
      () => asidePart(run)] : null;
    const side = finish ? ['finishing', finishKey(run), () => finishPart(run)] : aside;
    if (finish && aside) column.push(aside);
    return ['desk-layout', [Boolean(side), Boolean(finish)],
      () => make('div', side ? 'desk-layout' + (finish ? ' desk-finishing' : '') : ''),
      (node) => h.fit(node, [['desk-column', [], () => make('div', 'desk-column'),
        (inner) => h.fit(inner, column, fresh)], side], fresh)];
  }

  // Whether Deliver can be pressed now: the deck rests on the desk, drawn here, with no change
  // waiting or under way, as the runner says (desk.deliverable).
  function deliverableNow(found) {
    return found.deliverable !== false && !found.working && Boolean(found.drawn_here)
      && Boolean(found.expected);
  }

  // Deliver, the one filled button, then Download and More.
  function deskActions(run, lead) {
    if (h.theirs(run)) return [];
    const found = run.desk;
    const deliver = found.delivered || run.execution === 'conversation' ? null : h.capsule('Deliver', lead === 'deliver' ? 'filled'
      : '', h.openSheet('desk-deliver', 'deliver'), 'deliver');
    if (deliver) {
      deliver.disabled = !deliverableNow(found);
    }
    const download = found.drawn_here ? h.capsule(h.view.downloading ? 'Downloading…'
      : 'Download', '', () => h.downloadDeck(run, download), 'download') : null;
    // Finishing opens as a panel beside the slides: the brand check, the review, speaker
    // notes and rehearse.
    const finish = run.execution !== 'conversation' && found.drawn_here && kit && found.level !== 'selected'
      ? h.capsule(finishing() ? 'Close Finishing' : 'Finishing', '', toggleFinishing,
        'desk-finishing') : null;
    const ready = run.execution === 'conversation' && !found.ready && !found.delivered
      ? h.capsule('Mark ready', lead === 'ready' ? 'filled' : '',
        () => openDeskPreview(run, 'ready'), 'mark-ready') : null;
    if (ready) ready.disabled = !found.can_mark_ready;
    return [ready, deliver, download, finish, moreFor(run)];
  }

  // The redraw under way, said above the desk, with Stop.
  function workingPart(run) {
    const path = h.view.path;
    const stop = h.theirs(run) ? null : h.capsule('Stop', '', () => act('desk-stop', { path },
      stop, 'Stopped. What was redrawn is kept, and the deck is put together from it.'),
    'desk-stop');
    return h.callout('', h.add(make('p', 'desk-working-note'), h.state('current',
      run.desk.working.what)), stop ? make('p', 'quiet', 'Stop keeps what is redrawn so far, '
      + 'and puts the deck together from it.') : null, stop ? bar(stop) : null);
  }

  // A deck whose drawing is on another computer: the shared words, and the way to draw it here.
  function awayPart(run) {
    const found = run.desk;
    const path = h.view.path;
    const go = h.theirs(run) ? null : h.capsule('Draw it here', '', () => act('desk-draw-here',
      { path }, go, 'The deck is being drawn on this computer.'), 'desk-draw-here');
    if (go) go.disabled = Boolean(found.working);
    return h.callout('', make('p', '', found.no_drawing || ''), go ? bar(go) : null,
      go && found.draw_here_price ? make('p', 'quiet', found.draw_here_price) : null);
  }

  function deliveredPart(run) {
    const found = run.desk.delivered;
    const node = h.card('Delivered');
    h.add(node, h.state('done', 'Delivered as revision ' + (found.revision || 1) + '.'),
      found.url ? bar(h.outLink(found.url, 'Open in Google Slides', 'Open ' + (run.title
        || 'the deck') + ' in Google Slides')) : null,
      run.desk.reviewed ? null : make('p', 'quiet', 'It was delivered without a review of the '
        + 'deck.'),
      make('p', 'quiet', 'A note or an edit here makes the next revision, delivered when you '
        + 'press Deliver. This one is kept.'));
    // Delivered as a PowerPoint file: the same deck goes to Google Slides on request.
    const sent = run.deliver || {};
    if (sent.to_google && !h.theirs(run) && h.googleReady()) {
      const google = h.capsule(h.view.delivering ? 'Delivering…' : 'Send to Google Slides', '',
        () => h.deliverToGoogle(run, google), 'deliver-google');
      h.add(node, make('p', 'quiet', 'The same deck goes to Google Slides as the next '
        + 'revision. Nothing in it is built again.'), bar(google));
    }
    return node;
  }

  // The one sentence of the desk, and its two tabs. Your own deck at Selected changes has no
  // outline: its slides are the deck's.
  function headPart(tab, own, conversation) {
    if (conversation) return h.pageHead('Inspect saved slide parts and edit through checked conversation commands, then explicitly mark the checked deck ready.', []);
    if (own) return h.pageHead(OWN_LEDE, []);
    const tabs = h.segmented('The desk', ['Slides', 'Outline'], tab === 'outline' ? 1 : 0,
      (index) => {
        held.tabs[h.view.path] = index ? 'outline' : 'slides';
        h.paintDeck(false);
      }, 'desk-tab');
    tabs.classList.add('deck-desk-tabs');
    return h.pageHead(DESK_LEDE, [tabs]);
  }

  // --- the Slides tab: the workbench -----------------------------------------------------------
  // What stands before Deliver, in a short summary whose lines go to their slides; then the
  // navigator, every slide by its number, title and picture, beside (or, on a narrow screen,
  // above) the one slide chosen, read first and changed in place; and last, folded away, the
  // note for the whole deck. The slide chosen is kept for each deck: it stays through the
  // Outline tab, Finishing, History and Deliver, and through a reload, where the browser keeps
  // it with the screen. Words typed on a slide stay typed when another slide is chosen.

  // Every slide of the deck in order, each with the section it is in.
  function deckCards(run) {
    return h.list(run.desk.sections).flatMap((part) => h.list(part.slides)
      .filter((one) => one && typeof one.number === 'number')
      .map((one) => ({ one, part })));
  }

  // The brand check's blockers on one slide: what Deliver lists, by its slide.
  function blockersOn(run, one) {
    return h.list(run.desk.blockers).filter((line) => line.number === one.number);
  }

  // A fix proposed by the review or the brand check for one slide, still to apply or skip.
  // The brand check's are only those made from the last render's check, as Finishing shows.
  function proposalsOn(run, one) {
    const found = run.desk;
    const sets = found.finishing || {};
    return ['brand', 'review'].flatMap((key) => {
      const set = sets[key];
      if (!set || (key === 'brand' && !found.brand_current)) return [];
      return h.list(set.items).filter((item) => item.state === 'open' && item.present
        && item.number === one.number).map((item) => ({ key, set, item }));
    });
  }

  // The words typed on a slide and not saved yet, on this page.
  function unsavedOn(path, one) {
    return Object.values(held.edits).some((edit) => edit.path === path
      && edit.number === one.number);
  }

  // What was found on a slide, each thing once. Finishing's proposals are made from the same
  // review findings and brand check lines the slide carries: a finding or a line that a
  // proposal still open stands for is shown, and counted, as that proposal alone.
  function foundOn(run, one) {
    const proposals = h.theirs(run) ? [] : proposalsOn(run, one);
    const finding = (item) => [item.severity || '', item.note || item.question || ''].join('\n');
    const reviewed = new Set(proposals.filter(({ key }) => key === 'review')
      .map(({ item }) => finding(item)));
    const checked = new Set(proposals.filter(({ key }) => key === 'brand')
      .map(({ item }) => item.says));
    return { proposals,
      findings: h.list(one.findings).filter((item) => !reviewed.has(finding(item))),
      audit: h.list(one.audit).filter((line) => !checked.has(line.says)) };
  }

  // What a slide asks of the person, what is under way on it, and what is worth a look, each
  // said in a few words. Blockers come first; a warning never reads as one.
  function marksOf(run, one) {
    const path = h.view.path;
    const blocks = blockersOn(run, one);
    const found = foundOn(run, one);
    const waits = [];
    const kept = one.note && one.note.status === 'set aside';
    if (kept) waits.push('not redrawn when the whole-deck note was stopped: Redraw slide '
      + one.number + ' draws it again');
    if (one.unfit) waits.push('words that do not fit: redraw or discard them');
    if (unsavedOn(path, one)) waits.push('words not saved yet');
    if (one.note && one.note.status === 'waiting') waits.push('your note waits to be drawn');
    // A fix for a blocker is counted with the blocker, once.
    const fixes = found.proposals.filter(({ key, item }) => !(key === 'brand'
      && item.kind === 'blocker'));
    if (fixes.length) waits.push(h.count(fixes.length, 'fix', 'fixes') + ' to apply or skip');
    const looks = [];
    if (found.findings.length) {
      looks.push(h.count(found.findings.length, 'review finding', 'review findings'));
    }
    const warnings = found.audit.filter((line) => line.kind !== 'error').length;
    if (warnings) looks.push(h.count(warnings, 'brand warning', 'brand warnings'));
    const busy = Boolean(one.busy) || Boolean(one.note && one.note.status === 'drawing');
    return { blocks, waits, looks, busy,
      tag: blocks.length ? 'Blocks delivery' : busy ? 'Redrawing' : kept ? 'Not redrawn'
        : waits.length ? 'Waits for you' : looks.length ? 'Worth a look' : '' };
  }

  // The slide chosen: the one kept for this deck, by its ID, else by its number (an outline
  // saved since may have moved it), else the first that asks something of the person, else
  // the first. A slide chosen for the person is kept as if they chose it, so the desk does
  // not move away from it when what drew it there is resolved.
  function activeOf(run, cards) {
    const path = h.view.path;
    if (!held.slide[path]) {
      const saved = window.history && window.history.state;
      if (saved && saved.path === path && saved.deskSlide) {
        held.slide[path] = { id: saved.deskSlide, number: saved.deskNumber };
      }
    }
    const kept = held.slide[path];
    const found = kept && (cards.find(({ one }) => one.id === kept.id)
      || cards.find(({ one }) => one.number === kept.number));
    if (found) return found;
    const first = cards.find(({ one }) => one.unfit || blockersOn(run, one).length) || cards[0];
    if (!first) return null;
    remember(path, first.one);
    return first;
  }

  // The browser keeps the slide with the screen, so a reload opens the deck at it.
  function remember(path, one) {
    held.slide[path] = { id: one.id, number: one.number };
    try {
      const now = window.history.state;
      if (now && now.path === path && now.deskSlide !== one.id) {
        window.history.replaceState({ ...now, deskSlide: one.id, deskNumber: one.number }, '');
      }
    } catch (failure) {
      // A browser that keeps nothing with the screen keeps the slide for this page only.
    }
  }

  // Go to a slide. The focus goes where it was asked to: the control that was pressed, kept
  // by its key, or the slide itself, for a line of the summary.
  function choose(one, focus) {
    remember(h.view.path, one);
    if (!(held.selection && held.selection.asking)) {
      held.selection = null;
      const selection = h.byId('desk-selection');
      if (selection) selection.hidden = true;
    }
    h.paintDeck(false);
    if (focus === 'slide') {
      const heading = h.byId('desk-slide-title');
      if (heading) heading.focus();
    } else if (focus) {
      h.focusKey(focus);
    }
  }

  function slideParts(run, can, working) {
    const found = run.desk;
    const path = h.view.path;
    const cards = deckCards(run);
    const active = activeOf(run, cards);
    const marks = cards.map(({ one }) => [one.number, one.id, one.words && one.words.title,
      one.image, marksOf(run, one).tag]);
    const proposals = active ? proposalsOn(run, active.one).map(({ item }) => item) : [];
    return [
      ['summary', [marks, cards.map(({ one }) => marksOf(run, one)), found.blockers,
        found.reviewed, found.deliverable, found.working, found.drawn_here, found.expected,
        run.output, h.googleReady(), Boolean(found.delivered), found.revision, h.theirs(run),
        run.execution], () => summaryPart(run, cards)],
      cards.length ? ['desk-bench', [], () => make('div', 'desk-bench'),
        (inner) => h.fit(inner, [
          ['navigator', [marks, active.one.id, found.expected],
            () => navigatorPart(run, cards, active)],
          ['slide', [active.one, active.part.slides.map((one) => one.number), found.expected,
            can, working, found.words_locked, found.notes_locked, proposals,
            held.confirm[path] || '', h.theirs(run)],
          () => slideCard(run, active.one, active.part, can)],
        ], false)] : null,
      can && found.level !== 'selected' ? ['whole', [found.expected, found.deck_price, working,
        cards.length, h.list(found.sections).filter((part) => !part.lead).length],
      () => wholePart(run, working, cards)] : null,
    ];
  }

  // --- the summary: what stands before Deliver ----------------------------------------------

  // A line of the summary that goes to its slide.
  function jump(one, words) {
    const go = h.button('Slide ' + one.number, 'link', () => choose(one, 'slide'),
      'desk-jump ' + one.id);
    go.setAttribute('aria-label', 'Go to slide ' + one.number);
    return h.add(make('li'), go, ': ' + words);
  }

  const SUMMARY_LINES = 5;   // the lines of each list of the summary, before the rest are counted

  function summaryList(title, says, lines) {
    if (!lines.length) return null;
    // A long list stays short: the rest are counted, and the navigator marks each of them.
    const more = lines.length - SUMMARY_LINES;
    const shown = more > 1 ? lines.slice(0, SUMMARY_LINES) : lines;
    return h.add(make('div', 'desk-summary-part'), make('p', 'row-title', title),
      says ? make('p', 'quiet', says) : null, h.add(make('ul', 'plain'), ...shown,
        more > 1 ? make('li', 'quiet', 'And ' + more + ' more. The navigator marks each '
          + 'slide.') : null));
  }

  function summaryPart(run, cards) {
    const found = run.desk;
    const read = h.theirs(run);
    const conversation = run.execution === 'conversation';
    // Where there is no Deliver here (a deck run in conversation, one delivered, or a
    // teammate's), the summary says where the deck stands, not what stands before Deliver.
    const delivers = !read && !conversation && !found.delivered;
    const node = h.card(delivers ? 'Before you deliver' : 'Where the deck stands',
      'desk-summary');
    const blockers = h.list(found.blockers);
    const marked = cards.map(({ one }) => ({ one, marks: marksOf(run, one) }));
    const waiting = marked.filter(({ marks }) => marks.waits.length || marks.busy);
    const looks = marked.filter(({ marks }) => marks.looks.length);
    const ready = deliverableNow(found);
    const checked = blockers.length ? 'The brand check found ' + h.count(blockers.length,
      'problem that blocks', 'problems that block') + ' delivery.'
      : 'The brand check found nothing that blocks delivery.';
    h.add(node, make('p', '', !delivers ? checked : !found.drawn_here ? 'Nothing can be '
      + 'delivered from this computer until the deck is drawn here.' : !ready ? NOT_DELIVERABLE
      : blockers.length ? h.count(blockers.length, 'problem blocks', 'problems block')
        + ' delivery. Deliver asks you before it sends the deck anyway.'
        : 'Nothing blocks delivery.'));
    const byNumber = new Map(cards.map(({ one }) => [one.number, one]));
    h.add(node,
      summaryList('Blocks delivery', 'The brand check found these on the last render.',
        blockers.map((line) => (byNumber.has(line.number) ? jump(byNumber.get(line.number),
          line.says) : make('li', '', line.says)))),
      summaryList('Waiting for you', '', waiting.map(({ one, marks }) => jump(one,
        h.capital([...(marks.busy ? ['being redrawn'] : []), ...marks.waits].join('; '))
          + '.'))),
      summaryList('Worth a look', 'These do not block delivery.', looks.map(({ one, marks }) =>
        jump(one, marks.looks.join(' and ') + '.'))));
    if (delivers) {
      h.add(node, h.add(make('div', 'desk-summary-part'),
        make('p', 'row-title', 'What Deliver will use'),
        make('p', '', 'The ' + h.count(cards.length, 'slide', 'slides') + ' as they are drawn '
          + 'now, ' + (found.reviewed ? 'reviewed as they are' : 'not reviewed: only the brand '
          + 'check ran') + '. ' + deliveredAs(run) + ' Nothing is sent until you confirm it in '
          + 'Deliver.')));
    }
    return node;
  }

  // Where Deliver sends the deck, as its sheet says it.
  function deliveredAs(run) {
    const google = run.output === 'google';
    return google && h.googleReady() ? 'It goes to Google Slides.'
      : google ? 'Google is not connected on this computer, so it is made a PowerPoint file.'
        : 'It is made a PowerPoint file, to download from here.';
  }

  // --- the navigator --------------------------------------------------------------------------
  // Every slide, by its number, its title and its picture, with a word for what it asks of
  // you. Previous and Next step through them; the arrow keys, Home and End do in the list.

  function navigatorPart(run, cards, active) {
    const node = make('nav', 'desk-navigator');
    node.setAttribute('aria-label', 'Slides');
    const at = cards.indexOf(active);
    const to = (index, focus) => {
      const next = cards[Math.max(0, Math.min(cards.length - 1, index))];
      if (next && next !== active) choose(next.one, focus);
    };
    const earlier = h.capsule('Previous', '', () => to(at - 1, 'desk-previous'),
      'desk-previous');
    const later = h.capsule('Next', '', () => to(at + 1, 'desk-next'), 'desk-next');
    earlier.setAttribute('aria-label', 'Previous slide');
    later.setAttribute('aria-label', 'Next slide');
    earlier.setAttribute('aria-disabled', String(at === 0));
    later.setAttribute('aria-disabled', String(at === cards.length - 1));
    const now = make('p', 'slide-now', 'Slide ' + active.one.number + ' of ' + cards.length);
    now.setAttribute('role', 'status');
    const strip = make('ol', 'strip desk-nav-list');
    const keys = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };
    cards.forEach(({ one }, index) => {
      const words = one.words || {};
      const tag = marksOf(run, one).tag;
      const item = h.button('', 'strip-item', () => {
        if (index !== at) choose(one, 'desk-go ' + one.id);
      }, 'desk-go ' + one.id);
      item.setAttribute('aria-label', h.slideName({ number: one.number, title: words.title })
        + (one.hidden ? ', hidden' : '') + (tag ? ', ' + h.lower(tag) : ''));
      if (index === at) item.setAttribute('aria-current', 'true');
      item.addEventListener('keydown', (event) => {
        const by = keys[event.key];
        const target = event.key === 'Home' ? 0 : event.key === 'End' ? cards.length - 1
          : by ? index + by : -1;
        if (target < 0 || target >= cards.length || target === index) return;
        if (event.preventDefault) event.preventDefault();
        choose(cards[target].one, 'desk-go ' + cards[target].one.id);
      });
      h.add(strip, h.add(make('li'), h.add(item,
        one.image ? h.picture(one.image, h.slideName({ number: one.number,
          title: words.title }), run.desk.expected) : null,
        make('span', 'strip-number', String(one.number)),
        make('span', 'strip-title', words.title || ''),
        tag ? make('span', 'tag', tag) : null)));
    });
    // Once it is on the screen, the navigator scrolls itself to the slide chosen; the page
    // itself stays put.
    window.setTimeout(() => inView(node), 0);
    return h.add(node, h.add(make('div', 'bar slide-moves'), earlier, later, now), strip);
  }

  function inView(node, tries = 20) {
    const item = node.querySelector('[aria-current="true"]');
    if (!item) return;
    // A screen changed with a view transition is put in place a few frames later.
    if (!document.body.contains(node)) {
      if (tries > 0) window.setTimeout(() => inView(node, tries - 1), 50);
      return;
    }
    const shown = item.getBoundingClientRect();
    for (const box of [node.querySelector('.desk-nav-list'), node]) {
      const frame = box.getBoundingClientRect();
      if (shown.left < frame.left) box.scrollLeft -= frame.left - shown.left;
      else if (shown.right > frame.right) box.scrollLeft += shown.right - frame.right;
      // A rail taller than what is left of the window keeps the slide within the window.
      const bottom = Math.min(frame.bottom, window.innerHeight || frame.bottom);
      if (shown.top < frame.top) box.scrollTop -= frame.top - shown.top;
      else if (shown.bottom > bottom) box.scrollTop += shown.bottom - bottom;
    }
  }

  // --- the whole-deck note: a second, folded way to change the deck ---------------------------

  function wholePart(run, working, cards) {
    const path = h.view.path;
    const kept = held.deck[path] || (held.deck[path] = { note: '' });
    const id = 'desk-deck-note';
    const sections = h.list(run.desk.sections).filter((part) => !part.lead).length;
    const node = make('details', 'card desk-whole');
    node.dataset.key = 'desk-whole';
    // A note typed and not sent keeps it open.
    if (kept.note) node.open = true;
    const box = noteField(id, 'How should the whole deck change?', kept, '');
    const go = h.capsule('Redraw every section', '', async () => {
      const note = kept.note.trim();
      if (!note) {
        h.refuse(id, NO_DECK_NOTE);
        return;
      }
      const done = await act('desk-deck-note', { path, note, expected: run.desk.expected }, go,
        'Every section is being redrawn with your note.', h.byId(id + '-problem'));
      if (done) kept.note = '';
    }, 'desk-deck-redraw');
    go.disabled = working;
    box.querySelector('textarea').disabled = working;
    const summary = make('summary', '', 'Change the whole deck');
    summary.dataset.key = 'desk-whole-summary';
    return h.add(node, summary,
      make('p', '', 'This redraws every section of the deck: ' + h.count(sections, 'section',
        'sections') + ', ' + h.count(cards.length, 'slide', 'slides') + '. To change one '
        + 'slide, note that slide instead: only its section is redrawn.'),
      box, bar(go), make('p', 'quiet', run.desk.deck_price || ''));
  }

  // --- the slide chosen ----------------------------------------------------------------------
  // Its picture first, then what the brand check and the review found on it, with a fix to
  // apply or skip where one is proposed, then its words and speaker notes, its note, and its
  // caveat and source, folded.

  function slideCard(run, one, part, can) {
    const kind = one.lead && one.kind ? ' · ' + h.capital(h.spoken(one.kind)) : '';
    const words = one.words || {};
    const found = run.desk;
    // A slide of your own deck at Selected changes: its words are those of each part of it.
    const own = Array.isArray(one.objects);
    const node = make('section', 'card deck-desk-slide' + (one.busy ? ' desk-working'
      : ''));
    const editing = can && !h.theirs(run);
    const history = editing && !own ? h.capsule('History', 'quiet', () => openHistory(run, one),
      'desk-history ' + one.number) : null;
    if (history) history.setAttribute('aria-label', 'History of slide ' + one.number);
    const saved = make('p', 'quiet desk-save-state');
    saved.id = 'desk-saved-' + one.number;
    saved.setAttribute('role', 'status');
    // At Brand only and Polish the slide keeps your own deck's words: they are read here.
    const locked = !own && found.words_locked;
    const heading = make('h2', 'card-title', 'Slide ' + one.number + kind
      + (!part.lead && part.number ? ' · Section ' + part.number : '')
      + (one.hidden ? ' · Hidden' : ''));
    heading.id = 'desk-slide-title';
    heading.tabIndex = -1;
    node.setAttribute('aria-labelledby', heading.id);
    h.add(node, heading,
      picturesPart(run, one),
      one.busy && !own ? h.add(make('p', 'desk-working-note'), h.state('current',
        'Redrawing…')) : null,
      one.note ? noteSaid(one.note) : null,
      foundPart(run, one),
      editing && one.unfit ? unfitPart(run, one) : null,
      own ? (editing ? objectBoxes(one) : objectWords(one))
        : editing && !locked ? wordBoxes(one)
          : wordsPart(one.lead ? words : { ...words, caveat: null, source: null }),
      locked ? make('p', 'quiet', found.words_locked) : null,
      own ? make('p', 'quiet', found.notes_locked || '')
        : editing ? notesBox(one)
          : one.notes ? h.add(make('p', 'quiet'), make('strong', '', 'Speaker notes: '),
            one.notes) : null,
      editing ? saved : null);
    if (!one.lead && can) h.add(node, ...noteBox(run, one));
    return h.add(node, own || one.lead ? null : advancedPart(one, editing && !locked),
      history ? bar(history) : null);
  }

  // What the brand check and the review found on the slide, in their words, blockers first,
  // and each fix proposed for it, to apply or skip here as in Finishing. A finding a fix
  // stands for is shown once, as that fix.
  function foundPart(run, one) {
    const { audit, findings, proposals } = foundOn(run, one);
    if (!audit.length && !findings.length && !proposals.length) return null;
    return h.add(make('div', 'desk-found'),
      make('p', 'row-title', 'What was found on this slide'),
      audit.length ? auditPart(audit) : null,
      findings.length ? h.findingItems(findings) : null,
      ...proposals.map(({ key, set, item }) => locatedFix(run, key, set, item)));
  }

  // A fix proposed for the slide: what it is, then Apply, which says what it redraws before
  // anything is sent, or Skip.
  function locatedFix(run, key, set, item) {
    const path = h.view.path;
    const found = run.desk;
    const node = make('div', 'desk-located');
    node.dataset.item = item.id;
    const from = key === 'brand' ? 'Proposed by the brand check' : 'Proposed by the review';
    const tag = key === 'brand' ? KIND_TAGS[item.kind] : item.severity
      ? h.capital(item.severity) : '';
    h.add(node, h.add(make('p', ''), make('strong', '', from), tag ? ' ' : null,
      tag ? make('span', 'tag', tag) : null),
    make('p', '', key === 'brand' ? item.says : item.note),
    item.fix ? make('p', 'quiet', 'Suggested: ' + item.fix) : null);
    const skip = h.capsule('Skip', 'quiet', () => act('desk-skip', { path, set: set.job,
      ids: [item.id] }, skip, 'Skipped. Nothing changed.'), 'desk-slide-skip ' + item.id);
    if ('comment' in item) return h.add(node, bar(skip));
    if (held.confirm[path] === set.job + '\n' + item.id) {
      const go = h.capsule('Apply and redraw slide ' + item.number, '', () => apply(run, set,
        { id: item.id }, go, 'Slide ' + item.number + ' is being redrawn with the note. Every '
        + 'other part of the deck stays exactly as it is.'), 'desk-slide-apply-go ' + item.id);
      go.disabled = Boolean(found.working);
      const back = h.capsule('Cancel', 'quiet', () => {
        delete held.confirm[path];
        h.paintDeck(false);
      }, 'desk-slide-apply-cancel ' + item.id);
      return h.add(node, make('p', '', item.price || 'This redraws its slide’s section.'),
        bar(go, back));
    }
    const fix = h.capsule('Apply', '', () => {
      held.confirm[path] = set.job + '\n' + item.id;
      h.paintDeck(false);
      h.focusKey('desk-slide-apply-go ' + item.id);
    }, 'desk-slide-apply ' + item.id);
    fix.disabled = Boolean(found.working);
    return h.add(node, bar(fix, skip));
  }

  // The slide's picture now and, for an existing deck, the slide as it was in your deck
  // before it, each said in words. The picture of the slide chosen is fetched first.
  function picturesPart(run, one) {
    const words = one.words || {};
    const now = one.image ? h.pictureAt(h.pictureOf(h.view.path, one.image),
      h.slideName({ number: one.number, title: words.title }), run.desk.expected,
      { first: true, again: true })
      : make('p', 'quiet', 'There is no picture of this slide on this computer yet.');
    if (!one.before) return h.add(make('div', 'deck-desk-picture'), now);
    return h.add(make('div', 'pair deck-desk-pair'),
      h.add(make('div', 'deck-desk-picture'), make('p', 'quiet', 'Before'),
        h.picture(one.before, 'Slide ' + one.number + ' as it was in your deck', 'original')),
      h.add(make('div', 'deck-desk-picture'), make('p', 'quiet', 'After'), now));
  }

  // The words of each part of a slide of your own deck: a box for each run of words the part
  // has, named by the part and, where it has more than one, the run. A run of spaces only is
  // not a box.
  function objectBoxes(one) {
    const node = make('div', 'fields deck-desk-words');
    h.list(one.objects).forEach((part, at) => {
      const runs = h.list(part.runs).map(String);
      runs.forEach((text, index) => {
        if (!text.trim()) return;
        const single = runs.length === 1;
        h.add(node, wordBox(one, ['object', part.id, single ? null : index], 'Text box '
          + (at + 1) + (single ? '' : ', part ' + (index + 1)), text.trim(), text.length > 80));
      });
    });
    return node;
  }

  function objectWords(one) {
    return h.add(make('div', 'deck-desk-words'), ...h.list(one.objects).map((part) => make('p',
      '', h.list(part.runs).join(''))));
  }

  // A slide's words, as the outline has them. They are read here, and edited on the Outline
  // tab.
  function wordsPart(words) {
    const points = h.list(words.points).filter((point) => point && (point.label || point.text));
    return h.add(make('div', 'deck-desk-words'),
      words.title ? h.add(make('p', ''), make('strong', '', words.title)) : null,
      words.subtitle ? make('p', '', words.subtitle) : null,
      words.detail ? make('p', '', words.detail) : null,
      points.length ? h.bullets(points.map((point) => (point.label && point.text
        ? point.label + ': ' + point.text : point.label || point.text)), 'outline-points') : null,
      words.caveat ? make('p', 'quiet', words.caveat) : null,
      words.source ? make('p', 'quiet', 'Source: ' + words.source) : null);
  }

  // The slide's caveat and source, folded under its other words: boxes where its words are
  // edited here, read otherwise. It opens by itself where words in it are typed and not saved,
  // or did not fit.
  function advancedPart(one, editable) {
    const words = one.words || {};
    const fields = WORD_FIELDS.slice(3);
    const unfit = one.unfit ? fieldKey(one.unfit.field) : '';
    const shown = fields.filter(([field]) => words[field] || unfit === field);
    if (!shown.length) return null;
    const node = make('details', 'desk-advanced');
    node.dataset.key = 'desk-advanced ' + one.id;
    node.open = shown.some(([field]) => unfit === field
      || held.edits[editKey(h.view.path, one.number, field)]);
    const summary = make('summary', '', 'Caveat and source');
    summary.dataset.key = 'desk-advanced-summary ' + one.id;
    if (!editable) {
      return h.add(node, summary, wordsPart({ caveat: words.caveat, source: words.source }));
    }
    const boxes = make('div', 'fields deck-desk-words');
    for (const [field, label] of shown) h.add(boxes, wordBox(one, field, label, words[field]));
    return h.add(node, summary, boxes);
  }

  // The brand check on this slide: what blocks delivery first, then what it warns of.
  function auditPart(audit) {
    const ordered = audit.slice().sort((one, other) => (one.kind === 'error' ? 0 : 1)
      - (other.kind === 'error' ? 0 : 1));
    const items = make('ul', 'plain');
    for (const one of ordered) {
      h.add(items, h.add(make('li'), one.kind === 'error'
        ? h.state('late', 'The brand check: ' + one.says + ' It blocks delivery.')
        : h.state('none', 'The brand check: ' + one.says + ' A warning: it does not block '
          + 'delivery.')));
    }
    return items;
  }

  function noteSaid(note) {
    if (note.says) return make('p', 'quiet', note.says);
    const said = NOTE_SAYS[note.status];
    if (!said) return null;
    return make('p', 'quiet', note.status === 'set aside' ? said
      : said + '“' + String(note.note || '') + '”' + (note.whole ? ' (for the whole deck)' : ''));
  }

  // The note box of a content slide: Redraw slide N, and under it its price, which names the
  // section it redraws and the slides in it.
  function noteBox(run, one) {
    const path = h.view.path;
    const key = path + '\n' + one.number;
    const kept = held.notes[key] || (held.notes[key] = { note: '' });
    const id = 'desk-note-' + one.number;
    const box = noteField(id, 'How should this slide change?', kept, 'Slide ' + one.number);
    // On your own deck at Selected changes, a note plans the slide's changes again: nothing
    // is redrawn.
    const own = Array.isArray(one.objects);
    const input = box.querySelector('textarea');
    const go = h.capsule((own ? 'Change slide ' : 'Redraw slide ') + one.number, '', async () => {
      const note = kept.note.trim();
      if (!note) {
        h.refuse(id, NO_NOTE);
        input.focus();
        return;
      }
      const done = await act('desk-note', { path, number: one.number, note,
        expected: run.desk.expected }, go, own ? 'The changes to slide ' + one.number + ' are '
        + 'being planned again with your note.' : 'Slide ' + one.number + ' is being redrawn. '
        + 'Every other part of the deck stays exactly as it is.', h.byId(id + '-problem'));
      if (!done) return;
      kept.note = '';
      input.value = '';
    }, (own ? 'desk-change ' : 'desk-redraw ') + one.number);
    input.disabled = Boolean(one.busy);
    go.disabled = Boolean(one.busy);
    return [make('p', 'row-title', own ? 'Change this slide' : 'Change how it is drawn'), box,
      bar(go), one.price ? make('p', 'quiet', one.price) : null];
  }

  // --- the desk's aside: Sources and Research --------------------------------------------------
  // A source is a file or pasted text, kept with the deck and read by the words jobs, the
  // speaker notes and the outline when it is written again; adding one runs nothing. The
  // research's findings may be left out, and the research run again, each at its price,
  // said before it is asked.

  function asideKey(run) {
    const found = run.desk;
    return [found.sources, found.research, found.research_items, found.research_price,
      found.leave_out_price, Boolean(found.working), found.expected];
  }

  function asidePart(run) {
    const node = make('aside', 'desk-aside');
    node.setAttribute('aria-label', 'Sources and research');
    return h.add(node, sourcesCard(run), run.desk.research_price ? researchCard(run) : null);
  }

  function sourcesCard(run) {
    const path = h.view.path;
    // A file is kept in the Document Library too unless the person chooses this deck only.
    const kept = held.sources[path] || (held.sources[path] = { text: '', title: '', library: true });
    if (typeof kept.library !== 'boolean') kept.library = true;
    const listed = h.list(run.desk.sources);
    const problem = make('p', 'problem');
    problem.id = 'desk-source-problem';
    problem.hidden = true;
    // A file the library did not keep stays said, however often the card is drawn again.
    if (kept.notKept) h.say(problem, kept.notKept);
    const go = h.capsule('Add the pasted text', '', async () => {
      if (!kept.text.trim()) {
        h.refuse('desk-source-text', NO_TEXT);
        return;
      }
      const done = await act('desk-source', { path, text: kept.text,
        title: kept.title.trim() || 'Pasted text' }, go, 'The source is added. Research runs '
        + 'again only when you ask.', problem);
      if (done) Object.assign(kept, { text: '', title: '' });
    }, 'desk-source-add');
    const node = h.card('Sources');
    return h.add(node, make('p', 'quiet', SOURCES_SAY),
      listed.length ? h.bullets(listed.map((one) => (one.title || one.name)
        + (one.library ? ' · from the library, revision ' + one.library.revision
          + (one.update ? ' (revision ' + one.library_head + ' is available)' : '') : '')
        + (one.readable ? '' : ': ' + (one.problem || 'it has no text that can be read.'))))
        : make('p', 'quiet', 'No sources yet.'),
      ...libraryParts(run, path, listed, problem),
      h.add(make('p'), make('strong', '', 'Add a source')),
      // Chosen before the file: a file is added as soon as it is picked.
      h.choice('Keep the file', KEEP_CHOICES, kept.library ? 0 : 1,
        (index) => { kept.library = index === 0; }, 'desk-source-keep', KEEP_SAYS),
      h.field('desk-source-file', 'A file', {}, 'file', { accept: SOURCE_TYPES,
        hint: 'Text, Markdown, a web page, a Word document or a PDF, up to 8 MB.',
        picked: (input) => addFile(input, problem, kept) }),
      h.field('desk-source-text', 'Or paste its text', kept, 'text', { long: true, rows: 4,
        limit: 1000000 }),
      h.field('desk-source-title', 'Its title', kept, 'title', {}),
      bar(go), problem);
  }

  // The shared Document Library (library.js): Add from library pins chosen revisions as
  // sources, Use revision N takes a newer one only when pressed, and a delivered deck says
  // whether its slide Markdown was kept there. Nothing here starts research or a job.
  function libraryParts(run, path, listed, problem) {
    const parts = [];
    for (const one of listed.filter((entry) => entry.update)) {
      parts.push(bar(h.capsule('Use revision ' + one.library_head + ' of ' + (one.title || one.name), 'quiet',
        () => act('desk-library-update', { path, document: one.library.id }, null,
          'The newer revision is a source now. Research runs again only when you ask.', problem),
        'desk-library-update-' + one.library.id)));
    }
    const pick = h.capsule('Add from library', 'quiet', () => {
      if (!window.StudioLibrary) { h.say(problem, 'The library could not be loaded. Reload the page.'); return; }
      window.StudioLibrary.pick({
        studio: 'presentation', max: 40,
        post: (route, body) => h.send(route, body),
        // The card is drawn again with the new sources: focus its Add from library.
        refocus: () => document.querySelector('[data-key="desk-library-add"]'),
        use: async (picks) => {
          const found = await h.send('desk-library', { path, picks });
          if (h.view.screen === 'deck' && h.view.path === path) { h.view.run = found; h.paintDeck(false); }
          h.toast(picks.length === 1 ? 'The document is a source now.' : picks.length + ' documents are sources now.');
          h.refresh();
        },
      });
    }, 'desk-library-add');
    parts.push(bar(pick));
    const kept = run.desk.library;
    // "PDF saved" only when the library holds the PDF Harness Slides rendered of this deck.
    if (kept && kept.state === 'kept' && kept.pdf === 'saved') {
      parts.push(make('p', 'quiet', 'Kept in the Document Library as a PDF and slide Markdown, '
        + 'revision ' + kept.revision + '. PDF saved.'));
    } else if (kept && kept.state === 'kept') {
      parts.push(make('p', 'quiet', 'Kept in the Document Library as slide Markdown, revision '
        + kept.revision + '. PDF needs export: ' + (kept.pdf_note || '')));
    } else if (kept && kept.state === 'failed') {
      parts.push(make('p', 'problem', 'Not kept in the Document Library: ' + kept.problem));
      parts.push(bar(h.capsule('Keep in library again', 'quiet',
        () => act('desk-library-keep', { path }, null, 'Kept in the Document Library.', problem),
        'desk-library-keep')));
    }
    return parts;
  }

  // `form` is the card's held state: whether to keep the file in the library, and what the
  // library said when it did not, which every drawing of the card shows until the next file.
  async function addFile(input, problem, form) {
    const file = Array.from(input.files || [])[0];
    if (!file) return;
    form.notKept = '';
    if (file.size > 8000000) {
      h.say(problem, file.name + ' is larger than 8 MB. Add a shorter version of it.');
      return;
    }
    let content;
    try {
      content = await h.base64Of(file);
    } catch (failure) {
      h.say(problem, file.name + ' could not be read. ' + failure.message);
      return;
    }
    const found = await act('desk-source', { path: h.view.path, name: file.name, content,
      library: Boolean(form.library) }, null, null, problem);
    if (!found) return;
    const kept = found.library_upload;
    if (kept && kept.state === 'failed') {
      // Held, so the card drawn again by act's repaint or a later refresh still says it.
      form.notKept = kept.problem;
      h.say(h.byId('desk-source-problem') || problem, kept.problem);
      return;
    }
    h.toast(file.name + (kept && kept.state === 'kept' ? ' is added and kept in the Document '
      + 'Library.' : ' is added to this deck only.') + ' Research runs again only when you ask.');
  }

  function researchCard(run) {
    const found = run.desk;
    const path = h.view.path;
    const working = Boolean(found.working);
    const items = h.list(found.research_items);
    const before = items.filter((item) => item.left_out).map((item) => item.id);
    const ticked = held.leave[path] || (held.leave[path] = new Set(before));
    const same = () => before.length === ticked.size && before.every((id) => ticked.has(id));
    const node = h.card('Research');
    const account = found.research;
    if (account) {
      h.add(node, make('p', 'quiet', account.read || ''),
        account.check ? make('p', 'quiet', account.check.said || '') : null);
    }
    const list = make('ul', 'plain');
    for (const item of items) {
      const tick = StudioLists.tick({ id: 'desk-leave-' + item.id, label: 'Leave out '
        + (item.title || item.id), on: ticked.has(item.id), flip: (on) => {
        if (on) ticked.add(item.id);
        else ticked.delete(item.id);
        leave.disabled = working || same();
      } });
      h.add(list, h.add(make('li'), tick, item.headline ? make('p', '', item.headline) : null,
        item.unknown ? make('p', 'quiet', 'Not known: ' + item.unknown) : null));
    }
    const leave = h.capsule('Leave out the ticked findings', '', () => act('desk-leave-out',
      { path, ids: [...ticked] }, leave, 'The outline and the look samples are being made '
      + 'again without them.'), 'desk-leave-out');
    leave.disabled = working || same();
    const again = h.capsule('Research again', '', () => act('desk-research-again',
      { path, expected: found.expected }, again, 'The research runs again with your sources '
      + 'as they are now.'), 'desk-research-again');
    again.disabled = working || !found.expected;
    const gaps = account ? h.list(account.gaps) : [];
    return h.add(node, items.length ? list : make('p', 'quiet', 'No findings yet.'),
      gaps.length ? h.add(make('div'), h.add(make('p'), make('strong', '',
        'What it could not find')), h.bullets(gaps)) : null,
      bar(leave), make('p', 'quiet', found.leave_out_price || ''),
      bar(again), make('p', 'quiet', found.research_price || ''));
  }

  // --- Finishing: the shared kit's panel, with the deck's four tools -----------------------------
  // Each tool proposes, and nothing changes until Apply. A finding of the brand check or of
  // the review is applied as a note on its slide, and Apply says what that redraws before it
  // is sent; speaker notes are applied as typed notes are, with no redraw.

  function finishState(path) {
    if (held.finish[path]) return held.finish[path];
    const state = { view: null, finish: null };
    // The page's own parts place the panel: where the kit would put a new panel in its place
    // (All tools), the page draws the desk again, and the panel with it.
    const placed = { replaceWith: () => h.paintDeck(false) };
    Object.defineProperty(state, 'panel', { get: () => placed, set: () => {} });
    held.finish[path] = state;
    return state;
  }

  function finishing() {
    return Boolean((held.finish[h.view.path] || {}).finish);
  }

  function toggleFinishing() {
    const state = finishState(h.view.path);
    if (state.finish) kit.finishClose(state);
    else kit.finishOpen(state);
  }

  function openTool(state, key) {
    state.finish.tool = key;
    h.paintDeck(false);
    const run = h.view.run;
    // The brand check's proposals are made from the last render's check as it is opened.
    if (key === 'brand' && run && run.desk && !run.desk.brand_current && !h.theirs(run)) {
      act('desk-finish', { path: h.view.path, tool: 'brand' }, null, '');
    }
  }

  function finishKey(run) {
    const found = run.desk;
    const path = h.view.path;
    const state = finishState(path);
    return [state.finish && state.finish.tool, found.finishing, found.brand_check,
      found.brand_current, found.finish_prices, found.rehearse, found.reviewing,
      found.reviewed, found.working, found.seen, found.expected, held.confirm[path] || '',
      Object.keys(held.editing).filter((key) => key.startsWith(path + '\n'))];
  }

  function finishPart(run) {
    const state = finishState(h.view.path);
    state.view = { finishing: run.desk.finishing || {}, working: null };
    return kit.panel(state);
  }

  function finishView(key) {
    const run = h.view.run;
    const found = run.desk;
    const path = h.view.path;
    const set = (found.finishing || {})[key];
    const working = Boolean(found.working);
    const parts = [];
    if (key === 'brand') {
      const again = h.capsule('Check again', '', () => act('desk-finish', { path, tool: 'brand',
        again: true }, again, 'Checked again.'), 'desk-check-again');
      again.disabled = working;
      parts.push(make('p', 'quiet', BRAND_SAYS), bar(again));
      if (set && found.brand_current) parts.push(...proposalCards(run, key, set));
      else parts.push(brandLines(found.brand_check));
    } else if (key === 'review') {
      const go = h.capsule('Review the deck', '', () => act('desk-finish', { path,
        tool: 'review', expected: found.expected }, go, 'The deck is being reviewed. What it '
        + 'finds comes back here, slide by slide.'), 'desk-review');
      go.disabled = working || found.reviewing || found.reviewed || !found.expected;
      parts.push(bar(go), make('p', 'quiet', (found.finish_prices || {}).review || ''));
      if (found.reviewing) {
        parts.push(h.add(make('p', 'desk-working-note'), h.state('current',
          'Reviewing the deck…')));
      } else if (found.reviewed) {
        parts.push(make('p', 'quiet', 'The deck was reviewed as it is drawn now.'));
      }
      if (set) parts.push(...proposalCards(run, key, set));
    } else if (key === 'notes') {
      const go = h.capsule('Propose speaker notes', '', () => act('desk-finish', { path,
        tool: 'notes' }, go, 'Speaker notes are being proposed for every slide.'), 'desk-notes');
      go.disabled = working || Boolean(found.notes_locked);
      parts.push(bar(go), make('p', 'quiet', found.notes_locked
        || (found.finish_prices || {}).notes || ''));
      if (set) parts.push(...proposalCards(run, key, set));
    } else {
      parts.push(...rehearsed(found.rehearse || {}));
    }
    return parts;
  }

  function brandLines(listed) {
    const lines = h.list(listed);
    if (!lines.length) return make('p', '', 'The brand check found nothing on any slide.');
    return h.bullets(lines.map((one) => (typeof one.number === 'number' ? 'Slide '
      + one.number + ': ' : '') + one.says + (one.kind === 'blocker' ? ' It blocks delivery.'
      : '')));
  }

  // 'about 3 minutes', or 'under a minute' for a time that rounds to no minutes, as the
  // runner says it (finishing._minutes).
  function minutesOf(value) {
    const whole = Math.round(value || 0);
    if (whole < 1) return 'under a minute';
    return 'about ' + whole + (whole === 1 ? ' minute' : ' minutes');
  }

  // How long the speaker notes take to say, counted on the runner, with the slides that run
  // long named.
  function rehearsed(said) {
    const long = h.list(said.long);
    const minutes = new Map(h.list(said.slides).map((one) => [one.number, one.minutes]));
    return [make('p', '', said.says || ''),
      long.length ? h.add(make('div'), make('h3', 'sheet-part', 'The slides that run long'),
        h.bullets(long.map((number) => 'Slide ' + number + ': '
          + minutesOf(minutes.get(number) || 0)))) : null,
      make('p', 'quiet', 'Counted here, at 150 words a minute. Nothing is sent to an '
        + 'assistant.')].filter(Boolean);
  }

  function proposalCards(run, key, set) {
    const items = h.list(set.items);
    const open = items.filter((item) => item.state === 'open').length;
    const out = [make('p', 'quiet', h.count(items.length, 'proposal', 'proposals') + ' · '
      + open + ' to review.')];
    if (!items.length) {
      out.push(make('p', '', key === 'notes' ? 'Every slide’s notes are good as they are.'
        : key === 'review' ? 'The review found nothing to change.'
          : 'The brand check found nothing on any slide.'));
    }
    for (const item of items) out.push(proposalCard(run, key, set, item));
    return out;
  }

  function proposalCard(run, key, set, item) {
    const path = h.view.path;
    const found = run.desk;
    const can = !h.theirs(run);
    const node = make('section', 'card desk-proposal');
    node.dataset.item = item.id;
    const slide = typeof item.number === 'number' ? 'Slide ' + item.number : 'The whole deck';
    const tag = key === 'brand' ? KIND_TAGS[item.kind] : key === 'review' && item.severity
      ? h.capital(item.severity) : '';
    h.add(node, h.add(make('div', 'desk-part-head'), make('h4', 'row-title', slide),
      tag ? make('span', 'tag', tag) : null));
    const editKey = path + '\n' + set.job + '\n' + item.id;
    const editing = held.editing[editKey];
    if (key === 'notes') {
      h.add(node, kit.sides(item.before || '', editing !== undefined ? editing : item.after));
    } else {
      h.add(node, make('p', '', key === 'brand' ? item.says : item.note),
        item.fix ? make('p', 'quiet', 'Suggested: ' + item.fix) : null,
        'after' in item ? make('p', 'quiet', 'Its note: “' + item.after + '”') : null);
    }
    if (item.state !== 'open') {
      return h.add(node, make('p', 'quiet', item.state === 'applied' ? (key === 'notes'
        ? 'Applied. The earlier notes are in History.'
        : 'Applied: its slide is redrawn with this note.') : 'Skipped.'));
    }
    const skip = h.capsule('Skip', 'quiet', () => act('desk-skip', { path, set: set.job,
      ids: [item.id] }, skip, 'Skipped. Nothing changed.'), 'desk-skip ' + item.id);
    skip.disabled = !can;
    if ('comment' in item) return h.add(node, bar(skip));
    if (!item.present) {
      return h.add(node, make('p', 'quiet', key === 'notes' ? 'The notes of this slide changed '
        + 'since these were proposed, so they no longer fit.' : 'This slide is no longer in the '
        + 'deck as it is drawn, so this no longer fits.'), bar(skip));
    }
    const confirming = held.confirm[path] === set.job + '\n' + item.id;
    if (confirming) {
      // What applying it redraws, said before it is sent.
      const go = h.capsule('Apply and redraw slide ' + item.number, '', () => apply(run, set,
        { id: item.id }, go, 'Slide ' + item.number + ' is being redrawn with the note. Every '
        + 'other part of the deck stays exactly as it is.'), 'desk-apply-go ' + item.id);
      go.disabled = !can || Boolean(found.working);
      const back = h.capsule('Cancel', 'quiet', () => {
        delete held.confirm[path];
        h.paintDeck(false);
      }, 'desk-apply-cancel ' + item.id);
      return h.add(node, make('p', '', item.price || 'This redraws its slide’s section.'),
        bar(go, back));
    }
    if (editing !== undefined) {
      const id = 'desk-edit-' + item.id;
      const kept = { text: editing };
      const box = h.field(id, 'Your notes for slide ' + item.number, kept, 'text',
        { long: true, rows: 4, limit: 4000, typed: () => { held.editing[editKey] = kept.text; } });
      const use = h.capsule('Apply these notes', '', () => apply(run, set,
        { id: item.id, after: held.editing[editKey] }, use, 'The notes of slide ' + item.number
        + ' are saved. Nothing is redrawn.'), 'desk-apply-own ' + item.id);
      use.disabled = !can;
      const back = h.capsule('Cancel', 'quiet', () => {
        delete held.editing[editKey];
        h.paintDeck(false);
      }, 'desk-edit-cancel ' + item.id);
      return h.add(node, box, bar(use, back));
    }
    const applyNow = h.capsule('Apply', '', () => {
      if (key === 'notes') {
        apply(run, set, { id: item.id }, applyNow, 'The notes of slide ' + item.number
          + ' are saved. Nothing is redrawn.');
        return;
      }
      held.confirm[path] = set.job + '\n' + item.id;
      h.paintDeck(false);
    }, 'desk-apply ' + item.id);
    applyNow.disabled = !can || (key !== 'notes' && Boolean(found.working));
    const edit = key === 'notes' ? h.capsule('Edit', 'quiet', () => {
      held.editing[editKey] = item.after;
      h.paintDeck(false);
    }, 'desk-edit ' + item.id) : null;
    if (edit) edit.disabled = !can;
    return h.add(node, bar(applyNow, edit, skip));
  }

  async function apply(run, set, entry, pressed, done) {
    const path = h.view.path;
    const found = await act('desk-apply', { path, set: set.job, ids: [entry],
      seen: run.desk.seen }, pressed, done);
    if (!found) return;
    delete held.confirm[path];
    delete held.editing[path + '\n' + set.job + '\n' + entry.id];
    h.paintDeck(false);
  }

  // --- a slide's words on its card --------------------------------------------------------
  // Each word is a box that saves one second after the last key, against the desk's revision
  // the page last read (`seen`) and with this page's editing session, so the saves of one
  // sitting keep one version of the slide. A save from a form older than the slide is refused
  // for that slide only, and the words typed stay in the box.

  function fieldKey(field) {
    return typeof field === 'string' ? field : field.join('.');
  }

  function editKey(path, number, field) {
    return [path, number, fieldKey(field)].join('\n');
  }

  // The text a box shows: what was typed and not saved yet, else the words that did not fit
  // (kept until they are redrawn or let go), else the slide's own.
  function shownText(one, field, own) {
    const typed = held.edits[editKey(h.view.path, one.number, field)];
    if (typed) return typed.text;
    if (one.unfit && fieldKey(one.unfit.field) === fieldKey(field)) return one.unfit.text;
    return own || '';
  }

  // One box of a slide's words. `field` is what the runner names it by: 'title', or
  // ['points', 1, 'text'] for the second point's words.
  function wordBox(one, field, label, own, long) {
    const id = 'desk-' + fieldKey(field).replace(/\./g, '-') + '-' + one.number;
    const kept = { text: shownText(one, field, own) };
    const node = h.field(id, label, kept, 'text', { long: Boolean(long), rows: 2, limit: 2000,
      typed: () => typed(one.number, field, kept.text) });
    node.querySelector('label').append(make('span', 'offscreen', ' of slide ' + one.number));
    const input = node.querySelector(long ? 'textarea' : 'input');
    input.readOnly = Boolean(one.busy);
    if (field !== 'notes') {
      for (const kind of ['select', 'mouseup', 'keyup']) {
        input.addEventListener(kind, () => selected(one, field, input));
      }
    }
    return node;
  }

  function wordBoxes(one) {
    const words = one.words || {};
    const node = make('div', 'fields deck-desk-words');
    // A box for each word the slide has: a box added where the slide has none would be
    // something the drawing has no place for.
    const boxes = (fields) => {
      for (const [field, label] of fields) {
        const own = words[field];
        if (!own && !(one.unfit && fieldKey(one.unfit.field) === field)) continue;
        h.add(node, wordBox(one, field, label, own, field === 'detail'));
      }
    };
    boxes(WORD_FIELDS.slice(0, 3));
    // A lead slide has no points, caveat or source: no composer draws it. The caveat and the
    // source are folded under the slide's other words (`advancedPart`).
    if (one.lead) return node;
    addPoints(node, one, words);
    return node;
  }

  function addPoints(node, one, words) {
    h.list(words.points).forEach((point, index) => {
      if (!point) return;
      if (point.label) {
        h.add(node, wordBox(one, ['points', index, 'label'], 'Point ' + (index + 1) + ' label',
          point.label));
      }
      if (point.text) {
        h.add(node, wordBox(one, ['points', index, 'text'], 'Point ' + (index + 1) + ' text',
          point.text, true));
      }
    });
  }

  // The speaker notes: their own box, saved as the words are, with no redraw.
  function notesBox(one) {
    const kept = { text: shownText(one, 'notes', one.notes) };
    const id = 'desk-notes-' + one.number;
    const node = h.field(id, 'Speaker notes', kept, 'text', { long: true, rows: 3,
      limit: 4000, hint: 'What you say over this slide. Saving them redraws nothing.',
      typed: () => typed(one.number, 'notes', kept.text) });
    node.querySelector('label').append(make('span', 'offscreen', ' for slide ' + one.number));
    node.querySelector('textarea').readOnly = Boolean(one.busy);
    return node;
  }

  function saySaved(number, text, again) {
    const node = h.byId('desk-saved-' + number);
    if (!node) return;
    node.replaceChildren(text);
    if (again) h.add(node, ' ', again);
  }

  function typed(number, field, text) {
    const path = h.view.path;
    const key = editKey(path, number, field);
    const first = !unsavedOn(path, { number });
    const edit = held.edits[key] || (held.edits[key] = { path, number, field });
    edit.text = text;
    if (edit.timer) window.clearTimeout(edit.timer);
    // Named, so a test can say when the second has passed.
    edit.timer = window.setTimeout(function flush() {
      edit.timer = 0;
      return save(key);
    }, SAVE_WAIT);
    saySaved(number, 'Saving…');
    // The first key typed on a slide marks it in the navigator and the summary. Only those
    // are drawn again: the box being typed in, its focus and its caret stay as they are.
    if (first && h.view.screen === 'deck' && h.view.run && h.view.run.desk) h.paintDeck(false);
  }

  // One save at a time, each against the latest view; a newer edit of the same box is saved
  // after it.
  async function save(key) {
    while (saving) await saving;
    const edit = held.edits[key];
    if (!edit || edit.sending) return;
    const run = h.view.run;
    if (!run || !run.desk || h.view.path !== edit.path) return;
    const text = edit.text;
    edit.sending = true;
    const body = edit.field === 'notes'
      ? { path: edit.path, number: edit.number, text, seen: run.desk.seen, session: SESSION }
      : { path: edit.path, number: edit.number, field: edit.field, text, seen: run.desk.seen,
        session: SESSION };
    saving = (async () => {
      try {
        const found = await h.send(edit.field === 'notes' ? 'desk-notes' : 'desk-words', body);
        if (held.edits[key] === edit && edit.text === text) delete held.edits[key];
        if (h.view.screen === 'deck' && h.view.path === edit.path) {
          h.view.run = found;
          h.paintDeck(false);
        }
        saySaved(edit.number, 'Saved.');
      } catch (failure) {
        // The words typed stay in the box, and are sent again only when typed again.
        const again = /changed since/.test(failure.message) ? h.capsule('Reload', 'quiet', () => {
          delete held.edits[key];
          h.refresh();
        }, 'desk-reload ' + edit.number) : null;
        saySaved(edit.number, failure.message + ' Your words are kept here.', again);
        // The navigator and the summary say the slide's words are not saved yet.
        if (h.view.screen === 'deck' && h.view.path === edit.path) h.paintDeck(false);
      } finally {
        edit.sending = false;
      }
    })();
    try {
      await saving;
    } finally {
      saving = null;
    }
    const later = held.edits[key];
    if (later && later.text !== text && !later.timer) await save(key);
  }

  // Every edit typed and not saved yet, saved now: before History or Deliver reads the deck.
  async function flushAll() {
    for (const key of Object.keys(held.edits)) {
      const edit = held.edits[key];
      if (edit.path !== h.view.path) continue;
      if (edit.timer) window.clearTimeout(edit.timer);
      edit.timer = 0;
      await save(key);
    }
  }

  // --- the selection bar ------------------------------------------------------------------
  // Words selected in a box offer piece 3's actions on them: Rephrase, Shorten, Expand, Fix
  // and Ask…. One is a small words job on that passage, saved as typed words are.

  function selectionBar() {
    const node = make('div', 'desk-selection glass');
    node.id = 'desk-selection';
    node.setAttribute('role', 'toolbar');
    node.setAttribute('aria-label', 'Change the selected words');
    node.hidden = true;
    return node;
  }

  function selected(one, field, input) {
    const node = h.byId('desk-selection');
    if (!node) return;
    const value = input.value;
    let start = input.selectionStart;
    let end = input.selectionEnd;
    if (typeof start !== 'number' || typeof end !== 'number') start = end = 0;
    while (start < end && /\s/.test(value[start])) start += 1;
    while (end > start && /\s/.test(value[end - 1])) end -= 1;
    // The words are kept without the spaces they start with, so the place is counted there.
    const lead = value.length - value.replace(/^\s+/, '').length;
    // Only the saved words can be changed by a words job: not words typed and not saved yet,
    // nor words kept because they did not fit.
    const unsaved = Boolean(held.edits[editKey(h.view.path, one.number, field)])
      || Boolean(one.unfit && fieldKey(one.unfit.field) === fieldKey(field));
    if (start >= end || unsaved || one.busy || (h.view.run.desk && h.view.run.desk.working)) {
      if (!(held.selection && held.selection.asking)) {
        held.selection = null;
        node.hidden = true;
      }
      return;
    }
    held.selection = { number: one.number, field, start: start - lead, end: end - lead,
      passage: value.slice(start, end),
      asking: false };
    barContent();
  }

  function barContent() {
    const node = h.byId('desk-selection');
    const chosen = held.selection;
    if (!node || !chosen) return;
    const go = (action, instruction, pressed) => {
      const run = h.view.run;
      act('desk-selection', { path: h.view.path, number: chosen.number, field: chosen.field,
        start: chosen.start, end: chosen.end, action,
        ...(action === 'ask' ? { instruction } : {}), seen: run.desk.seen,
        passage: chosen.passage }, pressed,
      'The selected words are being changed.').then((found) => {
        if (!found) return;
        held.selection = null;
        const bar = h.byId('desk-selection');
        if (bar) bar.hidden = true;
      });
    };
    if (chosen.asking) {
      const kept = { instruction: '' };
      const box = h.field('desk-ask', 'What should change in the selected words?', kept,
        'instruction', { limit: 2000 });
      const send = h.capsule('Go', '', () => {
        const instruction = kept.instruction.trim();
        if (!instruction) {
          h.refuse('desk-ask', 'Say what should change in the words first.');
          return;
        }
        go('ask', instruction, send);
      }, 'desk-ask-go');
      const cancel = h.capsule('Cancel', 'quiet', () => {
        held.selection = null;
        node.hidden = true;
      }, 'desk-ask-cancel');
      node.replaceChildren(box, send, cancel);
      node.hidden = false;
      return;
    }
    const actions = (typeof Drafting === 'undefined' ? [] : Drafting.SELECTION)
      .map(([action, label]) => {
        const pressed = h.capsule(label, '', () => go(action, '', pressed), 'desk-' + action);
        return pressed;
      });
    node.replaceChildren(...actions, h.capsule('Ask…', '', () => {
      chosen.asking = true;
      barContent();
      h.focusKey('desk-ask');
    }, 'desk-ask'));
    node.hidden = false;
  }

  // --- words that do not fit ----------------------------------------------------------------

  // Words that do not fit the slide as it is drawn: nothing was saved. They are kept here,
  // with what the slides tool said, until they are redrawn, at the slide's price, or let go.
  function unfitPart(run, one) {
    const unfit = one.unfit;
    const path = h.view.path;
    const own = Array.isArray(one.objects);
    const redraw =h.capsule('Redraw with these words', '', () => act('desk-redraw-words',
      { path, number: one.number, field: unfit.field, text: unfit.text,
        expected: run.desk.expected }, redraw, 'Slide ' + one.number + ' is being redrawn with '
        + 'your words.'), 'desk-redraw-words ' + one.number);
    const discard = h.capsule('Discard', 'quiet', () => act('desk-discard',
      { path, number: one.number }, discard, 'Your words are let go. The slide is as it was.'),
    'desk-discard ' + one.number);
    redraw.disabled = Boolean(run.desk.working);
    // A restore that did not fit keeps every word of the version it brings back.
    const restoring = unfit.field === 'restore';
    return h.callout('late', make('p', '', unfit.says || ''),
      restoring ? h.add(make('div', ''), make('p', '', 'The words of the version you restored:'),
        ...wordsText(unfit.words).split('\n').filter(Boolean).map((line) => make('p', 'quiet',
          line)))
        : h.add(make('p', ''), make('strong', '', 'Your words: '), '“' + String(unfit.text || '')
          + '”'),
      h.list(unfit.lines).length ? h.bullets(h.list(unfit.lines).map(String)) : null,
      // Your own deck's words are not redrawn: a change its copy could not take is let go.
      own ? bar(discard) : bar(redraw, discard),
      one.price && !own ? make('p', 'quiet', one.price) : null);
  }

  // --- History ------------------------------------------------------------------------------
  // A slide's earlier words, newest first, each compared with its words now and, where this
  // computer kept it, its picture then beside its picture now. Restore brings one back.

  function wordsText(words) {
    const found = words || {};
    return [found.title, found.subtitle, found.detail,
      ...h.list(found.points).filter(Boolean).map((point) => [point.label, point.text]
        .filter(Boolean).join(': ')),
      found.caveat, found.source, found.notes].filter(Boolean).join('\n');
  }

  async function openHistory(run, one) {
    await flushAll();
    const path = h.view.path;
    held.history = { path, number: one.number, slide: one.id, versions: null, problem: '' };
    h.openSheet('desk-history', 'desk-history ' + one.number)();
    let found;
    try {
      found = await h.ask('desk-versions', { path, slide: one.id });
    } catch (failure) {
      if (held.history && held.history.slide === one.id) held.history.problem = failure.message;
      found = null;
    }
    if (!held.history || held.history.slide !== one.id || h.view.sheet !== 'desk-history') return;
    held.history.versions = found ? h.list(found.versions) : [];
    h.drawSheet();
  }

  function historySheet() {
    const shown = held.history || {};
    const run = h.view.run;
    const one = h.list(run.desk && run.desk.sections).flatMap((part) => h.list(part.slides))
      .find((card) => card.id === shown.slide) || {};
    const close = h.capsule('Close', 'quiet', h.closeSheet, 'cancel');
    const head = h.add(make('div', 'sheet-heading'), h.sheetTitle('History of slide '
      + (one.number || shown.number)), close);
    if (shown.problem) return [head, make('p', 'problem', shown.problem)];
    if (!shown.versions) return [head, make('p', 'quiet', 'Reading what was kept…')];
    if (!shown.versions.length) return [head, make('p', '', 'Nothing kept yet. A version is kept '
      + 'each time the slide’s words change.')];
    const now = wordsText({ ...(one.words || {}), notes: one.notes });
    const problem = h.problemLine();
    const list = make('div', 'desk-versions');
    shown.versions.forEach((version, index) => {
      const when = typeof Drafting === 'undefined' ? '' : Drafting.age(version.at);
      const restore = h.capsule('Restore', '', () => act('desk-restore', { path: shown.path,
        slide: shown.slide, index, seen: run.desk.seen, stamp: version.stamp }, restore,
      'Restored. The words it '
        + 'replaced are in History.', problem).then((found) => {
        if (!found) return;
        h.view.sheet = '';
        h.drawSheet();
        h.paintDeck(false);
      }), 'desk-restore ' + index);
      restore.setAttribute('aria-label', 'Restore the version kept ' + (when || 'earlier'));
      restore.disabled = Boolean(run.desk.working);
      const pictures = version.picture ? h.add(make('div', 'pair'),
        h.add(make('div', ''), make('p', 'quiet', 'Then'), h.pictureAt(h.pictureOf(shown.path,
          version.picture), 'Slide ' + one.number + ' as it was', version.stamp, { first: true })),
        one.image ? h.add(make('div', ''), make('p', 'quiet', 'Now'), h.pictureAt(h.pictureOf(
          shown.path, one.image), 'Slide ' + one.number + ' now', run.desk.expected,
        { first: true })) : null) : null;
      h.add(list, h.add(make('section', 'deck-desk-version'),
        h.add(make('div', 'desk-version'), h.add(make('div', 'row-text'),
          make('p', 'row-title', VERSION_SOURCES[version.source] || 'Earlier words'),
          when ? make('p', 'quiet', when) : null), bar(restore)),
        make('p', 'quiet', 'Struck words are in this version only; marked words were added '
          + 'since.'),
        kit ? kit.compare(wordsText(version.words), now) : null, pictures));
    });
    return [head, problem, list];
  }

  // --- the Outline tab ----------------------------------------------------------------------

  function outlineParts(run, can, working) {
    const outline = run.desk.outline;
    if (!outline) return [];
    return [
      ['outline', [outline.expected, outline.slides, outline.editable, can, working],
        () => outlinePart(run, can && outline.editable, working)],
      outline.reading ? ['reading', [outline.reading, can, working],
        () => readingPart(run, can, working)] : null,
      outline.look ? ['look', [outline.look, can, working], () => lookPart(run, can, working)]
        : null,
    ];
  }

  // What is being edited on the Outline tab, for the outline it was read from.
  function outlineEdit(outline) {
    const path = h.view.path;
    let edit = held.outlines[path];
    if (!edit || edit.base !== outline.expected) {
      edit = { base: outline.expected, work: JSON.parse(JSON.stringify(h.list(outline.slides))),
        priced: '', says: '', asking: '' };
      held.outlines[path] = edit;
    }
    return edit;
  }

  function outlinePart(run, editable, working) {
    const outline = run.desk.outline;
    const path = h.view.path;
    const edit = outlineEdit(outline);
    const node = h.card('The outline');
    const rows = make('ol', 'plain deck-desk-outline');
    rows.id = 'desk-outline';
    const said = make('p', 'quiet');
    said.setAttribute('role', 'status');
    const save = h.capsule('Save', '', () => saveOutline(), 'desk-outline-save');
    const back = h.capsule('Put it back as it was', 'quiet', () => {
      edit.work = JSON.parse(JSON.stringify(h.list(outline.slides)));
      edit.priced = '';
      edit.says = '';
      edit.asking = '';
      paint();
      h.focusKey('desk-outline-save');
    }, 'desk-outline-back');
    const now = () => JSON.stringify(edit.work);
    const edited = () => now() !== JSON.stringify(h.list(outline.slides));
    const tell = () => {
      const changed = edited();
      said.textContent = working ? OUTLINE_BUSY
        : !changed ? 'Saving redraws only the sections whose slides change.'
          : edit.priced === now() ? edit.says : 'Its price is worked out when you leave the box.';
      save.disabled = working || !changed || edit.priced !== now();
      back.hidden = !changed;
    };
    // What saving would redraw is asked of the server before Save sends anything.
    const price = async () => {
      if (working || !edited()) {
        tell();
        return;
      }
      const asked = now();
      edit.asking = asked;
      said.textContent = 'Working out what saving redraws…';
      save.disabled = true;
      try {
        const found = await h.send('desk-outline-price', { path, slides: JSON.parse(asked) });
        if (edit.asking !== asked) return;
        edit.priced = asked;
        edit.says = found.says;
      } catch (failure) {
        if (edit.asking !== asked) return;
        edit.priced = '';
        said.textContent = failure.message;
        return;
      }
      tell();
    };
    const saveOutline = async () => {
      if (working) return;
      if (edit.priced !== now()) {
        await price();
        return;
      }
      const done = await act('desk-outline', { path, slides: JSON.parse(now()),
        expected: outline.expected }, save, 'Saved. Only the sections whose slides changed are '
        + 'redrawn.', said);
      if (done) delete held.outlines[path];
    };
    const paint = () => {
      rows.replaceChildren(...edit.work.map((one, index) => outlineRow(edit, one, index,
        editable, { typed: tell, changed: price, moved: () => {
          paint();
          price();
        } })));
      tell();
    };
    paint();
    h.add(node, make('p', '', 'Each slide’s words, in order. Saving redraws only the sections '
      + 'whose slides changed; the rest stay as they are drawn.'), rows);
    if (editable) h.add(node, said, bar(save, back));
    return node;
  }

  function outlineRow(edit, one, index, editable, on) {
    const title = one.title || 'Untitled slide';
    const node = make('li', 'outline-slide');
    h.add(node, make('p', 'outline-top', 'Slide ' + (index + 1)
      + (one.kind ? ' · ' + h.capital(h.spoken(one.kind)) : '')));
    if (editable) {
      h.add(node, h.field('desk-outline-title-' + index, 'Title of slide ' + (index + 1), one,
        'title', { limit: 300, typed: on.typed, changed: on.changed }));
    } else {
      h.add(node, make('p', 'outline-title', title));
    }
    h.add(node, wordsPart({ subtitle: one.subtitle, detail: one.detail, points: one.points,
      caveat: one.caveat, source: one.source }));
    if (!editable) return node;
    const move = (by) => () => {
      const [taken] = edit.work.splice(index, 1);
      edit.work.splice(index + by, 0, taken);
      on.moved();
      h.focusKey('desk-outline ' + (by < 0 ? 'up ' : 'down ') + taken.id);
    };
    const up = h.button('Move up', 'menu-item', move(-1), 'desk-outline up ' + one.id);
    const down = h.button('Move down', 'menu-item', move(1), 'desk-outline down ' + one.id);
    const remove = h.button('Remove', 'menu-item', () => {
      edit.work.splice(index, 1);
      on.moved();
      h.focusKey('desk-outline-save');
    }, 'desk-outline remove ' + one.id);
    up.setAttribute('aria-label', 'Move up: “' + title + '”');
    down.setAttribute('aria-label', 'Move down: “' + title + '”');
    remove.setAttribute('aria-label', 'Remove “' + title + '”');
    up.disabled = index === 0;
    down.disabled = index === edit.work.length - 1;
    remove.disabled = edit.work.length < 2;
    return h.add(node, bar(h.moreMenu('More for “' + title + '”', [up, down, remove],
      'desk-outline-more ' + one.id)));
  }

  // How a document is read, and the way to read it the other way, at its price.
  function readingPart(run, can, working) {
    const reading = run.desk.outline.reading;
    const path = h.view.path;
    const other = reading.kind === 'spec' ? 'material' : 'spec';
    const node = h.card('How your document is read');
    h.add(node, make('p', '', READ_AS[reading.kind] || ''));
    if (!can) return node;
    const go = h.capsule('Read it the other way', '', () => act('desk-reread', { path,
      kind: other }, go, 'Your document is read again, ' + h.lower(READ_AS[other])), 'desk-reread');
    go.disabled = working;
    return h.add(node, bar(go), reading.price ? make('p', 'quiet', reading.price) : null);
  }

  // The look the deck is drawn in, and the way to change it, at its price.
  function lookPart(run, can, working) {
    const look = run.desk.outline.look;
    const path = h.view.path;
    const node = h.card('The look');
    h.add(node, make('p', '', look.name ? 'Drawn in ' + look.name + '.'
      : 'Drawn in the brand’s default look.'));
    if (!can) return node;
    const go = h.capsule('Change the look', '', () => act('desk-look-again', { path }, go,
      'The looks are being drawn again. Pick one when they are ready.'), 'desk-look-again');
    go.disabled = working;
    return h.add(node, make('p', 'quiet', 'The brand draws its looks again, you pick one, and '
      + 'every section is drawn again in it.'), bar(go),
    look.price ? make('p', 'quiet', look.price) : null);
  }

  // --- Deliver ------------------------------------------------------------------------------
  // Deliver opens a sheet that says whether the deck was reviewed, lists each blocker the
  // brand check found with its slide, and is confirmed there. It is bound to the deck on
  // screen and to the blockers the sheet listed.

  function deliverSheet() {
    const run = h.view.run;
    const found = run.desk;
    const blockers = h.list(found.blockers);
    const form = make('form', 'create-flow');
    form.noValidate = true;
    const problem = h.problemLine();
    const go = h.submitButton(blockers.length ? 'Deliver anyway' : 'Deliver', 'deliver-confirm');
    const cancel = h.capsule('Cancel', 'quiet', h.closeSheet, 'cancel');
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      deliver(run, blockers, go, problem);
    });
    const google = run.output === 'google';
    const ready = deliverableNow(found);
    if (!ready) {
      h.say(problem, NOT_DELIVERABLE);
      go.disabled = true;
    }
    h.add(form,
      make('p', '', found.reviewed ? 'This deck was reviewed.' : 'This deck has not been '
        + 'reviewed. Its brand check ran; no review of the deck did.'),
      blockers.length ? make('p', '', 'The brand check found ' + h.count(blockers.length,
        'problem that blocks', 'problems that block') + ' delivery. Deliver anyway, or fix '
        + 'them first.') : make('p', '', 'The brand check found nothing that blocks delivery.'),
      blockers.length ? h.bullets(blockers.map((one) => (typeof one.number === 'number'
        ? 'Slide ' + one.number + ': ' : '') + one.says)) : null,
      make('p', 'quiet', google && h.googleReady() ? 'It goes to Google Slides.'
        : google ? 'Google is not connected on this computer, so delivering makes a '
          + 'PowerPoint file. Send it to Google Slides once you are signed in.'
          : 'It is made a PowerPoint file, to download from here.'),
      problem, h.add(make('div', 'bar create-foot'), go, cancel));
    return [h.add(make('div', 'sheet-heading'), h.sheetTitle('Deliver the deck')), form];
  }

  async function deliver(run, blockers, pressed, problem) {
    if (h.view.busy) return;
    // The blockers are the ones this sheet listed, whatever the deck says since.
    const seen = run.desk.blockers_seen;
    await flushAll();
    run = h.view.run || run;
    // The deck may have moved on since the sheet was opened: it is read as it is now.
    if (!deliverableNow(run.desk || {})) {
      h.say(problem, NOT_DELIVERABLE);
      return;
    }
    const path = run.path || h.view.path;
    const body = { path, expected: run.desk.expected };
    if (blockers.length) body.blockers_seen = seen;
    h.view.busy = true;
    pressed.disabled = true;
    h.say(problem, '');
    let found;
    try {
      found = await h.send('desk-deliver', body);
    } catch (failure) {
      h.view.busy = false;
      pressed.disabled = false;
      h.say(problem, failure.message + ' Nothing was delivered.');
      return;
    }
    h.view.busy = false;
    h.view.sheet = '';
    h.drawSheet();
    h.toast('Delivered.');
    if (h.view.screen === 'deck' && h.view.path === path) {
      h.view.run = found;
      h.view.barred = '';
      h.paintDeck(false);
    }
    h.refresh();
  }

  window.deckDesk = { init, opens, start, progress, desk, deliverSheet, historySheet };
  // The page waits for this script before it begins; it begins now.
  if (typeof window.deckDeskWaits === 'function') window.deckDeskWaits();
}());
