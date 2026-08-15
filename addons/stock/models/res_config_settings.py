r"""``res.config.settings`` — el formulario de ajustes de ``stock``: NO PORTADO.

Adaptación de Odoo ``stock/models/res_config_settings.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 139 líneas) — atribución y aviso
de licencia preservados (DEC-KX-03).

Es el archivo más grande de los seis que faltaban en ``stock``, y **ninguna de
sus 139 líneas es dato**: 41 campos y 7 métodos que existen para pintar la
pestaña «Inventario» de la pantalla de Ajustes del cliente web de Odoo. El dato
real vive en otros tres sitios —``res.company``, los grupos de acceso y el
catálogo de módulos— y este archivo sólo lo expone.

Los 41 campos, por lo que hacen (no por su nombre)
===================================================

.. list-table::
   :header-rows: 1
   :widths: 12 60 28

   * - Cuántos
     - Qué son
     - Dónde vive su dato aquí
   * - 6
     - ``related='company_id.<campo>'`` — pasarela de escritura a la empresa
     - **YA PORTADO**, ver abajo
   * - 11
     - ``group_*`` con ``implied_group`` — activan un grupo de acceso
     - grupos de ``authz``; el mecanismo de grupo implicado no está construido
   * - 23
     - ``module_*`` — instalan un addon al guardar
     - catálogo de módulos; ninguno de los 23 addons está portado
   * - 1
     - ``barcode_separator`` con ``config_parameter='stock.barcode_separator'``
     - ``ir.config_parameter`` — **no existe** en este árbol
   * - 1
     - ``replenish_on_order`` — ``compute``/``inverse`` sobre el XML ID MTO
     - el XML ID ``stock.route_warehouse0_mto`` no está sembrado

*Métrica:* asignaciones del cuerpo de ``class ResConfigSettings`` en el archivo
de la referencia, clasificadas por el argumento que las distingue (``related=``,
``implied_group=``, prefijo ``module_``, ``config_parameter=``, ``compute=``).
*Ciega a:* si algún ``group_*`` o ``module_*`` tuviera además lógica propia — no
la tienen: los 34 son declaraciones de una línea.

Los 6 campos ``related``: el dato SÍ está completo
===================================================

``stock_move_email_validation``, ``stock_text_confirmation``,
``stock_confirmation_type``, ``annual_inventory_month``,
``annual_inventory_day`` y ``horizon_days`` **existen los seis** en
``addons/stock/models/res_company.py`` — los portó :ref:`h-api-615` en este
mismo ciclo. Medido: ``grep -c "'<campo>'" addons/stock/models/res_company.py``
→ **1** para cada uno de los seis.

Es decir: no falta ningún dato de configuración de empresa. Falta el
**formulario** que lo editaría desde una pantalla de ajustes, y eso es capa de
presentación.

Por qué NO se porta la clase — el precedente ya medido
=======================================================

``base/models/res_config.py:196`` declara ``ResConfigSettings`` con
``Meta: abstract = True``: es una **base para que cada addon cree su propia
subclase concreta**, no un modelo único donde varios addons cuelguen campos como
sí se hace con ``ResCompany``. Medido en este pase:

.. code-block:: text

    grep -rn "class .*(ResConfigSettings)" src/addons addons --include=*.py
      → addons/base_setup/models/res_config_settings.py:108  SiteConfigSettings

**Una sola** subclase concreta en todo el árbol, consumida por
``base_setup/controllers/`` (DRF), y no declara ningún campo de ``stock``.
Fabricar aquí una segunda clase paralela produciría un formulario **sin
lector** — la superficie inventada que ``porte-completo-no-parcial.md`` prohíbe
expresamente.

Es el **cuarto** caso idéntico del árbol, con el mismo desenlace:
``l10n_mx`` (1 campo), ``account_check_printing`` (6 campos), el ya registrado
como tarea **#278**, y éste (41 campos). La repetición es la señal de que el
patrón necesita una decisión, no cuatro declaraciones más — por eso **#278**
existe.

Los 7 métodos, y por qué ninguno sobrevive sin el formulario
=============================================================

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Método (línea)
     - De qué depende
   * - ``_compute_replenish_on_order`` (``:66-69``)
     - ``env.ref('stock.route_warehouse0_mto')`` — XML ID no sembrado
   * - ``_inverse_replenish_on_order`` (``:71-74``)
     - el mismo XML ID
   * - ``_onchange_group_stock_multi_locations`` (``:76-79``)
     - ``@api.onchange`` — evento del formulario, no del modelo
   * - ``_onchange_group_stock_production_lot`` (``:81-85``)
     - ídem
   * - ``_onchange_stock_confirmation_fields`` (``:87-90``)
     - ídem
   * - ``onchange_adv_location`` (``:92-95``)
     - ídem
   * - ``set_values`` (``:97-139``)
     - grupos implicados + activación de vistas XML + ``ir.actions``

Los cuatro ``@api.onchange`` son **el mecanismo del formulario**: se disparan
cuando el usuario marca una casilla, antes de guardar. Sin formulario no hay
evento que los dispare.

``set_values`` es el único con lógica de negocio real —desactiva los tipos de
operación internos de los almacenes al activar multi-ubicación, y **rehúsa**
desactivarla si hay más de un almacén por empresa— pero opera sobre tres cosas
ausentes: los grupos implicados (``base.group_user.implied_ids``), dos vistas
XML (``stock_location_view_tree2_editable``,
``stock_location_view_form_editable``) y el ``UserError`` de la pantalla.

Su regla de negocio —*"no se puede desactivar multi-ubicación si hay más de un
almacén por empresa"*— **sí** merece vivir en el modelo el día que la
configuración se exponga; hoy no tiene dónde: no hay campo que desactivar.

Lo que este archivo NO cierra
==============================

- **La decisión del patrón**, que es de arquitectura y no derivable: si
  ``res.config.settings`` se expone con una subclase por addon (y entonces
  ``stock`` merece la suya), o con un único formulario DRF de ajustes al que
  cada addon aporte campos. Cuarta ocurrencia — tarea **#278**.
- **El XML ID ``stock.route_warehouse0_mto``**, que ``stock_warehouse.py:882``
  y ``:1412`` ya nombran y nadie siembra: es la misma siembra ausente que
  ``stock_replenish_mixin.py`` declara para
  ``stock.stock_location_inter_company``. Tarea **#330**.
- **``ir.config_parameter``**, que no existe en el árbol (medido: 0 clases) y
  que este archivo necesitaría para un solo campo. Registrado como tarea
  **#387**.
"""
