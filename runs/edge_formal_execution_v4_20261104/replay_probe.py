"""Same-runtime real UDP16: actual exit after frame8 checkpoint, then restore."""
import argparse
import os
from pathlib import Path
import sys
import time
import worker
from checkpoint import PackedRoleSpool, atomic_json, canonical, require, sha
from streaming import ROOT, module
from worker import Guard, read
from replay_resume import snapshots
from progress_io import install
from runtime_control import bounded_process


def child(spec_path, phase):
    spec = read(spec_path); output = Path(spec['output']); scratch = Path(spec['scratch'])/phase
    scratch.mkdir(exist_ok=False)
    guard = Guard(output, scratch, dict(spec['budget'], wall_seconds=spec['deadline']-time.monotonic()), formal=False)
    adapter = module('_probe_edge', ROOT/'runs/edge_external_test1_engineering_v1_20261103/adapter/edge_adapter.py')
    replay = module('_probe_replay', ROOT/'runs/edge_preflight_io_repair_v1_20261103/replay_io.py')
    expected = {r['uid']: r for r in spec['rows']}
    spool = PackedRoleSpool(output/'spool', spec['binding'], 'UDP', sorted(expected))
    with install(replay, worker, output), replay.install(adapter, output=output/'replay_status',
            cache_root=output/'unused_cache', scratch_root=scratch, deadline=spec['deadline']-120,
            guard=guard, heartbeat=guard.progress) as patched:
        patched.active = dict(role='UDP', frame=0, start=time.monotonic(), append_seconds=0.,
                              decoder_next_seconds=0., selected_persisted=0)
        def fault(stage):
            if phase == 'crash' and stage == 'after_commit': os._exit(76)
        stream = snapshots(adapter, patched, spool, expected, output/'checkpoints', 'UDP',
            [r['frame'] for r in spec['rows']], output/('decode_'+phase),
            checkpoint_frame=8, failpoint=fault, value=spec['source_card'], tshark=Path(spec['tshark']),
            deadline=spec['deadline']-120)
        try:
            for snapshot in stream: spool.append(snapshot)
        finally: stream.close()
        require(phase == 'resume', 'REAL_PROBE_CRASH_NOT_EXERCISED')
        require(sha(spec['source_card']['raw_inputs']['UDP']['path']) ==
                spec['source_card']['raw_inputs']['UDP']['sha256'], 'PROBE_FINAL_RAW_SHA')
        spool.complete(generator_exhausted=True, raw_final_identity_pass=True)


def run(output, scratch, source_card, tshark, baseline, deadline, budget):
    output = Path(output)/'real_udp_resume_probe'; output.mkdir()
    rows = [h['row'] for h in baseline.headers()]
    require(sorted(r['frame'] for r in rows) == list(range(1, 17)), 'REAL_PROBE_FIXED_UDP16')
    binding = dict(scope='REAL_UDP16_REPLAY_CHECKPOINT_PROBE', source_sha256=source_card['raw_inputs']['UDP']['sha256'])
    scratch = Path(scratch)/'real_udp_probe'; scratch.mkdir()
    spec = dict(output=str(output), scratch=str(scratch), source_card=source_card, tshark=tshark,
                rows=rows, binding=binding, deadline=deadline, budget=budget)
    path = output/'SPEC.json'; atomic_json(path, spec)
    for phase, expected in (('crash', 76), ('resume', 0)):
        code = bounded_process([sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()),
            '--spec', str(path), '--phase', phase], output/(phase+'.log'), deadline-120, session=True)
        require(code == expected, 'REAL_REPLAY_RECOVERY_CHILD:'+phase+':'+str(code))
    spool = PackedRoleSpool(output/'spool', binding, 'UDP', sorted(r['uid'] for r in rows))
    require(spool.is_complete(), 'REAL_REPLAY_RESUMED_COMPLETE')
    for row in rows:
        require(canonical(spool.load(row['uid'])) == canonical(baseline.load(row['uid'])),
                'REAL_REPLAY_UNINTERRUPTED_SNAPSHOT_PARITY')
    attempt = read(output/'checkpoints/LAST_ATTEMPT.json')
    require(attempt['resume_from_frame'] == 8 and attempt['numerical_frames_appended'] == 8,
            'REAL_REPLAY_PREFIX_NOT_RECOMPUTED')
    receipt = dict(status='PASS_REAL_REPLAY_CRASH_RESUME', actual_exit=76, checkpoint_frame=8,
        resumed_numerical_frames=8, total_frames=16, all_snapshots_value_exact=True,
        raw_decoder_replayed_from_frame_one=True, same_frozen_numerical_core=True)
    atomic_json(output/'RESULT.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--phase', choices=('crash', 'resume'), required=True)
    args = parser.parse_args(); child(args.spec, args.phase)
