"""Modelos del addon ``website`` — paquete espejo de ``addons/website/models/``.

Un archivo por modelo, como la referencia y como ``base``:

- ``website_menu.py`` → ``WebsiteMenu`` (``website.menu``: menú de la cara
  pública, gemelo de ``base.IrUiMenu``).
- ``static_content.py`` → ``StaticContent`` + ``StaticContentVersion``.
- ``static_page.py`` → ``StaticPage`` + ``StaticPageVersion``.
- ``banner.py`` → ``Banner``.
- ``search_entry.py`` → ``SearchEntry``.

**Sólo ``website_menu`` está alineado con la referencia.** Los otros cuatro
archivos conservan modelos propios cuyo mapeo a ``website.page`` /
``website.track`` está medido pero **no** ejecutado: portar ``website.page``
fiel arrastra ``ir.ui.view`` (delegación ``_inherits``), que este árbol no
tiene. Además ``static_content`` y ``static_page`` **duplican** el mismo
propósito, donde la referencia tiene un solo modelo. Todo eso vive en la
iniciativa ``alinear-addon-website-referencia``.

Se reexporta aquí para preservar el contrato ``from addons.website.models
import StaticContent, ...``.
"""
from .banner import Banner
from .search_entry import SearchEntry
from .website import Website
from .static_content import StaticContent, StaticContentVersion
from .static_page import StaticPage, StaticPageVersion
from .website_menu import WebsiteMenu

__all__ = [
    'Banner',
    'SearchEntry',
    'StaticContent',
    'StaticContentVersion',
    'StaticPage',
    'StaticPageVersion',
    'WebsiteMenu',
]
