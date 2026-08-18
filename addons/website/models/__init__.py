"""Modelos del addon ``website`` — paquete espejo de ``addons/website/models/``.

Un archivo por modelo, como la referencia y como ``base``:

- ``website_menu.py`` → ``WebsiteMenu`` (``website.menu``: menú de la cara
  pública, gemelo de ``base.IrUiMenu``).
- ``website_page.py`` → ``WebsitePage`` (``website.page``, delegando en
  ``ir.ui.view`` por ``_inherits``) + ``PageCannotBeCached`` (#104).
- ``website_rewrite.py`` → ``WebsiteRoute`` + ``WebsiteRewrite``
  (``website.route`` / ``website.rewrite``) (#104).
- ``static_content.py`` → ``StaticContent`` + ``StaticContentVersion``.
- ``static_page.py`` → ``StaticPage`` + ``StaticPageVersion``.
- ``banner.py`` → ``Banner``.
- ``search_entry.py`` → ``SearchEntry``.

**Los modelos propios ``static_*`` se conservan como interinato.** #104
alineó ``website.page``/``website.rewrite``/``website.route`` con la
referencia; los pares ``StaticContent``/``StaticPage`` duplican el mismo
propósito y quedan **absorbidos en papel pero no en datos**: su flujo
editorial (DRAFT→PUBLISHED con historial) y sus consumidores REST no caben
en el pase sin pérdida — la decisión completa está en el docstring de
``website_page.py`` y en los suyos.

Se reexporta aquí para preservar el contrato ``from addons.website.models
import StaticContent, ...``.
"""
from .banner import Banner
from .ir_http import IrHttp
from .search_entry import SearchEntry
from .website import Website
from .website_page import PageCannotBeCached, WebsitePage
from .website_rewrite import WebsiteRewrite, WebsiteRoute
from .static_content import StaticContent, StaticContentVersion
from .static_page import StaticPage, StaticPageVersion
from .website_configurator_feature import WebsiteConfiguratorFeature
from .website_menu import WebsiteMenu

__all__ = [
    'Banner',
    'IrHttp',
    'PageCannotBeCached',
    'SearchEntry',
    'StaticContent',
    'StaticContentVersion',
    'StaticPage',
    'StaticPageVersion',
    'WebsiteConfiguratorFeature',
    'WebsiteMenu',
    'WebsitePage',
    'WebsiteRewrite',
    'WebsiteRoute',
]
