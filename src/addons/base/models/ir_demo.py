"""``ir.demo`` — asistente de instalación de datos de demostración.

Adaptación fiel de ``odoo/addons/base/models/ir_demo.py``
(``odoo-tools@bf077302``, ``odoo19c:``). Son 19 líneas allá: un
``TransientModel`` con un único método ``install_demo`` gateado por
``assert_log_admin_access``, que llama a ``odoo.modules.loading.force_demo`` y
redirige a ``/odoo``.

**Qué se porta y qué no, medido.** El *contrato* (un asistente que un
administrador dispara para poblar datos de demostración) se porta; el *cuerpo*
del método de la referencia llama a su cargador de módulos, que aquí no existe:
el registro de apps de Django se congela en ``django.setup()`` y no hay un
``force_demo`` equivalente. En su lugar el disparo se delega a los comandos de
seed del propio proyecto — que son el mecanismo real que puebla datos de
ejemplo aquí. Medidos con ``find src -path '*/management/commands/*.py'``:
cuatro comandos ``seed_*`` (``seed_authz``, ``seed_menu``, ``seed_l0_chart``,
``seed_rate_cards``).

El decorador ``assert_log_admin_access`` de la referencia hace dos cosas:
verifica que el usuario sea administrador y **deja rastro en el log** de quién
lo invocó. Ambas se preservan: la capacidad se verifica en el llamador (la
vista, vía ``HasCapability`` — DEC-11, no ``IsAuthenticated`` a secas) y el
rastro se escribe con el nombre del usuario, igual que allá.

La referencia importa su cargador **dentro** del método (``import
odoo.modules.loading  # noqa: PLC0415``). Aquí eso no se copia: el gate de
``no-lazy-imports`` prohíbe el statement dentro de una función y no tiene
mecanismo ``noqa``; el import va al top, que además es lo que PEP 8 pide.
"""
import logging

from django.core.management import call_command

from orm.models_transient import TransientModel

_logger = logging.getLogger(__name__)

#: Comandos que pueblan los datos de ejemplo, en orden de dependencia. Son el
#: análogo local de ``odoo.modules.loading.force_demo``: la referencia recarga
#: sus módulos con la bandera ``demo``; aquí el seed es explícito por comando.
SEED_COMMANDS = (
    'seed_authz',
    'seed_menu',
    'seed_l0_chart',
    'seed_rate_cards',
)

#: Destino al que la referencia redirige tras instalar (``/odoo``). Aquí el
#: backoffice vive bajo ``/admin`` del SPA.
REDIRECT_URL = '/admin'


class IrDemo(TransientModel):
    """Asistente de instalación de datos de demostración (``ir.demo``).

    ``TransientModel`` con ``managed = False`` — no tiene tabla, igual que el
    asistente de la referencia no guarda estado propio entre invocaciones.
    """

    class Meta:
        abstract = True
        managed = False

    def install_demo(self, user=None):
        """Puebla los datos de demostración y devuelve el destino de redirección.

        El llamador **debe** haber verificado la capacidad de administración
        antes (DEC-11). Este método deja el rastro que
        ``assert_log_admin_access`` deja allá, no lo sustituye.

        Devuelve el mismo trío que la referencia (tipo de acción, destino y
        URL) para que el consumidor lea igual que su fuente.
        """
        _logger.info(
            'install_demo invocado por %s',
            getattr(user, 'email', None) or '<sin usuario>',
        )
        for command in SEED_COMMANDS:
            call_command(command)
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': REDIRECT_URL,
        }
