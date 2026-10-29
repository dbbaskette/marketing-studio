"""Safe assistant diagnostics; raw stderr, prompts and provider messages stay private."""
import json

from .contracts import Invalid

MESSAGES = {
    'timeout': 'The assistant reached the five-minute limit and has stopped. Your saved sources and earlier work are kept. You can try this step again or narrow the source material. A retry starts a new assistant request.',
    'cancelled': 'The assistant request was stopped. Your saved sources and earlier work are kept. Nothing was retried automatically.',
    'sign-in': 'The selected assistant needs you to sign in on this computer. Your saved work is kept. Sign in before trying again.',
    'quota': 'The assistant reported a usage or rate limit. Your saved work is kept. Wait for your allowance to reset before trying again.',
    'model': 'The selected assistant model is unavailable. Your saved work is kept. Check the model in Marketing Studio settings before trying again.',
    'connection': 'The assistant could not finish because its provider connection failed. The local worker has ended and your saved work is kept. You can try again when the connection is restored.',
    'missing': 'The selected assistant CLI could not be started. Your saved work is kept. Check its installation on this computer before trying again.',
    'launch': 'The assistant request could not be started on this computer. Your saved work is kept. Check the installed assistant before trying again.',
    'incompatible': 'The installed assistant CLI does not support this request. Your saved work is kept. Check its version before trying again.',
    'invalid-output': 'The assistant ended without a usable structured proposal. Your manuscript and sources are unchanged. You can try planning again; nothing was retried automatically.',
    'worker': 'The assistant exited before completing this request. Your saved sources and earlier work are kept. Nothing is still running for this request; you can try again.',
}


class AssistantFailure(Invalid):
    def __init__(self, reason):
        self.reason = reason if reason in MESSAGES else 'worker'
        super().__init__(MESSAGES[self.reason])


def classify(outcome, stderr=''):
    """Classify only failed-run diagnostics, never quoted successful proposal text."""
    diagnostics = [stderr]
    for line in outcome.get('events', '').splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and (event.get('type') in ('error', 'turn.failed')
                or event.get('type') == 'result' and event.get('is_error') is True):
            diagnostics.append(json.dumps(event))
    value = '\n'.join(diagnostics).casefold()
    for reason, terms in (
            ('sign-in', ('not logged in', 'unauthorized', 'authentication failed', 'please sign in', 'login required')),
            ('quota', ('usage limit', 'rate limit', 'rate_limit', 'quota', 'insufficient credits', 'too many requests')),
            ('model', ('model_not_found', 'model not found', 'model is not supported', 'model is unavailable')),
            ('incompatible', ('unexpected argument', 'unrecognized arguments', 'unknown option')),
            ('connection', ('connection reset', 'connection refused', 'failed to connect', 'network error', 'stream disconnected'))):
        if any(term in value for term in terms):
            return reason
    return {'unknown': 'timeout', 'cancelled': 'cancelled'}.get(outcome.get('state'), 'worker')
