/* Current Infographic Studio details flow, with a scripted local assistant. */
const {spawn}=require('node:child_process'),{chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const renderer=process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER;
 const child=spawn(process.env.PYTHON||'python3',['studios/infographic/tests/ui/fixture_server.py','--renderer',renderer],{stdio:['ignore','pipe','pipe']});
 let browser,diagnostic='';child.stderr.on('data',b=>diagnostic+=b);
 try{
  const url=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostic)),30000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(raw.split('\n')[0]);}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostic));});});
  browser=await chromium.launch({headless:true,executablePath:renderer});
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);
  await page.getByRole('button',{name:'New infographic',exact:true}).click();
  const intake=page.getByRole('dialog',{name:'New infographic',exact:true});await intake.waitFor();
  await intake.getByLabel('Working title',{exact:true}).fill('Synthetic controls review');
  await intake.getByLabel('Notes or text',{exact:true}).fill((await page.evaluate(()=>request('/api/fixture-source'))).text);
  await intake.getByRole('button',{name:'Continue',exact:true}).click();
  await intake.getByLabel('How should we find the story?',{exact:true}).selectOption('direct');
  await intake.getByLabel('Page size',{exact:true}).selectOption('digital');
  await intake.getByRole('button',{name:'Save brief',exact:true}).click();
  await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).click();
  await page.getByRole('button',{name:'Use this story',exact:true}).click();
  await page.locator('#actions').getByRole('button',{name:'Build page',exact:true}).click();
  await page.getByRole('dialog').getByRole('button',{name:'Build page',exact:true}).click();
  await page.locator('.ig-preview').waitFor();
  const before=(await page.evaluate(()=>request('/api/fixture-calls'))).calls.length;
  for(const width of [390,1280])for(const colorScheme of ['light','dark']){
   await page.setViewportSize({width,height:900});await page.emulateMedia({colorScheme,reducedMotion:'no-preference'});
   for(const title of ['Brief and requirements','Sources and facts','Layout alternatives']){
    const summary=page.locator('.cult-expandable > summary').filter({hasText:new RegExp('^'+title+'$')});
    await summary.press('Enter');
    assert(await summary.evaluate(n=>n.parentElement.open),'Keyboard opens '+title);
    assert((await summary.boundingBox()).height>=44);
    await summary.press('Enter');
    assert.equal(await summary.evaluate(n=>n.parentElement.open),false,'Keyboard closes '+title);
   }
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
   const brief=page.locator('.cult-expandable > summary').filter({hasText:'Brief and requirements'});
   await brief.click();await brief.click(); // Repeated toggles remain responsive during the height transition.
   await page.emulateMedia({reducedMotion:'reduce'});
   assert.equal(await brief.evaluate(n=>getComputedStyle(n,'::before').transitionDuration),'0s');
   await brief.click();
   const edit=page.getByRole('button',{name:'Edit brief',exact:true});await edit.click();
   const sheet=page.getByRole('dialog',{name:'Edit brief and requirements',exact:true});await sheet.waitFor();
   assert.equal(await sheet.getByLabel('Working title',{exact:true}).inputValue(),'Synthetic controls review','Wrapped actions retain their handlers/data');
   await sheet.getByRole('button',{name:'Cancel',exact:true}).click();
   assert.equal(await edit.evaluate(n=>n===document.activeElement),true,'Closing returns focus to the wrapped action');
   await brief.click();
   if(process.env.INFOGRAPHIC_UI_RESULTS){fs.mkdirSync(process.env.INFOGRAPHIC_UI_RESULTS,{recursive:true});await brief.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.INFOGRAPHIC_UI_RESULTS,`cult-${width}-${colorScheme}.png`)});}
  }
  assert.equal((await page.evaluate(()=>request('/api/fixture-calls'))).calls.length,before,'Opening controls schedules no assistant work');
  assert.deepEqual(errors,[]);
  console.log('PASS Infographic Studio: create/source/story/render, three source-adapted panels, keyboard and rapid toggles, edit action/focus return, reduced motion, 390/1280 light/dark, no jobs from navigation');
 }finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)return resolve();const timer=setTimeout(()=>{child.kill('SIGKILL');resolve();},5000);child.once('exit',()=>{clearTimeout(timer);resolve();});});}
})().catch(e=>{console.error(e);process.exitCode=1;});
