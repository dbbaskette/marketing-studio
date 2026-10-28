"""Non-billable, non-secret local prerequisites; never a generation/access attestation."""
import os
from studio_core import runtime
from . import settings
from .provider_capabilities import report


def inspect(*, chosen=None, command=runtime.assistant_command, environ=None):
    chosen = chosen or settings.snapshot()
    environ = os.environ if environ is None else environ
    agent = chosen['assistant']['agent']
    capability = report(agent, installed=command(agent) is not None,
                        credential_present=bool(environ.get('GEMINI_API_KEY')) if agent == 'claude' else False)
    return {**capability, 'generation_started': False,
            'model_configured': bool(chosen['native'].get('gemini_model')) if agent == 'claude' else True,
            'renderer_configured': bool(chosen.get('renderer')),
            'disclosure': ('Uses existing Codex sign-in and included usage. No separate image API key is requested.' if agent == 'codex'
                           else 'Claude Code plans and inspects; Gemini image generation/editing uses separate API usage. Configure GEMINI_API_KEY in the server launch environment, not in this page.')}
