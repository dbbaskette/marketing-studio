"""Images on the desk, from the review of the first version: data a job never sees but
must never lose, labels that clash, limits, records read on a computer that does not drive
the blog, recovery, and Finishing. No assistant runs: results are written by hand."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import json
import secrets
import time
import unittest
from unittest.mock import patch

import desk
import desk_finish
import desk_images
import desk_jobs
import studio
import tool_jobs
from test_desk import GOOGLE, IMAGE_ONE, IMAGE_TWO, RouteCase, json_text, stored

CODE = 'data:image/png;base64,' + 'C' * 120


class ImageCase(RouteCase):
    def make(self, manuscript, **extra):
        return self.post(
            'desk-create',
            {'operation': secrets.token_hex(16), 'title': 'T', 'manuscript': manuscript, **extra},
        )

    def settle(self, job_id, content):
        job = tool_jobs.read(self.root, job_id)
        job.update(status='ready', result={'content': content, 'notes': ''}, finished_at='x')
        tool_jobs.write(self.root, job)
        desk_jobs.settle(self.root, job['metadata']['article'])
        return tool_jobs.read(self.root, job_id)

    def note(self, made, part, note='Tighten.'):
        shown = self.post('desk-note', {'id': made['id'], 'seen': 1, 'part': part, 'note': note})
        return tool_jobs.read(self.root, shown['working']['id'])


class DataInCodeTests(ImageCase):
    """Image data a part keeps as text (code, raw HTML, a quoted definition) goes to a job as
    a named token and comes back exactly; a result that loses or changes one is refused."""

    TEXT = (
        'Example:\n\n```html\n<img src="' + CODE + '">\n```\n\n'
        '> [x]: <' + CODE + '>\n\n    ![y](' + CODE + ')\n\nEnd.'
    )

    def made(self):
        made = self.make('# T\n\nOpen.\n\n## Code\n\n' + self.TEXT + '\n')
        self.assertEqual(made['sections'][0]['text'], self.TEXT)
        return made, made['sections'][0]['id']

    def test_a_rewrite_that_keeps_each_token_lands_with_the_data_exactly(self):
        made, part = self.made()
        job = self.note(made, part)
        sent = job['payload']['part']['text']
        self.assertNotIn('data:image', json.dumps(job['payload']))
        self.assertEqual(sent.count(desk_images.TOKEN), 3)
        landed = self.settle(job['id'], sent.replace('Example:', 'For example:'))
        self.assertTrue(landed['applied'], landed['error'])
        text = desk.read(self.root, made['id'])['sections'][0]['text']
        self.assertEqual(text, self.TEXT.replace('Example:', 'For example:'))

    def test_a_result_that_loses_or_changes_a_token_is_refused(self):
        made, part = self.made()
        for change in (
            lambda sent: sent.split('```\n\n')[1],  # The code block dropped.
            lambda sent: sent.replace(desk_images.TOKEN, desk_images.TOKEN + 'x', 1),
        ):
            job = self.note(made, part)
            landed = self.settle(job['id'], change(job['payload']['part']['text']))
            self.assertFalse(landed['applied'])
            self.assertIn('image data', landed['error'])
            self.assertEqual(desk.read(self.root, made['id'])['sections'][0]['text'], self.TEXT)

    def test_a_selection_around_data_in_code_keeps_it(self):
        made, part = self.made()
        shown = self.post(
            'desk-selection',
            {'id': made['id'], 'seen': 1, 'part': part, 'text': 'End.', 'action': 'fix'},
        )
        job = tool_jobs.read(self.root, shown['working']['id'])
        self.assertNotIn('data:image', json.dumps(job['payload']))
        self.settle(job['id'], 'The end.')
        self.assertEqual(
            desk.read(self.root, made['id'])['sections'][0]['text'],
            self.TEXT.replace('End.', 'The end.'),
        )

    def test_a_voice_rewrite_carries_tokens_and_apply_puts_the_data_back(self):
        import article_tools

        made, part = self.made()
        guide = article_tools.save_profile(
            self.root,
            {'name': 'Plain', 'guide': 'Plain words.', 'status': 'confirmed', 'confirmed': True},
        )['profile']
        shown = self.post(
            'desk-finish', {'id': made['id'], 'seen': 1, 'tool': 'voice', 'guide': guide}
        )
        job = tool_jobs.read(self.root, shown['working']['id'])
        sent = [s for s in job['payload']['sections'] if s['id'] == part][0]['text']
        rewritten = sent.replace('Example:', 'For instance:')
        self.settle(job['id'], json.dumps({'parts': [{'part': part, 'text': rewritten}]}))
        view = self.get('desk', id=made['id'])
        self.assertNotIn('data:image', json_text(view['finishing']))
        set_ = view['finishing']['voice']
        self.post(
            'desk-apply',
            {
                'id': made['id'],
                'seen': view['revision'],
                'job': set_['job'],
                'items': [{'id': 'p1'}],
            },
        )
        self.assertEqual(
            desk.read(self.root, made['id'])['sections'][0]['text'],
            self.TEXT.replace('Example:', 'For instance:'),
        )

    def test_inline_code_and_indented_code_are_text(self):
        for text in (
            '# T\n\nUse `![x](' + CODE + ')` like so.\n',
            '# T\n\nText:\n\n    ![x](' + CODE + ')\n    [image1]: <' + CODE + '>\n\nAfter.\n',
        ):
            found = desk.split(text)
            self.assertEqual(found['images'], {})
            self.assertEqual(desk.join(found), text)


class LabelTests(ImageCase):
    def test_a_pasted_definition_with_a_label_in_use_gets_its_own(self):
        made = self.make('# T\n\nOpen ![][image1]\n\n## S\n\nx\n\n[image1]: <' + IMAGE_ONE + '>\n')
        part = made['sections'][0]['id']
        saved = self.post(
            'desk-save',
            {
                'id': made['id'],
                'seen': 1,
                'part': part,
                'text': 'From another Doc: ![][image1]\n\n[image1]: <' + IMAGE_TWO + '>',
            },
        )
        self.assertEqual(saved['sections'][0]['text'], 'From another Doc: ![][image2]')
        self.assertEqual(saved['opening'], 'Open ![][image1]')
        self.assertEqual(stored(self, made['id']), {'image1': IMAGE_ONE, 'image2': IMAGE_TWO})

    def test_restoring_an_older_version_never_changes_another_parts_image(self):
        made = self.make('# T\n\nOpen ![][image1]\n\n## S\n\nx\n\n[image1]: <' + IMAGE_ONE + '>\n')
        part = made['sections'][0]['id']
        with studio.locked(self.root):
            desk.keep(
                self.root,
                made['id'],
                part,
                'x ![][image1]\n\n[image1]: <' + IMAGE_TWO + '>',
                'save',
            )
        self.post('desk-restore', {'id': made['id'], 'seen': 1, 'part': part, 'index': 0})
        draft = desk.read(self.root, made['id'])
        self.assertEqual(
            (draft['opening'], draft['sections'][0]['text']), ('Open ![][image1]', 'x ![][image2]')
        )
        self.assertEqual(stored(self, made['id']), {'image1': IMAGE_ONE, 'image2': IMAGE_TWO})

    def test_the_first_of_two_definitions_of_one_label_wins(self):
        text = (
            '# T\n\n![][image1]\n\n[image1]: <' + IMAGE_ONE + '>\n\n[image1]: <' + IMAGE_TWO + '>\n'
        )
        found = desk.split(text)
        self.assertEqual(found['images']['image1']['uri'], IMAGE_ONE)


class LimitTests(ImageCase):
    def test_a_new_image_near_the_total_is_kept_and_an_unused_one_goes(self):
        big = 'data:image/png;base64,' + 'A' * 1000
        unused = 'data:image/png;base64,' + 'U' * 300
        new = 'data:image/png;base64,' + 'N' * 500
        made = self.make(
            '# T\n\nOpen ![][image1]\n\n## S\n\nx ![][image2]\n\n[image1]: <' + big + '>\n\n'
            '[image2]: <' + unused + '>\n'
        )
        part = made['sections'][0]['id']
        shown = self.post('desk-save', {'id': made['id'], 'seen': 1, 'part': part, 'text': 'x'})
        with patch.object(desk_images, 'TOTAL', 1700):
            shown = self.post(
                'desk-save',
                {
                    'id': made['id'],
                    'seen': shown['revision'],
                    'part': part,
                    'text': 'x ![new](' + new + ')',
                },
            )
            self.assertEqual(shown['missing_images'], [])
            self.assertEqual(stored(self, made['id']), {'image1': big, 'image3': new})
            with self.assertRaisesRegex(ValueError, 'more than 12 MB together'):
                self.post(
                    'desk-save',
                    {
                        'id': made['id'],
                        'seen': shown['revision'],
                        'part': 'opening',
                        'text': 'Open ![][image1] ![](' + new.replace('N', 'M') + ')',
                    },
                )

    def test_bringing_back_a_section_respects_the_limits(self):
        made = self.make('# T\n\nOpen.\n\n## S\n\nx\n\n## Gone\n\ny\n')
        draft = desk.read(self.root, made['id'])
        rows = [{'id': s['id'], 'heading': s['heading']} for s in draft['sections'][:1]]
        shown = self.post('desk-outline-save', {'id': made['id'], 'seen': 1, 'sections': rows})
        removed = desk.removed(self.root, made['id'])
        removed[0]['text'] = 'y ![](data:image/png;base64,' + 'A' * (6 * 1024 * 1024) + ')'
        with studio.locked(self.root):
            studio.write_json(self.folder(made['id']) / 'desk' / 'removed.json', removed)
        with self.assertRaisesRegex(ValueError, 'larger than 5 MB'):
            self.post('desk-unremove', {'id': made['id'], 'seen': shown['revision'], 'index': 0})

    def test_a_start_keeps_no_image_data_in_its_notes(self):
        made = self.post(
            'desk-create',
            {
                'operation': secrets.token_hex(16),
                'title': 'T',
                'way': 'shape',
                'outline': '- One\n- Two ![][image1]\n\n[image1]: <' + IMAGE_ONE + '>\n',
            },
        )
        start = (self.folder(made['id']) / 'desk' / 'start.json').read_text()
        self.assertNotIn('data:image', start)


class ElsewhereTests(ImageCase):
    """A record read where it cannot be written, and image data that went missing."""

    def legacy(self):
        made = self.make(GOOGLE)
        directory = self.folder(made['id'])
        draft = studio.read_json(directory / 'desk' / 'draft.json')
        draft.pop('images')
        draft['opening'] += '\n\n[image1]: <' + IMAGE_ONE + '>\n\n[image2]: <' + IMAGE_TWO + '>'
        studio.write_json(directory / 'desk' / 'draft.json', draft)
        (directory / 'desk' / 'images.json').unlink()
        return made

    def test_a_computer_that_does_not_drive_the_blog_serves_and_remembers_the_clean_record(self):
        made = self.legacy()
        target = self.folder(made['id']) / 'desk' / 'draft.json'
        before = target.read_bytes()
        refused = ValueError('Another computer drives this blog.')
        with patch('team_workspace.guard', side_effect=refused):
            with patch('desk_images.moved_out', wraps=desk_images.moved_out) as moved:
                shown = self.get('desk', id=made['id'])
                self.get('desk', id=made['id'])
                self.assertEqual(moved.call_count, 1)
            served = self.get('desk-images', id=made['id'])
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(shown['missing_images'], [])
        self.assertEqual({image['uri'] for image in served['images']}, {IMAGE_ONE, IMAGE_TWO})

    def test_an_image_listed_without_its_data_is_missing_and_bad_data_is_skipped(self):
        made = self.make(GOOGLE)
        images = self.folder(made['id']) / 'desk' / 'images.json'
        original = self.folder(made['id']) / 'ORIGINAL.md'
        original.write_text('# T\n')  # Nowhere else to find it, for now.
        studio.write_json(images, {'image1': IMAGE_ONE, 'image2': 'data:image/png;base64,AA>"x'})
        with patch('team_workspace.guard', side_effect=ValueError('elsewhere')):
            shown = self.get('desk', id=made['id'])
            self.assertEqual(shown['missing_images'], ['image2'])
            self.assertEqual(len(self.get('desk-images', id=made['id'])['images']), 1)
        # The driving computer looks for it where it was last written.
        original.write_text(GOOGLE)
        shown = self.get('desk', id=made['id'])
        self.assertEqual(shown['missing_images'], [])
        self.assertEqual(stored(self, made['id'])['image2'], IMAGE_TWO)

    def test_recovery_takes_the_newest_version_of_any_part_then_the_original(self):
        made = self.make('# T\n\nOpen ![][image1]\n\n## S\n\nx\n\n[image1]: <' + IMAGE_ONE + '>\n')
        part = made['sections'][0]['id']
        with studio.locked(self.root):
            desk.keep(
                self.root,
                made['id'],
                'opening',
                'Old ![][image1]\n\n[image1]: <' + CODE + '>',
                'save',
            )
            time.sleep(0.01)
            desk.keep(self.root, made['id'], part, 'x\n\n[image1]: <' + IMAGE_TWO + '>', 'save')
        directory = self.folder(made['id'])
        draft = studio.read_json(directory / 'desk' / 'draft.json')
        draft['images'] = {}
        studio.write_json(directory / 'desk' / 'draft.json', draft)
        studio.write_json(directory / 'desk' / 'images.json', {})
        self.get('desk', id=made['id'])
        self.assertEqual(stored(self, made['id']), {'image1': IMAGE_TWO})

    def test_finding_what_is_missing_is_quick_with_many_references(self):
        refs = ' '.join('![][x%d]' % n for n in range(20_000))
        began = time.monotonic()
        self.assertEqual(
            len(desk_images.missing({'title': '', 'opening': refs, 'sections': []})), 20_000
        )
        self.assertLess(time.monotonic() - began, 2)


class ElsewhereInTheDeskTests(ImageCase):
    def test_finishing_apply_never_drops_an_image_reference(self):
        made = self.make(GOOGLE)
        job = secrets.token_hex(16)
        with studio.locked(self.root):
            desk_finish.keep(
                self.root,
                made['id'],
                job,
                'finish-humanize',
                [
                    {
                        'part': 'opening',
                        'before': 'An opening paragraph.\n\n![][image1]',
                        'after': 'A first paragraph.',
                        'flag': desk_finish.STRUCTURE,
                    }
                ],
            )
        self.post('desk-apply', {'id': made['id'], 'seen': 1, 'job': job, 'items': [{'id': 'p1'}]})
        opening = desk.read(self.root, made['id'])['opening']
        self.assertIn('A first paragraph.\n\n![][image1]', opening)

    def test_a_repurposed_copy_takes_the_images_it_names(self):
        made = self.make(GOOGLE)
        job = tool_jobs.create(
            self.root,
            secrets.token_hex(16),
            'repurpose',
            {'source': 'x'},
            'g',
            basis=None,
            metadata={'article': made['id'], 'format': 'linkedin'},
        )
        job = tool_jobs.read(self.root, job['id'])
        job.update(status='ready', result={'content': 'Copy.\n\n![][image2]', 'notes': ''})
        tool_jobs.write(self.root, job)
        shown = self.post(
            'desk-repurpose',
            {
                'id': made['id'],
                'job': job['id'],
                'title': 'Copy',
                'content': 'Copy.\n\n![][image2]',
            },
        )
        new = self.get('desk', id=shown['made']['id'])
        self.assertEqual(new['missing_images'], [])
        self.assertEqual(stored(self, shown['made']['id']), {'image2': IMAGE_TWO})


class KeptTests(unittest.TestCase):
    images = {'image1': {}, 'image2': {}}

    def test_a_reference_dropped_from_a_list_goes_back_into_its_item(self):
        self.assertEqual(
            desk_images.kept('- a ![][image1]\n- b', '- a\n- b', self.images),
            '- a ![][image1]\n- b',
        )

    def test_windows_line_endings_in_a_result_are_read(self):
        self.assertEqual(
            desk_images.kept('A\n\n![][image1]\n\nB', 'A\r\n\r\nB', self.images),
            'A\n\n![][image1]\n\nB',
        )


if __name__ == '__main__':
    unittest.main()
