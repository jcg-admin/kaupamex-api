"""Seguridad — ``account_test``. Mapeo de ``security/ir.model.access.csv``.

La referencia (``odoo19c: addons/account_test/security/ir.model.access.csv``)
declara dos filas de ACL sobre ``accounting.assert.test``::

    access_accounting_assert_test          base.group_system            read=1 write=0 create=0 unlink=1
    access_accounting_assert_test_manager  account.group_account_manager read=1 write=0 create=0 unlink=0

Es decir: el admin de sistema puede ver y borrar (nunca crear/editar desde
la UI); el gerente contable sólo puede ver. Este ORM no tiene grupos
jerárquicos — la ACL se porta como UNA capacidad DEC-11
(``finance.diagnostics``, declarada en ``authz_catalog.py`` de este mismo
directorio), colapsando los dos niveles a uno solo. Ver la sección
"``security/ir.model.access.csv`` — colapsado a UNA capacidad" en
``models/accounting_assert_test.py`` para la divergencia completa.

``authz_catalog.py`` en ``security/`` (no en la raíz del addon) es el layout
"fiel a odoo-tools" que ``addons.authz.declaration._import_declaration``
busca primero — coincide con que la referencia hospeda su ACL exactamente
aquí.
"""
