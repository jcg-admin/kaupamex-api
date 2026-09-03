"""Crea las siete tablas ``orm_signaling_*`` del eje de senalizacion.

La referencia guarda una secuencia por cache en tablas **insert-only**
(``odoo19c: odoo/orm/registry.py:1036-1064``): ``orm_signaling_registry`` mas
una por clave de ``_CACHES_BY_KEY``. ``signal_changes`` inserta una fila cuando
un proceso invalida; ``check_signaling`` lee ``max(id)`` de cada una al abrir
la peticion y se entera de lo que invalido **otro** proceso. Con
``workers = 4`` (``setup/gunicorn.conf.py:93``), sin ese eje una invalidacion
local deja a los otros tres sirviendo contenido viejo — :ref:`h-api-980`.

**Por que tablas y no secuencias.** El comentario de la fuente lo dice: una
``SEQUENCE`` no se replica logicamente
(https://www.postgresql.org/docs/current/logical-replication-restrictions.html),
asi que la numeracion se lleva con filas.

**Divergencia de mecanismo declarada.** Alla el DDL lo emite el propio
``setup_signaling``, que crea la tabla que falte. Aqui el DDL lo emiten las
migraciones, asi que ``setup_signaling`` conserva la mitad que si tiene
receptor —la verificacion, que **nombra** la tabla ausente— y esta migracion
hace la creacion. Es el mismo reparto que ``check_tables_exist``
(:ref:`h-api-1057`).

**Los nombres van literales, no derivados de** ``signaling_table_names()``.
Una migracion es historia congelada: derivarla del codigo vivo haria que
anadir una clave de cache reescribiera el pasado. Una clave nueva se queda sin
tabla, y entonces ``setup_signaling`` la nombra en voz alta — que es
exactamente la conducta que su verificacion existe para dar.

El ``INSERT ... DEFAULT VALUES`` de cada tabla es la siembra de la fuente
(``:1056``): sin ella ``max(id)`` devuelve ``NULL`` y la primera comparacion de
``check_signaling`` se haria contra nada.
"""
from django.db import migrations

#: Los siete nombres, congelados. El orden es el de la fuente: el registro
#: primero, luego las claves de ``_CACHES_BY_KEY`` en su orden de declaracion.
SIGNALING_TABLES = (
    'orm_signaling_registry',
    'orm_signaling_default',
    'orm_signaling_assets',
    'orm_signaling_stable',
    'orm_signaling_templates',
    'orm_signaling_routing',
    'orm_signaling_groups',
)

CREATE = '\n'.join(
    f'CREATE TABLE IF NOT EXISTS "{table}" '
    f'(id SERIAL PRIMARY KEY, date TIMESTAMP DEFAULT now());\n'
    f'INSERT INTO "{table}" DEFAULT VALUES;'
    for table in SIGNALING_TABLES
)

DROP = '\n'.join(f'DROP TABLE IF EXISTS "{table}" CASCADE;'
                 for table in SIGNALING_TABLES)


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0084_unaccent_extension"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE, reverse_sql=DROP),
    ]
