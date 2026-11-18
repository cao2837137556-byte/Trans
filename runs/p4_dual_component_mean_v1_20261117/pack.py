"""Freeze the experiment against the accepted table 9 controls and package executable sources."""
from hashlib import sha256
import gzip
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent
PREV = RUNS/'unified_reference_bank_k8192_v1_20261113'
RECAL = RUNS/'same_information_recalibration_v1_20261113'
ACCEPT = RUNS/'p4_tabm_acceptance_v1_20261111/controls'
DOC = RUNS/'mainline_docs/collab/20261117_paper04_v12_dual_component_mean_support_handoff_codex.md'
PRIVATE = HERE/'.private'
RUNTIME_MANIFEST_SHA = 'c7f659b3c6e77f554bb72e08ecc0acaa4f28895f197f1dd2b43fc8a074e8bce4'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def normalized(path):
    return path.read_bytes().replace(b'\r\n', b'\n')


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False)+'\n').encode()


def digest(data):
    return sha256(data).hexdigest()


def freeze():
    from reports import POOLS
    cfg = read(RECAL/'CONFIG.json')
    geometry = read(RUNS/'same_bank_context_v6_20261106/DIAGNOSE_RESULT.json')['pools']
    physical = read(RUNS/'context_geometry_attribution_v2_20261106/DIAGNOSE_RESULT.json')['pools']['EDGE']['physical_artifact']
    old_manifest = HERE/'RUNTIME_PACKAGE_MANIFEST.json'
    assert digest(normalized(old_manifest)) == RUNTIME_MANIFEST_SHA
    previous = read(old_manifest)['files']
    query, banks = read(ACCEPT/'QUERY_ASSETS.json'), read(ACCEPT/'REFERENCE_BANKS.json')
    completion = read(ACCEPT/'COMPLETE.json')['outputs_sha256']
    for name in ('METRICS.json','QUERY_ASSETS.json','REFERENCE_BANKS.json'):
        assert digest(normalized(ACCEPT/name)) == completion[name]
    original = [r for r in read(ACCEPT/'METRICS.json') if r['config'] in ('RAW','P4_MAIN')]
    assert original == read(RECAL/'EXPECTED_BASELINE.json')
    assert previous['EXPECTED_BASELINE.json'] == digest(normalized(RECAL/'EXPECTED_BASELINE.json'))
    assert previous['CONFIG.json'] == digest(normalized(RECAL/'CONFIG.json'))
    assert previous['GEOMETRY.json'] == digest(normalized(RUNS/'reference_evidence_round1_v1_20261112/CONFIG.json'))
    assert cfg['query'] == query and cfg['reference'] == banks
    method = read(RUNS/'p4_complete_bank_v1_20261111/P4_METHOD.json')
    assert method['variant_key'] == 'P4_MAIN' and method['correction']['scales'] == cfg['method']['scales']
    head_pins = read(RECAL/'INPUT_PINS.json')['inputs']
    additional = {}
    for h in cfg['method']['heads'][:3]:
        p = head_pins['head_'+h]
        assert p['sha256'] == method['heads'][h]['head_sha256']
        additional['head_'+h] = dict(group='reference', paths=p['remote'], sha256=p['sha256'], bytes=None)
    def pin(name, folder, a):
        additional[name] = dict(group='query', sha256=a['sha256'],bytes=a['bytes'],
                                paths=['runs/'+folder+'/'+a['file']])
    pin('EDGE:query_physical', 'context_geometry_attribution_v2_20261106', physical)
    for pool in POOLS:
        g = geometry[pool]
        assert dict(rows=g['reference_rows'], uid_sha256=g['reference_uid_sha256']) == banks[pool]['full_bank']
        pin(pool+':accepted_geometry','same_bank_context_v6_20261106',g['artifact'])
    meta = read(RUNS/(PREV.name+'_uidfix_184105')/'RECOVERY_INPUTS.json')['contexts']
    reads = read(RECAL/'received/results/QUERY_EVALUATION.json')['pools']
    return dict(run=HERE.name, protocol_sha256=digest(normalized(DOC)), source_controls_sha256=completion['METRICS.json'],
        method=cfg['method'], reference=banks,query=query,query_uid_sha256={p:reads[p]['query_uid_sha256'] for p in POOLS},
        additional_pins=additional,metadata_sha={p:m['uid_sha256'] for p,m in meta.items()},
        runtime_package='runs/'+PREV.name+'_early_183987/package',runtime_manifest_sha256=RUNTIME_MANIFEST_SHA)


def build():
    PRIVATE.mkdir(exist_ok=True)
    files = {n:normalized(HERE/n) for n in ('launch.py','worker.py','geometry.py','inputs.py',
                                             'boundary_checks.py','reports.py','run.slurm')}
    files['common_round1.py'] = normalized(RECAL/'common_round1.py')
    files['FROZEN.json'] = json_bytes(freeze())
    files['protocol.md'] = normalized(DOC)
    for n, data in files.items():
        if n.endswith('.py'):
            compile(data,n,'exec')
    manifest = dict(run=HERE.name,files={n:digest(v) for n,v in sorted(files.items())})
    files['PACKAGE_MANIFEST.json'] = json_bytes(manifest)
    for n in ('FROZEN.json','PACKAGE_MANIFEST.json'):
        (HERE/n).write_bytes(files[n])
    dest = PRIVATE/'package.tar.gz'
    with dest.open('wb') as raw, gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as gz, tarfile.open(fileobj=gz,mode='w') as tar:
        for n, data in sorted(files.items()):
            item = tarfile.TarInfo(n)
            item.size = len(data)
            item.mode = 0o700 if n.endswith('.slurm') else 0o600
            tar.addfile(item,io.BytesIO(data))
    print(f'{len(files)} files, {dest.stat().st_size} bytes, SHA256 {digest(dest.read_bytes())}')


if __name__ == '__main__':
    build()
