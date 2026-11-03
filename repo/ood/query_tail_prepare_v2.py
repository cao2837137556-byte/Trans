"""Read-only sealed-cache P phase. No PCAP, E3, reference body or optimizer."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import shutil
import sqlite3
import numpy as np
import query_tail_core_v2 as k
c = k.c


def manifest(folder, expected):
    folder = Path(folder).resolve()
    c.pin(folder/'SHA256SUMS', expected)
    result = {}
    for line in (folder/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        h, rel = line.split('  ', 1)
        c.require((folder/rel).resolve().is_relative_to(folder) and rel not in result and len(h) == 64, 'MANIFEST_UNSAFE')
        result[rel] = h
    return result


def load_metadata(base, design):
    base = Path(base); spec = design['data']; metadata = {}
    seals = manifest(base/'inputs', design['provenance']['input_manifest_sha256'])
    all_uids = set(); components = {}
    for role in k.ROLES:
        rel = role+'.jsonl.gz'; rr = list(c.rows(c.pin(base/'inputs'/rel, seals[rel])))
        partition = {'LEARN':'LEARN', 'CIC_DEV':'DEV', 'UNSW_DEV':'EXTERNAL_ARCHIVAL_EVALUATION'}[role]
        k.metadata_valid(rr, {partition})
        c.require(len(rr) == spec['role_counts'][role] and c.uid_sha(r['uid'] for r in rr) == spec['uid_sha256'][role], 'METADATA_UID:'+role)
        for r in rr:
            c.require(r['uid'] not in all_uids, 'GLOBAL_UID_OVERLAP'); all_uids.add(r['uid'])
            identity = r['fit_role'] if role == 'LEARN' else role
            c.require(role != 'LEARN' or identity in ('FIT', 'CAL'), 'SOURCE_ROLE')
            key = (r['source_sha256'], r['session_id'])
            c.require(components.setdefault(key, identity) == identity, 'DEPENDENCY_CROSS_ROLE')
            c.require(type(r['label_metric_weight_denominator']) is int and r['label_metric_weight_denominator'] > 0, 'METRIC_WEIGHT')
        metadata[role] = rr
    indices = {}
    for split in ('FIT', 'CAL'):
        with np.load(c.pin(base/'inputs'/(split+'.npz'), seals[split+'.npz']), allow_pickle=False) as f:
            ix = f['indices'].copy()
        c.require(ix.dtype == np.int64 and ix.ndim == 1 and len(set(ix)) == len(ix) and np.all((ix >= 0) & (ix < len(metadata['LEARN']))), 'INDEX_SCHEMA')
        rr = [metadata['LEARN'][int(i)] for i in ix]; identity = spec['fit_cal_identity'][split]
        c.require(len(rr) == identity['rows'] and c.uid_sha(r['uid'] for r in rr) == identity['uid_sha256'], 'FULL_SPLIT_UID')
        c.require(all(r['fit_role'] == split for r in rr) and Counter(r['label'] for r in rr) == {0:spec[split]['normal'], 1:spec[split]['attack']}, 'SPLIT_COUNTS')
        indices[split] = ix
    c.require(len(set(indices['FIT']) | set(indices['CAL'])) == len(metadata['LEARN']) and not set(indices['FIT']) & set(indices['CAL']), 'SPLIT_COVERAGE')
    return metadata, indices


def arrays(base, design, verify=True, progress=None):
    base = Path(base); pins = manifest(base/'features', design['provenance']['feature_manifest_sha256'])
    result = {}
    for role in k.ROLES:
        path = base/'features'/(role+'.npy')
        if verify: c.pin(path, pins[path.name])
        a = np.load(path, mmap_mode='r', allow_pickle=False)
        c.require(a.shape == (design['data']['role_counts'][role], 794) and a.dtype == np.float32, 'FEATURE_SCHEMA')
        if verify:
            for start in range(0, len(a), 4096):
                c.require(np.isfinite(a[start:start+4096]).all(), 'FEATURE_NONFINITE')
                if progress is not None: progress.tick(start+len(a[start:start+4096]), len(a))
        result[role] = a
    norms = manifest(base/'normalizers', design['provenance']['normalizer_manifest_sha256'])
    with np.load(c.pin(base/'normalizers/RECENT.npz', norms['RECENT.npz']), allow_pickle=False) as f:
        norm = f['mean'].copy(), f['scale'].copy()
    c.require(all(v.shape == (768,) and np.isfinite(v).all() for v in norm) and np.all(norm[1] > 0), 'NORMALIZER_INVALID')
    return result, norm


def support_census(rows, descriptors):
    groups = defaultdict(list); weight = np.zeros(len(rows), dtype=np.float64)
    for role in ('FIT', 'CAL'):
        for label in (0, 1):
            ix = [i for i, r in enumerate(rows) if r['fit_role'] == role and r['label'] == label]
            weight[ix] = k.class_weights([rows[i] for i in ix])
    for i, r in enumerate(rows):
        groups[(r['fit_role'], r['label'], r['protocol'], k.STAGES[int(descriptors['stage'][i])])].append(i)
    result = []
    for (role, label, proto, stage), ix in sorted(groups.items()):
        ww = weight[ix]; mass = math.fsum(ww)
        item = dict(role=role, label=label, protocol=proto, stage=stage, rows=len(ix),
                    conditional_class_mass=mass, max_row_weight=float(max(ww)), ESS=mass*mass/float(np.dot(ww, ww)))
        for field in ('device', 'capture_id', 'session_id', 'component_id'):
            item[field+'_count'] = len({rows[i][field] for i in ix})
        item['window'] = {}
        for field in ('packets', 'bursts', 'span_seconds', 'same_direction', 'opposite_direction'):
            a = descriptors[field][ix].astype(np.float64)
            item['window'][field] = dict(min=float(a.min()), max=float(a.max()), mean=float(a.mean()), weighted_mean=float(np.dot(a, ww)/mass))
        result.append(item)
    for role in ('FIT', 'CAL'):
        for label in (0, 1):
            c.require(math.isclose(math.fsum(g['conditional_class_mass'] for g in result if g['role'] == role and g['label'] == label), 1., abs_tol=1e-12), 'CENSUS_WEIGHT_CONSERVATION')
    return result


def support_gate(rows, descriptors):
    for label in (0, 1):
        fit = [i for i, r in enumerate(rows) if r['fit_role'] == 'FIT' and r['label'] == label]
        # SYN semantics use independent bits, including RST+SYN; census priority stays mutually exclusive.
        syn = [i for i in fit if descriptors['syn_no_ack'][i]]
        c.require(len({rows[i]['device'] for i in syn}) >= 2 and len({rows[i]['component_id'] for i in syn}) >= 2, 'FIT_SYN_SUPPORT_LABEL_'+str(label))
        c.require(any(rows[i]['protocol'] == 6 and not descriptors['syn_no_ack'][i] for i in fit), 'FIT_TCP_NON_SYN_CLASS')
        c.require(any(rows[i]['protocol'] == 17 for i in fit), 'FIT_UDP_CLASS')


def prepare(root, base, run, design, progress):
    root, base, run = Path(root), Path(base), Path(run)
    c.require(not run.resolve().is_relative_to(base.resolve()), 'OUTPUT_INSIDE_PARENT')
    pins = c.read(root/'parent_pins.json')
    progress.stage = 'P_PARENT_IDENTITIES'
    for rel, digest in pins.items():
        c.pin(base/rel, digest); progress.tick()
    parent = c.read(base/'P_COMPLETE.json')
    c.require(parent['status'] == 'COMPLETE' and parent['rows'] == 1095200 and parent['feature_seal'] == design['provenance']['feature_manifest_sha256'], 'PARENT_NOT_COMPLETE')
    metadata, indices = load_metadata(base, design)
    progress.stage = 'P_FEATURE_SHA_AND_SCHEMA'
    values, norm = arrays(base, design, progress=progress)
    spool = c.pin(base/'spool/snapshots.sqlite', design['provenance']['spool_sha256'])
    out = run/'prepared'; out.mkdir(exist_ok=False)
    q = {}; desc = {}; seen = {}
    dtype = np.dtype([('stage', 'u1'), ('syn_no_ack', '?'), ('packets', 'u1'), ('bursts', 'u1'), ('span_seconds', '<f8'), ('same_direction', 'u1'), ('opposite_direction', 'u1')])
    for role, rr in metadata.items():
        q[role] = np.lib.format.open_memmap(out/(role+'_q.npy'), mode='w+', dtype=np.float32, shape=(len(rr), 14))
        desc[role] = np.lib.format.open_memmap(out/(role+'_window.npy'), mode='w+', dtype=dtype, shape=(len(rr),))
        seen[role] = np.zeros(len(rr), dtype=bool)
    progress.stage = 'P_QUERY_READOUT'; done = 0
    db = sqlite3.connect(spool.resolve().as_uri()+'?mode=ro&immutable=1', uri=True)
    try:
        db.execute('PRAGMA query_only=ON'); db.execute('PRAGMA temp_store=MEMORY')
        counts = dict(db.execute('SELECT role,COUNT(*) FROM snapshots GROUP BY role'))
        c.require(counts == dict(design['data']['role_counts'], SOURCE_REFS=179, UNSW_REFS=92), 'SPOOL_ROLE_COUNTS')
        # No reference body is selected or decoded. No ORDER BY temp sort of the 4 GiB body table.
        for uid, role, slot, proto, body in db.execute("SELECT uid,role,slot,protocol,body FROM snapshots WHERE role IN ('LEARN','CIC_DEV','UNSW_DEV')"):
            c.require(type(slot) is int and 0 <= slot < len(metadata[role]) and not seen[role][slot], 'SPOOL_SLOT')
            row = metadata[role][slot]
            c.require(row['uid'] == uid and row['protocol'] == proto, 'SPOOL_UID_JOIN')
            qq, info = k.descriptor(json.loads(body), row)
            q[role][slot] = qq
            desc[role][slot] = tuple(k.STAGES.index(info[f]) if f == 'stage' else info[f] for f in dtype.names)
            seen[role][slot] = True; done += 1
            if done % 2048 == 0: progress.tick(done, design['input']['descriptor_rows'])
    finally:
        db.close()
    c.require(done == design['input']['descriptor_rows'] and all(v.all() for v in seen.values()), 'DESCRIPTOR_COVERAGE')
    for a in list(q.values())+list(desc.values()): a.flush()
    census = support_census(metadata['LEARN'], desc['LEARN'])
    c.write(out/'source_support.json', dict(groups=census, payload_reconstruction='NOT_REPRODUCIBLE_FROM_SAVED_HEADERS', entity_minimum_is_not_statistical_sufficiency=True))
    old = c.read(base/'spool/support.json')['counts']; rr = metadata['LEARN']; dd = desc['LEARN']
    reproduced = {'protocol_%s_label_%s' % (proto, label): sum(r['fit_role'] == 'FIT' and r['protocol'] == proto and r['label'] == label for r in rr) for proto in (6, 17) for label in (0, 1)}
    reproduced['normal_TCP'] = reproduced['protocol_6_label_0']
    # The parent's SYN count covers FIT rows of both labels (see parent producer).
    reproduced['TCP_SYN_without_ACK'] = sum(r['fit_role'] == 'FIT' and bool(dd['syn_no_ack'][i]) for i, r in enumerate(rr))
    c.write(out/'parent_support_comparison.json', dict(reproduced=reproduced, original={name:old[name] for name in reproduced}, omitted=['TCP_payload', 'rate_lt1', 'rate_1to10', 'rate_ge10']))
    c.require(all(old[name] == count for name, count in reproduced.items()), 'PARENT_SUPPORT_REPRODUCTION')
    support_gate(rr, dd)
    for role in k.ROLES:
        shutil.copyfile(base/'inputs'/(role+'.jsonl.gz'), out/(role+'.jsonl.gz'))
    for split in ('FIT', 'CAL'): c.save_arrays(out/(split+'.npz'), indices=indices[split])
    c.save_arrays(out/'normalizer.npz', mean=norm[0], scale=norm[1])
    c.write(out/'receipt.json', dict(status='COMPLETE', descriptor_rows=done, feature_manifest=design['provenance']['feature_manifest_sha256'], spool_sha256=design['provenance']['spool_sha256'], source_stage_support='PASS', no_reference_body=True, real_optimizer_updates=0))
    c.seal(out); c.verify(out)
    c.write(run/'P_COMPLETE.json', dict(status='COMPLETE', prepared_seal=c.sha(out/'SHA256SUMS'), design_sha256=k.DESIGN_SHA, rows=done))
    progress.tick(done, done, force=True)
    return metadata, indices, values, norm
