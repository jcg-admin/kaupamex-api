"""Renombra los dos relacionales de ``ir.actions.report`` a la forma C.

ADR-029 fija la **forma C** para un campo relacional portado: el símbolo
verbatim de la fuente **y** la columna verbatim. Este modelo tenía los dos en
forma A —símbolo divergente, columna fiel—: ``groups`` donde
``odoo19c: ir_actions_report.py:182`` declara ``group_ids``, y ``paperformat``
donde ``:185`` declara ``paperformat_id``.

**Son dos de las 655 que el barrido de la tarea #143 tiene por delante, no su
cierre.** Se pagan aquí porque el pase toca este archivo, que es el criterio
prospectivo del gate ``api: scripts/check_fk_naming.py``: una declaración
listada en su baseline no bloquea, y se corrige al tocar su archivo. Lo que
queda, agrupado por addon, lo publica
``docs: .claude/eventos/barrido-fk-forma-c-20260828T184007/pendientes_forma_c.py``
— tras este commit, **654 en 61 raíces**.

**La base no cambia**, y por eso la migración es de estado y no de esquema:

- ``paperformat`` producía la columna ``paperformat_id`` (Django sufija el
  ``_id`` de una FK); ``paperformat_id`` la declara con ``db_column`` y sale
  idéntica.
- ``groups`` guardaba la relación en ``res_groups_report_rel``, nombrada a
  mano en el propio campo; ``group_ids`` lleva el mismo ``db_table``.

Tres formas se midieron con ``sqlmigrate`` antes de elegir ésta:

1. Lo que el detector automático propone —``RemoveField`` + ``AddField``—
   **borra las filas** y toda pertenencia a grupo. Descartada.
2. ``RenameField`` a secas emite
   ``RENAME COLUMN "paperformat_id" TO "paperformat_id_id"``: el estado de la
   migración deriva la columna del nombre del campo y todavía no conoce el
   ``db_column``. Es el defecto que :ref:`h-api-275` registró — diez columnas
   ``*_id_id``. Descartada.
3. ``RenameField`` + ``AlterField`` corrige el nombre, pero por un viaje de
   ida y vuelta: renombra a ``paperformat_id_id`` y de vuelta, y de paso
   destruye y recrea la restricción de clave foránea con otro nombre. Correcta
   en el resultado y ruidosa en el trayecto. Descartada.

Queda ``SeparateDatabaseAndState`` con ``database_operations`` vacío: dice lo
que de verdad pasa —cambian los símbolos, no la base— y ``sqlmigrate`` lo
confirma sin una sola línea de DDL.

Los dos campos se nombran por cadena —``'base.resgroups'``,
``'base.reportpaperformat'``— y no por su clase: el estado de una migración
rechaza una referencia a la clase (*"Model fields in ModelState.fields cannot
refer to a model class"*), porque tiene que poder reconstruirse sin importar
el modelo real.

Los dos ``AlterField`` del final no mueven nada tampoco: recogen el
``db_column`` de la FK y el texto de ayuda de ambos campos, que perdieron la
mención al nombre de la fuente cuando el símbolo pasó a ser ese nombre. Sin
ellos, ``makemigrations --check`` seguiría proponiendo una migración.
"""
import django.db.models.deletion
from django.db import migrations

import fields


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0068_respartner_sale_warn_msg'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameField(
                    model_name='iractionsreport',
                    old_name='groups',
                    new_name='group_ids',
                ),
                migrations.RenameField(
                    model_name='iractionsreport',
                    old_name='paperformat',
                    new_name='paperformat_id',
                ),
                migrations.AlterField(
                    model_name='iractionsreport',
                    name='group_ids',
                    field=fields.Many2many(
                        'base.resgroups', blank=True,
                        db_table='res_groups_report_rel',
                        related_name='report_ids', verbose_name='Grupos',
                        help_text='Vacío = sin restricción por grupo. La '
                                  'autorización efectiva sigue siendo por '
                                  'capacidad (DEC-11).',
                    ),
                ),
                migrations.AlterField(
                    model_name='iractionsreport',
                    name='paperformat_id',
                    field=fields.Many2one(
                        'base.reportpaperformat',
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True, blank=True, db_index=True,
                        db_column='paperformat_id', related_name='report_ids',
                        verbose_name='Formato de papel',
                        help_text='Este related_name es el One2many que '
                                  'report_paperformat.py dejó anotado como '
                                  'pendiente.',
                    ),
                ),
            ],
        ),
    ]
