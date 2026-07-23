"""Contrato de ``RequestLog`` en su nuevo hogar ``addons.observability``
(DEC-08/DEC-12, slice 3 de ``adoptar-arquitectura-server-service-odoo``).

``RequestLog`` es telemetria HTTP por request sin analogo Odoo (DEC-12): el
UNICO addon legitimamente net-new del arbol. Este test fija:

- importable desde el hogar canonico ``addons.observability.models``,
- append-only (hereda ``AppendOnlyModel`` de ``addons.base``, SOL-011/DEC-LOG-05),
- ``db_table`` fiel al app_label del nuevo addon (``observability_requestlog``),
- ``RequestLogMiddleware`` importable desde ``addons.observability.middleware``.

El contrato append-only detallado (INSERT permitido / UPDATE-DELETE de
instancia bloqueados / bulk permitido) vive en
``tests/unit/core/test_log_immutability.py`` — aqui solo se fija la ubicacion.

Toca DB -> django_db.
"""
import pytest

from addons.base.models import AppendOnlyModel
from addons.observability.middleware import RequestLogMiddleware
from addons.observability.models import RequestLog


def test_request_log_importable_desde_observability():
    """``RequestLog`` se importa desde ``addons.observability.models``."""
    assert RequestLog.__module__ == 'addons.observability.models.request_log'


def test_request_log_es_append_only():
    """``RequestLog`` hereda ``AppendOnlyModel`` (append-only, DEC-LOG-05)."""
    assert issubclass(RequestLog, AppendOnlyModel)


def test_request_log_db_table_es_observability_requestlog():
    """``db_table`` sigue la convencion default de Django: ``<app_label>_<model>``,
    fiel al nuevo app_label ``observability`` (sin ``db_table`` explicito en Meta)."""
    assert RequestLog._meta.db_table == 'observability_requestlog'
    assert RequestLog._meta.app_label == 'observability'


def test_request_log_middleware_importable_desde_observability():
    """``RequestLogMiddleware`` se importa desde ``addons.observability.middleware``."""
    assert RequestLogMiddleware.__module__ == 'addons.observability.middleware'


@pytest.mark.django_db
def test_request_log_crud_basico():
    """INSERT permitido; la fila persiste en la tabla del nuevo addon."""
    row = RequestLog.objects.create(
        correlation_id='cid-obs-1', method='GET', path='/x', status_code=200,
        duration_ms=1,
    )
    assert RequestLog.objects.filter(pk=row.pk).exists()
