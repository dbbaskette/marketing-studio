"""Disposable, private derived-data cache; never a source of remote freshness."""
import json
import os
from pathlib import Path
import re
import time
import uuid

MAX_ENTRIES = 128
MAX_BYTES = 32 * 1024 * 1024
MAX_ENTRY = 2 * 1024 * 1024
MAX_AGE = 30 * 24 * 3600


def folder(root):
    import studio
    path = studio.inside(root, '.derived-cache')
    if path.is_symlink(): raise ValueError('Cache must not be a symlink.')
    return path


def entries(root):
    directory = folder(root)
    if not directory.exists(): return []
    return [p for p in directory.iterdir() if re.fullmatch(r'[0-9a-f]{64}\.json', p.name) and not p.is_symlink() and p.is_file()]


def maintain(root, clear=False):
    rows = sorted(entries(root), key=lambda p:p.stat().st_mtime, reverse=True)
    total = count = 0
    for path in rows:
        stat = path.stat()
        if clear or time.time()-stat.st_mtime > MAX_AGE or count >= MAX_ENTRIES or total+stat.st_size > MAX_BYTES:
            path.unlink(missing_ok=True)
        else:
            total += stat.st_size;count += 1
    return {'entries':count,'bytes':total,'scope':'local derived data only','removed_all':clear}


def key_for(namespace, inputs):
    import studio
    return studio.digest(json.dumps({'namespace':namespace,'inputs':inputs}, sort_keys=True).encode())


def get(root, key):
    import studio
    path = folder(root)/(key+'.json')
    if path.is_symlink() or not path.is_file(): return None
    try:
        stat = path.stat()
        if stat.st_size > MAX_ENTRY or time.time()-stat.st_mtime > MAX_AGE: return None
        record = json.loads(path.read_text())
        if record.get('schema') != 1 or record.get('key') != key: return None
        value = record['value']
        if record['sha256'] != studio.digest(json.dumps(value,sort_keys=True).encode()): return None
        return value
    except (OSError, ValueError, TypeError, KeyError, AttributeError): return None


def put(root, key, value):
    import studio
    data = json.dumps({'schema':1,'key':key,'value':value,
                      'sha256':studio.digest(json.dumps(value,sort_keys=True).encode())}).encode()
    if len(data) > MAX_ENTRY: return
    directory = folder(root);directory.mkdir(mode=0o700, exist_ok=True);directory.chmod(0o700)
    temporary = directory/('.'+uuid.uuid4().hex+'.tmp')
    try:
        fd = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream: stream.write(data)
        os.replace(temporary,directory/(key+'.json'))
        maintain(root)
    finally: temporary.unlink(missing_ok=True)


def reuse(root, namespace, inputs, compute):
    key = key_for(namespace, inputs)
    value = get(root,key)
    if value is not None: return value, True
    # Exceptions, unavailable results and model verdicts are never cached here.
    value = compute()
    put(root,key,value)
    return value, False
