"""Los cuatro archivos de ``base_vat`` — ≙ ``models/__init__.py`` de la fuente.

``odoo19c: addons/base_vat/models/__init__.py`` importa cuatro módulos:
``res_partner``, ``res_company``, ``res_config_settings`` y ``res_country``.
Los cuatro están portados; aquí sólo se importan para que sus funciones de
extensión sean alcanzables. Quien las **aplica** es ``BaseVatConfig.ready()``,
porque el ``_inherit`` de la fuente aquí es un ``extend_model`` en tiempo de
arranque y no una declaración de clase.
"""
from addons.base_vat.models import res_company  # noqa: F401 — _inherit
from addons.base_vat.models import res_config_settings  # noqa: F401 — _inherit
from addons.base_vat.models import res_country  # noqa: F401 — _inherit
from addons.base_vat.models import res_partner  # noqa: F401 — _inherit
