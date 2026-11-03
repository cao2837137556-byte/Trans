"""Real SQLite transactions with deterministic scan/commit interleaving.

All inputs are generated. No real PCAP, tokenizer, encoder or optimizer runs.
"""
import contextlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import continuous_features_engineering_v1 as features
import engineering_progress_v1 as progress
from scratch_registry_v1 import may_disappear, register_sqlite_sidecars
from test_engineering_lifecycle_v1 import Progress
from test_engineering_state_storage_v1 import POLICY, generated, target


class SnapshotJournalRaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()

    def scan_across_commit(self,database,path,commit):
        """Enumerate the real journal, commit, then stat that enumerated path."""
        journal=Path(str(path)+'-journal')
        self.assertTrue(journal.exists())
        enumerated=list(self.root.rglob('*'));self.assertIn(journal,enumerated)
        def entries(_folder,_pattern):
            commit()
            self.assertFalse(journal.exists())
            yield from enumerated
        with patch.object(Path,'rglob',entries):
            return progress.disk_bytes(self.root)

    def transaction(self,name):
        path=self.root/name;db=sqlite3.connect(str(path));self.addCleanup(db.close)
        self.assertEqual(db.execute('PRAGMA journal_mode=DELETE').fetchone()[0],'delete')
        db.execute('CREATE TABLE payload(value INTEGER)');db.execute('INSERT INTO payload VALUES(7)')
        return path,db

    def test_unregistered_real_commit_reproduces_original_failure(self):
        path,db=self.transaction('unregistered.sqlite')
        with self.assertRaises(FileNotFoundError):self.scan_across_commit(db,path,db.commit)
        self.assertEqual(db.execute('SELECT value FROM payload').fetchone(),(7,))

    def test_registered_real_commit_survives_and_live_journal_is_counted(self):
        path,db=self.transaction('persisted.sqlite');register_sqlite_sidecars(path)
        journal=Path(str(path)+'-journal')
        self.assertGreater(journal.stat().st_size,0)
        self.assertEqual(progress.disk_bytes(self.root),path.stat().st_size+journal.stat().st_size)
        self.assertEqual(self.scan_across_commit(db,path,db.commit),path.stat().st_size)
        self.assertEqual(db.execute('SELECT value FROM payload').fetchone(),(7,))

    def test_main_database_and_directory_disappearance_still_fail(self):
        folder=self.root/'spool';folder.mkdir();path=folder/'snapshots.sqlite'
        path.touch();register_sqlite_sidecars(path)
        self.assertFalse(may_disappear(path));self.assertFalse(may_disappear(folder))
        path.unlink()
        with patch.object(Path,'rglob',return_value=iter([path])):
            with self.assertRaises(FileNotFoundError):progress.disk_bytes(self.root)
        folder.rmdir()
        with patch.object(Path,'rglob',return_value=iter([folder])):
            with self.assertRaises(FileNotFoundError):progress.disk_bytes(self.root)

    def test_only_exact_sidecars_ignore_missing_and_permission_errors_remain(self):
        path=self.root/'snapshots.sqlite';path.touch();register_sqlite_sidecars(path)
        for suffix in ('-journal','-wal','-shm'):
            with self.subTest(suffix=suffix),patch.object(Path,'rglob',return_value=iter([Path(str(path)+suffix)])):
                self.assertEqual(progress.disk_bytes(self.root),0)
        for name in ('other.sqlite-journal','snapshots.sqlite-journal-copy','receipt.json'):
            with self.subTest(name=name),patch.object(Path,'rglob',return_value=iter([self.root/name])):
                with self.assertRaises(FileNotFoundError):progress.disk_bytes(self.root)
        journal=Path(str(path)+'-journal')
        with patch.object(Path,'rglob',return_value=iter([journal])), \
             patch.object(Path,'stat',side_effect=PermissionError('denied')):
            with self.assertRaises(PermissionError):progress.disk_bytes(self.root)

    def test_actual_spool_registers_before_schema_and_survives_commit_scan(self):
        row=generated(1,0);api=features.prep.old.legacy_runtime()
        metadata=dict(target(row,api),fit_role='FIT',label=0,device='aa',component_id='g')
        raw=self.root/'generated.raw';raw.write_bytes(b'generated only; never decoded')
        spec=dict(capture_id='generated',sha256='fixture',expected_packets=1,path=str(raw))
        runtime=dict(synthetic_only=True,known_macs=['aa'],state_storage=POLICY,tshark='NEVER')
        out=self.root/'spool';path=out/'snapshots.sqlite';journal=Path(str(path)+'-journal')
        seen=[];test=self
        class InterleavedConnection(sqlite3.Connection):
            def execute(self,sql,*args,**kwargs):
                if sql.startswith('CREATE TABLE snapshots'):
                    test.assertTrue(may_disappear(journal))
                    test.assertFalse(may_disappear(path));test.assertFalse(may_disappear(out))
                return super().execute(sql,*args,**kwargs)
            def commit(self):
                commit=super().commit
                if journal.exists():
                    seen.append(test.scan_across_commit(self,path,commit))
                else:commit()
        original_connect=sqlite3.connect
        def connect(filename,*args,**kwargs):
            if Path(filename).resolve()==path:
                kwargs['factory']=InterleavedConnection
            return original_connect(filename,*args,**kwargs)
        @contextlib.contextmanager
        def decoded(*args):yield [row]
        example=dict(input_ids=[[65537,21,1,61,1,65,3,1025,1,1,1,1,1]],
            attention_mask=[[1]*13],dataset_burst_sizes=[12],protocol=6)
        with patch.object(features,'e3_runtime',return_value=(None,)*5), \
             patch.object(features,'decode',decoded),patch.object(features,'tokenize',return_value=example), \
             patch.object(features.sqlite3,'connect',connect):
            features.spool(self.root,out,{'LEARN':[metadata]},[spec],runtime,Progress())
        self.assertGreaterEqual(len(seen),2)  # snapshot commit and batch assignment commit
        with contextlib.closing(original_connect(str(path))) as db:
            self.assertEqual(db.execute('SELECT uid,batch_id FROM snapshots').fetchall(),[(metadata['uid'],0)])
        self.assertFalse(journal.exists());features.c.verify(out)


if __name__=='__main__':unittest.main()
