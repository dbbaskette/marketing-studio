// Exercise the actual desk functions with a disposable DOM and controlled API responses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.attributes={};this.listeners={};this.hidden=false;this.disabled=false;this.value='';this.textContent='';this.className='';}
  append(...children){this.children.push(...children);for(const child of children)child.parent=this;}
  replaceChildren(...children){this.children=[];this.append(...children);}
  setAttribute(key,value){this.attributes[key]=value;}
  removeAttribute(key){delete this.attributes[key];}
  addEventListener(key,fn){this.listeners[key]=fn;}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  querySelectorAll(selector){return this.children.flatMap(c=>[...(selector==='.dialog-notice'&&c.className.includes('dialog-notice')?[c]:selector==='[type=submit]'&&c.type==='submit'?[c]:[]),...c.querySelectorAll(selector)]);}
  showModal(){this.open=true;}
  close(){this.open=false;}
  focus(){this.focused=true;}
  select(){this.selected=true;}
}
function descendants(node){return node.children.flatMap(c=>[c,...descendants(c)]);}
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}
function fixture(responder=()=>({items:[],total:0})){
  const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
  const document={getElementById:get,createElement:t=>new Element(t),querySelector:s=>s==='dialog[open]'?[...nodes.values()].find(n=>n.open):null,querySelectorAll:s=>[...nodes.values()].flatMap(n=>n.querySelectorAll(s))};
  const context=vm.createContext({document,location:{hash:'#fixture',pathname:'/'},sessionStorage:{getItem:()=>'',setItem:()=>{},removeItem:()=>{}},history:{replaceState:()=>{}},URLSearchParams,AbortController,Uint8Array,btoa,FormData:class{constructor(form){this.values=descendants(form).filter(e=>e.name).map(e=>[e.name,e.value]);}[Symbol.iterator](){return this.values[Symbol.iterator]();}},confirm:()=>true,crypto:{randomUUID:()=> 'a'.repeat(32)},fetch:async(url,options)=>{const result=await responder(url,options);return result&&result.__http?{ok:false,status:result.__http,json:async()=>result}:{ok:true,status:200,json:async()=>result};},console});
  const source=fs.readFileSync('skills/blog-studio/assets/management/app.js','utf8').split("for(const b of document.querySelectorAll('[data-view]'))")[0];
  vm.runInContext(source,context);
  vm.runInContext("access={status:'local-only',message:'Local only',actions:{edit:true,memory:false,refresh:false}}",context);
  return {get,nodes,run:code=>vm.runInContext(code,context),set:(name,value)=>{context[name]=value;}};
}
async function check(){
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
  pageDefinesEveryElement();
  const checks=['feedback','access and memory kinds','request ownership','curation conflicts','article/finding disclosures',
    'historical import preview/batching and source controls','diff-only saves and explicit ready/published confirmation',
    'analysis disclosure and per-operation choice','unreadable-blog notes','badge class whitelist','busy state',
    'refresh with a new selection','element ids'];
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

function pageDefinesEveryElement(){
  // The fixture creates any element on demand, so check the real page defines every id the script asks for.
  const base='skills/blog-studio/assets/management/';
  const script=fs.readFileSync(base+'app.js','utf8'),page=fs.readFileSync(base+'index.html','utf8');
  const defined=new Set([...page.matchAll(/id="([^"]+)"/g)].map(m=>m[1]));
  const wanted=new Set([...script.matchAll(/\$\('([a-z0-9-]+)'\)/g)].map(m=>m[1]));
  for(const prefix of ['upload','import'])for(const m of script.matchAll(/\$\(prefix\+'(-[a-z-]+)'\)/g))wanted.add(prefix+m[1]);
  for(const name of ['folder','export','url','links','scope','collection','name'])wanted.add('import-'+name+'-field');
  const created=new Set([...script.matchAll(/\.id='([a-z0-9-]+)'/g)].map(m=>m[1]));
  const missing=[...wanted].filter(id=>!defined.has(id)&&!created.has(id));
  assert.deepEqual(missing,[],'app.js uses ids that index.html does not define');
}
