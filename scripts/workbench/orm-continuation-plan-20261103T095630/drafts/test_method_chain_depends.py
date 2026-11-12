"""Una extensión de un método de cálculo conserva las dependencias previas.

≙ ``Field.get_depends`` (``odoo19c: odoo/orm/fields.py:584-599``): las
dependencias de un cálculo son la unión del ``_depends`` de **todas** las
funciones que lo sobrescriben en el MRO (``resolve_mro``). Aquí una extensión
de addon no añade una clase al MRO: se instala en el sitio con
``chain_method``/``wrap_method``, que enlazan la implementación previa en
``_chain_previous``. Si ``get_depends`` no sigue ese enlace, la extensión
borra las dependencias de la base. Caso real: ``account_payment`` sustituía
``AccountPaymentMethodLine._compute_name`` y el campo quedaba sin ninguna.
"""
import pytest
from django.apps import apps

import api
from orm import registry
from orm.method_chain import chain_method, chain_depends

pytestmark = pytest.mark.django_db

AccountPaymentMethodLine = apps.get_model('account',
                                          'AccountPaymentMethodLine')


def test_the_extended_compute_keeps_the_base_dependency():
    field = AccountPaymentMethodLine._meta.get_field('name')
    assert 'payment_method.name' in registry.field_depends[field]


def test_a_chained_compute_unions_both_declarations():
    """``chain_method`` sobre un cálculo con ``@api.depends('a')`` y una
    extensión con ``@api.depends('b')``: la cadena declara las dos."""

    class Probe:
        @api.depends('a')
        def _compute_x(self):
            return None

    @api.depends('b')
    def _compute_x(self):
        return None

    chain_method(Probe, '_compute_x', _compute_x)
    assert set(chain_depends(Probe._compute_x)) == {'a', 'b'}
