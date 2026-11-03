"""Generated failure injection; no capture decoder, encoder or optimizer runs.

Cleanup notes use the Python-3.9-compatible exception attribute
``engineering_cleanup_errors``; the original exception must remain primary.
"""
import contextlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import continuous_audit_engineering_v1 as audit_api
import continuous_features_engineering_v1 as features
import continuous_common_v3 as common
import legacy_reference_sample_prepare_v1 as prep
from test_engineering_state_storage_v1 import POLICY, generated, target


class Progress:
    def __init__(self, output=None, limits=None):
        if output is not None: Path(output).mkdir()
    def tick(self, *args): pass
    def record_failure(self, *args): pass
    def stop(self, *args, **kwargs): pass


class LifecycleFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.api = prep.old.legacy_runtime()
        self.row = generated(1, 0)
        self.targets = {1: ('LEARN', 0, target(self.row, self.api))}
        self.spec = dict(capture_id='generated', sha256='fixture', expected_packets=1)

    def make_audit(self):
        return audit_api.CaptureAudit(self.spec, {'aa'}, self.api, self.targets,
                                      self.root, storage_policy=POLICY)

    def assert_closed(self, database):
        with self.assertRaises(sqlite3.ProgrammingError):
            database.execute('SELECT 1')

    def test_second_store_constructor_failure_closes_first(self):
        contexts = []; original = audit_api.Contexts
        def context(*args, **kwargs):
            value = original(*args, **kwargs); contexts.append(value)
            self.addCleanup(value.close)
            return value
        with patch.object(audit_api, 'Contexts', context), patch.object(audit_api, 'SpillMap', side_effect=ValueError('SECOND_STORE')):
            with self.assertRaisesRegex(ValueError, 'SECOND_STORE'):
                self.make_audit()
        self.assertTrue(contexts[0].states.closed)
        self.assertFalse(any(self.root.glob('state_cache_*')))

    def test_stream_open_failure_closes_both_stores(self):
        contexts = []; stores = []
        original_context, original_store = audit_api.Contexts, audit_api.SpillMap
        def context(*args, **kwargs):
            value = original_context(*args, **kwargs); contexts.append(value)
            self.addCleanup(value.close)
            return value
        def store(*args, **kwargs):
            value = original_store(*args, **kwargs); stores.append(value)
            self.addCleanup(value.close)
            return value
        with patch.object(audit_api, 'Contexts', context), patch.object(audit_api, 'SpillMap', store), patch.object(audit_api.gzip, 'open', side_effect=OSError('STREAM_OPEN')):
            with self.assertRaisesRegex(OSError, 'STREAM_OPEN'):
                self.make_audit()
        self.assertTrue(contexts[0].states.closed and stores[0].closed)
        self.assertFalse(any(self.root.glob('state_cache_*')))

    def test_preexisting_cache_directory_is_untouched(self):
        directory = self.root/('state_cache_'+common.digest('generated'))
        directory.mkdir()
        sentinel = directory/'current.sqlite'; sentinel.write_bytes(b'UNRELATED')
        with self.assertRaises(FileExistsError): self.make_audit()
        self.assertEqual(sentinel.read_bytes(), b'UNRELATED')

    def test_closed_stream_does_not_skip_store_cleanup(self):
        value = self.make_audit(); self.addCleanup(value.close)
        value.stream.close(); value.close(); value.close()
        self.assertTrue(value.contexts.states.closed and value.legacy.states.closed)
        self.assertFalse(value.cache_directory.exists())

    def test_cleanup_failure_cannot_mask_active_failure(self):
        value = self.make_audit(); self.addCleanup(value.close)
        original = value.contexts.states.close
        def close():
            original()
            raise OSError('CLOSE_FAILED')
        primary = ValueError('PRIMARY_FAILURE')
        with patch.object(value.contexts.states, 'close', close):
            with self.assertRaises(ValueError) as caught:
                try: raise primary
                finally: value.close()
        self.assertIs(caught.exception, primary)
        self.assertTrue(value.legacy.states.closed)
        self.assertEqual(primary.engineering_cleanup_errors, ["OSError('CLOSE_FAILED')"])
        self.assertFalse(value.cache_directory.exists())

    def spool_failure(self, stage):
        raw = self.root/'generated.raw'; raw.write_bytes(b'GENERATED_NO_DECODE')
        spec = dict(self.spec, path=str(raw))
        row = dict(self.targets[1][2], fit_role='FIT', label=0, device='aa', component_id='g')
        runtime = dict(synthetic_only=True, known_macs=['aa'], state_storage=POLICY, tshark='NEVER')
        @contextlib.contextmanager
        def decoded(*args):
            if stage == 'decode': raise ValueError('DECODE_FAILED')
            yield [self.row]
        # Fixed generated header tokens; the original verifier still checks them.
        example = dict(input_ids=[[65537,21,1,61,1,65,3,1025,1,1,1,1,1]],
                       attention_mask=[[1]*13], dataset_burst_sizes=[12], protocol=6)
        connections = []; original_connect = sqlite3.connect
        def connect(*args, **kwargs):
            database = original_connect(*args, **kwargs); connections.append(database)
            self.addCleanup(database.close)
            return database
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(features, 'e3_runtime', return_value=(None,)*5))
            stack.enter_context(patch.object(features, 'decode', decoded))
            stack.enter_context(patch.object(features, 'tokenize', return_value=example))
            stack.enter_context(patch.object(features.sqlite3, 'connect', connect))
            if stage == 'finish':
                stack.enter_context(patch.object(audit_api.CaptureAudit, 'finish', side_effect=ValueError('FINISH_FAILED')))
            if stage == 'assign':
                stack.enter_context(patch.object(features, 'assign_batches', side_effect=ValueError('ASSIGN_FAILED')))
            with self.assertRaisesRegex(ValueError, stage.upper()+'_FAILED'):
                features.spool(self.root, self.root/'spool', {'LEARN': [row]}, [spec], runtime, Progress())
        for database in connections: self.assert_closed(database)
        self.assertFalse(any((self.root/'spool').glob('state_cache_*')))

    def test_spool_decode_failure_closes_all_databases(self):
        self.spool_failure('decode')

    def test_spool_finish_failure_closes_all_databases(self):
        self.spool_failure('finish')

    def test_spool_batch_assignment_failure_closes_all_databases(self):
        self.spool_failure('assign')

    def test_worker_database_and_diagnostic_failures_retain_primary(self):
        database = sqlite3.connect(':memory:'); self.addCleanup(database.close)
        closed = []
        class Database:
            def execute(self, *args): raise ValueError('QUERY_FAILED')
            def close(self):
                database.close(); closed.append(True)
                raise OSError('CLOSE_FAILED')
        class BadProgress(Progress):
            def record_failure(self, *args): raise OSError('DIAGNOSTIC_FAILED')
            def stop(self, *args, **kwargs): raise OSError('STOP_FAILED')
        runtime = dict(synthetic_only=True, worker_limits={}, feature_workers=1)
        with patch.object(features, 'e3_runtime', return_value=(None,)*5), patch.object(features, 'Progress', BadProgress), patch.object(features.sqlite3, 'connect', return_value=Database()), patch.object(common, 'pin'), patch.object(common, 'read', side_effect=[{'design_sha256': common.DESIGN_SHA}, {'sha256': 'dummy'}]):
            with self.assertRaisesRegex(ValueError, 'QUERY_FAILED') as caught:
                features.feature_worker(self.root, self.root, 0, True,
                    authorization=lambda *args: ({'input': {}}, runtime))
        self.assertEqual(closed, [True]); self.assert_closed(database)
        self.assertEqual(caught.exception.engineering_cleanup_errors,
                         ["OSError('CLOSE_FAILED')", "OSError('DIAGNOSTIC_FAILED')", "OSError('STOP_FAILED')"])


if __name__ == '__main__':
    unittest.main()
