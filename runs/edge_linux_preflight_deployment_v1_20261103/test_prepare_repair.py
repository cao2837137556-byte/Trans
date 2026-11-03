"""Prepare recovery safety checks; no processes, network or model execution."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import client
import repair_prepare


class ExplicitPrepareRepair(unittest.TestCase):
    def fixture(self, folder):
        (folder / 'remote_receiver.py').write_text('source = 1\n', encoding='utf-8')
        source_sha = client.sha(folder / 'remote_receiver.py')
        client.write(folder / 'PREPARE_REPAIR_PLAN.json', dict(new_receiver_sha256=source_sha))
        specs = {k: dict(filename=k, bytes=10, sha256='a'*64) for k in client.KEYS}
        client.write(folder / 'DELIVERY.json', dict(files=specs, receiver_source_sha256='b'*64,
                                                 archive_manifest_sha256='c'*64))
        intent = b'{"status":"previous failure"}\n'
        (folder / 'PREPARE_ATTEMPT.json').write_bytes(intent)
        state = dict(status='READY_TO_UPLOAD', job=None, last_error=None,
                     receiver_source_sha256=source_sha,
                     files={k: dict(bytes=10, sha256='a'*64, offset=10, complete=True)
                            for k in client.KEYS})
        return state, intent

    def test_confirmed_repair_preserves_old_intent_and_uses_only_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            state, intent = self.fixture(folder)
            calls = []
            def get(route):
                calls.append(route)
                return state
            result = repair_prepare.allow_local_resume(folder=folder, action=get)
            self.assertEqual(calls, ['state'])
            self.assertFalse((folder / 'PREPARE_ATTEMPT.json').exists())
            self.assertEqual((folder/'repair_history/prepare_tshark_environment_v1/PREPARE_ATTEMPT.json').read_bytes(), intent)
            self.assertFalse(result['input_upload_repeated'])

    def test_unknown_submission_or_wrong_receiver_cannot_clear_intent(self):
        for kind in ('remote_job', 'old_receiver', 'local_submit_intent', 'incomplete_input'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                state, intent = self.fixture(folder)
                if kind == 'remote_job': state['job'] = {'job_id': '123'}
                if kind == 'old_receiver': state['receiver_source_sha256'] = 'd'*64
                if kind == 'local_submit_intent': client.write(folder/'SUBMIT_ATTEMPT.json', {})
                if kind == 'incomplete_input': state['files']['UDP'].update(complete=False, offset=5)
                with self.assertRaises(ValueError):
                    repair_prepare.allow_local_resume(folder=folder, action=lambda route: state)
                self.assertEqual((folder/'PREPARE_ATTEMPT.json').read_bytes(), intent)
                self.assertFalse((folder/'repair_history').exists())

    def test_generated_repair_command_has_no_private_config_or_token_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.fixture(folder)
            (folder/'.private').mkdir()
            (folder/'.private/connection.json').write_text('{"token":"PRIVATE_SENTINEL"}')
            with patch.object(repair_prepare, 'HERE', folder), contextlib.redirect_stdout(io.StringIO()):
                repair_prepare.build()
            command = (folder/'RUN_REPAIR_IN_HPC_TERMINAL.txt').read_text()
            self.assertNotIn('PRIVATE_SENTINEL', command)
            self.assertIn(repair_prepare.PYTHON, command)
            self.assertEqual(client.read(folder/'PREPARE_REPAIR_PLAN.json')['wall_seconds'], 600)


if __name__ == '__main__':
    unittest.main()
