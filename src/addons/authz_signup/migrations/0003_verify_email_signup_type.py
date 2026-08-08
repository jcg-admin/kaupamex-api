"""Verificación de correo — tercer ``signup_type`` + su semilla.

Dos cosas en la misma migración porque son el mismo cambio: el tipo
``verify`` no sirve sin los parámetros que fijan su validez y la URL del SPA,
ni sin la plantilla del correo que lo transporta.

El ``AlterField`` sobre ``signup_type`` sólo amplía ``choices`` — en MariaDB
un ``Char`` con ``choices`` no lleva constraint de BD, así que el DDL es
no-destructivo y ninguna fila existente queda inválida.

Idempotente y ``noupdate`` como el XML de la referencia: nunca pisa un valor
que ya exista. Escribe sobre el modelo **histórico** vía ``apps.get_model``.
"""
from django.db import migrations

import fields

from addons.authz_signup.data import SIGNUP_PARAMETERS, SIGNUP_TEMPLATES

_NUEVOS_PARAMETROS = (
    'authz_signup.verify_validity_hours',
    'authz_signup.verify_email_url',
)
_NUEVA_PLANTILLA = 'authz_signup: verify email'


def sembrar(apps, schema_editor):
    """Crea las claves y la plantilla ausentes sobre el modelo histórico."""
    SystemParameter = apps.get_model('base', 'SystemParameter')
    MailTemplate = apps.get_model('mail', 'MailTemplate')
    alias = schema_editor.connection.alias

    for key in _NUEVOS_PARAMETROS:
        if not SystemParameter.objects.using(alias).filter(key=key).exists():
            SystemParameter.objects.using(alias).create(
                key=key, value=SIGNUP_PARAMETERS[key])

    spec = next(s for s in SIGNUP_TEMPLATES if s['name'] == _NUEVA_PLANTILLA)
    if not MailTemplate.objects.using(alias).filter(
            name=spec['name']).exists():
        MailTemplate.objects.using(alias).create(**spec)


class Migration(migrations.Migration):

    dependencies = [
        ("authz_signup", "0002_seed_signup_parameters"),
        ("mail", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="signuprequest",
            name="signup_type",
            field=fields.Char(
                choices=[
                    ("signup", "Alta invitada"),
                    ("reset", "Restablecer contraseña"),
                    ("verify", "Verificación de correo"),
                ],
                help_text='Odoo signup_type: "signup" (alta invitada) o '
                          '"reset" (restablecer contraseña). "verify" '
                          '(verificación de correo) es forma propia: no '
                          'existe en la referencia.',
                max_length=16,
                verbose_name="Tipo de signup",
            ),
        ),
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]
