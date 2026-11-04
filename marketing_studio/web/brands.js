'use strict';
// Marketing Studio's Brands screen: brand packs and icon libraries in the storage's brands
// folder, and the working copies that make and update them. It is a front for Harness
// Brand's pack commands and the person's assistant: every change happens on a working copy,
// and storage changes only when the person saves. Loaded by app.js, which hands it the page's
// own helpers (open).
(() => {
  const $ = selector => document.querySelector(selector);
  let ctx = null, key = null, timer = null, pictures = [], listed = null, pending = null;
  const words = {brand: 'brand pack', library: 'icon library'};

  function el(tag, text, className, attributes = {}) {
    const node = ctx.element(tag, text, className);
    for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
    return node;
  }
  function button(label, kind, action) {
    const node = el('button', label, kind ? `button ${kind}` : 'button', {type: 'button'});
    node.addEventListener('click', async () => {
      if (ctx.isBusy(node)) return;
      const done = ctx.busy(node, `${label}…`);
      try { await action(node); } catch (error) { ctx.problem(error); } finally { done(); }
    });
    return node;
  }
  function card(title, ...parts) {
    const node = el('section', '', 'card');
    if (title) node.append(el('h3', title, 'card-title'));
    node.append(...parts.filter(Boolean));
    return node;
  }
  function bar(...buttons) { const node = el('div', '', 'bar'); node.append(...buttons.filter(Boolean)); return node; }
  function forget() { for (const url of pictures) URL.revokeObjectURL(url); pictures = []; }
  function picture(path, alt, className) {
    const image = el('img', '', className, {alt, loading: 'lazy', decoding: 'async'});
    ctx.file({key, path}).then(url => { pictures.push(url); image.src = url; })
      .catch(() => image.replaceWith(el('p', `${alt}: the picture could not be shown.`, 'field-hint quiet')));
    return image;
  }
  function body() { return $('#brands-body'); }
  function toolbar(list) {
    $('#brands-back').hidden = !key;
    $('#brands-new').hidden = Boolean(key) || !list;
    $('#brands-new-library').hidden = Boolean(key) || !list;
  }
  function size(bytes) {
    return bytes >= 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : bytes >= 1e3 ? `${Math.round(bytes / 1e3)} KB` : `${bytes} bytes`;
  }

  // --- the list ------------------------------------------------------------------------
  async function showList() {
    key = null; clearTimeout(timer); forget();
    toolbar(null);
    body().replaceChildren(el('p', 'Looking for your brand packs…', 'quiet'));
    listed = await ctx.api('brand-list', {});
    if (key || !ctx.here()) return;
    const parts = [el('div', '', 'intro')];
    parts[0].append(el('h2', 'Brands', 'large-title'),
      el('p', 'Brand packs and icon libraries the studios use. Making or updating one runs Harness Brand and your assistant on a working copy on this computer; storage changes only when you save.', 'lede'));
    if (listed.unavailable) {
      parts.push(el('p', listed.unavailable, 'paper callout'));
      body().replaceChildren(...parts);
      return;
    }
    toolbar(listed);
    if (listed.work.length) {
      const list = el('ul', '', 'brand-rows');
      for (const work of listed.work) {
        const row = el('li', '', 'brand-row');
        const text = el('div', '', 'brand-row-text');
        text.append(el('span', work.name, 'row-title'),
          el('span', `${work.update ? 'Updating the' : 'New'} ${words[work.kind]} ${work.id}${work.task === 'running' ? ', working now' : ''}`, 'quiet'));
        row.append(text, bar(button('Continue', '', () => openWork(work.key)),
          button('Discard', 'button-quiet', () => discard(work))));
        list.append(row);
      }
      parts.push(card('In progress', list));
    }
    parts.push(card('Brand packs', packTable(listed.packs)), card('Icon libraries', libraryTable(listed.libraries)));
    const unshared = [...listed.packs, ...listed.libraries].filter(item => item.unshared).length;
    if (listed.team && unshared) {
      parts.push(card('Not pushed yet', el('p', `${unshared === 1 ? 'One saved brand or library is' : `${unshared} saved brands and libraries are`} committed on this computer and not in the team repository yet.`),
        pushOffer(null)));
    }
    parts.push(el('p', `Kept in ${listed.where}. ${listed.skill.name} ${listed.skill.version || ''} reads them.`, 'quiet'));
    body().replaceChildren(...parts);
  }
  function checkCell(check) {
    const cell = el('td');
    cell.append(ctx.stateLine(check.ok ? 'done' : 'review', check.ok ? 'Passes pack check' : 'Does not pass'));
    if (!check.ok && check.problems.length) cell.append(el('p', check.problems[0], 'field-hint quiet'));
    return cell;
  }
  function table(caption, heads, rows, empty) {
    if (!rows.length) return el('p', empty, 'field-hint quiet');
    const node = el('table', '', 'table');
    node.append(el('caption', caption, 'offscreen'));
    const head = el('thead'), line = el('tr');
    for (const name of heads) line.append(el('th', name, '', {scope: 'col'}));
    head.append(line);
    const rowsNode = el('tbody');
    rowsNode.append(...rows);
    node.append(head, rowsNode);
    return node;
  }
  function packTable(packs) {
    return table('Brand packs', ['Brand', 'Variants', 'Slides', 'Check', 'Action'], packs.map(pack => {
      const row = el('tr');
      const name = el('th', '', '', {scope: 'row'});
      name.append(el('span', pack.name, 'row-title'), el('span', ` ${pack.id}`, 'quiet'));
      const action = el('td');
      action.append(button('Update', '', () => start({kind: 'brand', id: pack.id, update: true})));
      row.append(name, el('td', pack.variants.join(', ') || 'None'), el('td', pack.slides ? 'Yes' : 'Writing only'), checkCell(pack.check), action);
      return row;
    }), 'No brand packs yet. New brand makes one from its sources.');
  }
  function libraryTable(libraries) {
    return table('Icon libraries', ['Library', 'Kind', 'Icons', 'Used by', 'Check', 'Action'], libraries.map(library => {
      const row = el('tr');
      const name = el('th', '', '', {scope: 'row'});
      name.append(el('span', library.name, 'row-title'), el('span', ` ${library.id}`, 'quiet'));
      const action = el('td');
      action.append(button('Update', '', () => start({kind: 'library', id: library.id, update: true})));
      row.append(name, el('td', library.kind === 'picture' ? 'Picture' : library.kind === 'glyph' ? 'Glyph' : 'Unknown'),
        el('td', library.count == null ? '—' : String(library.count)), el('td', library.usedBy.join(', ') || 'No brand yet'),
        checkCell(library.check), action);
      return row;
    }), 'No icon libraries yet. A brand can use any library kept here.');
  }
  async function discard(work) {
    if (!confirm(`Discard the working copy of ${work.name}? Its sources and proposals go; storage stays as it is.`)) return;
    await ctx.api('brand-discard', {key: work.key});
    ctx.inform(`Discarded the working copy of ${work.name}.`);
    await showList();
  }
  async function start(sent) {
    const work = await ctx.api('brand-start', sent);
    await openWork(work.key, work);
  }

  // --- New, in a sheet -----------------------------------------------------------------
  let sheetKind = 'brand';
  function openSheet(kind, opener) {
    sheetKind = kind;
    const sheet = $('#brands-sheet');
    $('#brands-sheet-title').textContent = kind === 'brand' ? 'New brand' : 'New icon library';
    $('#brands-new-kind').hidden = kind !== 'library';
    $('#brands-sheet-form').reset();
    sheet.returnTo = opener;
    sheet.showModal();
    $('#brands-new-name').focus();
  }
  function slug(text) { return text.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 63); }

  // --- one working copy ----------------------------------------------------------------
  async function openWork(which, given) {
    key = which; forget();
    const work = given || await ctx.api('brand-work', {key});
    if (key !== which || !ctx.here()) return;
    toolbar(listed);
    render(work);
  }
  // The step the person is on: Sources, Extract, Review (a brand only), then Save.
  function step(work) {
    if (!work.extracted && !(work.update && work.kind === 'brand')) return work.sources.length ? 1 : 0;
    if (work.kind === 'library') return 2;
    return work.ready ? 2 : 3;
  }
  function render(work) {
    clearTimeout(timer);
    const scroll = window.scrollY;
    const parts = [];
    const head = el('div', '', 'intro');
    head.append(el('h2', work.name, 'large-title'),
      el('p', `${work.update ? 'Updating the' : 'A new'} ${words[work.kind]}, ${work.id}${work.kind === 'library' ? `, ${work.libraryKind}` : ''}. Changes stay in this working copy until you save.`, 'lede'));
    parts.push(head);
    const names = work.kind === 'library' ? ['1. Sources', '2. Extract', '3. Save'] : ['1. Sources', '2. Extract', '3. Review', '4. Save'];
    const steps = el('ol', '', 'workflow-steps', {'aria-label': 'Steps'});
    const at = step(work);
    names.forEach((name, index) => {
      const item = el('li', name, 'workflow-step');
      if (index === at) item.setAttribute('aria-current', 'step');
      steps.append(item);
    });
    parts.push(steps);
    if (work.task) parts.push(taskCard(work));
    parts.push(sourcesCard(work), extractCard(work));
    if (work.kind === 'brand' && (work.extracted || work.update)) parts.push(...reviewCards(work));
    parts.push(saveCard(work));
    body().replaceChildren(...parts);
    window.scrollTo(0, scroll);
    if (work.task?.state === 'running') timer = setTimeout(() => refresh(work.key), 1500);
  }
  async function refresh(which) {
    if (key !== which || !ctx.here()) return;
    try { render(await ctx.api('brand-work', {key: which})); } catch (error) { ctx.problem(error); }
  }
  function taskCard(work) {
    const task = work.task;
    const what = task.kind === 'extract' ? 'Extract' : task.part ? 'The assistant, for one part' : 'The assistant';
    const says = {running: 'Working', done: 'Finished', failed: 'Did not finish', stopped: 'Stopped'}[task.state];
    const node = card(null);
    node.className = 'card brand-task';
    const top = el('div', '', 'part-head');
    top.append(el('h3', what, 'card-title'), ctx.stateLine(task.state === 'done' ? 'done' : task.state === 'running' ? 'current' : 'review', says));
    node.append(top);
    const last = task.lines[task.lines.length - 1];
    if (last) node.append(el('p', `${task.state === 'running' ? 'Now: ' : ''}${last}`, 'activity-now'));
    if (task.detail) node.append(el('p', task.detail, task.state === 'failed' ? 'paper callout' : 'quiet'));
    if (task.lines.length > 1) {
      const more = el('details', '', 'brand-lines');
      more.append(el('summary', 'Show activity'));
      const list = el('ol', '', 'quiet');
      for (const line of task.lines) list.append(el('li', line));
      more.append(list);
      node.append(more);
    }
    if (task.state === 'running') node.append(bar(button('Stop', 'button-quiet', async () => render(await ctx.api('brand-stop', {key: work.key})))));
    return node;
  }
  function sourcesCard(work) {
    const node = card('Sources');
    node.append(el('p', work.kind === 'library'
      ? 'The icons, as received: SVG files, an icons.json, or a ZIP archive of them.'
      : 'What the pack is made from, as received: the PowerPoint template for each variant, the design-system export, brand guides and logos.', 'quiet'));
    if (work.sources.length) {
      const list = el('ul', '', 'brand-files');
      for (const source of work.sources) {
        const item = el('li', '', 'brand-file');
        item.append(el('span', source.name, 'row-title'), el('span', size(source.size), 'quiet'));
        list.append(item);
      }
      node.append(list);
    } else node.append(el('p', 'No sources yet.', 'field-hint quiet'));
    for (const name of work.clashes) {
      const ask = el('div', '', 'paper callout', {role: 'group', 'aria-label': `Which ${name} to keep`});
      ask.append(el('p', `${name} is already a source. Which do you keep?`),
        bar(button('The one there', '', () => keep(work, name, 'there')),
          button('The new one', '', () => keep(work, name, 'new')),
          button('Both', '', () => keep(work, name, 'both'))));
      node.append(ask);
    }
    const field = el('div', '', 'field');
    const id = `brand-files-${work.key}`;
    const input = el('input', '', 'input', {type: 'file', id, multiple: '', ...(work.kind === 'library' ? {accept: '.svg,.json,.zip'} : {})});
    field.append(el('label', 'Add files', 'field-label', {for: id}), input,
      el('p', 'Each file is copied into this working copy, up to 40 MB each. A file whose name is taken waits until you say which to keep.', 'field-hint quiet'));
    node.append(field, bar(button('Add to sources', '', async () => {
      const files = [...input.files];
      if (!files.length) { input.focus(); throw new Error('Choose the files to add first.'); }
      let latest = null, waiting = 0;
      for (const chosen of files) {
        const content = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
          reader.onerror = () => reject(new Error(`${chosen.name} could not be read.`));
          reader.readAsDataURL(chosen);
        });
        const answer = await ctx.api('brand-source', {key: work.key, name: chosen.name, content});
        latest = answer.work; if (answer.clash) waiting++;
      }
      ctx.inform(`Added ${files.length - waiting} of ${files.length} file${files.length === 1 ? '' : 's'}${waiting ? `; ${waiting} wait${waiting === 1 ? 's' : ''} for your choice` : ''}.`);
      render(latest);
    })));
    return node;
  }
  async function keep(work, name, which) {
    const answer = await ctx.api('brand-keep', {key: work.key, name, which});
    ctx.inform(which === 'there' ? `Kept the ${name} that was there.` : which === 'new' ? `Kept the new ${name}.` : `Kept both; the new one is ${answer.kept}.`);
    render(answer.work);
  }

  // --- Extract -------------------------------------------------------------------------
  function extractCard(work) {
    const node = card('Extract');
    const running = work.task?.state === 'running';
    if (work.kind === 'library') {
      node.append(el('p', 'Harness Brand’s pack icons makes the library from the sources and draws a contact sheet. An icon that cannot be used is left out and named.', 'quiet'));
      node.append(bar(button(work.extracted ? 'Extract again' : 'Extract', work.extracted ? '' : 'button-filled', async () => {
        if (running) return; render(await ctx.api('brand-extract', {key: work.key}));
      })));
      if (work.extracted) node.append(...libraryResults(work));
      return node;
    }
    const choices = work.choices;
    node.append(el('p', 'Harness Brand reads the tokens from the design-system export, measures each template, draws a preview of each layout and, for a new pack, drafts the rest for review.', 'quiet'));
    const grid = el('div', '', 'field-grid');
    const exportId = `brand-export-${work.key}`;
    const exportField = el('div', '', 'field');
    const exportSelect = el('select', '', 'input', {id: exportId});
    if (work.update) exportSelect.append(new Option('Keep the tokens there are', ''));
    for (const name of choices.exports) exportSelect.append(new Option(name, name));
    if (!choices.exports.length && !work.update) exportSelect.append(new Option('Add a design-system export first', ''));
    if (work.extracted?.tokens && choices.exports.includes(work.extracted.tokens)) exportSelect.value = work.extracted.tokens;
    exportField.append(el('label', 'Design-system export', 'field-label', {for: exportId}), exportSelect);
    grid.append(exportField);
    const variants = [];
    choices.templates.forEach((template, index) => {
      const field = el('div', '', 'field');
      const id = `brand-variant-${work.key}-${index}`;
      const input = el('input', '', 'input input-typed', {id, value: template.variant, maxlength: '31', autocomplete: 'off', spellcheck: 'false'});
      const use = el('input', '', '', {type: 'checkbox', checked: ''});
      const check = el('label', '', 'check');
      check.append(use, el('span', `Measure ${template.source}`));
      field.append(check, el('label', `Variant for ${template.source}`, 'field-label', {for: id}), input);
      variants.push({source: template.source, input, use});
      grid.append(field);
    });
    node.append(grid);
    let libraries = [];
    if (!work.update && choices.libraries.length) {
      const set = el('fieldset', '', 'research-choices');
      set.append(el('legend', 'Icon libraries the brand uses', 'field-label'));
      libraries = choices.libraries.map(id => {
        const box = el('input', '', '', {type: 'checkbox', value: id});
        const label = el('label', '', 'check'); label.append(box, el('span', id)); set.append(label);
        return box;
      });
      node.append(set);
    }
    if (!choices.templates.length) node.append(el('p', 'No PowerPoint template among the sources: the pack will be for writing only, without slides.', 'field-hint quiet'));
    node.append(bar(button(work.extracted ? 'Extract again' : 'Extract', work.extracted ? '' : 'button-filled', async () => {
      if (running) return;
      const sent = {key: work.key, tokens: exportSelect.value || null,
                    templates: variants.filter(item => item.use.checked).map(item => ({source: item.source, variant: item.input.value.trim()})),
                    icons: libraries.filter(box => box.checked).map(box => box.value)};
      render(await ctx.api('brand-extract', sent));
    })));
    if (work.extracted || work.tokens) node.append(...brandResults(work));
    return node;
  }
  function libraryResults(work) {
    const shown = [];
    const found = work.extracted;
    shown.push(el('p', `${found.icons} ${found.kind} icon${found.icons === 1 ? '' : 's'} in the library.`, 'row-title'));
    if (found.skipped.length) {
      const more = el('details', '', 'brand-lines');
      more.append(el('summary', `Left out: ${found.skipped.length}`));
      const list = el('ul');
      for (const left of found.skipped) list.append(el('li', `${left.source}: ${left.file}: ${left.reason}`));
      more.append(list);
      shown.push(more);
    }
    if (work.library?.sheet) {
      const figure = el('figure', '', 'brand-sheet');
      figure.append(picture(work.library.sheet, 'Contact sheet of the icons', 'brand-sheet-image'), el('figcaption', 'Contact sheet', 'field-hint quiet'));
      shown.push(figure);
    }
    return shown;
  }
  function swatch(value, label) {
    const node = el('span', '', 'brand-swatch', {'aria-hidden': 'true'});
    if (value) node.style.background = value; else node.dataset.missing = 'true';
    node.title = label;
    return node;
  }
  function brandResults(work) {
    const shown = [];
    for (const [variant, problemText] of Object.entries(work.extracted?.previews || {})) {
      if (problemText) shown.push(el('p', `No previews for ${variant}. ${problemText}`, 'paper callout'));
    }
    if (work.tokens) {
      const colours = el('ul', '', 'brand-colours', {'aria-label': 'Colours, light and dark'});
      for (const colour of work.tokens.colors) {
        const item = el('li', '', 'brand-colour');
        const pair = el('span', '', 'brand-pair');
        pair.append(swatch(colour.light, `${colour.name}, light: ${colour.light || 'none'}`), swatch(colour.dark || colour.light, `${colour.name}, dark: ${colour.dark || colour.light || 'none'}`));
        const text = el('span', '', 'brand-colour-text');
        text.append(el('span', colour.name, 'row-title'),
          el('span', `Light ${colour.light || '—'} · Dark ${colour.dark || 'the same'}`, 'quiet'));
        if (colour.usage) text.append(el('span', colour.usage, 'field-hint quiet'));
        item.append(pair, text);
        colours.append(item);
      }
      shown.push(el('h4', 'Colours', 'sheet-part'), colours);
      if (work.tokens.styles.length) {
        shown.push(el('h4', 'Type styles', 'sheet-part'), table('Type styles', ['Style', 'Group', 'Size', 'Line height', 'Weight'],
          work.tokens.styles.map(style => {
            const row = el('tr');
            row.append(el('th', style.name, '', {scope: 'row'}), el('td', style.group || '—'), el('td', style.fontSize || '—'),
              el('td', style.lineHeight || '—'), el('td', style.fontWeight == null ? '—' : String(style.fontWeight)));
            return row;
          }), ''));
      }
    }
    for (const [variant, layouts] of Object.entries(work.layouts || {})) {
      const grid = el('ul', '', 'brand-layouts', {'aria-label': `Layouts, ${variant}`});
      for (const layout of layouts) {
        const item = el('li', '', 'brand-layout');
        if (layout.preview) item.append(picture(layout.preview, `${layout.name} preview`, 'brand-preview'));
        else item.append(el('span', 'No preview', 'brand-preview brand-preview-none quiet'));
        item.append(el('span', layout.name, 'row-title'),
          el('span', `${layout.id}${layout.relationship ? ` · ${layout.relationship}` : ''}${layout.used ? '' : ' · no example slide'}`, 'field-hint quiet'));
        grid.append(item);
      }
      shown.push(el('h4', `Layouts, ${variant}`, 'sheet-part'), grid);
    }
    if (work.extracted?.draft?.length) {
      const list = el('ul', '', 'quiet');
      for (const line of work.extracted.draft) list.append(el('li', line));
      shown.push(el('h4', 'What the draft leaves to review', 'sheet-part'), list);
    }
    return shown;
  }

  // --- Review --------------------------------------------------------------------------
  function reviewCards(work) {
    const running = work.task?.state === 'running';
    const cards = [];
    const intro = card('Review');
    const agent = ctx.agent();
    intro.append(el('p', work.update
      ? `Only the parts that differ from the current pack wait for you. ${agent} can propose new versions from the sources; you accept, edit or send back each part.`
      : `${agent} proposes each part from the sources, following Harness Brand’s guide to building a pack. You accept, edit or send back each part. It may write only these judgement files.`, 'quiet'));
    intro.append(bar(button(`Ask ${agent} for every part`, work.parts.some(p => p.by === 'assistant') ? '' : 'button-filled', async () => {
      if (running) return; render(await ctx.api('brand-interpret', {key: work.key}));
    })));
    if (work.notes?.length) {
      const notes = el('div', '', 'paper callout');
      notes.append(el('p', 'Where the sources disagree', 'row-title'));
      const list = el('ul'); for (const note of work.notes) list.append(el('li', note)); notes.append(list);
      intro.append(notes);
    }
    cards.push(intro);
    for (const part of work.parts) cards.push(partCard(work, part, running));
    return cards;
  }
  function partCard(work, part, running) {
    const node = card(null);
    node.className = 'card brand-part';
    const top = el('div', '', 'part-head');
    const label = {accepted: 'Accepted', unchanged: 'Unchanged', review: 'Waiting for you'}[part.state];
    top.append(el('h3', part.title, 'card-title'), ctx.stateLine(part.state === 'review' ? 'review' : 'done', label));
    node.append(top, el('p', `${part.file}, ${part.by === 'you' ? 'as you edited it' : part.by === 'assistant' ? `as ${ctx.agent()} proposed it` : part.by === 'draft' ? 'as pack scaffold drafted it' : 'as the current pack has it'}.`, 'field-hint quiet'));
    if (part.state === 'unchanged') {
      const more = el('details', '', 'brand-lines');
      more.append(el('summary', 'Show it'), el('pre', part.content, 'brand-code'));
      node.append(more);
      return node;
    }
    if (part.id === 'roles' && work.roles) {
      for (const [variant, roles] of Object.entries(work.roles)) {
        const list = el('ul', '', 'brand-colours', {'aria-label': `Colour roles, ${variant}`});
        for (const role of roles) {
          const item = el('li', '', 'brand-colour');
          const text = el('span', '', 'brand-colour-text');
          text.append(el('span', role.role, 'row-title'), el('span', `${role.color}${role.value ? `, ${role.value}` : ', not in tokens.json'}`, 'quiet'));
          item.append(swatch(role.value, `${role.role}: ${role.value || 'missing'}`), text);
          list.append(item);
        }
        node.append(el('h4', `Colour roles, ${variant}`, 'sheet-part'), list);
      }
    }
    if (part.quotes.length) {
      const more = el('details', '', 'brand-lines');
      more.append(el('summary', `Where each rule comes from (${part.quotes.length})`));
      const list = el('ul');
      for (const quote of part.quotes) list.append(el('li', `${quote.rule || ''} — ${quote.source || 'no source given'}`));
      more.append(list);
      node.append(more);
    }
    if (part.current !== null && part.current !== undefined) {
      const before = el('details', '', 'brand-lines');
      before.append(el('summary', 'The current pack’s version'), el('pre', part.current, 'brand-code'));
      node.append(before);
    }
    const id = `brand-part-${work.key}-${part.id}`;
    const field = el('div', '', 'field');
    const text = el('textarea', '', 'input brand-text', {id, rows: String(Math.min(24, Math.max(8, part.content.split('\n').length))), spellcheck: part.id === 'guide' ? 'true' : 'false'});
    text.value = part.content;
    field.append(el('label', part.id === 'guide' ? 'guide.md' : `${part.file}${part.id === 'layouts' ? ', the fields that say what each layout is for' : ''}`, 'field-label', {for: id}), text);
    node.append(field);
    const noteId = `${id}-note`;
    const back = el('details', '', 'brand-lines');
    const note = el('textarea', '', 'input', {id: noteId, rows: '3', maxlength: '4000'});
    back.append(el('summary', 'Send back with a note'));
    const noteField = el('div', '', 'field');
    noteField.append(el('label', 'What should change', 'field-label', {for: noteId}), note);
    back.append(noteField, bar(button('Send back', '', async () => {
      if (running) return;
      if (!note.value.trim()) { note.focus(); throw new Error('Say in the note what should change.'); }
      render(await ctx.api('brand-interpret', {key: work.key, part: part.id, note: note.value.trim()}));
    })));
    node.append(bar(
      part.state === 'review' ? button('Accept', 'button-filled', async () => render(await ctx.api('brand-part', {key: work.key, part: part.id, action: 'accept'}))) : null,
      button('Save my edit', '', async () => {
        render(await ctx.api('brand-part', {key: work.key, part: part.id, action: 'edit', content: text.value}));
        ctx.inform(`Kept your edit of ${part.file}.`);
      })), back);
    return node;
  }

  // --- Save and push -------------------------------------------------------------------
  function saveCard(work) {
    const node = card('Save');
    node.append(el('p', work.kind === 'brand'
      ? 'Save runs pack check, seals the pack, puts the pack and its sources in storage and commits them together.'
      : 'Save checks the library, puts it and its sources in storage and commits them together.', 'quiet'));
    if (work.checked && !work.checked.ok) {
      const said = el('div', '', 'paper callout');
      said.append(el('p', 'pack check says:', 'row-title'));
      const list = el('ul'); for (const line of work.checked.problems) list.append(el('li', line)); said.append(list);
      node.append(said);
    }
    if (work.ready) node.append(el('p', work.ready, 'field-hint'));
    node.append(bar(work.ready ? null : button('Save', 'button-filled', async () => {
      let saved;
      try { saved = await ctx.api('brand-save', {key: work.key}); }
      catch (error) {
        if (error.answer?.problems) { try { render(await ctx.api('brand-work', {key: work.key})); } catch (ignored) {} }
        throw error;
      }
      ctx.inform(saved.committed ? `Saved: ${saved.message}.` : `Saved ${saved.name}; nothing had changed, so there was nothing to commit.`);
      pending = saved.push || null;
      await showList();
      if (pending && pending.commits) body().prepend(card('Push to the team repository?', el('p', pushWords(pending)), pushOffer(pending)));
    }), button('Discard', 'button-quiet', () => discard(work))));
    return node;
  }
  function pushWords(push) {
    const extra = push.commits - (push.brands || 0);
    return `${push.address} (${push.branch}) does not have this yet. Pushing sends ${push.commits} commit${push.commits === 1 ? '' : 's'}${extra > 0 ? `, ${extra} of them a studio’s own work not shared yet` : ''}. Nothing is pushed until you say so.`;
  }
  function pushOffer(push) {
    return bar(button('Push', 'button-filled', async () => {
      const done = await ctx.api('brand-push', {confirm: true});
      ctx.inform(`Pushed to ${done.address} (${done.branch}).`);
      pending = null;
      await showList();
    }), push ? button('Not now', 'button-quiet', async () => { pending = null; await showList(); ctx.inform('The save is committed on this computer. Push it from Brands when you are ready.'); }) : null);
  }

  // --- wiring --------------------------------------------------------------------------
  let wired = false;
  function wire() {
    if (wired) return; wired = true;
    $('#brands-back').addEventListener('click', () => showList().catch(error => ctx.problem(error)));
    $('#brands-new').addEventListener('click', () => openSheet('brand', $('#brands-new')));
    $('#brands-new-library').addEventListener('click', () => openSheet('library', $('#brands-new-library')));
    const sheet = $('#brands-sheet'), name = $('#brands-new-name'), id = $('#brands-new-id');
    let typed = false;
    name.addEventListener('input', () => { if (!typed) id.value = slug(name.value); });
    id.addEventListener('input', () => { typed = Boolean(id.value); });
    for (const close of ['#brands-sheet-close', '#brands-sheet-cancel']) $(close).addEventListener('click', () => sheet.close());
    sheet.addEventListener('close', () => { typed = false; const back = sheet.returnTo; if (back && !back.hidden) back.focus(); });
    $('#brands-sheet-form').addEventListener('submit', async event => {
      event.preventDefault();
      const submit = $('#brands-sheet-start');
      if (ctx.isBusy(submit)) return;
      const done = ctx.busy(submit, 'Starting…');
      try {
        const kind = sheetKind === 'library' ? 'library' : 'brand';
        const libraryKind = kind === 'library' ? $('#brands-sheet-form').elements.kind.value : null;
        const work = await ctx.api('brand-start', {kind, id: id.value.trim(), name: name.value.trim(), libraryKind});
        sheet.close();
        await openWork(work.key, work);
      } catch (error) { ctx.problem(error); }
      finally { done(); }
    });
  }

  window.StudioBrands = {
    open(context) {
      ctx = context; wire();
      const again = key ? openWork(key) : showList();
      again.catch(error => { ctx.problem(error); if (key) { key = null; showList().catch(() => {}); } });
    },
    leave() { clearTimeout(timer); },
  };
})();
