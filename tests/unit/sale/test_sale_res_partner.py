"""``sale`` sobre ``res.partner`` — ≙ ``odoo19c: sale/models/res_partner.py``.

Cuatro ejes, y cada uno existe porque su ausencia produce un fallo distinto:

1. **El puente usuario→partner.** ``SaleOrder.partner`` apunta a ``res.users``,
   no a ``res.partner`` (tarea #993), así que toda consulta de "los pedidos de
   este cliente" cruza ``partner__partner``. Escrita sin el puente **no falla
   ruidosamente**: compara la PK del partner contra la PK del usuario. Los
   casos del puente construyen la divergencia de PK en vez de confiar en que
   la secuencia la produzca — mismo criterio que la clave sobrecadena de
   :ref:`h-api-908`.
2. **La cadena con ``portal``.** ``sale`` escribe ``super()._can_edit_country()``
   allá; aquí lo recibe por ``overrides=``. El caso que lo discrimina es un
   partner **hijo y sin pedidos**: ``sale`` no tiene por qué negarle nada, y aun
   así ``can_edit_vat()`` es falso porque el eslabón de ``portal`` lo niega. Un
   override que ignorara ``previous()`` devolvería verdadero y el caso caería.
3. **La guarda de grupo.** ``group_sale_salesman`` no está sembrado en el árbol
   (tarea #157), así que el conteo sale 0 sin consultar. Los casos siembran el
   grupo a mano para ejercitar las dos ramas — sin eso, medirían la ausencia
   del grupo y no el conteo.
4. **La descendencia.** El conteo suma los pedidos del partner **y de sus
   hijos**, que es el ``child_of`` de la fuente.

*Métrica:* filas devueltas y valores calculados contra PostgreSQL real, con
partners, usuarios y pedidos sembrados por caso.
*Ciega a:* ``_compute_credit_to_invoice``, que está BLOQUEADO por
``credit_to_invoice`` (sucesor #116) y no se ejercita aquí.
"""
import pytest

from addons.base.models.ir_model import IrModelData
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers
from addons.sale.models.res_partner import (
    GROUP_SALE_SALESMAN,
    _get_sale_order_domain_count,
    _merge_application_statistics,
    apply_sale_partner_extensions,
    lifetime_value,
)
from addons.sale.models.sale_order import SaleOrder
from orm.environments import user_scope

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def extensions_applied():
    """Idempotente: ``ready()`` ya las aplicó, re-aplicarlas es un no-op."""
    apply_sale_partner_extensions()


@pytest.fixture
def salesman(db):
    """Un usuario en ``sales_team.group_sale_salesman``, sembrado a mano.

    El grupo NO está en el árbol (tarea #157). Sembrarlo aquí es lo que separa
    "el conteo devuelve 0 porque el usuario no vende" de "devuelve 0 porque el
    grupo no existe" — dos causas que la guarda fail-closed colapsa.
    """
    group = ResGroups.objects.create(name='Vendedor')
    IrModelData.set_xmlid(group, GROUP_SALE_SALESMAN)
    user = ResUsers.objects.create_user(login='vendedor@kaupamex.test')
    user.group_ids.add(group)
    return user


@pytest.fixture
def buyer(db):
    """Un cliente cuyo usuario tiene PK DISTINTA de la de su partner.

    La divergencia se construye, no se espera: ``ResPartner`` y ``ResUsers``
    tienen secuencias independientes, así que un árbol recién creado puede
    darles el mismo número. Si coincidieran, una consulta escrita sin el
    puente pasaría igual y el caso no mediría nada.
    """
    relleno = [ResPartner.objects.create(name=f'Relleno {i}') for i in range(3)]
    user = ResUsers.objects.create_user(login='cliente@kaupamex.test')
    assert user.pk != user.partner.pk, (
        'el caso exige PK distintas para discriminar el puente')
    assert relleno  # el relleno existe para separar las secuencias
    return user


def order_for(user, state=SaleOrder.STATE_SALE, **extra):
    return SaleOrder.objects.create(partner=user, state=state, **extra)


class TestTheUserPartnerBridge:
    """``sale_order_ids`` — el ``One2many`` que aquí no es directo."""

    def test_it_finds_the_order_of_the_partner_behind_the_user(self, buyer):
        order = order_for(buyer)
        assert list(buyer.partner.sale_order_ids) == [order]

    def test_it_does_not_find_the_order_of_another_partner(self, buyer, db):
        other = ResUsers.objects.create_user(login='otro@kaupamex.test')
        order_for(other)
        assert list(buyer.partner.sale_order_ids) == []

    def test_lifetime_value_only_counts_confirmed(self, buyer):
        """El carrito abandonado no es valor de vida — agregado propio del L0."""
        order_for(buyer, state=SaleOrder.STATE_SALE, amount_total='100.00')
        order_for(buyer, state=SaleOrder.STATE_DRAFT, amount_total='999.00')
        assert str(lifetime_value(buyer.partner)) == '100.00'


class TestTheGroupGuard:
    """≙ ``if not self.env.user.has_group(...)`` (``odoo19c: :24-26``)."""

    def test_without_the_group_the_count_is_zero(self, buyer, db):
        order_for(buyer)
        plain = ResUsers.objects.create_user(login='sinvender@kaupamex.test')
        with user_scope(plain.pk):
            assert buyer.partner.sale_order_count == 0

    def test_without_an_actor_the_count_is_zero(self, buyer):
        """Fail-closed: sin usuario en contexto no hay grupo que consultar."""
        order_for(buyer)
        assert buyer.partner.sale_order_count == 0

    def test_with_the_group_the_count_is_the_real_one(self, buyer, salesman):
        order_for(buyer)
        order_for(buyer)
        with user_scope(salesman.pk):
            assert buyer.partner.sale_order_count == 2


class TestTheDescendants:
    """≙ el ``child_of`` de ``_compute_sale_order_count`` (``:31``)."""

    def test_the_parent_counts_the_orders_of_its_child(self, salesman, db):
        parent = ResPartner.objects.create(name='Matriz SA', is_company=True)
        child = ResPartner.objects.create(name='Sucursal', parent=parent)
        child_user = ResUsers.objects.create_user(
            login='sucursal@kaupamex.test', partner=child)
        order_for(child_user)
        with user_scope(salesman.pk):
            assert parent.sale_order_count == 1

    def test_the_child_does_not_count_the_orders_of_its_parent(
        self, salesman, db,
    ):
        parent = ResPartner.objects.create(name='Matriz SA', is_company=True)
        child = ResPartner.objects.create(name='Sucursal', parent=parent)
        parent_user = ResUsers.objects.create_user(
            login='matriz@kaupamex.test', partner=parent)
        order_for(parent_user)
        with user_scope(salesman.pk):
            assert child.sale_order_count == 0

    def test_the_domain_hook_is_the_empty_filter(self, buyer):
        """≙ ``return []`` (``:19-21``): sin condiciones, ``filter`` lo ignora."""
        assert not _get_sale_order_domain_count(buyer.partner).children


class TestHasOrder:
    """≙ ``_has_order`` (``:54-65``): sólo ``sent`` y ``sale`` cuentan."""

    @pytest.mark.parametrize('state, expected', [
        (SaleOrder.STATE_DRAFT, True),
        (SaleOrder.STATE_SENT, False),
        (SaleOrder.STATE_SALE, False),
        (SaleOrder.STATE_CANCEL, True),
    ])
    def test_only_an_issued_order_blocks_the_country(
        self, buyer, state, expected,
    ):
        order_for(buyer, state=state)
        assert buyer.partner._can_edit_country() is expected


class TestTheChainWithPortal:
    """La mitad que ``sale`` NO decide: el eslabón de abajo."""

    def test_a_child_without_orders_still_cannot_edit_its_vat(self, db):
        """El caso que discrimina la cadena.

        ``sale`` no tiene motivo para negar —no hay pedido— así que un override
        que ignorara ``previous()`` devolvería ``True``. Es ``portal`` quien
        niega: sólo la entidad comercial edita el RFC.
        """
        parent = ResPartner.objects.create(name='Matriz SA', is_company=True)
        child = ResPartner.objects.create(name='Sucursal', parent=parent)
        assert child.can_edit_vat() is False

    def test_a_commercial_entity_without_orders_can_edit_its_vat(self, db):
        alone = ResPartner.objects.create(name='Suelto SA')
        assert alone.can_edit_vat() is True

    def test_an_order_of_a_child_blocks_the_vat_of_the_parent(self, db):
        """≙ ``partner_id child_of commercial_partner_id`` (``:79``)."""
        parent = ResPartner.objects.create(name='Matriz SA', is_company=True)
        child = ResPartner.objects.create(name='Sucursal', parent=parent)
        child_user = ResUsers.objects.create_user(
            login='hija@kaupamex.test', partner=child)
        order_for(child_user)
        assert parent.can_edit_vat() is False

    def test_the_invoice_address_also_blocks_the_country(self, buyer, db):
        """El dominio de la fuente es ``partner_invoice_id = self OR ...``."""
        billed = ResPartner.objects.create(name='Facturación SA')
        order_for(buyer, partner_invoice_id=billed)
        assert billed._can_edit_country() is False


class TestTheStatisticsHook:
    """≙ ``_compute_application_statistics_hook`` (``:44-52``)."""

    def test_it_contributes_the_count_of_a_partner_with_orders(
        self, buyer, salesman,
    ):
        order_for(buyer)
        partner = buyer.partner
        with user_scope(salesman.pk):
            contributed = ResPartner._compute_application_statistics_hook(
                [partner])
        assert contributed[partner.pk][0]['value'] == 1
        assert contributed[partner.pk][0]['iconClass'] == 'fa-usd'

    def test_a_partner_without_orders_contributes_nothing(
        self, buyer, salesman,
    ):
        partner = buyer.partner
        with user_scope(salesman.pk):
            contributed = ResPartner._compute_application_statistics_hook(
                [partner])
        assert partner.pk not in contributed

    def test_the_merge_adds_to_the_previous_link_instead_of_replacing(self):
        """``combine=``: la fuente hace ``append`` sobre lo que ``super`` trajo."""
        merged = _merge_application_statistics({1: ['nuevo']}, {1: ['previo']})
        assert merged == {1: ['previo', 'nuevo']}


class TestTheWarningColumn:
    """``sale_warn_msg`` — ``fields.Text`` que sí es columna (``:17``)."""

    def test_it_persists_across_a_reload(self, db):
        partner = ResPartner.objects.create(
            name='Moroso SA', sale_warn_msg='Cobrar por adelantado')
        partner.refresh_from_db()
        assert partner.sale_warn_msg == 'Cobrar por adelantado'
