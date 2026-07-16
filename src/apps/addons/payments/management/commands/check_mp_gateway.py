"""
check_mp_gateway — diagnóstico del PaymentGateway de MercadoPago.

Verifica, SIN exponer secretos, que el gateway MP quede correctamente
configurado para que "la tarjeta cargue y cobre" cuando lleguen las
credenciales productivas (V-MP / H-PP-04). Pensado para correrse en la VM
tras `setup_mp_gateway`, o en CI.

Qué reporta (nunca imprime el valor de un token, solo ``****`` + últimos 4):

  - Existe un PaymentGateway MERCADOPAGO y está activo.
  - Modo derivado del prefijo del access_token: TEST- → Sandbox,
    APP_USR- (u otro) → Producción.
  - Presencia de public_key / access_token / client_secret (enmascarados).
  - Advertencias accionables:
      * sin public_key   → MP.js no inicializa en el front (BR-009).
      * sin access_token → no se puede crear preferencia ni cobrar.
      * sin client_secret→ el webhook no puede validar la firma.

Con ``--ping`` hace además una llamada autenticada barata al SDK de MP
(``payment_methods().list_all()``) para confirmar que el access_token es
válido de verdad — sin esa llamada el diagnóstico solo ve "hay un token",
no "el token sirve". La salida del ping es solo el status HTTP, nunca el
token.

Con ``--verify-pairing`` hace la prueba decisiva de Checkout API: tokeniza
una tarjeta de PRUEBA con el public_key (igual que MP.js en el navegador) e
intenta cobrarla con el access_token. Si MP responde ``2006 Card Token not
found``, el public_key y el access_token son de **aplicaciones distintas**
de MP Developers — el token nace en una app y el cobro lo intenta otra, así
que "no se encuentra". Ese es el fallo silencioso que ``--ping`` NO detecta:
cada credencial es válida por separado, pero juntas no cierran. Usa un
titular ``OTHE`` (fuerza rechazo) para no dejar un pago aprobado de humo.

Exit code:
  0 → configurado OK (row activa + public_key + access_token presentes; y
      si se pidió --ping, respondió 2xx; y si se pidió --verify-pairing, el
      token creado por el public_key SÍ lo encuentra el access_token).
  1 → falta algo (o el ping/pairing falló). Útil para gate en CI/ops.

Uso:
  DJANGO_SETTINGS_MODULE=config.settings.testing \\
    python manage.py check_mp_gateway
  DJANGO_SETTINGS_MODULE=config.settings.testing \\
    python manage.py check_mp_gateway --ping
  DJANGO_SETTINGS_MODULE=config.settings.testing \\
    python manage.py check_mp_gateway --verify-pairing
"""
import json
import urllib.error
import urllib.request
import uuid

import mercadopago
from django.core.management.base import BaseCommand

from apps.addons.settings_app.models import PaymentGateway

# Tarjeta de PRUEBA oficial de MP México (pública, libre). Solo se usa para
# la prueba de emparejamiento; el titular OTHE fuerza un rechazo para no
# dejar un pago aprobado de humo en la cuenta sandbox.
_PAIRING_TEST_CARD = {
    'card_number': '5474925432670366', 'security_code': '123',
    'expiration_month': 11, 'expiration_year': 2030,
}
_CARD_TOKENS_URL = 'https://api.mercadopago.com/v1/card_tokens?public_key={pk}'


def _mode_from_token(access_token: str) -> str:
    if not access_token:
        return 'DESCONOCIDO'
    if access_token.startswith('TEST-'):
        return 'Sandbox'
    return 'Producción'


class Command(BaseCommand):
    help = 'Diagnostica el PaymentGateway de MercadoPago sin exponer secretos'

    # No correr los system checks: el check payments.E001 falla en
    # producción (DEBUG=False) justo cuando NO hay gateway configurado —
    # que es precisamente el estado que este comando existe para
    # diagnosticar. Exigir --skip-checks al operador sería un footgun.
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--ping',
            action='store_true',
            help='Hace una llamada autenticada al SDK de MP para validar el '
                 'access_token (requiere red).',
        )
        parser.add_argument(
            '--verify-pairing',
            action='store_true',
            help='Prueba decisiva de Checkout API: tokeniza con el public_key '
                 'e intenta cobrar con el access_token. Detecta que ambos sean '
                 'de aplicaciones MP distintas (error 2006). Requiere red.',
        )

    def handle(self, *args, **options):
        do_ping = options['ping']
        do_pairing = options['verify_pairing']

        gateway = (
            PaymentGateway.objects
            .filter(gateway=PaymentGateway.GATEWAY_MERCADOPAGO)
            .first()
        )
        if gateway is None:
            self.stderr.write(self.style.ERROR(
                'FALLO: no existe un PaymentGateway MERCADOPAGO. '
                'Córrelo con: python manage.py setup_mp_gateway.'
            ))
            raise SystemExit(1)

        creds        = gateway.get_credentials()
        masked       = gateway.get_masked_credentials()
        access_token = creds.get('access_token', '')
        public_key   = creds.get('public_key', '')
        client_secret = creds.get('client_secret', '')
        mode         = _mode_from_token(access_token)

        self.stdout.write(f'gateway:       id={gateway.pk} MERCADOPAGO')
        self.stdout.write(f'activo:        {gateway.is_active}')
        self.stdout.write(f'modo:          {mode}')
        self.stdout.write(f'access_token:  {masked.get("access_token", "<AUSENTE>")}')
        self.stdout.write(f'public_key:    {masked.get("public_key", "<AUSENTE>")}')
        self.stdout.write(
            f'client_secret: {masked.get("client_secret", "<AUSENTE>")}'
        )

        problems = []
        if not gateway.is_active:
            problems.append('el gateway está inactivo (no se usará para pagos).')
        if not access_token:
            problems.append(
                'sin access_token: no se puede crear preferencia ni cobrar.'
            )
        if not public_key:
            problems.append(
                'sin public_key: MP.js no inicializa en el front (BR-009).'
            )
        if not client_secret:
            problems.append(
                'sin client_secret: el webhook no puede validar la firma '
                '(la firma MP quedará sin verificar).'
            )

        ping_ok = True
        if do_ping:
            if not access_token:
                problems.append('--ping omitido: no hay access_token que probar.')
                ping_ok = False
            else:
                ping_ok = self._ping(access_token)
                if not ping_ok:
                    problems.append(
                        '--ping falló: el access_token no autentica contra MP.'
                    )

        pairing_ok = True
        if do_pairing:
            if not access_token or not public_key:
                problems.append(
                    '--verify-pairing omitido: faltan public_key o access_token.'
                )
                pairing_ok = False
            else:
                pairing_ok = self._verify_pairing(public_key, access_token)
                if not pairing_ok:
                    problems.append(
                        '--verify-pairing falló: el public_key y el access_token '
                        'son de aplicaciones MP distintas (error 2006 Card Token '
                        'not found). El token nace en la app del public_key y el '
                        'cobro lo intenta la app del access_token. Emparéjalos: '
                        'ambos deben salir de la MISMA aplicación en MP '
                        'Developers, luego corre setup_mp_gateway.'
                    )

        # client_secret ausente es advertencia, no bloqueo del "cobra":
        # separa lo que impide cobrar (access_token/public_key/activo/ping)
        # de lo que solo degrada (webhook signature).
        blocking = [
            p for p in problems
            if 'client_secret' not in p
        ]

        for p in problems:
            self.stderr.write(self.style.WARNING(f'  - {p}'))

        if blocking:
            self.stderr.write(self.style.ERROR(
                'RESULTADO: NO listo para cobrar. Resuelve lo anterior.'
            ))
            raise SystemExit(1)

        marks = []
        if do_ping and ping_ok:
            marks.append('ping OK')
        if do_pairing and pairing_ok:
            marks.append('pairing OK')
        suffix = f' ({", ".join(marks)})' if marks else ''
        self.stdout.write(self.style.SUCCESS(
            f'RESULTADO: listo para cobrar en modo {mode}{suffix}.'
        ))

    def _ping(self, access_token: str) -> bool:
        """Llamada autenticada barata: lista payment_methods. True si 2xx."""
        try:
            sdk = mercadopago.SDK(access_token)
            resp = sdk.payment_methods().list_all()
        except Exception as exc:  # noqa: BLE001 — reportamos, no propagamos
            self.stderr.write(self.style.WARNING(
                f'  - ping error: {type(exc).__name__}'
            ))
            return False
        status = resp.get('status') if isinstance(resp, dict) else None
        self.stdout.write(f'ping status:   {status}')
        return isinstance(status, int) and 200 <= status < 300

    def _verify_pairing(self, public_key: str, access_token: str) -> bool:
        """Tokeniza con el public_key y cobra con el access_token.

        True  → el access_token SÍ encuentra el token del public_key (misma
                aplicación). El pago de humo se fuerza a rechazo (titular OTHE)
                para no dejar un aprobado.
        False → error 2006 Card Token not found (aplicaciones distintas), o el
                public_key no crea tokens, o falla la red. Nunca imprime
                secretos: solo status y código de error de MP.
        """
        # 1) Tokenizar con el public_key (equivalente a MP.js en el navegador).
        payload = {**_PAIRING_TEST_CARD, 'cardholder': {'name': 'OTHE'}}
        req = urllib.request.Request(
            _CARD_TOKENS_URL.format(pk=public_key),
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                token_id = json.loads(resp.read()).get('id', '')
        except urllib.error.HTTPError as exc:
            self.stderr.write(self.style.WARNING(
                f'  - pairing: el public_key no crea tokens (HTTP {exc.code}).'
            ))
            return False
        except Exception as exc:  # noqa: BLE001 — reportamos, no propagamos
            self.stderr.write(self.style.WARNING(
                f'  - pairing: error tokenizando ({type(exc).__name__}).'
            ))
            return False
        if not token_id:
            self.stderr.write(self.style.WARNING(
                '  - pairing: el public_key no devolvió token.'
            ))
            return False

        # 2) Cobrar ese token con el access_token vía el SDK (mismo camino que
        #    producción: el SDK añade el X-Idempotency-Key requerido).
        try:
            sdk = mercadopago.SDK(access_token)
            resp = sdk.payment().create({
                'transaction_amount': 10.0,
                'token': token_id,
                'installments': 1,
                'payment_method_id': 'master',
                'payer': {'email': 'pairing-check@practicayoruba.mx'},
            })
        except Exception as exc:  # noqa: BLE001 — reportamos, no propagamos
            self.stderr.write(self.style.WARNING(
                f'  - pairing: error cobrando ({type(exc).__name__}).'
            ))
            return False

        status = resp.get('status') if isinstance(resp, dict) else None
        body   = resp.get('response', {}) if isinstance(resp, dict) else {}
        # 2006 = Card Token not found → public_key y access_token de apps
        # distintas. Cualquier 2xx (pago creado, aun rechazado) → el token se
        # encontró → emparejamiento correcto.
        if isinstance(status, int) and 200 <= status < 300:
            self.stdout.write(
                f'pairing:       token encontrado (pago de humo status='
                f'{body.get("status")}).'
            )
            return True
        codes = [str(c.get('code')) for c in (body.get('cause') or [])]
        self.stdout.write(
            f'pairing status: {status} '
            f'msg={body.get("message")} cause={",".join(codes) or "-"}'
        )
        return False
