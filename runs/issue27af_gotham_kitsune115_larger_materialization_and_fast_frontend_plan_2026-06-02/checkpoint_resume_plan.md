# Checkpoint / Resume Plan

- checkpoint every N packets or N emitted rows for heavy ip-camera files.
- store frontend state snapshot hash before and after checkpoint.
- store packet_start, packet_end, sidecar row range, partial output hash.
- resume must skip already-emitted rows without duplication and preserve 115D schema/order.
- crash recovery validates state_hash_before against the saved checkpoint before appending.
