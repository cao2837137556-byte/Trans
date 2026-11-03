"""Generated complete history→selection→snapshot→token→E3 adapter integration."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import torch

from hnr.common import TARGETS, VERSION, read, sha, write, write_rows
from hnr.history import create_census, walk_decoded
from hnr.selection import select_candidates
from hnr.encoding import encode_member
from continuous_input_engineering_v1 import Contexts
import legacy_reference_sample_prepare_v1 as prep
from test_history import packet, index_for, Progress


class SyntheticEncoder:
    """No learned parameters; independent token contract passed to frozen checks."""
    def __init__(self): self.calls=[]; self.core=self
    def e3_forward_batches(self, model, batches, device):
        batch=batches[0]
        self.calls.append(tuple(batch['input_ids'].shape))
        return np.tile(batch['input_ids'].sum(dim=1).numpy().astype(np.float32)[:,None],(1,768))


def tokenizer(batch):
    flow={k:v[0] for k,v in batch.items()};header=12 if flow['protocol']==6 else 6
    ids=[]
    for burst in flow['burst_tokens']:
        ids.append([65537]+[v+1 for i in range(0,len(burst),header+6) for v in burst[i:i+header]])
    return {k:[v] for k,v in dict(input_ids=ids,attention_mask=[[1]*len(x) for x in ids],
        dataset_burst_sizes=[len(x)-1 for x in ids],protocol=flow['protocol'],
        direction=flow['directions'],iats=flow['iats'],bytes=flow['bytes'],pkt_count=flow['counts']).items()}


def collator(examples):
    width=max(examples[0]['dataset_burst_sizes'])+1
    batch={k:[] for k in ('input_ids','attention_mask','direction','iats','bytes','pkt_count','protocol','dataset_burst_sizes')}
    for ex in examples:
        for k in ('input_ids','attention_mask'):
            batch[k].append([v for burst in ex[k] for v in burst+[0]*(width-len(burst))])
        for k in set(batch)-{'input_ids','attention_mask'}:batch[k].append(ex[k])
    return {k:torch.tensor(v) for k,v in batch.items()}


class Resource:
    def __init__(self): self.n=0
    def encoded(self,n): self.n+=n
    def guard(self): pass
    def update(self,*a,**k): pass


class PipelineTests(unittest.TestCase):
    def test_full_generated_prepare_replay_descriptors_tokens_and_shape_batches(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);target=TARGETS['TP_LINK'];spec=dict(target,capture_id='generated-history',
                raw=dict(sha256='b'*64),normality_evidence='generated')
            packets=[packet(1,0,port=1234),packet(2,1000000,port=2345),
                     packet(3,3000000,port=1234),packet(4,4000000,port=2345)]
            for p in packets:p['eth.src']=target['owner']
            idx=index_for([0,1000000,3000000,4000000]);order=np.arange(4,dtype=np.uint32)
            binding=dict(bank_end_frame=2,reference_end_us=1000000,packets=4)
            api=prep.old.legacy_runtime()[0]
            db=create_census(folder/'candidates.sqlite')
            ctx=Contexts(spec['capture_id'],{target['owner']},api,storage_path=folder/'c1.sqlite',resident_contexts=2)
            try:walk_decoded(packets,spec,binding,idx,order,'a'*64,ctx,Progress(),census=db)
            finally:ctx.close();db.close()
            selected=select_candidates(folder/'candidates.sqlite',[],folder/'selection',devices=[target['device']])
            from hnr.common import rows
            wanted={r['uid']:r for field in ('ref_rows','dev_rows') for r in rows(selected[field]['path'])}
            ctx=Contexts(spec['capture_id'],{target['owner']},api,storage_path=folder/'c2.sqlite',resident_contexts=2)
            snapshots=[]
            try:walk_decoded(packets,spec,binding,idx,order,'a'*64,ctx,Progress(),selected=wanted,snapshots=snapshots)
            finally:ctx.close()
            write_rows(folder/'selected_snapshots.jsonl.gz',sorted(snapshots,key=lambda e:e['uid']))
            write(folder/'LOGICAL_INPUT.json',dict(source_sha256='a'*64,source_kind='BYTE_PRESERVING_CHRONOLOGICAL_PCAPNG'))
            receipt=dict(version=VERSION,status='PREPARED',input_readout='RECENT_CURRENT_INCLUSIVE',
                source_sha256='a'*64,selection=selected,census_sha256=sha(folder/'candidates.sqlite'),
                logical_input_sha256=sha(folder/'LOGICAL_INPUT.json'),snapshots_sha256=sha(folder/'selected_snapshots.jsonl.gz'))
            write(folder/'PREPARE_RESULT.json',receipt)
            engine=SyntheticEncoder();resource=Resource()
            result=encode_member(folder,folder/'encoded',dict(old_rows=[]),resource,
                encoder=(engine,None,None,tokenizer,collator),encoder_identity=dict(synthetic=True),synthetic=True)
            self.assertEqual(resource.n,4)
            self.assertEqual(len(result['HIST_REF']['rows']),2)
            self.assertEqual(len(result['HIST_DEV']['rows']),2)
            self.assertTrue(all(r['use']=='QUERY' for r in result['HIST_DEV']['rows']))
            self.assertEqual(result['HIST_DEV']['e3'].shape,(2,768))
            self.assertEqual(read(folder/'encoded/ENCODE_RESULT.json')['status'],'SYNTHETIC_COMPLETE')
            self.assertEqual(sum(n for n,_ in engine.calls),4)
            self.assertEqual({r['uid'] for d in result.values() for r in d['rows']},set(wanted))

    def test_cli_config_allows_path_relocation_but_no_input_replacement(self):
        import run
        original=read(run.PACKAGE/'config/EXECUTION.json')
        moved=copy.deepcopy(original)
        moved['devices'][0]['raw']['path']='some/other/location.pcapng'
        moved['root']='/remote/project'
        run.validate_config_bindings(moved)
        moved['devices'][0]['raw']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'EXECUTION_SCIENTIFIC_BINDING_CHANGED'):
            run.validate_config_bindings(moved)

    def test_cli_no_execute_without_explicit_flag(self):
        import run
        with patch.object(run,'execute') as executor:
            with self.assertRaisesRegex(ValueError,'REAL_DATA_EXECUTION_FLAG_REQUIRED'):
                run.main(['execute','--output','unused'])
            executor.assert_not_called()


if __name__=='__main__':unittest.main()
