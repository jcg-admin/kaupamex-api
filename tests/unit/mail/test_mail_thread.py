"""TDD del backbone de chatter ``mail`` (familia mail, SOL-096).

Verifica el contrato del mixin ``mail.thread`` (``MailThread``) portado del
addon ``mail`` de Odoo, ejercitado a traves de su primer consumidor real
``support.SupportTicket`` (wiring de relacion, no un modelo de prueba
artificial): ``message_post`` crea ``mail.message`` polimorficos y
``message_subscribe`` crea ``mail.followers`` idempotentes.
"""
import datetime

import pytest

from addons.mail.models import (
    MailActivity,
    MailActivityType,
    MailFollowers,
    MailMessage,
    MailMessageSubtype,
    MailTrackingValue,
)
from addons.support.models import SupportTicket
from tests.factories.user_factory import UserFactory


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def ticket(db, user):
    return SupportTicket.objects.create(
        user=user, subject='Pedido no llego', body='Detalle del incidente',
    )


class TestMailThreadMessagePost:
    def test_message_post_creates_polymorphic_message(self, ticket, user):
        msg = ticket.message_post(body='<p>Hola</p>', author=user)
        assert isinstance(msg, MailMessage)
        # el par polimorfico apunta al ticket, igual que Odoo (model + res_id)
        assert msg.model == 'support.SupportTicket'
        assert msg.res_id == ticket.pk
        assert msg.body == '<p>Hola</p>'
        assert msg.author_id == user.pk
        # message_type default = comment (fiel a message_post de Odoo)
        assert msg.message_type == MailMessage.TYPE_COMMENT
        # record_name se rellena con str(ticket)
        assert str(ticket.pk) in msg.record_name

    def test_message_post_sets_date_when_absent(self, ticket):
        """Odoo mail_message.py:92 — default=fields.Datetime.now; aqui via save()."""
        msg = ticket.message_post(body='sin fecha explicita')
        assert msg.date is not None

    def test_message_ids_returns_thread(self, ticket):
        ticket.message_post(body='uno')
        ticket.message_post(body='dos')
        bodies = set(ticket.message_ids.values_list('body', flat=True))
        assert bodies == {'uno', 'dos'}
        assert ticket.message_ids.count() == 2

    def test_message_type_override(self, ticket):
        msg = ticket.message_post(
            body='correo', message_type=MailMessage.TYPE_EMAIL,
        )
        assert msg.message_type == MailMessage.TYPE_EMAIL

    def test_subtype_fk_optional_and_wired(self, ticket):
        st = MailMessageSubtype.objects.create(name='Discussions')
        msg = ticket.message_post(body='con subtipo', subtype=st)
        assert msg.subtype_id == st.pk

    def test_isolation_between_records(self, db, user):
        t1 = SupportTicket.objects.create(user=user, subject='a', body='a')
        t2 = SupportTicket.objects.create(user=user, subject='b', body='b')
        t1.message_post(body='de t1')
        assert t1.message_ids.count() == 1
        assert t2.message_ids.count() == 0


class TestMailThreadFollowers:
    def test_subscribe_creates_follower(self, ticket, user):
        followers = ticket.message_subscribe(user)
        assert len(followers) == 1
        assert isinstance(followers[0], MailFollowers)
        assert ticket.message_is_follower(user) is True
        assert ticket.message_follower_ids.count() == 1

    def test_subscribe_is_idempotent(self, ticket, user):
        ticket.message_subscribe(user)
        ticket.message_subscribe(user)  # segunda vez: unicidad evita duplicado
        assert ticket.message_follower_ids.count() == 1

    def test_subscribe_multiple_partners(self, ticket, user):
        other = UserFactory()
        ticket.message_subscribe([user, other])
        assert ticket.message_follower_ids.count() == 2

    def test_subscribe_with_subtypes(self, ticket, user):
        st = MailMessageSubtype.objects.create(name='Order Confirmed')
        followers = ticket.message_subscribe(user, subtypes=[st])
        assert followers[0].subtype_ids.filter(pk=st.pk).exists()

    def test_unsubscribe_removes_follower(self, ticket, user):
        ticket.message_subscribe(user)
        ticket.message_unsubscribe(user)
        assert ticket.message_is_follower(user) is False
        assert ticket.message_follower_ids.count() == 0

    def test_followers_scoped_to_record(self, db, user):
        t1 = SupportTicket.objects.create(user=user, subject='a', body='a')
        t2 = SupportTicket.objects.create(user=user, subject='b', body='b')
        t1.message_subscribe(user)
        assert t1.message_is_follower(user) is True
        assert t2.message_is_follower(user) is False


class TestMailThreadActivities:
    def test_activity_schedule_creates_polymorphic_activity(self, ticket, user):
        act = ticket.activity_schedule(summary='Llamar al cliente', user=user)
        assert isinstance(act, MailActivity)
        assert act.res_model == 'support.SupportTicket'
        assert act.res_id == ticket.pk
        assert act.user_id == user.pk
        assert act.date_deadline is not None  # default hoy

    def test_activity_ids_returns_open_activities(self, ticket, user):
        ticket.activity_schedule(summary='uno', user=user)
        ticket.activity_schedule(summary='dos', user=user)
        assert ticket.activity_ids.count() == 2

    def test_activity_type_wired(self, ticket, user):
        at = MailActivityType.objects.create(name='Llamada')
        act = ticket.activity_schedule(activity_type=at, user=user)
        assert act.activity_type_id == at.pk

    def test_activity_state_property(self, ticket, user):
        today = datetime.date.today()
        overdue = ticket.activity_schedule(
            user=user, date_deadline=today - datetime.timedelta(days=1))
        due = ticket.activity_schedule(user=user, date_deadline=today)
        planned = ticket.activity_schedule(
            user=user, date_deadline=today + datetime.timedelta(days=3))
        assert overdue.state == MailActivity.STATE_OVERDUE
        assert due.state == MailActivity.STATE_TODAY
        assert planned.state == MailActivity.STATE_PLANNED

    def test_action_done_posts_message_and_deletes(self, ticket, user):
        act = ticket.activity_schedule(summary='Revisar pedido', user=user)
        pk = act.pk
        msg = act.action_done(feedback='listo')
        # actividad eliminada; mensaje de tipo notification publicado en el hilo
        assert not MailActivity.objects.filter(pk=pk).exists()
        assert isinstance(msg, MailMessage)
        assert msg.model == 'support.SupportTicket'
        assert msg.res_id == ticket.pk
        assert msg.message_type == MailMessage.TYPE_NOTIFICATION
        assert 'listo' in msg.body

    def test_activities_scoped_to_record(self, db, user):
        t1 = SupportTicket.objects.create(user=user, subject='a', body='a')
        t2 = SupportTicket.objects.create(user=user, subject='b', body='b')
        t1.activity_schedule(summary='de t1', user=user)
        assert t1.activity_ids.count() == 1
        assert t2.activity_ids.count() == 0


class TestMailThreadTracking:
    def test_message_track_creates_notification_and_values(self, ticket, user):
        msg = ticket.message_track([
            {'field': 'status', 'field_desc': 'Estado', 'field_type': 'char',
             'old': 'OPEN', 'new': 'RESOLVED'},
            {'field': 'priority', 'field_desc': 'Prioridad', 'field_type': 'char',
             'old': 'NORMAL', 'new': 'HIGH'},
        ], author=user)
        assert isinstance(msg, MailMessage)
        assert msg.message_type == MailMessage.TYPE_NOTIFICATION
        assert msg.model == 'support.SupportTicket' and msg.res_id == ticket.pk
        # dos tracking values colgados del mensaje (relacion Odoo tracking_value_ids)
        tvs = msg.tracking_value_ids.all()
        assert tvs.count() == 2
        status_tv = tvs.get(field='status')
        assert status_tv.get_old_value() == 'OPEN'
        assert status_tv.get_new_value() == 'RESOLVED'

    def test_message_track_typed_value_columns(self, ticket, user):
        msg = ticket.message_track([
            {'field': 'amount', 'field_type': 'float', 'old': 10.0, 'new': 25.5},
            {'field': 'qty', 'field_type': 'integer', 'old': 1, 'new': 3},
        ])
        amount = msg.tracking_value_ids.get(field='amount')
        assert amount.old_value_float == 10.0 and amount.new_value_float == 25.5
        # el valor cae en la columna correcta segun field_type (Odoo _get_field_value_type)
        assert amount.old_value_char == ''
        qty = msg.tracking_value_ids.get(field='qty')
        assert qty.old_value_integer == 1 and qty.new_value_integer == 3

    def test_message_track_empty_is_noop(self, ticket):
        assert ticket.message_track([]) is None
        assert ticket.message_ids.count() == 0

    def test_tracking_deleted_with_message(self, ticket, user):
        msg = ticket.message_track([
            {'field': 'status', 'old': 'OPEN', 'new': 'CLOSED'}], author=user)
        tv_pk = msg.tracking_value_ids.first().pk
        msg.delete()  # CASCADE (Odoo ondelete='cascade')
        assert not MailTrackingValue.objects.filter(pk=tv_pk).exists()
