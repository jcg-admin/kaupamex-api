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

Exit code:
  0 → configurado OK (row activa + public_key + access_token presentes; y
      si se pidió --ping, el ping respondió 2xx).
  1 → falta algo (o el ping falló). Útil para gate en CI/ops.

Uso:
  DJANGO_SETTINGS_MODULE=config.settings.testing \\
    python manage.py check_mp_gateway
  DJANGO_SETTINGS_MODULE=config.settings.testing \\
    python manage.py check_mp_gateway --ping
"""
import mercadopago
from django.core.management.base import BaseCommand

from apps.settings_app.models import PaymentGateway


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

    def handle(self, *args, **options):
        do_ping = options['ping']

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

        suffix = ' (ping OK)' if do_ping and ping_ok else ''
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
