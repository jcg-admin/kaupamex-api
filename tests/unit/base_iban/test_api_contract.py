"""El vocabulario de ``acc_type`` llega vivo al contrato DRF — y cuándo no.

``base_iban`` encadena ``_get_supported_account_types`` sobre
``ResPartnerBank``, así que el vocabulario del campo ``acc_type`` **crece con
los addons instalados**: ``base`` aporta ``bank``, ``base_iban`` aporta
``iban``, y un addon futuro puede aportar el suyo. El campo lo declara con un
``choices`` **invocable** (``base/models/res_partner_bank.py``), que es la
forma con la que Django resuelve el vocabulario en cada iteración en vez de
congelarlo al importar.

Estos tests fijan que esa propiedad **sobrevive el cruce a DRF**, que no es
gratis: Django y DRF resuelven ``choices`` de forma distinta.

- **Django** guarda el invocable en un ``CallableChoiceIterator`` y lo
  re-resuelve en cada iteración (``django/utils/choices.py::normalize_choices``
  → ``CallableChoiceIterator.__iter__``).
- **DRF** lo **materializa**: ``ChoiceField._set_choices``
  (``rest_framework/fields.py:1430-1441``) aplana las opciones a un dict plano
  en el momento de construir el campo, y ``utils/field_mapping.py:154-155`` lee
  ``model_field.choices`` una sola vez.

Que no haya defecto hoy depende de **cuándo** corre esa materialización, no de
que DRF sea perezoso —no lo es—. La evidencia completa, con las líneas de los
dos paquetes instaladas y la medición que las respalda, está en
``docs: …/completar-familia-base/evidencia-choices-invocables-django-drf.rst``.
"""
import pytest
from rest_framework import serializers

from addons.base.models.res_bank import (
    ResPartnerBank,
    _supported_account_types,
)
from orm.method_chain import chain_method, extend_list

pytestmark = pytest.mark.django_db


class AccTypeAutoSerializer(serializers.ModelSerializer):
    """Campo derivado por ``ModelSerializer`` — se construye por instancia."""

    class Meta:
        model = ResPartnerBank
        fields = ['acc_type']


@pytest.fixture
def restored_account_types():
    """Deja ``_get_supported_account_types`` como estaba.

    Encadenar sobre una clase muta estado **global** del proceso: sin esta
    restauración, el tipo que instala un test aparecería en todos los que
    corran después y el orden de la suite cambiaría los resultados.
    """
    original = ResPartnerBank.__dict__.get('_get_supported_account_types')
    yield
    if original is None:
        ResPartnerBank.__dict__.pop('_get_supported_account_types', None)
    else:
        setattr(ResPartnerBank, '_get_supported_account_types', original)


def test_the_contract_carries_what_the_chain_declares():
    """Lo que el serializer publica es lo que la cadena resuelve, no un
    subconjunto: si ``base_iban`` está instalado, ``iban`` está en el contrato.
    """
    published = list(AccTypeAutoSerializer().fields['acc_type'].choices)
    assert published == [code for code, _label in _supported_account_types()]
    assert 'iban' in published


def test_a_model_serializer_field_is_rebuilt_per_instance():
    """La razón por la que el contrato no se congela.

    DRF materializa las opciones al construir el campo; lo que salva la
    frescura es que ``get_fields()`` corre **por instancia** de serializer —y
    un serializer se instancia por petición—, no que DRF sea perezoso.
    """
    assert AccTypeAutoSerializer().fields is not AccTypeAutoSerializer().fields
    assert AccTypeAutoSerializer._declared_fields == {}


def test_a_type_chained_later_reaches_the_contract(restored_account_types):
    """Un addon que llegue después entra al contrato sin tocar el serializer."""
    def extra_types(cls):
        return [('clabe', 'CLABE')]

    chain_method(ResPartnerBank, '_get_supported_account_types',
                 classmethod(extra_types), combine=extend_list)

    assert 'clabe' in list(AccTypeAutoSerializer().fields['acc_type'].choices)


def test_an_explicit_choice_field_freezes_the_vocabulary(
        restored_account_types):
    """El anti-patrón que este archivo existe para impedir.

    Declarar el campo explícito con ``choices=_supported_account_types()``
    evalúa el invocable **al importar el módulo** y lo deja en
    ``_declared_fields``, que es estado de clase. El vocabulario queda
    congelado para toda la vida del proceso: un tipo encadenado después no
    aparece nunca, y el contrato publicado miente sobre lo que el modelo
    acepta.
    """
    class FrozenSerializer(serializers.ModelSerializer):
        acc_type = serializers.ChoiceField(choices=_supported_account_types())

        class Meta:
            model = ResPartnerBank
            fields = ['acc_type']

    def extra_types(cls):
        return [('clabe', 'CLABE')]

    chain_method(ResPartnerBank, '_get_supported_account_types',
                 classmethod(extra_types), combine=extend_list)

    assert 'clabe' in [code for code, _label in _supported_account_types()]
    assert 'clabe' not in list(FrozenSerializer().fields['acc_type'].choices)
    # Y el automático del mismo proceso sí lo ve — la diferencia es la forma
    # de declararlo, no el estado del modelo.
    assert 'clabe' in list(AccTypeAutoSerializer().fields['acc_type'].choices)
