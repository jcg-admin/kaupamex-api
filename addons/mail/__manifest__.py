# Adaptado de Odoo Community `mail/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Mensajería y avisos',
    'version': '1.0',
    'category': 'Productivity/Discuss',
    'summary': (
        'MailThread, MailMessage, MailTemplate y la cola de envío: el hilo '
        'que cualquier modelo hereda para dejar rastro y avisar'
    ),
    # `depends` MEDIDO da cuatro; la referencia declara ['base', 'base_setup',
    # 'bus'] más `web_tour`/`html_editor`, que este árbol no tiene.
    # `base_setup`
    # hospeda la UI de ajustes del servidor de correo; aquí eso es
    # SystemParameter de `base`.
    #
    # La arista `mail → sms` NO se declara: es una inversión. En la referencia
    # `sms` depende de `mail` (el SMS es otro canal del mismo hilo), nunca al
    # revés. Registrada aquí y en el gate de dirección
    # (`scripts/check_addon_cycles.py`), no legitimada.
    #
    # `authz` es el gate de capacidad de las vistas DRF, no dependencia de
    # datos — tampoco se declara (ver lote 2).
    'depends': [
        'base',  # ResUsers, ResPartner, ResCompany
        'bus',  # el canal por el que se notifica el mensaje nuevo
    ],
    # ≙ ``data`` de la fuente (``odoo19c: addons/mail/__manifest__.py:64``):
    # los grupos y el CSV de acceso; el resto de la lista entra con su modelo.
    # Del CSV quedan las 4 filas cuyo modelo tiene fila en ``ir.model``: las 65
    # restantes nombran modelos sin puerto (``discuss.*``, ``mail.push``…) o
    # sin cabecera de la fuente (``mail.message``, ``mail.mail``…). Vuelven con
    # ``mail-model-headers-0397``.
    'data': [
        'data/mail_groups.xml',
        'security/ir.model.access.csv',
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': True,
    'installable': True,
    'auto_install': False,
}
