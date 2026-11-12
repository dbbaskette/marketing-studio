"""Non-billable, non-secret local prerequisites; never a generation/access attestation."""
import os
from pathlib import Path
from studio_core import runtime
from . import settings
from .provider_capabilities import report


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
    renderer_available = bool(renderer and Path(renderer).is_file() and os.access(renderer, os.X_OK))
    return {**capability, 'generation_started': False,
            'model_configured': model_configured,
            'renderer_configured': bool(chosen.get('renderer')),
            'renderer_available': renderer_available,
            'disclosure': ('Pictures are drawn by Codex, under your Codex sign-in and account usage. No separate image API key is needed.' if not gemini
                           else 'Pictures are drawn by Gemini, billed to your Gemini API key. Choose the model and save the key in Marketing Studio, Shared settings, Document graphics.')}
