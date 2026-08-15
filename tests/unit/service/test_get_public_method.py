"""``get_public_method`` — qué métodos de un modelo son invocables remotamente.

Porte de ``odoo19c: odoo/service/model.py:get_public_method``, el gate de
seguridad que ``addons/rpc/controllers/json2.py`` consulta antes de despachar
``POST /json/2/<model>/<method>``.

Es el **primer** filtro del despacho genérico, y aquí no sustituye a
``HasCapability`` (DEC-11) sino que lo precede: la referencia tiene un gate, la
plataforma tendrá dos. Ver :ref:`h-api-638`.

Los cinco rechazos que la referencia declara, cada uno con su test:

1. nombre con guion bajo → ``AccessError``
2. nombre en ``_UNSAFE_ATTRIBUTES`` → ``AccessError``
3. método inexistente o no invocable → ``AttributeError``
4. ``classmethod`` / ``staticmethod`` → ``AccessError``
5. método decorado ``@api.private`` en cualquier punto del MRO → ``AccessError``
"""

import pytest
from django.db import models

import api
from exceptions import AccessError
from service.model import get_public_method
from tools.safe_eval import _UNSAFE_ATTRIBUTES


class _Base(models.Model):
    """Ancestro que declara el método privado, para probar el barrido del MRO."""

    class Meta:
        abstract = True
        app_label = 'base'

    @api.private
    def heredado_privado(self):
        return 'no debería alcanzarse'


class _Modelo(_Base):
    """Concreto pero ``managed = False``: se instancia sin tabla.

    ``get_public_method`` no toca la base —sólo inspecciona la clase— así que
    un modelo no gestionado basta y evita crear una tabla de prueba.
    """

    _name = 'test.public.method'

    class Meta:
        app_label = 'base'
        managed = False

    def publico(self, valor=1):
        return valor

    def _privado_por_nombre(self):
        return None

    @api.private
    def marcado_privado(self):
        return None

    @classmethod
    def de_clase(cls):
        return None

    @staticmethod
    def estatico():
        return None

    no_invocable = 'soy un atributo, no un método'


@pytest.fixture
def modelo():
    return _Modelo()


def test_devuelve_el_metodo_publico(modelo):
    """El caso feliz: un método público se devuelve **sin ligar**."""
    func = get_public_method(modelo, 'publico')
    assert callable(func)
    assert func(modelo, 7) == 7, 'debe venir sin ligar: recibe self explícito'


def test_rechaza_el_prefijo_de_guion_bajo(modelo):
    with pytest.raises(AccessError, match='Private methods'):
        get_public_method(modelo, '_privado_por_nombre')


@pytest.mark.parametrize('nombre', ['mro', 'f_globals', 'gi_frame'])
def test_rechaza_los_atributos_inseguros(modelo, nombre):
    """``_UNSAFE_ATTRIBUTES`` es la segunda mitad del filtro por nombre."""
    assert nombre in _UNSAFE_ATTRIBUTES
    with pytest.raises(AccessError, match='Private methods'):
        get_public_method(modelo, nombre)


def test_metodo_inexistente_es_attribute_error(modelo):
    """Distinto error a propósito: el dispatcher lo traduce a 404, no a 403."""
    with pytest.raises(AttributeError, match='does not exist'):
        get_public_method(modelo, 'no_existe_en_absoluto')


def test_atributo_no_invocable_es_attribute_error(modelo):
    with pytest.raises(AttributeError, match='does not exist'):
        get_public_method(modelo, 'no_invocable')


@pytest.mark.parametrize('nombre', ['de_clase', 'estatico'])
def test_rechaza_classmethod_y_staticmethod(modelo, nombre):
    """No reciben ``self``, así que el despacho por recordset no aplica.

    La referencia los detecta comparando el atributo de la clase con el de la
    instancia: si son el mismo objeto, no hubo ligadura.
    """
    with pytest.raises(AccessError, match='cannot be called remotely'):
        get_public_method(modelo, nombre)


def test_rechaza_el_decorado_api_private(modelo):
    with pytest.raises(AccessError, match='Private methods'):
        get_public_method(modelo, 'marcado_privado')


def test_el_barrido_de_private_recorre_el_mro(modelo):
    """Un ancestro puede volver privado un nombre que la subclase redefine.

    Es la razón de que la referencia recorra ``cls.mro()`` en vez de mirar sólo
    el método resuelto: sin el barrido, redefinir el método en la subclase
    levantaría la restricción del ancestro.
    """
    with pytest.raises(AccessError, match='Private methods'):
        get_public_method(modelo, 'heredado_privado')


def test_api_private_marca_el_atributo():
    """El decorador es lo que ``get_public_method`` consulta."""

    @api.private
    def f(self):
        return None

    assert f._api_private is True


def test_api_readonly_marca_el_atributo():
    """``_readonly`` lo consume el selector de cursor del dispatcher."""

    @api.readonly
    def f(self):
        return None

    assert f._readonly is True
