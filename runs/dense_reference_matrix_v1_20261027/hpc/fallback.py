"""Preserve Slurm-launch failures even when the scientific child never starts."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common import read, write

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--exit-code', type=int, required=True)
    parser.add_argument('--stage', required=True)
    args = parser.parse_args()
    progress = Path(args.output) / 'science/status.json'
    complete = progress.exists() and read(progress).get('status') == 'COMPLETE'
    write(Path(args.output) / 'launch.json', dict(status='COMPLETE' if args.exit_code == 0 and complete
        else 'EXCEPTION_STOP', stage=args.stage, returncode=args.exit_code,
        reason=None if args.exit_code == 0 and complete else 'LAUNCH_OR_WORKER_EXIT:' + str(args.exit_code),
        retries=0, evidence_preserved=True))
