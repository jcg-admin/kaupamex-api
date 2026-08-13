"""El tipo de servicio semilla «Vendor Bill».

≙ ``odoo19c: account_fleet/data/fleet_service_type_data.xml``
(``odoo-tools@622ddc2a``, LGPL-3):

.. code-block:: xml

    <record id="data_fleet_service_type_vendor_bill" model="fleet.service.type">
        <field name="name">Vendor Bill</field>
        <field name="category">service</field>
    </record>

Un único registro de ``fleet.service.type`` (modelo ya existente en
``fleet``, no se agrega columna alguna) más su identificador externo
(``ir.model.data``, tabla de ``base``). Es la fila que
``models/account_move.py::_create_fleet_service_bills_on_post`` busca por
xmlid antes de crear cualquier servicio — sin ella, el posteo de una factura
con vehículo no crea nada (mismo guard que la referencia: ``if not
vendor_bill_service: return super()._post(soft)``).

**El nombre queda verbatim en inglés** — "Vendor Bill" es el dato copiado de
la referencia (mismo criterio que ``account/data/account_tags.py`` para sus
tres etiquetas maestras: son datos, no cadenas de interfaz de este puerto).
"""
#: Nombre del identificador externo, sin el módulo — ≙ el ``id`` del
#: ``<record>`` de la referencia.
VENDOR_BILL_SERVICE_NAME = 'data_fleet_service_type_vendor_bill'

#: Identificador externo completo, tal como lo cita el código
#: (``account_move.py::VENDOR_BILL_SERVICE_XMLID``).
VENDOR_BILL_SERVICE_XMLID = f'account_fleet.{VENDOR_BILL_SERVICE_NAME}'

#: Los dos campos del ``<record>`` de la referencia.
VENDOR_BILL_SERVICE_TYPE_NAME = 'Vendor Bill'
VENDOR_BILL_SERVICE_TYPE_CATEGORY = 'service'


def seed_fleet_service_types(apps, alias):
    """Crea (o respeta) el tipo de servicio «Vendor Bill» y su identificador
    externo.

    Escribe sobre los modelos **históricos** (``apps.get_model``) porque
    corre dentro de una migración — mismo criterio que
    ``account.data.account_tags.seed_account_tags``: ejecutar comportamiento
    de la app viva desde una migración la ata a un estado del código que
    cambia bajo sus pies.

    Idempotente por ``(module, name)`` de ``ir.model.data`` — un segundo
    pase repunta la fila en vez de duplicarla, y no pisa un nombre que el
    operador haya ajustado a mano (``noupdate=True``, ≙ ``noupdate="1"`` del
    XML original).
    """
    FleetServiceType = apps.get_model('fleet', 'FleetServiceType')
    IrModelData = apps.get_model('base', 'IrModelData')
    label = FleetServiceType._meta.label

    row = IrModelData.objects.using(alias).filter(
        module='account_fleet', name=VENDOR_BILL_SERVICE_NAME).first()
    existing = None
    if row is not None:
        existing = FleetServiceType.objects.using(alias).filter(
            pk=row.res_id).first()
    if existing is None:
        existing = FleetServiceType.objects.using(alias).filter(
            name=VENDOR_BILL_SERVICE_TYPE_NAME,
            category=VENDOR_BILL_SERVICE_TYPE_CATEGORY).first()
    if existing is None:
        existing = FleetServiceType.objects.using(alias).create(
            name=VENDOR_BILL_SERVICE_TYPE_NAME,
            category=VENDOR_BILL_SERVICE_TYPE_CATEGORY)
    IrModelData.objects.using(alias).update_or_create(
        module='account_fleet', name=VENDOR_BILL_SERVICE_NAME,
        defaults={'model': label, 'res_id': existing.pk, 'noupdate': True},
    )
    return existing
