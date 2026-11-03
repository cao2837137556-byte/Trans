"""Actual preparation/worker/validator pipeline on tiny generated files only."""
import ast
import copy
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import issue27frontend_paired_train_model_v1 as m
import issue27frontend_paired_train_support_v3 as s
import issue27frontend_paired_train_control_v3 as c
import issue27frontend_paired_train_fixture_driver_v3 as driver


def oracle():
    path=s.ROOT/'repo/ood/issue27frontend_f4_fieldwise_input_v1.py'
    s.require(s.sha_file(path)=='9c729a3165d19042549723f029235734595131d5e7ba344a3f605cca89677200','F4_PIN')
    node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='prefix_bytes')
    ns={'np':np,'struct':struct,'WIDTH':131,'F4Failure':ValueError}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
    return ns['prefix_bytes']


def fixture(root):
    package=root/'package';package.mkdir()
    membership=root/'membership';membership.mkdir();s.atomic_json(membership/'membership.json',{'generated_only':True});s.seal(membership)
    cs=[];sources={'parent':bytearray(),'outer':bytearray()};dest=0;reference=oracle()
    for role in ('check','train'):
        for owner in ('A','B'):
            for label in (0,1):
                key=role+owner+str(label);length=2+label
                x=np.full((length,131),.2+label,dtype=np.float32)
                name='parent' if owner=='A' else 'outer'
                offset=len(sources[name]);sources[name].extend(x.astype('<f4').tobytes())
                targets=[dict(uid=key+str(i),context_key=key,component_id=key,event=i,
                    owner=owner,label=label,old_hard=label if owner=='A' else None,
                    attack_family='attack' if label else 'benign',device_family='generated_device',
                    member='generated_member',source_group='generated_source',
                    feature_prefix_sha256=s.digest(reference(x,i))) for i in range(length)]
                cs.append(dict(key=key,role=role,component=key,length=length,source=name,
                    source_offset=offset,offset=dest,targets=targets));dest+=length*524
    plan={'contexts':cs,'targets':sum(len(c0['targets']) for c0 in cs),'feature_bytes':dest,'accounting':s.exact_accounting(cs)}
    s.atomic_json(package/'plan.json',plan)
    specs={}
    for name,data in sources.items():
        path=root/(name+'.f32le');path.write_bytes(data)
        specs[name]={'path':str(path),'sha256':s.sha_file(path),'bytes':len(data)}
    m.configure();initial=m.Student()
    s.atomic_json(package/'initial.receipt.json',{'state_sha256':m.state_hash(initial)})
    pins={str(Path(x).resolve()):s.sha_file(Path(x)) for x in (c.__file__,s.__file__)}
    config=dict(code_and_document_pins=pins,metadata_pins={},runtime_pins={sys.executable:s.sha_file(Path(sys.executable))},
        python_path=sys.executable,preparation_caps=s.PREP_CAPS,training_caps=s.CAPS,
        plan_sha256=s.sha_file(package/'plan.json'),feature_sources=specs)
    s.atomic_json(package/'execution_config.json',config)
    # Generated acceptance receipt only enables the real readiness parser in
    # this isolated fixture. It is not evidence that 30 tests ran for a package.
    s.atomic_json(package/'synthetic_acceptance.json',dict(status='PAIRED_TRAIN_IMPLEMENTATION_ACCEPTANCE_PASS',
        tests_run=30,tests_passed=30,real_feature_bytes_decoded=0,real_optimizer_steps=0,
        config_sha256=s.sha_file(package/'execution_config.json'),fixture_only=True))
    s.seal(package)
    s.atomic_json(root/'GENERATED_FIXTURE.json',{'generated_only':True,'membership_manifest_sha256':s.sha_file(membership/'SHA256SUMS'),
        'plan_sha256':config['plan_sha256']})
    return plan


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='paired_generated_');cls.root=Path(cls.tmp.name)
        cls.plan=fixture(cls.root);cls.receipts={}
        for stage in ('prepare','train'):
            proc=subprocess.run([sys.executable,'-B',str(Path(driver.__file__).resolve()),'--root',str(cls.root),'--stage',stage],
                capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=60)
            if proc.returncode:raise AssertionError(proc.stderr)
            cls.receipts[stage]=json.loads(proc.stdout)
        s.verify_manifest(cls.root/'prepare');s.verify_manifest(cls.root/'train')

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_actual_preparation_worker_and_validator(self):
        self.assertEqual(self.receipts['prepare']['verdict']['status'],'PAIRED_FEATURES_PREPARED')
        receipt=s.read_json(self.root/'prepare/access_receipt.json')
        self.assertEqual(receipt['prefixes_verified'],20);self.assertEqual(receipt['contexts_written'],8)
        self.assertEqual(receipt['feature_decoded_bytes'],self.plan['feature_bytes'])

    def test_actual_training_worker_and_validator(self):
        self.assertEqual(self.receipts['train']['verdict']['status'],'PAIRED_COMPARISON_COMPLETE')
        terminal=s.read_json(self.root/'train/worker_terminal.json')
        self.assertEqual(terminal['counts'],self.plan['accounting']['total'])
        self.assertLess((self.root/'train/worker_terminal.json').stat().st_size,65536)

    def test_actual_optimizer_and_pass_ledger(self):
        r=s.read_json(self.root/'train/access_receipt.json')
        self.assertEqual(r['optimizer_steps'],80)
        self.assertEqual(r['check_passes'],{'A':1,'AB':1});self.assertEqual(r['postfit_passes'],{'A':1,'AB':1})
        self.assertEqual(r['model_initializations'],1)

    def test_candidate_epoch_and_update_barrier(self):
        barrier=s.read_json(self.root/'train/candidates_sealed.json')
        self.assertEqual(barrier['updates'],{'A':40,'AB':40})
        for arm in ('A','AB'):
            r=barrier['candidates'][arm]
            self.assertEqual(r['epoch'],40)
            self.assertEqual(r['file_sha256'],s.sha_file(self.root/'train'/('candidate_'+arm+'.pt')))

    def test_coverage_identifies_actual_arm_supervision(self):
        rows=s.read_json(self.root/'train/check_predictions.json')
        for arm in ('A','AB'):
            for r0 in rows[arm]:
                self.assertTrue(r0['training_covered'])
                self.assertEqual(r0['arm_supervision_covered'],arm=='AB' or r0['owner']=='A')

    def test_scientific_verdict_unchanged_by_coverage_clarification(self):
        from issue27frontend_paired_train_metrics_v1 import comparison,compact_result
        rows=s.read_json(self.root/'train/check_predictions.json')
        original,_=comparison(self.plan['contexts'],{r0['uid']:r0['logit'] for r0 in rows['A']},
            {r0['uid']:r0['logit'] for r0 in rows['AB']})
        current=s.read_json(self.root/'train/comparison.json')
        self.assertEqual(compact_result(original),compact_result(current))
        for key in ('old_reference_gates','A_to_AB_negative_flips','B_normal_increment','B_attack_increment','B_attack_negative_flips','flips'):
            self.assertEqual(original[key],current[key])

    def test_production_scopes_not_rebound_by_fixture(self):
        self.assertEqual(c.s.ROOT,s.ROOT);self.assertEqual(c.s.PLAN_SHA,s.PLAN_SHA)
        self.assertFalse((s.ROOT/s.PREP).exists());self.assertFalse((s.ROOT/s.REAL).exists())

    def test_contradictory_self_consistent_outputs_rejected(self):
        # Change a receipt and update its hash: the final validator must still
        # reject the semantic mismatch, not merely notice a stale file hash.
        scope=driver.bind(self.root)
        try:
            config=c.readiness('train');receipt=s.read_json(self.root/'train/worker_terminal.json')
            access=s.read_json(self.root/'train/access_receipt.json');access['optimizer_steps']-=1
            saved_read=scope.read_json
            def read(path):
                return access if Path(path).name=='access_receipt.json' else saved_read(path)
            with patch.object(scope,'read_json',side_effect=read):
                with self.assertRaisesRegex(s.Stop,'TRAIN_ACTION_COUNTS'):c.validate_worker(receipt,self.root/'train',config)
        finally:c.s=s

    def test_wrong_bound_plan_rejected_even_with_matching_config(self):
        scope=driver.bind(self.root)
        try:
            scope.PLAN_SHA='0'*64
            with self.assertRaisesRegex(s.Stop,'PLAN_IDENTITY'):c.readiness('prepare')
        finally:c.s=s


class FailureLedgerTests(unittest.TestCase):
    def test_step_is_counted_if_later_check_raises(self):
        import time
        import issue27frontend_paired_train_runner_v3 as r
        from issue27frontend_paired_train_tests_v2 import population
        with tempfile.TemporaryDirectory(prefix='paired_generated_') as d:
            b=r.Budget(Path(d),s.CAPS,time.monotonic());b.access={'optimizer_steps':0}
            real_update=m.update
            def fail_after_update(*args,**kwargs):
                real_update(*args,**kwargs)
                raise s.Stop('GENERATED_POST_UPDATE_FAILURE')
            with patch.object(m,'update',side_effect=fail_after_update):
                with self.assertRaisesRegex(s.Stop,'GENERATED_POST_UPDATE_FAILURE'):
                    r.paired_fit(population(),m.Student(),Path(d),b)
            self.assertEqual(b.access['optimizer_steps'],1)

    def test_failed_prefix_has_exact_partial_access_and_no_model(self):
        with tempfile.TemporaryDirectory(prefix='paired_generated_') as d:
            root=Path(d);plan=fixture(root)
            # Generate a *new*, internally pinned fixture with one bad prefix.
            pkg=root/'package';(pkg/'SHA256SUMS').unlink()
            plan['contexts'][0]['targets'][0]['feature_prefix_sha256']='0'*64
            s.atomic_json(pkg/'plan.json',plan)
            config=s.read_json(pkg/'execution_config.json');config['plan_sha256']=s.sha_file(pkg/'plan.json');s.atomic_json(pkg/'execution_config.json',config)
            accept=s.read_json(pkg/'synthetic_acceptance.json');accept['config_sha256']=s.sha_file(pkg/'execution_config.json');s.atomic_json(pkg/'synthetic_acceptance.json',accept);s.seal(pkg)
            marker=s.read_json(root/'GENERATED_FIXTURE.json');marker['plan_sha256']=config['plan_sha256'];s.atomic_json(root/'GENERATED_FIXTURE.json',marker)
            p=subprocess.run([sys.executable,'-B',str(Path(driver.__file__).resolve()),'--root',str(root),'--stage','prepare'],capture_output=True,text=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads(p.stdout)['verdict']['status'],'INPUT_OR_EXECUTION_STOP')
            terminal=s.read_json(root/'prepare/worker_terminal.json');a=terminal['access']
            self.assertEqual(a['feature_decoded_bytes'],2*524)
            self.assertEqual(a['prefixes_verified'],0);self.assertEqual(a['contexts_read'],1);self.assertEqual(a['contexts_written'],0)
            self.assertEqual(a['optimizer_steps'],0);self.assertEqual(terminal['last_state']['current_uid'],'checkA00')
            s.verify_manifest(root/'prepare')


if __name__=='__main__':
    m.configure()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    report=dict(tests_run=result.testsRun,tests_passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        real_feature_bytes_decoded=0,real_optimizer_steps=0,generated_only=True,
        scope='two-source tiny generated preparation, full 40-epoch worker, unchanged final validator, Windows supervisor and seals')
    print('SYNTHETIC_RESULT '+json.dumps(report),flush=True)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
