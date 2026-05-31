# Gotham Larger Sample Artifact Risk Report

Largest observed risk: `label_vs_file_id` with level `high`.

The sampled manifest confirms that label is strongly entangled with file/device/time groupings unless the split is deliberately designed. This is not a reason to abandon Gotham, but it blocks immediate Feature/interface gate promotion. The next gate must construct a fuller manifest and pre-register exact row/file/device/time disjoint splits.
