"""Tablas de sonda de una sesión de pruebas, recuperables tras un corte.

Varios módulos de prueba declaran modelos sin migración y crean su tabla
con el ``schema_editor`` en un fixture de sesión, para borrarla al cerrar.
Si la sesión muere antes del cierre (un ``timeout``, un contenedor
reclamado), la tabla queda en la base del worker y la sesión siguiente
falla con ``DuplicateTable`` en todos sus casos.

:func:`create_probe_tables` retira primero la tabla que **esos mismos
modelos** declaran, si existe, y después la crea. No toca nada más: la
pertenencia la fija el ``db_table`` del modelo de sonda, que sólo existe
en el módulo de prueba que la pide.
"""

from django.db import connection


def create_probe_tables(editor, models):
    """Crea las tablas de ``models`` retirando antes lo que dejó un corte.

    ``delete_model`` retira también las tablas intermedias de sus
    Many2many, igual que al cierre normal del fixture.

    :returns: cuántas tablas sobrantes se retiraron.
    """
    existing = set(connection.introspection.table_names())
    reclaimed = 0
    for model in reversed(tuple(models)):
        if model._meta.db_table in existing:
            editor.delete_model(model)
            reclaimed += 1
    for model in models:
        editor.create_model(model)
    return reclaimed
