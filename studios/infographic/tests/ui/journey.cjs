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
      await page.locator('#main').getByRole('button',{name:'Run checks again',exact:true}).click();
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
    await page.locator('#actions').getByRole('button',{name:'Update preview',exact:true}).click();
    await page.getByRole('heading',{name:'Draft page',exact:true}).waitFor();
    // Roadmap: one current step, and plain statements of what is done, needed and downloadable.
    assert.equal(await page.locator('.ig-roadmap [aria-current="step"]').innerText(),'Review and checks');
    await page.getByText(/^Downloads: Draft files for revision \d+, marked as drafts\.$/).waitFor();
    // Optional assistant inspection runs the local checks straight after; nothing is approved.
    await page.getByRole('button',{name:'Inspect page with assistant (optional)',exact:true}).click();
    await page.getByText('Visual review: passed',{exact:true}).first().waitFor();
    const approve=page.locator('#actions').getByRole('button',{name:/^Approve revision \d+$/});
    await approve.waitFor();
    assert.equal(await page.locator('.ig-roadmap [aria-current="step"]').innerText(),'Approved delivery');
    // Approval and local file preparation are one explicit action: no draft downloads in between.
    await page.locator('#main').getByRole('button',{name:/^Approve revision \d+ and prepare files$/}).click();
    await page.getByRole('heading',{name:'Approved delivery',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Download SVG draft',exact:true}).count(),0);
    await page.getByText(/^Downloads: Approved files for revision \d+: PNG, PDF, SVG and text\.$/).waitFor();
    // The approved page's text and PDF are kept in the Document Library from the saved files.
    await page.getByText('Kept in the Document Library with its text and PDF (library revision 1).',{exact:true}).waitFor();
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
      await page.getByRole('heading',{name:'Delivery receipt',exact:true}).waitFor();
      await page.getByText(/^Downloaded: approved revision \d+\.$/).waitFor();
      await page.getByRole('button',{name:'Download PDF again',exact:true}).waitFor();
      await page.getByRole('link',{name:'Open Google Doc',exact:true}).waitFor();
      assert.equal(await page.getByRole('link',{name:'Open Google Doc',exact:true}).getAttribute('href'),'https://docs.google.com/document/d/synthetic_delivered/edit');
      await page.getByRole('button',{name:'Done',exact:true}).click();
    }
    await page.getByRole('button',{name:'Record my review and run checks',exact:true}).click();
    await page.getByLabel('What did you inspect on the actual composed page?',{exact:true}).fill('I inspected the actual page again and confirmed its relationships.');
    await page.getByRole('button',{name:'Record review and run checks',exact:true}).click();
    await page.getByRole('heading',{name:'Earlier approval: review the current revision',exact:true}).waitFor();
    // A newer review never inherits the earlier approval or its files.
    assert.equal(await page.getByRole('button',{name:'Deliver Google Doc or PDF',exact:true}).count(),0);
    await approve.waitFor();
    await approve.click();
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
    // A rename clears nothing: the story, page and approval stay, and the approved files are
    // prepared again so they carry the new title. Earlier approved files stay downloadable.
    await page.setViewportSize({width:1280,height:900});await page.emulateMedia({colorScheme:'light'});
    const approvedAt=await page.evaluate(()=>held.project.approval.revision);
    await page.getByText('Brief and requirements',{exact:true}).click();
    await page.getByRole('button',{name:'Edit brief',exact:true}).click();
    await page.getByLabel('Working title',{exact:true}).fill('Synthetic rolling restarts');
    await page.getByRole('button',{name:'Save brief',exact:true}).click();
    await page.getByText(/^Renamed\. The story, page and approval are kept\./).waitFor();
    const renamed=await page.evaluate(()=>held.project);
    assert.equal(renamed.brief.title,'Synthetic rolling restarts');
    assert.equal(renamed.approval.carried.from_revision,approvedAt,'The approval names the revision the person approved');
    assert(renamed.stories.length&&renamed.scene,'A rename clears nothing');
    assert.equal(await page.evaluate(()=>document.activeElement.dataset.key),'ig-edit-brief');
    assert.equal(await page.locator('#title').innerText(),'Synthetic rolling restarts');
    await page.getByRole('heading',{name:'Approved revision '+renamed.revision+': prepare its files',exact:true}).waitFor();
    await page.getByRole('button',{name:'Download PDF (earlier approved)',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Update preview',exact:true}).count(),0);
    await page.locator('#actions').getByRole('button',{name:'Prepare approved files',exact:true}).click();
    await page.getByRole('heading',{name:'Approved delivery',exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>held.history[0].summary),'Renamed to “Synthetic rolling restarts”');
    // Every route that changes sources asks first, names what it clears, and Cancel or Escape
    // changes nothing and returns focus to the control that started it.
    const atRevision=await page.evaluate(()=>held.project.revision);
    await page.getByText('Sources and facts',{exact:true}).click();
    await page.getByRole('button',{name:'Add or update supplied information',exact:true}).click();
    await page.getByLabel('New or replacement supplied information',{exact:true}).fill('Synthetic replacement notes.');
    await page.getByRole('button',{name:'Save supplied information',exact:true}).click();
    const pasted=page.getByRole('dialog',{name:'Add supplied information'});
    await pasted.getByText(/^This clears this infographic’s facts, story, page and approval\. Earlier work stays in History\./).waitFor();
    await pasted.getByRole('button',{name:'Cancel',exact:true}).click();
    assert.equal(await page.evaluate(()=>held.project.revision),atRevision,'Cancel changes nothing');
    assert.equal(await page.evaluate(()=>document.activeElement.dataset.key),'ig-source-update');
    await page.getByRole('button',{name:'Add or update supplied information',exact:true}).click();
    await page.getByLabel('Or upload a source file',{exact:true}).setInputFiles({name:'more.md',mimeType:'text/markdown',buffer:Buffer.from('More synthetic notes.')});
    await page.getByRole('dialog').getByText('More synthetic notes.',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Save supplied information',exact:true}).click();
    await page.getByRole('dialog',{name:'Add more.md'}).getByText(/^This clears this infographic’s facts, story, page and approval\./).waitFor();
    await page.keyboard.press('Escape');
    assert.equal(await page.evaluate(()=>held.project.revision),atRevision,'Escape changes nothing');
    assert.equal(await page.evaluate(()=>document.activeElement.dataset.key),'ig-source-update');
    // Studio material, a Google Doc or page, and research all import through one reviewed capture.
    await page.evaluate(()=>sourceImportSheet({id:'synthetic_capture',name:'Synthetic material',characters:19,excerpt:'Synthetic material.',warnings:[],readable:true},'','ig-source-material'));
    await page.getByRole('button',{name:'Import this capture',exact:true}).click();
    await page.getByRole('dialog',{name:'Add Synthetic material'}).getByRole('button',{name:'Cancel',exact:true}).click();
    assert.equal(await page.evaluate(()=>held.project.revision),atRevision);
    assert.equal(await page.evaluate(()=>document.activeElement.dataset.key),'ig-source-material');
    // A brief change that affects the story asks first; Cancel changes nothing.
    await page.getByText('Brief and requirements',{exact:true}).click();
    await page.getByRole('button',{name:'Edit brief',exact:true}).click();
    await page.getByLabel('Audience',{exact:true}).fill('Site reliability engineers');
    await page.getByRole('button',{name:'Save brief',exact:true}).click();
    const briefAsks=page.getByRole('dialog',{name:'Save the brief'});
    await briefAsks.getByText(/^This clears this infographic’s story, page and approval\. Captured facts stay\. Earlier work stays in History\./).waitFor();
    if(output)await page.screenshot({path:path.join(output,'brief-confirm-desktop.png')});
    await briefAsks.getByRole('button',{name:'Cancel',exact:true}).click();
    assert.deepEqual(await page.evaluate(()=>[held.project.revision,held.project.brief.audience]),[atRevision,'Technical practitioners']);
    assert.equal(await page.evaluate(()=>document.activeElement.dataset.key),'ig-edit-brief');
    const approvedFiles=await page.evaluate(()=>held.deliveries.find(d=>d.approved_current).files.map(f=>f.sha256));
    await page.getByRole('button',{name:'Edit brief',exact:true}).click();
    await page.getByLabel('Audience',{exact:true}).fill('Site reliability engineers');
    await page.getByRole('button',{name:'Save brief',exact:true}).click();
    await briefAsks.getByRole('button',{name:'Save brief',exact:true}).click();
    await page.getByText('Brief saved. Find the story again when you’re ready.',{exact:true}).waitFor();
    const cleared=await page.evaluate(()=>({p:held.project,summary:held.history[0].summary,files:held.deliveries.find(d=>!d.draft&&d.files).files.map(f=>f.sha256)}));
    assert.deepEqual([cleared.p.stories.length,cleared.p.scene,cleared.p.approval],[0,null,null]);
    assert(cleared.p.facts.length,'Captured facts stay');
    assert.equal(cleared.summary,'Edited the brief: audience; cleared the story, page and approval');
    assert.deepEqual(cleared.files,approvedFiles,'Earlier approved files stay unchanged');
    // With no page, the card names the earlier page and the toolbar's next step.
    await page.getByRole('heading',{name:/^Earlier page \(revision \d+\)$/}).waitFor();
    await page.getByText('Your current work, revision '+cleared.p.revision+', has no page yet. Find the story and build the page again to edit or approve it.',{exact:true}).waitFor();
    await page.locator('#actions').getByRole('button',{name:'Find the story',exact:true}).waitFor();
    await page.getByRole('button',{name:'Download PDF (earlier approved)',exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Update preview',exact:true}).count(),0);
    for(const colorScheme of ['light','dark']){
      await page.setViewportSize({width:390,height:844});await page.emulateMedia({colorScheme});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow on the earlier page at 390 '+colorScheme);
      if(output){await page.getByRole('heading',{name:/^Earlier page/}).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(output,'earlier-page-'+colorScheme+'.png')});}
    }
    await page.emulateMedia({colorScheme:'light'});
    // Add from library: Cancel changes nothing; Use selected makes the document a source and
    // returns focus to Add from library. Nothing is started.
    await page.setViewportSize({width:390,height:844});
    const sourcesAt=await page.evaluate(()=>held.project.sources.length);
    await page.getByText('Sources and facts',{exact:true}).click();
    await page.getByRole('button',{name:'Add from library',exact:true}).click();
    const sheet=page.getByRole('dialog',{name:'Add from library'});
    await sheet.getByRole('checkbox',{name:'Select Synthetic capacity notes'}).waitFor();
    // This infographic's own kept export is listed as unavailable, never as a source.
    await sheet.getByText('Choose documents for this infographic only.',{exact:false}).waitFor();
    assert(await sheet.getByRole('checkbox',{name:'Synthetic rolling restarts is unavailable: This infographic'}).isDisabled());
    await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('dialog',{name:'Add from library'}).count(),0);
    assert.equal(await page.evaluate(()=>held.project.sources.length),sourcesAt,'Cancel changes nothing');
    await page.getByRole('button',{name:'Add from library',exact:true}).click();
    await sheet.getByRole('checkbox',{name:'Select Synthetic capacity notes'}).click();
    await sheet.getByRole('checkbox',{name:'Selected: Synthetic capacity notes'}).waitFor();
    await sheet.getByRole('button',{name:'Use selected',exact:true}).click();
    // This infographic still has its captured facts: it asks before clearing them.
    const confirm=page.getByRole('dialog',{name:'Add Synthetic capacity notes'});
    await confirm.getByText(/^This clears this infographic’s facts\. Earlier work stays in History\./).waitFor();
    assert.equal(await page.evaluate(()=>held.project.sources.length),sourcesAt,'Nothing changes before Add as sources');
    await confirm.getByRole('button',{name:'Add as sources',exact:true}).click();
    await page.getByText(/^The document is a source now\./).waitFor();
    assert.equal(await page.evaluate(()=>held.project.sources.length),sourcesAt+1);
    await page.getByText('From the Document Library (Marketing Studio), revision 1.',{exact:true}).waitFor();
    assert.equal(await page.evaluate(()=>document.activeElement.dataset.key),'ig-library-add');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    const cdp=await page.context().newCDPSession(page);await cdp.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'},{name:'prefers-reduced-motion',value:'reduce'}]});
    assert.equal(await page.locator('.toolbar').evaluate(n=>getComputedStyle(n).backdropFilter),'none');
    await page.getByRole('button',{name:'Infographics',exact:true}).first().click();
    await page.getByRole('button',{name:'New infographic',exact:true}).click();
    await page.getByLabel('Working title',{exact:true}).fill('Retained intake');
    await page.keyboard.press('Tab');assert(await page.getByRole('dialog').evaluate(n=>n.contains(document.activeElement)));
    await page.keyboard.press('Escape');await page.getByRole('button',{name:'New infographic',exact:true}).click();
    assert.equal(await page.getByLabel('Working title',{exact:true}).inputValue(),'Retained intake');
    // A new infographic starts with no library documents; one chosen here waits for Save brief.
    assert.equal(await page.getByText('It becomes a source when you save the brief.',{exact:false}).count(),0);
    await page.getByRole('button',{name:'Add from library',exact:true}).click();
    const picker=page.getByRole('dialog',{name:'Add from library'});
    await picker.getByRole('checkbox',{name:'Select Synthetic capacity notes'}).click();
    await picker.getByText('1 selected',{exact:true}).waitFor();
    await picker.getByRole('button',{name:'Use selected',exact:true}).click();
    await page.getByRole('heading',{name:'Synthetic capacity notes',exact:true}).waitFor();
    assert.equal(await page.getByLabel('Working title',{exact:true}).inputValue(),'Retained intake');
    await page.keyboard.press('Escape');
    assert.deepEqual(errors,[],'Browser runtime errors');
    console.log('PASS: phone intake → source-backed story → actual render → focused edit → pixel review → checks → approval → SVG download → kept in the Document Library; history comparison; a rename that keeps the approval; source and brief changes that ask first; the earlier page card; this infographic’s own export unavailable in Add from library; Add from library on the desk and a new brief; 320/390/1280 light/dark/reduced-motion; no browser errors or horizontal overflow. Providers are injected.');
  }catch(f){console.error(JSON.stringify({browser_errors:errors,text:page?await page.locator('body').innerText():''}));if(page&&process.env.INFOGRAPHIC_UI_RESULTS)await page.screenshot({path:path.join(process.env.INFOGRAPHIC_UI_RESULTS,'failure.png'),fullPage:true});throw f;}finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>{const timer=setTimeout(()=>{child.kill('SIGKILL');resolve();},5000);child.once('exit',()=>{clearTimeout(timer);resolve();});});}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
