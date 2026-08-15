"""``utm_source_data`` — las diez fuentes de enlace que la fuente siembra.

Adaptación de ``odoo19c: addons/utm/data/utm_source_data.xml``
(``odoo-tools@622ddc2a``, LGPL-3; ``noupdate="1"``).

``utm.utm_source_referral`` lo resuelve ``UtmSource._unlink_except_referral``
para impedir su borrado; sin la fila de ``ir.model.data`` esa guarda no
protegería nada.
"""

UTM_SOURCES = [
    {'xmlid': 'utm.utm_source_search_engine', 'name': 'Search engine'},
    {'xmlid': 'utm.utm_source_mailing', 'name': 'Lead Recall'},
    {'xmlid': 'utm.utm_source_newsletter', 'name': 'Newsletter'},
    {'xmlid': 'utm.utm_source_facebook', 'name': 'Facebook'},
    {'xmlid': 'utm.utm_source_twitter', 'name': 'X'},
    {'xmlid': 'utm.utm_source_linkedin', 'name': 'LinkedIn'},
    {'xmlid': 'utm.utm_source_monster', 'name': 'Monster'},
    {'xmlid': 'utm.utm_source_glassdoor', 'name': 'Glassdoor'},
    {'xmlid': 'utm.utm_source_craigslist', 'name': 'Craigslist'},
    {'xmlid': 'utm.utm_source_referral', 'name': 'Referral'},
]
