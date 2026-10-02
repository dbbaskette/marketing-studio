#!/usr/bin/env node
// Execute the shipped prompt generator with a minimal DOM; no browser/network.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(path.join(__dirname, '../../preview/blog-studio.html'), 'utf8');
const element = () => ({addEventListener(){}, classList:{toggle(){}}, textContent:'', innerHTML:''});
const context = vm.createContext({document:{getElementById:element, querySelectorAll:()=>[]}});
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
const cases = [
  ['existing','A revised draft or feedback'], ['first-draft','A first draft'],
  ['outline-only','An outline'], ['from-outline','A first draft'],
  ['interview','An outline'], ['discover','Topic options and a brief']
];
const prompts = {};
for (const [mode, stop] of cases) {
  vm.runInContext(`Object.assign(state, ${JSON.stringify({mode, material:'notes', voice:'tone', tone:'Direct, warm; no sales CTA.', topic:'Handoff notes', audience:'Team leads', notes:'Tuesday: six notes inspected; two omitted next owner. No throughput measurement.'})})`, context);
  const prompt = vm.runInContext('handoff()',context);
  assert.ok(prompt.includes(`Stop at: ${stop}.`));
  assert.ok(prompt.includes('No throughput measurement.'));
  assert.ok(prompt.includes('Direct, warm; no sales CTA.'));
  assert.ok(!/\/Users\/|[A-Z]:\\Users\\/.test(prompt), 'Generated request must be portable');
  prompts[mode] = prompt;
}
vm.runInContext("Object.assign(state,{mode:'outline-only',material:'attach',notes:'',voice:'build',linkedin:'https://www.linkedin.com/in/example-pilot/',blogs:'Authored sample: Name the next owner. Leave a clear decision.'})",context);
const upload = vm.runInContext('handoff()',context);
assert.ok(upload.includes('Please wait for it.'));
assert.ok(upload.includes('LinkedIn background:'));
assert.ok(upload.includes('My authored writing:'));
prompts['upload-and-voice'] = upload;
process.stdout.write(JSON.stringify({status:'passed',scope:'Generated text only; no live harness/upload claim',prompts},null,2)+'\n');
