"""Small-receipt acceptance; models, logits, and loss arrays stay on HPC."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE/name).read_text(encoding='utf-8-sig'))


def accept():
    retrieval = read('RETRIEVAL.json')
    assert retrieval['state']['stage'] == 'TRAINING_COMPLETE'
    for name, digest in retrieval['sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == digest
    preflight = read('PREFLIGHT_RESULT.json')
    assert preflight['status'] == 'PASS' and max(preflight['forecasts'].values()) <= 1800
    heads = {}
    for arm in ('REFIT782', 'STATS8', 'FUSION790'):
        for seed in (27, 127, 227):
            phase = f'TRAIN_{arm}_{seed}'
            result, job = read(phase+'_RESULT.json'), read(phase+'_JOB.json')
            scheduler = read(phase+'_SCHEDULER.json')['stdout']
            assert job['job_id']+'|COMPLETED|0:0|' in scheduler
            assert result['status'] == 'PASS' and not result['runtime_gate_only']
            assert result['updates'] == 96560 and result['epochs'] == 40
            assert result['arm'] == arm and result['seed'] == seed
            assert result['calibration']['weighted_normal_fpr'] <= .01+1e-14
            assert result['calibration']['checkpoint_score_readback']
            heads[f'{arm}_{seed}'] = dict(job_id=job['job_id'], head_sha256=result['head_sha256'],
                cut=result['calibration']['cut'], scale=result['calibration']['scale'])
    calibration = read('CALIBRATION_RESULT.json')
    assert calibration['status'] == 'PASS' and calibration['new_heads'] == 9
    assert set(calibration['ensembles']) == {'REFIT782', 'STATS8', 'FUSION790'}
    for result in calibration['ensembles'].values():
        assert result['status'] == 'PASS' and result['weighted_normal_fpr'] <= .01+1e-14
    result = dict(result='PASS', scope='TRAINING_AND_SOURCE_CALIBRATION_ONLY', new_heads=9,
                  total_optimizer_updates=869040, heads=heads, ensembles=calibration['ensembles'],
                  evaluation_pending=True, next='AB_NO_REGRESSION_AND_EDGE_DIAGNOSTIC',
                  receipt_sha256=retrieval['sha256'])
    (HERE/'FINAL_TRAINING_ACCEPTANCE.json').write_bytes((json.dumps(result, indent=2)+'\n').encode())
    return result


if __name__ == '__main__':
    print(json.dumps(accept()))
