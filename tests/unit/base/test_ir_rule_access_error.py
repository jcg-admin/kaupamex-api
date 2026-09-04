"""``_make_access_error`` de ``ir.rule`` — el mensaje rico del rechazo por fila.

≙ ``odoo19c: addons/base/models/ir_rule.py:208-268``, más las cuatro piezas
que aquí se extraen de su cuerpo (``_may_see_the_detail``,
``_user_has_company``, ``_describe_record``, ``_suggested_companies``) y el
``_get_redirect_suggested_company`` que la fuente declara en ``BaseModel``
(``odoo19c: odoo/orm/models.py:5825-5839``).

Por qué el mensaje merece casos propios
=======================================

Es la diferencia entre un 403 opaco y uno accionable, y esa diferencia vive
**entera** en el texto: qué operación, sobre qué modelo, qué filas, qué reglas
y —el ramal que más cuesta— si el problema no es de permiso sino de **empresa
activa**. Un caso que sólo comprobara ``isinstance(err, AccessError)`` no
distinguiría este puerto del sustituto de tres líneas que reemplaza.

Qué haría fallar a estos casos
==============================

- Que ``_failing_rules`` juzgara las reglas de grupo **una a una** en vez de en
  bloque: la fuente dice *"local rules are OR-ed together, the entire group
  succeeds or fails"*, así que una de dos reglas de grupo que por sí sola no
  devuelve todas las filas **no** falla si su hermana las devuelve.
- Que la guarda de detalle se abriera: el ``display_name`` de una fila
  prohibida es información sobre esa fila.
- Que la caché de ``_compute_domain`` no se invalidara al escribir la regla:
  ahí el fallo no es una caché fría, es **acceso concedido a filas que la
  regla nueva prohíbe**. Tiene su caso, y es el más importante del módulo.

Medido con cada guarda anulada
==============================

**Sin el ``registry.clear_cache()`` de ``save``/``delete``**:
:class:`TestComputeDomainCacheInvalidation` pasa de **4 passed** a **3 failed,
1 passed**. Caen exactamente los tres que miden la invalidación; sobrevive
``test_the_key_separates_the_operations``, que mide la clave y no depende de
ella — y está bien que sobreviva: mide otra cosa.

**Sin la validación del dominio contra el modelo** —la segunda mitad de
``_check_domain``, el ``Domain(domain).validate(model)`` de la fuente—:
:class:`TestConstraints` pasa de **3 passed** a **1 failed, 2 passed**, y el
que cae es el del campo inexistente. Esa mitad **no era opcional**: medido,
``domains.to_q([('no_existe_este_campo', '=', 1)])`` devuelve
``(AND: ('no_existe_este_campo__in', [1]))`` sin quejarse, así que un
``_check_domain`` que sólo evaluara no vería el defecto que dice ver.

En los dos casos el cuerpo se restauró y ``git diff`` lo confirma.
"""
import pytest

from django.core.exceptions import ValidationError

from addons.base.models import ResCompany, ResPartner
from addons.base.models.ir_model import IrModel
from addons.base.models.ir_rule import IrRule, _company_of
from addons.base.models.res_users import ResUsers
from exceptions import AccessError
from orm.environments import sudo
from orm.models import AccessQuerySet

pytestmark = pytest.mark.django_db

MODEL = 'base.ResCompany'


@pytest.fixture
def companies(db):
    return [ResCompany.objects.create(code=code, name=code.title())
            for code in ('uno', 'dos', 'tres')]


def _user(login, **kwargs):
    """Un usuario con su partner: ``res.users`` delega en ``res.partner``."""
    return ResUsers.objects.create(
        login=login, partner=ResPartner.objects.create(name=login), **kwargs)


def _rule(name, domain='', groups=()):
    rule = IrRule.objects.create(
        name=name, model_name=MODEL, domain_force=domain)
    if groups:
        rule.groups.set(groups)
    return rule


def _all():
    return ResCompany.objects.filter(code__in=('uno', 'dos', 'tres'))


class TestFailingRules:
    """Qué reglas concretas fallan — la mitad de ``_get_failing`` que nombra."""

    def test_a_global_rule_that_filters_is_named(self, companies):
        rule = _rule('sólo uno', "[('code', '=', 'uno')]")
        assert IrRule._failing_rules(_all(), mode='read') == [rule]

    def test_a_global_rule_that_lets_everything_through_is_not(self, companies):
        _rule('todas', "[(1, '=', 1)]")
        assert IrRule._failing_rules(_all(), mode='read') == []

    def test_a_rule_without_domain_is_not_failing(self, companies):
        _rule('vacía')
        assert IrRule._failing_rules(_all(), mode='read') == []

    def test_two_global_rules_are_judged_one_by_one(self, companies):
        """*"global rules get AND-ed and can each fail"* — ``:83-85``."""
        una = _rule('sólo uno', "[('code', '=', 'uno')]")
        todas = _rule('todas', "[(1, '=', 1)]")
        fallan = IrRule._failing_rules(_all(), mode='read')
        assert una in fallan
        assert todas not in fallan


class TestMakeAccessError:
    """El mensaje, parte por parte."""

    def test_it_is_an_access_error(self, companies):
        _rule('sólo uno', "[('code', '=', 'uno')]")
        fallan = IrRule._get_failing(_all(), mode='read')
        assert isinstance(IrRule._make_access_error('read', fallan),
                          AccessError)

    @pytest.mark.parametrize('operation,verbo', [
        ('read', 'consultar'), ('write', 'modificar'),
        ('create', 'crear'), ('unlink', 'borrar'),
    ])
    def test_it_names_the_operation(self, companies, operation, verbo):
        """Los cuatro verbos, no sólo el que se probó primero.

        La fuente traduce los cuatro uno a uno (``:214-219``); un mapa al que
        le faltara una entrada reventaría con ``KeyError`` justo al denegar.
        """
        _rule('sólo uno', "[('code', '=', 'uno')]")
        fallan = IrRule._get_failing(_all(), mode='read')
        assert verbo in str(IrRule._make_access_error(operation, fallan))

    def test_it_names_the_model(self, companies):
        _rule('sólo uno', "[('code', '=', 'uno')]")
        fallan = IrRule._get_failing(_all(), mode='read')
        assert MODEL in str(IrRule._make_access_error('read', fallan))

    def test_it_prefers_the_description_of_ir_model(self, companies):
        """≙ ``self.env['ir.model']._get(model).name or model`` (``:214``)."""
        IrModel.objects.update_or_create(
            model=MODEL, defaults={'name': 'Empresa'})
        _rule('sólo uno', "[('code', '=', 'uno')]")
        fallan = IrRule._get_failing(_all(), mode='read')
        assert 'Empresa' in str(IrRule._make_access_error('read', fallan))

    def test_the_short_branch_does_not_list_the_rows(self, companies):
        """Sin ``base.group_no_one`` el mensaje NO nombra filas — ``:255-256``.

        Es fail-closed y no es cosmético: el ``display_name`` de una fila que
        el usuario no puede leer es información sobre esa fila. Aquí ese grupo
        nunca concede (``has_group`` lo devuelve ``False`` mientras no haya
        modo depuración — tarea #450), así que ésta es la rama que el árbol
        recorre siempre hoy.
        """
        _rule('sólo uno', "[('code', '=', 'uno')]")
        fallan = IrRule._get_failing(_all(), mode='read')
        mensaje = str(IrRule._make_access_error('read', fallan))
        assert 'Dos' not in mensaje
        assert 'sólo uno' not in mensaje

    def test_the_detailed_branch_lists_rows_and_rules(self, companies,
                                                      monkeypatch):
        """La otra rama — ``:258-262``.

        Se fuerza la guarda porque en este árbol ``base.group_no_one`` no
        concede nunca (#450), así que la rama es **inalcanzable por el camino
        normal**. Sin este caso, el código de la rama larga no se ejercitaría
        jamás y su primer uso real sería su primera ejecución.
        """
        rule = _rule('sólo uno', "[('code', '=', 'uno')]")
        monkeypatch.setattr(IrRule, '_may_see_the_detail',
                            staticmethod(lambda user: True))
        fallan = IrRule._get_failing(_all(), mode='read')
        mensaje = str(IrRule._make_access_error('read', fallan))
        assert 'Dos' in mensaje
        assert rule.name in mensaje
        assert 'Lo impiden estas reglas' in mensaje


class TestMaySeeTheDetail:
    """La guarda del detalle — ``:255``."""

    def test_no_user_cannot(self):
        assert IrRule._may_see_the_detail(None) is False

    def test_a_user_without_the_debug_group_cannot(self, db):
        user = _user('sin_debug')
        assert IrRule._may_see_the_detail(user) is False


class TestUserHasCompany:
    """``in self.env.user.company_ids`` — ``:239``."""

    def test_no_user_no_company(self, companies):
        assert IrRule._user_has_company(None, companies[0]) is False

    def test_a_user_of_the_company_has_it(self, companies):
        user = _user('de_uno')
        companies[0].user_ids.add(user)
        assert IrRule._user_has_company(user, companies[0]) is True

    def test_a_user_of_another_company_does_not(self, companies):
        user = _user('de_dos')
        companies[1].user_ids.add(user)
        assert IrRule._user_has_company(user, companies[0]) is False


class TestCompanyOf:
    """El nombre de la FK — ``company`` o ``company_id``."""

    def test_it_finds_the_short_name(self, companies):
        user = _user('con_empresa', company=companies[0])
        assert _company_of(user) == companies[0]

    def test_it_returns_none_when_there_is_no_company(self, companies):
        assert _company_of(companies[0]) is None


class TestRedirectSuggestedCompany:
    """``_get_redirect_suggested_company`` — ≙ ``odoo/orm/models.py:5825``."""

    def test_a_model_without_the_field_suggests_nothing(self, companies):
        assert _all()._get_redirect_suggested_company() == []

    def test_a_model_with_company_returns_its_companies(self, companies):
        for i, code in enumerate(('a', 'b')):
            _user(code, company=companies[i])
        qs = AccessQuerySet(ResUsers).filter(login__in=('a', 'b'))
        assert set(qs._get_redirect_suggested_company()) == set(companies[:2])

    def test_the_union_has_no_repeats(self, companies):
        """La fuente devuelve un recordset: la unión, no la lista con repes.

        Qué haría fallar al caso: acumular sin comprobar. El llamador decide
        por ``len(suggested) != 1``, así que dos filas de la misma empresa
        parecerían ambigüedad multi-empresa y el mensaje diría lo contrario de
        lo que pasa.
        """
        for code in ('a', 'b'):
            _user(code, company=companies[0])
        qs = AccessQuerySet(ResUsers).filter(login__in=('a', 'b'))
        assert qs._get_redirect_suggested_company() == [companies[0]]


class TestGetRulesUnderElevation:
    """``if self.env.su: return self.browse(())`` — ``:118-119``."""

    def test_elevation_sees_no_rules(self, companies):
        _rule('sólo uno', "[('code', '=', 'uno')]")
        assert list(IrRule._get_rules(MODEL, mode='read')) != []
        with sudo():
            assert list(IrRule._get_rules(MODEL, mode='read')) == []

    def test_an_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            IrRule._get_rules(MODEL, mode='browse')


class TestConstraints:
    """Los dos ``@api.constrains`` y el ``CHECK`` de la fuente."""

    def test_a_rule_on_the_rules_model_is_rejected(self, db):
        """``:58-62`` — sería recursiva: leer la regla exigiría leer la regla."""
        with pytest.raises(ValidationError):
            IrRule.objects.create(name='recursiva', model_name='ir.rule')

    def test_a_broken_domain_is_rejected_on_save(self, db):
        with pytest.raises(ValidationError):
            _rule('rota', "[('no_existe_este_campo', '=', 1)]")

    def test_an_inactive_rule_is_not_validated(self, db):
        """``if rule.active and rule.domain_force`` — ``:67``.

        Desactivar es la vía de la fuente para desarmar una regla sin borrarla;
        validarla igual la haría imposible de guardar.
        """
        rule = IrRule(name='rota pero apagada', model_name=MODEL,
                      domain_force="[('no_existe_este_campo', '=', 1)]",
                      active=False)
        rule.save()
        assert rule.pk is not None


class TestComputeDomainCacheInvalidation:
    """La caché de ``_compute_domain`` y quién la jubila.

    Es el caso más importante del módulo: una caché de reglas de registro que
    no se invalida **concede** acceso, no lo retrasa.
    """

    def test_creating_a_rule_takes_effect_immediately(self, companies):
        assert _all().filter(IrRule._compute_domain(MODEL)).count() == 3
        _rule('sólo uno', "[('code', '=', 'uno')]")
        assert _all().filter(IrRule._compute_domain(MODEL)).count() == 1

    def test_editing_a_rule_takes_effect_immediately(self, companies):
        rule = _rule('sólo uno', "[('code', '=', 'uno')]")
        assert _all().filter(IrRule._compute_domain(MODEL)).count() == 1
        rule.domain_force = "[('code', '=', 'dos')]"
        rule.save()
        assert set(_all().filter(IrRule._compute_domain(MODEL))
                   .values_list('code', flat=True)) == {'dos'}

    def test_deleting_a_rule_takes_effect_immediately(self, companies):
        rule = _rule('sólo uno', "[('code', '=', 'uno')]")
        assert _all().filter(IrRule._compute_domain(MODEL)).count() == 1
        rule.delete()
        assert _all().filter(IrRule._compute_domain(MODEL)).count() == 3

    def test_the_key_separates_the_operations(self, companies):
        """Dos modos distintos no comparten entrada.

        Qué haría fallar al caso: dejar ``mode`` fuera de la clave. Una regla
        de lectura restrictiva se aplicaría también a la escritura, o al revés
        — y el «al revés» concede.
        """
        IrRule.objects.create(
            name='sólo lectura', model_name=MODEL,
            domain_force="[('code', '=', 'uno')]",
            perm_write=False, perm_create=False, perm_unlink=False)
        assert _all().filter(IrRule._compute_domain(MODEL, 'read')).count() == 1
        assert _all().filter(IrRule._compute_domain(MODEL, 'write')).count() == 3


class TestTheUnderscoreIsBack:
    """Los cuatro que estaban promovidos a API pública (:ref:`h-api-581`).

    **Mide forma, no fondo**, y lo dice: comprueba qué símbolos declara la
    clase, no lo que hacen. Su valor es que el defecto que corrige es
    exactamente de forma — un método público que la fuente declara privado
    compromete a este puerto a sostener una firma que allá nunca se expuso.
    """

    @pytest.mark.parametrize('name', [
        '_get_rules', '_eval_context', '_compute_domain', '_get_failing',
        '_make_access_error', '_compute_domain_keys',
        '_compute_domain_context_values', '_build_domain',
    ])
    def test_the_private_name_is_the_one_declared(self, name):
        assert hasattr(IrRule, name)

    @pytest.mark.parametrize('name', [
        'get_rules', 'eval_context', 'compute_domain', 'get_failing',
        'build_domain',
    ])
    def test_the_public_name_is_gone(self, name):
        assert not hasattr(IrRule, name)

    @pytest.mark.parametrize('name', [
        '_name', '_description', '_order', '_MODES', '_allow_sudo_commands',
    ])
    def test_the_five_class_attributes_of_the_source(self, name):
        """``atributos-de-clase-de-modelo.md``: se portan TODOS los que declare."""
        assert name in IrRule.__dict__
