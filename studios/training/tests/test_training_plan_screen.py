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
