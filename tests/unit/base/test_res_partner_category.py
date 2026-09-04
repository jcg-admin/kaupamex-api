"""``res.partner.category`` y los dos mixins de formato — porte del bloque de
partner que faltaba (``odoo19c: odoo/addons/base/models/res_partner.py``).

``res_partner.py`` de este arbol declaraba **una** clase contra las **cuatro**
de la referencia. Las tres ausentes eran la categoria jerarquica y los dos
mixins que deciden como se presenta un contacto segun el country.

El control que puede fallar
---------------------------

La guarda medida es **la de recursividad** de ``_check_parent_id``: la fuente
levanta *"You can not create recursive tags."* si una tag acaba colgando
de si misma. Sin ella, ``display_name`` —que sube por la cadena de padres—
entra en bucle infinito.

Medido: con ``_check_parent_id`` vaciada a ``pass``, esta suite pasa de
**11 passed** a **1 failed, 10 passed** — cae
``test_a_cycle_is_refused``, y solo ese. Los otros diez miden la jerarquia
sana, el color, la path materializada y los dos mixins, que no tocan esa
rama.

Prediccion antes de correrlo: 1 cae. (Las predicciones anteriores de esta
sesion fallaron dos de tres veces; se anota la de este por el mismo motivo
que el control existe.)
"""
import pytest

from addons.base.models.res_partner import (FormatAddressMixin,
                                            FormatVatLabelMixin,
                                            ResPartnerCategory)
from addons.base.models.res_country import ResCountry
from exceptions import ValidationError
from tests.conftest import matching_by_display_name

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


# --------------------------------------------------------------------------
# La jerarquia de etiquetas
# --------------------------------------------------------------------------

def test_the_class_attributes_are_the_references():
    """``atributos-de-clase-de-modelo.md``: los cuatro que la fuente declara."""
    assert ResPartnerCategory._name == 'res.partner.category'
    assert ResPartnerCategory._description == 'Partner Tags'
    assert ResPartnerCategory._order == 'name, id'
    assert ResPartnerCategory._parent_store is True


def test_the_color_is_dealt_at_random_within_eleven():
    """``_get_default_color`` (``:143-144``) reparte entre once."""
    tag = ResPartnerCategory.objects.create(name='Clientes')
    assert 1 <= tag.color <= ResPartnerCategory.COLOR_MAX


def test_an_explicit_color_is_respected():
    """El default de la fuente es *callable*: corre al crear, no pisa lo dado."""
    tag = ResPartnerCategory.objects.create(name='Fija', color=7)
    assert tag.color == 7


def test_the_color_is_not_redealt_on_write():
    tag = ResPartnerCategory.objects.create(name='Estable')
    first = tag.color
    tag.name = 'Estable II'
    tag.save()
    tag.refresh_from_db()
    assert tag.color == first


def test_display_name_is_the_whole_chain():
    """``_compute_display_name`` (``:162-172``) — de la raiz hacia abajo."""
    root = ResPartnerCategory.objects.create(name='Clientes')
    middle = ResPartnerCategory.objects.create(name='Mayoristas', parent=root)
    leaf = ResPartnerCategory.objects.create(name='Norte', parent=middle)
    assert leaf.display_name == 'Clientes / Mayoristas / Norte'
    assert root.display_name == 'Clientes'


def test_the_materialized_path_is_kept():
    """``parent_path`` sostiene ``_parent_store``: mismo mecanismo que
    ``ResCompany._compute_parent_path``."""
    root = ResPartnerCategory.objects.create(name='Raiz')
    child = ResPartnerCategory.objects.create(name='Hija', parent=root)
    root.refresh_from_db()
    child.refresh_from_db()
    assert root.parent_path == f'{root.pk}/'
    assert child.parent_path == f'{root.pk}/{child.pk}/'


def test_a_cycle_is_refused():
    """``_check_parent_id`` (``:157-160``) — el mensaje de la fuente es
    *"You can not create recursive tags."*"""
    a = ResPartnerCategory.objects.create(name='A')
    b = ResPartnerCategory.objects.create(name='B', parent=a)
    a.parent = b
    with pytest.raises(ValidationError):
        a.save()


def test_searching_by_name_brings_the_descendants():
    """``_search_display_name`` (``:174-181``) — quien busca "Clientes"
    espera tambien "Clientes / Mayoristas"."""
    root = ResPartnerCategory.objects.create(name='Clientes')
    ResPartnerCategory.objects.create(name='Mayoristas', parent=root)
    found = matching_by_display_name(ResPartnerCategory, 'like', 'Clientes')
    assert found.count() == 2


def test_a_negated_search_is_refused():
    """La fuente devuelve ``NotImplemented``: negar un ``child_of`` pediria
    el complemento de un arbol, que no es negar cada nombre."""
    assert ResPartnerCategory._search_display_name(
        'not like', 'x') is NotImplemented


# --------------------------------------------------------------------------
# Los dos mixins — la DECISION, no el XML
# --------------------------------------------------------------------------

def test_the_vat_label_comes_from_the_country():
    """``FormatVatLabelMixin`` (``:45-58``) — «RFC» en Mexico, «NIF» en
    Espana. El dato esta en ``ResCountry.vat_label``."""
    # ``MX`` ya lo siembra ``0017_seed_countries``: se actualiza, no se crea
    # —crear duplicaria la clave unica de ``code``—.
    country = ResCountry.objects.get(code='MX')
    country.vat_label = 'RFC'
    country.save(update_fields=['vat_label'])
    company = type('Empresa', (), {'country': country})()
    assert FormatVatLabelMixin.vat_label_for(company) == 'RFC'
    without_country = type('Empresa', (), {'country': None})()
    assert FormatVatLabelMixin.vat_label_for(without_country) == ''


def test_the_address_order_follows_the_country_format():
    """``FormatAddressMixin`` (``:61-136``) — el orden de la linea que
    contiene la ciudad, con los dos derivados ya mapeados a su campo real.

    La version anterior de este caso afirmaba ``['city', 'zip',
    'state_code']`` y era fiel a lo que el porte entregaba entonces: la linea
    en crudo. Lo que la fuente hace ademas —mapear ``state_code`` a
    ``state_id`` (``:112``, ``:120``) y colocar al final lo que el formato no
    nombra (``:119-124``)— faltaba, y este caso lo daba por bueno.

    El desglose de la conducta completa vive en
    ``tests/integration/base/test_format_address_and_vat_label.py``.
    """
    country = ResCountry.objects.create(
        name='Probeland', code='PB',
        address_format='%(street)s\n%(city)s %(zip)s %(state_code)s\n%(country_name)s')
    assert FormatAddressMixin.field_order_for(country) == [
        'city', 'zip', 'state_id']
