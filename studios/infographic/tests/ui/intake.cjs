/* Multiple local files, extraction preview and explicit gaps; no account/provider jobs. */
const {chromium} = require('playwright');
const {spawn, spawnSync} = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');
(async () => {
  const renderer = process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER;
  if (!renderer) throw Error('Supply the installed test renderer.');
  const python = process.env.PYTHON || 'python3';
  const made = spawnSync(python, ['-c', `import base64,io,zipfile
b=io.BytesIO()
with zipfile.ZipFile(b,'w') as z:
 z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>One instance restarts while the others serve.</w:t></w:r></w:p><w:p><w:r><w:drawing/></w:r></w:p></w:body></w:document>')
print(base64.b64encode(b.getvalue()).decode())`], {encoding:'utf8'});
  assert.equal(made.status, 0);
  const child = spawn(python, [path.join(__dirname,'fixture_server.py'),'--renderer',renderer,'--bridge'], {stdio:['ignore','pipe','pipe']});
  let browser;
  try {
    const url = await new Promise((resolve,reject) => {
      let output=''; const timer=setTimeout(()=>reject(Error('Fixture startup timed out')),15000);
      child.stdout.on('data',data=>{output+=data;if(output.startsWith('http://')&&output.includes('\n')){clearTimeout(timer);resolve(output.split('\n')[0]);}});
      child.once('exit',()=>{clearTimeout(timer);reject(Error('Fixture startup failed'));});
    });
    browser=await chromium.launch({headless:true,executablePath:renderer});
    const page=await browser.newPage({viewport:{width:390,height:844}}), errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);
    await page.getByRole('button',{name:'New infographic',exact:true}).click();
    await page.getByLabel('Working title',{exact:true}).fill('Synthetic supplied documents');
    await page.getByLabel('Upload files — text, Markdown, CSV, PDF, Word or HTML',{exact:true}).setInputFiles([
      {name:'synthetic.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:Buffer.from(made.stdout.trim(),'base64')},
      {name:'notes.md',mimeType:'text/markdown',buffer:Buffer.from('The supplied service continues serving.\n')},
      {name:'larger.txt',mimeType:'text/plain',buffer:Buffer.from('Synthetic readable material. '.repeat(2500))}
    ]);
    await page.getByRole('heading',{name:'synthetic.docx',exact:true}).waitFor();
    await page.getByRole('heading',{name:'notes.md',exact:true}).waitFor();
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByText('Review the file previews and acknowledge readable-only coverage, or remove unreadable files.',{exact:true}).waitFor();
    await page.getByRole('checkbox',{name:'I reviewed these gaps. Use only the readable text.',exact:true}).check();
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByRole('button',{name:'Save brief',exact:true}).click();
    await page.getByRole('heading',{name:'Find a useful story',exact:true}).waitFor();
    const snapshot=await page.evaluate(async()=>{
      const headers={'X-Infographic-Studio-Token':sessionStorage.getItem('infographic-studio-token')};
      const list=await (await fetch('/api/projects',{headers})).json();
      return (await (await fetch('/api/project?id='+encodeURIComponent(list.projects[0].id),{headers})).json()).project;
    });
    assert.deepEqual(snapshot.sources.map(s=>s.kind),['docx','markdown','text']);
    assert(snapshot.sources[0].coverage.acknowledged);
    assert.equal(snapshot.approval,null);
    await page.getByText('Sources and facts',{exact:true}).click();
    await page.getByRole('button',{name:'Review synthetic.docx',exact:true}).click();
    await page.getByRole('dialog').getByText('One instance restarts while the others serve.',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Done',exact:true}).click();
    await page.getByRole('button',{name:'Add or update supplied information',exact:true}).click();
    await page.getByLabel('Source to replace (leave empty to add another)',{exact:true}).selectOption(snapshot.sources[0].id);
    await page.getByLabel('Or upload a source file',{exact:true}).setInputFiles({name:'updated.md',mimeType:'text/markdown',buffer:Buffer.from('Updated supplied text.')});
    await page.getByRole('dialog').getByText('Updated supplied text.',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Save supplied information',exact:true}).click();
    await page.getByRole('heading',{name:'Find a useful story',exact:true}).waitFor();
    assert.deepEqual(errors,[]);
    console.log('PASS: phone LAN bridge multi-file Word/Markdown/text upload beyond 64 KB, coverage previews, gap acknowledgment, exact saved captures, no approval or provider work.');
  } finally {
    if(browser)await browser.close();
    child.kill('SIGTERM');
    await new Promise(resolve=>{const timer=setTimeout(()=>{child.kill('SIGKILL');resolve();},5000);child.once('exit',()=>{clearTimeout(timer);resolve();});});
  }
})().catch(()=>{console.error('FAIL: synthetic document intake browser journey. Private URLs are not logged.');process.exitCode=1;});
