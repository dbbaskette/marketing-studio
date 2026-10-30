/* Shared content checkpoint, actual phone/desktop DOM; synthetic HTTP adapter only. */
const {chromium}=require('playwright');
const {createServer}=require('node:http');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const root=path.join(__dirname,'..'),calls=[];
 const server=createServer((req,res)=>{
  if(req.url==='/style.css'||req.url==='/drafting.js'){res.setHeader('Content-Type',req.url.endsWith('css')?'text/css':'text/javascript');res.end(fs.readFileSync(path.join(root,'ui-kit',req.url.slice(1))));return;}
  if(req.url==='/decision'){let text='';req.on('data',b=>text+=b);req.on('end',()=>{calls.push(JSON.parse(text));res.setHeader('Content-Type','application/json');res.end('{}');});return;}
  res.setHeader('Content-Type','text/html');res.end(`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/style.css"></head><body><main style="max-width:900px;margin:auto;padding:16px;box-sizing:border-box"><h1>Synthetic slide text</h1><div id="review"></div></main><script src="/drafting.js"></script><script>
   document.getElementById('review').append(Drafting.slideContent({slides:[{title:'Restart instances one at a time',points:[{label:'Keep serving',text:'Other instances serve requests during the restart.'}],notes:'Explain the sequence and ask learners which instance serves the next request.'},{title:'Check what you can explain',points:[{text:'Which instance serves the next request?'}],notes:'Invite a learner response before revealing the answer.'}],onDecision:async(kind,note)=>{await fetch('/decision',{method:'POST',body:JSON.stringify({kind,note})});}}));
  </script></body></html>`);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
 try{
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  for(const width of [390,1280]){
   const page=await browser.newPage({viewport:{width,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto('http://127.0.0.1:'+server.address().port);
   assert.equal(calls.length,0,'Reading the text starts no request');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
   await page.getByRole('button',{name:'Ask for changes',exact:true}).click();
   assert.equal(calls.length,0,'Changes require a note');
   await page.getByLabel('Changes to slide text').fill('Shorten the first slide.');
   await page.getByRole('button',{name:'Ask for changes',exact:true}).click();
   await page.waitForFunction(()=>!document.querySelector('textarea').disabled);
   assert.deepEqual(calls.pop(),{kind:'changes',note:'Shorten the first slide.'});
   if(process.env.SLIDE_TEXT_UI_RESULTS){fs.mkdirSync(process.env.SLIDE_TEXT_UI_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.SLIDE_TEXT_UI_RESULTS,'slide-text-'+width+'.png'),fullPage:true});}
   await page.getByRole('button',{name:'Approve text & design deck',exact:true}).click();
   await page.waitForFunction(()=>!document.querySelector('textarea').disabled);
   assert.deepEqual(calls.pop(),{kind:'approve',note:null});assert.deepEqual(errors,[]);
   await page.close();
  }
  console.log('PASS shared slide-text phone and desktop view, explicit changes/approval, no request on read');
 }finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
