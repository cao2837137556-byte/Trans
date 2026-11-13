"""Local contract checks and SHA audit using the real reference metadata."""
import collections
import hashlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from common_round1 import HERE, Inputs, artifact, config_at, dump, load, uid_sha, write_rows
from evaluation import correction, evaluation_rows
from reference_inputs import (ReferenceAssets, cardinality, deduplicate, groups_for_c1,
                              load_reference_metadata, select_m, signature)
from replay_geometry import choose_representatives, plan_queries, replay
from worker import selection_fence
from vendor import constrained_onboarding_core_v3 as core


def row(uid, frame, capture='cap', comp='a', protocol=6, label=0, role='REFERENCE'):
    return dict(uid=uid, frame=frame, capture_id=capture, component_id=comp, protocol=protocol,
                device='device', partition='DEV', timestamp=1. if role == 'REFERENCE' else 3.,
                reference_end=2., bank_end_frame=9, use=role, label=label)


def fixture():
    rows = [row('dense', 1), row('b', 2, comp='b'), row('c', 3, comp='b'),
            row('d', 4, comp='b'), row('e', 5, comp='b'), row('f', 6, comp='a')]
    z = np.zeros((len(rows), 768), np.float32)
    z[:, 0] = 1
    q = np.zeros((len(rows), 14), np.float32)
    q[3, 7], q[4, 7] = .125, .875
    raw_c = np.zeros((len(rows), 8), np.float64)
    ids = [r['uid'] for r in rows]
    norm = np.zeros(768), np.ones(768)
    dense = core.ReferenceBank(rows[:1], z[:1], q[:1], norm, feature_uids=ids[:1], q_uids=ids[:1])
    full = core.ReferenceBank(rows, z, q, norm, feature_uids=ids, q_uids=ids)
    return ReferenceAssets(rows, z, q, raw_c, 1, dense, full, norm, (), {})


class Contract(unittest.TestCase):
    def test_c0_and_c1(self):
        a = fixture()
        kept, p = deduplicate(a)
        self.assertEqual(kept.tolist(), [0, 1, 3, 4, 5])
        self.assertEqual(p.tolist(), [0, 1, 1, 3, 4, 5])
        self.assertEqual(signature(a.rows[1], a.full_bank), signature(a.rows[2], a.full_bank))
        broken = SimpleNamespace(frame_ends={})
        self.assertNotEqual(signature(a.rows[1], broken), signature(a.rows[2], broken))
        changed_context = a.raw_context.copy()
        changed_context[2, 2] = 1.
        a.raw_context = changed_context
        self.assertIn(2, deduplicate(a)[0])
        a.raw_context[2, 2] = 0.
        groups = groups_for_c1(a, kept)
        self.assertEqual(cardinality(a, groups)['total'], 4)
        sel, mapping, n = choose_representatives(a, groups, a.raw_context, config_at(), lambda *x, **y: None)
        self.assertEqual(sel.tolist(), [0, 1, 4, 5])
        self.assertEqual(mapping[3], 1)
        self.assertLessEqual(n, 7)

    def test_opening_single_and_joint(self):
        a = fixture()
        data = dict(rows=[row('closed', 5, role='QUERY'),
                          row('after', 12, role='QUERY'),
                          row('another', 3, capture='other', role='QUERY'),
                          row('absent', 12, protocol=17, role='QUERY')],
                    z=np.repeat(a.z[:1], 4, axis=0), q=np.repeat(a.q[:1], 4, axis=0),
                    context=np.zeros((4, 8)))
        config = config_at()
        progress = lambda *x, **y: None
        g = replay(data, a.dense_bank, a.raw_context[:1], config, progress, 'test',
                   single_mask=np.ones(4, bool), auxiliary=True)
        self.assertEqual(g['opening'].tolist(), ['FRAME', '', '', ''])
        self.assertEqual(g['legal_component_count'].tolist(), [0, 1, 1, 0])
        self.assertEqual(g['support3'].tolist(), [0, 0, 0, 0])
        self.assertEqual(g['single'].tolist(), [0, 1, 1, 0])
        full = replay(data, a.full_bank, a.raw_context, config, progress, 'full')
        self.assertEqual(full['support3'].tolist(), [0, 1, 1, 0])
        # Construct a second component whose E3/q minimum and context minimum
        # come from different rows. Their joint distance must use the same row.
        a.q[2:5, :] = 1.
        a.raw_context[1, :] = 10.
        bank = a.bank(np.arange(len(a.rows)))
        full = replay(data, bank, a.raw_context, config, progress, 'joint')
        self.assertEqual(full['support2'].tolist(), [0, 1, 1, 0])
        self.assertEqual(full['support3'].tolist(), [0, 0, 0, 0])

    def test_guard_and_weighted_protocol_pairs(self):
        a = fixture()
        rows = [row('x', 12, label=0, role='QUERY'), row('y', 13, label=1, role='QUERY')]
        q = a.q[:2].copy()
        q[1, [0, 2]] = 1
        d = dict(rows=rows, q=q, raw=np.full((2, 4), 1.),
                 views={'full': (np.arange(2), np.array([.75, .25]))})
        m = config_at()['method']
        scored = correction(d, np.ones(2), m)
        self.assertTrue((scored[0] < -20).all())
        self.assertEqual(scored[1].tolist(), [1., 1., 1., 1.])
        pair = evaluation_rows(d, d['raw'] > 0, scored > 0)
        record = next(r for r in pair if r['group'] == 'device:device / protocol:6 / NORMAL' and
                      r['head'] == 'ensemble' and r['guard_stratum'] == 'ALL')
        self.assertEqual((record['n10'], record['weighted_n10']), (1, .75))
        self.assertNotIn('HT_rate', record)

    def test_selector_forbids_query_paths(self):
        import subprocess
        import sys
        code = """
from pathlib import Path
import tempfile
from common_round1 import Inputs
from worker import selection_fence
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    for name in ['reference','query']:
        (root/name).write_text('fake')
    store=Inputs(root,{'inputs':{'reference':{'role':'reference','remote':['reference']},'query':{'role':'query','remote':['query']}}},['reference'])
    selection_fence(root,root/'out',store,'select-m-c0')
    assert (root/'reference').read_text()=='fake'
    try:
        store.get('query')
    except ValueError:
        pass
    else:
        raise AssertionError('query through selector input store')
    try:
        (root/'query').read_bytes()
    except PermissionError:
        pass
    else:
        raise AssertionError('query through direct open')
"""
        run = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', code], cwd=HERE,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_duplicate_gate_and_receipt(self):
        from dispatch import inspect_existing, dispatch_job
        from common_round1 import RUN
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            control = p / 'runs' / RUN
            control.mkdir(parents=True)
            relay = control.parent / ('.' + RUN + '_relay_1234')
            relay.mkdir()
            old = '1234|p04-ref-r1-d|RUNNING|0:0'
            with patch('dispatch.checked', return_value=old):
                audit = inspect_existing(p, control)
                self.assertIn(old, audit['unmatched_jobs'])
                self.assertEqual(audit['other_run_directories'], [])
            dump(control / 'JOB_first.json', {'job_id': '1234'})
            with patch('dispatch.checked', return_value=old):
                self.assertEqual(inspect_existing(p, control)['status'], 'PASS')
            with patch('dispatch.command', side_effect=AssertionError('unexpected submission')):
                self.assertEqual(dispatch_job(control, control, p, 'first', 'amd', 8192, 3600)['job_id'], '1234')
                dump(control / 'SUBMIT_INTENT_eval.json', {})
                with self.assertRaisesRegex(ValueError, 'UNRESOLVED_PRIOR_SUBMIT_INTENT'):
                    dispatch_job(control, control, p, 'eval', 'amd', 8192, 3600)


def real_assets():
    cfg = config_at()
    all_pins = load(HERE / 'INPUT_PINS.json')
    store = Inputs(HERE.parents[1], all_pins, ('reference',), local=True)
    check = store.verify()
    allowed_missing = {'dense_context', 'history_context', 'context_normalizer'}
    assert set(check['failures']) <= allowed_missing
    dense, historical = load_reference_metadata(store, cfg)
    full = dense + historical
    assert len(full) == len({r['uid'] for r in full}) == 66082
    assert all(r['history_role'] == 'HIST_REF' and r['use'] == 'REFERENCE' and r['label'] == 0 for r in historical)
    assert uid_sha([r['uid'] for r in full]) == cfg['reference_identity']['full']['uid_sha256']
    assert uid_sha([r['uid'] for r in dense]) == cfg['reference_identity']['dense']['uid_sha256']
    indices, quotas = select_m(full, len(dense), cfg)
    got = collections.Counter((full[i]['device'], full[i]['protocol'], i >= len(dense)) for i in indices)
    want = {(r['device'], r['protocol'], hist): r['history' if hist else 'dense']
            for r in cfg['m']['quotas'] for hist in (False, True)}
    assert all(got[k] == n for k, n in want.items())
    # Independently derive the salted order using hexadecimal digests.
    for (device, protocol, history), count in want.items():
        pool = [r['uid'] for r in (historical if history else dense)
                if r['device'] == device and r['protocol'] == protocol]
        key = lambda u: (hashlib.sha256((cfg['m']['salt'] + '\n' + u).encode()).hexdigest(), u)
        actual = {full[i]['uid'] for i in indices
                  if full[i]['device'] == device and full[i]['protocol'] == protocol and
                  (i >= len(dense)) == history}
        assert set(sorted(pool, key=key)[:count]) == actual
    roster = HERE / 'LOCAL_M_UIDS.jsonl.gz'
    n = write_rows(roster, (dict(uid=full[i]['uid'], row=int(i),
                                source='TWO_HOUR' if i < len(dense) else 'HIST_REF') for i in indices))
    dump(HERE / 'LOCAL_REFERENCE_AUDIT.json', dict(
        status='PASS', scope='local SHA and real reference metadata; no query inputs',
        full=cfg['reference_identity']['full'], dense=cfg['reference_identity']['dense'],
        m_rows=len(indices), m_dense=10011, m_history=3236,
        m_reference_uid_sha256=uid_sha([full[i]['uid'] for i in indices]),
        local_m_roster=artifact(roster, n),
        quotas=quotas, local_reference_pins_verified=len(check['checked']),
        local_missing_reference_pins=sorted(check['failures']),
        real_slurm_preflight='NOT_EXECUTED', c0='not constructed locally', c1='not constructed locally'))
    print('REAL_LOCAL_M_SELECTION', len(indices), uid_sha([full[i]['uid'] for i in indices]))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Contract)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    real_assets()
