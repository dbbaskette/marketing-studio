/* The Document Library in a real browser: Marketing Studio's Library screen, Add existing
 * work to library and the shared Add from library sheet, at desktop and phone widths, light
 * and dark, with reduced motion, reduced transparency and more contrast.
 *
 *   PYTHON=python3 INFOGRAPHIC_STUDIO_TEST_RENDERER=<headless browser> node tests/library_visual.cjs
 *
 * tests/library_visual_server.py serves the real home over synthetic settings, a synthetic
 * library and one synthetic Blog Studio workspace in a temporary folder. codex, claude and
 * gemini on PATH are stand-ins that refuse, and BROWSER is false: no studio, assistant or
 * provider starts. LIBRARY_VISUAL_RESULTS, when set, keeps a screenshot of each state. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),os=require('node:os'),assert=require('node:assert/strict');
(async()=>{
 const standins=fs.mkdtempSync(path.join(os.tmpdir(),'library-visual-'));
 for(const name of ['codex','claude','gemini']){const file=path.join(standins,name);fs.writeFileSync(file,'#!/bin/sh\necho "This test refuses to start '+name+'." >&2\nexit 97\n');fs.chmodSync(file,0o755);}
 const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'library_visual_server.py')],
  {stdio:['ignore','pipe','pipe'],env:{...process.env,PATH:standins+path.delimiter+process.env.PATH,BROWSER:'false'}});
 let browser,diagnostics='';child.stderr.on('data',b=>diagnostics+=b);
 try{
  const url=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostics)),20000);child.stdout.on('data',b=>{raw+=b;if(raw.startsWith('http://')&&raw.includes('\n')){clearTimeout(timer);resolve(raw.split('\n')[0]);}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostics));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER||undefined});
  const page=await browser.newPage({viewport:{width:1280,height:900},colorScheme:'light'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const results=process.env.LIBRARY_VISUAL_RESULTS;
  async function capture(name){if(results){fs.mkdirSync(results,{recursive:true});await page.screenshot({path:path.join(results,name+'.png'),fullPage:!name.startsWith('sheet')});}}   // a sheet as the screen shows it
  async function fit(where){assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),where+': the page scrolls sideways');}
  // Every control a person presses is at least 44px tall; checkboxes sit inside 44px labels.
  async function tall(scope,where){
   const short=await page.locator(scope).evaluateAll(nodes=>nodes.filter(n=>n.offsetParent!==null&&n.getBoundingClientRect().height<43.5).map(n=>n.tagName+':'+(n.textContent||n.getAttribute('aria-label')||n.dataset.key||'').trim().slice(0,40)));
   assert.deepEqual(short,[],where+': controls under 44px');
  }
  // Forms, lists and reading surfaces stay opaque: no see-through fill and no backdrop blur.
  async function opaque(scope,where){
   const seen=await page.locator(scope).evaluateAll(nodes=>nodes.filter(n=>n.offsetParent!==null).map(n=>{const s=getComputedStyle(n);const m=s.backgroundColor.match(/rgba?\(([^)]+)\)/);const alpha=m&&m[1].split(',').length===4?Number(m[1].split(',')[3]):1;return {alpha,blur:s.backdropFilter,cls:n.className};}));
   assert.ok(seen.length,where+': nothing to look at');
   for(const one of seen){assert.equal(one.alpha,1,where+': '+one.cls+' is see-through');assert.ok(!one.blur||one.blur==='none',where+': '+one.cls+' blurs what is behind it');}
  }
  // Every row's words wrap inside its list: nothing runs past the list's edge, where a sheet
  // or a card would cut it off.
  async function contained(scope,where){
   const out=await page.locator(scope+' .library-row').evaluateAll(rows=>rows.flatMap(row=>{const edge=row.closest('.library-list').getBoundingClientRect().right+0.5;
    return [...row.querySelectorAll('.row-title, .quiet, .problem, .button, select')].filter(n=>n.getBoundingClientRect().right>edge).map(n=>n.textContent.trim().slice(0,40));}));
   assert.deepEqual(out,[],where+': words run past the list');
  }
  async function scheme(width,colorScheme){await page.setViewportSize({width,height:width<500?800:900});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});}

  await page.goto(url);
  await page.locator('button.nav-item[data-view="library"]').click();
  await page.locator('#library .library-row').first().waitFor();
  await page.locator('#library h3').filter({hasText:/^31 documents$/}).waitFor();   // every document counted
  // The long title wraps inside its row.
  const long=page.locator('#library .library-row').filter({hasText:'deliberately long title'});
  assert.equal(await long.count(),1);
  for(const width of [1280,390,320])for(const colorScheme of ['light','dark']){
   await scheme(width,colorScheme);await fit(`Library ${width} ${colorScheme}`);
   await tall('#library .button, #library select.input, #library input.input:not([type=file])',`Library ${width} ${colorScheme}`);
   await opaque('#library .library-list, #library .card',`Library ${width} ${colorScheme}`);
   await contained('#library',`Library ${width} ${colorScheme}`);
   const row=await long.boundingBox();assert.ok(row.x>=0&&row.x+row.width<=width+0.5,'a long title stays in its row at '+width);
   if(width!==1280)await capture(`library-${width}-${colorScheme}`);
  }

  // Add existing work to library: the preview, phone sized, then the confirm.
  await scheme(390,'light');
  await page.locator('#library-existing-preview').click();
  const add=page.getByRole('button',{name:'Add 3 to library',exact:true});await add.waitFor();
  const preview=await page.locator('#library-existing-result').innerText();
  for(const words of ['Blog Studio','Workspace: ','Presentation Studio has no workspace','3 items found: 3 new','Gateway guide','Finished blog','Markdown, Original','Will be added','needs text'])
   assert.ok(preview.includes(words),'the preview says '+words+': '+preview);
  for(const width of [390,320])for(const colorScheme of ['light','dark']){
   await scheme(width,colorScheme);await fit(`Preview ${width} ${colorScheme}`);
   await tall('#library-existing .button',`Preview ${width} ${colorScheme}`);
   await opaque('#library-existing .library-list',`Preview ${width} ${colorScheme}`);
   await contained('#library-existing',`Preview ${width} ${colorScheme}`);
   await capture(`existing-preview-${width}-${colorScheme}`);
  }
  await scheme(390,'light');
  await add.click();
  await page.locator('#library-existing-result').getByText('3 added.',{exact:true}).waitFor();
  await page.locator('#library h3').filter({hasText:/^34 documents$/}).waitFor();
  assert.equal(await page.evaluate(()=>document.activeElement?.id),'library-existing-preview','focus returns to Preview');
  await page.locator('#library-existing-preview').click();
  await page.locator('#library-existing-result').getByText('Everything found is already in the library.').waitFor();
  await capture('existing-again-390-light');

  // The Add from library sheet every studio opens, from the same page and the same routes.
  async function openSheet(){
   await page.evaluate(()=>{window.__picks=null;const opener=document.querySelector('#library-existing-preview');opener.focus();
    window.StudioLibrary.pick({studio:'blog',roles:[['facts','Facts (may be quoted)'],['example','Example of the kind of post']],max:20,
     post:(route,body)=>api(route,body),use:async picks=>{window.__picks=picks;}});});
   await page.locator('dialog.library-sheet[open] .library-row').first().waitFor();
  }
  await openSheet();
  assert.equal(await page.evaluate(()=>document.activeElement?.dataset.key),'library-query','the sheet opens on its search');
  for(const width of [390,320])for(const colorScheme of ['light','dark']){
   await scheme(width,colorScheme);await fit(`Sheet ${width} ${colorScheme}`);
   const box=await page.locator('dialog.library-sheet').boundingBox();
   assert.ok(box.x>=0&&box.x+box.width<=width+0.5,`the sheet fits a ${width}px phone`);
   await tall('dialog.library-sheet .button, dialog.library-sheet select.input, dialog.library-sheet input.input, dialog.library-sheet label.library-tick',`Sheet ${width} ${colorScheme}`);
   await opaque('dialog.library-sheet .library-list',`Sheet ${width} ${colorScheme}`);
   await contained('dialog.library-sheet',`Sheet ${width} ${colorScheme}`);
   await capture(`sheet-${width}-${colorScheme}`);
  }
  // Keyboard: a tick by Space, then the selection bar with its count; Escape changes nothing.
  await scheme(390,'light');
  const tick=page.locator('dialog.library-sheet input[type=checkbox][data-key^="library-tick-"]:not([disabled])').first();
  await tick.focus();await page.keyboard.press('Space');
  await page.locator('dialog.library-sheet .selection-bar').getByText('1 selected').waitFor();
  assert.equal(await page.locator('dialog.library-sheet select[data-key^="library-role-"]').count(),1,'a ticked document takes a role');
  await fit('Sheet with a selection');await contained('dialog.library-sheet','Sheet with a selection');await capture('sheet-selected-390-light');
  assert.notEqual(await page.locator('dialog.library-sheet .selection-bar').evaluate(n=>getComputedStyle(n).backdropFilter),'none','the selection bar is material');
  const cdp=await page.context().newCDPSession(page);
  await cdp.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'},{name:'prefers-contrast',value:'more'},{name:'prefers-reduced-motion',value:'reduce'}]});
  assert.equal(await page.locator('dialog.library-sheet .selection-bar').evaluate(n=>getComputedStyle(n).backdropFilter),'none','reduced transparency: a solid selection bar');
  await opaque('dialog.library-sheet .selection-bar, dialog.library-sheet .library-list','Sheet with reduced transparency');
  await capture('sheet-reduced-390-light');
  await page.keyboard.press('Escape');
  await page.locator('dialog.library-sheet').waitFor({state:'detached'});
  assert.equal(await page.evaluate(()=>window.__picks),null,'Escape chose nothing');
  assert.equal(await page.evaluate(()=>document.activeElement?.id),'library-existing-preview','focus goes back to what opened the sheet');
  await page.locator('#library').evaluate(()=>scrollTo(0,0));
  await fit('Library with reduced transparency');await opaque('#library .library-list, #library .card','Library with reduced transparency');
  await capture('library-reduced-390-light');
  await cdp.send('Emulation.setEmulatedMedia',{features:[]});
  // Use selected hands over the ticked revision, with its role, and closes the sheet.
  await openSheet();
  await page.locator('dialog.library-sheet input[type=checkbox][data-key^="library-tick-"]:not([disabled])').first().check();
  await page.locator('dialog.library-sheet [data-key="library-use"]').click();
  await page.locator('dialog.library-sheet').waitFor({state:'detached'});
  const picks=await page.evaluate(()=>window.__picks);
  assert.equal(picks.length,1);assert.deepEqual(Object.keys(picks[0]).sort(),['id','revision','role']);assert.equal(picks[0].role,'facts');
  assert.deepEqual(errors,[]);
  console.log('PASS Document Library in a browser: the Library screen, Add existing work to library and the Add from library sheet at 1280, 390 and 320px, light and dark, reduced motion and reduced transparency with more contrast; opaque lists, 44px controls, keyboard ticks, Escape and focus; no studio, assistant or provider started');
 }catch(e){console.error(e);throw e;}
 finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve();},10000).unref();}});fs.rmSync(standins,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
