/* Exercise the actual native catchUp functions; no browser, providers or real state. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
(async()=>{
 for(const product of ['training','presentation']){
  const text=fs.readFileSync(path.join(__dirname,`../studios/${product}/skills/${product}-studio/scripts/desk/app.js`),'utf8');
  const start=text.indexOf('async function catchUp(compact = false) {'),end=text.indexOf('\n}\n',start)+2;
  const calls=[];let now=1000,signal={revision:'known',complete:false,cached:true,active:false};
  const view={runner:true,setup:true,listing:{},decks:{},setupAt:1000,pollRevision:'known',fullReadAt:1000,pollFailures:0};
  const context=vm.createContext({view,document:{hidden:true},Date:{now:()=>now},SETUP_HIDDEN:600000,ask:async route=>{calls.push(route);return route==='updates'?signal:{};},took:()=>{},notify:()=>{},setTitle:()=>{}});
  vm.runInContext(text.slice(start,end),context);
  const check=async(full,compact=true)=>{calls.length=0;await vm.runInContext(`catchUp(${compact})`,context);assert.equal(calls.filter(c=>c!=='updates').length,full?1:0,product+' '+JSON.stringify({signal,compact,now}));assert.equal(view.pollFailures,0);};
  await check(false); // Explicitly cached, not a claim that the pending scan completed.
  signal.cached=false;await check(true); // No completed scan / expired cache fails open.
  signal.cached=true;view.pollFailures=1;await check(true);
  signal.active=true;await check(true);
  signal.active=false;signal.revision='changed';await check(true);
  await check(false);await check(true,false); // Foreground/noncompact catch-up stays authoritative.
  now+=60001;await check(true); // Missed-event recovery is still mandatory.
  signal.complete=true;signal.cached=false;await check(false);
 }
 console.log('PASS both native polling policies: cache, expiry, changes, active work and periodic catch-up');
})().catch(error=>{console.error(error);process.exitCode=1;});
