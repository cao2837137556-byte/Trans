# CKBM AMD 151583 metadata-writer recovery

Date: 2026-07-14
Original compute job: AMD `151583`
Original compute commit: `37b0fb4585d2634fa45fa2db31b1fead7bce886d`
Scientific status before recovery: not yet validated or registered

## Failure boundary

The job passed the frozen environment and CKBM contract-unit checks, ran for
23 minutes 18 seconds, completed all six protocol computations, and wrote the
scientific CSV tables.  It then failed at the first final metadata write:

```text
TypeError: write_text() got an unexpected keyword argument 'newline'
```

The frozen HPC Python does not support the `newline` keyword on
`Path.write_text`.  This is a deterministic launcher/output compatibility bug,
not a TabM training, data, threshold, memory, or metric-computation failure.
Intel job `151584` was cancelled before producing a second result.

No CKBM performance conclusion is allowed from the incomplete directory until
the existing scientific tables pass the formal validator and are pulled back.

## Repair

- Centralize LF output through `Path.open(..., newline="\n")`, which is
  supported by the frozen runtime.
- Exercise actual JSON writing in `contract-unit` so a future runtime cannot
  pass without testing the formerly failing API.
- Round-trip GO/NO-GO inputs through CSV in the contract test.  This protects
  boolean semantics during metadata-only recovery (`"False"` must not become
  truthy merely because it is a nonempty string).
- Add `finalize-existing`, restricted to seed 27.  It requires every formal
  table, every expected protocol, immutable manifest hashes, and zero report
  extension use before reconstructing the final JSON/Markdown artifacts.
- Record the original compute commit/hash separately from the recovery
  commit/hash and state explicitly that models were not retrained.
- Run the existing full formal validator and create the normal pullback archive.

The first `r2` recovery attempt stopped before writing any metadata because
unselected threshold rows are serialized with an empty `selected` field.  The
strict CSV boolean parser correctly rejected that unclassified `NaN`, but the
recovery contract had not yet assigned its intended meaning.  `r3` now treats
missing `selected`, gate, and support-use flags as false, while missing causal
violation flags remain conservatively true.  Contract-unit covers this exact
CSV round trip.

The recovery script is specific to AMD job `151583`.  It submits no Slurm job,
does not retrain or rescore a model, does not modify any frozen cache or split,
and does not use report labels for fit/select.  A recovered result is an urgent
single-seed route signal.  If it is a GO, a clean `COMPLETED 0:0` rerun remains
required before the result is treated as canonical paper evidence.
