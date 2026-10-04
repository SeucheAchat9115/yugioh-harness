"""Durable, bounded player dispatch. The host enforces its declared sandbox."""
from copy import deepcopy
import time
from uuid import uuid4
from harness.runner.workflow import fingerprint

MAX_ATTEMPTS = 3
MAX_RESPONSE = 8192
REASONS = {'timeout', 'cancelled', 'malformed', 'transport_error', 'host_shutdown', 'isolation_failed'}


class PlayerTaskError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def validate_isolation(policy):
    if not isinstance(policy, dict) or set(policy) != {'method', 'parent_history', 'tools', 'filesystem', 'evidence'}:
        raise PlayerTaskError('isolation_required')
    if policy['method'] not in ('context-only', 'host-sandbox') or policy['parent_history'] is not False or policy['tools'] != [] or policy['filesystem'] is not False:
        raise PlayerTaskError('isolation_required')
    if not isinstance(policy['evidence'], str) or not policy['evidence'].strip() or len(policy['evidence']) > 500:
        raise PlayerTaskError('isolation_required')


class PlayerTasks:
    def __init__(self, runner, clock=None):
        self.runner = runner
        self.clock = clock or time.time

    @property
    def tasks(self):
        return self.runner.workflow.data.setdefault('player_tasks', {})

    def task(self, task_id):
        self.runner._fresh()
        task = self.tasks.get(task_id)
        if not task:
            raise PlayerTaskError('unknown_task')
        return task

    def current(self, task):
        runner = self.runner
        pending = runner.state.get('pending_decision') or {}
        packet = runner.packet or {}
        if (runner.state['status'] != 'active' or task['revision'] != runner.state['revision'] or
                pending.get('actor') != task['player'] or packet.get('decision_id') != task['decision_id']):
            raise PlayerTaskError('stale_task')

    def refresh(self):
        self.runner._fresh()
        changed = False
        for task in self.tasks.values():
            task.setdefault('attempts', {})
            task.setdefault('status', 'ready')
            attempt = task['attempts'].get(task.get('attempt_id'))
            submitted = self.runner.workflow.data['submissions'].get('player-task-' + task['task_id'])
            if attempt and submitted and task['status'] != 'succeeded':
                # Repair a crash after durable submission but before attempt finalization.
                task['status'] = attempt['status'] = 'succeeded'
                attempt['termination_confirmed'] = True
                changed = True
            elif attempt and attempt['status'] == 'running' and self.clock() >= attempt['deadline']:
                task['status'] = attempt['status'] = 'timed_out'
                attempt['reason'] = 'timeout'
                attempt['termination_confirmed'] = False
                changed = True
        if changed:
            self.runner.workflow.persist()

    def blocking(self):
        self.refresh()
        for task in self.tasks.values():
            attempt = task['attempts'].get(task.get('attempt_id'))
            if attempt and not attempt['termination_confirmed']:
                return task
        return None

    def begin(self, task_id, request_id, isolation, timeout_seconds=60):
        self.runner._fresh()
        validate_isolation(isolation)
        if not isinstance(request_id, str) or not request_id or type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
            raise PlayerTaskError('invalid_dispatch')
        task = self.task(task_id)
        dispatches = self.runner.workflow.data.setdefault('player_dispatches', {})
        digest = fingerprint({'task_id': task_id, 'isolation': isolation, 'timeout_seconds': timeout_seconds})
        existing = dispatches.get(request_id)
        if existing:
            if existing['digest'] != digest:
                raise PlayerTaskError('conflicting_dispatch')
            return {**deepcopy(existing['receipt']), 'dispatch_authorized': False}
        self.current(task)
        if self.blocking():
            raise PlayerTaskError('child_still_active')
        if task['status'] == 'succeeded':
            raise PlayerTaskError('task_completed')
        if self.attempts_used(task) >= MAX_ATTEMPTS:
            raise PlayerTaskError('retry_exhausted')
        identity = uuid4().hex
        deadline = self.clock() + timeout_seconds
        task['attempt_id'] = identity
        task['status'] = 'running'
        task['attempts'][identity] = {'status': 'running', 'deadline': deadline,
            'isolation': deepcopy(isolation), 'termination_confirmed': False}
        receipt = {'task_id': task_id, 'attempt_id': identity, 'deadline': deadline,
                   'player': task['player'], 'decision_id': task['decision_id'], 'revision': task['revision']}
        dispatches[request_id] = {'digest': digest, 'receipt': receipt}
        self.runner.workflow.persist()
        return {**deepcopy(receipt), 'dispatch_authorized': True}

    def attempt(self, task, attempt_id):
        if not isinstance(attempt_id, str) or attempt_id != task.get('attempt_id'):
            raise PlayerTaskError('stale_attempt')
        return task['attempts'][attempt_id]

    def bind(self, task_id, attempt_id, child_id):
        self.refresh()
        task = self.task(task_id)
        attempt = self.attempt(task, attempt_id)
        if not isinstance(child_id, str) or not child_id.strip() or len(child_id) > 256:
            raise PlayerTaskError('invalid_child_id')
        if attempt.get('child_id') == child_id:
            return self.summary(task)
        if attempt.get('child_id') or attempt['status'] != 'running':
            raise PlayerTaskError('conflicting_child_binding')
        attempt['child_id'] = child_id
        self.runner.workflow.persist()
        return self.summary(task)

    def fail(self, task_id, attempt_id, reason, terminated=False):
        self.refresh()
        task = self.task(task_id)
        attempt = self.attempt(task, attempt_id)
        if reason not in REASONS or type(terminated) is not bool:
            raise PlayerTaskError('invalid_failure')
        if attempt['status'] == 'succeeded':
            raise PlayerTaskError('task_completed')
        if attempt.get('reason') and attempt['reason'] != reason:
            raise PlayerTaskError('conflicting_failure')
        status = 'timed_out' if reason == 'timeout' else ('cancelled' if reason == 'cancelled' else 'failed')
        task['status'] = attempt['status'] = status
        attempt['reason'] = reason
        attempt['termination_confirmed'] = attempt['termination_confirmed'] or terminated
        self.runner.workflow.persist()
        return self.summary(task)

    def attempts_used(self, task):
        # Re-presenting a menu at the same actor/revision must not reset the budget.
        return sum(len(item.get('attempts', {})) for item in self.tasks.values()
                   if item['player'] == task['player'] and item['revision'] == task['revision'])

    def summary(self, task):
        attempt = task.get('attempts', {}).get(task.get('attempt_id'), {})
        return {'task_id': task['task_id'], 'attempt_id': task.get('attempt_id'), 'player': task['player'],
                'status': task.get('status', 'ready'), 'reason': attempt.get('reason'),
                'deadline': attempt.get('deadline'), 'child_id': attempt.get('child_id'), 'termination_confirmed': attempt.get('termination_confirmed', True),
                'attempts_used': self.attempts_used(task), 'max_attempts': MAX_ATTEMPTS}

    def result(self, task_id, attempt_id, response):
        self.refresh()
        task = self.task(task_id)
        attempt = self.attempt(task, attempt_id)
        request_id = 'player-task-' + task_id
        if attempt['status'] == 'succeeded':
            return self.runner.workflow.submit(task['decision_id'], request_id, response, task['player'])
        self.current(task)
        if attempt['status'] != 'running':
            raise PlayerTaskError('attempt_not_running')
        if type(response) is int:
            response = str(response)
        valid = isinstance(response, str) and response.strip() and len(response) <= MAX_RESPONSE
        if valid:
            try:
                result = self.runner.workflow.submit(task['decision_id'], request_id, response, task['player'])
            except ValueError:
                valid = False
        if not valid:
            self.fail(task_id, attempt_id, 'malformed')
            raise PlayerTaskError('malformed_player_response')
        task['status'] = attempt['status'] = 'succeeded'
        attempt['termination_confirmed'] = True
        self.runner.workflow.persist()
        return result
