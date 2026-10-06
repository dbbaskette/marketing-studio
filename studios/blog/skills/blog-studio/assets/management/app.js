'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('blog-studio-session') || '';
if(token)sessionStorage.setItem('blog-studio-session',token);
history.replaceState(null, '', location.pathname);
let view = 'board', offset = 0, total = 0, memoryEdit = null;
const limit = 20;
let loadGeneration = 0, loadController = null, renderedState = null;
let access = {status:'checking',message:'Checking Hub access…',actions:{edit:false,memory:false,refresh:false}};
let accessGeneration = 0;
const operationCache = new Map();
function operationFor(kind,data){const key=kind+JSON.stringify(data);if(!operationCache.has(key))operationCache.set(key,crypto.randomUUID().replaceAll('-',''));return operationCache.get(key);}
const views = {board:['Blogs in progress','Plan the next handoff. Open a Doc. Keep writing.','Writing pipeline'],inbox:['Needs attention','Find waiting decisions, review findings and stale companions.','Review inbox'],library:['Reference library','Find earlier work and curate the material your team uses.','Sources and historical posts'],memory:['Team memory','Keep useful knowledge and writing guidance easy to find.','Shared notes, context and rules']};
function element(tag, text, cls) {const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function notice(message, error=false) {
  const dialog=document.querySelector('dialog[open]');
  let target=$('notice');
  if(dialog){target=dialog.querySelector('.dialog-notice');if(!target){target=element('p',undefined,'dialog-notice');target.setAttribute('role','alert');dialog.append(target);}}
  target.textContent=message;target.className=error?'dialog-notice error':'dialog-notice';target.hidden=false;
}
function savedNotice(result) {notice((result.receipts||[]).map(r=>r.label+': '+r.message).join(' ')||result.next_step||'Saved.');}
function applyCapabilities() {
  $('access-status').textContent=access.message;
  $('upload-open').disabled=!access.actions.edit;
  $('import-open').disabled=!access.actions.edit;
  $('memory-open').disabled=!access.actions.memory;
  $('refresh-hub').disabled=!access.actions.refresh;
}
async function loadCapabilities() {
  const generation=++accessGeneration;
  try {
    const result=await api('capabilities');
    if(generation!==accessGeneration)return;
    access=result;
  } catch(error) {
    if(generation!==accessGeneration)return;
    access={status:'unavailable',message:'Access could not be checked. Reopen the current desk link or check access again. Saved results remain available.',actions:{edit:false,memory:false,refresh:false}};
  }
  applyCapabilities();
}
function continuation(command, label='Continue in chat') {
  const box=element('section',undefined,'continuation');
  box.append(element('h3',label),element('p','Copy this request into your Codex or Claude Code chat.'));
  const field=element('textarea');field.value=command;field.readOnly=true;field.rows=3;
  field.setAttribute('aria-label','Article or memory continuation request');
  const copy=button('Copy request',async()=>{
    try {await navigator.clipboard.writeText(command);notice('Request copied. Paste it into your writing chat.');}
    catch(error){field.focus();field.select();notice('Select and copy the request, then paste it into your writing chat.');}
  },'primary');
  box.append(field,copy);return box;
}
function readOnlyMemory(result, explanation) {
  $('detail-title').textContent=result.record.title;$('detail-content').replaceChildren();
  $('detail-content').append(element('p',result.record.kind+' · '+result.record.scope.level),element('p',explanation,'context-note'),element('pre',result.body,'source-excerpt'),continuation(result.continuation));
  $('detail-dialog').showModal();
}

async function loadReceipts(signal, current=()=>true) {
  const result=await api('receipts',undefined,signal);if(!current())return;const pending=result.items.filter(r=>!['shared','synchronized','local-only'].includes(r.sharing));
  $('sync-status').replaceChildren();$('sync-status').hidden=!pending.length;
  for(const receipt of pending){const row=element('div');row.append(element('p',receipt.label+': '+receipt.message));if(receipt.retry&&access.actions.edit)row.append(button('Retry sync',async()=>{const saved=await api('retry-sync',{id:receipt.id});savedNotice(saved);await loadReceipts();}));$('sync-status').append(row);}
}

async function api(route, data, signal) {if(data)document.querySelectorAll('.dialog-notice').forEach(e=>e.hidden=true);const response=await fetch('/api/'+route,{method:data?'POST':'GET',headers:{'X-Blog-Studio-Token':token,...(data?{'Content-Type':'application/json'}:{})},body:data?JSON.stringify(data):undefined,signal});const result=await response.json();if(!response.ok){const error=new Error(result.error||'The operation could not be completed.');error.status=response.status;error.code=result.code;throw error;}return result;}
function link(url, text) {if(!/^https:\/\//.test(url||''))return element('span',text);const a=element('a',text);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}
function badge(value) {const labels={'not-run':'Not run','not-checked-live':'Not checked live','local-saved-not-shared':'Saved locally','pending-review':'Awaiting review','queued-unavailable':'Waiting to sync','needs-local-check':'Needs local check'};return element('span',labels[value]||value,'badge '+value);}
function button(text, action, cls='secondary') {const b=element('button',text,cls);b.type='button';b.addEventListener('click',()=>Promise.resolve(action()).catch(e=>notice(e.message,true)));return b;}
function textCell(row, text) {const cell=element('td',text??'—');cell.setAttribute('role','cell');row.append(cell);return cell;}
function sameView(left, right) {
  return left && right && ['view','query','stage'].every(key=>left[key]===right[key]);
}
function loading(state, pending) {
  $('results').setAttribute('aria-busy',String(pending));
  $('loading').hidden=!pending;
  $('loading').textContent=pending?'Loading '+views[state.view][0].toLowerCase()+'…':'';
  $('previous').disabled=pending || !sameView(renderedState,state) || renderedState.offset===0;
  $('next').disabled=pending || !sameView(renderedState,state) || renderedState.offset+limit>=total;
}
async function load() {
  const state=Object.freeze({view,offset,query:$('query').value,stage:view==='board'?$('stage').value:''});
  const generation=++loadGeneration;
  if(loadController)loadController.abort();
  const controller=new AbortController();loadController=controller;
  const current=()=>generation===loadGeneration;
  loading(state,true);
  loadReceipts(controller.signal,current).catch(error=>{if(current()&&error.name!=='AbortError')notice(error.message,true);});
  const args=new URLSearchParams({limit:String(limit),offset:String(state.offset),query:state.query});
  if(state.stage)args.set('stage',state.stage);
  try {
    const result=await api(state.view+'?'+args,undefined,controller.signal);
    if(!current())return;
    render(state,result);total=result.total;renderedState=state;
  } catch(error) {
    if(!current()||error.name==='AbortError')return;
    if(sameView(renderedState,state))offset=renderedState.offset;
    throw error;
  } finally {
    if(current())loading(state,false);
  }
}
function render(state, result) {
  const {view,offset}=state, total=result.total;
  $('heading').textContent=views[view][0];$('subtitle').textContent=views[view][1];$('section-title').textContent=views[view][2];$('count').textContent=total+' '+(total===1?'item':'items');
  $('import-open').hidden=view!=='library';$('stage-filter').hidden=view!=='board';$('memory-open').hidden=view!=='memory';$('previous').disabled=offset===0;$('next').disabled=offset+limit>=total;$('page-label').textContent=total?`${offset+1}–${Math.min(offset+limit,total)} of ${total}`:'No items yet';
  $('query').placeholder={board:'Blog title, author, owner…',inbox:'Blog, finding, status…',library:'Title, author, topic…',memory:'Title, kind, scope…'}[view];
  $('observation').textContent=result.observation||result.google_observation||'Saved content only. Historical product claims need current verification.';
  $('results').replaceChildren();
  if(!result.items.length){const box=element('div',undefined,'empty');box.append(element('h3',{board:'Your next blog starts here',inbox:'Nothing in this saved inbox',library:'Build your reference shelf',memory:'Give your team useful context'}[view]),element('p',{board:'Upload a draft, start a blog in chat, or join your team’s Hub to find shared work.',inbox:'Run a review in chat to collect findings. Google review status is not checked live here.',library:'Choose “Import old blogs” to add a folder, website, feed or export, or upload a single reference.',memory:'Join a Team Hub, then save a note, context, or writing rule.'}[view]));$('results').append(box);return;}
  const table=element('table'),head=element('tr');table.setAttribute('role','table');head.setAttribute('role','row');table.className='view-'+view;const headings={board:['Blog / author','Stage','Owner / due','Working copy'],inbox:['Blog','Finding','Status','Next action'],library:['Reference / author','Status','Collection / date','Actions'],memory:['Memory','Kind','Applies to','Actions']}[view];headings.forEach(h=>{const th=element('th',h);th.setAttribute('scope','col');head.append(th);});const thead=element('thead');thead.append(head);table.append(thead);const body=element('tbody');
  for(const item of result.items){const row=element('tr');row.setAttribute('role','row');
    if(view==='board'){const cell=textCell(row,'');cell.append(button(item.title,()=>showBlog(item),'title-button'),element('p',item.author));const stage=textCell(row,'');stage.append(badge(item.stage));if(item.conflict||item.shared_newer)stage.append(element('p',item.conflict?'Competing revisions':'New shared revision'));const owner=textCell(row,item.owner);if(item.due)owner.append(element('p',(item.overdue?'Overdue · ':'Due · ')+item.due,item.overdue?'overdue':''));const doc=textCell(row,'');doc.append(item.google?link(item.google.url,'Open Google Doc ↗'):element('span',item.location==='hub'?'Saved in Team Hub':'Local writing'));if(item.google)doc.append(element('p','Saved link; refresh Google in chat'));}
    if(view==='inbox'){const blog=textCell(row,'');blog.append(button(item.title,()=>showBlog({...item,location:item.location||'local'}),'title-button'));const finding=textCell(row,'');finding.append(button(item.kind,()=>showFinding(item),'title-button'));if(item.finding)finding.append(element('p',item.finding.message||item.finding.detail||item.finding.original||'Inspect this saved finding in chat.'));const status=textCell(row,'');status.append(badge(item.status));const action=textCell(row,'');action.append(button('Inspect finding',()=>showFinding(item)),element('p',item.action));}
    if(view==='library'){const cell=textCell(row,item.title);cell.append(element('p',item.author||'Author unknown'));if(item.library.canonical_url)cell.append(link(item.library.canonical_url,'Original post ↗'));const status=textCell(row,'');status.append(badge(item.library.curation||item.status));textCell(row,(item.collection_names||item.library.collections||[]).join(', ')+' '+(item.library.published||'Date unknown'));const action=textCell(row,'');action.append(button(access.actions.edit?'Curate':'Read reference',()=>curate(item)));if(item.historical)action.append(element('p','Historical reference'));}
    if(view==='memory'){const cell=textCell(row,'');cell.append(button(item.title,()=>editMemory(item),'title-button'));if(item.conflict)cell.append(element('p','Competing revisions'));if(item.lesson_status)cell.append(element('p','Candidate lesson · '+item.lesson_status));textCell(row,item.kind);textCell(row,item.scope.level+(item.scope.key?' · '+item.scope.key:''));textCell(row,item.lesson?'Review / promote in chat':item.focused_workflow?'Manage in chat':item.kind==='decision'||item.conflict||!access.actions.memory?'Read details':'Open to read or edit');}
    Array.from(row.children).forEach((cell,index)=>cell.setAttribute('data-label',headings[index]));
    body.append(row);
  }table.append(body);const wrap=element('div',undefined,'table-wrap');wrap.append(table);$('results').append(wrap);
}
function disclosure(label, ...content) {
  const box=element('details'),summary=element('summary',label);box.append(summary,...content);return box;
}
function editorialForm(item, result) {
  const data=result.record.editorial||{},form=element('form');
  for(const [key,label]of [['owner','Owner'],['due','Due date'],['publication_url','Publication URL']]) {
    const field=element('label',label),input=element('input');input.name=key;input.value=data[key]||'';
    input.type=key==='due'?'date':'text';input.maxLength=key==='publication_url'?2000:200;field.append(input);form.append(field);
  }
  const field=element('label','Editorial stage'),select=element('select');select.name='stage';
  for(const stage of ['idea','draft','review','ready','published']) {
    const option=element('option',stage);option.value=stage;option.selected=stage===(data.stage||result.view.stage);select.append(option);
  }
  field.append(select);form.append(field);
  const actions=element('div',undefined,'form-actions'),save=element('button','Save editorial decision','primary');save.type='submit';actions.append(save);form.append(actions);
  form.addEventListener('submit',async event=>{
    event.preventDefault();save.disabled=true;
    try {const values=Object.fromEntries(new FormData(form));const saved=await api('schedule',{id:item.id,expected:result.expected,...values});$('detail-dialog').close();await load();savedNotice(saved);}
    catch(error){notice(error.message,true);}
    finally{save.disabled=false;}
  });
  return form;
}
function articleContent(item, result, selectedFinding) {
  const content=$('detail-content'),state=result.view;content.replaceChildren();
  const status=element('section',undefined,'article-summary');
  status.append(badge(state.stage),element('p','Requested stop: '+state.stop_point));
  if(state.blocker)status.append(element('p',state.blocker,'context-note'));
  if(state.stop_reached)status.append(element('p','Your requested '+state.stop_point+' is saved. Continue only when you choose the next step.'));
  const counts={};for(const review of state.reviews)counts[review.status]=(counts[review.status]||0)+1;
  status.append(element('p','Reviews: '+(Object.entries(counts).map(([name,count])=>count+' '+name).join(', ')||'none saved')+'.'));
  content.append(status);
  if(selectedFinding) {
    const finding=selectedFinding.finding,section=element('section',undefined,'selected-finding');
    section.append(element('h3',finding.kind+' · '+finding.status));
    for(const [key,value]of Object.entries(finding.finding||{})){section.append(element('h4',key),element('p',value));}
    section.append(element('p',finding.action));content.append(section,continuation(selectedFinding.command,'Inspect this finding in chat'));
    if(selectedFinding.evidence.length){const evidence=element('div');for(const citation of selectedFinding.evidence)evidence.append(element('h4',citation.name||'Pinned passage'),element('blockquote',citation.quote));content.append(disclosure('Cited passages',evidence));}
  } else content.append(continuation(state.next_action.command,state.next_action.label));
  if(state.google)content.append(link(state.google.url,'Open Google Doc'));
  content.append(element('p',state.google_observation,'help'));
  const preview=state.preview;
  if(preview.text){content.append(element('h3','Saved '+preview.kind+' preview'),element('pre',preview.text,'manuscript-preview'));if(preview.truncated)content.append(element('p','Preview only. Continue in chat for the full manuscript.','help'));}
  else content.append(element('p','No manuscript is saved yet. Continue in chat to plan the requested writing step.'));
  const reviews=element('ul',undefined,'detail-list');
  for(const review of state.reviews){const row=element('li',review.check+' · '+review.status);if(review.detail)row.append(element('p',review.detail));if(review.checked_at)row.append(element('p','Last check: '+review.checked_at));reviews.append(row);}
  if(!state.reviews.length)reviews.append(element('li','No saved reviews. This is not a review verdict.'));
  content.append(disclosure('Reviews and freshness',reviews));
  if(result.location==='local'&&access.actions.edit&&!state.conflict&&!state.shared_newer)content.append(disclosure('Editorial details',editorialForm(item,result),element('p','Ready and published are explicit decisions. This desk does not publish your blog.','help')));
  else {
    const metadata=result.record.editorial||{};
    content.append(disclosure('Editorial details',element('p','Owner: '+(metadata.owner||'Unassigned')),element('p','Due: '+(metadata.due||'Not set')),element('p','Recorded stage: '+(metadata.stage||state.stage)),element('p',!access.actions.edit?access.message:'Compare shared revisions or resume in chat before changing editorial decisions.','help')));
  }
  const evidence=element('div');
  evidence.append(element('p','Selected source revisions: '+result.sources.length));
  for(const source of result.sources)evidence.append(element('p',(source.source_id||source.item||'Source')+' · '+source.revision));
  for(const [name,asset]of Object.entries(result.assets))evidence.append(element('p',name+' · '+asset.status));
  for(const name of result.history)evidence.append(element('p',name));
  if(!result.history.length)evidence.append(element('p','Inspect earlier revisions in chat.'));
  content.append(disclosure('Evidence and history',evidence));
  if(result.location==='hub'&&access.actions.edit&&!state.conflict&&!state.shared_newer)content.append(button('Resume in this workspace',async()=>{
    const saved=await api('resume',{item:item.id});await showBlog({id:saved.id,location:'local'});await load();notice('Blog resumed. Use its continuation request to keep writing in chat.');
  }));
}
async function showBlog(item) {
  const args={id:item.id,location:item.location||'local'};if(item.revision)args.revision=item.revision;
  const result=await api('article?'+new URLSearchParams(args));
  $('detail-title').textContent=result.title;articleContent(item,result);$('detail-dialog').showModal();
}
async function showFinding(item) {
  const result=await api('finding?'+new URLSearchParams({id:item.id,key:item.key,location:item.location||'local'}));
  $('detail-title').textContent=result.article.title;articleContent(item,result.article,result);$('detail-dialog').showModal();
}
async function curate(item) {
  let result=await api('source?'+new URLSearchParams({id:item.id,location:item.location}));
  $('detail-title').textContent=item.title;$('detail-content').replaceChildren();
  if(!access.actions.edit){$('detail-content').append(element('p',access.message,'context-note'),element('pre',JSON.stringify(result.record.library||{},null,2),'source-excerpt'),element('h3','Saved text excerpt'),element('pre',result.excerpt||'No extracted text yet.','source-excerpt'));$('detail-dialog').showModal();return;}
  const form=element('form'),metadata=result.record.library||{},l=element('label','Curation'),select=element('select');select.name='curation';
  for(const state of ['active','pending','retired']){const option=element('option',state);option.value=state;option.selected=state===(metadata.curation||'active');select.append(option);}l.append(select);form.append(l);
  const fields={curation:select};
  for(const [key,label]of [['topics','Topics (comma separated)'],['products','Products (comma separated)'],['note','Source note']]){const field=element('label',label),input=element(key==='note'?'textarea':'input');input.name=key;input.value=key==='note'?(result.record.note||''):(metadata[key]||[]).join(', ');fields[key]=input;field.append(input);form.append(field);}
  const save=element('button','Save curation','primary');save.type='submit';const actions=element('div',undefined,'form-actions');actions.append(save);form.append(actions);
  let blocked=false;
  const conflict=element('div',undefined,'curation-conflict');conflict.hidden=true;
  const comparison=element('div');
  conflict.append(element('p','Your proposed changes are retained. Compare the latest saved reference before deciding what to submit.'),button('Reload and compare',async()=>{
    const latest=await api('source?'+new URLSearchParams({id:result.id,location:result.location}));
    const proposed=Object.fromEntries(new FormData(form));
    const current={curation:latest.record.library?.curation||'active',topics:(latest.record.library?.topics||[]).join(', '),products:(latest.record.library?.products||[]).join(', '),note:latest.record.note||''};
    comparison.replaceChildren(element('h3','Latest saved values'),element('pre',JSON.stringify(current,null,2),'source-excerpt'),element('h3','Your proposed values'),element('pre',JSON.stringify(proposed,null,2),'source-excerpt'),button('Keep my proposal for resubmission',()=>{result=latest;blocked=false;save.disabled=false;conflict.hidden=true;notice('Latest version selected. Review your retained proposal, then choose Save curation to submit it.');}),button('Use latest saved values',()=>{for(const [key,value]of Object.entries(current))fields[key].value=value;result=latest;blocked=false;save.disabled=false;conflict.hidden=true;notice('Latest saved values loaded. Edit them and choose Save curation when ready.');}));
  }),comparison);
  form.addEventListener('submit',async e=>{
    e.preventDefault();if(blocked)return;save.disabled=true;
    try {
      const data=Object.fromEntries(new FormData(form));
      if(data.curation==='retired'&&!confirm('Retire this reference from active search? Earlier snapshots remain in Git history.'))return;
      for(const key of ['topics','products'])data[key]=data[key].split(',').map(v=>v.trim()).filter(Boolean);
      const saved=await api('curate',{id:result.id,location:result.location,expected:result.expected,...data,confirmed:data.curation==='retired'});
      $('detail-dialog').close();await load();savedNotice(saved);
    } catch(error) {
      if(error.status===409){blocked=true;conflict.hidden=false;comparison.replaceChildren();}
      notice(error.message,true);
    } finally {save.disabled=blocked;}
  });
  $('detail-content').append(element('p',result.limitation),form,conflict,element('h3','Saved text excerpt'),element('pre',result.excerpt||'No extracted text yet.','source-excerpt'));
  if(result.truncated)$('detail-content').append(element('p','Excerpt only. Ask Blog Studio for selected passages in chat.','help'));
  $('detail-dialog').showModal();
}
async function editMemory(item) {
  const result=await api('memory-detail?'+new URLSearchParams({id:item.item,revision:item.revision}));
  if(!result.editable||!access.actions.memory){readOnlyMemory(result,result.read_only_reason||access.message);return;}
  memoryEdit=result.record;
  $('memory-name').value=result.record.title;$('memory-kind').value=result.record.kind;
  $('memory-body').value=result.body;$('memory-scope').value=result.record.scope.level;
  $('memory-key').value=result.record.scope.key;$('memory-title').textContent='Edit shared memory';
  $('memory-form').querySelector('[type=submit]').disabled=false;$('memory-dialog').showModal();
}
let importState=null, importBusy=false;
function importFields(){
  const type=$('import-type').value, network=['archive','feed','sitemap','urls'].includes(type);
  for(const name of ['folder','export','url','links','scope','collection','name']){
    const visible={folder:type==='folder',export:type==='export',url:network&&type!=='urls',links:type==='urls',scope:network,collection:type==='collection',name:type!=='collection'}[name];
    $('import-'+name+'-field').hidden=!visible;
  }
  $('import-name').required=type!=='collection';$('import-scope').required=network;
  $('import-url').required=network&&type!=='urls';
  $('import-url-label').textContent={archive:'Blog archive URL',feed:'Feed URL',sitemap:'Sitemap URL'}[type]||'Website URL';
}
function importBusyState(busy,message=''){
  importBusy=busy;
  for(const id of ['import-type','import-name','import-folder','import-export','import-url','import-links','import-scope','import-collection','import-preview-button','import-close','import-save','import-retry','import-reload','import-new'])$(id).disabled=busy;
  $('import-progress').textContent=message;$('import-progress').hidden=!message;
}
function renderImport(result){
  $('import-form').hidden=true;$('import-new').hidden=false;
  importState=result;sessionStorage.setItem('blog-studio-import-preview',result.preview);
  const box=$('import-preview');box.replaceChildren();box.hidden=false;
  box.append(element('h3',result.collection),element('p',result.candidates+' posts found · '+result.remaining+' not yet processed'));
  if(result.scope)box.append(element('p','Permitted posts: '+result.scope,'help'));
  const counts=result.counts||{};
  if(result.completed)box.append(element('p',`${counts.imported||0} added · ${counts.updated||0} updated · ${counts.unchanged||0} unchanged · ${counts.failed||0} failed`));
  if(counts.pending_extraction)box.append(element('p',counts.pending_extraction+' files need text extraction in chat.','context-note'));
  if(result.sharing_message)box.append(element('p',result.sharing_message,'context-note'));
  if(result.network_bytes)box.append(element('p','Download size is unknown until posts are fetched. Each batch reads up to 25 posts.','help'));
  if(result.discovery_limited)box.append(element('p','Discovery reached its limit. Use a smaller folder or website path to cover the remaining posts.','context-note'));
  if(result.excluded.length)box.append(disclosure('Excluded items',...result.excluded.map(v=>element('p',v.reason))));
  const list=element('ul',undefined,'detail-list');
  for(const post of result.sample){const row=element('li');row.append(element('strong',post.title||post.url||post.identity));if(post.author)row.append(element('p',post.author));if(post.url)row.append(link(post.url,'Original post ↗'));list.append(row);}
  box.append(disclosure('Preview posts'+(result.candidates>20?' (first 20)':''),list));
  if(result.failures.length)box.append(disclosure('Why posts failed',...result.failures.map(reason=>element('p',reason))));
  $('import-save').hidden=!result.remaining;$('import-save').textContent=(result.completed?'Import next ':'Import first ')+Math.min(25,result.remaining)+' posts';
  $('import-retry').hidden=!counts.failed;$('import-reload').hidden=false;
}
function resetImportPreview(){
  $('import-form').hidden=false;$('import-new').hidden=true;
  importState=null;sessionStorage.removeItem('blog-studio-import-preview');
  for(const id of ['import-preview','import-save','import-retry','import-reload'])$(id).hidden=true;
}
async function openImport(){
  if(!access.actions.edit)return;
  $('import-dialog').showModal();importFields();
  try{
    const result=await api('collections'), select=$('import-collection');select.replaceChildren();
    for(const collection of result.items){const option=element('option',collection.name);option.value=collection.key;select.append(option);}
    const saved=sessionStorage.getItem('blog-studio-import-preview');
    if(!importState){const preview=await api('library-preview'+(saved?'?preview='+encodeURIComponent(saved):''));if(preview.preview)renderImport(preview);}
  }catch(error){notice(error.message,true);}
}
async function encodeImportFile(file){
  const bytes=new Uint8Array(await file.arrayBuffer());let binary='';
  for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  return btoa(binary);
}
async function previewImport(){
  if(importBusy||!access.actions.edit)return;
  resetImportPreview();importBusyState(true,'Preparing your preview…');
  try{
    const type=$('import-type').value,payload=type==='collection'?{collection:$('import-collection').value}:{name:$('import-name').value.trim(),type};
    if(type==='folder'){
      const files=Array.from($('import-folder').files||[]).filter(f=>/\.(md|txt|html?|docx|pdf)$/i.test(f.name)&&!(f.webkitRelativePath||f.name).split('/').some(p=>p.startsWith('.')));
      if(!files.length||files.length>500||files.reduce((sum,f)=>sum+f.size,0)>10*1024*1024)throw new Error('Choose a folder with 1–500 supported files totaling at most 10 MiB.');
      payload.files=[];for(const file of files)payload.files.push({path:file.webkitRelativePath||file.name,content:await encodeImportFile(file)});
    }else if(type==='export'){
      const file=$('import-export').files[0];if(!file||!file.size||file.size>10*1024*1024)throw new Error('Choose a nonempty JSON export of at most 10 MiB.');
      payload.export=await encodeImportFile(file);
    }else if(type!=='collection'){
      payload.url=type==='urls'?$('import-links').value.trim():$('import-url').value.trim();payload.scope=$('import-scope').value.trim();
      if(type!=='urls')payload.discovery_scope=payload.url;
    }
    const result=await api('library-preview',{...payload,operation:operationFor('library-preview',payload)});
    renderImport(result);notice('Preview ready. Review the collection and scope, then choose Import.');
  }catch(error){notice(error.message,true);}finally{importBusyState(false);}
}
async function saveImport(retry=false){
  if(importBusy||!importState||!access.actions.edit)return;
  importBusyState(true,'Importing up to 25 posts. This may take a moment…');
  try{
    const payload={preview:importState.preview,expected:importState.expected,confirm:true,retry};
    const result=await api('library-import',{...payload,operation:operationFor('library-import',payload)});
    renderImport(result);await load();notice(result.sharing_message||'Posts saved to the Reference Library.');
  }catch(error){notice(error.message,true);}finally{importBusyState(false);}
}

for(const b of document.querySelectorAll('[data-view]'))b.addEventListener('click',()=>{view=b.dataset.view;offset=0;$('query').value='';document.querySelectorAll('[data-view]').forEach(e=>e.removeAttribute('aria-current'));b.setAttribute('aria-current','page');load().catch(e=>notice(e.message,true));});
for(const b of document.querySelectorAll('[data-close]'))b.addEventListener('click',()=>b.closest('dialog').close());
$('search-go').addEventListener('click',()=>{offset=0;load().catch(e=>notice(e.message,true));});$('query').addEventListener('keydown',e=>{if(e.key==='Enter')$('search-go').click();});$('stage').addEventListener('change',()=>{$('search-go').click();});
$('previous').addEventListener('click',()=>{if($('previous').disabled)return;offset=Math.max(0,offset-limit);load().catch(e=>notice(e.message,true));});$('next').addEventListener('click',()=>{if($('next').disabled)return;offset+=limit;load().catch(e=>notice(e.message,true));});
$('refresh-hub').addEventListener('click',async()=>{try{await api('refresh',{});await loadCapabilities();await load();notice('Team Hub refreshed. Google Docs content is refreshed separately in chat.');}catch(e){notice(e.message,true);}});
$('check-access').addEventListener('click',async()=>{await loadCapabilities();await load();});
$('import-new').addEventListener('click',()=>{if(!importBusy)resetImportPreview();});
$('import-open').addEventListener('click',openImport);
$('import-type').addEventListener('change',()=>{resetImportPreview();importFields();});
$('import-form').addEventListener('input',()=>{if(!importBusy)resetImportPreview();});
$('import-form').addEventListener('submit',e=>{e.preventDefault();previewImport();});
$('import-save').addEventListener('click',()=>saveImport(false));
$('import-retry').addEventListener('click',()=>saveImport(true));
$('import-dialog').addEventListener('cancel',e=>{if(importBusy)e.preventDefault();});
$('import-reload').addEventListener('click',async()=>{if(importBusy||!importState)return;importBusyState(true,'Reloading your saved preview…');try{renderImport(await api('library-preview?preview='+encodeURIComponent(importState.preview)));}catch(error){notice(error.message,true);}finally{importBusyState(false);}});

$('upload-open').addEventListener('click',()=>{if(access.actions.edit)$('upload-dialog').showModal();});
$('upload-form').addEventListener('submit',async e=>{e.preventDefault();const submit=e.target.querySelector('[type=submit]');submit.disabled=true;try{const file=$('upload-file').files[0];if(!file||file.size>10*1024*1024)throw new Error('Choose a file of at most 10 MiB.');const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));const payload={filename:file.name,content:btoa(binary),title:$('upload-title').value,author:$('upload-author').value,as_blog:$('upload-blog').checked};const result=await api('upload',{...payload,operation:operationFor('upload',payload)});$('upload-dialog').close();await load();savedNotice(result);}catch(error){notice(error.message,true);}finally{submit.disabled=false;}});
$('memory-open').addEventListener('click',()=>{if(!access.actions.memory)return;memoryEdit=null;$('memory-form').reset();$('memory-form').querySelector('[type=submit]').disabled=false;$('memory-title').textContent='Add shared memory';$('memory-dialog').showModal();});
$('memory-form').addEventListener('submit',async e=>{e.preventDefault();const submit=e.target.querySelector('[type=submit]');submit.disabled=true;try{const payload={kind:$('memory-kind').value,title:$('memory-name').value,body:$('memory-body').value,scope:$('memory-scope').value,scope_key:$('memory-key').value,...(memoryEdit?{item:memoryEdit.item,revision:memoryEdit.revision}:{})};const saved=await api('memory',{...payload,operation:operationFor('memory',payload)});$('memory-dialog').close();await load();savedNotice(saved);}catch(error){notice(error.message,true);}finally{submit.disabled=false;}});
applyCapabilities();loadCapabilities().then(()=>load()).catch(e=>notice(e.message,true));
