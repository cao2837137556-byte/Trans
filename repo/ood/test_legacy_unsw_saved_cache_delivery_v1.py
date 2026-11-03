"""Stdlib-only delivery checks; never open real experiment inputs."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

import legacy_unsw_saved_cache_delivery_v1 as d


class Delivery(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root/'package.tar.gz'
        self.dest = self.root/'installed'

    def tearDown(self):
        self.temp.cleanup()

    def package(self, extra=None):
        data=b'generated package data\n'
        seal=(hashlib.sha256(data).hexdigest()+'  data.txt\n').encode()
        with tarfile.open(self.archive,'w:gz') as tar:
            for name,value in [('data.txt',data),('SHA256SUMS',seal)]:
                info=tarfile.TarInfo(name); info.size=len(value)
                tar.addfile(info,io.BytesIO(value))
            if extra:
                tar.addfile(extra,io.BytesIO(b'x'*extra.size))
        Path(str(self.archive)+'.sha256').write_bytes((d.sha(self.archive)+'  '+self.archive.name+'\n').encode())

    def test_clean_install_and_existing_destination_refused(self):
        self.package(); d.install(self.archive,self.dest)
        self.assertEqual((self.dest/'data.txt').read_bytes(),b'generated package data\n')
        with self.assertRaisesRegex(RuntimeError,'DESTINATION_EXISTS'):
            d.install(self.archive,self.dest)

    def test_archive_mismatch_no_extraction(self):
        self.package()
        with self.archive.open('ab') as stream: stream.write(b'changed')
        with self.assertRaisesRegex(RuntimeError,'ARCHIVE_SHA'):
            d.install(self.archive,self.dest)
        self.assertFalse(self.dest.exists())

    def test_traversal_no_extraction(self):
        self.package(tarfile.TarInfo('../escape'))
        with self.assertRaisesRegex(RuntimeError,'UNSAFE_MEMBER'):
            d.install(self.archive,self.dest)
        self.assertFalse(self.dest.exists())

    def test_duplicate_no_extraction(self):
        self.package(tarfile.TarInfo('data.txt'))
        with self.assertRaisesRegex(RuntimeError,'UNSAFE_MEMBER'):
            d.install(self.archive,self.dest)

    def test_symlink_no_extraction(self):
        info=tarfile.TarInfo('link'); info.type=tarfile.SYMTYPE; info.linkname='data.txt'
        self.package(info)
        with self.assertRaisesRegex(RuntimeError,'UNSAFE_MEMBER'):
            d.install(self.archive,self.dest)

    def test_unsealed_file_refused(self):
        self.package(tarfile.TarInfo('extra.txt'))
        with self.assertRaisesRegex(RuntimeError,'INNER_FILE_SET'):
            d.install(self.archive,self.dest)

    def test_environment_failure_export_without_site_packages(self):
        root=self.root/'run'; (root/'validation').mkdir(parents=True)
        (root/'validation/preflight.log').write_bytes(b'ModuleNotFoundError: numpy\n')
        (root/'exit_code.txt').write_bytes(b'1\n')
        code='import sys; sys.path.insert(0,sys.argv[1]); from legacy_unsw_saved_cache_delivery_v1 import export_output; export_output(sys.argv[2])'
        result=subprocess.run([sys.executable,'-S','-c',code,str(Path(d.__file__).parent),str(root)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        manifest=json.loads((root/'export_manifest.json').read_text(encoding='utf-8'))
        self.assertIn('validation/preflight.log',manifest)
        with tarfile.open(root/'cache_audit_pullback.tar.gz') as tar:
            self.assertEqual(tar.extractfile('exit_code.txt').read(),b'1\n')


if __name__=='__main__':
    unittest.main(verbosity=2)
