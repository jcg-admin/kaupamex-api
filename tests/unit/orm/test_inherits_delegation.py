"""Qué nombres delega ``orm.inherits`` del padre al hijo.

La regla es la de ``_add_inherited_fields`` (``odoo19c: odoo/orm/
model_classes.py:480-508``): todo campo del padre que el hijo no redefine,
sea columna o no. La rejilla diferencial mide la lectura y la escritura
contra la referencia; este archivo mide la precedencia del hijo, que la
rejilla no aísla: el ``attname`` de una FK propia se asigna en la instancia
al construirla y nunca se manda al padre.
"""

from types import SimpleNamespace

from orm import inherits
from orm.fields_nonstored import non_stored_fields
from orm.registry import MODELS_BY_NAME


def test_the_non_column_fields_of_the_parent_are_delegated():
    child = MODELS_BY_NAME['test_orm.related_inherits']
    for name in ('foo_name', 'foo_bar_name', 'foo_bar_ids', 'foo_foo_ids'):
        assert name in child._inherits_fields


def test_the_attname_of_an_own_field_stays_with_the_child(monkeypatch):
    """Ningún modelo instalado hoy tiene un ``attname`` propio que coincida
    con un nombre del padre (medido sobre los siete con ``_inherits``), así
    que el caso se arma: Django asigna el ``attname`` con ``setattr`` al
    construir la instancia, y mandarlo al padre perdería la FK del hijo."""
    own_fk = SimpleNamespace(name='company', attname='company_id')
    child = type('Child', (), {
        '_meta': SimpleNamespace(get_fields=lambda: [own_fk])})
    parent_names = {'company_id': object(), 'company': object(),
                    'street': object()}
    monkeypatch.setattr(inherits, 'model_field_registry',
                        lambda model: parent_names)
    assert inherits._delegable_field_names(object(), child) == ('street',)


def test_the_private_and_primary_key_names_are_never_delegated():
    for model in MODELS_BY_NAME.values():
        if not model.__dict__.get('_inherits'):
            continue
        for name in model._inherits_fields:
            assert not name.startswith('_')
            assert name not in ('id', 'pk')


def test_the_names_are_resolved_after_the_registry_is_ready():
    """La lista no se calcula dentro de ``ready()``: consultar ahí el mapa
    del padre lo memorizaba sin los campos que otra app le contribuye
    después. Resuelta con el registro listo, incluye el ``city_id`` que
    ``base_address_extended`` añade a ``res.partner``."""
    partner = MODELS_BY_NAME['res.partner']
    assert 'city_id' in non_stored_fields(partner)
    assert 'city_id' in MODELS_BY_NAME['res.users']._inherits_fields
