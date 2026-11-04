/* Shared settings only, disposable brand fixture, no assistant actions. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict');
(async()=>{const child=spawn(process.env.PYTHON||'python3',['tests/brands_fixture.py'],{stdio:['ignore','pipe','pipe']});let diagnostic='',browser;child.stderr.on('data',b=>diagnostic+=b);
 try{
  const test=await new Promise((resolve,reject)=>{let raw='';child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n'))resolve(JSON.parse(raw.split('\n')[0]));});child.once('exit',c=>reject(Error('Fixture exit '+c+' '+diagnostic)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});const page=await browser.newPage({viewport:{width:390,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(test.url);await page.waitForFunction(()=>snapshot?.shared);
  await page.evaluate(async()=>{snapshot=await api('shared',{changes:{assistant:{agent:'codex',model:'shared-model',effort:'high'},models:{schema:1,agent:'codex',mode:'single',profiles:{quick:{selection:'explicit',model:'quick-fixture-model',effort:'high'},writing:{selection:'explicit',model:'writing-fixture-model',effort:'high'}}}},seen:snapshot.shared});fill();show('settings');});
  await page.getByText('One model also applies its full reasoning to the first scan.',{exact:false}).waitFor();
  await page.getByLabel('Quick scan reasoning',{exact:true}).selectOption('low');await page.getByRole('button',{name:'Use this Quick choice',exact:true}).press('Enter');
  assert.match(await page.locator('#quick-effective').innerText(),/quick-fixture-model, low reasoning/);
  assert.equal(await page.locator('[name="models.writing.model"]').inputValue(),'writing-fixture-model');
  await page.getByRole('button',{name:'Save settings',exact:true}).click();await page.waitForFunction(()=>snapshot.shared.models?.mode==='by_task'&&snapshot.shared.models.profiles.quick.effort==='low');
  await page.reload();await page.waitForFunction(()=>snapshot?.shared);await page.evaluate(()=>show('settings'));
  assert.match(await page.locator('#quick-effective').innerText(),/quick-fixture-model, low reasoning/);
  for(const width of [390,1280])for(const colorScheme of ['light','dark']){await page.setViewportSize({width,height:950});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.deepEqual(errors,[]);console.log('PASS effective Quick preview, explicit low effort, preserved model IDs/other profiles, save/reload and phone/desktop light/dark');
 }finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,diagnostic);}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
