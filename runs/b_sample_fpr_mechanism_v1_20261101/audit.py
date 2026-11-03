"""Saved-decision diagnosis for the explicitly reopened sample-FPR objective.

Support=1 is an unattainability check, never a candidate or measured result.
No source/input mutations, model forwards, packet decoding or new distances.
"""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '4'
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'repo/ood'))
sys.path.insert(0, str(ROOT / 'runs/history_normal_reference_keyrepair_v1_20261031'))
import constrained_onboarding_core_v3 as core
from hnr.assets import helpers

PINS = {}
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(4*1024**2), b''): h.update(block)
    return h.hexdigest()

def pin(p, expected=None):
    p = Path(p).resolve(); digest = sha(p)
    if expected: assert digest == expected, str(p)
    PINS[str(p)] = digest
    return p

def read(p): return json.loads(pin(p).read_text(encoding='utf-8-sig'))
def rows(p):
    with gzip.open(pin(p), 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]

def write(name, value):
    with (HERE/name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')

def quant(x): return np.quantile(x, [0,.25,.5,.75,1]).tolist() if len(x) else []

def load():
    config = read(ROOT/'runs/history_normal_reference_keyrepair_v1_20261031/config/ASSETS.json')
    spec = config['pools']['UNSW_DEV']
    rr = rows(pin(ROOT/spec['query']['rows']['path'], spec['query']['rows']['sha256']))
    p = pin(ROOT/'runs/history_normal_reference_c3_progress_repair_v1_20261101/output/ab/UNSW_DEV/DECISIONS.npz')
    with np.load(p, allow_pickle=False) as f: saved = {k:f[k].copy() for k in f.files}
    assert saved['uid'].tolist() == [r['uid'] for r in rr]
    q = np.load(pin(ROOT/spec['query']['q14']['path'], spec['query']['q14']['sha256']), allow_pickle=False)
    assert np.array_equal(saved['guard'], (q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0))
    calibration = {k:read(pin(ROOT/config['calibration'][k]['path'], config['calibration'][k]['sha256'])) for k in ('cuts','scales','geometry')}
    mask = np.asarray(helpers().metrics.post_window_mask(rr, spec['windows']), dtype=bool)
    return config, rr, saved, q, calibration, mask

def main():
    config, rr, saved, q, frozen, primary = load()
    pin(ROOT/'repo/ood/constrained_onboarding_core_v3.py')
    pin(Path(helpers().metrics.__file__))
    normal = primary & np.array([r['label']==0 for r in rr])
    fp = normal & saved['corrected'][:,3]
    assert (int(normal.sum()),int(fp.sum())) == (74444,8494)
    ideal_logits = core.apply_correction(saved['raw_logits'], np.ones(len(rr)), frozen['scales'], .25)
    ideal_logits[saved['guard']] = saved['raw_logits'][saved['guard']]
    ideal_fp = normal & (core.ordered_ensemble(ideal_logits)>frozen['cuts']['ensemble_cut'])
    assert not np.any(ideal_fp & ~fp)
    needed = (core.ordered_ensemble(saved['raw_logits'])-frozen['cuts']['ensemble_cut'])/(.25*np.mean(frozen['scales']['scales']))
    # Reproduce stored corrected logits and all four heads before interpreting them.
    replay = core.apply_correction(saved['raw_logits'],saved['support'],frozen['scales'],.25)
    replay[saved['guard']] = saved['raw_logits'][saved['guard']]
    assert np.array_equal(replay, saved['corrected_logits'])
    decisions = np.column_stack((replay>frozen['cuts']['cuts'],core.ordered_ensemble(replay)>frozen['cuts']['ensemble_cut']))
    assert np.array_equal(decisions,saved['corrected'])
    devices = {}
    for device in sorted({r['device'] for r in rr}):
        dm = np.array([r['device']==device for r in rr]); ix=np.flatnonzero(fp&dm)
        devices[device] = dict(normal_rows=int((normal&dm).sum()),fp=len(ix),
            sample_fpr=len(ix)/int((normal&dm).sum()),guarded_fp=int(saved['guard'][ix].sum()),
            ineligible_fp=int((~saved['eligible'][ix]).sum()),zero_support_fp=int((saved['support'][ix]==0).sum()),
            optimistic_support_one_remaining_fp=int((ideal_fp&dm).sum()),
            support_quantiles=quant(saved['support'][ix]),required_support_quantiles=quant(needed[ix]),
            protocols=dict(Counter(str(rr[i]['protocol']) for i in ix)))
    components=defaultdict(list)
    for i in np.flatnonzero(normal): components[(rr[i]['device'],rr[i]['component_id'])].append(int(i))
    top=[]
    for (device,component),indices in components.items():
        ix=np.array(indices);fi=ix[fp[ix]]
        if not len(fi):continue
        top.append(dict(device=device,component_id=component,normal_rows=len(ix),fp=len(fi),
            protocols=dict(Counter(str(rr[i]['protocol']) for i in fi)),
            optimistic_support_one_remaining_fp=int(ideal_fp[ix].sum()),
            support_quantiles=quant(saved['support'][fi]),required_support_quantiles=quant(needed[fi]),
            representative_metadata=rr[fi[0]]))
    top.sort(key=lambda x:(-x['fp'],x['device'],x['component_id']))
    dense_spec=config['pools']['UNSW_DEV']['dense_bank']['rows']
    dense=rows(pin(ROOT/dense_spec['path'],dense_spec['sha256']))
    reference_groups=defaultdict(list)
    for r in dense: reference_groups[(r['device'],r['protocol'])].append(r)
    roster=[]
    for (device,protocol),group in sorted(reference_groups.items()):
        roster.append(dict(device=device,protocol=protocol,rows=len(group),components=len({r['component_id'] for r in group}),
            timestamp_min=min(r['timestamp'] for r in group),timestamp_max=max(r['timestamp'] for r in group)))
    archive=ROOT.parent.parent/'data_external/unsw_iotraffic_2025/pcaps.zip'
    before=archive.stat()
    with zipfile.ZipFile(archive) as z:
        entries=[dict(name=i.filename,uncompressed_bytes=i.file_size,compressed_bytes=i.compress_size,crc32=f'{i.CRC:08x}')
                 for i in z.infolist() if 'netatmo' in i.filename.lower() or '70ee50183443' in i.filename.lower()]
    after=archive.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    remaining=int(normal.sum())//50
    result=dict(status='SAVED_REPLAY_AND_BOUND_VERIFIED',evidence='CONSUMED_DEVELOPMENT_ONLY',
        current_fp=int(fp.sum()),normal_rows=int(normal.sum()),current_sample_fpr=float(fp.sum()/normal.sum()),
        maximum_fp_for_2pct=remaining,required_repairs_without_new_fp=int(fp.sum())-remaining,
        optimistic_support_one_remaining_fp=int(ideal_fp.sum()),optimistic_sample_fpr_floor=float(ideal_fp.sum()/normal.sum()),
        bound_warning='Support=1 is not an attainable result; ignores neighbor availability and attack protection.',
        devices=devices,components=top,dense_reference_roster=roster,
        existing_zip_netatmo_entries=entries,zip_inventory_only=dict(path=str(archive),size=after.st_size,mtime_ns=after.st_mtime_ns,
        crc_payload_not_tested=True,normality_and_identity_not_yet_qualified=True),
        new_distances=0,model_forwards=0,downloads=0,input_sha256=PINS)
    for path,digest in PINS.items():assert sha(path)==digest,path
    write('EVIDENCE.json',result)
    write('VERIFICATION.json',dict(status='PASS',inputs_unchanged=len(PINS),script_sha256=sha(__file__)))
    print(json.dumps({k:v for k,v in result.items() if k not in ('components','input_sha256','dense_reference_roster')},ensure_ascii=False))

if __name__=='__main__':main()
