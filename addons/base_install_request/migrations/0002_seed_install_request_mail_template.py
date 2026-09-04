"""Siembra la plantilla de correo de la solicitud, con su identificador externo.

≙ ``odoo19c: base_install_request/data/mail_template_data.xml``, que declara el
``<record model="mail.template">`` dentro de ``<data noupdate="1">``. Las dos
mitades del XML se escriben aquí:

- la fila de ``mail.template`` con sus campos (``addons/base_install_request/data.py``);
- la fila de ``ir.model.data`` que le da el ``id`` del ``<record>``, para que
  ``action_send_request`` la resuelva con ``IrModelData.ref`` igual que la
  fuente la resuelve con ``env.ref``.

Idempotente y ``noupdate`` como el XML: nunca pisa lo que ya exista. Escribe
sobre los modelos **históricos** vía ``apps.get_model``, que es el idioma de
``addons/authz_signup/migrations/0003_verify_email_signup_type.py``.
"""
from django.db import migrations

from addons.base_install_request.data import (
    INSTALL_REQUEST_TEMPLATE, INSTALL_REQUEST_TEMPLATE_MODEL_LABEL,
    INSTALL_REQUEST_TEMPLATE_MODULE, INSTALL_REQUEST_TEMPLATE_XMLID)


def sembrar(apps, schema_editor):
    """Crea la plantilla y su identificador externo si faltan."""
    MailTemplate = apps.get_model('mail', 'MailTemplate')
    IrModelData = apps.get_model('base', 'IrModelData')
    alias = schema_editor.connection.alias

    plantilla = MailTemplate.objects.using(alias).filter(
        name=INSTALL_REQUEST_TEMPLATE['name']).first()
    if plantilla is None:
        plantilla = MailTemplate.objects.using(alias).create(
            **INSTALL_REQUEST_TEMPLATE)

    if not IrModelData.objects.using(alias).filter(
            module=INSTALL_REQUEST_TEMPLATE_MODULE,
            name=INSTALL_REQUEST_TEMPLATE_XMLID).exists():
        IrModelData.objects.using(alias).create(
            module=INSTALL_REQUEST_TEMPLATE_MODULE,
            name=INSTALL_REQUEST_TEMPLATE_XMLID,
            model=INSTALL_REQUEST_TEMPLATE_MODEL_LABEL,
            res_id=plantilla.pk,
            noupdate=True,
        )


def desembrar(apps, schema_editor):
    """Retira el identificador externo y la plantilla que esta migración creó."""
    MailTemplate = apps.get_model('mail', 'MailTemplate')
    IrModelData = apps.get_model('base', 'IrModelData')
    alias = schema_editor.connection.alias
    IrModelData.objects.using(alias).filter(
        module=INSTALL_REQUEST_TEMPLATE_MODULE,
        name=INSTALL_REQUEST_TEMPLATE_XMLID).delete()
    MailTemplate.objects.using(alias).filter(
        name=INSTALL_REQUEST_TEMPLATE['name']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base_install_request', '0001_initial'),
        ('mail', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(sembrar, desembrar),
    ]
