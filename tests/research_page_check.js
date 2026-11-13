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
 focus(){document.activeElement=this;}
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
 assert.ok(!requests.some(r=>['start','generate','publish','google-write'].includes(r.action)));
 state.sources[0].status='needs-attention';editor.value=state;assert.equal(editor.valid(),false);state.sources[0].status='excluded';assert.equal(editor.valid(),true);
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
 console.log('PASS shared source editor: explicit scope, mixed links, validation, draft/focus preservation, progress, no provider actions');
})().catch(error=>{console.error(error);process.exitCode=1;});
