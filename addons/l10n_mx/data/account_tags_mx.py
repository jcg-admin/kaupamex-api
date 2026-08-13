"""Las dos etiquetas de cuenta que el plan mexicano cita por identificador externo.

Adaptado de Odoo Community ``l10n_mx/data/account.account.tag.csv`` (LGPL-3,
``odoo-tools@622ddc2aa5``, ``odoo19c:``) — atribución preservada (DEC-KX-03).

No son adorno: **el CSV de CUENTAS del plan las cita por identificador
externo**. Medido con ``csv.DictReader`` sobre
``account: data/template/account.account-mx.csv`` (copia verbatim de
``odoo19c: l10n_mx/data/template/``, verificada con ``diff -q``): las **140**
filas del plan traen la columna ``tag_ids`` poblada — 102 citan
``l10n_mx.tag_debit_balance_account`` y 38
``l10n_mx.tag_credit_balance_account``.

Mismo mecanismo, mismo motivo, que ``account: data/account_tags.py`` con las
tres etiquetas maestras del plan genérico — este archivo es su análogo para el
bloque mexicano, siguiendo el mismo patrón: constantes + función
``seed_*(apps, alias)`` que escribe sobre modelos históricos.

*Métrica:* filas de ``account.account-mx.csv`` cuya columna ``tag_ids`` cita
uno de estos dos identificadores, contadas parseando el CSV — no con ``grep``,
que no distingue columnas.
*Ciega a:* si el registro apuntado existe en la base al cargar el plan; esto
mide la cita, no su resolución.

**El CSV de IMPUESTOS cita OTRAS etiquetas, y no las siembra nadie.** Su
columna ``repartition_line_ids/tag_ids`` está poblada en **45 de sus 138**
filas, y lo que cita son **8 nombres sueltos del reporte DIOT**
(``DIOT: Retención``, ``DIOT: 16% TAX``, ``DIOT: Exento``…) — ninguno de estos
dos identificadores. Esas ocho no tienen sembrador en este árbol y
``get_tag_mapper`` descarta en silencio el nombre que no resuelve, así que el
plan cargaría con sus 138 impuestos y **cero** enlaces de reparto. Registrado
como :ref:`h-api-358`; su sucesora es la tarea #184, atada a #136 (el motor de
fórmulas de ``account.report``, que es de donde la referencia las declara).

**Los nombres van verbatim en inglés**, como el resto del CSV del plan —
mismo criterio que ``account: data/account_tags.py``: son datos copiados de
la referencia, no cadenas de interfaz de este puerto.

DIVERGENCIA DECLARADA — ``country`` queda ``None``, no ``'MX'``
==================================================================

La referencia declara ``country_id/id: base.mx`` para ambas etiquetas
(``odoo19c: l10n_mx/data/account.account.tag.csv``). Bloqueado por algo
medido: este árbol **no siembra países** — ``grep -rn
"ResCountry.objects.create\\|ResCountry.objects.get_or_create" src/addons/*/
migrations/*.py src/addons/*/data/*.py | grep -v account_tags_mx.py`` →
**0 archivos** [PROVEN].

La exclusión final no es cosmética: sin ella el comando se encuentra a sí
mismo en esta línea y devuelve 1, así que la cifra de ausencia dejaría de ser
cierta **en el momento de publicarla**. Es la trampa que
``metrica-decide-la-conclusion.md`` nombra —una cifra de ausencia escrita
dentro del árbol que mide— y la detectó la fase de refutación de este mismo
porte, no una relectura del autor.

No existe
un ``ResCountry`` para México (ni para ningún otro país) al que apuntar; el
propio modelo ``base.ResCountry`` no tiene mecanismo de siembra en este
puerto.

Que ``country`` quede en ``None`` **no rompe** el uso real de estas
etiquetas: se citan por identificador externo con módulo
(``l10n_mx.tag_debit_balance_account``), y ``ChartTemplate.get_tag_mapper``
resuelve ese camino por ``ref()`` directo — nunca consulta el campo
``country`` cuando el nombre trae prefijo de módulo
(``account: models/chart_template.py``, rama
``if match and apps.is_installed(...)`` de ``mapping_getter``). El campo
sólo importa para el segundo camino de resolución (nombre suelto sin
módulo, comparado contra ``country=<el del plan>``), que estas dos
etiquetas no usan.

Condición de cierre: cuando exista una migración de siembra de países en
``base``, reasignar ``country`` al ``ResCountry`` de código ``MX`` en una
migración de datos aparte — no es tarea de este archivo.
"""

#: ``(xmlid sin módulo, nombre)`` — el orden es el del CSV de la referencia.
MX_ACCOUNT_TAGS = (
    ('tag_debit_balance_account', 'Debit Balance Account'),
    ('tag_credit_balance_account', 'Credit Balance Account'),
)

#: Los identificadores externos completos, que es como el CSV del plan las cita.
MX_ACCOUNT_TAG_XMLIDS = tuple(
    f'l10n_mx.{name}' for name, _label in MX_ACCOUNT_TAGS
)


def seed_l10n_mx_account_tags(apps, alias):
    """Crea (o respeta) las dos etiquetas y sus identificadores externos.

    Escribe sobre los modelos **históricos** (``apps.get_model``) porque
    corre dentro de una migración — mismo criterio que
    ``account.data.account_tags.seed_account_tags``: ejecutar comportamiento
    de la app viva desde una migración la ata a un estado del código que
    cambia bajo sus pies.

    Idempotente por ``(module, name)`` de ``ir.model.data``: un segundo pase
    repunta la fila en vez de duplicarla, y no pisa un nombre que el
    operador haya ajustado.
    """
    AccountAccountTag = apps.get_model('account', 'AccountAccountTag')
    IrModelData = apps.get_model('base', 'IrModelData')
    label = AccountAccountTag._meta.label

    created = {}
    for name, tag_label in MX_ACCOUNT_TAGS:
        xmlid = f'l10n_mx.{name}'
        row = IrModelData.objects.using(alias).filter(
            module='l10n_mx', name=name).first()
        existing = None
        if row is not None:
            existing = AccountAccountTag.objects.using(alias).filter(
                pk=row.res_id).first()
        if existing is None:
            existing = AccountAccountTag.objects.using(alias).filter(
                name=tag_label, applicability='accounts',
                country__isnull=True).first()
        if existing is None:
            existing = AccountAccountTag.objects.using(alias).create(
                name=tag_label, applicability='accounts')
        IrModelData.objects.using(alias).update_or_create(
            module='l10n_mx', name=name,
            defaults={'model': label, 'res_id': existing.pk, 'noupdate': True},
        )
        created[xmlid] = existing
    return created
