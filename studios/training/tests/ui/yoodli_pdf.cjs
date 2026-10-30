/* Actual Training Studio form and source API, disposable settings, no author jobs. */
const {chromium}=require('playwright');
const {spawn,execFileSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const python=process.env.PYTHON||'python3';
 const pdf=execFileSync(python,['-c',"import sys;sys.path.insert(0,'tests');from pdf_fixture import source_pdf;sys.stdout.buffer.write(source_pdf())"]);
 const browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
 try{
  for(const [width,fallback] of [[390,false],[1280,false],[390,true]]){
   const child=spawn(python,[path.join(__dirname,'training_plan_fixture.py'),'--new'],{stdio:['ignore','pipe','pipe']});
   let diagnostics='';child.stderr.on('data',raw=>diagnostics+=raw);
   let page;
   try{
    const fixture=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timed out '+diagnostics)),30000);child.stdout.on('data',value=>{raw+=value;if(raw.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(raw.split('\n')[0]));}catch(e){reject(e);}}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+' '+diagnostics));});});
    page=await browser.newPage({viewport:{width,height:950}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
    if(fallback)await page.route('**/research.js',route=>route.fulfill({contentType:'text/javascript',body:'/* legacy source-picker compatibility */'}));
    await page.goto(fixture.url);await page.getByRole('button',{name:'New training',exact:true}).click();
    const yoodli=page.getByRole('button',{name:'Make scenarios for Yoodli',exact:true});
    const brief=page.getByRole('button',{name:'Reference brief',exact:true});
    const practice=page.getByRole('button',{name:'Practice scenarios',exact:true});
    await yoodli.click();
    assert.equal(await yoodli.getAttribute('aria-pressed'),'true');
    assert.equal(await brief.getAttribute('aria-pressed'),'true');
    assert.equal(await practice.getAttribute('aria-pressed'),'true');
    await page.getByRole('status').filter({hasText:'Included Reference brief and Practice scenarios for Yoodli.'}).waitFor();
    await brief.click();assert.equal(await yoodli.getAttribute('aria-pressed'),'false');
    await page.getByText('Yoodli scenarios turned off because Reference brief was removed.',{exact:true}).waitFor();
    await yoodli.click();
    if(fallback){
     const file=page.getByLabel('Add documents',{exact:true});
     assert.ok((await file.getAttribute('accept')).split(',').includes('.pdf'));
     await file.setInputFiles({name:'reference.pdf',mimeType:'application/pdf',buffer:pdf});
     await page.getByText('reference.pdf',{exact:true}).first().waitFor();
    }else{
     const file=page.getByLabel('Upload source files',{exact:true});
     const accept=(await file.getAttribute('accept')).split(',');assert.ok(accept.includes('.pdf')&&accept.includes('application/pdf'));
     await file.setInputFiles({name:'reference.pdf',mimeType:'application/pdf',buffer:pdf});
     await page.getByText('reference.pdf',{exact:true}).first().waitFor();
     const preview=page.getByRole('button',{name:'Preview text',exact:true});
     if(process.env.STUDIO_TEST_REAL_PDF){await preview.click();await page.getByText('Synthetic PDF source for all studios.',{exact:true}).waitFor();}
     else{await page.getByText(/PDF reading needs an explicitly installed pdftotext reader/).waitFor();}
    }
    assert.equal(await yoodli.getAttribute('aria-pressed'),'true');
    assert.equal(await brief.getAttribute('aria-pressed'),'true');
    assert.equal(await practice.getAttribute('aria-pressed'),'true');
    assert.deepEqual(errors,[]);
    if(process.env.TRAINING_PLAN_UI_RESULTS){fs.mkdirSync(process.env.TRAINING_PLAN_UI_RESULTS,{recursive:true});await yoodli.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.TRAINING_PLAN_UI_RESULTS,`yoodli-pdf-${width}-${fallback?'fallback':'shared'}.png`)});}
   }catch(e){if(page)console.error('Form: '+await page.locator('body').innerText());throw e;}
   finally{if(page)await page.close();child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve();},10000).unref();}});}
  }
  console.log('PASS Training Studio phone/desktop Yoodli dependencies, native PDF selection/capture, fallback PDF picker, preserved selections');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
