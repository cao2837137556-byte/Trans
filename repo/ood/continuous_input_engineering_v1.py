"""Original causal semantics with lossless bounded resident state storage."""
from pathlib import Path
import continuous_input_v3 as original
from spill_mapping_v1 import SpillMap


class Contexts(original.Contexts):
    def __init__(self,*args,storage_path,resident_contexts,**kwargs):
        super().__init__(*args,**kwargs)
        self.states=SpillMap(Path(storage_path),resident_contexts)

    def close(self):self.states.close()
