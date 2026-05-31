# Gotham Fuller Artifact Risk Report

The full file summary confirms that Gotham is much stronger than the anonymous full-Mirai feature CSV for data semantics, but shortcut risks remain material.

High or medium-high risks:
- label_vs_file_id: cramers_v_weighted_file_summary=0.796124 (medium_high); mitigation: pre-register file/device/protocol/time disjoint contract; exclude source identifiers at feature gate
- label_vs_device: cramers_v_weighted_file_summary=0.673438 (medium_high); mitigation: pre-register file/device/protocol/time disjoint contract; exclude source identifiers at feature gate
- label_vs_protocol: cramers_v_weighted_file_summary=0.523638 (medium_high); mitigation: pre-register file/device/protocol/time disjoint contract; exclude source identifiers at feature gate

Interpretation:
- Label/file binding is expected in packet-capture datasets because attack campaigns are captured in named files, but it becomes a claim risk if split roles are not file-disjoint.
- Device/protocol/time binding can support meaningful drift only if the split contract declares it explicitly and prevents using final eval for selection.
- Source identifiers such as IP/MAC/port-like columns must be handled in the Feature / interface gate before model work.
