"""Prepared single sbatch transaction. Unknown submission outcomes never retry."""
from datetime import datetime, timezone
import json
import re
import subprocess
import remote_preflight as preflight

HERE = preflight.HERE
PACKAGE = preflight.PACKAGE
SBATCH = '/usr/local/slurm-25.11.0-build/bin/sbatch'
OUTPUT = PACKAGE / 'outputs/c1_once_20261031'
LOCK = HERE / 'SUBMISSION_LOCK.json'
RECEIPT = HERE / 'SUBMISSION_RECEIPT.json'


def submit(runner=None):
    runner = subprocess.run if runner is None else runner
    accepted = preflight.read(preflight.RESULT)
    preflight.require(accepted.get('status') == 'PASS' and
                      accepted.get('input_readiness') == 'READY' and
                      accepted.get('synthetic_tests_passed') == 56, 'SUCCESSFUL_PREFLIGHT_REQUIRED')
    seals = preflight.current_seals()
    preflight.require(seals == accepted.get('seals'), 'PREFLIGHT_SEALS_CHANGED')
    preflight.require(not OUTPUT.exists() and not (PACKAGE/'EXECUTION_ATTEMPT.json').exists(),
                      'SCIENTIFIC_ATTEMPT_ALREADY_EXISTS')
    preflight.require(not RECEIPT.exists(), 'SUBMISSION_RECEIPT_ALREADY_EXISTS')
    preflight_sha = preflight.sha(preflight.RESULT)
    command = [SBATCH, '--parsable', '--no-requeue', '--nodes=1', '--ntasks=1',
               '--cpus-per-task=4', '--mem=16G', '--time=08:00:00',
               '--export=ALL,PAPER04_MAIN_PYTHON=' + str(preflight.PYTHON) +
               ',HNR_RUNTIME_CONFIG=' + str(PACKAGE/'config/EXECUTION.json') +
               ',HNR_OUTPUT=' + str(OUTPUT), str(PACKAGE/'hpc/run_history.slurm')]
    lock = dict(status='SUBMISSION_OUTCOME_UNKNOWN', automatic_retry=False, command=command,
                preflight_result_sha256=preflight_sha, seals=seals,
                started_utc=datetime.now(timezone.utc).isoformat())
    # Exclusive and fsynced before contacting sbatch; never clear this lock.
    preflight.write(LOCK, lock, exclusive=True)
    result = dict(lock, job_id=None)
    try:
        completed = runner(command, capture_output=True, text=True, timeout=60, check=False)
        (HERE/'sbatch.stdout.log').write_text(completed.stdout or '', encoding='utf-8')
        (HERE/'sbatch.stderr.log').write_text(completed.stderr or '', encoding='utf-8')
        result.update(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
        match = re.fullmatch(r'([0-9]+)(?:;[^\s]+)?\s*', completed.stdout or '')
        if completed.returncode == 0 and match:
            result.update(status='SUBMITTED', job_id=match.group(1))
        else:
            result.update(status='SUBMISSION_OUTCOME_UNKNOWN',
                          reason='sbatch failed or returned an unrecognized receipt; do not retry')
    except BaseException as exc:
        result.update(status='SUBMISSION_OUTCOME_UNKNOWN', error_type=type(exc).__name__, error=str(exc))
        if getattr(exc, 'stdout', None):
            (HERE/'sbatch.stdout.log').write_text(str(exc.stdout), encoding='utf-8')
        if getattr(exc, 'stderr', None):
            (HERE/'sbatch.stderr.log').write_text(str(exc.stderr), encoding='utf-8')
    result['finished_utc'] = datetime.now(timezone.utc).isoformat()
    preflight.write(RECEIPT, result, exclusive=True)
    return result


if __name__ == '__main__':
    result = submit()
    print(json.dumps(dict(status=result['status'], job_id=result['job_id'], automatic_retry=False)))
    raise SystemExit(0 if result['status'] == 'SUBMITTED' else 2)
