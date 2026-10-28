"""Short worker-marker transactions shared by the two deck Studio engines."""


def mark_step(engine, root, relative, step=None):
    """Protect canonical output from replay without holding a lock over rendering."""
    share = False
    with engine.files:
        marker = root / relative
        if step is None:
            marker.unlink(missing_ok=True)
            engine._active_steps.discard(str(root))
            share = engine._deferred_share and not engine._active_steps
            if share:
                engine._deferred_share = False
        else:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(f'{step}\n', encoding='utf-8')
            engine._active_steps.add(str(root))
    if share:
        engine.share_soon()


def defer_share(engine):
    """Retry final automatic sharing after this engine's canonical writes finish."""
    with engine.files:
        if engine._active_steps:
            engine._deferred_share = True
            return True
    return False
