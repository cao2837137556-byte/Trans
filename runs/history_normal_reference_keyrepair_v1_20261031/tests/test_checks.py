"""Synthetic acceptance checks; no real PCAP contents or model loading."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from hnr.common import sha
from hnr import checks


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / 'not_a_packet_file.bin'
        self.raw.write_bytes(b'not PCAP content; acceptance must never decode me')
        dtype = np.dtype([(name, '<' + kind + str(size))
                          for name, (kind, size) in checks.INDEX_FIELDS.items()])
        index = np.zeros(5, dtype=dtype)
        index['timestamp_us'] = np.arange(5, dtype=np.int64) * 86400000000 + 5
        index['original_packet_ordinal'] = np.arange(1, 6)
        index['block_offset'] = np.arange(5)
        index['captured_bytes'] = index['wire_bytes'] = 1
        self.index = self.root / 'index.npy'
        self.order = self.root / 'order.npy'
        np.save(self.index, index)
        np.save(self.order, np.arange(5, dtype=np.uint32))
        self.target = dict(owner='00:00:00:00:00:01', partition='EXTERNAL_ARCHIVAL_EVALUATION',
                           device='generated', reference_end_us=3*86400000000+5,
                           bank_end_frame=4, first_dev_time_us=4*86400000000+5, packets=5)
        def pin(p):
            return dict(path=str(p), sha256=sha(p), bytes=p.stat().st_size)
        device = dict(self.target, capture_id='synthetic-whole-member',
                      known_macs=[self.target['owner']], normality_evidence='generated test',
                      raw=pin(self.raw), packet_index=pin(self.index), chronological_order=pin(self.order))
        self.runtime = self.root / 'runtime'
        (self.runtime / 'vendor/netFound').mkdir(parents=True)
        (self.runtime / 'vendor/netFound-base').mkdir(parents=True)
        (self.runtime / 'vendor/netFound/model.py').write_text('not imported', encoding='utf-8')
        (self.runtime / 'vendor/netFound-base/model.safetensors').write_bytes(b'not a model')
        listed = [p for p in sorted(self.runtime.rglob('*')) if p.is_file()]
        (self.runtime / 'SHA256SUMS').write_text(''.join(
            sha(p) + '  ' + p.relative_to(self.runtime).as_posix() + '\n' for p in listed), encoding='utf-8')
        normalizer = self.root / 'normalizer.npz'
        normalizer.write_bytes(b'not loaded')
        assets = self.root / 'assets.json'
        assets.write_text(json.dumps(dict(schema='history-normal-reference-assets-v1',
                                          pools={'generated': {'query': pin(self.raw)}})), encoding='utf-8')
        self.config = dict(root=str(self.root), devices=[device], tshark=str(self.raw),
                           assets_manifest=str(assets), encoder=dict(runtime_root=str(self.runtime),
                           runtime_manifest_sha256=sha(self.runtime / 'SHA256SUMS'),
                           normalizer=str(normalizer), normalizer_sha256=sha(normalizer)))
        self.patches = [patch.object(checks, 'TARGETS', {'generated': self.target}),
                        patch.object(checks, 'NORMALIZER_SHA', sha(normalizer)),
                        patch.object(checks, 'verify_package', return_value={'status': 'SYNTHETIC_SEAL'})]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_ready_without_decoding_or_loading_invalid_payloads(self):
        original = {str(p): sha(p) for p in self.root.rglob('*') if p.is_file()}
        result = checks.preflight(self.config)
        self.assertEqual(result['status'], 'READY')
        self.assertFalse(result['raw_hashes_verified'])
        self.assertFalse(result['assets']['payloads_loaded'])
        self.assertFalse(result['role_files_created'])
        self.assertEqual(result['packet_decodes'], 0)
        self.assertEqual(result['devices'][0]['role_boundary_validation']['bank_end_frame'], 4)
        after = {str(p): sha(p) for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(original, after)

    def test_optional_raw_sha_rejects_changed_bytes(self):
        self.raw.write_bytes(self.raw.read_bytes().replace(b'PCAP', b'FAIL'))
        # Same size, default check reports skip rather than claiming hash pass.
        self.assertEqual(checks.preflight(self.config)['status'], 'READY')
        with self.assertRaisesRegex(ValueError, 'INPUT_SHA256:generated:raw'):
            checks.preflight(self.config, verify_raw_hash=True)

    def test_missing_runtime_and_decoder_are_precise_pending(self):
        config = copy.deepcopy(self.config)
        config['tshark'] = str(self.root / 'missing_tshark')
        config['encoder']['runtime_root'] = str(self.root / 'missing_runtime')
        result = checks.preflight(config)
        self.assertEqual(result['status'], 'IMPLEMENTED_RUNTIME_ASSETS_PENDING')
        codes = {x['code'] for x in result['blockers']}
        self.assertEqual(codes, {'TSHARK_EXECUTABLE_MISSING', 'ENCODER_RUNTIME_MISSING'})

    def test_index_hash_and_chronology_are_independently_guarded(self):
        np.save(self.order, np.array([1, 0, 2, 3, 4], dtype=np.uint32))
        with self.assertRaisesRegex(ValueError, 'INPUT_SHA256:generated:chronological_order'):
            checks.preflight(self.config)
        self.config['devices'][0]['chronological_order']['sha256'] = sha(self.order)
        with self.assertRaisesRegex(ValueError, 'NONCHRONOLOGICAL_INDEX'):
            checks.preflight(self.config)

    def test_runtime_manifest_cannot_escape(self):
        manifest = self.runtime / 'SHA256SUMS'
        manifest.write_text('a'*64 + '  ../outside.bin\n', encoding='utf-8')
        self.config['encoder']['runtime_manifest_sha256'] = sha(manifest)
        with self.assertRaisesRegex(ValueError, 'RUNTIME_MANIFEST_ESCAPE'):
            checks.preflight(self.config)

    def test_separate_json_runtime_manifest_and_unlisted_vendor(self):
        (self.runtime / 'SHA256SUMS').unlink()
        files = {p.relative_to(self.runtime).as_posix(): sha(p)
                 for p in self.runtime.rglob('*') if p.is_file()}
        manifest = self.root / 'runtime_files.json'
        manifest.write_text(json.dumps({'files': files}), encoding='utf-8')
        self.config['encoder']['runtime_files_manifest'] = dict(path=str(manifest), sha256=sha(manifest))
        result = checks.preflight(self.config)
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(result['encoder']['manifest_format'], 'JSON_FILES')
        (self.runtime / 'vendor/netFound/unlisted.py').write_text('must be sealed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'RUNTIME_VENDOR_TREE_NOT_PINNED'):
            checks.preflight(self.config)

    def test_json_runtime_manifest_path_escape(self):
        manifest = self.root / 'runtime_files.json'
        manifest.write_text(json.dumps({'files': {'../outside': 'a'*64}}), encoding='utf-8')
        self.config['encoder']['runtime_files_manifest'] = dict(path=str(manifest), sha256=sha(manifest))
        with self.assertRaisesRegex(ValueError, 'RUNTIME_MANIFEST_ESCAPE'):
            checks.preflight(self.config)

    def test_frozen_device_identity_and_cap_boundary(self):
        config = copy.deepcopy(self.config)
        config['devices'][0]['device'] = 'display name instead of key'
        with self.assertRaisesRegex(ValueError, 'FROZEN_DEVICE_BINDING'):
            checks.preflight(config)
        config = copy.deepcopy(self.config)
        config['devices'][0]['bank_end_frame'] += 1
        with self.assertRaisesRegex(ValueError, 'FROZEN_DEVICE_BINDING'):
            checks.preflight(config)


class PackageSealTests(unittest.TestCase):
    def test_design_and_code_seal_tampering_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package = root / 'package'
            package.mkdir()
            document = root / 'plan.md'
            document.write_text('fixed design', encoding='utf-8')
            manifest = package / 'CODE_MANIFEST.json'
            manifest.write_text(json.dumps({'code_sha256': {'module.py': 'a'*64}}), encoding='utf-8')
            with patch.object(checks, 'PACKAGE', package), \
                 patch.object(checks, 'PLAN_DOCUMENTS', {'plan.md': sha(document)}), \
                 patch.object(checks, 'code_identity', return_value={'module.py': 'a'*64}):
                self.assertEqual(checks.verify_package(root)['status'], 'SEALED')
                with patch.object(checks, 'code_identity', return_value={'module.py': 'b'*64}):
                    with self.assertRaisesRegex(ValueError, 'IMPLEMENTATION_CODE_CHANGED'):
                        checks.verify_package(root)
                document.write_text('changed design', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'FROZEN_DESIGN_CHANGED'):
                    checks.verify_package(root)


if __name__ == '__main__':
    unittest.main()
