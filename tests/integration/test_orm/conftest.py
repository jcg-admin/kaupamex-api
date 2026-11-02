"""El entorno de la suite ``test_orm`` — ≙ ``TransactionCase.env``.

``odoo19c: odoo/tests/common.py:1192`` construye
``api.Environment(cls.cr, api.SUPERUSER_ID, {})`` y, por
``odoo/orm/environments.py:66-67``, ``uid == SUPERUSER_ID`` eleva ``su``: la
suite de la referencia crea y lee sin pasar por las reglas de acceso. Las
pruebas de acceso de la fuente cambian de usuario explícitamente
(``with_user``), no dependen del entorno por defecto.

Este fixture reproduce ese entorno y lo deja ACTIVO durante la prueba, que es
como este stack resuelve ``self.env`` (``orm.environments.env``). No concede
permisos a ningún grupo ni toca la ACL del addon.
"""

from contextlib import contextmanager

import pytest
from django.db import transaction

from orm.environments import Environment
from orm.utils import SUPERUSER_ID


@pytest.fixture
def env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment


@pytest.fixture
def assert_raises(env):
    """≙ ``BaseCase._assertRaises`` (``odoo19c: odoo/tests/common.py:502``).

    La fuente envuelve el bloque en ``cr.savepoint()``: si la excepción
    esperada salta, la base vuelve al punto anterior y el entorno se limpia,
    así que una escritura rechazada no contamina las aserciones siguientes.
    Aquí el savepoint es ``transaction.atomic()``, y la limpieza es invalidar
    la caché del entorno y descartar los valores en memoria de los registros
    que la prueba nombra, para que la siguiente lectura vaya a la base.
    """
    @contextmanager
    def raises(exception, *records):
        with pytest.raises(exception) as info:
            with transaction.atomic():
                yield info
        env.invalidate_all(flush=False)
        for record in records:
            for field in record._meta.concrete_fields:
                record.__dict__.pop(field.attname, None)
            record._state.fields_cache.clear()

    return raises
