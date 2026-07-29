"""Registro de providers del framework de pagos — **por inscripción**.

En Odoo la resolución del provider es responsabilidad del framework
``payment`` (``payment.provider`` + su ``code``), y la dirección de la
dependencia va **del satélite al núcleo**: cada ``payment_<provider>``
declara ``depends: payment``; el núcleo no nombra a ningún provider
concreto.

Este módulo replica esa dirección (T-033). Antes importaba las 7 clases
concretas al tope, lo que invertía el patrón núcleo/satélite y ataba el
núcleo a sus proveedores — una de las 13 aristas que formaban el
componente cíclico de 28 addons (H-API-49).

Ahora el núcleo sólo expone el punto de registro; cada provider se
**inscribe** desde su propio ``gateway.py``, que su ``AppConfig.ready()``
importa. El núcleo conoce un **código** por defecto (dato, como
``payment.provider.code``), nunca una clase.

Importar siempre como ``from addons.payment.gateways.registry import
get_gateway``.
"""
import logging

from addons.payment.gateways.base import BaseGateway

logger = logging.getLogger('apps')

# Código del provider primario (BR-006: MP). Es un **dato**, no una clase:
# el núcleo no importa a ningún provider. Si el addon de ese código no
# está instalado, el registro queda sin él y ``get_gateway`` lo reporta.
DEFAULT_GATEWAY_CODE = 'MERCADOPAGO'

# Poblado por ``register_gateway`` desde cada ``payment_<provider>``.
GATEWAY_REGISTRY: dict[str, type[BaseGateway]] = {}


class GatewayNotRegistered(LookupError):
    """No hay ningún provider inscrito para el código solicitado.

    Se levanta sólo cuando falta también el primario — es decir, cuando
    ningún addon ``payment_*`` se inscribió. Un código desconocido con el
    primario presente cae al primario (comportamiento histórico).
    """


def register_gateway(code: str, gateway_cls: type[BaseGateway]) -> type[BaseGateway]:
    """Inscribe un provider bajo su código. Idempotente por código.

    La llama cada ``payment_<provider>/gateway.py`` a nivel de módulo. Se
    devuelve la clase para poder usarla como decorador si conviene.

    :param code: código del provider (``'MERCADOPAGO'``, ``'PAYPAL'``…).
    :param gateway_cls: subclase concreta de ``BaseGateway``.
    """
    previo = GATEWAY_REGISTRY.get(code)
    if previo is not None and previo is not gateway_cls:
        logger.warning(
            'register_gateway: el código %s ya estaba inscrito por %s; '
            'lo reemplaza %s', code, previo.__name__, gateway_cls.__name__,
        )
    GATEWAY_REGISTRY[code] = gateway_cls
    return gateway_cls


def get_gateway(gateway_type: str = DEFAULT_GATEWAY_CODE) -> BaseGateway:
    """Retorna la instancia del gateway solicitado.

    BR-006: MP es el gateway primario. BR-007: PayPal es el secundario
    disponible desde MVP. Tipos desconocidos caen al primario
    (comportamiento histórico preservado).

    :raises GatewayNotRegistered: si no hay provider para el código pedido
        **ni** para el primario — significa que ningún addon ``payment_*``
        se inscribió (app no instalada o ``ready()`` no corrió).
    """
    gateway_cls = GATEWAY_REGISTRY.get(gateway_type)
    if gateway_cls is None:
        gateway_cls = GATEWAY_REGISTRY.get(DEFAULT_GATEWAY_CODE)
    if gateway_cls is None:
        raise GatewayNotRegistered(
            f'No hay provider inscrito para {gateway_type!r} ni para el '
            f'primario {DEFAULT_GATEWAY_CODE!r}. ¿Falta el addon '
            f'payment_<provider> en INSTALLED_APPS?'
        )
    return gateway_cls()


def get_default_gateway() -> BaseGateway:
    """Retorna el gateway activo por defecto (BR-006: MP es el primario)."""
    return get_gateway(DEFAULT_GATEWAY_CODE)
