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
    return dict(uid='SYNTHETIC|'+uid, synthetic_fixture=True, label=label, device=device, component_id=uid, activity='NORMAL' if label == 0 else 'TCP',
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

    manifest = dict(schema=matrix.SCHEMA, synthetic_only=True,
        synthetic_fixture_kind='AB_STAGE_UNIT_TEST_ONLY', evaluation_scope=matrix.STAGE_SCOPE,
        stage_matrix_ready=True, full_matrix_ready=False, original_registered_matrix_complete=False,
        supplement_encoding_complete=True, dense_source_cal_complete=True,
        third_pool_deferred=dict(pool_id=matrix.THIRD_POOL,status='DEFERRED_MISSING_FROZEN_BASE_B2',
                                 original_registered_matrix_complete=False), source_cal_result=source_pin,
        source_preparations=preparation_pins, calibration=dict(cuts=cuts, scales=scales, geometry=geometry,
                                                             normalizer=normalizer), pools=pools)
    save('manifest.json', manifest)
    return argparse.Namespace(root=str(root), manifest=str(root/'manifest.json'),
        source_cal_result=str(root/'SOURCE_RESULT.json'), output=str(root/'output'), authorization=None,
        synthetic_dry_run=True)

