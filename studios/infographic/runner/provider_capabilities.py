"""Non-billable capability decisions and proposed confined image command contracts.

These helpers do not run assistants, inspect credentials, or contact providers.
Local feature discovery is not evidence of account access or successful generation.
"""
from __future__ import annotations

from pathlib import Path

CODEX_BASELINE = '0.162.1'
CLAUDE_BASELINE = '2.1.303'
# Keep the shared text workers unchanged. This list applies only to a future native
# image job, and deliberately leaves image_generation out of the disabled features.
CODEX_DISABLED = (
    'apps', 'plugins', 'remote_plugin', 'plugin_sharing', 'browser_use',
    'browser_use_external', 'browser_use_full_cdp_access', 'computer_use',
    'in_app_browser', 'multi_agent', 'hooks', 'skill_search', 'tool_suggest',
    'skill_mcp_dependency_install', 'worktrees', 'goals', 'shell_tool', 'unified_exec',
)


def report(assistant: str, *, installed: bool, authenticated: bool | None = None,
           image_tool: bool | None = None, inspection: bool | None = None,
           credential_present: bool = False, model_access: bool | None = None,
           live_verified: bool = False) -> dict:
    """A non-secret report from explicit observations, never a guessed live check."""
    if assistant not in ('codex', 'claude'):
        raise ValueError('Choose Codex or Claude Code.')
    if any(type(value) is not bool for value in (installed, credential_present, live_verified)):
        raise ValueError('Required capability observations must be booleans.')
    observations = (installed, authenticated, image_tool, inspection,
                    credential_present, model_access, live_verified)
    if any(value is not None and type(value) is not bool for value in observations):
        raise ValueError('Capability observations must be booleans or unknown.')
    problems, unknown = [], []
    if not installed:
        problems.append('assistant-missing')
    if authenticated is False:
        problems.append('sign-in-required')
    elif authenticated is None:
        unknown.append('sign-in-not-checked')
    if assistant == 'codex':
        if image_tool is False:
            problems.append('image-tool-unavailable')
        elif image_tool is None:
            unknown.append('image-tool-not-checked')
    else:
        if not credential_present:
            problems.append('gemini-key-required')
        if model_access is False:
            problems.append('image-model-unavailable')
        elif model_access is None:
            unknown.append('image-model-access-not-checked')
    if inspection is False:
        problems.append('manual-image-review-required')
    elif inspection is None:
        unknown.append('image-inspection-not-checked')
    if not live_verified:
        unknown.append('generation-and-editing-not-live-verified')
    return {
        'assistant': 'Codex' if assistant == 'codex' else 'Claude Code',
        'image_provider': 'Codex built-in image generation' if assistant == 'codex' else 'Gemini API',
        'state': ('unavailable' if any(p != 'manual-image-review-required' for p in problems)
                  else 'unverified' if unknown else 'manual-review' if problems else 'verified'),
        'problems': problems, 'unknown': unknown,
        'manual_review_required': inspection is False,
        'live_verified': bool(live_verified and not problems and not unknown),
        'credential_required': assistant == 'claude',
    }


def _reference_files(folder: Path, images) -> list[Path]:
    folder = Path(folder).resolve(strict=True)
    if not folder.is_dir():
        raise ValueError('Image jobs need an owned directory.')
    result = []
    for image in images:
        path = Path(image)
        if not path.is_absolute():
            path = folder / path
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(folder):
            raise ValueError('Image references must be regular files inside the image job.')
        owned_parts = []
        for part in (path, *path.parents):
            if part.resolve() == folder:
                break
            owned_parts.append(part)
        if any(part.is_symlink() for part in owned_parts):
            raise ValueError('Image references cannot traverse links.')
        result.append(path.resolve())
    return result


def codex_image_command(folder: Path, images=()) -> list[str]:
    """Command proposal verified against local help; execution belongs to I03.

    Prompt travels on stdin. The caller must collect returned image events, not
    assume that enabling a feature ensures account access or a particular tool path.
    """
    folder = Path(folder).resolve(strict=True)
    references = _reference_files(folder, images)
    args = ['codex', 'exec', '--json', '--cd', str(folder), '--sandbox', 'workspace-write',
            '--ignore-user-config', '--ignore-rules', '--ephemeral', '--skip-git-repo-check']
    for feature in CODEX_DISABLED:
        args += ['--disable', feature]
    args += ['--enable', 'image_generation', '-c', 'project_doc_max_bytes=0',
             '-c', 'web_search="disabled"']
    for image in references:
        args += ['--image', str(image)]
    return args + ['-']


def claude_inspection_command(folder: Path, mcp_config: Path) -> list[str]:
    """A Read-only inspection job; run with cwd=folder and an empty MCP config.

    The caller supplies private staged images and an explicit prompt. No Gemini
    key belongs in this process environment. Live multimodal access remains a
    separately recorded acceptance result.
    """
    folder = Path(folder).resolve(strict=True)
    config, = _reference_files(folder, [mcp_config])
    import json
    if json.loads(config.read_text(encoding='utf-8')) != {'mcpServers': {}}:
        raise ValueError('The inspection job requires an empty MCP configuration.')
    return ['claude', '-p', '--restricted', '--strict-mcp-config', '--mcp-config', str(config),
            '--tools', 'Read', '--allowedTools', 'Read', '--permission-prompts', 'none',
            '--permission-mode', 'dontAsk', '--no-session-persistence',
            '--output-format', 'stream-json', '--verbose']


def private_child_environment(environ: dict[str, str]) -> dict[str, str]:
    """Minimal environment for image/renderer children, excluding provider keys."""
    allowed = ('PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'CODEX_HOME', 'CLAUDE_CONFIG_DIR',
               'SYSTEMROOT', 'WINDIR')
    return {key: environ[key] for key in allowed if key in environ}
