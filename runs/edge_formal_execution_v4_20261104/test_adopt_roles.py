"""Complete-role migration checks actual payloads and refuses partial sources."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import adopt_roles
from checkpoint import PackedRoleSpool, atomic_json, canonical, sha


class Guard:
    def __call__(self): pass
    def progress(self, *args, **kwargs): pass


class AdoptionTests(unittest.TestCase):
    def run_case(self, mode):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';output=root/'target';output.mkdir()
            model=root/'frozen.py';model.write_text('frozen numerical code')
            parent=dict(selection_seal_sha256='selection',runtime_identity={},C5_method_freeze_sha256='frozen',
                        artifact_pins={'frozen.py':sha(model)})
            card_path=root/'parent.json';atomic_json(card_path,parent);digest=sha(card_path)
            card=dict(parent,complete_role_adoption=dict(parent_card='parent.json',parent_sha256=digest,
                                                       output=str(source),roles=['NORMAL','HTTP']))
            old_binding,new_binding={'version':'old'},{'version':'new'}
            rows={role:dict(uid=role,frame=1,protocol=17) for role in ('NORMAL','HTTP')}
            raw={role:dict(records=1,sha256='raw-'+role) for role in rows}
            snapshots={}
            for role in rows:
                snapshot=dict(uid=role,row=rows[role],q14=[0.]*14,body=dict(flow=dict(protocol=17,counts=[1])))
                snapshots[role]=snapshot
                spool=PackedRoleSpool(source/'spools'/role,old_binding,role,[role]);spool.append(snapshot)
                if mode!='partial' or role!='HTTP':spool.complete(generator_exhausted=True,raw_final_identity_pass=True)
                atomic_json(spool.root/'REPLAY_COVERAGE.json',dict(last_frame=1,expected_records=1,
                    raw_sha256=raw[role]['sha256'],generator_exhausted=True,final_raw_identity_pass=True,replay_to_eof=True))
                if mode=='tamper' and role=='HTTP':
                    path=next(spool.root.glob('attempt-*/chunk-*/snapshots.bin'))
                    with path.open('ab') as stream:stream.write(b'tamper')
            with patch.multiple(adopt_roles,ROOT=root,PARENT_CARD='parent.json',PARENT_SHA=digest,SOURCE_OUTPUT=str(source)), \
                    patch.object(adopt_roles,'current_status',return_value={'status':'STOP'}), \
                    patch('worker.input_binding',return_value=old_binding):
                action=lambda:adopt_roles.adopt(card,output,{'raw_inputs':raw},{},[rows['NORMAL']],
                    {'NORMAL':[],'HTTP':[rows['HTTP']]},new_binding,Guard())
                if mode!='good':
                    with self.assertRaises(ValueError):action()
                else:
                    action()
                    for role in rows:
                        spool=PackedRoleSpool(output/'spools'/role,new_binding,role,[role])
                        self.assertTrue(spool.is_complete())
                        self.assertEqual(canonical(spool.load(role)),canonical(snapshots[role]))

    def test_complete_payloads_rebound_with_exact_values(self):self.run_case('good')
    def test_partial_role_blocks_adoption(self):self.run_case('partial')
    def test_corrupt_payload_blocks_adoption(self):self.run_case('tamper')
