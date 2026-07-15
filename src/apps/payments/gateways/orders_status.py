"""
Mapeo de estados del **Orders API** de MercadoPago al vocabulario interno.

El Orders API NO devuelve ``approved``/``rejected``/``pending`` como el Payments
API: devuelve ``status`` de order/payment (``created``/``processed``/
``action_required``/``processing``/``canceled``/``failed``/``refunded``/
``charged_back``) + un ``status_detail`` anidado (``accredited``,
``waiting_payment``, ``pending_challenge``, ``cc_rejected_*``, …).

El mapa Payments-era (``mercadopago.py`` ``MP_STATUS_MAP``) cae al default
``pending`` para TODOS estos, clasificando un cobro ``processed/accredited`` como
``pending``. Este modulo construye el mapa correcto para Orders.

Vocabulario interno (``PaymentResult.status``): ``approved`` / ``rejected`` /
``pending`` / ``in_process``. Los estados **accionables** de Orders
(``action_required``: challenge 3DS, espera de pago offline, captura diferida)
mapean a ``pending`` — NO a ``rejected`` — y se distinguen por su
``status_detail`` (ver ``requires_challenge`` / ``awaiting_offline_payment``).

Fuente: docs/source/gestion/pm/api/iniciativas/migrar-gateway-mp-orders-api/
analisis-estados-orders-catalogo.rst (catalogo canonico).
"""

# Vocabulario interno
APPROVED = 'approved'
REJECTED = 'rejected'
PENDING = 'pending'
IN_PROCESS = 'in_process'

# ``payments[].status`` de Orders -> vocabulario interno.
# ``action_required`` y ``created`` son pendientes accionables (no rechazo).
# ``refunded`` se trata como ``approved`` (el reembolso se refleja via webhook,
# igual que el mapa Payments-era). ``charged_back`` es dinero revertido: se
# clasifica ``rejected`` a nivel de resultado de pago; el ciclo de disputa lo
# gestiona la iniciativa gestionar-contracargos.
_ORDER_PAYMENT_STATUS = {
    'created':        PENDING,
    'processed':      APPROVED,
    'processing':     IN_PROCESS,
    'action_required': PENDING,
    'canceled':       REJECTED,
    'failed':         REJECTED,
    'refunded':       APPROVED,
    'charged_back':   REJECTED,
}

# ``status_detail`` accionables bajo ``action_required`` (siguen siendo PENDING).
_CHALLENGE_DETAIL = 'pending_challenge'
_OFFLINE_PAYMENT_DETAIL = 'waiting_payment'
_DEFERRED_CAPTURE_DETAIL = 'waiting_capture'

# ``status_detail`` de rechazo (``status = failed``) -> motivo legible para el
# mensaje al usuario. Equivalente Orders de los ``cc_rejected_*`` de Payments.
ORDER_REJECT_REASONS = {
    'bad_filled_card_data':        'Datos de tarjeta incorrectos.',
    'invalid_card_token':          'Token de tarjeta incorrecto.',
    'high_risk':                   'Rechazado por prevención de fraude.',
    'rejected_by_issuer':          'Rechazado por el emisor (se requería autorización).',
    'required_call_for_authorize': 'Rechazado por el emisor de la tarjeta.',
    'max_attempts_exceeded':       'Rechazado por exceder el máximo de intentos.',
    'card_disabled':               'La tarjeta está deshabilitada.',
    'card_insufficient_amount':    'Fondos insuficientes.',
    'amount_limit_exceeded':       'El monto excede el límite de la tarjeta.',
    'invalid_installments':        'Cuotas inválidas.',
    'processing_error':            'Error de procesamiento.',
}

_DEFAULT_REJECT_REASON = 'El pago fue rechazado.'


def map_order_payment_status(status: str, status_detail: str = '') -> str:
    """Mapea el ``status`` de un ``payments[]`` de Orders al vocabulario interno.

    ``status`` es la clave primaria; ``status_detail`` solo refina el motivo de
    rechazo o el tipo de pendiente (no cambia la clase interna). Un ``status``
    desconocido cae a ``pending`` (fail-safe: no aprobar ni rechazar de más).
    """
    return _ORDER_PAYMENT_STATUS.get((status or '').strip(), PENDING)


def requires_challenge(status_detail: str = '') -> bool:
    """True si el pago exige un challenge 3DS (``pending_challenge``).

    El integrador debe redirigir/embeber la URL del challenge
    (``payment_method.transaction_security.url``); NO es un rechazo.
    """
    return (status_detail or '').strip() == _CHALLENGE_DETAIL


def awaiting_offline_payment(status_detail: str = '') -> bool:
    """True si la order espera un pago offline (OXXO/SPEI aún no pagado)."""
    return (status_detail or '').strip() == _OFFLINE_PAYMENT_DETAIL


def awaiting_deferred_capture(status_detail: str = '') -> bool:
    """True si el pago fue autorizado y espera captura diferida.

    Con ``capture_mode: automatic`` (DEC-ORD-02) no deberia ocurrir; se expone
    para completitud del catalogo.
    """
    return (status_detail or '').strip() == _DEFERRED_CAPTURE_DETAIL


def reject_reason(status_detail: str = '') -> str:
    """Motivo legible de un rechazo (``status = failed``) para el usuario."""
    return ORDER_REJECT_REASONS.get((status_detail or '').strip(), _DEFAULT_REJECT_REASON)
