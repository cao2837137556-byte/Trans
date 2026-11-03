"""Fail closed at child startup; active only for the explicit repair runtime."""
import os
import sys

if os.environ.get('PAPER04_DEPENDENCY_REPAIR'):
    try:
        from repair_runtime import install_from_environment
        install_from_environment()
    except BaseException as exc:
        sys.stderr.write('PAPER04_REPAIR_BOOTSTRAP_FATAL: '+str(exc)+'\n')
        sys.stderr.flush()
        # Python otherwise ignores sitecustomize failures and continues.
        os._exit(78)
