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
    def inherited_private(self):
        return 'no debería alcanzarse'


class _Model(_Base):
    """Concreto pero ``managed = False``: se instancia sin tabla.

    ``get_public_method`` no toca la base —sólo inspecciona la clase— así que
    un modelo no gestionado basta y evita crear una tabla de prueba.
    """

    _name = 'test.public.method'

    class Meta:
        app_label = 'base'
        managed = False

    def public(self, value=1):
        return value

    def _private_by_name(self):
        return None

    @api.private
    def marked_private(self):
        return None

    @classmethod
    def plain_classmethod(cls):
        return None

    @api.model
    @classmethod
    def declared_model_level(cls):
        """Nivel de modelo, declarado: la forma que este árbol da a ``@api.model``."""
        return 'model level'

    @staticmethod
    def plain_staticmethod():
        return None

    not_callable = 'soy un atributo, no un método'


@pytest.fixture
def model():
    return _Model()


def test_returns_the_public_method(model):
    """El caso feliz: un método público se devuelve **sin ligar**."""
    func = get_public_method(model, 'public')
    assert callable(func)
    assert func(model, 7) == 7, 'debe venir sin ligar: recibe self explícito'


def test_rejects_the_underscore_prefix(model):
    with pytest.raises(AccessError, match='Private methods'):
        get_public_method(model, '_private_by_name')


@pytest.mark.parametrize('name', ['mro', 'f_globals', 'gi_frame'])
def test_rejects_unsafe_attributes(model, name):
    """``_UNSAFE_ATTRIBUTES`` es la segunda mitad del filtro por nombre."""
    assert name in _UNSAFE_ATTRIBUTES
    with pytest.raises(AccessError, match='Private methods'):
        get_public_method(model, name)


def test_unknown_method_is_attribute_error(model):
    """Distinto error a propósito: el dispatcher lo traduce a 404, no a 403."""
    with pytest.raises(AttributeError, match='does not exist'):
        get_public_method(model, 'no_such_method_at_all')


def test_non_callable_attribute_is_attribute_error(model):
    with pytest.raises(AttributeError, match='does not exist'):
        get_public_method(model, 'not_callable')


@pytest.mark.parametrize('name', ['plain_classmethod', 'plain_staticmethod'])
def test_rejects_classmethod_and_staticmethod(model, name):
    """No reciben ``self``, así que el despacho por recordset no aplica.

    La referencia los detecta comparando el atributo de la clase con el de la
    instancia: si son el mismo objeto, no hubo ligadura.
    """
    with pytest.raises(AccessError, match='cannot be called remotely'):
        get_public_method(model, name)


def test_accepts_the_classmethod_marked_api_model(model):
    """La divergencia declarada: aquí ``classmethod`` ES la forma de ``@api.model``.

    La referencia rechaza todo ``classmethod`` porque en su árbol un método de
    nivel de modelo se escribe ``@api.model def f(self)`` —con ``self`` = un
    recordset vacío— y un ``classmethod`` real sería una anomalía que recibiría
    la clase en vez del recordset.

    Aquí la convención es la contraria y está escrita en el código:
    ``addons/product/models/product_template.py:400`` — *"Son ``@api.model``: no
    dependen de la instancia, así que aquí son ``classmethod``"*. Rechazarlos
    todos dejaría fuera del despacho la superficie de nivel de modelo entera.

    Por eso el criterio se traslada de la **forma** al **marcador**: un
    ``classmethod`` es invocable si —y sólo si— lleva ``@api.model``. Sin él
    sigue rechazado, que es el default fail-closed. Ver :ref:`h-api-639`.
    """
    func = get_public_method(model, 'declared_model_level')
    assert callable(func)
    assert func() == 'model level'


def test_rejects_the_api_private_decorated(model):
    with pytest.raises(AccessError, match='Private methods'):
        get_public_method(model, 'marked_private')


def test_the_private_sweep_walks_the_mro(model):
    """Un ancestro puede volver privado un nombre que la subclase redefine.

    Es la razón de que la referencia recorra ``cls.mro()`` en vez de mirar sólo
    el método resuelto: sin el barrido, redefinir el método en la subclase
    levantaría la restricción del ancestro.
    """
    with pytest.raises(AccessError, match='Private methods'):
        get_public_method(model, 'inherited_private')


def test_api_private_sets_the_marker():
    """El decorador es lo que ``get_public_method`` consulta."""

    @api.private
    def f(self):
        return None

    assert f._api_private is True


def test_api_readonly_sets_the_marker():
    """``_readonly`` lo consume el selector de cursor del dispatcher."""

    @api.readonly
    def f(self):
        return None

    assert f._readonly is True


def test_api_model_sets_the_marker():
    """``@api.model`` debe MARCAR, no ser un no-op.

    Es lo que el dispatcher lee para su 422 (*"cannot call X.y with ids"*) y lo
    que distingue un ``classmethod`` de nivel de modelo de uno cualquiera.
    Antes de :ref:`h-api-639` el decorador era ``return func``: existía con el
    nombre de la referencia y no hacía lo que el de la referencia hace.
    """

    @api.model
    def f(self):
        return None

    assert f._api_model is True


def test_api_model_create_multi_sets_the_marker():
    """≙ ``create._api_model = True`` (``odoo19c: odoo/orm/decorators.py:371``)."""

    @api.model_create_multi
    def create(self, vals_list):
        return None

    assert create._api_model is True
