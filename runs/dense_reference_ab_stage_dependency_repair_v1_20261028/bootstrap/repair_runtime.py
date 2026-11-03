"""Strictly load the frozen six-module repair in parent and child interpreters."""
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import sys


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            value.update(block)
    return value.hexdigest()


def require(value, message):
    if not value:
        raise RuntimeError(message)


def dependency_manifest(root):
    root = Path(root).resolve()
    manifest = json.loads((root/'DEPENDENCY_CLOSURE.json').read_text(encoding='utf-8'))
    dependencies = manifest['dependencies']
    require(set(dependencies) == {
        'constrained_onboarding_core_v3', 'onboarding_budget_v1', 'indexed_features_v1',
        'legacy_qref_common_v1', 'legacy_qref_data_v1', 'causal_reference_overlap_v1'},
        'EXACT_SIX_MODULE_CLOSURE_REQUIRED')
    for name, entry in dependencies.items():
        path = root/'vendor/ood'/(name+'.py')
        require(path.is_file() and sha(path) == entry['sha256'], 'FROZEN_VENDOR_SHA:'+name)
    return dependencies


class FrozenVendorFinder(importlib.abc.MetaPathFinder):
    def __init__(self, root, dependencies):
        self.root, self.dependencies = Path(root).resolve(), dependencies

    def find_spec(self, fullname, path=None, target=None):
        if fullname not in self.dependencies:
            return None
        source = self.root/'vendor/ood'/(fullname+'.py')
        require(sha(source) == self.dependencies[fullname]['sha256'], 'FROZEN_VENDOR_IMPORT_SHA:'+fullname)
        return importlib.util.spec_from_file_location(fullname, source)


def install(root):
    """Names in this closure can never resolve through a root-repo fallback."""
    root = Path(root).resolve()
    dependencies = dependency_manifest(root)
    for name in dependencies:
        cached = sys.modules.get(name)
        if cached is not None:
            require(Path(cached.__file__).resolve() == root/'vendor/ood'/(name+'.py'),
                    'UNTRUSTED_PRELOADED_VENDOR:'+name)
    if not any(isinstance(f, FrozenVendorFinder) and f.root == root for f in sys.meta_path):
        sys.meta_path.insert(0, FrozenVendorFinder(root, dependencies))
    return dependencies


def install_from_environment():
    root = os.environ.get('PAPER04_DEPENDENCY_REPAIR')
    if root:
        expected = os.environ.get('PAPER04_REPAIR_MANIFEST_SHA256', '')
        require(len(expected) == 64 and sha(Path(root)/'PACKAGE_SHA256SUMS') == expected,
                'REPAIR_BOOTSTRAP_MANIFEST_SHA')
        sealed={}
        for line in (Path(root)/'PACKAGE_SHA256SUMS').read_text(encoding='utf-8').splitlines():
            digest,relative=line.split('  ',1)
            require(relative not in sealed,'REPAIR_BOOTSTRAP_DUPLICATE_MANIFEST_ENTRY')
            sealed[relative]=digest
        require(sealed.get('DEPENDENCY_CLOSURE.json')==sha(Path(root)/'DEPENDENCY_CLOSURE.json'),
                'REPAIR_BOOTSTRAP_CLOSURE_SEAL_SHA')
        install(root)
