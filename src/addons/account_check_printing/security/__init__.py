"""Security — ``addons.account_check_printing``.

Espejo de ``security/ir.model.access.csv`` de la referencia:

.. code-block:: text

    "access_print_prenumbered_checks","access.print.prenumbered.checks",
    "model_print_prenumbered_checks","account.group_account_user",1,1,1,0

Una sola ACL, sobre la tabla del wizard, para el grupo de usuarios de
contabilidad.

Por qué no hay ``authz_catalog.py`` aquí
============================================

``account_check_printing`` no dueña un dominio de capacidad nuevo: imprimir
cheques es una operación **sobre** ``account.payment``, que ya dueña
``account`` bajo la capacidad ``finance``/``finance.record``
(``account/authz_catalog.py``: *"finance — los movimientos financieros"*).
Declarar una capacidad ``account_check_printing.*`` aparte duplicaría el
dominio que ``finance`` ya cubre — el mismo criterio que
``account_debit_note`` fija para su propio wizard (sin catálogo, la nota de
débito es una operación sobre ``account.move``, que dueña ``invoices``).

Además, la ACL de la referencia gatea la tabla del **wizard**
(``print.prenumbered.checks``), que aquí no tiene tabla (``TransientModel``,
``managed = False`` — ver ``wizard/print_prenumbered_checks.py``) ni vista
DRF propia en este pase (mismo criterio que ``models/account_payment.py``,
Divergencia 3: sin serializer de ``account.payment`` todavía). El
enforcement queda DEFERIDO a la vista que en el futuro exponga
``CheckPrintingPaymentInfo.prepare_print_checks``/
``PrintPrenumberedChecksWizard.print_checks`` — gateada por
``HasCapability('finance.record')``, no por una capacidad nueva.
"""
