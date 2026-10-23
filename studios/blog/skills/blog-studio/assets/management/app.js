'use strict';
const $ = id => document.getElementById(id);
// Marketing Studio names its own address when it opens this studio, so the page can link back
// to that tab. Only the same scheme and host on another port is accepted.
function suiteHome(hash, here) {
  const named = new URLSearchParams(String(hash).replace(/^#/, '')).get('home') || '';
  const found = /^(https?:)\/\/([^/:?#@\s]+):(\d{1,5})\/?$/.exec(named);
  return found && found[1] === here.protocol && found[2] === here.hostname && found[3] !== here.port
    && Number(found[3]) > 0 && Number(found[3]) < 65536
    ? found[1] + '//' + found[2] + ':' + found[3] : '';
}
// Marketing Studio says when it opened this studio in its own tab, as it does on a phone: the
// way back then stays in this tab, where Marketing Studio still holds its key.
function suiteBack(hash) {
  return new URLSearchParams(String(hash).replace(/^#/, '')).get('back') === 'tab';
}
// Marketing Studio also names its home page's port on this page when it started this studio, so
// the way back is found however the page was reached. Marketing Studio shares this page's host.
function suitePort(port, here) {
  return /^[1-9][0-9]{0,4}$/.test(String(port || ''))
    ? suiteHome('#home=' + encodeURIComponent(here.protocol + '//' + here.hostname + ':' + port), here) : '';
}
const token = location.hash.slice(1).split('&')[0] || sessionStorage.getItem('blog-studio-session') || '';
// The port the server names belongs to the Marketing Studio that started it, so it is preferred
// to one kept from an earlier session.
const suite = suiteHome(location.hash, location) || suitePort(document.body?.dataset?.suitePort, location)
  || sessionStorage.getItem('marketing-studio-home') || '';
if(token)sessionStorage.setItem('blog-studio-session',token);
if(suite)sessionStorage.setItem('marketing-studio-home',suite);
const suiteTab = suiteBack(location.hash) || sessionStorage.getItem('marketing-studio-back') === 'tab';
if(suiteTab)sessionStorage.setItem('marketing-studio-back','tab');
history.replaceState(null, '', location.pathname+(location.search||''));
// Ticked library rows by location and ID: a local item goes by its ID, a Team Hub one with its location.
let view = 'board', offset = 0, total = 0, memoryEdit = null, librarySelection = new Map(), libraryShown = [];
function libraryEntry(item){return item.location==='hub'?{id:item.id,location:'hub'}:item.id;}
// What a library item is for, as the catalog's role says it.
const LIBRARY_ROLES={facts:'Facts',messaging:'Approved messaging',example:'Example','voice-sample':'Voice sample','style-sample':'Style sample'};
const limit = 20;
let loadGeneration = 0, loadController = null, renderedState = null;
let access = {status:'checking',message:'Checking Hub access…',actions:{edit:false,memory:false,refresh:false}};
let accessGeneration = 0;
const operationCache = new Map();
// getRandomValues is available on trusted-LAN HTTP as well as secure origins.
function operationId(){return Array.from(crypto.getRandomValues(new Uint8Array(16)),value=>value.toString(16).padStart(2,'0')).join('');}
function operationFor(kind,data){const key=kind+JSON.stringify(data);if(!operationCache.has(key))operationCache.set(key,operationId());return operationCache.get(key);}
const views = {runs:['Writing runs','Start a blog, review each stage, and pick up where you left off.','Your writing runs'],board:['All blogs','Every saved blog by stage and owner. Open one to read it, decide or keep writing.','All blogs'],inbox:['Review findings','Find waiting decisions, review findings and stale companions.','Review findings'],library:['Team library','Finished blogs, files, links and Google Docs your team writes from, by role, kind of post and author.','Library items'],memory:['Team memory','Keep useful knowledge and writing guidance easy to find.','Shared notes, context and rules']};
function element(tag, text, cls) {const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function notice(message, error=false) {
  const dialog=document.querySelector('dialog[open]');
  let target=$('notice');
  if(dialog){target=dialog.querySelector('.dialog-notice');if(!target){target=element('p',undefined,'dialog-notice');target.setAttribute('role','alert');dialog.append(target);}}
  target.textContent=message;target.className=error?'dialog-notice error':'dialog-notice';target.hidden=false;
}
function savedNotice(result) {if(result.team_sync){notice(result.team_sync.shared?'Saved and shared with the team repository.':result.team_sync.notice||'Saved on this computer; sharing is pending.');return;}notice((result.receipts||[]).map(r=>r.label+': '+r.message).join(' ')||result.next_step||'Saved.');}
// Each view's toolbar: its one primary action, then the way to the other views. The buttons
// are made again whenever the view or the access changes, so they always follow both.
function legacyActions() {
  const made=[];
  const add=(id,text,action,cls='button',ready=true)=>{const b=button(text,action,cls);b.id=id;b.disabled=!ready;made.push(b);return b;};
  if(view==='board')add('new-blog','New blog',()=>newBlog(),'button button-filled',access.actions.edit);
  if(view==='library'){
    add('library-add-open','Add to library',()=>sLibraryAdd(),'button button-filled',access.actions.edit);
    // A secondary action of this view: under the lede, so the toolbar keeps one primary.
    const voices=button('Create voices for every author',()=>sVoicesForAuthors(),'button button-quiet');voices.id='library-voices-open';voices.disabled=!access.actions.edit;
    $('view-actions').replaceChildren(voices);
  }else $('view-actions').replaceChildren();
  if(view==='memory')add('memory-open','Add memory',openMemory,'button button-filled',access.actions.memory);
  if(typeof sTools==='function')add('legacy-tools','Library and team tools',()=>sTools(),'button button-quiet');
  return made;
}
function legacyToolbar() {
  // Only while a legacy view is the one showing; the guided screens draw their own toolbar.
  if($('editorial-screen').hidden)return;
  $('actions').replaceChildren(...legacyActions());
}
function openMemory() {
  if(!access.actions.memory)return;
  memoryEdit=null;$('memory-truncated').hidden=true;$('memory-form').reset();
  $('memory-form').querySelector('[type=submit]').disabled=false;$('memory-title').textContent='Add shared memory';$('memory-dialog').showModal();
}
function analysisChoice(prefix) {
  // Sent only when an analysis CLI is configured; unchecked means "do not send this text to the model".
  const analysis=access.analysis||{};
  return analysis.harness?{analyze:$(prefix+'-analyze').checked!==false}:{};
}
function applyCapabilities() {
  // The Hub access panel has something to say only when a Hub is selected or access failed.
  $('access-panel').hidden=!(access.hub||['read-only','unverified','access-expired','unavailable','identity-mismatch'].includes(access.status));
  $('access-status').textContent=access.message;
  $('refresh-hub').disabled=!access.actions.refresh;
  legacyToolbar();
  const analysis=access.analysis||{};
  $('analysis-status').textContent=analysis.message||'';
  $('analysis-status').hidden=!analysis.message;
  for(const prefix of ['upload','import']) {
    $(prefix+'-analyze-field').hidden=!analysis.harness;
    $(prefix+'-analyze-label').textContent='Summarize and tag with '+(analysis.label||'your analysis CLI');
    $(prefix+'-analysis-note').textContent=analysis.message||'';
    $(prefix+'-analysis-note').hidden=!analysis.message;
  }
  const where=[];
  if(access.workspace)where.push('Workspace: '+access.workspace);
  if(access.team)where.push('Team repository: '+(access.team.repository||'local'));
  else if(access.hub)where.push('Team Hub: '+(access.hub.repository||'selected'));
  else if(access.workspace)where.push('No Team Hub selected');
  $('desk-identity').textContent=where.join(' · ');
  $('desk-identity').hidden=!where.length;
}
async function busy(control, label, action) {
  // One visible "working" state for slow actions: disabled, announced, and always restored.
  const text=control.textContent;
  control.disabled=true;control.setAttribute('aria-busy','true');control.textContent=label;
  try {return await action();}
  finally {control.disabled=false;control.removeAttribute('aria-busy');control.textContent=text;}
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
  const field=element('textarea',undefined,'input');field.value=command;field.readOnly=true;field.rows=3;
  field.setAttribute('aria-label','Article or memory continuation request');
  const copy=button('Copy request',async()=>{
    try {await navigator.clipboard.writeText(command);notice('Request copied. Paste it into your writing chat.');}
    catch(error){field.focus();field.select();notice('Select and copy the request, then paste it into your writing chat.');}
  },'button button-filled');
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
  for(const receipt of pending){const row=element('div');row.append(element('p',receipt.label+': '+receipt.message));if(receipt.retry&&access.actions.edit){const retry=button('Retry sync',()=>busy(retry,'Retrying…',async()=>{const saved=await api('retry-sync',{id:receipt.id});savedNotice(saved);await loadReceipts();}));row.append(retry);}$('sync-status').append(row);}
}

async function api(route, data, signal) {
  if(data)document.querySelectorAll('.dialog-notice').forEach(e=>e.hidden=true);
  const headers={'X-Blog-Studio-Token':token,...(data?{'Content-Type':'application/json'}:{})};
  let response,result;
  try {
    response=await fetch('/api/'+route,{method:data?'POST':'GET',headers,body:data?JSON.stringify(data):undefined,signal});
  } catch(error) {
    if(error.name==='AbortError')throw error;
    throw new Error('The desk helper is not answering. Ask Blog Studio in chat to open the editorial desk again.');
  }
  try {result=await response.json();}
  catch(error) {throw new Error('The desk helper sent a reply this page could not read. Reload the desk.');}
  if(!response.ok){const error=new Error(result.error||'The operation could not be completed.');error.status=response.status;error.code=result.code;throw error;}
  return result;
}
function link(url, text) {if(!/^https:\/\//.test(url||''))return element('span',text);const a=element('a',text);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}
const BADGE_LABELS={'not-run':'Not run','not-checked-live':'Not checked live','local-saved-not-shared':'Saved locally','pending-review':'Awaiting review','queued-unavailable':'Waiting to sync','needs-local-check':'Needs local check'};
const BADGE_TONES=new Set(['ready','review','stale','waiting','unavailable','published','conflict','conflicting','conflicted']);
function badge(value) {
  // Status text can come from shared Hub records: show it as text, but never let it choose a CSS class.
  const name=String(value??'');
  return element('span',BADGE_LABELS[name]||name,BADGE_TONES.has(name)?'badge '+name:'badge');
}
function unreadableNote(result) {
  // Blogs the helper could not read are named instead of silently missing.
  const problems=result.problems||[];
  if(!problems.length)return null;
  const count=result.problem_count||problems.length,one=count===1;
  const names=problems.map(p=>p.id+(p.location==='hub'?' (Team Hub)':'')).join(', ')+(count>problems.length?', and more':'');
  const box=element('div',undefined,'context-note unreadable');box.setAttribute('role','note');
  box.append(element('p',count+(one?' blog could not be read and is':' blogs could not be read and are')+' not listed: '+names+'. Ask Blog Studio in chat to inspect '+(one?'it':'them')+'.'));
  return box;
}
function button(text, action, cls='button') {const b=element('button',text,cls);b.type='button';b.addEventListener('click',()=>Promise.resolve(action()).catch(e=>notice(e.message,true)));return b;}
function textCell(row, text) {const cell=element('td',text??'—');cell.setAttribute('role','cell');row.append(cell);return cell;}
function sameView(left, right) {
  return left && right && ['view','query','stage','sourceStatus','collection','role','kind','author'].every(key=>left[key]===right[key]);
}
function loading(state, pending) {
  $('results').setAttribute('aria-busy',String(pending));
  $('loading').hidden=!pending;
  $('loading').textContent=pending?'Loading '+views[state.view][0].toLowerCase()+'…':'';
  $('previous').disabled=pending || !sameView(renderedState,state) || renderedState.offset===0;
  $('next').disabled=pending || !sameView(renderedState,state) || renderedState.offset+limit>=total;
}
// The filters of a view as the server reads them; the same for a page and for Select all matching.
function filterArgs(state) {
  const args=new URLSearchParams({query:state.query});
  if(state.stage)args.set('stage',state.stage);
  if(state.sourceStatus)args.set('status',state.sourceStatus);
  if(state.collection)args.set('collection',state.collection);
  for(const key of ['role','kind','author'])if(state[key])args.set(key,state[key]);
  return args;
}
async function load() {
  const state=Object.freeze({view,offset,query:$('query').value,stage:view==='board'?$('stage').value:'',sourceStatus:view==='library'?$('library-status').value:'',collection:view==='library'?$('library-collection').value:'',role:view==='library'?$('library-role').value:'',kind:view==='library'?$('library-kind').value:'',author:view==='library'?$('library-author').value.trim():''});
  const generation=++loadGeneration;
  if(loadController)loadController.abort();
  const controller=new AbortController();loadController=controller;
  const current=()=>generation===loadGeneration;
  loading(state,true);
  loadReceipts(controller.signal,current).catch(error=>{if(current()&&error.name!=='AbortError')notice(error.message,true);});
  const args=filterArgs(state);args.set('limit',String(limit));args.set('offset',String(state.offset));
  try {
    const result=await api(state.view+'?'+args,undefined,controller.signal);
    if(!current())return;
    total=result.total;renderedState=state;render(state,result);
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
  if(view==='runs'){renderRuns(result);return;}
  $('heading').textContent=views[view][0];$('subtitle').textContent=views[view][1];$('section-title').textContent=views[view][2];$('count').textContent=total+' '+(total===1?'item':'items');
  $('stage-filter').hidden=view!=='board';for(const name of ['status','role','kind','author'])$('library-'+name+'-filter').hidden=view!=='library';$('library-more-filters').hidden=view!=='library';
  if(view==='library'){const kinds=$('library-kind'),chosen=kinds.value;kinds.replaceChildren(...[['','Any kind'],...(result.kinds||[]).map(kind=>[kind.id,kind.name])].map(([value,text])=>{const option=element('option',text);option.value=value;return option;}));kinds.value=chosen;}
  {const chosen=view==='library'?['library-role','library-kind','library-author','library-status'].filter(id=>$(id).value.trim()).length+($('library-collection').value.trim()?1:0):view==='board'&&$('stage').value?1:0;$('filters-toggle').textContent=chosen?'Filters ('+chosen+')':'Filters';}
  libraryShown=view==='library'?result.items:[];librarySelectionBar();legacyToolbar();$('previous').disabled=offset===0;$('next').disabled=offset+limit>=total;$('page-label').textContent=total?`${offset+1}–${Math.min(offset+limit,total)} of ${total}`:'No items yet';
  $('query').placeholder={board:'Blog title, author, owner…',inbox:'Blog, finding, status…',library:'Title, author, topic…',memory:'Title, kind, scope…'}[view];
  $('observation').textContent=result.observation||result.google_observation||'Saved content only. Historical product claims need current verification.';
  $('results').replaceChildren();
  const unreadable=view==='board'||view==='inbox'?unreadableNote(result):null;
  if(unreadable)$('results').append(unreadable);
  if(!result.items.length){const box=element('div',undefined,'empty');box.append(element('h3',{board:'Your next blog starts here',inbox:'Nothing in this saved inbox',library:'Build your reference shelf',memory:'Give your team useful context'}[view]),element('p',{board:'Choose New blog to write here, upload a draft, or start a blog in chat.',inbox:'Run a review in chat to collect findings. Google review status is not checked live here.',library:'Choose Add to library for files, links, a Google Doc, or a whole blog, site or feed.',memory:'Join a Team Hub, then save a note, context, or writing rule.'}[view]));$('results').append(box);return;}
  const table=element('table'),head=element('tr');table.setAttribute('role','table');head.setAttribute('role','row');table.className='table view-'+view;const headings={board:['Blog / author','Stage','Owner / due','Working copy'],inbox:['Blog','Finding','Status','Next action'],library:[...(access.actions.edit?['Selected']:[]),'Title','Author','Role','Status','Action'],memory:['Memory','Kind','Applies to','Actions']}[view];
  // On a phone each library row is a card: the title and the action need no label.
  const labels=view==='library'?headings.map(h=>['Selected','Title','Action'].includes(h)?'':h):headings;headings.forEach(h=>{const th=element('th',h);if(h==='Selected'){th.textContent='';th.setAttribute('aria-label','Selected');}th.setAttribute('scope','col');th.setAttribute('role','columnheader');head.append(th);});const thead=element('thead');thead.append(head);table.append(thead);const body=element('tbody');
  for(const item of result.items){const row=element('tr');row.setAttribute('role','row');
    if(view==='board'){const cell=textCell(row,'');cell.append(button(item.title,()=>showBlog(item),'title-button'),element('p',item.author));const stage=textCell(row,'');stage.append(badge(item.stage));if(item.conflict||item.shared_newer)stage.append(element('p',item.conflict?'Competing revisions':'New shared revision'));const owner=textCell(row,item.owner);if(item.due)owner.append(element('p',(item.overdue?'Overdue · ':'Due · ')+item.due,item.overdue?'overdue':''));const doc=textCell(row,'');doc.append(item.google?link(item.google.url,'Open Google Doc ↗'):element('span',item.location==='hub'?'Saved in Team Hub':'Local writing'));if(item.google)doc.append(element('p','Saved link; refresh Google in chat'));}
    if(view==='inbox'){const blog=textCell(row,'');blog.append(button(item.title,()=>showBlog({...item,location:item.location||'local'}),'title-button'));const finding=textCell(row,'');finding.append(button(item.kind,()=>showFinding(item),'title-button'));if(item.finding)finding.append(element('p',item.finding.message||item.finding.detail||item.finding.original||'Inspect this saved finding in chat.'));const status=textCell(row,'');status.append(badge(item.status));const action=textCell(row,'');action.append(button('Inspect finding',()=>showFinding(item)),element('p',item.action));}
    if(view==='library'){
      const key=libraryKey(item);
      if(access.actions.edit){const pick=element('input');pick.type='checkbox';pick.className='library-pick';pick.dataset.key=key;pick.setAttribute('aria-label','Select '+item.title);pick.checked=librarySelection.has(key);pick.addEventListener('change',()=>{if(pick.checked)librarySelection.set(key,libraryEntry(item));else librarySelection.delete(key);librarySelectionBar();});const tick=textCell(row,'');tick.className='pick-cell';tick.append(pick);}
      const cell=textCell(row,'');cell.append(element('strong',item.title,'item-title'));
      const facts=[item.library.published||'',(item.collection_names||item.library.collections||[]).join(', ')].filter(Boolean).join(' · ');if(facts)cell.append(element('p',facts));
      if(item.library.canonical_url)cell.append(link(item.library.canonical_url,'Original post ↗'));
      textCell(row,item.author||'Author unknown');
      textCell(row,(LIBRARY_ROLES[item.role]||'Facts')+(item.kind_name?' · '+item.kind_name:'')+['voice-sample','style-sample'].filter(purpose=>purpose!==item.role&&(item.purposes||[]).includes(purpose)).map(purpose=>' · '+LIBRARY_ROLES[purpose].toLowerCase()).join(''));
      const status=textCell(row,'');status.append(badge(item.library.curation||item.status),badge(item.analysis?.status==='ready'?'Analyzed':item.analysis?.status==='needs-extraction'?'Needs extraction':'Needs analysis'));
      const action=textCell(row,'');action.append(button(access.actions.edit?'Review details':'Read reference',()=>curate(item)));if(item.historical)action.append(element('p','Historical reference'));}
    if(view==='memory'){const cell=textCell(row,'');cell.append(button(item.title,()=>editMemory(item),'title-button'));if(item.conflict)cell.append(element('p','Competing revisions'));if(item.lesson_status)cell.append(element('p','Candidate lesson · '+item.lesson_status));textCell(row,item.kind);textCell(row,item.scope.level+(item.scope.key?' · '+item.scope.key:''));textCell(row,item.lesson?'Review / promote in chat':item.focused_workflow?'Manage in chat':item.kind==='decision'||item.conflict||!access.actions.memory?'Read details':'Open to read or edit');}
    Array.from(row.children).forEach((cell,index)=>cell.setAttribute('data-label',labels[index]));
    body.append(row);
  }table.append(body);const wrap=element('div',undefined,'table-wrap');wrap.append(table);$('results').append(wrap);
}
// The selection bar shows while anything is ticked. A tick stays as you page and change the
// filters, so the count can include rows not in view; Select all matching ticks what the
// filters match at that moment, and later filters neither add to it nor take from it.
function librarySelectionBar() {
  const count=librarySelection.size,shown=view==='library'?libraryShown:[],ticked=shown.filter(item=>librarySelection.has(libraryKey(item))).length,hidden=count-ticked;
  $('library-selection').hidden=view!=='library'||!count||!access.actions.edit;
  $('library-selection-count').textContent=count+' selected';
  $('library-selection-hidden').textContent=hidden?(hidden===1?'1 of them is':hidden+' of them are')+' not in this view.':'';
  $('library-select-shown').textContent='Select all '+shown.length+' on this page';$('library-select-shown').hidden=!shown.length||ticked===shown.length;
  $('library-select-matching').textContent='Select all '+total+' matching';$('library-select-matching').hidden=view!=='library'||total<=shown.length||allMatchingTicked();
  $('library-select-page').hidden=view!=='library'||!shown.length||!access.actions.edit;
  const box=$('library-select-page-box');box.checked=!!shown.length&&ticked===shown.length;box.indeterminate=ticked>0&&ticked<shown.length;
}
function libraryKey(item){return (item.location||'local')+':'+item.id;}
function tickLibrary(items,on) {
  for(const item of items){const key=libraryKey(item);if(on)librarySelection.set(key,libraryEntry(item));else librarySelection.delete(key);}
  for(const pick of document.querySelectorAll('.library-pick'))pick.checked=librarySelection.has(pick.dataset.key);
  librarySelectionBar();
}
// What the last Select all matching ticked, under which filters: the button hides only
// while every one of those matches is still ticked, not when the selection is merely large.
let libraryMatched=null;
const LIBRARY_SELECTION_LIMIT=500;
function allMatchingTicked(){
  const state=renderedState;if(!libraryMatched||!state||libraryMatched.filters!==filterArgs(state).toString())return false;
  return libraryMatched.keys.every(key=>librarySelection.has(key));
}
async function selectAllMatching(control) {
  // Every item the same filters match, through the server, up to its limit.
  const state=renderedState;if(!state||state.view!=='library')return;
  const found=await busy(control,'Selecting…',()=>api('library-matching?'+filterArgs(state)));
  const fresh=found.items.filter(item=>!librarySelection.has(libraryKey(item))).length;
  if(librarySelection.size+fresh>LIBRARY_SELECTION_LIMIT){
    notice('That would tick '+(librarySelection.size+fresh)+' items, and a selection holds at most '+LIBRARY_SELECTION_LIMIT+'. Clear the selection or narrow the filters first.',true);
    return;
  }
  libraryMatched={filters:filterArgs(state).toString(),keys:found.items.map(libraryKey)};
  tickLibrary(found.items,true);
  if(found.capped)notice('Selected the first '+found.items.length+' of '+found.total+' matching items. Narrow the filters to choose the rest.');
}
function disclosure(label, ...content) {
  const box=element('details'),summary=element('summary',label);box.append(summary,...content);return box;
}
function changedFields(proposed, saved) {
  // Forms send only what the person changed; an untouched field is never a decision.
  const changes={};
  for(const key of Object.keys(proposed))if(JSON.stringify(proposed[key])!==JSON.stringify(saved[key]))changes[key]=proposed[key];
  return changes;
}
function editorialForm(item, result) {
  const data=result.record.editorial||{},form=element('form',undefined,'narrow'),stages=['idea','draft','review','ready','published'];
  // An unknown recorded stage is shown as "follow writing progress", so leaving the select alone posts nothing.
  const saved={owner:data.owner||'',due:data.due||'',publication_url:data.publication_url||'',stage:stages.includes(data.stage)?data.stage:''};
  for(const [key,label]of [['owner','Owner'],['due','Due date'],['publication_url','Publication URL']]) {
    const field=element('label',label,'field'),input=element('input',undefined,'input');input.name=key;input.value=saved[key];
    input.type=key==='due'?'date':'text';input.maxLength=key==='publication_url'?2000:200;field.append(input);form.append(field);
    saved[key]=key==='owner'?input.value.trim():input.value;  // What an untouched field returns later.
  }
  const field=element('label','Editorial stage','field'),select=element('select',undefined,'input');select.name='stage';
  const follow=element('option','Follow writing progress (now: '+result.view.stage+')');follow.value='';select.append(follow);
  for(const stage of stages) {
    const option=element('option',stage);option.value=stage;select.append(option);
  }
  select.value=saved.stage;
  field.append(select);form.append(field);
  // Ready and published are decisions about one saved draft. They are recorded only with this box checked.
  const confirmRow=element('label',undefined,'check'),confirmBox=element('input'),confirmText=element('span');
  confirmBox.type='checkbox';confirmRow.append(confirmBox,confirmText);form.append(confirmRow);
  const stale=Boolean(result.view.decision_stale);
  const needsConfirmation=()=>{
    const stage=select.value,needed=(stage==='ready'||stage==='published')&&(stage!==saved.stage||stale);
    confirmRow.hidden=!needed;
    if(!needed)confirmBox.checked=false;
    confirmText.textContent=stage===saved.stage?'The draft changed after this decision. Record “'+stage+'” again for the current saved draft.':'Record “'+stage+'” for the current saved draft.';
    return needed;
  };
  select.addEventListener('change',needsConfirmation);needsConfirmation();
  const actions=element('div',undefined,'bar form-actions'),save=element('button','Save editorial decision','button button-filled');save.type='submit';actions.append(save);form.append(actions);
  form.addEventListener('submit',async event=>{
    event.preventDefault();save.disabled=true;
    try {
      const values=Object.fromEntries(new FormData(form));
      values.owner=values.owner.trim();
      const changes=changedFields(values,saved),needed=needsConfirmation();
      if('stage' in changes&&needed&&!confirmBox.checked){notice('Check the box to record “'+values.stage+'”, or choose another stage.',true);return;}
      if(needed&&confirmBox.checked){changes.stage=values.stage;changes.confirm_stage=true;}
      if(!Object.keys(changes).length){notice('No changes to save.');return;}
      const saving=await api('schedule',{id:item.id,expected:result.expected,...changes});
      $('detail-dialog').close();await load();savedNotice(saving);
    }
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
  if(result.location==='local'&&access.actions.edit&&!state.conflict&&!state.shared_newer)content.append(button('Open writing run',()=>openBlogRun(item.id)));
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
  if(result.location==='hub'&&access.actions.edit&&!state.conflict&&!state.shared_newer){
    const resume=button('Resume in this workspace',()=>busy(resume,'Resuming…',async()=>{
      const saved=await api('resume',{item:item.id});await showBlog({id:saved.id,location:'local'});await load();notice('Blog resumed. Use its continuation request to keep writing in chat.');
    }));
    content.append(resume);
  }
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
  const analysis=result.record.analysis||{};
  const overview=element('section',undefined,'analysis-overview');overview.append(element('h3',analysis.status==='ready'?'Automatic analysis':'Needs analysis'));
  if(analysis.summary)overview.append(element('p',analysis.summary));
  if(analysis.kind)overview.append(element('p',analysis.kind));
  for(const caution of analysis.cautions||[])overview.append(element('p',caution,'help'));
  if(analysis.message)overview.append(element('p',analysis.message,'help'));
  if(analysis.status!=='ready'&&access.actions.edit){
    const analyze=button('Analyze reference',()=>busy(analyze,'Analyzing… this can take a few minutes',async()=>{
      const running=api('analyze',{id:result.id,location:result.location,expected:result.expected});
      notice('Analyzing with your selected writing CLI. Up to 24,000 characters of this reference are sent through it to its model provider.');
      await running;await load();await curate(item);
    }));
    overview.append(analyze);
  }
  $('detail-content').append(overview);
  if(!access.actions.edit){$('detail-content').append(element('p',access.message,'context-note'),element('pre',JSON.stringify(result.record.library||{},null,2),'source-excerpt'),element('h3','Saved text excerpt'),element('pre',result.excerpt||'No extracted text yet.','source-excerpt'));$('detail-dialog').showModal();return;}
  const form=element('form',undefined,'narrow'),metadata=result.record.library||{},l=element('label','Curation','field'),select=element('select',undefined,'input');select.name='curation';
  for(const state of ['active','pending','retired']){const option=element('option',state);option.value=state;option.selected=state===(metadata.curation||'active');select.append(option);}l.append(select);form.append(l);
  const fields={curation:select};
  for(const [key,label]of [['author','Author (whose writing this is)'],['topics','Topics (comma separated)'],['products','Products (comma separated)'],['note','Source note']]){const field=element('label',label,'field'),input=element(key==='note'?'textarea':'input',undefined,'input');input.name=key;input.value=key==='note'?(result.record.note||''):key==='author'?(result.record.author||''):(metadata[key]||[]).join(', ');if(key==='author')input.maxLength=200;fields[key]=input;field.append(input);form.append(field);}
  const save=element('button','Save curation','button button-filled');save.type='submit';const actions=element('div',undefined,'bar form-actions');actions.append(save);form.append(actions);
  let blocked=false;
  const conflict=element('div',undefined,'curation-conflict');conflict.hidden=true;
  const comparison=element('div');
  conflict.append(element('p','Your proposed changes are retained. Compare the latest saved reference before deciding what to submit.'),button('Reload and compare',async()=>{
    const latest=await api('source?'+new URLSearchParams({id:result.id,location:result.location}));
    const proposed=Object.fromEntries(new FormData(form));
    const current={curation:latest.record.library?.curation||'active',author:latest.record.author||'',topics:(latest.record.library?.topics||[]).join(', '),products:(latest.record.library?.products||[]).join(', '),note:latest.record.note||''};
    comparison.replaceChildren(element('h3','Latest saved values'),element('pre',JSON.stringify(current,null,2),'source-excerpt'),element('h3','Your proposed values'),element('pre',JSON.stringify(proposed,null,2),'source-excerpt'),button('Keep my proposal for resubmission',()=>{result=latest;blocked=false;save.disabled=false;conflict.hidden=true;notice('Latest version selected. Review your retained proposal, then choose Save curation to submit it.');}),button('Use latest saved values',()=>{for(const [key,value]of Object.entries(current))fields[key].value=value;result=latest;blocked=false;save.disabled=false;conflict.hidden=true;notice('Latest saved values loaded. Edit them and choose Save curation when ready.');}));
  }),comparison);
  form.addEventListener('submit',async e=>{
    e.preventDefault();if(blocked)return;save.disabled=true;
    try {
      const data=Object.fromEntries(new FormData(form));
      // Compare what the form holds now with what it would show for the saved reference, in the same shape.
      const tags=text=>text.split(',').map(v=>v.trim()).filter(Boolean),library=result.record.library||{};
      const proposed={curation:data.curation,author:(data.author||'').trim(),topics:tags(data.topics),products:tags(data.products),note:data.note};
      const changes=changedFields(proposed,{
        curation:['active','pending','retired'].includes(library.curation)?library.curation:'active',
        author:(result.record.author||'').trim(),
        topics:tags((library.topics||[]).join(', ')),products:tags((library.products||[]).join(', ')),
        note:(result.record.note||'').replace(/\r\n?/g,'\n')});
      if(!Object.keys(changes).length){notice('No changes to save.');return;}
      if(changes.curation==='retired'){
        if(!confirm('Retire this reference from active search? Earlier snapshots remain in Git history.'))return;
        changes.confirmed=true;
      }
      const saved=await api('curate',{id:result.id,location:result.location,expected:result.expected,...changes});
      $('detail-dialog').close();await load();savedNotice(saved);
      if(changes.curation==='retired'){const current=await api('source?'+new URLSearchParams({id:result.id,location:result.location}));const undo=button('Undo retirement',async()=>{const restored=await api('curate',{id:result.id,location:result.location,expected:current.expected,curation:library.curation||'active'});await load();savedNotice(restored);});$('notice').append(undo);}
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
  $('memory-name').value=result.record.title;$('memory-kind').value=result.record.kind;
  $('memory-body').value=result.body;$('memory-scope').value=result.record.scope.level;
  $('memory-key').value=result.record.scope.key;$('memory-title').textContent='Edit shared memory';
  // Read the baseline back from the controls: it is exactly what an untouched field returns later.
  const loaded={kind:$('memory-kind').value,title:$('memory-name').value,body:$('memory-body').value,scope:$('memory-scope').value,scope_key:$('memory-key').value};
  memoryEdit={item:result.record.item,revision:result.record.revision,loaded};
  $('memory-truncated').hidden=!result.truncated;
  $('memory-form').querySelector('[type=submit]').disabled=false;$('memory-dialog').showModal();
}
let importState=null, importBusy=false, importChecks=new Map(), importCollections=[];
function refreshKind() {
  // 'folder' or 'export' when the chosen existing collection can take a new file selection.
  if($('import-type').value!=='collection')return null;
  const chosen=importCollections.find(c=>c.key===$('import-collection').value);
  return chosen&&chosen.refresh_files?chosen.type:null;
}
function importSelectionControls(){
  const selected=[...importChecks.entries()].filter(([,check])=>check.checked).map(([key])=>key);
  const pending=importState?importState.posts.filter(p=>selected.includes(p.key)&&p.status==='pending').length:0;
  const failed=importState?importState.posts.filter(p=>selected.includes(p.key)&&p.status==='failed').length:0;
  $('import-save').textContent='Import selected '+Math.min(25,pending)+' posts';
  $('import-save').disabled=importBusy||!pending;
  $('import-retry').textContent='Retry selected '+Math.min(25,failed)+' failed posts';
  $('import-retry').disabled=importBusy||!failed;
  if($('import-selection-count'))$('import-selection-count').textContent=selected.length+' selected';
  for(const [key,check] of importChecks)check.disabled=importBusy||!['pending','failed'].includes(importState.posts.find(p=>p.key===key).status);
  return selected;
}
function importFields(){
  const type=$('import-type').value, network=['archive','feed','sitemap','urls'].includes(type), again=refreshKind();
  for(const name of ['folder','export','url','links','scope','collection','name']){
    const visible={folder:type==='folder'||again==='folder',export:type==='export'||again==='export',url:network&&type!=='urls',links:type==='urls',scope:network,collection:type==='collection',name:type!=='collection'}[name];
    $('import-'+name+'-field').hidden=!visible;
  }
  $('import-folder-help').textContent=again==='folder'
    ?'Optional: choose the folder again to pick up new or changed files. Posts already saved are not duplicated. Leave this empty to re-check the files chosen earlier.'
    :'Markdown, text, HTML, DOCX and PDF. Up to 500 files and 10 MiB in total. For larger folders, import in chat.';
  $('import-export-help').textContent=again==='export'
    ?'Optional: choose a newer export file for this collection. Leave this empty to re-check the export chosen earlier.'
    :'A list of posts with title, text, and a URL or external_id. Author, dates, topics and products are optional.';
  $('import-name').required=type!=='collection';$('import-scope').required=network;
  $('import-url').required=network&&type!=='urls';
  $('import-url-label').textContent={archive:'Blog archive URL',feed:'Feed URL',sitemap:'Sitemap URL'}[type]||'Website URL';
}
function importBusyState(busy,message=''){
  importBusy=busy;
  for(const id of ['import-type','import-name','import-folder','import-export','import-url','import-links','import-scope','import-collection','import-preview-button','import-close','import-save','import-retry','import-reload','import-new'])$(id).disabled=busy;
  $('import-progress').textContent=message;$('import-progress').hidden=!message;
  if(importState)importSelectionControls();
  for(const control of $('import-preview').querySelectorAll('.import-select-control'))control.disabled=busy;
}
function renderImport(result){
  $('import-form').hidden=true;$('import-new').hidden=false;
  importState=result;sessionStorage.setItem('blog-studio-import-preview',result.preview);
  const box=$('import-preview');box.replaceChildren();box.hidden=false;
  box.append(element('h3',result.collection),element('p',result.candidates+' candidates listed · '+result.remaining+' not yet processed'));
  if(result.saved_collection===false)box.append(element('p','This collection is saved, and shared with your Team Hub, when you import its first posts. Closing now leaves nothing behind.','help'));
  if(result.coverage_note)box.append(element('p',result.coverage_note,'context-note'));
  if(result.scope)box.append(element('p','Permitted posts: '+result.scope,'help'));
  const counts=result.counts||{};
  if(result.completed)box.append(element('p',`${counts.imported||0} added · ${counts.updated||0} updated · ${counts.unchanged||0} unchanged · ${counts.failed||0} failed`));
  if(counts.pending_extraction)box.append(element('p',counts.pending_extraction+' files need text extraction in chat.','context-note'));
  if(result.sharing_message)box.append(element('p',result.sharing_message,'context-note'));
  if(result.network_bytes)box.append(element('p','Download size is unknown until posts are fetched. Each batch reads up to 25 posts.','help'));
  if(result.discovery_limited)box.append(element('p','Discovery reached its limit. Use a smaller folder or website path to cover the remaining posts.','context-note'));
  if(result.excluded.length)box.append(disclosure('Excluded items',...result.excluded.map(v=>element('p',v.reason))));
  box.append(element('p','Check only the posts you want. Author profiles, category pages and navigation links can appear here. Nothing is selected automatically.','context-note'));
  importChecks=new Map();
  const controls=element('div',undefined,'import-selection-tools'),count=element('span');count.id='import-selection-count';
  const choose=element('button','Select all','button button-quiet import-select-control'),clear=element('button','Clear selection','button button-quiet import-select-control');
  choose.type=clear.type='button';
  choose.addEventListener('click',()=>{for(const check of importChecks.values())if(!check.disabled)check.checked=true;importSelectionControls();});
  clear.addEventListener('click',()=>{for(const check of importChecks.values())check.checked=false;importSelectionControls();});
  controls.append(choose,clear,count);box.append(controls);
  const list=element('ul',undefined,'import-post-list');
  for(const post of result.posts){
    const row=element('li'),label=element('label'),check=element('input'),details=element('span');check.type='checkbox';
    check.checked=(result.selected||[]).includes(post.key)&&['pending','failed'].includes(post.status);
    check.setAttribute('aria-label','Import '+post.title);check.addEventListener('change',importSelectionControls);importChecks.set(post.key,check);
    details.append(element('strong',post.title));if(post.author)details.append(element('span',post.author,'help'));
    details.append(element('span',post.status==='pending'?'Not imported':post.status,'help'));
    label.append(check,details);row.append(label);if(post.url)row.append(link(post.url,post.url));list.append(row);
  }
  box.append(list);
  if(result.failures.length)box.append(disclosure('Why posts failed',...result.failures.map(reason=>element('p',reason))));
  $('import-save').hidden=!result.remaining;
  $('import-retry').hidden=!counts.failed;$('import-reload').hidden=false;importSelectionControls();
}
function resetImportPreview(){
  $('import-form').hidden=false;$('import-new').hidden=true;
  importState=null;importChecks=new Map();sessionStorage.removeItem('blog-studio-import-preview');
  for(const id of ['import-preview','import-save','import-retry','import-reload'])$(id).hidden=true;
}
async function openImport(){
  if(!access.actions.edit)return;
  $('import-dialog').showModal();importFields();
  try{
    const result=await api('collections'), select=$('import-collection');select.replaceChildren();
    importCollections=result.items;
    for(const collection of result.items){const option=element('option',collection.name);option.value=collection.key;select.append(option);}
    importFields();
    const saved=sessionStorage.getItem('blog-studio-import-preview');
    if(!importState){const preview=await api('library-preview'+(saved?'?preview='+encodeURIComponent(saved):''));if(preview.preview)renderImport(preview);}
  }catch(error){notice(error.message,true);}
}
async function encodeImportFile(file){
  const bytes=new Uint8Array(await file.arrayBuffer());let binary='';
  for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  return btoa(binary);
}
async function selectedFolderFiles(required){
  const files=Array.from($('import-folder').files||[]).filter(f=>/\.(md|txt|html?|docx|pdf)$/i.test(f.name)&&!(f.webkitRelativePath||f.name).split('/').some(p=>p.startsWith('.')));
  if(!files.length&&!required)return null;
  if(!files.length||files.length>500||files.reduce((sum,f)=>sum+f.size,0)>10*1024*1024)throw new Error('Choose a folder with 1–500 supported files totaling at most 10 MiB.');
  const encoded=[];
  for(const file of files)encoded.push({path:file.webkitRelativePath||file.name,content:await encodeImportFile(file)});
  return encoded;
}
async function selectedExport(required){
  const file=($('import-export').files||[])[0];
  if(!file&&!required)return null;
  if(!file||!file.size||file.size>10*1024*1024)throw new Error('Choose a nonempty JSON export of at most 10 MiB.');
  return encodeImportFile(file);
}
async function previewImport(){
  if(importBusy||!access.actions.edit)return;
  resetImportPreview();importBusyState(true,'Preparing your preview…');
  try{
    const type=$('import-type').value,payload=type==='collection'?{collection:$('import-collection').value}:{name:$('import-name').value.trim(),type};
    const again=refreshKind();
    if(type==='folder'||again==='folder'){
      // A new collection needs a folder; refreshing one may bring a new selection or re-check the earlier one.
      const files=await selectedFolderFiles(type==='folder');
      if(files)payload.files=files;
    }else if(type==='export'||again==='export'){
      const content=await selectedExport(type==='export');
      if(content)payload.export=content;
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
  const choice=analysisChoice('import');
  importBusyState(true,choice.analyze?'Importing selected posts, then summarizing and tagging them with your analysis CLI. Saved originals are kept if analysis needs a retry…':'Importing selected posts…');
  try{
    const selected=importSelectionControls();
    if(!selected.length)throw new Error('Check the posts you want to import first.');
    const payload={preview:importState.preview,expected:importState.expected,confirm:true,retry,selected,...choice};
    const result=await api('library-import',{...payload,operation:operationFor('library-import',payload)});
    renderImport(result);await load();notice(result.sharing_message||'Posts saved to the team library.');
  }catch(error){notice(error.message,true);}finally{importBusyState(false);}
}

// One file with the upload dialog's extra choices: summarize and tag it, or start a blog from it.
function openUpload(purpose='reference'){
  if(!access.actions.edit)return;
  $('upload-purpose').value=purpose;$('upload-dialog').showModal();
}
async function saveUpload(submit){
  const analyzing=analysisChoice('upload').analyze;
  try{
    await busy(submit,analyzing?'Uploading, then summarizing and tagging…':'Uploading…',async()=>{
      const file=$('upload-file').files[0];
      if(!file||file.size>10*1024*1024)throw new Error('Choose a file of at most 10 MiB.');
      const payload={filename:file.name,content:await encodeImportFile(file),title:$('upload-title').value,author:$('upload-author').value,purpose:$('upload-purpose').value||'reference',as_blog:$('upload-blog').checked,...analysisChoice('upload')};
      const result=await api('upload',{...payload,operation:operationFor('upload',payload)});
      $('upload-dialog').close();await load();savedNotice(result);
    });
  }catch(error){notice(error.message,true);}
}
async function saveMemory(submit){
  submit.disabled=true;
  try{
    const fields={kind:$('memory-kind').value,title:$('memory-name').value,body:$('memory-body').value,scope:$('memory-scope').value,scope_key:$('memory-key').value};
    let payload=fields;
    if(memoryEdit){
      // An edit sends only what changed; the rest stays exactly as saved.
      const changes=changedFields(fields,memoryEdit.loaded);
      if(!Object.keys(changes).length){notice('No changes to save.');return;}
      payload={item:memoryEdit.item,revision:memoryEdit.revision,...changes};
    }
    const saved=await api('memory',{...payload,operation:operationFor('memory',payload)});
    $('memory-dialog').close();await load();savedNotice(saved);
  }catch(error){notice(error.message,true);}
  finally{submit.disabled=false;}
}

for(const b of document.querySelectorAll('[data-view]'))b.addEventListener('click',()=>{view=b.dataset.view;offset=0;$('query').value='';document.querySelectorAll('[data-view]').forEach(e=>e.removeAttribute('aria-current'));b.setAttribute('aria-current','page');load().catch(e=>notice(e.message,true));});
for(const b of document.querySelectorAll('[data-close]'))b.addEventListener('click',()=>b.closest('dialog').close());
$('search-go').addEventListener('click',()=>{offset=0;load().catch(e=>notice(e.message,true));});
for(const id of ['library-role','library-kind','library-status'])$(id).addEventListener('change',()=>{$('search-go').click();});$('library-author').addEventListener('keydown',e=>{if(e.key==='Enter')$('search-go').click();});
$('library-clear-selection').addEventListener('click',()=>{librarySelection.clear();for(const pick of document.querySelectorAll('.library-pick'))pick.checked=false;librarySelectionBar();});
$('library-select-page-box').addEventListener('change',()=>tickLibrary(libraryShown,$('library-select-page-box').checked));
$('filters-toggle').addEventListener('click',()=>{const open=!$('filters-toggle').closest('.filter-bar').classList.contains('filters-open');$('filters-toggle').closest('.filter-bar').classList.toggle('filters-open',open);$('filters-toggle').setAttribute('aria-expanded',String(open));});
$('library-select-shown').addEventListener('click',()=>tickLibrary(libraryShown,true));
$('library-select-matching').addEventListener('click',()=>selectAllMatching($('library-select-matching')).catch(e=>notice(e.message,true)));
for(const [id,action] of [['library-learn-style','style-learn'],['library-learn-voice','voice-learn'],['library-start-blog','blog']])$(id).addEventListener('click',()=>sLibrarySelection(action,[...librarySelection.values()]).catch(e=>notice(e.message,true)));$('query').addEventListener('keydown',e=>{if(e.key==='Enter')$('search-go').click();});$('stage').addEventListener('change',()=>{$('search-go').click();});
$('previous').addEventListener('click',()=>{if($('previous').disabled)return;offset=Math.max(0,offset-limit);load().catch(e=>notice(e.message,true));});$('next').addEventListener('click',()=>{if($('next').disabled)return;offset+=limit;load().catch(e=>notice(e.message,true));});
$('refresh-hub').addEventListener('click',async()=>{
  try{await busy($('refresh-hub'),'Refreshing…',async()=>{await api('refresh',{});await loadCapabilities();await load();});notice('Team Hub refreshed. Google Docs content is refreshed separately in chat.');}
  catch(e){notice(e.message,true);}
  finally{applyCapabilities();}
});
$('check-access').addEventListener('click',async()=>{try{await loadCapabilities();await load();}catch(e){notice(e.message,true);}});
$('import-collection').addEventListener('change',importFields);
$('import-new').addEventListener('click',()=>{if(!importBusy)resetImportPreview();});
$('import-type').addEventListener('change',()=>{resetImportPreview();importFields();});
$('import-form').addEventListener('input',()=>{if(!importBusy)resetImportPreview();});
$('import-form').addEventListener('submit',e=>{e.preventDefault();previewImport();});
$('import-save').addEventListener('click',()=>saveImport(false));
$('import-retry').addEventListener('click',()=>saveImport(true));
$('import-dialog').addEventListener('cancel',e=>{if(importBusy)e.preventDefault();});
$('import-reload').addEventListener('click',async()=>{if(importBusy||!importState)return;importBusyState(true,'Reloading your saved preview…');try{renderImport(await api('library-preview?preview='+encodeURIComponent(importState.preview)));}catch(error){notice(error.message,true);}finally{importBusyState(false);}});

$('upload-form').addEventListener('submit',e=>{e.preventDefault();saveUpload(e.target.querySelector('[type=submit]'));});
$('memory-form').addEventListener('submit',e=>{e.preventDefault();saveMemory(e.target.querySelector('[type=submit]'));});
applyCapabilities();loadCapabilities().then(()=>load()).catch(e=>notice(e.message,true));
