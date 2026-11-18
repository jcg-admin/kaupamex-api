"""``UnitOfWorkCommand`` — una orden de gestión que corre en su unidad.

≙ el ``with registry.cursor() as cr:`` que cada orden de ``odoo-bin`` que
toca datos abre alrededor de su trabajo (``odoo19c: odoo/cli/shell.py:138``,
``odoo19c: odoo/cli/populate.py:59``, ``odoo19c: odoo/cli/module.py:140``):
lo que la orden escribe entra entero o no entra. Aquí la unidad la declara
la clase de la orden y la abre :func:`orm.registry.unit_of_work` sobre la
base de ``--database``.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
management-command-unit-of-work.md``.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections

from orm.registry import unit_of_work


class UnitOfWorkCommand(BaseCommand):
    """Orden de gestión cuya ejecución es una unidad de trabajo."""

    def execute(self, *args, **options):
        """Abre la unidad sobre ``--database`` y ejecuta la orden dentro.

        Una base desconocida se rechaza antes de abrir nada, con el mensaje
        que ``update_module_list`` ya daba: la fuente tampoco abre el
        cursor de un registro que no existe.
        """
        alias = options.get('database') or DEFAULT_DB_ALIAS
        if alias not in connections:
            raise CommandError(f'Unknown database alias: {alias}')
        with unit_of_work(alias):
            return super().execute(*args, **options)
