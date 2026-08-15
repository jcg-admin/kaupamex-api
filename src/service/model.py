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

import logging

from django.db import models

from exceptions import AccessError
from tools.safe_eval import _UNSAFE_ATTRIBUTES

_logger = logging.getLogger(__name__)


def get_public_method(model, name):
    """Devuelve el método **sin ligar** de un modelo, si es invocable remotamente.

    Porte de ``odoo19c: odoo/service/model.py:get_public_method``
    (``odoo-tools@abe4040e``, LGPL-3 → copia con atribución, DEC-KX-03).

    Es el primer gate del despacho genérico ``POST /json/2/<model>/<method>``.
    Su docstring en la fuente define «accesible» en dos ejes: **público en el
    sentido de Python** (sin prefijo ``_``) y **no decorado** ``@api.private``.

    Rechaza cinco formas, y el tipo de excepción importa porque el dispatcher
    las traduce a códigos HTTP distintos:

    - nombre con ``_`` o en ``_UNSAFE_ATTRIBUTES`` → ``AccessError``
    - método inexistente o atributo no invocable → ``AttributeError`` (→ 404)
    - ``classmethod`` / ``staticmethod`` → ``AccessError``
    - ``@api.private`` en cualquier punto del MRO → ``AccessError``

    **Esto NO reemplaza a** ``HasCapability`` (DEC-11). El docstring anterior de
    este módulo afirmaba que el modelo de capacidades sustituía a esta allowlist;
    era una racionalización, no un impedimento medido — el dispatcher genérico
    de la referencia no existe aquí, así que no había nada que sustituir. Con el
    despacho genérico, los dos gates se **componen**: la referencia tiene uno,
    la plataforma tendrá dos. Ver :ref:`h-api-638`.

    :param model: instancia del modelo (recordset vacío en la referencia).
    :param name: nombre del método pedido por el cliente.
    :raises AccessError: el método existe pero no es invocable remotamente.
    :raises AttributeError: el método no existe o no es invocable.
    """
    assert isinstance(model, models.Model)
    e = (
        f"Private methods (such as '{type(model).__name__}.{name}') "
        f"cannot be called remotely."
    )
    if name.startswith('_') or name in _UNSAFE_ATTRIBUTES:
        raise AccessError(e)

    cls = type(model)
    method = getattr(cls, name, None)
    if not callable(method):
        raise AttributeError(
            f"The method '{cls.__name__}.{name}' does not exist"
        )
    if method == getattr(model, name, None):
        # Un `classmethod` o `staticmethod` da el MISMO objeto leído desde la
        # clase y desde la instancia: no hubo ligadura, así que no recibe el
        # recordset y el despacho por `func(records, **kwargs)` no aplica.
        raise AccessError(
            f"The method '{cls.__name__}.{name}' cannot be called remotely."
        )

    for mro_cls in cls.mro():
        # Se recorre el MRO entero, no sólo el método resuelto: sin esto,
        # redefinir en la subclase un método que un ancestro marcó privado
        # levantaría la restricción del ancestro.
        if not (cla_method := getattr(mro_cls, name, None)):
            continue
        if getattr(cla_method, '_api_private', False):
            raise AccessError(e)

    return method
