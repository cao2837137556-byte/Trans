# Second Dataset Fallback Criteria

If full Mirai raw provenance cannot be recovered quickly, the project should start second-dataset intake instead of continuing anonymous_clean115 model work.

Hard requirements:

- benign traffic must contain multiple phases, environments, captures, or time windows so ID/OOD benign is semantically meaningful.
- attack labels must be available.
- raw pcap or flow records should exist, with timestamp/order metadata.
- capture/session/source metadata is strongly preferred.
- final OOD eval and attack eval must be report-only.
- attack support and attack eval must be disjoint.
- row-order/source artifact must be auditable before model execution.
- feature/interface gate must pass before any model claim.

Candidate families to inspect:

- IoT intrusion datasets with raw pcap and timestamps.
- CIC-style IDS datasets with PCAP/flows/timestamps.
- Bot-IoT / TON-IoT / CICIoT-style datasets only if benign count and metadata are enough.
- Any dataset with deployment-like benign drift and attack labels.

Do not choose a second dataset only because it is popular. It must satisfy the paper problem first.
