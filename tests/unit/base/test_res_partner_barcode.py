"""``res.partner.barcode`` y su guarda de unicidad — tarea #111.

Cierra el desbloqueo de ``_check_barcode_unicity``
(``odoo19c: addons/base/models/res_partner.py:647-651``) y del campo que lo
exigía (``:309``, ``company_dependent=True``).

El punto que estos casos protegen, y que una columna escalar NO puede dar:
**la unicidad es por empresa**. Dos contactos con el mismo código en empresas
distintas conviven; dos en la misma empresa, no.
"""
import pytest
from django.core.exceptions import ValidationError

from addons.base.models import ResCompany, ResPartner
from addons.base.wizard.base_partner_merge import PartnerMerge
from orm import registry
from orm.environments import company_scope


@pytest.fixture
def companies(db):
    return (ResCompany.objects.create(code='bc-uno', name='Barcode Uno'),
            ResCompany.objects.create(code='bc-dos', name='Barcode Dos'))


class TestFieldShape:
    """La cabecera del campo, contra la de la fuente."""

    def test_the_field_is_company_dependent(self):
        # odoo19c: res_partner.py:309 — company_dependent=True
        assert ResPartner._meta.get_field('barcode').company_dependent is True

    def test_the_help_is_the_one_from_the_reference(self):
        assert (ResPartner._meta.get_field('barcode').help_text
                == 'Use a barcode to identify this contact.')

    def test_the_column_is_jsonb(self):
        field = ResPartner._meta.get_field('barcode')
        assert field.get_internal_type() == 'JSONField'

    def test_the_guard_is_declared_with_the_reference_name(self):
        assert callable(ResPartner._check_barcode_unicity)


@pytest.mark.django_db
class TestUnicityGuard:
    """``_check_barcode_unicity`` — el mensaje y el alcance de la fuente."""

    def test_a_partner_without_a_barcode_passes(self):
        ResPartner.objects.create(name='Sin codigo')._check_barcode_unicity()

    def test_two_partners_in_the_same_company_collide(self, companies):
        first, _ = companies
        with company_scope(first.pk):
            uno = ResPartner(name='Uno')
            uno.barcode = 'DUPLICADO'
            uno.save()
            dos = ResPartner(name='Dos')
            dos.barcode = 'DUPLICADO'
            with pytest.raises(ValidationError) as exc:
                dos.save()
        assert 'Another partner already has this barcode' in str(exc.value)

    def test_two_partners_in_different_companies_do_not_collide(self, companies):
        """El caso que justifica ``company_dependent``: sin él esto fallaría."""
        first, second = companies
        with company_scope(first.pk):
            uno = ResPartner(name='Uno')
            uno.barcode = 'COMPARTIDO'
            uno.save()
        with company_scope(second.pk):
            dos = ResPartner(name='Dos')
            dos.barcode = 'COMPARTIDO'
            dos.save()          # no levanta
        with company_scope(first.pk):
            assert ResPartner.objects.get(pk=uno.pk).barcode == 'COMPARTIDO'
        with company_scope(second.pk):
            assert ResPartner.objects.get(pk=dos.pk).barcode == 'COMPARTIDO'

    def test_rewriting_its_own_barcode_does_not_collide_with_itself(
            self, companies):
        first, _ = companies
        with company_scope(first.pk):
            uno = ResPartner(name='Uno')
            uno.barcode = 'PROPIO'
            uno.save()
            uno.save()          # el exclude(pk) es lo que evita el falso positivo

    def test_the_guard_runs_on_save(self, companies):
        """El enganche: no basta con que el metodo exista, tiene que correr."""
        first, _ = companies
        with company_scope(first.pk):
            uno = ResPartner(name='Uno')
            uno.barcode = 'POR-SAVE'
            uno.save()
            dos = ResPartner(name='Dos')
            dos.barcode = 'POR-SAVE'
            with pytest.raises(ValidationError):
                dos.save()


@pytest.mark.django_db
class TestCompanyDependentCommercialFields:
    """El filtro de la fuente, ya no una lista vacia por construccion."""

    def test_it_filters_by_the_field_attribute(self):
        # odoo19c: :720-724 — filtra _commercial_fields() por company_dependent
        assert ResPartner._company_dependent_commercial_fields() == [
            fname for fname in ResPartner._commercial_fields()
            if getattr(ResPartner._meta.get_field(fname),
                       'company_dependent', False)
        ]

    def test_it_is_empty_today_because_of_the_data_not_the_mechanism(self):
        # ``barcode`` es dependiente de empresa pero NO es campo comercial;
        # ningun campo comercial lo es todavia.
        assert 'barcode' not in ResPartner._commercial_fields()
        assert ResPartner._company_dependent_commercial_fields() == []

    def test_the_sync_is_a_no_op_while_the_list_is_empty(self):
        partner = ResPartner.objects.create(name='Sin campos por empresa')
        assert partner._company_dependent_commercial_sync() is None


@pytest.mark.django_db
class TestMergeCarriesTheCompanyValues:
    """El tercer bloque ``company_dependent`` de la fusion (``:288-315``)."""

    def test_the_destination_inherits_the_companies_it_did_not_have(
            self, companies):
        first, second = companies
        with company_scope(first.pk):
            origen = ResPartner(name='Origen')
            origen.barcode = 'DEL-ORIGEN'
            origen.save()
            destino = ResPartner.objects.create(name='Destino')

        PartnerMerge._update_company_dependent_references(
            [origen], destino)

        destino.refresh_from_db()
        with company_scope(first.pk):
            assert destino.barcode == 'DEL-ORIGEN'

    def test_the_destination_keeps_its_own_value_where_it_had_one(
            self, companies):
        """El ``||`` da precedencia al operando derecho — el del destino."""
        first, _ = companies
        with company_scope(first.pk):
            origen = ResPartner(name='Origen')
            origen.barcode = 'DEL-ORIGEN'
            origen.save()
            destino = ResPartner(name='Destino')
            destino.barcode = 'DEL-DESTINO'
            destino.save()

        PartnerMerge._update_company_dependent_references(
            [origen], destino)

        destino.refresh_from_db()
        with company_scope(first.pk):
            assert destino.barcode == 'DEL-DESTINO'

    def test_without_sources_it_does_nothing(self, companies):
        destino = ResPartner.objects.create(name='Destino')
        assert (PartnerMerge
                ._update_company_dependent_references([], destino)) is None


class TestRegistryContainer:
    """``many2one_company_dependents`` — vacio por dato, no por construccion."""

    def test_it_returns_a_list(self):
        assert isinstance(
            registry.many2one_company_dependents('base.ResPartner'), list)

    def test_no_many2one_is_company_dependent_yet(self):
        # El despachador de Many2one existe desde #129; el vacio es de
        # dato: ningun campo de ``base`` lo declara todavia. Los 54 de la
        # referencia se cablean en la tarea #135.
        assert registry.many2one_company_dependents('base.ResPartner') == []
