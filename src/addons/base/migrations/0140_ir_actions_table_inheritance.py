"""Las tablas de los subtipos de acción heredan de ``ir_actions``.

≙ ``odoo19c: odoo/addons/base/data/base_data.sql:5-13``: ``ir_act_window``,
``ir_act_report_xml``, ``ir_act_url``, ``ir_act_server`` e ``ir_act_client``
se crean ``INHERITS (ir_actions)``; comparten la secuencia de ids y un
``SELECT`` sobre ``ir_actions`` devuelve también sus filas. Y
``odoo/orm/fields_relational.py:313-314``: un Many2one hacia ``ir_actions``
no crea clave foránea, porque la herencia no la admite.

La herencia de PostgreSQL no comparte columnas de identidad: cada subtipo
pierde la suya y su ``id`` toma por defecto el ``nextval`` de la secuencia de
``ir_actions``, adelantada al máximo de las seis tablas. Las filas existentes
conservan su id. Diseño:
``designs/ir-actions-family-basemodel-and-inheritance.md`` (paso 1).
"""

import django.db.models.deletion
from django.db import migrations, models

INHERIT_SQL = """
DO $$
DECLARE
    seq text := pg_get_serial_sequence('ir_actions', 'id');
    tbl text;
    top bigint;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['ir_act_window', 'ir_act_report_xml',
                               'ir_act_url', 'ir_act_server', 'ir_act_client']
    LOOP
        EXECUTE format('ALTER TABLE %I ALTER COLUMN id DROP IDENTITY', tbl);
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN id SET DEFAULT nextval(%L::regclass)',
            tbl, seq);
        EXECUTE format('ALTER TABLE %I INHERIT ir_actions', tbl);
    END LOOP;
    SELECT coalesce(max(id), 0) INTO top FROM ir_actions;
    PERFORM setval(seq, greatest(top, 1), top > 0);
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0139_report_layout_view_required'),
    ]

    operations = [
        migrations.AlterField(
            model_name='iractionstodo',
            name='action',
            field=models.ForeignKey(
                db_constraint=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='todos',
                to='base.iractionsactions',
                verbose_name='Acción',
            ),
        ),
        migrations.AlterField(
            model_name='irembeddedactions',
            name='action',
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                help_text=(
                    'Exclusivo con python_method (constraint de la fuente).'
                ),
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='embedded_in',
                to='base.iractionsactions',
                verbose_name='Acción',
            ),
        ),
        migrations.AlterField(
            model_name='irfilters',
            name='action_id',
            field=models.ForeignKey(
                blank=True,
                db_column='action_id',
                db_constraint=False,
                help_text=(
                    'The menu action this filter applies to. When left empty '
                    'the filter applies to all menus for this model.'
                ),
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='filter_ids',
                to='base.iractionsactions',
                verbose_name='Action',
            ),
        ),
        # Sin marcha atrás: deshacer la herencia exigiría repartir otra vez
        # las secuencias, y una fila creada después ya no tiene a qué volver.
        migrations.RunSQL(INHERIT_SQL, migrations.RunSQL.noop),
    ]
