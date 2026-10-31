/* Can open before launch; running state refreshes independently without disturbing forms. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const renderer=process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER;
 if(!renderer)throw Error('Supply the installed renderer.');
 const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'fixture_server.py'),'--renderer',renderer,'--suite'],{stdio:['ignore','pipe','pipe']});
 let browser;
 try{
  const url=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);child.stdout.on('data',b=>{out+=b;if(out.startsWith('http://')&&out.includes('\n')){clearTimeout(timer);resolve(out.split('\n')[0]);}});child.once('exit',()=>reject(Error('Fixture stopped')));});
  browser=await chromium.launch({headless:true,executablePath:renderer});
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.setDefaultTimeout(10000);
  let blogRunning=false,reachable=true,requests=0;
  await page.route('**/api/home',async route=>{
   requests++;if(!reachable){await route.abort();return;}
   const response=await route.fetch();const body=await response.json();
   for(const studio of body.studios){studio.readiness={state:'done',label:'Can open',detail:'Synthetic local prerequisites available; no sign-in check.',action:null};studio.running=studio.id==='blog'&&blogRunning;}
   await route.fulfill({response,json:body});
  });
  await page.goto(url);
  await page.getByRole('button',{name:'Open Infographic Studio',exact:true}).waitFor();
  assert.equal(await page.locator('.studio-readiness .bead[data-state="done"]').count(),4);
  // The home says Can open on each card, with its reason in words rather than a tooltip.
  const cardLabels=()=>page.locator('.studio-readiness .state').allTextContents();
  assert.deepEqual(await cardLabels(),Array(4).fill('Can open'));
  assert.equal(await page.getByText('Synthetic local prerequisites available; no sign-in check.',{exact:true}).count(),4);
  const before=requests;blogRunning=true;
  await page.getByRole('button',{name:'Return to Blog Studio',exact:true}).waitFor({timeout:10000});
  assert(requests>before,'Running state should refresh without opening a studio');
  blogRunning=false;await page.getByRole('button',{name:'Open Blog Studio',exact:true}).waitFor({timeout:10000});
  assert.equal(await page.locator('.studio-readiness .bead[data-state="done"]').count(),4,'Stopped studios remain locally ready');
  await page.getByRole('button',{name:'Shared settings',exact:true}).click();
  await page.locator('#person-name').fill('Unsaved synthetic name');
  await page.waitForTimeout(5200);assert.equal(await page.locator('#person-name').inputValue(),'Unsaved synthetic name');
  await page.getByRole('button',{name:'Studios',exact:true}).click();
  // Unreachable: every card says Not checked in words, and no green light is left behind.
  reachable=false;await page.locator('.studio-readiness').getByText('Not checked',{exact:true}).first().waitFor({timeout:10000});
  assert.deepEqual(await cardLabels(),Array(4).fill('Not checked'));
  assert.equal(await page.locator('.studio-readiness .bead[data-state="done"]').count(),0);
  assert.equal(await page.getByText(/Marketing Studio did not answer/).count(),4);
  reachable=true;await page.locator('.studio-readiness').getByText('Can open',{exact:true}).first().waitFor({timeout:10000});
  assert.deepEqual(await cardLabels(),Array(4).fill('Can open'));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
  console.log('PASS: four Can open cards before launch; running/stopped state refresh without opening; unsaved settings retained; stale green cleared to Not checked and recovered; phone layout.');
 }finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>{const t=setTimeout(()=>{child.kill('SIGKILL');resolve();},5000);child.once('exit',()=>{clearTimeout(t);resolve();});});}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
