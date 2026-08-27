r"""``kpi.provider`` extendido por ``account`` — bloqueado, con la mitad SQL portada.

Adaptación de ``addons/account/models/kpi_provider.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 80 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 de 3
=====================================

.. list-table::
   :header-rows: 1
   :widths: 45 15 40

   * - Símbolo
     - Estado
     - Nota
   * - ``get_kpi_summary(cr, uid)`` (función de módulo)
     - **portado**
     - SQL crudo, sin dependencia del ORM ni de ``kpi.provider``
   * - ``KpiProvider.get_account_kpi_summary``
     - **bloqueado**
     - el modelo ``kpi.provider`` no existe en este árbol
   * - ``KpiProvider.get_kpi_summary`` (override de instancia)
     - **bloqueado**
     - ídem — no hay clase base a la que colgarle ``_inherit``

Bloqueo — el modelo base no existe
=====================================

``kpi.provider`` es un ``AbstractModel`` de la referencia que agrega
resúmenes de KPI de varios addons para el panel principal del backend web de
Odoo (``base.KpiProvider`` — el mecanismo que arma la barra de atajos del
Home). Medido:

.. code-block:: text

    grep -rln "kpi.provider\|class KpiProvider" src/ addons/ --include=*.py
    → 0 hits

[PROVEN]. No hay clase base sobre la que aplicar ``_inherit``: fabricar aquí
un ``KpiProvider`` propio inventaría una superficie que ningún panel de este
árbol consume — lo que ``porte-completo-no-parcial.md`` prohíbe expresamente
(mismo desenlace que ``res_config_settings.py`` en este mismo pase).
**Desenlace: (b) bloqueado por pieza concreta.** Sucesor: el modelo
``kpi.provider`` (y el panel que lo consuma) es trabajo de plataforma, no de
``account`` — se registra como hallazgo para que el ejecutor le asigne
iniciativa.

Lo que SÍ se porta — la consulta, íntegra y con su propio guard
===================================================================

``get_kpi_summary(cr, uid)`` (la función de módulo, distinta del método de
instancia del mismo nombre) es SQL crudo deliberado: la referencia dice por
qué — *"this function intentionally bypasses the ORM so KPI summaries can be
retrieved without loading a registry, allowing multi-database servers to
serve them faster"*. No depende de ``kpi.provider`` en absoluto, así que se
porta VERBATIM, columna por columna, incluida su propia defensa:

**El guard de columnas ausentes hace el porte seguro sin adaptación.** La
consulta empieza comprobando en ``information_schema.columns`` que las seis
columnas que necesita existen; si falta alguna, devuelve ``[]`` — "the module
is not installed" en la lectura de la referencia. Medido contra este árbol:
``account_move.checked`` y ``account_move.statement_line_id`` **no
existen** (``grep -n "^    checked\|statement_line" account_move.py`` → 0
hits) [PROVEN]. El guard de la propia referencia detecta esto y responde
``[]`` — comportamiento correcto y sin necesidad de parchear la consulta:
la función es fiel al pie de la letra y su propia defensa absorbe la
diferencia de esquema.

Divergencia declarada — ``ir_model_fields_selection``
==========================================================

La sub-consulta ``journal_type_selection`` lee la etiqueta traducida del
``Selection`` de ``account.journal.type`` desde las tablas de introspección
de campos de Odoo (``ir_model_fields_selection`` / ``ir_model_fields``), que
este ORM no tiene — los ``choices`` de un ``Selection`` de Django viven en el
código Python, no en una tabla. Se resuelve con el diccionario de
``AccountJournal`` construido en Python, en vez de una sub-consulta SQL;
el resultado final —``(tipo, nombre_traducido, cuenta)``— es el mismo
contrato.
"""
from django.db import DEFAULT_DB_ALIAS, connections

from addons.account.models.account_journal import AccountJournal

#: Columnas que la consulta necesita — si falta alguna, "no instalado".
_EXPECTED_COLUMNS = {
    'account_bank_statement_line.is_reconciled',
    'account_move.checked',
    'account_move.journal_id',
    'account_move.state',
    'account_move.statement_line_id',
    'account_journal.type',
}


def get_kpi_summary(uid, using=DEFAULT_DB_ALIAS):
    """Cuántos asientos por tipo de diario requieren atención — ≙
    ``get_kpi_summary`` (``odoo19c: kpi_provider.py:19-45``).

    Cuenta asientos en borrador, publicados sin revisar (``checked=False``),
    y extractos bancarios publicados sin conciliar (``is_reconciled=False``).
    Bypasea el ORM a propósito (mismo motivo que la referencia): no requiere
    cargar ningún registro de modelos.

    :param uid: PK del usuario — sin uso en el SQL de este ORM (la
        referencia lo usa para resolver el idioma de la etiqueta del
        ``Selection`` vía ``res.users`` → ``res.partner``; aquí la etiqueta
        sale de ``AccountJournal.JOURNAL_TYPES`` en español, sin variante por
        idioma — ver la divergencia declarada del módulo). Se conserva en la
        firma para que el llamador futuro (cuando ``kpi.provider`` exista)
        no tenga que cambiarla.
    :param using: alias de base de datos (default: la conexión por defecto).
    """
    with connections[using].cursor() as cursor:
        cursor.execute(
            "SELECT table_name || '.' || column_name "
            "  FROM information_schema.columns "
            " WHERE table_name || '.' || column_name = ANY(%s)",
            [list(_EXPECTED_COLUMNS)],
        )
        existing_columns = {row[0] for row in cursor.fetchall()}
        if _EXPECTED_COLUMNS - existing_columns:
            # Faltan columnas que la consulta necesita -> "no instalado".
            return []

        cursor.execute(
            "SELECT journal.type, COUNT(*) "
            "  FROM account_move move "
            "  JOIN account_journal journal ON move.journal_id = journal.id "
            "  LEFT JOIN account_bank_statement_line st_line "
            "         ON move.statement_line_id = st_line.id "
            " WHERE (move.state = 'draft' "
            "        OR (move.state = 'posted' AND NOT move.checked) "
            "        OR (move.state = 'posted' AND journal.type = 'bank' "
            "            AND (st_line.id IS NULL OR NOT st_line.is_reconciled)))"
            " GROUP BY journal.type",
        )
        rows = cursor.fetchall()

    names = dict(AccountJournal.JOURNAL_TYPES)
    return [{
        'id': f'account_journal_type.{journal_type}',
        'name': names.get(journal_type, journal_type),
        'type': 'integer',
        'value': count,
    } for journal_type, count in rows]
