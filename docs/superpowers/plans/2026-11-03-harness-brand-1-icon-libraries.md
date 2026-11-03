# Harness Brand, Plan 1: foundations and icon libraries

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harness Brand's first working piece: `harness-brand pack icons` builds a shared icon library (`library.zip`) from Claude Design exports, SVG folders or an `icons.json`, and `harness-brand pack check` checks one, so the `vmware-functional` library can be built and reviewed.

**Architecture:** A Node 20 command, `scripts/harness-brand.mjs`, in `dbbaskette/harness-brand-skill`, with no npm packages. Small focused modules: ZIP reading and writing on `node:zlib`, a minimal XML parser, SVG path geometry, SVG-to-glyph conversion, source reading, library building and checking, and a contact sheet. Spec: `docs/superpowers/specs/2026-11-03-harness-brand-design.md` in marketing-studio (sections 2 "Icon libraries" and 3).

**Tech Stack:** Node.js 20 or newer (`node:zlib`, `node:fs`, `node:util` `parseArgs`, `node:test`, `node:assert/strict`); `npm test` runs `node --test`, which finds every `*.test.mjs`. No dependencies.

---

## Roadmap: the plans for Harness Brand

Each plan ends in working, tested software and is written when the one before it has
landed, from what that one taught.

1. **Foundations and icon libraries** (this plan): ZIP, XML, SVG geometry, `pack icons`,
   `pack check` for libraries, the icon library format document, the `vmware-functional`
   library built and reviewed from the three exports.
2. **Brand pack commands:** `pack tokens`, `pack measure`, `pack scaffold`, `pack
   previews`, `pack check` for packs, `pack seal`; `docs/brand-pack-format.md`;
   `references/building-a-pack.md`; the Example Co fixture pack.
3. **The three packs:** Tanzu Division, VMware by Broadcom and Broadcom built from their
   sources with the commands and the guide, reviewed by the person; placed with
   `vmware-functional` in `brands/` of tanzu-marketing-hub after the person's yes.
4. **The worker:** `version`, `brands`, `contract`, `layouts`, `icons`, `presentation`,
   `doctor`, `guidance`, `look`, `restyle`; the installers; release packaging; apply-brand
   and the design-system zips removed from the repository.
5. **Marketing Studio, data folder:** `HARNESS_BRAND_DATA` for every studio, the missing
   folder message, sync and sample configs and docs.
6. **Marketing Studio, Brands section.**
7. **Release 1.0.0:** tag, Mac archive and checksum, real-pack check in a disposable home.

## Where this plan's work happens

All code in this plan goes in the harness-brand-skill repository, at
`~/Projects/harness-brand-skill`, on a new branch. That folder is outside the
marketing-studio worktree, so a session running this plan works there (its own session
in that folder, or with the person's approval for each write). Commands below run from
`~/Projects/harness-brand-skill` unless they say otherwise. The design-system zips there
are read, never changed. Nothing is pushed in this plan.

## File structure

| File | Responsibility |
|---|---|
| `package.json` | name, version 0.1.0, Node 20, `npm test` |
| `scripts/harness-brand.mjs` | the command: usage, dispatch to `version` and `pack`, errors as sentences |
| `scripts/version.mjs` | `Harness Brand <version>` |
| `scripts/pack.mjs` | `pack icons` and `pack check` |
| `scripts/lib/zip.mjs` | read and write ZIP archives |
| `scripts/lib/xml.mjs` | parse XML into `{name, attrs, children, text}`; find helpers |
| `scripts/lib/svg-path.mjs` | SVG path data to absolute M, L, C, Z segments; transforms; bounds; formatting |
| `scripts/lib/icons/svg-glyph.mjs` | one SVG drawing to one glyph path in the 0 to 100 box, or why not |
| `scripts/lib/icons/sources.mjs` | a source (ZIP or folder) to an icon index or a list of SVG drawings |
| `scripts/lib/icons/library.mjs` | build, archive and check a library; slugs and categories |
| `scripts/lib/icons/contact-sheet.mjs` | an SVG sheet of every icon, for review |
| `docs/icon-library-format.md` | the format, for people and other tools |
| `tests/*.test.mjs` | one test file per module, plus the command |

---

### Task 1: Branch and package

**Files:**
- Create: `package.json`
- Create: `tests/package.test.mjs`

- [ ] **Step 1: Make the branch**

```bash
cd ~/Projects/harness-brand-skill
git switch main && git pull --ff-only && git switch -c harness-brand-foundations
```

Expected: `Switched to a new branch 'harness-brand-foundations'`.

- [ ] **Step 2: Write the failing test**

`tests/package.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('the package is Harness Brand on Node 20 with no dependencies', () => {
  const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
  assert.equal(pkg.name, 'harness-brand');
  assert.match(pkg.version, /^\d+\.\d+\.\d+$/);
  assert.equal(pkg.type, 'module');
  assert.equal(pkg.engines.node, '>=20.0.0');
  assert.equal(pkg.dependencies, undefined);
  assert.equal(pkg.devDependencies, undefined);
});
```

- [ ] **Step 3: Run it to see it fail**

Run: `node --test tests/package.test.mjs`
Expected: FAIL, `ENOENT` for `package.json`.

- [ ] **Step 4: Write `package.json`**

```json
{
  "name": "harness-brand",
  "version": "0.1.0",
  "description": "Harness Brand: brand packs and icon libraries for the studios' slides, blogs and infographics.",
  "private": true,
  "type": "module",
  "engines": {
    "node": ">=20.0.0"
  },
  "scripts": {
    "test": "node --test"
  }
}
```

- [ ] **Step 5: Run it to see it pass**

Run: `npm test`
Expected: `# pass 1`, `# fail 0`.

- [ ] **Step 6: Commit**

```bash
git add package.json tests/package.test.mjs
git commit -m "Start Harness Brand as a Node package with no dependencies"
```

---

### Task 2: ZIP archives

**Files:**
- Create: `scripts/lib/zip.mjs`
- Test: `tests/zip.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/zip.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { crc32, readZip, writeZip } from '../scripts/lib/zip.mjs';

test('crc32 matches the standard check value', () => {
  assert.equal(crc32(Buffer.from('123456789')), 0xcbf43926);
});

test('files written are read back unchanged', () => {
  const noise = randomBytes(2048);   // does not compress, so it is stored
  const archive = writeZip([['a.txt', 'hello '.repeat(200)], ['b/c.bin', noise]]);
  const files = readZip(archive);
  assert.deepEqual([...files.keys()], ['a.txt', 'b/c.bin']);
  assert.equal(files.get('a.txt').toString('utf8'), 'hello '.repeat(200));
  assert.deepEqual(files.get('b/c.bin'), noise);
});

test('the same files make the same archive', () => {
  const one = writeZip(new Map([['x.json', '{}\n']]));
  const two = writeZip(new Map([['x.json', '{}\n']]));
  assert.deepEqual(one, two);
});

test('something that is not an archive is refused', () => {
  assert.throws(() => readZip(Buffer.from('not a zip at all, clearly not')), /not a ZIP archive/);
});

test('a damaged file is refused', () => {
  const archive = writeZip([['a.txt', 'hello '.repeat(200)]]);
  archive[40] ^= 0xff;   // inside the first file's packed data
  assert.throws(() => readZip(archive), /a\.txt/);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/zip.test.mjs`
Expected: FAIL, cannot find module `../scripts/lib/zip.mjs`.

- [ ] **Step 3: Write `scripts/lib/zip.mjs`**

```js
// ZIP archives (PowerPoint files are ZIP archives too), with Node's own zlib.
import { deflateRawSync, inflateRawSync } from 'node:zlib';

const TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

export function crc32(bytes) {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i += 1) c = TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function endRecord(buffer) {
  for (let at = buffer.length - 22; at >= Math.max(0, buffer.length - 65557); at -= 1) {
    if (buffer.readUInt32LE(at) === 0x06054b50) return at;
  }
  throw new Error('It is not a ZIP archive.');
}

/** Every file in the archive, as a Map of name to Buffer. Folders are left out. */
export function readZip(buffer) {
  if (buffer.length < 22) throw new Error('It is not a ZIP archive.');
  const end = endRecord(buffer);
  const count = buffer.readUInt16LE(end + 10);
  let at = buffer.readUInt32LE(end + 16);
  const files = new Map();
  for (let n = 0; n < count; n += 1) {
    if (buffer.readUInt32LE(at) !== 0x02014b50) throw new Error('The ZIP archive is damaged.');
    const method = buffer.readUInt16LE(at + 10);
    const crc = buffer.readUInt32LE(at + 16);
    const packed = buffer.readUInt32LE(at + 20);
    const size = buffer.readUInt32LE(at + 24);
    const nameLength = buffer.readUInt16LE(at + 28);
    const extra = buffer.readUInt16LE(at + 30);
    const comment = buffer.readUInt16LE(at + 32);
    const local = buffer.readUInt32LE(at + 42);
    const name = buffer.toString('utf8', at + 46, at + 46 + nameLength);
    at += 46 + nameLength + extra + comment;
    if (name.endsWith('/')) continue;
    if (packed === 0xffffffff || size === 0xffffffff) throw new Error('ZIP64 archives are not read.');
    if (buffer.readUInt32LE(local) !== 0x04034b50) throw new Error('The ZIP archive is damaged.');
    const start = local + 30 + buffer.readUInt16LE(local + 26) + buffer.readUInt16LE(local + 28);
    const raw = buffer.subarray(start, start + packed);
    let data;
    try {
      if (method === 0) data = Buffer.from(raw);
      else if (method === 8) data = inflateRawSync(raw);
      else throw new Error(`it is packed in a way that is not read (method ${method})`);
    } catch (error) {
      throw new Error(`${name} cannot be unpacked: ${error.message}.`);
    }
    if (data.length !== size || crc32(data) !== crc) throw new Error(`${name} does not match its checksum.`);
    files.set(name, data);
  }
  return files;
}

// 1 January 1980 for every file, so the same files always make the same archive.
const TIME = 0;
const DATE = (1 << 5) | 1;
const UTF8 = 0x0800;

/** An archive of `files`: a Map or a list of [name, Buffer or text], in that order. */
export function writeZip(files) {
  const list = files instanceof Map ? [...files] : files;
  const parts = [];
  const directory = [];
  let offset = 0;
  for (const [name, content] of list) {
    const data = Buffer.isBuffer(content) ? content : Buffer.from(content, 'utf8');
    const packed = deflateRawSync(data);
    const stored = packed.length >= data.length;
    const body = stored ? data : packed;
    const method = stored ? 0 : 8;
    const nameBytes = Buffer.from(name, 'utf8');
    const crc = crc32(data);
    const header = Buffer.alloc(30);
    header.writeUInt32LE(0x04034b50, 0);
    header.writeUInt16LE(20, 4);
    header.writeUInt16LE(UTF8, 6);
    header.writeUInt16LE(method, 8);
    header.writeUInt16LE(TIME, 10);
    header.writeUInt16LE(DATE, 12);
    header.writeUInt32LE(crc, 14);
    header.writeUInt32LE(body.length, 18);
    header.writeUInt32LE(data.length, 22);
    header.writeUInt16LE(nameBytes.length, 26);
    const entry = Buffer.alloc(46);
    entry.writeUInt32LE(0x02014b50, 0);
    entry.writeUInt16LE(20, 4);
    entry.writeUInt16LE(20, 6);
    entry.writeUInt16LE(UTF8, 8);
    entry.writeUInt16LE(method, 10);
    entry.writeUInt16LE(TIME, 12);
    entry.writeUInt16LE(DATE, 14);
    entry.writeUInt32LE(crc, 16);
    entry.writeUInt32LE(body.length, 20);
    entry.writeUInt32LE(data.length, 24);
    entry.writeUInt16LE(nameBytes.length, 28);
    entry.writeUInt32LE(offset, 42);
    parts.push(header, nameBytes, body);
    directory.push(entry, nameBytes);
    offset += 30 + nameBytes.length + body.length;
  }
  const central = Buffer.concat(directory);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(list.length, 8);
  end.writeUInt16LE(list.length, 10);
  end.writeUInt32LE(central.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...parts, central, end]);
}
```

- [ ] **Step 4: Run them to see them pass**

Run: `node --test tests/zip.test.mjs`
Expected: `# pass 5`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/zip.mjs tests/zip.test.mjs
git commit -m "Read and write ZIP archives with Node's own zlib"
```

---

### Task 3: XML

**Files:**
- Create: `scripts/lib/xml.mjs`
- Test: `tests/xml.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/xml.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { all, kid, kids, parseXml, path } from '../scripts/lib/xml.mjs';

test('elements, attributes, text and entities are read', () => {
  const root = parseXml(`<?xml version="1.0"?>
    <!-- a comment -->
    <p:sld xmlns:p="urn:p" a='1' b="x &amp; y">
      <p:t>Fish &lt;&amp;&gt; chips &#x41;&#66;</p:t>
      <p:empty/>
      <p:raw><![CDATA[<kept>]]></p:raw>
    </p:sld>`);
  assert.equal(root.name, 'p:sld');
  assert.deepEqual(root.attrs, { 'xmlns:p': 'urn:p', a: '1', b: 'x & y' });
  assert.equal(kid(root, 'p:t').text, 'Fish <&> chips AB');
  assert.deepEqual(kid(root, 'p:empty').children, []);
  assert.equal(kid(root, 'p:raw').text, '<kept>');
});

test('an attribute may hold a > inside its quotes', () => {
  assert.equal(parseXml('<a title="x > y"/>').attrs.title, 'x > y');
});

test('finding children and descendants', () => {
  const root = parseXml('<a><b><c id="1"/></b><b><c id="2"/><c id="3"/></b></a>');
  assert.equal(kids(root, 'b').length, 2);
  assert.equal(path(root, 'b/c').attrs.id, '1');
  assert.equal(path(root, 'b/x/c'), null);
  assert.deepEqual(all(root, 'c').map((c) => c.attrs.id), ['1', '2', '3']);
});

test('badly formed XML is refused', () => {
  assert.throws(() => parseXml('<a><b></a>'), /closes a where b is open/);
  assert.throws(() => parseXml('<a>'), /still open/);
  assert.throws(() => parseXml('<!DOCTYPE x><a/>'), /document type/);
  assert.throws(() => parseXml('just text'), /no element/);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/xml.test.mjs`
Expected: FAIL, cannot find module `../scripts/lib/xml.mjs`.

- [ ] **Step 3: Write `scripts/lib/xml.mjs`**

```js
// A small XML reader for Office and SVG files: elements, attributes and text. Document types
// are refused, so no entity is ever expanded beyond the five standard ones and numbers.
const ENTITIES = { lt: '<', gt: '>', amp: '&', quot: '"', apos: "'" };

export function decode(text) {
  return text.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (whole, name) => {
    if (name[0] !== '#') return ENTITIES[name] ?? whole;
    const hex = name[1] === 'x' || name[1] === 'X';
    return String.fromCodePoint(parseInt(name.slice(hex ? 2 : 1), hex ? 16 : 10));
  });
}

function closing(text, from, marker) {
  const at = text.indexOf(marker, from);
  if (at < 0) throw new Error(`The XML has no ${marker} to end what starts at ${from}.`);
  return at;
}

function endOfTag(text, open) {
  let quote = null;
  for (let i = open + 1; i < text.length; i += 1) {
    const ch = text[i];
    if (quote) { if (ch === quote) quote = null; }
    else if (ch === '"' || ch === "'") quote = ch;
    else if (ch === '>') return i;
  }
  throw new Error(`The XML tag at ${open} never ends.`);
}

function attributes(text) {
  const attrs = {};
  for (const [, name, , double, single] of text.matchAll(/([^\s=]+)\s*=\s*("([^"]*)"|'([^']*)')/g)) {
    attrs[name] = decode(double ?? single);
  }
  return attrs;
}

/** The document's root element: {name, attrs, children, text}, `text` being its own text. */
export function parseXml(text) {
  const document = { name: '#document', attrs: {}, children: [], text: '' };
  const stack = [document];
  let at = 0;
  while (at < text.length) {
    const open = text.indexOf('<', at);
    const top = stack[stack.length - 1];
    if (open < 0) { top.text += decode(text.slice(at)); break; }
    if (open > at) top.text += decode(text.slice(at, open));
    if (text.startsWith('<!--', open)) { at = closing(text, open, '-->') + 3; continue; }
    if (text.startsWith('<![CDATA[', open)) {
      const end = closing(text, open, ']]>');
      top.text += text.slice(open + 9, end);
      at = end + 3;
      continue;
    }
    if (text.startsWith('<?', open)) { at = closing(text, open, '?>') + 2; continue; }
    if (text.startsWith('<!', open)) throw new Error('XML with a document type is not read.');
    const end = endOfTag(text, open);
    const inner = text.slice(open + 1, end);
    at = end + 1;
    if (inner.startsWith('/')) {
      const name = inner.slice(1).trim();
      if (stack.length < 2 || top.name !== name) {
        throw new Error(`The XML closes ${name} where ${top.name} is open.`);
      }
      stack.pop();
      continue;
    }
    const empty = inner.endsWith('/');
    const body = empty ? inner.slice(0, -1) : inner;
    const name = /^[^\s/>]+/.exec(body)?.[0];
    if (!name) throw new Error(`The XML has a tag with no name at ${open}.`);
    const node = { name, attrs: attributes(body.slice(name.length)), children: [], text: '' };
    top.children.push(node);
    if (!empty) stack.push(node);
  }
  if (stack.length !== 1) throw new Error(`The XML ends with ${stack[stack.length - 1].name} still open.`);
  const root = document.children[0];
  if (!root) throw new Error('The XML holds no element.');
  return root;
}

export const kids = (node, name) => node.children.filter((child) => child.name === name);
export const kid = (node, name) => node.children.find((child) => child.name === name) ?? null;

/** The element at `steps` ("a/b/c") below `node`, following the first match each step. */
export function path(node, steps) {
  let here = node;
  for (const step of steps.split('/')) {
    here = here && kid(here, step);
    if (!here) return null;
  }
  return here;
}

export function* walk(node) {
  yield node;
  for (const child of node.children) yield* walk(child);
}

/** Every element named `name` at or below `node`, in document order. */
export const all = (node, name) => [...walk(node)].filter((each) => each.name === name);
```

- [ ] **Step 4: Run them to see them pass**

Run: `node --test tests/xml.test.mjs`
Expected: `# pass 4`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/xml.mjs tests/xml.test.mjs
git commit -m "Read XML for Office and SVG files without a dependency"
```

---

### Task 4: SVG path geometry

**Files:**
- Create: `scripts/lib/svg-path.mjs`
- Test: `tests/svg-path.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/svg-path.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  apply, bounds, format, parsePath, parseTransform, transformSegments,
} from '../scripts/lib/svg-path.mjs';

const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-6, `${actual} is not ${expected}`);

test('absolute and relative lines, with H, V and an implicit line after M', () => {
  assert.equal(format(parsePath('M10 10 L20 10 Z')), 'M10 10 L20 10 Z');
  assert.equal(format(parsePath('m10 10 10 0 v5 h-10z')), 'M10 10 L20 10 L20 15 L10 15 Z');
});

test('a closed subpath returns to its start for the next relative move', () => {
  assert.equal(format(parsePath('M10 10 L20 10 Z m5 5 l1 0')), 'M10 10 L20 10 Z M15 15 L16 15');
});

test('smooth and quadratic curves become cubics', () => {
  assert.equal(format(parsePath('M0 0 C0 10 10 10 10 0 S20 -10 20 0')),
    'M0 0 C0 10 10 10 10 0 C10 -10 20 -10 20 0');
  assert.equal(format(parsePath('M0 0 Q15 30 30 0')), 'M0 0 C10 20 20 20 30 0');
  assert.equal(format(parsePath('M0 0 Q15 30 30 0 T60 0')), 'M0 0 C10 20 20 20 30 0 C40 -20 50 -20 60 0');
});

test('an arc becomes cubics that pass through the arc', () => {
  const segs = parsePath('M0 0 A10 10 0 0 1 20 0');
  assert.equal(segs.length, 3);
  const [x, y] = segs[1].pts[2];
  near(x, 10);
  near(y, -10);
  assert.deepEqual(segs[2].pts[2], [20, 0]);
});

test('arc flags may be written without spaces', () => {
  assert.equal(format(parsePath('M0 0a10 10 0 0120 0')), format(parsePath('M0 0 A10 10 0 0 1 20 0')));
});

test('bad path data is refused', () => {
  assert.throws(() => parsePath('10 10'), /start with a command/);
  assert.throws(() => parsePath('M10'), /no number/);
});

test('transforms compose left to right, as SVG writes them', () => {
  const m = parseTransform('translate(10 0) scale(2)');
  assert.deepEqual(apply(m, [1, 1]), [12, 2]);
  const r = parseTransform('rotate(90 10 10)');
  const [x, y] = apply(r, [20, 10]);
  near(x, 10);
  near(y, 20);
  assert.deepEqual(apply(parseTransform(''), [3, 4]), [3, 4]);
  assert.throws(() => parseTransform('wobble(3)'), /wobble/);
});

test('bounds and transformed segments', () => {
  const segs = transformSegments(parsePath('M0 0 L10 0 L10 5 Z'), parseTransform('translate(5 5)'));
  assert.deepEqual(bounds(segs), [5, 5, 15, 10]);
  assert.deepEqual(bounds([]), [0, 0, 0, 0]);
});

test('numbers are written to two places, without -0', () => {
  assert.equal(format(parsePath('M0.004 -0.001 L1.23456 2')), 'M0 0 L1.23 2');
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/svg-path.test.mjs`
Expected: FAIL, cannot find module `../scripts/lib/svg-path.mjs`.

- [ ] **Step 3: Write `scripts/lib/svg-path.mjs`**

```js
// SVG path data as absolute segments: {op: 'M'|'L'|'C', pts: [[x, y], ...]} or {op: 'Z'}.
// Quadratic curves and arcs become cubics, so every path needs only four operations.

const NUMBER = /^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?/;

export function parsePath(d) {
  const out = [];
  let i = 0;
  let command = null;
  let x = 0; let y = 0; let startX = 0; let startY = 0;
  let lastCubic = null; let lastQuad = null;
  const skip = () => { while (i < d.length && /[\s,]/.test(d[i])) i += 1; };
  const number = () => {
    skip();
    const match = NUMBER.exec(d.slice(i));
    if (!match) throw new Error(`The path has no number at ${i}.`);
    i += match[0].length;
    return Number(match[0]);
  };
  const flag = () => {
    skip();
    const ch = d[i];
    if (ch !== '0' && ch !== '1') throw new Error(`The path has no arc flag at ${i}.`);
    i += 1;
    return ch === '1';
  };
  for (;;) {
    skip();
    if (i >= d.length) break;
    if (/[A-Za-z]/.test(d[i])) { command = d[i]; i += 1; }
    else if (!command) throw new Error('The path does not start with a command.');
    const relative = command === command.toLowerCase();
    const op = command.toUpperCase();
    const ox = relative ? x : 0;
    const oy = relative ? y : 0;
    switch (op) {
      case 'Z':
        out.push({ op: 'Z' });
        x = startX; y = startY; lastCubic = null; lastQuad = null; command = null;
        break;
      case 'M':
        x = ox + number(); y = oy + number();
        out.push({ op: 'M', pts: [[x, y]] });
        startX = x; startY = y; lastCubic = null; lastQuad = null;
        command = relative ? 'l' : 'L';
        break;
      case 'L':
        x = ox + number(); y = oy + number();
        out.push({ op: 'L', pts: [[x, y]] });
        lastCubic = null; lastQuad = null;
        break;
      case 'H':
        x = ox + number();
        out.push({ op: 'L', pts: [[x, y]] });
        lastCubic = null; lastQuad = null;
        break;
      case 'V':
        y = oy + number();
        out.push({ op: 'L', pts: [[x, y]] });
        lastCubic = null; lastQuad = null;
        break;
      case 'C': {
        const one = [ox + number(), oy + number()];
        const two = [ox + number(), oy + number()];
        x = ox + number(); y = oy + number();
        out.push({ op: 'C', pts: [one, two, [x, y]] });
        lastCubic = two; lastQuad = null;
        break;
      }
      case 'S': {
        const one = lastCubic ? [2 * x - lastCubic[0], 2 * y - lastCubic[1]] : [x, y];
        const two = [ox + number(), oy + number()];
        x = ox + number(); y = oy + number();
        out.push({ op: 'C', pts: [one, two, [x, y]] });
        lastCubic = two; lastQuad = null;
        break;
      }
      case 'Q': {
        const control = [ox + number(), oy + number()];
        const end = [ox + number(), oy + number()];
        out.push(quadratic([x, y], control, end));
        [x, y] = end; lastQuad = control; lastCubic = null;
        break;
      }
      case 'T': {
        const control = lastQuad ? [2 * x - lastQuad[0], 2 * y - lastQuad[1]] : [x, y];
        const end = [ox + number(), oy + number()];
        out.push(quadratic([x, y], control, end));
        [x, y] = end; lastQuad = control; lastCubic = null;
        break;
      }
      case 'A': {
        const rx = number(); const ry = number(); const angle = number();
        const large = flag(); const sweep = flag();
        const endX = ox + number(); const endY = oy + number();
        out.push(...arc(x, y, rx, ry, angle, large, sweep, endX, endY));
        x = endX; y = endY; lastCubic = null; lastQuad = null;
        break;
      }
      default:
        throw new Error(`The path has an unknown command ${command}.`);
    }
  }
  return out;
}

function quadratic(start, control, end) {
  return {
    op: 'C',
    pts: [
      [start[0] + (2 / 3) * (control[0] - start[0]), start[1] + (2 / 3) * (control[1] - start[1])],
      [end[0] + (2 / 3) * (control[0] - end[0]), end[1] + (2 / 3) * (control[1] - end[1])],
      end,
    ],
  };
}

// An elliptical arc as cubics, following the SVG specification's centre parameterisation.
function arc(x1, y1, rxIn, ryIn, angle, large, sweep, x2, y2) {
  if (x1 === x2 && y1 === y2) return [];
  let rx = Math.abs(rxIn);
  let ry = Math.abs(ryIn);
  if (!rx || !ry) return [{ op: 'L', pts: [[x2, y2]] }];
  const phi = (angle * Math.PI) / 180;
  const cos = Math.cos(phi);
  const sin = Math.sin(phi);
  const dx = (x1 - x2) / 2;
  const dy = (y1 - y2) / 2;
  const xp = cos * dx + sin * dy;
  const yp = -sin * dx + cos * dy;
  const lambda = (xp * xp) / (rx * rx) + (yp * yp) / (ry * ry);
  if (lambda > 1) { rx *= Math.sqrt(lambda); ry *= Math.sqrt(lambda); }
  const top = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp;
  const bottom = rx * rx * yp * yp + ry * ry * xp * xp;
  let k = Math.sqrt(Math.max(0, top / bottom));
  if (large === sweep) k = -k;
  const cxp = (k * rx * yp) / ry;
  const cyp = (-k * ry * xp) / rx;
  const cx = cos * cxp - sin * cyp + (x1 + x2) / 2;
  const cy = sin * cxp + cos * cyp + (y1 + y2) / 2;
  const between = (ux, uy, vx, vy) => Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy);
  const start = between(1, 0, (xp - cxp) / rx, (yp - cyp) / ry);
  let delta = between((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry);
  if (!sweep && delta > 0) delta -= 2 * Math.PI;
  else if (sweep && delta < 0) delta += 2 * Math.PI;
  const pieces = Math.max(1, Math.ceil(Math.abs(delta) / (Math.PI / 2)));
  const step = delta / pieces;
  const alpha = (4 / 3) * Math.tan(step / 4);
  const point = (t) => [cx + rx * Math.cos(t) * cos - ry * Math.sin(t) * sin,
    cy + rx * Math.cos(t) * sin + ry * Math.sin(t) * cos];
  const tangent = (t) => [-rx * Math.sin(t) * cos - ry * Math.cos(t) * sin,
    -rx * Math.sin(t) * sin + ry * Math.cos(t) * cos];
  const out = [];
  for (let n = 0; n < pieces; n += 1) {
    const a = start + n * step;
    const b = a + step;
    const [p0, p3, d0, d3] = [point(a), point(b), tangent(a), tangent(b)];
    out.push({ op: 'C', pts: [[p0[0] + alpha * d0[0], p0[1] + alpha * d0[1]],
      [p3[0] - alpha * d3[0], p3[1] - alpha * d3[1]], p3] });
  }
  out[out.length - 1].pts[2] = [x2, y2];
  return out;
}

// A transform is [a, b, c, d, e, f]: x' = a x + c y + e, y' = b x + d y + f.
export const IDENTITY = [1, 0, 0, 1, 0, 0];

/** `outer` applied after `inner`. */
export function multiply(outer, inner) {
  const [a, b, c, d, e, f] = outer;
  const [A, B, C, D, E, F] = inner;
  return [a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D, a * E + c * F + e, b * E + d * F + f];
}

export function parseTransform(text) {
  let matrix = IDENTITY;
  for (const [, name, args] of String(text ?? '').matchAll(/([A-Za-z]+)\s*\(([^)]*)\)/g)) {
    const v = args.split(/[\s,]+/).filter(Boolean).map(Number);
    let step;
    switch (name) {
      case 'matrix': step = v; break;
      case 'translate': step = [1, 0, 0, 1, v[0], v[1] ?? 0]; break;
      case 'scale': step = [v[0], 0, 0, v[1] ?? v[0], 0, 0]; break;
      case 'rotate': {
        const r = (v[0] * Math.PI) / 180;
        step = [Math.cos(r), Math.sin(r), -Math.sin(r), Math.cos(r), 0, 0];
        if (v.length === 3) {
          step = multiply(multiply([1, 0, 0, 1, v[1], v[2]], step), [1, 0, 0, 1, -v[1], -v[2]]);
        }
        break;
      }
      case 'skewX': step = [1, 0, Math.tan((v[0] * Math.PI) / 180), 1, 0, 0]; break;
      case 'skewY': step = [1, Math.tan((v[0] * Math.PI) / 180), 0, 1, 0, 0]; break;
      default: throw new Error(`The transform ${name} is not known.`);
    }
    if (step.length !== 6 || step.some((n) => !Number.isFinite(n))) {
      throw new Error(`The transform ${name}(${args}) cannot be read.`);
    }
    matrix = multiply(matrix, step);
  }
  return matrix;
}

export const apply = (m, [x, y]) => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];

export const transformSegments = (segs, m) => segs.map((seg) => (seg.op === 'Z'
  ? seg : { op: seg.op, pts: seg.pts.map((p) => apply(m, p)) }));

/** [x0, y0, x1, y1] around every point, control points included. */
export function bounds(segs) {
  const points = segs.flatMap((seg) => seg.pts ?? []);
  if (!points.length) return [0, 0, 0, 0];
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

export const round = (n) => {
  const v = Math.round(n * 100) / 100;
  return v === 0 ? 0 : v;
};

export const format = (segs) => segs.map((seg) => (seg.op === 'Z' ? 'Z'
  : seg.op + seg.pts.map(([x, y]) => `${round(x)} ${round(y)}`).join(' '))).join(' ');
```

- [ ] **Step 4: Run them to see them pass**

Run: `node --test tests/svg-path.test.mjs`
Expected: `# pass 9`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/svg-path.mjs tests/svg-path.test.mjs
git commit -m "Read SVG path data and transforms as absolute cubic segments"
```

---

### Task 5: One SVG drawing to one glyph

> **Revised in review (3 November 2026):** a glyph is a list of paths (`paths`), each filled
> even-odd on its own, because joining overlapping shapes into one even-odd path made them
> cancel. The code below is the first version; the committed version, with its tests, is
> on the branch (commit "Keep each shape of a glyph as its own path, and refuse what cannot
> be drawn right"). Later tasks below use `paths`.

**Files:**
- Create: `scripts/lib/icons/svg-glyph.mjs`
- Test: `tests/svg-glyph.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/svg-glyph.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { convertSvg } from '../scripts/lib/icons/svg-glyph.mjs';

const svg = (box, body) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${box}">${body}</svg>`;

test('a plain drawing is scaled from its view box into the 0 to 100 box', () => {
  const glyph = convertSvg(svg('0 0 50 50', '<path d="M10 10 H40 V40 H10 Z"/>'));
  assert.equal(glyph.d, 'M20 20 L80 20 L80 80 L20 80 Z');
  assert.deepEqual(glyph.bounds, [20, 20, 80, 80]);
});

test('fill places the view box in a centred share of the box', () => {
  const glyph = convertSvg(svg('0 0 50 50', '<path d="M10 10 H40 V40 H10 Z"/>'), { fill: 0.5 });
  assert.equal(glyph.d, 'M35 35 L65 35 L65 65 L35 65 Z');
});

test('a container circle under the glyph is dropped (VMware by Broadcom icons)', () => {
  const glyph = convertSvg(svg('0 0 100 100',
    '<circle cx="50" cy="50" r="50" fill="#005c8a"/><rect x="30" y="30" width="40" height="40" fill="#fff"/>'));
  assert.equal(glyph.d, 'M30 30 L70 30 L70 70 L30 70 Z');
});

test('a fill drawn through a mask takes the mask as the glyph (Tanzu Division icons)', () => {
  const glyph = convertSvg(svg('0 0 100 100',
    '<mask id="m"><path d="M10 10 H20 V20 H10 Z" fill="#fff"/></mask>'
    + '<rect width="100" height="100" fill="#005c8a" mask="url(#m)"/>'));
  assert.equal(glyph.d, 'M10 10 L20 10 L20 20 L10 20 Z');
});

test('group transforms are applied', () => {
  const glyph = convertSvg(svg('0 0 100 100', '<g transform="translate(10 0)"><rect width="10" height="10"/></g>'));
  assert.equal(glyph.d, 'M10 0 L20 0 L20 10 L10 10 Z');
});

test('one shape alone is kept even when it fills the box', () => {
  const glyph = convertSvg(svg('0 0 100 100', '<rect width="100" height="100"/>'));
  assert.equal(glyph.d, 'M0 0 L100 0 L100 100 L0 100 Z');
});

test('circles, polygons and rounded rectangles are outlines too', () => {
  assert.ok(convertSvg(svg('0 0 100 100', '<circle cx="50" cy="50" r="10"/>')).d.startsWith('M40 50 C'));
  assert.equal(convertSvg(svg('0 0 100 100', '<polygon points="0,0 10,0 10,10"/>')).d, 'M0 0 L10 0 L10 10 Z');
  assert.ok(convertSvg(svg('0 0 100 100', '<rect width="20" height="20" rx="4"/>')).d.includes('C'));
});

test('what cannot be one glyph says why', () => {
  assert.match(convertSvg(svg('0 0 10 10', '<path d="M0 0 L10 10" fill="none" stroke="#000"/>')).skip, /lines/);
  assert.match(convertSvg(svg('0 0 10 10', '')).skip, /draws nothing/);
  assert.match(convertSvg('<html/>').skip, /not an SVG/);
  assert.match(convertSvg('<svg><path d="M0 0"/></svg>').skip, /view box/);
  assert.match(convertSvg('<svg viewBox="0 0 10 10"><path d="Q"/></svg>').skip, /number/);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/svg-glyph.test.mjs`
Expected: FAIL, cannot find module `../scripts/lib/icons/svg-glyph.mjs`.

- [ ] **Step 3: Write `scripts/lib/icons/svg-glyph.mjs`**

```js
// One SVG drawing as one single-colour glyph: an even-odd path in the 0 to 100 box.
import { all, parseXml } from '../xml.mjs';
import {
  IDENTITY, bounds, format, multiply, parsePath, parseTransform, round, transformSegments,
} from '../svg-path.mjs';

const NOT_DRAWN = new Set(['defs', 'mask', 'clipPath', 'title', 'desc', 'metadata', 'style',
  'symbol', 'linearGradient', 'radialGradient', 'pattern', 'filter']);
const GROUPS = new Set(['g', 'svg', 'a']);
const CONTAINER = 0.95;   // a shape this much of the view box wide and high is a container

function style(node, name) {
  const inline = new RegExp(`(?:^|;)\\s*${name}\\s*:\\s*([^;]+)`).exec(node.attrs.style ?? '');
  const value = inline ? inline[1] : node.attrs[name];
  return value === undefined ? undefined : String(value).trim();
}

function viewBox(root) {
  const v = String(root.attrs.viewBox ?? '').trim().split(/[\s,]+/).map(Number);
  if (v.length === 4 && v.every(Number.isFinite) && v[2] > 0 && v[3] > 0) {
    return { x: v[0], y: v[1], w: v[2], h: v[3] };
  }
  const w = parseFloat(root.attrs.width);
  const h = parseFloat(root.attrs.height);
  return w > 0 && h > 0 ? { x: 0, y: 0, w, h } : null;
}

const measure = (node, name) => {
  const v = parseFloat(node.attrs[name]);
  return Number.isFinite(v) ? v : 0;
};

const ellipse = (cx, cy, rx, ry) => `M${cx - rx} ${cy} A${rx} ${ry} 0 1 0 ${cx + rx} ${cy} `
  + `A${rx} ${ry} 0 1 0 ${cx - rx} ${cy} Z`;

/** The outline of a drawn element as path data, or null for one that draws nothing. */
function outline(node) {
  switch (node.name) {
    case 'path':
      return node.attrs.d ?? null;
    case 'rect': {
      const x = measure(node, 'x'); const y = measure(node, 'y');
      const w = measure(node, 'width'); const h = measure(node, 'height');
      if (w <= 0 || h <= 0) return null;
      const rxGiven = parseFloat(node.attrs.rx);
      const ryGiven = parseFloat(node.attrs.ry);
      let rx = Number.isFinite(rxGiven) ? rxGiven : (Number.isFinite(ryGiven) ? ryGiven : 0);
      let ry = Number.isFinite(ryGiven) ? ryGiven : rx;
      rx = Math.min(rx, w / 2);
      ry = Math.min(ry, h / 2);
      if (!rx || !ry) return `M${x} ${y} H${x + w} V${y + h} H${x} Z`;
      return `M${x + rx} ${y} H${x + w - rx} A${rx} ${ry} 0 0 1 ${x + w} ${y + ry} `
        + `V${y + h - ry} A${rx} ${ry} 0 0 1 ${x + w - rx} ${y + h} H${x + rx} `
        + `A${rx} ${ry} 0 0 1 ${x} ${y + h - ry} V${y + ry} A${rx} ${ry} 0 0 1 ${x + rx} ${y} Z`;
    }
    case 'circle': {
      const r = measure(node, 'r');
      return r > 0 ? ellipse(measure(node, 'cx'), measure(node, 'cy'), r, r) : null;
    }
    case 'ellipse': {
      const rx = measure(node, 'rx'); const ry = measure(node, 'ry');
      return rx > 0 && ry > 0 ? ellipse(measure(node, 'cx'), measure(node, 'cy'), rx, ry) : null;
    }
    case 'polygon':
    case 'polyline': {
      const v = String(node.attrs.points ?? '').trim().split(/[\s,]+/).filter(Boolean).map(Number);
      if (v.length < 4 || v.some((n) => !Number.isFinite(n))) return null;
      const pairs = [];
      for (let i = 0; i + 1 < v.length; i += 2) pairs.push(`${v[i]} ${v[i + 1]}`);
      return `M${pairs.join(' L')} Z`;
    }
    default:
      return null;
  }
}

function collect(node, matrix, paint, masks, out) {
  for (const child of node.children) {
    if (NOT_DRAWN.has(child.name)) continue;
    const here = multiply(matrix, parseTransform(child.attrs.transform));
    const mask = /url\(\s*#([^)\s]+)\s*\)/.exec(style(child, 'mask') ?? '');
    if (mask && masks.has(mask[1])) {
      collect(masks.get(mask[1]), here, {}, masks, out);
      continue;
    }
    const inherited = { fill: style(child, 'fill') ?? paint.fill, stroke: style(child, 'stroke') ?? paint.stroke };
    if (GROUPS.has(child.name)) {
      collect(child, here, inherited, masks, out);
      continue;
    }
    const d = outline(child);
    if (d === null) continue;
    const clear = [style(child, 'fill-opacity'), style(child, 'opacity')]
      .some((v) => v !== undefined && Number(v) === 0);
    out.push({
      segs: transformSegments(parsePath(d), here),
      painted: inherited.fill !== 'none' && !clear,
      stroked: Boolean(inherited.stroke && inherited.stroke !== 'none'),
    });
  }
}

/** {d, bounds} for the drawing, or {skip: why it cannot be one glyph}. `fill` is the share
 *  of the 0 to 100 box the drawing's view box fills, centred. */
export function convertSvg(text, { fill = 1 } = {}) {
  let root;
  try {
    root = parseXml(text);
  } catch (error) {
    return { skip: `it is not readable SVG (${error.message})` };
  }
  if (root.name !== 'svg') return { skip: 'it is not an SVG drawing' };
  const box = viewBox(root);
  if (!box) return { skip: 'it has no view box or size' };
  const masks = new Map(all(root, 'mask').filter((m) => m.attrs.id).map((m) => [m.attrs.id, m]));
  const shapes = [];
  try {
    collect(root, IDENTITY, {}, masks, shapes);
  } catch (error) {
    return { skip: `its drawing cannot be read: ${error.message}` };
  }
  const painted = shapes.filter((shape) => shape.painted);
  if (!painted.length) {
    return { skip: shapes.some((shape) => shape.stroked)
      ? 'it is drawn with lines, not filled shapes' : 'it draws nothing' };
  }
  const covers = (shape) => {
    const [x0, y0, x1, y1] = bounds(shape.segs);
    return x1 - x0 >= CONTAINER * box.w && y1 - y0 >= CONTAINER * box.h;
  };
  const glyph = painted.length > 1 ? painted.filter((shape) => !covers(shape)) : painted;
  if (!glyph.length) return { skip: 'it holds only its container' };
  const scale = (100 * fill) / Math.max(box.w, box.h);
  const fit = [scale, 0, 0, scale, (100 - box.w * scale) / 2 - box.x * scale,
    (100 - box.h * scale) / 2 - box.y * scale];
  const segs = transformSegments(glyph.flatMap((shape) => shape.segs), fit);
  return { d: format(segs), bounds: bounds(segs).map(round) };
}
```

- [ ] **Step 4: Run them to see them pass**

Run: `node --test tests/svg-glyph.test.mjs`
Expected: `# pass 8`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/icons/svg-glyph.mjs tests/svg-glyph.test.mjs
git commit -m "Turn one SVG icon into one glyph, dropping containers and reading masks"
```

---

### Task 6: Reading a source

**Files:**
- Create: `scripts/lib/icons/sources.mjs`
- Test: `tests/sources.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/sources.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { readSource, sourceFiles } from '../scripts/lib/icons/sources.mjs';
import { writeZip } from '../scripts/lib/zip.mjs';

const SVG = '<svg viewBox="0 0 10 10"><rect width="5" height="5"/></svg>';

test('an icons.json with glyph paths is read as an index', () => {
  const index = { viewBox: '0 0 100 100', note: 'Colour only with brand colours.',
    icons: [{ slug: 'ai-1', name: 'AI 1', category: 'AI', bounds: [1, 2, 3, 4], d: 'M1 2 L3 4 Z' }] };
  const held = readSource(new Map([['export/assets/Icons/icons.json', Buffer.from(JSON.stringify(index))]]));
  assert.equal(held.kind, 'index');
  assert.equal(held.icons.length, 1);
  assert.equal(held.note, 'Colour only with brand colours.');
});

test('an index drawn in another box is refused', () => {
  const index = { viewBox: '0 0 24 24', icons: [{ slug: 'a', d: 'M0 0 Z' }] };
  assert.throws(() => readSource(new Map([['icons.json', Buffer.from(JSON.stringify(index))]])), /0 0 24 24/);
});

test('icon folders in an export become categories, with names from their README', () => {
  const files = new Map([
    ['t/assets/Functional Cloud/cloud-1.svg', Buffer.from(SVG)],
    ['t/assets/Functional Cloud/README.md', Buffer.from('| File | Name |\n|---|---|\n| `cloud-1.svg` | Cloud One |\n')],
    ['t/assets/Icons Data Center/Rack_2.svg', Buffer.from(SVG)],
    ['t/assets/Logos/logo.svg', Buffer.from(SVG)],
  ]);
  const held = readSource(files);
  assert.equal(held.kind, 'svg');
  assert.deepEqual(held.drawings.map(({ slug, name, category }) => ({ slug, name, category })), [
    { slug: 'cloud-1', name: 'Cloud One', category: 'Cloud' },
    { slug: 'rack-2', name: 'Rack 2', category: 'Data Center' },
  ]);
});

test('a plain folder of SVGs takes each folder name as the category', () => {
  const held = readSource(new Map([['Spring/boot.svg', Buffer.from(SVG)], ['top.svg', Buffer.from(SVG)]]));
  assert.deepEqual(held.drawings.map((d) => [d.slug, d.category]), [['boot', 'Spring'], ['top', 'General']]);
});

test('sources are read from a folder or a ZIP archive alike', () => {
  const root = mkdtempSync(join(tmpdir(), 'hb-source-'));
  mkdirSync(join(root, 'Cloud'));
  writeFileSync(join(root, 'Cloud', 'a.svg'), SVG);
  writeFileSync(join(root, '.DS_Store'), 'x');
  writeFileSync(join(root, 'set.zip'), writeZip([['Cloud/a.svg', SVG]]));
  assert.deepEqual([...sourceFiles(join(root, 'set.zip')).keys()], ['Cloud/a.svg']);
  assert.ok(sourceFiles(root).has('Cloud/a.svg'));
  assert.ok(![...sourceFiles(root).keys()].some((name) => name.includes('.DS_Store')));
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/sources.test.mjs`
Expected: FAIL, cannot find module `../scripts/lib/icons/sources.mjs`.

- [ ] **Step 3: Write `scripts/lib/icons/sources.mjs`**

```js
// What an icon source holds: an icons.json index of glyphs, or SVG drawings by category.
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { readZip } from '../zip.mjs';

/** A source's files, as a Map of path (with /) to Buffer, from a ZIP archive or a folder. */
export function sourceFiles(place) {
  if (!statSync(place).isDirectory()) return readZip(readFileSync(place));
  const files = new Map();
  const walk = (folder) => {
    for (const name of readdirSync(folder).sort()) {
      if (name.startsWith('.')) continue;
      const full = join(folder, name);
      if (statSync(full).isDirectory()) walk(full);
      else files.set(relative(place, full).split(sep).join('/'), readFileSync(full));
    }
  };
  walk(place);
  return files;
}

export const slugOf = (text) => String(text).replace(/\.svg$/i, '').toLowerCase()
  .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

export const titleOf = (slug) => slug.split('-').filter(Boolean)
  .map((word) => word[0].toUpperCase() + word.slice(1)).join(' ');

const ICON_FOLDER = /^(Functional|Icons)\s+/;

function namesIn(readme) {
  const names = new Map();
  for (const [, file, name] of readme.matchAll(/^\|\s*`?([^`|]+?\.svg)`?\s*\|\s*([^|]+?)\s*\|/gim)) {
    names.set(file.trim(), name.trim());
  }
  return names;
}

/** {kind: 'index', path, icons, note} from the shallowest icons.json holding glyph paths,
 *  else {kind: 'svg', drawings: [{path, slug, name, category, text}]}. In an export with
 *  "Functional ..." or "Icons ..." folders, only those folders' SVGs are icons. */
export function readSource(files) {
  const indexes = [...files.keys()].filter((name) => name.split('/').pop() === 'icons.json')
    .sort((a, b) => a.split('/').length - b.split('/').length);
  for (const name of indexes) {
    let parsed;
    try { parsed = JSON.parse(files.get(name).toString('utf8')); } catch { continue; }
    if (!Array.isArray(parsed?.icons)
        || !parsed.icons.some((icon) => typeof icon?.d === 'string' || Array.isArray(icon?.paths))) continue;
    const box = String(parsed.viewBox ?? '0 0 100 100').trim().split(/[\s,]+/).join(' ');
    if (box !== '0 0 100 100') {
      throw new Error(`${name} draws in a ${parsed.viewBox} box; an icon library draws in 0 0 100 100.`);
    }
    return { kind: 'index', path: name, icons: parsed.icons, note: String(parsed.note ?? '') };
  }
  let svgs = [...files.keys()].filter((name) => name.toLowerCase().endsWith('.svg'));
  const folderOf = (name) => name.split('/').slice(-2, -1)[0] ?? '';
  if (svgs.some((name) => ICON_FOLDER.test(folderOf(name)))) {
    svgs = svgs.filter((name) => ICON_FOLDER.test(folderOf(name)));
  }
  const drawings = svgs.sort().map((name) => {
    const folder = name.split('/').slice(0, -1).join('/');
    const readme = files.get(folder ? `${folder}/README.md` : 'README.md');
    const file = name.split('/').pop();
    const slug = slugOf(file);
    return {
      path: name,
      slug,
      name: (readme && namesIn(readme.toString('utf8')).get(file)) || titleOf(slug),
      category: folderOf(name).replace(ICON_FOLDER, '') || 'General',
      text: files.get(name).toString('utf8'),
    };
  });
  return { kind: 'svg', drawings };
}
```

- [ ] **Step 4: Run them to see them pass**

Run: `node --test tests/sources.test.mjs`
Expected: `# pass 5`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/icons/sources.mjs tests/sources.test.mjs
git commit -m "Read icon sources: an icons.json index, or SVG folders by category"
```

---

### Task 7: Building and checking a library

**Files:**
- Create: `scripts/lib/icons/library.mjs`
- Test: `tests/library.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/library.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  alignCategory, buildLibrary, checkLibrary, libraryArchive,
} from '../scripts/lib/icons/library.mjs';
import { readZip, writeZip } from '../scripts/lib/zip.mjs';

const SQUARE = '<svg viewBox="0 0 10 10"><rect width="5" height="5"/></svg>';
const LINES = '<svg viewBox="0 0 10 10"><path d="M0 0 L9 9" fill="none" stroke="#000"/></svg>';
const index = (icons, note = 'Brand colours only.') => new Map([['assets/Icons/icons.json',
  Buffer.from(JSON.stringify({ viewBox: '0 0 100 100', note, icons }))]]);
const glyph = (slug, category = 'Cloud') => ({ slug, name: slug, category, bounds: [0, 0, 50, 50], d: 'M0 0 L50 0 L50 50 Z' });
const options = { id: 'test-icons', name: 'Test icons' };

test('categories line up with the first source when they plainly mean the same', () => {
  const known = ['Apps & Software', 'Business Tools / Objects', 'Business Tools / Tools', 'Business Tools / Process', 'Data Center'];
  assert.equal(alignCategory('Apps', known), 'Apps & Software');
  assert.equal(alignCategory('Apps and Software', known), 'Apps & Software');
  assert.equal(alignCategory('Business Objects', known), 'Business Tools / Objects');
  assert.equal(alignCategory('Tools', known), 'Business Tools / Tools');
  assert.equal(alignCategory('Business Process', known), 'Business Tools / Process');
  assert.equal(alignCategory('data center', known), 'Data Center');
  assert.equal(alignCategory('Spring', known), 'Spring');
});

test('the first source wins where slugs meet, and later sources add what is new', () => {
  const built = buildLibrary([
    { label: 'one.zip', files: index([glyph('cloud-1'), glyph('ai-1', 'AI')]) },
    { label: 'two.zip', files: new Map([
      ['x/assets/Functional Cloud/cloud-1.svg', Buffer.from(SQUARE)],
      ['x/assets/Functional Cloud/cloud-9.svg', Buffer.from(SQUARE)],
      ['x/assets/Functional Cloud/drawn.svg', Buffer.from(LINES)],
    ]) },
  ], options);
  assert.deepEqual(built.icons.map((icon) => icon.slug), ['cloud-1', 'ai-1', 'cloud-9']);
  assert.deepEqual(built.counts, [{ source: 'one.zip', added: 2, already: 0 },
    { source: 'two.zip', added: 1, already: 1 }]);
  assert.deepEqual(built.skipped, [{ source: 'two.zip', file: 'x/assets/Functional Cloud/drawn.svg',
    reason: 'it is drawn with lines, not filled shapes' }]);
  assert.equal(built.library.usage, 'Brand colours only.');
  assert.equal(built.library.kind, 'glyph');
});

test('fill can differ by source', () => {
  const files = new Map([['C/a.svg', Buffer.from('<svg viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')]]);
  const built = buildLibrary([{ label: 'tanzu.zip', files }], { ...options, fills: { 'tanzu.zip': 0.5 } });
  assert.deepEqual(built.icons[0].bounds, [25, 25, 75, 75]);
});

test('a repeated file name within one source is numbered, not lost', () => {
  const built = buildLibrary([{ label: 's', files: new Map([
    ['Icons A/x.svg', Buffer.from(SQUARE)], ['Icons B/x.svg', Buffer.from(SQUARE)]]) }], options);
  assert.deepEqual(built.icons.map((icon) => icon.slug), ['x', 'x-2']);
});

test('a slug repeated within one index keeps both drawings, renaming the second from its name', () => {
  const built = buildLibrary([{ label: 'one', files: index([
    { ...glyph('apps-2'), name: 'Apps 2' },
    { ...glyph('apps-2'), name: 'Apps', d: 'M0 0 L10 0 L10 10 Z' },
    { ...glyph('apps-2'), name: 'Apps 2' },
  ]) }], options);
  assert.deepEqual(built.icons.map((icon) => [icon.slug, icon.name]), [['apps-2', 'Apps 2'], ['apps', 'Apps']]);
  assert.deepEqual(built.skipped, []);
});

test('a picture library keeps each drawing as it is', () => {
  const built = buildLibrary([{ label: 's', files: new Map([['Logos/spring.svg', Buffer.from(SQUARE)]]) }],
    { ...options, kind: 'picture' });
  assert.deepEqual(built.icons, [{ slug: 'spring', name: 'Spring', category: 'Logos', file: 'svg/logos/spring.svg' }]);
  assert.equal(built.svgs.get('svg/logos/spring.svg'), SQUARE);
});

test('an archive made from a build passes the check', () => {
  const built = buildLibrary([{ label: 'one', files: index([glyph('cloud-1')]) }], options);
  const archive = libraryArchive(built);
  assert.deepEqual(checkLibrary(archive, { id: 'test-icons' }), []);
  const files = readZip(archive);
  assert.equal(JSON.parse(files.get('library.json').toString()).id, 'test-icons');
  // An index's single "d" is kept as a list of one path.
  assert.deepEqual(JSON.parse(files.get('icons.json').toString()).icons[0].paths, ['M0 0 L50 0 L50 50 Z']);
});

test('the check names each problem', () => {
  const bad = writeZip([
    ['library.json', JSON.stringify({ schema: 1, id: 'Bad Id', name: '', version: 1, kind: 'glyph' })],
    ['icons.json', JSON.stringify({ schema: 1, icons: [
      { slug: 'a', name: 'A', category: 'C', bounds: [0, 0, 1], paths: ['M0 0 Z'] },
      { slug: 'a', name: 'A', category: 'C', bounds: [0, 0, 1, 1], paths: ['nonsense'] },
    ] })],
  ]);
  const problems = checkLibrary(bad, { id: 'bad-id' });
  assert.ok(problems.some((p) => p.includes('"id"')), problems.join('\n'));
  assert.ok(problems.some((p) => p.includes('"name"')));
  assert.ok(problems.some((p) => p.includes('"version"')));
  assert.ok(problems.some((p) => p.includes('Icon 1 (a)') && p.includes('bounds')));
  assert.ok(problems.some((p) => p.includes('Icon 2 (a)') && p.includes('repeats')));
  assert.ok(problems.some((p) => p.includes('Icon 2 (a)') && p.includes('"paths"')));
  assert.deepEqual(checkLibrary(Buffer.from('nope')), ['library.zip cannot be read: It is not a ZIP archive.']);
});

test('a picture whose drawing has a script is refused', () => {
  const archive = writeZip([
    ['library.json', JSON.stringify({ schema: 1, id: 'p', name: 'P', version: '1', kind: 'picture' })],
    ['icons.json', JSON.stringify({ schema: 1, icons: [{ slug: 'x', name: 'X', category: 'C', file: 'svg/c/x.svg' }] })],
    ['svg/c/x.svg', '<svg><script>alert(1)</script></svg>'],
  ]);
  assert.deepEqual(checkLibrary(archive), ['Icon 1 (x) has a drawing with a script in it.']);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/library.test.mjs`
Expected: FAIL, cannot find module `../scripts/lib/icons/library.mjs`.

- [ ] **Step 3: Write `scripts/lib/icons/library.mjs`**

```js
// An icon library: built from sources, kept as library.zip, and checked.
import { readZip, writeZip } from '../zip.mjs';
import { parsePath } from '../svg-path.mjs';
import { readSource, slugOf, titleOf } from './sources.mjs';
import { convertSvg } from './svg-glyph.mjs';

export const SLUG = /^[a-z0-9][a-z0-9-]*$/;
export const KINDS = ['glyph', 'picture'];

const words = (text) => String(text).toLowerCase().replace(/&/g, ' and ').split(/[^a-z0-9]+/).filter(Boolean);

/** The first source's category that `name` plainly means, else `name` itself. */
export function alignCategory(name, known) {
  const exact = known.find((category) => words(category).join(' ') === words(name).join(' '));
  if (exact) return exact;
  const mine = new Set(words(name));
  const fits = known.filter((category) => {
    const last = words(category.split('/').pop());
    const lastSet = new Set(last);
    return last.every((word) => mine.has(word)) || [...mine].every((word) => lastSet.has(word));
  });
  return fits.length === 1 ? fits[0] : name;
}

/** An index entry's paths: its "paths" list, or its one "d" (as Broadcom's export writes it). */
export const pathsOf = (icon) => (Array.isArray(icon?.paths) ? icon.paths
  : typeof icon?.d === 'string' ? [icon.d] : null);

/** Why a glyph is not usable, as the end of a sentence, or null. */
export function glyphProblem(icon) {
  const paths = icon?.paths;
  if (!Array.isArray(paths) || !paths.length || paths.some((d) => typeof d !== 'string' || !d.trim())) {
    return 'needs "paths": a list of path data';
  }
  for (const d of paths) {
    try { parsePath(d); } catch { return 'has a path in "paths" that cannot be read'; }
  }
  const box = icon.bounds;
  if (!Array.isArray(box) || box.length !== 4 || !box.every(Number.isFinite)
      || box.some((n) => n < -1 || n > 101)) return 'needs "bounds" of four numbers in the 0 to 100 box';
  return null;
}

/** `base`, or `base-2`, `base-3` ... : the first that is a usable slug and not taken. */
function freeSlug(base, isTaken) {
  if (SLUG.test(base) && !isTaken(base)) return base;
  let n = 2;
  while (isTaken(`${base}-${n}`)) n += 1;
  return `${base}-${n}`;
}

/** Build a library from sources ([{label, files}]), the first source winning where slugs meet.
 *  Returns {library, icons, svgs, counts, skipped}; nothing is written. */
export function buildLibrary(sources, { id, name, kind = 'glyph', version = '1', usage, source,
  fill = 1, fills = {} }) {
  if (!SLUG.test(String(id))) throw new Error('A library id is lower-case letters, digits and hyphens.');
  if (!String(name ?? '').trim()) throw new Error('A library needs a name.');
  if (!KINDS.includes(kind)) throw new Error('A library is a glyph library or a picture library.');
  const icons = [];
  const svgs = new Map();
  const taken = new Map();
  const counts = [];
  const skipped = [];
  let note = '';
  for (const { label, files } of sources) {
    const held = readSource(files);
    const known = [...new Set(icons.map((icon) => icon.category))];
    const count = { source: label, added: 0, already: 0 };
    if (held.kind === 'index') {
      if (kind === 'picture') throw new Error(`${label} holds glyph shapes; a picture library takes SVG drawings.`);
      note ||= held.note;
      const here = new Map();   // slug to its paths, for this index
      for (const raw of held.icons) {
        let slug = String(raw?.slug ?? '');
        const paths = pathsOf(raw);
        const problem = !SLUG.test(slug) ? 'needs a slug of lower-case letters, digits and hyphens'
          : glyphProblem({ paths, bounds: raw?.bounds });
        if (problem) { skipped.push({ source: label, file: slug || '?', reason: `it ${problem}` }); continue; }
        if (here.has(slug)) {
          // One slug twice in one index: the same drawing again is dropped; another is renamed.
          if (here.get(slug) === JSON.stringify(paths)) continue;
          slug = freeSlug(slugOf(String(raw.name ?? '')) || slug, (each) => here.has(each) || taken.has(each));
        }
        here.set(slug, JSON.stringify(paths));
        if (taken.has(slug)) { count.already += 1; continue; }
        const keywords = Array.isArray(raw.keywords) && raw.keywords.length ? { keywords: raw.keywords.map(String) } : {};
        icons.push({ slug, name: String(raw.name ?? titleOf(slug)), category: alignCategory(String(raw.category ?? 'General'), known),
          ...keywords, bounds: raw.bounds, paths });
        taken.set(slug, label);
        count.added += 1;
      }
    } else {
      const share = fills[label] ?? fill;
      for (const drawing of held.drawings) {
        let slug = drawing.slug;
        if (!SLUG.test(slug)) {
          skipped.push({ source: label, file: drawing.path, reason: 'its file name gives no usable id' });
          continue;
        }
        if (taken.has(slug)) {
          if (taken.get(slug) !== label) { count.already += 1; continue; }
          slug = freeSlug(slug, (each) => taken.has(each));
        }
        const category = alignCategory(drawing.category, known);
        const file = `svg/${slugOf(category)}/${slug}.svg`;
        let icon = { slug, name: drawing.name, category };
        if (kind === 'glyph') {
          const converted = convertSvg(drawing.text, { fill: share });
          if (converted.skip) { skipped.push({ source: label, file: drawing.path, reason: converted.skip }); continue; }
          icon = { ...icon, bounds: converted.bounds, paths: converted.paths };
        } else {
          icon = { ...icon, file };
        }
        icons.push(icon);
        svgs.set(file, drawing.text);
        taken.set(slug, label);
        count.added += 1;
      }
    }
    counts.push(count);
  }
  const library = { schema: 1, id, name: String(name).trim(), version: String(version), kind,
    source: source ?? sources.map((each) => each.label).join(', '), usage: usage ?? note };
  return { library, icons, svgs, counts, skipped };
}

const json = (value) => `${JSON.stringify(value, null, 2)}\n`;

/** library.zip for a build: library.json, icons.json, then the drawings by path. */
export function libraryArchive({ library, icons, svgs }) {
  const entries = [['library.json', json(library)], ['icons.json', json({ schema: 1, icons })]];
  for (const file of [...svgs.keys()].sort()) entries.push([file, svgs.get(file)]);
  return writeZip(entries);
}

/** Every problem with a library.zip, each in a sentence; none means it passes. */
export function checkLibrary(archive, { id } = {}) {
  let files;
  try {
    files = readZip(archive);
  } catch (error) {
    return [`library.zip cannot be read: ${error.message}`];
  }
  const problems = [];
  const read = (name) => {
    const data = files.get(name);
    if (!data) { problems.push(`library.zip has no ${name}.`); return null; }
    try { return JSON.parse(data.toString('utf8')); } catch (error) {
      problems.push(`${name} is not JSON (${error.message}).`);
      return null;
    }
  };
  const library = read('library.json');
  const index = read('icons.json');
  if (library) {
    if (library.schema !== 1) problems.push('library.json needs "schema": 1.');
    if (typeof library.id !== 'string' || !SLUG.test(library.id)) {
      problems.push('library.json needs an "id" of lower-case letters, digits and hyphens.');
    } else if (id && library.id !== id) {
      problems.push(`library.json says its id is ${library.id}, but its folder is ${id}.`);
    }
    if (typeof library.name !== 'string' || !library.name.trim()) problems.push('library.json needs a "name".');
    if (typeof library.version !== 'string' || !library.version.trim()) problems.push('library.json needs a "version", as text.');
    if (!KINDS.includes(library.kind)) problems.push('library.json needs a "kind": "glyph" or "picture".');
  }
  if (index) {
    if (index.schema !== 1) problems.push('icons.json needs "schema": 1.');
    const icons = Array.isArray(index.icons) ? index.icons : [];
    if (!icons.length) problems.push('icons.json holds no icons.');
    const seen = new Set();
    icons.forEach((icon, n) => {
      const where = `Icon ${n + 1}${typeof icon?.slug === 'string' ? ` (${icon.slug})` : ''}`;
      if (typeof icon?.slug !== 'string' || !SLUG.test(icon.slug)) {
        problems.push(`${where} needs a "slug" of lower-case letters, digits and hyphens.`);
      } else if (seen.has(icon.slug)) {
        problems.push(`${where} repeats a slug used before it.`);
      } else {
        seen.add(icon.slug);
      }
      if (typeof icon?.name !== 'string' || !icon.name.trim()) problems.push(`${where} needs a "name".`);
      if (typeof icon?.category !== 'string' || !icon.category.trim()) problems.push(`${where} needs a "category".`);
      if (icon?.keywords !== undefined
          && !(Array.isArray(icon.keywords) && icon.keywords.every((word) => typeof word === 'string'))) {
        problems.push(`${where} has "keywords" that are not a list of words.`);
      }
      if (library?.kind === 'glyph') {
        const problem = glyphProblem(icon);
        if (problem) problems.push(`${where} ${problem}.`);
      }
      if (library?.kind === 'picture') {
        const drawing = typeof icon?.file === 'string' ? files.get(icon.file) : undefined;
        if (!drawing) problems.push(`${where} needs a "file" that is in the archive.`);
        else if (/<script\b/i.test(drawing.toString('utf8'))) problems.push(`${where} has a drawing with a script in it.`);
      }
    });
  }
  return problems;
}
```

- [ ] **Step 4: Run them to see them pass**

Run: `node --test tests/library.test.mjs`
Expected: `# pass 9`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/icons/library.mjs tests/library.test.mjs
git commit -m "Build icon libraries from several sources and check library.zip"
```

---

### Task 8: The contact sheet

**Files:**
- Create: `scripts/lib/icons/contact-sheet.mjs`
- Test: `tests/contact-sheet.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/contact-sheet.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { contactSheet } from '../scripts/lib/icons/contact-sheet.mjs';
import { parseXml, all } from '../scripts/lib/xml.mjs';

test('every glyph is drawn with its label, and the sheet is valid SVG', () => {
  const sheet = contactSheet({ name: 'Test & co', kind: 'glyph' }, [
    { slug: 'a', name: 'Alpha <1>', category: 'C', bounds: [0, 0, 10, 10], paths: ['M0 0 L10 0 L10 10 Z'] },
    { slug: 'b', name: 'Beta', category: 'C', bounds: [0, 0, 10, 10], paths: ['M0 0 L5 0 L5 5 Z'] },
  ], new Map());
  const root = parseXml(sheet);
  assert.equal(root.name, 'svg');
  assert.equal(all(root, 'path').length, 2);
  assert.ok(sheet.includes('Alpha &lt;1&gt;'));
  assert.ok(sheet.includes('Test &amp; co: 2 icons'));
});

test('a picture is embedded as an image', () => {
  const sheet = contactSheet({ name: 'P', kind: 'picture' },
    [{ slug: 'x', name: 'X', category: 'C', file: 'svg/c/x.svg' }],
    new Map([['svg/c/x.svg', '<svg viewBox="0 0 1 1"/>']]));
  assert.equal(all(parseXml(sheet), 'image').length, 1);
  assert.ok(sheet.includes('data:image/svg+xml;base64,'));
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/contact-sheet.test.mjs`
Expected: FAIL, cannot find module `../scripts/lib/icons/contact-sheet.mjs`.

- [ ] **Step 3: Write `scripts/lib/icons/contact-sheet.mjs`**

```js
// Every icon in a library on one SVG sheet, labelled, for a person to look over.
const COLUMNS = 12;
const CELL = 120;
const ROW = 150;
const TOP = 50;
const INK = '#1b1d36';

const escape = (text) => String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;')
  .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const short = (text) => (text.length > 22 ? `${text.slice(0, 21)}…` : text);

/** The sheet as SVG text. `svgs` holds a picture library's drawings by path. */
export function contactSheet(library, icons, svgs) {
  const rows = Math.max(1, Math.ceil(icons.length / COLUMNS));
  const width = COLUMNS * CELL;
  const height = TOP + rows * ROW;
  const cells = icons.map((icon, n) => {
    const x = (n % COLUMNS) * CELL + 10;
    const y = TOP + Math.floor(n / COLUMNS) * ROW;
    const frame = `<rect x="${x}" y="${y}" width="100" height="100" fill="none" stroke="#d0d3d9"/>`;
    const drawing = Array.isArray(icon.paths)
      ? `<g transform="translate(${x} ${y})" fill="${INK}" fill-rule="evenodd">${
        icon.paths.map((d) => `<path d="${escape(d)}"/>`).join('')}</g>`
      : `<image x="${x}" y="${y}" width="100" height="100" href="data:image/svg+xml;base64,${
        Buffer.from(svgs.get(icon.file) ?? '').toString('base64')}"/>`;
    const label = `<text x="${x + 50}" y="${y + 118}" text-anchor="middle" font-size="10">${escape(short(icon.name))}</text>`
      + `<text x="${x + 50}" y="${y + 132}" text-anchor="middle" font-size="9" fill="#5a6170">${escape(short(icon.slug))}</text>`;
    return frame + drawing + label;
  });
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" `
    + `font-family="Arial, Helvetica, sans-serif"><rect width="${width}" height="${height}" fill="#ffffff"/>`
    + `<text x="10" y="30" font-size="18" fill="${INK}">${escape(`${library.name}: ${icons.length} icons`)}</text>`
    + `${cells.join('')}</svg>\n`;
}
```

- [ ] **Step 4: Run them to see them pass**

Run: `node --test tests/contact-sheet.test.mjs`
Expected: `# pass 2`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/icons/contact-sheet.mjs tests/contact-sheet.test.mjs
git commit -m "Draw an icon library's contact sheet for review"
```

---

### Task 9: The command

**Files:**
- Create: `scripts/harness-brand.mjs`, `scripts/version.mjs`, `scripts/pack.mjs`
- Test: `tests/command.test.mjs`

- [ ] **Step 1: Write the failing tests**

`tests/command.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { readZip, writeZip } from '../scripts/lib/zip.mjs';

const COMMAND = fileURLToPath(new URL('../scripts/harness-brand.mjs', import.meta.url));
const run = (...args) => spawnSync(process.execPath, [COMMAND, ...args], { encoding: 'utf8' });
const SQUARE = '<svg viewBox="0 0 10 10"><rect width="5" height="5"/></svg>';
const LINES = '<svg viewBox="0 0 10 10"><path d="M0 0 L9 9" fill="none" stroke="#000"/></svg>';

function place() {
  const root = mkdtempSync(join(tmpdir(), 'hb-command-'));
  mkdirSync(join(root, 'svgs', 'Cloud'), { recursive: true });
  writeFileSync(join(root, 'svgs', 'Cloud', 'cloud-1.svg'), SQUARE);
  writeFileSync(join(root, 'svgs', 'Cloud', 'drawn.svg'), LINES);
  writeFileSync(join(root, 'index.zip'), writeZip([['assets/Icons/icons.json', JSON.stringify({
    viewBox: '0 0 100 100', note: 'Brand colours only.',
    icons: [{ slug: 'ai-1', name: 'AI 1', category: 'AI', bounds: [0, 0, 9, 9], d: 'M0 0 L9 0 L9 9 Z' }] })]]));
  return root;
}

test('version names Harness Brand and its version', () => {
  const done = run('version');
  assert.equal(done.status, 0);
  const { version } = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
  assert.equal(done.stdout.trim(), `Harness Brand ${version}`);
});

test('with no command it prints its usage, which mentions brands', () => {
  const done = run();
  assert.equal(done.status, 0);
  assert.match(done.stdout, /Usage: harness-brand <command>/);
  assert.match(done.stdout, /brands/);
});

test('an unknown command is refused with the usage', () => {
  const done = run('juggle');
  assert.equal(done.status, 2);
  assert.match(done.stderr, /juggle is not a Harness Brand command/);
});

test('pack icons builds a library and its contact sheet, then pack check passes it', () => {
  const root = place();
  const into = join(root, 'icon-libraries', 'test-icons');
  const done = run('pack', 'icons', join(root, 'index.zip'), join(root, 'svgs'),
    '--library', 'test-icons', '--name', 'Test icons', '--into', into, '--json');
  assert.equal(done.status, 0, done.stderr);
  const report = JSON.parse(done.stdout);
  assert.equal(report.icons, 2);
  assert.deepEqual(report.skipped.map((s) => s.reason), ['it is drawn with lines, not filled shapes']);
  const files = readZip(readFileSync(join(into, 'library.zip')));
  assert.equal(JSON.parse(files.get('library.json').toString()).usage, 'Brand colours only.');
  assert.ok(existsSync(join(into, 'contact-sheet.svg')));
  const checked = run('pack', 'check', into);
  assert.equal(checked.status, 0, checked.stdout + checked.stderr);
  assert.match(checked.stdout, /Test icons passes: 2 glyph icons/);
});

test('pack icons will not replace a library unless told to', () => {
  const root = place();
  const into = join(root, 'lib');
  assert.equal(run('pack', 'icons', join(root, 'svgs'), '--library', 'lib', '--name', 'L', '--into', into).status, 0);
  const again = run('pack', 'icons', join(root, 'svgs'), '--library', 'lib', '--name', 'L', '--into', into);
  assert.equal(again.status, 1);
  assert.match(again.stderr, /already has a library\.zip/);
  assert.equal(run('pack', 'icons', join(root, 'svgs'), '--library', 'lib', '--name', 'L', '--into', into, '--replace').status, 0);
});

test('pack icons takes a fill for one source by its file name', () => {
  const root = place();
  const into = join(root, 'lib');
  const done = run('pack', 'icons', join(root, 'svgs'), '--library', 'lib', '--name', 'L', '--into', into,
    '--fill-for', 'svgs=0.5', '--json');
  assert.equal(done.status, 0, done.stderr);
  const icons = JSON.parse(readZip(readFileSync(join(into, 'library.zip'))).get('icons.json').toString()).icons;
  assert.deepEqual(icons[0].bounds, [25, 25, 50, 50]);
});

test('pack check names the problems and fails', () => {
  const root = mkdtempSync(join(tmpdir(), 'hb-check-'));
  writeFileSync(join(root, 'library.zip'), writeZip([['library.json', '{}']]));
  const done = run('pack', 'check', root);
  assert.equal(done.status, 1);
  assert.match(done.stdout, /library\.zip has no icons\.json/);
  const empty = run('pack', 'check', mkdtempSync(join(tmpdir(), 'hb-empty-')));
  assert.equal(empty.status, 1);
  assert.match(empty.stderr, /has no library\.zip/);
});

test('missing options are refused in a sentence', () => {
  const done = run('pack', 'icons', '--library', 'x');
  assert.equal(done.status, 1);
  assert.match(done.stderr, /Name at least one source/);
});
```

- [ ] **Step 2: Run them to see them fail**

Run: `node --test tests/command.test.mjs`
Expected: FAIL; every test fails because `scripts/harness-brand.mjs` does not exist.

- [ ] **Step 3: Write `scripts/version.mjs`**

```js
import { readFileSync } from 'node:fs';

export const VERSION = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')).version;

export function main() {
  console.log(`Harness Brand ${VERSION}`);
  return 0;
}
```

- [ ] **Step 4: Write `scripts/pack.mjs`**

```js
// harness-brand pack: the commands that build and check what the brands folder holds.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, join, resolve } from 'node:path';
import { parseArgs } from 'node:util';
import { buildLibrary, checkLibrary, libraryArchive } from './lib/icons/library.mjs';
import { sourceFiles } from './lib/icons/sources.mjs';
import { contactSheet } from './lib/icons/contact-sheet.mjs';
import { readZip } from './lib/zip.mjs';

export const USAGE = [
  '  pack icons <source>... --library ID --name NAME [--kind glyph|picture] [--fill F]',
  '             [--fill-for SOURCE=F]... [--version V] [--usage TEXT] --into FOLDER [--replace] [--json]',
  '  pack check <folder> [--json]',
].join('\n');

function share(text, what) {
  const value = Number(text);
  if (!(value > 0 && value <= 1)) throw new Error(`${what} is a share of the box, more than 0 and at most 1.`);
  return value;
}

function icons(args) {
  const { values, positionals } = parseArgs({
    args,
    allowPositionals: true,
    options: {
      library: { type: 'string' }, name: { type: 'string' }, kind: { type: 'string', default: 'glyph' },
      fill: { type: 'string', default: '1' }, 'fill-for': { type: 'string', multiple: true, default: [] },
      version: { type: 'string', default: '1' }, usage: { type: 'string' }, into: { type: 'string' },
      replace: { type: 'boolean', default: false }, json: { type: 'boolean', default: false },
    },
  });
  if (!positionals.length) throw new Error('Name at least one source: an export ZIP, a folder of SVGs or an icons.json.');
  if (!values.library || !values.name || !values.into) throw new Error('Give --library, --name and --into.');
  const fills = {};
  for (const pair of values['fill-for']) {
    const at = pair.lastIndexOf('=');
    if (at < 1) throw new Error(`--fill-for takes SOURCE=F, such as tanzu-division-design-system.zip=0.88, not ${pair}.`);
    fills[pair.slice(0, at)] = share(pair.slice(at + 1), `--fill-for ${pair}`);
  }
  const into = resolve(values.into);
  const target = join(into, 'library.zip');
  if (existsSync(target) && !values.replace) throw new Error(`${into} already has a library.zip. Give --replace to make it again.`);
  const sources = positionals.map((place) => {
    if (!existsSync(place)) throw new Error(`There is no source at ${place}.`);
    return { label: basename(resolve(place)), files: sourceFiles(place) };
  });
  const built = buildLibrary(sources, { id: values.library, name: values.name, kind: values.kind,
    version: values.version, usage: values.usage, fill: share(values.fill, '--fill'), fills });
  if (!built.icons.length) throw new Error('No icons were found in those sources. Nothing was written.');
  const archive = libraryArchive(built);
  const problems = checkLibrary(archive, { id: values.library });
  if (problems.length) throw new Error(`The library made does not pass, so nothing was written:\n${problems.join('\n')}`);
  mkdirSync(into, { recursive: true });
  writeFileSync(target, archive);
  const sheet = join(into, 'contact-sheet.svg');
  writeFileSync(sheet, contactSheet(built.library, built.icons, built.svgs));
  if (values.json) {
    console.log(JSON.stringify({ library: target, kind: built.library.kind, icons: built.icons.length,
      sources: built.counts, skipped: built.skipped, contactSheet: sheet }, null, 2));
    return 0;
  }
  console.log(`Wrote ${target}: ${built.icons.length} ${built.library.kind} icons.`);
  for (const count of built.counts) {
    console.log(`  ${count.source}: ${count.added} added${count.already ? `, ${count.already} already in the library` : ''}`);
  }
  if (built.skipped.length) {
    console.log(`Left out ${built.skipped.length}:`);
    for (const each of built.skipped) console.log(`  ${each.source}: ${each.file}: ${each.reason}`);
  }
  console.log(`Contact sheet: ${sheet}`);
  return 0;
}

function check(args) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true,
    options: { json: { type: 'boolean', default: false } } });
  if (positionals.length !== 1) throw new Error('Name one folder to check.');
  const folder = resolve(positionals[0]);
  const archive = join(folder, 'library.zip');
  if (!existsSync(archive)) throw new Error(`There is no icon library in ${folder}: it has no library.zip.`);
  const buffer = readFileSync(archive);
  const problems = checkLibrary(buffer, { id: basename(folder) });
  if (values.json) {
    console.log(JSON.stringify({ ok: !problems.length, problems }, null, 2));
    return problems.length ? 1 : 0;
  }
  if (problems.length) {
    console.log(`${folder} does not pass:`);
    for (const problem of problems) console.log(`  ${problem}`);
    return 1;
  }
  const { library, index } = summary(buffer);
  console.log(`${library.name} passes: ${index.icons.length} ${library.kind} icons.`);
  return 0;
}

function summary(buffer) {
  // Only called on an archive that passed checkLibrary.
  const files = readZip(buffer);
  return { library: JSON.parse(files.get('library.json').toString('utf8')),
    index: JSON.parse(files.get('icons.json').toString('utf8')) };
}

export async function main(args) {
  const [command, ...rest] = args;
  if (command === 'icons') return icons(rest);
  if (command === 'check') return check(rest);
  throw new Error(`pack ${command ?? ''} is not a pack command. Usage:\n${USAGE}`);
}
```

- [ ] **Step 5: Write `scripts/harness-brand.mjs`**

```js
#!/usr/bin/env node
// Harness Brand: brand packs and icon libraries for the studios' slides, blogs and infographics.
import { USAGE as PACK } from './pack.mjs';

const COMMANDS = { version: './version.mjs', pack: './pack.mjs' };

const USAGE = `Harness Brand: brand packs and icon libraries for the studios. It reads the brands
folder it is given and never changes it.
Usage: harness-brand <command> [options]

  version
${PACK}`;

const [command, ...rest] = process.argv.slice(2);
if (!command || command === '--help' || command === 'help') {
  console.log(USAGE);
  process.exit(0);
}
if (!Object.hasOwn(COMMANDS, command)) {
  console.error(`${command} is not a Harness Brand command.\n${USAGE}`);
  process.exit(2);
}
try {
  const { main } = await import(COMMANDS[command]);
  process.exitCode = await main(rest);
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
```

- [ ] **Step 6: Run the command tests to see them pass**

Run: `node --test tests/command.test.mjs`
Expected: `# pass 8`, `# fail 0`. Note that `pack check` on a broken archive prints its problems to standard output, and a refusal (such as a folder with no library) goes to standard error.

- [ ] **Step 7: Run the whole suite**

Run: `npm test`
Expected: `# fail 0`, with 51 tests passing (1 + 5 + 4 + 9 + 8 + 5 + 9 + 2 + 8).

- [ ] **Step 8: Commit**

```bash
git add scripts/harness-brand.mjs scripts/version.mjs scripts/pack.mjs tests/command.test.mjs
git commit -m "Add the harness-brand command with pack icons and pack check"
```

---

### Task 10: The icon library format document

**Files:**
- Create: `docs/icon-library-format.md`
- Test: `tests/format-doc.test.mjs`

- [ ] **Step 1: Write the failing test**

`tests/format-doc.test.mjs`:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { checkLibrary } from '../scripts/lib/icons/library.mjs';
import { writeZip } from '../scripts/lib/zip.mjs';

const doc = readFileSync(new URL('../docs/icon-library-format.md', import.meta.url), 'utf8');
const blocks = [...doc.matchAll(/```json\n([\s\S]*?)```/g)].map((m) => JSON.parse(m[1]));

test('the document\'s examples make a library that passes the check', () => {
  const library = blocks.find((block) => block.kind === 'glyph');
  const index = blocks.find((block) => Array.isArray(block.icons) && block.icons[0]?.paths);
  assert.ok(library && index, 'the document shows a glyph library.json and its icons.json');
  assert.deepEqual(checkLibrary(writeZip([['library.json', JSON.stringify(library)],
    ['icons.json', JSON.stringify(index)]]), { id: library.id }), []);
});

test('the document names every field the check reads', () => {
  for (const field of ['schema', 'id', 'name', 'version', 'kind', 'source', 'usage', 'slug',
    'category', 'keywords', 'bounds', '"paths"', 'file']) {
    assert.ok(doc.includes(field), `the document does not mention ${field}`);
  }
});
```

- [ ] **Step 2: Run it to see it fail**

Run: `node --test tests/format-doc.test.mjs`
Expected: FAIL, `ENOENT` for `docs/icon-library-format.md`.

- [ ] **Step 3: Write `docs/icon-library-format.md`**

````markdown
# Icon library format

An icon library is a set of icons kept once, in the brands folder, for any brand to use.
Harness Brand reads it; it can be made with `harness-brand pack icons`, by hand, or with
any tool that writes the files below.

## Where a library lives

```
brands/
  icon-libraries/            this name is never a brand id
    <id>/
      sources/               what the library was made from, kept as received (optional)
      library.zip            the library
      contact-sheet.svg      every icon on one page, for review (optional)
```

`<id>` is lower-case letters, digits and hyphens, and is the same as the `id` inside the
library.

## library.zip

A ZIP archive holding:

| Path | Required | What it is |
|---|---|---|
| `library.json` | yes | what the library is |
| `icons.json` | yes | every icon |
| `svg/<category>/<slug>.svg` | for pictures | the drawings; optional for glyphs |

### library.json

```json
{
  "schema": 1,
  "id": "vmware-functional",
  "name": "VMware by Broadcom functional icons",
  "version": "2025-07",
  "kind": "glyph",
  "source": "VMware by Broadcom Functional Icons library, July 2025",
  "usage": "Colour only with the brand's icon colours. Never outline, shadow, distort or mix sizes in a row."
}
```

| Field | Required | Meaning |
|---|---|---|
| `schema` | yes | `1` |
| `id` | yes | the folder's name |
| `name` | yes | the library's name, for people |
| `version` | yes | text; any scheme, such as a date or `1.2` |
| `kind` | yes | `glyph` or `picture` (below) |
| `source` | no | where the icons came from |
| `usage` | no | the library's rules, in plain words; shown wherever the icons are chosen |

**glyph**: every icon is one single-colour shape. A brand colours it from its own colours,
and slides place it as a native, editable shape.

**picture**: every icon is a drawing kept in its own colours, such as a product logo or a
partner's architecture icon. It is placed as a picture. Blogs and infographics use
pictures; slides do not place them as icons.

### icons.json

```json
{
  "schema": 1,
  "icons": [
    {
      "slug": "cloud-1",
      "name": "Cloud 1",
      "category": "Cloud",
      "keywords": ["hybrid", "multi-cloud"],
      "bounds": [12.5, 22, 87.5, 78],
      "paths": ["M12.5 50 L50 22 L87.5 50 L50 78 Z"]
    }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `slug` | yes | the icon's id: lower-case letters, digits and hyphens, unique in the library |
| `name` | yes | the icon's name, for people |
| `category` | yes | its group, such as `Cloud` or `Business Tools / Objects` |
| `keywords` | no | more words to find it by |
| `bounds` | glyphs | `[x0, y0, x1, y1]`, the box around the shape, in the 0 to 100 box |
| `paths` | glyphs | the shape, as a list of SVG path data in a 0 to 100 box. Each path is filled even-odd on its own and all are painted together in one colour, so where paths overlap they add up. No colour and no container circle |
| `file` | pictures | the drawing's path in the archive, such as `svg/logos/spring.svg` |

A picture's drawing may not hold a script.

## Making a library with Harness Brand

```bash
harness-brand pack icons <source>... --library ID --name NAME [--kind glyph|picture] \
  [--fill F] [--fill-for SOURCE=F]... [--version V] [--usage TEXT] --into brands/icon-libraries/ID
```

A source is a Claude Design export ZIP, a folder of SVGs, a ZIP of SVGs, or anything that
holds an `icons.json` drawn in a 0 to 100 box. An `icons.json` that gives each icon one `d`
instead of `paths` (as Broadcom's export does) is read as a list of one path. With several sources, the first one's icons
win where slugs meet, and later sources add the icons the first lacks; their categories are
matched to the first source's where they plainly mean the same.

For a glyph library, each SVG becomes one shape:

- Each of its `path`, `rect`, `circle`, `ellipse`, `polygon` and `polyline` elements is
  taken with its transforms and becomes one path of the glyph; an exact repeat is dropped.
  Hidden and clear shapes are left out. Lines with no fill cannot be a glyph.
- A shape drawn through a mask takes the mask's shapes as the glyph. A mask that cuts holes
  with black shapes cannot be held and the icon is left out.
- When the first shape covers the whole view box in a colour no other shape uses, it is the
  container and is dropped.
- A drawing that uses `<use>`, a clip path or a style sheet is left out rather than drawn
  wrongly.
- The view box is scaled to fill `F` of the 0 to 100 box, centred (1 unless given). Use
  the share the library's own notes give: an icon cut at 88% of its circle takes 0.88.

Category comes from the SVG's folder (without a leading `Functional ` or `Icons `), and
the name from the folder's `README.md` table row for the file, else from the file name.
Every icon left out is listed with why; the command never stops on one icon.

`harness-brand pack check brands/icon-libraries/ID` checks a library against this format
and lists each problem in a sentence.
````

- [ ] **Step 4: Run it to see it pass**

Run: `node --test tests/format-doc.test.mjs`
Expected: `# pass 2`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add docs/icon-library-format.md tests/format-doc.test.mjs
git commit -m "Write down the icon library format"
```

---

### Task 11: Build vmware-functional from the three exports and review it

This builds the real library in a scratch folder, outside both repositories, so the
person can review it. It is placed in the team's `brands/` folder in Plan 3.

**Files:** none in the repository.

- [ ] **Step 1: Build the library**

```bash
cd ~/Projects/harness-brand-skill
OUT="$TMPDIR/harness-brand-review/vmware-functional"
node scripts/harness-brand.mjs pack icons \
  broadcom-design-system.zip vmware-by-broadcom-design-system.zip tanzu-division-design-system.zip \
  --library vmware-functional --name "VMware by Broadcom functional icons" --version 2025-07 \
  --fill-for tanzu-division-design-system.zip=0.88 \
  --into "$OUT" --replace --json > "$TMPDIR/harness-brand-review/report.json"
echo "exit $?"
node -e 'const r=require(process.argv[1]);console.log(r.icons,"icons");console.log(r.sources);console.log(r.skipped.length,"left out");for(const s of r.skipped.slice(0,20))console.log(" ",s.source,s.file,s.reason)' "$TMPDIR/harness-brand-review/report.json"
```

Expected: `exit 0`, 920 icons: `broadcom-design-system.zip` adds 858 (five of its slugs
are used twice for different drawings; the second of each is renamed from its name),
`vmware-by-broadcom-design-system.zip` adds 31 and `tanzu-division-design-system.zip`
adds 31. None are left out. (Counts from a dry run of this plan on 3 November 2026.)

- [ ] **Step 2: Check the Tanzu Division scale against Broadcom's on shared icons**

The 0.88 fill comes from the Tanzu Division README. Compare converted Tanzu glyphs with
Broadcom's for the same slugs. A ratio near 1 confirms it.

```bash
cd ~/Projects/harness-brand-skill
node --input-type=module -e '
import { readFileSync } from "node:fs";
import { readZip } from "./scripts/lib/zip.mjs";
import { sourceFiles, readSource } from "./scripts/lib/icons/sources.mjs";
import { convertSvg } from "./scripts/lib/icons/svg-glyph.mjs";
const bc = new Map(readSource(sourceFiles("broadcom-design-system.zip")).icons.map((i) => [i.slug, i]));
for (const [file, fill] of [["tanzu-division-design-system.zip", 0.88], ["vmware-by-broadcom-design-system.zip", 1]]) {
  const ratios = [];
  for (const d of readSource(sourceFiles(file)).drawings) {
    const theirs = bc.get(d.slug); if (!theirs) continue;
    const g = convertSvg(d.text, { fill }); if (g.skip) continue;
    const w = (b) => b[2] - b[0];
    if (w(theirs.bounds) > 5) ratios.push(w(g.bounds) / w(theirs.bounds));
  }
  ratios.sort((a, b) => a - b);
  console.log(file, "shared", ratios.length, "median width ratio", ratios[Math.floor(ratios.length / 2)].toFixed(3));
}'
```

Expected: both medians between 0.97 and 1.03 (the dry run gave 1.000 for Tanzu Division at
0.88 and 0.989 for VMware by Broadcom at 1). If Tanzu Division's is off, rebuild with
the fill that brings it to 1 (`0.88 / ratio`), and record the value used in the library's
`usage` note.

- [ ] **Step 3: Check the result**

```bash
cd ~/Projects/harness-brand-skill
node scripts/harness-brand.mjs pack check "$TMPDIR/harness-brand-review/vmware-functional"
```

Expected: `VMware by Broadcom functional icons passes: N glyph icons.`, where N matches
Step 1.

- [ ] **Step 4: Have the person review the contact sheet**

Render the sheet for the person, writing out the full path of the result:
`rsvg-convert -w 1440 contact-sheet.svg -o contact-sheet.png` (Homebrew's librsvg), or open
the SVG in a browser. Ask them to look for icons that are filled
where they should be open (a cut-out drawn as a solid), off-centre, or the wrong size
next to their neighbours, especially among the icons added from the Tanzu Division and
VMware by Broadcom sets (they come after Broadcom's 858). The dry run found the conversions
sound; it also found that several added icons are `-v2` redesigns or near-duplicates of
Broadcom icons under other names, which the person may want to keep or drop. Report the counts from Step 1,
the ratios from Step 2, and every icon left out with why.

- [ ] **Step 5: Fix what the review finds, test first**

For each wrongly converted icon, add a test to `tests/svg-glyph.test.mjs` with a minimal
SVG of the same structure (copy the structure, not the artwork), see it fail, fix
`scripts/lib/icons/svg-glyph.mjs`, run `npm test`, rebuild (Step 1), and commit:

```bash
git add scripts/lib/icons/svg-glyph.mjs tests/svg-glyph.test.mjs
git commit -m "Convert icons drawn as <the structure that was wrong> correctly"
```

If the review finds nothing, there is nothing to commit.

---

### Task 12: Finish

- [ ] **Step 1: Run the whole suite once more**

Run: `npm test`
Expected: `# fail 0`.

- [ ] **Step 2: Show the branch to the person**

```bash
git log --oneline main..HEAD
git status --short
```

Expected: the commits from Tasks 1 to 11 and a clean tree. Do not push. Tell the person
the branch name, what the review found, and that Plan 2 (brand pack commands) is next.
