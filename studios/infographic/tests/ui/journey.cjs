/* Real loopback desk + pinned renderer; injected assistant, no real providers. */
const {chromium} = require('playwright');
const {spawn} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async()=>{
  const renderer=process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER;
  if(!renderer)throw Error('Supply an explicitly installed renderer. No download is performed by this test.');
  const scenario=process.env.INFOGRAPHIC_STUDIO_TEST_SCENARIO;
  const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'fixture_server.py'),'--renderer',renderer,...(process.env.INFOGRAPHIC_STUDIO_TEST_REMOTE?['--remote','--bridge']:[]),...(process.env.INFOGRAPHIC_STUDIO_TEST_VISUAL?['--visual',process.env.INFOGRAPHIC_STUDIO_TEST_VISUAL]:[]),...(scenario?['--scenario',scenario]:[])],{stdio:['ignore','pipe','pipe']});
  let browser, page, errors=[];
  try{
    const url=await new Promise((resolve,reject)=>{let buf='';const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);child.stdout.on('data',b=>{buf+=b;const line=buf.split('\n')[0];if(line.startsWith('http://')&&buf.includes('\n')){clearTimeout(timer);resolve(line);}});child.on('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
    browser=await chromium.launch({headless:true,executablePath:renderer});
    page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);await page.getByRole('button',{name:'New infographic',exact:true}).waitFor();
    await page.getByRole('button',{name:'Settings',exact:true}).click();
    await page.getByRole('heading',{name:'Page renderer',exact:true}).waitFor();
    assert(await page.getByText('Installed renderer found. Preview checks actual fonts, layout, and output.',{exact:true}).isVisible());
    assert.equal(await page.getByLabel('Gemini image model',{exact:true}).count(),0);
    await page.getByRole('button',{name:'Infographics',exact:true}).first().click();
    await page.getByRole('button',{name:'New infographic',exact:true}).click();
    await page.getByLabel('Working title',{exact:true}).fill('Synthetic rolling restart');
    if(process.env.INFOGRAPHIC_STUDIO_TEST_REMOTE){
      await page.getByRole('button',{name:'Add a Google Doc, Slides or public page',exact:true}).click();
      await page.getByLabel('Document or page link',{exact:true}).fill(process.env.INFOGRAPHIC_STUDIO_TEST_SLIDES?'https://docs.google.com/presentation/d/synthetic_slides/edit':'https://docs.google.com/document/d/synthetic_source/edit');
      assert.equal(await page.getByLabel('Google account email',{exact:true}).count(),0);
      await page.getByRole('button',{name:'Read and preview',exact:true}).click();
      await page.getByRole('heading',{name:process.env.INFOGRAPHIC_STUDIO_TEST_SLIDES?'Synthetic Google slides':'Synthetic Google source',exact:true}).waitFor();
    }else await page.getByLabel('Notes or text',{exact:true}).fill((await page.evaluate(()=>request('/api/fixture-source'))).text);
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByLabel('How should we find the story?',{exact:true}).selectOption('direct');
    await page.getByLabel('Audience and prior knowledge',{exact:true}).fill('Technical practitioners');
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByLabel('Page size',{exact:true}).selectOption('digital');
    await page.getByRole('button',{name:'Save brief',exact:true}).click();
    await page.getByRole('heading',{name:'Find a useful story',exact:true}).waitFor();
    await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).click();
    if(scenario==='recovery'){
      const saved=page.getByRole('heading',{name:'Planning response saved',exact:true});
      await saved.waitFor();
      assert.equal((await page.evaluate(()=>request('/api/fixture-calls'))).calls.length,1);
      await page.reload();await saved.waitFor();
      await page.locator('#actions').getByRole('button',{name:'Check saved proposal',exact:true}).click();
      await page.getByText('The saved planning response needs a source or story correction.',{exact:false}).first().waitFor();
      await page.waitForFunction(()=>!document.querySelector('[data-work-status]:not([hidden])'));
      assert.equal((await page.evaluate(()=>request('/api/fixture-calls'))).calls.length,1,'Local recheck must not use assistant allowance');
      await page.getByRole('button',{name:'Review source material',exact:true}).click();
      assert(await page.getByText('Sources and facts',{exact:true}).evaluate(n=>n.parentElement.open));
      assert.equal(await page.getByRole('dialog').count(),0,'Source review should open captured sources, not a new-source form');
      await page.getByRole('button',{name:'Ask for a new plan',exact:true}).click();
      await page.waitForFunction(()=>!document.querySelector('[data-work-status]:not([hidden])'));
      assert.equal((await page.evaluate(()=>request('/api/fixture-calls'))).calls.length,2,'Only the explicit new-plan action may call the assistant');
      assert.deepEqual(errors,[]);
      console.log('PASS: rejected response retained across refresh; local recheck makes no provider request; captured source review; explicit new planning only.');
      return;
    }
    await page.getByRole('button',{name:'Use this story',exact:true}).click();
    await page.locator('#actions').getByRole('button',{name:'Build page',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Build page',exact:true}).click();
    await page.locator('.ig-preview').waitFor();
    await page.waitForFunction(()=>{const i=document.querySelector('.ig-preview');return i&&i.complete&&i.naturalWidth===1080;});
    if(scenario){
      await page.locator('#main').getByRole('button',{name:'Run checks',exact:true}).click();
      const beforeEdit=await page.evaluate(()=>request('/api/desk?id='+held.project.id));
      assert(beforeEdit.project.checks.filter(c=>c.kind!=='visual').every(c=>c.status==='passed'),JSON.stringify(beforeEdit.project.checks));
    }
    if(process.env.INFOGRAPHIC_STUDIO_TEST_VISUAL){
      const current=await page.evaluate(()=>request('/api/desk?id='+held.project.id));
      assert.equal(current.project.stories[0].blocks[0].kind,process.env.INFOGRAPHIC_STUDIO_TEST_VISUAL);
      assert(!current.project.scene.elements.some(e=>e.kind==='chart'),'Descriptive source material must never become scaled chart data');
    }
    // Two edits in sequence: the inspector stays open, keeps its selection and returns focus.
    assert.deepEqual(await page.locator('#ig-element option').evaluateAll(n=>n.map(o=>o.textContent).filter(t=>t.includes('_'))),[],'Labels are human names, not element IDs');
    await page.getByLabel('Element',{exact:true}).selectOption({label:'Section 1 heading'});
    await page.getByLabel('Words for Section 1 heading',{exact:true}).fill('One at a time');
    await page.getByRole('button',{name:'Save words',exact:true}).click();
    await page.getByText(/^Saved Section 1 heading as revision \d+\./).waitFor();
    assert.equal(await page.evaluate(()=>document.activeElement.id),'ig-words');
    assert.equal(await page.getByLabel('Element',{exact:true}).evaluate(n=>n.selectedOptions[0].textContent),'Section 1 heading');
    await page.getByRole('heading',{name:'Earlier preview: update it to see your changes',exact:true}).waitFor();
    await page.getByLabel('Element',{exact:true}).selectOption({label:'Page takeaway'});
    await page.getByLabel('Words for Page takeaway',{exact:true}).fill('Restart one at a time.');
    await page.getByRole('button',{name:'Save words',exact:true}).click();
    await page.getByText(/^Saved Page takeaway as revision \d+\./).waitFor();
    assert.equal(await page.evaluate(()=>document.activeElement.id),'ig-words');
    // Saving unchanged words makes no revision.
    const unchangedAt=await page.evaluate(()=>held.project.revision);
    await page.getByRole('button',{name:'Save words',exact:true}).click();
    await page.getByText(/^Nothing changed, so no revision was made\./).waitFor();
    assert.equal(await page.evaluate(()=>held.project.revision),unchangedAt);
    // Unsaved words survive opening another infographic and coming back.
    const first=await page.evaluate(()=>({id:held.project.id,title:held.project.brief.title,text:held.elements.find(e=>e.label==='Section 1 text').text}));
    await page.getByLabel('Element',{exact:true}).selectOption({label:'Section 1 text'});
    await page.getByLabel('Words for Section 1 text',{exact:true}).fill('Others keep serving.');
    await page.evaluate(async()=>{
      let b=(await request('/api/projects',{title:'Second synthetic page',preset:'digital',direction:'direct'})).project;
      const text=(await request('/api/fixture-source')).text;
      b=(await request('/api/action',{action:'source',id:b.id,expected_revision:b.revision,data:btoa(unescape(encodeURIComponent(text))),kind:'text',name:'Pasted notes'})).result;
      await request('/api/action',{action:'suggest',id:b.id,expected_revision:b.revision});
      b=(await request('/api/project?id='+b.id)).project;
      b=(await request('/api/action',{action:'select',id:b.id,expected_revision:b.revision,story_id:b.stories[0].id})).result;
      await request('/api/brand-current',{id:b.id,expected_revision:b.revision});
      b=(await request('/api/project?id='+b.id)).project;
      await request('/api/action',{action:'build',id:b.id,expected_revision:b.revision,request_id:requestId()});
      await openProject(b.id);
    });
    await page.getByRole('heading',{name:'Second synthetic page',exact:true}).waitFor();
    await page.locator('#ig-words').waitFor();
    assert.equal(await page.locator('#ig-element option').evaluateAll(n=>n.filter(o=>o.textContent.endsWith('(unsaved)')).length),0,'Another infographic has its own words');
    await page.getByRole('button',{name:'Infographics',exact:true}).first().click();
    await page.getByRole('button',{name:'Open '+first.title,exact:true}).click();
    await page.getByLabel('Words for Section 1 text',{exact:true}).waitFor();
    assert.equal(await page.getByLabel('Words for Section 1 text',{exact:true}).inputValue(),'Others keep serving.');
    assert.equal(await page.getByLabel('Element',{exact:true}).evaluate(n=>n.selectedOptions[0].textContent),'Section 1 text (unsaved)');
    await page.getByLabel('Words for Section 1 text',{exact:true}).fill(first.text);
    await page.locator('#actions').getByRole('button',{name:'Create preview',exact:true}).click();
    await page.getByRole('heading',{name:'Draft page',exact:true}).waitFor();
    await page.getByRole('button',{name:'Inspect page with assistant',exact:true}).click();
    await page.getByText('Visual review: passed',{exact:true}).waitFor();
    await page.locator('#main').getByRole('button',{name:'Run checks',exact:true}).click();
    await page.getByRole('button',{name:'Approve this checked revision',exact:true}).click();
    await page.getByRole('button',{name:'Export approved files',exact:true}).click();
    await page.getByRole('heading',{name:'Approved delivery',exact:true}).waitFor();
    await page.getByRole('button',{name:'Actual pixels',exact:true}).click();
    assert(await page.locator('.ig-preview-scroll').evaluate(n=>n.scrollWidth>n.clientWidth));
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.getByRole('button',{name:'Fit page',exact:true}).click();
    const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download SVG',exact:true}).click();
    const file=await download;assert.equal(file.suggestedFilename(),'infographic.svg');
    const source=fs.readFileSync(await file.path(),'utf8');assert(source.includes('One at a time'));assert(!source.includes('DRAFT — not approved'));
    if(process.env.INFOGRAPHIC_STUDIO_TEST_REMOTE){
      await page.getByRole('button',{name:'Deliver Google Doc or PDF',exact:true}).click();
      assert.equal(await page.getByLabel('Google account email',{exact:true}).count(),0);
      assert.equal(await page.getByLabel('Output',{exact:true}).inputValue(),'google');
      await page.getByLabel('Output',{exact:true}).selectOption('both');
      const deliveredPdf=page.waitForEvent('download');
      await page.getByRole('button',{name:'Deliver approved page',exact:true}).click();
      assert.equal((await deliveredPdf).suggestedFilename(),'infographic.pdf');
      await page.getByRole('link',{name:'Open Google Doc',exact:true}).waitFor();
      assert.equal(await page.getByRole('link',{name:'Open Google Doc',exact:true}).getAttribute('href'),'https://docs.google.com/document/d/synthetic_delivered/edit');
      await page.getByRole('button',{name:'Done',exact:true}).click();
    }
    await page.getByRole('button',{name:'Record my visual review',exact:true}).click();
    await page.getByLabel('What did you inspect on the actual composed page?',{exact:true}).fill('I inspected the actual page again and confirmed its relationships.');
    await page.getByRole('button',{name:'Record reviewed page',exact:true}).click();
    await page.getByRole('heading',{name:'Earlier approval: review the current revision',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Export approved files',exact:true}).count(),0);
    assert.equal(await page.locator('#actions').getByRole('button',{name:'Run checks',exact:true}).count(),1);
    await page.locator('#actions').getByRole('button',{name:'Run checks',exact:true}).click();
    await page.getByRole('button',{name:'Approve this checked revision',exact:true}).click();
    await page.getByRole('button',{name:'Export approved files',exact:true}).click();
    await page.getByRole('heading',{name:'Approved delivery',exact:true}).waitFor();
    await page.getByText('History',{exact:true}).click();
    await page.getByText('Edited words',{exact:true}).first().waitFor();
    await page.getByRole('button',{name:/^Compare revision \d+ with current$/}).first().click();
    await page.getByRole('button',{name:'Done',exact:true}).click();
    for(const width of [320,390,1280])for(const colorScheme of ['light','dark']){
      await page.setViewportSize({width,height:900});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow at '+width+' '+colorScheme);
      const targets=await page.locator('button:visible').evaluateAll(nodes=>nodes.filter(n=>{const r=n.getBoundingClientRect();return r.height<43.5;}).map(n=>n.textContent));
      assert.deepEqual(targets,[],'Small controls at '+width);
    }
    const output=process.env.INFOGRAPHIC_UI_RESULTS;if(output){fs.mkdirSync(output,{recursive:true});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(output,'desktop-dark.png'),fullPage:false});await page.setViewportSize({width:390,height:844});await page.emulateMedia({colorScheme:'light'});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(output,'phone-light.png'),fullPage:false});}
    const cdp=await page.context().newCDPSession(page);await cdp.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'},{name:'prefers-reduced-motion',value:'reduce'}]});
    assert.equal(await page.locator('.toolbar').evaluate(n=>getComputedStyle(n).backdropFilter),'none');
    await page.getByRole('button',{name:'Infographics',exact:true}).first().click();
    await page.getByRole('button',{name:'New infographic',exact:true}).click();
    await page.getByLabel('Working title',{exact:true}).fill('Retained intake');
    await page.keyboard.press('Tab');assert(await page.getByRole('dialog').evaluate(n=>n.contains(document.activeElement)));
    await page.keyboard.press('Escape');await page.getByRole('button',{name:'New infographic',exact:true}).click();
    assert.equal(await page.getByLabel('Working title',{exact:true}).inputValue(),'Retained intake');
    await page.keyboard.press('Escape');
    assert.deepEqual(errors,[],'Browser runtime errors');
    console.log('PASS: phone intake → source-backed story → actual render → focused edit → pixel review → checks → approval → SVG download; history comparison; 320/390/1280 light/dark/reduced-motion; no browser errors or horizontal overflow. Providers are injected.');
  }catch(f){console.error(JSON.stringify({browser_errors:errors,text:page?await page.locator('body').innerText():''}));if(page&&process.env.INFOGRAPHIC_UI_RESULTS)await page.screenshot({path:path.join(process.env.INFOGRAPHIC_UI_RESULTS,'failure.png'),fullPage:true});throw f;}finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>{const timer=setTimeout(()=>{child.kill('SIGKILL');resolve();},5000);child.once('exit',()=>{clearTimeout(timer);resolve();});});}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
