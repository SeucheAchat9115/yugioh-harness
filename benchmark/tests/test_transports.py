import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import unittest
from unittest.mock import patch
import subprocess
from yugioh_benchmark.transports import OpenAICompatible
from yugioh_benchmark.metering import Meter

class TransportTests(unittest.TestCase):
    def test_real_worker_limits_no_tools_and_reported_usage(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                body={'model':'test-snapshot','choices':[{'message':{'content':'{"action":"end_turn"}'}}],
                      'usage':{'prompt_tokens':20,'completion_tokens':5,'total_tokens':25,
                               'prompt_tokens_details':None,'completion_tokens_details':{'reasoning_tokens':2}}}
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps(body).encode())
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            transport=OpenAICompatible(f'http://127.0.0.1:{server.server_port}',key_env='BENCH_TEST_KEY',max_output_tokens=17)
            with patch.dict(os.environ,{'BENCH_TEST_KEY':'offline-test-only'}):
                meter=Meter();response=meter.call(transport,'test',{'messages':[{'role':'user','content':'test'}],'tools':[],'tool_choice':'none'},case_id='a',role='evaluation')
            self.assertEqual(json.loads(response)['action'],'end_turn')
            self.assertNotIn('tools',seen[0]);self.assertNotIn('tool_choice',seen[0])
            self.assertEqual(seen[0]['max_completion_tokens'],17)
            self.assertEqual(meter.calls[0]['usage']['total_tokens'],25)
            self.assertEqual(meter.calls[0]['pricing_model'],'test-snapshot')
            self.assertIsNone(meter.calls[0]['cost']['usd'])
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_local_watchdog_and_options_preflight(self):
        transport=OpenAICompatible(key_env='BENCH_TEST_KEY',timeout_seconds=1)
        with patch.dict(os.environ,{'BENCH_TEST_KEY':'offline-test-only'}):
            with self.assertRaises(ValueError):transport.preflight({'tools':['shell']})
            with patch('subprocess.run',side_effect=subprocess.TimeoutExpired('worker',1)) as worker:
                with self.assertRaises(subprocess.TimeoutExpired):transport('test',{},role='evaluation',options={})
                self.assertEqual(worker.call_args.kwargs['timeout'],1)
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ValueError):transport.preflight({})
        with self.assertRaises(ValueError):OpenAICompatible('http://example.com')
