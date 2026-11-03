"""Generated tiny evidence only; exercise the real stdlib phase exporter."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
BUNDLE = Path(os.environ.get('MODERN_HEAD_TEST_BUNDLE', str(HERE/'bundle')))


class PhaseExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'fixture'; self.root.mkdir()
        (self.root/'repo/ood').mkdir(parents=True)
        for name in ('modern_head_delivery_io_v1.py','onboarding_delivery_io_v1.py'):
            shutil.copyfile(BUNDLE/'repo/ood'/name,self.root/'repo/ood'/name)
        (self.root/'runtime_contract.json').write_text('{"export_included_limit_gib": 0.01}\n')
        heads=self.root/'runs/modern_heads/heads'; heads.mkdir(parents=True)
        (heads/'endpoint.json').write_text('{"generated_fixture": true}\n')
        (self.root/'dependency_install_receipt.json').write_text('{}\n')
        (self.root/'extra_deps').mkdir(); (self.root/'extra_deps/recoverable').write_bytes(b'dependency')

    def export(self,mode):
        env=dict(os.environ,MODERN_HEAD_EXECUTION_MODE=mode,PYTHONDONTWRITEBYTECODE='1')
        return subprocess.run([sys.executable,'-B',str(self.root/'repo/ood/modern_head_delivery_io_v1.py'),
                               'export','--root',str(self.root)],env=env,text=True,capture_output=True,timeout=20)

    def test_full_mode_retains_original_name_and_no_overwrite(self):
        result=self.export('full'); self.assertEqual(result.returncode,0,result.stderr)
        archive=self.root/'modern_head_pullback.tar.gz'
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(Path(str(archive)+'.sha256').read_text().split()[0],digest)
        again=self.export('full'); self.assertNotEqual(again.returncode,0)
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),digest)

    def test_split_archives_keep_all_evidence_without_nesting(self):
        first=self.export('heads'); self.assertEqual(first.returncode,0,first.stderr)
        archive=self.root/'modern_heads_pullback.tar.gz'; first_bytes=archive.read_bytes()
        module=self.root/'runs/modern_heads/onboarding/TabM'; module.mkdir(parents=True)
        (module/'result.json').write_text('{"optimizer_updates": 0}\n')
        second=self.export('modules'); self.assertEqual(second.returncode,0,second.stderr)
        self.assertEqual(archive.read_bytes(),first_bytes)
        manifest=json.loads((self.root/'modern_modules_export_manifest.json').read_text())
        self.assertIn('modern_heads_pullback.tar.gz',manifest['omitted'])
        self.assertIn('modern_heads_pullback.tar.gz.sha256',manifest['included'])
        self.assertIn('modern_heads_export_manifest.json',manifest['included'])
        self.assertIn('runs/modern_heads/heads/endpoint.json',manifest['included'])
        self.assertIn('runs/modern_heads/onboarding/TabM/result.json',manifest['included'])
        self.assertIn('extra_deps/recoverable',manifest['omitted'])
        with tarfile.open(self.root/'modern_modules_pullback.tar.gz','r:gz') as tar:
            self.assertNotIn('modern_heads_pullback.tar.gz',tar.getnames())
            self.assertIn('runs/modern_heads/heads/endpoint.json',tar.getnames())

    def test_invalid_mode_has_no_export_side_effect(self):
        result=self.export('unexpected'); self.assertNotEqual(result.returncode,0)
        self.assertIn('INVALID_MODERN_HEAD_EXECUTION_MODE',result.stderr)
        self.assertEqual(list(self.root.glob('*pullback*')),[])


if __name__ == '__main__': unittest.main()
