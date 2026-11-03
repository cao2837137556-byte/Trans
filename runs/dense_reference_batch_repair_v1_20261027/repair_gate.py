"""Verify immutable inputs and the new repair contract; standard library only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

ORIGINAL_SHA = 'ddb94bb9836c9ace0b2a704e875d969c1d3c40c94198212ac795a9d0731db120'
ORIGINAL_FILES = 1492
STAGES = ['runtime', 'encode', 'source_cal']
SCOPE = 'DENSE_REFERENCE_SINGLETON_BATCH_REPAIR_PREFIX_ONLY'
LIMITS = dict(slurm_cpus=4, slurm_memory_gib=16, total_wall_seconds=43200,
              tree_rss_gib=8, min_free_gib=12, retries=0)


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024**2), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)+'\n').encode()
    if exclusive:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        return
    temporary = path.with_name(path.name+'.tmp')
    with temporary.open('wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def verify_tree(root, manifest_name, expected_sha=None, expected_count=None, ignored=()):
    root = Path(root).resolve()
    raw = (root/manifest_name).read_bytes()
    require(expected_sha is None or hashlib.sha256(raw).hexdigest()==expected_sha, 'MANIFEST_SHA')
    require(raw.endswith(b'\n'), 'MANIFEST_FINAL_LF')
    entries = {}
    for line in raw.split(b'\n')[:-1]:
        if line.endswith(b'\r'):
            line = line[:-1]
        require(b'\r' not in line and b'\x00' not in line, 'MANIFEST_RECORD_BYTES')
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line.decode('utf-8'))
        require(match is not None, 'MANIFEST_RECORD')
        checksum, relative = match.groups()
        path = PurePosixPath(relative)
        require(not path.is_absolute() and '..' not in path.parts and '\\' not in relative and ':' not in relative
                and str(path)==relative and relative not in entries and relative!=manifest_name, 'MANIFEST_PATH')
        entries[relative] = checksum
    require(expected_count is None or len(entries)==expected_count, 'MANIFEST_MEMBER_COUNT')
    actual = set()
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if relative.parts[0] in ignored or '__pycache__' in relative.parts:
            continue
        require(not path.is_symlink(), 'SEALED_SYMLINK')
        if path.is_file() and relative.as_posix()!=manifest_name:
            actual.add(relative.as_posix())
    require(actual==set(entries), 'SEALED_MEMBER_SET')
    for relative, checksum in entries.items():
        require(sha(root/relative)==checksum, 'SEALED_MEMBER_SHA:'+relative)
    return dict(manifest_sha256=hashlib.sha256(raw).hexdigest(), files=len(entries))


def verify_inputs(original, overlay):
    original, overlay = Path(original).resolve(), Path(overlay).resolve()
    require(not original.is_relative_to(overlay) and not overlay.is_relative_to(original), 'SEPARATE_OVERLAY_REQUIRED')
    repair = verify_tree(overlay, 'OVERLAY_SHA256SUMS', ignored=('.private','runtime','validation','distribution'))
    frozen = verify_tree(original, 'PACKAGE_SHA256SUMS', ORIGINAL_SHA, ORIGINAL_FILES,
                         ignored=('.private','runtime','local_progress'))
    manifest = read(overlay/'REPAIR_MANIFEST.json')
    require(manifest.get('schema')=='paper04-dense-singleton-batch-repair-v1' and
            manifest.get('original_manifest_sha256')==ORIGINAL_SHA and manifest.get('stages')==STAGES and
            manifest.get('limits')==LIMITS and manifest.get('matrix') is False and
            manifest.get('automatic_retry') is False and manifest.get('real_execution_authorized') is False,
            'FROZEN_REPAIR_CONTRACT')
    require(sha(overlay/'ENCODER_PHYSICAL_BUDGET.json')==manifest['budget_sha256'], 'BUDGET_IDENTITY')
    require(set(manifest['original_entrypoints'])=={'src/chain.py','src/source_cal.py','src/supervisor.py',
            'vendor/encoding_v2/repo/ood/onboarding_supplement_encoder_r2.py'}, 'ORIGINAL_ENTRYPOINT_SET')
    for relative, checksum in manifest['original_entrypoints'].items():
        require(relative in ('src/chain.py','src/source_cal.py','src/supervisor.py',
            'vendor/encoding_v2/repo/ood/onboarding_supplement_encoder_r2.py') and sha(original/relative)==checksum,
            'ORIGINAL_ENTRYPOINT_IDENTITY')
    return dict(status='DRY_RUN_PASS', original=frozen, overlay=repair,
        budget_sha256=manifest['budget_sha256'], source_cal=True, target_evaluation=False,
        real_forwards=0, checkpoint_loads=0, remote_submissions=0)


def authorize(value, overlay, proof):
    manifest = read(Path(overlay)/'REPAIR_MANIFEST.json')
    budget = read(Path(overlay)/'ENCODER_PHYSICAL_BUDGET.json')
    require(value.get('schema')=='paper04-dense-singleton-batch-repair-approval-v1' and
            value.get('user_authorized') is True and value.get('scope')==SCOPE and
            value.get('overlay_manifest_sha256')==proof['overlay']['manifest_sha256'] and
            value.get('original_manifest_sha256')==ORIGINAL_SHA and
            value.get('budget_sha256')==manifest['budget_sha256'] and value.get('stages')==STAGES and
            value.get('limits')==LIMITS and value.get('authorized_new_submissions')==1 and
            type(value.get('authorized_new_submissions')) is int and
            value.get('automatic_retry') is False and value.get('target_evaluation') is False and
            value.get('optimizer_updates')==0 and bool(value.get('evidence')), 'NEW_SCOPED_EXECUTION_APPROVAL_REQUIRED')
    return budget


def record(output, stage, status, returncode=None, line=None):
    require(re.fullmatch('[A-Za-z0-9_]+', stage or '') is not None, 'LAUNCH_STAGE')
    require(status in ('RUNNING','COMPLETE','EXCEPTION_STOP'), 'LAUNCH_STATUS')
    if status=='COMPLETE':
        try:
            complete = read(Path(output)/'science/status.json').get('status')=='COMPLETE'
        except (OSError, ValueError, AttributeError):
            complete = False
        if not complete:
            status, returncode = 'EXCEPTION_STOP', 70
    value = dict(status=status, stage=stage, returncode=returncode, failure_line=line,
        reason=None if status!='EXCEPTION_STOP' else 'LAUNCH_STAGE:'+stage+':EXIT'+str(returncode)+':LINE'+str(line),
        retries=0, evidence_preserved=True, automatic_retry=False,
        repair_scope=SCOPE, updated_utc=datetime.now(timezone.utc).isoformat())
    write(Path(output)/'launch.json', value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    gate = sub.add_parser('verify')
    gate.add_argument('--original', required=True)
    gate.add_argument('--overlay', default=str(Path(__file__).resolve().parent))
    gate.add_argument('--output')
    gate.add_argument('--approval-file')
    rec = sub.add_parser('record')
    rec.add_argument('--output', required=True)
    rec.add_argument('--stage', required=True)
    rec.add_argument('--status', required=True)
    rec.add_argument('--returncode', type=int)
    rec.add_argument('--line', type=int)
    args = parser.parse_args()
    if args.mode=='record':
        result = record(args.output, args.stage, args.status, args.returncode, args.line)
        return 70 if args.status=='COMPLETE' and result['status']!='COMPLETE' else 0
    result = verify_inputs(args.original, args.overlay)
    if args.approval_file:
        authorize(read(args.approval_file), args.overlay, result)
        result['new_scoped_execution_authorization'] = 'PASS'
    if args.output:
        write(args.output, result)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
