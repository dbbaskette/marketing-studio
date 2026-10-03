"""Scoped writing defaults; personal values are never Hub artifacts."""
import json
import re
from pathlib import Path
import studio
from hub_store import HubError

KEYS = ('author', 'voice', 'audience', 'blog_type', 'review_folder')
FORMS = ('announcement', 'tutorial', 'architecture', 'performance', 'comparison', 'story')


def validate(key, value, root, team=False):
    if key not in KEYS:
        raise ValueError('Unknown writing default.')
    if key == 'voice':
        if not isinstance(value, dict):
            raise ValueError('Voice needs a pinned profile reference.')
        if team:
            if set(value) != {'item', 'revision'} or not all(re.fullmatch('[a-f0-9]{32}', str(v)) for v in value.values()):
                raise ValueError('Team voice must use a portable Hub item/revision.')
        else:
            if set(value) != {'profile_id', 'revision'} or type(value['revision']) is not int or value['revision'] < 1:
                raise ValueError('Personal voice needs profile_id and positive revision.')
            studio.voice_pin(root, value['profile_id'], value['revision'])
    elif not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError('Default must be nonempty text of at most 500 characters.')
    elif key == 'blog_type' and value not in FORMS:
        raise ValueError('Unknown blog type: use ' + ', '.join(FORMS))
    elif key == 'review_folder' and not re.fullmatch(r'https://drive\.google\.com/drive/(?:u/\d+/)?folders/[A-Za-z0-9_-]{1,200}', value):
        raise ValueError('Use a canonical Google Drive folder URL without query parameters.')
    return value


def personal(root):
    path = studio.inside(root, '.writing-defaults.json')
    value = studio.read_json(path) if path.exists() else {'schema': 1, 'values': {}}
    if value.get('schema') != 1 or not isinstance(value.get('values'), dict):
        raise ValueError('Unsupported personal defaults file.')
    return value


def team_rows(adapter):
    rows = {key: [] for key in KEYS}
    if adapter:
        graph = adapter.hub.graph()
        for item, heads in graph['heads'].items():
            for rev in heads:
                record = graph['revisions'][rev]
                data = record.get('data', {})
                key = data.get('key', '')
                if (record['kind'] == 'context' and record['scope'] == {'level': 'team', 'key': ''}
                        and record['status'] != 'tombstone' and key.startswith('writing-default:')
                        and key[16:] in KEYS):
                    rows[key[16:]].append({'value': data.get('value'), 'item': item, 'revision': rev,
                                           'conflicted': len(heads) != 1})
    return rows


def resolve(root, record=None, overrides=None, adapter=None):
    if adapter is None:
        from hub_workspace import active
        adapter = active(root)
    personal_values = personal(root)['values']
    rows = team_rows(adapter)
    article = dict((record or {}).get('writing_preferences', {}))
    if record:
        if record.get('author'): article['author'] = record['author']
        if record.get('voice', {}).get('mode') == 'profile':
            article['voice'] = {k: record['voice'][k] for k in ('profile_id', 'revision')}
        elif record.get('voice'):
            article['voice'] = {'mode': record['voice']['mode'], 'tone': record['voice'].get('tone', '')}
    result, problems = {}, []
    for key in KEYS:
        source, value = None, None
        for scope, values in [('request', overrides or {}), ('article', article), ('personal', personal_values)]:
            if key in values:
                source, value = scope, values[key]
                break
        if source is None and rows[key]:
            if len(rows[key]) != 1 or rows[key][0]['conflicted']:
                problems.append({'key': key, 'status': 'conflicted', 'scope': 'team', 'choices': rows[key]})
                continue
            source, value = 'team', rows[key][0]['value']
        if source:
            try:
                if not (source in ('article', 'request') and key == 'voice' and isinstance(value, dict) and value.get('mode') in ('tone', 'preserve')):
                    validate(key, value, root, team=source == 'team')
                if key == 'voice' and source == 'team':
                    shared = adapter.hub.graph()['revisions'].get(value['revision'])
                    if not shared or shared['item'] != value['item'] or shared['kind'] != 'voice' or shared['status'] == 'tombstone':
                        raise ValueError('Selected team voice is missing or retired.')
                result[key] = {'value': value, 'scope': source}
                if source == 'team':
                    result[key]['reference'] = {k: rows[key][0][k] for k in ('item', 'revision')}
            except (ValueError, KeyError, TypeError, OSError) as exc:
                problems.append({'key': key, 'scope': source, 'status': 'unavailable', 'reason': str(exc)})
    return {'values': result, 'problems': problems,
            'precedence': ['request', 'article', 'personal', 'team', 'generic'],
            'team_observation': 'cached; refresh the selected Hub for other members’ changes' if adapter else 'no selected Hub'}


def command(root, args):
    from hub_workspace import active
    adapter = active(root)
    record = studio.item(root, 'articles', args.id)[1] if getattr(args, 'id', None) else None
    if args.action == 'show':
        return resolve(root, record, adapter=adapter)
    if args.scope == 'personal':
        config = personal(root)
        if args.action == 'set':
            value = json.loads(args.value) if args.key == 'voice' else args.value
            config['values'][args.key] = validate(args.key, value, root)
        else:
            config['values'].pop(args.key, None)
        path = studio.inside(root, '.writing-defaults.json')
        studio.write_json(path, config);path.chmod(0o600)
        return {'status': 'saved', 'scope': 'personal', 'key': args.key}
    if adapter is None:
        raise ValueError('Select a Team Hub for shared defaults.')
    rows = team_rows(adapter)[args.key]
    if len(rows) > 1 or any(r['conflicted'] for r in rows):
        raise ValueError('Resolve competing team default records before changing this key.')
    if args.action == 'reset' and not rows:
        return {'status': 'unchanged', 'scope': 'team', 'key': args.key}
    value = json.loads(args.value) if args.key == 'voice' and args.action == 'set' else args.value
    deps = []
    if args.action == 'set':
        validate(args.key, value, root, team=True)
        if args.key == 'voice':
            shared = adapter.hub.graph()['revisions'].get(value['revision'])
            if not shared or shared['item'] != value['item'] or shared['kind'] != 'voice' or shared['status'] == 'tombstone':
                raise ValueError('Share the chosen voice profile before setting it as a team default.')
            deps = [{**value, 'kind': 'voice'}]
    old = rows[0] if rows else {}
    saved = adapter.hub.save('context', 'Writing default: ' + args.key,
        item=old.get('item'), parents=[old['revision']] if old else [],
        data={'key': 'writing-default:' + args.key, 'value': value}, dependencies=deps,
        status='tombstone' if args.action == 'reset' else 'active')
    return {'scope': 'team', 'key': args.key, 'hub_sync': saved}


def for_create(root, args):
    overrides = {}
    for key in ('author', 'audience', 'blog_type', 'review_folder'):
        value = getattr(args, key, None)
        if value is not None: overrides[key] = value
    if args.profile:
        overrides['voice'] = studio.voice_pin(root, args.profile)
    elif args.tone is not None or args.voice is not None or args.mode == 'existing':
        # Explicit tone/preserve (and imported draft voice) outrank profile defaults.
        overrides['voice'] = {'mode': args.voice or 'preserve', 'tone': args.tone or ''}
    from hub_workspace import active
    adapter = active(root)
    result = resolve(root, overrides=overrides, adapter=adapter)
    if 'voice' in overrides and not args.profile:
        result['values'].pop('voice', None)
        result['problems'] = [p for p in result['problems'] if p['key'] != 'voice']
    if result['problems']:
        raise ValueError('Resolve missing or competing defaults first: ' + ', '.join(p['key'] for p in result['problems']))
    values = result['values']
    for key in ('author', 'audience', 'blog_type', 'review_folder'):
        if key in values: setattr(args, key, values[key]['value'])
    voice = values.get('voice')
    pin = None
    if voice:
        if voice['scope'] == 'team':
            ref = voice['value']
            local_id = adapter._checkout(ref['item'], ref['revision'])
            pin = studio.voice_pin(root, local_id)
        else: pin = voice['value']
    return pin
