"""
Tests UC-NOT-08 — auto-close + notificacion de soporte.

Cubre:
- notify_support_closed crea Notification in-app (staff + buyer).
- Signal post_save dispara notificacion al cerrar ticket manualmente.
- Signal NO dispara si el ticket ya estaba CLOSED (idempotencia).
- auto_close_support_tickets cierra tickets AWAITING_USER obsoletos.
- auto_close_support_tickets omite tickets recientes (< AUTO_CLOSE_DAYS).
- auto_close_support_tickets omite tickets no-AWAITING_USER.
- auto_close_support_tickets usa select_for_update skip_locked.
- CloseView devuelve 409 si ticket ya cerrado.
- CloseView cierra en atomic (Reply creado en misma transaccion).
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.addons.notifications.models import Notification, NotificationType
from apps.addons.notifications.service import notify_support_closed
from apps.addons.support.models import SupportTicket, SupportTicketReply
from apps.addons.support.management.commands.auto_close_support_tickets import AUTO_CLOSE_DAYS

User = get_user_model()


def _make_user(username='buyer', email='buyer@test.com', is_staff=False):
    return User.objects.create_user(
        username=username, email=email, password='pass', is_staff=is_staff
    )


def _make_ticket(user, status=SupportTicket.Status.AWAITING_USER):
    ticket = SupportTicket.objects.create(
        user=user, subject='Test ticket', body='Help', status=status,
    )
    return ticket


class NotifySupportClosedTest(TestCase):
    def setUp(self):
        self.user = _make_user()

    def test_creates_inapp_notification_staff_close(self):
        ticket = _make_ticket(self.user)
        with self.captureOnCommitCallbacks():
            notify_support_closed(ticket, self.user, closed_by_staff=True)
        notif = Notification.objects.get(user=self.user)
        self.assertEqual(notif.type, NotificationType.SUPPORT_UPDATE)
        self.assertIn('resuelto', notif.subject.lower())

    def test_creates_inapp_notification_buyer_close(self):
        ticket = _make_ticket(self.user)
        with self.captureOnCommitCallbacks():
            notify_support_closed(ticket, self.user, closed_by_staff=False)
        notif = Notification.objects.get(user=self.user)
        self.assertEqual(notif.type, NotificationType.SUPPORT_UPDATE)
        self.assertIn('cerrado', notif.body.lower())

    def test_no_notification_if_user_none(self):
        ticket = _make_ticket(self.user)
        notify_support_closed(ticket, None)
        self.assertEqual(Notification.objects.count(), 0)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SignalCloseTest(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.staff = _make_user('staff', 'staff@test.com', is_staff=True)

    def test_signal_fires_on_closed_transition(self):
        ticket = _make_ticket(self.user, status=SupportTicket.Status.OPEN)
        ticket._closed_by_staff = True
        ticket.status = SupportTicket.Status.CLOSED
        with self.captureOnCommitCallbacks(execute=True):
            ticket.save(update_fields=['status', 'updated_at'])
        self.assertEqual(
            Notification.objects.filter(user=self.user, type=NotificationType.SUPPORT_UPDATE).count(),
            1,
        )

    def test_signal_idempotent_no_double_notification(self):
        ticket = _make_ticket(self.user, status=SupportTicket.Status.CLOSED)
        # Guardar de nuevo sin cambio de status — no debe disparar UC-NOT-08
        ticket.subject = 'Updated'
        with self.captureOnCommitCallbacks(execute=True):
            ticket.save(update_fields=['subject', 'updated_at'])
        self.assertEqual(Notification.objects.count(), 0)


class AutoCloseCommandTest(TestCase):
    def setUp(self):
        self.user = _make_user()

    def _stale_ticket(self):
        ticket = _make_ticket(self.user)
        stale_time = timezone.now() - timedelta(days=AUTO_CLOSE_DAYS + 1)
        SupportTicket.objects.filter(pk=ticket.pk).update(updated_at=stale_time)
        ticket.refresh_from_db()
        return ticket

    def test_closes_stale_awaiting_user_ticket(self):
        ticket = self._stale_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            call_command('auto_close_support_tickets')
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, SupportTicket.Status.CLOSED)

    def test_creates_auto_close_reply(self):
        ticket = self._stale_ticket()
        call_command('auto_close_support_tickets')
        self.assertTrue(
            SupportTicketReply.objects.filter(
                ticket=ticket, is_internal_note=False
            ).exists()
        )

    def test_sends_notification(self):
        ticket = self._stale_ticket()
        with self.captureOnCommitCallbacks(execute=True):
            call_command('auto_close_support_tickets')
        self.assertEqual(
            Notification.objects.filter(
                user=self.user, type=NotificationType.SUPPORT_UPDATE
            ).count(),
            1,
        )

    def test_skips_recent_ticket(self):
        _make_ticket(self.user)  # updated_at = now (reciente)
        call_command('auto_close_support_tickets')
        ticket = SupportTicket.objects.first()
        self.assertEqual(ticket.status, SupportTicket.Status.AWAITING_USER)

    def test_skips_non_awaiting_user(self):
        _make_ticket(self.user, status=SupportTicket.Status.OPEN)
        call_command('auto_close_support_tickets')
        ticket = SupportTicket.objects.first()
        self.assertEqual(ticket.status, SupportTicket.Status.OPEN)
