"""Check the actual configured package, its budget derivation and frozen science."""
import hashlib
import json
import math
import os
from pathlib import Path
import unittest
import query_tail_resources_v1 as resources


class ConfiguredPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(os.environ.get('QUERY_TAIL_TEST_ROOT',Path(__file__).resolve().parents[2]))
        cls.plan=resources.load(cls.root/'resource_plan.json')
        cls.runtime=json.loads((cls.root/'runtime_contract.json').read_text())

    def test_phase_components_and_single_margin_derive_allocation(self):
        for phase in self.plan['phases'].values():
            total=sum(x['gib_per_instance']*x['instances'] for x in phase['components'])
            self.assertAlmostEqual(total,phase['component_total_gib'])
            self.assertEqual(phase['simultaneous_peak_gib'],math.ceil(total*2)/2)
            self.assertEqual(phase['basis'],'ESTIMATED')
        peak=max(x['simultaneous_peak_gib'] for x in self.plan['phases'].values())
        self.assertEqual(self.plan['memory_gib'],math.ceil(peak*(1+self.plan['margin_fraction'])/2)*2)

    def test_runtime_has_no_inactive_or_conflicting_allocation(self):
        runtime=resources.runtime(self.runtime,self.plan)
        for key in ('cpus','train_workers','threads_per_worker','limits','worker_limits','slurm'):
            self.assertEqual(runtime[key],self.runtime[key])
        self.assertEqual(self.runtime['engineering_revision']['allocation_status'],
                         'CONFIGURED_ESTIMATE_TARGET_VERIFICATION_PENDING')
        self.assertFalse(self.runtime['real_execution_authorized'])
        self.assertEqual(self.runtime['retries'],0)

    def test_parent_and_all_worker_guards_fit_total_guard(self):
        phase=self.plan['phases']['T_TRAINING']
        parent=next(x['gib_per_instance'] for x in phase['components'] if x['name']=='parent_retained_heap_and_supervisor')
        self.assertLessEqual(parent+self.plan['train_workers']*self.plan['worker_guard_gib'],self.plan['guard_gib'])
        self.assertEqual(self.plan['train_workers'],3)
        self.assertEqual(self.plan['threads_per_worker'],4)
        self.assertGreaterEqual(self.plan['cpus'],self.plan['train_workers']*4)

    def test_resource_workload_binds_design_and_unchanged_scientific_files(self):
        identity=self.plan['workload_identity']
        self.assertEqual(hashlib.sha256((self.root/'design_contract.json').read_bytes()).hexdigest(),identity['design_sha256'])
        for name,expected in identity['scientific_modules'].items():
            self.assertEqual(hashlib.sha256((self.root/'repo/ood'/name).read_bytes()).hexdigest(),expected)
        self.assertEqual(identity['new_heads'],9);self.assertEqual(identity['optimizer_updates'],869040)
        self.assertEqual(identity['epochs'],40);self.assertEqual(identity['batch_size'],256)
        self.assertFalse(identity['frontend_rebuild']);self.assertFalse(identity['onboarding'])

    def test_disk_time_and_export_bounds_are_the_executed_runtime_values(self):
        bounds=self.plan['execution_bounds']
        self.assertEqual(self.runtime['limits']['wall_seconds'],bounds['runtime_wall_seconds'])
        self.assertEqual(self.runtime['worker_limits']['wall_seconds'],bounds['runtime_wall_seconds'])
        self.assertEqual(self.runtime['slurm']['time'],bounds['slurm_time'])
        self.assertEqual(self.runtime['limits']['disk_gib'],bounds['run_disk_guard_gib'])
        self.assertEqual(self.runtime['worker_limits']['disk_gib'],bounds['worker_monitor_disk_guard_gib'])
        self.assertEqual(self.runtime['minimum_free_gib'],bounds['minimum_free_gib'])
        self.assertLess(bounds['expected_new_output_gib'],bounds['export_included_limit_gib'])
        self.assertGreaterEqual(bounds['minimum_free_gib'],bounds['run_disk_guard_gib']+bounds['export_included_limit_gib']+1)
        script=(self.root/'scripts/run.slurm').read_text()
        self.assertIn('#SBATCH --time='+bounds['slurm_time'],script)
        self.assertIn('test_query_tail_configured_v2r3',script)


if __name__=='__main__':unittest.main()
