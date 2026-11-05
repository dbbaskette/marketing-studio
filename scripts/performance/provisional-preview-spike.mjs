// Offline experiment, not a production renderer. Existing helper + new scratch only.
import {mkdir,writeFile,readFile,readdir} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash,randomUUID} from 'node:crypto';
import {createServer} from 'node:http';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {performance} from 'node:perf_hooks';
import assert from 'node:assert/strict';
const [helperArg,scratchArg]=process.argv.slice(2);
if(!helperArg||!scratchArg)throw Error('Usage: node provisional-preview-spike.mjs HELPER NEW_SCRATCH');
const helper=resolve(helperArg),scratch=resolve(scratchArg),exec=promisify(execFile);
await mkdir(scratch,{mode:0o700});
const lib=name=>import(pathToFileURL(join(helper,'scripts/lib',name)).href);
const {compileCompositionFile}=await lib('compose-file.mjs');
const {previewComposition}=await lib('compose-preview.mjs');
const {decodePng}=await lib('contact-sheet.mjs');
const {neutralBrandContract,contractRevision}=await lib('brand-contract.mjs');
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const binding=async dir=>hash(Buffer.concat(await Promise.all((await readdir(dir)).sort().map(async name=>{try{return Buffer.concat([Buffer.from(name),await readFile(join(dir,name))]);}catch(error){if(error.code==='EISDIR')return Buffer.from(name);throw error;}}))));
// The prototype binds only compiled top-level inputs, not the full helper dependency
// contract. That limitation is deliberately recorded, never represented as approval.
let current=null,photo=null,started=false,finished=false;const rows=[];
const eligible=(held,packet)=>held?.attempt===packet?.attempt&&held?.basis===packet?.basis&&!['cancelled','superseded','failed'].includes(held?.state)&&packet?.sha===hash(packet.bytes);
const probe={attempt:'a',basis:'b',state:'working'},packet={attempt:'a',basis:'b',bytes:Buffer.from('synthetic')};packet.sha=hash(packet.bytes);
assert(eligible(probe,packet));for(const changed of [{attempt:'new'},{basis:'changed'},{state:'cancelled'},{state:'superseded'},{state:'failed'}])assert(!eligible({...probe,...changed},packet));assert(!eligible(probe,{...packet,bytes:Buffer.from('corrupt')}));
assert.throws(()=>decodePng(Buffer.from('truncated')));assert(!eligible(probe,null));
const html=`<!doctype html><meta charset="utf-8"><title>Provisional preview experiment</title><style>body{font:18px system-ui;background:#101318;color:#eef1f5;margin:28px}img{display:block;max-width:94vw;max-height:72vh;background:white}p{color:#bfc7d0}</style><h1>Provisional preview experiment</h1><p id="status">Waiting for local renderer. Synthetic slides only.</p><img id="slide" alt="Synthetic rendered slide"><script>
let shown='',busy=false;async function poll(){if(busy)return;busy=true;try{const state=await(await fetch('/state')).json();document.querySelector('#status').textContent=state.label||'Preparing';if(state.image&&state.image!==shown){const image=document.querySelector('#slide');image.src=state.image;await image.decode();await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));shown=state.image;await fetch('/seen?attempt='+encodeURIComponent(state.attempt)+'&phase='+state.phase,{method:'POST'});}}finally{busy=false;}}setInterval(poll,50);poll();fetch('/ready',{method:'POST'});</script>`;
const server=createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://localhost');res.setHeader('Cache-Control','no-store');
  if(url.pathname==='/'){res.setHeader('Content-Type','text/html');res.end(html);return;}
  if(url.pathname==='/ready'){if(!started){started=true;void run();}res.end('ok');return;}
  if(url.pathname==='/state'){const valid=photo&&eligible(current,photo);res.setHeader('Content-Type','application/json');res.end(JSON.stringify({attempt:current?.attempt,phase:current?.state,image:valid?'/image?attempt='+current.attempt+'&phase='+current.state+'&hash='+photo.sha:null,label:finished?'Experiment complete. No deck approved.':current?current.count+' slides · '+current.scenario+' · '+(current.state==='final'?'Sealed bundle ready':'Provisional — do not approve or deliver'):'Waiting'}));return;}
  if(url.pathname==='/image'&&photo&&url.searchParams.get('attempt')===current?.attempt&&eligible(current,photo)){res.setHeader('Content-Type','image/png');res.end(photo.bytes);return;}
  if(url.pathname==='/seen'&&url.searchParams.get('attempt')===current?.attempt){const key=url.searchParams.get('phase')==='final'?'visibleFinalMs':'visibleProvisionalMs';current.row[key]??=performance.now()-current.begun;res.end('ok');return;}
  res.statusCode=404;res.end('No current image');
 }catch(error){res.statusCode=500;res.end(error.message);}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));console.log('VIEWER http://127.0.0.1:'+server.address().port+'/');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function run(){try{
 for(const count of (process.env.BENCH_COUNTS||'6,30,100').split(',').map(Number)){
  const work=join(scratch,String(count));await mkdir(work);
  const original={version:1,title:'Synthetic provisional timing',slides:Array.from({length:count},(_,i)=>({id:'slide_'+(i+1),title:'Synthetic step '+(i+1),sources:['synthetic'],notes:'Fictional benchmark only.',canvas:{type:'stack',direction:'row',gap:'wide',children:[{type:'box',id:'from_'+i,text:'Input'},{type:'box',id:'destination_'+i,text:'Result'}]},connect:[{id:'edge_'+i,from:'from_'+i,to:'destination_'+i,route:'elbow'}]}))};
  let compiled;
  for(const scenario of ['cold','unchanged','one-slide']){
   const begun=performance.now(),row={count,scenario,firstRasterMs:null,visibleProvisionalMs:null,visibleFinalMs:null,rasters:0};
   current={attempt:randomUUID(),basis:'preparing',state:'working',count,scenario,begun,row};photo=null;
   const held=current;
   if(scenario!=='unchanged'){const comp=structuredClone(original),brand=await neutralBrandContract();if(scenario==='one-slide')comp.slides[Math.floor(count/2)].title+=' changed';brand.revision=contractRevision(brand);const file=join(work,scenario+'.json'),brandFile=join(work,scenario+'-brand.json');await writeFile(file,JSON.stringify(comp));await writeFile(brandFile,JSON.stringify(brand));compiled=join(work,scenario+'-compiled');await compileCompositionFile({file,brand:brandFile,output:compiled});}
   held.basis=await binding(compiled);
   const runTool=async(command,args,options)=>{const result=await exec(command,args,options);if(args.includes('-singlefile')){row.rasters++;if(row.firstRasterMs===null){row.firstRasterMs=performance.now()-begun;const bytes=await readFile(args.at(-1)+'.png');const decoded=decodePng(bytes);assert(decoded.width>100&&decoded.height>100);if(await binding(compiled)!==held.basis)throw Error('Compiled inputs changed');const found={attempt:held.attempt,basis:held.basis,bytes,sha:hash(bytes)};if(eligible(current,found))photo=found;row.provisionalReadyMs=performance.now()-begun;}}return result;};
   const result=await previewComposition({file:compiled,output:join(work,scenario+'-preview'),renderer:'local',register:false},{run:runTool});
   row.bundleMs=performance.now()-begun;row.reused=result.reused;
   if(!photo){const bytes=await readFile(result.slides[0].image);photo={attempt:held.attempt,basis:held.basis,bytes,sha:hash(bytes)};}
   held.state='final';const until=Date.now()+2000;while(row.visibleFinalMs===null&&Date.now()<until)await wait(25);
   rows.push(row);await writeFile(join(scratch,'samples.json'),JSON.stringify(rows,null,2));console.log(JSON.stringify(row));await wait(100);
  }
 }
 finished=true;await writeFile(join(scratch,'decision-input.json'),JSON.stringify({helperVersion:JSON.parse(await readFile(join(helper,'package.json'))).version,rows,guardChecks:'attempt/scope/cancel/supersede/failure/hash/corrupt PNG/missing packet passed',limitations:['Prototype compiled-input binding is not the complete runtime/font/asset/source contract.','No approval action or production publication route was added.','First visible means image decode plus two browser animation frames; absent acknowledgement stays null.']},null,2));console.log('DONE');
 }catch(error){finished=true;if(current)current.state='failed';photo=null;console.error(error);process.exitCode=1;}}
