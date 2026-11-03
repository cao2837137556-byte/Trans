"""Evidence-bound, sequential commissioning resources; no training allocation."""
import argparse
import math
from pathlib import Path
import continuous_common_v3 as c
from spill_mapping_v1 import validate_policy

SCHEMA = 'onboarding-resource-plan-v1'
PHASES = ('RAW_REFERENCE', 'E3_REFERENCE', 'HEAD_AND_MODULE')


def validate(plan):
    c.require(plan.get('schema') == SCHEMA and plan.get('status') == 'REVIEWABLE', 'ONBOARDING_RESOURCE_PLAN_REQUIRED')
    c.require(plan['processes'] == 1 and plan['threads'] == 4 and type(plan['cpus']) is int and plan['cpus'] >= 4,
              'ONBOARDING_CONCURRENCY')
    c.require(plan['concurrency_basis'] and plan['workload_identity'], 'ONBOARDING_RESOURCE_BASIS')
    c.require(set(plan['phases']) == set(PHASES), 'ONBOARDING_PHASES')
    peaks = []
    for phase in plan['phases'].values():
        c.require(phase['basis'] in ('MEASURED', 'ESTIMATED') and phase['explanation'] and phase['evidence'] and
                  phase['includes_mappings_and_temporary_buffers'] is True, 'ONBOARDING_PHASE_EVIDENCE')
        total = 0.; names = set()
        for part in phase['components']:
            value = part['gib_per_instance']
            c.require(part['name'] not in names and part['explanation'] and type(value) in (int, float) and
                      math.isfinite(value) and value > 0 and type(part['instances']) is int and part['instances'] > 0,
                      'ONBOARDING_COMPONENT')
            names.add(part['name']); total += value*part['instances']
        peak = phase['simultaneous_peak_gib']
        c.require(type(peak) in (int, float) and math.isfinite(peak) and peak == math.ceil(total*2)/2,
                  'ONBOARDING_COMPONENT_SUM')
        peaks.append(peak)
    margin = plan['margin_fraction']
    c.require(type(margin) in (int, float) and math.isfinite(margin) and .1 <= margin <= .5, 'ONBOARDING_MARGIN')
    allocation = math.ceil(max(peaks)*(1+margin)/2)*2
    c.require(type(plan['memory_gib']) is int and plan['memory_gib'] == allocation, 'ONBOARDING_ALLOCATION')
    c.require(max(peaks) < plan['guard_gib'] < allocation, 'ONBOARDING_MEMORY_GUARD')
    for field in ('disk_gib', 'minimum_free_gib', 'export_included_limit_gib', 'wall_seconds'):
        c.require(type(plan[field]) in (float, int) and math.isfinite(plan[field]) and plan[field] > 0,
                  'ONBOARDING_LIMIT:'+field)
    c.require(plan['minimum_free_gib'] >= plan['disk_gib']+plan['export_included_limit_gib']+1,
              'ONBOARDING_DISK_RESERVE')
    c.require(plan['disk_basis'] and plan['time_basis'] and plan['slurm_time'] == '1-00:00:00' and
              plan['wall_seconds'] < 86400, 'ONBOARDING_TIME_BASIS')
    validate_policy(plan['state_storage'])
    return plan


def load(path):
    path = Path(path).resolve(); plan = validate(c.read(path))
    for phase in plan['phases'].values():
        for ref in phase['evidence']:
            c.require(set(ref) == {'path', 'sha256'}, 'ONBOARDING_EVIDENCE_SCHEMA')
            target = (path.parent/ref['path']).resolve()
            c.require(target.is_relative_to(path.parent), 'ONBOARDING_EVIDENCE_ESCAPE')
            c.pin(target, ref['sha256'])
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True); parser.add_argument('--slurm-fields', action='store_true')
    args = parser.parse_args(); plan = load(args.plan)
    if args.slurm_fields:
        print('%s %s %s' % (plan['memory_gib'], plan['cpus'], c.sha(args.plan)))
    else:
        print('ONBOARDING_RESOURCE_PLAN_VALID memory=%sG cpus=%s' % (plan['memory_gib'], plan['cpus']))


if __name__ == '__main__':
    main()
