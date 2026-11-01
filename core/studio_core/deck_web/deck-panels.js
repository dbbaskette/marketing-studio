// The deck panels both studios' pages show, served by the shared page server: the brand's
// looks for a deck, to pick one from. Plain DOM, no build step. A page hands in how it shows
// a picture, so pictures are fetched with that page's own key.
(function () {
  'use strict';

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  // spec: {name, looks: [{id, name, useWhen, number}], defaultId, preselect, sheet, notes,
  //        failed, picked: {choice, words}, picture(number, alt), changed({choice, words}),
  //        wordsLabel}
  // A radio group of the looks, each with its picture and what it is for, the sheet of them
  // all, what the studio says about how they were rendered, and a box for the person's words.
  // It is one stop for Tab: the arrow keys, Home and End move the choice within it, and Space
  // or Enter picks the look that has the focus. With `preselect`, the brand's default is
  // chosen until the person picks another, and the studio is told so at once.
  function lookPicker(spec) {
    const node = make('div', 'deck-looks');
    const held = { choice: (spec.picked && spec.picked.choice) || '',
      words: (spec.picked && spec.picked.words) || '' };
    const tell = () => { if (spec.changed) spec.changed({ choice: held.choice, words: held.words }); };
    for (const note of spec.notes || []) node.append(make('p', 'quiet deck-looks-note', note));
    if (spec.failed) return node;
    if (spec.sheet && spec.picture) node.append(spec.picture(0, 'Every look on one sheet'));
    const looks = spec.looks || [];
    const known = (id) => looks.some((look) => look.id === id);
    // A choice that is not among these looks is let go, and the studio is told so.
    if (held.choice && !known(held.choice)) {
      held.choice = '';
      tell();
    }
    if (!held.choice && spec.preselect && known(spec.defaultId)) {
      held.choice = spec.defaultId;
      tell();
    }
    const group = make('div', 'deck-looks-choices');
    group.setAttribute('role', 'radiogroup');
    group.setAttribute('aria-label', 'Looks for ' + (spec.name || 'the slide deck'));
    const options = [];
    // Only the chosen look, or the first while none is, can be reached with Tab.
    const rove = () => {
      const stop = options.find((option) => option.dataset.look === held.choice) || options[0];
      for (const option of options) option.tabIndex = option === stop ? 0 : -1;
    };
    const pick = (chosen) => {
      held.choice = chosen;
      for (const option of options) {
        option.setAttribute('aria-checked', String(option.dataset.look === chosen));
      }
      rove();
      tell();
    };
    const KEYS = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    looks.forEach((look, index) => {
      // A choice among a few: one button each, as a radio, with its picture and its use.
      const option = make('button', 'deck-look');
      option.type = 'button';
      option.setAttribute('role', 'radio');
      option.setAttribute('aria-label', look.name);
      option.setAttribute('aria-checked', String(held.choice === look.id));
      option.dataset.look = look.id;
      option.dataset.key = 'look-' + look.id;
      const named = make('span', 'deck-look-name', look.name);
      if (look.id === spec.defaultId) {
        // Said with the look's name, which its label alone would leave out.
        const marked = make('span', 'quiet', ' · the brand’s default');
        marked.id = 'look-default-' + String(spec.name || 'deck').replace(/[^a-z0-9]+/gi, '-');
        option.setAttribute('aria-describedby', marked.id);
        named.append(marked);
      }
      option.append(named);
      if (spec.picture) option.append(spec.picture(look.number, look.name));
      if (look.useWhen) option.append(make('span', 'quiet deck-look-use', look.useWhen));
      option.addEventListener('click', () => pick(look.id));
      option.addEventListener('keydown', (event) => {
        const by = KEYS[event.key];
        const to = event.key === 'Home' ? 0 : event.key === 'End' ? looks.length - 1
          : by ? (index + by + looks.length) % looks.length : -1;
        if (to < 0) return;
        if (event.preventDefault) event.preventDefault();
        // As in any radio group, moving the focus moves the choice with it.
        pick(looks[to].id);
        options[to].focus();
      });
      options.push(option);
      group.append(option);
    });
    rove();
    node.append(group);
    const said = spec.wordsLabel || 'Your words, kept with your choice (optional)';
    const words = make('textarea', 'input deck-looks-words');
    words.id = 'look-words-' + String(spec.name || 'deck').replace(/[^a-z0-9]+/gi, '-');
    words.rows = 2;
    words.maxLength = 2000;
    words.value = held.words;
    words.addEventListener('input', () => { held.words = words.value; tell(); });
    const label = make('label', 'field-label', said);
    label.htmlFor = words.id;
    node.append(label, words);
    return node;
  }

  // spec: {title, load: () => Promise of the frame's address, note}
  // The deck's wireframe draft, as the slides tool draws it: what each slide says and how its
  // points relate, before any design. It is framed from the studio's own server, opened with a
  // ticket and sandboxed there: it can run no script and reach nothing of the page.
  function storyboard(spec) {
    const node = make('div', 'deck-storyboard');
    node.append(make('p', 'quiet', spec.note || 'A wireframe draft of the deck: what each '
      + 'slide says and how its points relate, drawn plainly. It is not the design.'));
    const holder = make('div', 'deck-storyboard-holder');
    const said = make('p', 'quiet', 'Drawing the draft…');
    said.setAttribute('role', 'status');
    holder.append(said);
    node.append(holder);
    Promise.resolve().then(spec.load).then((address) => {
      const frame = make('iframe', 'deck-storyboard-frame');
      frame.setAttribute('sandbox', '');
      frame.title = spec.title || 'Wireframe draft of the deck';
      frame.src = address;
      holder.replaceChildren(frame);
    }).catch((failure) => {
      said.textContent = 'The draft could not be drawn: ' + ((failure && failure.message) || failure);
    });
    return node;
  }

  window.DeckPanels = { lookPicker, storyboard };
}());
