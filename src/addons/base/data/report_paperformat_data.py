"""Los formatos de papel de ``base``: ``euro``, ``us`` y ``batch_deposit``.

≙ ``odoo19c: odoo/addons/base/data/report_paperformat_data.xml``, que el
manifiesto de ``base`` carga con ``noupdate="1"``. Aquí los datos de
``base`` los siembra una migración (mismo patrón que ``res_users_data.py`` y
``res_groups_data.py``), y ``noupdate`` significa lo mismo: se crea el
registro si su XML-ID no existe y no se toca si ya existe.

Lo consume ``ResCompany.init``, que da ``base.paperformat_euro`` a las
compañías sin formato (``odoo19c: odoo/addons/base/models/
res_company.py:102-109``).
"""
from django.apps import apps
from django.db import DEFAULT_DB_ALIAS

from addons.base.data.res_groups_data import _existing, _xmlid_row

#: ``(XML-ID, valores)`` en el orden del XML de la fuente, verbatim.
PAPERFORMATS = (
    ('paperformat_euro', {
        'name': 'A4', 'default': True, 'format': 'A4',
        'page_height': 0, 'page_width': 0, 'orientation': 'Portrait',
        'margin_top': 52, 'margin_bottom': 32, 'margin_left': 0,
        'margin_right': 0, 'header_line': False, 'header_spacing': 52,
        'dpi': 90, 'css_margins': True,
    }),
    ('paperformat_us', {
        'name': 'US Letter', 'default': True, 'format': 'Letter',
        'page_height': 0, 'page_width': 0, 'orientation': 'Portrait',
        'margin_top': 52, 'margin_bottom': 32, 'margin_left': 0,
        'margin_right': 0, 'header_line': False, 'header_spacing': 52,
        'dpi': 90, 'css_margins': True,
    }),
    ('paperformat_batch_deposit', {
        'name': 'US Batch Deposit', 'default': False, 'format': 'Letter',
        'page_height': 0, 'page_width': 0, 'orientation': 'Portrait',
        'margin_top': 15, 'margin_bottom': 30, 'margin_left': 10,
        'margin_right': 10, 'header_line': False, 'header_spacing': 15,
        'dpi': 90,
    }),
)


def seed_paperformats(apps, alias):
    """Crea los formatos cuyo XML-ID falta; no toca los existentes."""
    IrModelData = apps.get_model('base', 'IrModelData')
    ReportPaperformat = apps.get_model('base', 'ReportPaperformat')
    for name, values in PAPERFORMATS:
        if _existing(IrModelData, ReportPaperformat, alias, name) is not None:
            continue
        record = ReportPaperformat.objects.using(alias).create(**values)
        _xmlid_row(IrModelData, alias, name, record)


def seed(using=DEFAULT_DB_ALIAS):
    """La misma siembra sobre los modelos vivos (reposición tras ``flush``)."""
    seed_paperformats(apps, using)
