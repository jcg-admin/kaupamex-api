"""Modelos del addon ``website`` — paquete espejo de ``addons/website/models/``.

Un archivo por modelo, como la referencia y como ``base``:

- ``ir_ui_view.py`` → ``WebsiteViewInfo`` + ``apply_website_ir_ui_view_extensions``
  (la **extensión** que el addon del sitio cuelga sobre ``ir.ui.view``:
  visibilidad, contraseña, seguimiento y sitio de la vista, #565). No declara
  un modelo nuevo de la referencia — ``WebsiteViewInfo`` es la tabla lateral
  que D-1 de ese módulo explica.
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
- ``mixins.py`` → los cuatro mixins abstractos del sitio: publicación,
  búsqueda y el par de opciones de página (``website.page_options.mixin`` +
  ``website.page_visibility_options.mixin``, #561).

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
from .ir_ui_view import (
    WebsiteViewInfo,
    apply_website_ir_ui_view_extensions,
)
from .mixins import (
    WebsitePageOptionsMixin,
    WebsitePageVisibilityOptionsMixin,
    WebsitePublishedMixin,
    WebsiteSearchableMixin,
)
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
    'WebsitePageOptionsMixin',
    'WebsitePageVisibilityOptionsMixin',
    'WebsitePublishedMixin',
    'WebsiteRewrite',
    'WebsiteRoute',
    'WebsiteSearchableMixin',
    'WebsiteViewInfo',
    'apply_website_ir_ui_view_extensions',
]
