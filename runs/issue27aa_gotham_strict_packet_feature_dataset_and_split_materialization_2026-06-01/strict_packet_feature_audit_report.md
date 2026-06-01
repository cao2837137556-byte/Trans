# Strict Packet Feature Audit Report

- strict features: frame.len, ip.flags, ip.tos, ip.ttl, tcp.flags, tcp.pdu.size, tcp.window_size_scalefactor, tcp.window_size_value
- constant features: none
- high-missing features (>95% invalid/missing): ip.tos, tcp.pdu.size
- forbidden fields in feature header: none
- Ports/protocol/IP/MAC/time/path/device/labels are not present in the model-feature artifact.
- This audit checks feature availability and leakage policy, not model predictive power.
- Important limitation: this strict packet-header feature space is deliberately source-clean but thin. If interface smoke shows inadequate usable signal, the next repair should be a preregistered flow/PCAP-derived feature path, not ad hoc reintroduction of IP, MAC, ports, protocol, file, or device identifiers.
