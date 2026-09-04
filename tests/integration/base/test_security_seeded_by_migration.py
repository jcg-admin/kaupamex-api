"""La ACL y las record rules las siembra una MIGRACIÓN, no el conftest.

≙ lo que la referencia carga al instalar un módulo: su
``security/ir.model.access.csv`` y su ``security/*.xml``
(``odoo19c: odoo/addons/base/security/``). Aquí no hay cargador de módulo, y
hasta la tarea #95 las dos siembras vivían **sólo** en ``tests/conftest.py``:
una base de producción recién migrada quedaba con las dos tablas vacías.

Por qué esto necesita casos y no basta la migración
====================================================

Una migración de datos se aplica **una vez** y ``django_migrations`` la da por
aplicada para siempre. Si alguien retira su ``RunPython``, o si el sembrador
deja de encontrar sus filas —un grupo renombrado, un modelo movido—, la base
nueva sale vacía y **nada lo dice**: la migración sigue en la lista.

Las dos tablas vacías no fallan igual, y es la mitad que hay que tener clara:

- **Sin ACL** ``IrModelAccess.check`` deniega todo. Fail-closed, ruidoso, se ve
  al primer clic.
- **Sin record rules** ``_compute_domain`` devuelve ``Q()`` —*modelo sin regla,
  sin restricción*, semántica de la fuente— y el aislamiento por fila
  simplemente **no existe**. Silencioso: todo funciona y cada empresa ve las
  filas de las demás.

Qué haría fallar a estos casos
==============================

Retirar cualquiera de las tres migraciones, o romper su sembrador. Un caso que
sólo comprobara *"la migración está en el árbol"* leería el archivo y no la
tabla — es el defecto que :ref:`h-api-876` registró en otro instrumento.

Medido sobre una base construida sólo con ``migrate``
======================================================

Con las tres migraciones desaplicadas y las dos tablas vaciadas,
``TRUNCATE ir_model_access, ir_rule CASCADE`` deja **0 | 0**; volver a correr
``migrate`` las aplica y deja **23 | 4**. La sonda corrió sobre una base
desechable (``kaupamex_seed_probe``), no sobre la de QA.
"""
import importlib

import pytest

from addons.base.models.ir_model import IrModelAccess
from addons.base.models.ir_rule import IrRule

pytestmark = pytest.mark.django_db


class TestTheAclIsThere:
    """Las 23 filas del CSV cuyo modelo existe en este árbol."""

    def test_the_acl_is_not_empty(self):
        assert IrModelAccess.objects.exists()

    def test_the_twenty_three_rows_are_there(self):
        assert IrModelAccess.objects.count() >= 23

    def test_the_global_row_grants_nothing_not_even_read(self):
        """``ir.model.access.csv:35`` — los cuatro permisos en cero.

        Existe y no concede nada; el renderizador de vistas lee bajo elevación.
        Un sembrador «arreglado» que le pusiera ``perm_read=True`` cambiaría la
        política disfrazado de corrección.
        """
        row = IrModelAccess.objects.filter(name='ir_ui_view group_user').first()
        assert row is not None
        assert (row.perm_read, row.perm_write, row.perm_create,
                row.perm_unlink) == (False, False, False, False)


class TestTheRecordRulesAreThere:
    """Las cuatro reglas multi-empresa, que son el aislamiento L3."""

    @pytest.mark.parametrize('name,model_name', [
        ('Company Setting multi-company', 'base.CompanySetting'),
        ('Sales Order multi-company', 'sale.SaleOrder'),
        ('Company Module Subscription multi-company',
         'sale_subscription.CompanyModuleSubscription'),
        ('Subscription Invoice multi-company',
         'sale_subscription.SubscriptionInvoice'),
    ])
    def test_the_rule_is_seeded_for_its_model(self, name, model_name):
        rule = IrRule.objects.filter(name=name).first()
        assert rule is not None
        assert rule.model_name == model_name

    def test_the_domain_is_the_one_of_the_source(self):
        """``[('company_id', 'in', company_ids)]`` verbatim.

        Qué haría fallar al caso: cambiarlo por ``company_id = company_id``.
        Con ``in`` y cero empresas activadas el dominio da ``IN []`` → cero
        filas, que es el fail-closed como dato; con ``=`` y ``None`` daría
        ``company_id IS NULL``, que devuelve las filas sin empresa a todo el
        mundo.
        """
        for rule in IrRule.objects.filter(name__endswith='multi-company'):
            assert rule.domain_force == "[('company_id', 'in', company_ids)]"

    def test_the_rules_are_global(self):
        """Sin grupos: restringen a todo el mundo, como en la fuente.

        ``account_security.xml`` no les declara grupos. Si los tuvieran, un
        usuario fuera de ese grupo no quedaría restringido — que es lo
        contrario del aislamiento.
        """
        for rule in IrRule.objects.filter(name__endswith='multi-company'):
            assert not rule.groups.exists()


class TestTheSeedersHaveTheTwoEntryPoints:
    """Una definición, dos entradas — el patrón de ``res_groups_data``.

    **Mide forma**, y lo dice. Su valor es que la forma es la que impide la
    divergencia: si el sembrador de la migración y el del conftest fueran dos
    cuerpos, arreglar uno dejaría el otro atrás y el fallo aparecería lejos.
    """

    @pytest.mark.parametrize('modulo,vivo,historico', [
        ('addons.base.security.ir_model_access', 'seed', 'seed_base_acl'),
        ('addons.base.security.base_security', 'seed', 'seed_base_rules'),
        ('addons.sale.security.ir_rules', 'seed', 'seed_sale_rules'),
        ('addons.sale_subscription.security.ir_rules', 'seed',
         'seed_subscription_rules'),
    ])
    def test_both_entry_points_exist(self, modulo, vivo, historico):
        module = importlib.import_module(modulo)
        assert callable(getattr(module, vivo))
        assert callable(getattr(module, historico))
