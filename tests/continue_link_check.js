/* Continue in another studio's two links, with their real scripts and no network:
 * StudioShell.continueLink (core/studio_core/deck_web/shell.js), which a studio calls for a
 * document it kept, and the home page's reading of `continue=` (setup_web/app.js). */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');

const ROOT = path.join(__dirname, '..');
const shellSource = fs.readFileSync(path.join(ROOT, 'core/studio_core/deck_web/shell.js'), 'utf8');
const HOME = 'http://127.0.0.1:8790';
const KEY = 'home-fixture-token';

// A shell loaded on a studio page at `hash`, with `saved` in this tab's memory.
function shellAt(hash, saved = null, here = { protocol: 'http:', hostname: '127.0.0.1', port: '8791' }) {
  const memory = new Map(saved ? [['marketing-studio-return', JSON.stringify(saved)]] : []);
  const body = { dataset: {}, append() {}, querySelectorAll: () => [] };
  const document = { readyState: 'complete', body, documentElement: { style: {} }, activeElement: null,
    querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, createElement: () => ({}) };
  const context = vm.createContext({ document, navigator: { platform: 'MacIntel' }, window: {},
    location: { ...here, hash }, sessionStorage: { getItem: (name) => memory.get(name) ?? null, setItem: (name, value) => memory.set(name, value) },
    URLSearchParams, JSON, Object, Array, String, Number, Math, Set, Map, Promise, Error, encodeURIComponent });
  vm.runInContext(shellSource + '\nthis.StudioShell = StudioShell;', context);
  return context.StudioShell;
}

const launched = '#token=studio-key&home=' + encodeURIComponent(HOME) + '&homeToken=' + KEY;
const shell = shellAt(launched);
const doc = { id: 'launch-0a1b2c3d4e', revision: 2 };
assert.equal(shell.continueLink(doc), HOME + '/#token=' + KEY + '&continue=launch-0a1b2c3d4e@2');
// A studio's own record of what the library kept says `document` for the id.
assert.equal(shell.continueLink({ document: 'launch-0a1b2c3d4e', revision: 3 }), HOME + '/#token=' + KEY + '&continue=launch-0a1b2c3d4e@3');
for (const wrong of [null, {}, { id: 'Launch', revision: 1 }, { id: 'a&token=x', revision: 1 }, { id: '../x', revision: 1 },
  { id: 'ok', revision: '1' }, { id: 'ok', revision: 0 }, { id: 'ok', revision: 1.5 }, { id: 'ok', revision: 1001 }, { id: 'a'.repeat(65), revision: 1 }]) {
  assert.equal(shell.continueLink(wrong), null, JSON.stringify(wrong));
}
// Run alone (no home in its link, nothing kept in this tab): no link.
assert.equal(shellAt('#token=studio-key').continueLink(doc), null);
assert.equal(shellAt('').continueLink(doc), null);
// A page that cleared its fragment first still has what its way back kept in this tab.
assert.equal(shellAt('', { home: HOME, token: KEY }).continueLink(doc), HOME + '/#token=' + KEY + '&continue=launch-0a1b2c3d4e@2');
// Only Marketing Studio's home on this host, another port, with a key of its own shape.
for (const hash of ['#home=' + encodeURIComponent('http://elsewhere.example:8790') + '&homeToken=' + KEY,
  '#home=' + encodeURIComponent('https://127.0.0.1:8790') + '&homeToken=' + KEY,
  '#home=' + encodeURIComponent('http://127.0.0.1:8791') + '&homeToken=' + KEY,
  '#home=' + encodeURIComponent('http://127.0.0.1:8790/api') + '&homeToken=' + KEY,
  '#home=' + encodeURIComponent(HOME) + '&homeToken=' + encodeURIComponent('short'),
  '#home=' + encodeURIComponent(HOME) + '&homeToken=' + encodeURIComponent(KEY + '&continue=evil@1')]) {
  assert.equal(shellAt(hash).continueLink(doc), null, hash);
}
assert.equal(shellAt('', { home: 'http://elsewhere.example:8790', token: KEY }).continueLink(doc), null);

// The home page reads `continue=<id>@<revision>` and nothing else of it.
const app = fs.readFileSync(path.join(ROOT, 'core/studio_core/setup_web/app.js'), 'utf8');
const found = /function libraryContinue\(options\) \{[\s\S]*?\n\}/.exec(app);
assert.ok(found, 'the home page reads continue= with libraryContinue');
const reading = vm.createContext({ URLSearchParams, Number });
vm.runInContext(found[0] + '\nthis.read = (hash) => libraryContinue(new URLSearchParams(hash));', reading);
assert.deepEqual(JSON.parse(JSON.stringify(reading.read('token=k&continue=launch-0a1b2c3d4e@2'))), { id: 'launch-0a1b2c3d4e', revision: 2 });
for (const hash of ['', 'continue=', 'continue=Launch@1', 'continue=a@0', 'continue=a@1001', 'continue=a@01',
  'continue=a%26token%3Dx@1', 'continue=a@1@2', 'continue=../a@1']) {
  assert.equal(reading.read(hash), null, hash);
}
// It opens the Library on that document with the chooser, and a studio's tab can ask again.
assert.match(app, /continueWanted \? 'library' : 'home'/);
assert.match(app, /await libraryCatalog\.continueWith\(id, revision\)/);
assert.match(app, /continueIn: \{studios: continueStudios, open: continueInStudio\}/);
assert.match(app, /api\('open', \{studio: studio\.id, library: \{id: doc\.id, revision: doc\.revision\}\}\)/);
console.log('continue link check passed');
