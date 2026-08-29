"""``CheckCompanyMixin`` — la coherencia de empresa entre un registro y lo que apunta.

≙ ``BaseModel._check_company_auto`` / ``_check_company_domain`` /
``_check_company`` (``odoo19c: odoo/orm/models.py:451, 3997, 4009``) y sus dos
llamadas, desde ``write`` (``:4516``) y ``create`` (``:4744``).

Qué haría fallar a estos casos
==============================

La marca ``check_company=True`` es una palabra clave: sin el mecanismo que la
lee, se declara y no pasa nada. Por eso ningún caso se conforma con *"guardar
funciona"* — cada uno siembra un registro cuyo apuntado pertenece a **otra**
empresa y exige el rechazo, o siembra uno coherente y exige que pase. Los dos
lados hacen falta: sólo con el positivo, un mecanismo que rechazara siempre
también daría verde.

El caso que ancla todo es ``team_id``: la referencia lo marca
(``odoo19c: crm/models/crm_lead.py:112``) y aquí ``crm.team`` declara
``company_id``, así que hay con qué discriminar de verdad.

Medido con la guarda anulada
============================

Hay dos guardas y cada una tiene su control, porque anular una no mueve a la
otra:

**1. La llamada desde ``save``.** Sustituyendo el cuerpo de
``CheckCompanyMixin.save`` por un ``super().save()`` pelado, el módulo pasa de
**20 passed** a **2 failed, 18 passed**:

- ``test_saving_a_model_with_the_switch_on_runs_the_check``
- ``test_update_fields_reaches_the_check``

Sobrevive ``test_saving_a_model_with_the_switch_off_does_not``, y **es
correcto que sobreviva**: afirma una ausencia, y un enganche retirado la
produce igual. Ese caso no mide el enganche — mide el interruptor, y por eso
no discrimina aquí. Los demás llaman a ``_check_company`` directo, que es como
lo llaman ``write`` y ``create`` allá.

**2. El cuerpo de la verificación.** Anteponiendo un ``return`` a
``_check_company``, el módulo pasa de **20 passed** a **3 failed, 17 passed**:

- ``test_a_team_from_another_company_is_rejected``
- ``test_the_rejection_names_the_field``
- ``test_naming_the_company_field_reopens_the_whole_walk``

Sobreviven los dos positivos —pasan igual sin guarda, que es su trabajo—,
``test_update_fields_narrows_what_is_looked_at`` (también afirma silencio), y
los del predicado y la marca, que leen ``_meta`` y no escriben.

*Métrica:* casos de este módulo que caen al anular cada una de las dos guardas.
*Ciega a:* un modelo que sobrescriba ``save`` sin llamar a ``super()`` — ahí
la verificación no corre y ningún caso de aquí lo vería.
"""
import pytest

from django.apps import apps

from addons.base.models import ResCompany
from exceptions import UserError
from orm.models import (
    COMPANIES_FIELD_NAMES, COMPANY_FIELD_NAMES, CheckCompanyMixin,
    _company_ids, _first_field_name,
)

pytestmark = pytest.mark.django_db

CrmLead = apps.get_model('crm', 'CrmLead')
CrmTeam = apps.get_model('sales_team', 'CrmTeam')


@pytest.fixture
def two_companies():
    """Dos empresas distintas — el mínimo para que la pregunta tenga sentido."""
    return (ResCompany.objects.create(code='acme', name='ACME'),
            ResCompany.objects.create(code='globex', name='Globex'))


class TestTheSwitchTravelsOnTheCommonBase:
    """El mixin llega a todo modelo, apagado, como ``BaseModel`` allá."""

    def test_a_plain_model_inherits_the_mixin_switched_off(self):
        model = apps.get_model('product', 'ProductProduct')
        assert issubclass(model, CheckCompanyMixin)
        assert model._check_company_auto is False

    def test_a_model_that_declares_it_has_it_on(self):
        assert CrmLead._check_company_auto is True


class TestTheMarkLivesOnTheField:
    """``check_company=True`` sobrevive al constructor y llega a ``_meta``."""

    def test_the_marked_fields_are_the_ones_the_reference_marks(self):
        regular, dependent = CrmLead._check_company_fields()
        assert set(regular) == {'user_id', 'team_id', 'partner_id'}
        assert dependent == []

    def test_an_unmarked_field_is_not_collected(self):
        regular, _dependent = CrmLead._check_company_fields()
        assert 'company_id' not in regular

    def test_update_fields_narrows_the_walk(self):
        regular, _dependent = CrmLead._check_company_fields(['team_id'])
        assert regular == ['team_id']


class TestTheComodelPredicate:
    """``_check_company_domain`` — quién vale contra qué empresas."""

    def test_without_companies_only_the_shared_ones_pass(self, two_companies):
        acme, _globex = two_companies
        shared = CrmTeam.objects.create(name='Compartido', company_id=None)
        owned = CrmTeam.objects.create(name='De ACME', company_id=acme)
        got = set(CrmTeam.objects.filter(
            CrmTeam._check_company_domain(None)).values_list('pk', flat=True))
        assert got == {shared.pk}
        assert owned.pk not in got

    def test_with_a_company_its_own_and_the_shared_ones_pass(self, two_companies):
        acme, globex = two_companies
        shared = CrmTeam.objects.create(name='Compartido', company_id=None)
        mine = CrmTeam.objects.create(name='De ACME', company_id=acme)
        theirs = CrmTeam.objects.create(name='De Globex', company_id=globex)
        got = set(CrmTeam.objects.filter(
            CrmTeam._check_company_domain([acme])).values_list('pk', flat=True))
        assert got == {shared.pk, mine.pk}
        assert theirs.pk not in got

    def test_a_model_without_a_company_field_has_no_discriminator(self):
        model = apps.get_model('base', 'ResPartner')
        assert _first_field_name(model, COMPANY_FIELD_NAMES) is None
        assert model._check_company_domain(None) is None


class TestTheCheckItself:
    """``_check_company`` — el cuerpo que la marca existe para disparar.

    Se ejercita **directamente**, que es como lo llaman ``write`` (``:4516``)
    y ``create`` (``:4744``) en la fuente. Que ``save()`` lo invoque es otro
    eslabón y tiene su propio caso, abajo.
    """

    def test_a_team_from_the_same_company_is_silent(self, two_companies):
        acme, _globex = two_companies
        team = CrmTeam.objects.create(name='De ACME', company_id=acme)
        lead = CrmLead(name='Coherente', company_id=acme, team_id=team)
        lead._check_company()

    def test_a_shared_team_is_silent(self, two_companies):
        acme, _globex = two_companies
        team = CrmTeam.objects.create(name='Compartido', company_id=None)
        lead = CrmLead(name='Compartido', company_id=acme, team_id=team)
        lead._check_company()

    def test_a_team_from_another_company_is_rejected(self, two_companies):
        acme, globex = two_companies
        team = CrmTeam.objects.create(name='De Globex', company_id=globex)
        lead = CrmLead(name='Incoherente', company_id=acme, team_id=team)
        with pytest.raises(UserError):
            lead._check_company()

    def test_the_rejection_names_the_field(self, two_companies):
        acme, globex = two_companies
        team = CrmTeam.objects.create(name='De Globex', company_id=globex)
        lead = CrmLead(name='Incoherente', company_id=acme, team_id=team)
        with pytest.raises(UserError) as exc:
            lead._check_company()
        assert 'team_id' in str(exc.value)

    def test_update_fields_narrows_what_is_looked_at(self, two_companies):
        """Lo que no se escribió no se mira — ≙ ``_check_company(list(vals))``.

        Es el caso que distingue *"acota"* de *"no acota"*: el mismo estado
        incoherente pasa en silencio cuando ``fnames`` no nombra el campo.
        """
        acme, globex = two_companies
        team = CrmTeam.objects.create(name='De Globex', company_id=globex)
        lead = CrmLead(name='Incoherente', company_id=acme, team_id=team)
        lead._check_company(['name'])

    def test_naming_the_company_field_reopens_the_whole_walk(self, two_companies):
        """≙ ``if fnames is None or {'company_id','company_ids'} & set(fnames)``.

        Al cambiar de empresa, un valor que era coherente puede dejar de serlo
        sin que nadie lo toque; por eso nombrar la empresa reabre el recorrido
        entero en vez de acotarlo a ella.
        """
        acme, globex = two_companies
        team = CrmTeam.objects.create(name='De Globex', company_id=globex)
        lead = CrmLead(name='Incoherente', company_id=acme, team_id=team)
        with pytest.raises(UserError):
            lead._check_company(['company_id'])


class TestTheHookFromSave:
    """El eslabón que une el mecanismo con la escritura.

    ≙ las dos llamadas de la fuente, que van **después** de escribir. Aquí no
    se puede afirmar con un rechazo de punta a punta, y la razón está medida:
    de los seis modelos del árbol que hoy declaran ``_check_company_auto =
    True``, ninguno puede exhibir la incoherencia al guardar —``crm.lead``
    recalcula su empresa desde el equipo, ``certificate.certificate``
    recalcula el campo marcado desde el contenido, ``res.partner`` no declara
    empresa, y los cuatro asistentes de ``account`` no declaran ningún campo—.
    Eso es un hallazgo del porte, no de este mecanismo: ver H-API-897.

    Lo que sí se afirma es lo que hay que afirmar de un enganche: que corre,
    con qué argumento, y sólo cuando el interruptor está encendido.
    """

    def test_saving_a_model_with_the_switch_on_runs_the_check(
            self, two_companies, monkeypatch):
        acme, _globex = two_companies
        llamadas = []
        original = CheckCompanyMixin._check_company
        monkeypatch.setattr(
            CheckCompanyMixin, '_check_company',
            lambda self, fnames=None: (llamadas.append((type(self).__name__, fnames)),
                                       original(self, fnames))[1])
        team = CrmTeam.objects.create(name='De ACME', company_id=acme)
        CrmLead(name='Coherente', company_id=acme, team_id=team).save()
        assert ('CrmLead', None) in llamadas

    def test_saving_a_model_with_the_switch_off_does_not(self, monkeypatch):
        llamadas = []
        original = CheckCompanyMixin._check_company
        monkeypatch.setattr(
            CheckCompanyMixin, '_check_company',
            lambda self, fnames=None: (llamadas.append(type(self).__name__),
                                       original(self, fnames))[1])
        ResCompany.objects.create(code='sola', name='Sola')
        assert 'ResCompany' not in llamadas

    def test_update_fields_reaches_the_check(self, two_companies, monkeypatch):
        acme, _globex = two_companies
        llamadas = []
        original = CheckCompanyMixin._check_company
        monkeypatch.setattr(
            CheckCompanyMixin, '_check_company',
            lambda self, fnames=None: (llamadas.append(fnames),
                                       original(self, fnames))[1])
        team = CrmTeam.objects.create(name='De ACME', company_id=acme)
        lead = CrmLead(name='Coherente', company_id=acme, team_id=team)
        lead.save()
        llamadas.clear()
        lead.name = 'Renombrada'
        lead.save(update_fields=['name'])
        assert ['name'] in llamadas


class TestTheCompanyNormalisation:
    """``_company_ids`` — ≙ ``to_record_ids`` (``odoo19c: models.py:159``)."""

    def test_an_instance_a_list_and_a_queryset_give_the_same(self, two_companies):
        acme, _globex = two_companies
        esperado = [acme.pk]
        assert _company_ids(acme) == esperado
        assert _company_ids([acme]) == esperado
        assert _company_ids(ResCompany.objects.filter(pk=acme.pk)) == esperado

    def test_none_and_the_empty_list_give_nothing(self):
        assert _company_ids(None) == []
        assert _company_ids([]) == []

    def test_the_plural_names_are_the_ones_res_users_uses(self):
        model = apps.get_model('base', 'ResUsers')
        assert _first_field_name(model, COMPANIES_FIELD_NAMES) == 'company_ids'
