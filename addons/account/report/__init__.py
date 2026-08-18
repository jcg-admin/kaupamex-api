"""Reportes del addon ``account``.

Adaptacion de ``odoo19c: addons/account/report/__init__.py``
(``odoo-tools@622ddc2a``, LGPL-3 -- atribucion y aviso de licencia
preservados, DEC-KX-03).

Cobertura del porte -- 2 de 2 simbolos (imports de submodulo)
================================================================

.. list-table::
   :header-rows: 1

   * - Simbolo
     - Estado
   * - ``from . import account_invoice_report``
     - portado verbatim
   * - ``from . import account_hash_integrity_templates``
     - portado verbatim

**Nota de registro (no es divergencia de ESTE archivo).** Este paquete no
esta importado todavia desde ``addons/account/models/__init__.py`` -- el
unico punto donde Django importa el paquete ``models`` de una app durante
``AppConfig.import_models()`` (fase 2 de ``apps.populate()``). Cablearlo ahi
es lo que registraria ``AccountInvoiceReport`` en el registro vivo de Django;
ese archivo esta fuera de mi alcance de escritura en la tarea #398
(``addons/account/models/**``). Ver el hallazgo H-API-682 para el detalle
completo del bloqueo y su sucesor.
"""
from . import account_hash_integrity_templates  # noqa: F401
from . import account_invoice_report  # noqa: F401
