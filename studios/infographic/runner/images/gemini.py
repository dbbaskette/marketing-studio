"""Bounded standard-library Gemini Interactions image adapter. No SDK or silent retry."""
from __future__ import annotations

import base64
import http.client
import json
import os
from pathlib import Path
import re
import socket
import ssl
import time

from .base import result, save_asset
from ..contracts import MAX_ASSET_BYTES, Invalid, canonical
from ..validation import identifier, image_size, require, text

MAX_RESPONSE = 64_000_000


def https(model, credential, payload, seconds):
    deadline = time.monotonic() + seconds
    connection = http.client.HTTPSConnection('generativelanguage.googleapis.com', timeout=seconds,
                                            context=ssl.create_default_context())
    try:
        connection.request('POST', '/v1beta/interactions',
                           body=canonical(payload), headers={'x-goog-api-key': credential,
                           'Content-Type': 'application/json', 'Accept': 'application/json'})
        channel = connection.sock
        channel.settimeout(max(.01, deadline - time.monotonic()))
        response = connection.getresponse()
        chunks, size = [], 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('The image request exceeded its deadline.')
            channel.settimeout(remaining)
            chunk = response.read1(min(65_536, MAX_RESPONSE - size + 1))
            if not chunk: break
            size += len(chunk)
            require(size <= MAX_RESPONSE, 'The image provider exceeded its response limit.')
            chunks.append(chunk)
        raw = b''.join(chunks)
        if response.status != 200:
            return response.status, {}  # Never propagate provider error text or a reflected key.
        return response.status, json.loads(raw)
    finally:
        connection.close()


class Gemini:
    def __init__(self, folder, *, model, transport=https, key=lambda: os.environ.get('GEMINI_API_KEY'), seconds=180):
        require(isinstance(model, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}', model),
                'Choose the explicit image-capable Gemini model ID.')
        require(type(seconds) is int and 1 <= seconds <= 600, 'Choose an image request timeout of 1–600 seconds.')
        self.folder, self.model, self.transport, self.key, self.seconds = Path(folder), model, transport, key, seconds

    def readiness(self):
        present = bool(self.key())
        return result('gemini', 'readiness', None, state='unverified' if present else 'unavailable',
                      reason=None if present else 'gemini-key-required')

    def generate(self, *, attempt_id, brief):
        return self._request('generate', attempt_id, brief, [])

    def edit(self, *, attempt_id, brief, reference_assets):
        require(bool(reference_assets), 'Reference-guided editing needs an original owned image.')
        return self._request('edit', attempt_id, brief, reference_assets)

    def _request(self, operation, attempt_id, brief, references):
        require(identifier(attempt_id) and isinstance(brief, dict) and text(brief.get('prompt'), limit=60_000),
                'Use an owned attempt and a complete saved image brief.')
        credential = self.key()
        if not credential:
            return result('gemini', operation, attempt_id, state='unavailable', reason='gemini-key-required')
        require(isinstance(credential, str) and 0 < len(credential) <= 4096 and credential.isascii()
                and not any(ord(c) < 33 for c in credential),
                'The server image credential is invalid.')
        require(credential not in brief['prompt'], 'A credential was found in the proposed prompt; nothing was sent.')
        parts = [{'type': 'text', 'text': brief['prompt']}]
        require(len(references) <= 5, 'Use at most five explicit image references.')
        total = 0
        for reference in references:
            require(isinstance(reference, dict) and reference.get('mime') in ('image/png', 'image/jpeg')
                    and type(reference.get('data')) is bytes, 'References must be staged image bytes, not paths or URLs.')
            raw = reference['data']
            total += len(raw)
            require(total <= MAX_ASSET_BYTES, 'The reference-image request exceeds its size limit.')
            image_size(raw, reference['mime'])
            parts.append({'type': 'image', 'mime_type': reference['mime'], 'data': base64.b64encode(raw).decode()})
        canvas = brief.get('canvas') or {'width': 3, 'height': 4}
        ratio = canvas['width'] / canvas['height']
        aspect = min(('2:3', '3:4', '4:5'), key=lambda v: abs(int(v[0]) / int(v[2]) - ratio))
        payload = {'model': self.model, 'input': parts, 'store': False,
                   'response_format': {'type': 'image', 'mime_type': 'image/png', 'image_size': '2K', 'aspect_ratio': aspect}}
        try:
            status, response = self.transport(self.model, credential, payload, self.seconds)
        except (TimeoutError, socket.timeout, ConnectionError, http.client.HTTPException, OSError):
            return result('gemini', operation, attempt_id, state='unknown', reason='timeout')
        except (ValueError, RecursionError):
            return result('gemini', operation, attempt_id, state='failed', reason='invalid-asset')
        reasons = {401: 'sign-in-required', 403: 'image-model-unavailable', 404: 'image-model-unavailable',
                   429: 'quota'}
        if status != 200:
            if status >= 500:
                return result('gemini', operation, attempt_id, state='unknown', reason='provider-refusal')
            return result('gemini', operation, attempt_id, state='failed', reason=reasons.get(status, 'provider-refusal'))
        try:
            require(isinstance(response, dict) and len(canonical(response)) <= MAX_RESPONSE,
                    'The provider response is invalid or too large.')
            assets = []
            state = response.get('status')
            if state in ('in_progress', 'requires_action'):
                return result('gemini', operation, attempt_id, state='unknown', reason='provider-refusal')
            require(state == 'completed', 'The image provider did not complete its interaction.')
            steps = response.get('steps') or []
            require(isinstance(steps, list) and len(steps) <= 30, 'The provider returned too many steps.')
            for step in steps:
                if step.get('type') != 'model_output': continue
                for part in step.get('content', []):
                    if part.get('type') != 'image': continue
                    require(len(assets) < 4 and isinstance(part.get('data'), str)
                            and len(part['data']) <= 44_000_000, 'Returned image data exceeds its limit.')
                    raw = base64.b64decode(part['data'], validate=True)
                    assets.append(save_asset(self.folder, raw, part.get('mime_type')))
            if not assets:
                return result('gemini', operation, attempt_id, state='failed', reason='provider-refusal')
            usage = response.get('usage') or {}
            usage = {'cost': None, 'currency': None, 'input_tokens': usage.get('total_input_tokens'),
                     'output_tokens': usage.get('total_output_tokens')}
            # Response ID is opaque and bounded, never a reflected error/prompt.
            request_id = response.get('id')
            if not text(request_id, limit=512) or credential in request_id:
                request_id = None
            return result('gemini', operation, attempt_id, state='complete', assets=assets,
                          request_id=request_id, usage=usage)
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            return result('gemini', operation, attempt_id, state='failed', reason='invalid-asset')

    def status(self, *, attempt_id):
        # Synchronous generateContent has no supported request reconciliation endpoint.
        return result('gemini', 'status', attempt_id, state='unknown')

    def cancel(self, *, attempt_id):
        return result('gemini', 'cancel', attempt_id, state='unknown', reason='stopped')
