"""Annul duplicate-file semantics only in memory; expected pytest exit1."""
from pathlib import Path
from types import SimpleNamespace

import django
import pytest

django.setup()

from modules import loading

original = loading.load_data


def deduplicating_data(idref, mode, kind, package, *, using):
    seen = set()
    manifest = {}
    for key, filenames in package.manifest.items():
        manifest[key] = []
        for filename in filenames:
            if filename not in seen:
                manifest[key].append(filename)
                seen.add(filename)
    changed = SimpleNamespace(name=package.name, manifest=manifest)
    return original(idref, mode, kind, changed, using=using)


loading.load_data = deduplicating_data
root = Path(__file__).resolve().parents[4]
print('Negative control: duplicate-file execution annulled only in memory', flush=True)
raise SystemExit(pytest.main(['--noconftest','-o','addopts=', '-q',
                             str(root/'tests/unit/modules/test_loading.py')]))
