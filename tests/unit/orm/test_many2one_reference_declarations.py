"""Las declaraciones ``Many2oneReference`` de la fuente.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
many2one-reference-declarations.md``.
"""
import pytest

from addons.base.models.ir_attachment import IrAttachment
from addons.base.models.ir_model import IrModelData
from addons.base_automation.models.base_automation import BaseAutomation
from addons.mail.models.mail_activity import MailActivity
from addons.mail.models.mail_followers import MailFollowers
from addons.mail.models.mail_message import MailMessage
from orm.fields_reference import Many2oneReference


@pytest.mark.parametrize('model, name, model_field', [
    (IrAttachment, 'res_id', 'res_model'),
    (IrModelData, 'res_id', 'model'),
    (MailMessage, 'res_id', 'model'),
    (MailActivity, 'res_id', 'res_model'),
    (MailFollowers, 'res_id', 'res_model'),
    (BaseAutomation, 'trg_field_ref', 'trg_field_ref_model_name'),
])
def test_the_field_is_a_many2one_reference(model, name, model_field):
    field = model._meta.get_field(name)
    assert isinstance(field, Many2oneReference)
    assert field.model_field == model_field
    assert field.type == 'many2one_reference'
