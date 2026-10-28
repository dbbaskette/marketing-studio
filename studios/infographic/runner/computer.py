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
    capability = report(agent, installed=command(agent) is not None,
                        credential_present=bool(environ.get('GEMINI_API_KEY')) if agent == 'claude' else False)
    model_configured = bool(chosen['native'].get('gemini_model')) if agent == 'claude' else True
    if not model_configured:
        capability['problems'].append('gemini-model-required')
        capability['state'] = 'unavailable'
    renderer = chosen.get('renderer')
    renderer_available = bool(renderer and Path(renderer).is_file() and os.access(renderer, os.X_OK))
    return {**capability, 'generation_started': False,
            'model_configured': model_configured,
            'renderer_configured': bool(chosen.get('renderer')),
            'renderer_available': renderer_available,
            'disclosure': ('Uses existing Codex sign-in and account usage. No separate image API key is requested.' if agent == 'codex'
                           else 'Claude Code plans and inspects; Gemini image generation/editing uses separate API usage. Configure GEMINI_API_KEY in the server launch environment, not in this page.')}
