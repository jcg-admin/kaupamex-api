"""Siembra de registros ``ir.cron`` — helper compartido por los addons.

La referencia declara cada tarea programada como un ``<record model="ir.cron">``
en el ``data/ir_cron_data.xml`` de su addon, con ``noupdate="1"`` para que una
actualización no pise lo que el operador haya ajustado (``odoo19c: mail/data/
ir_cron_data.xml:3``, ``odoo-tools@622ddc2a``). Aquí el equivalente es una
**data-migration por addon** que importa su spec y llama a ``sembrar_cron``.

Por qué un helper y no cuatro copias: la siembra de un cron son **dos** filas
—``ir.actions.server`` (el qué) e ``ir.cron`` (el cada-cuánto)— unidas por FK,
y esa costura es idéntica en todos los addons. Repetirla cuatro veces es cuatro
oportunidades de que una diverja.

**Idempotencia.** La clave natural es ``(model_name, method_name)``: la
identidad de un job es *qué ejecuta*, no cómo se llama en la interfaz. Un
segundo pase no duplica ni pisa el intervalo — si el operador cambió la
periodicidad, se respeta, que es lo que ``noupdate`` garantiza en la referencia.
"""
from django.apps import apps as apps_vivos


def sembrar_cron(apps, alias, spec):
    """Crea (o respeta) el par acción + cron de ``spec``. Devuelve ``(cron, creado)``.

    ``spec`` lleva: ``name``, ``model_name``, ``method_name``,
    ``interval_number``, ``interval_type`` y ``priority``.

    Escribe sobre los modelos **históricos** (``apps.get_model``), nunca sobre
    los vivos: una migración no debe ejecutar comportamiento de la app, que
    cambia bajo sus pies.
    """
    IrActionsServer = apps.get_model('base', 'IrActionsServer')
    IrCron = apps.get_model('base', 'IrCron')

    accion, _ = IrActionsServer.objects.using(alias).get_or_create(
        model_name=spec['model_name'],
        method_name=spec['method_name'],
        defaults={
            'name': spec['name'],
            # 'code' es el modo de la referencia, que EVALÚA Python. Aquí el
            # qué-ejecutar es method_name (adaptación declarada en ir_actions),
            # pero el state se conserva para no inventar un valor fuera del
            # vocabulario del modelo.
            'state': 'code',
            'code': '',
        },
    )

    cron, creado = IrCron.objects.using(alias).get_or_create(
        ir_actions_server=accion,
        defaults={
            'interval_number': spec['interval_number'],
            'interval_type': spec['interval_type'],
            'priority': spec['priority'],
            'active': True,
        },
    )
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

    accion, _ = IrActionsServer.objects.get_or_create(
        model_name=spec['model_name'],
        method_name=spec['method_name'],
        defaults={
            'name': spec['name'],
            'state': 'code',
            'code': '',
        },
    )
    cron, creado = IrCron.objects.get_or_create(
        ir_actions_server=accion,
        defaults={
            'interval_number': spec['interval_number'],
            'interval_type': spec['interval_type'],
            'priority': spec['priority'],
            'active': True,
        },
    )
    return cron, creado
