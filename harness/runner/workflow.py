"""Durable numbered decisions, submitted intentions, and retry-safe execution."""
from copy import deepcopy
import hashlib
import json
from uuid import uuid4
from harness.runner.state_tools import build
from harness.storage.atomic import save
from harness.storage.checkpoint import write_checkpoint


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


class Workflow:
    def __init__(self,runner,data=None):
        self.runner=runner
        self.data=deepcopy(data or {'schema_version':'1.0','submissions':{},'executions':{}})
        self.data.setdefault('presentations',{})
        packets = self.data.setdefault('decision_packets', {})
        packet = runner.packet or {}
        if packet.get('decision_id') and packet['decision_id'] not in packets:
            packets[packet['decision_id']] = {
                'actor': (runner.state.get('pending_decision') or {}).get('actor', 'human'),
                **{key: deepcopy(packet[key]) for key in
                   ('decision_id', 'expected_revision', 'role', 'awaiting_user', 'events',
                    'question', 'recommendations', 'option_review', 'hand_refs') if key in packet}}


    def persist(self):
        from harness.runner.duel import RecoveryRequired
        try:
            save(self.runner.state_path.with_name('workflow.json'),self.data)
            from harness.storage.archive import write_decisions
            write_decisions(self.runner.game_dir, self.data)
            write_checkpoint(self.runner.state_path,self.runner.game_dir,self.runner.journal,self.runner.packet,
                             _verified_state=self.runner.state,_assets=self.runner.assets)
        except Exception:
            self.runner._recovery_required=True
            raise RecoveryRequired(self.runner.last_action_status) from None

    def submit(self,decision_id,request_id,response,player='human'):
        self.runner._fresh()
        if not isinstance(request_id,str) or not request_id:raise ValueError('Request ID required')
        if isinstance(response,int) and not isinstance(response,bool):response=str(response)
        payload={'decision_id':decision_id,'response':response,'player':player}
        digest=fingerprint(payload)
        existing=self.data['submissions'].get(request_id)
        if existing:
            if existing['digest']!=digest:raise ValueError('Request ID reused for different input')
            return deepcopy(existing)
        packet=self.runner.packet
        if not packet or packet.get('decision_id')!=decision_id or packet['expected_revision']!=self.runner.state['revision']:
            raise ValueError('Stale or missing decision')
        pending=self.runner.state.get('pending_decision') or {}
        if pending.get('actor')!=player or not packet.get('awaiting_user',True):raise ValueError('Wrong decision actor')
        if any(s['decision_id']==decision_id for s in self.data['submissions'].values()):raise ValueError('Decision already answered')
        if isinstance(response,int) and not isinstance(response,bool):response=str(response)
        if not isinstance(response,str) or not response.strip():raise ValueError('Response must be text or a numbered option')
        intention={'text':response}
        if response.strip().isdigit():
            index=int(response.strip())-1
            moves=packet.get('recommendations',[])
            if index<0 or index>=len(moves):raise ValueError('Unknown numbered option')
            intention={'text':moves[index]['label'],'option':index+1,'details':deepcopy(moves[index])}
        result={'request_id':request_id,'decision_id':decision_id,'player':player,'revision':self.runner.state['revision'],
                'digest':digest,'intention':intention,'status':'submitted'}
        self.data['submissions'][request_id]=result
        self.persist()
        return deepcopy(result)

    def execute(self,request_id,request,submission_id=None):
        self.runner._fresh()
        if not isinstance(request_id,str) or not request_id:raise ValueError('Request ID required')
        digest=fingerprint({'request':request,'submission_id':submission_id})
        existing=self.data['executions'].get(request_id)
        if existing:
            if existing['digest']!=digest:raise ValueError('Request ID reused for different action')
            entry=existing
        else:
            if self.runner.state.get('pending_decision') is not None and submission_id is None and request.get('automatic') is not True:
                raise ValueError('Pending player decisions require submitted input or a verified automatic step')
            if submission_id is not None:
                submission=self.data['submissions'].get(submission_id)
                if not submission or submission['status']!='submitted' or submission['revision']!=self.runner.state['revision']:
                    raise ValueError('Missing, stale, or consumed submission')
            refs=(self.runner.packet or {}).get('hand_refs',{})
            action=build(self.runner.state,request,refs)
            action['id']=f'workflow-{request_id}'
            action['workflow_request_id']=request_id
            action['workflow_digest']=digest
            entry={'digest':digest,'action':action,'action_id':action['id'],'status':'prepared','submission_id':submission_id}
            self.data['executions'][request_id]=entry
            self.persist()
        recorded=next((event for event in self.runner.journal['events'] if event['action']['id']==entry.get('action_id',(entry.get('action') or {}).get('id'))),None)
        if recorded:
            if recorded['action'].get('workflow_digest')!=digest:raise ValueError('Conflicting recorded action')
            result={'revision':recorded['action']['expected_revision']+1,'summary':recorded['action']['public_summary'],'duplicate':True}
        else:
            result=self.runner.record(entry['action'])
            result.pop('state',None)
            result['duplicate']=False
        entry['status']='recorded'
        entry.pop('action',None)
        if submission_id:self.data['submissions'][submission_id]['status']='consumed'
        self.persist()
        result['current_revision']=self.runner.state['revision']
        from harness.views.perspective import view
        result['state']=view(self.runner.state,'public' if self.runner.state['mode']=='agent-vs-agent' else 'human')
        return result

    def present(self,packet):
        self.runner._fresh()
        packet=deepcopy(packet)
        if packet.get('decision_id') is None:
            packet['decision_id']=f"{self.runner.state['game_id']}:{self.runner.state['revision']}:{uuid4().hex}"
        if not isinstance(packet['decision_id'],str) or not packet['decision_id']:
            raise ValueError('Decision ID must be a nonempty string')
        identity=packet['decision_id']
        signature=fingerprint({key:value for key,value in packet.items() if key!='hand_refs'})
        previous=self.data['presentations'].get(identity)
        current=self.runner.packet
        if previous is None and current and current.get('decision_id')==identity:
            previous=fingerprint({key:value for key,value in current.items() if key!='hand_refs'})
        if previous and previous!=signature:raise ValueError('Decision ID reused with different choices')
        actor=(self.runner.state.get('pending_decision') or {}).get('actor','human')
        if packet.get('awaiting_user',True) and self.runner.state.get('pending_decision') is None:
            raise ValueError('Open a player decision window before presenting choices')
        if actor=='agent' or self.runner.state['mode']=='agent-vs-agent':
            from harness.rendering.decision import render
            render(self.runner.state,packet)  # Validate the packet; never expose opponent choice text.
            if packet.get('expected_revision')!=self.runner.state['revision']:raise ValueError('Stale packet')
            prefix='H' if actor=='human' else 'A'
            packet['hand_refs']={f'{prefix}{i}':card['instance_id'] for i,card in enumerate(self.runner.state['players'][actor]['hand'],1)}
            self.runner.packet=packet
            self.persist()
            result={'decision_id':identity,'revision':self.runner.state['revision'],'actor':actor}
        else:
            text=self.runner.display(packet)
            result={'decision_id':identity,'text':text,'revision':self.runner.state['revision'],'actor':actor}
        self.data.setdefault('decision_packets', {})[identity] = {
            'actor': actor, **{key: deepcopy(packet[key]) for key in
            ('decision_id', 'expected_revision', 'role', 'awaiting_user', 'events',
             'question', 'recommendations', 'option_review', 'hand_refs') if key in packet}}
        self.data['presentations'][identity]=signature
        self.persist()
        return result

    def status(self):
        self.runner._fresh()
        from harness.runner.player_tasks import PlayerTasks
        players = PlayerTasks(self.runner)
        players.refresh()
        packet=self.runner.packet or {}
        from harness.isolation import saved_policy
        return {'revision':self.runner.state['revision'],'decision_id':packet.get('decision_id'),
                'isolation_policy': saved_policy(self.runner.state),
                'pending':deepcopy(self.runner.state.get('pending_decision')),
                'player_tasks':[players.summary(task) for task in players.tasks.values()],
                'submissions':[{'request_id':key,'status':value['status']} for key,value in self.data['submissions'].items()],
                'executions':[{'request_id':key,'status':value['status']} for key,value in self.data['executions'].items()]}
