import helpers  # noqa: F401
import hub
from test_runner_gitstate import WorkspaceCase, git
from runner import decks, gitstate

BRANDS = [{'brand': 'acme', 'variants': ['light']}]
FORM = {'route': 'scratch', 'title': 'Spring AI', 'brand': 'acme', 'variant': 'light',
        'output': 'google'}


class RemoteIdTests(WorkspaceCase):
    def test_id_taken_on_remote_only(self):
        self.be('blake')
        mine = self.join()
        self.be('alex')
        theirs = self.join()
        root = decks.create(theirs, decks.check_form(FORM, BRANDS))
        # create() alone is the intermediate record before the engine assigns an agent.
        # Model a completed, idle saved run before another person fetches it.
        record = decks.read_run(root)
        record['agent'] = 'claude'
        decks.write_run(root, record)
        gitstate.commit(theirs, 'Complete the saved run setup', [root.name])
        gitstate.sync(theirs)
        self.be('blake')
        hub.run(mine.repo, 'fetch', '--quiet')       # tracking ref ahead; nothing merged
        self.assertFalse(mine.deck('spring-ai').exists())
        self.assertEqual(decks.deck_id(mine, 'Spring AI'), 'spring-ai-2')
        self.assertEqual(decks.create(mine, decks.check_form(FORM, BRANDS)).name,
                         'spring-ai-2')
