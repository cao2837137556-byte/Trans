"""Repair contract and real chain hand-off with inert scientific workers."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import repair_gate as gate
import run_repaired_chain as repaired
from inert_test_support import frozen_test_root


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def environment(numpy_path):
    return dict(status='PASS', python='fixed synthetic runtime', neural_forwards=0, checkpoint_loads=0,
        torch_cpu_capability='AVX2', torch_config='synthetic fixed build',
        dependencies={'numpy':dict(version='2.0.1',path=str(numpy_path)),
                      'torch':dict(version='2.5.1',path='/fixed/torch/__init__.py')})


def budget_fixture():
    values=dict(name='ORIGINAL104',logical_rows=104,physical_positions=224,clone_positions=120,
                singleton_batches=8,batches=21,queue_sha256='synthetic-uid-order',shape_counts=[])
    return dict(policy='synthetic singleton policy',datasets=[values],
                totals={k:values[k] for k in ('logical_rows','physical_positions','clone_positions','singleton_batches','batches')})


def completed_encoding(output, budget, budget_file):
    output.mkdir(parents=True)
    gate.write(output/'BATCH_REPAIR_BATCHES.jsonl', {'synthetic':'no real forwards'})
    receipt=dict(status='COMPLETE',policy=budget['policy'],budget_sha256=gate.sha(budget_file),
        budget_content_sha256=digest(budget),totals=budget['totals'],clone_rows_in_bank=0,
        logical_uids_unchanged=True,target_query_inputs=0,
        batch_ledger_sha256=gate.sha(output/'BATCH_REPAIR_BATCHES.jsonl'),
        datasets=[dict(item,actual={k:item[k] for k in
            ('logical_rows','physical_positions','clone_positions','singleton_batches','batches')}) for item in budget['datasets']])
    gate.write(output/'BATCH_REPAIR_RECEIPT.json',receipt)
    gate.write(output/'ORIGINAL104_PARITY.json',dict(original104_exact_bytes=True,mismatch_count=0,max_abs_error=0))
    gate.write(output/'RESULT.json',dict(status='COMPLETE',mode='encode',batch_repair_verified=True,
        batch_repair_receipt_sha256=gate.sha(output/'BATCH_REPAIR_RECEIPT.json'),
        no_training=True,target_evaluation=False,package_sha256=repaired.ENCODING_PACKAGE_SHA,
        datasets=[dict(name=item['name'],measured_rows=item['logical_rows']) for item in budget['datasets']]))


class ContractTests(unittest.TestCase):
    def test_manifest_crlf_bytes_exact_without_rewriting_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'payload').write_bytes(b'frozen')
            raw=(gate.sha(root/'payload')+'  payload\r\n').encode();(root/'SEAL').write_bytes(raw)
            checksum=hashlib.sha256(raw).hexdigest()
            self.assertEqual(gate.verify_tree(root,'SEAL',checksum,1)['files'],1)
            self.assertEqual((root/'SEAL').read_bytes(),raw)
            (root/'payload').write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'SEALED_MEMBER_SHA'):gate.verify_tree(root,'SEAL',checksum,1)

    def test_extra_member_and_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'a').write_bytes(b'a');(root/'extra').write_bytes(b'extra')
            (root/'SEAL').write_text(gate.sha(root/'a')+'  a\n',encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError,'MEMBER_SET'):gate.verify_tree(root,'SEAL')
            (root/'SEAL').write_text('0'*64+'  ../outside\n',encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError,'MANIFEST_PATH'):gate.verify_tree(root,'SEAL')

    def test_false_template_or_scope_resources_retries_cannot_execute(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);gate.write(root/'REPAIR_MANIFEST.json',dict(budget_sha256='budget'))
            gate.write(root/'ENCODER_PHYSICAL_BUDGET.json',{})
            proof=dict(overlay=dict(manifest_sha256='seal'))
            approval=dict(schema='paper04-dense-singleton-batch-repair-approval-v1',user_authorized=True,
                scope=gate.SCOPE,overlay_manifest_sha256='seal',original_manifest_sha256=gate.ORIGINAL_SHA,
                budget_sha256='budget',stages=gate.STAGES,limits=gate.LIMITS,
                authorized_new_submissions=1,automatic_retry=False,target_evaluation=False,
                optimizer_updates=0,evidence='inert synthetic fixture')
            gate.authorize(approval,root,proof)
            for changes in ({'user_authorized':False},{'target_evaluation':True},{'automatic_retry':True},
                            {'limits':dict(gate.LIMITS,slurm_cpus=8)},{'stages':gate.STAGES+['matrix']},
                            {'budget_sha256':'wrong'},{'authorized_new_submissions':True}):
                with self.subTest(changes=changes),self.assertRaisesRegex(RuntimeError,'APPROVAL_REQUIRED'):
                    gate.authorize(dict(approval,**changes),root,proof)

    def test_complete_launch_requires_child_complete_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.assertEqual(gate.record(root,'complete','COMPLETE',0)['status'],'EXCEPTION_STOP')
            (root/'science').mkdir();gate.write(root/'science/status.json',dict(status='COMPLETE'))
            self.assertEqual(gate.record(root,'complete','COMPLETE',0)['status'],'COMPLETE')

    def test_runtime_accepts_new_numpy_directory_and_rejects_build_or_module_drift(self):
        expected=environment('/old/numpy/__init__.py');actual=environment('/new/numpy/__init__.py')
        repaired.runtime_identity(actual,expected,'/new')
        for changes in ({'torch_config':'changed'},{'python':'changed'},{'neural_forwards':1}):
            with self.subTest(changes=changes),self.assertRaises(RuntimeError):
                repaired.runtime_identity(dict(actual,**changes),expected,'/new')
        actual['dependencies']['torch']['path']='/other/torch.py'
        with self.assertRaisesRegex(RuntimeError,'DEPENDENCY_IDENTITY'):repaired.runtime_identity(actual,expected,'/new')


class PipelineTests(unittest.TestCase):
    def test_source_cal_requires_verified_encoding_ledger_budget_and_zero_tolerance(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);budget=budget_fixture();path=root/'budget.json';gate.write(path,budget)
            output=root/'encode';completed_encoding(output,budget,path)
            repaired.encoding_identity(output,budget,path)
            gate.write(output/'ORIGINAL104_PARITY.json',dict(original104_exact_bytes=True,mismatch_count=0,max_abs_error=1e-9))
            with self.assertRaisesRegex(RuntimeError,'ZERO_TOLERANCE'):repaired.encoding_identity(output,budget,path)
            gate.write(output/'ORIGINAL104_PARITY.json',dict(original104_exact_bytes=True,mismatch_count=0,max_abs_error=0))
            (output/'BATCH_REPAIR_BATCHES.jsonl').write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'LEDGER_IDENTITY'):repaired.encoding_identity(output,budget,path)

    def test_unverified_or_wrong_receipt_blocks_cal_before_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);budget=budget_fixture();gate.write(root/'ENCODER_PHYSICAL_BUDGET.json',budget)
            completed_encoding(root/'out/encode',budget,root/'ENCODER_PHYSICAL_BUDGET.json')
            result=gate.read(root/'out/encode/RESULT.json');result['batch_repair_verified']=False
            gate.write(root/'out/encode/RESULT.json',result)
            calls=[];chain=SimpleNamespace(run_stage=lambda *a,**kw:calls.append(a))
            runner=repaired.make_runner(chain,root/'original',root,root/'out',budget)
            with self.assertRaisesRegex(RuntimeError,'COMPLETE_RECEIPT'):
                runner(['inert'],output=root/'out/source_cal')
            self.assertEqual(calls,[])

    def test_encoder_command_identity_and_matrix_rejected_before_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);calls=[];chain=SimpleNamespace(run_stage=lambda *a,**kw:calls.append(a))
            runner=repaired.make_runner(chain,root/'original',root,root/'out',budget_fixture())
            with self.assertRaisesRegex(RuntimeError,'EXACT_ORIGINAL_ENCODER'):runner(['other'],output=root/'out/encode')
            with self.assertRaisesRegex(RuntimeError,'PREFIX_ONLY'):runner(['other'],output=root/'out/matrix')
            self.assertEqual(calls,[])

    def test_actual_frozen_chain_runs_runtime_adapter_cal_in_order_with_inert_workers(self):
        frozen=frozen_test_root()
        sys.path.insert(0,str(frozen/'src'))
        spec=importlib.util.spec_from_file_location('frozen_chain_repair_integration',frozen/'src/chain.py')
        chain=importlib.util.module_from_spec(spec);spec.loader.exec_module(chain)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);original=root/'original';overlay=root/'overlay';overlay.mkdir();output=root/'job/science'
            gate.write(original/'config/chain.json',dict(checkpoint_sha256=hashlib.sha256(b'checkpoint').hexdigest()))
            gate.write(original/'config/SOURCE_ASSET_MANIFEST.json',dict(files=[]))
            gate.write(original/'vendor/encoding_v2/data/SOURCE_REFS/DENSE_PLAN.json',dict(selected_uids=[]))
            (original/'vendor/encoding_v2/SHA256SUMS').write_text('inert fixture\n',encoding='utf-8')
            members=sorted(p for p in original.rglob('*') if p.is_file())
            (original/'PACKAGE_SHA256SUMS').write_text(''.join(gate.sha(p)+'  '+p.relative_to(original).as_posix()+'\n' for p in members),encoding='utf-8')
            (root/'checkpoint').write_bytes(b'checkpoint')
            gate.write(root/'approval.json',dict(user_authorized=True,scope='DENSE_REFERENCE_V1',
                package_sha256=gate.sha(original/'PACKAGE_SHA256SUMS'),stages=gate.STAGES,retries=0,total_wall_seconds=43200))
            budget=budget_fixture();gate.write(overlay/'ENCODER_PHYSICAL_BUDGET.json',budget)
            expected=environment('/old/numpy/__init__.py');gate.write(overlay/'RUNTIME_BINDING_179536.json',expected)
            calls=[]
            def inert(argv,**kw):
                stage=Path(kw['output']).name;calls.append(stage)
                if stage=='runtime':
                    gate.write(kw['output']/'environment.json',environment(output/'runtime/numpy201/numpy/__init__.py'))
                    gate.write(kw['output']/'RESULT.json',dict(status='COMPLETE'))
                elif stage=='encode':
                    self.assertEqual(argv[3],str(overlay/'encoder_adapter.py'))
                    self.assertEqual(argv[argv.index('--frozen-root')+1],str(original))
                    self.assertEqual(kw['env']['PYTHONPATH'].split(os.pathsep)[0],str(output/'runtime/numpy201'))
                    completed_encoding(kw['output'],budget,overlay/'ENCODER_PHYSICAL_BUDGET.json')
                elif stage=='source_cal':
                    self.assertEqual(argv[3],str(original/'src/source_cal.py'))
                    self.assertEqual(argv[argv.index('--dense-bank')+1],str(output/'encode/banks/SOURCE_REFS'))
                    gate.write(kw['output']/'RESULT.json',dict(status='SOURCE_CAL_COMPLETE'))
                return dict(elapsed_seconds=0)
            chain.run_stage=inert;chain.run_stage=repaired.make_runner(chain,original,overlay,output,budget)
            rc=chain.main(['--package',str(original),'--assets-root',str(root),'--checkpoint',str(root/'checkpoint'),
                '--approval-file',str(root/'approval.json'),'--output',str(output),'--stages']+gate.STAGES)
            self.assertEqual(rc,0);self.assertEqual(calls,gate.STAGES)
            self.assertEqual(gate.read(output/'status.json')['status'],'COMPLETE')
            self.assertEqual(gate.read(output/'RESULT.json')['evaluation_scope'],'AUTHORIZED_STAGE_PREFIX_ONLY')


if __name__=='__main__':
    unittest.main()
