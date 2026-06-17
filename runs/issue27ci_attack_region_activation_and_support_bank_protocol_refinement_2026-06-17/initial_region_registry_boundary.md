# Initial Region Registry Boundary

## Key Answer

The current `512` selected support rows do not yet have known active attack regions.

They have:

- exact attack labels;
- semantic groups;
- provenance seeds;
- train/validation partitions;
- source hashes and role-access cleanliness.

They do not yet have:

- geometric candidate regions;
- active region status;
- prototypes;
- radius or shell boundaries;
- OOD-overlap warnings;
- unknown behavior under certified dev query.

## Treatment of issue27cf `region_manifest.csv`

issue27cf `region_manifest.csv` has `16` rows. In issue27ci terminology these are `provenance_seed` rows, not active attack regions.

They are useful because they preserve:

- device/source group;
- exact attack label;
- PCAP path;
- phase;
- row count;
- semantic group.

They are insufficient because they do not test:

- whether rows are close in the 115D/evidence space;
- whether a label has multiple geometric modes;
- whether different labels overlap;
- whether benign/OOD development rows overlap;
- whether a query falls in core, near, uncertain, or out-of-region shells.

## Initial Scope Recommendation

issue27cj should instantiate `initial_region_registry_v1` from the selected support bank, not from all `69,492` unused candidates.

Rationale:

- The selected `512` rows are the frozen initial memory.
- The unused candidate pool has no default reuse identity.
- Reopening all candidates would mix support-bank refinement with candidate expansion.

The unused `69,492` candidate pool remains provenance and future expansion source only.
