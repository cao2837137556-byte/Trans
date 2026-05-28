# Reviewer Defense: Split-Aware Rebuild

## Q1: Did you recover row-level provenance?

Yes. The sidecar manifest maps current original100 rows to extracted TSV row order, packet timestamp, packet-order proxy, capture id, and feature-row hashes.

## Q2: Does this prove LOW-GUARD++ generalizes?

No. It proves the provenance blocker is partly resolved. Clean validation still requires a sufficiently large independent future/capture split and split-aware feature rebuild.

## Q3: Did continuous-state carryover invalidate the old result?

No direct invalidating artifact was found. But the old continuous-state result is not enough for a strong claim because split-boundary state carryover remains a plausible confound.

## Q4: Why not run LOW-GUARD++ now?

Because no clean purged split was selected. Running on reused locked bins would create another consistency check, not formal independent validation.
