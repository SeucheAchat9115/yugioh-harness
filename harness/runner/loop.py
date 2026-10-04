"""Host-driven LLM/player decision loop; no coded rules or model vendor dependency."""
from copy import deepcopy
from time import perf_counter
from uuid import uuid4


class DuelLoop:
    def __init__(self,runner,moderator,players=None):
        self.runner=runner
        self.moderator=moderator
        self.players=players or {}
        self.metrics=[]

    def ask(self,stage,intention=None):
        started=perf_counter()
        request={'stage':stage,'context':self.runner.context('moderator'),'intention':deepcopy(intention)}
        result=self.moderator(deepcopy(request))
        self.metrics.append({'stage':stage,'elapsed_ms':(perf_counter()-started)*1000})
        if not isinstance(result,dict):raise ValueError('Moderator must return a plan object')
        return result

    def run(self,max_steps=100):
        events=[]
        for _ in range(max_steps):
            if self.runner.state['status'] in ('paused','finished'):
                from harness.rendering.decision import render
                packet={'expected_revision':self.runner.state['revision'],'awaiting_user':False,
                        'events':events,'recommendations':[],'role':'Moderator',
                        'option_review':{'complete':False,'meaningful_choices':None}}
                return {'status':self.runner.state['status'],'events':events,
                        'text':render(self.runner.state,packet),'state':self.runner.context('human')['state'],
                        'metrics':deepcopy(self.metrics)}
            pending=self.runner.state.get('pending_decision')
            packet=self.runner.packet
            if pending and packet and packet['expected_revision']==self.runner.state['revision'] and packet.get('decision_id'):
                actor=pending['actor']
                submission=next((entry for entry in self.runner.workflow.data['submissions'].values()
                                 if entry['decision_id']==packet['decision_id'] and entry['status']=='submitted'),None)
                if submission is None:
                    adapter=self.players.get(actor)
                    if adapter is None:
                        result={'status':'awaiting_input','player':actor,'decision_id':packet['decision_id'],
                                'context':self.runner.context(actor),'events':events,'metrics':deepcopy(self.metrics)}
                        if actor=='human':
                            from harness.rendering.decision import render
                            shown=deepcopy(packet)
                            shown['events']=list(dict.fromkeys(packet.get('events',[])+events))
                            result['text']=render(self.runner.state,shown)
                        return result
                    started=perf_counter()
                    choice=adapter.choose(self.runner.context(actor))
                    self.metrics.append({'stage':f'{actor}_choose','elapsed_ms':(perf_counter()-started)*1000})
                    submission=self.runner.workflow.submit(packet['decision_id'],choice.get('request_id',uuid4().hex),choice['response'],actor)
                plan=self.ask('review_intent',submission)
                if plan.get('rejected'):
                    # Retain submitted intent for clarification; never silently pick another action.
                    return {'status':'clarification_required','decision_id':packet['decision_id'],'events':events,
                            'context':self.runner.context(actor)}
                result=self.runner.workflow.execute(plan.get('request_id',uuid4().hex),plan['action'],submission['request_id'])
                events.append(result['summary'])
                continue
            plan=self.ask('next_step')
            if 'packet' in plan:
                packet=deepcopy(plan['packet'])
                packet.setdefault('events',events)
                self.runner.workflow.present(packet)
                continue
            request=plan.get('action')
            if request is None:raise ValueError('Moderator must present a decision or an automatic step')
            if request.get('automatic') is not True:raise ValueError('Unprompted steps require a verified no-choice review')
            result=self.runner.workflow.execute(plan.get('request_id',uuid4().hex),request)
            events.append(result['summary'])
        raise ValueError('Decision loop step limit reached')
