"""Fail closed on current-attempt, scheduler, source, fixture and resource identity."""
import json
from pathlib import Path
from checkpoint import atomic_json, require, sha
from runtime_control import current_status, attempt_directory
from real_slice_preflight import validate_candidate


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def inspect(deploy, card_path, job, scheduler):
    deploy = Path(deploy).resolve()
    require(str(job.get('job_id', '')).isdigit() and job.get('phase') == 'preflight'
            and job.get('wall_seconds') == 1800 and job.get('cpu') == 1 and job.get('memory_gib') == 8,
            'PREFLIGHT_JOB_CONTRACT')
    output = deploy/'outputs'/('preflight_'+job['job_id'])
    require(Path(job['output_directory']).resolve() == output and not output.is_symlink(), 'PREFLIGHT_OUTPUT_BINDING')
    require(job.get('card_sha256') == sha(card_path), 'PREFLIGHT_JOB_CARD')
    card = read(card_path)
    current = current_status(output, card_sha256=sha(card_path))
    require(current['status'] == 'PASS' and current.get('cleanup_complete') is True,
            'PREFLIGHT_CURRENT_PASS_AND_CLEANUP')
    resource = current['resources']
    require(0 < resource['max_tree_rss_bytes'] <= 8*1024**3
            and resource['rss_samples'] > 0, 'PREFLIGHT_WHOLE_TREE_RSS')
    candidate_path = attempt_directory(output, current['attempt_id'])/'CANDIDATE.json'
    candidate = read(candidate_path)
    require(candidate['attempt_id'] == current['attempt_id'], 'PREFLIGHT_CANDIDATE_ATTEMPT')
    validate_candidate(candidate, sha(card_path), card['runtime_identity'])
    rows = [line.split('|') for line in scheduler['stdout'].splitlines()]
    primary = [row for row in rows if len(row) >= 8 and row[0] == job['job_id']]
    require(scheduler['returncode'] == 0 and len(primary) == 1 and primary[0][1] == 'COMPLETED'
            and primary[0][2] == '0:0' and primary[0][5] == '1'
            and primary[0][6] in ('8G', '8Gn', '8192M', '8192Mn')
            and primary[0][7] in ('00:30:00', '30:00'), 'PREFLIGHT_SCHEDULER_CONTRACT')
    files = [output/'CURRENT_ENGINEERING_ATTEMPT.json', candidate_path,
             attempt_directory(output, current['attempt_id'])/'PASS.json']
    return dict(status='PASS', scope='V3_REAL_SLICE_PRECONDITION', card_sha256=sha(card_path),
        job=job, scheduler=scheduler, attempt_id=current['attempt_id'],
        files={p.relative_to(deploy).as_posix(): sha(p) for p in files},
        slice_sha256=candidate['slice_sha256'], runtime_identity=candidate['runtime_identity'],
        logical_rows=78, resources=resource, cleanup_complete=True,
        full_gate_started=False, formal_evaluation_authorized=True)


def validate_saved(deploy, card_path):
    deploy = Path(deploy)
    value = read(deploy/'PREFLIGHT_ACCEPTANCE.json')
    expected = inspect(deploy, card_path, value['job'], value['scheduler'])
    require(value == expected, 'PREFLIGHT_ACCEPTANCE_IMMUTABLE_BINDING')
    return value


def accept(deploy, card_path, job, scheduler):
    target = Path(deploy)/'PREFLIGHT_ACCEPTANCE.json'
    value = inspect(deploy, card_path, job, scheduler)
    if target.exists():
        require(read(target) == value, 'PREFLIGHT_ACCEPTANCE_CHANGED')
    else:
        atomic_json(target, value)
    return value
