# Adaptado de Odoo Community `digest/__manifest__.py` (LGPL-3) — atribución
# y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Digests de KPIs periódicos',
    'version': '1.0',
    'category': 'Marketing',
    'summary': (
        'digest.digest + digest.tip — motor de cómputo de KPIs por periodo '
        '(el envío queda pendiente de cablear a la familia mail, no de '
        'construir: ver divergencia 7 y H-API-302)'
    ),
    # `depends` MEDIDO contra los imports reales de los modelos portados
    # (`get_current_company`/`get_current_user` de `orm`, no de un addon):
    # sólo `base` (TimeStampedModel, ResCompany, ResUsers, ResUsersLog,
    # SystemParameter) y `mail` (MailMessage, para el KPI de mensajes). La
    # referencia también depende de `portal`/`resource` — ninguno de los dos
    # es consumido por este porte (ver "Consumidores medidos" del análisis).
    'depends': [
        'base',      # TimeStampedModel, ResCompany, ResUsers, ResUsersLog,
                     # SystemParameter
        'mail',      # MailMessage (KPI kpi_mail_message_total)
    ],
    # Licencia de la fuente de la que se adapta este addon, tal como su
    # manifest la declara (DEC-KX-03 punto 1): `digest` en Odoo Community es
    # LGPL-3.
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
