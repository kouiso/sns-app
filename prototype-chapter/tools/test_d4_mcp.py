import io
import json
import os
import subprocess
import tempfile
from pathlib import Path
import unittest

from d4_mcp import D4MCPServer, MAX_MESSAGE_BYTES, MAX_RESPONSE_BYTES, ProtocolError, decode_message, serve


class Workspace:
    def __init__(self):
        self.calls = []
        self.tampered = False

    def verify_inventory(self):
        if self.tampered:
            raise ValueError('/private/path/never/return')

    def read_file(self, args):
        if args != {'path': 'chapter.md'}:
            raise ValueError('denied')
        self.calls.append('read')
        return {'content': 'chapter', 'sha256': 'a' * 64}

    def edit_file(self, args):
        self.calls.append('edit')
        self.tampered = True
        return {'ok': True}

    def snapshot(self):
        return {'sha256': 'b' * 64}


class Checker:
    def __init__(self):
        self.calls = 0

    def run(self, profile):
        self.calls += 1
        return {'exit_code': 0}


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Workspace()
        self.checker = Checker()
        self.records = []
        self.server = D4MCPServer(self.workspace, self.checker, self.records.append)

    def request(self, method, params=None):
        return self.server.handle({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})

    def initialize(self):
        result = self.request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}})
        self.assertIn('result', result)
        self.assertIsNone(self.server.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'}))

    def test_lifecycle_and_exact_tool_surface(self):
        self.assertIn('error', self.request('tools/list'))
        self.initialize()
        names = {item['name'] for item in self.request('tools/list')['result']['tools']}
        self.assertEqual(names, {'read_file', 'edit_file', 'typecheck'})
        self.assertIn('error', self.request('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {}}))

    def test_read_and_fixed_typecheck_are_dispatched(self):
        self.initialize()
        self.assertNotIn('isError', self.request('tools/call', {'name': 'read_file', 'arguments': {'path': 'chapter.md'}})['result'])
        self.assertNotIn('isError', self.request('tools/call', {'name': 'typecheck', 'arguments': {'profile_id': 'd4-sdk57'}})['result'])
        self.assertEqual(self.workspace.calls, ['read'])
        self.assertEqual(self.checker.calls, 1)

    def test_bounded_protocol_metadata_does_not_change_tool_arguments(self):
        self.initialize()
        reply = self.request('tools/call', {'name':'read_file', 'arguments':{'path':'chapter.md'}, '_meta':{'progressToken':7}})
        self.assertNotIn('isError', reply['result'])
        self.assertEqual(self.workspace.calls, ['read'])
        for metadata in ['invalid', {'value':'x'*5000}]:
            reply = self.request('tools/call', {'name':'read_file', 'arguments':{'path':'chapter.md'}, '_meta':metadata})
            self.assertIn('error', reply)
        self.assertEqual(self.workspace.calls, ['read'])

    def test_metadata_on_lifecycle_and_lists_is_bounded(self):
        reply = self.request('initialize', {'protocolVersion':'2025-11-25', 'capabilities':{}, 'clientInfo':{}, '_meta':{'progressToken':1}})
        self.assertIn('result', reply)
        self.assertIsNone(self.server.handle({'jsonrpc':'2.0', 'method':'notifications/initialized', 'params':{'_meta':{}}}))
        self.assertTrue(self.server.ready)
        for method in ['ping', 'tools/list', 'resources/list', 'prompts/list']:
            self.assertIn('result', self.request(method, {'_meta':{}}))
            self.assertIn('error', self.request(method, {'_meta':'invalid'}))
            self.assertIn('error', self.request(method, {'_meta':{'value':'x'*5000}}))
        self.assertIn('error', self.request('tools/list', {'cursor':'unsupported', '_meta':{}}))

    def test_invalid_notification_has_no_response_or_lifecycle_effect(self):
        self.request('initialize', {'protocolVersion':'2025-11-25', 'capabilities':{}, 'clientInfo':{}})
        for params in [{'_meta':'invalid'}, {'_meta':{'value':'x'*5000}}, {'extra':True}, []]:
            message = {'jsonrpc':'2.0', 'method':'notifications/initialized', 'params':params}
            output = io.BytesIO()
            serve(self.server, io.BytesIO(json.dumps(message).encode()+b'\n'), output)
            self.assertEqual(output.getvalue(), b'')
            self.assertFalse(self.server.ready)
        self.assertIn('error', self.server.handle({'jsonrpc':'2.0', 'id':None, 'method':'ping'}))

    def test_version_negotiation_returns_supported_version(self):
        reply = self.request('initialize', {'protocolVersion':'2026-12-01', 'capabilities':{}, 'clientInfo':{}})
        self.assertEqual(reply['result']['protocolVersion'], '2025-11-25')
        for version in [None, [], '', 'x'*129, '2026\n']:
            server = D4MCPServer(self.workspace, self.checker)
            reply = server.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':version,'capabilities':{},'clientInfo':{}}})
            self.assertIn('error', reply)
            self.assertFalse(server.initialized)

    def test_arbitrary_command_or_provider_tool_never_runs(self):
        self.initialize()
        for args in [{'profile_id': 'shell'}, {'profile_id': 'd4-sdk57', 'argv': ['curl']}, {'profile_id': 'd4-sdk57', 'env': {'KEY': 'private'}}]:
            self.assertTrue(self.request('tools/call', {'name': 'typecheck', 'arguments': args})['result']['isError'])
        for name in ['http', 'sql', 'sign_in', 'wda', 'execute']:
            self.assertIn('error', self.request('tools/call', {'name': name, 'arguments': {}}))
        self.assertEqual(self.checker.calls, 0)

    def test_tamper_rejected_before_and_after_and_errors_do_not_leak(self):
        self.initialize()
        value = self.request('tools/call', {'name': 'edit_file', 'arguments': {}})
        self.assertTrue(value['result']['isError'])
        value = self.request('tools/call', {'name': 'read_file', 'arguments': {'path': 'chapter.md'}})
        self.assertTrue(value['result']['isError'])
        self.assertNotIn('/private/', json.dumps(value))
        self.assertEqual(self.workspace.calls, ['edit'])
        self.assertTrue(all(not entry['ok'] for entry in self.records))

    def test_duplicate_nan_deep_json_and_invalid_ids_are_rejected(self):
        for raw in [b'{"id":1,"id":2}', b'{"id":NaN}', b'[]', b'[' * 5000 + b']' * 5000]:
            with self.assertRaises(ProtocolError):
                decode_message(raw)
        for rid in [True, [], {}, None, 'x' * 129, '\ud800', 'bad\n', 2**64]:
            value = self.server.handle({'jsonrpc': '2.0', 'id': rid, 'method': 'ping'})
            self.assertIn('error', value)
            self.assertIsNone(value['id'])

    def test_stdio_oversized_frame_cannot_execute_valid_suffix(self):
        self.initialize()
        valid = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'read_file', 'arguments': {'path': 'chapter.md'}}}).encode() + b'\n'
        incoming = io.BytesIO(b'x' * (MAX_MESSAGE_BYTES + 1) + b'\n' + valid)
        output = io.BytesIO()
        serve(self.server, incoming, output)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(self.workspace.calls, [])

    def test_logger_failure_is_explicit_and_blocks_further_operations(self):
        self.initialize()
        def broken(value):
            raise OSError('/private/audit/full')
        self.server.record = broken
        reply = self.request('tools/call', {'name': 'read_file', 'arguments': {'path': 'chapter.md'}})
        self.assertEqual(reply['result']['content'][0]['text'], 'tool_completed_audit_failed_stop')
        reply = self.request('tools/call', {'name': 'read_file', 'arguments': {'path': 'chapter.md'}})
        self.assertEqual(reply['result']['content'][0]['text'], 'audit_failed_session_closed')
        self.assertEqual(self.workspace.calls, ['read'])
        self.assertNotIn('/private/', json.dumps(reply))

    def test_legal_maximal_text_response_has_separate_bounded_frame(self):
        self.initialize()
        self.workspace.read_file = lambda args: {'content': '"' * (128 * 1024)}
        message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'read_file', 'arguments': {'path': 'chapter.md'}}}
        output = io.BytesIO()
        serve(self.server, io.BytesIO(json.dumps(message).encode() + b'\n'), output)
        raw = output.getvalue()
        self.assertGreater(len(raw), MAX_MESSAGE_BYTES)
        self.assertLessEqual(len(raw), MAX_RESPONSE_BYTES)
        self.assertNotIn('isError', json.loads(raw)['result'])

    def test_real_subprocess_bootstrap_and_starter_typecheck(self):
        def not_ready(reason):
            if os.environ.get('D4_REQUIRE_REAL_TOOLCHAIN') == '1':
                self.fail('Required real toolchain unavailable: ' + reason)
            self.skipTest('NOT_READY: ' + reason)
        if ('D4_TEST_DEPENDENCIES' in os.environ) != ('D4_TEST_TARGETS' in os.environ):
            not_ready('both trusted toolchain overrides are required')
        overlay = Path(os.environ.get('D4_TEST_DEPENDENCIES', '/tmp/sns-auth-sdk57-runtime/node_modules'))
        if not overlay.is_dir() or not Path('/usr/bin/bwrap').is_file():
            not_ready('local bounded SDK57 toolchain is required')
        try:
            node = subprocess.check_output(['node', '-p', 'process.execPath'], text=True, timeout=10).strip()
        except (OSError, subprocess.SubprocessError):
            not_ready('Node is unavailable')
        tools = Path(__file__).resolve().parent
        candidate = tools.parent / 'candidates/d4-runtime'
        roots = json.loads(os.environ['D4_TEST_TARGETS']) if 'D4_TEST_TARGETS' in os.environ else ['/home/kouiso/ghq/kouiso/sns-app/prototype-chapter/listings/expo-first-screen/node_modules', '/tmp/sns-auth-sdk57-libraries/node_modules']
        messages = [
            {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{}}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'typecheck','arguments':{'profile_id':'d4-sdk57'}}},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            env = {'PATH':'/usr/bin:/bin','D4_CANDIDATE':str(candidate),'D4_WORKSPACE':temporary+'/workspace',
                   'D4_DEPENDENCIES':str(overlay),'D4_NODE':node,'D4_DEPENDENCY_TARGETS':json.dumps(roots),'D4_EVENTS':temporary+'/events.jsonl'}
            result = subprocess.run(['/usr/bin/python3',str(tools/'d4_mcp.py')], input=''.join(json.dumps(m)+'\n' for m in messages),
                                    text=True, capture_output=True, env=env, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            replies = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(len(replies), 2)
            self.assertNotIn('isError', replies[-1]['result'])
            receipt = json.loads(replies[-1]['result']['content'][0]['text'])
            self.assertTrue(receipt['passed'])
            self.assertEqual(receipt['exit_code'], 0)
            event = json.loads(Path(temporary+'/events.jsonl').read_text())
            self.assertTrue(event['typecheck_passed'])
            self.assertEqual(event['exit_code'], 0)

    def test_notifications_cannot_dispatch_tools(self):
        self.initialize()
        self.assertIsNone(self.server.handle({'jsonrpc': '2.0', 'method': 'tools/call', 'params': {'name': 'read_file', 'arguments': {'path': 'chapter.md'}}}))
        self.assertEqual(self.workspace.calls, [])


if __name__ == '__main__':
    unittest.main()
