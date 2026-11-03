"""Independent generated-only tests for the fixed-model transfer diagnostic.

No historical model, representation, teacher cache, or feature file is opened.
The analytical checks intentionally do not import the real diagnostic worker.
"""
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]


def no_real_numeric(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    raw_path = os.fsdecode(args[0])
    if raw_path.casefold() == os.devnull.casefold():
        return
    path = Path(raw_path).resolve()
    if ROOT / 'runs' in path.parents and path.suffix.lower() in (
            '.pt', '.pth', '.npz', '.npy', '.f32le', '.gz'):
        raise RuntimeError('DIAGNOSTIC_SYNTHETIC_BLOCKED_REAL_NUMERIC:' + str(path))


sys.addaudithook(no_real_numeric)

import issue27frontend_transfer_support_v1 as s
import issue27frontend_transfer_model_v1 as m
import issue27frontend_transfer_diagnostic_math_v1 as d


def context(key, label, owner='A', old=None, role='train', events=(0, 2)):
    targets = [dict(uid=key + ':' + str(i), context_key=key, event=i,
                    label=label, owner=owner,
                    old_hard=label if old is None else old,
                    component_id=key, new_role=role,
                    source_group='source-' + key,
                    attack_family='family-' + str(label), device_family='device')
               for i in events]
    return dict(key=key, role=role, component=key, length=3,
                targets=targets, x=torch.randn(3, 131))


def teacher_index(contexts, cache):
    return {t['uid']: dict(uid=t['uid'], context_key=t['context_key'],
                           label=t['label'], canonical_logit=2. if t['label'] else -2.)
            for c in contexts for t in c['targets'] if t['uid'] in cache}


def norm(x):
    return float(torch.linalg.vector_norm(x))


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m.configure()

    def setUp(self):
        torch.manual_seed(2705)

    def test_parameter_groups_partition_every_parameter_once(self):
        model, projection = m.Student(), m.Projection()
        groups = d.parameter_groups(model, projection)
        self.assertEqual(set(groups), {'event_projection', 'encoder', 'head', 'projection'})
        flattened = [p for ps in groups.values() for p in ps]
        self.assertEqual(len(flattened), len({id(p) for p in flattened}))
        self.assertEqual({id(p) for p in flattened},
                         {id(p) for p in list(model.parameters()) + list(projection.parameters())})
        self.assertEqual({k: sum(p.numel() for p in ps) for k, ps in groups.items()},
                         dict(event_projection=8448, encoder=74496, head=8321, projection=16512))

    def test_analytic_gradients_are_per_task_not_accumulated(self):
        a = torch.nn.Parameter(torch.tensor([2., -3.]))
        b = torch.nn.Parameter(torch.tensor([1.]))
        groups = dict(event_projection=[a], encoder=[b], head=[], projection=[])
        losses = dict(first=(a * torch.tensor([3., -4.])).sum() + b.square().sum(),
                      second=-2. * a.sum())
        result = d.task_gradients(losses, groups)
        torch.testing.assert_close(result['first']['event_projection'],
                                   torch.tensor([3., -4.], dtype=torch.float64), rtol=0, atol=0)
        torch.testing.assert_close(result['first']['encoder'],
                                   torch.tensor([2.], dtype=torch.float64), rtol=0, atol=0)
        torch.testing.assert_close(result['second']['event_projection'],
                                   torch.tensor([-2., -2.], dtype=torch.float64), rtol=0, atol=0)
        self.assertEqual(norm(result['second']['encoder']), 0.)
        self.assertIsNone(a.grad)
        self.assertIsNone(b.grad)
        for values in result.values():
            for value in values.values():
                self.assertEqual(value.dtype, torch.float64)
                self.assertEqual(value.ndim, 1)
                self.assertFalse(value.requires_grad)
                self.assertIsNone(value.grad_fn)

    def test_constant_disconnected_and_differentiable_zero_losses(self):
        a = torch.nn.Parameter(torch.tensor([2., -3.]))
        groups = dict(event_projection=[a], encoder=[], head=[], projection=[])
        losses = dict(constant=torch.tensor(0.),
                      disconnected=torch.tensor(7., requires_grad=True),
                      zero=a.sum() * 0.)
        for task in d.task_gradients(losses, groups).values():
            torch.testing.assert_close(task['event_projection'], torch.zeros(2, dtype=torch.float64),
                                       rtol=0, atol=0)
            self.assertEqual(task['projection'].numel(), 0)
        self.assertIsNone(a.grad)

    def test_parameter_groups_must_not_overlap(self):
        a = torch.nn.Parameter(torch.ones(1))
        with self.assertRaises(s.Stop):
            d.task_gradients(dict(x=a.sum()), dict(event_projection=[a], encoder=[a], head=[], projection=[]))

    def test_nonfinite_loss_is_rejected(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            with self.subTest(value=value):
                a = torch.nn.Parameter(torch.ones(1))
                with self.assertRaises(s.Stop):
                    d.task_gradients(dict(x=a.sum() * value),
                                     dict(event_projection=[a], encoder=[], head=[], projection=[]))

    def test_finite_loss_with_infinite_gradient_is_rejected(self):
        a = torch.nn.Parameter(torch.zeros(1))
        with self.assertRaises(s.Stop):
            d.task_gradients(dict(x=a.sqrt().sum()),
                             dict(event_projection=[a], encoder=[], head=[], projection=[]))

    def generated_tasks(self, zero_projection=False):
        model, projection = m.Student(), m.Projection()
        if not zero_projection:
            with torch.no_grad():
                projection.weight.copy_(torch.eye(128) * .2)
                projection.bias.fill_(.1)
        contexts = [context('attack', 1), context('normal', 0)]
        qs, hs = model([c['x'] for c in contexts], [c['key'] for c in contexts], with_hidden=True)
        cache = {t['uid']: torch.ones(128) for c in contexts for t in c['targets']}
        losses = dict(label=m.label_loss(contexts, qs),
                      teacher=m.teacher_loss(contexts, hs, projection, cache, {0: 1, 1: 1}, 1))
        return model, projection, contexts, qs, hs, cache, losses

    def test_label_has_no_direct_projection_gradient(self):
        model, projection, _, _, _, _, losses = self.generated_tasks()
        result = d.task_gradients(losses, d.parameter_groups(model, projection))
        self.assertEqual(norm(result['label']['projection']), 0.)
        for name in ('event_projection', 'encoder', 'head'):
            self.assertGreater(norm(result['label'][name]), 0.)

    def test_teacher_has_encoder_gradient_but_no_direct_head_gradient(self):
        model, projection, _, _, _, _, losses = self.generated_tasks()
        result = d.task_gradients(losses, d.parameter_groups(model, projection))
        self.assertEqual(norm(result['teacher']['head']), 0.)
        for name in ('event_projection', 'encoder', 'projection'):
            self.assertGreater(norm(result['teacher'][name]), 0.)

    def test_zero_projection_has_zero_first_step_encoder_gradient(self):
        model, projection, _, _, _, _, losses = self.generated_tasks(zero_projection=True)
        result = d.task_gradients(losses, d.parameter_groups(model, projection))
        self.assertEqual(norm(result['teacher']['event_projection']), 0.)
        self.assertEqual(norm(result['teacher']['encoder']), 0.)
        self.assertEqual(norm(result['teacher']['head']), 0.)
        self.assertGreater(norm(result['teacher']['projection']), 0.)

    def test_four_task_gradients_sum_to_independent_total_loss_gradient(self):
        model, projection, contexts, qs, _, _, losses = self.generated_tasks()
        new_context = context('new', 0, owner='B')
        new_qs = model([new_context['x']], [new_context['key']])
        guard = {c['key']: [dict(t, logit=2. if t['label'] else -2., hard=t['label'])
                           for t in c['targets']] for c in contexts}
        penalty, pairs = m.guard_loss(contexts, qs, guard, 1, 2.)
        self.assertGreater(pairs, 0)
        losses = dict(label_A=losses['label'] * .25,
                      label_B=m.label_loss([new_context], new_qs) * .5,
                      guard=penalty, teacher=losses['teacher'])
        groups = d.parameter_groups(model, projection)
        parts = d.task_gradients(losses, groups)
        parameters = [p for ps in groups.values() for p in ps]
        reference = torch.autograd.grad(sum(losses.values()), parameters, allow_unused=True)
        offset = 0
        for group, ps in groups.items():
            expected = torch.cat([(torch.zeros_like(p) if g is None else g).detach().reshape(-1).double()
                                  for p, g in zip(ps, reference[offset:offset + len(ps)])])
            actual = sum(parts[task][group] for task in losses)
            torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-7)
            offset += len(ps)
        self.assertTrue(all(p.grad is None for p in parameters))

    def test_diagnostics_leave_parameters_gradients_rng_and_modes_unchanged(self):
        model, projection, contexts, qs, hs, cache, losses = self.generated_tasks()
        before = (m.state_hash(model), m.state_hash(projection),
                  torch.get_rng_state().clone(), model.training, projection.training)
        d.task_gradients(losses, d.parameter_groups(model, projection))
        d.row_diagnostics(contexts, qs, hs, projection, cache, teacher_index(contexts, cache), .5)
        self.assertEqual(before[:2], (m.state_hash(model), m.state_hash(projection)))
        self.assertTrue(torch.equal(before[2], torch.get_rng_state()))
        self.assertEqual(before[3:], (model.training, projection.training))
        self.assertTrue(all(p.grad is None for p in list(model.parameters()) + list(projection.parameters())))

    def test_gradient_reader_preserves_existing_grad_values(self):
        a = torch.nn.Parameter(torch.tensor([2., 3.]))
        a.grad = torch.tensor([17., -9.])
        before = a.grad.clone()
        d.task_gradients(dict(x=a.square().sum()),
                         dict(event_projection=[a], encoder=[], head=[], projection=[]))
        torch.testing.assert_close(a.grad, before, rtol=0, atol=0)

    def test_vector_metrics_known_analytical_values(self):
        result = d.vector_metrics(torch.tensor([3., 4.]), torch.tensor([4., -3.]))
        self.assertAlmostEqual(result['norm_a'], 5.)
        self.assertAlmostEqual(result['norm_b'], 5.)
        self.assertAlmostEqual(result['dot'], 0.)
        self.assertAlmostEqual(result['cosine'], 0.)

    def test_vector_metrics_positive_and_negative_cosines(self):
        a = torch.tensor([1., -2., 3.])
        self.assertAlmostEqual(d.vector_metrics(a, a * 3)['cosine'], 1.)
        self.assertAlmostEqual(d.vector_metrics(a, a * -2)['cosine'], -1.)

    def test_vector_metrics_zero_norm_cosine_is_null(self):
        for a, b in ((torch.zeros(2), torch.ones(2)),
                     (torch.ones(2), torch.zeros(2)),
                     (torch.zeros(2), torch.zeros(2))):
            with self.subTest(a=a.tolist(), b=b.tolist()):
                result = d.vector_metrics(a, b)
                self.assertIsNone(result['cosine'])
                self.assertEqual(result['dot'], 0.)

    def test_vector_metrics_reject_shape_mismatch_and_nonfinite_input(self):
        for a, b in ((torch.ones(2), torch.ones(3)),
                     (torch.ones(1, 2), torch.ones(1, 2)),
                     (torch.tensor([float('nan')]), torch.ones(1)),
                     (torch.ones(1), torch.tensor([float('inf')]))):
            with self.subTest(a=a.tolist(), b=b.tolist()):
                with self.assertRaises(s.Stop):
                    d.vector_metrics(a, b)

    def row_fixture(self, bias=0.):
        contexts = [context('attack', 1, events=(0,))]
        qs, hs = [torch.tensor([.75, 0., -1.])], [torch.zeros(3, 128)]
        projection = m.Projection()
        with torch.no_grad():
            projection.bias.fill_(bias)
        cache = {'attack:0': torch.zeros(128)}
        return contexts, qs, hs, projection, cache, teacher_index(contexts, cache)

    def test_row_identity_and_logits_join_exact_teacher_target(self):
        values = self.row_fixture(.5)
        row = d.row_diagnostics(*values, 2.)[0]
        self.assertEqual(row['uid'], 'attack:0')
        self.assertEqual(row['context_key'], 'attack')
        self.assertEqual(row['label'], 1)
        self.assertEqual(row['source_group'], 'source-attack')
        self.assertEqual(row['attack_family'], 'family-1')
        self.assertEqual(row['student_logit'], .75)
        self.assertEqual(row['teacher_logit'], 2.)
        self.assertAlmostEqual(row['coordinate_huber'], .125)
        self.assertAlmostEqual(row['coordinate_rmse'], .5)

    def test_task_residual_accumulates_all_128_coordinates(self):
        for bias in (.5, -.5, 0.):
            with self.subTest(bias=bias):
                row = d.row_diagnostics(*self.row_fixture(bias), 2.)[0]
                self.assertEqual(row['task_residual'], 2. * 128 * bias)
                self.assertAlmostEqual(row['coordinate_huber'], .5 * bias * bias)
                self.assertAlmostEqual(row['coordinate_rmse'], abs(bias))

    def test_task_residual_uses_float64_before_summing(self):
        values = self.row_fixture()
        with torch.no_grad():
            values[3].bias[:3].copy_(torch.tensor([16777216., 1., -16777216.]))
        row = d.row_diagnostics(*values, .5)[0]
        self.assertEqual(row['task_residual'], .5)

    def test_huber_linear_region_and_rmse_independent_reference(self):
        values = self.row_fixture()
        residual = torch.linspace(-2., 2., 128, dtype=torch.float32)
        with torch.no_grad():
            values[3].bias.copy_(residual)
        row = d.row_diagnostics(*values, .25)[0]
        raw = [float(v) for v in residual]
        expected_huber = sum(.5 * v * v if abs(v) <= 1 else abs(v) - .5 for v in raw) / 128
        expected_rmse = math.sqrt(sum(v * v for v in raw) / 128)
        self.assertAlmostEqual(row['coordinate_huber'], expected_huber, places=7)
        self.assertAlmostEqual(row['coordinate_rmse'], expected_rmse, places=7)

    def test_uncached_B_and_teacher_errors_are_excluded(self):
        contexts = [context('legal', 1), context('new', 0, owner='B'), context('wrong', 1, old=0)]
        qs, hs = [torch.zeros(3) for _ in contexts], [torch.zeros(3, 128) for _ in contexts]
        cache = {'legal:0': torch.ones(128)}
        rows = d.row_diagnostics(contexts, qs, hs, m.Projection(), cache, teacher_index(contexts, cache), 1.)
        self.assertEqual([r['uid'] for r in rows], ['legal:0'])

    def test_nontrain_context_is_rejected(self):
        for role in ('check', 'expanded', 'select', 'report', 'FINAL'):
            with self.subTest(role=role):
                values = self.row_fixture()
                values[0][0]['role'] = role
                with self.assertRaises(s.Stop):
                    d.row_diagnostics(*values, 1.)

    def test_cached_B_teacher_is_rejected(self):
        values = self.row_fixture()
        values[0][0]['targets'][0]['owner'] = 'B'
        with self.assertRaises(s.Stop):
            d.row_diagnostics(*values, 1.)

    def test_cached_incorrect_teacher_is_rejected(self):
        values = self.row_fixture()
        values[0][0]['targets'][0]['old_hard'] = 0
        with self.assertRaises(s.Stop):
            d.row_diagnostics(*values, 1.)

    def test_teacher_index_context_and_label_must_match(self):
        for field, replacement in (('context_key', 'elsewhere'), ('label', 0)):
            with self.subTest(field=field):
                values = self.row_fixture()
                values[5]['attack:0'][field] = replacement
                with self.assertRaises(s.Stop):
                    d.row_diagnostics(*values, 1.)

    def test_duplicate_teacher_target_is_rejected(self):
        values = self.row_fixture()
        values[0][0]['targets'].append(dict(values[0][0]['targets'][0]))
        with self.assertRaises(s.Stop):
            d.row_diagnostics(*values, 1.)

    def test_teacher_vector_shape_and_nonfinite_values_are_rejected(self):
        for target in (torch.ones(127), torch.full((128,), float('nan'))):
            with self.subTest(shape=list(target.shape)):
                values = self.row_fixture()
                values[4]['attack:0'] = target
                with self.assertRaises(s.Stop):
                    d.row_diagnostics(*values, 1.)

    def test_teacher_scale_must_be_positive_and_finite(self):
        for scale in (0., -1., float('nan'), float('inf')):
            with self.subTest(scale=scale):
                with self.assertRaises(s.Stop):
                    d.row_diagnostics(*self.row_fixture(), scale)


class DiagnosticIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import issue27frontend_transfer_diagnostic_fixture_v1 as fixture
        cls.fixture = fixture
        fixture.TEST_ROOT.mkdir(parents=True, exist_ok=True)

    def test_generated_full_diagnose_path_and_persisted_statistics(self):
        with tempfile.TemporaryDirectory(dir=self.fixture.TEST_ROOT) as td:
            out = Path(td) / 'diagnostic'
            value = self.fixture.generated_diagnose(out)
            result, access = value['result'], value['access']
            self.assertEqual(result['status'], 'DIAGNOSTIC_COMPLETE')
            self.assertEqual(result['targets'], 12)
            self.assertEqual(result['teacher_targets'], 8)
            self.assertTrue(result['parameters_unchanged'])
            self.assertTrue(result['parameter_grad_none'])
            self.assertLess(result['baseline_max_abs_delta'], 1e-5)
            self.assertEqual(access['contexts_processed'], 6)
            self.assertEqual(access['student_forwards'], 4)
            self.assertEqual(access['task_gradient_calls'], 8)
            self.assertEqual(access['hidden_gradient_calls'], 2)
            self.assertEqual(value['generated_state_loads'], 2)
            self.assertEqual(access['teacher_cache_rows'], 8)
            for name in ('optimizer_steps', 'teacher_passes', 'retries', 'raw_decodes',
                         'network_requests', 'evaluated_targets', 'feature_bytes_decoded'):
                self.assertEqual(access[name], 0, name)
            self.assertEqual(set(result['losses_fixed_epoch20']), {'label_A', 'label_B', 'guard', 'teacher'})
            self.assertEqual(result['gradient_of_mean_objective']['head']['norms']['teacher'], 0.)
            self.assertEqual(result['gradient_of_mean_objective']['projection']['norms']['label'], 0.)
            self.assertGreater(result['gradient_of_mean_objective']['shared']['norms']['teacher'], 0.)
            self.assertEqual(s.read_json(out / 'diagnostic.json'), result)
            rows = [json.loads(line) for line in (out / 'teacher_readout.jsonl').read_text().splitlines()]
            buckets = [json.loads(line) for line in (out / 'bucket_diagnostics.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 8)
            self.assertEqual(len({row['uid'] for row in rows}), 8)
            self.assertEqual(len(buckets), 2)
            self.assertTrue(all(row['uid'].startswith('A') for row in rows))
            self.assertTrue(all(row['local_head_teacher_cosine'] is not None for row in rows))
            self.assertEqual(result['readout']['ALL']['coordinate_huber']['n'], 8)
            self.assertEqual(result['readout']['label:0']['coordinate_huber']['n'], 4)
            self.assertEqual(result['readout']['label:1']['coordinate_huber']['n'], 4)
            expected = sum(abs(row['task_residual']) for row in rows) / len(rows)
            self.assertAlmostEqual(result['readout']['ALL']['absolute_task_residual']['mean'], expected)
            for task, loss in result['losses_fixed_epoch20'].items():
                self.assertAlmostEqual(loss, sum(bucket['losses'][task] for bucket in buckets) / 2.)
            self.assertEqual(s.read_json(out / 'progress.json')['bucket'], 2)

    def test_D_supervisor_job_append_progress_with_concurrent_held_readers(self):
        with tempfile.TemporaryDirectory(dir=self.fixture.TEST_ROOT) as td:
            out = Path(td) / 'supervised-diagnostic'
            command = [str(s.PYTHON), '-B', str(Path(self.fixture.__file__).resolve()), 'supervise', str(out)]
            process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
            stop = threading.Event()
            errors, counts = [], [0, 0, 0]

            def read_progress(slot):
                try:
                    while not stop.is_set() and not (out / 'progress.json').exists():
                        stop.wait(.005)
                    if stop.is_set():
                        return
                    # Ordinary held Windows handles must not prevent appends.
                    with (out / 'progress.json').open('rb'), (out / 'progress.jsonl').open('rb'):
                        previous = -1
                        while not stop.is_set():
                            value = s.read_json(out / 'progress.json')
                            if value['padding'] != 'x' * 4096 or value['bucket'] < previous:
                                raise AssertionError('torn or regressing generated progress')
                            previous = value['bucket']
                            counts[slot] += 1
                            stop.wait(.002)
                except Exception as exc:
                    errors.append(repr(exc))

            threads = [threading.Thread(target=read_progress, args=(i,)) for i in range(3)]
            for thread in threads:
                thread.start()
            try:
                stdout, stderr = process.communicate(timeout=60)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
                stop.set()
                for thread in threads:
                    thread.join(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertFalse(errors, errors)
            self.assertTrue(all(count > 0 for count in counts), counts)
            result = json.loads(stdout)
            self.assertEqual(result['status'], 'COMPLETE', result)
            self.assertEqual(result['stage'], 'D')
            self.assertTrue(result['synthetic'])
            self.assertTrue(result['verified'])
            self.assertEqual(result['retries'], 0)
            self.assertEqual(result['worker_exit_code'], 0)
            self.assertEqual(s.read_json(out / 'progress.json')['bucket'], 499)
            self.assertEqual(len((out / 'progress.jsonl').read_text().splitlines()), 500)
            self.assertEqual(s.read_json(out / 'attempt.json')['synthetic'], True)
            self.assertEqual(s.read_json(out / 'worker_terminal.json')['stage'], 'D')
            self.assertIn('generated_result.json', s.manifest(out))


def tested_sources():
    paths = list((ROOT / 'repo/ood').glob('issue27frontend_transfer_diagnostic*_v1.py'))
    paths += list((ROOT / 'scripts').glob('*frontend_transfer_diagnostic_v1.ps1'))
    paths += [ROOT / 'repo/ood' / name for name in (
        'issue27frontend_transfer_support_v1.py', 'issue27frontend_transfer_model_v1.py',
        'issue27frontend_paired_train_support_v1.py', 'issue27frontend_paired_train_model_v1.py')]
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(set(paths))}


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: diagnostic_tests_v1.py RESULT.json')
    started = time.monotonic()
    before = tested_sources()
    output = io.StringIO()
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(DiagnosticTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(DiagnosticIntegrationTests)])
    # These APIs are unnecessary for generated diagnostics. Reject any accidental
    # asset decoding independently of the audited filesystem suffix guard.
    with patch.object(torch, 'load', side_effect=RuntimeError('NO_MODEL_LOAD_IN_SYNTHETIC')), \
            patch.object(np, 'load', side_effect=RuntimeError('NO_ARRAY_LOAD_IN_SYNTHETIC')), \
            patch.object(np, 'fromfile', side_effect=RuntimeError('NO_FEATURE_LOAD_IN_SYNTHETIC')):
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    unchanged = before == tested_sources()
    status = 'PASS' if result.wasSuccessful() and unchanged else 'FAIL'
    report = dict(status=status, tests_run=result.testsRun,
                  tests_passed=result.testsRun - len(result.failures) - len(result.errors),
                  elapsed_seconds=time.monotonic() - started,
                  real_model_forwards=0, real_optimizer_steps=0, real_teacher_rows=0,
                  source_unchanged_during_tests=unchanged, tested_code_pins=before,
                  generated_only=True, details=output.getvalue())
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('details', 'tested_code_pins')}))
    if status != 'PASS':
        print(output.getvalue())
        raise SystemExit(1)


if __name__ == '__main__':
    main()
