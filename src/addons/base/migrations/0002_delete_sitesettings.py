"""Retira la tabla monolítica de ajustes, salvando sus valores primero.

``SiteSettings`` declaraba trece campos de diez dominios distintos en un solo
esquema: cada cambio de política (IVA, plazo de pago, umbral de envío, datos
de contacto) exigía una migración que tocaba a todos los demás. La referencia
no almacena en el formulario — ``res.config.settings`` es un
``TransientModel`` en ``odoo19c:`` y ``odoo18c:`` — y reparte los valores
entre parámetros, la compañía y los grupos.

Esta migración hace las dos mitades en orden: **primero** copia lo que hubiera
configurado a su clave de dominio en ``SystemParameter``, **después** borra la
tabla. Al revés se perdería la configuración de cualquier instalación viva.

Ver H-API-265 para la medición (10 razones para cambiar; 12 archivos de 5
addons acoplados).
"""
import json

from django.db import migrations

#: Campo de la tabla retirada → clave del parámetro, con el prefijo del
#: dominio dueño. Es el mismo mapa que ``base_setup`` declara en
#: ``CONFIG_CASTERS``; se repite aquí verbatim porque una migración no debe
#: importar código de aplicación, que cambia bajo sus pies.
FIELD_TO_KEY = {
    'payment_timeout_minutes': 'payment.timeout_minutes',
    'order_timeout_minutes': 'sale.order_timeout_minutes',
    'site_name': 'website.site_name',
    'iva_rate': 'account.iva_rate',
    'max_return_days': 'stock.max_return_days',
    'min_stock_threshold': 'stock.min_stock_threshold',
    'free_shipping_threshold': 'delivery.free_shipping_threshold',
    'support_email': 'crm.support_email',
    'phone': 'crm.phone',
    'address': 'crm.address',
}


def salvar_valores(apps, schema_editor):
    """Copia la fila del singleton (si existe) a los parámetros por dominio."""
    SiteSettings = apps.get_model('base', 'SiteSettings')
    SystemParameter = apps.get_model('base', 'SystemParameter')
    alias = schema_editor.connection.alias

    fila = SiteSettings.objects.using(alias).order_by('pk').first()
    if fila is None:
        return

    for campo, clave in FIELD_TO_KEY.items():
        valor = getattr(fila, campo, None)
        if valor in (None, ''):
            continue
        SystemParameter.objects.using(alias).update_or_create(
            key=clave, defaults={'value': str(valor)},
        )

    social = getattr(fila, 'social_links', None)
    if social:
        SystemParameter.objects.using(alias).update_or_create(
            key='crm.social_links', defaults={'value': json.dumps(social)},
        )


def sin_vuelta_atras(apps, schema_editor):
    """La copia no se deshace: los parámetros son el almacén desde ahora.

    Revertir recrea la tabla vacía; los valores siguen en sus claves, que es
    donde el código los lee.
    """
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(salvar_valores, sin_vuelta_atras),
        migrations.DeleteModel(
            name="SiteSettings",
        ),
    ]
