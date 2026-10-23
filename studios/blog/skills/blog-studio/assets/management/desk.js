// The writing desk: one page per blog with a card for each part, notes that rewrite a
// section, selection edits and quiet version history. Built with runner.js's helpers; every
// text from the draft is set with textContent.
'use strict';
const DESK_FIRST_PASSES=[['tighten','Tighten and proofread'],['reshape','Reshape to fit this kind of post'],['leave','Leave it as it is']];
const DESK_SELECTION=[['rephrase','Rephrase'],['shorten','Shorten'],['expand','Expand'],['fix','Fix']];
const DESK_SOURCES={save:'Before your edit',rewrite:'Before a rewrite','revise-all':'Before a whole-draft revision',selection:'Before a selection edit','first-pass':'Before the first pass',finishing:'Before a finishing change',restore:'Before a restore'};
const DESK_DOING={'desk-section':'Rewriting','desk-revise-all':'Revising the whole draft','desk-selection':'Editing a passage','desk-first-pass':'Working on the first pass'};
const DESK_SAVE_WAIT=1000,DESK_POLL=3000,DESK_DIFF_LIMIT=4000;

// Words, with the spaces between them kept, compared by a longest common subsequence.
function deskWords(text){return String(text||'').match(/\s+|[^\s]+/g)||[];}
function diffWords(before,after){
  const a=deskWords(before),b=deskWords(after);
  if(a.length>DESK_DIFF_LIMIT||b.length>DESK_DIFF_LIMIT)return null;
  const rows=a.length+1,cols=b.length+1,table=new Uint32Array(rows*cols);
  for(let i=a.length-1;i>=0;i--)for(let j=b.length-1;j>=0;j--)table[i*cols+j]=a[i]===b[j]?table[(i+1)*cols+j+1]+1:Math.max(table[(i+1)*cols+j],table[i*cols+j+1]);
  const out=[],push=(op,text)=>{const last=out[out.length-1];if(last&&last.op===op)last.text+=text;else out.push({op,text});};
  let i=0,j=0;
  while(i<a.length&&j<b.length){if(a[i]===b[j]){push('same',a[i]);i++;j++;}else if(table[(i+1)*cols+j]>=table[i*cols+j+1]){push('removed',a[i]);i++;}else{push('added',b[j]);j++;}}
  while(i<a.length)push('removed',a[i++]);while(j<b.length)push('added',b[j++]);
  return out;
}
function deskCompare(before,after){
  const found=diffWords(before,after),box=sNode('div','paper desk-compare');
  if(!found){box.append(sAdd(sNode('div','desk-side'),sNode('h3','sheet-part','Before'),sNode('p','desk-plain',before)),sAdd(sNode('div','desk-side'),sNode('h3','sheet-part','Now'),sNode('p','desk-plain',after)));return box;}
  const text=sNode('p','desk-plain');text.setAttribute('aria-label','Changes from this version to the current text');
  for(const piece of found){const node=sNode(piece.op==='same'?'span':piece.op==='added'?'ins':'del',piece.op==='same'?'':piece.op==='added'?'diff-add':'diff-remove',piece.text);text.append(node);}
  return sAdd(box,text);
}
function deskAge(at){const then=Date.parse(at||'');if(!then)return '';const minutes=Math.round((Date.now()-then)/60000);if(minutes<1)return 'just now';if(minutes<60)return minutes+(minutes===1?' minute ago':' minutes ago');const hours=Math.round(minutes/60);if(hours<24)return hours+(hours===1?' hour ago':' hours ago');const days=Math.round(hours/24);return days+(days===1?' day ago':' days ago');}
function deskPartName(view,part){if(part==='title')return 'the title';if(part==='opening')return 'the opening';if(part==='sections')return 'every section';const found=(view.sections||[]).find(section=>section.id===part);return found?'“'+found.heading+'”':'a section';}
function deskTextOf(view,part){if(part==='title'||part==='opening')return view[part]||'';return (view.sections||[]).find(section=>section.id===part)?.text||'';}

// The start for a draft the person brings: paste, upload or a Google Doc, its kind of post,
// tone and an optional first pass.
async function sDeskStart(){
  if(!studio.options)studio.options=await api('run-options');
  const defaults=studio.options.settings?.defaults||{};
  const held=studio.deskStart||(studio.deskStart={source:'paste',title:'',manuscript:'',url:'',file:null,style:'',tone:defaults.tone||'',first_pass:'leave',operation:operationId(),upload:operationId(),preview:null});
  const form=sNode('form','narrow desk-start'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  sFrame('Edit a draft',[],'Bring your draft to the desk',()=>sRoute('home'));
  const where=sChoice('Where is your draft?',[['paste','Paste text'],['file','Upload a file'],['google','Google Doc']],held,'source',()=>{held.preview=null;sDeskStart();});
  const draftPart=sCard('1. Your draft',where);
  let file=null;
  if(held.source==='paste')draftPart.append(sField('desk-manuscript','Paste your draft',held,'manuscript',{long:true,max:1000000,required:true,hint:'Markdown or plain text. Each ## heading starts a section; text before the first one is the opening.'}));
  else if(held.source==='file'){
    file=sNode('input','input');file.type='file';file.accept='.txt,.md,.docx,.pdf,.html,.htm';file.setAttribute('aria-label','Upload a draft');
    const note=sNode('p','quiet field-hint',held.file?'Selected: '+held.file.name:'Text, Markdown, Word or PDF. Up to 10 MiB.');
    file.addEventListener('change',()=>{held.file=file.files?.[0]||null;note.textContent=held.file?'Selected: '+held.file.name:'Choose a draft.';});
    draftPart.append(file,note);
  }else{
    draftPart.append(sField('desk-google','Google Doc link or document ID',held,'url',{required:true,max:2000,hint:'Every tab is read. The Doc is not changed or shared.'}));
    if(held.preview){const paper=sNode('article','paper doc');paper.setAttribute('aria-label','Google Doc preview');paper.append(window.TrainingStudioMarkdown?window.TrainingStudioMarkdown.render(held.preview.content):sNode('p','',held.preview.content));draftPart.append(sNode('p','','Check the text below, then start.'),paper);}
  }
  draftPart.append(sField('desk-title','Title (optional)',held,'title',{max:500,hint:'Leave blank to use the draft’s # heading or the Doc’s name.'}));
  const shape=sCard('2. Kind of post and tone',sStyleSelect(held),sField('desk-tone','Tone',held,'tone',{max:2000,hint:'How it should sound, such as clear and conversational.'}));
  const pass=sCard('3. A first pass',sChoice('Before you edit',DESK_FIRST_PASSES,held,'first_pass'),sNode('p','quiet','Optional. It runs once on the desk and keeps your text as a version first.'));
  const go=sNode('button','button button-filled',held.source==='google'&&!held.preview?'Read Google Doc':'Start');go.type='submit';go.disabled=!access.actions.edit;
  sAdd(form,draftPart,shape,pass,sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),go)));
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(!access.actions.edit)return;const turn=studio.turn;
    if(held.source==='paste'&&!held.manuscript.trim()){problem.textContent='Paste your draft first.';return;}
    if(held.source==='file'&&!held.file){problem.textContent='Choose a draft to upload.';return;}
    if(held.first_pass==='reshape'&&!held.style){problem.textContent='Choose a kind of post to reshape the draft to.';return;}
    await busy(go,'Starting…',async()=>{try{
      const settings={operation:held.operation,style:held.style,tone:held.tone,first_pass:held.first_pass,...(held.title.trim()?{title:held.title.trim()}:{})};
      let made;
      if(held.source==='paste')made=await api('desk-create',{...settings,manuscript:held.manuscript});
      else if(held.source==='file'){
        if(held.file.size>10*1024*1024)throw new Error('Choose a file up to 10 MiB.');
        const uploaded=await api('upload',{operation:held.upload,filename:held.file.name,title:held.title.trim()||held.file.name.replace(/\.[^.]+$/,''),content:await encodeImportFile(held.file),purpose:'manuscript',analyze:false});
        if(uploaded.state&&uploaded.state!=='ready')throw new Error('This file needs its text extracted before it can be edited. Paste the text instead.');
        made=await api('desk-create',{...settings,source:uploaded.source.id});
      }else if(!held.preview){
        const found=await api('google-preview',{url:held.url.trim()});if(turn!==studio.turn)return;
        if(found?.status==='already-linked'&&found.id){made=await api('desk-create',{...settings,article:found.id});}
        else{held.preview=sGooglePreview(found);if(!held.title.trim())held.title=found.title;sDeskStart();return;}
      }else{
        const started=await api('google-start',{preview:held.preview.preview,expected:held.preview.expected,title:held.title.trim()||held.preview.title,confirmed:true});
        made=await api('desk-create',{...settings,title:undefined,article:started.id});
      }
      if(turn!==studio.turn)return;studio.deskStart=null;
      if(made.first_pass_problem)sToast('The first pass did not start: '+made.first_pass_problem);
      studio.desk={id:made.id,view:made,session:operationId()};await sRoute('desk',made.id);
    }catch(error){if(turn===studio.turn)problem.textContent=error.message+' Your choices are kept here.';}});
  });
  sPage(sNode('p','lede','Your draft opens as one page of sections. Give a note to any section, or select text to change it.'),form);
}

// The desk.
async function sDesk(ident){
  const turn=studio.turn;
  const view=await api('desk?id='+encodeURIComponent(ident));if(turn!==studio.turn)return;
  const held=studio.desk&&studio.desk.id===ident?studio.desk:(studio.desk={id:ident,session:operationId()});
  held.view=view;held.pending=held.pending||{};held.stale=false;
  sDeskRender(held);
  sDeskWatch(held);
}
function sDeskCurrent(held){return studio.screen==='desk'&&studio.desk===held;}
// Whether the job under way changes this part: its own section, or every section.
function sDeskWorking(held,part){const job=held.view.working;if(!job)return false;return job.part===part||job.part==='sections'&&part!=='title'&&part!=='opening';}
function sDeskStatusWords(held){const job=held.view.working;if(!job)return '';return (DESK_DOING[job.kind]||'Working')+(job.kind==='desk-section'||job.kind==='desk-selection'?' '+deskPartName(held.view,job.part):'')+'…';}
function sDeskRender(held){
  const view=held.view,editable=access.actions.edit;
  const copy=sButton('Copy',async()=>{if(typeof navigator==='undefined'||!navigator.clipboard?.writeText)throw new Error('Download the draft and copy it from there.');await navigator.clipboard.writeText(held.view.markdown);sToast('Markdown copied.');});
  const download=sButton('Download',()=>sDownload({content:held.view.markdown,name:'DRAFT.md'}));
  const google=view.google?.url?link(view.google.url,'Google Doc ↗'):null;if(google)google.className='button';
  const publish=sButton(view.publication?'Published':'Mark as published',()=>sDeskPublish(held));publish.disabled=!editable;
  const finishing=sButton('Finishing',()=>{});finishing.disabled=true;finishing.title='Finishing tools arrive in a later update.';
  const stop=held.view.working?sButton('Stop',async button=>{await busy(button,'Stopping…',async()=>{held.view=await api('desk-stop',{id:held.id,job:held.view.working.id});sDeskRender(held);});}):null;
  sFrame(view.title,sFold([stop,copy,download,google,publish,finishing]),held.view.working?sDeskStatusWords(held):'On the desk',()=>sRoute('blogs'));
  const status=sNode('p','quiet desk-save-state');status.setAttribute('role','status');status.setAttribute('aria-live','polite');held.status=status;
  if(held.stale)sDeskStale(held);else status.textContent=held.saved||'Changes save as you type.';
  const column=sNode('div','desk-column');
  const problem=sDeskProblem(held);if(problem)column.append(problem);
  column.append(sDeskWhole(held),sDeskPart(held,'title'),sDeskPart(held,'opening'));
  for(const section of view.sections)column.append(sDeskPart(held,section.id));
  if(!view.sections.length)column.append(sCard('No sections yet',sNode('p','','This draft has no ## headings, so it is one opening. Add headings in the text to work section by section.')));
  held.bar=sDeskSelectionBar(held);
  sPage(sNode('p','lede','Edit any part in place, give a section a note to rewrite it, or select text for a quick change. Every change keeps the earlier text in History.'),status,sAdd(sNode('div','desk-layout'),column,sDeskAside(held)),held.bar);
}
// What the last job left: a result not applied, or a job that failed.
function sDeskProblem(held){
  const last=(held.view.jobs||[]).at(-1);if(!last||held.dismissed===last.id)return null;
  const failed=last.status==='failed'||last.status==='ready'&&last.applied===false;if(!failed||!last.error)return null;
  return sAdd(sNode('div','decision-notice desk-problem'),sNode('p','',(last.status==='failed'?'The last change could not finish: ':'The last change was not applied: ')+last.error),sButton('Dismiss',()=>{held.dismissed=last.id;sDeskRender(held);}));
}
function sDeskWhole(held){
  const card=sCard('Note for the whole draft');
  const box=sNode('textarea','input');box.id='desk-whole-note';box.rows=2;box.maxLength=4000;box.setAttribute('aria-label','Note for the whole draft');box.value=held.wholeNote||'';box.placeholder='For example: tighten throughout, or make it more casual.';
  box.addEventListener('input',()=>{held.wholeNote=box.value;});
  const go=sButton('Revise the draft',async button=>{const text=(held.wholeNote||'').trim();if(!text){notice('Write the note for the whole draft.',true);return;}await sDeskJob(held,button,'desk-revise',{note:text},()=>{held.wholeNote='';});},'filled');
  go.disabled=!access.actions.edit||!!held.view.working;
  return sAdd(card,box,sNode('p','quiet field-hint','Each section is revised for the note with the whole draft in view. Your text is kept as a version first.'),sAdd(sNode('div','bar'),go));
}
function sDeskPart(held,part){
  const view=held.view,section=(view.sections||[]).find(row=>row.id===part),working=sDeskWorking(held,part);
  const card=sNode('section','card desk-part'+(working?' desk-working':''));card.dataset.part=part;
  const heading=sNode('h2','card-title',part==='title'?'Title':part==='opening'?'Opening':section.heading);
  const count=(view.versions||{})[part]||0,history=sButton(count?'History ('+count+')':'History',()=>sDeskHistory(held,part));history.disabled=!count;
  card.append(sAdd(sNode('div','desk-part-head'),heading,history));
  const text=held.pending[part]?.text??deskTextOf(view,part);
  const input=sNode(part==='title'?'input':'textarea','input desk-text');input.value=text;input.setAttribute('aria-label',part==='title'?'Title':part==='opening'?'Opening':'Text of '+section.heading);
  if(part==='title'){input.type='text';input.maxLength=500;}else{input.rows=Math.min(24,Math.max(3,Math.ceil(text.length/90)+text.split('\n').length));}
  input.readOnly=working||!access.actions.edit;
  input.addEventListener('input',()=>sDeskTyped(held,part,input.value));
  if(part!=='title'){for(const kind of ['select','mouseup','keyup'])input.addEventListener(kind,()=>sDeskSelected(held,part,input));}
  else input.addEventListener('select',()=>sDeskSelected(held,part,input));
  card.append(input);
  if(working){const note=sNode('p','desk-working-note','Working on this section');note.setAttribute('role','status');card.append(note);if(view.working.note)card.append(sNode('p','quiet','Your note: '+view.working.note));}
  if(section){
    const typed=(held.notes||{})[part]||'',row=sNode('div','desk-note');
    const box=sNode('input','input');box.type='text';box.maxLength=4000;box.value=typed;box.placeholder='How should this change?';box.setAttribute('aria-label','How should '+section.heading+' change?');
    const go=sButton(typed.trim()?'Rewrite':'Write again',async button=>{const note=((held.notes||{})[part]||'').trim();await sDeskJob(held,button,'desk-note',{part,note},()=>{if(held.notes)delete held.notes[part];});});
    go.disabled=!access.actions.edit||!!view.working;
    box.addEventListener('input',()=>{held.notes=held.notes||{};held.notes[part]=box.value;go.textContent=box.value.trim()?'Rewrite':'Write again';});
    card.append(sAdd(row,box,go));
  }
  return card;
}
function sDeskAside(held){
  const view=held.view,aside=sNode('aside','desk-aside');aside.setAttribute('aria-label','Sources and gaps');
  const sources=sCard('Sources');
  if((view.source_names||[]).length){const list=sNode('ul','rows');for(const source of view.source_names)list.append(sAdd(sNode('li','row'),sNode('span','row-title',source.name)));sources.append(list);}
  else sources.append(sNode('p','quiet','No sources were given for this draft. Rewrites keep to what the draft already says.'));
  if(view.style_name)sources.append(sNode('p','quiet','Kind of post: '+view.style_name));
  if(view.tone)sources.append(sNode('p','quiet','Tone: '+view.tone));
  aside.append(sources);
  const gaps=view.gaps||[];
  const list=sNode('ul','gap-items');for(const gap of gaps)list.append(sNode('li','',gap));
  aside.append(sAdd(sNode('section','paper aside-part'),sNode('h2','aside-title','Needs you before publishing'),gaps.length?list:sNode('p','quiet','Nothing yet. What a rewrite cannot support from your sources is listed here, never in the text.')));
  if(view.run)aside.append(sAdd(sNode('p','quiet'),sButton('Open the step-by-step run',()=>sRoute('run',view.id))));
  return aside;
}

// Saving as you type: one second after the last keystroke, against the revision last seen.
function sDeskTyped(held,part,text){
  held.pending[part]={text,timer:held.pending[part]?.timer};
  if(held.pending[part].timer&&typeof clearTimeout==='function')clearTimeout(held.pending[part].timer);
  held.pending[part].timer=setTimeout(()=>sDeskSave(held,part),DESK_SAVE_WAIT);
  if(held.status)held.status.textContent='Saving…';
}
async function sDeskSave(held,part){
  if(!held.pending[part]||held.stale)return;
  while(held.saving)await held.saving;  // One save at a time, each against the latest revision.
  const pending=held.pending[part];if(!pending||held.stale)return;
  const text=pending.text;
  held.saving=(async()=>{try{
    const view=await api('desk-save',{id:held.id,seen:held.view.revision,part,text,session:held.session});
    if(held.pending[part]?.text===text)delete held.pending[part];
    const wasWorking=!!held.view.working;held.view=view;held.saved='Saved.';
    if(held.status&&!held.stale)held.status.textContent='Saved.';
    sDeskCounts(held);
    if(wasWorking&&!view.working&&sDeskCurrent(held))sDeskRender(held);
  }catch(error){
    if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}
    else if(held.status)held.status.textContent=error.message+' Your text is kept here.';
  }finally{held.saving=null;}})();
  await held.saving;
  if(held.pending[part]&&held.pending[part].text!==text&&!held.stale)return sDeskSave(held,part);
}
async function sDeskFlush(held){for(const part of Object.keys(held.pending)){if(held.pending[part]?.timer&&typeof clearTimeout==='function')clearTimeout(held.pending[part].timer);await sDeskSave(held,part);}}
function sDeskCounts(held){for(const card of $('studio-page').querySelectorAll('.desk-part')){const count=(held.view.versions||{})[card.dataset.part]||0,button=card.querySelectorAll('button')[0];if(button&&/^History/.test(button.textContent)){button.textContent=count?'History ('+count+')':'History';button.disabled=!count;}}}
function sDeskStale(held){
  if(!held.status)return;held.status.className='desk-save-state decision-notice desk-stale';held.status.replaceChildren(sNode('span','','This draft changed in another window or job. Reload to see the latest; your unsaved text is shown until you do. '),sButton('Reload',async()=>{held.pending={};held.stale=false;held.saved='';await sDesk(held.id);},'filled'));
}

// Notes and selection edits start a job; the desk follows it until it ends.
async function sDeskJob(held,button,route,data,done){
  await busy(button,'Starting…',async()=>{try{
    await sDeskFlush(held);if(held.stale)return;
    held.view=await api(route,{id:held.id,seen:held.view.revision,...data});if(done)done();
    sDeskRender(held);sDeskWatch(held);
  }catch(error){if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else notice(error.message,true);}});
}
function sDeskWatch(held){
  if(!held.view.working||held.watching)return;held.watching=true;
  const follow=async()=>{
    if(!sDeskCurrent(held)){held.watching=false;return;}
    try{await sDeskFlush(held);const view=await api('desk?id='+encodeURIComponent(held.id));if(!sDeskCurrent(held)){held.watching=false;return;}
      const ended=!view.working;held.view=view;
      if(ended){held.watching=false;sDeskRender(held);const last=(view.jobs||[]).at(-1);if(last?.applied)sToast('Done. The earlier text is in History.');return;}
    }catch(error){if(held.status)held.status.textContent=error.message;}
    setTimeout(follow,DESK_POLL);
  };
  setTimeout(follow,DESK_POLL);
}

// A small bar for the selected passage: Rephrase, Shorten, Expand, Fix and Ask….
function sDeskSelected(held,part,input){
  // The selection without the spaces around it, and where it starts in the saved text (the
  // server keeps a part without its leading spaces), so a repeated word is the one chosen.
  const value=input.value;let start=input.selectionStart,end=input.selectionEnd;
  if(typeof start!=='number'||typeof end!=='number')start=end=0;
  while(start<end&&/\s/.test(value[start]))start++;while(end>start&&/\s/.test(value[end-1]))end--;
  const text=value.slice(start,end),lead=value.length-value.replace(/^\s+/,'').length;
  if(!text||held.view.working||!access.actions.edit){if(held.bar&&!held.asking)held.bar.hidden=true;return;}
  held.selection={part,text,start:start-lead};held.asking=false;sDeskBarContent(held);held.bar.hidden=false;
}
function sDeskSelectionBar(held){const bar=sNode('div','desk-selection glass');bar.setAttribute('role','toolbar');bar.setAttribute('aria-label','Change the selected text');bar.hidden=true;held.bar=bar;sDeskBarContent(held);return bar;}
function sDeskBarContent(held){
  const bar=held.bar;if(!bar)return;
  const run=(action,instruction='')=>async button=>{const chosen=held.selection;if(!chosen)return;await sDeskJob(held,button,'desk-selection',{part:chosen.part,text:chosen.text,start:chosen.start,action,...(action==='ask'?{instruction}:{})},()=>{held.selection=null;held.asking=false;});};
  if(held.asking){
    const box=sNode('input','input');box.type='text';box.maxLength=2000;box.placeholder='What should change?';box.setAttribute('aria-label','What should change in the selected text?');
    bar.replaceChildren(box,sButton('Go',async button=>{const instruction=box.value.trim();if(!instruction){notice('Say what to do with the passage.',true);return;}await run('ask',instruction)(button);},'filled'),sButton('Cancel',()=>{held.asking=false;bar.hidden=true;}));
    return;
  }
  bar.replaceChildren(...DESK_SELECTION.map(([action,label])=>sButton(label,run(action))),sButton('Ask…',()=>{held.asking=true;sDeskBarContent(held);}));
}

// History: each kept version with its words compared to the current text, and Restore.
async function sDeskHistory(held,part){
  await sDeskFlush(held);
  const found=await api('desk-versions?'+new URLSearchParams({id:held.id,part}));
  const current=deskTextOf(held.view,part),list=sNode('div','desk-versions'),compare=sNode('div','desk-compare-area');
  found.versions.forEach((version,index)=>{
    const row=sAdd(sNode('div','desk-version'),sAdd(sNode('div','row-text'),sNode('h3','row-title',DESK_SOURCES[version.source]||'Earlier text'),sNode('p','quiet',[deskAge(version.at),version.words+(version.words===1?' word':' words')].filter(Boolean).join(' · '))));
    const restore=sButton('Restore',async button=>{await busy(button,'Restoring…',async()=>{try{held.view=await api('desk-restore',{id:held.id,seen:held.view.revision,part,index});delete held.pending[part];sCloseSheet();sToast('Restored. The text it replaced is in History.');sDeskRender(held);}catch(error){if(/changed since/.test(error.message)){sCloseSheet();held.stale=true;sDeskStale(held);}else notice(error.message,true);}});});
    restore.disabled=!access.actions.edit||!!held.view.working;
    row.append(sAdd(sNode('div','bar'),sButton('Compare',()=>{compare.replaceChildren(sNode('h3','sheet-part','This version compared with now'),sNode('p','quiet','Struck words are in this version only; marked words were added since.'),deskCompare(version.text,current));}),restore));
    list.append(row);
  });
  sOpenSheet('History of '+deskPartName(held.view,part),found.versions.length?list:sNode('p','','Nothing kept yet.'),compare);
}

// Mark as published: where it went, said by the person. Nothing is posted.
function sDeskPublish(held){
  const draft={url:held.view.publication||''},problem=sNode('p','sheet-error');problem.setAttribute('role','alert');
  const save=sButton('Mark as published',async button=>{const url=draft.url.trim();if(!/^https:\/\/\S+$/.test(url)){problem.textContent='Add the public https address where it was published.';return;}await busy(button,'Saving…',async()=>{try{await sDeskFlush(held);await api('schedule',{id:held.id,expected:held.view.expected,stage:'published',confirm_stage:true,publication_url:url});sCloseSheet();sToast('Recorded as published. Nothing was posted anywhere.');await sDesk(held.id);}catch(error){problem.textContent=error.message;}});},'filled');
  sOpenSheet('Mark as published',sNode('p','','Record where this blog was published. The current text is the published one.'),sField('desk-publication','Public address',draft,'url',{max:2000,required:true}),problem,sAdd(sNode('div','bar'),save,sButton('Cancel',sCloseSheet)));
}

// A finished step-by-step blog once it is on the desk: its run is read as it ended, with
// nothing to resume, approve or ask for; the desk is where it is edited now.
function sRunOnDesk(found){
  studio.found=found;studio.signature=JSON.stringify(found);
  const open=sButton('Open on the desk',()=>sRoute('desk',found.id),'filled');
  sFrame(found.title,[open],'Writing run',()=>sRoute('blogs'));
  const steps=sNode('ol','rows');for(const row of found.stages||[])steps.append(sAdd(sNode('li','row step'),sBead('done'),sAdd(sNode('div','row-text'),sNode('h3','step-name',row.label))));
  sPage(sCard('This blog is on the writing desk',sNode('p','','It was finished here and then opened on the desk, where its notes, selection edits and versions are. This run is kept as it ended, to read.'),sAdd(sNode('div','bar'),sButton('Open on the desk',()=>sRoute('desk',found.id),'filled'))),disclosure('How it was written',steps));
}
