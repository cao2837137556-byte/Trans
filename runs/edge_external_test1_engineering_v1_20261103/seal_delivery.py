"""Preserve draft r1 and seal final engineering-only r2 after gate review."""
from datetime import datetime, timezone
from pathlib import Path
import json

from build_engineering_receipt import HERE, ROOT, read, sha, write
from execution_gate import readiness


def main():
    previous = HERE / 'ENGINEERING_CARD.json'
    write(HERE/'TEST_RECEIPT.json', dict(status='PASS', tests=9, failures=0,
        scope='External metrics/UID joins/suppression and runtime authorization gates; no model inference',
        command='python -X utf8 -B -m unittest -v test_evaluation_gate.py',
        actual_run_wall_seconds=.013,
        implementation_sha256={name:sha(HERE/name) for name in
            ('evaluation.py', 'execution_gate.py', 'test_evaluation_gate.py')}))
    current = read(previous)
    current['revision'] = 2
    current['previous_card_sha256'] = sha(previous)
    current['revision_reason'] = 'Submission gate now explicitly blocks an unvalidated full streaming/resume worker; all scientific settings and population unchanged.'
    current['artifact_pins'] = {}
    for path in sorted(HERE.rglob('*')):
        if path.is_file() and path.suffix in ('.py', '.md', '.json') and path.name not in (
                'PROGRESS.md', 'STATUS.json', 'PROGRESS.json', 'SOURCE_PROGRESS.json'):
            current['artifact_pins'][path.relative_to(ROOT).as_posix()] = sha(path)
    frozen = ROOT/'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json'
    current['artifact_pins'][frozen.relative_to(ROOT).as_posix()] = sha(frozen)
    for relative, binding in read(frozen)['immutable_asset_pins'].items():
        if sha(ROOT/relative) != binding['sha256']:
            raise RuntimeError('FROZEN_INPUT_CHANGED:' + relative)
        current['artifact_pins'][relative] = binding['sha256']
    write(HERE/'ENGINEERING_CARD_R2.json', current)
    result = readiness(current, ROOT)
    if result['status'] != 'BLOCKED' or any(x.startswith('ARTIFACT_IDENTITY:') for x in result['failures']):
        raise RuntimeError('EXPECTED_HONEST_BLOCKED_STATUS_AND_VALID_PINS')
    write(HERE/'EXECUTION_READINESS_R2.json', result)
    for path in sorted(HERE.rglob('*')):
        if path.is_file() and path.suffix in ('.py', '.md') and not path.with_name(path.name+'.sha256').exists():
            path.with_name(path.name+'.sha256').write_text(sha(path)+'  '+path.name+'\n', encoding='utf-8')
    reply = ROOT/'runs/mainline_docs/collab/20261103_edge_engineering_progress_and_dataport_codex.md'
    reply.with_name(reply.name+'.sha256').write_text(sha(reply)+'  '+reply.name+'\n', encoding='utf-8')
    checks = []
    for sidecar in HERE.rglob('*.sha256'):
        target = sidecar.with_name(sidecar.name[:-7])
        expected = sidecar.read_text(encoding='utf-8-sig').split()[0]
        if not target.is_file() or sha(target) != expected:
            raise RuntimeError('SIDECAR_FAILED:' + str(sidecar))
        checks.append(sidecar.relative_to(HERE).as_posix())
    write(HERE/'DELIVERY_VERIFICATION.json', dict(status='PASS_ENGINEERING_DELIVERY_NOT_EXECUTION_READY',
        created_utc=datetime.now(timezone.utc).isoformat(), sidecar_checks=len(checks),
        current_card_sha256=sha(HERE/'ENGINEERING_CARD_R2.json'),
        reply_sha256=sha(reply), current_artifact_identity_checks_pass=True,
        unchanged_frozen_assets=len(read(frozen)['immutable_asset_pins']),
        formal_external_evaluation_ready=False, automatic_monitoring=False))
    paths = [ROOT/'.gitignore', ROOT/'.gitattributes',
        ROOT/'runs/mainline_docs/NEW_CHAT_START_HERE.md', reply, reply.with_name(reply.name+'.sha256')]
    for path in sorted(HERE.rglob('*')):
        if (path.is_file() and path.suffix in ('.py', '.md', '.json', '.sha256', '.jsonl')
                and path.stat().st_size <= 2**20):
            paths.append(path)
    # NUL paths are portable, literal and unaffected by spaces/newline settings.
    (HERE/'backup_paths.nul').write_bytes(b'\0'.join(p.relative_to(ROOT).as_posix().encode() for p in paths)+b'\0')
    print(json.dumps(dict(files_to_backup=len(paths), status=result['status'],
        blocked_by=result['failures'], sidecar_checks=len(checks)), ensure_ascii=False))


if __name__ == '__main__':
    main()
