# Gotham Source-Like Feature Inventory Report

- Unique processed CSV fields plus derived identifiers inventoried: 30
- Fields forbidden from main model input by blocking/high shortcut risk: attack_type, csv_archive_path, device, eth.dst, eth.src, file_id, frame.time, inferred_device, ip.dst, ip.src, label, pcap_archive_path, source/capture/path
- The inventory deliberately distinguishes split/audit/pairing fields from model input fields.
