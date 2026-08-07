"""El catálogo de países y lo que su ausencia mantenía inerte.

Portación de ``odoo19c: odoo/addons/base/data/res_country_data.xml`` y del
modelo ``res_country.py`` (``odoo-tools@622ddc2a``, addon ``base``, LGPL-3).

Estos tests fijan las dos cosas que la extracción de los datos hizo mal y que
sólo se vieron al comparar contra la referencia — ver :ref:`h-api-359`. Ambas
tenían la misma forma: el instrumento no veía un caso, y su silencio se leyó
como ausencia.
"""
import pytest

from addons.base.models import ResCountry, ResCountryGroup

pytestmark = pytest.mark.django_db


class TestCountryCatalogue:
    """Los 251 países que la referencia declara."""

    def test_seeds_every_country_of_the_reference(self):
        assert ResCountry.objects.count() >= 251

    def test_mexico_carries_its_fiscal_label(self):
        """``vat_label`` es lo que la interfaz muestra en vez de «VAT».

        Para México es **RFC**, y es el dato por el que el CFDI pregunta.
        """
        mexico = ResCountry.objects.get(code='MX')
        assert mexico.vat_label == 'RFC'
        assert mexico.state_required is True
        assert mexico.phone_code == 52

    def test_the_united_kingdom_is_seeded_under_its_iso_code(self):
        """El xmlid de la referencia es ``uk``; su código ISO es ``GB``.

        Es el único país de los 251 donde ambos difieren, y por eso resolver
        la membresía de las agrupaciones por código lo perdía.
        """
        assert ResCountry.objects.filter(code='GB').exists()


class TestCountryGroups:
    """Las ocho agrupaciones y su membresía."""

    @pytest.mark.parametrize('code, expected', [
        ('EU', 27), ('EU_PREFIX', 31), ('SEPA', 49), ('SA', 15),
        ('GCC', 6), ('EEU', 5), ('DOM-TOM', 10), ('CH-LI', 2),
    ])
    def test_membership_matches_the_reference(self, code, expected):
        """Conteos medidos sobre el XML, no elegidos.

        ``GCC`` está aquí por una razón concreta: el XML cita a sus seis
        miembros con ``ref('base.sa')`` mientras las demás usan ``ref('sa')``,
        y el primer extractor sólo veía la segunda forma — el grupo quedó con
        cero miembros sin que nada fallara.
        """
        group = ResCountryGroup.objects.get(code=code)
        assert group.country_ids.count() == expected

    def test_the_united_kingdom_belongs_to_sepa_and_eu_prefix(self):
        """La consecuencia concreta de resolver por xmlid y no por código."""
        uk = ResCountry.objects.get(code='GB')
        assert set(uk.country_groups.values_list('code', flat=True)) >= {
            'SEPA', 'EU_PREFIX'}


class TestFlagUrl:
    """``image_url`` — ≙ ``_compute_image_url``."""

    def test_derives_the_path_from_the_iso_code(self):
        assert ResCountry.objects.get(code='MX').image_url == \
            '/base/static/img/country_flags/mx.png'

    def test_the_two_countries_without_a_flag_return_none(self):
        """``NO_FLAG_COUNTRIES`` de la referencia tiene **dos** códigos.

        La Antártida y Svalbard + Jan Mayen. Una versión anterior de esta
        constante llevaba siete escritos de memoria, cinco de ellos con bandera
        propia en la referencia.
        """
        for code in ('AQ', 'SJ'):
            assert ResCountry.objects.get(code=code).image_url is None

    def test_territories_borrow_the_flag_of_another_country(self):
        """``FLAG_MAPPING`` — sin ella la ruta apunta a un archivo inexistente.

        Guayana Francesa usa la bandera de Francia; las Islas Ultramarinas de
        EE. UU., la de Estados Unidos.
        """
        assert ResCountry.objects.get(code='GF').image_url.endswith('/fr.png')
        assert ResCountry.objects.get(code='UM').image_url.endswith('/us.png')


class TestCountryGroupCodes:
    """``country_group_codes`` — el contrato que ``account_fiscal_country`` lee."""

    def test_returns_the_codes_of_its_groups(self):
        assert 'EU' in ResCountry.objects.get(code='ES').country_group_codes

    def test_returns_a_list_with_an_empty_string_when_it_has_none(self):
        """No ``[]``: la referencia devuelve ``['']`` y eso es contrato.

        Quien compare contra esta lista obtiene un resultado distinto si el
        valor cambia a lista vacía.
        """
        assert ResCountry.objects.get(code='MX').country_group_codes == ['']


class TestPortedMethods:
    """Los tres métodos de ``res.country`` que el puerto no tenía.

    Destapados al preguntar —directiva del ejecutor— cómo prueba la referencia
    este modelo y qué revisa de sus dependencias. El modelo tenía los campos y
    **ninguno** de los ocho métodos de ``odoo19c: res_country.py``.
    """

    def test_the_code_is_normalised_to_upper_case(self):
        """≙ el ``code.upper()`` de ``create``/``write`` de la referencia.

        Es un invariante de datos, no un detalle de estilo: el índice único
        vive sobre ``code``, así que sin normalizar, ``'zz'`` y ``'ZZ'`` son
        dos países distintos y la restricción no lo impide.
        """
        country = ResCountry.objects.create(name='Zetalandia', code='zz')
        country.refresh_from_db()
        assert country.code == 'ZZ'

    def test_get_address_fields_reads_the_keys_of_its_format(self):
        """México pide el **código** del estado; el Reino Unido, su nombre."""
        assert 'state_code' in ResCountry.objects.get(code='MX').get_address_fields()
        assert 'state_name' in ResCountry.objects.get(code='GB').get_address_fields()

    def test_phone_code_for_resolves_by_code_case_insensitively(self):
        assert ResCountry.phone_code_for('mx') == 52
        assert ResCountry.phone_code_for('MX') == 52
        assert ResCountry.phone_code_for('nope') is None
