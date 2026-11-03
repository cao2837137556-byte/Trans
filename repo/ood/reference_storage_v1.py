"""Lifetime of private working databases for one normal-reference preparation."""
from collections.abc import Mapping
from pathlib import Path
import sys
import tempfile
from spill_mapping_v1 import SpillMap,validate_policy


class SnapshotLookup(Mapping):
    def __init__(self,rows,store):
        self.uid_keys={row['uid']:(row['owner'],row['component_id']) for row in rows}
        self.store=store

    def __getitem__(self,uid):return self.store[self.uid_keys[uid]]
    def __iter__(self):return iter(self.uid_keys)
    def __len__(self):return len(self.uid_keys)


class PreparedCapture(dict):
    def __init__(self,policy,working_directory=None):
        super().__init__();self.policy=validate_policy(policy)
        if working_directory is not None:Path(working_directory).mkdir(parents=True,exist_ok=True)
        self.folder=Path(tempfile.mkdtemp(prefix='reference-working-',dir=working_directory)).resolve()
        self.stores=[];self.contexts=None;self.closed=False

    def snapshots(self,duration):
        store=SpillMap(self.folder/('snapshots_%s.sqlite'%duration),self.policy['resident_candidate_snapshots'])
        self.stores.append(store);return store

    def observation(self):
        stores=list(self.stores)
        if self.contexts is not None:stores.append(self.contexts.states)
        return dict(policy=self.policy,stores={store.path.name:dict(store.stats) for store in stores},
                    full_state_expiration=False,small_metadata_ledger_still_resident=True,
                    scratch_not_a_resumable_cache=True)

    def close(self):
        if self.closed:return
        failure=sys.exc_info()[1];errors=[]
        def attempt(action):
            try:action()
            except BaseException as exc:errors.append(exc)
        stores=list(self.stores)
        if self.contexts is not None:stores.append(self.contexts.states)
        for store in stores:attempt(store.close)
        # Delete only the explicitly created private SQLite files. No tree delete.
        for store in stores:
            if not store.path.is_relative_to(self.folder):
                errors.append(RuntimeError('WORKING_PATH_ESCAPE'));continue
            for suffix in ('','-journal','-wal','-shm'):
                file=Path(str(store.path)+suffix)
                def remove(file=file):
                    try:file.unlink()
                    except FileNotFoundError:pass
                attempt(remove)
        attempt(self.folder.rmdir);self.closed=True
        self.cleanup_errors=[repr(exc) for exc in errors]
        if errors and failure is None:raise errors[0]
        if errors and failure is not None:
            failure.engineering_cleanup_errors=getattr(failure,'engineering_cleanup_errors',[])+self.cleanup_errors

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
