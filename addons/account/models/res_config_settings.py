r"""``res.config.settings`` — el formulario de ajustes de ``account``: NO PORTADO.

Adaptación de Odoo ``account/models/res_config_settings.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 311 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Es el archivo más grande de los seis históricamente medidos con este mismo
desenlace en el árbol (``stock`` 139 líneas, ``account_check_printing`` 32,
``l10n_mx`` 1 campo, y éste, 311). Y **ninguna de sus 311 líneas es dato**:
63 campos y 18 métodos que existen para pintar la pestaña «Facturación» de la
pantalla de Ajustes del cliente web de Odoo. El dato real vive en otros dos
sitios —``res.company`` y el catálogo de grupos/módulos— y este archivo sólo
lo expondría.

Los 63 campos, por lo que hacen (no por su nombre)
=====================================================

.. list-table::
   :header-rows: 1
   :widths: 12 60 28

   * - Cuántos
     - Qué son
     - Dónde vive su dato aquí
   * - 36
     - ``related='company_id.<campo>'`` — pasarela de escritura a la empresa
     - una parte YA PORTADA (``res_company.py``: 2 de 72 del Bloque 1, los
       5 candados de fecha); el resto es la tarea **#137**
   * - 17
     - ``module_*`` — instalan un addon al guardar (facturación electrónica,
       OCR de facturas, presupuesto analítico…)
     - catálogo de módulos; ninguno de los 17 addons está portado
   * - 2
     - ``group_*`` con ``implied_group`` — activan un grupo de acceso
     - grupos de ``authz``; el mecanismo de grupo implicado no está construido
       en el formulario (``implied_ids`` sí existe en el modelo, ver
       ``res_users.py`` de este mismo pase)
   * - 2
     - ``config_parameter=`` — parámetro de sistema plano
     - ``ir.config_parameter`` / ``SystemParameter`` — **sí existe**
       (``src/addons/base/models/ir_config_parameter.py``), pero sin
       formulario que lo escriba
   * - 6
     - sin ``related=``/``implied_group=``/prefijo — campos propios del
       formulario (``terms_type``, umbrales de riesgo, plantillas)
     - dato nuevo, no expuesto por ningún otro modelo

*Métrica:* asignaciones del cuerpo de ``class ResConfigSettings`` en el
archivo de la referencia, clasificadas por el argumento que las distingue.
*Ciega a:* si algún ``module_*``/``group_*`` tuviera además lógica propia —
medido explícitamente en la fila de métodos, abajo.

Por qué NO se porta la clase — el precedente ya medido, ahora quinta vez
=============================================================================

``base/models/res_config.py`` declara ``ResConfigSettings`` con
``class Meta: abstract = True``: es una **base para que cada addon cree su
propia subclase concreta**, no un modelo único donde varios addons cuelguen
campos con ``add_to_class`` como sí se hace con ``ResCompany``. Medido en
este pase:

.. code-block:: text

    grep -rn "class .*(ResConfigSettings)" src/addons addons --include=*.py
      → addons/base_setup/models/res_config_settings.py:108  SiteConfigSettings

**Una sola** subclase concreta en todo el árbol, consumida por
``base_setup/controllers/`` (DRF), y no declara ningún campo de ``account``.
Fabricar aquí una segunda clase paralela produciría un formulario **sin
lector** — la superficie inventada que ``porte-completo-no-parcial.md``
prohíbe expresamente.

Es el **quinto** caso idéntico del árbol, con el mismo desenlace: ``l10n_mx``
(1 campo), ``account_check_printing`` (6 campos), ``stock`` (41 campos, ya
registrado como tarea **#278**), y éste (63 campos, el mayor con diferencia).
La repetición sostenida —y su tamaño creciente— es la señal de que el patrón
necesita la decisión de arquitectura, no una quinta declaración más.

Los 18 métodos, y por qué ninguno sobrevive sin el formulario
==================================================================

Todos son ``@api.depends``/``@api.onchange`` (eventos y computados **del
formulario**: se disparan cuando el usuario marca una casilla o abre la
pantalla, antes de guardar) o ``action_*`` (botones de la vista). Ninguno
tiene lógica de negocio que sobreviva fuera de un formulario que no existe:

.. list-table::
   :header-rows: 1
   :widths: 55 45

   * - Método
     - Naturaleza
   * - ``_compute_is_account_peppol_eligible``
     - ``@api.depends`` — computado de UI
   * - ``set_values`` / ``reload_template``
     - persistencia del formulario + recarga de vista
   * - ``_compute_account_default_credit_limit`` /
       ``_inverse_account_default_credit_limit``
     - par compute/inverse — pasarela de escritura a la empresa
   * - ``_compute_has_chart_of_accounts``
     - ``@api.depends`` — computado de UI
   * - ``_compute_module_account_invoice_extract`` /
       ``_compute_module_account_bank_statement_extract``
     - ``@api.depends`` sobre otro campo ``module_*`` — cadena de UI
   * - ``onchange_analytic_accounting`` / ``onchange_module_account_budget`` /
       ``_onchange_tax_exigibility``
     - ``@api.onchange`` — evento de formulario, no del modelo
   * - ``_compute_terms_preview``
     - ``@api.depends`` — previsualización de plantilla en la UI
   * - ``action_update_terms`` / ``action_eu_oss_tax_mapping``
     - botones de la vista, abren asistentes/URLs

Lo que este archivo NO cierra
================================

- **La decisión del patrón**, que es de arquitectura y no derivable: si
  ``res.config.settings`` se expone con una subclase por addon, o con un
  único formulario DRF de ajustes al que cada addon aporte campos. Quinta
  ocurrencia — tarea **#278** (ya registrada, no se duplica).
- **El Bloque 1 de** ``res.company`` **completo** (70 de 72 campos
  restantes) — tarea **#137**, precondición de los 36 campos ``related=``.
- **El catálogo de módulos instalables** — ninguno de los 17 addons
  ``module_*`` (OCR, EDI, presupuesto analítico…) está portado; su
  instalación en caliente tampoco tiene mecanismo (mismo hueco que
  ``ir_module.py`` de este mismo pase documenta con más detalle).
"""
