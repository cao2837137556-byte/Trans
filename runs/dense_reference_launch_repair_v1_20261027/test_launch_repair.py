"""Local-only launch-gate tests. No model, network, or scheduler calls."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('launch_repair', HERE/'verify_original.py')
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def manifest_bytes(entries, newline=b'\n'):
    return newline.join((checksum+'  '+name).encode() for name, checksum in entries)+newline


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'a.txt').write_bytes(b'unchanged data\n')
        (self.root/'sub').mkdir()
        (self.root/'sub/b.txt').write_bytes(b'second payload\x00')
        self.entries = [('a.txt', digest((self.root/'a.txt').read_bytes())),
                        ('sub/b.txt', digest((self.root/'sub/b.txt').read_bytes()))]

    def seal(self, newline=b'\n'):
        raw = manifest_bytes(self.entries, newline)
        (self.root/'PACKAGE_SHA256SUMS').write_bytes(raw)
        return raw

    def assert_parse_failure(self, raw, reason):
        with self.assertRaisesRegex(ValueError, reason):
            repair.parse_manifest(raw, digest(raw), len(raw.split(b'\n'))-1)

    def test_lf_and_crlf_verify_all_bytes_and_preserve_original_manifest(self):
        for newline, count in ((b'\n', 0), (b'\r\n', 2)):
            with self.subTest(newline=newline):
                raw = self.seal(newline)
                before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                          for p in self.root.rglob('*') if p.is_file()}
                result = repair.verify(self.root, digest(raw), 2)
                self.assertEqual(result['files_verified'], 2)
                self.assertEqual(result['CRLF_records'], count)
                self.assertFalse(result['original_files_modified'])
                self.assertEqual(before, {p.relative_to(self.root).as_posix(): p.read_bytes()
                                         for p in self.root.rglob('*') if p.is_file()})

    def test_raw_manifest_newline_tamper_does_not_normalize_before_hash(self):
        raw = self.seal(b'\r\n')
        with self.assertRaisesRegex(ValueError, 'RAW_MANIFEST_SHA256'):
            repair.parse_manifest(raw.replace(b'\r\n', b'\n'), digest(raw), 2)

    def test_file_tamper_rejected(self):
        raw = self.seal(b'\r\n')
        (self.root/'a.txt').write_bytes(b'tampered\n')
        with self.assertRaisesRegex(ValueError, 'SEALED_MEMBER_SHA256:a.txt'):
            repair.verify(self.root, digest(raw), 2)

    def test_missing_and_extra_files_rejected(self):
        raw = self.seal()
        (self.root/'a.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'SEALED_MEMBER_SET'):
            repair.verify(self.root, digest(raw), 2)
        (self.root/'a.txt').write_bytes(b'unchanged data\n')
        (self.root/'extra.txt').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'SEALED_MEMBER_SET'):
            repair.verify(self.root, digest(raw), 2)

    def test_internal_cr_nul_and_empty_record_rejected(self):
        for suffix in (b'a\rb.txt', b'a\x00.txt', b'a.txt\r\r'):
            self.assert_parse_failure(b'a'*64+b'  '+suffix+b'\n', 'NON_TERMINAL_CR_OR_EMPTY_RECORD')
        self.assert_parse_failure(b'a'*64+b'  a.txt\n\n', 'NON_TERMINAL_CR_OR_EMPTY_RECORD')

    def test_missing_final_lf_rejected(self):
        self.assert_parse_failure(b'a'*64+b'  a.txt', 'MANIFEST_FINAL_LF_REQUIRED')

    def test_unsafe_noncanonical_self_and_duplicate_paths_rejected(self):
        unsafe = ('../x', '/tmp/x', 'C:/x', 'a\\b', 'a//b', './a', 'a/../b',
                  'PACKAGE_SHA256SUMS', 'OVERLAY_SHA256SUMS')
        for name in unsafe:
            with self.subTest(name=name):
                self.assert_parse_failure(manifest_bytes([(name, 'a'*64)]), 'MANIFEST_PATH_OR_DUPLICATE')
        self.assert_parse_failure(manifest_bytes([('a', 'a'*64), ('a', 'b'*64)]), 'MANIFEST_PATH_OR_DUPLICATE')

    def test_malformed_digest_separator_and_count_rejected(self):
        self.assert_parse_failure(b'A'*64+b'  a.txt\n', 'MANIFEST_RECORD_FORMAT')
        self.assert_parse_failure(b'a'*64+b' a.txt\n', 'MANIFEST_RECORD_FORMAT')
        raw = self.seal()
        with self.assertRaisesRegex(ValueError, 'MANIFEST_FILE_COUNT'):
            repair.parse_manifest(raw, digest(raw), 1)

    def test_symlink_rejected_when_host_allows_it(self):
        raw = self.seal()
        try:
            (self.root/'link').symlink_to(self.root/'a.txt')
        except OSError:
            self.skipTest('Host does not permit unprivileged symlink creation')
        with self.assertRaisesRegex(ValueError, 'SEALED_MEMBER_SYMLINK'):
            repair.verify(self.root, digest(raw), 2)

    def test_symlink_flag_always_rejected_without_requiring_windows_privilege(self):
        raw = self.seal()
        original = Path.is_symlink
        def flagged(path):
            return path == self.root/'a.txt' or original(path)
        with mock.patch.object(Path, 'is_symlink', flagged):
            with self.assertRaisesRegex(ValueError, 'SEALED_MEMBER_SYMLINK'):
                repair.verify(self.root, digest(raw), 2)

    def test_explicit_runtime_exclusions_do_not_change_sealed_members(self):
        raw = self.seal()
        (self.root/'runtime').mkdir()
        (self.root/'runtime/old_receipt.json').write_text('{}')
        self.assertEqual(repair.verify(self.root, digest(raw), 2, ignored=('runtime',))['status'], 'PASS')
        self.assertEqual((self.root/'runtime/old_receipt.json').read_text(), '{}')


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.old = dict(user_authorized=True, scope='DENSE_REFERENCE_V1',
            package_sha256=repair.ORIGINAL_MANIFEST_SHA, stages=repair.STAGES,
            retries=0, total_wall_seconds=43200, evidence={'original': 'preserved'})
        self.new = dict(schema='dense-reference-launch-repair-approval-v1',
            user_authorized=True, scope='LAUNCH_CRLF_AND_EXTERNAL_OUTPUT_REPAIR_ONLY',
            overlay_manifest_sha256='b'*64, original_manifest_sha256=repair.ORIGINAL_MANIFEST_SHA,
            original_launcher_sha256=repair.ORIGINAL_LAUNCHER_SHA,
            original_approval_sha256=repair.ORIGINAL_APPROVAL_SHA,
            previous_failed_job_id=repair.PREVIOUS_JOB, stages=repair.STAGES,
            authorized_new_submissions=1, automatic_resubmit=False, retries=0,
            total_wall_seconds=43200, evidence={'test': 'synthetic fixture only'})

    def check(self, approval=None, old=None, old_sha=None):
        repair.approval_gate(approval if approval is not None else self.new,
            old if old is not None else self.old,
            repair.ORIGINAL_APPROVAL_SHA if old_sha is None else old_sha, 'b'*64)

    def test_explicit_one_new_submission_and_original_identity_pass_without_mutation(self):
        before = copy.deepcopy((self.old, self.new))
        self.check()
        self.assertEqual(before, (self.old, self.new))

    def test_false_template_prior_job_or_auto_retry_cannot_authorize(self):
        changes = [dict(user_authorized=False), dict(authorized_new_submissions=0),
            dict(authorized_new_submissions=True), dict(automatic_resubmit=True),
            dict(retries=1), dict(previous_failed_job_id='179524'), dict(stages=['runtime','encode','source_cal','matrix']),
            dict(total_wall_seconds=86400), dict(evidence={})]
        for changeset in changes:
            with self.subTest(changeset=changeset):
                approval = dict(self.new, **changeset)
                with self.assertRaisesRegex(ValueError, 'EXPLICIT_NEW_LAUNCH_REPAIR_AUTHORIZATION_REQUIRED'):
                    self.check(approval)

    def test_all_pinned_repair_identities_rejected_on_mismatch(self):
        for name in ('original_manifest_sha256', 'original_launcher_sha256',
                     'original_approval_sha256', 'overlay_manifest_sha256'):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, 'EXPLICIT_NEW_LAUNCH_REPAIR_AUTHORIZATION_REQUIRED'):
                    self.check(dict(self.new, **{name:'a'*64}))

    def test_original_approval_scope_hash_and_bytes_cannot_be_replaced(self):
        for changeset in (dict(scope='OTHER'), dict(user_authorized=False), dict(retries=1),
                          dict(stages=['runtime']), dict(package_sha256='a'*64)):
            with self.subTest(changeset=changeset):
                with self.assertRaisesRegex(ValueError, 'ORIGINAL_APPROVAL_IDENTITY'):
                    self.check(old=dict(self.old, **changeset))
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_APPROVAL_IDENTITY'):
            self.check(old_sha='a'*64)


class DiagnosticsAndBashTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_record_cli_exposes_actual_stage_code_and_line(self):
        subprocess.run([sys.executable, '-B', str(HERE/'verify_original.py'), 'record',
            '--output', str(self.root), '--stage', 'environment_source', '--status', 'EXCEPTION_STOP',
            '--exit-code', '17', '--line', '89'], check=True, capture_output=True, text=True)
        value = json.loads((self.root/'launch.json').read_text())
        self.assertEqual((value['stage'], value['returncode'], value['failure_line']), ('environment_source', 17, 89))
        self.assertEqual(value['reason'], 'LAUNCH_STAGE:environment_source:EXIT17:LINE89')
        self.assertEqual(value['previous_failed_job_id'], '179523')
        self.assertEqual(value['retries'], 0)
        self.assertEqual(list(self.root.iterdir()), [self.root/'launch.json'])

    def test_record_success_does_not_retain_failure_reason(self):
        repair.record(self.root, 'package_sha', 'EXCEPTION_STOP', 1, 77)
        (self.root/'science').mkdir()
        (self.root/'science/status.json').write_text('{"status":"COMPLETE"}')
        repair.record(self.root, 'complete', 'COMPLETE', 0, 0)
        value = json.loads((self.root/'launch.json').read_text())
        self.assertEqual(value['status'], 'COMPLETE')
        self.assertIsNone(value['reason'])

    def test_success_without_valid_science_complete_is_exception_and_nonzero(self):
        for content in (None, '{bad json', '{"status":"RUNNING"}'):
            with self.subTest(content=content):
                if content is not None:
                    (self.root/'science').mkdir(exist_ok=True)
                    (self.root/'science/status.json').write_text(content)
                process = subprocess.run([sys.executable, '-B', str(HERE/'verify_original.py'), 'record',
                    '--output', str(self.root), '--stage', 'complete', '--status', 'COMPLETE',
                    '--exit-code', '0', '--line', '0'], capture_output=True, text=True)
                self.assertEqual(process.returncode, 70)
                value = json.loads((self.root/'launch.json').read_text())
                self.assertEqual(value['status'], 'EXCEPTION_STOP')
                self.assertEqual(value['reason'], 'SCIENCE_COMPLETE_RECEIPT_REQUIRED')
                self.assertEqual(value['returncode'], 70)

    def bash(self):
        path = Path('C:/Program Files/Git/bin/bash.exe')
        result = str(path) if path.is_file() else shutil.which('bash')
        if not result:
            self.skipTest('GNU Bash unavailable')
        return result

    def test_slurm_bash_syntax_lf_and_external_output_contract(self):
        launcher = HERE/'run_repair.slurm'
        raw = launcher.read_bytes()
        self.assertNotIn(b'\r', raw)
        subprocess.run([self.bash(), '-n', str(launcher)], check=True, capture_output=True, text=True)
        text = raw.decode()
        self.assertIn('paper04_attempt="$paper04_overlay/runtime/job_$SLURM_JOB_ID"', text)
        self.assertIn('mkdir "$paper04_attempt"', text)
        self.assertNotIn('mkdir -p "$paper04_attempt"', text)
        self.assertNotIn('sbatch ', text)
        self.assertIn('--no-requeue', text)
        self.assertIn('--output "$paper04_attempt/science"', text)

    def test_frozen_chain_rejects_internal_and_accepts_external_layout_without_science(self):
        configured = os.environ.get('PAPER04_FROZEN_PACKAGE')
        if configured:
            frozen = Path(configured)
        else:
            frozen = HERE.parent/'dense_reference_matrix_v1_20261027'
            if (frozen/'distribution/r2/package/src/chain.py').is_file():
                frozen = frozen/'distribution/r2/package'
        chain = frozen/'src/chain.py'
        self.assertTrue(chain.is_file(), 'Frozen original chain required for launch contract integration')
        package = self.root/'empty_package'
        package.mkdir()
        def invoke(output):
            return subprocess.run([sys.executable, '-B', str(chain), '--package', str(package),
                '--assets-root', str(self.root/'no_assets'), '--checkpoint', str(self.root/'no_checkpoint'),
                '--approval-file', str(self.root/'no_approval'), '--output', str(output),
                '--stages', 'runtime', 'encode', 'source_cal'], capture_output=True, text=True)
        internal = package/'runtime/job_SYNTHETIC/science'
        failed = invoke(internal)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn('FRESH_EXTERNAL_OUTPUT_REQUIRED', failed.stderr)
        self.assertFalse(internal.exists())
        # An intentionally empty package stops immediately at the byte manifest
        # preflight. It cannot read a model, load data, or launch a science stage.
        external = self.root/'repair_runtime/job_SYNTHETIC/science'
        result = invoke(external)
        self.assertEqual(result.returncode, 70, result.stderr)
        self.assertNotIn('FRESH_EXTERNAL_OUTPUT_REQUIRED', result.stderr)
        value = json.loads((external/'status.json').read_text())
        self.assertEqual(value['status'], 'EXCEPTION_STOP')
        self.assertEqual(value['stage'], 'preflight')
        self.assertEqual(value['error_type'], 'FileNotFoundError')
        self.assertTrue(all(stage['state'] == 'PENDING' for stage in value['stages']))
        self.assertFalse((external/'runtime').exists())

    def test_gnu_sha256sum_reproduces_crlf_failure_and_repair_preserves_raw_bytes(self):
        (self.root/'payload.txt').write_bytes(b'actual GNU integration payload\n')
        checksum = digest((self.root/'payload.txt').read_bytes())
        lf = manifest_bytes([('payload.txt', checksum)])
        crlf = manifest_bytes([('payload.txt', checksum)], b'\r\n')
        path = self.root/'PACKAGE_SHA256SUMS'
        def gnu_check():
            return subprocess.run([self.bash(), '-c', 'cd -- "$1" && sha256sum --check PACKAGE_SHA256SUMS',
                'launch-repair-test', str(self.root)], capture_output=True)
        path.write_bytes(lf)
        self.assertEqual(gnu_check().returncode, 0)
        path.write_bytes(crlf)
        failed = gnu_check()
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn(b'could not be read', failed.stderr)
        self.assertEqual(repair.verify(self.root, digest(crlf), 1)['status'], 'PASS')
        self.assertEqual(path.read_bytes(), crlf)
        (self.root/'payload.txt').write_bytes(b'tampered')
        self.assertNotEqual(gnu_check().returncode, 0)
        with self.assertRaisesRegex(ValueError, 'SEALED_MEMBER_SHA256'):
            repair.verify(self.root, digest(crlf), 1)


if __name__ == '__main__':
    unittest.main()
