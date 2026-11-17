"""``message_post_with_source`` sin QWeb (TASK-API-0121).

≙ ``odoo19c: addons/mail/models/mail_thread.py:2621-2711,3097-3150,
3197-3214``. Diseño: ``scripts/workbench/orm-continuation-plan-
20261103T095630/designs/message-post-with-source.md``.
"""
import importlib

import pytest
from django.apps import apps
from django.db import connection

from addons.base.models.ir_model import IrModelData
from addons.helpdesk.models import SupportTicket
from addons.mail.models import MailMessage, MailTemplate
from addons.mail.models.mail_thread import SOURCE_BODIES, register_source_body
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.unit, pytest.mark.django_db]
VIEW = 'test_mail_source.ticket_note_view'


@pytest.fixture
def ticket(db):
    return SupportTicket.objects.create(
        user=UserFactory(), subject='Pedido', body='Detalle')


@pytest.fixture
def view_body():
    @register_source_body(VIEW)
    def _body(record, values):
        return f'<p>{record.subject}: {values["status"]}</p>'
    yield _body
    SOURCE_BODIES.pop(VIEW, None)


def _subtype(xmlid):
    subtype_id = IrModelData._xmlid_to_res_id(xmlid)
    # Sin este control, dos ``None`` se compararían iguales y el subtipo por
    # defecto pasaría sin medirse.
    assert subtype_id, xmlid
    return subtype_id


def test_a_view_source_posts_the_registered_body(ticket, view_body):
    [message] = ticket.message_post_with_source(
        VIEW, render_values={'status': 'cerrado'})
    assert message.body == '<p>Pedido: cerrado</p>'
    assert message.message_type == MailMessage.TYPE_NOTIFICATION
    assert message.res_id == ticket.pk


def test_the_default_subtype_is_the_note(ticket, view_body):
    [message] = ticket.message_post_with_source(
        VIEW, render_values={'status': 'x'})
    assert message.subtype_id == _subtype('mail.mt_note')


def test_the_subtype_xmlid_wins(ticket, view_body):
    [message] = ticket.message_post_with_source(
        VIEW, render_values={'status': 'x'}, subtype_xmlid='mail.mt_comment')
    assert message.subtype_id == _subtype('mail.mt_comment')


def test_an_unknown_xmlid_without_a_body_is_refused(ticket):
    with pytest.raises(ValueError):
        ticket.message_post_with_source('test_mail_source.nowhere')


def test_a_record_of_another_model_is_refused(ticket):
    with pytest.raises(ValueError):
        ticket.message_post_with_source(ticket)


def test_a_source_of_an_invalid_type_is_refused(ticket):
    with pytest.raises(ValueError):
        ticket.message_post_with_source(42)


@pytest.mark.parametrize('name', ['body', 'model', 'res_id', 'values'])
def test_forbidden_parameters_are_refused(ticket, view_body, name):
    with pytest.raises(ValueError):
        ticket.message_post_with_source(VIEW, **{name: 'x'})


def test_a_template_source_posts_its_rendered_body(ticket):
    template = MailTemplate.objects.create(
        name='Nota', model='support.ticket', subject='#{{ object.pk }}',
        body_html='<p>{{ object.subject }}</p>')
    [message] = ticket.message_post_with_source(template)
    assert message.body == '<p>Pedido</p>'
    assert message.subject == f'#{ticket.pk}'


def test_migration_0010_registers_the_subtype_xmlids():
    """Escenario B: un subtipo sembrado por la 0002 sin xmlid recibe su fila
    de ``ir.model.data`` y la operación no duplica las existentes."""
    IrModelData.objects.filter(
        module='mail', name__in=['mt_note', 'mt_comment']).delete()
    assert IrModelData._xmlid_to_res_id('mail.mt_note') is None
    module = importlib.import_module(
        'addons.mail.migrations.0010_register_subtype_xmlids')
    with connection.schema_editor() as editor:
        module.register(apps, editor)
        module.register(apps, editor)
    assert IrModelData._xmlid_to_res_id('mail.mt_note')
    assert IrModelData.objects.filter(
        module='mail', name='mt_note').count() == 1
