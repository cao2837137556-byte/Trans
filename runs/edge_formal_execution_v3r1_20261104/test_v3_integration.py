"""Integrated routing and version isolation; synthetic inputs, no model calls."""
from contextlib import contextmanager
import copy
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import worker
from checkpoint import PackedRoleSpool, atomic_json, canonical, sha

HERE = Path(__file__).resolve().parent
OLD = HERE.parent/'edge_formal_execution_v2_20261103'


class V3IntegrationTests(unittest.TestCase):
    def test_scientific_and_safety_code_unchanged(self):
        for name in ('checkpoint.py', 'streaming.py', 'evaluate.py', 'reporting.py',
                     'runtime_control.py', 'budget.py'):
            self.assertEqual((HERE/name).read_bytes(), (OLD/name).read_bytes(), name)
        gate = (OLD/'engineering_gate.py').read_text(encoding='utf-8').replace(
            "    require(card.get('independent_review', {}).get('status') == 'PASS',\n            'ENGINEERING_INDEPENDENT_REVIEW_REQUIRED')",
            "    from review_authorization import require_review_decision\n    require_review_decision(card, auth, root)", 1)
        self.assertEqual((HERE/'engineering_gate.py').read_text(encoding='utf-8'), gate)
        old = (OLD/'worker.py').read_text(encoding='utf-8')
        expected = old.replace(
            'from streaming import ROOT, FrozenBackend, make_plan, module, run_encoding\n',
            'from streaming import ROOT, FrozenBackend, make_plan, module, run_encoding\n'
            'from progress_io import install as install_progress_io\n', 1).replace(
            '            with replay.install(adapter, output=',
            '            with install_progress_io(replay, sys.modules[__name__], output), replay.install(adapter, output=', 1)
        self.assertEqual((HERE/'worker.py').read_text(encoding='utf-8'), expected)

    def test_integrated_prepare_preserves_snapshots_and_routes_only_live_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); output = root/'output'; output.mkdir()
            scratch = root/'scratch'; scratch.mkdir()
            (output/'replay_status').mkdir()
            selected, snapshots, raw_paths, specs = {}, {}, {}, {}
            for role in ('NORMAL', 'HTTP', 'UDP'):
                raw = root/(role+'.raw'); raw.write_bytes(b'x')
                raw_paths[role] = str(raw)
                specs[role] = dict(path=str(raw), bytes=1, sha256=sha(raw), records=1)
                row = dict(uid=role+'-1', frame=1, timestamp_ns=1, protocol=17,
                           capture_id=role, component_id='fixture', source_role=role,
                           use='QUERY', owner='fixture', source_sha256=sha(raw))
                selected[role] = [row]
                snapshots[role] = dict(uid=row['uid'], row=row, q14=[0.]*14,
                    body=dict(flow=dict(protocol=17, counts=[1]), provenance={}, state=[]))
            adapter = types.SimpleNamespace(card=lambda: dict(raw_inputs=specs))
            live = {output/'PROGRESS.json', output/'replay_status'/'REPLAY_HEARTBEAT.json'}
            durable_calls = []
            def original_writer(path, value):
                self.assertNotIn(Path(path), live, 'Live path reached durable writer')
                durable_calls.append(Path(path).name)
                atomic_json(path, value)
            replay = types.SimpleNamespace(_write_json=original_writer)
            @contextmanager
            def install(adapter, **kwargs):
                patched = types.SimpleNamespace(active={}, decode_rows=lambda *a, **k: iter(()))
                def stream(role, frames, work, **kw):
                    patched.active['frame'] = 1
                    replay._write_json(output/'replay_status'/'REPLAY_HEARTBEAT.json', {'role': role})
                    worker.atomic_json(output/'PROGRESS.json', {'role': role})
                    yield copy.deepcopy(snapshots[role])
                patched.original = {'selected_snapshots': stream}
                yield patched
            replay.install = install
            class Guard:
                started = time.monotonic()
                budget = {'wall_seconds': 7200}
                def __call__(self): pass
                def progress(self, *a, **kw): pass
            card = dict(selection_seal_sha256=worker.SELECTION_SHA,
                        scientific_input_artifact_pins={'fixture': 'pinned'}, dependency_envelope={})
            with patch('dependency_identity.verify'), \
                 patch.object(worker, 'selection_inputs', return_value=({}, [], selected)), \
                 patch.object(worker, 'module', side_effect=lambda name, p: adapter if p.name=='edge_adapter.py' else replay), \
                 patch.object(worker, 'atomic_json', original_writer):
                result = worker.prepare_inputs(card, dict(tshark='fixture', raw_paths=raw_paths),
                    output, scratch, Guard(), {'runtime': 'fixture'}, replay_to_eof=True)
            self.assertEqual(len(result['headers']), 3)
            self.assertEqual(durable_calls, ['REPLAY_COVERAGE.json']*3)
            for role, snapshot in snapshots.items():
                self.assertEqual(canonical(result['load'](snapshot['uid'])), canonical(snapshot))
                self.assertTrue((output/'spools'/role/'COMPLETE.json').is_file())
            self.assertIs(replay._write_json, original_writer)

    def test_v2_complete_spool_is_not_silently_adopted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = dict(schema='EDGE_SCIENTIFIC_INPUT_BINDING_V2',
                dependency_envelope={'source_inventories': {'v2': {'worker.py': 'old'}}})
            new = copy.deepcopy(old)
            new['dependency_envelope']['source_inventories'] = {'v3': {'worker.py': 'new', 'progress_io.py': 'new'}}
            snapshot = dict(uid='one', row=dict(uid='one', protocol=17), q14=[0.]*14,
                            body=dict(flow=dict(protocol=17, counts=[1])))
            spool = PackedRoleSpool(root, old, 'UDP', ['one'])
            spool.append(snapshot)
            spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
            with self.assertRaisesRegex(ValueError, 'BINDING_CHANGED'):
                PackedRoleSpool(root, new, 'UDP', ['one'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
