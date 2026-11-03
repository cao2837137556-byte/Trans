"""Evidence-bound budgets for cache-only reconstruction; no default RAM target."""
import argparse
import math
from pathlib import Path
import continuous_common_v3 as c
from spill_mapping_v1 import validate_policy

SCHEMA = 'continuous-frontend-resource-plan-v1'
PHASES = ('P_DECODE_AND_PROBE', 'E3_WORKERS', 'MERGE_NORMALIZE')


def positive(value, name):
    c.require(type(value) in (float, int) and math.isfinite(value) and value > 0, name)
    return float(value)


def validate(plan):
    c.require(plan.get('schema') == SCHEMA and plan.get('status') == 'REVIEWABLE', 'FRONTEND_RESOURCE_PLAN_PENDING')
    workers = plan['feature_workers']
    c.require(type(workers) is int and workers >= 1 and type(plan['threads_per_worker']) is int and plan['threads_per_worker'] == 4,
              'FRONTEND_PARALLELISM')
    c.require(type(plan['cpus']) is int and plan['cpus'] >= workers*4, 'FRONTEND_CPUS')
    c.require(bool(plan['concurrency_basis']) and set(plan['workload_identity']) ==
              {'design_sha256', 'runtime_sha256', 'package_seal_sha256'}, 'FRONTEND_WORKLOAD')
    c.require(set(plan['phases']) == set(PHASES), 'FRONTEND_PHASES')
    margin = positive(plan['margin_fraction'], 'FRONTEND_MARGIN')
    c.require(.1 <= margin <= .5, 'FRONTEND_MARGIN')
    peaks = []
    for name in PHASES:
        phase = plan['phases'][name]
        c.require(phase['basis'] in ('MEASURED', 'ESTIMATED') and phase['explanation'] and phase['evidence'],
                  'FRONTEND_PHASE_EVIDENCE')
        c.require(phase['includes_mappings_and_temporary_buffers'] is True, 'FRONTEND_BUFFERS')
        total = 0.; labels = set()
        for component in phase['components']:
            c.require(component['name'] and component['name'] not in labels and component['explanation'],
                      'FRONTEND_COMPONENT')
            labels.add(component['name'])
            c.require(type(component['instances']) is int and component['instances'] >= 1, 'FRONTEND_INSTANCES')
            total += positive(component['gib_per_instance'], 'FRONTEND_COMPONENT_GIB')*component['instances']
        peak = positive(phase['simultaneous_peak_gib'], 'FRONTEND_PEAK')
        c.require(math.isclose(total, peak, rel_tol=1e-12, abs_tol=1e-12), 'FRONTEND_COMPONENT_SUM')
        if name == 'E3_WORKERS':
            by_name = {x['name']: x for x in phase['components']}
            c.require('parent_and_shared' in by_name and by_name['parent_and_shared']['instances'] == 1 and
                      'worker_private' in by_name and by_name['worker_private']['instances'] == workers,
                      'FRONTEND_E3_CONCURRENCY')
        peaks.append(peak)
    # These phases are sequential; reserve is applied once, not to their sum.
    peak = max(peaks); allocation = math.ceil(peak*(1+margin)/2)*2
    c.require(type(plan['memory_gib']) is int and plan['memory_gib'] == allocation, 'FRONTEND_ALLOCATION')
    guard = positive(plan['guard_gib'], 'FRONTEND_GUARD')
    worker_guard = positive(plan['worker_guard_gib'], 'FRONTEND_WORKER_GUARD')
    c.require(peak < guard < allocation and worker_guard*workers <= guard, 'FRONTEND_GUARD_HEADROOM')
    worker_component = next(x for x in plan['phases']['E3_WORKERS']['components'] if x['name']=='worker_private')
    c.require(worker_guard > worker_component['gib_per_instance'], 'FRONTEND_WORKER_GUARD_BELOW_PEAK')
    positive(plan['minimum_free_gib'], 'FRONTEND_FREE_DISK')
    positive(plan['disk_gib'], 'FRONTEND_DISK')
    positive(plan['worker_disk_gib'], 'FRONTEND_WORKER_DISK')
    c.require(plan['disk_gib'] <= plan['minimum_free_gib'] and plan['disk_basis'], 'FRONTEND_DISK_BASIS')
    positive(plan['post_features_reserve_seconds'], 'FRONTEND_MERGE_TIME_RESERVE')
    c.require(plan['post_features_reserve_basis'], 'FRONTEND_MERGE_TIME_BASIS')
    validate_policy(plan['state_storage'])
    return plan


def load(path):
    path = Path(path).resolve(); plan = validate(c.read(path))
    for phase in plan['phases'].values():
        for asset in phase['evidence']:
            c.require(set(asset) == {'path', 'sha256'}, 'FRONTEND_EVIDENCE_SCHEMA')
            target = (path.parent/asset['path']).resolve()
            c.require(target.is_relative_to(path.parent), 'FRONTEND_EVIDENCE_ESCAPE')
            c.pin(target, asset['sha256'])
    return plan


def runtime(base, plan):
    result = dict(base, version='continuous-frontend-engineering-v1-20261017',
                  feature_workers=plan['feature_workers'], cpus=plan['cpus'], threads_per_worker=4,
                  state_storage=dict(plan['state_storage']), minimum_free_gib=plan['minimum_free_gib'],
                  post_features_reserve_seconds=plan['post_features_reserve_seconds'])
    result['limits'] = dict(base['limits'], memory_gib=plan['guard_gib'], disk_gib=plan['disk_gib'])
    result['worker_limits'] = dict(base['worker_limits'], memory_gib=plan['worker_guard_gib'], disk_gib=plan['worker_disk_gib'])
    result['slurm'] = dict(base['slurm'], cpus=plan['cpus'], memory=str(plan['memory_gib'])+'G')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True); parser.add_argument('--slurm-fields', action='store_true')
    args = parser.parse_args(); plan = load(args.plan)
    if args.slurm_fields:
        print('%s %s %s' % (plan['memory_gib'], plan['cpus'], c.sha(args.plan)))
    else:
        print('FRONTEND_RESOURCE_PLAN_VALID memory=%sG cpus=%s workers=%s' %
              (plan['memory_gib'], plan['cpus'], plan['feature_workers']))


if __name__ == '__main__': main()
