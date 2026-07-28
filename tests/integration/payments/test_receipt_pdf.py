"""
Tests — Generar Recibo de Compra en PDF (UC-PAY-10).

Cubre los criterios de aceptación AC-01..AC-04 del contrato:
- AC-01: orden pagada del dueño → 200 application/pdf, cuerpo abre con %PDF.
- AC-02: orden no pagada → 409 ORDER_NOT_PAID, sin PDF.
- AC-03: sin JWT → 401; autenticado sin permiso → 403 FORBIDDEN.
- AC-04: order_number inexistente → 404 NOT_FOUND.

Adicional:
- admin (is_staff) puede descargar el recibo de una orden ajena (Alternativa A).
- la auditoría RECEIPT_PDF_GENERATED queda registrada (POST-02 / AC-06).
- totales del PDF derivan de OrderValue (AC-05, vía payload del helper).

El helper C (tools/pdf/pdf_receipt) debe estar compilado en el entorno
(ADR-017): el provisioner server lo construye con `make`. Estos tests lo
ejercen end-to-end vía subprocess.
"""
import pytest
from tests.factories.user_factory import make_buyer
from decimal import Decimal

from django.contrib.auth import get_user_model

from addons.catalogue.models import Category, Product
from addons.delivery.models.sale_order import set_delivery_line
from addons.orders.models import Order, OrderItem, OrderValue, OrderAddress
from addons.sale.models import SaleOrderLine
from addons.payment.models import Payment
from addons.payments.pdf_receipt import HELPER_PATH, build_receipt_payload
from addons.base.models import SiteSettings
from addons.users.models import BusinessEvent
from tests.factories.order_factory import make_order
from addons.orders.status_projection import (
    STATUS_PAID,
    STATUS_PENDING,
)

pytestmark = pytest.mark.integration

RECEIPT_URL = lambda o: f'/api/v2/payments/{o}/receipt/'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def buyer(db):
    User = get_user_model()
    return make_buyer(User.objects.create_user(
        email='buyer-pay10@practicayoruba.mx',
        password='BuyerPass123!',
    ))


@pytest.fixture
def other_user(db):
    User = get_user_model()
    return make_buyer(User.objects.create_user(
        email='other-pay10@practicayoruba.mx',
        password='OtherPass123!',
    ))


def _make_paid_order(user, *, status=STATUS_PAID, with_payment=True):
    """Orden con snapshots financieros + (opcional) Payment aprobado."""
    # E5-pre: el recibo lee del canónico, así que la venta debe traer sus
    # líneas. Fabricar sólo el espejo producía un recibo en ceros — misma
    # clase de estado imposible que H-API-33 (una venta confirmada sin
    # líneas es lo que ``action_confirm`` rechaza).
    cat = Category.objects.create(
        name='Cat R', slug=f'cat-r-{user.pk}', is_active=True)
    p1 = Product.objects.create(
        name='Collar Eleguá', slug=f'collar-{user.pk}', sku='YOR-001',
        price=Decimal('450.00'), stock=9, is_active=True, is_published=True)
    p2 = Product.objects.create(
        name='Otá de Yemayá', slug=f'ota-{user.pk}', sku='YOR-002',
        price=Decimal('150.00'), stock=9, is_active=True, is_published=True)
    p1.categories.add(cat)
    p2.categories.add(cat)

    order = make_order(user=user, status=status,
                       product=p1, quantity=2, unit_price=Decimal('450.00'))
    SaleOrderLine.objects.create(
        order=order.sale_order, product=p2, name='Otá de Yemayá',
        product_uom_qty=1, price_unit=Decimal('150.00'))
    set_delivery_line(order.sale_order, Decimal('99.00'))

    OrderItem.objects.create(
        order=order, product_name='Collar Eleguá', sku='YOR-001',
        unit_price=Decimal('450.00'), quantity=2,
        subtotal=Decimal('900.00'),
    )
    OrderItem.objects.create(
        order=order, product_name='Otá de Yemayá', sku='YOR-002',
        unit_price=Decimal('150.00'), quantity=1,
        subtotal=Decimal('150.00'),
    )
    OrderValue.objects.create(
        order=order, subtotal=Decimal('1050.00'),
        tax=Decimal('144.83'), shipping_cost=Decimal('99.00'),
        discount=Decimal('0.00'), total=Decimal('1149.00'),
    )
    OrderAddress.objects.create(
        order=order, recipient_name='Juan Pérez',
        street='Av. Reforma 100', city='CDMX',
        state='Ciudad de México', zip_code='06600', country='MX',
    )
    if with_payment:
        Payment.objects.create(
            order=order, sale_order=order.sale_order, gateway=Payment.GATEWAY_MERCADOPAGO,
            preference_id=f'PREF-PAY10-{order.pk}',
            gateway_payment_id=f'GW-PAY10-{order.pk}',
            status=Payment.STATUS_APPROVED, amount=Decimal('1149.00'),
        )
    return order


# ---------------------------------------------------------------------------
# AC-01 — orden pagada del dueño → 200 application/pdf con %PDF
# ---------------------------------------------------------------------------

def test_ac01_owner_paid_order_returns_pdf(api_client, buyer):
    api_client.force_authenticate(user=buyer)
    order = _make_paid_order(buyer)

    resp = api_client.get(RECEIPT_URL(order.order_number))

    assert resp.status_code == 200, resp.content[:300]
    assert resp['Content-Type'] == 'application/pdf'
    assert resp['Content-Disposition'] == (
        f'attachment; filename="recibo-{order.order_number}.pdf"'
    )
    body = b''.join(resp.streaming_content) if resp.streaming else resp.content
    assert body.startswith(b'%PDF'), body[:40]
    assert len(body) > 200  # documento real, no placeholder vacío


def test_ac01_audit_event_recorded(
    api_client, buyer, django_capture_on_commit_callbacks,
):
    """AC-06 / POST-02: queda registro RECEIPT_PDF_GENERATED.

    audit_log_business emite el BusinessEvent vía transaction.on_commit
    (DEC-CC-2); en el atomic-rollback default del test los callbacks no
    disparan, así que se capturan/ejecutan explícitamente.
    """
    api_client.force_authenticate(user=buyer)
    order = _make_paid_order(buyer)

    with django_capture_on_commit_callbacks(execute=True):
        resp = api_client.get(RECEIPT_URL(order.order_number))
    assert resp.status_code == 200

    ev = BusinessEvent.objects.filter(
        action=BusinessEvent.ACTION_RECEIPT_PDF_GENERATED,
        target_type=BusinessEvent.TARGET_ORDER,
        target_id=order.pk,
    ).first()
    assert ev is not None
    assert ev.actor_id == buyer.pk
    assert ev.extra_json.get('order_number') == order.order_number


# ---------------------------------------------------------------------------
# AC-02 — orden no pagada → 409 ORDER_NOT_PAID
# ---------------------------------------------------------------------------

def test_ac02_unpaid_order_returns_409(api_client, buyer):
    api_client.force_authenticate(user=buyer)
    order = _make_paid_order(
        buyer, status=STATUS_PENDING, with_payment=False,
    )

    resp = api_client.get(RECEIPT_URL(order.order_number))

    assert resp.status_code == 409
    assert resp.json()['codigo_error'] == 'ORDER_NOT_PAID'
    # No se generó auditoría de recibo.
    assert not BusinessEvent.objects.filter(
        action=BusinessEvent.ACTION_RECEIPT_PDF_GENERATED,
        target_id=order.pk,
    ).exists()


# ---------------------------------------------------------------------------
# AC-03 — sin JWT → 401 ; autenticado sin permiso → 403 FORBIDDEN
# ---------------------------------------------------------------------------

def test_ac03_anonymous_returns_401(api_client, buyer):
    order = _make_paid_order(buyer)
    resp = api_client.get(RECEIPT_URL(order.order_number))
    assert resp.status_code == 401


def test_ac03_non_owner_returns_403(api_client, buyer, other_user):
    order = _make_paid_order(buyer)
    api_client.force_authenticate(user=other_user)

    resp = api_client.get(RECEIPT_URL(order.order_number))

    assert resp.status_code == 403
    assert resp.json()['codigo_error'] == 'FORBIDDEN'


def test_admin_can_download_other_users_receipt(api_client, buyer, admin_user):
    """Alternativa A: admin (is_staff) descarga recibo de orden ajena."""
    order = _make_paid_order(buyer)
    api_client.force_authenticate(user=admin_user)

    resp = api_client.get(RECEIPT_URL(order.order_number))

    assert resp.status_code == 200
    body = b''.join(resp.streaming_content) if resp.streaming else resp.content
    assert body.startswith(b'%PDF')


# ---------------------------------------------------------------------------
# AC-04 — order_number inexistente → 404 NOT_FOUND
# ---------------------------------------------------------------------------

def test_ac04_missing_order_returns_404(api_client, buyer):
    api_client.force_authenticate(user=buyer)

    resp = api_client.get(RECEIPT_URL('PY-NOEXIST'))

    assert resp.status_code == 404
    assert resp.json()['codigo_error'] == 'NOT_FOUND'


# ---------------------------------------------------------------------------
# AC-05 — totales del PDF derivan de OrderValue (vía payload del helper)
# ---------------------------------------------------------------------------

def test_ac05_payload_totals_match_order_value(db, buyer):
    order = _make_paid_order(buyer)
    value = order.value
    items = list(order.items.all())
    address = order.address
    payment = order.payments.first()
    site = SiteSettings.get_current()

    payload = build_receipt_payload(
        order=order, value=value, items=items,
        address=address, payment=payment, site=site,
    )

    # E5-pre — los importes salen del canónico. Cuatro de los cinco son
    # idénticos a los del espejo; el IVA diverge a propósito (H-API-41): el
    # espejo lo calculaba excluyendo el envío de la base gravable, el canónico
    # extrae el impuesto por línea, así que el flete también tributa. El total
    # que paga el comprador no cambia.
    assert payload['totals']['subtotal'] == '1050.00'
    assert payload['totals']['shipping'] == '99.00'
    assert payload['totals']['discount'] == '0.00'
    assert payload['totals']['total']    == '1149.00'
    assert payload['totals']['total']    == f'{value.total:.2f}'
    assert payload['totals']['tax'] == f'{order.sale_order.amount_tax:.2f}'
    assert Decimal(payload['totals']['tax']) > value.tax
    assert payload['order_number'] == order.order_number
    assert len(payload['items']) == 2
    assert payload['items'][0]['sku'] == 'YOR-001'
    assert payload['payment']['status']  # método/estado de pago presentes


def test_ac05_payload_sin_logo_degrada_a_vacio(db, buyer):
    # H-API-PAY10-01: sin logo el seam debe devolver logo_path vacío
    # (el helper lo trata como "sin logo").
    order = _make_paid_order(buyer)
    site = SiteSettings.get_current()
    assert not site.logo  # ImageField vacío por defecto

    payload = build_receipt_payload(
        order=order, value=order.value, items=list(order.items.all()),
        address=order.address, payment=order.payments.first(), site=site,
    )
    assert payload['issuer']['logo_path'] == ''


def test_ac05_payload_incluye_logo_path_cuando_hay_logo(db, buyer):
    # H-API-PAY10-01: si SiteSettings tiene logo, el seam debe pasar su
    # path absoluto en el payload (UC-PAY-10 AC-05). No es necesario
    # rasterizar — basta con que build_receipt_payload propague el path.
    order = _make_paid_order(buyer)
    site = SiteSettings.get_current()
    # Asociar un nombre de archivo al ImageField; .path resuelve contra
    # MEDIA_ROOT sin requerir un archivo físico en disco.
    site.logo.name = 'settings/logo/practicayoruba.png'

    payload = build_receipt_payload(
        order=order, value=order.value, items=list(order.items.all()),
        address=order.address, payment=order.payments.first(), site=site,
    )
    logo_path = payload['issuer']['logo_path']
    assert logo_path  # no vacío
    assert logo_path.endswith('settings/logo/practicayoruba.png')


# ---------------------------------------------------------------------------
# Sanity: el helper compilado existe en el entorno (ADR-017 gate)
# ---------------------------------------------------------------------------

def test_helper_binary_present():
    assert HELPER_PATH.exists(), (
        f'Helper PDF no compilado en {HELPER_PATH}. '
        f'Compilar con `make` en practicayoruba/tools/pdf/ (ADR-017).'
    )
