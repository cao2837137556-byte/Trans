"""Collect the frozen runtime source closure and immutable small input contracts."""
import ast
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import tarfile

from motion_ingress import CARD_SHA, LIMIT, digest

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent
ROOT = RUNS.parent
ROUND1 = RUNS / 'reference_evidence_round1_v1_20261112'
C4 = RUNS / 'history_sample_coverage_c4_batch_resume_v1_20261102'
C3 = RUNS / 'history_normal_reference_c3_progress_repair_v1_20261101'
RECAL = RUNS / 'same_information_recalibration_v1_20261113'
OOD = ROOT / 'repo/ood'


def json_read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def bytes_json(value):
    return (json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False)+'\n').encode()


def text_bytes(path):
    return path.read_bytes().replace(b'\r\n', b'\n')


def source_closure(seed, shadowed):
    remaining = set(seed)
    seen = set()
    while remaining:
        module = remaining.pop()
        path = OOD / (module+'.py')
        if module in seen or module in shadowed or not path.is_file():
            continue
        seen.add(module)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if isinstance(node, ast.Import):
                remaining.update(n.name.split('.')[0] for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                remaining.add(node.module.split('.')[0])
    return {f'repo/ood/{m}.py':text_bytes(OOD/(m+'.py')) for m in sorted(seen)}


def sources():
    execution = json_read(C4/'config/EXECUTION.json')
    census_records = {
        'TP_LINK': (18, 42191), 'WEMO_POWER': (21, 113542),
        'SAMSUNG': (24, 2741318), 'NETATMO': (27, 2612450),
    }
    specs, logical, counts = [], {}, {}
    for spec in execution['devices']:
        device = spec['key']
        first, count = census_records[device]
        counts[device] = count
        paths = {field:'a'+str(first+i) for i,field in enumerate(
            ('raw','packet_index','chronological_order'))}
        specs.append(dict({k:v for k,v in spec.items() if k not in paths}, paths=paths))
        logical[device] = json_read(C4/'retrieved/history'/device/'LOGICAL_INPUT.json')
        for field in paths:
            if field in logical[device]:
                del logical[device][field]['path']
    motion = json_read(HERE/'MOTION_ROLE_HEADER_WITNESS.json')
    local_index = json_read(HERE/'.private/motion_verified/ROLE_BINDING.json')['assets']
    specs.append(dict({k:motion[k] for k in ('reference_end_us','bank_end_frame','first_dev_time_us','packets')},
        key='MOTION', display_name='WEMO Motion', owner='ec:1a:59:83:28:11',
        capture_id='well-history-r2-wemo_motion-e1a9de0a5eb30c72',
        device='unsw-attack-traces-2018:ec:1a:59:83:28:11',
        partition='EXTERNAL_ARCHIVAL_EVALUATION', known_macs=specs[0]['known_macs'],
        normality_evidence=specs[0]['normality_evidence']))
    catalog = json_read(RUNS/'device_context_training_v2_20261105/RAW_CATALOG.json')
    c3 = json_read(C3/'INPUT_MANIFEST.json')
    clips = {106:'Eufy:106',107:'Eufy:107',108:'Eufy:108',189:'a30',190:'a31',191:'a32'}
    short = []
    for item in catalog:
        if item.get('file_id') not in clips:
            continue
        eufy = item['file_id'] < 180
        first = 1634135742834257 if eufy else 1634046748850539
        normal = next((r['normality_evidence'] for r in c3['captures']
                      if r['file_id']==item['file_id']), None)
        short.append(dict({k:v for k,v in item.items() if k != 'path'},
            asset=clips[item['file_id']], first_query_us=first,
            normality_evidence=normal or 'CIC original 3-Interactions / LOCAL_RING normal category, pre-existing REFERENCE role and device MAC.'))
    old = json_read(C4/'retrieved/history/NETATMO/PREPARED_REUSE.json')
    netatmo = dict(files={k:v['sha256'] for k,v in old['files'].items()},
                   counts={'HIST_REF':2612450,'HIST_DEV':980497})
    base = 'runs/diagnostics_c5_step2_package_v1_20261025/local_benchmark_v1/runtime'
    encoder_dirs = [base,
        'runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/encode/runtime',
        'runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime',
        'runs/dense_reference_ab_stage_dependency_repair_v1_20261028_runtime/job_179700/science/runtime']
    encoder_exec = [f'runs/{d}/config/EXECUTION.json' for d in (
        C4.name, 'history_normal_reference_keyrepair_v1_20261031',
        'history_sample_coverage_c4_header_repair_v1_20261101',
        'history_normal_reference_d2_trace_v1_20261031')]
    return dict(long=specs, short=short, logical=logical, netatmo_reuse=netatmo,
        old_hist_ref_counts=counts, cic_known_macs=c3['known_macs'], probe_frames=4096,
        motion_index_sha256={k:local_index[k]['sha256'] for k in ('packet_index','chronological_order')},
        encoder_runtime_locations=encoder_dirs, encoder_execution_paths=encoder_exec)


def pack():
    parts = {}
    for name in ('motion_ingress.py','motion_index.py','frozen_selector.py','zero_degradation.py',
                 'runtime_support.py','reference_frontend.py','reference_features.py','prepare_reference.py',
                 'paired_replay.py','worker.py','dispatch.py','run.slurm','REMOTE_ASSET_PINS.json',
                 'MOTION_ROLE_HEADER_WITNESS.json'):
        parts[name] = text_bytes(HERE/name)
    for name in ('common_round1.py','analysis_core.py','evaluation.py','calibration.py',
                 'reference_assets.py','CONFIG.json','EXPECTED_BASELINE.json'):
        parts[name] = text_bytes(RECAL/name)
    for name in ('reference_inputs.py','replay_geometry.py'):
        parts[name] = text_bytes(ROUND1/name)
    parts['GEOMETRY.json'] = text_bytes(ROUND1/'CONFIG.json')
    parts['freeze.md'] = text_bytes(RUNS/'mainline_docs/collab/20261113_unified_reference_bank_k8192_freeze_codex.md')
    assert sha256(parts['freeze.md']).hexdigest() == CARD_SHA, 'FROZEN_CARD_PIN'
    for path in (ROUND1/'vendor').glob('*.py'):
        # The accepted metrics module at package root also supplies group_masks.
        # A second module with this name shadows it after vendor initializes.
        if path.name == 'analysis_core.py':
            continue
        parts['vendor/'+path.name] = text_bytes(path)
    for name in ('__init__.py','common.py','history.py','contexts.py','encoding.py'):
        parts['hnr/'+name] = text_bytes(C4/'hnr'/name)
    parts['decoder_guard.py'] = text_bytes(C4/'decoder_guard.py')
    seeds = {'continuous_input_v3','continuous_features_v3','continuous_input_engineering_v1',
             'constrained_onboarding_reference_v2','legacy_reference_sample_prepare_v1',
             'legacy_unsw_archival_runtime_v1','issue27ckbu_unified_tshark_causal_frontend_v1',
             'issue27ckda_d0_resource_pilot_v1','issue27ckda_d1_e3_embed_v1'}
    shadows = {Path(name).stem for name in parts if name.endswith('.py')}
    parts.update(source_closure(seeds, shadows))
    parts['REFERENCE_SOURCES.json'] = bytes_json(sources())
    # These small witnesses prove cached E3 input and vector identity, without transferring model files.
    receipts = {}
    for number,key in enumerate(('TP_LINK','WEMO_POWER','SAMSUNG','NETATMO')):
        path = C4/'retrieved/history'/key/'encoded/tensor_receipts.jsonl.gz'
        expected = json_read(path.parent/'ENCODE_RESULT.json')['files'][path.name]
        assert digest(path) == expected, 'C4_TENSOR_RECEIPT'
        receipts['a'+str(10+2*number)] = dict(bundled=True, path='tensor/'+key+'.jsonl.gz',
                                                  sha256=expected)
        parts['tensor/'+key+'.jsonl.gz'] = path.read_bytes()
    for i,key in enumerate(('TP_LINK','WEMO_POWER','SAMSUNG')):
        member = RUNS/'history_normal_reference_d2_trace_v1_20261031/retrieved/history'/key/'encoded'
        expected = json_read(member/'ENCODE_RESULT.json')['files']['tensor_receipts.jsonl.gz']
        receipts['a'+str(4+2*i)] = dict(path=str(
            (RUNS/'history_normal_reference_keyrepair_v1_20261031/outputs/history'/key/'encoded/tensor_receipts.jsonl.gz')
            .relative_to(ROOT).as_posix()), sha256=expected)
    path = C3/'retrieved/encoded/tensor_receipts.jsonl.gz'
    receipts['a2'] = dict(bundled=True, path='tensor/HEIM.jsonl.gz', sha256=digest(path))
    parts['tensor/HEIM.jsonl.gz'] = path.read_bytes()
    parts['CACHE_TENSOR_PINS.json'] = bytes_json(receipts)
    for name,value in parts.items():
        if name.endswith('.py'):
            compile(value, name, 'exec')
    manifest = bytes_json(dict(card_sha256=CARD_SHA,
        files={name:sha256(data).hexdigest() for name,data in sorted(parts.items())}))
    parts['PACKAGE_MANIFEST.json'] = manifest
    out = HERE/'.private/package.tar.gz'
    out.parent.mkdir(exist_ok=True)
    temporary = out.with_suffix('.tmp')
    with (
        temporary.open('wb') as dst,
        gzip.GzipFile(filename='', fileobj=dst, mode='wb', mtime=0) as gz,
        tarfile.open(fileobj=gz, mode='w') as archive,
    ):
        for name, value in sorted(parts.items()):
            member = tarfile.TarInfo(name)
            member.mode = 0o700 if name.endswith('.slurm') else 0o600
            member.size = len(value)
            archive.addfile(member, io.BytesIO(value))
    assert temporary.stat().st_size <= LIMIT and len(parts) <= 240
    temporary.replace(out)
    (HERE/'PACKAGE_MANIFEST.json').write_bytes(manifest)
    print(json.dumps(dict(files=len(parts), bytes=out.stat().st_size,
                          archive_sha256=digest(out), manifest_sha256=sha256(manifest).hexdigest())))


if __name__ == '__main__':
    pack()
