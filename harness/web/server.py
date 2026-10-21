"""Loopback browser transport sharing the moderator's single writer."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from threading import Thread


def snapshot(service):
    with service.lock:
        runner = service.runner
        if runner is None:
            return {'state': None, 'message': 'Ask your orchestrator to start or resume a duel.'}
        runner._fresh()
        context = runner.context('public' if runner.state['mode'] == 'agent-vs-agent' else 'human')
        state = context['state']
        packet = runner.packet or {}
        human = (state.get('pending_decision') or {}).get('actor') == 'human' and state['mode'] != 'agent-vs-agent'
        current = packet.get('expected_revision') == state['revision']
        answered = any(s['decision_id'] == packet.get('decision_id') for s in runner.workflow.data['submissions'].values())
        ready = human and current and packet.get('awaiting_user', True) and state['status'] == 'active' and not answered
        return {'cards': context.get('cards', {}), 'state': state, 'decision': ({key: deepcopy(packet[key]) for key in
                ('decision_id', 'question', 'recommendations', 'events') if key in packet} if human and current else None),
                'can_reply': ready, 'message': 'Choose a move or describe your action.' if ready else
                ('Choice submitted. Waiting for moderator review.' if human and answered else 'Waiting for the orchestrator.'),
                'events': [event['summary'] for event in context['recent_events']]}


def start_server(service, port=8765):
    token = secrets.token_urlsafe(32)
    assets = Path(__file__).parent
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, data, kind='application/json'):
            body = json.dumps(data).encode() if kind == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            return self.headers.get('X-Duel-Token') == token

        def do_GET(self):
            if self.path == '/api/state':
                if not self.authorized():
                    return self.send(403, {'error': 'Unauthorized'})
                try:
                    return self.send(200, snapshot(service))
                except (OSError, ValueError):
                    return self.send(503, {'error': 'Session unavailable; ask the orchestrator to recover.'})
            routes = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
            if self.path not in routes:
                return self.send(404, {'error': 'Not found'})
            name, kind = routes[self.path]
            self.send(200, (assets / name).read_bytes(), kind)

        def do_POST(self):
            if self.path != '/api/reply' or not self.authorized():
                return self.send(403, {'error': 'Unauthorized'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    raise ValueError()
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or set(body) != {'decision_id', 'request_id', 'response'}:
                    raise ValueError()
                with service.lock:
                    result = service.request({'op': 'human_reply', **body})
                self.send(200 if result['ok'] else 409, {'ok': result['ok']})
            except (ValueError, TypeError):
                self.send(400, {'error': 'Invalid reply'})
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f'http://127.0.0.1:{server.server_port}/#token={token}'
