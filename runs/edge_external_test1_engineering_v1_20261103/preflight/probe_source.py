"""Small source-only runtime/parity probe; not the external E2E gate."""
import json
from pathlib import Path

import run_preflight as runtime
from engine import frozen_assets, source_parity

out = Path(__file__).resolve().parent / 'source_probe'
out.mkdir(exist_ok=False)
progress = runtime.Progress(out)
env = runtime.environment()
freeze, spec, normalizer, pins = frozen_assets()
result = source_parity(spec, normalizer, freeze, progress)
runtime.write(out / 'RESULT.json', dict(status='SOURCE_ONLY_PROBE', environment=env,
    result=result, external_E3_rows=0, external_distance_pairs=0,
    external_quality_metrics=False, real_external_slice_e2e_pass=False))
print(json.dumps(result, indent=2))
