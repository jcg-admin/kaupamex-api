"""Modelo ``PaymentGateway`` — addon ``payment`` (framework de pagos).

Contraparte de ``payment.provider`` de Odoo: el registro de configuración por
provider (cuál está activo y sus credenciales, cifradas con Fernet). Movido
desde ``settings_app`` (UC-CFG-01): la configuración de la pasarela pertenece
al framework de pagos, no a la configuración genérica del sitio. La tabla
``settings_payment_gateway`` conserva su nombre (movimiento state-only).

Identifiers + field names in English per DEC-DOC-005.
"""
import base64
import hashlib
import json
import logging

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel

logger = logging.getLogger(__name__)


class PaymentGateway(TimeStampedModel):
    """Pasarela de pago configurada. UC-CFG-01."""
    GATEWAY_TEST     = 'TEST'
    GATEWAY_MERCADOPAGO = 'MERCADOPAGO'
    GATEWAY_PAYPAL   = 'PAYPAL'
    GATEWAYS = [
        (GATEWAY_TEST,        'Test (sandbox)'),
        (GATEWAY_MERCADOPAGO, 'MercadoPago'),
        (GATEWAY_PAYPAL,      'PayPal'),
    ]

    name        = models.CharField(max_length=50)
    gateway     = models.CharField(max_length=20, choices=GATEWAYS, unique=True)
    is_active   = models.BooleanField(default=False)
    credentials = models.BinaryField(
        help_text='Credenciales cifradas con Fernet (addons.payment.models.payment_provider._fernet_key)')
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'settings_payment_gateway'
        verbose_name = 'Pasarela de pago'

    def __str__(self):
        return f'{self.gateway} ({"activo" if self.is_active else "inactivo"})'

    @staticmethod
    def _fernet_key() -> bytes:
        raw = settings.SECRET_KEY.encode()
        digest = hashlib.sha256(raw).digest()
        return base64.urlsafe_b64encode(digest)

    def set_credentials(self, data: dict) -> None:
        f = Fernet(self._fernet_key())
        self.credentials = f.encrypt(json.dumps(data).encode())

    def get_credentials(self) -> dict:
        """Descifra y retorna las credenciales. {} si están vacías o son inválidas."""
        if not self.credentials:
            return {}
        try:
            f = Fernet(self._fernet_key())
            return json.loads(f.decrypt(bytes(self.credentials)).decode())
        except Exception:
            # Loud-log: credenciales no descifrables (SECRET_KEY rotada
            # o blob corrupto). UI debe tratar como "sin credenciales"
            # y obligar a re-ingresarlas. DEC-DOC-008.
            logger.warning(
                'PaymentGateway.get_credentials: decrypt failed gw=%s',
                getattr(self, 'gateway', '?'), exc_info=True,
            )
            return {}

    def get_masked_credentials(self) -> dict:
        """Retorna credenciales con campos sensibles enmascarados.
        Formato: '****' + últimos 4 caracteres (empieza siempre con *).
        BR-009 / RNF-SEC-002: nunca exponer credenciales completas.
        """
        try:
            creds = self.get_credentials()
        except Exception:
            # Loud-log: get_credentials ya loggea pero envolvemos por si
            # falla antes de su try. DEC-DOC-008.
            logger.warning(
                'PaymentGateway.get_masked_credentials failed gw=%s',
                getattr(self, 'gateway', '?'), exc_info=True,
            )
            return {}
        masked = {}
        for key, value in creds.items():
            if isinstance(value, str) and len(value) > 4:
                masked[key] = '****' + value[-4:]
            else:
                masked[key] = '****'
        return masked

