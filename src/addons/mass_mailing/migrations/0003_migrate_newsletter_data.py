"""Migracion de datos: ``newsletter`` → ``mass_mailing`` (paso 2b de disolucion).

Copia los datos del addon de proyecto ``newsletter`` (en disolucion) a su hogar
Odoo ``mass_mailing``, **sin perdida**:

- ``NewsletterSubscriber`` → ``MailingContact`` + una ``MailingSubscription`` a
  la lista canonica "Newsletter". El estado PENDING/CONFIRMED/UNSUBSCRIBED se
  mapea a la maquina de estados por-lista (``confirmed_at``/``opt_out``), y se
  **preservan los tokens** (``confirmation_token``/``unsubscribe_token``) para
  que los enlaces de baja ya enviados sigan funcionando.
- ``NewsletterCampaign`` → ``MailingMailing`` (subject/body/sender/sent_date).

Idempotente por email (``get_or_create`` del contacto) y por subject+fecha de la
campana. Reversible parcialmente (borra lo copiado a la lista "Newsletter"). En
la BD de test (``--reuse-db``) las tablas ``newsletter`` estan vacias → no copia
nada; en prod copia los datos reales antes de retirar el addon (paso 3).
"""
from django.db import migrations

NEWSLETTER_LIST_NAME = 'Newsletter'


def forwards(apps, schema_editor):
    # El addon ``newsletter`` fue retirado (paso 3): en instalaciones nuevas ya
    # no existe → esta copia es un no-op. En la BD que aún tenía sus tablas, la
    # copia ya corrió antes del retiro. Guardamos el LookupError para que la
    # migración siga siendo aplicable sin el addon fuente.
    try:
        Subscriber = apps.get_model('newsletter', 'NewsletterSubscriber')
        Campaign = apps.get_model('newsletter', 'NewsletterCampaign')
    except LookupError:
        return
    MailingList = apps.get_model('mass_mailing', 'MailingList')
    MailingContact = apps.get_model('mass_mailing', 'MailingContact')
    MailingSubscription = apps.get_model('mass_mailing', 'MailingSubscription')
    MailingMailing = apps.get_model('mass_mailing', 'MailingMailing')

    news_list, _ = MailingList.objects.get_or_create(
        name=NEWSLETTER_LIST_NAME, defaults={'is_public': True},
    )

    for sub in Subscriber.objects.all():
        contact, _ = MailingContact.objects.get_or_create(
            email=sub.email, defaults={'name': ''},
        )
        status = sub.status
        # CONFIRMED sin timestamp (dato heredado) → usar created_at como fallback
        # para no perder el estado confirmado.
        confirmed_at = (
            (sub.confirmed_at or sub.created_at) if status == 'CONFIRMED' else None
        )
        opt_out = status == 'UNSUBSCRIBED'
        MailingSubscription.objects.get_or_create(
            contact=contact, mailing_list=news_list,
            defaults={
                'opt_out': opt_out,
                'opt_out_datetime': sub.unsubscribed_at if opt_out else None,
                'confirmed_at': confirmed_at,
                'confirmation_token': sub.confirmation_token,
                'unsubscribe_token': sub.unsubscribe_token,
            },
        )

    for camp in Campaign.objects.all():
        MailingMailing.objects.get_or_create(
            subject=camp.subject,
            created_at=camp.created_at,
            defaults={
                'body_html': camp.body,
                'user_id': camp.sender_id,
                'sent_date': camp.sent_at,
                'state': 'done' if camp.sent_at else 'draft',
            },
        )


def backwards(apps, schema_editor):
    MailingList = apps.get_model('mass_mailing', 'MailingList')
    MailingSubscription = apps.get_model('mass_mailing', 'MailingSubscription')
    news = MailingList.objects.filter(name=NEWSLETTER_LIST_NAME).first()
    if news:
        MailingSubscription.objects.filter(mailing_list=news).delete()
        news.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mass_mailing', '0002_mailingsubscription_confirmation_token_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
