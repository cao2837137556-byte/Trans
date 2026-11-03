"""Single separately authorized launch of unchanged frozen A/B mathematics."""
import argparse
import json
import os
from pathlib import Path
import signal
import sys

REPAIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPAIR/'bootstrap'))
from repair_runtime import install, require, sha

PARENT_SHA = '6870ae7c60ecfb82e4e8c0bc8a18306cad6ee0cf62ed640a82ca254da1fa8f61'
MATRIX_SHA = '3c7d04a6a32b2a033b62bdfefc93172809eb6a7e6375b7fd7be7828a27ad1199'
SOURCE_SHA = '810f28a769f60057ed14fde968b740d87173b130c2bfb0eb192548bcf325fbb8'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def validate_repair_approval(approval, repair_sha):
    require(approval.get('repair_user_authorized') is True and
            approval.get('repair_schema') == 'paper04-dense-ab-dependency-repair-authorization-v1' and
            approval.get('repair_manifest_sha256') == repair_sha and
            approval.get('repair_evidence') and
            approval.get('replaces_failed_job') == '179680' and
            approval.get('package_sha256') == PARENT_SHA and
            approval.get('manifest_sha256') == MATRIX_SHA and
            approval.get('source_cal_result_sha256') == SOURCE_SHA and
            type(approval.get('retries')) is int and approval['retries'] == 0 and
            approval.get('automatic_retry') is False and
            approval.get('total_wall_seconds') == 7200,
            'NEW_REPAIR_PACKAGE_AND_USER_AUTHORIZATION_REQUIRED')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-package', required=True)
    parser.add_argument('--assets-root', required=True)
    parser.add_argument('--source-cal-result', required=True)
    parser.add_argument('--approval-file', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    parent = Path(args.parent_package).resolve()
    output = Path(args.output).resolve()
    require(not output.exists(), 'FRESH_REPAIR_SCIENCE_OUTPUT_REQUIRED')
    # Complete repair/parent identity and fresh repair authorization all precede
    # the original launcher, any target score load, and target asset assembly.
    sys.path.insert(0, str(parent/'src'))
    from common import verify_package
    repair_sha = verify_package(REPAIR)
    require(verify_package(parent) == PARENT_SHA, 'FROZEN_PARENT_PACKAGE_SHA')
    require(sha(parent/'config/MATRIX_CANDIDATE_HPC.json') == MATRIX_SHA,
            'FROZEN_MATRIX_MANIFEST_SHA')
    require(sha(args.source_cal_result) == SOURCE_SHA, 'FROZEN_SOURCE_CAL_RESULT_SHA')
    approval = read(args.approval_file)
    validate_repair_approval(approval, repair_sha)
    install(REPAIR)
    os.environ['PAPER04_DEPENDENCY_REPAIR'] = str(REPAIR)
    os.environ['PAPER04_REPAIR_MANIFEST_SHA256'] = repair_sha
    # The original launcher preserves this tail for its matrix subprocess.
    # sitecustomize's meta finder wins even when matrix inserts original vendor.
    os.environ['PYTHONPATH'] = os.pathsep.join((str(REPAIR/'bootstrap'),
                                               os.environ.get('PYTHONPATH', '')))
    import launch_stage
    # Original authorization also runs: the repair gate cannot weaken it.
    result = launch_stage.main([
        '--package', str(parent), '--assets-root', args.assets_root,
        '--manifest', str(parent/'config/MATRIX_CANDIDATE_HPC.json'),
        '--source-cal-result', args.source_cal_result,
        '--approval-file', args.approval_file, '--output', str(output)])
    if output.is_dir():
        (output/'DEPENDENCY_REPAIR_IDENTITY.json').write_text(json.dumps(dict(
            repair_manifest_sha256=repair_sha, parent_package_sha256=PARENT_SHA,
            matrix_manifest_sha256=MATRIX_SHA, source_result_sha256=SOURCE_SHA,
            frozen_vendor_paths={name: str(REPAIR/'vendor/ood'/(name+'.py'))
                                 for name in install(REPAIR)},
            mathematical_code_changes=0, automatic_retry=False), indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    def terminate(signum, frame):
        raise RuntimeError('TERMINATION_SIGNAL:'+str(signum))
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    sys.exit(main())
