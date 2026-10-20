"""Opt-in compact CLI envelope; existing full JSON remains compatible."""

import argparse
import json
import sys


class Parser(argparse.ArgumentParser):
    def error(self, message):
        if '--compact' not in sys.argv[1:]:
            return super().error(message)
        print(json.dumps(failure(message, usage=True)))
        self.exit(2)


def failure(message, usage=False):
    busy = 'Workspace is busy:' in message or 'still running after a short wait' in message
    return {
        'schema': 1,
        'status': 'usage' if usage else 'busy' if busy else 'failed',
        'saved': None,
        'shared': False,
        'warnings': [message[:1200]],
        'next_step': 'Check --help and correct the command; nothing was run.'
        if usage
        else 'Retry shortly; leave the lock file in place.'
        if busy
        else 'Inspect the saved article/status before retrying a mutation. Keep your local work.',
    }


def compact(result, args):
    if isinstance(result, list):
        return {
            'schema': 1,
            'status': 'ok',
            'saved': None,
            'shared': False,
            'warnings': [],
            'items': [
                {
                    key: item.get(key)
                    for key in ('id', 'name', 'title', 'status', 'revision')
                    if key in item
                }
                for item in result[:20]
            ],
            'total': len(result),
            'truncated': len(result) > 20,
            'next_step': 'Choose an item by ID. Omit --compact for full records.',
        }
    sync = result.get('team_sync') or result.get('hub_sync') or {}
    shared = sync.get('shared') is True or sync.get('status') in ('shared', 'synchronized')
    saved = args.group in ('article', 'profile', 'source') and getattr(args, 'action', '') not in (
        'show',
        'status',
    )
    if args.group == 'article' and getattr(args, 'action', '') == 'restore':
        saved = args.apply
    warnings = []
    if sync and not shared and sync.get('status') != 'local-only':
        warnings.append(
            str(
                sync.get('notice')
                or sync.get('error')
                or sync.get('status')
                or 'Sharing is not verified.'
            )[:800]
        )
    return {
        'schema': 1,
        'status': result.get('status', 'saved' if saved else 'ok'),
        'saved': True if saved else None,
        'shared': shared,
        'warnings': warnings,
        **{
            key: result[key]
            for key in (
                'id',
                'title',
                'name',
                'revision',
                'stage',
                'next_step',
                'preview',
                'expected',
                'comparison',
            )
            if key in result
        },
        'next_step': result.get('next_step')
        or sync.get('next_step')
        or (
            'Continue from the saved version; sharing is a separate result.'
            if saved
            else 'Omit --compact to inspect the full result.'
        ),
    }
