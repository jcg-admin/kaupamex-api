"""Tests — la sincronización de campos entre un partner y su jerarquía.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_partner.py``:
``_convert_fields_to_values`` (``:653``), ``_get_address_values`` (``:669``),
``_update_address`` (``:677``), ``_get_commercial_values`` (``:702``),
``_get_synced_commercial_values`` (``:711``),
``_company_dependent_commercial_fields`` (``:720``),
``_commercial_sync_from_company`` (``:726``),
``_company_dependent_commercial_sync`` (``:737``),
``_commercial_sync_to_descendants`` (``:751``), ``_fields_sync`` (``:770``),
``_children_sync`` (``:816``) y ``_handle_first_contact_creation`` (``:829``).

Qué mecanismo es éste, y por qué no es un campo relacionado
============================================================

Una dirección es un partner **hijo**. Para que la dirección de facturación de
una empresa lleve la calle de la empresa, la fuente no usa un campo
relacionado: sincroniza **valores** en las tres direcciones de la jerarquía —
del padre al hijo, del hijo al padre y del padre a los nietos— con control
explícito de cuándo. Un campo relacionado no puede hacerlo porque el hijo
debe poder **divergir**: una bodega tiene su propia calle y no debe perderla
cuando alguien edita la empresa.

Las dos fronteras, que son lo que un porte ingenuo se salta
------------------------------------------------------------

- **La dirección baja sólo a los hijos de tipo contacto.** Una dirección de
  entrega es una dirección *distinta* a propósito; pisarla con la del padre
  destruye el dato que alguien capturó.
- **Los campos comerciales no cruzan otra empresa.** Una filial tiene su
  propio RFC; heredar el de la matriz es un error fiscal, no cosmético.

Qué haría fallar a cada control
--------------------------------

``TestAddressDownstream.test_a_delivery_child_keeps_its_own_address``
    CONTROL de la primera frontera. Un ``_children_sync`` que baje a todos
    los hijos pasa el caso del contacto y rompe éste.

``TestCommercialSync.test_it_does_not_cross_into_a_child_company``
    CONTROL de la segunda. Es la mitad que el recorrido ingenuo se salta.

``TestFirstContact.test_it_does_nothing_when_the_parent_already_has_one``
    CONTROL de la precondición: la heurística sólo actúa sobre una empresa
    **sin** dirección y con **un** solo hijo; sin este caso, el método podría
    pisar la dirección de cualquier empresa y los demás tests no lo verían.
"""
import pytest

from addons.base.models.res_partner import ResPartner

pytestmark = pytest.mark.integration


def _company(**extra):
    data = dict(name='Kaupamex SA', is_company=True)
    data.update(extra)
    return ResPartner.objects.create(**data)


def _contact(parent, **extra):
    data = dict(name='Ana', parent=parent, type=ResPartner.TYPE_CONTACT)
    data.update(extra)
    return ResPartner.objects.create(**data)


class TestConvertFieldsToValues:
    """≙ ``_convert_fields_to_values`` — el diccionario que se escribiría."""

    def test_it_returns_the_named_fields(self, db):
        who = _company(street='Av. Vallarta 1300', city='Guadalajara')
        assert who._convert_fields_to_values(['street', 'city']) == {
            'street': 'Av. Vallarta 1300', 'city': 'Guadalajara'}

    def test_a_reverse_relation_is_refused(self, db):
        """≙ el ``AssertionError`` de la fuente ante un ``one2many``.

        Qué lo haría fallar: aceptarlo. Sincronizar ``children`` copiaría la
        lista de hijos del padre al hijo, que es un ciclo, no una dirección.
        """
        who = _company()
        with pytest.raises(AssertionError):
            who._convert_fields_to_values(['children'])


class TestAddressValues:
    """≙ ``_get_address_values`` — vacío es vacío, no un dict de vacíos."""

    def test_without_any_address_field_it_is_empty(self, db):
        assert _company()._get_address_values() == {}

    def test_one_field_set_is_enough(self, db):
        vals = _company(city='Guadalajara')._get_address_values()
        assert vals['city'] == 'Guadalajara'
        assert set(vals) == set(ResPartner._address_fields())


class TestUpdateAddress:
    """≙ ``_update_address`` — filtra a los campos de dirección y no recursa."""

    def test_it_writes_only_the_address_keys(self, db):
        who = _company(name='Kaupamex SA')
        who._update_address({'city': 'Zapopan', 'name': 'OTRO'})
        who.refresh_from_db()
        assert who.city == 'Zapopan'
        assert who.name == 'Kaupamex SA', 'name no es campo de direccion'

    def test_the_instance_in_memory_also_sees_it(self, db):
        """La fuente escribe en la caché del registro; aquí, en el objeto."""
        who = _company()
        who._update_address({'city': 'Zapopan'})
        assert who.city == 'Zapopan', 'sin refresh_from_db de por medio'


class TestCommercialValues:
    """≙ ``_get_commercial_values`` — sólo los campos CON valor."""

    def test_an_unset_field_is_not_returned(self, db):
        assert _company()._get_commercial_values() == {}

    def test_a_set_field_is_returned(self, db):
        assert _company(vat='KAU010101AAA')._get_commercial_values() == {
            'vat': 'KAU010101AAA'}

    def test_the_synced_subset_behaves_the_same(self, db):
        assert _company(vat='KAU010101AAA')._get_synced_commercial_values() == {
            'vat': 'KAU010101AAA'}


class TestCompanyDependent:
    """≙ ``_company_dependent_commercial_fields`` — vacío en este stack."""

    def test_it_is_empty_because_the_attribute_does_not_exist_here(self, db):
        """Divergencia declarada: ningún campo de este árbol es
        ``company_dependent`` —el atributo no existe en ``src/fields.py``—, así
        que la lista es vacía y su sincronizador es un no-op. Los dos símbolos
        existen igual: son el punto de extensión del día que el atributo se
        construya."""
        assert _company()._company_dependent_commercial_fields() == []


class TestCommercialSync:
    """≙ ``_commercial_sync_from_company`` / ``_commercial_sync_to_descendants``."""

    def test_a_contact_takes_the_rfc_of_its_company(self, db):
        company = _company(vat='KAU010101AAA')
        who = _contact(company)
        who._commercial_sync_from_company()
        who.refresh_from_db()
        assert who.vat == 'KAU010101AAA'

    def test_a_grandchild_takes_it_too(self, db):
        company = _company(vat='KAU010101AAA')
        middle = _contact(company, name='Sucursal')
        deep = _contact(middle, name='Bodega')
        company._commercial_sync_to_descendants()
        deep.refresh_from_db()
        assert deep.vat == 'KAU010101AAA'

    def test_it_does_not_cross_into_a_child_company(self, db):
        """CONTROL — una filial tiene su propio RFC; heredarlo es un error
        fiscal, no cosmetico."""
        company = _company(vat='KAU010101AAA')
        filial = ResPartner.objects.create(
            name='Filial', parent=company, is_company=True)
        company._commercial_sync_to_descendants()
        filial.refresh_from_db()
        assert not filial.vat

    def test_a_company_does_not_sync_from_itself(self, db):
        """CONTROL — es entidad comercial: no hay de quién heredar."""
        company = _company(vat='KAU010101AAA')
        company._commercial_sync_from_company()
        company.refresh_from_db()
        assert company.vat == 'KAU010101AAA'


class TestAddressDownstream:
    """≙ ``_children_sync`` — la dirección baja, y sólo a los contactos."""

    def test_a_contact_child_takes_the_new_address(self, db):
        company = _company()
        who = _contact(company)
        company.city = 'Zapopan'
        company._children_sync({'city': 'Zapopan'})
        who.refresh_from_db()
        assert who.city == 'Zapopan'

    def test_a_delivery_child_keeps_its_own_address(self, db):
        """CONTROL de la frontera: una direccion de entrega es distinta a
        proposito, y pisarla destruye lo que alguien capturo."""
        company = _company()
        bodega = ResPartner.objects.create(
            name='Bodega', parent=company, type=ResPartner.TYPE_DELIVERY,
            city='Tlaquepaque')
        company._children_sync({'city': 'Zapopan'})
        bodega.refresh_from_db()
        assert bodega.city == 'Tlaquepaque'

    def test_without_children_it_does_nothing(self, db):
        _company()._children_sync({'city': 'Zapopan'})


class TestFieldsSync:
    """≙ ``_fields_sync`` — las tres direcciones del mecanismo."""

    def test_from_upstream_a_new_contact_takes_the_company_address(self, db):
        company = _company(street='Av. Vallarta 1300', city='Guadalajara')
        who = _contact(company)
        who._fields_sync({'parent': company})
        who.refresh_from_db()
        assert who.city == 'Guadalajara'

    def test_to_upstream_the_address_of_the_contact_reaches_the_company(self, db):
        """El sentido que sorprende: editar el contacto edita a la empresa.

        Es deliberado en la fuente — para un contacto ``type='contact'`` la
        dirección **es** la de su empresa, así que corregirla en cualquiera de
        los dos lados debe corregirla en ambos.
        """
        company = _company(city='Guadalajara')
        who = _contact(company, city='Zapopan')
        who._fields_sync({'city': 'Zapopan'})
        company.refresh_from_db()
        assert company.city == 'Zapopan'

    def test_a_delivery_child_does_not_push_up(self, db):
        """CONTROL — sólo el contacto comparte dirección con su empresa."""
        company = _company(city='Guadalajara')
        bodega = ResPartner.objects.create(
            name='Bodega', parent=company, type=ResPartner.TYPE_DELIVERY,
            city='Tlaquepaque')
        bodega._fields_sync({'city': 'Tlaquepaque'})
        company.refresh_from_db()
        assert company.city == 'Guadalajara'


class TestFirstContact:
    """≙ ``_handle_first_contact_creation`` — la heurística del primer contacto."""

    def test_the_first_contact_gives_its_address_to_the_company(self, db):
        company = _company()
        who = _contact(company, street='Av. Vallarta 1300',
                       city='Guadalajara')
        who._handle_first_contact_creation()
        company.refresh_from_db()
        assert company.city == 'Guadalajara'

    def test_it_does_nothing_when_the_parent_already_has_one(self, db):
        """CONTROL — sin este caso el método podría pisar cualquier empresa."""
        company = _company(city='Guadalajara')
        who = _contact(company, city='Zapopan')
        who._handle_first_contact_creation()
        company.refresh_from_db()
        assert company.city == 'Guadalajara'

    def test_it_does_nothing_when_it_is_not_the_only_child(self, db):
        """CONTROL — con dos hijos la suposición ya no se sostiene."""
        company = _company()
        _contact(company, name='Primero')
        segundo = _contact(company, name='Segundo', city='Zapopan')
        segundo._handle_first_contact_creation()
        company.refresh_from_db()
        assert not company.city
