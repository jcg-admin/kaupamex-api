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

import pytest

from orm.environments import Environment
from orm.utils import SUPERUSER_ID


@pytest.fixture
def env(db, system_user):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment
