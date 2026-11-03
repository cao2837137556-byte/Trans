"""One bounded, read-only SSH collection; never launches experiment code."""
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess


REMOTE = r'''
import base64, datetime, hashlib, json
from collections import defaultdict
from pathlib import Path

root = Path('/srv/paper04/learned_onboarding_20261024_v4')
results = root/'runs/learned_onboarding_v1_20261023/results'
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def verify_seal(folder):
    seal = folder/'SEAL.json'
    if not seal.is_file():
        return dict(status='MISSING_SEAL')
    value = json.loads(seal.read_text(encoding='utf-8-sig'))
    failures = []
    checked_bytes = 0
    for name, expected in value['files'].items():
        p = (folder/name).resolve()
        if folder.resolve() not in p.parents:
            failures.append(dict(path=name, reason='PATH_ESCAPE'))
        elif not p.is_file():
            failures.append(dict(path=name, reason='MISSING'))
        else:
            checked_bytes += p.stat().st_size
            if sha(p) != expected:
                failures.append(dict(path=name, reason='SHA256_MISMATCH'))
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*')
              if p.is_file() and p.name != 'SEAL.json'}
    expected = set(value['files'])
    return dict(status='PASS' if not failures and actual == expected else 'FAIL',
                seal_status=value.get('status'), spec_sha256=value.get('spec_sha256'),
                seal_sha256=sha(seal), checked_files=len(value['files']),
                checked_bytes=checked_bytes, failures=failures,
                extra=sorted(actual-expected), missing=sorted(expected-actual))

size_by_dir = defaultdict(int)
all_files = []
for p in results.rglob('*'):
    if p.is_file():
        rel = p.relative_to(results)
        n = p.stat().st_size
        size_by_dir[rel.parts[0]] += n
        all_files.append(dict(path=rel.as_posix(), bytes=n))

relative_names = [
    'fit/FIT_COMPLETE.json', 'fit/SEAL.json', 'fit/source_signal.json',
    'fit/runtime.json', 'fit/implementation_code.json',
    'calibration/calibration.json', 'calibration/SEAL.json',
    'calibration/source_cut_replay.json', 'calibration/runtime.json',
    'calibration/input_binding.json', 'calibration/status.json',
    'preflight/resource_plan.json',
]
for name in ('AUX_G0', 'AUX_G1', 'L_STANDARD', 'L_HARD', 'L_QUERY_ONLY'):
    for file in ('endpoint.json', 'replay.json', 'SEAL.json'):
        relative_names.append('fit/'+name+'/'+file)
for p in sorted((results/'evaluation').rglob('summary.json')):
    relative_names.append(p.relative_to(results).as_posix())
for name in ('CIC_DEV_base_replay.json', 'UNSW_DEV_base_replay.json', 'status.json'):
    relative_names.append('evaluation/'+name)

selected = [results/name for name in relative_names if (results/name).is_file()]
total = sum(p.stat().st_size for p in selected)
if total > 6*1024*1024 or any(p.stat().st_size > 128*1024 for p in selected):
    raise RuntimeError('READ_ONLY_EVIDENCE_TRANSFER_BUDGET')
payload = []
for p in selected:
    body = p.read_bytes()
    payload.append(dict(path=p.relative_to(results).as_posix(), bytes=len(body),
                        sha256=hashlib.sha256(body).hexdigest(),
                        body_base64=base64.b64encode(body).decode('ascii')))

folders = ['fit', 'calibration'] + ['fit/'+x for x in
    ('AUX_G0', 'AUX_G1', 'L_STANDARD', 'L_HARD', 'L_QUERY_ONLY')]
out = dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
           read_only=True, root=str(root), results=str(results),
           results_bytes_by_directory=dict(size_by_dir),
           all_results_files=sorted(all_files, key=lambda x: x['path']),
           seals={name: verify_seal(results/name) for name in folders},
           final_markers={name: (results/'evaluation'/name).is_file() for name in
                          ('SEAL.json','paired_summary.json','EVALUATION_COMPLETE.json')},
           selected_transfer_bytes=total, files=payload)
print(json.dumps(out, ensure_ascii=False))
'''


def main():
    folder = Path(__file__).resolve().parent
    encoded = base64.b64encode(REMOTE.encode('utf-8')).decode('ascii')
    remote_command = (
        "/opt/paper04-venv/bin/python -B -c \"import base64;"
        "exec(base64.b64decode('" + encoded + "'))\""
    )
    started = datetime.datetime.now().astimezone()
    stamp = started.strftime('%Y%m%d_%H%M%S')
    result = subprocess.run(
        ['ssh', '-nT', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=12',
         '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
         'paper04-coupon-20261020', remote_command],
        stdin=subprocess.DEVNULL, capture_output=True, encoding='utf-8',
        timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    receipt = dict(started_at=started.isoformat(),
                   ended_at=datetime.datetime.now().astimezone().isoformat(),
                   read_only=True, remote_mutations=False,
                   automatic_retry=False, returncode=result.returncode,
                   stdout_bytes=len(result.stdout.encode('utf-8')), stderr=result.stderr)
    receipt_path = folder/('ARTIFACT_CHECK_'+stamp+'.json')
    if result.returncode:
        receipt['stdout'] = result.stdout
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        raise SystemExit('SSH_READ_ONLY_CHECK_FAILED: '+str(receipt_path))
    data = json.loads(result.stdout)
    destination = folder/('artifact_evidence_'+stamp)
    destination.mkdir()
    for item in data.pop('files'):
        body = base64.b64decode(item.pop('body_base64'), validate=True)
        assert len(body) == item['bytes']
        assert hashlib.sha256(body).hexdigest() == item['sha256']
        target = (destination/item['path']).resolve()
        assert destination.resolve() in target.parents
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        data.setdefault('downloaded_files', []).append(item)
    manifest = destination/'EVIDENCE_MANIFEST.json'
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    receipt.update(local_evidence=str(destination), manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                   transferred_files=len(data['downloaded_files']),
                   transferred_payload_bytes=data['selected_transfer_bytes'], local_sha256_verified=True)
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps({k: data[k] for k in ('seals','results_bytes_by_directory','final_markers')}, indent=2))


if __name__ == '__main__':
    main()
