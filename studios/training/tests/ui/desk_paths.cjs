/* Training Studio paths that used to end nowhere (issue #254): a first Start with only the
   required boxes filled, a Document Library document pinned at Start and from Add a source on
   a public-web desk, and Publish on a finished desk. Real page and engine; synthetic authors,
   research, library and settings; keyboard only where a person chooses. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const python=process.env.PYTHON||'python3';
const RESEARCH=/drafts\/(note|revise|selection|retry|layout|write-whole|finish|source)$|\/api\/(update-research|research-sources)$/;
async function fixture(...flags){
 const child=spawn(python,[path.join(__dirname,'training_plan_fixture.py'),...flags],{stdio:['ignore','pipe','pipe']});
 let diagnostics='';child.stderr.on('data',b=>diagnostics+=b);
 const found=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timed out '+diagnostics)),60000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+' '+diagnostics));});});
 return {child,...found};
}
async function stop(child){child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve();},10000).unref();}});}
// Add from library, by keyboard: the document ticked with Space, then Use selected.
async function pickFromLibrary(page,opener){
 await opener.focus();await page.keyboard.press('Enter');
 const sheet=page.locator('dialog.library-sheet');await sheet.waitFor();
 const tick=sheet.getByRole('checkbox',{name:/^Select /});await tick.first().waitFor();
 await tick.first().focus();await page.keyboard.press('Space');
 const use=sheet.getByRole('button',{name:'Use selected',exact:true});
 await use.focus();await page.keyboard.press('Enter');
 await sheet.waitFor({state:'detached'});
}
// The page with every script run. The fixture's one-at-a-time server can reset a script's
// connection while the engine is busy; the page is then loaded again, as a person would.
async function opened(page,url){
 for(let tries=0;;tries++){
  await page.goto(url);
  try{await page.waitForFunction(()=>typeof ask==='function'&&typeof paintDesk==='function',null,{timeout:10000});return;}
  catch(e){if(tries>=3)throw e;}
 }
}
// Add from library opened, then Escape: the dialog goes, the sheet under it stays, and the
// focus is back on Add from library.
async function escapeLibrary(page,opener,key){
 await opener.focus();await page.keyboard.press('Enter');
 const dialog=page.locator('dialog.library-sheet');await dialog.waitFor();
 await dialog.getByRole('checkbox',{name:/^Select /}).first().waitFor();
 await page.keyboard.press('Escape');
 await dialog.waitFor({state:'detached'});
 assert.ok(await page.locator('#sheet').isVisible(),'The sheet under the library stays open');
 await page.waitForFunction(key=>document.activeElement&&document.activeElement.dataset.key===key,key,{timeout:5000});
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
 const shots=process.env.TRAINING_DESK_UI_RESULTS;
 try{
  for(const [width,height,theme] of [[390,844,'light'],[1280,900,'dark']].filter(([w])=>!process.env.ONLY_WIDTH||String(w)===process.env.ONLY_WIDTH)){
   // 1. First Start: the learner guide is chosen to start with, and a library document goes
   //    with the start's sources, pinned once, never uploaded again.
   {
    const {child,url}=await fixture('--new','--desk','--library');
    let page;
    try{
     page=await browser.newPage({viewport:{width,height},colorScheme:theme});
     const errors=[],writes=[];page.on('pageerror',e=>{errors.push(e.message);console.error('Page error: '+e.message);});
     page.on('request',r=>{if(r.method()==='POST')writes.push(new URL(r.url()).pathname);});
     page.on('requestfailed',r=>console.error('Request failed: '+r.url()+' '+(r.failure()||{}).errorText));page.on('console',m=>{if(m.type()==='error')console.error('Console: '+m.text());});await opened(page,url);
     await page.getByRole('button',{name:'New training',exact:true}).first().click();
     assert.equal(await page.getByRole('checkbox',{name:'Learner guide',exact:true}).isChecked(),true,'Learner guide is chosen to start with');
     await page.getByLabel('A short title',{exact:true}).fill('Library start');
     await page.getByLabel('What should it teach?',{exact:true}).fill('How a rolling restart keeps capacity.');
     await page.getByLabel('Who is it for?',{exact:true}).fill('Platform engineers new to it.');
     const library=page.locator('#sheet [data-key="research-library"]');
     await library.waitFor();
     await escapeLibrary(page,library,'research-library');
     assert.equal(await page.getByLabel('A short title',{exact:true}).inputValue(),'Library start','Escape in the library keeps the form');
     await pickFromLibrary(page,library);
     await page.locator('#sheet').getByText('From the Document Library, revision 1',{exact:true}).waitFor();
     assert.equal(await page.evaluate(()=>document.getElementById('sheet').contains(document.activeElement)),true,'Focus is back in the sheet');
     if(shots){fs.mkdirSync(shots,{recursive:true});await page.screenshot({path:path.join(shots,`start-library-${width}-${theme}.png`)});}
     const start=page.locator('#sheet').getByRole('button',{name:'Start',exact:true});
     await start.focus();await page.keyboard.press('Enter');
     await page.getByRole('tab',{name:/^Plan · /}).waitFor({timeout:60000});
     const started=await page.evaluate(()=>view.path);
     const run=await page.evaluate(root=>ask('run',{path:root}),started);
     const added=(run.documents&&run.documents.added)||[];
     assert.ok(added.some(one=>one.library&&one.library.revision===1),'The library document is the training\'s own: '+JSON.stringify(added));
     assert.ok(!run.documents.waiting,'Nothing waits for documents');
     const kept=await page.evaluate(()=>send('library',{studio:'training'}).then(found=>found.total));
     assert.equal(kept,1,'No second library entry');
     assert.ok(!writes.includes('/api/documents'),'Nothing was uploaded');
     assert.deepEqual(errors,[]);
    }catch(e){if(page)console.error('Start '+width+': '+(await page.locator('body').innerText()).slice(0,2500));throw e;}
    finally{if(page)await page.close();await stop(child);}
   }
   // 2. A public-web desk: Add a source offers the library; the document waits, unread,
   //    until Update the research. Then the finished desk is published from its desk.
   {
    const {child,url,path:root}=await fixture('--desk','--library');
    let page;
    try{
     page=await browser.newPage({viewport:{width,height},colorScheme:theme});
     const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
     page.on('request',r=>{if(r.method()==='POST')writes.push(new URL(r.url()).pathname);});
     await page.addInitScript(({root})=>history.replaceState({screen:'run',path:root},''),{root});
     page.on('requestfailed',r=>console.error('Request failed: '+r.url()+' '+(r.failure()||{}).errorText));page.on('console',m=>{if(m.type()==='error')console.error('Console: '+m.text());});await opened(page,url);
     await page.waitForFunction(root=>ask('run',{path:root}).then(run=>run.state==='done'),root,{timeout:90000});
     await page.getByRole('tab',{name:'Research & sources',exact:true}).click();
     assert.equal(await page.getByRole('button',{name:'Add from library',exact:true}).count(),0,'Not before research reads documents');
     await page.getByRole('button',{name:'Add a source',exact:true}).click();
     await page.getByText('They wait, unread, until you choose Update the research. You can choose several at once.',{exact:true}).waitFor();
     await page.getByText('This training is researched from the public web. From now on it reads your documents too.',{exact:true}).waitFor();
     // Tab stays in the sheet, and the library sheet opened over it keeps its own Tab.
     for(let i=0;i<10;i++){await page.keyboard.press('Tab');assert.ok(await page.evaluate(()=>document.getElementById('sheet').contains(document.activeElement)));}
     // Escape in the library dialog puts away only the dialog: the files chosen are kept.
     const fromLibrary=page.locator('#sheet [data-key="desk-source-library"]');
     await page.locator('#sheet').getByLabel('Add documents',{exact:true}).setInputFiles({name:'notes.txt',mimeType:'text/plain',buffer:Buffer.from('Synthetic notes.')});
     await page.locator('#sheet').getByText('notes.txt',{exact:true}).waitFor();
     await escapeLibrary(page,fromLibrary,'desk-source-library');
     await page.locator('#sheet').getByText('notes.txt',{exact:true}).waitFor();
     await page.locator('#sheet').getByRole('button',{name:'Remove notes.txt',exact:true}).click();
     const before=writes.length;
     await pickFromLibrary(page,fromLibrary);
     await page.locator('#sheet').waitFor({state:'hidden'});
     await page.getByText(/^Not read yet: capacity-notes\.md\. The research reads it once you update it\.$/).waitFor();
     await page.waitForFunction(()=>document.activeElement&&document.activeElement.dataset.key==='desk-update-research',null,{timeout:10000});
     // Browsing the library reads; pinning is the one change, and starts no research.
     assert.deepEqual(writes.slice(before).filter(route=>!/^\/api\/library/.test(route)),['/api/documents-library'],'Pinning starts no research');
     const record=await page.evaluate(root=>ask('run',{path:root}),root);
     assert.ok(record.documents.later.some(one=>one.name==='capacity-notes.md'));
     if(shots)await page.screenshot({path:path.join(shots,`desk-library-${width}-${theme}.png`)});
     // Mark the level ready, wait for the index, then Publish from the desk.
     await page.getByRole('tab',{name:/^Plan · /}).click();
     const narrow=width<600;
     await page.locator('#actions').getByRole('button',{name:narrow?'Mark all ready':'Mark every material ready',exact:true}).click();
     await page.locator('#sheet').getByRole('button',{name:/^Mark \d+ materials? ready$/}).click();
     await page.waitForFunction(root=>ask('drafts',{path:root}).then(desk=>desk.index_written),root,{timeout:90000});
     await page.reload();
     const publish=page.getByRole('button',{name:'Publish',exact:true});
     await publish.waitFor({timeout:30000});
     // With nothing left to mark ready, Open the index is the toolbar's filled action.
     const index=page.locator('#actions > .button-filled');
     await index.waitFor();assert.equal((await index.textContent()).trim(),'Open the index');
     await publish.focus();await page.keyboard.press('Enter');
     const go=page.locator('#sheet').getByRole('button',{name:'Publish it',exact:true});
     await go.focus();await page.keyboard.press('Enter');
     await page.locator('#toasts').getByText('Published as revision 1.',{exact:true}).waitFor();
     await page.locator('#main').getByText('Published as revision 1.',{exact:true}).waitFor();
     await page.getByRole('button',{name:'Publish again',exact:true}).waitFor();
     if(shots)await page.screenshot({path:path.join(shots,`desk-published-${width}-${theme}.png`)});
     assert.ok(writes.includes('/api/publish'));
     assert.ok(!writes.some(route=>RESEARCH.test(route)),'No research or writing job was started: '+writes);
     assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No sideways scroll');
     assert.deepEqual(errors,[]);
    }catch(e){if(page)console.error('Desk '+width+': '+(await page.locator('body').innerText()).slice(0,2500));throw e;}
    finally{if(page)await page.close();await stop(child);}
   }
  }
  console.log('PASS Training Studio at 390 light and 1280 dark: first Start with the learner guide chosen, a library document pinned at Start and from Add a source without re-uploading or research, Publish and the index on a finished desk, keyboard only');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
