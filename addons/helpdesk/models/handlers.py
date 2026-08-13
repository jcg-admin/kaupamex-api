"""Receptores de notificación que pertenecen a ``helpdesk`` (UC-NOT-08).

Reubicados desde ``mail/models/notification_signals.py`` (T-035): el receptor
del cierre de ticket vive con ``SupportTicket``, no dentro del addon de correo.
Ver la nota de dirección en ``addons/orders/handlers.py``.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from addons.helpdesk.models import SupportTicket
from addons.mail.models.notification_service import notify_support_closed

logger = logging.getLogger('apps')


@receiver(pre_save, sender=SupportTicket)
def _cache_ticket_old_status(sender, instance, **kwargs):
    """Captura status anterior para detectar transicion a CLOSED."""
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'status' not in update_fields:
        instance._old_status = getattr(instance, '_old_status', None)
        return
    if instance.pk:
        try:
            instance._old_status = SupportTicket.objects.get(pk=instance.pk).status
        except SupportTicket.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=SupportTicket)
def _support_ticket_closed(sender, instance, created, **kwargs):
    """Dispara UC-NOT-08 cuando el ticket transiciona a CLOSED."""
    if created:
        return
    old = getattr(instance, '_old_status', None)
    if old is None or old == instance.status:
        return
    if instance.status != SupportTicket.Status.CLOSED:
        return
    # closed_by_staff: la vista de cierre manual setea _closed_by_staff;
    # el management command no lo setea, se asume staff (auto-close).
    closed_by_staff = getattr(instance, '_closed_by_staff', True)
    try:
        notify_support_closed(instance, instance.user, closed_by_staff=closed_by_staff)
    except Exception:
        logger.warning(
            '_support_ticket_closed: notificacion fallida para SupportTicket %s',
            instance.pk, exc_info=True,
        )
