/* Selected editor loading against the real native desk; disposable scripted authors. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const child=spawn(process.env.PYTHON||'python3',['tests/slide_review_fixture.py','training','--rendered'],{stdio:['ignore','pipe','pipe']});
 let diagnostic='',browser;child.stderr.on('data',b=>diagnostic+=b);
 try{
  const fixture=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostic)),40000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostic));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  let requests=[],holdBrief,failBrief=true;
  await page.route('**/api/drafts/card?*',async route=>{
   const name=new URL(route.request().url()).searchParams.get('name');requests.push(name);
   if(name.startsWith('brief')){
    if(failBrief){await route.fulfill({status:503,json:{error:'Synthetic temporary read failure.'}});return;}
    if(holdBrief)await holdBrief;
   }
   await route.continue();
  });
  await page.goto(fixture.url+'&resume='+encodeURIComponent(path.basename(fixture.path)));
  await page.waitForFunction(()=>view.run&&!view.refreshing&&Object.keys(deskHeld(view.path).materials).length);
  const initial=await page.evaluate(()=>({cards:deskHeld(view.path).view.cards,loaded:Object.keys(deskHeld(view.path).materials)}));
  assert.equal(initial.loaded.length,1,'Initial navigation loads only the selected editor');
  const jobs=(await page.evaluate(()=>ask('fixture-review-state'))).jobs;
  requests=[];await page.evaluate(()=>refresh());assert.equal(requests.length,1,'Refresh reads only one editor');
  const tabs=page.getByRole('tablist',{name:'Training material',exact:true});
  await tabs.getByRole('tab',{name:/^Brief ·/}).click();
  await page.getByRole('button',{name:'Try opening again',exact:true}).waitFor();
  const brief=initial.cards.find(c=>c.kind==='brief');
  assert.equal(await page.evaluate(name=>deskHeld(view.path).opened?.[name],brief.name),undefined,'Failed loads are not counted as read');
  failBrief=false;let release;holdBrief=new Promise(resolve=>release=resolve);
  await page.getByRole('button',{name:'Try opening again',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Opening brief'}).waitFor();
  await tabs.getByRole('tab',{name:/^Guide ·/}).click();
  await page.getByRole('button',{name:'Edit Guide',exact:true}).waitFor();
  await page.getByRole('button',{name:'Edit Guide',exact:true}).click();
  const editor=page.locator('.desk-column textarea:visible').first();await editor.fill('Unsaved text survives a different material arriving.');
  release();holdBrief=null;
  await page.waitForFunction(name=>!!deskHeld(view.path).materials[name],brief.name);
  assert.match(await tabs.locator('[aria-selected="true"]').innerText(),/^Guide/);
  assert.equal(await editor.inputValue(),'Unsaved text survives a different material arriving.');
  assert.equal(await page.evaluate(name=>deskHeld(view.path).opened?.[name],brief.name),undefined,'A background completion is not a read');
  requests=[];await tabs.getByRole('tab',{name:/^Brief ·/}).click();
  await page.getByRole('button',{name:'Edit Brief',exact:true}).waitFor();
  assert.equal(requests.length,0,'Opening the loaded revision reuses its editor');
  assert.equal(await page.evaluate(name=>deskHeld(view.path).opened[name],brief.name),brief.seen);
  assert.equal((await page.evaluate(()=>ask('fixture-review-state'))).jobs,jobs);
  assert.deepEqual(errors,[]);
  console.log('PASS selected editor: one initial/refresh read, lazy selection, retry, late response, retained edits, cached return, accurate opened revisions, no jobs');
 }finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,diagnostic);}
})().catch(e=>{console.error(e);process.exitCode=1;});
