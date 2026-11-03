"""Preserve launch failures without confusing A/B completion with three-pool completion."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from common import read, write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--exit-code', type=int, required=True)
    parser.add_argument('--stage', required=True)
    args = parser.parse_args(argv)
    progress = Path(args.output)/'science/status.json'
    complete = (progress.exists() and read(progress).get('status') == 'COMPLETE' and
                read(progress).get('original_registered_matrix_complete') is False)
    ok = args.exit_code == 0 and complete
    write(Path(args.output)/'launch.json', dict(status='COMPLETE' if ok else 'EXCEPTION_STOP',
        stage=args.stage, returncode=args.exit_code, evaluation_scope='AB_DENSE_STAGE_PENDING_THIRD_POOL',
        original_registered_matrix_complete=False, third_pool_deferred='CIC_THREE_DEVICE_REGRESSION_CONSUMED',
        reason=None if ok else 'LAUNCH_OR_WORKER_EXIT:' + str(args.exit_code),
        retries=0, evidence_preserved=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
