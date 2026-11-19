"""Las pruebas de ``base_automation`` corren como superusuario.

≙ ``TransactionCase`` de la fuente, que construye su entorno con
``SUPERUSER_ID``. Desde que ``base.automation`` es ``BaseModel``, la ACL de
la fuente (``odoo19c: addons/base_automation/security/ir.model.access.csv``)
sólo da permisos a ``base.group_system``. Una prueba que necesita otro
usuario lo abre con ``user_scope`` dentro de este entorno.
"""
import pytest

from orm.environments import Environment
from orm.utils import SUPERUSER_ID


@pytest.fixture(autouse=True)
def superuser_env(db, system_user):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment
