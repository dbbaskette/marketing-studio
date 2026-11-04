"""Private, versioned unfinished briefs; reading and saving never create a project."""
from studio_core import intake_drafts
from .workspace import data_root
from .validation import require, identifier
from .contracts import Invalid

FIELDS = frozenset(('research_first', 'materials', 'library', 'imported', 'step', 'title',
    'text', 'direction', 'audience', 'purpose', 'must', 'locked', 'exclusions', 'preset',
    'upload', 'selection', 'csv', 'created', 'request_id', 'notes_text', 'notes_source',
    'library_added', 'upload_added', 'intakeOpen'))


def scope(store):
    return {'product': 'Infographic Studio', 'owner': store.owner, 'workspace': str(store.root)}


def dispatch(store, sent):
    require(store is not None, 'Finish setup before saving an unfinished brief.')
    patch = sent.get('patch') if isinstance(sent, dict) else None
    if patch is not None:
        require(isinstance(patch, dict) and set(patch) <= FIELDS, 'Save only unfinished brief fields.')
        require('step' not in patch or type(patch['step']) is int and patch['step'] in (0, 1), 'Choose one intake step.')
        for key in ('materials', 'library', 'imported'):
            require(key not in patch or isinstance(patch[key], list) and len(patch[key]) <= 40, 'Choose up to forty captured sources.')
    if patch is not None:
        require('materials' not in patch or all(isinstance(one, dict) and isinstance(one.get('preview'), dict) and identifier(one['preview'].get('id')) and type(one.get('acknowledged', False)) is bool for one in patch['materials']), 'Choose saved source previews and their acknowledgements.')
        require('created' not in patch or patch['created'] is None or isinstance(patch['created'], dict) and identifier(patch['created'].get('id')), 'Keep one saved infographic identity.')
    try:
        held = intake_drafts.dispatch(data_root(), scope(store), sent)
    except ValueError as error:
        raise Invalid(str(error)) from None
    missing = []
    from .workspace import _json
    for material in (held.get('draft') or {}).get('materials') or []:
        ident = (material.get('preview') or {}).get('id') if isinstance(material, dict) else None
        if not identifier(ident):
            missing.append(str(ident)[:64])
            continue
        try:
            root = data_root() / 'jobs' / ('intake_' + ident)
            # Read bounded metadata only. Actual source hashes are verified on import.
            record = _json(root, 'preview.json', 16_000)
            if record.get('id') != ident or any((root / name).is_symlink() or not (root / name).is_file()
                for name in ('original.raw', 'extracted.json')):
                missing.append(ident)
        except (OSError, ValueError):
            missing.append(ident)
    if sent.get('action') == 'save':
        return {'revision': held['revision'], 'missing': missing}
    return {**held, 'missing': missing}
