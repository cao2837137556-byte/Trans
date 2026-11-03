"""Bind sealed query identities to the engineering card without changing C5."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024**2),b''):h.update(chunk)
    return h.hexdigest()


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    Path(str(path)+'.sha256').write_text(sha(path)+'  '+Path(path).name+'\n',encoding='utf-8')


def main():
    folder=HERE/'seal20k'
    seal=read(folder/'QUERY_SELECTION_SEAL.json')
    verified=read(folder/'VERIFICATION.json')
    if verified['status']!='PASS_REAL_METADATA_SELECTION_AUDIT':raise RuntimeError('SELECTION_NOT_VERIFIED')
    oldseal=read(ROOT/'runs/edge_external_test1_engineering_v1_20261103/adapter/population_sealed_v1/POPULATION_SEAL.json')
    refs={int(k):v for k,v in oldseal['references']['by_protocol'].items()}
    byprotocol={p:sum(int(item['protocols'].get(str(p),0)) for item in seal['roles'].values()) for p in (6,17)}
    pairs=sum(byprotocol[p]*refs[p] for p in (6,17))
    freeze_path=ROOT/'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json'
    freeze=read(freeze_path)
    unchanged=[]
    for name,binding in freeze['immutable_asset_pins'].items():
        if sha(ROOT/name)!=binding['sha256']:raise RuntimeError('FROZEN_ASSET_CHANGED:'+name)
        unchanged.append(name)
    overlay=dict(schema='EDGE_SELECTION_EXECUTION_OVERLAY_V1',
        status='BASE_SELECTION_SEALED_LINUX_PREFLIGHT_AND_FINAL_BUDGET_PENDING',
        created_utc=datetime.now(timezone.utc).isoformat(),
        original_engineering_card=dict(path='runs/edge_external_test1_engineering_v1_20261103/ENGINEERING_CARD_R2.json',
            sha256=sha(ROOT/'runs/edge_external_test1_engineering_v1_20261103/ENGINEERING_CARD_R2.json')),
        C5_freeze_sha256=sha(freeze_path),immutable_frozen_assets_verified=len(unchanged),
        selection_seal=dict(path='runs/edge_query_selection_v1_20261103/seal20k/QUERY_SELECTION_SEAL.json',
            sha256=sha(folder/'QUERY_SELECTION_SEAL.json')),
        verification_sha256=sha(folder/'VERIFICATION.json'),
        normal=dict(population_count=1220126,component_count=17025,selected=20000,
            branch='B_RESIDUAL_CAPACITY',all_components_represented=True,
            sampling='Original B exact integer quotas; fixed new domain salt',
            fallback_registered_for_future_K_below_C='Hash sample K components, one UID each; expansion C*N_g/K'),
        attack=dict(HTTP=seal['roles']['HTTP']['strata'],UDP=seal['roles']['UDP']['strata'],
            quota_donor='Largest current quota above floor; fixed stratum-order ties',
            source_scope='Pinned scenario/direction establishes eligible population; within-population ranking uses only header strata and physical UID'),
        base_query_rows=60000,reference_rows=4124,base_encoding_rows=64124,
        selected_query_rows_by_protocol=byprotocol,
        reference_rows_by_protocol=refs,
        distance_upper=dict(one_same_protocol_pass=pairs,C5_and_knn5_two_passes=2*pairs,
            geometry_or_heads_changed=False,p1_p3_share_support=True,
            guard_or_fallback_savings_not_claimed=True),
        storage_lower_bound=dict(E3_float32_bytes=64124*768*4,
            q14_float32_bytes=64124*14*4,
            caution='Not a full disk budget; add original context state, metadata, checkpoint, decode and temporary files'),
        resizing=dict(status='NOT_PERFORMED_PENDING_LINUX_MEASUREMENTS',common_integer_K_range=[10000,20000],
            f='K/20000 applied identically to all three role quotas; references remain4124',
            criterion='Select largest K whose conservative measured complete pipeline estimate fits24h; include decode/context/shape batches/references/distances/I/O/resume',
            if_K10000_still_exceeds_budget='STOP_BLOCKED_NO_AUTOMATIC_EXTENSION_OR_RESUBMISSION',
            preserve_base_seal=True,new_final_derived_seal_required=True,
            same_salts_and_rules=True,recompute_inclusion_weights=True,quality_results_must_not_influence=True),
        reporting=dict(sample_rate='Exact errors/selected rows, explicitly sample ratio',
            population_estimate='Inverse inclusion weights divided by known full N; do not renormalize or clamp HT point estimate',
            normal_component_metric='All components equal within B branch; sampled-component estimate in fallback',
            normal_FULL='NOT_EVALUABLE_FROM_POSTWINDOW_ONLY_SELECTION',
            reference_rows_in_postwindow_query_denominator=0,unselected_rows='NOT_SAMPLED',
            methods_share_same_ordered_query_UIDs=True,
            independent_attack_event_recall='NOT_EVALUABLE_WITHOUT_EVENT_LEDGER'),
        temporal_sensitivity=dict(block_seconds=60,anchor='Original captured minimum timestamp within each pinned capture/scenario',
            blocks='Enumerate entire eligible population blocks, including zero-selected blocks; never mix capture/scenario boundaries',
            repetitions=2000,seed=20261103,interval='2.5th/97.5th percentiles of within-capture block resampling',
            label='Conditional temporal sensitivity interval, not proof of full sampling-design95% coverage',
            at_least_HTTP_blocks=5,at_least_UDP_blocks=7,
            precision_halfwidth_0_3pp_guaranteed=False,
            attack_packets_not_independent_events=True,
            inference_implementation='PENDING_FULL_WORKER_ENGINEERING_AND_SYNTHETIC_VALIDATION_BEFORE_FORMAL_EVALUATION'),
        full_streaming_resume_worker_ready=False,formal_external_evaluation_authorized=False,
        execution_card_frozen=False,execution_ready=False,training=False,
        model_forwards_this_task=0,cloud_jobs_submitted_this_task=0,
        no_input_tensor_dedup=True,no_sampling_context_deletion=True)
    write(HERE/'EXECUTION_OVERLAY.json',overlay)
    print(json.dumps(dict(status=overlay['status'],distance_upper=overlay['distance_upper'],
        unchanged_frozen_assets=len(unchanged))))


if __name__=='__main__':main()
