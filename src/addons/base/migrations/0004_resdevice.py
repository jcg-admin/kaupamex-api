"""``res.device`` — la vista SQL que proyecta la última actividad por dispositivo.

Porta el ``init()`` de la referencia (``odoo19c:
odoo/addons/base/models/res_device.py:250-256``), que crea la vista con
``CREATE or REPLACE VIEW`` a partir de ``_select``/``_from``/``_where``
(``:198-243``). El modelo Django es ``managed = False``: Django registra su
estado pero **no** emite DDL para él —comportamiento propio del autodetector,
que omite toda operación que modifique la base en modelos no gestionados—, así
que la vista la crea este ``RunSQL``. Por lo mismo el ``CreateModel`` va sin
campos: son estado, no esquema.

El SQL es hoy **idéntico al de la referencia**: no queda ninguna adaptación de
dialecto que mantener.

Histórico, porque explica por qué este archivo tuvo dos formas: bajo MariaDB,
``IS NOT DISTINCT FROM`` no era una preferencia de estilo sino un **error de
sintaxis** (``ERROR 1064 … near 'DISTINCT FROM NULL'``), y se escribía con su
equivalente nativo ``<=>`` — mismo comportamiento NULL-safe, medido entonces:
``1 <=> 1`` → 1 · ``NULL <=> NULL`` → 1 · ``1 <=> NULL`` → 0. Al migrar el
motor (iniciativa ``migrar-motor-mariadb-a-postgresql``) la traducción se
**revirtió**, que era justamente lo previsto: la adaptación de dialecto es
reversible, no una reescritura.

Lo que la comparación NULL-safe protege sigue igual de vivo: sin ella, una fila
con ``platform`` nulo nunca se compararía consigo misma, el ``NOT EXISTS`` no
encontraría a su sucesora, y la vista devolvería **todo** el log en vez de la
última actividad por dispositivo.
"""
from django.db import migrations, models

_SELECT = 'SELECT D.*'
_FROM = 'FROM res_device_log D'
# Verbatim de ``odoo19c: res_device.py:213-243``: sobrevive la fila **más
# reciente** de cada (usuario, sesión, plataforma, navegador) que no esté
# revocada. Tras migrar el motor a PostgreSQL ya no hay traducción que hacer —
# el ``<=>`` de MariaDB volvió a ``IS NOT DISTINCT FROM``, que es la forma de
# la referencia. Ver la nota del docstring del módulo.
_WHERE = """
WHERE
    NOT EXISTS (
        SELECT 1
        FROM res_device_log D2
        WHERE
            D2.user_id = D.user_id
            AND D2.session_identifier = D.session_identifier
            AND D2.platform IS NOT DISTINCT FROM D.platform
            AND D2.browser IS NOT DISTINCT FROM D.browser
            AND (
                D2.last_activity > D.last_activity
                OR (D2.last_activity = D.last_activity AND D2.id > D.id)
            )
            AND D2.revoked IS NOT TRUE
    )
    AND D.revoked IS NOT TRUE
"""

CREAR_VISTA = 'CREATE OR REPLACE VIEW res_device AS (%s %s %s)' % (
    _SELECT, _FROM, _WHERE)
BORRAR_VISTA = 'DROP VIEW IF EXISTS res_device'


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0003_res_columnas_nombre_referencia"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResDevice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dispositivo",
                "verbose_name_plural": "Dispositivos",
                "db_table": "res_device",
                "ordering": ["-last_activity"],
                "managed": False,
            },
        ),
        migrations.RunSQL(sql=CREAR_VISTA, reverse_sql=BORRAR_VISTA),
    ]
