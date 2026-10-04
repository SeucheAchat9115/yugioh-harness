"""Sequential host tasks: one moderator conversation, context-only player children."""
from copy import deepcopy
from uuid import uuid4
from harness.rendering.decision import render
from harness.runner.player_tasks import PlayerTasks

PLAYER_POLICY = ('You are a Yu-Gi-Oh! player, not the moderator. Choose one intention '
                 'using only the supplied context and card text. Return response as a '
                 'number or free text. Do not mutate state, inspect files, call moderator '
                 'tools, or use parent/sibling conversation history.')


class Orchestrator:
    def __init__(self, runner, clock=None):
        self.runner = runner
        self.players = PlayerTasks(runner, clock)

    def progress_text(self):
        return render(self.runner.state, {'expected_revision': self.runner.state['revision'],
            'awaiting_user': self.runner.state['status'] == 'active', 'observer': True,
            'role': 'Moderator', 'recommendations': [],
            'events': [event['summary'] for event in self.runner.context('public')['recent_events']]})

    def next(self):
        runner = self.runner
        runner._fresh()
        blocking = self.players.blocking()
        if blocking:
            info = self.players.summary(blocking)
            if info['status'] != 'running':
                return {'kind': 'subagent_failure', **info, 'text': self.progress_text()}
            # Never return a fresh dispatch while any child is already running.
            return {'kind': 'subagent_wait', **info, 'text': self.progress_text()}
        if runner.state['status'] in ('paused', 'finished'):
            packet = {'expected_revision': runner.state['revision'], 'awaiting_user': False,
                      'recommendations': [], 'events': [event['summary'] for event in runner.context('public')['recent_events']]}
            return {'kind': runner.state['status'], 'text': render(runner.state, packet), 'context': runner.context('public' if runner.state['mode'] == 'agent-vs-agent' else 'human')}
        pending = runner.state.get('pending_decision')
        packet = runner.packet
        if not pending or not packet or packet['expected_revision'] != runner.state['revision'] or not packet.get('awaiting_user', True):
            return {'kind': 'moderator', 'stage': 'next_step', 'context': runner.context('moderator')}
        identity = packet['decision_id']
        submission = next((entry for entry in runner.workflow.data['submissions'].values()
                           if entry['decision_id'] == identity and entry['status'] == 'submitted'), None)
        if submission:
            return {'kind': 'moderator', 'stage': 'review_intent', 'intention': deepcopy(submission),
                    'context': runner.context('moderator')}
        actor = pending['actor']
        if actor == 'human' and runner.state['mode'] != 'agent-vs-agent':
            return {'kind': 'human', 'decision_id': identity, 'text': render(runner.state, packet)}
        tasks = runner.workflow.data.setdefault('player_tasks', {})
        task = next((item for item in tasks.values() if item['decision_id'] == identity), None)
        if task is None:
            task = {'task_id': uuid4().hex, 'decision_id': identity,
                    'revision': runner.state['revision'], 'player': actor}
            tasks[task['task_id']] = task
            runner.workflow.persist()
        if task.get('status') in ('failed', 'cancelled', 'timed_out'):
            return {'kind': 'subagent_failure', **self.players.summary(task), 'text': self.progress_text()}
        return {'kind': 'subagent', 'task_id': task['task_id'], 'decision_id': task['decision_id'],
                'revision': task['revision'], 'player': actor, 'instructions': PLAYER_POLICY,
                'context': runner.context(actor)}

    def agent_result(self, task_id, attempt_id, response):
        return self.players.result(task_id, attempt_id, response)

    def human_reply(self, decision_id, request_id, response):
        if self.runner.state['mode'] == 'agent-vs-agent':
            raise ValueError('No human player in this mode')
        return self.runner.workflow.submit(decision_id, request_id, response, 'human')
