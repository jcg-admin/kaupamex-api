"""Tests — E5 paso 1: el canónico lleva su propia bitácora (chatter).

Cierra la capacidad que el diff contra la referencia detectó ausente en
``sale.SaleOrder``: en Odoo la bitácora de la venta **no es una tabla lateral**,
es ``mail.thread`` + ``tracking=True`` sobre ``state``
(``odoo19x sale/models/sale_order.py:81``). El espejo ``orders.Order`` sí
heredaba ``MailThread`` (``orders/models.py:22``); la canónica no.

Lo que se fija aquí:

1. ``SaleOrder`` es un hilo: ``message_post`` / seguidores funcionan sobre él,
   con la identidad polimórfica correcta (``sale.SaleOrder``).
2. Cada transición de la máquina de estados **deja rastro**: ``action_confirm``,
   ``action_cancel`` y ``action_draft`` registran un ``mail.tracking.value``
   del campo ``state`` con su valor viejo y nuevo.
3. Una transición que **no cambia** el estado no ensucia el hilo — el
   ``action_draft`` sobre una orden ya en ``draft`` no registra nada.
4. El bloqueo (``action_lock``) rastrea ``locked``, no ``state``.

Por qué importa para el cut-over: si ``orders`` se retira sin esta capacidad en
la canónica, el proyecto pierde la bitácora de la venta. Es el mismo
acoplamiento invertido que ya corrigieron H-API-26 y H-API-32 — la capacidad
canónica viviendo en el espejo.
"""
from decimal import Decimal

import pytest

from addons.catalogue.models import Category, Product
from addons.mail.models import MailMessage, MailTrackingValue
from addons.sale.models import SaleOrder, SaleOrderLine

pytestmark = pytest.mark.django_db


def _tracking_de(order, field):
    """Los tracking values de ``field`` registrados en el hilo de ``order``."""
    return MailTrackingValue.objects.filter(
        message__model=order._mail_thread_res_model(),
        message__res_id=order.pk,
        field=field,
    ).order_by('id')


@pytest.fixture
def producto():
    cat = Category.objects.create(name='Cat E5p1', slug='cat-e5p1', is_active=True)
    prod = Product.objects.create(
        name='Prod E5p1', slug='prod-e5p1', sku='SKU-E5P1',
        price=Decimal('100.00'), stock=5, is_active=True, is_published=True)
    prod.categories.add(cat)
    return prod


@pytest.fixture
def orden(producto):
    order = SaleOrder.objects.create()
    SaleOrderLine.objects.create(
        order=order, product=producto, name='Línea E5p1',
        price_unit=Decimal('100.00'), product_uom_qty=1)
    return order


class TestElCanonicoEsUnHilo:

    def test_saleorder_hereda_mailthread(self, orden):
        assert hasattr(orden, 'message_post')
        assert hasattr(orden, 'message_subscribe')

    def test_la_identidad_polimorfica_es_la_del_canonico(self, orden):
        """El hilo se ancla a ``sale.SaleOrder``, no al espejo."""
        assert orden._mail_thread_res_model() == 'sale.SaleOrder'

    def test_publicar_en_el_hilo_crea_el_mensaje(self, orden):
        orden.message_post(body='nota interna')
        assert MailMessage.objects.filter(
            model='sale.SaleOrder', res_id=orden.pk, body='nota interna',
        ).exists()


class TestLasTransicionesDejanRastro:

    def test_confirmar_registra_draft_a_sale(self, orden):
        orden.action_confirm()

        tracks = _tracking_de(orden, 'state')
        assert tracks.count() == 1
        track = tracks.first()
        assert track.get_old_value() == SaleOrder.STATE_DRAFT
        assert track.get_new_value() == SaleOrder.STATE_SALE

    def test_cancelar_registra_sale_a_cancel(self, orden):
        orden.action_confirm()
        orden.action_cancel()

        tracks = list(_tracking_de(orden, 'state'))
        assert len(tracks) == 2
        assert tracks[-1].get_old_value() == SaleOrder.STATE_SALE
        assert tracks[-1].get_new_value() == SaleOrder.STATE_CANCEL

    def test_reabrir_registra_cancel_a_draft(self, orden):
        orden.action_confirm()
        orden.action_cancel()
        orden.action_draft()

        tracks = list(_tracking_de(orden, 'state'))
        assert len(tracks) == 3
        assert tracks[-1].get_old_value() == SaleOrder.STATE_CANCEL
        assert tracks[-1].get_new_value() == SaleOrder.STATE_DRAFT

    def test_bloquear_rastrea_locked_no_state(self, orden):
        orden.action_confirm()
        orden.action_lock()

        assert _tracking_de(orden, 'locked').count() == 1
        # confirmar dejó 1 rastro de state; bloquear no añade otro
        assert _tracking_de(orden, 'state').count() == 1


class TestNoSeEnsuciaElHilo:

    def test_una_transicion_que_no_cambia_nada_no_registra(self, orden):
        """``action_draft`` sobre una orden ya en draft es no-op."""
        orden.action_draft()
        assert _tracking_de(orden, 'state').count() == 0

    def test_confirmar_una_orden_cancelada_falla_sin_dejar_rastro(self, orden):
        orden.action_cancel()
        antes = _tracking_de(orden, 'state').count()

        with pytest.raises(Exception):
            orden.action_confirm()

        assert _tracking_de(orden, 'state').count() == antes

    def test_desbloquear_rastrea_el_regreso(self, orden):
        orden.action_lock()
        orden.action_unlock()

        tracks = list(_tracking_de(orden, 'locked'))
        assert len(tracks) == 2
        # Un ``field_type='boolean'`` se persiste en la columna entera, fiel a
        # ``mail.tracking.value`` de Odoo (no hay columna booleana propia).
        assert tracks[-1].get_old_value() == 1
        assert tracks[-1].get_new_value() == 0
