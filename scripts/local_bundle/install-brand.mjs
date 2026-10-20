import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { readFile, appendFile } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
const [source, home, target, action] = process.argv.slice(2);
const {planShared, activateShared} = await import(pathToFileURL(join(source,'scripts/lib/shared-install.mjs')));
const {personalTargets} = await import(pathToFileURL(join(source,'scripts/lib/install-targets.mjs')));
const sharedRoot = join(home,'Library/Application Support/Tanzu Brand');
const current = join(sharedRoot,'current');
const targets = personalTargets(home,join(home,'.claude')).filter(item => target === 'both' || item.agent === (target === 'claude' ? 'claude-code' : 'codex'));
const incoming = JSON.parse(await readFile(join(source,'package.json'),'utf8')).version;
let installed;
try { installed = JSON.parse(await readFile(join(current,'package.json'),'utf8')).version; } catch {}
const numbers = version => version.split('.').map(Number);
if (installed && numbers(installed).some((n,i) => n > numbers(incoming)[i] && numbers(installed).slice(0,i).every((v,j) => v === numbers(incoming)[j]))) {
  console.log(JSON.stringify({current,status:'kept newer brand'}));
} else {
  const plan = await planShared({sourceRoot:source,targets,sharedRoot});
  if (plan.needsReplacement) throw new Error('Existing unrelated brand folders need explicit migration; this offline bundle preserves them.');
  if(action === 'install') {
    const exec = promisify(execFile);
    await activateShared(plan,{log:()=>{},verify:async root => {
      const args = [join(root,'scripts/audit-brand.mjs'),'--self'];
      const log = async text => {
        if(process.env.STUDIO_INSTALL_LOG) {
          await appendFile(process.env.STUDIO_INSTALL_LOG, `\n${new Date().toISOString()} [pid ${process.pid}] ${text}\n`);
        }
      };
      await log('Run: ' + JSON.stringify([process.execPath,...args]));
      try {
        const result = await exec(process.execPath,args,{timeout:60000});
        await log(result.stdout + result.stderr + '\nCommand finished: exit 0');
      } catch(error) {
        await log((error.stdout || '') + (error.stderr || '') + '\nCommand failed: ' + (error.signal || error.code));
        throw error;
      }
    }});
  }
  console.log(JSON.stringify({current,status:action === 'install' ? 'installed' : 'planned'}));
}
