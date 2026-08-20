"""AppConfig — addons.observability (DEC-12): addon net-new, sin analogo Odoo.

``addons.observability`` aloja el **evento de negocio** (``BusinessEvent``,
DEC-LOG-01..08): una fila por hecho de dominio —pedido pagado, envío
despachado— que la referencia no modela como capa consultable. Por eso es la
**excepcion deliberada** (DEC-12) a la regla de portacion fiel Odoo que
gobierna el resto de ``addons/``: los demas addons son o adaptaciones de un
modulo Odoo real, o quedan ausentes por no aplicar.

**``RequestLog`` ya no vive aqui (DEC-AF-11).** El addon nacio con dos
modelos; el ejecutor partio el segundo en sus dos mitades —la de error se
fundio en ``ir.logging``, la de acceso es trabajo del ``access_log`` del proxy
inverso— y con el se fueron su middleware, su handler de excepciones y su
vista de administracion. Lo que queda es ``BusinessEvent``, y su destino
declarado es ``mail`` (la referencia lo modela como ``mail.message`` /
``mail.tracking.value``): mientras esa mudanza no ocurra, el addon sobrevive
como su hogar.

``addons.observability`` vive en el **plano de control** (base ``default``):
``BusinessEvent`` es telemetria global de la instancia, no per-empresa -- por
eso su app_label ``observability`` se registra en
``MULTIDB_CONTROL_PLANE_APPS`` junto a ``base``, igual que ``SystemParameter``
e ``IrLogging``.
"""
from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'addons.observability'
    label = 'observability'
    verbose_name = 'Observability (evento de negocio, net-new DEC-12)'
