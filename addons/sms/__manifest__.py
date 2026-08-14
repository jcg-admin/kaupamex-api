# Adaptado de Odoo Community `sms/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Pasarela de SMS',
    'version': '1.0',
    'category': 'Sales/Sales',
    'summary': (
        'SmsSms y su composición desde el hilo: el mismo aviso de `mail` '
        'entregado por mensaje corto'
    ),
    # `depends` MEDIDO coincide EXACTO con la parte presente del de la
    # referencia (['base', 'mail']); sus otros dos —`iap_mail` y
    # `phone_validation`— no existen en este árbol.
    'depends': [
        'base',  # ResPartner — el número destinatario
        'mail',  # MailThread — el hilo del que sale el aviso
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
