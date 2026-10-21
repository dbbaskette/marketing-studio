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

  // spec: {name, looks: [{id, name, useWhen, number}], defaultId, sheet, notes, failed,
  //        picked: {choice, words}, picture(number, alt), changed({choice, words}),
  //        wordsLabel}
  // A radio group of the looks, each with its picture and what it is for, the sheet of them
  // all, what the studio says about how they were rendered, and a box for the person's words.
  function lookPicker(spec) {
    const node = make('div', 'deck-looks');
    const held = { choice: (spec.picked && spec.picked.choice) || '',
      words: (spec.picked && spec.picked.words) || '' };
    const tell = () => { if (spec.changed) spec.changed({ choice: held.choice, words: held.words }); };
    for (const note of spec.notes || []) node.append(make('p', 'quiet deck-looks-note', note));
    if (spec.failed) return node;
    if (spec.sheet && spec.picture) node.append(spec.picture(0, 'Every look on one sheet'));
    const group = make('div', 'deck-looks-choices');
    group.setAttribute('role', 'radiogroup');
    group.setAttribute('aria-label', 'Looks for ' + (spec.name || 'the slide deck'));
    const options = [];
    const pick = (chosen) => {
      held.choice = chosen;
      for (const option of options) {
        option.setAttribute('aria-checked', String(option.dataset.look === chosen));
      }
      tell();
    };
    (spec.looks || []).forEach((look) => {
      // A choice among a few: one button each, as a radio, with its picture and its use.
      const option = make('button', 'deck-look');
      option.type = 'button';
      option.setAttribute('role', 'radio');
      option.setAttribute('aria-label', look.name);
      option.setAttribute('aria-checked', String(held.choice === look.id));
      option.dataset.look = look.id;
      option.dataset.key = 'look-' + look.id;
      const named = make('span', 'deck-look-name', look.name);
      if (look.id === spec.defaultId) named.append(make('span', 'quiet', ' · the brand’s default'));
      option.append(named);
      if (spec.picture) option.append(spec.picture(look.number, look.name));
      if (look.useWhen) option.append(make('span', 'quiet deck-look-use', look.useWhen));
      option.addEventListener('click', () => pick(look.id));
      options.push(option);
      group.append(option);
    });
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

  window.DeckPanels = { lookPicker };
}());
