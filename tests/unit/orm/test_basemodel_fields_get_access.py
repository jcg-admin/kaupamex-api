"""Las dos ramas de acceso de ``BaseModel.fields_get``.

``odoo19c: odoo/orm/models.py:3354-3366``: un campo que el usuario no puede
leer no aparece, y uno que no puede escribir sale con ``readonly`` cierto. El
diferencial (``test_contract_model_record_reference.py``) no alcanza esas
ramas: ningún campo de ``ir.attachment`` declara ``groups``. Aquí se miden
sobre un doble con un campo de grupo inaccesible (``NO_ACCESS``).

*Métrica:* los nombres y el ``readonly`` del resultado.
*Ciega a:* grupos reales de usuario, que necesitan ``res.users``.
"""
from orm.models import NO_ACCESS, BaseModel


class _Field:
    def __init__(self, groups=None, readonly=False):
        self.groups = groups
        self.readonly = readonly

    def get_description(self, env, attributes=None):
        return {'readonly': self.readonly}


class _Double:
    env = None
    _fields = {'open': _Field(), 'hidden': _Field(groups=NO_ACCESS)}
    _has_field_access = BaseModel._has_field_access


def test_an_unreadable_field_is_left_out():
    assert sorted(BaseModel.fields_get(_Double())) == ['open']


def test_a_readable_field_keeps_its_readonly():
    assert BaseModel.fields_get(_Double())['open'] == {'readonly': False}
