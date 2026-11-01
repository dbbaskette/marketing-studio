/* Local saved-image recovery and visual rebuild: no provider execution in this fixture. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
  const renderer=process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER;
  if(!renderer)throw Error('Supply the installed renderer.');
  const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'fixture_server.py'),'--renderer',renderer,'--recover-image'],{stdio:['ignore','pipe','pipe']});
  let browser;
  try{
    const url=await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);child.stdout.on('data',data=>{text+=data;if(text.startsWith('http://')&&text.includes('\n')){clearTimeout(timer);resolve(text.split('\n')[0]);}});child.once('exit',()=>{clearTimeout(timer);reject(Error('Fixture exited before startup'));});});
    browser=await chromium.launch({headless:true,executablePath:renderer});
    const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);await page.getByRole('button',{name:'New infographic',exact:true}).click();
    await page.getByLabel('Working title',{exact:true}).fill('Recover a saved schematic');
    await page.getByLabel('Notes or text',{exact:true}).fill('One instance restarts while the others serve.');
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByLabel('How should we find the story?',{exact:true}).selectOption('direct');
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByLabel('Page size',{exact:true}).selectOption('digital');
    await page.getByRole('button',{name:'Save brief',exact:true}).click();
    await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).click();
    await page.getByRole('button',{name:'Use this story',exact:true}).click();
    await page.locator('#actions').getByRole('button',{name:'Build page',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Build page',exact:true}).click();
    await page.locator('#actions').getByRole('button',{name:'Recover saved artwork',exact:true}).waitFor();
    const calls=await page.evaluate(()=>request('/api/fixture-calls'));
    assert.deepEqual(calls.calls,['story','art','image']);
    // The notice, Image work needs attention, Needs you and the usage row agree: saved
    // artwork was found, so each leads with that and names Recover saved artwork.
    const lead='The image was made but not handed back.';
    assert((await page.locator('#notice').innerText()).startsWith(lead),await page.locator('#notice').innerText());
    await page.getByText(lead+' Recover saved artwork places it on the page on this computer, without a new image request.',{exact:true}).waitFor();
    const needs=await page.locator('.ig-needs').innerText();
    assert(needs.includes('Recover saved artwork: the image was made but not handed back.'),needs);
    await page.getByText('Image requests and usage',{exact:true}).click();
    await page.getByText('Codex image generation: the image was made but not handed back; saved artwork was found on this computer.',{exact:true}).waitFor();
    assert(!(await page.locator('#main').innerText()).includes('codex · generate'),'Provider and state are words');
    await page.reload();await page.locator('#actions').getByRole('button',{name:'Recover saved artwork',exact:true}).click();
    await page.waitForFunction(()=>!document.querySelector('[data-work-status]:not([hidden])'));
    // Recovery says what it did, and the usage row agrees.
    await page.getByText(/^Recovered the saved artwork on this computer and placed it on the page, revision \d+\. No new image request was made\.$/).waitFor();
    await page.getByText('Image requests and usage',{exact:true}).click();
    await page.getByText('Codex image generation: recovered from saved artwork on this computer, without a new request.',{exact:true}).waitFor();
    const recovered=await page.evaluate(()=>request('/api/desk?id='+held.project.id));
    assert(recovered.project.scene.elements.some(e=>e.kind==='artwork'));
    assert.equal(await page.getByRole('heading',{name:'Image work needs attention',exact:true}).count(),0);
    assert.deepEqual((await page.evaluate(()=>request('/api/fixture-calls'))).calls,calls.calls,'Recovery cannot resubmit or call an assistant');
    await page.getByText('Layout alternatives',{exact:true}).click();
    await page.getByRole('button',{name:'Stacked blocks',exact:true}).click();
    await page.locator('#actions').getByRole('button',{name:'Rebuild visual layout',exact:true}).click();
    await page.waitForFunction(()=>!document.querySelector('[data-work-status]:not([hidden])'));
    const rebuilt=await page.evaluate(()=>request('/api/desk?id='+held.project.id));
    assert.equal(rebuilt.project.scene.arrangement,'infographic');
    assert(rebuilt.project.scene.elements.some(e=>e.glyph));
    assert.deepEqual((await page.evaluate(()=>request('/api/fixture-calls'))).calls,calls.calls,'Visual rebuild is local');
    // Sentence-length legacy labels must lead to a useful visual revision, not a failed fit.
    await page.getByRole('button',{name:'Infographics',exact:true}).first().click();
    await page.getByRole('button',{name:'New infographic',exact:true}).click();
    await page.getByLabel('Working title',{exact:true}).fill('Make an older prose plan visual');
    await page.getByLabel('Notes or text',{exact:true}).fill('One service instance restarts while all the other service instances continue serving existing requests.');
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByLabel('How should we find the story?',{exact:true}).selectOption('direct');
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByLabel('Page size',{exact:true}).selectOption('digital');
    await page.getByRole('button',{name:'Save brief',exact:true}).click();
    await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).click();
    await page.getByRole('button',{name:'Use this story',exact:true}).click();
    await page.locator('#actions').getByRole('button',{name:'Make this story visual',exact:true}).click();
    assert.equal(await page.getByRole('dialog').getByLabel('Scope',{exact:true}).isVisible(),false);
    await page.getByRole('dialog').getByRole('button',{name:'Suggest visual plan',exact:true}).click();
    await page.getByRole('button',{name:'Use this story',exact:true}).click();
    await page.locator('#actions').getByRole('button',{name:'Build page',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Build page',exact:true}).click();
    await page.getByRole('heading',{name:'Draft page',exact:true}).waitFor();
    const revised=await page.evaluate(()=>request('/api/desk?id='+held.project.id));
    assert(revised.project.scene.elements.some(e=>e.glyph));
    assert.equal(revised.project.scene.art_regions.length,0);
    const finalCalls=(await page.evaluate(()=>request('/api/fixture-calls'))).calls;
    assert.equal(finalCalls.filter(call=>call==='revision').length,1);
    assert.equal(finalCalls.filter(call=>call==='image').length,1,'The new visual plan builds without an image provider');
    assert.deepEqual(errors,[]);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    console.log('PASS: completed image found after refresh; local recovery composes saved output without repeat generation; old short plan rebuilds locally; long prose plan gets one explicit visual revision and builds native diagrams without image generation; phone controls and no browser errors. Synthetic providers only.');
  }finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>{const timer=setTimeout(()=>{child.kill('SIGKILL');resolve();},5000);child.once('exit',()=>{clearTimeout(timer);resolve();});});}
})().catch(e=>{console.error('FAIL: '+e.message);process.exitCode=1;});
