"""``res.device`` — la vista SQL que proyecta la última actividad por dispositivo.

Porta el ``init()`` de la referencia (``odoo19c:
odoo/addons/base/models/res_device.py:250-256``), que crea la vista con
``CREATE or REPLACE VIEW`` a partir de ``_select``/``_from``/``_where``
(``:198-243``). El modelo Django es ``managed = False``: Django registra su
estado pero **no** emite DDL para él —comportamiento propio del autodetector,
que omite toda operación que modifique la base en modelos no gestionados—, así
que la vista la crea este ``RunSQL``. Por lo mismo el ``CreateModel`` va sin
campos: son estado, no esquema.

Dos adaptaciones de dialecto, verificadas contra MariaDB 11.8.8 antes de
escribirlas:

============================================  ===============================
``odoo19c`` (PostgreSQL)                      Aquí (MariaDB)
============================================  ===============================
``D2.platform IS NOT DISTINCT FROM D.platform``  ``D2.platform <=> D.platform``
``revoked IS NOT TRUE``                       idéntico (soportado)
============================================  ===============================

La forma estándar **no es opcional aquí, es un error de sintaxis**::

    MariaDB> SELECT NULL IS NOT DISTINCT FROM NULL;
    ERROR 1064 (42000): You have an error in your SQL syntax ...
             near 'DISTINCT FROM NULL' at line 1

``<=>`` es su equivalente nativo, no un rodeo. La ayuda del propio servidor
(``HELP '<=>'``) lo define así: *"NULL-safe equal operator. It performs an
equality comparison like the ``=`` operator, but returns 1 rather than NULL if
both operands are NULL, and 0 rather than NULL if one operand is NULL"* — que
es la semántica de ``IS NOT DISTINCT FROM`` palabra por palabra. Medido:
``1 <=> 1`` → 1 · ``NULL <=> NULL`` → 1 · ``1 <=> NULL`` → 0.

Sin él, una fila con ``platform`` nulo nunca se compararía consigo misma: el
``NOT EXISTS`` no encontraría a su sucesora y la vista devolvería **todo** el
log en vez de la última actividad por dispositivo.
"""
from django.db import migrations, models

_SELECT = 'SELECT D.*'
_FROM = 'FROM res_device_log D'
# Verbatim de ``odoo19c: res_device.py:213-243``, con ``<=>`` por
# ``IS NOT DISTINCT FROM``: sobrevive la fila **más reciente** de cada
# (usuario, sesión, plataforma, navegador) que no esté revocada.
_WHERE = """
WHERE
    NOT EXISTS (
        SELECT 1
        FROM res_device_log D2
        WHERE
            D2.user_id = D.user_id
            AND D2.session_identifier = D.session_identifier
            AND D2.platform <=> D.platform
            AND D2.browser <=> D.browser
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
