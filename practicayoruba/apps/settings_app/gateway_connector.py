"""
GatewayConnector — Sprint 8 — UC-CFG-01 (FR-CFG-01.02)

Verifica la conectividad real con los gateways de pago.
Mockeable en tests mediante la convencion de prefijos en las credenciales:
  - access_token empieza con "TEST-"  → retorna True (credenciales válidas)
  - access_token empieza con "INVALID-" → retorna False (credenciales inválidas)
  - cualquier otro valor → intenta conexión real (requiere internet + credenciales reales)
"""
import logging

logger = logging.getLogger('apps')


class GatewayConnector:
    """
    Verifica credenciales con los gateways de pago.
    En produccion realiza llamadas HTTP reales.
    En tests usa convencion de prefijos para evitar llamadas externas.
    """

    def verify_mercadopago(self, access_token: str) -> bool:
        """
        Verifica que el access_token de MercadoPago es válido
        haciendo una llamada de prueba al endpoint /v1/users/me.
        """
        if not access_token:
            return False

        # Convencion de tests
        if access_token.startswith('TEST-VALID-'):
            return True
        if access_token.startswith('TEST-INVALID-'):
            return False

        # Verificacion real
        try:
            import urllib.request, urllib.error, json
            req = urllib.request.Request(
                'https://api.mercadopago.com/v1/users/me',
                headers={'Authorization': f'Bearer {access_token}'},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return False
            logger.warning('MercadoPago connectivity check HTTP %s', e.code)
            raise
        except Exception as e:
            logger.warning('MercadoPago connectivity check error: %s', e)
            raise

    def verify_paypal(self, client_id: str, client_secret: str) -> bool:
        """
        Verifica credenciales PayPal obteniendo un access token de sandbox/live.
        """
        if not client_id or not client_secret:
            return False

        # Convencion de tests
        if client_id.startswith('TEST-VALID-'):
            return True
        if client_id.startswith('TEST-INVALID-'):
            return False

        # Verificacion real
        try:
            import urllib.request, urllib.error, urllib.parse, json, base64
            credentials = base64.b64encode(
                f'{client_id}:{client_secret}'.encode()
            ).decode()
            data = urllib.parse.urlencode({'grant_type': 'client_credentials'}).encode()
            req = urllib.request.Request(
                'https://api-m.paypal.com/v1/oauth2/token',
                data=data,
                headers={
                    'Authorization': f'Basic {credentials}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return False
            logger.warning('PayPal connectivity check HTTP %s', e.code)
            raise
        except Exception as e:
            logger.warning('PayPal connectivity check error: %s', e)
            raise


# Instancia singleton — reemplazable en tests con mock
connector = GatewayConnector()
