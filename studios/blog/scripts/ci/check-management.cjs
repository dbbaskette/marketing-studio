// Exercise the actual desk functions with a disposable DOM and controlled API responses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.attributes={};this.listeners={};this.hidden=false;this.disabled=false;this.value='';this.textContent='';this.className='';this.dataset={};if(tag==='textarea')Object.defineProperty(this,'type',{get:()=> 'textarea'});}
  append(...children){this.children.push(...children);for(const child of children)child.parent=this;}
  get firstElementChild(){return this.children[0]||null;}
  get parentElement(){return this.parent||null;}
  prepend(...children){this.children.unshift(...children);for(const child of children)child.parent=this;}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(child=>child!==this);}
  replaceChildren(...children){this.children=[];this.append(...children);}
  setAttribute(key,value){this.attributes[key]=value;}
  removeAttribute(key){delete this.attributes[key];}
  addEventListener(key,fn){this.listeners[key]=fn;}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  querySelectorAll(selector){return this.children.flatMap(c=>[...(selector.startsWith('.')&&c.className.split(' ').includes(selector.slice(1))?[c]:selector==='[type=submit]'&&c.type==='submit'?[c]:['button','input','textarea','select'].includes(selector)&&c.tagName===selector?[c]:[]),...c.querySelectorAll(selector)]);}
  showModal(){this.open=true;}
  close(){this.open=false;}
  focus(){this.focused=true;}
  select(){this.selected=true;}
}
function descendants(node){return node.children.flatMap(c=>[c,...descendants(c)]);}
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
function fixture(responder=()=>({items:[],total:0})){
  const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
  const document={getElementById:get,createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t),createDocumentFragment:()=>new Element('fragment'),createTextNode:text=>{const node=new Element('#text');node.textContent=text;return node;},querySelector:s=>s==='dialog[open]'?[...nodes.values()].find(n=>n.open):null,querySelectorAll:s=>[...nodes.values()].flatMap(n=>n.querySelectorAll(s))};
  const stored=new Map();
  const context=vm.createContext({document,location:{hash:'#fixture',pathname:'/'},sessionStorage:{getItem:key=>stored.get(key)||'',setItem:(key,value)=>stored.set(key,value),removeItem:key=>stored.delete(key)},history:{replaceState:()=>{},pushState:()=>{}},window:{},URLSearchParams,AbortController,Uint8Array,TextEncoder,btoa,FormData:class{constructor(form){this.values=descendants(form).filter(e=>e.name).map(e=>[e.name,e.value]);}[Symbol.iterator](){return this.values[Symbol.iterator]();}},confirm:()=>true,crypto:{getRandomValues:values=>require('node:crypto').webcrypto.getRandomValues(values)},setInterval:()=>0,setTimeout:()=>0,fetch:async(url,options)=>{const result=await responder(url,options);return result&&result.__http?{ok:false,status:result.__http,json:async()=>result}:{ok:true,status:200,json:async()=>result};},console});
  const source=fs.readFileSync('skills/blog-studio/assets/management/app.js','utf8').split("for(const b of document.querySelectorAll('[data-view]'))")[0];
  vm.runInContext(source,context);
  vm.runInContext("access={status:'local-only',message:'Local only',actions:{edit:true,memory:false,refresh:false}}",context);
  return {get,nodes,run:code=>vm.runInContext(code,context),set:(name,value)=>{context[name]=value;},loadRunner:()=>{vm.runInContext(fs.readFileSync('skills/blog-studio/assets/management/markdown.js','utf8'),context);vm.runInContext(fs.readFileSync('skills/blog-studio/assets/management/runner.js','utf8').split('// Keep initialization below this marker')[0],context);}};
}
async function check(){
  const lan=fixture();
  assert.equal(lan.run('typeof crypto.randomUUID'),'undefined');
  assert.match(lan.run('operationId()'),/^[0-9a-f]{32}$/);
  assert.notEqual(lan.run('operationId()'),lan.run('operationId()'));
  assert.equal(lan.run("operationFor('save',{id:'fixture'})"),lan.run("operationFor('save',{id:'fixture'})"));
  const f=fixture();const dialog=f.get('detail-dialog');dialog.open=true;
  f.run("notice('Reload before saving.',true)");
  assert.equal(dialog.querySelector('.dialog-notice').textContent,'Reload before saving.');
  assert.equal(dialog.querySelector('.dialog-notice').attributes.role,'alert');
  assert.equal(f.get('notice').textContent,'');
  dialog.open=false;
  f.set('result',{receipts:[{label:'Reference',message:'Shared with the Team Hub.'},{label:'Blog',message:'Saved locally; Hub sync needs attention.'}]});
  f.run('savedNotice(result)');assert.match(f.get('notice').textContent,/Blog: Saved locally/);
  const pending=fixture(()=>({items:[{id:'fixture',label:'Blog',sharing:'pending-review',message:'Waiting for contribution review.',retry:true}]}));
  pending.run('access.actions.edit=true');await pending.run('loadReceipts()');assert.equal(pending.get('sync-status').hidden,false);
  assert.equal(pending.get('sync-status').children[0].children[1].textContent,'Retry sync');
  await capabilityAndMemory();
  await articleDisclosure();
  await requestOrdering();
  await curationConflict();
  await historicalImport();
  await diffOnlyForms();
  await privacyChoiceAndIdentity();
  await unreadableBlogsAndBadges();
  await busyAnalysis();
  await refreshWithNewSelection();
  await guidedRuns();
  await googleIntake();
  await googleReopening();
  await manuscriptEditing();
  await reviewInteractions();
  await editorTransitions();
  await commentCompletionAndFailure();
  await pendingEditorSaves();
  await manualEditingJourneys();
  await writingReviewJourneys();
  await taskJourneys();
  await revisionCompletion();
  await deliveryRecovery();
  await brandInputs();
  await contextualTools();
  await sharedSettings();
  await staleSharedForms();
  await sharedPattern();
  await finishAndDelete();
  await filesJourney();
  await voiceLinksJourney();
  pageDefinesEveryElement();
  const checks=['feedback','access and memory kinds','request ownership','curation conflicts','article/finding disclosures',
    'historical import preview/batching and source controls','diff-only saves and explicit ready/published confirmation',
    'analysis disclosure and per-operation choice','unreadable-blog notes','badge class whitelist','busy state',
    'refresh with a new selection','guided run decisions and handoff controls','Google manuscript preview, confirmation and reopening','review selection, preserved wording, late reads and in-flight saves','manual feedback and comments-only completion','brand skill inputs and confirmation','shared settings refusal/reload/retry','stops, now line, honest retry, note and phone toolbar','finish, done card, typed-title delete, restore and idea picks','new blog from my files: one screen, per-file text and roles, the point path, Write as, angle picks, none of these and check detail lines','voice samples from a list of links: suggested author, scope check, one site, batches, byline keep and learning','element ids'];
  console.log(JSON.stringify({status:'passed',checks:checks.join('; ')}));
}
function controlled(){
  const requests=[];
  const f=fixture((url,options)=>{
    if(url==='/api/receipts')return {items:[]};
    const pending=deferred();requests.push({url,options,...pending});return pending.promise;
  });
  return {...f,requests};
}
async function manuscriptEditing(){
  let state={id:'fixture',title:'Synthetic author draft',content:'The delay matters.',expected:'v1',google:{url:'https://docs.google.com/document/d/fixture/edit'},proposals:[],findings:[],baseline:'The delay matters.',diff:[],checks:{polish:{status:'not-run'}},working:false};
  const writes=[];const f=fixture((url,options)=>{
    if(url.startsWith('/api/manuscript?'))return state;
    if(url.startsWith('/api/run?'))return state.operation;
    if(url==='/api/run-options')return {sources:[]};
    if(options?.body){const data=JSON.parse(options.body);writes.push({url,data});
      if(url==='/api/editor-check'){state={...state,operation:{id:'fixture',expected:'run1',status:'working',error:'',enabled:true,next:'review',editor_check:'polish'},working:true};return state.operation;}
      if(url==='/api/editor-proposals'){state={...state,proposals:data.proposals,expected:'v3'};return state;}
      if(url==='/api/editor-google-plan')return {plan:'a'.repeat(32),target:state.google.url,count:state.proposals.length,mode:'auto',expected:state.expected,proposals:state.proposals};
      if(url==='/api/editor-google-send')return {status:'verified-pending'};
    }return {items:[]};
  });f.loadRunner();await f.run("sRoute('editor','fixture')");
  const nodes=()=>descendants(f.get('studio-page'));
  assert.equal(nodes().find(e=>e.id==='editor-check').value,'polish');
  assert.equal(nodes().some(e=>e.textContent==='Polish writing'),true);
  const form=nodes().find(e=>e.tagName==='form');await form.listeners.submit({preventDefault(){}});
  assert.equal(writes[0].url,'/api/editor-check');assert.equal(writes[0].data.research,'none');
  assert.equal(f.run('studio.screen'),'editor');assert.ok(nodes().some(e=>e.textContent==='Polishing your document'));
  state={...state,working:false,operation:{...state.operation,status:'waiting-for-approval'},findings:[{id:'plain',kind:'edit',before:'delay',after:'wait',reason:'Plainer wording.',evidence:'Editorial judgment',verdict:'editorial'}]};
  await f.run('sPoll()');
  assert.ok(nodes().some(e=>e.textContent==='wait'),'show proposed replacement beside original');
  assert.equal(f.get('actions').children.some(e=>e.textContent==='Approve'),false);
  await f.run("sRoute('gate','fixture','review')");assert.equal(f.run('studio.screen'),'editor','old focused-review links use the workflow');
  const preferred=nodes().find(e=>e.id==='wording-0');preferred.value='pause';preferred.listeners.input();
  await descendants(f.get('actions')).find(e=>e.textContent==='Use this change').listeners.click();
  assert.equal(state.proposals.length,1);assert.equal(state.proposals[0].after,'pause');
  assert.equal(writes.some(r=>r.url==='/api/editor-google-send'),false,'finish preview only reads Google');
  assert.equal(writes.filter(r=>r.url==='/api/editor-google-plan').length,1);
  assert.ok(nodes().some(e=>e.textContent==='Send to the original Google Doc'));
  await nodes().find(e=>e.textContent==='Send feedback to Google').listeners.click();
  assert.equal(writes.find(r=>r.url==='/api/editor-google-send').data.confirmed,true);
  assert.ok(nodes().some(e=>e.textContent==='Feedback sent'));
  assert.equal(nodes().some(e=>e.textContent==='Send feedback to Google'),false,'verified delivery does not offer a duplicate send');
  assert.equal(writes.filter(r=>r.url==='/api/editor-google-plan').length,1,'success does not prepare another write');
  f.run('studio.editorDelivery=null');await f.run("sRoute('editor','fixture','finish')");
  assert.ok(nodes().some(e=>e.textContent==='Feedback sent'),'refresh keeps the verified delivery result');
  assert.equal(writes.filter(r=>r.url==='/api/editor-google-plan').length,1);

  f.run("studio.editorDelivery={id:'fixture',expected:'v3',status:'local',message:'Saved locally'}");await f.run("sRoute('editor','fixture','finish')");
  assert.ok(nodes().some(e=>e.textContent==='Send feedback to Google'),'saving locally still permits sending selected feedback');
  assert.equal(nodes().some(e=>e.textContent==='Apply selected edits to local draft'),false);

}

async function reviewInteractions(){
  let state={id:'selection',title:'Selection fixture',content:'Old wording. Other wording.',expected:'v1',google:null,proposals:[],findings:[{id:'one',kind:'edit',before:'Old wording.',after:'New wording.',reason:'Clearer.'},{id:'two',kind:'comment',before:'Other wording.',reason:'Explain this.'}],checks:{},working:false};
  const writes=[];let refuse=true;
  const f=fixture((url,options)=>{if(url.startsWith('/api/manuscript?'))return state;if(url==='/api/editor-proposals'){writes.push(JSON.parse(options.body));if(refuse)return {__http:409,error:'Reload before saving.'};state={...state,expected:'v2',proposals:writes.at(-1).proposals};return state;}return {items:[]};});f.loadRunner();await f.run("sRoute('editor','selection','changes')");
  const nodes=()=>descendants(f.get('studio-page')),next=()=>descendants(f.get('actions')).find(e=>e.className.includes('review-continue')),boxes=()=>nodes().filter(e=>e.type==='checkbox');
  assert.equal(boxes().every(box=>box.checked),true,'default selection is visible');
  assert.equal(next().textContent,'Use all 2 changes');
  await nodes().find(e=>e.textContent==='Clear selection').listeners.click();
  assert.equal(next().disabled,true);assert.ok(nodes().some(e=>e.textContent==='0 of 2 selected'));
  await next().listeners.click();assert.equal(writes.length,0,'clearing the selection never falls back to all changes');
  boxes()[0].checked=true;boxes()[0].listeners.change();
  const wording=nodes().find(e=>e.id==='wording-0');wording.value='Better wording.';wording.listeners.input();
  const manual=nodes().find(e=>e.id==='proposal-reason');manual.value='Keep this unfinished note.';manual.listeners.input();
  await f.run("sRoute('editor','selection','prepare')");await f.run("sRoute('editor','selection','changes')");
  assert.deepEqual(boxes().map(box=>box.checked),[true,false],'step navigation keeps skipped changes');
  assert.equal(nodes().find(e=>e.id==='wording-0').value,'Better wording.');
  assert.equal(nodes().find(e=>e.id==='proposal-reason').value,'Keep this unfinished note.');
  await next().listeners.click();
  assert.equal(writes.length,1);assert.equal(writes[0].proposals.length,1);assert.equal(writes[0].proposals[0].after,'Better wording.');
  assert.equal(nodes().find(e=>e.id==='wording-0').value,'Better wording.','a save conflict keeps the adjusted wording');
  assert.deepEqual(boxes().map(box=>box.checked),[true,false]);
  refuse=false;await next().listeners.click();assert.equal(f.run('studio.stage'),'finish');
  assert.equal(writes.at(-1).proposals[0].id,'one');
  state={...state,expected:'v3',proposals:[],findings:[{id:'fresh',kind:'edit',before:'Old wording.',after:'Fresh wording.',reason:'Fresh pass.'}]};
  await f.run("sRoute('editor','selection','changes')");
  assert.equal(boxes().length,1);assert.equal(nodes().find(e=>e.id==='wording-0').value,'Fresh wording.','a new document version resets old review choices');
  f.run('access.actions.edit=false');await f.run("sRoute('editor','selection','changes')");assert.equal(next().disabled,true);
}

async function editorTransitions(){
  const state={id:'race',title:'Stable title',content:'Saved text.',expected:'v1',google:null,proposals:[],findings:[],checks:{},working:false};
  let pending=false;const reads=[];
  const f=fixture(url=>{if(url.startsWith('/api/manuscript?')){if(!pending)return state;const next=deferred();reads.push(next);return next.promise;}return {items:[]};});f.loadRunner();await f.run("sRoute('editor','race','prepare')");
  const visible=f.get('studio-page').children[0];pending=true;
  const older=f.run("sRoute('editor','race','changes')");
  assert.equal(f.get('studio-page').children[0],visible,'step changes retain the current document while loading');
  assert.equal(f.get('title').textContent,'Stable title');assert.equal(f.get('studio-page').attributes['aria-busy'],'true');
  const latest=f.run("sRoute('editor','race','prepare')");
  reads[1].resolve(state);await latest;reads[0].resolve({...state,title:'Late title'});await older;
  assert.equal(f.get('title').textContent,'Stable title','an older same-document response cannot overwrite the current step');
  assert.equal(f.get('studio-page').attributes['aria-busy'],undefined);
  const plans=[];let sent;
  const google={...state,google:{url:'https://docs.google.com/document/d/fixture/edit'},proposals:[{id:'one',kind:'comment',before:'Saved text.',reason:'Clarify.'}]};
  const g=fixture((url,options)=>{if(url.startsWith('/api/manuscript?'))return google;if(url==='/api/editor-google-plan'){const plan=deferred();plans.push(plan);return plan.promise;}if(url==='/api/editor-google-send'){sent=JSON.parse(options.body);return {status:'verified-comments'};}return {items:[]};});g.loadRunner();
  const first=g.run("sRoute('editor','race','finish')");await new Promise(resolve=>setImmediate(resolve));
  const second=g.run("sEditor('race')");await new Promise(resolve=>setImmediate(resolve));
  plans[1].resolve({plan:'b'.repeat(32),expected:'v1',count:1,mode:'comments'});await second;
  plans[0].resolve({plan:'a'.repeat(32),expected:'v1',count:1,mode:'auto'});await first;
  await descendants(g.get('studio-page')).find(e=>e.textContent==='Send feedback to Google').listeners.click();
  assert.equal(sent.plan,'b'.repeat(32),'a late delivery preview cannot restore an older plan');
}

async function commentCompletionAndFailure(){
  const state={id:'comments',title:'Local comments',content:'Keep this text.',expected:'v1',google:null,proposals:[{id:'one',kind:'comment',before:'Keep this text.',reason:'Explain the audience.'}],findings:[],checks:{},working:false};
  const f=fixture(url=>url==='/api/run-options'?{sources:[]}:state);f.loadRunner();f.run('sDownload=async value=>{window.downloaded=value;}');await f.run("sRoute('editor','comments','finish')");
  const nodes=()=>descendants(f.get('studio-page'));
  assert.equal(nodes().some(e=>e.textContent==='Save 0 edits to my draft'),false);
  await nodes().find(e=>e.textContent==='Download feedback').listeners.click();
  assert.match(f.run('window.downloaded.content'),/Explain the audience/);assert.match(f.run('window.downloaded.content'),/> Keep this text/);
  state.proposals=[];state.operation={status:'failed',error:'A synthetic detailed validation error.',editor_check:'polish',next:'review'};
  await f.run("sRoute('editor','comments','prepare')");
  assert.ok(nodes().some(e=>e.textContent==='This review couldn’t finish'));
  assert.ok(nodes().some(e=>e.textContent==='Try again'));
  assert.equal(nodes().some(e=>e.textContent==='No changes suggested'),false,'failure never reads as a successful clean review');
  assert.equal(nodes().find(e=>e.textContent===state.operation.error).parentElement.tagName,'details','technical diagnostics remain secondary');
  assert.equal(nodes().find(e=>e.textContent==='2. Choose changes').disabled,false,'manual feedback remains available after a failed pass');
  state.findings=[{id:'old',kind:'edit',before:'Keep this text.',after:'Keep the text.',reason:'Earlier pass.'}];state.expected='v2';
  await f.run("sRoute('editor','comments')");
  assert.ok(nodes().some(e=>e.textContent==='This review couldn’t finish'),'a failed latest pass is shown before earlier feedback');
  await f.run("sRoute('editor','comments','changes')");
  assert.ok(nodes().some(e=>e.textContent==='The latest pass failed. These are earlier saved suggestions; no new results were added.'));
  state.operation.editor_check='factual-support';f.run('studio.editorChoices={}');await f.run("sRoute('editor','comments','prepare')");
  assert.equal(nodes().find(e=>e.id==='editor-check').value,'factual-support','reopening a failed pass retains its action instead of switching to polish');
  assert.ok(nodes().some(e=>e.textContent==='Try again'));
}

async function pendingEditorSaves(){
  const pending=deferred();let state={id:'typing',title:'Typing fixture',content:'Original.',expected:'v1',google:null,proposals:[],findings:[],checks:{},working:false};
  const f=fixture((url,options)=>{if(url.startsWith('/api/manuscript?'))return state;if(url==='/api/editor-save')return pending.promise;return {items:[]};});f.loadRunner();await f.run("sRoute('editor','typing','prepare')");
  const nodes=()=>descendants(f.get('studio-page')),input=nodes().find(e=>e.attributes['aria-label']==='Manuscript Markdown');
  input.value='Submitted text.';input.listeners.input();const saving=nodes().find(e=>e.textContent==='Save local edits').listeners.click();
  input.value='Submitted text. More typing.';input.listeners.input();
  state={...state,content:'Submitted text.',expected:'v2'};pending.resolve({...state,preservation:{needs_review:false}});await saving;
  assert.equal(nodes().find(e=>e.attributes['aria-label']==='Manuscript Markdown').value,'Submitted text. More typing.','typing during a save is not discarded');
  assert.equal(f.run('studio.editorDraft.baseContent'),'Submitted text.');assert.equal(f.run('studio.editorDraft.expected'),'v2');
  const selected=deferred(),review={...state,id:'leave',content:'Original.',expected:'v1',findings:[{id:'one',kind:'edit',before:'Original.',after:'Revised.',reason:'Clearer.'}]};
  const g=fixture(url=>url.startsWith('/api/manuscript?')?review:url==='/api/editor-proposals'?selected.promise:{items:[]});g.loadRunner();await g.run("sRoute('editor','leave','changes')");
  const page=()=>descendants(g.get('studio-page'));const next=descendants(g.get('actions')).find(e=>e.className.includes('review-continue'));
  const keeping=next.listeners.click();assert.equal(page().find(e=>e.type==='checkbox').disabled,true,'selection is stable during its save');
  assert.equal(page().find(e=>e.id==='wording-0').disabled,true);
  await g.run("sRoute('polish')");selected.resolve(review);await keeping;
  assert.equal(g.run('studio.screen'),'polish','a completed save does not pull the person back after navigation');
}

async function manualEditingJourneys(){
  let state={id:'manual',title:'Manual fixture',content:'Revised text.',baseline:'Original text.',expected:'v1',google:{url:'https://docs.google.com/document/d/fixture/edit'},proposals:[],findings:[],checks:{},working:false};
  const writes=[];const f=fixture((url,options)=>{if(url.startsWith('/api/manuscript?'))return state;if(options?.body){writes.push({url,data:JSON.parse(options.body)});if(url==='/api/editor-proposals'){state={...state,proposals:writes.at(-1).data.proposals,expected:'v2'};return state;}}return {items:[]};});f.loadRunner();await f.run("sRoute('editor','manual','prepare')");
  const nodes=()=>descendants(f.get('studio-page'));
  assert.equal(nodes().find(e=>e.textContent==='3. Finish').disabled,false,'saved manual Google edits can reach delivery preparation');
  await f.run("sRoute('editor','manual','finish')");assert.ok(nodes().some(e=>e.textContent==='Prepare your edits for Google'));
  assert.equal(writes.length,0,'opening manual preparation never sends feedback or starts a model');
  await nodes().find(e=>e.textContent==='Add quoted feedback instead').listeners.click();
  for(const [id,value]of [['proposal-before','Revised text.'],['proposal-after','Better text.'],['proposal-reason','Clearer wording.']]){const input=nodes().find(e=>e.id===id);input.value=value;input.listeners.input();}
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(writes[0].url,'/api/editor-proposals');assert.equal(writes[0].data.proposals[0].after,'Better text.');
  assert.equal(writes.some(write=>write.url==='/api/editor-check'||write.url==='/api/editor-google-send'),false);
}

async function writingReviewJourneys(){
  let run={id:'ready',title:'Ready writing',expected:'r1',approval:'page',status:'waiting-for-approval',next:'outline',enabled:true,complete:false,existing:false,mode:'write',engine:'codex',seconds:600,brief:{goal:'Explain',audience:'Authors'},decisions:[],stages:[{stage:'outline',label:'Outline',status:'draft',path:'OUTLINE.md'},{stage:'draft',label:'Draft',status:'pending',path:'DRAFT.md'}]};
  const shown={stage:'outline',label:'Outline',expected:'r1',status:'draft',content:'# Three ideas\n\nAn angle to develop.',checks:[],notes:'Synthetic only.',previous:null,diff:[]},writes=[];
  const f=fixture((url,options)=>{if(url.startsWith('/api/run?'))return run;if(url.startsWith('/api/run-file?'))return shown;if(url==='/api/run-develop'){writes.push(JSON.parse(options.body));run={...run,mode:'write',status:'queued',next:'draft'};return run;}return {items:[]};});f.loadRunner();
  await f.run("sRoute('run','ready')");
  assert.equal(f.run('studio.screen'),'gate','a ready outline opens directly for reading');
  assert.equal(writes.length,0,'opening a document never approves it');
  await descendants(f.get('toolbar-lead')).find(e=>e.attributes['aria-label']==='Back').listeners.click();
  assert.equal(f.run('studio.screen'),'run');assert.equal(f.run('studio.stage'),'status','Back can still open progress');await f.run('sPoll()');assert.equal(f.run('studio.screen'),'run');
  run={...run,mode:'ideas'};await f.run("sRoute('run','ready')");
  assert.equal(f.get('title').textContent,'Ideas');
  const actions=()=>descendants(f.get('actions'));
  assert.equal(actions().filter(e=>e.tagName==='button'&&e.className.includes('button-filled')).length,1);
  assert.ok(actions().some(e=>e.textContent==='Save ideas for later'));
  await actions().find(e=>e.textContent==='Develop an idea').listeners.click();
  const sheet=()=>descendants(f.get('sheet')),go=sheet().find(e=>e.textContent==='Develop this choice');assert.equal(go.disabled,true);assert.equal(writes.length,0);
  const choice=sheet().find(e=>e.id==='develop-choice');choice.value='Develop the second idea for technical leads.';choice.listeners.input();assert.equal(go.disabled,false);
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(writes.length,1);assert.equal(writes[0].request,'Develop the second idea for technical leads.');
}

async function deliveryRecovery(){
  let attempts=0,plans=0;const tokens=[];
  const state={id:'retry',title:'Retry fixture',content:'Old wording.',expected:'v1',google:{url:'https://docs.google.com/document/d/fixture/edit'},proposals:[{id:'one',kind:'edit',before:'Old',after:'New',reason:'Clearer'}],findings:[],checks:{},working:false};
  const f=fixture((url,options)=>{
    if(url.startsWith('/api/manuscript?'))return state;
    if(url==='/api/editor-google-plan'){plans++;return {plan:'b'.repeat(32),expected:'v1',count:1,mode:'auto'};}
    if(url==='/api/editor-google-send'){tokens.push(JSON.parse(options.body).plan);return {status:++attempts===1?'uncertain':'verified-comments'};}
    return {items:[]};
  });f.loadRunner();await f.run("sRoute('editor','retry','finish')");
  const nodes=()=>descendants(f.get('studio-page'));
  await nodes().find(e=>e.textContent==='Send feedback to Google').listeners.click();
  assert.ok(nodes().some(e=>e.textContent==='Check delivery'));assert.equal(plans,1);
  f.run('studio.editorDelivery=null');await f.run("sRoute('editor','retry','finish')");
  assert.ok(nodes().some(e=>e.textContent==='Check delivery'),'uncertain attempt survives refresh');
  await nodes().find(e=>e.textContent==='Check delivery').listeners.click();
  assert.equal(plans,1);assert.deepEqual(tokens,['b'.repeat(32),'b'.repeat(32)]);
  assert.ok(nodes().some(e=>e.textContent==='Feedback sent'));
  state.proposals=[];state.expected='v2';state.operation={editor_check:'polish',next:'review',status:'waiting-for-approval'};
  await f.run("sRoute('editor','retry','changes')");
  assert.ok(nodes().some(e=>e.textContent==='No changes suggested'));
  assert.equal(nodes().some(e=>e.textContent==='Use all 0 changes'),false);
}

async function revisionCompletion(){
  const state={id:'revised',title:'Revised local draft',content:'The revised wording.',expected:'v1',google:null,proposals:[],findings:[],checks:{},working:false,operation:{editor_check:'revise',next:'review',status:'waiting-for-approval'}};
  const f=fixture(()=>state);f.loadRunner();await f.run("sRoute('editor','revised')");
  const nodes=()=>descendants(f.get('studio-page'));
  assert.ok(nodes().some(e=>e.textContent==='Your revised draft'));
  assert.equal(nodes().some(e=>e.textContent==='No wording changes found'),false);
  await nodes().find(e=>e.textContent==='Use revised draft').listeners.click();
  assert.ok(nodes().some(e=>e.textContent==='Download polished document'));
}

async function taskJourneys(){
  const defaults={engine:'codex',seconds:600,research:'web-allowed',stop:'package',tone:'Clear',author:''};
  const requests=[];
  const manuscript={id:'pasted',title:'Pasted draft',content:'Café draft.',expected:'v1',google:null,proposals:[],findings:[],checks:{},working:false};
  const found={id:'written',title:'Supplied outline',status:'queued',next:'draft',approval:'page',expected:'r1',enabled:true,directory:'/synthetic',seconds:600,engine:'codex',decisions:[],brief:{goal:'Explain',audience:'Authors'},stages:[]};
  const f=fixture((url,options)=>{
    requests.push({url,data:options?.body?JSON.parse(options.body):null});
    if(url==='/api/run-options')return {settings:{defaults},sources:[],profiles:[],agents:{codex:true}};
    if(url==='/api/upload')return {article:{id:'pasted'}};
    if(url.startsWith('/api/manuscript?'))return manuscript;
    if(url==='/api/run-create'||url.startsWith('/api/run?'))return found;
    return {items:[],total:0};
  });f.loadRunner();f.run('sHome()');
  const nodes=()=>descendants(f.get('studio-page')),field=id=>nodes().find(e=>e.id===id);
  for(const label of ['Polish a document','Write from a brief','Use my outline','Explore ideas'])assert.ok(nodes().some(e=>e.textContent===label));
  await nodes().find(e=>e.textContent==='Polish a document').listeners.click();
  assert.ok(nodes().some(e=>e.textContent==='Google Doc'));assert.ok(nodes().some(e=>e.textContent==='Upload a file'));
  await nodes().find(e=>e.textContent==='Paste text').listeners.click();
  for(const [id,value] of [['draft-title','Pasted draft'],['draft-content','Café draft.']]){field(id).value=value;field(id).listeners.input();}
  await nodes().find(e=>e.textContent==='Google Doc').listeners.click();
  await nodes().find(e=>e.textContent==='Paste text').listeners.click();
  assert.equal(field('draft-content').value,'Café draft.');
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const upload=requests.find(r=>r.url==='/api/upload').data;
  assert.equal(upload.as_blog,true);assert.equal(upload.analyze,false);assert.equal(Buffer.from(upload.content,'base64').toString(),'Café draft.');
  assert.equal(f.run('studio.screen'),'editor');assert.equal(requests.some(r=>r.url==='/api/editor-check'),false,'opening a manuscript does not start a model');
  await f.run("sRoute('polish')");
  await nodes().find(e=>e.textContent==='Upload a file').listeners.click();
  field('draft-title').value='Uploaded draft';field('draft-title').listeners.input();
  const file=nodes().find(e=>e.type==='file');file.files=[{name:'sample.txt',size:11,arrayBuffer:async()=>new TextEncoder().encode('Plain text.').buffer}];file.listeners.change();
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const uploaded=requests.filter(r=>r.url==='/api/upload').at(-1).data;
  assert.equal(uploaded.filename,'sample.txt');assert.equal(uploaded.analyze,false);assert.equal(Buffer.from(uploaded.content,'base64').toString(),'Plain text.');
  await f.run("sRoute('polish')");await nodes().find(e=>e.textContent==='Paste text').listeners.click();
  field('draft-content').value='# Café notes\n\nA new draft.';field('draft-content').listeners.input();
  assert.equal(field('draft-title').required,false);
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(requests.filter(r=>r.url==='/api/upload').at(-1).data.title,'Café notes','a pasted heading supplies the optional working title');
  await f.run("newBlog('',null,'from-outline')");
  for(const [id,value] of [['new-title','Supplied outline'],['new-goal','Explain'],['new-audience','Authors'],['new-outline','# First\n## Second']]){field(id).value=value;field(id).listeners.input();}
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.ok(nodes().some(e=>e.textContent==='Ready to start'));
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const creation=requests.find(r=>r.url==='/api/run-create').data;
  assert.equal(creation.mode,'from-outline');assert.equal(creation.outline_text,'# First\n## Second');assert.equal(creation.research,'none');
  assert.equal(creation.stop,'draft');
}

async function googleReopening(){
  const manuscript={id:'existing',title:'Existing manuscript',content:'Keep these local edits.',expected:'v2',google:{url:'https://docs.google.com/document/d/fixture-doc/edit'},proposals:[],findings:[],checks:{},working:false};
  const linked={status:'already-linked',id:manuscript.id,title:manuscript.title,linked_document:manuscript.google.url};
  const preview={status:'preview',preview:'b'.repeat(32),expected:'v1',title:'Synthetic manuscript',linked_document:manuscript.google.url,content:'Original text.',summary:{structure:{paragraphs:1}}};
  for(const entry of ['polish','google']){
    for(const response of [linked,{...preview,summary:undefined},{...preview,summary:{}},{status:'unrecognized'},{status:'already-linked'}]){
      const requests=[];let result=response;
      const f=fixture((url,options)=>{requests.push({url,options});if(url==='/api/google-preview')return result;if(url.startsWith('/api/manuscript?'))return manuscript;return {items:[]};});
      f.loadRunner();await f.run(`sRoute('${entry}')`);
      const nodes=()=>descendants(f.get('studio-page'));
      const input=nodes().find(e=>e.id===(entry==='polish'?'polish-url':'google-url'));input.value='fixture-doc';input.listeners.input();
      const submit=()=>nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
      await submit();
      if(response===linked){
        assert.equal(f.run('studio.screen'),'editor',entry+' reopens an already linked Doc');
        assert.equal(f.run('studio.editorDraft.content'),manuscript.content,'saved local edits are kept');
        assert.ok(f.run('studio.intake')==null);assert.equal(f.run('studio.google'),null);
      }else{
        assert.equal(f.run('studio.screen'),entry,'invalid response stays at the entered link');
        assert.equal(nodes().find(e=>e.id===input.id).value,'fixture-doc');
        assert.ok(nodes().some(e=>e.className==='problem'&&e.textContent.includes('Read the document again')));
        assert.equal(nodes().find(e=>e.type==='submit').disabled,false,'retry stays available');
        result=linked;await submit();assert.equal(f.run('studio.screen'),'editor','retry reopens the existing manuscript');
      }
      assert.equal(requests.some(r=>r.options?.method==='POST'&&r.url!=='/api/google-preview'),false,'reopening does not reimport, start a model, or send feedback');
      assert.equal(nodes().some(e=>e.textContent==='This view could not be read'),false);
    }
  }
  // A link can become associated with a saved blog between preview and confirmation.
  const raced=[];const f=fixture((url)=>{raced.push(url);if(url==='/api/google-preview')return preview;if(url==='/api/google-start')return linked;if(url.startsWith('/api/manuscript?'))return manuscript;return {items:[]};});f.loadRunner();
  await f.run("sRoute('polish')");let nodes=()=>descendants(f.get('studio-page'));
  const input=nodes().find(e=>e.id==='polish-url');input.value='fixture-doc';input.listeners.input();
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(f.run('studio.screen'),'editor');assert.equal(f.run('studio.editorDraft.content'),manuscript.content);
  assert.equal(raced.filter(url=>url==='/api/google-start').length,1);
  // Navigating away while the new entry point reads a link must not reopen it later.
  const pending=deferred(),late=fixture(()=>pending.promise);late.loadRunner();await late.run("sRoute('polish')");
  const reading=descendants(late.get('studio-page')).find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  late.run("studio.turn++;studio.screen='blogs'");pending.resolve(linked);await reading;
  assert.equal(late.run('studio.screen'),'blogs');assert.equal(late.run('studio.google'),undefined);
}

async function googleIntake(){
  const defaults={engine:'codex',seconds:600,research:'none',stop:'review',tone:'Clear',author:''};
  const preview={status:'preview',preview:'b'.repeat(32),expected:'capture-version',title:'Synthetic Google draft',linked_document:'https://docs.google.com/document/d/fixture-doc/edit',content:'# Synthetic manuscript\n\n<script>not executable</script>',images_omitted:true,summary:{pending_suggestions:1,projection:'blog-studio/1',structure:{paragraphs:2,headings:1}}};
  const manuscript={id:'imported',title:preview.title,content:'Synthetic text',expected:'v1',google:{url:preview.linked_document},proposals:[],findings:[],baseline:'Synthetic text',diff:[],checks:{},working:false};
  const requests=[];
  const f=fixture((url,options)=>{
    requests.push({url,options});
    if(url.startsWith('/api/manuscript?'))return manuscript;
    if(url==='/api/google-preview')return preview;
    if(url==='/api/google-start')return {id:'imported',status:'started-from-google',title:preview.title,linked_document:preview.linked_document};
    if(url==='/api/run-options')return {settings:{defaults},brand:{default:{brand:'default-brand',variant:'default-variant'}},sources:[],profiles:[],agents:{codex:true}};
    if(url.startsWith('/api/article?'))return {title:preview.title,view:{google:{url:preview.linked_document}},record:{}};
    return {items:[],total:0};
  });
  f.loadRunner();
  const find=id=>descendants(f.get('studio-page')).find(e=>e.id===id);
  await f.run("sRoute('polish')");
  assert.equal(f.get('title').textContent,'Polish a document');
  find('polish-url').value=preview.linked_document;find('polish-url').listeners.input();
  let form=f.get('studio-page').children.find(e=>e.tagName==='form');await form.listeners.submit({preventDefault(){}});
  assert.equal(requests.filter(r=>r.url==='/api/google-preview').length,1);
  assert.equal(requests.some(r=>r.url==='/api/google-start'),false);
  form=f.get('studio-page').children.find(e=>e.tagName==='form');let nodes=descendants(form);
  assert.equal(nodes.find(e=>e.type==='submit').disabled,false);
  assert.equal(nodes.some(e=>e.tagName==='script'),false);
  assert.ok(nodes.some(e=>e.textContent.includes('1 pending Google suggestions')));
  assert.ok(nodes.some(e=>e.textContent.includes('Images are omitted from this preview.')));
  assert.equal(nodes.some(e=>e.type==='checkbox'),false,'the preview is checked by reading it, not by a checkbox');
  await form.listeners.submit({preventDefault(){}});
  assert.equal(f.run('studio.screen'),'editor');
  assert.equal(f.run('studio.editorDraft.id'),'imported');
  assert.equal(f.run('studio.editorDraft.content'),'Synthetic text');
  assert.equal(requests.some(r=>r.url==='/api/run-create'),false,'intake does not start an assistant');
  assert.deepEqual(JSON.parse(requests.find(r=>r.url==='/api/google-start').options.body),{preview:preview.preview,expected:preview.expected,title:preview.title,confirmed:true});
  assert.ok(descendants(f.get('actions')).some(e=>e.tagName==='a'&&e.href===preview.linked_document));
  await f.run("newBlog('imported',{goal:'Keep my purpose',audience:'Operators',brand:'',variant:'',author:'',mode:'revise',stop:'draft'})");
  assert.equal(f.run('studio.draft.goal'),'Keep my purpose');assert.equal(f.run('studio.draft.audience'),'Operators');
  assert.equal(f.run('studio.draft.brand'),'');assert.equal(f.run('studio.draft.mode'),'revise');assert.equal(f.run('studio.draft.stop'),'draft');
  // Access failures keep the entered link, show an inline error, and permit retry.
  const denied=fixture(()=>({__http:400,error:'Google sign-in is unavailable.'}));denied.loadRunner();
  await denied.run('sGoogleButton().listeners.click()');denied.run("studio.google.url='fixture-doc'");
  await denied.get('studio-page').children.find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(denied.run('studio.google.url'),'fixture-doc');
  assert.ok(descendants(denied.get('studio-page')).some(e=>e.textContent.includes('Google sign-in is unavailable.')));
  assert.equal(descendants(denied.get('studio-page')).find(e=>e.type==='submit').disabled,false);
  // A late preview response cannot replace the screen the person navigated to.
  const pending=deferred(),late=fixture(()=>pending.promise);late.loadRunner();
  await late.run('sGoogleButton().listeners.click()');late.run("studio.google.url='fixture-doc'");
  const reading=late.get('studio-page').children.find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  late.run("studio.turn++;studio.screen='blogs'");pending.resolve(preview);await reading;
  assert.equal(late.run('studio.screen'),'blogs');
  // A repeated link opens its existing guided run without a new import.
  const existing={id:'imported',title:preview.title,google:{url:preview.linked_document},status:'complete',complete:true,next:null,stages:[],brief:{goal:'Synthetic review',audience:'Authors'},decisions:[],engine:'codex',seconds:600,approval:'page',directory:'/synthetic/articles/imported'};
  const reopened=[];const again=fixture((url)=>{reopened.push(url);if(url==='/api/google-preview')return {status:'already-linked',id:existing.id};if(url==='/api/runs')return {items:[existing]};if(url.startsWith('/api/run?'))return existing;if(url.startsWith('/api/manuscript?'))return manuscript;if(url==='/api/run-options')return {sources:[]};return {items:[]};});again.loadRunner();
  await again.run('sGoogleButton().listeners.click()');again.run("studio.google.url='fixture-doc'");
  await again.get('studio-page').children.find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(again.run('studio.screen'),'editor');assert.equal(again.run('studio.id'),'imported');
  assert.equal(reopened.includes('/api/google-start'),false);
  assert.ok(descendants(again.get('actions')).some(e=>e.tagName==='a'&&e.href===preview.linked_document));
}
const empty=(total=0)=>({items:[],total});
async function requestOrdering(){
  const f=controlled();
  const board=f.run('load()');assert.equal(f.get('results').attributes['aria-busy'],'true');
  assert.equal(f.get('previous').disabled,true);assert.equal(f.get('next').disabled,true);
  f.run("view='memory'");const memory=f.run('load()');
  assert.equal(f.requests[0].options.signal.aborted,true);
  f.requests[1].resolve(empty());await memory;
  f.requests[0].resolve({items:[{title:'Old blog'}],total:1});await board;
  assert.equal(f.get('heading').textContent,'Team memory');assert.equal(f.get('count').textContent,'0 items');
  assert.equal(f.get('loading').hidden,true);assert.equal(f.get('results').attributes['aria-busy'],'false');
  for(const mode of ['search','stage','page']){
    const g=controlled();const old=g.run('load()');
    if(mode==='search')g.get('query').value='latest search';
    if(mode==='stage')g.get('stage').value='review';
    if(mode==='page')g.run('offset=20');
    const latest=g.run('load()');
    g.requests[1].resolve(empty(40));await latest;
    const count=g.get('count').textContent, page=g.get('page-label').textContent;
    g.requests[0].resolve(empty(5));await old;
    assert.equal(g.get('count').textContent,count);assert.equal(g.get('page-label').textContent,page);
    if(mode==='page')assert.equal(page,'21–40 of 40');
    if(mode==='search')assert.match(g.requests[1].url,/query=latest\+search/);
    if(mode==='stage')assert.match(g.requests[1].url,/stage=review/);
  }
  // An obsolete failure is silent, even when the transport ignores cancellation.
  const g=controlled();const old=g.run('load()');g.get('query').value='new';const newest=g.run('load()');
  g.requests[1].resolve(empty(2));await newest;
  g.requests[0].reject(new Error('Obsolete failure'));await old;
  assert.equal(g.get('notice').textContent,'');assert.equal(g.get('count').textContent,'2 items');
  // Keep the last valid result and restore pagination offset after a current failure.
  const h=controlled();const initial=h.run('load()');h.requests[0].resolve(empty(40));await initial;
  const previous=h.get('results').children[0];h.run('offset=20');const failed=h.run('load()');
  h.requests[1].resolve({__http:503,error:'Current failure'});await assert.rejects(failed,/Current failure/);
  assert.equal(h.get('results').children[0],previous);assert.equal(h.run('offset'),0);
  assert.equal(h.get('next').disabled,false);assert.equal(h.get('loading').hidden,true);
  h.run("view='memory'");const missing=h.run('load()');h.requests[2].reject(new Error('socket hang up'));
  await assert.rejects(missing,/desk helper is not answering/);assert.equal(h.get('results').children[0],previous);
  assert.equal(h.get('next').disabled,true);
}
async function curationConflict(){
  let reads=0;const writes=[];
  const f=fixture((url,options)=>{
    if(url.startsWith('/api/source?')){reads++;return {id:'source',location:'local',expected:reads===1?'old-token':'new-token',record:{library:{curation:'active',topics:reads===1?['old']:['new saved'],products:[]},note:'Saved note'},excerpt:'Reference text'};}
    if(url==='/api/curate'){
      writes.push(JSON.parse(options.body));
      return writes.length===1?{__http:409,code:'source-conflict',error:'This reference changed.'}:{receipts:[{label:'Curation',message:'Saved locally.'}]};
    }
    return empty();
  });
  f.set('item',{id:'source',location:'local',title:'Reference'});await f.run('curate(item)');
  const form=descendants(f.get('detail-content')).find(e=>e.tagName==='form');
  const fields=Object.fromEntries(descendants(form).filter(e=>e.name).map(e=>[e.name,e]));
  fields.curation.value='active';fields.topics.value='My proposed topic';fields.products.value='';fields.note.value='My proposed note';
  const save=form.querySelector('[type=submit]');
  await form.listeners.submit({preventDefault(){}});
  assert.equal(writes[0].expected,'old-token');assert.equal(save.disabled,true);
  assert.equal(fields.note.value,'My proposed note');assert.equal(f.get('detail-dialog').open,true);
  assert.equal(f.get('detail-dialog').querySelector('.dialog-notice').textContent,'This reference changed.');
  const conflict=descendants(f.get('detail-content')).find(e=>e.className==='curation-conflict');
  const reload=descendants(conflict).find(e=>e.tagName==='button'&&e.textContent==='Reload and compare');
  await reload.listeners.click();
  assert.equal(writes.length,1);assert.equal(save.disabled,true);assert.equal(fields.topics.value,'My proposed topic');
  assert.ok(descendants(conflict).some(e=>e.textContent.includes('new saved')));
  const keep=descendants(conflict).find(e=>e.tagName==='button'&&e.textContent==='Keep my proposal for resubmission');
  await keep.listeners.click();assert.equal(save.disabled,false);assert.equal(writes.length,1);
  await form.listeners.submit({preventDefault(){}});
  assert.equal(writes.length,2);assert.equal(writes[1].expected,'new-token');
  assert.equal(writes[1].note,'My proposed note');assert.equal(f.get('detail-dialog').open,false);
}
check().catch(e=>{console.error(e);process.exitCode=1;});

async function capabilityAndMemory(){
  const f=fixture(()=>({status:'read-only',message:'Read-only Hub access.',actions:{edit:false,memory:false,refresh:true}}));
  await f.run('loadCapabilities()');
  assert.equal(f.get('upload-open').disabled,true);assert.equal(f.get('memory-open').disabled,true);
  assert.equal(f.get('refresh-hub').disabled,false);assert.match(f.get('access-status').textContent,/Read-only/);
  for(const kind of ['note','context','rule','decision','collection','lesson']){
    const editable=['note','context','rule'].includes(kind);
    const m=fixture(()=>({record:{item:'memory',revision:'revision',kind:editable?kind:kind==='decision'?kind:'context',title:kind,scope:{level:'team',key:''}},body:'Saved body',editable,read_only_reason:editable?'':kind+' is read-only',continuation:'Inspect memory fixture'}));
    const submit=new Element('button');submit.type='submit';m.get('memory-form').append(submit);
    m.run('access.actions.memory=true');m.set('item',{item:'memory',revision:'revision'});
    await m.run('editMemory(item)');
    if(editable){assert.equal(m.get('memory-kind').value,kind);assert.equal(m.get('memory-dialog').open,true);}
    else {assert.equal(m.get('detail-dialog').open,true);assert.equal(descendants(m.get('detail-content')).some(e=>e.type==='submit'),false);assert.ok(descendants(m.get('detail-content')).some(e=>e.textContent===kind+' is read-only'));}
  }
}

async function articleDisclosure(){
  const data={title:'Gateway guide',location:'local',expected:'guard',record:{editorial:{},stop_point:'draft'},assets:{},sources:[],history:[],view:{id:'article-id',location:'local',stage:'draft',stop_point:'draft',stop_reached:true,blocker:'',reviews:[{check:'proofread',status:'stale',detail:'Inputs changed.'}],next_action:{label:'Inspect saved draft in chat',command:'Continue blog article-id. Keep the requested stopping point (draft).'},google:null,google_observation:'No saved Google link.',preview:{kind:'draft',text:'A bounded manuscript preview.',truncated:false}}};
  const f=fixture(url=>url.startsWith('/api/finding')?{article:data,finding:{kind:'proofread',status:'stale',action:'Inspect it.',finding:{message:'Saved finding.'}},evidence:[{name:'Specification',quote:'Exact passage.'}],command:'Continue blog article-id. Show finding fixture.'}:data);
  f.set('item',{id:'article-id',location:'local'});await f.run('showBlog(item)');
  const content=f.get('detail-content');
  assert.ok(descendants(content).some(e=>e.textContent==='A bounded manuscript preview.'));
  const details=descendants(content).filter(e=>e.tagName==='details');
  assert.ok(details.some(e=>e.children[0].textContent==='Editorial details'));
  assert.ok(details.some(e=>e.children[0].textContent==='Reviews and freshness'));
  assert.ok(details.every(e=>!e.open));
  const field=descendants(content).find(e=>e.tagName==='textarea'&&e.readOnly);
  assert.match(field.value,/article-id/);
  const copy=descendants(content).find(e=>e.textContent==='Copy request');await copy.listeners.click();
  assert.equal(field.selected,true);assert.equal(field.focused,true);
  f.run('access.actions.edit=false');await f.run('showBlog(item)');
  assert.equal(descendants(content).some(e=>e.type==='submit'),false);
  f.set('item',{id:'article-id',location:'local',key:'fixture'});await f.run('showFinding(item)');
  assert.ok(descendants(content).some(e=>e.textContent==='Saved finding.'));
  assert.ok(descendants(content).some(e=>e.textContent==='Exact passage.'));
  for(const name of ['board','inbox','library','memory']){
    const item={id:'blog',item:'memory',title:'A long title',location:'local',author:'Avery',stage:'draft',owner:'Morgan',kind:'proofread',key:'finding',action:'Inspect',status:'stale',library:{curation:'active'},scope:{level:'team',key:''}};
    f.set('state',{view:name,offset:0});f.set('result',{items:[item],total:1});f.run('render(state,result)');
    const cells=descendants(f.get('results')).filter(e=>e.tagName==='td');
    assert.equal(cells.length,4);assert.ok(cells.every(e=>e.attributes['data-label']));
  }
}

async function historicalImport(){
  const preview={preview:'a'.repeat(32),expected:'initial',collection:'Past posts',type:'folder',candidates:26,completed:0,remaining:26,counts:{},excluded:[],posts:Array.from({length:26},(_,i)=>({key:String(i),title:i===0?'A retained <post>':'Post '+i,status:'pending'})),selected:[],failures:[]};
  const writes=[];
  const f=fixture((url,options)=>{
    if(url==='/api/library-preview'&&options.method==='POST'){writes.push([url,JSON.parse(options.body)]);return preview;}
    if(url==='/api/library-import'){writes.push([url,JSON.parse(options.body)]);return {...preview,expected:'next',completed:25,remaining:1,posts:preview.posts.map((p,i)=>({...p,status:i<25?'imported':'pending'})),selected:preview.posts.map(p=>p.key),counts:{imported:25},sharing_message:'Saved locally.'};}
    return empty();
  });
  for(const type of ['folder','archive','feed','export','sitemap','urls','collection']){
    f.get('import-type').value=type;f.run('importFields()');
    assert.equal(f.get('import-folder-field').hidden,type!=='folder');
    assert.equal(f.get('import-export-field').hidden,type!=='export');
    assert.equal(f.get('import-collection-field').hidden,type!=='collection');
    assert.equal(f.get('import-scope-field').hidden,!['archive','feed','sitemap','urls'].includes(type));
  }
  f.get('import-type').value='folder';f.get('import-name').value='Past posts';
  f.get('import-folder').files=[{name:'one.md',webkitRelativePath:'Posts/one.md',size:5,arrayBuffer:async()=>new TextEncoder().encode('text.').buffer}];
  await f.run('previewImport()');
  assert.equal(writes.length,1);assert.equal(writes[0][0],'/api/library-preview');
  assert.equal(writes[0][1].files[0].path,'Posts/one.md');
  assert.equal(Buffer.from(writes[0][1].files[0].content,'base64').toString(),'text.');
  assert.equal(f.get('import-form').hidden,true);
  assert.equal(f.get('import-new').hidden,false);
  assert.equal(f.get('import-save').textContent,'Import selected 0 posts');
  assert.equal(f.get('import-save').disabled,true);
  assert.equal(f.run('importChecks.size'),26);
  f.run("importChecks.get('21').checked=true;importSelectionControls()");
  assert.equal(f.get('import-save').textContent,'Import selected 1 posts');
  f.run('for(const check of importChecks.values())check.checked=true;importSelectionControls()');
  assert.equal(f.get('import-save').textContent,'Import selected 25 posts');
  assert.ok(descendants(f.get('import-preview')).some(e=>e.textContent==='A retained <post>'));
  await f.run('saveImport()');
  assert.equal(writes.length,2);assert.equal(writes[1][1].confirm,true);assert.equal(writes[1][1].expected,'initial');
  assert.deepEqual(writes[1][1].selected,preview.posts.map(p=>p.key));
  assert.equal(f.get('import-save').textContent,'Import selected 1 posts');
  assert.equal(f.run("importChecks.get('0').disabled"),true);
  assert.equal(f.run("importChecks.get('25').checked"),true);
  f.get('import-folder').files=[];await f.run('previewImport()');
  assert.equal(writes.length,2);assert.equal(f.get('import-save').hidden,true);
  f.run('access.actions.edit=false');await f.run('saveImport()');assert.equal(writes.length,2);
}

const text=node=>descendants(node).map(e=>e.textContent).join(' | ');

async function diffOnlyForms(){
  // Editorial form: a stale "ready" blog. Changing only the owner must not carry the stage.
  const writes=[];
  const article=(editorial,view={})=>({title:'Ready blog',location:'local',expected:'guard',record:{editorial,stop_point:'draft'},assets:{},sources:[],history:[],
    view:{stage:'review',decision_stale:true,stop_point:'draft',stop_reached:false,blocker:'Changed after the decision.',reviews:[],next_action:{label:'l',command:'c'},google:null,google_observation:'',preview:{kind:'draft',text:'t',truncated:false},...view}});
  let saved=article({stage:'ready',owner:'Morgan'});
  const f=fixture((url,options)=>{
    if(url==='/api/schedule'){writes.push(JSON.parse(options.body));return {receipts:[]};}
    if(url.startsWith('/api/article'))return saved;
    if(url==='/api/memory'){writes.push(JSON.parse(options.body));return {receipts:[]};}
    if(url.startsWith('/api/memory-detail'))return {record:{item:'memory',revision:'revision',kind:'note',title:'Saved title',scope:{level:'team',key:''}},body:'Saved body',editable:true,truncated:true};
    return empty();
  });
  const open=async()=>{f.set('item',{id:'blog',location:'local'});await f.run('showBlog(item)');
    const form=descendants(f.get('detail-content')).find(e=>e.tagName==='form');
    const named=Object.fromEntries(descendants(form).filter(e=>e.name).map(e=>[e.name,e]));
    const box=descendants(form).find(e=>e.type==='checkbox');
    return {form,named,box,row:box.parent,submit:()=>form.listeners.submit({preventDefault(){}})};};
  let ui=await open();
  assert.equal(ui.named.stage.value,'ready');assert.equal(ui.row.hidden,false);assert.match(ui.row.children[1].textContent,/again for the current saved draft/);
  ui.named.owner.value='Jordan';await ui.submit();
  assert.deepEqual(writes.pop(),{id:'blog',expected:'guard',owner:'Jordan'});
  // Renewing the stale decision takes the explicit checkbox.
  ui=await open();ui.box.checked=true;await ui.submit();
  assert.deepEqual(writes.pop(),{id:'blog',expected:'guard',stage:'ready',confirm_stage:true});
  // Nothing changed: nothing is posted.
  ui=await open();await ui.submit();assert.equal(writes.length,0);
  assert.equal(f.get('detail-dialog').querySelector('.dialog-notice').textContent,'No changes to save.');
  // No recorded stage: the select follows writing progress and an owner edit does not pin a stage.
  saved=article({},{stage:'idea',decision_stale:false});ui=await open();
  assert.equal(ui.named.stage.value,'');assert.equal(ui.row.hidden,true);
  assert.match(ui.named.stage.children[0].textContent,/Follow writing progress \(now: idea\)/);
  ui.named.owner.value='Morgan';await ui.submit();
  assert.deepEqual(writes.pop(),{id:'blog',expected:'guard',owner:'Morgan'});
  // Choosing ready without the confirmation is refused in the page; with it, the decision is explicit.
  ui=await open();ui.named.stage.value='ready';ui.named.stage.listeners.change();assert.equal(ui.row.hidden,false);
  await ui.submit();assert.equal(writes.length,0);
  assert.match(f.get('detail-dialog').querySelector('.dialog-notice').textContent,/Check the box to record/);
  ui.box.checked=true;await ui.submit();
  assert.deepEqual(writes.pop(),{id:'blog',expected:'guard',stage:'ready',confirm_stage:true});
  // An ordinary stage needs no confirmation.
  ui=await open();ui.named.stage.value='review';ui.named.stage.listeners.change();assert.equal(ui.row.hidden,true);await ui.submit();
  assert.deepEqual(writes.pop(),{id:'blog',expected:'guard',stage:'review'});

  // Curation form: a note-only edit posts the note and nothing else.
  const curations=[];
  const c=fixture((url,options)=>{
    if(url.startsWith('/api/source?'))return {id:'source',location:'local',expected:'token',record:{status:'ready',analysis:{status:'needs-analysis'},library:{curation:'active',topics:[],products:[]},note:'Saved note'},excerpt:'Reference text',limitation:'x'};
    if(url==='/api/curate'){curations.push(JSON.parse(options.body));return {receipts:[]};}
    return empty();
  });
  c.set('item',{id:'source',location:'local',title:'Reference'});await c.run('curate(item)');
  let form=descendants(c.get('detail-content')).find(e=>e.tagName==='form');
  let fields=Object.fromEntries(descendants(form).filter(e=>e.name).map(e=>[e.name,e]));
  fields.curation.value='active';
  await form.listeners.submit({preventDefault(){}});assert.equal(curations.length,0);
  assert.equal(c.get('detail-dialog').querySelector('.dialog-notice').textContent,'No changes to save.');
  fields.note.value='Reviewed by Morgan.';await form.listeners.submit({preventDefault(){}});
  assert.deepEqual(curations.pop(),{id:'source',location:'local',expected:'token',note:'Reviewed by Morgan.'});
  await c.run('curate(item)');
  form=descendants(c.get('detail-content')).find(e=>e.tagName==='form');
  fields=Object.fromEntries(descendants(form).filter(e=>e.name).map(e=>[e.name,e]));
  fields.curation.value='retired';await form.listeners.submit({preventDefault(){}});
  assert.deepEqual(curations.pop(),{id:'source',location:'local',expected:'token',curation:'retired',confirmed:true});

  // Memory edit: only the changed field travels; an untouched (possibly truncated) body is never resent.
  const submit=new Element('button');submit.type='submit';f.get('memory-form').append(submit);
  f.run('access.actions.memory=true');f.set('item',{item:'memory',revision:'revision'});await f.run('editMemory(item)');
  assert.equal(f.get('memory-truncated').hidden,false);
  f.set('submit',submit);await f.run('saveMemory(submit)');assert.equal(writes.length,0);
  f.get('memory-name').value='Better title';await f.run('saveMemory(submit)');
  const memory=writes.pop();
  assert.deepEqual({...memory,operation:undefined},{item:'memory',revision:'revision',title:'Better title',operation:undefined});
  assert.equal(submit.disabled,false);
  // A new memory still sends every field.
  f.run('memoryEdit=null');f.get('memory-kind').value='note';f.get('memory-name').value='New';f.get('memory-body').value='Body';f.get('memory-scope').value='team';f.get('memory-key').value='';
  await f.run('saveMemory(submit)');
  assert.deepEqual({...writes.pop(),operation:undefined},{kind:'note',title:'New',body:'Body',scope:'team',scope_key:'',operation:undefined});
}

async function privacyChoiceAndIdentity(){
  const uploads=[];let capability={status:'writable',message:'Hub access verified.',actions:{edit:true,memory:true,refresh:true},workspace:'~/writing/.blog-studio',hub:{repository:'team/hub'},
    analysis:{harness:'codex',label:'Codex',message:'Reference analysis uses your signed-in Codex CLI. Text from readable uploads and imports (up to 24,000 characters per file) is sent through it to its model provider.'}};
  const f=fixture((url,options)=>{
    if(url==='/api/capabilities')return capability;
    if(url==='/api/upload'){uploads.push(JSON.parse(options.body));return {receipts:[]};}
    if(url==='/api/library-import'){uploads.push(JSON.parse(options.body));return {preview:'a'.repeat(32),expected:'next',collection:'Past posts',candidates:1,completed:1,remaining:0,counts:{imported:1},excluded:[],posts:[{key:'k',title:'Post',status:'imported'}],selected:['k'],failures:[]};}
    return empty();
  });
  await f.run('loadCapabilities()');
  assert.match(f.get('analysis-status').textContent,/24,000 characters/);assert.equal(f.get('analysis-status').hidden,false);
  assert.equal(f.get('desk-identity').textContent,'Workspace: ~/writing/.blog-studio · Team Hub: team/hub');
  for(const prefix of ['upload','import']){
    assert.equal(f.get(prefix+'-analyze-field').hidden,false);
    assert.equal(f.get(prefix+'-analyze-label').textContent,'Summarize and tag with Codex');
    assert.match(f.get(prefix+'-analysis-note').textContent,/model provider/);
  }
  const submit=new Element('button');submit.textContent='Upload and save';f.set('submit',submit);
  f.get('upload-file').files=[{name:'one.md',size:5,arrayBuffer:async()=>new TextEncoder().encode('text.').buffer}];
  f.get('upload-analyze').checked=true;await f.run('saveUpload(submit)');
  assert.equal(uploads.pop().analyze,true);assert.equal(submit.textContent,'Upload and save');assert.equal(submit.disabled,false);
  f.get('upload-analyze').checked=false;await f.run('saveUpload(submit)');
  assert.equal(uploads.pop().analyze,false);
  // The same choice travels with an import batch.
  f.run("importState={preview:'"+'a'.repeat(32)+"',expected:'initial',posts:[{key:'k',title:'Post',status:'pending'}]};importChecks=new Map([['k',{checked:true}]])");
  f.get('import-analyze').checked=false;await f.run('saveImport()');
  assert.equal(uploads.pop().analyze,false);
  // Without a configured CLI there is no checkbox and no analyze field: nothing is sent to a model.
  capability={...capability,hub:null,analysis:{harness:null,label:null,message:'Reference analysis is off. No analysis CLI is configured, so document text is not sent to a model.'}};
  await f.run('loadCapabilities()');
  assert.equal(f.get('upload-analyze-field').hidden,true);assert.match(f.get('analysis-status').textContent,/Reference analysis is off/);
  assert.match(f.get('desk-identity').textContent,/No Team Hub selected/);
  await f.run('saveUpload(submit)');assert.equal('analyze' in uploads.pop(),false);
}

async function unreadableBlogsAndBadges(){
  const f=fixture();
  for(const name of ['board','inbox']){
    f.set('state',{view:name,offset:0});
    f.set('result',{items:[],total:0,problems:[{id:'broken-article',location:'local'},{id:'shared-item',location:'hub'}],problem_count:3});
    f.run('render(state,result)');
    assert.match(text(f.get('results')),/3 blogs could not be read and are not listed: broken-article, shared-item \(Team Hub\), and more\. Ask Blog Studio in chat to inspect them\./);
    f.set('result',{items:[],total:0,problems:[{id:'only-one',location:'local'}],problem_count:1});f.run('render(state,result)');
    assert.match(text(f.get('results')),/1 blog could not be read and is not listed: only-one\./);
  }
  f.set('state',{view:'library',offset:0});f.set('result',{items:[],total:0,problems:[{id:'x',location:'local'}]});f.run('render(state,result)');
  assert.doesNotMatch(text(f.get('results')),/could not be read/);
  // Hub-supplied status text is shown as text and never becomes a CSS class.
  assert.equal(f.run("badge('ready').className"),'badge ready');assert.equal(f.run("badge('conflicted').className"),'badge conflicted');
  for(const hostile of ['sidebar','primary close','Needs analysis','not-shared']){
    f.set('value',hostile);assert.equal(f.run('badge(value).className'),'badge');assert.equal(f.run('badge(value).textContent'),hostile);
  }
  assert.equal(f.run("badge('not-run').textContent"),'Not run');assert.equal(f.run('badge(null).className'),'badge');
}

async function busyAnalysis(){
  const gate=deferred();
  const f=fixture(async url=>{
    if(url.startsWith('/api/source?'))return {id:'s',location:'local',expected:'e',record:{status:'ready',analysis:{status:'needs-analysis'},library:{}},excerpt:'text',limitation:'x'};
    if(url==='/api/analyze'){await gate.promise;return {results:[]};}
    return empty();
  });
  f.set('item',{id:'s',location:'local',title:'Reference'});await f.run('curate(item)');
  const analyze=descendants(f.get('detail-content')).find(e=>e.tagName==='button'&&e.textContent==='Analyze reference');
  const running=analyze.listeners.click();await new Promise(resolve=>setTimeout(resolve,5));
  assert.equal(analyze.disabled,true);assert.equal(analyze.attributes['aria-busy'],'true');assert.match(analyze.textContent,/Analyzing/);
  const note=f.get('detail-dialog').querySelector('.dialog-notice');
  assert.equal(note.hidden,false);assert.match(note.textContent,/24,000 characters/);
  gate.resolve();await running;
  assert.equal(analyze.disabled,false);assert.equal(analyze.textContent,'Analyze reference');
}

async function refreshWithNewSelection(){
  const writes=[];
  const f=fixture((url,options)=>{
    if(url==='/api/collections')return {items:[{key:'desk-1',name:'Past posts',type:'folder',refresh_files:true},{key:'site',name:'Site',type:'archive',refresh_files:false}]};
    if(url==='/api/library-preview'&&options.method==='POST'){writes.push(JSON.parse(options.body));return {preview:'b'.repeat(32),expected:'e',collection:'Past posts',saved_collection:true,candidates:0,completed:0,remaining:0,counts:{},excluded:[],posts:[],selected:[],failures:[]};}
    return {available:false};
  });
  f.get('import-type').value='collection';f.get('import-collection').value='desk-1';await f.run('openImport()');
  assert.equal(f.get('import-folder-field').hidden,false);assert.match(f.get('import-folder-help').textContent,/Optional: choose the folder again/);
  f.get('import-folder').files=[];await f.run('previewImport()');
  assert.deepEqual({...writes.pop(),operation:undefined},{collection:'desk-1',operation:undefined});
  f.get('import-folder').files=[{name:'three.md',webkitRelativePath:'Posts/three.md',size:5,arrayBuffer:async()=>new TextEncoder().encode('text.').buffer}];
  await f.run('previewImport()');
  const refreshed=writes.pop();assert.equal(refreshed.collection,'desk-1');assert.equal(refreshed.files[0].path,'Posts/three.md');assert.equal('name' in refreshed,false);
  // A collection that reads a website has nothing to choose.
  f.get('import-collection').value='site';f.run('importFields()');
  assert.equal(f.get('import-folder-field').hidden,true);assert.equal(f.get('import-export-field').hidden,true);
  // A draft collection says when it becomes real.
  f.set('preview',{preview:'c'.repeat(32),expected:'e',collection:'New',saved_collection:false,candidates:0,completed:0,remaining:0,counts:{},excluded:[],posts:[],selected:[],failures:[]});
  f.run('renderImport(preview)');assert.match(text(f.get('import-preview')),/saved, and shared with your Team Hub, when you import its first posts/);
}

async function staleSharedForms(){
  const defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:'Before'},oldBefore={engine:'codex',author:'Before'},freshBefore={engine:'claude',author:'Other studio'};
  let saved=false,reads=0;const requests=[];
  const f=fixture((url,options)=>{
    if(options?.method==='POST'){const data=JSON.parse(options.body);requests.push({url,data});if(!saved)return {__http:400,error:'Shared settings changed in another studio. Reload before saving.'};return {defaults:{...defaults,...data},shared_before:freshBefore,workspace:'/synthetic'};}
    if(url==='/api/run-settings'){reads++;return {defaults:{...defaults,engine:'claude',author:'Other studio'},shared_before:freshBefore,workspace:'/synthetic'};}
    if(url==='/api/run-options')return {settings:{defaults},sources:[],profiles:[],agents:{}};if(url==='/api/team')return {};return empty();
  });
  f.loadRunner();f.set('defaults',defaults);f.set('before',oldBefore);f.run("studio.settings={defaults,shared_before:before,workspace:'/synthetic'};studio.screen='settings';sSettings()");
  const byId=id=>descendants(f.get('studio-page')).find(e=>e.id===id);
  let input=byId('settings-author');input.value='My stale author';input.listeners.input();
  input=byId('settings-tone');input.value='Unsaved local tone';input.listeners.input();
  await f.get('studio-page').children.find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(reads,0,'refusal never silently reloads or retries');assert.equal(requests.length,1);
  let reload=descendants(f.get('studio-page')).find(e=>e.textContent==='Reload shared settings');assert.ok(reload);
  await reload.listeners.click();assert.equal(reads,1);assert.equal(requests.length,1);
  assert.equal(byId('settings-author').value,'Other studio');assert.equal(byId('settings-tone').value,'Unsaved local tone');
  saved=true;await f.get('studio-page').children.find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.deepEqual(requests[1].data.shared_before,freshBefore);assert.equal(requests[1].data.engine,'claude');assert.equal(requests[1].data.tone,'Unsaved local tone');

  for(const kind of ['brand','team']){
    let current=false;const posted=[];
    const old=kind==='brand'?{repository:'/synthetic/brand',release:'v1.0.0',skills:[],shared_before:{repository:'/synthetic/brand',release:'v1.0.0'}}:{repository:'/synthetic/team',branch:'main',share:'decision',shared_before:{team:{repository:'/synthetic/team',branch:'main'},share:'decision'}};
    const fresh=kind==='brand'?{...old,release:'v2.0.0',shared_before:{repository:'/synthetic/brand',release:'v2.0.0'}}:{...old,share:'asked',shared_before:{team:{repository:'/synthetic/team',branch:'main'},share:'asked'}};
    const g=fixture((url,options)=>{
      if(options?.method==='POST'){posted.push({url,data:JSON.parse(options.body)});if(!current)return {__http:400,error:'Shared settings changed in another studio. Reload before saving.'};return fresh;}
      if(url==='/api/'+kind){current=true;return fresh;}if(url==='/api/run-settings')return {defaults,workspace:'/synthetic'};if(url==='/api/run-options')return {settings:{defaults},sources:[],profiles:[],agents:{}};return empty();
    });
    g.loadRunner();g.set('shown',old);g.set('defaults',defaults);g.run("studio.settings={defaults,workspace:'/synthetic'};studio.screen='settings';studio."+kind+"=shown;sPage("+(kind==='brand'?'sBrandCard()':'sTeamCard()')+")");
    const fields=()=>descendants(g.get('studio-page'));
    const field=fields().find(e=>e.id===(kind==='brand'?'brand-release':'team-sharing'));
    await field.parent.parent.listeners.submit({preventDefault(){}});
    assert.equal(posted.length,1);assert.deepEqual(posted[0].data.shared_before,old.shared_before);
    reload=fields().find(e=>e.textContent==='Reload shared settings');await reload.listeners.click();assert.equal(posted.length,1);
    const refreshed=fields().find(e=>e.id===(kind==='brand'?'brand-release':'team-sharing'));
    assert.equal(refreshed.value,kind==='brand'?'v2.0.0':'asked');
    await refreshed.parent.parent.listeners.submit({preventDefault(){}});
    assert.equal(posted.length,2);assert.deepEqual(posted[1].data.shared_before,fresh.shared_before);
  }
}

async function sharedSettings(){
  const requests=[],defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:'Before'},before={engine:'codex',author:'Before'};
  const f=fixture((url,options)=>{if(options?.method==='POST'){requests.push({url,data:JSON.parse(options.body)});return {defaults,shared_before:before,workspace:'/synthetic'};}if(url==='/api/run-options')return {settings:{defaults},sources:[],profiles:[],agents:{}};if(url==='/api/team')return {};return empty();});
  f.loadRunner();f.set('defaults',defaults);f.set('before',before);f.run("studio.settings={defaults,shared_before:before,workspace:'/synthetic'};studio.screen='settings';sSettings()");
  assert.equal(descendants(f.get('studio-page')).filter(e=>e.type==='checkbox').length,0,'shared saves have no second consent toggle');
  const input=descendants(f.get('studio-page')).find(e=>e.id==='settings-author');input.value='New Author';input.listeners.input();
  await f.get('studio-page').children.find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(requests[0].url,'/api/run-settings');assert.equal(requests[0].data.author,'New Author');
  assert.deepEqual(requests[0].data.shared_before,before);assert.equal('for_all_studios' in requests[0].data,false);
}

async function brandInputs(){
  const requests=[],defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''};
  let found={repository:'/synthetic/brand-repo',release:'',runtime:'/synthetic/brand-two',name:'Synthetic Brand',version:'1.0.0',skills:[{runtime:'/synthetic/brand-one',name:'Brand one',version:'1.0.0'},{runtime:'/synthetic/brand-two',name:'Brand two',version:'1.0.0'}],brands:[{brand:'fictional',name:'Fictional identity',variants:['light','dark']}],checked:{tag:'v1.2.0',version:'1.2.0',commit:'a'.repeat(40)},job:{}};
  const f=fixture((url,options)=>{if(options?.method==='POST'){requests.push({url,data:JSON.parse(options.body)});if(url==='/api/brand-configure'){found={...found,...requests.at(-1).data};return found;}if(url==='/api/brand-install')return {...found,job:{status:'working',message:'Installing…'}};}
    if(url==='/api/brand')return found;if(url==='/api/run-settings')return {defaults,workspace:'/synthetic',configured:true};if(url==='/api/run-options')return {settings:{defaults},brand:found,sources:[],profiles:[],agents:{codex:true}};if(url==='/api/team')return {};if(url==='/api/computer')return {checks:[],brand:found};return empty();});
  f.loadRunner();f.set('brand',found);f.set('defaults',defaults);f.run("studio.brand=brand;studio.settings={defaults,workspace:'/synthetic'};studio.screen='settings';sSettings()");
  const byId=id=>descendants(f.get('studio-page')).find(e=>e.id===id);
  assert.equal(byId('brand-skill').value,'/synthetic/brand-two');
  assert.equal(byId('brand-repository').value,'/synthetic/brand-repo');
  let input=byId('brand-release');input.value='v1.1.0';input.listeners.input();
  await input.parent.parent.listeners.submit({preventDefault(){}});
  assert.deepEqual(requests.pop(),{url:'/api/brand-configure',data:{repository:'/synthetic/brand-repo',release:'v1.1.0'}});
  input=byId('brand-skill');input.value='/synthetic/brand-one';input.listeners.change();
  await input.parent.parent.listeners.submit({preventDefault(){}});
  assert.deepEqual(requests.pop(),{url:'/api/brand-configure',data:{runtime:'/synthetic/brand-one'}});
  const install=descendants(f.get('studio-page')).find(e=>e.tagName==='button'&&e.textContent==='Install selected release');
  await install.listeners.click();assert.equal(requests.length,0,'opening the install sheet must run nothing');
  assert.match(text(f.get('sheet')),/v1.2.0/);assert.match(text(f.get('sheet')),new RegExp('a'.repeat(40)));
  const confirm=descendants(f.get('sheet')).find(e=>e.textContent==='Install it now');await confirm.listeners.click();
  assert.deepEqual(requests.pop(),{url:'/api/brand-install',data:{confirmed:true,repository:found.repository,tag:'v1.2.0',commit:'a'.repeat(40)}});
  f.set('brand',found);f.run("studio.options={brand};studio.screen='new';studio.draft={brand:'fictional',variant:'dark'};sPage(sBrandChoice(studio.draft))");
  assert.equal(byId('new-brand-variant').value,'dark');
  input=byId('new-brand');input.value='';input.listeners.change();
  assert.equal(f.run('studio.draft.brand'),'');assert.equal(f.run('studio.draft.variant'),'');
}

function pageDefinesEveryElement(){
  // The fixture creates any element on demand, so check the real page defines every id the script asks for.
  const base='skills/blog-studio/assets/management/';
  const script=fs.readFileSync(base+'app.js','utf8')+fs.readFileSync(base+'runner.js','utf8'),page=fs.readFileSync(base+'index.html','utf8');
  const defined=new Set([...page.matchAll(/id="([^"]+)"/g)].map(m=>m[1]));
  const wanted=new Set([...script.matchAll(/\$\('([a-z0-9-]+)'\)/g)].map(m=>m[1]));
  for(const prefix of ['upload','import'])for(const m of script.matchAll(/\$\(prefix\+'(-[a-z-]+)'\)/g))wanted.add(prefix+m[1]);
  for(const name of ['folder','export','url','links','scope','collection','name'])wanted.add('import-'+name+'-field');
  const created=new Set([...script.matchAll(/\.id='([a-z0-9-]+)'/g)].map(m=>m[1]));
  for(const match of script.matchAll(/sField\('([a-z0-9-]+)'/g))created.add(match[1]);
  const missing=[...wanted].filter(id=>!defined.has(id)&&!created.has(id));
  assert.deepEqual(missing,[],'app.js uses ids that index.html does not define');
}

async function guidedRuns(){
  const requests=[];
  const found={id:'synthetic',title:'Synthetic blog',status:'waiting-for-approval',next:'outline',approval:'page',expected:'version-1',enabled:true,directory:'/synthetic/articles/synthetic',content:'# Outline\nSynthetic writing.',seconds:600,engine:'codex',mode:'write',decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},stages:[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'draft',notes:'Assistant judgment, not verification.'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'pending'}]};
  const updated={...found,next:'draft',expected:'version-2',status:'queued',stages:[{...found.stages[0],status:'approved'},found.stages[1]]};
  const shown={id:found.id,title:found.title,name:'OUTLINE.md',stage:'outline',label:'Outline',expected:found.expected,status:'draft',content:found.content,notes:found.stages[0].notes,checks:[{label:'A readable file',passed:true}],previous:null,diff:[]};
  const f=fixture((url,options)=>{requests.push({url,options});if(url==='/api/run-approve')return updated;if(url.startsWith('/api/run?'))return updated;return {items:[],total:0};});
  f.loadRunner();f.set('found',found);f.set('shown',shown);f.run("studio.screen='gate';studio.found=found;sGate(found,shown)");
  const content=f.get('studio-page');
  assert.ok(descendants(content).some(e=>/^h[1-6]$/.test(e.tagName)&&descendants(e).some(n=>n.textContent==='Outline')));
  assert.ok(descendants(content).some(e=>e.textContent==='Checked for you'));
  assert.ok(descendants(content).some(e=>e.textContent==='Worth a look'));
  const approve=f.get('actions').children.find(e=>e.textContent==='Use this outline');await approve.listeners.click();
  assert.equal(requests.length,0,'opening the confirmation must not approve');
  assert.equal(f.get('sheet').hidden,false);assert.equal(f.get('main').inert,true);
  const confirm=descendants(f.get('sheet')).find(e=>e.textContent==='Approve');await confirm.listeners.click();
  assert.equal(requests[0].url,'/api/run-approve');
  assert.deepEqual(JSON.parse(requests[0].options.body),{id:'synthetic',expected:'version-1'});
  assert.equal(f.get('sheet').hidden,true);assert.equal(f.get('main').inert,false);
  for(const mode of ['balanced','automatic']){
    const calls=[];const direct=fixture((url,options)=>{calls.push({url,options});return url==='/api/run-approve'||url.startsWith('/api/run?')?updated:{items:[],total:0};});
    direct.loadRunner();direct.set('found',{...found,review_level:mode});direct.set('shown',{...shown,bundle:[{stage:'research',label:'Research findings',content:'# Synthetic evidence'}]});
    direct.run("studio.screen='gate';studio.found=found;sGate(found,shown)");
    assert.ok(descendants(direct.get('studio-page')).some(e=>e.textContent==='Research findings'));
    await direct.get('actions').children.find(e=>e.textContent==='Use this outline').listeners.click();
    assert.equal(calls[0].url,'/api/run-approve','grouped reviews approve the displayed revision directly');
    assert.deepEqual(JSON.parse(calls[0].options.body),{id:'synthetic',expected:'version-1'});
  }
  f.set('found',{...found,approval:'conversation',status:'in-chat'});f.run('renderRun(found)');
  assert.ok(f.get('actions').children.some(e=>e.textContent==='Run this from here'));
  assert.ok(!f.get('actions').children.some(e=>e.textContent==='Approve'));
  f.set('found',{...found,status:'failed',error:'Synthetic failure',enabled:false});f.run('renderRun(found)');
  assert.ok(f.get('actions').children.some(e=>e.textContent==='Try again'));
  assert.ok(descendants(content).some(e=>e.textContent==='Synthetic failure'));
  f.set('found',found);f.run('studio.listing=[found];sHome()');
  assert.equal(f.get('title').textContent,'Home');assert.equal(f.get('needs-count').textContent,'1');
  assert.ok(descendants(content).some(e=>e.textContent==='Needs you'));
  assert.equal(f.get('actions').children[0].className,'button','a review leads, so New blog is a plain button');
  assert.ok(f.get('actions').children.some(e=>e.textContent==='Review Synthetic blog'&&e.className==='button button-filled'));
  const working={...updated,id:'working',title:'Working blog'};f.set('working',working);f.run('studio.listing=[found,working];sHome()');
  const homeGroup=name=>descendants(content).find(e=>e.tagName==='section'&&e.children[0]&&e.children[0].textContent===name);
  assert.ok(descendants(homeGroup('Needs you')).some(e=>e.textContent==='Synthetic blog'));
  assert.ok(!descendants(homeGroup('Needs you')).some(e=>e.textContent==='Working blog'),'work that is not waiting stays out of Needs you');
  assert.ok(descendants(homeGroup('In progress')).some(e=>e.textContent==='Working blog'));
  assert.equal(f.get('needs-count').textContent,'1');
  f.run('studio.listing=[working];sHome()');
  assert.equal(f.get('actions').children[0].className,'button button-filled','nothing waits, so New blog leads');
  assert.ok(!f.get('actions').children.some(e=>e.textContent==='Review Working blog'));
  assert.equal(f.get('actions').children[0].disabled,false);
  f.run('access.actions.edit=false;sHome()');
  assert.equal(f.get('actions').children[0].disabled,true,'New blog follows edit access');
  f.run('access.actions.edit=true');
  f.run('studio.listing=[found];sHome()');
  f.run('studio.ordinary=[];sBlogs()');assert.equal(f.get('title').textContent,'Your blogs');
  assert.ok(descendants(content).some(e=>e.textContent==='Synthetic blog'));
  f.run("studio.computer={checks:[{label:'Codex',status:'action',detail:'Sign-in needed',next_step:'Run codex login'}]};studio.settings={workspace:'/synthetic'};sStatusPage()");
  assert.ok(descendants(content).some(e=>e.textContent==='Run codex login'));
  assert.ok(f.get('actions').children.some(e=>e.textContent==='Check this computer'));
  // Safe Markdown turns no document-supplied HTML or javascript link into active content.
  f.run("sPage(window.TrainingStudioMarkdown.render('<script>bad()</script> [bad](javascript:bad()) [good](https://example.com)'))");
  assert.equal(descendants(content).some(e=>e.tagName==='script'),false);
  assert.equal(descendants(content).filter(e=>e.tagName==='a').length,1);
  const defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''};
  f.set('defaults',defaults);f.run("studio.options={settings:{defaults},sources:[],profiles:[],agents:{codex:true}};studio.screen='new';studio.draft={...defaults,step:0,id:'',title:'A synthetic blog',goal:'Explain a fictional gateway',audience:'Authors',profile:'',sources:[],manuscript:'',mode:'write',minutes:'10',operation:'a'.repeat(32)};sWizard()");
  assert.equal(f.get('above').textContent,'New writing');
  let form=f.get('studio-page').children.find(e=>e.tagName==='form');await form.listeners.submit({preventDefault(){}});
  assert.ok(descendants(f.get('studio-page')).some(e=>e.textContent==='Ready to start'));
  assert.ok(descendants(f.get('studio-page')).some(e=>e.textContent==='Start writing'));
  f.run("studio.draft.step=0;studio.draft.mode='from-outline';studio.draft.outline_text='## Supplied outline';sWizard()");
  assert.equal(descendants(f.get('studio-page')).find(e=>e.id==='new-outline').value,'## Supplied outline');
  f.run('sChanges(found, "outline")');const note=descendants(f.get('sheet')).find(e=>e.tagName==='textarea');note.value='Keep my request';
  await f.run('sPoll()');assert.equal(note.value,'Keep my request');
  // A newer server version cannot silently replace the document being read or be approved.
  f.run("sCloseSheet();studio.screen='gate';studio.id=found.id;studio.found=found;sGate(found,shown)");
  const visibleDocument=f.get('studio-page').children.at(-1);
  await f.run('sPoll()');
  assert.equal(f.get('studio-page').children.at(-1),visibleDocument);
  assert.equal(f.get('actions').children.find(e=>e.textContent==='Use this outline').disabled,true);
  f.set('found',{...updated,complete:true,next:null,stages:updated.stages.map(e=>({...e,status:'approved'}))});
  f.run('sGate(found,{...shown,status:"approved"})');
  assert.ok(f.get('actions').children.some(e=>e.textContent==='Ask for changes'));
  assert.ok(!f.get('actions').children.some(e=>e.textContent==='Approve'));
  // Navigation while creation is pending must keep the person's current view.
  const pending=deferred();const g=fixture(()=>pending.promise);g.loadRunner();g.set('defaults',defaults);
  g.run("studio.screen='new';studio.draft={...defaults,id:'',title:'A fixture',goal:'Explain',audience:'Authors',profile:'',sources:[],mode:'write',minutes:'10',operation:'a'.repeat(32)}");
  const creating=g.run("sStartBlog(studio.draft,document.createElement('button'),document.createElement('p'))");
  g.run("studio.turn++;studio.screen='blogs'");pending.resolve(found);await creating;
  assert.equal(g.run('studio.screen'),'blogs');
}


async function contextualTools(){
  const calls=[];
  const f=fixture((url,options)=>{
    calls.push([url,options?.body]);
    if(url.startsWith('/api/tools'))return {id:'fixture',title:'Synthetic draft',has_manuscript:true,working:false,google:{document_id:'doc'},history:[{revision:'draft-1.md'}],next_offset:null,jobs:[{id:'a'.repeat(32),kind:'repurpose',status:'ready'}]};
    if(url.startsWith('/api/voices'))return {profiles:[{id:'voice',name:'Synthetic Author',revision:1,status:'provisional'}],samples:[{id:'sample',name:'Authored passage',author:'Synthetic Author'}]};
    if(url.startsWith('/api/voice?'))return {id:'voice',name:'Synthetic Author',revision:1,status:'provisional',guide:'A short synthetic voice guide.',sample_ids:['sample'],expected:'profile-version'};
    if(url.startsWith('/api/tool-history'))return {scope:'Local manuscript only',expected:'restore-version',changes:{changes:[{section:'Opening',before:'Current',after:'Earlier'}],truncated:false}};
    if(url.startsWith('/api/prepublish'))return {findings:[],coverage:'Remote claims not verified.'};
    if(url.startsWith('/api/interview'))return {id:'fixture',title:'Synthetic interview',expected:'interview-version',answers:[{id:'answer',question:'Main point?',answer:'Synthetic answer'}],question:'Example?',outline:false};
    if(url.startsWith('/api/variant?'))return {id:'fixture',name:'launch-copy',content:'Human-edited copy',expected:'copy-version',provenance:{format:'summary',source_sha256:'a'.repeat(64)}};
    if(url.startsWith('/api/variants'))return {id:'fixture',variants:[{name:'launch-copy',content:'Human-edited copy',provenance:{format:'summary',source_sha256:'a'.repeat(64)}}]};
    return {};
  });f.loadRunner();
  await f.run("sMoreTools('fixture')");
  const sheet=()=>descendants(f.get('sheet'));
  assert.ok(sheet().some(node=>node.textContent==='Compare Google and local text'));
  assert.ok(sheet().some(node=>node.textContent==='Saved manuscript revisions'));
  assert.ok(sheet().some(node=>node.textContent==='Resume repurpose · ready'));
  assert.equal(calls.some(([url,body])=>body),false);
  await f.run("sVoiceTools('fixture')");assert.ok(sheet().some(node=>node.textContent==='Learn a voice from samples'));
  await f.run("sVoiceProfile('voice','fixture')");assert.ok(sheet().some(node=>node.textContent==='Use this revision for this article'));
  assert.ok(sheet().some(node=>node.textContent==='Export voice guide'));
  await f.run("sInterview('fixture')");assert.ok(sheet().some(node=>node.textContent==='Save revised answer'));
  assert.ok(sheet().some(node=>node.textContent==='I have enough — prepare an outline'));
  await f.run("sVariants('fixture')");assert.ok(sheet().some(node=>node.textContent==='Open launch-copy'));
  await f.run("sVariant('fixture','launch-copy')");assert.ok(sheet().some(node=>node.id==='saved-copy-text'&&node.value==='Human-edited copy'));
  assert.ok(sheet().some(node=>node.textContent==='Save this copy locally'));
  f.set('job',{id:'a'.repeat(32),kind:'repurpose',status:'ready',metadata:{article:'fixture',words:150},result:{content:'Prepared copy',notes:'No posting'},source_changed:true});
  await f.run('sToolJob(job)');assert.ok(sheet().some(node=>node.textContent==='Return to current source'));
  assert.equal(sheet().some(node=>node.textContent==='Save named copy'),false);
  const pending=deferred(),g=fixture(()=>pending.promise);g.loadRunner();
  const read=g.run("sHistoryPreview({id:'fixture'},'draft-1.md')");g.run('sCloseSheet()');pending.resolve({changes:{changes:[]},scope:'Local'});await read;
  assert.equal(g.run('studio.sheet'),null);
  const slow=deferred(),h=fixture(()=>slow.promise);h.loadRunner();const reading=h.run("sPrepublishTool('fixture')");h.run('sCloseSheet()');slow.resolve({findings:[],coverage:'Local'});await reading;assert.equal(h.run('studio.sheet'),null);
}

// The pattern every studio shares: the start form says where it stops, the run says what it
// is doing now and for how long, a retry says what it costs, a note reaches the next job
// without stopping, and a phone keeps one decision in the toolbar.
async function sharedPattern(){
  const requests=[];const found={id:'synthetic',title:'Synthetic blog',status:'working',next:'draft',approval:'page',expected:'version-1',enabled:true,directory:'/synthetic/articles/synthetic',seconds:600,engine:'codex',mode:'write',review_level:'balanced',decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},started_at:new Date(Date.now()-3*60000).toISOString(),note_stage:'review',notes:{},stages:[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'approved'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'pending'},{stage:'review',label:'Review',path:'REVIEW.md',status:'pending'}]};
  const f=fixture((url,options)=>{requests.push({url,options,data:options?.body?JSON.parse(options.body):null});return url.startsWith('/api/run?')?found:{...found,noted:'draft'};});f.loadRunner();
  const text=()=>descendants(f.get('studio-page')).map(e=>e.textContent);
  // The start form: one line says where this run stops, from the shared review level.
  const defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''};f.set('defaults',defaults);
  f.run("studio.options={settings:{defaults,review_level:'balanced'},sources:[],profiles:[],agents:{codex:true}};studio.screen='new';studio.draft={...defaults,step:1,id:'',title:'A synthetic blog',goal:'Explain',audience:'Authors',profile:'',sources:[],manuscript:'',mode:'write',stop:'draft',minutes:'10',operation:'a'.repeat(32)};sWizard()");
  assert.ok(text().some(t=>t==='Balanced: it stops for the outline and the draft'),'the stops line follows the review level and the pipeline: '+text().join('|'));
  {const voice=descendants(f.get('studio-page')).find(e=>e.id==='new-profile');assert.ok(voice,'the second step chooses the voice');let node=voice,inside=false;while(node){if(node.tagName==='details')inside=true;node=node.parent;}assert.equal(inside,false,'Write as is visible without opening a disclosure');
   assert.equal(voice.parent.children.find(e=>e.tagName==='label').textContent,'Write as');assert.deepEqual(voice.children.map(o=>o.textContent),['No particular voice'],'without saved profiles, only no particular voice');
   const tone=descendants(f.get('studio-page')).find(e=>e.id==='new-tone');node=tone;inside=false;while(node){if(node.tagName==='details')inside=true;node=node.parent;}assert.equal(inside,true,'the tone stays in the Voice and brand disclosure');
   f.run("studio.options.profiles=[{id:'p2',name:'Sam',status:'provisional'}];studio.options.default_voice={profile_id:'p1',name:'Avery'};sWizard()");
   assert.deepEqual(descendants(f.get('studio-page')).find(e=>e.id==='new-profile').children.map(o=>[o.value,o.textContent]),[['p1','Me'],['p2','Sam (provisional)'],['','No particular voice']]);
   f.run("studio.options.profiles=[];studio.options.default_voice=null;sWizard()");}
  f.run("studio.options.settings.review_level='balanced';studio.draft.mode='from-outline';studio.draft.stop='package';sWizard()");
  assert.ok(text().some(t=>t==='Balanced: it stops for the draft and the export package'),'Balanced reads the first writing stage a run has: '+text().join('|'));
  f.run("studio.draft.mode='write';studio.draft.stop='draft';sWizard()");
  const change=descendants(f.get('studio-page')).find(e=>e.tagName==='a'&&e.textContent==='Change');assert.equal(change.href,'/onboarding/#fixture');
  assert.equal(descendants(f.get('studio-page')).some(e=>['new-engine','new-minutes'].includes(e.id)),false,'the assistant and time limit are defaults, not per-blog decisions');
  f.run("studio.options.settings.review_level='automatic';studio.draft.mode='ideas';sWizard()");
  assert.ok(text().some(t=>t==='Automatic draft: it stops for the ideas'),text().join('|'));
  f.run("studio.options.settings.review_level='step_by_step';studio.draft.mode='write';studio.draft.research='supplied-only';studio.draft.stop='package';sWizard()");
  assert.ok(text().some(t=>t==='Step by step: it stops for the outline, the draft, the review and the export package'),'selected sources with none selected is no research: '+text().join('|'));
  f.run("studio.draft.sources=['one'];sWizard()");
  assert.ok(text().some(t=>t==='Step by step: it stops for the research plan, the research findings, the outline, the draft, the review and the export package'),text().join('|'));
  // New blog without a task chosen shows the same start cards as Home.
  f.run("studio.draft={...defaults,mode:null,step:0};sWizard()");
  assert.equal(f.get('title').textContent,'New blog');assert.ok(descendants(f.get('studio-page')).some(e=>e.className==='pick-card'&&e.textContent==='Write from a brief'));
  // Settings no longer ask where to stop: the review level governs that.
  f.run("studio.settings={defaults,workspace:'/synthetic',shared_before:{}};studio.team={};studio.brand=null;sSettings()");
  assert.equal(descendants(f.get('studio-page')).some(e=>e.id==='settings-stop'),false);
  // The run: a "now" line under the title, with the step and how long it has taken.
  f.set('found',found);f.run('studio.screen=\'run\';studio.id=found.id;sRun(found)');
  const now=descendants(f.get('studio-page')).find(e=>e.className==='now-line');
  assert.equal(now.textContent,'Drafting · 3 min of up to 10');
  f.run('studio.signature=JSON.stringify(found);const realNow=Date.now;Date.now=()=>realNow()+4*60000');await f.run('sPoll()');
  assert.equal(descendants(f.get('studio-page')).find(e=>e.className==='now-line').textContent,'Drafting · 7 min of up to 10','the now line ticks while nothing else changes');
  assert.ok(text().some(t=>/cost is not tracked for a CLI account/.test(t)),'About says once that cost is not tracked');
  // A note for the next step goes with the next job and stops nothing.
  const note=descendants(f.get('studio-page')).find(e=>e.id==='note-request');note.value='Mention the gateway.';note.listeners.input();
  await descendants(f.get('studio-page')).find(e=>e.textContent==='Add the note').listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/run-note').data,{id:'synthetic',expected:'version-1',request:'Mention the gateway.'});
  assert.ok(text().some(t=>/goes with the next job that starts, review/.test(t)),'the box names the stage the runner would note for');
  f.set('found',{...found,note_stage:null});f.run('sRun(found)');assert.equal(descendants(f.get('studio-page')).some(e=>e.id==='note-request'),false,'no later step, no box');
  // A time limit that ran out offers more time, and says what a plain retry costs.
  f.set('found',{...found,status:'failed',enabled:false,started_at:null,error:'This step reached its time limit. Retry or continue in chat.'});f.run('sRun(found)');
  const more=f.get('actions').children.find(e=>e.textContent==='Try again with more time');assert.equal(more.className,'button button-filled');
  assert.ok(text().some(t=>t==='Try again re-runs the draft from the start with the same 10-minute limit. More time doubles it to 20 minutes.'),text().join('|'));
  await more.listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/run-retry').data,{id:'synthetic',expected:'version-1',seconds:1200});
  // Copy Markdown sits beside the download.
  const shown={id:found.id,title:found.title,name:'DRAFT.md',stage:'draft',label:'Draft',expected:found.expected,status:'draft',content:'# Draft',notes:'',checks:[],previous:null,diff:[]};
  f.set('shown',shown);f.run("studio.screen='gate';studio.found=found;sGate({...found,status:'waiting-for-approval'},shown)");
  assert.ok(descendants(f.get('studio-page')).some(e=>e.textContent==='Copy Markdown'));
  // A phone keeps one decision in the toolbar and folds the rest into the menu.
  f.run("window.matchMedia=query=>({matches:/max-width/.test(query)});studio.screen='run';sRun({...found,status:'waiting-for-approval',enabled:true,error:'',stages:[found.stages[0],{...found.stages[1],status:'draft'}]})");
  const actions=f.get('actions').children;
  assert.equal(actions.filter(e=>e.tagName==='button').length,1,'one action stays in the toolbar on a phone');
  assert.equal(actions[0].textContent,'Review Draft');assert.equal(actions[0].className,'button button-filled');
  const menu=actions.find(e=>e.tagName==='details');assert.equal(menu.className,'menu');
  assert.deepEqual(descendants(menu).filter(e=>e.className==='menu-item').map(e=>e.textContent),['Edit manuscript','Pause','More tools']);
  f.run('delete window.matchMedia');
}


// A real finish: the final stop shows the draft open with Finish, a finished run has a Done
// card, Delete asks for the typed title and says what is running stops, Blogs lists what was
// New blog from my files: one screen uploads every file at once with its role and says what each has,
// the run starts from the readable ones, and the angles gate offers picks or none of these.
async function filesJourney(){
  const requests=[];
  const defaults={engine:'codex',seconds:600,research:'supplied-only',stop:'package',tone:'Clear',author:''};
  const uploaded={files:[{filename:'notes.md',source:{id:'s1',name:'notes'},state:'ready',chars:1200,note:''},{filename:'scan.pdf',source:{id:'s2',name:'scan'},state:'pending',chars:0,note:'This computer has no PDF reader (pdftotext), so this PDF needs text.'}],receipts:[],state:'saved',next_step:'1 of 2 files have text.'};
  const found={id:'files',title:'From my files',status:'queued',next:'angles',approval:'page',expected:'a1',enabled:true,directory:'/synthetic',seconds:600,engine:'codex',mode:'from-files',review_level:'balanced',decisions:[],brief:{goal:'A team post',audience:'To be chosen with the angle.'},stages:[{stage:'angles',label:'Angles',path:'derived/blog-angles.md',status:'pending'}],excerpted:[]};
  const f=fixture((url,options)=>{requests.push({url,data:options?.body?JSON.parse(options.body):null});
    if(url==='/api/run-options')return {settings:{defaults,review_level:'balanced'},sources:[],profiles:[{id:'p1',name:'Avery',status:'confirmed'},{id:'p2',name:'Sam',status:'provisional'}],default_voice:{profile_id:'p1',name:'Avery'},agents:{codex:true}};
    if(url==='/api/upload')return (JSON.parse(options.body).files||[]).some(e=>e.google)?{files:[{filename:'Messaging Doc',source:{id:'s9',name:'Messaging Doc'},state:'ready',chars:4200,note:'',link:'https://docs.google.com/document/d/abc/edit'}]}:uploaded;
    if(url==='/api/source-role')return {id:JSON.parse(options.body).id,role:JSON.parse(options.body).role};
    if(url==='/api/run-create'||url.startsWith('/api/run?'))return found;
    if(url.startsWith('/api/run-'))return found;
    return {items:[],total:0};});
  f.loadRunner();f.run('sHome()');
  const nodes=()=>descendants(f.get('studio-page')),text=()=>nodes().map(e=>e.textContent),byId=id=>nodes().find(e=>e.id===id);
  const card=nodes().find(e=>e.className==='pick-card'&&e.textContent==='New blog from my files');
  assert.ok(card,'Home offers New blog from my files: '+text().join('|'));
  assert.ok(descendants(card).some(e=>/say what each file is for; then find angles, or give the point/.test(e.textContent)),'the card says what the screen does');
  await card.listeners.click();
  assert.equal(f.get('title').textContent,'New blog from my files');
  const picker=byId('files-input');
  assert.equal(picker.type,'file');assert.equal(picker.multiple,true);assert.match(picker.accept,/\.pdf/);
  assert.ok(byId('files-goal'),'one optional line: what is this for');
  assert.equal(byId('files-web').checked,false,'web research is off by default');
  assert.equal(byId('files-keep').checked,false,'files are not kept in the references by default');
  const start=()=>nodes().find(e=>e.type==='submit');
  assert.equal(start().disabled,true,'nothing to start before a file has text');
  assert.equal(start().textContent,'Find three angles');
  assert.ok(text().some(t=>/stops for the angles/.test(t)),'the stops line names the angles: '+text().join('|'));
  // Each upload says what the files are for: facts by default, or an example of the kind of post.
  const role=()=>byId('files-role');
  assert.equal(role().tagName,'select');assert.equal(role().value,'material');
  assert.deepEqual(role().children.map(o=>[o.value,o.textContent]),[['material','Facts (may be quoted)'],['inspiration','Example of the kind of post']]);
  // Write as: Me is the default voice, a provisional profile says so, and no voice shows the tone.
  const voice=()=>byId('files-voice');
  assert.equal(voice().value,'p1','Me, the personal default voice, is chosen first');
  assert.deepEqual(voice().children.map(o=>[o.value,o.textContent]),[['p1','Me'],['p2','Sam (provisional)'],['','No particular voice']]);
  assert.equal(byId('files-tone'),undefined,'a chosen voice needs no tone');
  voice().value='';voice().listeners.change();
  assert.ok(byId('files-tone'),'no particular voice: the tone field appears');
  voice().value='p1';voice().listeners.change();
  assert.equal(byId('files-tone'),undefined);
  // Every chosen file goes up in one request, as material, each with its role.
  picker.files=[{name:'notes.md',size:12,arrayBuffer:async()=>new TextEncoder().encode('Notes words.').buffer},{name:'scan.pdf',size:4,arrayBuffer:async()=>new TextEncoder().encode('%PDF').buffer}];
  await picker.listeners.change();
  const upload=requests.filter(r=>r.url==='/api/upload');
  assert.equal(upload.length,1);
  assert.deepEqual(upload[0].data.files.map(e=>e.filename),['notes.md','scan.pdf']);
  assert.deepEqual(upload[0].data.files.map(e=>e.purpose),['material','material']);
  assert.equal(upload[0].data.purpose,'material');assert.equal(upload[0].data.keep,false);assert.equal(upload[0].data.analyze,false);
  assert.match(upload[0].data.operation,/^[0-9a-f]{32}$/);
  assert.ok(text().some(t=>/1,200 characters/.test(t)),'each file shows its extracted size: '+text().join('|'));
  assert.ok(text().some(t=>/Needs text/.test(t)),'a file without text says so');
  assert.ok(text().some(t=>/no PDF reader/.test(t)),'and why');
  assert.equal(start().disabled,false);
  // A file's role can change until Start: the row's select calls source-role.
  const rowRole=()=>byId('files-role-s1');
  assert.equal(rowRole().value,'material');
  rowRole().value='inspiration';await rowRole().listeners.change();
  assert.deepEqual(requests.find(r=>r.url==='/api/source-role').data,{id:'s1',role:'example'});
  assert.equal(byId('files-role-s1').value,'inspiration','the row keeps the new role');
  byId('files-role-s1').value='material';await byId('files-role-s1').listeners.change();
  assert.deepEqual(requests.filter(r=>r.url==='/api/source-role').at(-1).data,{id:'s1',role:'facts'});
  // Example files go up with inspiration; the select applies to the next upload.
  role().value='inspiration';role().listeners.change();
  byId('files-input').files=[{name:'earlier.md',size:4,arrayBuffer:async()=>new TextEncoder().encode('Post').buffer}];
  await byId('files-input').listeners.change();
  assert.deepEqual(requests.filter(r=>r.url==='/api/upload').at(-1).data.files.map(e=>e.purpose),['inspiration']);
  byId('files-role').value='material';byId('files-role').listeners.change();
  // Keep applies to the files added after it is ticked.
  byId('files-keep').checked=true;byId('files-keep').listeners.change();
  byId('files-input').files=[{name:'more.md',size:4,arrayBuffer:async()=>new TextEncoder().encode('More').buffer}];
  await byId('files-input').listeners.change();
  assert.equal(requests.filter(r=>r.url==='/api/upload').at(-1).data.keep,true);
  // Large files go up in several requests, each under the page's request limit.
  const before=requests.filter(r=>r.url==='/api/upload').length,MiB=1024*1024;
  byId('files-input').files=[6,6,5].map((size,n)=>({name:'big'+n+'.md',size:size*MiB,arrayBuffer:async()=>new TextEncoder().encode('Big').buffer}));
  await byId('files-input').listeners.change();
  const parts=requests.filter(r=>r.url==='/api/upload').slice(before);
  assert.deepEqual(parts.map(r=>r.data.files.map(e=>e.filename)),[['big0.md'],['big1.md'],['big2.md']],'each request stays under the 15 MiB limit once encoded');
  assert.equal(new Set(parts.map(r=>r.data.operation)).size,parts.length,'each request has its own operation');
  const picker2=byId('files-input');picker2.files=[{name:'a.md',size:2*MiB,arrayBuffer:async()=>new TextEncoder().encode('a').buffer},{name:'b.md',size:2*MiB,arrayBuffer:async()=>new TextEncoder().encode('b').buffer}];
  await picker2.listeners.change();
  assert.deepEqual(requests.filter(r=>r.url==='/api/upload').at(-1).data.files.map(e=>e.filename),['a.md','b.md'],'small files still go up together');
  // A Google Doc link is one more file: read with this computer's Google sign-in.
  assert.ok(byId('files-google'),'the files screen takes a Google Doc link');
  assert.equal(byId('files-google').type,'url');
  const docAdd=()=>byId('files-google-add'),asked=()=>requests.filter(r=>r.url==='/api/upload'&&r.data.files.some(e=>e.google));
  await docAdd().listeners.click();
  assert.equal(asked().length,0,'an empty link sends nothing');
  assert.ok(text().some(t=>/Paste a Google Doc link first/.test(t)),'and says what to do');
  byId('files-google').value='https://docs.google.com/document/d/abc/edit';
  await docAdd().listeners.click();
  assert.equal(asked().length,1);
  assert.deepEqual(asked()[0].data.files,[{google:'https://docs.google.com/document/d/abc/edit',purpose:'material'}],'a Doc has a role too');
  assert.equal(asked()[0].data.purpose,'material');assert.match(asked()[0].data.operation,/^[0-9a-f]{32}$/);
  assert.ok(text().some(t=>/^Messaging Doc$/.test(t)),'the Doc is listed by its title: '+text().join('|'));
  assert.ok(text().some(t=>/Google Doc · 4,200 characters/.test(t)),'with how much text it has');
  assert.equal(start().disabled,false,'a Doc with text can start the blog: the screen is not left busy');
  assert.equal(docAdd().disabled,false,'and another Doc can be added');
  byId('files-goal').value='A team post';byId('files-goal').listeners.input();
  byId('files-web').checked=true;byId('files-web').listeners.change();
  assert.ok(text().some(t=>/stops for the angles/.test(t)));
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const creation=requests.find(r=>r.url==='/api/run-create').data;
  assert.equal(creation.mode,'from-files');assert.equal(creation.research,'web-allowed');assert.equal(creation.goal,'A team post');
  assert.deepEqual(creation.sources,['s1','s9'],'only files with text are pinned, once, the Google Doc among them');
  assert.equal(creation.title,'');assert.equal(creation.stop,'package');
  assert.equal(creation.point,false);assert.equal(creation.profile,'p1','Write as reaches the run');
  // I know the point: a title, the point and the reader; the run starts at the outline.
  f.run("studio.screen='new';studio.draft={...studio.options.settings.defaults,mode:'from-files',research:'supplied-only',stop:'package',files:[{id:'s1',filename:'notes.md',state:'ready',chars:1200,note:'',link:'',role:'material'}],web:false,keep:false,profile:'p1',tone:'',goal:'',title:'',audience:'',sources:[],minutes:'10',operation:'b'.repeat(32)};sWizard()");
  const how=()=>nodes().find(e=>e.attributes['aria-label']==='How to start');
  assert.deepEqual(how().children.filter(e=>e.tagName==='button').map(e=>e.textContent),['Find three angles','I know the point']);
  assert.equal(byId('files-title'),undefined,'the angles path asks for no title');
  await how().children.find(e=>e.textContent==='I know the point').listeners.click();
  assert.ok(byId('files-title')&&byId('files-point')&&byId('files-audience'),'the point path asks for the title, the point and the reader: '+text().join('|'));
  assert.equal(byId('files-goal'),undefined);
  assert.equal(start().textContent,'Start writing');
  assert.ok(text().some(t=>/^Balanced: it stops for the outline and the export package$/.test(t)),'no angles on the point path: '+text().join('|'));
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.ok(text().some(t=>/title, the point/.test(t)),'an empty point is refused on the page: '+text().join('|'));
  assert.equal(requests.filter(r=>r.url==='/api/run-create').length,1);
  byId('files-title').value='Announcing the gateway';byId('files-title').listeners.input();
  byId('files-point').value='It is generally available.';byId('files-point').listeners.input();
  byId('files-audience').value='Platform engineers';byId('files-audience').listeners.input();
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const pointed=requests.filter(r=>r.url==='/api/run-create').at(-1).data;
  assert.equal(pointed.point,true);assert.equal(pointed.title,'Announcing the gateway');assert.equal(pointed.goal,'It is generally available.');assert.equal(pointed.audience,'Platform engineers');assert.equal(pointed.mode,'from-files');
  // The angles gate: picks, a note, or none of these.
  const waiting={...found,status:'waiting-for-approval',expected:'a2',stages:[{...found.stages[0],status:'draft'}],excerpted:['notes']};
  const shown={id:'files',title:'From my files',name:'blog-angles.md',stage:'angles',label:'Angles',expected:'a2',status:'draft',content:'# Angles\n\n## Retries are a budget\n\nPlatform engineers · Retries cost · Leans on notes.md\n\n## The gateway is a contract\n\nAPI authors · The contract · Leans on notes.md\n\n## Fewer hops\n\nTeam leads · Hops · Leans on notes.md',notes:'',checks:[],previous:null,diff:[],bundle:[]};
  f.set('waiting',waiting);f.set('shown',shown);
  f.run("studio.screen='gate';studio.found=waiting;sGate(waiting,shown)");
  const actions=()=>f.get('actions').children.map(e=>e.textContent);
  assert.ok(actions().includes('Choose an angle'),actions().join('|'));assert.ok(actions().includes('None of these'),actions().join('|'));
  // Checked for you lists the passages a check found, under the check.
  f.set('copied',{...shown,checks:[{label:'Carried over from an example',passed:false,detail:['42 percent','https://example.invalid/launch']}]});
  f.run("sGate(waiting,copied)");
  const items=nodes().filter(e=>e.className==='check-detail quiet');
  assert.equal(items.length,1,'one detail list for the failing check');
  assert.deepEqual(items[0].children.map(e=>e.textContent),['42 percent','https://example.invalid/launch']);
  f.run("sGate(waiting,shown)");
  assert.ok(!actions().some(t=>/Save ideas|Use this|Finish/.test(t)),actions().join('|'));
  assert.ok(text().some(t=>/notes was excerpted|excerpted/.test(t)),'the gate says which files were excerpted: '+text().join('|'));
  const sheet=()=>descendants(f.get('sheet'));
  await f.get('actions').children.find(e=>e.textContent==='Choose an angle').listeners.click();
  const picks=sheet().filter(e=>e.className==='pick-card');
  assert.deepEqual(picks.map(e=>e.textContent),['Retries are a budget','The gateway is a contract','Fewer hops']);
  assert.ok(descendants(picks[1]).some(e=>e.textContent==='API authors · The contract · Leans on notes.md'));
  const go=sheet().find(e=>e.type==='submit');assert.equal(go.disabled,true);
  await picks[1].listeners.click();assert.equal(go.disabled,false);
  const note=sheet().find(e=>e.id==='develop-note');note.value='Short.';note.listeners.input();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.deepEqual(requests.find(r=>r.url==='/api/run-develop').data,{id:'files',expected:'a2',request:'The gateway is a contract\nShort.'});
  f.run("studio.screen='gate';studio.found=waiting;sGate(waiting,shown)");
  await f.get('actions').children.find(e=>e.textContent==='None of these').listeners.click();
  const why=sheet().find(e=>e.id==='angles-note');why.value='Closer to on-call.';why.listeners.input();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.deepEqual(requests.find(r=>r.url==='/api/run-changes').data,{id:'files',expected:'a2',request:'Closer to on-call.',stage:'angles'});
}
// recently deleted with Restore, and the ideas gate offers the headings as picks.
async function finishAndDelete(){
  const requests=[];
  const complete={id:'synthetic',title:'Synthetic blog',status:'complete',complete:true,next:null,approval:'page',expected:'version-3',enabled:false,directory:'/synthetic/articles/synthetic',seconds:600,engine:'codex',mode:'write',review_level:'step_by_step',decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},publication:null,stages:[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'approved'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'approved'},{stage:'package',label:'Export package',path:'derived/blog-package.md',status:'approved'}]};
  const deleted=[{id:'synthetic',title:'Synthetic blog',deleted_at:new Date().toISOString(),until:new Date(Date.now()+30*86400000).toISOString()}];
  const f=fixture((url,options)=>{requests.push({url,data:options?.body?JSON.parse(options.body):null});
    if(url.startsWith('/api/run-file'))return {content:'# The draft',name:'DRAFT.md'};
    if(url.startsWith('/api/article'))return {expected:'detail-1',title:'Synthetic blog'};
    if(url==='/api/schedule')return {id:'synthetic',status:'saved'};
    if(url==='/api/blog-delete')return {deleted:true,title:'Synthetic blog',notice:null};
    if(url==='/api/blog-restore')return {id:'synthetic',restored:true};
    if(url.startsWith('/api/run?'))return {...complete,publication:'https://example.com/post'};
    if(url==='/api/runs')return {items:[],total:0,deleted};
    if(url.startsWith('/api/tools'))return {id:'synthetic',title:'Synthetic blog',has_manuscript:true,working:false,google:null,history:[],next_offset:null,jobs:[]};
    if(url.startsWith('/api/run-'))return complete;
    return {items:[],total:0};});
  f.loadRunner();f.set('found',complete);
  const text=()=>descendants(f.get('studio-page')).map(e=>e.textContent),sheet=()=>descendants(f.get('sheet'));
  // The final stop: the draft is the open document, the package is handoff notes, the decision is Finish.
  const shown={id:'synthetic',title:'Synthetic blog',name:'blog-package.md',stage:'package',label:'Export package',expected:'version-2',status:'draft',content:'# Handoff',notes:'',checks:[],previous:null,diff:[],bundle:[{stage:'draft',label:'Draft',content:'# The draft text'}]};
  const atPackage={...complete,complete:false,next:'package',status:'waiting-for-approval',expected:'version-2',stages:[complete.stages[0],complete.stages[1],{...complete.stages[2],status:'draft'}]};
  f.set('shown',shown);f.set('atPackage',atPackage);
  f.run("studio.screen='gate';studio.found=atPackage;sGate(atPackage,shown)");
  const finish=f.get('actions').children.find(e=>e.textContent==='Finish');
  assert.ok(finish,'the final stop says Finish: '+f.get('actions').children.map(e=>e.textContent).join('|'));
  const papers=descendants(f.get('studio-page')).filter(e=>e.tagName==='article');
  assert.equal(papers[0].attributes['aria-label'],'Draft','the draft is the open document at the final stop');
  assert.ok(text().some(t=>t==='Handoff notes'),text().join('|'));
  assert.ok(descendants(f.get('studio-page')).some(e=>e.textContent==='Download draft'),'the download at the final stop is the draft');
  await finish.listeners.click();
  assert.ok(sheet().some(e=>e.textContent==='Finish this blog?'),sheet().map(e=>e.textContent).join('|'));
  f.run('sCloseSheet()');
  // The Done card on a finished run.
  f.run("studio.screen='run';studio.id=found.id;sRun(found)");
  const done=descendants(f.get('studio-page')).find(e=>e.tagName==='section'&&e.children[0]&&e.children[0].textContent==='Done');
  assert.ok(done,'a finished run has a Done card: '+text().join('|'));
  const labels=descendants(done).filter(e=>e.tagName==='button').map(e=>e.textContent);
  for(const label of ['Copy Markdown','Download','Mark as published','Delete this blog'])assert.ok(labels.includes(label),label+' in '+labels.join('|'));
  assert.equal(descendants(done).find(e=>e.textContent==='Delete this blog').className,'button button-danger');
  const url=descendants(done).find(e=>e.id==='published-url');url.value='https://example.com/post';url.listeners.input();
  await descendants(done).find(e=>e.textContent==='Mark as published').listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/schedule').data,{id:'synthetic',expected:'detail-1',stage:'published',confirm_stage:true,publication_url:'https://example.com/post'});
  assert.ok(text().some(t=>/Published at/.test(t)),'the card then says where it was published: '+text().join('|'));
  // Delete names the blog, says what is running stops, and waits for the typed title.
  f.run("sDeleteSheet({...found,status:'working'})");
  assert.ok(sheet().some(e=>e.textContent==='Delete Synthetic blog?'));
  assert.ok(sheet().some(e=>/running will stop/.test(e.textContent)),sheet().map(e=>e.textContent).join('|'));
  const confirm=sheet().find(e=>e.textContent==='Delete Synthetic blog');
  assert.equal(confirm.className,'button button-danger');assert.equal(confirm.disabled,true,'nothing is deleted until the title is typed');
  const typed=sheet().find(e=>e.id==='delete-title');typed.value='Synthetic';typed.listeners.input();assert.equal(confirm.disabled,true);
  typed.value='Synthetic blog';typed.listeners.input();assert.equal(confirm.disabled,false);
  await confirm.listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/blog-delete').data,{id:'synthetic',expected:'version-3',title:'Synthetic blog'});
  assert.equal(f.get('sheet').hidden,true);
  // More tools offers Delete for a saved blog, and not without one.
  await f.run("sMoreTools('synthetic')");assert.ok(sheet().some(e=>e.textContent==='Delete this blog'&&!e.disabled));
  await f.run('sMoreTools()');assert.ok(sheet().some(e=>e.textContent==='Delete this blog'&&e.disabled));
  f.run('sCloseSheet()');
  // Blogs lists what was recently deleted, with Restore.
  await f.run('sReadList()');f.run("studio.screen='blogs';sBlogs()");
  assert.ok(text().some(t=>t==='Recently deleted (1)'),text().join('|'));
  await descendants(f.get('studio-page')).find(e=>e.textContent==='Restore').listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/blog-restore').data,{id:'synthetic'});
  // The ideas gate: the headings become picks, with an optional note.
  const ideasRun={...atPackage,mode:'ideas',next:'outline',expected:'version-i',stages:[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'draft'}]};
  const ideas={...shown,stage:'outline',label:'Outline',expected:'version-i',content:'# Ideas\n\n## The first angle\n\nWhy it matters.\n\n## The second angle\n\nAnother view.\n\n## A third angle\n\nMore.',bundle:[]};
  f.set('ideasRun',ideasRun);f.set('ideas',ideas);
  f.run("studio.screen='gate';studio.found=ideasRun;sGate(ideasRun,ideas)");
  await f.get('actions').children.find(e=>e.textContent==='Develop an idea').listeners.click();
  const picks=sheet().filter(e=>e.className==='pick-card');
  assert.deepEqual(picks.map(e=>e.textContent),['The first angle','The second angle','A third angle']);
  const go=sheet().find(e=>e.textContent==='Develop this choice');assert.equal(go.disabled,true);
  await picks[1].listeners.click();assert.equal(go.disabled,false);
  const note=sheet().find(e=>e.id==='develop-note');note.value='x'.repeat(8000);note.listeners.input();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(requests.some(r=>r.url==='/api/run-develop'),false,'an over-long note is refused before it is sent');
  assert.ok(sheet().some(e=>/Keep the note under/.test(e.textContent)));
  note.value='Keep it short.';note.listeners.input();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.deepEqual(requests.find(r=>r.url==='/api/run-develop').data,{id:'synthetic',expected:'version-i',request:'The second angle\nKeep it short.'});
}

// Published posts from a list of links: the file name suggests the author, the check shows the
// site scope before anything is fetched, mixed sites ask for one, the import continues until
// every link is read, a different byline waits for the person, and learning the voice is next.
async function voiceLinksJourney(){
  const requests=[],links='# synthetic\nhttps://blog.example/team/one/\nhttps://blog.example/team/two/\n';
  const preview={status:'ready',author:'Avery Quinn',links:2,in_library:1,to_fetch:1,duplicates:1,comments:1,upgraded:0,unusable:0,skipped:[],left_out:1,shown_scope:'blog.example/team/',scope:'https://blog.example/team/',site:'blog.example',sites:[],posts:[{url:'https://blog.example/team/one/',status:'in-library',title:'One'},{url:'https://blog.example/team/two/',status:'new',title:null}],expected:'check-1'};
  const mixed={status:'choose-site',author:'Avery Quinn',problem:'These links come from 2 sites.',sites:[{site:'blog.example',shown:'blog.example/team/',links:2},{site:'other.example',shown:'other.example/blog/',links:1}]};
  const result=kept=>({operation:'x',author:'Avery Quinn',links:2,remaining:0,shown_scope:'blog.example/team/',counts:{imported:1,'in-library':1,failed:0,pending:0,mismatch:kept?0:1,no_text:0,samples:kept?2:1},samples:kept?['s1','s2']:['s1'],results:[{url:'https://blog.example/team/one/',status:'in-library',id:'s1',title:'One',byline:['Avery Quinn'],sample:true},{url:'https://blog.example/team/two/',status:'imported',id:'s2',title:'Two',byline:['Jordan Lee'],mismatch:true,sample:kept,kept}],sharing_message:'Saved in this workspace; no Team Hub selected.',next_step:'Next, learn or update the voice from these samples.'});
  let imports=0;
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url.startsWith('/api/voices'))return {profiles:[],samples:[{id:'s1',name:'One',author:'Avery Quinn'},{id:'s2',name:'Two',author:'Avery Quinn'}]};
    if(url==='/api/voice-links-preview')return data.site?preview:mixed;
    if(url==='/api/voice-links-import'){imports++;return imports===1?{...result(false),remaining:1,counts:{...result(false).counts,pending:1}}:result(data.keep.length>0);}
    return {items:[],total:0};});
  f.loadRunner();
  const sheet=()=>descendants(f.get('sheet')),find=label=>sheet().find(e=>e.textContent===label),byId=id=>sheet().find(e=>e.id===id),has=pattern=>sheet().some(e=>pattern.test(e.textContent));
  await f.run('sVoiceTools()');
  await find('Add published posts from a list of links').listeners.click();
  const input=byId('voice-links-file');assert.equal(input.accept,'.txt,text/plain');
  input.files=[{name:'avery-quinn-blog-links.txt',size:200,text:async()=>links+'https://other.example/blog/three/\n'}];
  await input.listeners.change();
  assert.equal(byId('voice-links-author').value,'Avery Quinn','the file name suggests the author');
  assert.match(byId('voice-links-text').value,/other\.example/);assert.ok(has(/Read avery-quinn-blog-links\.txt/));
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.ok(find('Choose one site'),'mixed sites ask which one to use');
  await find('Use blog.example/team/ (2 links)').listeners.click();
  assert.equal(requests.filter(r=>r.url==='/api/voice-links-preview').at(-1).data.site,'blog.example');
  assert.ok(find('2 posts from blog.example/team/'));assert.ok(has(/^By Avery Quinn$/));
  assert.ok(has(/1 already in your reference library: reused, not fetched again/));
  assert.ok(has(/1 new page is fetched once from blog\.example\/team\//));assert.ok(has(/1 links from other sites are left out/));
  assert.equal(requests.some(r=>r.url==='/api/voice-links-import'),false,'checking imports nothing');
  await find('Import 2 posts').listeners.click();
  const sent=requests.filter(r=>r.url==='/api/voice-links-import');
  assert.equal(sent.length,2,'the import continues until every link is read');
  assert.equal(sent[0].data.operation,sent[1].data.operation);assert.equal(sent[0].data.expected,'check-1');assert.equal(sent[0].data.author,'Avery Quinn');
  assert.ok(find('1 of 2 posts are Avery Quinn’s voice samples'));
  assert.ok(has(/Already in your library · voice sample · byline Avery Quinn/));
  assert.ok(has(/Imported · byline names Jordan Lee, so it is left out/));
  const keep=sheet().find(e=>e.tagName==='input'&&e.type==='checkbox');keep.checked=true;keep.listeners.change();
  await find('Keep the ticked posts as samples').listeners.click();
  const last=requests.filter(r=>r.url==='/api/voice-links-import').at(-1).data;
  assert.deepEqual(last.keep,['https://blog.example/team/two/']);assert.equal(last.operation,sent[0].data.operation);assert.equal(last.retry,false);
  assert.ok(has(/kept as a sample/));assert.ok(has(/Voice learning reads up to ten samples/));
  await find('Learn Avery Quinn’s voice').listeners.click();
  assert.equal(byId('learn-voice-name').value,'Avery Quinn');
  assert.deepEqual(JSON.parse(f.run('JSON.stringify(studio.voiceLearning.new.samples)')),['s1','s2']);
  assert.equal(sheet().filter(e=>e.tagName==='input'&&e.type==='checkbox'&&e.checked).length,2,'the imported samples are ticked for learning');
}
