# restored115 Feature Mapping Report

Mapping confidence: `low`

The 115D dimension is consistent with a classic Kitsune-style restored115 vector. A tentative schema would be:

- current original100 = MI(15) + HH(35) + HH_jit(15) + HpHp(35)
- possible restored115 = MI(15) + Hstat(15) + HH(35) + HH_jit(15) + HpHp(35)

However, the full Mirai clean115 CSV has no feature header, no generation script, and no direct column-order provenance. Therefore:

- MI / HH / HH_jit / HpHp family membership cannot be verified by column name.
- lambda scales cannot be verified by column name.
- the extra15 cannot be safely named beyond a tentative Host-BW/Hstat hypothesis.
- `restored115_common100` cannot be safely constructed.

Decision: block interface smoke until feature-name/order mapping is recovered.
