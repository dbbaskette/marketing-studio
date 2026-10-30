/* Visual pilot: real protected pages, isolated settings, synthetic material only. */
const {chromium} = require('playwright');
const {spawn} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');
(async () => {
  const renderer = process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER;
  if (!renderer) throw Error('Supply the installed test renderer.');
  const output = process.env.INFOGRAPHIC_UI_RESULTS;
  if (output) fs.mkdirSync(output, {recursive:true});
  const child = spawn(process.env.PYTHON || 'python3', [path.join(__dirname,'fixture_server.py'), '--renderer',renderer,'--suite'], {stdio:['ignore','pipe','pipe']});
  let browser;
  try {
    const url = await new Promise((resolve,reject) => {
      let text = ''; const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);
      child.stdout.on('data', data => {text+=data; if(text.startsWith('http://')&&text.includes('\n')){clearTimeout(timer);resolve(text.split('\n')[0]);}});
      child.once('exit',()=>{clearTimeout(timer);reject(Error('Fixture exited before startup'));});
    });
    browser = await chromium.launch({headless:true,executablePath:renderer});
    const context = await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'light'});
    const errors=[]; context.on('weberror',error=>errors.push(error.error().message));
    const home=await context.newPage();
    let setupCases=false;
    // Exercise long repository details and all status/action variants without real repositories.
    await home.route('**/api/home', async route=>{
      const response=await route.fetch(), data=await response.json();
      data.shared.local.root='~/Studios';
      for(const studio of data.studios){
        studio.workspace=studio.id==='infographic'
          ? {state:'local',summary:'Local supplied-information workspace',detail:'Drafts stay local. Share selected files through Team library.'}
          : {state:'connected',summary:'Connected to https://example.invalid/marketing/a-long-but-readable-repository-name (main)',detail:null};
        if(setupCases && studio.id==='blog'){
          studio.installed=false;studio.readiness={state:'off',label:'Not installed',detail:'Install explicitly.'};studio.workspace=null;
        }
        if(setupCases && studio.id==='presentation'){
          studio.workspace={state:'disconnected',summary:'Shared settings changed',detail:'Connect this workspace to the configured repository. Your local work is kept.',connect:true};
        }
      }
      await route.fulfill({response,json:data});
    });
    await home.goto(url);
    await home.getByRole('button',{name:'Open Infographic Studio',exact:true}).waitFor();
    assert.equal(await home.locator('body').getAttribute('data-pilot'),'liquid');
    const cards=await home.locator('.studio-card').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y};}));
    assert.equal(cards.length,4); assert.equal(cards[0].y,cards[1].y); assert.equal(cards[2].y,cards[3].y); assert(cards[2].y>cards[0].y);
    assert.equal(await home.locator('.studio-repository').count(),4);
    await home.locator('.studio-repository').first().getByText('Details',{exact:true}).click();
    assert(await home.locator('.studio-repository').first().evaluate(n=>n.open));
    await home.locator('.studio-repository').first().getByText('Details',{exact:true}).click();
    async function capture(page,name){await page.evaluate(()=>scrollTo(0,0));if(output)await page.screenshot({path:path.join(output,name+'.png'),fullPage:false});}
    async function fit(page){assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Page overflow');}
    await capture(home,'marketing-desktop-light');
    await home.emulateMedia({colorScheme:'dark'});await capture(home,'marketing-desktop-dark');
    await home.emulateMedia({colorScheme:'light'});
    setupCases=true;await home.reload();
    await home.getByRole('link',{name:'Install Blog Studio',exact:true}).waitFor();
    for(const width of [390,900,1440]){
      await home.setViewportSize({width,height:900});await fit(home);
      assert.deepEqual(await home.locator('.studio-card').evaluateAll(cards=>cards.flatMap(card=>{
        const title=card.querySelector('.studio-name').getBoundingClientRect();
        return [...card.querySelectorAll(':scope > .button')].filter(button=>{
          const r=button.getBoundingClientRect();
          return r.x<title.right && r.right>title.x && r.y<title.bottom && r.bottom>title.y;
        }).map(button=>button.textContent);
      })),[],'Launcher actions must not overlap studio names');
      assert(await home.getByText('Connect this workspace to the configured repository. Your local work is kept.',{exact:true}).isVisible());
    }
    setupCases=false;await home.reload();await home.setViewportSize({width:1440,height:1000});
    await home.getByRole('button',{name:'Open Infographic Studio',exact:true}).waitFor();
    await home.getByRole('button',{name:'Shared settings',exact:true}).click();
    await capture(home,'marketing-settings');await fit(home);
    await home.getByRole('button',{name:'Studios',exact:true}).click();
    const popup=home.waitForEvent('popup');await home.getByRole('button',{name:'Open Infographic Studio',exact:true}).click();
    const studio=await popup;await studio.getByRole('button',{name:'New infographic',exact:true}).waitFor();
    assert.equal(await studio.locator('body').getAttribute('data-pilot'),'liquid');
    await studio.getByRole('button',{name:'New infographic',exact:true}).click();
    await studio.getByLabel('Working title',{exact:true}).fill('A clear explanation of rolling restarts');
    await studio.getByLabel('Notes or text',{exact:true}).fill('One instance restarts while the others serve.');
    await capture(studio,'infographic-intake');
    assert.equal(await studio.getByRole('dialog').evaluate(n=>getComputedStyle(n).backgroundColor),'rgb(255, 255, 255)');
    await studio.getByRole('button',{name:'Continue',exact:true}).click();
    await studio.getByLabel('How should we find the story?',{exact:true}).selectOption('direct');
    await studio.getByRole('button',{name:'Continue',exact:true}).click();
    await studio.getByLabel('Page size',{exact:true}).selectOption('digital');
    await studio.getByRole('button',{name:'Save brief',exact:true}).click();
    await studio.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).click();
    await studio.getByRole('button',{name:'Use this story',exact:true}).waitFor();
    await capture(studio,'infographic-story');
    await studio.getByRole('button',{name:'Use this story',exact:true}).click();
    await studio.locator('#actions').getByRole('button',{name:'Build page',exact:true}).click();
    await studio.getByRole('dialog').getByRole('button',{name:'Build page',exact:true}).click();
    await studio.waitForFunction(()=>{const image=document.querySelector('.ig-preview');return image?.complete&&image.naturalWidth===1080;});
    await capture(studio,'infographic-desktop-light');
    await studio.getByRole('button',{name:'Actual pixels',exact:true}).click();
    assert.equal(await studio.getByRole('button',{name:'Actual pixels',exact:true}).getAttribute('aria-pressed'),'true');
    await fit(studio);
    await studio.getByRole('button',{name:'Fit page',exact:true}).click();
    assert.equal(await studio.getByRole('button',{name:'Fit page',exact:true}).getAttribute('aria-pressed'),'true');
    await studio.emulateMedia({colorScheme:'dark'});await capture(studio,'infographic-desktop-dark');
    for(const page of [home,studio]){
      for(const width of [320,390,768,1440])for(const colorScheme of ['light','dark']){
        await page.setViewportSize({width,height:900});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});await fit(page);
        assert.deepEqual(await page.locator('button:visible, .nav-item:visible, summary:visible').evaluateAll(nodes=>nodes.filter(n=>n.getBoundingClientRect().height<43.5).map(n=>n.textContent)),[],'Small hit targets at '+width);
        const contrast=await page.evaluate(()=>{
          const luminance=color=>{const channels=color.match(/[\d.]+/g).slice(0,3).map(n=>{const c=Number(n)/255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4;});return channels[0]*.2126+channels[1]*.7152+channels[2]*.0722;};
          const resolve=name=>{const probe=document.createElement('span');probe.style.color='var('+name+')';document.body.append(probe);const color=getComputedStyle(probe).color;probe.remove();return luminance(color);};
          return ['--ink','--quiet'].flatMap(foreground=>['--card','--ground'].map(background=>{const a=resolve(foreground),b=resolve(background);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);}));
        });
        assert(contrast.every(ratio=>ratio>=4.5),'Pilot reading contrast must meet 4.5:1 in '+colorScheme);
      }
      await page.setViewportSize({width:390,height:844});await page.emulateMedia({colorScheme:'light'});await capture(page,page===home?'marketing-phone-light':'infographic-phone-light');
      await page.emulateMedia({colorScheme:'dark'});await capture(page,page===home?'marketing-phone-dark':'infographic-phone-dark');
      const cdp=await page.context().newCDPSession(page);
      await cdp.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'},{name:'prefers-contrast',value:'more'}]});
      assert.equal(await page.locator('.toolbar').evaluate(n=>getComputedStyle(n).backdropFilter),'none');
      // 200% browser zoom equivalent: halve CSS viewport, keeping every control reachable.
      await page.setViewportSize({width:720,height:450});await fit(page);
      await cdp.send('Emulation.setEmulatedMedia',{features:[]});
    }
    // Exercise the actual shared setup entry script for the other three product names.
    const other=await context.newPage();
    await other.setViewportSize({width:1440,height:900});
    let product='Blog Studio';
    await other.route(new URL(url).origin+'/',async route=>{
      const response=await route.fetch();
      await route.fulfill({response,body:(await response.text()).replace('data-product="Marketing Studio"','data-product="'+product+'"')});
    });
    for(product of ['Blog Studio','Presentation Studio','Training Studio']){
      await other.goto(url);await other.locator('.studio-card').first().waitFor();
      assert.equal(await other.locator('body').getAttribute('data-pilot'),null);
      assert.equal(await other.locator('.nav-item').first().evaluate(n=>getComputedStyle(n).borderRadius),'10px');
    }
    await studio.getByRole('button',{name:'Infographics',exact:true}).first().click();
    await studio.getByRole('button',{name:'New infographic',exact:true}).click();
    await studio.getByLabel('Working title',{exact:true}).focus();await studio.keyboard.press('Tab');
    assert(await studio.getByRole('dialog').evaluate(n=>n.contains(document.activeElement)));
    assert(await studio.evaluate(()=>getComputedStyle(document.activeElement).outlineStyle!=='none'),'Keyboard focus must stay visible');
    assert.deepEqual(errors,[]);
    console.log('PASS: scoped two-product pilot; balanced launcher; repository disclosure; opaque intake; story and real page preview; selected zoom controls; 320/390/768/1440 light/dark; reduced effects; keyboard dialog; 200% viewport; no overflow or runtime errors. Synthetic data, no providers.');
  } finally {
    if(browser)await browser.close(); child.kill('SIGTERM');
    await new Promise(resolve=>{const timer=setTimeout(()=>{child.kill('SIGKILL');resolve();},5000);child.once('exit',()=>{clearTimeout(timer);resolve();});});
  }
})().catch(error=>{console.error('FAIL: '+error.message);process.exitCode=1;});
