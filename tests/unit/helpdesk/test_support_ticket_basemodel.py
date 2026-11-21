"""``support.ticket`` como ``BaseModel``.

≙ el programa ``basemodel-adoption-0397``: todo modelo con ``_name`` es un
``BaseModel`` (``odoo19c: odoo/orm/models.py:334``, ``:7046``, ``:7049``).
Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
helpdesk-support-ticket-basemodel.md``.

*Métrica:* la clase, el recordset que da ``env[...]`` y un alta y una
búsqueda por el ORM.
*Ciega a:* la conducta de los endpoints, que miden
``tests/integration/helpdesk/``.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.helpdesk.models import SupportTicket
from orm.environments import env, sudo
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


def test_the_ticket_is_a_basemodel():
    assert issubclass(SupportTicket, BaseModel)


def test_the_environment_gives_a_recordset():
    assert env()['support.ticket']._name == 'support.ticket'
    assert not env()['support.ticket'].browse()


def test_a_ticket_is_created_and_found_through_the_orm():
    user = get_user_model().objects.create_user(
        login='stb-user@kaupamex.mx', password='TestPass123!')
    with sudo():
        [ticket] = env()['support.ticket'].create([{
            'user': user.pk, 'subject': 'STB asunto', 'body': 'STB cuerpo'}])
        found = env()['support.ticket'].search(
            [('subject', '=', 'STB asunto')])
        assert found == ticket
        assert ticket.status == SupportTicket.Status.OPEN
