"""Real SQLite, frozen RecentState, actual process death; no model calls."""
from collections import Counter
import io
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import types
import unittest

from streaming import ROOT
sys.path.insert(0, str(ROOT/'repo/ood'))
from continuous_input_v3 import RecentState
from spill_mapping_v1 import SpillMap
from checkpoint import PackedRoleSpool, canonical, read_json
from replay_resume import Checkpoints, StateUnpickler, snapshots, seed_role


def packet(frame):
    return {'frame.number': str(frame), 'frame.time_epoch': str(frame/10), 'frame.len': '74',
        'frame.cap_len': '74', 'eth.src': 'aa', 'eth.dst': 'bb', 'ip.src': '1.1.1.1',
        'ip.dst': '2.2.2.2', 'ip.version': '4', 'ip.proto': '17', 'ip.hdr_len': '20',
        'ip.dsfield': '0', 'ip.len': '60', 'ip.flags': '0', 'ip.ttl': '64', 'ip.frag_offset': '0',
        'udp.srcport': str(1234+frame%3), 'udp.dstport': '80', 'udp.length': '40'}


def fixture(root, suffix='a'):
    expected = {str(i): dict(uid=str(i), frame=i, protocol=17) for i in range(1, 13)}
    spool = PackedRoleSpool(root/'spool', {'fixture': 'unchanged'}, 'UDP', sorted(expected))
    context = types.SimpleNamespace(frame=0, capture='fixture', known={'aa'}, required=frozenset({'aa'}),
        max_states=100, previous_ns=None, reasons=Counter(), poisoned={('old',)}, tainted=set(),
        retired={('r',): (123, 1)}, events=[], last_seen={}, query_allowed=True, query_reason='VALID',
        states=SpillMap(root/(suffix+'.sqlite'), 1), api=None)
    return spool, context, expected


def advance(context, spool, first, last):
    for frame in range(first, last+1):
        key = ('key', frame%3)
        if key not in context.states: context.states[key] = RecentState('aa', key, 17)
        state = context.states[key]; state.append(packet(frame))
        flow, numbers, provenance = state.snapshot()
        snapshot = dict(uid=str(frame), row=dict(uid=str(frame), frame=frame, protocol=17),
                        body=dict(flow=flow, state=numbers, provenance=provenance), q14=[0.]*14)
        spool.append(snapshot)
        context.frame = frame; context.previous_ns = frame*100000000
        context.last_seen[key] = context.previous_ns; context.reasons['VALID'] += 1


def state_values(context):
    return {str(key): canonical(context.states[key].snapshot()) for key in context.states}


def crash_child(root, stage):
    spool, context, expected = fixture(root, 'child')
    manager = Checkpoints(root/'checkpoints', spool, expected)
    saved = manager.load(); manager.restore_spool(saved); manager.restore_context(context, saved)
    advance(context, spool, saved[1]['frame']+1, 6)
    manager.failpoint = lambda at: os._exit(77) if at == stage else None
    manager.save(context)
    raise AssertionError('Failure point not exercised')


class ReplayResumeTests(unittest.TestCase):
    def test_partial_checkpoint_can_seed_a_new_output_without_editing_source(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spool,ctx,expected=fixture(root)
            advance(ctx,spool,1,3);Checkpoints(root/'checkpoints',spool,expected).save(ctx);ctx.states.close()
            source=root/'source';shutil.copytree(root/'spool',source/'spools/UDP')
            shutil.copytree(root/'checkpoints',source/'replay_checkpoints/UDP')
            before=(source/'replay_checkpoints/UDP/CURRENT.json').read_bytes()
            target=root/'target';seed_role(source,target,'UDP',{'fixture':'unchanged'},expected)
            seeded=PackedRoleSpool(target/'spools/UDP',{'fixture':'unchanged'},'UDP',sorted(expected))
            unused,ctx,_=fixture(target)
            manager=Checkpoints(target/'replay_checkpoints/UDP',seeded,expected)
            saved=manager.load();manager.restore_spool(saved);manager.restore_context(ctx,saved)
            self.assertEqual(ctx.frame,3)
            advance(ctx,seeded,4,12);seeded.complete(generator_exhausted=True,raw_final_identity_pass=True)
            ctx.states.close()
            self.assertEqual((source/'replay_checkpoints/UDP/CURRENT.json').read_bytes(),before)

    def test_partial_spool_without_context_checkpoint_cannot_seed(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spool,ctx,expected=fixture(root)
            advance(ctx,spool,1,3);spool._flush();ctx.states.close()
            source=root/'source';shutil.copytree(root/'spool',source/'spools/UDP')
            with self.assertRaisesRegex(ValueError,'DURABLE_CONTEXT_REQUIRED'):
                seed_role(source,root/'target','UDP',{'fixture':'unchanged'},expected)

    def test_frozen_states_ledgers_and_snapshot_suffix_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spool, ctx, expected = fixture(root)
            advance(ctx, spool, 1, 6)
            manager = Checkpoints(root/'checkpoints', spool, expected); manager.save(ctx)
            advance(ctx, spool, 7, 12)
            oracle = state_values(ctx); spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
            values = {uid: canonical(spool.load(uid)) for uid in expected}; ctx.states.close()
            # Separate output spool containing the same committed prefix files.
            import shutil
            other = root/'resume'; other.mkdir(); shutil.copytree(root/'spool', other/'spool')
            (other/'spool/COMPLETE.json').unlink()
            shutil.copytree(root/'checkpoints', other/'checkpoints')
            resumed, ctx, expected = fixture(other)
            manager = Checkpoints(other/'checkpoints', resumed, expected)
            saved = manager.load(); manager.restore_spool(saved); manager.restore_context(ctx, saved)
            self.assertEqual(ctx.frame, 6); self.assertEqual(ctx.poisoned, {('old',)})
            self.assertEqual(ctx.retired, {('r',): (123, 1)})
            advance(ctx, resumed, 7, 12)
            self.assertEqual(state_values(ctx), oracle)
            resumed.complete(generator_exhausted=True, raw_final_identity_pass=True)
            self.assertEqual({uid: canonical(resumed.load(uid)) for uid in expected}, values)
            ctx.states.close()

    def test_real_process_death_before_or_after_commit(self):
        for stage in ('after_payload', 'before_commit', 'after_commit'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); spool, ctx, expected = fixture(root)
                advance(ctx, spool, 1, 3); Checkpoints(root/'checkpoints', spool, expected).save(ctx)
                ctx.states.close()
                result = subprocess.run([sys.executable, '-B', __file__, '--crash', str(root), stage], timeout=30,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 77, result.stderr)
                spool, ctx, expected = fixture(root, 'resume')
                manager = Checkpoints(root/'checkpoints', spool, expected); saved = manager.load()
                self.assertEqual(saved[1]['frame'], 6 if stage == 'after_commit' else 3)
                manager.restore_spool(saved); manager.restore_context(ctx, saved)
                advance(ctx, spool, ctx.frame+1, 12)
                spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
                self.assertEqual(len(list(spool.headers())), 12); ctx.states.close()

    def test_tampered_context_or_database_rejected_before_deserialization(self):
        for name in ('context.pickle', 'states.sqlite'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); spool,ctx,expected=fixture(root)
                advance(ctx,spool,1,3); manager=Checkpoints(root/'checkpoints',spool,expected);manager.save(ctx)
                ctx.states.close();directory,_=manager.load()
                with (directory/name).open('ab') as out:out.write(b'tamper')
                with self.assertRaisesRegex(ValueError,'PAYLOAD_SHA'):manager.load()

    def test_arbitrary_pickle_globals_forbidden(self):
        with self.assertRaisesRegex(ValueError, 'GLOBAL_FORBIDDEN'):
            StateUnpickler(io.BytesIO(pickle.dumps(os.system))).load()

    def test_incomplete_selected_prefix_cannot_be_checkpointed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spool,ctx,expected=fixture(root)
            advance(ctx,spool,1,3);ctx.frame=4
            with self.assertRaisesRegex(ValueError,'ATOMIC_BOUNDARY'):
                Checkpoints(root/'checkpoints',spool,expected).save(ctx)
            ctx.states.close()

    def test_changed_binding_cannot_load_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spool,ctx,expected=fixture(root)
            advance(ctx,spool,1,3);Checkpoints(root/'checkpoints',spool,expected).save(ctx);ctx.states.close()
            other=PackedRoleSpool(root/'other',{'fixture':'different'},'UDP',sorted(expected))
            with self.assertRaisesRegex(ValueError,'BINDING_CHANGED'):Checkpoints(root/'checkpoints',other,expected)


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--crash':crash_child(Path(sys.argv[2]),sys.argv[3])
    else:unittest.main(verbosity=2)
