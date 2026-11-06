/* Long native guide navigation, measured without models or personal state. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
(async()=>{
 const child=spawn(process.env.PYTHON||'python3',['tests/slide_review_fixture.py','training','--rendered'],{stdio:['ignore','pipe','pipe']});
 let diagnostic='',browser;child.stderr.on('data',b=>diagnostic+=b);
 try{
  const fixture=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostic)),40000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostic));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  if(process.env.READING_SCRIPT)await page.route('**/drafts.js',route=>route.fulfill({contentType:'text/javascript',body:fs.readFileSync(process.env.READING_SCRIPT)}));
  // Keep the navigation draft local: the long outline is a display fixture, not
  // a new backend document format. Existing desk tests verify acknowledged saves.
  await page.route('**/api/drafts/save',route=>route.fulfill({status:503,json:{error:'Synthetic held save.'}}));
  await page.route('**/api/drafts/card?*',async route=>{
   const response=await route.fetch(),data=await response.json();
   if(data.kind==='document'){
    data.opening='';const first=data.sections[0];
    data.sections=Array.from({length:8},(_,i)=>({...first,id:i?'fixture-section-'+i:first.id,
     heading:(i+1)+'. '+['Understand high availability and disaster recovery','Choose an installation and operating approach','Prepare a reliable production environment','Explain failover roles and responsibilities','Practice backup and recovery procedures','Recognize operating costs and tradeoffs','Handle questions and common objections','Review the key lessons and next steps'][i]}));
   }
   await route.fulfill({response,json:data});
  });
  await page.goto(fixture.url+'&resume='+encodeURIComponent(path.basename(fixture.path)));
  await page.getByRole('tab',{name:/^Guide ·/}).click();await page.locator('.desk-reading').waitFor();
  const jobs=(await page.evaluate(()=>ask('fixture-review-state'))).jobs;
  for(const width of [1280,390]){
   await page.setViewportSize({width,height:950});await page.emulateMedia({colorScheme:'light',reducedMotion:'reduce'});
   await page.evaluate(()=>{deskHeld(view.path).drawn='';paintDesk(false);scrollTo(0,0);});
   const before=await page.locator('.desk-reading').evaluate(n=>Math.round(n.getBoundingClientRect().top+scrollY));
   console.log(JSON.stringify({width,firstReadingPixel:before,sections:8,scope:'Synthetic eight-section guide; document position from page top'}));
   if(process.env.READING_RESULTS){fs.mkdirSync(process.env.READING_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.READING_RESULTS,'reading-'+width+'.png')});}
  }
  if(!process.env.READING_BASELINE)for(const width of [1280,390]){
   await page.setViewportSize({width,height:950});
   await page.waitForFunction(narrow=>document.getElementById('toolbar').classList.contains('toolbar-compact')===narrow,width<832);
   const picker=page.getByLabel('Section of Guide',{exact:true});
   assert.equal(await picker.locator('option').count(),8);
   await picker.focus();await picker.selectOption('fixture-section-5');
   assert(await picker.evaluate(n=>n===document.activeElement),'Section change keeps selector focus');
   await page.getByRole('heading',{name:'6. Recognize operating costs and tradeoffs',exact:true}).waitFor();
   await page.evaluate(()=>refresh());assert.equal(await picker.inputValue(),'fixture-section-5');
   await picker.selectOption({index:0});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   const checks=page.locator('.desk-checks');
   assert.equal(await checks.evaluate(n=>n.open),false,'Successful checks start folded');
   await checks.locator('summary').click();await page.evaluate(()=>{deskHeld(view.path).drawn='';paintDesk(false);});
   assert.equal(await page.locator('.desk-checks').evaluate(n=>n.open),true,'Successful check disclosure survives refresh');
   await page.locator('.desk-checks summary').click();
   for(const colorScheme of ['light','dark']){await page.emulateMedia({colorScheme,reducedMotion:'reduce'});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  }
  if(!process.env.READING_BASELINE){
   const picker=page.getByLabel('Section of Guide',{exact:true});
   await page.getByRole('button',{name:'Edit Guide',exact:true}).click();
   const editor=page.locator('.desk-column textarea:visible').first();await editor.fill('Retained local guide text.');
   await picker.selectOption('fixture-section-1');await picker.selectOption({index:0});
   assert.equal(await editor.inputValue(),'Retained local guide text.');
  }
  assert.equal((await page.evaluate(()=>ask('fixture-review-state'))).jobs,jobs);assert.deepEqual(errors,[]);
  console.log(process.env.READING_BASELINE?'PASS training reading baseline captured':'PASS training reading: section focus/selection, retained local text, stable check disclosure, phone/desktop light/dark, no jobs');
 }finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,diagnostic);}
})().catch(e=>{console.error(e);process.exitCode=1;});
