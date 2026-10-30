/* Real phone UI and helper acceptance; entirely synthetic authors and source text. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const renderer=process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER,runtime=process.env.STUDIO_TEST_RESEARCH_RUNTIME;
 if(!renderer||!runtime)throw Error('Use explicitly prepared pinned renderer and research runtime.');
 const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'fixture_server.py'),'--renderer',renderer,'--research-runtime',runtime],{stdio:['ignore','pipe','pipe']});
 let browser,diagnostic='';child.stderr.on('data',b=>diagnostic+=b);
 try{
  const url=await new Promise((resolve,reject)=>{let data='';const timer=setTimeout(()=>reject(Error('Fixture timed out '+diagnostic)),15000);child.stdout.on('data',b=>{data+=b;if(data.includes('\n')){clearTimeout(timer);resolve(data.split('\n')[0]);}});child.on('exit',c=>{clearTimeout(timer);reject(Error('Fixture exited '+c+' '+diagnostic));});});
  browser=await chromium.launch({headless:true,executablePath:renderer});
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto(url);
  await page.getByRole('button',{name:'New infographic',exact:true}).click();
  await page.getByLabel('Working title',{exact:true}).fill('Synthetic researched infographic');
  await page.getByLabel('Research this topic first',{exact:true}).check();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByLabel('Audience and prior knowledge',{exact:true}).fill('Synthetic learners');
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('button',{name:'Save brief',exact:true}).click();
  await page.getByRole('heading',{name:'Research this topic',exact:true}).waitFor();
  assert.equal((await page.evaluate(()=>request('/api/fixture-calls'))).calls.length,0);
  assert.equal(await page.getByLabel('Search for additional external sources',{exact:true}).isChecked(),false);
  await page.getByRole('button',{name:'Paste text',exact:true}).click();
  await page.getByLabel('Source text',{exact:true}).fill('One instance restarts while the others serve.');
  await page.getByRole('button',{name:'Add text',exact:true}).click();
  await page.getByText('Pasted notes',{exact:true}).first().waitFor();
  await page.getByRole('button',{name:'Start research',exact:true}).click();
  await page.getByRole('button',{name:'Use research',exact:true}).waitFor({timeout:45000});
  assert.equal(await page.locator('.research-agent-count').innerText(),'0');
  await page.getByText('All agents finished',{exact:true}).waitFor();
  assert.deepEqual((await page.evaluate(()=>request('/api/fixture-calls'))).calls,['investigate','synthesize','review']);
  assert.equal(await page.evaluate(()=>held.project.sources.length),0,'Research is not automatically imported');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Phone view must not overflow');
  if(process.env.INFOGRAPHIC_UI_RESULTS){fs.mkdirSync(process.env.INFOGRAPHIC_UI_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.INFOGRAPHIC_UI_RESULTS,'shared-research-phone.png')});}
  await page.getByRole('button',{name:'Use research',exact:true}).click();
  await page.getByRole('heading',{name:'Review captured information',exact:true}).waitFor();
  await page.getByRole('button',{name:'Import this capture',exact:true}).click();
  await page.waitForFunction(()=>held.project.sources.length===1);
  assert.equal(await page.evaluate(()=>held.project.stories.length),0,'Research must not start story or image generation');
  assert.deepEqual((await page.evaluate(()=>request('/api/fixture-calls'))).calls,['investigate','synthesize','review']);
  assert.deepEqual(errors,[]);console.log('PASS shared research phone journey: topic-only brief, selected capture, independent review, explicit preview/import, no image work');
 }finally{if(browser)await browser.close();child.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
