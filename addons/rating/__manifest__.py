# Adaptado de Odoo Community `rating/__manifest__.py` (LGPL-3, odoo19c:)
# — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Calificación del cliente',
    'version': '1.0',
    'category': 'Productivity',
    'summary': (
        'Rating y su token de un solo uso: la valoración que el cliente '
        'deja sobre un registro, y la reseña de producto'
    ),
    # `depends` MEDIDO da cuatro; la referencia declara sólo ['mail'].
    #
    # Dos aristas NO se declaran porque invierten la dirección: `rating → sale`
    # y `rating → product` vienen de la reseña de producto, que en la
    # referencia es `portal_rating`/`website_sale` —addons que dependen de
    # `rating`, no al revés—. Registradas, no legitimadas: el gate de dirección
    # (`scripts/check_addon_cycles.py`) es su dueño.
    'depends': [
        'base',  # ResPartner — quien califica
        'mail',  # MailThread — el hilo que envía la invitación
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
