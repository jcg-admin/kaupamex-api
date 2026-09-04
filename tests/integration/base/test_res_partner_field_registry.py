"""Tests — el registro de campos del modelo incluye el campo sin columna.

Qué mide este archivo, y por qué no lo medía ninguno
====================================================

``_convert_fields_to_values`` (``odoo19c: odoo/addons/base/models/
res_partner.py:653-657``) recorre los nombres que le dan y consulta
``self._fields[fname]`` — el registro de campos del modelo — para rechazar un
``one2many``. En la fuente ese registro contiene **todos** los campos que el
modelo declara, vengan de donde vengan: los de la clase base y los que un
addon le cuelga con ``_inherit``.

Aquí el porte consultaba ``self._meta.get_field(fname)``, y ése es un
registro **estrictamente más estrecho**: sólo tiene los campos de Django, o
sea los que tienen columna. En cuanto ``base_address_extended`` hizo que
``_address_fields()`` devolviera ``city_id`` —cuyo valor vive en la fila
RELATED (DEC-SALE-01) y no en una columna de ``res_partner``— la consulta
levantaba ``FieldDoesNotExist`` y se llevaba por delante toda la
sincronización de direcciones.

La prosa del propio archivo declaraba la equivalencia —*"``self._fields
[fname]`` es ``self._meta.get_field(fname)``"*— y era falsa: son dos
registros de tamaño distinto. Ver :ref:`h-api-1025`.

Qué haría fallar a cada control
--------------------------------

``TestTheRegistryHoldsEveryDeclaredField::test_it_holds_the_field_without_a_column``
    CONTROL del ensanchado. Con ``_fields`` filtrando por ``_meta`` este caso
    es rojo; es el que distingue *"el registro es el de la fuente"* de *"el
    registro es el de las columnas"*.

``TestTheOneToManyGuardSurvives::test_a_reverse_relation_is_still_refused``
    CONTROL de que el ensanchado **no** ablandó la guarda. Un porte que
    resolviera el fallo tragándose la excepción pasaría el caso de arriba y
    rompería éste.

``TestTheOneToManyGuardSurvives::test_a_name_that_is_not_a_field_is_refused``
    CONTROL del tercer desenlace. La fuente levanta ``KeyError`` ante un
    nombre que no declara; un ``try/except`` que devolviera el valor sin más
    aceptaría una errata en silencio.

``TestWritingTheFieldWithoutAColumn::test_it_creates_the_related_row``
    CONTROL de la escritura. Leerlo no basta: en la fuente ``city_id`` es una
    columna y siempre se puede escribir, también en un contacto que todavía
    no tiene fila RELATED.
"""
import pytest

from addons.base.models.res_partner import ResPartner
from addons.base_address_extended.models.res_city import ResCity
from addons.base_address_extended.models.res_partner import AddressStructured
from addons.base.models.res_country import ResCountry
from orm.environments import context_scope
from orm.fields_nonstored import NonStored

pytestmark = pytest.mark.integration


def _company(**extra):
    """Una empresa creada sin disparar la sincronización de la jerarquía."""
    data = dict(name='Kaupamex SA', is_company=True)
    data.update(extra)
    with context_scope(_partners_skip_fields_sync=True):
        return ResPartner.objects.create(**data)


def _city(name='Guadalajara'):
    country, _ = ResCountry.objects.get_or_create(
        code='MX', defaults={'name': 'México'})
    city, _ = ResCity.objects.get_or_create(
        name=name, country_id=country, defaults={'zipcode': '44100'})
    return city


class TestTheRegistryHoldsEveryDeclaredField:
    """≙ ``BaseModel._fields`` — el registro del modelo, no el de sus columnas."""

    def test_it_holds_the_columns(self, db):
        registry = _company()._fields
        assert 'street' in registry
        assert 'city' in registry

    def test_it_holds_the_field_without_a_column(self, db):
        """``city_id`` lo declara ``base_address_extended``, y no tiene columna.

        Qué lo haría fallar: que ``_fields`` se construya sólo con
        ``_meta.get_fields()``. Ése era el estado hasta :ref:`h-api-1025`.
        """
        registry = _company()._fields
        assert 'city_id' in registry, (
            'el registro del modelo dejó fuera un campo que el propio '
            '_address_fields() devuelve')
        assert isinstance(registry['city_id'], NonStored)

    def test_every_address_field_is_in_the_registry(self, db):
        """La lista que ``_address_fields()`` publica es consultable entera.

        Es la invariante que ``_convert_fields_to_values`` necesita: recorre
        esa lista y consulta el registro por cada nombre.
        """
        registry = _company()._fields
        missing = [f for f in ResPartner._address_fields() if f not in registry]
        assert missing == [], f'campos de dirección fuera del registro: {missing}'


class TestTheOneToManyGuardSurvives:
    """El ensanchado no ablanda la guarda de ``_convert_fields_to_values``."""

    def test_a_reverse_relation_is_still_refused(self, db):
        with pytest.raises(AssertionError):
            _company()._convert_fields_to_values(['children'])

    def test_a_name_that_is_not_a_field_is_refused(self, db):
        """≙ el ``KeyError`` de ``self._fields[fname]`` en la fuente."""
        with pytest.raises(KeyError):
            _company()._convert_fields_to_values(['no_existe_este_campo'])

    def test_the_field_without_a_column_goes_through(self, db):
        who = _company()
        assert who._convert_fields_to_values(['city_id']) == {'city_id': None}


class TestWritingTheFieldWithoutAColumn:
    """``city_id`` se lee y se escribe siempre — allá es una columna."""

    def test_it_reads_none_without_a_related_row(self, db):
        assert _company().city_id is None

    def test_it_creates_the_related_row(self, db):
        who = _company()
        assert not AddressStructured.objects.filter(partner=who).exists()

        who.city_id = _city()

        assert who.city_id.name == 'Guadalajara'
        assert AddressStructured.objects.get(partner=who).city_id.name == \
            'Guadalajara'

    def test_it_overwrites_an_existing_related_row(self, db):
        who = _company()
        AddressStructured.objects.create(partner=who, street_name='Vallarta')

        who.city_id = _city('Zapopan')

        row = AddressStructured.objects.get(partner=who)
        assert row.city_id.name == 'Zapopan'
        assert row.street_name == 'Vallarta', (
            'la escritura de la ciudad pisó el resto de la fila RELATED')

    def test_the_address_values_carry_it(self, db):
        """El camino completo: ``_get_address_values`` lo incluye."""
        who = _company(city='Guadalajara')
        who.city_id = _city()
        assert who._get_address_values()['city_id'].name == 'Guadalajara'
