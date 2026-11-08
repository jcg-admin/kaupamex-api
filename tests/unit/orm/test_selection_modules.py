"""``Selection._selection_modules`` con ampliaciones de otro addon.

La rejilla diferencial (``model_persisted_grid``) lo mide sobre
``test_orm.model_selection_base``, donde la declaración y sus dos
ampliaciones son del mismo addon: ahí el módulo no discrimina. Este caso
usa ``ir.actions.server.usage``, que declara ``base``
(``odoo19c: odoo/addons/base/models/ir_actions.py:608-611``) y amplía
``base_automation`` (``odoo19c: addons/base_automation/models/
ir_actions_server.py:14-16``). La base de la referencia no instala
``base_automation``, así que el resultado esperado sale del texto de la
fuente y no de su proceso.
"""

from addons.base.models.ir_actions import IrActionsServer


def test_each_value_names_the_module_that_defines_it():
    field = IrActionsServer._meta.get_field('usage')
    modules = field._selection_modules(IrActionsServer)
    assert modules == {
        'ir_actions_server': {'base'},
        'ir_cron': {'base'},
        'base_automation': {'base_automation'},
    }


def test_a_computed_selection_has_no_modules():
    field = IrActionsServer._meta.get_field('usage')
    declared = field.selection
    field.selection = lambda model: declared
    try:
        assert field._selection_modules(IrActionsServer) == {}
    finally:
        field.selection = declared
