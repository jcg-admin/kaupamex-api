"""Anulación en memoria del contexto: el router real debe delatar el destino erróneo."""
from contextlib import nullcontext
from unittest.mock import patch

import django
import pytest

django.setup()

from service import db

with patch.object(db, 'company_scope', lambda company: nullcontext()):
    raise SystemExit(pytest.main([
        '--confcutdir=tests/unit/service', '-o', 'addopts=', '--tb=short',
        'tests/unit/service/test_provision_company.py', '-q',
    ]))
