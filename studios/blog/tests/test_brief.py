"""A solution brief: a desk way of its own, written to its own guide, and made in the brand's
template by Harness Brand (a fake one here; no test calls the real tool)."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import os
import unittest
from unittest.mock import patch

import brand_skill
import brief
import desk
import desk_jobs
import studio
from test_desk import RouteCase
from test_desk_start import StartCase

BRAND = {
    'skill': 'synthetic-brand',
    'version': '1.0.0',
    'brand': 'acme',
    'variant': '',
    'contract': {},
    'design': '',
    'voice': '',
}
BRIEF = """# A Synthetic Platform

_Run made-up workloads on your own terms_

Teams run more made-up workloads every year.

The Synthetic Platform runs them in one place.

> **At a glance**
> A made-up platform for made-up workloads.
> - **Reach** – where a workload runs

- [icon: database] **Ready data**: Governed data with context
- [icon: identity] **Known callers**: Every caller has a name
- [icon: security lock] **Locked down**: Nothing connects unasked
- [icon: cost] **Capped spend**: Limits per team

## The risks

Workloads fail in predictable ways.

## The platform

> **Use cases**
> - **Contain** workloads in a locked-down runtime
> Stat: 9 in 10 teams say so. — A survey, 2026

It runs every workload in a sandbox.

- **Sandbox** – nothing connects unasked

## Why us

We have done this before.

## Summary

Workloads need limits.
"""
FAKE_BRAND = """import json, os, sys
from pathlib import Path
# This fake understands '--layout', as Harness Brand 1.3.0 does.
a = sys.argv
run = Path(a[a.index('--run-dir') + 1])
run.mkdir(parents=True)
layout = json.loads(Path(a[a.index('--layout') + 1]).read_text())
log = Path(os.environ['FAKE_BRAND_LOG'])
log.write_text((log.read_text() if log.exists() else '') + json.dumps(layout) + '\\n')
if os.environ.get('FAKE_BRAND_REFUSES'):
    result = {'status': 'error', 'error': os.environ['FAKE_BRAND_REFUSES']}
    (run / 'result.json').write_text(json.dumps(result))
    sys.exit(1)
breaks, bars = layout.get('page_break_before') or [], []
order = ['The risks', 'The platform', 'Why us', 'Summary']  # Two sections to a page.
for bar in layout.get('sidebars') or []:
    at = bar['page_of']
    page = 1 if at is None else 1 + order.index(at) // 2
    page += sum(1 for name in breaks if at is not None and order.index(name) <= order.index(at))
    bars.append({'page_of': at, 'page': page})
pages = [bar['page'] for bar in bars]
(run / 'out.docx').write_bytes(b'word bytes')
(run / 'out.pdf').write_bytes(b'%PDF-1.4 pdf bytes')
before = (layout.get('icon_row') or {}).get('before')
result = {
    'status': 'branded',
    'outputs': {'word': str(run / 'out.docx'), 'pdf': str(run / 'out.pdf')},
    'warnings': ['A made-up warning.'],
    'layout': {
        'rendered': True,
        'pages': int(os.environ.get('FAKE_BRAND_PAGES', '5')),
        'sidebars': bars,
        'sidebars_sharing_a_page': sorted({n for n in pages if pages.count(n) > 1}),
        'subtitle_on_one_line': True,
        'headings': {before: 1} if before else {},
    },
}
(run / 'result.json').write_text(json.dumps(result))
print(json.dumps(result))
"""
FAKE_ICONS = """import json, sys
query = sys.argv[2]
print(json.dumps([] if query.startswith('zz') else [{'id': 'functional-icons.' + query.split()[0]}]))
"""


class BriefCase(StartCase):
    def setUp(self):
        super().setUp()
        chosen = patch.object(brand_skill, 'snapshot', lambda *given, **more: dict(BRAND))
        chosen.start()
        self.addCleanup(chosen.stop)

    def brief(self, **data):
        return self.start(way='brief', point='What the made-up platform does.', **data)

    def written(self, text=BRIEF):
        """A brief whose draft is written, as the desk has it after its draft step."""
        made = self.brief()
        found, draft = desk.split(text), desk.read(self.root, made['id'])
        draft.update(title=found['title'], opening=found['opening'], sections=found['sections'])
        desk._write(
            self.root, made['id'], draft, ['opening'] + [s['id'] for s in found['sections']]
        )
        return made['id']

    def harness(self, layout_option=True):
        folder = self.base / 'harness-brand'
        (folder / 'rebrand/scripts').mkdir(parents=True)
        script = FAKE_BRAND if layout_option else "print('an older Harness Brand')\n"
        (folder / 'rebrand/scripts/brand.py').write_text(script)
        (folder / 'rebrand/scripts/brand_icons.py').write_text(FAKE_ICONS)
        self.log = self.base / 'harness-calls.jsonl'
        environment = patch.dict(
            os.environ, {'HARNESS_BRAND_RUNTIME': str(folder), 'FAKE_BRAND_LOG': str(self.log)}
        )
        environment.start()
        self.addCleanup(environment.stop)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]


class StartTests(BriefCase):
    def test_a_brief_plans_an_outline_then_a_draft_and_is_marked_as_a_brief(self):
        made = self.brief(audience='Platform teams')
        start = desk.read_start(self.root, made['id'])
        self.assertEqual((start['way'], start['steps']), ('brief', ['outline', 'draft']))
        record = studio.read_json(self.folder(made['id']) / 'session.json')
        self.assertEqual(record['brief'], {'template': 'solution-brief'})
        self.assertEqual(record['brand']['brand'], 'acme')
        self.assertTrue(desk_jobs.view(self.root, made['id'])['brief'])

    def test_a_brief_needs_what_it_is_about_and_takes_no_kind_of_post_or_length(self):
        with self.assertRaisesRegex(ValueError, 'what the brief is about'):
            self.start(way='brief', point=' ')
        with self.assertRaisesRegex(ValueError, 'its own shape and length'):
            self.brief(length='short')

    def test_a_blog_is_not_marked_as_a_brief(self):
        made = self.start(way='topic', point='A point.')
        self.assertFalse(desk_jobs.view(self.root, made['id'])['brief'])


class NoBrandTests(StartCase):
    def test_a_brief_needs_a_brand(self):
        with self.assertRaisesRegex(ValueError, 'Choose a brand in Settings'):
            self.start(way='brief', point='What it does.')


class GuidanceTests(BriefCase):
    def guidance(self, job, *more):
        made = self.written() if job is desk_jobs.draft_job else self.brief()['id']
        with patch.object(desk_jobs, '_queue') as queued:
            job(self.root, made, *more)
        return queued.call_args.args[6]

    def test_the_outline_and_draft_are_written_to_the_brief_guide(self):
        for said in (self.guidance(desk_jobs.outline_job), self.guidance(desk_jobs.draft_job, 1)):
            self.assertIn('This is a solution brief, not a blog post.', said)
            self.assertIn('# Solution brief', said)
            self.assertNotIn(desk_jobs._guide('blog-write.md')[:80], said)

    def test_the_writer_is_told_to_use_icons_from_the_brands_library_only(self):
        said = self.guidance(desk_jobs.draft_job, 1)
        self.assertIn("The icons come from the brand's own icon library.", said)
        self.assertIn('Never describe a custom drawing, name an', said)
        self.assertIn('- [icon: database] **AI-ready data**', said)

    def test_a_blog_keeps_its_own_guides(self):
        made = self.start(way='topic', point='A point.')
        with patch.object(desk_jobs, '_queue') as queued:
            desk_jobs.outline_job(self.root, made['id'])
        self.assertNotIn('# Solution brief', queued.call_args.args[6])


class ReadTests(unittest.TestCase):
    def test_sidebars_and_the_icon_row_leave_the_text_for_the_layout(self):
        source, layout, checks = brief.read(BRIEF)
        self.assertTrue(source.startswith('# A Synthetic Platform\n\n_Run made-up workloads'))
        self.assertNotIn('>', source)
        self.assertNotIn('[icon:', source)
        self.assertIn('- **Sandbox** – nothing connects unasked', source)
        self.assertEqual(layout['icon_row']['before'], 'The risks')
        self.assertEqual(
            layout['icon_row']['items'][2],
            {
                'words': 'security lock',
                'label': 'Locked down',
                'detail': 'Nothing connects unasked',
            },
        )
        self.assertEqual([bar['page_of'] for bar in layout['sidebars']], [None, 'The platform'])
        self.assertEqual(
            layout['sidebars'][0]['blocks'],
            [
                {'type': 'heading', 'text': 'At a glance'},
                {'type': 'body', 'text': 'A made-up platform for made-up workloads.'},
                {'type': 'bullet', 'text': '**Reach** – where a workload runs'},
            ],
        )
        self.assertEqual(
            layout['sidebars'][1]['blocks'][-1],
            {'type': 'stat', 'text': '9 in 10 teams say so.', 'attribution': 'A survey, 2026'},
        )
        self.assertEqual(layout['closing_from'], 'Why us')
        self.assertTrue(all(check['passed'] for check in checks), checks)

    def test_what_a_brief_leaves_out_is_reported(self):
        text = BRIEF.replace('- [icon: cost] **Capped spend**: Limits per team\n', '')
        text = text.replace('— A survey, 2026', '').replace('## Why us', '## Who it is for')
        text += '\n## Sources\n\n1. A survey.\n\n![A figure](figure.png)\n'
        failed = {c['label']: c['detail'] for c in brief.read(text)[2] if not c['passed']}
        self.assertEqual(
            set(failed),
            {
                'One row of four icons',
                'Nothing internal',
                'No list of sources',
                'Every pulled figure and quote names its source',
                'No pictures to carry',
            },
        )
        self.assertIn('names 3 icons', failed['One row of four icons'])
        self.assertIn('Who it is for', failed['Nothing internal'])


class RuntimeTests(unittest.TestCase):
    """Harness Brand is found where every studio looks for a brand skill (#505)."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        self.temp = tempfile.TemporaryDirectory(prefix='blog-brief-runtime-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / 'home'
        self.config = self.base / 'studios-config.json'
        environment = patch.dict(
            os.environ,
            {
                'HOME': str(self.home),
                'STUDIOS_CONFIG': str(self.config),
                'BRAND_SKILL_RUNTIME': '',
                'HARNESS_BRAND_RUNTIME': '',
            },
        )
        environment.start()
        self.addCleanup(environment.stop)

    def harness(self, folder):
        (folder / 'rebrand/scripts').mkdir(parents=True)
        (folder / 'rebrand/scripts/brand.py').write_text("options = ['--layout']\n")
        return folder

    def shared(self, **brand):
        self.config.write_text(json.dumps({'schema': 1, 'brand': brand}))

    def test_brand_skill_runtime_comes_before_the_older_variable(self):
        first, older = self.harness(self.base / 'first'), self.harness(self.base / 'older')
        with patch.dict(
            os.environ, {'BRAND_SKILL_RUNTIME': str(first), 'HARNESS_BRAND_RUNTIME': str(older)}
        ):
            self.assertEqual(brief.runtime(), first)
        with patch.dict(os.environ, {'HARNESS_BRAND_RUNTIME': str(older)}):
            self.assertEqual(brief.runtime(), older)
        # One that holds no Harness Brand leaves the older variable to answer.
        with patch.dict(
            os.environ,
            {
                'BRAND_SKILL_RUNTIME': str(self.base / 'nowhere'),
                'HARNESS_BRAND_RUNTIME': str(older),
            },
        ):
            self.assertEqual(brief.runtime(), older)

    def test_the_chosen_brand_skill_comes_before_the_usual_places(self):
        usual = self.harness(self.home / '.agents/skills/harness-brand')
        chosen = self.harness(self.base / 'chosen-harness-brand')
        self.assertEqual(brief.runtime(), usual)
        self.shared(skill=str(chosen))
        self.assertEqual(brief.runtime(), chosen)

    def test_codex_and_cursor_skills_folders_are_looked_in(self):
        for assistant in ('.codex', '.cursor'):
            folder = self.harness(self.home / assistant / 'skills/harness-brand')
            self.assertEqual(brief.runtime(), folder)
            import shutil

            shutil.rmtree(folder)
        with self.assertRaisesRegex(ValueError, 'Harness Brand is not installed'):
            brief.runtime()

    def test_the_brands_repository_setting_is_told_to_harness_brand(self):
        brands = self.base / 'brands'
        brands.mkdir()
        folder = self.harness(self.base / 'harness-brand')
        self.shared(brands=str(brands))
        with patch.object(brief.subprocess, 'run') as ran:
            brief._run(folder, ['brand.py'], 'acme')
        env = ran.call_args.kwargs['env']
        self.assertEqual(
            (env['HARNESS_BRAND_DATA'], env['HARNESS_REBRAND_BRAND']), (str(brands), 'acme')
        )


class MakeTests(BriefCase):
    def test_the_brief_is_laid_out_with_library_icons_and_kept_with_the_blog(self):
        ident = self.written()
        self.harness()
        made = brief.make(self.root, ident)
        first, last = self.calls()[0], self.calls()[-1]
        self.assertEqual(
            [item['icon'] for item in first['icon_row']['items']],
            [
                'functional-icons.database',
                'functional-icons.identity',
                'functional-icons.security',
                'functional-icons.cost',
            ],
        )
        self.assertEqual(made['icons'], [item['icon'] for item in first['icon_row']['items']])
        self.assertEqual(first['closing_from'], 'Why us')
        # Both sidebars landed on page 1, which is the opening's: the later one moved to the
        # next section without a sidebar, and no page break was needed.
        self.assertEqual(len(self.calls()), 2)
        self.assertEqual([bar['page_of'] for bar in last['sidebars']], [None, 'Why us'])
        self.assertEqual(made['page_breaks'], [])
        self.assertEqual(made['pages'], 5)
        self.assertTrue(all(check['passed'] for check in made['checks']), made['checks'])
        self.assertEqual(made['warnings'], ['A made-up warning.'])
        word = made['files']['word']
        self.assertEqual(
            (word['name'], word['content']), ('solution-brief.docx', 'd29yZCBieXRlcw==')
        )
        self.assertTrue(word['path'].startswith(str(self.folder(ident) / 'derived' / 'brief')))
        self.assertEqual(made['files']['pdf']['name'], 'solution-brief.pdf')
        # The draft on the desk still has its sidebars and icon lines.
        self.assertIn('[icon: database]', desk.join(desk.read(self.root, ident), images=False))

    def test_two_sidebars_on_the_final_page_are_left_for_the_person(self):
        moved = BRIEF.replace('## Why us\n', '## Why us\n\n> **Proof**\n> - One\n')
        moved = moved.replace('## Summary\n', '## Summary\n\n> **Next**\n> - Two\n')
        ident = self.written(moved)
        self.harness()
        made = brief.make(self.root, ident)
        # Page 1's clash is settled with a page break; Summary shares the final page by design,
        # so no break is put before it and the clash there is reported.
        self.assertEqual(made['page_breaks'], ['The platform'])
        failed = [check for check in made['checks'] if not check['passed']]
        self.assertEqual([check['label'] for check in failed], ['One sidebar on a page'])

    def test_two_sidebars_on_a_later_page_get_a_page_break_between_them(self):
        layout = {'sidebars': [{'page_of': 'One'}, {'page_of': 'Two'}]}
        placed = {
            'sidebars_sharing_a_page': [2],
            'sidebars': [{'page_of': 'One', 'page': 2}, {'page_of': 'Two', 'page': 2}],
        }
        self.assertTrue(brief._apart(layout, placed, ['One', 'Two', 'Three']))
        self.assertEqual(layout['page_break_before'], ['Two'])
        self.assertFalse(brief._apart(layout, placed, ['One', 'Two', 'Three']))  # Tried already.

    def test_a_sidebar_on_the_openings_page_moves_only_to_the_next_section(self):
        layout = {'sidebars': [{'page_of': None}, {'page_of': 'One'}, {'page_of': 'Two'}]}
        placed = {
            'sidebars_sharing_a_page': [1],
            'sidebars': [{'page_of': None, 'page': 1}, {'page_of': 'One', 'page': 1}],
        }
        # The next section has a sidebar of its own, so this one's section starts a new page.
        self.assertTrue(brief._apart(layout, placed, ['One', 'Two', 'Three']))
        self.assertEqual(layout['page_break_before'], ['One'])
        self.assertEqual([bar['page_of'] for bar in layout['sidebars']], [None, 'One', 'Two'])

    def test_a_long_brief_is_reported_not_shrunk(self):
        ident = self.written()
        self.harness()
        with patch.dict(os.environ, {'FAKE_BRAND_PAGES': '6'}):
            made = brief.make(self.root, ident)
        failed = [check for check in made['checks'] if not check['passed']]
        self.assertEqual([check['label'] for check in failed], ['Four or five pages'])
        self.assertIn('Cut text', failed[0]['detail'])

    def test_an_icon_the_library_lacks_is_named(self):
        ident = self.written(BRIEF.replace('[icon: cost]', '[icon: zzunknown]'))
        self.harness()
        with self.assertRaisesRegex(ValueError, 'no icon for “zzunknown”'):
            brief.make(self.root, ident)
        self.assertFalse(self.log.exists())  # Nothing was laid out.

    def test_harness_brand_missing_or_too_old_says_what_to_install(self):
        ident = self.written()
        with patch.dict(os.environ, {'HARNESS_BRAND_RUNTIME': str(self.base / 'nowhere')}):
            with self.assertRaisesRegex(ValueError, 'Harness Brand is not installed'):
                brief.make(self.root, ident)
        self.harness(layout_option=False)
        with self.assertRaisesRegex(ValueError, 'Update it to 1.3.0'):
            brief.make(self.root, ident)

    def test_a_refusal_from_harness_brand_is_passed_on(self):
        ident = self.written()
        self.harness()
        with patch.dict(os.environ, {'FAKE_BRAND_REFUSES': 'The layout names a heading twice.'}):
            with self.assertRaisesRegex(ValueError, 'names a heading twice'):
                brief.make(self.root, ident)

    def test_a_blog_and_an_unwritten_brief_are_refused(self):
        self.harness()
        blog = self.start(way='topic', point='A point.')
        with self.assertRaisesRegex(ValueError, 'not a solution brief'):
            brief.make(self.root, blog['id'])
        with self.assertRaisesRegex(ValueError, 'Write the draft first'):
            brief.make(self.root, self.brief()['id'])


class RouteTests(BriefCase, RouteCase):
    def setUp(self):
        super().setUp()
        library = patch.dict(os.environ, {'STUDIOS_LIBRARY': str(self.base / 'shared-library')})
        library.start()
        self.addCleanup(library.stop)

    def test_the_page_makes_the_brief_through_its_desk_route(self):
        ident = self.written()
        self.harness()
        found = self.post('desk-brief', {'id': ident})
        self.assertEqual(found['brief_made']['pages'], 5)
        self.assertTrue(found['brief'])

    def test_a_brief_made_is_kept_in_the_document_library_with_its_pdf(self):
        from studio_core import document_library

        ident = self.written()
        self.harness()
        self.assertIsNone(self.get('desk', id=ident)['document_library'])
        found = self.post('desk-brief', {'id': ident})
        self.assertEqual(found['library_copy']['state'], 'kept')
        library = document_library.opened()
        rows = library.catalog(kind='blog')['items']
        self.assertEqual(len(rows), 1)
        kept = library.snapshot(rows[0]['id'], 1)
        self.assertIn('## The risks', kept['text'])
        self.assertEqual(library.download(rows[0]['id'], 1, 'pdf')[2], b'%PDF-1.4 pdf bytes')
        self.assertEqual(found['document_library']['id'], rows[0]['id'])
        self.assertFalse(found['document_library']['older'], 'the brief kept is the draft now')
        # Not published, and no address was asked for.
        self.assertIsNone(found['publication'])

    def test_a_brief_that_is_not_made_is_not_kept(self):
        from studio_core import document_library

        ident = self.written()
        self.harness()
        with patch.dict(os.environ, {'FAKE_BRAND_REFUSES': 'No layout.'}):
            with self.assertRaisesRegex(ValueError, 'No layout'):
                self.post('desk-brief', {'id': ident})
        library = document_library.opened()
        self.assertEqual(library.catalog(kind='blog')['items'] if library else [], [])


if __name__ == '__main__':
    unittest.main()
