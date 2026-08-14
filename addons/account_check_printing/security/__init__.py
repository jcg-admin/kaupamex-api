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
``managed = False`` — ver ``wizard/print_prenumbered_checks.py``). El
enforcement lo ejerce ``controllers/views.py::print_checks`` (H-API-406,
tarea #50; UC-FIN-09) — gateada por ``HasCapability('finance.record')``, no
por una capacidad nueva. La ACL de la referencia sobre
``model_print_prenumbered_checks`` no tiene análogo directo (sin tabla que
gatear); la capacidad de dominio cumple el mismo papel.
"""
