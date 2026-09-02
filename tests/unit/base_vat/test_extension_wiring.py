"""El cableado que ``base_vat`` cuelga sobre modelos de ``base``.

``base_vat`` no declara ninguna clase propia: sus cuatro archivos extienden
``res.partner``, ``res.company``, ``res.country`` y ``res.config.settings`` —
es el ``_inherit`` de la fuente materializado con ``extend_model`` desde
``BaseVatConfig.ready()``. Estos casos miden que la extensión **aterrizó**, que
es lo que ningún gate estático puede ver: el gate de porte compara nombres en
el AST y da por instalado lo que la llamada nombra, sin arrancar Django.
"""
import pytest

from addons.base.models.res_company import ResCompany
from addons.base.models.res_country import ResCountry
from addons.base.models.res_partner import ResPartner
from addons.base_setup.models.res_config_settings import ResConfigSettings
from addons.base_vat.models import res_partner as vat

pytestmark = pytest.mark.django_db


# --- Los campos que el addon aporta --------------------------------------

def test_partner_gains_vies_valid_field():
    """≙ ``vies_valid = fields.Boolean(...)`` (``odoo19c: :181-184``)."""
    field = ResPartner._meta.get_field('vies_valid')
    assert field.default is False
    assert field.verbose_name == 'Intra-Community Valid'


def test_company_gains_vat_check_vies_field():
    """≙ ``vat_check_vies`` de ``res_company.py`` (``odoo19c: :7``)."""
    field = ResCompany._meta.get_field('vat_check_vies')
    assert field.default is False


def test_config_settings_gains_vat_check_vies():
    """≙ ``res_config_settings.py`` (``odoo19c: :7``) — el campo del formulario.

    Va por ``add_field_if_absent`` y no por ``extend_model``: la clase destino
    es ``Meta: abstract = True`` y ``extend_model`` resuelve por el registro de
    Django, que no lista a las abstractas. La divergencia está declarada en el
    docstring de su ``apply_``.
    """
    assert hasattr(ResConfigSettings, 'vat_check_vies')


# --- Las propiedades: el compute sin store de la fuente -------------------

def test_perform_vies_validation_is_a_property():
    """≙ ``perform_vies_validation`` (``odoo19c: :179``), ``compute`` sin store.

    Sin ``store`` no hay columna: aquí el hogar es una ``property`` que deriva
    el valor en cada acceso.
    """
    assert isinstance(ResPartner.__dict__['perform_vies_validation'], property)


def test_country_gains_has_foreign_fiscal_position_property_and_its_compute():
    """≙ ``res_country.py`` (``odoo19c: :9-18``) — el campo **y** su compute.

    Los dos símbolos existen: la ``property`` es la superficie de lectura y
    ``_compute_has_foreign_fiscal_position`` conserva el name de la fuente
    para el consumidor que lo llame directo, como allá.
    """
    assert isinstance(ResCountry.__dict__['has_foreign_fiscal_position'], property)
    assert callable(ResCountry._compute_has_foreign_fiscal_position)


# --- El override de escritura --------------------------------------------

def test_save_is_wrapped_and_still_persists():
    """≙ ``create``/``write`` (``odoo19c: :963-974``) en una sola entrada.

    Dos afirmaciones, y la segunda es la que discrimina: envolver ``save`` sin
    delegar en la previa dejaría al partner sin fila, y el caso lo vería.
    """
    assert hasattr(ResPartner.save, '__wrapped__'), 'save no quedó envuelto'
    partner = ResPartner.objects.create(name='Socio de prueba')
    assert ResPartner.objects.filter(pk=partner.pk).exists()


def test_save_keeps_the_value_that_came_in_on_create():
    """El ``vies_valid`` que llega en el alta no lo pisa el cómputo.

    Es el trabajo del ``create`` de la fuente: sacar el campo de la cola de
    recomputación para que el valor recibido sobreviva.
    """
    partner = ResPartner.objects.create(name='Socio VIES', vies_valid=True)
    assert ResPartner.objects.get(pk=partner.pk).vies_valid is True


def test_create_contact_parent_company_is_wrapped():
    """≙ ``_create_contact_parent_company`` (``odoo19c: :976-981``).

    Es el único de los tres enganches de escritura cuya previa **sí** existe en
    ``base`` (``src/addons/base/models/res_partner.py:1777``), así que va por
    ``overrides=`` tal como la fuente lo declara.
    """
    assert hasattr(ResPartner._create_contact_parent_company, '__wrapped__')


# --- Las quince expresiones regulares precompiladas -----------------------

#: Las quince que la fuente declara dentro de la clase (``odoo19c: :385``…``:790``).
#: La lista está entera a propósito: un caso sobre una muestra no distingue
#: «las cuelga todas» de «cuelga la que el caso nombra».
SOURCE_REGEXES = [
    '_check_vat_al_re', '_check_tin1_ro_natural_persons',
    '_check_tin2_ro_natural_persons', '_check_vat_gt_testing_infile',
    '_check_tin_hu_individual_re', '_check_tin_hu_companies_re',
    '_check_tin_hu_european_re', '_check_vat_ch_re', '_check_vat_mx_re',
    '_check_vat_ph_re', '_check_vat_sa_re', '_check_vat_br_re',
    '_check_vat_cr_re', '_check_vat_vn_re', '_check_vat_vn_companies_re',
]


@pytest.mark.parametrize('name', SOURCE_REGEXES)
def test_precompiled_regexes_hang_on_the_class(name):
    """≙ los ``_check_vat_xx_re`` de la fuente, que son atributos de clase.

    Los cuelga el ``luego=`` de ``extend_model``: son atributos, no métodos, y
    ninguno de los cuatro diccionarios de ``extend_model`` los admite. El
    acceso ``self._check_vat_ch_re`` de la fuente es parte del contrato — una
    localización que herede del partner redefine una sin tocar su método.
    """
    assert hasattr(ResPartner, name), f'{name} no quedó colgada'
    assert hasattr(getattr(ResPartner, name), 'match'), f'{name} no es un patrón'


# --- Los cinco bloqueados: fallan RUIDOSAMENTE ----------------------------

@pytest.mark.parametrize('name, args', [
    ('_inverse_vat', ()),
    ('_onchange_vat', ()),
    ('_get_country_specific_vat_variants', ('MXAAA010101AAA', 'MX')),
    ('_get_vat_required_valid', ()),
    ('_check_vies_iap', ()),
])
def test_blocked_symbols_raise_instead_of_returning_a_wrong_answer(name, args):
    """Un símbolo bloqueado existe y **grita**; no devuelve un valor plausible.

    Es el criterio de ``porte-completo-no-parcial.md``: un bloqueo declarado
    sigue siendo deuda con su arista recorrible. Si en vez de levantar
    devolviera ``False`` o ``None``, el llamador leería una respuesta y nadie
    volvería a mirar — la deuda desaparecería de la lista sin cerrarse.
    """
    function = getattr(vat, name)
    with pytest.raises(NotImplementedError):
        function(object(), *args)
