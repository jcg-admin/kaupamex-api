# Adaptado de Odoo Community `base_automation/__manifest__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Reglas de automatización (base.automation)',
    'version': '1.0',
    'category': 'Technical',
    'summary': (
        'base.automation — reglas declarativas por evento (create/write/'
        'unlink vía señales globales de Django) y por tiempo (ir.cron)'
    ),
    # `depends` MEDIDO contra los imports reales de este addon (base, mail,
    # resource). La referencia declara además `digest` y `sms`: `sms` no
    # existe en este árbol, y `digest` allá sólo aporta el disparador de KPI
    # que este porte no consume — ambos se omiten con esa razón declarada.
    'depends': [
        # IrActionsServer, IrCron, IrLogging, IrModel*, TimeStampedModel
        'base',
        'mail',      # MailThread, MailActivityMixin
        'resource',  # ResourceCalendar (trg_date_calendar_id)
    ],
    'license': 'LGPL-3',
    # Seguridad de la fuente (``odoo19c:
    # addons/base_automation/__manifest__.py:20``), por ``load_data`` en el
    # ciclo de instalación: copia fiel del CSV.
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
}
