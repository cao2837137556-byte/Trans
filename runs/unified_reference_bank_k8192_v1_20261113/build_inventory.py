"""Build the asset probe from the frozen receipts without opening query files."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import zlib
import base64

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
HPC = '/public/home/jiangxinwei.zr/work/paper04/'
CARD = 'runs/mainline_docs/collab/20261113_unified_reference_bank_k8192_freeze_codex.md'
CARD_SHA = '3a346a76bc05d8428a60dbd0e73c7951463d21b2452230b12e620b59088e5368'
RUN = 'unified_reference_bank_k8192_v1_20261113'
C4 = 'history_sample_coverage_c4_batch_resume_v1_20261102'
C1 = 'history_normal_reference_d2_trace_v1_20261031'


def load(path):
    return json.loads((REPO / path).read_text(encoding='utf-8-sig'))


def relative(path):
    return path.removeprefix(HPC)


def save(path, value):
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def build():
    freeze = subprocess.check_output(['git','show','acfe0a1:'+CARD],cwd=REPO)
    if hashlib.sha256(freeze).hexdigest()!=CARD_SHA or (REPO/CARD).read_bytes()!=freeze:
        raise ValueError('Frozen card does not match acfe0a1')
    rec = load('runs/same_information_recalibration_v1_20261113/INPUT_PINS.json')['inputs']
    r1 = load('runs/reference_evidence_round1_v1_20261112/INPUT_PINS.json')['inputs']
    verified = load('runs/same_bank_context_v6_20261106/HISTORY_INVENTORY.json')
    lineage = load('runs/same_bank_context_v6_20261106/HISTORY_INPUTS.json')
    paths = {}

    def put(name, group, paths_, source, sha=None, size=None):
        for path in paths_:
            if Path(path).is_absolute() or '..' in Path(path).parts:
                raise ValueError('Probe paths must stay under Paper04: '+path)
        paths[name] = dict(group=group, paths=list(dict.fromkeys(paths_)), source=source,
                           sha256=sha, bytes=size)

    def rec_spec(name, spec, group=None):
        put(name,group or spec['role'],spec['remote'],'prior acceptance receipt',
            spec.get('sha256'),spec.get('bytes'))

    for name,spec in rec.items():
        if name.startswith(('head_', 'model:')):continue
        rec_spec(name,spec)
    for k in ('query_context','query_e3','query_q','query_context_uids'):
        rec_spec('UNSW_DEV:'+k,r1[k],'query')
    prior = load('runs/context_geometry_attribution_v2_20261106/DIAGNOSE_RESULT.json')['all_input_pins']
    for k,f in (('query_context','features8/CIC_DEV.npy'),('query_e3','features/CIC_DEV.npy'),('query_q','prepared/CIC_DEV_q.npy')):
        hits = [relative(path) for path in prior if path.endswith('/'+f)]
        if len(hits)!=1:raise ValueError('CIC input identity: '+k)
        path=hits[0]
        put('CIC_DEV:'+k,'query',[path],'prior real attribution acceptance',prior[HPC+path])
    put('CIC_DEV:query_context_uids','query',['runs/device_context_training_v2_20261105/metadata/CIC_DEV.npz'],
        'compare ordered UID during query admission')
    for i in range(18,33):
        key=f'a{i}'; s=lineage['assets'][key]
        put(key,'raw_or_index',[relative(verified[key]['path'])], 'same_bank_context_v6 prior verified inventory',
            s['sha256'],s['bytes'])
    old = load('runs/device_context_training_v2_20261105/INVENTORY.json')['files']
    for fileno,k in zip((106,107,108),('raw76','raw77','raw78')):
        s=old[k]
        put('Eufy:'+str(fileno),'raw_or_index',[relative(x) for x in s['candidates']],
            'frozen CIC raw catalog',s['sha256'],s['bytes'])

    for device in ('TP_LINK','WEMO_POWER','SAMSUNG','NETATMO'):
        f=f'runs/{C4}/retrieved/history/{device}'
        a=load(f+'/PREPARE_RESULT.json')
        clean=load(f+'/INTERMEDIATE_CLEANUP.json')['files']
        remove=next(x for x in clean if x['name']=='candidates.sqlite')
        assert a['census_sha256']==remove['sha256']
        pool=[relative(a['selection']['ref_rows']['path'].split('/selection/')[0]),
              f'runs/{C4}/outputs/encoding/history/{device}']
        if device=='NETATMO':
            hard=load(f+'/PREPARED_REUSE.json')
            assert hard['files']['candidates.sqlite']['sha256']==remove['sha256']
            pool.extend([relative(hard['source']),
                'runs/history_sample_coverage_c4_checkpoint_repair_v1_20261101/outputs/encoding/history/NETATMO',
                'runs/history_sample_coverage_c4_memory_repair_v1_20261101/outputs/encoding/history/NETATMO'])
        put('census:C4:'+device,'census',[x+'/candidates.sqlite' for x in pool],
            'C4 complete census pin; the cleanup may have removed some paths',remove['sha256'],remove['bytes'])
        if device=='NETATMO':continue
        f=f'runs/{C1}/retrieved/history/{device}'
        a=load(f+'/PREPARE_RESULT.json')
        remove=next(x for x in load(f+'/INTERMEDIATE_CLEANUP.json')['removed'] if x['name']=='candidates.sqlite')
        assert a['census_sha256']==remove['sha256']
        put('census:C1:'+device,'census',[relative(a['selection']['ref_rows']['path'].split('/selection/')[0])+'/candidates.sqlite'],
            'C1 complete census pin; legacy schema requires metadata and count parity',remove['sha256'],remove['bytes'])
    motion=load(f'runs/{RUN}/MOTION_ROLE_HEADER_WITNESS.json')
    put('Motion:raw','raw_or_index',[
        'data_external/unsw_iotraffic_2025/raw_selected/BelkinWemoMotionSensor_ec1a59832811.pcap',
        f'runs/{RUN}/inputs/BelkinWemoMotionSensor_ec1a59832811.pcap'],
        'locally SHA-verified ZIP member; HPC copy not yet proven',motion['raw_sha256'],motion['raw_bytes'])
    for suffix in ('packet_index.npy','chronological_order.npy'):
        put('Motion:'+suffix,'new_artifact_if_missing',[
            'data_external/unsw_iotraffic_2025/timeline_index/BelkinWemoMotionSensor_ec1a59832811.'+suffix,
            f'runs/{RUN}/inputs/BelkinWemoMotionSensor_ec1a59832811.'+suffix],
            'file presence only; needs independent raw/index binding')
    for name,path in (
        ('frontend_wrapper','frontend_compat_v1/environment.sh'),
        ('numpy2','runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201/numpy/__init__.py'),
    ):
        put(name,'runtime',[path],'previously accepted runtime; compute-node check still required')
    encoder = load(f'runs/{C4}/config/EXECUTION.json')['encoder']['runtime_files_manifest']
    put('history_runtime_manifest','runtime',
        ['runs/history_normal_reference_keyrepair_v1_20261031/config/ENCODER_RUNTIME_FILES.json'],
        'C4 encoder runtime manifest',encoder['sha256'])
    manifest=dict(status='HPC_PRESENCE_NOT_YET_CHECKED', frozen_card_sha256=CARD_SHA,
                  project=HPC.rstrip('/'), run=RUN, files=paths)
    save(HERE/'REMOTE_ASSET_PINS.json',manifest)
    source=(HERE/'probe_hpc.py').read_text(encoding='utf-8')
    pre='PROBE_MANIFEST = '+repr(manifest)+'\n'
    payload=pre+source
    # Inline a small script in the existing shell; stdout only, no login or scheduler mutation.
    bash = (
        "(\n  set -o pipefail\n  umask 077\n"
        "  /share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -B - <<'PAPER04_K8192_READ_ONLY'\n"
        +payload+"\nPAPER04_K8192_READ_ONLY\n)\n"
    )
    with (HERE/'HPC_READONLY_CHECK.sh').open('w',encoding='utf-8',newline='\n') as stream:
        stream.write(bash)
    data=base64.b64encode(zlib.compress(bash.encode('utf-8'),9)).decode('ascii')
    loader=('import base64,subprocess,sys,zlib; '
            'sys.exit(subprocess.run(["bash"],input=zlib.decompress(base64.b64decode('
            +repr(data)+'))).returncode)')
    with (HERE/'HPC_READONLY_ONE_LINE.txt').open('w',encoding='ascii',newline='\n') as stream:
        stream.write(' /share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -B -c '
                     +shlex.quote(loader)+'\n')
    print('HPC_INVENTORY_MANIFEST',len(paths),hashlib.sha256(bash.encode()).hexdigest())


if __name__ == '__main__':
    build()
