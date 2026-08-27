r"""``res.config.settings`` — el interruptor de alternativas de compra: NO PORTADO.

Adaptación de Odoo ``purchase_requisition/models/res_config_settings.py``
(``odoo19c: addons/purchase_requisition/models/res_config_settings.py``, 9
líneas, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

El único símbolo, y su bloqueo
================================

*Métrica:* entradas del cuerpo de ``class ResConfigSettings`` contadas por AST
sobre la fuente. Son **2** con ``_inherit``; **1** sin él:
``group_purchase_alternatives`` (``:7``), ningún método.

Su firma completa es::

    group_purchase_alternatives = fields.Boolean(
        "Purchase Alternatives",
        implied_group='purchase_requisition.group_purchase_alternatives')

``implied_group=`` es el mecanismo entero: el campo **no guarda nada**, activa
un grupo de acceso al marcarlo. Bloqueado por dos ausencias medidas:

.. code-block:: text

    grep -rn "implied_group" addons/ src/ --include=*.py   → 0
    grep -rn "class .*(ResConfigSettings)" src/addons addons --include=*.py
      → addons/base_setup/models/res_config_settings.py:108  SiteConfigSettings

Ni el mecanismo de grupo implicado ni un formulario de ajustes al que aportar
el campo. Es la **sexta** ocurrencia idéntica del árbol —``l10n_mx``,
``account_check_printing``, ``account``, ``stock``, ``purchase_stock`` y ésta—
y la decisión que las cierra a todas es la misma: **tarea #278**. Fabricar aquí
una subclase paralela produciría un formulario sin lector, que es la superficie
inventada que ``porte-completo-no-parcial.md`` prohíbe.

El grupo ``purchase_requisition.group_purchase_alternatives`` tampoco está
sembrado (este puerto no siembra datos XML). Su consumidor en la fuente es la
visibilidad del botón «crear alternativa» en la vista de la orden — capa de
presentación, no de negocio: ``PurchaseOrder.alternative_po_ids`` y
``button_confirm`` funcionan igual con o sin el grupo.
"""
