"""Security — ``addons.account_debit_note``.

Espejo de ``security/`` de la referencia
(``odoo19c: addons/account_debit_note/security/ir.model.access.csv``):

.. code-block:: text

    "access_account_debit_note_user","account_debit_note_group_invoice",
    "model_account_debit_note","account.group_account_invoice",1,1,1,0

Una sola ACL, sobre la tabla del wizard, para el grupo de facturación.

Por qué no hay ``authz_catalog.py`` aquí
============================================

``account_debit_note`` no dueña un dominio de capacidad nuevo: la nota de
débito es una operación **sobre** ``account.move``, que ya dueña
``account`` con la capacidad ``invoices`` (``account/authz_catalog.py``:
*"invoices — account dueña account.move — la factura es un asiento"*).
Declarar una capacidad ``account_debit_note.*`` aparte duplicaría el
dominio que ``invoices`` ya cubre — el mismo criterio que evita que
``account_add_gln``/``sale_margin`` (extensiones sin acción propia de
usuario) declaren su propio catálogo.

Además, la ACL de la referencia gatea la tabla del **wizard**
(``account.debit.note``), que aquí no tiene tabla (``TransientModel``,
``managed = False`` — ver ``wizard/account_debit_note.py``) ni vista DRF
propia en este pase (ver ``__init__.py`` del addon). El enforcement queda
DEFERIDO a la vista que en el futuro exponga ``AccountDebitNoteWizard.
create_debit`` — gateada por ``HasCapability('invoices')``, no por una
capacidad nueva.
"""
