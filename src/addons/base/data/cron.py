"""Siembra de registros ``ir.cron`` — helper compartido por los addons.

La referencia declara cada tarea programada como un ``<record
model="ir.cron">``
en el ``data/ir_cron_data.xml`` de su addon, con ``noupdate="1"`` para que una
actualización no pise lo que el operador haya ajustado (``odoo19c: mail/data/
ir_cron_data.xml:3``, ``odoo-tools@622ddc2a``). Aquí el equivalente es una
**data-migration por addon** que importa su spec y llama a ``sembrar_cron``.

Por qué un helper y no cuatro copias: la siembra de un cron son **dos** filas
—``ir.actions.server`` (el qué) e ``ir.cron`` (el cada-cuánto)— unidas por FK,
y esa costura es idéntica en todos los addons. Repetirla cuatro veces es cuatro
oportunidades de que una diverja.

**Idempotencia.** La clave natural es el ``xml_id`` del spec: el ``id`` del
``<record model="ir.cron">`` de la fuente, que es como la fuente identifica el
cron y como sus consumidores lo piden (``env.ref``). Una base sembrada antes
de que el spec declarara ``xml_id`` no tiene aún su fila de ``ir.model.data``;
ahí la siembra encuentra la acción por ``(model_name, method_name)`` y le
vincula el ``xml_id`` (``designs/cron-xml-id-natural-key.md``). Un segundo
pase no duplica ni pisa el intervalo — si el operador cambió la periodicidad,
se respeta, que es lo que ``noupdate`` garantiza en la referencia.
"""

from django.apps import apps as apps_vivos

from orm import registry


def cron_code(spec):
    """El ``code`` que ejecuta el cron de ``spec``: el que declare, o
    ``model.<method_name>()`` — la llamada que el corredor de métodos hacía
    antes de que el cron ejecutara su acción
    (``designs/cron-runs-server-action.md``)."""
    return spec.get('code') or f"model.{spec['method_name']}()"


def _fill_code(action, spec):
    """Completa el ``code`` de una acción ya sembrada sin él: la siembra es
    idempotente por ``(model_name, method_name)`` y una acción anterior a
    que el cron ejecutara ``code`` lo tiene vacío."""
    if not action.code:
        action.code = cron_code(spec)
        action.save(update_fields=['code'])


def sembrar_cron(apps, alias, spec):
    """
    Crea (o respeta) el par acción + cron de ``spec``. Devuelve ``(cron,
    creado)``.

    ``spec`` lleva: ``name``, ``model_name``, ``method_name``,
    ``interval_number``, ``interval_type`` y ``priority``; y, opcionales,
    ``code`` (por defecto ``model.<method_name>()``, ver ``cron_code``),
    ``active`` (por defecto ``True``) y ``xml_id`` (``'modulo.nombre'``), el
    identificador externo con que la fuente declara el ``<record>`` y con que
    sus consumidores lo piden (``env.ref``). Un cron que nace inactivo, como
    ``account_edi.ir_cron_edi_network``, los necesita los dos.

    Escribe sobre los modelos **históricos** (``apps.get_model``), nunca sobre
    los vivos: una migración no debe ejecutar comportamiento de la app, que
    cambia bajo sus pies.
    """
    IrActionsServer = apps.get_model('base', 'IrActionsServer')
    IrCron = apps.get_model('base', 'IrCron')
    IrModelData = apps.get_model('base', 'IrModelData')

    accion = _find_seeded_action(IrModelData, IrCron, IrActionsServer,
                                 alias, spec)
    _fill_code(accion, spec)

    cron, creado = IrCron.objects.using(alias).get_or_create(
        ir_actions_server=accion,
        defaults={
            'interval_number': spec['interval_number'],
            'interval_type': spec['interval_type'],
            'priority': spec['priority'],
            'active': spec.get('active', True),
        },
    )
    _register_xml_id(IrModelData, alias, spec, cron)
    return cron, creado


def sembrar_cron_vivo(spec):
    """Igual que ``sembrar_cron`` pero con los modelos **vivos** — H-API-22.

    Una data-migration siembra con ``apps.get_model`` porque no debe ejecutar
    comportamiento de la app. El **fixture de restauracion** del conftest tiene
    el problema opuesto: corre fuera de toda migracion y no tiene ``apps``.

    Por que hace falta. Un test ``django_db(transaction=True)`` es un
    ``TransactionTestCase``: Django hace ``flush`` de todas las tablas de
    modelo en su teardown, pero ``django_migrations`` **no** es tabla de
    modelo. La semilla desaparece y la migracion sigue registrada como
    aplicada, asi que no vuelve a correr nunca. Es exactamente H-API-22, y las
    siete siembras de cron del arbol estaban fuera de su red.

    Escribe sobre el mismo ``spec`` que la migracion importa: no hay dos copias
    que puedan divergir.
    """
    IrActionsServer = apps_vivos.get_model('base', 'IrActionsServer')
    IrCron = apps_vivos.get_model('base', 'IrCron')
    IrModelData = apps_vivos.get_model('base', 'IrModelData')

    accion = _find_seeded_action(IrModelData, IrCron, IrActionsServer,
                                 None, spec)
    _fill_code(accion, spec)
    cron, creado = IrCron.objects.get_or_create(
        ir_actions_server=accion,
        defaults={
            'interval_number': spec['interval_number'],
            'interval_type': spec['interval_type'],
            'priority': spec['priority'],
            'active': spec.get('active', True),
        },
    )
    _register_xml_id(IrModelData, None, spec, cron)
    return cron, creado


def _register_xml_id(ir_model_data, alias, spec, cron):
    """Graba el identificador externo del cron si el ``spec`` lo declara y
    aún no existe — ≙ el ``id`` del ``<record model="ir.cron">`` de la
    fuente, con ``noupdate`` como su ``<odoo noupdate="1">``. Mismo patrón que
    ``mail.data.register_subtype_xmlids``."""
    xml_id = spec.get('xml_id')
    if not xml_id:
        return
    module, _, name = xml_id.partition('.')
    manager = (ir_model_data.objects.using(alias) if alias
               else ir_model_data.objects)
    if manager.filter(module=module, name=name).exists():
        return
    manager.create(module=module, name=name,
                   model=registry.identity_for_key('base.IrCron'),
                   res_id=cron.pk, noupdate=True)


def _find_seeded_action(ir_model_data, ir_cron, ir_actions_server, alias,
                        spec):
    """La acción del cron de ``spec``, creada si no existe.

    Con ``xml_id`` declarado y ya registrado, la acción es la del cron que
    ``ir.model.data`` nombra — la identidad de la fuente, sea cual sea el
    método que hoy ejecute. Sin esa fila (base sembrada antes del ``xml_id``,
    o spec que no lo declara) la clave es ``(model_name, method_name)``.
    """
    using = (lambda manager: manager.using(alias)) if alias else (
        lambda manager: manager)
    xml_id = spec.get('xml_id')
    if xml_id:
        module, _, name = xml_id.partition('.')
        row = using(ir_model_data.objects).filter(
            module=module, name=name).first()
        if row is not None:
            cron = using(ir_cron.objects).filter(pk=row.res_id).first()
            if cron is not None:
                return cron.ir_actions_server
    accion, _ = using(ir_actions_server.objects).get_or_create(
        model_name=registry.identity_for_key(spec['model_name']),
        method_name=spec['method_name'],
        defaults={
            'name': spec['name'],
            # ≙ ``<field name="state">code</field>`` de cada cron de la
            # fuente: el cron ejecuta este ``code`` (``ir_cron._callback``).
            'state': 'code',
            'code': cron_code(spec),
        },
    )
    return accion
