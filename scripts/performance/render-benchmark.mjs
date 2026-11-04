// Explicit, offline benchmark. Requires an existing Harness Slides checkout with
// its normal dependencies; creates synthetic work only in the chosen scratch path.
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {performance} from 'node:perf_hooks';
import os from 'node:os';
const [helperArg,scratchArg]=process.argv.slice(2);
if(!helperArg||!scratchArg)throw Error('Usage: node render-benchmark.mjs HELPER_CHECKOUT NEW_SCRATCH_DIRECTORY');
const helper=resolve(helperArg),scratch=resolve(scratchArg),exec=promisify(execFile);
if (!process.env.BENCH_SUMMARY_ONLY) await mkdir(scratch,{mode:0o700});
const lib=name=>import(pathToFileURL(join(helper,'scripts/lib',name)).href);
const {compileCompositionFile}=await lib('compose-file.mjs');
const {previewComposition,verifyCriticPacket}=await lib('compose-preview.mjs');
const {neutralBrandContract,contractRevision}=await lib('brand-contract.mjs');
const {cachedCompositionArtifact}=await lib('render-bundle.mjs');
const counts=(process.env.BENCH_COUNTS||'6,30,100').split(',').map(Number);
const repeats=Number(process.env.BENCH_REPEATS||3),rows=process.env.BENCH_SUMMARY_ONLY?JSON.parse(await readFile(join(scratch,'samples.json'))):[];
const sample=async fn=>{const start=performance.now();const result=await fn();return [result,performance.now()-start];};
if (!process.env.BENCH_SUMMARY_ONLY) for(const count of counts)for(let trial=0;trial<repeats;trial++){
 const work=join(scratch,`${count}-${trial}`);await mkdir(work);
 const original={version:1,title:'Synthetic render timing',slides:Array.from({length:count},(_,i)=>({id:`slide_${i+1}`,title:`Synthetic step ${i+1}`,sources:['synthetic'],notes:'Synthetic benchmark; no user material.',canvas:{type:'stack',direction:'row',gap:'wide',children:[{type:'box',id:`from_${i}`,text:'Input'},{type:'box',id:`destination_${i}`,text:'Result'}]},connect:[{id:`edge_${i}`,from:`from_${i}`,to:`destination_${i}`,route:'elbow'}]}))};
 let compiled;
 for(const scenario of ['cold','unchanged','one-slide','neighbor','global-style','font','final-export']){
  const comp=structuredClone(original),brand=await neutralBrandContract();
  if(scenario==='one-slide'||scenario==='neighbor')comp.slides[Math.floor(count/2)].title+=' changed';
  if(scenario==='neighbor')comp.slides[Math.floor(count/2)+1].title+=' neighbor';
  if(scenario==='global-style')brand.design.colors.accentAqua='#994400';
  if(scenario==='font')brand.design.fontFamily='Helvetica';
  brand.revision=contractRevision(brand);
  let compileMs=0;
  if(!['unchanged','final-export'].includes(scenario)){
   const file=join(work,scenario+'.json'),brandFile=join(work,scenario+'-brand.json');
   await writeFile(file,JSON.stringify(comp));await writeFile(brandFile,JSON.stringify(brand));
   compiled=join(work,scenario+'-compiled');
   [,compileMs]=await sample(()=>compileCompositionFile({file,brand:brandFile,output:compiled}));
  }
  let conversionMs=0,rasterMs=0,rasters=0,firstImageMs=null;
  const begun=performance.now();
  const run=async(command,args,options)=>{
   const [result,ms]=await sample(()=>exec(command,args,options));
   if(args.includes('--convert-to'))conversionMs+=ms;
   if(args.includes('-singlefile')){rasterMs+=ms;rasters++;if(firstImageMs===null)firstImageMs=performance.now()-begun;}
   return result;
  };
  const output=join(work,scenario+'-preview');
  const [result,previewMs]=await sample(()=>previewComposition({file:compiled,output,renderer:'local',register:false,refresh:scenario==='final-export'},{run}));
  const [,cacheVerifyMs]=await sample(()=>cachedCompositionArtifact(compiled));
  const packet=JSON.parse(await readFile(join(output,'critic.json')));
  const [,inspectionMs]=await sample(()=>verifyCriticPacket(output,packet));
  const row={count,trial,scenario,compileMs,previewMs,conversionMs,rasterMs,rasters,cacheVerifyMs,inspectionMs,firstImageMs,totalMs:compileMs+previewMs,reused:result.reused};
  rows.push(row);await writeFile(join(scratch,'samples.json'),JSON.stringify(rows,null,2));
  console.log(JSON.stringify(row));
 }
}
const percentile=(xs,q)=>xs.toSorted((a,b)=>a-b)[Math.ceil(xs.length*q)-1];
const metrics=['totalMs','compileMs','previewMs','conversionMs','rasterMs','cacheVerifyMs','inspectionMs','firstImageMs'];
const summaries=counts.flatMap(count=>[...new Set(rows.map(r=>r.scenario))].map(scenario=>{
 const selected=rows.filter(r=>r.count===count&&r.scenario===scenario);
 return {count,scenario,n:selected.length,rasters:selected.map(r=>r.rasters),...Object.fromEntries(metrics.map(k=>{const xs=selected.map(r=>r[k]).filter(v=>v!==null);return [k,xs.length?{p50:percentile(xs,.5),p95:percentile(xs,.95)}:null];}))};
}));
const report={schema:1,environment:{platform:os.platform(),arch:os.arch(),release:os.release(),node:process.version,helperVersion:JSON.parse(await readFile(join(helper,'package.json'),'utf8')).version},notes:['Synthetic diagrams; local conversion only; no provider, Google, brand or owner acceptance.','Three samples: p95 is the maximum observed sample, not a stable tail estimate.','firstImageMs measures the first raster file, not a streamed UI preview. Warm cache exposes its verified preview at return.','cacheVerifyMs is an additional full artifact verification probe; inspectionMs verifies critic files, never visual judgment.','final-export uses refresh for a fresh whole-deck conversion/raster pass; it does not mark any deck approved.'],summaries};
await writeFile(join(scratch,'report.json'),JSON.stringify(report,null,2));
