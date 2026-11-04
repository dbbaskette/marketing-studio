/* Real native pages, isolated workspaces and synthetic accounting; no providers. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const path=require('node:path'),assert=require('node:assert/strict'),fs=require('node:fs');
async function fixture(product){
 const file=product==='training'?'outline_fixture.py':'story_fixture.py';
 const child=spawn(process.env.PYTHON||'python3',[`studios/${product}/tests/ui/${file}`,'--spending-test'],{stdio:['ignore','pipe','pipe']});
 let diagnostic='';child.stderr.on('data',b=>diagnostic+=b);
 const result=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error(diagnostic||'Fixture timeout')),30000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',c=>{clearTimeout(timer);reject(Error('Fixture exit '+c+' '+diagnostic));});});
 return {...result,stop:async()=>{child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,diagnostic);}};
}
(async()=>{let browser;try{
 browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
 for(const product of ['training','presentation']){
  const test=await fixture(product);let page;
  try{
   page=await browser.newPage({viewport:{width:390,height:844}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(test.url+'&resume='+encodeURIComponent(path.basename(test.path)));
   const heading=product==='training'?'Review the training outline':'Review the slide story';await page.getByRole('heading',{name:heading,exact:true}).waitFor();
   const field=page.getByLabel('Section 1 title',{exact:true});await field.fill('Budget keeps typing');await field.press('ArrowLeft');
   await field.evaluate(n=>{window.beforeBudgetField=n;window.beforeBudgetCaret=n.selectionStart;});
   const before=await page.evaluate(root=>ask('run',{path:root}),test.path);
   await page.evaluate(root=>send('fixture-spend',{path:root}),test.path);await page.evaluate(()=>refresh());
   await page.locator('.spending-status .spending-warning').filter({hasText:/Reported spending/}).first().waitFor();
   assert.equal(await field.inputValue(),'Budget keeps typing');
   assert(await field.evaluate(n=>n===window.beforeBudgetField&&n.selectionStart===window.beforeBudgetCaret&&document.activeElement===n),'Warning must preserve typing and focus');
   for(const width of [390,1280])for(const colorScheme of ['light','dark']){
    await page.setViewportSize({width,height:900});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    if(process.env.SPENDING_UI_RESULTS){fs.mkdirSync(process.env.SPENDING_UI_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SPENDING_UI_RESULTS,`${product}-${width}-${colorScheme}.png`)});}
   }
   const control=page.locator('.spending-status details');
   await control.locator('summary').click();await control.getByLabel('At the project spending amount').waitFor();
   await control.getByLabel('At the project spending amount').selectOption('hard-stop');
   await control.getByRole('button',{name:'Save spending behavior',exact:true}).press('Enter');
   await page.locator('.spending-status .spending-warning').filter({hasText:/Reported spending/}).first().waitFor({state:'detached'});
   const after=await page.evaluate(root=>ask('run',{path:root}),test.path);
   assert.equal(after.spending.policy,'hard-stop');
   const attempts=r=>(r.steps||r.timeline||[]).find(s=>(s.id||s.name)==='scan')?.attempts;
   assert.equal(attempts(after),attempts(before),'Policy save must not repeat scan');
   assert.deepEqual(errors,[]);console.log('PASS '+product+' spending: durable warning, unchanged focus, explicit policy save, no repeated scan, 390/1280 light/dark');
  }finally{if(page)await page.close();await test.stop();}
 }
 const home=spawn(process.env.PYTHON||'python3',['studios/infographic/tests/ui/fixture_server.py','--renderer',process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER,'--suite'],{stdio:['ignore','pipe','pipe']});
 let diagnostic='';home.stderr.on('data',b=>diagnostic+=b);let sharedPage;
 try{
  const url=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error(diagnostic||'Home timeout')),30000);home.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(raw.split('\n')[0]);}});home.once('exit',c=>{clearTimeout(timer);reject(Error('Home exit '+c+' '+diagnostic));});});
  sharedPage=await browser.newPage({viewport:{width:390,height:844}});await sharedPage.goto(url);
  await sharedPage.getByRole('button',{name:'Shared settings',exact:true}).click();
  await sharedPage.getByRole('button',{name:'Spending',exact:true}).click();
  const section=sharedPage.locator('#spending-part');await section.getByLabel('Training Studio',{exact:true}).waitFor();
  await sharedPage.evaluate(()=>api('shared',{changes:{spending:{presentation:'hard-stop'}},seen:snapshot.shared}));
  await section.getByLabel('Training Studio',{exact:true}).selectOption('hard-stop');
  await sharedPage.getByRole('button',{name:'Save settings',exact:true}).click();
  await sharedPage.waitForFunction(()=>snapshot.shared.spending?.training==='hard-stop');
  const saved=await sharedPage.evaluate(()=>snapshot.shared.spending);
  assert.deepEqual(saved,{training:'hard-stop',presentation:'hard-stop'},'Saving one studio preserves a concurrent other-studio choice');
  for(const width of [390,1280])for(const colorScheme of ['light','dark']){
   await sharedPage.setViewportSize({width,height:900});await sharedPage.emulateMedia({colorScheme,reducedMotion:'reduce'});await section.scrollIntoViewIfNeeded();
   assert(await sharedPage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert(await section.getByLabel('Training Studio',{exact:true}).evaluate(n=>n.getBoundingClientRect().height>=43.5));
   if(process.env.SPENDING_UI_RESULTS)await sharedPage.screenshot({path:path.join(process.env.SPENDING_UI_RESULTS,`shared-spending-${width}-${colorScheme}.png`)});
  }
  console.log('PASS shared spending settings: real locked save, concurrent other-studio choice retained, 390/1280 light/dark');
 }finally{if(sharedPage)await sharedPage.close();home.kill('SIGTERM');await new Promise(resolve=>home.exitCode!==null?resolve():home.once('exit',resolve));assert.equal(home.exitCode,0,diagnostic);}
}finally{if(browser)await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
