r"""``res.users`` — el almacén por defecto del usuario, addon ``stock``.

Adaptación de Odoo ``stock/models/res_users.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3, 12 líneas) — atribución y aviso de licencia preservados
(DEC-KX-03).

Qué aporta ``stock`` a ``res.users``: **un solo símbolo**, el almacén que se
propone cuando un documento necesita uno y el usuario no eligió ninguno. Es de
los archivos de extensión más pequeños del addon, y aun así su comentario es lo
que hay que preservar íntegro:

    *"!!! Any change to the following search domain should probably be also
    applied in ``sale_stock/models/sale_order.py``/``_init_column``."*

Es decir: el criterio —el primer almacén de la empresa activa— está **duplicado
a mano** en otro addon, y la fuente lo sabe. Al portar ``sale_stock`` hay que
volver aquí antes de tocar nada.

Porte símbolo por símbolo — 1 de 1
===================================

.. list-table::
   :header-rows: 1
   :widths: 42 12 46

   * - Símbolo (línea)
     - Estado
     - Forma aquí
   * - ``_get_default_warehouse_id`` (``:9-12``)
     - portado
     - ``extend_model('base', 'ResUsers', metodos=…)``; nombre **verbatim**

*Métrica:* entradas del cuerpo de ``class ResUsers`` en el archivo de la
referencia, contadas por AST — 2, de las que ``_inherit`` no es un símbolo a
portar (aquí lo expresa ``extend_model``).
*Ciega a:* lo que **otros** addons cuelgan de ``res.users``; este conteo sólo
ve el archivo de ``stock``.

Divergencias declaradas
========================

**D-1 — el nombre conserva el sufijo ``_id`` aunque no devuelva un id.** La
fuente devuelve un **recordset** (``search(..., limit=1)``), no un entero: el
sufijo ya es engañoso allá, y es la convención de Odoo para el campo
``Many2one`` que este método alimenta. Se porta verbatim porque
``porte-completo-no-parcial.md`` lo prefiere explícitamente —*"un método que
conserva su nombre no necesita tabla de equivalencia"*— y porque cada renombre
ciega a ``check_porte_completo`` (:ref:`h-api-579`).

**D-2 — la empresa activa se resuelve desde su PK.** ``get_current_company()``
(``src/orm/environments.py:153-161``) devuelve la **PK**, no el registro; el
filtro la usa tal cual, que es lo correcto y lo que evita el defecto D-3 de
:ref:`h-api-617`.

**D-3 — el destino se nombra con el par de Django, no con ``'res.users'``.**
``extend_model`` admite las dos formas y la primera es la de la referencia,
pero el nombre punteado exige que el modelo esté **registrado por ``_name``**, y
``base.models.ResUsers`` no lo declara: medido en este pase,
``extend_model('res.users', …)`` levanta ``LookupError: Ningún modelo cargado
declara _name='res.users'``.

La referencia sí lo declara —cinco atributos de clase, ``odoo19c:
odoo/addons/base/models/res_users.py:163-167``: ``_name``, ``_description``,
``_inherits``, ``_order``, ``_allow_sudo_commands``— así que la ausencia es el
defecto que ``atributos-de-clase-de-modelo.md`` describe, no una divergencia de
mecanismo. **No se corrige aquí**: completar la cabecera de ``res.users`` toca
``addons/base``, que es transversal y obliga a la suite entera; meterlo dentro
del porte de ``stock`` mezclaría dos cambios con radios de impacto distintos.
Sucesor: :ref:`h-api-618`, tarea **#385**.
"""
from django.apps import apps

from orm.environments import get_current_company
from orm.model_classes import extend_model


def _get_default_warehouse_id(self):
    """≙ ``_get_default_warehouse_id`` (``odoo19c: :9-12``).

    El primer almacén de la empresa activa, o ``None`` si no hay ninguno.

    .. warning::

       El dominio de búsqueda está **duplicado a mano** en
       ``sale_stock/models/sale_order.py::_init_column`` — la propia fuente lo
       avisa con ``!!!``. Todo cambio aquí se replica allá.
    """
    warehouse_model = apps.get_model('stock', 'StockWarehouse')
    return warehouse_model.objects.filter(
        company_id=get_current_company()).first()


def apply_stock_res_users_extensions():
    """Cuelga sobre ``res.users`` lo que ``stock`` le añade — ≙ ``_inherit``."""
    # Par de Django, no ``'res.users'``: ese modelo no declara ``_name``. Ver
    # la divergencia D-3 del docstring y :ref:`h-api-618`.
    extend_model('base', 'ResUsers', metodos={
        '_get_default_warehouse_id': _get_default_warehouse_id,
    })
