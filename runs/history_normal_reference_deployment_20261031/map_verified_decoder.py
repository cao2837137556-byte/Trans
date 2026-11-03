"""Record the decoder path observed on HPC, preserving all scientific inputs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_REL = 'runs/history_normal_reference_v1_20261031/'
EXPECTED = 'f789739690ed83024c02ac392e08fdbe12720bfe885f8e2077bb0f534cf7f146'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, body):
    path.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    manifest_path = HERE/'DELIVERY_INPUTS.json'
    assert sha(manifest_path) == EXPECTED, 'DELIVERY_CHANGED_BEFORE_PATH_CORRECTION'
    config_path = HERE/'staged_root'/PACKAGE_REL/'config/EXECUTION.json'
    seal_path = HERE/'staged_root'/PACKAGE_REL/'CODE_MANIFEST.json'
    old_config = json.loads(config_path.read_text(encoding='utf-8'))
    assert old_config['tshark'] == '/usr/bin/tshark'
    history = HERE/'decoder_mapping_correction'
    history.mkdir(exist_ok=False)
    for source, name in ((manifest_path, 'DELIVERY_INPUTS.original.json'),
                         (config_path, 'EXECUTION.original.json'),
                         (seal_path, 'CODE_MANIFEST.original.json'),
                         (HERE/'BUILD_RECEIPT.json', 'BUILD_RECEIPT.original.json')):
        (history/name).write_bytes(source.read_bytes())
    config = dict(old_config, tshark='/share/software/tshark-4.6.6/bin/tshark')
    assert {k:v for k,v in old_config.items() if k!='tshark'} == {k:v for k,v in config.items() if k!='tshark'}
    write(config_path, config)
    seal = json.loads(seal_path.read_text(encoding='utf-8'))
    seal['code_sha256']['config/EXECUTION.json'] = sha(config_path)
    write(seal_path, seal)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    changes = []
    for row in manifest['files']:
        if row['remote_relative_path'] in (PACKAGE_REL+'config/EXECUTION.json', PACKAGE_REL+'CODE_MANIFEST.json'):
            path = Path(row['local_path'])
            changes.append(dict(relative=row['remote_relative_path'], before=row['sha256'], after=sha(path)))
            row.update(sha256=sha(path), bytes=path.stat().st_size)
    assert len(changes) == 2
    write(manifest_path, manifest)
    receipt_path = HERE/'BUILD_RECEIPT.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    receipt.update(delivery_inputs_sha256=sha(manifest_path), relocated_code_manifest_sha256=sha(seal_path),
                   total_unique_bytes=sum(r['bytes'] for r in manifest['files']),
                   tshark_observed_remote_path=config['tshark'])
    write(receipt_path, receipt)
    result = dict(status='PATH_ONLY_CORRECTION', evidence='User-connected node168: source frontend_compat_v1/environment.sh; command -v tshark',
                  previous_manifest_sha256=EXPECTED, manifest_sha256=sha(manifest_path),
                  relocated_code_manifest_sha256=sha(seal_path), changes=changes,
                  original_scientific_package_edited=False, scientific_semantics_changed=False)
    write(history/'CORRECTION_RECEIPT.json', result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
