"""Generated tensors only; prove singleton shape repair never creates new UIDs."""
import hashlib
import unittest
import numpy as np
from hnr.encoding import physical_batch, concatenate


class Tensor(np.ndarray):
    def repeat(self, sizes): return np.tile(np.asarray(self),sizes).view(Tensor)


def tensor_hash(batch, j):
    return hashlib.sha256(b''.join(np.asarray(batch[k][j]).tobytes() for k in sorted(batch))).hexdigest()


class EncodingTests(unittest.TestCase):
    def test_singleton_physical_clones_have_identical_tensors(self):
        batch=dict(input_ids=np.arange(5).reshape(1,5).view(Tensor),protocol=np.asarray([6]).view(Tensor))
        prepared,n=physical_batch(batch,1,tensor_hash)
        self.assertEqual(n,16)
        self.assertEqual(prepared['input_ids'].shape,(16,5))
        self.assertTrue(all(tensor_hash(prepared,j)==tensor_hash(batch,0) for j in range(16)))
        self.assertEqual(batch['input_ids'].shape,(1,5))
        regular=dict(input_ids=np.zeros((3,4)).view(Tensor))
        self.assertIs(physical_batch(regular,3,tensor_hash)[0],regular)

    def test_concatenate_preserves_rows_and_rejects_identity_overlap(self):
        one=dict(rows=[dict(uid='a')],e3=np.zeros((1,768),np.float32),q14=np.zeros((1,14),np.float32))
        two=dict(rows=[dict(uid='b')],e3=np.ones((1,768),np.float32),q14=np.ones((1,14),np.float32))
        out=concatenate([one,two])
        self.assertEqual([r['uid'] for r in out['rows']],['a','b'])
        self.assertEqual(out['e3'].shape,(2,768))
        with self.assertRaisesRegex(ValueError,'DUPLICATE_DATASET_UID'):
            concatenate([one,one])


if __name__=='__main__': unittest.main()
