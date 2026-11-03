"""Prepared adoption, cumulative accounting and DEV commit tests (mock only)."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

import coordinator
import member_worker
import prepared_reuse as pr
import recovery
from hnr.common import VERSION, digest, read, rows, sha, write, write_rows
from hnr.history import create_census


class PreparedReuseChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'old/outputs/encoding/history/NETATMO'
        self.source.mkdir(parents=True);(self.source/'selection').mkdir()
        self.spec=dict(key='NETATMO',device='device',owner='owner',capture_id='capture',packets=3,
            bank_end_frame=2,reference_end_us=2,first_dev_time_us=3,
            raw=dict(sha256='a'*64),packet_index=dict(sha256='b'*64),chronological_order=dict(sha256='c'*64))
        binding={k:self.spec[k] for k in ('packets','bank_end_frame','reference_end_us','first_dev_time_us')}
        write(self.source/'ROLE_BINDING.json',binding)
        write(self.source/'LOGICAL_INPUT.json',dict(source_sha256='d'*64,
            source_kind='BYTE_PRESERVING_CHRONOLOGICAL_PCAPNG',**{k:self.spec[k] for k in ('raw','packet_index','chronological_order')}))
        for name in ('decoder_pass1.stderr.log','decoder_pass2.stderr.log'):(self.source/name).write_bytes(b'audited diagnostic')
        write(self.source/'DECODER_DIAGNOSTIC_AUDIT.json',dict(all_other_diagnostics_rejected=True,decoder_exit_zero=True,
            prior_stderr_sha256=sha(self.source/'decoder_pass1.stderr.log'),new_stderr_sha256=sha(self.source/'decoder_pass2.stderr.log')))
        db=create_census(self.source/'candidates.sqlite');rr=[]
        for frame,role,use in [(1,'HIST_REF','REFERENCE'),(3,'HIST_DEV','QUERY')]:
            row=dict(uid=digest(['d'*64,frame,'owner']),history_role=role,use=use,label=0,
                device='device',owner='owner',capture_id='capture',source_sha256='d'*64,
                origin_raw_sha256='a'*64,origin_packet_ordinal=frame,frame=frame,timestamp_us=frame,
                timestamp=frame/1e6,protocol=6,component_id=digest(frame))
            rr.append(row)
            db.execute('INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?)',(row['uid'],'device',6,row['component_id'],
                row['timestamp'],frame,role,'rank',json.dumps(row)))
            db.execute('INSERT INTO physical_origins VALUES (?,?,?,?)',('a'*64,frame,'owner',row['uid']))
        db.commit();db.close();self.metadata=sorted(rr,key=lambda r:r['uid'])
        self.selection=dict(status='SELECTED',device_scope=['device'],census_sha256=sha(self.source/'candidates.sqlite'))
        for field,role in [('ref_rows','HIST_REF'),('dev_rows','HIST_DEV')]:
            selected=[r for r in self.metadata if r['history_role']==role]
            path=self.source/'selection'/(role+'.jsonl.gz');write_rows(path,selected)
            self.selection[field]=dict(path=str(path),sha256=sha(path),rows=1,uid_sha256=digest([r['uid'] for r in selected]))
        write(self.source/'selection/SELECTION.json',self.selection)
        snapshots=[dict(uid=r['uid'],row=r,body=dict(source_sha256='d'*64),q14=[float(r['frame'])]*14)
                   for r in self.metadata]
        write_rows(self.source/'selected_snapshots.jsonl.gz',snapshots)
        self.receipt=dict(status='PREPARED',version=VERSION,input_readout='RECENT_CURRENT_INCLUSIVE',
            source_sha256='d'*64,selection=self.selection,role_binding=binding,real_E3_forwards=0,
            all_legal_endpoint_rows_exactly_replayed=True,logical_input_sha256=sha(self.source/'LOGICAL_INPUT.json'),
            census_sha256=sha(self.source/'candidates.sqlite'),snapshots_sha256=sha(self.source/'selected_snapshots.jsonl.gz'),
            diagnostic_audit_sha256=sha(self.source/'DECODER_DIAGNOSTIC_AUDIT.json'))
        write(self.source/'PREPARE_RESULT.json',self.receipt)
        write(self.root/'old/EXECUTION_CARD.json',dict(old_card=True))
        self.card=dict(recovery=dict(prepared_source_package='old',
            prepared_source_card_sha256=sha(self.root/'old/EXECUTION_CARD.json'),
            prepared_source_receipt_sha256=sha(self.source/'PREPARE_RESULT.json')))
        for name in ('encoded','selection_replay'):
            (self.source/name).mkdir();(self.source/name/'old_evidence').write_bytes(b'keep')
        (self.source/'chronological.pcapng').write_bytes(b'large raw scratch excluded')
        self.addCleanup(patch.stopall)
        patch.object(pr,'ROOT',self.root).start();patch.dict(pr.EXPECTED,ref_rows=1,dev_rows=1).start()
        def descriptor(body,row):return np.full(14,row['frame'],dtype=np.float32),{}
        patch.dict(sys.modules,{'constrained_onboarding_reference_v2':types.SimpleNamespace(
            reference_descriptor=descriptor,query_descriptor=descriptor)}).start()

    def refresh_snapshot_pin(self):
        self.receipt['snapshots_sha256']=sha(self.source/'selected_snapshots.jsonl.gz')
        write(self.source/'PREPARE_RESULT.json',self.receipt)
        self.card['recovery']['prepared_source_receipt_sha256']=sha(self.source/'PREPARE_RESULT.json')

    def test_prepared_adoption_relocates_only_paths_and_preserves_all_source_bytes(self):
        before={p.relative_to(self.source).as_posix():sha(p) for p in self.source.rglob('*') if p.is_file()}
        destination=self.root/'new'
        result=pr.reuse_prepared(self.spec,destination,card=self.card)
        self.assertEqual(result['snapshots'],2)
        self.assertFalse((destination/'encoded').exists());self.assertFalse((destination/'selection_replay').exists())
        self.assertFalse((destination/'chronological.pcapng').exists())
        derived=read(destination/'PREPARE_RESULT.json');original=read(destination/'SOURCE_PREPARE_RESULT.json')
        self.assertEqual(original,self.receipt)
        for field in ('ref_rows','dev_rows'):
            self.assertEqual(Path(derived['selection'][field]['path']).parent,destination/'selection')
            self.assertEqual(derived['selection'][field]['sha256'],original['selection'][field]['sha256'])
        derived['selection']=original['selection'];self.assertEqual(derived,original)
        self.assertEqual(before,{p.relative_to(self.source).as_posix():sha(p) for p in self.source.rglob('*') if p.is_file()})
        self.assertEqual(read(destination/'PREPARED_REUSE.json')['raw_decodes'],0)

    def test_existing_destination_is_not_overwritten(self):
        destination=self.root/'new';destination.mkdir();(destination/'evidence').write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError,'DESTINATION_NEW'):pr.reuse_prepared(self.spec,destination,card=self.card)
        self.assertEqual((destination/'evidence').read_bytes(),b'keep')

    def test_changed_snapshot_bytes_fail_original_pin(self):
        with (self.source/'selected_snapshots.jsonl.gz').open('ab') as stream:stream.write(b'changed')
        with self.assertRaisesRegex(ValueError,'PREPARED_FILE_PIN'):pr.check_prepared(self.spec,self.card)

    def test_missing_snapshot_and_wrong_role_or_q14_fail_semantic_join(self):
        original=list(rows(self.source/'selected_snapshots.jsonl.gz'))
        cases=[(original[:-1],'UID_COVERAGE')]
        for field,value,error in [('q14',[999.]*14,'Q14_REPLAY'),('uid','bad','UID_COVERAGE')]:
            changed=copy.deepcopy(original);changed[0][field]=value;cases.append((changed,error))
        changed=copy.deepcopy(original);changed[0]['row']['use']='WRONG';cases.append((changed,'SOURCE_ROW'))
        for snapshots,error in cases:
            with self.subTest(error=error):
                write_rows(self.source/'selected_snapshots.jsonl.gz',snapshots);self.refresh_snapshot_pin()
                with self.assertRaisesRegex(ValueError,error):pr.check_prepared(self.spec,self.card)

    def test_changed_census_and_old_source_card_are_rejected(self):
        with (self.source/'candidates.sqlite').open('ab') as stream:stream.write(b'changed')
        with self.assertRaisesRegex(ValueError,'PREPARED_FILE_PIN'):pr.check_prepared(self.spec,self.card)
        write(self.root/'old/EXECUTION_CARD.json',dict(changed=True))
        with self.assertRaisesRegex(ValueError,'PREPARED_SOURCE_PIN'):pr.check_prepared(self.spec,self.card)

    def test_input_role_boundary_and_directory_escape_rejected(self):
        spec=copy.deepcopy(self.spec);spec['bank_end_frame']=1
        with self.assertRaisesRegex(ValueError,'ROLE_BINDING'):pr.check_prepared(spec,self.card)
        self.card['recovery']['prepared_source_package']='../outside'
        with self.assertRaisesRegex(ValueError,'SOURCE_SCOPE'):pr.check_prepared(self.spec,self.card)


class DevCommitChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.member=Path(self.tmp.name);(self.member/'encoded').mkdir()
        write(self.member/'encoded/ENCODE_RESULT.json',dict(status='COMPLETE'))
        self.queries=dict(rows=[dict(uid='a'*64),dict(uid='b'*64)],
            e3=np.zeros((2,768),dtype=np.float32),q14=np.zeros((2,14),dtype=np.float32))
        self.assets=types.SimpleNamespace(calibration=lambda:{'frozen':True},immutable=lambda:None)
        self.calls=[]
    def scorer(self,queries,assets,frozen,runtime):
        self.calls.append(True);return dict(feature_uids=[r['uid'] for r in queries['rows']],logits=np.ones((2,3),dtype=np.float64))
    def run_score(self,**extra):
        kwargs=dict(assets=self.assets,scorer=self.scorer,card_sha256='c'*64);kwargs.update(extra)
        return member_worker.dev_logits(self.member,self.queries,object(),**kwargs)
    def test_atomic_score_and_zero_scoring_reuse(self):
        first=self.run_score();self.assertFalse(first['reused'])
        before={p.name:sha(p) for p in (self.member/'encoded').iterdir()}
        second=self.run_score();self.assertTrue(second['reused']);self.assertEqual(self.calls,[True])
        self.assertEqual(before,{p.name:sha(p) for p in (self.member/'encoded').iterdir()})
    def test_head_scoring_failure_can_retry_without_losing_encoded_member(self):
        with self.assertRaisesRegex(RuntimeError,'interrupted'):
            self.run_score(scorer=lambda *a:(_ for _ in ()).throw(RuntimeError('interrupted')))
        self.assertFalse((self.member/'encoded/DEV_LOGITS.npz').exists())
        self.assertTrue((self.member/'encoded/ENCODE_RESULT.json').exists());self.run_score()
    def test_orphan_logits_are_not_overwritten_or_rescored(self):
        (self.member/'encoded/DEV_LOGITS.npz').write_bytes(b'keep orphan')
        with self.assertRaisesRegex(ValueError,'ORPHAN'):self.run_score()
        self.assertEqual(self.calls,[]);self.assertEqual((self.member/'encoded/DEV_LOGITS.npz').read_bytes(),b'keep orphan')
    def test_card_encoding_or_array_mismatch_prevents_reuse(self):
        self.run_score()
        with self.assertRaisesRegex(ValueError,'RECEIPT_PIN'):self.run_score(card_sha256='d'*64)
        with (self.member/'encoded/DEV_LOGITS.npz').open('ab') as stream:stream.write(b'changed')
        with self.assertRaisesRegex(ValueError,'RECEIPT_PIN'):self.run_score()
        self.assertEqual(self.calls,[True])
    def test_nonfinite_or_wrong_logit_schema_never_commits(self):
        for logits in [np.ones((2,3),dtype=np.float32),np.ones((2,2)),np.full((2,3),np.nan)]:
            with self.subTest(shape=logits.shape,dtype=logits.dtype):
                with self.assertRaisesRegex(ValueError,'SCORED_SCHEMA'):
                    self.run_score(scorer=lambda *a:dict(feature_uids=[r['uid'] for r in self.queries['rows']],logits=logits))
                self.assertFalse((self.member/'encoded/DEV_LOGITS.npz').exists())


class CoordinatorChecks(unittest.TestCase):
    def test_worker_progress_separates_durable_rows_from_reserved_budget(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td);status=output/'workers/NETATMO_encode.json'
            write(status,dict(phase='HISTORY_E3',completed=100,total=12288,encoded_charged=116,work_heartbeat_utc='new'))
            write(status.with_name('NETATMO_encode_COMPLETE.json'),dict(status='COMPLETE',status_sha256=sha(status)))
            updates=[]
            runtime=types.SimpleNamespace(output=output,limits={'wall_seconds':18000},started=0,children=[],
                state={'reused_encoded_rows':20480},update=lambda *a,**kw:updates.append(kw),guard=lambda:None)
            child=types.SimpleNamespace(returncode=0,poll=unittest.mock.Mock(side_effect=[None,0]))
            with patch.object(coordinator.subprocess,'Popen',return_value=child), \
                 patch.object(coordinator.time,'monotonic',return_value=1),patch.object(coordinator.time,'sleep'):
                coordinator.launch('encode','NETATMO',runtime,12288)
            self.assertEqual(updates[0]['durable_completed_rows'],20580)
            self.assertEqual(updates[0]['netatmo_durable_encoded_rows'],100)
            self.assertEqual(updates[0]['worker_encoded_charged'],116)
            self.assertEqual(runtime.children,[])

    def test_only_net_encoder_runs_and_charges_prior_plus_net_once(self):
        import run
        with tempfile.TemporaryDirectory() as td:
            package=Path(td);write(package/'EXECUTION_CARD.json',{'card':'frozen'})
            write(package/'config/EXECUTION.json',dict(devices=[dict(key=k,display_name=k) for k in (*coordinator.KEYS,'NETATMO')]))
            card=dict(limits=dict(total_wall_seconds=46861,encoded=37442),recovery=dict(
                prior_wall_seconds_charged=28861,prior_encoded_rows_charged=25154,reused_encoded_rows=20480,new_encoded_rows=12288))
            instances=[];launches=[]
            class Budget:
                def __init__(self,output):self.output=output;self.limits={};self.charges=[];instances.append(self)
                def __enter__(self):self.output.mkdir(parents=True);return self
                def __exit__(self,*a):return False
                def update(self,*a,**kw):pass
                def encoded(self,n):self.charges.append(n)
                def finish(self,result):self.result=result
            def prepared(spec,destination,runtime,card):
                write(destination/'selection/SELECTION.json',dict(ref_rows=dict(rows=8192),dev_rows=dict(rows=4096)))
                write(destination/'encoded/ENCODE_RESULT.json',{'complete':True})
            def launch(stage,key,runtime,cap):
                launches.append((stage,key,cap));return dict(encoded_charged=12288)
            with patch.object(coordinator,'PACKAGE',package),patch.object(coordinator,'Runtime',Budget), \
                 patch.object(coordinator,'previous_status',return_value={'prior':'verified'}), \
                 patch.object(coordinator,'reuse_member',return_value={'reused':True}), \
                 patch.object(coordinator,'reuse_prepared',side_effect=prepared),patch.object(coordinator,'launch',side_effect=launch), \
                 patch.object(run,'verify',return_value=card),patch.object(run,'latch'),patch.object(run,'cleanup'):
                coordinator.encode()
            self.assertEqual(launches,[('encode','NETATMO',12288)])
            self.assertEqual(instances[0].charges,[25154,12288])
            self.assertEqual(instances[0].limits,dict(wall_seconds=18000,encoded=37442))
            self.assertEqual(instances[0].result['durable_completed_rows'],32768)
            self.assertEqual(instances[0].result['new_encoded_rows_charged'],12288)
            self.assertEqual(instances[0].result['raw_decodes_this_attempt'],0)


class PriorAccountingChecks(unittest.TestCase):
    def fixture(self,root):
        previous=root/'previous';latest=root/'latest';prepared=root/'prepared';package=root/'new'
        write(previous/'EXECUTION_CARD.json',{'job':'180552'})
        write(latest/'EXECUTION_CARD.json',{'job':'180591'})
        write(prepared/'EXECUTION_CARD.json',{'job':'180670'})
        write(previous/'outputs/encoding/STATUS.json',dict(technical_status='EXCEPTION_STOPPED',
            error='ISOLATED_NETATMO_prepare_FAILED: see log',encoded_rows=20480,pairs=0,elapsed_seconds=14626.291181526962))
        write(previous/'outputs/encoding/workers/NETATMO_prepare_ERROR.json',dict(error='DECODER_STDERR'))
        write(latest/'outputs/encoding/STATUS.json',dict(technical_status='EXCEPTION_STOPPED',
            encoded_rows=20480,pairs=0,elapsed_seconds=722.2216791909887))
        write(latest/'outputs/encoding/workers/NETATMO_prepare_ERROR.json',dict(error='AUDIT_INVALID_INTEGER:tcp.flags.syn'))
        status=prepared/'outputs/encoding/STATUS.json'
        write(status,dict(technical_status='EXCEPTION_STOPPED',error='WALL_SECONDS_LIMIT',pairs=0,
            phase='HISTORY_E3',encoded_rows=32768,worker_encoded_charged=4674,completed=4658,elapsed_seconds=4266.397972752922))
        write_rows(prepared/'outputs/encoding/history/NETATMO/encoded/BATCH_LEDGER.jsonl',[
            dict(status='ATTEMPT',logical_rows=4658),dict(status='COMPLETE',logical_rows=4658),
            dict(status='ATTEMPT',logical_rows=16)])
        card=dict(recovery=dict(previous_card_sha256=sha(previous/'EXECUTION_CARD.json'),
            latest_failed_card_sha256=sha(latest/'EXECUTION_CARD.json'),prepared_source_package='prepared',
            prepared_source_card_sha256=sha(prepared/'EXECUTION_CARD.json'),prepared_source_status_sha256=sha(status),
            prior_encoded_rows_charged=25154,reused_encoded_rows=20480,new_encoded_rows=12288,
            prior_wall_seconds_charged=28861))
        write(package/'EXECUTION_CARD.json',card)
        return previous,latest,prepared,package,card
    def test_cumulative_prior_cost_includes_lost_attempt_and_conservative_wall_tail(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);previous,latest,prepared,package,card=self.fixture(root)
            with patch.object(recovery,'PREVIOUS',previous),patch.object(recovery,'LATEST',latest), \
                 patch.object(recovery,'PACKAGE',package),patch.object(pr,'ROOT',root):
                value=recovery.previous_status()
            self.assertEqual(value['prior_wall_seconds_charged'],28861)
            self.assertEqual(value['prior_encoded_rows_charged'],25154)
            self.assertEqual(value['unrecoverable_legacy_completed_rows'],4658)
    def test_reset_prior_cost_or_existing_evaluation_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);previous,latest,prepared,package,card=self.fixture(root)
            with patch.object(recovery,'PREVIOUS',previous),patch.object(recovery,'LATEST',latest), \
                 patch.object(recovery,'PACKAGE',package),patch.object(pr,'ROOT',root):
                card['recovery']['prior_encoded_rows_charged']=20480;write(package/'EXECUTION_CARD.json',card)
                with self.assertRaisesRegex(ValueError,'CUMULATIVE_FORWARD_ACCOUNTING'):recovery.previous_status()
                card['recovery']['prior_encoded_rows_charged']=25154;write(package/'EXECUTION_CARD.json',card)
                (prepared/'outputs/evaluation').mkdir()
                with self.assertRaisesRegex(ValueError,'NO_EVALUATION'):recovery.previous_status()


if __name__=='__main__':unittest.main(verbosity=2)
