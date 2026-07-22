"""
MercadoPagoGateway — implementación concreta del Strategy Pattern.

Usa el SDK oficial mercadopago>=2.2.0.
Las credenciales se obtienen desde PaymentGateway.credentials (Fernet).
BR-009: las credenciales NUNCA pasan al frontend.
"""
import json
import logging
import uuid
from decimal import Decimal, Decimal as Dec
from addons.payment.gateways.base import BaseGateway, PreferenceResult, InstallmentPlan, PaymentVerification, RefundResult, PaymentResult
from .orders_status import map_order_payment_status
from addons.payment.models import PaymentGateway

import mercadopago
from mercadopago.config.request_options import RequestOptions


logger = logging.getLogger('apps')

# T-502 — Retiro por fases del Payments API legacy (``/v1/payments``).
# Fase 1: instrumentar los code-paths que aún llaman ``sdk.payment()`` /
# ``sdk.refund()`` con un marcador **greppeable** en logs de producción, para
# tener evidencia real de tráfico residual ANTES de borrar el código (la
# migración de creación/refund/cancel/verify a Orders ya está hecha; estos
# paths solo deberían activarse con pagos legacy pre-migración o save-card).
# Criterio de borrado: ``grep LEGACY_PAYMENTS_API`` en 0 durante la ventana de
# observación (ver plan de retiro en el progreso de la iniciativa).
_LEGACY_MARKER = 'LEGACY_PAYMENTS_API'


def _log_legacy_payments_api(method: str, **ctx) -> None:
    """Emite un WARNING greppeable cada vez que se usa el Payments API legacy."""
    detail = ' '.join(f'{k}={v}' for k, v in ctx.items())
    logger.warning('%s method=%s %s', _LEGACY_MARKER, method, detail)


# Métodos de pago que NO requieren token de tarjeta ni número de cuotas.
# Para estos la API de MP usa payer.email + monto + payment_method_id solamente.
NON_CARD_METHOD_IDS = frozenset({
    'oxxo', 'clabe', 'paycash', 'banamex', 'serfin', 'bancomer',
    'account_money', 'consumer_credits',
})

# Mapeo de estados de MP al vocabulario interno
MP_STATUS_MAP = {
    'approved':   'approved',
    'rejected':   'rejected',
    'in_process': 'in_process',
    'pending':    'pending',
    'cancelled':  'rejected',
    'refunded':   'approved',   # se maneja vía webhook de reembolso
}


def _split_payer_name(order) -> tuple[str, str]:
    """
    Deriva (first_name, last_name) del comprador. Prefiere el nombre de la
    cuenta (order.user); si no, parte el recipient_name de la dirección.
    """
    user = getattr(order, 'user', None)
    if user and (user.first_name or user.last_name):
        return user.first_name or '', user.last_name or ''
    addr = getattr(order, 'address', None)
    full = (getattr(addr, 'recipient_name', '') or '').strip()
    if not full:
        return '', ''
    parts = full.split()
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], ' '.join(parts[1:])


def _build_preference_payer(order, email: str) -> dict:
    """
    Arma el ``payer`` de una preferencia de Checkout Pro. A diferencia de la
    Payments API (first_name/last_name, phone.number), la preferencia usa
    ``name``/``surname`` y ``address`` {zip_code, street_name}. Solo agrega
    llaves con datos reales; el email siempre va.
    """
    payer: dict = {'email': email}
    first, last = _split_payer_name(order)
    if first:
        payer['name'] = first
    if last:
        payer['surname'] = last
    addr = getattr(order, 'address', None)
    if addr:
        if addr.phone:
            payer['phone'] = {'number': addr.phone}
        payer['address'] = {
            'zip_code':    addr.zip_code,
            'street_name': addr.street,
        }
    return payer


def _build_receiver_address(order) -> dict | None:
    """receiver_address para shipments (compartido preferencia + pago)."""
    addr = getattr(order, 'address', None)
    if not addr:
        return None
    return {
        'zip_code':    addr.zip_code,
        'street_name': addr.street,
        'city_name':   addr.city,
        'state_name':  addr.state,
    }


def _build_additional_info(order) -> dict:
    """
    Construye additional_info para la Payments API de MercadoPago.

    Calidad de integración (Payment Approval + Security): enviar items,
    datos del payer y dirección de envío da más señales al motor
    antifraude de MP, mejora la tasa de aprobación y sube el score de
    calidad de la integración. Solo incluye llaves con datos reales.
    """
    info: dict = {}

    items = [
        {
            'id':         str(item.pk),
            'title':      item.product_name,
            'quantity':   item.quantity,
            'unit_price': _money_number(item.unit_price),
        }
        for item in order.items.all()
    ]
    if items:
        info['items'] = items

    first, last = _split_payer_name(order)
    addr = getattr(order, 'address', None)
    payer: dict = {}
    if first:
        payer['first_name'] = first
    if last:
        payer['last_name'] = last
    if addr and addr.phone:
        payer['phone'] = {'number': addr.phone}
    if payer:
        info['payer'] = payer

    receiver = _build_receiver_address(order)
    if receiver:
        info['shipments'] = {'receiver_address': receiver}

    return info


# Tipos de payment_method de Orders que llevan token + cuotas (tarjeta).
CARD_PAYMENT_TYPES = frozenset({'credit_card', 'debit_card'})

# Mapeo id no-tarjeta -> ``payment_method.type`` de Orders.
# [INFERRED] por analogía (Pix/Boleto/PSE); se verifica en T-002 contra sandbox.
_NON_CARD_TYPE_BY_ID = {
    'oxxo':             'ticket',
    'paycash':          'ticket',
    'banamex':          'ticket',
    'serfin':           'ticket',
    'bancomer':         'ticket',
    'clabe':            'bank_transfer',
    'account_money':    'account_money',
    'consumer_credits': 'consumer_credits',
}


def _derive_payment_type(payment_method_id: str, is_non_card: bool) -> str:
    """Deriva el ``payment_method.type`` de Orders desde el id.

    Fallback cuando el frontend no envía el ``type`` (T-203 lo enviará). Para
    tarjeta asume ``credit_card`` (el débito debe declararse explícito). Para
    no-tarjeta usa el mapa ``[INFERRED]`` (T-002 lo verifica).
    """
    if is_non_card:
        return _NON_CARD_TYPE_BY_ID.get(payment_method_id, 'ticket')
    return 'credit_card'


def _amount_str(value) -> str:
    """Formatea un importe como string con 2 decimales.

    El Orders API exige los importes como **string** (``"12.90"``), no como
    número — enviar float puede perder precisión o ser rechazado.
    """
    return str(Decimal(str(value)).quantize(Decimal('0.01')))


def _money_number(value) -> float:
    """Importe como número JSON con **2 decimales exactos**.

    Algunos endpoints del Payments API *legacy* (``unit_price`` de items,
    ``amount`` de reembolso) exigen número, no string. Cuantizar a 2
    decimales ANTES de cruzar a ``float`` evita que un artefacto de coma
    flotante IEEE-754 (p.ej. ``19.989999999999998`` en vez de ``19.99``)
    llegue a la pasarela. Redondeo igual que :func:`_amount_str`
    (HALF_EVEN) para que ambos caminos coincidan; sólo cambia el tipo de
    salida (número vs string). Política del proyecto: Decimal para dinero,
    nunca float sin cuantizar.
    """
    return float(Decimal(str(value)).quantize(Decimal('0.01')))


def _build_order_payment_method(
    payment_method_id: str,
    payment_type: str,
    token: str = '',
    installments: int = 1,
    statement_descriptor: str = '',
) -> dict:
    """Arma el bloque ``payment_method`` de una transacción Orders.

    El discriminante es ``type`` (credit_card/debit_card/ticket/bank_transfer).
    Tarjeta lleva ``token`` + ``installments`` (+ ``statement_descriptor``
    opcional); no-tarjeta (OXXO/SPEI) los omite.
    """
    pm = {'id': payment_method_id, 'type': payment_type}
    if payment_type in CARD_PAYMENT_TYPES:
        pm['token'] = token
        pm['installments'] = installments
        if statement_descriptor:
            pm['statement_descriptor'] = statement_descriptor
    return pm


def _build_order_payload(
    order,
    *,
    payment_method_id: str,
    payment_type: str,
    token: str = '',
    installments: int = 1,
    payer_email: str = '',
    payer_identification_type: str = '',
    payer_identification_number: str = '',
    statement_descriptor: str = '',
    three_ds_validation: str = 'on_fraud_risk',
) -> dict:
    """Construye el payload de ``POST /v1/orders`` (Orders API).

    Estructura PROVEN de la colección Postman
    (analisis-postman-inferencias-modelo-datos-orders): ``type: online``,
    importes **string**, ``transactions.payments[]`` con el discriminante
    ``payment_method.type``, ``processing_mode``/``capture_mode`` automatic
    (DEC-ORD-02), ``payer``/``items`` inline.

    ``three_ds_validation`` = ``on_fraud_risk`` (DEC-ORD-02): dispara el 3DS
    solo ante riesgo. La **ubicación exacta** de la clave de config 3DS en el
    request se confirma en T-202 (smoke sandbox); se aísla en ``config`` del
    payment para poder ajustarla sin tocar el resto del payload.

    Función pura: no hace red; determinística desde ``order``.
    """
    total = _amount_str(order.value.total)

    payment_method = _build_order_payment_method(
        payment_method_id, payment_type, token, installments, statement_descriptor,
    )
    # 3DS (DEC-ORD-02, on_fraud_risk): el Orders API **no acepta** una clave de
    # config 3DS explícita en el create — verificado contra el sandbox (T-202,
    # H-ORD-07): ``payment_method.config``, ``config.payment_method.
    # three_d_secure_mode``, ``payments[].three_d_secure_mode`` y
    # ``payment_method.three_d_secure_mode`` devuelven todas
    # ``400 unsupported_properties``. El motor antifraude de MP aplica el 3DS
    # automáticamente según riesgo (== on_fraud_risk); cuando lo dispara, el
    # pago vuelve ``action_required``/``pending_challenge`` y lo maneja
    # verify_order/webhook/UI. Por eso NO se emite ninguna clave de config aquí.
    # ``three_ds_validation`` se conserva en la firma por retrocompatibilidad.

    email_resolved = (
        payer_email
        or (order.user.email if order.user else '')
        or getattr(order, 'guest_email', '')
        or 'guest@practicayoruba.mx'
    )
    payer = {'email': email_resolved}
    if payer_identification_type and payer_identification_number:
        payer['identification'] = {
            'type':   payer_identification_type,
            'number': payer_identification_number,
        }

    # items/payer/shipments inline (reusa additional_info; importes a string).
    info = _build_additional_info(order)

    # Señales antifraude del comprador (nombre/teléfono) en el ``payer`` de la
    # order — preserva la enriquecimiento de aprobación de la Payments API
    # (additional_info.payer) que Orders acepta inline en ``payer``.
    info_payer = info.get('payer') or {}
    for key in ('first_name', 'last_name', 'phone'):
        if info_payer.get(key):
            payer[key] = info_payer[key]

    payload = {
        'type':               'online',
        'external_reference':  order.order_number,
        'total_amount':        total,
        'processing_mode':     'automatic',
        'capture_mode':        'automatic',
        'transactions': {
            'payments': [
                {'amount': total, 'payment_method': payment_method},
            ],
        },
        'payer': payer,
    }

    items = info.get('items')
    if items:
        payload['items'] = [
            {**it, 'unit_price': _amount_str(it['unit_price'])} for it in items
        ]
    shipments = info.get('shipments')
    if shipments:
        payload['shipments'] = shipments

    return payload


def _get_sdk() -> mercadopago.SDK:
    """
    Instancia el SDK de MP con el access_token descifrado en memoria.
    BR-009: las credenciales se descifran solo en el servidor.
    H-S15-004: las credenciales están en PaymentGateway.credentials (Fernet).
    """
    try:
        gateway = PaymentGateway.objects.get(
            gateway=PaymentGateway.GATEWAY_MERCADOPAGO,
            is_active=True,
        )
        creds       = gateway.get_credentials()
        access_token = creds.get('access_token', '')
        if not access_token:
            raise ValueError('access_token no configurado en PaymentGateway MERCADOPAGO')
        return mercadopago.SDK(access_token)
    except PaymentGateway.DoesNotExist:
        raise ValueError(
            'No existe un PaymentGateway activo para MERCADOPAGO. '
            'Configúralo en UC-CFG-01 antes de iniciar pagos.'
        )


class MercadoPagoGateway(BaseGateway):
    """
    Implementación del gateway de pago MercadoPago.
    Cubre UC-PAY-01 y UC-PAY-01-EXT (cuotas MSI).
    """

    def create_preference(
        self,
        order,
        back_urls: dict,
        installments: int = 1,
    ) -> PreferenceResult:
        """
        Crea una preferencia de pago en MercadoPago.
        FR-PAY-01.01, FR-PAY-01.02.

        El payload incluye:
        - items: OrderItems con nombre, cantidad y precio unitario del snapshot BR-005
        - payer: email del comprador o guest_email
        - back_urls: success, failure, pending
        - auto_return: 'approved'
        - external_reference: order.order_number para correlacionar el webhook
        - installments (solo si > 1): configuración de cuotas MSI
        """
        sdk = _get_sdk()

        # Construir items desde el snapshot BR-005
        items = [
            {
                'id':          str(item.pk),
                'title':       item.product_name,
                'description': f'{item.variant_label}' if item.variant_label else '',
                'quantity':    item.quantity,
                'unit_price':  _money_number(item.unit_price),
                'currency_id': 'MXN',
            }
            for item in order.items.all()
        ]

        # Email del comprador (autenticado o invitado)
        payer_email = (
            order.user.email if order.user
            else order.guest_email or 'guest@practicayoruba.com'
        )

        preference_data = {
            'items':              items,
            'payer':              _build_preference_payer(order, payer_email),
            'back_urls':          back_urls,
            'auto_return':        'approved',
            'external_reference': order.order_number,
        }

        # Calidad de integración MP: dirección de envío da señales al motor
        # antifraude y mejora la aprobación.
        receiver = _build_receiver_address(order)
        if receiver:
            preference_data['shipments'] = {'receiver_address': receiver}

        # UC-PAY-01-EXT: agregar configuración de cuotas si se pidió MSI
        if installments > 1:
            preference_data['payment_methods'] = {
                'installments':     installments,
                'default_installments': installments,
            }

        response = sdk.preference().create(preference_data)

        if response['status'] != 201:
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MercadoPago preference error: %s', msg)
            raise RuntimeError(f'Error al crear preferencia en MercadoPago: {msg}')

        result = response['response']
        return PreferenceResult(
            preference_id = result['id'],
            checkout_url  = result['init_point'],
        )

    def get_installment_plans(self, amount: Decimal) -> list[InstallmentPlan]:
        """
        Consulta los planes de cuotas MSI disponibles en MP.
        FR-PAY-01-EXT.01.
        Solo retorna planes sin interés (installment_rate = 0).
        """
        sdk  = _get_sdk()
        resp = sdk.payment_methods().list_all()

        if resp.get('status') != 200:
            logger.warning('MercadoPago installments error: %s', resp)
            return []

        plans = []
        for method in resp.get('response', []):
            payer_costs = method.get('payer_costs', [])
            for cost in payer_costs:
                if cost.get('installment_rate', 1) == 0:
                    n = cost.get('installments', 1)
                    if n > 1:
                        amount_per = (amount / n).quantize(Decimal('0.01'))
                        plans.append(InstallmentPlan(
                            installments=n,
                            amount_per_installment=amount_per,
                            total_amount=amount,
                            interest_rate=Decimal('0.00'),
                        ))

        # Deduplicar y ordenar por número de cuotas
        seen = set()
        unique = []
        for p in sorted(plans, key=lambda x: x.installments):
            if p.installments not in seen:
                seen.add(p.installments)
                unique.append(p)
        return unique

    def verify_payment(self, payment_id: str) -> PaymentVerification:
        """
        Verifica el estado de un pago en MP (Payments API **legacy**).

        DEPRECADO (T-502): para pagos migrados a Orders usar ``verify_order``.
        Solo se conserva para webhooks ``type: payment`` de pagos legacy.
        """
        _log_legacy_payments_api('verify_payment', payment_id=payment_id)
        sdk  = _get_sdk()
        resp = sdk.payment().get(payment_id)

        if resp.get('status') != 200:
            logger.error('MercadoPago verify payment error: %s', resp)
            return PaymentVerification(
                gateway_payment_id=payment_id,
                status='pending',
                amount=None,
            )

        data = resp['response']
        return PaymentVerification(
            gateway_payment_id=str(data.get('id', payment_id)),
            status=MP_STATUS_MAP.get(data.get('status', 'pending'), 'pending'),
            amount=Decimal(str(data.get('transaction_amount', 0))),
            installments=data.get('installments', 1),
        )

    # -------------------------------------------------------------------------
    # Orders API — operaciones sobre el recurso Order (DEC-ORD-01)
    # mp_order_id (ORD...) es la clave; el pago vive en transactions.payments[0].
    # -------------------------------------------------------------------------

    def verify_order(self, mp_order_id: str) -> PaymentVerification:
        """Verifica el estado de una Order — GET ``/v1/orders/{id}`` (T-301).

        Reemplaza el polling del Payments API para pagos migrados a Orders: lee
        el pago anidado en ``transactions.payments[0]`` y mapea su ``status``
        con ``orders_status`` (processed→approved, action_required→pending…),
        no con ``MP_STATUS_MAP`` legacy que caía todo a ``pending``.
        """
        sdk  = _get_sdk()
        resp = sdk.order().get(mp_order_id)

        if resp.get('status') != 200:
            logger.error('MercadoPago verify order error: %s', resp)
            return PaymentVerification(
                gateway_payment_id=None,
                status='pending',
                amount=None,
            )

        data     = resp['response']
        payments = (data.get('transactions') or {}).get('payments') or []
        pay      = payments[0] if payments else {}
        pay_method = pay.get('payment_method') or {}
        return PaymentVerification(
            gateway_payment_id=str(pay.get('id') or ''),
            status=map_order_payment_status(
                pay.get('status') or data.get('status', ''),
                pay.get('status_detail', ''),
            ),
            amount=Decimal(str(pay.get('amount') or data.get('total_amount') or 0)),
            installments=pay_method.get('installments', 1),
        )

    def cancel_order(self, mp_order_id: str) -> dict:
        """Cancela una Order — POST ``/v1/orders/{id}/cancel`` (T-401).

        Válido para orders aún no procesadas (``created``/``action_required``).
        Retorna la respuesta cruda del SDK. Raises ``RuntimeError`` en error.
        """
        sdk = _get_sdk()
        response = sdk.order().cancel(mp_order_id)
        if response.get('status') not in (200, 201):
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MercadoPago cancel order error: %s', msg)
            raise RuntimeError(f'Error al cancelar la order en MercadoPago: {msg}')
        return response

    def refund_order(self, mp_order_id: str, payment_id: str = '', amount=None) -> RefundResult:
        """Reembolso via Orders API — ``/v1/orders/{id}/refund`` (T-402).

        Total (sin body) o parcial (``transactions[] = {id, amount}``). El
        importe va como **string** (Orders exige string). Usa el
        ``refund_transaction`` del SDK oficial.
        """
        sdk  = _get_sdk()
        body = None
        if amount is not None:
            body = {'transactions': [{'id': payment_id, 'amount': _amount_str(amount)}]}

        response = sdk.order().refund_transaction(mp_order_id, body)
        if response.get('status') not in (200, 201):
            err = response.get('response', {})
            msg = err.get('message', str(response))
            logger.error('MercadoPago refund order error: %s', msg)
            raise RuntimeError(f'Error al reembolsar la order en MercadoPago: {msg}')

        data = response['response']
        # El refund vive en transactions.refunds[0] (Orders) o al top-level según
        # la forma de respuesta; se toma el primer id disponible.
        refunds = (data.get('transactions') or {}).get('refunds') or []
        refund  = refunds[0] if refunds else data
        return RefundResult(
            refund_id=str(refund.get('id', '')),
            status='approved',
            amount=Dec(str(refund.get('amount', amount or 0))),
        )

    def search_order(self, external_reference: str) -> dict:
        """Busca orders por ``external_reference`` (order_number) — T-403.

        Reconciliación cuando se pierde el webhook (rescate N2): recupera el
        estado real de la order desde MP. Retorna el ``response`` del SDK (dict
        con ``results``); ``{}`` si MP responde con error (best-effort).
        """
        sdk = _get_sdk()
        response = sdk.order().search(filters={'external_reference': external_reference})
        if response.get('status') != 200:
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MercadoPago search order error: %s', msg)
            return {}
        return response['response']

    def search_customer_by_email(self, email: str):
        """
        Busca un customer en MP por email.
        Retorna el customer_id string o None si no existe o hay error.
        """
        sdk = _get_sdk()
        response = sdk.customer().search({'email': email})
        if response.get('status') != 200:
            return None
        results = response['response'].get('results', [])
        if results:
            return results[0]['id']
        return None

    def create_customer(self, email: str, first_name: str = '', last_name: str = '') -> str:
        """
        Crea un customer en MP y retorna el customer_id.
        Raises RuntimeError si MP responde con error.
        """
        sdk = _get_sdk()
        payload = {
            'email':      email,
            'first_name': first_name,
            'last_name':  last_name,
        }
        response = sdk.customer().create(payload)
        if response.get('status') != 201:
            body = response.get('response', {})
            msg = body.get('message', str(response))
            raise RuntimeError(f'Error al crear customer en MercadoPago: {msg}')
        return response['response']['id']

    def get_or_create_customer(self, email: str, first_name: str = '', last_name: str = '') -> str:
        """
        Busca customer existente o crea uno nuevo. Evita el error 101 de MP
        (duplicado) buscando primero. Retorna el customer_id.
        """
        existing = self.search_customer_by_email(email)
        if existing:
            return existing
        return self.create_customer(email, first_name, last_name)

    def create_payment(
        self,
        order,
        token: str = '',
        installments: int = 1,
        payment_method_id: str = '',
        issuer_id: str = '',
        payer_email: str = '',
        payer_identification_type: str = '',
        payer_identification_number: str = '',
        customer_id: str = '',
        payment_type: str = '',
    ) -> PaymentResult:
        """
        Crea un pago con Checkout API **Orders** (``POST /v1/orders``, pago en
        sitio sin redirección). Migrado del Payments API (DEC-ORD-01/02/03): MP
        restringió ``/v1/payments`` legacy (401 cause 7) y empuja a Orders.

        Para tarjeta: ``token`` (obligatorio) + ``installments`` +
        ``payment_type`` (credit_card/debit_card). Para no-tarjeta (OXXO/SPEI):
        solo email + ``payment_method_id`` (el ``type`` se deriva).
        """
        sdk = _get_sdk()

        is_non_card = payment_method_id in NON_CARD_METHOD_IDS
        resolved_type = payment_type or _derive_payment_type(payment_method_id, is_non_card)

        payload = _build_order_payload(
            order,
            payment_method_id=payment_method_id,
            payment_type=resolved_type,
            token=token,
            installments=installments,
            payer_email=payer_email,
            payer_identification_type=payer_identification_type,
            payer_identification_number=payer_identification_number,
        )

        # X-Idempotency-Key por intento de pago (DEC-ORD-02): un UUID nuevo por
        # llamada protege contra doble-submit del MISMO request sin bloquear un
        # reintento legítimo. customer_id se conserva en la firma para el flujo
        # futuro de saved-card; NO se envía junto al token de un solo uso.
        request_options = RequestOptions()
        request_options.custom_headers = {'X-Idempotency-Key': uuid.uuid4().hex}

        response = sdk.order().create(payload, request_options=request_options)

        http = response.get('status')
        raw  = response.get('response') or {}

        # HTTP 402 = pago RECHAZADO por el emisor (no un error de gateway):
        # el Orders API devuelve la order completa bajo ``response.data`` con
        # ``status: failed`` + ``status_detail`` (p. ej. insufficient_amount).
        # Verificado contra el sandbox (T-202, H-ORD-09): tratarlo como un
        # PaymentResult ``rejected`` — NO ``raise`` — para que la vista devuelva
        # 200 con el motivo, no 502 GATEWAY_ERROR.
        if http == 402 and isinstance(raw.get('data'), dict):
            data = raw['data']
        elif http in (200, 201):
            data = raw
        else:
            # 400 (validación), 401 (auth), 5xx: error real de integración/gateway.
            msg = raw.get('message') or str(raw.get('errors') or response)
            logger.error('MercadoPago Orders API error: %s', msg)
            raise RuntimeError(f'Error al procesar pago en MercadoPago: {msg}')

        # El pago vive en transactions.payments[0]; el id de la order (ORD) y el
        # del pago (PAY) se persisten por separado (DEC-ORD-03).
        payments = (data.get('transactions') or {}).get('payments') or []
        pay = payments[0] if payments else {}
        pay_method = pay.get('payment_method') or {}

        pay_status = pay.get('status') or data.get('status', '')
        pay_detail = pay.get('status_detail') or data.get('status_detail', '')

        # Campos de voucher (no-tarjeta): OXXO/SPEI exponen la URL/expiración en
        # el payment_method anidado. Best-effort; T-501 lo refina tras T-002.
        external_resource_url = (
            pay_method.get('ticket_url', '')
            or pay_method.get('external_resource_url', '')
            or data.get('external_resource_url', '')
        )
        date_of_expiration = pay.get('date_of_expiration', '') or data.get('expiration_time', '')

        return PaymentResult(
            gateway_payment_id    = str(pay.get('id') or ''),
            mp_order_id           = str(data.get('id') or ''),
            status                = map_order_payment_status(pay_status, pay_detail),
            status_detail         = pay_detail,
            amount                = Decimal(str(pay.get('amount') or order.value.total)),
            installments          = pay_method.get('installments', installments),
            external_resource_url = external_resource_url,
            date_of_expiration    = date_of_expiration,
            transaction_data      = pay_method if is_non_card and pay_method else None,
        )

    # -------------------------------------------------------------------------
    # Card CRUD — Customer Cards API
    # -------------------------------------------------------------------------

    def save_card(self, customer_id: str, token: str) -> dict:
        """
        Guarda una tarjeta para un customer existente.
        POST /v1/customers/{customer_id}/cards
        Retorna el dict completo de la tarjeta creada.
        Raises RuntimeError si MP responde con error.
        """
        sdk = _get_sdk()
        response = sdk.card().create(customer_id, {'token': token})
        if response.get('status') not in (200, 201):
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MP save_card error (customer=%s): %s', customer_id, msg)
            raise RuntimeError(f'Error al guardar tarjeta en MercadoPago: {msg}')
        return response['response']

    def get_customer_cards(self, customer_id: str) -> list:
        """
        Lista las tarjetas de un customer.
        GET /v1/customers/{customer_id}/cards
        Retorna lista de dicts de tarjeta (puede ser vacía).
        """
        sdk = _get_sdk()
        response = sdk.card().all(customer_id)
        if response.get('status') != 200:
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MP get_customer_cards error (customer=%s): %s', customer_id, msg)
            raise RuntimeError(f'Error al obtener tarjetas de MercadoPago: {msg}')
        return response['response']

    def get_customer_card(self, customer_id: str, card_id: str) -> dict:
        """
        Obtiene una tarjeta específica de un customer.
        GET /v1/customers/{customer_id}/cards/{id}
        Raises RuntimeError si no se encuentra o hay error de MP.
        """
        sdk = _get_sdk()
        response = sdk.card().get(customer_id, card_id)
        if response.get('status') != 200:
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error(
                'MP get_customer_card error (customer=%s, card=%s): %s',
                customer_id, card_id, msg,
            )
            raise RuntimeError(f'Error al obtener tarjeta de MercadoPago: {msg}')
        return response['response']

    def update_customer_card(self, customer_id: str, card_id: str, data: dict) -> dict:
        """
        Actualiza datos de una tarjeta (vencimiento, titular).
        PUT /v1/customers/{customer_id}/cards/{id}
        Raises RuntimeError si MP responde con error.
        """
        sdk = _get_sdk()
        response = sdk.card().update(customer_id, card_id, data)
        if response.get('status') not in (200, 201):
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error(
                'MP update_customer_card error (customer=%s, card=%s): %s',
                customer_id, card_id, msg,
            )
            raise RuntimeError(f'Error al actualizar tarjeta en MercadoPago: {msg}')
        return response['response']

    def delete_customer_card(self, customer_id: str, card_id: str) -> dict:
        """
        Elimina una tarjeta de un customer.
        DELETE /v1/customers/{customer_id}/cards/{id}
        Retorna el dict de la tarjeta eliminada.
        Raises RuntimeError si MP responde con error.
        """
        sdk = _get_sdk()
        response = sdk.card().delete(customer_id, card_id)
        if response.get('status') != 200:
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error(
                'MP delete_customer_card error (customer=%s, card=%s): %s',
                customer_id, card_id, msg,
            )
            raise RuntimeError(f'Error al eliminar tarjeta de MercadoPago: {msg}')
        return response['response']

    def get_payment_methods(self) -> list:
        """
        Lista los métodos de pago disponibles en MP.
        GET /v1/payment_methods
        Filtra a los tipos relevantes: credit_card, debit_card, ticket,
        bank_transfer, account_money.
        BR-009: no expone access_token — solo datos públicos del método.
        """
        sdk = _get_sdk()
        resp = sdk.payment_methods().list_all()

        if resp.get('status') != 200:
            logger.warning('MP get_payment_methods error: %s', resp)
            return []

        RELEVANT_TYPES = frozenset({
            'credit_card', 'debit_card', 'ticket', 'bank_transfer', 'account_money',
        })

        methods = []
        for m in resp.get('response', []):
            if m.get('payment_type_id') in RELEVANT_TYPES and m.get('status') == 'active':
                methods.append({
                    'id':                 m.get('id', ''),
                    'name':               m.get('name', ''),
                    'payment_type_id':    m.get('payment_type_id', ''),
                    'thumbnail':          m.get('thumbnail', ''),
                    'secure_thumbnail':   m.get('secure_thumbnail', ''),
                    'min_allowed_amount': m.get('min_allowed_amount', 0),
                    'max_allowed_amount': m.get('max_allowed_amount', 0),
                    'accreditation_time': m.get('accreditation_time', 0),
                })
        return methods

    def refund(self, gateway_payment_id: str, amount) -> 'RefundResult':
        """
        Ejecuta un reembolso en MercadoPago (Payments API **legacy**).
        UC-PAY-07 (FR-PAY-07.02). H-REF-002: usa sdk.refund().create().

        DEPRECADO (T-502): para pagos Orders usar ``refund_order``
        (``services.refund`` ya ramifica por ``mp_order_id``). Solo pagos
        legacy pre-migración deberían llegar aquí.
        """
        _log_legacy_payments_api('refund', gateway_payment_id=gateway_payment_id)
        sdk = _get_sdk()
        payload = {}
        if amount is not None:
            payload['amount'] = _money_number(amount)

        response = sdk.refund().create(gateway_payment_id, payload)

        if response.get('status') not in (200, 201):
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MercadoPago refund error: %s', msg)
            raise RuntimeError(f'Error al reembolsar en MercadoPago: {msg}')

        data = response['response']
        return RefundResult(
            refund_id=str(data.get('id', '')),
            status='approved',
            amount=Dec(str(data.get('amount', amount or 0))),
        )

    def get_chargeback(self, chargeback_id: str) -> dict:
        """
        Obtiene el detalle de un contracargo por su ID. T-17.
        Retorna el dict completo de respuesta del SDK (response + status).
        """
        sdk = _get_sdk()
        response = sdk.chargeback().get(chargeback_id)
        if response.get('status') not in (200, 201):
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MercadoPago chargeback get error: %s', msg)
            raise RuntimeError(f'Error al obtener contracargo: {msg}')
        return response

    def cancel_payment(self, gateway_payment_id: str) -> dict:
        """
        Cancela un pago pendiente en MercadoPago (Payments API **legacy**). T-CAN.

        DEPRECADO (T-502): para pagos Orders usar ``cancel_order`` (la vista de
        cancelación ya ramifica por ``mp_order_id``). Solo pagos legacy llegan aquí.
        """
        _log_legacy_payments_api('cancel_payment', gateway_payment_id=gateway_payment_id)
        sdk = _get_sdk()
        response = sdk.payment().update(gateway_payment_id, {'status': 'cancelled'})
        if response.get('status') not in (200, 201):
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MercadoPago cancel payment error: %s', msg)
            raise RuntimeError(f'Error al cancelar pago en MercadoPago: {msg}')
        return response

    def zero_dollar_auth(
        self,
        token: str,
        payment_method_id: str,
        payer_email: str,
    ) -> dict:
        """
        Valida una tarjeta sin cargo real (T-15).
        Crea un pago con amount=0 y capture=False; MP verifica la tarjeta
        sin débito. Retorna la respuesta cruda del SDK (incluye 'status').

        DEPRECADO (T-502): usa el Payments API legacy (``/v1/payments``).
        La migración a Orders API no cubre save-card / validación 0-dólar;
        cada invocación queda instrumentada con LEGACY_PAYMENTS_API para la
        ventana de observación previa al retiro del endpoint legacy.
        """
        _log_legacy_payments_api('zero_dollar_auth', payment_method_id=payment_method_id)
        sdk = _get_sdk()
        response = sdk.payment().create({
            'token':              token,
            'transaction_amount': 0,
            'payment_method_id':  payment_method_id,
            'capture':            False,
            'payer':              {'email': payer_email},
        })
        if response.get('status') not in (200, 201):
            body = response.get('response', {})
            msg  = body.get('message', str(response))
            logger.error('MercadoPago zero-dollar auth error: %s', msg)
            raise RuntimeError(f'Error al validar tarjeta en MercadoPago: {msg}')
        return response['response']
