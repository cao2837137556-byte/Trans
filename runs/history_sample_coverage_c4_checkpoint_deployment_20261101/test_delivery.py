import io
import hashlib
from pathlib import Path
import tarfile
import tempfile
import unittest
from receiver import validate_archive
from client import safe_members
from build_delivery import relocate,ROOT,REMOTE

def archive(name='run.py',value=b'hello',link=False):
    b=io.BytesIO()
    with tarfile.open(fileobj=b,mode='w') as ar:
        info=tarfile.TarInfo(name)
        if link:info.type=tarfile.SYMTYPE;info.linkname='/tmp/target';ar.addfile(info)
        else:info.size=len(value);ar.addfile(info,io.BytesIO(value))
    b.seek(0);return tarfile.open(fileobj=b,mode='r:')

class DeliveryChecks(unittest.TestCase):
    def spec(self,name='run.py'):return {name:dict(bytes=5,sha256=hashlib.sha256(b'hello').hexdigest())}
    def test_real_slurm_unix_lf(self):
        from build_delivery import PACKAGE
        data=(PACKAGE/'hpc/run_encode.slurm').read_bytes();self.assertTrue(data.startswith(b'#!/bin/bash\n'));self.assertNotIn(b'\r',data)
    def test_exact_archive_accepted(self):
        with archive() as ar:self.assertEqual(len(validate_archive(ar,self.spec())),1)
    def test_path_escape_rejected(self):
        with archive('../escape') as ar,self.assertRaises(ValueError):validate_archive(ar,self.spec('../escape'))
    def test_symlink_rejected(self):
        with archive(link=True) as ar,self.assertRaises(ValueError):validate_archive(ar,self.spec())
    def test_changed_payload_rejected(self):
        with archive(value=b'other') as ar,self.assertRaises(ValueError):validate_archive(ar,self.spec())
    def test_unexpected_member_rejected(self):
        with archive('extra') as ar,self.assertRaises(ValueError):validate_archive(ar,self.spec())
    def test_result_windows_drive_rejected(self):
        with archive('C:/escape') as ar,self.assertRaises(ValueError):safe_members(ar,Path(tempfile.gettempdir())/'c4-test')
    def test_relocation_preserves_science(self):
        data=Path('D:/data');v=dict(root=str(ROOT),raw=dict(path=str(data/'test.pcap'),sha256='abc'),cap=4096)
        mapped=relocate(v,data);self.assertEqual(mapped['root'],REMOTE);self.assertEqual(mapped['raw']['sha256'],'abc');self.assertEqual(mapped['cap'],4096)

if __name__=='__main__':unittest.main(verbosity=2)
