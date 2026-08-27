"""``product.product`` — la variante que se entrega como horas
(Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/product_product.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 58 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``ProductProduct``,
``_inherit``), **0 campos**, **5 métodos**. **No-op medido** — los cinco
tienen desenlace declarado y ninguno es alcanzable hoy.

Porte símbolo por símbolo — 0 de 5
=====================================

.. list-table::
   :header-rows: 1

   * - Método de la referencia (línea)
     - Desenlace aquí
   * - ``_is_delivered_timesheet`` (:11-14)
     - **BLOQUEADO** — ``self.type == 'service' and self.service_policy ==
       'delivered_timesheet'``. La primera mitad **sí** se puede medir
       (``ProductTemplate.type`` existe, con ``TYPE_SERVICE`` ya constante en
       ``api: addons/product/models/product_template.py:116``); la segunda no:
       ``service_policy`` lo declara ``sale_project``
       (``odoo19c: sale_project/models/product_template.py:44``) y da 0 hits
       en este árbol.

       **No se porta la mitad medible**, y la razón importa: el método es un
       **predicado** que decide si una línea se factura por tiempo entregado.
       Con una de las dos conjunciones ausente devolvería ``True`` para
       *cualquier* servicio, no para los facturados por hoja de horas — un
       predicado más ancho que el de la fuente, que es peor que ninguno.
       Mismo criterio que los dos filtros de ``models/account_move_line.py``.
       Sucesor: tarea PENDIENTE DE ASIGNAR (hogar ``addons/sale_project``).
   * - ``_onchange_service_fields`` (:16-33)
     - BLOQUEADO — no hay motor de ``onchange`` en este árbol (mismo desenlace
       que ``hr_timesheet`` declaró para ``_onchange_project_id``), y su
       cuerpo lee ``ir.default`` y las semillas ``uom.product_uom_hour``.
   * - ``_onchange_service_policy`` (:35-42)
     - BLOQUEADO — ídem, y delega en
       ``ProductTemplate._get_onchange_service_policy_updates``, bloqueado a
       su vez en ``models/product_template.py``.
   * - ``_unlink_except_master_data`` (:44-48) / ``write`` (:50-58)
     - BLOQUEADOS — protegen el producto semilla
       ``sale_timesheet.time_product`` (``data/sale_service_data.xml``) de ser
       archivado, borrado o atado a una compañía. Sin la fila semilla no hay
       qué proteger. Sucesor: la tarea de la semilla (PENDIENTE DE ASIGNAR);
       el candado se cablea con ella. Es el mismo par de símbolos —y el mismo
       desenlace— que ``models/product_template.py``, porque la fuente los
       duplica en variante y plantilla.

Divergencia de forma en la fuente, anotada
=============================================

``import threading`` (:3) está en la referencia y **no se usa** en ninguna de
las 58 líneas del archivo (medido: 0 ocurrencias de ``threading.`` en el
cuerpo). Es un import muerto de la fuente; no se porta. Se anota aquí porque
un conteo de imports fuente-vs-portado lo marcaría como símbolo ausente si no
constara la razón. El mismo import muerto está en
``odoo19c: sale_timesheet/models/product_template.py:3``.
"""


def apply_sale_timesheet_product_product_extensions():
    """No-op declarado — los cinco símbolos de la referencia están bloqueados.
    Ver el docstring del módulo.

    Se conserva la función (y su entrada en
    ``SaleTimesheetConfig._EXTENSIONES``) porque es el punto exacto donde se
    cablea ``_is_delivered_timesheet`` el día que ``service_policy`` aterrice
    — mismo criterio que ``hr/models/res_config_settings.py``.
    """
    return None


__all__ = ['apply_sale_timesheet_product_product_extensions']
