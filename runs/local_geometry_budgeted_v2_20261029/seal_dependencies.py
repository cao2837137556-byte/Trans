"""One-time implementation dependency seal. Hash-only; never runs scientific code."""
from lg.common import PACKAGE, ROOT, SPEC_SHA, require, sha, write_json


def main():
    destination = PACKAGE/'DEPENDENCIES.json'
    require(not destination.exists(), 'DEPENDENCIES_ALREADY_SEALED')
    paths = [ROOT/'repo/ood'/ (name+'.py') for name in (
        'legacy_qref_common_v1','legacy_qref_data_v1','indexed_features_v1',
        'causal_reference_overlap_v1','constrained_onboarding_core_v3','onboarding_budget_v1')]
    paths += list((ROOT/'runs/phase_conditioned_calibration_v1_20261028/src').glob('*.py'))
    paths += [ROOT/path for path in (
        'runs/phase_conditioned_calibration_v1_20261028/ASSETS.json',
        'runs/source_controls_base_ctx_v1_20261026/src/training.py',
        'runs/source_controls_base_ctx_v1_20261026/src/runner.py',
        'runs/dense_reference_ab_stage_candidate_v1_20261028/preparation_r2/MATRIX_CANDIDATE_LOCAL.json')]
    require(sha(PACKAGE/'EXPERIMENT_PLAN.md') == SPEC_SHA, 'FROZEN_PLAN_CHANGED')
    write_json(destination, dict(spec_sha256=SPEC_SHA, operation='hash_only',
                                files={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths)}))


if __name__ == '__main__':
    main()
