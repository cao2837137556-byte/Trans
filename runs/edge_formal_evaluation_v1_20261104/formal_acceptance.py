"""Structural acceptance independent of observed model quality."""
from pathlib import Path
import hashlib
from checkpoint import require,sha,canonical
from worker import read

METHODS={'RAW','C5_P3','C5_P1','STANDARD_KNN5'}
def validate_outputs(output,card_sha):
    output=Path(output);enc=read(output/'encoded/COMPLETE.json')
    binding=read(output/'encoded/BINDING.json')
    require(binding.get('execution_card_sha256')==card_sha and enc['binding_sha256']==hashlib.sha256(canonical(binding)).hexdigest(),'ENCODE_CARD_BINDING')
    require(enc['rows']==64124 and len(enc['batches'])==4046,'ENCODE_FULL_COVERAGE')
    uids=[u for b in enc['batches'] for u in b['uids']]
    require(len(uids)==len(set(uids))==64124 and enc['ordered_uids_sha256']==hashlib.sha256(canonical(uids)).hexdigest(),'ENCODE_UID_COVERAGE')
    complete=read(output/'evaluation/COMPLETE.json');report=read(output/'evaluation/METRICS.json')
    require(complete['metrics_sha256']==sha(output/'evaluation/METRICS.json') and
        complete['query_rows']==report['query_rows']==60000 and complete['reference_rows']==4124 and
        set(complete['methods'])==set(report['methods'])==METHODS and complete['training'] is False,'EVAL_COMPLETE')
    require(complete['pairs_full_upper']==324756408,'DISTANCE_PAIR_COVERAGE')
    require(set(report['ordered_query_uids'])<=set(uids),'QUERY_SUBSET_ENCODING')
    require(len(report['ordered_query_uids'])==len(set(report['ordered_query_uids']))==60000 and
        hashlib.sha256(canonical(report['ordered_query_uids'])).hexdigest()==complete['ordered_query_uids_sha256'],'REPORT_UIDS')
    require(report['external_quality_used_for_selection'] is False and report['ht_renormalized'] is False and
        report['ht_clamped'] is False and report['references_in_query_denominator']==0,'FROZEN_REPORT_POLICY')
    from reporting import HEADS
    for method,value in report['methods'].items():
        require(set(value['heads'])==set(HEADS),'FOUR_FROZEN_HEADS')
        for head in value['heads'].values():
            require(set(head['roles'])=={'NORMAL','HTTP','UDP'},'ALL_ROLES_REPORT')
            for role,metric in head['roles'].items():
                require(metric['selected_rows']==20000 and metric['metric']==('FPR' if role=='NORMAL' else 'ATTACK_ASSOCIATED_RECALL'),'METRIC_ROLE_DENOMINATOR')
    return dict(status='PASS_STRUCTURAL_VALIDATION',encoding_rows=64124,query_rows=60000,reference_rows=4124,
        metrics_sha256=complete['metrics_sha256'],evaluation_complete_sha256=sha(output/'evaluation/COMPLETE.json'),
        encoded_complete_sha256=sha(output/'encoded/COMPLETE.json'),quality_threshold_used=False)
