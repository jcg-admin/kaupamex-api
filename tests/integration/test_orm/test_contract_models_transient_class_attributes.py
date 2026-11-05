"""Atributos de clase de ``TransientModel`` — ``odoo19c:
odoo/orm/models_transient.py:18-27``.

Oráculo leído de la referencia en ``odoo-tools@abe4040e``:

- ``_auto = True``, ``_register = False``, ``_abstract = False``,
  ``_transient = True`` (``:18-21``).
- ``_transient_max_count`` y ``_transient_max_hours`` son
  ``lazy_classproperty`` sobre ``config['osv_memory_count_limit']`` y
  ``config['transient_age_limit']`` (``:24-27``), cuyos valores por defecto
  son ``0`` y ``1.0`` (``odoo/tools/config.py:436-443``): sin configurar
  nada, un transitorio se barre a la hora y no tiene tope de filas.

Mutaciones que lo hacen caer: volver a la constante ``0`` de horas (cae la de
valores por defecto); leer el límite al importar en vez de al primer acceso
(cae la de configuración); retirar cualquiera de los tres atributos
declarados (cae la de banderas).
"""
import pytest
from django.test import override_settings

from orm.models_transient import TransientModel

pytestmark = pytest.mark.integration


def _fresh_subclass():
    """Una subclase nueva: el ``lazy_classproperty`` memoriza en el dueño."""
    declared = TransientModel.__dict__
    return type('ProbeTransientLimits', (), {
        name: declared[name]
        for name in ('_transient_max_count', '_transient_max_hours')})


class TestTransientFlags:

    def test_the_four_declared_flags(self):
        assert TransientModel.__dict__['_auto'] is True
        assert TransientModel.__dict__['_register'] is False
        assert TransientModel.__dict__['_abstract'] is False
        assert TransientModel.__dict__['_transient'] is True


class TestTransientLimitsComeFromConfiguration:

    def test_the_reference_defaults(self):
        probe = _fresh_subclass()
        assert probe._transient_max_count == 0
        assert probe._transient_max_hours == 1.0

    @override_settings(OSV_MEMORY_COUNT_LIMIT=25, TRANSIENT_AGE_LIMIT=0.5)
    def test_a_configured_limit_is_read_on_first_access(self):
        probe = _fresh_subclass()
        assert probe._transient_max_count == 25
        assert probe._transient_max_hours == 0.5
