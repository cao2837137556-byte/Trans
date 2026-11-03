"""Immutable launch repair: verify original bytes, never rewrite them."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys

ORIGINAL_MANIFEST_SHA = 'ddb94bb9836c9ace0b2a704e875d969c1d3c40c94198212ac795a9d0731db120'
ORIGINAL_FILES = 1492
ORIGINAL_LAUNCHER_SHA = '8b1db4d33924736a901627237d6d272249537aee36b4b134aa4134bce183968d'
ORIGINAL_APPROVAL_SHA = '0576a803faf1fd77ffb57fecb606e5a31aa98957b895f657c23fb152ff2c4b26'
PREVIOUS_JOB = '179523'
STAGES = ['runtime', 'encode', 'source_cal']


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4*1024**2), b''):
            result.update(block)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.tmp')
    data = (json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False)+'\n').encode()
    with temp.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def parse_manifest(raw, expected_sha, expected_files):
    """Allow exactly LF or CRLF record terminators; preserve every other byte.

    In particular, this is not strip(), splitlines(), replacement of all CRs,
    or rewriting a normalized manifest into the sealed original directory.
    """
    require(hashlib.sha256(raw).hexdigest() == expected_sha, 'RAW_MANIFEST_SHA256')
    require(raw.endswith(b'\n'), 'MANIFEST_FINAL_LF_REQUIRED')
    lines = raw.split(b'\n')[:-1]
    result, crlf = {}, 0
    for raw_line in lines:
        if raw_line.endswith(b'\r'):
            raw_line = raw_line[:-1]
            crlf += 1
        require(raw_line and b'\r' not in raw_line and b'\x00' not in raw_line, 'NON_TERMINAL_CR_OR_EMPTY_RECORD')
        line = raw_line.decode('utf-8', errors='strict')
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        require(match is not None, 'MANIFEST_RECORD_FORMAT')
        digest, name = match.groups()
        path = PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts and '\\' not in name and ':' not in name and
                str(path) == name and name not in result and name not in ('PACKAGE_SHA256SUMS','OVERLAY_SHA256SUMS'),
                'MANIFEST_PATH_OR_DUPLICATE')
        result[name] = digest
    require(len(result) == expected_files, 'MANIFEST_FILE_COUNT')
    return result, crlf


def verify(package, expected_sha, expected_files, manifest_name='PACKAGE_SHA256SUMS', *, ignored=()):
    root = Path(package).resolve()
    manifest = root/manifest_name
    original = manifest.read_bytes()
    expected, crlf = parse_manifest(original, expected_sha, expected_files)
    actual = set()
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if relative.parts[0] in ignored or '__pycache__' in relative.parts:
            continue
        require(not path.is_symlink(), 'SEALED_MEMBER_SYMLINK')
        if path.is_file() and relative.as_posix() != manifest_name:
            actual.add(relative.as_posix())
    require(actual == set(expected), 'SEALED_MEMBER_SET')
    for name, digest in expected.items():
        path = root/name
        require(path.resolve().is_relative_to(root), 'SEALED_MEMBER_ESCAPE')
        require(sha(path) == digest, 'SEALED_MEMBER_SHA256:'+name)
    require(manifest.read_bytes() == original, 'ORIGINAL_MANIFEST_CHANGED')
    return dict(status='PASS', raw_manifest_sha256=expected_sha, files_verified=len(expected),
                CRLF_records=crlf, LF_records=len(expected)-crlf,
                handling='Remove at most one terminal CR before each LF only during parsing',
                original_files_modified=False)


def approval_gate(approval, original_approval, original_approval_sha, overlay_manifest_sha):
    require(original_approval_sha == ORIGINAL_APPROVAL_SHA and original_approval.get('user_authorized') is True and
            original_approval.get('package_sha256') == ORIGINAL_MANIFEST_SHA and original_approval.get('scope') == 'DENSE_REFERENCE_V1' and
            original_approval.get('stages') == STAGES and original_approval.get('retries') == 0,
            'ORIGINAL_APPROVAL_IDENTITY')
    require(approval.get('schema') == 'dense-reference-launch-repair-approval-v1' and
            approval.get('user_authorized') is True and approval.get('scope') == 'LAUNCH_CRLF_AND_EXTERNAL_OUTPUT_REPAIR_ONLY' and
            approval.get('overlay_manifest_sha256') == overlay_manifest_sha and
            approval.get('original_manifest_sha256') == ORIGINAL_MANIFEST_SHA and
            approval.get('original_launcher_sha256') == ORIGINAL_LAUNCHER_SHA and
            approval.get('original_approval_sha256') == ORIGINAL_APPROVAL_SHA and
            approval.get('previous_failed_job_id') == PREVIOUS_JOB and approval.get('stages') == STAGES and
            type(approval.get('authorized_new_submissions')) is int and approval['authorized_new_submissions'] == 1 and
            approval.get('automatic_resubmit') is False and
            approval.get('retries') == 0 and approval.get('total_wall_seconds') == original_approval.get('total_wall_seconds') and
            bool(approval.get('evidence')), 'EXPLICIT_NEW_LAUNCH_REPAIR_AUTHORIZATION_REQUIRED')


def record(output, stage, status, exit_code=None, line=None):
    require(re.fullmatch('[A-Za-z0-9_]+', stage or '') is not None, 'LAUNCH_STAGE_FORMAT')
    require(status in ('RUNNING', 'COMPLETE', 'EXCEPTION_STOP'), 'LAUNCH_STATUS')
    why = None if status != 'EXCEPTION_STOP' else 'LAUNCH_STAGE:'+stage+':EXIT'+str(exit_code)+':LINE'+str(line)
    if status == 'COMPLETE':
        try:
            child_complete = read(Path(output)/'science/status.json').get('status') == 'COMPLETE'
        except (OSError, ValueError, AttributeError):
            child_complete = False
        if not child_complete:
            status, exit_code = 'EXCEPTION_STOP', 70
            why = 'SCIENCE_COMPLETE_RECEIPT_REQUIRED'
    value = dict(status=status, stage=stage, returncode=exit_code, failure_line=line, reason=why,
                 updated_utc=datetime.now(timezone.utc).isoformat(), retries=0, evidence_preserved=True,
                 repair_scope='LAUNCH_CRLF_AND_EXTERNAL_OUTPUT_ONLY', previous_failed_job_id=PREVIOUS_JOB)
    write(Path(output)/'launch.json', value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    gate = sub.add_parser('gate')
    gate.add_argument('--package', required=True)
    gate.add_argument('--overlay', required=True)
    gate.add_argument('--repair-approval', required=True)
    gate.add_argument('--original-approval', required=True)
    gate.add_argument('--output', required=True)
    rec = sub.add_parser('record')
    rec.add_argument('--output', required=True)
    rec.add_argument('--stage', required=True)
    rec.add_argument('--status', choices=('RUNNING','COMPLETE','EXCEPTION_STOP'), required=True)
    rec.add_argument('--exit-code', type=int)
    rec.add_argument('--line', type=int)
    args = parser.parse_args()
    if args.mode == 'record':
        result = record(args.output, args.stage, args.status, args.exit_code, args.line)
        return 70 if args.status == 'COMPLETE' and result['status'] != 'COMPLETE' else 0
    package, overlay = Path(args.package).resolve(), Path(args.overlay).resolve()
    require(not overlay.is_relative_to(package) and not package.is_relative_to(overlay), 'SEPARATE_REPAIR_OVERLAY_REQUIRED')
    approval, original_approval = read(args.repair_approval), read(args.original_approval)
    overlay_manifest_sha = sha(overlay/'OVERLAY_SHA256SUMS')
    approval_gate(approval, original_approval, sha(args.original_approval), overlay_manifest_sha)
    count = len((overlay/'OVERLAY_SHA256SUMS').read_bytes().split(b'\n'))-1
    overlay_result = verify(overlay, overlay_manifest_sha, count, 'OVERLAY_SHA256SUMS', ignored=('.private','runtime','validation'))
    require(sha(package/'hpc/run_dense.slurm') == ORIGINAL_LAUNCHER_SHA, 'ORIGINAL_LAUNCHER_IDENTITY')
    result = verify(package, ORIGINAL_MANIFEST_SHA, ORIGINAL_FILES, ignored=('.private','runtime','local_progress'))
    result.update(overlay=overlay_result, original_launcher_sha256=ORIGINAL_LAUNCHER_SHA,
                  original_approval_sha256=ORIGINAL_APPROVAL_SHA, previous_failed_job_id=PREVIOUS_JOB,
                  new_submission_authorized=True, scientific_code_changed=False)
    write(args.output, result)


if __name__ == '__main__':
    sys.exit(main())
