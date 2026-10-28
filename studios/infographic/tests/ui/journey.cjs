/* Real loopback desk + pinned renderer; injected assistant, no real providers. */
const {chromium} = require('playwright');
const {spawn} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async()=>{
  const renderer=process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER;
  if(!renderer)throw Error('Supply an explicitly installed renderer. No download is performed by this test.');
  const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'fixture_server.py'),'--renderer',renderer],{stdio:['ignore','pipe','pipe']});
  let browser, page, errors=[];
  try{
    const url=await new Promise((resolve,reject)=>{let buf='';const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);child.stdout.on('data',b=>{buf+=b;const line=buf.split('\n')[0];if(line.startsWith('http://')&&buf.includes('\n')){clearTimeout(timer);resolve(line);}});child.on('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
    browser=await chromium.launch({headless:true,executablePath:renderer});
    page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);await page.getByRole('button',{name:'New infographic',exact:true}).waitFor();
    await page.getByRole('button',{name:'New infographic',exact:true}).click();
    await page.getByLabel('Working title',{exact:true}).fill('Synthetic rolling restart');
    await page.getByLabel('Notes or text',{exact:true}).fill('One instance restarts while the others serve.');
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByLabel('How should we find the story?',{exact:true}).selectOption('direct');
    await page.getByLabel('Audience and prior knowledge',{exact:true}).fill('Technical practitioners');
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByLabel('Page size',{exact:true}).selectOption('digital');
    await page.getByRole('button',{name:'Save brief',exact:true}).click();
    await page.getByRole('heading',{name:'Find a useful story',exact:true}).waitFor();
    await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).click();
    await page.getByRole('button',{name:'Use this story',exact:true}).click();
    await page.locator('#actions').getByRole('button',{name:'Build page',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'Build page',exact:true}).click();
    await page.locator('.ig-preview').waitFor();
    await page.waitForFunction(()=>{const i=document.querySelector('.ig-preview');return i&&i.complete&&i.naturalWidth===1080;});
    await page.getByText('Edit words directly',{exact:true}).click();
    await page.getByLabel('b1_heading',{exact:true}).fill('One at a time');
    await page.getByRole('button',{name:'Save b1_heading',exact:true}).click();
    await page.getByRole('heading',{name:'Earlier page — create a new preview',exact:true}).waitFor();
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
    await page.getByText('History',{exact:true}).click();
    await page.getByRole('button',{name:'Compare with current',exact:true}).first().click();
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
