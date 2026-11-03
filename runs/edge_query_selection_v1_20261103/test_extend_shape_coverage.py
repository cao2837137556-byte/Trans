"""Small regression for full+target coverage union without raw replay."""
import importlib.util
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('edge_extend_shape_coverage',HERE/'extend_shape_coverage.py')
s=importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class UnionCoverage(unittest.TestCase):
    def test_union_keeps_missing_full_shapes_and_prefers_target_representative(self):
        target=dict(role='HTTP',frame=101,shape=[6,73,12])
        full_same=dict(role='NORMAL',frame=8,shape=[6,73,12])
        full_only=dict(role='NORMAL',frame=18,shape=[6,49,2])
        census=dict(target_requirements=dict(representatives=[target]),
                    full_requirements=dict(representatives=[full_same,full_only]))
        reps=s.union_representatives(census)
        self.assertEqual({tuple(r['shape']) for r in reps},{(6,73,12),(6,49,2)})
        shared=next(r for r in reps if r['shape']==[6,73,12])
        self.assertEqual((shared['role'],shared['frame']),('HTTP',101))
        self.assertEqual(shared['requirement_domains'],['target','full'])
        self.assertEqual(census['target_requirements']['representatives'][0],target)


if __name__=='__main__':
    unittest.main()
