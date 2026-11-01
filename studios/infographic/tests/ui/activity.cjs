/* Real phone bridge, blocked synthetic assistant, no provider or personal data. */
const {chromium} = require('playwright');
const {spawn} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async()=>{
  const renderer=process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER;
  if(!renderer)throw Error('Supply the installed test renderer. Nothing is downloaded.');
  const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'fixture_server.py'),'--renderer',renderer,'--slow','--bridge','--remote'],{stdio:['ignore','pipe','pipe']});
  let browser,page;const errors=[];
  try{
    const url=await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);child.stdout.on('data',chunk=>{text+=chunk;const line=text.split('\n')[0];if(line.startsWith('http://')&&text.includes('\n')){clearTimeout(timer);resolve(line);}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code));});});
    browser=await chromium.launch({headless:true,executablePath:renderer});
    page=await browser.newPage({viewport:{width:390,height:844}});
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);
    async function makeProject(title){
      await page.getByRole('button',{name:'New infographic',exact:true}).click();
      await page.getByLabel('Working title',{exact:true}).fill(title);
      await page.getByLabel('Notes or text',{exact:true}).fill('One instance restarts while the other instances serve.');
      await page.getByRole('button',{name:'Continue',exact:true}).click();
      await page.getByLabel('How should we find the story?',{exact:true}).selectOption('direct');
      await page.getByRole('button',{name:'Save brief',exact:true}).click();
      await page.getByRole('heading',{name:'Find a useful story',exact:true}).waitFor();
    }
    const status=()=>page.locator('[data-work-status]:visible');
    async function running(){
      await status().getByText('Reading sources and finding the story',{exact:true}).waitFor();
      assert(await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).isDisabled());
      assert.match(await status().innerText(),/\d+:\d\d elapsed/);
      assert(!(await status().innerText()).includes('%'));
    }
    async function release(fail=false){await page.evaluate(fail=>request('/api/fixture-release',{fail}),fail);}
    async function calls(){return page.evaluate(()=>request('/api/fixture-calls'));}

    await makeProject('Synthetic progress after refresh');
    await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).click();
    await running();
    const output=process.env.INFOGRAPHIC_UI_RESULTS;
    if(output){fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'activity-phone-light.png')});}
    for(const width of [320,390,1280]){
      await page.setViewportSize({width,height:844});await page.emulateMedia({colorScheme:'dark',reducedMotion:'reduce'});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      assert.equal(await status().locator('.bead').evaluate(n=>getComputedStyle(n,'::before').animationName),'none');
    }
    if(output)await page.screenshot({path:path.join(output,'activity-desktop-dark.png')});
    await page.setViewportSize({width:390,height:844});
    await page.reload();await running();
    assert.equal((await calls()).calls.length,1,'Refresh must not repeat assistant work');
    await release();
    await page.getByRole('button',{name:'Use this story',exact:true}).waitFor();
    await page.waitForFunction(()=>!document.querySelector('[data-work-status]:not([hidden])'));
    assert(await page.getByText('Finished. Your saved work is ready to review.',{exact:true}).isVisible());

    await page.getByRole('button',{name:'Infographics',exact:true}).first().click();
    await makeProject('Synthetic failed planning');
    await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).click();
    await running();await release(true);
    await page.getByText('Synthetic planning failure. Your saved work is kept.',{exact:true}).waitFor();
    assert.equal(await status().count(),0);
    assert(!(await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).isDisabled()));
    assert.equal((await calls()).calls.length,2,'Failure must not retry automatically');

    await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).click();
    await running();await release('timeout');
    await page.locator('#notice').filter({hasText:'five-minute limit and has stopped'}).waitFor();
    assert(!(await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).isDisabled()));
    assert.equal((await calls()).calls.length,3,'A timed-out request must not retry automatically');
    // The notice sits in the page's flow, covers no control, and Dismiss clears it.
    const notice=page.locator('#notice');
    assert.equal(await notice.evaluate(n=>getComputedStyle(n).position),'static');
    const covered=await page.evaluate(()=>{const box=document.getElementById('notice').getBoundingClientRect();return [...document.querySelectorAll('button')].filter(b=>{if(document.getElementById('notice').contains(b))return false;const r=b.getBoundingClientRect();return r.width&&r.left<box.right&&r.right>box.left&&r.top<box.bottom&&r.bottom>box.top;}).map(b=>b.textContent);});
    assert.deepEqual(covered,[],'The notice covers no control');
    await notice.getByRole('button',{name:'Dismiss',exact:true}).click();
    assert.equal(await notice.isVisible(),false);
    // A reload returns to the same infographic, where the failed request keeps its reason.
    await page.reload();
    await page.getByRole('heading',{name:'Synthetic failed planning',exact:true}).waitFor();
    await page.locator('#notice').filter({hasText:'five-minute limit and has stopped'}).waitFor();
    assert.equal((await calls()).calls.length,3,'Opening a failed request must preserve its reason without running it');

    // While the assistant works, the rest of the studio stays usable: Infographics opens Home,
    // where the card says it is working; Stop waiting leaves the work running; coming back
    // shows its progress, then its result. Nothing is requested again.
    await page.getByRole('button',{name:'Infographics',exact:true}).first().click();
    await makeProject('Synthetic leave and return');
    await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).click();
    await running();
    assert.equal(await page.locator('#actions').getByRole('button',{name:'Infographics',exact:true}).isDisabled(),false);
    assert.equal(await page.locator('#settings').isDisabled(),false);
    const before=(await calls()).calls.length;
    await page.locator('#actions').getByRole('button',{name:'Infographics',exact:true}).click();
    await page.getByRole('heading',{name:'Your infographics',exact:true}).waitFor();
    const workingCard=page.locator('.ig-project-card').filter({hasText:'Synthetic leave and return'});
    await workingCard.getByText('Working now: Reading sources and finding the story',{exact:true}).waitFor();
    await page.locator('#settings').click();
    await page.getByRole('heading',{name:'Page renderer',exact:true}).waitFor();
    await page.locator('#home').click();
    await workingCard.getByRole('button',{name:'Open Synthetic leave and return',exact:true}).click();
    await running();
    // Stop waiting from the progress itself: Home again, with the work still running.
    await status().getByRole('button',{name:'Stop waiting',exact:true}).click();
    await page.getByRole('heading',{name:'Your infographics',exact:true}).waitFor();
    await workingCard.getByText(/^Working now:/).waitFor();
    assert.equal((await calls()).calls.length,before,'Leaving never repeats the request');
    await release();
    // Finished while away: said where the person is, without pulling them back.
    await page.getByText('“Synthetic leave and return” is ready. Open it to see the result.',{exact:true}).waitFor();
    assert.equal(await page.getByRole('heading',{name:'Your infographics',exact:true}).count(),1);
    await workingCard.getByText('Stories proposed: choose one',{exact:true}).waitFor();
    await workingCard.getByRole('button',{name:'Open Synthetic leave and return',exact:true}).click();
    await page.getByRole('button',{name:'Use this story',exact:true}).waitFor();
    assert.equal((await calls()).calls.length,before,'No assistant request is repeated');
    // Toasts leave by themselves after the shared delay.
    await page.waitForFunction(()=>!document.querySelector('#toasts .toast'),null,{timeout:8000});

    // Forward once, then lose only the browser's POST connection while the
    // synthetic assistant is blocked. Recovery must use GET status requests.
    await page.getByRole('button',{name:'Infographics',exact:true}).first().click();
    await makeProject('Synthetic lost connection');
    let forwarded;
    await page.route('**/api/action',async route=>{
      const sent=route.request().postDataJSON();
      if(sent.action!=='suggest')return route.continue();
      forwarded=page.request.post(route.request().url(),{data:sent,headers:route.request().headers()});
      forwarded.catch(()=>{});   // awaited below; a failure elsewhere must not hide its own error
      for(let n=0;n<100;n++){
        const value=await page.evaluate(id=>request('/api/activity?id='+encodeURIComponent(id)),sent.id);
        if(value.activity?.state==='running')break;
        await new Promise(resolve=>setTimeout(resolve,20));
      }
      await route.abort('failed');
    });
    await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).click();
    await running();assert.equal((await calls()).calls.length,5);
    await release();await forwarded;
    await page.getByRole('button',{name:'Use this story',exact:true}).waitFor();
    assert.equal((await calls()).calls.length,5,'Connection recovery must not repeat the POST');
    await page.unroute('**/api/action');

    // A pending remote read must remain visible inside the open modal.
    await page.getByRole('button',{name:'Infographics',exact:true}).first().click();
    await page.getByRole('button',{name:'New infographic',exact:true}).click();
    await page.getByRole('button',{name:'Add a Google Doc, Slides or public page',exact:true}).click();
    await page.getByLabel('Document or page link',{exact:true}).fill('https://docs.google.com/document/d/synthetic_source/edit');
    let unblock;const gate=new Promise(resolve=>unblock=resolve);
    await page.route('**/api/remote-preview',async route=>{const response=await route.fetch();await gate;await route.fulfill({response});});
    await page.getByRole('button',{name:'Read and preview',exact:true}).click();
    await page.getByRole('dialog').getByText('Reading the linked document',{exact:true}).waitFor();
    assert.equal(await status().count(),1);
    if(output)await page.screenshot({path:path.join(output,'activity-import-phone-dark.png')});
    unblock();await page.getByRole('heading',{name:'Synthetic Google source',exact:true}).waitFor();
    assert.equal(await status().count(),0);
    assert.deepEqual(errors,[]);
    console.log('PASS: persistent phone status, real stages and elapsed time, refresh recovery, one-request disconnect recovery, safe timeout diagnostics after reopening and explicit retry, failure cleanup, modal source progress, 320/390/1280 dark/light and reduced motion; navigation, Home and Stop waiting while work runs, the result when back, a dismissable in-flow notice, reload to the same infographic; no providers.');
  }finally{
    if(browser)await browser.close();child.kill('SIGTERM');
    await new Promise(resolve=>{const timer=setTimeout(()=>{child.kill('SIGKILL');resolve();},5000);child.once('exit',()=>{clearTimeout(timer);resolve();});});
  }
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
