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
   // The screen has one filled button: Add documents, in its toolbar.
   const filled=await page.locator('.toolbar .button-filled, #library .button-filled').evaluateAll(nodes=>nodes.filter(n=>n.offsetParent!==null).map(n=>n.textContent.trim()));
   assert.deepEqual(filled,['Add documents'],`Library ${width} ${colorScheme}: one filled button`);
  }

  // List first: on a 390×844 phone the first document row is in view without scrolling, and
  // Add existing work is a plain button, prominent until something has been imported.
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
  const firstRow=await page.locator('#library .library-row').first().boundingBox();
  assert.ok(firstRow.y+firstRow.height<=844,'the first document row is in view on a phone: '+JSON.stringify(firstRow));
  assert.equal(await page.locator('#library-existing-open').getAttribute('class'),'button');
  assert.ok(await page.locator('#library-existing-hint').isVisible());

  // Phone Filters: only the search shows; Filters, by keyboard, opens Type, From, Origin,
  // Status and Author and counts those set. The Add from library sheet has the same.
  async function phoneFilters(scope,where){
   const type=page.locator(scope+' select[data-key="library-kind"]');
   assert.equal(await type.isVisible(),false,where+': Type waits under Filters');
   const toggle=page.locator(scope+' [data-key="library-filters-toggle"]');
   assert.equal(await toggle.getAttribute('aria-expanded'),'false');
   await toggle.focus();await page.keyboard.press('Enter');
   for(const key of ['kind','studio','origin','state','author'])
    assert.ok(await page.locator(scope+` [data-key="library-${key}"]`).isVisible(),where+': Filters shows '+key);
   assert.equal(await page.locator(scope+' [data-key="library-filters-toggle"]').getAttribute('aria-expanded'),'true');
   assert.equal(await page.evaluate(()=>document.activeElement?.dataset.key),'library-filters-toggle',where+': focus stays on Filters');
   await page.locator(scope+' select[data-key="library-kind"]').focus();
   await page.locator(scope+' select[data-key="library-kind"]').selectOption('upload');
   await page.locator(scope+' [data-key="library-filters-toggle"]').filter({hasText:'Filters (1)'}).waitFor();
   await fit(where+' with Filters open');await tall(scope+' .button, '+scope+' select.input, '+scope+' input.input',where+' with Filters open');
   await capture(where.replaceAll(' ','-').toLowerCase());
   await page.locator(scope+' select[data-key="library-kind"]').selectOption('');
   await page.locator(scope+' [data-key="library-filters-toggle"]').filter({hasText:/^Filters$/}).waitFor();
   await page.locator(scope+' [data-key="library-filters-toggle"]').click();
  }
  await phoneFilters('#library','library-filters-390');
  await page.locator('#library h3').filter({hasText:/^31 documents$/}).waitFor();

  // Add existing work to library: the preview, phone sized, then the confirm.
  await scheme(390,'light');
  await page.locator('#library-existing-open').click();
  await page.locator('dialog#library-existing[open]').waitFor();
  await page.locator('#library-existing-preview').focus();await page.keyboard.press('Enter');
  await page.locator('#library-existing-said').waitFor();
  assert.equal(await page.evaluate(()=>document.activeElement?.id),'library-existing-said','Preview existing work lands on what it found');
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
  assert.equal(await page.evaluate(()=>document.activeElement?.id),'library-existing-said','Preview again lands on what it found');
  await capture('existing-again-390-light');
  await page.keyboard.press('Escape');
  await page.locator('dialog#library-existing[open]').waitFor({state:'detached'}).catch(()=>{});
  assert.equal(await page.locator('dialog#library-existing').evaluate(n=>n.open),false);
  assert.equal(await page.evaluate(()=>document.activeElement?.id),'library-existing-open','focus returns to Add existing work');
  // Once something was imported, Add existing work is quiet and its hint is gone.
  await page.waitForFunction(()=>document.querySelector('#library-existing-open').className==='button button-quiet');
  assert.equal(await page.locator('#library-existing-hint').isVisible(),false);

  // Add documents: three files, one of them refused, then the same again. Each file is
  // reported by name, the refusal stops nothing, and a retry adds nothing twice.
  async function addFiles(files){
   await page.locator('#library-files').setInputFiles(files);
   await page.locator('#library-add').click();
   await page.locator('#library-add-results [role=status]').waitFor();
   await page.waitForFunction(()=>!document.querySelector('#library-add').disabled);
   return page.locator('#library-add-results').innerText();
  }
  const mixed=[{name:'alpha.md',mimeType:'text/markdown',buffer:Buffer.from('# Alpha\n\nSynthetic alpha.\n')},
   {name:'beta.png',mimeType:'image/png',buffer:Buffer.from('synthetic, not a picture')},
   {name:'gamma.txt',mimeType:'text/plain',buffer:Buffer.from('Synthetic gamma.\n')}];
  for(const width of [1280,390]){
   await scheme(width,'light');
   await page.locator('#library-add-open').click();
   await page.locator('dialog#library-add-sheet[open]').waitFor();
   assert.equal(await page.evaluate(()=>document.activeElement?.id),'library-files','the sheet opens on its files');
   const first=await addFiles(mixed);
   const expected=width===1280?['2 added, 1 not added.','alpha.md','Added as “alpha”','beta.png','"beta.png" is not a text','gamma.txt','Added as “gamma”']
    :['2 already in the library, 1 not added.','alpha.md','Already there','beta.png','Not added','gamma.txt'];
   for(const words of expected)assert.ok(first.includes(words),`${width}: the upload says ${words}: ${first}`);
   assert.equal(await page.evaluate(()=>document.activeElement?.closest('#library-add-results')!==null),true,'focus lands on the outcome');
   assert.deepEqual(await page.locator('#library-files').evaluate(n=>[...n.files].map(f=>f.name)),['beta.png'],'only the refused file stays chosen');
   await page.locator('#library h3').filter({hasText:/^36 documents$/}).waitFor();
   const again=await page.locator('#library-add').click().then(()=>page.locator('#library-add-results').getByText('1 not added.',{exact:true}).waitFor()).then(()=>page.locator('#library-add-results').innerText());
   assert.ok(again.includes('beta.png'),'a retry tries only what was refused');
   await fit(`Add documents ${width}`);await tall('#library-add-sheet .button, #library-add-sheet input.input',`Add documents ${width}`);
   await opaque('#library-add-sheet .library-list',`Add documents ${width}`);await contained('#library-add-sheet',`Add documents ${width}`);
   await capture(`sheet-add-documents-${width}-light`);
   await page.locator('#library-add-cancel').click();
   assert.equal(await page.evaluate(()=>document.activeElement?.id),'library-add-open','focus returns to Add documents');
  }
  // A file over 8 MB is reported for that file, beside one that is added.
  await page.locator('#library-add-open').click();
  const big=await addFiles([{name:'huge.txt',mimeType:'text/plain',buffer:Buffer.alloc(8_000_001,97)},
   {name:'delta.md',mimeType:'text/markdown',buffer:Buffer.from('Synthetic delta.\n')}]);
  assert.ok(big.includes('huge.txt')&&big.includes('larger than 8 MB')&&big.includes('Added as “delta”'),'the oversize file is named: '+big);
  await page.locator('#library h3').filter({hasText:/^37 documents$/}).waitFor();
  await page.locator('#library-add-close').click();

  // Preview opens below its row and Close preview returns to that row's Preview, by keyboard,
  // at 1280 and 390px; the downloads are in the preview.
  for(const width of [1280,390]){
   await scheme(width,'light');
   const opener=page.locator('#library .library-row').nth(5).locator('[data-key^="library-preview-"]');
   const key=await opener.getAttribute('data-key');
   await opener.focus();await page.keyboard.press('Enter');
   // Focus moves to the preview once its document is read.
   await page.waitForFunction(()=>document.activeElement?.dataset.key==='library-preview-heading'&&document.activeElement.closest('.library-preview-item'));
   const next=await page.locator('#library .library-list > li').evaluateAll((items,key)=>{const at=items.findIndex(n=>n.querySelector(`[data-key="${key}"]`));return items[at+1].className;},key);
   assert.equal(next,'library-preview-item','the preview opens just below its row');
   assert.ok(await page.locator('#library .library-preview [data-key^="library-download-"]').count(),'downloads are in the preview');
   await page.locator('#library [data-key="library-preview-close"]').focus();await page.keyboard.press('Enter');
   assert.equal(await page.evaluate(()=>document.activeElement?.dataset.key),key,`${width}: Close preview lands on the same row's Preview`);
   const back=await page.locator(`#library [data-key="${key}"]`).boundingBox();
   assert.ok(back.y>=0&&back.y+back.height<=(width<500?800:900),'the row is in view');
  }

  // The Add from library sheet every studio opens, from the same page and the same routes.
  async function openSheet(){
   await page.evaluate(()=>{window.__picks=null;const opener=document.querySelector('#library-add-open');opener.focus();
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
  // The sheet's filters work on a phone just as the Library's do.
  await scheme(390,'light');
  await phoneFilters('dialog.library-sheet','sheet-filters-390');
  // Keyboard: a tick by Space, then the selection bar with its count; Escape changes nothing.
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
  assert.equal(await page.evaluate(()=>document.activeElement?.id),'library-add-open','focus goes back to what opened the sheet');
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

  // Remove from library: said and confirmed in place, then gone from the list and from Add
  // from library; Show hidden lists it and Restore brings it back.
  await scheme(1280,'light');
  const doomed=page.locator('#library .library-row [data-key^="library-preview-"]').first();
  const id=(await doomed.getAttribute('data-key')).slice('library-preview-'.length);
  await doomed.click();
  await page.locator(`#library [data-key="library-remove-${id}"]`).click();
  assert.equal(await page.evaluate(()=>document.activeElement?.dataset.key),'library-remove-cancel','the safe choice has focus');
  const warning=await page.locator('#library .library-removal').innerText();
  for(const words of ['Nothing is deleted','keep their copy','no studio workspace is changed'])assert.ok(warning.includes(words),'Remove says '+words);
  await fit('Remove from library');await tall('#library .library-removal .button','Remove from library');
  await capture('library-remove-1280-light');
  await page.locator('#library [data-key="library-remove-confirm"]').click();
  await page.locator('#library h3').filter({hasText:/^36 documents$/}).waitFor();
  assert.equal(await page.locator(`#library [data-key="library-row-${id}"]`).count(),0,'a removed document leaves the list');
  await openSheet();
  assert.equal(await page.locator(`dialog.library-sheet [data-key="library-row-${id}"]`).count(),0,'and Add from library');
  await page.keyboard.press('Escape');await page.locator('dialog.library-sheet').waitFor({state:'detached'});
  await page.locator('#library [data-key="library-show-hidden"]').click();
  await page.locator(`#library [data-key="library-row-${id}"]`).getByText('Hidden',{exact:true}).waitFor();
  await page.locator(`#library [data-key="library-preview-${id}"]`).click();
  await page.locator(`#library [data-key="library-restore-${id}"]`).click();
  await page.locator(`#library [data-key="library-row-${id}"] .tag`).waitFor({state:'detached'});
  await page.locator('#library [data-key="library-show-hidden"]').click();   // it is redrawn, then gone
  await page.locator('#library h3').filter({hasText:/^37 documents$/}).waitFor();
  assert.equal(await page.locator('#library [data-key="library-show-hidden"]').count(),0,'nothing is hidden now');
  // On the same open page, a file added earlier then removed is shown again by uploading it:
  // the page asks the server rather than answering from what it added before.
  const alphaKey=await page.locator('#library-catalog .library-row').evaluateAll(rows=>rows.find(row=>row.querySelector('.row-title')?.textContent==='alpha')?.querySelector('[data-key^="library-preview-"]')?.dataset.key);
  assert.ok(alphaKey,'alpha is listed');
  await page.locator(`#library [data-key="${alphaKey}"]`).click();
  await page.locator(`#library [data-key="library-remove-${alphaKey.slice('library-preview-'.length)}"]`).click();
  await page.locator('#library [data-key="library-remove-confirm"]').click();
  await page.locator('#library h3').filter({hasText:/^36 documents$/}).waitFor();
  await page.locator('#library-add-open').click();
  const shownAgain=await addFiles([mixed[0]]);
  assert.ok(shownAgain.includes('Shown again as “alpha”'),'uploading a removed file shows it again: '+shownAgain);
  await page.locator('#library h3').filter({hasText:/^37 documents$/}).waitFor();
  await page.locator('#library-add-close').click();
  assert.deepEqual(errors,[]);
  console.log('PASS Document Library in a browser: the Library screen list first with one filled action, phone Filters in the Library and the Add from library sheet, Add documents with a mixed and an oversize upload reported per file and retried without duplicates, preview beside its row with focus back, Add existing work to library, Remove from library and Restore, at 1280, 390 and 320px, light and dark, reduced motion and reduced transparency with more contrast; opaque lists, 44px controls, keyboard ticks, Escape and focus; no studio, assistant or provider started');
 }catch(e){console.error(e);throw e;}
 finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve();},10000).unref();}});fs.rmSync(standins,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
