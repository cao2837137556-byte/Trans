"""Mocked orchestration: no decoder, encoder, real latch or scientific values."""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from hnr.common import PACKAGE, HEIM, TARGETS, write

spec = importlib.util.spec_from_file_location('_history_cli_test', PACKAGE / 'run.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def dataset(uid, component='new'):
    return dict(rows=[dict(uid=uid, device=HEIM['device'], protocol=6, component_id=component)],
                e3=np.ones((1, 768)), q14=np.zeros((1, 14)))


class FakeAssets:
    def dense(self, pool): return dataset('dense-' + pool, component='old')
    def a_history(self): return dataset('a-history')
    def calibration(self): return {'generated': True}
    def immutable(self): pass
    def queries(self, pool): raise AssertionError('AB query loader must stay closed')


class FakeRuntime:
    def __init__(self, output): self.output = Path(output); self.events = []
    def __enter__(self): self.output.mkdir(); return self
    def __exit__(self, typ, exc, tb): return False
    def update(self, stage, **fields): self.events.append((stage, fields))
    def finish(self, result): self.result = result


class OrchestrationTests(unittest.TestCase):
    def test_member_stop_prevents_encoder_and_all_scores(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(cli, 'PACKAGE', Path(tmp)))
            stack.enter_context(patch.object(cli, 'validate_config_bindings'))
            stack.enter_context(patch.object(cli, 'environment_check', return_value={'generated': True}))
            stack.enter_context(patch('hnr.checks.preflight', return_value={'status': 'READY', 'blockers': []}))
            stack.enter_context(patch('hnr.assets.load_assets', return_value=FakeAssets()))
            stack.enter_context(patch('hnr.history.prepare_member', return_value={'status': 'STOP_NO_NEW_COMPONENT'}))
            encoder = stack.enter_context(patch('hnr.encoding.new_encoder', side_effect=AssertionError('encoder loaded')))
            scorer = stack.enter_context(patch('hnr.assets.score_dev', side_effect=AssertionError('DEV scored')))
            ab = stack.enter_context(patch('hnr.evaluation.evaluate_ab', side_effect=AssertionError('AB opened')))
            config = dict(root=tmp, devices=[dict(key='generated')], tshark='generated', encoder={})
            result = cli.execute(config, Path(tmp) / 'output', run_runtime=FakeRuntime)
            self.assertEqual(result['status'], 'STOP_NO_NEW_COMPONENT')
            self.assertFalse(result['AB_evaluated'])
            encoder.assert_not_called(); scorer.assert_not_called(); ab.assert_not_called()

    def test_one_encoder_across_three_members_then_dev_fail_blocks_ab(self):
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(cli, 'PACKAGE', Path(tmp)))
            stack.enter_context(patch.object(cli, 'validate_config_bindings'))
            stack.enter_context(patch.object(cli, 'environment_check', return_value={'generated': True}))
            stack.enter_context(patch.object(cli, 'cleanup_intermediates'))
            stack.enter_context(patch('hnr.checks.preflight', return_value={'status': 'READY', 'blockers': []}))
            stack.enter_context(patch('hnr.assets.load_assets', return_value=FakeAssets()))
            prepare = stack.enter_context(patch('hnr.history.prepare_member', return_value={'status': 'PREPARED'}))
            encoder = stack.enter_context(patch('hnr.encoding.new_encoder', return_value=('single-encoder', {'id': 'generated'})))
            counter = iter(range(3))
            def encoded(*args, **kwargs):
                self.assertEqual(kwargs['encoder'], 'single-encoder')
                i = next(counter)
                write(Path(args[1])/'ENCODE_RESULT.json', dict(physical_positions=2))
                return dict(HIST_REF=dataset('ref' + str(i)), HIST_DEV=dataset('dev' + str(i)))
            encoding = stack.enter_context(patch('hnr.encoding.encode_member', side_effect=encoded))
            stack.enter_context(patch('hnr.assets.score_dev', side_effect=lambda queries, *_: queries))
            gate = stack.enter_context(patch('hnr.evaluation.evaluate_dev', return_value=dict(status='STOP_DEV_FAIL', no_AB_loaded=True)))
            ab = stack.enter_context(patch('hnr.evaluation.evaluate_ab', side_effect=AssertionError('AB opened')))
            config = dict(root=tmp, devices=[dict(key=k) for k in TARGETS], tshark='generated', encoder={})
            result = cli.execute(config, Path(tmp) / 'output', run_runtime=FakeRuntime)
            self.assertEqual(result['status'], 'STOP_DEV_FAIL')
            self.assertFalse(result['AB_evaluated'])
            self.assertEqual(prepare.call_count, 3); self.assertEqual(encoding.call_count, 3)
            self.assertEqual(encoder.call_count, 1); self.assertEqual(gate.call_count, 1)
            ab.assert_not_called()


if __name__ == '__main__':
    unittest.main()
