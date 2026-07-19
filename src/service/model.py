"""``model`` — fiel a ``odoo/service/model.py`` (Odoo 19).

En Odoo ``service/model.py`` es el **dispatch RPC de métodos de modelo**:
``call_kw`` / ``execute_cr`` / ``dispatch`` (el ``execute_kw`` de la API externa),
``get_public_method`` (qué métodos son invocables remotamente, filtrando privados
y ``@api.private``), ``Params``, y ``retrying`` (loop de reintento ante deadlock /
serialization failure, ``MAX_TRIES_ON_CONCURRENCY_FAILURE = 5``).

Mapeo a Django/DRF — es un stub delgado documentado; cada pieza ya vive en la pila:

===================================  ===================================================
Odoo ``service/model``               Equivalente en la pila
===================================  ===================================================
``call_kw`` / ``execute_cr`` /       vistas + serializers DRF: el verbo HTTP
``dispatch`` (``execute_kw`` RPC)    (GET/POST/PATCH/DELETE) mapea a la operación ORM;
                                     el router DRF hace el dispatch, no un
                                     ``execute_kw`` central
``get_public_method`` (superficie    autorización por **capacidad**: ``HasCapability``
invocable remotamente)               fail-closed (sin capacidad declarada → 403) —
                                     ver skill ``backend-drf``; no una allowlist de
                                     nombres de método
``Params``                           parámetros de request de DRF (``request.data`` /
                                     query params) validados por el serializer
``retrying`` (reintento deadlock)    **ya extraído nativo** en ``service/retry.py``
                                     (patrón loop + backoff+jitter contra el 1213 de
                                     MariaDB; DEC-KX-03) — ver ese módulo
===================================  ===================================================

Por qué stub: recrear ``execute_kw`` duplicaría el router+serializers de DRF, y la
allowlist ``get_public_method`` la reemplaza el modelo de capacidades (más estricto:
fail-closed por vista). La única lógica no-Django de este módulo —el reintento de
concurrencia— NO se re-documenta aquí: vive faithfully en ``service/retry.py``.
"""
