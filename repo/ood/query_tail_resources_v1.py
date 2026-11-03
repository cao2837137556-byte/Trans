"""Evidence-based per-stage budgets; no fixed small/large RAM target."""
import argparse
import math
from pathlib import Path
import continuous_common_v3 as c

SCHEMA = 'query-tail-resource-plan-v1'
PHASES = ('P_PREPARATION', 'T_TRAINING', 'K_EVALUATION')


def validate(plan):
    c.require(plan.get('schema') == SCHEMA and plan.get('status') == 'REVIEWABLE', 'RESOURCE_PLAN_REQUIRED')
    c.require(type(plan['train_workers']) is int and 1 <= plan['train_workers'] <= 3 and
              type(plan['threads_per_worker']) is int and plan['threads_per_worker'] == 4, 'RESOURCE_PARALLELISM')
    c.require(type(plan['cpus']) is int and plan['cpus'] >= 4*plan['train_workers'], 'RESOURCE_CPUS')
    c.require(bool(plan.get('concurrency_basis')) and bool(plan.get('workload_identity')), 'RESOURCE_BASIS')
    c.require(set(plan['phases']) == set(PHASES), 'RESOURCE_PHASES')
    c.require(type(plan['margin_fraction']) in (float, int) and
              math.isfinite(plan['margin_fraction']) and 0.1 <= plan['margin_fraction'] <= .5, 'RESOURCE_MARGIN')
    peaks = []
    for name in PHASES:
        phase = plan['phases'][name]
        value = phase['simultaneous_peak_gib']
        c.require(type(value) in (int, float) and math.isfinite(value) and value > 0, 'RESOURCE_PEAK')
        c.require(phase['basis'] in ('MEASURED', 'ESTIMATED') and bool(phase['explanation']) and
                  bool(phase['evidence']), 'RESOURCE_PHASE_BASIS')
        c.require(phase['includes_mappings_and_temporary_buffers'] is True, 'RESOURCE_MISSING_BUFFERS')
        peaks.append(float(value))
    # Sequential P/T/K do not coexist. Apply one explicit reserve once.
    peak = max(peaks); allocation = math.ceil(peak*(1+plan['margin_fraction'])/2)*2
    c.require(type(plan['memory_gib']) is int and plan['memory_gib'] == allocation, 'RESOURCE_ALLOCATION_DERIVATION')
    c.require(all(type(plan[field]) in (float, int) and math.isfinite(plan[field])
                  for field in ('guard_gib', 'worker_guard_gib')), 'RESOURCE_GUARD_TYPE')
    c.require(peak < plan['guard_gib'] < allocation, 'RESOURCE_GUARD_HEADROOM')
    c.require(0 < plan['worker_guard_gib'] <= plan['guard_gib'], 'RESOURCE_WORKER_GUARD')
    c.require(plan['worker_guard_gib']*plan['train_workers'] <= plan['guard_gib'], 'RESOURCE_CONCURRENT_GUARDS')
    return plan


def load(path):
    path = Path(path).resolve(); plan = validate(c.read(path))
    for phase in plan['phases'].values():
        for asset in phase['evidence']:
            c.require(set(asset) == {'path', 'sha256'}, 'RESOURCE_EVIDENCE_SCHEMA')
            target = (path.parent/asset['path']).resolve()
            c.require(target.is_relative_to(path.parent), 'RESOURCE_EVIDENCE_ESCAPE')
            c.pin(target, asset['sha256'])
    return plan


def runtime(base, plan):
    result = dict(base); result['version'] = 'query-tail-engineering-v2r2-20261016'
    result['cpus'] = plan['cpus']; result['train_workers'] = plan['train_workers']
    result['limits'] = dict(base['limits'], memory_gib=plan['guard_gib'])
    result['worker_limits'] = dict(base['worker_limits'], memory_gib=plan['worker_guard_gib'])
    result['slurm'] = dict(base['slurm'], cpus=plan['cpus'], memory=str(plan['memory_gib'])+'G')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--slurm-fields', action='store_true'); args = parser.parse_args()
    plan = load(args.plan)
    if args.slurm_fields:
        print('%s %s %s' % (plan['memory_gib'], plan['cpus'], c.sha(args.plan)))
    else:
        print('RESOURCE_PLAN_VALID memory=%sG cpus=%s workers=%s' %
              (plan['memory_gib'], plan['cpus'], plan['train_workers']))


if __name__ == '__main__': main()
