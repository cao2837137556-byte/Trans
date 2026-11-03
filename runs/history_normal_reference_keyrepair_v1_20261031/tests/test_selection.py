"""Generated metadata only: no real packet, feature, or score asset is opened."""
import importlib.util
import json
from pathlib import Path
import random
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hnr import selection
from hnr.common import HEIM, ROOT, TARGETS, digest, rows


def candidate(target, protocol, component, frame, role, timestamp=None):
    uid = digest([target['owner'], protocol, component, frame, role])
    return dict(uid=uid, device=target['device'], partition=target['partition'],
        owner=target['owner'], protocol=protocol, component_id=component,
        timestamp=float(frame if timestamp is None else timestamp), frame=frame,
        role=role, use='REFERENCE' if role in ('REF','HIST_REF') else 'QUERY', label=0,
        capture_id='generated-history', source_sha256='0'*64,
        reference_end=target['reference_end_us']/1e6,
        bank_end_frame=target['bank_end_frame'])


def census(path, values):
    db = sqlite3.connect(path)
    db.execute('''CREATE TABLE candidates(uid TEXT PRIMARY KEY,device TEXT,
        protocol INTEGER,component_id TEXT,timestamp REAL,frame INTEGER,
        role TEXT,rank TEXT,body TEXT)''')
    for row in values:
        db.execute('INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?)', (
            row['uid'],row['device'],row['protocol'],row['component_id'],
            row['timestamp'],row['frame'],row['role'],selection.point_rank(row['uid'])[0],
            json.dumps(row)))
    db.commit()
    db.close()


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def fixture(self):
        values, old = [], []
        for target in TARGETS.values():
            old.append(dict(device=target['device'],protocol=6,component_id='old'))
            for protocol in (6, 17):
                for component in ('old','new0','new1','new2','new3'):
                    for frame in (1,2,3,4):
                        values.append(candidate(target,protocol,component,frame,'HIST_REF'))
            for protocol in (6,17):
                for component in ('dev0','dev1','dev2','dev3'):
                    for frame in (6,7,8):
                        values.append(candidate(target,protocol,component,frame,'HIST_DEV'))
        return values, old

    def test_caps_new_component_priority_overflow_and_device_total_dev(self):
        values, old = self.fixture()
        census(self.folder/'census.sqlite', values)
        with patch.object(selection,'REF_CAP',3), patch.object(selection,'DEV_CAP',3):
            receipt = selection.select_candidates(self.folder/'census.sqlite',old,self.folder/'out')
        self.assertEqual(receipt['status'],'SELECTED')
        self.assertEqual(receipt['ref_rows']['rows'],18)
        self.assertEqual(receipt['dev_rows']['rows'],9)
        selected = list(rows(receipt['ref_rows']['path']))
        self.assertFalse(any(r['protocol']==6 and r['component_id']=='old' for r in selected))
        for group in receipt['groups']:
            self.assertLessEqual(group['selected_rows'],3)
            self.assertGreater(group['uncovered_components'],0)
            if group['role']=='HIST_DEV':
                self.assertIsNone(group['protocol'])
        self.assertFalse({r['uid'] for r in selected} &
                         {r['uid'] for r in rows(receipt['dev_rows']['path'])})

    def test_replay_independent_of_insertion_order(self):
        values, old = self.fixture()
        shuffled = values[:]
        random.Random(72).shuffle(shuffled)
        census(self.folder/'one.sqlite',values)
        census(self.folder/'two.sqlite',shuffled)
        with patch.object(selection,'REF_CAP',7),patch.object(selection,'DEV_CAP',5):
            one = selection.select_candidates(self.folder/'one.sqlite',old,self.folder/'one')
            two = selection.select_candidates(self.folder/'two.sqlite',old,self.folder/'two')
        for field in ('ref_rows','dev_rows'):
            self.assertEqual(one[field]['uid_sha256'],two[field]['uid_sha256'])
            self.assertEqual(list(rows(one[field]['path'])),list(rows(two[field]['path'])))

    def test_uniform_time_exact_frozen_ties_and_greedy_intervals(self):
        spec = importlib.util.spec_from_file_location('frozen_dense_binding',
            ROOT/'runs/dense_reference_matrix_v1_20261027/src/binding.py')
        binding = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(binding)
        target = next(iter(TARGETS.values()))
        generated = [candidate(target,6,'c',i+1,'HIST_REF',timestamp=t)
            for i,t in enumerate([0,0,0,1,2,2,4,4,4,4,5,9,10,10,100])]
        census(self.folder/'time.sqlite', generated)
        with sqlite3.connect(self.folder/'time.sqlite') as db:
            for count in range(1,len(generated)+1):
                actual = selection._uniform_time_db(db,target['device'],6,'HIST_REF','c',count)
                expected = [r['uid'] for r in binding._uniform_time(generated,count,selection.SALT)]
                self.assertEqual(actual,expected)

    def test_empty_role_and_no_new_component_are_explicit_stops(self):
        target = next(iter(TARGETS.values()))
        value = candidate(target,6,'old',1,'HIST_REF')
        census(self.folder/'empty.sqlite',[value])
        result = selection.select_candidates(self.folder/'empty.sqlite',
            [dict(device=target['device'],protocol=6,component_id='old')],self.folder/'empty')
        statuses = {r['status'] for r in result['stops']}
        self.assertIn('STOP_NO_NEW_COMPONENT',statuses)
        self.assertIn('STOP_EMPTY_HIST_DEV',statuses)
        self.assertIn('STOP_EMPTY_HIST_REF',statuses)

    def test_explicit_single_device_scope_does_not_stop_absent_other_members(self):
        target = next(iter(TARGETS.values()))
        values = [candidate(target,6,'new',1,'HIST_REF'),
                  candidate(target,17,'dev',2,'HIST_DEV')]
        census(self.folder/'one_device.sqlite',values)
        result = selection.select_candidates(self.folder/'one_device.sqlite',[],
            self.folder/'one_device',devices=[target['device']])
        self.assertEqual(result['status'],'SELECTED')
        self.assertEqual(result['device_scope'],[target['device']])
        self.assertEqual({r['device'] for r in result['groups']},{target['device']})

    def test_rank_tamper_is_rejected_even_on_unselected_row(self):
        values,old = self.fixture()
        census(self.folder/'bad.sqlite',values)
        with sqlite3.connect(self.folder/'bad.sqlite') as db:
            db.execute('UPDATE candidates SET rank=? WHERE uid=?',('f'*64,values[-1]['uid']))
        with self.assertRaisesRegex(ValueError,'CENSUS_INVALID_IDENTITY'):
            selection.select_candidates(self.folder/'bad.sqlite',old,self.folder/'bad')

    def test_dual_cutoff_preserves_original_metadata_and_history_frames(self):
        target = next(iter(TARGETS.values()))
        base = candidate(target,6,'old',1,'HIST_REF',timestamp=1550000000.)
        base.update(uid='1'*64,reference_end=1550000001.,bank_end_frame=17,capture_id='old-capture')
        history = candidate(target,17,'new',2,'HIST_REF',timestamp=target['reference_end_us']/1e6-1)
        output = selection.bank_views([base],[history],'UNSW_DEV')
        self.assertEqual(output['AB_BANK'][0],base)
        ab, dev = output['AB_BANK'][1],output['HIST_DEV_BANK'][0]
        self.assertEqual(ab['reference_end'],base['reference_end'])
        self.assertEqual(dev['reference_end'],target['reference_end_us']/1e6)
        self.assertEqual(ab['bank_end_frame'],target['bank_end_frame'])
        self.assertEqual(dev['bank_end_frame'],target['bank_end_frame'])
        self.assertEqual(history['reference_end'],dev['reference_end'])
        with self.assertRaisesRegex(ValueError,'HISTORICAL_UID_OVERLAP'):
            selection.bank_views([base],[base],'UNSW_DEV')
        other = dict(base,uid='2'*64,reference_end=base['reference_end']+1)
        with self.assertRaisesRegex(ValueError,'COMPLETE_BANK_END_MISMATCH'):
            selection.bank_views([base,other],[],'UNSW_DEV')

    def test_heim_reuse_allows_original_optional_frame_cutoff_absence(self):
        base = dict(uid='a',partition=HEIM['partition'],device=HEIM['device'],
            reference_end=200.,capture_id='original')
        historical = dict(uid='b',partition=HEIM['partition'],device=HEIM['device'],
            reference_end=100.,capture_id='old-capture',timestamp=99.,frame=5,
            use='REFERENCE',label=0)
        result = selection.bank_views([base],[historical],'CIC_DEV')
        self.assertEqual(result['HIST_DEV_BANK'],[])
        self.assertNotIn('bank_end_frame',result['AB_BANK'][1])
        self.assertEqual(result['AB_BANK'][1]['uid'],'b')


if __name__ == '__main__':
    unittest.main()
