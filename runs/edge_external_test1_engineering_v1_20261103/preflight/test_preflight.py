"""Failure and frozen arithmetic gates, separate from real-slice evidence."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np

import engine
import run_preflight


class PreflightContractTests(unittest.TestCase):
    def test_frozen_arithmetic_exact_against_independent_audit(self):
        frozen = engine.read(engine.ROOT / 'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json')
        audit = engine.load_module('_edge_arithmetic_contract_test', engine.ROOT /
            'runs/c5_kernel_independent_replay_codex_20261102/ab/replay.py')
        raw = np.asarray([[-30., 0., 10.], [1., 2., 3.], [100., -100., 0.], [0., 0., 0.]])
        q = np.zeros((4, 14), dtype=np.float32)
        q[1, [0, 2]] = 1
        q[2, [0, 2, 5]] = 1
        support = np.asarray([0., 1., .123, 1e-15])
        guard = (q[:, 0] == 1) & (q[:, 2] == 1) & (q[:, 5] == 0)
        for p in (1, 3):
            actual, predictions = engine.c5(raw, support, q, frozen, p)
            expected, expected_pred, _ = audit.calculate(raw, support, guard,
                np.asarray(frozen['calibration']['scales']['scales']),
                frozen['calibration']['cuts'], p)
            self.assertTrue(np.array_equal(actual, expected))
            self.assertTrue(np.array_equal(predictions, expected_pred))
            self.assertTrue(np.array_equal(actual[guard], raw[guard]))
            self.assertTrue(np.array_equal(actual[support == 0], raw[support == 0]))

    def test_no_unfrozen_p_or_invalid_support(self):
        frozen = engine.read(engine.ROOT / 'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json')
        with self.assertRaisesRegex(ValueError, 'ENGINEERING_P'):
            engine.c5(np.zeros((1, 3)), np.ones(1), np.zeros((1, 14)), frozen, p=2)
        with self.assertRaisesRegex(ValueError, 'SUPPORT_RANGE'):
            engine.c5(np.zeros((1, 3)), np.asarray([float('nan')]), np.zeros((1, 14)), frozen)

    def test_stage_failure_retains_stage_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            progress = run_preflight.Progress(directory)
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                with progress.stage('REAL_ENCODER'):
                    raise RuntimeError('injected')
            self.assertEqual(progress.stages[-1]['status'], 'FAIL')
            self.assertEqual(progress.stages[-1]['name'], 'REAL_ENCODER')
            self.assertIn('injected', progress.stages[-1]['error'])

    def test_wall_budget_blocks_before_work(self):
        with tempfile.TemporaryDirectory() as directory:
            progress = run_preflight.Progress(directory, seconds=-1)
            with self.assertRaisesRegex(ValueError, 'PREFLIGHT_WALL_LIMIT'):
                progress.guard()


if __name__ == '__main__':
    unittest.main()
