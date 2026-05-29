# issue27n Decision

primary_verdict = `restored115_feature_mapping_blocked`

clean115 construction is technically clear, but restored115 feature mapping is not safe enough to run LOW-GUARD interface smoke. The prior-use audit also finds that `my_gold_mirai_200k` likely covers the full Mirai prefix containing all benign rows, so strict isolation leaves no benign rows for clean ID/OOD/final benign evaluation.

The right next step is mapping/provenance recovery, not deployment robustness and not demotion.
