"""Servicio de compatibilidad ``newsletter`` → ``mass_mailing``.

Aloja la lógica de la newsletter pública de proyecto (UC-NEW-01..04) sobre los
modelos Odoo fieles de ``mass_mailing``, como parte de la **disolución** del
addon ``newsletter`` (en retiro). La suscripción pública a la newsletter es una
única lista canónica ``"Newsletter"`` (``mailing.list``); cada suscriptor es un
``MailingContact`` + una ``MailingSubscription`` en esa lista, con el doble
opt-in por lista que la ``MailingSubscription`` ya hospeda (DEC-NEW-02).

**Preservación del contrato:** el estado de negocio ``PENDING``/``CONFIRMED``/
``UNSUBSCRIBED`` (que la API v2 de newsletter expone) se **deriva** de la
máquina de estados por-lista (``confirmed_at``/``opt_out``), y los **salts de
token** siguen siendo los del addon ``newsletter`` (``newsletter-unsub`` /
``newsletter-confirm``) para que los enlaces ya enviados y los datos migrados
(paso 2b, ``0003_migrate_newsletter_data``) sigan funcionando sin cambios.
"""
import secrets

from django.core import signing
from django.utils import timezone

from .models import (
    MailingContact,
    MailingList,
    MailingMailing,
    MailingSubscription,
)

NEWSLETTER_LIST_NAME = 'Newsletter'
UNSUBSCRIBE_SALT = 'newsletter-unsub'

# Estados de negocio del suscriptor (ex-``newsletter.SubscriberStatus``),
# derivados de la máquina por-lista de la suscripción.
STATUS_PENDING = 'PENDING'
STATUS_CONFIRMED = 'CONFIRMED'
STATUS_UNSUBSCRIBED = 'UNSUBSCRIBED'


def newsletter_list():
    """Lista canónica ``"Newsletter"`` (creada perezosamente, idempotente)."""
    lst, _ = MailingList.objects.get_or_create(
        name=NEWSLETTER_LIST_NAME, defaults={'is_public': True},
    )
    return lst


def status_of(sub) -> str:
    """Deriva el estado de negocio de una ``MailingSubscription``.

    ``opt_out`` → UNSUBSCRIBED; confirmada y no dada de baja → CONFIRMED;
    resto (alta sin confirmar) → PENDING.
    """
    if sub.opt_out:
        return STATUS_UNSUBSCRIBED
    if sub.confirmed_at is not None:
        return STATUS_CONFIRMED
    return STATUS_PENDING


def serialize_item(sub) -> dict:
    """Item del contrato de la API de newsletter (UC-NEW-03).

    Mismas claves y semántica que el ``SubscriberListItemSerializer`` original:
    ``id`` = pk de la suscripción; ``unsubscribed_at`` = ``opt_out_datetime``.
    """
    return {
        'id': sub.pk,
        'email': sub.contact.email,
        'status': status_of(sub),
        'confirmed_at': sub.confirmed_at,
        'unsubscribed_at': sub.opt_out_datetime,
        'created_at': sub.created_at,
    }


def find_by_email(email):
    """Suscripción a la lista Newsletter por email del contacto, o ``None``."""
    return (
        MailingSubscription.objects
        .filter(mailing_list=newsletter_list(), contact__email=email)
        .select_related('contact')
        .first()
    )


def create_pending(email, confirmation_token):
    """Alta nueva PENDING: crea el contacto (si falta) y la suscripción.

    Genera el token de baja con el salt ``newsletter-unsub`` (compat con los
    enlaces ya enviados), no con el default de ``MailingSubscription``.
    """
    contact, _ = MailingContact.objects.get_or_create(
        email=email, defaults={'name': ''},
    )
    return MailingSubscription.objects.create(
        contact=contact,
        mailing_list=newsletter_list(),
        confirmation_token=confirmation_token,
        unsubscribe_token=signing.dumps(
            secrets.token_urlsafe(16), salt=UNSUBSCRIBE_SALT,
        ),
    )


def reopt_in(sub, confirmation_token):
    """Re-suscripción desde UNSUBSCRIBED: vuelve a PENDING."""
    sub.opt_out = False
    sub.opt_out_datetime = None
    sub.confirmed_at = None
    sub.confirmation_token = confirmation_token
    sub.save(update_fields=[
        'opt_out', 'opt_out_datetime', 'confirmed_at',
        'confirmation_token', 'updated_at',
    ])
    return sub


def confirm(sub):
    """Confirma el doble opt-in (delegado en el método del modelo)."""
    sub.confirm()
    return sub


def find_by_confirmation_token(email, token):
    """Suscripción PENDING por (email, confirmation_token), o ``None``."""
    return (
        MailingSubscription.objects
        .filter(
            mailing_list=newsletter_list(),
            contact__email=email,
            confirmation_token=token,
        )
        .select_related('contact')
        .first()
    )


def find_by_unsubscribe_token(token):
    """Suscripción por su token de baja único, o ``None``."""
    return (
        MailingSubscription.objects
        .filter(unsubscribe_token=token)
        .select_related('contact')
        .first()
    )


def unsubscribe(sub):
    """Baja de la lista (delegado en el método del modelo)."""
    sub.unsubscribe()
    return sub


def _status_filter(qs, status):
    """Traduce el estado de negocio a condiciones sobre la máquina por-lista."""
    if status == STATUS_UNSUBSCRIBED:
        return qs.filter(opt_out=True)
    if status == STATUS_CONFIRMED:
        return qs.filter(opt_out=False, confirmed_at__isnull=False)
    if status == STATUS_PENDING:
        return qs.filter(opt_out=False, confirmed_at__isnull=True)
    return qs


def list_subscriptions(status=None):
    """Suscripciones de la lista Newsletter (opcionalmente filtradas)."""
    qs = (
        MailingSubscription.objects
        .filter(mailing_list=newsletter_list())
        .select_related('contact')
        .order_by('-created_at', '-id')
    )
    if status:
        qs = _status_filter(qs, status)
    return qs


def recipients_for(status):
    """Emails de los suscriptores en el estado dado (destinatarios de campaña)."""
    return list(
        _status_filter(
            MailingSubscription.objects
            .filter(mailing_list=newsletter_list())
            .select_related('contact'),
            status,
        ).values_list('contact__email', flat=True)
    )


def find_recent_mailing(subject, body_html, cutoff):
    """Envío idéntico reciente (guarda de idempotencia), con lock de fila."""
    return (
        MailingMailing.objects
        .select_for_update()
        .filter(subject=subject, body_html=body_html, created_at__gte=cutoff)
        .first()
    )


def create_mailing(*, subject, body_html, user, recipients_count):
    """Crea el ``MailingMailing`` de la campaña (hogar del ``NewsletterCampaign``)."""
    return MailingMailing.objects.create(
        subject=subject,
        body_html=body_html,
        user=user,
        state=MailingMailing.STATE_DONE if recipients_count else MailingMailing.STATE_DRAFT,
        sent_date=timezone.now() if recipients_count else None,
    )
