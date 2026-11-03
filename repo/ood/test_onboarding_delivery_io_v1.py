"""Synthetic-only installation/export safety and result-retention checks."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

import onboarding_delivery_io_v1 as delivery


class DeliveryFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='onboarding-delivery-test-')
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def archive(self, files=None, extra=(), seal_override=None):
        files = dict(files or {'scripts/run.sh': b'#!/bin/bash\nexit 0\n', 'protocol.json': b'{"frozen":true}\n'})
        seal = ''.join(hashlib.sha256(body).hexdigest() + '  ' + name + '\n'
                       for name, body in sorted(files.items())).encode()
        archive = self.root / 'delivery.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            for name, body in list(files.items()) + [('SHA256SUMS', seal if seal_override is None else seal_override)]:
                member = tarfile.TarInfo(name)
                member.size = len(body)
                member.mode = 0o755 if name.endswith('.sh') else 0o644
                tar.addfile(member, io.BytesIO(body))
            for member, body in extra:
                tar.addfile(member, io.BytesIO(body) if body is not None else None)
        Path(str(archive) + '.sha256').write_text(delivery.sha(archive) + '  ' + archive.name + '\n', encoding='ascii')
        return archive

    def run_root(self, limit=1):
        root = self.root / 'run'
        root.mkdir()
        self.put(root, 'runtime_contract.json', json.dumps({'export_included_limit_gib': limit}).encode())
        return root

    def put(self, root, name, body=b'synthetic\n'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path


class InstallationTests(DeliveryFixture):
    def test_verified_install_preserves_seal_and_external_receipt(self):
        archive = self.archive()
        destination = self.root / 'installed'
        receipt = delivery.install(archive, destination)
        self.assertFalse(receipt['scoring_started'])
        self.assertFalse(receipt['remote_access'])
        self.assertEqual(receipt['retries'], 0)
        self.assertEqual(receipt['installed_files'], 3)
        self.assertTrue(destination.with_name('installed.install_receipt.json').is_file())
        self.assertEqual({p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()},
                         {'scripts/run.sh', 'protocol.json', 'SHA256SUMS'})
        self.assertEqual(receipt['internal_seal_sha256'], delivery.sha(destination / 'SHA256SUMS'))

    def test_archive_tamper_rejected_before_mkdir(self):
        archive = self.archive()
        with archive.open('ab') as stream:
            stream.write(b'tamper')
        with self.assertRaisesRegex(RuntimeError, 'ARCHIVE_SHA'):
            delivery.install(archive, self.root / 'installed')
        self.assertFalse((self.root / 'installed').exists())

    def test_inner_tamper_rejected_before_mkdir(self):
        archive = self.archive(seal_override=(('0' * 64) + '  protocol.json\n' + ('0' * 64) + '  scripts/run.sh\n').encode())
        with self.assertRaisesRegex(RuntimeError, 'INNER_SHA'):
            delivery.install(archive, self.root / 'installed')
        self.assertFalse((self.root / 'installed').exists())

    def test_unsealed_member_rejected(self):
        item = tarfile.TarInfo('unsealed.json')
        item.size = 1
        archive = self.archive(extra=[(item, b'x')])
        with self.assertRaisesRegex(RuntimeError, 'INNER_FILE_SET'):
            delivery.install(archive, self.root / 'installed')

    def test_paths_cannot_escape_or_alias(self):
        for index, name in enumerate(('../escape', '/absolute', 'C:/escape', 'folder\\escape',
                                      './alias', 'a//alias', 'a/../alias', 'CON.txt', 'trailing.')):
            with self.subTest(name=name):
                archive = self.archive(files={name: b'x'})
                destination = self.root / ('installed' + str(index))
                with self.assertRaisesRegex(RuntimeError, 'UNSAFE_MEMBER'):
                    delivery.install(archive, destination)
                self.assertFalse(destination.exists())

    def test_links_and_duplicate_names_rejected(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.REGTYPE):
            with self.subTest(kind=kind):
                member = tarfile.TarInfo('protocol.json')
                member.type = kind
                member.linkname = '../outside'
                member.size = 0
                archive = self.archive(extra=[(member, b'' if kind == tarfile.REGTYPE else None)])
                with self.assertRaisesRegex(RuntimeError, 'UNSAFE_OR_DUPLICATE_MEMBER'):
                    delivery.install(archive, self.root / 'installed')

    def test_portable_case_collisions_rejected(self):
        archive = self.archive(files={'Config.json': b'a', 'config.json': b'b'})
        with self.assertRaisesRegex(RuntimeError, 'UNSAFE_OR_DUPLICATE_MEMBER'):
            delivery.install(archive, self.root / 'installed')

    def test_file_directory_collision_rejected(self):
        archive = self.archive(files={'A': b'a', 'a/file.json': b'b'})
        with self.assertRaisesRegex(RuntimeError, 'FILE_DIRECTORY_COLLISION'):
            delivery.install(archive, self.root / 'installed')

    def test_existing_destination_and_receipt_never_overwritten(self):
        archive = self.archive()
        destination = self.root / 'installed'
        destination.mkdir()
        (destination / 'precious').write_bytes(b'keep')
        with self.assertRaisesRegex(RuntimeError, 'NO_OVERWRITE'):
            delivery.install(archive, destination)
        self.assertEqual((destination / 'precious').read_bytes(), b'keep')
        other = self.root / 'other'
        receipt = self.root / 'other.install_receipt.json'
        receipt.write_bytes(b'keep')
        with self.assertRaisesRegex(RuntimeError, 'NO_OVERWRITE'):
            delivery.install(archive, other)
        self.assertEqual(receipt.read_bytes(), b'keep')
        self.assertFalse(other.exists())

    def test_cli_installs_using_standard_library_only(self):
        archive = self.archive()
        result = subprocess.run([sys.executable, '-I', str(Path(delivery.__file__).resolve()), 'install',
                                 '--archive', str(archive), '--destination', str(self.root / 'installed')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('INSTALLED_AND_VERIFIED_NO_EXPERIMENT_STARTED', result.stdout)


class ExportTests(DeliveryFixture):
    def test_every_reference_feature_and_result_retained(self):
        root = self.run_root()
        required = ['logs/run.log', 'protocols/reference.json', 'resource_evidence/budget.json',
                    'runs/onboarding/raw/candidates.jsonl.gz', 'runs/onboarding/raw/census_receipt.json',
                    'runs/onboarding/raw/selected_snapshots.jsonl.gz', 'runs/onboarding/raw/q14.npy',
                    'runs/onboarding/encoded/features.npy', 'runs/onboarding/encoded/receipt.json',
                    'runs/onboarding/evaluation/scores.npy', 'runs/onboarding/evaluation/decisions.npy',
                    'runs/onboarding/evaluation/report.json', 'runs/onboarding/selected/snapshots.sqlite',
                    'runs/onboarding/encoder_runtime/SHA256SUMS', 'runs/onboarding/encoder_runtime/identity.json']
        for name in required:
            self.put(root, name, ('content ' + name).encode())
        manifest = delivery.export(root)
        with tarfile.open(root / delivery.EXPORT_NAME) as tar:
            self.assertEqual(set(tar.getnames()), set(required) | {'runtime_contract.json', delivery.MANIFEST_NAME})
            for name in required:
                content = tar.extractfile(name).read()
                self.assertEqual(hashlib.sha256(content).hexdigest(), manifest['included'][name]['sha256'])
                self.assertEqual(len(content), manifest['included'][name]['bytes'])
            self.assertEqual(json.loads(tar.extractfile(delivery.MANIFEST_NAME).read()), manifest)
        self.assertEqual((root / delivery.MANIFEST_NAME).stat().st_size, manifest['manifest_bytes'])
        self.assertEqual(Path(str(root / delivery.EXPORT_NAME) + '.sha256').read_text().split()[0],
                         delivery.sha(root / delivery.EXPORT_NAME))

    def test_all_omissions_explicit_with_hashes_and_scratch_is_narrow(self):
        root = self.run_root()
        omitted = ['repo/ood/code.py', 'vendor/model.bin', 'synthetic_tmp/generated.npy',
                   'runs/onboarding/encoder_runtime/vendor/model.pt',
                   'runs/onboarding/raw/reference-working-abcd/contexts.sqlite',
                   'runs/onboarding/raw/reference-working-abcd/snapshots_3600.sqlite-wal']
        kept = ['runs/onboarding/raw/contexts.sqlite',
                'runs/onboarding/raw/reference-working-abcd/selected_snapshots.jsonl.gz',
                'runs/onboarding/raw/reference-working-abcd/candidates.jsonl.gz',
                'runs/onboarding/raw/reference-working-abcd/census_receipt.json']
        for name in omitted + kept:
            self.put(root, name)
        manifest = delivery.export(root)
        self.assertEqual(set(manifest['omitted']), set(omitted))
        for name in omitted:
            self.assertEqual(manifest['omitted'][name]['sha256'], delivery.sha(root / name))
            self.assertGreater(len(manifest['omitted'][name]['reason']), 10)
        with tarfile.open(root / delivery.EXPORT_NAME) as tar:
            self.assertTrue(set(kept).issubset(tar.getnames()))
            self.assertFalse(set(omitted).intersection(tar.getnames()))

    def test_failed_run_is_exportable_without_complete_marker(self):
        root = self.run_root()
        self.put(root, 'runs/onboarding/FAILED.json', b'{"reason":"synthetic failure"}')
        self.put(root, 'logs/stderr.log', b'Traceback: synthetic\n')
        manifest = delivery.export(root)
        self.assertTrue(manifest['failure_outputs_supported'])
        self.assertIn('runs/onboarding/FAILED.json', manifest['included'])
        self.assertIn('logs/stderr.log', manifest['included'])
        self.assertFalse(manifest['scoring_started'])

    def test_limit_fails_before_writing_instead_of_truncating(self):
        root = self.run_root(limit=0.000001)
        source = self.put(root, 'runs/onboarding/encoded/features.npy', b'x' * 4096)
        with self.assertRaisesRegex(RuntimeError, 'SIZE_LIMIT_KEEP_ALL_RESULTS_NO_TRUNCATION'):
            delivery.export(root)
        self.assertEqual(source.stat().st_size, 4096)
        self.assertFalse((root / delivery.EXPORT_NAME).exists())
        self.assertFalse((root / delivery.MANIFEST_NAME).exists())

    def test_invalid_limits_rejected(self):
        root = self.run_root()
        for limit in (None, True, 0, -1, '1', float('nan'), float('inf')):
            with self.subTest(limit=limit):
                (root / 'runtime_contract.json').write_text(json.dumps({'export_included_limit_gib': limit}))
                with self.assertRaisesRegex(RuntimeError, 'INVALID_EXPORT_LIMIT'):
                    delivery.export(root)

    def test_second_export_cannot_overwrite_original(self):
        root = self.run_root()
        delivery.export(root)
        original = delivery.sha(root / delivery.EXPORT_NAME)
        self.put(root, 'new_result.json')
        with self.assertRaisesRegex(RuntimeError, 'EXPORT_EXISTS_NO_OVERWRITE'):
            delivery.export(root)
        self.assertEqual(delivery.sha(root / delivery.EXPORT_NAME), original)

    def test_preexisting_sidecar_cannot_be_overwritten(self):
        root = self.run_root()
        sidecar = self.put(root, delivery.EXPORT_NAME + '.sha256', b'keep')
        with self.assertRaisesRegex(RuntimeError, 'EXPORT_EXISTS_NO_OVERWRITE'):
            delivery.export(root)
        self.assertEqual(sidecar.read_bytes(), b'keep')
        self.assertFalse((root / delivery.EXPORT_NAME).exists())

    def test_link_evidence_rejected_instead_of_silently_dropped(self):
        root = self.run_root()
        linked = self.put(root, 'runs/onboarding/encoded/features.npy')
        original = Path.is_symlink
        # Works on Windows without symlink privileges; exercises the same
        # lstat traversal rejection used for actual links on the target.
        with mock.patch.object(Path, 'is_symlink', lambda path: path == linked or original(path)):
            with self.assertRaisesRegex(RuntimeError, 'EXPORT_LINK_OR_ESCAPE'):
                delivery.export(root)
        self.assertFalse((root / delivery.EXPORT_NAME).exists())

    def test_changed_content_aborts_and_removes_only_current_export(self):
        root = self.run_root()
        source = self.put(root, 'runs/onboarding/encoded/features.npy', b'before')
        original = delivery.sha

        def modify_after_inventory(path):
            result = original(path)
            if Path(path) == source:
                source.write_bytes(b'after!')  # Equal size still must fail hash.
            return result

        with mock.patch.object(delivery, 'sha', side_effect=modify_after_inventory):
            with self.assertRaisesRegex(RuntimeError, 'EXPORT_CHANGED_CONTENT'):
                delivery.export(root)
        self.assertEqual(source.read_bytes(), b'after!')
        self.assertFalse((root / delivery.EXPORT_NAME).exists())
        self.assertFalse((root / delivery.MANIFEST_NAME).exists())
        self.assertFalse(Path(str(root / delivery.EXPORT_NAME) + '.sha256').exists())

    def test_cli_exports_without_third_party_modules(self):
        root = self.run_root()
        self.put(root, 'runs/onboarding/FAILED.json')
        result = subprocess.run([sys.executable, '-I', str(Path(delivery.__file__).resolve()),
                                 'export', '--root', str(root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PULLBACK_READY', result.stdout)


if __name__ == '__main__':
    unittest.main()
