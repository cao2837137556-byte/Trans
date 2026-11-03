"""Synthetic regression tests for disk-scan cleanup races and inherited guards."""
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

import engineering_progress_v1 as progress
from scratch_registry_v1 import register_sqlite
from scratch_registry_v1 import may_disappear
from spill_mapping_v1 import SpillMap


class DiskScanTests(unittest.TestCase):
    def test_spill_initialization_failure_cleans_only_owned_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            database=Path(tmp)/'private.sqlite'
            with mock.patch('spill_mapping_v1.sqlite3.connect',side_effect=OSError('synthetic connect failure')):
                with self.assertRaisesRegex(OSError,'synthetic connect failure'):
                    SpillMap(database,1)
            self.assertFalse(database.exists())
            self.assertTrue(may_disappear(database))
            self.assertTrue(may_disappear(Path(str(database)+'-journal')))
            database.write_bytes(b'preserve existing data')
            with mock.patch('spill_mapping_v1.sqlite3.connect') as connect:
                with self.assertRaises(FileExistsError):SpillMap(database,1)
                connect.assert_not_called()
            self.assertEqual(database.read_bytes(),b'preserve existing data')

    def test_spill_schema_failure_closes_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            database=Path(tmp)/'private.sqlite';connection=mock.Mock()
            connection.execute.side_effect=RuntimeError('synthetic schema failure')
            with mock.patch('spill_mapping_v1.sqlite3.connect',return_value=connection):
                with self.assertRaisesRegex(RuntimeError,'synthetic schema failure'):
                    SpillMap(database,1)
            connection.close.assert_called_once_with()
            self.assertFalse(database.exists())

    def test_registered_sqlite_journal_and_directory_may_disappear(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); folder=root/'private'; folder.mkdir()
            database=folder/'state.sqlite'; database.write_bytes(b'')
            register_sqlite(database)
            database.unlink();folder.rmdir()
            vanished=[folder,database,Path(str(database)+'-journal'),Path(str(database)+'-wal'),Path(str(database)+'-shm')]
            with mock.patch.object(Path,'rglob',return_value=iter(vanished)):
                self.assertEqual(progress.disk_bytes(root),0)

    def test_unregistered_sqlite_and_other_files_still_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            database=root/'private'/'owned.sqlite';database.parent.mkdir();database.touch()
            register_sqlite(database)
            for name in ('unknown.sqlite','unknown.sqlite-journal','artifact.npy','private/receipt.json'):
                with self.subTest(name=name),mock.patch.object(Path,'rglob',return_value=iter([root/name])):
                    with self.assertRaises(FileNotFoundError):progress.disk_bytes(root)

    def test_registered_files_do_not_hide_permission_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);database=root/'owned.sqlite';database.touch();register_sqlite(database)
            with mock.patch.object(Path,'rglob',return_value=iter([database])), \
                 mock.patch.object(Path,'stat',side_effect=PermissionError('synthetic denied')):
                with self.assertRaises(PermissionError):progress.disk_bytes(root)

    def test_atomic_json_and_live_size_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);regular=root/'actual.bin';regular.write_bytes(b'12345')
            with mock.patch.object(Path,'rglob',return_value=iter([regular,root/'status.json.next'])):
                self.assertEqual(progress.disk_bytes(root),5)


class GuardTests(unittest.TestCase):
    def monitor(self,root,scope=None):
        value=object.__new__(progress.Progress)
        value.out=root;value.storage_scope=scope;value.error=None
        value.guard_lock=threading.RLock();value.started=0.;value.disk_at=0.
        value.limits=dict(memory_gib=1,disk_gib=1,wall_seconds=1000)
        value.rss=0;value.stage='SYNTHETIC';value.recorder=mock.Mock()
        return value

    def test_output_and_parent_scope_never_call_legacy_disk_scanner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);private=root/'private';private.mkdir()
            database=private/'state.sqlite';database.write_bytes(b'');register_sqlite(database)
            database.unlink()
            for scope in (None,root):
                with self.subTest(scope=scope):
                    value=self.monitor(root,scope)
                    with mock.patch.object(Path,'rglob',return_value=iter([Path(str(database)+'-journal')])), \
                         mock.patch.object(progress.time,'monotonic',return_value=100.), \
                         mock.patch.object(progress,'tree_rss',return_value=100), \
                         mock.patch.object(progress.shutil,'disk_usage',return_value=SimpleNamespace(free=2*1024**3)), \
                         mock.patch('legacy_unsw_archival_runtime_v2.disk_bytes',side_effect=AssertionError('legacy scan')):
                        value.guard()
                    value.recorder.observe.assert_called_once_with('SYNTHETIC',100)

    def test_original_guard_failures_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            cases=[('prior','PRIOR'),('stop','USER_STOP_REQUESTED'),('wall','WALL_TIME_LIMIT'),
                   ('rss','COMBINED_MEMORY_LIMIT'),('disk','OUTPUT_DISK_LIMIT'),('free','OUTPUT_DISK_FREE_LIMIT')]
            for kind,message in cases:
                with self.subTest(kind=kind):
                    value=self.monitor(root)
                    if kind=='prior':value.error='PRIOR'
                    if kind=='stop':(root/'STOP_REQUESTED').touch()
                    if kind=='wall':value.started=-2000
                    try:
                        with mock.patch.object(progress.time,'monotonic',return_value=100.), \
                             mock.patch.object(progress,'tree_rss',return_value=2*1024**3 if kind=='rss' else 1), \
                             mock.patch.object(progress,'disk_bytes',return_value=2*1024**3 if kind=='disk' else 0), \
                             mock.patch.object(progress.shutil,'disk_usage',return_value=SimpleNamespace(free=0 if kind=='free' else 2*1024**3)):
                            with self.assertRaisesRegex(RuntimeError,message):value.guard()
                    finally:
                        if kind=='stop':(root/'STOP_REQUESTED').unlink()

    def test_whole_scope_disk_limit_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);monitor=root/'monitor';monitor.mkdir()
            value=self.monitor(monitor,root)
            with mock.patch.object(progress.time,'monotonic',return_value=100.), \
                 mock.patch.object(progress,'tree_rss',return_value=1), \
                 mock.patch.object(progress,'disk_bytes',return_value=2*1024**3) as scan:
                with self.assertRaisesRegex(RuntimeError,'WORKING_DISK_LIMIT'):value.guard()
                scan.assert_called_once_with(root)


if __name__=='__main__':unittest.main()
