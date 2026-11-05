// Fault probes against the same helper, using a disposable compiled fixture.
import assert from 'node:assert/strict';
import {readFile,readdir,stat} from 'node:fs/promises';
import {join,resolve,dirname} from 'node:path';
import {pathToFileURL} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const [helperArg,compiledArg]=process.argv.slice(2),helper=resolve(helperArg),compiled=resolve(compiledArg);
const {previewComposition}=await import(pathToFileURL(join(helper,'scripts/lib/compose-preview.mjs')));
const {decodePng}=await import(pathToFileURL(join(helper,'scripts/lib/contact-sheet.mjs')));
const exec=promisify(execFile);
for(const fault of ['partial-failure','cancelled','superseded']){
 const output=join(dirname(compiled),'fault-'+fault);let rasters=0,visible=null,current='attempt-1',stopped=false;
 const run=async(command,args,options)=>{
  if(stopped)throw Error(fault);
  const result=await exec(command,args,options);
  if(args.includes('-singlefile')){
   rasters++;const bytes=await readFile(args.at(-1)+'.png');decodePng(bytes);
   const packet={attempt:'attempt-1',bytes};visible=packet;
   if(fault==='superseded')current='attempt-2';
   stopped=true;
   if(stopped||visible.attempt!==current)visible=null;
   throw Error(fault); // At a confirmed tool return; no orphan subprocess.
  }
  return result;
 };
 await assert.rejects(()=>previewComposition({file:compiled,output,renderer:'local',register:false,refresh:true},{run}),new RegExp(fault));
 assert.equal(rasters,1);assert.equal(visible,null);
 await assert.rejects(()=>stat(output),/ENOENT/);
 const cache=join(dirname(compiled),'.harness-slides','render-bundles');
 assert(!(await readdir(cache)).some(name=>name.startsWith('.stage-')),'failed temporary bundle removed');
 console.log('PASS '+fault+': first PNG decoded; current preview cleared; no final output or partial bundle');
}
