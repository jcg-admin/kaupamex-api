"""TDD del backbone de chatter ``mail`` (familia mail, SOL-096).

Verifica el contrato del mixin ``mail.thread`` (``MailThread``) portado del
addon ``mail`` de Odoo, ejercitado a traves de su primer consumidor real
``support.SupportTicket`` (wiring de relacion, no un modelo de prueba
artificial): ``message_post`` crea ``mail.message`` polimorficos y
``message_subscribe`` crea ``mail.followers`` idempotentes.
"""
import pytest

from addons.mail.models import MailFollowers, MailMessage, MailMessageSubtype
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
