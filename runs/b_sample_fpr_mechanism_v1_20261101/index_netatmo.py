"""Build stable chronological access for verified Netatmo raw bytes."""
import audit as a
import importlib.util
import numpy as np

receipt=a.read(a.HERE/'NETATMO_RAW_ACCEPTANCE.json')
assert receipt['status']=='STRUCTURAL_METADATA_PASS_REFERENCE_ADMISSION_PENDING'
src=a.pin(a.ROOT/'runs/targeted_normal_raw_qualification_v1_20261031/build_timeline_index.py')
ms=importlib.util.spec_from_file_location('stable_timeline_reuse',src)
module=importlib.util.module_from_spec(ms);ms.loader.exec_module(module);module.RUN=a.HERE
result=module.build(receipt['member'])
from hnr.history import role_binding
index=np.load(result['packet_index'],mmap_mode='r',allow_pickle=False)
order=np.load(result['chronological_order'],mmap_mode='r',allow_pickle=False)
roles=role_binding(index,order,{},frozen=False)
a.write('NETATMO_CHRONOLOGY_AND_ROLE_PROPOSAL.json',dict(status='CHRONOLOGY_VERIFIED_ROLE_SPLIT_PROPOSED',
    index_receipt=result,role_proposal=roles,rule='First floor(0.8 * observed UTC days) as historical reference, remaining observed days as historical development; same rule as C1.',
    no_feature_extraction=True,no_reference_admission=True,indexer_sha256=a.sha(src),script_sha256=a.sha(__file__)))
