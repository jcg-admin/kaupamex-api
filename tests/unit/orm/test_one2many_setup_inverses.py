"""``One2many.setup_inverses`` — ≙ ``odoo19c: odoo/orm/fields_relational.py:
891-899``.

Docstring de la clase base, verbatim (``:96-97``): *"Populate ``inverses``
with ``self`` and its inverse fields."* El ``One2many`` declarado apunta a su
``Many2one`` inverso, y el inverso a él; con un inverso entero
(``Many2oneReference``) sólo se anota la vuelta, porque escribir el
``One2many`` no invalida un par ``res_model``/``res_id``.

``test_orm.discussion.messages`` invierte ``test_orm.message.discussion``
(``odoo/addons/test_orm/models/test_orm.py:97``).
"""

from django.apps import apps

from orm import registry
from tools.misc import Collector


def _model(name):
    return next(model for model in apps.get_models()
                if getattr(model, '_name', None) == name)


def test_a_declared_one2many_links_itself_and_its_many2one():
    messages = _model('test_orm.discussion')._fields['messages']
    discussion = _model('test_orm.message')._fields['discussion']
    inverses = Collector()
    messages.setup_inverses(registry.MODELS_BY_NAME, inverses)
    assert inverses[messages] == (discussion,)
    assert inverses[discussion] == (messages,)
    assert set(inverses) == {messages, discussion}


def test_the_registry_collects_inverses_through_the_field_method():
    discussion = _model('test_orm.message')._fields['discussion']
    names = sorted(inverse.name
                   for inverse in registry.field_inverses[discussion])
    assert names == [
        'important_messages', 'messages', 'very_important_messages']
