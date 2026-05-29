# restored115_common100 Mapping Blocked

`restored115_common100` was not materialized and was not used for smoke.

The tempting construction is to assume clean115 is ordered as:

`MI(15) + Hstat(15) + HH(35) + HH_jit(15) + HpHp(35)`

and then remove indices `15:30` to recover the same 100 columns as current `original100`.

That assumption is not claim-safe here because the full Mirai clean115 CSV has no feature names, no column-order manifest, and no generator script proving this order. Deleting 15 anonymous columns would create a pseudo-original100 representation and could manufacture a misleading comparison.

Required next evidence:

- feature-name/order mapping for the 115 columns, or
- a source extractor script that emits the 115 columns in documented order, or
- re-extraction into current original100 with known headers.
