"""Tests — ``save()`` como el punto de entrada que SINCRONIZA.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/res_partner.py``:
``create`` (``:926-948``), ``write`` (``:856-924``) y ``_clean_website``
(``:843-849``). La referencia parte en dos lo que Django unifica; aquí los dos
caminos viven en ``save()`` y se distinguen por ``_state.adding``.

Por qué este archivo existe aparte
===================================

``test_res_partner_sync.py`` mide cada método del bloque **llamándolo a
mano**. Éste mide que **alguien los llame**: hasta este porte ``_fields_sync``
existía sin llamador, que es la forma que :ref:`h-api-836` registró —un
símbolo portado, correcto y que nadie invoca—. Un test que sólo llama al
método directamente no puede ver esa ausencia.

Qué haría fallar a cada control
--------------------------------

``TestWiring.test_creating_a_contact_takes_the_company_address``
    El eje. Lo haría fallar retirar la llamada a ``_fields_sync`` de
    ``save()`` — el defecto que este archivo existe para detectar.

``TestSkipFlag.test_inside_the_scope_nothing_is_synced``
    CONTROL de la bandera: sin este caso el escape sería decorativo y nadie
    lo notaría, porque el resto de los casos no la usan.

``TestLoopGuard.test_saving_without_changes_does_not_pull_the_child_back``
    CONTROL del filtro «sólo lo que cambió». Sincronizar en cada ``save()``
    —cambie o no— es lo que la fuente evita por reentrada, y sin este caso
    quitar el filtro no rompería nada visible.
"""
import pytest

from addons.base.models.res_partner import ResPartner
from orm.environments import context_scope

pytestmark = pytest.mark.integration


class TestCleanWebsite:
    """≙ ``_clean_website`` — sin esquema no es un enlace, es una ruta."""

    def test_a_bare_domain_gets_the_scheme(self):
        assert ResPartner._clean_website('kaupamex.mx') == 'http://kaupamex.mx'

    def test_one_that_already_has_it_is_untouched(self):
        """CONTROL — anteponerlo dos veces produce basura."""
        assert ResPartner._clean_website(
            'https://kaupamex.mx/a') == 'https://kaupamex.mx/a'

    def test_empty_stays_empty(self):
        assert ResPartner._clean_website('') == ''

    def test_it_runs_on_save(self, db):
        who = ResPartner.objects.create(name='Con web',
                                        website='kaupamex.mx')
        who.refresh_from_db()
        assert who.website == 'http://kaupamex.mx'


class TestCompanyName:
    """El ``company_name`` se borra al fijar un padre — ≙ la línea de la fuente
    en ``create`` y en ``write``.

    Es la razón social escrita a mano de un contacto **suelto**. Con padre, la
    da la entidad comercial; tener las dos es tener dos verdades.
    """

    def test_setting_a_parent_clears_it(self, db):
        company = ResPartner.objects.create(name='Kaupamex SA',
                                            is_company=True)
        who = ResPartner.objects.create(name='Ana',
                                        company_name='Escrita a mano')
        assert who.company_name == 'Escrita a mano'
        who.parent = company
        who.save()
        who.refresh_from_db()
        assert not who.company_name

    def test_without_a_parent_it_survives(self, db):
        """CONTROL — el borrado es por el padre, no por guardar."""
        who = ResPartner.objects.create(name='Ana',
                                        company_name='Escrita a mano')
        who.save()
        who.refresh_from_db()
        assert who.company_name == 'Escrita a mano'


class TestWiring:
    """``save()`` llama a ``_fields_sync`` — la ausencia que este porte cierra."""

    def test_creating_a_contact_takes_the_company_address(self, db):
        company = ResPartner.objects.create(
            name='Kaupamex SA', is_company=True,
            street='Av. Vallarta 1300', city='Guadalajara')
        who = ResPartner.objects.create(
            name='Ana', parent=company, type=ResPartner.TYPE_CONTACT)
        who.refresh_from_db()
        assert who.city == 'Guadalajara'

    def test_creating_a_contact_takes_the_company_rfc(self, db):
        company = ResPartner.objects.create(
            name='Kaupamex SA', is_company=True, vat='KAU010101AAA')
        who = ResPartner.objects.create(
            name='Ana', parent=company, type=ResPartner.TYPE_CONTACT)
        who.refresh_from_db()
        assert who.vat == 'KAU010101AAA'

    def test_editing_the_company_address_reaches_its_contacts(self, db):
        company = ResPartner.objects.create(
            name='Kaupamex SA', is_company=True, city='Guadalajara')
        who = ResPartner.objects.create(
            name='Ana', parent=company, type=ResPartner.TYPE_CONTACT)
        company.city = 'Zapopan'
        company.save()
        who.refresh_from_db()
        assert who.city == 'Zapopan'

    def test_a_delivery_child_is_left_alone(self, db):
        """CONTROL — la frontera del tipo sigue en pie con el cableado."""
        company = ResPartner.objects.create(
            name='Kaupamex SA', is_company=True, city='Guadalajara')
        bodega = ResPartner.objects.create(
            name='Bodega', parent=company, type=ResPartner.TYPE_DELIVERY,
            city='Tlaquepaque')
        company.city = 'Zapopan'
        company.save()
        bodega.refresh_from_db()
        assert bodega.city == 'Tlaquepaque'


class TestSkipFlag:
    """≙ el contexto ``_partners_skip_fields_sync`` (``odoo19c: :942``)."""

    def test_inside_the_scope_nothing_is_synced(self, db):
        company = ResPartner.objects.create(
            name='Kaupamex SA', is_company=True, city='Guadalajara')
        with context_scope(_partners_skip_fields_sync=True):
            who = ResPartner.objects.create(
                name='Ana', parent=company, type=ResPartner.TYPE_CONTACT)
        who.refresh_from_db()
        assert not who.city, 'la bandera debe apagar la sincronizacion'

    def test_outside_it_syncs_again(self, db):
        """CONTROL — la bandera no deja residuo: fuera del bloque, sincroniza."""
        company = ResPartner.objects.create(
            name='Kaupamex SA', is_company=True, city='Guadalajara')
        with context_scope(_partners_skip_fields_sync=True):
            pass
        who = ResPartner.objects.create(
            name='Ana', parent=company, type=ResPartner.TYPE_CONTACT)
        who.refresh_from_db()
        assert who.city == 'Guadalajara'


class TestLoopGuard:
    """Sólo se sincroniza lo que de verdad cambió — ≙ el ``pre_values_list``.

    No es una optimización: el comentario de la fuente dice *"we should avoid
    infinite loops in case same value is updated due to cycles"*.
    """

    def test_saving_without_changes_does_not_pull_the_child_back(self, db):
        company = ResPartner.objects.create(
            name='Kaupamex SA', is_company=True, city='Guadalajara')
        who = ResPartner.objects.create(
            name='Ana', parent=company, type=ResPartner.TYPE_CONTACT)
        # El hijo diverge por una via que no pasa por save()
        ResPartner.objects.filter(pk=who.pk).update(city='Tlaquepaque')
        # Guardar la empresa sin tocar nada NO debe re-sincronizar
        company.save()
        who.refresh_from_db()
        assert who.city == 'Tlaquepaque'

    def test_but_a_real_change_does_reach_it(self, db):
        """CONTROL — el filtro no debe apagar la sincronizacion de verdad."""
        company = ResPartner.objects.create(
            name='Kaupamex SA', is_company=True, city='Guadalajara')
        who = ResPartner.objects.create(
            name='Ana', parent=company, type=ResPartner.TYPE_CONTACT)
        ResPartner.objects.filter(pk=who.pk).update(city='Tlaquepaque')
        company.city = 'Zapopan'
        company.save()
        who.refresh_from_db()
        assert who.city == 'Zapopan'
