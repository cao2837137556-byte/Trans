# Preflight Adapter Bottleneck Diagnosis Check

- Successfully read issue23 locked validation: yes.
- Successfully read issue24 adapter upgrade results: yes.
- V1 / V2_top64 / adapter row-level scores persisted by issue23/24: no.
- Row-level scores reconstructed for diagnosis only: yes, representative seed 42.
- attack eval / OOD eval row-level labels available for diagnostic reconstruction: yes.
- locked bins 5/6/7/8 per-bin score distribution available: yes.
- bin6/bin7 degradation samples analyzable: yes.
- bin8 improvement samples analyzable: yes.
- LR vs weighted LR / SVM score changes analyzable: yes.
- New adapter training as method claim: no.
- This run is diagnosis only, not method claim: yes.
