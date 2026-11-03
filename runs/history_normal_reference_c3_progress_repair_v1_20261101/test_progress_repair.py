"""Regress the actual Windows file-lock failure without using real queries."""
import ast
import contextlib
import ctypes
import io
import tempfile
import unittest
from unittest.mock import patch
import common
from common import *
from evaluate import PairBudget


class ProgressRepairTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows sharing semantics')
    def test_windows_status_read_handle_does_not_abort_progress(self):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                      ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        with tempfile.TemporaryDirectory() as folder, patch.object(common, 'HERE', Path(folder)):
            status = Path(folder) / 'STATUS.json'
            status.write_text('{"stage":"old"}', encoding='utf-8')
            handle = kernel.CreateFileW(str(status), 0x80000000, 3, None, 3, 0, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
            try:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    common.progress('RUNNING', 'test', completed=128)
                self.assertIn('display_write_warnings', json.loads(output.getvalue()))
                self.assertEqual(read(status)['stage'], 'old')
            finally:
                kernel.CloseHandle(handle)
            with contextlib.redirect_stdout(io.StringIO()):
                common.progress('RUNNING', 'test', completed=256)
            self.assertEqual(read(status)['completed'], 256)

    def test_locked_markdown_does_not_abort_or_hide_status(self):
        original = Path.write_text
        def blocked(path, *args, **kwargs):
            if path.name == 'PROGRESS.md':
                raise PermissionError('simulated display lock')
            return original(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as folder, patch.object(common, 'HERE', Path(folder)):
            with patch.object(Path, 'write_text', blocked), contextlib.redirect_stdout(io.StringIO()) as output:
                common.progress('RUNNING', 'test')
            self.assertIn('display_write_warnings', json.loads(output.getvalue()))
            self.assertEqual(read(Path(folder) / 'STATUS.json')['stage'], 'RUNNING')

    def test_scientific_artifact_errors_remain_fatal(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'RESULT.json'
            path.write_text('{"old":true}', encoding='utf-8')
            with patch.object(Path, 'replace', side_effect=PermissionError('locked result')):
                with self.assertRaises(PermissionError):
                    write(path, {'changed': True})
            self.assertEqual(read(path), {'old': True})

    def test_previous_compute_reservation_is_enforced(self):
        budget = PairBudget(LIMITS['distance_pairs'] - 10)
        budget.pairs(7)
        with self.assertRaisesRegex(ValueError, 'DISTANCE_PAIR_LIMIT'):
            budget.pairs(4)
        self.assertEqual(budget.total, 7)
        budget.pairs(3)
        self.assertEqual(budget.total + budget.previous_upper_bound, LIMITS['distance_pairs'])

    def test_selection_metric_and_adoption_functions_unchanged(self):
        parent = HERE.parent / 'history_normal_reference_c3_small_bank_v1_20261101'
        for filename, functions in {
            'common.py': ['complete_small_group', 'c3_gate', 'same_physical'],
            'evaluate.py': ['saved_c2', 'validate_dev', 'report'],
            'prepare.py': ['walk_capture'],
        }.items():
            def definitions(path):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                return {x.name: ast.dump(x) for x in tree.body if isinstance(x, ast.FunctionDef)}
            original, repaired = definitions(parent / filename), definitions(HERE / filename)
            for name in functions:
                self.assertEqual(original[name], repaired[name], filename + ':' + name)


if __name__ == '__main__':
    unittest.main()
