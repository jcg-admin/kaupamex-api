"""``field_inverses`` de un ``Many2one`` con ``One2many`` declarados.

En la referencia, ``One2many.setup_inverses`` (``odoo19c: odoo/orm/
fields_relational.py:891-899``) apunta cada ``One2many`` a su ``Many2one``
inverso y al revés. ``test_orm.discussion`` declara tres sobre
``test_orm.message.discussion`` (``odoo/addons/test_orm/models/test_orm.py:
97-103``): ``messages``, ``important_messages`` y
``very_important_messages``. Ésos son los inversos del ``Many2one``.

El ``Many2one`` del puerto lleva ``related_name='+'``: Django crea una
relación inversa oculta, sin accesor, que recorrerla devolvía vacío y que,
anotada como inverso, tapaba la búsqueda de respaldo del recálculo
(H-API-1165). No es un inverso de la referencia y no se anota.
"""

from django.apps import apps

from orm import registry


def _model(name):
    return next(model for model in apps.get_models()
                if getattr(model, '_name', None) == name)


def test_the_inverses_of_the_many2one_are_the_declared_one2many():
    field = _model('test_orm.message')._fields['discussion']
    names = sorted(inverse.name for inverse in registry.field_inverses[field])
    assert names == [
        'important_messages', 'messages', 'very_important_messages']
