/* Private intake write ordering and payload size, with a scripted local adapter only. */
const assert=require('node:assert/strict');
global.document={querySelectorAll:()=>[]};
const {Intake}=require('../ui-kit/drafting.js');
(async()=>{
 let held={revision:0,draft:null},release,blocked=false;const calls=[];
 const intake=new Intake(async sent=>{
  calls.push(sent);
  if(sent.action==='read')return structuredClone(held);
  if(sent.action==='save'){
   if(blocked)await new Promise(resolve=>release=resolve);
   assert.equal(sent.expected,held.revision);
   held={revision:held.revision+1,draft:{...(held.draft||{}),...sent.patch}};
  }else held={revision:held.revision+1,draft:null};
  return structuredClone(held);
 });
 await intake.load();
 const draft={title:'First',step:0,upload:{name:'synthetic.pptx',encoded:'x'.repeat(1_000_000)}};
 await intake.keep(draft);
 blocked=true;draft.title='Second';const saving=intake.keep(draft);
 await new Promise(resolve=>setImmediate(resolve));
 draft.title='Third';intake.keep(draft);draft.title='Last';intake.keep(draft);
 blocked=false;release();await saving;
 assert.equal(held.draft.title,'Last','coalescing keeps the latest text');
 const saves=calls.filter(c=>c.action==='save');
 assert.equal(saves.length,3,'one active write and the latest queued update');
 assert(saves.slice(1).every(c=>!('upload' in c.patch)),'unchanged upload bytes are not resent for typing');
 assert(saves.slice(1).every(c=>JSON.stringify(c).length<500),'incremental text writes stay small');
 await intake.keep(draft,false);assert.equal(held.draft.intakeOpen,false);
 draft.title='Last queued edit';intake.queue(draft);
 await intake.discard();assert.equal(held.draft,null);
 await new Promise(resolve=>setTimeout(resolve,300));assert.equal(held.draft,null,'discard cannot resurrect a queued draft');
 const refusing=new Intake(async sent=>sent.action==='read'?{revision:2,draft:{title:'Newer'}}:Promise.reject(Error('Changed in another tab.')));
 const local={title:'Local answer',step:1};
 assert.equal(await refusing.keep(local),false);assert.equal(local.title,'Local answer');
 assert.match(refusing.problem,/another tab/);
 console.log('PASS intake coalescing, private revision ordering, unchanged-upload payloads, close/discard and conflict retention');
})().catch(error=>{console.error(error);process.exitCode=1;});
