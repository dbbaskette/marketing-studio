// The page: home, trainings, status, settings, one training, and a gate. With the runner
// behind it there are six more: set-up, a new training, a run, what a deck says, a finished
// training's index, and what the workspace has published.
// It draws what the server says and sends back only what the person decides. Every value
// from the server is placed as text, so nothing in a training's files or its record can
// ever be read as markup. Documents are drawn by markdown.js, which keeps the same rule.
// A slide's picture is fetched as bytes and shown from memory, never from an address.
'use strict';

const TOKEN_HEADER = 'X-Training-Studio-Token';
const POLL_SHOWN = 5000;
const POLL_HIDDEN = 20000;
const POLL_RUN = 2000; // while a run is working and its own screen is open
// Where set-up is read each time. It carries what was found of the skills, for home and status.
const SET_UP_SHOWN = ['home', 'status', 'settings', 'setup', 'new'];
const WORKING = 3 * 60000; // with no run to ask, a training that changed this recently is working
const DRAWING = 'http://www.w3.org/2000/svg'; // the name of the SVG language; nothing is fetched
const COUNTED = ['Nothing needs', 'One thing needs', 'Two things need', 'Three things need',
  'Four things need', 'Five things need', 'Six things need', 'Seven things need',
  'Eight things need', 'Nine things need', 'Ten things need'];
const NOTICES = {
  stopped: 'This page has lost touch with Training Studio, so it cannot read or save anything. '
    + 'Run the desk command again in your terminal and use the new link.',
  refused: 'This link does not match the page that is running. '
    + 'Run the desk command again in your terminal and use the link it prints, whole.',
};
// Under the runner, opened from Open Training Studio, the way back is the same.
const RUNNER_NOTICES = {
  stopped: 'This page has lost touch with Training Studio, so it cannot read or save anything. '
    + 'Open Training Studio again and use the new link.',
  refused: 'This link does not match the page that is running. '
    + 'Open Training Studio again and use the new link.',
};

function noticeOf(kind) {
  return (view.runner ? RUNNER_NOTICES : NOTICES)[kind];
}
// Every icon is drawn here, on a 24 by 24 grid, in one weight of line.
const ICONS = {
  studio: ['M2 8 12 3l10 5-10 5z', 'M6 10v8c4 3 8 3 12 0v-8', 'M22 8v10'],
  home: ['M4 11.5 12 4.5l8 7', 'M6.5 10.5V19.5h11V10.5'],
  trainings: ['M12 4 3.5 8.5 12 13l8.5-4.5z', 'M3.5 12.5 12 17l8.5-4.5', 'M3.5 16.5 12 21l8.5-4.5'],
  status: ['M3 12.5h4l2.5-6.5 4.5 12 2.5-5.5H21'],
  settings: ['M4.5 7.5h7', 'M16.5 7.5h3', 'M14 5.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4z', 'M4.5 16.5h3',
    'M12.5 16.5h7', 'M10 14.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4z'],
  suite: ['M4 4h6v6H4z', 'M14 4h6v6h-6z', 'M4 14h6v6H4z', 'M14 14h6v6h-6z'],
  back: ['M14.5 5.5 8 12l6.5 6.5'],
  more: ['M6 12h.01', 'M12 12h.01', 'M18 12h.01'],
  check: ['M5.5 12.5 10 17l8.5-10'],
  eye: ['M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z',
    'M12 9.2a2.8 2.8 0 1 0 0 5.6 2.8 2.8 0 0 0 0-5.6z'],
  warn: ['M12 6v7.5', 'M12 17.5h.01'],
  minus: ['M6.5 12h11'],
  slash: ['M7 17 17 7'],
};
// The decisions that take a note. `needed` is what the page says when one is missing.
const FORMS = {
  revise: {
    title: 'Ask for changes',
    label: 'What should change?',
    hint: 'Say it in your own words. Your assistant makes the change and brings it back here.',
    needed: 'Say what should change first.',
    send: 'Send for changes',
  },
  rebuild: {
    title: 'Rebuild it',
    label: 'Anything to do differently? You can leave this empty.',
    hint: 'It is made again from what it is built from, and comes back here for your review.',
    needed: '',
    send: 'Ask for a rebuild',
  },
  skip: {
    title: 'Skip this stage',
    label: 'Why leave this stage out?',
    hint: 'The reason is kept with the training. You can bring the stage back later.',
    needed: 'Give a reason first.',
    send: 'Skip this stage',
  },
  accept: {
    title: 'Accept it as it is',
    label: 'Why is it fine as it is?',
    hint: 'What it was built from has changed. Your reason is kept with the training.',
    needed: 'Give a reason first.',
    send: 'Accept as it is',
  },
};
// The decisions that take no note. They are confirmed in the sheet before anything is sent.
const CONFIRMS = {
  approve: {
    title: (label) => 'Approve ' + label + '?',
    says: 'You are approving this version, built from what it is built from now. If either '
      + 'changes, it comes back to you.',
    send: 'Approve',
  },
  restore: {
    title: () => 'Bring this stage back?',
    says: 'It becomes part of the training again, and what it makes will come to you for review.',
    send: 'Bring it back',
  },
};
// The shape beside a desk training's standing (runner/drafts.py PHASES).
const PHASE_BEADS = { working: 'current', decision: 'review', attention: 'late',
  drafts: 'review', ready: 'done', stopped: 'off' };
const STATES = {
  'needs-you': ['review', 'Waiting for you'],
  'in-progress': ['current', 'In progress'],
  finished: ['done', 'Finished'],
};
const STAGE_BEADS = { 'not-started': 'none', 'left-out': 'out', unavailable: 'off' };
const FILE_BEADS = {
  approved: 'done', draft: 'current', stale: 'late', 'not-started': 'none',
  skipped: 'out', unavailable: 'off',
};
const BEAD_ICONS = { done: 'check', review: 'eye', late: 'warn', out: 'minus', off: 'slash' };
const COPY_WORDS = {
  current: 'up to date', outdated: 'out of date', missing: 'not made yet',
  unavailable: 'could not be made',
};
const COMPUTER_WORDS = {
  ok: ['done', 'Ready'], missing: ['off', 'Not installed'], problem: ['late', 'Needs attention'],
};
const NAV = [['go-home', 'home', 'home'], ['go-trainings', 'trainings', 'trainings'],
  ['go-status', 'status', 'status'], ['go-settings', 'settings', 'settings']];
// The screen in the sidebar that each other screen belongs to.
const PARENTS = { training: 'trainings', gate: 'trainings', run: 'trainings', new: 'trainings',
  index: 'trainings', outline: 'trainings', published: 'trainings', setup: 'settings' };

// What the runner adds. A run and each of its steps say where they are in these words.
const RUN_WORDS = {
  working: ['current', 'Working on its own'],
  waiting: ['review', 'Waiting for you'],
  paused: ['out', 'Paused'],
  stopped: ['off', 'Stopped'],
  failed: ['late', 'Stopped: something went wrong'],
  done: ['done', 'Finished here'],
  // A training a teammate's computer runs: only what was last shared is known here.
  elsewhere: ['none', 'Run by your teammates'],
};
const STEP_WORDS = {
  done: ['done', 'Done'], working: ['current', 'Working'], waiting: ['review', 'Waiting for you'],
  failed: ['late', 'Failed'], 'to-do': ['none', 'To do'],
};
const STEERED = {
  pause: 'Paused. Nothing more is started until you resume it.',
  resume: 'Carrying on.',
  stop: 'Stopped. The step in hand was ended and its work so far is lost; everything '
    + 'finished before it is kept.',
  retry: 'Trying again.',
  'more-time': 'Trying again, with twice the time for each step.',
  'finish-level': 'It finishes this level, then waits. Resume it when you are ready for the next.',
};
const AGENTS = ['claude', 'codex'];
const AGENT_NAMES = { claude: 'Claude Code', codex: 'Codex' };
// The first choice of a model and of a reasoning level, which leaves it to the agent.
const OWN_CHOICE = 'The agent’s own choice';
// Where "Another model…" is in the list of models. No name an agent takes has a space.
const OTHER_MODEL = ' other';
const LEVEL_NAMES = { none: 'None', minimal: 'Minimal', low: 'Low', medium: 'Medium',
  high: 'High', xhigh: 'Extra high', max: 'Maximum', ultra: 'Ultra' };
const MODELS_AGAIN = 60000; // a list of models that could not be made is asked for again after
const SHARE = ['each-decision', 'when-asked'];
// The file of defaults every studio on this computer shares, where the runner reads it.
const STUDIOS_FILE = '~/.config/studios-config.json';
// What the folder and the workspace are called become names of folders, so they are plain.
const PLAIN_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
const PLAIN_SAYS = 'Use letters, digits, dots, hyphens and underscores, with no spaces, '
  + 'starting with a letter or a digit: field-training, for example.';
const SHARE_SAYS = [
  'After each decision: your team sees the drafts, your answers and each review as soon as '
    + 'you decide a stage, finished or not.',
  'Only when I ask: everything stays on this computer, and your team sees nothing new, '
    + 'until you press “Share now”.',
];
const PURPOSES = ['Field enablement', 'Technical upskilling', 'General knowledge'];
const LEVELS = ['101', '201', '301', '401'];
const DECKS = [['pptx', 'PowerPoint'], ['google', 'Google Slides'], [null, 'No deck']];
const DELIVERIES = [['live', 'Presented in a session'], ['reading', 'Read on its own']];
const COPIES = [['google', 'Google Docs'], ['word', 'Word']];
const MATERIALS = [['document', 'Learner guide'], ['brief', 'Reference brief'],
  ['scenario', 'Practice scenarios']];
// Where the research looks. What each answer means is said under the choice.
const REVIEW_LEVELS = [['balanced', 'Balanced'], ['automatic', 'Automatic draft'],
  ['step_by_step', 'Step by step']];
// Where research may look: your documents, your sites and/or the public web, any of them
// together. Your sites start as the list every studio shares; a site added on the form is
// for that training only. The words are the ones every studio uses
// (studio_core.research_sites), and the runner refuses the same choices again.
const RESEARCH_FROM = [['documents', 'Your documents'], ['sites', 'Your sites'],
  ['web', 'The public web']];
const RESEARCH_SAYS = {
  documents: 'Your documents: it reads the documents you give it. You add them right after '
    + 'starting, and they stay on this computer.',
  // Said one way with the public web off, another with it on.
  sites: 'Your sites: they are searched through the assistant’s web search tool, with site: '
    + 'searches, and only pages from under your sites are saved.',
  sitesAndWeb: 'Your sites: they are searched first, through the assistant’s web search tool '
    + 'with site: searches. The public web fills what they leave open.',
  web: 'The public web: it searches for pages anyone can read, and keeps every page it quotes '
    + 'with the training.',
};
const RESEARCH_EMPTY = 'Choose where research may look: your documents, your sites or the '
  + 'public web.';
const RESEARCH_NO_SITES = 'Choose at least one of your sites, or turn your sites off.';
const SITES_NAMED = 5;   // sites a summary names before "and N more"
// A training where the run has made everything it can, and the deck is all that is left.
const DECK_LEFT = 'Everything but the slide deck is made: check this computer again once a '
  + 'deck can be made on it, or leave the deck out.';
const SETTLED = ['done', 'left-out', 'unavailable'];
// Who wrote a practice scenario. A person's own file is never rewritten for them.
const WHOSE = {
  you: 'This file is yours: you wrote it, and Training Studio does not rewrite it. If you ask '
    + 'for changes, your own wording is laid out under the headings, and you are asked for '
    + 'anything that is missing. A scenario file written in a conversation training’s folder '
    + 'is used as it is.',
  runner: 'This file is Training Studio’s draft, written from the practice plan in the '
    + 'blueprint.',
};
// A copy of a guide, a brief or a Yoodli scenario, and where it stands.
const COPY_KINDS = { google: 'Google Doc', word: 'Word copy' };
const COPY_STATES = {
  made: ['done', 'Made'], 'out-of-date': ['late', 'Out of date'], 'not-made': ['off', 'Not made'],
};
const WEB_LINK = /^https?:\/\/\S+$/i;
const KEPT_HERE = 'Your documents stay on this computer and are never shared with your team. '
  + 'Passages quoted from them appear in the research report, which is shared.';
// How the pictures of a deck's slides are made while it is drawn. What each way means is
// said under the choice.
const PREVIEWS = ['local', 'drive'];
const PREVIEW_NAMES = ['LibreOffice', 'Google Drive'];
const PREVIEW_SAYS = [
  'LibreOffice: the pictures are made on this computer, and nothing leaves it.',
  'Google Drive: each deck keeps one presentation named “Preview: …” in your Drive, written '
    + 'again at each render. Training Studio never deletes it. Settings lists the ones it '
    + 'made, each with its address, so that you can.',
];
// With a slides tool that keeps a pool of preview presentations, no file is named for a deck.
const POOL_SAYS = 'Google Drive: previews are drawn in a few shared presentations named '
  + '“Preview: …” in your Drive, reused by every deck. Training Studio never deletes them.';
function pooled() {
  return Boolean(view.setup && view.setup.previews && view.setup.previews.pool);
}
function previewSays() {
  return pooled() ? [PREVIEW_SAYS[0], POOL_SAYS] : PREVIEW_SAYS;
}
const PREVIEW_ABSENT = [
  'LibreOffice was not found on this computer, so Google Drive is the one way there is.',
  'Google access on this computer does not reach Drive, so LibreOffice is the one way there '
    + 'is.',
];
const PREVIEW_WORDS = { local: 'made with LibreOffice, on this computer',
  drive: 'made through Google Drive' };
// A section of a deck while it is drawn, and a finding of the review by how much it matters.
const SECTION_WORDS = {
  'to-do': ['none', 'Not started'], working: ['current', 'Being drawn'],
  done: ['done', 'Handed in'], failed: ['late', 'Could not be drawn'],
};
// How each asset a deck's approved design uses stands in the slides tool's record of it.
const ASSET_WORDS = {
  recorded: ['done', 'Recorded'], wanted: ['none', 'Still needed'],
  missing: ['late', 'Its file is missing'], changed: ['late', 'Its file has changed'],
  conflict: ['late', 'Recorded as something else'],
};
const SEVERITIES = { critical: ['late', 'Critical'], major: ['late', 'Major'],
  minor: ['none', 'Minor'] };
const SERIOUS = ['critical', 'major'];
// What a finding is about, where drawing again would not put it right, and the categories a
// review against the approved design files its findings in, as the slides tool orders them.
const ABOUT_TAGS = {
  content: 'About what it says', concept: 'About how it was approved to teach',
};
const CATEGORY_WORDS = {
  'asset-failure': 'The pictures and icons it was approved with',
  'design-deviation': 'How it departs from the approved design',
  'visual-teaching': 'Whether the visual teaches',
  'fit-defect': 'How it fits',
  'direct-text': 'Direct text by decision',
};
// What a brand's own check answers when it has nothing to raise.
const AUDIT_QUIET = ['ok', 'clear', 'clean', 'pass', 'passed', 'fine', 'success'];
// What the page says once what a deck says is decided. A gate's decision is answered by the
// server in these words; this one is answered with the run, which says what it does next.
const OUTLINE_SAID = {
  approve: 'Approved.',
  revise: 'Your changes are noted. Once they are made, the new version comes back here for '
    + 'your review.',
};
const OUTLINE_APPROVES = 'You are approving what each slide says. The slides are drawn from '
  + 'these words and come to you again as a deck. If the blueprint or the guide changes, '
  + 'this comes back to you.';
const OUTLINE_APPROVES_DESIGN = 'You are approving what each slide says and how it is '
  + 'drawn, together. The slides are drawn from both and come to you again as a deck. If the '
  + 'blueprint or the guide changes, this comes back to you.';
const CLOSE = 'You can close this page; it says when it needs you again.';
// What a team adds. Each of these is confirmed in the sheet before anything is sent: who
// runs a training, publishing a finished one, and bringing one in from a conversation.
const TEAM_SHEETS = ['take', 'hand-over', 'publish', 'adopt'];
const READ_ONLY = 'You can read everything here: the steps, the files and the reviews. '
  + 'Nothing here can be paused, stopped, decided or answered from this computer.';
const PUBLISH_SAYS = 'Publishing marks this training, exactly as it stands now, as its next '
  + 'numbered revision in the workspace, where it is listed with its index to read. Nothing '
  + 'is copied anywhere.';
const PUBLISH_KEPT = 'A revision is never moved afterwards. If the training changes later, '
  + 'publish it again, and that is the next revision. Documents you supplied and pages that '
  + 'were saved are not part of it.';
const NOTIFY_SAYS = 'When no page is open and a training needs you, this computer tells you '
  + 'through its own notifications. It says only the training’s title and that it needs a '
  + 'decision, once for each thing that needs you.';
const NOTIFY_DIFFERS = 'This is not the browser’s notification above. That one works only '
  + 'while this page is open in a tab; this one is for when no page is open at all.';
// Deleting a training: what the card offers, and what its confirmation says. The runner says
// what goes and what stays for each training; these are the words around it.
const DELETE_SAYS = 'If you no longer want this training, delete it. It goes from this '
  + 'computer';
const DELETE_TEAM = ' and from your team’s workspace';
const DELETE_STOPS = 'It is working now. Deleting it stops it first, and ends everything it '
  + 'is running.';
const DELETE_SHARED = { decision: 'Your team sees it gone straight away.',
  asked: 'Your team sees it gone the next time you press Share now.' };
const DELETE_UNDO = 'This cannot be undone from this page. Its history stays in git, where '
  + 'someone who knows git can bring it back.';
const DELETE_DRIVE = 'Training Studio never deletes anything in your Google Drive. Remove '
  + 'these yourself if you no longer want them:';
// Drawing a deck again from a design: what its card and its confirmation say. The runner says
// which decks may be; these are the words around them.
const REDESIGN_SAYS = 'This deck was approved before decks were drawn from a design. Training '
  + 'Studio can draw it again from one: each slide planned to show what it teaches.';
const REDESIGN_DOES = ['What the deck says is written again, with how each slide is drawn, '
  + 'from the words you approved. You review both together, as for a new deck.',
'Then it is drawn, rendered and reviewed again, and comes back to you to approve.',
'Nothing else in the training changes.'];
const REDESIGN_KEEPS = ['The deck you approved, as it is, until the new one replaces it. Then '
  + 'it stays in the training’s history.', 'What you approved it should say, and when.'];
const REDESIGN_COSTS = 'It costs about what drawing the deck cost the first time.';
// Where a finished training's index is, in its folder.
const UPDATE_SAYS = 'Each is fetched from its own repository at the one revision this '
  + 'Training Studio was made with, and checked file for file before any of it is run. Then '
  + 'its own installer is run with Node, and registers the skill for every assistant it knows.';
const UPDATE_WAITS = 'It takes a few minutes, while you carry on. The Status screen says how '
  + 'it goes.';
const LOOK_SAYS = 'Once a day, Training Studio asks where it and its skills are kept which '
  + 'releases there are, and says on Home when a newer one is out. It only reads their names: '
  + 'nothing is downloaded or run, and nothing is installed without your yes.';
const BRAND_SAYS = 'Your organisation’s brand skill is released from a repository of its own. '
  + 'Name it here, and Training Studio installs and upgrades the brand skill from it, with '
  + 'your own git access and only after your yes. A brand skill you installed yourself is '
  + 'still found and used. Every studio on this computer shares the repository and release '
  + 'named here, so saving changes them for all of them.';
const BRAND_STEPS = ['The release is fetched with your own access: its ZIP through gh, where '
  + 'gh is signed in, or else the tag with git.',
'Its own installer is run, and told to leave harness-research alone. Where it would put in '
  + 'its own harness-slides in place of the one Training Studio uses, nothing is run, and '
  + 'you are told.',
'Then this computer is checked again, so that new decks can use it.'];
const BRAND_TRUST = 'The repository is your choice, so the release is not checked against '
  + 'anything Training Studio knows. Install only from a repository you trust.';
const BRAND_WAITS = 'It takes a few minutes, while you carry on. Nothing is changed while a '
  + 'training is working.';
const UPGRADE_KEEPS = 'The version you have now is kept beside it, so trainings carry on where '
  + 'they are, and nothing of yours is touched.';
const UPGRADE_WAITS = 'It takes a minute or two, while you carry on. Nothing is changed while a '
  + 'training is working.';
// How each row of the versions is said: its bead and its words.
const VERSION_STATES = { current: ['done', 'Up to date'], update: ['review', 'Update available'],
  missing: ['late', 'Missing'], unknown: ['none', 'Not known'] };
const COME_BACK_TRIES = 90;   // one a second, while the runner opens its newer version
const SETUP_HIDDEN = 600000;  // how often a tab nobody looks at reads what was found of versions
const INDEX = 'README.md';
const HALTED = 'This training is not running, so nothing more happens until you resume it or '
  + 'try again.';

const view = {
  token: '', screen: 'home', path: null, artifact: null,
  listing: null, needs: 0, computer: undefined, known: null,
  gate: null, newer: null, training: null, after: null, sheet: '', opener: '', pane: 0,
  drawn: '', named: '', pushed: 0, timer: 0, turn: 0, busy: false, checking: false,
  // What the runner adds. `runner` is undefined until it has been asked for, and false on the
  // plain desk, where nothing below is ever used.
  runner: undefined, setup: null, form: null, draft: null, run: null,
  asks: {}, answers: {}, nextNotes: {}, agents: null, looking: false, unlooked: '',
  sharing: false,
  steered: '', barred: '',
  // Each agent's models as the runner listed them, by agent, and the choice of a model on
  // the screen: what it is held in, and how it is drawn again once a list comes.
  models: {}, picking: null,
  // What a sheet opened from a run decides, what a gate is read beside, and what was said
  // no to on a run: a document, the end of adding them, another try at the copies.
  deciding: null, beside: null, unadded: '', undone: '', copying: false, uncopied: '',
  // The slide a deck's gate is showing and the way to turn to another, and the pictures of
  // slides this screen holds: each by what it is of, those still to fetch, and what says
  // when one comes into view.
  slide: 0, viewer: null, pictures: new Map(), wanted: [], fetching: false, watcher: null,
  // What a team adds: every run and who runs what, what is published, what publishing just
  // answered, the copy a training was brought in as, what the runner last said about who
  // has each training, a look for teammates' work and what it brought, and the switch for
  // the computer's own notifications while it is being changed.
  status: null, shelf: null, issued: null, adopted: null, noticed: {},
  // The training the delete sheet is about, the open one or one on a list, what deleting it
  // would do, as the runner said when its sheet was opened, and the deck whose redesign the
  // sheet asks about.
  doomed: null, leaving: null, redesigning: null,
  // Looking online for newer releases, while it is switched, and why switching it was refused.
  turningLook: false, lookRefused: '',
  // The brand skill's repository as it is typed in Settings, while it is saved, and why
  // saving it was refused.
  brandForm: null, savingBrand: false, brandRefused: '',
  // Set-up is to start from the team repository every studio now shares.
  joining: false,
  // The versions Home last told of, when set-up was last read, and the restart in hand.
  versionsTold: undefined, setupAt: 0, restarting: false, comingBack: null,
  fetching: false, fetched: null, notifying: false, unnotified: '',
  // Why moving where a training is decided was refused, by training, and why bringing a stage
  // back was, by stage: each is said until it is tried again or the screen is left. And what
  // is typed in a sheet's note, kept until it is sent, so putting the sheet away loses nothing.
  unmoved: {}, unrestored: {}, notes: {},
  // What each item of a combined review is marked as on this page, until it is sent.
  marks: {},
  // What each list is filtered by, whether a phone's filters are open, and what is ticked on
  // a list, by list. Ticks stay through filter changes. The trainings a sheet deletes
  // together, and what the runner said deleting each would do.
  filters: {}, filtersOpen: {}, ticked: {}, doomedMany: null, leavingMany: null,
  // The picture a deck waits for that the picture sheet is adding.
  picture: null,
  // The refresh in hand, and whether another was asked for while it was. What the list said
  // of each run whose asks were read, and of the open training when it was last read: each
  // is read again only once that has changed.
  refreshing: null, again: false, asked: {}, recorded: '',
};
// Each part of a screen that is drawn in parts, and what it was drawn from.
const PARTS = new WeakMap();
// Each place a picture goes, and which picture that is.
const PLACES = new WeakMap();

const byId = (id) => document.getElementById(id);
const main = () => byId('main');

// --- small builders ---------------------------------------------------------------

function make(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function add(parent, ...children) {
  for (const child of children) {
    if (child) parent.append(child);
  }
  return parent;
}

function count(number, one, many) {
  return number + ' ' + (number === 1 ? one : many);
}

function list(value) {
  return Array.isArray(value) ? value : [];
}

// Several things named in a row: "one, two and three".
function series(items) {
  return items.length < 2 ? items.join('')
    : items.slice(0, -1).join(', ') + ' and ' + items[items.length - 1];
}

function ago(then) {
  const minutes = Math.round((Date.now() - then) / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return count(minutes, 'minute', 'minutes') + ' ago';
  const hours = Math.round(minutes / 60);
  if (hours < 24) return count(hours, 'hour', 'hours') + ' ago';
  const days = Math.round(hours / 24);
  if (days < 30) return count(days, 'day', 'days') + ' ago';
  return new Date(then).toLocaleDateString(undefined,
    { year: 'numeric', month: 'short', day: 'numeric' });
}

function clock(stamp) {
  return new Date(stamp).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});
}

function when(stamp) {
  const then = Date.parse(stamp);
  if (Number.isNaN(then)) return make('span', 'quiet', 'not recorded');
  const node = make('time', '', ago(then));
  node.dateTime = new Date(then).toISOString();
  node.title = new Date(then).toLocaleString();
  return node;
}

// A limit, in the round numbers a limit is set in: 8,000,000 bytes is 8 MB.
function megabytes(bytes) {
  return String(Math.round(bytes / 100000) / 10) + ' MB';
}

function size(bytes) {
  if (bytes < 1024) return count(bytes, 'byte', 'bytes');
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1024 / 1024).toFixed(1) + ' MB';
}

function pathInto(node, path) {
  String(path).split('/').forEach((part, index) => {
    if (index) add(node, '/', document.createElement('wbr'));
    add(node, part);
  });
  return node;
}

function levelsText(levels) {
  const held = list(levels);
  if (!held.length) return '';
  return (held.length === 1 ? 'Level ' : 'Levels ') + held.join(', ');
}

function icon(name) {
  const node = document.createElementNS(DRAWING, 'svg');
  node.setAttribute('class', 'icon');
  node.setAttribute('viewBox', '0 0 24 24');
  node.setAttribute('aria-hidden', 'true');
  node.setAttribute('focusable', 'false');
  for (const line of ICONS[name]) {
    const path = document.createElementNS(DRAWING, 'path');
    path.setAttribute('d', line);
    node.append(path);
  }
  return node;
}

function button(label, className, action, key) {
  const node = make('button', className, label);
  node.type = 'button';
  if (key) node.dataset.key = key;
  node.addEventListener('click', action);
  return node;
}

// A capsule of glass. The highlight on it follows the pointer.
function capsule(label, kind, action, key) {
  return button(label, 'button shine' + (kind ? ' button-' + kind : ''), action, key);
}

// The filled button of a form. Pressing it, or Enter in one of the form's boxes, sends it.
function submitButton(label, key) {
  const node = make('button', 'button shine button-filled', label);
  node.type = 'submit';
  node.dataset.key = key;
  return node;
}

// A form in the page's narrow column. The browser checks nothing in it: `sent` does, and
// says what is wrong beside each box.
function pageForm(sent) {
  const node = make('form', 'narrow');
  node.noValidate = true;
  node.addEventListener('submit', (event) => {
    event.preventDefault();
    sent();
  });
  return node;
}

// A bead that says a state by its shape. The words beside it say the same thing.
function bead(kind) {
  const node = make('span', 'bead');
  node.dataset.state = kind;
  node.setAttribute('aria-hidden', 'true');
  if (BEAD_ICONS[kind]) node.append(icon(BEAD_ICONS[kind]));
  return node;
}

function state(kind, text) {
  return add(make('span', 'state'), bead(kind), make('span', '', text));
}

function card(title, className) {
  const node = make('section', 'card shine' + (className ? ' ' + className : ''));
  return add(node, make('h2', 'card-title', title));
}

function bullets(items, className) {
  const node = make('ul', className || 'plain');
  for (const item of items) node.append(make('li', '', item));
  return node;
}

// The row of stages, the same everywhere: beads on a thread, filling as the training goes.
function beads(stages, small) {
  const row = make('ol', 'beads' + (small ? ' beads-small' : ''));
  let told = null;
  for (const stage of list(stages)) {
    const item = make('li', 'bead-stage');
    item.dataset.state = stage.state;
    if (small) item.title = stage.name + ': ' + stage.words;
    add(item, bead(STAGE_BEADS[stage.state] || stage.state),
      make('span', small ? 'offscreen' : 'bead-name', stage.name),
      make('span', 'offscreen', ': ' + stage.words));
    row.append(item);
    if (stage.state === 'review' || (stage.state === 'current' && !told)) told = stage;
  }
  if (small || !told) return row;
  // Where there is no room for a name under every bead, the one that matters is said below.
  const caption = make('p', 'beads-caption', told.name + ': ' + told.words);
  caption.setAttribute('aria-hidden', 'true');
  return add(document.createDocumentFragment(), row, caption);
}

// A control with two answers, or three. Its glass thumb slides to the one that is chosen.
function segmented(label, options, at, choose, key) {
  const node = make('div', 'segmented');
  node.setAttribute('role', 'group');
  node.setAttribute('aria-label', label);
  node.dataset.at = String(at);
  node.dataset.count = String(options.length);
  const thumb = make('span', 'seg-thumb');
  thumb.setAttribute('aria-hidden', 'true');
  node.append(thumb);
  options.forEach((text, index) => {
    const option = button(text, 'seg-option', () => {
      if (index !== Number(node.dataset.at)) choose(index, node);
    }, key + ' ' + index);
    option.setAttribute('aria-pressed', String(index === at));
    node.append(option);
  });
  return node;
}

function slide(node, at) {
  node.dataset.at = String(at);
  node.querySelectorAll('.seg-option').forEach((option, index) => {
    option.setAttribute('aria-pressed', String(index === at));
  });
}

// A line beside a control that says why it was refused. It is read out when it appears.
function alertLine(id) {
  const node = make('p', 'problem');
  node.id = id;
  node.setAttribute('role', 'alert');
  node.hidden = true;
  return node;
}

function say(problem, text) {
  problem.textContent = text;
  problem.hidden = !text;
}

// A labelled box to type in. What is typed is kept in `held[name]` as it is typed, so a
// screen that is drawn again still has it. With `picked` it is the browser's own file picker
// instead: nothing of it is kept, and what is chosen is handed to `picked`. With `options`,
// each a value and its name, it is the browser's own list to choose one from. An option
// with a third word, a group's name, is put in that group with the options next to it
// that name it too.
function field(id, label, held, name, about) {
  const spec = about || {};
  const title = make('label', 'field-label', label);
  title.htmlFor = id;
  const input = make(spec.long ? 'textarea' : spec.options ? 'select' : 'input',
    'input' + (spec.short ? ' input-short' : ''));
  input.id = id;
  if (spec.long) input.rows = 3;
  else if (!spec.options) input.type = spec.picked ? 'file' : 'text';
  if (spec.picked) {
    input.multiple = true;
    input.accept = spec.accept || '';
    input.addEventListener('change', () => spec.picked(input));
  } else {
    let group = null;
    for (const [value, text, under] of spec.options || []) {
      const option = make('option', '', text);
      option.value = value;
      if (!under) group = null;
      else if (!group || group.label !== under) {
        group = make('optgroup');
        group.label = under;
        input.append(group);
      }
      (group || input).append(option);
    }
    input.value = held[name] || '';
    input.maxLength = spec.long ? 4000 : 400;
    input.autocomplete = 'off';
    input.spellcheck = Boolean(spec.long);
    input.addEventListener('input', () => {
      held[name] = input.value;
      // A box that is being put right no longer says it is wrong.
      if (input.getAttribute('aria-invalid')) refuse(id, '');
      if (spec.typed) spec.typed();
    });
  }
  if (spec.mode) input.inputMode = spec.mode;
  input.dataset.key = id;
  const hint = spec.hint ? make('p', 'quiet field-hint', spec.hint) : null;
  if (hint) hint.id = id + '-hint';
  input.setAttribute('aria-describedby', (hint ? id + '-hint ' : '') + id + '-problem');
  if (spec.changed) input.addEventListener('change', spec.changed);
  const problem = alertLine(id + '-problem');
  // Drawn again after it was refused, it still says why.
  if (spec.refused) {
    say(problem, spec.refused);
    input.setAttribute('aria-invalid', 'true');
  }
  return add(make('div', 'field'), title, input, hint, problem);
}

// Refuse what is in a field, beside it, before anything is sent. Returns the field.
function refuse(id, text) {
  const input = byId(id);
  say(byId(id + '-problem'), text);
  if (text) input.setAttribute('aria-invalid', 'true');
  else input.removeAttribute('aria-invalid');
  return input;
}

// One choice among two or three, with its name above it and what it means below.
function choice(label, options, at, choose, key, hint) {
  const control = segmented(label, options, at, (index, node) => {
    slide(node, index);
    choose(index);
  }, key);
  return add(make('div', 'field'), make('p', 'field-label', label), control,
    hint ? make('p', 'quiet field-hint', hint) : null);
}

// A choice with what each of its answers means spelled out under it. The one that is chosen
// is marked there too.
function explained(label, options, says, at, choose, key) {
  const meanings = make('ul', 'reasons meanings');
  const mark = (chosen) => Array.from(meanings.children).forEach((item, index) => {
    if (index === chosen) item.dataset.chosen = 'true';
    else delete item.dataset.chosen;
  });
  for (const text of says) meanings.append(make('li', '', text));
  mark(at);
  return [choice(label, options, at, (index) => {
    choose(index);
    mark(index);
  }, key), meanings];
}

// A capsule that is on or off. A tick says it is on, so it does not rest on colour.
function chip(label, on, flip, key) {
  const node = button('', 'chip', () => {
    const now = node.getAttribute('aria-pressed') !== 'true';
    node.setAttribute('aria-pressed', String(now));
    flip(now);
  }, key);
  node.setAttribute('aria-pressed', String(Boolean(on)));
  return add(node, icon('check'), make('span', '', label));
}

// Where the shared settings are changed: Marketing Studio's own page, with the key kept in
// the fragment.
function settingsAddress() {
  return '/onboarding/#token=' + view.token;
}

// The shared review level, as a start form says it.
const REVIEW_WORDS = { balanced: 'Balanced', automatic: 'Automatic draft',
  step_by_step: 'Step by step' };

// A phone: the page's own width query for the narrow layout matches.
function narrow() {
  return Boolean(window.matchMedia && window.matchMedia('(max-width: 52rem)').matches);
}

// What it is doing now, in one line: the step, how long it has taken, what it has spent and
// the limit it stops at. Each is left out where it is not known.
// While nothing else changes, the time in the now line still moves.
function tickNow(run) {
  const shown = main().querySelector('.now-line');
  const fresh = nowLine(run);
  if (shown && fresh && shown.textContent !== fresh.textContent) {
    shown.textContent = fresh.textContent;
  }
}

function nowLine(run) {
  if (run.state !== 'working' || run.mine === false || queued(run)) return null;
  const parts = [];
  const current = list(run.steps).find((step) => step.status === 'working');
  if (current) parts.push(current.label);
  const began = list(run.workers).map((worker) => Date.parse(worker.started_at))
    .filter((stamp) => !Number.isNaN(stamp));
  if (began.length) parts.push(lasted((Date.now() - Math.min(...began)) / 1000));
  const spent = run.spent || {};
  if (given(spent.dollars) && Number(spent.dollars) >= 0.005) {
    parts.push(money(spent.dollars) + ' so far');
  }
  // The run's own limit, raised by every Carry on; Settings' only where the run says none.
  const limits = (view.setup && view.setup.limits) || {};
  const stopsAt = given(spent.stops_at) ? spent.stops_at : limits.training_dollars;
  if (given(stopsAt)) parts.push('stops at ' + money(stopsAt));
  return parts.length ? make('p', 'now-line', parts.join(' · ')) : null;
}

// Server-measured interval unions distinguish overlapping work from elapsed time.
function measuredTime(run) {
  const time = run.timing;
  if (!time) return null;
  const parts = [];
  if (given(time.elapsed_seconds)) parts.push(lasted(time.elapsed_seconds) + ' elapsed');
  parts.push(lasted(time.active_seconds) + ' actively working');
  parts.push(lasted(time.assistant_seconds) + ' total assistant time');
  if (time.incomplete) parts.push('earlier timing history is incomplete');
  return make('p', 'quiet measured-time', parts.join(' · '));
}

function researchActivity(run, controls = null) {
  const research = run.research_progress;
  if (!research || research.phase === 'complete') return null;
  if (typeof StudioResearch !== 'undefined') return StudioResearch.progress(research, {timing: run.timing, controls});
  const names = { investigate: 'Investigating', synthesize: 'Combining findings', review: 'Independent check' };
  const node = add(card(names[research.phase] || 'Research'),
    make('p', 'quiet', 'Completed research areas are kept for retry.'));
  const rows = make('ul', 'plain');
  const words = { waiting: 'Waiting', working: 'Working', kept: 'Evidence kept', failed: 'Needs retry' };
  for (const area of list(research.streams)) {
    add(rows, add(make('li', 'row'), make('span', 'row-text',
      list(area.questions).join(' · ') || 'Research area ' + area.id.slice(-1)),
    make('span', 'quiet', words[area.status] || 'Waiting')));
  }
  return add(node, rows, measuredTime(run), make('p', 'quiet',
    'Elapsed includes waiting and stopped time. Total assistant time adds overlapping jobs.'));
}

function money(dollars) {
  return '$' + Number(dollars).toFixed(2);
}

function lasted(seconds) {
  const whole = Math.round(Number(seconds));
  if (whole < 60) return count(whole, 'second', 'seconds');
  const minutes = Math.round(whole / 60);
  if (minutes < 60) return count(minutes, 'minute', 'minutes');
  return count(Math.floor(minutes / 60), 'hour', 'hours') + ' '
    + count(minutes % 60, 'minute', 'minutes');
}

function lower(text) {
  return String(text).charAt(0).toLowerCase() + String(text).slice(1);
}

function capital(text) {
  return String(text).charAt(0).toUpperCase() + String(text).slice(1);
}

// A word the runner uses for a kind or a state, as a person would write it.
function spoken(word) {
  return capital(String(word).replace(/[-_]+/g, ' '));
}

function given(value) {
  return value !== null && value !== undefined;
}

// --- talking to the server ---------------------------------------------------------

class PageError extends Error {
  constructor(kind, message, status) {
    super(message);
    this.kind = kind;
    this.status = status || 0;
  }
}

// One request to the server. With no answer at all, the page has lost touch with it.
async function reach(endpoint, options) {
  try {
    return await fetch('/api/' + endpoint, options);
  } catch (failure) {
    throw new PageError('stopped', noticeOf('stopped'));
  }
}

// What an answer says, where it can be read, and the refusal an answer that says no makes.
async function saidBy(response) {
  try {
    return await response.json();
  } catch (failure) {
    return null;
  }
}

function refusal(response, body) {
  const said = body && body.error ? String(body.error)
    : 'Training Studio gave no answer this page can read.';
  return new PageError(response.status === 403 ? 'refused' : 'failed', said, response.status);
}

async function call(endpoint, options) {
  const response = await reach(endpoint, options);
  const body = await saidBy(response);
  if (response.ok && body) return body;
  throw refusal(response, body);
}

function ask(endpoint, params) {
  const query = params ? '?' + new URLSearchParams(params).toString() : '';
  return call(endpoint + query, { headers: { [TOKEN_HEADER]: view.token }, cache: 'no-store' });
}

// One slide's picture, as its bytes. It is asked for like everything else that is read, with
// the key, which an address written into the page could not send.
async function picture(params) {
  const response = await reach('slide?' + new URLSearchParams(params).toString(),
    { headers: { [TOKEN_HEADER]: view.token }, cache: 'no-store' });
  if (!response.ok) throw refusal(response, await saidBy(response));
  let held = null;
  try {
    held = await response.blob();
  } catch (failure) {
    held = null;
  }
  if (!held) throw new PageError('failed', 'It did not arrive whole.');
  if (!/^image\/png\b/.test(held.type)) {
    throw new PageError('failed', 'What came back is not a picture.');
  }
  return held;
}

// The file's name as the runner sends it, in Content-Disposition's filename="…", else
// the name the caller passed, which always has its extension.
function sentName(response, fallback) {
  const said = response.headers && typeof response.headers.get === 'function'
    ? String(response.headers.get('Content-Disposition') || '') : '';
  const found = /filename="([^"\\/]+)"/.exec(said);
  return found ? found[1] : fallback;
}

async function downloadFile(path, params, fallback, pressed) {
  if (pressed.disabled) return;
  pressed.disabled = true;
  try {
    const response = await reach('download?' + new URLSearchParams({path, ...params}),
      {headers: {[TOKEN_HEADER]: view.token}, cache: 'no-store'});
    if (!response.ok) throw refusal(response, await saidBy(response));
    const name = sentName(response, fallback);
    const held = URL.createObjectURL(await response.blob());
    const link = make('a', 'offscreen', 'Download');
    link.href = held;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(held), 60000);
    toast('Downloaded ' + name + '.');
  } catch (failure) {
    toast(failure.message + ' Nothing was downloaded.');
  } finally {
    pressed.disabled = false;
  }
}

function send(endpoint, body, options = {}) {
  return call(endpoint, {
    method: 'POST',
    headers: { [TOKEN_HEADER]: view.token, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    cache: 'no-store',
    ...options,
  });
}

function notify(text) {
  byId('notice').textContent = text;
  byId('notice').hidden = !text;
}

function calm() {
  return Boolean(window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
}

// A short message that slides in at the bottom right, is read out, and leaves by itself.
// It is kept clear of the toolbar, so it never covers the main thing to do.
function toast(text) {
  const node = make('p', 'toast glass', text);
  byId('toasts').append(node);
  window.setTimeout(() => {
    node.classList.add('toast-leaving');
    window.setTimeout(() => node.remove(), calm() ? 0 : 260);
  }, 4200);
}

// --- copying ----------------------------------------------------------------------

function copyBySelection(text) {
  const holder = make('textarea', 'offscreen');
  holder.value = text;
  holder.readOnly = true;
  holder.setAttribute('aria-hidden', 'true');
  document.body.append(holder);
  holder.select();
  let copied = false;
  try {
    copied = document.execCommand('copy');
  } catch (failure) {
    copied = false;
  }
  holder.remove();
  return copied;
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (failure) {
    return copyBySelection(text);
  }
}

function copyButton(label, done, text, key) {
  return capsule(label, '', async () => {
    toast(await copy(text) ? done : 'Not copied. Select the text instead.');
  }, key);
}

// --- pictures of slides ------------------------------------------------------------------
// Each picture is fetched as bytes, kept in memory, and shown from there under an address
// that only this page holds. They are fetched one at a time: the one being looked at first,
// and each of the others when its place comes into view. Leaving the screen lets go of all.

// What says when a picture's place comes into view.
function watcher() {
  if (!view.watcher) {
    view.watcher = new IntersectionObserver((seen) => {
      for (const found of seen) {
        if (!found.isIntersecting) continue;
        view.watcher.unobserve(found.target);
        wantPicture(PLACES.get(found.target), false);
      }
    }, { rootMargin: '200px' });
  }
  return view.watcher;
}

// Put a picture in line to be fetched. `first` puts it at the head of the line.
function wantPicture(place, first) {
  let held = view.pictures.get(place.key);
  if (!held) {
    held = { state: 'wanted', where: place.where, url: '', says: '' };
    view.pictures.set(place.key, held);
  }
  if (held.state !== 'wanted') return;
  const at = view.wanted.indexOf(place.key);
  if (at >= 0 && !first) return;
  if (at >= 0) view.wanted.splice(at, 1);
  if (first) view.wanted.unshift(place.key);
  else view.wanted.push(place.key);
  fetchPictures();
}

async function fetchPictures() {
  if (view.fetching) return;
  view.fetching = true;
  try {
    while (view.wanted.length) {
      const key = view.wanted.shift();
      const held = view.pictures.get(key);
      if (!held) continue;
      held.state = 'fetching';
      let found = null;
      try {
        found = await picture({ path: view.path, ...held.where });
      } catch (failure) {
        held.says = failure.message;
      }
      // The screen was left meanwhile, or this picture is no longer on it: it is not kept.
      if (view.pictures.get(key) !== held) continue;
      held.state = found ? 'here' : 'failed';
      if (found) held.url = URL.createObjectURL(found);
      for (const node of document.querySelectorAll('.frame')) {
        if (PLACES.get(node).key === key) fillFrame(node);
      }
    }
  } finally {
    view.fetching = false;
  }
}

// What a picture's place shows: the picture once it is here, and words until then. A picture
// that cannot be had says so in its place, and never leaves a gap.
function fillFrame(node) {
  const place = PLACES.get(node);
  const held = view.pictures.get(place.key);
  const says = (className, text) => add(make('span', 'frame-says ' + className),
    make('span', 'offscreen', place.alt + '. '), text);
  if (held && held.state === 'here') {
    const image = make('img', 'picture');
    image.alt = place.alt;
    image.src = held.url;
    image.addEventListener('error', () => {
      node.replaceChildren(says('problem', 'What was fetched cannot be shown as a picture.'));
    });
    node.replaceChildren(image);
  } else if (held && held.state === 'failed') {
    const again = place.again ? button('Try this picture again', 'link', () => {
      view.pictures.delete(place.key);
      wantPicture(place, true);
      fillFrame(node);
      node.focus({ preventScroll: true });
    }, 'picture-again') : null;
    node.replaceChildren();
    add(node, says('problem', 'Its picture could not be fetched. ' + held.says
      + (again ? ' The deck itself is as it was.' : '')), again);
  } else {
    node.replaceChildren(says('quiet', 'Its picture is on its way.'));
  }
}

// The place a picture goes. `where` is what it is of, `alt` says so in words, and `mark`
// changes when a newer picture of the same thing is made. `about.first` is for the one being
// looked at, and `about.again` offers another try where one could not be fetched.
function pictureAt(where, alt, mark, about) {
  const spec = about || {};
  const node = make('span', 'frame');
  const place = { key: JSON.stringify([where, mark || '']), where, alt,
    again: Boolean(spec.again) };
  PLACES.set(node, place);
  if (place.again) node.tabIndex = -1;
  fillFrame(node);
  // A browser that cannot say when a place comes into view is asked for each in turn.
  if (spec.first || typeof IntersectionObserver === 'undefined') wantPicture(place, spec.first);
  else if (!view.pictures.has(place.key)) watcher().observe(node);
  return node;
}

// A picture that nothing on the screen shows any more, such as a section's earlier preview,
// is let go.
function tidyPictures() {
  const shown = new Set(Array.from(document.querySelectorAll('.frame'))
    .map((node) => PLACES.get(node).key));
  for (const [key, held] of Array.from(view.pictures)) {
    if (shown.has(key)) continue;
    if (held.url) URL.revokeObjectURL(held.url);
    view.pictures.delete(key);
  }
  view.wanted = view.wanted.filter((key) => shown.has(key));
}

// Leaving a screen lets go of every picture it held, and stops waiting for the rest.
function letGo() {
  for (const held of view.pictures.values()) {
    if (held.url) URL.revokeObjectURL(held.url);
  }
  view.pictures = new Map();
  view.wanted = [];
  if (view.watcher) view.watcher.disconnect();
}

// --- the window: sidebar, toolbar, sheet ------------------------------------------------

function show(screen, where, replace) {
  const next = { screen, path: (where && where.path) || null,
    artifact: (where && where.artifact) || null };
  if (replace) {
    window.history.replaceState(next, '');
  } else {
    window.history.pushState(next, '');
    view.pushed += 1;
  }
  open(next);
}

function back() {
  if (view.pushed > 0) {
    window.history.back();
    return;
  }
  const up = { gate: homeOf(view.path), index: homeOf(view.path), outline: 'run', new: 'home',
    setup: 'settings' };
  show(up[view.screen] || 'trainings', { path: view.path }, true);
}

// Change screens with the browser's own transition where it has one, and a fade where not.
function swap(update) {
  if (document.startViewTransition && !calm()) {
    const moving = document.startViewTransition(update);
    // A transition that is overtaken by the next one is dropped; the screen is drawn anyway.
    moving.ready.catch(() => {});
    moving.finished.catch(() => {});
    return moving.updateCallbackDone;
  }
  const done = update();
  const holder = main();
  holder.classList.remove('arrive');
  holder.classList.add('arrive');
  return done;
}

function open(next) {
  if (view.screen === 'run' && view.path && (next.screen !== 'run' || next.path !== view.path)
      && typeof shareDesk === 'function') shareDesk(view.path);
  view.screen = unset() ? 'setup' : next.screen || 'home';
  view.path = next.path || null;
  view.artifact = next.artifact || null;
  view.gate = null;
  view.newer = null;
  view.training = null;
  view.after = null;
  view.sheet = '';
  view.pane = 0;
  view.drawn = '';
  view.run = null;
  view.form = null;
  view.steered = '';
  view.barred = '';
  view.deciding = null;
  view.doomed = null;
  view.leaving = null;
  view.beside = null;
  view.unadded = '';
  view.undone = '';
  view.copying = false;
  view.uncopied = '';
  view.slide = 0;
  view.viewer = null;
  view.unmoved = {};
  view.unrestored = {};
  view.recorded = '';
  letGo();
  view.turn += 1;
  frame();
  const current = PARENTS[view.screen] || view.screen;
  for (const [id, screen] of NAV) {
    if (current === screen) byId(id).setAttribute('aria-current', 'page');
    else byId(id).removeAttribute('aria-current');
  }
  drawSheet();
  swap(() => draw(true));
}

// The toolbar: where you are, the way back, and the main thing to do here.
function toolbar(spec) {
  setTitle(spec.name === undefined ? spec.title : spec.name);
  byId('title').textContent = spec.title;
  // A title too long for two lines is cut there. Its whole text is a pointer away.
  byId('title').title = spec.title;
  const above = byId('above');
  above.replaceChildren(...list(spec.above).filter(Boolean));
  above.hidden = !above.childNodes.length;
  const lead = byId('toolbar-lead');
  lead.replaceChildren();
  if (spec.back) {
    const node = button('', 'button button-round shine', back, 'back');
    node.setAttribute('aria-label', 'Back');
    add(lead, add(node, icon('back')));
  }
  byId('actions').replaceChildren(...ordered(spec.actions));
}

// A toolbar's actions: the one filled action first, then the rest, each quiet. A screen
// passes at most one filled action. On a phone they wrap under the title.
function ordered(actions) {
  actions = list(actions).filter(Boolean);
  const filled = (node) => Boolean(node.classList && node.classList.contains('button-filled'));
  const lead = actions.filter(filled);
  const rest = actions.filter((node) => !filled(node));
  for (const node of rest) {
    const control = node.tagName === 'DETAILS' ? node.querySelector('summary') : node;
    if (control && control.classList && control.classList.contains('button')
        && !control.classList.contains('button-danger')) control.classList.add('button-quiet');
  }
  return [...lead, ...rest];
}

// A screen's header: the one sentence that says what the screen is for, and the view's own
// actions in a bar beside it.
function pageHead(lede, beside) {
  const actions = list(beside).filter(Boolean);
  return add(make('div', 'page-head'), typeof lede === 'string' ? make('p', 'lede', lede) : lede,
    actions.length ? add(make('div', 'bar'), ...actions) : null);
}

// Put a screen in place. A screen drawn again, because something changed, keeps the
// reader's place: what had the focus has it again, and what was open stays open.
function place(spec, nodes, fresh) {
  const holder = main();
  const active = document.activeElement;
  const focused = !fresh && active && active.dataset ? active.dataset.key : '';
  const opened = fresh ? [] : Array.from(holder.querySelectorAll('details'))
    .filter((node) => node.open).map((node) => node.dataset.key);
  toolbar(spec);
  holder.replaceChildren(...nodes.filter(Boolean));
  for (const node of holder.querySelectorAll('details')) {
    if (opened.includes(node.dataset.key)) node.open = true;
  }
  if (fresh) {
    window.scrollTo(0, 0);
    // A sheet opened on this screen keeps the focus: it is the only thing that can be reached.
    if (!view.sheet) byId('title').focus({ preventScroll: true });
    return;
  }
  if (focused) focusKey(focused);
}

function focusKey(key) {
  for (const node of document.querySelectorAll('[data-key]')) {
    if (node.dataset.key === key && !node.disabled) {
      node.focus({ preventScroll: true });
      return true;
    }
  }
  return false;
}

// The tab's title leads with how many things need the person, so it shows from another tab.
// Versions Home tells of count as one more thing.
function setTitle(name) {
  if (name !== undefined) view.named = name;
  const needs = view.needs + (versionsNotice() ? 1 : 0);
  const waiting = needs ? '(' + needs + ') ' : '';
  document.title = waiting + (view.named ? view.named + ' · ' : '') + 'Training Studio';
  const badge = byId('needs-count');
  badge.replaceChildren(String(needs), make('span', 'offscreen',
    needs === 1 ? ' thing needs you' : ' things need you'));
  badge.hidden = !needs;
}

// Everything a list screen is drawn from. When none of it has changed, nothing is redrawn.
function signature() {
  return JSON.stringify([view.listing, view.asks, ...around()]);
}

// What a list screen's parts are drawn from, apart from the trainings themselves.
function around() {
  return [view.computer, view.checking, alerts(), view.setup, view.sharing, view.status,
    view.unnotified, view.fetching, view.fetched, Boolean(view.runner), view.lookRefused,
    view.brandRefused, view.savingBrand];
}

function draw(fresh) {
  if (view.screen === 'gate') return drawGate(fresh);
  if (view.screen === 'training') return drawTraining(fresh);
  if (view.screen === 'run') return drawRun(fresh);
  if (view.screen === 'outline') return drawOutline(fresh);
  if (view.screen === 'index') return drawIndex(fresh);
  if (view.screen === 'published' && view.runner) return drawPublished(fresh);
  if (view.screen === 'setup' && view.setup) return drawSetup(fresh);
  const titles = { home: 'Home', trainings: 'Trainings', status: 'Status', settings: 'Settings',
    setup: 'Set-up', new: 'New training', published: 'Published' };
  if (!view.listing) {
    place({ title: titles[view.screen] || 'Home' },
      [make('p', 'quiet', 'Reading your trainings.')], fresh);
    return undefined;
  }
  // Only the runner has these screens. On the plain desk a stray visit lands on home.
  if (view.screen === 'setup' || (['new', 'published'].includes(view.screen) && !view.runner)) {
    show('home', null, true);
    return undefined;
  }
  if (view.screen === 'new') return drawNew(fresh);
  view.drawn = signature();
  if (view.screen === 'trainings') return drawTrainings(fresh);
  if (view.screen === 'status') return drawStatus(fresh);
  if (view.screen === 'settings') return drawSettings(fresh);
  return drawHome(fresh);
}

// --- the sheet: it drops from the toolbar, and a decision is confirmed in it ---------------

function sheetTitle(text) {
  const node = make('h2', 'sheet-title', text);
  node.id = 'sheet-title';
  return node;
}

function openSheet(kind, opener) {
  return () => {
    for (const menu of document.querySelectorAll('.menu')) menu.open = false;
    view.sheet = kind;
    view.opener = opener;
    // The screen under the sheet gives up its filled button while the sheet holds one.
    repaintUnder(true);
    drawSheet();
    const field = byId('note-text');
    (field || byId('sheet')).focus();
  };
}

function closeSheet() {
  const opener = view.opener;
  view.sheet = '';
  view.after = null;
  view.deciding = null;
  view.doomed = null;
  view.leaving = null;
  view.doomedMany = null;
  view.leavingMany = null;
  view.redesigning = null;
  view.picture = null;
  drawSheet();
  repaintUnder();
  if (!focusKey(opener)) byId('title').focus({ preventScroll: true });
}

// The screen under a sheet, drawn again as a sheet opens or is put away: while one is open
// it holds the one filled button, so the screen under it gives its own up.
function repaintUnder(opening) {
  if (opening && (view.gate || outlined() || view.screen === 'training')) return;
  if (view.gate) paintGate(false);
  else if (view.screen === 'run' && view.run) paintRun(false);
  else if (outlined()) paintOutline(false);
  else if (view.screen === 'training' && view.training) paintTraining(false);
  else if (['home', 'trainings'].includes(view.screen) && view.listing) draw(false);
}

function problemLine() {
  const node = make('p', 'problem');
  node.id = 'sheet-problem';
  node.setAttribute('role', 'alert');
  node.hidden = true;
  return node;
}

// What a sheet's decision is sent with: a gate's own, or the one for what a deck says.
function decider() {
  return outlined() ? decideOutline : decide;
}

function confirmSheet(kind) {
  const spec = CONFIRMS[kind];
  const problem = problemLine();
  const confirm = capsule(spec.send, 'filled', () => decider()(kind, '', problem, confirm),
    'send');
  const about = outlined() ? [outlineLabel(view.run.outline), view.run.outline.design
    ? OUTLINE_APPROVES_DESIGN : OUTLINE_APPROVES]
    : [lower(view.gate.label), spec.says];
  // A deck is approved as it is. What the review still finds in it is said before it is.
  const left = kind === 'approve' && view.gate ? serious(view.gate).length : 0;
  return [sheetTitle(spec.title(about[0])), make('p', '', about[1]),
    left ? state('late', 'The review still lists ' + count(left, 'serious finding',
      'serious findings') + '. Approving takes the deck as it is.') : null, problem,
    add(make('div', 'bar'), confirm, capsule('Cancel', 'quiet', closeSheet, 'cancel'))]
    .filter(Boolean);
}

// A note is kept for the training, the file and the decision it was typed for.
function noteKey(kind) {
  return [view.path, view.deciding || view.artifact || view.screen, kind].join('\n');
}

function noteSheet(kind) {
  const spec = FORMS[kind];
  const form = make('form', 'note');
  form.noValidate = true;
  const label = make('label', 'note-label', spec.label);
  label.htmlFor = 'note-text';
  const field = make('textarea', 'note-field');
  field.id = 'note-text';
  field.rows = 3;
  field.maxLength = 10000;
  field.dataset.key = 'note';
  field.setAttribute('aria-describedby', 'note-hint sheet-problem');
  // What was typed before the sheet was put away is here again.
  const key = noteKey(kind);
  field.value = view.notes[key] || '';
  field.addEventListener('input', () => {
    view.notes[key] = field.value;
  });
  // What a change writes again, and what that took the last time, said before it is sent.
  const price = outlined() ? view.run.outline.redo : view.gate && view.gate.redo;
  const researchPrice = !outlined() && view.gate && view.gate.artifact === 'research' && view.gate.research_price;
  const redo = kind === 'revise' && researchPrice ? ' ' + researchPrice.words
    : kind === 'revise' && price ? ' ' + price.says : '';
  // A change to a deck draws it again whole: said before the price.
  const decked = kind === 'revise' && !outlined() && view.gate
    && String(view.gate.artifact || '').split('@')[0] === 'deck';
  const hint = make('p', 'quiet', (decked ? 'A change to the deck writes its outline again and '
    + 'draws every slide again.' : runOf(view.path) ? spec.hint.replace('Your assistant makes',
    'Training Studio makes') : spec.hint) + redo);
  hint.id = 'note-hint';
  // At the research stop, the sources may be read again: the whole research, brought up to
  // date. It is off unless asked for, and says what it costs.
  const refreshing = kind === 'revise' && researchPrice ? { on: false } : null;
  const refresh = refreshing ? add(make('div', 'field'),
    chip('Bring the evidence up to date', false, (on) => { refreshing.on = on; }, 'refresh'),
    make('p', 'quiet field-hint', researchPrice.refresh || 'Re-reads the sources and checks '
      + 'the report again: about as long and as costly as the research was.')) : null;
  const problem = problemLine();
  const submit = submitButton(spec.send, 'send');
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const text = field.value.trim();
    if (refreshing && refreshing.on) {
      decide(kind, text, problem, submit, { refresh: true });
      return;
    }
    if (spec.needed && !text) {
      // Refused here, beside the control, before anything is sent.
      problem.textContent = spec.needed;
      problem.hidden = false;
      field.setAttribute('aria-invalid', 'true');
      field.focus();
      return;
    }
    decider()(kind, text, problem, submit);
  });
  add(form, label, field, hint, refresh, problem,
    add(make('div', 'bar'), submit, capsule('Cancel', 'quiet', closeSheet, 'cancel')));
  return [sheetTitle(spec.title), form];
}

function afterSheet() {
  const done = view.after;
  const next = done.next;
  const nodes = [sheetTitle('Done'), make('p', '', done.said)];
  // A training that runs on its own carries on from here, and its run is the place to watch.
  // Decided from the run itself, that is where the person already is.
  const watch = runOf(view.path) && view.screen !== 'run' ? capsule('Watch it carry on', '',
    () => show('run', { path: view.path }), 'watch') : null;
  if (next) {
    // What is next is a gate to review, what a deck says to review, or a training to open.
    const to = next.artifact ? 'gate' : next.outline ? 'outline' : homeOf(next.path);
    nodes.push(make('p', 'quiet', 'Next: ' + next.title + '. ' + next.sentence));
    nodes.push(add(make('div', 'bar'),
      capsule(next.artifact || next.outline ? 'Review the next one' : 'Open the next one',
        'filled', () => show(to, { path: next.path, artifact: next.artifact }), 'next'),
      watch, capsule('Stay here', 'quiet', closeSheet, 'cancel')));
  } else {
    nodes.push(make('p', 'quiet', 'Nothing else needs you right now.'));
    nodes.push(add(make('div', 'bar'),
      capsule('Back to home', 'filled', () => show('home'), 'next'),
      watch, capsule('Stay here', 'quiet', closeSheet, 'cancel')));
  }
  return nodes;
}

function drawSheet() {
  const holder = byId('sheet');
  const shown = view.after || (view.sheet && (view.gate || view.deciding || outlined()
    || TEAM_SHEETS.includes(view.sheet)
    || (view.sheet === 'new' && view.draft) || (view.sheet === 'picture' && view.picture)
    || ['delete', 'bulk-delete', 'companions', 'upgrade', 'redesign', 'brand', 'copy-choice',
      'update-research', 'stop-run', 'desk-migration'].includes(view.sheet)
    || (DESK_SHEETS.includes(view.sheet) && view.run)
    || (view.sheet === 'approve-combined' && view.run && view.run.review)));
  holder.hidden = !shown;
  // While a sheet is open it holds the one filled button, so the toolbar's are put away.
  byId('actions').hidden = Boolean(shown);
  // And it is the only thing that can be reached: everything behind it is inert until it is
  // put away, by its own buttons or by Escape.
  for (const id of ['main', 'sidebar', 'toolbar']) byId(id).inert = Boolean(shown);
  if (!shown) {
    holder.replaceChildren();
    return;
  }
  let body;
  if (view.after) body = afterSheet();
  else if (view.sheet === 'desk-migration') body = trainingMigrationSheet();
  else if (view.sheet === 'delete') body = deleteSheet();
  else if (view.sheet === 'bulk-delete') body = bulkDeleteSheet();
  else if (view.sheet === 'new') body = newSheet();
  else if (view.sheet === 'picture') body = pictureSheet();
  else if (view.sheet === 'companions') body = updateSheet();
  else if (view.sheet === 'upgrade') body = upgradeSheet();
  else if (view.sheet === 'redesign') body = redesignSheet();
  else if (view.sheet === 'brand') body = brandSheet();
  else if (view.sheet === 'copy-choice') body = copyChoiceSheet();
  else if (view.sheet === 'update-research') body = updateResearchSheet();
  else if (view.sheet === 'stop-run') body = stopSheet();
  else if (view.sheet === 'approve-combined') body = combinedConfirm();
  else if (DESK_SHEETS.includes(view.sheet)) body = deskSheet(view.sheet);
  else if (TEAM_SHEETS.includes(view.sheet)) body = teamSheet(view.sheet);
  else if (FORMS[view.sheet]) body = noteSheet(view.sheet);
  else body = confirmSheet(view.sheet);
  holder.replaceChildren(...body);
  if (view.sheet === 'new') paintAgents();
}

async function decide(decision, note, problem, pressed, more) {
  if (view.busy) return;
  const turn = view.turn;
  const noted = noteKey(decision);
  view.busy = true;
  pressed.disabled = true;
  // At a gate, what is decided is what is being read. A sheet opened from a run names it.
  const body = { path: view.path, artifact: view.deciding || view.artifact, decision,
    ...(more || {}) };
  if (note) body.note = note;
  if (view.gate && view.gate.sha256) body.seen = view.gate.sha256;
  let done;
  try {
    done = await send('decide', body);
  } catch (failure) {
    problem.textContent = failure.message;
    problem.hidden = false;
    pressed.disabled = false;
    view.busy = false;
    return;
  }
  // A note that was sent is not offered again.
  delete view.notes[noted];
  view.busy = false;
  if (turn !== view.turn) return;
  // Keep a runner approval in this training. The explicit confirmation was the decision;
  // a second dialog should not make the person choose where to go afterward.
  if (decision === 'approve' && runOf(view.path)) {
    toast(done.said);
    show('run', { path: view.path }, true);
    refresh();
    return;
  }
  view.after = done;
  view.sheet = '';
  view.deciding = null;
  try {
    if (view.gate) {
      // Draw the gate as it now stands, so nothing on it still says "waiting".
      view.gate = await ask('gate', { path: view.path, artifact: view.artifact });
      view.newer = null;
      if (turn === view.turn) paintGate(false);
    } else {
      // Decided from a run, which is read again below and then shows what follows.
      if (view.run) paintRun(false);
      drawSheet();
    }
  } catch (failure) {
    drawSheet();
  }
  if (turn !== view.turn) return;
  byId('sheet').focus();
  refresh();
}

async function moveApproval(path, mode) {
  await send('approval', { path, mode });
  toast(mode === 'page' ? 'Decisions for this training are now made on this page.'
    : 'Decisions for this training are now made in the conversation.');
}

// Where a training is decided: a control whose thumb slides before the answer is back,
// and slides home again if the answer is no. Why it was no is said beside it, and stays.
function approvalControl(path, title, approval, after) {
  const problem = alertLine('approval-' + path.replace(/[^\w-]/g, '-') + '-problem');
  say(problem, view.unmoved[path] || '');
  const control = segmented('Where ' + title + ' is decided',
    ['In the conversation', 'On this page'], approval === 'page' ? 1 : 0,
    async (index, node) => {
      if (view.busy) return;
      view.busy = true;
      delete view.unmoved[path];
      say(problem, '');
      slide(node, index);
      try {
        await moveApproval(path, index ? 'page' : 'chat');
        view.busy = false;
        await after();
      } catch (failure) {
        slide(node, index ? 0 : 1);
        view.unmoved[path] = failure.message;
        say(problem, failure.message);
      }
      view.busy = false;
    }, 'approval ' + path);
  control.setAttribute('aria-describedby', problem.id);
  return add(document.createDocumentFragment(), control, problem);
}

// --- home -------------------------------------------------------------------------

function greeting() {
  const hour = new Date().getHours();
  const hello = hour < 12 ? 'Good morning.' : hour < 18 ? 'Good afternoon.' : 'Good evening.';
  const things = view.needs < COUNTED.length ? COUNTED[view.needs]
    : view.needs + ' things need';
  return hello + ' ' + things + ' you' + (view.needs ? '.' : ' right now.');
}

// A training that runs on its own opens on its run; any other opens on its own view.
function openTraining(training) {
  return () => show(watched(training) ? 'run' : 'training', { path: training.path });
}

function reviewAction(training) {
  const waiting = training.waiting || {};
  const next = training.standing && training.standing.next;
  // A desk training opens on its desk at the person's next action: its level, material and,
  // for a review finding, its slide. Opening it starts nothing.
  if (!waiting.artifact && next && typeof deskGoTo === 'function') {
    return () => {
      deskGoTo(deskHeld(training.path), training.standing, null);
      show('run', { path: training.path });
    };
  }
  return waiting.artifact
    ? () => show('gate', { path: training.path, artifact: waiting.artifact })
    : openTraining(training);
}

// A run says whether it is working. Only where there is no run is it guessed, from how
// lately the training changed.
function working(training) {
  if (training.run) return training.run.state === 'working';
  return training.state === 'in-progress'
    && Date.now() - Date.parse(training.touched_at) < WORKING;
}

// One sentence for a training in a list. A run says what it is doing now; a gate says what
// is waiting. Where the deck is all that is left, that is the one thing said.
function saysOf(training) {
  // Of a training a teammate runs, the runner says what was last shared and when.
  if (elsewhere(training)) return (training.run && training.run.sentence) || training.sentence;
  // A desk training is said from the one standing its desk shows too.
  if (training.standing) return training.standing.sentence;
  if (deckLeft(training)) return DECK_LEFT;
  const atGate = training.state === 'needs-you' && (training.waiting || {}).artifact;
  return (training.run && !atGate && training.run.sentence) || training.sentence;
}

function needsRow(training, index) {
  const waiting = training.waiting || {};
  const asked = view.asks[training.path] || {};
  const title = training.title || 'Untitled';
  const text = add(make('div', 'row-text'), make('p', 'row-title', title));
  const says = asked.problem ? asked.problem.what : saysOf(training);
  if (asked.question) {
    add(text, questionBox(training.path, title, asked.question, '', 'answer-' + index));
  } else {
    add(text, make('p', 'row-says', says));
    if (waiting.artifact && waiting.question && !asked.problem) {
      add(text, make('p', 'row-quote', asker(training.path) + waiting.question));
    }
  }
  add(text, noticeLine(training));
  const next = training.standing && training.standing.next;
  const review = (waiting.artifact || next) && !asked.question && !asked.problem;
  // What a deck says is reviewed on a screen of its own, reached from here like any gate.
  const outline = !waiting.artifact && readsOutline(asked);
  const go = capsule(review || outline ? 'Review' : 'Open', asked.question ? 'quiet' : '',
    outline ? () => show('outline', { path: training.path })
      : review ? reviewAction(training) : openTraining(training), 'needs ' + training.path);
  go.setAttribute('aria-label', go.textContent + ': ' + title + '. '
    + (asked.question ? asked.question.text : says));
  return add(make('li', 'row row-needs'), bead(asked.problem ? 'late' : 'review'), text,
    withDelete(go, training));
}

function quietRow(training, kind) {
  const text = add(make('div', 'row-text'),
    make('p', 'row-title', training.title || 'Untitled'));
  if (kind === 'in-progress') add(text, beads(training.stages, true));
  // A run that is not working says so: paused, stopped, or finished as far as it goes here.
  // A desk training says its own standing instead: a finished writing job is not Ready.
  if (training.standing && kind === 'in-progress') {
    add(text, state(...standingOf(training)));
  } else if (training.run && training.run.state !== 'working' && kind === 'in-progress'
      && !deckLeft(training)) {
    add(text, state(...runWords(training.run)));
  }
  add(text, make('p', 'row-says', saysOf(training)), whoLine(training), noticeLine(training));
  const go = capsule('Open', 'quiet', openTraining(training), 'open ' + training.path);
  go.setAttribute('aria-label', 'Open ' + (training.title || 'Untitled'));
  const row = make('li', working(training) ? 'row working' : 'row');
  return add(row, kind === 'finished' ? bead('done') : null, text, withDelete(go, training));
}

function brokenRow(training) {
  const text = add(make('div', 'row-text'),
    make('p', 'row-title', training.title || 'Untitled'),
    make('p', 'row-says', 'Its record cannot be read: ' + training.error),
    pathInto(make('p', 'path'), training.path));
  const go = capsule('Open', 'quiet', openTraining(training), 'open ' + training.path);
  go.setAttribute('aria-label', 'Open ' + (training.title || 'Untitled'));
  return add(make('li', 'row'), bead('off'), text, go);
}

// A card with a row for each training, as a part of its screen. A row is built again only
// when what it is drawn from has changed, so the others keep their place and their focus.
function rows(title, trainings, build, className) {
  if (!trainings.length) return null;
  return ['rows ' + title, [className], () => add(card(title, className), make('ul', 'rows')),
    (node) => fit(node.querySelector('.rows'), trainings.map((training, index) => [
      'row ' + training.path, [training, index, view.asks[training.path] || null,
        working(training), unclaimed(training)], () => build(training, index)]))];
}

// How a training is started, as the invitation and the Start a training card say it.
const START_SAYS = 'Say what it is about and who it is for. Training Studio does the '
  + 'research and writes the blueprint, the learner guide, the brief and the practice '
  + 'scenarios on its own, and puts each on its desk for you to edit and mark ready.';
const ASK_SAYS = 'Make a folder for your topic, start your assistant in that folder, and ask '
  + 'for the training in a sentence, for example:';
const ASK_SENTENCE = 'Use training-studio to build a 101 training on rolling restarts.';
const HOME_LEDE = 'What needs you comes first, then trainings in progress, then ways to start '
  + 'one.';

// Home's way to start another: with the runner, New training; without it, what to ask the
// assistant.
function startCard() {
  const node = card('Start a training');
  if (view.runner) {
    return add(node, make('p', '', START_SAYS),
      add(make('div', 'bar'), newButton('', 'start-new')));
  }
  return add(node, make('p', '', ASK_SAYS), make('p', 'sentence', ASK_SENTENCE));
}

function invitation() {
  const node = make('section', 'card shine invite');
  if (view.runner) {
    return add(node,
      make('h2', 'invite-title', 'Start your first training'),
      make('p', '', START_SAYS),
      // While the sheet is open it holds the one filled button.
      add(make('div', 'bar'), newButton(view.sheet ? '' : 'filled')),
      make('p', 'quiet', 'It takes three short steps, and this page tells you each time it '
        + 'needs you.'));
  }
  return add(node,
    make('h2', 'invite-title', 'Start your first training'),
    make('p', '', ASK_SAYS),
    make('p', 'sentence', ASK_SENTENCE),
    make('p', 'quiet', 'It appears here as soon as it exists, and this page tells you each '
      + 'time it needs you.'));
}

function alerts() {
  return typeof Notification === 'undefined' ? 'none' : Notification.permission;
}

function computerLine() {
  const node = make('p', 'foot-line');
  const result = view.computer;
  if (!result) {
    add(node, make('span', '', 'This computer has not been checked yet.'));
  } else if (result.ready) {
    add(node, state('done', 'This computer is ready.'));
  } else {
    add(node, state('late', count(list(result.wrong).length, 'thing needs', 'things need')
      + ' putting right on this computer.'));
  }
  return add(node, button(result ? 'See the details' : 'Check it on the status screen',
    'link', () => show('status'), 'computer'));
}

// The trainings in one state. One a teammate runs is theirs to decide, so it is never among
// what needs this person, and is listed apart.
function pick(kind) {
  return view.listing.filter((training) => !training.error && training.state === kind
    && !elsewhere(training));
}

function drawHome(fresh) {
  const all = view.listing;
  const first = pick('needs-you')[0];
  const asked = first ? view.asks[first.path] : null;
  const next = first && !(first.waiting || {}).artifact && first.standing
    && first.standing.next;
  const gate = first && ((first.waiting || {}).artifact || next) && !asked;
  const outline = first && !(first.waiting || {}).artifact && readsOutline(asked);
  const lead = !first ? null : outline ? capsule('Review ' + outlineLabel(asked.outline),
    'filled', () => show('outline', { path: first.path }), 'lead')
    : capsule(gate ? (next ? next.label : 'Review ' + first.waiting.label)
      : 'Open ' + (first.title || 'Untitled'),
      'filled', gate ? reviewAction(first) : openTraining(first), 'lead');
  // With the runner, one button starts a new training. It is the filled one when nothing
  // needs the person first.
  const start = view.runner && all.length ? newButton(lead ? '' : 'filled') : null;
  const said = greeting();
  const parts = [['greeting', [said], () => make('p', 'large-title', said)],
    ['head', [], () => pageHead(HOME_LEDE)]];
  const setup = [['updates', [upkeepOf()], updatesCard],
    ['studios', studiosMark(), studiosHomeCard]];
  if (!all.length) {
    parts.push(['invite', [Boolean(view.runner), Boolean(view.sheet)], invitation], ...setup);
  } else {
    parts.push(
      rows('Needs you', pick('needs-you'), needsRow, 'card-needs'),
      rows('In progress', pick('in-progress'), (training) => quietRow(training, 'in-progress')),
      rows('Run by your teammates', teammates(), teamRow),
      ['start', [Boolean(view.runner)], startCard],
      ...setup,
      rows('Finished', pick('finished'), (training) => quietRow(training, 'finished')),
      rows('Cannot be read', all.filter((training) => training.error), brokenRow));
  }
  parts.push(['foot', around(),
    () => add(make('footer', 'foot'), computerLine(), sharingLine(), fetchLine())]);
  placeParts({ title: 'Home', name: '', actions: [start, lead],
    mark: ['Home', first ? [first.path, first.title, first.waiting] : null, asked || null,
      Boolean(start), Boolean(lead)] }, parts, fresh);
}

// --- trainings ---------------------------------------------------------------------

// Where a training stands, as the Trainings list filters it.
const STANDS = [['', 'Any'], ['needs-you', 'Needs you'], ['in-progress', 'In progress'],
  ['finished', 'Finished'], ['teammates', 'Run by your teammates'],
  ['unreadable', 'Cannot be read']];

// A list's filters, as they were last set on this page.
function filtersOf(name, empty) {
  if (!view.filters[name]) view.filters[name] = { ...empty };
  return view.filters[name];
}

// What is ticked on a list. Ticks stay through filter changes.
function tickedOf(name) {
  if (!view.ticked[name]) view.ticked[name] = new Set();
  return view.ticked[name];
}

function standsAt(training, wanted) {
  if (wanted === 'unreadable') return Boolean(training.error);
  if (training.error) return false;
  if (wanted === 'teammates') return elsewhere(training);
  return training.state === wanted && !elsewhere(training);
}

function matching(training) {
  const held = filtersOf('trainings', { text: '', stands: '' });
  if (held.stands && !standsAt(training, held.stands)) return false;
  const text = String(held.text || '').toLowerCase();
  if (!text) return true;
  return [training.title, training.error || saysOf(training), training.sentence,
    training.driver ? nameOf(training.driver) : '']
    .some((words) => String(words || '').toLowerCase().includes(text));
}

// Whether the runner drives a training and this computer may delete it. Only one that
// may is offered for deletion, one at a time or ticked with others.
function mayDelete(training) {
  return Boolean(!training.error && training.run && deletable({ mine: training.mine,
    driver: training.driver, finished: training.run.state === 'done' }));
}

// Ticking one more, or one fewer, draws the list again; the bar follows.
function flipTick(name, paths, on) {
  const ticked = tickedOf(name);
  for (const path of paths) {
    if (on) ticked.add(path);
    else ticked.delete(path);
  }
  draw(false);
}

function trainingCard(training) {
  const node = make('li', 'card shine' + (working(training) ? ' working' : ''));
  const title = training.title || 'Untitled';
  add(node, make('h2', 'card-title', title));
  const go = capsule('Open', '', openTraining(training), 'open ' + training.path);
  go.setAttribute('aria-label', 'Open ' + title);
  if (training.error) {
    return add(node, state('off', 'Cannot be read'), make('p', 'row-says', training.error),
      add(make('div', 'bar'), add(make('span', 'quiet'), when(training.touched_at)), go));
  }
  if (view.runner && mayDelete(training)) {
    const pick = window.StudioLists.tick({ id: 'tick-' + training.path, label: 'Select',
      on: tickedOf('trainings').has(training.path),
      flip: (on) => flipTick('trainings', [training.path], on) });
    pick.querySelector('input').setAttribute('aria-label', 'Select ' + title);
    node.append(pick);
  }
  const [shape, words] = standingOf(training);
  if (levelsText(training.levels)) add(node, make('p', 'quiet', levelsText(training.levels)));
  return add(node, beads(training.stages, true), state(shape, words),
    lastOr(training, 'row-says'), whoLine(training), noticeLine(training),
    add(make('div', 'bar'), add(make('span', 'quiet'), 'Changed ', when(training.touched_at)),
      go, deleteButton(training)));
}

// What is typed in a list's search box is kept as it is typed, and applied on Search.
function keepTyped(row, held) {
  const box = row.querySelector('input');
  if (box) box.addEventListener('input', () => { held.draft = box.value; });
  return row;
}

function trainingFilters() {
  const held = filtersOf('trainings', { text: '', stands: '' });
  // Teammates' trainings and ones that cannot be read are offered only where there are any.
  const offered = STANDS.filter(([value]) => (value !== 'teammates' || teamSpace()
    || teammates().length) && (value !== 'unreadable'
    || view.listing.some((training) => training.error)) || value === held.stands);
  return keepTyped(window.StudioLists.filterRow({ key: 'trainings',
    search: { id: 'text', label: 'Search', value: held.draft === undefined ? held.text
      : held.draft, hint: 'By its title, what it says or who runs it' },
    choices: [{ id: 'stands', label: 'Where it stands', options: offered, value: held.stands }],
    open: Boolean(view.filtersOpen.trainings),
    changed: (name, value) => { held[name] = value; draw(false); },
    searched: (text) => { held.text = text; held.draft = text; draw(false); },
    toggled: (open) => { view.filtersOpen.trainings = open; } }), held);
}

function drawTrainings(fresh) {
  const parts = [];
  if (!view.listing.length) {
    parts.push(['invite', [Boolean(view.runner), Boolean(view.sheet)], invitation]);
  } else {
    const said = count(view.listing.length, 'training', 'trainings')
      + ' on this computer, the one that changed last first.';
    const held = filtersOf('trainings', { text: '', stands: '' });
    const ticked = tickedOf('trainings');
    // A tick is kept only for a training that is still here and may still be deleted.
    const deletableNow = new Set(view.listing.filter(mayDelete).map((training) => training.path));
    for (const path of [...ticked]) if (!deletableNow.has(path)) ticked.delete(path);
    const shown = view.listing.filter(matching);
    const tickable = view.runner ? shown.filter(mayDelete).map((training) => training.path) : [];
    const picked = [...ticked];
    parts.push(['head', [said], () => pageHead(said)],
      ['filters', [held.text, held.stands, Boolean(view.filtersOpen.trainings)],
        trainingFilters],
      ['selection', [picked, tickable], () => window.StudioLists.selectionBar({
        ticked, shown: tickable, noun: ['training', 'trainings'], key: 'trainings-selection',
        actions: [{ label: 'Delete ' + count(ticked.size, 'training', 'trainings'),
          kind: 'danger', run: askBulkDelete, key: 'bulk-delete' }],
        selectShown: () => flipTick('trainings', tickable, true),
        clear: () => flipTick('trainings', [...ticked], false) })],
      ['heading', [shown.length, view.listing.length, tickable, picked], () => add(
        make('div', 'panel-heading'),
        make('p', 'quiet', shown.length + ' of ' + count(view.listing.length, 'training',
          'trainings') + (view.listing.length === 1 ? ' matches.' : ' match.')),
        tickable.length ? window.StudioLists.selectPage({ id: 'trainings-page',
          shown: tickable, ticked,
          flip: (on) => flipTick('trainings', tickable, on) }) : null)],
      shown.length ? null : ['none', [], () => make('p', 'quiet',
        'No training matches. Change or clear the filters.')],
      // Each card is built again only when its own training has changed.
      ['grid', [], () => make('ul', 'grid'), (node) => fit(node, shown.map((training) => [
        'card ' + training.path, [training, working(training), unclaimed(training),
          ticked.has(training.path)], () => trainingCard(training)]))]);
  }
  // With the runner, what the workspace has published is one step from here.
  placeParts({ title: 'Trainings', actions: [view.runner && view.listing.length
    ? newButton('filled') : null, view.runner ? capsule('Published', 'quiet',
    () => show('published'), 'published') : null],
  mark: ['Trainings', Boolean(view.runner), view.listing.length > 0] }, parts, fresh);
}

// --- status -----------------------------------------------------------------------

function cell(label, ...children) {
  const node = make('td');
  node.dataset.label = label;
  return add(node, ...children);
}

// The run of a listed training as the status screen knows it: what the runner said of
// every run, where it answered, or else what the list itself carries of the run.
function statusRunOf(training) {
  const runs = view.status ? list(view.status.runs) : [];
  const found = runs.find((run) => run.path === training.path);
  if (found) return statusOf(found);
  return training.run ? statusOf({ path: training.path, title: training.title,
    levels: training.levels, run: training.run }) : null;
}

// What is left before a training is ready: the files still to make while it is in
// progress, or what is in the way of one whose files are all made.
function leftLine(training) {
  if (!training || training.error || training.ready || !given(training.to_make)) return null;
  // Drafts still to write, drafts to review and mark ready, and what needs attention are
  // counted apart: a draft that exists is never said to be still to make.
  const write = given(training.to_write) ? training.to_write : training.to_make;
  const parts = [];
  if (write) parts.push('Still to write: ' + write);
  if (training.to_review) parts.push('To review and mark ready: ' + training.to_review);
  if (training.attention) parts.push('Needs attention: ' + training.attention);
  if (parts.length) return make('p', 'quiet', parts.join(' · '));
  if (!training.blocking || training.standing) return null;
  const go = capsule('In the way: ' + count(training.blocking, 'thing', 'things'), 'link',
    openTraining(training), 'in-the-way ' + training.path);
  go.setAttribute('aria-label', 'See what is in the way of ' + (training.title || 'Untitled'));
  return add(make('p', ''), go);
}

// When a training last moved: now, while a worker of its run is in hand; otherwise its
// newest activity, which the runner's tries count towards, or its last touch.
function activityCell(training, found) {
  if (found && found.state === 'working' && !queued(found)) {
    return cell('Last activity', make('span', '', 'Working now'));
  }
  return cell('Last activity', when(training.activity_at || training.touched_at));
}

function statusRow(training, found) {
  const row = make('tr');
  const name = make('th');
  name.scope = 'row';
  const title = training.title || 'Untitled';
  add(name, make('span', 'row-title', title),
    levelsText(training.levels) ? make('span', 'quiet', levelsText(training.levels)) : null);
  const go = capsule('Open', 'quiet', found && !training.error
    ? () => show('run', { path: training.path }) : openTraining(training),
  'open ' + training.path);
  go.setAttribute('aria-label', 'Open ' + title);
  if (training.error) {
    return add(row, name,
      cell('Doing now', state('off', 'Cannot be read'), make('p', 'quiet', training.error)),
      cell('Cost', '—'), cell('Last activity', when(training.touched_at)), cell('', go));
  }
  // What the runner said of the run, where it did, is the freshest word on a listed
  // training; the list's own words still decide what is said at a gate or when only the
  // deck is left. A run the list does not know is read as the runner gave it.
  const known = found && training.stage ? { ...training,
    run: { ...(training.run || {}), state: found.state, sentence: found.sentence } } : training;
  const [shape, words] = found && queued(found) ? ['none', 'Waiting its turn']
    : found && !training.stage ? statusWords(found) : standingOf(known);
  const says = found && !training.stage ? found.sentence : saysOf(known);
  return add(row, name,
    cell('Doing now', state(shape, words),
      // A question, a problem, or documents to add: it does nothing more until you come.
      (found && found.needs) || (known.standing && known.standing.state === 'needs-you')
        ? add(make('p', ''), make('strong', '', 'It needs you.')) : null,
      says ? make('p', 'quiet', says) : null,
      found && queued(found) ? make('p', 'quiet', queueSays(found.queue)) : null,
      noticeLine(found || training), leftLine(training)),
    cell('Cost', found ? spentSays(found.spent) : '—'),
    activityCell(training, found),
    cell('', go));
}

// How many trainings work at once is this computer's own limit, set where the set-up is
// changed.
function turnsLine() {
  const limit = view.status ? Number(view.status.limit) || 0 : 0;
  return limit ? make('p', 'quiet', 'Up to ' + count(limit, 'training works',
    'trainings work') + ' at once on this computer. Any more wait their turn.') : null;
}

// Every training on this computer, once, as a part of the status screen: what each is
// doing now, what its run has cost, and when it last moved. A row is built again only
// when its own training or run has changed. A run the runner lists of a training the
// list does not know is a row of its own.
function trainingsTable() {
  // A training a teammate runs is listed apart, under their name.
  const shown = view.listing.filter((training) => !elsewhere(training));
  const known = new Set(shown.map((training) => training.path));
  const extra = (view.status ? list(view.status.runs) : [])
    .filter((run) => !known.has(run.path)).map(statusOf);
  const rows = [...shown.map((training) => [training, statusRunOf(training)]),
    ...extra.map((found) => [{ path: found.path, title: found.title, levels: found.levels,
      notice: '' }, found])];
  const about = [Boolean(view.runner), view.status && view.status.limit,
    view.status && view.status.background, Boolean(view.status), rows.length > 0];
  return ['trainings', about, () => {
    const node = card('Trainings on this computer');
    if (!rows.length) {
      return add(node, make('p', 'quiet', 'There are no trainings on this computer yet.'),
        turnsLine(), backgroundLine());
    }
    const table = make('table', 'table');
    const head = make('tr');
    for (const title of ['Training', 'Doing now', 'Cost', 'Last activity', '']) {
      const top = make('th', '', title);
      top.scope = 'col';
      if (!title) add(top, make('span', 'offscreen', 'Open'));
      head.append(top);
    }
    return add(node, turnsLine(), backgroundLine(),
      add(table, add(make('thead'), head), make('tbody')));
  }, (node) => {
    const body = node.querySelector('tbody');
    if (body) {
      fit(body, rows.map(([training, found]) => ['row ' + training.path,
        [training, unclaimed(training), found], () => statusRow(training, found)]));
    }
  }];
}

function fact(found, optional) {
  const shape = found.state === 'ok' ? 'done'
    : found.state === 'problem' && !optional ? 'late' : 'none';
  const words = found.label + (found.detail ? ': ' + found.detail : '')
    + (found.state === 'ok' && !found.detail ? ': yes' : '');
  return add(make('li', 'fact'), bead(shape), make('span', '', words));
}

function computerItem(item) {
  const [shape, words] = COMPUTER_WORDS[item.state] || COMPUTER_WORDS.problem;
  const node = make('li', 'computer-item');
  const said = item.state !== 'ok' && item.optional ? words + ' (optional)' : words;
  add(node, add(make('div', 'computer-top'), make('p', 'row-title', item.name),
    state(item.state !== 'ok' && item.optional ? 'none' : shape, said)));
  const facts = make('ul', 'facts');
  for (const found of list(item.facts)) facts.append(fact(found, item.optional));
  add(node, facts);
  if (item.fix) add(node, make('p', item.optional ? 'fix fix-optional' : 'fix', item.fix));
  // What a newer release would put right is updated from the versions, on this same screen.
  if (item.versions) {
    add(node, add(make('div', 'bar'), capsule('See the versions', 'quiet', () => {
      const found = byId('versions');
      if (found && found.scrollIntoView) {
        found.scrollIntoView({ block: 'start', behavior: calm() ? 'auto' : 'smooth' });
      }
    }, 'versions-' + item.id)));
  }
  return node;
}

async function checkComputer() {
  if (view.checking) return;
  view.checking = true;
  draw(false);
  try {
    view.computer = (await send('computer', {})).computer;
    toast(view.computer.ready ? 'This computer is ready.'
      : 'This computer needs something put right.');
  } catch (failure) {
    notify(failure.message);
  }
  view.checking = false;
  draw(false);
}

function computerCard() {
  const node = card('This computer');
  const result = view.computer;
  if (!result) {
    return add(node, make('p', '', 'See whether this computer has what a training needs: an '
      + 'assistant that is installed and can be reached from this network, Node, and the two '
      + 'companion skills. It asks each one for its version and nothing more.'),
    // With the runner, a deck is made here too, and what that needs is checked with the rest.
    view.runner ? make('p', 'quiet', 'A slide deck needs more: the slides skill, a brand '
      + 'skill, a way to make previews, and the programs that turn a render into pictures. '
      + 'Each is listed with the rest, with what to do about it.') : null);
  }
  const summary = make('p', 'foot-line');
  if (result.ready) add(summary, state('done', 'This computer is ready.'));
  else {
    add(summary, state('late', 'Not ready yet. To put right: '
      + list(result.wrong).join(', ') + '.'));
  }
  add(summary, add(make('span', 'quiet'), 'Checked ', when(result.checked_at), '.'));
  const items = make('ul', 'computer-items');
  for (const item of list(result.items)) items.append(computerItem(item));
  return add(node, summary, items);
}

// The file every studio shares, on Status: where it could not be read, built-in defaults are
// used meanwhile, and nothing waits on it.
function studiosStatusCard() {
  const parts = studiosParts(true);
  return parts.length ? add(card('Your other studios'), ...parts) : null;
}

function studiosHomeCard() {
  const parts = studiosParts(false);
  return parts.length ? add(card('Your other studios'), ...parts) : null;
}

// Who runs a training is said only where there is a team to run it.
function statusLede() {
  return 'What is running, ' + (teamSpace() ? 'who runs it, ' : '')
    + 'and whether this computer has what a training needs.';
}

function drawStatus(fresh) {
  const check = capsule(view.checking ? 'Checking…' : view.computer ? 'Check this computer again'
    : 'Check this computer', 'filled', checkComputer, 'check-computer');
  check.disabled = view.checking;
  const theirs = view.status ? list(view.status.elsewhere).map(statusOf)
    : teammates().map(statusOf);
  placeParts({ title: 'Status', actions: [check],
    mark: ['Status', view.checking, Boolean(view.computer)] }, [
    ['head', [statusLede()], () => pageHead(statusLede())],
    ['computer', [view.computer, Boolean(view.runner)], computerCard],
    trainingsTable(),
    ['teammates', [Boolean(view.runner), Boolean(view.status), theirs, teamSpace(),
      view.fetching, view.fetched], teammatesCard],
    ['versions', [upkeepOf(), view.restarting], versionsCard],
    ['skills', [upkeepOf()], skillsCard],
    ['studios', studiosMark(), studiosStatusCard]], fresh);
  // With the runner, every run and who runs what is asked for as the screen opens.
  if (fresh && view.runner) {
    const turn = view.turn;
    readStatus().then(() => {
      if (turn === view.turn && view.drawn !== signature() && !view.checking) draw(false);
    });
  }
}

// --- settings ---------------------------------------------------------------------

function alertsCard() {
  const node = card('Notifications');
  const allowed = alerts();
  if (allowed === 'none') {
    return add(node, make('p', '', 'This browser cannot show notifications. The count beside '
      + 'Home, and in the tab title, still shows what needs you.'));
  }
  if (allowed === 'granted') {
    return add(node, state('done', 'On. This browser tells you when something needs you, '
      + 'while this page is open in a tab.'));
  }
  if (allowed === 'denied') {
    return add(node, make('p', '', 'Notifications are turned off for this page in your '
      + 'browser’s own settings. The count beside Home, and in the tab title, still shows '
      + 'what needs you.'));
  }
  return add(node, make('p', '', 'Be told when a training needs you, even when this tab is '
    + 'behind another.'), add(make('div', 'bar'), capsule('Turn on notifications', '',
    async () => {
      try {
        await Notification.requestPermission();
      } catch (failure) {
        // Older browsers answer through a callback; the next draw reads the result.
      }
      draw(false);
    }, 'alerts')));
}

function decidedCard() {
  const node = card('Where each training is decided');
  add(node, make('p', '', 'On this page, only you can approve a stage: your assistant is '
    + 'refused if it tries. In the conversation, you approve by telling your assistant.'));
  // A training that runs on its own is always decided here, so there is nothing to choose.
  // One a teammate runs is decided on their computer.
  const held = view.listing.filter((training) => !training.error && !watched(training));
  if (!held.length) {
    return add(node, make('p', 'quiet', view.listing.some((training) => training.run
      && !elsewhere(training))
      ? 'Every training here runs from this page, and is decided on it.'
      : teammates().length ? 'Every training here is run by a teammate, and is decided '
        + 'where it runs.' : 'There are no trainings yet.'));
  }
  for (const training of held) {
    add(node, add(make('div', 'setting'), make('p', 'row-title', training.title || 'Untitled'),
      approvalControl(training.path, training.title || 'Untitled', training.approval,
        refresh)));
  }
  return node;
}

const SETTINGS_LEDE = 'How Training Studio works on this computer; what every studio shares '
  + 'is changed in Shared settings.';

// Each card is built again only when what it is drawn from has changed: where each training
// is decided, only when a training's own answer to that has.
function drawSettings(fresh) {
  const decided = view.listing.map((training) => [training.path, training.title,
    training.approval, Boolean(training.error), watched(training), Boolean(training.run),
    elsewhere(training)]);
  placeParts({ title: 'Settings', mark: ['Settings'] }, [
    ['head', [], () => pageHead(SETTINGS_LEDE)],
    ['shared-settings', [Boolean(view.runner)], () => view.runner ? add(card('Shared settings'),
      make('p', '', 'Your assistant, work folder, brand and delivery choices apply across all studios.'),
      // Who owns each kind of value, said in words rather than implied by where it sits.
      about([['Shared', 'Assistant, work folder, default brand and delivery: changed in '
          + 'Marketing Studio’s Shared settings.'],
        ['This training only', 'Each training keeps the brand, research sites and models it '
          + 'was started with.'],
        ['This studio', 'The cards below apply to Training Studio on this computer, except '
          + 'Brand skill: its repository and release are shared, as Shared settings, Advanced, '
          + 'Brand skill release shows them.']]),
      capsule('Change shared settings', 'quiet', () => { location.href = settingsAddress(); }, 'shared-settings')) : null],
    ['workspace', around(), workspaceCard],
    ['decided', [decided, view.unmoved], decidedCard],
    ['brand-source', [view.setup && view.setup.brand && [view.setup.brand.repository,
      view.setup.brand.release], view.brandRefused, view.savingBrand], brandSourceCard],
    ['look', [view.setup && view.setup.updates, view.lookRefused], lookCard],
    ['alerts', [alerts()], alertsCard], ['notify', around(), notifyCard],
    ['left', around(), leftCard],
    ['page', [Boolean(view.runner)], () => add(card('This page'),
      make('p', '', 'It runs on this computer and answers only to the link that opened it. '
        + (view.runner ? 'The page sends what you read and decide nowhere else. The agent that '
          + 'does the drafting is sent what it needs for each step, by its own service.'
          : 'Nothing you read or decide here is sent anywhere else.')))]], fresh);
}

// --- a gate -----------------------------------------------------------------------

function documentBody(shown, found) {
  const node = make('article', 'paper doc');
  node.setAttribute('aria-label', found.label);
  if (shown.kind === 'missing') {
    return add(node, make('p', 'quiet', 'Nothing has been made here yet.'));
  }
  if (shown.kind === 'questions') {
    add(node, make('h2', 'doc-title', shown.topic || 'The research questions'));
    if (shown.scope) add(node, make('p', 'quiet', 'Sources: ' + shown.scope.replace('-', ' ')));
    const items = make('ol', 'questions');
    for (const item of list(shown.questions)) {
      add(items, add(make('li'), make('span', '', item.question),
        make('span', 'question-id', item.id)));
    }
    return add(node, items);
  }
  if (shown.kind === 'file') {
    return add(node, make('h2', 'doc-title', shown.file.split('/').pop()),
      make('p', '', (slidesOf(found).length ? 'The pictures above are of this file. It is '
        : 'This is not text, so it is not shown here. It is ') + size(shown.size)
        + '. Open it from the training folder:'),
      pathInto(make('p', 'path'), found.path + '/' + shown.file),
      copyButton('Copy where it is', 'Copied', found.path + '/' + shown.file, 'copy-file'),
      capsule('Download ' + shown.file.split('/').pop(), 'quiet', (event) =>
        downloadFile(found.path, {artifact: found.artifact}, shown.file.split('/').pop(),
          event.currentTarget), 'download-file'));
  }
  if (shown.kind === 'link') {
    add(node, make('p', 'quiet', shown.file.split('/').pop() + ', ' + size(shown.size)
      + '. The deck itself is where this points:'));
  }
  add(node, window.StudioMarkdown.render(shown.text, { files: Boolean(found.files) }));
  if (shown.truncated) {
    add(node, make('p', 'quiet', 'This is the start of a long file of ' + size(shown.size)
      + '. Open the file for the rest.'));
  }
  return node;
}

// A file of a training as the server reads it out, in the shape a gate's document has.
function asDocument(read) {
  return { kind: read.binary ? 'file' : 'markdown', file: read.file, size: read.size,
    text: read.text, truncated: read.truncated };
}

function comparison(changed) {
  const node = make('article', 'paper diff');
  node.tabIndex = 0;
  node.setAttribute('aria-label', 'Lines added and removed since you approved it');
  for (const row of changed.rows) {
    const line = make('p', 'diff-row');
    line.dataset.kind = row.kind;
    const sign = row.kind === 'added' ? '+' : row.kind === 'removed' ? '−' : '';
    add(line, make('span', 'diff-sign', row.kind === 'gap' ? '⋯' : sign),
      row.kind === 'gap' ? null : make('span', 'diff-text', row.text));
    if (row.kind === 'added') add(line, make('span', 'offscreen', ' (added)'));
    if (row.kind === 'removed') add(line, make('span', 'offscreen', ' (removed)'));
    node.append(line);
  }
  if (changed.truncated) add(node, make('p', 'quiet', 'Only the first changes are shown.'));
  return node;
}

// What is read at a gate: the document, with what changed in it one press away. A deck the
// runner rendered is its slides first, and which of them address each objective.
function researchReading(found) {
  const node = make('article', 'paper doc');
  add(node, window.StudioMarkdown.render(found.brief),
    make('h2', 'doc-title', 'What the independent check said'), make('p', '', found.check.said),
    found.check.note ? make('p', '', found.check.note) : null,
    ...list(found.check.unread).map((one) => make('p', '', (one.title || one.source) + ': ' + one.access_error)),
    make('h2', 'doc-title', 'What the research could not settle'),
    list(found.gaps).length ? bullets(found.gaps) : make('p', 'quiet', 'No gaps were named.'),
    ...list(found.sources.partial).map((one) => make('p', '', one.title + ': ' + one.note)),
    // Pages refused for being outside your sites, with the sites named.
    found.outside ? make('p', '', found.outside) : null,
    make('p', 'quiet', found.read));
  const finding = (id) => list(found.findings).find((one) => one.id === id);
  const show = (ids) => ids.map(finding).filter(Boolean).map((one) =>
    add(make('div', 'card-part'), make('p', 'row-title', one.title), make('p', '', one.summary)));
  if (list(found.questions).length) add(node, make('h2', 'doc-title', 'Your questions'));
  for (const question of list(found.questions)) add(node, make('p', 'row-title', question.question),
    ...(list(question.findings).length ? show(question.findings) : [make('p', 'quiet', 'The research did not answer this.')]));
  if (list(found.unplanned).length) add(node, make('h2', 'doc-title', 'Also found'), ...show(found.unplanned));
  for (const [label, text] of [['Read the full report', found.report], ['The evidence and the check’s notes', found.evidence]]) {
    add(node, add(make('details', 'card-part'), make('summary', '', label), window.StudioMarkdown.render(text)));
  }
  return node;
}

function reading(found) {
  const node = make('div', 'reading');
  if (found.research) return add(node, researchReading(found.research));
  if (found.outside) add(node, make('p', 'quiet', found.outside));
  if (slidesOf(found).length) add(node, slidesPart(found), coveragePart(found));
  const changed = found.changes;
  if (!changed.available || changed.same || !changed.comparable) {
    return add(node, documentBody(found.document, found));
  }
  const panes = [() => documentBody(found.document, found), () => comparison(changed)];
  const holder = make('div', 'pane');
  const at = view.pane ? 1 : 0;
  add(holder, panes[at]());
  return add(node, segmented('What to read', ['The document', 'What changed'], at,
    (index, control) => {
      view.pane = index;
      slide(control, index);
      holder.replaceChildren(panes[index]());
    }, 'pane'), holder);
}

// The fields of a Yoodli scenario: each heading with a fenced text block under it, named
// by its heading and, under Personas, by the persona and the heading. Yoodli's Builder has
// a box of the same name for each.
function yoodliFields(text) {
  const fields = [];
  const heads = [];
  let block = null;
  for (const line of String(text || '').split('\n')) {
    if (block) {
      if (line.trim() === '```') {
        const named = heads.length > 1 ? heads.slice(1).join(' · ') : heads[0] || '';
        if (named) fields.push({ name: named, text: block.join('\n') });
        block = null;
      } else {
        block.push(line);
      }
      continue;
    }
    const heading = /^(#{2,4}) (.+)$/.exec(line);
    if (heading) {
      heads.length = heading[1].length - 2;
      heads[heading[1].length - 2] = heading[2].trim();
    } else if (line.trim() === '```text') {
      block = [];
    }
  }
  return fields;
}

// A Yoodli scenario at its gate offers each field to copy, ready to paste into the Builder.
function yoodliCopies(found) {
  if (!String(found.artifact || '').startsWith('yoodli:')) return null;
  const fields = yoodliFields(found.text || '');
  if (!fields.length) return null;
  const bar = make('div', 'bar');
  fields.forEach((field, index) => add(bar, copyButton('Copy ' + field.name,
    'Copied ' + field.name + '.', field.text, 'copy-field-' + index)));
  return callout('', make('h2', 'aside-title', 'Copy into Yoodli'),
    make('p', 'quiet', 'Each field is copied on its own, ready to paste into the box of the '
      + 'same name in Yoodli’s Builder.'), bar);
}

// What a Yoodli scenario was laid out from, to read beside it. It is read once for a gate.
async function readBeside(found, turn) {
  const named = found.beside;
  if (!named) {
    view.beside = null;
    return;
  }
  if (view.beside && view.beside.artifact === named.artifact) return;
  let held;
  try {
    held = { artifact: named.artifact,
      read: await ask('file', { path: found.path, artifact: named.artifact }) };
  } catch (failure) {
    held = { artifact: named.artifact, error: failure.message };
  }
  if (turn === view.turn) view.beside = held;
}

// It sits beside the document that is being decided, and never in its place.
function besidePart(found) {
  const named = found.beside;
  const held = view.beside && view.beside.artifact === named.artifact ? view.beside : null;
  const label = lower(named.label);
  const node = make('section', 'beside');
  node.setAttribute('aria-label', 'What it was laid out from');
  add(node, make('h2', 'aside-title', 'Laid out from ' + label),
    make('p', 'quiet', 'Here to compare with. What you are deciding is ' + lower(found.label)
      + ', not this.'));
  if (!held) return add(node, make('p', 'quiet', 'Reading it.'));
  if (held.error) {
    return add(node, callout('late', make('p', '', 'It could not be read. ' + held.error),
      make('p', 'quiet', 'Nothing was changed, and what you are deciding is not affected.'),
      add(make('div', 'bar'), button('Open it on its own', 'link', () => show('gate',
        { path: found.path, artifact: named.artifact }), 'beside ' + named.artifact))));
  }
  return add(node, documentBody(asDocument(held.read),
    { label: capital(label), path: found.path }));
}

function changesNote(changed) {
  const node = make('section', 'paper aside-part');
  add(node, make('h2', 'aside-title', 'What changed'));
  if (!changed.available) {
    return add(node, make('p', 'quiet', 'You have not approved a version of this before, so '
      + 'there is nothing to compare it with.'));
  }
  if (changed.same) {
    return add(node, add(make('p', 'quiet'), 'Nothing. It is as you approved it ',
      when(changed.approved_at), '.'));
  }
  if (!changed.comparable) {
    return add(node, add(make('p', ''), 'It has changed since you approved it ',
      when(changed.approved_at), ', and it cannot be compared line by line.'));
  }
  const added = changed.rows.filter((row) => row.kind === 'added').length;
  const removed = changed.rows.filter((row) => row.kind === 'removed').length;
  return add(node, add(make('p', ''), count(added, 'line', 'lines') + ' added and '
    + count(removed, 'line', 'lines') + ' removed since you approved it ',
  when(changed.approved_at), '. Choose “What changed” above the document to see them.'));
}

function checkedNote(found) {
  const node = make('section', 'paper aside-part');
  add(node, make('h2', 'aside-title', 'Checked for you'));
  const passed = Number(found.checked.passed) || 0;
  const failing = list(found.checked.problems).length;
  if (!passed && !failing && !found.audit) {
    return add(node, make('p', 'quiet', 'No automatic checks apply here. It is yours to read.'));
  }
  // While the review still finds something serious in a deck, nothing here says the deck is
  // through: the checks are said to have run, and what they do not look at is said too.
  if (passed && serious(found).length) {
    add(node, make('p', '', count(passed, 'automatic check', 'automatic checks')
      + ' ran and raised nothing. Automatic checks do not look at the slides: the review '
      + 'does, and it still finds something.'));
  } else if (passed) {
    add(node, state('done', count(passed, 'check', 'checks') + ' passed'));
  }
  if (failing) {
    add(node, make('p', 'quiet', count(failing, 'check', 'checks') + ' did not. See below.'));
  }
  return add(node, found.audit ? auditPart(found.audit) : null);
}

function lookNote(found) {
  const node = make('section', 'paper aside-part');
  add(node, make('h2', 'aside-title', 'Worth a look'));
  const items = make('ul', 'look');
  for (const first of list(found.first)) {
    add(items, add(make('li'), state('late', 'Not ready to approve: it is built from '
      + first.label + ', which is not approved yet.'), ' ',
    button('Open that first', 'link', () => show('gate',
      { path: found.path, artifact: first.artifact }), 'first ' + first.artifact)));
  }
  for (const reason of list(found.out_of_date)) {
    add(items, add(make('li'), state('late', 'Out of date. ' + reason)));
  }
  if (found.unavailable) {
    add(items, add(make('li'), state('off', 'Could not be made: ' + found.unavailable)));
  }
  for (const failed of list(found.checked.problems)) {
    add(items, add(make('li'), state('late', 'A check ' + failed.words + ': '),
      make('code', '', failed.check), bullets(list(failed.problems), 'reasons')));
  }
  for (const request of list(found.asked)) {
    add(items, add(make('li'), add(make('p', 'foot-line'), state('current',
      request.kind === 'rebuild' ? 'You asked for a rebuild' : 'You asked for changes'),
    when(request.at)),
    request.note ? make('p', 'quote', request.note) : null,
    make('p', 'quiet', runOf(found.path)
      ? 'It is being done on its own now, and comes back here for your review.'
      : 'Your assistant does this when you go back to the conversation.')));
  }
  if (items.childNodes.length) add(node, items);
  // A deck the runner rendered has its review as findings, shown in a part of their own.
  const note = typeof found.review === 'string' ? found.review : '';
  if (note) {
    const notes = make('details', 'review-notes');
    notes.dataset.key = 'review';
    // Open, except where two documents are read side by side below: there a long note
    // would push both off the first screen, so it waits to be opened.
    notes.open = !found.beside;
    add(notes, make('summary', '', 'The latest review note'),
      window.StudioMarkdown.render(note));
    add(node, notes);
  }
  if (!items.childNodes.length && !note) {
    add(node, make('p', 'quiet', reviewOf(found) ? 'Nothing else was flagged.'
      : 'Nothing was flagged.'));
  }
  return node;
}

function gateSignature(found) {
  return JSON.stringify([found.status, found.sha256, found.checked, found.out_of_date,
    found.review, found.asked, found.decisions, found.first, found.approval, found.stages,
    found.waiting, found.question, found.changes.same, found.changes.available,
    found.whose, found.beside, found.slides, found.audit, found.coverage, found.research, found.research_price]);
}

function callout(kind, ...children) {
  const node = make('div', 'paper callout');
  if (kind) node.dataset.kind = kind;
  return add(node, ...children);
}

// What is being read changed under the reader. It is never swapped for them: they say when.
function changedCallout(see) {
  return callout('late', make('p', 'problem', 'This changed while you had it open.'),
    add(make('div', 'bar'), capsule('Show the new version', 'filled', see, 'newer')));
}

// What the gate says before anything is decided: where it stands and what is asked.
function standing(found) {
  if (view.newer) {
    return changedCallout(() => {
      view.gate = view.newer;
      view.newer = null;
      paintGate(false);
    });
  }
  // A file a combined review covers is decided there, with everything else it covers.
  if (found.combined && found.approval === 'page' && !reads(found.path)) {
    return callout('yours', make('p', '', 'This is part of the ' + found.combined.name
      + ' that is waiting for you. It is decided there, with everything the review covers.'));
  }
  if (found.status === 'approved' && found.approved) {
    return callout('', add(make('p', ''), found.approved.by === 'review-policy'
      ? 'Continued automatically under the saved review level '
      : 'You approved this ' + (found.approved.by === 'page' ? 'on this page ' : 'in the conversation '),
    when(found.approved.at), '.'));
  }
  if (found.status === 'skipped') {
    return callout('', make('p', '', 'This stage is left out of the training.'));
  }
  if (found.status === 'unavailable') {
    return callout('late', make('p', '', 'This stage could not be made.'));
  }
  if (found.status === 'not-started') {
    return callout('', make('p', '', 'Nothing has been made here yet, so there is nothing '
      + 'to decide.'));
  }
  if (found.status === 'stale') {
    return callout('late', make('p', '', 'This is out of date. Have it rebuilt, or accept it '
      + 'as it is.'), found.question ? make('p', 'quiet', asker(found.path)
      + found.question) : null);
  }
  if (list(found.first).length) {
    return callout('late', make('p', '', 'This cannot be approved yet. See “Worth a look”.'));
  }
  if (found.question) {
    return callout('yours', make('p', '', asker(found.path) + found.question));
  }
  return null;
}

// Where approving happens in the conversation, the page says so and offers one control.
function inChat(found) {
  if (found.approval === 'page' || reads(found.path)) return null;
  const problem = make('p', 'problem');
  problem.setAttribute('role', 'alert');
  problem.hidden = true;
  const move = capsule('Decide on this page instead', '', async () => {
    if (view.busy) return;
    view.busy = true;
    move.disabled = true;
    try {
      await moveApproval(found.path, 'page');
      view.busy = false;
      await draw(false);
      if (!focusKey('lead')) byId('title').focus({ preventScroll: true });
    } catch (failure) {
      problem.textContent = failure.message;
      problem.hidden = false;
      move.disabled = false;
    }
    view.busy = false;
  }, 'move');
  return callout('', make('p', '', 'For this training, approving happens in your conversation '
    + 'with your assistant. You can move it here: your assistant then cannot approve '
    + 'anything, and only this page can.'), add(make('div', 'bar'), move), problem);
}

// The toolbar's side of a gate: one filled button for the main thing to do, the rest quieter.
function gateActions(found) {
  // A training someone else runs is read here, and decided where it runs. A file a
  // combined review covers is decided there.
  if (found.approval !== 'page' || view.newer || reads(found.path)) return [];
  // While a combined review covers the file, only a stage can be left out or brought back.
  const offers = list(found.decisions).filter((offer) => !found.combined
    || ['skip', 'restore'].includes(offer));
  const lead = offers.includes('approve') ? 'approve' : offers.includes('restore') ? 'restore'
    : found.status === 'stale' && offers.includes('rebuild') ? 'rebuild' : '';
  const actions = [];
  if (found.combined) {
    actions.push(capsule('Request changes in the ' + found.combined.name, lead ? '' : 'filled',
      () => show('run', { path: found.path }), 'combined'));
  }
  if (offers.includes('revise')) {
    actions.push(capsule('Ask for changes', '', openSheet('revise', 'revise'), 'revise'));
  }
  const rest = [];
  const item = (label, kind) => button(label, 'menu-item', openSheet(kind, 'more'),
    'menu ' + kind);
  if (offers.includes('rebuild') && lead !== 'rebuild') rest.push(item('Rebuild it', 'rebuild'));
  if (offers.includes('accept')) rest.push(item('Accept as it is', 'accept'));
  if (offers.includes('skip')) rest.push(item('Skip this stage', 'skip'));
  if (found.held_by === 'yoodli') {
    rest.push(make('p', 'menu-note quiet', 'The brief and the practice scenarios cannot be '
      + 'skipped while Make scenarios for Yoodli is on: Yoodli uses both.'));
  }
  if (rest.length) {
    const more = make('details', 'menu');
    const opener = make('summary', 'button button-round shine');
    opener.dataset.key = 'more';
    opener.setAttribute('aria-label', 'More');
    add(more, add(opener, icon('more')), add(make('div', 'menu-list'), ...rest));
    actions.push(more);
  }
  if (lead === 'approve') {
    actions.push(capsule('Approve', 'filled', openSheet('approve', 'lead'), 'lead'));
  } else if (lead === 'restore') {
    actions.push(capsule('Bring this stage back', 'filled', openSheet('restore', 'lead'),
      'lead'));
  } else if (lead === 'rebuild') {
    actions.push(capsule('Rebuild it', 'filled', openSheet('rebuild', 'lead'), 'lead'));
  }
  return actions;
}

function paintGate(fresh) {
  const found = view.gate;
  view.drawn = gateSignature(found);
  const theirs = reads(found.path);
  const words = found.waiting ? ['review', theirs ? 'Waiting for a decision where it runs'
    : found.status === 'stale'
      ? 'Out of date, and waiting for your decision' : 'Waiting for your review']
    : [FILE_BEADS[found.status], capital(found.words)];
  // A practice scenario says whose file it is: the person's own, or a draft made for them.
  // A deck the runner rendered says that its pictures are of the very file being decided.
  const decked = slidesOf(found).length > 0;
  if (!decked) view.viewer = null;
  // Only a gate waiting for this person's decision here says what to do at it.
  const decides = found.waiting && found.approval === 'page' && !theirs && !found.combined;
  const intro = add(make('div', 'intro'), state(words[0], words[1]),
    beads(found.stages, false),
    decides ? make('p', 'lede', 'Read ' + lower(found.label)
      + ', then approve it or ask for changes.') : null,
    WHOSE[found.whose] ? make('p', 'quiet', WHOSE[found.whose]) : null,
    decked ? make('p', 'quiet', 'These are the slides themselves. The pictures were made from '
      + 'the very file you are deciding on.') : null);
  const aside = add(make('aside', 'aside'), reviewOf(found) ? findingsNote(found) : null,
    found.research ? null : checkedNote(found), lookNote(found), changesNote(found.changes));
  aside.setAttribute('aria-label', 'The review');
  const above = [button(found.title, 'link', () => show(homeOf(found.path),
    { path: found.path }), 'training'),
  levelsText(found.levels) ? make('span', '', ' · ' + levelsText(found.levels)) : null];
  // The document comes first, so in one column it is read before the review. Where there is
  // room, each part is put in its place by the stylesheet.
  place({ title: found.label, name: found.label + ' · ' + found.title, above, back: true,
    actions: gateActions(found) },
  [intro, theirs ? readNote(found.path) : null, inChat(found), standing(found),
    yoodliCopies({artifact: found.artifact, text: found.document?.text}),
    add(make('div', found.beside ? 'gate gate-pair'
      : 'gate'), reading(found), found.beside ? besidePart(found) : null, aside)],
  fresh);
  tidyPictures();
  drawSheet();
}

// --- a gate: a deck's slides -----------------------------------------------------------
// A deck the runner rendered is shown as its slides: one at full size with the way to the
// next and the one before, and all of them in a strip to jump by. Beside them is what the
// review still finds, and under them which slides address each objective.

function slidesOf(found) {
  return list(found && found.slides);
}

// A deck's review as its findings, where the runner gives it that way.
function reviewOf(found) {
  return found.review && typeof found.review === 'object' ? found.review : null;
}

// The findings that matter most. While there is one, the page never says the deck is through.
function serious(found) {
  return list((reviewOf(found) || {}).findings)
    .filter((finding) => SERIOUS.includes(finding.severity));
}

function slideName(slide) {
  return 'Slide ' + slide.number + (slide.title ? ': ' + slide.title : '');
}

// Slides by their numbers: "slide 3", "slides 3 to 5", or "slides 3, 5 and 8".
function slidesNamed(numbers) {
  const held = list(numbers);
  if (held.length < 2) return held.length ? 'slide ' + held[0] : 'no slide';
  const row = held.length > 2 && held.every((number, index) => !index
    || number === held[index - 1] + 1);
  return 'slides ' + (row ? held[0] + ' to ' + held[held.length - 1]
    : series(held.map(String)));
}

function slidesPart(found) {
  const slides = slidesOf(found);
  const node = make('section', 'slides');
  node.id = 'slides';
  node.setAttribute('aria-label', 'The slides');
  if (!slides.some((slide) => slide.number === view.slide)) view.slide = slides[0].number;
  const at = () => slides.findIndex((slide) => slide.number === view.slide);
  const of = (slide) => ({ artifact: found.artifact, number: slide.number });
  const stage = make('div', 'paper stage');
  stage.id = 'slide-stage';
  stage.tabIndex = -1;
  stage.dataset.key = 'slide-stage';
  const now = make('p', 'slide-now');
  now.setAttribute('role', 'status');
  const earlier = capsule('Previous', '', () => view.viewer.move(-1), 'slide-previous');
  const later = capsule('Next', '', () => view.viewer.move(1), 'slide-next');
  earlier.setAttribute('aria-label', 'Previous slide');
  later.setAttribute('aria-label', 'Next slide');
  const strip = make('ol', 'strip');
  strip.setAttribute('aria-label', 'Every slide');
  const items = slides.map((slide) => {
    const item = button('', 'strip-item', () => view.viewer.go(slide.number),
      'slide ' + slide.number);
    item.setAttribute('aria-label', slideName(slide));
    add(strip, add(make('li'), add(item, pictureAt(of(slide), slideName(slide), found.sha256),
      make('span', 'strip-number', String(slide.number)),
      make('span', 'strip-title', slide.title || ''))));
    return item;
  });
  // Turning to a slide changes only what is in the stage, so nothing else loses its place.
  const turn = () => {
    const index = at();
    const slide = slides[index];
    // Where the focus was on what is about to go, it stays on the stage, not nowhere.
    const within = stage.contains(document.activeElement);
    stage.replaceChildren(pictureAt(of(slide), slideName(slide), found.sha256,
      { first: true, again: true }));
    if (within) stage.focus({ preventScroll: true });
    now.textContent = 'Slide ' + slide.number + ' of ' + slides.length
      + (slide.title ? ': ' + slide.title : '');
    // At either end the control stays where the keyboard can find it, and says it is off.
    earlier.setAttribute('aria-disabled', String(index === 0));
    later.setAttribute('aria-disabled', String(index === slides.length - 1));
    items.forEach((item, other) => {
      if (other === index) item.setAttribute('aria-current', 'true');
      else item.removeAttribute('aria-current');
    });
    // The strip follows the slide that is shown, sideways only: the page itself stays put.
    const shown = items[index].parentNode;
    const past = shown.offsetLeft + shown.offsetWidth - strip.clientWidth;
    if (shown.offsetLeft < strip.scrollLeft) strip.scrollLeft = shown.offsetLeft;
    else if (past > strip.scrollLeft) strip.scrollLeft = past;
  };
  view.viewer = {
    move(by) {
      const next = slides[at() + by];
      if (next) this.go(next.number);
    },
    go(number, look) {
      if (slides.some((slide) => slide.number === number)) {
        view.slide = number;
        turn();
      }
      // Reached from a finding, the slide itself is where the reader is taken.
      if (look) stage.focus();
    },
  };
  turn();
  return add(node, stage, add(make('div', 'bar slide-moves'), earlier, later, now), strip);
}

// What the reviewer still finds, the most serious first, in the reviewer's own words.
function findingsNote(found) {
  const review = reviewOf(found);
  const node = make('section', 'paper aside-part');
  add(node, make('h2', 'aside-title', 'What the review still finds'));
  const order = Object.keys(SEVERITIES);
  const rank = (finding) => (order.includes(finding.severity)
    ? order.indexOf(finding.severity) : order.length);
  const findings = list(review.findings).slice().sort((one, other) => rank(one) - rank(other)
    || one.number - other.number);
  // The reviewer drew none of the slides. How often it has looked says how far repair went.
  const looked = 'An independent reviewer, which drew none of the slides, has looked at each '
    + 'one' + (review.round > 0 ? ' ' + times(review.round) : '') + '.';
  // Reviewed against the approved design: the slides drawn as text by decision, accepted so.
  const accepted = list(review.direct).filter((entry) => entry.accepted);
  const direct = accepted.length ? make('p', 'quiet', 'Drawn as text by decision, and '
    + 'accepted so by the review: ' + slidesNamed(accepted.map((entry) => entry.number))
    + '.') : null;
  if (!findings.length) {
    return add(node, make('p', '', 'The reviewer has nothing left to raise.'),
      make('p', 'quiet', looked + ' Whether the deck is good is still yours to judge.'),
      direct);
  }
  const counted = order.map((severity) => [findings.filter((finding) => finding.severity
    === severity).length, SEVERITIES[severity][1].toLowerCase()])
    .filter(([number]) => number).map(([number, word]) => number + ' ' + word);
  const others = findings.filter((finding) => !SEVERITIES[finding.severity]).length;
  if (others) counted.push(others + (counted.length ? ' other' : ''));
  const says = series(counted) + (findings.length === 1 ? ' finding remains.'
    : ' findings remain.');
  add(node, serious(found).length ? state('late', says) : make('p', '', says),
    make('p', 'quiet', looked + ' The deck comes to you as it is.'));
  const item = (finding, index) => {
    const [shape, words] = SEVERITIES[finding.severity]
      || ['none', spoken(finding.severity || 'finding')];
    const go = button('Slide ' + finding.number, 'link',
      () => view.viewer && view.viewer.go(finding.number, true), 'finding ' + index);
    return add(make('li', 'finding'),
      add(make('p', 'foot-line'), state(shape, words), go,
        ABOUT_TAGS[finding.about] ? make('span', 'tag', ABOUT_TAGS[finding.about]) : null),
      make('p', '', finding.note),
      finding.fix ? make('p', 'quiet', 'Suggested: ' + finding.fix) : null);
  };
  // A review against the approved design files each finding in one of the slides tool's
  // categories, and they are shown so, in its order. Any other review is one list.
  const filed = findings.some((finding) => finding.category);
  if (filed) {
    const known = Object.keys(CATEGORY_WORDS);
    const rank = (finding) => (known.includes(finding.category) ? known.indexOf(finding.category)
      : known.length);
    const groups = [...new Set(findings.map((finding) => finding.category))]
      .sort((one, other) => rank({ category: one }) - rank({ category: other }));
    groups.forEach((category) => {
      const items = make('ol', 'look findings');
      findings.forEach((finding, index) => {
        if (finding.category === category) add(items, item(finding, index));
      });
      add(node, make('p', 'row-title', CATEGORY_WORDS[category] || 'Found'), items);
    });
  } else {
    const items = make('ol', 'look findings');
    findings.forEach((finding, index) => add(items, item(finding, index)));
    add(node, items);
  }
  add(node, direct);
  if (findings.some((finding) => finding.about === 'content')) {
    add(node, make('p', 'quiet', '“About what it says” is a finding about a slide’s words, '
      + 'not how it is drawn, so drawing the slide again would not put it right. Choose “Ask '
      + 'for changes” and say what should change: that leads back to what the deck says, and '
      + 'the slides are drawn from it again.'));
  }
  if (findings.some((finding) => finding.about === 'concept')) {
    add(node, make('p', 'quiet', '“About how it was approved to teach” is a finding that only '
      + 'another visual concept than the one you approved would put right. Choose “Ask for '
      + 'changes” and say what should change: that leads back to what the deck says and how '
      + 'each slide is drawn.'));
  }
  return node;
}

// What the brand's own check of the finished deck says. A warning is shown as a warning, and
// what the check holds against the deck, or why it could not be run, is said in its own words.
function auditPart(audit) {
  const warnings = list(audit.warnings);
  const held = list(audit.blockers).filter(Boolean);
  const node = add(make('div', 'audit'), make('p', 'row-title', 'The brand’s own check'));
  if (held.length) {
    const against = make('ul', 'look');
    for (const said of held) add(against, add(make('li'), state('late', String(said))));
    add(node, state('late', 'The check did not pass this deck.'), against,
      make('p', 'quiet', 'Approving is still yours to decide. Weigh this first.'));
    if (!warnings.length) return node;
  }
  if (!warnings.length) {
    const status = String(audit.status || '').toLowerCase();
    return add(node, AUDIT_QUIET.includes(status)
      ? state('done', 'It raised no warnings about the brand’s rules.')
      : state('none', 'It listed no warnings' + (status ? ', and answered “' + audit.status
        + '”.' : ', and did not say how it ended.')));
  }
  const items = make('ul', 'look');
  for (const warning of warnings) {
    const often = Number(warning.count) || 0;
    add(items, add(make('li'), state('late', 'Warning: ' + warning.says
      + (often > 1 ? ' (' + often + ' times)' : '')),
    warning.code ? add(make('p', 'quiet'), 'The brand’s name for it: ',
      make('code', '', warning.code)) : null));
  }
  return add(node, state('late', count(warnings.length, 'warning', 'warnings')), items,
    make('p', 'quiet', 'A warning does not stop the deck. It is here for you to weigh.'));
}

// Which slides address each objective: as the reviewer saw it, and as the deck itself says.
function coveragePart(found) {
  const rows = list(found.coverage);
  if (!rows.length) return null;
  const node = make('section', 'paper coverage');
  add(node, make('h2', 'aside-title', 'Which slides address each objective'),
    make('p', '', '“As reviewed” is where the reviewer, looking at the finished slides, found '
      + 'the objective addressed. “As cited” is where the deck itself says a slide serves it. '
      + 'Where the two differ, a slide may not do what it was written to do.'));
  const table = make('table', 'table');
  const head = make('tr');
  for (const title of ['Objective', 'As reviewed', 'As cited']) {
    const top = make('th', '', title);
    top.scope = 'col';
    head.append(top);
  }
  const body = make('tbody');
  const told = (numbers) => (list(numbers).length
    ? make('span', '', capital(slidesNamed(numbers))) : state('late', 'No slide'));
  for (const row of rows) {
    const name = make('th');
    name.scope = 'row';
    add(name, make('span', 'row-title', row.objective),
      row.says ? make('span', 'quiet', row.says) : null);
    add(body, add(make('tr'), name, cell('As reviewed', told(row.reviewed)),
      cell('As cited', told(row.cited))));
  }
  return add(node, add(table, add(make('thead'), head), body));
}

// A screen that could not be read says why, and the way back, where it was being opened. One
// already on the screen stays as it is. Where the page has lost touch, the notice says so too.
function unopened(failure, shown, fresh, about) {
  const spec = about || {};
  if (failure.kind === 'stopped') notify(failure.message);
  if (shown) return;
  place({ title: spec.title || 'This cannot be opened', back: true },
    [make('p', 'problem', failure.message), spec.said ? make('p', 'quiet', spec.said) : null,
      capsule(spec.back || 'Back to home', 'filled', spec.to || (() => show('home')), 'home')],
    fresh);
}

async function drawGate(fresh) {
  const turn = view.turn;
  if (fresh) {
    place({ title: 'Opening', back: true }, [make('p', 'quiet', 'Reading it.')], true);
  }
  try {
    const found = await ask('gate', { path: view.path, artifact: view.artifact });
    if (turn !== view.turn) return;
    await readBeside(found, turn);
    if (turn !== view.turn) return;
    if (!fresh && view.gate && (view.after || view.sheet)) {
      // Someone is in the middle of deciding. A newer version waits until they are done.
      if (found.sha256 !== view.gate.sha256) view.newer = found;
      return;
    }
    if (!fresh && view.gate && found.sha256 !== view.gate.sha256) {
      // Never swap the document under a reader: they say when to see the new one.
      view.newer = found;
      paintGate(false);
      return;
    }
    if (!fresh && view.gate && gateSignature(found) === view.drawn) return;
    view.gate = found;
    view.newer = null;
    paintGate(fresh);
  } catch (failure) {
    if (turn !== view.turn) return;
    unopened(failure, !fresh && view.gate, fresh);
  }
}

// --- one training -----------------------------------------------------------------

function sentenceFor(training) {
  const path = '"' + training.path + '"';
  if (training.error) {
    return 'Use training-studio to look at the training in ' + path
      + '. Its record cannot be read: ' + training.error;
  }
  return 'Use training-studio to resume the training in ' + path
    + ' and tell me what is waiting on me.';
}

function copyState(kind, value) {
  return make('span', 'copy-state', kind + ': ' + (COPY_WORDS[value] || value));
}

function fileRow(training, file) {
  const row = make('tr');
  const name = make('th');
  name.scope = 'row';
  add(name, make('span', 'row-title', file.label));
  const shape = file.waiting ? 'review' : FILE_BEADS[file.status];
  const words = file.waiting ? 'waiting for your review'
    : file.asked ? file.words + ', changes asked for' : file.words;
  const go = capsule(file.status === 'not-started' ? 'Look' : 'Open', 'quiet',
    () => show('gate', { path: training.path, artifact: file.artifact }),
    'file ' + file.artifact);
  go.setAttribute('aria-label', 'Open ' + file.label);
  return add(row, name, cell('Where it is', state(shape, words)),
    cell('File', pathInto(make('span', 'path'), file.file)),
    cell('Copies', file.google_doc ? copyState('Google Doc', file.google_doc) : null,
      file.word_copy ? copyState('Word', file.word_copy) : null,
      !file.google_doc && !file.word_copy ? make('span', 'quiet', 'none kept') : null),
    cell('', go));
}

function filesTable(training, caption, files) {
  const table = make('table', 'table');
  if (caption) add(table, make('caption', 'table-caption', caption));
  const head = make('tr');
  for (const title of ['What', 'Where it is', 'File', 'Copies', '']) {
    const top = make('th', '', title);
    top.scope = 'col';
    if (!title) add(top, make('span', 'offscreen', 'Open'));
    head.append(top);
  }
  const body = make('tbody');
  for (const file of files) body.append(fileRow(training, file));
  return add(table, add(make('thead'), head), body);
}

function filesCard(training) {
  const node = card('Files');
  const files = list(training.view.files);
  const levels = list(training.levels);
  if (!levels.length) return add(node, filesTable(training, '', files));
  add(node, filesTable(training, 'Shared by every level', files.filter((file) => !file.level)));
  for (const level of levels) {
    add(node, filesTable(training, 'Level ' + level,
      files.filter((file) => file.level === level)));
  }
  return node;
}

// A card of reasons, drawn only when there is one to give.
function reasonsCard(title, items) {
  if (!list(items).length) return null;
  return add(card(title), bullets(list(items), 'reasons'));
}

function checksCard(check) {
  const failing = list(check.checks);
  const node = card('Checks');
  add(node, make('p', 'quiet', count(Number(check.passed) || 0, 'check', 'checks') + ' passed.'
    + (failing.length ? '' : ' None failed, and none was unable to run.')));
  for (const outcome of failing) {
    add(node, add(make('div', 'check-outcome'),
      add(make('p', ''), make('code', '', outcome.check), ' ',
        make('span', 'quiet', outcome.status === 'unavailable' ? 'could not run' : 'failed')),
      bullets(list(outcome.problems), 'reasons')));
  }
  return node;
}

function objectives(label, names, exercised) {
  const row = add(make('p', 'foot-line'), make('span', 'quiet', label + ':'));
  if (!names.length) return add(row, make('span', '', 'none'));
  for (const name of names) add(row, state(exercised ? 'done' : 'none', name));
  return row;
}

function practiceCard(training) {
  const report = training.check.practice || {};
  const levels = list(training.levels);
  const node = card('Practice');
  add(node, make('p', 'quiet', 'Which objectives the scenarios exercise. '
    + 'A scenario need not cover them all.'));
  const parts = levels.length
    ? levels.filter((level) => report[level]).map((level) => ['Level ' + level, report[level]])
    : (report.basis ? [['', report]] : []);
  if (!parts.length) {
    return add(node, make('p', 'quiet', 'Nothing to report yet: there is no blueprint and '
      + 'scenario to compare.'));
  }
  for (const [title, part] of parts) {
    add(node, add(make('div', 'practice'), title ? make('p', 'row-title', title) : null,
      objectives('Exercised', list(part.exercised), true),
      objectives('Not exercised', list(part.not_exercised), false),
      make('p', 'quiet', 'Read from the ' + part.basis + '.')));
  }
  return node;
}

function researchCard(status) {
  const node = card('Research');
  const summary = status.research;
  if (!summary) return add(node, make('p', 'quiet', 'There is no research to report yet.'));
  const line = make('p', '');
  if (summary.approved_at) add(line, 'Approved ', when(summary.approved_at));
  else add(line, 'Not approved yet');
  if (summary.run) add(line, ', from run ', make('code', '', summary.run));
  add(node, add(line, '.'));
  const found = Object.entries(summary.findings || {});
  if (found.length) {
    add(node, make('p', 'quiet', 'Findings: '
      + found.map(([kind, number]) => number + ' ' + kind).join(', ') + '.'));
  }
  return node;
}

function guidanceCard(status) {
  const node = card('Guidance');
  const pin = status.guidance;
  if (!pin) {
    return add(node, make('p', 'quiet', 'This training is not pinned to any guidance yet.'));
  }
  const line = make('p', '');
  if (pin.commit) {
    add(line, 'Pinned to commit ', make('code', '', String(pin.commit).slice(0, 12)));
  } else {
    add(line, 'Pinned to the guidance installed with the scripts');
  }
  if (pin.pinned_at) add(line, ', ', when(pin.pinned_at));
  if (pin.runtime) add(line, ', by scripts version ', make('code', '', pin.runtime));
  return add(node, add(line, '.'));
}

// Bring a stage back. Why it could not be is said beside its button, and stays.
async function restore(stage, pressed, problem) {
  if (view.busy) return;
  view.busy = true;
  pressed.disabled = true;
  delete view.unrestored[stage.stage];
  say(problem, '');
  try {
    await send('decide', { path: view.path, artifact: stage.stage, decision: 'restore' });
    toast(stage.name + ' is back.');
    view.busy = false;
    await draw(false);
    refresh();
  } catch (failure) {
    view.unrestored[stage.stage] = failure.message;
    say(problem, failure.message);
    pressed.disabled = false;
    pressed.focus();
  }
  view.busy = false;
}

function decisionsCard(training) {
  const node = card('How this training is decided');
  const theirs = reads(training.path);
  const onPage = training.approval === 'page' && !theirs;
  if (theirs) {
    add(node, make('p', '', whose(training.path)
      ? whose(training.path) + ' runs this training, so each stage is decided on their '
        + 'computer. Here it can be read.'
      : 'Nobody is running this training, so nothing can be decided until someone takes it.'));
  } else if (training.run) {
    // One driver for a training: what the page runs, the page decides.
    add(node, make('p', '', 'This training runs from this page, so each stage is approved '
      + 'here, by you. Nothing can approve it for you.'));
  } else {
    add(node, make('p', '', onPage
      ? 'Each stage is approved on this page. Your assistant cannot approve anything for you.'
      : 'Each stage is approved in your conversation with your assistant. You can move that '
        + 'here, so that only this page can approve.'),
    approvalControl(training.path, training.title || 'Untitled', training.approval,
      () => draw(false)));
  }
  const out = list(training.view.left_out);
  if (out.length) {
    add(node, make('p', 'row-title', 'Left out'));
    const items = make('ul', 'rows');
    for (const stage of out) {
      const problem = alertLine('restore-' + stage.stage + '-problem');
      say(problem, view.unrestored[stage.stage] || '');
      const text = add(make('div', 'row-text'), make('p', '', stage.name
        + (stage.optional ? ' (optional, and off unless you ask for it)' : '')), problem);
      const again = onPage ? capsule(stage.optional ? 'Turn it on' : 'Bring it back', '',
        () => restore(stage, again, problem), 'restore ' + stage.stage) : null;
      if (again) {
        again.setAttribute('aria-label', again.textContent + ': ' + stage.name);
        again.setAttribute('aria-describedby', problem.id);
      }
      add(items, add(make('li', 'row'), bead('out'), text, again));
    }
    add(node, items);
    if (!onPage && !theirs) {
      add(node, make('p', 'quiet', 'To bring one back, ask your assistant.'));
    }
  }
  return node;
}

function folderCard(training) {
  const node = card('Carry on with your assistant');
  const sentence = sentenceFor(training);
  return add(node,
    make('p', 'quiet', 'Start your assistant in this folder:'),
    pathInto(make('p', 'path sentence'), training.path),
    add(make('div', 'bar'), copyButton('Copy the folder', 'Folder copied', training.path,
      'copy-folder')),
    make('p', 'quiet', 'Then say:'),
    make('p', 'sentence', sentence),
    add(make('div', 'bar'), copyButton('Copy the sentence', 'Sentence copied', sentence,
      'copy-sentence')));
}

async function previewTrainingMigration(path) {
  view.migration = null;
  view.migrationError = '';
  view.migrationPath = path;
  openSheet('desk-migration', 'unfinished-desk-open')();
  try {
    const found = await ask('drafts/migration-preview', { path });
    if (view.sheet === 'desk-migration' && view.migrationPath === path) {
      view.migration = found;
      drawSheet();
    }
  } catch (error) {
    if (view.sheet === 'desk-migration') { view.migrationError = error.message; drawSheet(); }
  }
}

function trainingMigrationSheet() {
  const found = view.migration;
  const form = make('form', 'create-flow card');
  const problem = problemLine();
  add(form, make('p', '', 'Keep the saved materials and continue editing in conversation.'));
  if (!found) add(form, make('p', 'quiet', view.migrationError || 'Reading saved work…'));
  else {
    add(form, make('p', '', found.consequences), bullets(found.retained || []));
    if (list(found.blockers).length) add(form, make('p', 'problem', 'Before opening:'), bullets(found.blockers));
  }
  const apply = submitButton('Apply', 'migration-apply');
  apply.disabled = !found || !found.expected || list(found.blockers).length > 0;
  add(form, problem, add(make('div', 'bar create-foot'), apply,
    capsule('Cancel', 'quiet', closeSheet, 'cancel')));
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (apply.disabled) return;
    apply.disabled = true;
    try {
      view.run = await send('drafts/migrate', { path: view.migrationPath, expected: found.expected });
      closeSheet(); show('run', { path: view.migrationPath });
    } catch (error) { say(problem, error.message); apply.disabled = false; }
  });
  return [add(make('div', 'sheet-heading'), sheetTitle('Open on the desk')), form];
}

function openDeskButton(path, kind, unfinished = false) {
  return capsule('Open on the desk', kind, async () => {
    if (unfinished) return previewTrainingMigration(path);
    try {
      await send('drafts/open', { path });
      show('run', { path });
    } catch (failure) { toast(failure.message); }
  }, 'open-desk');
}

function paintTraining(fresh) {
  const training = view.training;
  const above = levelsText(training.levels) ? [make('span', '', levelsText(training.levels))]
    : [];
  if (training.error) {
    place({ title: training.title || 'Untitled', above, back: true },
      [add(card('Its record cannot be read'), make('p', 'problem', training.error),
        make('p', 'quiet', 'Nothing else about this training can be shown until the record is '
          + 'readable again. Your assistant can look at it with you.')),
      folderCard(training)], fresh);
    return;
  }
  const [shape, words] = standingOf(training);
  const waiting = training.waiting;
  // What a teammate runs is read here, never reviewed: the decision is theirs.
  const theirs = reads(training.path);
  const lead = waiting && waiting.artifact ? capsule((theirs ? 'Read ' : 'Review ')
    + waiting.label, theirs ? '' : 'filled',
  () => show('gate', { path: training.path, artifact: waiting.artifact }), 'lead') : null;
  // A training that runs on its own is watched on its run. This view keeps the detail.
  const known = listed(training.path) || training;
  const watch = training.run || watched(known) ? capsule('Watch the run', '',
    () => show('run', { path: training.path }), 'watch') : null;
  const openDesk = training.run && (training.run.can_open_desk || training.run.can_migrate_desk)
    ? openDeskButton(training.path, lead && !theirs ? '' : 'filled', !training.run.can_open_desk) : null;
  place({ title: training.title || 'Untitled', above, back: true, actions: [watch, lead, openDesk] },
    [add(make('div', 'intro'), state(shape, words), beads(training.stages, false),
      make('p', 'lede', saysOf(training)), whoLine(known)),
    adoptCard(known),
    reasonsCard('In the way', training.view.blocking),
    filesCard(training),
    checksCard(training.check),
    reasonsCard('Left out or limited', training.view.limitations),
    reasonsCard('Warnings', training.view.warnings),
    practiceCard(training), researchCard(training.status), guidanceCard(training.status),
    decisionsCard(training),
    // One driver for a training: while the page runs it, nobody is sent to an assistant.
    theirs || training.run ? null : folderCard(training),
    // A training the runner drives can be deleted from here too; one a conversation made
    // is never the runner's to delete.
    training.run && deletable({ mine: known.mine, driver: known.driver,
      finished: (known.run || training.run).state === 'done' }) ? deleteCard() : null], fresh);
}

async function drawTraining(fresh) {
  const turn = view.turn;
  if (fresh) {
    place({ title: 'Opening', back: true }, [make('p', 'quiet', 'Reading the training.')],
      true);
  }
  try {
    const training = await ask('training', { path: view.path });
    if (turn !== view.turn) return;
    const signature = JSON.stringify(training);
    if (!fresh && signature === view.drawn) return;
    view.training = training;
    view.drawn = signature;
    paintTraining(fresh);
  } catch (failure) {
    if (turn !== view.turn) return;
    unopened(failure, !fresh && view.training, fresh);
  }
}

// --- with the runner behind the page ---------------------------------------------------
// Everything from here to "staying up to date" is offered only when the runner answers. On
// the plain desk `view.runner` is false, and none of it is ever shown or asked for.

// Ask, once, whether the runner is here. The plain desk answers 404, and that settles it.
async function discover() {
  try {
    const found = await ask('capabilities');
    view.runner = found.runner === true ? { version: String(found.version || '') } : false;
  } catch (failure) {
    if (failure.status === 404) view.runner = false;
    // No answer at all, or a link that is refused, is not an answer to this: it is asked again.
    else if (failure.kind !== 'failed') throw failure;
  }
}

// The runner is here and nobody has said where the trainings are kept. Until they have,
// set-up is the only screen there is.
function unset() {
  return Boolean(view.runner && view.setup && !view.setup.configured);
}

function frame() {
  const alone = unset();
  byId('sidebar').hidden = alone;
  if (alone) document.body.classList.add('alone');
  else document.body.classList.remove('alone');
}

// The run that is driving a training, or nothing where no run is.
function runOf(path) {
  const found = list(view.listing).find((training) => training.path === path);
  return (found && found.run) || null;
}

function homeOf(path) {
  return watched(listed(path)) ? 'run' : 'training';
}

function asker(path) {
  return runOf(path) ? 'Training Studio asks: ' : 'Your assistant asks: ';
}

function runWords(run) {
  return RUN_WORDS[run.state] || RUN_WORDS.working;
}

// The run has made everything it can, and the one stage that is neither done nor left out is
// the deck's. The list does not say so itself, so it is read from the row of stages.
function deckLeft(training) {
  if (!training.run || training.run.state !== 'done' || training.state !== 'in-progress') {
    return false;
  }
  const open = list(training.stages).filter((stage) => stage.stage !== 'package'
    && !SETTLED.includes(stage.state));
  return open.length === 1 && open[0].stage === 'deck';
}

// Where a training stands, as a shape and words. A run knows more than the list does about
// one that is working, paused or stopped.
function standingOf(training) {
  // What a teammate runs is never said to be working or waiting: that is not known here.
  if (elsewhere(training)) return ['none', 'Run by ' + nameOf(training.driver)];
  if (unclaimed(training)) return ['off', 'Nobody is running it'];
  if (training.standing) {
    return [PHASE_BEADS[training.standing.phase] || 'current', training.standing.words];
  }
  if (deckLeft(training)) return STATES['in-progress'];
  if (training.run && (training.state === 'in-progress' || training.run.state === 'failed')) {
    return runWords(training.run);
  }
  return STATES[training.state] || STATES['in-progress'];
}

function newButton(kind, key) {
  return capsule('New training', kind, () => openNew(key || 'new'), key || 'new');
}

// The new-training sheet, over the screen it was asked from. What was filled in before is
// still there: a draft is kept for the session until the training starts.
function openNew(opener) {
  if (!view.draft) view.draft = newDraft();
  openSheet('new', opener || 'new')();
  readAgents();
  readModels(view.draft.agent);
}

// A section of a sheet that makes something: its number and name, then what it asks.
function createStep(number, title, ...nodes) {
  return add(make('section', 'create-step'), make('h3', 'sheet-part', number + '. ' + title),
    ...nodes);
}

// The list says that a run needs its person. What it asks is read from the run itself: the
// open run's from what its screen last read, and any other's only when what the list says
// of it has changed since it was last read.
async function readAsks() {
  const open = view.screen === 'run' && view.run ? view.path : null;
  const asking = view.listing.filter((training) => training.run
    && training.state === 'needs-you' && !elsewhere(training));
  const asks = {};
  const asked = {};
  const reading = [];
  for (const training of asking) {
    const path = training.path;
    const mark = JSON.stringify(training);
    if (path === open) {
      if (asksOf(view.run)) asks[path] = asksOf(view.run);
    } else if (view.asked[path] === mark) {
      asked[path] = mark;
      if (view.asks[path]) asks[path] = view.asks[path];
    } else {
      reading.push(ask('run', { path }).then((run) => {
        asked[path] = mark;
        if (asksOf(run)) asks[path] = asksOf(run);
      }, () => null));
    }
  }
  await Promise.all(reading);
  view.asks = asks;
  view.asked = asked;
}

// What a run asks of its person, in the few words a list needs. Nothing when it asks nothing.
function asksOf(run) {
  if (!run || !(run.question || run.problem || outlining(run))) return null;
  return { question: run.question || null, problem: run.problem || null,
    outline: outlining(run) ? { level: run.outline.level || null } : null };
}

// A run that has put what a deck says to its person, and waits for the decision.
function outlining(run) {
  return Boolean(run.outline && run.outline.waiting);
}

// What a run asks is only that: to review what a deck says. A question or a problem of its
// own comes first, and is answered where it is asked.
function readsOutline(asked) {
  return Boolean(asked && asked.outline && !asked.question && !asked.problem);
}

// A question from a worker, with a box to answer in. What is typed is kept as it is typed.
function questionBox(path, title, question, kind, id) {
  const key = path + '\n' + question.id;
  const label = add(make('label', 'field-label', 'Your answer'),
    make('span', 'offscreen', ' for ' + title));
  label.htmlFor = id;
  const box = make('textarea', 'input');
  box.id = id;
  box.rows = 3;
  box.maxLength = 10000;
  box.value = view.answers[key] || '';
  box.dataset.key = 'answer ' + key;
  box.setAttribute('aria-describedby', id + '-problem');
  box.addEventListener('input', () => {
    view.answers[key] = box.value;
  });
  const problem = alertLine(id + '-problem');
  const go = capsule('Send answer', kind, () => sendAnswer(path, question, box, problem, go),
    'send ' + key);
  go.setAttribute('aria-label', 'Send answer for ' + title);
  return add(make('div', 'answer'),
    make('p', 'row-says', (question.from || 'A worker') + ' asks:'),
    make('p', 'row-quote', question.text), label, box, problem, add(make('div', 'bar'), go));
}

async function sendAnswer(path, question, box, problem, pressed) {
  const text = box.value.trim();
  if (!text) {
    // Refused here, beside the box, before anything is sent.
    say(problem, 'Write your answer first.');
    box.setAttribute('aria-invalid', 'true');
    box.focus();
    return;
  }
  if (view.busy) return;
  const turn = view.turn;
  view.busy = true;
  pressed.disabled = true;
  try {
    const run = await send('answer', { path, id: question.id, answer: text });
    delete view.answers[path + '\n' + question.id];
    delete view.asks[path];
    view.busy = false;
    toast('Your answer is sent. It carries on from here.');
    if (turn === view.turn && view.screen === 'run' && view.path === path) {
      // The question is gone from the screen: show the run from the top, as it now stands.
      view.run = run;
      paintRun(false);
      window.scrollTo(0, 0);
      byId('title').focus({ preventScroll: true });
    } else if (turn === view.turn && view.screen === 'home') {
      draw(false);
      byId('title').focus({ preventScroll: true });
    }
    refresh();
  } catch (failure) {
    say(problem, failure.message + ' Your answer is still here, and nothing was sent.');
    pressed.disabled = false;
  }
  view.busy = false;
}

// Whether the team can see the work yet, and the way to share it when they cannot.
function sharingLine() {
  const space = view.runner && view.setup ? view.setup.workspace : null;
  if (!space) return null;
  const node = make('p', 'foot-line');
  if (!space.repository) {
    return add(node, make('span', '', 'Your trainings are kept in a folder on this computer, '
      + 'and are not shared with anyone.'));
  }
  if (space.shared) {
    return add(node, state('done', 'Shared: your team can see everything decided so far.'));
  }
  add(node, state(space.notice ? 'late' : 'none', space.notice
    ? 'Not shared with your team yet. ' + space.notice
      + ' The work is kept on this computer until it is.'
    : 'Not shared with your team yet: the latest work is on this computer only.'));
  const go = capsule(view.sharing ? 'Sharing…' : 'Share now', '', shareNow, 'share');
  if (view.sharing) go.setAttribute('aria-busy', 'true');
  return add(node, go);
}

// What teammates have shared is looked for every few minutes. This looks now, and says in
// a sentence what came back.
function fetchLine() {
  if (!teamSpace()) return null;
  const node = make('p', 'foot-line');
  const found = view.fetched;
  add(node, found ? state(found.shape, found.says) : make('span', '', 'What your teammates '
    + 'share is looked for every few minutes.'));
  const go = capsule(view.fetching ? 'Looking…' : 'Look now', 'quiet', fetchNow, 'fetch');
  go.setAttribute('aria-label', view.fetching ? 'Looking for what your teammates shared'
    : 'Look now for what your teammates shared');
  if (view.fetching) go.setAttribute('aria-busy', 'true');
  return add(node, go);
}

async function fetchNow() {
  if (view.fetching) return;
  view.fetching = true;
  draw(false);
  try {
    const found = await send('fetch', {});
    const received = Number(found.received) || 0;
    if (found.reached === false) {
      view.fetched = { shape: 'late', says: 'Nothing new could be brought in. '
        + (found.notice || 'Your team’s repository could not be reached.') };
    } else if (found.notice) {
      view.fetched = { shape: 'late', says: found.notice };
    } else {
      view.fetched = { shape: 'done', says: received ? 'Brought in '
        + count(received, 'change', 'changes') + ' your team shared.'
        : 'Nothing new from your team since the last look.' };
    }
  } catch (failure) {
    view.fetched = { shape: 'late', says: failure.message + ' Nothing was changed.' };
  }
  view.fetching = false;
  draw(false);
  if (!focusKey('fetch')) byId('title').focus({ preventScroll: true });
  refresh();
}

async function shareNow() {
  if (view.sharing) return;
  view.sharing = true;
  draw(false);
  let found;
  try {
    found = await send('share', {});
    toast(found.shared ? 'Shared. Your team can see it now.'
      : 'It is not shared yet. The work is still kept on this computer.');
  } catch (failure) {
    found = { shared: false, notice: failure.message };
    toast('It could not be shared. The work is still kept on this computer.');
  }
  // The set-up may have been read again meanwhile; the answer goes on the one that is held now.
  if (view.setup && view.setup.workspace) {
    view.setup.workspace.shared = Boolean(found.shared);
    view.setup.workspace.notice = found.notice || null;
  }
  view.sharing = false;
  draw(false);
  if (!focusKey('share')) byId('title').focus({ preventScroll: true });
}

function about(pairs) {
  const node = make('dl', 'about');
  for (const [name, value] of pairs) {
    if (given(value) && value !== '') add(node, make('dt', '', name), make('dd', '', value));
  }
  return node;
}

function limitsSays(limits) {
  const says = [];
  if (limits.step_seconds) says.push('A step may take up to ' + lasted(limits.step_seconds) + '.');
  if (given(limits.training_dollars)) {
    says.push('A training stops and asks you once it has spent '
      + money(limits.training_dollars) + '.');
  }
  if (limits.parallel) {
    says.push(limits.parallel === 1 ? 'One training runs at a time.'
      : 'Up to ' + limits.parallel + ' trainings run at once.');
  }
  return says.join(' ');
}

// Settings, with the runner: where the trainings are kept, who can see them, and the way in
// to change any of it.
function workspaceCard() {
  const held = view.runner ? view.setup : null;
  const space = held && held.workspace;
  if (!space) return null;
  const node = card('Workspace');
  const agent = held.agent || {};
  add(node, make('p', 'row-title', space.name || 'Your trainings'),
    about([[space.repository ? 'Repository' : 'Folder on this computer',
      space.repository || space.path],
    [space.repository ? 'This computer’s copy' : '', space.repository ? space.path : ''],
    ['Folder inside it', space.folder], ['Branch', space.branch],
    ['Shared', space.repository ? lower(SHARE_SAYS[space.share_when === 'when-asked' ? 1 : 0])
      : ''],
    ['Drafting is done by', (AGENT_NAMES[agent.default] || agent.default || 'no agent yet')
      + (held.shared?.models?.mode === 'by_task' ? ', using Quick, Main, and Complex model profiles' : modelWords(agent.model, agent.effort, true))],
    ['Limits', limitsSays(held.limits || {})],
    ['Slide previews', held.previews ? previewsSays(held.previews) : '']]),
    sharingLine(), fetchLine(),
    add(make('div', 'bar'), capsule('Change the set-up', '', () => show('setup'), 'setup')));
  return node;
}

// How previews are made, as it can be on this computer now: the way that was chosen, or
// else the first way there is, or nothing where there is none. Drive is not asked about
// while LibreOffice makes them, and a way not asked about is still offered.
function previewsNow(found) {
  const can = PREVIEWS.filter((how) => found[how] || found[how] === null);
  return can.includes(found.how) ? found.how : can[0] || null;
}

// How previews are made as it is set now, in a few words for Settings.
function previewsSays(found) {
  if (found.how) {
    return PREVIEW_WORDS[found.how] + (found[found.how] ? ''
      : ', which this computer cannot do now');
  }
  return found.drive || found.local ? 'not chosen yet: choose how in the set-up'
    : 'cannot be made on this computer yet';
}

// The preview files Training Studio made in the person's Drive. It never deletes one, so
// each is listed with where it is, for the person to remove.
function leftCard() {
  const found = view.runner && view.setup ? view.setup.previews : null;
  const left = list(found && found.left);
  if (!found || (!left.length && found.how !== 'drive')) return null;
  const node = card('Preview files in your Google Drive');
  add(node, make('p', '', pooled() ? 'Previews made through Google Drive are drawn in a few '
    + 'shared presentations there, named “Preview: …”, and reused by every deck. Training '
    + 'Studio never deletes them, so removing them is yours to do, in Drive.'
    : 'A deck whose previews are made through Google Drive keeps one '
    + 'presentation there, named “Preview: …”. Training Studio never deletes one, so '
    + 'removing them is yours to do, in Drive, once a deck is finished.'));
  if (!left.length) return add(node, make('p', 'quiet', 'It has made none so far.'));
  const items = make('ul', 'rows');
  for (const file of left) {
    const text = add(make('div', 'row-text'), make('p', 'step-name', file.name),
      make('p', 'quiet', 'Made for ' + file.training));
    // Only a web address is a link to follow. Anything else is shown as the text it is.
    if (WEB_LINK.test(file.url || '')) {
      const go = make('a', 'link', 'Open it in Drive');
      go.href = file.url;
      go.rel = 'noopener noreferrer';
      go.target = '_blank';
      go.setAttribute('aria-label', 'Open ' + file.name + ' in Drive, in a new tab');
      add(text, add(make('p', ''), go));
    }
    add(items, add(make('li', 'row'), add(text, pathInto(make('p', 'path'), file.url || ''))));
  }
  return add(node, items);
}

// --- set-up ------------------------------------------------------------------------
// Shown first where nothing is set up yet, and from Settings afterwards. Each answer about
// where the trainings are kept is checked as it is given, and nothing is changed until Save.

function setupForm() {
  const held = view.setup;
  // Joining the team repository every studio now shares starts from it, not from the
  // workspace this computer has.
  const joining = view.joining;
  view.joining = false;
  const space = (!joining && held.workspace) || {};
  const limits = held.limits || {};
  const shared = sharedOf();
  const team = shared.team || {};
  // The agent is one of the values every studio shares, so the runner reads it from their
  // file. The team repository fills in only where this computer keeps none.
  const agent = held.agent || {};
  const local = !joining && Boolean(held.workspace) && !space.repository;
  const seconds = Number(limits.step_seconds) || 0;
  const share = space.share_when || (shared.share === 'asked' ? SHARE[1] : SHARE[0]);
  return {
    where: local ? 1 : 0,
    repository: space.repository || team.repository || '',
    path: local ? space.path || '' : '',
    folder: space.folder || '',
    branch: space.branch || '',
    name: space.name || '',
    touched: { folder: Boolean(space.folder), branch: Boolean(space.branch),
      name: Boolean(space.name) },
    team: space.repository ? {} : team,
    share: share === SHARE[1] ? 1 : 0,
    // The values every studio shares as this form was shown them, sent back with it so
    // that one another studio changes meanwhile is never written over.
    seen: 'shared' in held ? shared : null,
    agent: agent.default === 'codex' ? 'codex' : 'claude',
    model: agent.model || '', other: false, effort: agent.effort || '',
    minutes: seconds ? String(Math.round(seconds / 6) / 10) : '', seconds,
    dollars: given(limits.training_dollars) ? String(limits.training_dollars) : '',
    parallel: given(limits.parallel) ? String(limits.parallel) : '',
    previews: previewsNow(held.previews || {}),
    brandSkill: (brandSkills().find((skill) => skill.chosen) || brandSkills()[0] || {}).path
      || '',
    check: null, checked: '', checking: false, unchecked: '', existing: false, turn: 0,
    saving: false,
  };
}

// What is asked of the check: exactly where the trainings would be kept, and nothing else.
// A folder or a branch that nobody has chosen is not asked about: the check says what it found.
function placeAsked(form) {
  const text = (value) => String(value).trim() || null;
  const chosen = (name) => (form.touched[name] || form.existing ? text(form[name]) : null);
  return { repository: form.where ? null : text(form.repository),
    path: form.where ? text(form.path) : null,
    folder: chosen('folder'), branch: chosen('branch') };
}

// A different place was named. What was found in the last one says nothing about this one.
function forgetFound(form) {
  for (const name of ['folder', 'branch', 'name']) {
    if (!form.existing && form.touched[name]) continue;
    form[name] = '';
    form.touched[name] = false;
  }
  form.existing = false;
  form.check = null;
}

function checkItem(found) {
  const item = add(make('li', 'check-item'), add(make('p', 'fact'),
    bead(found.ok ? 'done' : 'late'),
    make('span', '', found.what + (found.ok ? ': yes' : ': no'))));
  if (!found.ok && found.fix) add(item, make('p', 'fix', found.fix));
  return item;
}

function paintChecks() {
  const form = view.form;
  const holder = byId('setup-checks');
  if (!form || !holder) return;
  const nodes = [];
  if (form.checking) {
    nodes.push(make('p', 'quiet', 'Checking…'));
  } else if (form.unchecked) {
    nodes.push(make('p', 'problem', 'This could not be checked. ' + form.unchecked),
      make('p', 'quiet', 'Nothing was changed. Try “Check again”.'));
  } else if (form.check) {
    const checks = list(form.check.checks);
    const wrong = checks.filter((found) => !found.ok).length;
    const items = make('ul', 'plain check-items');
    for (const found of checks) items.append(checkItem(found));
    nodes.push(items, form.check.ok
      ? state('done', 'This is ready to use.')
      : state('late', (wrong ? count(wrong, 'thing needs', 'things need') : 'Something needs')
        + ' putting right before this can be saved. Then choose “Check again”.'));
  } else {
    nodes.push(make('p', 'quiet', form.where
      ? 'It is checked as soon as you say which folder.'
      : 'It is checked as soon as you give the address.'));
  }
  holder.replaceChildren(...nodes);
}

// What the check found is filled in. Where the team has already set Training Studio up in
// the repository, its folder, branch and name are theirs, and are not asked for again.
function fillFound(found) {
  const form = view.form;
  form.existing = Boolean(found.existing);
  for (const name of ['folder', 'branch', 'name']) {
    const box = byId('setup-' + name);
    if (found[name] && (form.existing || !form.touched[name])) form[name] = String(found[name]);
    // The branch every studio shares is the one for a new workspace in the team repository.
    // A workspace the team has set up already keeps the branch its hub.json names.
    if (name === 'branch' && sharedBranch(form)) form.branch = form.team.branch;
    if (!box) continue;
    box.value = form[name];
    box.readOnly = form.existing;
  }
  const note = byId('setup-found');
  if (!note) return;
  note.hidden = !form.existing;
  note.replaceChildren(...(form.existing ? [make('p', '', 'Training Studio is already set up '
    + 'in this repository' + (found.name ? ', as “' + found.name + '”' : '') + '. Its folder, '
    + 'branch and name are read from the hub.json your team keeps there, so there is nothing '
    + 'to choose here.')] : []));
}

// Whether the branch every studio shares is the one to fill in: for the team repository they
// share, when nobody has named a branch here and the repository has none of its own yet.
function sharedBranch(form) {
  return Boolean(form.team.branch && !form.where && !form.existing && !form.touched.branch
    && form.repository.trim() === form.team.repository);
}

async function checkSetup() {
  const form = view.form;
  const asked = placeAsked(form);
  form.turn += 1;
  const turn = form.turn;
  form.unchecked = '';
  if (!asked.repository && !asked.path) {
    form.check = null;
    form.checking = false;
    fillFound({});
    paintChecks();
    return false;
  }
  form.checking = true;
  paintChecks();
  try {
    const found = await send('setup/check', asked);
    if (view.form !== form || turn !== form.turn) return false;
    form.check = found;
    fillFound(found.found || {});
  } catch (failure) {
    if (view.form !== form || turn !== form.turn) return false;
    form.check = null;
    form.unchecked = failure.message;
  }
  form.checked = JSON.stringify(placeAsked(form));
  form.checking = false;
  paintChecks();
  return Boolean(form.check && form.check.ok);
}

// An agent, as the runner found it: installed, signed in, reachable from this network.
function agentItem(found) {
  const yes = (value, unknown) => (value === true ? ['ok', ''] : value === false
    ? ['problem', 'no'] : ['unknown', unknown]);
  const facts = [{ label: 'Installed', state: found.installed ? 'ok' : 'problem',
    detail: found.installed ? found.version || '' : 'not found' }];
  if (found.installed) {
    const [signed, signedSays] = yes(found.signed_in, 'cannot be asked');
    const [reached, reachedSays] = yes(found.reachable, 'not known');
    facts.push({ label: 'Signed in', state: signed, detail: signedSays },
      { label: 'Reachable from this network', state: reached, detail: reachedSays });
  }
  const usable = found.installed && found.signed_in !== false && found.reachable !== false
    && !found.problem;
  return computerItem({ name: AGENT_NAMES[found.agent] || found.agent,
    state: usable ? 'ok' : found.installed ? 'problem' : 'missing', facts,
    fix: found.problem || '' });
}

function paintAgents() {
  const holder = byId('agents');
  if (!holder) return;
  const nodes = [];
  if (view.looking && !view.agents) {
    nodes.push(make('p', 'quiet', 'Looking for the agents on this computer…'));
  } else if (view.unlooked) {
    nodes.push(make('p', 'problem', 'The agents could not be looked for. ' + view.unlooked),
      make('p', 'quiet', 'Nothing was changed. Try “Look again”.'));
  } else if (view.agents) {
    const items = make('ul', 'computer-items');
    for (const found of view.agents) items.append(agentItem(found));
    nodes.push(items);
    if (!view.agents.length) {
      nodes.push(make('p', 'problem', 'No agent was found on this computer. Install Claude '
        + 'Code or Codex, sign in to it, then choose “Look again”.'));
    }
  }
  holder.replaceChildren(...nodes);
}

async function readAgents() {
  if (view.looking) return;
  view.looking = true;
  paintAgents();
  try {
    view.agents = list((await ask('agents')).agents);
    view.unlooked = '';
  } catch (failure) {
    view.unlooked = failure.message;
  }
  view.looking = false;
  paintAgents();
}

// A reasoning level as a person would say it.
function levelName(level) {
  return LEVEL_NAMES[level] || spoken(level);
}

// The model and the reasoning level, in words that follow an agent's name. With `own`, a
// model left to the agent is said so.
function draftModelWords(draft) {
  const held = view.setup?.agent || {};
  return view.setup?.shared?.models?.mode === 'by_task' && draft.agent === held.default
    && draft.model.trim() === (held.model || '') && draft.effort === (held.effort || '')
    ? ', using Quick, Main, and Complex model profiles'
    : modelWords(draft.model.trim(), draft.effort, true);
}

function modelWords(model, effort, own) {
  const level = effort ? 'reasoning set to ' + lower(levelName(effort)) : '';
  if (model || own) {
    return ', with the model ' + (model || 'it chooses itself') + (level ? ' and ' + level : '');
  }
  return level ? ', with ' + level : '';
}

// What the runner listed for an agent: its models, and the levels a model it does not list
// may be given. Nothing while it is being asked, or where it could not be listed.
function listedFor(agent) {
  const found = view.models[agent];
  return found && found.models ? found : null;
}

// The levels the chosen model takes, or null while that is not known.
function levelsFor(held) {
  const found = listedFor(held.agent);
  if (!found) return null;
  const model = held.other ? null : found.models.find((one) => one.name === held.model);
  return list(model ? model.levels : found.levels);
}

// Hold a choice to what the agent listed: a model it does not list is typed in as another,
// and a level the model does not take is left to the agent again.
function settlePick(held) {
  const found = listedFor(held.agent);
  if (!found) return;
  if (held.model && !found.models.some((one) => one.name === held.model)) held.other = true;
  if (held.effort && !levelsFor(held).includes(held.effort)) held.effort = '';
}

// Ask the runner which models an agent has. It is asked apart from the page's refresh and
// holds nothing up: the choice is drawn again when the list comes. A list is asked for once,
// and one that could not be made again a minute later, or at once with `again`.
async function readModels(agent, again) {
  const known = view.models[agent];
  if (known && (known.asking || known.models
    || (!again && Date.now() - known.at < MODELS_AGAIN))) return;
  view.models[agent] = { asking: true };
  paintPick();
  let found;
  try {
    found = await ask('models', { agent });
  } catch (failure) {
    found = { problem: failure.message };
  }
  view.models[agent] = found.problem ? { problem: String(found.problem), at: Date.now() }
    : { models: list(found.models).filter((one) => one && typeof one.name === 'string'),
      levels: list(found.levels), source: found.source || '' };
  paintPick();
}

function paintPick() {
  if (!view.picking) return;
  settlePick(view.picking.held);
  view.picking.fill();
}

// The model, from the agent's own list, and how hard it reasons, from the levels that model
// takes. Models of one family are a group, and what the agent says of a model follows its
// name. "Another model…" is for a name the list does not have, and stays where the list
// could not be made. A model that takes no level is offered none.
function modelFields(held, prefix, fill, told) {
  const name = AGENT_NAMES[held.agent] || held.agent;
  const known = view.models[held.agent] || { asking: true };
  const found = listedFor(held.agent);
  const listed = found ? found.models : [];
  const model = held.other ? null : listed.find((one) => one.name === held.model);
  const options = [['', OWN_CHOICE], ...listed.map((one) => [one.name,
    (one.label || one.name) + (one.about ? ': ' + one.about : ''), one.family || ''])];
  // Until the list comes, a model already chosen is offered as it is.
  if (!found && held.model && !held.other) options.push([held.model, held.model]);
  options.push([OTHER_MODEL, 'Another model…']);
  const pick = { model: held.other ? OTHER_MODEL : held.model };
  const nodes = [field(prefix + '-model', 'Its model', pick, 'model', { options,
    changed: () => {
      if (pick.model === OTHER_MODEL) {
        if (!held.other && found) held.model = '';
        held.other = true;
      } else {
        held.other = false;
        held.model = pick.model;
      }
      settlePick(held);
      fill();
    },
    hint: 'As ' + (found && found.source ? 'the ' + found.source + ',' : name) + ' lists '
      + 'them. Its own choice is the model it uses when none is named.' })];
  if (known.asking) {
    nodes.push(make('p', 'quiet', 'Asking ' + name + ' which models it has…'));
  } else if (!found) {
    const problem = make('p', 'problem', name + '’s models could not be listed. '
      + known.problem);
    problem.setAttribute('role', 'status');
    nodes.push(problem, make('p', 'quiet', 'Choose “Another model…” to give one by its name, '
      + 'or try “Look again”.'));
  }
  if (held.other) {
    nodes.push(field(prefix + '-model-name', 'The model’s name', held, 'model', { typed: told,
      hint: 'As ' + name + ' knows it, with no spaces.' }));
  }
  const levels = levelsFor(held);
  if (model && !list(model.levels).length) {
    nodes.push(make('p', 'quiet', (model.label || model.name) + ' takes no reasoning level.'));
    return nodes;
  }
  const usual = model && model.default_level
    ? ' (' + lower(levelName(model.default_level)) + ')' : '';
  const choices = [['', OWN_CHOICE + usual], ...list(levels).map((level) => [level,
    levelName(level)])];
  if (!levels && held.effort) choices.push([held.effort, levelName(held.effort)]);
  nodes.push(field(prefix + '-effort', 'Its reasoning level', held, 'effort', {
    options: choices, changed: told,
    hint: 'How much it thinks before it answers: more is slower, and costs more. Only the '
      + 'levels this model takes are offered.' }));
  return nodes;
}

// Which agent, which of its models, and how hard it reasons. The same questions are asked at
// set-up, for the default, and at the last step of a new training, for that training.
// `told` is called whenever the answer changes.
function agentFields(held, prefix, label, told) {
  const found = make('div', 'agents');
  found.id = 'agents';
  found.setAttribute('role', 'status');
  const picks = make('div', 'fields');
  settlePick(held);
  const fill = () => {
    const active = document.activeElement;
    const focused = active && active.dataset && picks.contains(active) ? active.dataset.key : '';
    picks.replaceChildren(...modelFields(held, prefix, fill, told));
    if (focused) focusKey(focused);
    if (told) told();
  };
  view.picking = { held, fill };
  fill();
  return [found,
    add(make('div', 'bar'), capsule('Look again', 'quiet', () => {
      readAgents();
      readModels(held.agent, true);
    }, 'agents-again')),
    choice(label, AGENTS.map((name) => AGENT_NAMES[name]), AGENTS.indexOf(held.agent),
      (index) => {
        held.agent = AGENTS[index];
        held.model = '';
        held.other = false;
        settlePick(held);
        fill();
        readModels(held.agent);
      }, prefix + '-agent'),
    picks];
}

function placeCard(form) {
  const node = card('Where your trainings are kept');
  const again = () => {
    checkSetup();
  };
  const moved = () => {
    forgetFound(form);
    checkSetup();
  };
  add(node, choice('Kept in', ['A team repository', 'A folder on this computer'], form.where,
    (index) => {
      form.where = index;
      forgetFound(form);
      paintSetup(false);
      checkSetup();
    }, 'where'));
  if (form.where) {
    add(node, field('setup-path', 'The folder', form, 'path', { changed: moved,
      hint: 'A folder on this computer, for trying things out. Nothing in it is shared with '
        + 'anyone.' }));
  } else {
    add(node, field('setup-repository', 'The repository’s address', form, 'repository', {
      changed: moved,
      hint: 'The address you would clone it from. Training Studio keeps a copy of its own on '
        + 'this computer, and writes inside one folder of the repository and nowhere else.' }));
  }
  const found = make('div', 'paper callout');
  found.id = 'setup-found';
  found.hidden = true;
  const touch = (name) => () => {
    form.touched[name] = true;
  };
  add(node, found,
    field('setup-folder', 'The folder inside it', form, 'folder', { changed: again,
      typed: touch('folder'), hint: 'Everything Training Studio writes goes in this folder.' }),
    field('setup-branch', 'The branch', form, 'branch', { changed: again,
      typed: touch('branch') }),
    field('setup-name', 'A name for this workspace', form, 'name', { typed: touch('name'),
      hint: 'What your team calls this collection of trainings: a short name with no '
        + 'spaces, such as field-training.' }));
  const checks = make('div', 'checks');
  checks.id = 'setup-checks';
  checks.setAttribute('role', 'status');
  return add(node, add(make('fieldset', 'checked'), make('legend', 'field-label',
    'Checked for you'), checks,
  add(make('div', 'bar'), capsule('Check again', 'quiet', again, 'check-again'))));
}

// What every studio on this computer shares, as the runner read it, or nothing from a runner
// that does not read it.
function sharedOf() {
  return (view.setup && view.setup.shared) || {};
}

// The file every studio shares, said once and plainly: the values in it are theirs, so a
// change saved here is a change for all of them.
function studiosCard() {
  const held = view.setup;
  if (!held || !('shared' in held)) return null;
  return add(card('Your other studios'),
    make('p', '', 'The team repository, when to share and the agent, with its model and '
      + 'level, are shared by every studio on this computer, in one file, ' + STUDIOS_FILE
      + '. Saving here changes them for Presentation Studio and Blog Studio too. Nothing '
      + 'secret is written there.'),
    held.shared_problem ? make('p', 'problem', held.shared_problem) : null);
}

// What Home and Status say of the file every studio shares: the team repository it now
// names, when this computer works in another, and what moving to it left as it was. Status
// also says when it could not be read. Nothing waits on any of them.
function studiosParts(problem) {
  const held = view.runner && view.setup;
  if (!held) return [];
  const parts = [];
  if (problem && held.shared_problem) parts.push(make('p', 'problem', held.shared_problem));
  const moved = held.team_moved;
  if (moved && moved.says) {
    parts.push(make('p', '', moved.says), add(make('div', 'bar'),
      capsule('Join it', '', joinShared, 'join-shared')));
  }
  if (held.shared_notice) {
    parts.push(make('p', '', held.shared_notice), add(make('div', 'bar'),
      capsule('Got it', 'quiet', sharedSeen, 'shared-seen')));
  }
  return parts;
}

function studiosMark() {
  const held = (view.runner && view.setup) || {};
  return [Boolean(view.runner), held.shared_problem, (held.team_moved || {}).says,
    held.shared_notice];
}

// Set-up, filled in with the team repository every studio now shares.
function joinShared() {
  view.joining = true;
  show('setup');
}

async function sharedSeen() {
  try {
    view.setup = await send('shared', { seen: true });
  } catch (failure) {
    toast(failure.message);
    return;
  }
  draw(false);
}

function shareCard(form) {
  return add(card('When your team sees the work'), ...explained('Share',
    ['After each decision', 'Only when I ask'], SHARE_SAYS, form.share, (index) => {
      form.share = index;
    }, 'share-when'));
}

function limitsCard(form) {
  const node = card('Limits');
  return add(node, make('p', '', 'These keep a training from running away with your time or '
    + 'your money. A training that reaches one stops and asks you.'),
  field('setup-minutes', 'The longest a step may take, in minutes', form, 'minutes',
    { short: true, mode: 'decimal' }),
  field('setup-dollars', 'The most a training may spend, in dollars', form, 'dollars',
    { short: true, mode: 'decimal', hint: 'Counted where the agent says what it spends.' }),
  field('setup-parallel', 'How many trainings may run at once', form, 'parallel',
    { short: true, mode: 'numeric' }));
}

// The brand skills found on this computer, each as the runner names it and where it is.
function brandSkills() {
  return list(((view.setup || {}).brand || {}).skills).filter((skill) => skill && skill.path);
}

// Which brand skill decks are made with. It is a choice only where more than one was found.
// Two with one name are told apart by where each is.
function brandSkillCard(form) {
  const skills = brandSkills();
  if (skills.length < 2) return null;
  const twice = (name) => skills.filter((skill) => skill.name === name).length > 1;
  return add(card('The brand skill decks are made with'),
    make('p', '', 'A slide deck is always made in a brand, and a brand skill holds the '
      + 'brands. More than one was found on this computer.'),
    oneOf('setup-brand-skill', 'Use this brand skill', skills.map((skill) => [skill.path,
      (skill.name || skill.path) + (twice(skill.name) ? ' (' + skill.path + ')' : '')]),
    form, 'brandSkill'),
    make('p', 'quiet field-hint', 'A new training offers the brands of the one chosen here.'));
}

// How the pictures of a deck's slides are made. Each way says what it means, and a way this
// computer cannot do says so and cannot be chosen.
function previewsCard(form) {
  const found = view.setup.previews;
  if (!found) return null;
  const node = card('How slide previews are made');
  add(node, make('p', '', 'While a slide deck is drawn, each slide is turned into a picture, '
    + 'so that it can be looked at and put right before it comes to you. A deck cannot be '
    + 'made without them.'));
  if (!form.previews) {
    return add(node, state('late', 'This computer cannot make them yet.'),
      make('p', 'fix', 'It needs LibreOffice, or Google access that reaches Drive. Everything '
        + 'but the deck can be made meanwhile, and the Status screen says what a deck needs.'));
  }
  const [control, meanings] = explained('Make them with', PREVIEW_NAMES, previewSays(),
    PREVIEWS.indexOf(form.previews), (index) => {
      form.previews = PREVIEWS[index];
    }, 'previews');
  add(node, control, meanings);
  PREVIEWS.forEach((how, index) => {
    if (found[how] || found[how] === null) return;
    const option = control.querySelectorAll('.seg-option')[index];
    option.disabled = true;
    option.classList.add('seg-absent');
    add(node, make('p', 'fix', PREVIEW_ABSENT[index]));
  });
  if (found.how && found.how !== form.previews) {
    add(node, make('p', 'problem', PREVIEW_NAMES[PREVIEWS.indexOf(found.how)] + ' was chosen '
      + 'before, and this computer cannot use it now. Save to use the other way.'));
  }
  return node;
}

function paintSetup(fresh) {
  const form = view.form;
  const first = !view.setup.configured;
  view.drawn = 'setup';
  const problem = alertLine('setup-problem');
  const save = submitButton(first ? 'Save and go on' : 'Save', 'save');
  const intro = add(make('div', 'intro'),
    first ? make('p', 'large-title', 'Welcome. Let’s get you set up.') : null,
    make('p', 'lede', 'Say where your team keeps its trainings and which agent does the '
      + 'drafting. Each answer is checked as you give it, and nothing is changed until you '
      + 'save.' + (first ? ' Then you can start your first training.' : '')));
  // The set-up is a form, so Enter in a box saves as the filled button does.
  const body = add(pageForm(() => saveSetup(save)), intro, placeCard(form),
    form.where ? null : shareCard(form),
    add(card('The agent that does the drafting'),
      make('p', '', 'An agent is the AI that drafts each stage for you to decide on. It has '
        + 'to be installed on this computer and signed in.'),
      ...agentFields(form, 'setup', 'Use by default')),
    studiosCard(), brandSkillCard(form), previewsCard(form), limitsCard(form),
    add(make('div', 'form-foot'), problem, add(make('div', 'bar'), save,
      first ? null : capsule('Cancel', 'quiet', back, 'cancel'))));
  place({ title: first ? 'Set up Training Studio' : 'Set-up', name: 'Set-up',
    above: first ? [] : [make('span', '', 'Settings')], back: !first }, [body], fresh);
  fillFound((form.check && form.check.found) || (form.existing ? { existing: true } : {}));
  paintChecks();
  paintAgents();
}

function drawSetup(fresh) {
  if (!fresh && view.drawn === 'setup') return;
  if (!view.form) view.form = setupForm();
  paintSetup(true);
  checkSetup();
  readAgents();
  readModels(view.form.agent);
}

// A limit as a number, or nothing when what was typed is not one that can be used.
function limit(id, text, whole) {
  const value = Number(String(text).trim());
  const fine = String(text).trim() !== '' && Number.isFinite(value) && value > 0
    && (!whole || Number.isInteger(value));
  refuse(id, fine ? '' : whole ? 'Give a whole number, 1 or more.'
    : 'Give a number greater than 0.');
  return fine ? value : null;
}

async function saveSetup(pressed) {
  const form = view.form;
  if (form.saving) return;
  const problem = byId('setup-problem');
  say(problem, '');
  const asked = placeAsked(form);
  const where = form.where ? 'setup-path' : 'setup-repository';
  const missing = [];
  const need = (id, value, text) => {
    if (!refuse(id, value ? '' : text).getAttribute('aria-invalid')) return;
    missing.push(id);
  };
  need(where, asked.repository || asked.path, form.where ? 'Say which folder first.'
    : 'Give the repository’s address first.');
  const minutes = limit('setup-minutes', form.minutes, false);
  const dollars = limit('setup-dollars', form.dollars, false);
  const parallel = limit('setup-parallel', form.parallel, true);
  for (const [id, value] of [['setup-minutes', minutes], ['setup-dollars', dollars],
    ['setup-parallel', parallel]]) {
    if (value === null) missing.push(id);
  }
  if (missing.length) {
    say(problem, 'Something above is missing. Nothing was saved.');
    byId(missing[0]).focus();
    return;
  }
  form.saving = true;
  pressed.disabled = true;
  const done = (text) => {
    form.saving = false;
    pressed.disabled = false;
    say(problem, text);
    if (text) pressed.focus();
  };
  // Never save a place that has not been checked as it now stands.
  if (form.checking || !form.check || form.checked !== JSON.stringify(asked)) await checkSetup();
  if (view.form !== form) return;
  if (!form.check || !form.check.ok) {
    done('Where your trainings are kept needs putting right first: see “Checked for you” '
      + 'above. Nothing was saved.');
    return;
  }
  for (const [name, text] of [['folder', 'Say which folder inside it.'],
    ['branch', 'Say which branch.'], ['name', 'Give it a name.']]) {
    need('setup-' + name, form[name].trim(), text);
  }
  // What the repository already says is taken as it is. What was typed here has to be plain.
  for (const name of form.existing ? [] : ['folder', 'name']) {
    const id = 'setup-' + name;
    if (missing.includes(id) || PLAIN_NAME.test(form[name].trim())) continue;
    refuse(id, PLAIN_SAYS);
    missing.push(id);
  }
  if (missing.length) {
    done('Something above is missing or cannot be used. Nothing was saved.');
    byId(missing[0]).focus();
    return;
  }
  // Minutes are shown to the nearest tenth. A time nobody changed is saved as it was.
  const kept = form.seconds && minutes === Math.round(form.seconds / 6) / 10;
  const body = { folder: form.folder.trim(), branch: form.branch.trim(),
    name: form.name.trim(), share_when: form.where ? SHARE[1] : SHARE[form.share],
    agent: form.agent, model: form.model.trim() || null, effort: form.effort || null,
    limits: { step_seconds: kept ? form.seconds : Math.max(1, Math.round(minutes * 60)),
      training_dollars: dollars, parallel } };
  if (form.where) body.path = asked.path;
  else body.repository = asked.repository;
  // Where this computer can make previews in neither way, there is no choice to send.
  if (form.previews) body.previews = form.previews;
  // With one brand skill, or none, there is nothing to choose and nothing to send.
  if (brandSkills().length > 1 && form.brandSkill) body.brand_skill = form.brandSkill;
  // The computer's own notification is switched in Settings, and is saved as it stands.
  if (view.setup.notify) body.notify = Boolean(view.setup.notify.on);
  if (form.seen) body.shared_seen = form.seen;
  const first = !view.setup.configured;
  // Where the workspace is, to tell whether the runner moved it before it refused.
  const placed = () => {
    const space = view.setup.workspace || {};
    return JSON.stringify([space.repository || null, space.path || null]);
  };
  const workspace = placed();
  try {
    view.setup = await send('setup', body);
  } catch (failure) {
    const anew = await lookAgain(form);
    // A workspace joined before another studio's change was found is said by the runner.
    const said = failure.message + (placed() !== workspace
      ? ' Your other answers are still here: save again.'
      : ' Nothing was saved, and your answers are still here: change what it names and '
        + 'save again.');
    if (anew === null) {
      done(said);
      return;
    }
    // What another studio changed is shown as it is now, so the form is drawn again.
    form.saving = false;
    paintSetup(false);
    readModels(form.agent);
    say(byId('setup-problem'), said + anew);
    focusKey('save');
    return;
  }
  form.saving = false;
  frame();
  toast(first ? 'You are set up. Now start your first training.' : 'The set-up is saved.');
  if (first || view.pushed === 0) show(first ? 'home' : 'settings', null, true);
  else back();
}

// After a refusal, set-up reads again what every studio shares, as the brand skill's form
// does. Each value another studio changed while the form was open is shown as it is now, and
// the form counts as having been shown it, so saving again is the person's choice over it.
// Answers what to add to the refusal, or null where nothing was changed elsewhere.
async function lookAgain(form) {
  if (!form.seen) return null;
  let found;
  try {
    found = await ask('setup');
  } catch (failure) {
    return null;
  }
  tookSetup(found);
  if (view.form !== form || !('shared' in found)) return null;
  const was = form.seen;
  const now = sharedOf();
  const same = (one, other) => JSON.stringify(one || {}) === JSON.stringify(other || {});
  if (same(was, now)) return null;
  form.seen = now;
  if (!same(was.assistant, now.assistant)) {
    const agent = found.agent || {};
    form.agent = agent.default === 'codex' ? 'codex' : 'claude';
    form.model = agent.model || '';
    form.effort = agent.effort || '';
    form.other = false;
  }
  if ((was.share || 'decision') !== (now.share || 'decision')) {
    form.share = now.share === 'asked' ? 1 : 0;
  }
  const team = (now.team || {}).repository;
  return team && team !== (was.team || {}).repository
    ? ' The team repository every studio shares is now ' + team + '.' : '';
}

// --- a new training ------------------------------------------------------------------
// Three short steps, with a default for every choice. Nothing is sent until the last one.

function newDraft() {
  const agent = (view.setup && view.setup.agent) || {};
  // The brand, its variant and Google Slides come from what every studio shares, where the
  // brand skill here has them.
  const shared = sharedOf();
  const brand = shared.brand || {};
  return settleDeck({ step: 0, title: '', topic: '', audience: '', purpose: 0,
    levels: ['101'], brief: 0, time: '',
    // A deck needs a brand; without one shared, no deck is the default.
    deck: brand.brand ? (shared.output === 'google' ? 1 : 0) : DECKS.length - 1,
    brand: brand.brand || '', variant: brand.variant || '', copies: [], delivery: 0,
    walkthrough: false,
    yoodli: false, materials: [], research: newResearch(),
    agent: agent.default === 'codex' ? 'codex' : 'claude',
    model: agent.model || '', other: false, effort: agent.effort || '', starting: false });
}

// --- where research may look ----------------------------------------------------------

// Your sites as every studio shares them, from the studios config.
function sharedSites() {
  return list((sharedOf().research || {}).sites).filter((site) => typeof site === 'string');
}

// A new form's choice: the public web, as it always was. Your sites are off until they are
// ticked, and then every shared one is ticked. Documents are a choice: they are added after
// the start.
function newResearch() {
  const sites = sharedSites();
  return { documents: false, sites: false, web: true,
    listed: sites.slice(), picked: sites.slice(), adding: '' };
}

function shownSite(site) {
  return site.replace(/^[a-z]+:\/\//, '');
}

// The choice as the form sends it: the sites ticked, in their order, none with your sites off.
function researchChoice(draft) {
  const research = draft.research;
  return { documents: research.documents, web: research.web,
    sites: research.sites ? research.listed.filter((site) => research.picked.includes(site)) : [] };
}

// Where research looks, in the words every studio uses: "from your documents and 3 of your
// sites (a, b, c)". The runner says the same with studio_core.research_sites.summary.
function researchSummary(chosen) {
  const named = chosen.sites.map(shownSite);
  const sites = named.length > SITES_NAMED
    ? named.slice(0, SITES_NAMED).join(', ') + ' and ' + (named.length - SITES_NAMED) + ' more'
    : named.join(', ');
  const parts = [chosen.documents ? 'your documents' : null,
    named.length ? named.length + ' of your sites (' + sites + ')' : null,
    chosen.web ? 'the public web' : null].filter(Boolean);
  return parts.length ? 'from ' + series(parts) : 'from nothing';
}

// Why this choice cannot start, or nothing when it can.
function researchProblem(draft) {
  if (draft.sourceEditor) return draft.sourceEditor.valid() ? '' : 'Add readable sources or allow additional external search before starting.';
  const research = draft.research;
  if (research.sites && !researchChoice(draft).sites.length) return RESEARCH_NO_SITES;
  const chosen = researchChoice(draft);
  return chosen.documents || chosen.sites.length || chosen.web ? '' : RESEARCH_EMPTY;
}

// Research from: your documents, your sites and the public web, each on or off. Your sites
// open into the list, a chip a site, and a box to add one for this training only. `held`
// names what is chosen elsewhere and not ticked here: the desk start's documents are the
// files added above it.
function researchFields(draft, changed, held) {
  const research = draft.research;
  const node = make('div', 'fields');
  const offered = RESEARCH_FROM.filter(([id]) => !list(held).includes(id));
  const fill = () => {
    const ticked = research.listed.filter((site) => research.picked.includes(site)).length;
    const row = add(make('fieldset', 'research-choices'), make('legend', 'field-label',
      'Research from'));
    for (const [id, label] of offered) {
      const words = id === 'sites' ? label + ' (' + ticked + ')' : label;
      row.append(window.StudioLists.tick({ id: 'research-' + id, label: words,
        on: research[id], flip: (on) => {
          research[id] = on;
          say(byId('new-problem'), '');
          fill();
          focusKey('research-' + id);
          changed();
        } }));
    }
    const means = bullets(offered.filter(([id]) => research[id])
      .map(([id]) => RESEARCH_SAYS[id === 'sites' && research.web ? 'sitesAndWeb' : id]),
    'reasons meanings');
    node.replaceChildren();
    add(node, row, means);
    if (!research.sites) return;
    const listed = add(make('fieldset', 'site-choices'), make('legend', 'field-label',
      'Your sites'));
    research.listed.forEach((site, index) => {
      listed.append(window.StudioLists.tick({ id: 'site-' + index, label: shownSite(site),
        on: research.picked.includes(site), flip: (on) => {
          research.picked = research.listed.filter((one) => (one === site ? on
            : research.picked.includes(one)));
          say(byId('new-problem'), '');
          fill();
          focusKey('site-' + index);
          changed();
        } }));
    });
    // The runner checks a site the way every studio does, and keeps it nowhere: it is
    // sent with this training's choice when the training starts.
    const added = async () => {
      const typed = (research.adding || '').trim();
      if (!typed || research.checking) return;
      research.checking = true;
      let found;
      try {
        found = await send('research-site', { site: typed });
      } catch (failure) {
        research.checking = false;
        refuse('new-site', failure.message);
        return;
      }
      research.checking = false;
      if (!research.listed.includes(found.site)) research.listed.push(found.site);
      if (!research.picked.includes(found.site)) research.picked.push(found.site);
      research.adding = '';
      fill();
      focusKey('new-site');
      changed();
    };
    const box = field('new-site', 'Add a site for this training', research, 'adding',
      { hint: 'For this training only: your shared list of sites stays as it is. It is '
        + 'changed in Shared settings.' });
    // Enter in the box adds the site, and does not start the training.
    box.querySelector('input').addEventListener('keydown', (event) => {
      if (event.key !== 'Enter') return;
      event.preventDefault();
      added();
    });
    add(node, research.listed.length ? listed
      : make('p', 'quiet', 'No sites are shared yet. Add one for this training, or add your '
        + 'sites in Shared settings.'),
    box, add(make('div', 'bar'), capsule('Add the site', 'quiet', added, 'add-site')));
  };
  fill();
  return node;
}

// The brands a deck can be made in, as the brand skill on this computer lists them. A deck
// is always made in one, so with none there is no deck to choose.
function brandsFound() {
  const found = (view.setup && view.setup.brand) || {};
  return found.found ? list(found.brands) : [];
}

// Hold a draft to what this computer can do now: a brand the brand skill has, one of that
// brand's variants, and no deck where no brand is to be had.
function settleDeck(draft) {
  const brands = brandsFound();
  const chosen = brands.find((brand) => brand.brand === draft.brand) || brands[0];
  const variants = list(chosen && chosen.variants);
  draft.brand = chosen ? chosen.brand : '';
  draft.variant = variants.includes(draft.variant) ? draft.variant : variants[0] || '';
  if (!chosen) draft.deck = DECKS.length - 1;
  return draft;
}

function times(number) {
  return number === 1 ? 'once' : number === 2 ? 'twice' : number + ' times';
}

function trainingTick(label, on, flip, key) {
  const node = window.StudioLists.tick({id: 'new-' + key.replaceAll(' ', '-'), label, on, flip});
  node.querySelector('input').dataset.key = key;
  return node;
}

function checkChoices(label, options, chosen, flip, key, hint) {
  const row = add(make('fieldset', 'research-choices'), make('legend', 'field-label', label));
  for (const [value, text] of options) {
    const option = trainingTick(text, chosen(value), (on) => flip(value, on), key + ' ' + value);
    if (hint) option.querySelector('input').setAttribute('aria-describedby', key + '-help');
    row.append(option);
  }
  const help = hint ? make('p', 'quiet field-hint', hint) : null;
  if (help) help.id = key + '-help';
  return add(make('div', 'field'), row, help);
}

function topicStep(draft) {
  return [
    field('new-title', 'A short title', draft, 'title',
      { hint: 'What it is called in every list, for example “Rolling restarts”.' }),
    field('new-topic', 'What should it teach?', draft, 'topic', { long: true,
      hint: 'Describe what learners should be able to do, the depth you want, and any topics or examples to include. A sentence or two is enough.' }),
    field('new-audience', 'Who is it for?', draft, 'audience', { long: true,
      hint: 'Their role, and what they already know.' }),
    choice('What it is for', PURPOSES, draft.purpose, (index) => {
      draft.purpose = index;
    }, 'purpose')];
}

// One thing chosen from several, in the browser's own list. Where there is only one, there
// is nothing to choose, and it is said in a line.
function oneOf(id, label, options, held, name, changed) {
  if (options.length > 1) return field(id, label, held, name, { options, changed });
  return add(make('div', 'field'), make('p', 'field-label', label),
    make('p', '', options.length ? options[0][1] : 'None'));
}

// The brand a deck is made in, and which of its variants: both as the brand skill on this
// computer lists them. Choosing another brand offers that brand's variants.
function brandFields(draft) {
  const found = (view.setup && view.setup.brand) || {};
  const brands = brandsFound();
  const node = make('div', 'fields');
  const fill = () => {
    const chosen = brands.find((brand) => brand.brand === draft.brand) || {};
    const variants = list(chosen.variants);
    node.replaceChildren();
    add(node, oneOf('new-brand', 'The deck’s brand',
      brands.map((brand) => [brand.brand, brand.name || brand.brand]), draft, 'brand', () => {
        settleDeck(draft);
        fill();
        focusKey('new-brand');
      }),
    variants.length ? oneOf('new-variant', 'The brand’s variant',
      variants.map((variant) => [variant, variant]), draft, 'variant') : null,
    make('p', 'quiet field-hint', 'A deck is always made in a brand. '
      + (found.name ? 'These are what ' + found.name + ', the brand skill on this computer, '
        + 'offers.' : 'These are what the brand skill on this computer offers.')),
    found.problem ? make('p', 'fix', found.problem) : null);
  };
  fill();
  return node;
}

// Secondary choices stay in the same form without competing with its main task.
function trainingOptions(label, key, ...children) {
  const node = make('details', 'training-options');
  node.dataset.key = key;
  node.open = Boolean(view.draft && list(view.draft.opened).includes(key));
  return add(node, make('summary', '', label), ...children);
}

// What the sheet's summary says is said again whenever a choice it reads changes.
function retell() {
  if (view.draft && view.draft.retell) view.draft.retell();
}

function yoodliNotice(draft, text) {
  draft.yoodliNote = text;
  say(byId('new-yoodli-note'), text);
}

function syncMaterialChoices(draft) {
  for (const control of byId('sheet').querySelectorAll('input')) {
    const key = control.dataset.key || '';
    if (key.startsWith('material ')) {
      control.checked = draft.materials.includes(key.slice(9));
    }
    if (key === 'practice yoodli') control.checked = draft.yoodli;
  }
}

function materialChoices(draft) {
  return checkChoices('Materials to make', MATERIALS, (id) => draft.materials.includes(id),
    (id, selected) => {
      draft.materials = MATERIALS.map(([key]) => key)
        .filter((key) => key === id ? selected : draft.materials.includes(key));
      // Removing an included material is an explicit choice to stop preparing Yoodli.
      if (!selected && ['brief', 'scenario'].includes(id)) {
        const wasOn = draft.yoodli;
        draft.yoodli = false;
        syncMaterialChoices(draft);
        if (wasOn) yoodliNotice(draft, 'Yoodli scenarios turned off because ' + MATERIALS.find(([key]) => key === id)[1] + ' was removed.');
        else yoodliNotice(draft, '');
      }
      say(byId('new-problem'), '');
      retell();
    }, 'material');
}

// The desk start's second step: what is made, at which levels. The deck's brand and the
// copies are settings, asked in the third step (brandOption, copiesOption); a change to the
// deck is said to them through retell().
function shapeStep(draft) {
  const toggle = (held) => (value, on) => {
    draft[held] = draft[held].filter((other) => other !== value);
    if (on) draft[held].push(value);
    retell();
  };
  settleDeck(draft);
  const able = brandsFound().length > 0;
  // Asked once a training: a talk is presented live, a handout is read on its own.
  const used = choice('How is this deck used?', DELIVERIES.map((kind) => kind[1]),
    draft.delivery || 0, (index) => { draft.delivery = index; }, 'delivery',
    'A spoken session is presented live; choose Read on its own for self-study.');
  used.hidden = !able || DECKS[draft.deck][0] === null;
  // A deck is approved on what it says and on its look, as the brand's checkpoints are. Its
  // slides' designs are walked through one at a time only when asked for here.
  const walk = add(make('div', 'field'),
    trainingTick('Walk through each slide’s design before it is built', draft.walkthrough,
      (on) => { draft.walkthrough = on; }, 'walkthrough'),
    make('p', 'quiet field-hint', 'Optional. Review how each slide will be drawn before the deck is built.'));
  walk.hidden = used.hidden;
  const deck = choice('The slide deck', DECKS.map((kind) => kind[1]), draft.deck, (index) => {
    draft.deck = index;
    used.hidden = !able || DECKS[index][0] === null;
    walk.hidden = used.hidden;
    retell();
  }, 'deck');
  for (const option of able ? [] : deck.querySelectorAll('.seg-option[aria-pressed="false"]')) {
    option.disabled = true;
    option.classList.add('seg-absent');
  }
  const yoodliNote = make('p', 'quiet field-hint', draft.yoodliNote || '');
  yoodliNote.id = 'new-yoodli-note'; yoodliNote.setAttribute('role', 'status');
  yoodliNote.hidden = !draft.yoodliNote;
  return [
    make('p', 'quiet', 'Choose only what you need. Research and a blueprint connect every selected material.'),
    checkChoices('Levels', LEVELS.map((level) => [level, level]),
      (level) => draft.levels.includes(level), toggle('levels'), 'level',
      '101 introduces the subject; 201 applies it; 301 handles trade-offs; 401 explores advanced cases. '
        + 'Each selected level gets its own materials, and its own cost. Choose none for one training without levels.'),
    materialChoices(draft),
    checkChoices('Practice', [['yoodli', 'Make scenarios for Yoodli']], () => draft.yoodli,
      (value, on) => {
        if (on) {
          draft.materials = MATERIALS.map(([id]) => id)
            .filter((id) => draft.materials.includes(id) || ['brief', 'scenario'].includes(id));
        }
        draft.yoodli = on;
        syncMaterialChoices(draft);
        yoodliNotice(draft, on ? 'Included Reference brief and Practice scenarios for Yoodli.'
          : 'Reference brief and Practice scenarios remain selected.');
        say(byId('new-problem'), '');
        retell();
      }, 'practice', 'Prepares scenarios and a reference brief for you to copy or upload to Yoodli.'),
    yoodliNote,
    deck,
    able ? null : make('p', 'quiet', 'A deck needs a brand skill. You can make the other '
      + 'materials now; Status explains what this computer needs for slides.'),
    used, walk,
    trainingOptions('About the reference brief', 'training-depth',
      choice('What the brief is about', ['One product or technology', 'A comparison'],
        draft.brief, (index) => { draft.brief = index; }, 'brief'))].filter(Boolean);
}

// The deck's brand, under the start's settings. It shows only while a deck is chosen.
function brandOption(draft) {
  if (!brandsFound().length) return null;
  const node = trainingOptions('Deck brand', 'deck-brand', brandFields(draft));
  node.hidden = DECKS[draft.deck][0] === null;
  return node;
}

// The copies kept of each guide and brief, under the start's settings.
function copiesOption(draft) {
  return trainingOptions('Copies of the guide and brief', 'training-copies',
    checkChoices('Keep a copy of each selected guide and brief', COPIES,
      (kind) => draft.copies.includes(kind), (value, on) => {
        draft.copies = draft.copies.filter((other) => other !== value);
        if (on) draft.copies.push(value);
      }, 'copy',
      'Optional. Original files are kept locally. Google copies require Google access.'));
}



// The new-training sheet: the desk's start, in drafts.js's three numbered steps, then Start
// and Cancel together. Every new training is started on the desk.
function newSheet() {
  return deskStart();
}

// The sheet drawn again in place, from the draft: what was open stays open.
function paintNew() {
  const holder = byId('sheet');
  const draft = view.draft;
  if (view.sheet !== 'new' || !draft) return;
  const shown = Array.from(holder.querySelectorAll('details'));
  const keys = shown.map((node) => node.dataset.key);
  draft.opened = [...list(draft.opened).filter((key) => !keys.includes(key)),
    ...shown.filter((node) => node.open).map((node) => node.dataset.key)];
  holder.replaceChildren(...newSheet());
  paintAgents();
}

// An address that names the form, from history or a link: Home, with the sheet open on it.
function drawNew() {
  show('home', null, true);
  openNew();
}

// The research questions, checked as they are typed against what the runner takes.
const QUESTIONS_MOST = 8;
const QUESTION_LONGEST = 300;

function questionsProblem(text) {
  const lines = String(text || '').split('\n').map((line) => line.trim()).filter(Boolean);
  if (lines.length > QUESTIONS_MOST) return 'Ask research at most 8 questions.';
  if (lines.some((line) => line.split(/\s+/).join(' ').length > QUESTION_LONGEST)) {
    return 'Keep each research question to 300 characters.';
  }
  return '';
}

function questionsField(draft) {
  const node = field('research-questions', 'What should the research answer? (optional)',
    draft, 'researchQuestions', { long: true, rows: 4,
      hint: 'One question a line, at most 8, each up to 300 characters.' });
  const box = node.querySelector('textarea');
  if (box) box.addEventListener('input', () => refuse('research-questions',
    questionsProblem(draft.researchQuestions)));
  return node;
}

// What is missing before it can start: each box it needs is marked beside it, and the first
// is focused. Returns true when nothing is missing.
function startReady(draft) {
  const missing = [['new-title', draft.title, 'Give it a title first.'],
    ['new-topic', draft.topic, 'Say what it should teach first.'],
    ['new-audience', draft.audience, 'Say who it is for first.']]
    .filter(([id, value, text]) => refuse(id, value.trim() ? '' : text)
      .getAttribute('aria-invalid'));
  if (missing.length) {
    say(byId('new-problem'), 'Something above is missing.');
    byId(missing[0][0]).focus();
    return false;
  }
  if (!draft.materials.length && !DECKS[draft.deck][0]) {
    say(byId('new-problem'), 'Choose at least one material to make, or a slide deck.');
    focusKey('material document');
    return false;
  }
  return true;
}

// Start: drafts.js makes the training on the desk, adds the documents held in the sheet, and
// opens the desk.
function startTraining(pressed) {
  return startOnDesk(pressed);
}

// --- a run -------------------------------------------------------------------------
// One training working on its own: where it is, what it is doing, what it has made and
// spent, and the three controls. It is drawn in parts, and a part that has not changed is
// left exactly as it is, so an answer being written stays under the cursor while the rest
// of the screen keeps up with the run.

// Put parts in a holder in order. A part is [name, what it is drawn from, how it is built],
// and a node already there that was built from the same is kept where it is, untouched.
// A fourth item fills a part, whether it was kept or built: a list inside it is fitted
// the same way, one item at a time.
function fit(holder, parts, fresh) {
  const kept = new Map();
  for (const node of fresh ? [] : Array.from(holder.children)) {
    if (PARTS.has(node)) kept.set(PARTS.get(node), node);
  }
  const nodes = [];
  for (const [name, from, build, fill] of parts.filter(Boolean)) {
    const mark = name + '\n' + JSON.stringify(from);
    let node = kept.get(mark);
    if (!node) {
      node = build();
      if (!node) continue;
      PARTS.set(node, mark);
    }
    kept.delete(mark);
    if (fill) fill(node);
    nodes.push(node);
  }
  let at = holder.firstChild;
  for (const node of nodes) {
    if (node === at) at = at.nextSibling;
    else holder.insertBefore(node, at);
  }
  while (at) {
    const next = at.nextSibling;
    at.remove();
    at = next;
  }
}

function placeParts(spec, parts, fresh) {
  const holder = main();
  const active = document.activeElement;
  const focused = !fresh && active && active.dataset ? active.dataset.key : '';
  const disclosed = new Map((fresh ? [] : Array.from(holder.querySelectorAll('details')))
    .filter((node) => node.dataset.key).map((node) => [node.dataset.key, node.open]));
  const bar = JSON.stringify(spec.mark);
  if (fresh || bar !== view.barred) toolbar(spec);
  view.barred = bar;
  fit(holder, parts, fresh);
  for (const node of holder.querySelectorAll('details')) {
    if (disclosed.has(node.dataset.key)) node.open = disclosed.get(node.dataset.key);
  }
  if (fresh) {
    window.scrollTo(0, 0);
    if (!view.sheet) byId('title').focus({ preventScroll: true });
  } else if (focused && !document.body.contains(active) && !focusKey(focused)) {
    byId('title').focus({ preventScroll: true });
  }
}

// The next decision a run will ask for, so the person knows what is coming.
function nextGate(run) {
  return list(run.steps).find((step) => step.kind === 'gate' && step.status === 'to-do') || null;
}

// A run that waits for documents waits for its person, whatever it says of itself meanwhile.
function adding(run) {
  return Boolean(run.documents && run.documents.waiting);
}

// A run that is done has finished the training, or has made everything but the deck.
function runStanding(run) {
  if (run.finished) {
    return run.finished.ready ? ['done', 'Finished']
      : ['late', 'Not ready to use yet'];
  }
  if (run.deck_left) return ['done', 'Everything but the slide deck is made'];
  if (run.mine === false) {
    return run.driver ? RUN_WORDS.elsewhere : ['off', 'Nobody is running it'];
  }
  if (queued(run)) return ['none', 'Waiting its turn'];
  return run.state === 'working' && (adding(run) || outlining(run)) ? RUN_WORDS.waiting
    : runWords(run);
}

// One line under the beads: how many steps are left, where the training next stops for you
// under its own level, and what it has spent so far, all as the runner says them.
function aheadLine(run) {
  const ahead = run.ahead;
  if (!ahead || !ahead.steps_left) return null;
  const parts = [count(ahead.steps_left, 'step left', 'steps left')];
  if (ahead.next_stop) {
    parts.push('Next stop: ' + lower(ahead.next_stop).replace(/^(your review of|review) /, ''));
  }
  if (ahead.spent) parts.push('So far ' + ahead.spent);
  return make('p', 'quiet ahead-line', parts.join(' · '));
}

function runIntro(run, training) {
  const node = add(make('div', 'intro'), make('p', 'lede run-says', run.sentence));
  if (run.decided) {
    const last = run.decided;
    const line = make('p', 'quiet', (last.decision === 'revise' ? 'You asked for changes to '
      : 'You approved ') + last.label + ' at ' + clock(last.at) + '. ' + last.next);
    line.setAttribute('role', 'status');
    add(node, line);
  }
  add(node, nowLine(run), state(...runStanding(run)));
  if (list(training.stages).length) add(node, beads(training.stages, false));
  add(node, aheadLine(run));
  const next = nextGate(run);
  // What someone else runs asks nothing of this person, and promises them nothing: who
  // runs it, and what can be read, is said next.
  const theirs = run.mine === false;
  const stands = theirs ? '' : run.state;
  if (queued(run) && !theirs) add(node, make('p', '', queueSays(run.queue)));
  if (stands === 'working' && !adding(run) && !outlining(run)) {
    add(node, make('p', 'quiet', 'Nothing is needed from you right now. It carries on by '
      + 'itself, and this page tells you when it needs you.'
      + (next ? ' Next it asks for your decision on '
        + lower(next.label).replace(/^your review of /, '') + '.' : '')));
    // What the two ways of halting it cost, said before either is pressed.
    if (!queued(run)) {
      add(node, make('p', 'quiet', 'Stop ends the step in hand and loses its work so far; '
        + 'Pause lets it finish first.'));
    }
  } else if (stands === 'paused') {
    add(node, make('p', 'quiet', 'Nothing more is started until you resume it. Everything '
      + 'made so far is kept.'));
  } else if (stands === 'stopped' && !run.problem) {
    add(node, make('p', 'quiet', 'Everything finished before the stop is kept. Resume, and '
      + 'the step that was in hand starts over.'));
  }
  if (view.steered) {
    const problem = make('p', 'problem', view.steered);
    problem.setAttribute('role', 'alert');
    add(node, problem);
  }
  return node;
}

// The step a problem stopped at: the one it names, or else the one the steps say failed.
function failedStep(run, found) {
  const steps = list(run.steps);
  return (found.step && steps.find((step) => step.id === found.step))
    || steps.find((step) => step.status === 'failed') || null;
}

// What the one action a problem offers does, and roughly what it costs, in the way a
// deck's cost is said before it is drawn: from what the same work took before.
function actionSays(run, found) {
  if (found.waits === 'assets') {
    return 'The deck is drawn once its pictures are here. Without one, redesign the deck or '
      + 'leave it out.';
  }
  if (found.action === 'resume') {
    return 'Carry on starts that step again; everything finished before it is kept.';
  }
  if (found.action === 'more-time') return moreTime(found, 'training');
  if (found.action !== 'retry') return '';
  // Research done as one report and one independent check carries on from its saved draft.
  if (found.research) return researchAgain(found.research);
  const step = failedStep(run, found);
  const research = /^research(:|$)/.test(String(found.step || (step && step.id) || ''));
  const taken = [];
  if (step && given(step.seconds)) taken.push(lasted(step.seconds));
  if (step && given(step.dollars)) taken.push(money(step.dollars));
  const before = taken.length ? 'the tries so far took ' + taken.join(' and ') + '.' : '';
  if (research) {
    return 'Try again researches the questions still unanswered and keeps the answered ones.'
      + (before ? ' ' + capital(before) : '');
  }
  return 'Try again re-runs this step from the start' + (step ? ': ' + lower(step.label)
    : '') + '.' + (before ? ' ' + capital(before) : '');
}

// What Try again does at research done as one report and one independent check: it carries
// on from the saved draft for up to as many more rounds, and the last rounds' time and money
// say what that may take.
function researchAgain(research) {
  const took = [research.seconds ? lasted(research.seconds) + (research.parallel ? ' total assistant time' : '') : '',
    given(research.dollars) ? money(research.dollars) : ''].filter(Boolean);
  const rounds = research.rounds === 1 ? 'the last round' : research.rounds
    ? 'the last ' + count(research.rounds, 'round', 'rounds') : 'the last try';
  const most = research.most || 3;
  if (research.parallel) return 'Try again reuses checked research areas, retries missing or refused areas, and then combines and independently checks the report, for up to ' + count(most, 'round', 'rounds') + (took.length ? '; the last try used ' + took.join(' and ') : '') + '.';
  return (research.drafted
    ? 'Try again continues from the saved draft and runs up to '
      + count(most, 'more round', 'more rounds')
    : 'Try again runs the research again, up to ' + count(most, 'round', 'rounds'))
    + ' of writing and checking'
    + (took.length ? '; ' + rounds + ' took ' + took.join(' and ') : '') + '.';
}

// What "Give it more time and try again" does, after a step ran out of the time it may take.
function moreTime(found, thing) {
  if (!found.seconds) return '';
  return 'Give it more time and try again lets each step of this ' + thing + ' take up to '
    + lasted(2 * found.seconds) + ', and runs this step again from the start. Raising the '
    + 'limit in Settings, under Limits, is the other way on, for every ' + thing + '.';
}

// What a stop kept: a sentence and, where it names things one a line, those as a list.
function keptPart(text) {
  const lines = String(text || '').split('\n').map((line) => line.trim()).filter(Boolean);
  const items = lines.filter((line) => line.startsWith('- ')).map((line) => line.slice(2));
  const said = lines.filter((line) => !line.startsWith('- ')).join(' ');
  return add(make('div', 'kept'), add(make('p', ''), make('strong', '', 'What was kept: '), said),
    items.length ? bullets(items, 'plain kept-list') : null);
}

// --- one run: a note for the next step -----------------------------------------------------

// Whether a note can be left: the training is this computer's and has a next step to come.
function noting(run) {
  return Boolean(run.note) && run.mine !== false
    && ['working', 'waiting', 'paused', 'failed'].includes(run.state);
}

// A note for the next job that starts, sent without stopping anything. One already waiting
// is shown, and another sent before a job takes it replaces it.
function notePart(run) {
  const path = view.path;
  const waiting = run.note.pending;
  const label = make('label', 'field-label', 'Note for the next step');
  label.htmlFor = 'next-note';
  const box = make('textarea', 'input');
  box.id = 'next-note';
  box.rows = 2;
  box.maxLength = 2000;
  box.value = view.nextNotes[path] || '';
  box.dataset.key = 'next-note ' + path;
  box.spellcheck = true;
  const hint = make('p', 'quiet field-hint', waiting
    ? 'Noted for the next step: ' + shortNote(waiting.text) + ' Sending another replaces it.'
    : 'It goes with the next job that starts, and stops nothing. A reviewer takes no note: '
      + 'it waits for the next writer.');
  hint.id = 'next-note-hint';
  box.setAttribute('aria-describedby', 'next-note-hint next-note-problem');
  box.addEventListener('input', () => {
    view.nextNotes[path] = box.value;
    if (box.getAttribute('aria-invalid')) refuse('next-note', '');
  });
  const problem = alertLine('next-note-problem');
  const go = capsule(waiting ? 'Replace the note' : 'Send the note', '',
    () => sendNote(run, box, problem, go), 'send-note');
  go.disabled = Boolean(view.busy);
  return add(make('div', 'answer'), label, box, hint, problem, add(make('div', 'bar'), go));
}

// A note as the hint repeats it: the first line and a half, at most.
function shortNote(text) {
  const flat = String(text || '').replace(/\s+/g, ' ').trim();
  return flat.length > 160 ? flat.slice(0, 159).trimEnd() + '…' : flat;
}

async function sendNote(run, box, problem, pressed) {
  const text = box.value.trim();
  if (!text) {
    say(problem, 'Write the note first.');
    box.setAttribute('aria-invalid', 'true');
    box.focus();
    return;
  }
  if (view.busy) return;
  const turn = view.turn;
  const path = view.path;
  view.busy = true;
  pressed.disabled = true;
  try {
    const found = await send('note', { path, expected: run.note.expected, text });
    delete view.nextNotes[path];
    view.busy = false;
    toast(run.note.pending ? 'The note is replaced. It goes with the next job that starts.'
      : 'Noted. It goes with the next job that starts.');
    if (turn === view.turn && view.screen === 'run' && view.path === path) {
      view.run = found;
      paintRun(false);
    }
    refresh();
  } catch (failure) {
    say(problem, failure.message + ' Your note is still here, and nothing was sent.');
    pressed.disabled = false;
  }
  view.busy = false;
}

// The step a note went with, as the steps name it: a job of a step is named for its step.
function stepLabel(run, name) {
  const base = String(name || '').split(':')[0];
  const row = list(run.steps).find((step) => step.id === base);
  return row ? row.label : base;
}

// What went wrong, what was kept, and the one thing to do about it.
function problemPart(run, lead) {
  const found = run.problem;
  const theirs = run.mine === false;
  const label = found.label || (found.action === 'retry' ? 'Try again' : 'Resume');
  // An agent that could not be used: Status says what it needs. Missing answers: a new
  // training in its place.
  const goes = found.action === 'status' ? () => show('status')
    : found.action === 'new' ? () => openNew('problem-action')
    // A deck waiting for a picture leads to the deck's picture form, and to its file.
    : found.action === 'asset' ? () => {
    const assets = list(run.deck && run.deck.assets);
    const at = assets.findIndex((asset) => asset.supply);
    if (at >= 0) openPicture(assets[at], at, 'problem-action');
  } : () => steer(found.action, go);
  const go = found.action && !theirs
    ? capsule(label, lead ? 'filled' : '', goes, 'problem-action')
    : capsule('See everything it made', '', () => show('training', { path: view.path }),
      'problem-open');
  const title = run.state === 'waiting' ? 'It is waiting for you'
    : theirs ? 'It has stopped' : 'It has stopped, and needs you';
  const does = theirs ? '' : actionSays(run, found);
  // The research check's objections, every one under its group, read where the stop is.
  let read = null;
  const shown = found.objections ? make('div', 'card-part') : null;
  if (found.objections) {
    read = capsule('Read every objection', 'quiet', async () => {
      read.disabled = true;
      try {
        const file = await ask('file', { path: view.path, artifact: found.objections });
        shown.replaceChildren(make('p', 'row-title', 'The research check'),
          window.StudioMarkdown.render(file.text || ''));

      } catch (failure) {
        shown.replaceChildren(make('p', 'problem', failure.message));
      } finally {
        read.disabled = false;
      }
    }, 'read-objections');
  }
  return callout('late', make('h2', 'aside-title', title),
    add(make('p', ''), make('strong', '', 'What happened: '), found.what),
    keptPart(found.kept),
    does ? make('p', 'quiet', does) : null,
    add(make('div', 'bar'), go, read, theirs ? null : alsoPart(found)), shown);
}

// Beside a stop's one action: Try again once Status has been put right, and deleting a
// training whose answers are missing.
function alsoPart(found) {
  if (found.action === 'status') {
    const again = capsule('Try again', '', () => steer('retry', again), 'problem-retry');
    return again;
  }
  if (found.action === 'new') {
    return capsule('Delete this training', 'quiet', askDelete('delete'), 'problem-delete');
  }
  return null;
}

function questionPart(run, title) {
  const node = card('Needs you', 'card-needs');
  return add(node, questionBox(view.path, title, run.question, 'filled', 'answer-run'));
}

function gatePart(training, waiting, said) {
  const sentence = training.sentence || sentenceOf(waiting.label);
  return callout('yours', sentence === said ? null : make('p', '', sentence),
    waiting.question ? make('p', sentence === said ? '' : 'quiet',
      asker(training.path) + waiting.question) : null);
}

function sentenceOf(label) {
  return capital(label) + ' is waiting for your review.';
}

// What a step has taken so far. It moves while the step is working, so it is written into
// the step that is already on the screen rather than drawing the list again.
function stepFacts(step) {
  const facts = [];
  if (step.kind === 'gate') facts.push('Your decision');
  if (step.attempts > 1) facts.push(count(step.attempts, 'try', 'tries'));
  if (given(step.seconds)) facts.push(lasted(step.seconds) + (step.id === 'research' ? ' assistant time' : ''));
  if (given(step.dollars)) facts.push(money(step.dollars));
  return facts.join(' · ');
}

function stepItem(step) {
  const [shape, words] = STEP_WORDS[step.status] || STEP_WORDS['to-do'];
  const facts = make('p', 'quiet step-facts', stepFacts(step));
  facts.hidden = !facts.textContent;
  const text = add(make('div', 'row-text'), make('p', 'step-name', step.label), facts);
  if (step.error) add(text, make('p', step.status === 'failed' ? 'problem' : 'quiet', step.error));
  const item = make('li', 'row step' + (step.status === 'working' ? ' working' : ''));
  item.dataset.state = step.status;
  return add(item, bead(shape), text, make('span', 'step-words', words));
}

function stepsCard(run) {
  const node = add(make('details', 'paper training-options'), make('summary', '', 'All production steps'));
  node.dataset.key = 'production-steps';
  const steps = list(run.steps);
  if (!steps.length) return add(node, make('p', 'quiet', 'It is working out what to do first.'));
  const items = make('ol', 'rows');
  for (const step of steps) items.append(stepItem(step));
  add(node, items);
  const used = list(run.note && run.note.used);
  if (used.length) add(node, make('p', 'row-title', 'Notes for the next step'),
    bullets(used.map((item) => item.text + ' Went with: ' + stepLabel(run, item.step) + '.')));
  return node;
}

function tickSteps(run) {
  const shown = main().querySelectorAll('.step-facts');
  list(run.steps).forEach((step, index) => {
    const said = stepFacts(step);
    if (!shown[index] || shown[index].textContent === said) return;
    shown[index].textContent = said;
    shown[index].hidden = !said;
  });
}

function workerItem(worker) {
  const lines = list(worker.lines);
  const item = add(make('li', 'worker'), add(make('div', 'computer-top'),
    make('p', 'row-title', worker.label),
    add(make('span', 'quiet'), 'Started ', when(worker.started_at))));
  if (!lines.length) return add(item, make('p', 'quiet', 'Just starting.'));
  add(item, make('p', 'worker-now', lines[lines.length - 1]));
  if (lines.length > 1) {
    const before = make('details', 'worker-before');
    before.dataset.key = 'worker ' + worker.id;
    add(item, add(before, make('summary', '', 'What it did just before'),
      bullets(lines.slice(0, -1).reverse(), 'reasons')));
  }
  return item;
}

function workersCard(run) {
  const items = make('ul', 'plain workers');
  for (const worker of list(run.workers)) items.append(workerItem(worker));
  return add(card('Working now'), items);
}

function madeCard(training, theirs) {
  const node = card('Made so far');
  const made = list(training.view && training.view.files).filter((file) => !['not-started',
    'skipped', 'unavailable'].includes(file.status));
  if (!made.length) {
    add(node, make('p', 'quiet', 'Nothing yet. Each thing it makes appears here, ready to '
      + 'open.'));
  } else {
    const items = make('ul', 'rows');
    for (const file of made) {
      const words = file.waiting ? (theirs ? 'waiting for a decision where it runs'
        : 'waiting for your review')
        : file.asked ? file.words + ', changes asked for' : file.words;
      const review = file.waiting && !theirs;
      const go = capsule(review ? 'Review' : 'Open', 'quiet',
        () => show('gate', { path: training.path, artifact: file.artifact }),
        'file ' + file.artifact);
      go.setAttribute('aria-label', (review ? 'Review ' : 'Open ') + lower(file.label));
      add(items, add(make('li', 'row'), bead(file.waiting ? 'review' : FILE_BEADS[file.status]),
        add(make('div', 'row-text'), make('p', 'step-name', file.label),
          make('p', 'quiet', capital(words))), go,
        (() => {
          const save = capsule('Download', 'quiet', (event) => downloadFile(training.path,
            {artifact: file.artifact}, file.file.split('/').pop(), event.currentTarget),
            'download-' + file.artifact);
          save.setAttribute('aria-label', 'Download ' + lower(file.label));
          return save;
        })()));
    }
    add(node, items);
  }
  return add(node, add(make('div', 'bar'), capsule('Everything about this training', 'quiet',
    () => show('training', { path: view.path }), 'detail')));
}

function costCard(run) {
  const node = card('What it has cost');
  const spent = run.spent || {};
  const limits = (view.setup && view.setup.limits) || {};
  const agent = AGENT_NAMES[run.agent] || run.agent || 'an agent';
  // A cost of nothing is not reported money: it is never said as $0.00.
  const reported = given(spent.dollars) && Number(spent.dollars) > 0;
  add(node, make('p', 'cost', !reported ? 'Not reported'
    : Number(spent.dollars) < 0.005 ? 'Less than $0.01' : money(spent.dollars)));
  const says = [];
  const silent = !reported && given(spent.tokens);
  if (reported) says.push('So far.');
  else if (silent) says.push(agent + ' says how many tokens it uses, not what they cost.');
  else says.push('Nothing has been reported yet. An agent says what it used as each step ends.');
  if (given(spent.tokens)) says.push(Number(spent.tokens).toLocaleString() + ' tokens used.');
  if (given(limits.training_dollars)) {
    says.push(silent ? 'So the limit of ' + money(limits.training_dollars)
      + ' cannot stop it: watch the steps instead.'
      : 'It stops and asks you at ' + money(limits.training_dollars) + '.');
  }
  return add(node, make('p', 'quiet', says.join(' ')),
    make('p', 'quiet', 'Drafted by ' + agent + (run.model_mode === 'by_task' ? ', using Quick, Main, and Complex model profiles' : modelWords(run.model, run.effort)) + '.'));
}

// --- a run: your own documents ---------------------------------------------------------
// With documents of your own, a run waits for them before it researches anything. They are
// sent one at a time, and each is refused here first if the runner would refuse it anyway.

// The ending of a file's name, as the runner names a type: lower case, with its dot.
function ending(name) {
  const at = String(name).lastIndexOf('.');
  return at < 0 ? '' : String(name).slice(at).toLowerCase();
}

function typesOf(held) {
  return list(held.types).map((type) => '.' + String(type).toLowerCase().replace(/^\./, ''));
}

// Why a file cannot be added, or nothing when it can. `room` is how many more may be.
function unfit(file, held, room) {
  const types = typesOf(held);
  const limits = held.limits || {};
  if (types.length && !types.includes(ending(file.name))) {
    return file.name + ' was not added: only ' + series(types) + ' files are taken.';
  }
  if (given(limits.bytes) && file.size > limits.bytes) {
    return file.name + ' was not added: it is ' + megabytes(file.size) + ', and a document '
      + 'can be at most ' + megabytes(limits.bytes) + '.';
  }
  if (room < 1) {
    return file.name + ' was not added: there is room for ' + limits.files
      + ' documents and no more.';
  }
  return '';
}

// A file as the runner takes it, in base64. The browser reads it, and puts a few words about
// its kind in front, up to a comma, which are left off.
function base64Of(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const read = String(reader.result);
      const at = read.indexOf(',');
      resolve(at < 0 ? '' : read.slice(at + 1));
    };
    reader.onerror = () => reject(new Error('This browser could not read it.'));
    reader.readAsDataURL(file);
  });
}

// While documents are being sent or removed, the card's controls wait.
function holdDocuments(held) {
  for (const node of main().querySelectorAll('.documents button, .documents input')) {
    node.disabled = held;
  }
}

// What was not added, said beside the control. The card may have been drawn again since.
function unadded(text) {
  view.unadded = text;
  const problem = byId('documents-file-problem');
  if (problem && problem.textContent !== text) refuse('documents-file', text);
}

function undone(text) {
  view.undone = text;
  if (byId('documents-problem')) say(byId('documents-problem'), text);
}

async function addDocuments(input) {
  const held = view.run.documents;
  const chosen = Array.from(input.files || []);
  if (view.busy || !chosen.length) return;
  const turn = view.turn;
  const limits = held.limits || {};
  let room = given(limits.files) ? limits.files - list(held.added).length : chosen.length;
  const refused = [];
  const taken = [];
  for (const file of chosen) {
    const why = unfit(file, held, room);
    if (why) {
      refused.push(why);
    } else {
      taken.push(file);
      room -= 1;
    }
  }
  // What was said about the files chosen last time is no longer about these.
  undone('');
  unadded('');
  if (!taken.length) {
    // Refused here, beside the control, before anything is sent.
    input.value = '';
    unadded(refused.join(' ') + ' Nothing was sent.');
    input.focus();
    return;
  }
  view.busy = true;
  holdDocuments(true);
  let added = 0;
  for (const [index, file] of taken.entries()) {
    say(byId('documents-status'), 'Adding ' + (index + 1) + ' of ' + taken.length + ': '
      + file.name);
    try {
      const content = await base64Of(file);
      view.run = await send('documents', { path: view.path, action: 'add', name: file.name,
        content });
      added += 1;
    } catch (failure) {
      refused.push(file.name + ' was not added. ' + failure.message);
      // With no answer at all, there is nobody to send the rest to.
      if (failure.kind === 'stopped') break;
    }
    if (turn !== view.turn) break;
  }
  view.busy = false;
  if (turn !== view.turn) return;
  input.value = '';
  holdDocuments(false);
  say(byId('documents-status'), '');
  paintRun(false);
  unadded(refused.join(' '));
  if (added) toast(count(added, 'document', 'documents') + ' added.');
  if (!focusKey('documents-file')) byId('title').focus({ preventScroll: true });
}

// Take one document away, or say that is all of them. The runner answers with the run.
async function settleDocuments(action, name, pressed) {
  if (view.busy) return;
  const turn = view.turn;
  view.busy = true;
  holdDocuments(true);
  let run;
  try {
    run = await send('documents', name ? { path: view.path, action, name }
      : { path: view.path, action });
  } catch (failure) {
    view.busy = false;
    if (turn !== view.turn) return;
    holdDocuments(false);
    undone(failure.message + ' Nothing was changed, and your documents are still here.');
    pressed.focus();
    return;
  }
  view.busy = false;
  if (turn !== view.turn) return;
  view.run = run;
  view.unadded = '';
  view.undone = '';
  toast(name ? name + ' is removed.' : 'That is all of them. It carries on from here.');
  paintRun(false);
  // A card that the answer left as it was is not drawn again, so its controls are let go here.
  holdDocuments(false);
  if (name) {
    if (!focusKey('documents-file')) byId('title').focus({ preventScroll: true });
    return;
  }
  // The card to add them is gone from the screen: show the run from the top, as it now stands.
  window.scrollTo(0, 0);
  byId('title').focus({ preventScroll: true });
  refresh();
}

function documentItem(found, waiting, later = false) {
  const text = add(make('div', 'row-text'), make('p', 'step-name', found.name),
    make('p', 'quiet', size(Number(found.bytes) || 0)));
  // Added once the research was planned: kept, and read when the research is updated.
  if (later) add(text, make('p', '', 'Added after the research: not read yet.'));
  if (!found.readable) {
    add(text, make('p', 'problem', 'It could not be read' + (found.problem ? ': '
      + found.problem : '.')), make('p', 'quiet', 'It is kept, and is not used for the '
      + 'research.' + (waiting ? ' Remove it, or carry on without it.' : '')));
  }
  const item = make('li', 'row step');
  item.dataset.state = found.readable ? 'read' : 'unread';
  add(item, bead(found.readable ? 'done' : 'late'), text,
    make('span', 'step-words', found.readable ? 'Can be read' : 'Cannot be read'));
  if (!waiting && !later) return item;
  const remove = capsule('Remove', 'quiet',
    () => settleDocuments('remove', found.name, remove), 'remove ' + found.name);
  remove.setAttribute('aria-label', 'Remove ' + found.name);
  return add(item, remove);
}

// Stop, asked first: what is lost, and that Pause lets the step finish.
function stopSheet() {
  const run = view.run || {};
  const step = list(run.steps).find((one) => one.status === 'working');
  const go = capsule('Stop it', 'filled', () => {
    closeSheet();
    steer('stop', go);
  }, 'confirm-stop');
  return [sheetTitle('Stop ' + (step ? '“' + step.label + '”' : 'the training') + '?'),
    make('p', '', 'Its work so far is lost. Pause lets it finish first.'),
    add(make('div', 'bar'), go, capsule('Cancel', 'quiet', closeSheet, 'cancel'))];
}

// Reading the documents added since the research: priced before it is asked for.
function updateResearchSheet() {
  const held = (view.run && view.run.documents) || {};
  const names = list(held.later).map((entry) => entry.name);
  const problem = problemLine();
  const go = capsule('Update it', 'filled', async () => {
    go.disabled = true;
    try {
      view.run = await send('documents', { path: view.path, action: 'update' });
      closeSheet();
      toast('The research runs again with ' + series(names) + '.');
      paintRun(false);
    } catch (failure) {
      say(problem, failure.message + ' Nothing was changed.');
      go.disabled = false;
    }
  }, 'confirm-update-research');
  return [sheetTitle('Update the research?'),
    make('p', '', 'The research reads ' + series(names) + ' with the documents it read '
      + 'before.'),
    held.update_price ? make('p', 'quiet', held.update_price.words) : null,
    problem, add(make('div', 'bar'), go, capsule('Cancel', 'quiet', closeSheet, 'cancel'))];
}

function documentsCard(run, lead) {
  const held = run.documents;
  const added = list(held.added);
  const limits = held.limits || {};
  const node = card(held.waiting ? 'Add your documents' : 'Your documents',
    'documents' + (held.waiting ? ' card-needs' : ''));
  if (held.waiting) {
    const types = typesOf(held);
    const takes = [types.length ? 'It takes ' + series(types) + ' files' : 'It takes files',
      given(limits.bytes) ? ', each up to ' + megabytes(limits.bytes) : '',
      given(limits.files) ? ', and ' + limits.files + ' in all' : ''].join('');
    const status = make('p', 'quiet');
    status.id = 'documents-status';
    status.setAttribute('role', 'status');
    status.hidden = true;
    add(node, make('p', '', 'Nothing is researched until you have added them and chosen '
      + '“That is all of them”.'), make('p', '', KEPT_HERE),
    field('documents-file', 'Add documents', {}, '', { picked: addDocuments,
      accept: types.join(','), refused: view.unadded,
      hint: takes + '. You can choose several at once.' }), status);
  } else {
    add(node, make('p', '', added.length ? 'These were given to the research. ' + KEPT_HERE
      : 'None were added.'));
  }
  if (held.note) add(node, make('p', 'quiet', held.note));
  const later = new Set(list(held.later).map((entry) => entry.name));
  if (added.length) {
    const items = make('ul', 'rows');
    for (const found of added) {
      items.append(documentItem(found, held.waiting, later.has(found.name)));
    }
    add(node, make('p', 'row-title', count(added.length, 'document', 'documents')
      + ' added'), items);
  } else if (held.waiting) {
    add(node, make('p', 'quiet', 'Nothing is added yet.'));
  }
  if (!held.waiting) {
    if (!later.size || run.mine === false) return node;
    // While a combined review waits, the research is changed from that review.
    if (run.review) {
      return add(node, make('p', 'quiet', 'Update the research once this review is '
        + 'decided.'));
    }
    const update = capsule('Update the research', '', openSheet('update-research',
      'update-research'), 'update-research');
    return add(node, alertLine('documents-problem'), add(make('div', 'bar'), update));
  }
  const problem = alertLine('documents-problem');
  say(problem, view.undone);
  const done = capsule('That is all of them', lead ? 'filled' : '',
    () => settleDocuments('done', '', done), 'documents-done');
  return add(node, problem, add(make('div', 'bar'), done));
}

// --- a run: the copies, the deck, and the end -------------------------------------------

// Where a copy is. A web address is a link to follow; anything else is a file in the
// training's folder, and is shown as where it is.
function copyLink(found, kind, what) {
  if (!found.link) return null;
  if (!WEB_LINK.test(found.link)) {
    return add(make('p', 'quiet'), 'Kept with the training as ',
      pathInto(make('span', 'path'), found.link));
  }
  const node = make('a', 'link', 'Open the ' + kind);
  node.href = found.link;
  node.rel = 'noopener noreferrer';
  node.target = '_blank';
  node.setAttribute('aria-label', 'Open the ' + what + ', in a new tab');
  return add(make('p', ''), node);
}

function copyItem(found) {
  const [shape, words] = COPY_STATES[found.state] || COPY_STATES['not-made'];
  const kind = COPY_KINDS[found.kind] || 'copy';
  const what = kind + ' of ' + lower(found.label);
  const text = add(make('div', 'row-text'),
    make('p', 'step-name', capital(what)));
  if (found.state === 'out-of-date') {
    add(text, make('p', '', 'Its file has changed since this copy was made.'));
  }
  // What Google was found to hold, when the person last looked.
  if (found.remote === 'remote changed') add(text, make('p', '', 'Changed in Google Docs.'));
  if (found.remote === 'both changed') {
    add(text, make('p', '', 'Changed in Google Docs, and here too.'));
  }
  const why = found.problem || (found.state === 'not-made' ? 'No reason was given.' : '');
  if (found.state !== 'made' && why) add(text, make('p', '', why));
  add(text, copyLink(found, kind, what));
  if (found.kind === 'google' && view.run?.mine !== false) {
    if (found.conflict) {
      for (const [choose, label] of [['theirs', "Use the Doc's version"],
        ['ours', 'Keep this version and send it']]) {
        add(text, capsule(label, 'quiet', (event) => {
          view.copyChoice = {found, choose};
          openSheet('copy-choice', event.currentTarget)();
        }, 'choose-copy-' + choose + '-' + found.artifact));
      }
    }
    if (found.conflict || ['remote changed', 'both changed'].includes(found.remote)) {
      add(text, capsule("Bring the Doc's changes in", 'quiet', (event) =>
        pullCopy(found, null, event.currentTarget), 'pull-copy-' + found.artifact));
    }
  }
  if (found.kind === 'google' && found.missing && view.run?.mine !== false) {
    add(text, capsule('Make a new Google Doc', 'quiet', (event) =>
      remakeCopy(found, event.currentTarget), 'remake-copy-' + found.artifact));
  }
  if (found.kind === 'word' && found.link && found.state !== 'not-made') {
    add(text, capsule('Download the Word copy', 'quiet', (event) =>
      downloadFile(view.path, {artifact: found.artifact, copy: 'word'},
        found.link.split('/').pop(), event.currentTarget), 'download-word-' + found.artifact));
  }
  const item = make('li', 'row step');
  item.dataset.state = found.state;
  return add(item, bead(shape), text, make('span', 'step-words', words));
}

function copyChoiceSheet() {
  const {found, choose} = view.copyChoice;
  const theirs = choose === 'theirs';
  const go = capsule(theirs ? "Use the Doc's version" : 'Keep this version and send it',
    'filled', async () => {
      if (await pullCopy(found, choose, go)) closeSheet();
    }, 'confirm-copy');
  return [sheetTitle(theirs ? "Use the Doc's version?" : 'Send this version?'),
    make('p', '', theirs ? 'This replaces the local ' + lower(found.label).replace(/^the /, '')
      + ' with the Doc’s kept text. Review it again before continuing.'
      : 'This replaces the changes in the Google Doc with this training’s version.'),
    add(make('div', 'bar'), go, capsule('Cancel', 'quiet', closeSheet, 'cancel'))];
}

async function remakeCopy(found, pressed) {
  pressed.disabled = true;
  try {
    view.run = await send('copies', { path: view.path, action: 'remake',
      artifact: found.artifact });
    toast(view.run.said);
    paintRun(false);
  } catch (failure) {
    toast(failure.message + ' Nothing was changed.');
  } finally {
    pressed.disabled = false;
  }
}

async function pullCopy(found, choose, pressed) {
  pressed.disabled = true;
  try {
    const run = await send('copies', {path: view.path, pull: found.artifact,
      ...(choose ? {choose} : {})});
    view.run = run;
    toast(run.unplaced ? run.said + ' ' + run.unplaced : run.said);
    paintRun(false);
    return true;
  } catch (failure) {
    toast(failure.message + ' Nothing was replaced.');
    return false;
  } finally {
    pressed.disabled = false;
  }
}

async function tryCopies() {
  if (view.copying) return;
  const turn = view.turn;
  view.copying = true;
  view.uncopied = '';
  paintRun(false);
  let run = null;
  let refusal = '';
  try {
    run = await send('copies', { path: view.path });
  } catch (failure) {
    refusal = failure.message + ' Nothing was changed: the copies are as they were.';
  }
  // Another screen is open by now, and it has put this one's state away.
  if (turn !== view.turn) return;
  view.copying = false;
  view.uncopied = refusal;
  if (run) {
    view.run = run;
    const left = list(run.copies).filter((found) => found.state !== 'made').length;
    toast(left ? count(left, 'copy is', 'copies are') + ' still not made. Each says why.'
      : 'Every copy is made.');
  }
  paintRun(false);
  if (!focusKey('copies-again')) byId('title').focus({ preventScroll: true });
}

// Asked for by the person: the one time Google is asked whether a Doc was changed there.
async function checkCopies(pressed) {
  if (view.checking) return;
  view.checking = true;
  pressed.disabled = true;
  try {
    const run = await send('copies', { path: view.path, action: 'check' });
    view.run = run;
    const changed = list(run.copies).filter((found) => found.remote).length;
    // The runner says what it found, including a Doc Google could not be asked about.
    toast(run.said || (changed ? count(changed, 'Google Doc was', 'Google Docs were')
      + ' changed there.' : 'No Google Doc was changed there.'));
  } catch (failure) {
    toast(failure.message + ' Nothing was changed.');
  } finally {
    view.checking = false;
    pressed.disabled = false;
  }
  paintRun(false);
  focusKey('check-copies');
}

// A Google copy changed both there and here waits for the person's choice.
function conflicted(found) {
  return found.kind === 'google' && found.conflict && view.run?.mine !== false;
}

function conflictPart(run) {
  const items = make('ul', 'rows');
  for (const found of list(run.copies).filter(conflicted)) items.append(copyItem(found));
  return add(card('A copy changed in two places', 'card-needs'),
    make('p', 'quiet', 'Choose which version to keep. Nothing is sent until you confirm it.'),
    items);
}

function copiesCard(run) {
  const node = card('Copies');
  const items = make('ul', 'rows');
  for (const found of list(run.copies).filter((one) => !conflicted(one))) {
    items.append(copyItem(found));
  }
  add(node, items);
  const docs = list(run.copies).some((found) => found.kind === 'google' && found.link);
  if (docs && run.mine !== false) {
    const look = capsule('Look for changes in Google Docs', 'quiet',
      (event) => checkCopies(event.currentTarget), 'check-copies');
    add(node, add(make('div', 'bar'), look));
  }
  if (!list(run.copies).some((found) => found.state !== 'made')) return node;
  // Making them again is a change, which only the computer that runs the training makes.
  if (run.mine === false) {
    return add(node, make('p', 'quiet', 'The training itself is complete without them.'));
  }
  const go = capsule(view.copying ? 'Trying again…' : 'Try the copies again', '', tryCopies,
    'copies-again');
  if (view.copying) go.setAttribute('aria-busy', 'true');
  const problem = alertLine('copies-problem');
  say(problem, view.uncopied);
  return add(node, make('p', 'quiet', 'A copy that is not made is listed as a limitation. A '
    + 'copy that is out of date must be sent again before the training is ready.'), problem,
  add(make('div', 'bar'), go));
}

// A deck this computer cannot make is the one stage a run leaves. It says what is missing in
// its own words, and leaving the deck out is the decision a gate has, with its reason.
function deckLeftPart(run) {
  const found = run.deck_left;
  if (run.mine === false) {
    return callout('', make('h2', 'aside-title', 'The slide deck is all that is left'),
      found.says === run.sentence ? null : make('p', '', found.says));
  }
  const leave = capsule('Leave the deck out', '', () => {
    view.deciding = found.artifact;
    openSheet('skip', 'leave-deck')();
    paintRun(false);
  }, 'leave-deck');
  return callout('yours', make('h2', 'aside-title', 'What to do about the slide deck'),
    found.says === run.sentence ? null : make('p', '', found.says),
    make('p', 'quiet', 'Leaving it out takes a reason, which is kept with the training. You '
      + 'can bring the deck back later.'),
    add(make('div', 'bar'), leave));
}

// The soft controls: finish the level in hand and then wait, and leave the deck out before
// anything of it is drawn. Neither stops what is in hand.
function controlsPart(run) {
  const found = run.controls;
  const node = callout('', make('h2', 'aside-title', 'Steer it'));
  if (found.grouped) add(node, make('p', 'quiet', 'The final review waits until every level is made.'));
  const bar = make('div', 'bar');
  if (found.finishing) {
    add(node, make('p', '', 'It finishes level ' + found.finishing + ', then waits. Resume it '
      + 'when you are ready for the next level.'));
  } else if (found.finish_level) {
    add(node, make('p', 'quiet', 'Level ' + found.finish_level + ' is in hand. You can have it '
      + 'finished, and nothing started for another level until you resume.'));
    const finish = capsule('Finish this level, then wait', '', () => steer('finish-level', finish),
      'finish-level');
    add(bar, finish);
  }
  if (found.skip_deck) {
    add(node, make('p', 'quiet', 'Nothing of the deck is drawn yet. Leaving it out takes a '
      + 'reason, which is kept with the training; you can bring the deck back later.'));
    add(bar, capsule('Leave the deck out', '', () => {
      view.deciding = 'deck';
      openSheet('skip', 'skip-deck')();
      paintRun(false);
    }, 'skip-deck'));
  }
  return add(node, bar.childNodes.length ? bar : null);
}

function finishedPart(run, lead) {
  const found = run.finished;
  const desk = run.can_open_desk ? openDeskButton(view.path, '') : null;
  const limits = list(found.limitations);
  const yoodli = list(found.yoodli).map((item) => add(make('div', 'card-part'),
    make('p', 'row-title', item.label || 'Yoodli scenario'), yoodliCopies(item)));
  // The index is one more file of the training, read on a screen of its own.
  const open = found.index && !found.ready ? capsule('Open the index', '',
    () => show('index', { path: view.path, artifact: found.index }), 'index') : null;
  const limited = limits.length ? [make('p', '', count(limits.length, 'thing was',
    'things were') + ' left out or limited:'), bullets(limits, 'reasons')] : [];
  const indexed = open ? make('p', 'quiet', 'The index lists every file, what was checked, '
    + 'and how to use the practice scenarios.') : null;
  if (found.ready) {
    return callout('', make('h2', 'aside-title', 'Ready to use'),
      ...(limited.length ? limited : [make('p', '', 'Nothing was left out or limited.')]),
      found.index ? make('p', 'quiet', 'Open the index for the materials and how to use them, '
        + 'or open an individual material below.') : null, ...yoodli,
      desk ? add(make('div', 'bar'), desk) : null);
  }
  const blocking = list(found.blocking);
  const go = capsule('See what is in the way', lead ? 'filled' : '',
    () => show('training', { path: view.path }), 'blocking');
  return callout('late', make('h2', 'aside-title', 'Not ready to use yet'),
    make('p', '', blocking.length ? count(blocking.length, 'thing is', 'things are')
      + ' in the way:' : 'Something is in the way, and it was not said what.'),
    blocking.length ? bullets(blocking, 'reasons') : null,
    add(make('p', ''), make('strong', '', 'What was kept: '), 'everything that was made.'),
    ...limited, ...yoodli, indexed, add(make('div', 'bar'), go, open, desk));
}

async function steer(action, pressed) {
  if (view.busy) return;
  const turn = view.turn;
  const key = pressed.dataset.key;
  view.busy = true;
  pressed.disabled = true;
  try {
    if (onTheDesk(view.run)) {
      const path = view.path;
      if (action === 'stop') {
        // Stopping must not wait for a refused or stalled save. Its text stays pending.
        flushDesk(deskHeld(path)).catch(() => {
          deskHeld(path).said = 'Unsaved text is still on the desk.';
          if (view.path === path && view.screen === 'run') paintDesk(false);
        });
      } else await flushDesk(deskHeld(path));
    }
    const run = await send('run', { path: view.path, action });
    view.busy = false;
    if (turn !== view.turn) return;
    view.run = run;
    view.steered = '';
    toast(STEERED[action]);
  } catch (failure) {
    view.busy = false;
    if (turn !== view.turn) return;
    view.steered = failure.message + ' Nothing was changed.';
    if (onTheDesk(view.run)) deskHeld(view.path).said = view.steered;
  }
  view.barred = '';
  paintRun(false);
  // The control that was pressed may be gone. Focus goes to the one that undoes it, or to
  // the head of the screen, never to nowhere.
  const undo = { pause: 'resume', resume: 'pause', stop: 'resume' }[action];
  if (!focusKey(key) && !(undo && focusKey(undo))) byId('title').focus({ preventScroll: true });
  refresh();
}

// The toolbar's side of a run: pause, resume and stop, and one filled button for whatever
// is needed first.
function runActions(run, waiting, lead) {
  const actions = [];
  if (run.review && !run.question && !run.problem) {
    // On a desktop the filled action follows the marks: Send once anything is marked, the
    // approval otherwise. On a phone the filled one is the review bar's.
    const asked = marked(run.review);
    const leads = lead === 'combined' && !narrow();
    if (asked.length && !narrow()) {
      const send = capsule('Send ' + count(asked.length, 'request', 'requests'),
        leads ? 'filled' : '', () => decideCombined(run.review, 'revise', null, null, send,
          byId('combined-send-problem'), marked(run.review)), 'send-requests');
      actions.push(send);
    }
    const approve = capsule(combinedLabel(run.review), leads && !asked.length ? 'filled' : '',
      () => decideCombined(run.review, 'approve', null, null, approve), 'approve-combined');
    actions.push(approve);
  }
  if (run.finished?.ready && run.finished.index) {
    actions.push(capsule('Open the index', lead === 'finished' ? 'filled' : '',
      () => show('index', { path: view.path, artifact: run.finished.index }), 'index'));
  }
  const press = (label, kind, action) => {
    const node = capsule(label, kind, () => steer(action, node), action);
    actions.push(node);
  };
  const offered = run.problem && run.problem.action;
  if (run.state === 'working') press('Pause', '', 'pause');
  // Stop asks first: the step in hand loses its work.
  if (['working', 'waiting', 'paused'].includes(run.state)) {
    actions.push(capsule('Stop', 'quiet', openSheet('stop-run', 'stop'), 'stop'));
  }
  if (['paused', 'stopped'].includes(run.state) && offered !== 'resume') {
    press('Resume', lead === 'resume' ? 'filled' : '', 'resume');
  }
  // A run that failed and says nothing more is still not a dead end.
  if (lead === 'retry') press('Try again', 'filled', 'retry');
  if (waiting && !run.question && !run.review) {
    actions.push(capsule('Review ' + waiting.label, lead === 'review' ? 'filled' : '',
      () => show('gate', { path: view.path, artifact: waiting.artifact }), 'lead'));
  }
  // What a deck says is reviewed on a screen of its own, reached like any gate.
  if (outlining(run) && !run.question && !run.review) {
    actions.push(capsule('Review ' + outlineLabel(run.outline),
      lead === 'outline' ? 'filled' : '', () => show('outline', { path: view.path }),
      'lead-outline'));
  }
  return actions;
}

// --- a run: the slide deck -----------------------------------------------------------------

function outlineLabel(outline) {
  return outline && outline.level ? 'what the level ' + outline.level + ' deck says'
    : 'what the deck says';
}

// What a deck says is waiting for its person. The run leads to it, and says why it matters.
function outlinePart(run) {
  const says = capital(outlineLabel(run.outline)) + ' is waiting for your review.';
  return callout('yours', says === run.sentence ? null : make('p', '', says),
    make('p', 'quiet', 'It is every slide’s words, before any slide is drawn. Words are '
      + 'quick to change now, and slow to change once the slides are drawn.'));
}

// The brand's looks for a deck, each drawn on the same slide of what it says, in the panel
// every studio's page shows. The person picks the one every slide is drawn in, and may say
// why: their words are kept with it. Looks that could not be rendered are never picked
// blind: the person tries again, or carries on in the brand's default look.
// The deck's wireframe draft, drawn by the slides tool from what the deck says and framed
// from this page's own server: opened with a ticket, sandboxed, able to reach nothing.
function draftPanel(level) {
  return window.DeckPanels.storyboard({ title: 'Wireframe draft of the deck',
    load: () => ask('deck-draft-ticket', level ? { path: view.path, level } : { path: view.path })
      .then((made) => made.src) });
}

function lookPicker(look, picked, changed) {
  return window.DeckPanels.lookPicker({ name: look.artifact, looks: list(look.looks),
    defaultId: look.default, sheet: look.sheet, notes: list(look.notes), failed: look.failed,
    picked, changed,
    picture: (number, alt) => pictureAt({ artifact: look.artifact, section: 'look', number },
      alt) });
}

function lookPart(run, leads) {
  const look = run.look;
  const deck = look.level ? 'the level ' + look.level + ' slide deck' : 'the slide deck';
  const node = callout('yours', make('p', '', 'Choose the look of ' + deck + '.'),
    make('p', 'quiet', 'The brand drew one slide of what the deck says in each of its looks. '
      + 'The look you choose sets the colours, what each one stands for and how cards are '
      + 'drawn on every slide.'));
  const key = 'look:' + look.artifact;
  const held = view.notes[key] || (view.notes[key] = { choice: '', words: '' });
  const problem = alertLine('look-problem');
  add(node, lookPicker(look, held, (now) => Object.assign(held, now)), problem);
  if (look.failed) {
    const again = capsule('Try again', leads ? 'filled' : '',
      () => chooseLook(look, 'again', '', problem, again), 'look-again');
    const proceed = capsule('Carry on in the brand’s default look', '',
      () => chooseLook(look, 'default', '', problem, proceed), 'look-default');
    return add(node, again, proceed);
  }
  const use = capsule('Use this look', leads ? 'filled' : '', () => {
    if (!held.choice) return say(problem, 'Pick a look first.');
    return chooseLook(look, held.choice, held.words || '', problem, use);
  }, 'look-use');
  return add(node, use);
}

async function chooseLook(look, choice, words, problem, pressed) {
  if (view.busy) return;
  const turn = view.turn;
  view.busy = true;
  pressed.disabled = true;
  let run;
  try {
    run = await send('look', { path: view.path, level: look.level || null, choice,
      words: words.trim() || null });
  } catch (failure) {
    say(problem, failure.message);
    pressed.disabled = false;
    view.busy = false;
    return;
  }
  delete view.notes['look:' + look.artifact];
  view.busy = false;
  if (turn !== view.turn) return;
  view.run = run;
  toast('The look is chosen. ' + run.sentence);
  show('run', { path: view.path }, true);
  refresh();
}

// What a deck of this size has cost before, so that this one is no surprise.
function costBefore(before) {
  const parts = [];
  if (given(before.dollars)) parts.push('about ' + money(before.dollars));
  if (given(before.minutes)) {
    parts.push('about ' + lasted(Number(before.minutes) * 60) + ' of agent time');
  }
  return parts.length ? 'A deck of this size has cost ' + parts.join(' and ') + ' before. '
    + 'It spends from the same limit as the rest of the training.' : '';
}

// One section of a deck while it is drawn: where it stands, how many previews it has used,
// and its slides as they were last previewed. The runner numbers a section's slides within
// that section, from 1, and gives each its title: where a slide falls in the deck is not
// known until the sections are put together, so nothing here says.
function sectionItem(section, index) {
  const [shape, words] = SECTION_WORDS[section.state]
    || ['current', spoken(section.state || 'being drawn')];
  const slides = list(section.slides);
  const titles = list(section.titles);
  const used = Number(section.previews) || 0;
  const text = add(make('div', 'row-text'), make('p', 'step-name', 'Section ' + (index + 1)),
    make('p', 'quiet', used ? (slides.length ? count(slides.length, 'slide', 'slides') + ' · '
      : '') + count(used, 'preview', 'previews') + ' used' : 'No preview yet'));
  if (used && slides.length) {
    const thumbs = make('ul', 'thumbs');
    slides.forEach((number, at) => {
      const name = make('span', 'thumb-name quiet', String(number));
      name.setAttribute('aria-hidden', 'true');
      // A new preview is a new picture of the same slide, so it is fetched again.
      add(thumbs, add(make('li', 'thumb'), pictureAt({ section: section.id, number },
        'Section ' + (index + 1) + ', slide ' + number + (titles[at] ? ': ' + titles[at] : ''),
        used), name));
    });
    add(text, make('p', 'quiet', 'As last previewed:'), thumbs);
  }
  const item = make('li', 'row step section');
  item.dataset.state = section.state;
  return add(item, bead(shape), text, make('span', 'step-words', words));
}

// One picture or icon a deck's approved design uses, and how it stands. A picture the
// person gives can be supplied here, or given again.
function assetItem(found, index, theirs) {
  const [shape, words] = ASSET_WORDS[found.state] || ['none', spoken(found.state || '')];
  const named = (found.kind === 'icon' ? 'Icon' : capital(found.kind)) + ': '
    + (found.ref || found.asset);
  const text = add(make('div', 'row-text'), make('p', 'step-name', named),
    make('p', 'quiet', (found.concept ? found.concept + ', on ' : 'On ') + found.slide
      + (found.alt ? '. It shows: ' + found.alt : '')));
  if (found.supply && !theirs) {
    add(text, add(make('div', 'bar'), capsule('Add the picture', '',
      () => openPicture(found, index, 'asset-' + index), 'asset-' + index)));
  }
  const item = make('li', 'row step asset');
  item.dataset.state = found.state;
  return add(item, bead(shape), text, make('span', 'step-words', words));
}

// Whether the deck waits for a picture from this person, and nothing else says so already.
function waitsForPicture(run) {
  return run.mine !== false && list(run.deck && run.deck.assets).some((found) => found.supply)
    && !(run.problem && run.problem.action === 'asset');
}

// At the top of the run: each picture the deck waits for, and the way to add it.
function picturePart(run) {
  const items = make('ul', 'rows');
  list(run.deck.assets).forEach((found, index) => {
    if (!found.supply) return;
    const go = capsule('Add the picture', '', () => openPicture(found, index,
      'needs-asset-' + index), 'needs-asset-' + index);
    go.setAttribute('aria-label', 'Add the picture: ' + assetName(found));
    items.append(add(make('li', 'row row-needs'), bead('review'), add(make('div', 'row-text'),
      make('p', 'row-title', assetName(found)),
      make('p', 'row-says', 'The slide deck waits for this picture, on ' + found.slide + '.')),
    go));
  });
  return add(card('Needs you', 'card-needs'), items);
}

// The name a deck's picture or icon goes by.
function assetName(found) {
  return (found.kind === 'icon' ? 'Icon' : capital(found.kind)) + ': '
    + (found.ref || found.asset);
}

// Open the sheet for one picture a deck waits for.
function openPicture(found, index, opener) {
  view.picture = { found, index };
  openSheet('picture', opener)();
  const box = byId('asset-' + index + '-file');
  if (box) box.focus();
}

// The sheet that adds a picture: the file, what it shows, where it came from and any limit
// on its use, then Save the picture and Cancel together.
function pictureSheet() {
  const { found, index } = view.picture;
  view.assetsHeld = view.assetsHeld || {};
  const held = view.assetsHeld[found.asset] || (view.assetsHeld[found.asset] = {});
  const id = 'asset-' + index;
  const picture = field(id + '-file', found.state === 'recorded' ? 'Give another picture'
    : 'Supply the picture', {}, '', { picked: (input) => {
    held.file = (input.files || [])[0] || null;
  }, accept: '.png,.jpg,.jpeg,.gif', hint: 'A PNG, JPEG or GIF file.' });
  picture.querySelector('input').multiple = false;
  const send = submitButton('Save the picture', id + '-send');
  const form = make('form', 'create-flow');
  form.noValidate = true;
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    supplyAsset(found, index, send);
  });
  add(form,
    createStep(1, 'The picture', make('p', 'quiet', assetName(found) + ', on '
      + found.slide + (found.concept ? ': ' + found.concept : '') + '.'), picture),
    createStep(2, 'What it shows', field(id + '-alt', 'What it shows', held, 'alt')),
    createStep(3, 'Where it came from, and any limit on its use',
      field(id + '-source', 'Where it came from', held, 'source'),
      field(id + '-restrictions', 'Any limit on its use, if there is one', held,
        'restrictions')),
    add(make('div', 'bar create-foot'), send, capsule('Cancel', 'quiet', closeSheet, 'cancel')));
  return [add(make('div', 'sheet-heading'), sheetTitle('Add a picture')), form];
}

async function supplyAsset(found, index, pressed) {
  if (view.busy) return;
  const id = 'asset-' + index;
  const held = (view.assetsHeld || {})[found.asset] || {};
  const missing = !held.file ? [id + '-file', 'Choose the picture first.']
    : !(held.alt || '').trim() ? [id + '-alt', 'Say what the picture shows.']
      : !(held.source || '').trim() ? [id + '-source', 'Say where it came from.'] : null;
  if (missing) {
    refuse(...missing).focus();
    return;
  }
  const turn = view.turn;
  view.busy = true;
  pressed.disabled = true;
  try {
    const content = await base64Of(held.file);
    const run = await send('asset', { path: view.path, level: view.run.deck.level,
      asset: found.asset, content, alt: held.alt.trim(), source: held.source.trim(),
      restrictions: (held.restrictions || '').trim() || null });
    view.busy = false;
    if (turn !== view.turn) return;
    view.run = run;
    delete view.assetsHeld[found.asset];
    view.picture = null;
    view.sheet = '';
    drawSheet();
    toast('The picture is recorded.');
  } catch (failure) {
    view.busy = false;
    if (turn !== view.turn) return;
    pressed.disabled = false;
    refuse(id + '-file', failure.message + ' Nothing was changed.').focus();
    return;
  }
  paintRun(false);
  refresh();
}

function deckCard(run) {
  const deck = run.deck;
  const sections = list(deck.sections);
  const node = card(deck.level ? 'The level ' + deck.level + ' slide deck' : 'The slide deck',
    'deck');
  const cost = deck.before ? costBefore(deck.before) : '';
  if (cost) add(node, make('p', '', cost));
  if (!sections.length) {
    add(node, make('p', 'quiet', 'Its sections appear here once the deck is split into '
      + 'them.'));
  } else {
    const items = make('ol', 'rows');
    sections.forEach((section, index) => items.append(sectionItem(section, index)));
    add(node, make('p', '', 'It is drawn in sections, side by side. Each one draws its '
      + 'slides, looks at a preview of them, and puts right what it sees before handing in.'),
    items);
  }
  const assets = list(deck.assets);
  if (assets.length) {
    const items = make('ul', 'rows');
    assets.forEach((found, index) => items.append(assetItem(found, index,
      run.mine === false)));
    add(node, make('p', 'row-title', 'Pictures and icons'), make('p', '', 'What its '
      + 'approved design uses. The slides tool keeps each one, and a picture is yours to '
      + 'give.'), items);
  }
  return add(node, run.outline ? add(make('div', 'bar'), capsule('Read '
    + outlineLabel(run.outline), 'quiet', () => show('outline', { path: view.path }),
  'read-outline')) : null);
}

function combinedLabel(review) {
  return 'Approve ' + (review.phase === 'direction' ? 'the first drafts' : 'the finished materials');
}

// What one item of a combined review is marked as on this page: 'changes', 'good' or ''.
function markKey(review, item) {
  return [view.path, review.phase, 'mark', item.target].join('\n');
}

function noteKeyOf(review, item) {
  return [view.path, review.phase, item.target].join('\n');
}

// The change requests marked on a combined review, each a target and what was typed.
function marked(review) {
  return review.items.filter((item) => view.marks[markKey(review, item)] === 'changes')
    .map((item) => ({ target: item.target, note: (view.notes[noteKeyOf(review, item)] || '').trim(),
      label: item.label, rewrites: list(item.rewrites) }));
}

// The stages written before the first drafts stop: approving it does not write them.

// What approving a combined review commits to, said before it is approved.
function commitsSays(review) {
  const commits = review.commits;
  if (review.phase !== 'direction' || !commits) {
    return 'Approving finishes this training. Everything is kept as it stands, and '
      + 'publishing is a separate action.';
  }
  const names = { document: 'learner guides', brief: 'briefs', scenario: 'practice scenarios',
    yoodli: 'Yoodli scenarios' };
  // The runner lists only work still unwritten in this run, including legacy runs.
  const made = list(commits.materials)
    .map((stage) => names[stage] || stage);
  const levels = commits.levels > 1 ? 'each of the ' + commits.levels + ' levels' : 'the training';
  const parts = [];
  if (given(commits.dollars)) parts.push('about ' + money(commits.dollars));
  if (given(commits.minutes)) parts.push(lasted(Number(commits.minutes) * 60) + ' of agent time');
  const estimate = parts.length ? parts.join(' and ') + ' for a deck of this size (a fixed '
    + "estimate, not this computer's history)" : '';
  let said;
  if (made.length) {
    said = 'Approving the first drafts writes the ' + series(made) + ' for ' + levels
      + (commits.deck ? ', and the deck is then drawn' + (estimate ? ': estimated at '
        + estimate : '') : '') + '.';
  } else {
    const what = commits.levels > 1 ? 'the levels' : 'the training';
    said = commits.deck ? 'Nothing more is written for ' + what + ': approving carries on to '
      + 'the deck.' + (estimate ? ' The deck is estimated at ' + estimate + '.' : '')
      : 'Nothing more is written for ' + what + '.';
  }
  return said + ' It spends from the same limit as the rest of the training.';
}

// The sheet that confirms a combined approval: the same one a file's approval gets, saying
// what the approval commits to.
function combinedConfirm() {
  const review = view.run && view.run.review;
  const spec = CONFIRMS.approve;
  const problem = problemLine();
  const confirm = capsule(spec.send, 'filled', () => decideCombined(review, 'approve', null,
    null, confirm, problem), 'send');
  const what = review.phase === 'direction' ? 'the first drafts' : 'the finished materials';
  // Requests marked but not sent are said before the approval goes without them.
  const held = marked(review).length;
  return [sheetTitle(spec.title(what)), make('p', '', spec.says),
    make('p', '', commitsSays(review)),
    held ? state('late', count(held, 'item is', 'items are') + ' marked for changes. Approving '
      + 'does not send ' + (held === 1 ? 'it' : 'them') + '.') : null, problem,
    add(make('div', 'bar'), confirm, capsule('Cancel', 'quiet', closeSheet, 'cancel'))]
    .filter(Boolean);
}

// Looks that could not be rendered, drawn again from the combined review. It approves
// nothing: the review comes back with what was drawn.
async function redrawLooks(review, looks, problem, pressed) {
  if (view.busy) return;
  const turn = view.turn;
  view.busy = true;
  pressed.disabled = true;
  say(problem, '');
  let run;
  try {
    run = await send('review', { path: view.path, expected: review.expected,
      decision: 'approve', target: null, note: null,
      looks: { [looks.level || '']: { choice: 'again', words: '' } } });
  } catch (failure) {
    say(problem, failure.message);
    pressed.disabled = false;
    view.busy = false;
    return;
  }
  view.busy = false;
  if (turn !== view.turn) return;
  view.run = run;
  toast('The looks are being drawn again. ' + run.sentence);
  show('run', { path: view.path }, true);
  refresh();
}

async function decideCombined(review, decision, target, note, pressed,
  problem = byId('combined-problem'), requests = null) {
  if (view.busy) return;
  // An approval is confirmed first, in the sheet, which says what it commits to.
  if (decision === 'approve' && view.sheet !== 'approve-combined') {
    view.deciding = null;
    openSheet('approve-combined', pressed && pressed.dataset.key)();
    return;
  }
  const turn = view.turn;
  const path = view.path;
  const asked = decision === 'revise' ? requests || [{ target, note }] : null;
  if (asked) {
    const empty = asked.find((ask) => !String(ask.note || '').trim());
    if (empty) {
      const named = review.items.find((item) => item.target === empty.target);
      say(problem, 'Say what should change in ' + (named ? named.label : 'it') + ' first.');
      focusKey('change-' + review.phase + '-' + empty.target);
      return;
    }
  }
  view.busy = true;
  if (pressed) pressed.disabled = true;
  say(problem, '');
  try {
    const body = { path, expected: review.expected, decision, target: null, note: null };
    // The looks picked for each deck go with an approval of the direction.
    const offered = review.items.filter((item) => item.looks);
    if (decision === 'approve' && offered.length) {
      body.looks = {};
      for (const item of offered) {
        const held = view.notes['look:' + item.looks.artifact] || {};
        if (!held.choice) {
          view.busy = false;
          if (pressed) pressed.disabled = false;
          say(problem, 'Pick a look for ' + item.label.toLowerCase() + ' first.');
          return;
        }
        body.looks[item.looks.level || ''] = { choice: held.choice, words: held.words || '' };
      }
    }
    if (asked && requests) body.requests = asked.map((ask) => ({ target: ask.target, note: ask.note }));
    else if (asked) Object.assign(body, { target, note });
    const run = await send('review', body);
    if (turn !== view.turn) return;
    for (const ask of asked || []) {
      delete view.notes[[path, review.phase, ask.target].join('\n')];
      delete view.marks[[path, review.phase, 'mark', ask.target].join('\n')];
    }
    view.run = run;
    view.busy = false;
    if (view.sheet === 'approve-combined') {
      view.sheet = '';
      drawSheet();
    }
    paintRun(false);
    toast(decision === 'approve' ? 'Approved. ' + run.sentence
      : (asked.length === 1 ? 'Changes requested. ' : asked.length + ' changes requested. ')
        + run.sentence);
    byId('title').focus({preventScroll: true});
    refresh();
  } catch (failure) {
    if (turn === view.turn) {
      say(problem, failure.message);
      if (pressed) pressed.disabled = false;
    }
  } finally { view.busy = false; }
}

// What is sent when the marked requests go: how many, and what each change is followed by.
function reviewBar(review, theirs, leads) {
  const bar = make('div', 'review-bar');
  const says = make('p', '');
  const follows = make('p', 'quiet');
  const problem = alertLine('combined-send-problem');
  // On a desktop the toolbar holds both actions and the bar the tally. On a phone the one
  // filled action is the bar's, under the thumb and above the tab bar: Send while anything
  // is marked for changes, the approval otherwise.
  const small = narrow() && !theirs;
  const kind = leads ? 'filled' : '';
  const send = small ? capsule('', kind, () => decideCombined(review, 'revise', null, null,
    send, problem, marked(review)), 'send-requests') : null;
  const approve = small ? capsule(combinedLabel(review), kind,
    () => decideCombined(review, 'approve', null, null, approve), 'approve-combined-bar') : null;
  const update = () => {
    const asked = marked(review);
    const seen = review.items.filter((item) => view.marks[markKey(review, item)]).length;
    says.textContent = asked.length ? count(asked.length, 'item is', 'items are')
      + ' marked for changes.' : seen ? seen + ' of ' + review.items.length + ' looked at. '
      + 'Nothing is marked for changes.' : 'Nothing is marked for changes.';
    const after = [...new Set(asked.flatMap((ask) => ask.rewrites))]
      .filter((label) => !asked.some((ask) => ask.label === label));
    follows.textContent = after.length ? 'If ' + series(asked.map((ask) => ask.label))
      + (asked.length === 1 ? ' changes, ' : ' change, ') + 'these are written again from '
      + (asked.length === 1 ? 'it' : 'them') + ': ' + series(after) + '.' : '';
    follows.hidden = !after.length;
    if (send) {
      send.textContent = 'Send ' + count(asked.length, 'request', 'requests');
      send.hidden = !asked.length;
    }
    if (approve) approve.hidden = Boolean(asked.length);
  };
  add(bar, says, follows, problem, add(make('div', 'bar'), send, approve));
  bar.update = update;
  update();
  return bar;
}

function combinedReview(run, leads) {
  const review = run.review;
  const theirs = run.mine === false;
  const small = narrow();
  const node = card(review.label);
  // The screen's lede is the run's; what this review is for is a quiet line of its own.
  add(node, make('p', 'quiet', review.phase === 'direction'
    ? 'Review the first drafts below: the research and what is written so far for each level. Approve them to go on to what is still to write.'
    : 'Review the completed materials together. Approval finishes this draft; publishing is a separate action.'));
  if (!theirs) {
    add(node, make('p', 'quiet', 'Mark what needs changes as you read, and send every request '
      + 'at once' + (small ? '' : ' from the toolbar, or approve them there') + '.'));
  }
  const problem = problemLine();
  problem.id = 'combined-problem';
  add(node, problem);
  const material = (item) => /^(document|brief|deck)(@|$)|^(scenario|yoodli):/.test(item.target);
  const items = [...review.items];
  if (review.phase === 'final') items.sort((a, b) => Number(material(b)) - Number(material(a)));
  const firstMaterial = items.find(material);
  const bar = theirs ? null : reviewBar(review, theirs, leads);
  for (const item of items) {
    const detail = add(make('details', 'review-bundle'), make('summary', 'row-title', item.label));
    detail.dataset.key = 'combined-' + review.phase + '-' + item.target;
    const part = make('div', 'review-bundle-body'); add(detail, part);
    const first = review.phase === 'direction' ? item.target === 'research' : item === firstMaterial;
    const mark = view.marks[markKey(review, item)] || '';
    // On a phone everything but the first material is folded away until it is opened.
    detail.open = small ? first || mark === 'changes'
      : Boolean(item.sample || item.sample_note || item.looks || item.deck_view || first);
    if (item.research) add(part, researchReading(item.research));
    else if (item.document) add(part, documentBody(item.document, {label: item.label}));
    else if (item.text) add(part, window.StudioMarkdown.render(item.text));
    if (item.sample) add(part, pictureAt({path: view.path, ...item.sample},
      'Sample slide for ' + item.label, review.expected));
    // The draft and the look are approved together: the draft as the slides tool draws it,
    // and the look the person picks.
    if (/^outline:/.test(item.target) && !theirs) {
      add(part, draftPanel(item.target.slice('outline:'.length) || null));
    }
    if (item.looks && !theirs) {
      const key = 'look:' + item.looks.artifact;
      const held = view.notes[key] || (view.notes[key] = { choice: '', words: '' });
      add(part, make('p', 'step-name', 'Pick the look of this deck'),
        lookPicker(item.looks, held, (now) => Object.assign(held, now)));
      if (item.looks.failed) {
        // Nothing is picked blind: the looks are drawn again, or the brand's default is
        // chosen knowingly, and goes with the approval.
        const lookProblem = alertLine('look-problem-' + item.looks.artifact);
        const again = capsule('Try again', '', () => redrawLooks(review, item.looks,
          lookProblem, again), 'looks-again-' + item.looks.artifact);
        const proceed = capsule('Use the brand’s default look', '', () => {
          held.choice = held.choice === 'default' ? '' : 'default';
          proceed.setAttribute('aria-pressed', String(held.choice === 'default'));
        }, 'looks-default-' + item.looks.artifact);
        proceed.setAttribute('aria-pressed', String(held.choice === 'default'));
        add(part, again, proceed, lookProblem);
      }
    }
    // A sample that could not be drawn is said in its place; the review goes on without it.
    if (item.sample_note) add(part, make('p', 'fix', item.sample_note));
    if (item.deck_view) {
      for (const slide of list(item.deck_view.slides)) add(part,
        pictureAt({path: view.path, artifact: item.target, number: slide.number},
          slide.title || 'Slide ' + slide.number, review.expected));
      for (const finding of list(item.deck_view.review?.findings)) add(part, make('p', 'fix',
        (finding.number ? 'Slide ' + finding.number + ': ' : '') + (finding.note || finding.question || 'Review finding')
        + (finding.fix ? ' Suggested: ' + finding.fix : '')));
      if (!list(item.deck_view.slides).length) add(part, make('p', 'fix', 'Slide pictures are unavailable on this computer. Read the saved deck before approving.'));
      add(part, capsule('Open the saved deck and its review', '', () => show('gate', {path: view.path, artifact: item.target}), 'read-' + item.target));
    }
    if (item.target.startsWith('yoodli:')) add(part, yoodliCopies({artifact: item.target, text: item.text}));
    if (review.phase === 'final' && /^(document|brief|deck)(@|$)|^(scenario|yoodli):/.test(item.target)) {
      add(part, capsule('Download ' + lower(item.label), 'quiet', (event) =>
        downloadFile(view.path, {artifact: item.target},
          String(item.file || '').split('/').pop() || item.target, event.currentTarget),
        'download-' + item.target));
    }
    if (item.notes) add(part, window.StudioMarkdown.render(item.notes));
    if (!theirs) {
      // Marked for changes, the item takes a note; the request goes with the others.
      const request = make('textarea'); request.maxLength = 4000;
      request.id = 'change-' + item.target;
      request.dataset.key = 'change-' + review.phase + '-' + item.target;
      const label = make('label', 'note-label', 'What should change in ' + item.label);
      label.htmlFor = request.id;
      request.setAttribute('aria-label', 'What should change in ' + item.label);
      const key = noteKeyOf(review, item);
      request.value = view.notes[key] || '';
      request.addEventListener('input', () => { view.notes[key] = request.value; });
      const hint = make('p', 'quiet', (list(item.rewrites).length ? 'If it changes, these are '
        + 'written again from it: ' + series(item.rewrites) + '.'
        + (item.returns ? ' They come back to this review.' : '')
        + (item.deck_again ? ' The deck is drawn again and stops for you first.' : '')
        : 'Nothing else is built from it.')
        + (item.research_price ? ' ' + item.research_price.words : item.redo ? ' ' + item.redo.says : ''));
      const asking = add(make('div', 'review-request'), label, request, hint);
      asking.hidden = mark !== 'changes';
      const marks = make('div', 'review-marks chips');
      marks.setAttribute('role', 'group');
      marks.setAttribute('aria-label', 'Your view of ' + item.label);
      const set = (value) => {
        view.marks[markKey(review, item)] = value;
        asking.hidden = value !== 'changes';
        for (const [name, chipNode] of Object.entries(both)) {
          chipNode.setAttribute('aria-pressed', String(value === name));
        }
        bar.update();
        // The toolbar follows: Send is the filled action once anything is marked.
        if (view.run && view.run.review === review) paintRun(false);
        if (value === 'changes') request.focus();
      };
      // Each chip names its item, so the same words on every item are told apart.
      const both = {
        changes: chip('Needs changes', mark === 'changes', (on) => set(on ? 'changes' : ''),
          'needs-' + item.target),
      };
      both.changes.setAttribute('aria-label', 'Needs changes in ' + item.label);
      // Looked at and fine: offered at every width, so the tally can count it.
      both.good = chip('Looks good', mark === 'good', (on) => set(on ? 'good' : ''),
        'good-' + item.target);
      both.good.setAttribute('aria-label', 'Looks good: ' + item.label);
      add(marks, both.good, both.changes);
      add(part, marks, asking);
    }
    add(node, detail);
  }
  if (bar) add(node, bar);
  return node;
}

function paintRun(fresh) {
  const run = view.run;
  // A training started on the desk is drawn by drafts.js. Every other run keeps this screen.
  if (onTheDesk(run)) {
    paintDesk(fresh);
    return;
  }
  const training = view.training
    || list(view.listing).find((found) => found.path === view.path) || {};
  const title = training.title || 'Untitled';
  const waiting = training.waiting && training.waiting.artifact ? training.waiting : null;
  const offered = run.problem && run.problem.action;
  // A training someone else runs, or nobody does, is read here and never changed.
  const theirs = run.mine === false;
  const driver = run.driver || null;
  const supplying = adding(run) && !theirs;
  const outline = outlining(run) && !theirs;
  const looking = Boolean(run.look && run.look.waiting) && !theirs;
  const free = theirs && !driver && !run.finished;
  // One filled button on the screen, for the first thing that is needed. While a sheet is
  // open it holds that button, so nothing under it is filled.
  const lead = view.sheet || view.after ? '' : theirs ? (run.finished ? 'finished'
    : free ? 'take' : '')
    : run.question ? 'answer' : offered ? 'problem'
      : supplying ? 'documents' : run.review ? 'combined' : waiting ? 'review' : outline ? 'outline'
        : looking ? 'look' : run.finished ? 'finished' : ['paused', 'stopped'].includes(run.state) ? 'resume'
          : run.state === 'failed' && !run.problem ? 'retry' : '';
  const limits = (view.setup && view.setup.limits) || {};
  const runs = !theirs ? 'Runs on this page' : driver ? 'Run by ' + nameOf(driver)
    : run.finished ? 'Finished' : 'Nobody is running it';
  const above = [make('span', '', [levelsText(training.levels), runs, ({balanced: 'Balanced review', automatic: 'Automatic draft review', step_by_step: 'Step by step review'})[run.review_level]]
    .filter(Boolean).join(' · '))];
  const published = view.issued && view.issued.path === view.path ? view.issued : null;
  const brought = view.adopted && view.adopted.path === view.path ? view.adopted : null;
  placeParts({ title, above, back: true, actions: theirs ? readActions(run, waiting)
    : runActions(run, waiting, lead),
  mark: [title, training.levels, run.state, lead, offered, waiting, outline
    && run.outline.level, theirs, driver, Boolean(run.outline), run.review,
    run.finished, run.review ? marked(run.review).length : 0] }, [
    ['intro', [run.state, run.sentence, run.decided, training.stages, view.steered,
      nextGate(run), Boolean(run.problem), runStanding(run), supplying, outline, theirs,
      run.queue, run.steps, run.workers, run.spent],
    () => runIntro(run, training)],
    run.can_migrate_desk ? ['migration', [view.path, run.can_migrate_desk], () => add(card('Continue saved work'),
      make('p', '', 'Preview which saved materials can open for editing in conversation.'),
      add(make('div', 'bar'), openDeskButton(view.path, '', true)))] : null,
    brought ? ['brought', brought, () => broughtPart(brought)] : null,
    theirs && (driver || !run.finished) ? ['theirs', [driver, lead, run.taken, run.notice,
      run.last_shared, run.kept, title], () => theirsPart(run, lead === 'take')] : null,
    !theirs && run.notice ? ['notice', [run.notice, run.clash, run.kept],
      () => noticePart(run)] : null,
    // What needs you: a worker's question, a problem, a copy changed in two places, and a
    // picture the deck waits for.
    run.question && theirs ? ['asked', [run.question, driver], () => askedPart(run)] : null,
    run.question && !theirs ? ['question', [run.question, title],
      () => questionPart(run, title)] : null,
    run.problem ? ['problem', [run.problem, lead, theirs],
      () => problemPart(run, lead === 'problem')] : null,
    list(run.copies).some(conflicted) ? ['conflict', [run.copies, view.copying, view.uncopied],
      () => conflictPart(run)] : null,
    waitsForPicture(run) ? ['picture', [run.deck.assets], () => picturePart(run)] : null,
    supplying ? ['documents', [run.documents, lead],
      () => documentsCard(run, lead === 'documents')] : null,
    // Then the review, or the gate.
    run.review ? ['combined-review', [run.review, theirs, lead],
      () => combinedReview(run, lead === 'combined')] : null,
    waiting && !run.question && !run.review && !theirs ? ['gate', [waiting, training.sentence],
      () => gatePart(training, waiting, run.sentence)] : null,
    outline && !run.question && !run.review ? ['outline', [run.outline.level, run.sentence],
      () => outlinePart(run)] : null,
    looking && !run.question && !run.review ? ['look', [run.look, run.sentence, lead],
      () => lookPart(run, lead === 'look')] : null,
    run.deck_left ? ['deck-left', [run.deck_left, run.sentence, theirs],
      () => deckLeftPart(run)] : null,
    !theirs && run.controls && (run.controls.finish_level || run.controls.finishing
      || run.controls.skip_deck) ? ['controls', [run.controls], () => controlsPart(run)] : null,
    // Then work in progress.
    noting(run) ? ['note', [run.note, run.state], () => notePart(run)] : null,
    // While a deck is drawn, its sections and their latest previews are what there is to see.
    run.deck ? ['deck', [run.deck, run.outline && run.outline.level],
      () => deckCard(run)] : null,
    run.research_progress ? ['research-progress', [run.research_progress, run.timing], () => researchActivity(run)] : null,
    list(run.workers).length ? ['workers', run.workers, () => workersCard(run)] : null,
    ['made', [training.path, training.view && training.view.files, theirs],
      () => madeCard(training, theirs)],
    ['steps', [list(run.steps).map((step) => [step.id, step.label, step.kind, step.status,
      step.attempts > 1, step.error]), run.note && run.note.used], () => stepsCard(run)],
    list(run.copies).some((found) => !conflicted(found)) ? ['copies', [run.copies,
      view.copying, view.uncopied, theirs], () => copiesCard(run)] : null,
    // Once that is all of them, what was added is kept on the screen, with nothing to press.
    run.documents && !supplying && !theirs ? ['documents', [run.documents, ''],
      () => documentsCard(run, false)] : null,
    ['cost', [run.spent, run.agent, run.model, run.effort, limits.training_dollars],
      () => costCard(run)],
    // Then what is finished.
    run.finished ? ['finished', [run.finished, lead, run.can_open_desk],
      () => finishedPart(run, lead === 'finished')] : null,
    theirs && !driver && run.finished ? ['free', [title], () => finishedFreePart()] : null,
    run.finished ? ['publish', [run.finished.ready, published, teamSpace()],
      () => publishCard(run, published)] : null,
    // What this computer runs for a team can be handed over, for anyone to take.
    !theirs && driver && driver.here ? ['mine', [driver, title, run.kept],
      () => minePart(driver, run.kept)] : null,
    !theirs && list(run.redesign).length ? ['redesign', [run.redesign, run.state],
      () => redesignCard(run)] : null,
    deletable(run) ? ['delete', [title], () => deleteCard()] : null,
  ], fresh);
  tickSteps(run);
  tidyPictures();
}

async function drawRun(fresh) {
  const turn = view.turn;
  if (fresh) {
    place({ title: 'Opening', back: true }, [make('p', 'quiet', 'Reading the run.')], true);
  }
  try {
    // The training's own files and record are read again only when the list says they
    // changed. The run is what moves while it works, so it is read each time.
    const record = recordOf(listed(view.path));
    const reread = fresh || !view.training || !record || record !== view.recorded;
    const [run, training] = await Promise.all([ask('run', { path: view.path }),
      reread ? ask('training', { path: view.path }).catch(() => null) : null]);
    if (turn !== view.turn) return;
    const first = fresh || !view.run;
    view.run = run;
    if (training) {
      view.training = training;
      view.recorded = record;
    }
    // A training started on the desk opens on its desk, which drafts.js reads and draws.
    if (onTheDesk(run)) {
      await drawDesk(first);
      if (first && turn === view.turn) later();
      return;
    }
    // Someone is in the middle of leaving the deck out. The run waits until they are done.
    if (!view.busy && !view.sheet) paintRun(first);
    // The intro is kept when nothing in it changed; the time in its now line still moves.
    tickNow(run);
    // A run just opened is read again at its own pace, not at the list's.
    if (first) later();
  } catch (failure) {
    if (turn !== view.turn) return;
    unopened(failure, !fresh && view.run, fresh,
      { said: 'Nothing was changed. The training itself is as it was.' });
  }
}

// --- what a deck says ------------------------------------------------------------------
// Every slide's words, put to the person before any slide is drawn. It is the runner's own
// gate, so it is read from the run and decided at an address of its own; it is drawn, and
// decided, like any other gate.

function outlined() {
  return Boolean(view.screen === 'outline' && view.run && view.run.outline);
}

// What there is to read here. When it changes under a reader, they say when to see it.
function outlineRead(outline) {
  return JSON.stringify([outline.level, outline.slides, outline.checked, outline.worth,
    outline.design]);
}

// Everything this screen is drawn from. When none of it has changed, nothing is redrawn.
function outlineDrawn() {
  const training = list(view.listing).find((found) => found.path === view.path) || {};
  return JSON.stringify([view.run.outline, view.run.state, view.run.sentence,
    Boolean(view.newer), training.title, training.stages]);
}

// One slide, as something to read: what kind it is, what it says, what it is for, and its
// notes, which are there to open and not in the way. With a design, how it is drawn sits
// beside what it says. `asked` lists the slides whose design is put to the person now.
function outlineSlide(slide, index, asked) {
  const node = make('li', 'outline-slide');
  add(node, make('p', 'quiet outline-top', 'Slide ' + (index + 1) + ' · '
    + spoken(slide.kind || 'slide')),
  make('h3', 'outline-title', slide.title || 'No title'));
  const copy = slide.design ? make('div', 'outline-copy') : node;
  add(copy, slide.subtitle ? make('p', 'outline-subtitle', slide.subtitle) : null,
    slide.understand ? add(make('p', ''), make('strong', '', 'It should leave the audience '
      + 'understanding: '), slide.understand) : null);
  const points = list(slide.points);
  if (points.length) {
    const items = make('ul', 'outline-points');
    for (const point of points) {
      add(items, add(make('li'), point.label ? make('strong', '', point.label
        + (point.text ? ': ' : '')) : null, point.text || ''));
    }
    add(copy, items);
  }
  const serves = list(slide.serves);
  add(copy,
    slide.caveat ? add(make('p', ''), make('strong', '', 'Caveat: '), slide.caveat) : null,
    slide.source ? add(make('p', 'quiet'), make('strong', '', 'Source: '), slide.source) : null,
    serves.length ? make('p', 'quiet', 'Serves ' + (serves.length === 1 ? 'objective '
      : 'objectives ') + series(serves) + '.') : null);
  if (slide.design) {
    add(node, add(make('div', 'outline-pair'), copy,
      outlineDesign(slide.design, Boolean(asked) && !asked.includes(slide.id))));
  }
  if (slide.notes) {
    const notes = make('details', 'outline-notes');
    notes.dataset.key = 'notes ' + (slide.id || index);
    add(node, add(notes, make('summary', '', 'Speaker notes for slide ' + (index + 1)),
      make('p', 'outline-said', slide.notes)));
  }
  return node;
}

// How one slide is drawn, as its design proposes: the visual and what it teaches, how it is
// laid out, the claim, what it was weighed against, its asset and the candidates still to
// find, and the wording its copy must keep. `kept` says its design was approved before and
// has not changed, so only the rest is asked about now.
function outlineDesign(design, kept) {
  const node = add(make('div', 'outline-drawn'), make('p', 'outline-label', 'How it is drawn'));
  const asset = design.asset || {};
  const alternative = design.alternative || {};
  add(node,
    kept ? make('p', 'quiet', 'Its design is as you approved it before.') : null,
    add(make('p', ''), make('strong', '', (spoken(design.family || 'visual')) + ': '),
      design.purpose || ''),
    design.drawn ? make('p', 'outline-said', design.drawn) : null,
    design.claim ? add(make('p', ''), make('strong', '', 'Claim: '), design.claim) : null,
    design.why ? add(make('p', 'quiet'), make('strong', '', 'Why: '), design.why) : null,
    alternative.treatment ? add(make('p', 'quiet'), make('strong', '', 'Weighed against: '),
      alternative.treatment + (alternative.reason ? '. ' + alternative.reason : '')) : null,
    asset.disposition === 'unavailable'
      ? add(make('p', ''), state('late', 'Its asset is unavailable'), ' ' + (asset.reason || ''))
      : add(make('p', 'quiet'), make('strong', '', asset.disposition === 'not-needed'
        ? 'No asset: ' : 'Asset: '), asset.disposition === 'not-needed' ? asset.reason || ''
        : asset.description || ''));
  const candidates = list(design.candidates);
  if (candidates.length) {
    const items = make('ul', 'outline-points');
    for (const candidate of candidates) {
      add(items, add(make('li'), spoken(candidate.kind || 'asset') + ' “' + (candidate.ref || '')
        + '” for ' + (candidate.concept || 'this slide') + ' · ',
      candidate.status === 'pending' ? state('late', 'not resolved yet')
        : make('span', 'quiet', 'resolved')));
    }
    add(node, items);
  }
  const keeps = list(design.keeps);
  return add(node, keeps.length ? add(make('p', ''), make('strong', '', 'Must keep: '),
    series(keeps.map((kept) => '“' + kept + '”'))) : null);
}

function outlineChecked(outline) {
  const checked = list(outline.checked);
  return add(make('section', 'paper aside-part'), make('h2', 'aside-title', 'Checked for you'),
    checked.length ? bullets(checked, 'reasons') : make('p', 'quiet', 'No automatic checks '
      + 'apply here. It is yours to read.'));
}

function outlineWorth(outline) {
  const items = make('ul', 'look');
  for (const text of list(outline.worth)) add(items, add(make('li'), state('late', text)));
  if (outline.note) {
    add(items, add(make('li'), state('current', 'You asked for changes'),
      make('p', 'quote', outline.note)));
  }
  return add(make('section', 'paper aside-part'), make('h2', 'aside-title', 'Worth a look'),
    items.childNodes.length ? items : make('p', 'quiet', 'Nothing was flagged.'));
}

// What the screen says before anything is decided: a newer version, or nothing to decide.
function outlineStanding(run) {
  if (view.newer) {
    return changedCallout(() => {
      view.run = view.newer;
      view.newer = null;
      paintOutline(false);
    });
  }
  if (run.outline.waiting) return null;
  return callout('', make('p', '', 'Nothing here is waiting for your decision now.'),
    make('p', 'quiet', run.sentence));
}

function paintOutline(fresh) {
  const run = view.run;
  const outline = run.outline;
  const training = list(view.listing).find((found) => found.path === view.path) || {};
  const title = training.title || 'Untitled';
  const label = capital(outlineLabel(outline));
  const home = () => show('run', { path: view.path });
  const above = [button(title, 'link', home, 'training'),
    outline && outline.level ? make('span', '', ' · Level ' + outline.level) : null];
  view.drawn = outlineDrawn();
  if (!outline) {
    // Reached before anything is written, or after it was put away: never a dead end.
    place({ title: label, name: label + ' · ' + title, above, back: true },
      [callout('', make('p', '', 'There is nothing here to read yet. What the deck says '
        + 'appears here once it is written.'), make('p', 'quiet', run.sentence)),
      add(make('div', 'bar'), capsule('Back to the run', view.after ? '' : 'filled', home,
        'home'))], fresh);
    drawSheet();
    return;
  }
  const slides = list(outline.slides);
  const items = make('ol', 'outline');
  // Slides whose design was approved before and is unchanged are not asked about again.
  const asked = outline.design && outline.waiting ? list(outline.design.asked) : null;
  slides.forEach((slide, index) => items.append(outlineSlide(slide, index, asked)));
  const doc = add(make('article', 'paper doc'), make('h2', 'doc-title',
    count(slides.length, 'slide', 'slides') + ', in order'), items);
  doc.setAttribute('aria-label', label);
  // Where it is decided here, the draft is shown as the slides tool draws it.
  if (outline.waiting && !outline.content_first && run.mine !== false) doc.prepend(draftPanel(outline.level));
  const aside = add(make('aside', 'aside'), outlineChecked(outline), outlineWorth(outline));
  aside.setAttribute('aria-label', 'The review');
  // What someone else runs is read here, and decided where it runs.
  const theirs = run.mine === false;
  const intro = add(make('div', 'intro'),
    state(...(outline.waiting ? ['review', theirs ? 'Waiting for a decision where it runs'
      : 'Waiting for your review'] : runStanding(run))),
    list(training.stages).length ? beads(training.stages, false) : null,
    make('p', 'lede', (outline.design ? 'This is every slide’s words, in order, beside how '
      + 'each is drawn, before any slide is drawn. '
      : 'This is every slide’s words, in order, before any slide is drawn. ')
      + (outline.waiting && theirs ? 'It is decided on the computer that runs this '
        + 'training. Here it can be read.'
        : outline.waiting ? 'Approve it, or say what should change: words are quick to change '
          + 'now, and slow to change once the slides are drawn.'
          : outline.design ? 'The slides are drawn from these words and this design.'
            : 'The slides are drawn from these words.')));
  // One filled button for the main thing to do, as at any gate. A newer version comes first.
  const actions = outline.waiting && !view.newer && !theirs ? [
    capsule('Ask for changes', '', openSheet('revise', 'revise'), 'revise'),
    capsule('Approve', 'filled', openSheet('approve', 'lead'), 'lead')] : [];
  place({ title: label, name: label + ' · ' + title, above, back: true, actions },
    [intro, outlineStanding(run), add(make('div', 'gate'),
      add(make('div', 'reading'), doc), aside)], fresh);
  drawSheet();
}

async function drawOutline(fresh) {
  const turn = view.turn;
  if (fresh) {
    place({ title: 'Opening', back: true }, [make('p', 'quiet', 'Reading what the deck says.')],
      true);
  }
  try {
    const run = await ask('run', { path: view.path });
    if (turn !== view.turn) return;
    const held = view.run && view.run.outline;
    if (fresh || !held) {
      view.run = run;
      view.newer = null;
      // Someone may be in the middle of deciding what was here a moment ago.
      if (fresh || !(view.sheet || view.after)) paintOutline(fresh);
      return;
    }
    // Never swap what is being read under a reader: they say when to see the new one.
    const moved = Boolean(run.outline) && outlineRead(run.outline) !== outlineRead(held);
    if (view.sheet || view.after || view.busy) {
      if (moved) view.newer = run;
      return;
    }
    view.newer = moved ? run : null;
    if (!moved) view.run = run;
    if (outlineDrawn() !== view.drawn) paintOutline(false);
  } catch (failure) {
    if (turn !== view.turn) return;
    unopened(failure, !fresh && view.run, fresh,
      { said: 'Nothing was changed. The training itself is as it was.' });
  }
}

// The next thing that needs the person, read from the list. A decision at a gate is told it
// by the server; a decision about what a deck says is answered with the run alone.
function nextNeed() {
  const found = pick('needs-you')[0];
  if (!found) return null;
  const asked = view.asks[found.path] || {};
  const artifact = (found.waiting || {}).artifact || null;
  return { path: found.path, title: found.title || 'Untitled', artifact,
    outline: !artifact && readsOutline(asked),
    sentence: asked.problem ? asked.problem.what : saysOf(found) };
}

async function decideOutline(decision, note, problem, pressed) {
  if (view.busy) return;
  if (view.newer) {
    // Nothing is decided about words that were not read. Refused here, before it is sent.
    say(problem, 'This changed while you had it open. Cancel, and read the new version '
      + 'first.');
    return;
  }
  const turn = view.turn;
  const noted = noteKey(decision);
  view.busy = true;
  pressed.disabled = true;
  let run;
  try {
    // What was read goes with the decision, so that words that changed since are not decided.
    const body = { path: view.path, level: view.run.outline.level || null, decision,
      note: note || null };
    if (view.run.outline.sha256) body.seen = view.run.outline.sha256;
    // And the design that was read beside the words, which the one decision answers too.
    const design = view.run.outline.design;
    if (design && design.revision) body.design = design.revision;
    run = await send('outline', body);
  } catch (failure) {
    say(problem, failure.message);
    pressed.disabled = false;
    view.busy = false;
    return;
  }
  delete view.notes[noted];
  view.busy = false;
  if (turn !== view.turn) return;
  view.run = run;
  view.newer = null;
  view.sheet = '';
  const halted = ['paused', 'stopped', 'failed'].includes(run.state);
  const said = OUTLINE_SAID[decision] + ' ' + (halted ? HALTED
    : run.sentence + (run.state === 'working' ? ' ' + CLOSE : ''));
  if (decision === 'approve') {
    toast(said);
    show('run', { path: view.path }, true);
    refresh();
    return;
  }
  let next = null;
  try {
    took(await ask('trainings'));
    await readAsks();
    next = nextNeed();
  } catch (failure) {
    // With the list out of reach, what happens next is still said; the way on is home.
    next = null;
  }
  if (turn !== view.turn) return;
  view.after = { said, next };
  paintOutline(false);
  byId('sheet').focus();
  refresh();
}

// --- with a team ---------------------------------------------------------------------
// A shared workspace has one driver for each training: the computer that runs it. Everyone
// else reads. The runner names the driver; where it names none, which is every workspace
// that is a folder on one computer, nothing from here to "the index" is ever shown.

function listed(path) {
  return list(view.listing).find((training) => training.path === path) || null;
}

// What the list says of a training's own record: when it last changed, and where it stands.
// A run's words change while it works, and are read from the run, so they are left out.
function recordOf(training) {
  if (!training) return '';
  const { run, sentence, ...rest } = training;
  return JSON.stringify(rest);
}

function nameOf(driver) {
  return String((driver && driver.name) || '').trim() || 'A teammate';
}

// A training that someone else's computer runs.
function elsewhere(training) {
  return Boolean(training && training.driver && training.driver.here === false);
}

function teamSpace() {
  const space = view.runner && view.setup ? view.setup.workspace : null;
  return Boolean(space && space.repository);
}

// Whether a folder is inside this computer's copy of the workspace.
function inWorkspace(path) {
  const space = view.runner && view.setup ? view.setup.workspace : null;
  const root = space && space.path ? String(space.path).replace(/[\\/]+$/, '') : '';
  return Boolean(root) && ['/', '\\'].some((mark) => String(path).startsWith(root + mark));
}

// A training in a shared workspace that was handed over: nobody runs it until someone
// takes it.
function unclaimed(training) {
  return Boolean(training && training.driver === null && !training.error && teamSpace()
    && inWorkspace(training.path) && training.state !== 'finished');
}

// A training that opens on its run: one the runner drives, here or on a teammate's
// computer, or one that waits for someone to take it.
function watched(training) {
  return Boolean(training && (training.run || elsewhere(training) || unclaimed(training)));
}

// Whether this computer may only read a training. Its run says so itself; away from the
// run, the list does: someone else has it, or nobody does.
function reads(path) {
  if (view.run && view.path === path && view.run.mine === false) return true;
  const found = listed(path);
  return elsewhere(found) || Boolean(found && found.mine === false);
}

// Whose a training is, where it is someone else's.
function whose(path) {
  const run = view.run && view.path === path ? view.run : null;
  const driver = (run && run.driver) || (listed(path) || {}).driver || null;
  return driver && driver.here === false ? nameOf(driver) : '';
}

// Who runs a training and since when, in a sentence.
function whoSays(driver, className) {
  const node = make('p', className);
  const who = driver.here ? 'This computer runs it'
    : nameOf(driver) + ' runs it from another computer';
  if (Number.isNaN(Date.parse(driver.since))) return add(node, who + '.');
  return add(node, who + ', and took it ', when(driver.since), '.');
}

function whoLine(training) {
  if (unclaimed(training)) {
    return make('p', 'quiet who', 'Nobody is running it. Anyone on your team may take it.');
  }
  return training && training.driver ? whoSays(training.driver, 'quiet who') : null;
}

function teammates() {
  return view.listing.filter((training) => !training.error && elsewhere(training));
}

// What this computer knows of a training a teammate runs: when it was last shared and where
// it stood then. It never says what is happening now, because that is not known here.
function lastLine(last, className) {
  if (!last) return null;
  const node = make('p', className);
  if (!Number.isNaN(Date.parse(last.at))) add(node, 'Last shared ', when(last.at), '. ');
  return add(node, (last.says ? String(last.says).trim() + ' ' : '')
    + 'It may have moved on since: this computer knows only what was shared.');
}

// One sentence for a training in a list: for one a teammate runs, what was last shared.
function lastOr(training, className) {
  return (elsewhere(training) && lastLine(training.last_shared, className))
    || make('p', className, saysOf(training));
}

// What the runner says about who has a training: that it was taken from this computer, or
// that it was changed on two computers at once.
function noticeLine(training) {
  return training && training.notice ? make('p', 'fix', training.notice) : null;
}

// Where what this computer set aside is kept, for someone who brings it back with git. The
// sentence beside it has already said, in plain words, that it is kept and can come back.
function keptLine(names) {
  const kept = list(names).filter(Boolean);
  if (!kept.length) return null;
  const space = view.setup && view.setup.workspace;
  const node = make('p', 'quiet', 'A detail for whoever brings it back: it is in this '
    + 'computer’s copy of the workspace' + (space && space.path ? ' (' + space.path + ')' : '')
    + ', where git keeps it under the name' + (kept.length > 1 ? 's ' : ' '));
  kept.forEach((name, index) => add(node, index ? ', ' : '', pathInto(make('code'), name)));
  return add(node, '. It is on this computer only, and is never sent to your team.');
}

function teamRow(training) {
  const title = training.title || 'Untitled';
  const text = add(make('div', 'row-text'), make('p', 'row-title', title),
    beads(training.stages, true), whoLine(training), lastOr(training, 'row-says'),
    noticeLine(training));
  const go = capsule('Open', 'quiet', openTraining(training), 'open ' + training.path);
  go.setAttribute('aria-label', 'Open ' + title + ', which ' + nameOf(training.driver)
    + ' runs');
  return add(make('li', 'row'), text, go);
}

// At a gate of a training someone else runs: why nothing here can be decided.
function readNote(path) {
  const name = whose(path);
  return callout('', make('p', '', (name ? name + ' runs this training, so it is decided '
    + 'on their computer.' : 'Nobody is running this training, so it cannot be decided '
    + 'until someone takes it.') + ' Here you can read it, with what the review found.'));
}

// A run that waits for its turn, and how many are ahead of it.
function queued(run) {
  return Boolean(run && run.queue && given(run.queue.ahead));
}

function queueSays(queue) {
  const ahead = Number(queue.ahead) || 0;
  return (ahead ? 'It is waiting its turn: ' + count(ahead, 'training is', 'trainings are')
    + ' ahead of it.' : 'It is waiting its turn, and is next.')
    + ' Trainings take turns in the order they became ready, and it starts by itself when '
    + 'its turn comes.';
}

// Open one of the team's confirmations. On a run, nothing under the sheet stays filled.
function askTeam(kind, opener) {
  return () => {
    openSheet(kind, opener)();
    if (view.screen === 'run' && view.run) paintRun(false);
  };
}

// The toolbar's side of a run that is only read: the ways to what there is to read.
function readActions(run, waiting) {
  const actions = [];
  if (run.finished?.ready && run.finished.index) {
    actions.push(capsule('Open the index', view.sheet ? '' : 'filled',
      () => show('index', { path: view.path, artifact: run.finished.index }), 'index'));
  }
  if (waiting) {
    actions.push(capsule('Read ' + waiting.label, '',
      () => show('gate', { path: view.path, artifact: waiting.artifact }), 'lead'));
  }
  if (run.outline && !run.deck) {
    actions.push(capsule('Read ' + outlineLabel(run.outline), '',
      () => show('outline', { path: view.path }), 'lead-outline'));
  }
  return actions;
}

// On a run this computer does not drive: who does and since when, what was last shared,
// that it is read here, and the way to take it. Where it was this computer's until it was
// taken, the runner's own sentence says so first: who took it, when, that this computer
// stopped, and that what it had not shared is kept. That is the runner's to say, so it is
// the same after a reload.
function theirsPart(run, lead) {
  const driver = run.driver;
  if (!driver) {
    return callout('yours', make('h2', 'aside-title', 'Nobody is running this training'),
      make('p', '', 'It was handed over, so anyone on your team may take it. Once you take '
        + 'it, it runs from this computer and carries on from where it stands.'),
      make('p', 'quiet', 'Until someone does, nothing more happens to it. ' + READ_ONLY),
      add(make('div', 'bar'), capsule('Take it', lead ? 'filled' : '',
        askTeam('take', 'take'), 'take')));
  }
  const name = nameOf(driver);
  const lost = run.taken || null;
  const kept = lost ? (list(run.kept).length ? run.kept : [lost.kept]) : [];
  return callout(lost ? 'late' : '', make('h2', 'aside-title', lost
    ? (String(lost.by || '').trim() || name) + ' took this training over'
    : name + ' is running this training'),
  lost ? make('p', '', run.notice || 'This computer stopped working on it, and nothing '
    + 'was deleted.') : null,
  keptLine(kept),
  whoSays(driver, ''), lastLine(run.last_shared, ''),
  make('p', 'quiet', READ_ONLY),
  add(make('div', 'bar'), capsule('Take it over', '', askTeam('take', 'take'), 'take')));
}

// A finished training in a shared workspace is nobody's. It is read and published as it
// stands; anything that changes it is refused until someone takes it, so that is offered.
function finishedFreePart() {
  return callout('', make('h2', 'aside-title', 'Nobody is running this training'),
    make('p', '', 'It is finished, so no computer runs it. It can be read, and published as '
      + 'it stands, from any computer on your team.'),
    make('p', '', 'To change anything in it, such as a decision that is in the way or a copy '
      + 'to make again, take it first. It then runs from this computer.'),
    add(make('div', 'bar'), capsule('Take it', '', askTeam('take', 'take'), 'take')));
}

// What the runner says about a training this computer runs: that it was changed on two
// computers at once, which is put right by carrying on from the shared version, or that
// it has just been.
function noticePart(run) {
  if (!run.clash) {
    return callout('', make('p', '', run.notice), keptLine(run.kept));
  }
  return callout('late', make('h2', 'aside-title', 'Changed on two computers at once'),
    make('p', '', run.notice),
    add(make('div', 'bar'), capsule('Carry on from the shared version', '',
      askTeam('take', 'take-shared'), 'take-shared')));
}

// A question that only the computer running the training can answer, shown to be read.
function askedPart(run) {
  const name = run.driver ? nameOf(run.driver) : '';
  return add(card('A question is waiting'),
    make('p', 'row-says', (run.question.from || 'A worker') + ' asks:'),
    make('p', 'row-quote', run.question.text),
    make('p', 'quiet', name ? 'Only ' + name + ' can answer it, on the computer that runs '
      + 'this training.' : 'It can be answered once someone takes this training.'));
}

function minePart(driver, kept) {
  const aside = keptLine(kept);
  return add(card('Who runs this training'), whoSays(driver, ''),
    make('p', 'quiet', 'Your teammates can read it, and only this computer can change it. '
      + 'If someone else should carry it on, hand it over: anyone on your team may then '
      + 'take it.'),
    aside ? make('p', 'quiet', 'Some of what this computer made for this training was set '
      + 'aside, because it had not been shared when the training carried on from the shared '
      + 'version. It is kept on this computer, and can be brought back.') : null, aside,
    add(make('div', 'bar'), capsule('Hand over', '', askTeam('hand-over', 'hand-over'),
      'hand-over')));
}

// A training that was just brought in: where the copy is, and that it is the one to use.
function broughtPart(brought) {
  return callout('', make('h2', 'aside-title', 'This is the copy, and the one to work on '
    + 'from now'),
  make('p', '', 'It was copied into your workspace, here:'),
  pathInto(make('p', 'path'), brought.path),
  make('p', '', 'The original is left exactly as it was, with nothing deleted, here:'),
  pathInto(make('p', 'path'), brought.from));
}

// A finished training is published from its own screen. Once it is, the card says which
// revision that made, and whether the team can see it yet.
function publishCard(run, published) {
  const node = add(card('Publish it'), make('p', '', PUBLISH_SAYS));
  if (published) {
    add(node, state('done', 'Published as revision ' + published.revision + '.'));
    if (!published.ready) {
      add(node, state('late', 'It was not ready to use when it was published, and the '
        + 'revision says so.'));
    }
    const notice = published.notice ? ' ' + published.notice : '';
    add(node, published.shared ? state('done', 'Shared: your team can see this revision.'
      + notice)
      : state(notice ? 'late' : 'none', (teamSpace() ? 'Not shared with your team yet.'
        : 'Kept on this computer: this workspace is not shared with anyone.') + notice));
  } else if (!run.finished.ready) {
    add(node, state('late', 'This training is not ready to use. It can still be published, '
      + 'and the revision will say that it was not ready.'));
  }
  return add(node, add(make('div', 'bar'),
    capsule(published ? 'Publish again' : 'Publish', '', askTeam('publish', 'publish'),
      'publish'),
    capsule('See what is published', 'quiet', () => show('published'), 'see-published')));
}

// A training this computer knows that the runner does not drive, and that is outside the
// workspace: one started in a conversation, in a folder of its own.
function adoptable(training) {
  return Boolean(view.runner && view.setup && view.setup.workspace && training
    && !training.error && !training.run && !training.driver
    && !inWorkspace(training.path));
}

function adoptCard(training) {
  if (!adoptable(training)) return null;
  return add(card('Run it from this page'),
    make('p', '', 'This training is not run from this page: it lives in a folder of its '
      + 'own, outside your workspace. Training Studio can carry it on from here instead, '
      + 'working on its own, and stops where its review level says, for your decision.'),
    add(make('div', 'bar'), capsule('Run this from here', '', askTeam('adopt', 'adopt'),
      'adopt')));
}

// What each confirmation says before anything is sent, and what its button is called.
function teamAsks(kind, title) {
  const run = view.run || {};
  if (kind === 'take' && run.clash && run.mine !== false) {
    return { title: 'Carry on with ' + title + ' from the shared version?',
      send: 'Carry on from it',
      says: [make('p', '', 'It was changed on this computer and on another at the same '
        + 'time. From then on it carries on from the version your team shares, and runs '
        + 'from this computer.'),
      make('p', '', 'What this computer made and never shared is set aside. It is kept on '
        + 'this computer and can be brought back; nothing is deleted.')] };
  }
  if (kind === 'take' && run.driver) {
    const name = nameOf(run.driver);
    const dated = !Number.isNaN(Date.parse(run.driver.since));
    return { title: 'Take ' + title + ' over from ' + name + '?', send: 'Take it over',
      says: [dated ? add(make('p', ''), 'It is ' + name + '’s: ' + name + ' took it ',
        when(run.driver.since), ', and runs it from another computer.')
        : make('p', '', 'It is ' + name + '’s, and runs from another computer.'),
      make('p', '', 'If you take it over, ' + name + '’s runner stops working on it and '
        + 'keeps what it had. From then on it runs from this computer, and only this '
        + 'computer can change it.'),
      make('p', 'quiet', name + ' is told who took it and when.')] };
  }
  if (kind === 'take') {
    return { title: 'Take ' + title + '?', send: 'Take it',
      says: [make('p', '', 'Nobody is running it. From then on it runs from this computer, '
        + 'and carries on from where it stands.'),
      run.finished ? make('p', 'quiet', 'It is finished, so nothing more is made until you '
        + 'change something. When you are done, hand it over, so that nobody is shown as '
        + 'running it.') : null] };
  }
  if (kind === 'hand-over') {
    return { title: 'Hand ' + title + ' over?', send: 'Hand it over',
      says: [make('p', '', 'This computer stops working on it, and keeps everything made so '
        + 'far.'),
      make('p', '', 'Anyone on your team may then take it and carry it on. Until someone '
        + 'does, nothing more happens to it.')] };
  }
  if (kind === 'publish') {
    const found = run.finished || {};
    const blocking = list(found.blocking).length;
    return { title: 'Publish ' + title + '?', send: 'Publish it',
      says: [make('p', '', PUBLISH_SAYS), make('p', '', PUBLISH_KEPT),
        found.ready ? null : state('late', 'This training is not ready to use'
          + (blocking ? ': ' + count(blocking, 'thing is', 'things are') + ' in the way' : '')
          + '. It can still be published, and the revision will say that it was not '
          + 'ready.')] };
  }
  return { title: 'Run ' + title + ' from here?', send: 'Copy it and run it here',
    says: [make('p', '', 'It is copied into your workspace as a new training. Training '
      + 'Studio carries the copy on from wherever the training has got to, with each '
      + 'decision made on this page.'),
    make('p', '', 'The original folder is left exactly as it was, with nothing deleted. '
      + 'Its own Git history stays where it is.'),
    make('p', '', 'From then on the copy is the one to work on, and this page takes you '
      + 'to it. A training brought in runs Step by step.')] };
}

function teamSheet(kind) {
  const title = (listed(view.path) || view.training || {}).title || 'Untitled';
  const spec = teamAsks(kind, title);
  const problem = problemLine();
  const confirm = capsule(spec.send, 'filled', () => settleTeam(kind, problem, confirm),
    'send');
  return [sheetTitle(spec.title), ...spec.says.filter(Boolean), problem,
    add(make('div', 'bar'), confirm, capsule('Cancel', 'quiet', closeSheet, 'cancel'))];
}

// Send what was confirmed. A refusal is said in the sheet, in the runner's own words, with
// what it means for the training: nothing was changed.
async function settleTeam(kind, problem, pressed) {
  if (view.busy) return;
  const turn = view.turn;
  const path = view.path;
  const to = { take: 'drive', 'hand-over': 'drive' }[kind] || kind;
  const body = to === 'drive' ? { path, action: kind } : { path };
  view.busy = true;
  pressed.disabled = true;
  let found;
  try {
    found = await send(to, body);
  } catch (failure) {
    view.busy = false;
    if (turn !== view.turn) return;
    say(problem, failure.message + (kind === 'adopt'
      ? ' Nothing was copied, and the training is exactly as it was.'
      : kind === 'publish' ? ' Nothing was published.' : ' Nothing was changed.'));
    pressed.disabled = false;
    pressed.focus();
    return;
  }
  view.busy = false;
  if (turn !== view.turn) return;
  view.sheet = '';
  if (kind === 'adopt') {
    view.adopted = { path: found.path, from: path };
    toast('Copied. The copy is the one to work on from now.');
    show('run', { path: found.path });
    refresh();
    return;
  }
  if (kind === 'publish') {
    view.issued = { path, revision: found.revision, ready: found.ready !== false,
      shared: Boolean(found.shared), notice: found.notice || '' };
    toast('Published as revision ' + found.revision + '.');
  } else {
    view.run = found;
    // Taking one that was changed on two computers answers with what was set aside. The
    // run goes on saying where that is kept; that it happened is told once, here.
    toast(kind === 'take' ? found.notice || 'It runs from this computer now.'
      : 'Handed over. Anyone on your team may take it now.');
  }
  drawSheet();
  view.barred = '';
  paintRun(false);
  if (!(kind === 'publish' && focusKey('publish'))) {
    window.scrollTo(0, 0);
    byId('title').focus({ preventScroll: true });
  }
  refresh();
}

// --- deleting a training ---------------------------------------------------------------
// A training this computer runs, or a finished one nobody runs, can be deleted. What goes and
// what stays is the runner's to say, so the sheet asks it first; nothing is sent until the
// person presses the button that names the training.

// Whether a run of the open training may be offered for deletion here. The runner decides;
// this only keeps the card off a training someone else runs.
function deletable(run) {
  return Boolean(view.runner && run && (run.mine !== false || (run.finished && !run.driver)));
}

function deleteCard() {
  // From a team's workspace it goes for the team too; from a local one, from here only.
  return add(card('Delete this training'), make('p', 'quiet', DELETE_SAYS
    + (teamSpace() ? DELETE_TEAM : '') + '.'),
    add(make('div', 'bar'), capsule('Delete this training', 'quiet', askDelete('delete'),
      'delete')));
}

// A training on Home or on Trainings offers the same sheet, beside the way into it, where
// the runner drives it and this computer may delete it. It is plain and quiet, never the
// filled one. One a conversation made is never the runner's to delete, so it offers none.
function deleteButton(training) {
  if (!mayDelete(training)) return null;
  const node = capsule('Delete', 'quiet', askDelete('delete ' + training.path, training),
    'delete ' + training.path);
  node.setAttribute('aria-label', 'Delete ' + (training.title || 'Untitled'));
  return node;
}

// A row's way in, with the way to delete it beside it where there is one.
function withDelete(go, training) {
  const remove = deleteButton(training);
  return remove ? add(make('div', 'bar row-actions'), go, remove) : go;
}

// Open the sheet for the open training, or for `training`, one on a list.
function askDelete(opener, training) {
  return async () => {
    const turn = view.turn;
    const doomed = training ? { path: training.path, title: training.title || 'Untitled' }
      : { path: view.path, title: (listed(view.path) || view.training || {}).title
        || 'Untitled' };
    view.doomed = doomed;
    view.leaving = null;
    openSheet('delete', opener)();
    if (view.screen === 'run' && view.run) paintRun(false);
    let found;
    try {
      found = await ask('delete', { path: doomed.path });
    } catch (failure) {
      found = { failed: failure.message };
    }
    if (turn !== view.turn || view.sheet !== 'delete' || view.doomed !== doomed) return;
    view.leaving = found;
    drawSheet();
    byId('sheet').focus();
  };
}

// Open the sheet for every ticked training. What deleting each would do is asked of the
// runner one at a time, with the same question one training's sheet asks.
async function askBulkDelete() {
  const turn = view.turn;
  const ticked = tickedOf('trainings');
  const doomed = view.listing.filter((training) => ticked.has(training.path))
    .map((training) => ({ path: training.path, title: training.title || 'Untitled' }));
  view.doomedMany = doomed;
  view.leavingMany = null;
  openSheet('bulk-delete', 'bulk-delete')();
  const found = [];
  for (const one of doomed) {
    let said;
    try {
      said = await ask('delete', { path: one.path });
    } catch (failure) {
      said = { may: false, why: failure.message };
    }
    if (turn !== view.turn || view.sheet !== 'bulk-delete' || view.doomedMany !== doomed) return;
    found.push({ ...one, may: Boolean(said.may), why: said.why || '',
      stops: Boolean(said.stops), share: said.share || '', drive: list(said.drive) });
  }
  view.leavingMany = found;
  drawSheet();
  byId('sheet').focus();
}

function bulkDeleteSheet() {
  const doomed = view.doomedMany || [];
  const head = sheetTitle('Delete ' + count(doomed.length, 'training', 'trainings') + '?');
  const cancel = capsule('Cancel', 'quiet', closeSheet, 'cancel');
  const found = view.leavingMany;
  if (!found) {
    return [head, make('p', 'quiet', 'Reading what would go.'), add(make('div', 'bar'), cancel)];
  }
  const going = found.filter((one) => one.may);
  const items = make('ul', 'reasons');
  for (const one of found) {
    items.append(make('li', '', one.title + ': ' + (one.may
      ? ['its folder and what only this computer kept for it.',
        DELETE_SHARED[one.share] || ''].filter(Boolean).join(' ')
      : (one.why || 'It cannot be deleted from here.') + ' It stays.')));
  }
  // What one training's sheet warns of, said once for all of them.
  const working = going.filter((one) => one.stops).map((one) => one.title);
  const stops = working.length === 1 ? working[0] + ' is working now. Deleting it stops it '
    + 'first, and ends everything it is running.' : working.length ? series(working)
    + ' are working now. Deleting them stops them first, and ends everything they are '
    + 'running.' : '';
  const drive = going.flatMap((one) => one.drive);
  const problem = problemLine();
  const confirm = going.length ? capsule('Delete ' + count(going.length, 'training',
    'trainings'), 'danger', () => settleBulkDelete(going, confirm), 'send') : null;
  return [head, stops ? state('late', stops) : null, items,
    drive.length ? make('p', '', DELETE_DRIVE) : null,
    drive.length ? add(make('ul', 'plain'), ...drive.map(driveItem)) : null,
    make('p', 'quiet', DELETE_UNDO), problem,
    add(make('div', 'bar'), confirm, cancel)].filter(Boolean);
}

// Delete each in turn, with the same request one training's sheet sends. A refusal does not
// stop the rest; each that stayed is named, in the runner's own words.
async function settleBulkDelete(going, pressed) {
  if (view.busy) return;
  const turn = view.turn;
  const doomed = view.doomedMany;
  view.busy = true;
  for (const node of byId('sheet').querySelectorAll('button')) node.disabled = true;
  pressed.disabled = true;
  const stayed = [];
  const notices = [];
  let deleted = 0;
  for (const one of going) {
    if (view.sheet !== 'bulk-delete' || view.doomedMany !== doomed) {
      view.busy = false;
      toast('Stopped after deleting ' + deleted + ' of ' + count(going.length, 'training',
        'trainings') + '. The rest are as they were.');
      if (turn === view.turn) draw(false);
      refresh();
      return;
    }
    try {
      const said = await send('delete', { path: one.path, title: one.title });
      if (said && said.notice && !notices.includes(said.notice)) notices.push(said.notice);
      deleted += 1;
      view.listing = list(view.listing).filter((training) => training.path !== one.path);
      tickedOf('trainings').delete(one.path);
    } catch (failure) {
      stayed.push(one.title + ': ' + failure.message);
    }
  }
  view.busy = false;
  if (turn !== view.turn) return;
  view.sheet = '';
  view.doomedMany = null;
  view.leavingMany = null;
  toast(['Deleted ' + deleted + ' of ' + count(going.length, 'training', 'trainings') + '.',
    ...notices, ...stayed].join(' '));
  drawSheet();
  draw(false);
  if (!focusKey('bulk-delete')) byId('title').focus({ preventScroll: true });
  refresh();
}

// One file left in Google Drive, as a link that opens in a new tab.
function driveItem(found) {
  const words = found.what + ': ' + (found.name || 'untitled');
  if (!WEB_LINK.test(String(found.url || ''))) return make('li', '', words);
  const node = make('a', 'link', words);
  node.href = found.url;
  node.rel = 'noopener noreferrer';
  node.target = '_blank';
  node.setAttribute('aria-label', words + ', in a new tab');
  return add(make('li'), node);
}

function deleteSheet() {
  const title = (view.doomed || listed(view.path) || view.training || {}).title || 'Untitled';
  const found = view.leaving;
  const head = sheetTitle('Delete ' + title + '?');
  const cancel = capsule('Cancel', 'quiet', closeSheet, 'cancel');
  if (!found) {
    return [head, make('p', 'quiet', 'Reading what would go.'), add(make('div', 'bar'), cancel)];
  }
  if (found.failed || !found.may) {
    return [head, make('p', '', (found.failed || found.why || 'It cannot be deleted from '
      + 'here.') + ' Nothing was deleted.'), add(make('div', 'bar'), cancel)];
  }
  const documents = Number(found.documents) || 0;
  const revisions = Number(found.revisions) || 0;
  const drive = list(found.drive);
  const goes = [['Its folder in your workspace, with every file in it.',
    DELETE_SHARED[found.share] || ''].filter(Boolean).join(' '),
  'What only this computer kept for it: ' + (documents ? count(documents,
    'document you supplied', 'documents you supplied') + ', ' : '')
    + 'the pages saved for its research, its previews and its run record.'];
  const stays = [revisions ? count(revisions, 'published revision', 'published revisions')
    + '. ' + (revisions === 1 ? 'It stays' : 'They stay') + ' in your workspace’s history, '
    + 'and the page no longer lists ' + (revisions === 1 ? 'it.' : 'them.') : null,
  DELETE_UNDO].filter(Boolean);
  const problem = problemLine();
  const confirm = capsule('Delete ' + title, 'danger', () => settleDelete(title, problem,
    confirm), 'send');
  return [head,
    found.stops ? state('late', DELETE_STOPS) : null,
    make('h3', 'sheet-part', 'What goes'), bullets(goes),
    make('h3', 'sheet-part', 'What stays'), bullets(stays),
    drive.length ? make('p', '', DELETE_DRIVE) : null,
    drive.length ? add(make('ul', 'plain'), ...drive.map(driveItem)) : null,
    problem, add(make('div', 'bar'), confirm, cancel)].filter(Boolean);
}

// Send the deletion. A refusal is said in the sheet, in the runner's own words. Once it is
// done the training is gone: from one of its own screens the page goes home, in place of
// that screen, and a list is drawn again without it.
async function settleDelete(title, problem, pressed) {
  if (view.busy) return;
  const turn = view.turn;
  const path = (view.doomed || {}).path || view.path;
  view.busy = true;
  pressed.disabled = true;
  let found;
  try {
    found = await send('delete', { path, title });
  } catch (failure) {
    view.busy = false;
    if (turn !== view.turn) return;
    say(problem, failure.message + (/\bdeleted\b/.test(failure.message) ? ''
      : ' Nothing was deleted.'));
    pressed.disabled = false;
    pressed.focus();
    return;
  }
  view.busy = false;
  if (turn !== view.turn) return;
  view.sheet = '';
  view.doomed = null;
  view.leaving = null;
  toast('Deleted ' + title + '.' + (found && found.notice ? ' ' + found.notice : ''));
  if (['home', 'trainings'].includes(view.screen)) {
    // The list loses the card at once; the runner's own list follows.
    view.listing = list(view.listing).filter((training) => training.path !== path);
    drawSheet();
    draw(false);
  } else {
    show('home', null, true);
  }
  refresh();
}

// --- a deck drawn again from a design ------------------------------------------------------
// Offered for each deck of the run that was drawn without a design. Nothing happens until the
// person says yes in the sheet: it is never done for them, after an update or otherwise.

function redesignCard(run) {
  const node = card('Draw a deck again from a design');
  add(node, make('p', '', REDESIGN_SAYS));
  for (const found of list(run.redesign)) {
    const pressed = capsule(list(run.redesign).length > 1 ? 'Redesign ' + lower(found.label)
      : 'Redesign', '', () => {
      view.redesigning = found;
      openSheet('redesign', 'redesign-' + (found.level || 'deck'))();
      paintRun(false);
    }, 'redesign-' + (found.level || 'deck'));
    pressed.disabled = run.state === 'working';
    add(node, add(make('div', 'bar'), pressed));
    if (!found.may && found.why) add(node, make('p', 'quiet', found.why));
  }
  if (run.state === 'working') {
    add(node, make('p', 'quiet', 'Pause the training, or wait until it stops for you, to ask '
      + 'for this.'));
  }
  return node;
}

function redesignSheet() {
  const found = view.redesigning || {};
  const head = sheetTitle('Redesign ' + lower(found.label || 'the slide deck') + '?');
  const cancel = capsule('Cancel', 'quiet', closeSheet, 'cancel');
  if (!found.may) {
    return [head, make('p', '', (found.why || 'This computer cannot draw a deck from a design '
      + 'yet.') + ' Nothing was changed.'), add(make('div', 'bar'), cancel)];
  }
  const problem = problemLine();
  const confirm = capsule('Redesign it', 'filled', () => settleRedesign(found, problem,
    confirm), 'send');
  return [head, make('h3', 'sheet-part', 'What happens'), bullets(REDESIGN_DOES),
    make('h3', 'sheet-part', 'What is kept'), bullets(REDESIGN_KEEPS),
    make('p', 'quiet', REDESIGN_COSTS), problem, add(make('div', 'bar'), confirm, cancel)];
}

// Ask for it. A refusal is said in the sheet, in the runner's own words; once it is asked, the
// run is shown as the runner now has it, writing what the deck says again.
async function settleRedesign(found, problem, pressed) {
  if (view.busy) return;
  const turn = view.turn;
  view.busy = true;
  pressed.disabled = true;
  let run;
  try {
    run = await send('redesign', { path: view.path, level: found.level || null });
  } catch (failure) {
    view.busy = false;
    if (turn !== view.turn) return;
    say(problem, failure.message);
    pressed.disabled = false;
    pressed.focus();
    return;
  }
  view.busy = false;
  if (turn !== view.turn) return;
  view.sheet = '';
  view.redesigning = null;
  if (run) view.run = run;
  drawSheet();
  toast(found.label + ' is being drawn again from a design. What it says comes back to you '
    + 'first.');
  paintRun(false);
}

// --- with a team: every run at once ----------------------------------------------------

async function readStatus() {
  try {
    view.status = await ask('status');
  } catch (failure) {
    // A runner that does not answer this leaves the screen as it was before there was one.
    view.status = null;
  }
}

// One training as the status screen shows it, whether the runner listed it there or the
// list of trainings did.
function statusOf(found) {
  const known = listed(found.path) || {};
  const run = found.run || {};
  return { path: found.path, title: found.title || known.title || 'Untitled',
    levels: found.levels || known.levels, state: run.state || found.state,
    sentence: run.sentence || found.sentence || '', queue: found.queue || run.queue || null,
    spent: found.spent || run.spent || {}, driver: found.driver || known.driver || null,
    needs: Boolean(found.needs), notice: found.notice || known.notice || '',
    last_shared: found.last_shared || known.last_shared || null };
}

function statusWords(found) {
  if (queued(found)) return ['none', 'Waiting its turn'];
  return RUN_WORDS[found.state] || STATES[found.state] || RUN_WORDS.working;
}

function spentSays(spent) {
  // A cost of nothing is never said as $0.00.
  if (given(spent.dollars) && Number(spent.dollars) > 0) {
    return Number(spent.dollars) < 0.005 ? 'less than $0.01' : money(spent.dollars);
  }
  return given(spent.tokens) ? Number(spent.tokens).toLocaleString() + ' tokens'
    : 'Not reported yet';
}

// What last went wrong in what the runner does by itself in the background, in its own
// words, and when. It is said until that work goes right again.
function backgroundLine() {
  const wrong = view.status && view.status.background;
  if (!wrong || !wrong.says) return null;
  const node = add(make('p', 'fix'), String(wrong.says));
  if (!Number.isNaN(Date.parse(wrong.at))) add(node, ' This was ', when(wrong.at), '.');
  return node;
}

// The trainings teammates run, apart from this computer's own.
function teammatesCard() {
  if (!view.runner) return null;
  const theirs = (view.status ? list(view.status.elsewhere) : teammates()).map(statusOf);
  if (!theirs.length && !(view.status && teamSpace())) return null;
  const node = card('Run by your teammates');
  if (!theirs.length) {
    return add(node, make('p', 'quiet', 'No teammate is running a training right now, as '
      + 'far as this computer has been told.'), fetchLine());
  }
  const items = make('ul', 'rows');
  for (const found of theirs) {
    const go = capsule('Open', 'quiet', () => show('run', { path: found.path }),
      'theirs ' + found.path);
    go.setAttribute('aria-label', 'Open ' + found.title + ', to read it');
    add(items, add(make('li', 'row'), add(make('div', 'row-text'),
      make('p', 'row-title', found.title),
      found.driver ? whoSays(found.driver, 'who') : null,
      lastLine(found.last_shared, 'row-says')
        || (found.sentence ? make('p', 'row-says', found.sentence) : null),
      noticeLine(found)), go));
  }
  return add(node, make('p', 'quiet', 'Each can be opened and read here. Only the computer '
    + 'that runs a training can change it.'), items, fetchLine());
}

// --- with a team: the computer's own notification ----------------------------------------

// The set-up as it stands, as a change to it is sent: whole, so that one answer changing
// leaves every other as it was.
function setupAsItIs() {
  const held = view.setup;
  const space = held.workspace || {};
  const agent = held.agent || {};
  const body = { folder: space.folder, branch: space.branch, name: space.name,
    share_when: space.share_when, agent: agent.default, model: agent.model || null,
    effort: agent.effort || null, limits: held.limits };
  if (space.repository) body.repository = space.repository;
  else body.path = space.path;
  if (held.previews && held.previews.how) body.previews = held.previews.how;
  const chosen = brandSkills().find((skill) => skill.chosen);
  if (brandSkills().length > 1 && chosen) body.brand_skill = chosen.path;
  return body;
}

async function setNotify(index, node) {
  if (view.notifying) return;
  view.notifying = true;
  view.unnotified = '';
  slide(node, index);
  try {
    view.setup = await send('setup', { ...setupAsItIs(), notify: Boolean(index) });
    toast(index ? 'On. This computer tells you when no page is open.'
      : 'Off. This computer says nothing when no page is open.');
  } catch (failure) {
    // The thumb slides home again: the card is not built again when it says what it said.
    slide(node, index ? 0 : 1);
    view.unnotified = failure.message + ' Nothing was changed.';
  }
  view.notifying = false;
  if (view.screen === 'settings') draw(false);
}

// Settings, with the runner: the notification for when no page is open. It is the
// computer's own, and is kept apart from the browser's, which is the card above.
function notifyCard() {
  const found = view.runner && view.setup ? view.setup.notify : null;
  if (!found) return null;
  const node = add(card('When this page is closed'), make('p', '', NOTIFY_SAYS));
  if (found.can) {
    add(node, add(make('div', 'setting'),
      make('p', 'row-title', 'Tell me when no page is open'),
      segmented('Tell me when no page is open', ['Off', 'On'], found.on ? 1 : 0, setNotify,
        'notify')));
    if (found.problem) add(node, make('p', 'fix', found.problem));
  } else {
    add(node, state('off', found.on ? 'Turned on, but this computer cannot do it now.'
      : 'This computer cannot do this.'),
    make('p', 'fix', found.problem || 'It has no way to show a notification of its own.'));
  }
  const problem = alertLine('notify-problem');
  say(problem, view.unnotified);
  return add(node, problem, make('p', 'quiet', NOTIFY_DIFFERS));
}

// --- Training Studio and its skills --------------------------------------------------------
// What the runner found when it last looked at its links, the companion skills and the
// releases. It puts back by itself only what the installer placed. A companion is brought
// only once the person says yes in the sheet, and a newer release is only ever said.

function upkeepOf() {
  return view.runner && view.setup ? view.setup.upkeep || null : null;
}

function wantedCompanions(found) {
  return list(found && found.companions).filter((one) => ['missing', 'older']
    .includes(one.state));
}

function updating(found) {
  return Boolean(found && found.update && found.update.state === 'running');
}

// What the update in hand is doing, or how the last one went. None before there was one.
function updateLine(found) {
  const update = (found && found.update) || {};
  if (!update.state) return null;
  const node = add(make('p', ''), state(update.state === 'running' ? 'current'
    : update.state === 'done' ? 'done' : 'late', update.says || ''));
  if (update.state === 'running' && !Number.isNaN(Date.parse(update.since))) {
    add(node, ' Started ', when(update.since), '.');
  }
  return node;
}

// The way to the sheet that asks before the companions are brought.
function updateBar(found) {
  if (!found || !found.update || !found.update.offered) return null;
  return add(make('div', 'bar'), capsule('Update the skills', '', openSheet('companions',
    'update-skills'), 'update-skills'));
}

// --- versions: what is installed, the newest, and upgrading Training Studio -----------------
// The runner works out every row; the page only says it. Training Studio is upgraded only
// once the person says yes in the sheet, and restarted only when they press Restart.

function versionsOf() {
  const found = upkeepOf();
  return found && found.versions ? found.versions : null;
}

function upgradeOf(found) {
  return (found && found.upgrade) || {};
}

// The brand skill's install: what it would install, from where, and how the last one went.
function brandOf(found) {
  return (found && found.brand) || {};
}

// Whether Home tells of the versions: an upgrade or a brand install in hand or how it went,
// an upgrade waiting for a restart, or something newer or missing, until it is dismissed.
function versionsNotice() {
  const found = versionsOf();
  if (!found) return false;
  if (['running', 'restart', 'restarting', 'failed'].includes(upgradeOf(found).state)) return true;
  if (['running', 'failed', 'changed'].includes(brandOf(found).state)) return true;
  return Boolean(found.key && !found.dismissed);
}

function wantedRows(found) {
  return list(found && found.rows).filter((row) => ['update', 'missing'].includes(row.state));
}

// The companions among what is wanted: what comes with a newer Training Studio.
function wantedCompanionRows(found) {
  return wantedRows(found).filter((row) => row.name !== 'training-studio'
    && row.kind !== 'brand');
}

// One row's versions in a few words: from what is here to what it would be.
function versionStep(row) {
  if (row.state === 'missing') return row.name + ' ' + row.target + ', which is missing';
  return row.name + ' ' + row.installed + ' → ' + row.target;
}

// What the upgrade in hand is doing, or how it went, with Restart once it is installed.
function upgradeParts(found) {
  const upgrade = upgradeOf(found);
  if (!upgrade.state) return [];
  const shape = { running: 'current', restart: 'done', restarting: 'current' }[upgrade.state]
    || 'late';
  const parts = [add(make('p', ''), state(shape, upgrade.says || ''))];
  if (upgrade.state === 'restart' && upgrade.restart) {
    const go = capsule('Restart', 'quiet', () => restartNow(go), 'restart');
    parts.push(add(make('div', 'bar'), go));
  }
  return parts;
}

// What the brand skill's install in hand is doing, or how it went.
function brandParts(found) {
  const brand = brandOf(found);
  if (!brand.state) return [];
  const shape = { running: 'current', done: 'done' }[brand.state] || 'late';
  const node = add(make('p', ''), state(shape, brand.says || ''));
  if (brand.state === 'running' && !Number.isNaN(Date.parse(brand.since))) {
    add(node, ' Started ', when(brand.since), '.');
  }
  return [node];
}

// The ways on from the versions: upgrade, the companions' own update, or the command a
// checkout is upgraded with.
function versionsBar(found, dismiss) {
  const upkeep = upkeepOf();
  const upgrade = upgradeOf(found);
  const buttons = [];
  if (upgrade.offered) {
    const companions = wantedCompanionRows(found).length > 0;
    buttons.push(capsule(companions ? 'Upgrade everything' : 'Upgrade', '',
      openSheet('upgrade', 'upgrade'), 'upgrade'));
  } else if (!upgrade.state && upkeep && upkeep.update && upkeep.update.offered) {
    buttons.push(capsule('Update the skills', '', openSheet('companions', 'update-skills'),
      'update-skills'));
  }
  const brand = brandOf(found);
  if (brand.offered && brand.state !== 'running') {
    buttons.push(capsule(brand.action + ' the brand skill', '', openSheet('brand', 'brand'),
      'brand'));
  }
  if (dismiss && found.key && !upgrade.state) {
    buttons.push(capsule('Dismiss', 'quiet', () => dismissVersions(found.key), 'dismiss'));
  }
  const parts = buttons.length ? [add(make('div', 'bar'), ...buttons)] : [];
  if (found.checkout && found.command && wantedRows(found).length) {
    parts.unshift(make('p', 'sentence', found.command));
    parts.push(add(make('div', 'bar'), copyButton('Copy the command', 'Command copied',
      found.command, 'copy-update')));
  }
  return parts;
}

// Home: said only when something is newer or missing, or an upgrade is in hand.
// A studio Marketing Studio installed is updated by it, and by nothing here.
const SUITE_SAYS = 'Marketing Studio installs and updates this studio. To update it, unpack a '
  + 'newer Marketing Studio release and run marketing-studio update --from <the unpacked '
  + 'folder> --yes.';

function suiteLine() {
  const [before, rest] = SUITE_SAYS.split('marketing-studio update');
  return add(make('p', ''), before,
    make('code', '', 'marketing-studio update' + rest.replace(/\.$/, '')), '.');
}

function updatesCard() {
  const upkeep = upkeepOf();
  if (!upkeep) return null;
  const found = versionsOf();
  if (!versionsNotice() && !updating(upkeep)) return null;
  const node = card('Updates');
  if (found && versionsNotice()) {
    const wanted = wantedRows(found);
    if (found.suite === 'marketing-studio') {
      add(node, suiteLine());
      for (const row of wanted) add(node, add(make('p', ''), state('review', row.says)));
    } else if (wanted.length && !['restart', 'restarting'].includes(upgradeOf(found).state)) {
      add(node, make('p', '', 'Newer versions are ready for this computer:'),
        bullets(wanted.map(versionStep)));
      for (const row of wanted) add(node, add(make('p', ''), state('review', row.says)));
    }
    add(node, ...upgradeParts(found), ...brandParts(found));
  }
  if (updating(upkeep)) add(node, updateLine(upkeep));
  else if (found && versionsNotice()) add(node, ...versionsBar(found, true));
  return node;
}

// Status: a row for each of the three, with everything that was said of it.
function versionsCard() {
  const found = versionsOf();
  if (!found) return null;
  const node = card('Versions');
  node.id = 'versions';
  const table = make('table', 'table');
  const head = make('tr');
  for (const title of ['Skill', 'Installed', 'Newest', 'Pinned to', 'State']) {
    const top = make('th', '', title);
    top.scope = 'col';
    head.append(top);
  }
  const body = make('tbody');
  for (const row of list(found.rows)) {
    const name = make('th', '', row.name);
    name.scope = 'row';
    const [shape, words] = VERSION_STATES[row.state] || VERSION_STATES.unknown;
    const pinned = row.pinned ? row.pinned + (row.next && row.next !== row.pinned
      ? ', ' + row.next + ' with the newest Training Studio' : '') : '—';
    body.append(add(make('tr'), name, cell('Installed', row.installed || 'not installed'),
      cell('Newest', row.newest || 'not known'), cell('Pinned to', pinned),
      cell('State', state(shape, words))));
  }
  add(node, add(table, add(make('thead'), head), body));
  const facts = make('ul', 'facts');
  for (const row of list(found.rows)) {
    for (const said of [row.says, row.beyond, row.reports]) {
      if (said) facts.append(add(make('li', 'fact'), bead(said === row.says
        ? (VERSION_STATES[row.state] || VERSION_STATES.unknown)[0] : 'none'),
      make('span', '', said)));
    }
  }
  add(node, facts, found.suite === 'marketing-studio' ? suiteLine() : null,
    ...upgradeParts(found), ...brandParts(found), ...versionsBar(found, false));
  const releases = (upkeepOf() || {}).releases || {};
  const known = (list(found.rows)[0] || {}).known_at;
  add(node, releasesLine(upkeepOf()));
  if (releases.problem && known && !Number.isNaN(Date.parse(known))) {
    add(node, add(make('p', 'quiet'), 'What is shown was last known ', when(known), '.'));
  }
  return node;
}

// The sheet that asks before Training Studio is upgraded: what, from where, and what next.
function upgradeSheet() {
  const found = versionsOf();
  const upgrade = upgradeOf(found);
  const cancel = capsule('Cancel', 'quiet', closeSheet, 'cancel');
  if (!upgrade.offered) {
    return [sheetTitle('Upgrade Training Studio?'), make('p', '', upgrade.says
      || 'There is nothing to upgrade now.'), add(make('div', 'bar'), cancel)];
  }
  const own = list(found.rows)[0] || {};
  const companions = wantedCompanionRows(found);
  const problem = problemLine();
  const confirm = capsule('Upgrade now', 'filled', () => settleUpgrade(problem, confirm),
    'send');
  const parts = [sheetTitle('Upgrade Training Studio to ' + upgrade.version + '?'),
    make('h3', 'sheet-part', 'What happens'),
    bullets(['Training Studio ' + upgrade.version + ' is fetched from '
      + (upgrade.from === 'tag' ? 'its release' : 'the newest version on ' + upgrade.from)
      + ' in Training Studio’s own repository, and its own installer checks it.',
    'It is installed beside ' + (own.installed || 'this version') + '. ' + UPGRADE_KEEPS,
    'Then you restart Training Studio to use it. This page comes back by itself.'])];
  if (companions.length) {
    parts.push(make('h3', 'sheet-part', 'Then the skills'),
      make('p', '', 'After the restart, Home offers the companion skills Training Studio '
        + upgrade.version + ' is made with, to bring with one more yes:'),
      bullets(companions.map(versionStep)));
  }
  return [...parts, make('p', 'quiet', UPGRADE_WAITS), problem,
    add(make('div', 'bar'), confirm, cancel)];
}

async function settleUpgrade(problem, pressed) {
  if (view.busy) return;
  const turn = view.turn;
  view.busy = true;
  pressed.disabled = true;
  let answered;
  try {
    answered = await send('upgrade', { version: upgradeOf(versionsOf()).version });
  } catch (failure) {
    view.busy = false;
    if (turn !== view.turn) return;
    say(problem, failure.message + ' Nothing was changed.');
    pressed.disabled = false;
    pressed.focus();
    return;
  }
  view.busy = false;
  if (turn !== view.turn) return;
  if (view.setup && answered) view.setup = { ...view.setup, upkeep: answered.upkeep };
  closeSheet();
  toast('Upgrading Training Studio. Home and the Status screen say how it goes.');
  draw(false);
}

// The sheet that asks before the brand skill is installed: the repository, the release and
// its revision, and what happens. Nothing is fetched or run before the yes.
function brandSheet() {
  const brand = brandOf(versionsOf());
  const cancel = capsule('Cancel', 'quiet', closeSheet, 'cancel');
  if (!brand.offered) {
    return [sheetTitle('Install the brand skill?'), make('p', '', brand.says
      || 'There is nothing to install now.'), add(make('div', 'bar'), cancel)];
  }
  const problem = problemLine();
  const confirm = capsule(brand.action + ' it now', 'filled', () => settleBrand(problem,
    confirm), 'send');
  return [sheetTitle(brand.action === 'Upgrade'
    ? 'Upgrade the brand skill from ' + brand.installed + ' to ' + brand.version + '?'
    : 'Install the brand skill ' + brand.version + '?'),
  make('h3', 'sheet-part', 'What is installed'),
  bullets(['Release ' + brand.release + ', at revision ' + brand.commit + '.',
    'From ' + brand.repository + '.']),
  make('h3', 'sheet-part', 'What happens'), bullets(BRAND_STEPS),
  make('p', '', BRAND_TRUST), make('p', 'quiet', BRAND_WAITS), problem,
  add(make('div', 'bar'), confirm, cancel)];
}

async function settleBrand(problem, pressed) {
  if (view.busy) return;
  const turn = view.turn;
  view.busy = true;
  pressed.disabled = true;
  let answered;
  try {
    answered = await send('brand/install', { release: brandOf(versionsOf()).release });
  } catch (failure) {
    view.busy = false;
    if (turn !== view.turn) return;
    say(problem, failure.message + ' Nothing was changed.');
    pressed.disabled = false;
    pressed.focus();
    return;
  }
  view.busy = false;
  if (turn !== view.turn) return;
  if (view.setup && answered) view.setup = { ...view.setup, upkeep: answered.upkeep };
  closeSheet();
  toast('Installing the brand skill. Home and the Status screen say how it goes.');
  draw(false);
}

async function dismissVersions(key) {
  try {
    const answered = await send('versions', { dismiss: key });
    if (view.setup && answered) view.setup = { ...view.setup, upkeep: answered.upkeep };
  } catch (failure) {
    toast(failure.message);
    return;
  }
  toast('Dismissed. Home says so again when a newer version is out.');
  setTitle();
  draw(false);
}

// Restart: the runner stops and opens its newer version, on the same address and with the
// same key, so this page waits for it and then loads the newer page.
async function restartNow(pressed) {
  if (view.restarting) return;
  const version = upgradeOf(versionsOf()).version;
  pressed.disabled = true;
  let answered;
  try {
    answered = await send('restart', {});
  } catch (failure) {
    pressed.disabled = false;
    toast(failure.message);
    return;
  }
  if (view.setup && answered) view.setup = { ...view.setup, upkeep: answered.upkeep };
  view.restarting = true;
  view.comingBack = { version, tries: 0 };
  toast('Restarting Training Studio. This page comes back by itself.');
  draw(false);
  window.setTimeout(comeBack, 1000);
}

// Asked once a second: whether the newer version answers yet. Once it does, its page is
// loaded. If it never does, the person is told to open it again.
async function comeBack() {
  const waiting = view.comingBack;
  if (!waiting) return;
  try {
    const found = await ask('capabilities');
    if (found && found.version === waiting.version) {
      window.location.reload();
      return;
    }
  } catch (failure) {
    // Not there yet, while it stops and starts again.
  }
  waiting.tries += 1;
  if (waiting.tries < COME_BACK_TRIES) {
    window.setTimeout(comeBack, 1000);
    return;
  }
  view.restarting = false;
  view.comingBack = null;
  notify('Training Studio did not come back by itself. Open it again with its command or '
    + 'its launcher.');
}

// What set-up says, and a browser notification once for each newer version Home tells of.
function tookSetup(found) {
  view.setup = found;
  view.setupAt = Date.now();
  const versions = versionsOf();
  const key = versions && versions.key && !versions.dismissed ? versions.key : null;
  const before = view.versionsTold;
  view.versionsTold = key;
  if (before === undefined || !key || key === before || alerts() !== 'granted') return;
  try {
    const note = new Notification('Training Studio can be upgraded',
      { body: wantedRows(versions).map(versionStep).join('; '), tag: 'versions' });
    note.onclick = () => {
      window.focus();
      note.close();
      show('home');
    };
  } catch (failure) {
    // A browser that will not show one still has the count in the tab title.
  }
}

function linkWords(link) {
  if (link.state === 'ok') return ['done', link.assistant + ': Training Studio is linked.'];
  if (link.state === 'repaired') return ['done', link.says];
  return [link.state === 'missing' ? 'late' : 'none', link.says];
}

const COMPANION_BEADS = { ok: 'done', missing: 'late', older: 'late', unread: 'none' };

function releasesLine(found) {
  const releases = (found && found.releases) || {};
  if (releases.on === false) {
    return make('p', 'quiet', 'Looking online for newer releases is turned off, in Settings.');
  }
  if (releases.problem) return make('p', 'fix', releases.problem);
  if (!releases.at || Number.isNaN(Date.parse(releases.at))) {
    return make('p', 'quiet', 'Newer releases have not been looked for yet.');
  }
  return add(make('p', 'quiet'), 'Newer releases were last looked for ', when(releases.at),
    list(releases.newer).length ? '.' : '. Nothing newer was found.');
}

// Status: everything that was found, what was put back, and the update.
function skillsCard() {
  const found = upkeepOf();
  if (!found) return null;
  const node = card('Training Studio and its skills');
  add(node, make('p', '', 'Training Studio ' + found.version + '.'
    + (found.guidance && found.guidance.says ? ' ' + found.guidance.says : '')));
  if (found.checking) {
    return add(node, make('p', 'quiet', 'Looking at the skills on this computer.'));
  }
  if (found.problem) add(node, make('p', 'fix', found.problem));
  const facts = make('ul', 'facts');
  for (const link of list(found.links)) {
    const [shape, words] = linkWords(link);
    facts.append(add(make('li', 'fact'), bead(shape), make('span', '', words)));
  }
  for (const one of list(found.companions)) {
    facts.append(add(make('li', 'fact'), bead(COMPANION_BEADS[one.state] || 'none'),
      make('span', '', one.says)));
  }
  add(node, facts);
  for (const said of list(found.repaired)) {
    if (!list(found.links).some((link) => link.says === said)) {
      add(node, add(make('p', ''), state('done', said)));
    }
  }
  return add(node, updateLine(found), updating(found) ? null : updateBar(found));
}

// The sheet that asks before the companions are brought: what, from where, and how.
function updateSheet() {
  const wanted = wantedCompanions(upkeepOf());
  const head = sheetTitle('Update the companion skills?');
  const cancel = capsule('Cancel', 'quiet', closeSheet, 'cancel');
  if (!wanted.length) {
    return [head, make('p', '', 'Every companion skill is already as new as this Training '
      + 'Studio was made with.'), add(make('div', 'bar'), cancel)];
  }
  const problem = problemLine();
  const confirm = capsule('Update them now', 'filled', () => settleUpdate(problem, confirm),
    'send');
  return [head, make('h3', 'sheet-part', 'What is brought'),
    bullets(wanted.map((one) => one.name + ' ' + one.wanted + ', from ' + one.repository
      + ' at revision ' + one.commit + '.')),
    make('p', '', UPDATE_SAYS),
    ...wanted.filter((one) => one.note).map((one) => make('p', '', one.note)),
    make('p', 'quiet', UPDATE_WAITS), problem,
    add(make('div', 'bar'), confirm, cancel)];
}

async function settleUpdate(problem, pressed) {
  if (view.busy) return;
  const turn = view.turn;
  view.busy = true;
  pressed.disabled = true;
  let answered;
  try {
    answered = await send('companions', {});
  } catch (failure) {
    view.busy = false;
    if (turn !== view.turn) return;
    say(problem, failure.message + ' Nothing was changed.');
    pressed.disabled = false;
    pressed.focus();
    return;
  }
  view.busy = false;
  if (turn !== view.turn) return;
  if (view.setup && answered) view.setup = { ...view.setup, upkeep: answered.upkeep };
  closeSheet();
  toast('Updating the skills. The Status screen says how it goes.');
  draw(false);
}

async function setLook(index, node) {
  if (view.turningLook) return;
  view.turningLook = true;
  view.lookRefused = '';
  slide(node, index);
  try {
    view.setup = await send('setup', { ...setupAsItIs(), look_for_updates: Boolean(index) });
    toast(index ? 'On. Training Studio looks for newer releases once a day.'
      : 'Off. Training Studio no longer looks online for newer releases.');
  } catch (failure) {
    slide(node, index ? 0 : 1);
    view.lookRefused = failure.message + ' Nothing was changed.';
  }
  view.turningLook = false;
  if (view.screen === 'settings') draw(false);
}

// Settings, with the runner: whether it looks online for newer releases.
function lookCard() {
  const found = view.runner && view.setup ? view.setup.updates : null;
  if (!found) return null;
  const node = add(card('Updates'), make('p', '', LOOK_SAYS),
    add(make('div', 'setting'), make('p', 'row-title', 'Look for updates once a day'),
      segmented('Look for updates once a day', ['Off', 'On'], found.look ? 1 : 0, setLook,
        'look')));
  const problem = alertLine('look-problem');
  say(problem, view.lookRefused);
  return add(node, problem, add(make('div', 'bar'),
    capsule('See the versions', 'quiet', () => show('status'), 'see-versions')));
}

// Settings, with the runner: where the brand skill is installed from. What is typed is kept
// while the screen is drawn again, and is checked by the runner before it is saved.
function brandSourceCard() {
  const found = view.runner && view.setup ? view.setup.brand : null;
  if (!found) return null;
  if (!view.brandForm) {
    view.brandForm = { repository: found.repository || '', release: found.release || '',
      seen: 'shared' in view.setup ? sharedOf() : null };
  }
  const form = view.brandForm;
  const node = add(card('Brand skill'), make('p', '', BRAND_SAYS),
    field('brand-repository', 'Its repository', form, 'repository',
      { hint: 'An https or ssh address, as git clones it. Git reaches it as you, without '
        + 'asking for anything.' }),
    field('brand-release', 'Which release', form, 'release',
      { short: true, hint: 'Empty for the newest, or a release’s tag, such as v1.4.0.' }));
  if (found.repository) {
    add(node, make('p', 'quiet', 'Installed from ' + found.repository + ', '
      + (found.release ? 'release ' + found.release : 'the newest release') + '.'));
  }
  const problem = alertLine('brand-problem');
  say(problem, view.brandRefused);
  const save = capsule(view.savingBrand ? 'Checking…' : 'Check and save', '',
    () => saveBrand(save), 'brand-save');
  save.disabled = view.savingBrand;
  return add(node, problem, add(make('div', 'bar'), save));
}

async function saveBrand(pressed) {
  if (view.savingBrand) return;
  const form = view.brandForm;
  const repository = form.repository.trim();
  view.savingBrand = true;
  view.brandRefused = '';
  pressed.disabled = true;
  try {
    const body = { repository, release: form.release.trim() };
    if (form.seen) body.shared_seen = form.again ? sharedOf() : form.seen;
    view.setup = await send('brand', body);
    view.brandForm = null;
    toast(repository ? 'Saved. The Status screen shows which release can be installed.'
      : 'Forgotten. A brand skill already installed is still used.');
  } catch (failure) {
    view.brandRefused = failure.message + ' Nothing was changed.';
    // What is typed here is the person's own: saved again, it is meant over what the page
    // has read by then.
    form.again = true;
  }
  view.savingBrand = false;
  if (view.screen === 'settings') draw(false);
}

// --- with a team: what is published ------------------------------------------------------
// Each training the workspace has published, at its latest revision, with its index to read.

function publishedMatch(found) {
  const held = filtersOf('published', { text: '', ready: '', by: '' });
  if (held.ready === 'ready' && !found.ready) return false;
  if (held.ready === 'not-ready' && found.ready) return false;
  if (held.by && found.by !== held.by) return false;
  const text = String(held.text || '').toLowerCase();
  return !text || [found.title, found.by].some((words) => String(words || '').toLowerCase()
    .includes(text));
}

function publishedRow(found) {
  const title = found.title || 'Untitled';
  const go = capsule('Open the index', 'quiet',
    () => show('index', { path: found.path, artifact: INDEX }), 'index ' + found.path);
  go.setAttribute('aria-label', 'Open the index of ' + title);
  // The index that opens is the training's as it stands on this computer now. Where the
  // training has changed since the revision, that is not what was published, and is said.
  const moved = found.current === false ? make('p', 'fix', 'It has changed on this computer '
    + 'since revision ' + found.revision + ' was published, so the index here is the '
    + 'training as it stands now, not as it was published. Publish it again to make that '
    + 'the next revision.') : null;
  const name = make('th');
  name.scope = 'row';
  add(name, make('span', 'row-title', title), moved);
  return add(make('tr'), name, cell('Revision', String(found.revision)),
    cell('Published', when(found.at), found.by ? ' by ' + found.by : ''),
    cell('Ready to use', found.ready ? state('done', 'Ready to use when it was published')
      : state('late', 'Not ready to use when it was published')),
    cell('', go));
}

function publishedFilters(found) {
  const held = filtersOf('published', { text: '', ready: '', by: '' });
  const names = [...new Set(found.map((entry) => entry.by).filter(Boolean))].sort();
  return keepTyped(window.StudioLists.filterRow({ key: 'published',
    search: { id: 'text', label: 'Search', value: held.draft === undefined ? held.text
      : held.draft, hint: 'By its title or who published it' },
    choices: [{ id: 'ready', label: 'Ready to use', value: held.ready,
      options: [['', 'Any'], ['ready', 'Ready to use'], ['not-ready', 'Not ready to use']] }],
    // Published by is offered only where there is someone to choose.
    more: names.length ? [{ id: 'by', label: 'Published by', value: held.by,
      options: [['', 'Anyone'], ...names.map((who) => [who, who])] }] : [],
    open: Boolean(view.filtersOpen.published),
    changed: (key, value) => { held[key] = value; paintPublished(false); },
    searched: (text) => { held.text = text; held.draft = text; paintPublished(false); },
    toggled: (open) => { view.filtersOpen.published = open; } }), held);
}

function paintPublished(fresh) {
  const found = view.shelf;
  if (!found.length) {
    place({ title: 'Published', back: true }, [add(make('section', 'card shine invite'),
      make('h2', 'invite-title', 'Nothing is published yet'),
      make('p', '', 'A finished training is published from its own screen: open it, and '
        + 'choose “Publish”. It is then listed here, with its index to read.'),
      add(make('div', 'bar'), capsule('See your trainings', 'filled',
        () => show('trainings'), 'home')))], fresh);
    return;
  }
  const shown = found.filter(publishedMatch);
  const table = make('table', 'table');
  const head = make('tr');
  for (const title of ['Training', 'Revision', 'Published', 'Ready to use', '']) {
    const top = make('th', '', title);
    top.scope = 'col';
    if (!title) add(top, make('span', 'offscreen', 'Open'));
    head.append(top);
  }
  const body = make('tbody');
  for (const entry of shown) body.append(publishedRow(entry));
  add(table, add(make('thead'), head), body);
  place({ title: 'Published', back: true },
    [pageHead(count(found.length, 'training is', 'trainings are')
      + ' published in this workspace, each shown at its latest revision.'),
    publishedFilters(found),
    add(card('Published trainings'), shown.length ? table : make('p', 'quiet',
      'No published training matches. Change or clear the filters.'),
    make('p', 'quiet', 'A revision is never moved once it is published.'))], fresh);
}

async function drawPublished(fresh) {
  const turn = view.turn;
  if (fresh) {
    view.shelf = null;
    place({ title: 'Published', back: true },
      [make('p', 'quiet', 'Reading what is published.')], true);
  }
  try {
    const found = list((await ask('published')).published);
    if (turn !== view.turn) return;
    const mark = JSON.stringify(found);
    if (view.shelf && mark === view.drawn) return;
    const first = !view.shelf;
    view.shelf = found;
    view.drawn = mark;
    paintPublished(first);
  } catch (failure) {
    if (turn !== view.turn) return;
    if (!view.shelf) view.drawn = 'unread';
    unopened(failure, view.shelf, true, { title: 'What is published cannot be read',
      said: 'Nothing was changed. Whatever is published is as it was.',
      back: 'Back to your trainings', to: () => show('trainings') });
  }
}

// --- the index -----------------------------------------------------------------------
// README.md at the top of a finished training, read like any other of its files. It is
// written once, when the training finishes, so it is read once and not again.

async function drawIndex(fresh) {
  if (!fresh) return;
  const turn = view.turn;
  const path = view.path;
  const found = list(view.listing).find((training) => training.path === path) || {};
  const home = () => show(homeOf(path), { path });
  view.drawn = 'index';
  place({ title: 'Opening', back: true }, [make('p', 'quiet', 'Reading the index.')], true);
  try {
    const read = await ask('file', { path, artifact: view.artifact });
    if (turn !== view.turn) return;
    const download = capsule('Download the index', 'filled', (event) => downloadFile(path,
      { artifact: 'README.md' }, 'README.md', event.currentTarget), 'download-index');
    place({ title: 'The index', name: 'The index · ' + (found.title || 'Untitled'), back: true,
      above: [button(found.title || 'Untitled', 'link', home, 'training')],
      actions: [download] },
    [pageHead('Everything this training made, with where each file is.'),
      add(make('div', 'reading index'), documentBody(asDocument(read),
        { label: 'The index', path, files: true }))], true);
  } catch (failure) {
    if (turn !== view.turn) return;
    unopened(failure, false, true, { title: 'The index cannot be opened',
      said: 'Nothing was changed. The training and everything it made are as they were.',
      back: 'Back to the training', to: home });
  }
}

// --- staying up to date --------------------------------------------------------------

function waitingKey(training) {
  const waiting = training.waiting || {};
  // What a run needs when it is not at a gate is in its own sentence: a question, a problem.
  return training.path + '\n' + (waiting.artifact || '') + '\n' + (waiting.question || '')
    + (training.run && !waiting.artifact ? '\n' + training.run.sentence : '');
}

// Open what needs the person, as its row on home would: a gate, what a deck says, or the
// training, where a question or a problem is answered.
function needed(training) {
  const waiting = training.waiting || {};
  const asked = view.asks[training.path] || {};
  if (!waiting.artifact && readsOutline(asked)) {
    show('outline', { path: training.path });
  } else if (waiting.artifact && !asked.question && !asked.problem) {
    reviewAction(training)();
  } else {
    openTraining(training)();
  }
}

// Tell the person, once, about each new thing that needs them. A notification that is
// clicked opens what it was about.
function took(listing) {
  view.listing = list(listing.trainings);
  view.needs = Number(listing.needs) || 0;
  // What a teammate runs is theirs to decide: it is never counted, or told, as needing you.
  const waiting = view.listing.filter((training) => training.state === 'needs-you'
    && !elsewhere(training));
  if (view.listing.some((training) => training.state === 'needs-you'
      && elsewhere(training))) {
    view.needs = Math.min(view.needs, waiting.length);
  }
  // What the runner says about who has a training is told once when it is new: that one
  // was taken from this computer, or was changed on two at once. It is the runner's to
  // say, so the row and the run still say it after a reload.
  const noticed = {};
  for (const training of view.listing) {
    if (!training.notice) continue;
    noticed[training.path] = training.notice;
    if (view.known && view.noticed[training.path] !== training.notice) {
      toast((training.title || 'Untitled') + ': ' + training.notice);
    }
  }
  view.noticed = noticed;
  const keys = waiting.map(waitingKey);
  for (const training of view.known ? waiting : []) {
    if (view.known.includes(waitingKey(training))) continue;
    const said = (training.title || 'Untitled') + ': ' + saysOf(training);
    toast(said);
    if (alerts() !== 'granted') continue;
    try {
      const note = new Notification('Training Studio needs you',
        { body: said, tag: waitingKey(training) });
      note.onclick = () => {
        window.focus();
        note.close();
        needed(training);
      };
    } catch (failure) {
      // A browser that will not show one still has the count in the tab title.
    }
  }
  view.known = keys;
}

// Someone is in the middle of writing in a box: the list is left as it is until they are done.
function typing() {
  const active = document.activeElement;
  return Boolean(active && (active.tagName === 'TEXTAREA' || active.tagName === 'INPUT')
    && active.value && main().contains(active));
}

// A run that is working is read more often, while its own screen is open.
function pace() {
  if (document.hidden) return POLL_HIDDEN;
  return view.screen === 'run' && view.run && view.run.state === 'working' ? POLL_RUN
    : POLL_SHOWN;
}

function later() {
  window.clearTimeout(view.timer);
  view.timer = window.setTimeout(refresh, pace());
}

// One refresh at a time, so an older answer never lands after a newer one. One asked for
// while another is in hand is done once that one is, and once however often it was asked.
async function refresh() {
  window.clearTimeout(view.timer);
  if (view.refreshing) {
    view.again = true;
    return view.refreshing;
  }
  view.refreshing = (async () => {
    do {
      view.again = false;
      await catchUp();
    } while (view.again);
  })();
  try {
    await view.refreshing;
  } finally {
    view.refreshing = null;
  }
  later();
  return undefined;
}

// Read what has changed and draw it. A tab nobody is looking at reads only the list, for the
// count in its title and what to tell; the rest is read when it is looked at again.
async function catchUp() {
  // While the runner opens its newer version, it is not there to be asked.
  if (view.restarting) return;
  try {
    if (view.runner === undefined) await discover();
    if (document.hidden && view.listing) {
      // Set-up is read now and then too, for a newer version to be told of.
      const setup = Boolean(view.runner) && Date.now() - view.setupAt > SETUP_HIDDEN;
      const [found, listing] = await Promise.all([setup ? ask('setup') : null,
        ask('trainings')]);
      if (setup) tookSetup(found);
      took(listing);
      notify('');
      setTitle();
      return;
    }
    // Set-up is read where it is shown, and once to begin with.
    const setup = Boolean(view.runner) && (!view.setup || SET_UP_SHOWN.includes(view.screen));
    const [found, listing] = await Promise.all([setup ? ask('setup') : null, ask('trainings')]);
    if (setup) tookSetup(found);
    took(listing);
    await Promise.all([readAsks(),
      view.computer === undefined
        ? ask('computer').then((seen) => { view.computer = seen.computer; }) : null,
      view.runner && view.screen === 'status' ? readStatus() : null]);
    notify('');
    setTitle();
    for (const node of document.querySelectorAll('time')) {
      const then = Date.parse(node.dateTime);
      if (!Number.isNaN(then)) node.textContent = ago(then);
    }
    frame();
    if (unset() && view.screen !== 'setup') {
      show('setup', null, true);
    } else if (['gate', 'training', 'run', 'outline', 'published'].includes(view.screen)) {
      await draw(false);
    } else if (view.screen === 'setup' || view.screen === 'new' || view.screen === 'index') {
      // A form is drawn once and never again under the person filling it in. So is the
      // index, under the person reading it.
      if (!view.drawn) draw(true);
    } else if (!view.busy && !view.checking && !view.notifying && !view.turningLook
        && !view.savingBrand && !typing()
        && view.drawn !== signature()) {
      draw(!view.drawn);
    }
  } catch (failure) {
    // Reading the list needs nothing but the key, so a refusal here is about the link.
    notify(failure.kind === 'refused' ? noticeOf('refused') : failure.message);
  }
}

// Marketing Studio names its own address when it opens this studio, so the page can link back
// to that tab. Only the same scheme and host on another port is accepted.
function suiteHome(hash, here) {
  const named = new URLSearchParams(String(hash).replace(/^#/, '')).get('home') || '';
  const found = /^(https?:)\/\/([^/:?#@\s]+):(\d{1,5})\/?$/.exec(named);
  return found && found[1] === here.protocol && found[2] === here.hostname && found[3] !== here.port
    && Number(found[3]) > 0 && Number(found[3]) < 65536
    ? found[1] + '//' + found[2] + ':' + found[3] : '';
}
// Marketing Studio says when it opened this studio in its own tab, as it does on a phone: the
// way back then stays in this tab, where Marketing Studio still holds its key.
// The return key stays in a fragment and tab memory, bound to the validated home origin.
// A phone's network home port can differ from the native server's loopback home port.
function rememberedSuiteHome(here) {
  try {
    const saved = JSON.parse(sessionStorage.getItem('marketing-studio-return') || 'null');
    if (saved && /^[A-Za-z0-9_-]{8,256}$/.test(saved.token || '')
        && suiteHome('#home=' + encodeURIComponent(saved.home), here) === saved.home) return saved.home;
  } catch (failure) {}
  return '';
}
function suiteReturn(home, hash, here) {
  if (!home || suiteHome('#home=' + encodeURIComponent(home), here) !== home) return '';
  const offered = suiteHome(hash, here) === home
    ? new URLSearchParams(String(hash).replace(/^#/, '')).get('homeToken') || '' : '';
  const valid = value => typeof value === 'string' && /^[A-Za-z0-9_-]{8,256}$/.test(value);
  let key = valid(offered) ? offered : '';
  try {
    const saved = JSON.parse(sessionStorage.getItem('marketing-studio-return') || 'null');
    if (!key && saved?.home === home && valid(saved.token)) key = saved.token;
    if (key) sessionStorage.setItem('marketing-studio-return', JSON.stringify({home, token: key}));
  } catch (failure) {
    // The current private link still works when tab storage is unavailable.
  }
  return home + '/' + (key ? '#token=' + encodeURIComponent(key) : '');
}
function suiteBack(hash) {
  return new URLSearchParams(String(hash).replace(/^#/, '')).get('back') === 'tab';
}
// Marketing Studio also names its home page's port on this page when it started this studio, so
// the way back is found however the page was reached. Marketing Studio shares this page's host.
function suitePort(port, here) {
  return /^[1-9][0-9]{0,4}$/.test(String(port || ''))
    ? suiteHome('#home=' + encodeURIComponent(here.protocol + '//' + here.hostname + ':' + port), here) : '';
}

function linkToken() {
  const found = /(?:^#|&)token=([A-Za-z0-9_-]+)/.exec(window.location.hash);
  return found ? found[1] : '';
}

function begin() {
  const symbol = byId('studio-symbol');
  if (symbol) symbol.append(icon('studio'));
  view.token = linkToken();
  // A new link pasted into a tab that is already open changes only the fragment.
  window.addEventListener('hashchange', () => {
    const next = linkToken();
    if (next && next !== view.token) {
      view.token = next;
      refresh();
    }
  });
  for (const [id, screen, drawing] of NAV) {
    const item = byId(id);
    item.prepend(icon(drawing));
    item.addEventListener('click', () => show(screen));
  }
  const suite = byId('go-suite');
  // The key's fragment is lost when a link changes the address, so the way back is kept for this tab.
  // The port the server names belongs to the Marketing Studio that started it, so it is preferred
  // to one kept from an earlier session.
  let home = suiteHome(window.location.hash, window.location)
    || rememberedSuiteHome(window.location) || suitePort(document.body?.dataset?.suitePort, window.location);
  try {
    home = home || sessionStorage.getItem('marketing-studio-home') || '';
    if (home) sessionStorage.setItem('marketing-studio-home', home);
  } catch (failure) {
    // No tab storage: the address in this link is still used.
  }
  if (suite && home) {
    suite.href = suiteReturn(home, window.location.hash, window.location);
    let back = suiteBack(window.location.hash);
    try {
      back = back || sessionStorage.getItem('marketing-studio-back') === 'tab';
      if (back) sessionStorage.setItem('marketing-studio-back', 'tab');
    } catch (failure) {
      // No tab storage: the address in this link is still used.
    }
    if (back) suite.removeAttribute('target');
    suite.prepend(icon('suite'));
    suite.hidden = false;
  }
  window.addEventListener('popstate', (event) => {
    view.pushed = Math.max(0, view.pushed - 1);
    open(event.state || { screen: 'home' });
  });
  window.addEventListener('pagehide', () => {
    if (view.screen === 'run' && view.path && typeof leaveDesk === 'function') leaveDesk(view.path);
  });
  window.addEventListener('beforeunload', (event) => {
    if (view.screen === 'run' && DESK.held[view.path] && pendingDeskEdits(view.path).length
        && !keepDeskRecovery(view.path)) { event.preventDefault(); event.returnValue = ''; }
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refresh();
    else if (view.screen === 'run' && view.path && typeof shareDesk === 'function') shareDesk(view.path);
  });
  // Escape puts away whatever is open: a menu first, then the sheet.
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const menus = Array.from(document.querySelectorAll('.menu')).filter((menu) => menu.open);
    if (menus.length) {
      for (const menu of menus) menu.open = false;
      focusKey('more');
    } else if (!byId('sheet').hidden && !view.busy) {
      closeSheet();
    }
  });
  document.addEventListener('click', (event) => {
    for (const menu of document.querySelectorAll('.menu')) {
      if (menu.open && !menu.contains(event.target)) menu.open = false;
    }
  });
  // The arrow keys turn the slides at a deck's gate, from the slides themselves or from the
  // head of the screen. They are left alone in a sheet, in a box, and with a modifier held,
  // which is how a browser goes back.
  document.addEventListener('keydown', (event) => {
    const by = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
    if (!by || !view.viewer || !byId('sheet').hidden) return;
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const active = document.activeElement;
    const slides = byId('slides');
    if (active && ![document.body, byId('title'), main()].includes(active)
        && !(slides && slides.contains(active))) return;
    view.viewer.move(by);
  });
  // The link's fragment holds the key, so the skip link must not replace it.
  document.querySelector('.skip').addEventListener('click', (event) => {
    event.preventDefault();
    main().focus();
  });
  if (!view.token) {
    place({ title: 'This page needs its link' }, [], true);
    notify(noticeOf('refused'));
    return;
  }
  open(window.history.state || { screen: 'home' });
  refresh();
}

begin();
