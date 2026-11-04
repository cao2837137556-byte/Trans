"""Local synthetic/mock checks; no model loads, cloud calls or external scores."""
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import numpy as np

import engineering_gate as gate
from checkpoint import canonical, sha
from streaming import make_plan, run_encoding
from test_streaming import FakeBackend, fixture
import worker


def card_fixture(root):
    pin = root/'artifact.py'
    pin.write_text('synthetic fixture\n', encoding='utf-8')
    card = dict(status=gate.READY, independent_review=dict(status='PASS'),
        selection_seal_sha256=gate.SELECTION_SHA,
        artifact_pins={'artifact.py': sha(pin)}, scientific_input_artifact_pins={'artifact.py': sha(pin)},
        budget=dict(cpu=1, rss_bytes=8*gate.GIB, wall_seconds=7200,
                    scratch_bytes=32*gate.GIB, disk_bytes=32*gate.GIB,
                    automatic_resubmit=False, automatic_extension=False))
    import dependency_identity as dep
    inventories = {}
    for relative in dep.INVENTORIES:
        folder=root/relative;folder.mkdir(parents=True,exist_ok=True)
        source=folder/'fixture.py';source.write_text('fixture = 1\n',encoding='utf-8')
        inventories[relative]=dep.python_inventory(root,relative)
    manifest=root/dep.BASE;manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_bytes(canonical(dict(files={'artifact.py':dict(bytes=pin.stat().st_size,sha256=sha(pin))})))
    envelope=dict(schema='EDGE_FULL_DEPENDENCY_ENVELOPE_V2',
        base_manifest=dict(path=dep.BASE,sha256=sha(manifest)),source_inventories=inventories)
    pins={dep.BASE:sha(manifest),'artifact.py':sha(pin)}
    for inventory in inventories.values():pins.update(inventory)
    card.update(dependency_envelope=envelope,artifact_pins=dict(pins),scientific_input_artifact_pins=dict(pins))
    path=root/'CARD.json'
    path.write_bytes(canonical(card))
    auth=root/'AUTHORIZATION.json'
    auth.write_bytes(canonical(dict(scope=gate.SCOPE, card_sha256=sha(path), user_authorized=True)))
    return path, auth, card


def synthetic_child(root, mode):
    headers, snapshots=fixture()
    plan=make_plan(headers)[:2]
    def fault(name):
        if mode=='crash' and name=='after_commit':
            os._exit(75)
    run_encoding(plan, snapshots.__getitem__, FakeBackend, root, dict(fixture='engineering-v1'),
                 failpoint=fault)


class EngineeringGateTests(unittest.TestCase):
    def test_authorization_requires_bound_independent_engineering_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            card,auth,value=card_fixture(root)
            self.assertEqual(gate.require_engineering_authorization(card,auth,root),value)
            for override in (dict(scope='EDGE_EXTERNAL_TEST_1_FULL_EVALUATION'),
                             dict(user_authorized=False),dict(card_sha256='wrong')):
                a=dict(scope=gate.SCOPE,user_authorized=True,card_sha256=sha(card));a.update(override)
                auth.write_bytes(canonical(a))
                with self.assertRaisesRegex(ValueError,'ACTUAL_BOUND_ENGINEERING'):
                    gate.require_engineering_authorization(card,auth,root)

    def test_draft_blocks_before_runtime_or_model_and_records_fresh_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);card=root/'DRAFT.json';card.write_bytes(canonical(dict(status='DRAFT')))
            with patch.object(gate,'FrozenBackend',side_effect=AssertionError('MODEL_FORBIDDEN')):
                with self.assertRaisesRegex(ValueError,'CARD_NOT_READY'):
                    gate.run(card,root/'absent-auth',root/'absent-runtime',root/'output')
            status=gate.current_status(root/'output')
            self.assertEqual(status['status'],'STOP')
            self.assertIn('CARD_NOT_READY',status['reason'])

    def test_pin_and_resource_changes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);card,auth,value=card_fixture(root)
            value['budget']['wall_seconds']=7201;card.write_bytes(canonical(value))
            auth.write_bytes(canonical(dict(scope=gate.SCOPE,user_authorized=True,card_sha256=sha(card))))
            with self.assertRaisesRegex(ValueError,'RESOURCE_CONTRACT'):
                gate.require_engineering_authorization(card,auth,root)
            card,auth,value=card_fixture(root)
            (root/'artifact.py').write_text('changed',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'BASE_MEMBER_SIZE|DEPENDENCY_FILE_CHANGED'):
                gate.require_engineering_authorization(card,auth,root)

    def test_first_sixteen_uid_plan_rare_and_singleton_remain_honest(self):
        headers,_=fixture()
        plan=gate.probe_plan(list(reversed(headers)),expected_shapes=3)
        self.assertEqual([len(b['uids']) for b in plan],[16,3,1])
        self.assertEqual([b['physical_rows'] for b in plan],[16,3,16])
        self.assertEqual(plan[0]['uids'],sorted(h['uid'] for h in headers if h['shape']==[6,13,1])[:16])
        with self.assertRaisesRegex(ValueError,'CENSUS_COUNT'):
            gate.probe_plan(headers)

    def test_mock_throughput_emits_timing_and_inputs_without_features(self):
        headers,snapshots=fixture();plan=gate.probe_plan(headers,expected_shapes=3)
        value=gate.throughput(plan,snapshots.__getitem__,FakeBackend(),lambda:None,lambda *a,**k:None)
        self.assertEqual(len(value),3)
        self.assertEqual([x['logical_rows'] for x in value],[16,3,1])
        self.assertFalse(any(key in x for x in value for key in ('e3','q14','scores','decisions')))

    def test_actual_subprocess_after_commit_recovers_identical_committed_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);deadline=time.monotonic()+40
            for name,phase,code in [('baseline','normal',0),('resumed','crash',75),('resumed','resume',0)]:
                command=[sys.executable,'-X','utf8','-B',__file__,'--synthetic-child',str(root/name),phase]
                self.assertEqual(gate.bounded_process(command,root/(name+'-'+phase+'.log'),deadline),code)
            self.assertEqual(gate.committed_files(root/'baseline'),gate.committed_files(root/'resumed'))

    def test_deadline_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'DEADLINE_BEFORE_CHILD'):
                gate.bounded_process([sys.executable,'-c','raise AssertionError()'],Path(temp)/'log',time.monotonic())
            self.assertFalse((Path(temp)/'log').exists())

    def test_recovery_attempts_are_distinct_and_cannot_escape_owned_tree(self):
        self.assertNotEqual(gate.recovery_root('/output','a'*32),gate.recovery_root('/output','b'*32))
        for invalid in ('../other','a'*31,'A'*32):
            with self.assertRaisesRegex(ValueError,'RECOVERY_ATTEMPT_ID'):
                gate.recovery_root('/output',invalid)

    def test_crashed_child_scratch_cleanup_requires_exact_pid_scope_and_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);scratch=root/'scratch';scratch.mkdir();output=root/'output';output.mkdir()
            owned=scratch/'edge-gate-owned-fixture';owned.mkdir()
            other=scratch/'edge-gate-owned-unrelated';other.mkdir();(other/'keep').write_text('keep')
            owner=dict(scope=gate.SCOPE,pid=12345,output=str(output.resolve()))
            (owned/'OWNERSHIP.json').write_bytes(canonical(owner))
            marker=root/'SCRATCH_crash.json';marker.write_bytes(canonical(dict(owner,scratch=str(owned))))
            with self.assertRaisesRegex(ValueError,'MARKER_OWNER'):
                gate.cleanup_child_scratch(marker,scratch,output,99999)
            self.assertTrue(owned.exists())
            gate.cleanup_child_scratch(marker,scratch,output,12345)
            self.assertFalse(owned.exists());self.assertTrue((other/'keep').exists())

    def test_source_head_comparison_reports_roundoff_and_blocks_decision_change(self):
        old=np.zeros((16,3),dtype=np.float64);saved=old.copy();cached=old+1e-6
        pred=np.zeros((16,4),dtype=bool)
        value=gate.compare_source_scores(cached,old,saved,pred,pred,pred)
        self.assertFalse(value['cache_vs_old_bit_exact'])
        self.assertTrue(value['cache_vs_old_tolerance_1e_4_pass'])
        bad=pred.copy();bad[0,0]=True
        with self.assertRaisesRegex(ValueError,'PARITY_FAILED'):
            gate.compare_source_scores(cached,old,saved,bad,pred,pred)

    def test_small_synthetic_bank_uses_real_core_and_knn_without_model(self):
        with patch.object(gate,'FrozenBackend',side_effect=AssertionError('MODEL_FORBIDDEN')):
            a=gate.synthetic_distances(lambda:None,reference_counts=(8,6),query_count=3)
            b=gate.synthetic_distances(lambda:None,reference_counts=(8,6),query_count=3)
        self.assertEqual([x['distance_pairs_each'] for x in a['records']],[24,18])
        for x,y in zip(a['records'],b['records']):
            for key in ('synthetic_input_sha256','core_output_sha256','knn_output_sha256'):
                self.assertEqual(x[key],y[key])

    def test_input_binding_ignores_card_sha_but_tracks_scientific_and_runtime_identity(self):
        card=dict(scientific_input_artifact_pins={'adapter.py':'fixed'},execution_card_sha256='one',dependency_envelope={'fixture':'v2'})
        source=dict(raw_inputs={role:dict(bytes=100,sha256=role) for role in ('NORMAL','HTTP','UDP')})
        first=worker.input_binding(card,dict(runtime='same'),source)
        card['execution_card_sha256']='different'
        self.assertEqual(first,worker.input_binding(card,dict(runtime='same'),source))
        self.assertNotEqual(first,worker.input_binding(card,dict(runtime='different'),source))

    def test_raw_tuple_reference_namespace_matches_its_json_seal(self):
        row=dict(uid='r',frame=1,timestamp_ns=1,protocol=6,capture_id='c',component_id='c',
            source_role='NORMAL',use='REFERENCE',owner='owner',source_sha256='raw',
            canonical_key=(6,('one',80),('two',9000)))
        expected=json.loads(canonical(row))
        result=worker.merge_selected(dict(uid='r',row=row,q14=[0.]*14),expected)
        self.assertEqual(result['row']['canonical_key'],expected['canonical_key'])
        expected['canonical_key'][1][1]=81
        with self.assertRaisesRegex(ValueError,'RAW_TO_SEALED_METADATA:canonical_key'):
            worker.merge_selected(dict(uid='r',row=row,q14=[0.]*14),expected)

    def test_prepare_inputs_full_eof_keeps_original_generator_final_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);output=root/'output';output.mkdir();scratch=root/'scratch';scratch.mkdir()
            source=dict(raw_inputs={});raw_paths={};selected={};expected={};final=[]
            for role in ('NORMAL','HTTP','UDP'):
                raw=root/(role+'.pcap');raw.write_bytes(role.encode());raw_paths[role]=str(raw)
                source['raw_inputs'][role]=dict(path=str(raw),bytes=raw.stat().st_size,sha256=sha(raw),records=3)
                row=dict(uid=role+'-2',frame=2,timestamp_ns=2,protocol=6,capture_id=role,
                    component_id=role,source_role=role,use='QUERY',owner='synthetic',source_sha256=sha(raw))
                selected[role]=[row];expected[role]=row
            adapter=types.SimpleNamespace(card=lambda:copy.deepcopy(source))
            def decode(path,**kwargs):
                for frame in range(1,kwargs['stop_after']+1):
                    yield {'frame.number':str(frame)}
            adapter.decode_rows=decode
            def selected_snapshots(role,frames,work,**kwargs):
                try:
                    for packet in adapter.decode_rows('synthetic',stop_after=max(frames)):
                        frame=int(packet['frame.number'])
                        if frame in frames:
                            row=copy.deepcopy(expected[role])
                            yield dict(uid=row['uid'],row=row,q14=[0.]*14,
                                body=dict(flow=dict(protocol=6,counts=[1])),info={})
                finally:
                    final.append((role,frame))
            adapter.selected_snapshots=selected_snapshots
            @contextmanager
            def install(adapter,**kwargs):
                patched=types.SimpleNamespace(active=None,original={'selected_snapshots':selected_snapshots})
                def tracked(*args,**kw):
                    for packet in decode(*args,**kw):
                        patched.active['frame']=int(packet['frame.number']);yield packet
                patched.decode_rows=tracked;adapter.decode_rows=tracked
                try:yield patched
                finally:adapter.decode_rows=decode
            replay=types.SimpleNamespace(install=install)
            guard=types.SimpleNamespace(started=time.monotonic(),budget={'wall_seconds':7200},progress=lambda *a,**k:None)
            class CallableGuard:
                started=guard.started;budget=guard.budget;progress=staticmethod(guard.progress)
                def __call__(self):pass
            card=dict(selection_seal_sha256=gate.SELECTION_SHA,scientific_input_artifact_pins={'input':'same'},dependency_envelope={'fixture':'v2'})
            runtime=dict(tshark='synthetic',raw_paths=raw_paths)
            def modules(name,path):return replay if 'replay_io' in str(path) else adapter
            with patch('dependency_identity.verify'),patch.object(worker,'selection_inputs',return_value=({},[],selected)),patch.object(worker,'module',side_effect=modules):
                result=worker.prepare_inputs(card,runtime,output,scratch,CallableGuard(),{'runtime':'mock'},replay_to_eof=True)
            self.assertEqual(final,[('NORMAL',3),('HTTP',3),('UDP',3)])
            self.assertEqual(len(result['headers']),3)
            for role in selected:
                coverage=json.loads((output/'spools'/role/'REPLAY_COVERAGE.json').read_text())
                self.assertEqual(coverage['last_frame'],3)
                self.assertTrue(coverage['final_raw_identity_pass'])


if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--synthetic-child':
        synthetic_child(sys.argv[2],sys.argv[3])
    else:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EngineeringGateTests))
        here=Path(__file__).resolve().parent
        receipt=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
            failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
            frozen_model_calls=0,cloud_jobs_submitted=0,external_quality_computed=False,
            actual_mock_encoder_subprocess_exit=75,synthetic_real_core_and_knn=True,
            linux_gate_status='PENDING_NOT_EXECUTED_ON_HPC',
            source_sha256={name:sha(here/name) for name in ('engineering_gate.py','test_engineering_gate.py','worker.py')})
        (here/'ENGINEERING_GATE_TEST_RECEIPT.json').write_bytes(canonical(receipt))
        raise SystemExit(not result.wasSuccessful())
