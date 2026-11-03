"""Exercise durable phase records and fail-closed preflight completion."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from preflight_worker import StagedPreflight, read


class PreflightWorkerChecks(unittest.TestCase):
    def test_start_is_persisted_before_work_and_finish_keeps_timing(self):
        clock = [10.]
        log = io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            runner = StagedPreflight(td, stream=log, clock=lambda: clock[0])
            with runner.step('LARGE_CHECK'):
                saved = read(Path(td)/'PREFLIGHT_STATUS.json')
                self.assertEqual(saved['current_stage'], 'LARGE_CHECK')
                self.assertEqual(saved['stages'][-1]['status'], 'START')
                self.assertIn('"event": "START"', log.getvalue())
                clock[0] += 4.25
            result = runner.finish()
            self.assertEqual(result['status'], 'PASS')
            self.assertEqual(result['stages'][-1]['elapsed_seconds'], 4.25)
            self.assertEqual(read(Path(td)/'PREFLIGHT_RESULT.json'), result)
            self.assertEqual([json.loads(line)['event'] for line in log.getvalue().splitlines()],
                             ['START', 'DONE', 'RESULT'])

    def test_failed_stage_retains_trace_and_cannot_become_pass(self):
        log = io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            runner = StagedPreflight(td, stream=log)
            try:
                with runner.step('ENV_IMPORT'):
                    raise RuntimeError('test import failure')
            except RuntimeError as error:
                failed = read(Path(td)/'PREFLIGHT_STATUS.json')
                self.assertEqual(failed['stages'][-1]['status'], 'FAIL')
                self.assertIn('test import failure', failed['stages'][-1]['traceback'])
                with self.assertRaisesRegex(ValueError, 'UNFINISHED_STAGE'):
                    runner.finish()
                result = runner.finish(error)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(read(Path(td)/'PREFLIGHT_RESULT.json')['status'], 'FAIL')
            self.assertIn('test import failure', log.getvalue())

    def test_existing_status_or_result_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            runner = StagedPreflight(td, stream=io.StringIO())
            with self.assertRaisesRegex(ValueError, 'STATUS_ALREADY_EXISTS'):
                StagedPreflight(td, stream=io.StringIO())
            with runner.step('CHECK'):
                pass
            runner.finish()
            before = (Path(td)/'PREFLIGHT_RESULT.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'RESULT_ALREADY_EXISTS'):
                StagedPreflight(td, stream=io.StringIO())
            self.assertEqual((Path(td)/'PREFLIGHT_RESULT.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
