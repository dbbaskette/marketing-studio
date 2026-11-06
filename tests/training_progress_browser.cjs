/* Real native page and scripted worker: active, queued, stop, resume and research handoff. */
const {chromium}=require('playwright'), {spawn}=require('node:child_process');
const assert=require('node:assert/strict'), path=require('node:path'), fs=require('node:fs');
(async()=>{
 const child=spawn(process.env.PYTHON||'python3',['tests/training_progress_fixture.py'],{stdio:['ignore','pipe','pipe']});
 let stderr='',browser; child.stderr.on('data',b=>stderr+=b);
 try {
  const fixture=await new Promise((resolve,reject)=>{
   let out=''; const timer=setTimeout(()=>reject(Error('Fixture timeout: '+stderr)),40000);
   child.stdout.on('data',b=>{out+=b;if(out.includes('\n')){clearTimeout(timer);resolve(JSON.parse(out.split('\n')[0]));}});
   child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+': '+stderr));});
  });
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  const page=await browser.newPage({viewport:{width:390,height:950}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(fixture.url+'&resume='+encodeURIComponent(path.basename(fixture.path)));
  await page.getByRole('tab',{name:'Guide · Writing',exact:true}).waitFor().catch(async error=>{throw Error(error.message+'\n'+await page.locator('body').innerText()+'\n'+JSON.stringify(errors));});
  await page.getByText('Writing the level 101 learner guide.',{exact:true}).waitFor();
  await page.getByText(/Up next: the level 101 brief/).waitFor();
  const activity=page.locator('.desk-progress-activity');
  const toggle=activity.locator('summary').first();
  assert.equal(await activity.evaluate(n=>n.open),false,'Worker metadata starts folded');
  await toggle.focus();await page.keyboard.press('Enter');
  await page.waitForFunction(()=>document.querySelector('.desk-progress-activity').open);
  await page.evaluate(()=>refresh());
  assert.equal(await activity.evaluate(n=>n.open),true,'Polling retains activity disclosure');
  assert.equal(await toggle.evaluate(n=>n===document.activeElement),true,'Polling retains keyboard focus');
  await page.keyboard.press('Enter');
  await page.waitForFunction(()=>!document.querySelector('.desk-progress-activity').open);
  assert.equal(await page.locator('.desk-time').evaluate(n=>n.open),false,'Activity does not open timing');
  const researchToggle=page.locator('[data-key="research-choices-toggle"]');
  await researchToggle.focus();await page.keyboard.press('Enter');
  await page.getByText(/Included uncertainty remains marked/).waitFor();
  await page.evaluate(()=>refresh());
  assert.equal(await researchToggle.evaluate(n=>n===document.activeElement),true,'Saved research disclosure retains focus');
  await page.keyboard.press('Enter');
  assert.equal(await page.getByText('Continue when ready to create materials.').count(),0);
  const before=await page.evaluate(()=>ask('fixture-progress-state'));
  await page.getByRole('tab',{name:'Brief · Queued',exact:true}).click();
  await page.getByText(/Queued. Current step: Write the level 101 learner guide/).last().waitFor();
  for(const width of [320,390,1280]) for(const colorScheme of ['light','dark']){
   await page.setViewportSize({width,height:950});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'horizontal overflow');
   const band=await page.locator('.desk-progress').boundingBox();
   if(width===390)assert(band.height<=300,'Compact phone progress: '+band.height);
   assert.equal(await page.locator('.desk-progress').evaluate(n=>getComputedStyle(n).backdropFilter),'none');
   assert((await researchToggle.boundingBox()).height>=44,'Research disclosure touch target');
   if(process.env.TRAINING_PROGRESS_RESULTS){fs.mkdirSync(process.env.TRAINING_PROGRESS_RESULTS,{recursive:true});await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(process.env.TRAINING_PROGRESS_RESULTS,`queue-${width}-${colorScheme}.png`)});}
  }
  await page.emulateMedia({forcedColors:'active'});
  assert(await page.getByRole('button',{name:'Stop training',exact:true}).isVisible());
  assert.equal(await page.locator('.desk-progress').evaluate(n=>getComputedStyle(n).borderTopStyle),'solid');
  await page.emulateMedia({forcedColors:'none'});
  await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Text enlargement overflow');
  await toggle.focus();assert.equal(await toggle.evaluate(n=>n===document.activeElement),true);
  await page.evaluate(()=>document.documentElement.style.fontSize='');
  await page.reload();await page.getByRole('tab',{name:'Guide · Writing',exact:true}).waitFor();
  assert.equal((await page.evaluate(()=>ask('fixture-progress-state'))).jobs,before.jobs,'reads start no workers');
  await page.getByRole('button',{name:'Stop training',exact:true}).click();
  await page.getByRole('button',{name:'Stop it',exact:true}).click();
  await page.getByRole('tab',{name:'Guide · Queued',exact:true}).waitFor();
  await page.getByRole('tab',{name:'Guide · Queued',exact:true}).click();
  await page.getByText('Queued until you resume training.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Resume training',exact:true}).click();
  await page.getByRole('tab',{name:'Guide · Draft',exact:true}).waitFor();
  assert.deepEqual(errors,[]);
  console.log('PASS Training Studio: actual worker vs queue, creator-approved handoff, read-only reload, stop/resume, compact 320/390/1280 light/dark, keyboard disclosure/polling, forced colors and 200% text');
 } finally {
  if(browser) await browser.close();
  child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)return resolve();child.once('exit',resolve);});
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
