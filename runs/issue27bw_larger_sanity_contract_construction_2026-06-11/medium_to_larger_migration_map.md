# Medium To Larger Migration Map

## Purpose

This file maps the medium diagnostic roles to the larger sanity contract. It prevents old report-only data from silently becoming selection data.

## Mapping

| Medium role | Larger role | Migration rule | Selection allowed |
|---|---|---|---|
| `id_benign_train` | `id_benign_train` | expand to more benign files/devices, file-disjoint from ID calibration | yes |
| `id_calib` | `id_benign_calib` | use file-disjoint ID calibration files; medium single-source caveat must not carry forward | yes |
| `ood_benign_val` | `ood_benign_val` | independent benign devices/files for OOD calibration | yes |
| `ood_stress` | `ood_benign_stress` | development-side hard benign drift only; no final OOD | yes |
| `final_ood_benign_eval` | `sealed_final_ood` | sealed from issue27bw forward; report-only replay | no |
| `attack_support` | `attack_support_candidate_pool` | development-side labelled attack support only | yes |
| `support_val` | derived from `attack_support_candidate_pool` | development-side threshold/support sanity only | yes |
| `dev/query attack` | `dev_future_attack_query` | development-side query for mechanism design; no final selection from outcomes | limited diagnostics only |
| `attack_eval` | `sealed_final_attack` | report-only replay after config freeze | no |

## Non-Negotiable Rule

Old report-only roles cannot be reused as selection roles just because the larger contract is being rebuilt. If a role was report-only in a previous diagnostic, it must either remain report-only or be explicitly downgraded to development diagnostic with a written caveat.
