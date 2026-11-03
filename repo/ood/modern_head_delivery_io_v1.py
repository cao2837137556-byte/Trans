"""Stdlib-only result export; split jobs retain independent receipts and archives."""
import os
import onboarding_delivery_io_v1 as io

MODE = os.environ.get('MODERN_HEAD_EXECUTION_MODE', 'full')
if MODE not in ('full', 'heads', 'modules'):
    raise RuntimeError('INVALID_MODERN_HEAD_EXECUTION_MODE')

io.VERSION = 'modern-head-delivery-io-v1r1-20261018'
PREFIX = {'full': 'modern_head', 'heads': 'modern_heads', 'modules': 'modern_modules'}[MODE]
io.EXPORT_NAME = PREFIX + '_pullback.tar.gz'
io.MANIFEST_NAME = PREFIX + '_export_manifest.json'
_original_omit = io._omit_reason
_ARCHIVES = {'modern_head_pullback.tar.gz', 'modern_heads_pullback.tar.gz', 'modern_modules_pullback.tar.gz'}


def omit(parts):
    if len(parts) == 1 and parts[0] in _ARCHIVES:
        return 'previous phase archive; original evidence, manifest and SHA sidecar retained without recursive archive nesting'
    if parts[0] in ('extra_deps','wheelhouse'):
        return 'reproducible isolated dependencies; wheel/source identities retained in package manifest'
    return _original_omit(parts)


io._omit_reason = omit
if __name__ == '__main__':
    io.main()
