"""One persistent moderator writer; no model, network, or git on the hot path."""
from copy import deepcopy
from harness.isolation import saved_policy
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter

from harness.engine.actions import apply, digest, publish_verified, replay
from harness.engine.commands import prepare
from harness.effects.registry import EffectRegistry
from harness.storage.atomic import save
from harness.storage.locking import acquire_writer
from harness.storage.checkpoint import verify_checkpoint, write_checkpoint
from harness.views.perspective import view
from harness.rendering.decision import render


class RecoveryRequired(RuntimeError):
    def __init__(self, action_status):
        self.action_status = deepcopy(action_status)
        super().__init__('Recovery required before continuing')


class DuelRunner:
    def __init__(self, state_path, game_dir, effects=None):
        self.state_path = Path(state_path).resolve()
        self.game_dir = Path(game_dir).resolve()
        if self.game_dir.parent.parent.name != 'games':
            raise ValueError('Use games/<format>/<id>')
        if self.state_path.is_relative_to(self.game_dir.parent.parent.parent):
            raise ValueError('Private state must stay outside the repository')
        self.lock = acquire_writer(self.state_path, self.game_dir)
        self._recovery_required = False
        self.last_action_status = None
        try:
            self.journal_path = self.state_path.with_name('journal.json')
            self.journal = json.loads(self.journal_path.read_text(encoding="utf-8"))
            self.state = replay(self.journal)
            if self.state != json.loads(self.state_path.read_text(encoding="utf-8")):
                raise ValueError('State cache differs from journal; recover before resuming')
            checkpoint = json.loads(self.state_path.with_name('checkpoint.json').read_text(encoding="utf-8"))
            if verify_checkpoint(checkpoint) != self.state:
                raise ValueError('Checkpoint differs from current journal')
            config = json.loads((self.game_dir / 'game.json').read_text(encoding="utf-8"))
            if (config['id'] != self.state['game_id'] or config['mode'] != self.state['mode']
                    or saved_policy(config) != saved_policy(self.state)):
                raise ValueError('Game directory does not match session')
            from harness.storage.snapshots import collect
            current_assets = collect(self.game_dir)
            for name, asset in checkpoint['assets'].items():
                if current_assets.get(name) != asset:
                    raise ValueError('Game assets differ from saved checkpoint')
            self.configuration = config
            self.assets = checkpoint['assets']
            self.packet = checkpoint.get('decision_packet')
            self.effects = effects or EffectRegistry()
            self._ids = {event['action']['id'] for event in self.journal['events']}
            self._journal_stat = self.journal_path.stat()
            self.timings = []
            from harness.runner.workflow import Workflow
            workflow_path = self.state_path.with_name('workflow.json')
            workflow_data = json.loads(workflow_path.read_text(encoding="utf-8")) if workflow_path.exists() else checkpoint.get('workflow')
            self.workflow = Workflow(self, workflow_data)
        except BaseException:
            self.close()
            raise

    def close(self):
        if not self.lock.closed:
            self.lock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _fresh(self):
        if self.lock.closed:
            raise ValueError('Runner is closed')
        if self._recovery_required:
            raise RecoveryRequired(self.last_action_status)
        now = self.journal_path.stat()
        if (now.st_mtime_ns, now.st_size) != (self._journal_stat.st_mtime_ns, self._journal_stat.st_size):
            raise ValueError('External writer changed the journal; restart runner')

    def context(self, player, card_ids=None, compact=False):
        self._fresh()
        if player not in ('human', 'agent', 'moderator', 'public'):
            raise ValueError('Player must be human or agent')
        permitted = view(self.state, player)
        # The moderator may know a managed human deck order; players never read ahead.
        for details in permitted['players'].values():
            details.pop('remaining_deck_order', None)
        # Chain objects may carry internal resolution choices; give players only public fields.
        permitted['chain'] = [{k: link[k] for k in ('id', 'actor', 'name', 'effect', 'costs', 'targets', 'effect_negated') if k in link}
                              for link in permitted['chain']]
        context = {'perspective': player, 'state': permitted, 'capabilities': self.effects.capabilities(),
                   'decision': deepcopy(permitted['pending_decision'])}
        if self.packet is not None and (player == 'moderator' or player == (self.state.get('pending_decision') or {}).get('actor','human')):
            context['prompt'] = {key: deepcopy(self.packet[key]) for key in
                                 ('decision_id', 'question', 'events', 'awaiting_user', 'hand_refs') if key in self.packet}
            context['prompt']['recommendations'] = [
                {key: move[key] for key in ('label', 'reason')}
                for move in self.packet.get('recommendations', [])]
        context['recent_events'] = [
            {'id': event['action']['id'], 'kind': event['action']['kind'],
             'actor': event['action']['actor'], 'summary': event['action']['public_summary']}
            for event in self.journal['events'][-10:]]
        # Card text only for identities visible in this permitted view, never the full hidden catalog.
        visible_ids = set()
        def collect(value):
            if isinstance(value, dict):
                if 'card_id' in value:
                    visible_ids.add(str(value['card_id']))
                for child in value.values(): collect(child)
            elif isinstance(value, list):
                for child in value: collect(child)
        collect(permitted)
        fields = ('id', 'name', 'type', 'frameType', 'desc', 'race', 'archetype', 'atk', 'def',
                  'level', 'attribute', 'scale', 'linkval', 'linkmarkers', 'pend_desc', 'monster_desc')
        context['cards'] = {}
        for owner in self.state['players'].values():
            for key, card in owner.get('cards', {}).items():
                if key in visible_ids:
                    context['cards'][key] = {field: deepcopy(card[field]) for field in fields if field in card}
        if card_ids is not None:
            if not isinstance(card_ids,list) or any(type(value) not in (int,str) for value in card_ids):
                raise ValueError('Card focus must be a list of IDs')
            allowed={str(value) for value in card_ids}
            context['cards']={key:value for key,value in context['cards'].items() if key in allowed}
        if player=='moderator':
            context['submitted_intentions']=[deepcopy(entry) for entry in self.workflow.data['submissions'].values()
                if entry['status']=='submitted' and entry['revision']==self.state['revision']]
        from harness.runner.context import enrich
        enriched = enrich(self, context, player)
        if compact:
            from harness.runner.agent_context import compact as compact_context
            return compact_context(self, enriched, card_ids)
        return enriched

    def recover(self):
        """Repair projections from the authoritative journal without executing another action."""
        if self.lock.closed:
            raise ValueError('Runner is closed')
        try:
            journal = json.loads(self.journal_path.read_text(encoding="utf-8"))
            state = replay(journal)
            publish_verified(journal, state, self.state_path, self.game_dir, assets=self.assets)
        except Exception:
            self._recovery_required = True
            raise RecoveryRequired(self.last_action_status) from None
        self.journal, self.state = journal, state
        self._ids = {event['action']['id'] for event in journal['events']}
        self._journal_stat = self.journal_path.stat()
        self.packet = json.loads(self.state_path.with_name('checkpoint.json').read_text(encoding="utf-8")).get('decision_packet')
        self._recovery_required = False
        from harness.runner.workflow import Workflow
        workflow_path = self.state_path.with_name('workflow.json')
        self.workflow = Workflow(self, json.loads(workflow_path.read_text(encoding="utf-8")) if workflow_path.exists() else None)
        return {'revision': state['revision'], 'recovered': True, 'last_action': self.last_action_status}

    def record(self, action):
        """Trusted moderator interface, never exposed directly to a player adapter."""
        self._fresh()
        started = perf_counter()
        if action.get('id') in self._ids:
            raise ValueError('Action already recorded')
        updated = apply(self.state, action)
        event = {'recorded_at': datetime.now(timezone.utc).isoformat(),
                 'before_sha256': digest(self.state), 'after_sha256': digest(updated),
                 'action': deepcopy(action)}
        journal = {**self.journal, 'events': self.journal['events'] + [event]}
        # Journal first: replay recovers interrupted projection writes.
        self.last_action_status = {'id': action['id'], 'recorded': False, 'revision': updated['revision']}
        try:
            save(self.journal_path, journal)
            self.last_action_status['recorded'] = True
            self.journal, self.state = journal, updated
            self._ids.add(action['id'])
            self._journal_stat = self.journal_path.stat()
            self.packet = None
            publish_verified(journal, updated, self.state_path, self.game_dir, assets=self.assets)
            self.packet = json.loads(self.state_path.with_name('checkpoint.json').read_text(encoding="utf-8")).get('decision_packet')
        except Exception:
            # A failed write may have reached disk. Check commit status, then block every operation.
            try:
                disk = json.loads(self.journal_path.read_text(encoding="utf-8"))
                self.last_action_status['recorded'] = any(e['action']['id'] == action['id'] for e in disk['events'])
            except Exception:
                self.last_action_status['recorded'] = None
            self._recovery_required = True
            raise RecoveryRequired(self.last_action_status) from None
        self.timings.append((perf_counter() - started) * 1000)
        return {'revision': updated['revision'], 'summary': action['public_summary'],
                'state': view(updated, 'public')}

    def command(self, request):
        self._fresh()
        return self.record(prepare(self.state, request))

    def effect(self, name, request):
        self._fresh()
        return self.record(self.effects.prepare(name, self.state, request))

    def display(self, packet):
        self._fresh()
        text = render(self.state, packet)
        packet = deepcopy(packet)
        packet['hand_refs'] = {f'H{i}': c['instance_id'] for i, c in
                               enumerate(self.state['players']['human']['hand'] or [], 1)}
        try:
            write_checkpoint(self.state_path, self.game_dir, self.journal, packet,
                             _verified_state=self.state, _assets=self.assets)
        except Exception:
            self._recovery_required = True
            raise RecoveryRequired(self.last_action_status) from None
        self.packet = packet
        return text

    def advance(self, next_step, limit=100):
        """Trusted scheduler proposes verified automatic actions; stop at every choice."""
        self._fresh()
        events = []
        for _ in range(limit):
            if self.state['status'] != 'active' or self.state.get('pending_decision') is not None:
                return events
            action = next_step(deepcopy(self.state))
            if action is None:
                return events
            if action.get('automatic') is not True:
                raise ValueError('Scheduler may only propose verified automatic steps')
            events.append(self.record(action)['summary'])
        raise ValueError('Automatic continuation limit reached')
