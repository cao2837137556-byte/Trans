import copy,json,tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch
import numpy as np
import legacy_reference_executor_common_v1 as c
import legacy_reference_executor_features_v1 as f
import legacy_reference_hpc_parallel_v1 as h
import legacy_reference_hpc_runtime_v1 as rt
from legacy_reference_executor_fixture_v1 import create
class ParallelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_package=c.PACKAGE
        parent=c.ROOT/'runs/legacy_reference_hpc_preparation_v1_20260918/tests'
        parent.mkdir(parents=True,exist_ok=True)
        cls.root=Path(tempfile.mkdtemp(prefix='synthetic_',dir=parent));c.PACKAGE=cls.root
        cls.fixture=c.load(create(cls.root/'synthetic/input'));cls.recipe=cls.fixture['recipe']
        cls.plan=h.plan(cls.recipe,cls.root/'plan',2)
        f.prepare(cls.recipe,cls.root/'serial','LEARN_DEV',fixture=cls.fixture)
        cls.shards=[]
        for i,path in enumerate(cls.plan['shard_recipes']):
            sr=c.load(path);fx=copy.deepcopy(cls.fixture);fx['recipe']=sr
            out=cls.root/('shard_'+str(i));f.prepare(sr,out,'LEARN_DEV',fixture=fx);cls.shards.append(out)
        h.merge(cls.recipe,cls.root/'plan',cls.shards,cls.root/'merged')
    @classmethod
    def tearDownClass(cls):c.PACKAGE=cls.old_package
    def test_parallel_equals_serial_every_uid(self):
        for role in ('LEARN','DEV','REFERENCE'):
            a,ar=f.load_cache(self.root/'serial',role,c.digest(self.recipe));b,br=f.load_cache(self.root/'merged',role,c.digest(self.recipe))
            self.assertEqual(ar,br);np.testing.assert_array_equal(a,b)
    def test_capture_not_split(self):
        ownership={}
        for i,path in enumerate(self.plan['shard_recipes']):
            r=c.load(path)
            for role in ('LEARN','DEV'):
                for row in c.rows(r['data']['manifests'][role]['path']):
                    self.assertEqual(ownership.setdefault(row['capture_id'],i),i)
    def test_weights_unchanged(self):
        original={r['uid']:r for role in ('LEARN','DEV') for r in h.source_rows(self.recipe,role)}
        found={}
        for path in self.plan['shard_recipes']:
            for role in ('LEARN','DEV'):
                for row in c.rows(c.load(path)['data']['manifests'][role]['path']):
                    self.assertNotIn(row['uid'],found);found[row['uid']]=row
        self.assertEqual(found,original)
    def test_missing_shard_rejected(self):
        with self.assertRaises(c.Stop):h.merge(self.recipe,self.root/'plan',self.shards[:1],self.root/'bad_missing')
    def test_duplicate_shard_rejected(self):
        with self.assertRaises(c.Stop):h.merge(self.recipe,self.root/'plan',[self.shards[0]]*2,self.root/'bad_duplicate')
    def test_recipe_change_rejected(self):
        r=copy.deepcopy(self.recipe);r['legacy']['threshold_probability']=.9
        with self.assertRaises(c.Stop):h.merge(r,self.root/'plan',self.shards,self.root/'bad_recipe')
    def test_scope_forbids_holdout(self):
        with self.assertRaises(c.Stop):h.source_rows(self.recipe,'DEVICE_HOLDOUT')
    def test_source_tamper_rejected(self):
        r=copy.deepcopy(self.recipe);r['data']['manifests']['LEARN']['sha256']='0'*64
        with self.assertRaises(c.Stop):h.source_rows(r,'LEARN')
    def test_relocation_only_paths(self):
        r=rt.relocate(self.recipe,c.ROOT,c.ROOT/'runs/test_meta',Path('/source'),Path('/checkpoint'))
        self.assertEqual(r['optimization'],self.recipe['optimization']);self.assertEqual(r['evaluation'],self.recipe['evaluation'])
        self.assertEqual(r['data']['manifests']['DEVICE_HOLDOUT']['path'],'FORBIDDEN_HOLDOUT_QUERY')
        for role in ('LEARN','DEV','REFERENCE'):self.assertNotIn(chr(92),r['data']['manifests'][role]['path'])
    def test_worker_rejects_holdout_operation(self):
        import legacy_reference_hpc_control_v1 as control
        run=self.root/'forbidden';(run/'requests').mkdir(parents=True)
        req=run/'requests/q.json';c.atomic_json(req,dict(operation='HOLDOUT',out=str(run/'out')))
        with patch.object(rt,'install',return_value=self.recipe),self.assertRaisesRegex(c.Stop,'NO_HOLDOUT_OPERATION'):
            control.worker(run,req)
if __name__=='__main__':unittest.main(verbosity=2)
