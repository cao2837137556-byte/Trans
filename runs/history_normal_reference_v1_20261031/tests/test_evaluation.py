"""Generated data only: gates, exact support accounting, and frozen-bank union."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from hnr.assets import joined
from hnr.common import TARGETS, HEIM, rows as read_rows, read, sha
from hnr import evaluation as ev


def row(uid, device, label=0, timestamp=2., component='one', use='QUERY', **extra):
    return dict(uid=uid, partition='EXTERNAL_ARCHIVAL_EVALUATION', device=device,
                protocol=6, frame=2, timestamp=timestamp, component_id=component,
                capture_id='query', use=use, label=label, annotation_id='attack',
                activity='attack', session_id=uid, **extra)


def frozen():
    return dict(normalizer=(np.zeros(768), np.ones(768)),
                geometry={'protocols': {str(p): dict(status='READY', rho_z=1., rho_q=1.) for p in (6, 17)}},
                cuts=dict(cuts=[0., 0., 0.], ensemble_cut=0.), scales=[1., 1., 1.])


class Runtime:
    def __init__(self): self.count = 0; self.events = []
    def pairs(self, n): self.count += n
    def update(self, stage, **values): self.events.append((stage, values))


class EvaluationTests(unittest.TestCase):
    def test_dev_row_weighted_gate_and_no_room(self):
        rr = []
        for j, target in enumerate(TARGETS.values()):
            rr += [row(str(j) + str(i), target['device']) for i in range(j + 2)]
        raw = np.ones(len(rr), dtype=bool)
        after = np.zeros(len(rr), dtype=bool)
        result = ev.dev_gate(rr, raw, after)
        self.assertEqual(result['status'], 'PASS_DEV')
        self.assertEqual(result['pooled']['rows'], 9)
        raw[:2] = False
        result = ev.dev_gate(rr, raw, after)
        self.assertEqual(result['status'], 'STOP_DEV_FAIL')
        self.assertTrue(any(d['status'] == 'STOP_DEV_NO_ROOM' for d in result['devices']))

    def test_dev_each_device_strictly_improves(self):
        rr = [row(str(i), target['device']) for i, target in enumerate(TARGETS.values())]
        raw = np.ones(3, dtype=bool)
        result = ev.dev_gate(rr, raw, np.asarray([True, False, False]))
        self.assertGreaterEqual(result['pooled']['relative_fpr_reduction'], .5)
        self.assertEqual(result['status'], 'STOP_DEV_FAIL')

    def test_dev_support_and_frozen_correction(self):
        refs, queries = [], []
        for i, target in enumerate(TARGETS.values()):
            cutoff = target['reference_end_us'] / 1e6
            for c in (0, 1):
                refs.append(row('r%d%d' % (i, c), target['device'], timestamp=cutoff - 1.,
                                component=str(c), use='REFERENCE', reference_end=cutoff,
                                bank_end_frame=target['bank_end_frame']))
            q = row('q' + str(i), target['device'], timestamp=cutoff + 1.)
            q['frame'] = target['bank_end_frame'] + 1
            queries.append(q)
        ref = joined(refs, np.ones((6, 768)), np.zeros((6, 14)))
        query = joined(queries, np.ones((3, 768)), np.zeros((3, 14)), logits=np.full((3, 3), .1))
        runtime = Runtime()
        for r in queries:
            r['source_sha256'] = 'a'*64
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'dev'
            result = ev.evaluate_dev(query, ref, frozen(), runtime, output=output)
            with np.load(output / 'DEV_DECISIONS.npz', allow_pickle=False) as saved:
                self.assertEqual(saved['uid'].tolist(), [r['uid'] for r in queries])
                self.assertTrue(np.array_equal(saved['raw_logits'], query['logits']))
                self.assertTrue(np.array_equal(saved['base'][:, 3], np.ones(3, dtype=bool)))
                self.assertFalse(saved['corrected'][:, 3].any())
            self.assertEqual(list(read_rows(output/'QUERIES.jsonl.gz')), queries)
            receipt = read(output/'AUDIT_RECEIPT.json')
            self.assertEqual(receipt['result_sha256'], sha(output/'RESULT.json'))
            self.assertEqual(receipt['additional_distance_pairs'], 0)
        self.assertEqual(result['status'], 'PASS_DEV')
        self.assertEqual(runtime.count, 6)
        self.assertEqual(result['distance_pairs'], 6)
        self.assertTrue(result['no_AB_loaded'])
        self.assertEqual(result['positive_support_rows'], 3)

    def test_ref_dev_overlap_rejected(self):
        data = joined([row('same', 'd')], np.ones((1, 768)), np.zeros((1, 14)))
        with self.assertRaisesRegex(ValueError, 'HIST_REF_DEV_UID_OVERLAP'):
            ev.evaluate_dev(data, data, frozen())

    def test_failed_dev_never_opens_ab_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(ev, 'load_assets', side_effect=AssertionError('AB was loaded')) as loader:
                with self.assertRaisesRegex(ValueError, 'DEV_GATE_REQUIRED_BEFORE_AB_LOAD'):
                    ev.evaluate_ab(Path(tmp), Path(tmp) / 'absent', {}, {'status': 'STOP_DEV_FAIL'})
                loader.assert_not_called()
                self.assertFalse((Path(tmp) / 'absent').exists())

    def test_union_retains_original_and_uses_two_cutoffs(self):
        original = row('old', 'd', use='REFERENCE', timestamp=1., reference_end=5., bank_end_frame=3)
        hist = row('hist', 'd', use='REFERENCE', timestamp=.1, reference_end=.5, bank_end_frame=2)
        hist['capture_id'] = 'historical'
        a = joined([original], np.ones((1, 768)), np.zeros((1, 14)))
        b = joined([hist], np.ones((1, 768)), np.zeros((1, 14)))
        result = ev.union_bank(a, b)
        self.assertEqual(result['rows'][0], original)
        self.assertEqual(result['rows'][1]['reference_end'], 5.)
        self.assertEqual(result['rows'][1]['historical_reference_end'], .5)
        self.assertEqual(result['rows'][1]['bank_end_frame'], 2)
        self.assertEqual(b['rows'][0]['reference_end'], .5)

    def test_low_raw_recall_requires_zero_tp_withdrawal(self):
        rr = [row(str(i), 'd', label=1) for i in range(100)]
        raw = np.asarray([True] * 98 + [False] * 2)
        corrected = raw.copy(); corrected[0] = False
        metric = ev.helpers().metrics.report(rr, raw, corrected, np.ones(100) / 100,
                                            np.ones(100, dtype=bool), np.ones(100))
        gate = ev.protection_gate(metric)
        self.assertEqual(gate['status'], 'FAIL')
        self.assertTrue(any('ZERO_WITHDRAWAL' in s for s in gate['failures']))
        self.assertFalse(gate['pool_epsilon_enforced'])

    def test_budget_is_not_old_pool_epsilon(self):
        rr = [row(str(i), 'd', label=1) for i in range(1000)]
        raw = np.ones(1000, dtype=bool)
        corrected = raw.copy(); corrected[:5] = False
        metric = ev.helpers().metrics.report(rr, raw, corrected, np.ones(1000) / 1000,
                                            np.ones(1000, dtype=bool), np.ones(1000))
        self.assertEqual(ev.protection_gate(metric)['status'], 'PASS')

    def test_terminal_checks_all_heads_and_untouched_devices_primary(self):
        metric = dict(protection=dict(status='PASS'),
                      corrected=dict(normal=dict(weighted_rate=.01), attack=dict(weighted_rate=1.)),
                      groups={'device': [dict(group={'device': 'untouched'},
                                              corrected={'normal': dict(rows=10, weighted_rate=.01)})]})
        view = dict(reports={suffix: deepcopy(metric) for suffix in ev.SUFFIXES})
        pools = {pool: dict(original_devices=['untouched'],
                           views={ev.PRIMARY: deepcopy(view), 'full': {'irrelevant': True}}) for pool in ev.POOLS}
        self.assertEqual(ev.terminal_gate(pools)['status'], 'PASS')
        pools['UNSW_DEV']['views'][ev.PRIMARY]['reports']['ensemble']['groups']['device'][0]['corrected']['normal']['weighted_rate'] = .025
        self.assertEqual(ev.terminal_gate(pools)['status'], 'IMPROVED_NOT_PASS')
        pools['CIC_DEV']['views'][ev.PRIMARY]['reports']['27']['protection']['status'] = 'FAIL'
        self.assertEqual(ev.terminal_gate(pools)['status'], 'FAIL_PROTECTION')

    def test_activity_protection_uses_original_metric_activity_groups(self):
        rr = [row('d%d' % i, 'd', label=1) for i in range(100)]
        rr[0]['activity'] = 'rare_activity'
        raw = np.ones(100, dtype=bool); after = raw.copy(); after[0] = False
        metric = ev.helpers().metrics.report(rr, raw, after, np.ones(100)/100,
                                            np.ones(100, dtype=bool), np.ones(100))
        gate = ev.protection_gate(metric)
        self.assertEqual(gate['group_fields']['attack_type'], ['activity'])
        self.assertTrue(any('attack_type_WITHDRAWAL_BUDGET:rare_activity' == f for f in gate['failures']))

    def test_terminal_cannot_drop_original_device_normal_denominator(self):
        metric = dict(protection=dict(status='PASS'),
                      corrected=dict(normal=dict(weighted_rate=.01), attack=dict(weighted_rate=1.)),
                      groups={'device': []})
        view = dict(reports={suffix: deepcopy(metric) for suffix in ev.SUFFIXES})
        pools = {pool: dict(original_devices=['original'], views={ev.PRIMARY: deepcopy(view)}) for pool in ev.POOLS}
        result = ev.terminal_gate(pools)
        self.assertEqual(result['status'], 'IMPROVED_NOT_PASS')
        self.assertTrue(any('DEVICE_PRIMARY_NORMAL_MISSING:original' in f for f in result['target_failures']))

    def test_complete_generated_ab_reuses_untouched_support_and_is_once_only(self):
        history_rows = []
        for j, device in enumerate([HEIM['device']] + [t['device'] for t in TARGETS.values()]):
            for component in (0, 1):
                r = row('hist%d%d' % (j, component), device, timestamp=.1,
                        component='hist' + str(component), use='REFERENCE', reference_end=.2)
                r['capture_id'] = 'historical'
                history_rows.append(r)
        history = joined(history_rows, np.ones((8, 768)), np.zeros((8, 14)))
        class FakeAssets:
            def __init__(self):
                self.inputs = type('Pins', (), {'pins': {}})()
                self.spec = {'pools': {p: dict(windows={'*': dict(cutoff=.5)}) for p in ev.POOLS}}
                self.datasets = {}
            def calibration(self): return frozen()
            def queries(self, pool):
                devices = ([HEIM['device'], 'Eufy Home Base'] if pool == 'CIC_DEV' else
                           [t['device'] for t in TARGETS.values()] + ['Motion', 'Netatmo'])
                rr, logits = [], []
                for j, device in enumerate(devices):
                    for label in (0, 1):
                        rr.append(row(pool + str(j) + str(label), device, label=label,
                                      label_metric_weight_denominator=len(devices)))
                        normal = -.1 if device in ('Eufy Home Base', 'Motion', 'Netatmo') else .1
                        logits.append([1. if label else normal] * 3)
                data = joined(rr, np.ones((len(rr), 768)), np.zeros((len(rr), 14)), logits=np.asarray(logits))
                self.datasets[pool] = data
                return data
            def baseline(self, pool, uids):
                data = self.datasets[pool]
                before = ev.decisions(data['logits'], frozen())
                trace = dict(support=np.zeros(len(uids)), eligible=np.zeros(len(uids), dtype=bool),
                             base=before, corrected=before.copy(), raw_logits=data['logits'].copy())
                old = {'corrected': {'normal': {'weighted_rate': .5}}}
                view = {'reports': {s: deepcopy(old) for s in ev.SUFFIXES}}
                return trace, {'arms': {'R-DENSE': {'0.1': {'views': {'full': view, ev.PRIMARY: view}}}}}
            def dense(self, pool):
                devices = {r['device'] for r in self.datasets[pool]['rows']}
                rr = []
                for j, device in enumerate(sorted(devices)):
                    for c in (0, 1):
                        r = row(pool + 'ref%d%d' % (j, c), device, timestamp=.25,
                                component='old' + str(c), use='REFERENCE', reference_end=.5)
                        r['capture_id'] = 'old-bank'
                        rr.append(r)
                return joined(rr, np.ones((len(rr), 768)), np.zeros((len(rr), 14)))
            def immutable(self): pass
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'AB'
            with patch.object(ev, 'load_assets', return_value=FakeAssets()):
                result = ev.evaluate_ab(tmp, output, history,
                                        dict(status='PASS_DEV', no_AB_loaded=True, query_uid_sha256='synthetic'))
                self.assertEqual(result['status'], 'PASS')
                self.assertEqual(result['distance_pairs'], 32)
                self.assertEqual(result['pools']['CIC_DEV']['reused_support_rows'], 2)
                self.assertEqual(result['pools']['UNSW_DEV']['reused_support_rows'], 4)
                self.assertTrue(result['pools']['UNSW_DEV']['untouched_decisions_exact'])
                with self.assertRaisesRegex(ValueError, 'AB_ONCE_OUTPUT_ALREADY_EXISTS'):
                    ev.evaluate_ab(tmp, output, history,
                                   dict(status='PASS_DEV', no_AB_loaded=True, query_uid_sha256='synthetic'))


if __name__ == '__main__':
    unittest.main()
