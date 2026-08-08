"""El único parámetro de configuración de la referencia — ≙ ``odoo19c:
account_payment/data/ir_config_parameter.xml``:

.. code-block:: xml

    <record id="enable_portal_payment" model="ir.config_parameter" forcecreate="0">
        <field name="key">account_payment.enable_portal_payment</field>
        <field name="value">True</field>
    </record>

Se siembra vía ``SystemParameter`` (``api:
base/models/ir_config_parameter.py``, ≙ ``ir.config_parameter``) — mismo
patrón que ``account_fleet/data/fleet_service_types.py``, adaptado: aquí no
hace falta ``ir.model.data`` porque ``SystemParameter`` se identifica por
``key`` (columna única), no por identificador externo — la referencia lo
usa (``id="enable_portal_payment"``) sólo para que otros módulos puedan
referenciar el ``<record>`` vía ``ref()``, lo cual esta portación no
necesita.

**Declarado, no usado todavía**: el valor se siembra fiel a la referencia
(``'True'``), pero ningún código de este addon lo lee — ``_has_to_be_paid``
(el único consumidor en la referencia) no se porta (ver
``models/account_move.py``, sección "No portado"). Sembrarlo igual es
correcto: es DATO, independiente de qué lo consuma; y deja la puerta
abierta a que un futuro consumidor lo encuentre ya presente.
"""
#: Nombre completo de la clave — ≙ el ``<field name="key">`` del ``<record>``.
ENABLE_PORTAL_PAYMENT_KEY = 'account_payment.enable_portal_payment'

#: Valor sembrado — ≙ el ``<field name="value">`` (``True``, como cadena:
#: ``SystemParameter.value`` es ``TextField``, igual que Odoo lo serializa).
ENABLE_PORTAL_PAYMENT_VALUE = 'True'


def seed_config_parameters(apps, alias):
    """Crea (o respeta) el parámetro ``account_payment.enable_portal_payment``.

    Escribe sobre el modelo **histórico** (``apps.get_model``) porque corre
    dentro de una migración — mismo criterio que ``account/data/
    account_tags.py``. Idempotente: sólo crea la clave si no existe (≙
    ``noupdate="1"`` del XML original — no repunta un valor que el operador
    haya cambiado a mano).
    """
    SystemParameter = apps.get_model('base', 'SystemParameter')
    SystemParameter.objects.using(alias).get_or_create(
        key=ENABLE_PORTAL_PAYMENT_KEY,
        defaults={'value': ENABLE_PORTAL_PAYMENT_VALUE},
    )
