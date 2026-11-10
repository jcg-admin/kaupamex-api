"""``_reflect_selections`` sólo refleja selecciones que son una lista — ≙
``odoo19c: odoo/addons/base/models/ir_model.py:1543-1548``::

    fields = [
        field
        for model_name in model_names
        for field_name, field in self.env[model_name]._fields.items()
        if field.type in ('selection', 'reference')
        if isinstance(field.selection, list)
    ]

Una selección invocable (``selection=lambda …``) no se refleja ni se valida:
su contenido depende de quién la llame. Aquí el equivalente es un campo de
Django con ``choices`` invocable, que Django envuelve en
``CallableChoiceIterator``. Diseño: ``designs/module-install-cycle.md``, L2.
"""
import pytest
from django.apps import apps
from django.core.exceptions import ValidationError

from addons.base.models.ir_model import IrModelFieldsSelection

pytestmark = pytest.mark.django_db


def test_a_callable_selection_is_left_out():
    bank = apps.get_model('base', 'ResPartnerBank')
    IrModelFieldsSelection._reflect_selections([bank])


def test_a_listed_selection_with_a_non_text_label_is_still_rejected(
        monkeypatch):
    bank = apps.get_model('base', 'ResPartnerBank')
    field = bank._meta.get_field('acc_type')
    monkeypatch.setattr(field, 'choices', [('bank', 1)])
    with pytest.raises(ValidationError):
        IrModelFieldsSelection._reflect_selections([bank])
