"""Las tres etiquetas maestras del estado de flujo de efectivo.

≙ ``odoo19c: account/data/account_data.xml:18-33`` (``odoo-tools@622ddc2a``),
bajo el comentario ``TAGS FOR CASH FLOW STATEMENT DIRECT METHOD``.

No son adorno ni datos de demo: **el plan genérico las cita por identificador
externo**. Medido sobre ``data/template/account.account-generic_coa.csv``:
13 de sus 46 filas traen la columna ``tag_ids`` con uno de estos tres
identificadores, y ``_get_accounts_data_values`` etiqueta con
``account_tag_investing`` las dos cuentas de diferencia de efectivo
(``odoo19c: chart_template.py:873,880``).

*Métrica:* filas del CSV del plan genérico cuya columna ``tag_ids`` no está
vacía.
*Ciega a:* los CSV de otras localizaciones — este puerto sólo trae
``generic_coa``.

**Los nombres van verbatim en inglés**, como el resto del CSV del plan: son
datos copiados de la referencia, no cadenas de interfaz de este puerto. Lo que
sí se traduce son los nombres que el código construye con ``_()``, p. ej. las
seis cuentas de utilidad de ``get_accounts_data_values``.
"""

#: ``(xmlid sin módulo, nombre, aplicabilidad)`` — el orden es el del XML.
MASTER_ACCOUNT_TAGS = (
    ('account_tag_operating', 'Operating Activities', 'accounts'),
    ('account_tag_financing', 'Financing Activities', 'accounts'),
    ('account_tag_investing', 'Investing & Extraordinary Activities', 'accounts'),
)

#: Los identificadores externos completos, que es como los cita el plan.
MASTER_ACCOUNT_TAG_XMLIDS = tuple(
    f'account.{name}' for name, _label, _applicability in MASTER_ACCOUNT_TAGS
)


def seed_account_tags(apps, alias):
    """Crea (o respeta) las tres etiquetas y sus identificadores externos.

    Escribe sobre los modelos **históricos** (``apps.get_model``) porque corre
    dentro de una migración: ejecutar comportamiento de la app viva desde una
    migración la ata a un estado del código que cambia bajo sus pies.

    Idempotente por ``(module, name)`` de ``ir.model.data``, que es lo que
    ``noupdate="1"`` garantiza en el XML original: un segundo pase repunta la
    fila en vez de duplicarla, y no pisa un nombre que el operador haya
    ajustado.
    """
    AccountAccountTag = apps.get_model('account', 'AccountAccountTag')
    IrModelData = apps.get_model('base', 'IrModelData')
    label = AccountAccountTag._meta.label

    created = {}
    for name, tag_label, applicability in MASTER_ACCOUNT_TAGS:
        xmlid = f'account.{name}'
        row = IrModelData.objects.using(alias).filter(
            module='account', name=name).first()
        existing = None
        if row is not None:
            existing = AccountAccountTag.objects.using(alias).filter(
                pk=row.res_id).first()
        if existing is None:
            existing = AccountAccountTag.objects.using(alias).filter(
                name=tag_label, applicability=applicability,
                country__isnull=True).first()
        if existing is None:
            existing = AccountAccountTag.objects.using(alias).create(
                name=tag_label, applicability=applicability)
        IrModelData.objects.using(alias).update_or_create(
            module='account', name=name,
            defaults={'model': label, 'res_id': existing.pk, 'noupdate': True},
        )
        created[xmlid] = existing
    return created
