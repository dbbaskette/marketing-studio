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
  replaceWith(node){if(!this.parent)return;const at=this.parent.children.indexOf(this);this.parent.children[at]=node;node.parent=this.parent;this.parent=null;}
  contains(node){return node===this||descendants(this).includes(node);}
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
// The older voice tools are switched off by default; a journey of them turns them on.
function voicesOn(f){f.run('sVoicesOn=()=>true');}
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
  return {get,nodes,run:code=>vm.runInContext(code,context),set:(name,value)=>{context[name]=value;},loadRunner:()=>{vm.runInContext(fs.readFileSync('skills/blog-studio/assets/management/markdown.js','utf8'),context);vm.runInContext(fs.readFileSync('skills/blog-studio/assets/management/runner.js','utf8').split('// Keep initialization below this marker')[0],context);vm.runInContext(fs.readFileSync('skills/blog-studio/assets/management/desk.js','utf8'),context);}};
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
  await phase4Starts();
  await phase4GoogleHandoff();
  await phase4ApplyReview();
  await phase4ReviewAside();
  await phase4FileKeep();
  await revisionCompletion();
  await deliveryRecovery();
  await brandInputs();
  await contextualTools();
  await sharedSettings();
  await interviewVoice();
  await staleSharedForms();
  await sharedPattern();
  await whereThisRunStops();
  await phase3ResearchDefaults();
  await researchFromJourney();
  await phase3ResearchAccount();
  await phase5BringResearchUpToDate();
  await phase3ClaimsMap();
  await oneVocabulary();
  await honestBlogCopy();
  await finishAndDelete();
  await filesJourney();
  await voiceLinksJourney();
  await libraryAddJourney();
  await libraryScreen();
  await librarySelectAll();
  await voicesForEveryAuthor();
  await voicesBatchLimit();
  await authorClarify();
  await createVoiceSources();
  await movedControls();
  await libraryPicker();
  await wizardVoiceAndKind();
  await voicesAndStyles();
  await voiceCandidates();
  await runVoiceChange();
  await toolsAreNamed();
  await voiceSwitch();
  await voiceGuides();
  await researchRefusal();
  await researchRounds();
  await skipResearch();
  await finishEveryLevel();
  await failureRecovery();
  await deskJourneys();
  await deskOpenFinished();
  await deskLeaveShares();
  await deskReturnAndGoogle();
  await deskTopicStart();
  await deskOutlineStarts();
  await deskOtherWaysIn();
  await deskProgress();
  await deskOutlineTab();
  await deskAddSource();
  await deskFinishing();
  pageDefinesEveryElement();
  const checks=['Apply a voice in Finishing: a voice guide chosen, retired ones left out, each part before and after, Apply all leaving a part that changes a fact, code or its shape, and Skip','voice guides: the sidebar screen, a guide written by hand, one made from samples then read and edited, one being made discarded, and a saved one edited or retired','the voice switch: off by default, no Write as, Default voice, Change the voice, voice learning, Create voices for every author or voice-sample choices; kinds of post on their own screen with Back; on, each returns','Finishing on the desk: every tool listed, Humanize previewed before and after with Apply, Edit, Skip and Apply all (a flagged change left), Proofread with Fix, facts with Add a source and Keep it, facts never applied all at once, headline alternatives, feedback in place and added to a typed note, the pre-publish check, a repurposed copy as a new blog, the Google Doc send, a full-screen sheet on a phone, a sheet opened from the panel on top on a phone and a tablet, a redraw on turning the screen, and no redraw under a focused control','an interview’s outline and a saved blog’s details opening the desk start, a saved draft brought as it is','desk starts: a kind of post, a topic with three editable angles, an outline written from or shaped first, sources and research ticks, the progress screen with its clock, Stop and Retry, the draft opening on its own, an overrun said as such, the Outline tab reordering, writing a section and the draft, bringing back a removed section, and Add a source with a file, a library post and a link, kept with the blog unless ticked','the writing desk: a pasted draft started, typing saved with its revision and session, a section note rewritten while its card works, a selection shortened, History compared and restored, a stale save, a whole-draft note, and a finished run opened on the desk','keep or not, file by file','review aside open by default and folded per blog','Apply the review’s findings, confirmed, three jobs','Open as a Google Doc, confirmed, private, once','starts on Home: a topic, an outline or notes, a draft, and the Done card’s Pre-publish and Repurpose','feedback','access and memory kinds','request ownership','curation conflicts','article/finding disclosures',
    'historical import preview/batching and source controls','diff-only saves and explicit ready/published confirmation',
    'analysis disclosure and per-operation choice','unreadable-blog notes','badge class whitelist','busy state',
    'refresh with a new selection','guided run decisions and handoff controls','Google manuscript preview, confirmation and reopening','review selection, preserved wording, late reads and in-flight saves','manual feedback and comments-only completion','brand skill inputs and confirmation','shared settings refusal/reload/retry, with the default voice','Interview me writes as a chosen voice','stops, now line, honest retry, note and phone toolbar','where this run stops, on the form and in Settings','one name for each thing','copy that says what the form and gates do','finish, done card, typed-title delete, restore and idea picks','new blog from my files: one screen, per-file text and roles, kept in the team library by default, the point path, Write as, angle picks, none of these and check detail lines','voice samples from a list of links: suggested author, scope check, one site, batches, byline keep and learning','add to the library: files, links and a Doc checked then added, each post’s own author grouped, renamed, merged and completed, marked as samples and learned from with the usual confirmation','the library screen: role, kind and author filters, a selection, and its three actions','select all on the page and every match through the server, kept across filters','create voices for every author: two readable posts, one confirmation, updates not duplicates, each job reviewed, who was not queued, and a batch of at most the server’s limit','create a voice: links, uploads, a LinkedIn export and library posts in one samples list','moved controls: each view’s one primary action, Refresh Hub, Import, Upload and More filters','a name that might be one person: suggested, confirmed as the same person or kept apart, and an author edited in Review details','from the library on the files card, with a learned style’s samples pre-ticked','Write as and Kind of post on the first step, for new blogs and manuscripts','voices and styles sheet, style learning and the LinkedIn export','sample candidates and pending sources','a run’s voice and kind of post, with a confirmed change','Tools and Voices and styles in plain sight','a refused research case listed by kind and verdict, kept on this computer','research rounds under way, what the last attempt took and what Try again does','Continue without research, confirmed, and the run’s stops line','Finish confirmed at every review level, naming the team library','failures that say what to do: Status and what the assistant said, where the time limit lives, setup that shows an assistant is missing','research from your documents, your sites and/or the public web: the shared list prefilled, a site for one blog checked by the server, the shared sentences, and the sites named at the research gate','element ids'];
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

async function phase4FileKeep(){
  const calls=[],f=fixture((route,options)=>{const data=options?.body?JSON.parse(options.body):null;calls.push({route,data});return {id:data.id,kept:data.keep};});f.loadRunner();
  f.run("studio.screen='new';studio.options={settings:{defaults:{}},sources:[],styles:[],profiles:[]};studio.draft={mode:'from-files',files:[{id:'one',filename:'one.md',state:'ready',chars:10,kept:false,role:'material'},{id:'two',filename:'two.md',state:'ready',chars:10,kept:true,role:'material'}],keep:false,role:'material'}");
  f.run("sPage(sFilesCard(studio.draft,sNode('p'),()=>sPage(sFilesCard(studio.draft,sNode('p'),()=>{},()=>{})),()=>{}))");
  const rows=()=>descendants(f.get('studio-page')).filter(n=>n.tagName==='li'&&n.className.includes('row'));
  await descendants(rows()[0]).find(n=>n.textContent==='Keep in the team library').listeners.click();
  assert.equal(f.run('studio.draft.files[0].kept'),true);assert.equal(f.run('studio.draft.files[1].kept'),true);assert.equal(f.run('studio.draft.keep'),false);
  await descendants(rows()[1]).find(n=>n.textContent==='Keep it to this blog').listeners.click();
  assert.equal(f.run('studio.draft.files[1].kept'),false);
  assert.deepEqual(calls.map(r=>r.data),[{id:'one',keep:true},{id:'two',keep:false}]);
}

async function phase4ReviewAside(){
  const f=fixture();f.loadRunner();
  const found={id:'aside',title:'A draft',mode:'write',next:'draft',approval:'page',expected:'v1',complete:false,stages:[{stage:'draft',label:'Draft',status:'draft'}]};
  const shown={stage:'draft',label:'Draft',status:'draft',expected:'v1',content:'# Draft',notes:'A real note.',checks:[{label:'2 em dashes',passed:false,detail:['line 3: —']}],previous:null};
  f.set('found',found);f.set('shown',shown);f.run('sGate(found,shown)');
  const aside=()=>descendants(f.get('studio-page')).find(n=>n.tagName==='details'&&n.children.some(c=>c.textContent==='Review notes and checks'));
  assert.equal(aside().open,true);aside().open=false;aside().listeners.toggle();
  f.run('sGate(found,shown)');assert.equal(aside().open,false);
  f.run("sGate({...found,id:'other'},shown)");assert.equal(aside().open,true);
}

async function phase4ApplyReview(){
  const calls=[],found={id:'apply',title:'Review draft',mode:'write',status:'waiting-for-approval',next:'package',approval:'page',expected:'v1',enabled:true,complete:false,engine:'codex',seconds:600,directory:'/synthetic/articles/apply',decisions:[],brief:{goal:'Explain',audience:'Authors'},stages:[{stage:'draft',label:'Draft',status:'approved'},{stage:'review',label:'Review',status:'approved'},{stage:'package',label:'Handoff',status:'draft'}],redo:{draft:{stages:['draft','review','package'],says:'This computer has no record of what they cost.'}}};
  const shown={stage:'package',label:'Handoff',expected:'v1',status:'draft',content:'# Handoff',checks:[],notes:'',previous:null,bundle:[]};
  const updated={...found,status:'queued',next:'draft'};
  const f=fixture((route,options)=>{calls.push({route,data:options?.body?JSON.parse(options.body):null});return updated;});f.loadRunner();f.set('found',found);f.set('shown',shown);f.run("studio.screen='gate';studio.id=found.id;sGate(found,shown)");
  await descendants(f.get('actions')).find(n=>n.textContent==="Apply the review's findings").listeners.click();
  const sheet=()=>descendants(f.get('sheet'));
  assert.ok(sheet().some(n=>/three jobs/.test(n.textContent)));assert.ok(sheet().some(n=>/no record of what they cost/.test(n.textContent)));assert.equal(calls.length,0);
  await sheet().find(n=>n.textContent==='Apply them').listeners.click();
  const sent=calls.find(r=>r.route==='/api/run-apply-review');assert.equal(sent.data.id,'apply');assert.equal(sent.data.expected,'v1');
}

async function phase4GoogleHandoff(){
  const requests=[],url='https://docs.google.com/document/d/fixture-doc/edit';
  const found={id:'finished',title:'Finished draft',status:'complete',complete:true,approval:'page',expected:'v1',enabled:true,decisions:[],directory:'/synthetic/articles/finished',mode:'write',stages:[{stage:'draft',label:'Draft',path:'DRAFT.md',status:'approved'}],brief:{goal:'Explain',audience:'Authors'},engine:'codex',seconds:600};
  const f=fixture((route,options)=>{requests.push({route,data:options?.body?JSON.parse(options.body):null});return route==='/api/google-open'?{id:'finished',url,transfer:'one'}:{items:[]};});f.loadRunner();f.set('done',found);f.run("studio.screen='run';studio.id=done.id;sPage(sDoneCard(done))");
  const nodes=()=>descendants(f.get('studio-page')),sheet=()=>descendants(f.get('sheet'));
  await nodes().find(n=>n.textContent==='Open as a Google Doc').listeners.click();
  assert.ok(sheet().some(n=>/private to you. Nothing is shared/.test(n.textContent)));
  assert.equal(requests.length,0);
  await sheet().find(n=>n.textContent==='Cancel').listeners.click();
  assert.equal(requests.length,0);
  await nodes().find(n=>n.textContent==='Open as a Google Doc').listeners.click();
  await sheet().find(n=>n.textContent==='Make the Google Doc').listeners.click();
  assert.equal(requests.filter(r=>r.route==='/api/google-open').length,1);
  assert.equal(requests[0].data.id,'finished');assert.equal(requests[0].data.expected,'v1');assert.equal(requests[0].data.confirmed,true);
  assert.ok(nodes().some(n=>n.textContent==='Open the Google Doc ↗'&&n.href===url));
  assert.equal(nodes().some(n=>n.textContent==='Open as a Google Doc'),false);
  const pending={...found,google:null,google_pending:{url}};
  let attempts=0;
  const retry=fixture((route)=>route==='/api/google-open'?(++attempts===1?{__http:409,error:'The readback needs reconciliation.'}:{id:found.id,url,transfer:'one'}):pending);
  retry.loadRunner();retry.set('done',{...found,google:null});retry.run("studio.screen='run';studio.id=done.id;sPage(sDoneCard(done))");
  const retryNodes=()=>descendants(retry.get('studio-page')),retrySheet=()=>descendants(retry.get('sheet'));
  await retryNodes().find(n=>n.textContent==='Open as a Google Doc').listeners.click();
  await retrySheet().find(n=>n.textContent==='Make the Google Doc').listeners.click();
  assert.ok(retrySheet().some(n=>n.href===url));
  assert.ok(retrySheet().some(n=>n.textContent==='Check the existing Google Doc'));
  await retrySheet().find(n=>n.textContent==='Check the existing Google Doc').listeners.click();
  assert.equal(attempts,2);
  assert.ok(retryNodes().some(n=>n.textContent==='Open the Google Doc ↗'&&n.href===url));
}

async function phase4Starts(){
  const requests=[];
  const made={id:'manuscript-run',title:'A draft',status:'queued',next:'review',approval:'page',expected:'v1',enabled:true,seconds:600,engine:'codex',decisions:[],brief:{goal:'Check it',audience:'Authors'},stages:[]};
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});if(url==='/api/run-options')return {settings:{defaults:{engine:'codex',seconds:600,research:'supplied-only',stop:'package',tone:'',author:''}},sources:[],profiles:[],styles:[],agents:{codex:true}};if(url==='/api/upload')return {source:{id:'manuscript-source'},state:'ready'};if(url==='/api/run-create'||url.startsWith('/api/run?'))return made;return {items:[]};});
  f.loadRunner();f.run('sHome()');
  const nodes=()=>descendants(f.get('studio-page'));
  for(const title of ['Write about a topic','Work from my outline or notes','Edit or polish a draft'])assert.ok(nodes().some(n=>n.textContent===title));
  for(const title of ['Outline only','Revise or review a draft','New blog from my files'])assert.ok(!nodes().some(n=>n.textContent===title),title+' is no longer a way to start');
  // A draft the person brings opens on the writing desk; the step-by-step revise start stays
  // for blogs already on it.
  await nodes().find(n=>n.textContent==='Edit or polish a draft').listeners.click();
  assert.equal(f.run('studio.screen'),'desk-start');assert.equal(f.run('studio.deskStart.have'),'draft');
  await f.run("newBlog('',null,'revise')");
  assert.ok(nodes().some(n=>n.attributes['aria-label']==='Upload a manuscript'),nodes().map(n=>n.textContent).join(' | '));
  await nodes().find(n=>n.textContent==='Give feedback only').listeners.click();
  assert.equal(f.run('studio.draft.mode'),'review');
  await nodes().find(n=>n.textContent==='Improve it').listeners.click();
  assert.equal(f.run('studio.draft.mode'),'revise');
  await nodes().find(n=>n.textContent==='Give feedback only').listeners.click();
  const file=nodes().find(n=>n.attributes['aria-label']==='Upload a manuscript');
  file.files=[{name:'draft.md',size:10,arrayBuffer:async()=>new TextEncoder().encode('My draft.').buffer}];
  await file.listeners.change();
  for(const [id,value] of [['new-title','A draft'],['new-goal','Check it'],['new-audience','Authors']]){const field=nodes().find(n=>n.id===id);field.value=value;field.listeners.input();}
  await nodes().find(n=>n.tagName==='form').listeners.submit({preventDefault(){}});
  await nodes().find(n=>n.tagName==='form').listeners.submit({preventDefault(){}});
  const payload=requests.find(r=>r.url==='/api/run-create').data;
  assert.equal(payload.mode,'review');assert.equal(payload.manuscript,'manuscript-source');assert.equal(payload.stop,'review');
  const uploaded=requests.find(r=>r.url==='/api/upload').data;assert.equal(uploaded.purpose,'manuscript');assert.equal(uploaded.analyze,false);
  assert.equal(Buffer.from(uploaded.content,'base64').toString(),'My draft.');
  f.set('done',{id:'done',stages:[{stage:'draft'}],complete:true});
  f.run("sPage(sDoneCard(done))");
  for(const title of ['Pre-publish check','Repurpose'])assert.equal(nodes().find(n=>n.textContent===title).disabled,false);
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
  for(const label of ['Write about a topic','Work from my outline or notes','Edit or polish a draft'])assert.ok(nodes().some(e=>e.textContent===label));
  // Setting up voices, styles and the library is on Home, without starting a blog.
  assert.ok(nodes().some(e=>e.textContent==='Set up before you write'),'Home offers setting up before writing');
  for(const label of ['Kinds of post','Team library'])assert.ok(nodes().some(e=>e.className==='pick-card'&&descendants(e).some(d=>d.textContent===label)||e.textContent===label),label);
  await nodes().find(e=>e.textContent==='Edit or polish a draft').listeners.click();
  assert.equal(f.run('studio.screen'),'desk-start');
  await f.run("sRoute('polish')");
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
  assert.equal(creation.mode,'from-outline');assert.equal(creation.outline_text,'# First\n## Second');assert.equal(creation.research,undefined);assert.deepEqual(creation.research_from,{documents:true,sites:[],web:true},'an older default reads as your documents and the public web');
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
  // Each view's primary action sits in the toolbar and follows the access.
  assert.equal(f.get('actions').children.find(e=>e.textContent==='New blog').disabled,true,'New blog follows edit access');
  f.run("view='memory';legacyToolbar()");assert.equal(f.get('actions').children.find(e=>e.textContent==='Add memory').disabled,true);
  f.run("view='library';legacyToolbar()");assert.deepEqual(f.get('actions').children.map(e=>[e.textContent,e.disabled]),[['Add to library',true]]);
  assert.deepEqual(f.get('view-actions').children.map(e=>[e.textContent,e.disabled]),[],'Create voices for every author waits behind the voice switch');
  f.run('globalThis.sVoicesOn=()=>true');f.run("legacyToolbar()");
  assert.deepEqual(f.get('view-actions').children.map(e=>[e.textContent,e.disabled]),[['Create voices for every author',true]],'a secondary action sits under the lede');
  f.run('delete globalThis.sVoicesOn');
  f.run("view='board'");
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
    // A library row is a card on a phone: its title and action go unlabelled, the rest say what they are.
    if(name==='library'){assert.equal(cells.length,5);assert.deepEqual(cells.map(e=>e.attributes['data-label']),['','Author','Role','Status','']);}
    else {assert.equal(cells.length,4);assert.ok(cells.every(e=>e.attributes['data-label']));}
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
  const voices=[{id:'mine',name:'Synthetic Author',revision:3},{id:'guest',name:'Guest Writer',revision:1}];
  const f=fixture((url,options)=>{if(options?.method==='POST'){requests.push({url,data:JSON.parse(options.body)});return {defaults,shared_before:before,workspace:'/synthetic',features:{voice:true},voice:null,voices};}if(url==='/api/run-options')return {settings:{defaults},sources:[],profiles:[],agents:{}};if(url==='/api/team')return {};return empty();});
  f.loadRunner();f.set('defaults',defaults);f.set('before',before);f.set('voices',voices);f.run("studio.settings={defaults,shared_before:before,workspace:'/synthetic',features:{voice:true},voice:{profile_id:'mine',revision:3},voices};studio.screen='settings';sSettings()");
  assert.equal(descendants(f.get('studio-page')).filter(e=>e.type==='checkbox'&&!e.id.startsWith('settings-research-')&&e.id!=='settings-voice-tools').length,0,'shared saves have no second consent toggle');
  // The research default: three ticks, an older 'none' read as none of them.
  const tick=key=>descendants(f.get('studio-page')).find(e=>e.id==='settings-research-'+key);
  assert.deepEqual(['documents','sites','web'].map(key=>tick(key).checked),[false,false,false]);
  assert.ok(descendants(f.get('studio-page')).some(e=>e.textContent==='Research for new blogs from:'));
  tick('sites').checked=true;tick('sites').listeners.change();
  // The default voice: None or a confirmed voice; saved as its exact pin, or null for none.
  const voice=descendants(f.get('studio-page')).find(e=>e.id==='settings-voice');
  assert.deepEqual(voice.children.map(o=>[o.value,o.textContent]),[['','None'],['mine','Synthetic Author'],['guest','Guest Writer']]);
  assert.equal(voice.value,'mine','the saved default is chosen');
  const input=descendants(f.get('studio-page')).find(e=>e.id==='settings-author');input.value='New Author';input.listeners.input();
  await f.get('studio-page').children.find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(requests[0].url,'/api/run-settings');assert.equal(requests[0].data.author,'New Author');
  assert.deepEqual(requests[0].data.shared_before,before);assert.equal('for_all_studios' in requests[0].data,false);
  assert.deepEqual(requests[0].data.voice,{profile_id:'mine',revision:3},'the default voice is saved with its revision');
  assert.deepEqual(requests[0].data.voice_before,{profile_id:'mine',revision:3},'against the voice the form showed');
  assert.deepEqual([requests[0].data.features,requests[0].data.features_before],[{voice:true},{voice:true}],'the voice switch is saved against what the form showed');
  assert.deepEqual(requests[0].data.research,{documents:false,sites:true,web:false},'the research default is saved as three ticks');assert.equal(defaults.research,'none','the shown defaults are not changed by the form');
  f.run("studio.settings={defaults,shared_before:before,workspace:'/synthetic',features:{voice:true},voice:null,voices};sSettings()");
  const none=descendants(f.get('studio-page')).find(e=>e.id==='settings-voice');assert.equal(none.value,'','no default: None');
  none.value='guest';none.listeners.change();
  await f.get('studio-page').children.find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.deepEqual(requests.at(-1).data.voice,{profile_id:'guest',revision:1});
  f.run("studio.settings={defaults,shared_before:before,workspace:'/synthetic',features:{voice:true},voice:{profile_id:'guest',revision:1},voices};sSettings()");
  const back=descendants(f.get('studio-page')).find(e=>e.id==='settings-voice');back.value='';back.listeners.change();
  await f.get('studio-page').children.find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(requests.at(-1).data.voice,null,'None removes the default');
}

// Interview me takes Write as, like a new blog: My voice sends the default's exact pin, a
// chosen voice its profile, no particular voice an empty one.
async function interviewVoice(){
  const requests=[],mine={scope:'personal',profile:'mine',name:'Synthetic Author',revision:2,status:'confirmed'};
  const f=fixture((url,o)=>{const data=o?.body?JSON.parse(o.body):null;requests.push({url,data});
    if(url==='/api/run-options')return {settings:{defaults:{engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''}},sources:[],agents:{codex:true},default_voice:mine,profiles:[{id:'mine',name:'Synthetic Author',status:'confirmed'},{id:'guest',name:'Guest Writer',status:'provisional'}],styles:[]};
    if(url==='/api/tool-action'&&data.action==='interview-start')return {id:'interviewed',title:data.title,answers:[],notes:'',question:'What is the main point?',expected:'i1',outline:false,outline_content:''};
    if(url.startsWith('/api/interview?'))return {id:'interviewed',title:'Synthetic interview',answers:[],notes:'',question:'What is the main point?',expected:'i1',outline:false,outline_content:''};
    return {items:[],total:0};});
  f.loadRunner();voicesOn(f);
  const sheet=()=>descendants(f.get('sheet')),byId=id=>sheet().find(e=>e.id===id);
  const fill=()=>{for(const [id,value] of [['interview-title','Synthetic interview'],['interview-audience','Developers'],['interview-goal','Explain a gateway']]){byId(id).value=value;byId(id).listeners.input();}};
  await f.run('sNewInterview()');
  assert.equal(sheet().find(e=>e.tagName==='label'&&e.htmlFor==='interview-voice').textContent,'Write as','the interview asks whose voice');
  assert.deepEqual(byId('interview-voice').children.map(o=>o.textContent),['My voice — Synthetic Author · confirmed','Guest Writer · provisional','No particular voice (use the described tone)','Learn a new voice…']);
  fill();await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  let sent=requests.filter(r=>r.url==='/api/tool-action').at(-1).data;
  assert.equal(sent.action,'interview-start');assert.equal(sent.title,'Synthetic interview');assert.equal(sent.profile,'mine');assert.equal(sent.revision,2,'My voice sends the default’s exact pin');
  f.run('studio.interviewDraft=null');await f.run('sNewInterview()');fill();byId('interview-voice').value='guest';byId('interview-voice').listeners.change();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  sent=requests.filter(r=>r.url==='/api/tool-action').at(-1).data;assert.equal(sent.profile,'guest');assert.equal('revision' in sent,false);
  f.run('studio.interviewDraft=null');await f.run('sNewInterview()');fill();byId('interview-voice').value='';byId('interview-voice').listeners.change();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  sent=requests.filter(r=>r.url==='/api/tool-action').at(-1).data;assert.equal(sent.profile,'','no particular voice sends an empty one');
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

// Select all: the heading's box ticks the rows on this page; the bar, shown only while
// something is ticked, offers the rest of the page and every item the filters match, through
// the server; ticks stay as the filters change; a blog takes at most fifty.
async function librarySelectAll(){
  const requests=[];const row=n=>({id:'p'+n,title:'Post '+n,author:n%2?'Avery':'Sam',status:'ready',revision:1,purposes:['reference','inspiration'],role:'example',kind_name:null,library:{},analysis:{},historical:false,collection_names:[]});
  const page=Array.from({length:20},(_,n)=>row(n));
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url.startsWith('/api/library?'))return {items:page,total:61,kinds:[]};
    if(url.startsWith('/api/library-matching?'))return {items:Array.from({length:61},(_,n)=>({id:'p'+n,location:n===60?'hub':'local',title:'Post '+n})),total:61,capped:false};
    if(url==='/api/library-selection')return {action:data.action,candidates:[{id:'p0',name:'Post 0',author:'Sam'}],author:null,left_out:[],skipped:[]};
    if(url.startsWith('/api/styles'))return {styles:[],samples:[],candidates:[],pending:[]};
    return {items:[],total:0};});
  f.loadRunner();await f.run("sLegacy('library')");
  const bar=f.get('library-selection'),box=f.get('library-select-page-box');
  assert.equal(bar.hidden,true,'the bar shows only once something is ticked');assert.equal(f.get('library-select-page').hidden,false,'the page’s own select all is always there');
  box.checked=true;f.run("tickLibrary(libraryShown,true)");
  assert.equal(bar.hidden,false);assert.equal(f.get('library-selection-count').textContent,'20 selected');
  assert.equal(f.get('library-select-shown').hidden,true,'every row on the page is ticked');
  assert.equal(descendants(f.get('results')).filter(e=>e.type==='checkbox'&&e.checked).length,20,'the rows show their ticks');
  assert.equal(f.get('library-select-matching').hidden,false);assert.equal(f.get('library-select-matching').textContent,'Select all 61 matching');
  const pick=descendants(f.get('results')).find(e=>e.type==='checkbox');pick.checked=false;pick.listeners.change();
  assert.equal(f.get('library-select-shown').hidden,false);assert.equal(f.get('library-select-shown').textContent,'Select all 20 on this page');
  assert.equal(box.indeterminate,true,'some on this page');
  f.get('library-author').value='Avery';f.get('query').value='launch';f.get('library-role').value='example';await f.run('load()');
  await f.run("selectAllMatching(document.getElementById('library-select-matching'))");
  const asked=requests.filter(r=>r.url.startsWith('/api/library-matching?')).at(-1).url;
  assert.match(asked,/author=Avery/);assert.match(asked,/query=launch/);assert.match(asked,/role=example/);assert.doesNotMatch(asked,/offset|limit/,'every match, not a page');
  assert.equal(f.get('library-selection-count').textContent,'61 selected');assert.equal(f.get('library-select-matching').hidden,true);
  assert.equal(f.get('library-selection-hidden').textContent,'41 of them are not in this view.','the bar says what the filters hide');
  f.get('library-author').value='';await f.run('load()');assert.equal(f.get('library-selection-count').textContent,'61 selected','changing the filters keeps the ticks');
  // Under other filters the matches are not all ticked, however large the selection: the button offers them.
  assert.equal(f.get('library-select-matching').hidden,false,'other filters offer their own matches');
  f.get('library-author').value='Avery';await f.run('load()');assert.equal(f.get('library-select-matching').hidden,true,'back under the same filters, all of them are ticked');
  f.run("librarySelection.delete('local:p59');librarySelectionBar()");assert.equal(f.get('library-select-matching').hidden,false,'untick one match and the button is back');
  f.run("tickLibrary([{id:'p59'}],true)");
  await assert.rejects(f.run("sLibrarySelection('blog',[...librarySelection.values()])"),/up to 50 examples, and 61 are ticked/);
  assert.equal(requests.some(r=>r.url==='/api/library-selection'),false,'nothing is sent for too many examples');
  await f.run("sLibrarySelection('style-learn',[...librarySelection.values()])");
  const sent=requests.find(r=>r.url==='/api/library-selection').data;assert.equal(sent.ids.length,61,'learning takes the whole selection; the server reads twenty');
  assert.deepEqual(sent.ids.filter(e=>typeof e==='object'),[{id:'p60',location:'hub'}],'a Team Hub item keeps its location');
  // A selection holds at most 500: another Select all matching that would pass it is stopped on the page.
  f.run("for(let n=0;n<460;n++)librarySelection.set('local:x'+n,'x'+n);libraryMatched=null;librarySelectionBar()");
  f.get('library-author').value='';await f.run('load()');
  const before=requests.filter(r=>r.url.startsWith('/api/library-matching?')).length;
  await f.run("selectAllMatching(document.getElementById('library-select-matching'))");
  assert.equal(requests.filter(r=>r.url.startsWith('/api/library-matching?')).length,before+1);
  assert.equal(f.run('librarySelection.size'),521,'nothing is added');
  assert.match(f.get('notice').textContent,/at most 500/);
  await assert.rejects(f.run("sLibrarySelection('style-learn',[...librarySelection.values()])"),/at most 500 items, and 521 are ticked/);
  f.run("librarySelection.clear();librarySelectionBar()");assert.equal(bar.hidden,true);
}

// Create voices for every author: authors with two readable posts are ticked, others listed
// with the reason; one confirmation queues the batch; the sheet follows each job, and saving a
// reviewed voice comes back to it.
async function voicesForEveryAuthor(){
  const requests=[];let status='queued';
  const authors={authors:[{author:'Avery Quinn',posts:8,readable:8,samples:[],profile:null,ready:true,reason:''},{author:'Sam Rivera',posts:3,readable:3,samples:[],profile:{id:'sam',name:'Sam Rivera',status:'confirmed',revision:2},ready:true,reason:''},{author:'Jordan Lee',posts:1,readable:1,samples:[],profile:null,ready:false,reason:'Only 1 readable post; a voice needs at least 2.'}],unnamed:2,minimum:2};
  const job=(id,author)=>({id,kind:'voice-learn',status,metadata:{name:author,samples:['a','b']},attempts:0,result:status==='ready'?{content:'# '+author,notes:''}:null,applied:null});
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url==='/api/library-authors')return authors;
    if(url==='/api/library-voices')return {operation:data.operation,jobs:[{author:'Avery Quinn',update:false,profile:null,samples:8,job:job('a'.repeat(32),'Avery Quinn')},{author:'Sam Rivera',update:true,profile:authors.authors[1].profile,samples:3,job:job('b'.repeat(32),'Sam Rivera')}]};
    if(url.startsWith('/api/tool-job?job='))return job(url.slice(-32),url.endsWith('a'.repeat(32))?'Avery Quinn':'Sam Rivera');
    if(url==='/api/tool-action')return {profile:'avery',revision:1,status:'provisional'};
    if(url.startsWith('/api/voices'))return {profiles:[],samples:[],candidates:[],pending:[]};
    return {items:[],total:0};});
  f.loadRunner();voicesOn(f);
  const sheet=()=>descendants(f.get('sheet')),text=()=>sheet().map(e=>e.textContent),find=label=>sheet().find(e=>e.textContent===label),byId=id=>sheet().find(e=>e.id===id);
  await f.run("sLegacy('library')");
  await f.get('view-actions').children.find(e=>e.textContent==='Create voices for every author').listeners.click();
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Create voices for every author');
  const ticks=sheet().filter(e=>e.type==='checkbox'&&e.id.startsWith('voices-author-'));
  assert.deepEqual(ticks.map(e=>[e.value,e.checked,e.disabled]),[['Avery Quinn',true,false],['Sam Rivera',true,false],['Jordan Lee',false,true]],'two readable posts make a voice');
  assert.ok(text().some(t=>/1 post · 1 readable · Only 1 readable post; a voice needs at least 2\./.test(t)),'the reason is shown');
  assert.ok(text().includes('Update Sam Rivera’s voice'),'an existing voice is updated, not duplicated');
  assert.ok(text().some(t=>/^2 posts have no author/.test(t)));
  const submit=sheet().find(e=>e.type==='submit');assert.equal(submit.textContent,'Create 1 voice and update 1');
  ticks[1].checked=false;ticks[1].listeners.change();assert.equal(submit.textContent,'Create 1 voice');ticks[1].checked=true;ticks[1].listeners.change();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(requests.some(r=>r.url==='/api/library-voices'),false,'nothing starts without the permission');assert.ok(text().some(t=>/Confirm you have permission/.test(t)));
  byId('voices-permission').checked=true;await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const sent=requests.filter(r=>r.url==='/api/library-voices');assert.equal(sent.length,1,'one confirmation for the batch');
  assert.deepEqual([sent[0].data.authors,sent[0].data.confirmed],[['Avery Quinn','Sam Rivera'],true]);assert.match(sent[0].data.operation,/^[0-9a-f]{32}$/);
  assert.ok(text().includes('Avery Quinn'));assert.ok(text().includes('Waiting to start · 8 posts'));assert.ok(text().includes('Update Sam Rivera’s voice'));
  // Ready jobs are reviewed one by one, and saving one comes back to the batch.
  status='ready';await f.run('sVoicesBatch()');
  assert.ok(text().includes('Ready for your review · 8 posts'));
  await find('Review Avery Quinn’s voice').listeners.click();
  assert.ok(find('Save provisional voice guide'));assert.ok(find('Back to every author'));
  await find('Save provisional voice guide').listeners.click();
  assert.equal(requests.filter(r=>r.url==='/api/tool-action').at(-1).data.action,'job-apply');
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Create voices for every author','saving returns to the batch');
  // An author not queued after the checks is named, beside who was.
  f.run("studio.voiceBatch={operation:'o',jobs:[studio.voiceBatch.jobs[0]],failed:[{author:'Sam Rivera',reason:'The disk is full.'}]}");await f.run('sVoicesBatch()');
  assert.ok(text().includes('Queued: Avery Quinn. Not queued:'),text().join('|'));assert.ok(text().includes('The disk is full.'));
  // Reopening the action shows the batch until another is started.
  f.run('sCloseSheet()');await f.run('sVoicesForAuthors()');assert.ok(find('Start another batch'));
  await find('Start another batch').listeners.click();assert.ok(sheet().some(e=>e.id==='voices-permission'),'a new batch asks again');
  // An author still queued from the earlier batch is not ticked again; it says Queued.
  status='queued';f.run("studio.voiceBatch=null;studio.voicesQueued={jobs:[{author:'Avery Quinn',samples:8,job:{id:'"+'a'.repeat(32)+"',status:'queued'}}]}");
  f.run('sCloseSheet()');await f.run('sVoicesForAuthors()');
  const again=sheet().filter(e=>e.type==='checkbox'&&e.id.startsWith('voices-author-'));
  assert.deepEqual(again.map(e=>[e.value,e.checked,e.disabled]),[['Avery Quinn',false,true],['Sam Rivera',true,false],['Jordan Lee',false,true]]);
  assert.ok(text().some(t=>/Queued: its voice is already being learned/.test(t)));
  assert.equal(sheet().find(e=>e.type==='submit').textContent,'Update 1 voice');
  status='ready';f.run('sCloseSheet()');await f.run('sVoicesForAuthors()');
  assert.equal(sheet().find(e=>e.value==='Avery Quinn').checked,true,'once its learning is ready, it can be ticked again');
}

// Create a voice: every source lands in the same samples list, ticked, for the named author.
// A batch names at most the server's limit: the page ticks that many and says why.
async function voicesBatchLimit(){
  const authors=Array.from({length:3},(_,n)=>({author:'Author '+n,posts:2,readable:2,samples:[],profile:null,ready:true,reason:''}));
  const f=fixture(url=>url==='/api/library-authors'?{authors,unnamed:0,minimum:2,batch_limit:2}:{items:[],total:0});f.loadRunner();
  await f.run('sVoicesForAuthors()');
  const sheet=()=>descendants(f.get('sheet'));
  assert.deepEqual(sheet().filter(e=>e.type==='checkbox'&&e.id.startsWith('voices-author-')).map(e=>e.checked),[true,true,false]);
  assert.ok(sheet().some(e=>/3 authors can have a voice; a batch takes 2, so the first 2 are ticked/.test(e.textContent)));
  const third=sheet().find(e=>e.id==='voices-author-2');third.checked=true;third.listeners.change();
  const submit=sheet().find(e=>e.type==='submit');assert.equal(submit.textContent,'Tick at most 2 authors');assert.equal(submit.disabled,true);
}

async function createVoiceSources(){
  const requests=[];const samples=[{id:'mine',name:'Old post',author:'Avery Quinn'},{id:'other',name:'Not theirs',author:'Sam Rivera'}];
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url.startsWith('/api/voices'))return {profiles:[],samples,candidates:[{id:'lib',name:'Library post',author:'Avery Quinn'},{id:'theirs',name:'Sam’s post',author:'Sam Rivera'}],pending:[]};
    if(url==='/api/upload'){if(data.files)return {files:[{filename:'LinkedIn · Article',source:{id:'li'},state:'ready',chars:9,note:'',purpose:'voice-sample',author:'Avery Quinn'}],receipts:[],state:'saved',next_step:'Every file has text.'};samples.push({id:'up-'+data.filename,name:data.filename,author:data.author});return {source:{id:'up-'+data.filename},state:'ready',chars:20,note:'',receipts:[]};}
    if(url==='/api/tool-action'){samples.push({id:data.source,name:'Library post',author:'Avery Quinn'});return {source:data.source,revision:2,purposes:['reference','voice-sample'],author:'Avery Quinn',changed:true,receipts:[]};}
    return {items:[],total:0};});
  f.loadRunner();voicesOn(f);
  const sheet=()=>descendants(f.get('sheet')),text=()=>sheet().map(e=>e.textContent),find=label=>sheet().find(e=>e.textContent===label),byId=id=>sheet().find(e=>e.id===id);
  const ticked=()=>sheet().filter(e=>e.type==='checkbox'&&e.checked&&e.value).map(e=>e.value);
  await f.run("sRoute('voices')");
  assert.equal(f.get('title').textContent,'Voices and styles');
  await f.get('actions').children.find(e=>e.textContent==='Create a voice').listeners.click();
  byId('learn-voice-name').value='Avery Quinn';byId('learn-voice-name').listeners.input();
  // Posts already in the library, narrowed to this author once the sheet is drawn again.
  await f.run("api('voices').then(found=>sLearnVoice(found))");
  assert.ok(text().includes('Library post'));assert.equal(text().includes('Sam’s post'),false,'another author’s post is not offered');
  assert.ok(text().some(t=>/1 post by another author is not shown/.test(t)));
  assert.equal(text().includes('Not theirs · Sam Rivera'),false,'nor is another author’s sample');
  await find('Use as a sample by Avery Quinn').listeners.click();
  assert.deepEqual(ticked(),['lib']);
  // Uploads: several at once, each this author’s sample.
  const upload=byId('learn-voice-upload');assert.equal(upload.multiple,true);
  upload.files=['one.md','two.md'].map(name=>({name,size:9,arrayBuffer:async()=>new TextEncoder().encode('# A post').buffer}));await upload.listeners.change();
  assert.deepEqual(requests.filter(r=>r.url==='/api/upload').map(r=>[r.data.filename,r.data.author,r.data.purpose]),[['one.md','Avery Quinn','voice-sample'],['two.md','Avery Quinn','voice-sample']]);
  assert.deepEqual(ticked(),['lib','up-one.md','up-two.md']);
  // A LinkedIn export comes back to the same sheet, its article ticked beside the rest.
  await find('Import a LinkedIn export').listeners.click();
  assert.equal(byId('linkedin-author').value,'Avery Quinn','the export is named for the voice being made');
  byId('linkedin-file').files=[{name:'export.zip',size:4,arrayBuffer:async()=>new Uint8Array([80,75,3,4]).buffer}];
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  samples.push({id:'li',name:'LinkedIn · Article',author:'Avery Quinn'});
  await find('Learn Avery Quinn’s voice from these articles').listeners.click();
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Create a voice');
  assert.deepEqual(ticked(),['lib','up-one.md','up-two.md','li'],'the export’s article joins what was already ticked');
  // Links to their posts open with the author named.
  f.run('sVoiceLinks=(found,profile)=>{window.linksAuthor=sVoiceLinksHeld(profile).author;}');
  await find('Add links to posts').listeners.click();assert.equal(f.run('window.linksAuthor'),'Avery Quinn');
}

// Every control that moved can still be reached.
async function movedControls(){
  const page=fs.readFileSync('skills/blog-studio/assets/management/index.html','utf8');
  const access=page.slice(page.indexOf('<section id="access-panel"'),page.indexOf('</section>',page.indexOf('<section id="access-panel"')));
  assert.match(access,/id="refresh-hub"/,'Refresh Hub sits with the Hub access line');
  const more=page.slice(page.indexOf('<details id="library-more-filters"'),page.indexOf('</details>'));
  assert.match(more,/id="library-collection"/,'Collection ID is under More filters');
  const head=page.slice(page.indexOf('<section id="editorial-screen"'),page.indexOf('<section id="access-panel"'));
  for(const gone of ['new-blog','upload-open','import-open','library-add-open','memory-open'])assert.doesNotMatch(page,new RegExp('id="'+gone+'"'),gone+' is no longer a page button');
  assert.doesNotMatch(head,/<button/,'the view header holds no buttons');
  const f=fixture(()=>({items:[],total:0,profiles:[],samples:[],candidates:[],pending:[],styles:[],authors:[],unnamed:0}));f.loadRunner();
  for(const [name,primary] of [['board','New blog'],['library','Add to library'],['memory','Add memory'],['inbox',null]]){
    f.run("access.actions.memory=true");await f.run("sLegacy('"+name+"')");
    const actions=f.get('actions').children.map(e=>[e.textContent,e.className]);
    assert.equal(actions.filter(([,cls])=>cls.includes('button-filled')).length,primary?1:0,name+': one primary action');
    if(primary)assert.equal(actions[0][0],primary);
    assert.ok(actions.some(([label])=>label==='Library and team tools'),name+': the other views are a button away');
  }
  await f.run("sLegacy('library')");await f.get('actions').children[0].listeners.click();
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Add to the library');
  f.get('memory-form').reset=()=>{};{const submit=new Element('button');submit.type='submit';f.get('memory-form').append(submit);}
  f.run('sCloseSheet()');await f.run("sLegacy('memory')");await f.get('actions').children[0].listeners.click();assert.equal(f.get('memory-dialog').open,true,'Add memory');
  f.get('memory-dialog').open=false;
  // Refresh Hub also sits with Team sharing on Status and Settings, when a Hub can be refreshed.
  f.run("access.actions.refresh=true;studio.team={joined:true,repository:'x',branch:'main',share:'decision'}");
  assert.ok(descendants(f.run('sTeamCard()')).some(e=>e.textContent==='Refresh Hub'));
  f.run("access.actions.refresh=false");assert.equal(descendants(f.run('sTeamCard()')).some(e=>e.textContent==='Refresh Hub'),false);
  // Home: what needs you and what is under way come before starting something new.
  f.run("studio.listing=[{id:'w',title:'Working',status:'working',stages:[],complete:false}];studio.ordinary=[];studio.options={};sHome()");
  const titles=descendants(f.get('studio-page')).filter(e=>e.className==='card-title').map(e=>e.textContent);
  assert.ok(titles.indexOf('In progress')<titles.indexOf('What would you like to do?'),titles.join('|'));
  assert.ok(titles.indexOf('What would you like to do?')<titles.indexOf('Set up before you write'));
}

// A name that might be someone's fuller name: the sheet suggests, the person decides. Same
// person is confirmed, then renames that author's posts; Different person stops suggesting.
// Review details edits one post's author, sending only what changed.
async function authorClarify(){
  const requests=[];let state='suggest';
  const dan={author:'Dan',posts:1,readable:1,samples:[],profile:null,ready:false,reason:'Only 1 readable post; a voice needs at least 2.',expected:'v1',suggestions:[{name:'Dan Smith',posts:2,voice:null},{name:'Dan Baskette',posts:0,voice:{id:'db',name:'Dan Baskette',status:'confirmed',revision:1}}]};
  const smith=posts=>({author:'Dan Smith',posts,readable:posts,samples:[],profile:null,ready:true,reason:'',expected:'v2',suggestions:[]});
  const listing=()=>state==='merged'?{authors:[smith(3)],unnamed:0,minimum:2,batch_limit:100}:state==='apart'?{authors:[smith(2),{...dan,suggestions:[]}],unnamed:0,minimum:2,batch_limit:100}:{authors:[smith(2),dan],unnamed:0,minimum:2,batch_limit:100};
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url==='/api/library-authors')return listing();
    if(url==='/api/library-author-same'){state='merged';return listing();}
    if(url==='/api/library-author-different'){state='apart';return listing();}
    if(url.startsWith('/api/source?'))return {id:'d1',location:'local',expected:'e'.repeat(64),record:{author:'Dan',library:{curation:'active',topics:[],products:[]},note:''},excerpt:'Text'};
    if(url==='/api/curate')return {receipts:[{label:'Reference curation',message:'Saved locally.'}]};
    return {items:[],total:0};});
  f.loadRunner();
  const sheet=()=>descendants(f.get('sheet')),text=()=>sheet().map(e=>e.textContent),find=label=>sheet().find(e=>e.textContent===label);
  await f.run('sVoicesForAuthors()');
  assert.ok(text().includes('Might be the same person as Dan Smith (2 posts) or Dan Baskette (a voice).'),text().join('|'));
  assert.equal(sheet().find(e=>e.value==='Dan').disabled,true,'too small to learn alone, still listed');
  assert.ok(find('Same person as Dan Smith')&&find('Same person as Dan Baskette')&&find('Different person'));
  await find('Same person as Dan Smith').listeners.click();
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Same person?');
  assert.equal(requests.some(r=>r.url==='/api/library-author-same'),false,'nothing changes before the confirmation');
  assert.ok(text().some(t=>/Name Dan Smith as the author of Dan’s 1 post\?/.test(t)));
  await find('Yes, same person').listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/library-author-same').data,{author:'Dan',into:'Dan Smith',expected:'v1'});
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Create voices for every author','the sheet regroups');
  assert.ok(text().some(t=>/^3 posts · 3 readable/.test(t)));assert.equal(sheet().some(e=>e.value==='Dan'),false,'no Dan group remains');
  // Different person, from a fresh list.
  state='suggest';await f.run('sVoicesForAuthors()');
  await find('Different person').listeners.click();
  assert.deepEqual(requests.filter(r=>r.url==='/api/library-author-different').map(r=>r.data),[{author:'Dan',others:['Dan Smith','Dan Baskette']}],'one request, saved all at once');
  assert.equal(text().some(t=>/Might be the same person/.test(t)),false,'the suggestion stops');
  // Review details: the author is a field, sent only when it changes.
  f.set('item',{id:'d1',location:'local',title:'d1'});await f.run('curate(item)');
  const form=descendants(f.get('detail-content')).find(e=>e.tagName==='form');
  const author=descendants(form).find(e=>e.name==='author');assert.equal(author.value,'Dan');
  author.value=' Dan Smith ';await form.listeners.submit({preventDefault(){}});
  const sent=requests.filter(r=>r.url==='/api/curate').at(-1).data;
  assert.deepEqual([sent.author,sent.expected,'topics' in sent],['Dan Smith','e'.repeat(64),false]);
}

function pageDefinesEveryElement(){
  // The fixture creates any element on demand, so check the real page defines every id the script asks for.
  const base='skills/blog-studio/assets/management/';
  const script=fs.readFileSync(base+'app.js','utf8')+fs.readFileSync(base+'runner.js','utf8')+fs.readFileSync(base+'desk.js','utf8'),page=fs.readFileSync(base+'index.html','utf8');
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
  // Every blog Home lists offers Delete beside the way in, through the same typed-title sheet.
  {
    for(const name of ['Needs you','In progress']){const remove=descendants(homeGroup(name)).find(e=>e.textContent==='Delete');assert.ok(remove,name+' offers Delete');assert.equal(remove.className,'button button-quiet','Delete is never the filled button');}
    f.run("studio.listing=[found,working,{...working,id:'done',title:'Done blog',status:'complete',complete:true}];studio.ordinary=[{id:'plain',title:'A saved draft',mode:'existing'},{id:'shared',title:'Hub only',location:'hub'}];sHome()");
    for(const name of ['Finished drafts','Saved drafts'])assert.ok(descendants(homeGroup(name)).some(e=>e.textContent==='Delete'),name+' offers Delete');
    assert.equal(descendants(homeGroup('Saved drafts')).filter(e=>e.textContent==='Delete').length,1,'a blog with no local copy offers no Delete');
    await descendants(homeGroup('In progress')).find(e=>e.textContent==='Delete').listeners.click();
    const open=descendants(f.get('sheet')),said=open.map(e=>e.textContent);
    for(const words of ['Delete Working blog?','Type the title to confirm','It is kept for 30 days under Recently deleted on the Blogs page, where Restore brings it back.'])assert.ok(said.includes(words),words+': '+said.join('|'));
    assert.equal(open.find(e=>e.textContent==='Delete Working blog').disabled,true,'nothing is deleted until the title is typed');
    f.run('sCloseSheet()');
    f.run("studio.listing=[{...working,team:true,driver:{here:false}}];studio.ordinary=[];sHome()");
    assert.equal(descendants(homeGroup('In progress')).find(e=>e.textContent==='Delete').disabled,true,'a team blog driven elsewhere cannot be deleted from Home');
    f.run('studio.listing=[found];studio.ordinary=[];sHome()');
  }
  f.run('studio.listing=[working];sHome()');
  assert.equal(f.get('actions').children[0].className,'button button-filled','nothing waits, so New blog leads');
  assert.ok(!f.get('actions').children.some(e=>e.textContent==='Review Working blog'));
  assert.equal(f.get('actions').children[0].disabled,false);
  f.run('access.actions.edit=false;sHome()');
  assert.equal(f.get('actions').children[0].disabled,true,'New blog follows edit access');
  f.run('access.actions.edit=true');
  f.run('studio.listing=[found];sHome()');
  f.run('studio.ordinary=[];sBlogs()');assert.equal(f.get('title').textContent,'Blogs','titled like its navigation item');
  assert.deepEqual(f.get('actions').children.map(e=>[e.textContent,e.className]),[['New blog','button button-filled'],['Library and team tools','button button-quiet']],'one primary action, then the other views');
  // Every card on Blogs can delete its blog through the same sheet as the run's last screen.
  {
    const remove=descendants(content).find(e=>e.textContent==='Delete');
    assert.ok(remove,'a Blogs card offers Delete');assert.equal(remove.className,'button button-quiet');
    await remove.listeners.click();
    const open=descendants(f.get('sheet'));
    assert.ok(open.some(e=>e.textContent==='Delete Synthetic blog?'),open.map(e=>e.textContent).join('|'));
    f.run('sCloseSheet()');
    f.run("studio.ordinary=[{id:'plain',title:'A saved draft',author:'Avery',mode:'existing'},{id:'shared',title:'Hub only',location:'hub'}];sBlogs()");
    const removes=descendants(content).filter(e=>e.textContent==='Delete');
    assert.equal(removes.length,2,'saved drafts get Delete, and a blog with no local copy does not');
    await removes[1].listeners.click();
    assert.ok(descendants(f.get('sheet')).some(e=>e.textContent==='Delete A saved draft?'),'a saved draft opens the same sheet');
    f.run('sCloseSheet()');
    f.run("studio.ordinary=[{id:'driven',title:'Driven elsewhere',team:true,driver:{here:false}}];sBlogs()");
    const driven=descendants(content).filter(e=>e.textContent==='Delete');
    assert.equal(driven.length,2);assert.equal(driven[0].disabled,false,'the run driven here can be deleted');
    assert.equal(driven[1].disabled,true,'a team blog driven elsewhere cannot be deleted from here');
    f.run("studio.ordinary=[{id:'plain',title:'A saved draft',author:'Avery',mode:'existing'}];access.actions.edit=false;sBlogs()");
    assert.ok(descendants(content).filter(e=>e.textContent==='Delete').every(e=>e.disabled),'Delete follows edit access');
    f.run('access.actions.edit=true;studio.ordinary=[];sBlogs()');
  }
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
  });f.loadRunner();voicesOn(f);
  await f.run("sMoreTools('fixture')");
  const sheet=()=>descendants(f.get('sheet'));
  assert.ok(sheet().some(node=>node.textContent==='Compare Google and local text'));
  assert.ok(sheet().some(node=>node.textContent==='Saved manuscript revisions'));
  assert.ok(sheet().some(node=>node.textContent==='Resume repurpose · ready'));
  assert.equal(calls.some(([url,body])=>body),false);
  await f.run("sVoiceTools('fixture')");assert.ok(sheet().some(node=>node.textContent==='Create a voice'));
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

// Where this run stops is chosen on the form, for this blog only; the chip also makes it the
// level new work starts at in every studio. Settings saves it at once. Nothing leaves the form.
async function whereThisRunStops(){
  const requests=[];let refuse=false;const found={id:'synthetic',title:'Synthetic blog',status:'queued',expected:'version-1',stages:[],decisions:[],brief:{goal:'Explain',audience:'Authors'},seconds:600,engine:'codex',mode:'write'};
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});if(url==='/api/review-level'){if(refuse)return {__http:400,error:'Another studio changed where new work stops. Reload the page and try again.'};return {defaults,workspace:'/synthetic',shared_before:{},review_level:data.level};}if(url==='/api/run-create')return found;return url.startsWith('/api/run?')?found:{};});f.loadRunner();
  const defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''};f.set('defaults',defaults);
  const nodes=()=>descendants(f.get('studio-page')),text=()=>nodes().map(e=>e.textContent),line=()=>nodes().find(e=>e.className==='quiet stops-line')?.textContent;
  f.run("studio.options={settings:{defaults,review_level:'balanced'},sources:[],profiles:[],agents:{codex:true}};studio.screen='new';studio.draft={...defaults,step:1,id:'',title:'A synthetic blog',goal:'Explain',audience:'Authors',profile:'',sources:[],manuscript:'',mode:'write',stop:'package',minutes:'10',operation:'a'.repeat(32)};sWizard()");
  const card=nodes().find(e=>e.tagName==='section'&&e.children[0]?.textContent==='Where this run stops');assert.ok(card,'the last step has a Where this run stops card: '+text().join('|'));
  const segments=descendants(card).filter(e=>e.className==='seg-option');assert.deepEqual(segments.map(e=>e.textContent),['Balanced','Automatic draft','Step by step']);
  assert.equal(segments[0].attributes['aria-pressed'],'true','it starts at the shared level the form read');
  assert.equal(line(),'Balanced: it stops for the outline and the handoff');
  assert.ok(descendants(card).some(e=>e.tagName==='span'&&e.textContent==='Use this for new work in every studio'),'the chip');
  assert.ok(descendants(card).some(e=>e.textContent==='Saved when the blog starts.'),'the chip says when it is saved');
  assert.equal(nodes().some(e=>e.tagName==='a'&&String(e.href||'').startsWith('/onboarding/')),false,'nothing on the form leaves it');
  await segments[2].listeners.click();
  assert.equal(line(),'Step by step: it stops for the outline, the draft, the review and the handoff');
  assert.equal(f.run('studio.options.settings.review_level'),'balanced','the shared level is not changed by the form');
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const created=requests.find(r=>r.url==='/api/run-create');assert.ok(created,'Start writing creates the run');
  assert.equal(created.data.review_level,'step_by_step');assert.equal(created.data.review_seen,'balanced');assert.equal(created.data.review_default,false);
  // Settings: Where new work stops, saved at once; a refusal shows in its own problem line.
  f.run("studio.settings={defaults,workspace:'/synthetic',shared_before:{},review_level:'balanced'};studio.team={};studio.brand=null;studio.screen='settings';sSettings()");
  const shared=nodes().find(e=>e.tagName==='a'&&e.textContent==='Change shared settings');assert.ok(shared&&shared.href.startsWith('/onboarding/'),'Settings keeps its way to the shared settings');
  const where=nodes().find(e=>e.tagName==='section'&&e.children[0]?.textContent==='Where new work stops');assert.ok(where,'Settings shows Where new work stops: '+text().join('|'));
  const choices=descendants(where).filter(e=>e.className==='seg-option');assert.deepEqual(choices.map(e=>e.textContent),['Balanced','Automatic draft','Step by step']);
  await choices[1].listeners.click();
  assert.deepEqual(requests.filter(r=>r.url==='/api/review-level').pop().data,{level:'automatic',seen:'balanced'});
  assert.equal(f.run('studio.settings.review_level'),'automatic');
  refuse=true;
  const again=nodes().find(e=>e.tagName==='section'&&e.children[0]?.textContent==='Where new work stops');
  await descendants(again).filter(e=>e.className==='seg-option')[2].listeners.click();
  assert.deepEqual(requests.filter(r=>r.url==='/api/review-level').pop().data,{level:'step_by_step',seen:'automatic'});
  const after=nodes().find(e=>e.tagName==='section'&&e.children[0]?.textContent==='Where new work stops');
  assert.ok(descendants(after).some(e=>e.className==='problem'&&e.textContent==='Another studio changed where new work stops. Reload the page and try again.'),'the refusal is in the card: '+descendants(after).map(e=>e.textContent).join('|'));
}

// One name for each thing: the handoff, Record in team repository, the research choice, the
// example role and the kind of post a style is.
async function oneVocabulary(){
  const f=fixture(()=>({}));f.loadRunner();
  const nodes=()=>descendants(f.get('studio-page')),text=()=>nodes().map(e=>e.textContent);
  const stages=[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'approved'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'approved'},{stage:'review',label:'Review',path:'derived/blog-review.md',status:'approved'},{stage:'package',label:'Handoff',path:'derived/blog-package.md',status:'pending'}];
  const working={id:'synthetic',title:'Synthetic blog',status:'working',next:'package',approval:'page',expected:'v1',enabled:true,directory:'/synthetic',seconds:600,engine:'codex',mode:'write',review_level:'balanced',decisions:[],brief:{goal:'Explain',audience:'Authors'},notes:{},started_at:new Date().toISOString(),stages};
  f.set('found',working);f.run("studio.screen='run';studio.id=found.id;sRun(found)");
  assert.ok(text().some(t=>/^Writing the handoff · /.test(t)),'the now line names the handoff: '+text().join('|'));
  assert.ok(nodes().some(e=>e.className==='bead-name'&&e.textContent==='Handoff'));
  // A finished team blog this computer drives records it in the team repository.
  f.set('found',{...working,status:'complete',complete:true,next:null,started_at:null,team:true,driver:{here:true},stages:stages.map(row=>({...row,status:'approved'}))});f.run('sRun(found)');
  const labels=f.get('actions').children.map(e=>e.textContent);
  assert.ok(labels.includes('Record in team repository'),labels.join('|'));assert.equal(labels.includes('Publish revision'),false);
  // The research choice, one way in Settings, a new blog and from files: your documents, your
  // sites and the public web.
  const defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''};f.set('defaults',defaults);
  const ticks=['your documents','your sites (3)','the public web'],shared=['https://a.example','https://b.example/docs','https://c.example'];f.set('shared',shared);
  f.run("studio.settings={defaults,workspace:'/synthetic',shared_before:{},review_level:'balanced',research_sites:shared};studio.team={};studio.brand=null;studio.screen='settings';sSettings()");
  assert.ok(text().includes('Research for new blogs from:'));for(const label of ticks)assert.ok(text().includes(label),label+': '+text().join('|'));
  f.run("studio.options={settings:{defaults,review_level:'balanced',research_sites:shared},sources:[],profiles:[],agents:{codex:true}};studio.screen='new';studio.draft={...defaults,step:1,id:'',title:'A synthetic blog',goal:'Explain',audience:'Authors',profile:'',sources:[],manuscript:'',mode:'write',stop:'package',minutes:'10',operation:'a'.repeat(32)};sWizard()");
  assert.ok(text().includes('Research it first')&&text().includes('Research from:'));for(const label of ticks)assert.ok(text().includes(label),label);
  f.run("studio.draft={...defaults,mode:'from-files',files:[],step:0,title:'',goal:'',audience:'',profile:'',sources:[],stop:'package',minutes:'10',operation:'b'.repeat(32)};sWizard()");
  assert.ok(text().includes('Research from:'),text().join('|'));for(const label of ticks)assert.ok(text().includes(label),label);
  assert.ok(text().includes('Your files are read at every step. Your sites or the public web add research before the outline.'));
  assert.ok(text().some(t=>t==='Example of the kind of post'),'one example label: '+text().join('|'));
  for(const old of ['Examples of the kind of post','examples of a kind of writing','Selected sources only','Sources plus public research','Also research the web to fill gaps','Also research the public web','Only what you supply','What you supply and the public web','Off: only what you supply.'])assert.equal(text().some(t=>t.includes(old)),false,old);
}

// The form and the gates say only what they do: what research reads, what the tone does with
// a voice, what each gate's decision does, and where a change comes back.
async function honestBlogCopy(){
  const requests=[];let changed=null;
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});if(url==='/api/run-changes')return changed;return {};});f.loadRunner();voicesOn(f);
  const nodes=()=>descendants(f.get('studio-page')),text=()=>nodes().map(e=>e.textContent),all=()=>text().join('\n');
  const defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''};f.set('defaults',defaults);
  f.run("studio.options={settings:{defaults,review_level:'balanced'},sources:[{id:'one',name:'One',status:'ready',purposes:['reference']},{id:'two',name:'Two',status:'ready',purposes:['reference']}],profiles:[],agents:{codex:true}};studio.screen='new';studio.draft={...defaults,step:1,id:'',title:'A synthetic blog',goal:'Explain',audience:'Authors',profile:'',sources:[],manuscript:'',mode:'write',stop:'package',minutes:'10',operation:'a'.repeat(32)};sWizard()");
  assert.ok(all().includes('No research.'),all());
  // Use the real listeners: refreshing the explanation must preserve these controls.
  const tick=key=>nodes().find(e=>e.id==='new-research-'+key);
  const sources=nodes().find(e=>e.className==='source-choices'&&e.parent?.className!=='site-choices').querySelectorAll('input');
  const chooseResearch=(key,checked)=>{const box=tick(key);box.focus();box.checked=checked;box.listeners.change();assert.equal(tick(key),box);assert.equal(box.focused,true);};
  const chooseSource=(index,checked)=>{sources[index].focus();sources[index].checked=checked;sources[index].listeners.change();assert.equal(nodes().find(e=>e.className==='source-choices'&&e.parent?.className!=='site-choices').querySelectorAll('input')[index],sources[index]);assert.equal(sources[index].focused,true);};
  chooseResearch('on',true);
  assert.ok(all().includes('No research: no source is ticked.'),all());
  assert.equal(all().includes('No research.'),false);
  chooseSource(0,true);
  assert.ok(all().includes('Research from your documents.'),all());
  chooseSource(1,true);
  assert.ok(all().includes('Research from your documents.'),all());
  chooseResearch('web',true);
  assert.ok(all().includes('Research from your documents and the public web.'),all());
  assert.equal(all().includes('Research from your documents.'),false);
  assert.deepEqual(Array.from(f.run('studio.draft.sources')),['one','two']);
  assert.ok(sources.every(source=>source.checked),'changing research preserves the sources');
  chooseResearch('web',false);
  chooseSource(0,false);
  assert.ok(all().includes('Research from your documents.'),all());
  chooseSource(1,false);
  assert.ok(all().includes('No research: no source is ticked.'),all());
  chooseResearch('on',false);
  assert.ok(all().includes('No research.'),all());
  assert.equal(all().includes('No research: no source is ticked.'),false);
  assert.equal(all().includes('Research uses only the sources you allow'),false);
  assert.ok(all().includes('With a voice chosen, the usual tone is left out; a tone you type here is added as a nudge.'));
  assert.equal(all().includes('Tone is a nudge on top of the voice.'),false);
  // Each gate's lede says what its decision does.
  const stages=[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'approved'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'draft'},{stage:'review',label:'Review',path:'derived/blog-review.md',status:'pending'},{stage:'package',label:'Handoff',path:'derived/blog-package.md',status:'pending'}];
  const found={id:'synthetic',title:'Synthetic blog',status:'waiting-for-approval',next:'draft',approval:'page',expected:'v1',enabled:true,directory:'/synthetic',seconds:600,engine:'codex',mode:'write',review_level:'step_by_step',decisions:[],brief:{goal:'Explain',audience:'Authors'},notes:{},stages};
  const shown={id:'synthetic',title:'Synthetic blog',name:'DRAFT.md',stage:'draft',label:'Draft',expected:'v1',status:'draft',content:'# Draft',notes:'',checks:[],previous:null,diff:[]};
  f.set('found',found);f.set('shown',shown);f.run("studio.screen='gate';studio.found=found;sGate(found,shown)");
  assert.ok(all().includes('Read the draft. Use it to go on, or ask for changes.'),all());
  f.set('shown',{...shown,stage:'review',name:'blog-review.md',label:'Review'});f.set('found',{...found,next:'review',stages:stages.map(row=>row.stage==='draft'?{...row,status:'approved'}:row.stage==='review'?{...row,status:'draft'}:row)});f.run("sGate(found,shown)");
  assert.ok(all().includes('Read the review. Its findings go to the handoff; to act on one, ask for changes to the draft.'),all());
  for(const old of ['polish the wording','return to the manuscript'])assert.equal(all().includes(old),false,old);
  // Ask for changes says what it does, and the toast where the change comes back.
  f.set('found',found);f.run("sChanges(found,'draft')");
  const sheet=()=>descendants(f.get('sheet')).map(e=>e.textContent);
  assert.ok(sheet().some(t=>t.includes('Ask for changes writes this stage again with your words.')),sheet().join('|'));
  changed={...found,status:'queued',enabled:true,stages:stages.map(row=>row.stage==='draft'?{...row,status:'pending'}:row),ahead:{steps_left:3,next_gate:'draft',next_stop:'Draft'}};
  descendants(f.get('sheet')).find(e=>e.id==='change-request').value='Shorter.';descendants(f.get('sheet')).find(e=>e.id==='change-request').listeners.input();
  await descendants(f.get('sheet')).find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.ok(descendants(f.get('toasts')).some(e=>e.textContent==='Your changes are noted. The next draft comes back for your review.'),descendants(f.get('toasts')).map(e=>e.textContent).join('|'));
  // Under Balanced the review is not a stop: it is written again and the run goes on.
  const balanced={...found,next:'review',review_level:'balanced',stages:stages.map(row=>row.stage==='draft'?{...row,status:'approved'}:row.stage==='review'?{...row,status:'draft'}:row)};
  f.set('found',balanced);f.run("sChanges(found,'review')");
  changed={...balanced,status:'queued',enabled:true,ahead:{steps_left:2,next_gate:'package',next_stop:'Handoff'}};
  descendants(f.get('sheet')).find(e=>e.id==='change-request').value='Name the risk.';descendants(f.get('sheet')).find(e=>e.id==='change-request').listeners.input();
  await descendants(f.get('sheet')).find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.ok(descendants(f.get('toasts')).some(e=>e.textContent==='Your changes are noted. The review is written again and the run goes on to the handoff, where you see it.'),descendants(f.get('toasts')).map(e=>e.textContent).join('|'));
}

// The pattern every studio shares: the start form says where it stops, the run says what it
// is doing now and for how long, a retry says what it costs, a note reaches the next job
// without stopping, and a phone keeps one decision in the toolbar.
async function sharedPattern(){
  const requests=[];const found={id:'synthetic',title:'Synthetic blog',status:'working',next:'draft',approval:'page',expected:'version-1',enabled:true,directory:'/synthetic/articles/synthetic',seconds:600,engine:'codex',mode:'write',review_level:'balanced',ahead:{steps_left:2,next_gate:'draft',next_stop:'Draft',jobs:2,seconds:180,dollars:null,spent:'3 minutes; the assistant reported no cost'},decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},started_at:new Date(Date.now()-3*60000).toISOString(),note_stage:'review',notes:{},stages:[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'approved'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'pending'},{stage:'review',label:'Review',path:'REVIEW.md',status:'pending'}]};
  const f=fixture((url,options)=>{requests.push({url,options,data:options?.body?JSON.parse(options.body):null});if(url==='/api/upload')return f.run('studio.api_upload');if(url==='/api/run-create')return found;return url.startsWith('/api/run?')?found:{...found,noted:'draft'};});f.loadRunner();voicesOn(f);
  const text=()=>descendants(f.get('studio-page')).map(e=>e.textContent);
  // The start form: one line says where this run stops, from the shared review level.
  const defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''};f.set('defaults',defaults);
  f.run("studio.options={settings:{defaults,review_level:'balanced'},sources:[],profiles:[],agents:{codex:true}};studio.screen='new';studio.draft={...defaults,step:1,id:'',title:'A synthetic blog',goal:'Explain',audience:'Authors',profile:'',sources:[],manuscript:'',mode:'write',stop:'draft',minutes:'10',operation:'a'.repeat(32)};sWizard()");
  assert.ok(text().some(t=>t==='Balanced: it stops for the outline and the draft'),'the stops line follows the review level and the pipeline: '+text().join('|'));
  {assert.equal(descendants(f.get('studio-page')).some(e=>e.id==='new-profile'),false,'the voice is chosen on the first step, not the second');
   const tone=descendants(f.get('studio-page')).find(e=>e.id==='new-tone');let node=tone,inside=null;while(node){if(node.tagName==='details'&&!inside)inside=node;node=node.parent;}assert.ok(inside,'the tone stays in a disclosure');
   assert.ok(descendants(inside).some(e=>e.textContent==='Tone, author and brand'),'the Tone, author and brand disclosure');
   f.run("studio.draft.step=0;sWizard()");
   const voice=descendants(f.get('studio-page')).find(e=>e.id==='new-profile');assert.ok(voice,'the first step chooses the voice');node=voice;let hidden=false;while(node){if(node.tagName==='details')hidden=true;node=node.parent;}assert.equal(hidden,false,'Write as is visible without opening a disclosure');
   assert.equal(descendants(f.get('studio-page')).find(e=>e.tagName==='label'&&e.htmlFor==='new-profile').textContent,'Write as');assert.deepEqual(voice.children.map(o=>o.textContent),['No particular voice (use the described tone)','Learn a new voice…'],'without saved profiles, only no particular voice');
   f.run("studio.options.profiles=[{id:'p1',name:'Avery',status:'confirmed'},{id:'p2',name:'Sam',status:'provisional'}];studio.options.default_voice={scope:'personal',profile:'p1',name:'Avery',revision:3,status:'confirmed'};studio.draft.profile=null;sWizard()");
   assert.deepEqual(descendants(f.get('studio-page')).find(e=>e.id==='new-profile').children.map(o=>[o.value,o.textContent]),[['*default','My voice — Avery · confirmed'],['p2','Sam · provisional'],['','No particular voice (use the described tone)'],['*learn','Learn a new voice…']]);
   f.run("studio.options.profiles=[];studio.options.default_voice=null;studio.draft.profile='';studio.draft.step=1;sWizard()");}
  f.run("studio.options.settings.review_level='balanced';studio.draft.mode='from-outline';studio.draft.stop='package';sWizard()");
  assert.ok(text().some(t=>t==='Balanced: it stops for the draft and the handoff'),'Balanced reads the first writing stage a run has: '+text().join('|'));
  f.run("studio.draft.mode='write';studio.draft.stop='draft';sWizard()");
  assert.equal(descendants(f.get('studio-page')).some(e=>e.tagName==='a'&&e.textContent==='Change'),false,'the form has no Change link: where it stops is chosen on it');
  // The second step takes every file at once and lists each one with its text and role; the old one-at-a-time input is gone.
  {const nodes=()=>descendants(f.get('studio-page')),byId=id=>nodes().find(e=>e.id===id);
   assert.equal(nodes().some(e=>e.textContent==='Add a document'),false,'no single-file upload on the wizard');
   const picker=byId('files-input');assert.ok(picker,'the wizard has the files picker');assert.equal(picker.multiple,true);
   assert.ok(byId('files-role'),'and asks what the files are for');assert.ok(byId('files-google'),'and takes a Google Doc');
   let node=picker,inside=false;while(node){if(node.tagName==='details')inside=true;node=node.parent;}assert.equal(inside,false,'the files card is in plain view, not inside a disclosure');
   f.set('uploadedTwo',{files:[{filename:'messaging.md',source:{id:'m1',name:'messaging'},state:'ready',chars:900,note:''},{filename:'old-post.md',source:{id:'m2',name:'old post'},state:'ready',chars:2100,note:''}],receipts:[],state:'saved',next_step:'Every file has text.'});
   f.run("studio.api_upload=uploadedTwo");
   picker.files=[{name:'messaging.md',size:9,arrayBuffer:async()=>new TextEncoder().encode('Messaging').buffer},{name:'old-post.md',size:8,arrayBuffer:async()=>new TextEncoder().encode('Old post').buffer}];
   await picker.listeners.change();
   const upload=requests.filter(r=>r.url==='/api/upload');assert.equal(upload.length,1,'both files go up in one request');
   assert.deepEqual(upload[0].data.files.map(e=>e.filename),['messaging.md','old-post.md']);assert.equal(upload[0].data.purpose,'material');assert.equal(upload[0].data.keep,true,'the wizard keeps files in the team library too');
   const titles=nodes().filter(e=>e.className==='row-title').map(e=>e.textContent);assert.deepEqual(titles,['messaging.md','old-post.md'],'every added file is listed: '+titles.join('|'));
   assert.ok(text().some(t=>/900 characters/.test(t))&&text().some(t=>/2,100 characters/.test(t)),'each with how much text it has');
   assert.ok(byId('files-role-m1')&&byId('files-role-m2'),'each with its role');
   assert.equal(f.run('studio.busy'),false,'the screen is free again after the upload');
   assert.ok(text().some(t=>t==='Balanced: it stops for the outline and the draft'),'with no research chosen the stops are unchanged: '+text().join('|'));
   f.run("studio.options.settings.review_level='step_by_step';studio.draft.from=sFromDefault('supplied-only');sWizard()");
   assert.ok(text().some(t=>t==='Step by step: it stops for the claims in your material, the outline and the draft'),'selected sources research counts the files: '+text().join('|'));
   f.run("studio.options.settings.review_level='balanced';studio.draft.from=sFromDefault('none');sWizard()");
   await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
   const created=requests.find(r=>r.url==='/api/run-create');assert.ok(created,'Start writing creates the run');assert.deepEqual(created.data.sources,['m1','m2'],'the files are the run\'s sources');
   f.run("studio.draft={...defaults,step:1,id:'',title:'A synthetic blog',goal:'Explain',audience:'Authors',profile:'',sources:[],manuscript:'',mode:'write',stop:'draft',minutes:'10',operation:'a'.repeat(32)};sWizard()");}
  assert.equal(descendants(f.get('studio-page')).some(e=>['new-engine','new-minutes'].includes(e.id)),false,'the assistant and time limit are defaults, not per-blog decisions');
  f.run("studio.options.settings.review_level='automatic';studio.draft.mode='ideas';sWizard()");
  assert.ok(text().some(t=>t==='Automatic draft: it stops for the ideas'),text().join('|'));
  f.run("studio.options.settings.review_level='step_by_step';studio.draft.mode='write';studio.draft.from=sFromDefault('supplied-only');studio.draft.stop='package';sWizard()");
  assert.ok(text().some(t=>t==='Step by step: it stops for the outline, the draft, the review and the handoff'),'selected sources with none selected is no research: '+text().join('|'));
  f.run("studio.options.sources=[{id:'one',name:'One',status:'ready',purposes:['reference']}];studio.draft.sources=['one'];sWizard()");
  assert.ok(text().some(t=>t==='Step by step: it stops for the claims in your material, the outline, the draft, the review and the handoff'),text().join('|'));
  // New blog without a task chosen shows the same start cards as Home.
  f.run("studio.draft={...defaults,mode:null,step:0};sWizard()");
  assert.equal(f.get('title').textContent,'New blog');assert.ok(descendants(f.get('studio-page')).some(e=>e.className==='pick-card'&&e.textContent==='Write about a topic'));
  // Settings no longer ask where to stop: the review level governs that.
  f.run("studio.settings={defaults,workspace:'/synthetic',shared_before:{}};studio.team={};studio.brand=null;sSettings()");
  assert.equal(descendants(f.get('studio-page')).some(e=>e.id==='settings-stop'),false);
  // The run: a "now" line under the title, with the step and how long it has taken.
  f.set('found',found);f.run('studio.screen=\'run\';studio.id=found.id;sRun(found)');
  const now=descendants(f.get('studio-page')).find(e=>e.className==='now-line');
  assert.equal(now.textContent,'Drafting · 3 min of up to 10');
  f.run('studio.signature=JSON.stringify(found);const realNow=Date.now;Date.now=()=>realNow()+4*60000');await f.run('sPoll()');
  assert.equal(descendants(f.get('studio-page')).find(e=>e.className==='now-line').textContent,'Drafting · 7 min of up to 10','the now line ticks while nothing else changes');
  assert.equal(text().some(t=>/cost is not tracked/.test(t)),false,'the run says what it spent instead');
  assert.equal(descendants(f.get('studio-page')).find(e=>e.className==='quiet ahead-line')?.textContent,'2 steps left · Next stop: the draft · So far 3 minutes; the assistant reported no cost','one line under the beads: steps left, the next stop and what it has spent');
  // A cost reported as nothing is never "$0.00": the research line says no cost was reported.
  assert.equal(f.run("sTook({jobs:2,rounds:1,seconds:90,tokens:null,dollars:0,reported:true})").includes('$0.00'),false);
  // A team blog's jobs are kept on each computer that ran them: the line says so.
  f.set('found',{...found,team:true});f.run('sRun(found)');
  assert.equal(descendants(f.get('studio-page')).find(e=>e.className==='quiet ahead-line')?.textContent,'2 steps left · Next stop: the draft · So far on this computer 3 minutes; the assistant reported no cost');
  // A saved run from before jobs were kept says nothing of what it spent.
  f.set('found',{...found,ahead:{...found.ahead,jobs:0,seconds:0,dollars:null,spent:null}});f.run('sRun(found)');
  assert.equal(descendants(f.get('studio-page')).find(e=>e.className==='quiet ahead-line')?.textContent,'2 steps left · Next stop: the draft');
  f.set('found',{...found,ahead:undefined});f.run('sRun(found)');
  assert.equal(descendants(f.get('studio-page')).some(e=>e.className==='quiet ahead-line'),false,'a view without ahead draws without it');
  f.set('found',found);f.run('sRun(found)');
  // A note for the next step goes with the next job and stops nothing.
  const note=descendants(f.get('studio-page')).find(e=>e.id==='note-request');note.value='Mention the gateway.';note.listeners.input();
  await descendants(f.get('studio-page')).find(e=>e.textContent==='Add the note').listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/run-note').data,{id:'synthetic',expected:'version-1',request:'Mention the gateway.'});
  assert.ok(text().some(t=>/goes with the next job that starts, review/.test(t)),'the box names the stage the runner would note for');
  f.set('found',{...found,note_stage:null});f.run('sRun(found)');assert.equal(descendants(f.get('studio-page')).some(e=>e.id==='note-request'),false,'no later step, no box');
  // A time limit that ran out offers more time, and says what a plain retry costs.
  f.set('found',{...found,status:'failed',enabled:false,started_at:null,error:'This step reached its time limit. Retry or continue in chat.'});f.run('sRun(found)');
  const more=f.get('actions').children.find(e=>e.textContent==='Try again with more time');assert.equal(more.className,'button button-filled');
  assert.ok(text().some(t=>t==='Try again makes the draft again in a new job, with the same 10-minute limit; saved work is kept.'),text().join('|'));
  assert.ok(text().some(t=>t==='The limit is in Settings → Step time limit and applies to blogs started after a change. Try again with more time doubles it to 20 minutes for this blog.'),'a time limit says where it lives: '+text().join('|'));
  await more.listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/run-retry').data,{id:'synthetic',expected:'version-1',seconds:1200});
  // Ask for changes says what it draws again, and what that took, before it is sent.
  f.set('found',{...found,status:'waiting-for-approval',stages:[found.stages[0],{...found.stages[1],status:'draft'},found.stages[2]],redo:{outline:{stages:['outline','draft','review'],says:'Drawn again: the outline and every step after it, 3 steps. Last time they took 12 minutes and about $1.40.'},draft:{stages:['draft','review'],says:'Drawn again: the draft and every step after it, 2 steps; this computer has no record of what they cost.'}}});
  f.run("sChanges(found,'draft')");
  {const sheet=()=>descendants(f.get('sheet')).map(e=>e.textContent);
   assert.ok(sheet().includes('Drawn again: the draft and every step after it, 2 steps; this computer has no record of what they cost.'),'the sheet prices the change: '+sheet().join('|'));
   const pick=descendants(f.get('sheet')).find(e=>e.id==='change-stage');pick.value='outline';pick.listeners.change();
   assert.ok(sheet().includes('Drawn again: the outline and every step after it, 3 steps. Last time they took 12 minutes and about $1.40.'),'and follows the stage chosen: '+sheet().join('|'));
   f.run('sCloseSheet()');}
  // Copy Markdown sits beside the download.
  const shown={id:found.id,title:found.title,name:'DRAFT.md',stage:'draft',label:'Draft',expected:found.expected,status:'draft',content:'# Draft',notes:'',checks:[],previous:null,diff:[]};
  f.set('shown',shown);f.run("studio.screen='gate';studio.found=found;sGate({...found,status:'waiting-for-approval'},shown)");
  assert.ok(descendants(f.get('studio-page')).some(e=>e.textContent==='Copy Markdown'));
  // A phone keeps one decision in the toolbar and folds the rest into the menu.
  f.run("window.matchMedia=query=>({matches:/max-width/.test(query)});studio.screen='run';sRun({...found,status:'waiting-for-approval',enabled:true,error:'',stages:[found.stages[0],{...found.stages[1],status:'draft'}]})");
  const actions=f.get('actions').children;
  assert.ok(descendants(f.get('studio-page')).some(e=>e.className==='quiet ahead-line'),'the ahead line is drawn on a phone too');
  assert.equal(actions.filter(e=>e.tagName==='button').length,1,'one action stays in the toolbar on a phone');
  assert.equal(actions[0].textContent,'Review Draft');assert.equal(actions[0].className,'button button-filled');
  const menu=actions.find(e=>e.tagName==='details');assert.equal(menu.className,'menu');
  assert.deepEqual(descendants(menu).filter(e=>e.className==='menu-item').map(e=>e.textContent),['Edit manuscript','Pause','Tools']);
  f.run('delete window.matchMedia');
}


// A real finish: the final stop shows the draft open with Finish, a finished run has a Done
// card, Delete asks for the typed title and says what is running stops, Blogs lists what was
// New blog from my files: one screen uploads every file at once with its role and says what each has,
// the run starts from the readable ones, and the angles gate offers picks or none of these.
async function filesJourney(){
  const requests=[];let refuseRole=false;
  const defaults={engine:'codex',seconds:600,research:'supplied-only',stop:'package',tone:'Clear',author:''};
  const uploaded={files:[{filename:'notes.md',source:{id:'s1',name:'notes'},state:'ready',chars:1200,note:''},{filename:'scan.pdf',source:{id:'s2',name:'scan'},state:'pending',chars:0,note:'This computer has no PDF reader (pdftotext), so this PDF needs text.'}],receipts:[],state:'saved',next_step:'1 of 2 files have text.'};
  const found={id:'files',title:'From my files',status:'queued',next:'angles',approval:'page',expected:'a1',enabled:true,directory:'/synthetic',seconds:600,engine:'codex',mode:'from-files',review_level:'balanced',decisions:[],brief:{goal:'A team post',audience:'To be chosen with the angle.'},stages:[{stage:'angles',label:'Angles',path:'derived/blog-angles.md',status:'pending'}],excerpted:[]};
  const f=fixture((url,options)=>{requests.push({url,data:options?.body?JSON.parse(options.body):null});
    if(url==='/api/run-options')return {settings:{defaults,review_level:'balanced'},sources:[],profiles:[{id:'p1',name:'Avery',status:'confirmed'},{id:'p2',name:'Sam',status:'provisional'}],default_voice:{scope:'personal',profile:'p1',name:'Avery',revision:3,status:'confirmed'},agents:{codex:true}};
    if(url==='/api/source-role'&&refuseRole)return {__http:400,error:'A started blog read this file as facts; its role stays.'};
    if(url==='/api/upload')return (JSON.parse(options.body).files||[]).some(e=>e.google)?{files:[{filename:'Messaging Doc',source:{id:'s9',name:'Messaging Doc'},state:'ready',chars:4200,note:'All 3 tabs were read: “Overview”, “Messaging”, “FAQ”. Link one tab to read only that tab.',link:'https://docs.google.com/document/d/abc/edit'}]}:uploaded;
    if(url==='/api/source-role')return {id:JSON.parse(options.body).id,role:JSON.parse(options.body).role};
    if(url==='/api/run-create'||url.startsWith('/api/run?'))return found;
    if(url.startsWith('/api/run-'))return found;
    return {items:[],total:0};});
  f.loadRunner();voicesOn(f);f.run('sHome()');
  const nodes=()=>descendants(f.get('studio-page')),text=()=>nodes().map(e=>e.textContent),byId=id=>nodes().find(e=>e.id===id);
  // New blogs start on the writing desk; the files screen stays for the code that reaches it.
  assert.ok(!nodes().some(e=>e.className==='pick-card'&&e.textContent==='New blog from my files'),'Home starts new blogs on the desk');
  await f.run("newBlog('',null,'from-files')");
  assert.equal(f.get('title').textContent,'New blog from my files');
  const picker=byId('files-input');
  assert.equal(picker.type,'file');assert.equal(picker.multiple,true);assert.match(picker.accept,/\.pdf/);
  assert.ok(byId('files-goal'),'one optional line: what is this for');
  assert.equal(byId('files-research-web').checked,false,'web research is off by default');assert.equal(byId('files-research-documents').checked,true,'your files are your documents');
  assert.equal(byId('files-keep').checked,true,'files land in the team library by default');
  assert.equal(byId('files-keep').parent.children[1].textContent,'Keep in the team library');
  assert.match(byId('files-keep-hint').textContent,/^Applies to files you add next\./);assert.match(byId('files-keep-hint').textContent,/just this blog/);
  {const ids=nodes().filter(e=>e.id).map(e=>e.id);assert.ok(ids.indexOf('files-keep')<ids.indexOf('files-input'),'Keep comes before the picker: '+ids.join('|'));}
  assert.match(byId('files-google-hint').textContent,/lands in the team library unless Keep is unticked; then it stays with just this blog/);
  assert.equal(nodes().some(e=>e.id==='new-profile'),false);
  const start=()=>nodes().find(e=>e.type==='submit');
  assert.equal(start().disabled,true,'nothing to start before a file has text');
  assert.ok(text().some(t=>/^Add at least one file with text, from your computer, a Google Doc or the library, and this lights up\.$/.test(t)),'and the screen says why Start is grey: '+text().join('|'));
  assert.equal(start().textContent,'Find three angles');
  assert.ok(text().some(t=>/stops for the angles/.test(t)),'the stops line names the angles: '+text().join('|'));
  // Each upload says what the files are for: facts by default, approved messaging, or an example of the kind of post.
  const role=()=>byId('files-role');
  assert.equal(role().tagName,'select');assert.equal(role().value,'material');
  assert.deepEqual(role().children.map(o=>[o.value,o.textContent]),[['material','Facts (may be quoted)'],['messaging','Approved messaging (the product’s own claims)'],['inspiration','Example of the kind of post']]);
  // Write as: the same choice as the wizard's first step. My voice is the default voice, a
  // provisional profile says so, and no particular voice shows the tone.
  const voice=()=>byId('files-voice');
  assert.equal(nodes().find(e=>e.tagName==='label'&&e.htmlFor==='files-voice').textContent,'Write as');
  assert.equal(voice().value,'*default','My voice, the personal default voice, is chosen first');
  assert.deepEqual(voice().children.map(o=>[o.value,o.textContent]),[['*default','My voice — Avery · confirmed'],['p2','Sam · provisional'],['','No particular voice (use the described tone)'],['*learn','Learn a new voice…']]);
  assert.equal(byId('files-tone'),undefined,'a chosen voice needs no tone');
  voice().value='';voice().listeners.change();
  assert.ok(byId('files-tone'),'no particular voice: the tone field appears');
  voice().value='*default';voice().listeners.change();
  assert.equal(byId('files-tone'),undefined);
  // Every chosen file goes up in one request, as material, each with its role.
  picker.files=[{name:'notes.md',size:12,arrayBuffer:async()=>new TextEncoder().encode('Notes words.').buffer},{name:'scan.pdf',size:4,arrayBuffer:async()=>new TextEncoder().encode('%PDF').buffer}];
  await picker.listeners.change();
  const upload=requests.filter(r=>r.url==='/api/upload');
  assert.equal(upload.length,1);
  assert.deepEqual(upload[0].data.files.map(e=>e.filename),['notes.md','scan.pdf']);
  assert.deepEqual(upload[0].data.files.map(e=>e.purpose),['material','material']);
  assert.equal(upload[0].data.purpose,'material');assert.equal(upload[0].data.keep,true,'kept in the team library');assert.equal(upload[0].data.analyze,false);
  assert.equal('author' in upload[0].data,false,'no author until one is named');assert.equal('kind' in upload[0].data,false,'no kind of post until one is chosen');
  assert.match(upload[0].data.operation,/^[0-9a-f]{32}$/);
  assert.ok(text().some(t=>/1,200 characters/.test(t)),'each file shows its extracted size: '+text().join('|'));
  assert.ok(text().some(t=>/^1,200 characters · In the team library$/.test(t)),'and says it went to the team library: '+text().join('|'));
  assert.ok(text().some(t=>/Needs text/.test(t)),'a file without text says so');
  assert.ok(text().some(t=>/no PDF reader/.test(t)),'and why');
  assert.equal(start().disabled,false);
  assert.equal(text().some(t=>/^Add at least one file with text/.test(t)),false,'the hint goes once a file has text');
  // A file's role can change until Start: the row's select calls source-role.
  const rowRole=()=>byId('files-role-s1');
  assert.equal(rowRole().value,'material');
  rowRole().value='inspiration';await rowRole().listeners.change();
  assert.deepEqual(requests.find(r=>r.url==='/api/source-role').data,{id:'s1',role:'example'});
  assert.equal(byId('files-role-s1').value,'inspiration','the row keeps the new role');
  byId('files-role-s1').value='messaging';await byId('files-role-s1').listeners.change();
  assert.deepEqual(requests.filter(r=>r.url==='/api/source-role').at(-1).data,{id:'s1',role:'messaging'},'approved messaging is its own role');
  byId('files-role-s1').value='material';await byId('files-role-s1').listeners.change();
  assert.deepEqual(requests.filter(r=>r.url==='/api/source-role').at(-1).data,{id:'s1',role:'facts'});
  assert.equal(f.run('studio.busy'),false,'the screen is free again after a role change');assert.equal(start().disabled,false);
  // A refused role change goes back to what it was and says why.
  refuseRole=true;byId('files-role-s1').value='inspiration';await byId('files-role-s1').listeners.change();refuseRole=false;
  assert.equal(byId('files-role-s1').value,'material','the row shows the role the file kept');
  assert.ok(text().some(t=>/its role stays/.test(t)),'and says why: '+text().join('|'));
  assert.equal(f.run('studio.busy'),false);assert.equal(start().disabled,false);
  // Example files go up with inspiration; the select applies to the next upload.
  role().value='inspiration';role().listeners.change();
  byId('files-input').files=[{name:'earlier.md',size:4,arrayBuffer:async()=>new TextEncoder().encode('Post').buffer}];
  await byId('files-input').listeners.change();
  assert.deepEqual(requests.filter(r=>r.url==='/api/upload').at(-1).data.files.map(e=>e.purpose),['inspiration']);
  byId('files-role').value='material';byId('files-role').listeners.change();
  // A kept file carries the kind of post to the library; facts take no author, an example the blog's.
  f.run("studio.draft.author='Avery';studio.draft.style='product-announcement'");
  byId('files-input').files=[{name:'kept.md',size:4,arrayBuffer:async()=>new TextEncoder().encode('Kept').buffer}];
  await byId('files-input').listeners.change();
  const keptUpload=requests.filter(r=>r.url==='/api/upload').at(-1).data;
  assert.equal(keptUpload.keep,true);assert.equal('author' in keptUpload,false,'facts written by others do not get the blog’s author');assert.equal(keptUpload.kind,'product-announcement');
  byId('files-role').value='inspiration';byId('files-role').listeners.change();
  byId('files-input').files=[{name:'example.md',size:4,arrayBuffer:async()=>new TextEncoder().encode('Ex').buffer}];
  await byId('files-input').listeners.change();
  assert.equal(requests.filter(r=>r.url==='/api/upload').at(-1).data.author,'Avery','an example of the kind of post takes the blog’s author');
  byId('files-role').value='material';byId('files-role').listeners.change();
  f.run("studio.draft.author='';studio.draft.style=''");
  // Unticked, Just this blog: the files added after it stay with the blog, out of the library.
  byId('files-keep').checked=false;byId('files-keep').listeners.change();
  byId('files-input').files=[{name:'more.md',size:4,arrayBuffer:async()=>new TextEncoder().encode('More').buffer}];
  await byId('files-input').listeners.change();
  assert.equal(requests.filter(r=>r.url==='/api/upload').at(-1).data.keep,false);
  assert.equal('author' in requests.filter(r=>r.url==='/api/upload').at(-1).data,false,'a file that stays with the blog carries no library fields');
  f.run("studio.draft.files.push({id:'s7',filename:'mine.md',state:'ready',chars:5,note:'',link:'',role:'material',kept:false});sWizard()");
  assert.ok(text().some(t=>/^5 characters · Just this blog$/.test(t)),'a file kept out of the library says so: '+text().join('|'));
  f.run("studio.draft.files=studio.draft.files.filter(file=>file.id!=='s7');sWizard()");
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
  assert.ok(text().some(t=>/Google Doc · 4,200 characters · All 3 tabs were read: “Overview”, “Messaging”, “FAQ”\. Link one tab/.test(t)),'with how much text it has and which tabs were read: '+text().join('|'));
  assert.equal(start().disabled,false,'a Doc with text can start the blog: the screen is not left busy');
  assert.equal(docAdd().disabled,false,'and another Doc can be added');
  byId('files-goal').value='A team post';byId('files-goal').listeners.input();
  byId('files-research-web').checked=true;byId('files-research-web').listeners.change();
  assert.ok(text().some(t=>/stops for the angles/.test(t)));
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const creation=requests.find(r=>r.url==='/api/run-create').data;
  assert.equal(creation.mode,'from-files');assert.deepEqual(creation.research_from,{documents:true,sites:[],web:true});assert.equal(creation.goal,'A team post');
  assert.deepEqual(creation.sources,['s1','s9'],'only files with text are pinned, once, the Google Doc among them');
  assert.equal(creation.title,'');assert.equal(creation.stop,'package');
  assert.equal(creation.point,false);assert.equal(creation.profile,'p1','Write as reaches the run');assert.equal(creation.revision,3,'My voice writes with the default voice\'s pinned revision');
  // I know the point: a title, the point and the reader; the run starts at the outline.
  f.run("studio.screen='new';studio.draft={...studio.options.settings.defaults,mode:'from-files',research:'supplied-only',stop:'package',files:[{id:'s1',filename:'notes.md',state:'ready',chars:1200,note:'',link:'',role:'material'}],web:false,keep:false,profile:'p1',tone:'',goal:'',title:'',audience:'',sources:[],minutes:'10',operation:'b'.repeat(32)};sWizard()");
  const how=()=>nodes().find(e=>e.attributes['aria-label']==='How to start');
  assert.deepEqual(how().children.filter(e=>e.tagName==='button').map(e=>e.textContent),['Find three angles','I know the point']);
  assert.equal(byId('files-title'),undefined,'the angles path asks for no title');
  await how().children.find(e=>e.textContent==='I know the point').listeners.click();
  assert.ok(byId('files-title')&&byId('files-point')&&byId('files-audience'),'the point path asks for the title, the point and the reader: '+text().join('|'));
  assert.equal(byId('files-goal'),undefined);
  assert.match(byId('files-point-hint').textContent,/For example: “/,'the point has an example of a specific point');
  assert.ok(byId('files-length'),'Length is on the files screen too');
  assert.equal(start().textContent,'Start writing');
  assert.ok(text().some(t=>/^Balanced: it stops for the outline and the handoff$/.test(t)),'no angles on the point path: '+text().join('|'));
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.ok(text().some(t=>/title, the point/.test(t)),'an empty point is refused on the page: '+text().join('|'));
  assert.equal(requests.filter(r=>r.url==='/api/run-create').length,1);
  byId('files-title').value='Announcing the gateway';byId('files-title').listeners.input();
  byId('files-point').value='It is generally available.';byId('files-point').listeners.input();
  byId('files-audience').value='Platform engineers';byId('files-audience').listeners.input();
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const pointed=requests.filter(r=>r.url==='/api/run-create').at(-1).data;
  assert.equal(pointed.point,true);assert.equal(pointed.revision,3);assert.equal(pointed.title,'Announcing the gateway');assert.equal(pointed.goal,'It is generally available.');assert.equal(pointed.audience,'Platform engineers');assert.equal(pointed.mode,'from-files');
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
  // What the author must supply before publishing is its own part of the aside, never in the writing.
  assert.ok(!text().includes('Needs you before publishing'),'no gaps, no heading');
  f.set('gapped',{...shown,gaps:['The confirmed release date.','A launch link.']});
  f.run("sGate(waiting,gapped)");
  const needs=nodes().find(e=>e.tagName==='h2'&&e.textContent==='Needs you before publishing');
  assert.ok(needs,'the gaps have their own heading: '+text().join('|'));
  assert.deepEqual(nodes().find(e=>e.className==='gap-items')?.children.map(e=>e.textContent),['The confirmed release date.','A launch link.']);
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
  const complete={id:'synthetic',title:'Synthetic blog',status:'complete',complete:true,next:null,approval:'page',expected:'version-3',enabled:false,directory:'/synthetic/articles/synthetic',seconds:600,engine:'codex',mode:'write',review_level:'step_by_step',decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},publication:null,stages:[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'approved'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'approved'},{stage:'package',label:'Handoff',path:'derived/blog-package.md',status:'approved'}]};
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
  // The Done card says whether Finish kept the blog in the team library, or why not.
  for(const [library,words] of [[{id:'kept',revision:1},'Kept in the team library, where the next blog can pick it as an example.'],[{reason:'it could not be saved here.'},'Not kept in the team library: it could not be saved here.']]){f.set('card',{...complete,library});f.run("studio.page=sPage(sDoneCard(card))");assert.ok(text().includes(words),words+': '+text().join('|'));}
  f.set('card',complete);f.run("sPage(sDoneCard(card))");assert.equal(text().some(t=>/team library/.test(t)),false,'nothing said without an outcome');
  // The final stop: the draft is the open document, the package is the handoff, the decision is Finish.
  const shown={id:'synthetic',title:'Synthetic blog',name:'blog-package.md',stage:'package',label:'Handoff',expected:'version-2',status:'draft',content:'# Handoff',notes:'',checks:[],previous:null,diff:[],bundle:[{stage:'draft',label:'Draft',content:'# The draft text'}]};
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
  const typed=sheet().find(e=>e.id==='delete-title'),hint=()=>sheet().find(e=>e.id==='delete-title-hint');
  assert.equal(hint().hidden,true,'no hint before anything is typed');
  typed.value='Synthetic';typed.listeners.input();assert.equal(confirm.disabled,true);
  assert.equal(hint().hidden,false,'a partial title says it is not the title yet');assert.equal(hint().textContent,'Not the title yet.');
  typed.value='  synthetic  BLOG ';typed.listeners.input();assert.equal(confirm.disabled,false,'case and spacing do not matter');assert.equal(hint().hidden,true);
  typed.value='“Synthetic” blog';typed.listeners.input();assert.equal(confirm.disabled,true,'added characters still do not match');
  typed.value='Synthetic blog';typed.listeners.input();assert.equal(confirm.disabled,false);
  assert.equal(typed.attributes?.['aria-describedby']??typed.getAttribute?.('aria-describedby'),'delete-title-hint','the input points at its hint');
  await confirm.listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/blog-delete').data,{id:'synthetic',expected:'version-3',title:'Synthetic blog'});
  assert.equal(f.get('sheet').hidden,true);
  assert.equal(f.get('title').textContent,'Blogs','from its own screens, a deleted blog goes to Blogs');
  // Deleted from Home, Home is drawn again without it, and says so.
  f.run("studio.screen='home';studio.listing=[found];sHome();sDeleteSheet(found)");
  {const typedHome=sheet().find(e=>e.id==='delete-title');typedHome.value='Synthetic blog';typedHome.listeners.input();
  await sheet().find(e=>e.textContent==='Delete Synthetic blog').listeners.click();}
  assert.equal(f.get('sheet').hidden,true);assert.equal(f.get('title').textContent,'Home','a blog deleted from Home stays on Home');
  assert.ok(!text().includes('Synthetic blog'),'Home is drawn again without it: '+text().join('|'));
  assert.ok(descendants(f.get('toasts')).some(e=>e.textContent==='Deleted Synthetic blog.'),descendants(f.get('toasts')).map(e=>e.textContent).join('|'));
  // A stored title with curly quotes deletes when typed with plain ones.
  f.run("sDeleteSheet({...found,title:'The \u201cquoted\u201d blog'})");
  const quoted=sheet().find(e=>e.id==='delete-title'),quotedConfirm=sheet().find(e=>e.textContent==='Delete The \u201cquoted\u201d blog');
  assert.equal(quotedConfirm.disabled,true);quoted.value='the "quoted" blog';quoted.listeners.input();assert.equal(quotedConfirm.disabled,false,'plain quotes match curly ones');
  f.run('sCloseSheet()');
  // Tools offers Delete for a saved blog, and not without one.
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
    if(url.startsWith('/api/styles'))return {styles:[],samples:[{id:'s1',name:'One',author:'Avery Quinn'},{id:'s2',name:'Two',author:'Avery Quinn'}],candidates:[],pending:[]};
    if(url==='/api/voice-links-preview')return data.purpose==='style-sample'?{...preview,author:data.author}:data.site?preview:mixed;
    if(url==='/api/voice-links-import'&&data.purpose==='style-sample')return {...result(true),author:data.author,purpose:'style-sample',results:result(true).results.map(({byline,mismatch,kept,...row})=>row),counts:{...result(true).counts,mismatch:0},next_step:'Next, learn or update a style from these examples.'};
    if(url==='/api/voice-links-import'){imports++;return imports===1?{...result(false),remaining:1,counts:{...result(false).counts,pending:1}}:result(data.keep.length>0);}
    return {items:[],total:0};});
  f.loadRunner();voicesOn(f);
  const sheet=()=>descendants(f.get('sheet')),find=label=>sheet().find(e=>e.textContent===label),byId=id=>sheet().find(e=>e.id===id),has=pattern=>sheet().some(e=>pattern.test(e.textContent));
  await f.run('sVoiceTools()');
  // Links to posts are one of Create a voice's sources.
  await find('Create a voice').listeners.click();assert.equal(f.get('sheet').children[0].children[0].textContent,'Create a voice');
  await find('Add links to posts').listeners.click();
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
  assert.ok(has(/kept as a sample/));assert.ok(has(/Voice learning reads up to twenty samples/));
  await find('Learn Avery Quinn’s voice').listeners.click();
  assert.equal(byId('learn-voice-name').value,'Avery Quinn');
  assert.deepEqual(JSON.parse(f.run('JSON.stringify(studio.voiceLearning.new.samples)')),['s1','s2']);
  assert.equal(sheet().filter(e=>e.tagName==='input'&&e.type==='checkbox'&&e.checked).length,2,'the imported samples are ticked for learning');
  assert.ok(requests.filter(r=>r.url.startsWith('/api/voice-links-')).every(r=>r.data.purpose==='voice-sample'),'voice links say they are voice samples');
  // Examples of a kind of writing: the same flow, named for the kind, with no byline check.
  requests.length=0;
  await f.run("sVoiceLinks({profiles:[],samples:[]},null,null,'style-sample')");
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Add links to examples');
  assert.equal(sheet().find(e=>e.tagName==='label'&&e.htmlFor==='voice-links-author').textContent,'What kind of writing is this?');
  assert.equal(byId('voice-links-author-hint').textContent,'For example, Product announcements.');
  const styleFile=byId('voice-links-file');styleFile.files=[{name:'avery-quinn-blog-links.txt',size:200,text:async()=>links}];await styleFile.listeners.change();
  assert.equal(byId('voice-links-author').value,'','a kind of writing is not named after the file');
  byId('voice-links-author').value='Product announcements';byId('voice-links-author').listeners.input();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(requests.find(r=>r.url==='/api/voice-links-preview').data.purpose,'style-sample');
  assert.equal(has(/names its author/),false,'no byline wording for examples');
  await find('Import 2 posts').listeners.click();
  assert.equal(requests.find(r=>r.url==='/api/voice-links-import').data.purpose,'style-sample');
  assert.equal(sheet().some(e=>/^Keep /.test(e.textContent)),false,'no byline keep for examples');
  await find('Learn a style from these').listeners.click();
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Create a style');
  assert.equal(byId('learn-style-name').value,'Product announcements');
  assert.deepEqual(sheet().filter(e=>e.type==='checkbox'&&e.checked).map(e=>e.value),['s1','s2'],'the imported examples are ticked');
}

// Add to the library: one sheet for files, links and a Google Doc with role, author and kind; a
// check first, then the add continues until every link is read; each post's own author groups
// the posts by byline, with rename, merge and set author; marking as samples is on by default
// and learning a group's voice still asks for permission.
async function libraryAddJourney(){
  const requests=[];let marked=false,renamed=false,adds=0;
  const preview={status:'ready',role:'example',author:'*each',kind:'product-announcement',kind_name:'Product announcement',items:[{key:'post.html',kind:'file',title:'An earlier post',filename:'post.html',state:'ready',chars:1200,note:'',bylines:['Avery Quinn']},{key:'https://blog.example/team/a/',kind:'link',url:'https://blog.example/team/a/',site:'blog.example/team/',state:'new',chars:null,bylines:[],note:''},{key:'https://blog.example/team/b/',kind:'link',url:'https://blog.example/team/b/',site:'blog.example/team/',title:'B',state:'in-library',chars:null,bylines:['Sam Rivera'],note:''}],sites:[{site:'blog.example',scope:'https://blog.example/team/',shown:'blog.example/team/',links:2}],in_library:1,to_fetch:2,duplicates:0,comments:0,upgraded:0,unusable:0,skipped:[],expected:'check-1',next_step:'Check the items.'};
  const item=(id,extra)=>({id,kind:'link',url:'https://blog.example/team/'+id+'/',site:'blog.example/team/',status:'imported',title:id.toUpperCase(),author:null,bylines:[],role:'example',sample:false,revision:1,text:true,...extra});
  const result=()=>{const sam=renamed?'Samantha Rivera':'Sam Rivera',groups=[{author:'Darin Zook',ids:['a','f'],samples:marked?['a','f']:[],learnable:marked?['a','f']:[],count:2},{author:sam,ids:['b'],samples:marked?['b']:[],learnable:marked?['b']:[],count:1}];
    return {operation:'x',state:'saved',role:'example',author:'*each',kind:'product-announcement',kind_name:'Product announcement',items:[{id:'f',kind:'file',filename:'post.html',status:'imported',title:'An earlier post',author:'Darin Zook',bylines:['Darin Zook'],role:'example',sample:marked,revision:1,text:true},item('a',{author:'Darin Zook',sample:marked}),item('b',{author:sam,status:'in-library',sample:marked}),item('co',{bylines:['Avery Quinn','Jordan Lee']})],counts:{imported:3,'in-library':1,failed:0,pending:0,samples:marked?3:0},remaining:0,groups,held:[{id:'co',title:'CO',url:'https://blog.example/team/co/',bylines:['Avery Quinn','Jordan Lee'],reason:'Several bylines: Avery Quinn, Jordan Lee'}],next_step:'Mark the posts as voice samples.',sharing:'local-only',sharing_message:'Saved in this workspace; no Team Hub selected.',receipts:[]};};
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url.startsWith('/api/styles'))return {styles:[{id:'product-announcement',name:'Product announcement',kind:'seed',status:'confirmed',revision:1,summary:''},{id:'old',name:'Old',kind:'learned',status:'retired',revision:1,summary:''}],samples:[],candidates:[],pending:[]};
    if(url.startsWith('/api/voices'))return {profiles:[],samples:[{id:'a',name:'A',author:'Darin Zook'},{id:'f',name:'An earlier post',author:'Darin Zook'}],candidates:[],pending:[]};
    if(url==='/api/library-add-preview')return preview;
    if(url==='/api/library-add'){adds++;return adds===1?{...result(),remaining:1,state:'importing',counts:{...result().counts,pending:1}}:result();}
    if(url==='/api/library-add-author'){renamed=true;return result();}
    if(url==='/api/library-add-samples'){marked=true;return result();}
    return {items:[],total:0};});
  f.loadRunner();voicesOn(f);
  const sheet=()=>descendants(f.get('sheet')),find=label=>sheet().find(e=>e.textContent===label),byId=id=>sheet().find(e=>e.id===id),has=pattern=>sheet().some(e=>pattern.test(e.textContent));
  await f.run('sLibraryAdd()');
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Add to the library');
  const files=byId('library-add-files');assert.equal(files.multiple,true);assert.match(files.accept,/\.pdf/);
  assert.ok(byId('library-add-links')&&byId('library-add-links-file'),'links can be pasted or chosen as a file');assert.ok(byId('library-add-google'),'and a Google Doc link added');
  assert.equal(byId('library-add-who').value,'*each','each post’s own author by default');
  assert.equal(byId('library-add-author'),undefined,'so no name field shows');
  assert.deepEqual(byId('library-add-who').children.map(o=>[o.value,o.textContent]),[['*each','Each post’s own author'],['named','One author'],['','No author']]);
  byId('library-add-who').value='named';await byId('library-add-who').listeners.change();
  assert.ok(byId('library-add-author'),'one typed author remains a choice');
  // The larger sources sit under More ways to add: a whole blog or site, and one file to tag or start a blog.
  assert.ok(find('More ways to add'));
  await find('Import a blog or site').listeners.click();assert.equal(f.get('import-dialog').open,true,'Import old blogs is reached from Add to library');assert.equal(f.get('sheet').hidden,true);
  f.get('import-dialog').open=false;await f.run('sLibraryAdd()');
  await find('Upload one file').listeners.click();assert.equal(f.get('upload-dialog').open,true,'Upload is reached from Add to library');
  f.get('upload-dialog').open=false;await f.run('sLibraryAdd()');
  assert.deepEqual(byId('library-add-kind').children.map(o=>o.textContent),['No particular kind of post','Product announcement (starter)'],'retired kinds are left out');
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.ok(has(/Choose files, paste links/),'nothing chosen is refused on the page');assert.equal(requests.some(r=>r.url==='/api/library-add-preview'),false);
  files.files=[{name:'post.html',size:20,arrayBuffer:async()=>new TextEncoder().encode('<p>By Avery</p>').buffer}];await files.listeners.change();
  assert.ok(has(/1 chosen: post\.html/));
  byId('library-add-links').value='https://blog.example/team/a/\nhttps://blog.example/team/b/';byId('library-add-links').listeners.input();
  const role=sheet().find(e=>e.attributes['aria-label']==='Use these as');await role.children.find(e=>e.textContent==='Example of the kind of post').listeners.click();
  byId('library-add-who').value='*each';await byId('library-add-who').listeners.change();
  assert.equal(byId('library-add-author'),undefined,'each post’s own author needs no name');
  byId('library-add-kind').value='product-announcement';byId('library-add-kind').listeners.change();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const checked=requests.find(r=>r.url==='/api/library-add-preview').data;
  assert.deepEqual(checked.files.map(e=>e.filename),['post.html']);assert.equal(checked.role,'example');assert.equal(checked.author,'*each');assert.equal(checked.kind,'product-announcement');assert.match(checked.links,/team\/b\//);
  assert.ok(find('3 items'));assert.ok(has(/Example of the kind of post · Each post’s own author · Product announcement/));
  assert.ok(has(/1,200 characters · byline Avery Quinn/),'a file shows its size and byline');assert.ok(has(/New · fetched from blog\.example\/team\//));assert.ok(has(/Already in the library · byline Sam Rivera/));
  assert.ok(has(/1 already in the library/));assert.ok(has(/2 new pages are fetched once from blog\.example\/team\//));
  assert.equal(requests.some(r=>r.url==='/api/library-add'),false,'checking adds nothing');
  await find('Add 3 items').listeners.click();
  const sent=requests.filter(r=>r.url==='/api/library-add');assert.equal(sent.length,2,'adding continues until every link is read');
  assert.equal(sent[0].data.expected,'check-1');assert.equal(sent[0].data.operation,sent[1].data.operation);assert.equal(sent[0].data.author,'*each');assert.equal(sent[0].data.kind,'product-announcement');
  assert.ok(find('3 added · 1 already there · 0 failed'));
  assert.ok(find('Darin Zook · 2 posts'));assert.ok(find('Sam Rivera · 1 post'),'posts are grouped by author');
  assert.ok(has(/Several bylines: Avery Quinn, Jordan Lee/),'a co-authored post is held');
  assert.ok(find('Create voices for every author'),'the result offers a voice for every author');
  assert.equal(byId('library-add-mark').checked,true,'marking as samples is on by default');
  assert.equal(find('Learn Darin Zook’s voice'),undefined,'nothing to learn from until the posts are samples');
  const operation=sent[0].data.operation;
  byId('library-add-rename-1').value='Samantha Rivera';byId('library-add-rename-1').listeners.input();await sheet().filter(e=>e.textContent==='Rename')[1].listeners.click();
  assert.deepEqual(requests.filter(r=>r.url==='/api/library-add-author').at(-1).data,{operation,ids:['b'],author:'Samantha Rivera'});
  assert.ok(find('Samantha Rivera · 1 post'),'the group is renamed');
  byId('library-add-merge-1').value='Darin Zook';byId('library-add-merge-1').listeners.change();await sheet().filter(e=>e.textContent==='Merge')[1].listeners.click();
  assert.deepEqual(requests.filter(r=>r.url==='/api/library-add-author').at(-1).data,{operation,ids:['b'],author:'Darin Zook'},'merging gives the group the other author');
  byId('library-add-held-co').value='Casey Park';byId('library-add-held-co').listeners.input();await find('Set author').listeners.click();
  assert.deepEqual(requests.filter(r=>r.url==='/api/library-add-author').at(-1).data,{operation,ids:['co'],author:'Casey Park'});
  await find('Mark as samples').listeners.click();
  assert.deepEqual(requests.filter(r=>r.url==='/api/library-add-samples').at(-1).data,{operation});
  assert.ok(has(/Added · by Darin Zook · voice sample/));
  await find('Learn Darin Zook’s voice').listeners.click();
  assert.equal(byId('learn-voice-name').value,'Darin Zook');
  assert.deepEqual(sheet().filter(e=>e.type==='checkbox'&&e.value&&e.checked).map(e=>e.value),['a','f'],'the group’s samples are ticked');
  assert.ok(!byId('learn-voice-permission').checked,'learning still asks for permission');
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(requests.some(r=>r.url==='/api/tool-action'),false,'no learning job without the confirmation');
  assert.ok(has(/Confirm sample permissions/));
  // A failed link is fetched again only when asked, with the same operation.
  assert.equal(find('Try the failed links again'),undefined,'no retry without a failure');
  f.run("studio.libraryAdd.result={...studio.libraryAdd.result,counts:{...studio.libraryAdd.result.counts,failed:1},items:[...studio.libraryAdd.result.items,{kind:'link',url:'https://blog.example/team/gone/',status:'failed',reason:'Source returned HTTP 404.'}]};sLibraryAddResult(studio.libraryAdd)");
  assert.ok(has(/Not added: Source returned HTTP 404\./));
  await find('Try the failed links again').listeners.click();
  const retried=requests.filter(r=>r.url==='/api/library-add').at(-1).data;
  assert.equal(retried.retry,true);assert.equal(retried.operation,operation,'the same operation');assert.equal(retried.expected,'check-1');
}

// The library screen: filters for role, kind of post and author reach the request; rows can be
// ticked; the selection learns a style or a voice (marked as samples first, asking whose when
// nobody is named) or starts a blog from my files with the items ticked as examples.
async function libraryScreen(){
  const requests=[];let askWho=false;
  const rows=[{id:'a',title:'A post',author:'Avery',status:'ready',revision:1,purposes:['reference','inspiration'],role:'example',kind_name:'Product announcement',library:{kind:'product-announcement',origin_kind:'written-here',article:'blog-1'},analysis:{status:'ready'},historical:false,collection_names:[]},{id:'b',title:'B notes',author:'',status:'ready',revision:1,purposes:['reference'],role:'facts',kind_name:null,library:{origin_kind:'upload'},analysis:{},historical:false,collection_names:[]}];
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url.startsWith('/api/library?'))return {items:rows,total:2,kinds:[{id:'product-announcement',name:'Product announcement'},{id:'how-to',name:'How-to'}]};
    if(url==='/api/library-selection'){if(data.action==='voice-learn'&&askWho&&!data.author)return {__http:400,error:'Say whose writing these items are before learning a voice.'};return data.action==='blog'?{action:'blog',files:[{id:'a',filename:'A post',state:'ready',chars:900,role:'inspiration',library:true},{id:'b',filename:'B notes',state:'ready',chars:300,role:'inspiration',library:true}]}:{action:data.action,candidates:[{id:'a',name:'A post',author:'Avery'},{id:'b',name:'B notes',author:''}],author:data.action==='voice-learn'?data.author||'Avery':null,left_out:[],skipped:[{id:'c',name:'Scan',reason:'It has no readable text yet.'}]};}
    if(url==='/api/tool-action')return {id:'j'.repeat(32),kind:data.kind,status:'queued',metadata:{},attempts:0};
    if(url.startsWith('/api/styles'))return {styles:[],samples:[],candidates:[{id:'a',name:'A post',author:'Avery'},{id:'z',name:'Other',author:''}],pending:[]};
    if(url.startsWith('/api/voices'))return {profiles:[],samples:[{id:'a',name:'A post',author:'Avery'},{id:'b',name:'B notes',author:'Avery'}],candidates:[],pending:[]};
    if(url==='/api/run-options')return {settings:{defaults:{engine:'codex',seconds:600,research:'supplied-only',stop:'package',tone:'Clear',author:''},review_level:'balanced'},sources:[],profiles:[],default_voice:null,agents:{codex:true},styles:[]};
    return {items:[],total:0};});
  f.loadRunner();voicesOn(f);
  f.run("view='library'");await f.run('load()');
  for(const name of ['role','kind','author'])assert.equal(f.get('library-'+name+'-filter').hidden,false,name+' filter shows on the library');
  assert.deepEqual(f.get('library-kind').children.map(o=>o.textContent),['Any kind','Product announcement','How-to'],'the kinds come from the view');
  const results=()=>descendants(f.get('results'));
  const picks=results().filter(e=>e.type==='checkbox');assert.equal(picks.length,2,'each row can be ticked');
  assert.ok(results().some(e=>e.textContent==='Example · Product announcement'),'a row says its role and kind');
  assert.equal(f.get('library-selection').hidden,true);
  picks[0].checked=true;picks[0].listeners.change();picks[1].checked=true;picks[1].listeners.change();
  assert.equal(f.get('library-selection').hidden,false);assert.equal(f.get('library-selection-count').textContent,'2 selected');
  f.get('library-role').value='example';f.get('library-kind').value='product-announcement';f.get('library-author').value='Avery';await f.run('load()');
  const asked=requests.filter(r=>r.url.startsWith('/api/library?')).at(-1).url;
  assert.match(asked,/role=example/);assert.match(asked,/kind=product-announcement/);assert.match(asked,/author=Avery/);
  assert.equal(f.get('library-selection-count').textContent,'2 selected','the selection survives a reload');
  const sheet=()=>descendants(f.get('sheet')),byId=id=>sheet().find(e=>e.id===id);
  await f.run("sLibrarySelection('style-learn',[...librarySelection.values()])");
  assert.deepEqual(requests.filter(r=>r.url==='/api/library-selection').at(-1).data,{action:'style-learn',ids:['a','b']});
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Create a style');
  assert.deepEqual(sheet().filter(e=>e.type==='checkbox'&&e.checked).map(e=>e.value),['a','b'],'the items are ticked as examples');
  assert.equal(requests.some(r=>r.url==='/api/tool-action'),false,'choosing marks nothing');
  assert.equal(sheet().some(e=>e.attributes?.['aria-label']==='Use A post as an example'),false,'a ticked item is not offered again below');
  assert.ok(sheet().some(e=>e.attributes?.['aria-label']==='Use Other as an example'),'other sources still are');
  assert.ok(sheet().some(e=>e.textContent==='Scan has no readable text yet, so it is skipped.'),'an item without text is named, not a stop');
  byId('learn-style-name').value='Launch posts';byId('learn-style-name').listeners.input();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(requests.some(r=>r.url==='/api/tool-action'),false,'nothing before the permission is ticked');
  byId('learn-style-permission').checked=true;await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const learned=requests.filter(r=>r.url==='/api/tool-action').at(-1).data;
  assert.deepEqual([learned.kind,learned.samples,learned.mark,learned.confirmed],['style-learn',['a','b'],true,true],'confirming the learning marks the chosen items');
  await f.run("sLibrarySelection('voice-learn',[...librarySelection.values()])");
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Create a voice');
  assert.equal(byId('learn-voice-name').value,'Avery','the author comes from the items');
  askWho=true;await f.run("sLibrarySelection('voice-learn',[...librarySelection.values()])");
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Learn a voice from these','without an author the page asks');
  byId('library-voice-author').value='Casey Park';byId('library-voice-author').listeners.input();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.deepEqual(requests.filter(r=>r.url==='/api/library-selection').at(-1).data,{action:'voice-learn',ids:['a','b'],author:'Casey Park'});
  assert.equal(byId('learn-voice-name').value,'Casey Park');
  await f.run("sLibrarySelection('blog',[...librarySelection.values()])");
  // A blog from library items starts on the desk's start, with the items as its sources.
  assert.equal(f.run('studio.screen'),'desk-start');
  assert.deepEqual(JSON.parse(f.run('JSON.stringify(studio.deskStart.files.map(file=>[file.id,file.role,file.library]))')),[['a','inspiration',true],['b','inspiration',true]],'the items are the blog’s files, each an example');
  f.run("studio.deskStart.kind='';studio.deskStart.step=1");await f.run('sDeskStart()');
  const nodes=()=>descendants(f.get('studio-page'));
  assert.equal(nodes().find(e=>e.id==='files-role-a').value,'inspiration');
  assert.ok(nodes().some(e=>/900 characters/.test(e.textContent)),'with how much text each has');
  assert.equal(f.run('librarySelection.size'),0,'the selection is used up');
  // A row only the Team Hub holds goes with its location, so the server checks it out first.
  // Without edit access the rows cannot be ticked and nothing can be added.
  f.run("access.actions.edit=false");await f.run("sLegacy('library')");
  assert.equal(f.get('title').textContent,'Team library');assert.equal(f.get('editorial-screen').hidden,false);
  assert.equal(results().filter(e=>e.type==='checkbox').length,0,'no checkboxes without edit access');
  const add=()=>f.get('actions').children.find(e=>e.textContent==='Add to library');
  assert.equal(add().disabled,true,'and no Add to library');
  f.run("access.actions.edit=true");await f.run('load()');assert.equal(add().disabled,false);assert.equal(add().className,'button button-filled','the library’s one primary action');
  // A voice-sample-only item says so, never Facts.
  rows.push({...rows[1],id:'v',title:'Only a sample',role:'voice-sample',purposes:['voice-sample']});await f.run('load()');
  assert.ok(results().some(e=>e.textContent==='Voice sample'),'a voice sample is not listed as facts: '+results().map(e=>e.textContent).join('|'));
  rows.pop();
  rows.push({...rows[0],id:'h',title:'Shared post',location:'hub'});await f.run('load()');
  const shared=results().find(e=>e.attributes?.['aria-label']==='Select Shared post');shared.checked=true;shared.listeners.change();
  await f.run("sLibrarySelection('blog',[...librarySelection.values()])");
  assert.deepEqual(requests.filter(r=>r.url==='/api/library-selection').at(-1).data.ids,[{id:'h',location:'hub'}]);
}

// From the library: a learned kind of post pre-ticks its samples (up to eight, newest first)
// as examples and a starter none; the picker's filters reach the request; a picked item keeps
// its library role for this blog only and goes with the run as `library`, not as a source.
async function libraryPicker(){
  const requests=[],defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''};
  const sampleIds=Array.from({length:9},(_,n)=>'s'+(n+1));
  const options={settings:{defaults,review_level:'balanced'},sources:sampleIds.map(id=>({id,name:'Sample '+id,status:id==='s9'?'pending':'ready'})).concat([{id:'lib1',name:'Launch notes',status:'ready'}]),profiles:[],default_voice:null,agents:{codex:true},styles:[{id:'product-announcement',name:'Product announcement',kind:'seed',revision:1,status:'confirmed',sample_ids:[]},{id:'field-notes',name:'Field notes',kind:'learned',revision:2,status:'confirmed',sample_ids:sampleIds}]};
  const run={id:'created',title:'A synthetic blog',status:'queued',next:'outline',approval:'page',expected:'r1',enabled:true,directory:'/synthetic',seconds:600,engine:'codex',decisions:[],brief:{goal:'Explain',audience:'Authors'},stages:[]};
  const f=fixture((url,o)=>{const data=o?.body?JSON.parse(o.body):null;requests.push({url,data});
    if(url==='/api/run-options')return options;
    if(url.startsWith('/api/library?'))return {items:[{id:'hub1',title:'Shared notes',author:'Sam',status:'ready',role:'facts',kind_name:null,purposes:['reference'],library:{origin_kind:'upload'},location:'hub'},{id:'lib1',title:'Launch notes',author:'Avery',status:'ready',role:'facts',kind_name:'Product announcement',purposes:['reference'],library:{origin_kind:'upload',kind:'product-announcement'}},{id:'s2',title:'Sample s2',author:'Avery',status:'ready',role:'example',kind_name:'Field notes',purposes:['reference','inspiration','style-sample'],library:{}}],total:2,kinds:[]};
    if(url==='/api/run-create'||url.startsWith('/api/run?'))return run;
    return {items:[],total:0};});
  f.loadRunner();
  const nodes=()=>descendants(f.get('studio-page')),byId=id=>nodes().find(e=>e.id===id),texts=()=>nodes().map(e=>e.textContent);
  const choose=(id,value)=>{const select=byId(id);select.value=value;select.listeners.change();};
  const fill=()=>{for(const [id,value] of [['new-title','A synthetic blog'],['new-goal','Explain'],['new-audience','Authors']]){byId(id).value=value;byId(id).listeners.input();}};
  const submit=()=>nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const files=()=>JSON.parse(f.run('JSON.stringify((studio.draft.files||[]).map(file=>[file.id,file.role,!!file.library]))'));
  await f.run("newBlog('',null,'write')");fill();
  choose('new-style','field-notes');
  assert.deepEqual(files().map(([id])=>id),['s9','s8','s7','s6','s5','s4','s3','s2'],'a learned kind of post pre-ticks its samples: up to eight, newest first');
  assert.ok(files().every(([,role,library])=>role==='inspiration'&&library),'each as an example from the library');
  choose('new-style','product-announcement');assert.deepEqual(files(),[],'a starter pre-ticks nothing');
  choose('new-style','field-notes');assert.equal(files().length,8);
  await submit();
  assert.ok(texts().some(t=>t==='Sample s8'),'the second step lists them: '+texts().join('|'));
  assert.ok(texts().some(t=>t==='From the library'),'as library items');
  assert.ok(texts().some(t=>/needs text, so it is not read/.test(t)),'a sample without text says so');
  assert.equal(byId('files-role-s8').value,'inspiration');
  await nodes().find(e=>e.attributes['aria-label']==='Remove Sample s8').listeners.click();
  assert.equal(files().length,7,'unticking removes it');assert.equal(files().some(([id])=>id==='s8'),false);
  const sheet=()=>descendants(f.get('sheet')),inSheet=id=>sheet().find(e=>e.id===id);
  await nodes().find(e=>e.textContent==='From the library'&&e.tagName==='button').listeners.click();
  assert.equal(f.get('sheet').children[0].children[0].textContent,'From the library');
  assert.ok(inSheet('pick-role')&&inSheet('pick-kind')&&inSheet('pick-author')&&inSheet('pick-query'),'role, kind and author filters and a search box');
  assert.deepEqual(inSheet('pick-kind').children.map(o=>o.textContent),['Any kind','Product announcement','Field notes']);
  inSheet('pick-role').value='facts';inSheet('pick-role').listeners.change();inSheet('pick-author').value='Avery';inSheet('pick-author').listeners.input();inSheet('pick-query').value='launch';inSheet('pick-query').listeners.input();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const asked=requests.filter(r=>r.url.startsWith('/api/library?')).at(-1).url;
  assert.match(asked,/role=facts/);assert.match(asked,/author=Avery/);assert.match(asked,/query=launch/);
  assert.equal(inSheet('pick-s2'),undefined,'an item already among the files is not offered again');
  const pick=inSheet('pick-lib1');pick.checked=true;pick.listeners.change();
  assert.ok(sheet().some(e=>e.textContent==='Launch notes')&&sheet().some(e=>/Avery · facts · Product announcement/.test(e.textContent)),'each item shows its title, author, role and kind: '+sheet().map(e=>e.textContent).join('|'));
  const hubPick=inSheet('pick-hub1');hubPick.checked=true;hubPick.listeners.change();
  await sheet().find(e=>e.textContent==='Add 2 to this blog').listeners.click();
  assert.equal(f.get('sheet').hidden,true);
  assert.deepEqual(files().find(([id])=>id==='lib1'),['lib1','material',true],'facts in the library are facts here');
  byId('files-role-lib1').value='inspiration';await byId('files-role-lib1').listeners.change();
  assert.equal(requests.some(r=>r.url==='/api/source-role'),false,'a library item changes its role for this blog only');
  assert.ok(texts().some(t=>/stops for/.test(t)),'the stops line follows');
  await submit();
  const sent=requests.filter(r=>r.url==='/api/run-create').at(-1).data;
  assert.deepEqual(sent.library,[...['s7','s6','s5','s4','s3','s2'].map(id=>({id,role:'example'})),{id:'hub1',role:'facts',location:'hub'},{id:'lib1',role:'example'}],'library items with text go with their roles for this blog, a Team Hub one with its location');
  assert.deepEqual(sent.sources,[],'and not as plain sources');assert.equal(sent.style,'field-notes');
}

// Write as and Kind of post on the first step: what each choice sends, for a new blog and for
// a manuscript, and Learn a new voice coming back to the wizard with the new voice chosen.
async function wizardVoiceAndKind(){
  const requests=[],defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''};
  const styles=[{id:'product-announcement',name:'Product announcement',summary:'Lead with what is new.',kind:'seed',revision:1,status:'confirmed'},{id:'field-notes',name:'Field notes',summary:'',kind:'learned',revision:1,status:'provisional'},{id:'old-notes',name:'Old notes',summary:'',kind:'learned',revision:2,status:'retired'}];
  const mine={scope:'personal',profile:'mine',name:'Synthetic Author',revision:2,status:'confirmed'};
  let options={settings:{defaults},sources:[],agents:{codex:true},default_voice:mine,profiles:[{id:'mine',name:'Synthetic Author',status:'confirmed'},{id:'guest',name:'Guest Writer',status:'provisional'}],styles};
  const run={id:'created',title:'A synthetic blog',status:'queued',next:'outline',approval:'page',expected:'r1',enabled:true,directory:'/synthetic',seconds:600,engine:'codex',decisions:[],brief:{goal:'Explain',audience:'Authors'},stages:[]};
  const f=fixture((url,o)=>{const data=o?.body?JSON.parse(o.body):null;requests.push({url,data});
    if(url==='/api/run-options')return options;
    if(url==='/api/run-create'||url.startsWith('/api/run?'))return run;
    if(url.startsWith('/api/voices'))return {profiles:options.profiles.map(p=>({...p,revision:1})),samples:[],candidates:[],pending:[]};
    if(url.startsWith('/api/styles'))return {styles,samples:[],candidates:[],pending:[]};
    if(url==='/api/tool-action'&&data.action==='job-apply')return {profile:'learned',revision:1,status:'provisional',receipts:[]};
    if(url==='/api/tool-action'&&data.action==='profile-save')return {profile:data.profile||'written',revision:2,status:'provisional',receipts:[]};
    if(url.startsWith('/api/article?'))return {title:'Uploaded draft',record:{writing_preferences:{audience:'Editors'},...(url.includes('styled')?{style:{style_id:'product-announcement',revision:1}}:{})},view:{}};
    return {items:[],total:0};});
  f.loadRunner();voicesOn(f);
  const nodes=()=>descendants(f.get('studio-page')),byId=id=>nodes().find(e=>e.id===id),texts=select=>select.children.map(o=>o.textContent);
  const chosen=id=>{const select=byId(id);return select.children.find(o=>o.value===select.value)?.textContent;};
  const choose=(id,text)=>{const select=byId(id),option=select.children.find(o=>o.textContent===text);assert.ok(option,text+' in '+texts(select).join('|'));select.value=option.value;select.listeners.change();};
  const fill=()=>{for(const [id,value] of [['new-title','A synthetic blog'],['new-goal','Explain'],['new-audience','Authors']]){byId(id).value=value;byId(id).listeners.input();}};
  const submit=()=>nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const start=async()=>{const before=requests.filter(r=>r.url==='/api/run-create').length;await submit();await submit();const sent=requests.filter(r=>r.url==='/api/run-create');assert.equal(sent.length,before+1,'one blog started');return sent.at(-1).data;};
  await f.run("newBlog('',null,'write')");fill();
  assert.ok(f.get('actions').children.some(e=>e.textContent==='Tools'));assert.equal(f.get('actions').children.some(e=>e.textContent==='More tools'),false,'tools are not hidden under More tools');
  // The first step: Write as after the audience, Kind of post beside it, each with its label and hint.
  const ids=nodes().filter(e=>e.id).map(e=>e.id);
  assert.ok(ids.indexOf('new-profile')>ids.indexOf('new-audience'),'Write as comes after the audience: '+ids.join('|'));
  assert.ok(ids.indexOf('new-style')>ids.indexOf('new-profile'),'Kind of post is beside Write as');
  assert.equal(nodes().find(e=>e.tagName==='label'&&e.htmlFor==='new-profile').textContent,'Write as');
  assert.equal(nodes().find(e=>e.tagName==='label'&&e.htmlFor==='new-style').textContent,'Kind of post');
  assert.equal(byId('new-style').attributes['aria-describedby'],'new-style-hint');
  assert.match(byId('new-style-hint').textContent,/shape of the piece/);assert.match(byId('new-style-hint').textContent,/voice is how it sounds/);
  assert.equal(byId('new-profile').attributes['aria-describedby'],'new-profile-hint');
  assert.deepEqual(texts(byId('new-profile')),['My voice — Synthetic Author · confirmed','Guest Writer · provisional','No particular voice (use the described tone)','Learn a new voice…']);
  assert.equal(chosen('new-profile'),'My voice — Synthetic Author · confirmed','the default voice is chosen by default');
  assert.deepEqual(texts(byId('new-style')),['No particular kind of post','Product announcement (starter)','Field notes · provisional'],'retired kinds are left out');
  // Length sits beside Kind of post: the style's own by default.
  assert.ok(ids.indexOf('new-length')>ids.indexOf('new-style'),'Length is beside Kind of post');
  assert.equal(nodes().find(e=>e.tagName==='label'&&e.htmlFor==='new-length').textContent,'Length');
  assert.deepEqual(texts(byId('new-length')),['The usual length','Short (about half)','In depth (about twice)'],'Length names no style or capability that may not apply');
  assert.equal(chosen('new-length'),'The usual length');
  assert.equal(byId('new-length-hint').textContent,'For the kind of post, or for a post like this one. In depth gives each main point a worked example or proof point from your material.');
  // Step two keeps tone, author and brand, with the tone as a nudge.
  await submit();
  assert.ok(nodes().some(e=>e.textContent==='Tone, author and brand'));
  assert.equal(byId('new-tone-hint').textContent,'With a voice chosen, the usual tone is left out; a tone you type here is added as a nudge.');
  assert.equal(nodes().some(e=>e.id==='new-profile'),false,'the voice is chosen once, on the first step');
  await submit();
  let sent=requests.filter(r=>r.url==='/api/run-create').at(-1).data;
  assert.equal(sent.profile,'mine','My voice sends the personal default voice');assert.equal(sent.revision,2,'at the revision the default pins');assert.equal(sent.tone,'Clear');assert.equal(sent.style,'');
  // A team default voice has no local profile: nothing is sent, and the server applies it.
  options={...options,default_voice:{scope:'team',profile:null,name:'Team Voice',revision:'d'.repeat(32),status:'confirmed'}};
  await f.run("newBlog('',null,'write')");fill();
  assert.equal(chosen('new-profile'),'My voice — Team Voice · confirmed');
  sent=await start();assert.equal(Object.hasOwn(sent,'profile'),false,'a team default voice sends no profile');assert.equal(Object.hasOwn(sent,'revision'),false,'nor a revision');
  options={...options,default_voice:mine};
  // A chosen voice and kind are sent as chosen.
  await f.run("newBlog('',null,'write')");fill();choose('new-profile','Guest Writer · provisional');choose('new-style','Field notes · provisional');
  sent=await start();assert.equal(sent.profile,'guest');assert.equal(sent.style,'field-notes');assert.equal(Object.hasOwn(sent,'length'),false,'the style’s own length sends nothing');
  await f.run("newBlog('',null,'write')");fill();choose('new-length','In depth (about twice)');
  sent=await start();assert.equal(sent.length,'deep','a chosen length is sent');
  // Length appears only where an outline or a draft is written new.
  for(const mode of ['outline','from-outline']){await f.run("newBlog('',null,'"+mode+"')");assert.ok(byId('new-length'),'Length is offered for '+mode);}
  for(const mode of ['ideas','revise','review']){await f.run("newBlog('',null,'"+mode+"')");assert.equal(byId('new-length'),undefined,'no Length for '+mode);}
  // A length chosen for new writing is not sent once the flow writes nothing new.
  await f.run("newBlog('',null,'write')");fill();choose('new-length','Short (about half)');f.run("studio.draft.mode='review';studio.draft.stop='review';studio.draft.manuscript='m1';sWizard()");
  assert.equal(byId('new-length'),undefined,'switching to review hides Length');
  sent=await start();assert.equal(Object.hasOwn(sent,'length'),false,'a review sends no length');
  await f.run("newBlog('',null,'write')");fill();choose('new-profile','No particular voice (use the described tone)');
  sent=await start();assert.equal(sent.profile,'','no particular voice uses the described tone');
  // With no default voice, nothing is left to a default that may be missing or in conflict.
  options={...options,default_voice:null};
  await f.run("newBlog('',null,'write')");fill();
  assert.deepEqual(texts(byId('new-profile')),['Synthetic Author · confirmed','Guest Writer · provisional','No particular voice (use the described tone)','Learn a new voice…']);
  assert.equal(chosen('new-profile'),'No particular voice (use the described tone)');
  sent=await start();assert.equal(sent.profile,'');
  // A manuscript keeps its own voice unless another is picked.
  options={...options,default_voice:mine};
  await f.run("newBlog('existing')");fill();
  assert.deepEqual(texts(byId('new-profile')),['Keep this blog’s voice','Synthetic Author · confirmed','Guest Writer · provisional','Learn a new voice…'],'a saved blog keeps its voice; an empty choice would be ignored');
  sent=await start();assert.equal(sent.id,'existing');assert.equal(Object.hasOwn(sent,'profile'),false,'keeping the blog’s voice sends no profile');
  // The interview's outline starts a draft of the same saved blog: its voice is kept too.
  await f.run("newBlog('existing',null,'from-outline')");fill();byId('new-outline').value='## One';byId('new-outline').listeners.input();
  assert.deepEqual(texts(byId('new-profile')),['Keep this blog’s voice','Synthetic Author · confirmed','Guest Writer · provisional','Learn a new voice…']);
  sent=await start();assert.equal(sent.id,'existing');assert.equal(Object.hasOwn(sent,'profile'),false);
  await f.run("newBlog('existing')");fill();choose('new-profile','Guest Writer · provisional');
  sent=await start();assert.equal(sent.profile,'guest');
  // A saved blog with a kind of post keeps it unless another is picked; an empty one keeps it.
  await f.run("newBlog('styled')");fill();
  assert.deepEqual(texts(byId('new-style')),['Keep this blog’s kind of post — Product announcement','Product announcement (starter)','Field notes · provisional'],'a saved blog ignores an empty kind of post');
  assert.equal(chosen('new-style'),'Keep this blog’s kind of post — Product announcement');
  sent=await start();assert.equal(sent.id,'styled');assert.equal(sent.style,'','keeping the blog’s kind of post sends none');
  await f.run("newBlog('existing')");fill();
  assert.equal(texts(byId('new-style'))[0],'No particular kind of post','a saved blog without one offers none');
  // Learn a new voice opens Voices and styles, and an applied voice comes back chosen.
  await f.run("newBlog('',null,'write')");fill();choose('new-profile','Learn a new voice…');
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(f.get('sheet').hidden,false);assert.equal(f.get('sheet').children[0].children[0].textContent,'Voices and styles');
  assert.equal(chosen('new-profile'),'My voice — Synthetic Author · confirmed','the choice is unchanged until a voice is learned');
  f.set('job',{id:'c'.repeat(32),kind:'voice-learn',status:'ready',metadata:{name:'Learned Voice',samples:['s']},result:{content:'# Learned voice',notes:''},attempts:0});
  await f.run('sToolJob(job)');
  options={...options,profiles:[...options.profiles,{id:'learned',name:'Learned Voice',status:'provisional'}]};
  await descendants(f.get('sheet')).find(e=>e.textContent==='Save provisional voice guide').listeners.click();
  assert.equal(f.get('sheet').hidden,true);assert.equal(f.run('studio.screen'),'new');
  assert.equal(chosen('new-profile'),'Learned Voice · provisional','the new voice is chosen');
  assert.equal(byId('new-title').value,'A synthetic blog','the brief is kept');
  // Editing a voice that already existed is not a new choice for this brief.
  f.run("sEditVoice({id:'guest',name:'Guest Writer',guide:'A guide.',status:'provisional',sample_ids:[],rules:{},expected:'p1'},{samples:[]})");
  options={...options,profiles:[...options.profiles]};
  const before=chosen('new-profile');
  await descendants(f.get('sheet')).find(e=>e.textContent==='Save provisional guide').listeners.click();
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Voices and styles','an edited voice returns to Voices and styles');
  assert.equal(chosen('new-profile'),before,'the brief’s choice is unchanged');
}

// Voices and styles: one sheet lists both, a style can be read and learned, links open the
// voice-links flow for either purpose, and a LinkedIn export goes up as one entry whose
// articles become the voice samples.
async function voicesAndStyles(){
  const posts=[];
  const kinds={styles:[{id:'product-announcement',name:'Product announcement',summary:'Lead with what is new.',kind:'seed',revision:1,status:'confirmed'}],samples:[{id:'example',name:'Launch post',author:''}],candidates:[{id:'memo',name:'Team memo',author:''}],pending:[]};
  const f=fixture((url,options)=>{
    if(options?.body)posts.push({url,data:JSON.parse(options.body)});
    if(url.startsWith('/api/voices'))return {profiles:[{id:'voice',name:'Synthetic Author',revision:1,status:'provisional'}],samples:[{id:'sample',name:'Authored passage',author:'Synthetic Author'},{id:'article',name:'LinkedIn · A first article',author:'Synthetic Author'}],candidates:[],pending:[]};
    if(url.startsWith('/api/styles'))return kinds;
    if(url.startsWith('/api/style?'))return {...kinds.styles[0],guide:'# Product announcement\n\nLead with what is new.',sample_ids:[],expected:'style-version'};
    if(url==='/api/tool-action'){const data=JSON.parse(options.body);if(data.action==='source-purpose')return {source:data.source,revision:2,purposes:['reference',data.purpose],author:null,changed:true,receipts:[]};return {id:'b'.repeat(32),kind:'style-learn',status:'queued',metadata:{name:'Launch note',samples:['example']},attempts:0};}
    if(url==='/api/upload')return {files:[{filename:'LinkedIn · About',source:{id:'about'},state:'ready',chars:40,note:'',purpose:'author-background',author:'Synthetic Author'},{filename:'LinkedIn · A first article',source:{id:'article'},state:'ready',chars:400,note:'',purpose:'voice-sample',author:'Synthetic Author'}],receipts:[],state:'saved',next_step:'Every file has text.'};
    return {items:[]};
  });f.loadRunner();voicesOn(f);
  const sheet=()=>descendants(f.get('sheet')),text=()=>sheet().map(e=>e.textContent),find=label=>sheet().find(e=>e.textContent===label);
  await f.run('sVoiceTools()');
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Voices and styles');
  for(const label of ['Voices','Styles','Synthetic Author','Create a voice','Write a voice guide','Create voices for every author','Create a style','Write a style guide','Product announcement'])assert.ok(text().includes(label),label+' in '+text().join('|'));
  for(const gone of ['Learn a voice from samples','Import a LinkedIn export','Add links to posts','Upload an authored sample','Learn a style from examples','Add links to examples','Upload an example'])assert.ok(!text().includes(gone),gone+' is now a source inside Create a voice or Create a style');
  // Create a voice: one sheet, in order: the name, the writing from any source, the samples.
  await find('Create a voice').listeners.click();
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Create a voice');
  for(const label of ['1. Whose voice is this?','2. Add their writing','3. Choose up to 20 samples','Add links to posts','Import a LinkedIn export','Upload their posts','Posts already in the library','Build a provisional voice'])assert.ok(text().includes(label),label+' in '+text().join('|'));
  // Links open the merged voice-links flow, for voices and, from Create a style, for style samples.
  f.run('sVoiceLinks=(found,profile,article,purpose)=>{window.linksOpened=purpose||"voice-sample";}');
  await find('Add links to posts').listeners.click();assert.equal(f.run('window.linksOpened'),'voice-sample');
  await f.run('sVoiceTools()');await find('Create a style').listeners.click();
  for(const label of ['1. What kind of writing is this?','2. Add examples','3. Choose up to 20 examples','Upload examples','Build a provisional style'])assert.ok(text().includes(label),label+' in '+text().join('|'));
  await find('Add links to examples').listeners.click();assert.equal(f.run('window.linksOpened'),'style-sample');
  await f.run("sStyleDetail('product-announcement')");
  assert.ok(text().includes('Edit this style guide'));assert.ok(text().includes('Retire this kind of post'));assert.ok(text().some(t=>/^Starter style/.test(t)));
  // Learning a style needs the permission box, then sends the chosen examples.
  await f.run('sVoiceTools()');await find('Create a style').listeners.click();
  assert.ok(find('Use as an example'),'a reference can become an example of this kind');
  assert.equal(find('Use as an example').attributes['aria-label'],'Use Team memo as an example');
  await find('Use as an example').listeners.click();
  assert.deepEqual(posts.find(p=>p.url==='/api/tool-action').data,{action:'source-purpose',source:'memo',purpose:'style-sample'});
  posts.length=0;
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(posts.some(p=>p.url==='/api/tool-action'),false,'nothing starts before the permission box is checked');
  const name=sheet().find(e=>e.id==='learn-style-name');name.value='Launch note';name.listeners.input();
  const example=sheet().find(e=>e.value==='example');example.checked=true;example.listeners.change();
  sheet().find(e=>e.id==='learn-style-permission').checked=true;
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const learn=posts.find(p=>p.url==='/api/tool-action').data;
  assert.equal(learn.kind,'style-learn');assert.equal(learn.name,'Launch note');assert.ok(learn.samples.includes('example'));assert.equal(learn.confirmed,true);
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Learn a style');
  f.set('styleJob',{id:'b'.repeat(32),kind:'style-learn',status:'ready',metadata:{name:'Launch note',samples:['example']},result:{content:'# Launch note',notes:''},attempts:0});
  await f.run('sToolJob(styleJob)');
  assert.ok(text().some(t=>/describes a kind of writing, not a person/.test(t)),text().join('|'));
  assert.ok(find('Save provisional style guide'));assert.ok(find('Confirm this style guide'));assert.equal(sheet().some(e=>e.textContent==='Save outline for review'),false);
  // The LinkedIn export goes up as one entry, says what it shares, and sends the author when given.
  await f.run('sVoiceTools()');await find('Create a voice').listeners.click();await find('Import a LinkedIn export').listeners.click();
  assert.ok(text().includes('The About text and the articles are saved as sources in your reference library. With a Team Hub selected, they are shared with your team like any other source.'));
  const file=sheet().find(e=>e.id==='linkedin-file');file.files=[{name:'export.zip',size:4,arrayBuffer:async()=>new Uint8Array([80,75,3,4]).buffer}];
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  let sent=posts.filter(p=>p.url==='/api/upload').at(-1).data;
  assert.equal(sent.files.length,1);assert.deepEqual(Object.keys(sent.files[0]),['linkedin']);assert.equal(sent.purpose,'voice-sample');assert.equal(sent.analyze,false);
  assert.equal(Object.hasOwn(sent,'author'),false,'no author unless one is given');
  const author=sheet().find(e=>e.id==='linkedin-author');author.value='Synthetic Author';author.listeners.input();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  sent=posts.filter(p=>p.url==='/api/upload').at(-1).data;assert.equal(sent.author,'Synthetic Author');
  assert.ok(text().includes('Learn Synthetic Author’s voice from these articles'),text().join('|'));
  f.run("studio.voiceLearning={new:{name:'An older name',samples:[],background:null,operation:'d'.repeat(32)}}");
  await find('Learn Synthetic Author’s voice from these articles').listeners.click();
  assert.deepEqual(sheet().filter(e=>e.type==='checkbox'&&e.checked).map(e=>e.value),['article'],'the About text is background, not a sample');
  assert.equal(sheet().find(e=>e.id==='learn-voice-name').value,'Synthetic Author','the export’s person names the voice');
  posts.length=0;sheet().find(e=>e.id==='learn-voice-permission').checked=true;
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const job=posts.find(p=>p.url==='/api/tool-action').data;assert.equal(job.kind,'voice-learn');assert.equal(job.background,'about');assert.deepEqual(job.samples,['article']);
}

// The learn-a-voice sheet shows what can be used: other ready sources become samples by their
// author, sources without text are listed but cannot be chosen, and uploads are samples.
async function voiceCandidates(){
  const requests=[];let marked=false;
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url.startsWith('/api/voices'))return {profiles:[],samples:marked?[{id:'talk',name:'Conference talk',author:'Synthetic Author'}]:[],candidates:[{id:'talk',name:'Conference talk',author:'Synthetic Author'},{id:'notes',name:'Untitled notes',author:null}],pending:[{id:'scan',name:'Scanned page',author:''}]};
    if(url==='/api/tool-action'){marked=true;return {source:data.source,revision:2,purposes:['reference','voice-sample'],author:data.author||'Synthetic Author',changed:true,receipts:[]};}
    if(url==='/api/upload')return {source:{id:'upload'},state:'ready',chars:20,note:'',receipts:[]};
    return {items:[]};});
  f.loadRunner();
  const sheet=()=>descendants(f.get('sheet')),text=()=>sheet().map(e=>e.textContent),find=label=>sheet().find(e=>e.textContent===label);
  await f.run('api("voices").then(found=>sLearnVoice(found))');
  assert.equal(text().some(t=>/reference library/.test(t)&&/classif/.test(t)),false,'no hint sends people to a screen that cannot reclassify');
  assert.ok(text().includes('Scanned page · needs text'),text().join('|'));
  assert.equal(sheet().some(e=>e.tagName==='input'&&e.value==='scan'),false,'a source without text cannot be chosen');
  assert.ok(find('Add links to posts'));
  assert.equal(find('Use as a sample by Synthetic Author').attributes['aria-label'],'Use Conference talk as a sample by Synthetic Author');
  const named=sheet().find(e=>e.id==='learn-voice-name');named.value='synthetic author';named.listeners.input();
  await find('Use as a sample by Synthetic Author').listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/tool-action').data,{action:'source-purpose',source:'talk',purpose:'voice-sample'});
  assert.deepEqual(sheet().filter(e=>e.type==='checkbox'&&e.checked).map(e=>e.value),['talk'],'the new sample is ticked');
  // A source with no author asks whose writing it is.
  const whose=sheet().find(e=>e.id==='candidate-author-notes');assert.ok(whose,'asks for the author');
  whose.value='Avery Quinn';whose.listeners.input();
  assert.equal(find('Use as a sample by Avery Quinn').attributes['aria-label'],'Use Untitled notes as a sample by Avery Quinn');
  await find('Use as a sample by Avery Quinn').listeners.click();
  assert.deepEqual(requests.filter(r=>r.url==='/api/tool-action').at(-1).data,{action:'source-purpose',source:'notes',purpose:'voice-sample',author:'Avery Quinn'});
  assert.equal(JSON.parse(f.run('JSON.stringify(studio.voiceLearning.new.samples)')).includes('notes'),false,'another author’s writing is not ticked for this voice');
  // An upload here is a voice sample by the named author, never a plain reference.
  const name=sheet().find(e=>e.id==='learn-voice-name');assert.equal(name.value,'synthetic author');name.value='Synthetic Author';name.listeners.input();
  const upload=sheet().find(e=>e.id==='learn-voice-upload');upload.files=[{name:'post.md',size:20,arrayBuffer:async()=>new TextEncoder().encode('# A post\n\nText.').buffer}];
  await upload.listeners.change();
  const sent=requests.find(r=>r.url==='/api/upload').data;
  assert.equal(sent.purpose,'voice-sample');assert.equal(sent.author,'Synthetic Author');assert.equal(sent.as_blog,false);assert.equal(sent.analyze,false);
}

// The run says which voice and kind of post it writes with; Change asks once before a voice
// change on a blog with an outline or a draft, and stays on the run.
async function runVoiceChange(){
  const requests=[];let content='',refuse='';
  const found={id:'synthetic',title:'Synthetic blog',status:'waiting-for-approval',next:'draft',approval:'page',expected:'run-1',enabled:false,directory:'/synthetic',seconds:600,engine:'codex',mode:'write',decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},voice_name:'Synthetic Author',voice_mode:'profile',voice_profile:'voice',voice_revision:1,style_name:'Product announcement',notes:{},stages:[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'approved'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'pending'}]};
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url.startsWith('/api/run?'))return found;
    if(url.startsWith('/api/manuscript?'))return {id:'synthetic',title:'Synthetic blog',content,expected:'m1',proposals:[],findings:[],checks:{},working:false};
    if(url.startsWith('/api/voices'))return {profiles:[{id:'voice',name:'Synthetic Author',revision:1,status:'confirmed'},{id:'guest',name:'Guest Writer',revision:2,status:'provisional'},{id:'gone',name:'Retired Writer',revision:1,status:'retired'}],samples:[],candidates:[],pending:[]};
    if(url.startsWith('/api/voice?'))return {id:'guest',name:'Guest Writer',revision:2,status:'provisional',guide:'A guide.',sample_ids:[],expected:'p1'};
    if(url==='/api/tool-action')return refuse?{__http:409,error:refuse}:{id:data.id,voice:{mode:'profile'},status:'voice-selected',receipts:[],run:found};
    return {items:[],total:0};});
  f.loadRunner();voicesOn(f);
  const page=()=>descendants(f.get('studio-page')),sheet=()=>descendants(f.get('sheet')),find=label=>sheet().find(e=>e.textContent===label);
  await f.run("sRoute('run','synthetic','status')");
  assert.ok(page().some(e=>e.textContent==='Voice: Synthetic Author · Kind of post: Product announcement'),page().map(e=>e.textContent).join('|'));
  assert.ok(f.get('actions').children.some(e=>e.textContent==='Tools'));
  await page().find(e=>e.textContent==='Change the voice').listeners.click();
  const select=sheet().find(e=>e.id==='change-voice');
  assert.deepEqual(select.children.map(o=>o.textContent),['Synthetic Author · confirmed','Guest Writer · provisional'],'retired voices are left out');
  assert.equal(select.value,'voice','the current voice is chosen');
  assert.equal(find('Use this voice').disabled,true,'choosing the current voice changes nothing');
  assert.ok(sheet().some(e=>/no particular voice, ask in the conversation/.test(e.textContent||'')),'says where no particular voice is chosen');
  select.value='guest';select.listeners.change();assert.equal(find('Use this voice').disabled,false);
  await find('Use this voice').listeners.click();
  assert.equal(requests.some(r=>r.url==='/api/tool-action'),false,'a blog with an outline asks first');
  assert.ok(sheet().some(e=>e.textContent==='Its reviews will need a new look; nothing is rewritten.'));
  await find('Change to Guest Writer').listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/tool-action').data,{action:'voice-apply',id:'synthetic',profile:'guest',expected:'m1',confirmed:true});
  assert.equal(f.run('studio.screen'),'run','the run stays open');assert.equal(f.get('sheet').hidden,true);
  // The same voice at a newer revision than the blog pinned is a change it can take.
  f.set('older',{...found,voice_revision:0});f.run("studio.screen='run';sRun(older)");
  await page().find(e=>e.textContent==='Change the voice').listeners.click();
  assert.equal(sheet().find(e=>e.id==='change-voice').value,'voice');assert.equal(find('Use this voice').disabled,false,'a newer revision of the same voice');
  // A refusal other than the confirmation shows on the sheet's problem line.
  f.set('fresh',{...found,id:'fresh',stages:[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'pending'}]});f.run('sRun(fresh)');
  refuse='This blog changed. Reload before changing its voice.';
  await page().find(e=>e.textContent==='Change the voice').listeners.click();
  await find('Use this voice').listeners.click();
  assert.ok(sheet().some(e=>e.className==='problem'&&e.textContent===refuse),'the refusal reaches the sheet: '+sheet().map(e=>e.textContent).join('|'));
  assert.equal(f.get('sheet').hidden,false,'the sheet stays open');refuse='';
  // A manuscript's own voice is named as that, not as a described tone; a twin name is not the current voice.
  f.set('kept',{...found,voice_name:null,voice_mode:'preserve',voice_profile:null,style_name:null});f.run("studio.screen='run';sRun(kept)");
  assert.ok(page().some(e=>e.textContent==='Voice: the manuscript’s own voice · Kind of post: none'),page().map(e=>e.textContent).join('|'));
  f.set('toned',{...found,voice_name:null,voice_mode:'tone',voice_profile:null});f.run('sRun(toned)');
  assert.ok(page().some(e=>e.textContent==='Voice: none (the described tone) · Kind of post: Product announcement'));
  // From the editor, Use this revision asks first on a blog with a draft, then reopens the
  // editor, even when the blog has a guided run.
  requests.length=0;content='# Draft';found.id='edited';
  f.run("studio.screen='editor';studio.id='edited'");
  await f.run("sVoiceProfile('guest','edited')");
  await find('Use this revision for this article').listeners.click();
  assert.equal(requests.some(r=>r.url==='/api/tool-action'),false,'nothing changes before the confirmation');
  await find('Change to Guest Writer').listeners.click();
  const applied=requests.find(r=>r.url==='/api/tool-action').data;assert.equal(applied.confirmed,true);assert.equal(applied.id,'edited');
  assert.equal(f.run('studio.screen'),'editor','a change made in the editor returns to the editor');
}

// Tools are not hidden: the library sheet opens Tools and Voices and styles directly, and Settings links to them.
// The older voice tools wait behind one switch in Settings → Advanced, off by default: no
// Write as, Default voice, Change the voice, voice learning, Create voices for every author,
// voice-sample uploads or library marks. Kinds of post have their own screen. On, they return.
async function voiceSwitch(){
  const requests=[],defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''};
  const found={id:'synthetic',title:'Synthetic blog',status:'waiting-for-approval',next:'draft',approval:'page',expected:'run-1',enabled:false,directory:'/synthetic',seconds:600,engine:'codex',mode:'write',decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},voice_name:'Synthetic Author',voice_mode:'profile',voice_profile:'voice',voice_revision:1,style_name:'Product announcement',notes:{},stages:[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'approved'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'pending'}]};
  let settings={defaults,shared_before:{engine:'codex',author:''},workspace:'/synthetic',voice:{profile_id:'voice',revision:1},voices:[{id:'voice',name:'Synthetic Author',revision:1}],features:{voice:false}};
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url==='/api/run-settings'&&data){settings={...settings,features:data.features||settings.features};return settings;}
    if(url==='/api/run-settings')return settings;
    if(url.startsWith('/api/run?'))return found;
    if(url.startsWith('/api/tools'))return {id:null,has_manuscript:false,jobs:[]};
    if(url.startsWith('/api/voices'))return {profiles:[{id:'voice',name:'Synthetic Author',revision:1,status:'confirmed'}],samples:[],candidates:[],pending:[]};
    if(url.startsWith('/api/styles'))return {styles:[{id:'product-announcement',name:'Product announcement',summary:'Lead with what is new.',kind:'seed',revision:1,status:'confirmed'}],samples:[],candidates:[],pending:[]};
    if(url==='/api/run-options')return {settings,sources:[],profiles:[{id:'voice',name:'Synthetic Author',status:'confirmed'}],agents:{codex:true},default_voice:{scope:'personal',profile:'voice',name:'Synthetic Author',revision:1,status:'confirmed'},styles:[]};
    if(url==='/api/team')return {};
    return {items:[],total:0};});
  f.loadRunner();f.set('settings',settings);f.set('defaults',defaults);f.run('studio.settings=settings');
  const page=()=>descendants(f.get('studio-page')),text=()=>page().map(e=>e.textContent),sheet=()=>descendants(f.get('sheet')).map(e=>e.textContent);
  // The page parts drawn once: the Voices item, Learn a voice from these, the voice-sample roles.
  for(const id of ['upload-purpose','library-role']){const select=f.get(id);for(const value of ['reference','voice-sample','style-sample']){const option=new (f.get(id).constructor)('option');option.value=value;select.append(option);}}
  f.run('sVoiceSwitchShown()');
  assert.equal(f.get('library-learn-voice').hidden,true,'no Learn a voice from these');
  for(const id of ['upload-purpose','library-role'])assert.deepEqual(f.get(id).children.map(o=>o.value),['reference','style-sample'],'no voice-sample choice in '+id);
  // Settings: no Default voice; the switch is under Advanced, closed; saving posts it, and no voice.
  f.run("studio.brand={};studio.team={};studio.screen='settings';sSettings()");
  assert.equal(page().some(e=>e.id==='settings-voice'),false,'no Default voice while off');
  const box=page().find(e=>e.id==='settings-voice-tools');assert.ok(box,'the switch is in Settings');assert.equal(box.checked,false);
  let node=box,inside=null;while(node){if(node.tagName==='details'&&!inside)inside=node;node=node.parent;}
  assert.ok(inside&&descendants(inside).some(e=>e.textContent==='Advanced'),'the switch sits under Advanced');assert.notEqual(inside.open,true,'Advanced is closed');
  assert.ok(text().includes('Kinds of post')&&text().includes('Open kinds of post'),'Settings links to kinds of post');assert.equal(text().includes('Open voices and styles'),false);
  await page().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  let sent=requests.filter(r=>r.url==='/api/run-settings'&&r.data).at(-1).data;
  assert.deepEqual([sent.features,sent.features_before],[{voice:false},{voice:false}]);assert.equal('voice' in sent||'voice_before' in sent,false,'no default voice is posted while off');
  // The old start: no Write as, and the tone shows; a new blog sends no profile.
  f.run("studio.options={settings:{defaults,review_level:'balanced'},sources:[],profiles:[{id:'voice',name:'Synthetic Author',status:'confirmed'}],default_voice:{scope:'personal',profile:'voice',name:'Synthetic Author',revision:1,status:'confirmed'},agents:{codex:true},styles:[]};studio.screen='new';studio.draft={...studio.options.settings.defaults,step:0,id:'',title:'T',goal:'G',audience:'A',sources:[],manuscript:'',mode:'write',stop:'draft',minutes:'10',files:[]};sWizard()");
  assert.equal(page().some(e=>e.id==='new-profile'),false,'no Write as while off');
  assert.equal(f.run('JSON.stringify(sVoicePayload(studio.draft))'),'{}','no profile is sent');assert.equal(/Write as/.test(f.run('sVoiceSummary(studio.draft)')),false);
  // A run: its voice is said, never changed here.
  await f.run("sRoute('run','synthetic','status')");
  assert.ok(text().some(t=>/^Voice: Synthetic Author/.test(t)),'the run still says its voice');assert.equal(text().includes('Change the voice'),false,'no Change the voice while off');
  // Tools and the kinds of post screen.
  f.run('sTools()');assert.ok(sheet().includes('Kinds of post'));assert.equal(sheet().includes('Voices and styles'),false);
  await f.run('sMoreTools()');assert.ok(sheet().includes('Kinds of post'));assert.equal(sheet().includes('Voices and styles'),false);
  f.run('sCloseSheet()');await f.run("sRoute('settings')");await f.run("sRoute('voices')");
  assert.equal(f.get('title').textContent,'Kinds of post');
  assert.deepEqual(f.get('actions').children.map(e=>e.textContent),['Create a style']);
  assert.ok(text().includes('Product announcement')&&text().includes('Write a style guide'));
  for(const gone of ['Voices','Create a voice','Write a voice guide','Create voices for every author','Every author in the team library'])assert.equal(text().includes(gone),false,gone+' is hidden while off');
  const back=f.get('toolbar-lead').children[0];assert.ok(back,'Kinds of post goes Back');await back.listeners.click();assert.equal(f.run('studio.screen'),'settings');
  assert.equal(f.get('go-settings').attributes['aria-current'],'page');
  // On: Settings saves it, and the tools come back.
  f.run("studio.screen='settings';sSettings()");const on=page().find(e=>e.id==='settings-voice-tools');on.checked=true;on.listeners.change();
  await page().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  sent=requests.filter(r=>r.url==='/api/run-settings'&&r.data).at(-1).data;assert.deepEqual([sent.features,sent.features_before],[{voice:true},{voice:false}]);
  assert.equal(f.run('sVoicesOn()'),true);assert.equal(f.get('library-learn-voice').hidden,false);
  for(const id of ['upload-purpose','library-role'])assert.ok(f.get(id).children.some(o=>o.value==='voice-sample'),'the voice-sample choice is back in '+id);
  f.run("studio.screen='settings';sSettings()");assert.ok(page().some(e=>e.id==='settings-voice'),'Default voice is back');
  await f.run("sRoute('run','synthetic','status')");assert.ok(text().includes('Change the voice'));
  f.run("studio.screen='new';studio.draft.step=0;sWizard()");assert.ok(page().some(e=>e.id==='new-profile'),'Write as is back');
}

// Voice guides: a screen from the sidebar, whether or not the older voice tools are on. A
// guide is written by hand, or made from three to twenty samples and then read and edited;
// a saved one is edited or retired.
async function voiceGuides(){
  const requests=[];let job={id:'c'.repeat(32),kind:'voice-guide',status:'queued',metadata:{name:'Release notes',samples:3},result:null};
  const listing={guides:[{id:'avery',name:'Avery',revision:2,status:'provisional',says:'Short direct sentences, with one dry joke per post.'},{id:'plain',name:'Plain',revision:1,status:'confirmed',says:'Plain words.'},{id:'old',name:'Old voice',revision:3,status:'retired',says:'Long sentences.'}],making:[{id:'d'.repeat(32),name:'Launch voice',status:'ready'}]};
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url==='/api/voice-guides')return listing;
    if(url.startsWith('/api/voice?'))return {id:'avery',name:'Avery',revision:2,status:'provisional',guide:'# Avery\n\nShort direct sentences.',sample_ids:['s1'],expected:'p2'};
    if(url.startsWith('/api/tool-job?'))return job;
    if(url==='/api/tool-action'&&data.action==='job-create')return job;
    if(url==='/api/tool-action')return {profile:'new-guide',revision:1,status:'confirmed',receipts:[]};
    return {items:[],total:0};});
  f.loadRunner();f.run("studio.settings={defaults:{},features:{voice:false}}");f.run('setTimeout=(fn)=>{window.later=fn;return 0;}');
  const page=()=>descendants(f.get('studio-page')),text=()=>page().map(e=>e.textContent),sheet=()=>descendants(f.get('sheet')),find=label=>sheet().find(e=>e.textContent===label),byId=id=>sheet().find(e=>e.id===id);
  const type=(id,value)=>{const node=byId(id);node.value=value;node.listeners.input();};
  await f.run("sRoute('guides')");
  assert.equal(f.get('title').textContent,'Voice guides');assert.equal(f.get('go-guides').attributes['aria-current'],'page','Voice guides is a sidebar screen');
  assert.deepEqual(f.get('actions').children.map(e=>[e.textContent,e.className]),[['New voice guide','button button-filled']]);
  for(const said of ['Avery','Short direct sentences, with one dry joke per post.','Provisional','Plain','Plain words.','Launch voice','Ready to read and save.','Retired (1)'])assert.ok(text().includes(said),said+' on the screen: '+text().join('|'));
  assert.equal(text().includes('Learning voices'),false,'the older tools are not offered while off');
  assert.equal(page().find(e=>e.attributes['aria-label']==='Open Avery')?.textContent,'Open');
  // A guide being made that is not wanted (failed, or never saved) is discarded from the list.
  await page().find(e=>e.attributes['aria-label']==='Discard Launch voice').listeners.click();
  assert.deepEqual(requests.filter(r=>r.url==='/api/tool-action').at(-1).data,{action:'guide-discard',job:'d'.repeat(32)});
  // By hand: a name and the text, saved confirmed with no samples.
  await f.get('actions').children[0].listeners.click();
  assert.equal(f.get('sheet').children[0].children[0].textContent,'New voice guide');
  for(const step of ['1. Name','2. Write it, or make it from samples','3. Read and edit'])assert.ok(find(step),step);
  type('guide-name','Plain notes');type('guide-text','Plain words. Short paragraphs.');
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.deepEqual(requests.filter(r=>r.url==='/api/tool-action').at(-1).data,{action:'profile-save',name:'Plain notes',guide:'Plain words. Short paragraphs.',status:'confirmed',confirmed:true});
  assert.equal(f.get('sheet').hidden,true,'saved, the sheet closes');
  // From samples: three pasted, Make the guide, then the text arrives to read and edit.
  await f.get('actions').children[0].listeners.click();
  type('guide-name','Release notes');await find('From samples').listeners.click();
  assert.ok(byId('guide-upload'),'samples can be uploaded');assert.equal(find('Save guide').disabled,true,'nothing to save before the guide is made');
  for(const n of [1,2,3])type('guide-sample-'+n,'Sample text '+n+'.');
  await find('Make the guide').listeners.click();
  const made=requests.filter(r=>r.url==='/api/tool-action').at(-1).data;
  assert.equal(made.kind,'voice-guide');assert.equal(made.name,'Release notes');assert.deepEqual(made.samples,[{text:'Sample text 1.'},{text:'Sample text 2.'},{text:'Sample text 3.'}]);
  assert.ok(sheet().some(e=>e.textContent==='Making the guide from your samples…'));
  job={...job,status:'ready',result:{content:'# Release notes\n\nShort and specific.'}};await f.run('window.later()');
  assert.equal(byId('guide-text').value,'# Release notes\n\nShort and specific.','the made guide is there to edit');
  type('guide-text','# Release notes\n\nShort, specific, edited.');assert.equal(find('Save guide').disabled,false);
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.deepEqual(requests.filter(r=>r.url==='/api/tool-action').at(-1).data,{action:'job-apply',job:job.id,name:'Release notes',content:'# Release notes\n\nShort, specific, edited.'});
  // A saved guide: edited and saved, or retired with a confirmation.
  await f.run("sRoute('guides')");await page().find(e=>e.attributes['aria-label']==='Open Avery').listeners.click();
  assert.equal(byId('guide-text').value,'# Avery\n\nShort direct sentences.');assert.ok(sheet().some(e=>/^Provisional/.test(e.textContent)));
  type('guide-text','# Avery\n\nShorter.');await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.deepEqual(requests.filter(r=>r.url==='/api/tool-action').at(-1).data,{action:'profile-save',profile:'avery',expected:'p2',name:'Avery',guide:'# Avery\n\nShorter.',status:'confirmed',confirmed:true});
  await page().find(e=>e.attributes['aria-label']==='Open Avery').listeners.click();
  await find('Retire this guide').listeners.click();assert.equal(f.get('sheet').children[0].children[0].textContent,'Retire Avery?');
  await find('Retire').listeners.click();
  assert.deepEqual(requests.filter(r=>r.url==='/api/tool-action').at(-1).data,{action:'profile-retire',profile:'avery',expected:'p2',confirmed:true});
  // With the older tools on, the screen links to them; the guides stay the same.
  f.run("studio.settings.features={voice:true}");await f.run("sRoute('guides')");assert.ok(text().includes('Learning voices')&&text().includes('Open voices and styles'));
}

async function toolsAreNamed(){
  const f=fixture(url=>{if(url.startsWith('/api/tools'))return {id:null,has_manuscript:false,jobs:[]};if(url.startsWith('/api/voices'))return {profiles:[],samples:[],candidates:[],pending:[]};if(url.startsWith('/api/styles'))return {styles:[],samples:[],candidates:[],pending:[]};return {items:[]};});f.loadRunner();voicesOn(f);
  const sheet=()=>descendants(f.get('sheet')),find=label=>sheet().find(e=>e.textContent===label);
  f.run('sTools()');assert.ok(find('Tools'));assert.equal(sheet().some(e=>e.textContent==='More tools'),false);
  await find('Tools').listeners.click();assert.equal(f.get('sheet').children[0].children[0].textContent,'Tools');
  assert.ok(find('Voices and styles'),'the tools sheet opens voices and styles');
  f.run('sTools()');await find('Voices and styles').listeners.click();assert.equal(f.get('sheet').children[0].children[0].textContent,'Voices and styles');
  f.run("sCloseSheet();studio.settings={defaults:{engine:'codex',seconds:600,research:'none',tone:'Clear',author:''},workspace:'/synthetic'};studio.brand={};studio.team={};sSettings()");
  const link=descendants(f.get('studio-page')).find(e=>e.tagName==='button'&&e.textContent==='Open voices and styles');assert.ok(link,'Settings links to voices and styles');
  await link.listeners.click();
  // Voices and styles is a screen: Create a voice leads its toolbar, Create a style beside it.
  assert.equal(f.run('studio.screen'),'voices');assert.equal(f.get('title').textContent,'Voices and styles');
  assert.deepEqual(f.get('actions').children.map(e=>[e.textContent,e.className]),[['Create a voice','button button-filled'],['Create a style','button button-quiet']]);
  const page=descendants(f.get('studio-page')).map(e=>e.textContent);
  for(const label of ['Voices','Every author in the team library','Create voices for every author','Styles','Write a voice guide','Write a style guide'])assert.ok(page.includes(label),label+' on the screen');
  assert.equal(page.includes('Create a voice'),false,'the toolbar holds the primary action, not the cards');
}

// A research case the independent check refused: the run says how many objections in how many
// groups, lists each group by what it checked and its verdict with its first note, and says the
// draft is kept on this computer. Nothing is listed for a run the check did not refuse.
async function researchRefusal(){
  const refused={id:'synthetic',title:'Synthetic blog',status:'failed',enabled:false,next:'research',approval:'page',expected:'version-1',directory:'/synthetic/articles/synthetic',seconds:600,engine:'codex',mode:'write',review_level:'balanced',existing:false,decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},notes:{},
    error:'The research check still objected after 3 rounds of writing and checking: 4 objections in 3 groups. The draft report and the check’s notes are kept on this computer; Try again continues from them.',
    research:{kept:true,rounds:3,refusal:{rounds:3,count:4,cause:null,groups:[{kind:'facts',verdict:'narrow',count:2,note:'Only the fictional example says this.',ids:['fact-a','fact-b']},{kind:'findings',verdict:'unsupported',count:1,note:'No saved fact supports it.',ids:['instance-min']},{kind:'assessment',verdict:'needs-revision',count:1,note:'The brief leaves out the strongest objection.',ids:[],asked:['coverage']}]}},
    stages:[{stage:'research-plan',label:'Research questions',path:'derived/blog-research-plan.md',status:'approved'},{stage:'research',label:'Research findings',path:'derived/blog-research.md',status:'pending'},{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'pending'}]};
  const f=fixture(()=>({items:[],total:0}));f.loadRunner();
  const nodes=()=>descendants(f.get('studio-page')),text=()=>nodes().map(e=>e.textContent);
  f.set('found',refused);f.run("studio.screen='run';studio.id=found.id;sRun(found)");
  assert.ok(text().includes(refused.error),'the stop sentence is shown as it is: '+text().join('|'));
  const box=nodes().find(e=>e.tagName==='details'&&e.children[0]?.textContent==='What the research check objected to');
  assert.ok(box,'the objections sit under their own disclosure: '+text().join('|'));
  const inside=descendants(box).map(e=>e.textContent);
  for(const words of ['2 facts marked narrow','Only the fictional example says this.','1 finding marked unsupported','No saved fact supports it.','Coverage needs revision','The brief leaves out the strongest objection.'])assert.ok(inside.includes(words),words+' in '+inside.join('|'));
  assert.ok(inside.some(t=>/4 objections in its last review, after 3 rounds of writing and checking/.test(t)),inside.join('|'));
  assert.ok(inside.some(t=>/kept on this computer, in this blog’s \.studio-research-draft folder, and are not shared/.test(t)),inside.join('|'));
  // A cause the contract names leads the list; a run nothing refused lists nothing.
  f.set('found',{...refused,research:{...refused.research,refusal:{...refused.research.refusal,cause:'The check could not read the original of “Synthetic”.'}}});f.run('sRun(found)');
  assert.ok(text().includes('The check could not read the original of “Synthetic”.'));
  f.set('found',{...refused,error:'Research ran out of the time a step may take (10 minutes).',research:{kept:true,rounds:3,refusal:null}});f.run('sRun(found)');
  assert.equal(nodes().some(e=>e.tagName==='details'&&e.children[0]?.textContent==='What the research check objected to'),false,'only a refusal has objections');
}

// Research says its round while it works, and a stopped research says what Try again does: it
// continues from the kept draft for up to three more rounds, and the last attempt's jobs, time,
// tokens and cost as the assistant reported them. No "from the start" for anything.
async function researchRounds(){
  const base={id:'synthetic',title:'Synthetic blog',next:'research',approval:'page',expected:'version-1',directory:'/synthetic/articles/synthetic',seconds:600,engine:'claude',mode:'write',review_level:'balanced',existing:false,decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},notes:{},
    stages:[{stage:'research-plan',label:'Research questions',path:'derived/blog-research-plan.md',status:'approved'},{stage:'research',label:'Research findings',path:'derived/blog-research.md',status:'pending'},{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'pending'}]};
  const f=fixture(()=>({items:[],total:0}));f.loadRunner();
  const nodes=()=>descendants(f.get('studio-page')),text=()=>nodes().map(e=>e.textContent),now=()=>nodes().find(e=>e.className==='now-line')?.textContent;
  const working={...base,status:'working',enabled:true,error:'',started_at:new Date(Date.now()-4*60000).toISOString(),research:{kept:false,rounds:3,round:2,phase:'review',refusal:null,last:null}};
  f.set('found',working);f.run("studio.screen='run';studio.id=found.id;sRun(found)");
  assert.equal(now(),'Researching · Round 2 of 3, the independent check · 4 min of up to 10');
  f.set('found',{...working,research:{...working.research,round:1,phase:'author'}});f.run('sRun(found)');
  assert.equal(now(),'Researching · Round 1 of 3, writing the report · 4 min of up to 10');
  f.set('found',{...working,research:{...working.research,round:0,phase:'discovery'}});f.run('sRun(found)');
  assert.equal(now(),'Researching · Finding public sources · 4 min of up to 10');
  f.set('found',{...working,next:'outline',research:null});f.run('sRun(found)');
  assert.equal(now(),'Outlining · 4 min of up to 10','other steps say no round');
  // Stopped with a kept draft: Try again continues from it, and says what the last attempt took.
  const stopped={...base,status:'failed',enabled:false,started_at:null,error:'The research check still objected after 3 rounds of writing and checking: 4 objections in 3 groups. The draft report and the check’s notes are kept on this computer; Try again continues from them.',research:{contract:true,kept:true,from:'kept',rounds:3,round:null,phase:null,refusal:null,last:{jobs:6,rounds:3,seconds:552.4,tokens:410250,dollars:1.234,reported:6}}};
  f.set('found',stopped);f.run('sRun(found)');
  assert.ok(text().includes('Try again continues from the kept draft: up to 3 more rounds of writing and checking, within this blog’s 10-minute limit for the whole research step. The last attempt took 6 jobs in 3 rounds: 9 min 12 s, 410,250 tokens and about $1.23, as the assistant reported.'),text().join('|'));
  assert.ok(f.get('actions').children.some(e=>e.textContent==='Try again'));
  assert.equal(text().some(t=>/from the start/.test(t)),false,'Try again never claims to start over');
  // Nothing kept, and an assistant that reports no usage.
  f.set('found',{...stopped,engine:'codex',error:'Research could not produce valid evidence and report data after one correction attempt.',research:{...stopped.research,kept:false,from:null,last:{jobs:2,rounds:1,seconds:120,tokens:null,dollars:null,reported:0}}});f.run('sRun(found)');
  assert.ok(text().includes('Try again starts the research again: up to 3 rounds of writing and checking, within this blog’s 10-minute limit for the whole research step. The last attempt took 2 jobs in 1 round: 2 min; the assistant reported no tokens or cost.'),text().join('|'));
  // From the accepted research, when some jobs reported usage and some did not.
  f.set('found',{...stopped,research:{...stopped.research,kept:false,from:'accepted',last:{jobs:2,rounds:1,seconds:90,tokens:null,dollars:null,reported:1}}});f.run('sRun(found)');
  assert.ok(text().includes('Try again starts from the accepted research: up to 3 rounds of writing and checking, within this blog’s 10-minute limit for the whole research step. The last attempt took 2 jobs in 1 round: 1 min 30 s; the assistant reported no tokens or cost for every job.'),text().join('|'));
  // Research from before the shared contract is one plain job: no rounds, no check.
  f.set('found',{...stopped,error:'The selected CLI failed.',research:{contract:false,kept:false,from:null,rounds:3,refusal:null,last:null}});f.run('sRun(found)');
  assert.ok(text().includes('Try again makes the research findings again in a new job, with the same 10-minute limit; saved work is kept.'),text().join('|'));
  assert.equal(text().some(t=>/rounds of writing and checking/.test(t)),false);
}

// A new blog stopped at its research offers Continue without research: a confirmation that says
// what it does, one request, and the run's stops line without the research. Only a blog with a
// manuscript is told to open Edit manuscript.
async function skipResearch(){
  const requests=[];
  const stages=[{stage:'research-plan',label:'Research questions',path:'derived/blog-research-plan.md',status:'approved'},{stage:'research',label:'Research findings',path:'derived/blog-research.md',status:'pending'},{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'pending'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'pending'},{stage:'review',label:'Review',path:'derived/blog-review.md',status:'pending'},{stage:'package',label:'Handoff',path:'derived/blog-package.md',status:'pending'}];
  const stopped={id:'synthetic',title:'Synthetic blog',status:'failed',enabled:false,next:'research',approval:'page',expected:'version-1',directory:'/synthetic/articles/synthetic',seconds:600,engine:'codex',mode:'write',review_level:'step_by_step',ahead:{steps_left:5,next_gate:'research',next_stop:'Research findings',jobs:0,seconds:0,dollars:null,spent:null},existing:false,decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},notes:{},error:'The selected CLI failed.',research:{kept:false,rounds:3,refusal:null,last:null},stages};
  const after={...stopped,status:'queued',enabled:true,error:'',next:'outline',expected:'version-2',research:null,stages:stages.slice(2),ahead:{steps_left:4,next_gate:'outline',next_stop:'Outline',jobs:0,seconds:0,dollars:null,spent:null},decisions:[{event:'Continued without research',at:new Date().toISOString()}]};
  const f=fixture((url,options)=>{requests.push({url,data:options?.body?JSON.parse(options.body):null});if(url==='/api/run-skip-research'||url.startsWith('/api/run?'))return after;return {items:[],total:0};});f.loadRunner();
  const nodes=()=>descendants(f.get('studio-page')),text=()=>nodes().map(e=>e.textContent),line=()=>nodes().find(e=>e.className==='quiet ahead-line')?.textContent;
  f.set('found',stopped);f.run("studio.screen='run';studio.id=found.id;sRun(found)");
  assert.equal(line(),'5 steps left · Next stop: the research findings');
  assert.ok(text().includes('Research is optional. Continue without research takes this blog on to the outline, from your brief and selected sources; the later steps get no research findings.'),text().join('|'));
  assert.equal(text().some(t=>/Open Edit manuscript/.test(t)),false,'a new blog has no manuscript to edit');
  assert.equal(f.get('actions').children.some(e=>e.textContent==='Edit manuscript'),false);
  const skip=f.get('actions').children.find(e=>e.textContent==='Continue without research');assert.ok(skip,f.get('actions').children.map(e=>e.textContent).join('|'));
  await skip.listeners.click();
  assert.equal(requests.length,0,'opening the confirmation sends nothing');
  const sheet=descendants(f.get('sheet'));
  assert.ok(sheet.some(e=>e.textContent==='Continue without research?'));
  assert.ok(sheet.some(e=>e.textContent==='The research steps leave this blog’s run, and it goes on to the outline from your brief and selected sources. The later steps get no research findings, and research cannot be added back to this run.'),sheet.map(e=>e.textContent).join('|'));
  await sheet.find(e=>e.tagName==='button'&&e.textContent==='Continue without research').listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/run-skip-research').data,{id:'synthetic',expected:'version-1'});
  assert.equal(line(),'4 steps left · Next stop: the outline','the line no longer counts research');
  assert.ok(descendants(f.get('toasts')).some(e=>e.textContent==='Continuing without research.'));
  assert.equal(f.get('actions').children.some(e=>e.textContent==='Continue without research'),false,'not once research is gone');
  // An existing draft keeps the editing hint, and a working research offers no skip.
  f.set('found',{...stopped,existing:true});f.run('sRun(found)');
  assert.ok(text().includes('Research is optional for editing. Open Edit manuscript to polish the writing without research.'));
  f.set('found',{...stopped,status:'working',enabled:true,error:'',started_at:new Date().toISOString()});f.run('sRun(found)');
  assert.equal(f.get('actions').children.some(e=>e.textContent==='Continue without research'),false,'stop the research first');
  // The next stop is the server's, under the run's own level.
  f.set('found',{...stopped,review_level:'balanced',ahead:{...stopped.ahead,next_gate:'outline',next_stop:'Outline'}});f.run('sRun(found)');
  assert.equal(line(),'5 steps left · Next stop: the outline');
  // Only where research stopped: not at the research gates, and the hint goes with the button.
  for(const status of ['stopped','paused','needs-attention']){f.set('found',{...stopped,status,error:status==='needs-attention'?'Saved writing or its inputs changed.':''});f.run('sRun(found)');assert.ok(f.get('actions').children.some(e=>e.textContent==='Continue without research'),status);}
  for(const next of ['research','research-plan']){f.set('found',{...stopped,next,status:'waiting-for-approval',enabled:true,error:'An earlier note.'});f.run('sRun(found)');
    assert.equal(f.get('actions').children.some(e=>e.textContent==='Continue without research'),false,'not at the '+next+' gate');
    assert.equal(text().some(t=>/^Research is optional/.test(t)),false,'no hint without the button');}
}

// Finish asks first at every review level, names what it does with the team library, and the
// toast says whether the draft was kept there or why not. Earlier grouped stops still approve
// the displayed version directly.
async function finishEveryLevel(){
  const stages=[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'approved'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'approved'},{stage:'package',label:'Handoff',path:'derived/blog-package.md',status:'draft'}];
  const atPackage={id:'synthetic',title:'Synthetic blog',status:'waiting-for-approval',complete:false,next:'package',approval:'page',expected:'version-2',enabled:true,directory:'/synthetic/articles/synthetic',seconds:600,engine:'codex',mode:'write',existing:false,decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},notes:{},stages};
  const shown={id:'synthetic',title:'Synthetic blog',name:'blog-package.md',stage:'package',label:'Handoff',expected:'version-2',status:'draft',content:'# Handoff',notes:'',checks:[],previous:null,diff:[],bundle:[{stage:'draft',label:'Draft',content:'# The draft text'}]};
  for(const [level,library,toast] of [['step_by_step',{id:'kept',revision:1},'Finished. Kept in the team library.'],['balanced',{id:'kept',revision:2},'Finished. Kept in the team library.'],['automatic',{reason:'it could not be saved here.'},'Finished. Not kept in the team library: it could not be saved here.']]){
    const requests=[];const done={...atPackage,review_level:level,status:'complete',complete:true,next:null,expected:'version-3',stages:stages.map(row=>({...row,status:'approved'})),library};
    const f=fixture((url,options)=>{requests.push({url,data:options?.body?JSON.parse(options.body):null});if(url==='/api/run-approve'||url.startsWith('/api/run?'))return done;if(url.startsWith('/api/run-file'))return {content:'# The draft',name:'DRAFT.md'};return {items:[],total:0};});f.loadRunner();
    f.set('found',{...atPackage,review_level:level});f.set('shown',shown);f.run("studio.screen='gate';studio.found=found;sGate(found,shown)");
    const finish=f.get('actions').children.find(e=>e.textContent==='Finish');assert.ok(finish,level+': '+f.get('actions').children.map(e=>e.textContent).join('|'));
    await finish.listeners.click();
    assert.equal(requests.length,0,level+': Finish opens its sheet before anything is approved');
    const sheet=descendants(f.get('sheet'));
    assert.ok(sheet.some(e=>e.textContent==='Finish this blog?'),level);
    assert.ok(sheet.some(e=>/kept in the team library as a reference and an example of its kind of post/.test(e.textContent)),level+': the sheet names the library: '+sheet.map(e=>e.textContent).join('|'));
    await sheet.find(e=>e.tagName==='button'&&e.textContent==='Finish').listeners.click();
    assert.deepEqual(requests[0],{url:'/api/run-approve',data:{id:'synthetic',expected:'version-2'}},level);
    assert.ok(descendants(f.get('toasts')).some(e=>e.textContent===toast),level+': '+descendants(f.get('toasts')).map(e=>e.textContent).join('|'));
    assert.equal(descendants(f.get('toasts')).some(e=>/The next stage can begin/.test(e.textContent)),false,level+': Finish has no next stage');
  }
  // A run without a draft says why nothing is kept in the team library.
  const f=fixture(()=>({items:[],total:0}));f.loadRunner();
  f.set('found',{...atPackage,existing:false,review_level:'balanced',stages:[{stage:'review',label:'Review',path:'derived/blog-review.md',status:'draft'}],next:'review'});f.set('shown',{...shown,stage:'review',label:'Review',bundle:[]});
  f.run("studio.screen='gate';studio.found=found;sGate(found,shown)");
  await f.get('actions').children.find(e=>e.textContent==='Finish').listeners.click();
  assert.ok(descendants(f.get('sheet')).some(e=>/Nothing is kept in the team library: this blog has no saved draft\./.test(e.textContent)),descendants(f.get('sheet')).map(e=>e.textContent).join('|'));
  assert.equal(descendants(f.get('sheet')).some(e=>/as a reference and an example/.test(e.textContent)),false);
  f.run('sCloseSheet()');f.set('found',{...atPackage,review_level:'balanced',keeps_draft:false});f.set('shown',shown);f.run("studio.screen='gate';studio.found=found;sGate(found,shown)");
  await f.get('actions').children.find(e=>e.textContent==='Finish').listeners.click();
  assert.ok(descendants(f.get('sheet')).some(e=>/Nothing is kept in the team library/.test(e.textContent)),'the server says there is no draft to keep');
}

// Failures that say what to do: a CLI failure points at Status and shows the last lines the
// assistant printed; a step out of time says where its limit lives beside Try again with more
// time; first-run setup opens Writing preferences and marks an assistant that is not installed.
async function failureRecovery(){
  const requests=[];
  const failed={id:'synthetic',title:'Synthetic blog',status:'failed',enabled:false,next:'draft',approval:'page',expected:'version-1',directory:'/synthetic/articles/synthetic',seconds:600,engine:'codex',mode:'write',review_level:'balanced',existing:false,decisions:[],brief:{goal:'Explain a fixture',audience:'Authors'},notes:{},
    error:'The selected CLI failed. Check its sign-in and usage under Status → Check this computer, then try again.',reason:'cli',said:['Synthetic: not signed in.','Synthetic: run the login command.'],research:null,
    stages:[{stage:'outline',label:'Outline',path:'OUTLINE.md',status:'approved'},{stage:'draft',label:'Draft',path:'DRAFT.md',status:'pending'}]};
  const f=fixture((url,options)=>{requests.push(url);if(url==='/api/computer')return {checks:[{label:'Codex',status:'action',detail:'Sign-in needed',next_step:'Run codex login'}]};if(url==='/api/run-settings')return {defaults:{engine:'codex',seconds:600,research:'none',tone:'Clear',author:''},workspace:'/synthetic',shared_before:{}};return {items:[],total:0};});f.loadRunner();
  const nodes=()=>descendants(f.get('studio-page')),text=()=>nodes().map(e=>e.textContent);
  f.set('found',failed);f.run("studio.screen='run';studio.id=found.id;sRun(found)");
  assert.ok(text().includes(failed.error),'the error names Status → Check this computer');
  const said=nodes().find(e=>e.tagName==='details'&&e.children[0]?.textContent==='What the assistant said');
  assert.ok(said,'what the assistant said sits under its own disclosure: '+text().join('|'));
  assert.ok(descendants(said).some(e=>e.textContent==='Synthetic: not signed in.\nSynthetic: run the login command.'));
  assert.ok(descendants(said).some(e=>/kept on this computer only/.test(e.textContent)));
  const status=nodes().find(e=>e.tagName==='button'&&e.textContent==='Open Status');assert.ok(status,'a CLI failure offers Status');
  await status.listeners.click();
  assert.equal(f.get('title').textContent,'Status');assert.ok(requests.includes('/api/computer'));
  // Without lines there is nothing to disclose, and Status is still offered.
  f.set('found',{...failed,said:null});f.run("studio.screen='run';sRun(found)");
  assert.equal(nodes().some(e=>e.tagName==='details'&&e.children[0]?.textContent==='What the assistant said'),false);
  assert.ok(nodes().some(e=>e.textContent==='Open Status'));
  // Out of time: the error names the limit, the page says where it lives, beside more time.
  f.set('found',{...failed,reason:'time-limit',said:null,error:'This step ran out of the time a step may take (10 minutes).'});f.run('sRun(found)');
  assert.ok(text().includes('This step ran out of the time a step may take (10 minutes).'));
  assert.ok(text().includes('The limit is in Settings → Step time limit and applies to blogs started after a change. Try again with more time doubles it to 20 minutes for this blog.'),text().join('|'));
  assert.ok(f.get('actions').children.some(e=>e.textContent==='Try again with more time'));
  assert.equal(nodes().some(e=>e.textContent==='Open Status'),false,'a time limit is not a sign-in problem');
  // The words follow the limit exactly, and nothing doubles past the longest a step may take.
  for(const [seconds,words,retry] of [[90,'Try again with more time doubles it to 3 minutes for this blog.','with the same 1.5-minute limit'],[45,'Try again with more time doubles it to 1.5 minutes for this blog.','with the same 45-second limit'],[2400,'Try again with more time raises it to 60 minutes for this blog.','with the same 40-minute limit']]){
    f.set('found',{...failed,seconds,reason:'time-limit',said:null,error:'This step ran out of the time a step may take.'});f.run('sRun(found)');
    assert.ok(text().includes('The limit is in Settings → Step time limit and applies to blogs started after a change. '+words),seconds+': '+text().join('|'));
    assert.ok(text().some(t=>t.includes(retry)),seconds+': '+text().join('|'));
    assert.ok(f.get('actions').children.some(e=>e.textContent==='Try again with more time'));}
  f.set('found',{...failed,seconds:3600,reason:'time-limit',said:null,error:'This step ran out of the time a step may take (60 minutes).'});f.run('sRun(found)');
  assert.ok(text().includes('The limit is in Settings → Step time limit and applies to blogs started after a change. 60 minutes is the longest a step may take.'),text().join('|'));
  assert.equal(f.get('actions').children.some(e=>e.textContent==='Try again with more time'),false,'no more time past the longest');
  assert.equal(f.get('actions').children.find(e=>e.textContent==='Try again').className,'button button-filled');
  // First-run setup: Writing preferences open, and an assistant that is not installed marked.
  f.run("studio.options={agents:{codex:false,claude:true}};studio.settings={defaults:{engine:'codex',seconds:600,research:'none',tone:'Clear',author:''},workspace:'/synthetic',shared_before:{}};studio.team={};studio.brand=null;sSettings(true)");
  const preferences=()=>nodes().find(e=>e.tagName==='details'&&e.children[0]?.textContent==='Writing preferences');
  assert.equal(preferences().open,true,'setup opens Writing preferences');
  assert.ok(descendants(preferences()).some(e=>e.textContent==='Codex: Not installed — see Status.'),descendants(preferences()).map(e=>e.textContent).join('|'));
  assert.equal(descendants(preferences()).some(e=>/Claude Code: Not installed/.test(e.textContent)),false);
  f.run('sSettings(false)');assert.equal(!!preferences().open,false,'Settings keeps it folded');
  // The setup route reads which assistants are installed.
  f.run('studio.options=null');requests.length=0;await f.run("sRoute('setup')");
  assert.ok(requests.includes('/api/run-options'),requests.join('|'));
  // The start form says so before a step fails.
  const defaults={engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''};f.set('defaults',defaults);
  f.run("studio.options={settings:{defaults,review_level:'balanced'},sources:[],profiles:[],agents:{codex:false,claude:true}};studio.screen='new';studio.draft={...defaults,step:1,id:'',title:'A synthetic blog',goal:'Explain',audience:'Authors',profile:'',sources:[],manuscript:'',mode:'write',minutes:'10',operation:'a'.repeat(32)};sWizard()");
  assert.ok(text().includes('Codex: Not installed — see Status. Every step stops until it is.'),text().join('|'));
}

async function phase3ResearchDefaults(){
  const sites=['https://blogs.vmware.com/tanzu','https://docs.example.com'],words={empty:'Choose where research may look: your documents, your sites or the public web.',no_documents:'No documents were given, so choose your sites or the public web for research, or add documents.',no_sites:'Choose at least one of your sites, or turn your sites off.'};
  const defaults={engine:'codex',seconds:600,research:{documents:true,sites:true,web:false},stop:'package',tone:'Clear',author:''};
  const f=fixture(url=>url==='/api/run-options'?{settings:{defaults,review_level:'balanced',research_sites:sites,research_words:words},sources:[],profiles:[],agents:{codex:true}}:{items:[],total:0});
  f.loadRunner();
  const mine={research_from:{documents:true,sites,web:false}};
  for(const [entry,want]of [['write',mine],['outline',mine],['ideas',{research:'none'}],['revise',{research:'none'}],['review',{research:'none'}],['from-files',{research_from:{documents:true,sites:[],web:false}}]]){
    await f.run(`newBlog('',null,'${entry}')`);
    assert.deepEqual(JSON.parse(f.run('JSON.stringify(sResearchPayload(studio.draft))')),want,'Home card takes the research default: '+entry);
  }
  f.run("studio.options.sources=[{id:'s1',status:'ready',purposes:['reference']},{id:'s2',status:'ready',purposes:['reference']}]");
  for(const [research,sources,want]of [['none',[],'No research.'],['supplied-only',['s1','s2'],'Research from your documents.'],['web-allowed',[],'Research from the public web.'],['web-allowed',['s1'],'Research from your documents and the public web.'],['supplied-only',[],'No research: no source is ticked.'],[{documents:true,sites:true,web:false},['s1'],'Research from your documents and 2 of your sites (blogs.vmware.com/tanzu, docs.example.com).'],[{documents:true,sites:true,web:true},[],'Research from 2 of your sites (blogs.vmware.com/tanzu, docs.example.com) and the public web.']]){
    f.set('draft',{mode:'write',research,sources,stop:'package'});
    assert.equal(f.run('sResearchWords(draft)'),want,'Ready to start says what research will run');
  }
  // Blog Studio's own default: your sites stay off until ticked, even with a shared list, on
  // the start screens, the files screen and Settings.
  const usual=fixture(url=>url==='/api/run-options'?{settings:{defaults:{...defaults,research:{documents:true,sites:false,web:false}},review_level:'balanced',research_sites:sites,research_words:words},sources:[],profiles:[],agents:{codex:true}}:{items:[],total:0});
  usual.loadRunner();
  for(const entry of ['write','outline','from-outline','from-files']){
    await usual.run(`newBlog('',null,'${entry}')`);
    assert.deepEqual(JSON.parse(usual.run('JSON.stringify(sResearchPayload(studio.draft))')),{research_from:{documents:true,sites:[],web:false}},'your sites are off by default: '+entry);
  }
  usual.run("studio.settings={defaults:{...studio.options.settings.defaults},workspace:'/synthetic',shared_before:{},review_level:'balanced',research_sites:studio.options.settings.research_sites};studio.team={};studio.brand=null;studio.screen='settings';sSettings()");
  assert.equal(descendants(usual.get('studio-page')).find(e=>e.id==='settings-research-sites').checked,false,'Settings keeps your sites off by default');
  assert.ok(descendants(usual.get('studio-page')).some(e=>/only pages under them are saved/.test(e.textContent)),'Settings says how your sites are searched');
  // More than five sites are named five at a time, as research_sites.summary() names them.
  assert.equal(f.run("sResearchSummary({documents:false,sites:['https://a.example/1','https://b.example','https://c.example','https://d.example','https://e.example','https://f.example','https://g.example'],web:false})"),'from 7 of your sites (a.example/1, b.example, c.example, d.example, e.example and 2 more)');
}

// Research from: your documents, your sites and/or the public web. The shared list is
// prefilled with a tick per site; a site added for this blog is checked by the server and
// sent with this blog only; an incomplete choice says the shared sentence and starts nothing.
async function researchFromJourney(){
  const sites=['https://blogs.vmware.com/tanzu','https://docs.example.com'],words={empty:'Choose where research may look: your documents, your sites or the public web.',no_documents:'No documents were given, so choose your sites or the public web for research, or add documents.',no_sites:'Choose at least one of your sites, or turn your sites off.'};
  const defaults={engine:'codex',seconds:600,research:{documents:true,sites:true,web:false},stop:'package',tone:'Clear',author:''},requests=[];
  const found={id:'written',title:'A synthetic blog',status:'queued',next:'research-plan',approval:'page',expected:'r1',enabled:true,directory:'/synthetic',seconds:600,engine:'codex',decisions:[],brief:{goal:'Explain',audience:'Authors'},stages:[]};
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url==='/api/run-options')return {settings:{defaults,review_level:'balanced',research_sites:sites,research_words:words},sources:[{id:'s1',name:'Specification',status:'ready',purposes:['reference']}],profiles:[],agents:{codex:true},styles:[]};
    if(url==='/api/research-site'){if(data.site.startsWith('http://'))return {__http:400,error:'"http://intranet.example": research sites use https only.'};return {site:'https://extra.example.org/guide',shown:'extra.example.org/guide'};}
    if(url==='/api/run-create'||url.startsWith('/api/run?'))return found;
    return {items:[],total:0};});
  f.loadRunner();
  const nodes=()=>descendants(f.get('studio-page')),byId=id=>nodes().find(e=>e.id===id),text=()=>nodes().map(e=>e.textContent),said=()=>nodes().filter(e=>e.className.split(' ').includes('research-scope')).map(e=>e.textContent);
  await f.run("newBlog('',null,'write')");
  for(const [id,value] of [['new-title','A synthetic blog'],['new-goal','Explain'],['new-audience','Authors']]){byId(id).value=value;byId(id).listeners.input();}
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  // Research from: ☑ your documents ☑ your sites (2) ☐ the public web, with Research it first on.
  assert.equal(byId('new-research-on').checked,true);
  assert.ok(text().includes('Research from:'),text().join('|'));
  assert.deepEqual(['documents','sites','web'].map(key=>byId('new-research-'+key).checked),[true,true,false]);
  assert.ok(text().includes('your sites (2)'),text().join('|'));
  assert.deepEqual([0,1].map(at=>byId('new-research-site-'+at).checked),[true,true],'the shared list is prefilled');
  const searching=()=>nodes().find(e=>e.className==='quiet site-search');
  assert.equal(searching().textContent,'Your sites are searched with the assistant’s web search; only pages under them are saved.');
  assert.equal(searching().parent.hidden,false,'said while your sites are ticked');
  assert.ok(text().includes('blogs.vmware.com/tanzu')&&text().includes('docs.example.com'));
  assert.ok(said().length>=2&&said().every(line=>line==='Research from 2 of your sites (blogs.vmware.com/tanzu, docs.example.com).'),said().join('|'));
  // Ticking a reference brings your documents in.
  const reference=nodes().find(e=>e.type==='checkbox'&&e.parent?.className==='source-choice');reference.checked=true;reference.listeners.change();
  assert.ok(said().every(line=>line==='Research from your documents and 2 of your sites (blogs.vmware.com/tanzu, docs.example.com).'),said().join('|'));
  // One site unticked, one added for this blog only.
  byId('new-research-site-1').checked=false;byId('new-research-site-1').listeners.change();
  assert.ok(text().includes('your sites (1)'),text().join('|'));
  const add=byId('new-research-add');add.value='http://intranet.example';add.listeners.input();
  await nodes().find(e=>e.textContent==='Add the site').listeners.click();
  assert.ok(text().includes('"http://intranet.example": research sites use https only.'),'the server refuses a bad site: '+text().join('|'));
  add.value='extra.example.org/guide/';add.listeners.input();
  await nodes().find(e=>e.textContent==='Add the site').listeners.click();
  assert.deepEqual(requests.filter(r=>r.url==='/api/research-site').at(-1).data,{site:'extra.example.org/guide/'});
  assert.equal(byId('new-research-site-2').checked,true,'an added site is ticked');
  assert.ok(text().includes(' · this piece of work only'));
  assert.ok(text().includes('your sites (2)'),text().join('|'));
  assert.ok(said().every(line=>line==='Research from your documents and 2 of your sites (blogs.vmware.com/tanzu, extra.example.org/guide).'),said().join('|'));
  // Return in the add field adds the site and never starts the blog.
  let prevented=false;byId('new-research-add').listeners.keydown({key:'Enter',preventDefault(){prevented=true;}});assert.equal(prevented,true);
  assert.equal(requests.some(r=>r.url==='/api/run-create'),false);
  // Nothing ticked, or your sites with none ticked: the shared sentences, and nothing starts.
  for(const key of ['documents','sites']){byId('new-research-'+key).checked=false;byId('new-research-'+key).listeners.change();}
  assert.ok(said().every(line=>line===words.empty),said().join('|'));
  assert.equal(searching().parent.hidden,true,'folded away with your sites off');
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.ok(text().includes(words.empty));assert.equal(requests.some(r=>r.url==='/api/run-create'),false,'nothing chosen starts nothing');
  byId('new-research-sites').checked=true;byId('new-research-sites').listeners.change();
  for(const at of [0,2]){byId('new-research-site-'+at).checked=false;byId('new-research-site-'+at).listeners.change();}
  assert.ok(said().every(line=>line===words.no_sites),said().join('|'));
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(requests.some(r=>r.url==='/api/run-create'),false,'your sites with none ticked starts nothing');
  // The added site and the public web go to the server.
  byId('new-research-site-2').checked=true;byId('new-research-site-2').listeners.change();
  byId('new-research-web').checked=true;byId('new-research-web').listeners.change();
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const created=requests.find(r=>r.url==='/api/run-create').data;
  assert.deepEqual(created.research_from,{documents:false,sites:['https://extra.example.org/guide'],web:true});assert.equal('research' in created,false);
  assert.deepEqual(requests.filter(r=>r.data).map(r=>r.url),['/api/research-site','/api/research-site','/api/run-create'],'the shared list is not changed');
  // Research it first off: no research, and the choices fold away.
  await f.run("newBlog('',null,'write')");
  f.run("studio.draft.step=1;studio.draft.title='A synthetic blog';studio.draft.goal='Explain';studio.draft.audience='Authors';sWizard()");
  byId('new-research-on').checked=false;byId('new-research-on').listeners.change();
  assert.equal(nodes().find(e=>e.tagName==='fieldset'&&e.className==='research-choices').hidden,true);
  assert.ok(said().every(line=>line==='No research.'),said().join('|'));
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(requests.filter(r=>r.url==='/api/run-create').at(-1).data.research,'none');
  // The files screen: the files are your documents; your sites or the web add research steps.
  await f.run("newBlog('',null,'from-files')");
  f.run("studio.draft.files=[{id:'m1',filename:'notes.md',state:'ready',chars:1200,note:'',link:'',role:'material'}];sWizard()");
  assert.deepEqual(['documents','sites','web'].map(key=>byId('files-research-'+key).checked),[true,false,false]);
  assert.equal(byId('files-research-on'),undefined,'the files screen has no off switch: the files are always read');
  assert.ok(text().includes('Your files are read at every step. Your sites or the public web add research before the outline.'));
  assert.ok(said().every(line=>line==='Research from your documents.'),said().join('|'));
  byId('files-research-sites').checked=true;byId('files-research-sites').listeners.change();
  assert.ok(said().every(line=>line==='Research from your documents and 2 of your sites (blogs.vmware.com/tanzu, docs.example.com).'),said().join('|'));
  assert.ok(f.run("sPipeline(studio.draft).includes('research')"),'your sites add research before the outline');
  await nodes().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  assert.deepEqual(requests.filter(r=>r.url==='/api/run-create').at(-1).data.research_from,{documents:true,sites,web:false});
  // The run and its research gate name the sites that kept pages out.
  const gate={...found,status:'waiting-for-approval',next:'research',research_says:'Research from 1 of your sites (blogs.vmware.com/tanzu).',research:{contract:true,kept:false,rounds:3,refusal:null,outside:'2 pages were outside your sites (blogs.vmware.com/tanzu) and were not saved.'},stages:[{stage:'research',label:'Research findings',path:'derived/blog-research.md',status:'draft'}]};
  f.set('found',gate);f.run('sRun(found)');
  assert.ok(text().includes('Research from 1 of your sites (blogs.vmware.com/tanzu).'),'About this blog says where research looked');
  f.set('shown',{stage:'research',label:'Research findings',content:'# Research',checks:[],bundle:[],notes:'',expected:'r1',research:{brief:'# Brief',check:{said:'Checked.',note:''},gaps:['A synthetic gap.'],sources:{partial:[]},read:'',findings:[],questions:[],report:'',evidence:''}});
  f.run("studio.found=found;studio.shown=shown;sGate(found,shown)");
  assert.ok(text().includes('2 pages were outside your sites (blogs.vmware.com/tanzu) and were not saved.'),text().join('|'));
  f.set('found',{...gate,status:'failed',error:'Research could not produce valid evidence.',research:{...gate.research,refusal:{rounds:3,count:1,cause:null,groups:[]}}});f.run('sRun(found)');
  assert.ok(text().includes('2 pages were outside your sites (blogs.vmware.com/tanzu) and were not saved.'),'the refusal names the sites: '+text().join('|'));
}

async function phase5BringResearchUpToDate(){
  const calls=[];
  const found={id:'synthetic',title:'Synthetic',status:'waiting-for-approval',next:'research',approval:'page',expected:'v1',enabled:true,mode:'write',review_level:'step_by_step',brief:{},notes:{},research_price:{words:'Asking for changes runs the whole research again.',refresh:'Re-reads the sources and checks the report again: its last try took 48 minutes and $9.80.'},stages:[{stage:'research',label:'Research',path:'derived/blog-research.md',status:'draft'},{stage:'outline',label:'Outline',status:'pending'}]};
  const f=fixture((route,options)=>{calls.push({route,data:options?.body?JSON.parse(options.body):null});return {...found,status:'queued'};});f.loadRunner();
  f.set('found',found);f.run("studio.screen='gate';studio.id=found.id;studio.found=found;sChanges(found,'research')");
  const sheet=()=>descendants(f.get('sheet'));
  const box=sheet().find(e=>e.id==='change-refresh');
  assert.ok(box,'the research sheet offers to bring the evidence up to date');
  assert.equal(box.checked,false,'off unless asked');
  assert.ok(sheet().some(e=>e.textContent==='Bring the evidence up to date'));
  assert.ok(sheet().some(e=>e.textContent===found.research_price.refresh));
  box.checked=true;box.listeners.change();
  await sheet().find(e=>e.tagName==='form').listeners.submit({preventDefault(){}});
  const sent=calls.find(r=>r.route==='/api/run-changes');
  assert.ok(sent,'the change is sent');assert.equal(sent.data.stage,'research');assert.equal(sent.data.refresh,true);
  f.run('sCloseSheet()');
  f.run("sChanges(found,'outline')");
  const field=sheet().find(e=>e.className==='field'&&descendants(e).some(c=>c.id==='change-refresh'));
  assert.equal(field.hidden,true,'only the research is brought up to date');
}

async function phase3ResearchAccount(){
  const f=fixture();f.loadRunner();
  const account={brief:'# Prioritized handoff',report:'# Full report',evidence:'# Evidence',check:{said:'Independent check accepted.',note:'Honest coverage.',unread:[]},gaps:['Unknown range.'],sources:{partial:[{title:'Public page',note:'Pages 1 to 4 only.'}]},read:'3 sources: 2 of yours, 1 public.',questions:[{id:'q',question:'Minimum?',findings:['q--one']}],findings:[{id:'q--one',title:'Capacity condition',summary:'Bounded finding.'}],unplanned:[]};
  const found={id:'synthetic',title:'Synthetic',status:'waiting-for-approval',next:'research',approval:'page',expected:'v1',enabled:true,mode:'write',review_level:'step_by_step',brief:{},notes:{},research_price:{words:'Asking for changes runs the whole research again.'},stages:[{stage:'research',label:'Research',path:'derived/blog-research.md',status:'draft'},{stage:'outline',label:'Outline',status:'pending'}]};
  const shown={id:'synthetic',stage:'research',label:'Research',status:'draft',content:'# Full report',notes:'',expected:'v1',checks:[],bundle:[],previous:null,diff:[],research:account};
  f.set('found',found);f.set('shown',shown);f.run("studio.screen='gate';studio.id=found.id;studio.found=found;sGate(found,shown)");
  const texts=()=>descendants(f.get('studio-page')).map(e=>e.textContent).join(' ');
  for(const words of ['Prioritized handoff','Independent check accepted.','Honest coverage.','Unknown range.','Pages 1 to 4 only.','3 sources: 2 of yours, 1 public.','Your questions','Minimum?','Capacity condition'])assert.ok(texts().includes(words),words+': '+texts());
  assert.equal(texts().includes('No assistant note was submitted'),false);
  assert.ok(texts().includes('Read the research brief, its limits and the independent check.'));
  assert.equal(texts().includes('to act on one, ask for changes to the draft'),false);
  f.run("sChanges(found,'research')");
  assert.ok(descendants(f.get('sheet')).some(e=>e.textContent===found.research_price.words));
  const select=descendants(f.get('sheet')).find(e=>e.id==='change-stage');select.value='outline';select.listeners.change();
  assert.equal(descendants(f.get('sheet')).some(e=>e.textContent===found.research_price.words),false);
  f.run('sCloseSheet()');
  for(const [stage,words]of [['research-plan','Read the questions this research will answer.'],['claims-map','Read the claims mapped to your supplied material.']]){
    f.set('found',{...found,next:stage,stages:[{stage,label:stage,status:'draft'},{stage:'outline',label:'Outline',status:'pending'}]});
    f.set('shown',{...shown,stage,label:stage,research:null});
    f.run('sGate(found,shown)');
    assert.ok(texts().includes(words),stage+' explains its own decision');
    assert.equal(texts().includes('to act on one, ask for changes to the draft'),false);
  }
}

async function phase3ClaimsMap(){const f=fixture();f.loadRunner();
  f.run("studio.options={sources:[{id:'s1',status:'ready',purposes:['reference']},{id:'voice',status:'ready',purposes:['voice-sample']},{id:'example',status:'ready',purposes:['inspiration']}]} ");
  f.set('draft',{mode:'write',research:'supplied-only',sources:['s1'],stop:'package'});
  assert.deepEqual(Array.from(f.run('sPipeline(draft)')),['claims-map','outline','draft','review','package']);
  assert.equal(f.run("sStopWords('balanced',sPipeline(draft),'write')"),'Balanced: it stops for the outline and the handoff');
  assert.ok(f.run("sStopWords('step_by_step',sPipeline(draft),'write')").includes('the claims in your material'));
  f.set('draft',{mode:'from-files',research:'supplied-only',sources:['s1'],start:'point',stop:'package'});
  assert.equal(f.run("sPipeline(draft).includes('claims-map')"),false);
  for(const sources of [['voice'],['example']]){
    f.set('draft',{mode:'write',research:'supplied-only',sources,stop:'package'});
    assert.equal(f.run("sPipeline(draft).includes('claims-map')"),false,'voice/example is not factual material');
  }
  f.set('draft',{mode:'write',research:'supplied-only',sources:['s1','voice'],files:[{id:'example',state:'ready',role:'inspiration'}],stop:'package'});
  assert.equal(f.run('sResearchWords(draft)'),'Research from your documents.','a voice sample or an example is not one of your documents');
  f.set('draft',{mode:'write',research:'supplied-only',sources:[],files:[{id:'owned',filename:'notes.md',state:'ready',role:'material',chars:40}],stop:'package'});
  f.run("document.getElementById('studio-page').replaceChildren(sNode('p','stops-line',sStops(draft)),sFilesCard(draft,sNode('p'),()=>{},()=>{}))");
  const stops=f.get('studio-page').querySelector('.stops-line');
  assert.ok(stops.textContent.includes('claims in your material'));
  const role=descendants(f.get('studio-page')).find(node=>node.id==='files-role-owned');
  role.value='inspiration';await role.listeners.change();
  assert.equal(stops.textContent.includes('claims in your material'),false,'changing a file to an example refreshes the predicted stops');
}

function deskView(extra={}){
  return {id:'desk-blog',revision:1,title:'A synthetic title',opening:'An opening paragraph.',sections:[{id:'aaaaaaaa',heading:'First part',brief:'',text:'First text here.'},{id:'bbbbbbbb',heading:'Second part',brief:'',text:'Second text.'},{id:'cccccccc',heading:'Third part',brief:'',text:'Third text.'}],tone:'Plain',gaps:[],markdown:'# A synthetic title\n',jobs:[],working:null,versions:{},run:false,google:null,publication:null,style_name:null,source_names:[],expected:'session-v1',...extra};
}
async function deskJourneys(){
  const requests=[],timers=[];let view=deskView(),refuse=false;
  const f=fixture((url,options)=>{
    const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url==='/api/run-options')return {settings:{defaults:{engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''}},sources:[],profiles:[],styles:[{id:'how-to',name:'How-to and tutorial',status:'confirmed',kind:'seed'}],agents:{codex:true}};
    if(url==='/api/desk-create')return {...view,first_pass_problem:null};
    if(url.startsWith('/api/desk?'))return view;
    if(url==='/api/desk-save'){if(refuse)return {__http:409,error:'This draft changed since you opened it. Reload to see the latest.'};view={...view,revision:view.revision+1,versions:{[data.part]:1},sections:view.sections.map(s=>s.id===data.part?{...s,text:data.text}:s)};return view;}
    if(url==='/api/desk-note'){view={...view,working:{id:'j1',kind:'desk-section',status:'working',part:data.part,note:data.note}};return view;}
    if(url==='/api/desk-selection'){view={...view,working:{id:'j2',kind:'desk-selection',status:'queued',part:data.part}};return view;}
    if(url==='/api/desk-revise'){view={...view,working:{id:'j3',kind:'desk-revise-all',status:'queued',busy:true,part:'aaaaaaaa',chain:'c1',index:0,total:3}};return view;}
    if(url==='/api/desk-stop'){view={...view,working:null};return view;}
    if(url==='/api/desk-share')return {id:data.id,shared:true};
    if(url.startsWith('/api/desk-versions?'))return {id:'desk-blog',part:'aaaaaaaa',versions:[{at:new Date().toISOString(),source:'rewrite',text:'First old text here.',words:4}]};
    if(url==='/api/desk-restore'){view={...view,revision:view.revision+1,sections:view.sections.map(s=>s.id===data.part?{...s,text:'First old text here.'}:s)};return view;}
    return {items:[],total:0};
  });
  f.loadRunner();f.set('setTimeout',fn=>{timers.push(fn);return timers.length;});f.set('clearTimeout',()=>{});
  const nodes=()=>descendants(f.get('studio-page')),tick=async()=>{for(const fn of timers.splice(0))await fn();};
  const card=part=>nodes().find(n=>n.dataset?.part===part),inside=(node,test)=>descendants(node).find(test);
  // 1. A pasted draft starts on the desk, with a card for the title, the opening and each section.
  await f.run("sDeskBegin({have:'draft'})");
  assert.equal(f.get('title').textContent,'New blog');
  await nodes().find(n=>n.className==='pick-card'&&n.textContent==='Something else').listeners.click();
  assert.ok(!nodes().some(n=>n.id==='desk-sites'),'research is for new writing, not a draft brought to edit');
  await nodes().find(n=>n.tagName==='form').listeners.submit({preventDefault(){}});
  const paste=nodes().find(n=>n.id==='desk-manuscript');paste.value='# A synthetic title\n\nAn opening paragraph.\n\n## First part\n\nFirst text here.';paste.listeners.input();
  await nodes().find(n=>n.tagName==='form').listeners.submit({preventDefault(){}});
  const created=requests.find(r=>r.url==='/api/desk-create').data;
  assert.match(created.operation,/^[0-9a-f]{32}$/);assert.equal(created.first_pass,'leave');assert.equal(created.tone,'Clear');assert.match(created.manuscript,/## First part/);
  assert.equal(f.run('studio.screen'),'desk');
  assert.equal(nodes().filter(n=>n.className.split(' ').includes('desk-part')).length,5);
  assert.equal(nodes().filter(n=>n.className==='card-title').map(n=>n.textContent).slice(1,-1).join('|'),'Title|Opening|First part|Second part|Third part');
  // 2. Typing saves a second later, against the revision seen and this editing session.
  const text=inside(card('aaaaaaaa'),n=>n.tagName==='textarea');text.value='First text here, edited.';text.listeners.input();
  assert.match(nodes().find(n=>/desk-save-state/.test(n.className)).textContent,/Saving/);
  await tick();
  const saved=requests.find(r=>r.url==='/api/desk-save').data;
  assert.deepEqual([saved.part,saved.seen,saved.text],['aaaaaaaa',1,'First text here, edited.']);assert.match(saved.session,/^[0-9a-f]{32}$/);
  assert.equal(nodes().find(n=>/desk-save-state/.test(n.className)).textContent,'Saved.');
  // 3. A note rewrites the section; its card says it is working until the result lands.
  const note=inside(card('bbbbbbbb'),n=>/desk-note-text/.test(n.className));const rewrite=()=>inside(card('bbbbbbbb'),n=>n.tagName==='button'&&['Rewrite','Write again'].includes(n.textContent));
  assert.equal(rewrite().textContent,'Write again');
  note.value='Add an example.';note.listeners.input();assert.equal(rewrite().textContent,'Rewrite');
  await rewrite().listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/desk-note').data,{id:'desk-blog',seen:2,part:'bbbbbbbb',note:'Add an example.'});
  assert.ok(descendants(card('bbbbbbbb')).some(n=>n.textContent==='Working on this section'));
  assert.ok(descendants(card('bbbbbbbb')).some(n=>n.textContent==='Your note: Add an example.'));
  assert.equal(inside(card('bbbbbbbb'),n=>n.tagName==='textarea').readOnly,true);
  assert.equal(inside(card('aaaaaaaa'),n=>n.tagName==='textarea').readOnly,false);
  assert.match(f.get('above').textContent,/Rewriting “Second part”/);
  view={...view,revision:3,working:null,jobs:[{id:'j1',kind:'desk-section',status:'ready',applied:true,error:''}],sections:view.sections.map(s=>s.id==='bbbbbbbb'?{...s,text:'Second text, for example.'}:s),versions:{aaaaaaaa:1,bbbbbbbb:1}};
  const untouched=card('cccccccc'),typing=card('aaaaaaaa'),rewritten=card('bbbbbbbb');
  await tick();
  // Only the rewritten card is drawn again; the others, and whatever is typed in them, stay.
  assert.equal(card('cccccccc'),untouched);assert.equal(card('aaaaaaaa'),typing);assert.notEqual(card('bbbbbbbb'),rewritten);
  assert.equal(inside(card('bbbbbbbb'),n=>n.tagName==='textarea').value,'Second text, for example.');
  assert.ok(!descendants(card('bbbbbbbb')).some(n=>n.textContent==='Working on this section'));
  // 4. Selecting text shows the bar; Shorten sends the exact passage.
  // A selection with spaces around it is sent without them, with where it starts.
  const first=inside(card('aaaaaaaa'),n=>n.tagName==='textarea');first.selectionStart=0;first.selectionEnd=11;first.listeners.select();
  const bar=nodes().find(n=>/desk-selection/.test(n.className));assert.equal(bar.hidden,false);
  assert.deepEqual(bar.children.map(n=>n.textContent),['Rephrase','Shorten','Expand','Fix','Ask…']);
  await bar.children.find(n=>n.textContent==='Ask…').listeners.click();
  assert.equal(bar.children[0].tagName,'input');
  await bar.children.find(n=>n.textContent==='Cancel').listeners.click();
  first.listeners.select();
  await bar.children.find(n=>n.textContent==='Shorten').listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/desk-selection').data,{id:'desk-blog',seen:3,part:'aaaaaaaa',text:'First text',start:0,action:'shorten'});
  await f.run('sDeskRender(studio.desk)');
  await descendants(f.get('actions')).find(n=>n.textContent==='Stop').listeners.click();
  assert.equal(requests.at(-1).url,'/api/desk-stop');
  // 5. History lists the kept versions; Compare marks what changed; Restore posts it.
  const history=inside(card('aaaaaaaa'),n=>n.tagName==='button'&&/^History/.test(n.textContent));assert.equal(history.textContent,'History (1)');
  await history.listeners.click();
  const sheet=()=>descendants(f.get('sheet'));
  assert.ok(sheet().some(n=>n.textContent==='Before a rewrite'));
  await sheet().find(n=>n.textContent==='Compare').listeners.click();
  assert.equal(sheet().find(n=>n.tagName==='del').textContent.trim(),'old');
  assert.ok(sheet().some(n=>n.tagName==='ins'&&/edited/.test(n.textContent)));
  await sheet().find(n=>n.textContent==='Restore').listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/desk-restore').data,{id:'desk-blog',seen:3,part:'aaaaaaaa',index:0});
  assert.equal(inside(card('aaaaaaaa'),n=>n.tagName==='textarea').value,'First old text here.');
  // 6. A save refused as outdated says so and offers Reload.
  refuse=true;const third=inside(card('cccccccc'),n=>n.tagName==='textarea');third.value='Changed elsewhere.';third.listeners.input();await tick();
  const state=nodes().find(n=>/desk-save-state/.test(n.className));
  assert.match(descendants(state).map(n=>n.textContent).join(' '),/This draft changed/);
  assert.ok(descendants(state).some(n=>n.textContent==='Reload'));
  refuse=false;await descendants(state).find(n=>n.textContent==='Reload').listeners.click();
  // 7. A note for the whole draft revises it.
  const whole=nodes().find(n=>n.id==='desk-whole-note');whole.value='Tighten throughout.';whole.listeners.input();
  await nodes().find(n=>n.textContent==='Revise the draft').listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/desk-revise').data,{id:'desk-blog',seen:view.revision,note:'Tighten throughout.'});
  // Section by section: the one being revised works, and the toolbar says which of how many.
  assert.match(card('aaaaaaaa').className,/desk-working/);assert.doesNotMatch(card('bbbbbbbb').className,/desk-working/);
  assert.equal(f.get('above').textContent,'Revising section 1 of 3…');
  // A section that failed is named once the note is done; the others were revised.
  view={...view,working:null,jobs:[{id:'j3',kind:'desk-revise-all',status:'failed',chain:'c1',index:0,total:3,error:'The assistant stopped.'},{id:'j4',kind:'desk-revise-all',status:'ready',chain:'c1',index:1,total:3,applied:true,error:''}],chain:{total:3,revised:2,working:false,problems:[{part:'aaaaaaaa',heading:'First part',error:'The assistant stopped.'}]}};
  f.set('next',view);await f.run('studio.desk.view=next;sDeskRender(studio.desk)');
  assert.ok(nodes().some(n=>n.textContent==='Revised 2 of 3 sections for your note. These were not:'));
  assert.ok(nodes().some(n=>n.textContent==='“First part”: The assistant stopped.'));
  // The page-wide poll leaves the desk to its own: it never redraws another screen over it.
  const before=f.get('studio-page').children.length;await f.run('sPoll()');assert.equal(f.get('studio-page').children.length,before);assert.equal(f.get('title').textContent,'A synthetic title');
  // Word comparison: a long text falls back to the two texts side by side.
  assert.equal(f.run("diffWords('a '.repeat(5000),'b')"),null);
  assert.deepEqual(JSON.parse(f.run("JSON.stringify(diffWords('one two three','one 2 three'))")).map(p=>p.op),['same','removed','added','same']);
}
async function deskLeaveShares(){
  const requests=[];const f=fixture((url,options)=>{requests.push({url,options,data:options?.body?JSON.parse(options.body):null});if(url.startsWith('/api/desk?'))return deskView();return {items:[],total:0,settings:{defaults:{}},sources:[]};});
  f.loadRunner();await f.run("sRoute('desk','desk-blog')");
  await f.run("sRoute('blogs')");await new Promise(r=>setImmediate(r));
  const share=requests.find(r=>r.url==='/api/desk-share');
  assert.deepEqual(share?.data,{id:'desk-blog'});assert.equal(share.options.keepalive,true);assert.equal(share.options.method,'POST');
}
async function deskReturnAndGoogle(){
  const requests=[],timers=[];let view=deskView();
  const f=fixture((url,options)=>{const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    if(url==='/api/run-options')return {settings:{defaults:{tone:'Clear'}},sources:[],styles:[]};
    if(url==='/api/google-preview')return {status:'already-linked',id:'desk-blog'};
    if(url.startsWith('/api/desk?'))return view;if(url==='/api/desk-save'||url==='/api/desk-share')return view;return {items:[],total:0};});
  f.loadRunner();f.set('setTimeout',fn=>{timers.push(fn);return timers.length;});f.set('clearTimeout',()=>{});
  const nodes=()=>descendants(f.get('studio-page')),card=part=>nodes().find(n=>n.dataset?.part===part);
  // Typing, leaving before it saves, and coming back: the desk shows what the server has.
  await f.run("sRoute('desk','desk-blog')");
  const text=descendants(card('cccccccc')).find(n=>n.tagName==='textarea');text.value='Typed, then left.';text.listeners.input();
  timers.length=0;f.run("studio.desk.pending.cccccccc.timer=0");
  await f.run("studio.screen='blogs';studio.desk.pending={cccccccc:{text:'Typed, then left.'}}");
  await f.run("sRoute('desk','desk-blog')");
  assert.equal(descendants(card('cccccccc')).find(n=>n.tagName==='textarea').value,'Third text.');
  assert.deepEqual(JSON.parse(f.run('JSON.stringify(studio.desk.pending)')),{});
  // A Google Doc already brought in as a desk blog opens that desk.
  await f.run("sRoute('desk-start')");
  await nodes().find(n=>n.className==='pick-card'&&n.textContent==='Something else').listeners.click();
  await nodes().find(n=>n.tagName==='form').listeners.submit({preventDefault(){}});
  await nodes().find(n=>n.textContent==='A draft').listeners.click();
  await nodes().find(n=>n.textContent==='Google Doc').listeners.click();
  const url=nodes().find(n=>n.id==='desk-google');url.value='https://docs.google.com/document/d/abc/edit';url.listeners.input();
  await nodes().find(n=>n.tagName==='form').listeners.submit({preventDefault(){}});
  assert.equal(f.run('studio.screen'),'desk');assert.ok(!requests.some(r=>r.url==='/api/desk-create'));
  // On a phone the sources fold under the draft.
  f.run("window.matchMedia=()=>({matches:true})");await f.run("sDeskRender(studio.desk)");
  assert.ok(nodes().some(n=>n.tagName==='details'&&/desk-aside/.test(n.className)));
}
async function deskOpenFinished(){
  const requests=[];const found={id:'finished',title:'Finished run',stages:[{stage:'draft'}],complete:true,desk_open:true,on_desk:false};
  const f=fixture((url,options)=>{requests.push({url,data:options?.body?JSON.parse(options.body):null});if(url==='/api/desk-open')return deskView({id:'finished',run:true});if(url.startsWith('/api/desk?'))return deskView({id:'finished',run:true});return {items:[]};});
  f.loadRunner();f.set('done',found);f.run("studio.screen='run';studio.id=done.id;sPage(sDoneCard(done))");
  const nodes=()=>descendants(f.get('studio-page'));
  const open=nodes().find(n=>n.textContent==='Open on the desk');assert.ok(open,'a finished run offers Open on the desk');
  await open.listeners.click();
  assert.deepEqual(requests.find(r=>r.url==='/api/desk-open').data,{id:'finished'});
  assert.equal(f.run('studio.screen'),'desk');
  assert.ok(nodes().some(n=>n.textContent==='Open the step-by-step run'));
  f.set('later',{...found,desk_open:false});f.run("studio.screen='run';sPage(sDoneCard(later))");
  assert.ok(!nodes().some(n=>n.textContent==='Open on the desk'));
  // Once on the desk, the run page reads as it ended: Open on the desk and nothing to act on.
  f.set('onDesk',{...found,on_desk:true,status:'on-desk',stages:[{stage:'draft',label:'Draft',status:'approved'}]});f.run("studio.screen='run';sRun(onDesk)");
  const shown=[...nodes(),...descendants(f.get('actions'))].map(n=>n.textContent);
  assert.ok(shown.includes('Open on the desk'));
  for(const label of ['Resume','Try again','Polish or edit the draft','Edit manuscript','Tools','Ask for changes','Continue'])assert.ok(!shown.includes(label),label);
}

// Phase 2 of the writing desk: the author and co-author starts, progress, the Outline tab and
// Add a source. Synthetic content only; the fake server answers as the desk routes do.
function deskStartFixture(answer=()=>null){
  const requests=[],timers=[];
  const f=fixture((url,options)=>{
    const data=options?.body?JSON.parse(options.body):null;requests.push({url,data});
    const given=answer(url,data);if(given!==null&&given!==undefined)return given;
    if(url==='/api/run-options')return {settings:{defaults:{engine:'codex',seconds:600,research:'none',stop:'package',tone:'Clear',author:''},research_sites:['https://docs.example.com']},sources:[],profiles:[],styles:[{id:'how-to',name:'How-to and tutorial',summary:'Prerequisites, numbered steps with checkpoints, a finished state, troubleshooting.',status:'confirmed',kind:'seed'},{id:'old',name:'Retired kind',status:'retired',kind:'learned'}],agents:{codex:true}};
    if(url==='/api/desk-share')return {id:data.id,shared:true};
    return {items:[],total:0};
  });
  f.loadRunner();f.set('setTimeout',fn=>{timers.push(fn);return timers.length;});f.set('clearTimeout',()=>{});
  const nodes=()=>descendants(f.get('studio-page')),tick=async()=>{for(const fn of timers.splice(0))await fn();};
  const sheet=()=>descendants(f.get('sheet')),byId=id=>nodes().find(n=>n.id===id);
  const type=(id,value)=>{const field=byId(id)||sheet().find(n=>n.id===id);field.value=value;field.listeners[field.tagName==='select'?'change':'input']();};
  const submit=()=>nodes().find(n=>n.tagName==='form').listeners.submit({preventDefault(){}});
  const click=async label=>{const found=nodes().find(n=>n.textContent===label&&n.listeners.click)||sheet().find(n=>n.textContent===label&&n.listeners.click)||descendants(f.get('actions')).find(n=>n.textContent===label&&n.listeners.click);assert.ok(found,'no '+label+' in '+nodes().map(n=>n.textContent).filter(Boolean).join('|'));await found.listeners.click();};
  return {f,requests,timers,nodes,tick,sheet,byId,type,submit,click};
}
function startView(extra={}){return deskView({id:'started',sections:[],opening:'',start:{way:'topic',steps:['research','outline','draft'],step:'research',job:'r1',started_at:new Date().toISOString(),ended_at:null,problem:'',open:'draft',minutes:14,phase:'',busy:true,status:'working',doing:'Researching'},working:{id:'r1',kind:'desk-research',status:'working',busy:true,part:'research'},...extra});}
async function deskTopicStart(){
  let polls=0;
  const angles=[{headline:'Retries that keep work',point:'A retry resumes from the last checkpoint.',audience:'Operators'},{headline:'Why jobs stop',point:'Most stops are timeouts.',audience:'Developers'},{headline:'A checkpoint primer',point:'Checkpoints are cheap.',audience:'Newcomers'}];
  const t=deskStartFixture((url,data)=>{
    if(url==='/api/upload')return {files:[{filename:'notes.md',source:{id:'s1'},state:'ready',chars:120,note:''}]};
    if(url==='/api/source-keep')return {id:data.id,kept:data.keep};
    if(url==='/api/desk-angles')return {operation:data.operation,job:'a1',status:'queued',busy:true,angles:[],error:''};
    if(url.startsWith('/api/desk-angles?')){polls++;return {operation:new URLSearchParams(url.split('?')[1]).get('operation'),job:'a1',status:'ready',busy:false,angles,error:''};}
    if(url==='/api/desk-create')return {...startView(),first_pass_problem:null};
    if(url.startsWith('/api/desk?'))return startView();
    return null;
  });
  // Home's tasks open the new start with what the person brings already chosen.
  await t.f.run("sRoute('home')");
  await t.click('Write about a topic');
  assert.equal(t.f.run('studio.screen'),'desk-start');assert.equal(t.f.run('studio.deskStart.have'),'topic');
  assert.equal(t.f.get('title').textContent,'New blog');
  // 1. A card per kind of post, with its usual shape; a retired one is not offered.
  const kinds=t.nodes().filter(n=>n.className==='pick-card').map(n=>n.textContent);
  assert.deepEqual(kinds,['How-to and tutorial','Something else']);
  assert.ok(t.nodes().some(n=>n.textContent==='Prerequisites, numbered steps with checkpoints, a finished state, troubleshooting.'));
  await t.nodes().find(n=>n.className==='pick-card'&&n.textContent==='How-to and tutorial').listeners.click();
  // 2. Sources and settings: sources stay with this blog unless kept; research off by default.
  assert.equal(t.f.run('studio.deskStart.step'),1);
  assert.equal(t.byId('files-keep').checked,false,'files stay with this blog by default');
  assert.ok(t.byId('files-link'),'a link');assert.ok(t.nodes().some(n=>n.textContent==='What the roles mean'),'the roles in a fold');
  assert.ok(!t.nodes().some(n=>/^Applies to files you add next/.test(n.textContent)),'one short line under Keep');
  assert.equal(t.byId('desk-sites').checked,false);assert.equal(t.byId('desk-web').checked,false);
  const picker=t.byId('files-input');picker.files=[{name:'notes.md',size:20,arrayBuffer:async()=>new TextEncoder().encode('Synthetic notes.').buffer}];await picker.listeners.change();
  assert.equal(t.requests.find(r=>r.url==='/api/upload').data.keep,false,'saved with this blog only');
  assert.ok(t.nodes().some(n=>/· Just this blog$/.test(n.textContent)));
  await t.nodes().find(n=>n.attributes['aria-label']==='Keep in the team library · notes.md').listeners.click();
  assert.ok(t.nodes().some(n=>/· To the team library$/.test(n.textContent)));
  assert.ok(!t.requests.some(r=>r.url==='/api/source-keep'),'nothing reaches the library before Start');
  t.byId('desk-sites').checked=true;t.byId('desk-sites').listeners.change();
  assert.ok(t.nodes().some(n=>n.textContent==='docs.example.com'),'the saved site list');
  t.byId('desk-web').checked=true;t.byId('desk-web').listeners.change();
  t.type('desk-length','deep');t.type('desk-tone','Warm');
  await t.submit();
  // 3. Just a topic: the point typed, or three angles that read the sources already chosen.
  assert.equal(t.f.run('studio.deskStart.step'),2);
  assert.ok(!t.nodes().some(n=>n.textContent==='Add sources first'));
  t.type('desk-title','Retries');t.type('desk-audience','Operators');t.type('desk-point','Keep the work.');
  await t.click('Suggest three angles');
  const asked=t.requests.find(r=>r.url==='/api/desk-angles').data;
  assert.match(asked.operation,/^[0-9a-f]{32}$/);
  assert.deepEqual({...asked,operation:undefined},{operation:undefined,title:'Retries',point:'Keep the work.',audience:'Operators',style:'how-to',tone:'Warm',sources:['s1'],library:[]});
  assert.ok(t.nodes().some(n=>/Finding three angles/.test(n.textContent)),'the page says the angles are coming');
  await t.tick();assert.equal(polls,1);
  const cards=t.nodes().filter(n=>/\bdesk-angle\b/.test(n.className));
  assert.equal(cards.length,3,'three angle cards');
  t.type('desk-angle-1-headline','Why long jobs stop');
  await descendants(cards[1]).find(n=>n.textContent==='Use this angle').listeners.click();
  assert.deepEqual(JSON.parse(t.f.run('JSON.stringify([studio.deskStart.title,studio.deskStart.point,studio.deskStart.audience])')),['Why long jobs stop','Most stops are timeouts.','Developers'],'the picked, edited angle is the brief');
  assert.match(t.nodes().find(n=>/\bdesk-angle\b/.test(n.className)&&descendants(n).some(d=>d.textContent==='Using this angle')).className,/desk-angle-picked/);
  t.type('desk-angle-1-point','Most stops are timeouts, and a retry keeps the work.');
  assert.equal(t.f.run('studio.deskStart.point'),'Most stops are timeouts, and a retry keeps the work.');
  await t.click('Suggest three more');
  assert.equal(t.requests.filter(r=>r.url==='/api/desk-angles').at(-1).data.replaces,asked.operation,'the earlier angles are let go');
  await t.tick();await descendants(t.nodes().filter(n=>/\bdesk-angle\b/.test(n.className))[1]).find(n=>n.textContent==='Use this angle').listeners.click();
  await t.submit();
  assert.ok(!t.requests.some(r=>r.url==='/api/source-keep'),'the server keeps a ticked file once the blog is made, not the page before');
  const made=t.requests.find(r=>r.url==='/api/desk-create').data;
  const latest=t.requests.filter(r=>r.url==='/api/desk-angles').at(-1).data.operation;
  assert.deepEqual({...made,operation:undefined},{operation:undefined,style:'how-to',tone:'Warm',sources:['s1'],library:[],keep:['s1'],title:'Why jobs stop',way:'topic',length:'deep',research_from:{sites:['https://docs.example.com'],web:true},angles:latest,point:'Most stops are timeouts.',audience:'Developers'});
  assert.equal(t.f.run('studio.screen'),'desk');
}
async function deskOutlineStarts(){
  const t=deskStartFixture((url)=>{if(url==='/api/desk-create')return {...startView(),first_pass_problem:null};if(url.startsWith('/api/desk?'))return startView();return null;});
  for(const [way,label] of [['outline','Write from my outline'],['shape','Shape an outline with me first']]){
    await t.f.run("sDeskBegin({have:'outline'})");
    await t.nodes().find(n=>n.className==='pick-card'&&n.textContent==='Something else').listeners.click();
    await t.submit();
    assert.ok(t.nodes().some(n=>n.textContent==='Write from my outline')&&t.nodes().some(n=>n.textContent==='Shape an outline with me first'),'both co-author choices');
    t.type('desk-outline','# A synthetic outline\n\n## One\n\nBrief one.\n\n## Two\n');
    await t.click(label);
    await t.submit();
    const made=t.requests.filter(r=>r.url==='/api/desk-create').at(-1).data;
    assert.equal(made.way,way);assert.equal(made.outline,'# A synthetic outline\n\n## One\n\nBrief one.\n\n## Two\n');assert.equal(made.style,'');assert.equal(made.research_from,undefined,'no research unless ticked');
  }
  // An outline with neither a title nor a # line is stopped on the page.
  await t.f.run("sDeskBegin({have:'outline'})");
  await t.nodes().find(n=>n.className==='pick-card'&&n.textContent==='Something else').listeners.click();
  await t.submit();
  t.type('desk-outline','Some notes.');await t.submit();
  assert.ok(t.nodes().some(n=>n.className==='problem'&&/# title line/.test(n.textContent)));
}
// The other ways in reach the desk start too: an interview's outline, and a saved blog's
// details when it has no step-by-step run.
async function deskOtherWaysIn(){
  const outline='# Synthetic interview\n\n## One\n\nBrief one.\n\n## Two\n';
  const t=deskStartFixture((url)=>{
    if(url.startsWith('/api/interview?'))return {id:'interviewed',title:'Synthetic interview',answers:[],notes:'',question:'Anything else?',expected:'i1',outline:true,outline_content:outline};
    if(url.startsWith('/api/run?'))return {__http:400,error:'This blog has no guided run. Choose Run this blog on the page.'};
    if(url==='/api/desk?id=desk-blog')return deskView();
    if(url.startsWith('/api/desk?'))return {__http:400,error:'This blog is not on the desk.'};
    if(url.startsWith('/api/article?')&&url.includes('id=saved'))return {title:'A saved blog',view:{preview:{kind:'draft',text:'Saved text.',truncated:false}}};
    if(url.startsWith('/api/article?'))return {title:'An empty blog',view:{preview:{kind:null,text:'',truncated:false}}};
    if(url==='/api/desk-create')return {...deskView({id:'saved'}),first_pass_problem:null};
    return null;
  });
  const throughKinds=async()=>{await t.nodes().find(n=>n.className==='pick-card'&&n.textContent==='Something else').listeners.click();await t.submit();};
  // An interview's outline: a desk start from the outline, with the interview's title.
  await t.f.run("sInterview('interviewed')");
  await t.click('Review outline and start a draft');
  assert.equal(t.f.run('studio.screen'),'desk-start');
  await throughKinds();
  assert.equal(t.byId('desk-outline').value,outline,'the interview outline is pasted for you');
  assert.equal(t.byId('desk-title').value,'Synthetic interview');
  await t.submit();
  let made=t.requests.filter(r=>r.url==='/api/desk-create').at(-1).data;
  assert.equal(made.way,'outline');assert.equal(made.outline,outline);assert.equal(made.title,'Synthetic interview');
  assert.equal(t.requests.some(r=>r.url==='/api/run-create'),false,'no step-by-step run is started');
  // Open writing run on a blog on the desk opens the desk.
  await t.f.run("openBlogRun('desk-blog')");
  assert.equal(t.f.run('studio.screen'),'desk');assert.equal(t.f.run('studio.id'),'desk-blog');
  // A saved draft comes to the desk start as the draft to bring, in the same blog.
  await t.f.run("openBlogRun('saved')");
  assert.equal(t.f.run('studio.screen'),'desk-start');
  await throughKinds();
  const saved=t.nodes().find(n=>n.textContent==='Your saved draft');
  assert.equal(saved.attributes['aria-pressed'],'true','the saved draft is chosen');
  assert.equal(t.byId('desk-manuscript'),undefined,'nothing to paste');
  await t.submit();
  made=t.requests.filter(r=>r.url==='/api/desk-create').at(-1).data;
  assert.equal(made.article,'saved');assert.equal(made.manuscript,undefined);assert.equal(made.title,'A saved blog');assert.equal(made.first_pass,'leave');
  // Paste text still works from there, and the saved draft is not offered on a fresh start.
  await t.f.run("sDeskBegin({have:'draft'})");await throughKinds();
  assert.equal(t.nodes().some(n=>n.textContent==='Your saved draft'),false);
  // A blog with no draft yet starts on the desk with its title.
  await t.f.run("openBlogRun('empty')");
  assert.equal(t.f.run('studio.screen'),'desk-start');assert.equal(t.f.run('studio.deskStart.title'),'An empty blog');assert.equal(t.f.run('studio.deskStart.have'),'topic');
}
async function deskProgress(){
  let view=startView();
  const t=deskStartFixture((url,data)=>{
    if(url.startsWith('/api/desk?'))return view;
    if(url==='/api/desk-stop'){view=startView({working:null,start:{...view.start,busy:false,status:'cancelled',problem:'Stopped. Choose Retry to start this step again.'}});return view;}
    if(url==='/api/desk-retry'){view=startView();return view;}
    return null;
  });
  await t.f.run("sRoute('desk','started')");
  const lede=t.nodes().find(n=>n.className==='lede');
  assert.equal(lede.textContent,'Nothing needed from you. The draft opens here when it is ready, in about 14 minutes.');
  assert.ok(t.nodes().some(n=>n.textContent==='Researching'));
  assert.ok(t.nodes().some(n=>n.textContent==='Under way'),'the current step in words');
  assert.equal(t.nodes().filter(n=>/desk-clock/.test(n.className)).length,1,'one clock for the whole start');
  assert.match(t.nodes().find(n=>/desk-clock/.test(n.className)).textContent,/so far, for the whole start/);
  assert.equal(t.f.get('above').textContent,'Writing on its own');
  // Stop, then Retry.
  await t.click('Stop');
  assert.deepEqual(t.requests.find(r=>r.url==='/api/desk-stop').data,{id:'started',job:'r1'});
  assert.ok(t.nodes().some(n=>n.textContent==='Stopped. Choose Retry to start this step again.'));
  await t.click('Retry');
  assert.deepEqual(t.requests.find(r=>r.url==='/api/desk-retry').data,{id:'started'});
  // A step past its usual time says so, with the time spent, never a frozen estimate.
  view=startView({start:{...view.start,over:true,minutes_left:1,started_at:new Date(Date.now()-9*60000).toISOString()}});await t.tick();
  assert.equal(t.nodes().find(n=>n.className==='lede').textContent,'Nothing needed from you. Taking longer than usual; still working, 9 minutes so far. The draft opens here when it is ready.');
  // A research phase in words, then the draft opens on its own.
  view=startView({start:{...view.start,phase:'Round 1 of 3, writing the report'}});await t.tick();
  assert.ok(t.nodes().some(n=>n.textContent==='Round 1 of 3, writing the report'));
  view=deskView({id:'started',start:{...view.start,step:null,ended_at:new Date().toISOString(),busy:false}});await t.tick();
  assert.equal(t.nodes().filter(n=>n.className.split(' ').includes('desk-part')).length,5,'the desk opened with its cards');
  assert.ok(descendants(t.f.get('toasts')).some(n=>n.textContent==='The draft is ready. Edit it here.'));
  // Shape ends on the Outline tab.
  view=deskView({id:'shaped',sections:[{id:'aaaaaaaa',heading:'One',brief:'Brief one.',text:''},{id:'bbbbbbbb',heading:'Two',brief:'',text:''}],opening:'',start:{...view.start,open:'outline',ended_at:new Date().toISOString()}});
  t.f.run('studio.desk=null');await t.f.run("sRoute('desk','shaped')");
  assert.equal(t.f.run('studio.desk.tab'),'outline');assert.ok(t.nodes().some(n=>n.textContent==='Write the draft'));
}
async function deskOutlineTab(){
  let view=deskView({sections:[{id:'aaaaaaaa',heading:'First part',brief:'Say what stops.',text:'First text here.'},{id:'bbbbbbbb',heading:'Second part',brief:'',text:''},{id:'cccccccc',heading:'Third part',brief:'',text:''}]});
  const t=deskStartFixture((url,data)=>{
    if(url.startsWith('/api/desk?'))return view;
    if(url==='/api/desk-outline-save'){const known=Object.fromEntries(view.sections.map(s=>[s.id,s]));view={...view,revision:view.revision+1,sections:data.sections.map((row,at)=>({text:'',...(known[row.id]||{}),id:row.id||'dddddddd',heading:row.heading,brief:row.brief}))};return view;}
    if(url==='/api/desk-note'){view={...view,working:{id:'j1',kind:'desk-section',status:'queued',busy:true,part:data.part,note:''}};return view;}
    if(url==='/api/desk-draft'){view={...view,working:{id:'j2',kind:'desk-draft',status:'queued',busy:true,part:'sections'}};return view;}
    if(url==='/api/desk-unremove'){view={...view,revision:view.revision+1,removed:[]};return view;}
    return null;
  });
  await t.f.run("sRoute('desk','desk-blog')");
  await t.click('Outline');
  assert.equal(t.byId('desk-outline-heading-0').value,'First part');assert.equal(t.byId('desk-outline-brief-0').value,'Say what stops.');
  await t.nodes().find(n=>n.attributes['aria-label']==='Move down · First part').listeners.click();
  const moved=t.requests.find(r=>r.url==='/api/desk-outline-save').data;
  assert.deepEqual(moved.sections.map(row=>row.id),['bbbbbbbb','aaaaaaaa','cccccccc'],'reordering keeps the ids');assert.equal(moved.seen,1);
  t.type('desk-outline-brief-0','Explain the retry.');assert.match(t.nodes().find(n=>/desk-save-state/.test(n.className)).textContent,/Saving/);
  await t.tick();
  const briefed=t.requests.filter(r=>r.url==='/api/desk-outline-save').at(-1).data;
  assert.equal(briefed.sections[0].brief,'Explain the retry.');assert.equal(briefed.seen,2);
  await t.click('Add a section');
  assert.deepEqual(t.requests.filter(r=>r.url==='/api/desk-outline-save').at(-1).data.sections.at(-1),{heading:'New section',brief:''});
  // Write this section, from its brief and the sections before it.
  await t.nodes().find(n=>n.textContent==='Write this section'&&n.listeners.click).listeners.click();
  assert.deepEqual(t.requests.find(r=>r.url==='/api/desk-note').data,{id:'desk-blog',seen:view.revision,part:'bbbbbbbb',note:''});
  view={...view,working:null};t.f.run('studio.desk.view.working=null');await t.f.run('sDeskRender(studio.desk)');
  // Write the draft, confirmed because a section already has text.
  await t.click('Write the draft');
  assert.ok(t.sheet().some(n=>n.textContent==='Write the whole draft?'));
  await t.sheet().find(n=>n.textContent==='Write the draft').listeners.click();
  assert.deepEqual(t.requests.find(r=>r.url==='/api/desk-draft').data,{id:'desk-blog',seen:view.revision});
  assert.equal(t.f.run('studio.desk.tab'),'draft','the draft tab shows the sections being written');
  assert.ok(t.nodes().filter(n=>/desk-working/.test(n.className)).length>=3);
  // Removing a written section asks first.
  view={...view,working:null};await t.f.run("studio.desk.view.working=null;studio.desk.tab='outline';sDeskRender(studio.desk)");
  const removing=t.nodes().find(n=>n.attributes['aria-label']==='Remove First part');await removing.listeners.click();
  assert.ok(t.sheet().some(n=>n.textContent==='Remove “First part”?'));
  // A removed section is listed under the outline and comes back with its text and History.
  t.f.run('sCloseSheet()');view={...view,removed:[{heading:'An old part',words:12,at:new Date().toISOString()}]};t.f.run('studio.desk.view.removed=[{heading:"An old part",words:12,at:new Date().toISOString()}]');await t.f.run('sDeskRender(studio.desk)');
  assert.ok(t.nodes().some(n=>n.textContent==='Removed sections'));
  await t.nodes().find(n=>n.attributes['aria-label']==='Bring back An old part').listeners.click();
  assert.deepEqual(t.requests.find(r=>r.url==='/api/desk-unremove').data,{id:'desk-blog',seen:view.revision-1,index:0});
}
function finishSet(kind,items,extra={}){return {job:kind+'job'.padEnd(28,'0'),kind:'finish-'+kind,blog:'desk-blog',made_at:'x',dropped:0,...extra,items:items.map((item,index)=>({id:'p'+(index+1),state:'open',present:true,flag:'',note:'',...item}))};}
async function deskFinishing(){
  let view=deskView({source_names:[]}),job=0;
  const t=deskStartFixture((url,data)=>{
    if(url.startsWith('/api/desk?'))return view;
    if(url==='/api/desk-finish'){view={...view,working:{id:'f'+(++job),kind:'finish-'+data.tool,status:'queued',busy:true,part:'finishing',action:data.tool}};return view;}
    if(url==='/api/desk-apply'){view={...view,revision:view.revision+1,finished:{applied:data.items.length,left:[]}};return view;}
    if(url==='/api/desk-skip'){const tool=Object.keys(view.finishing).find(key=>view.finishing[key].job===data.job);view={...view,finishing:{...view.finishing,[tool]:{...view.finishing[tool],items:view.finishing[tool].items.map(item=>data.items.includes(item.id)?{...item,state:'skipped'}:item)}},finished:{skipped:data.items.length}};return view;}
    if(url.startsWith('/api/desk-proofread?'))return {id:'desk-blog',revision:view.revision,more:0,limitations:'Mechanical matches only.',findings:[{part:'aaaaaaaa',rule:'banished:here',label:'“here” often reads as machine-written.',fix:'Say it without “here”, in plain words.',target:'here',sentence:'First text here.',start:0,at:11}]};
    if(url==='/api/desk-selection'){view={...view,working:{id:'s1',kind:'desk-selection',status:'queued',busy:true,part:data.part}};return view;}
    if(url.startsWith('/api/prepublish?'))return {findings:[{line:3,code:'unfinished-note',detail:'Resolve the unfinished editorial note or placeholder.'}],coverage:'Local checks only.'};
    if(url==='/api/tool-action')return {id:'r'.repeat(32),kind:'repurpose',status:'ready',metadata:{article:'desk-blog',format:'linkedin'},result:{content:'A short post.',notes:''}};
    if(url==='/api/desk-repurpose'){view={...view,made:{id:'copy-blog',title:data.title}};return view;}
    if(url==='/api/desk-google-plan')return {plan:'g'.repeat(32),mode:'auto',count:1,left:1,target:'https://docs.google.com/document/d/x/edit',proposals:[{id:'desk-1',kind:'edit',before:'slow',after:'late',reason:'Wording changed on the writing desk.'}]};
    if(url==='/api/desk-google-send')return {status:'verified-pending'};
    if(url==='/api/desk-stop'){view={...view,working:null};return view;}
    if(url==='/api/voice-guides')return {guides:[{id:'plain',name:'Plain',revision:1,status:'confirmed',says:'Plain words. Short sentences.'},{id:'old',name:'Old voice',revision:2,status:'retired',says:'Long.'}],making:[]};
    return null;
  });
  const {f,requests,nodes,tick,sheet}=t;
  const panel=()=>nodes().find(n=>/(^| )desk-finish( |$)/.test(n.className));
  const inPanel=label=>descendants(panel()).find(n=>n.textContent===label&&n.listeners.click);
  const item=id=>descendants(panel()).find(n=>n.dataset?.item===id);
  const inItem=(id,label)=>descendants(item(id)).find(n=>n.textContent===label&&n.listeners.click);
  const card=part=>nodes().find(n=>n.dataset?.part===part);
  const last=url=>requests.filter(r=>r.url===url).at(-1)?.data;
  await f.run("sRoute('desk','desk-blog')");
  // 1. Finishing opens beside the draft and lists every tool, Apply a voice among them.
  const opener=descendants(f.get('actions')).find(n=>n.textContent==='Finishing');
  assert.equal(opener.disabled,false);
  await opener.listeners.click();
  assert.ok(panel(),'the panel is open');
  assert.match(nodes().find(n=>/desk-layout/.test(n.className)).className,/desk-finishing/);
  assert.match(descendants(panel()).find(n=>/desk-finish-head/.test(n.className)).className,/\bglass\b/,'transient chrome uses the material');
  assert.deepEqual(descendants(panel()).filter(n=>n.className==='pick-card').map(n=>n.textContent),['Humanize','Apply a voice','Proofread','Check facts against sources','Headline and opening','Feedback without a rewrite','Before publishing']);
  assert.equal(descendants(panel()).find(n=>n.textContent==='Apply a voice').disabled,false);
  // 2. Humanize at medium: one job that writes no part, so every card stays editable.
  await inPanel('Humanize').listeners.click();
  await inPanel('Medium').listeners.click();
  await inPanel('Find sentences').listeners.click();
  assert.deepEqual(last('/api/desk-finish'),{id:'desk-blog',seen:1,tool:'humanize',level:'medium'});
  assert.equal(descendants(card('aaaaaaaa')).find(n=>n.tagName==='textarea').readOnly,false);
  assert.ok(descendants(panel()).some(n=>n.textContent==='Finding sentences that read as machine-written…'));
  // The suggestions land; the card being typed in is not redrawn.
  const typing=card('bbbbbbbb');
  view={...view,working:null,jobs:[{id:'f1',kind:'finish-humanize',status:'ready',applied:true,error:''}],finishing:{humanize:finishSet('humanize',[
    {part:'aaaaaaaa',before:'First text here.',after:'The first text here.',note:'Stock wording.'},
    {part:'bbbbbbbb',before:'Second text.',after:'The second text.'},
    {part:'cccccccc',before:'Third text.',after:'Third text, 3 times.',flag:'Check the facts: this changes a number.'},
  ],{level:'medium'})}};
  await tick();
  assert.equal(card('bbbbbbbb'),typing,'cards the suggestions did not change keep focus and caret');
  const first=item('p1');assert.ok(first,'each suggestion is shown');
  assert.deepEqual(descendants(first).filter(n=>n.tagName==='h4').map(n=>n.textContent),['Before','After']);
  assert.ok(descendants(first).some(n=>n.tagName==='del'&&n.textContent==='First'));
  assert.ok(descendants(first).some(n=>n.tagName==='ins'&&n.textContent==='The first'));
  assert.ok(descendants(item('p3')).some(n=>n.textContent==='Check the facts: this changes a number.'),'a changed fact is flagged');
  // Apply all applies every open, unflagged suggestion; the flagged one waits.
  assert.ok(inPanel('Apply all (2)'));
  // 3. Apply, Edit then Apply this, and Skip.
  await inItem('p1','Apply').listeners.click();
  assert.deepEqual(last('/api/desk-apply'),{id:'desk-blog',seen:1,job:view.finishing.humanize.job,items:[{id:'p1'}]});
  view={...view,finishing:{humanize:{...view.finishing.humanize,items:view.finishing.humanize.items.map(i=>i.id==='p1'?{...i,state:'applied'}:i)}}};
  f.set('next',view);await f.run('studio.desk.view=next;sDeskPanelShow(studio.desk)');
  assert.ok(descendants(item('p1')).some(n=>n.textContent==='Applied. The earlier text is in History.'));
  await inItem('p2','Edit').listeners.click();
  const box=descendants(item('p2')).find(n=>n.tagName==='textarea');assert.equal(box.value,'The second text.');
  box.value='My second text.';box.listeners.input();
  assert.ok(descendants(item('p2')).some(n=>n.tagName==='ins'&&/My/.test(n.textContent)),'the After side follows the edit');
  // A poll while the person types in the panel leaves it as it is.
  f.set('focused',box);f.run('document.activeElement=focused');const shownPanel=panel();
  f.set('next',{...view,revision:view.revision});await f.run('studio.desk.view={...next,jobs:[{id:"f9",kind:"finish-facts",status:"failed",error:"x"}]};sDeskPanelSync(studio.desk)');
  assert.equal(panel(),shownPanel,'typing in an edited suggestion keeps its caret');
  f.run('document.activeElement=null;studio.desk.view=next');
  await inItem('p2','Apply this').listeners.click();
  assert.deepEqual(last('/api/desk-apply').items,[{id:'p2',after:'My second text.'}]);
  await inItem('p3','Skip').listeners.click();
  assert.deepEqual(last('/api/desk-skip'),{id:'desk-blog',job:view.finishing.humanize.job,items:['p3']});
  // Apply all: a fresh set, one flagged.
  view={...view,finishing:{humanize:finishSet('humanize',[{part:'aaaaaaaa',before:'A.',after:'B.'},{part:'bbbbbbbb',before:'C.',after:'D.'},{part:'cccccccc',before:'E.',after:'F 2.',flag:'Check the facts: this changes a number.'}])}};
  f.set('next',view);await f.run('studio.desk.view=next;sDeskPanelShow(studio.desk)');
  await inPanel('Apply all (2)').listeners.click();
  assert.deepEqual(last('/api/desk-apply').items,[{id:'p1'},{id:'p2'}]);
  assert.ok(descendants(panel()).some(n=>n.textContent==='1 flagged suggestion is left for you to check one by one.'));
  // Apply a voice: a voice guide (retired ones left out), then each part before and after;
  // Apply all, some or none; a part where a fact changed waits to be checked.
  await inPanel('All tools').listeners.click();
  await inPanel('Apply a voice').listeners.click();await tick();
  const guide=descendants(panel()).find(n=>n.id==='desk-voice-guide');assert.ok(guide,'a voice guide to choose');
  assert.deepEqual(guide.children.map(o=>[o.value,o.textContent]),[['plain','Plain']],'retired guides are left out');
  assert.ok(descendants(panel()).some(n=>n.textContent==='Plain words. Short sentences.'),'the guide says how it sounds');
  await inPanel('Apply the voice').listeners.click();
  assert.deepEqual(last('/api/desk-finish'),{id:'desk-blog',seen:view.revision,tool:'voice',guide:'plain'});
  assert.ok(descendants(panel()).some(n=>n.textContent==='Rewriting the draft in the voice guide, section by section…'));
  view={...view,working:null,finishing:{...view.finishing,voice:finishSet('voice',[
    {part:'opening',before:'An opening.',after:'An opening, said plainly.',whole:true,note:'Plainer.'},
    {part:'aaaaaaaa',before:'First text here.',after:'First text, plainly.',whole:true},
    {part:'bbbbbbbb',before:'Second text, 2 times.',after:'Second text, 3 times.',whole:true,flag:'Check the facts: this changes a number.'},
  ],{guide_name:'Plain',kept:1})}};
  f.set('next',view);await f.run('studio.desk.view=next;sDeskPanelShow(studio.desk)');
  assert.ok(descendants(panel()).some(n=>n.textContent==='In the voice of Plain · 3 parts rewritten · 3 to review · 1 part already reads in this voice.'),descendants(panel()).map(n=>n.textContent).join('|'));
  assert.deepEqual(descendants(item('p2')).filter(n=>n.tagName==='h4').map(n=>n.textContent),['Before','After'],'each section before and after');
  assert.ok(descendants(item('p3')).some(n=>n.textContent==='Check the facts: this changes a number.'),'a section where a fact changed is flagged');
  const seenVoice=view.revision;await inPanel('Apply all (2)').listeners.click();
  assert.deepEqual(last('/api/desk-apply'),{id:'desk-blog',seen:seenVoice,job:view.finishing.voice.job,items:[{id:'p1'},{id:'p2'}]});
  assert.ok(descendants(panel()).some(n=>n.textContent==='1 part that changes a fact, code or the part’s shape is left for you to check one by one.'));
  await inItem('p3','Skip').listeners.click();
  assert.deepEqual(last('/api/desk-skip'),{id:'desk-blog',job:view.finishing.voice.job,items:['p3']});
  // 4. Proofread: at once, no job; Fix rewrites only the sentence.
  await inPanel('All tools').listeners.click();
  await inPanel('Proofread').listeners.click();
  assert.ok(requests.some(r=>r.url==='/api/desk-proofread?id=desk-blog'));
assert.ok(descendants(panel()).some(n=>n.tagName==='mark'&&n.textContent==='here'),'the finding is marked in its sentence');
  await inPanel('Fix').listeners.click();
  assert.deepEqual(last('/api/desk-selection'),{id:'desk-blog',seen:view.revision,part:'aaaaaaaa',text:'First text here.',start:0,action:'fix',instruction:'Say it without “here”, in plain words.'});
  view={...view,working:null};f.set('next',view);await f.run('studio.desk.view=next;sDeskRender(studio.desk)');
  // 5. Facts: with no sources the panel offers Add a source; each claim keeps its passage.
  await inPanel('All tools').listeners.click();
  await inPanel('Check facts against sources').listeners.click();
  assert.ok(descendants(panel()).some(n=>n.textContent==='Facts are checked against your sources, and this draft has none yet.'));
  view={...view,source_names:[{id:'s1',name:'Notes',purposes:['reference']}],finishing:{...view.finishing,facts:finishSet('facts',[
    {part:'aaaaaaaa',before:'First text here.',verdict:'contradicted',passage:'The text is elsewhere.',source:'Notes'},
    {part:'bbbbbbbb',before:'Second text.',verdict:'not-in-sources',passage:'',after:'A second text.'},
    {part:'cccccccc',before:'Third text.',verdict:'supported',passage:'Third text.',source:'Notes'},
    {part:'cccccccc',before:'Third',verdict:'not-in-sources',passage:'',after:'A third'},
  ])}};
  f.set('next',view);await f.run('studio.desk.view=next;sDeskPanelShow(studio.desk)');
  assert.ok(descendants(item('p1')).some(n=>n.textContent==='Contradicted'));
  assert.ok(descendants(item('p1')).some(n=>n.textContent==='From Notes: “The text is elsewhere.”'));
  assert.ok(descendants(panel()).some(n=>n.tagName==='summary'&&n.textContent==='Supported (1)'));
  assert.ok(!descendants(panel()).some(n=>/^Apply all/.test(n.textContent)),'each claim is checked on its own, never applied all at once');
  await inItem('p1','Add a source').listeners.click();
  assert.equal(f.get('sheet').children[0].children[0].textContent,'Add a source','Add a source opens the sources sheet');
  f.run('sCloseSheet()');
  await inItem('p1','Fix the wording').listeners.click();
  const wording=descendants(item('p1')).find(n=>n.tagName==='textarea');wording.value='First text, as Notes says.';wording.listeners.input();
  await inItem('p1','Apply this').listeners.click();
  assert.deepEqual(last('/api/desk-apply').items,[{id:'p1',after:'First text, as Notes says.'}]);
  await inItem('p2','Keep it').listeners.click();
  assert.deepEqual(last('/api/desk-skip').items,['p2']);
  // 6. Headline and opening: alternatives to use.
  await inPanel('All tools').listeners.click();await inPanel('Headline and opening').listeners.click();
  view={...view,finishing:{...view.finishing,headline:finishSet('headline',[{part:'title',before:'A synthetic title',after:'A sharper title',whole:true,group:'title'},{part:'opening',before:'An opening paragraph.',after:'A new opening.',whole:true,group:'opening'}])}};
  f.set('next',view);await f.run('studio.desk.view=next;sDeskPanelShow(studio.desk)');
  assert.ok(descendants(panel()).some(n=>n.textContent==='Title alternatives'));
  assert.ok(!inPanel('Apply all (2)'),'alternatives are chosen one at a time');
  await inItem('p1','Use this').listeners.click();
  assert.deepEqual(last('/api/desk-apply').items,[{id:'p1'}]);
  // 7. Feedback: comments in place, each a section note in one click; nothing applied.
  await inPanel('All tools').listeners.click();await inPanel('Feedback without a rewrite').listeners.click();
  view={...view,finishing:{...view.finishing,feedback:finishSet('feedback',[{part:'bbbbbbbb',quote:'Second text.',aspect:'argument',comment:'Say why this matters.'},{part:'whole',quote:'',aspect:'shape',comment:'The ending trails off.'}],{summary:'A clear start.'})}};
  f.set('next',view);await f.run('studio.desk.view=next;sDeskRender(studio.desk)');
  assert.ok(descendants(panel()).some(n=>n.textContent==='A clear start.'));
  const inCard=descendants(card('bbbbbbbb')).find(n=>n.textContent==='Make it a note'&&n.listeners.click);
  assert.ok(inCard,'the comment is shown in its section card');
  // A note the person typed is kept: the comment is added after it.
  const typed=descendants(card('bbbbbbbb')).find(n=>/desk-note-text/.test(n.className));typed.value='My own note.';typed.listeners.input();
  const posts=requests.length;await inCard.listeners.click();
  assert.equal(descendants(card('bbbbbbbb')).find(n=>/desk-note-text/.test(n.className)).value,'My own note.\n\nSay why this matters. (About: “Second text.”)');
  const whole=nodes().find(n=>n.id==='desk-whole-note');whole.value='Keep it short.';whole.listeners.input();
  assert.equal(requests.length,posts,'a note is not sent until Rewrite');
  await inItem('p2','Make it the whole-draft note').listeners.click();
  assert.equal(nodes().find(n=>n.id==='desk-whole-note').value,'Keep it short.\n\nThe ending trails off.');
  // 8. Before publishing: the check, a repurposed copy as a new blog, and the Google send.
  view={...view,google_suggestions:true,google:{url:'https://docs.google.com/document/d/x/edit'}};f.set('next',view);await f.run('studio.desk.view=next');
  await inPanel('All tools').listeners.click();await inPanel('Before publishing').listeners.click();
  await inPanel('Run the check').listeners.click();
  assert.ok(requests.some(r=>r.url==='/api/prepublish?id=desk-blog'));
  assert.ok(descendants(panel()).some(n=>n.textContent==='Line 3: Resolve the unfinished editorial note or placeholder.'));
  await inPanel('Prepare copy').listeners.click();
  const made=last('/api/tool-action');assert.equal(made.action,'job-create');assert.equal(made.kind,'repurpose');assert.equal(made.id,'desk-blog');assert.equal(made.format,'linkedin');
  assert.equal(descendants(panel()).find(n=>n.id==='desk-copy').value,'A short post.');
  await inPanel('Make it a new blog').listeners.click();
  assert.deepEqual(last('/api/desk-repurpose'),{id:'desk-blog',job:'r'.repeat(32),title:'A synthetic title (LinkedIn feed copy)',content:'A short post.'});
  assert.ok(descendants(panel()).some(n=>n.textContent==='Made “A synthetic title (LinkedIn feed copy)” as a new blog on the desk.'));
  await inPanel('Check what would be sent').listeners.click();
  assert.deepEqual(last('/api/desk-google-plan'),{id:'desk-blog',mode:'auto'});
  assert.ok(descendants(panel()).some(n=>n.textContent==='“slow” → “late”'));
  await inPanel('Send to Google Doc').listeners.click();
  assert.deepEqual(last('/api/desk-google-send'),{id:'desk-blog',plan:'g'.repeat(32),confirmed:true});
  assert.ok(descendants(panel()).some(n=>n.textContent==='Suggestions are ready for the Doc’s owner to accept or reject.'));
  // 9. On a phone the panel is a full-screen sheet over the desk.
  f.run("window.matchMedia=()=>({matches:true})");
  await inPanel('Close').listeners.click();assert.ok(!panel());
  const folded=descendants(f.get('actions')).find(n=>n.textContent==='Finishing');assert.ok(folded,'Finishing is in the phone toolbar menu');
  await folded.listeners.click();
  assert.match(panel().className,/desk-finish-sheet/);
  assert.equal(panel().parent,f.get('studio-page'),'the sheet sits over the page, not in the layout');
  // A sheet opened from the panel is the one on top: the panel steps aside while it is open,
  // and comes back when it closes. On a tablet the drawer does the same.
  for(const [size,media] of [['phone',()=>({matches:true})],['tablet',query=>({matches:/1099/.test(query)})]]){
    f.set('media',media);f.run('window.matchMedia=media');await f.run('sDeskFinishOpen(studio.desk,"facts")');
    f.set('next',{...view,source_names:[]});await f.run('studio.desk.view=next;sDeskPanelShow(studio.desk)');
    assert.equal(panel().className.includes('desk-finish-sheet'),size==='phone');
    await descendants(panel()).find(n=>n.textContent==='Add a source'&&n.listeners.click).listeners.click();
    assert.equal(f.get('sheet').hidden,false,size+': the sheet is open');
    assert.equal(f.get('main').inert,true,size+': the page behind the sheet waits');
    assert.equal(panel().hidden,true,size+': the panel is not over the sheet');
    f.run('sDeskPanelShow(studio.desk)');assert.equal(panel().hidden,true,size+': a redraw keeps it aside');
    f.run('sCloseSheet()');
    assert.equal(panel().hidden,false,size+': the panel is back when the sheet closes');
    assert.equal(f.get('main').inert,false);
  }
  // Narrowing the window while a sheet is open keeps the sheet on top at once.
  f.run("window.matchMedia=()=>({matches:false})");f.run('sDeskResized()');
  await descendants(panel()).find(n=>n.textContent==='Add a source'&&n.listeners.click).listeners.click();
  assert.equal(panel().hidden,false,'beside the draft, the panel is not in the way');
  f.run("window.matchMedia=()=>({matches:true})");f.run('sDeskResized()');
  assert.equal(panel().hidden,true,'narrowed under an open sheet, the panel steps aside');
  f.run('sCloseSheet()');assert.equal(panel().hidden,false);
  // Turning the screen redraws the desk in its new layout.
  f.run("window.matchMedia=()=>({matches:false})");f.run('sDeskResized()');
  assert.doesNotMatch(panel().className,/desk-finish-sheet/);assert.match(nodes().find(n=>/desk-layout/.test(n.className)).className,/desk-finishing/);
  f.run("window.matchMedia=()=>({matches:true})");f.run('sDeskResized()');assert.match(panel().className,/desk-finish-sheet/);
  // A redraw the person did not ask for waits while a control in the panel has focus.
  const select=descendants(panel()).find(n=>n.tagName==='button');f.set('focused',select);f.run('document.activeElement=focused');
  const kept=panel();f.set('next',{...view,revision:view.revision+5});await f.run('studio.desk.view=next;sDeskPanelSync(studio.desk)');
  assert.equal(panel(),kept,'a focused control keeps its place');assert.equal(f.run('studio.desk.panelStale'),true);
  f.run('document.activeElement=null');await kept.listeners.focusout();for(const fn of t.timers.splice(0))await fn();
  assert.notEqual(panel(),kept,'it redraws once focus leaves the panel');
  f.run("window.matchMedia=undefined");
}
async function deskAddSource(){
  let view=deskView();
  const t=deskStartFixture((url,data)=>{
    if(url.startsWith('/api/desk?'))return view;
    if(url==='/api/upload')return {files:[{filename:'A synthetic page',source:{id:'link1'},state:'ready',chars:900,note:'',link:data.files[0].link}]};
    if(url==='/api/source-keep')return {id:data.id,kept:data.keep};
    if(url==='/api/desk-sources'){view={...view,revision:2,source_names:[{id:'s1',name:'Notes',purposes:['reference']}]};return view;}
    return null;
  });
  await t.f.run("sRoute('desk','desk-blog')");
  await t.click('Add a source');
  assert.equal(t.f.get('sheet').children[0].children[0].textContent,'Add a source');
  assert.ok(t.sheet().some(n=>n.id==='files-input'),'files, Google Docs, links and the library, as the start takes them');
  assert.equal(t.sheet().find(n=>n.id==='files-keep').checked,false);
  t.f.run("studio.desk.adding.files.push({id:'s1',filename:'notes.md',state:'ready',role:'material',chars:12,note:'',link:'',kept:true},{id:'lib1',filename:'A post',state:'ready',role:'messaging',library:true,location:'hub',kept:true})");
  t.sheet().find(n=>n.id==='files-link').value='https://docs.example.com/guide';
  await t.click('Add the link');
  const asked=t.requests.find(r=>r.url==='/api/upload').data;
  assert.deepEqual(asked.files,[{link:'https://docs.example.com/guide',purpose:'material'}]);assert.equal(asked.keep,false);assert.equal(asked.purpose,'material');
  assert.ok(t.sheet().some(n=>/^Link · /.test(n.textContent)),'the row says it is a link');
  await t.click('Add to this draft');
  assert.ok(!t.requests.some(r=>r.url==='/api/source-keep'));
  assert.deepEqual(t.requests.find(r=>r.url==='/api/desk-sources').data,{id:'desk-blog',sources:['s1','link1'],library:[{id:'lib1',role:'messaging',location:'hub'}],keep:['s1']},'only the ticked file is kept, by the server, on Add');
  assert.equal(t.f.get('sheet').hidden,true);
  assert.ok(t.nodes().some(n=>n.textContent==='Notes'),'the sources panel names the new source');
  // On a phone the start still runs in its three steps.
  t.f.run("window.matchMedia=()=>({matches:true})");await t.f.run("sDeskBegin()");
  assert.ok(t.nodes().some(n=>n.className==='pick-card'&&n.textContent==='Something else'));
}
