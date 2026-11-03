"""Turn a pre-model header-only frame plan into a pinned E2E input card."""
import argparse
from pathlib import Path

from engine import read, require, sha
from run_preflight import write


def freeze(plan_path, output):
    plan_path, output = Path(plan_path).resolve(), Path(output).resolve()
    require(not output.exists(), 'SLICE_CARD_ALREADY_EXISTS')
    plan = read(plan_path)
    require(plan['status'] == 'FIXED_HEADER_ONLY_ENGINEERING_SLICE', 'HEADER_ONLY_PLAN')
    require(plan['model_evaluations'] == plan['features_generated'] == plan['distance_pairs'] == 0,
            'PLAN_MUST_PRECEDE_MODEL_EXECUTION')
    slices = []
    for role in ('NORMAL', 'HTTP', 'UDP'):
        item = plan[role]
        refs = item.get('reference_frames', [])
        frames = sorted(set(item['query_frames']) | set(refs))
        require(len(frames) == len(item['query_frames']) + len(refs), 'SLICE_ROLE_OVERLAP')
        slices.append(dict(role=role, frames=frames, reference_frames=refs))
    require(sum(len(item['frames']) for item in slices) <= 100, 'SLICE_ROW_CAP')
    write(output, dict(mode='FIXED_HEADER_ONLY_ENGINEERING_SLICE',
        plan_path=str(plan_path), plan_sha256=sha(plan_path), slices=slices,
        frame_semantics='Original physical frame; complete original prefixes replayed unfiltered',
        reference_fixture='Small legal deterministic subset for interface only, not official bank',
        no_external_performance_selection=True, no_individual_decisions_or_quality_export=True))
    output.with_name(output.name + '.sha256').write_text(sha(output) + '  ' + output.name + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    freeze(args.plan, args.output)
