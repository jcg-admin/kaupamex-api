"""Security — ``addons.account_update_tax_tags``.

Espejo de ``security/`` de la referencia
(``odoo19c: addons/account_update_tax_tags/security/ir.model.access.csv``):

.. code-block:: text

    access_account_update_tax_tags_wizard,access.account.update.tax.tags.wizard,
    model_account_update_tax_tags_wizard,account.group_account_manager,1,1,1,0

Una sola ACL, sobre la tabla del wizard, para el grupo de gerencia contable.

Por qué no hay ``authz_catalog.py`` aquí
============================================

``account_update_tax_tags`` no dueña un dominio de capacidad nuevo: opera
**sobre** ``account.move.line`` (vía sus puentes, ver ``models/``), que ya
dueña ``account`` con la capacidad ``invoices`` (``account/authz_catalog.py``:
*"invoices — account dueña account.move — la factura es un asiento"*).
Declarar una capacidad ``account_update_tax_tags.*`` aparte duplicaría el
dominio que ``invoices`` ya cubre — mismo criterio que
``account_debit_note/security/__init__.py``.

Además, la ACL de la referencia gatea la tabla del **wizard**
(``account.update.tax.tags.wizard``), que aquí no tiene tabla
(``TransientModel``, ``managed = False`` — ver
``wizard/account_update_tax_tags_wizard.py``). El enforcement lo ejerce
``controllers/views.py::recalculate_tax_tags`` (H-API-406, tarea #52;
UC-FIN-11) — gateada por ``HasCapability('invoices')``, no por una capacidad
nueva.
"""
