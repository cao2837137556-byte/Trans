import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common import assemble_view, confined, read, sha, validate_approval, verify_package, write
from supervisor import run_stage
import chain


class IdentityTests(unittest.TestCase):
    def test_false_approval_and_wrong_scope_do_not_authorize(self):
        for approval in ({}, {'user_authorized': False},
                         {'user_authorized': True, 'scope': 'OTHER', 'package_sha256': 'a'}):
            with self.assertRaisesRegex(RuntimeError, 'APPROVAL'):
                validate_approval(approval, 'a', ['encode'])

    def test_stage_cannot_exceed_user_authorization(self):
        approval = dict(user_authorized=True, package_sha256='a', scope='DENSE_REFERENCE_V1',
                        stages=['runtime', 'encode', 'source_cal'], retries=0)
        validate_approval(approval, 'a', ['runtime', 'encode'])
        with self.assertRaisesRegex(RuntimeError, 'STAGE_NOT_AUTHORIZED'):
            validate_approval(approval, 'a', ['matrix'])

    def test_manifest_rejects_tamper_and_extra_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'a').write_bytes(b'a')
            (root / 'PACKAGE_SHA256SUMS').write_text(sha(root / 'a') + '  a\n')
            verify_package(root)
            (root / '.private').mkdir()
            (root / '.private/APPROVED.json').write_text('{}')
            verify_package(root)
            (root / 'extra').touch()
            with self.assertRaisesRegex(RuntimeError, 'MEMBER_SET'):
                verify_package(root)
            (root / 'a').write_bytes(b'b')
            with self.assertRaisesRegex(RuntimeError, 'PACKAGE_SHA'):
                verify_package(root)

    def test_paths_reject_escape(self):
        for value in ('../x', 'a/../../x', '/tmp/x', 'a\\b'):
            with self.assertRaises(RuntimeError):
                confined(Path.cwd(), value)

    def test_view_binds_only_registered_exact_input(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / 'source').mkdir()
            (base / 'bundle').mkdir()
            original = base / 'source/old.bin'
            original.write_bytes(b'frozen')
            manifest = {'files': [dict(path='canonical/data.bin', aliases=['old.bin'],
                bytes=6, sha256=sha(original))]}
            result = assemble_view(manifest, base / 'source', base / 'bundle', base / 'view')
            self.assertEqual(result['status'], 'PASS')
            self.assertEqual((base / 'view/canonical/data.bin').read_bytes(), b'frozen')
            original.write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError, 'MISSING_OR_CHANGED'):
                assemble_view(manifest, base / 'source', base / 'bundle', base / 'view2')
            self.assertFalse((base / 'view2').exists())


class StageTests(unittest.TestCase):
    def test_authorized_prefix_wires_exact_view_overlay_and_scoped_completion(self):
        for stages in (['runtime'], ['runtime', 'encode'], ['runtime', 'encode', 'source_cal']):
            with self.subTest(stages=stages):
                self._assert_authorized_prefix(stages)

    def _assert_authorized_prefix(self, stages):
        # A real filesystem hand-off, with scientific workers replaced by inert
        # fixtures: no model, real feature input or target evaluation is opened.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            package, output = base / 'package', base / 'out'
            write(package / 'config/chain.json', {'checkpoint_sha256': hashlib.sha256(b'checkpoint').hexdigest(),
                'matrix_execution_blockers': ['THIRD_POOL_ABSENT']})
            write(package / 'config/SOURCE_ASSET_MANIFEST.json', {'files': []})
            write(package / 'vendor/encoding_v2/data/SOURCE_REFS/DENSE_PLAN.json', {'selected_uids': []})
            (package / 'vendor/encoding_v2/SHA256SUMS').write_text('fixture\n')
            members = sorted(p for p in package.rglob('*') if p.is_file())
            (package / 'PACKAGE_SHA256SUMS').write_text(''.join(
                sha(p) + '  ' + p.relative_to(package).as_posix() + '\n' for p in members))
            (base / 'checkpoint').write_bytes(b'checkpoint')
            write(base / 'approval.json', dict(user_authorized=True,
                package_sha256=sha(package / 'PACKAGE_SHA256SUMS'), scope='DENSE_REFERENCE_V1',
                stages=stages, retries=0, total_wall_seconds=43200,
                evidence='synthetic fixture only'))
            seen = []
            def inert_worker(argv, **kwargs):
                stage = kwargs['output'].name
                seen.append(stage)
                self.assertEqual(kwargs['expected'], ('SOURCE_CAL_COMPLETE',) if stage == 'source_cal' else ('COMPLETE',))
                if stage != 'runtime':
                    self.assertEqual(kwargs['env']['PYTHONPATH'].split(os.pathsep)[0], str(output / 'runtime/numpy201'))
                if stage == 'source_cal':
                    self.assertEqual(argv[argv.index('--root') + 1], str(output / 'readonly_view'))
                    self.assertEqual(argv[argv.index('--dense-bank') + 1], str(output / 'encode/banks/SOURCE_REFS'))
                write(kwargs['output'] / 'RESULT.json', {'status': kwargs['expected'][0]})
                return {'elapsed_seconds': 0}
            with patch.object(chain, 'run_stage', side_effect=inert_worker):
                rc = chain.main(['--package', str(package), '--assets-root', str(base),
                    '--checkpoint', str(base / 'checkpoint'), '--approval-file', str(base / 'approval.json'),
                    '--output', str(output), '--stages'] + stages)
            self.assertEqual(rc, 0)
            self.assertEqual(seen, stages)
            result = read(output / 'RESULT.json')
            self.assertEqual(result['evaluation_scope'], 'AUTHORIZED_STAGE_PREFIX_ONLY')
            self.assertEqual(result['scientific_status'], 'NOT_EVALUATED')
            delegated_path = output / 'ENCODER_CAL_APPROVAL.json'
            if 'encode' not in stages:
                self.assertFalse(delegated_path.exists())
            else:
                delegated = read(delegated_path)
                self.assertFalse(delegated['matrix'])
                self.assertEqual(delegated['dense_source_cal'], 'source_cal' in stages)
                self.assertEqual(delegated['scope'], 'R2_SUPPLEMENT_AND_SOURCE_CAL'
                                 if 'source_cal' in stages else 'SUPPLEMENT_E3_ONLY')

    def test_shared_total_cap_does_not_require_sum_of_stage_caps(self):
        self.assertGreater(sum(v['wall_seconds'] for v in chain.LIMITS.values()), 43200)
        self.assertEqual(chain.stage_limits('encode', 43200, 100)['wall_seconds'], 36000)
        self.assertEqual(chain.stage_limits('matrix', 43200, 43200-17)['wall_seconds'], 17)
        with self.assertRaisesRegex(RuntimeError, 'TOTAL_WALL_LIMIT'):
            chain.stage_limits('matrix', 43200, 43200)

    def test_missing_third_pool_blocks_before_any_worker_or_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            package = base / 'package'
            write(package / 'config/chain.json', {'matrix_execution_blockers': ['THIRD_POOL_ABSENT']})
            (package / 'PACKAGE_SHA256SUMS').write_text(sha(package / 'config/chain.json') + '  config/chain.json\n')
            approval = dict(user_authorized=True, package_sha256=sha(package / 'PACKAGE_SHA256SUMS'),
                scope='DENSE_REFERENCE_V1', stages=list(chain.STAGES), retries=0, total_wall_seconds=43200)
            write(base / 'approval.json', approval)
            with patch.object(chain, 'run_stage') as worker:
                rc = chain.main(['--package', str(package), '--assets-root', str(base),
                    '--checkpoint', str(base / 'absent'), '--approval-file', str(base / 'approval.json'),
                    '--output', str(base / 'out')])
                self.assertEqual(rc, 70)
                worker.assert_not_called()
            self.assertIn('MATRIX_PREFLIGHT_BLOCKED', read(base / 'out/status.json')['reason'])

    def run_fixture(self, code, limits=None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / 'fixture.py'
            script.write_text(code)
            budget = dict(wall_seconds=5, rss_bytes=256*1024**2, output_bytes=1024**2,
                          min_free_bytes=0, poll_seconds=.03)
            budget.update(limits or {})
            try:
                return run_stage([sys.executable, '-B', str(script), str(root / 'out')],
                    output=root / 'out', control=root / 'monitor', limits=budget)
            except RuntimeError:
                self.assertEqual(read(root / 'monitor/status.json')['status'], 'EXCEPTION_STOP')
                self.assertTrue(read(root / 'monitor/status.json')['cleanup_confirmed'])
                raise

    def test_scientific_fail_is_technical_complete(self):
        result = self.run_fixture("import pathlib,json,sys\np=pathlib.Path(sys.argv[1]);p.mkdir()\n(p/'RESULT.json').write_text(json.dumps({'status':'COMPLETE','scientific_status':'FAIL'}))")
        self.assertEqual(result['status'], 'COMPLETE')
        self.assertEqual(result['scientific_status'], 'FAIL')

    def test_worker_error_stops_without_retry(self):
        with self.assertRaisesRegex(RuntimeError, 'WORKER_EXIT:7'):
            self.run_fixture('raise SystemExit(7)')

    def test_missing_complete_receipt_stops(self):
        with self.assertRaises(RuntimeError):
            self.run_fixture('pass')

    def test_wall_limit_terminates_worker(self):
        with self.assertRaisesRegex(RuntimeError, 'WALL_LIMIT'):
            self.run_fixture('import time\ntime.sleep(30)', {'wall_seconds': .1})


if __name__ == '__main__':
    unittest.main()
