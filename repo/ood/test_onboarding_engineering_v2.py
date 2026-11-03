"""Generated-only parity checks for storage changes; no real assets or training."""
import contextlib
import copy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import numpy as np
import indexed_features_v1 as ix
import constrained_onboarding_reference_v1 as old
import constrained_onboarding_reference_v2 as new
import constrained_onboarding_runner_v1 as old_runner
import constrained_onboarding_runner_v2 as new_runner
from test_constrained_onboarding_reference_v1 import SPEC, REGISTRY, DECODER, stream_packet
from test_constrained_onboarding_integration_v1 import fixture, PROTOCOL

POLICY=dict(resident_contexts=1,resident_legacy_prefixes=1,resident_candidate_snapshots=1)


def compare_tree(test,a,b):
    """Compare scientific payloads, not ZIP/GZIP timestamps or transport seals."""
    files={p.relative_to(a) for p in a.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
    test.assertEqual(files,{p.relative_to(b) for p in b.rglob('*') if p.is_file() and p.name!='SHA256SUMS'})
    for rel in sorted(files):
        left,right=a/rel,b/rel
        with test.subTest(file=str(rel)):
            if left.suffix=='.npz':
                with np.load(left,allow_pickle=False) as x,np.load(right,allow_pickle=False) as y:
                    test.assertEqual(x.files,y.files)
                    for key in x.files:np.testing.assert_array_equal(x[key],y[key])
            elif left.suffix=='.npy':np.testing.assert_array_equal(np.load(left),np.load(right))
            elif left.suffix=='.gz':test.assertEqual(gzip.decompress(left.read_bytes()),gzip.decompress(right.read_bytes()))
            else:test.assertEqual(left.read_bytes(),right.read_bytes())


class IndexedFeatureTests(unittest.TestCase):
    def test_nested_rows_negative_duplicates_columns_and_read_only(self):
        base=np.arange(120,dtype=np.float32).reshape(12,10)
        a=ix.take(base,[7,1,-1,7,0],slice(1,9,2)); b=ix.take(a,[3,-3,0])
        expected=base[[7,1,-1,7,0],1:9:2][[3,-3,0]]
        np.testing.assert_array_equal(b[:],expected)
        self.assertIs(b.base,base);self.assertFalse(b[:].flags.writeable)
        self.assertFalse(b.indices.flags.writeable)
        np.testing.assert_array_equal(b[1],expected[1])
        self.assertEqual(ix.take(base,[]).shape,(0,10))
        with self.assertRaisesRegex(TypeError,'EXPLICIT_BATCH_REQUIRED'):np.asarray(b)
        for selection in ([12],[-13],[1.5],[True]):
            with self.assertRaises((IndexError,ValueError)):ix.take(base,selection)

    def test_chunk_hash_matches_contiguous_bytes_without_full_read(self):
        base=np.arange(3000,dtype=np.float32).reshape(300,10)
        indexed=ix.take(base,np.arange(299,-1,-1),slice(2,8))
        expected=base[::-1,2:8].copy();a=hashlib.sha256();b=hashlib.sha256()
        a.update(str(expected.dtype).encode());a.update(str(expected.shape).encode());a.update(expected.tobytes())
        ix.hash_matrix(b,indexed,block_rows=7)
        self.assertEqual(a.hexdigest(),b.hexdigest());self.assertEqual(indexed.peak_read_rows,7)
        with self.assertRaises(ValueError):ix.hash_matrix(b,indexed,block_rows=0)

    def test_mmap_reads_follow_source_without_duplicating_pool(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'base.npy';np.save(path,np.arange(100,dtype=np.float32).reshape(10,10))
            base=np.load(path,mmap_mode='r');indexed=ix.take(base,[9,2,3])
            self.assertTrue(np.shares_memory(indexed.base,base))
            np.testing.assert_array_equal(indexed[[2,0]],base[[3,9]])
            del indexed,base


class ReferenceStorageTests(unittest.TestCase):
    def test_cleanup_secondary_failure_preserves_primary_and_closes_other_stores(self):
        from reference_storage_v1 import PreparedCapture
        with tempfile.TemporaryDirectory() as td:
            working=PreparedCapture(POLICY,td);a=working.snapshots(1);b=working.snapshots(2)
            close=a.close
            def fail_after_close():close();raise OSError('secondary close error')
            with patch.object(a,'close',side_effect=fail_after_close):
                try:
                    with working:raise ValueError('primary error')
                except ValueError as exc:
                    self.assertIn('secondary close error',str(exc.engineering_cleanup_errors))
                else:self.fail('original exception lost')
            self.assertTrue(b.closed);self.assertFalse(working.folder.exists())

    def packets(self):
        # Many components, revisits after eviction, both protocols, cross-flow
        # time reversal, and both independently closed observation windows.
        times=[(0,1200,6),(10,1201,17),(20,1202,6),(5,1203,6),
               (30,1200,6),(35,1201,17),(3599,1202,6),(3600,1200,6),
               (3601,1201,17),(7000,1202,6),(7199,1203,6),(7201,1204,6)]
        return [stream_packet(i,t,port=p,proto=proto) for i,(t,p,proto) in enumerate(times,1)]

    def test_all_census_candidates_selections_and_saved_payloads_exact(self):
        packets=self.packets();before=old.prepare_decoded_capture(packets,SPEC,REGISTRY,t0=0.,decoder_identity=DECODER)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with new.prepare_decoded_capture(packets,SPEC,REGISTRY,t0=0.,decoder_identity=DECODER,
                    storage_policy=POLICY,working_directory=root) as after:
                for duration in (3600,7200):
                    self.assertEqual(before[duration]['rows'],after[duration]['rows'])
                    self.assertEqual(before[duration]['receipt'],after[duration]['receipt'])
                    self.assertEqual(before[duration]['snapshots'],dict(after[duration]['snapshots']))
                old.save_prepared(root/'old',before);new.save_prepared(root/'new',after)
                compare_tree(self,root/'old',root/'new')
                stats=after.observation()['stores']
                self.assertGreater(stats['contexts.sqlite']['spills'],0)
                self.assertGreater(stats['snapshots_3600.sqlite']['loads'],0)
                self.assertTrue(all(s['peak_resident']<=1 for s in stats.values()))
            self.assertFalse(list(root.glob('reference-working-*')))

    def test_failed_preparation_cleans_private_storage(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);keep=root/'keep';keep.write_text('unrelated')
            with self.assertRaisesRegex(RuntimeError,'INCOMPLETE_WINDOW'):
                new.prepare_decoded_capture(self.packets()[:4],SPEC,REGISTRY,t0=0.,decoder_identity=DECODER,
                    storage_policy=POLICY,working_directory=root)
            self.assertEqual(list(root.iterdir()),[keep])

    def test_raw_entry_drains_stream_and_cleans_storage_on_success_and_failure(self):
        import legacy_reference_sample_prepare_v1 as prep
        packets=self.packets();packets.append(stream_packet(len(packets)+1,7300))
        @contextlib.contextmanager
        def decoder(*args):yield iter(packets)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);raw=root/'generated.pcap';raw.write_bytes(b'generated test only')
            config=dict(synthetic_only=True,capture=dict(SPEC,path=str(raw),sha256=new.sha(raw),expected_packets=len(packets)),
                device_registry=REGISTRY,state_storage=POLICY,limits=dict(wall_seconds=60,memory_gib=2,disk_gib=1))
            for wrong_count in (False,True):
                dest=root/str(wrong_count);progress=SimpleNamespace(tick=Mock(),stop=Mock())
                changed=copy.deepcopy(config)
                if wrong_count:changed['capture']['expected_packets']+=1
                run=lambda:new.prepare_raw_capture(changed,dest,decoder_factory=decoder,
                    event_runtime=prep.old.legacy_runtime(),progress_factory=lambda *a:progress,decoder_identity=DECODER)
                if wrong_count:
                    with self.assertRaisesRegex(RuntimeError,'RAW_COMPLETE_PACKET_COUNT'):run()
                    self.assertEqual(progress.stop.call_args.args[0],'STOPPED_NO_RETRY')
                else:
                    run();self.assertEqual(progress.stop.call_args.args[0],'COMPLETE')
                    self.assertEqual(json.loads((dest/'raw_receipt.json').read_text())['packets'],len(packets))
                self.assertFalse(list(dest.glob('reference-working-*')))


class CompleteOnboardingParityTests(unittest.TestCase):
    def test_indexed_source_target_banks_and_nested_splits_match_old_runner(self):
        original=fixture();changed=copy.deepcopy(original)
        assets=[changed['source_fit'],changed['source_cal'],changed['source_references']]
        for target in changed['targets'].values():assets.extend([target,*target['banks'].values()])
        for asset in assets:
            for key in ('e3','q14'):
                arr=asset[key];base=np.concatenate([arr,arr[::-1]],axis=0)
                asset[key]=ix.take(base,list(range(len(arr))))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            a=old_runner.run_development(original,root/'old',PROTOCOL)
            b=new_runner.run_development(changed,root/'new',PROTOCOL)
            self.assertEqual(a,b);compare_tree(self,root/'old',root/'new')


if __name__=='__main__':unittest.main()
