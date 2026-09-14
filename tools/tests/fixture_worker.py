"""Tiny subprocess fixture; never builds or mutates the real game."""
import json
import os
from pathlib import Path
import shutil
import sys
import time

job = Path(os.environ['PIRATE_BUILD_JOB'])
root = Path(os.environ['PIRATE_BUILD_ROOT'])
mode = sys.argv[1]
(root / 'worker-ready').write_text(str(os.getpid()))
if mode == 'hold':
    while True:
        time.sleep(0.1)
if mode == 'fail':
    print('intentional build failure', flush=True)
    sys.exit(17)
package = job / 'package'
package.mkdir()
if mode != 'invalid':
    shutil.copytree(root / 'static', package, dirs_exist_ok=True)
    (package / '_app/immutable').mkdir(parents=True)
    (package / '_app/immutable/app.js').write_text('console.log("valid");')
    (package / '_app/version.json').write_text(json.dumps({'version': job.name}))
    (package / 'index.html').write_text('<!doctype html><h1>valid</h1>')
    (package / 'service-worker.js').write_text('// service worker')
if mode == 'symbols':
    (job / 'compiler.js.map').write_text('{"version":3}')
if mode == 'verbose':
    sys.stdout.write('a' * (2 * 1024 * 1024) + '\nLOG-END\n')
print('fixture complete', flush=True)
