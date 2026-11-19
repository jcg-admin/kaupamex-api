"""Las pruebas de ``fleet`` corren como superusuario.

≙ ``TransactionCase`` de la fuente, que construye su entorno con
``SUPERUSER_ID``. Desde que los modelos de ``fleet`` son ``BaseModel``, la
ACL de la fuente (``odoo19c: addons/fleet/security/ir.model.access.csv``)
sólo da permisos a los grupos de flota. Una prueba que mide la ACL redefine
este fixture.
"""
import pytest

from orm.environments import Environment
from orm.utils import SUPERUSER_ID


@pytest.fixture(autouse=True)
def superuser_env(db):
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment
