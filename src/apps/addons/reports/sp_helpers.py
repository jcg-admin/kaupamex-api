"""
sp_helpers — apps.addons.reports

Helper modular para invocar Stored Procedures de PracticaYoruba-db
(sp_rpt_*) y mapear las filas resultantes a list[dict] usando
``cursor.description``.

Sucesora: implementar-endpoints-db-rpt (DEC-DBR-01).
Cierra hallazgos D-26 + D-27 + D-28 del audit T-114.
"""
from django.db import connection


def call_sp(sp_name: str, params: list | None = None) -> list[dict]:
    """
    Invoca un Stored Procedure y retorna las filas como list[dict].

    :param sp_name: nombre del SP (ej. ``sp_rpt_low_stock``).
    :param params: parametros posicionales (None si el SP no recibe).
    :returns: lista de filas serializadas a dict via cursor.description.

    Notas:
    - Usa connection.cursor() — respeta la DB activa
      (config.settings.testing apunta a kaupamex_qa).
    - El SP debe existir en el schema actual; verificar despliegue via
      ``provisioners/mariadb/deploy_objetos.sh``.
    """
    with connection.cursor() as cursor:
        cursor.callproc(sp_name, params or [])
        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]
