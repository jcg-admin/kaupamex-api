"""Comprueba el rechazo de solicitudes no ejecutables sin tocar PostgreSQL."""
import argparse
import json
from pathlib import Path

import django

django.setup()

from orm.registry import Registry


parser = argparse.ArgumentParser()
parser.add_argument('--result', type=Path, required=True)
arguments = parser.parse_args()
key = 'contract_registry_request_probe'
original = Registry(key)
try:
    try:
        returned = Registry.new(key, install_modules=('contract_probe_missing_addon',))
    except NotImplementedError:
        outcome = 'REJECTED'
        ready = None
    else:
        outcome = 'RETURNED'
        ready = returned.ready
    preserved = Registry.registries.get(key) is original
    result = {
        'outcome': outcome, 'returned_ready': ready,
        'previous_registry_preserved': preserved,
        'scope': 'Proceso aislado y registro de metadatos; sin instalación ni SQL',
    }
    arguments.result.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    assert outcome == 'REJECTED' and preserved
finally:
    Registry.delete(key)
