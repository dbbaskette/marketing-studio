// The writing desk: one page per blog with a card for each part, notes that rewrite a
// section, selection edits and quiet version history. Built with runner.js's helpers and the
// shared desk kit (ui-kit/drafting.js, bound to Blog Studio as DESK_KIT at the end of this
// file); every text from the draft is set with textContent.
'use strict';
const DESK_SELECTION=Drafting.SELECTION;
const DESK_SOURCES={save:'Before your edit',rewrite:'Before a rewrite','revise-all':'Before a whole-draft revision',selection:'Before a selection edit','first-pass':'Before the first pass',finishing:'Before a finishing change',restore:'Before a restore',draft:'Before the draft was written',chat:'Before an edit in chat',google:'Before Google’s accepted text'};
const DESK_DOING={'desk-section':'Rewriting','desk-revise-all':'Revising the whole draft','desk-selection':'Editing a passage','desk-first-pass':'Working on the first pass','desk-outline':'Outlining','desk-draft':'Writing the draft','desk-research':'Researching','finish-copyedit':'Copy editing the draft','finish-humanize':'Finding sentences to humanize','finish-facts':'Checking facts against your sources','finish-headline':'Suggesting headlines and openings','finish-feedback':'Reading the draft for feedback','finish-voice':'Rewriting the draft in a voice guide','finish-geo':'Reviewing retrieval readiness','finish-faq':'Writing FAQ questions','finish-table':'Looking for a comparison table','finish-quotes':'Finding quotations in your sources','finish-takeaways':'Gathering the key takeaways','finish-alt':'Writing image alt text','finish-queries':'Listing likely search questions','finish-opener':'Writing a definition-style opening'};
// A start's steps, as the progress screen names them.
const DESK_STEPS={research:'Researching',outline:'Outlining',draft:'Drafting'};
const DESK_SAVE_WAIT=Drafting.SAVE_WAIT,DESK_POLL=Drafting.POLL,DESK_DIFF_LIMIT=Drafting.DIFF_LIMIT;

// The word comparison, History's compare and a version's age are the shared desk kit's
// (ui-kit/drafting.js).
function deskWords(text){return Drafting.words(text);}
function diffWords(before,after){return Drafting.diffWords(before,after);}
function deskCompare(before,after){return DESK_KIT.compare(before,after);}
function deskAge(at){return Drafting.age(at);}
function deskPartName(view,part){if(part==='title')return 'the title';if(part==='opening')return 'the opening';if(part==='sections')return 'every section';const found=(view.sections||[]).find(section=>section.id===part);return found?'“'+deskHeading(found.heading)+'”':'a section';}
function deskTextOf(view,part){if(part==='title'||part==='opening')return view[part]||'';return (view.sections||[]).find(section=>section.id===part)?.text||'';}

// Images: a part's text holds only its short reference, ![][image1], as typed. The desk view
// lists the images by key without their data; the page reads the data once (desk-images),
// keeps it here, shows a thumbnail under each part that refers to one, and writes the images
// back at the end for Copy and Download. No form field or autosave ever holds the data.
const DESK_IMAGE_REF=/!\[([^\[\]\n]*)\]\[([^\[\]\n]*)\]/g;
function deskImageLabel(label){return String(label||'').split(/\s+/).filter(Boolean).join(' ').toLowerCase();}
function deskImageData(){return studio.deskImages||(studio.deskImages={});}
function deskImagesIn(view,text){
  const listed=view.images||[],out=[],seen=new Set();
  for(const found of String(text||'').matchAll(DESK_IMAGE_REF)){
    const label=deskImageLabel(found[2]||found[1]),image=listed.find(item=>deskImageLabel(item.label)===label);
    if(image&&!seen.has(image.key)){seen.add(image.key);out.push({...image,alt:found[2]?found[1]:''});}
  }
  return out;
}
// The images a part's text names that are kept nowhere, each once.
function deskImagesMissing(view,text){
  const lost=(view.missing_images||[]).map(deskImageLabel),out=[];
  for(const found of String(text||'').matchAll(DESK_IMAGE_REF)){const label=found[2]||found[1];if(lost.includes(deskImageLabel(label))&&!out.some(name=>deskImageLabel(name)===deskImageLabel(label)))out.push(label);}
  return out;
}
function sDeskThumbs(held,part){return sDeskThumbsFor(held.view,deskTextOf(held.view,part));}
function sDeskThumbsFor(view,text){
  const found=deskImagesIn(view,text),lost=deskImagesMissing(view,text);if(!found.length&&!lost.length)return null;
  const row=sNode('div','desk-images');row.setAttribute('aria-label','Images in this part');
  for(const image of found){
    const img=sNode('img','desk-thumb');img.alt=image.alt||'Image '+image.label;img.dataset.key=image.key;
    const data=deskImageData()[image.key];if(data)img.src=data;
    row.append(sAdd(sNode('figure','desk-image'),img,sNode('figcaption','quiet',image.label)));
  }
  // Named in the text, kept nowhere: said in its place, so the reference can be fixed or cut.
  // One too large for the blog's shared files stays in the Google Doc, shown as kept there.
  const kept=(view.kept_images||[]).map(deskImageLabel);
  for(const label of lost)row.append(sAdd(sNode('figure','desk-image desk-image-missing'),sNode('span','desk-thumb-missing',kept.includes(deskImageLabel(label))?'Image kept in the Google Doc':'Image missing'),sNode('figcaption','quiet',label)));
  return row;
}
// Read the images not kept yet, once, then fill the thumbnails waiting for them.
async function sDeskImagesLoad(held){
  if(!(held.view.images||[]).some(image=>!deskImageData()[image.key]))return;
  if(held.imagesLoading)return held.imagesLoading;
  held.imagesLoading=(async()=>{try{
    const found=await api('desk-images?'+new URLSearchParams({id:held.id}));
    for(const image of found.images||[])deskImageData()[image.key]=image.uri;
    for(const img of $('studio-page').querySelectorAll('.desk-thumb')){const data=deskImageData()[img.dataset.key];if(data&&!img.src)img.src=data;}
  }catch(_){/* The thumbnails wait; Copy and Download ask again. */}finally{held.imagesLoading=null;}})();
  return held.imagesLoading;
}
// The Markdown as DRAFT.md keeps it: the text, then each image it refers to. An image whose
// data cannot be read is left out and named, never stopping Copy or Download.
async function sDeskMarkdown(held){
  const kept=(held.view.kept_images||[]).map(deskImageLabel);
  const view=held.view,images=view.images||[],missing=(view.missing_images||[]).filter(label=>!kept.includes(deskImageLabel(label)));if(!images.length)return {markdown:view.markdown,missing};
  await sDeskImagesLoad(held);
  const lines=[];for(const image of images){const data=deskImageData()[image.key];if(data)lines.push('['+image.label+']: <'+data+'>'+(image.title?' '+image.title:''));else missing.push(image.label);}
  return {markdown:lines.length?view.markdown.replace(/\n$/,'')+'\n\n'+lines.join('\n\n')+'\n':view.markdown,missing};
}
// Images kept in the Google Doc, said once: they show as placeholders and Copy and Download
// leave them out, their placeholder in their place.
function sDeskKeptLine(view){const count=(view.kept_images||[]).length;if(!count)return null;const line=sNode('p','quiet desk-kept-images',count===1?'1 image is large, so it stays in the Google Doc and shows here as a placeholder.':count+' images are large, so they stay in the Google Doc and show here as placeholders.');return line;}
function deskWithout(done,missing){return missing.length?done+' without '+missing.join(', ')+(missing.length===1?': its image could not be read.':': their images could not be read.'):done+'.';}

// Start with the task and one source inventory; optional writing preferences follow.
// A draft to polish or review is one screen instead (sDeskPolish), with no kind of post.
const DESK_HAVE=[['topic','A topic'],['outline','An outline or notes'],['draft','A draft']];
const DESK_OUTLINE_WAYS=[['outline','Write from my outline'],['shape','Shape an outline with me first']];
const DESK_START_STEPS=['Idea and sources','Writing preferences'];
const DESK_START_LEDES=['Bring your idea or outline and add any sources once.','Check the writing preferences, then start. Your choices and sources are kept.'];
const DESK_INTAKE_FIELDS='step kind style researchOn have title audience point angles angle angleOp outline outlineFrom outlineWay source article manuscript url link collection preview first_pass humanizeOn humanizeLevel geoReview voiceOn voiceGuide files role keep from searchSites searchWeb length tone operation upload uploaded docKeep sourceDraft sourceEntry fileData outlineFileData'.split(' ');
class BlogIntake extends Drafting.Intake {
  snapshot(held,open=true){
    const value=Object.fromEntries(DESK_INTAKE_FIELDS.filter(key=>held[key]!==undefined).map(key=>[key,held[key]]));
    if(held.sourceEditor){value.sourceDraft=held.sourceEditor.spec()||held.sourceEditor.resume||held.sourceDraft||null;value.sourceEntry=Object.fromEntries(['urls','text','name','pasting','keep'].map(key=>[key,held.sourceEditor[key]??null]));}
    return {...value,intakeOpen:open};
  }
}
function sBlogIntake(){return studio.intake||(studio.intake=new BlogIntake(sent=>api('intake-draft',sent)));}
async function sDeskFilesKeep(held){
  for(const key of ['file','outlineFile']){
    const file=held[key],cache='_'+key+'Cache',data=key+'Data';
    if(!file){held[data]=null;continue;}
    if(held[cache]?.file===file){held[data]=await held[cache].value;continue;}
    if(file.size>10*1024*1024)throw Error('Choose a file up to 10 MiB. Your other answers are still here.');
    const value=encodeImportFile(file).then(content=>({name:file.name,size:file.size,content}));
    held[cache]={file,value};held[data]=await value;
  }
}
function sDeskFilesRestore(held){
  for(const key of ['file','outlineFile'])if(held[key+'Data']){
    const data=held[key+'Data'];held[key]={name:data.name,size:data.size,arrayBuffer:async()=>Uint8Array.from(atob(data.content),c=>c.charCodeAt(0)).buffer};
    held['_'+key+'Cache']={file:held[key],value:Promise.resolve(data)};
  }
}
function sDeskKeep(held,open=true){
  const intake=sBlogIntake();clearTimeout(held._saveTimer);held._saveTimer=null;
  const run=async()=>{
    for(const node of document.querySelectorAll('[data-intake-status]'))node.textContent='Saving intake…';
    const edit=held._editRevision||0;
    try{await sDeskFilesKeep(held);const ok=await intake.keep(held,open);if(ok&&edit===(held._editRevision||0))held._dirty=false;return ok;}
    catch(error){intake.problem=error.message;intake.status();return false;}
  };
  const saving=(held._saving||Promise.resolve()).then(run,run);held._saving=saving;
  saving.finally(()=>{if(held._saving===saving)held._saving=null;});return saving;
}
async function sDeskConsumed(held,revision){
  const intake=sBlogIntake();
  if(studio.deskStart!==held||intake.revision!==revision||held._dirty||held._saving)return;
  clearTimeout(held._saveTimer);held._saveTimer=null;
  try{
    const cleared=await intake.request({action:'discard',expected:revision});
    if(studio.deskStart===held&&!held._dirty&&!held._saving&&intake.revision===revision){
      intake.revision=cleared.revision;intake.saved=null;intake.encoded={};studio.deskStart=null;
    }
  }catch(error){intake.problem=error.message;intake.status();}
}
function sDeskIntakeControls(held){
  const intake=sBlogIntake(),form=$('studio-page').querySelector('form');if(!form)return;
  const status=sNode('p','quiet field-hint');status.dataset.intakeStatus='true';status.setAttribute('role','status');
  const save=sButton('Save and close',async()=>{if(await sDeskKeep(held,false))await sRoute('home');});
  const discard=sButton('Discard draft',async()=>{if(!confirm('Discard this unfinished blog form? Captured sources and existing blogs are kept.'))return;clearTimeout(held._saveTimer);held._saveTimer=null;if(held._saving)await held._saving;if(await intake.discard()){studio.deskStart=null;await sRoute('home');}});
  form.append(sAdd(sNode('div','form-foot'),status,sAdd(sNode('div','bar'),save,discard)));
  const changed=()=>{held._editRevision=(held._editRevision||0)+1;held._dirty=true;clearTimeout(held._saveTimer);held._saveTimer=setTimeout(()=>{held._saveTimer=null;sDeskKeep(held);},250);status.textContent='Saving intake…';};
  form.addEventListener('input',changed);form.addEventListener('change',changed);
  form.addEventListener('click',event=>{if(event.target.closest('.segmented'))changed();});
  sDeskKeep(held);
}
// Settings' research for new blogs is where the start's ticks begin: Search my sites when it
// ticks your sites and the shared list has any, Search the web too when it ticks the public
// web. Your documents are always read. The person can change both for this blog.
function sDeskResearchDefault(value){const ticks=OLD_RESEARCH[value]||(value&&typeof value==='object'?value:{});return {searchSites:!!ticks.sites&&sSharedSites().length>0,searchWeb:!!ticks.web};}
function sDeskHeld(){
  if(studio.deskStart)return studio.deskStart;
  const defaults=studio.options?.settings?.defaults||{},preset=studio.deskPreset||{};studio.deskPreset=null;
  return studio.deskStart={step:0,kind:'',style:'',researchOn:false,have:'topic',title:'',audience:'',point:'',angles:[],angle:null,angleOp:null,anglesBusy:false,anglesProblem:'',outline:'',outlineFrom:'paste',outlineFile:null,outlineWay:'outline',source:'paste',article:null,manuscript:'',url:'',link:'',collection:null,collectionProblem:'',file:null,preview:null,first_pass:null,humanizeOn:false,humanizeLevel:'light',geoReview:false,voiceOn:false,voiceGuide:'',files:[],role:'material',keep:false,from:{on:true,documents:true,sites:false,web:false,picked:[...sSharedSites()],added:[]},...sDeskResearchDefault(defaults.research),length:'style',tone:defaults.tone||'',operation:operationId(),upload:operationId(),...preset};
}
// Home's tasks, New blog, the library's "Write a blog from these", an interview's outline and
// a saved blog's details all start here.
async function sDeskBegin(preset={}){
  const intake=sBlogIntake();await intake.load();
  if(Object.keys(preset).length&&(studio.deskStart||intake.saved)){
    if(!confirm('Replace the unfinished blog form with this new starting point? Cancel resumes the saved form.'))return sRoute('desk-start');
    const held=studio.deskStart;if(held){clearTimeout(held._saveTimer);held._saveTimer=null;if(held._saving)await held._saving;}
    if(!await intake.discard())return notice(intake.problem,true);
  }
  if(Object.keys(preset).length||(!studio.deskStart&&!intake.saved)){studio.deskStart=null;studio.deskPreset=preset;}
  return sRoute('desk-start');
}
// What a step of New blog holds so far, for its place in the step row.
function sDeskStepSays(held,index){
  if(index===0)return (held.title||'').trim()||(DESK_HAVE.find(([value])=>value===held.have)||[])[1]||'Your idea';
  const kind=(studio.options?.styles||[]).find(found=>found.id===held.kind);
  return (kind?kind.name:'Any kind of post')+((held.tone||'').trim()?' · '+held.tone.trim():'');
}
async function sDeskStart(){
  if(!studio.options)studio.options=await api('run-options');
  const intake=sBlogIntake();if(!intake.ready)await intake.load();
  const restore=!studio.deskStart&&intake.saved;
  const held=sDeskHeld();
  if(restore){Object.assign(held,intake.saved);sDeskFilesRestore(held);}
  if(held.have==='draft'){sDeskPolish(held);sDeskIntakeControls(held);return;}
  sFrame('New blog',[],'New writing',()=>sRoute('home'));
  held.step=Math.min(held.step,1);
  // The same guided step row the other studios' starts show: what was chosen in each step,
  // a tick once the first is complete, and a press that opens a step.
  const says=index=>sDeskStepSays(held,index);
  const steps=sNode('ol','intake-progress intake-guided');steps.setAttribute('aria-label','Creation progress');
  steps.append(...Drafting.Intake.steps(DESK_START_STEPS,held.step,new Set(held.step?[0]:[]),says,index=>{if(index){const problem=sDeskHaveProblem(held);if(problem)return notice(problem,true);}held.step=index;sTop();sDeskStart();}));
  const form=held.step===0?sDeskHave(held):sDeskSettings(held);
  const retell=()=>steps.querySelectorAll('.intake-step-summary').forEach((node,index)=>{node.textContent=says(index);});
  form.addEventListener('input',retell);form.addEventListener('change',retell);
  sPage(sNode('p','lede',DESK_START_LEDES[held.step]),steps,form);
  sDeskIntakeControls(held);
}
function sDeskStartAgain(held){if(studio.screen==='desk-start'&&studio.deskStart===held)sDeskStart();}
function sDeskWriting(held){return held.have!=='draft';}

// First: the writing task and one source list. A draft switches to its polishing screen.
function sDeskHave(held){
  const form=sNode('form','narrow desk-start'),problem=sNode('p','problem',held.problem||'');problem.setAttribute('role','alert');delete held.problem;
  const parts=[sCard('What do you have?',sChoice('What you bring',DESK_HAVE,held,'have',()=>sDeskStart()))];
  const content=held.have==='topic'?sDeskTopic(held):[sDeskOutlineIn(held)],research=sDeskResearchOptions(held);
  parts.push(content[0],sFilesCard(held,problem,()=>sDeskStartAgain(held),()=>{}),...content.slice(1),research);
  const go=sNode('button','button button-filled','Next');go.type='submit';go.disabled=!access.actions.edit;
  form.append(...parts,sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),go)),sGeoInstead());
  form.addEventListener('submit',event=>{event.preventDefault();if(studio.busy)return;const said=sDeskHaveProblem(held);if(said){problem.textContent=said;return;}held.step=1;sTop();sDeskStart();});
  return form;
}

// Then: optional post type, length and tone. Sources remain on the first step.
function sDeskSettings(held){
  // A refused role change is said here after the card is drawn again.
  const form=sNode('form','narrow desk-start'),problem=sNode('p','problem',held.problem||'');problem.setAttribute('role','alert');delete held.problem;
  const go=sNode('button','button button-filled','Start');go.type='submit';go.disabled=studio.busy||!access.actions.edit;
  const kinds=(studio.options?.styles||[]).filter(kind=>kind.status!=='retired');
  form.append(sCard('Kind of post (optional)',sField('desk-kind','Kind of post',held,'kind',{options:[['','Follow my idea and sources'],...kinds.map(kind=>[kind.id,kind.name])],changed:()=>{held.style=held.kind;sStyleSamples(held);}}),sNode('p','quiet','A saved kind supplies a usual shape and length. Leave it open for this blog.')));
  form.append(sCard(sDeskWriting(held)?'Length and tone':'Tone',sDeskWriting(held)?sLengthSelect(held,'desk-length'):null,sField('desk-tone','Tone',held,'tone',{max:2000,hint:'Such as clear and conversational.'})));
  form.append(sDeskGeoStart(held));
  const back=sButton('Back',()=>{held.step=0;sTop();sDeskStart();});
  form.append(sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),back,go)));
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(!access.actions.edit||studio.busy)return;
    if(sDeskWriting(held)&&!held.sourceEditor&&held.searchSites&&!sChosenSites(held.from).length){problem.textContent=sResearchWord('no_sites')||'Choose at least one of your sites, or untick Search my sites.';return;}
    // What you have is said on its own step.
    const said=sDeskHaveProblem(held);if(said){held.problem=said;held.step=0;sTop();sDeskStart();return;}
    await busy(go,'Starting…',async()=>{try{await sDeskGo(held);}catch(error){problem.textContent=error.message+' Your choices are kept here.';}});
  });
  return form;
}
function sDeskResearchOptions(held){
  const box=sCard('Research (optional)',sNode('p','quiet','All sources above stay with this blog. Facts are evidence; messaging stays attributed; examples guide the writing only.'));
  const saved=(held.sourceEditor?.value?.sources||[]).some(source=>source.status==='ready');if(saved)held.researchOn=true;
  const toggle=sCheck('desk-research-on','Research these sources before writing',held,'researchOn',saved?'Saved research is checked for this blog’s purpose. Remove it from Sources to write without that check.':'Research runs if either option is on. Leave both off to write directly from your sources.');if(saved)toggle.querySelector('input').disabled=true;box.append(toggle);
  if(typeof StudioResearch!=='undefined'){
    if(!held.sourceEditor){held.sourceSignature='[]';held.sourceEditor=new StudioResearch.Editor({resume:held.sourceDraft,onChange:value=>{const signature=JSON.stringify(value?.sources||[]);if(signature!==held.sourceSignature){held.sourceSignature=signature;sDeskStartAgain(held);}},request:async sent=>{let value=await api('research-sources',sent);if(sent.action==='create'&&(held.searchSites||held.searchWeb))value=await api('research-sources',{action:'configure',id:value.id,expected:value.revision,external:true,restricted:!held.searchWeb});return value;},policyOnly:true});if(held.sourceEntry)Object.assign(held.sourceEditor,held.sourceEntry);}
    box.append(held.sourceEditor.node);
  }else sAdd(box,sCheck('desk-sites','Search my sites',held,'searchSites',null,()=>sDeskStartAgain(held)),held.searchSites?sSitePicker(held.from,'desk-research',()=>{}):null,sCheck('desk-web','Search the web too',held,'searchWeb'));
  return box;
}
// Polishing or reviewing a draft: the draft, what happens first, then Start. A kind of post
// is asked for only to reshape the draft; sources are optional, for the fact check.
// Check spelling and grammar is Finishing's Copy edit, opened in Review mode (sDeskReview).
const DESK_POLISH_FIRST=[['copyedit','Check spelling and grammar'],['feedback','Just give feedback'],['geo','Review for AI search (GEO)'],['reshape','Reshape to fit a kind of post'],['leave','Leave it as it is']];
const DESK_POLISH_SAYS={geo:'Recommends changes for clearer answers, consistent names, cited evidence and passages that stand on their own. They wait in Finishing to preview, then apply or skip. Nothing changes until you accept.',copyedit:'See each fix marked in your text, then accept or reject it. Nothing changes until you accept.',feedback:'Comments on shape, argument, audience and claims appear beside each part. Nothing in the text changes.',reshape:'The sections and length are reshaped to the kind of post; a draft with no headings may be divided into sections. Your text is kept as a version first.',leave:'The draft opens on the desk as it is, for your own edits and notes.'};
function sDeskPolish(held){
  if(!DESK_POLISH_FIRST.some(([value])=>value===held.first_pass))held.first_pass=held.source==='saved'?'leave':'copyedit';
  // The kind of post goes with the draft only to reshape it, with a learned kind's samples.
  const style=held.first_pass==='reshape'?held.kind||'':'';if(held.style!==style){held.style=style;sStyleSamples(held);}
  sFrame('Polish a draft',[],'Writing desk',()=>sRoute('home'));
  const form=sNode('form','narrow desk-start'),problem=sNode('p','problem',held.problem||'');problem.setAttribute('role','alert');delete held.problem;
  const again=()=>sDeskStartAgain(held);
  const googleAction={copyedit:'Read and polish',feedback:'Read and review',geo:'Read and review for AI search',reshape:'Read and reshape',leave:'Open Google Doc'}[held.first_pass];
  const linkAction=held.preview?'Start':'Read the page and start';
  const go=sNode('button','button button-filled',held.source==='google'?(held.preview?'Start':googleAction):held.source==='link'?linkAction:'Start');go.type='submit';go.disabled=studio.busy||!access.actions.edit;
  const first=sCard('What should happen first',sChoice('When the desk opens',DESK_POLISH_FIRST,held,'first_pass',()=>again()),sNode('p','quiet field-hint',DESK_POLISH_SAYS[held.first_pass]));
  // Check spelling and grammar may also suggest more human-sounding wording, at a strength,
  // mixed in with the fixes. Ticking it shows the strength in place, so focus stays put.
  if(held.first_pass==='copyedit'){const strength=sChoice('Strength',DESK_LEVELS,held,'humanizeLevel');strength.hidden=!held.humanizeOn;first.append(sCheck('desk-humanize','Also suggest more human-sounding wording',held,'humanizeOn',REVIEW_HUMAN_SAYS,on=>{strength.hidden=!on;}),strength,sPolishVoiceChoice(held,'polish'));}
  if(held.first_pass==='reshape'){const kinds=(studio.options?.styles||[]).filter(kind=>kind.status!=='retired');first.append(sField('desk-kind','Kind of post',held,'kind',{options:[['','Choose a kind of post'],...kinds.map(kind=>[kind.id,kind.name])],changed:()=>again()}),sNode('p','quiet field-hint',kinds.length?'Its usual shape and length.':'No kinds of post yet. Set them up from Home, under Kinds of post.'));}
  const fold=(label,open,remember,...content)=>{const box=sAdd(sNode('details','card desk-fold'),sAdd(sNode('summary',''),sNode('span','card-title',label)),...content);box.open=open;box.addEventListener('toggle',()=>remember(box.open));return box;};
  const tone=fold('Tone (optional)',!!held.toneOpen,open=>{held.toneOpen=open;},sField('desk-tone','Tone',held,'tone',{max:2000,hint:'Such as clear and conversational. It guides any rewriting.'}));
  const facts=fold('Check facts against your sources (optional)',held.factsOpen??held.files.length>0,open=>{held.factsOpen=open;},sNode('p','quiet','Finishing’s fact check reads these. They stay with this blog unless you keep them in the team library.'),...[...sFilesCard(held,problem,again,locked=>{go.disabled=locked||!access.actions.edit;}).children].slice(1));
  const instead=sButton('Writing something new? Start from a topic or an outline',()=>{held.have='topic';if(held.kind===null)held.step=0;else{held.style=held.kind;sStyleSamples(held);}sTop();sDeskStart();});instead.className+=' desk-instead';
  const linked=held.linkedRun;delete held.linkedRun;const run=linked?sButton('Open its run',()=>sRoute('run',linked)):null;
  sAdd(form,...sDeskDraftIn(held),first,tone,facts,held.first_pass==='geo'?null:sDeskGeoStart(held),sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),go,run)),['saved','upload','collection'].includes(held.source)?null:instead,['saved','upload','collection'].includes(held.source)?null:sGeoInstead());
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(!access.actions.edit||studio.busy||held.starting)return;const said=sDeskHaveProblem(held);if(said){problem.textContent=said;return;}
    // A read that fails again says so as a new answer, so pressing the button visibly reads.
    const failed=problem.textContent,needsRead=['google','link','collection'].includes(held.source)&&!held.preview;problem.textContent='';
    held.starting=true;const reading=needsRead?sDeskReadingSheet(held):null,unlock=sFreezeControls(form);
    try{await busy(go,needsRead?'Reading and starting…':'Starting…',async()=>{try{if(needsRead&&held.source==='google')await sDeskReadGoogle(held,{start:true,read:reading.read});else if(needsRead)await sDeskReadPublished(held,{start:true,read:reading.read});else await sDeskGo(held);}catch(error){if(reading)reading.close();const readFailed=needsRead&&!held.preview;if(readFailed&&held.find){await sDeskFindShown(held);return;}problem.textContent=(readFailed&&failed?'Read again, and still: ':'')+error.message+(readFailed?(held.source==='google'?' Your link is kept here; change the Doc or try again.':' Your link is kept here; change it or try again.'):' Your choices and captured draft are kept here.');}});}
    // A read that was refused leaves the reason on the form and the focus on its button.
    finally{if(reading)reading.close();held.starting=false;unlock();if(reading&&problem.textContent&&go.isConnected&&typeof go.focus==='function')go.focus();}
  });
  sPage(sNode('p','lede','Bring your draft and choose what happens first. No kind of post needed.'),form);
}
// Include a GEO review on New blog: off by default, kept with the post, changeable on its desk.
function sDeskGeoStart(held){return sCard('GEO review (optional)',sCheck('desk-geo-review','Include a GEO review',held,'geoReview',DESK_GEO_SAYS));}
function sDeskHaveProblem(held){
  if(held.have==='draft'&&held.first_pass==='copyedit'&&held.voiceOn&&!held.voiceGuide)return 'Choose a voice guide, or turn Use a voice guide off.';
  if(held.have!=='draft'&&!held.sourceEditor&&held.searchSites&&!sChosenSites(held.from).length)return sResearchWord('no_sites')||'Choose at least one of your sites, or untick Search my sites.';
  if(held.have==='topic'&&!(held.title.trim()&&held.point.trim()))return 'Add a working title and the point to make, or pick an angle.';
  if(held.have==='outline'){
    if(held.outlineFrom==='paste'&&!held.outline.trim())return 'Paste your outline or notes first.';
    if(held.outlineFrom==='file'&&!held.outlineFile)return 'Choose your outline to upload.';
    if(held.outlineFrom==='paste'&&!held.title.trim()&&!/^# \S/.test(held.outline.trim()))return 'Give the blog a title, or start your outline with a # title line.';
  }
  if(held.have==='draft'){
    if(held.source==='paste'&&!held.manuscript.trim())return 'Paste your draft first.';
    if(held.source==='file'&&!held.file)return 'Choose a draft to upload.';
    if(held.source==='google'&&!held.url.trim())return 'Paste the Google Doc link first.';
    if(held.source==='link'&&!held.link.trim())return 'Paste the post’s link first.';
    if(held.first_pass==='reshape'&&!held.kind)return 'Choose a kind of post to reshape the draft to.';
  }
  return '';
}
// A topic: the point typed, or three angles from the sources chosen, to pick and edit.
function sDeskTopic(held){
  const card=sCard('Your topic',sField('desk-title','Working title',held,'title',{required:true,max:500}),sField('desk-audience','Who is it for?',held,'audience',{max:500}),sField('desk-point','The point to make',held,'point',{long:true,max:2000,hint:'What the reader should understand or do afterward.'}));
  const ready=held.files.filter(file=>file.state==='ready').length;
  const ask=sButton(held.angles.length?'Suggest three more':'Suggest three angles',button=>sDeskAskAngles(held,button));ask.disabled=!access.actions.edit||held.anglesBusy;
  const discovery=sCard('Need an angle?',sAdd(sNode('div','bar'),ask),sNode('p','quiet field-hint',ready?'Angles read your '+ready+(ready===1?' source.':' sources.'):'With no sources, angles work from the title and point.'));
  if(held.anglesBusy){const working=sNode('p','desk-working-note','Finding three angles…');working.setAttribute('role','status');discovery.append(working);const doing=sActivityNow(held.anglesActivity,{});if(doing)discovery.append(doing);}
  if(held.anglesProblem)discovery.append(sNode('p','problem',held.anglesProblem));
  if(!held.angles.length)return [card,discovery];
  const cards=sNode('div','desk-angles');cards.setAttribute('aria-label','Three angles');
  held.angles.forEach((angle,index)=>{
    const picked=held.angle===index,box=sNode('section','card desk-angle'+(picked?' desk-angle-picked':''));
    const follow=()=>{if(held.angle===index)Object.assign(held,{title:angle.headline,point:angle.point,audience:angle.audience});};
    box.append(sNode('h2','card-title','Angle '+(index+1)),sField('desk-angle-'+index+'-headline','Headline',angle,'headline',{max:300,changed:follow}),sField('desk-angle-'+index+'-point','The point it makes',angle,'point',{long:true,max:2000,changed:follow}),sField('desk-angle-'+index+'-audience','Who it is for',angle,'audience',{max:500,changed:follow}));
    const use=sButton(picked?'Using this angle':'Use this angle',()=>{held.angle=index;follow();sDeskStart();});use.setAttribute('aria-pressed',String(picked));
    box.append(sAdd(sNode('div','bar'),use));cards.append(box);
  });
  return [card,discovery,cards];
}
function sDeskLibraryPicks(files){return files.filter(file=>file.library&&file.state==='ready').map(file=>({id:file.id,role:FILE_ROLES[file.role]||'facts',...(file.location==='hub'?{location:'hub'}:{})}));}
function sDeskUploads(files){return [...new Set(files.filter(file=>!file.library&&file.state==='ready').map(file=>file.id))];}
// Files with Keep ticked: the server moves them to the team library once the blog is made
// (or the source is added), never before, and a repeated request keeps nothing twice.
function sDeskKept(files){const kept=sDeskUploads(files.filter(file=>file.kept));return kept.length?{keep:kept}:{};}
async function sDeskAskAngles(held,button){
  const operation=operationId(),replaces=held.angleOp;held.angleOp=operation;held.anglesProblem='';
  await busy(button,'Asking…',async()=>{try{
    const shown=await api('desk-angles',{operation,title:held.title.trim(),point:held.point.trim(),audience:held.audience.trim(),style:held.kind||'',tone:held.tone,sources:sDeskUploads(held.files),library:sDeskLibraryPicks(held.files),...(replaces?{replaces}:{})});
    sDeskAnglesShown(held,shown);
  }catch(error){held.anglesProblem=error.message;sDeskStartAgain(held);}});
}
function sDeskAnglesShown(held,shown){
  if(held.angleOp!==shown.operation)return;
  held.anglesBusy=!!shown.busy;held.anglesActivity=shown.activity||[];
  if(!shown.busy){if(shown.error)held.anglesProblem=shown.error;else{held.angles=shown.angles.map(angle=>({...angle}));held.angle=null;}}
  sDeskStartAgain(held);
  if(shown.busy)setTimeout(async()=>{if(held.angleOp!==shown.operation||studio.deskStart!==held)return;try{sDeskAnglesShown(held,await api('desk-angles?'+new URLSearchParams({operation:shown.operation})));}catch(error){held.anglesBusy=false;held.anglesProblem=error.message;sDeskStartAgain(held);}},DESK_POLL);
}
// An outline or notes: pasted or uploaded, then written from, or shaped together first.
function sDeskOutlineIn(held){
  const card=sCard('Your outline or notes',sChoice('Where is it?',[['paste','Paste'],['file','Upload a file']],held,'outlineFrom',()=>sDeskStart()));
  if(held.outlineFrom==='paste')card.append(sField('desk-outline','Paste your outline or notes',held,'outline',{long:true,max:200000,required:true,hint:'Headings or a list make the sections.'}));
  else{const file=sNode('input','input');file.type='file';file.accept='.txt,.md,.docx,.pdf,application/pdf,.html,.htm';file.setAttribute('aria-label','Upload an outline');const note=sNode('p','quiet field-hint',held.outlineFile?'Selected: '+held.outlineFile.name:'Text, Markdown, Word or PDF.');file.addEventListener('change',()=>{held.outlineFile=file.files?.[0]||null;note.textContent=held.outlineFile?'Selected: '+held.outlineFile.name:'Choose an outline.';});card.append(file,note);}
  card.append(sField('desk-title','Title (optional)',held,'title',{max:500,hint:'Blank uses the outline’s # heading.'}),sChoice('Then',DESK_OUTLINE_WAYS,held,'outlineWay',()=>sDeskStart()),sNode('p','quiet field-hint',held.outlineWay==='shape'?'The outline opens on the desk for you to shape first.':'The draft is written from your outline.'));
  return card;
}
// A draft: paste, upload or one selected Google Doc tab. A start opened from a saved blog's
// details also offers that blog's own draft, brought as it is.
function sDeskDraftIn(held){
  const saved=held.article?sCheck('desk-saved','Use this blog’s saved draft',{on:held.source==='saved'},'on','It comes to the desk as it is, in the same blog. Its history is kept.',on=>{held.source=on?'saved':'paste';held.preview=null;sDeskStart();}):null;
  const uploaded=held.uploaded?sCheck('desk-uploaded','Use the file you uploaded',{on:held.source==='upload'},'on','“'+held.uploaded.name+'” comes to the desk as it is. It stays in the team library too.',on=>{held.source=on?'upload':'paste';held.preview=null;sDeskStart();}):null;
  const kept=['saved','upload','collection'].includes(held.source);
  const card=sCard('Your draft',saved,uploaded,kept?null:sChoice('Where is your draft?',[['paste','Paste text'],['file','Upload a file'],['google','Google Doc'],['link','Link to a published post']],held,'source',()=>{held.preview=null;sDeskStart();}));
  if(held.source==='saved'){/* The blog's own draft: nothing to paste or read. */}
  else if(held.source==='collection'){
    // A post from a team collection: a copy comes to the desk; the collection keeps its entry.
    card.append(sNode('p','','A copy of “'+(held.collection?.title||'this post')+'” from your team library comes to the desk. Its entry in the collection stays as it is.'));
    if(held.preview)card.append(sPublishedPreview(held.preview,'The post as saved in the collection'));
    else if(held.collectionProblem)card.append(sNode('p','problem',held.collectionProblem));
    else{card.append(sNode('p','quiet','Reading the saved post…'));sDeskReadCollection(held);}
  }
  else if(held.source==='link'){
    // A published post by its link: read once on a press, shown here, then started.
    card.append(sField('desk-link','Link to the published post',held,'link',{required:true,max:2000,hint:'Its page is read once, without running anything on it, and shown here before anything starts. The desk works on a copy; the published page is never changed.',changed:()=>{held.preview=null;sFindTextGone(held);}}));
    const read=sButton(held.preview?'Read the page again':'Read the page',button=>busy(button,'Reading…',()=>sDeskReadLink(held)));read.disabled=!access.actions.edit;
    card.append(sAdd(sNode('div','bar'),read));
    if(held.find&&!held.preview){const find=held.find;card.append(sFindText(find,{current:()=>studio.screen==='desk-start'&&studio.deskStart===held&&held.find===find,found:()=>{held.find=null;return sDeskReadLink(held);}}));}
    if(held.preview)card.append(sPublishedPreview(held.preview,'The post as it was read'));
  }
  else if(held.source==='upload'){if(held.uploaded.text){const paper=sNode('article','paper doc');paper.setAttribute('aria-label','The uploaded file’s text');paper.append(window.StudioMarkdown?window.StudioMarkdown.render(held.uploaded.text):sNode('p','',held.uploaded.text));card.append(sNode('p','quiet',held.uploaded.truncated?'Its text as it was read, the first part shown:':'Its text as it was read:'),paper);}}
  else if(held.source==='paste')card.append(sField('desk-manuscript','Paste your draft',held,'manuscript',{long:true,max:1000000,required:true,hint:'Up to 200,000 characters of text; images in it are not counted. Its headings start the sections, at whatever level it uses.'}));
  else if(held.source==='file'){
    const file=sNode('input','input');file.type='file';file.accept='.txt,.md,.docx,.pdf,application/pdf,.html,.htm';file.setAttribute('aria-label','Upload a draft');
    const note=sNode('p','quiet field-hint',held.file?'Selected: '+held.file.name:'Text, Markdown, Word or PDF.');
    file.addEventListener('change',()=>{held.file=file.files?.[0]||null;note.textContent=held.file?'Selected: '+held.file.name:'Choose a draft.';});
    card.append(file,note);
  }else{
    card.append(sField('desk-google','Google Doc link or document ID',held,'url',{required:true,max:2000,hint:'Your chosen pass starts after the Doc is read locally. For a Doc with multiple tabs, paste the address of the tab you want. Only that tab is imported; the Doc is not changed.',changed:()=>{held.preview=null;}}));
    if(held.preview){const paper=sNode('article','paper doc google-preview');paper.tabIndex=-1;paper.setAttribute('aria-label','Google Doc preview');paper.append(window.StudioMarkdown?window.StudioMarkdown.render(held.preview.content):sNode('p','',held.preview.content));const tab=held.preview.summary.selected_tab;card.append(sNode('p','',tab?'Only the tab “'+tab.title+'” is included. Other tabs are not imported. Check the text below, then start.':'Check the text below, then start.'));if(held.preview.summary.excluded_approval_blocks)card.append(sNode('p','quiet','Leading approval fields are left out of this editing copy. They stay in the Google Doc. Check that the blog below is complete.'));card.append(paper);}
  }
  card.append(sField('desk-title','Title (optional)',held,'title',{max:500,hint:'Blank uses the draft’s # heading or the Doc’s name.'}));
  return [card];
}
// A read that takes a while says so the moment it is asked for, in a sheet: what is being
// read, what follows, and that nothing is asked of the person. It moves on when the text is
// in hand and puts itself away when the desk opens, or when the read is refused.
const DESK_READ_THEN={copyedit:'Check spelling and grammar',feedback:'Review it',geo:'Review it for AI search',reshape:'Reshape it'};
function sDeskReadingSheet(held){
  const google=held.source==='google',then=DESK_READ_THEN[held.first_pass];
  const names=[google?'Read the Doc':'Read the page','Open it on the desk',...(then?[then]:[])];
  const line=sNode('p','reading-now'),steps=sNode('div','reading-steps');line.setAttribute('role','status');
  const show=at=>{
    line.textContent=at?'Opening it on the desk…':google?'Reading your Google Doc…':'Reading the page…';
    steps.replaceChildren(...(typeof StudioShell==='undefined'?[]:[StudioShell.track(names.map((label,index)=>({label,state:index<at?'done':index===at?'current':'todo'})),'What happens now')]));
  };
  show(0);
  sOpenSheet(google?'Bringing in your Google Doc':'Bringing in the page',line,steps,sNode('p','quiet','Nothing for you to do. '+(google?'Only the tab you linked is read, and the Doc is not changed. ':'')+'This can take up to a minute, and the desk opens by itself.'));
  const owner=studio.sheet;
  return {read:()=>{if(studio.sheet===owner)show(1);},close:()=>{if(studio.sheet===owner)sCloseSheet();}};
}
async function sDeskReadGoogle(held,{start=false,read=null}={}){
  const turn=studio.turn,found=await api('google-preview',{url:held.url.trim()});if(turn!==studio.turn)return;
  if(found?.status==='view-only')return sDeskGoogleCopyOffer(held,found);
  if(found?.status==='already-linked'&&found.id){
    // The Doc is already a blog here: open it on the desk, or bring it there.
    if(!await sDeskKeep(held))throw Error(sBlogIntake().problem);
    const intakeRevision=sBlogIntake().revision;
    let made=null,created=false;try{made=await api('desk?id='+encodeURIComponent(found.id));}catch(_){made=null;}
    // A Doc an older step-by-step run links stays with that run: the start offers it.
    if(!made){created=true;try{made=await api('desk-create',{intake_revision:sBlogIntake().revision,operation:held.operation,style:held.style,tone:held.tone,first_pass:held.first_pass,...sDeskPolishOptions(held),sources:sDeskUploads(held.files),library:sDeskLibraryPicks(held.files),...sDeskKept(held.files),article:found.id});}catch(error){if(!/step-by-step run/.test(error.message))throw error;if(turn!==studio.turn)return;held.problem=error.message;held.linkedRun=found.id;return sDeskStart();}}
    await sDeskConsumed(held,intakeRevision);if(turn!==studio.turn)return;studio.desk={id:made.id,view:made,session:operationId()};if(!created&&held.first_pass==='copyedit'&&held.voiceOn)studio.desk.review={pendingVoice:{guide:held.voiceGuide,name:(held.polishVoices?.find(guide=>guide.id===held.voiceGuide)||{}).name||'Selected voice',humanize:held.humanizeOn?held.humanizeLevel:null}};return sRoute('desk',made.id,held.first_pass==='copyedit'&&(created||held.voiceOn)?'review':null);
  }
  held.preview=sGooglePreview(found);if(!held.title.trim())held.title=found.title;
  if(start){if(read)read();const made=await sDeskGo(held);if(made&&studio.screen==='desk'&&studio.id===made.id){const summary=held.preview.summary,notes=[];if(summary.selected_tab)notes.push('Opened only the tab “'+summary.selected_tab.title+'”.');if(summary.excluded_approval_blocks)notes.push('Leading approval fields stay in the original Google Doc.');if(notes.length)sToast(notes.join(' '));}return made;}
  await sDeskStart();const paper=$('studio-page').querySelector('.google-preview');if(paper&&typeof paper.focus==='function')paper.focus({preventScroll:false});
}
function sDeskGoogleCopyOffer(held,found){
  const original=held.url,turn=studio.turn,problem=sNode('p','sheet-error');problem.setAttribute('role','alert');
  const title=found.access==='comment-only'?'Comment-only Google Doc':'View-only Google Doc';
  const explanation=found.access==='comment-only'?'You can comment on the original, but Blog Studio needs an editable copy for this review.':'You can read the original, but cannot send suggestions or comments to it.';
  const create=found.can_copy?sButton(found.copy_pending?'Check copy':'Create copy in My Drive',async button=>{
    await busy(button,found.copy_pending?'Checking copy…':'Creating copy…',async()=>{
      let copied;
      try{copied=await api('google-copy',{copy:found.copy,confirmed:true});}
      catch(error){problem.textContent=error.message;found.copy_pending=true;return;}
      if(studio.sheet!==owner||turn!==studio.turn||studio.deskStart!==held||held.url!==original)return;
      // Keep the confirmed URL before reading it: a capture failure or restart
      // must never send the author back through another copy operation.
      held.url=copied.url;held.preview=null;sCloseSheet();
      try{if(!await sDeskKeep(held))throw Error(sBlogIntake().problem);await sDeskReadGoogle(held);sToast('Review copy created in My Drive for '+copied.account+'. Check its text, then start.');}
      catch(error){held.problem='Your review copy is in My Drive. Its link is kept below. '+error.message;sDeskStart();}
    });
    if(found.copy_pending)button.textContent='Check copy';
  },'filled'):null;
  if(create)create.disabled=!access.actions.edit;
  sOpenSheet(title,sNode('p','',explanation),sNode('p','','Google account: '+found.account),
    sNode('p','',found.can_copy?'Create a review copy in this account’s My Drive. Future Blog Studio suggestions go to the copy; the original stays unchanged.':'Google does not allow this account to copy the Doc. Ask its owner to allow copying or grant edit access.'),
    found.selected_tab&&found.can_copy?sNode('p','quiet','The entire Doc is copied. Only your selected tab opens on the desk.'):null,
    found.can_copy?sNode('p','quiet','Check the copied text before starting. Existing comments and suggestions stay in the original.'):null,
    problem,sAdd(sNode('div','bar'),create,sButton('Cancel',sCloseSheet)));
  const owner=studio.sheet;
  // Reading temporarily disables the submit button, which can blur it before
  // the sheet opens. Cancel still returns keyboard focus to that action.
  owner.opener=$('studio-page').querySelector('[type=submit]')||owner.opener;
}
// A published post's preview: what was read, said in a line, then its text, read only.
function sPublishedShape(found){
  const s=found.summary||{},said=[s.words+(s.words===1?' word':' words'),s.headings+(s.headings===1?' heading':' headings'),s.links+(s.links===1?' link':' links'),s.images+(s.images===1?' image':' images')];
  if(s.images_without_alt)said.push(s.images_without_alt+(s.images_without_alt===1?' image has':' images have')+' no alt text');
  return said.join(' · ');
}
// A published post's images are never loaded here: each is shown as its file name and alt text.
function sPublishedText(markdown){return String(markdown||'').replace(/!\[([^\[\]\n]*)\]\(([^()\s]+)(?:\s+"[^"\n]*")?\)/g,(_,alt,src)=>'[Image: '+(src.split('/').pop().split('?')[0]||'image')+(alt.trim()?' — alt text: '+alt.trim():', no alt text')+']');}
function sPublishedPreview(found,label){
  const box=sNode('div','published-preview'),paper=sNode('article','paper doc');paper.setAttribute('aria-label',label);paper.tabIndex=-1;
  paper.append(window.StudioMarkdown?window.StudioMarkdown.render(sPublishedText(found.content)):sNode('p','',found.content));
  box.append(sNode('p','','Check the text below, then start.'),sNode('p','quiet',sPublishedShape(found)));
  if(found.read_from&&found.read_from.found_by)box.append(sNode('p','quiet','Read from the site’s content address, found by '+found.read_from.found_by+'.'));
  box.append(paper);
  return box;
}
function sPublishedFound(found){
  if(!found||found.status!=='preview'||typeof found.preview!=='string'||typeof found.expected!=='string'||typeof found.content!=='string'||typeof found.title!=='string')throw new Error('The page’s preview is incomplete. Read it again.');
  return found;
}
// A published page built by scripts: on a press, the assistant chosen under Settings works
// out where the page gets its text, and Blog Studio reads that address itself and checks it.
// It never runs by itself. find holds the link, the assistant's name and the job as shown.
function sFindTextFrom(error,link){const said=error?.reply||{};return error&&error.code==='no-text'?{url:typeof said.url==='string'&&said.url?said.url:link,assistant:typeof said.assistant==='string'&&said.assistant?said.assistant:'Your assistant',said:error.message,view:null,problem:'',node:null,timer:false}:null;}
function sFindText(find,{current,found}){const box=sNode('div','find-text');find.node=box;find.current=current;find.found=found;sFindTextDraw(find);if(find.view?.busy)sFindTextWatch(find);return box;}
function sFindTextDraw(find,focus=false){
  const box=find.node,view=find.view,who=find.assistant;if(!box)return;
  const parts=[],can=access.actions.edit;
  if(view&&view.busy){
    const line=sNode('p','desk-working-note',who+' is looking for where this page gets its text…');line.setAttribute('role','status');
    const stop=sButton('Stop',button=>busy(button,'Stopping…',async()=>{try{find.view=await api('published-find-text-stop',{id:view.id});}catch(error){find.problem=error.message;}sFindTextDraw(find,true);}));stop.disabled=!can;
    parts.push(line,sActivityNow(view.activity,{}),sNode('p','quiet','It reads the page’s head and the scripts it loads from this site, and runs none of them. Blog Studio then reads the address it finds and checks that it holds this post. This takes a minute or two.'),sAdd(sNode('div','bar'),stop));
  }else if(view&&view.status==='ready'){
    const line=sNode('p','desk-working-note','Found where this page gets its text. Reading the post…');line.setAttribute('role','status');parts.push(line);
  }else{
    const again=view&&['failed','cancelled'].includes(view.status);
    if(view&&view.status==='failed'){const said=sNode('p','problem',view.error+(view.advice?' '+view.advice:''));said.setAttribute('role','alert');parts.push(said);}
    else if(view&&view.status==='cancelled'){const said=sNode('p','quiet','Stopped. Nothing was kept.');said.setAttribute('role','status');parts.push(said);}
    else if(find.said){const said=sNode('p','problem',find.said);said.setAttribute('role','alert');parts.push(said);}  // Why the read found no text.
    if(find.problem){const said=sNode('p','problem',find.problem);said.setAttribute('role','alert');parts.push(said);find.problem='';}
    const ask=sButton(again?'Ask '+who+' again':'Ask '+who+' to find the post’s text',button=>sFindTextAsk(find,button));ask.disabled=!can;
    if(!again)parts.push(sNode('p','quiet',who+', your assistant, can work out where this page gets its text from its head and the scripts it loads, without running them. Blog Studio then reads that address itself and checks that it holds this post. It takes a minute or two. Or paste the post’s text instead.'));
    parts.push(sAdd(sNode('div','bar'),ask));
  }
  // Focus stays in the block when it is drawn again, on its button, for a keyboard user.
  const held=typeof document!=='undefined'&&document.activeElement&&box.contains(document.activeElement);
  box.replaceChildren(...parts.filter(Boolean));
  if(focus||held){const first=box.querySelector('button');if(first&&typeof first.focus==='function')first.focus();}
}
async function sFindTextAsk(find,button){
  await busy(button,'Asking…',async()=>{try{find.view=await api('published-find-text',{operation:operationId(),url:find.url});}catch(error){find.problem=error.message;}});
  if(!find.current())return;
  sFindTextDraw(find,true);if(find.view?.busy)sFindTextWatch(find);
}
function sFindTextWatch(find){
  if(find.timer)return;find.timer=true;
  setTimeout(async()=>{
    find.timer=false;if(!find.current()||!find.view)return;
    let shown;try{shown=await api('published-find-text?'+new URLSearchParams({id:find.view.id}));}catch(error){find.problem=error.message;find.view=null;sFindTextDraw(find);return;}
    if(!find.current())return;
    const changed=shown.status!==find.view.status;find.view=shown;
    if(shown.busy){sActivityUpdate(find.node,shown.activity,{});return sFindTextWatch(find);}  // Queued and working read the same.
    sFindTextDraw(find,changed);
    if(shown.status==='ready')await find.found(shown);  // Read again: from the address it found.
  },DESK_POLL);
}
// Read a published post by its link: one fetch on this press, shown before anything starts.
// A page with no text offers to ask the assistant where it gets its text (sFindText).
async function sDeskReadPublished(held,{start=false,read=null}={}){
  if(held.source==='collection')return sDeskReadCollection(held,{start,read});
  const turn=studio.turn;let found;
  try{found=sPublishedFound(await api('published-preview',{url:held.link.trim()}));}
  catch(error){if(turn===studio.turn)held.find=sFindTextFrom(error,held.link.trim());throw error;}
  if(turn!==studio.turn)return;
  held.preview=found;held.find=null;
  if(start){if(read)read();return sDeskGo(held);}
  await sDeskStart();sPublishedFocus();
}
// Read the page on its own button (or once its text was found): a refusal is said on the form.
async function sDeskReadLink(held){try{await sDeskReadPublished(held);}catch(error){held.problem=held.find?'':error.message;if(held.find)await sDeskFindShown(held);else sDeskStartAgain(held);}}
// A read that found no text: the form is drawn with the offer, and focus goes to its button.
async function sDeskFindShown(held){if(studio.screen==='desk-start'&&studio.deskStart===held){await sDeskStart();sFindTextFocus();}}
function sFindTextFocus(){const box=$('studio-page').querySelector('.find-text'),button=box&&box.querySelector('button');if(button&&typeof button.focus==='function')button.focus();}
// The link changed: an offer to find the old link's text goes.
function sFindTextGone(held){if(held.find?.node)held.find.node.hidden=true;held.find=null;}
async function sDeskReadCollection(held,{start=false,read=null}={}){
  if(held.collectionReading)return;held.collectionReading=true;
  const turn=studio.turn;
  try{const found=sPublishedFound(await api('published-preview',{item:held.collection.id,location:held.collection.location||'local'}));if(turn!==studio.turn)return;held.preview=found;held.collectionProblem='';}
  catch(error){held.collectionProblem=error.message;if(start)throw error;}
  finally{held.collectionReading=false;}
  if(start&&held.preview){if(read)read();return sDeskGo(held);}
  sDeskStartAgain(held);
}
// Check spelling and grammar's strength of human-sounding suggestions, or null for none.
function sDeskPolishOptions(held){return held.first_pass==='copyedit'?{humanize:held.humanizeOn?held.humanizeLevel:null,...(held.voiceOn?{voice_guide:held.voiceGuide}:{})}:{};}
async function sDeskGo(held){
  const turn=studio.turn;
  if(!await sDeskKeep(held))throw Error(sBlogIntake().problem||'Save this intake before starting.');
  // A draft takes a kind of post only to be reshaped to it (sDeskPolish keeps held.style so).
  const common={intake_revision:sBlogIntake().revision,operation:held.operation,style:held.have==='draft'?held.style:held.kind||'',tone:held.tone,sources:sDeskUploads(held.files),library:sDeskLibraryPicks(held.files),...sDeskKept(held.files),...(held.title.trim()?{title:held.title.trim()}:{}),...(held.geoReview?{geo_review:true}:{})};
  let made;
  if(held.have==='draft'){
    const settings={...common,first_pass:held.first_pass,...sDeskPolishOptions(held)};
    if(held.source==='saved')made=await api('desk-create',{...settings,article:held.article});
    else if(held.source==='upload')made=await api('desk-create',{...settings,source:held.uploaded.id});
    else if(held.source==='paste')made=await api('desk-create',{...settings,manuscript:held.manuscript});
    else if(held.source==='link'||held.source==='collection'){
      if(!held.preview)throw new Error('Read the page first.');
      made=await api('desk-create',{...settings,published:{preview:held.preview.preview,expected:held.preview.expected}});
    }
    else if(held.source==='file'){
      if(held.file.size>10*1024*1024)throw new Error('Choose a file up to 10 MiB.');
      const uploaded=await api('upload',{operation:held.upload,filename:held.file.name,title:held.title.trim()||held.file.name.replace(/\.[^.]+$/,''),content:await encodeImportFile(held.file),purpose:'manuscript',analyze:false});
      if(uploaded.state&&uploaded.state!=='ready')throw new Error('This file needs its text extracted before it can be edited. Paste the text instead.');
      made=await api('desk-create',{...settings,source:uploaded.source.id});
    }else{
      if(!held.preview)throw new Error('Read the Google Doc first.');
      const started=await api('google-start',{preview:held.preview.preview,expected:held.preview.expected,title:held.title.trim()||held.preview.title,confirmed:true});
      made=await api('desk-create',{...settings,title:undefined,article:started.id});
    }
  }else{
    if(held.sourceEditor&&(!held.sourceEditor.value||held.sourceEditor.busy))throw new Error('Research choices are still loading. Your sources are kept; try Start again when they are ready.');
    const primary=held.files.some(file=>file.state==='ready'&&file.role!=='inspiration');
    const sourceChoice=held.sourceEditor?.choice(primary);
    const wantsResearch=sourceChoice&&(held.researchOn||sourceChoice.web||sourceChoice.sites.length);
    if(wantsResearch&&!held.sourceEditor.valid(primary))throw new Error('Finish reading, remove or exclude unreadable sources before starting.');
    const research=wantsResearch?{research_inputs:held.sourceEditor.spec()}:!held.sourceEditor&&(held.searchSites||held.searchWeb)?{research_from:{sites:held.searchSites?sChosenSites(held.from):[],web:!!held.searchWeb}}:{};
    const writing={...common,way:held.have==='topic'?'topic':held.outlineWay,length:held.length||'style',...research,...(held.have==='topic'&&held.angleOp?{angles:held.angleOp}:{})};
    if(held.have==='topic')made=await api('desk-create',{...writing,point:held.point.trim(),...(held.audience.trim()?{audience:held.audience.trim()}:{})});
    else if(held.outlineFrom==='paste')made=await api('desk-create',{...writing,outline:held.outline});
    else{
      if(held.outlineFile.size>10*1024*1024)throw new Error('Choose a file up to 10 MiB.');
      const uploaded=await api('upload',{operation:held.upload,filename:held.outlineFile.name,title:held.title.trim()||held.outlineFile.name.replace(/\.[^.]+$/,''),content:await encodeImportFile(held.outlineFile),purpose:'manuscript',analyze:false});
      if(uploaded.state&&uploaded.state!=='ready')throw new Error('This file needs its text extracted first. Paste the outline instead.');
      made=await api('desk-create',{...writing,outline_source:uploaded.source.id});
    }
  }
  await sDeskConsumed(held,common.intake_revision);
  if(turn!==studio.turn)return;
  if(made.first_pass_problem)sToast('The first pass did not start: '+made.first_pass_problem);
  if(made.keep_problem)sToast(made.keep_problem);
  // Check spelling and grammar lands in Review mode; every other start on the full desk.
  // Review for AI search opens Finishing at the GEO review, where its proposals will wait.
  studio.desk={id:made.id,view:made,session:operationId(),...(held.have==='draft'&&held.first_pass==='geo'&&!made.first_pass_problem?{openTool:'geo'}:{})};await sRoute('desk',made.id,held.have==='draft'&&held.first_pass==='copyedit'?'review':null);
  return made;
}

// Add a source on the desk: the same files card, saved with this blog; a kept one goes to
// the team library when it is added.
function sDeskSourcesSheet(held){
  const adding=held.adding||(held.adding={files:[],role:'material',keep:false,style:held.view.style?.style_id||''});
  const problem=sNode('p','sheet-error',adding.problem||'');problem.setAttribute('role','alert');delete adding.problem;
  let done;
  const files=sFilesCard(adding,problem,()=>sDeskSourcesSheet(held),locked=>{if(done)done.disabled=locked||!sDeskCan(held);},{keepWhen:'Ticked ones go to the team library when you add them.',empty:'No sources yet. Later rewrites will read what you add.'});
  done=sButton('Add to this draft',async button=>{
    const ready=adding.files.filter(file=>file.state==='ready');if(!ready.length){problem.textContent='Add a file, a link, a Google Doc or a post from the team or Document Library with text first.';return;}
    await busy(button,'Adding…',async()=>{try{await sDeskFlush(held);const before=held.view;held.view=await api('desk-sources',{id:held.id,sources:sDeskUploads(ready),library:sDeskLibraryPicks(ready),...sDeskKept(ready)});held.adding=null;sCloseSheet();sToast(ready.length===1?'Added. Later rewrites read it.':'Added. Later rewrites read them.');sDeskRefresh(held,before);}catch(error){problem.textContent=error.message;}});
  },'filled');
  done.disabled=!sDeskCan(held);
  sOpenSheet('Add a source',sNode('p','quiet','Later rewrites read it; nothing already written changes.'),files,problem,sAdd(sNode('div','bar'),done,sButton('Cancel',sCloseSheet)));
}

// The desk.
async function sDesk(ident){
  const turn=studio.turn;
  const view=await api('desk?id='+encodeURIComponent(ident));if(turn!==studio.turn)return;
  const held=studio.desk&&studio.desk.id===ident?studio.desk:(studio.desk={id:ident,session:operationId()});
  // Coming back reads the desk afresh: nothing typed before leaving is saved over it.
  for(const pending of Object.values(held.pending||{}))if(pending?.timer&&typeof clearTimeout==='function')clearTimeout(pending.timer);
  const query=new URLSearchParams(location.search),reading=query.get('view');
  if(['read','edit','full'].includes(reading))held.reading=reading;
  if(query.get('part'))held.activePart=query.get('part');
  held.view=view;held.pending={};held.stale=false;held.outline=null;if(held.review)held.review.editing=null;
  // Explicit manuscript links win. A fresh visit to a saved review resumes that
  // review; returning within a session keeps the view the author chose.
  const resumeReview=held.mode==='review'||(!held.reading&&sDeskHasReview(view));
  held.mode=studio.stage==='review'||(!['read','edit','full'].includes(reading)&&resumeReview)?'review':null;
  if(sDeskStarting(view))return sDeskProgress(held);
  if(!held.tab)held.tab=(view.start?.open==='outline'||view.conversation_scope==='outline')&&!sDeskHasText(view)?'outline':'draft';
  sDeskRender(held);
  if(held.openTool){const tool=held.openTool;delete held.openTool;sDeskFinishOpen(held,tool);}
  sDeskWatch(held);
}
function sDeskStarting(view){return DESK_KIT.starting(view);}
function sDeskHasText(view){return !!view.opening||(view.sections||[]).some(section=>section.text);}
function sDeskHasReview(view){return !!(view.review||view.finishing?.copyedit||view.jobs?.some(job=>job.kind==='finish-copyedit'));}

// A start under way: nothing is needed from the person; the draft opens on its own.
function sDeskElapsed(start){return DESK_KIT.elapsed(start);}
function sDeskSpent(start){return DESK_KIT.spent(start);}
function sDeskClock(start){return DESK_KIT.clock(start);}
// About how long is left, from recent runs of each step here; an overrun step says so.
function sDeskEstimate(start,what){return DESK_KIT.estimate(start,what);}
function sDeskProgress(held){
  const view=held.view,start=view.start,p=DESK_KIT.progress(held,start.open==='outline'?'The outline':'The draft');
  // Driven on another computer, or by nobody: the start says so, and offers to take it.
  sFrame(view.title,[sDeskTeam(view),p.stop],sDeskDriverWords(view)||p.above,()=>sRoute('blogs'));
  // What the assistant is doing: in the research panel while research runs, else on its own.
  const of={id:held.id},researching=start.research_progress&&typeof StudioResearch!=='undefined';
  sPage(sDeskBench(held),p.lede,sDeskElsewhere(view),p.stopped,...(researching?[StudioResearch.progress(start.research_progress,{workers:view.activity||[],lines:sActivityLoad(of)})]:[sActivityNow(view.activity,of)]),p.card,sActivityLog(of));
  if(!start.problem)sDeskFollowStart(held);
}
// A stopped start: the ways on a run has. More time for a step out of time, no research for
// a research step that stopped, Status and what the assistant said for one that failed,
// Retry always, and Delete this start.
function sDeskStopped(held){
  const view=held.view,start=view.start,can=sDeskCan(held);
  const again=extra=>async button=>{await busy(button,'Starting…',async()=>{try{held.view=await api('desk-retry',{id:held.id,...extra});sDeskProgress(held);}catch(error){notice(error.message,true);}});};
  const more=start.reason==='time-limit'&&start.more?sButton('Try again with more time',again({seconds:start.more}),'filled'):null;
  const retry=sButton('Retry',again({}),more?'':'filled');
  const skip=start.step==='research'?sButton('Continue without research',()=>sDeskSkipResearch(held)):null;
  const remove=sButton('Delete this start',()=>sDeleteSheet({id:held.id,title:view.title,expected:view.expected,team:view.team,status:start.status}));
  for(const button of [more,retry,skip,remove])if(button)button.disabled=!can;
  return sAdd(sNode('div','decision-notice desk-problem'),sAdd(sNode('div',''),sNode('p','',start.problem),more?sNode('p','quiet',sTimeWords({seconds:start.seconds})):null,...sCliFailure({status:'failed',reason:start.reason,said:start.said,error:start.problem})),sAdd(sNode('div','bar'),more,retry,skip,remove));
}
function sDeskSkipResearch(held){
  const problem=sNode('p','sheet-error');problem.setAttribute('role','alert');
  const go=sButton('Continue without research',async button=>{await busy(button,'Saving…',async()=>{try{held.view=await api('desk-retry',{id:held.id,skip_research:true});sCloseSheet();sToast('Continuing without research.');sDeskProgress(held);}catch(error){problem.textContent=error.message;}});},'filled');
  sOpenSheet('Continue without research?',sNode('p','','The research step leaves this start, and the writing goes on from your point and sources. It gets no research findings, and research cannot be added back to this start.'),problem,sAdd(sNode('div','bar'),go,sButton('Cancel',sCloseSheet)));
}
function sDeskFollowStart(held){return DESK_KIT.followStart(held);}
function sDeskCurrent(held){return studio.screen==='desk'&&studio.desk===held;}
// Whether the job under way changes this part: its own section, or every section.
function sDeskWorkingIn(view,part){return DESK_KIT.workingIn(view,part);}
function sDeskWorking(held,part){return DESK_KIT.workingIn(held.view,part);}
function sDeskStatusWords(held){return DESK_KIT.statusWords(held);}
function sDeskTabs(held){return sChoice('Work on',[['draft','Draft'],['outline','Outline']],held,'tab',async()=>{await sDeskFlush(held);await sDeskOutlineFlush(held);held.outline=null;sDeskRender(held);});}
// In a team workspace a blog has one driver. While another computer drives it, or nobody
// does, the desk is read only and the toolbar offers Take over or Take this blog.
function sDeskCan(held){return sCanEdit(held?.view||{});}
function sDeskDriverWords(view){if(!view.team||view.driver?.here)return '';return view.driver?view.driver.name+' · driving on another computer':'Nobody is running this blog';}
// Hand over, Take over or Take this blog, in a team workspace; on the desk and on a start's
// progress screen alike. Each confirms against the desk's version.
function sDeskTeam(view){
  if(!view.team)return null;
  const action=view.driver?.here?'handover':view.driver?'takeover':'take';
  const team=sButton({handover:'Hand over',takeover:'Take over',take:'Take this blog'}[action],()=>sTeamDecision(view,action,'desk'),action==='handover'?'':'filled');
  team.disabled=!access.actions.edit;return team;
}
function sDeskElsewhere(view){return view.elsewhere?sNode('p','decision-notice desk-driver',view.elsewhere):null;}
// The blog's own actions, on the desk's toolbar and on Review mode's: Copy, Download, its
// Google Doc and Mark as published.
function sDeskShareActions(held){
  const view=held.view,editable=sDeskCan(held);
  const copy=sButton('Copy',async()=>{if(typeof navigator==='undefined'||!navigator.clipboard?.writeText)throw new Error('Download the draft and copy it from there.');if(held.mode==='review')await sReviewFlush(held);const found=await sDeskMarkdown(held);await navigator.clipboard.writeText(found.markdown);sToast(deskWithout('Markdown copied',found.missing));});
  const download=sButton('Download',async()=>{if(held.mode==='review')await sReviewFlush(held);const found=await sDeskMarkdown(held);await sDownload({content:found.markdown,name:'DRAFT.md'});if(found.missing.length)sToast(deskWithout('Downloaded',found.missing));});
  const publish=sButton(view.publication?'Published':'Mark as published',()=>sDeskPublish(held));publish.disabled=!editable;
  return [copy,download,...sDeskGoogleActions(held,true),publish];
}
// Share: every way the draft leaves the desk, behind one button, so the toolbar keeps a
// single filled action. On a phone the toolbar folds itself, so the items go in as they are.
function sDeskShareMenu(held){
  const items=sDeskShareActions(held);
  if(sNarrow())return items;
  // Sending changes to a linked Google Doc stays a visible action, outside the menu.
  const send=items.find(item=>item.textContent==='Review changes to send'),rest=items.filter(item=>item!==send);
  if(send)send.className='button';
  const menu=sNode('details','menu desk-share-menu');
  for(const item of rest)item.className='menu-item';
  // A choice closes the menu it was made in.
  const list=sAdd(sNode('div','menu-list'),...rest);list.addEventListener('click',()=>{menu.open=false;});
  return [send,sAdd(menu,sNode('summary','button','Share'),list)].filter(Boolean);
}
// Outgoing review is a visible action, including on phones. The Google Doc menu
// holds opening the Doc and bringing incoming accepted text; neither sends edits.
function sDeskGoogleActions(held,flat=false){
  const view=held.view,editable=sDeskCan(held);
  if(!view.google?.url){const make=sButton('Make a Google Doc',()=>sDeskMakeDoc(held));make.disabled=!editable;return [make];}
  if(!view.google_suggestions){const open=link(view.google.url,'Google Doc ↗');open.className='button';return [open];}
  // A choice closes the menu it was made in.
  const menu=sNode('details','menu desk-google-menu'),shut=go=>()=>{menu.open=false;return go(held);};
  const open=link(view.google.url,'Open the Google Doc ↗'),check=sButton('Review changes to send',()=>sDeskGoogleSend(held),'filled'),bring=sButton('Bring accepted changes',shut(sDeskGoogleBring));
  // Verify the last send: offered once something has gone, and a reading only.
  const last=view.google_state?.last?.plan,verify=last?sButton('Verify the last send',shut(()=>sDeskGoogleVerifyAgain(held,last))):null;
  check.disabled=bring.disabled=!editable;
  if(flat||sNarrow())return [check,open,bring,verify].filter(Boolean);
  for(const item of [open,bring,verify])if(item)item.className='menu-item';
  return [check,sAdd(menu,sNode('summary','button','Google Doc'),sAdd(sNode('div','menu-list'),...[open,bring,verify].filter(Boolean)))];
}
// The Doc as the desk last knew it, said in the toolbar: what waits there, when the desk last
// sent, and changes not sent yet. Read on this computer; Google is read only when asked.
function sDeskDocWords(view){const g=view.google_state;if(!g)return '';const said=[];if(g.waiting)said.push('Doc: '+g.waiting+' waiting');if(g.last)said.push('last sent '+sDeskWhen(g.last.at));if(g.unsent)said.push('Unsent desk changes');return said.join(' · ');}
function sDeskWhen(at){const when=new Date(at||'');if(isNaN(when.getTime()))return '';const time=when.toLocaleTimeString('en-US',{hour:'numeric',minute:'2-digit'});return when.toDateString()===new Date().toDateString()?time:when.toLocaleDateString('en-US',{month:'short',day:'numeric'})+', '+time;}
// A Google request that took too long to answer (the phone link's 504), said plainly.
function sDeskSlow(error,again){return error?.status===504||/took too long|timed? ?out/i.test(error?.message||'')?again:error?.message;}
// The receipt of a send: how many went, when, and what comes next.
function sDeskSentWords(plan,result){
  if(!['verified-pending','verified-comments'].includes(result?.status))return 'The result is not yet verified. Check delivery before trying anything else.';
  const asComments=result.status==='verified-comments',edits=plan.suggestions??plan.count??0,n=asComments?0:edits,m=asComments?edits+(plan.comments||0):plan.comments||0,parts=[];
  if(n)parts.push(n+(n===1?' suggestion':' suggestions'));if(m)parts.push(m+(m===1?' comment':' comments'));
  return 'Sent '+(parts.join(' and ')||'the changes')+' at '+sDeskWhen(new Date().toISOString())+'.'+(n?' When the owner has decided them, choose Bring accepted changes.':' The Doc’s owner makes each change by hand.');
}
// A send ends with the Doc read back, and only then counts as sent. What that readback
// found is said in words beside the receipt, so "sent" is never taken on trust: when the Doc
// was read, how many suggestions are pending in it and how many of the comments were found.
function sDeskVerifiedWords(result){
  if(!['verified-pending','verified-comments'].includes(result?.status))return '';
  const when=sDeskWhen(result.checked_at),pending=result.review_state?.pending,notes=Array.isArray(result.comments)?result.comments:[],found=notes.filter(row=>row&&row.verified).length,parts=[];
  if(Number.isInteger(pending)&&pending>0)parts.push(pending+(pending===1?' suggestion is':' suggestions are')+' pending in it');
  if(notes.length)parts.push(found+' of '+notes.length+(notes.length===1?' comment was':' comments were')+' found in it');
  return 'Verified by reading the Doc back'+(when?' at '+when:'')+(parts.length?': '+parts.join(', and ')+'.':': it holds what was sent.');
}
// Verify again: the Doc read once more for the plan that went last. Nothing is sent, nothing
// on the desk changes and the record of the send stays as it was. A Doc whose owner has since
// accepted, rejected or edited no longer reads back as sent, and that is said as what it is.
function sDeskCheckedWords(result){
  const when=sDeskWhen(result.checked_at),at=when?' at '+when:'',state=result.review_state,notes=Array.isArray(result.comments)?result.comments:[],found=notes.filter(row=>row&&row.verified).length;
  const parts=[];
  if(result.as_sent){
    if(Number.isInteger(state?.pending)&&state.pending>0)parts.push(state.pending+(state.pending===1?' suggestion is':' suggestions are')+' pending in it');
    if(notes.length)parts.push(found+' of '+notes.length+(notes.length===1?' comment was':' comments were')+' found in it');
    return 'Read again'+at+': the Doc still holds what was sent'+(parts.length?'. '+parts.join(', and ').replace(/^./,c=>c.toUpperCase())+'.':'.');
  }
  if(state&&[state.pending,state.accepted,state.rejected].every(Number.isInteger))parts.push('It now holds '+state.pending+' pending, '+state.accepted+' accepted and '+state.rejected+' rejected '+(state.pending+state.accepted+state.rejected===1?'suggestion':'suggestions')+'.');
  if(notes.length)parts.push(found+' of '+notes.length+(notes.length===1?' comment is':' comments are')+' still there.');
  return 'Read again'+at+': the Doc no longer matches what was sent, as happens once its owner accepts, rejects or edits. '+parts.join(' ')+(parts.length?' ':'')+'Nothing was sent again. Bring accepted changes brings the accepted text to the desk.';
}
async function sDeskGoogleVerifyAgain(held,token){
  const problem=sNode('p','sheet-error'),kept=studio.sheet?.opener||null;problem.setAttribute('role','alert');
  sOpenSheet('Verify the last send',sNode('p','','Reading the Google Doc. Nothing is sent, and nothing on the desk changes.'),problem,sAdd(sNode('div','bar'),sButton('Cancel',sCloseSheet)));
  const owner=studio.sheet;if(kept)owner.opener=kept;const opener=owner.opener;let result;
  try{result=await api('desk-google-check',{id:held.id,plan:token});}catch(error){if(studio.sheet===owner)problem.textContent=sDeskSlow(error,'Reading the Google Doc took too long. Try again; nothing was sent.');return;}
  if(studio.sheet!==owner)return;
  const doc=held.view.google?.url?sAdd(sNode('p',''),link(held.view.google.url,'Open the Google Doc ↗')):null;
  sOpenSheet(result.as_sent?'Still in the Google Doc':'The Doc has changed since',sStatus(result.as_sent?'done':'current',sDeskCheckedWords(result)),doc,sAdd(sNode('div','bar'),sButton('Close',sCloseSheet)));studio.sheet.opener=opener;
}
// The button for it, wherever the last send is shown, while the desk knows which plan went.
function sDeskVerifyAgain(held){const token=held.view.google_state?.last?.plan;return token?sButton('Verify in the Doc again',()=>sDeskGoogleVerifyAgain(held,token)):null;}
function sDeskVerifiedLine(words){if(!words)return null;const line=sNode('p','quiet google-verified',words);line.setAttribute('role','status');return line;}
// The desk read again after Google work, so its toolbar says what the Doc holds now.
async function sDeskReread(held){if(!sDeskCurrent(held))return;const before=held.view;held.view=await api('desk?id='+encodeURIComponent(held.id));sDeskRefresh(held,before);}
// Check what would be sent, then Send: two steps from the toolbar, on a sheet, nothing sent
// before Send.
async function sDeskGoogleSend(held){
  const problem=sNode('p','sheet-error');problem.setAttribute('role','alert');
  sOpenSheet('Send to the Google Doc',sNode('p','','Checking what the desk would send. Nothing is sent until you choose Send.'),problem,sAdd(sNode('div','bar'),sButton('Cancel',sCloseSheet)));
  const owner=studio.sheet,opener=owner.opener;let plan;
  try{if(held.mode==='review')await sReviewFlush(held);await sDeskFlush(held);plan=await api('desk-google-plan',{id:held.id,mode:'auto'});}catch(error){if(studio.sheet===owner)problem.textContent=sDeskSlow(error,'Reading the Google Doc took too long. Check again; nothing was sent.');return;}
  if(studio.sheet!==owner)return;
  const changes=sNode('ul','look');for(const item of plan.proposals||[])changes.append(sNode('li','',sDeskGoogleItem(item)));
  const deliver=async button=>{await busy(button,'Sending…',async()=>{try{
    const result=await api('desk-google-send',{id:held.id,plan:plan.plan,confirmed:true}),done=['verified-pending','verified-comments'].includes(result.status);
    const again=done?null:sButton('Check delivery',deliver,'filled');
    sOpenSheet(done?'Sent to the Google Doc':'Check delivery',sStatus(done?'done':'late',sDeskSentWords(plan,result)),sDeskVerifiedLine(sDeskVerifiedWords(result)),sAdd(sNode('div','bar'),again,done?sButton('Verify in the Doc again',()=>sDeskGoogleVerifyAgain(held,plan.plan)):null,sButton('Close',sCloseSheet)));studio.sheet.opener=opener;
    if(done)await sDeskReread(held);
  }catch(error){problem.textContent=error.message;}});};
  const send=sButton('Send to Google Doc',deliver,'filled');send.disabled=!sDeskCan(held);
  sOpenSheet('Send to the Google Doc',sNode('p','',sDeskGoogleSaid(plan)),disclosure('What would be sent',changes),problem,sAdd(sNode('div','bar'),send,sButton('Cancel',sCloseSheet)));studio.sheet.opener=opener;
}
// Bring accepted changes from the Doc: read its accepted text, say which parts change, then
// bring them, each keeping the desk's text first in History. Nothing is written to Google.
async function sDeskGoogleBring(held){
  const problem=sNode('p','sheet-error');problem.setAttribute('role','alert');
  sOpenSheet('Bring accepted changes from the Doc',sNode('p','','Reading the Google Doc’s accepted text. Nothing is written to Google, and nothing on the desk changes until you choose to bring it.'),problem,sAdd(sNode('div','bar'),sButton('Cancel',sCloseSheet)));
  const owner=studio.sheet,opener=owner.opener;let found;
  try{if(held.mode==='review')await sReviewFlush(held);await sDeskFlush(held);found=await api('desk-google-compare',{id:held.id});}catch(error){if(studio.sheet===owner)problem.textContent=sDeskSlow(error,'Reading the Google Doc took too long. Check again; nothing on the desk changed.');return;}
  if(studio.sheet!==owner)return;
  const list=sNode('ul','rows desk-brought');
  for(const change of found.changes){const what=change.kind==='added'?'Added in the Doc':change.kind==='removed'?'Removed in the Doc':change.renamed?'Renamed from “'+change.renamed+'” and changed in the Doc':'Changed in the Doc';list.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('span','row-title',change.name),sNode('span','row-says',what),disclosure('Compare',deskSides(change.before,change.after)))));}
  const parts=found.changes.length;
  const go=found.ready?sButton(parts===1?'Bring 1 part to the desk':'Bring '+parts+' parts to the desk',async button=>{await busy(button,'Bringing…',async()=>{try{
    const before=held.view;held.view=await api('desk-google-take',{id:held.id,preview:found.preview,confirmed:true});sCloseSheet();
    const n=held.view.brought?.parts?.length??parts;sToast((n===1?'Brought 1 part':'Brought '+n+' parts')+' from the Google Doc. The desk’s earlier text is in History.');sDeskRefresh(held,before);
  }catch(error){problem.textContent=sDeskSlow(error,'This took too long to answer. Check again: choose Bring again, which never brings anything twice, and the result is kept.');}});},'filled'):null;
  if(go)go.disabled=!sDeskCan(held);
  sOpenSheet('Bring accepted changes from the Doc',sNode('p','',found.ready?'These parts take the Doc’s accepted text. Each keeps the desk’s text first in History, as Before Google’s accepted text. Nothing is written to Google.':found.said),parts?list:null,problem,sAdd(sNode('div','bar'),go,sButton(go?'Cancel':'Close',sCloseSheet)));studio.sheet.opener=opener;
}
function sDeskToolbar(held){
  const view=held.view;
  const finishing=sButton('Finishing',()=>held.finish?sDeskFinishClose(held):sDeskFinishOpen(held),'filled');finishing.setAttribute('aria-pressed',String(!!held.finish));
  const review=held.review||sDeskHasReview(view)?sButton('Review fixes',async()=>{await sDeskFlush(held);await sDeskOutlineFlush(held);sReviewEnter(held);sDeskRender(held);sDeskWatch(held);}):null;
  const stop=held.view.working?sButton('Stop',async button=>{await busy(button,'Stopping…',async()=>{const before=held.view;held.view=await api('desk-stop',{id:held.id,job:held.view.working.id});sDeskRefresh(held,before);});}):null;
  const team=sDeskTeam(view);
  sFrame(view.title,sFold([team,stop,review,...sDeskShareMenu(held),finishing]),held.view.working?sDeskStatusWords(held):sDeskDriverWords(view)||sDeskDocWords(view)||'On the desk',()=>sRoute('blogs'));
}
// Reading is the default; editing mounts only the selected part. The full desk remains
// available for experienced authors. URL choices contain navigation only, never text.
function sDeskParts(held){const parts=['title','opening',...held.view.sections.map(section=>section.id)];if(!parts.includes(held.activePart))held.activePart='opening';return held.reading==='edit'?[held.activePart]:parts;}
function sDeskViewUrl(held){if(studio.screen!=='desk')return;const query=new URLSearchParams(location.search);query.set('screen','desk');query.set('id',held.id);query.set('view',held.reading||'read');query.set('part',held.activePart||'opening');history.replaceState(null,'',location.pathname+'?'+query);}
async function sDeskChoose(held,reading,part=held.activePart){
  const previousReading=held.shownReading||held.reading,previousPart=held.shownPart||held.activePart;
  await sDeskFlush(held);await sDeskOutlineFlush(held);
  if(held.stale||Object.keys(held.pending||{}).length){held.reading=previousReading;held.activePart=previousPart;if(!held.stale)held.saved=held.status?.textContent||'Your text has not saved yet. Try again before changing views.';sDeskRender(held);held.cards?.[previousPart]?.deskInput?.focus();return;}
  held.selection=null;held.reading=reading;held.activePart=part||'opening';sDeskViewUrl(held);sDeskRender(held);
  const selected=held.cards?.[held.activePart];if(reading==='read')selected?.scrollIntoView?.({block:'start',behavior:'instant'});
  else selected?.deskInput?.focus();
}
// Finishing opens from the toolbar only: Polish goes to Review mode, the one place fixes are
// accepted or rejected in the text. On a phone the view, the buttons and the page's sentence
// fold into one bar beside Go to section, so the title and the first paragraph come first.
function sDeskReadingControls(held,lede,status){
  const choices=sChoice('Manuscript view',[['read','Read'],['edit','Edit section'],['full','Edit everything']],held,'reading',value=>sDeskChoose(held,value));
  const selected=['read','edit','full'].indexOf(held.reading);
  Drafting.cultTabs(choices.querySelector('.segmented'),selected,held.cultReading ?? selected);
  held.cultReading=selected;
  // What the chosen view is for, said under the switch, so its three names need no guessing.
  const hint=sNode('p','quiet field-hint',{read:'Read: the whole post as your reader sees it.',edit:'Edit section: one section at a time, in an editor.',full:'Edit everything: every section on one page, each with a box to ask your assistant for a rewrite.'}[held.reading]||'');
  const picker=sField('desk-part-picker','Go to section',held,'activePart',{options:[['title','Title'],['opening','Opening'],...held.view.sections.map(section=>[section.id,deskHeading(section.heading)])],changed:value=>sDeskChoose(held,held.reading,value)});
  const actions=sAdd(sNode('div','bar'),sButton('Sources',()=>sDeskSourcesSheet(held)),sButton('Outline',async()=>{await sDeskFlush(held);held.tab='outline';sDeskRender(held);}));
  // One row of controls, with what the chosen view is for and the save line under it.
  if(!sNarrow())return sAdd(sNode('div','desk-reading-controls'),choices,picker,actions,sAdd(sNode('div','desk-view-foot'),hint,status));
  choices.append(hint);
  const fold=sNode('details','desk-tools-fold');fold.open=!!held.toolsOpen;fold.addEventListener('toggle',()=>{held.toolsOpen=fold.open;});
  fold.append(sNode('summary','button','View and tools'),sAdd(sNode('div','desk-tools-list'),lede,choices,actions));
  // The save line stays in reach, empty until there is something to say.
  return sAdd(sNode('div','desk-reading-controls desk-compact'),picker,Drafting.cultExpandable(fold),status);
}
function sDeskReviewQueue(held){
  // Humanize's located rewrites open Review mode, as Copy edit's fixes do: one place to accept or reject them.
  const rows=[];for(const tool of DESK_TOOLS){const open=(held.view.finishing?.[tool.key]?.items||[]).filter(item=>item.state==='open'),n=open.length;if(!n)continue;rows.push(sButton(tool.name+' · '+n+' to review',()=>tool.key==='humanize'&&open.some(item=>item.present&&'after' in item)?sReviewHuman(held):sDeskFinishOpen(held,tool.key)));}
  if(!rows.length)return null;
  return sAdd(sNode('section','desk-suggestion-summary'),sNode('p','quiet','Optional suggestions to review'),sAdd(sNode('div','bar'),...rows));
}
function sDeskReadPart(held,part){
  const title=part==='title'?'Title':part==='opening'?'Opening':deskHeading(held.view.sections.find(row=>row.id===part)?.heading||''),text=held.pending?.[part]?.text??deskTextOf(held.view,part);
  const card=sNode('section','desk-part desk-reading-part');card.dataset.part=part;card.setAttribute('aria-label',title);card.tabIndex=-1;
  const edit=sButton('Edit '+title,()=>sDeskChoose(held,'edit',part));
  const versions=held.view.versions?.[part]||0,history=sButton(versions?'History ('+versions+')':'History',()=>sDeskHistory(held,part));history.disabled=!versions;
  card.append(sAdd(sNode('div','desk-part-head'),sNode('h2',part==='title'?'editorial-title':'card-title',part==='title'?(text||'Untitled'):title),sAdd(sNode('div','bar'),edit,versions?history:null)));
  if(part!=='title'){const body=sNode('div','doc');body.append(window.StudioMarkdown?window.StudioMarkdown.render(text):sNode('p','',text||'No text yet.'));card.append(body);}
  const thumbs=part==='title'?null:sDeskThumbs(held,part);if(thumbs)card.append(thumbs);
  const comments=sDeskComments(held,part);if(comments)card.append(comments);
  if(sDeskWorking(held,part))card.append(sNode('p','quiet','Working on this part…'));
  return card;
}
// The head of a blog's workbench: a line of light, the one arc every studio shares, and the
// one thing that waits for the person. The draft and its side panel are the workbench itself.
// Finishing sits beside the draft on the desk, never in Review mode: opened from there, it
// leaves Review first. With no tool named it opens the list, or stays as it is when open.
async function sDeskFinishFrom(held,tool=null){
  if(held.mode==='review')await sReviewLeave(held);
  if(held.stale||!sDeskCurrent(held))return;
  if(held.finish)return tool?sDeskFinishTool(held,tool):undefined;
  return sDeskFinishOpen(held,tool);
}
// The GEO review runs apart from the fixes in the text and its proposals wait in Finishing,
// so the desk and Review mode both say where it stands and open it from here.
function sDeskGeoPointer(held){
  const geo=held.view.geo_review;if(!geo||!geo.status||geo.status==='none')return null;
  const n=geo.open||0,waits=geo.status==='done'&&n>0;
  const said={working:'GEO review: reading the post now. Its proposals will wait in Finishing.',
    done:n?'GEO review: '+n+(n===1?' proposal waits':' proposals wait')+' for you in Finishing, apart from the fixes in your text.':'GEO review: done, with nothing left to review.',
    stale:'GEO review: out of date, because the post changed since it ran.',
    waiting:geo.waiting==='draft'?'GEO review: it runs once the full draft is written.':geo.waiting==='review'?'GEO review: it runs once you have accepted or rejected the fixes in your text.':'GEO review: it runs when the change under way ends.',
    'not-run':'GEO review: asked for, and not run yet.'}[geo.status];
  if(!said)return null;
  const line=sNode('p','geo-pointer-says',said);line.setAttribute('role','status');
  const row=sAdd(sNode('div','geo-pointer'+(waits?' geo-pointer-waits':'')),line);
  if(waits)row.append(sButton('Show GEO proposals',()=>sDeskFinishFrom(held,'geo')));
  else if(geo.status==='stale'||geo.status==='not-run')row.append(sButton('Go to GEO review',()=>sDeskFinishFrom(held,'publish')));
  if(geo.problem)row.append(sNode('p','problem','The last GEO review did not finish: '+geo.problem));
  return row;
}
function sDeskBench(held){
  if(typeof StudioShell==='undefined')return null;
  const view=held.view,start=view.start&&!sDeskHasText(view)?view.start:null,working=!!(view.working||start&&!start.problem);
  const hasText=sDeskHasText(view),finished=!!view.finished;
  // Reading and polishing the draft is still Make; Ship is Finishing and what follows it.
  const at=start?(start.open==='outline'?1:2):!hasText?1:finished||held.finish?3:2;
  const stopped=!!(start&&start.problem);
  // In Review mode the move is the fixes still to decide, counted as the page counts them.
  const reviewing=held.mode==='review'&&held.review&&!view.working?sReviewState(held):null;
  const fixes=reviewing?reviewing.pending.length:0;
  // Nothing checked yet: the move is the check itself, not Finishing, which comes after it.
  const unchecked=!!reviewing&&!reviewing.any&&!reviewing.failed.length;
  const move=stopped?{title:'It stopped and needs you',text:'See what happened below, then choose how to go on.'}
    :working||finished?null
    :!hasText?{title:'Write the draft from your outline',text:'Shape the outline, then write the draft or one section at a time.'}
    :fixes?{title:fixes===1?'1 fix to review in your text':fixes+' fixes to review in your text',text:'Accept or reject each one where it is marked. Nothing changes until you do.'}
    :unchecked?{title:'Check your draft',text:'Start the check here, or choose what it covers below first. Nothing changes until you accept a fix.',
      action:sDeskCan(held)?{label:'Check spelling and grammar',run:()=>{const go=held.review.head&&sReviewFind(held.review.head,'check');if(go)go.click();}}:null}
    :sDeskCan(held)?{title:'Review your draft',text:'Finishing checks it before you publish. Nothing changes until you accept.',action:{label:'Open Finishing',run:()=>sDeskFinishFrom(held)}}:null;
  const head=sNode('div','workbench-head');head.dataset.key='workbench-head';
  // What is under way, in the words its own screen uses: a check in review mode, or the job.
  const check=held.mode==='review'&&['finish-copyedit','finish-humanize'].includes(view.working?.kind);
  const doing=(check?(view.working.kind==='finish-humanize'?REVIEW_HUMAN:REVIEW_CHECKING):sDeskStatusWords(held)||'').replace(/…$/,'');
  const busyCard=working?{working:true,title:doing||'Working on it',text:'Nothing for you to do. '+(check?'Each fix is marked in the text when the check finishes. Read or edit meanwhile.':hasText?'Read or edit meanwhile.':'It opens here as it is written.')}:null;
  head.append(StudioShell.arc({at,yours:!!move,finished,note:working?(doing?doing+'…':''):''},'Where this blog is'),
    move?StudioShell.move(move):busyCard?StudioShell.move(busyCard):StudioShell.move({calm:true,title:finished?'Published':'Nothing is yours right now'}));
  // With a draft to read and nothing but the standing next step, the band is one quiet row
  // and the writing starts higher.
  const quiet=(hasText&&!stopped&&!working&&!fixes)||check;  // a check has its own status box
  const bench=sNode('div','workbench-top'+(quiet?' workbench-quiet':''));bench.append(...[StudioShell.pulse(move?'yours':working?'working':'still'),head,sDeskGeoPointer(held)].filter(Boolean));
  return bench;
}
function sDeskRender(held){
  if(held.mode==='review')return sDeskReview(held);
  const view=held.view;held.reading=held.reading||'read';sDeskParts(held);held.shownReading=held.reading;held.shownPart=held.activePart;sDeskToolbar(held);held.layout=sDeskLayout();
  const status=sNode('p','quiet desk-save-state');status.setAttribute('role','status');status.setAttribute('aria-live','polite');held.status=status;
  const narrow=sNarrow()&&held.tab!=='outline';
  if(held.stale)sDeskStale(held);else status.textContent=held.saved||(narrow?'':'Changes save as you type.');
  const column=sNode('div','desk-column'+(held.tab!=='outline'&&held.reading==='read'?' paper desk-reading-document':''));held.tab=held.tab||'draft';held.shownTab=held.tab;
  held.problemSlot=sNode('div','desk-problem-slot');const problem=sDeskProblem(held);if(problem)held.problemSlot.append(problem);
  held.cards={};
  held.column=column;held.outlineStale=false;
  if(held.tab==='outline'){held.wholeCard=null;held.wholeGo=null;column.append(held.problemSlot,...[sActivityNow(view.activity,{id:held.id})].filter(Boolean),...sDeskOutline(held));column.addEventListener('focusout',()=>setTimeout(()=>{if(held.outlineStale&&held.column===column&&!held.outlineTimer&&!sDeskTyping(column)&&sDeskCurrent(held)){held.outline=null;sDeskRender(held);}},0));}
  else{
    held.wholeCard=held.reading==='read'?null:sDeskWhole(held);
    for(const part of sDeskParts(held))held.cards[part]=sDeskPart(held,part);
    const whole=held.wholeCard?(held.reading==='full'?held.wholeCard:disclosure('Revise the whole draft',held.wholeCard)):null;
    held.queueSlot=sNode('div','desk-review-queue');const queue=sDeskReviewQueue(held);if(queue)held.queueSlot.append(queue);
    // In reading order: an object keyed by part ids lists all-digit ids first, so the cards are
    // placed by the parts' own order, never by the object's.
    column.append(held.problemSlot,...[sActivityNow(view.activity,{id:held.id})].filter(Boolean),held.queueSlot,...[whole].filter(Boolean),...sDeskParts(held).map(part=>held.cards[part]));
    held.noSections=view.sections.length?null:sDeskNoSections();if(held.noSections)column.append(held.noSections);
  }
  held.bar=sDeskSelectionBar(held);held.aside=sDeskAside(held);
  // Finishing sits beside the draft in place of the sources; on a phone it is a full-screen sheet.
  const finishing=!!held.finish,sheet=finishing&&sNarrow();
  held.panel=finishing?sDeskPanel(held):null;held.panelKey=finishing?sDeskPanelKey(held):null;
  const lede=held.tab==='outline'?'Rename, reorder, add and remove sections and say what each must do. Write the draft from the outline, or one section at a time.':'Read your manuscript, or choose a section to edit. Polish and checks offer suggestions; nothing changes until you accept.';
  const said=sNode('p','lede',narrow?lede+' Changes save as you type.':lede);
  held.bench=sDeskBench(held);
  sPage(held.bench,narrow||held.bench&&held.tab!=='outline'?null:said,sDeskElsewhere(view),narrow||held.tab!=='outline'?null:status,held.tab==='outline'?sDeskTabs(held):null,held.tab==='outline'?null:sDeskReadingControls(held,said,status),sAdd(sNode('div','desk-layout'+(finishing&&!sheet?' desk-finishing':'')),column,finishing&&!sheet?held.panel:held.aside),sheet?held.panel:null,held.bar);
  sDeskImagesLoad(held);
}
// After a job starts, moves on or ends: redraw only the cards it changed, so the part the
// person is typing in keeps its focus and caret.
// A field the person is typing in is never drawn again under them: its card is brought up to
// date in place, and drawn again once focus leaves it.
function sDeskFocused(){return typeof document.activeElement==='object'?document.activeElement:null;}
function sDeskTyping(node){const focused=sDeskFocused();return !!(node&&focused&&['INPUT','TEXTAREA','SELECT'].includes(String(focused.tagName).toUpperCase())&&typeof node.contains==='function'&&node.contains(focused));}
function sDeskRefresh(held,before){
  // What the assistant is doing, drawn again in place whatever else is drawn again.
  sActivityUpdate($('studio-page'),held.view.activity,{id:held.id});
  // The arc and the move follow every change, whatever else is drawn again.
  if(held.bench&&held.bench.parentNode){const bench=sDeskBench(held);if(bench){held.bench.replaceWith(bench);held.bench=bench;}}
  if(held.mode==='review')return sDeskReviewRefresh(held,before);
  const view=held.view,order=found=>(found?.sections||[]).map(section=>section.id).join(',');
  if(held.tab==='outline'||held.shownTab!==held.tab){if((held.outlineTimer||held.tab==='outline'&&sDeskTyping(held.column))&&sDeskCurrent(held)){if(!held.outlineTimer)held.outlineStale=true;sDeskToolbar(held);const focus=sFocusHeld(held.aside),aside=sDeskAside(held);held.aside.replaceWith(aside);held.aside=aside;sFocusAgain(focus,aside);sDeskPanelSync(held);return;}held.outline=null;return sDeskRender(held);}
  if(!held.cards||!before||!sDeskCurrent(held))return sDeskRender(held);
  if(order(before)!==order(view))return sDeskReorder(held,before);
  sDeskToolbar(held);
  held.problemSlot.replaceChildren(...[sDeskProblem(held)].filter(Boolean));
  sDeskWholeState(held);
  const queue=sDeskReviewQueue(held);held.queueSlot?.replaceChildren(...[queue].filter(Boolean));
  for(const part of Object.keys(held.cards)){
    const was=sDeskWorkingIn(before,part),now=sDeskWorking(held,part),old=held.cards[part];
    const changed=was!==now||deskTextOf(before,part)!==deskTextOf(view,part)||(before.versions||{})[part]!==(view.versions||{})[part]||sDeskCommentKey(before,part)!==sDeskCommentKey(view,part);
    if(changed&&!sDeskTyping(old)){const card=sDeskPart(held,part);old.replaceWith(card);held.cards[part]=card;}
    else{if(changed)old.deskStale=true;sDeskPartState(held,part,old,was&&!now);}
  }
  const focus=sFocusHeld(held.aside),aside=sDeskAside(held);held.aside.replaceWith(aside);held.aside=aside;sFocusAgain(focus,aside);
  sDeskPanelSync(held);
  sDeskImagesLoad(held);
}
// A card brought up to date in place: whether its part is being worked on, its text when it
// is not the field typed in, and whether its notes can start a job now. When a job on this
// part has just ended (`landed`), its text is set even in a focused field: the field was
// read-only while the job worked, so nothing typed is lost, and the next keystroke must
// build on the job's text, never save the text from before it.
function sDeskPartState(held,part,card,landed=false){
  const view=held.view,working=sDeskWorking(held,part),focused=sDeskFocused(),input=card.deskInput;
  card.className=(held.reading==='read'?'desk-part desk-reading-part':'card desk-part')+(working?' desk-working':'');
  if(input){input.readOnly=working||!sDeskCan(held);if(landed)delete held.pending[part];if(landed||input!==focused&&!held.pending[part]){const text=deskTextOf(view,part);if(input.value!==text)input.value=text;}}
  if(card.deskGo)card.deskGo.disabled=!sDeskCan(held)||!!view.working;
  if(!working&&card.deskWorkingNotes){for(const note of card.deskWorkingNotes)note.remove();card.deskWorkingNotes=null;}
}
// Sections added, removed or moved by a job while the person types: the card they are typing
// in stays where it is, brought up to date in place, and the other cards are drawn in the new
// order around it. With nothing being typed, the desk is drawn again whole.
function sDeskReorder(held,before){
  if(held.reading!=='full')return sDeskRender(held);
  const view=held.view,parts=['title','opening',...(view.sections||[]).map(section=>section.id)];
  const keep=Object.values(held.cards).find(card=>sDeskTyping(card))||null;
  if(keep?!parts.includes(keep.dataset.part):!sDeskTyping(held.wholeCard))return sDeskRender(held);
  sDeskToolbar(held);
  held.problemSlot.replaceChildren(...[sDeskProblem(held)].filter(Boolean));
  sDeskWholeState(held);
  const cards={};
  for(const part of parts){
    if(keep&&keep.dataset.part===part){const was=sDeskWorkingIn(before,part),now=sDeskWorking(held,part);if(was!==now||deskTextOf(before,part)!==deskTextOf(view,part))keep.deskStale=true;sDeskPartState(held,part,keep,was&&!now);cards[part]=keep;}
    else cards[part]=sDeskPart(held,part);
  }
  for(const old of Object.values(held.cards))if(old!==keep)old.remove();
  if(held.noSections){held.noSections.remove();held.noSections=null;}
  const order=parts.map(part=>cards[part]);
  if(keep){const at=parts.indexOf(keep.dataset.part);keep.before(...order.slice(0,at));keep.after(...order.slice(at+1));}
  else held.column.append(...order);
  held.cards=cards;
  if(!view.sections.length){held.noSections=sDeskNoSections();held.column.append(held.noSections);}
  const focus=sFocusHeld(held.aside),aside=sDeskAside(held);held.aside.replaceWith(aside);held.aside=aside;sFocusAgain(focus,aside);
  sDeskPanelSync(held);
  sDeskImagesLoad(held);
}
function sDeskNoSections(){return sCard('No sections yet',sNode('p','','This draft has no headings, so it is one opening. Add sections on the Outline tab.'));}
// Drawn again once focus leaves a card brought up to date in place.
function sDeskPartLeft(held,part,card){
  setTimeout(()=>{if(!card.deskStale||held.cards?.[part]!==card||sDeskTyping(card)||!sDeskCurrent(held)||held.mode==='review')return;const fresh=sDeskPart(held,part);card.replaceWith(fresh);held.cards[part]=fresh;sDeskImagesLoad(held);},0);
}
// What the last job left: a result not applied, or a job that failed.
function sDeskProblem(held){return DESK_KIT.problem(held);}
function sDeskWhole(held){return DESK_KIT.whole(held);}
// The note for the whole draft is never drawn again by a poll: only its button follows the job.
function sDeskWholeState(held){if(held.wholeGo)held.wholeGo.disabled=!sDeskCan(held)||!!held.view.working;}
function sDeskPart(held,part){return held.reading==='read'?sDeskReadPart(held,part):DESK_KIT.part(held,part);}
// One source on the desk. A document taken from the Document Library says which revision
// this blog reads; a newer one there shows Update available, and is taken only with
// Use revision N. Nothing already written changes, and no job starts.
function sDeskSourceRow(held,source){
  const row=sNode('li','row'),text=sAdd(sNode('div','row-text'),sNode('span','row-title',source.name));row.append(text);
  const found=source.library;if(!found)return row;
  text.append(sNode('span','row-says','From the Document Library · revision '+found.revision+(found.update?' · Update available: revision '+found.head:found.head===null?' · no longer in the Document Library; this blog keeps its copy':'')));
  if(found.update){
    const take=sButton('Use revision '+found.head,async button=>{await busy(button,'Taking revision '+found.head+'…',async()=>{try{await sDeskFlush(held);const before=held.view;held.view=await api('desk-library-update',{id:held.id,source:source.id});sToast('Revision '+found.head+' is a source now. Later rewrites read it; nothing already written changes.');sDeskRefresh(held,before);}catch(error){sToast(error.message);}});});
    take.setAttribute('aria-label','Use revision '+found.head+' of '+source.name);take.disabled=!sDeskCan(held)||!!held.view.working;row.append(take);
  }
  return row;
}
function sDeskAside(held){
  const view=held.view,aside=sNode('aside','desk-aside');aside.setAttribute('aria-label','Sources and gaps');
  const sources=sCard('Sources');
  if((view.source_names||[]).length){const list=sNode('ul','rows');for(const source of view.source_names)list.append(sDeskSourceRow(held,source));sources.append(list);}
  else if(!view.research)sources.append(sNode('p','quiet','No sources were given for this draft. Rewrites keep to what the draft already says.'));
  if(view.research)sources.append(sNode('p','quiet','Research was read for this draft'+(view.research.sources?': '+view.research.sources+(view.research.sources===1?' source.':' sources.'):'.')));
  const add=sButton('Add a source',()=>sDeskSourcesSheet(held));add.disabled=!sDeskCan(held);sources.append(sAdd(sNode('div','bar'),add));
  if(view.style_name)sources.append(sNode('p','quiet','Kind of post: '+view.style_name));
  if(view.tone)sources.append(sNode('p','quiet','Tone: '+view.tone));
  aside.append(sources);
  const kept=sDeskKeptLine(view);if(kept)sources.append(kept);
  // What the assistant did in each job for this blog, newest first: read when it is opened.
  const log=sActivityLog({id:held.id});
  // Other people's suggestions pending in the Google Doc, each where it sits: decided there.
  const doc=view.doc_suggestions||{count:0,marks:[]};
  if(doc.count){
    const card=sCard('Suggested in the Doc',sDocPendingLine(doc.count),sDocKey());card.className+=' doc-pending-card';
    const list=sNode('ul','rows doc-suggestions');
    for(const mark of doc.marks){const text=deskTextOf(view,mark.part),before=text.slice(Math.max(0,mark.at-24),mark.at).replace(/^\S*\s/,'…'),after=text.slice(mark.at+mark.length,mark.at+mark.length+24).replace(/\s\S*$/,'…');list.append(sAdd(sNode('li','row'),document.createTextNode(before),sDocMark(text,mark),document.createTextNode(after)));}
    if(doc.marks.length)card.append(list);
    if(doc.marks.length<doc.count)card.append(sNode('p','quiet',(doc.count-doc.marks.length===1?'1 is':(doc.count-doc.marks.length)+' are')+' on words the desk has changed since, so not marked here.'));
    aside.append(card);
  }
  const gaps=view.gaps||[];
  const list=sNode('ul','gap-items');for(const gap of gaps)list.append(sNode('li','',gap));
  aside.append(sAdd(sNode('section','paper aside-part'),sNode('h2','aside-title','Needs you before publishing'),gaps.length?list:sNode('p','quiet','Nothing yet. What a rewrite cannot support from your sources is listed here, never in the text.')));
  if(view.run)aside.append(sAdd(sNode('p','quiet'),sButton('Open the step-by-step run',()=>sRoute('run',view.id))));
  if(!sNarrow()){if(log)aside.append(log);return aside;}
  // On a phone the sources and gaps fold under the draft, and the Activity log follows them.
  const folded=disclosure('Sources and what needs you'+(gaps.length?' ('+gaps.length+')':''),...aside.children);folded.className='desk-aside desk-aside-folded';
  return log?sAdd(sNode('div','stack desk-aside-stack'),folded,log):folded;
}

// Saving as you type: one second after the last keystroke, against the revision last seen.
function sDeskTyped(held,part,text){return DESK_KIT.typed(held,part,text);}
function sDeskSave(held,part){return DESK_KIT.save(held,part);}
// After a save: an image pasted as data is kept beside the text, so its card shows the reference instead.
async function sDeskSaved(held,part,text){if(/data:image\//i.test(text)&&!held.pending[part]&&held.cards?.[part]&&sDeskCurrent(held)){const card=sDeskPart(held,part);held.cards[part].replaceWith(card);held.cards[part]=card;await sDeskImagesLoad(held);}}
// Review mode's paragraph editor saves first, then every part typing left waiting.
function sDeskFlush(held){return DESK_KIT.flush(held);}
function sDeskCounts(held){return DESK_KIT.counts(held);}
function sDeskStale(held){return DESK_KIT.stale(held);}

// Leaving the desk, or hiding its tab, shares the edits typing kept on this computer.
// keepalive lets the request finish while the tab goes away.
function sDeskShare(held){return DESK_KIT.share(held);}

// Notes and selection edits start a job; the desk follows it until it ends.
function sDeskJob(held,button,route,data,done){return DESK_KIT.job(held,button,route,data,done);}
function sDeskWatch(held){return DESK_KIT.watch(held);}

// A small bar for the selected passage: Rephrase, Shorten, Expand, Fix and Ask….
function sDeskSelected(held,part,input){return DESK_KIT.selected(held,part,input);}
function sDeskSelectionBar(held){return DESK_KIT.selectionBar(held);}
function sDeskBarContent(held){return DESK_KIT.barContent(held);}

// History: each kept version with its words compared to the current text, and Restore.
// A version from before a first pass divided the draft brings the draft back as it was.
function deskVersionNote(version){const added=(version.divided||[]).length;return added?'Restoring this also takes out the '+added+(added===1?' section':' sections')+' the first pass added. They can be brought back on the Outline tab.':'';}
function sDeskHistory(held,part){return DESK_KIT.history(held,part);}

// Make a Google Doc: a private Doc of the draft, made once and linked to this blog. The desk
// then sends its later wording to it as suggestions, from Before publishing.
function sDeskMakeDoc(held){
  const problem=sNode('p','sheet-error');problem.setAttribute('role','alert');
  const make=sButton('Make the Doc',async button=>{await busy(button,'Making…',async()=>{try{await sDeskFlush(held);await api('desk-google-open',{id:held.id,expected:held.view.expected,confirmed:true});sCloseSheet();sToast('Google Doc made. Later desk changes are sent to it as suggestions.');await sDesk(held.id);}catch(error){problem.textContent=error.message;}});},'filled');
  make.disabled=!sDeskCan(held);
  sOpenSheet('Make a Google Doc?',sNode('p','','A private Google Doc of this draft is made in your Drive. Later desk changes are sent to it as suggestions.'),problem,sAdd(sNode('div','bar'),make,sButton('Cancel',sCloseSheet)));
}
// Mark as published: where it went, said by the person. Nothing is posted.
function sDeskPublish(held){
  const draft={url:held.view.publication||''},problem=sNode('p','sheet-error');problem.setAttribute('role','alert');
  const save=sButton('Mark as published',async button=>{const url=draft.url.trim();if(!/^https:\/\/\S+$/.test(url)){problem.textContent='Add the public https address where it was published.';return;}await busy(button,'Saving…',async()=>{try{await sDeskFlush(held);const result=await api('schedule',{id:held.id,expected:held.view.expected,stage:'published',confirm_stage:true,publication_url:url}),kept=result?.library,copy=result?.document_library;sCloseSheet();sToast('Recorded as published. Nothing was posted anywhere.'+(kept?.reason?' Not kept in the team library: '+kept.reason:kept?.id?' Its draft is kept in the team library.':'')+(copy?.state==='kept'?' A copy is in the Document Library on this computer.':copy?.state==='failed'?' Not kept in the Document Library: '+copy.reason:''));await sDesk(held.id);}catch(error){problem.textContent=error.message;}});},'filled');
  const team=studio.team?.joined?'':' Without a Team Hub, the team library is on this computer only.';
  sOpenSheet('Mark as published',sNode('p','','Record where this blog was published. The current text is the published one. Its draft is kept in the team library, as a reference and an example of its kind of post, and a copy goes to the Document Library on this computer, for any studio. Marking it again updates both.'+team),sField('desk-publication','Public address',draft,'url',{max:2000,required:true}),problem,sAdd(sNode('div','bar'),save,sButton('Cancel',sCloseSheet)));
}

// A finished step-by-step blog once it is on the desk: its run is read as it ended, with
// nothing to resume, approve or ask for; the desk is where it is edited now.
function sRunOnDesk(found){
  studio.found=found;studio.signature=JSON.stringify(found);
  const open=sButton('Open on the desk',()=>sRoute('desk',found.id),'filled');
  sFrame(found.title,[open],'Writing run',()=>sRoute('blogs'));
  const steps=sNode('ol','rows');for(const row of found.stages||[])steps.append(sAdd(sNode('li','row step'),sBead(row.status==='approved'?'done':'none'),sAdd(sNode('div','row-text'),sNode('h3','step-name',row.label),found.unfinished_migration?sNode('p','quiet',row.accepted_by==='review-policy'?'Continued automatically':STAGE_STATUSES[row.status]||row.status):null)));
  sPage(sNode('p','lede','The saved run stays readable while you edit on the writing desk.'),sCard('This blog is on the writing desk',sNode('p','',found.unfinished_migration?'Its supported materials were opened on the desk as a Draft. Unfinished steps remain incomplete, and the original decisions and files are kept. No work was started.':'It was finished here and then opened on the desk, where its notes, selection edits and versions are. This run is kept as it ended, to read.')),disclosure('How it was written',steps));
}

// The Outline tab: each section's heading and brief, in order, saved as they are edited with
// the stale check; reordering keeps each section's id, so its text and History go with it.
function sDeskOutlineRows(held){return held.outline||(held.outline=(held.view.sections||[]).map(section=>({id:section.id,heading:section.heading,brief:section.brief||''})));}
function sDeskOutline(held){
  const view=held.view,rows=sDeskOutlineRows(held),editable=sDeskCan(held),whole=!!view.working;
  const write=sButton('Write the draft',button=>sDeskWriteDraft(held,button),'filled');write.disabled=!editable||whole||!rows.length;
  const add=sButton('Add a section',()=>sDeskOutlineChange(held,rows=>rows.push({heading:'New section',brief:''})));add.disabled=!editable;
  const head=sCard('Outline',sNode('p','','Each brief says what its section must do. The draft is written from the outline, section by section, with your sources.'),sAdd(sNode('div','bar'),write,add));
  const cards=rows.map((row,index)=>sDeskOutlineCard(held,row,index,rows.length));
  if(!rows.length)cards.push(sCard('No sections yet',sNode('p','','Add a section to start the outline.')));
  // Sections taken out, with their text and History, to bring back.
  if((view.removed||[]).length){const list=sNode('ul','rows');view.removed.forEach((item,index)=>{const back=sButton('Bring back',async button=>{await busy(button,'Bringing back…',async()=>{try{await sDeskOutlineFlush(held);held.view=await api('desk-unremove',{id:held.id,seen:held.view.revision,index});held.outline=null;sDeskRender(held);}catch(error){if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else notice(error.message,true);}});});back.setAttribute('aria-label','Bring back '+item.heading);back.disabled=!editable;list.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('span','row-title',item.heading),sNode('span','row-says',(item.words?item.words+(item.words===1?' word':' words'):'No text')+(item.at?' · removed '+deskAge(item.at):''))),back));});cards.push(sCard('Removed sections',list));}
  return [head,...cards];
}
function sDeskOutlineCard(held,row,index,count){
  const view=held.view,section=(view.sections||[]).find(found=>found.id===row.id),working=!!row.id&&sDeskWorking(held,row.id),editable=sDeskCan(held)&&!working;
  const card=sNode('section','card desk-part desk-outline-part'+(working?' desk-working':''));if(row.id)card.dataset.part=row.id;
  const words=section?.text?section.text.split(/\s+/).filter(Boolean).length:0;
  card.append(sAdd(sNode('div','desk-part-head'),sNode('h2','card-title','Section '+(index+1)),sNode('span','quiet',words?words+(words===1?' word written':' words written'):'Not written yet')));
  const heading=sField('desk-outline-heading-'+index,'Heading',row,'heading',{max:200,changed:()=>sDeskOutlineTyped(held)}),brief=sField('desk-outline-brief-'+index,'What it must do',row,'brief',{long:true,max:4000,changed:()=>sDeskOutlineTyped(held)});
  for(const box of [heading,brief])box.querySelector(box===heading?'input':'textarea').readOnly=!editable;
  card.append(heading,brief);
  if(working){const note=sNode('p','desk-working-note','Working on this section');note.setAttribute('role','status');card.append(note);}
  const name=row.heading||'this section',move=(by,label)=>{const button=sButton(label,()=>sDeskOutlineChange(held,rows=>{const [moved]=rows.splice(index,1);rows.splice(index+by,0,moved);}));button.setAttribute('aria-label',label+' · '+name);button.disabled=!sDeskCan(held)||index+by<0||index+by>=count;return button;};
  const remove=sButton('Remove',()=>{const gone=rows=>rows.splice(index,1);if(!words)return sDeskOutlineChange(held,gone);const confirm=sButton('Remove the section',async button=>{await busy(button,'Removing…',async()=>{sCloseSheet();await sDeskOutlineChange(held,gone);});},'danger');sOpenSheet('Remove “'+name+'”?',sNode('p','','Its '+words+(words===1?' word goes':' words go')+' with it. Bring it back from Removed sections under the outline.'),sAdd(sNode('div','bar'),confirm,sButton('Cancel',sCloseSheet)));});
  remove.setAttribute('aria-label','Remove '+name);remove.disabled=!sDeskCan(held)||working;
  const write=sButton(words?'Write it again':'Write this section',async button=>{await sDeskJob(held,button,'desk-note',{part:row.id,note:''});});
  write.disabled=!sDeskCan(held)||!!view.working||!row.id;
  card.append(sAdd(sNode('div','bar'),move(-1,'Move up'),move(1,'Move down'),remove,write));
  return card;
}
function sDeskOutlineTyped(held){
  if(held.outlineTimer&&typeof clearTimeout==='function')clearTimeout(held.outlineTimer);
  held.outlineTimer=setTimeout(()=>sDeskOutlineSave(held),DESK_SAVE_WAIT);
  if(held.status)held.status.textContent='Saving…';
}
async function sDeskOutlineFlush(held){if(held.outlineTimer)await sDeskOutlineSave(held);}
async function sDeskOutlineChange(held,change){await sDeskFlush(held);change(sDeskOutlineRows(held));await sDeskOutlineSave(held,true);}
async function sDeskOutlineSave(held,redraw=false){
  if(held.outlineTimer&&typeof clearTimeout==='function')clearTimeout(held.outlineTimer);held.outlineTimer=null;
  if(held.stale||!held.outline)return;
  while(held.saving)await held.saving;
  const rows=held.outline.map(row=>({...(row.id?{id:row.id}:{}),heading:row.heading,brief:row.brief}));
  if(rows.some(row=>!row.heading.trim())){if(held.status)held.status.textContent='Give each section a heading; it saves once it has one.';return;}
  held.saving=(async()=>{try{
    held.view=await api('desk-outline-save',{id:held.id,seen:held.view.revision,sections:rows});
    held.saved='Saved.';if(held.status)held.status.textContent='Saved.';
    if(redraw||rows.some(row=>!row.id)){held.outline=null;if(sDeskCurrent(held))sDeskRender(held);}
  }catch(error){
    if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}
    else if(held.status)held.status.textContent=error.message+' Your outline is kept here.';
  }finally{held.saving=null;}})();
  await held.saving;
}
async function sDeskWriteDraft(held,button){
  const go=async pressed=>{await sDeskOutlineFlush(held);await sDeskJob(held,pressed,'desk-draft',{},()=>{held.tab='draft';held.outline=null;});};
  if(!sDeskHasText(held.view))return go(button);
  const confirm=sButton('Write the draft',async pressed=>{sCloseSheet();await go(pressed);},'filled');
  sOpenSheet('Write the whole draft?',sNode('p','','Every section is written from its brief, and the opening too. The text there now is kept in History first.'),sAdd(sNode('div','bar'),confirm,sButton('Cancel',sCloseSheet)));
}

// Finishing: an optional side panel of tools that propose. Each proposal is previewed before
// and after, side by side, then applied, edited or skipped; nothing changes until Apply, and
// each Apply keeps the earlier text in History. On a phone the panel is a full-screen sheet.
// The panel is the shared desk kit's (DESK_KIT); these are Blog Studio's tools, in panel
// order, each found by its key. Quick check keeps the key proofread, as its route
// desk-proofread does. Copy edit is reviewed in the text itself: it opens Review mode.
const DESK_VERDICTS={supported:'Supported','not-in-sources':'Not in your sources',contradicted:'Contradicted'};
const DESK_ASPECTS={shape:'Shape',argument:'Argument',audience:'Audience',claims:'Claims'};
const DESK_TOOLS=[
  {key:'copyedit',name:'Copy edit',says:'Grammar, spelling, punctuation, consistency and wordy sentences, each fix marked in your text to accept or reject. Voice, facts, quotes and links are kept.',run:'Find fixes',doing:'Finding grammar, spelling and wording fixes…',open:held=>sDeskCopyEdit(held),applyAll:true,empty:'Nothing to fix.'},
  {key:'humanize',name:'Humanize',says:'Sentences that read as machine-written, each with a rewrite. Numbers, names, quotes and links are kept.',run:'Find sentences',doing:'Finding sentences that read as machine-written…',start:{level:'light'},options:(held,f)=>[sChoice('Intensity',DESK_LEVELS,f,'level')],data:f=>({level:f.level}),applyAll:true,view:held=>sDeskHumanizeView(held)},
  {key:'proofread',name:'Quick check',says:'Dashes, repetition, source IDs, editorial notes and passages carried over from examples, checked at once with no assistant.',view:held=>DESK_KIT.proofView(held),opened:(held,first)=>first||!held.finish.proof?sDeskProofread(held):undefined},
  {key:'facts',name:'Check facts against sources',says:'Each claim marked supported, not in your sources, or contradicted, with the passage.',run:'Check facts',doing:'Checking each claim against your sources…',options:held=>sDeskFactsOptions(held),verdicts:DESK_VERDICTS,counted:[' claim checked',' claims checked'],empty:'No claims to check.',source:held=>sDeskSourcesSheet(held)},
  {key:'geo',name:'GEO: retrieval readiness',says:'Proposals for direct answers, clear entities, claims with their context and dates, and useful evidence. Preview each change, then apply or skip it.',run:'Review retrieval readiness',doing:'Reviewing retrieval readiness…',applyAll:true,empty:'No retrieval changes suggested.',said:(set,said)=>{const summary=(set.summary||'').trim().replace(/\.+$/,'');if(summary)said.push(summary);}},
  {key:'faq',name:'FAQ',says:'An aid for readers: the questions they would ask next, each answered only from the post and its sources, as a section you place. Edit or drop each one, then add them all or the ones you tick.',run:'Write the FAQ',doing:'Writing questions a reader would ask next…',start:{faqCount:'5'},view:held=>sDeskSectionView(held,'faq')},
  {key:'takeaways',name:'Key takeaways',says:'An aid for readers: a short list of the post’s own points, as a section you place. Edit or drop each one, then add them all or the ones you tick.',run:'Write key takeaways',doing:'Gathering the post’s key points…',view:held=>sDeskSectionView(held,'takeaways')},
  {key:'table',name:'Comparison table',says:'A table of what the post compares, built from what it says, after the paragraph that makes the comparison. Only where the post really compares things.',run:'Suggest a table',doing:'Looking for what the post compares…',empty:'No table suggested: the post does not compare things side by side.',said:(set,said)=>deskSummarySaid(set,said)},
  {key:'quotes',name:'Quotes from sources',says:'Exact passages from your selected sources, word for word with their source named, after the paragraph whose point they support.',run:'Find quotations',doing:'Finding passages in your sources…',options:held=>sDeskQuotesOptions(held),empty:'No passage in your sources fits a point the post makes.',said:(set,said)=>deskSummarySaid(set,said)},
  {key:'opener',name:'Definition-style opening',says:'A one- or two-sentence opening that defines the topic, to compare with your opening, then use or skip.',run:'Suggest an opening',doing:'Writing a definition-style opening…',empty:'No definition-style opening suggested: the opening could not be matched.'},
  {key:'alt',name:'Image alt text',says:'Alt text for images that have none, written from what the post says about each one. Blog Studio cannot see the images themselves, so check each before you apply it.',run:'Write alt text',doing:'Writing alt text from what the post says…',applyAll:true,empty:'No alt text suggested: the post says nothing about these images.',said:(set,said)=>{if(set.unknown)said.push(set.unknown+(set.unknown===1?' image the post says nothing about: describe it yourself':' images the post says nothing about: describe them yourself'));}},
  {key:'queries',name:'Likely search questions',says:'Questions people might ask an AI assistant that this post answers. Advice for you: nothing is added to the post.',run:'List the questions',doing:'Listing the questions this post answers…',view:held=>sDeskQueriesView(held),status:(held,set)=>{const n=(set.queries||[]).length;return n?n+(n===1?' question listed.':' questions listed.'):'';}},
  {key:'headline',name:'Headline and opening',says:'Alternatives for the title and the opening, to use or adjust.',run:'Suggest alternatives',doing:'Suggesting headlines and openings…',groups:[['title','Title'],['opening','Opening']]},
  {key:'feedback',name:'Feedback without a rewrite',says:'Comments on shape, argument, audience and claims. Nothing in the text changes.',run:'Get feedback',doing:'Reading the draft for feedback…',comments:DESK_ASPECTS},
  {key:'voice',name:'Apply a voice',says:'The draft rewritten in one of your voice guides, section by section. Its facts, quotes, links and shape are kept.',run:'Apply the voice',doing:'Rewriting the draft in the voice guide, section by section…',opened:held=>sDeskGuides(held),options:(held,f)=>sDeskVoiceOptions(held,f),data:f=>({guide:f.guide}),ready:f=>!!f.guide,applyAll:true,counted:[' part rewritten',' parts rewritten'],empty:'Nothing to change: the draft already reads in this voice.',said:(set,said)=>{if(set.guide_name)said.unshift('In the voice of '+set.guide_name);if(set.kept)said.push(set.kept+(set.kept===1?' part already reads':' parts already read')+' in this voice');},flagged:flagged=>flagged+(flagged===1?' part that changes a fact, code or the part’s shape is':' parts that change a fact, code or a part’s shape are')+' left for you to check one by one.'},
  {key:'publish',name:'Before publishing',says:'The pre-publish check, the GEO review, Repurpose, and Send to Google Doc as suggestions.',view:held=>sDeskPublishView(held)},
];
for(const tool of DESK_TOOLS)tool.group=({copyedit:'Polish the writing',humanize:'Polish the writing',proofread:'Check before sharing',facts:'Check claims',geo:'Reader aids and AI search',faq:'Reader aids and AI search',takeaways:'Reader aids and AI search',table:'Reader aids and AI search',quotes:'Reader aids and AI search',opener:'Reader aids and AI search',alt:'Reader aids and AI search',queries:'Reader aids and AI search',headline:'Shape and voice',feedback:'Shape and voice',voice:'Shape and voice',publish:'Send and download'})[tool.key];
// One Finishing tool, by its key.
function deskTool(key){return DESK_KIT.tool(key);}
const DESK_LEVELS=[['light','Light'],['medium','Medium'],['strong','Strong']];
// [run, doing] for each tool that runs a job, as the tools say them.
const DESK_RUN=Object.fromEntries(DESK_TOOLS.filter(tool=>tool.run).map(tool=>[tool.key,[tool.run,tool.doing]]));
const DESK_FORMATS=[['linkedin','LinkedIn feed copy'],['newsletter','Newsletter introduction'],['email','Announcement email'],['summary','Short summary'],['thread','Short thread'],['meta','SEO meta description']];
// An SEO meta description is counted in characters and kept with its post, never a new blog.
const DESK_META_LIMIT=155;
function sDeskFinishOpen(held,tool=null){const input=held.cards?.[held.activePart]?.deskInput;held.returnFocus=input?{part:held.activePart,start:input.selectionStart,end:input.selectionEnd}:null;held.returnScroll=typeof window.scrollY==='number'?window.scrollY:0;const open=()=>held.stale?undefined:DESK_KIT.finishOpen(held,tool);if(Object.keys(held.pending||{}).length||held.outlineTimer||held.review?.editing?.dirty)return sDeskFlush(held).then(()=>sDeskOutlineFlush(held)).then(()=>Object.keys(held.pending||{}).length?undefined:open());return open();}
function sDeskFinishClose(held){return DESK_KIT.finishClose(held);}
// The finishing pass: one start for what a post is usually finished with. Copy edit, then
// more human-sounding wording at the strength kept for this blog (medium the first time),
// land as one review in the text beside the Quick check; Check facts against sources runs
// last, and its findings wait under Check claims. Each tool below still runs on its own.
function sDeskFinishPass(held){
  const view=held.view,level=view.review?.humanize||'medium',voice=view.review?.voice_guide?.id;
  const run=sButton('Finish this post',async button=>{await sDeskFlush(held);await sDeskOutlineFlush(held);if(held.stale)return;sReviewEnter(held);sDeskRender(held);await sReviewCheck(held,button,level,voice||undefined,true);},'filled');
  run.disabled=!sDeskCan(held)||!!view.working;
  const card=sCard('One pass',sNode('p','','Copy edit and more human-sounding wording, marked in your text as one review beside the Quick check, then a check of your claims against your sources. Nothing changes until you accept it.'),sAdd(sNode('div','bar'),run));
  card.classList.add('desk-finish-pass');return card;
}
function sDeskReturnFocus(held){const saved=held.returnFocus,input=saved&&held.cards?.[saved.part]?.deskInput;if(input){input.focus();input.setSelectionRange?.(saved.start,saved.end);}if(typeof window.scrollTo==='function')window.scrollTo(0,held.returnScroll||0);}
// Copy edit is reviewed in the text itself: it opens Review mode, where the check starts.
async function sDeskCopyEdit(held){await sDeskFlush(held);await sDeskOutlineFlush(held);sReviewEnter(held);sDeskRender(held);sDeskWatch(held);}
// Review mode, entered from the desk, remembers the view, the part, the tab and the scroll it
// came from; Back returns there. Reloads keep the manuscript view and part in the address.
function sReviewEnter(held){if(held.mode!=='review')held.reviewFrom={reading:held.reading||'read',part:held.activePart||'opening',tab:held.tab||'draft',scroll:typeof window.scrollY==='number'?window.scrollY:0};held.finish=null;held.mode='review';}
async function sReviewLeave(held,reading){
  await sReviewFlush(held);const from=held.reviewFrom||{reading:held.reading||'read',part:held.activePart||'opening',tab:'draft',scroll:0};
  held.reviewFrom=null;held.reviewHuman=false;held.mode=null;held.reading=reading||from.reading;held.activePart=from.part;held.tab=reading?'draft':from.tab;
  sDeskModeUrl(held);sDeskViewUrl(held);sDeskRender(held);sDeskWatch(held);
  if(!reading&&typeof window.scrollTo==='function')window.scrollTo(0,from.scroll||0);
}
// Humanize's rewrites reviewed in the text, with Accept and Reject, as Copy edit's fixes are.
async function sReviewHuman(held){await sDeskFlush(held);await sDeskOutlineFlush(held);if(Object.keys(held.pending||{}).length)return;sReviewEnter(held);held.reviewHuman=true;sDeskRender(held);sDeskWatch(held);}
function sDeskFinishTool(held,tool){return DESK_KIT.finishTool(held,tool);}
// One optional saved guide in both Polish intake and a first review. Loading only this
// region preserves the draft and keyboard focus while the catalog arrives.
function sPolishVoiceChoice(held,prefix){
  const options=sNode('div','stack'),message=sNode('p','quiet');options.hidden=!held.voiceOn;
  let loading=false;
  const show=async()=>{
    if(loading)return;loading=true;options.replaceChildren(sNode('p','quiet','Reading saved voice guides…'));
    try{
      const found=await api('voice-guides'),guides=found.guides.filter(guide=>guide.status!=='retired');held.polishVoices=guides;
      if(!guides.some(guide=>guide.id===held.voiceGuide))held.voiceGuide='';
      const summary=sNode('p','quiet',(guides.find(guide=>guide.id===held.voiceGuide)||{}).says||'');
      options.replaceChildren(sField(prefix+'-voice-guide','Voice guide',held,'voiceGuide',{options:[['','Choose a saved voice guide'],...guides.map(guide=>[guide.id,guide.name])],changed:id=>{summary.textContent=(guides.find(guide=>guide.id===id)||{}).says||'';}}),summary);
      if(!guides.length)options.append(sNode('p','quiet','No active voice guides yet. Create one on Voice guides, then return to this draft.'));
    }catch(error){message.textContent=error.message;message.setAttribute('role','alert');options.replaceChildren(message,sButton('Try loading voice guides again',show));}
    finally{loading=false;}
  };
  const tick=sCheck(prefix+'-voice','Use a voice guide',held,'voiceOn','Suggest wording in a saved voice while keeping facts, quotations and structure. Every change is yours to accept or reject.',on=>{options.hidden=!on;if(on)show();});
  if(held.voiceOn)show();return sAdd(sNode('div','polish-voice-choice'),tick,options);
}
// The voice guides Apply a voice can use, read when the tool opens.
async function sDeskGuides(held){
  const f=held.finish;try{const found=await api('voice-guides');if(held.finish!==f)return;f.guides=found.guides.filter(guide=>guide.status!=='retired');f.guidesProblem='';}catch(error){if(held.finish!==f)return;f.guides=f.guides||[];f.guidesProblem=error.message;}
  const used=(held.view.finishing||{}).voice?.items&&f.guides.find(guide=>guide.name===(held.view.finishing||{}).voice.guide_name);
  if(!f.guides.some(guide=>guide.id===f.guide))f.guide=(used||f.guides[0]||{}).id||'';
  if(f.tool==='voice')sDeskPanelSync(held,true);
}
function sDeskPanel(held){return DESK_KIT.panel(held);}
// What the panel shows, so a poll redraws it only when that changed.
function sDeskPanelKey(held){return DESK_KIT.panelKey(held);}
function sDeskPanelShow(held){return DESK_KIT.panelShow(held);}
// A redraw the person did not ask for waits while they use a control in the panel, and
// happens as soon as focus leaves it.
function sDeskPanelSync(held,force=false){return DESK_KIT.panelSync(held,force);}
function sDeskToolList(held){return DESK_KIT.toolList(held);}
function sDeskToolSays(held,key){return DESK_KIT.toolSays(held,key);}
function sDeskToolView(held,key){return DESK_KIT.toolView(held,key);}
// Apply a voice: the voice guide to rewrite in, read when the tool opens.
function sDeskVoiceOptions(held,f){
  const parts=[];
  if(!f.guides)parts.push(sNode('p','quiet','Reading your voice guides…'));
  else if(!f.guides.length){parts.push(sAdd(sNode('div','decision-notice'),sNode('p','','No voice guides yet. Write one, or make one from a few samples of the writing you want to sound like.'),sButton('Open voice guides',()=>sRoute('guides'))));}
  else{const says=sNode('p','quiet desk-guide-says',(f.guides.find(guide=>guide.id===f.guide)||{}).says||'');parts.push(sField('desk-voice-guide','Voice guide',f,'guide',{options:f.guides.map(guide=>[guide.id,guide.name]),changed:value=>{says.textContent=(f.guides.find(guide=>guide.id===value)||{}).says||'';}}),says);}
  if(f.guidesProblem)parts.push(sNode('p','problem',f.guidesProblem));
  return parts;
}
// Check facts: a draft with no sources yet is told so, with Add a source.
function sDeskFactsOptions(held){
  if((held.view.source_names||[]).length)return [];
  const add=sButton('Add a source',()=>sDeskSourcesSheet(held));add.disabled=!sDeskCan(held);
  return [sAdd(sNode('div','decision-notice desk-problem'),sNode('p','','Facts are checked against your sources, and this draft has none yet.'),add)];
}
function sDeskProposals(held,key,set){return DESK_KIT.proposals(held,key,set);}
// Humanize in Finishing. With nothing open it is the kit's tool: Find sentences, filled. With
// rewrites waiting, finishing them comes first: Review them in your text (Accept and Reject,
// as Copy edit's fixes), the list with Apply all, and Find sentences again last and quiet,
// saying that a new look replaces the open set.
function sDeskHumanizeView(held){
  const tool=deskTool('humanize'),view=held.view,f=held.finish,set=(view.finishing||{}).humanize,working=view.working;
  const open=set?set.items.filter(item=>item.state==='open'):[],located=open.filter(item=>item.present&&'after' in item).length;
  const run=sButton(set?tool.run+' again':tool.run,button=>sDeskJob(held,button,'desk-finish',{tool:'humanize',...tool.data(f)}),open.length?'':'filled');run.disabled=!sDeskCan(held)||!!working;
  const said=[];
  if(working&&working.kind==='finish-humanize'){const note=sNode('p','desk-working-note',tool.doing);note.setAttribute('role','status');said.push(note);}
  else if(working)said.push(sNode('p','quiet','Another change is under way. This can run when it ends.'));
  const last=(view.jobs||[]).filter(job=>job.kind==='finish-humanize').at(-1);
  if(last&&!last.busy&&last.error&&(!set||set.job!==last.id))said.push(sNode('p','problem',last.error));
  const head=[sNode('p','quiet',tool.says),...tool.options(held,f)];
  if(!open.length)return [...head,sAdd(sNode('div','bar'),run),...said,...(set?sDeskProposals(held,'humanize',set):[])];
  const review=sButton('Review them in your text',()=>sReviewHuman(held),'filled');review.disabled=!located||!sDeskCan(held);
  return [head[0],...said,sAdd(sNode('div','bar'),review),sNode('p','quiet','In your text each rewrite is accepted or rejected; here Apply takes it and Skip leaves the sentence as it is. Either way the earlier text stays in History.'),...sDeskProposals(held,'humanize',set),
    sNode('h3','sheet-part','Look again'),...head.slice(1),sAdd(sNode('div','bar'),run),sNode('p','quiet',open.length===1?'Finding sentences again replaces the open suggestion with a new set.':'Finding sentences again replaces the '+open.length+' open suggestions with a new set.')];
}
// Before and after side by side: struck words only before, marked words only after.
function deskSides(before,after){return DESK_KIT.sides(before,after);}
function sDeskProposal(held,set,item,key){return DESK_KIT.proposal(held,set,item,key);}
function sDeskApply(held,set,items,button){return DESK_KIT.apply(held,set,items,button);}
function sDeskSkip(held,set,ids,button){return DESK_KIT.skip(held,set,ids,button);}
// The kit's wording for what an accept did, and why a retired suggestion no longer fits:
// Review mode says them too.
function deskFinishedSaid(done){return DESK_KIT.finishedSaid(done);}
function reviewNoLonger(item){return DESK_KIT.noLonger(item);}
// Feedback: comments shown in the panel and in their section cards, each a note in one click.
function sDeskCommentKey(view,part){return DESK_KIT.commentKey(view,part);}
function sDeskComments(held,part){return DESK_KIT.comments(held,part);}
function sDeskComment(held,set,item,inPanel){return DESK_KIT.comment(held,set,item,inPanel);}
function sDeskToNote(held,item){return DESK_KIT.toNote(held,item);}
// Quick check (proofread): in place, at once; Fix rewrites only the sentence a finding is in.
function sDeskProofread(held,button){return DESK_KIT.proofread(held,button);}
function sDeskProofView(held){return DESK_KIT.proofView(held);}
function sDeskFinding(held,finding){return DESK_KIT.finding(held,finding);}
// Before publishing: the pre-publish check, Repurpose into new blogs, and Google suggestions,
// each reading the desk's latest text.
function sDeskPublishView(held){
  const f=held.finish,p=f.publish||(f.publish={check:null,checkProblem:'',copy:{format:'linkedin',words:'150',audience:'',url:''},job:null,content:null,title:'',made:null,copyProblem:'',google:{mode:'auto'},plan:null,sent:null,googleProblem:''});
  return [sDeskPrepublishCard(held,p),sDeskGeoCard(held),sDeskRepurposeCard(held,p),sDeskGoogleCard(held,p)];
}
// The GEO review beside the pre-publish check: whether it is done, under way, waiting or out
// of date because the post changed, and Run GEO review, on every post at any time. An
// out-of-date review offers to run again; it never reruns by itself.
function sDeskGeoCard(held){
  const geo=held.view.geo_review||{status:'none'},working=held.view.working;
  const said={working:'Under way: the GEO review is reading the post.',done:geo.open?'Done: '+geo.open+(geo.open===1?' proposal waits':' proposals wait')+' in GEO: retrieval readiness.':'Done: nothing left to review.',stale:'Out of date: the post changed since the GEO review ran. Run it again for the latest.',waiting:geo.waiting==='draft'?'Waiting: it runs once the full draft is written.':geo.waiting==='review'?'Waiting: it runs once you have accepted or rejected the fixes in your text, so it reads the post as you left it.':'Waiting: it runs when the change under way ends.','not-run':geo.why==='conversation'?'Not run yet: this post’s work belongs to the conversation, so its GEO review does not run by itself here. Run GEO review to run it now.':'Not run yet. Run GEO review to run it now.',none:geo.include&&geo.due==='ran'?'No GEO review on this computer yet. This post’s one review already ran, so it does not run again by itself.':'No GEO review for this post yet.'}[geo.status]||'';
  const line=sNode('p',geo.status==='stale'?'decision-notice':'quiet',said);line.setAttribute('role','status');
  const again=geo.status==='done'||geo.status==='stale';
  const run=sButton(again?'Run GEO review again':'Run GEO review',button=>sDeskRunGeo(held,button),geo.status==='done'?'':'filled');run.disabled=!sDeskCan(held)||!!working;
  const open=again?sButton('Open the GEO review',()=>sDeskFinishTool(held,'geo')):null;
  return sCard('GEO review',sNode('p','quiet','Retrieval readiness: direct answers, clear entities and useful evidence, proposed for you to preview, then apply or skip.'+(geo.include?' This post includes one GEO review.':'')),line,
    geo.problem?sNode('p','problem','The last GEO review did not finish: '+geo.problem):null,
    working&&working.kind!=='finish-geo'?sNode('p','quiet','Another change is under way. This can run when it ends.'):null,
    sAdd(sNode('div','bar'),run,open));
}
// Run GEO review: one explicit job, then the GEO review opens to follow it.
async function sDeskRunGeo(held,button){await sDeskJob(held,button,'desk-finish',{tool:'geo'});if(held.finish&&held.view.working?.kind==='finish-geo')sDeskFinishTool(held,'geo');}
// Include a GEO review, the post's own choice, shown after the Reader aids and AI search tools.
const DESK_GEO_SAYS='Once the full draft is written and the fixes in your text are accepted or rejected, one GEO review runs as part of this post’s work, and its proposals wait in Finishing for you to preview, then apply or skip. Off, nothing GEO runs by itself. You can run one at any time.';
function sDeskGeoChoice(held){
  const state={on:!!held.view.geo_review?.include};
  const box=sCheck('desk-geo-include','Include a GEO review',state,'on',DESK_GEO_SAYS+' '+deskGeoDue(held.view.geo_review),async on=>{
    input.disabled=true;
    try{const before=held.view;held.view=await api('desk-geo-option',{id:held.id,include:on});const queued=held.view.working?.kind==='finish-geo';sToast(on?(queued?'A GEO review is under way for this post. Its proposals will wait in Finishing.':'This post includes a GEO review. It runs once the full draft is written.'):'No GEO review runs by itself for this post. You can still run one at any time.');sDeskRefresh(held,before);if(queued)sDeskWatch(held);}
    catch(error){state.on=!on;input.checked=!on;notice(error.message,true);}
    finally{input.disabled=!sDeskCan(held);}
  });
  box.className+=' desk-geo-choice';
  const input=box.querySelector('input');input.disabled=!sDeskCan(held);
  return box;
}
// What this post's GEO review does next, as the choice says it: on or off.
function deskGeoDue(geo){
  const due=(geo||{}).due||'now',on=!!(geo||{}).include;
  if(due==='ran')return on?'Its one GEO review has run.':'This post’s GEO review has already run, so turning this on runs nothing more.';
  if(due==='conversation')return 'This post’s work belongs to the conversation, so its GEO review does not run by itself here.';
  if(due==='draft')return on?'It runs once the full draft is written.':'Turned on, it runs once the full draft is written.';
  if(due==='busy')return on?'It runs when the change under way ends.':'Turned on, it runs when the change under way ends.';
  if(due==='review')return on?'It runs once you have accepted or rejected the fixes in your text.':'Turned on, it runs once you have accepted or rejected the fixes in your text.';
  return on?'It runs now.':'Turned on, it runs now.';
}
function deskSummarySaid(set,said){const summary=(set.summary||'').trim().replace(/\.+$/,'');if(summary)said.push(summary);}
// Quotes from sources: a draft with no sources yet is told so, with Add a source.
function sDeskQuotesOptions(held){
  if((held.view.source_names||[]).length)return [];
  const add=sButton('Add a source',()=>sDeskSourcesSheet(held));add.disabled=!sDeskCan(held);
  return [sAdd(sNode('div','decision-notice desk-problem'),sNode('p','','Quotations come only from your sources, word for word, and this draft has none yet.'),add)];
}
// What a tool's own view says about its job: working, another change under way, or why the
// last one did not finish.
function sDeskToolLines(held,key){
  const tool=deskTool(key),view=held.view,set=(view.finishing||{})[key],working=view.working,lines=[];
  if(working&&working.kind==='finish-'+key){const note=sNode('p','desk-working-note',tool.doing);note.setAttribute('role','status');lines.push(note);}
  else if(working)lines.push(sNode('p','quiet','Another change is under way. This can run when it ends.'));
  const last=(view.jobs||[]).filter(job=>job.kind==='finish-'+key).at(-1);
  if(last&&!last.busy&&last.error&&(!set||set.job!==last.id))lines.push(sNode('p','problem',last.error));
  return lines;
}
// An FAQ or key takeaways: a new section the person places, or the new form of the one the
// post has. Each question and answer (or point) can be edited or dropped (untick it), then
// all are added, or only the ticked ones. The preview shows exactly what goes in.
const DESK_SECTION_WORDS={faq:{row:'question',rows:'questions',empty:'No questions: the post and its sources do not answer enough reader questions for an FAQ.'},takeaways:{row:'takeaway',rows:'takeaways',empty:'No takeaways suggested.'}};
function sDeskSectionView(held,key){
  const tool=deskTool(key),view=held.view,f=held.finish,set=(view.finishing||{})[key],words=DESK_SECTION_WORDS[key];
  const open=set&&set.items.some(item=>item.state==='open'&&item.present);
  const parts=[sNode('p','quiet',tool.says)];
  if(key==='faq'&&set&&set.count&&f.faqCountFrom!==set.job){f.faqCount=String(set.count);f.faqCountFrom=set.job;}
  if(key==='faq')parts.push(sChoice('Questions',[['3','3'],['4','4'],['5','5'],['6','6']],f,'faqCount'));
  const run=sButton(set?tool.run+' again':tool.run,button=>sDeskJob(held,button,'desk-finish',{tool:key,...(key==='faq'?{count:Number(f.faqCount||5)}:{})}),open?'':'filled');run.disabled=!sDeskCan(held)||!!view.working;
  parts.push(sAdd(sNode('div','bar'),run),...sDeskToolLines(held,key));
  if(!set)return parts;
  if(set.summary)parts.push(sNode('p','quiet',set.summary));
  if(!set.items.length){parts.push(sNode('p','',words.empty));return parts;}
  for(const item of set.items)parts.push(sDeskSectionProposal(held,set,item,key));
  return parts;
}
function sDeskSectionPreview(key,heading,chosen){
  const box=sAdd(sNode('div','paper desk-side'),sNode('h4','sheet-part',heading));
  if(!chosen.length)return sAdd(box,sNode('p','quiet','(Nothing ticked)'));
  if(key==='faq'){for(const row of chosen)box.append(sAdd(sNode('p',''),sNode('strong','',row.question.trim())),sNode('p','',row.answer.trim()));return box;}
  const list=sNode('ul','');for(const row of chosen)list.append(sNode('li','',row.point.trim()));return sAdd(box,list);
}
function deskSectionText(key,rows){return key==='faq'?rows.map(row=>'**'+row.question.trim()+'**\n\n'+row.answer.trim()).join('\n\n'):rows.map(row=>'- '+row.point.trim()).join('\n');}
function sDeskSectionProposal(held,set,item,key){
  const f=held.finish,view=held.view,words=DESK_SECTION_WORDS[key],card=sNode('section','card desk-proposal');card.dataset.item=item.id;
  card.append(sAdd(sNode('div','desk-part-head'),sNode('h3','row-title',item.insert?'A new section: “'+item.heading+'”':'In '+deskPartName(view,item.part))));
  if(!item.insert)card.append(sNode('p','quiet','This post already has this section, so this proposes its new form rather than a second one.'));
  if(item.flag)card.append(sNode('p','decision-notice',item.flag));
  if(item.note)card.append(sNode('p','quiet',item.note));
  if(item.state!=='open'){card.append(sNode('p','quiet',item.state==='applied'?(item.insert?'Added as a new section. To take it out, remove it on the Outline tab.':'Applied. The earlier text is in History.'):'Skipped.'));return card;}
  const skip=sButton('Skip',button=>sDeskSkip(held,set,[item.id],button));skip.disabled=!sDeskCan(held);
  if(!item.present){card.append(sNode('p','quiet',item.insert?'The post changed since this was suggested, so it no longer fits. Run it again for the latest.':'The text changed since this was suggested, so it no longer fits.'),sAdd(sNode('div','bar'),skip));return card;}
  // The person's ticks, edits and place, kept for this proposal across redraws.
  const mark=set.job+':'+item.id+':'+item.after;f.rows=f.rows||{};f.places=f.places||{};
  const rows=f.rows[mark]||(f.rows[mark]=(key==='faq'?item.questions:item.points).map(row=>({...row,on:true})));
  if(item.insert&&!(mark in f.places))f.places[mark]=item.at;
  const ready=()=>rows.filter(row=>row.on&&(key==='faq'?row.question.trim()&&row.answer.trim():row.point.trim()));
  const list=sNode('div','desk-section-rows');
  rows.forEach((row,index)=>{
    const id='desk-'+key+'-'+item.id+'-'+index,box=sNode('div','desk-section-row');
    const tick=sCheck(id+'-on',key==='faq'?'Include question '+(index+1):'Include takeaway '+(index+1),row,'on',null,()=>show());
    if(key==='faq')sAdd(box,tick,sField(id+'-question','Question',row,'question',{max:300,changed:()=>show()}),sField(id+'-answer','Answer',row,'answer',{long:true,max:2000,changed:()=>show()}));
    else sAdd(box,tick,sField(id+'-point','Takeaway',row,'point',{max:300,changed:()=>show()}));
    list.append(box);
  });
  card.append(list);
  if(item.insert){
    const sections=view.sections||[],options=[];
    sections.forEach((section,index)=>options.push([section.id,index?'After “'+deskHeading(sections[index-1].heading)+'”':'After the opening']));
    options.push(['end',sections.length?'At the end, after “'+deskHeading(sections.at(-1).heading)+'”':'At the end']);
    const suggested=item.cta?'Suggested: before “'+deskHeading((sections.find(section=>section.id===item.cta)||{}).heading||'')+'”, the closing call to action.':item.at==='end'?'Suggested: at the end of the post.':'Suggested: after the opening.';
    card.append(sField('desk-'+key+'-place-'+item.id,'Where it goes',f.places,mark,{options,hint:suggested}));
  }
  const preview=sNode('div','desk-section-preview'),bar=sNode('div','bar'),said=sNode('p','quiet');said.setAttribute('aria-live','polite');
  card.append(sNode('h4','sheet-part','What goes in'),preview,said,bar);
  const add=(chosen,button)=>sDeskSectionAdd(held,set,item,key,mark,chosen,button);
  function show(){
    const chosen=ready(),all=rows.length,count=chosen.length;
    // A new section reads as it will in the post; a new form is compared with the one there.
    preview.replaceChildren(item.insert?sDeskSectionPreview(key,item.heading,chosen):deskSides(item.before,deskSectionText(key,chosen)));
    said.textContent=count===all?'All '+all+' '+(all===1?words.row:words.rows)+' go in.':count+' of '+all+' '+words.rows+' ticked.';
    const every=sButton((item.insert?'Add all':'Use all')+' ('+all+')',button=>add(rows.filter(row=>key==='faq'?row.question.trim()&&row.answer.trim():row.point.trim()),button),count&&count<all?'':'filled');
    every.disabled=!sDeskCan(held)||!!view.working||rows.some(row=>key==='faq'?!row.question.trim()||!row.answer.trim():!row.point.trim());
    const ticked=count&&count<all?sButton((item.insert?'Add the ticked':'Use the ticked')+' ('+count+')',button=>add(chosen,button),'filled'):null;if(ticked)ticked.disabled=!sDeskCan(held)||!!view.working;
    bar.replaceChildren(...[every,ticked,skip].filter(Boolean));
  }
  show();
  return card;
}
async function sDeskSectionAdd(held,set,item,key,mark,chosen,button){
  await busy(button,'Adding…',async()=>{
    try{
      await sDeskFlush(held);if(held.stale)return;
      const before=held.view,entry={id:item.id,after:deskSectionText(key,chosen),...(item.insert?{at:held.finish.places[mark]}:{})};
      held.view=await api('desk-apply',{id:held.id,seen:held.view.revision,job:set.job,items:[entry]});
      delete held.finish.rows[mark];
      sToast(item.insert?'Added “'+item.heading+'” as a new section. To take it out, remove it on the Outline tab.':'Updated “'+deskHeading((before.sections.find(section=>section.id===item.part)||{}).heading||'')+'”. The earlier text is in History.');
      sDeskRefresh(held,before);sDeskPanelShow(held);DESK_KIT.refocus(held);
    }catch(error){if(/changed since you opened/.test(error.message)){held.stale=true;DESK_KIT.stale(held);}else notice(error.message,true);}
  });
}
// Likely search questions: advice for the person, listed with Copy; nothing goes in the post.
function sDeskQueriesView(held){
  const tool=deskTool('queries'),view=held.view,set=(view.finishing||{}).queries;
  const run=sButton(set?tool.run+' again':tool.run,button=>sDeskJob(held,button,'desk-finish',{tool:'queries'}),set?'':'filled');run.disabled=!sDeskCan(held)||!!view.working;
  const parts=[sNode('p','quiet',tool.says),sAdd(sNode('div','bar'),run),...sDeskToolLines(held,'queries')];
  if(!set)return parts;
  const found=set.queries||[];
  if(!found.length){parts.push(sNode('p','',set.summary||'No questions listed: the post does not yet answer a question people ask.'));return parts;}
  const list=sNode('ul','look');for(const query of found)list.append(sNode('li','',query));
  parts.push(sNode('h3','sheet-part','Questions this post answers'),list,sNode('p','quiet','Advice for you: these are not added to the post. Use them to check the post answers each one plainly.'));
  if(set.summary)parts.push(sNode('p','quiet',set.summary));
  parts.push(sAdd(sNode('div','bar'),sButton('Copy the questions',async()=>{if(typeof navigator==='undefined'||!navigator.clipboard?.writeText)throw new Error('Select the questions and copy them.');await navigator.clipboard.writeText(found.join('\n'));sToast('Questions copied.');})));
  return parts;
}
function sDeskPrepublishCard(held,p){
  const run=sButton(p.check?'Check again':'Run the check',async button=>{await busy(button,'Checking…',async()=>{try{await sDeskFlush(held);p.check=await api('prepublish?id='+encodeURIComponent(held.id));p.checkProblem='';}catch(error){p.checkProblem=error.message;}sDeskPanelShow(held);});},'filled');
  const card=sCard('Pre-publish check',sNode('p','quiet','Headings, placeholders, links and evidence references in the latest text. Report only: nothing changes.'),sAdd(sNode('div','bar'),run));
  if(p.checkProblem)card.append(sNode('p','problem',p.checkProblem));
  if(p.check){const list=sNode('ul','look');for(const item of p.check.findings)list.append(sNode('li','','Line '+item.line+': '+item.detail));card.append(p.check.findings.length?list:sNode('p','','No findings from these checks.'),sNode('p','quiet',p.check.coverage||''));}
  return card;
}
function sDeskRepurposeCard(held,p){
  const card=sCard('Repurpose',sNode('p','quiet','Prepare channel copy from the latest text; each copy you keep becomes a new blog on the desk. An SEO meta description is kept with this post instead. Nothing is posted.'));
  const kept=held.view.meta_description;if(kept)card.append(sDeskMetaKept(kept));
  if(p.copyProblem)card.append(sNode('p','problem',p.copyProblem));
  if(p.made){card.append(sNode('p','','Made “'+p.made.title+'” as a new blog on the desk.'),sAdd(sNode('div','bar'),sButton('Open it',()=>sRoute('desk',p.made.id),'filled'),sButton('Prepare another',()=>{Object.assign(p,{job:null,content:null,title:'',made:null,copyProblem:''});sDeskPanelShow(held);})));return card;}
  const job=p.job;
  if(job&&['queued','working'].includes(job.status)){const note=sNode('p','desk-working-note','Preparing the copy…');note.setAttribute('role','status');card.append(note,sAdd(sNode('div','bar'),sButton('Cancel',async button=>{await busy(button,'Cancelling…',async()=>{try{p.job=await api('tool-action',{action:'job-control',job:job.id,control:'cancel'});}catch(error){p.copyProblem=error.message;}sDeskPanelShow(held);});})));sDeskRepurposeFollow(held,p);return card;}
  if(job&&job.status==='ready'&&job.metadata?.format==='meta')return sDeskMetaReady(held,p,card,job);
  if(job&&job.status==='ready'){
    if(p.content===null)p.content=job.result?.content||'';
    if(!p.title)p.title=held.view.title+' ('+((DESK_FORMATS.find(([key])=>key===job.metadata?.format)||[])[1]||'copy')+')';
    const make=sButton('Make it a new blog',async button=>{await busy(button,'Making…',async()=>{try{const shown=await api('desk-repurpose',{id:held.id,job:job.id,title:p.title.trim(),content:p.content});p.made=shown.made;p.copyProblem='';held.view=shown;sToast('Made a new blog on the desk. Nothing was posted.');}catch(error){p.copyProblem=error.message;}sDeskPanelShow(held);});},'filled');make.disabled=!sDeskCan(held);
    sAdd(card,sField('desk-copy','The prepared copy',p,'content',{long:true,max:200000}),sField('desk-copy-title','Title for the new blog',p,'title',{max:500}),job.result?.notes?sNode('p','quiet',job.result.notes):null,sAdd(sNode('div','bar'),make,sButton('Discard',()=>{Object.assign(p,{job:null,content:null,title:''});sDeskPanelShow(held);})));
    return card;
  }
  if(job&&job.error)card.append(sNode('p','problem',job.error));
  const prepare=sButton('Prepare copy',async button=>{await busy(button,'Starting…',async()=>{try{await sDeskFlush(held);p.job=await api('tool-action',{action:'job-create',kind:'repurpose',id:held.id,operation:operationId(),format:p.copy.format,words:Number(p.copy.words),audience:p.copy.audience,url:p.copy.url});p.content=null;p.title='';p.copyProblem='';}catch(error){p.copyProblem=error.message;}sDeskPanelShow(held);});},'filled');prepare.disabled=!sDeskCan(held);
  const meta=p.copy.format==='meta';
  if(meta)prepare.textContent='Write a meta description';
  sAdd(card,sField('desk-copy-format','Copy format',p.copy,'format',{options:DESK_FORMATS,changed:()=>{sDeskPanelShow(held);document.getElementById('desk-copy-format')?.focus();}}),meta?sNode('p','quiet field-hint','One line of up to '+DESK_META_LIMIT+' characters, from the post’s own claims. It is kept with this post.'):sField('desk-copy-words','Target words',p.copy,'words',{type:'number',min:30,maximum:1500}),sField('desk-copy-reader','Reader (optional)',p.copy,'audience',{max:2000}),meta?null:sField('desk-copy-url','Article URL (optional)',p.copy,'url',{max:2000}),sAdd(sNode('div','bar'),prepare));
  return card;
}
// How long a meta description is, said plainly: over the limit, by how much.
function sDeskMetaCount(text){const count=Array.from(String(text||'').trim()).length;return count>DESK_META_LIMIT?count+' characters: '+(count-DESK_META_LIMIT)+' over the '+DESK_META_LIMIT+' a meta description takes. Shorten it to keep it.':count+' of '+DESK_META_LIMIT+' characters';}
// The meta description kept with this post, to copy, and whether the post changed since.
function sDeskMetaKept(kept){
  const box=sAdd(sNode('div','desk-meta-kept'),sNode('h3','sheet-part','SEO meta description'),sNode('p','desk-plain',kept.text),sNode('p','quiet',kept.characters+' of '+kept.limit+' characters · kept with this post'));
  if(kept.out_of_date)box.append(sNode('p','decision-notice','The post changed after this description was written, so it may be out of date.'));
  return sAdd(box,sAdd(sNode('div','bar'),sButton('Copy the description',async()=>{if(typeof navigator==='undefined'||!navigator.clipboard?.writeText)throw new Error('Select the description and copy it.');await navigator.clipboard.writeText(kept.text);sToast('Meta description copied.');})));
}
// A meta description ready to review: edited in place with its count, then kept with this
// post (never a new blog), copied or discarded.
function sDeskMetaReady(held,p,card,job){
  if(p.content===null)p.content=(job.result?.content||'').trim();
  const count=sNode('p','quiet',sDeskMetaCount(p.content));count.setAttribute('aria-live','polite');
  const keep=sButton('Keep with this post',async button=>{await busy(button,'Keeping…',async()=>{try{held.view=await api('desk-meta',{id:held.id,job:job.id,content:p.content});Object.assign(p,{job:null,content:null,copyProblem:''});sToast('Meta description kept with this post. Nothing was published.');}catch(error){p.copyProblem=error.message;}sDeskPanelShow(held);});},'filled');
  const over=()=>Array.from(String(p.content||'').trim()).length>DESK_META_LIMIT||!String(p.content||'').trim();
  keep.disabled=!sDeskCan(held)||over();
  const field=sField('desk-meta','The meta description',p,'content',{long:true,max:1000,changed:()=>{count.textContent=sDeskMetaCount(p.content);keep.disabled=!sDeskCan(held)||over();}});
  const copy=sButton('Copy',async()=>{if(typeof navigator==='undefined'||!navigator.clipboard?.writeText)throw new Error('Select the description and copy it.');await navigator.clipboard.writeText(String(p.content||'').trim());sToast('Meta description copied.');});
  return sAdd(card,field,count,job.result?.notes?sNode('p','quiet',job.result.notes):null,sAdd(sNode('div','bar'),keep,copy,sButton('Discard',()=>{Object.assign(p,{job:null,content:null});sDeskPanelShow(held);})));
}
function sDeskRepurposeFollow(held,p){
  if(p.following)return;p.following=true;
  setTimeout(async()=>{
    p.following=false;if(!sDeskCurrent(held)||held.finish?.publish!==p||!p.job)return;
    try{p.job=await api('tool-job?job='+encodeURIComponent(p.job.id));}catch(error){p.copyProblem=error.message;}
    if(held.finish?.tool==='publish')sDeskPanelSync(held,true);
    if(['queued','working'].includes(p.job?.status))sDeskRepurposeFollow(held,p);
  },DESK_POLL);
}
// What a plan sends to the Google Doc, said plainly: every desk change goes as a suggestion or
// a comment; one in a paragraph still waiting on an earlier suggestion goes next time.
function sDeskGoogleSaid(plan){
  const n=plan.suggestions??plan.count,m=plan.comments||0,parts=[];
  if(n)parts.push(n+(n===1?' suggestion':' suggestions'));
  if(m)parts.push(m+(m===1?' comment':' comments'));
  let said=parts.join(' and ')+(n+m===1?' goes':' go')+' to the Google Doc.';
  // Comments fallback: Google cannot take suggestions here, so each change is a comment.
  if(plan.mode==='comments')said=(n+m)+(n+m===1?' change goes':' changes go')+' to the Google Doc as comments: it cannot take suggestions, so its owner makes each change by hand.';
  else if(n)said+=' Its owner accepts or rejects each suggestion.';
  if(plan.waiting)said+=' '+plan.waiting+(plan.waiting===1?' change waits':' changes wait')+' for the Doc’s owner to decide the earlier suggestion in its paragraph, and '+(plan.waiting===1?'goes':'go')+' next time.';
  if(plan.sent_before)said+=' '+plan.sent_before+(plan.sent_before===1?' change was':' changes were')+' sent before.';
  if(plan.doc_overlap)said+=' '+plan.doc_overlap+' of these '+(plan.doc_overlap===1?'changes':'change')+' words a Doc suggestion also changes, so '+(plan.doc_overlap===1?'it goes':'they go')+' as '+(plan.doc_overlap===1?'a comment':'comments')+'; the Doc’s suggestion stays for its owner.';
  if(plan.later)said+=' '+plan.later+(plan.later===1?' note goes':' notes go')+' with the next send (nearby paragraphs already have changes).';
  if(plan.left)said+=' '+plan.left+(plan.left===1?' change':' changes')+' could not be placed in the Doc: pull the latest Doc and check again.';
  return said;
}
function sDeskGoogleItem(item){
  const quote=text=>'“'+text+'”',short=text=>text.length>80?text.slice(0,79).trimEnd()+'…':text,before=String(item.before||''),after=String(item.after||'');
  if(item.kind==='comment')return 'Comment on '+quote(before)+': '+item.reason;
  if(item.remove||!after.trim())return 'Removes '+quote(before.trim()||before);
  const lines=text=>text.split('\n').map(line=>line.trim()).filter(Boolean);
  if(after.includes('\n')&&after.startsWith(before)){
    // A new paragraph after the words named: said with the end of the paragraph it follows.
    const context=String(item.context||''),at=context.indexOf(before),end=at<0?-1:at+before.length,lead=end>0?(end>32?'…':'')+context.slice(Math.max(0,end-32),end).trim():before.trim();
    const added=lines(after.slice(before.length));
    return 'Adds '+(added.length===1?'a paragraph':added.length+' paragraphs')+' after '+quote(lead)+': '+quote(short(added.join(' ')));
  }
  if(after.includes('\n')){const [first,...rest]=lines(after);return 'Changes '+quote(before)+' to '+quote(first||'')+(rest.length?', then adds '+quote(short(rest.join(' '))):'');}
  return quote(before)+' → '+quote(after);
}
function sDeskGoogleCard(held,p){
  const view=held.view,card=sCard('Send to Google Doc as suggestions');
  if(!view.google_suggestions&&!view.google?.url){const make=sButton('Make a Google Doc',()=>sDeskMakeDoc(held));make.disabled=!sDeskCan(held);card.append(sNode('p','','This blog has no Google Doc yet. Make a private one of this draft, and later desk changes are sent to it as suggestions for you to accept.'),sAdd(sNode('div','bar'),make));return card;}
  if(!view.google_suggestions){card.append(sNode('p','','This blog’s Google Doc cannot take suggestions yet: it has no confirmed copy of the draft to compare with.'));return card;}
  card.append(sNode('p','quiet','Every desk change goes to the Google Doc: words and paragraphs as suggestions its owner accepts or rejects, and a link’s address, formatting or an image as a comment. Once the owner has decided them, Bring accepted changes takes the Doc’s text back to the desk.'));
  const docSaid=sDeskDocWords(view);if(docSaid)card.append(sNode('p','',docSaid));
  if(view.google?.url){const doc=link(view.google.url,'Open the Google Doc ↗');card.append(sAdd(sNode('p',''),doc));}
  if(p.googleProblem)card.append(sNode('p','problem',p.googleProblem));
  const check=sButton(p.plan?'Check again':'Check what would be sent',async button=>{await busy(button,'Checking…',async()=>{try{await sDeskFlush(held);p.plan=await api('desk-google-plan',{id:held.id,mode:p.google.mode});p.sent=null;p.googleProblem='';}catch(error){p.plan=null;p.googleProblem=error.message;}sDeskPanelShow(held);});},p.plan?'quiet':'filled');check.disabled=!sDeskCan(held);
  if(p.sent){card.append(sStatus(['verified-pending','verified-comments'].includes(p.sent.status)?'done':'late',p.sent.message));const verified=sDeskVerifiedLine(p.sent.verified);if(verified)card.append(verified,...[sDeskVerifyAgain(held)].filter(Boolean));}
  if(p.plan&&!p.sent){
    const changes=sNode('ul','look');for(const item of p.plan.proposals||[])changes.append(sNode('li','',sDeskGoogleItem(item)));
    const send=sButton('Send to Google Doc',async button=>{await busy(button,'Sending…',async()=>{try{const result=await api('desk-google-send',{id:held.id,plan:p.plan.plan,confirmed:true});p.sent={status:result.status,message:sDeskSentWords(p.plan,result),verified:sDeskVerifiedWords(result)};p.googleProblem='';await sDeskReread(held);}catch(error){p.googleProblem=error.message;if(/changed/.test(error.message))p.plan=null;}sDeskPanelShow(held);});},'filled');send.disabled=!sDeskCan(held);
    card.append(sNode('p','',sDeskGoogleSaid(p.plan)),disclosure('What would be sent',changes),sAdd(sNode('div','bar'),send,check));
    return card;
  }
  if(p.sent&&!['verified-pending','verified-comments'].includes(p.sent.status)&&p.plan){card.append(sAdd(sNode('div','bar'),sButton('Check delivery',async button=>{await busy(button,'Checking…',async()=>{try{const result=await api('desk-google-send',{id:held.id,plan:p.plan.plan,confirmed:true});p.sent={status:result.status,message:sDeskSentWords(p.plan,result),verified:sDeskVerifiedWords(result)};}catch(error){p.googleProblem=error.message;}sDeskPanelShow(held);});},'filled')));return card;}
  const bring=sButton('Bring accepted changes',()=>sDeskGoogleBring(held));bring.disabled=!sDeskCan(held);
  card.append(sField('desk-google-mode','Send as',p.google,'mode',{options:[['auto','Suggestions, with comments fallback'],['native','Suggestions only'],['comments','Comments only']]}),sAdd(sNode('div','bar'),check,bring));
  return card;
}

// Review mode ("Check spelling and grammar"): where polishing a draft lands. Copy edit runs on
// its own, and when the person asked for more human-sounding wording Humanize follows it at the
// chosen strength, queued once Copy edit settles; the fixes can be accepted while it looks. The
// draft then reads section by section with the suggestions from both marked in place, in
// reading order, each with a small label (Spelling, Grammar, Punctuation, Wording or Sounds
// human), struck words out and highlighted words in, its reason under the paragraph, and Accept
// or Reject on each. A wording fix may offer alternatives to pick from before Accept. Accept is
// Finishing's apply, keeping a version; every other suggestion stays independent unless the
// accepted one changed its words: one with them inside its own takes them in, its marks
// updated in place, and one whose words are gone no longer fits and names the suggestion that
// changed them. Reject sets one aside. A flagged suggestion (it changes a fact, code or shape)
// waits to be checked one by one. Any paragraph can be clicked and edited in place; it saves after a
// short pause or when focus leaves it, and a suggestion whose words are no longer in the text
// drops out. Every text is set with textContent.
const REVIEW_CHECKING='Checking spelling and grammar…',REVIEW_HUMAN='Looking for machine-like wording…';
const REVIEW_HUMAN_SAYS='Rewrites for sentences that read as machine-written, mixed in with the fixes, each yours to accept or reject.';
const REVIEW_TOOLS=['copyedit','humanize'];
// A copy edit's kind as its label: consistency is one name, term or style written two ways.
const REVIEW_KINDS={spelling:'Spelling',grammar:'Grammar',punctuation:'Punctuation',consistency:'Consistency',wording:'Wording'};
const REVIEW_PROOF_WAIT=4000;  // Quick check is read again this long after the text last changed.
const REVIEW_SHOW=[['all','All'],['fixes','Fixes'],['human','Sounds human']];
const REVIEW_INLINE=/(\*\*|__)(?=\S)([^\n]*?\S)\1|(?<![*\w])\*(?=[^\s*])([^*\n]*?[^\s*])\*(?![*\w])|`([^`\n]+)`|!\[[^\[\]\n]*\]\[[^\[\]\n]*\]|!\[[^\[\]\n]*\]\([^)\n]*\)|\[([^\[\]\n]+)\]\(([^)\s]+)[^)\n]*\)|\\([\\`*_{}\[\]()#+\-.!<>|~])/g;
function deskHeading(text){return String(text||'').replace(/^(\*\*|__)(.+)\1$/,'$2');}
function sReviewOn(held){held.mode='review';const r=held.review=held.review||{editing:null,parts:{},google:null};r.picks=r.picks||{};r.dismissed=r.dismissed||{};r.filter=r.filter||'all';sDeskModeUrl(held);}
// A suggestion's small label: a copy edit's kind, or Humanize's own.
function reviewLabel(item){return item.tool==='humanize'?'Sounds human':REVIEW_KINDS[item.kind]||'Grammar';}
// Whether a suggestion can be accepted now: nothing works on the draft, or only a Finishing
// tool does (Humanize looking while Copy edit's fixes wait), which changes no part.
function sReviewFree(held){const job=held.view.working;return !job||job.part==='finishing';}
// Accept's request for one suggestion: the alternative picked, if one was.
function sReviewPick(item){return {id:item.id,...(Number.isInteger(item.picked)?{alternative:item.picked}:{})};}
// The desk's address says which view is shown, without a new history entry.
function sDeskModeUrl(held){const review=held.mode==='review';if(studio.screen!=='desk'||(studio.stage==='review')===review)return;studio.stage=review?'review':null;const query=new URLSearchParams(location.search);query.set('screen','desk');query.set('id',held.id);if(review)query.set('stage','review');else query.delete('stage');history.replaceState(null,'',location.pathname+'?'+query);}
// Markdown as plain reading: bold, emphasis, code and link words shown, list marks as bullets,
// image references left to their thumbnails. `lineStart` says whether the text starts a line.
// Other people's suggestions pending in the blog's Google Doc: shown where they sit, never
// ours to accept or reject, and never counted or numbered with our fixes.
const DOC_OVERLAP='A Doc suggestion also changes these words; accepting this makes it moot.';
const DOC_NOTE='Suggested in the Doc. Decide it in Google Docs.';
function sDocPendingLine(count){const line=sNode('p','quiet doc-pending',(count===1?'1 suggestion is':count+' suggestions are')+' pending in the Google Doc. Decide them there; nothing to do here.');line.dataset.doc='count';return line;}
// The key to the Doc's marks, shown beside the count: no hover needed, on a phone too.
function sDocKey(){const key=sAdd(sNode('p','quiet doc-key'),sAdd(sNode('span','doc-suggestion doc-key-mark'),sNode('ins','doc-inserted','Marked like this')),document.createTextNode(': waiting in the Google Doc. Decide it there.'));key.dataset.doc='key';return key;}
function sDocMark(text,mark){
  const node=sNode('span','doc-suggestion');node.title=DOC_NOTE;node.tabIndex=0;node.dataset.doc=mark.id||'';node.setAttribute('aria-label',DOC_NOTE);
  const removed=text.slice(mark.at,mark.at+mark.length);
  if(removed)node.append(sNode('del','doc-removed',removed));
  if(mark.inserted)node.append(sNode('ins','doc-inserted',mark.inserted));
  return node;
}
function sDocInline(view,part,text,from,to){
  const out=[],marks=(view.doc_suggestions?.marks||[]).filter(mark=>mark.part===part&&mark.at>=from&&mark.at+mark.length<=to).sort((a,b)=>a.at-b.at);
  let at=from;
  for(const mark of marks){
    if(mark.at<at)continue;
    if(mark.at>at)out.push(...reviewInline(text.slice(at,mark.at),at===0||text[at-1]==='\n'));
    out.push(sDocMark(text,mark));at=mark.at+mark.length;
  }
  if(to>at)out.push(...reviewInline(text.slice(at,to),at===0||text[at-1]==='\n'));
  return out;
}
function reviewInline(text,lineStart=true){
  const out=[];
  String(text).split('\n').forEach((line,index)=>{
    if(index)out.push(document.createTextNode('\n'));
    if(index||lineStart)line=line.replace(/^([ \t]*)[*+-][ \t]+/,'$1• ').replace(/^#{1,6}[ \t]+/,'');
    let at=0;
    for(const found of line.matchAll(REVIEW_INLINE)){
      if(found.index>at)out.push(document.createTextNode(line.slice(at,found.index)));
      if(found[2]!==undefined)out.push(sNode('strong','',found[2]));
      else if(found[3]!==undefined)out.push(sNode('em','',found[3]));
      else if(found[4]!==undefined)out.push(sNode('code','',found[4]));
      else if(found[5]!==undefined){const word=sNode('span','review-link',found[5]);word.title=found[6];out.push(word);}
      else if(found[7]!==undefined)out.push(document.createTextNode(found[7]));
      at=found.index+found[0].length;
    }
    if(at<line.length)out.push(document.createTextNode(line.slice(at)));
  });
  return out;
}
// Where blocks (paragraphs) of a part's text start and end: at blank lines, but never inside
// fenced code or inside a fix's words.
function reviewBlocks(text,marks){
  const fenced=[];let open=null,offset=0;
  for(const line of text.split('\n')){if(/^ {0,3}(`{3,}|~{3,})/.test(line)){if(open===null)open=offset;else{fenced.push([open,offset+line.length]);open=null;}}offset+=line.length+1;}
  if(open!==null)fenced.push([open,text.length]);
  const inside=(at,ranges)=>ranges.some(([from,to])=>at>from&&at<to);
  const spans=marks.map(item=>[item.at,item.at+item.before.length]),blocks=[];let start=0;
  for(const found of text.matchAll(/\n[ \t]*\n\s*/g)){if(inside(found.index,fenced)||inside(found.index,spans))continue;blocks.push({start,end:found.index});start=found.index+found[0].length;}
  blocks.push({start,end:text.length});
  return blocks.filter(block=>block.end>block.start||!text).map(block=>({...block,text:text.slice(block.start,block.end)}));
}
// The newest Copy edit, and Humanize when it is on, and what is left of them: open suggestions
// whose words are still in the text, placed where they sit, in reading order (by part, then
// by place in it) and numbered across both; the flagged ones; the gone and retired ones. A
// suggestion keeps its number while its set is shown, so a number still names the one
// accepted: a retired suggestion says which one changed its words, a carried one which it fits.
function sReviewState(held){
  // Humanize is shown with Copy edit when the review asked for it, or when its rewrites from
  // Finishing were opened here to accept or reject.
  const view=held.view,finishing=view.finishing||{},human=view.review?.humanize||(held.reviewHuman&&finishing.humanize?finishing.humanize.level||'light':null),r=held.review||{};
  const kind=view.working?.kind,working=kind==='finish-copyedit'||kind==='finish-humanize'?view.working:null;
  const parts=['title','opening',...(view.sections||[]).map(section=>section.id)];
  // While Copy edit checks, nothing from the check before is shown; while Humanize looks, the
  // fixes Copy edit just found are, to accept or reject meanwhile.
  const hidden=tool=>!!working&&(kind==='finish-copyedit'||kind==='finish-'+tool);
  const sets=REVIEW_TOOLS.map(tool=>[tool,tool==='humanize'&&!human?null:finishing[tool]||null]).filter(([tool,set])=>set&&!hidden(tool));
  const pending=[],gone=[];
  for(const [tool,set] of sets)for(const item of set.items){
    const row={...item,tool,job:set.job,key:tool+':'+set.job+':'+item.id};
    if(item.state==='retired'){gone.push(row);continue;}  // Another accepted change took its words.
    if(item.state!=='open')continue;
    const text=deskTextOf(view,item.part),at=item.present&&parts.includes(item.part)?text.indexOf(item.before):-1;
    if(at<0||!('after' in item)){gone.push(row);continue;}
    // The wording picked from a fix's alternatives, with its own flag.
    const pick=r.picks?.[row.key],alternative=Number.isInteger(pick)?(item.alternatives||[])[pick]:null;
    pending.push({...row,at,base:item.after,baseFlag:item.flag||'',...(alternative?{picked:pick,after:alternative.after,flag:alternative.flag||''}:{})});
  }
  pending.sort((a,b)=>parts.indexOf(a.part)-parts.indexOf(b.part)||a.at-b.at||REVIEW_TOOLS.indexOf(a.tool)-REVIEW_TOOLS.indexOf(b.tool));
  // Words a suggestion still pending in the Google Doc also changes: allowed, and said, and
  // Accept all leaves it for you. The Doc's own suggestions are never numbered or counted.
  const doc=view.doc_suggestions||{count:0,marks:[]};
  for(const item of pending)if(doc.marks.some(mark=>mark.part===item.part&&mark.at<=item.at+item.before.length&&mark.at+mark.length>=item.at))item.docFlag=DOC_OVERLAP;
  // A set that is no longer shown takes its numbers with it; a set that lands later (Humanize
  // after Copy edit's fixes) is numbered after the ones already shown, which keep theirs.
  const shownSets=new Set(sets.map(([tool,set])=>tool+':'+set.job+':'));
  const numbers=r.numbers=Object.fromEntries(Object.entries(r.numbers||{}).filter(([key])=>shownSets.has(key.slice(0,key.lastIndexOf(':')+1))));
  let next=Math.max(0,...Object.values(numbers));
  for(const item of pending)item.number=numbers[item.key]??(numbers[item.key]=++next);
  const number=ref=>{const tool=sets.find(([,set])=>set.job===ref?.job)?.[0];return tool?numbers[tool+':'+ref.job+':'+ref.id]||null:null;};
  for(const item of pending)if(item.carried?.length)item.carriedBy=item.carried.map(number);
  for(const item of gone)if(item.retired_by)item.byNumber=number(item.retired_by);
  const filter=human&&REVIEW_SHOW.some(([value])=>value===r.filter)?r.filter:'all',fits=tool=>filter==='all'||(filter==='human')===(tool==='humanize');
  const shown=pending.filter(item=>fits(item.tool));
  // A check that did not finish: Copy edit's, and Humanize's when it came after it.
  const jobs=view.jobs||[],failed=[],copy=jobs.filter(job=>job.kind==='finish-copyedit').at(-1);
  for(const tool of REVIEW_TOOLS){
    if(hidden(tool)||tool==='humanize'&&!human)continue;
    const last=jobs.filter(job=>job.kind==='finish-'+tool).at(-1);
    if(tool==='humanize'&&last&&copy&&jobs.indexOf(last)<jobs.indexOf(copy))continue;
    if(last&&!last.busy&&last.error&&(!finishing[tool]||finishing[tool].job!==last.id))failed.push([tool,last.error]);
  }
  if(human&&!working&&view.review?.problem)failed.push(['humanize',view.review.problem]);
  const all=sets.flatMap(([,set])=>set.items);
  return {sets,working,human,parts,pending,shown,filter,fits,gone,doc,ready:shown.filter(item=>!item.flag&&!item.docFlag),flagged:shown.filter(item=>item.flag),overlapping:shown.filter(item=>item.docFlag&&!item.flag),failed,any:sets.length>0,total:all.length,applied:all.filter(item=>item.state==='applied').length};
}
// Drawn again only when what it shows changes, so a poll never swaps a button being pressed.
function sReviewToolbar(held,state,force=false){
  const ran=state.any||!!state.working||state.failed.length>0,view=held.view;
  const key=JSON.stringify([view.title,state.working?.kind||null,!!view.working,sDeskCan(held),sNarrow(),ran,view.google?.url||'',!!view.google_suggestions,sDeskDocWords(view),view.publication||'']);
  if(!force&&held.review?.toolbarKey===key&&studio.screen==='desk')return;if(held.review)held.review.toolbarKey=key;
  // Before any check there is one way to start it, in the page: no Check again.
  const again=ran?sButton('Check again',button=>sReviewCheck(held,button)):null;if(again)again.disabled=!sDeskCan(held)||!!view.working;
  const full=sButton('Edit everything',()=>sReviewLeave(held,'full'));
  sFrame(view.title,sFold([again,full,...sDeskShareActions(held)]),state.working?sReviewDoing(state):sDeskDocWords(view)||'Check spelling and grammar',()=>sReviewLeave(held));
}
// What the check under way is doing, said in the toolbar and above the draft.
function sReviewDoing(state){return state.working?.kind==='finish-humanize'?REVIEW_HUMAN:REVIEW_CHECKING;}
function sDeskReview(held,keep=null){
  sReviewOn(held);const state=sReviewState(held);sReviewToolbar(held,state,true);held.layout=sDeskLayout();held.cards=null;held.wholeCard=null;held.wholeGo=null;
  const status=sNode('p','quiet desk-save-state');status.setAttribute('role','status');status.setAttribute('aria-live','polite');held.status=status;
  if(held.stale)sDeskStale(held);else status.textContent=held.saved||'';
  held.review.head=sReviewHead(held,state);held.review.headKey=sReviewHeadKey(held,state);held.review.paper=sReviewPaper(held,state);
  held.review.lede=sNode('p','lede',sReviewLede(state));
  held.bench=sDeskBench(held);
  sPage(held.bench,held.review.lede,status,sActivityNow(held.view.activity,{id:held.id}),held.review.head,held.review.paper,sActivityLog({id:held.id}));
  sDeskImagesLoad(held);sReviewProof(held);sReviewFocusAfter(held,keep);
}
// What needs the person first: the check under way, a problem, the count with Accept all and
// Reject all, or, once nothing is left, where the draft goes next.
function sReviewHead(held,state){
  const head=sNode('div','review-head'),editable=sDeskCan(held)&&sReviewFree(held),noun=state.human?['suggestion','suggestions']:['fix','fixes'];
  const voice=held.view.review?.voice_guide;if(voice)head.append(sNode('p','quiet','Voice guide: '+voice.name+' · revision '+voice.revision+'. Wording changes are suggestions; nothing is applied automatically.'));
  if(held.review?.pendingVoice){const selected=held.review.pendingVoice;head.append(sCard('Use your selected voice',sNode('p','quiet',selected.name+'. This Doc was already on the desk. Start a new check to use the voice you selected; the existing review is kept until then.'),sButton('Polish with the selected voice',button=>sReviewCheck(held,button,selected.humanize,selected.guide),'filled')));}
  if(state.working){
    // One status box for what the person is waiting on: what is being done, in which step,
    // what it is doing this moment, and Stop. The page's own lede and activity lines give
    // way to it while it shows (blog.css), so nothing says the same thing twice.
    const human=state.working.kind==='finish-humanize',steps=state.human?(human?'Step 2 of 2: the wording check. The copy edit is done and its fixes are in your text.':'Step 1 of 2: the copy edit. The wording check follows by itself.'):'';
    const line=sNode('h2','desk-working-note review-status-title',sReviewDoing(state));line.setAttribute('role','status');
    const stop=sButton('Stop',async button=>{await busy(button,'Stopping…',async()=>{try{const before=held.view;held.view=await api('desk-stop',{id:held.id,job:state.working.id});sDeskRefresh(held,before);}catch(error){notice(error.message,true);}});});stop.disabled=!sDeskCan(held);sReviewMark(stop,'stop');
    const label=sNode('p','move-label','Working now · nothing for you to do');
    head.append(sAdd(sNode('div','card review-checking review-status'),label,line,steps?sNode('p','review-status-step',steps):null,sNode('p','quiet',sReviewLede(state)),sActivityNow(held.view.activity,{id:held.id}),sAdd(sNode('div','bar'),stop)));
  }else if(held.view.working){const line=sNode('p','desk-working-note',sDeskStatusWords(held));line.setAttribute('role','status');head.append(line);}  // A Quick check Fix, say.
  state.failed.forEach(([tool,error],index)=>{
    const said=sAdd(sNode('div','decision-notice desk-problem'),sNode('p','',(tool==='humanize'?'The check for machine-like wording did not finish: ':'The check did not finish: ')+error));
    if(!state.working&&index===state.failed.length-1){const again=sButton('Check again',button=>sReviewCheck(held,button),'filled');again.disabled=!sDeskCan(held);said.append(sReviewMark(again,'check-again'));}
    head.append(said);
  });
  if(!state.any&&!state.working&&!state.failed.length)return sAdd(head,state.doc.count?sDocPendingLine(state.doc.count):null,state.doc.count?sDocKey():null,sReviewStart(held));
  if(state.pending.length){
    const count=sNode('p','review-count',state.pending.length+' '+noun[state.pending.length===1?0:1]+' to review');count.setAttribute('role','status');count.tabIndex=-1;sReviewMark(count,'count');
    const all=sButton('Accept all ('+state.ready.length+')',button=>sReviewAcceptAll(held,state.ready.map(item=>item.key),button),'filled');all.disabled=!editable||!state.ready.length;sReviewMark(all,'accept-all');
    const open=state.sets.filter(([tool])=>state.fits(tool)).flatMap(([,set])=>set.items.filter(item=>item.state==='open').map(item=>({job:set.job,id:item.id})));
    const none=sButton('Reject all',button=>sReviewRejectAll(held,open,button));none.disabled=!sDeskCan(held)||!open.length;sReviewMark(none,'reject-all');
    const both=state.pending.some(item=>item.tool==='humanize')&&state.pending.some(item=>item.tool!=='humanize');
    const filter=state.human&&(both||state.filter!=='all')?sReviewFilter(held):null;
    const flagged=state.flagged.length?sNode('p','quiet',state.flagged.length===1?'1 '+noun[0]+' changes a fact, code or the shape of a part, so Accept all leaves it for you to check.':state.flagged.length+' '+noun[1]+' change a fact, code or the shape of a part, so Accept all leaves them for you to check.'):null;
    const overlap=state.overlapping.length?sNode('p','quiet',state.overlapping.length===1?'1 '+noun[0]+' changes words a Doc suggestion also changes, so Accept all leaves it for you.':state.overlapping.length+' '+noun[1]+' change words a Doc suggestion also changes, so Accept all leaves them for you.'):null;
    sAdd(head,sAdd(sNode('div','card review-tally'),count,sAdd(sNode('div','bar'),all,none)),filter,flagged,overlap);
  }else if(state.any&&!state.working)head.append(sReviewDone(held,state));
  if(state.doc.count)head.append(sDocPendingLine(state.doc.count),sDocKey());
  const kept=sDeskKeptLine(held.view);if(kept)head.append(kept);
  return sAdd(head,sReviewQuick(held,state));
}
// Before the first check: Check spelling and grammar, and whether to suggest more
// human-sounding wording too, at a strength. The choice is kept for Check again.
function sReviewStart(held){
  const r=held.review,pinned=held.view.review?.humanize||null,ask=r.ask||(r.ask={on:!!pinned,level:pinned||'light',voiceOn:!!held.view.review?.voice_guide,voiceGuide:held.view.review?.voice_guide?.id||''});
  const strength=sReviewMarks(sChoice('Strength',DESK_LEVELS,ask,'level'),'strength:');strength.hidden=!ask.on;
  const go=sButton('Check spelling and grammar',button=>{if(ask.voiceOn&&!ask.voiceGuide)return notice('Choose a voice guide, or turn Use a voice guide off.',true);return sReviewCheck(held,button,ask.on?ask.level:null,ask.voiceOn?ask.voiceGuide:null);},'filled');go.disabled=!sDeskCan(held);sReviewMark(go,'check');
  const tick=sCheck('review-humanize','Also suggest more human-sounding wording',ask,'on',REVIEW_HUMAN_SAYS,on=>{strength.hidden=!on;});sReviewMark(sReviewFindTag(tick,'input'),'review-humanize');
  return sCard('Check spelling and grammar',sNode('p','','Each fix is marked in your text for you to accept or reject.'),tick,strength,sPolishVoiceChoice(ask,'review'),sAdd(sNode('div','bar'),go));
}
// A segmented choice's buttons, each marked to keep focus by its words.
function sReviewMarks(box,prefix){for(const button of sReviewAll(box,'button'))sReviewMark(button,prefix+button.textContent);return box;}
function sReviewAll(node,tag){const out=[];for(const child of node?.children||[]){if(String(child.tagName).toLowerCase()===tag)out.push(child);out.push(...sReviewAll(child,tag));}return out;}
function sReviewFindTag(node,tag){return sReviewAll(node,tag)[0]||null;}
// Show: All · Fixes · Sounds human. Accept all and Reject all act on what is shown.
// Changing it draws the head and the parts again, focus kept on the choice.
function sReviewFilter(held){const box=sReviewMarks(sChoice('Show',REVIEW_SHOW,held.review,'filter',value=>sReviewShown(held,value)),'show:');box.className+=' review-filter';return box;}
function sReviewShown(held,value){
  const r=held.review,label=(REVIEW_SHOW.find(([key])=>key===value)||[])[1];r.focusNext='show:'+label;
  const state=sReviewState(held);sReviewHeadReplace(held,state);
  for(const part of state.parts)if(r.parts[part]&&r.editing?.part!==part)sReviewPartShow(held,part);
}
function sReviewDone(held,state){
  const noun=state.human?['suggestion','suggestions']:['fix','fixes'];
  const said=state.total?'Accepted '+state.applied+' of '+state.total+' '+noun[state.total===1?0:1]+'.':'No '+noun[1]+' were needed.';
  const summary=sReviewMark(sNode('p','',said+' Every accepted '+noun[0]+' kept the earlier text in History.'),'done');summary.tabIndex=-1;
  const card=sCard('Nothing left to review',summary);card.className+=' review-done';
  if(held.view.google_suggestions)return sAdd(card,...sReviewGoogle(held));
  const copy=sButton('Copy',async()=>{if(typeof navigator==='undefined'||!navigator.clipboard?.writeText)throw new Error('Download the draft and copy it from there.');const found=await sDeskMarkdown(held);await navigator.clipboard.writeText(found.markdown);sToast(deskWithout('Markdown copied',found.missing));},'filled');
  const download=sButton('Download',async()=>{const found=await sDeskMarkdown(held);await sDownload({content:found.markdown,name:'DRAFT.md'});if(found.missing.length)sToast(deskWithout('Downloaded',found.missing));});
  return sAdd(card,sAdd(sNode('div','bar'),copy,download));
}
// The accepted fixes, and any paragraph edited here, go to the Google Doc as suggestions for
// its owner: the plan says how many first, and nothing is sent until Send.
function sReviewGoogle(held){
  const g=held.review.google||(held.review.google={plan:null,sent:null,problem:''}),out=[];
  if(g.problem)out.push(sNode('p','problem',g.problem));
  if(g.sent){out.push(sStatus(['verified-pending','verified-comments'].includes(g.sent.status)?'done':'late',g.sent.message));const verified=sDeskVerifiedLine(g.sent.verified);if(verified)out.push(verified,...[sDeskVerifyAgain(held)].filter(Boolean));if(held.view.google?.url)out.push(sAdd(sNode('p',''),link(held.view.google.url,'Open the Google Doc ↗')));return out;}
  if(g.plan){
    const changes=sNode('ul','look');for(const item of g.plan.proposals||[])changes.append(sNode('li','',sDeskGoogleItem(item)));
    const count=g.plan.count;
    const send=sButton('Send '+count+(count===1?' change':' changes'),async button=>{await busy(button,'Sending…',async()=>{try{const result=await api('desk-google-send',{id:held.id,plan:g.plan.plan,confirmed:true});g.sent={status:result.status,verified:sDeskVerifiedWords(result),message:['verified-pending','verified-comments'].includes(result.status)?sDeskSentWords(g.plan,result):'The result is not yet verified. Check delivery in Finishing, under Edit everything, before trying anything else.'};g.problem='';await sDeskReread(held);}catch(error){g.problem=error.message;if(/changed/.test(error.message))g.plan=null;}sReviewHeadShow(held);});},'filled');send.disabled=!sDeskCan(held);
    out.push(sNode('p','',sDeskGoogleSaid(g.plan)),disclosure('What would be sent',changes),sAdd(sNode('div','bar'),send,sButton('Cancel',()=>{g.plan=null;sReviewHeadShow(held);})));
    return out;
  }
  const plan=sButton('Review changes to send',async button=>{await busy(button,'Checking…',async()=>{try{await sReviewFlush(held);g.plan=await api('desk-google-plan',{id:held.id,mode:'auto'});g.problem='';}catch(error){g.plan=null;g.problem=error.message;}sReviewHeadShow(held);});},'filled');plan.disabled=!sDeskCan(held);
  out.push(sNode('p','quiet','Review the fixes you accepted and any edits you made before sending them to Google. Nothing is sent during this check; the next screen shows what will be sent and has the Send button. Rejected fixes are never sent.'),sAdd(sNode('div','bar'),plan));
  return out;
}
function sReviewLede(state){
  if(!state.any&&!state.working&&!state.failed.length)return 'Check the draft to see fixes marked in the text. Nothing changes until you accept one.';
  if(state.working?.kind==='finish-humanize')return 'The fixes are marked in your text while the wording check looks for sentences that read as machine-written. Accept or reject them meanwhile.';
  if(state.working)return state.human?'Copy edit is reading your draft for spelling, grammar and wordy sentences, then the wording check looks for sentences that read as machine-written. Read or edit it meanwhile.':'Copy edit is reading your draft for spelling, grammar and wordy sentences. Read or edit it meanwhile.';
  if(state.any&&!state.pending.length&&!state.failed.length)return (state.human?'Every suggestion is reviewed.':'Every fix is reviewed.')+' Click any paragraph to keep editing, or Check again for the latest text.';
  return state.human?'Each suggestion is marked in your text, labelled as a fix or as more human-sounding wording: struck words go, highlighted words come in. Accept or reject each one, or click a paragraph to edit it yourself. Nothing changes until you accept.':'Each fix is marked in your text: struck words go, highlighted words come in. Accept or reject each one, or click a paragraph to edit it yourself. Nothing changes until you accept.';
}
function sReviewHeadKey(held,state){const g=held.review?.google,proof=sReviewFindings(held,state);return JSON.stringify([state.doc?.count||0,state.overlapping?.length||0,state.working?.id||null,state.working?.kind||null,state.failed,state.sets.map(([tool,set])=>[tool,set.job,set.items.length]),state.applied,state.pending.map(item=>[item.key,item.flag]),state.filter,state.human,sReviewFree(held),!!held.view.working,sDeskCan(held),!!held.view.google_suggestions,held.view.google?.url||'',g?[!!g.plan,!!g.sent,g.problem]:null,proof?[proof.findings.map(found=>found.key),proof.revision===held.view.revision]:null]);}
function sReviewHeadShow(held){if(!held.review?.head)return;sReviewHeadReplace(held,sReviewState(held));}
// The head drawn again with focus where it was: each control that can hold it is marked with
// data-focus, and the same control in the new head takes it back. A Quick check finding that
// went away hands focus to the next one (focusNext), or to the list's summary.
function sReviewHeadReplace(held,state,key){
  const r=held.review,focused=sDeskFocused(),was=r.focusNext||(focused&&typeof r.head.contains==='function'&&r.head.contains(focused)?focused.dataset?.focus:null);r.focusNext=null;
  const head=sReviewHead(held,state);r.head.replaceWith(head);r.head=head;r.headKey=key||sReviewHeadKey(held,state);
  if(!was)return;
  // A control that is gone (Stop once the job ended, Accept all once nothing is left, the
  // last finding dismissed) hands focus to the head's first control, or to the count.
  const again=sReviewFind(head,was)||(/^(fix|dismiss):/.test(was)?sReviewFind(head,'quick'):null)||sReviewFirst(head)||sReviewFind(head,'count');
  if(again&&typeof again.focus==='function')again.focus();
}
// After Accept, Reject, Accept all or Reject all, focus goes to the next suggestion's Accept,
// or to the count, or to the summary once nothing is left: never to the page itself.
function sReviewFocusNext(held,state,item){
  const at=item?state.pending.findIndex(row=>row.key===item.key):-1,next=at<0?null:state.pending[at+1]||state.pending[at-1];
  held.review.focusAfter=next?'accept:'+next.key:'count';
}
// The page keeps its place through it. Focus never scrolls: the next suggestion is brought
// into view only when it is off the screen, and with none left the page stays where the
// last one was. `keep` is where the page was before it was drawn again, put back if drawing
// moved it. While the request is still out (`deciding`) a poll leaves all of this alone.
function sReviewFocusAfter(held,keep=null){
  const r=held.review;if(!r||r.deciding)return;
  const stay=()=>{if(keep!==null&&typeof window.scrollTo==='function'&&typeof window.scrollY==='number'&&Math.abs(window.scrollY-keep)>240)window.scrollTo({top:keep,behavior:'instant'});};
  const key=r.focusAfter;if(!key||!sDeskCurrent(held)){stay();return;}r.focusAfter=null;
  const find=name=>{for(const scope of [r.head,r.paper]){const node=sReviewFind(scope,name);if(node&&!node.disabled&&!node.hidden)return node;}return null;};
  const next=find(key),node=next||find('count')||find('done')||sReviewFirst(r.head);
  if(node&&typeof node.focus==='function')node.focus({preventScroll:true});
  stay();
  if(next)sReviewInView(next);
}
// Bring a suggestion into view if it is not: once now, and again shortly after while it
// still has the focus, because pictures in the paper arrive late and move what is under them.
function sReviewInView(node){
  if(typeof node.getBoundingClientRect!=='function'||typeof window.innerHeight!=='number')return;
  const check=smooth=>{if(!node.isConnected)return;const box=node.getBoundingClientRect();if(box.top<96||box.bottom>window.innerHeight-32)node.scrollIntoView({block:'center',behavior:smooth?'smooth':'instant'});};
  check(true);
  if(typeof setTimeout==='function')for(const wait of [400,1200])setTimeout(()=>{if(sDeskFocused()===node)check(false);},wait);
}
function sReviewFirst(node){for(const child of node?.children||[]){if(child.hidden)continue;if(['button','input','select','textarea','summary'].includes(String(child.tagName).toLowerCase())&&!child.disabled)return child;const found=sReviewFirst(child);if(found)return found;}return null;}
function sReviewFind(node,key){if(!node)return null;if(node.dataset?.focus===key)return node;for(const child of node.children||[]){const found=sReviewFind(child,key);if(found)return found;}return null;}
function sReviewMark(node,key){if(node)node.dataset.focus=key;return node;}
// The reading surface: the title, the opening and each section, every paragraph with its
// fixes marked, opaque like any document.
function sReviewPaper(held,state){
  const paper=sNode('article','paper review-paper');paper.setAttribute('aria-label','Your draft with its fixes marked');held.review.parts={};held.review.order=[];
  for(const part of state.parts){const box=sReviewPart(held,part,state);if(box){held.review.parts[part]=box;held.review.order.push(part);paper.append(box);}}
  return paper;
}
function sReviewKey(held,part,state){const editing=held.review.editing;return JSON.stringify([deskTextOf(held.view,part),(state.doc?.marks||[]).filter(mark=>mark.part===part),state.pending.filter(item=>item.part===part&&item.docFlag).map(item=>item.key),!!state.working,sReviewFree(held),state.shown.filter(item=>item.part===part).map(item=>[item.key,item.number,item.at,item.before,item.after,item.flag,item.note,item.picked??null,item.carriedBy||null]),state.gone.filter(item=>item.part===part).map(item=>[item.key,item.state,item.byNumber??null]),editing&&editing.part===part?editing.start:null,(held.view.sections||[]).find(section=>section.id===part)?.heading||'']);}
function sReviewPart(held,part,state){
  const view=held.view,text=deskTextOf(view,part),section=(view.sections||[]).find(row=>row.id===part);
  const marks=state.shown.filter(item=>item.part===part),gone=state.gone.filter(item=>item.part===part);
  if(part==='opening'&&!text.trim()&&!marks.length)return null;
  const box=sNode(part==='title'?'header':'section','review-part');box.dataset.part=part;box.deskKey=sReviewKey(held,part,state);
  if(section)box.append(sNode('h3','review-heading',deskHeading(section.heading)));
  // Suggestions that overlap one another, from either tool, are listed under the part, not
  // marked in it; each stays independent of the others.
  const placed=[],loose=[];let end=-1;
  for(const item of marks){if(item.at>=end){placed.push(item);end=item.at+item.before.length;}else loose.push(item);}
  const blocks=part==='title'?[{start:0,end:text.length,text}]:reviewBlocks(text,placed);
  for(const block of blocks)box.append(sReviewBlock(held,part,block,placed.filter(item=>item.at>=block.start&&item.at<block.end||!block.text&&item.at===block.start)));
  if(loose.length)box.append(sReviewFixes(held,loose,true));
  // One an accepted suggestion retired says which; the others whose words were edited away are counted.
  for(const item of gone.filter(row=>row.state==='retired')){const line=sAdd(sNode('p','quiet review-gone'),sNode('span','tag review-kind'+(item.tool==='humanize'?' review-kind-human':''),reviewLabel(item)),document.createTextNode(' '+reviewNoLonger(item)));line.dataset.item=item.id;line.dataset.tool=item.tool;box.append(line);}
  const lost=gone.filter(row=>row.state!=='retired').length;
  if(lost){const noun=state.human?['suggestion','suggestions']:['fix','fixes'];box.append(sNode('p','quiet review-gone',lost===1?'1 '+noun[0]+' no longer fits this text, so it was left out.':lost+' '+noun[1]+' no longer fit this text, so they were left out.'));}
  // A part kept as it was while a choice in it had focus is drawn again once focus leaves.
  box.addEventListener('focusout',()=>setTimeout(()=>{if(box.deskStale&&held.review?.parts?.[part]===box&&!sDeskTyping(box)&&sDeskCurrent(held))sReviewPartShow(held,part);},0));
  return box;
}
function sReviewPartShow(held,part){const old=held.review.parts[part],box=sReviewPart(held,part,sReviewState(held));if(old&&box){old.replaceWith(box);held.review.parts[part]=box;}return box;}
function sReviewBlock(held,part,block,marks){
  const view=held.view,wrap=sNode('div','review-block'),editing=held.review.editing;
  if(editing&&editing.part===part&&editing.start===block.start){const note=sNode('p','quiet review-editing',editing.said||'Saves as you type. Click outside the box to finish; its fixes come back.');note.setAttribute('aria-live','polite');editing.note=note;wrap.append(sReviewEditor(held,editing),note);return wrap;}
  const images=deskImagesIn(view,block.text),lost=deskImagesMissing(view,block.text),words=block.text.replace(DESK_IMAGE_REF,'').trim();
  if(words||!images.length&&!lost.length){
    const shown=sNode(part==='title'?'h2':'p',part==='title'?'review-title review-text':'review-text');
    let at=block.start;const text=deskTextOf(view,part);
    for(const item of marks){
      if(item.at>at)shown.append(...sDocInline(view,part,text,at,item.at));
      const mark=sNode('span','review-mark'+(item.tool==='humanize'?' review-human':'')+(item.flag?' review-flagged':''));mark.dataset.item=item.id;mark.dataset.tool=item.tool;mark.title=reviewLabel(item);
      const found=diffWords(item.before,item.after);
      if(!found)mark.append(sNode('del','review-old',item.before),document.createTextNode(' '),sNode('ins','review-new',item.after));
      else found.forEach((piece,index)=>{if(index)mark.append(document.createTextNode(' '));if(piece.op==='same')mark.append(...reviewInline(piece.text,false));else mark.append(sNode(piece.op==='added'?'ins':'del',piece.op==='added'?'review-new':'review-old',piece.text));});
      mark.append(sNode('sup','review-num',String(item.number)));
      shown.append(mark);at=item.at+item.before.length;
    }
    if(at<block.end)shown.append(...sDocInline(view,part,text,at,block.end));
    if(!block.text)shown.append(sNode('span','quiet',part==='title'?'No title yet':'Nothing written yet'));
    if(sDeskCan(held)){shown.tabIndex=0;shown.title='Click to edit';shown.addEventListener('click',()=>sReviewEdit(held,part,block));shown.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault?.();sReviewEdit(held,part,block);}});}
    wrap.append(shown);
  }
  if(part!=='title'){const thumbs=sDeskThumbsFor(view,block.text);if(thumbs)wrap.append(thumbs);}
  if(marks.length)wrap.append(sReviewFixes(held,marks,false));
  return wrap;
}
// Each fix's number, reason and flag, with Accept and Reject; stacked on a phone.
function sReviewFixes(held,items,loose){
  const list=sNode('ol','review-fixes');list.setAttribute('aria-label',loose?'Fixes that overlap others':'Fixes in this paragraph');
  const editable=sDeskCan(held)&&sReviewFree(held);
  for(const item of items){
    const human=item.tool==='humanize',what=human?'suggestion ':'fix ';
    const row=sNode('li','review-fix'+(human?' review-human':'')+(item.flag||item.docFlag?' review-flagged':''));row.dataset.item=item.id;row.dataset.tool=item.tool;
    const said=sAdd(sNode('div','review-why'),sNode('span','review-num',String(item.number)),sNode('span','tag review-kind'+(human?' review-kind-human':''),reviewLabel(item)),sNode('span','',item.note||(human?'Reads as machine-written.':'A fix.')));
    if(item.flag)said.append(sNode('span','tag','Check this'));
    row.append(said);
    if(item.flag)row.append(sNode('p','quiet',item.flag));
    if(item.docFlag){if(!item.flag)said.append(sNode('span','tag doc-tag','Doc suggestion'));row.append(sNode('p','quiet doc-overlap',item.docFlag));}
    if(item.carriedBy?.length){const known=item.carriedBy.filter(Boolean);row.append(sNode('p','quiet review-carried',known.length?'Updated to fit accepted suggestion '+known.map(n=>'#'+n).join(', ')+'.':'Updated to fit an accepted suggestion.'));}
    if(item.alternatives?.length)row.append(sReviewChoices(held,item));
    if(loose)row.append(deskSides(item.before,item.after));
    const accept=sButton('Accept',button=>sReviewAccept(held,item,button));accept.disabled=!editable;accept.setAttribute('aria-label','Accept '+what+item.number);sReviewMark(accept,'accept:'+item.key);
    const reject=sButton('Reject',button=>sReviewReject(held,item.job,[item.id],button,item));reject.disabled=!sDeskCan(held);reject.setAttribute('aria-label','Reject '+what+item.number);sReviewMark(reject,'reject:'+item.key);
    row.append(sAdd(sNode('div','bar'),accept,reject));list.append(row);
  }
  return list;
}
// A wording fix's alternatives: the suggested wording or one of the others, picked before
// Accept, each with its own flag. The paragraph shows the one picked; Accept applies it.
function sReviewChoices(held,item){
  const r=held.review,box=sNode('fieldset','review-choices'),name='review-pick-'+item.tool+'-'+item.id;
  box.append(sNode('legend','quiet','Choose the wording'));
  [{after:item.base,flag:item.baseFlag},...item.alternatives].forEach((option,index)=>{
    const pick=index-1,row=sNode('label','check review-choice'),input=sNode('input','');
    input.type='radio';input.name=name;input.id=name+'-'+index;input.checked=(item.picked??-1)===pick;
    input.addEventListener('change',async()=>{
      if(!input.checked)return;if(r.editing)await sReviewClose(held);  // Saved first, never stuck open.
      if(pick<0)delete r.picks[item.key];else r.picks[item.key]=pick;
      r.pickFocus=input.id;sReviewPartShow(held,item.part);sReviewHeadShow(held);
      const again=r.pickInput;r.pickFocus=r.pickInput=null;if(again)again.focus();
    });
    if(r.pickFocus===input.id)r.pickInput=input;
    row.append(input,sNode('span','',option.after));if(option.flag)row.append(sNode('span','tag','Check this'));
    box.append(row);
  });
  return box;
}
// A poll, a save or a job landing redraws only what changed, never a paragraph being edited.
function sDeskReviewRefresh(held,before){
  if(!sDeskCurrent(held)||!held.review?.paper)return;
  // Where the page is now: drawing it again, in part or whole, must not move it.
  const keep=typeof window.scrollY==='number'?window.scrollY:null;
  const state=sReviewState(held);sReviewToolbar(held,state);
  // Like the toolbar, drawn again only when what it shows changes: a poll never swaps Stop
  // or Accept all under a click.
  const key=sReviewHeadKey(held,state);
  if(key!==held.review.headKey)sReviewHeadReplace(held,state,key);
  if(held.review.lede)held.review.lede.textContent=sReviewLede(state);
  // Sections added or taken away, or an opening that appears or goes: drawn again whole,
  // unless a paragraph is being edited, when it waits for the editor to close.
  // The order drawn, kept as drawn: the parts object lists all-digit ids first.
  const drawn=(held.review.order||[]).join(','),wanted=state.parts.filter(part=>held.review.parts[part]||part!=='opening'||deskTextOf(held.view,part).trim()).join(',');
  if(drawn!==wanted){if(!held.review.editing)sDeskReview(held,keep);return;}
  // A part with the paragraph being edited, or a choice with focus, is kept as it is: a
  // second job landing never takes the caret or the words.
  for(const part of state.parts){
    const old=held.review.parts[part];
    if(!old||held.review.editing?.part===part||old.deskKey===sReviewKey(held,part,state))continue;
    if(sDeskTyping(old)){old.deskStale=true;continue;}
    const box=sReviewPart(held,part,state);if(!box)continue;
    old.replaceWith(box);held.review.parts[part]=box;
  }
  sDeskImagesLoad(held);sReviewProof(held);sReviewFocusAfter(held,keep);
}
function sReviewEditor(held,editing){
  const title=editing.part==='title',box=sNode(title?'input':'textarea','input review-editor');
  box.value=editing.text;box.setAttribute('aria-label',title?'Edit the title':'Edit this paragraph');
  if(title){box.type='text';box.maxLength=500;}else box.rows=Math.min(16,Math.max(3,Math.ceil(editing.text.length/80)+editing.text.split('\n').length));
  box.addEventListener('input',()=>{editing.text=box.value;editing.dirty=true;sReviewSaid(held,editing,'Saving…');if(editing.timer&&typeof clearTimeout==='function')clearTimeout(editing.timer);editing.timer=setTimeout(()=>sReviewSave(held),DESK_SAVE_WAIT);});
  // Leaving the paragraph saves it and shows it marked again, wherever focus went (a choice
  // in another paragraph too); a click on Accept or Reject elsewhere goes ahead first, and
  // saves it before it acts.
  box.addEventListener('blur',()=>{setTimeout(()=>{if(held.review.editing===editing&&sDeskFocused()!==box)sReviewClose(held);},150);});
  editing.box=box;return box;
}
async function sReviewEdit(held,part,block){
  if(held.review.editing){if(held.review.editing.part===part&&held.review.editing.start===block.start)return;await sReviewClose(held);block=sReviewBlockAt(held,part,block)||block;}
  held.review.editing={part,start:block.start,original:block.text,text:block.text,dirty:false};
  const old=held.review.parts[part],box=sReviewPart(held,part,sReviewState(held));if(old&&box){old.replaceWith(box);held.review.parts[part]=box;}
  const editor=held.review.editing.box;if(editor){editor.focus();if(typeof editor.setSelectionRange==='function'){const end=editor.value.length;editor.setSelectionRange(end,end);}}
}
// The block that started at the same place, after the text around it changed.
function sReviewBlockAt(held,part,block){const text=deskTextOf(held.view,part);return part==='title'?{start:0,end:text.length,text}:reviewBlocks(text,[]).find(found=>found.text===block.text)||null;}
// Save the paragraph being edited into its part, at the place it was found.
async function sReviewSave(held){
  const editing=held.review?.editing;if(!editing||!editing.dirty||held.stale)return;
  if(editing.timer&&typeof clearTimeout==='function')clearTimeout(editing.timer);editing.timer=null;
  while(held.saving)await held.saving;
  const whole=deskTextOf(held.view,editing.part),typed=editing.part==='title'?editing.text:editing.text.replace(/\s+$/,'');
  let at=whole.slice(editing.start,editing.start+editing.original.length)===editing.original?editing.start:whole.indexOf(editing.original);
  if(at<0||editing.original&&whole.indexOf(editing.original,at+1)!==-1&&at!==editing.start){sReviewSaid(held,editing,'This paragraph changed elsewhere. Your words are kept in the box; reload to see the latest.');return;}
  const text=whole.slice(0,at)+typed+whole.slice(at+editing.original.length);editing.dirty=false;
  held.saving=(async()=>{try{
    const before=held.view;held.view=await api('desk-save',{id:held.id,seen:held.view.revision,part:editing.part,text,session:held.session});
    const now=deskTextOf(held.view,editing.part),lead=text.length-text.replace(/^\s+/,'').length;
    editing.start=Math.max(0,Math.min(at-lead,now.length));editing.original=now.slice(editing.start,editing.start+typed.length)===typed?typed:typed.trim();
    if(now.indexOf(editing.original)!==-1&&now.slice(editing.start,editing.start+editing.original.length)!==editing.original)editing.start=now.indexOf(editing.original);
    held.saved='Saved.';if(!held.stale)sReviewSaid(held,editing,'Saved. Click outside the box to finish.');
    sDeskRefresh(held,before);
  }catch(error){editing.dirty=true;if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else sReviewSaid(held,editing,error.message+' Your words are kept in the box.');}finally{held.saving=null;}})();
  await held.saving;
  if(editing.dirty&&!held.stale&&held.review.editing===editing&&editing.text!==typed)return sReviewSave(held);
}
// How the paragraph being edited is saving, said under it and in the page's save line.
function sReviewSaid(held,editing,words){editing.said=words;if(editing.note)editing.note.textContent=words;if(held.status&&!held.stale)held.status.textContent=words;}
async function sReviewClose(held){const editing=held.review?.editing;if(!editing)return;await sReviewSave(held);if(held.review.editing!==editing||editing.dirty)return;held.review.editing=null;if(held.status&&!held.stale&&editing.said)held.status.textContent=/^Saved/.test(editing.said)?'Saved.':editing.said;if(sDeskCurrent(held)&&held.mode==='review')sDeskReviewRefresh(held,held.view);}
async function sReviewFlush(held){if(held.review?.editing)await sReviewClose(held);}
async function sReviewCheck(held,button,humanize,voiceGuide,claims=false){
  await busy(button,'Starting…',async()=>{try{
    await sReviewFlush(held);await sDeskFlush(held);if(held.stale)return;
    // Check again sends no strength: the server reuses the one pinned for this blog.
    const before=held.view;held.view=await api('desk-review',{id:held.id,seen:held.view.revision,...(humanize===undefined?{}:{humanize}),...(voiceGuide===undefined?{}:{voice_guide:voiceGuide}),...(claims?{claims:true}:{})});
    if(held.review){held.review.google=null;held.review.picks={};held.review.ask=null;held.review.pendingVoice=null;}
    sDeskRefresh(held,before);sDeskWatch(held);
  }catch(error){if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else notice(error.message,true);}});
}
async function sReviewAccept(held,item,button){
  await busy(button,'Accepting…',async()=>{try{
    await sReviewFlush(held);if(held.stale)return;
    sReviewFocusNext(held,sReviewState(held),item);if(held.review)held.review.deciding=true;
    const before=held.view;try{held.view=await api('desk-apply',{id:held.id,seen:held.view.revision,job:item.job,items:[sReviewPick(item)]});}finally{if(held.review)held.review.deciding=false;}
    if(held.review){held.review.google=null;delete held.review.picks[item.key];}
    sToast('Accepted. The earlier text is in History.'+deskFinishedSaid(held.view.finished));
    sDeskRefresh(held,before);
  }catch(error){if(held.review)held.review.focusAfter=null;if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else notice(error.message,true);}});
}
// Accept all: every shown suggestion that still fits and is not flagged, from both tools in one
// request. The server lands them in reading order, each checked against the text the ones
// before it left: one that took in an earlier one's words goes ahead with them, and one whose
// words an earlier one changed no longer fits. Flagged and hidden ones are never sent; they
// stay open unless their words were changed.
async function sReviewAcceptAll(held,keys,button){
  await busy(button,'Accepting…',async()=>{
    const before=held.view;
    try{
      await sReviewFlush(held);if(held.stale)return;
      const chosen=sReviewState(held).ready.filter(item=>keys.includes(item.key));if(!chosen.length)return;
      held.review.focusAfter='count';
      held.view=await api('desk-apply',{id:held.id,seen:held.view.revision,job:chosen[0].job,items:chosen.map(item=>({job:item.job,...sReviewPick(item)})),all:true});
      for(const item of chosen)delete held.review.picks[item.key];
      if(held.review)held.review.google=null;
      const done=held.view.finished||{applied:chosen.length,left:[]},left=(done.left||[]).length,waits=left?' '+left+(left===1?' is':' are')+' left for you to decide.':'';
      if(done.applied)sToast((done.applied===1?'Accepted.':'Accepted '+done.applied+'.')+' The earlier text is in History.'+deskFinishedSaid(done)+waits);
      else if(left)sToast('Nothing was accepted: '+(left===1?'1 is':left+' are')+' left for you to decide.');
    }catch(error){if(held.view===before&&held.review)held.review.focusAfter=null;if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else notice(error.message,true);}
    if(held.view!==before)sDeskRefresh(held,before);
  });
}
async function sReviewReject(held,job,ids,button,item){
  await busy(button,'Rejecting…',async()=>{try{
    await sReviewFlush(held);if(item)sReviewFocusNext(held,sReviewState(held),item);if(held.review)held.review.deciding=true;
    const before=held.view;try{held.view=await api('desk-skip',{id:held.id,job,items:ids});}finally{if(held.review)held.review.deciding=false;}
    sReviewUndoToast(held,ids.length===1?'Rejected; the text is unchanged.':'Rejected '+ids.length+'; the text is unchanged.',[{job,ids}],item);
    sDeskRefresh(held,before);
  }catch(error){if(held.review)held.review.focusAfter=null;notice(error.message,true);}});
}
// A rejection is said, with Undo for a short while: the suggestions are open again, and focus
// goes back to the one brought back. Nothing in the text changed either way.
function sReviewUndoToast(held,words,sets,item){
  const toast=sNode('p','toast glass',words+' ');let used=false;
  const undo=sButton('Undo',async button=>{if(used)return;used=true;await busy(button,'Bringing back…',async()=>{try{const before=held.view;for(const set of sets)held.view=await api('desk-unskip',{id:held.id,job:set.job,items:set.ids});toast.remove();sToast('Brought back to review.');if(held.review)held.review.focusAfter=item?'accept:'+item.key:'count';sDeskRefresh(held,before);}catch(error){used=false;notice(error.message,true);}});});
  undo.className+=' button-quiet';toast.append(undo);$('toasts').append(toast);setTimeout(()=>toast.remove(),8000);
}
// Reject all: every open suggestion shown, set by set.
async function sReviewRejectAll(held,open,button){
  await busy(button,'Rejecting…',async()=>{
    const before=held.view;
    const sets=[];
    try{await sReviewFlush(held);held.review.focusAfter='count';for(const job of [...new Set(open.map(item=>item.job))]){const ids=open.filter(item=>item.job===job).map(item=>item.id);held.view=await api('desk-skip',{id:held.id,job,items:ids});sets.push({job,ids});}}
    catch(error){notice(error.message,true);}
    if(sets.length)sReviewUndoToast(held,open.length===1?'Rejected; the text is unchanged.':'Rejected '+open.length+'; the text is unchanged.',sets,null);
    if(held.view!==before)sDeskRefresh(held,before);
  });
}
// One name for each thing: Sounds human is the assistant's rewrites, marked in the text;
// Quick check is this list, and says it is a second, optional pass.
// With human-sounding wording on, Quick check's mechanical findings (dashes, words that often
// read as machine-written, repetition) are listed at the top, read from the latest text with
// no assistant: a short list, not marks, so they never crowd the suggestions in the text. Fix
// rewrites only the sentence a finding is in, as Quick check's Fix does; Dismiss hides it here.
// It is read at once the first time and when the list is opened; after the text changes, a
// short pause after the last change, so autosaves while typing do not each read it again.
function sReviewProof(held,now=false){
  const r=held.review,revision=held.view?.revision;
  if(!r||!held.view.review?.humanize||r.proofing||r.proof?.revision===revision)return;
  if(!now&&r.proof){
    if(r.proofTimer&&r.proofWanted===revision)return;
    if(r.proofTimer&&typeof clearTimeout==='function')clearTimeout(r.proofTimer);
    r.proofWanted=revision;r.proofTimer=setTimeout(()=>{r.proofTimer=null;if(held.review===r&&sDeskCurrent(held)&&held.mode==='review')sReviewProof(held,true);},REVIEW_PROOF_WAIT);
    return;
  }
  if(!now&&r.proofTried===revision)return;
  r.proofing=true;r.proofTried=revision;
  (async()=>{
    try{const found=await api('desk-proofread?'+new URLSearchParams({id:held.id}));if(found&&Array.isArray(found.findings))r.proof=found;}catch(_){/* Quick check is a hint: the review goes on without it. */}
    finally{r.proofing=false;}
    if(held.review===r&&sDeskCurrent(held)&&held.mode==='review')sDeskReviewRefresh(held,held.view);
  })();
}
function sReviewFindings(held,state){
  const proof=held.review?.proof;if(!state.human||!proof)return null;
  const dismissed=held.review.dismissed||{};
  // Keyed by what was found and the sentence around it, never by where: an edit earlier in
  // the part moves a finding without bringing a dismissed one back.
  // Where it sits within its sentence tells apart two findings of one word in one sentence.
  // A dismissed finding also stays dismissed when its own sentence changes elsewhere, as it
  // does when a fix is accepted in it: it is known again by the words right around it.
  const near=found=>{const at=found.at-found.start;return ['near',found.part,found.rule,found.target,found.sentence.slice(Math.max(0,at-24),at+found.target.length+24)].join('\u0001');};
  const findings=proof.findings.map(found=>({...found,key:[found.part,found.rule,found.target,found.sentence,found.at-found.start].join('\u0001'),near:near(found)})).filter(found=>!dismissed[found.key]&&!dismissed[found.near]);
  return {revision:proof.revision,findings,more:proof.more||0};
}
function sReviewQuick(held,state){
  const found=sReviewFindings(held,state);if(!found||!found.findings.length)return null;
  const r=held.review,box=sNode('details','card review-quick'),count=found.findings.length;box.open=!!r.quickOpen;box.addEventListener('toggle',()=>{r.quickOpen=box.open;if(box.open)sReviewProof(held,true);});
  box.append(sAdd(sReviewMark(sNode('summary',''),'quick'),sNode('span','card-title','Quick check'),sNode('span','quiet review-quick-count',count+(count===1?' pattern found':' patterns found')+' · optional')));
  box.append(sNode('p','quiet','A second, optional pass, apart from the suggestions marked in your text: dashes, repeated words and words that often read as machine-written, found by pattern with no assistant. Fix rewrites only the sentence a finding is in and keeps the earlier text in History; Dismiss hides it here.'));
  if(found.revision!==held.view.revision)box.append(sNode('p','quiet','The text changed since this check; it is read again in a moment.'));
  const list=sNode('ol','review-fixes review-quick-list');list.setAttribute('aria-label','Quick check findings');
  found.findings.forEach((finding,index)=>{
    const row=sNode('li','review-fix review-human');row.dataset.finding=finding.key;
    row.append(sAdd(sNode('div','review-why'),sNode('span','tag review-kind review-kind-human','Quick check'),sNode('span','',finding.label)));
    const said=sNode('p','desk-plain desk-quote'),at=finding.at-finding.start;
    if(at>=0&&finding.sentence.slice(at,at+finding.target.length)===finding.target)said.append(document.createTextNode(finding.sentence.slice(0,at)),sNode('mark','',finding.target),document.createTextNode(finding.sentence.slice(at+finding.target.length)));
    else said.textContent=finding.sentence;
    const still=deskTextOf(held.view,finding.part).slice(finding.start,finding.start+finding.sentence.length)===finding.sentence;
    const fix=sButton('Fix',button=>sDeskJob(held,button,'desk-selection',{part:finding.part,text:finding.sentence,start:finding.start,action:'fix',instruction:finding.fix}));fix.disabled=!sDeskCan(held)||!!held.view.working||!still;fix.setAttribute('aria-label','Fix: '+finding.label);sReviewMark(fix,'fix:'+finding.key);
    // Dismissed, it goes; focus moves to the next finding, or back to the list's summary.
    const dismiss=sButton('Dismiss',()=>{const next=found.findings[index+1]||found.findings[index-1];r.dismissed[finding.key]=true;r.dismissed[finding.near]=true;r.focusNext=next?'dismiss:'+next.key:'quick';sReviewHeadShow(held);});dismiss.setAttribute('aria-label','Dismiss: '+finding.label);sReviewMark(dismiss,'dismiss:'+finding.key);
    row.append(said,sAdd(sNode('div','bar'),fix,dismiss));if(!still)row.append(sNode('p','quiet','This sentence changed since the check.'));
    list.append(row);
  });
  return sAdd(box,list,found.more?sNode('p','quiet','And '+found.more+' more. Fix some, then look again.'):null);
}

// A sheet opened over the desk (Add a source, History…) is always on top: on a screen too
// narrow for the panel to sit beside the draft, the panel steps aside while the sheet is open
// and comes back when it closes. runner.js calls these when any sheet opens or closes.
function sDeskFloating(){return DESK_KIT.floating();}
function sDeskSheetOpened(){const held=studio.desk;if(studio.screen!=='desk'||!held?.finish||!held.panel||!sDeskFloating())return;held.panelUnder=true;held.panel.hidden=true;}
function sDeskSheetClosed(){const held=studio.desk;if(!held?.panelUnder)return;held.panelUnder=false;if(held.panel)held.panel.hidden=false;}
// Turning a phone or resizing the window across a layout redraws the desk in the new one.
function sDeskLayout(){return DESK_KIT.layout();}
function sDeskResized(){const held=studio.desk;if(!held||!sDeskCurrent(held)||held.layout===sDeskLayout())return;if(held.mode==='review'){if(!held.review?.editing){held.layout=sDeskLayout();sDeskReview(held);}return;}if(!held.cards&&held.tab!=='outline')return;held.layout=sDeskLayout();held.panelUnder=!!studio.sheet&&!!held.finish&&sDeskFloating();sDeskRender(held);}  // A sheet open across the change stays on top.
// The shared desk kit (ui-kit/drafting.js), bound to Blog Studio's controls, requests, words,
// parts and Finishing tools. Each member names Blog's function when it is called, so the kit
// can be built here, before anything runs, and a check that swaps a global still reaches it.
const DESK_KIT=Drafting.kit({
  ui:{button:(...x)=>sButton(...x),card:(...x)=>sCard(...x),pickCard:(...x)=>sPickCard(...x),choice:(...x)=>sChoice(...x),disclosure:(...x)=>disclosure(...x),bead:(...x)=>sBead(...x),openSheet:(...x)=>sOpenSheet(...x),closeSheet:()=>sCloseSheet(),toast:(...x)=>sToast(...x),notice:(...x)=>notice(...x),busy:(...x)=>busy(...x),narrow:()=>sNarrow()},
  api:(route,data)=>api(route,data),
  routes:{view:'desk',save:'desk-save',versions:'desk-versions',restore:'desk-restore',note:'desk-note',revise:'desk-revise',selection:'desk-selection',stop:'desk-stop',retry:'desk-retry',finish:'desk-finish',apply:'desk-apply',skip:'desk-skip',proofread:'desk-proofread'},
  share:id=>fetch('/api/desk-share',{method:'POST',keepalive:true,headers:{'X-Blog-Studio-Token':token,'Content-Type':'application/json'},body:JSON.stringify({id})}),
  canEdit:held=>sDeskCan(held),
  current:held=>sDeskCurrent(held),
  page:()=>$('studio-page'),
  hooks:{
    render:held=>sDeskRender(held),
    refresh:(held,before)=>sDeskRefresh(held,before),
    reload:held=>{held.pending={};held.stale=false;held.saved='';return sDesk(held.id);},
    beforeJob:held=>sDeskOutlineFlush(held),
    // Review mode's paragraph editor saves before the parts typing left waiting.
    beforeFlush:held=>held.review?.editing?.dirty?sReviewSave(held):undefined,
    finishClosed:held=>sDeskReturnFocus(held),
    // Include a GEO review, the post's own choice, after the Reader aids and AI search tools.
    listLead:held=>sDeskFinishPass(held),
    groupAfter:(held,group)=>group==='Reader aids and AI search'?sDeskGeoChoice(held):null,
    noteTarget:(held,item)=>{if(held.reading==='full')return false;const section=held.view.sections.find(row=>row.id===item.part);held.reading=section?'edit':'full';if(section)held.activePart=section.id;sDeskViewUrl(held);return true;},
    saved:(held,part,text)=>sDeskSaved(held,part,text),
    versionNote:version=>deskVersionNote(version),
    // Under a part's text: its image thumbnails; and a card drawn again once focus leaves it.
    extra:(held,part)=>part==='title'?null:sDeskThumbs(held,part),
    left:(held,part,card)=>sDeskPartLeft(held,part,card),
    // A start that ended opens the draft, or the outline it wrote.
    started:(held,view)=>{held.tab=view.start?.open==='outline'?'outline':'draft';held.outline=null;},
    // In Review mode, Copy edit's and Humanize's suggestions are marked in the text itself.
    landed:(held,last)=>held.mode==='review'&&last.kind==='finish-copyedit'?'The fixes are marked in your text.':held.mode==='review'&&last.kind==='finish-humanize'?'The suggestions are marked in your text.':'',
  },
  parts:{title:(view,part)=>part==='title'?'Title':part==='opening'?'Opening':deskHeading(((view.sections||[]).find(row=>row.id===part)||{}).heading),textOf:(view,part)=>deskTextOf(view,part),nameOf:(view,part)=>deskPartName(view,part),single:part=>part==='title',noted:(view,part)=>(view.sections||[]).some(row=>row.id===part)},
  words:()=>({thing:'draft',sources:DESK_SOURCES,doing:DESK_DOING,steps:DESK_STEPS,named:['desk-section','desk-selection'],withOpening:['desk-first-pass'],chain:['desk-revise-all'],ready:tab=>tab==='outline'?'The outline is ready. Shape it here, then write the draft.':'The draft is ready. Edit it here.'}),
  tools:()=>DESK_TOOLS,
  progress:{stopped:held=>sDeskStopped(held),show:held=>sDeskProgress(held)},
});
if(typeof window.addEventListener==='function')window.addEventListener('resize',()=>{if(typeof clearTimeout==='function')clearTimeout(window.deskResize);window.deskResize=setTimeout(sDeskResized,150);});

// GEO reports (geo_report.py): a published post's recommendations, kept here, listed in Blogs
// as a GEO report rather than a draft, and reopened from there. A link, its read-only preview,
// then one press starts one job. Nothing is brought to the desk unless the person asks, and
// the live page is never changed. Every text from the report is set with textContent.
const GEO_REPORT_SAYS='Point at a published post and get a report of the changes that would make it clearer for AI search: what already works, the changes ranked by how much they help, additions shown where they would go, the questions it answers and the sources it needs. Nothing is brought onto the desk, and the live page is never changed.';
const GEO_ACCESS_WORDS={ok:'Fine',problem:'Check this',note:'Note',unknown:'Couldn’t check'};
function sGeoBegin(){studio.geoStart=null;return sRoute('geo-start');}
function sGeoHeld(){return studio.geoStart||(studio.geoStart={link:'',preview:null,problem:'',operation:operationId()});}
function sGeoInstead(){const b=sButton('Only want recommendations for a published post? Get a GEO report',()=>sGeoBegin());b.className+=' desk-instead';b.disabled=!access.actions.edit;return b;}
async function sGeoStart(){
  const held=sGeoHeld();
  sFrame('GEO report',[],'New blog',()=>sRoute('home'));
  const form=sNode('form','narrow desk-start geo-start'),problem=sNode('p','problem',held.problem||'');problem.setAttribute('role','alert');held.problem='';
  const card=sCard('The published post',sField('geo-link','Link to the published post',held,'link',{required:true,max:2000,hint:'Its page is read once when you press Read the page, without running anything on it, together with the site’s robots.txt. You see what was read before anything starts.',changed:()=>{held.preview=null;sFindTextGone(held);}}));
  if(held.find&&!held.preview){const find=held.find;card.append(sFindText(find,{current:()=>studio.screen==='geo-start'&&studio.geoStart===held&&held.find===find,found:()=>{held.find=null;return sGeoRead(held);}}));}
  if(held.preview){
    card.append(sPublishedPreview(held.preview,'The post as it was read'));
    const again=sButton('Read the page again',button=>busy(button,'Reading…',()=>sGeoRead(held)));again.disabled=!access.actions.edit;card.append(sAdd(sNode('div','bar'),again));
  }
  const go=sNode('button','button button-filled',held.preview?'Get the GEO report':'Read the page');go.type='submit';go.disabled=!access.actions.edit;
  sAdd(form,card,held.preview?sGeoAccess(held.preview.access,'Page access (as read)'):null,sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),go)),held.preview?sNode('p','quiet','One job reads this copy of the post and writes the report. It recommends; nothing on the page, the desk or Google changes.'):null);
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(!access.actions.edit||studio.busy)return;
    if(!held.link.trim()){problem.textContent='Paste the post’s link first.';return;}
    if(!held.preview)return busy(go,'Reading…',()=>sGeoRead(held));
    await busy(go,'Starting…',async()=>{try{const made=await api('geo-report-start',{operation:held.operation,published:{preview:held.preview.preview,expected:held.preview.expected}});studio.geoStart=null;await sRoute('geo-report',made.id);}catch(error){problem.textContent=error.message;}});
  });
  sPage(sNode('p','lede',GEO_REPORT_SAYS),form);
}
async function sGeoRead(held){
  const turn=studio.turn;
  try{const found=sPublishedFound(await api('published-preview',{url:held.link.trim()}));if(turn!==studio.turn)return;held.preview=found;held.find=null;}
  catch(error){if(turn!==studio.turn)return;held.preview=null;held.find=sFindTextFrom(error,held.link.trim());held.problem=held.find?'':error.message+' Your link is kept here.';}
  if(studio.screen==='geo-start'&&studio.geoStart===held){await sGeoStart();if(held.find)sFindTextFocus();else sPublishedFocus();}
}
// After a read, focus goes to what was read, so a keyboard user reads it before starting.
function sPublishedFocus(){const paper=$('studio-page').querySelector('.published-preview .paper');if(paper&&typeof paper.focus==='function')paper.focus({preventScroll:false});}
// Page access: advice only, each check in a line, and what it never promises.
function sGeoAccess(access,title='Page access'){
  const checks=(access&&access.checks)||[];if(!checks.length)return null;
  const list=sNode('ul','geo-access');
  for(const check of checks)list.append(sAdd(sNode('li','geo-access-'+(GEO_ACCESS_WORDS[check.status]?check.status:'note')),sNode('strong','',(GEO_ACCESS_WORDS[check.status]||'Note')+': '),document.createTextNode(check.said||'')));
  return sCard(title,sNode('p','quiet',access.eligibility||''),list,sNode('p','quiet',access.site_owner||''));
}
function sGeoDate(value){return String(value||'').slice(0,10);}
async function sGeoReport(ident){
  const turn=studio.turn,shown=await api('geo-report?'+new URLSearchParams({id:ident}));if(turn!==studio.turn)return;
  const held=studio.geoReport&&studio.geoReport.id===ident?studio.geoReport:(studio.geoReport={id:ident,google:null,problem:''});
  held.view=shown;sGeoReportRender(held);
  if(shown.status==='working')sGeoWatch(held,turn);
}
function sGeoWatch(held,turn){
  setTimeout(async()=>{
    if(turn!==studio.turn||studio.screen!=='geo-report'||studio.geoReport!==held)return;
    try{const shown=await api('geo-report?'+new URLSearchParams({id:held.id}));if(turn!==studio.turn||studio.geoReport!==held)return;const changed=shown.status!==held.view.status;held.view=shown;if(changed)sGeoReportRender(held);else sActivityUpdate($('studio-page'),shown.activity,{report:held.id});if(shown.status==='working')sGeoWatch(held,turn);}
    catch(error){notice(error.message,true);}
  },DESK_POLL);
}
function sGeoReportRender(held){
  const view=held.view,ready=view.status==='ready';
  const again=sButton('Run again',button=>sGeoAgain(held,button));again.disabled=!access.actions.edit||view.status==='working';
  const deskCopy=view.desk;
  const edit=ready?sButton(deskCopy?'Open its desk copy':'Edit this post on the desk',button=>sGeoDesk(held,button),'filled'):null;if(edit)edit.disabled=!deskCopy&&!access.actions.edit;
  sFrame('GEO report',[again,edit],'Blogs',()=>sRoute('blogs'));
  const parts=[];
  if(view.newer)parts.push(sAdd(sNode('div','decision-notice'),sNode('p','','A newer report of this page was made after this one.'),sButton('Open the newer report',()=>sRoute('geo-report',view.newer))));
  else if(view.previous)parts.push(sAdd(sNode('div','bar'),sButton('Open the earlier report',()=>sRoute('geo-report',view.previous))));
  if(view.status==='working'){const line=sNode('p','desk-working-note','Reading the post and writing its report. One job; nothing else changes.');line.setAttribute('role','status');parts.push(sCard(view.title,line,sActivityNow(view.activity,{report:view.id}),sNode('p','quiet','It opens here when it is ready. You can leave this page; the report is kept in Blogs.')));}
  else if(!ready){const said=sNode('p','problem','The report did not finish: '+(view.error||'it stopped.'));said.setAttribute('role','alert');parts.push(sCard(view.title,said,sNode('p','quiet','Run again reads the page again and makes a new report.')));}
  else parts.push(sGeoPaper(view),sGeoAfterwards(held));
  if(held.find){
    // Run again found no text: the assistant may find where the page gets it, then Run again goes ahead.
    const find=held.find;
    parts.unshift(sCard('Find the post’s text',sFindText(find,{current:()=>studio.screen==='geo-report'&&studio.geoReport===held&&held.find===find,found:()=>{held.find=null;return sGeoAgain(held,null);}})));
  }
  if(held.problem){const said=sNode('p','problem',held.problem);said.setAttribute('role','alert');parts.unshift(said);held.problem='';}
  // What the assistant did for this report, newest first: read when it is opened.
  parts.push(sActivityLog({report:view.id}));
  sPage(...parts);
}
// The report itself: an opaque, typeset reading document.
function sGeoPaper(view){
  const paper=sNode('article','paper review-paper geo-report-paper');paper.setAttribute('aria-label','GEO report: '+view.title);
  const head=sAdd(sNode('header','geo-report-head'),sNode('p','quiet geo-report-kind','GEO report'),sNode('h1','review-title',view.title));
  if(view.url){const a=link(view.url,view.url);a.className='geo-report-link';head.append(sAdd(sNode('p',''),a));}
  else if(view.collection_item)head.append(sNode('p','quiet','From a team collection'));
  head.append(sNode('p','quiet','Read '+sGeoDate(view.read_at)+'. Recommendations only: nothing on the page was changed. These are not ranking promises.'));
  paper.append(head);
  if(view.changed)paper.append(sAdd(sNode('section','geo-report-part'),sNode('h2','review-heading','Since the last report'),sNode('p','',sGeoChanged(view.changed))));
  const summary=sAdd(sNode('section','geo-report-part'),sNode('h2','review-heading','Summary'));
  if(view.works.length)summary.append(sNode('h3','geo-report-sub','What already works'),sAdd(sNode('ul',''),...view.works.map(text=>sNode('li','',text))));
  if(view.recommendations.length){
    const list=sNode('ol','geo-report-ranked');
    for(const row of view.recommendations){const item=sAdd(sNode('li',''),sNode('span','review-num',String(row.n)),row.label?sNode('strong','',row.label+': '):null,document.createTextNode((row.help||row.why||'')+' '),sNode('span','quiet','('+row.where+')'));if(row.flag)item.append(sNode('p','geo-report-flag',row.flag));list.append(item);}
    summary.append(sNode('h3','geo-report-sub','Recommended, most helpful first'),list);
  }else summary.append(sNode('p','','No changes are recommended.'));
  if(view.advice)summary.append(sNode('p','',view.advice));
  paper.append(summary);
  const post=sAdd(sNode('section','geo-report-part geo-report-post'),sNode('h2','review-heading','The post with changes marked'),sAdd(sNode('p','quiet'),document.createTextNode('Inserted words are '),sNode('ins','review-new','marked like this'),document.createTextNode(', deleted ones '),sNode('del','review-old','like this'),document.createTextNode('. Each number is a recommendation in the summary.')));
  for(const entry of view.post)post.append(...sGeoEntry(entry));
  if(view.overlaps&&view.overlaps.length)post.append(sNode('p','quiet',(view.overlaps.length===1?'Recommendation ':'Recommendations ')+view.overlaps.join(', ')+' change words another one already changes, so '+(view.overlaps.length===1?'it is':'they are')+' listed in the summary only.'));
  paper.append(post);
  if(view.questions.length)paper.append(sAdd(sNode('section','geo-report-part'),sNode('h2','review-heading','Questions this post answers'),sNode('p','quiet','Advice only: questions people might ask an AI assistant that this post answers. Nothing is added to the post.'),sAdd(sNode('ul',''),...view.questions.map(text=>sNode('li','',text)))));
  if(view.sources_needed.length)paper.append(sAdd(sNode('section','geo-report-part'),sNode('h2','review-heading','Sources needed'),sNode('p','quiet','Claims that would be stronger with a cited source, and what kind. No source is named or invented for you.'),sAdd(sNode('ul',''),...view.sources_needed.map(row=>sAdd(sNode('li',''),sNode('q','',row.claim),document.createTextNode(' '),sNode('span','quiet','('+row.where+')'),document.createTextNode(': '+row.kind+'.'))))));
  const access=(view.access&&view.access.checks)||[];
  if(access.length)paper.append(sAdd(sNode('section','geo-report-part'),sNode('h2','review-heading','Page access'),sNode('p','quiet',view.access.eligibility),sAdd(sNode('ul','geo-access'),...access.map(check=>sAdd(sNode('li','geo-access-'+(GEO_ACCESS_WORDS[check.status]?check.status:'note')),sNode('strong','',(GEO_ACCESS_WORDS[check.status]||'Note')+': '),document.createTextNode(check.said)))),sNode('p','quiet',view.access.site_owner)));
  return paper;
}
function sGeoSegments(node,segments){
  for(const [at,segment] of segments.entries()){
    // A deletion and the insertion that replaces it are kept a space apart, as words.
    if(segment.t==='del')node.append(sNode('del','review-old',segment.v),...(segments[at+1]?.t==='ins'?[document.createTextNode(' ')]:[]));
    else if(segment.t==='ins')node.append(sNode('ins','review-new',segment.v));
    else if(segment.t==='note'){const n=sNode('span','review-num',String(segment.n));n.setAttribute('aria-label','recommendation '+segment.n);node.append(n);}
    else node.append(document.createTextNode(segment.v||''));
  }
  return node;
}
function sGeoNotes(entry){const notes=(entry.notes||[]).filter(note=>note.why);if(!notes.length)return null;return sAdd(sNode('p','review-why geo-report-why'),...notes.flatMap((note,at)=>[at?document.createTextNode(' · '):null,sNode('span','review-num',String(note.n)),document.createTextNode(' '+note.why)].filter(Boolean)));}
function sGeoEntry(entry){
  if(entry.type==='title')return [entry.segments?sGeoSegments(sNode('h3','geo-report-title'),entry.segments):sNode('h3','geo-report-title',entry.text),sGeoNotes(entry)].filter(Boolean);
  if(entry.type==='heading')return [sNode('h4','geo-report-heading',entry.text)];
  if(entry.type==='text'){const box=sNode('div','geo-report-text');box.append(window.StudioMarkdown?window.StudioMarkdown.render(sPublishedText(entry.markdown)):sNode('p','',entry.markdown));return [box];}
  if(entry.type==='image')return [sNode('p','geo-report-image','Image: '+entry.name+' — '+(entry.alt?'alt text: '+entry.alt:'no alt text'))];
  if(entry.type==='marked')return [sGeoSegments(sNode('p','review-text geo-report-marked'),entry.segments),sGeoNotes(entry)].filter(Boolean);
  const box=sAdd(sNode('aside','geo-report-addition'),sAdd(sNode('p','geo-report-addition-label'),sNode('span','review-num',String(entry.n)),document.createTextNode(' Suggested addition: '+entry.label)),sNode('p','quiet',entry.note));
  if(entry.heading)box.append(sNode('h5','geo-report-heading',entry.heading));
  const text=sNode('div','geo-report-text');text.append(window.StudioMarkdown?window.StudioMarkdown.render(entry.markdown):sNode('p','',entry.markdown));box.append(text);
  if(entry.flag)box.append(sNode('p','geo-report-flag',entry.flag));
  return [box];
}
function sGeoChanged(changed){
  if(changed.same)return 'The page’s text is the same as when it was read on '+sGeoDate(changed.since)+'.';
  const said=['Since the page was read on '+sGeoDate(changed.since)+':'];
  if(changed.changed?.length)said.push('changed '+changed.changed.join(', ')+';');
  if(changed.added?.length)said.push('added '+changed.added.map(name=>'“'+name+'”').join(', ')+';');
  if(changed.removed?.length)said.push('removed '+changed.removed.map(name=>'“'+name+'”').join(', ')+';');
  said.push((changed.words||[0,0])[0]+' words then, '+(changed.words||[0,0])[1]+' now.');
  if(changed.of)said.push(changed.taken+' of the '+changed.of+' changes the last report recommended now read as it suggested.');
  return said.join(' ');
}
// Afterwards: the downloads and a new Google Doc, each only on a press.
function sGeoAfterwards(held){
  const view=held.view;
  const html=sButton('Download HTML',button=>sGeoDownload(held,button,'html'));
  const md=sButton('Download Markdown',button=>sGeoDownload(held,button,'md'));
  const download=sCard('Download',sNode('p','quiet','One self-contained HTML file that prints cleanly to PDF, or Markdown.'),sAdd(sNode('div','bar'),html,md));
  const g=held.google;
  const google=sCard('Google Doc',sNode('p','quiet','Makes a new private Google Doc of the post, with each change as a suggestion and its reason as a comment, so you can accept or reject each one there. Additions go as comments where they would go. '+(view.desk?'This Doc is linked to the desk copy “'+(view.desk.title||view.title)+'”, so you can bring the changes you accept back there.':'A desk copy of the post is made too and the Doc is linked to it, so you can bring the changes you accept back there.')+' Your own Google Doc and the live page are never touched.'));
  if(g&&g.sent){google.append(sNode('p','','Sent to the new Google Doc: '+g.plan.suggestions+(g.plan.suggestions===1?' suggestion':' suggestions')+' and '+g.plan.comments+(g.plan.comments===1?' comment.':' comments.')),sAdd(sNode('p',''),link(g.plan.url,'Open the Google Doc')));}
  else if(g&&g.plan){
    const p=g.plan,line=p.suggestions+(p.suggestions===1?' suggestion':' suggestions')+' and '+p.comments+(p.comments===1?' comment':' comments')+' are ready to send'+(p.left?'; '+p.left+(p.left===1?' recommendation could':' recommendations could')+' not be placed in the Doc':'')+'.';
    const send=sButton('Send to the Google Doc',button=>busy(button,'Sending…',async()=>{try{await api('geo-report-google-send',{id:held.id,plan:p.plan,confirmed:true});g.sent=true;sToast('Sent. Accept or reject each suggestion in Google Docs.');sGeoReportRender(held);}catch(error){held.problem=error.message;sGeoReportRender(held);}}),'filled');
    google.append(sNode('p','',line),sAdd(sNode('p',''),link(p.url,'The new Google Doc')),sAdd(sNode('div','bar'),send,sButton('Not now',()=>{held.google=null;sGeoReportRender(held);})));
  }else{
    const make=sButton('Make a Google Doc with these suggestions',button=>busy(button,'Making the Doc and checking…',async()=>{try{const plan=await api('geo-report-google-plan',{id:held.id,operation:held.googleOp||(held.googleOp=operationId()),mode:'auto'});held.google={plan,sent:false};held.view=await api('geo-report?'+new URLSearchParams({id:held.id}));sGeoReportRender(held);}catch(error){held.problem=error.message;sGeoReportRender(held);}}));
    make.disabled=!access.actions.edit||!!(view.desk&&view.desk.changed);
    sAdd(google,view.desk&&view.desk.changed?sNode('p','quiet','This post’s desk copy has changed since the report. Send its changes from the desk instead: Before publishing, Send to Google Doc as suggestions.'):null,sAdd(sNode('div','bar'),make));
  }
  return sAdd(sNode('div','stack geo-report-after'),download,google);
}
async function sGeoDownload(held,button,format){
  await busy(button,'Preparing…',async()=>{const found=await api('geo-report-download?'+new URLSearchParams({id:held.id,format}));const blob=new Blob([found.content],{type:format==='html'?'text/html;charset=utf-8':'text/markdown;charset=utf-8'}),url=URL.createObjectURL(blob),a=sNode('a','');a.href=url;a.download=found.filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
}
async function sGeoDesk(held,button){
  if(held.view.desk){studio.desk={id:held.view.desk.id,session:operationId()};return sRoute('desk',held.view.desk.id);}
  await busy(button,'Making the desk copy…',async()=>{try{const made=await api('geo-report-desk',{id:held.id,operation:held.deskOp||(held.deskOp=operationId())});studio.desk={id:made.desk,session:operationId(),openTool:'geo'};sToast('A desk copy of the post is ready. The recommendations wait in Finishing.');await sRoute('desk',made.desk);}catch(error){held.problem=error.message;sGeoReportRender(held);}});
}
async function sGeoAgain(held,button){
  // A press reads the page again; once the assistant found where its text is, it goes ahead by itself.
  const again=async()=>{try{const made=await api('geo-report-again',{id:held.id,operation:held.againOp||(held.againOp=operationId())});held.againOp=null;held.find=null;await sRoute('geo-report',made.id);}catch(error){if(studio.geoReport!==held)return;held.find=sFindTextFrom(error,held.view?.url||'');held.problem=held.find?'':error.message;sGeoReportRender(held);if(held.find)sFindTextFocus();}};
  return button?busy(button,'Reading the page again…',again):again();
}
// In Blogs and on Home: each report marked a GEO report, never a draft.
function sGeoCurrent(){return (studio.reports||[]).filter(row=>!row.newer);}
function sGeoReportCard(row){return sCard(row.title,sAdd(sNode('p','quiet'),sNode('span','badge geo-report-badge','GEO report'),document.createTextNode((row.newer?' An earlier report, read ':' Read ')+sGeoDate(row.read_at))),sStatus(row.status==='ready'?'done':row.status==='working'?'current':'review',row.status==='ready'?'Ready to read':row.status==='working'?'Being written':'Did not finish'),sAdd(sNode('div','bar'),sButton('Open report',()=>sRoute('geo-report',row.id),'filled')));}
function sGeoReportsCard(){const rows=sGeoCurrent().slice(0,5);if(!rows.length)return null;const list=sNode('ul','rows');for(const row of rows)list.append(sAdd(sNode('li','row'),sBead(row.status==='ready'?'done':row.status==='working'?'current':'review'),sAdd(sNode('div','row-text'),sNode('h3','row-title',row.title),sNode('p','row-says','GEO report · read '+sGeoDate(row.read_at))),sButton('Open report',()=>sRoute('geo-report',row.id))));return sCard('GEO reports',list);}
