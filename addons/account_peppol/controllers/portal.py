"""Portal del cliente — los campos Peppol en su dirección. BLOQUEADO.

Adaptación de Odoo ``account_peppol/controllers/portal.py``
(``odoo19c: addons/account_peppol/controllers/portal.py``, 55 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no declara ninguna vista** y no exporta nada. Existe para
conservar el SITIO del archivo contra la referencia.

Porte símbolo por símbolo — 3 símbolos, los 3 bloqueados
==========================================================

.. list-table::
   :header-rows: 1
   :widths: 44 56

   * - Símbolo (línea)
     - Desenlace
   * - ``_prepare_my_account_rendering_values`` (``:16-23``)
     - BLOQUEADO — añade a la plantilla del portal la lista de códigos EAS
       disponibles (``available_peppol_eas``), campo de
       ``account_edi_ubl_cii`` (0 hits medidos aquí). Además es contexto de
       una plantilla QWeb del portal, y ``IrTemplateExpressions.render`` de este árbol
       levanta ``NotImplementedError`` a propósito
       (``src/addons/base/models/ir_template_expressions.py:261``).
   * - ``_get_mandatory_billing_address_fields`` (``:25-32``)
     - BLOQUEADO — hace obligatorios ``peppol_eas`` y ``peppol_endpoint`` en
       la dirección de facturación cuando el país está en ``PEPPOL_LIST``
       (``odoo19c: account/models/company.py``, 0 hits aquí). Doble arista:
       ``account_edi_ubl_cii`` y ``account``.
   * - ``_validate_address_values`` (``:34-55``)
     - BLOQUEADO — valida ese par contra las reglas de endpoint por EAS, que
       en este árbol están recortadas por ``python-stdnum`` (0 hits en
       ``uv.lock``; ver ``models/res_company.py``).

Bloqueador transversal, el mismo que las otras dos rutas: el cableado de URLs
vive en ``src/config/urls.py``, fuera de este write-set, y el portal de este
árbol (``addons/portal/``) sirve por DRF, no por QWeb.

**Sucesor:** tarea PENDIENTE DE ASIGNAR (resumen de este pase) — cuando
``account_edi_ubl_cii`` aterrice y el portal exponga la dirección de
facturación por DRF, los tres símbolos se expresan como campos y validadores
del serializador, no como ganchos de plantilla.
"""
