"""Siembra la ACL y las record rules de ``base``.

≙ lo que la referencia carga al **instalar el módulo**: su
``security/ir.model.access.csv`` (146 filas) y su ``security/base_security.xml``
(``odoo19c: odoo/addons/base/security/``). Aquí no hay cargador de módulo, y
hasta este pase las dos siembras existían **sólo en ``tests/conftest.py``**:
una base de producción recién migrada quedaba con ``ir_model_access`` e
``ir_rule`` vacías.

Qué significaba eso, medido y no supuesto
==========================================

Las dos tablas vacías **no fallan igual**, y por eso las dos importan:

- Sin ACL, ``IrModelAccess.check`` resuelve la lista de modelos permitidos, la
  encuentra vacía y **deniega todo**. Es fail-closed: la aplicación no arranca
  a nada, y el defecto se ve al primer clic.
- Sin record rules, ``_compute_domain`` devuelve ``Q()`` —semántica de la
  referencia: *modelo sin regla, sin restricción*— y **el aislamiento por fila
  no existe**. Ese sí es silencioso: todo funciona, y cada empresa ve las filas
  de las demás. El fail-closed multi-company de este árbol es **dato**
  (``[('company_id', 'in', company_ids)]``, DEC-AISL-04 §4), así que sin el
  dato no hay fail-closed que valga.

El sembrador vive en ``addons/base/security/``, no aquí, por el mismo motivo
que ``0027_seed_base_groups``: un test transaccional hace ``flush`` y borra las
filas mientras ``django_migrations`` las sigue dando por aplicadas, así que
``tests/conftest.py`` necesita re-aplicar **la misma definición** — una sola,
sin dos copias que puedan divergir (:ref:`h-api-337`).
"""
from django.db import migrations

from addons.base.security.base_security import seed_base_rules
from addons.base.security.ir_model_access import seed_base_acl


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias
    seed_base_acl(apps, alias)
    seed_base_rules(apps, alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0058_port_ir_rule_from_the_reference'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que países, idiomas y grupos: borrar
        # la ACL dejaría la aplicación denegando todo, y borrar las reglas
        # dejaría el aislamiento por fila apagado sin que nada lo dijera.
        # Revertir esta migración busca volver al esquema, no vaciar la tabla.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
