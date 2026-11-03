"""An agent's event stream in plain words: one short line for each thing it does, and how it
ended. No studio state, no process, no network: a reader is fed one decoded event at a time.

    reader = ClaudeEvents()             # or CodexEvents()
    for event in stream:
        for line in reader.feed(event):
            activity(line)              # "Searching the web: …", "Reading saved source S3"
    reader.ended, reader.reason, reader.detail, reader.text

- `describe(tool, input)` is the line for one call to a worker tool or the agent's web search;
  `settled(tool, refused)` the line for how a call came out, when that is worth saying.
- A line is plain words only: never the event itself, a prompt, a task or a token count.
- `classify(said)` reads an agent's own account of why it stopped: unavailable, limit or
  failed. `shared_runner.agents` starts Claude Code and Codex as confined workers and uses
  these readers; a studio that starts an agent its own way may use them too.
"""
from __future__ import annotations

SERVER = 'runner'           # the name the worker tools are served under
CLAUDE_SEARCH = 'WebSearch'

# Words in an agent's own account of a failure that mean it could not be reached or is not
# signed in, and words that mean an account limit. A best effort: ready() is the real check.
UNREACHABLE = ('error sending request', 'connection failed', 'not logged in', 'unauthorized',
               'please run /login', 'invalid api key', 'routing discovery failed')
LIMITED = ('usage limit', 'rate limit', 'quota')
# How Claude names an ending that is not a success, in plain words.
CLAUDE_ENDINGS = {'error_max_budget_usd': 'its spending limit was reached',
                  'error_max_turns': 'it took more turns than a job may',
                  'error_during_execution': 'it failed while it was working'}



def flag(value) -> bool:
    """A yes or no an agent sent, which may have arrived as text."""
    if isinstance(value, str):
        return value.strip().lower() in ('true', 'yes', '1')
    return bool(value)


# --- plain words for what a worker is doing --------------------------------------------

def clip(text, length: int = 140) -> str:
    text = ' '.join(str(text).split())
    return text if len(text) <= length else text[:length - 1] + '…'


def describe(tool: str, given: dict) -> str:
    """One plain line for a call to a worker tool or to the agent's web search."""
    given = given if isinstance(given, dict) else {}
    lines = {
        'list_inputs': 'Looking at what it was given',
        'read_input': f"Reading {given.get('name', 'an input')}",
        'submit_artifact': f"Handing back {given.get('name', 'a draft')}",
        'submit_review': 'Writing its own notes on the draft',
        'save_source': f"Saving a source: {given.get('url', '')}",
        'read_source': (f"Reading the original of saved source {given.get('source_id', '')}"
                        if flag(given.get('original')) else
                        f"Reading saved source {given.get('source_id', '')}"),
        'search_source': (f"Searching {given.get('source_id', 'a source')} for "
                          f"\"{given.get('query', '')}\""),
        'submit_finding': f"Handing back the finding for {given.get('item', 'its question')}",
        'ask_person': 'Asking a question',
        'check_outline': 'Checking what the slides say',
        'submit_outline': 'Handing in what the slides say',
        'check_section': 'Checking that its slides can be drawn',
        'preview_section': 'Rendering its slides to look at them',
        'search_icons': f"Searching the icons for \"{given.get('words', '')}\"",
        'submit_section': 'Handing in its slides',
        'look_at_slide': f"Looking at slide {given.get('number', '')}",
        'submit_assessment': 'Handing in what it found on the slides',
        'submit_judgements': 'Handing in its judgement of every slide',
        'submit_coverage': 'Saying which slides address each objective',
        'web_search': f"Searching the web: {given.get('query', '')}",
        # Claude Code's own tool for an answer in a required shape (--json-schema).
        'StructuredOutput': 'Handing back its answer',
    }
    return clip(lines.get(tool, f'Using {tool}')).rstrip(': ')


HANDED = {'submit_artifact': 'draft', 'submit_finding': 'finding', 'submit_outline': 'outline',
          'submit_section': 'section', 'submit_assessment': 'review',
          'submit_judgements': 'review'}


def settled(tool: str | None, refused: bool) -> str | None:
    """One plain line for how a call came out, when that is worth saying."""
    if tool in HANDED:
        thing = HANDED[tool]
        return (f'The {thing} was sent back with problems to fix' if refused
                else f'The {thing} was accepted')
    if tool == 'save_source' and refused:
        return 'That source could not be saved'
    return f'{tool} was refused' if refused and tool else None


def classify(said: str) -> str:
    """Why an agent stopped, from its own account: unavailable, limit or failed."""
    low = said.lower()
    if any(mark in low for mark in UNREACHABLE):
        return 'unavailable'
    return 'limit' if any(mark in low for mark in LIMITED) else 'failed'


class ClaudeEvents:
    """Reads Claude's event stream: lines to show as they happen, and how it ended."""

    def __init__(self):
        self.calls: dict[str, str] = {}
        self.text, self.cost, self.tokens = '', None, None
        self.ended, self.reason, self.detail = False, None, ''
        self.budget = False     # it ended because it spent all it was given
        self.account = False    # its account refused it: Claude Code's status 429

    def feed(self, event: dict) -> list[str]:
        kind, lines = event.get('type'), []
        if kind == 'system':
            lines += self._system(event)
        elif kind in ('assistant', 'user'):
            content = (event.get('message') or {}).get('content')
            for block in content if isinstance(content, list) else ():
                lines += self._block(block) if isinstance(block, dict) else []
        elif kind == 'rate_limit_event':
            status = str((event.get('rate_limit_info') or {}).get('status', 'allowed'))
            if not status.startswith('allowed'):
                lines.append(f'The account\'s usage limit: {status}')
        elif kind == 'result':
            self._result(event)
        return [line for line in lines if line]

    def _system(self, event: dict) -> list[str]:
        subtype = event.get('subtype')
        if subtype == 'init':
            model = event.get('model')
            return ['Started' + (f' on {model}' if model else '')]
        if subtype == 'thinking_tokens':
            return ['Thinking']
        if subtype == 'permission_denied':
            return [f"Was refused the use of {event.get('tool_name', 'a tool')}"]
        return []

    def _block(self, block: dict) -> list[str]:
        if block.get('type') == 'tool_use':
            name = str(block.get('name', ''))
            tool = ('web_search' if name == CLAUDE_SEARCH
                    else name.removeprefix(f'mcp__{SERVER}__'))
            self.calls[block.get('id')] = tool
            return [describe(tool, block.get('input'))]
        if block.get('type') == 'tool_result':
            return [settled(self.calls.get(block.get('tool_use_id')),
                            bool(block.get('is_error')))]
        return []

    def _result(self, event: dict) -> None:
        self.ended = True
        self.text = event.get('result') if isinstance(event.get('result'), str) else ''
        cost, usage = event.get('total_cost_usd'), event.get('usage')
        self.cost = float(cost) if isinstance(cost, (int, float)) else None
        if isinstance(usage, dict):
            cached = usage.get('cache_read_input_tokens') or 0
            self.tokens = {
                'input': ((usage.get('input_tokens') or 0) + cached
                          + (usage.get('cache_creation_input_tokens') or 0)),
                'cached': cached, 'output': usage.get('output_tokens') or 0}
        subtype, status = str(event.get('subtype')), event.get('api_error_status')
        if subtype == 'success' and not event.get('is_error'):
            return
        said = clip(self.text or CLAUDE_ENDINGS.get(subtype, subtype), 300)
        self.budget = subtype == 'error_max_budget_usd'
        self.account = status == 429
        if subtype in ('error_max_budget_usd', 'error_max_turns') or status == 429:
            self.reason = 'limit'
        elif status in (401, 403):
            self.reason = 'unavailable'
        else:
            self.reason = classify(said)
        self.detail = said


class CodexEvents:
    """Reads Codex's event stream: lines to show as they happen, and how it ended."""

    def __init__(self):
        self.text, self.cost, self.tokens = '', None, None
        self.turns, self.failure, self.said = 0, None, ''

    def feed(self, event: dict) -> list[str]:
        kind, item = event.get('type'), event.get('item')
        item = item if isinstance(item, dict) else {}
        if kind == 'thread.started':
            return ['Started']
        if kind == 'item.started' and item.get('type') == 'mcp_tool_call':
            return [describe(str(item.get('tool')), item.get('arguments'))]
        if kind == 'item.completed':
            return [line for line in self._item(item) if line]
        if kind == 'turn.completed':
            self._usage(event.get('usage'))
        elif kind == 'turn.failed':
            self.failure = clip((event.get('error') or {}).get('message', 'no reason given'),
                                300)
        elif kind == 'error':
            self.said = clip(event.get('message', ''), 300)
            return ['Reconnecting' if self.said.startswith('Reconnecting')
                    else f'Codex said: {clip(self.said)}']
        return []

    def _item(self, item: dict) -> list:
        kind = item.get('type')
        if kind == 'mcp_tool_call':
            return [settled(str(item.get('tool')), item.get('status') == 'failed')]
        if kind == 'web_search':
            return [describe('web_search', item)]
        if kind == 'agent_message':
            self.text = item.get('text') if isinstance(item.get('text'), str) else self.text
        elif kind == 'reasoning':
            return ['Thinking']
        elif kind == 'command_execution':
            return ['Ran a command, which a worker should not be able to do']
        elif kind == 'error':
            self.said = clip(item.get('message', ''), 300)
            return [f'Codex said: {clip(self.said)}']
        return []

    def _usage(self, usage) -> None:
        self.turns += 1
        if not isinstance(usage, dict):
            return
        tokens = self.tokens or {'input': 0, 'cached': 0, 'output': 0}
        for ours, theirs in (('input', 'input_tokens'), ('cached', 'cached_input_tokens'),
                             ('output', 'output_tokens')):
            tokens[ours] += usage.get(theirs) or 0
        self.tokens = tokens
