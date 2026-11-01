/* Training Studio desk on a phone and a desktop (issue #253): the material fills the screen,
   Finishing opens where the person looks, Yoodli fields once, one ZIP per level, and Tab
   stays in an open sheet. Real page and engine; synthetic authors, research and settings. */
const {chromium}=require('playwright');
const {spawn,execFileSync}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),os=require('node:os'),assert=require('node:assert/strict');
const python=process.env.PYTHON||'python3';
const JOBS=/drafts\/(note|revise|selection|retry|layout|write-whole|finish|apply|source|ready|level-ready|draft|update|send|doc)$|\/api\/(publish|documents|research-sources)$/;
async function fixture(){
 const child=spawn(python,[path.join(__dirname,'training_plan_fixture.py'),'--desk','--two-levels','--yoodli'],{stdio:['ignore','pipe','pipe']});
 let diagnostics='';child.stderr.on('data',b=>diagnostics+=b);
 const found=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timed out '+diagnostics)),60000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+' '+diagnostics));});});
 return {child,...found};
}
async function stop(child){child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve();},10000).unref();}});}
// What covers the page while it is read: the sticky toolbar and, on a phone, the tab bar.
const chrome=page=>page.evaluate(()=>{const bar=document.getElementById('toolbar').getBoundingClientRect().height;const side=document.getElementById('sidebar');const fixed=getComputedStyle(side).position==='fixed';return Math.round(bar+(fixed?side.getBoundingClientRect().height:0));});
// The first line of what is read, inside the part of the screen nothing covers.
const firstLineShown=page=>page.evaluate(()=>{const doc=document.querySelector('.desk-reading .md > *, .desk-reading > p, .desk-yoodli-field .row-title');if(!doc)return 'nothing to read';const r=doc.getBoundingClientRect();const top=document.getElementById('toolbar').getBoundingClientRect().bottom;const side=document.getElementById('sidebar');const bottom=getComputedStyle(side).position==='fixed'?side.getBoundingClientRect().top:innerHeight;return r.top>=top-1&&r.top+16<=bottom?true:'first line at '+Math.round(r.top)+', view '+Math.round(top)+'-'+Math.round(bottom);});
const small=page=>page.evaluate(()=>[...document.querySelectorAll('#toolbar button, #toolbar summary, [role=tab], .menu-item')].filter(n=>n.getClientRects().length&&getComputedStyle(n).visibility!=='hidden').filter(n=>n.getBoundingClientRect().height<43.5).map(n=>(n.getAttribute('aria-label')||n.textContent).trim()+' '+n.getBoundingClientRect().height));
const noSideScroll=page=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);
// The page with every script run. The fixture's one-at-a-time server can reset a script's
// connection while the engine is busy; the page is then loaded again, as a person would.
async function opened(page,url){
 for(let tries=0;;tries++){
  await page.goto(url);
  try{await page.waitForFunction(()=>typeof ask==='function'&&typeof paintDesk==='function',null,{timeout:10000});return;}
  catch(e){if(tries>=3)throw e;}
 }
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
 const shots=process.env.TRAINING_DESK_UI_RESULTS;
 try{
  for(const [width,height,theme] of [[390,844,'light'],[1280,900,'light'],[390,844,'dark'],[1280,900,'dark']]){
   const {child,url,path:root}=await fixture();
   let page;
   try{
    page=await browser.newPage({viewport:{width,height},colorScheme:theme});
    const errors=[],writes=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.method()==='POST')writes.push(new URL(r.url()).pathname);});
    await page.addInitScript(({root})=>history.replaceState({screen:'run',path:root},''),{root});
    page.on('requestfailed',r=>console.error('Request failed: '+r.url()+' '+(r.failure()||{}).errorText));page.on('console',m=>{if(m.type()==='error')console.error('Console: '+m.text());});await opened(page,url);
    await page.waitForFunction(root=>ask('run',{path:root}).then(run=>run.state==='done'),root,{timeout:90000});
    await page.getByRole('tab',{name:/^Plan · Draft$/}).waitFor({timeout:30000});
    const phone=width<600;
    // 1. The chrome while reading, and what the first screen shows after a tab is chosen.
    if(phone){
     assert.ok(await chrome(page)<=120,'Sticky chrome is '+await chrome(page)+'px');
     assert.equal(await page.locator('#actions > *').count(),2,'One filled action and More');
     await page.locator('#actions summary[aria-label="More"]').click();
     for(const name of ['Download level 101','Google Doc','Finishing'])await page.locator('.menu-item',{hasText:name}).waitFor();
     assert.deepEqual(await small(page),[]);
     await page.keyboard.press('Escape');
    }
    for(const tab of [/^Guide · Draft$/,/^Plan · Draft$/]){
     await page.getByRole('tab',{name:tab}).click();
     assert.equal(await firstLineShown(page),true,'After choosing '+tab);
     assert.equal(await page.getByRole('tab',{name:tab}).evaluate(n=>n===document.activeElement),true,'The chosen tab keeps the focus');
    }
    await page.getByRole('tab',{name:'Sizing',exact:true}).click();
    assert.equal(await firstLineShown(page),true,'After choosing a section');
    assert.deepEqual(await small(page),[]);
    assert.ok(await noSideScroll(page),'No sideways page scroll');
    if(shots){fs.mkdirSync(shots,{recursive:true});await page.screenshot({path:path.join(shots,`desk-reading-${width}-${theme}.png`)});}
    // 2. Finishing opens in view with its heading focused; Close and Escape give the focus back.
    await page.getByRole('tab',{name:/^Guide · Draft$/}).click();
    const finishing=async()=>{if(phone)await page.locator('#actions summary[aria-label="More"]').click();await page.locator(phone?'.menu-item':'#actions button',{hasText:'Finishing'}).click();};
    const back=phone?'More':'Finishing';
    for(const how of ['Close','Escape']){
     await finishing();
     const title=page.locator('.desk-finish-title');
     await title.waitFor();
     assert.equal(await title.evaluate(n=>n===document.activeElement),true,'Finishing heading has the focus');
     const box=await title.boundingBox(),bar=await page.locator('#toolbar').boundingBox();
     assert.ok(box.y>=bar.y+bar.height-1&&box.y+box.height<=height,'Finishing heading in view: '+JSON.stringify(box));
     if(shots&&how==='Close')await page.screenshot({path:path.join(shots,`desk-finishing-${width}-${theme}.png`)});
     if(how==='Close')await page.locator('.desk-finish-head').getByRole('button',{name:'Close',exact:true}).click();
     else await page.keyboard.press('Escape');
     await page.locator('.desk-finish-title').waitFor({state:'detached'});
     assert.equal(await page.evaluate(()=>document.activeElement.getAttribute('aria-label')||document.activeElement.textContent.trim()),back,how+' returns the focus');
    }
    // 3. Yoodli: each field once, a Copy named after it, the counts, and half the height.
    await page.getByRole('tab',{name:/^Yoodli · Draft$/}).click();
    await page.locator('.desk-yoodli-field').first().waitFor();
    const copies=await page.locator('.desk-yoodli-field button').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('aria-label')));
    assert.ok(copies.length>=20,'Every field: '+copies.length);
    assert.equal(new Set(copies).size,copies.length,'Unique Copy names');
    assert.ok(copies.includes('Copy Roleplay name'));
    assert.ok(copies.every(name=>/^Copy \S/.test(name)));
    assert.equal(await page.getByRole('button',{name:'Copy text',exact:true}).count(),0,'The whole layout is not shown a second time');
    assert.ok(await page.getByText(/^\d[\d,]* of 10,000 characters$/).count()>=1,'Character counts');
    const tall=await page.evaluate(()=>document.documentElement.scrollHeight);
    if(width===1280)assert.ok(tall<=4965,'Yoodli page is '+tall+'px, at most half of 9,930');
    if(shots)await page.screenshot({path:path.join(shots,`desk-yoodli-${width}-${theme}.png`)});
    // 4. One ZIP of the level, named by level; nothing marked ready or sent.
    const before=writes.length;
    if(phone)await page.locator('#actions summary[aria-label="More"]').click();
    await page.locator(phone?'.menu-item':'#actions button',{hasText:'Download level 101'}).click();
    const [file]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'Download level 101 (.zip)',exact:true}).click()]);
    const saved=path.join(fs.mkdtempSync(path.join(os.tmpdir(),'training-zip-')),file.suggestedFilename());
    await file.saveAs(saved);
    const inside=JSON.parse(execFileSync(python,['-c','import json,sys,zipfile;print(json.dumps(sorted(zipfile.ZipFile(sys.argv[1]).namelist())))',saved]));
    assert.ok(/-level-101-materials\.zip$/.test(file.suggestedFilename()),file.suggestedFilename());
    assert.ok(inside.length>=5&&inside.every(name=>name.startsWith('101-')),JSON.stringify(inside));
    for(const name of ['101-plan.md','101-learner-guide.md','101-brief.md','101-practice.md','101-yoodli.md'])assert.ok(inside.includes(name),name+' in '+inside);
    // 5. Tab and Shift+Tab stay in the open sheet, keyboard only.
    for(const key of ['Tab','Shift+Tab']){
     for(let i=0;i<14;i++){await page.keyboard.press(key);assert.equal(await page.evaluate(()=>document.getElementById('sheet').contains(document.activeElement)),true,key+' left the sheet');}
    }
    await page.keyboard.press('Escape');
    await page.getByRole('tab',{name:'Research & sources',exact:true}).click();
    await page.getByRole('button',{name:'Add a source',exact:true}).click();
    await page.getByRole('heading',{name:'Add a source',exact:true}).waitFor();
    for(const key of ['Tab','Shift+Tab']){
     const seen=new Set();
     for(let i=0;i<16;i++){await page.keyboard.press(key);const at=await page.evaluate(()=>({inside:document.getElementById('sheet').contains(document.activeElement),name:(document.activeElement.getAttribute('aria-label')||document.activeElement.textContent||document.activeElement.tagName).trim().slice(0,40)}));assert.equal(at.inside,true,key+' reached '+at.name);seen.add(at.name);}
     assert.ok(seen.has('Cancel'),'It goes round to Cancel: '+[...seen]);
    }
    await page.keyboard.press('Escape');
    assert.deepEqual(writes.slice(before).filter(route=>JOBS.test(route)),[],'Reading, downloading and Tab start nothing');
    assert.deepEqual(errors,[]);
   }catch(e){if(page)console.error(width+' '+theme+': '+(await page.locator('body').innerText()).slice(0,3000));throw e;}
   finally{if(page)await page.close();await stop(child);}
  }
  console.log('PASS Training Studio desk at 390 and 1280, light and dark: chrome under 120px on a phone, first line after a tab, 44px controls, Finishing in view and focused, Yoodli fields once with named Copy, one ZIP per level, Tab kept in sheets');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
