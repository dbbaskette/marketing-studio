# Harness Brand, Plan 2: the pack format and the extraction commands

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The written brand pack format (`docs/brand-pack-format.md`) and the three commands that take the exact parts of a pack from its sources: `pack tokens` (colours, type and spacing from a Claude Design export), `pack measure` (a PowerPoint template's master, layouts, placeholders, artwork, theme and slides) and `pack previews` (a picture of each layout).

**Architecture:** Built on Plan 1's ZIP and XML readers, in `dbbaskette/harness-brand-skill`. A small OOXML package reader (`scripts/lib/ooxml.mjs`) resolves parts and relationships, matching names by local name. `scripts/lib/pack/` holds one module for each command's work. `scripts/pack-brand.mjs` holds the three commands, which `scripts/pack.mjs` dispatches to. Pack files are written as readable JSON (`scripts/lib/readable-json.mjs`) so people and assistants can read them. Spec: `docs/superpowers/specs/2026-11-03-harness-brand-design.md` in marketing-studio, sections 2 and 3.

**Tech Stack:** Node.js 20 or newer, no npm packages; `npm test` runs `node --test`. `pack previews` runs LibreOffice (`soffice`) and Poppler (`pdftoppm`, `pdfinfo`); the tests stand in for them.

**Dry run:** every file in this plan was written and run before the plan was, on 3 November 2026: all 142 tests passed, and the commands ran on the three Claude Design exports and the four corporate templates (Task 9's numbers come from that run).

---

## Roadmap: the plans for Harness Brand

Plan 2 was split in two when it was written: the format and the exact extraction here, and
the checking and authoring next. The roadmap is now:

1. **Foundations and icon libraries** (done, merged as dbbaskette/harness-brand-skill#3).
2. **The pack format and the extraction commands** (this plan).
3. **Checking and authoring packs:** `pack scaffold`, `pack check` for packs, `pack seal`,
   `references/building-a-pack.md` (the guide for Claude or Codex), and the Example Co pack.
4. **The three packs:** Tanzu Division, VMware by Broadcom and Broadcom built from their
   sources and reviewed by the person; placed with `vmware-functional` in `brands/` of
   tanzu-marketing-hub after the person's yes.
5. **The worker:** `version`, `brands`, `contract`, `layouts`, `icons` (with the native icon
   deck Harness Slides places icons from), `presentation`, `doctor`, `guidance`, `look`,
   `restyle`; the installers; release packaging; apply-brand and the design-system zips
   removed; the README rewritten.
6. **Marketing Studio, data folder.**
7. **Marketing Studio, Brands section.**
8. **Release 1.0.0.**

## What the pack must hold, and why

Research before this plan (3 November 2026) read what Harness Slides accepts in a brand
contract (`~/Projects/harness-slides-skill/scripts/lib/brand-contract.mjs`), what Tanzu Brand
exports today and from which files, and what Marketing Studio's studios read. The format in
Task 8 holds all of it in a pack:

- Colour roles: Harness Slides requires `canvasPrimary`, `canvasSecondary`, `inkDeep`,
  `headingPrimary` and `accentAqua`, as `#rrggbb`. The Infographic Studio also requires
  `inkPrimary`, which only Tanzu's contract has today.
- Slides: canvas, title and content boxes, the seven type styles (`title`, `body`,
  `bodyReference`, `label`, `caption`, `metric`, `quote`), chart series roles, table header
  roles, icon size and colour, and the native template with its master and content layout.
- Deck directions, the audit's limits, the brand's naming rules, and its logos.

The template measuring ports Tanzu Brand's `tools/extract-presentation-template.py`, and does
better where that was fragile:
- It chooses the master the visible slides use. Tanzu's template has three masters, and only
  the second is used.
- It resolves a placeholder's frame and text style through its master.
- It keeps rotation and flips.
- It takes a system colour by its last value.
- It numbers layouts in the chosen master only.

## Where this plan's work happens

In `dbbaskette/harness-brand-skill`, on a branch from `main` (which has Plan 1). A session
running this plan works in a clone it can write to and hands the branch back as Plan 1 did.
Wherever a task says `~/Projects/harness-brand-skill`, use that clone. Nothing is pushed in
this plan. The design-system zips in the repository and the templates in
`~/Projects/tanzu-brand/assets/presentations/` are read, never changed.

## File structure

| File | Responsibility |
|---|---|
| `scripts/lib/readable-json.mjs` | JSON for pack files: one entry to a line, with short values and flat objects kept on one line |
| `scripts/lib/ooxml.mjs` | a PowerPoint package: parts, XML and relationships, with names matched by local name |
| `scripts/lib/pack/tokens.mjs` | a Claude Design export's tokens as `tokens.json` |
| `scripts/lib/pack/measure.mjs` | a template measured for `layouts.json`, and a new measure merged with what was added before |
| `scripts/lib/pack/previews.mjs` | layout previews drawn with LibreOffice and Poppler, or a stand-in |
| `scripts/pack-brand.mjs` | `pack tokens`, `pack measure`, `pack previews` |
| `scripts/pack.mjs` | (changed) dispatches the three commands and lists them |
| `docs/brand-pack-format.md` | the pack format, for people and other tools |
| `tests/fixtures/template.mjs` | a small template for tests, holding each case the measuring must handle |
| `tests/*.test.mjs` | one test file per module, plus the commands and the format document |

---

### Task 1: Branch

- [ ] **Step 1: Make the branch**

```bash
cd ~/Projects/harness-brand-skill
git switch main && git pull --ff-only && git switch -c harness-brand-pack-extraction
npm test
```

Expected: `Switched to a new branch 'harness-brand-pack-extraction'`, then `# pass 109`, `# fail 0`.

---

### Task 2: Readable JSON

**Files:**
- Create: `scripts/lib/readable-json.mjs`
- Test: `tests/readable-json.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/readable-json.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readableJson } from '../scripts/lib/readable-json.mjs';

test('it reads back as the same value', () => {
  const value = { schema: 1, list: [1, 2, 3], nested: { a: [{ b: 'x'.repeat(120) }], c: null }, empty: [], none: {} };
  assert.deepEqual(JSON.parse(readableJson(value)), value);
});

test('short values, lists of plain values and small flat objects stay on one line', () => {
  const long = 'y'.repeat(120);
  assert.equal(readableJson({ bounds: [1, 2, 3, 4], layouts: [{ id: 'a', name: 'b' }, { id: 'c', notes: long }] }),
    `{\n  "bounds": [1,2,3,4],\n  "layouts": [\n    {"id":"a","name":"b"},\n    {"id":"c","notes":"${long}"}\n  ]\n}\n`);
});

test('an object holding a long nested value opens up', () => {
  const long = 'z'.repeat(120);
  assert.equal(readableJson({ theme: { part: 'p', colors: { dk1: long } } }),
    `{\n  "theme": {\n    "part": "p",\n    "colors": {"dk1":"${long}"}\n  }\n}\n`);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/readable-json.test.mjs`
Expected: FAIL, the module under test cannot be found (`ERR_MODULE_NOT_FOUND`).

- [ ] **Step 3: Write `scripts/lib/readable-json.mjs`**

```js
// JSON for files people and assistants read: objects and arrays opened one entry to a line,
// but a short value, a list of plain values, or a small flat object kept on one line.
const SHORT = 100;   // characters: a value this long or shorter stays on one line
const FLAT = 400;    // characters: a flat object (no long nested values) this long or shorter stays on one line

function layout(value, indent) {
  const flat = JSON.stringify(value);
  if (value === null || typeof value !== 'object' || flat.length <= SHORT) return flat;
  if (Array.isArray(value) && value.every((each) => each === null || typeof each !== 'object')) return flat;
  if (!Array.isArray(value) && flat.length <= FLAT
      && Object.values(value).every((each) => each === null || typeof each !== 'object' || JSON.stringify(each).length < 60)) {
    return flat;
  }
  const inner = `${indent}  `;
  if (Array.isArray(value)) {
    if (!value.length) return '[]';
    return `[\n${value.map((each) => inner + layout(each, inner)).join(',\n')}\n${indent}]`;
  }
  const entries = Object.entries(value).filter(([, each]) => each !== undefined);
  if (!entries.length) return '{}';
  return `{\n${entries.map(([key, each]) => `${inner}${JSON.stringify(key)}: ${layout(each, inner)}`).join(',\n')}\n${indent}}`;
}

export const readableJson = (value) => `${layout(value, '')}\n`;
```

- [ ] **Step 4: Run them to see them pass**

Run: `node --test tests/readable-json.test.mjs`
Expected: `# pass 3`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/readable-json.mjs tests/readable-json.test.mjs
git commit -m "Write pack files as readable JSON"
```


---

### Task 3: The PowerPoint package reader, and a test template

**Files:**
- Create: `scripts/lib/ooxml.mjs`
- Create: `tests/fixtures/template.mjs`
- Test: `tests/ooxml.test.mjs`

The test template is used by every later task. It holds each case the measuring must handle: a legacy master no slide uses, a placeholder with no frame of its own, a rotated and flipped picture, a slide number, a layout name with a trailing space, a hidden slide, and a theme colour given as a system colour.

- [ ] **Step 1: Write the failing test fixture**

`tests/fixtures/template.mjs`:

```js
// A small PowerPoint template for tests. Master 1 is a legacy master no slide uses; master 2
// has three layouts: "Title Slide" (a subtitle with no frame of its own, which inherits the
// master body's), "Title Only " (a trailing space; a title that inherits the master's, a
// rotated and flipped logo, a slide number, master artwork hidden) and "Blank" (no slide).
// Slide 2 is hidden. The theme gives dk1 as a system colour.
import { writeZip } from '../../scripts/lib/zip.mjs';

const NS = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
  + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
  + 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"';
const rels = (list) => '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
  + list.map(([id, type, target]) => `<Relationship Id="${id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/${type}" Target="${target}"/>`).join('')
  + '</Relationships>';
const xfrm = (x, y, w, h, extra = '') => `<a:xfrm${extra}><a:off x="${x * 12700}" y="${y * 12700}"/><a:ext cx="${w * 12700}" cy="${h * 12700}"/></a:xfrm>`;
const shape = (id, ph, frame = '', style = '') => `<p:sp><p:nvSpPr><p:cNvPr id="${id}" name="Shape ${id}"/><p:cNvSpPr/><p:nvPr>${ph}</p:nvPr></p:nvSpPr>`
  + `<p:spPr>${frame}</p:spPr>${style ? `<p:txBody><a:bodyPr/><a:lstStyle><a:lvl1pPr>${style}</a:lvl1pPr></a:lstStyle><a:p/></p:txBody>` : ''}</p:sp>`;
const tree = (name, shapes) => `<p:cSld${name === null ? '' : ` name="${name}"`}><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>${shapes}</p:spTree></p:cSld>`;
const theme = (accent) => `<a:theme ${NS} name="T"><a:themeElements><a:clrScheme name="C">`
  + '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
  + `<a:accent1><a:srgbClr val="${accent}"/></a:accent1></a:clrScheme><a:fontScheme name="F">`
  + '<a:majorFont><a:latin typeface="Arial"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/></a:minorFont>'
  + '</a:fontScheme></a:themeElements></a:theme>';
const STYLES = '<p:txStyles><p:titleStyle><a:lvl1pPr><a:defRPr sz="2800" b="1"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
  + '<a:latin typeface="+mj-lt"/></a:defRPr></a:lvl1pPr></p:titleStyle><p:bodyStyle><a:lvl1pPr><a:defRPr sz="2000">'
  + '<a:solidFill><a:srgbClr val="333333"/></a:solidFill></a:defRPr></a:lvl1pPr></p:bodyStyle></p:txStyles>';
const master = (shapes, layouts) => `<p:sldMaster ${NS}>${tree(null, shapes)}`
  + '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" hlink="hlink" folHlink="folHlink"/>'
  + `<p:sldLayoutIdLst>${layouts.map((n) => `<p:sldLayoutId id="${2147483648 + n}" r:id="rId${n}"/>`).join('')}</p:sldLayoutIdLst>`
  + `${STYLES}</p:sldMaster>`;
const layout = (name, shapes, attrs = '') => `<p:sldLayout ${NS}${attrs}>${tree(name, shapes)}</p:sldLayout>`;
const slide = (hidden) => `<p:sld ${NS}${hidden ? ' show="0"' : ''}>${tree(null, '')}</p:sld>`;

export function makeTemplate() {
  const masterShapes = shape(2, '<p:ph type="title"/>', xfrm(48, 36, 864, 60))
    + shape(3, '<p:ph type="body" idx="1"/>', xfrm(48, 120, 864, 360))
    + shape(4, '<p:ph type="sldNum" idx="12"/>', xfrm(900, 500, 40, 20))
    + shape(5, '', xfrm(0, 0, 960, 6));
  const logo = '<p:pic><p:nvPicPr><p:cNvPr id="7" name="Logo"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill/>'
    + `<p:spPr>${xfrm(10, 10, 50, 20, ' rot="5400000" flipH="1"')}</p:spPr></p:pic>`;
  return writeZip([
    ['[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'],
    ['ppt/presentation.xml', `<p:presentation ${NS}><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>`
      + '<p:sldMasterId id="2147483652" r:id="rId2"/></p:sldMasterIdLst><p:sldIdLst><p:sldId id="256" r:id="rId3"/>'
      + '<p:sldId id="257" r:id="rId4"/><p:sldId id="258" r:id="rId5"/></p:sldIdLst>'
      + '<p:sldSz cx="12192000" cy="6858000"/></p:presentation>'],
    ['ppt/_rels/presentation.xml.rels', rels([['rId1', 'slideMaster', 'slideMasters/slideMaster1.xml'],
      ['rId2', 'slideMaster', 'slideMasters/slideMaster2.xml'], ['rId3', 'slide', 'slides/slide1.xml'],
      ['rId4', 'slide', 'slides/slide2.xml'], ['rId5', 'slide', 'slides/slide3.xml']])],
    ['ppt/slideMasters/slideMaster1.xml', master(masterShapes, [1])],
    ['ppt/slideMasters/_rels/slideMaster1.xml.rels', rels([['rId1', 'slideLayout', '../slideLayouts/slideLayout4.xml'],
      ['rId9', 'theme', '../theme/theme1.xml']])],
    ['ppt/slideMasters/slideMaster2.xml', master(masterShapes, [1, 2, 3])],
    ['ppt/slideMasters/_rels/slideMaster2.xml.rels', rels([['rId1', 'slideLayout', '../slideLayouts/slideLayout1.xml'],
      ['rId2', 'slideLayout', '../slideLayouts/slideLayout2.xml'], ['rId3', 'slideLayout', '../slideLayouts/slideLayout3.xml'],
      ['rId9', 'theme', '../theme/theme2.xml']])],
    ['ppt/slideLayouts/slideLayout1.xml', layout('Title Slide',
      shape(10, '<p:ph type="ctrTitle"/>', xfrm(100, 200, 700, 100), '<a:defRPr sz="4000"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:defRPr>')
      + shape(11, '<p:ph type="subTitle" idx="1"/>'), ' type="title"')],
    ['ppt/slideLayouts/slideLayout2.xml', layout('Title Only ',
      shape(20, '<p:ph type="title"/>') + logo + shape(21, '<p:ph type="sldNum" idx="12"/>', xfrm(900, 500, 40, 20)),
      ' showMasterSp="0"')],
    ['ppt/slideLayouts/slideLayout3.xml', layout('Blank', '')],
    ['ppt/slideLayouts/slideLayout4.xml', layout('Legacy', shape(30, '<p:ph type="title"/>', xfrm(0, 0, 100, 50)))],
    ...[1, 2, 3, 4].map((n) => [`ppt/slideLayouts/_rels/slideLayout${n}.xml.rels`,
      rels([['rId1', 'slideMaster', `../slideMasters/slideMaster${n === 4 ? 1 : 2}.xml`]])]),
    ['ppt/slides/slide1.xml', slide(false)],
    ['ppt/slides/slide2.xml', slide(true)],
    ['ppt/slides/slide3.xml', slide(false)],
    ['ppt/slides/_rels/slide1.xml.rels', rels([['rId1', 'slideLayout', '../slideLayouts/slideLayout1.xml']])],
    ['ppt/slides/_rels/slide2.xml.rels', rels([['rId1', 'slideLayout', '../slideLayouts/slideLayout2.xml']])],
    ['ppt/slides/_rels/slide3.xml.rels', rels([['rId1', 'slideLayout', '../slideLayouts/slideLayout2.xml']])],
    ['ppt/theme/theme1.xml', theme('999999')],
    ['ppt/theme/theme2.xml', theme('1F4E8C')],
  ]);
}
```

- [ ] **Step 2: Write the failing tests**

`tests/ooxml.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { attr, child, find, openPackage, relationId } from '../scripts/lib/ooxml.mjs';
import { parseXml } from '../scripts/lib/xml.mjs';
import { writeZip } from '../scripts/lib/zip.mjs';
import { makeTemplate } from './fixtures/template.mjs';

test('parts, their XML and their relationships are read, with targets resolved', () => {
  const pkg = openPackage(makeTemplate());
  assert.equal(pkg.related('ppt/slides/slide1.xml', 'slideLayout'), 'ppt/slideLayouts/slideLayout1.xml');
  assert.equal(pkg.target('ppt/presentation.xml', 'rId2'), 'ppt/slideMasters/slideMaster2.xml');
  assert.equal(pkg.related('ppt/slides/slide1.xml', 'theme'), null);
  assert.equal(pkg.xml('ppt/presentation.xml').name, 'p:presentation');
  assert.throws(() => pkg.xml('ppt/missing.xml'), /It has no ppt\/missing\.xml/);
});

test('names are matched whatever their prefix, and r:id is told apart from id', () => {
  const root = parseXml('<x:root xmlns:x="u" xmlns:q="r"><x:a><x:b id="1" q:id="rId7"/></x:a></x:root>');
  const b = find(root, 'a/b');
  assert.equal(attr(b, 'id'), '1');
  assert.equal(relationId(b), 'rId7');
  assert.equal(child(root, 'missing'), null);
  assert.equal(find(root, 'a/missing/b'), null);
});

test('what is not a presentation, or holds a part that cannot be placed, is refused', () => {
  assert.throws(() => openPackage(writeZip([['word/document.xml', '<w/>']])), /not a PowerPoint presentation/);
  assert.throws(() => openPackage(writeZip([['ppt/presentation.xml', '<p/>'], ['ppt/../evil.xml', '<x/>']])), /cannot be placed/);
  const broken = openPackage(writeZip([['ppt/presentation.xml', '<p:presentation>']]));
  assert.throws(() => broken.xml('ppt/presentation.xml'), /ppt\/presentation\.xml cannot be read/);
});
```

- [ ] **Step 3: Run them to see them fail**

Run: `node --test tests/ooxml.test.mjs`
Expected: FAIL, the module under test cannot be found (`ERR_MODULE_NOT_FOUND`).

- [ ] **Step 4: Write `scripts/lib/ooxml.mjs`**

```js
// A PowerPoint (OOXML) package: its parts, their XML and their relationships. Element and
// attribute names are matched by local name, so any namespace prefix works.
import { posix } from 'node:path';
import { readZip } from './zip.mjs';
import { parseXml, walk } from './xml.mjs';

export const EMU_PER_PT = 12700;
const MOST_PARTS = 10000;
const MOST_BYTES = 256 * 1024 * 1024;

export const local = (name) => String(name).split(':').pop();
export const child = (node, name) => node?.children.find((each) => local(each.name) === name) ?? null;
export const children = (node, name) => node?.children.filter((each) => local(each.name) === name) ?? [];
export const find = (node, steps) => steps.split('/').reduce((here, step) => child(here, step), node);
export const descendants = (node, name) => (node ? [...walk(node)].filter((each) => each !== node && local(each.name) === name) : []);
export const descendant = (node, name) => descendants(node, name)[0] ?? null;

/** An attribute by local name, such as "id" for r:id. */
export function attr(node, name) {
  if (!node) return undefined;
  for (const [key, value] of Object.entries(node.attrs)) if (local(key) === name) return value;
  return undefined;
}

/** The package in `buffer`: {parts, xml(part), rels(part), related(part, type), target(part, id)}.
 *  Refuses what is not a presentation, and parts that could not be placed safely. */
export function openPackage(buffer) {
  const parts = readZip(buffer);
  if (parts.size > MOST_PARTS) throw new Error('It holds more parts than a presentation does.');
  let total = 0;
  for (const [name, data] of parts) {
    if (name.startsWith('/') || name.includes('\\') || name.split('/').includes('..')) {
      throw new Error(`It holds a part that cannot be placed: ${name}.`);
    }
    total += data.length;
  }
  if (total > MOST_BYTES) throw new Error('It is larger unpacked than a presentation is.');
  if (!parts.has('ppt/presentation.xml')) throw new Error('It is not a PowerPoint presentation: it has no ppt/presentation.xml.');
  const cache = new Map();
  const xml = (part) => {
    if (!cache.has(part)) {
      const data = parts.get(part);
      if (!data) throw new Error(`It has no ${part}.`);
      try {
        cache.set(part, parseXml(data.toString('utf8')));
      } catch (error) {
        throw new Error(`Its ${part} cannot be read: ${error.message}`);
      }
    }
    return cache.get(part);
  };
  const rels = (part) => {
    const dir = posix.dirname(part);
    const file = `${dir}/_rels/${posix.basename(part)}.rels`;
    if (!parts.has(file)) return [];
    return children(xml(file), 'Relationship').filter((each) => each.attrs.TargetMode !== 'External').map((each) => {
      const target = String(each.attrs.Target ?? '');
      return { id: each.attrs.Id, type: String(each.attrs.Type ?? '').split('/').pop(),
        target: target.startsWith('/') ? target.slice(1) : posix.normalize(posix.join(dir, target)) };
    });
  };
  const related = (part, type) => rels(part).find((each) => each.type === type)?.target ?? null;
  const target = (part, id) => rels(part).find((each) => each.id === id)?.target ?? null;
  return { parts, xml, rels, related, target };
}

/** The relationship id on an element (r:id), as opposed to its own plain `id`. */
export function relationId(node) {
  for (const [key, value] of Object.entries(node?.attrs ?? {})) if (key.includes(':') && local(key) === 'id') return value;
  return undefined;
}
```

- [ ] **Step 5: Run them to see them pass**

Run: `node --test tests/ooxml.test.mjs`
Expected: `# pass 3`, `# fail 0`.

- [ ] **Step 6: Commit**

```bash
git add scripts/lib/ooxml.mjs tests/fixtures/template.mjs tests/ooxml.test.mjs
git commit -m "Read PowerPoint packages by part and relationship, with a small test template"
```


---

### Task 4: Tokens from a Claude Design export

**Files:**
- Create: `scripts/lib/pack/tokens.mjs`
- Test: `tests/tokens.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/tokens.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { hexColor, parseThemes, readTokens } from '../scripts/lib/pack/tokens.mjs';

const TOKENS = {
  name: 'Example Co', version: 1,
  color: { themes: [{ id: 'light', name: 'Light' }, { id: 'dark', name: 'Dark' }], tokens: [
    { name: 'blue', value: '#005C8A', usage: 'Headings.' },
    { name: 'white', value: '#fff', usage: 'Ground.' },
    { name: 'ink', value: 'rgb(0, 0, 0)' },
  ] },
  type: { families: { sans: 'Arial, sans-serif' }, groups: [
    { name: 'Titles', family: 'sans', styles: [{ name: 'title', fontSize: '36px', lineHeight: '39px', fontWeight: 400, usage: 'Slide titles.' }] },
    { name: 'Body', styles: [{ name: 'body', fontSize: '20px', fontWeight: 400 }] },
  ] },
  spacing: { tokens: [{ name: 'space-margin', value: '48px', usage: 'Slide margin.' }] },
  radius: { tokens: [{ name: 'radius-none', value: '0' }] },
  gradient: { tokens: [{ name: 'gradient-bar', value: 'linear-gradient(90deg, #61a60e, #6c4b94)' }] },
};
const CSS = `/* generated */
:root, [data-theme="light"] {
  --blue: #005c8a;
  --white: #ffffff;
  --ink: var(--black, #000000);
  --surface: var(--white);
}
[data-theme="dark"] {
  --blue: #0088ef;
  --ink: var(--white);
  --surface: var(--blue);
}
.t-title { font-size: 36px; }`;
const files = (tokens = TOKENS, css = CSS) => new Map([['export/tokens.json', Buffer.from(JSON.stringify(tokens))],
  ...(css === null ? [] : [['export/tokens.css', Buffer.from(css)]])]);

test('colours are written as #rrggbb wherever a plain colour is given', () => {
  assert.equal(hexColor('#ABC'), '#aabbcc');
  assert.equal(hexColor('#005C8A'), '#005c8a');
  assert.equal(hexColor('#005c8aff'), '#005c8a');
  assert.equal(hexColor('rgb(0%, 100%, 0%)'), '#00ff00');
  assert.equal(hexColor('rgba(255, 0, 0, 1)'), '#ff0000');
  assert.equal(hexColor('rgba(255, 0, 0, 0.5)'), null);
  assert.equal(hexColor('var(--blue)'), null);
});

test('tokens.css gives each theme its properties', () => {
  const themes = parseThemes(CSS);
  assert.equal(themes.light.blue, '#005c8a');
  assert.equal(themes.dark.blue, '#0088ef');
  assert.equal(themes.light['font-size'], undefined);
});

test('each colour gets its light value and, where the dark theme differs, its dark value', () => {
  const made = readTokens(files());
  assert.deepEqual(made.colors, [
    { name: 'blue', light: '#005c8a', dark: '#0088ef', usage: 'Headings.' },
    { name: 'white', light: '#ffffff', usage: 'Ground.' },
    { name: 'ink', light: '#000000', dark: '#ffffff' },
    { name: 'surface', light: '#ffffff', dark: '#0088ef', usage: 'Named in tokens.css only.' },
  ]);
  assert.deepEqual(made.themes, ['light', 'dark']);
});

test('type styles keep their values and say their group, and the rest is kept', () => {
  const made = readTokens(files());
  assert.deepEqual(made.type.families, { sans: 'Arial, sans-serif' });
  assert.deepEqual(made.type.styles, [
    { name: 'title', fontSize: '36px', lineHeight: '39px', fontWeight: 400, usage: 'Slide titles.', group: 'Titles', family: 'sans' },
    { name: 'body', fontSize: '20px', fontWeight: 400, group: 'Body' },
  ]);
  assert.deepEqual(made.spacing, [{ name: 'space-margin', value: '48px', usage: 'Slide margin.' }]);
  assert.deepEqual(Object.keys(made.other), ['gradient']);
  assert.deepEqual(made.source, { name: 'Example Co', version: 1, file: 'export/tokens.json' });
});

test('without tokens.css, colours keep the values tokens.json gives', () => {
  const made = readTokens(files(TOKENS, null));
  assert.deepEqual(made.colors.map((color) => [color.name, color.light, color.dark]),
    [['blue', '#005c8a', undefined], ['white', '#ffffff', undefined], ['ink', '#000000', undefined]]);
});

test('an export without usable tokens is refused in a sentence', () => {
  assert.throws(() => readTokens(new Map([['a.svg', Buffer.from('<svg/>')]])), /holds no tokens\.json/);
  assert.throws(() => readTokens(new Map([['tokens.json', Buffer.from('{bad')]])), /tokens\.json is not JSON/);
  assert.throws(() => readTokens(new Map([['tokens.json', Buffer.from('{}')]])), /no colour tokens/);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/tokens.test.mjs`
Expected: FAIL, the module under test cannot be found (`ERR_MODULE_NOT_FOUND`).

- [ ] **Step 3: Write `scripts/lib/pack/tokens.mjs`**

```js
// A design system's tokens as a pack's tokens.json: every colour with its light and dark value,
// the type styles, spacing, radius and the rest, read from a Claude Design export (tokens.json,
// with dark values from tokens.css) or from a folder holding the same files.

const amount = (text) => {
  const value = String(text).trim();
  return value.endsWith('%') ? parseFloat(value) / 100 : parseFloat(value);
};

/** `#rrggbb` for a colour written as #rgb, #rrggbb, #rrggbbff, rgb() or an opaque rgba(), else null. */
export function hexColor(text) {
  const value = String(text ?? '').trim().toLowerCase().replace(/\s+/g, '');
  let match = /^#([0-9a-f]{3})$/.exec(value);
  if (match) return `#${[...match[1]].map((c) => c + c).join('')}`;
  if (/^#[0-9a-f]{6}$/.test(value)) return value;
  if (/^#[0-9a-f]{6}ff$/.test(value)) return value.slice(0, 7);
  match = /^rgba?\(([^)]*)\)$/.exec(value);
  if (!match) return null;
  const parts = match[1].split(/[,/]/);
  if (parts.length < 3 || parts.length > 4 || (parts.length === 4 && amount(parts[3]) !== 1)) return null;
  const channels = parts.slice(0, 3).map((part) => Math.round(part.endsWith('%') ? parseFloat(part) * 2.55 : parseFloat(part)));
  if (!channels.every((c) => Number.isFinite(c) && c >= 0 && c <= 255)) return null;
  return `#${channels.map((c) => c.toString(16).padStart(2, '0')).join('')}`;
}

/** The custom properties tokens.css sets for each theme: {light: {name: value}, dark: {...}}. */
export function parseThemes(css) {
  const themes = { light: {}, dark: {} };
  for (const [, selector, body] of String(css).replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const theme = /data-theme\s*=\s*["']?dark/.test(selector) ? 'dark'
      : /:root|data-theme\s*=\s*["']?light/.test(selector) ? 'light' : null;
    if (!theme) continue;
    for (const [, name, value] of body.matchAll(/--([\w-]+)\s*:\s*([^;]+);/g)) themes[theme][name] = value.trim();
  }
  return themes;
}

/** A property's value in a theme, following var() through that theme, then the light one. */
function resolve(themes, theme, name, seen = new Set()) {
  if (seen.has(name)) return null;
  seen.add(name);
  const value = themes[theme][name] ?? themes.light[name];
  if (value === undefined) return null;
  const reference = /^var\(\s*--([\w-]+)\s*(?:,\s*(.+))?\)$/.exec(value);
  if (!reference) return value;
  return resolve(themes, theme, reference[1], seen) ?? reference[2]?.trim() ?? null;
}

const named = (files, file) => [...files.keys()].filter((name) => name.split('/').pop() === file)
  .sort((a, b) => a.split('/').length - b.split('/').length)[0];

/** tokens.json for a pack, from the files of an export (a Map of path to Buffer). */
export function readTokens(files) {
  const jsonPath = named(files, 'tokens.json');
  if (!jsonPath) throw new Error('It holds no tokens.json.');
  let tokens;
  try {
    tokens = JSON.parse(files.get(jsonPath).toString('utf8'));
  } catch (error) {
    throw new Error(`Its ${jsonPath} is not JSON (${error.message}).`);
  }
  if (!tokens || typeof tokens !== 'object' || !Array.isArray(tokens.color?.tokens)) {
    throw new Error(`Its ${jsonPath} has no colour tokens (color.tokens).`);
  }
  const cssPath = jsonPath.replace(/tokens\.json$/, 'tokens.css');
  const themes = files.has(cssPath) ? parseThemes(files.get(cssPath).toString('utf8')) : { light: {}, dark: {} };
  const colors = [];
  const listed = new Set();
  for (const token of tokens.color.tokens) {
    const name = String(token?.name ?? '').trim();
    if (!name || listed.has(name)) continue;
    listed.add(name);
    const lightText = resolve(themes, 'light', name) ?? token.value;
    const color = { name, light: hexColor(lightText) ?? String(lightText ?? '') };
    const darkText = token.dark ?? (themes.dark[name] !== undefined ? resolve(themes, 'dark', name) : null);
    if (darkText !== null && darkText !== undefined) {
      const dark = hexColor(darkText) ?? String(darkText);
      if (dark !== color.light) color.dark = dark;
    }
    if (token.usage) color.usage = String(token.usage);
    colors.push(color);
  }
  // Colours tokens.css names that tokens.json does not, such as surface or chart-1.
  for (const name of [...new Set([...Object.keys(themes.light), ...Object.keys(themes.dark)])]) {
    if (listed.has(name)) continue;
    const light = name in themes.light ? hexColor(resolve(themes, 'light', name)) : null;
    const dark = name in themes.dark ? hexColor(resolve(themes, 'dark', name)) : null;
    if (!light && !dark) continue;
    const color = { name };
    if (light) color.light = light;
    if (dark && dark !== light) color.dark = dark;
    color.usage = 'Named in tokens.css only.';
    colors.push(color);
  }
  const styles = (tokens.type?.groups ?? []).flatMap((group) => (group?.styles ?? []).map((style) => ({
    ...style, group: group.name, ...(group.family ? { family: group.family } : {}) })));
  const known = new Set(['name', 'version', 'meta', 'color', 'type', 'spacing', 'radius']);
  const other = Object.fromEntries(Object.entries(tokens).filter(([key]) => !known.has(key)));
  return {
    schema: 1,
    name: String(tokens.name ?? ''),
    themes: (tokens.color.themes ?? []).map((theme) => String(theme?.id ?? theme)).filter(Boolean),
    colors,
    type: { families: tokens.type?.families ?? {}, styles },
    spacing: tokens.spacing?.tokens ?? [],
    radius: tokens.radius?.tokens ?? [],
    ...(Object.keys(other).length ? { other } : {}),
    source: { name: tokens.name ?? null, version: tokens.version ?? null, file: jsonPath },
  };
}
```

- [ ] **Step 4: Run them to see them pass**

Run: `node --test tests/tokens.test.mjs`
Expected: `# pass 6`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/pack/tokens.mjs tests/tokens.test.mjs
git commit -m "Read a design system's tokens, with dark values from tokens.css"
```


---

### Task 5: Measuring a template

**Files:**
- Create: `scripts/lib/pack/measure.mjs`
- Test: `tests/measure.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/measure.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { measureTemplate, mergeLayouts } from '../scripts/lib/pack/measure.mjs';
import { writeZip } from '../scripts/lib/zip.mjs';
import { makeTemplate } from './fixtures/template.mjs';

const measured = measureTemplate(makeTemplate(), { variant: 'light' });
const byName = (name) => measured.layouts.find((layout) => layout.name === name);

test('the master the visible slides use is measured, and the others are listed', () => {
  assert.equal(measured.master, 'ppt/slideMasters/slideMaster2.xml');
  assert.deepEqual(measured.masters, [
    { number: 1, part: 'ppt/slideMasters/slideMaster1.xml', layouts: 1, slides: 0 },
    { number: 2, part: 'ppt/slideMasters/slideMaster2.xml', layouts: 3, slides: 2 },
  ]);
  assert.deepEqual(measured.layouts.map((layout) => layout.id), ['light-layout-001', 'light-layout-002', 'light-layout-003']);
  assert.deepEqual(measured.canvas, { width: 960, height: 540 });
  assert.equal(measured.template, 'templates/light.pptx');
  assert.match(measured.sha256, /^[0-9a-f]{64}$/);
});

test('the theme gives its colours, a system colour by its last value, and its fonts', () => {
  assert.equal(measured.theme.part, 'ppt/theme/theme2.xml');
  assert.deepEqual(measured.theme.colors, { dk1: '#000000', lt1: '#ffffff', accent1: '#1f4e8c' });
  assert.deepEqual(measured.theme.fonts, { major: 'Arial', minor: 'Arial' });
});

test('a placeholder with no frame takes its master placeholder\'s, and its text style is resolved', () => {
  assert.deepEqual(byName('Title Slide').placeholders, [
    { id: '10', type: 'ctrTitle', bounds: [100, 200, 700, 100], size: 40, bold: true, font: 'Arial',
      color: { scheme: 'accent1', hex: '#1f4e8c' } },
    { id: '11', type: 'subTitle', idx: '1', bounds: [48, 120, 864, 360], inherited: true, size: 20,
      color: { hex: '#333333' } },
  ]);
  assert.deepEqual(byName('Title Only').placeholders, [
    { id: '20', type: 'title', bounds: [48, 36, 864, 60], inherited: true, size: 28, bold: true, font: 'Arial',
      color: { scheme: 'tx1', hex: '#000000' } },
  ]);
});

test('artwork keeps its rotation and flips, and a slide number counts as artwork', () => {
  assert.deepEqual(byName('Title Only').artwork, [
    { id: '7', kind: 'pic', bounds: [10, 10, 50, 20], rotation: 90, flipH: true },
    { id: '21', kind: 'sp', placeholder: 'sldNum', bounds: [900, 500, 40, 20] },
  ]);
  assert.deepEqual(measured.masterArtwork, [
    { id: '4', kind: 'sp', placeholder: 'sldNum', bounds: [900, 500, 40, 20] },
    { id: '5', kind: 'sp', bounds: [0, 0, 960, 6] },
  ]);
});

test('names are tidied, and each layout knows its first visible slide and page', () => {
  const titleOnly = byName('Title Only');
  assert.equal(titleOnly.rawName, 'Title Only ');
  assert.deepEqual([titleOnly.used, titleOnly.slide, titleOnly.renderPage, titleOnly.showsMasterArtwork], [true, 3, 2, false]);
  assert.deepEqual([byName('Title Slide').type, byName('Title Slide').renderPage], ['title', 1]);
  assert.deepEqual([byName('Blank').used, byName('Blank').slide, byName('Blank').renderPage], [false, null, null]);
  assert.deepEqual(measured.slides, [
    { slide: 1, hidden: false, renderPage: 1, layout: 'light-layout-001' },
    { slide: 2, hidden: true, renderPage: null, layout: 'light-layout-002' },
    { slide: 3, hidden: false, renderPage: 2, layout: 'light-layout-002' },
  ]);
});

test('another master can be chosen by number or part, and an unknown one is refused', () => {
  const legacy = measureTemplate(makeTemplate(), { variant: 'light', master: '1' });
  assert.deepEqual(legacy.layouts.map((layout) => layout.name), ['Legacy']);
  assert.equal(measureTemplate(makeTemplate(), { variant: 'light', master: 'ppt/slideMasters/slideMaster1.xml' }).layouts.length, 1);
  assert.throws(() => measureTemplate(makeTemplate(), { variant: 'light', master: '9' }),
    /no master 9\. Its masters are: 1 \(ppt\/slideMasters\/slideMaster1\.xml\), 2/);
});

test('what is not a template, or not a variant name, is refused', () => {
  assert.throws(() => measureTemplate(makeTemplate(), { variant: 'Light Theme' }), /variant is lower-case/);
  assert.throws(() => measureTemplate(writeZip([['word/document.xml', '<w/>']]), { variant: 'light' }), /not a PowerPoint presentation/);
  assert.throws(() => measureTemplate(Buffer.from('nope'), { variant: 'light' }), /not a ZIP archive/);
});

test('measuring again keeps what was added to a layout, and its preview while the template is the same', () => {
  const first = mergeLayouts(null, 'light', measured);
  const titleOnly = first.variants.light.layouts[1];
  Object.assign(titleOnly, { relationship: 'statement', searchTerms: ['one idea'], preview: 'previews/light/light-layout-002.png' });
  const again = mergeLayouts(first, 'light', measureTemplate(makeTemplate(), { variant: 'light' }));
  assert.deepEqual(again.variants.light.layouts[1].searchTerms, ['one idea']);
  assert.equal(again.variants.light.layouts[1].preview, 'previews/light/light-layout-002.png');
  const changed = mergeLayouts(first, 'light', { ...measured, sha256: '0'.repeat(64) });
  assert.equal(changed.variants.light.layouts[1].relationship, 'statement');
  assert.equal(changed.variants.light.layouts[1].preview, undefined);
  const both = mergeLayouts(first, 'dark', { ...measured, template: 'templates/dark.pptx' });
  assert.deepEqual(Object.keys(both.variants), ['dark', 'light']);
  assert.equal(both.schema, 1);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/measure.test.mjs`
Expected: FAIL, the module under test cannot be found (`ERR_MODULE_NOT_FOUND`).

- [ ] **Step 3: Write `scripts/lib/pack/measure.mjs`**

```js
// Measuring a PowerPoint template: the master its slides use, each of that master's layouts
// with its placeholders and artwork, the theme's colours and fonts, and the slides.
import { createHash } from 'node:crypto';
import {
  EMU_PER_PT, attr, child, children, descendant, find, local, openPackage, relationId,
} from '../ooxml.mjs';

const SHAPES = new Set(['sp', 'pic', 'grpSp', 'cxnSp', 'graphicFrame']);
const FURNITURE = new Set(['ftr', 'hdr', 'dt', 'sldNum']);   // placeholders that are template artwork
const PRESENTATION = 'ppt/presentation.xml';

const round = (n) => {
  const v = Math.round(n * 100) / 100;
  return v === 0 ? 0 : v;
};
const pt = (emu) => round(Number(emu) / EMU_PER_PT);
const tidy = (text) => String(text ?? '').replace(/\s+/g, ' ').trim();
const family = (type) => (type === 'title' || type === 'ctrTitle' ? 'title'
  : ['body', 'obj', 'subTitle'].includes(type) ? 'body' : type);

function slidesOf(pkg) {
  let page = 0;
  return children(child(pkg.xml(PRESENTATION), 'sldIdLst'), 'sldId').map((entry, n) => {
    const part = pkg.target(PRESENTATION, relationId(entry));
    if (!part) throw new Error(`Slide ${n + 1} is listed but has no part.`);
    const hidden = attr(pkg.xml(part), 'show') === '0';
    if (!hidden) page += 1;
    return { slide: n + 1, part, layoutPart: pkg.related(part, 'slideLayout'), hidden, renderPage: hidden ? null : page };
  });
}

function mastersOf(pkg) {
  return children(child(pkg.xml(PRESENTATION), 'sldMasterIdLst'), 'sldMasterId').map((entry, n) => {
    const part = pkg.target(PRESENTATION, relationId(entry));
    if (!part) throw new Error(`Master ${n + 1} is listed but has no part.`);
    const layouts = children(child(pkg.xml(part), 'sldLayoutIdLst'), 'sldLayoutId')
      .map((each) => pkg.target(part, relationId(each))).filter(Boolean);
    return { number: n + 1, part, layouts };
  });
}

/** The master named by `wanted` (its number or part), else the one most visible slides use. */
function chooseMaster(masters, slides, wanted) {
  if (!masters.length) throw new Error('It has no slide master.');
  if (wanted !== undefined && wanted !== null) {
    const chosen = masters.find((m) => m.part === wanted || String(m.number) === String(wanted));
    if (!chosen) {
      throw new Error(`It has no master ${wanted}. Its masters are: ${
        masters.map((m) => `${m.number} (${m.part})`).join(', ')}.`);
    }
    return chosen;
  }
  const visible = (m) => slides.filter((s) => !s.hidden && m.layouts.includes(s.layoutPart)).length;
  return masters.reduce((best, m) => (visible(m) > visible(best) ? m : best));
}

function themeOf(pkg, masterPart) {
  const part = pkg.related(masterPart, 'theme');
  const theme = { part, colors: {}, fonts: {} };
  if (!part) return theme;
  const root = pkg.xml(part);
  for (const entry of find(root, 'themeElements/clrScheme')?.children ?? []) {
    const value = entry.children[0];
    const raw = local(value?.name) === 'sysClr' ? value.attrs.lastClr : value?.attrs.val;
    if (/^[0-9a-f]{6}$/i.test(raw ?? '')) theme.colors[local(entry.name)] = `#${raw.toLowerCase()}`;
  }
  for (const [key, name] of [['majorFont', 'major'], ['minorFont', 'minor']]) {
    const face = find(root, `themeElements/fontScheme/${key}/latin`)?.attrs.typeface;
    if (face) theme.fonts[name] = face;
  }
  return theme;
}

/** {bounds: [x, y, width, height] in points, rotation?, flipH?, flipV?} from a shape's own frame. */
function frameOf(shape) {
  const xfrm = find(shape, 'spPr/xfrm') ?? child(shape, 'xfrm') ?? find(shape, 'grpSpPr/xfrm');
  const off = child(xfrm, 'off');
  const ext = child(xfrm, 'ext');
  if (!off || !ext) return null;
  const out = { bounds: [pt(off.attrs.x), pt(off.attrs.y), pt(ext.attrs.cx), pt(ext.attrs.cy)] };
  if (Number(xfrm.attrs.rot)) out.rotation = round(Number(xfrm.attrs.rot) / 60000);
  if (xfrm.attrs.flipH === '1') out.flipH = true;
  if (xfrm.attrs.flipV === '1') out.flipV = true;
  return out;
}

const shapesOf = (root) => (find(root, 'cSld/spTree')?.children ?? []).filter((each) => SHAPES.has(local(each.name)));

function placeholderOf(shape) {
  if (local(shape.name) === 'grpSp') return null;
  const ph = descendant(shape, 'ph');
  return ph ? { type: ph.attrs.type ?? 'obj', idx: ph.attrs.idx } : null;
}

/** The master placeholder a layout placeholder inherits from: same idx, else same type, else same family. */
function inheritFrom(masterPlaceholders, { type, idx }) {
  if (idx !== undefined) {
    const same = masterPlaceholders.find((each) => each.idx === idx);
    if (same) return same;
  }
  return masterPlaceholders.find((each) => each.type === type)
    ?? masterPlaceholders.find((each) => family(each.type) === family(type)) ?? null;
}

function runStyle(defRPr) {
  if (!defRPr) return {};
  const out = {};
  if (defRPr.attrs.sz) out.size = Number(defRPr.attrs.sz) / 100;
  if (defRPr.attrs.b !== undefined) out.bold = defRPr.attrs.b === '1' || defRPr.attrs.b === 'true';
  const face = child(defRPr, 'latin')?.attrs.typeface;
  if (face) out.font = face;
  const fill = child(defRPr, 'solidFill')?.children[0];
  if (fill) {
    const kind = local(fill.name);
    out.color = kind === 'schemeClr' ? { scheme: fill.attrs.val } : { value: kind === 'sysClr' ? fill.attrs.lastClr : fill.attrs.val };
  }
  return out;
}

/** The text style a placeholder's first level shows: the first value found for each of size,
 *  bold, font and colour along the shape, its master placeholder, the master's text styles
 *  and the presentation's default. */
function textStyle(chain, theme, colorMap) {
  const out = {};
  for (const node of chain) {
    for (const [key, value] of Object.entries(runStyle(node))) if (out[key] === undefined) out[key] = value;
  }
  if (out.font === '+mj-lt') out.font = theme.fonts.major ?? out.font;
  if (out.font === '+mn-lt') out.font = theme.fonts.minor ?? out.font;
  if (out.color) {
    if (out.color.scheme) {
      const mapped = colorMap[out.color.scheme] ?? out.color.scheme;
      out.color = { scheme: out.color.scheme, hex: theme.colors[mapped] ?? null };
    } else {
      out.color = { hex: /^[0-9a-f]{6}$/i.test(out.color.value ?? '') ? `#${out.color.value.toLowerCase()}` : null };
    }
  }
  return out;
}

const ownStyle = (shape) => (shape ? [find(shape, 'txBody/lstStyle/lvl1pPr/defRPr'), find(shape, 'txBody/p/pPr/defRPr')] : []);

function describe(shape, context) {
  const { masterPlaceholders, masterRoot, presentation, theme, colorMap } = context;
  const kind = local(shape.name);
  const identity = descendant(shape, 'cNvPr');
  const placeholder = placeholderOf(shape);
  let frame = frameOf(shape);
  const item = { id: identity?.attrs.id ?? null };
  if (placeholder && !FURNITURE.has(placeholder.type)) {
    const from = inheritFrom(masterPlaceholders, placeholder);
    if (!frame && from) {
      frame = frameOf(from.shape);
      if (frame) item.inherited = true;
    }
    const styles = child(masterRoot, 'txStyles');
    const chain = [...ownStyle(shape), ...ownStyle(from?.shape),
      find(styles, `${family(placeholder.type) === 'title' ? 'titleStyle' : 'bodyStyle'}/lvl1pPr/defRPr`),
      find(presentation, 'defaultTextStyle/lvl1pPr/defRPr')];
    const style = textStyle(chain, theme, colorMap);
    const ordered = Object.fromEntries(['size', 'bold', 'font', 'color'].filter((key) => style[key] !== undefined)
      .map((key) => [key, style[key]]));
    return { content: true, item: { id: item.id, type: placeholder.type,
      ...(placeholder.idx !== undefined ? { idx: placeholder.idx } : {}), ...frame,
      ...(item.inherited ? { inherited: true } : {}), ...ordered } };
  }
  return { content: false, item: { ...item, kind, ...(placeholder ? { placeholder: placeholder.type } : {}), ...frame } };
}

const sha256 = (buffer) => createHash('sha256').update(buffer).digest('hex');

/** The template measured, for one variant of a pack's layouts.json. `master` chooses a master
 *  by number or part; otherwise the one most visible slides use. */
export function measureTemplate(buffer, { variant, master } = {}) {
  if (!/^[a-z][a-z0-9-]*$/.test(String(variant ?? ''))) {
    throw new Error('A variant is lower-case letters, digits and hyphens, starting with a letter, such as light or dark.');
  }
  const pkg = openPackage(buffer);
  const presentation = pkg.xml(PRESENTATION);
  const size = child(presentation, 'sldSz');
  if (!size) throw new Error('Its presentation gives no slide size.');
  const slides = slidesOf(pkg);
  const masters = mastersOf(pkg);
  const chosen = chooseMaster(masters, slides, master);
  const masterRoot = pkg.xml(chosen.part);
  const theme = themeOf(pkg, chosen.part);
  const colorMap = child(masterRoot, 'clrMap')?.attrs ?? {};
  const masterPlaceholders = shapesOf(masterRoot).map((shape) => ({ ...placeholderOf(shape), shape }))
    .filter((each) => each.type);
  const context = { masterPlaceholders, masterRoot, presentation, theme, colorMap };
  const masterArtwork = shapesOf(masterRoot).map((shape) => describe(shape, context))
    .filter((each) => !each.content).map((each) => each.item);
  const ids = new Map();
  const layouts = chosen.layouts.map((part, n) => {
    const root = pkg.xml(part);
    const id = `${variant}-layout-${String(n + 1).padStart(3, '0')}`;
    ids.set(part, id);
    const rawName = String(attr(child(root, 'cSld'), 'name') ?? '');
    const first = slides.find((s) => !s.hidden && s.layoutPart === part);
    const layout = { id, name: tidy(rawName), part };
    if (rawName !== layout.name) layout.rawName = rawName;
    if (attr(root, 'type')) layout.type = attr(root, 'type');
    Object.assign(layout, { used: Boolean(first), slide: first?.slide ?? null, renderPage: first?.renderPage ?? null });
    if (attr(root, 'showMasterSp') === '0') layout.showsMasterArtwork = false;
    const described = shapesOf(root).map((shape) => describe(shape, context));
    layout.placeholders = described.filter((each) => each.content).map((each) => each.item);
    layout.artwork = described.filter((each) => !each.content).map((each) => each.item);
    return layout;
  });
  return {
    template: `templates/${variant}.pptx`,
    sha256: sha256(buffer),
    canvas: { width: pt(size.attrs.cx), height: pt(size.attrs.cy) },
    master: chosen.part,
    masters: masters.map((m) => ({ number: m.number, part: m.part, layouts: m.layouts.length,
      slides: slides.filter((s) => !s.hidden && m.layouts.includes(s.layoutPart)).length })),
    theme,
    masterArtwork,
    layouts,
    slides: slides.map((s) => ({ slide: s.slide, hidden: s.hidden, renderPage: s.renderPage,
      layout: ids.get(s.layoutPart) ?? null })),
  };
}

/** What a person or an assistant adds to a measured layout, kept when the template is measured again. */
export const JUDGEMENT = ['relationship', 'contentRange', 'components', 'searchTerms', 'delivery', 'searchable', 'notes'];

/** layouts.json with one variant measured afresh. A layout keeps its judgement fields when one
 *  with the same part and name was there before, and its preview when the template is unchanged. */
export function mergeLayouts(previous, variant, measured) {
  const before = previous?.variants?.[variant];
  const layouts = measured.layouts.map((layout) => {
    const old = before?.layouts?.find((each) => each.part === layout.part && each.name === layout.name);
    if (!old) return { ...layout };
    const kept = {};
    for (const key of JUDGEMENT) if (old[key] !== undefined) kept[key] = old[key];
    if (old.preview && before.sha256 === measured.sha256) kept.preview = old.preview;
    return { ...layout, ...kept };
  });
  const variants = { ...(previous?.variants ?? {}), [variant]: { ...measured, layouts } };
  return { schema: 1, variants: Object.fromEntries(Object.keys(variants).sort().map((key) => [key, variants[key]])) };
}
```

- [ ] **Step 4: Run them to see them pass**

Run: `node --test tests/measure.test.mjs`
Expected: `# pass 8`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/pack/measure.mjs tests/measure.test.mjs
git commit -m "Measure a template: the master its slides use, each layout, the theme and the slides"
```


---

### Task 6: Previews

**Files:**
- Create: `scripts/lib/pack/previews.mjs`
- Test: `tests/previews.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/previews.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { drawPreviews, findTool } from '../scripts/lib/pack/previews.mjs';
import { measureTemplate, mergeLayouts } from '../scripts/lib/pack/measure.mjs';
import { makeTemplate } from './fixtures/template.mjs';

const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 1, 2, 3]);

function pack() {
  const folder = mkdtempSync(join(tmpdir(), 'hb-previews-'));
  const template = makeTemplate();
  mkdirSync(join(folder, 'templates'));
  writeFileSync(join(folder, 'templates', 'light.pptx'), template);
  writeFileSync(join(folder, 'layouts.json'), JSON.stringify(mergeLayouts(null, 'light', measureTemplate(template, { variant: 'light' }))));
  return folder;
}

test('each layout with an example slide gets the picture of its page', () => {
  const folder = pack();
  const asked = [];
  const result = drawPreviews(folder, 'light', (template, pages, visible) => {
    asked.push([template.endsWith('templates/light.pptx'), pages, visible]);
    return new Map(pages.map((page) => [page, PNG]));
  });
  assert.deepEqual(asked, [[true, [1, 2], 2]]);
  assert.deepEqual(result, { drawn: 2, without: 1 });
  const layouts = JSON.parse(readFileSync(join(folder, 'layouts.json'), 'utf8')).variants.light.layouts;
  assert.deepEqual(layouts.map((layout) => layout.preview),
    ['previews/light/light-layout-001.png', 'previews/light/light-layout-002.png', undefined]);
  assert.deepEqual(readFileSync(join(folder, 'previews', 'light', 'light-layout-002.png')), PNG);
  assert.ok(!existsSync(join(folder, 'previews', 'light', 'light-layout-003.png')));
});

test('what cannot be drawn is refused in a sentence', () => {
  const folder = pack();
  assert.throws(() => drawPreviews(folder, 'dark', () => new Map()), /no variant dark\. Its variants are: light/);
  assert.throws(() => drawPreviews(folder, 'light', (t, pages) => new Map(pages.map((page) => [page, Buffer.from('GIF89a')]))),
    /Page 1 was not drawn as a PNG/);
  assert.throws(() => drawPreviews(mkdtempSync(join(tmpdir(), 'hb-empty-')), 'light', () => new Map()), /has no layouts\.json/);
});

test('a program named outright must be one that can be run', () => {
  const folder = mkdtempSync(join(tmpdir(), 'hb-tool-'));
  writeFileSync(join(folder, 'not-a-program'), 'text');
  assert.throws(() => findTool('soffice', join(folder, 'not-a-program')), /is not a program that can be run/);
  assert.equal(findTool('node', process.execPath), process.execPath);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/previews.test.mjs`
Expected: FAIL, the module under test cannot be found (`ERR_MODULE_NOT_FOUND`).

- [ ] **Step 3: Write `scripts/lib/pack/previews.mjs`**

```js
// Previews of a pack's layouts: the template drawn by LibreOffice and Poppler, one picture for
// each layout that a visible slide uses, kept as previews/<variant>/<layout id>.png.
import { spawnSync } from 'node:child_process';
import { accessSync, constants, existsSync, mkdtempSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { delimiter, join } from 'node:path';
import { readableJson } from '../readable-json.mjs';

const PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const WAIT = 300_000;   // milliseconds LibreOffice may take for one template
const PLACES = { soffice: ['/Applications/LibreOffice.app/Contents/MacOS/soffice'] };

/** The path of a program: the one given, else the first on PATH, else a usual install place. */
export function findTool(name, given) {
  const runnable = (place) => {
    try { accessSync(place, constants.X_OK); return true; } catch { return false; }
  };
  if (given) {
    if (!runnable(given)) throw new Error(`${given} is not a program that can be run.`);
    return given;
  }
  const candidates = [...String(process.env.PATH ?? '').split(delimiter).filter(Boolean).map((dir) => join(dir, name)),
    ...(PLACES[name] ?? [])];
  return candidates.find(runnable) ?? null;
}

function run(tool, args, what) {
  const done = spawnSync(tool, args, { encoding: 'utf8', timeout: WAIT });
  if (done.error || done.status !== 0) {
    const said = String(done.stderr || done.stdout || done.error?.message || '').trim().split('\n')
      .filter((line) => !/^Fontconfig/.test(line)).pop();
    const how = done.error ? '' : ` (exit ${done.status})`;
    throw new Error(`${what} failed${how}${said ? `: ${said}` : ''}.`);
  }
  return done.stdout;
}

/** A renderer for drawPreviews, with LibreOffice, pdftoppm and (when found) pdfinfo. */
export function libreOfficeRenderer({ soffice, pdftoppm, pdfinfo } = {}) {
  const office = findTool('soffice', soffice);
  const raster = findTool('pdftoppm', pdftoppm);
  if (!office || !raster) {
    throw new Error('Previews need LibreOffice (soffice) and Poppler (pdftoppm). Install them, or give --soffice and --pdftoppm.');
  }
  const info = findTool('pdfinfo', pdfinfo);
  return (template, pages, visible) => {
    const work = mkdtempSync(join(tmpdir(), 'harness-brand-previews-'));
    try {
      run(office, [`-env:UserInstallation=file://${join(work, 'profile')}`, '--headless', '--convert-to', 'pdf',
        '--outdir', work, template], 'LibreOffice');
      const pdf = join(work, template.split(/[\\/]/).pop().replace(/\.[^.]+$/, '.pdf'));
      if (!existsSync(pdf)) throw new Error('LibreOffice made no PDF of the template.');
      if (info) {
        const count = Number(/^Pages:\s+(\d+)/m.exec(run(info, [pdf], 'pdfinfo'))?.[1]);
        if (count !== visible) {
          throw new Error(`LibreOffice drew ${count} pages but the template has ${visible} visible slides, so pages and slides would not match.`);
        }
      }
      const drawn = new Map();
      for (const page of pages) {
        const stem = join(work, `page-${page}`);
        run(raster, ['-f', String(page), '-l', String(page), '-singlefile', '-scale-to', '960', '-png', pdf, stem], 'pdftoppm');
        drawn.set(page, readFileSync(`${stem}.png`));
      }
      return drawn;
    } finally {
      rmSync(work, { recursive: true, force: true });
    }
  };
}

/** Draw the previews for one variant of the pack in `pack` with `render(template, pages,
 *  visibleSlides)`, which returns a Map of page number to PNG. Writes the pictures and the
 *  layouts' `preview` fields; returns {drawn, without}. */
export function drawPreviews(pack, variant, render) {
  const index = join(pack, 'layouts.json');
  if (!existsSync(index)) throw new Error(`${pack} has no layouts.json. Measure a template first with pack measure.`);
  const layouts = JSON.parse(readFileSync(index, 'utf8'));
  const measured = layouts.variants?.[variant];
  if (!measured) {
    throw new Error(`layouts.json has no variant ${variant}. Its variants are: ${Object.keys(layouts.variants ?? {}).join(', ') || 'none'}.`);
  }
  const template = join(pack, measured.template);
  if (!existsSync(template)) throw new Error(`${pack} has no ${measured.template}.`);
  const pages = [...new Set(measured.layouts.map((layout) => layout.renderPage).filter(Number.isInteger))].sort((a, b) => a - b);
  const visible = measured.slides.filter((slide) => !slide.hidden).length;
  const drawn = render(template, pages, visible);
  const folder = join(pack, 'previews', variant);
  mkdirSync(folder, { recursive: true });
  let count = 0;
  for (const layout of measured.layouts) {
    const picture = Number.isInteger(layout.renderPage) ? drawn.get(layout.renderPage) : null;
    if (!picture) { delete layout.preview; continue; }
    if (!picture.subarray(0, 8).equals(PNG)) throw new Error(`Page ${layout.renderPage} was not drawn as a PNG.`);
    const file = join(folder, `${layout.id}.png`);
    writeFileSync(`${file}.tmp`, picture);
    renameSync(`${file}.tmp`, file);
    layout.preview = `previews/${variant}/${layout.id}.png`;
    count += 1;
  }
  writeFileSync(`${index}.tmp`, readableJson(layouts));
  renameSync(`${index}.tmp`, index);
  return { drawn: count, without: measured.layouts.length - count };
}
```

- [ ] **Step 4: Run them to see them pass**

Run: `node --test tests/previews.test.mjs`
Expected: `# pass 3`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/pack/previews.mjs tests/previews.test.mjs
git commit -m "Draw layout previews with LibreOffice and Poppler"
```


---

### Task 7: The commands

**Files:**
- Create: `scripts/pack-brand.mjs`
- Modify: `scripts/pack.mjs`
- Modify: `tests/format-doc.test.mjs`
- Test: `tests/pack-brand.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/pack-brand.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeZip } from '../scripts/lib/zip.mjs';
import { makeTemplate } from './fixtures/template.mjs';

const COMMAND = fileURLToPath(new URL('../scripts/harness-brand.mjs', import.meta.url));
const run = (...args) => spawnSync(process.execPath, [COMMAND, ...args], { encoding: 'utf8' });

function place() {
  const root = mkdtempSync(join(tmpdir(), 'hb-pack-'));
  writeFileSync(join(root, 'template.pptx'), makeTemplate());
  writeFileSync(join(root, 'export.zip'), writeZip([['export/tokens.json', JSON.stringify({ name: 'Example Co',
    color: { themes: [{ id: 'light' }], tokens: [{ name: 'blue', value: '#005c8a' }] } })]]));
  return root;
}

test('pack tokens writes tokens.json, and will not replace it unless told to', () => {
  const root = place();
  const pack = join(root, 'example', 'pack');
  const done = run('pack', 'tokens', join(root, 'export.zip'), '--into', pack);
  assert.equal(done.status, 0, done.stderr);
  assert.match(done.stdout, /1 colours \(0 with a dark value\)/);
  assert.equal(JSON.parse(readFileSync(join(pack, 'tokens.json'), 'utf8')).colors[0].light, '#005c8a');
  const again = run('pack', 'tokens', join(root, 'export.zip'), '--into', pack);
  assert.equal(again.status, 1);
  assert.match(again.stderr, /already has a tokens\.json/);
  assert.equal(run('pack', 'tokens', join(root, 'export.zip'), '--into', pack, '--replace').status, 0);
});

test('pack measure copies the template and writes layouts.json, naming the masters it left out', () => {
  const root = place();
  const pack = join(root, 'example', 'pack');
  const done = run('pack', 'measure', join(root, 'template.pptx'), '--variant', 'light', '--into', pack);
  assert.equal(done.status, 0, done.stderr);
  assert.match(done.stdout, /as light: 960 × 540 pt, master 2, 3 layouts \(2 with an example slide\), 3 slides \(1 hidden\)/);
  assert.match(done.stdout, /Not measured: master 1 \(1 layouts, no slides\)\. Give --master to choose another\./);
  assert.deepEqual(readFileSync(join(pack, 'templates', 'light.pptx')), readFileSync(join(root, 'template.pptx')));
  const layouts = JSON.parse(readFileSync(join(pack, 'layouts.json'), 'utf8'));
  assert.equal(layouts.variants.light.layouts.length, 3);
  const again = run('pack', 'measure', join(root, 'template.pptx'), '--variant', 'light', '--into', pack);
  assert.equal(again.status, 1);
  assert.match(again.stderr, /already has templates\/light\.pptx\. Give --replace/);
  const json = run('pack', 'measure', join(root, 'template.pptx'), '--variant', 'light', '--into', pack, '--replace', '--json');
  assert.equal(JSON.parse(json.stdout).used, 2);
});

test('pack measure refuses what it cannot measure, and writes nothing', () => {
  const root = place();
  const pack = join(root, 'example', 'pack');
  const done = run('pack', 'measure', join(root, 'export.zip'), '--variant', 'light', '--into', pack);
  assert.equal(done.status, 1);
  assert.match(done.stderr, /not a PowerPoint presentation/);
  assert.ok(!existsSync(pack));
  assert.match(run('pack', 'measure', join(root, 'template.pptx'), '--into', pack).stderr, /Give --variant and --into/);
});

test('pack previews says what it needs when it cannot draw', () => {
  const root = place();
  const pack = join(root, 'example', 'pack');
  run('pack', 'measure', join(root, 'template.pptx'), '--variant', 'light', '--into', pack);
  writeFileSync(join(root, 'not-a-program'), 'text');
  const done = run('pack', 'previews', pack, '--variant', 'light', '--soffice', join(root, 'not-a-program'));
  assert.equal(done.status, 1);
  assert.match(done.stderr, /not-a-program is not a program that can be run/);
  assert.match(run('pack', 'previews', pack).stderr, /Give --variant/);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/pack-brand.test.mjs`
Expected: FAIL, 4 of 4: `pack tokens`, `pack measure` and `pack previews` are not pack commands yet.

- [ ] **Step 3: Write `scripts/pack-brand.mjs`**

```js
// harness-brand pack tokens | measure | previews: the commands that take the exact parts of a
// brand pack from its sources.
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { sourceFiles } from './lib/icons/sources.mjs';
import { readTokens } from './lib/pack/tokens.mjs';
import { measureTemplate, mergeLayouts } from './lib/pack/measure.mjs';
import { drawPreviews, libreOfficeRenderer } from './lib/pack/previews.mjs';
import { readableJson } from './lib/readable-json.mjs';

export const USAGE = [
  '  pack tokens <export> --into PACK [--replace] [--json]',
  '  pack measure <template.pptx> --variant V --into PACK [--master N] [--replace] [--json]',
  '  pack previews <pack> --variant V [--soffice PATH] [--pdftoppm PATH] [--pdfinfo PATH] [--json]',
].join('\n');

const json = (value) => `${JSON.stringify(value, null, 2)}\n`;   // for --json output

/** Write a file all at once: a reader never sees half of it. */
function put(file, data) {
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(`${file}.tmp`, data);
  renameSync(`${file}.tmp`, file);
}

function readJson(file) {
  try {
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch (error) {
    throw new Error(`${file} cannot be read as JSON (${error.message}). Nothing was written.`);
  }
}

export function tokens(args) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    into: { type: 'string' }, replace: { type: 'boolean', default: false }, json: { type: 'boolean', default: false } } });
  if (positionals.length !== 1) throw new Error('Name one design-system export: a ZIP archive, a folder or a tokens.json.');
  if (!values.into) throw new Error('Give --into, the pack folder.');
  const into = resolve(values.into);
  const target = join(into, 'tokens.json');
  if (existsSync(target) && !values.replace) throw new Error(`${into} already has a tokens.json. Give --replace to make it again.`);
  if (!existsSync(positionals[0])) throw new Error(`There is no export at ${positionals[0]}.`);
  const made = readTokens(sourceFiles(positionals[0]));
  put(target, readableJson(made));
  const dark = made.colors.filter((color) => color.dark).length;
  if (values.json) {
    console.log(json({ tokens: target, colors: made.colors.length, dark, styles: made.type.styles.length,
      spacing: made.spacing.length, radius: made.radius.length }).trimEnd());
    return 0;
  }
  console.log(`Wrote ${target}: ${made.colors.length} colours (${dark} with a dark value), `
    + `${made.type.styles.length} type styles, ${made.spacing.length} spacing and ${made.radius.length} radius tokens.`);
  return 0;
}

export function measure(args) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    variant: { type: 'string' }, into: { type: 'string' }, master: { type: 'string' },
    replace: { type: 'boolean', default: false }, json: { type: 'boolean', default: false } } });
  if (positionals.length !== 1) throw new Error('Name one PowerPoint template.');
  if (!values.variant || !values.into) throw new Error('Give --variant and --into.');
  if (!existsSync(positionals[0])) throw new Error(`There is no template at ${positionals[0]}.`);
  const into = resolve(values.into);
  const buffer = readFileSync(positionals[0]);
  const measured = measureTemplate(buffer, { variant: values.variant, master: values.master });
  const template = join(into, measured.template);
  if (existsSync(template) && !values.replace) {
    throw new Error(`${into} already has ${measured.template}. Give --replace to measure it again.`);
  }
  const index = join(into, 'layouts.json');
  const layouts = mergeLayouts(existsSync(index) ? readJson(index) : null, values.variant, measured);
  put(template, buffer);
  put(index, readableJson(layouts));
  const used = measured.layouts.filter((layout) => layout.used).length;
  const hidden = measured.slides.filter((slide) => slide.hidden).length;
  const others = measured.masters.filter((master) => master.part !== measured.master);
  if (values.json) {
    console.log(json({ layouts: index, template, variant: values.variant, canvas: measured.canvas, master: measured.master,
      measured: measured.layouts.length, used, slides: measured.slides.length, hidden, otherMasters: others }).trimEnd());
    return 0;
  }
  const chosen = measured.masters.find((master) => master.part === measured.master);
  console.log(`Measured ${basename(positionals[0])} as ${values.variant}: ${measured.canvas.width} × ${measured.canvas.height} pt, `
    + `master ${chosen.number}, ${measured.layouts.length} layouts (${used} with an example slide), `
    + `${measured.slides.length} slides${hidden ? ` (${hidden} hidden)` : ''}.`);
  if (others.length) {
    console.log(`  Not measured: ${others.map((master) => `master ${master.number} (${master.layouts} layouts, `
      + `${master.slides ? `${master.slides} slides` : 'no slides'})`).join(', ')}. Give --master to choose another.`);
  }
  console.log(`Wrote ${template} and ${index}.`);
  return 0;
}

export function previews(args) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    variant: { type: 'string' }, soffice: { type: 'string' }, pdftoppm: { type: 'string' }, pdfinfo: { type: 'string' },
    json: { type: 'boolean', default: false } } });
  if (positionals.length !== 1) throw new Error('Name one pack folder.');
  if (!values.variant) throw new Error('Give --variant.');
  const pack = resolve(positionals[0]);
  const render = libreOfficeRenderer({ soffice: values.soffice, pdftoppm: values.pdftoppm, pdfinfo: values.pdfinfo });
  const { drawn, without } = drawPreviews(pack, values.variant, render);
  if (values.json) {
    console.log(json({ previews: join(pack, 'previews', values.variant), drawn, without }).trimEnd());
    return 0;
  }
  console.log(`Drew ${drawn} layout previews in ${join(pack, 'previews', values.variant)}.`
    + `${without ? ` ${without} layouts have no example slide, so no preview.` : ''}`);
  return 0;
}
```

- [ ] **Step 4: Dispatch the commands from `scripts/pack.mjs`**

Below the line `import { readZip } from './lib/zip.mjs';` add:

```js
import { USAGE as BRAND_USAGE, measure, previews, tokens } from './pack-brand.mjs';
```

In `USAGE`, after the line `'  pack check <folder> [--json]',` add the line:

```js
  BRAND_USAGE,
```

In `main`, after `if (command === 'check') return check(rest);` add:

```js
  if (command === 'tokens') return tokens(rest);
  if (command === 'measure') return measure(rest);
  if (command === 'previews') return previews(rest);
```

- [ ] **Step 5: Keep the icon library document's option check to `pack icons`**

`USAGE` now lists the brand-pack commands too, whose options the icon library format does
not describe. In `tests/format-doc.test.mjs`, in the test 'the document names every option
of pack icons, and the numbers the check uses', replace

```js
  for (const option of new Set(USAGE.match(/--[a-z-]+/g))) {
```

with

```js
  const iconsUsage = USAGE.slice(USAGE.indexOf('pack icons'), USAGE.indexOf('pack check'));
  for (const option of new Set(iconsUsage.match(/--[a-z-]+/g))) {
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `node --test tests/pack-brand.test.mjs`, then `npm test`
Expected: `# pass 4`, then every test passing (`# fail 0`).

- [ ] **Step 7: Commit**

```bash
git add scripts/pack-brand.mjs scripts/pack.mjs tests/format-doc.test.mjs tests/pack-brand.test.mjs
git commit -m "Add pack tokens, pack measure and pack previews"
```

---

### Task 8: The brand pack format document

**Files:**
- Create: `docs/brand-pack-format.md`
- Test: `tests/brand-pack-format.test.mjs`

This is the written definition the person asked for: what is in a brand, how it is pointed
at, and what each file holds, so that a pack can be made by hand or by an assistant. Its
test keeps it in step with the code: every field `pack measure` and `pack tokens` write must
be shown and described, every option of the three commands named, and the examples complete
and consistent.

- [ ] **Step 1: Write the failing test**

`tests/brand-pack-format.test.mjs`:

````js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { USAGE } from '../scripts/pack-brand.mjs';
import { JUDGEMENT, measureTemplate } from '../scripts/lib/pack/measure.mjs';
import { readTokens } from '../scripts/lib/pack/tokens.mjs';
import { makeTemplate } from './fixtures/template.mjs';

const doc = readFileSync(new URL('../docs/brand-pack-format.md', import.meta.url), 'utf8');
const blocks = [...doc.matchAll(/```json\n([\s\S]*?)```/g)].map((m) => JSON.parse(m[1]));
const brand = blocks.find((block) => block.variants && block.aliases);
const layouts = blocks.find((block) => block.variants && !block.aliases && Object.values(block.variants)[0].layouts);
const directions = blocks.find((block) => block.house);
const tokens = blocks.find((block) => Array.isArray(block.colors));
const audit = blocks.find((block) => 'minTextPt' in block);
// A field named in the first column of a table row, alone or beside others.
const row = (field) => new RegExp(`^\\|[^|\\n]*\`${field.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\``, 'm').test(doc);

test('the document shows every pack file it describes as JSON', () => {
  assert.ok(brand && layouts && directions && tokens && audit);
  for (const file of ['brand.json', 'tokens.json', 'templates/<variant>.pptx', 'layouts.json', 'guide.md',
    'directions.json', 'audit.json', 'assets/']) {
    assert.ok(row(file), `the files table has no row for ${file}`);
  }
});

test('the brand.json example gives every required role and type style', () => {
  const variant = brand.variants[brand.defaultVariant];
  for (const role of ['canvasPrimary', 'canvasSecondary', 'inkPrimary', 'inkDeep', 'headingPrimary', 'accentAqua']) {
    assert.ok(variant.colors[role], `the example has no ${role}`);
    assert.ok(row(role), `the roles table has no row for ${role}`);
  }
  for (const style of ['title', 'body', 'bodyReference', 'label', 'caption', 'metric', 'quote']) {
    assert.ok(variant.slides.typography[style], `the example has no ${style} style`);
  }
  for (const field of Object.keys(brand)) assert.ok(row(field), `the brand.json table has no row for ${field}`);
  for (const field of Object.keys(variant.slides)) assert.ok(row(field), `the slides table has no row for ${field}`);
});

test('every field pack measure writes is shown and described', () => {
  const measured = measureTemplate(makeTemplate(), { variant: 'light' });
  const example = Object.values(layouts.variants)[0];
  for (const key of Object.keys(measured)) {
    assert.ok(key in example, `the layouts.json example has no ${key}`);
    assert.ok(row(key), `no row describes ${key}`);
  }
  const layoutKeys = new Set(measured.layouts.flatMap((layout) => Object.keys(layout)));
  for (const key of [...layoutKeys, ...JUDGEMENT]) {
    assert.ok(doc.includes(`\`${key}\``), `the layout tables do not mention ${key}`);
  }
});

test('every field pack tokens writes is described', () => {
  const made = readTokens(new Map([['tokens.json', Buffer.from(JSON.stringify({ name: 'X',
    color: { tokens: [{ name: 'a', value: '#000000' }] }, gradient: {} }))]]));
  for (const key of Object.keys(made)) assert.ok(row(key), `the tokens.json table has no row for ${key}`);
  assert.equal(tokens.schema, 1);
});

test('the directions example holds together, and every audit field is described', () => {
  const variant = Object.values(directions.variants)[0];
  assert.ok(variant.directions.some((direction) => direction.id === variant.default));
  const ids = new Set(Object.values(layouts.variants)[0].layouts.map((layout) => layout.id));
  for (const direction of variant.directions) {
    for (const id of Object.values(direction.layouts)) assert.ok(ids.has(id), `${id} is not a layout in the example`);
  }
  for (const key of Object.keys(audit)) assert.ok(row(key), `the audit.json table has no row for ${key}`);
});

test('the document names every option of the pack commands it describes', () => {
  for (const option of new Set(USAGE.match(/--[a-z-]+/g))) {
    assert.match(doc, new RegExp(`${option}(?![a-z-])`), `the document does not mention ${option}`);
  }
});
````

- [ ] **Step 2: Run it to see it fail**

Run: `node --test tests/brand-pack-format.test.mjs`
Expected: FAIL, `ENOENT` for `docs/brand-pack-format.md`.

- [ ] **Step 3: Write `docs/brand-pack-format.md`**

````markdown
# Brand pack format

A brand pack is everything Harness Brand knows about one brand: its colours and type, its
PowerPoint template and what each layout is for, its rules and voice, the deck directions it
offers, and the limits its brand check holds a deck to. Harness Brand reads packs; it never
changes them. A pack is made from the brand's own source files: the exact parts by
`harness-brand pack` commands, the rest by a person or an assistant, following this
document. Anyone can make one by hand.

Icons are kept apart, in icon libraries that any brand may use: see
[icon-library-format.md](icon-library-format.md).

## Where a pack lives

```
brands/
  <id>/
    sources/            what the pack was made from, kept by you as received
    pack/               the pack: the files below
  icon-libraries/       reserved by Harness Brand, never a brand id
```

`<id>` is lower-case letters, digits and hyphens, starting with a letter, such as `tanzu`
or `vmware`. `brands/` sits at the root of the team's repository, or in the studios' local
folder when they keep their work locally.

## The files

| File | Required | What it holds | Made by |
|---|---|---|---|
| `brand.json` | yes | who the brand is, its variants, which colour does which job, its slide geometry and type, its icons and language | a person or an assistant |
| `tokens.json` | yes | every colour with its light and dark value, the type styles, spacing and radius | `pack tokens`, or by hand |
| `templates/<variant>.pptx` | for slides | the brand's PowerPoint template, as received | `pack measure` copies it |
| `layouts.json` | for slides | each template layout as measured, and what each is for | `pack measure`, then a person or an assistant |
| `previews/<variant>/<layout>.png` | no | a picture of each layout | `pack previews` |
| `guide.md` | yes | the brand's rules, voice and naming, in plain words | a person or an assistant |
| `directions.json` | for slides | the deck directions the brand offers | a person or an assistant |
| `audit.json` | yes | the limits the brand check holds a deck to | a person or an assistant |
| `assets/` | yes | the logos, and any art `brand.json` names | copied from the sources |
| `compositions/` | no | authored example slides | a person or an assistant |

A brand without templates is a brand for blogs and other writing only: it has no `slides`
in `brand.json`, no `layouts.json` and no `directions.json`.

Every path a pack file gives is inside the pack, written with `/`, such as
`templates/light.pptx`.

## brand.json

```json
{
  "schema": 1,
  "id": "example",
  "name": "Example Co",
  "aliases": ["example", "example co", "exco"],
  "defaultVariant": "light",
  "fonts": { "sans": "Arial", "mono": "Courier New" },
  "variants": {
    "light": {
      "theme": "light",
      "colors": {
        "canvasPrimary": "white", "canvasSecondary": "mist", "inkPrimary": "black", "inkDeep": "black",
        "inkSecondary": "dark-gray", "headingPrimary": "blue", "accentAqua": "aqua", "onAccent": "white",
        "statusCritical": "red"
      },
      "slides": {
        "template": "templates/light.pptx",
        "layout": "light-layout-002",
        "canvas": { "width": 960, "height": 540 },
        "titleBox": { "x": 48, "y": 36, "width": 864, "height": 60 },
        "contentBox": { "x": 48, "y": 120, "width": 864, "height": 360 },
        "reservedBottom": 492,
        "spacing": { "inset": 16, "column": 28 },
        "typography": {
          "title": { "size": 28, "bold": false, "colorRole": "headingPrimary" },
          "section": { "size": 40, "bold": false, "colorRole": "headingPrimary" },
          "body": { "size": 24, "bold": false, "colorRole": "inkDeep" },
          "bodyReference": { "size": 20, "bold": false, "colorRole": "inkDeep" },
          "label": { "size": 20, "bold": true, "colorRole": "inkDeep" },
          "caption": { "size": 14, "bold": false, "colorRole": "inkSecondary" },
          "metric": { "size": 60, "bold": false, "colorRole": "accentAqua" },
          "quote": { "size": 30, "bold": false, "colorRole": "inkDeep" }
        },
        "chart": { "seriesRoles": ["headingPrimary", "accentAqua"], "axisFontPt": 14 },
        "table": { "headerFillRole": "headingPrimary", "headerTextRole": "onAccent", "fontPt": 16, "paddingPt": 6 },
        "icon": { "size": 48, "colorRole": "headingPrimary" }
      }
    }
  },
  "icons": [{ "library": "vmware-functional", "default": true, "roles": ["headingPrimary", "accentAqua", "inkDeep"] }],
  "logos": { "onLight": "assets/logo-on-light.svg", "onDark": "assets/logo-on-dark.svg" },
  "language": {
    "headlineCase": "sentence",
    "preserveProductNamesAndAcronyms": true,
    "names": ["Write Example Co in full, never ExCo.", "Example Platform is a product: keep its capitals."]
  }
}
```

| Field | Required | Meaning |
|---|---|---|
| `schema` | yes | `1` |
| `id` | yes | the brand's folder name |
| `name` | yes | the brand's name, for people |
| `aliases` | yes | the words a request may use for the brand, in lower case |
| `defaultVariant` | yes | the variant used when a request names none |
| `fonts` | yes | `sans`: the font every slide and page is set in; `mono`: the font for code (Courier New if not given) |
| `variants` | yes | one entry per variant, such as `light` and `dark` (below) |
| `icons` | no | the icon libraries the brand uses: `library` (its id), `default` (searched first), `roles` (the colour roles a glyph may be drawn in) |
| `logos` | yes | `onLight` and `onDark`: the logo files in `assets/` for light and dark grounds |
| `language` | no | `headlineCase` (`sentence` or `title`), `preserveProductNamesAndAcronyms` (true or false), `names` (a list of naming rules, each a sentence) |
| `visual` | no | anything more the brand's contract should carry, as it is: `geometry`, `imagery`, `accessibility`, `colorPolicy`, `emphasis` |
| `files` | no | each pack file's SHA-256, written when the pack is sealed |
| `sources` | no | each source file's name and SHA-256, written when the pack is sealed |

### A variant

| Field | Required | Meaning |
|---|---|---|
| `theme` | yes | which values of `tokens.json` the variant takes: `light` or `dark` |
| `colors` | yes | each colour role (below) and the `tokens.json` colour that plays it |
| `slides` | for slides | the variant's slides (below) |

### Colour roles

A role names a job, and the variant says which colour does it. Every role must name a
colour in `tokens.json` whose value for the variant's theme is a plain `#rrggbb` colour.

| Role | Required | Its job |
|---|---|---|
| `canvasPrimary` | yes | the slide or page ground |
| `canvasSecondary` | yes | a quieter ground, for panels and supporting cards |
| `inkPrimary` | yes | body text on `canvasPrimary` |
| `inkDeep` | yes | the strongest text colour |
| `headingPrimary` | yes | titles and headings |
| `accentAqua` | yes | the brand's main supporting accent, whatever its hue (Harness Slides calls it so) |
| `inkSecondary` | no | captions and quieter text |
| `onAccent` | no | text on an accent fill |
| `statusCritical`, `statusAttention` | no | warnings and alerts |
| any name starting `accent` | no | further accents, offered as supporting fills |

Any other role name may be added and used in `slides`, `icons` and `directions.json`.
`inkPrimary`, `inkDeep`, `headingPrimary`, `inkSecondary` and every role used as a text
colour must reach a contrast of 4.5 to 1 against `canvasPrimary`.

### A variant's slides

| Field | Required | Meaning |
|---|---|---|
| `template` | yes | the variant's template, `templates/<variant>.pptx` |
| `layout` | yes | the id (from `layouts.json`) of the layout new content slides are built on |
| `canvas` | yes | `width` and `height` of the slide, in points |
| `titleBox`, `contentBox` | yes | `x`, `y`, `width`, `height` in points: where the title and the content go, inside the canvas |
| `reservedBottom` | no | the height in points below which content never goes (footers, logos); at least the content box's bottom |
| `spacing` | no | `inset` (inside a card, 16 if not given) and `column` (between columns, 28), in points |
| `typography` | yes | `title`, `body`, `bodyReference`, `label`, `caption`, `metric`, `quote`, and optionally `section`: each `size` (points, 1 to 120), `bold` (true or false) and `colorRole` |
| `chart` | yes | `seriesRoles` (the colour roles of chart series, in order) and optionally `axisFontPt` |
| `table` | yes | `headerFillRole`, `headerTextRole`, and optionally `fontPt` and `paddingPt` |
| `icon` | yes | `size` in points and the `colorRole` icons are drawn in |

`body` is the body text size for a deck that will be presented; `bodyReference` for one that
will be read.

## tokens.json

Written by `harness-brand pack tokens` from a Claude Design export, or by hand.

```json
{
  "schema": 1,
  "name": "Example Co",
  "themes": ["light", "dark"],
  "colors": [
    { "name": "blue", "light": "#005c8a", "dark": "#0088ef", "usage": "Headings and key marks." },
    { "name": "white", "light": "#ffffff", "usage": "The slide ground." }
  ],
  "type": {
    "families": { "sans": "Arial, Helvetica, sans-serif" },
    "styles": [{ "name": "title", "group": "Titles", "fontSize": "36px", "lineHeight": "39px", "fontWeight": 400 }]
  },
  "spacing": [{ "name": "space-margin", "value": "48px" }],
  "radius": [{ "name": "radius-none", "value": "0" }]
}
```

| Field | Required | Meaning |
|---|---|---|
| `schema` | yes | `1` |
| `name` | yes | the design system's name |
| `themes` | yes | the themes it has, such as `light` and `dark` |
| `colors` | yes | each colour: `name`, `light` (its value in the light theme), `dark` (in the dark theme, when it differs), `usage` |
| `type` | no | `families` (font stacks by name) and `styles` (each with its `name`, `group` and values as the source gives them) |
| `spacing`, `radius` | no | each `name`, `value` and `usage` |
| `other` | no | any other groups of tokens, kept as the source gives them |
| `source` | no | where the tokens came from |

A colour with no `light` value exists only in the dark theme. Values are `#rrggbb` wherever
the source gives a plain colour, else kept as given.

## templates and layouts.json

`harness-brand pack measure` copies a template to `templates/<variant>.pptx` and writes what
it measures into `layouts.json`, under the variant. It measures the master the template's
visible slides use (or the one given with `--master`) and every layout of that master.
Sizes are in points.

```json
{
  "schema": 1,
  "variants": {
    "light": {
      "template": "templates/light.pptx",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
      "canvas": { "width": 960, "height": 540 },
      "master": "ppt/slideMasters/slideMaster1.xml",
      "masters": [{ "number": 1, "part": "ppt/slideMasters/slideMaster1.xml", "layouts": 2, "slides": 1 }],
      "theme": { "part": "ppt/theme/theme1.xml", "colors": { "dk1": "#000000", "lt1": "#ffffff" }, "fonts": { "major": "Arial", "minor": "Arial" } },
      "masterArtwork": [{ "id": "5", "kind": "sp", "bounds": [0, 0, 960, 6] }],
      "layouts": [
        {
          "id": "light-layout-001",
          "name": "Title Only",
          "part": "ppt/slideLayouts/slideLayout1.xml",
          "used": true,
          "slide": 1,
          "renderPage": 1,
          "placeholders": [{ "id": "2", "type": "title", "bounds": [48, 36, 864, 60], "size": 28, "bold": false, "font": "Arial", "color": { "scheme": "tx1", "hex": "#000000" } }],
          "artwork": [{ "id": "7", "kind": "pic", "bounds": [880, 500, 60, 24] }],
          "preview": "previews/light/light-layout-001.png",
          "relationship": "statement",
          "contentRange": { "maxWords": 35, "minItems": 1, "maxItems": 1 },
          "components": ["title", "body"],
          "searchTerms": ["one idea", "a key message"],
          "delivery": ["live", "reading"],
          "searchable": true
        }
      ],
      "slides": [{ "slide": 1, "hidden": false, "renderPage": 1, "layout": "light-layout-001" }]
    }
  }
}
```

What `pack measure` writes for a variant:

| Field | Meaning |
|---|---|
| `template`, `sha256` | the template file and its SHA-256 |
| `canvas` | the slide size |
| `master`, `masters` | the master measured, and every master with its count of layouts and of visible slides |
| `theme` | the master's theme: its colours by name (`dk1`, `lt1`, `accent1` and so on) and its fonts |
| `masterArtwork` | the master's shapes that are not content placeholders |
| `layouts` | each layout of the master (below) |
| `slides` | each slide: its number, whether it is hidden, its page among the visible slides, its layout's id |

And for each layout:

| Field | Meaning |
|---|---|
| `id` | `<variant>-layout-<NNN>`, numbered in the master's order |
| `name`, `rawName` | the layout's name tidied, and as written when that differs |
| `part`, `type` | where it is in the template, and its PowerPoint layout type when it has one |
| `used`, `slide`, `renderPage` | whether a visible slide uses it, and the first such slide and its page |
| `showsMasterArtwork` | `false` when the layout hides the master's shapes |
| `placeholders` | each content placeholder: `id`, `type`, `idx`, `bounds` (`[x, y, width, height]`), `rotation`, `flipH`, `flipV`, `inherited` (its frame comes from the master), and the text it shows: `size`, `bold`, `font`, `color` |
| `artwork` | every other shape, including slide numbers, dates and footers: `id`, `kind`, `placeholder` (for those), `bounds`, `rotation`, `flipH`, `flipV` |
| `preview` | written by `pack previews`: the layout's picture |

What a person or an assistant adds to a layout, kept when the template is measured again:

| Field | Meaning |
|---|---|
| `relationship` | what the layout shows, in a word or two, such as `opening`, `statement`, `agenda`, `section`, `comparison`, `sequence`, `list`, `grid`, `metric`, `quote`, `image`, `chart`, `table`, `closing`, `thanks` |
| `contentRange` | `maxWords`, `minItems`, `maxItems`: how much the layout holds comfortably |
| `components` | the parts it is built from, such as `title`, `body`, `metric`, `icon`, `image` |
| `searchTerms` | phrases a request might use that this layout answers |
| `delivery` | `live`, `reading` or both: the decks it suits |
| `searchable` | `false` to keep the layout out of searches (it can still be named by id) |
| `notes` | anything more a slide builder should know |

## guide.md

The brand's rules in plain words, read by people and by the assistant that builds slides.
It has these sections, each a level-two heading:

- `## Brand rules`: what the brand always and never does, from its brand book.
- `## Voice and naming`: how the brand writes, and how its organisation and products are named.
- `## Slides` (for slides): how the brand's slides are built: recipes, and what to avoid.

Each rule says where it comes from (the brand book, a template, a guide), quoted where it
can be.

## directions.json

The deck directions a brand offers: ready-made choices of which colour leads and what
colours mean, from which a deck's look is picked.

```json
{
  "schema": 1,
  "house": ["Fill cards: a supporting card is a solid neutral box.", "Use one approved icon for each concrete idea."],
  "variants": {
    "light": {
      "default": "example-clear",
      "closing": {
        "withWords": { "layout": "light-layout-001", "title": true, "subtitles": 0, "use": "A closing whose words matter." }
      },
      "directions": [
        {
          "id": "example-clear",
          "name": "Clear",
          "useWhen": "Most decks: one product explained.",
          "direction": {
            "focal": "headingPrimary",
            "neutral": "canvasSecondary",
            "meanings": { "accentAqua": "Example Platform: the product this deck is about" },
            "motif": "A strip on each card says what it is about."
          },
          "layouts": { "cover": "light-layout-001", "section": "light-layout-001", "closing": "light-layout-001" }
        }
      ]
    }
  }
}
```

| Field | Required | Meaning |
|---|---|---|
| `schema` | yes | `1` |
| `house` | yes | rules every deck follows, each a sentence |
| `variants` | yes | for each variant with slides: its directions (below) |

For each variant:

| Field | Required | Meaning |
|---|---|---|
| `default` | yes | the id of the direction used when none is chosen |
| `directions` | yes | the directions (below), at least one |
| `closing` | yes | `withWords` (a closing slide with a message) and optionally `thanks` (one that only thanks): each `layout` (an id from `layouts.json`), `title` (true or false), `subtitles` (how many), `use` |
| `reservedRoles` | no | colour roles a direction may not use as its focal colour or a meaning |
| `stripOnly` | no | `roles` that may only be used as a thin strip, and `why` |

For each direction:

| Field | Required | Meaning |
|---|---|---|
| `id`, `name` | yes | its id (unique in the pack) and its name, for people |
| `useWhen` | yes | when to choose it, in a sentence |
| `direction` | yes | `focal` (the role that leads), `neutral` (the role for supporting fills), `meanings` (roles that stand for one thing in a deck, each with what it stands for) and `motif` (the deck's recurring device, at most 200 characters) |
| `layouts` | yes | the layout ids for `cover`, `section` and `closing`, and optionally `thanks` |
| `cues` | no | for a meaning's role, words that mark a point as standing for that meaning |

A direction's roles must be the variant's colour roles. `focal` and `neutral` differ,
`neutral` is not `canvasPrimary`, and `neutral` reaches 4.5 to 1 against `inkDeep`. A
meaning's role is neither the focal nor the neutral one, no two meanings share a colour, and
text on a focal or meaning colour can reach 4.5 to 1 in `onAccent`, `canvasPrimary` or
`inkDeep`.

## audit.json

The limits the brand check holds a deck to. Any field left out takes the value shown.

```json
{
  "schema": 1,
  "minTextPt": 18,
  "maxWords": 60,
  "textLedWords": 45,
  "overlapRatio": 0.1,
  "outOfBoundsInches": 0.02,
  "contrast": { "normal": 4.5, "large": 3 },
  "tolerances": { "titlePositionPt": 5, "fontPt": 1, "iconSizePt": 4 },
  "consistency": { "minimumSlides": 3, "majorityFraction": 0.6 },
  "starterText": ["click to add", "click to edit", "lorem ipsum"]
}
```

| Field | Meaning |
|---|---|
| `schema` | `1` (required) |
| `minTextPt` | the smallest size for main text; captions may go down to the caption size in `brand.json` |
| `maxWords` | the most words on a slide |
| `textLedWords` | words beyond which a slide with no picture, chart, table or diagram is flagged |
| `overlapRatio` | how much two text boxes may overlap, as a share of the smaller |
| `outOfBoundsInches` | how far a shape may stray past the slide's edge |
| `contrast` | the least contrast for `normal` text and for `large` text (18 points, or 14 bold) |
| `tolerances` | how far titles, text sizes and icon sizes may drift between slides before it is flagged |
| `consistency` | `minimumSlides` (how many slides of a kind before drift is checked) and `majorityFraction` (the share that sets what is normal) |
| `fonts` | the fonts allowed (the `sans` and `mono` fonts of `brand.json` if not given) |
| `starterText` | words that, left on a slide, block it: template text never replaced |

## assets, previews and compositions

`assets/` holds the logos `brand.json` names and any art the brand's rules call for,
copied from the sources. `previews/` is written by `pack previews`. `compositions/` holds
authored example slides when a brand has them: `compositions.pptx`, and
`compositions.json` in the shape of a variant in `layouts.json`.

## Making a pack

The exact parts come from commands:

```bash
harness-brand pack tokens <export> --into brands/<id>/pack [--replace] [--json]
harness-brand pack measure <template.pptx> --variant V --into brands/<id>/pack [--master N] [--replace] [--json]
harness-brand pack previews brands/<id>/pack --variant V [--soffice PATH] [--pdftoppm PATH] [--pdfinfo PATH] [--json]
```

- `pack tokens` reads a Claude Design export (a ZIP archive or a folder holding
  `tokens.json`, with dark values from `tokens.css` beside it) and writes `tokens.json`.
  Colours `tokens.css` names that `tokens.json` does not, such as `surface`, are added.
- `pack measure` copies the template and measures it into `layouts.json`. It measures the
  master most visible slides use and names the others it left out; `--master` chooses
  another by number or part. Measuring again keeps what was added to each layout, and its
  preview while the template is unchanged.
- `pack previews` draws each layout that a visible slide uses, with LibreOffice (`soffice`)
  and Poppler (`pdftoppm`, and `pdfinfo` to check the pages). A layout no visible slide uses
  has no preview.

Each refuses to replace what is there unless given `--replace` (`pack previews` always
draws afresh), and a command that is refused writes nothing.
````

- [ ] **Step 4: Run it to see it pass**

Run: `node --test tests/brand-pack-format.test.mjs`, then `npm test`
Expected: `# pass 6`, then `# tests 142`, `# pass 142`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add docs/brand-pack-format.md tests/brand-pack-format.test.mjs
git commit -m "Write down the brand pack format"
```

---

### Task 9: Run it on the real sources and review the previews

This builds the exact parts of the three packs in a scratch folder, outside the repository,
for the person to look at. The packs are finished in Plan 4.

**Files:** none in the repository.

- [ ] **Step 1: Tokens from the three exports**

```bash
cd ~/Projects/harness-brand-skill
P=/tmp/harness-brand-packs
node scripts/harness-brand.mjs pack tokens tanzu-division-design-system.zip --into $P/tanzu/pack --replace
node scripts/harness-brand.mjs pack tokens vmware-by-broadcom-design-system.zip --into $P/vmware/pack --replace
node scripts/harness-brand.mjs pack tokens broadcom-design-system.zip --into $P/broadcom/pack --replace
```

Expected, from the dry run on 3 November 2026, with every colour a `#rrggbb`:
- Tanzu Division: 32 colours (20 with a dark value).
- VMware by Broadcom: 35 (25).
- Broadcom: 50 (16).

- [ ] **Step 2: Measure the four templates**

```bash
T=~/Projects/tanzu-brand/assets/presentations
node scripts/harness-brand.mjs pack measure $T/tanzu-presentation-template.pptx --variant light --into $P/tanzu/pack --replace
node scripts/harness-brand.mjs pack measure $T/corporate/vmware-light-template.pptx --variant light --into $P/vmware/pack --replace
node scripts/harness-brand.mjs pack measure $T/corporate/vmware-dark-template.pptx --variant dark --into $P/vmware/pack --replace
node scripts/harness-brand.mjs pack measure $T/corporate/broadcom-template.pptx --variant light --into $P/broadcom/pack --replace
```

Expected, matching Tanzu Brand's own catalogues:
- Tanzu Division: master 2 of 3, 43 layouts (34 with an example slide), 35 slides, with
  masters 1 and 3 named as not measured.
- VMware by Broadcom: light 43 (40), dark 43 (38), 41 slides each.
- Broadcom: 23 layouts (20), 36 slides (1 hidden).

Every content placeholder has `bounds` and a `size`.

- [ ] **Step 3: Draw the previews**

LibreOffice must be able to run. In a sandboxed agent session, run these outside the
sandbox, with the absolute folder (not `$TMPDIR`, which differs inside and outside).

```bash
node scripts/harness-brand.mjs pack previews $P/tanzu/pack --variant light
node scripts/harness-brand.mjs pack previews $P/vmware/pack --variant light
node scripts/harness-brand.mjs pack previews $P/vmware/pack --variant dark
node scripts/harness-brand.mjs pack previews $P/broadcom/pack --variant light
```

Expected, in about 5 to 12 seconds each:

| Pack | Previews | Layouts with none |
|---|---|---|
| Tanzu Division | 34 | 9 |
| VMware by Broadcom light | 40 | 3 |
| VMware by Broadcom dark | 38 | 5 |
| Broadcom | 20 | 3 |

A page-count mismatch would be refused, so a success means the pages matched the visible
slides, including after Broadcom's hidden slide 25.

- [ ] **Step 4: Have the person look at the previews**

Show the person a few previews from each pack, for example the cover, a content layout and
a closing layout. Include Broadcom's `light-layout-016` ("Closing 1 - dark", drawn from
slide 31, after the hidden slide), to confirm that pages and layouts line up. Report the
counts from Steps 1 to 3.

---

### Task 10: Finish

- [ ] **Step 1: Run the whole suite once more**

Run: `npm test`
Expected: `# fail 0`.

- [ ] **Step 2: Show the branch**

```bash
git log --oneline main..HEAD
git status --short
```

Expected: the commits from Tasks 2 to 8, and a clean tree. Do not push. Tell the person:
- the branch name;
- what the previews showed;
- that Plan 3 (checking and authoring) is next.
