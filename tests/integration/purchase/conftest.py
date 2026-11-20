"""Las pruebas de este directorio corren como superusuario."""
import pytest

from orm.environments import Environment
from orm.utils import SUPERUSER_ID


@pytest.fixture(autouse=True)
def superuser_env(db):
    """≙ ``TransactionCase`` de la fuente, que construye su entorno con
    ``SUPERUSER_ID``: los modelos de producto son ``BaseModel`` y leerlos
    pasa por la ACL. Una prueba que mide la ACL redefine este fixture.
    Precedente: ``tests/unit/fleet/conftest.py``."""
    environment = Environment(None, SUPERUSER_ID, {})
    with environment:
        yield environment
