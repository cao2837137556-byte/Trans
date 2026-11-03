"""Small, offline engineering checks for the evaluation-only execution boundary."""
import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    'evaluation_completion_runner', Path(__file__).with_name('run_evaluation.py'))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def put(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')


def seal(folder):
    folder = Path(folder)
    put(folder/'SEAL.json', dict(status='SEALED', spec_sha256=runner.SPEC_SHA,
        files={p.relative_to(folder).as_posix(): runner.sha(p)
               for p in folder.rglob('*') if p.is_file() and p.name != 'SEAL.json'}))


def inventory(folder, census=('protected',)):
    folder = Path(folder)
    return dict(files={p.relative_to(folder).as_posix(): dict(
        bytes=p.stat().st_size, mtime_ns=p.stat().st_mtime_ns, sha256=runner.sha(p))
        for name in census for p in (folder/name).rglob('*') if p.is_file()},
        census_roots=list(census))


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)


class BudgetTests(unittest.TestCase):
    def evidence(self):
        prefix = runner.PACKAGE+'/results/evaluation/'
        return dict(files={
            prefix+'predictions/CIC_DEV/B0/BASE/predictions.jsonl.gz': {'bytes': 11_000_000},
            prefix+'predictions/UNSW_DEV/B0/BASE/predictions.jsonl.gz': {'bytes': 13_000_000},
            prefix+'predictions/CIC_DEV/B0/BASE/summary.json': {'bytes': 70_000},
            prefix+'control_plan.json': {'bytes': 127_000_000}},
            parent_peak_rss=6*1024**3, parent_estimated_peak_rss=7*1024**3,
            parent_results_bytes=2_149_196_167, pool_rows={'CIC_DEV': 2, 'UNSW_DEV': 3})

    def test_forecast_counts_all_52_cells_and_large_final_outputs(self):
        plan = runner.budget_plan(self.evidence())
        # Include 26 predictions per pool, control plan, 52 summaries and the
        # forty-summary paired export; retained parent output is a separate scope.
        expected = (2*26*(11_000_000+13_000_000) + 2*127_000_000
                    + 2*52*70_000 + 2*40*70_000 + 1024**2 + 16*1024**2)
        self.assertEqual(plan['estimated_output_upper_bytes'], expected)
        self.assertEqual(plan['expected_main_cells']+plan['expected_control_cells'], 52)
        self.assertEqual(plan['expected_prediction_rows'], 26*5)
        self.assertEqual(plan['output_limit_bytes'], 2*1024**3)
        self.assertEqual(plan['retained_parent_results_bytes'], 2_149_196_167)
        self.assertFalse(plan['scientific_recipe_changed'])

    def test_output_or_memory_over_registered_limit_is_rejected(self):
        data = self.evidence()
        key = next(p for p in data['files'] if p.endswith('predictions.jsonl.gz'))
        data['files'][key]['bytes'] = runner.OUTPUT_LIMIT
        with self.assertRaisesRegex(runner.Stop, 'OUTPUT_FORECAST_EXCEEDS_REGISTERED_LIMIT'):
            runner.budget_plan(data)
        data = self.evidence()
        data['parent_peak_rss'] = runner.RSS_LIMIT
        with self.assertRaisesRegex(runner.Stop, 'MEMORY_FORECAST_EXCEEDS_REGISTERED_LIMIT'):
            runner.budget_plan(data)


class ProtectedInputTests(TemporaryCase):
    def test_seal_validates_and_rejects_extra_missing_and_tampered_files(self):
        folder = self.folder/'sealed'
        put(folder/'data.json', {'value': 'original'})
        seal(folder)
        self.assertEqual(runner.verify_seal(folder)['status'], 'SEALED')
        put(folder/'extra.json', {})
        with self.assertRaisesRegex(runner.Stop, 'SEAL_EXTRA_OR_MISSING_FILES'):
            runner.verify_seal(folder)
        (folder/'extra.json').unlink()
        original = (folder/'data.json').read_bytes()
        (folder/'data.json').unlink()
        with self.assertRaisesRegex(runner.Stop, 'SEAL_EXTRA_OR_MISSING_FILES'):
            runner.verify_seal(folder)
        (folder/'data.json').write_bytes(original.replace(b'original', b'tampered'))
        with self.assertRaisesRegex(runner.Stop, 'SEALED_FILE_CHANGED'):
            runner.verify_seal(folder)

    def test_path_escape_and_substituted_seal_identity_are_rejected(self):
        folder = self.folder/'sealed'
        put(folder/'data.json', {})
        seal(folder)
        with self.assertRaisesRegex(runner.Stop, 'PATH_ESCAPE'):
            runner.safe_child(folder, '../outside.json')
        put(self.folder/'outside.json', {})
        put(folder/'SEAL.json', dict(status='SEALED', spec_sha256=runner.SPEC_SHA,
            files={'../outside.json': runner.sha(self.folder/'outside.json')}))
        with self.assertRaises(runner.Stop):
            runner.verify_seal(folder)
        with self.assertRaisesRegex(runner.Stop, 'SEAL_IDENTITY'):
            runner.verify_seal(folder, expected='0'*64)

    def test_inventory_rejects_census_addition_mtime_and_same_stat_sha_changes(self):
        file = self.folder/'protected/data.bin'
        file.parent.mkdir()
        file.write_bytes(b'original')
        data = inventory(self.folder)
        runner.verify_inventory(self.folder, data)
        extra = file.with_name('extra.bin')
        extra.write_bytes(b'new')
        with self.assertRaisesRegex(runner.Stop, 'PROTECTED_DIRECTORY_CENSUS_CHANGED'):
            runner.verify_inventory(self.folder, data)
        extra.unlink()
        initial = file.stat()
        os.utime(file, ns=(initial.st_atime_ns, initial.st_mtime_ns+1_000_000_000))
        with self.assertRaisesRegex(runner.Stop, 'PROTECTED_FILE_STAT_CHANGED'):
            runner.verify_inventory(self.folder, data, full=False)
        file.write_bytes(b'tampered')
        os.utime(file, ns=(initial.st_atime_ns, initial.st_mtime_ns))
        runner.verify_inventory(self.folder, data, full=False)
        with self.assertRaisesRegex(runner.Stop, 'PROTECTED_FILE_SHA_CHANGED'):
            runner.verify_inventory(self.folder, data, full=True)


class ExecutionBoundaryTests(TemporaryCase):
    def payload(self):
        root, parent = self.folder/'new', self.folder/'parent'
        root.mkdir(); parent.mkdir()
        contract = dict(root=str(root.resolve()), parent_root=str(parent.resolve()),
                        unit=runner.UNIT, output_limit_bytes=runner.OUTPUT_LIMIT,
                        rss_guard_bytes=runner.RSS_LIMIT)
        put(root/'contract.json', contract)
        put(root/'parent_inventory.json', {'parent_results_bytes': 123})
        put(root/'DEPLOYMENT_MANIFEST.json', dict(spec_sha256=runner.SPEC_SHA,
            files={name: dict(bytes=(root/name).stat().st_size, sha256=runner.sha(root/name))
                   for name in ('contract.json', 'parent_inventory.json')}))
        return root, parent, runner.sha(root/'DEPLOYMENT_MANIFEST.json')

    def instance(self, root, parent, manifest_sha):
        with mock.patch.object(runner, 'NEW_ROOT', str(root.resolve())), \
             mock.patch.object(runner, 'PARENT', str(parent.resolve())):
            return runner.Runner(root, manifest_sha)

    def test_manifest_hash_payload_and_execution_identity_are_pinned(self):
        root, parent, manifest_sha = self.payload()
        runner.verify_payload(root, manifest_sha)
        with self.assertRaisesRegex(runner.Stop, 'NEW_PAYLOAD_MANIFEST_CHANGED'):
            runner.verify_payload(root, '0'*64)
        with mock.patch.object(runner, 'NEW_ROOT', str(root.resolve())+'-other'):
            with self.assertRaisesRegex(runner.Stop, 'EXECUTION_ROOT_IDENTITY'):
                runner.Runner(root, manifest_sha)
        path = root/'parent_inventory.json'
        path.write_bytes(path.read_bytes().replace(b'123', b'456'))
        with self.assertRaisesRegex(runner.Stop, 'NEW_PAYLOAD_CHANGED'):
            runner.verify_payload(root, manifest_sha)

    def test_existing_state_or_results_cannot_resume_or_spawn_worker(self):
        root, parent, manifest_sha = self.payload()
        for name in ('state', 'results'):
            with self.subTest(existing=name):
                instance = self.instance(root, parent, manifest_sha)
                existing = root/name
                existing.mkdir()
                with mock.patch.object(instance, 'guard') as guard, \
                     mock.patch.object(runner.subprocess, 'Popen') as spawn:
                    with self.assertRaisesRegex(runner.Stop, 'FRESH_STATE_REQUIRED_NO_RESUME'):
                        instance.execute()
                    guard.assert_not_called()
                    spawn.assert_not_called()
                self.assertFalse(instance.owns_state)
                existing.rmdir()

    def test_guard_stop_records_actual_child_exit_and_requested_termination(self):
        root, parent, manifest_sha = self.payload()
        instance = self.instance(root, parent, manifest_sha)
        actual_popen = subprocess.Popen
        children = []

        def spawn_sleep(command, **kwargs):
            child = actual_popen([sys.executable, '-c', 'import time; time.sleep(30)'], **kwargs)
            children.append(child)
            return child

        def cleanup_children():
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=3)
        self.addCleanup(cleanup_children)
        with mock.patch.object(instance, 'guard', side_effect=[None, runner.Stop('TEST_GUARD_STOP')]), \
             mock.patch.object(runner, 'verify_inventory'), \
             mock.patch.object(runner, 'verify_seal'), \
             mock.patch.object(runner, 'budget_plan', return_value={'estimated_output_upper_bytes': 1}), \
             mock.patch.object(runner.subprocess, 'Popen', side_effect=spawn_sleep):
            with self.assertRaisesRegex(runner.Stop, 'TEST_GUARD_STOP'):
                instance.execute()
        child = children[0]
        receipt = runner.read(root/'state/stages/evaluation/process_exit.json')
        self.assertNotEqual(child.returncode, 0)
        self.assertEqual(receipt['returncode'], child.returncode)
        self.assertTrue(receipt['termination_requested'])
        self.assertFalse(receipt['completion_observed'])
        self.assertFalse(receipt['normal_exit_observed'])
        self.assertFalse((root/'state/CHAIN_COMPLETE.json').exists())

    def test_terminate_finished_negative_returncode_never_reaps_or_rewrites_it(self):
        child = mock.Mock(returncode=-15)
        child.poll.return_value = -15
        runner.terminate_child(child)
        self.assertEqual(child.returncode, -15)
        child.terminate.assert_not_called()
        child.wait.assert_not_called()

    def test_terminal_worker_status_overrides_stale_running_and_keeps_internal_snapshot(self):
        root, parent, manifest_sha = self.payload()
        instance = self.instance(root, parent, manifest_sha)
        internal = dict(status='RUNNING', stage='evaluation', pool='UNSW_DEV',
                        policy='B2', arm='L_HARD', updated_at='previous-internal-time')
        put(root/'results/evaluation/status.json', internal)
        for terminal in ('EXCEPTION_STOP', 'COMPLETE'):
            with self.subTest(terminal=terminal):
                instance.complete = terminal == 'COMPLETE'
                instance.status(terminal, force=True)
                worker = runner.read(root/'state/stages/evaluation/worker.json')
                self.assertEqual(worker['status'], terminal)
                self.assertEqual(worker['last_internal_snapshot'], internal)
                self.assertEqual(runner.read(root/'state/status.json')['status'], terminal)


class EvaluationAcceptanceTests(TemporaryCase):
    def fixture(self):
        root, parent = self.folder/'new', self.folder/'parent'
        output = root/'results/evaluation'
        main, controls = runner.expected_cells()
        identities = {pool: dict(rows=n, ordered_uid_sha256=pool+'-uids',
                               base_score_sha256=pool+'-base', cut=0.5)
                      for pool, n in (('CIC_DEV', 2), ('UNSW_DEV', 3))}
        for pool, bank, arm in main | controls:
            folder = output/'predictions'/pool/bank/arm
            put(folder/'summary.json', dict(pool=pool, bank=bank, arm=arm,
                spec_sha256=runner.SPEC_SHA, **identities[pool]))
            with gzip.open(folder/'predictions.jsonl.gz', 'wb') as stream:
                for row in range(identities[pool]['rows']):
                    stream.write(json.dumps({'uid': str(row)}).encode()+b'\n')
        put(output/'paired_summary.json', dict(status='COMPLETE',
            cells=[dict(pool=p, bank=b, arm=a,
                        summary=runner.read(output/'predictions'/p/b/a/'summary.json'))
                   for p, b, a in sorted(main)]))
        put(output/'EVALUATION_COMPLETE.json',
            dict(status='COMPLETE', cells=40, synthetic_only=False))
        put(output/'decision.json', dict(status='EVALUATED', automatic_promotion=False,
            learned_benefit={'L_HARD': {'status': 'FAIL'}},
            reference_attribution={'status': 'REFERENCE_ATTRIBUTION_FAIL'}))
        one = ('CIC_DEV', 'B0', 'BASE')
        previous = parent/runner.PACKAGE/'results/evaluation/predictions'/Path(*one)/'summary.json'
        put(previous,
            runner.read(output/'predictions'/Path(*one)/'summary.json'))
        seal(output)
        previous_stat = previous.stat()
        return root, parent, dict(pool_identities=identities, files={
            previous.relative_to(parent).as_posix(): dict(bytes=previous_stat.st_size,
                mtime_ns=previous_stat.st_mtime_ns, sha256=runner.sha(previous))}), output

    def test_full_matrix_with_scientific_fail_is_engineering_complete(self):
        root, parent, data, output = self.fixture()
        progress = []
        result = runner.validate_evaluation(root, parent, data, progress.append)
        self.assertEqual((result['main_cells'], result['control_cells']), (40, 12))
        self.assertEqual(result['prediction_rows'], 26*(2+3))
        self.assertEqual(result['prior_summaries_equal'], 1)
        self.assertEqual(len(progress), 52)
        self.assertEqual(result['scientific_decision']['learned_benefit']['L_HARD']['status'], 'FAIL')
        self.assertTrue(result['engineering_completion_does_not_assert_scientific_pass'])

    def test_missing_control_rejected_even_with_40_main_cells_and_fresh_seal(self):
        root, parent, data, output = self.fixture()
        (output/'predictions/CIC_DEV/EMPTY/L_HARD/summary.json').unlink()
        seal(output)
        with self.assertRaisesRegex(runner.Stop, 'FULL_52_CELL_MATRIX_INCOMPLETE'):
            runner.validate_evaluation(root, parent, data)

    def test_gzip_truncated_row_or_wrong_count_cannot_pass_acceptance(self):
        root, parent, data, output = self.fixture()
        path = output/'predictions/CIC_DEV/B0/BASE/predictions.jsonl.gz'
        for content, message in ((b'{"uid": "0"}', 'PREDICTION_ROW_TRUNCATED'),
                                 (b'{"uid": "0"}\n', 'PREDICTION_ROW_COUNT')):
            with self.subTest(error=message):
                with gzip.open(path, 'wb') as stream:
                    stream.write(content)
                seal(output)
                with self.assertRaisesRegex(runner.Stop, message):
                    runner.validate_evaluation(root, parent, data)

    def test_previously_completed_summary_must_remain_identical(self):
        root, parent, data, output = self.fixture()
        path = parent/runner.PACKAGE/'results/evaluation/predictions/CIC_DEV/B0/BASE/summary.json'
        value = runner.read(path)
        value['previous_only_extra'] = True
        put(path, value)
        with self.assertRaisesRegex(runner.Stop, 'PREVIOUS_COMPLETED_SUMMARY_CHANGED'):
            runner.validate_evaluation(root, parent, data)

    def test_registered_prior_summary_must_exist_and_all_be_compared(self):
        root, parent, data, output = self.fixture()
        prior_name = next(iter(data['files']))
        (parent/prior_name).unlink()
        with self.assertRaises(runner.Stop):
            runner.validate_evaluation(root, parent, data)

    def test_embedded_paired_summary_must_equal_sealed_leaf_summary(self):
        root, parent, data, output = self.fixture()
        path = output/'paired_summary.json'
        value = runner.read(path)
        value['cells'][0]['summary']['additional_wrong_value'] = True
        put(path, value)
        seal(output)
        with self.assertRaises(runner.Stop):
            runner.validate_evaluation(root, parent, data)


if __name__ == '__main__':
    unittest.main()
