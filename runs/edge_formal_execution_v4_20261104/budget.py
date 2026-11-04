"""Auditable shape/physical-row budget scenarios; no encoder or quality inputs."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def pin(path):
    path = Path(path)
    return dict(path=str(path.relative_to(ROOT)).replace('\\','/'), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def physical_rows(count, batch_size=16):
    if type(count) is not int or count < 0 or batch_size != 16:
        raise ValueError('FROZEN_BATCH16_NONNEGATIVE_COUNT')
    return count + (15 if count % batch_size == 1 else 0)


def shape_tuple(key):
    value = tuple(map(int, key.split(','))) if isinstance(key, str) else tuple(key)
    if len(value) != 3 or value[0] not in (6,17) or min(value[1:]) <= 0:
        raise ValueError('SHAPE_SCHEMA')
    return value


def measured_rates(batches):
    rates = defaultdict(list)
    for batch in batches:
        rows = batch['physical_rows']
        logical = batch['logical_rows']
        if rows != (16 if logical == 1 else logical) or not 1 <= logical <= 16:
            raise ValueError('PHYSICAL_BATCH_CONTRACT')
        rates[shape_tuple(batch['shape'])].append(batch['seconds']/rows)
    return {shape:max(values) for shape,values in rates.items()}


def estimate_rate(shape, rates):
    """Return an explicit engineering scenario, never a proven runtime bound.

    Exact shape uses slowest measured physical-row throughput. An unmeasured
    shape uses the slowest point on the closest componentwise-dominating
    frontier. Shapes without a measured dominator use token-area scaling and
    are explicitly tagged as extrapolation requiring engineering validation.
    """
    shape = shape_tuple(shape)
    if shape in rates:
        return rates[shape], 'EXACT_SHAPE_PHYSICAL_ROW_RATE', [shape]
    candidates = [s for s in rates if s[0] == shape[0] and s[1] >= shape[1] and s[2] >= shape[2]]
    if candidates:
        frontier = [s for s in candidates if not any(t != s and t[1] <= s[1] and t[2] <= s[2]
                                                    for t in candidates)]
        return max(rates[s] for s in frontier), 'UNMEASURED_DOMINATING_SHAPE_SCENARIO', frontier
    same = [s for s in rates if s[0] == shape[0]]
    if not same:
        raise ValueError('NO_PROTOCOL_MEASUREMENT')
    rate = max(rates[s] * max(1., shape[1]*shape[2]/(s[1]*s[2])) for s in same)
    return rate, 'UNMEASURED_TOKEN_AREA_EXTRAPOLATION', same


def encoding_scenario(counts, rates):
    result=[]
    for key, count in sorted(counts.items(), key=lambda x: shape_tuple(x[0])):
        if type(count) is not int or count < 1:
            raise ValueError('POSITIVE_SHAPE_COUNT')
        shape=shape_tuple(key)
        seconds_per_physical, kind, proxies = estimate_rate(shape, rates)
        physical=physical_rows(count)
        result.append(dict(shape=list(shape), logical_rows=count, physical_rows=physical,
            batches=math.ceil(count/16), measurement_kind=kind,
            proxy_shapes=[list(s) for s in proxies],
            seconds_per_physical_row=seconds_per_physical,
            estimated_seconds=physical*seconds_per_physical))
    return dict(logical_rows=sum(row['logical_rows'] for row in result),
        physical_rows=sum(row['physical_rows'] for row in result),
        batches=sum(row['batches'] for row in result),
        exact_shape_rows=sum(row['logical_rows'] for row in result
                             if row['measurement_kind']=='EXACT_SHAPE_PHYSICAL_ROW_RATE'),
        unmeasured_shape_rows=sum(row['logical_rows'] for row in result
                                  if row['measurement_kind']!='EXACT_SHAPE_PHYSICAL_ROW_RATE'),
        estimated_seconds=sum(row['estimated_seconds'] for row in result), shapes=result)


def build():
    source = ROOT/'runs/edge_preflight_io_repair_v1_20261103/LINUX_PREFLIGHT_RESULT_181418.json'
    census_path=ROOT/'runs/edge_query_selection_v1_20261103/shapes_v2/SHAPE_CENSUS.json'
    seal_path=ROOT/'runs/edge_query_selection_v1_20261103/seal20k/QUERY_SELECTION_SEAL.json'
    overlay_path=ROOT/'runs/edge_query_selection_v1_20261103/EXECUTION_OVERLAY.json'
    probe_path=HERE/'UDP_PROBE_RESULT.json'
    actual,census,seal,overlay,probe=map(read,(source,census_path,seal_path,overlay_path,probe_path))
    if actual['status']!='SAME_RUNTIME_REAL_SLICE_E2E_PASS':
        raise ValueError('LINUX_PREFLIGHT_REQUIRED')
    if census['selection_seal_sha256'] != pin(seal_path)['sha256']:
        raise ValueError('CENSUS_SELECTION_BINDING')
    counts = Counter()
    full_shapes = set()
    roles={}
    for role,value in census['roles'].items():
        counts.update(value['target_shape_counts'])
        full_shapes.update(shape_tuple(key) for key in value['full_shape_counts'])
        roles[role]=dict(raw_records=value['counts']['raw_records'],
                        target_rows=value['counts']['selected_targets'])
    if sum(counts.values())!=seal['total_logical_encoding_rows'] or sum(counts.values())!=64124:
        raise ValueError('EXACT_BASE20K_TARGET_COUNTS')
    rates=measured_rates(actual['encoding']['batches'])
    enc=encoding_scenario(counts,rates)
    # A planning margin is recorded as an assumption, not a new measurement.
    enc_margin=2.5
    observed_stage={x['name']:x['seconds'] for x in actual['stages']}
    local_prior_path=ROOT/'runs/edge_preflight_io_repair_v1_20261103/REAL_REPLAY_VALIDATION.json'
    local_prior=read(local_prior_path)
    local_prefix=sum(local_prior['prefix_runs'][r]['seconds'] for r in ('NORMAL','HTTP','UDP'))
    prefix_factor=observed_stage['REAL_UNFILTERED_DECODE_CONTEXT_DESCRIPTOR']/local_prefix
    windows_udp_linear=probe['seconds']*roles['UDP']['raw_records']/probe['rows_completed']
    windows_normal_linear=local_prior['prefix_runs']['NORMAL']['seconds']*roles['NORMAL']['raw_records']/255220
    windows_http_linear=local_prior['prefix_runs']['HTTP']['seconds']*roles['HTTP']['raw_records']/228978
    local_full_linear=windows_udp_linear+windows_normal_linear+windows_http_linear
    replay_margin=3.
    replay_seconds=local_full_linear*max(1.,prefix_factor)*replay_margin
    # Distance fixture timings include setup/heads and are not an isolated
    # large-bank kernel benchmark. Expose, but do not certify this projection.
    fixture=actual['fixture']
    fixture_pairs=fixture['distance_pairs_reserved']+fixture['knn5_distance_pairs']
    pairs=overlay['distance_upper']['C5_and_knn5_two_passes']
    distance_linear=observed_stage['REAL_DISTANCE_FOUR_HEAD_EVALUATE_RECEIPT']*pairs/fixture_pairs
    overhead=1800.
    planning_total=enc['estimated_seconds']*enc_margin+replay_seconds+distance_linear*2+overhead
    unmultiplied_total=enc['estimated_seconds']+replay_seconds/replay_margin+distance_linear+overhead
    samples=probe['samples']
    peak_temp=max(x['temporary_bytes'] for x in samples)
    udp_temp_linear=peak_temp*roles['UDP']['raw_records']/probe['rows_completed']
    return dict(schema='EDGE_LINUX_MEASURED_BUDGET_SCENARIOS_V1',
        status='PLANNING_SCENARIOS_NOT_A_CERTIFIED_FULL_PIPELINE_BOUND',
        input_pins=[pin(p) for p in (source,census_path,seal_path,overlay_path,probe_path,local_prior_path)],
        exact_target_roles=roles, query_rows=60000, reference_rows=4124,
        exact_target_shapes=len(counts), raw_prefix_measured=dict(NORMAL=255220,HTTP=228978,UDP=16),
        shape_coverage=dict(full_population_shapes=len(full_shapes),
            selected_target_shapes=len(counts), measured_shapes=len(rates),
            unmeasured_full_shapes=len(full_shapes-set(rates)),
            unmeasured_target_shapes=len(set(map(shape_tuple,counts))-set(rates)),
            interpretation='Only selected endpoint shapes require formal encoder forwards; all original packets still enter causal context.'),
        full_raw_records=sum(v['raw_records'] for v in roles.values()),
        frozen_batch_size=16, input_dedup=False,
        encoding=dict(enc, safety_multiplier=enc_margin,
            planning_seconds=enc['estimated_seconds']*enc_margin,
            multiplier_is_assumption=True, strict_probe_seconds_not_added_per_batch=True,
            limitation='Target shape census exact; unmeasured shape dominance/throughput and large-batch scaling are engineering assumptions, not wall-time bounds.'),
        decode=dict(local_udp_probe_rows=probe['rows_completed'],
            local_udp_probe_seconds=probe['seconds'], local_udp_full_linear_seconds=windows_udp_linear,
            observed_linux_prefix_vs_windows_factor=prefix_factor,
            planning_slowdown_multiplier=replay_margin,
            planning_seconds=replay_seconds, linux_full_prefix_measured=False,
            limitations=['UDP 32k Windows probe is not Linux throughput.',
                         'Full TShark conversation/state-table growth and later-prefix I/O remain unmeasured.',
                         'All original physical packets remain in causal state; sampling changes encoding endpoints only.']),
        distances=dict(two_pass_upper_pairs=pairs, fixture_pairs=fixture_pairs,
            fixture_seconds=observed_stage['REAL_DISTANCE_FOUR_HEAD_EVALUATE_RECEIPT'],
            linear_fixture_projection_seconds=distance_linear,
            planning_seconds=distance_linear*2,
            isolated_full_bank_kernel_measurement=False,
            limitation='Tiny fixture includes heads/setup; linear scaling is a deliberately padded scenario, not an empirical full-bank upper bound.'),
        planning_total_seconds=planning_total, planning_total_hours=planning_total/3600,
        conditional_scenario_without_additional_multipliers=dict(
            encoding_seconds=enc['estimated_seconds'], replay_seconds=replay_seconds/replay_margin,
            distance_seconds=distance_linear, fixed_seconds=overhead,
            total_seconds=unmultiplied_total, total_hours=unmultiplied_total/3600,
            fits_24h=unmultiplied_total<=86400,
            interpretation='Conditional projection only. Uses tiny variable-size encoder batches, proxy shapes, Windows/Linux prefix scaling and tiny-fixture distance scaling. Not a measured formal runtime or permission to run.'),
        fixed_overhead_allowance_seconds=overhead,
        quota_decision=dict(certified_largest_K=None,
            requested_base_K=20000, pre_registered_K_range=[10000,20000],
            scenario_fits_24h=planning_total<=86400,
            reason='No complete Linux streaming/late-prefix/recovery measurement. Do not seal a lower K by proportional shape scaling: references stay fixed and re-selection changes shape mix.',
            quality_scores_used=False, new_derived_seal_required_if_resized=True),
        resources=dict(proposed_cpu_threads=1, proposed_rss_bytes=8*1024**3,
            proposed_scratch_bytes=32*1024**3, proposed_durable_output_bytes=16*1024**3,
            proposed_wall_seconds=86400,
            measured_linux_preflight_peak_tree_rss_bytes=actual['peak_tree_rss_bytes'],
            udp_local_peak_tree_rss_bytes=max(s['tree_rss_bytes'] for s in samples),
            udp_full_db_linear_projection_bytes=math.ceil(udp_temp_linear),
            udp_db_2x_planning_bytes=math.ceil(udp_temp_linear*2),
            E3_bytes=64124*768*4, q14_bytes=64124*14*4,
            complete_snapshot_bytes_unknown=True,
            durable_includes_models_raw_arrays_checkpoints=True,
            local_retrieval='SMALL_RECEIPTS_AND_SUMMARIES_ONLY_REMOTE_ARRAYS_REMAIN_REMOTE',
            hard_resource_guards_required=True,
            limitation='Resource proposal with headroom, not a measured guarantee. Snapshot spooling, full decoder RSS and numerical-state late growth must be checked.'),
        blockers_before_claiming_formal_ready=[
            'Final streaming worker snapshot/checkpoint storage bound and killed-worker byte-exact recovery gate.',
            'Full or defensibly bounded Linux late-prefix decode/resource measurement, especially UDP.',
            'Representative large-bank distance throughput measurement or explicitly approved conservative hard-stop budget.',
            'Final complete execution card and independent review; explicit formal-run user authorization.'],
        proposed_bounded_linux_engineering_validation=dict(
            submitted=False, requires_separate_resource_authorization=True,
            cpu_threads=1, requested_rss_bytes=8*1024**3,
            requested_scratch_bytes=32*1024**3,
            hard_wall_seconds=7200, hard_temporary_bytes=24*1024**3,
            local_retrieval='RECEIPTS_ONLY', quality_outputs='DISCARD_NO_QUALITY_REPORT',
            steps=[
                'Use the actual formal worker and pinned contracts; deliberately kill after an atomic shard, resume, and compare uninterrupted vs resumed arrays byte for byte on a fixed small real slice.',
                'Causally replay the raw UDP stream from frame 1 through EOF with numerical spill state, preserving all original packets. Emit periodic live TShark+worker RSS and disk/rate samples, including the final 10 percent; no model/quality outputs for the scan.',
                'In the same causal replay mechanism, collect only predetermined real representatives needed for missing selected target shapes. Benchmark exact-shape batch16 with deterministic engineering clones if fewer than16 real endpoints exist. Hard overall deadline applies; incomplete coverage remains BLOCKED.',
                'Benchmark the actual distance kernels at 4124 reference rows on fixed synthetic embeddings/descriptors, bounded to query blocks no larger than4096; retain timings/checksums only, not external predictions.',
                'Recompute the base20k scenario from observed batch16 throughput, complete UDP replay and full-bank kernel timing. Retain K20k unless a separately sealed metadata-only resize is required and authorized.'
            ],
            success_requires=[
                'Killed-worker resume equality and input seal/hash equality.',
                'UDP EOF reached with live late-prefix resource samples inside hard guards.',
                'Sufficient true target-shape batch16 timing coverage or an explicit conservative remaining uncertainty; no claim that unmeasured shapes passed.',
                'Full-bank kernel timing, durable/scratch accounting and a reviewed total budget before formal evaluation.'
            ],
            on_cap='Preserve validated atomic shards and failure/resource receipts, stop without automatic resubmission; no scientific metrics are accepted.'),
        training=False, model_calls_this_analysis=0, external_quality_values_used=False,
        new_cloud_jobs_submitted=0)


def main():
    result=build()
    path=HERE/'MEASURED_BUDGET.json'
    with path.open('w',encoding='utf-8',newline='\n') as out:
        json.dump(result,out,ensure_ascii=False,allow_nan=False,indent=2)
        out.write('\n')
    print(json.dumps({k:result[k] for k in ('status','exact_target_shapes','planning_total_hours','quota_decision')},ensure_ascii=False))


if __name__=='__main__':
    main()
