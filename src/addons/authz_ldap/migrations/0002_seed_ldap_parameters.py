"""Siembra el config-param L2 de LDAP (≙ ``ir.config_parameter`` de la
referencia: ``auth_ldap.disable_chase_ref``, leído con default ``'True'`` en
``res_company_ldap.py:109``).

El spec vive en ``addons.authz_ldap.data`` — fuente única para esta migración
y para la re-aplicación sobre el modelo vivo (``seed()``, H-API-22).
"""
from django.db import migrations

from addons.authz_ldap.data import LDAP_PARAMETERS


def seed_ldap_parameters(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    for key, value in LDAP_PARAMETERS.items():
        if not SystemParameter.objects.using(db).filter(key=key).exists():
            SystemParameter.objects.using(db).create(key=key, value=value)


def unseed_ldap_parameters(apps, schema_editor):
    SystemParameter = apps.get_model('base', 'SystemParameter')
    db = schema_editor.connection.alias
    SystemParameter.objects.using(db).filter(
        key__in=list(LDAP_PARAMETERS)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('authz_ldap', '0001_initial'),
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_ldap_parameters, unseed_ldap_parameters),
    ]
