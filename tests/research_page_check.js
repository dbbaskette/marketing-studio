/* Shared source editor behavior with synthetic authenticated adapter calls only. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
let document;
class Node{
 constructor(tag){this.tagName=tag;this.children=[];this.parent=null;this.dataset={};this.listeners={};this.value='';this.className='';this.scrollTop=0;this.disabled=false;this.textContent='';}
 append(...nodes){for(let n of nodes){if(typeof n==='string')n=Object.assign(new Node('#text'),{textContent:n});if(n.parent)n.parent.children=n.parent.children.filter(c=>c!==n);n.parent=this;this.children.push(n);}}
 setAttribute(k,v){this[k]=v;}
 addEventListener(k,fn){this.listeners[k]=fn;}
 replaceChildren(...nodes){this.children=[];this.append(...nodes);}
 replaceWith(n){const i=this.parent.children.indexOf(this);this.parent.children[i]=n;n.parent=this.parent;}
 contains(n){return this===n||this.children.some(c=>c.contains(n));}
 get childNodes(){return this.children;}
 querySelectorAll(selector){return all(this).filter(n=>selector.split(',').some(s=>s.trim()==='[data-key]'?!!n.dataset.key:s.trim()==='details[open][data-key]'?n.tagName==='details'&&n.open&&n.dataset.key:s.trim()==='details[data-key]'?n.tagName==='details'&&n.dataset.key:n.tagName===s.trim()));}
 focus(options){document.activeElement=this;document.focusedWith=options;}
 setSelectionRange(start,end,direction){this.selectionStart=start;this.selectionEnd=end;this.selectionDirection=direction;}
}
function all(n){return n.children.flatMap(c=>[c,...all(c)]);}
document={createElement:t=>new Node(t),createTextNode:t=>Object.assign(new Node('#text'),{textContent:t}),body:new Node('body'),activeElement:null};document.activeElement=document.body;
const context=vm.createContext({document,URL,URLSearchParams,JSON,Object,Array,String,Number,Math,Set,Promise,Error,setTimeout,clearTimeout,module:{exports:{}},btoa:t=>Buffer.from(t,'binary').toString('base64')});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../ui-kit/drafting.js'),'utf8'),context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../ui-kit/research.js'),'utf8'),context);
const kit=context.module.exports;
const settle=async()=>{for(let n=0;n<30;n++)await Promise.resolve();};
const key=(editor,k)=>all(editor.node).find(n=>n.dataset.key===k);
(async()=>{
 let revision=0,state={id:'synthetic',revision:'0',external:false,restricted:false,workers:3,focus:'',sites:['https://example.invalid/docs'],sources:[]},requests=[];
 const request=async sent=>{requests.push(sent);if(sent.action==='capture'){state.sources.push({id:String(state.sources.length+1),name:sent.name||sent.url,kind:sent.kind,origin:sent.url,status:'ready'});}if(sent.action==='configure')Object.assign(state,Object.fromEntries(Object.entries(sent).filter(([k])=>['external','restricted','workers','focus'].includes(k))));state.revision=String(++revision);return JSON.parse(JSON.stringify(state));};
 const ready=[]; const editor=new kit.Editor({request,onChange:()=>ready.push(editor.valid())});document.body.append(editor.node);await settle();
 assert.equal(requests[0].action,'create');assert.equal(editor.valid(),false);assert.equal(editor.choice().web,false);
 const filePicker=all(editor.node).find(n=>n.type==='file');
 assert.ok(filePicker.accept.split(',').includes('.pdf'));assert.ok(filePicker.accept.split(',').includes('application/pdf'));
 await editor.files([{name:'synthetic.pdf',size:5,arrayBuffer:async()=>Buffer.from('%PDF-')}]);
 const pdf=requests.find(r=>r.action==='capture'&&r.name==='synthetic.pdf');
 assert.equal(pdf.kind,'file');assert.equal(Buffer.from(pdf.content,'base64').toString(),'%PDF-');
 assert.equal('keep' in pdf,false,'Keep in library is off unless the studio turns it on');assert.equal(key(editor,'research-keep-0'),undefined);
 state.sources=[];requests.length=0;
 editor.urls='https://example.invalid/a\nhttps://example.invalid/b';await editor.links();assert.equal(editor.value.sources.length,2);assert.equal(editor.urls,'');assert.equal(editor.valid(),true);assert.equal(ready.at(-1),true,'Parent form is notified only after capture unlocks');
 assert.equal(requests.filter(r=>r.action==='capture').length,2);
 editor.urls='http://unsafe.invalid';await editor.links();assert.match(editor.problem,/HTTPS/);assert.equal(requests.filter(r=>r.action==='capture').length,2);
 editor.problem='';editor.urls='draft link stays';editor.pasting=true;editor.text='Unsubmitted source text';editor.render();
 const external=key(editor,'research-external');external.focus();await editor.act('configure',{external:true});
 assert.equal(editor.urls,'draft link stays');assert.equal(editor.text,'Unsubmitted source text');assert.equal(editor.choice().web,true);assert.equal(document.activeElement.dataset.key,'research-external');
 key(editor,'research-add-text').focus();await key(editor,'research-add-text').listeners.click();await settle();
 assert.equal(document.activeElement.dataset.key,'research-paste','Successful capture returns to a stable source action');
 // A redraw while typing keeps the field, the caret and the page where they were.
 {const links=key(editor,'research-urls');links.value='https://example.invalid/typed';links.focus();Object.assign(links,{selectionStart:8,selectionEnd:12,selectionDirection:'forward'});
  editor.render();const again=key(editor,'research-urls');
  assert.notEqual(again,links,'the field was drawn again');assert.equal(document.activeElement,again,'focus stays in the field');
  assert.deepEqual([again.selectionStart,again.selectionEnd,again.selectionDirection],[8,12,'forward'],'the caret stays where it was');
  assert.equal(document.focusedWith?.preventScroll,true,'restoring focus does not scroll the page');}
 assert.ok(!requests.some(r=>['start','generate','publish','google-write'].includes(r.action)));
 state.sources[0].status='needs-attention';editor.value=state;assert.equal(editor.valid(),false);state.sources[0].status='excluded';assert.equal(editor.valid(),true);
 // Add a folder: one field for a folder path or a Google Drive folder link, then what the scan added and each document it skipped, with the reason.
 assert.ok(filePicker.accept.split(',').includes('.pptx'));assert.ok(filePicker.accept.split(',').includes('.xlsx'));
 let folderState={id:'folder',revision:'0',external:false,restricted:false,workers:3,focus:'',sites:[],sources:[]},scanning=false;const folderSent=[];
 const folders=new kit.Editor({value:folderState,request:async sent=>{folderSent.push(sent);
  scanning=all(folders.node).some(n=>n.role==='status'&&n.textContent.startsWith('Scanning the folder and reading its documents.'))&&key(folders,'research-add-folder').disabled;
  if(sent.location==='/missing')throw Error('This folder was not found on this computer. Check the path and try again.');
  if(sent.location==='/empty')return {...JSON.parse(JSON.stringify(folderState)),folder:{where:'local',title:'Empty',found:0,added:0,hidden:0,stopped:null,skipped_count:0,unlisted:0,skipped:[]}};
  folderState={...folderState,revision:'1',sources:[{id:'f1',name:'Compete/Battlecards/EDB battlecard.pdf',kind:'file',origin:'Field kit/Compete/Battlecards/EDB battlecard.pdf',status:'ready'}]};
  return {...JSON.parse(JSON.stringify(folderState)),folder:{where:'local',title:'Field kit',found:2,added:1,hidden:2,stopped:'The scan stopped after looking at 2,000 files and folders. Add a smaller folder to read the rest.',again:true,next:'Add the same folder again to read the next ones.',skipped_count:12,unlisted:1,
   skipped:Array.from({length:11},(_,n)=>({name:'Pictures/picture-'+n+'.png',code:'unsupported',reason:'Not a type that can be read.'}))}};}});
 assert.equal(key(folders,'research-folder').tagName,'input');
 assert.ok(all(folders.node).some(n=>n.className==='field-label'&&n.textContent==='Add a folder'),'the field has a visible label, not only a placeholder');
 assert.ok(all(folders.node).some(n=>n.className==='field-hint'&&n.textContent.includes('Google Docs, Google Slides and Google Sheets')));
 assert.equal(key(folders,'research-folder-said'),undefined);
 await folders.folder();assert.match(folders.problem,/folder path or a Google Drive folder link first/);assert.equal(folderSent.length,0);
 folders.problem='';folders.folderPath='  /Users/synthetic/Field kit  ';folders.render();
 let prevented=0;key(folders,'research-folder').listeners.keydown({key:'Enter',preventDefault:()=>{prevented+=1;}});await settle();await settle();
 assert.equal(prevented,1,'Enter adds the folder and never submits the form around the editor');
 assert.deepEqual(JSON.parse(JSON.stringify(folderSent[0])),{action:'folder',id:'folder',expected:'0',location:'/Users/synthetic/Field kit'});
 assert.equal(scanning,true,'the wait is explained and the action cannot be pressed twice');
 assert.equal('folder' in folders.value,false,'the scan report is not part of the draft');assert.equal(folders.folderPath,'');
 assert.equal(folders.value.sources.length,1);assert.equal(folders.valid(),true);
 assert.ok(all(folders.node).some(n=>n.className==='row-title'&&n.textContent==='Compete/Battlecards/EDB battlecard.pdf'),'what was found is an ordinary source row');
 const folderSaid=key(folders,'research-folder-said');assert.equal(folderSaid.role,'status');
 assert.equal(folderSaid.textContent,'1 document added from Field kit. 12 were skipped: each says why below. 2 hidden items were not looked at. The scan stopped after looking at 2,000 files and folders. Add a smaller folder to read the rest. Add the same folder again to read the next ones.');
 const skippedBox=key(folders,'research-folder-skipped');assert.equal(skippedBox.tagName,'details');
 assert.equal(skippedBox.children[0].tagName,'summary');assert.equal(skippedBox.children[0].textContent,'Skipped documents · 12');
 const skippedList=skippedBox.children[1];assert.equal(skippedList.children.length,11);assert.equal(skippedList.className,'research-source-list research-source-scroll');assert.equal(skippedList.tabIndex,0);
 assert.deepEqual(all(skippedList.children[0]).filter(n=>n.tagName==='p').map(n=>n.textContent),['Pictures/picture-0.png','Not a type that can be read.']);
 assert.ok(all(skippedBox).some(n=>n.textContent==='1 more is not listed here.'));
 skippedBox.open=true;folders.render();assert.equal(key(folders,'research-folder-skipped').open,true,'the skipped list stays open across a redraw');
 folders.folderPath='/empty';await folders.folder();
 assert.equal(key(folders,'research-folder-said').textContent,'No documents were added from Empty. It holds no documents that can be read. Check that this is the folder you meant.');
 assert.equal(key(folders,'research-folder-skipped'),undefined);
 folders.folderPath='/missing';await folders.folder();assert.match(folders.problem,/was not found on this computer/);assert.equal(folders.folderPath,'/missing','a refused path stays in the field to be corrected');
 // A folder location typed and not yet added comes back after a reload, with the other typed entries.
 const Intake=vm.runInContext('Drafting.Intake',context);
 folders.folderPath='https://drive.google.com/drive/folders/synthetic_folder_0001';folders.urls='https://example.invalid/typed';
 const typed=new Intake(async()=>({})).snapshot({title:'Synthetic',sourceEditor:folders}).sourceEntry;
 assert.deepEqual(JSON.parse(JSON.stringify(typed)),{urls:'https://example.invalid/typed',text:'',name:'Pasted notes',pasting:null,keep:null,folderPath:'https://drive.google.com/drive/folders/synthetic_folder_0001'});
 const reopened=new kit.Editor({request,value:{...state,sources:[]},entry:JSON.parse(JSON.stringify(typed))});
 assert.equal(key(reopened,'research-folder').value,'https://drive.google.com/drive/folders/synthetic_folder_0001');assert.equal(key(reopened,'research-urls').value,'https://example.invalid/typed');
 assert.equal(new kit.Editor({request,value:{...state,sources:[]},entry:{urls:'kept'}}).folderPath,'','a draft saved before folders existed still opens');
 // A native inventory can own intake while this adapter retains shared policy.
 const policy=new kit.Editor({request,value:{...state,sources:[],external:false},policyOnly:true});
 assert.equal(all(policy.node).some(n=>n.type==='file'),false,'policy-only adapters have no duplicate upload picker');
 assert.equal(key(policy,'research-urls'),undefined);assert.equal(key(policy,'research-paste'),undefined);
 assert.ok(key(policy,'research-external'));assert.ok(key(policy,'research-workers'));
 assert.equal(policy.valid(true),true);assert.equal(policy.choice(true).documents,true);
 assert.equal(policy.valid(false),false,'external-only policy cannot invent a primary source');
 // Add from library, for a studio whose adapter turns it on: its button beside the others, and what it chose under the list in place of the empty line.
 assert.equal(key(editor,'research-library'),undefined,'Add from library is off unless the studio turns it on');
 let opened=0,chosen=null;
 const library=new kit.Editor({request,value:{...state,sources:[]},library:()=>{opened+=1;},extra:()=>chosen});
 key(library,'research-library').listeners.click();assert.equal(opened,1);
 assert.ok(all(library.node).some(n=>n.textContent==='Add material here, or allow external search below.'));
 chosen=Object.assign(new Node('ul'),{className:'research-source-list'});chosen.append('Synthetic library brief');library.render();
 assert.ok(all(library.node).some(n=>n.textContent==='Synthetic library brief'));
 assert.equal(all(library.node).some(n=>n.textContent==='Add material here, or allow external search below.'),false);
 let full=false;const capped=new kit.Editor({request,value:{...state,sources:[]},library:()=>{},libraryFull:()=>full});
 assert.equal(key(capped,'research-library').disabled,false);full=true;capped.render();assert.equal(key(capped,'research-library').disabled,true,'Add from library waits once the studio says its choices are full');
 // A studio may say the search choice in its own words; without them the shared summary stands.
 assert.ok(all(editor.node).some(n=>n.textContent===kit.summary(editor.value)));
 const worded=new kit.Editor({request,value:{...state,sources:[],external:false},policyHint:value=>value.external?'Searching too.':'Yours only.'});
 assert.ok(all(worded.node).some(n=>n.textContent==='Yours only.'));
 assert.equal(all(worded.node).some(n=>n.textContent===kit.summary(worded.value)),false);
 // Keep in library, for a studio whose adapter turns it on: Keep in library first, Only this project on request, a retry when the library refused.
 const kept=[];let keepState={id:'keeping',revision:'0',external:false,restricted:false,workers:3,focus:'',sites:[],sources:[]};
 const keeping=new kit.Editor({keepChoice:true,request:async sent=>{kept.push(sent);if(sent.action==='capture')keepState.sources.push({id:'k'+keepState.sources.length,name:sent.name,kind:'file',status:'ready'});
  const answer=JSON.parse(JSON.stringify(keepState));if(sent.action==='capture'&&sent.keep)answer.library_kept={state:'failed',problem:'The library is busy.',source:'k'+(keepState.sources.length-1)};
  if(sent.action==='library-keep')answer.library_kept={state:'kept',source:sent.source};return answer;}});
 await settle();
 assert.equal(key(keeping,'research-keep-0')['aria-pressed'],'true');
 await keeping.files([{name:'kept.md',size:3,arrayBuffer:async()=>Buffer.from('# K')}]);
 assert.equal(kept.find(r=>r.action==='capture').keep,true);assert.equal('library_kept' in keeping.value,false,'the library answer is not part of the draft');
 assert.ok(all(keeping.node).some(n=>n.textContent==='Not kept in the Document Library: The library is busy.'));
 key(keeping,'library-keep-k0').listeners.click();await settle();
 assert.deepEqual(JSON.parse(JSON.stringify(kept.at(-1))),{action:'library-keep',id:'keeping',expected:'0',source:'k0'});
 assert.ok(all(keeping.node).some(n=>n.textContent==='Kept in the Document Library too.'));
 // The library keeps a file of any type, so a PowerPoint file kept with Keep in library says so like any other.
 const untaken=new kit.Editor({keepChoice:true,value:{id:'untaken',revision:'0',external:false,restricted:false,workers:3,focus:'',sites:[],sources:[]},request:async sent=>sent.action==='folder'
  ?{id:'untaken',revision:'2',external:false,restricted:false,workers:3,focus:'',sites:[],sources:[{id:'u0',name:'deck.pptx',kind:'file',status:'ready'},{id:'u1',name:'Notes/a.md',kind:'file',status:'ready'}],folder:{where:'local',title:'Kit',found:1,added:1,hidden:0,stopped:null,skipped_count:0,unlisted:0,skipped:[]}}
  :{id:'untaken',revision:'1',external:false,restricted:false,workers:3,focus:'',sites:[],sources:[{id:'u0',name:'deck.pptx',kind:'file',status:'ready'}],library_kept:{state:'kept',source:'u0'}}});
 await untaken.files([{name:'deck.pptx',size:3,arrayBuffer:async()=>Buffer.from('PK!')}]);
 assert.ok(all(untaken.node).some(n=>n.className==='quiet'&&n.textContent==='Kept in the Document Library too.'));
 assert.equal(all(untaken.node).some(n=>n.textContent.includes('files only')),false);assert.equal(/not-taken/.test(fs.readFileSync(path.join(__dirname,'../ui-kit/research.js'),'utf8')),false);
 untaken.folderPath='/synthetic/Kit';await untaken.folder();
 assert.equal(key(untaken,'research-folder-said').textContent,'1 document added from Kit. Documents from a folder are kept in this project only, not in the Document Library.');
 key(keeping,'research-keep-1').listeners.click();await settle();assert.equal(key(keeping,'research-keep-1')['aria-pressed'],'true');
 await keeping.files([{name:'only.md',size:3,arrayBuffer:async()=>Buffer.from('# O')}]);
 assert.equal(kept.filter(r=>r.action==='capture').at(-1).keep,false);
 const draftState={phase:'synthesize',combining:[{id:'one',status:'kept',preview:{basis:'revision-1',sections:[{title:'Basics',text:'A saved explanation.'}],sources:[{title:'Reference',permission:'public',origin:'https://example.invalid/ref'}],truncated:true}},{id:'two',status:'working',questions:['Remaining scope']}]};
 const draft=kit.workingDraft(draftState);assert.match(draft.text,/independent check pending/);assert.match(draft.text,/A saved explanation/);assert.match(draft.text,/Section pending/);assert.match(draft.text,/shortened/);assert.match(draft.text,/https:\/\/example.invalid\/ref/);
 for(const phase of ['stopped','stopping','invalidated','complete','paused'])assert.equal(kit.workingDraft({...draftState,phase}),null);
 const workingDraftNodes=all(kit.progress(draftState));assert.ok(workingDraftNodes.some(n=>n.dataset.key==='research-working-draft-download'));assert.ok(workingDraftNodes.some(n=>n.dataset.key==='research-working-draft-toggle'));
 const incompleteNodes=all(kit.progress({...draftState,phase:'check-incomplete',review_coverage:{read:1,total:3,unread:2}}));assert.ok(incompleteNodes.some(n=>n.textContent==='Independent check incomplete'));assert.ok(incompleteNodes.some(n=>n.textContent.includes('1 of 3 required sources checked')));
 const finalNodes=all(kit.progress({phase:'synthesize',agents:{count:1,active:[{phase:'synthesize',section:'final'}]}}));assert.ok(finalNodes.some(n=>n.textContent==='Assembling the final brief'));
 const progress=kit.progress({phase:'review',streams:[{id:'area1',questions:['Synthetic area'],status:'kept'}]}, {stop:()=>{}});assert.ok(all(progress).some(n=>n.textContent==='Independent check'));assert.ok(all(progress).some(n=>n.dataset.key==='research-stop'));
 for(const [phase,current] of [['investigate',0],['synthesize',1],['review',2],['complete',-1],['paused',-1],['stopped',-1],['needs-attention',-1]]){
  const controls=new Node('div');controls.append(new Node('button'));
  const box=kit.progress({phase,streams:[{id:'kept',questions:['First question','Second question'],status:'kept'},{id:'busy',questions:['Another question'],status:'working'},{id:'failed',questions:['Retry question'],status:'failed'}]}, {controls,timing:{elapsed_seconds:60,active_seconds:1,assistant_seconds:null}});
  const nodes=all(box),stages=nodes.find(n=>n.className==='research-stages');
  assert.equal(stages.children.findIndex(n=>n['aria-current']==='step'),current);
  if(current>=0)assert.ok(nodes.some(n=>n.textContent==='Research · Stage '+(current+1)+' of 3'));
  assert.equal(nodes.filter(n=>n.className==='research-stage-state'&&n.textContent==='Working now').length,current>=0?1:0);
  assert.ok(nodes.some(n=>n.className.split(' ').includes('research-next')),'Every phase explains what remains');
  assert.ok(nodes.some(n=>n.textContent==='1 minute elapsed · 1 second actively working'));
  assert.ok(nodes.some(n=>n.textContent==='Evidence kept'));assert.ok(nodes.some(n=>n.textContent==='Needs retry'));
  assert.ok(nodes.some(n=>n.dataset.key==='research-area-kept-toggle'));
  assert.ok(nodes.some(n=>n.textContent==='Second question'),'Full questions remain available');
  assert.ok(nodes.includes(controls),'Native controls belong to the same progress surface');
  assert.equal(nodes.some(n=>n.className==='research-collected'),['synthesize','review'].includes(phase),'Keep completed evidence subordinate while report/check work continues');
  const meter=nodes.find(n=>n.tagName==='progress');
  assert.equal(Boolean(meter),phase==='investigate');if(meter){assert.equal(meter.value,1);assert.equal(meter.max,3);}
 }
 for(const [count,phase] of [[3,'investigate'],[1,'synthesize'],[1,'review'],[0,'complete']]){
  const nodes=all(kit.progress({phase,agents:{count,active:count?[{phase,id:'synthetic',stream:phase==='investigate'?'area1':null}]:[]}}));
  assert.equal(nodes.find(n=>n.className==='research-agent-count').textContent,String(count));
  assert.equal(nodes.filter(n=>n.className==='research-agent-robot').length,Math.max(1,count));
  assert.ok(nodes.some(n=>n.dataset.key==='research-agents-toggle'));
 }
 for(const agents of [undefined,{count:null,unconfirmed:1,active:[{phase:'investigate',status:'termination-unconfirmed'}]}]){
  const nodes=all(kit.progress({phase:'needs-attention',agents}));
  assert.equal(nodes.find(n=>n.className==='research-agent-count').textContent,'—','Unknown activity must not be displayed as zero');
 }
 const corrected=all(kit.progress({phase:'synthesize',round:2,round_limit:3,agents:{count:1},correction:{areas:[],notes:['Synthetic prose correction']}}));
 assert.ok(corrected.some(n=>n.textContent==='Correction round 2 of 3'));
 assert.ok(corrected.some(n=>n.textContent.includes('sources are not being researched again')));
 assert.ok(corrected.some(n=>n.textContent==='Synthetic prose correction'));
 const previewState={phase:'review',first_readable_seconds:2,combining:[{id:'area1',questions:['Saved question'],status:'kept',preview:{basis:'revision1',sections:[{title:'Saved heading',text:'Saved prose is visible without another author.'}],sources:[{title:'Selected source',permission:'selected'}]}}]};
 const early={phase:'investigate',first_finding_seconds:1,streams:[{id:'fast',status:'kept',questions:['Fast area'],evidence:{basis:'current-basis',generation:2,attempt:3,facts:[{statement:'Accepted early statement',citations:[{source:'s1',quote:'Quoted evidence'}]}],sources:[{id:'s1',title:'Fixture source',origin:'Selected fixture',permission:'selected',context:'partial'}],limitations:['Remaining uncertainty']}},{id:'slow',status:'working'}]};
 const earlyNodes=all(kit.progress(early));assert(earlyNodes.some(n=>n.textContent==='Accepted early statement'));assert(earlyNodes.some(n=>n.textContent.includes('Unreviewed evidence draft')));assert(earlyNodes.some(n=>n.textContent.includes('1 research areas remain')));assert(earlyNodes.some(n=>n.textContent.includes('generation 2 · attempt 3')));assert(earlyNodes.some(n=>n.textContent==='Limitation: Remaining uncertainty'));
 for(const phase of ['stopped','stopping','paused','invalidated'])assert(!all(kit.progress({...early,phase})).some(n=>n.textContent==='Accepted early statement'));
 assert(!all(kit.progress({...early,streams:[{...early.streams[0],status:'waiting'}]})).some(n=>n.textContent==='Accepted early statement'));
 const draftNodes=all(kit.progress(previewState));assert.ok(draftNodes.some(n=>n.textContent==='Draft—independent check pending'));assert.ok(draftNodes.some(n=>n.textContent==='Saved prose is visible without another author.'));assert.ok(draftNodes.some(n=>n.textContent.includes('Not eligible for final delivery')));
 const completeNodes=all(kit.progress({...previewState,phase:'complete',checked_result_seconds:9}));assert.ok(completeNodes.some(n=>n.textContent==='Superseded by the checked research report.'));assert.ok(completeNodes.some(n=>n.textContent.includes('checked result at 9 seconds')));
 let savedNote={revision:0,draft:null},failure='',releaseSave=null;
 const notes=async(id,sent)=>{if(failure)throw Error(failure);if(sent.action==='save'){if(releaseSave)await new Promise(resolve=>releaseSave(resolve));savedNote={revision:savedNote.revision+1,draft:{...(savedNote.draft||{}),...JSON.parse(JSON.stringify(sent.patch))}};}return JSON.parse(JSON.stringify(savedNote));};
 const hooks={notesScope:'synthetic-notes',notes};
 const mount=async(state=previewState,using=hooks)=>{const box=kit.progress(state,using);await settle();return all(box);};
 const noteInput=nodes=>nodes.find(n=>n.dataset.key==='research-queued-note-area1');
 const noteSave=nodes=>nodes.find(n=>n.dataset.key==='research-queue-save-area1');
 const noteStatus=nodes=>nodes.find(n=>n.role==='status');
 let notesNodes=await mount();assert.equal(noteStatus(notesNodes).textContent,'No queued note.');
 noteInput(notesNodes).value='A';noteInput(notesNodes).listeners.input();await noteSave(notesNodes).listeners.click();
 assert.match(noteStatus(notesNodes).textContent,/Queued privately/);
 noteInput(notesNodes).value='B';noteInput(notesNodes).listeners.input();notesNodes=await mount();
 assert.equal(noteInput(notesNodes).value,'B');assert.match(noteStatus(notesNodes).textContent,/not queued until you save/);
 const reloaded=await mount(previewState,{...hooks,notesScope:'synthetic-reload'});
 assert.equal(noteInput(reloaded).value,'A');assert.match(noteStatus(reloaded).textContent,/Queued privately/);
 failure='Changed in another tab';await noteSave(notesNodes).listeners.click();notesNodes=await mount();
 assert.equal(noteInput(notesNodes).value,'B');assert.match(noteStatus(notesNodes).textContent,/Changed in another tab/);failure='';
 let release;releaseSave=resolve=>{release=resolve;};const saving=noteSave(notesNodes).listeners.click();await settle();
 noteInput(notesNodes).value='C';noteInput(notesNodes).listeners.input();release();await saving;releaseSave=null;
 assert.equal(savedNote.draft.note,'B');assert.match(noteStatus(notesNodes).textContent,/not queued until you save/);
 const older=await mount({...previewState,combining:[{...previewState.combining[0],preview:{...previewState.combining[0].preview,basis:'revision2'}}]});
 assert.equal(noteInput(older).value,'C');assert.match(noteStatus(older).textContent,/earlier section revision/);
 // A file of links: every link in it is added, each once, and the page says what happened.
 {const held={id:'links',revision:'0',external:false,restricted:false,workers:3,focus:'',sites:[],sources:[{id:'0',name:'Here',kind:'url',origin:'https://example.invalid/here',status:'ready'}]},sent=[];
  const ask=async one=>{sent.push(one);if(one.action==='capture')held.sources.push({id:String(held.sources.length),name:one.url,kind:'url',origin:one.url,status:'ready'});held.revision=String(sent.length);return JSON.parse(JSON.stringify(held));};
  const many=new kit.Editor({request:ask,value:JSON.parse(JSON.stringify(held))});
  assert.ok(key(many,'research-links-file'),'the shared editor offers a file of links');
  assert.ok(all(many.node).some(n=>n.type==='file'&&/\.csv/.test(n.accept)&&!n.multiple));
  const file=(name,text,size)=>({name,size:size===undefined?text.length:size,text:async()=>text});
  await many.linkFile(file('reading.md','# Reading\n- [One](https://example.invalid/one).\n- http://example.invalid/two, twice: https://example.invalid/one\nhttps://example.invalid/here\n"https://example.invalid/three?x=1&amp;y=2",note\nhttps://someone:secret@example.invalid/private\n'));
  assert.deepEqual(sent.filter(r=>r.action==='capture').map(r=>r.url),['https://example.invalid/one','https://example.invalid/two','https://example.invalid/three?x=1&y=2']);
  assert.equal(many.urls,'');assert.equal(many.problem,'');
  assert.match(many.said,/^3 of 3 links in reading\.md added\. 1 was already here\. 1 was not usable and left out\.$/);
  assert.equal(key(many,'research-links-said').textContent,many.said);
  assert.ok(!JSON.stringify(sent).includes('secret'),'a link carrying a sign-in is never sent');
  held.sources.at(-1).status='needs-attention';many.value=JSON.parse(JSON.stringify(held));
  const unread=new kit.Editor({request:async one=>{if(one.action==='capture')held.sources.push({id:'u',name:one.url,kind:'url',origin:one.url,status:'needs-attention'});return JSON.parse(JSON.stringify(held));},value:JSON.parse(JSON.stringify(held))});
  await unread.linkFile(file('one.txt','https://example.invalid/unread'));
  assert.match(unread.said,/^1 of 1 link in one\.txt added\. 1 could not be read: each says why below\.$/);
  held.sources=held.sources.filter(source=>source.id!=='u');held.sources.at(-1).status='ready';many.value=JSON.parse(JSON.stringify(held));
  const before=sent.length;
  await many.linkFile(file('empty.txt','no links here'));assert.match(many.problem,/no web links/);
  await many.linkFile(file('big.txt','https://example.invalid/big',300000));assert.match(many.problem,/within 256 KB/);
  await many.linkFile(file('again.txt','https://example.invalid/one'));assert.match(many.said,/already a source here/);assert.equal(many.problem,'');
  assert.equal(sent.length,before,'nothing is asked for a file with nothing new');
  {const row=many.source({id:'r',name:'Rolling restarts',kind:'url',origin:'https://example.invalid/post',status:'ready',characters:8764});
   assert.ok(all(row).some(n=>n.textContent==='Page text read · 8,764 characters'),'a link row says its text was read');
   assert.ok(!all(many.source({id:'n',name:'x',kind:'url',origin:'https://example.invalid/x',status:'needs-attention',problem:'no'})).some(n=>/text read/i.test(n.textContent)));}
  // A file chosen while links are still being read waits its turn and is then added.
  {const slow={id:'slow',revision:'0',external:false,restricted:false,workers:3,focus:'',sites:[],sources:[]},order=[];let release;
   const gate=new Promise(done=>{release=done;});
   const waits=new kit.Editor({request:async one=>{if(one.action==='capture'){if(one.kind==='url')await gate;order.push(one.kind);slow.sources.push({id:String(slow.sources.length),name:one.name||one.url,kind:one.kind,origin:one.url||'',status:'ready'});}return JSON.parse(JSON.stringify(slow));},value:JSON.parse(JSON.stringify(slow))});
   const reading=waits.linkFile(file('two.txt','https://example.invalid/w1 https://example.invalid/w2'));await settle();
   const adding=waits.files([{name:'late.pdf',size:5,arrayBuffer:async()=>Buffer.from('%PDF-')}]);await settle();
   assert.deepEqual(order,[],'nothing is read until the first page answers');
   release();await reading;await adding;
   assert.deepEqual(order,['url','url','file']);assert.equal(waits.value.sources.length,3);}
  // A file adds as many links as it holds: none is held back for a count.
  await many.linkFile(file('long.txt',Array.from({length:60},(_,n)=>'https://example.invalid/more-'+n).join('\n')));
  assert.equal(many.value.sources.length,64);assert.equal(many.urls,'');assert.equal(many.problem,'');
  assert.match(many.said,/^60 of 60 links in long\.txt added\.$/);
  // A long list: one line says how it stands, it can be searched while a source is read, and
  // what could not be read is shown alone and left out in one go.
  held.sources[5].status='needs-attention';held.sources[6].status='needs-attention';many.value=JSON.parse(JSON.stringify(held));many.render();
  assert.equal(key(many,'research-overview').textContent,'64 sources · 62 read · 2 could not be read');
  assert.match(many.listNode.className,/research-source-scroll/);
  const find=all(many.node).find(n=>n.dataset.key==='research-find'&&n.tagName==='input');
  find.value='MORE-59';find.listeners.input();
  assert.equal(many.listNode.children.filter(row=>!row.hidden).length,1);assert.equal(key(many,'research-shown').textContent,'Showing 1 of 64.');
  many.busy=true;many.render();
  assert.equal(all(many.node).find(n=>n.dataset.key==='research-find'&&n.tagName==='input').disabled,false,'searching never waits on reading');
  assert.equal(key(many,'research-files').disabled,true);many.busy=false;
  many.find='';await key(many,'research-show-unread').listeners.click();
  assert.equal(many.listNode.children.length,2);assert.match(key(many,'research-shown').textContent,/the 2 that could not be read/);
  const asked=sent.length;
  held.sources.forEach(source=>{if(source.status==='needs-attention')source.status='excluded';});
  await many.excludeUnread();
  assert.deepEqual(sent.slice(asked).map(r=>r.action),['exclude','exclude']);
  assert.equal(key(many,'research-overview').textContent,'64 sources · 62 read · 2 excluded');assert.equal(many.only,'');
  many.value={...many.value,over:'One research run reads at most 100 links.'};many.render();
  assert.equal(key(many,'research-over').textContent,'One research run reads at most 100 links.');assert.equal(many.valid(),false);
  many.value={...many.value,over:null};
  many.progress={done:11,total:60};many.render();assert.match(key(many,'research-reading-now').textContent,/^Reading link 12 of 60\./);many.progress=null;
  assert.deepEqual(JSON.parse(JSON.stringify(kit.linksIn('(https://example.invalid/wiki/Thing_(x)). <a href="https://example.invalid/z">z</a> https://localhost/x'))),{links:['https://example.invalid/wiki/Thing_(x)','https://example.invalid/z'],left:1});
 }
 // Research over many documents: the reading stage says how far it has got and what is open.
 {const reading=kit.progress({phase:'read',streams:[],agents:{count:2,active:[]},reading:{total:766,read:100,of:16,groups:[{from:101,to:150,status:'working'},{from:151,to:200,status:'working'},{from:201,to:250,status:'waiting'}]}});
  const said=all(reading).map(n=>n.textContent).join(' ');
  assert.match(said,/Reading your documents/);assert.match(said,/100 of 766 documents read, in groups of up to 50/);assert.match(said,/Reading documents 101–150 and 151–200 now\./);
  const after=all(kit.progress({phase:'investigate',streams:[],agents:{count:0,active:[]},reading:{total:766,read:766,of:16,groups:[],unused:12,dropped:3}})).map(n=>n.textContent).join(' ');
  assert.match(after,/All 766 documents were read in groups of up to 50/);assert.match(after,/12 bear on no research area and were not passed on\./);assert.match(after,/3 more were relevant/);}
 // The units doing the work (#379): each on its own line under its stage, with its state in
 // words, its tries and its time; the final brief and the whole-research check apart.
 {const text=n=>n.textContent+n.children.map(text).join(''),ago=seconds=>new Date(Date.now()-seconds*1000).toISOString();
  const long='Which synthetic deployment pattern keeps every instance reachable while one of them restarts during a rolling change?';
  const units=[{id:'unit-a',kind:'content',label:long,status:'kept',attempts:2,seconds:3},
   {id:'unit-b',kind:'content',label:'Synthetic question 2',status:'working',attempts:1,seconds:3,started_at:ago(12)},
   {id:'unit-c',kind:'content',label:'Synthetic question 3',status:'failed',attempts:1,seconds:40},
   {id:'unit-d',kind:'content',label:'Synthetic question 4',status:'waiting'},
   {id:'final',kind:'final',label:'the whole research',status:'waiting'}];
  const checking={phase:'review',streams:[{id:'a',questions:['Q'],status:'kept',attempts:1,seconds:61}],
   agents:{count:1,unconfirmed:0,active:[{id:'r1',phase:'review',section:'unit-b',unit:'unit-b',status:'working'}]},
   review_units:units,counts:{check:{working:1,waiting:2,kept:1,failed:1,stopped:0,total:5}}};
  const nodes=all(kit.progress(checking)),byKey=k=>nodes.find(n=>n.dataset.key===k);
  assert.equal(byKey('research-units-check').textContent,'Check sources: 5 parts, 1 working now, 2 waiting, 1 kept, 1 need a retry.','the running stage says its counts in words');
  const group=byKey('research-review-units'),all_=byKey('research-review-units-all');
  assert.equal(all_.tagName,'details');assert.ok(!all_.open,'every part is listed, collapsed');
  assert.equal(byKey('research-review-units-toggle').textContent,'1 of 5 parts of the independent check kept');
  const lines=all_.children[1];assert.equal(lines.tagName,'ul');assert.equal(lines.children.length,5,'lists are lists: one line a part');
  assert.deepEqual(lines.children.map(text),[long+' · Checked and kept · try 2 · took 3 seconds','Synthetic question 2 · Checking · 12 seconds so far','Synthetic question 3 · Retry needed · after 40 seconds','Synthetic question 4 · Waiting','Whole-research check · Waits for every part']);
  assert.equal(lines.children.at(-1).dataset.key,'research-whole-check','the whole-research check is its own line, last');
  assert.ok(lines.children[1].children.at(-1).dataset.started,'a working part is timed in the page from its start, never less than it was');
  const nowBox=group.children[0],now=nowBox.children[1];assert.equal(now.tagName,'ul');
  assert.equal(nowBox.children[0].className,'field-label');assert.equal(nowBox.children[0].textContent,'Check sources: working now or needing a retry','a sighted person reads which stage the list belongs to');
  assert.equal(now['aria-labelledby'],nowBox.children[0].id);
  assert.deepEqual(now.children.map(text),['Synthetic question 2 · Checking · 12 seconds so far','Synthetic question 3 · Retry needed · after 40 seconds'],'what works now and what failed show without opening the list');
  assert.ok(nodes.some(n=>n.textContent==='Independent reviewer · Synthetic question 2'),'a reviewer is named by its part');
  assert.ok(nodes.some(n=>n.textContent.startsWith('Independent reviewers are checking the research in 4 parts')));
  assert.ok(nodes.some(n=>n.textContent==='Evidence kept'));assert.ok(nodes.some(n=>n.textContent===' · took 1 minute'),'an area says how long it took');
  assert.equal(nodes.filter(n=>n.role==='status').length,1,'one short status line, never a list that announces');
  assert.equal(nodes.some(n=>n.style||n['aria-live']),false,'no fixed sizes and nothing that announces every second');
  // Phone width: names wrap in full inside the card's own lists; nothing is cut or held to a width.
  assert.ok(lines.children[0].children[0].textContent.startsWith(long),'a long name is shown in full, to wrap');
  // The final unit at work, and the final brief's author, are different lines.
  const whole=all(kit.progress({...checking,agents:{count:1,active:[{phase:'review',section:'final-check',unit:'final'}]},review_units:units.map(u=>({...u,status:u.kind==='final'?'working':'kept'})),counts:{check:{working:1,waiting:0,kept:4,failed:0,stopped:0,total:5}}}));
  assert.ok(whole.some(n=>n.textContent==='Independent reviewer · the whole research'));assert.ok(!whole.some(n=>n.textContent==='Assembling the final brief'));
  assert.ok(whole.some(n=>n.textContent.startsWith('Every part is checked and kept. One independent reviewer is checking the whole research')));
  // The final brief: its own line after the section drafts, and the heading names it.
  const combining={phase:'synthesize',combining:[{id:'s1',questions:['Section one'],status:'kept',attempts:1,seconds:20},{id:'s2',questions:['Section two'],status:'kept',attempts:2,seconds:30}],
   final_brief:{status:'working',attempts:1,seconds:5,started_at:ago(5)},agents:{count:1,active:[{phase:'synthesize',section:'final'}]},
   counts:{combine:{working:1,waiting:0,kept:2,failed:0,stopped:0,total:3}}};
  const brief=all(kit.progress(combining)),briefKey=k=>brief.find(n=>n.dataset.key===k);
  assert.ok(brief.some(n=>n.textContent==='Assembling the final brief'));
  assert.equal(text(briefKey('research-final-brief')),'Final brief · Writing · 5 seconds so far');
  assert.equal(briefKey('research-final-brief').parent.children.indexOf(briefKey('research-final-brief')),2,'after the section drafts');
  assert.deepEqual(briefKey('research-combining-now').children.map(text),['Final brief · Writing · 5 seconds so far']);
  assert.equal(briefKey('research-combining-now-title').textContent,'Combine findings: working now or needing a retry');
  assert.equal(briefKey('research-units-combine').textContent,'Combine findings: 3 parts, 1 working now, 2 kept.');
  assert.ok(brief.some(n=>text(n)==='Section two · Draft kept · try 2 · took 30 seconds'),'a section kept after a retry reads as kept');
  // A final brief that failed is named, with the section drafts kept, in the server's words.
  const said='The final brief could not finish. All 2 section drafts are kept; only the final brief is written again.';
  const failed=all(kit.progress({...combining,agents:{count:0,active:[]},final_brief:{status:'failed',attempts:1,seconds:9},ended_in:{part:'final-brief',how:'failed',kept:2,total:2,said}}));
  {const top=kit.progress({...combining,agents:{count:0,active:[]},final_brief:{status:'failed'},ended_in:{part:'final-brief',how:'failed',said}}).children.map(n=>n.dataset.key);
   assert.ok(top.indexOf('research-ended')>=0&&top.indexOf('research-ended')<top.indexOf('research-combining'),'where it ended is said before any list');}
  {const halt=all(kit.progress({phase:'stopped',review_units:units,ended_in:{part:'review-unit',how:'stopped',said:'Research stopped during the independent check of “Synthetic question 2”.',next:'Next: continue when you are ready; what is kept is not done again.'}}));
   assert.ok(halt.some(n=>n.textContent.startsWith('Next: continue when you are ready')));assert.ok(!halt.some(n=>n.textContent==='Research needs attention'),'a stop is not a failure');
   const pause=all(kit.progress({phase:'paused',review_units:units,ended_in:{part:'review-unit',how:'paused',said:'Research paused during the independent check of “Synthetic question 2”.',next:'Next: resume when you are ready; what is kept is not done again.'}}));
   assert.ok(pause.some(n=>n.textContent.startsWith('Next: resume when you are ready')),'a pause is called a pause');assert.ok(!pause.some(n=>n.textContent==='Research needs attention'));}
  {const gathering=all(kit.progress({phase:'investigate',streams:[{id:'a',status:'kept'},{id:'b',status:'working',started_at:ago(3)},{id:'c',status:'waiting'}],counts:{gather:{working:1,waiting:1,kept:1,failed:0,stopped:0,total:3}}}));
   assert.ok(gathering.some(n=>n.textContent==='1 of 3 areas collected · 1 working · 1 waiting'),'gathering says how many wait');
   assert.ok(gathering.some(n=>n.textContent===' · 3 seconds so far'),'a working area is timed');}
  assert.ok(failed.some(n=>n.textContent===said));assert.ok(failed.some(n=>n.textContent==='Research needs attention'));
  assert.ok(!failed.some(n=>n.dataset.key==='research-units-combine'),'no running counts once it ended');
  assert.ok(failed.some(n=>n.className==='research-stage-state'&&n.textContent==='Incomplete'));
  assert.ok(failed.some(n=>n.dataset.key==='research-combining-now-title'&&n.textContent==='Combine findings: to be done again'),'nothing works now: the list says what is done again');
  assert.ok(!failed.some(n=>n.textContent==='Working now'));
  // A stopped run says what it kept in the run's one sentence; the page counts nothing itself.
  const stopSaid='Research stopped. Kept: 1 of 1 research area and 2 of 2 section drafts.';
  const stopped=all(kit.progress({phase:'stopped',streams:[{id:'a',status:'kept'}],combining:combining.combining,final_brief:{status:'waiting',again:true},review_units:units,
   counts:{gather:{total:1,kept:1},combine:{total:3,kept:2},check:{total:5,kept:1,waiting:2,failed:1,working:0}},ended_in:{part:'research',how:'stopped',said:stopSaid}}));
  assert.equal(stopped.filter(n=>n.textContent.includes('Kept:')).length,1,'one sentence says what is kept');assert.ok(stopped.some(n=>n.textContent===stopSaid));
  assert.ok(!all(kit.progress({phase:'stopped',streams:[{id:'a',status:'kept'}],counts:{gather:{total:1,kept:1}}})).some(n=>n.textContent.includes('Kept:')),'without the run\'s sentence the page counts nothing of its own');
  // Work done again is never called kept: the final brief and the parts after a correction.
  {const redo=all(kit.progress({phase:'investigate',round:2,correction:{areas:['a'],notes:[]},streams:[{id:'a',status:'waiting'}],combining:[{id:'s1',questions:['Section one'],status:'waiting',again:true},{id:'s2',questions:['Section two'],status:'kept'}],
    final_brief:{status:'waiting',again:true},review_units:units.map(u=>({id:u.id,kind:u.kind,label:u.label,status:'waiting',again:true}))}));
   assert.ok(redo.some(n=>text(n)==='Section one · To be written again'));assert.ok(redo.some(n=>text(n)==='Section two · Draft kept'));
   assert.ok(redo.some(n=>text(n)==='Final brief · To be written again'));
   assert.ok(redo.some(n=>text(n)==='Synthetic question 2 · Checked again after the correction'));assert.ok(redo.some(n=>text(n)==='Whole-research check · Checked again after the correction'));
   assert.ok(redo.some(n=>n.textContent==='5 parts of the independent check to be done again'));assert.ok(redo.some(n=>n.textContent==='1 of 2 section drafts kept'));
   assert.ok(!redo.some(n=>n.textContent==='Section drafts are kept for retry. The assembled research still needs its independent check.'),'no sentence calls every draft kept');}
  // A working part with no start to time it from shows no time.
  {const untimed=all(kit.progress({phase:'review',review_units:[{id:'u',kind:'content',label:'Untimed',status:'working',seconds:400}]}));
   assert.ok(untimed.some(n=>n.tagName==='li'&&text(n)==='Untimed · Checking'));assert.ok(!untimed.some(n=>/so far/.test(n.textContent)),'no stale time');}
  // Live numbers that are not known are said to be unknown, never the limit.
  const unknown=all(kit.progress({...checking,agents:{count:null,unconfirmed:1,active:[{phase:'review',status:'termination-unconfirmed'}]},counts:{check:{working:null,waiting:2,kept:1,failed:1,stopped:0,total:5}}}));
  assert.equal(unknown.find(n=>n.className==='research-agent-count').textContent,'—');
  assert.equal(unknown.find(n=>n.dataset.key==='research-units-check').textContent,'Check sources: 5 parts, how many are working now is not known, 2 waiting, 1 kept, 1 need a retry.');
  // A snapshot saved before this change draws as it did: no parts, no counts, no times.
  const legacy=all(kit.progress({phase:'review',workstreams:[{id:'w1',questions:['Older question'],status:'accepted'}],combining:[{id:'s1',questions:['Older section'],status:'kept'}]}));
  assert.ok(!legacy.some(n=>n.dataset.key==='research-review-units'||(n.dataset.key||'').startsWith('research-units-')||n.dataset.key==='research-final-brief'));
  assert.ok(legacy.some(n=>n.textContent==='Live agent activity is not available for this saved run.'));
  assert.ok(legacy.some(n=>text(n)==='Older section · Draft kept'));
  assert.ok(legacy.some(n=>n.textContent==='Evidence kept'));
  assert.ok(legacy.some(n=>n.textContent==='The independent reviewer is checking the report and brief against the captured sources. Research is not finished until this check passes.'));
  // Every way research stops, as the run reports it: nothing on the card disagrees with the
  // run's one sentence (#379). A stop outside the check gathers the evidence again, so
  // nothing else on the card says kept, "only the unfinished work" or a correction.
  {const area=(n,status,again)=>({id:'a'+n,questions:['Area question '+n],status,...(again?{again:true}:{})});
   const section=(n,status,again)=>({id:'a'+n,questions:['Section question '+n],status,...(again?{again:true}:{})});
   const part=(n,status,again)=>({id:'u'+n,kind:'content',label:'Part question '+n,status,...(again?{again:true}:{})});
   const whole=(status,again)=>({id:'final',kind:'final',label:'the whole research',status,...(again?{again:true}:{})});
   const regathered={part:'research',how:'stopped',regathers:true,said:'Research stopped. Going on gathers the evidence again; your sources are kept.',
    next:'Next: go on when you are ready; the research starts again from your sources.'};
   const stops={
    'stopped while gathering':{phase:'stopped',round:1,streams:[area(0,'stopped'),area(1,'waiting'),area(2,'waiting'),area(3,'waiting')],
     counts:{gather:{working:0,waiting:3,kept:0,failed:0,stopped:1,total:4}},ended_in:regathered},
    'stopped while writing a section':{phase:'stopped',round:1,streams:[0,1,2,3].map(n=>area(n,'waiting')),
     combining:[section(0,'stopped',true),section(1,'stopped',true),section(2,'waiting',true),section(3,'waiting',true)],final_brief:{status:'waiting',again:true},
     counts:{gather:{working:0,waiting:4,kept:0,failed:0,stopped:0,total:4},combine:{working:0,waiting:3,kept:0,failed:0,stopped:2,total:5}},ended_in:regathered},
    'stopped while writing the final brief':{phase:'stopped',round:1,streams:[0,1,2,3].map(n=>area(n,'waiting')),
     combining:[0,1,2,3].map(n=>section(n,'waiting',true)),final_brief:{status:'waiting',again:true,attempts:1,seconds:4},
     counts:{gather:{working:0,waiting:4,kept:0,failed:0,stopped:0,total:4},combine:{working:0,waiting:5,kept:0,failed:0,stopped:0,total:5}},ended_in:regathered},
    // As an older snapshot of this step still holds it: the correction of round 1 beside a stop
    // that gathers the evidence again. The run no longer reports it; the page draws none of it.
    'stopped in round 2 while gathering':{phase:'stopped',round:2,round_limit:3,correction:{areas:['a1'],notes:['Synthetic narrower claim.']},
     streams:[0,1,2,3].map(n=>area(n,'waiting')),combining:[0,1,2,3].map(n=>section(n,'waiting',true)),final_brief:{status:'waiting',again:true},
     review_units:[part(0,'waiting',true),part(1,'waiting',true),part(2,'waiting',true),part(3,'waiting',true),whole('waiting',true)],
     counts:{gather:{working:0,waiting:4,kept:0,failed:0,stopped:0,total:4},combine:{working:0,waiting:5,kept:0,failed:0,stopped:0,total:5},check:{working:0,waiting:5,kept:0,failed:0,stopped:0,total:5}},ended_in:regathered},
    'stopped during the check':{phase:'stopped',round:1,streams:[0,1,2,3].map(n=>area(n,'kept')),combining:[0,1,2,3].map(n=>section(n,'kept')),final_brief:{status:'kept'},
     review_units:[part(0,'kept'),part(1,'kept'),part(2,'stopped'),part(3,'waiting'),whole('waiting')],
     counts:{gather:{working:0,waiting:0,kept:4,failed:0,stopped:0,total:4},combine:{working:0,waiting:0,kept:5,failed:0,stopped:0,total:5},check:{working:0,waiting:2,kept:2,failed:0,stopped:1,total:5}},
     ended_in:{part:'review-unit',how:'stopped',label:'Part question 2',kept:2,total:5,said:'Research stopped during the independent check of “Part question 2”. The checks of the other 2 parts are kept; only what is left is checked again, then the whole research.',
      next:'Next: continue when you are ready; what is kept is not done again.'}},
    'paused while gathering':{phase:'paused',round:1,streams:[area(0,'kept'),area(1,'kept'),area(2,'stopped'),area(3,'waiting')],
     counts:{gather:{working:0,waiting:1,kept:2,failed:0,stopped:1,total:4}},
     ended_in:{part:'research',how:'paused',said:'Research paused. Kept: 2 of 4 research areas.',next:'Next: resume when you are ready; what is kept is not done again.'}}};
   const drawn={};
   for(const [what,state] of Object.entries(stops)){
    const nodes=all(kit.progress(state)),said=state.ended_in.said;
    drawn[what]=nodes.filter(n=>n.textContent&&!n.children.length).map(n=>n.textContent);
    const others=nodes.filter(n=>n.textContent&&n.textContent!==said).map(n=>n.textContent);
    assert.ok(nodes.some(n=>n.textContent===said),what+': the run\'s sentence is said');
    assert.ok(nodes.some(n=>n.textContent===state.ended_in.next),what+': the next step is the run\'s own');
    for(const text of others){
     assert.ok(!/only the unfinished work/i.test(text),what+': '+text);
     if(state.ended_in.regathers){
      assert.ok(!/kept/i.test(text),what+': nothing else says kept: '+text);
      assert.ok(!/correction/i.test(text),what+': no correction is under way: '+text);
     }
    }
    const stage=nodes.filter(n=>n.className==='research-stage-state').map(n=>n.textContent);
    const word=state.phase==='paused'?'Paused':'Stopped';
    assert.deepEqual(stage,state.ended_in.regathers?[word,'Still to do','Still to do']:state.ended_in.part==='review-unit'?['Complete','Complete',word]:[word,'Still to do','Still to do'],what+': the stages say where it stopped');
    // The lists agree with the counts and with the sentence.
    const kept=state.counts.gather.kept;
    assert.ok(nodes.some(n=>n.textContent.startsWith(kept+' of 4 areas collected')),what+': areas as counted');
    if(state.review_units&&!state.ended_in.regathers){
     const keptLines=nodes.filter(n=>n.tagName==='li'&&/· Checked and kept/.test(text(n))&&n.parent.parent.dataset.key==='research-review-units-all').length;
     assert.equal(keptLines,state.counts.check.kept,what+': kept lines as counted');
     assert.ok(nodes.some(n=>n.textContent===state.counts.check.kept+' of 5 parts of the independent check kept'));
    }
   }
   assert.ok(drawn['stopped while writing a section'].some(t=>t==='Section question 0 · Stopped'),'a section the stop ended says it was stopped');
   assert.ok(drawn['stopped in round 2 while gathering'].some(t=>t==='Part question 0 · To be checked again'),'no part is checked "after the correction" once the correction is gone');
   assert.ok(!drawn['stopped in round 2 while gathering'].some(t=>/Correction round/.test(t)));
   console.log('CARD TEXT '+JSON.stringify(drawn));}
  // A preview saved without its revision or sources prints nothing for what is missing.
  {const bare=all(kit.progress({phase:'review',combining:[{id:'p',questions:['Q'],status:'kept',preview:{sections:[{title:'T',text:'x'}]}}]})).map(n=>n.textContent);
   assert.ok(!bare.some(t=>/Revision undefined|Sources: \.|undefined/.test(t)),'nothing missing is printed');}
  // Any shape a saved or partly written snapshot may hold draws without throwing, and a number
  // that is missing is not said.
  for(const [what,hostile] of [['null units',{review_units:[null]}],['odd units',{review_units:[1,'x',[],{id:null,label:7,status:{}}]}],['null areas',{streams:[null,{id:'a',questions:[null,{question:'Q'}],status:'kept'}]}],
    ['null sections',{combining:[null,{id:'s',questions:null,status:'kept',preview:'text'}]}],['null final brief',{final_brief:null}],['partial final brief',{final_brief:{}}],['string final brief',{final_brief:'kept'}],
    ['null agents',{agents:null}],['null active',{agents:{count:1,active:[null,{phase:'review'}]}}],['counts missing stages',{counts:{}}],['partial counts',{phase:'review',review_units:[{id:'u',status:'kept'}],counts:{check:{total:2}}}],
    ['partial gather counts',{counts:{gather:{total:3}},streams:[{id:'a',status:'kept'}]}],['counts null',{counts:null}],['ended_in string',{ended_in:'stopped'}],['ended_in number',{ended_in:3}],['ended_in array',{ended_in:['x']}],
    ['ended_in without words',{ended_in:{part:'final-brief',said:null}}],['preview without basis',{combining:[{id:'p',status:'kept',preview:{sections:[],sources:[{},null]}}]}],['phase object',{phase:{}}],['reading odd',{reading:{total:5,read:1,groups:[null]}}],['workstreams null',{workstreams:[null]}],['everything null',{streams:null,combining:null,review_units:null,counts:null,agents:null,final_brief:null,ended_in:null}]]){
   let drawn;assert.doesNotThrow(()=>{drawn=kit.progress({phase:'review',...hostile});},what);
   assert.ok(!all(drawn).some(n=>/undefined|NaN|\[object Object\]/.test(n.textContent)),what+': nothing says undefined');}
  assert.equal(all(kit.progress({phase:'review',review_units:[{id:'u',status:'kept'}],counts:{check:{total:2}}})).find(n=>n.dataset.key==='research-units-check').textContent,'Check sources: 2 parts.');
  for(const value of [null,'x',3,[]])assert.equal(kit.progress(value),null);
  assert.doesNotThrow(()=>kit.workingDraft({phase:'synthesize',combining:[null,{status:'kept',preview:{basis:'b',sections:[null,{title:'T',text:'x'}],sources:[null]}}]}));
  const older=all(kit.progress({phase:'review',agents:{count:1,active:[{phase:'review',section:'final-check',unit:'final'}]}}));
  assert.ok(older.some(n=>n.textContent==='Independent reviewer · the whole research'));assert.ok(!older.some(n=>n.textContent==='Assembling the final brief'));}
 console.log('PASS shared source editor: explicit scope, mixed links, validation, draft/focus preservation, progress, no provider actions');
})().catch(error=>{console.error(error);process.exitCode=1;});
