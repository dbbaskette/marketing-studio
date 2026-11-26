"""Shared settings' Brand card, set up in one pass (GitHub issue #516).

The page's real script runs over tests/settings_page_harness.js: the installed brands are
looked up when the card is shown and after a save, the brand and variant are offered as the
person types, the brand skill overrides stay closed unless one is set, and the brands folder
says what it holds, with Get brands only for a Git address whose brands are not here yet.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / 'tests/settings_page_harness.js'
INDEX = (ROOT / 'core/studio_core/setup_web/index.html').read_text()

SKILLS = {'skills': [
    {'name': 'Synthetic brand skill', 'path': '/opt/brand-skill', 'brands': [
        {'name': 'Example Co', 'brand': 'example', 'variants': ['light', 'dark']},
        {'name': 'Plain Co', 'brand': 'plain', 'variants': ['light']}]},
    {'name': 'Second brand skill', 'path': '/opt/other-skill', 'brands': [
        {'name': 'Other Co', 'brand': 'other', 'variants': ['night']}]}], 'problem': None}
REMOTE = {'state': 'remote', 'address': 'https://example.com/org/brands.git', 'folder': '/data/brands/brands-1',
          'fetched': False, 'exists': False, 'brands': [], 'read': False}
PROBE = ("$('#probe').textContent = JSON.stringify({open: $('#brand-more').open,"
         " overrides: $('#brand-more-state').textContent,"
         " brands: $('#brand-brand-list').children.map(o => [o.value, o.label]),"
         " variants: $('#brand-variant-list').children.map(o => o.value),"
         " brand: form.elements['brand.brand'].value, variant: form.elements['brand.variant'].value,"
         " skill: form.elements['brand.skill'].value, changes: changesForStep().brand || null});")
READ = ['#probe', '#brand-brands-status', '#brand-catalog-status', '#get-brands-bar', '#get-brands',
        '#brand-variant-hint']


def shown(**brand):
    return {'shared': {'person': {'name': 'Ana'}, 'research': {'sites': []}, 'output': 'pptx',
                       'render': {'previews': None}, 'local': {'root': '/tmp/studios'},
                       'assistant': {'agent': 'claude'}, 'brand': brand},
            'efforts': {'claude': [], '': []}, 'setup': {'done': True}, 'network': None, 'studios': [],
            'computer': None}


@unittest.skipUnless(shutil.which('node'), 'The page journey needs Node.js.')
class BrandCardTests(unittest.TestCase):
    def page(self, steps, **plan):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'steps.json'
            file.write_text(json.dumps({'steps': steps, **plan}))
            done = subprocess.run(['node', str(HARNESS), str(file)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    @staticmethod
    def load(snapshot):
        return {'run': 'snapshot = ' + json.dumps(snapshot) + '; setup = false; fill(); renderHome(); markSaved();'}

    def test_the_card_finds_installed_brands_when_shown_with_no_find_step(self):
        shots = self.page([self.load(shown(brand='example')), {'show': 'settings'}, {'wait': True},
                           {'run': PROBE}, {'snapshot': 'shown', 'read': READ}],
                          responses={'brands': {**SKILLS, 'store': REMOTE}})
        shot = shots['shown']
        probe = json.loads(shot['read']['#probe']['text'])
        self.assertIn('brands', [request['url'].split('/api/')[1] for request in shot['requests']])
        self.assertEqual(probe['brands'], [['example', 'Example Co · Synthetic brand skill'],
                                           ['plain', 'Plain Co · Synthetic brand skill'],
                                           ['other', 'Other Co · Second brand skill']])
        self.assertEqual(probe['variants'], ['light', 'dark'])
        self.assertEqual(shot['read']['#brand-variant-hint']['text'],
                         'Example Co offers light, dark. Leave blank to use light.')
        self.assertEqual(shot['read']['#brand-catalog-status']['text'],
                         '3 installed brands: Example Co, Plain Co, Other Co. Choose one below, then save.')
        self.assertNotIn('find-brands', INDEX)
        # The overrides stay closed while neither is set.
        self.assertEqual((probe['open'], probe['overrides']), (False, '· none set'))

    def test_a_saved_repository_says_its_brands_are_not_fetched_and_offers_the_one_action(self):
        got = {'folder': '/data/brands/brands-1', 'brands': ['example'], 'action': 'cloned'}
        fetched = {**REMOTE, 'fetched': True, 'exists': True, 'brands': ['example'], 'read': True}
        shots = self.page([
            self.load(shown(brands=REMOTE['address'])), {'show': 'settings'}, {'wait': True},
            {'snapshot': 'saved', 'read': READ},
            {'responses': {'brands-repository': {'defer': 'clone'}, 'brands': {**SKILLS, 'store': fetched}}},
            {'press': '#get-brands'}, {'snapshot': 'getting', 'read': READ},
            {'release': 'clone', 'answer': got}, {'wait': True}, {'snapshot': 'got', 'read': READ}],
            responses={'brands': {**SKILLS, 'store': REMOTE}})
        saved = shots['saved']['read']
        self.assertEqual(saved['#brand-brands-status']['text'], 'The brands have not been fetched yet. Get brands '
                         'copies https://example.com/org/brands.git to this computer.')
        self.assertFalse(saved['#get-brands-bar']['hidden'])
        self.assertEqual(saved['#get-brands']['text'], 'Get brands')
        # Its progress: the button is busy and the line says what is being copied.
        getting = shots['getting']['read']
        self.assertEqual(getting['#get-brands']['text'], 'Getting brands…')
        self.assertEqual(getting['#get-brands']['attributes'].get('aria-disabled'), 'true')
        self.assertIn('Copying the brands from https://example.com/org/brands.git', getting['#brand-brands-status']['text'])
        done = shots['got']
        self.assertEqual(done['read']['#brand-brands-status']['text'], '1 brand (example) copied from '
                         'https://example.com/org/brands.git to /data/brands/brands-1.')
        self.assertEqual(done['read']['#get-brands']['text'], 'Update brands')
        self.assertIn('Copied 1 brand (example). Harness Brand reads them from this folder from now on.', done['toasts'])

    def test_a_folder_on_this_computer_is_read_as_part_of_save(self):
        folder = '/work/brands'
        before = {'state': 'following', 'folder': '/elsewhere', 'exists': True, 'brands': ['plain'], 'read': True}
        after = {'state': 'local', 'folder': folder, 'exists': True, 'brands': ['example'], 'read': True}
        saved = {**shown(brands=folder), 'brands_saved': {'folder': folder, 'brands': ['example'], 'action': 'used'}}
        shots = self.page([
            self.load(shown()), {'show': 'settings'}, {'wait': True},
            {'snapshot': 'following', 'read': READ},
            {'run': f"form.elements['brand.brands'].value = '{folder}'; form.elements['brand.brands'].fire('input');"},
            {'snapshot': 'typed', 'read': READ},
            {'responses': {'shared': saved, 'brands': {**SKILLS, 'store': after}}}, {'submit': True}, {'wait': True},
            {'snapshot': 'saved', 'read': READ}],
            responses={'brands': {**SKILLS, 'store': before}})
        self.assertEqual(shots['following']['read']['#brand-brands-status']['text'],
                         'Harness Brand reads 1 brand (plain) from /elsewhere.')
        self.assertTrue(shots['following']['read']['#get-brands-bar']['hidden'])
        self.assertTrue(shots['typed']['read']['#brand-brands-status']['text'].startswith('Save settings to use this brands folder.'))
        result = shots['saved']
        self.assertEqual([request['sent'] for request in result['requests'] if request['url'].endswith('/api/shared')][0]['changes'],
                         {'brand': {'brands': folder}})
        self.assertEqual(result['read']['#brand-brands-status']['text'], 'Harness Brand reads 1 brand (example) from /work/brands.')
        self.assertTrue(result['read']['#get-brands-bar']['hidden'])
        self.assertIn('Harness Brand reads 1 brand (example) from this folder from now on.', result['toasts'])
        # After the save the installed brands are looked up again.
        urls = [request['url'].split('/api/')[1] for request in result['requests']]
        self.assertGreaterEqual(urls[urls.index('shared'):].count('brands'), 1)

    def test_choosing_a_brand_fills_its_variants_and_one_save_keeps_every_key(self):
        shots = self.page([
            self.load(shown(brand='example', variant='dark')), {'show': 'settings'}, {'wait': True},
            {'run': "form.elements['brand.brand'].value = 'plain'; form.elements['brand.brand'].fire('change');" + PROBE},
            {'snapshot': 'plain', 'read': READ},
            {'run': "form.elements['brand.brand'].value = 'other'; form.elements['brand.brand'].fire('change');" + PROBE},
            {'snapshot': 'other', 'read': READ, 'ids': ['save-state']}],
            responses={'brands': {**SKILLS, 'store': None}})
        plain = json.loads(shots['plain']['read']['#probe']['text'])
        # A variant the chosen brand does not have is cleared: blank is its first.
        self.assertEqual((plain['brand'], plain['variant'], plain['variants']), ('plain', '', ['light']))
        other = json.loads(shots['other']['read']['#probe']['text'])
        # A brand only another installed skill offers names that skill, and the overrides open.
        self.assertEqual((other['skill'], other['open'], other['overrides']), ('/opt/other-skill', True, '· one set'))
        # One save sends the brand, the variant cleared from dark, and the skill: each its own key.
        self.assertEqual(other['changes'], {'brand': 'other', 'variant': None, 'skill': '/opt/other-skill'})
        self.assertEqual(shots['other']['words']['save-state'], 'Unsaved changes')

    def test_a_set_override_keeps_the_disclosure_open_and_every_setting_keeps_its_key(self):
        shots = self.page([self.load(shown(repository='https://example.com/team/brand-skill.git')),
                           {'show': 'settings'}, {'run': PROBE}, {'snapshot': 'shown', 'read': ['#probe']}],
                          responses={'brands': {'skills': [], 'problem': 'Node.js is needed to list installed brands.', 'store': None}})
        probe = json.loads(shots['shown']['read']['#probe']['text'])
        self.assertEqual((probe['open'], probe['overrides']), (True, '· one set'))
        for name in ('brand.repository', 'brand.skill', 'brand.brand', 'brand.variant', 'brand.brands'):
            self.assertIn(f'name="{name}"', INDEX)
        # The brand skill overrides sit in the card's one disclosure, and no real company is
        # an example on it.
        card = INDEX[INDEX.index('<section id="brand-part"'):INDEX.index('</section>', INDEX.index('<section id="brand-part"'))]
        more = card[card.index('<details id="brand-more"'):]
        self.assertIn('name="brand.repository"', more)
        self.assertIn('name="brand.skill"', more)
        self.assertNotIn('name="brand.brand"', more)
        self.assertNotIn('tanzu', card.lower())
        for studio in ('Blog Studio', 'Presentation Studio', 'Training Studio', 'Infographic Studio'):
            self.assertIn(studio, card)
        # The card keeps one filled action: Save, at the form's end.
        self.assertNotIn('button-filled', card)

    def test_a_failed_lookup_says_so_and_still_offers_get_brands_for_a_saved_address(self):
        address = 'https://example.com/org/brands.git'
        shots = self.page([self.load(shown(brands=address)), {'show': 'settings'}, {'wait': True},
                           {'snapshot': 'failed', 'read': READ},
                           {'responses': {'brands-repository': {'folder': '/data/brands/b', 'brands': ['example'], 'action': 'cloned'},
                                          'brands': {**SKILLS, 'store': {**REMOTE, 'fetched': True, 'exists': True,
                                                                         'brands': ['example'], 'read': True}}}},
                           {'press': '#get-brands'}, {'wait': True}, {'snapshot': 'got', 'read': READ}],
                          responses={'brands': {'error': 'This page has lost touch with Marketing Studio.'}})
        failed = shots['failed']['read']
        self.assertEqual(failed['#brand-brands-status']['text'],
                         'The brands folder could not be looked at: This page has lost touch with Marketing Studio. '
                         f'Get brands copies {address} to this computer.')
        self.assertFalse(failed['#get-brands-bar']['hidden'])
        self.assertEqual(failed['#get-brands']['text'], 'Get brands')
        self.assertIn('lost touch', failed['#brand-catalog-status']['text'])
        self.assertEqual(shots['got']['read']['#get-brands']['text'], 'Update brands')
        # A failed lookup with a folder on this computer offers nothing to fetch.
        local = self.page([self.load(shown(brands='/work/brands')), {'show': 'settings'}, {'wait': True},
                           {'snapshot': 'failed', 'read': READ}],
                          responses={'brands': {'error': 'Not answered.'}})['failed']['read']
        self.assertEqual(local['#brand-brands-status']['text'], 'The brands folder could not be looked at: Not answered.')
        self.assertTrue(local['#get-brands-bar']['hidden'])

    def test_a_phone_is_told_counts_and_never_a_folder(self):
        shots = self.page([self.load(shown()), {'show': 'settings'}, {'wait': True}, {'snapshot': 'phone', 'read': READ}],
                          responses={'brands': {**SKILLS, 'store': {'state': 'following', 'exists': True, 'read': True, 'count': 2}}})
        self.assertEqual(shots['phone']['read']['#brand-brands-status']['text'], 'Harness Brand reads 2 brands.')

    def test_a_phone_chooses_brands_by_name_and_never_sets_a_skill_folder(self):
        # GitHub issue #539: over the network the lookup names no skill folder.
        unplaced = {'skills': [{'name': skill['name'], 'brands': skill['brands']} for skill in SKILLS['skills']],
                    'problem': None, 'store': {'state': 'following', 'exists': True, 'read': True, 'count': 2}}
        unplaced['skills'][0]['brands'] = [*unplaced['skills'][0]['brands'],
                                           {'name': 'Other Co', 'brand': 'other', 'variants': ['night']}]
        pick = lambda brand: {'run': f"form.elements['brand.brand'].value = '{brand}'; form.elements['brand.brand'].fire('change');" + PROBE}
        shots = self.page([self.load(shown()), {'show': 'settings'}, {'wait': True},
                           pick('other'), {'snapshot': 'both', 'read': READ, 'ids': ['brand-from-field']}],
                          responses={'brands': unplaced})
        both = shots['both']
        # Two skills offer it, but a phone is not asked to choose between folders.
        self.assertTrue(both['hidden']['brand-from-field'])
        self.assertEqual(json.loads(both['read']['#probe']['text'])['skill'], '')
        # A brand only the second skill offers keeps the skill blank, and the card says where it is chosen.
        unplaced['skills'][0]['brands'] = unplaced['skills'][0]['brands'][:2]
        other = self.page([self.load(shown()), {'show': 'settings'}, {'wait': True},
                           pick('other'), {'snapshot': 'other', 'read': READ}],
                          responses={'brands': unplaced})['other']['read']
        probe = json.loads(other['#probe']['text'])
        self.assertEqual((probe['brand'], probe['skill'], probe['changes']), ('other', '', {'brand': 'other'}))
        self.assertEqual(other['#brand-catalog-status']['text'],
                         '3 installed brands: Example Co, Plain Co, Other Co. Choose one below, then save. Other Co comes '
                         'from another installed brand skill, which is chosen on the computer Marketing Studio runs on.')
        # A saved skill folder a phone sent is refused with the lookup's own sentence.
        refused = self.page([self.load(shown(skill='/opt/second')), {'show': 'settings'}, {'wait': True},
                             {'snapshot': 'refused', 'read': READ}],
                            responses={'brands': {'skills': [], 'problem': 'Read only on the computer.', 'store': None}})
        self.assertEqual(refused['refused']['read']['#brand-catalog-status']['text'], 'Read only on the computer.')

    def test_the_brand_skill_always_agrees_with_the_brand_chosen(self):
        both = {'skills': [
            {'name': 'First skill', 'path': '/opt/first', 'brands': [
                {'name': 'Plain Co', 'brand': 'plain', 'variants': ['light']},
                {'name': 'Shared Co', 'brand': 'shared', 'variants': ['light']}]},
            {'name': 'Second skill', 'path': '/opt/second', 'brands': [
                {'name': 'Other Co', 'brand': 'other', 'variants': ['dark']},
                {'name': 'Shared Co', 'brand': 'shared', 'variants': ['dark']}]}], 'problem': None, 'store': None}
        pick = lambda brand: {'run': f"form.elements['brand.brand'].value = '{brand}'; form.elements['brand.brand'].fire('change');" + PROBE}
        from_skill = lambda path: {'run': f"$('#brand-from').value = '{path}'; $('#brand-from').fire('change');" + PROBE}
        shots = self.page([self.load(shown()), {'show': 'settings'}, {'wait': True},
                           pick('other'), {'snapshot': 'other', 'read': ['#probe']},
                           pick('plain'), {'snapshot': 'plain', 'read': ['#probe']},
                           pick('shared'), {'snapshot': 'shared', 'read': ['#probe'], 'ids': ['brand-from-field']},
                           from_skill('/opt/second'), {'snapshot': 'second', 'read': ['#probe', '#brand-variant-hint']},
                           from_skill('/opt/first'), {'snapshot': 'first', 'read': ['#probe']}],
                          responses={'brands': both})
        skill = lambda name: json.loads(shots[name]['read']['#probe']['text'])['skill']
        # A brand only the second skill offers names it; then one the first offers clears it.
        self.assertEqual((skill('other'), skill('plain')), ('/opt/second', ''))
        # A brand both offer asks which, and each answer leaves a matching pair.
        self.assertFalse(shots['shared']['hidden']['brand-from-field'])
        self.assertEqual(skill('shared'), '')
        self.assertEqual(skill('second'), '/opt/second')
        self.assertEqual(shots['second']['read']['#brand-variant-hint']['text'], 'Shared Co offers dark. Leave blank to use dark.')
        self.assertEqual(skill('first'), '')
        # With a saved skill folder, the lookup lists that skill alone, and choosing keeps it.
        kept = self.page([self.load(shown(skill='/opt/second')), {'show': 'settings'}, {'wait': True},
                          pick('other'), {'snapshot': 'kept', 'read': ['#probe']}],
                         responses={'brands': {'skills': [both['skills'][1]], 'problem': None, 'store': None}})
        self.assertEqual(json.loads(kept['kept']['read']['#probe']['text'])['skill'], '/opt/second')

    def test_a_lookup_that_fails_still_lets_a_brand_id_be_typed(self):
        shots = self.page([self.load(shown()), {'show': 'settings'}, {'wait': True},
                           {'snapshot': 'shown', 'read': READ}],
                          responses={'brands': {'error': 'The brand command did not return a readable list.'}})
        self.assertEqual(shots['shown']['read']['#brand-catalog-status']['text'],
                         'The brand command did not return a readable list. You can still enter a brand ID.')


if __name__ == '__main__':
    unittest.main()
