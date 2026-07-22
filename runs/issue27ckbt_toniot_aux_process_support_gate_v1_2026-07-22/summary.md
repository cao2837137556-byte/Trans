# CKBT ToN-IoT auxiliary process-support gate

Status: `TONIOT_AUX_PROCESS_SUPPORT_CANDIDATE_READY_FOR_STATIC_EXPERT_ONLY`.

- Reused the dataset-provided mature Bro/Zeek 21-field `conn.log` representation and the prior CKAN loader policy.
- Built an independent auxiliary candidate bank: 2,000 fit + 500 select scanning connections and 2,000 fit + 500 select password connections.
- Every selected row is a unique direct join on `floor(conn.ts)`, source/destination IP and port, and protocol to the ToN-IoT GroundTruth event.
- Fit and select use different conn-log/GroundTruth file pairs. This is source-file separation, not a claim of independent campaigns.
- Seven additional scan/password conn files remain unused by this route.
- The mapping is generic mechanism supervision (`scan`, `credential_bruteforce`), not a claim that ToN labels equal Gotham TCP Scan/Telnet labels.
- Because the provided logs lack explicit log-emission time, these rows may supervise only a static completed-connection expert. They are forbidden for temporal replay.
- Gotham support stays 385/127; all Gotham report/sealed families remain at zero use. No model was trained.
