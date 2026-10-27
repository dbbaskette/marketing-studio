"""A job's result lands only while its part is unchanged.

A desk job carries the part it changes and that part's fingerprint when it was asked for
(`basis`). When the result comes back, `land_part`, `land_selection` and `land_sections`
check the basis, clean the result, refuse one that would start a new part, check the text
the part would hold and return what to write, each with the guards' line for it
(`guards.flags`), so every rewrite's fact and structure check is kept. They write nothing:
the studio keeps the version, sets the text and writes through its store. `settle` runs a
studio's apply once and settles the job with a readable problem whatever goes wrong.

The job queues are not shared; each studio calls these as its results land.
"""

import hashlib
import json
import re

from . import guards, record
from .parts import MARKDOWN, TITLE

ACTIVE = ('queued', 'working')
GAPS = 50  # gaps a draft keeps
EMPTY_RESULT = 'The result was empty. Run it again.'
MOVED = 'The selected passage changed while this was being written. Select it again.'
NOT_LISTED = 'The result was not the list of sections asked for. Run it again.'
UNKNOWN = 'The result named sections this draft does not have. Run it again.'
NOT_SAVED = 'This result could not be saved: '
NOTHING_CHANGED = ' Nothing was changed; run it again.'


def unsettled(job):
    """A ready result not yet landed: still the item's job under way."""
    return job.get('status') == 'ready' and not job.get('settled_at')


def busy(job):
    return job.get('status') in ACTIVE or unsettled(job)


def fingerprint(value):
    """The SHA-256 of `value` as sorted JSON, as a job's basis."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def sections_basis(draft):
    return fingerprint([[section['id'], section['text']] for section in draft['sections']])


def _openings(codec):
    """The fixed parts a whole-draft job works on as sections: each that is not one line."""
    return [part for part in codec.fixed if part not in codec.single]


def pass_basis(draft, codec=MARKDOWN):
    """What a whole-draft pass was asked about: the opening and every section."""
    return fingerprint(
        [[part, draft[part]] for part in _openings(codec)]
        + [[s['id'], s['text']] for s in draft['sections']]
    )


def stale(codec=MARKDOWN):
    return 'The ' + codec.thing + ' changed while this was being written. Run it again.'


def clean(text, heading=None):
    """The returned writing without a repeated heading or wrapping blank lines."""
    text = text.replace('\r\n', '\n').strip()
    if heading is not None:
        first, _, rest = text.partition('\n')
        if re.fullmatch(r'#{1,6}\s+' + re.escape(heading) + r'\s*', first.strip()):
            text = rest.strip()
    return text


def opening_text(text):
    """A returned opening without a leading # title line: the title is its own part."""
    text = clean(text)
    first, _, rest = text.partition('\n')
    return rest.strip() if TITLE.fullmatch(first.strip()) else text


def no_heading(text, codec=MARKDOWN, deepest=2):
    """A result that would add a part is refused readably; the person adds parts."""
    mark = codec.heading_in(text, deepest)
    if mark:
        raise ValueError(codec.added_message(mark))


def section_texts(content):
    """[{id, text}] from a whole-draft result, refused readably when malformed."""
    text = content.strip()
    fenced = re.fullmatch(r'```(?:json)?\s*\n(.*)\n```', text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        found = json.loads(text)
    except ValueError:
        raise ValueError(NOT_LISTED) from None
    if (
        not isinstance(found, list)
        or len(found) > 500
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get('id'), str)
            or not isinstance(item.get('text'), str)
            for item in found
        )
    ):
        raise ValueError(NOT_LISTED)
    return found


def merge_gaps(draft, result, most=GAPS):
    """The gaps a result names join the draft's, each once, the newest `most` kept."""
    found = result.get('gaps')
    if not isinstance(found, list):
        return
    gaps = list(draft.get('gaps') or [])
    for gap in found:
        if isinstance(gap, str) and gap.strip() and gap.strip()[:1000] not in gaps:
            gaps.append(gap.strip()[:1000])
    draft['gaps'] = gaps[-most:]


def land_part(draft, meta, content, codec=MARKDOWN):
    """A rewrite of one part as it lands: (part, text before, text after, flag).

    An unknown part, or one changed since the job was asked for, is refused as stale. The
    result loses a repeated heading (or, for the opening, a title line), takes the codec's
    `landed` shape, and is refused when it would start a new part or the part cannot hold
    it. The flag is the guards' line, '' when nothing needs checking."""
    part = meta['part']
    deepest = codec.deepest(draft)
    if part in codec.fixed:
        before = draft.get(part)
        if before is None or fingerprint(before) != meta.get('basis'):
            raise ValueError(stale(codec))
        text = codec.landed(draft, before, opening_text(content))
    else:
        try:
            section = codec.section(draft, part)
        except ValueError:
            raise ValueError(stale(codec)) from None
        before = section['text']
        if fingerprint(before) != meta.get('basis'):
            raise ValueError(stale(codec))
        text = codec.landed(draft, before, clean(content, section['heading']))
    no_heading(text, codec, deepest)
    record.checked_text(part, text, codec, deepest)
    return part, before, text, guards.flags(before, text)


def land_selection(draft, meta, content, codec=MARKDOWN):
    """A selection edit as it lands: (part, the part before, the part after, flag).

    It lands where the person selected while the part is unchanged; otherwise where the
    passage occurs once, or not at all. The passage's own spaces and line breaks stay around
    its replacement, and a one-line part's replacement is put on one line."""
    part, passage, start = meta['part'], meta.get('selection') or '', meta.get('start')
    try:
        whole = codec.text_of(draft, part)
    except ValueError:
        raise ValueError(stale(codec)) from None
    unchanged = fingerprint(whole) == meta.get('basis')
    if not passage:
        raise ValueError(stale(codec))
    if unchanged and type(start) is int and whole[start : start + len(passage)] == passage:
        at = start
    elif whole.count(passage) == 1:
        at = whole.index(passage)
    else:
        raise ValueError(MOVED)
    lead = passage[: len(passage) - len(passage.lstrip())]
    trail = passage[len(passage.rstrip()) :]
    replacement = clean(content)
    if part in codec.single:
        replacement = ' '.join(replacement.split())
    updated = whole[:at] + lead + replacement + trail + whole[at + len(passage) :]
    if part not in codec.single:
        updated = codec.landed(draft, whole, updated)
    deepest = codec.deepest(draft)
    no_heading(replacement, codec, deepest)
    record.checked_text(part, updated, codec, deepest)
    return part, whole, updated, guards.flags(whole, updated)


def land_sections(draft, meta, content, codec=MARKDOWN, divide=None):
    """A whole-draft pass as it lands: ({part: (before, after, flag)}, sections added).

    The opening and every section must be as they were asked about, and every returned id
    known (the opening only when it was sent, not empty). A text left empty or as it was is
    left out. `divide(part, text)` may return (text, new sections) for a part a studio lets
    the pass divide; any other part that would start a new one is refused."""
    if pass_basis(draft, codec) != meta.get('basis'):
        raise ValueError(stale(codec))
    found = section_texts(content)
    sections = {section['id']: section for section in draft['sections']}
    openings = {part for part in _openings(codec) if (draft.get(part) or '').strip()}
    ids = [item['id'] for item in found]
    if len(set(ids)) != len(ids) or any(name not in set(sections) | openings for name in ids):
        raise ValueError(UNKNOWN)
    changes, added = {}, []
    for item in found:
        if item['id'] in openings:
            before, text = draft[item['id']], opening_text(item['text'])
        else:
            section = sections[item['id']]
            before, text = section['text'], clean(item['text'], section['heading'])
        if not text or text == before:
            continue
        text = codec.landed(draft, before, text)
        if text == before:
            continue
        divided = divide(item['id'], text) if divide is not None else None
        if divided is not None:
            text, added = divided
        else:
            no_heading(text, codec, codec.deepest(draft))
        record.checked_text(
            item['id'], text, codec, codec.deepest({'sections': added or draft['sections']})
        )
        changes[item['id']] = (before, text, guards.flags(before, text))
    return changes, added


def settle(job, apply, now):
    """Run `apply()` once and settle the job: applied, or a readable problem whatever went
    wrong, so it never holds up the desk. `now()` is the settling time."""
    try:
        apply()
        job.update(applied=True, error='')
    except ValueError as error:
        job.update(applied=False, error=str(error)[:1000])
    except Exception as error:  # noqa: BLE001 - e.g. a full disk: said, never stuck.
        job.update(applied=False, error=(NOT_SAVED + str(error))[:1000] + NOTHING_CHANGED)
    job['settled_at'] = now()
    return job
