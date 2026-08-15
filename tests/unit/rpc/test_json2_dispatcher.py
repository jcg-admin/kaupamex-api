"""``/json/2/<model>/<method>`` — el despacho genérico y sus cuatro rechazos.

Porte de ``odoo19c: addons/rpc/controllers/json2.py`` (``odoo-tools@abe4040e``,
LGPL-3). Se prueba la **resolución** —la parte que decide qué código HTTP
corresponde— por separado de la vista, porque es donde vive todo el contrato:

- modelo inexistente          → 404
- método inexistente          → 404 (``AttributeError`` traducido)
- método no invocable         → 403 (``AccessError`` = ``PermissionDenied``)
- ``@api.model`` con ``ids``  → 422
- firma que no liga           → 422

El 403 no se prueba con ``pytest.raises`` de un tipo propio: ``AccessError`` es
``django.core.exceptions.PermissionDenied`` (``src/exceptions.py:77``), y el
handler por defecto de DRF lo mapea a 403 sin que el dispatcher intervenga
(medido en ``rest_framework/views.py:exception_handler``). Por eso el
dispatcher **no** lo captura: dejarlo pasar es el comportamiento correcto.
"""

import pytest
from django.db import models
from rest_framework import status
from rest_framework.exceptions import NotFound

import api
from addons.rpc.controllers.json2 import UnprocessableEntity, resolve_call
from exceptions import AccessError


class RpcModel(models.Model):
    """Modelo de prueba: ``managed = False``, sin tabla.

    La resolución no toca la base —sólo el registro y la clase— así que un
    modelo no gestionado basta.
    """

    _name = 'test.rpc.model'

    class Meta:
        app_label = 'base'
        managed = False

    def add(self, a, b=0):
        return a + b

    @api.model
    @classmethod
    def model_level(cls, echo='ok'):
        return echo

    @api.private
    def reserved(self):
        return None


def test_unknown_model_is_404():
    with pytest.raises(NotFound, match='does not exist'):
        resolve_call('no.such.model', 'add', ())


def test_unknown_method_is_404():
    """``AttributeError`` se traduce a 404, no se deja escapar como 500.

    Es la única traducción que el dispatcher hace de verdad: sin ella, DRF no
    conoce ``AttributeError`` y su handler devuelve ``None`` → 500.
    """
    with pytest.raises(NotFound, match='does not exist'):
        resolve_call('test.rpc.model', 'no_such_method', ())


def test_reserved_method_propagates_access_error():
    """403 por propagación, no por traducción — DRF ya mapea PermissionDenied."""
    with pytest.raises(AccessError):
        resolve_call('test.rpc.model', 'reserved', ())


def test_model_level_call_with_ids_is_422():
    """``≙`` *"cannot call X.y with ids"* de la referencia."""
    with pytest.raises(UnprocessableEntity, match='with ids'):
        resolve_call('test.rpc.model', 'model_level', (1, 2))


def test_model_level_call_without_ids_resolves():
    _, func, _ = resolve_call('test.rpc.model', 'model_level', ())
    assert func(echo='hello') == 'hello'


def test_signature_mismatch_is_422():
    """``inspect.signature().bind()`` es el que decide, no un chequeo a mano."""
    with pytest.raises(UnprocessableEntity):
        resolve_call('test.rpc.model', 'add', (), {'no_such_argument': 1})


def test_matching_signature_resolves():
    model, func, records = resolve_call('test.rpc.model', 'add', (), {'a': 1, 'b': 2})
    assert model is RpcModel
    assert func(records, a=1, b=2) == 3


def test_unprocessable_entity_declares_422():
    """DRF 3.16.1 NO trae clase para 422 — su escalera salta de 415 a 429.

    Medido en ``rest_framework/exceptions.py``: ``HTTP_422_UNPROCESSABLE_ENTITY``
    existe en ``status.py`` pero ninguna ``APIException`` lo declara. Por eso la
    clase se declara aquí, y este test es su ancla.
    """
    assert UnprocessableEntity.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
