#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
python="${1:-python3}"
"$python" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ is required"'
"$python" -m compileall -q marketing_studio
node --check marketing_studio/web/app.js
"$python" -m unittest discover -s tests -v
