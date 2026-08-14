"""``account.root`` — prefijo de 2 dígitos del código de cuenta (Odoo
``account``).

Adaptación de Odoo addons/account/models/account_root.py
(odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:, LGPL-3).

**NO se porta como modelo Django** — se documenta por qué en vez de
fabricar una forma. La referencia declara ``_auto = False`` +
``_table_query = '0'`` (odoo19c: account_root.py:10-11): no es una vista SQL
sobre una tabla real (ese caso sí tiene equivalente Django — ``Meta.managed
= False`` sobre una vista de migración, patrón ya usado en
``base.ResDevice``, ver docstring de ``base/models/res_device.py``).
``account.root`` es más extremo: ``_table_query = '0'`` es un query que no
referencia ninguna tabla, y ``browse()``/``_search()`` están sobreescritos
para **fabricar** registros a partir del propio ``id`` pedido — el "dato" no
sale de una consulta, sale de trocear el string del código de cuenta
(``_from_account_code``: ``code[:2]``) y encadenar prefijos
(``_compute_root``: ``parent_id = id[:-1]``). No hay join con
``account.account`` en ningún punto del archivo.

Es, en esencia, una función pura sobre strings que Odoo expone con la
interfaz de un modelo porque el cliente web de Odoo (breadcrumbs jerárquicos
en la vista kanban del plan de cuentas) necesita que todo lo agrupable sea
un "recordset". Sin ese cliente web, envolverlo en un ``models.Model`` con
tabla propia fabricaría persistencia que la referencia explícitamente NO
tiene (``_auto = False``), y envolverlo en una vista SQL fabricaría una
consulta que la referencia tampoco tiene (``_table_query = '0'``, no una
subconsulta real).

Se porta como lo que realmente es: una utilidad Python pura, sin tabla, sin
registro en ``models/__init__.py`` como modelo ORM.
"""


def account_root_name(code_prefix):
    """Nombre del nodo — Odoo ``_compute_root``: ``name = root.id`` (odoo19c:
    account_root.py:26-29). El "id" de un nodo de ``account.root`` ES su
    prefijo; no hay traducción adicional."""
    return code_prefix


def account_root_parent(code_prefix):
    """Prefijo padre en la cadena — Odoo ``_compute_root``:
    ``parent_id = self.browse(root.id[:-1] if len(root.id) > 1 else False)``
    (odoo19c: account_root.py:27-29). Devuelve ``None`` en la raíz (longitud
    1), igual que la referencia devuelve un recordset vacío."""
    if not code_prefix or len(code_prefix) <= 1:
        return None
    return code_prefix[:-1]


def account_root_from_code(code):
    """Prefijo de 2 dígitos de un código de cuenta — Odoo
    ``_from_account_code`` (odoo19c: account_root.py:22-24): ``code[:2]``."""
    return (code or '')[:2] or None
