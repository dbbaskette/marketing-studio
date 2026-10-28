/* Real protected Marketing Studio → Infographic Studio → Marketing Studio round trips. */
const {chromium} = require('playwright');
const {spawn} = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');
(async () => {
  const renderer = process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER;
  if (!renderer) throw Error('Supply the installed test renderer.');
  const child = spawn(process.env.PYTHON || 'python3', [path.join(__dirname, 'fixture_server.py'), '--renderer', renderer, '--suite'], {stdio: ['ignore', 'pipe', 'pipe']});
  let browser;
  try {
    const url = await new Promise((resolve, reject) => {
      let output = '';
      const timer = setTimeout(() => reject(Error('Suite fixture startup timed out')), 15000);
      child.stdout.on('data', data => {
        output += data;
        if (output.startsWith('http://') && output.includes('\n')) {clearTimeout(timer); resolve(output.split('\n')[0]);}
      });
      child.once('exit', () => {clearTimeout(timer); reject(Error('Suite fixture exited before startup'));});
    });
    const home = new URL(url), expected = new URLSearchParams(home.hash.slice(1)).get('token');
    browser = await chromium.launch({headless: true, executablePath: renderer});
    for (const phone of [false, true]) {
      const context = await browser.newContext({viewport: {width: phone ? 390 : 1280, height: 900}, hasTouch: phone});
      const errors = [];
      context.on('weberror', error => errors.push(error.error().message));
      const parent = await context.newPage();
      await parent.goto(url);
      const popup = phone ? null : parent.waitForEvent('popup');
      await parent.getByRole('button', {name: 'Open Infographic Studio', exact: true}).click();
      const studio = phone ? parent : await popup;
      await studio.getByRole('button', {name: 'New infographic', exact: true}).waitFor();
      // The return metadata must survive a native-page reload after removing its fragment.
      await studio.reload();
      await studio.getByRole('button', {name: 'New infographic', exact: true}).waitFor();
      const link = studio.getByRole('link', {name: 'Marketing Studio', exact: true});
      const target = new URL(await link.getAttribute('href'));
      assert.equal(target.origin, home.origin);
      assert.equal(target.search, '');
      assert.equal(new URLSearchParams(target.hash.slice(1)).get('token'), expected);
      assert.equal(await link.getAttribute('target'), phone ? null : 'marketing-studio');
      // Closing the parent loses its tab memory. A fresh return tab must authenticate again.
      if (!phone) await parent.close();
      const authenticated = context.waitForEvent('response', {predicate: response => response.url() === home.origin + '/api/home'});
      await link.click();
      const response = await authenticated;
      assert.equal(response.status(), 200);
      const returned = response.request().frame().page();
      await returned.getByRole('button', {name: 'Open Infographic Studio', exact: true}).waitFor();
      assert(!await returned.getByText(/This page needs its private link/).isVisible());
      assert.deepEqual(errors, []);
      await context.close();
    }
    console.log('PASS: authenticated desktop/phone suite round trips, missing parent storage, native reload, fragment-only return key, and tab targeting. Synthetic isolated settings; no providers.');
  } finally {
    if (browser) await browser.close();
    child.kill('SIGTERM');
    await new Promise(resolve => {const timer = setTimeout(() => {child.kill('SIGKILL'); resolve();}, 5000); child.once('exit', () => {clearTimeout(timer); resolve();});});
  }
})().catch(() => {console.error('FAIL: protected suite return journey. No private URLs are logged.'); process.exitCode = 1;});
