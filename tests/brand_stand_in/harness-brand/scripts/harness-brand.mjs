#!/usr/bin/env node
// A stand-in Harness Brand for Marketing Studio's tests: version, brands and the pack
// commands, answered by stand_in.py beside this skill folder. It has made-up brands only.
import { spawnSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const done = spawnSync(process.env.STAND_IN_PYTHON || 'python3',
  [join(here, '..', '..', 'stand_in.py'), ...process.argv.slice(2)], { stdio: 'inherit' });
process.exit(done.status ?? 1);
