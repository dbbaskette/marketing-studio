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

  // --- the desk -----------------------------------------------------------------------------

  function desk(run, fresh) {
    const found = run.desk;
    const read = h.theirs(run);
    const path = h.view.path;
    const title = run.title || 'Untitled';
    const working = Boolean(found.working);
    const lead = h.view.sheet || read ? '' : run.question ? 'answer'
      : run.problem && run.problem.action ? 'problem' : found.delivered ? '' : 'deliver';
    h.view.lead = lead;
    const tab = held.tabs[path] === 'outline' ? 'outline' : 'slides';
    const can = !read && found.drawn_here;
    h.placeParts({ title, above: above(run), back: true, actions: deskActions(run, lead),
      mark: ['desk', title, run.state, lead, read, run.driver, working, found.drawn_here,
        Boolean(found.delivered), found.expected, h.view.downloading] }, [
      ...interruptions(run, lead, title),
      working ? ['working', [found.working, read], () => workingPart(run)] : null,
      !found.drawn_here ? ['away', [found.no_drawing, found.draw_here_price, read, working],
        () => awayPart(run)] : null,
      found.delivered ? ['delivered', [found.delivered, title], () => deliveredPart(run)]
        : null,
      found.revision ? ['revision', [found.revision], () => make('p', 'quiet', found.revision)]
        : null,
      ['head', [tab], () => headPart(tab)],
      ...(tab === 'outline' ? outlineParts(run, can, working)
        : slideParts(run, can, working)),
    ], fresh);
    h.tidyPictures();
  }

  // Deliver, the one filled button, then Download and More.
  function deskActions(run, lead) {
    if (h.theirs(run)) return [];
    const found = run.desk;
    const deliver = found.delivered ? null : h.capsule('Deliver', lead === 'deliver' ? 'filled'
      : '', h.openSheet('desk-deliver', 'deliver'), 'deliver');
    if (deliver) deliver.disabled = Boolean(found.working) || !found.drawn_here || !found.expected;
    const download = found.drawn_here ? h.capsule(h.view.downloading ? 'Downloading…'
      : 'Download', '', () => h.downloadDeck(run, download), 'download') : null;
    return [deliver, download, moreFor(run)];
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
    return node;
  }

  // The one sentence of the desk, and its two tabs.
  function headPart(tab) {
    const tabs = h.segmented('The desk', ['Slides', 'Outline'], tab === 'outline' ? 1 : 0,
      (index) => {
        held.tabs[h.view.path] = index ? 'outline' : 'slides';
        h.paintDeck(false);
      }, 'desk-tab');
    tabs.classList.add('deck-desk-tabs');
    return h.pageHead(DESK_LEDE, [tabs]);
  }

  // --- the Slides tab: the whole-deck note, then each section's cards -------------------------

  function slideParts(run, can, working) {
    const found = run.desk;
    return [
      can ? ['whole', [found.expected, found.deck_price, working],
        () => wholePart(run, working)] : null,
      ...h.list(found.sections).map((part, index) => ['section ' + index,
        [part, found.expected, can, working], () => sectionPart(run, part, can)]),
    ];
  }

  function wholePart(run, working) {
    const path = h.view.path;
    const kept = held.deck[path] || (held.deck[path] = { note: '' });
    const id = 'desk-deck-note';
    const node = h.card('The whole deck');
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
    return h.add(node, box, bar(go), make('p', 'quiet', run.desk.deck_price || ''));
  }

  function sectionPart(run, part, can) {
    const node = make('section', 'deck-desk-section');
    if (!part.lead) {
      const heading = make('h2', 'deck-desk-section-title', 'Section ' + part.number);
      heading.id = 'desk-section-' + part.number;
      node.setAttribute('aria-labelledby', heading.id);
      h.add(node, heading);
    }
    for (const one of h.list(part.slides)) h.add(node, slideCard(run, one, can));
    return node;
  }

  function slideCard(run, one, can) {
    const kind = one.lead && one.kind ? ' · ' + h.capital(h.spoken(one.kind)) : '';
    const words = one.words || {};
    const node = make('section', 'card shine deck-desk-slide' + (one.busy ? ' desk-working'
      : ''));
    h.add(node, make('h3', 'card-title', 'Slide ' + one.number + kind),
      h.add(make('div', 'deck-desk-picture'), one.image ? h.picture(one.image,
        h.slideName({ number: one.number, title: words.title }), run.desk.expected)
        : make('p', 'quiet', 'There is no picture of this slide on this computer yet.')),
      wordsPart(words),
      one.notes ? h.add(make('p', 'quiet'), make('strong', '', 'Speaker notes: '), one.notes)
        : null,
      h.list(one.findings).length ? h.findingItems(one.findings) : null,
      h.list(one.audit).length ? auditPart(one.audit) : null,
      one.busy ? h.add(make('p', 'desk-working-note'), h.state('current', 'Redrawing…'))
        : null,
      one.note ? noteSaid(one.note) : null);
    if (!one.lead && can) h.add(node, ...noteBox(run, one));
    return node;
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

  // The brand check on this slide: what blocks delivery first, then what it warns of.
  function auditPart(audit) {
    const ordered = audit.slice().sort((one, other) => (one.kind === 'error' ? 0 : 1)
      - (other.kind === 'error' ? 0 : 1));
    const items = make('ul', 'plain');
    for (const one of ordered) {
      h.add(items, h.add(make('li'), one.kind === 'error'
        ? h.state('late', 'The brand check: ' + one.says + ' It blocks delivery.')
        : h.state('none', 'The brand check: ' + one.says)));
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

  // The note box of a content slide: Redraw slide N, its price under it, and where words
  // change.
  function noteBox(run, one) {
    const path = h.view.path;
    const key = path + '\n' + one.number;
    const kept = held.notes[key] || (held.notes[key] = { note: '' });
    const id = 'desk-note-' + one.number;
    const box = noteField(id, 'How should this slide change?', kept, 'Slide ' + one.number);
    const input = box.querySelector('textarea');
    const go = h.capsule('Redraw slide ' + one.number, '', async () => {
      const note = kept.note.trim();
      if (!note) {
        h.refuse(id, NO_NOTE);
        input.focus();
        return;
      }
      const done = await act('desk-note', { path, number: one.number, note,
        expected: run.desk.expected }, go, 'Slide ' + one.number + ' is being redrawn. Every '
        + 'other part of the deck stays exactly as it is.', h.byId(id + '-problem'));
      if (!done) return;
      kept.note = '';
      input.value = '';
    }, 'desk-redraw ' + one.number);
    input.disabled = Boolean(one.busy);
    go.disabled = Boolean(one.busy);
    return [box, bar(go), one.price ? make('p', 'quiet', one.price) : null,
      make('p', 'quiet', WORDS_LINE)];
  }

  // --- the Outline tab ----------------------------------------------------------------------

  function outlineParts(run, can, working) {
    const outline = run.desk.outline;
    if (!outline) return [];
    return [
      ['outline', [outline.expected, outline.slides, outline.editable, can, working],
        () => outlinePart(run, can && outline.editable)],
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

  function outlinePart(run, editable) {
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
      said.textContent = !changed ? 'Saving redraws only the sections whose slides change.'
        : edit.priced === now() ? edit.says : 'Its price is worked out when you leave the box.';
      save.disabled = !changed || edit.priced !== now();
      back.hidden = !changed;
    };
    // What saving would redraw is asked of the server before Save sends anything.
    const price = async () => {
      if (!edited()) {
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
    h.add(form,
      make('p', '', found.reviewed ? 'This deck was reviewed.' : 'This deck has not been '
        + 'reviewed. Its brand check ran; no review of the deck did.'),
      blockers.length ? make('p', '', 'The brand check found ' + h.count(blockers.length,
        'problem that blocks', 'problems that block') + ' delivery. Deliver anyway, or fix '
        + 'them first.') : make('p', '', 'The brand check found nothing that blocks delivery.'),
      blockers.length ? h.bullets(blockers.map((one) => 'Slide ' + one.number + ': '
        + one.says)) : null,
      make('p', 'quiet', google && h.googleReady() ? 'It goes to Google Slides.'
        : google ? 'Google is not connected on this computer, so delivering makes a '
          + 'PowerPoint file. Send it to Google Slides once you are signed in.'
          : 'It is made a PowerPoint file, to download from here.'),
      problem, h.add(make('div', 'bar create-foot'), go, cancel));
    return [h.add(make('div', 'sheet-heading'), h.sheetTitle('Deliver the deck')), form];
  }

  async function deliver(run, blockers, pressed, problem) {
    if (h.view.busy) return;
    const path = run.path || h.view.path;
    const body = { path, expected: run.desk.expected };
    if (blockers.length) body.blockers_seen = run.desk.blockers_seen;
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

  window.deckDesk = { init, opens, start, progress, desk, deliverSheet };
  // The page waits for this script before it begins; it begins now.
  if (typeof window.deckDeskWaits === 'function') window.deckDeskWaits();
}());
