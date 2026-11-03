"""Normalize reporting-only metadata and verify immutable population masks."""
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import edge_adapter as edge


def seal(population_directory, output):
    source=Path(population_directory);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    original=edge.read(source/'POPULATION.json');value=edge.card();start=time.monotonic()
    selected=edge.read(source/'DENSE_REFERENCE_PLAN.json');anchors=edge.read(source/'SPARSE_B2_ANCHOR_PLAN.json')
    protocols={};reference_counts=Counter();reference_uid=set()
    with gzip.open(source/'REFERENCE_ROWS.jsonl.gz','rt',encoding='utf-8') as inp, gzip.open(output/'REFERENCE_ROWS.jsonl.gz','wt',encoding='utf-8',newline='\n') as out:
        for line in inp:
            row=json.loads(line);row['scenario']='NORMAL'
            edge.frozen.require(row['uid']==edge.frozen.digest([row['source_sha256'],row['frame'],row['owner']]),'REFERENCE_PHYSICAL_UID')
            reference_uid.add(row['uid']);reference_counts[str(row['protocol'])]+=1
            out.write(json.dumps(row,separators=(',',':'),ensure_ascii=True)+'\n')
    edge.frozen.require(reference_uid==set(selected['selected_uids']),'REFERENCE_SELECTED_UID_JOIN')
    for role in ('NORMAL','HTTP','UDP'):
        item=original['roles'][role];mask_path=source/item['mask_file']
        edge.frozen.require(edge.sha(mask_path)==item['mask_sha256'],'POPULATION_MASK_SHA')
        mask=mask_path.read_bytes();counts=Counter();frame=0
        fields=['frame.number','ip.proto','tcp.flags','tcp.len']
        command=[str(edge.TSHARK),'-n','-r',value['raw_inputs'][role]['path'],'-T','fields','-E','header=y','-E','separator=/t','-E','quote=d','-E','occurrence=f']
        for name in fields:command+=['-e',name]
        with (output/(role+'_metadata_decoder.stderr.log')).open('x',encoding='utf-8') as err:
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=err,text=True,encoding='utf-8')
            try:
                reader=csv.DictReader(process.stdout,delimiter='\t',quotechar='"')
                edge.frozen.require(reader.fieldnames==fields,'METADATA_DECODER_FIELDS')
                for row in reader:
                    frame+=1;edge.frozen.require(int(row['frame.number'])==frame,'METADATA_FRAME_CONTINUITY')
                    truth,reason=mask[2*(frame-1):2*frame]
                    if not truth:continue
                    proto=int(row['ip.proto'])
                    counts['candidate|truth%d|proto%d'%(truth,proto)]+=1
                    counts[('eligible' if reason==1 else 'unscored')+'|truth%d|proto%d'%(truth,proto)]+=1
                    if reason==1 and role=='HTTP':
                        flags=edge.frozen.integer(row['tcp.flags']);counts['HTTP_flags|'+str(flags)]+=1
                        if flags&16 and not flags&2:counts['HTTP_ACK_no_SYN']+=1
                        if flags&2 and not flags&16:counts['HTTP_SYN_guarded']+=1
                        if int(row['tcp.len'])>0:counts['HTTP_payload_containing']+=1
                    if time.monotonic()-start>300:raise TimeoutError('SEAL_METADATA_AUDIT_300S')
                edge.frozen.require(process.wait(timeout=30)==0,'METADATA_DECODER_EXIT')
            finally:
                if process.poll() is None:process.kill()
                process.wait(timeout=30);process.stdout.close()
        edge.frozen.require(frame==value['raw_inputs'][role]['records'] and len(mask)==frame*2,'MASK_RAW_FRAME_COVERAGE')
        edge.frozen.require(sum(v for k,v in counts.items() if k.startswith('eligible|'))==item['counts']['eligible'],'ELIGIBILITY_COUNT_RECONCILIATION')
        protocols[role]=dict(counts)
    result=dict(status='SEALED_NO_EXTERNAL_MODEL_EVALUATION',population_manifest_sha256=edge.sha(source/'POPULATION.json'),
        reporting_metadata_added=['scenario=NORMAL/HTTP/UDP'],reporting_metadata_does_not_change=['UID','eligibility','reference selection','scores'],
        population=original,protocol_and_stratum_counts=protocols,
        references=dict(rows=sum(reference_counts.values()),by_protocol=dict(reference_counts),
            reference_rows_sha256=edge.sha(output/'REFERENCE_ROWS.jsonl.gz'),selected_uid_sha256=selected['selected_uid_sha256'],
            original_dense_plan_sha256=edge.sha(source/'DENSE_REFERENCE_PLAN.json'),sparse_b2_anchor_rows=len(anchors['rows']),
            scheduled_anchor_priority=[r['uid'] for r in anchors['rows']],actual_encoded_available=0,
            actual_total_encoding_required=len(reference_uid),selection_internal_encoded_parameter='SCHEDULING_PRIORITY_ONLY_NOT_CACHE_AVAILABILITY',
            bank_activation='Encode all anchors then other selected rows; activate only complete selected identity-joined bank'),
        full_view_overlap=dict(reference_uids_are_full_view_queries=True,selected_references=len(reference_uid),
            no_duplicate_logical_encoding=True,adapter='prebank_query_for_reference',
            behavior='Query and reference retain exact physical UID; QUERY before cutoff is forced exact RAW, no reference distance.'),
        adapter_sha256=edge.sha(Path(edge.__file__)),mask_files={role:dict(path=str(source/item['mask_file']),sha256=item['mask_sha256'],bytes=item['mask_bytes']) for role,item in original['roles'].items()},
        elapsed_seconds=time.monotonic()-start,model_rows=0,distance_pairs=0)
    edge.write(output/'POPULATION_SEAL.json',result)
    print(json.dumps(dict(status=result['status'],protocols=protocols,elapsed_seconds=result['elapsed_seconds'])))


if __name__=='__main__':seal(sys.argv[1],sys.argv[2])
