"""``default_applicability`` pasa de ``varchar`` a ``jsonb`` por empresa.

El campo era un ``Selection`` escalar con ``default='optional'``; la referencia
lo declara ``company_dependent=True``
(``odoo19c: analytic/models/analytic_plan.py:77-86``) y el mecanismo existe
desde la tarea #111, con su despachador de ``Selection`` desde la #129.

Por qué esta migración se escribe a mano
========================================

El ``AlterField`` que ``makemigrations`` genera emite

.. code-block:: sql

   ALTER COLUMN default_applicability TYPE jsonb USING default_applicability::jsonb

y eso **falla sobre datos**: ``'optional'::jsonb`` es un error de sintaxis JSON,
no una cadena JSON. Medido con la migración generada: el ``ALTER`` revienta en
cuanto la tabla tiene una fila con su valor por defecto.

Qué hace con el dato existente, y por qué
=========================================

El valor viejo era **uno por fila, igual para todas las empresas**. El nuevo es
**uno por fila y empresa**. La conversión que conserva el significado es
repartir el escalar entre todas las empresas existentes: lo que antes veía
cualquiera, ahora lo ve cada una por separado.

Perderlo y confiar en ``ir.default`` **no** sería equivalente: el fallback de
``ir.default`` es uno por (modelo, campo, empresa), global a todas las filas,
y el valor que se está convirtiendo es de la fila. Un plan con
``'unavailable'`` y otro con ``'optional'`` no caben en un solo default.
"""
from django.db import migrations

import orm.fields_company_dependent

#: Reparte el escalar entre todas las empresas: ``{id_empresa: valor}``.
A_JSONB = """
ALTER TABLE account_analytic_plan
    ADD COLUMN default_applicability_legacy varchar(16);

UPDATE account_analytic_plan
   SET default_applicability_legacy = default_applicability;

ALTER TABLE account_analytic_plan
    ALTER COLUMN default_applicability DROP DEFAULT,
    ALTER COLUMN default_applicability DROP NOT NULL,
    ALTER COLUMN default_applicability TYPE jsonb USING '{}'::jsonb,
    ALTER COLUMN default_applicability SET DEFAULT '{}'::jsonb;

UPDATE account_analytic_plan p
   SET default_applicability = COALESCE(
           (SELECT jsonb_object_agg(
                       c.id::text, to_jsonb(p.default_applicability_legacy))
              FROM res_company c),
           '{}'::jsonb)
 WHERE p.default_applicability_legacy IS NOT NULL
   AND p.default_applicability_legacy <> '';

ALTER TABLE account_analytic_plan
    DROP COLUMN default_applicability_legacy;
"""

#: La vuelta atrás toma el valor de la empresa de menor id — hay uno por
#: empresa y la columna escalar sólo admite uno. Es una pérdida declarada, no
#: silenciosa: revertir un campo por empresa a uno escalar la tiene por
#: construcción.
A_VARCHAR = """
ALTER TABLE account_analytic_plan
    ADD COLUMN default_applicability_legacy varchar(16);

UPDATE account_analytic_plan p
   SET default_applicability_legacy = (
           SELECT v.value #>> '{}'
             FROM jsonb_each(p.default_applicability) AS v(key, value)
            ORDER BY (v.key)::bigint
            LIMIT 1);

ALTER TABLE account_analytic_plan
    ALTER COLUMN default_applicability DROP DEFAULT,
    ALTER COLUMN default_applicability TYPE varchar(16)
        USING COALESCE(default_applicability_legacy, 'optional'),
    ALTER COLUMN default_applicability SET DEFAULT 'optional',
    ALTER COLUMN default_applicability SET NOT NULL;

ALTER TABLE account_analytic_plan
    DROP COLUMN default_applicability_legacy;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("analytic", "0004_accountanalyticline_is_so_line_edited_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=A_JSONB,
            reverse_sql=A_VARCHAR,
            state_operations=[
                migrations.AlterField(
                    model_name="accountanalyticplan",
                    name="default_applicability",
                    field=orm.fields_company_dependent.CompanyDependent(
                        base_type="selection",
                        blank=True,
                        default=dict,
                        help_text=(
                            "Odoo default_applicability, company_dependent: "
                            "cada empresa fija la suya. Sin valor propio "
                            "responde ir.default."
                        ),
                        null=True,
                        verbose_name="Aplicabilidad por defecto",
                    ),
                ),
            ],
        ),
    ]
