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
  const map=page.getByRole('region',{name:'Training workflow',exact:true});
  await map.waitFor();
  assert.equal(await map.locator('.desk-flow-expanded').evaluate(n=>n.open),false,'Detailed map starts folded');
  assert((await map.locator('.desk-flow-summary').boundingBox()).height<150,'Compact phone workflow summary');
  // Polling used to detach the reader every few seconds, dismissing its native menu.
  const chapter=page.getByRole('combobox',{name:'Section of Plan',exact:true});
  await chapter.selectOption({label:'Objectives'});
  await chapter.focus();
  await page.evaluate(()=>{window.readingNodes={panel:document.querySelector('#desk-material-panel'),picker:document.querySelector('[aria-label="Section of Plan"]')};});
  const readingY=await page.evaluate(()=>window.scrollY);
  for(let poll=0;poll<3;poll++)await page.evaluate(()=>refresh());
  assert(await page.evaluate(()=>readingNodes.panel===document.querySelector('#desk-material-panel')&&readingNodes.picker===document.activeElement),'Unrelated active polls must keep the reader and focused picker mounted');
  assert.equal(await chapter.locator('option:checked').innerText(),'Objectives');
  assert(Math.abs(await page.evaluate(()=>window.scrollY)-readingY)<3,'Polling keeps reading scroll position');
  await page.getByRole('button',{name:'Next section',exact:true}).click();
  await page.getByRole('heading',{name:'M1 — Rolling restarts (25 min)',exact:true}).waitFor();
  await page.getByRole('button',{name:'Previous section',exact:true}).click();
  await page.getByRole('heading',{name:'Objectives',exact:true}).waitFor();
  for(const width of [390,1280]){
   await page.setViewportSize({width,height:950});
   await chapter.waitFor();
   await page.evaluate(()=>refresh());
   assert.equal(await chapter.locator('option:checked').innerText(),'Objectives');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Reading controls fit');
   if(process.env.TRAINING_PROGRESS_RESULTS){fs.mkdirSync(process.env.TRAINING_PROGRESS_RESULTS,{recursive:true});await chapter.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.TRAINING_PROGRESS_RESULTS,`reader-${width}.png`)});}
  }
  await page.setViewportSize({width:390,height:950});
  await page.getByRole('region',{name:'Review level 101'}).getByText('1 of 3 ready to read · 0 of 3 marked ready · 1 draft awaiting your review.',{exact:true}).waitFor();
  await page.getByText(/Mark ready becomes available when every material/).waitFor();
  assert.equal(await page.getByRole('button',{name:'Mark ready',exact:true}).count(),0);
  await page.getByText('Explore workflow',{exact:true}).click();
  const mapMaterials=map.locator('#desk-flow-materials');
  assert.equal(await mapMaterials.getAttribute('data-state'),'working');
  assert.equal(await map.locator('#desk-flow-research').getAttribute('data-state'),'complete');
  await map.locator('#desk-flow-research').getByText('Creator accepted',{exact:true}).waitFor();
  const mapJobs=(await page.evaluate(()=>ask('fixture-progress-state'))).jobs;
  await mapMaterials.focus();await page.keyboard.press('Enter');
  await page.getByRole('heading',{name:/Plans, guides & briefs/}).waitFor();
  await page.evaluate(()=>refresh());
  assert.equal(await mapMaterials.getAttribute('aria-expanded'),'true');
  assert.equal(await mapMaterials.evaluate(n=>n===document.activeElement),true);
  if(process.env.TRAINING_PROGRESS_RESULTS){fs.mkdirSync(process.env.TRAINING_PROGRESS_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.TRAINING_PROGRESS_RESULTS,'map-materials-390.png')});}
  // Check after the disclosure transition, not just in the refresh promise's frame.
  // Restoring [open] after insertion used to add scroll drift on each background poll.
  for(const width of [390,1280]) for(const reducedMotion of ['no-preference','reduce']){
   await page.setViewportSize({width,height:950});await page.emulateMedia({reducedMotion});
   await chapter.selectOption({label:'M1 — Rolling restarts (25 min)'});
   await chapter.focus();
   await page.waitForTimeout(350); // The disclosure's height transition is 250 ms.
   await page.evaluate(()=>window.scrollTo(0,document.querySelector('.desk-reading').getBoundingClientRect().top+scrollY-250));
   const beforeScroll=await page.evaluate(()=>({y:scrollY,top:document.querySelector('.desk-reading').getBoundingClientRect().top}));
   for(let poll=0;poll<4;poll++){
    await page.evaluate(()=>refresh());
    await page.waitForTimeout(350);
    const afterScroll=await page.evaluate(()=>({y:scrollY,top:document.querySelector('.desk-reading').getBoundingClientRect().top}));
    assert(Math.abs(afterScroll.y-beforeScroll.y)<3,`Delayed scroll drift at ${width}/${reducedMotion}: ${JSON.stringify({beforeScroll,afterScroll})}`);
    assert(Math.abs(afterScroll.top-beforeScroll.top)<3,'Reading position remains stable after animation frames');
   }
   assert.equal(await chapter.evaluate(n=>n===document.activeElement),true);
  }
  await page.setViewportSize({width:390,height:950});
  await page.locator('[data-key="desk-flow-open blueprint@101"]').click();
  await page.locator('#desk-card-blueprint-101').waitFor();
  assert.equal(await page.locator('#desk-card-blueprint-101').evaluate(n=>n===document.activeElement),true);
  await mapMaterials.click();
  await map.locator('#desk-flow-research').click();
  await map.getByText(/independent-check notes are kept/).waitFor();
  await page.getByRole('button',{name:'Open research & sources',exact:true}).click();
  const sourcesTab=page.getByRole('tab',{name:'Research & sources',exact:true});
  assert.equal(await sourcesTab.getAttribute('aria-selected'),'true');
  assert.equal(await sourcesTab.evaluate(n=>n===document.activeElement),true);
  assert((await page.locator('#desk-material-panel').boundingBox()).y<700,'Research opens in view');
  await map.locator('#desk-flow-research').click();
  assert.equal((await page.evaluate(()=>ask('fixture-progress-state'))).jobs,mapJobs,'Map navigation starts no work');
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
  await page.getByText(/Warnings appear only where you requested them/).waitFor();
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
   await page.waitForFunction(()=>document.querySelector('[data-key="research-choices-toggle"]')?.getBoundingClientRect().height>=44); // Resolve after breakpoint repaint.
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
  assert.equal(await mapMaterials.getAttribute('data-state'),'stopped');
  await page.getByRole('tab',{name:'Guide · Queued',exact:true}).click();
  await page.getByText('Queued until you resume training.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Resume training',exact:true}).click();
  await page.getByRole('tab',{name:'Guide · Draft',exact:true}).waitFor();
  await page.waitForFunction(()=>document.querySelector('#desk-flow-materials')?.dataset.state==='complete');
  assert.equal(await map.locator('#desk-flow-review').getAttribute('data-state'),'needs-you');
  assert.deepEqual(errors,[]);
  console.log('PASS Training Studio: actual worker vs queue, creator-approved handoff, read-only reload, stop/resume, compact 320/390/1280 light/dark, keyboard disclosure/polling, delayed scroll retention with expanded panels and normal/reduced motion, forced colors and 200% text');
 } finally {
  if(browser) await browser.close();
  child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)return resolve();child.once('exit',resolve);});
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
