"""Los dos índices parciales de ``res.device.log``, medidos en el catálogo.

Porta los dos objetos de tabla que la referencia declara en la cabecera del
modelo (``odoo19c: odoo/addons/base/models/res_device.py:37-38``):

.. code-block:: python

   _composite_idx = models.Index("(user_id, session_identifier, platform, "
                                 "browser, last_activity, id) "
                                 "WHERE revoked IS NOT TRUE")
   _revoked_idx   = models.Index("(revoked) WHERE revoked IS NOT TRUE")

Por qué se mide el catálogo y no la declaración
------------------------------------------------

Un test que leyera ``Meta.indexes`` afirmaría que **el modelo lo declara**, que
es lo que el archivo ya dice de sí mismo. Lo que puede fallar en silencio es
otra cosa: que la migración no aplique, o que el predicado parcial se traduzca
a un SQL que **no** es el de la fuente. Por eso las aserciones van contra
``pg_indexes``, que es el estado real del motor.

El predicado NO distingue aquí, y eso se midió
----------------------------------------------

``WHERE revoked IS NOT TRUE`` y ``WHERE revoked = false`` **difieren** en la
lógica de tres valores de SQL: el primero admite el NULL. Aquí no: la columna
se declaró ``NOT NULL`` (``information_schema.columns.is_nullable = 'NO'``),
así que los dos predicados son equivalentes y PostgreSQL normaliza **ambos** al
mismo texto — ``WHERE (NOT revoked)``.

Medido: sustituyendo ``~Q(revoked=True)`` por ``Q(revoked=False)`` en el modelo
y en la migración, y reconstruyendo la base con ``--create-db``, el
``indexdef`` sale **idéntico** y los cuatro casos siguen pasando. Un caso que
pretendiera atrapar esa sustitución sería decorativo, así que no se escribe.

Se conserva ``~Q(revoked=True)`` por **fidelidad al texto de la fuente**, no
por semántica: es lo que hace legible el porte al leerlo contra
``res_device.py:37-38``. Si algún día la columna admitiera NULL, la diferencia
dejaría de ser cosmética — y entonces el control de abajo sí discriminaría.

*Métrica:* ``indexdef`` de ``pg_indexes`` para la tabla ``res_device_log``.
*Ciega a:* la diferencia entre los dos predicados mientras la columna sea
``NOT NULL`` (medido arriba); y a si el planificador **elige** el índice — con
la tabla vacía de un test PostgreSQL prefiere el barrido secuencial. Estos
casos afirman que el índice existe, sobre qué columnas y que es parcial; no que
se use.

El control que puede fallar
---------------------------

Retirando el ``condition=`` de los dos índices —en el modelo y en la
migración— y reconstruyendo con ``--create-db``, la suite pasa de **4 passed**
a **1 failed, 3 passed**. Cae el único que mide la parcialidad; sobreviven los
tres que miden otra cosa a propósito, y conviene nombrarlos:

- **existencia** — un índice sin ``WHERE`` sigue existiendo en el catálogo;
- **columnas** — el ``condition`` no las toca;
- **nombres declarados** — se leen de ``Meta.indexes``, que conserva el
  ``name=`` aunque pierda el predicado.

La predicción escrita antes de correr el control decía *"2 failed, 2 passed"*
y contaba el de los nombres entre los que caen. Es falsa: el nombre no depende
del predicado. Se corrige aquí en vez de ajustar el caso para que la
predicción encaje — lo que no vale es no saberlo.
"""

import pytest
from django.db import connection

from addons.base.models.res_device import ResDeviceLog

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

COMPUESTO = 'res_device_log_composite_idx'
REVOCADO = 'res_device_log_revoked_idx'


def _indexdef(name):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT indexdef FROM pg_indexes '
            'WHERE tablename = %s AND indexname = %s',
            ['res_device_log', name],
        )
        fila = cursor.fetchone()
    return fila[0] if fila else None


def test_both_indexes_exist_in_the_catalog(db):
    assert _indexdef(COMPUESTO) is not None
    assert _indexdef(REVOCADO) is not None


def test_the_composite_index_covers_the_six_columns_of_the_reference(db):
    definition = _indexdef(COMPUESTO)
    for columna in ('user_id', 'session_identifier', 'platform', 'browser',
                    'last_activity', 'id'):
        assert columna in definition, f'{columna} falta en {definition}'


def test_both_are_partial_and_negate_the_revoked_column(db):
    """La parcialidad es lo que los hace baratos.

    Un índice completo sobre las mismas columnas indexaría también las
    sesiones revocadas, que la vista ``res.device`` nunca consulta — y el
    ``indexdef`` se leería casi igual. Por eso la aserción es sobre el
    ``WHERE``, no sobre las columnas: ésas ya las mide el caso anterior.
    """
    for name in (COMPUESTO, REVOCADO):
        definition = _indexdef(name)
        assert ' WHERE ' in definition, f'{name} no es parcial: {definition}'
        assert 'NOT revoked' in definition, \
            f'{name} no niega revoked: {definition}'


def test_the_model_declares_them_with_the_names_of_the_reference(db):
    """El nombre se conserva, como manda ``atributos-de-clase-de-modelo.md``
    para un objeto de tabla portado."""
    declarados = {idx.name for idx in ResDeviceLog._meta.indexes}
    assert {COMPUESTO, REVOCADO} <= declarados
