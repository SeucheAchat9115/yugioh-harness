"""One local runner, three role-bound connections for independent agent clients."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import secrets
import os
import time
from uuid import uuid4
import threading
from harness.runner.duel import DuelRunner
from harness.__main__ import respond
from harness.storage.atomic import save


class Arena:
    def __init__(self, runner, credentials):
        self.runner=runner
        self.credentials=credentials
        self.mutex=threading.Lock()

    def request(self, token, request):
        role=next((role for role,value in self.credentials.items()
                   if isinstance(token,str) and secrets.compare_digest(token,value)),None)
        if role is None:
            return {'ok':False,'error':{'code':'unauthorized','message':'Invalid arena credential.'}}
        if not isinstance(request,dict):
            return {'ok':False,'error':{'code':'invalid_request','message':'Request must be an object.'}}
        request=deepcopy(request)
        operation=request.get('op')
        if role!='moderator':
            if operation not in ('view','submit','status') or request.get('player',role)!=role:
                return {'ok':False,'error':{'code':'role_forbidden','message':'Player connection is restricted to its own decisions.'}}
            if operation in ('view','submit'):request['player']=role
        with self.mutex:
            if role!='moderator' and operation=='status':
                try:
                    self.runner._fresh()
                    pending=self.runner.state.get('pending_decision') or {}
                    packet=self.runner.packet or {}
                    return {'ok':True,'result':{'revision':self.runner.state['revision'],
                        'status':self.runner.state['status'],'your_turn':pending.get('actor')==role,
                        'decision_id':packet.get('decision_id') if pending.get('actor')==role else None,
                        'submissions':[{'request_id':key,'status':value['status']}
                            for key,value in self.runner.workflow.data['submissions'].items() if value['player']==role]}}
                except Exception:
                    return {'ok':False,'error':{'code':'unavailable','message':'Moderator recovery required.'}}
            return respond(self.runner,json.dumps(request))


class ArenaClient:
    def __init__(self, credential_path):
        self.path=Path(credential_path)
        credential=json.loads(self.path.read_text(encoding="utf-8"))
        self.role=credential['role']
        self.endpoint=Path(credential['mailbox'])
        self.token=credential['token']

    def request(self, request):
        marker=json.loads((self.endpoint/'server.json').read_text(encoding="utf-8"))
        os.kill(marker['pid'],0)
        identity=uuid4().hex
        request_path=self.endpoint/f'{identity}.request.json'
        response_path=self.endpoint/f'{identity}.response.json'
        save(request_path,{'token':self.token,'request':request})
        deadline=time.monotonic()+30
        try:
            while time.monotonic()<deadline:
                if response_path.exists():return json.loads(response_path.read_text(encoding="utf-8"))
                os.kill(marker['pid'],0)
                time.sleep(.005)
            raise TimeoutError('Arena response timeout')
        finally:
            request_path.unlink(missing_ok=True)
            response_path.unlink(missing_ok=True)


def serve(runner, private_dir):
    if runner.state['mode']!='agent-vs-agent':raise ValueError('Arena requires agent-vs-agent mode')
    private_dir=Path(private_dir).resolve()
    if private_dir.is_relative_to(runner.game_dir.parent.parent.parent):
        raise ValueError('Arena credentials must remain outside the repository')
    private_dir.mkdir(parents=True,mode=0o700,exist_ok=True)
    private_dir.chmod(0o700)
    endpoint=private_dir/'mailbox'
    endpoint.mkdir(mode=0o700,exist_ok=True)
    endpoint.chmod(0o700)
    marker=endpoint/'server.json'
    if marker.exists():
        previous=json.loads(marker.read_text(encoding="utf-8"))
        try:os.kill(previous['pid'],0)
        except ProcessLookupError:pass
        else:raise ValueError('Arena endpoint is already active')
    credentials={}
    paths={}
    for role,label in (('human','player_1'),('agent','player_2'),('moderator','moderator')):
        path=private_dir/f'{label}.json'
        value=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        token=value.get('token') if value.get('role')==role and value.get('mailbox')==str(endpoint) and value.get('game_id')==runner.state['game_id'] and value.get('session')==str(runner.game_dir) else None
        token=token or secrets.token_urlsafe(32)
        credentials[role]=token
        save(path,{'role':role,'mailbox':str(endpoint),'token':token,'game_id':runner.state['game_id'],'session':str(runner.game_dir)})
        path.chmod(0o600);paths[label]=str(path)
    arena=Arena(runner,credentials)
    save(marker,{'pid':os.getpid()})
    try:
        print(json.dumps({'ready':True,'credentials':paths}),flush=True)
        while True:
            for path in sorted(endpoint.glob('*.request.json')):
                try:
                    message=json.loads(path.read_text(encoding="utf-8"))
                    result=arena.request(message.get('token'),message.get('request'))
                except (ValueError,TypeError,AttributeError):
                    result={'ok':False,'error':{'code':'invalid_request','message':'Malformed arena request.'}}
                except FileNotFoundError:continue
                response=path.with_name(path.name.replace('.request.json','.response.json'))
                save(response,result)
                path.unlink(missing_ok=True)
            time.sleep(.005)
    finally:
        marker.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--game-dir',type=Path,required=True)
    parser.add_argument('--private-dir',type=Path,required=True)
    args=parser.parse_args()
    with DuelRunner(args.state,args.game_dir) as runner:serve(runner,args.private_dir)


if __name__=='__main__':main()
