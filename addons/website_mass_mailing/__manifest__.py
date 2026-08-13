# Adaptado de Odoo Community `website_mass_mailing/__manifest__.py` (LGPL-3,
# odoo19c:) — atribución y aviso de licencia preservados (DEC-KX-03).
{
    'name': 'Suscripción al boletín',
    'version': '1.0',
    'category': 'Website/Website',
    'summary': (
        'El alta al boletín desde el sitio público: registra el contacto en '
        'la lista y confirma por correo'
    ),
    # `depends` MEDIDO da ['base', 'mass_mailing'] y la referencia declara
    # ['website', 'mass_mailing'] — el par que define al puente. Se declara
    # `website` por fidelidad al encuadre: el alta ocurre EN el sitio. El
    # import todavía no existe porque el modelo `website` está sin portar
    # (tarea #103).
    'depends': [
        'base',           # ResPartner — el suscriptor
        'mass_mailing',   # MailingList — la lista a la que se da de alta
        'website',        # el sitio desde el que se suscribe (fidelidad a la ref)
    ],
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'application': False,
    'installable': True,
    'auto_install': False,
}
