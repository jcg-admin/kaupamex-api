"""``orm.method_chain`` — el ``super()`` del idioma de extensión por ``setattr``.

Cubre las tres formas de descriptor que la referencia usa sobre un mismo
modelo: método de instancia, ``@classmethod`` y ``@staticmethod``. El caso de
``@classmethod`` es el que :ref:`h-api-381` registró como roto: ``getattr``
sobre él devuelve un método ya ligado a ``cls``, así que la cadena pasaba la
instancia como argumento extra.

No tocan la base de datos — son clases planas de Python, que es exactamente el
nivel en el que vive el mecanismo.
"""
import pytest

from orm.method_chain import chain_method, extend_list


class _Base:
    """Terminal de las tres cadenas — ≙ lo que declara ``addons/base``."""

    def relay(self, value):
        return f'base:{value}'

    @classmethod
    def retrieve_acc_type(cls, acc_number):
        return 'bank'

    @staticmethod
    def normalize(value):
        return value.strip()

    @classmethod
    def supported_types(cls):
        return ['bank']


@pytest.fixture
def probe_cls():
    """Una subclase fresca por test — ``chain_method`` muta la clase."""
    return type('Probe', (_Base,), {})


def test_instance_method_relays_when_new_returns_none(probe_cls):
    def relay(self, value):
        return 'new' if value == 'mine' else None

    chain_method(probe_cls, 'relay', relay)

    instance = probe_cls()
    assert instance.relay('mine') == 'new'
    assert instance.relay('other') == 'base:other'


def test_classmethod_chain_does_not_leak_self(probe_cls):
    """El caso de H-API-381: encadenar sobre un ``@classmethod``.

    Antes del arreglo esto daba ``TypeError: retrieve_acc_type() takes 2
    positional arguments but 3 were given`` — la instancia viajaba como
    argumento extra hacia el método base, que ya venía ligado a ``cls``.
    """
    def retrieve_acc_type(cls, acc_number):
        return 'iban' if acc_number.startswith('ES') else None

    chain_method(probe_cls, 'retrieve_acc_type', retrieve_acc_type)

    # Por la clase — la forma que un descriptor destruido rompería primero.
    assert probe_cls.retrieve_acc_type('ES9121000418') == 'iban'
    assert probe_cls.retrieve_acc_type('0001234567') == 'bank'
    # Y por la instancia, que es como lo invoca ``ResPartnerBank.save()``.
    assert probe_cls().retrieve_acc_type('ES9121000418') == 'iban'
    assert probe_cls().retrieve_acc_type('0001234567') == 'bank'


def test_classmethod_stays_a_classmethod(probe_cls):
    """El descriptor se preserva: ``setattr`` de una función plana lo perdía."""
    def retrieve_acc_type(cls, acc_number):
        return None

    chain_method(probe_cls, 'retrieve_acc_type', retrieve_acc_type)

    raw = probe_cls.__dict__['retrieve_acc_type']
    assert isinstance(raw, classmethod)


def test_classmethod_chain_of_three(probe_cls):
    """Tres eslabones — el defecto sólo se manifiesta al encadenar de verdad."""
    def first_link(cls, acc_number):
        return 'iban' if acc_number.startswith('ES') else None

    def second_link(cls, acc_number):
        return 'clabe' if len(acc_number) == 18 and acc_number.isdigit() else None

    chain_method(probe_cls, 'retrieve_acc_type', first_link)
    chain_method(probe_cls, 'retrieve_acc_type', second_link)

    assert probe_cls.retrieve_acc_type('ES9121000418') == 'iban'
    assert probe_cls.retrieve_acc_type('012180001234567895') == 'clabe'
    assert probe_cls.retrieve_acc_type('123') == 'bank'


def test_classmethod_chain_is_idempotent(probe_cls):
    """``ready()`` puede correr dos veces; la cadena no debe duplicarse."""
    def retrieve_acc_type(cls, acc_number):
        return None

    chain_method(probe_cls, 'retrieve_acc_type', retrieve_acc_type)
    installed = probe_cls.__dict__['retrieve_acc_type']
    chain_method(probe_cls, 'retrieve_acc_type', retrieve_acc_type)

    assert probe_cls.__dict__['retrieve_acc_type'] is installed


def test_classmethod_combine(probe_cls):
    """``combine=extend_list`` sobre un ``@classmethod`` — el caso de
    ``_get_supported_account_types``."""
    def supported_types(cls):
        return ['iban']

    chain_method(probe_cls, 'supported_types', supported_types,
                 combine=extend_list)

    assert probe_cls.supported_types() == ['bank', 'iban']


def test_staticmethod_chain_takes_no_first_argument(probe_cls):
    def normalize(value):
        return value.replace(' ', '') if ' ' in value else None

    chain_method(probe_cls, 'normalize', normalize)

    assert isinstance(probe_cls.__dict__['normalize'], staticmethod)
    assert probe_cls.normalize('ES91 2100') == 'ES912100'
    assert probe_cls.normalize('  ES912100  ') == 'ES912100'


def test_installs_new_method_when_there_is_no_previous(probe_cls):
    def brand_new(self):
        return 'new'

    chain_method(probe_cls, 'brand_new', brand_new)

    assert probe_cls().brand_new() == 'new'


def test_installs_new_classmethod_when_there_is_no_previous(probe_cls):
    """Sin previo, el llamador declara el descriptor que quiere."""
    def brand_new(cls):
        return cls.__name__

    chain_method(probe_cls, 'brand_new', classmethod(brand_new))

    assert isinstance(probe_cls.__dict__['brand_new'], classmethod)
    assert probe_cls.brand_new() == 'Probe'


def test_refuses_to_clobber_a_property(probe_cls):
    """Parte (c) de H-API-381, medida: una ``property`` sustituida por una
    función plana hacía que ``obj.value`` devolviera el método. Ahora falla
    ruidoso en vez de corromper en silencio."""
    probe_cls.value = property(lambda self: 'base')

    def value(self):
        return 'new'

    with pytest.raises(TypeError, match='no un método'):
        chain_method(probe_cls, 'value', value)

    assert probe_cls().value == 'base'
