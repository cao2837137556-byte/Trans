# issue27v Next Action

Recommended issue:

`issue27v_gotham_user_confirmed_download_and_file_level_data_gate_2026-05-28`

Before starting:

- ask user to confirm the 23.8GB Gotham download.
- use only `D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\raw`.
- do not stage raw data.

After download:

1. compute zip hash and compare with Zenodo md5.
2. inspect zip listing before extraction.
3. extract metadata/README/CSV schema first.
4. audit device IDs, timestamps, attack labels, benign phases, and source/capture coupling.
5. decide whether Gotham can construct ID benign, OOD benign, final OOD, attack support, and attack eval.
6. only after Data Gate passes should Feature/interface gate begin.

Fallback: if user does not want the large download or Gotham file-level audit fails, run ToN-IoT metadata intake.
