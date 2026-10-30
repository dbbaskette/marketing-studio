"""Translate a completed negative-findings review to Harness Slides coverage.

Callers must enforce real inspection before calling this boundary. A finding is
the reviewer's no; its complement is the yes required by the current wire format.
No assistant request, rendering, or creative assessment happens here.
"""
import hashlib
import json
from pathlib import Path


def coverage(review, findings, questions, picture):
    rows = []
    for slide in review['slides']:
        reused = (review.get('reused') or {}).get(slide['id'])
        note = ('Reused verified native inspection from deck ' + reused['from_deck']
                + '; checked current whole-deck consistency. ' if reused else
                'Inspected native pixels and all review questions. ')
        rows.append({'id': slide['id'], 'number': slide['number'],
                     'answers': [not any(f['slide'] == slide['id'] and f['question'] == n
                                         for f in findings)
                                 for n in range(1, len(questions) + 1)],
                     'note': note + f"Slide {slide['number']}: {slide['title']}",
                     'image_sha256': hashlib.sha256(picture(slide['image'])).hexdigest(),
                     **({'reused_from': reused['from_deck']} if reused else {})})
    return rows


def payload(review, findings, weakest, rows):
    answer = {'deckSha256': review['deck'], 'reviewer': 'independent',
              'weakest': weakest, 'findings': [
                  {key: finding[key] for key in ('slide', 'question', 'severity', 'note', 'fix')
                   if finding.get(key) is not None} for finding in findings]}
    try:
        packet = json.loads((Path(review['preview']) / 'critic.json').read_text())
    except (OSError, ValueError):
        packet = {}
    if packet.get('schema') != 1:
        answer['slides'] = [{key: row[key] for key in ('id', 'answers', 'note')} for row in rows]
    return answer
