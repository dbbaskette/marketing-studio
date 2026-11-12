"""Non-billable, non-secret local prerequisites; never a generation/access attestation."""
import os
from pathlib import Path
from studio_core import runtime
from . import settings
from .provider_capabilities import report


# Where other tools on this computer keep a Chromium headless shell. Nothing is downloaded or
# installed here: a path is only offered, and used once the person chooses it in Settings.
SHELLS = ('.cache/hyperframes/chrome/chrome-headless-shell/*/*/chrome-headless-shell',
          'Library/Caches/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell',
          '.cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell',
          '.cache/puppeteer/chrome-headless-shell/*/*/chrome-headless-shell')


def usable(path):
    return bool(path and Path(path).is_file() and os.access(path, os.X_OK))


def found_renderers(home=None):
    """Headless shells already on this computer, newest first, three at most."""
    home, found = Path(home) if home else Path.home(), []
    for pattern in SHELLS:
        try:
            found += [path for path in home.glob(pattern) if usable(path)]
        except OSError:
            continue
    def age(path):
        try: return path.stat().st_mtime
        except OSError: return 0
    return [str(path) for path in sorted(found, key=age, reverse=True)[:3]]


def inspect(*, chosen=None, command=runtime.assistant_command, environ=None):
    chosen = chosen or settings.snapshot()
    environ = os.environ if environ is None else environ
    agent = chosen['assistant']['agent']
    # Who draws is the shared Document graphics choice, which need not be the assistant.
    provider = chosen.get('image_provider') or ('codex' if agent == 'codex' else 'gemini')
    gemini = provider == 'gemini'
    from studio_core import graphics
    capability = report('claude' if gemini else 'codex',
                        installed=command('claude' if gemini and agent == 'claude' else 'codex' if not gemini else agent) is not None,
                        credential_present=bool(graphics.key(environ)) if gemini else False)
    capability['assistant'] = 'Codex' if agent == 'codex' else 'Claude Code'
    model_configured = bool(chosen.get('image_model') or chosen['native'].get('gemini_model')) if gemini else True
    if not model_configured:
        capability['problems'].append('gemini-model-required')
        capability['state'] = 'unavailable'
    renderer = chosen.get('renderer')
    renderer_available = usable(renderer)
    return {**capability, 'generation_started': False,
            'model_configured': model_configured,
            'renderer_configured': bool(chosen.get('renderer')),
            'renderer_available': renderer_available,
            'renderer_found': [] if renderer_available else found_renderers(),
            'disclosure': ('Pictures are drawn by Codex, under your Codex sign-in and account usage. No separate image API key is needed.' if not gemini
                           else 'Pictures are drawn by Gemini, billed to your Gemini API key. Choose the model and save the key in Marketing Studio, Shared settings, Document graphics.')}
