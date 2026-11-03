"""I/O regressions for streaming hash selection and immutable metadata joins."""
import gzip
import hashlib
import random
import tempfile
from pathlib import Path
import unittest

import select_queries as s


class StreamingContracts(unittest.TestCase):
    def test_streaming_heap_equals_full_sort_in_both_orders(self):
        rows=[dict(uid=hashlib.sha256(str(i).encode()).hexdigest(),frame=i) for i in range(2000)]
        expected=sorted(rows,key=lambda r:(hashlib.sha256(('salt|'+r['uid']).encode()).hexdigest(),r['uid']))[:37]
        rng=random.Random(38823)
        for _ in range(3):
            rng.shuffle(rows);heap=[]
            for row in rows:s.keep_smallest(heap,row,37,'salt')
            self.assertEqual({x[2]['uid'] for x in heap},{x['uid'] for x in expected})

    def test_gzip_output_is_identical_across_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=Path(temp)/'a.gz',Path(temp)/'longer_name.gz'
            for path in (a,b):
                with s.gzip_text(path) as f:f.write('physical UID\n123\n')
            self.assertEqual(a.read_bytes(),b.read_bytes())
            self.assertEqual(gzip.decompress(a.read_bytes()),b'physical UID\n123\n')
            with self.assertRaises(FileExistsError):
                with s.gzip_text(a):pass

    def test_selected_spool_schema_preserves_integer_clocks(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'meta.gz'
            with s.gzip_text(path) as f:
                f.write('\t'.join(s.FIELDS)+'\n')
                f.write('u\t17\t1637491450081753000\t6\tcap\tcomp\t24\tPSH_ACK\tIN\n')
            [row]=list(s.spool_rows(path))
            self.assertEqual(row['timestamp_ns'],1637491450081753000)
            self.assertEqual(row['frame'],17)
            self.assertEqual(row['tcp_flags'],24)


if __name__=='__main__':unittest.main()
