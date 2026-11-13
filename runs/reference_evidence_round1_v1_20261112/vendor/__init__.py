"""Use the pinned local production modules, with their original import names."""
from pathlib import Path
import sys

directory = Path(__file__).resolve().parent
for name in ('indexed_features_v1', 'legacy_qref_common_v1', 'legacy_qref_data_v1',
             'causal_reference_overlap_v1', 'stream_core', 'source_packets', 'packet_reader',
             'physical', 'geometry_frozen'):
    if name in sys.modules and Path(sys.modules[name].__file__).resolve().parent != directory:
        raise ImportError('FOREIGN_PRODUCTION_MODULE:' + name)
sys.path.insert(0, str(directory))
