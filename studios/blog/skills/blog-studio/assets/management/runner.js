'use strict';
let runSelection = null, runLoading = false, runOptions = null, runRevision = null;
const RUN_LABELS={'waiting-for-approval':'Waiting for your review','in-chat':'Continue in chat','needs-attention':'Needs attention',queued:'Waiting to start',working:'Working',failed:'Needs a retry',paused:'Paused',stopped:'Stopped',complete:'Finished'};
const STAGE_STATUSES={draft:'Ready for your review',approved:'Approved',pending:'Not started',stale:'Needs review after changes'};
function renderRuns(result) {
  $('heading').textContent='Writing runs';$('subtitle').textContent=views.runs[1];
  $('section-title').textContent='Your writing runs';$('count').textContent=result.total+' runs';
  $('import-open').hidden=true;$('memory-open').hidden=true;$('stage-filter').hidden=true;
  $('previous').disabled=true;$('next').disabled=true;$('page-label').textContent='All writing runs';
  $('observation').textContent='Run here or continue in chat. Approval is always yours.';
  $('results').replaceChildren();
  const query=$('query').value.toLowerCase();
  for(const item of result.items.filter(item=>!query||(item.title+' '+item.status).toLowerCase().includes(query))) {
    const row=element('section',undefined,'run-card');
    row.append(button(item.title,()=>openRun(item.id),'title-button'),element('p',RUN_LABELS[item.status]||item.status));
    if(item.error)row.append(element('p',item.error,'context-note'));
    $('results').append(row);
  }
  if(!result.items.length)$('results').append(element('h3','Start your next blog'),element('p','Choose New blog. Your assistant runs each stage and waits for your approval.'));
}
async function newBlog(ident='') {
  runOptions=await api('run-options');
  $('new-blog-form').reset();$('new-blog-id').value=ident;
  $('new-blog-heading').textContent=ident?'Run this blog':'New blog';
  $('new-blog-title').required=!ident;
  $('new-blog-title').closest('label').hidden=!!ident;
  $('new-blog-author').closest('label').hidden=!!ident;
  $('new-blog-tone').closest('label').hidden=!!ident;
  $('new-blog-voice').replaceChildren();
  const defaultVoice=element('option','Keep existing voice or use tone');defaultVoice.value='';$('new-blog-voice').append(defaultVoice);
  for(const profile of runOptions.profiles){const option=element('option',profile.name+' · '+profile.status);option.value=profile.id;$('new-blog-voice').append(option);}
  $('new-blog-sources').replaceChildren();
  for(const source of runOptions.sources){const option=element('option',source.name+' · '+source.status);option.value=source.id;$('new-blog-sources').append(option);}
  for(const option of $('new-blog-stop').options)option.disabled=!!ident&&['outline','draft'].includes(option.value);
  $('new-blog-readiness').textContent=Object.entries(runOptions.agents).map(([name,ready])=>name+': '+(ready?'CLI found; sign-in checked when it runs':'CLI not found')).join(' · ');
  $('new-blog-dialog').showModal();
}
async function openBlogRun(ident) {
  try{await api('run?id='+encodeURIComponent(ident));$('detail-dialog').close();await openRun(ident);}
  catch(error){if(error.status===400&&/no guided run/.test(error.message)){$('detail-dialog').close();await newBlog(ident);return;}throw error;}
}
async function runAction(action, found, extra={}) {
  try{
    runLoading=true;
    const updated=await api('run-'+action,{id:found.id,expected:found.expected,...extra});
    renderRun(updated);if(view==='runs')await load();
  }catch(error){notice(error.message,true);}
  finally{runLoading=false;}
}
function renderRun(found) {
  runRevision=JSON.stringify([found.expected,found.status,found.error,found.enabled]);
  $('run-title').textContent=found.title;
  const content=$('run-content');content.replaceChildren();
  content.append(element('p',(RUN_LABELS[found.status]||found.status)+(found.next?' · '+STAGE_LABEL(found,found.next):''),'context-note'));
  if(found.error)content.append(element('p',found.error,'error'));
  const stages=element('ol',undefined,'run-stages');
  for(const row of found.stages) {
    const item=element('li',row.label+' · '+(STAGE_STATUSES[row.status]||row.status));
    if(row.notes)item.append(disclosure('Assistant’s notes and limitations',element('p',row.notes)));
    stages.append(item);
  }
  content.append(stages);
  const actions=element('div',undefined,'run-actions');
  const add=(label,action,extra={})=>{const b=button(label,()=>busy(b,'Working…',()=>runAction(action,found,extra)),action==='approve'?'primary':'secondary');b.disabled=!access.actions.edit;actions.append(b);};
  if(found.approval==='conversation') {
    content.append(element('p','Decisions for this blog are made in your conversation. Run this from here moves them to this page.'));
    if(!found.complete)add('Run this from here','start');
  } else {
    if(found.status==='waiting-for-approval')add('Approve '+STAGE_LABEL(found,found.next),'approve');
    if(found.content&&found.stages.some(row=>row.stage===found.next&&row.status==='stale'))add('Review this saved version','adopt');
    if(!found.complete&&(!found.enabled||found.status==='failed'))add(found.status==='failed'?'Retry step':'Resume','resume');
    if(found.enabled&&!found.complete){add(found.status==='working'?'Pause after this step':'Pause run','pause');if(found.status==='working')add('Stop now','stop');}
    add('Continue in chat','handoff');
  }
  const refresh=button('Reload run',()=>openRun(found.id));actions.append(refresh);content.append(actions);
  if(found.content){content.append(element('h3',STAGE_LABEL(found,found.next)),element('pre',found.content,'manuscript-preview'));}
  content.append(element('p','Files: '+found.directory,'help'));
  for(const row of found.stages.filter(row=>['draft','approved','stale'].includes(row.status))) {
    const download=button('Download '+row.label,async()=>{
      try{
        const file=await api('run-file?'+new URLSearchParams({id:found.id,stage:row.stage}));
        const blob=new Blob([file.content],{type:'text/markdown;charset=utf-8'}),url=URL.createObjectURL(blob);
        const a=element('a');a.href=url;a.download=file.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      }catch(error){notice(error.message,true);}
    });content.append(download);
  }
  if(found.approval==='page'&&access.actions.edit) {
    const form=element('form'),label=element('label','Which stage should change?'),select=element('select');
    if(found.existing&&!found.stages.some(row=>row.stage==='draft')){const option=element('option','Revise the draft');option.value='draft';select.append(option);}
    for(const row of found.stages){const option=element('option',row.label);option.value=row.stage;select.append(option);if(row.stage===found.next)break;}
    select.value=found.next||'draft';label.append(select);form.append(label);
    const requestLabel=element('label','What should change?'),request=element('textarea');request.required=true;request.maxLength=8000;request.rows=3;
    requestLabel.append(request);const submit=element('button','Ask for changes','primary');submit.type='submit';form.append(requestLabel,submit);
    form.addEventListener('submit',event=>{event.preventDefault();busy(submit,'Saving changes…',()=>runAction('changes',found,{stage:select.value,request:request.value}));});
    content.append(disclosure('Ask for changes',form));
  }
  content.append(element('p',found.observation||'Saved writing and decisions stay with this blog.','help'),
    continuation('Use Blog Studio. Continue guided blog '+found.id+' in workspace '+found.directory.replace(/\/articles\/[^/]+$/,'')+'. Show run status first.','Continue this blog in chat'));
}
function STAGE_LABEL(found,stage){return found.stages.find(row=>row.stage===stage)?.label||stage||'Finished';}
async function openRun(ident) {
  try{const found=await api('run?id='+encodeURIComponent(ident));runSelection=ident;renderRun(found);if(!$('run-dialog').open)$('run-dialog').showModal();}
  catch(error){notice(error.message,true);}
}
$('new-blog').addEventListener('click',()=>newBlog().catch(error=>notice(error.message,true)));
$('new-blog-form').addEventListener('submit',async event=>{
  event.preventDefault();const submit=event.target.querySelector('[type=submit]');
  try{await busy(submit,'Starting…',async()=>{
    const payload={title:$('new-blog-title').value,author:$('new-blog-author').value,goal:$('new-blog-goal').value,
      audience:$('new-blog-audience').value,tone:$('new-blog-tone').value,profile:$('new-blog-voice').value,
      sources:Array.from($('new-blog-sources').selectedOptions).map(option=>option.value),
      research:$('new-blog-research').value,stop:$('new-blog-stop').value,engine:$('new-blog-engine').value,
      seconds:Number($('new-blog-seconds').value)};
    if($('new-blog-id').value)payload.id=$('new-blog-id').value;
    const found=await api('run-create',{...payload,operation:operationFor('run-create',payload)});
    $('new-blog-dialog').close();$('detail-dialog').close();await openRun(found.id);await load();
  });}catch(error){notice(error.message,true);}
});
// Refresh only the run state while working. Never replace an open change-request form.
setInterval(async()=>{
  if(runLoading||!runSelection||!$('run-dialog').open||$('run-content').querySelector('details[open]'))return;
  try{const found=await api('run?id='+encodeURIComponent(runSelection));
    if(JSON.stringify([found.expected,found.status,found.error,found.enabled])!==runRevision)renderRun(found);
  }catch(error){notice(error.message,true);}
},3000);
