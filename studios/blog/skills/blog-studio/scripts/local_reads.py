"""Bounded local reads reused only within an explicit, synchronous operation."""
from contextlib import contextmanager
from contextvars import ContextVar

_active = ContextVar('blog_studio_local_reads', default=None)
MAX_BYTES = 32 * 1024 * 1024
MAX_FILES = 512


@contextmanager
def operation():
    token = _active.set({})
    try: yield
    finally: _active.reset(token)


def signature(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def read(path):
    cache = _active.get()
    if cache is None: return path.read_bytes()
    key = str(path.resolve());before=signature(path)
    previous=cache.get(key)
    if previous and previous[0]==before: return previous[1]
    data=path.read_bytes()
    # Concurrent replacements are not eligible for reuse. Next access reads again.
    if signature(path)!=before:
        cache.pop(key,None)
        return data
    if len(cache)>=MAX_FILES or sum(len(v[1]) for v in cache.values())+len(data)>MAX_BYTES:
        cache.clear()
    if len(data)<=MAX_BYTES:cache[key]=(before,data)
    return data
