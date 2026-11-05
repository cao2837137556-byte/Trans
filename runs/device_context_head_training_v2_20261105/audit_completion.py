"""Audit final small receipts without retrieving model or logit arrays."""
import hashlib
import json
from pathlib import Path
import accept_training

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(name):
    return json.loads((HERE/name).read_text(encoding='utf-8-sig'))


def main():
    accepted = accept_training.accept()
    delivery = read('DELIVERY.json')
    for name, digest in delivery['pins'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == digest, name
    spec = read('TRAINING_SPEC_FROZEN.json')
    norm = read('NORMALIZER.json')
    assert norm['source'] == 'LEARN/FIT' and norm['rows'] == spec['data_identity']['FIT']['rows']
    assert norm['fit_uid_sha256'] == spec['data_identity']['FIT']['uid_sha256']
    assert norm['sha256'] == read('PREFLIGHT_RESULT.json')['normalizer_sha256']
    state = read('RETRIEVAL.json')['state']
    assert state['stage'] == 'TRAINING_COMPLETE' and state['completed_heads'] == 9
    assert all(v is None for k, v in state.items() if k.endswith('_STOP'))
    resources = {}
    for phase in ['TRAIN_'+name for name in accepted['heads']] + ['CALIBRATION']:
        job, result = read(phase+'_JOB.json'), read(phase+'_RESULT.json')
        sched = read(phase+'_SCHEDULER.json')
        rows = [line.split('|') for line in sched['stdout'].splitlines()]
        top = next(row for row in rows if row[0] == job['job_id'])
        assert sched['returncode'] == 0 and top[1:3] == ['COMPLETED', '0:0']
        assert job['cpu'] == 1 and job['memory_gib'] == 8
        assert job['wall_seconds'] == (900 if phase == 'CALIBRATION' else 3600)
        assert result['cpu_threads'] == 1 and result['external_data_read'] is False
        h, m, s = map(int, top[3].split(':'))
        elapsed = h*3600+m*60+s
        assert elapsed < job['wall_seconds']
        rss = next(row[4] for row in rows if row[0] == job['job_id']+'.batch')
        unit = rss[-1]
        assert unit in 'KMGT'
        rss_bytes = float(rss[:-1])*1024**('KMGT'.index(unit)+1)
        resources[phase] = dict(job_id=job['job_id'], elapsed_seconds=elapsed, slurm_max_rss_bytes=rss_bytes)
        if phase != 'CALIBRATION':
            assert [p['epoch'] for p in result['profile']] == list(range(1, 41))
            assert all(p['batches'] == 2414 for p in result['profile'])
            cal = result['calibration']
            assert cal['cal_uid_sha256'] == spec['data_identity']['CAL']['uid_sha256']
            assert cal['threshold_source'] == 'CAL_NORMAL' and cal['scale_source'] == 'FIT'
            assert cal['comparison'] == '>' and cal['normal_rows'] == 33147
            assert cal['scale'] == cal['q90']-cal['q10']
    frozen = json.loads((ROOT/'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json').read_text())['calibration']
    refit = [accepted['heads']['REFIT782_'+str(seed)] for seed in (27, 127, 227)]
    identity = dict(seed_cuts=[x['cut'] for x in refit] == frozen['cuts']['cuts'],
                    seed_scales=[x['scale'] for x in refit] == frozen['scales']['scales'],
                    ensemble_cut=accepted['ensembles']['REFIT782']['cut'] == frozen['cuts']['ensemble_cut'])
    heads = {k: v for k, v in resources.items() if k != 'CALIBRATION'}
    result = dict(result='PASS', scope='TRAINING_AND_SOURCE_CALIBRATION_ONLY',
                  impact='Nine complete epoch40 endpoints and source calibration accepted; external detection unknown',
                  next='AB_NO_REGRESSION_AND_EDGE_DIAGNOSTIC', resources=resources,
                  training_elapsed_sum_seconds=sum(v['elapsed_seconds'] for v in heads.values()),
                  max_training_rss_bytes=max(v['slurm_max_rss_bytes'] for v in heads.values()),
                  refit_calibration_matches_old=identity,
                  refit_identity_limit='Matching cuts/scales does not prove every model parameter or every sample score is identical',
                  ensembles=accepted['ensembles'], new_heads=9, total_optimizer_updates=869040,
                  verification_scope='Pinned source and retrieved receipt audit; remote worker verified model/logit files, full arrays not downloaded',
                  acceptance_sha256=hashlib.sha256((HERE/'FINAL_TRAINING_ACCEPTANCE.json').read_bytes()).hexdigest())
    (HERE/'COMPLETION_AUDIT.json').write_bytes((json.dumps(result, indent=2)+'\n').encode())
    print(json.dumps(result))


if __name__ == '__main__':
    main()
