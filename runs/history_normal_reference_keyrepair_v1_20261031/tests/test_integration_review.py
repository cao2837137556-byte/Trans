"""Independent regression checks for deployment path/identity separation."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from hnr.common import PACKAGE, read, write
from hnr.history import create_census, walk_decoded
from continuous_input_engineering_v1 import Contexts
import legacy_reference_sample_prepare_v1 as prep
import numpy as np

if __package__:
    from .test_history import packet, index_for, Progress
else:
    from test_history import packet, index_for, Progress


def entrypoint():
    spec = importlib.util.spec_from_file_location('_history_entry_review',PACKAGE/'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeploymentBindingsReviewTests(unittest.TestCase):
    def test_relocated_asset_normalizer_payload_cannot_change(self):
        config = copy.deepcopy(read(PACKAGE/'config/EXECUTION.json'))
        assets = copy.deepcopy(read(PACKAGE/'config/ASSETS.json'))
        assets['calibration']['normalizer']['sha256'] = '0'*64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'ASSETS.json'
            write(path,assets)
            config['assets_manifest'] = str(path)
            with self.assertRaisesRegex(ValueError,'ASSET_SCIENTIFIC_BINDING_CHANGED'):
                entrypoint().validate_config_bindings(config)

    def test_asset_path_only_relocation_keeps_frozen_payload(self):
        config = copy.deepcopy(read(PACKAGE/'config/EXECUTION.json'))
        assets = copy.deepcopy(read(PACKAGE/'config/ASSETS.json'))
        assets['calibration']['normalizer']['path'] = '/relocated/frozen/normalizer.npz'
        config['encoder']['normalizer'] = '/relocated/frozen/normalizer.npz'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'ASSETS.json'
            write(path,assets)
            config['assets_manifest'] = str(path)
            entrypoint().validate_config_bindings(config)

    def test_production_scale_microsecond_times_and_json_selection_roundtrip(self):
        # Generated fields at a long UNIX epoch exercise Decimal(us)/1e6,
        # descriptor Decimal(ns)/1e9, and JSON list/float round trips together.
        start = 1484092799863312
        times = [start-1000000,start,start+4800584]
        packets = [packet(i+1,t) for i,t in enumerate(times)]
        index = index_for(times)
        order = np.arange(len(times),dtype=np.uint32)
        binding = dict(bank_end_frame=2,reference_end_us=start,packets=3)
        spec = dict(capture_id='generated-microsecond-review',owner='aa',
            partition='EXTERNAL_ARCHIVAL_EVALUATION',device='generated',
            display_name='generated',raw=dict(sha256='b'*64),normality_evidence='generated')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            db = create_census(folder/'census.sqlite')
            ctx = Contexts(spec['capture_id'],{'aa'},prep.old.legacy_runtime()[0],
                storage_path=folder/'pass1.sqlite',resident_contexts=2)
            try:
                walk_decoded(packets,spec,binding,index,order,'a'*64,ctx,Progress(),census=db)
            finally:
                ctx.close()
            selected = {uid:json.loads(body) for uid,body in db.execute('SELECT uid,body FROM candidates')}
            db.close()
            ctx = Contexts(spec['capture_id'],{'aa'},prep.old.legacy_runtime()[0],
                storage_path=folder/'pass2.sqlite',resident_contexts=2)
            snapshots = []
            try:
                walk_decoded(packets,spec,binding,index,order,'a'*64,ctx,Progress(),
                    selected=selected,snapshots=snapshots)
            finally:
                ctx.close()
            self.assertEqual(len(snapshots),3)
            self.assertEqual(snapshots[1]['row']['reference_end_us'],start)
            self.assertEqual(snapshots[-1]['body']['provenance']['query_time_ns'],times[-1]*1000)
            self.assertEqual(snapshots[-1]['body']['provenance']['episode_first_frame'],1)


if __name__ == '__main__':
    unittest.main()
