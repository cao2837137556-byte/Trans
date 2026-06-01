# Gotham Kitsune115 Frontend Recovery Report

- Existing `repo/kitsune_frontend_original/netStat.py` emits 100D because Host BW `Hstat` is commented out.
- This issue restores the commented Host BW block as an explicit `RestoredNetStat115` implementation inside the issue27ab script.
- The restored family is `H_*`, 3 statistics across 5 lambdas, giving 15 additional dimensions.
- Total schema: MI_dir 15 + H 15 + HH 35 + HH_jit 15 + HpHp 35 = 115.
- The original frontend files are not modified, so old original100 artifacts remain reproducible.
- This is a frontend/data gate only; no model scores are computed.
