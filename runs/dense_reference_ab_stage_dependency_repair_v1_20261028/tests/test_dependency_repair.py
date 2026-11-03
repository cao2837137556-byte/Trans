"""Isolated real-core tests of the formerly unexercised overlap lazy import."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(__file__).resolve().parents[1]
NUMPY_ROOT=str(Path(np.__file__).resolve().parent.parent)
sys.path.insert(0, str(HERE/'bootstrap'))
sys.path.insert(0, str(HERE/'src'))
from repair_runtime import dependency_manifest
from run_repaired_stage import validate_repair_approval

SCRIPT = r'''
import copy, json, pathlib, sys
sys.path.insert(0, sys.argv[3])
sys.path.insert(0, sys.argv[1])
import numpy as np
import constrained_onboarding_core_v3 as core
ref=dict(uid='SYNTHETIC|overlap', source_sha256='synthetic-sha', owner='synthetic-owner',
    component_id='synthetic-component',session_id='synthetic-session',capture_id='synthetic-capture',
    device='synthetic-device', partition='DEV', protocol=6, timestamp=1., frame=1,
    use='REFERENCE',label=0,reference_end=2.,bank_end_frame=2)
query=dict(ref,use='QUERY')
case=sys.argv[2]
bank=core.ReferenceBank([ref],np.ones((1,768)),np.zeros((1,14)),
    (np.zeros(768),np.ones(768)),feature_uids=[ref['uid']],q_uids=[ref['uid']],
    allow_prebank_history=True)
def forbidden(*a, **k): raise AssertionError('SUPPORT_DISTANCE_ENTRY_FORBIDDEN')
bank.own=bank.matrix=bank._evaluate_group=forbidden
core._second_distinct=forbidden
if case.startswith('identity:'): query[case.split(':')[1]]='bad-identity'
if case=='role': query['use']='REFERENCE'
if case=='label': query['label']=1
if case=='end': bank.rows[0]['reference_end']=0.
if case=='frame_end': bank.rows[0]['bank_end_frame']=0
q=np.zeros((1,14))
if case=='q14': q[0,0]=2.
uids=[query['uid']]
if case=='uid_join': uids=['SYNTHETIC|wrong']
if case=='guard': bank.own([],None,None,None)
bank._queries([query],np.ones((1,768)),q,uids,[query['uid']])
print(json.dumps({'ok':True,'module_path':str(pathlib.Path(core.__file__).resolve())}))
'''


class RepairTest(unittest.TestCase):
    def isolated(self, case='valid', missing=False):
        with tempfile.TemporaryDirectory(prefix='p04-dependency-isolated-') as directory:
            vendor = Path(directory)/'vendor'
            vendor.mkdir()
            for source in (HERE/'vendor/ood').glob('*.py'):
                if not missing or source.stem != 'causal_reference_overlap_v1':
                    shutil.copyfile(source, vendor/source.name)
            result = subprocess.run([sys.executable,'-I','-B','-c',SCRIPT,str(vendor),case,NUMPY_ROOT],
                cwd=directory, capture_output=True,text=True,timeout=45)
            return result

    def test_parent_five_modules_reproduce_exact_missing_lazy_dependency(self):
        result=self.isolated(missing=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("ModuleNotFoundError: No module named 'causal_reference_overlap_v1'",result.stderr)

    def test_full_six_modules_legal_overlap_passes_in_isolation(self):
        result=self.isolated()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('p04-dependency-isolated-',json.loads(result.stdout)['module_path'])

    def test_history_identity_changes_fail(self):
        for field in ('owner','source_sha256','component_id','session_id','capture_id','device'):
            with self.subTest(field=field):
                result=self.isolated('identity:'+field)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('HISTORY_REPLAY_IDENTITY_MISMATCH',result.stderr)

    def test_query_role_label_and_complete_bank_time_frame_fail(self):
        for case,reason in [('role','QUERY_ROLE'),('label','HISTORY_REPLAY_ROLE_OR_SOURCE'),
                           ('end','HISTORY_REPLAY_NOT_BEFORE_COMPLETE_BANK'),
                           ('frame_end','HISTORY_REPLAY_NOT_BEFORE_COMPLETE_BANK')]:
            with self.subTest(case=case):
                result=self.isolated(case)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(reason,result.stderr)

    def test_q14_range_and_uid_join_fail(self):
        for case,reason in [('q14','Q14_RANGE'),('uid_join','BROKEN_FEATURE_UID_JOIN')]:
            with self.subTest(case=case):
                result=self.isolated(case)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(reason,result.stderr)

    def test_support_distance_guard_is_active(self):
        result=self.isolated('guard')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('SUPPORT_DISTANCE_ENTRY_FORBIDDEN',result.stderr)

    def test_exact_frozen_six_module_closure(self):
        self.assertEqual(len(dependency_manifest(HERE)),6)

    def test_recursive_ast_closure_in_isolated_directory(self):
        with tempfile.TemporaryDirectory(prefix='p04-closure-isolated-') as directory:
            directory=Path(directory)
            shutil.copyfile(HERE/'build_overlay.py',directory/'build_overlay.py')
            shutil.copytree(HERE/'vendor/ood',directory/'vendor')
            script="import sys; sys.path.insert(0,sys.argv[1]); from build_overlay import closure; print(len(closure(sys.argv[2])))"
            result=subprocess.run([sys.executable,'-I','-B','-c',script,str(directory),
                str(directory/'vendor')],cwd=directory,capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),'6')

    def test_child_sitecustomize_loads_overlap_dependency_and_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix='p04-child-bootstrap-') as directory:
            directory=Path(directory)
            shutil.copytree(HERE/'bootstrap',directory/'bootstrap')
            shutil.copytree(HERE/'vendor',directory/'vendor')
            shutil.copyfile(HERE/'DEPENDENCY_CLOSURE.json',directory/'DEPENDENCY_CLOSURE.json')
            marker=directory/'PACKAGE_SHA256SUMS'
            marker.write_text(hashlib.sha256((directory/'DEPENDENCY_CLOSURE.json').read_bytes()).hexdigest()+
                              '  DEPENDENCY_CLOSURE.json\n')
            shadow=directory/'shadow'
            shadow.mkdir()
            (shadow/'constrained_onboarding_core_v3.py').write_text("raise RuntimeError('FALLBACK_USED')\n")
            parent=HERE.parent/'dense_reference_ab_stage_candidate_v1_20261028'
            env=dict(os.environ,PYTHONPATH=os.pathsep.join((NUMPY_ROOT,str(directory/'bootstrap'),str(parent/'src'))),
                PAPER04_DEPENDENCY_REPAIR=str(directory),
                PAPER04_REPAIR_MANIFEST_SHA256=hashlib.sha256(marker.read_bytes()).hexdigest(),
                PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1')
            result=subprocess.run([sys.executable,'-B','-c',SCRIPT,str(shadow),'valid',NUMPY_ROOT],
                cwd=directory,env=env,capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(Path(json.loads(result.stdout)['module_path']),
                directory/'vendor/ood/constrained_onboarding_core_v3.py')
            # Import the actual unchanged original matrix. Its top-level code
            # inserts the old five-module vendor before importing core/budget.
            actual_matrix="import matrix\n"+SCRIPT+"\nimport onboarding_budget_v1\n"+r'''
closure=json.loads((pathlib.Path(sys.argv[4])/'DEPENDENCY_CLOSURE.json').read_text())
for name in closure['dependencies']:
    __import__(name)
    assert pathlib.Path(sys.modules[name].__file__).resolve()==pathlib.Path(sys.argv[4])/'vendor/ood'/(name+'.py'), name
print('ALL_SIX_MODULES_STRICT_AFTER_ACTUAL_MATRIX_IMPORT')
'''
            matrix_child=subprocess.run([sys.executable,'-B','-c',actual_matrix,
                str(shadow),'valid',NUMPY_ROOT,str(directory)],cwd=directory,env=env,
                capture_output=True,text=True,timeout=45)
            self.assertEqual(matrix_child.returncode,0,matrix_child.stderr)
            self.assertIn('ALL_SIX_MODULES_STRICT_AFTER_ACTUAL_MATRIX_IMPORT',matrix_child.stdout)
            env['PAPER04_REPAIR_MANIFEST_SHA256']='0'*64
            failed=subprocess.run([sys.executable,'-B','-c',"print('UNSAFE_CONTINUATION')"],
                cwd=directory,env=env,capture_output=True,text=True,timeout=45)
            self.assertEqual(failed.returncode,78)
            self.assertIn('PAPER04_REPAIR_BOOTSTRAP_FATAL',failed.stderr)
            self.assertNotIn('UNSAFE_CONTINUATION',failed.stdout)
            env['PAPER04_REPAIR_MANIFEST_SHA256']=hashlib.sha256(marker.read_bytes()).hexdigest()
            (directory/'DEPENDENCY_CLOSURE.json').write_text(
                (directory/'DEPENDENCY_CLOSURE.json').read_text()+'\n')
            tampered=subprocess.run([sys.executable,'-B','-c',"print('UNSAFE_CONTINUATION')"],
                cwd=directory,env=env,capture_output=True,text=True,timeout=45)
            self.assertEqual(tampered.returncode,78)
            self.assertIn('REPAIR_BOOTSTRAP_CLOSURE_SEAL_SHA',tampered.stderr)

    def test_old_approval_and_template_cannot_run_repair(self):
        old=json.loads((HERE/'config/APPROVAL.template.json').read_text())
        with self.assertRaisesRegex(RuntimeError,'NEW_REPAIR_PACKAGE_AND_USER_AUTHORIZATION_REQUIRED'):
            validate_repair_approval(old,'0'*64)
        for key in ('repair_schema','repair_user_authorized','repair_manifest_sha256','repair_evidence'):
            old.pop(key,None)
        with self.assertRaises(RuntimeError): validate_repair_approval(old,'0'*64)

    def test_pinned_finder_beats_root_repo_fallback(self):
        with tempfile.TemporaryDirectory(prefix='p04-shadow-test-') as directory:
            fake=Path(directory)/'constrained_onboarding_core_v3.py'
            fake.write_text("raise AssertionError('UNSAFE_ROOT_REPO_FALLBACK')\n")
            script="""import sys, pathlib; sys.path.insert(0,sys.argv[4]); sys.path.insert(0,sys.argv[1]); from repair_runtime import install; install(sys.argv[2]); sys.path.insert(0,sys.argv[3]); import constrained_onboarding_core_v3 as c; print(pathlib.Path(c.__file__).resolve())"""
            result=subprocess.run([sys.executable,'-I','-B','-c',script,str(HERE/'bootstrap'),
                str(HERE),directory,NUMPY_ROOT],cwd=directory,capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(Path(result.stdout.strip()),(HERE/'vendor/ood/constrained_onboarding_core_v3.py').resolve())


if __name__=='__main__': unittest.main()
