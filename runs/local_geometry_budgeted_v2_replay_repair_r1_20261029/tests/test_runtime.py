import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from lg import runtime
from lg.common import read_json, write_json


class RuntimeTests(unittest.TestCase):
    def limits(self):
        return dict(cpu=4, rss_bytes=8*2**30, wall_seconds=60, output_bytes=10*2**20, pairs=10, forwards=5)

    def test_counts_cannot_exceed_budget_and_output_cannot_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            with runtime.StageRuntime('source', Path(temp)/'new', limits=self.limits(), monitor=False) as rt:
                rt.add_pairs(10)
                rt.add_forwards(5)
                with self.assertRaisesRegex(ValueError, 'DISTANCE_PAIR_LIMIT'):
                    rt.add_pairs(1)
                with self.assertRaisesRegex(ValueError, 'HEAD_FORWARD_LIMIT'):
                    rt.add_forwards(1)
                with self.assertRaisesRegex(ValueError, 'OUTPUT_PATH_ESCAPE'):
                    rt.write_json('../escape.json', {})
                rt.finish({'scientific_status':'SOURCE_SIGNAL_FAIL'})
            self.assertEqual(read_json(Path(temp)/'new/STAGE_RECEIPT.json')['pairs'], 10)

    def test_scientific_failure_is_completed_but_cannot_promote(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'run'
            with runtime.StageRuntime('source', output, limits=self.limits(), monitor=False) as rt:
                rt.finish({'scientific_status':'SOURCE_SIGNAL_FAIL'})
            self.assertEqual(read_json(output/'STATUS.json')['technical_status'], 'COMPLETED')
            with self.assertRaisesRegex(ValueError, 'SOURCE_GATE_NOT_PASS'):
                runtime.verify_predecessor(output/'RESULT.json')
            with self.assertRaises(FileExistsError):
                with runtime.StageRuntime('source', output, monitor=False):
                    pass

    def test_success_receipt_binds_every_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'run'
            with runtime.StageRuntime('source', output, limits=self.limits(), monitor=False) as rt:
                rt.write_json('fold/asset.json', {'a':1})
                rt.finish({'scientific_status':'SOURCE_SIGNAL_PASS'})
            result, receipt = runtime.verify_predecessor(output/'RESULT.json')
            self.assertEqual(result['scientific_status'], 'SOURCE_SIGNAL_PASS')
            write_json(output/'fold/asset.json', {'a':2})
            with self.assertRaisesRegex(ValueError, 'SOURCE_OUTPUT_CHANGED'):
                runtime.verify_predecessor(output/'RESULT.json')

    def test_resource_limits_and_technical_exception_preserve_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'run'
            with self.assertRaisesRegex(ValueError, 'bad input'):
                with runtime.StageRuntime('source', output, limits=self.limits(), monitor=False) as rt:
                    usage = dict(elapsed_seconds=1,process_tree_rss_bytes=1,output_bytes=1)
                    for field, reason in [('elapsed_seconds','WALL_LIMIT'),('process_tree_rss_bytes','RSS_LIMIT'),('output_bytes','OUTPUT_LIMIT')]:
                        bad = copy.copy(usage)
                        bad[field] = 10**15
                        with self.assertRaisesRegex(ValueError, reason):
                            rt._validate(bad)
                    raise ValueError('bad input')
            self.assertEqual(read_json(output/'STATUS.json')['technical_status'],'EXCEPTION_STOPPED')
            self.assertTrue((output/'EXCEPTION.json').exists())

    def test_cli_default_never_executes_science_and_invalid_target_stops_early(self):
        import run
        self.assertEqual(run.parser().parse_args([]).stage, 'check')
        with patch('run.verify_package'), patch('run.verify_predecessor', side_effect=ValueError('bad predecessor')), \
             patch('run.StageRuntime') as stage:
            with self.assertRaisesRegex(ValueError, 'bad predecessor'):
                run.main(['target','--source-result','missing.json'])
            stage.assert_not_called()

    def test_output_hash_time_is_inside_stage_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'run'
            rt = runtime.StageRuntime('source', output, limits=self.limits(), monitor=False)
            real_sha = runtime.sha
            def slow_hash(path):
                if Path(path) == output/'RESULT.json':
                    rt.started -= 61
                return real_sha(path)
            with self.assertRaisesRegex(ValueError, 'WALL_LIMIT'):
                with rt, patch('lg.runtime.sha', side_effect=slow_hash):
                    rt.finish({'scientific_status':'SOURCE_SIGNAL_PASS'})
            self.assertFalse((output/'STAGE_RECEIPT.json').exists())

    def test_late_failure_or_excess_receipt_cannot_promote(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'run'
            with runtime.StageRuntime('source', output, limits=self.limits(), monitor=False) as rt:
                rt.finish({'scientific_status':'SOURCE_SIGNAL_PASS'})
            status = read_json(output/'STATUS.json')
            write_json(output/'STATUS.json', dict(status, technical_status='EXCEPTION_STOPPED'))
            with self.assertRaisesRegex(ValueError, 'SOURCE_NOT_FINALIZED'):
                runtime.verify_predecessor(output/'RESULT.json')
            write_json(output/'STATUS.json', status)
            receipt = read_json(output/'STAGE_RECEIPT.json')
            write_json(output/'STAGE_RECEIPT.json', dict(receipt, pairs=2_000_000_001))
            with self.assertRaisesRegex(ValueError, 'SOURCE_BUDGET_EXCEEDED:pairs'):
                runtime.verify_predecessor(output/'RESULT.json')


if __name__ == '__main__':
    unittest.main()
