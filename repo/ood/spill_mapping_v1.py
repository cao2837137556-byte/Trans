"""Single-owner mutable cache: spill complete values, never expire semantic state.

The database is created exclusively by this process and cannot be reopened.
Pickle is used only for our own in-process objects, never supplied input files.
Callers must finish mutating a returned value before another key can evict it.
Cache counts bound resident objects, not total process RSS or disk consumption.
"""
from collections import OrderedDict
from collections.abc import MutableMapping
from pathlib import Path
import pickle
import sqlite3
from scratch_registry_v1 import register_sqlite


class SpillMap(MutableMapping):
    def __init__(self, path, resident_limit, *, encode=None, decode=None):
        if type(resident_limit) is not int or resident_limit < 1:
            raise ValueError('POSITIVE_RESIDENT_LIMIT_REQUIRED')
        self.path=Path(path).resolve()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open('xb'): pass
        self.db=None
        try:
            register_sqlite(self.path)
            self.db=sqlite3.connect(str(self.path))
            self.db.execute('PRAGMA cache_size=-2048')
            self.db.execute('PRAGMA mmap_size=0')
            self.db.execute('CREATE TABLE objects (position INTEGER PRIMARY KEY, key BLOB UNIQUE NOT NULL, value BLOB)')
        except BaseException:
            # Exclusivity above established ownership before cleanup becomes
            # possible. A failed xb never opens or removes a prior database.
            if self.db is not None:self.db.close()
            for suffix in ('','-journal','-wal','-shm'):
                try:Path(str(self.path)+suffix).unlink()
                except FileNotFoundError:pass
            raise
        self.cache=OrderedDict();self.limit=resident_limit;self.count=0;self.closed=False
        self.encode=encode or (lambda value:pickle.dumps(value,protocol=5))
        self.decode=decode or pickle.loads
        self.stats=dict(hits=0,loads=0,spills=0,serialized_bytes=0,peak_resident=0,peak_entries=0)

    def _check(self):
        if self.closed:raise RuntimeError('SPILL_MAP_CLOSED')

    @staticmethod
    def _key(key):return pickle.dumps(key,protocol=5)

    def __contains__(self,key):
        self._check()
        return key in self.cache or self.db.execute('SELECT 1 FROM objects WHERE key=?',(self._key(key),)).fetchone() is not None

    def _admit(self,key,value):
        if len(self.cache)>=self.limit:
            old,body=next(iter(self.cache.items()))
            encoded=self.encode(body)
            self.db.execute('UPDATE objects SET value=? WHERE key=?',(encoded,self._key(old)))
            del self.cache[old]
            self.stats['spills']+=1;self.stats['serialized_bytes']+=len(encoded)
            # Batched transactions avoid fsync per packet while bounding the journal.
            if self.stats['spills']%1024==0:self.db.commit()
        self.cache[key]=value
        self.stats['peak_resident']=max(self.stats['peak_resident'],len(self.cache))

    def __getitem__(self,key):
        self._check()
        if key in self.cache:
            self.stats['hits']+=1;self.cache.move_to_end(key);return self.cache[key]
        found=self.db.execute('SELECT value FROM objects WHERE key=?',(self._key(key),)).fetchone()
        if found is None:raise KeyError(key)
        if found[0] is None:raise RuntimeError('MISSING_SPILLED_VALUE')
        value=self.decode(found[0]);self.stats['loads']+=1
        self._admit(key,value);return value

    def __setitem__(self,key,value):
        self._check()
        if key in self.cache:
            self.cache[key]=value;self.cache.move_to_end(key);return
        cursor=self.db.execute('INSERT OR IGNORE INTO objects(key,value) VALUES(?,NULL)',(self._key(key),))
        if cursor.rowcount:
            self.count+=1;self.stats['peak_entries']=max(self.stats['peak_entries'],self.count)
        self._admit(key,value)

    def __delitem__(self,key):
        self._check()
        cursor=self.db.execute('DELETE FROM objects WHERE key=?',(self._key(key),))
        if not cursor.rowcount:raise KeyError(key)
        self.cache.pop(key,None);self.count-=1

    def __len__(self):self._check();return self.count

    def __iter__(self):
        self._check()
        # Same insertion ordering as dict; callers must not change size mid-scan.
        cursor=self.db.execute('SELECT key FROM objects ORDER BY position')
        try:
            for (key,) in cursor:yield pickle.loads(key)
        finally:cursor.close()

    def close(self):
        if not self.closed:
            # Ephemeral working state is deliberately not a resumable artifact.
            self.cache.clear();self.db.close();self.closed=True


def object_codec(factory):
    """Store only object attributes; dynamic legacy module names need not pickle."""
    def encode(value):
        attrs=dict(getattr(value,'__dict__',{}))
        for cls in type(value).__mro__:
            slots=getattr(cls,'__slots__',())
            if isinstance(slots,str):slots=(slots,)
            for name in slots:
                if name not in ('__dict__','__weakref__') and hasattr(value,name):attrs[name]=getattr(value,name)
        return pickle.dumps(attrs,protocol=5)
    def decode(blob):
        value=factory()
        for name,body in pickle.loads(blob).items():setattr(value,name,body)
        return value
    return encode,decode


def validate_policy(policy):
    required={'resident_contexts','resident_legacy_prefixes','resident_candidate_snapshots'}
    if not isinstance(policy,dict) or set(policy)!=required:
        raise ValueError('STATE_STORAGE_POLICY_REQUIRED')
    if any(type(value) is not int or value<1 for value in policy.values()):
        raise ValueError('POSITIVE_RESIDENT_LIMIT_REQUIRED')
    return policy
