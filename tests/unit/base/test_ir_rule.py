"""``ir.rule`` cableado — evaluador + combinación de dominios (tarea #31).

Contrato fiel a ``_compute_domain`` de la fuente (``odoo19c:
addons/base/models/ir_rule.py:141-173``):

- globales se combinan con **AND**; de grupo con **OR** entre sí; y ese OR,
  AND contra las globales;
- regla sin ``domain_force`` es VERDADERA (no restringe);
- regla de un grupo que el usuario no tiene se descarta;
- el ``domain_force`` almacenado se evalúa con ``tools.safe_eval`` contra
  ``eval_context`` (``user``/``company_ids``/``company_id``) y se traduce a
  ``Q`` con ``orm.domains.to_q``.

Y el punto de integración (``RuleScopedManager``): bajo ``su`` las reglas no
se evalúan (``odoo19c: odoo/orm/models.py:4114``); sin regla para el modelo
no hay restricción (el fail-closed multi-company es la regla sembrada
``[('company_id','in',company_ids)]``, no el manager).
"""
import pytest

from addons.base.models import ResCompany
from addons.base.models.ir_rule import IrRule
from addons.base.models.res_groups import ResGroups
from addons.sale_subscription.models import CompanyModuleSubscription
from orm.environments import company_scope, sudo
from django.core.exceptions import ValidationError

from tools.safe_eval import safe_eval

pytestmark = pytest.mark.django_db

MODEL = 'base.ResCompany'


def _rule(name, domain='', groups=()):
    rule = IrRule.objects.create(
        name=name, model_name=MODEL, domain_force=domain)
    if groups:
        rule.groups.set(groups)
    return rule


#: La QA reusada trae compañías sembradas (founder/system); los asserts se
#: acotan a las tres del fixture para no depender de ese estado.
_CODES = ('alfa', 'beta', 'gama')


def _visible(group_ids=()):
    q = IrRule._compute_domain(MODEL, mode='read', group_ids=group_ids)
    return set(ResCompany.objects.filter(code__in=_CODES).filter(q)
               .values_list('code', flat=True))


@pytest.fixture
def tres_companias(db):
    for code in ('alfa', 'beta', 'gama'):
        ResCompany.objects.create(code=code, name=code.title())


class TestComputeDomain:
    def test_sin_reglas_no_restringe(self, tres_companias):
        # Semántica Odoo: modelo sin regla → sin restricción.
        assert _visible() == {'alfa', 'beta', 'gama'}

    def test_regla_sin_dominio_es_verdadera(self, tres_companias):
        _rule('vacía')
        assert _visible() == {'alfa', 'beta', 'gama'}

    def test_globales_se_combinan_con_and(self, tres_companias):
        _rule('no gama', "[('code', '!=', 'gama')]")
        _rule('con a', "[('code', 'like', 'a')]")
        # like 'a' matchea las tres (alfa, beta, gama); el AND quita gama.
        assert _visible() == {'alfa', 'beta'}

    def test_grupos_se_combinan_con_or(self, tres_companias):
        g1 = ResGroups.objects.create(name='g1')
        g2 = ResGroups.objects.create(name='g2')
        _rule('solo alfa', "[('code', '=', 'alfa')]", groups=[g1])
        _rule('solo beta', "[('code', '=', 'beta')]", groups=[g2])
        assert _visible(group_ids=(g1.pk, g2.pk)) == {'alfa', 'beta'}

    def test_grupo_ajeno_se_descarta(self, tres_companias):
        g1 = ResGroups.objects.create(name='g1')
        ajeno = ResGroups.objects.create(name='ajeno')
        _rule('solo alfa', "[('code', '=', 'alfa')]", groups=[g1])
        _rule('solo beta', "[('code', '=', 'beta')]", groups=[ajeno])
        # La regla del grupo ajeno ni aporta ni restringe.
        assert _visible(group_ids=(g1.pk,)) == {'alfa'}

    def test_or_de_grupos_and_contra_globales(self, tres_companias):
        g1 = ResGroups.objects.create(name='g1')
        _rule('global no gama', "[('code', '!=', 'gama')]")
        _rule('grupo gama o alfa', "[('code', 'in', ['gama', 'alfa'])]",
              groups=[g1])
        # La global QUITA filas que ninguna regla de grupo puede devolver.
        assert _visible(group_ids=(g1.pk,)) == {'alfa'}

    def test_modo_invalido_revienta(self):
        with pytest.raises(ValueError):
            IrRule._get_rules(MODEL, mode='browse')


class TestBuildDomain:
    def test_evalua_contra_company_ids_del_contexto(self, tres_companias):
        alfa = ResCompany.objects.get(code='alfa')
        rule = _rule('mc', "[('id', 'in', company_ids)]")
        with company_scope(alfa.pk):
            q = rule._build_domain(IrRule._eval_context())
        assert set(ResCompany.objects.filter(q)) == {alfa}

    def test_leaf_verdadero_de_la_fuente(self, tres_companias):
        # ``[(1, '=', 1)]`` — el TRUE de ``base_security.xml``.
        rule = _rule('true', "[(1, '=', 1)]")
        q = rule._build_domain({})
        assert ResCompany.objects.filter(code__in=_CODES).filter(q).count() == 3

    def test_arbitrary_code_is_rejected_on_save(self):
        """El rechazo se adelantó al ``save``, que es donde la fuente lo pone.

        Antes este caso creaba la regla y comprobaba que ``_build_domain``
        reventaba **al evaluarla**. Ahora ni se guarda: ``_check_domain`` es el
        ``@api.constrains('active', 'domain_force', 'model_id')`` de la fuente
        (``odoo19c: ir_rule.py:64-73``), y una regla con dominio roto rompería
        toda consulta sobre su modelo — lejos de donde se escribió.
        """
        with pytest.raises(ValidationError):
            _rule('mala', "__import__('os').system('id')")

    def test_the_evaluator_still_rejects_it_unsaved(self):
        """La guarda de ``safe_eval`` no se movió: se le añadió una anterior.

        Qué haría fallar al caso: que ``_build_domain`` dejara de validar
        confiando en que ``_check_domain`` ya lo hizo. Una fila escrita por SQL
        crudo —una migración, una siembra— no pasa por el ``save``.

        La excepción es ``NameError``, no ``ValueError``: con el porte completo
        de ``safe_eval`` (tarea #140) la guarda que para esta expresión es
        ``assert_no_dunder_name`` —``__import__`` contiene ``__``—, que corre
        antes que la de opcodes. Se afirma la que se mide, no la union de las
        dos: la union no distinguiria cual de las dos guardas actua, que es
        justo lo que este caso existe para comprobar.
        """
        rule = IrRule(name='mala', model_name=MODEL,
                      domain_force="__import__('os').system('id')")
        with pytest.raises(NameError, match='forbidden name'):
            rule._build_domain({})

    def test_the_evaluator_blocks_traversal_to_the_class(self):
        with pytest.raises(NameError, match='forbidden name'):
            safe_eval("[('a', '=', user.__class__)]", {'user': object()})

    def test_a_plain_domain_over_the_same_context_still_evaluates(self):
        """Control positivo de los dos casos de arriba.

        Sin el, un verde no distingue «la guarda rechaza lo prohibido» de «el
        evaluador rechaza todo». Este dominio usa el MISMO nombre del contexto
        y si tiene que evaluarse.
        """
        assert safe_eval("[('company_id', 'in', company_ids)]",
                         {'company_ids': [1, 2]}) == [
            ('company_id', 'in', [1, 2])]


class TestRuleScopedManagerSemantica:
    def test_su_omite_las_reglas(self, tres_companias):
        # Sin compañías activadas la regla sembrada da IN [] → 0 filas…
        assert (CompanyModuleSubscription.scoped
                .for_current_company().count() == 0)
        # …y bajo su las reglas NO se evalúan (models.py:4114 de la fuente).
        with sudo():
            assert (CompanyModuleSubscription.scoped.for_current_company()
                    .count()
                    == CompanyModuleSubscription.objects.count())
