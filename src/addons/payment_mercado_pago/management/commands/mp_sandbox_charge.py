"""
mp_sandbox_charge — cobro de humo contra MercadoPago **sandbox**.

Tokeniza una tarjeta de PRUEBA de MP (públicas y libres) vía la API
``card_tokens`` (equivalente headless de MP.js), crea una Order PENDING
desechable y llama al MISMO servicio de producción
``initiate_checkout_api_payment``. El resultado esperado se fuerza con el
nombre del titular (APRO/OTHE/CONT/CALL/FUND/SECU/EXPI/FORM).

On-demand, NUNCA corre en CI (hace red real + necesita credenciales de
prueba). Los datos desechables (orden + pago + usuario) se borran al
terminar salvo ``--keep``. El PaymentGateway NO se toca (es config): si
no hay uno activo, se siembra desde las credenciales de entorno.

No imprime secretos (solo ``****``+últimos 4 y el status de MP).

Uso:
  cd practicayoruba
  DJANGO_SETTINGS_MODULE=config.settings.testing \\
    python manage.py mp_sandbox_charge --status APRO --method master
  python manage.py mp_sandbox_charge --status FUND --method visa --amount 250.00
"""
import json
import urllib.request
import urllib.error
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from addons.orders.models import Order, OrderValue
from addons.payment.models import Payment
from addons.payments.services import initiate_checkout_api_payment
from addons.settings_app.models import PaymentGateway

# Tarjetas de PRUEBA oficiales de MP México (públicas, libres). El estado
# del pago se fuerza con el nombre del titular, no con la tarjeta.
TEST_CARDS = {
    'master':    {'number': '5474925432670366', 'cvv': '123',  'exp_mm': 11, 'exp_yy': 2030},
    'visa':      {'number': '4075595716483764', 'cvv': '123',  'exp_mm': 11, 'exp_yy': 2030},
    'debmaster': {'number': '5579053461482647', 'cvv': '1234', 'exp_mm': 11, 'exp_yy': 2030},
    'debvisa':   {'number': '4189141221267633', 'cvv': '123',  'exp_mm': 11, 'exp_yy': 2030},
}

# Nombres de titular que MP interpreta como resultado forzado.
STATUS_NAMES = {'APRO', 'OTHE', 'CONT', 'CALL', 'FUND', 'SECU', 'EXPI', 'FORM'}

# Qué status de MP se espera por cada nombre (para el reporte OK/DIFERENTE).
EXPECTED_MP_STATUS = {
    'APRO': 'approved',
    'CONT': 'in_process',
    'CALL': 'rejected',
    'FUND': 'rejected',
    'SECU': 'rejected',
    'EXPI': 'rejected',
    'FORM': 'rejected',
    'OTHE': 'rejected',
}

_CARD_TOKENS_URL = 'https://api.mercadopago.com/v1/card_tokens?public_key={pk}'
# El Orders API sandbox exige que el email del pagador termine en
# '@testuser.com' (H-ORD-08, verificado en T-202); en producción va el email
# real del comprador. Solo el smoke corre contra sandbox, así que el dominio
# de prueba vive aquí, no en el builder de producción.
_SANDBOX_EMAIL = 'mp-sandbox-charge@testuser.com'


def _get_active_gateway():
    """Devuelve el PaymentGateway MERCADOPAGO activo, o error accionable.

    Sembrar credenciales es trabajo de ``setup_mp_gateway``; aquí solo se
    cobra, así que exigimos que el gateway ya exista.
    """
    gw = PaymentGateway.objects.filter(
        gateway='MERCADOPAGO', is_active=True).first()
    if gw is None:
        raise CommandError(
            'No hay PaymentGateway MERCADOPAGO activo. '
            'Córrelo primero con: python manage.py setup_mp_gateway.')
    return gw


def tokenize_test_card(public_key, method, holder_name):
    """Tokeniza una tarjeta de prueba vía MP card_tokens. Devuelve el id."""
    card = TEST_CARDS[method]
    payload = {
        'card_number': card['number'],
        'security_code': card['cvv'],
        'expiration_month': card['exp_mm'],
        'expiration_year': card['exp_yy'],
        'cardholder': {'name': holder_name},
    }
    url = _CARD_TOKENS_URL.format(pk=public_key)
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read().decode())
    return body['id']


def run_sandbox_charge(status='APRO', method='master', amount='199.00',
                       keep=False):
    """Ejecuta un cobro sandbox y devuelve un dict con el resultado.

    Reutilizable por el pytest opt-in. Crea datos desechables y los borra
    salvo keep=True. NO toca el PaymentGateway (config).
    """
    status = status.upper()
    method = method.lower()
    if status not in STATUS_NAMES:
        raise CommandError(
            f'--status inválido: {status}. Usa uno de: '
            f'{", ".join(sorted(STATUS_NAMES))}.')
    if method not in TEST_CARDS:
        raise CommandError(
            f'--method inválido: {method}. Usa uno de: '
            f'{", ".join(sorted(TEST_CARDS))}.')

    gw = _get_active_gateway()
    public_key = gw.get_credentials().get('public_key', '')

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        email=_SANDBOX_EMAIL,
        defaults={'username': 'mp_sandbox_charge',
                  'first_name': 'Sandbox', 'last_name': 'Charge'})
    if getattr(user, 'mp_customer_id', None):
        user.mp_customer_id = ''
        user.save(update_fields=['mp_customer_id'])

    # order_number único por corrida (uuid): Order es SoftDeleteModel, así que
    # una orden "borrada" deja la fila viva y su order_number único colisionaría
    # con un contador. El sufijo aleatorio lo evita. 'MPSMOKE'(7)+12 = 19 <= 20.
    order_number = f'MPSMOKE{uuid.uuid4().hex[:12].upper()}'
    order = Order.objects.create(
        order_number=order_number, user=user,
        status=Order.STATUS_PENDING)
    OrderValue.objects.create(
        order=order, subtotal=Decimal(amount), tax=Decimal('0.00'),
        shipping_cost=Decimal('0.00'), discount=Decimal('0.00'),
        total=Decimal(amount))

    token = tokenize_test_card(public_key, method, status)
    payment, result = initiate_checkout_api_payment(
        order, token=token, installments=1,
        payment_method_id=method, payer_email=user.email)
    order.refresh_from_db()

    out = {
        'holder_status': status,
        'method': method,
        'mp_status': getattr(result, 'status', None),
        'mp_detail': getattr(result, 'status_detail',
                             getattr(result, 'detail', '')),
        'expected_mp_status': EXPECTED_MP_STATUS.get(status),
        'order_number': order.order_number,
        'order_status': order.status,
        'payment_id': getattr(payment, 'pk', None),
        'gateway_payment_id': getattr(payment, 'gateway_payment_id', None),
        'public_key_last4': public_key[-4:],
    }

    if not keep:
        # hard_delete: Order es SoftDeleteModel; su delete() dejaría la fila.
        for pay in Payment.objects.filter(order=order):
            (pay.hard_delete if hasattr(pay, 'hard_delete') else pay.delete)()
        order.hard_delete()  # OrderValue cascada real

    return out


class Command(BaseCommand):
    help = 'Cobro de humo contra MercadoPago sandbox (no corre en CI)'

    # Mismo motivo que check_mp_gateway/setup_mp_gateway: el deploy check
    # payments.E001 no debe bloquear esta herramienta on-demand.
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--status', default='APRO',
                            help='Nombre de titular que fuerza el resultado: '
                                 + ', '.join(sorted(STATUS_NAMES)))
        parser.add_argument('--method', default='master',
                            help='Método/tarjeta de prueba: '
                                 + ', '.join(sorted(TEST_CARDS)))
        parser.add_argument('--amount', default='199.00',
                            help='Monto de la orden desechable.')
        parser.add_argument('--keep', action='store_true',
                            help='No borrar la orden/pago desechables.')

    def handle(self, *args, **options):
        try:
            r = run_sandbox_charge(
                status=options['status'], method=options['method'],
                amount=options['amount'], keep=options['keep'])
        except urllib.error.HTTPError as exc:
            raise CommandError(
                f'card_tokens falló: HTTP {exc.code} {exc.read().decode()[:200]}')

        ok = (r['mp_status'] == r['expected_mp_status'])
        self.stdout.write(f'public_key:    ****{r["public_key_last4"]}')
        self.stdout.write(f'titular/estado: {r["holder_status"]} ({r["method"]})')
        self.stdout.write(f'MP status:     {r["mp_status"]} '
                          f'(esperado {r["expected_mp_status"]}) '
                          f'detail={r["mp_detail"]}')
        self.stdout.write(f'order:         {r["order_number"]} '
                          f'status={r["order_status"]} '
                          f'payment_id={r["payment_id"]} '
                          f'mp_payment={r["gateway_payment_id"]}')
        if not options['keep']:
            self.stdout.write('(orden/pago desechables borrados)')
        if ok:
            self.stdout.write(self.style.SUCCESS(
                f'RESULTADO: {r["mp_status"].upper()} — coincide con lo esperado.'))
        else:
            self.stdout.write(self.style.WARNING(
                f'RESULTADO: {r["mp_status"]} ≠ esperado {r["expected_mp_status"]}.'))
