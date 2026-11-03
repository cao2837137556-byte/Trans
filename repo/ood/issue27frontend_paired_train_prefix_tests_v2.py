"""Compatibility checks against the pinned historical F4 function, generated only."""
import ast
import json
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path
import numpy as np
import issue27frontend_paired_train_support_v2 as s
import issue27frontend_paired_train_runner_v2 as runner
from issue27frontend_paired_train_prefix_fix_v2 import prefix_digest


class PrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=s.ROOT/'repo/ood/issue27frontend_f4_fieldwise_input_v1.py'
        s.require(s.sha_file(path)=='9c729a3165d19042549723f029235734595131d5e7ba344a3f605cca89677200','F4_SOURCE_PIN')
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='prefix_bytes')
        module=ast.Module(body=[node],type_ignores=[])
        ns={'np':np,'struct':struct,'WIDTH':131,'F4Failure':ValueError}
        exec(compile(module,str(path),'exec'),ns)
        cls.reference=staticmethod(ns['prefix_bytes'])

    def test_exact_historical_bytes_all_prefix_lengths(self):
        x=np.arange(256*131,dtype=np.float32).reshape(256,131)/7
        raw=x.astype('<f4').tobytes()
        for event in range(256):
            self.assertEqual(prefix_digest(raw,event),s.digest(self.reference(x,event)))

    def test_header_known_layout(self):
        x=np.zeros((2,131),dtype=np.float32)
        envelope=self.reference(x,1)
        self.assertEqual(envelope[:12],b'F4_INPUT_V1\0')
        self.assertEqual(envelope[12:20],b'\x02\x00\x00\x00\x83\x00\x00\x00')
        self.assertEqual(prefix_digest(x.tobytes(),1),s.digest(envelope))

    def test_previous_bare_byte_hash_is_rejected_by_reference(self):
        x=np.zeros((1,131),dtype=np.float32)
        self.assertNotEqual(s.digest(x.tobytes()),s.digest(self.reference(x,0)))

    def test_unused_suffix_does_not_affect_prefix(self):
        x=np.zeros((4,131),dtype=np.float32);before=prefix_digest(x.tobytes(),1)
        x[2:]=19
        self.assertEqual(before,prefix_digest(x.tobytes(),1))

    def test_prefix_mutation_changes_digest(self):
        x=np.zeros((2,131),dtype=np.float32);before=prefix_digest(x.tobytes(),1)
        x[0,0]=1
        self.assertNotEqual(before,prefix_digest(x.tobytes(),1))

    def test_invalid_lengths_and_indices(self):
        for raw,event in ((b'',0),(bytes(525),0),(bytes(257*524),0),(bytes(524),-1),(bytes(524),1),(bytes(524),True)):
            with self.subTest(n=len(raw),event=event),self.assertRaises(s.Stop):prefix_digest(raw,event)

    def test_noncontiguous_historical_matrix(self):
        x=np.arange(4*262,dtype=np.float32).reshape(4,262)[:,::2]
        self.assertFalse(x.flags.c_contiguous)
        self.assertEqual(prefix_digest(np.ascontiguousarray(x).tobytes(),2),s.digest(self.reference(x,2)))

    def test_preparation_uses_independent_historical_oracle(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);x=np.arange(3*131,dtype=np.float32).reshape(3,131)/10
            source=folder/'generated.f32le';source.write_bytes(x.tobytes())
            c={'key':'generated','source':'fixture','source_offset':0,'offset':0,'length':3,
               'targets':[{'event':i,'feature_prefix_sha256':s.digest(self.reference(x,i))} for i in range(3)]}
            plan={'contexts':[c],'feature_bytes':3*524}
            spec={'fixture':{'path':str(source),'bytes':3*524,'sha256':s.sha_file(source)}}
            out=folder/'out';out.mkdir()
            access=runner.prepare_data(plan,spec,out,runner.Budget(out,s.PREP_CAPS,time.monotonic()))
            self.assertEqual(access['prefixes_verified'],3)
            self.assertEqual((out/'features.f32le').read_bytes(),x.tobytes())


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PrefixTests))
    report=dict(tests_run=result.testsRun,tests_passed=result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
                errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),
                real_feature_bytes_decoded=0,real_optimizer_steps=0,
                reference='pinned F4 prefix_bytes AST projection on generated arrays, not historical experiment replay')
    print('SYNTHETIC_RESULT '+json.dumps(report),flush=True)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
