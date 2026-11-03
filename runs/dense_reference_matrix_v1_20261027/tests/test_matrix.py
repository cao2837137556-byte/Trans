import argparse
import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / 'src'))
import matrix
import metrics
core, budget = matrix.core, matrix.budget


def row(uid, label=0, device='D', reference=False):
    return dict(uid=uid, label=label, device=device, component_id=uid, activity='NORMAL' if label == 0 else 'TCP',
                capture_id='capture', session_id='session-'+uid, annotation_id='NORMAL' if label == 0 else 'TCP',
                timestamp=1. if reference else 20., reference_end=2., observation_t0=0.,
                frame=1 if reference else 20, protocol=6,
                partition='LEARN' if reference else 'DEV', fit_role='FIT' if reference else 'CAL',
                use='REFERENCE' if reference else 'QUERY', label_metric_weight_denominator=1)


class MatrixBank:
    def __init__(self, support):
        self.support = support
        self.rows = [row('ref1', reference=True), row('ref2', reference=True)]

    def matrix(self, rows, *args, **kwargs):
        return dict(support=np.full((len(rows), 1), self.support), eligible=np.ones((len(rows), 1), dtype=bool),
                    roster=[dict(partition='LEARN', device='D', protocol=6, distinct_components=2)],
                    query_uid_sha256=core._uid_hash([r['uid'] for r in rows]))

    def own(self, rows, *args, **kwargs):
        return dict(support=np.ones(len(rows)))


def source_fixture():
    attacks, normals = [row('attack', 1)], [row('normal')]
    for r in attacks + normals:
        r['partition'] = 'LEARN'
    x = np.full((1, 3), 1.)
    preparation = budget.prepare_budget_calibration(attacks, x, np.zeros(3), 0., np.ones(3), MatrixBank(0.),
        None, None, dict(protocols={'6': dict(status='READY', rho_z=1., rho_q=1.)}),
        cal_normal_rows=normals, normal_logits=np.full((1, 3), .05),
        normal_e3=None, normal_q14=None)
    selections = {str(e): budget.select_budget_lambda(preparation, e) for e in matrix.EPSILONS}
    result = dict(status='SOURCE_CAL_COMPLETE', no_AB_loaded=True, no_model_forward=True,
                  arms={a: dict(selections=copy.deepcopy(selections)) for a in ('R-B2', 'R-DENSE')})
    return preparation, result


def trace(n, value):
    return dict(support=np.full(n, value), eligible=np.ones(n, dtype=bool), same_component=np.zeros(n, dtype=bool),
                reason=np.full(n, 'SUPPORTED', dtype=object))


def synthetic_manifest(root):
    """Exercise real pinned files and V3 math, with explicitly synthetic rows."""
    prep, source = source_fixture()
    def save(name, value):
        (root/name).write_text(json.dumps(value), encoding='utf-8')
        return dict(path=name, sha256=matrix.sha(root/name))
    source_pin = save('SOURCE_RESULT.json', source)
    preparation_pins = {a: save(a+'_PREPARATION.json', prep) for a in ('R-B2', 'R-DENSE')}
    cuts = save('cuts.json', dict(seeds=list(core.SEEDS), moved=False, cuts=[0., 0., 0.], ensemble_cut=0.))
    scales = save('scales.json', dict(scales=[1., 1., 1.]))
    geometry = save('geometry.json', dict(protocols={str(p): dict(status='READY', rho_z=1., rho_q=1.) for p in (6,17)}))
    np.savez(root/'norm.npz', mean=np.zeros(768), scale=np.ones(768))
    normalizer = dict(path='norm.npz', sha256=matrix.sha(root/'norm.npz'))
    def dataset(name, rows, logits=False):
        with gzip.open(root/(name+'.jsonl.gz'), 'wt', encoding='utf-8') as stream:
            for r in rows:
                stream.write(json.dumps(r)+'\n')
        uids = [r['uid'] for r in rows]
        np.savez(root/(name+'.npz'), uid=uids, e3=np.ones((len(rows), 768), dtype=np.float32),
                 q14=np.zeros((len(rows),14), dtype=np.float32), head=np.full((len(rows),3), 1.))
        arr = dict(path=name+'.npz', sha256=matrix.sha(root/(name+'.npz')))
        result = dict(rows=dict(path=name+'.jsonl.gz', sha256=matrix.sha(root/(name+'.jsonl.gz'))),
                      e3=dict(**arr, key='e3'), q14=dict(**arr, key='q14'),
                      feature_uid_sha256=core._uid_hash(uids), q_uid_sha256=core._uid_hash(uids))
        if logits:
            result['logits'] = dict(**arr, key='head')
        return result
    pools = []
    for pool, partition in [('CIC_DEV', 'DEV'), ('UNSW_DEV', 'EXTERNAL_ARCHIVAL_EVALUATION')]:
        queries = [row(pool+d+str(y), y, device=d) for d in ('D1','D2') for y in (0,1)]
        refs = [row(pool+d+'ref'+str(i), reference=True, device=d) for d in ('D1','D2') for i in (1,2)]
        for r in queries+refs:
            r['partition'] = partition
        for r in queries:
            r['label_metric_weight_denominator'] = 2
        bank = dataset(pool+'bank', refs)
        plans = []
        for device, donor in [('D1','D2'), ('D2','D1')]:
            uids = [r['uid'] for r in refs if r['device'] == donor]
            plans.append(dict(device=device, donor_device=donor, protocol=6, status='EVALUABLE',
                              selected_uids=uids, uid_sha256=core._uid_hash(uids), target_n=2, donor_n=2))
        pools.append(dict(pool_id=pool, mode='DENSE_MATRIX', query=dataset(pool,queries,True),
                          b2_bank=bank, dense_bank=bank, wrong_groups=plans, windows={'*': dict(cutoff=2.)}))
    pools.append(dict(pool_id='CIC_THREE_DEVICE_REGRESSION_CONSUMED',
                      mode='BLOCKED_MISSING_FROZEN_BASE_B2', reason='Synthetic missing regression test'))
    manifest = dict(schema=matrix.SCHEMA, synthetic_only=True, source_cal_result=source_pin,
        source_preparations=preparation_pins, calibration=dict(cuts=cuts, scales=scales, geometry=geometry,
                                                             normalizer=normalizer), pools=pools)
    save('manifest.json', manifest)
    return argparse.Namespace(root=str(root), manifest=str(root/'manifest.json'),
        source_cal_result=str(root/'SOURCE_RESULT.json'), output=str(root/'output'), authorization=None,
        synthetic_dry_run=True)


class NumericTests(unittest.TestCase):
    def test_one_component_wrong_donor_is_not_paired_evidence(self):
        refs = [row('a1', reference=True, device='D1'), row('a2', reference=True, device='D1'),
                row('b1', reference=True, device='D2')]
        for r in refs:
            r['partition'] = 'DEV'
        ids = [r['uid'] for r in refs]
        bank = core.ReferenceBank(refs, np.ones((3,768)), np.zeros((3,14)), (np.zeros(768),np.ones(768)),
                                  feature_uids=ids, q_uids=ids, allowed_partitions={'DEV'})
        queries = [row('query', device='D1')]
        plan = [dict(device='D1', protocol=6, donor_device='D2', status='EVALUABLE',
                     selected_uids=['b1'], uid_sha256=core._uid_hash(['b1']), target_n=2, donor_n=1)]
        override, roster = matrix.wrong_override(bank, queries, plan)
        data = dict(rows=queries, e3=np.ones((1,768)), q14=np.zeros((1,14)), feature_uids=['query'], q_uids=['query'])
        geo = dict(protocols={str(p):dict(status='READY',rho_z=1.,rho_q=1.) for p in (6,17)})
        own, wrong = matrix.own_trace(bank,data,geo), matrix.own_trace(bank,data,geo,override)
        self.assertTrue(own['eligible'][0])
        self.assertFalse(wrong['eligible'][0])
        self.assertEqual(roster[0]['density_ratio'], .5)
        paired = metrics.paired_own_wrong(queries, np.asarray([False]), np.asarray([True]), np.ones(1),
                                         own['eligible'], wrong['eligible'])
        self.assertEqual(paired['status'], 'NOT_EVALUABLE')
        self.assertEqual(paired['coverage']['normal']['weight_coverage'], 0.)

    def test_strict_cut_and_original_ensemble_order(self):
        x = np.asarray([[0., np.nextafter(0., 1.), -1.], [2.**53, -(2.**53), 1.]])
        pred = matrix.decisions(x, [0., 0., 0.], 0.)
        self.assertEqual(pred[0].tolist(), [False, True, False, False])
        self.assertEqual(core.ordered_ensemble(x)[1], 1/3)
        self.assertTrue(pred[1, 3])

    def test_saved_epsilon_zero_workpoint_exact_legacy_and_wrong_shared(self):
        preparation, result = source_fixture()
        points = matrix.source_workpoints(result, {a: preparation for a in ('R-B2', 'R-DENSE')})
        self.assertEqual(points['R-B2']['0.0']['selected_lambda'], preparation['legacy_protection']['selected_lambda'])
        self.assertIs(points['R-DENSE'], points['R-DENSE-WRONG'])
        result['arms']['R-B2']['selections']['0.1']['selected_lambda'] = .1
        with self.assertRaisesRegex(ValueError, 'WORKPOINT_REPLAY'):
            matrix.source_workpoints(result, {a: preparation for a in ('R-B2', 'R-DENSE')})

    def test_scientific_fail_does_not_abort_remaining_cells(self):
        prep, source = source_fixture()
        points = matrix.source_workpoints(source, {a: prep for a in ('R-B2', 'R-DENSE')})
        rows = [row('normal'), row('attack', 1)]
        data = dict(rows=rows, logits=np.full((2, 3), 1.))
        events = []
        with tempfile.TemporaryDirectory() as tmp:
            result = matrix.evaluate_pool('CIC_DEV', data, {a: trace(2, 0.) for a in matrix.ARMS}, points,
                    [0., 0., 0.], 0., [1., 1., 1.], {'*': dict(cutoff=2.)}, Path(tmp),
                    lambda a, e: events.append((a, e)))
            self.assertEqual(len(events), 12)
            for arm in matrix.ARMS:
                self.assertEqual(set(result['arms'][arm]), {'0.0', '0.05', '0.1', '0.2'})
                self.assertEqual(result['arms'][arm]['0.1']['views']['post_window_primary']['reports']['ensemble']['gate']['status'], 'FAIL')
            self.assertEqual(len(list(Path(tmp).glob('*decisions.npz'))), 12)

    def test_unknown_epsilon_and_identity_error_stop(self):
        x = np.ones((2, 3))
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_LAMBDA'):
            core.apply_correction(x, np.ones(2), np.ones(3), .2)
        with self.assertRaisesRegex(ValueError, 'FEATURE_UID'):
            core._joined([row('one')], np.ones((1, 768)), np.zeros((1, 14)), ['different'], ['one'])


class IdentityTests(unittest.TestCase):
    def test_real_entrypoint_blocks_missing_third_pool_before_ab_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = synthetic_manifest(root)
            manifest = matrix.read(args.manifest)
            manifest['synthetic_only'] = False
            matrix.write(args.manifest, manifest)
            auth = dict(schema='dense-reference-matrix-authorization-v1', status='AUTHORIZED',
                        scope='REGISTERED_DENSE_MATRIX',allow_target_evaluation=True,evidence='Synthetic test of real entry gate',
                        manifest_sha256=matrix.sha(args.manifest),source_cal_result_sha256=matrix.sha(args.source_cal_result))
            matrix.write(root/'auth.json', auth)
            args.authorization = str(root/'auth.json')
            args.synthetic_dry_run = False
            # Even absent AB files must not be touched when the third-pool
            # contract is unresolved: the first error is the explicit gate.
            (root/'CIC_DEV.npz').unlink()
            with self.assertRaisesRegex(ValueError, 'MATRIX_FROZEN_THIRD_POOL_INPUTS_MISSING'):
                matrix.run(args)
            self.assertFalse((root/'output').exists())

    def test_complete_synthetic_dryrun_real_file_join_and_missing_third_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = synthetic_manifest(root)
            result = matrix.run(args)
            self.assertEqual(result['technical_status'], 'COMPLETE')
            self.assertEqual(result['status'], 'INCOMPLETE')
            self.assertEqual(result['scientific_status'], 'FAIL')
            self.assertTrue(result['synthetic_only'])
            self.assertEqual(result['model_forward_calls'], 0)
            self.assertEqual(len(list((root/'output').rglob('*decisions.npz'))), 24)
            status = matrix.read(root/'output/status.json')
            self.assertTrue(status['terminal'])
            self.assertEqual(status['missing_pools'], ['CIC_THREE_DEVICE_REGRESSION_CONSUMED'])

    def test_corrupt_target_stops_and_preserves_exception_scene(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = synthetic_manifest(root)
            with (root/'CIC_DEV.npz').open('ab') as stream:
                stream.write(b'identity drift')
            with self.assertRaisesRegex(ValueError, 'INPUT_SHA256'):
                matrix.run(args)
            status = matrix.read(root/'output/status.json')
            self.assertEqual(status['status'], 'EXCEPTION_STOP')
            self.assertTrue(status['preserve_scene'])
            self.assertFalse((root/'output/RESULT.json').exists())

    def test_authorization_is_bound_to_exact_manifest_and_source_result(self):
        auth = dict(schema='dense-reference-matrix-authorization-v1', status='AUTHORIZED',
                    scope='REGISTERED_DENSE_MATRIX', allow_target_evaluation=True,
                    manifest_sha256='manifest', source_cal_result_sha256='source', evidence='User authorized registered plan')
        matrix.check_authorization(dict(synthetic_only=False), 'manifest', 'source', auth, False)
        for altered in ('wrong-manifest',):
            with self.assertRaisesRegex(ValueError, 'AUTHORIZATION_REQUIRED'):
                matrix.check_authorization(dict(synthetic_only=False), altered, 'source', auth, False)
        with self.assertRaisesRegex(ValueError, 'SYNTHETIC_CANNOT'):
            matrix.check_authorization(dict(synthetic_only=False), 'manifest', 'source', None, True)

    def test_hash_mismatch_stops_before_array_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'bad.npy'
            path.write_bytes(b'not an array')
            inputs = matrix.Inputs(tmp)
            with self.assertRaisesRegex(ValueError, 'INPUT_SHA256'):
                inputs.array(dict(path='bad.npy', sha256='0'*64))

    def test_real_saved_npz_head_and_uid_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rr = [row('normal'), row('attack', 1)]
            with gzip.open(root/'rows.jsonl.gz', 'wt', encoding='utf-8') as f:
                for r in rr:
                    f.write(json.dumps(r)+'\n')
            np.save(root/'e.npy', np.ones((2, 794), dtype=np.float32))
            np.save(root/'q.npy', np.zeros((2, 14), dtype=np.float32))
            np.savez(root/'scores.npz', uid=['normal', 'attack'], head=np.ones((2, 3), dtype=np.float32))
            def pin(name, **kw):
                return dict(path=name, sha256=matrix.sha(root/name), **kw)
            uh = core._uid_hash(['normal', 'attack'])
            spec = dict(rows=pin('rows.jsonl.gz'), e3=pin('e.npy', column_slice=[0, 768]), q14=pin('q.npy'),
                        feature_uid_sha256=uh, q_uid_sha256=uh, logits=pin('scores.npz', key='head'))
            data = matrix.Inputs(root).dataset(spec, logits=True)
            self.assertEqual(data['e3'].shape, (2, 768))
            self.assertEqual(data['logits'].dtype, np.float64)
            spec['feature_uid_sha256'] = 'wrong'
            with self.assertRaisesRegex(ValueError, 'FEATURE_UID_PIN'):
                matrix.Inputs(root).dataset(spec, logits=True)
            del data
            __import__('gc').collect()

    def test_output_never_overwrites_existing_directory(self):
        # The check is deterministic even before a single target file opens.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'manifest.json').write_text(json.dumps(dict(schema=matrix.SCHEMA, synthetic_only=True)))
            (root/'cal.json').write_text('{}')
            args = argparse.Namespace(manifest=str(root/'manifest.json'), source_cal_result=str(root/'cal.json'),
                     root=str(root), output=str(root), authorization=None, synthetic_dry_run=True)
            with self.assertRaisesRegex(ValueError, 'OUTPUT_ALREADY_EXISTS'):
                matrix.run(args)


if __name__ == '__main__':
    unittest.main()
