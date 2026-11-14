"""Reference-only preparation. Freeze the population and selected UIDs before queries open."""
from collections import Counter, defaultdict
from itertools import chain
import json
from pathlib import Path

import numpy as np

from common_round1 import read_rows, uid_sha, write_rows
from frozen_selector import CAP, SALT, need, physical, select
from hnr.encoding import new_encoder
from reference_features import caches, encoder_config, materialize, source_identity_equal
from reference_frontend import admit_long, admission, iter_long_census, short_capture, walk_long
from runtime_support import HERE, asset, digest, read, write
from vendor import history_context, physical as context_physical


class PathPin:
    @staticmethod
    def pin(path, sha):
        from runtime_support import digest
        path = Path(path)
        need(digest(path) == sha, 'PHYSICAL_CONTEXT_RAW_PIN')
        return path


def chronological_context(rows, spec, material, progress, oracle):
    binding, index, order, _, _ = material
    target = dict(spec, **{k: v for k, v in binding.items() if k not in spec})
    # Use the accepted context engine, independent of the E3/Q14 decoder.
    from collections import deque
    import struct
    from stream_core import Engine

    at_frame = {row['frame']: (i, row) for i, row in enumerate(rows)}
    need(len(at_frame) == len(rows) > 0, 'CONTEXT_FRAME_MAP')
    stop = max(at_frame)
    engine = Engine()
    values = np.full((len(rows), 8), np.nan, dtype=np.float64)
    owner = spec['owner'].replace(':', '')
    previous = deque()
    for frame, t, packet, _, ordinal in history_context.indexed_packets(
            Path(spec['raw']['path']), index, order, target, stop):
        event = None
        if packet and packet[-2] == owner:
            proto, size, src, dst, sp, dp, md, _ = packet
            event = (md, proto, size, src, struct.pack('!BIIHH', proto, src, dst, sp, dp))
        clock = engine.advance(frame, t, spec['key'], event)
        if oracle:
            while previous and previous[0][0] <= clock-10**10:
                previous.popleft()
            if event:
                previous.append((clock, event))
        if frame in at_frame:
            i, row = at_frame[frame]
            need(ordinal == row['origin_packet_ordinal'] and t == row['timestamp_us']*1000 and
                 packet and owner in packet[-2:] and packet[0] == row['protocol'],
                 'FROZEN_CONTEXT_PACKET_IDENTITY:' + spec['key'] + ':' + str(frame))
            values[i] = engine.features(owner, packet[0])
            if oracle:
                brute = []
                for width in (10**9, 10**10):
                    selected = [e for tm, e in previous if clock-width < tm <= clock
                                and e[0] == owner and e[1] == packet[0]]
                    brute.extend((len(selected)/(width/1e9), sum(e[2] for e in selected)/(width/1e9),
                                  len({e[3] for e in selected}), len({e[4] for e in selected})))
                need(np.array_equal(values[i], brute), 'CHRONOLOGICAL_CONTEXT_ORACLE')
        if frame % 50000 == 0:
            progress('HIST_REF_CONTEXT', frame, stop, device=spec['key'])
    need(np.isfinite(values).all(), 'CONTEXT_COVERAGE')
    return dict(zip((row['uid'] for row in rows), values)), dict(
        frames=stop, rows=len(rows), decoded_hist_dev=0, peak_entries=engine.peak_entries)


def load_sources(store, motion):
    cfg = read(HERE / 'REFERENCE_SOURCES.json')
    need(all(motion[k]['sha256'] == v for k, v in cfg['motion_index_sha256'].items()),
         'MOTION_INDEPENDENT_INDEX_PARITY')
    specs = []
    for member in cfg['long']:
        spec = dict(member)
        paths = spec.pop('paths', None)
        if paths is None:
            spec.update(motion)
        else:
            for field, key in paths.items():
                path = store.get(key)
                spec[field] = dict(store.checked[key], path=str(path))
        specs.append(spec)
    shorts = []
    for member in cfg['short']:
        path = store.get(member['asset'])
        need(store.checked[member['asset']]['sha256'] == member['sha256'], 'CIC_RAW_JOIN')
        shorts.append(dict(member, raw=dict(path=str(path), sha256=member['sha256'])))
    need(len(specs) == 5 and len(shorts) == 6 and
         len({r['raw']['sha256'] for r in specs+shorts}) == 11, 'ADMITTED_CAPTURE_ROSTER')
    return cfg, specs, shorts


def freeze_selection(store, cfg, specs, shorts, output, progress, tshark, *, probe, prior_probe):
    import legacy_reference_sample_prepare_v1 as legacy

    api = legacy.old.legacy_runtime()
    record = {}
    sources = {'CIC_DEV': {}, 'UNSW_DEV': {}}
    shorts_selected = {}
    long_material = {}
    for spec in shorts:
        with progress.measure('CIC_ADMISSION_' + spec['capture_id']):
            entries, (key, entry) = short_capture(spec, output, api, tshark, cfg['cic_known_macs'])
            sources['CIC_DEV'][key] = entry
            shorts_selected.update({x['uid']: x for x in entries})
            record[spec['capture_id']] = dict(eligible=len(entries), source=entry,
                                             mode=spec['mode'], raw=spec['raw'])
    long_rows = []
    if probe:
        specs = [s for s in specs if s['key'] in ('TP_LINK', 'MOTION')]
    for spec in specs:
        device = spec['key']
        known = None
        if device == 'NETATMO':
            known = dict(cfg['netatmo_reuse'], path=store.get('census:C4:NETATMO'))
        folder = output / device
        previous = prior_probe/device if prior_probe is not None and (
            prior_probe/device/'chronological.pcapng').is_file() else None
        with progress.measure('ADMIT_' + device):
            material = admit_long(spec, folder, tshark, dict(
                logical=cfg['logical'].get(device), netatmo=known), progress, prior_probe=previous)
        binding, index, order, _, source_sha = material
        key, entry = admission(spec, binding)
        sources['UNSW_DEV'][key] = entry
        with progress.measure('ENDPOINT_POPULATION_' + device):
            if probe and previous is not None:
                path = previous/'census_probe.sqlite'
                receipt = read(previous/'census_probe_receipt.json')
                counts = receipt['legal_endpoints']
                need(receipt['packets'] == cfg['probe_frames'] and
                     receipt['stderr_sha256'] == digest(previous/'census_probe.stderr') and
                     not (previous/'census_probe.stderr').stat().st_size and
                     asset(path) == receipt['census'], 'PREDECESSOR_COMPLETE_PROBE_CENSUS:' + device)
                census = asset(path)
            elif known is None:
                path, counts = walk_long(spec, folder, material, api, tshark, progress,
                                         prefix=cfg['probe_frames'] if probe else None)
                expected = cfg['old_hist_ref_counts'].get(device)
                if expected is not None and not probe:
                    need(counts.get('HIST_REF') == expected, 'REBUILT_CENSUS_COUNTS:' + device)
                census = asset(path)
            else:
                path, counts = known['path'], known['counts']
                census = store.checked['census:C4:NETATMO']
        long_rows.append(iter_long_census(spec, binding, index, order, source_sha, path, counts))
        long_material[device] = (spec, folder, material, known)
        record[device] = dict(census=census, counts=counts,
                              reused=known is not None or (probe and previous is not None),
                              binding=binding, raw=spec['raw'], logical_source_sha256=source_sha)

    with progress.measure('FROZEN_PHYSICAL_HASH_SELECTION'):
        choices = {}
        for pool, population in (
            ('CIC_DEV', (entry['row'] for entry in shorts_selected.values())),
            ('UNSW_DEV', chain.from_iterable(long_rows)),
        ):
            def progress_rows():
                for i, row in enumerate(population, 1):
                    if i % 32768 == 0:
                        progress('HASH_'+pool, i, sum(
                            r.get('counts', {}).get('HIST_REF', r.get('eligible', 0))
                            for r in record.values()))
                    yield row
            rows, totals = select(progress_rows(), sources[pool], output/(pool+'_rank.sqlite'))
            picked = Counter((r['device'], r['protocol']) for r in rows)
            need(all(picked[k] == min(CAP, v) for k, v in totals.items()) and
                 sum(picked.values()) == len(rows) > 0, 'K8192_GROUP_COUNTS')
            if probe:
                # Sample legal candidates by physical order for the compute-node witness only.
                groups = defaultdict(list)
                for row in sorted(rows, key=physical):
                    if len(groups[row['device'], row['protocol']]) < 8:
                        groups[row['device'], row['protocol']].append(row)
                rows = sorted(chain.from_iterable(groups.values()), key=lambda r: r['uid'])
            choices[pool] = rows
            path = output/(pool+'_HISTORY.jsonl.gz')
            need(write_rows(path, rows) == len(rows), 'SELECTION_ROWS_WRITTEN')
            if probe and prior_probe is not None:
                earlier = read(prior_probe/'SELECTION.json')[pool]['rows']
                old_path = prior_probe/path.name
                need(asset(old_path, count=len(rows), uid_sha256=uid_sha([r['uid'] for r in rows])) == earlier
                     and rows == read_rows(old_path), 'PROBE_RESELECTED_ROWS_CHANGED:' + pool)
            record[pool] = dict(rows=asset(path, count=len(rows), uid_sha256=uid_sha([r['uid'] for r in rows])),
                groups=[dict(device=k[0], protocol=k[1], eligible=totals[k], selected=picked[k])
                        for k in sorted(totals)])
        record['EDGE'] = dict(added_historical=0, commissioning=4124)
        write(output/'SELECTION.json', dict(status='REAL_SLICE_SEALED' if probe else 'SEALED',
            cap=CAP, salt=SALT, old_rows=[], query_access=False, **record))
    return choices, long_material, shorts_selected, api, record


def prepare(store, output, motion, progress, tshark, cfg, *, probe, prior_probe=None):
    output.mkdir(exist_ok=False)
    source_cfg, specs, shorts = load_sources(store, motion)
    choices, materials, short_entries, api, population = freeze_selection(
        store, source_cfg, specs, shorts, output, progress, tshark, probe=probe, prior_probe=prior_probe)
    selection_sha = asset(output/'SELECTION.json')['sha256']
    with progress.measure('PIN_FROZEN_ENCODER'):
        encoder, identity = new_encoder(encoder_config(store))
    results = {}
    for pool, rows in choices.items():
        entries = {}
        context_values = {}
        cache, old_context, tensors = caches(store, pool, cfg)
        receipts = {}
        groups = defaultdict(list)
        for row in rows:
            groups[row['capture_id']].append(row)
            old = cache.get(row['uid'])
            if old is not None and source_identity_equal(old[0], row) and row['uid'] in old_context:
                context_values[row['uid']] = old_context[row['uid']]
        if pool == 'CIC_DEV':
            entries = {r['uid']: short_entries[r['uid']] for r in rows}
            for spec in shorts:
                group = groups[spec['capture_id']]
                new = [r for r in group if probe or r['uid'] not in context_values]
                if new:
                    values, receipt = context_physical.replay(new, Path(spec['raw']['path']),
                        spec['sha256'], PathPin, progress, oracle=probe)
                    for row, value in zip(new, values['features']):
                        if row['uid'] in context_values:
                            need(np.array_equal(value, context_values[row['uid']]), 'CIC_CONTEXT_CACHE_PARITY')
                        context_values[row['uid']] = value
                    receipts[spec['capture_id']] = receipt
        else:
            for spec, folder, material, known in materials.values():
                group = groups[spec['capture_id']]
                selected = {row['uid']: row for row in group}
                with progress.measure('RECENT_SNAPSHOTS_' + spec['key']):
                    captured = walk_long(spec, folder, material, api, tshark, progress,
                        selected=selected, known=known,
                        prefix=source_cfg['probe_frames'] if probe else None)
                    entries.update({e['uid']: e for e in captured})
                new = [r for r in group if probe or r['uid'] not in context_values]
                if new:
                    with progress.measure('CONTEXT8_' + spec['key']):
                        values, receipt = chronological_context(new, spec, material, progress, probe)
                        for uid, value in values.items():
                            if uid in context_values:
                                need(np.array_equal(value, context_values[uid]), 'HISTORY_CONTEXT_CACHE_PARITY')
                        context_values.update(values)
                        receipts[spec['key']] = receipt
        need(set(entries) == {r['uid'] for r in rows} == set(context_values), 'REFERENCE_FEATURE_UID_COVERAGE')
        contexts = np.stack([context_values[r['uid']] for r in rows])
        with progress.measure('REFERENCE_E3_Q14_' + pool):
            materialize(rows, [entries[r['uid']] for r in rows], cache, contexts, tensors,
                encoder, identity, progress, output/pool, require_new=probe, selection_sha=selection_sha)
        results[pool] = dict(feature=read(output/pool/'FEATURE_RECEIPT.json'), context=receipts)
        if probe and pool == 'UNSW_DEV':
            write(output.parent/'SNAPSHOT_REGRESSION.json', dict(status='PASS',
                 rows=len(rows), rows_sha256=asset(output/(pool+'_HISTORY.jsonl.gz'))['sha256'],
                 receipt=results[pool]['feature'], phase='REAL_UNSW_DECODER_SNAPSHOT_ENCODING'))
    write(output/'CANDIDATE.json', dict(status='PROBE_FEATURES_SEALED' if probe else 'CANDIDATE_SEALED',
         selection=asset(output/'SELECTION.json'), pools=results, verified_inputs=store.checked,
         history_features_only=True, query_access=False, model_training=False))
    return results
