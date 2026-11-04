"""Bounded display of already accepted packets; never a delivery artifact."""
import hashlib
import json

from studio_core import research_contract as rc


def evidence(packet, basis):
    def text(value):
        return str(value or '')[:1200]
    facts = packet.get('facts', [])
    sources = packet.get('sources', [])
    return {
        'basis': basis, 'request_digest': packet['request_digest'],
        'generation': packet['generation'], 'attempt': packet['attempt'],
        'facts': [{'statement': text(fact.get('statement')),
                   'citations': [{key: text(citation.get(key)) for key in ('source', 'quote', 'locator')}
                                 for citation in fact.get('citations', [])[:6]]} for fact in facts[:12]],
        'sources': [{key: text(source.get(key)) for key in ('id', 'title', 'origin', 'permission', 'context', 'context_note')}
                    for source in sources[:24]],
        'limitations': [text(item) for item in [*packet.get('limitations', []), *packet.get('gaps', [])][:12]],
        'truncated': len(facts) > 12 or len(sources) > 24 or any(len(str(f)) > 1200 for f in facts),
    }


def restored(case, state, basis):
    """Fail closed for a missing, replaced or obsolete saved preview."""
    found = {}
    if state.get('status') == 'stopped':
        return found
    for stream in state['workstreams']:
        attempt = next(iter(reversed(stream['attempts'])), {})
        if attempt.get('status') != 'accepted':
            continue
        try:
            path = rc.inside(case, attempt['packet']['file'])
            if path.stat().st_size > 2 * 1024 * 1024:
                continue
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != attempt['packet']['sha256']:
                continue
            packet = json.loads(raw)
            if any(packet[key] != expected for key, expected in (
                    ('generation', state['generation']), ('request_digest', state['request_digest']),
                    ('workstream', stream['id']), ('attempt', attempt['number']),
                    ('investigator', attempt['investigator']))):
                continue
            found[stream['id']] = evidence(packet, basis)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return found
