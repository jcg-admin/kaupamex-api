"""TDD del addon ``mass_mailing`` — hogar Odoo fiel de la newsletter (en
disolucion). Verifica el contrato de los modelos portados: list/contact/
subscription (opt-out por lista) / mailing (hereda mail.thread) / trace."""
import pytest
from django.db import IntegrityError, transaction

from addons.mail.models import MailMessage, MailThread
from addons.mass_mailing.models import (
    MailingContact,
    MailingList,
    MailingMailing,
    MailingSubscription,
    MailingTrace,
)


class TestMailingListAndContacts:
    def test_subscription_links_contact_and_list(self, db):
        lst = MailingList.objects.create(name='Ofertas')
        contact = MailingContact.objects.create(email='a@x.com', name='Ana')
        sub = MailingSubscription.objects.create(contact=contact, mailing_list=lst)
        assert sub.opt_out is False
        # reversos por related_name
        assert lst.subscription_ids.filter(pk=sub.pk).exists()
        assert contact.subscription_ids.filter(pk=sub.pk).exists()

    def test_subscription_unique_per_list(self, db):
        lst = MailingList.objects.create(name='L')
        c = MailingContact.objects.create(email='a@x.com')
        MailingSubscription.objects.create(contact=c, mailing_list=lst)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                MailingSubscription.objects.create(contact=c, mailing_list=lst)

    def test_optout_is_per_list_not_global(self, db):
        c = MailingContact.objects.create(email='a@x.com')
        l1 = MailingList.objects.create(name='L1')
        l2 = MailingList.objects.create(name='L2')
        s1 = MailingSubscription.objects.create(contact=c, mailing_list=l1, opt_out=True)
        s2 = MailingSubscription.objects.create(contact=c, mailing_list=l2)
        # el contacto salio de L1 pero sigue en L2 (fiel a Odoo)
        assert s1.opt_out is True and s2.opt_out is False


class TestMailingIsThread:
    def test_mailing_inherits_mailthread(self, db):
        assert issubclass(MailingMailing, MailThread)
        m = MailingMailing.objects.create(subject='Promo', body_html='<p>hi</p>')
        # gana chatter (mail.thread) sin columnas propias
        msg = m.message_post(body='campana creada')
        assert isinstance(msg, MailMessage)
        assert msg.model == 'mass_mailing.MailingMailing'
        assert msg.res_id == m.pk

    def test_mailing_state_default_draft(self, db):
        m = MailingMailing.objects.create(subject='X')
        assert m.state == MailingMailing.STATE_DRAFT


class TestMailingTrace:
    def test_trace_per_contact_cross_linked(self, db):
        m = MailingMailing.objects.create(subject='X')
        c = MailingContact.objects.create(email='a@x.com')
        t = MailingTrace.objects.create(mailing=m, contact=c, email=c.email)
        assert t.trace_status == MailingTrace.STATUS_OUTGOING
        assert m.trace_ids.filter(pk=t.pk).exists()
        assert c.trace_ids.filter(pk=t.pk).exists()

    def test_trace_unique_per_contact(self, db):
        m = MailingMailing.objects.create(subject='X')
        c = MailingContact.objects.create(email='a@x.com')
        MailingTrace.objects.create(mailing=m, contact=c)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                MailingTrace.objects.create(mailing=m, contact=c)

    def test_trace_email_snapshot_survives_contact_delete(self, db):
        m = MailingMailing.objects.create(subject='X')
        c = MailingContact.objects.create(email='a@x.com')
        t = MailingTrace.objects.create(mailing=m, contact=c, email='a@x.com')
        c.delete()  # MailingContact no es soft-delete → hard delete, FK SET_NULL
        t.refresh_from_db()
        assert t.contact_id is None
        assert t.email == 'a@x.com'
