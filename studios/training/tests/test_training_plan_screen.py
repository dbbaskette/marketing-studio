"""Training Studio's actual desk scripts use a single topics decision."""
import test_desk as h

def a_desk_run(state='waiting', sentence='Review topics.', **more):
    run = h.a_desk_run(state, sentence)
    run['body'].update(more)
    return run

a_desk = h.a_desk

PLAN = {'expected': 'plan-v1', 'levels': [{'level': '101', 'objectives': ['Explain a bounded process.'],
    'modules': [{'title': 'How the process works', 'minutes': 15,
      'items': ['The sequence and its constraints.'], 'example': 'A hypothetical worked example.',
      'practice': ['Check: Apply the sequence. | Observe: Explain the result.']}], 'gaps': ''}]}

class TopicsScreenTests(h.ScriptedPage, h.PageCase):
    answers = h.RunnerScreenTests.answers
    posts = h.RunnerScreenTests.posts
    asked = h.RunnerScreenTests.asked
    started = h.RunnerScreenTests.started
    listed = h.RunnerScreenTests.listed
    detail = h.RunnerScreenTests.detail
    on_desk = h.TrainingDeskScreenTests.on_desk
    open_desk = h.TrainingDeskScreenTests.open_desk

    def waiting(self):
        return a_desk_run('waiting', 'Review the training topics.', training_plan=PLAN, training_plan_pending=True)

    def test_one_overview_and_one_primary_action_builds_without_a_sample(self):
        working = a_desk_run('working', 'Writing the guide.', training_plan=None, training_plan_pending=False)
        result = self.open_desk(self.on_desk(a_desk(running=False), self.waiting(), **{
            'POST /api/training-plan': [working]}), [
            {'snapshot': 'topics'}, {'click': 'Build the training'}, {'snapshot': 'working'}], narrow=True)
        shot = result['snapshots']['topics']
        self.assertIn('Here’s what this training will cover', shot['text'])
        self.assertIn('How the process works', shot['text'])
        self.assertIn('Build the training', shot['buttons'])
        self.assertNotIn('Mark this level ready', shot['buttons'])
        self.assertNotIn('Finishing', shot['buttons'])
        self.assertNotIn('Stop training', shot['buttons'])
        self.assertEqual([route for route, body in self.posts(result)], ['/api/training-plan'])
        self.assertEqual(self.posts(result)[0][1]['expected'], 'plan-v1')
        self.assertEqual(self.posts(result)[0][1]['decision'], 'approve')

    def test_a_change_note_survives_polling_and_is_sent_with_the_current_plan(self):
        working = a_desk_run('working', 'Updating the topics.', training_plan=None, training_plan_pending=True)
        result = self.open_desk(self.on_desk(a_desk(running=False), self.waiting(), **{
            'POST /api/training-plan': [working]}), [
            {'click': 'Ask for changes'}, {'snapshot': 'needs-note'},
            {'fill': 'Anything to change?', 'value': 'More depth and a practical exercise.'},
            {'poll': True}, {'snapshot': 'typed'}, {'click': 'Ask for changes'}], narrow=True)
        self.assertIn('Say which topics', result['snapshots']['needs-note']['text'])
        self.assertEqual(result['snapshots']['typed']['fields']['Anything to change?'], 'More depth and a practical exercise.')
        self.assertEqual(self.posts(result)[0][1]['note'], 'More depth and a practical exercise.')
        self.assertEqual(len(self.posts(result)), 1)


# The training outline (#297): drafted from a quick scan, before any research.
OUTLINE = {'mode': 'outline', 'expected': 'outline-v1', 'levels': [], 'separate': [],
    'sections': [
        {'id': 'section-1', 'title': 'How the process works', 'objectives': ['Explain the sequence'],
         'questions': [{'text': 'How does the sequence run?', 'from': 'scan'},
                       {'text': 'What starts each step?', 'from': 'form'}]},
        {'id': 'section-2', 'title': 'Limits', 'objectives': [],
         'questions': [{'text': 'What does the process not promise?', 'from': 'scan'}]}],
    'scan': {'terms': ['sequence'], 'documents': [{'source': 's1', 'title': 'Handbook', 'covers': 'The steps.'}],
             'gaps': ['Nothing on recovery.'], 'pages': [], 'most_pages': 5, 'seconds': 42, 'dollars': 0.12,
             'covers': ['', ''], 'note': 'The quick scan is a first look at the ground, not research.'},
    'limits': {'sections': 12, 'questions': 5, 'objectives': 5, 'separate': 8, 'title': 120, 'text': 300, 'all': 30}}


class OutlineScreenTests(h.ScriptedPage, h.PageCase):
    answers = h.RunnerScreenTests.answers
    posts = h.RunnerScreenTests.posts
    asked = h.RunnerScreenTests.asked
    started = h.RunnerScreenTests.started
    listed = h.RunnerScreenTests.listed
    detail = h.RunnerScreenTests.detail
    on_desk = h.TrainingDeskScreenTests.on_desk
    open_desk = h.TrainingDeskScreenTests.open_desk

    def waiting(self):
        return a_desk_run('waiting', 'Review the training outline.', training_plan=OUTLINE,
                          training_plan_pending=True, outline_first=True)

    def test_the_outline_is_edited_in_place_and_approved_as_edited(self):
        working = a_desk_run('working', 'Researching each section.', training_plan=None,
                             training_plan_pending=False, outline_first=True)
        result = self.open_desk(self.on_desk(a_desk(running=False), self.waiting(), **{
            'POST /api/training-plan': [working]}), [
            {'snapshot': 'outline'},
            {'fill': 'Section title', 'value': 'How batches run'},
            {'click': 'Remove research question 2 of How the process works'},
            {'click': 'Add a section'},
            {'click': 'Approve and start research'}, {'snapshot': 'untitled'},
            {'click': 'Remove section 3'},
            {'poll': True}, {'snapshot': 'polled'},
            {'click': 'Approve and start research'}], narrow=True)
        shot = result['snapshots']['outline']
        self.assertIn('Here’s what this training will cover', shot['text'])
        self.assertIn('From your form', shot['text'])
        self.assertIn('What the quick scan found', shot['text'])
        self.assertIn('Approve and start research', shot['buttons'])
        self.assertNotIn('Build the training', shot['buttons'])
        self.assertNotIn('Mark this level ready', shot['buttons'])
        self.assertIn('Give section 3 a title.', result['snapshots']['untitled']['text'])
        # Sent after the page polled: what was typed survives polling.
        posted = self.posts(result)
        self.assertEqual([route for route, body in posted], ['/api/training-plan'])
        body = posted[0][1]
        self.assertEqual((body['expected'], body['decision']), ('outline-v1', 'approve'))
        sections = body['outline']['sections']
        self.assertEqual([s['title'] for s in sections], ['How batches run', 'Limits'])
        self.assertEqual([q['text'] for q in sections[0]['questions']], ['How does the sequence run?'])

    def test_the_scan_says_it_is_not_research_and_what_it_cost(self):
        result = self.open_desk(self.on_desk(a_desk(running=False), self.waiting()), [
            {'click': 'What the quick scan found'}, {'snapshot': 'found'}], narrow=False)
        text = result['snapshots']['found']['text']
        self.assertIn('not research', text)
        self.assertIn('Handbook: The steps.', text)
        self.assertIn('0 of at most 5 pages.', text)
        self.assertIn('The quick scan took 42 seconds and cost $0.12.', text)

    def test_an_older_stopped_training_switches_only_after_reading_what_it_discards(self):
        offer = {'words': 'Use the outline-first flow: a quick scan drafts the outline.',
                 'confirm': 'Switching discards the research plan and any research not yet accepted.',
                 'expected': 'rev-1', 'discards': {'tries': 1, 'seconds': 60, 'dollars': 1.25}}
        stopped = a_desk_run('failed', 'Research stopped.', outline_offer=offer,
                             problem={'what': 'Research stopped.', 'kept': 'Kept.', 'action': 'retry', 'label': 'Try again'})
        switched = a_desk_run('waiting', 'Switched.', outline_offer=None,
                              problem={'what': 'This training now uses the outline-first flow.', 'kept': 'Kept.',
                                       'action': 'retry', 'label': 'Continue'})
        result = self.open_desk(self.on_desk(a_desk(running=False), stopped, **{
            'POST /api/outline-first': [switched]}), [
            {'snapshot': 'offered'}, {'click': 'Use the outline-first flow…'}, {'snapshot': 'confirm'},
            {'click': 'Keep the current flow'}, {'snapshot': 'kept'},
            {'click': 'Use the outline-first flow…'}, {'click': 'Discard and switch'}, {'snapshot': 'switched'}],
            narrow=True)
        self.assertIn('Try the outline-first flow', result['snapshots']['offered']['text'])
        self.assertNotIn('Discard and switch', result['snapshots']['offered']['buttons'])
        self.assertIn('Switching discards the research plan', result['snapshots']['confirm']['text'])
        self.assertNotIn('Discard and switch', result['snapshots']['kept']['buttons'])
        posted = self.posts(result)
        self.assertEqual(posted, [('/api/outline-first', {'path': posted[0][1]['path'], 'expected': 'rev-1', 'confirmed': True})])
        self.assertNotIn('Try the outline-first flow', result['snapshots']['switched']['text'])
