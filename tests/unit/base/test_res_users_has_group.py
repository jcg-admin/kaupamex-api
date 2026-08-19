"""``res.users`` — la familia ``has_group`` (≙ ``odoo19c: res_users.py:1034-1096``).

Tres métodos y un puente. Los métodos son ``has_groups`` (el ``group_spec`` con
``!``), ``has_group`` (guarda de acceso + el matiz de ``base.group_no_one``) y
``_has_group`` (la pertenencia cruda). El puente es que la fuente pregunta
``group_id in user.all_group_ids`` con ``all_group_ids = group_ids.all_implied_ids``
(``:447-449``), y aquí eso se lee desde el grupo como ``all_implied_by_ids`` —
la misma arista del mismo M2M, recorrida al revés.

Lo que estos tests fijan, y por qué cada cosa:

- **La implicación transitiva cuenta.** Si sólo se mirara ``group_ids``, un
  administrador no "sería" usuario interno y la mitad del árbol autorizaría de
  menos. Es la diferencia entre pertenencia declarada y pertenencia efectiva.
- **``!`` niega, y un spec de sólo negativos es verdadero.** No es un borde
  decorativo: ``"!base.group_system"`` significa "cualquiera que no sea
  administrador", y con la lectura contraria no designaría a nadie.
- **``base.group_no_one`` es falso siempre.** El XML de la referencia lo hace
  implicado por ``group_user``, así que sin el matiz de depuración —que este
  árbol no tiene, tarea #450— quedaría encendido para todo interno.
- **Un xmlid que no resuelve no otorga.** Fail-closed: el mecanismo nace sobre
  una tabla que hasta ayer estaba vacía, y "no encontrado" no puede leerse como
  "sí".

Los grupos sembrados (``0027_seed_base_groups``) se ejercitan aparte de los
grupos sintéticos: unos fijan el catálogo, los otros el álgebra.
"""
import pytest

from addons.base.models.ir_model import IrModelData
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_users import ResUsers
from exceptions import AccessError
from orm.environments import sudo, user_scope

pytestmark = [pytest.mark.unit]


def _group(xmlid, label, user_type=None):
    """Crea un grupo y le graba su identificador externo."""
    group = ResGroups.objects.create(name=label, user_type=user_type)
    IrModelData.set_xmlid(group, xmlid)
    return group


def _user(login):
    return ResUsers.objects.create_user(login=login, password='x')


@pytest.fixture
def chain(db):
    """``boss`` ⇒ ``lead`` ⇒ ``worker`` — tres eslabones, dos aristas.

    Réplica en miniatura de ``group_system ⇒ group_erp_manager ⇒ group_user``
    del XML de la referencia, que es la cadena que obliga a que la clausura sea
    transitiva y no sólo directa.
    """
    worker = _group('prueba.group_worker', 'Operario')
    lead = _group('prueba.group_lead', 'Mando')
    boss = _group('prueba.group_boss', 'Jefe')
    lead.implied_ids.add(worker)
    boss.implied_ids.add(lead)
    return boss, lead, worker


@pytest.mark.django_db
class TestRawMembership:
    """``_has_group`` — sin guarda y sin el matiz de depuración."""

    def test_direct_membership(self, chain):
        _, _, worker = chain
        user = _user('directo@kaupamex.test')
        user.group_ids.add(worker)
        assert user._has_group('prueba.group_worker') is True

    def test_membership_through_transitive_implication(self, chain):
        """El jefe es operario sin estar declarado en el grupo del operario.

        Es el caso que separa ``group_ids`` de ``all_group_ids`` en la fuente.
        """
        boss, _, _ = chain
        user = _user('jefe@kaupamex.test')
        user.group_ids.add(boss)
        assert user._has_group('prueba.group_lead') is True
        assert user._has_group('prueba.group_worker') is True

    def test_implication_does_not_run_upwards(self, chain):
        """Ser operario no hace jefe: la arista es dirigida."""
        _, _, worker = chain
        user = _user('operario@kaupamex.test')
        user.group_ids.add(worker)
        assert user._has_group('prueba.group_boss') is False

    def test_user_without_groups(self, chain):
        user = _user('huerfano@kaupamex.test')
        assert user._has_group('prueba.group_worker') is False

    def test_unknown_xmlid_grants_nothing(self, db):
        user = _user('nadie@kaupamex.test')
        assert user._has_group('prueba.group_que_no_existe') is False

    def test_xmlid_without_module_grants_nothing(self, db):
        """Sin ``modulo.`` no hay identificador: no hay módulo implícito."""
        user = _user('sinmodulo@kaupamex.test')
        assert user._has_group('group_worker') is False

    def test_xmlid_pointing_at_another_model_grants_nothing(self, db):
        """La tabla es genérica; un identificador puede designar cualquier cosa.

        Que resuelva no basta — tiene que resolver a un ``res.groups``.
        """
        target = _user('objetivo@kaupamex.test')
        IrModelData.set_xmlid(target, 'prueba.no_soy_un_grupo')
        user = _user('curioso@kaupamex.test')
        assert user._has_group('prueba.no_soy_un_grupo') is False

    def test_unsaved_user_grants_nothing(self, chain):
        """Un registro nuevo no tiene M2M que consultar."""
        assert ResUsers(login='enelaire@kaupamex.test')._has_group(
            'prueba.group_worker') is False


@pytest.mark.django_db
class TestGroupSpec:
    """``has_groups`` — la gramática del ``group_spec``."""

    def test_single_positive(self, chain):
        _, _, worker = chain
        user = _user('pos@kaupamex.test')
        user.group_ids.add(worker)
        assert user.has_groups('prueba.group_worker') is True

    def test_one_positive_is_enough(self, chain):
        _, _, worker = chain
        user = _user('alguno@kaupamex.test')
        user.group_ids.add(worker)
        assert user.has_groups(
            'prueba.group_boss,prueba.group_worker') is True

    def test_no_positive_matches(self, chain):
        user = _user('ninguno@kaupamex.test')
        assert user.has_groups(
            'prueba.group_boss,prueba.group_worker') is False

    def test_negative_wins_over_a_matching_positive(self, chain):
        """``!`` niega: pertenecer al negado invalida el spec entero."""
        boss, _, _ = chain
        user = _user('negado@kaupamex.test')
        user.group_ids.add(boss)
        assert user.has_groups(
            'prueba.group_worker,!prueba.group_boss') is False

    def test_negative_is_harmless_when_not_a_member(self, chain):
        _, _, worker = chain
        user = _user('limpio@kaupamex.test')
        user.group_ids.add(worker)
        assert user.has_groups(
            'prueba.group_worker,!prueba.group_boss') is True

    def test_only_negatives_that_miss_is_true(self, chain):
        """``return not positives`` de la fuente.

        ``"!X"`` designa "cualquiera que no sea X"; leerlo como falso lo
        dejaría sin designar a nadie.
        """
        user = _user('solonegativo@kaupamex.test')
        assert user.has_groups('!prueba.group_boss') is True

    def test_only_negatives_that_match_is_false(self, chain):
        boss, _, _ = chain
        user = _user('solonegativo2@kaupamex.test')
        user.group_ids.add(boss)
        assert user.has_groups('!prueba.group_boss') is False

    def test_lone_dot_is_false(self, db):
        """``'.'`` es el marcador de "ningún grupo satisface esto"."""
        user = _user('punto@kaupamex.test')
        assert user.has_groups('.') is False

    def test_blanks_around_the_comma_are_ignored(self, chain):
        """El ``strip()`` de la fuente es del token entero, antes del ``!``.

        Por eso tolera ``" a , !b "`` y **no** ``"! b"``: ahí el ``!`` se
        consume y queda un identificador con espacio, que no resuelve. Se fija
        el comportamiento de la fuente, no uno más indulgente.
        """
        _, _, worker = chain
        user = _user('espacios@kaupamex.test')
        user.group_ids.add(worker)
        assert user.has_groups(
            ' prueba.group_worker , !prueba.group_boss ') is True


@pytest.mark.django_db
class TestAccessGuard:
    """La guarda de ``has_group`` (``:1077-1080`` de la fuente).

    Su comentario dice para qué está: *"this prevents RPC calls from
    non-internal users to retrieve information about other users"*.
    """

    def test_no_actor_in_context_is_allowed(self, chain):
        """Cron, migraciones y tests: no hay RPC de la que protegerse.

        Es el cuarto estado que la referencia no tiene —allá ``env.user``
        siempre existe— y por eso la decisión se toma aquí y se declara.
        """
        _, _, worker = chain
        target = _user('objetivo@kaupamex.test')
        target.group_ids.add(worker)
        assert target.has_group('prueba.group_worker') is True

    def test_asking_about_oneself_is_allowed(self, chain):
        _, _, worker = chain
        user = _user('yo@kaupamex.test')
        user.group_ids.add(worker)
        with user_scope(user.pk):
            assert user.has_group('prueba.group_worker') is True

    def test_outsider_without_internal_group_is_refused(self, chain):
        """Sin ``base.group_user``, preguntar por otro es ``AccessError``."""
        _, _, worker = chain
        target = _user('victima@kaupamex.test')
        target.group_ids.add(worker)
        snooper = _user('fisgon@kaupamex.test')
        with user_scope(snooper.pk):
            with pytest.raises(AccessError):
                target.has_group('prueba.group_worker')

    def test_internal_outsider_may_ask(self, chain):
        """``base.group_user`` es el permiso; lo siembra la migración."""
        _, _, worker = chain
        target = _user('consultado@kaupamex.test')
        target.group_ids.add(worker)
        insider = _user('interno@kaupamex.test')
        insider.group_ids.add(IrModelData.ref('base.group_user'))
        with user_scope(insider.pk):
            assert target.has_group('prueba.group_worker') is True

    def test_sudo_bypasses_the_guard(self, chain):
        """``env.su`` de la fuente — aquí ``orm.environments.sudo()``."""
        _, _, worker = chain
        target = _user('elevado@kaupamex.test')
        target.group_ids.add(worker)
        snooper = _user('fisgon2@kaupamex.test')
        with user_scope(snooper.pk), sudo():
            assert target.has_group('prueba.group_worker') is True

    def test_the_guard_does_not_reach_the_raw_method(self, chain):
        """``_has_group`` no la lleva — la fuente tampoco se la pone."""
        _, _, worker = chain
        target = _user('crudo@kaupamex.test')
        target.group_ids.add(worker)
        snooper = _user('fisgon3@kaupamex.test')
        with user_scope(snooper.pk):
            assert target._has_group('prueba.group_worker') is True


@pytest.mark.django_db
class TestGroupNoOne:
    """``base.group_no_one`` sin modo desarrollador (tarea #450)."""

    def test_is_false_even_for_a_member(self, db):
        no_one = IrModelData.ref('base.group_no_one')
        user = _user('tecnico@kaupamex.test')
        user.group_ids.add(no_one)
        assert user.has_group('base.group_no_one') is False

    def test_the_raw_method_still_sees_it(self, db):
        """El matiz vive en ``has_group``; ``_has_group`` es la pertenencia."""
        no_one = IrModelData.ref('base.group_no_one')
        user = _user('tecnico2@kaupamex.test')
        user.group_ids.add(no_one)
        assert user._has_group('base.group_no_one') is True

    def test_every_internal_would_hold_it_by_implication(self, db):
        """El motivo de que el matiz importe, medido sobre lo sembrado.

        El XML de la referencia declara ``group_no_one.implied_by_ids =
        [group_user, group_system]``; sin el matiz, cualquier interno abriría
        las funciones técnicas.
        """
        user = _user('interno2@kaupamex.test')
        user.group_ids.add(IrModelData.ref('base.group_user'))
        assert user._has_group('base.group_no_one') is True
        assert user.has_group('base.group_no_one') is False

    def test_has_groups_inherits_the_nuance(self, db):
        user = _user('spec_no_one@kaupamex.test')
        user.group_ids.add(IrModelData.ref('base.group_no_one'))
        assert user.has_groups('base.group_no_one') is False


@pytest.mark.django_db
class TestSeededCatalog:
    """``0027_seed_base_groups`` — los 12 grupos del XML de la referencia."""

    #: ``base_groups.xml`` declara doce ``res.groups``; medido con
    #: ``grep -c 'model="res.groups"'`` sobre el archivo de la fuente.
    XMLIDS = (
        'base.group_erp_manager',
        'base.group_sanitize_override',
        'base.group_system',
        'base.group_user',
        'base.group_multi_company',
        'base.group_multi_currency',
        'base.group_no_one',
        'base.group_allow_export',
        'base.group_partner_manager',
        'base.group_portal',
        'base.group_public',
        'base.default_user_group',
    )

    @pytest.mark.parametrize('xmlid', XMLIDS)
    def test_the_group_resolves(self, db, xmlid):
        group = IrModelData.ref(xmlid)
        assert isinstance(group, ResGroups)

    def test_the_administrator_is_internal_by_implication(self, db):
        """``group_system ⇒ group_erp_manager ⇒ group_user``.

        La cadena del XML: sin ella, un administrador no pasaría la guarda de
        ``has_group`` ni ningún gate que exija ``base.group_user``.
        """
        admin = _user('admin@kaupamex.test')
        admin.group_ids.add(IrModelData.ref('base.group_system'))
        assert admin._has_group('base.group_erp_manager') is True
        assert admin._has_group('base.group_user') is True

    def test_the_three_user_types_carry_user_type(self, db):
        """El conjunto disjunto de la fuente, declarado en el registro.

        La referencia lo saca de tres xmlid fijos; aquí ``user_type`` lo lleva
        el propio grupo (ver el docstring de ``res_groups.py``).
        """
        expected = {
            'base.group_user': 'internal',
            'base.group_portal': 'portal',
            'base.group_public': 'public',
        }
        assert {x: IrModelData.ref(x).user_type
                for x in expected} == expected

    def test_group_user_keeps_its_api_key_duration(self, db):
        """``<field name="api_key_duration">90.0</field>`` del XML."""
        assert IrModelData.ref('base.group_user').api_key_duration == 90.0

    def test_both_privileges_are_wired(self, db):
        """``group_allow_export`` → Export, ``group_partner_manager`` → Contact."""
        assert IrModelData.ref(
            'base.group_allow_export').privilege.name == 'Export'
        assert IrModelData.ref(
            'base.group_partner_manager').privilege.name == 'Contact'
