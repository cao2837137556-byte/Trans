"""Build pinned metadata-only input plan; seal after generated acceptance."""
import json
from pathlib import Path
import issue27frontend_paired_train_support_v1 as s

F4='runs/frontend_f4_fieldwise_input_feasibility_v1_20260905'
OUTER='runs/frontend_inheritance_outer_comparison_v1_20260909'
METADATA={
    F4+'/f4_context_index.csv':'c62d9fb84db7edf6eaa733fcb5ac72b928f3c783db9f2549afa81a3a77700444',
    F4+'/f4_target_audit.csv.gz':'fa4cb5efa3af5cc65cafc562c7c5e3d71aa2416910edd213ef5535f0a2da7c51',
    F4+'/f4_schema.json':'5d66120b8f1b224bdcb66ff46ae6923641d923cb1eee4554a6c8bf80179c3681',
    F4+'/SHA256SUMS':'432c03f543e3dc9c2bdc97cc9842e53fb846e4cf62f92fb5642b2896855d4df5',
    'runs/frontend_inheritance_outer_metadata_v1_20260909/qualified_metadata.json':'12e0846eb4cd54093d077ea82a8fd5bafb9e9f980cb45cf460d30e3db05b53e4',
    OUTER+'/input_target_receipts.json':'8f98c676d82088fdaad38e045a9a19185e2e231fd76ad4e915a8766030da341d',
    OUTER+'/prepared_input_receipt.json':'66151f43b866c1f3783a27fa0bfe282331d2ead7d2cf7f569ac2cca2ec850eb1'}
SOURCES={
    'parent':{'path':str(s.ROOT/F4/'f4_parent_features.f32le'),'bytes':107666280,'sha256':'5c4b20abcca4b192f91c6094eda370fb3c5e977c8106a69f713aa059f93b450d'},
    'outer':{'path':str(s.ROOT/OUTER/'outer_features.f32le'),'bytes':2705936,'sha256':'18c2533d2a91839cb17dbc35579fb96cb3050449d5badeeff2ac47d98158bd91'}}


def build_plan():
    s.verify_manifest(s.ROOT/s.meta.FREEZE,s.meta.FREEZE_SHA,allow_doc_links=True)
    s.verify_manifest(s.ROOT/s.MEMBERSHIP,s.MEMBERSHIP_SHA)
    for rel,h in METADATA.items():s.require(s.sha_file(s.ROOT/rel)==h,'PLAN_METADATA_PIN')
    plan=s.qualify_plan(s.read_csv(s.ROOT/s.MEMBERSHIP/'membership.csv'),
        s.read_csv(s.ROOT/s.meta.FREEZE/'lawful_target_metadata.csv.gz'),
        s.read_csv(s.ROOT/F4/'f4_context_index.csv'),s.read_csv(s.ROOT/F4/'f4_target_audit.csv.gz'),
        s.read_json(s.ROOT/'runs/frontend_inheritance_outer_metadata_v1_20260909/qualified_metadata.json')['contexts'],
        s.read_json(s.ROOT/OUTER/'input_target_receipts.json'))
    sched=s.read_json(s.ROOT/s.MEMBERSHIP/'schedule.json');a=plan['accounting']
    for k in ('N_A','N_B','steps_per_epoch','updates_per_arm','epoch_order_hashes'):s.require(a[k]==sched[k],'SCHEDULE_PIN')
    s.require(a['training']['events']==sched['train_context_events_both_arms'] and
              a['training']['padded_slots']==sched['train_padded_slots_both_arms'],'TRAIN_ACCOUNTING_PIN')
    s.require(plan['targets']==18266 and len(plan['contexts'])==12889,'PLAN_DENOMINATORS')
    s.require(a['total']['events']<=13664708 and a['training']['padded_slots']<=210647040,'FROZEN_ENVELOPE')
    folder=s.ROOT/s.PACKAGE;folder.mkdir(exist_ok=False)
    s.atomic_json(folder/'plan.json',plan)
    s.atomic_json(folder/'plan_access_receipt.json',{'real_feature_bytes_decoded':0,'real_model_forwards':0,
        'raw_packets':0,'metadata_pins':METADATA,'prefixes_with_inherited_identity':18266,
        'feature_hashes':'inherited only; not read during implementation',
        'initial_metadata_validation_correction':'F4 serializes true in lowercase; parser corrected before acceptance'})
    print(json.dumps({'targets':plan['targets'],'feature_bytes':plan['feature_bytes'],
        'accounting':{k:v for k,v in a.items() if k!='epoch_order_hashes'}},indent=2))


if __name__=='__main__':build_plan()
