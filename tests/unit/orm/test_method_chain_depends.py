"""Una extensión de un método de cálculo conserva las dependencias previas.

≙ ``Field.get_depends`` (``odoo19c: odoo/orm/fields.py:584-599``): las
dependencias de un cálculo son la unión del ``_depends`` de **todas** las
funciones que lo sobrescriben en el MRO (``resolve_mro``), de la más derivada
a la base. Aquí una extensión de addon no añade una clase al MRO: se instala en
el sitio con ``chain_method``/``wrap_method``, que enlazan la implementación
previa en ``_chain_previous``. Si ``get_depends`` no sigue ese enlace, la
extensión borra las dependencias de la base. Caso real: ``account_payment``
sustituía ``AccountPaymentMethodLine._compute_name`` y el campo quedaba sin
ninguna dependencia, así que cambiar el nombre del método no lo recalculaba.
"""
import pytest
from django.apps import apps

import api
from orm import registry
from orm.environments import env as current_env
from orm.environments import transaction_scope
from orm.method_chain import chain_depends, chain_links, chain_method
from orm.method_chain import wrap_method

AccountPaymentMethod = apps.get_model('account', 'AccountPaymentMethod')
AccountPaymentMethodLine = apps.get_model('account',
                                          'AccountPaymentMethodLine')


def _probe():
    class Probe:
        @api.depends('a')
        def _compute_x(self):
            return None
    return Probe


def test_a_chain_keeps_the_base_dependency_when_the_extension_declares_none():
    probe = _probe()

    def _compute_x(self):
        return None

    chain_method(probe, '_compute_x', _compute_x)
    assert chain_depends(probe._compute_x) == ['a']


def test_a_chained_compute_unions_both_declarations_derived_first():
    probe = _probe()

    @api.depends('b')
    def _compute_x(self):
        return None

    chain_method(probe, '_compute_x', _compute_x)
    assert chain_depends(probe._compute_x) == ['b', 'a']


def test_a_wrapped_compute_unions_both_declarations():
    probe = _probe()

    @api.depends('b')
    def _compute_x(self, previous):
        return previous()

    wrap_method(probe, '_compute_x', _compute_x)
    assert chain_depends(probe._compute_x) == ['b', 'a']


def test_successive_chains_keep_every_link_in_order():
    probe = _probe()

    @api.depends('b')
    def second(self):
        return None

    @api.depends('c')
    def third(self, previous):
        return previous()

    chain_method(probe, '_compute_x', second)
    wrap_method(probe, '_compute_x', third)
    assert chain_depends(probe._compute_x) == ['c', 'b', 'a']
    assert len(chain_links(probe._compute_x)) == 3


def test_a_repeated_dependency_appears_once():
    probe = _probe()

    @api.depends('a', 'b')
    def _compute_x(self):
        return None

    chain_method(probe, '_compute_x', _compute_x)
    assert chain_depends(probe._compute_x) == ['a', 'b']


def test_reinstalling_the_same_extension_adds_no_link():
    probe = _probe()

    @api.depends('b')
    def _compute_x(self):
        return None

    chain_method(probe, '_compute_x', _compute_x)
    chain_method(probe, '_compute_x', _compute_x)
    assert chain_depends(probe._compute_x) == ['b', 'a']
    assert len(chain_links(probe._compute_x)) == 2


def test_a_callable_dependency_receives_the_model():
    probe = _probe()

    @api.depends(lambda model: [f'{model}.y'])
    def _compute_x(self):
        return None

    chain_method(probe, '_compute_x', _compute_x)
    assert chain_depends(probe._compute_x, 'm') == ['m.y', 'a']


def test_the_extended_compute_keeps_the_base_dependency_in_the_registry():
    field = AccountPaymentMethodLine._meta.get_field('name')
    assert 'payment_method.name' in registry.field_depends[field]
    assert 'payment_method.name' in field.get_depends(
        AccountPaymentMethodLine)[0]


@pytest.mark.django_db
def test_renaming_the_method_marks_the_line_name_for_recompute():
    """La dependencia no sólo se declara: el grafo de disparo la ejecuta."""
    method = AccountPaymentMethod.objects.create(
        name='Manual', code='manual_probe', payment_type='inbound')
    line = AccountPaymentMethodLine.objects.create(payment_method=method)
    field = AccountPaymentMethodLine._meta.get_field('name')
    with transaction_scope():
        current_env().flush_all()
        method.name = 'Manual renombrado'
        method.save(update_fields=['name'])
        assert current_env().is_to_compute(field, line.pk)


def test_the_base_reached_by_mro_and_by_the_chain_counts_once():
    """``StockLot._compute_display_name`` encadena sobre la base heredada:
    ``resolve_mro`` devuelve la base desde la clase padre y el envoltorio la
    alcanza otra vez por ``_chain_previous``. Cada función cuenta una vez.

    ``'name'`` sí sale dos veces, y es la fuente: lo declaran dos funciones
    distintas —la extensión y la base, por ``_rec_name``— y ``get_depends``
    hace ``depends.extend`` por función, sin deduplicar valores
    (``odoo19c: odoo/orm/fields.py:592-596``). Lo que no sale es la base
    contada dos veces, que daba ``'name'`` tres veces."""
    stock_lot = apps.get_model('stock', 'StockLot')
    field = stock_lot._meta.get_field('display_name')
    assert list(registry.field_depends[field]) == [
        'name', 'expiration_date', 'alert_date',
        'product.product_tmpl.use_expiration_date', 'name']
