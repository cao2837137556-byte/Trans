"""Actual unfiltered raw-prefix eligibility parity, without model inference."""
from pathlib import Path
import sys
import time

import edge_adapter as edge


def run(output, count=4096):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    value=edge.card();api=edge.prep.old.legacy_runtime()[0];result={};started=time.monotonic()
    for role in ('NORMAL','HTTP','UDP'):
        capture=edge.segments(role,value)[0]['capture_id']
        numerical=edge.numerical_context(capture,api,output/(role+'.sqlite'))
        census=edge.eligibility_context(capture,api)
        try:
            seen=0
            for packet in edge.decode_rows(value['raw_inputs'][role]['path'],output/(role+'_decoder.stderr.log'),stop_after=count,deadline=started+300):
                a=numerical.append(packet);b=census.append(packet)
                edge.frozen.require(a[:2]==b[:2] and numerical.query_allowed==census.query_allowed and
                    numerical.query_reason==census.query_reason and numerical.events==census.events,
                    'REAL_ELIGIBILITY_PER_PACKET_PARITY')
                # Namespace/poison/taint histories must also remain equal.
                if int(packet['frame.number'])%256==0:
                    edge.frozen.require(numerical.last_seen==census.last_seen and
                        numerical.poisoned==census.poisoned and numerical.tainted==census.tainted and
                        numerical.reasons==census.reasons,'REAL_ELIGIBILITY_LEDGER_PARITY')
                seen+=1
            edge.frozen.require(seen==count,'REAL_PREFIX_COVERAGE')
            result[role]=dict(original_unfiltered_prefix_frames=count,
                numerical_vs_eligibility_per_packet_exact=True,events=dict(census.reasons),
                namespaces=len(census.last_seen),poisoned=len(census.poisoned))
        finally:numerical.close()
    receipt=dict(status='PASS_REAL_RAW_PREFIX_ELIGIBILITY_PARITY',roles=result,
        adapter_sha256=edge.sha(Path(edge.__file__)),frozen_append_file_sha256=edge.sha(edge.ROOT/'repo/ood/continuous_input_v3.py'),
        model_evaluations=0,features_generated=0,distance_pairs=0,elapsed_seconds=time.monotonic()-started)
    edge.write(output/'PARITY.json',receipt)
    print(receipt['status'])


if __name__=='__main__':run(sys.argv[1])
