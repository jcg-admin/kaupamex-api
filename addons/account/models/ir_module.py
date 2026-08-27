r"""``ir.module.module`` extendido por ``account`` — el instalador de planes contables: NO PORTADO.

Adaptación de Odoo ``account/models/ir_module.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 115 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 0 de 6
=====================================

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Símbolo
     - Por qué está bloqueado
   * - ``account_templates`` (campo) / ``_compute_account_templates``
     - introspección de paquete Python vía ``getmembers``/``import_module``
       sobre funciones decoradas ``_l10n_template`` — mecanismo estructuralmente
       distinto del que ya existe en este árbol (ver abajo)
   * - ``write`` (override)
     - engancha la instalación automática del plan de cuentas a la
       transición de estado ``→ installed``, que este árbol no tiene
   * - ``_load_module_terms`` (override)
     - traducciones cargadas al instalar un módulo — mismo eje: no hay
       instalación en caliente
   * - ``_register_hook`` (override)
     - hook del ciclo de vida del registro de Odoo (``env.registry``),
       inexistente aquí
   * - ``module_uninstall`` (override)
     - la contraparte de desinstalación — mismo eje

Bloqueo estructural — ya documentado por el propio modelo base
====================================================================

``src/addons/base/models/ir_module.py`` (el ``IrModule`` que este archivo
extendería) ya declara, en su propio docstring, la premisa exacta que hace
inaplicables los seis símbolos: *"Se portan los campos de declaración y los
tres estados ALCANZABLES en este árbol. Las transiciones de Odoo (``to
install``/``to upgrade``/``to remove``) NO se portan: son la máquina de
estados de un instalador que aquí no existe — el registro de apps de Django
se congela en ``django.setup()`` y el schema es compartido entre companies
(ADR-021). Registrar un estado que nadie puede alcanzar sería inventar una
capacidad."*

Los seis símbolos de ``account`` son, sin excepción, ganchos sobre esa misma
máquina de estados ausente: ``write`` reacciona a la transición
``→ installed``; ``_register_hook``/``_load_module_terms``/
``module_uninstall`` son fases del ciclo de vida del registro de Odoo
(``self.env.registry``, que tampoco existe — el registro de apps de Django
es estático tras ``django.setup()``). No hay un evento al que colgarse.

``account_templates``/``_compute_account_templates`` — divergencia de mecanismo, no bloqueo puro
=========================================================================================================

Este par es distinto de los otros cuatro: no depende de la máquina de
instalación, sino de introspeccionar el paquete Python de cada módulo
(``getmembers(import_module(f"odoo.addons.{module.name}.models"),
template_module)``) buscando funciones marcadas con el decorador
``_l10n_template``. Medido: **el decorador sí existe** en este árbol
(``addons/account/models/chart_template.py``, la función ``template()``),
pero con una forma **distinta**: no expone sus metadatos vía introspección de
paquete para que un modelo ajeno los recorra — los consume directamente
``ChartTemplate.try_loading()`` (``addons/account/models/chart_template.py:481``),
que ya es la vía por la que este árbol carga un plan contable
(``load_chart_for_new_company``, colgado en ``res_company.py`` de este mismo
addon).

Es decir: el **propósito** de ``account_templates`` —listar qué planes
contables hay disponibles, para elegir uno— ya tiene un mecanismo propio en
``chart_template.py``, con otra forma. Portar la introspección de la
referencia encima sería una segunda vía para lo mismo, divergente de la que
ya está construida. **Desenlace: (a) divergencia de mecanismo declarada** —
si algún día se necesita un catálogo de planes disponibles para una UI, se
construye contra ``ChartTemplate``, no contra ``getmembers``/``ir.module``.

Lo que este archivo NO cierra
================================

- **El registro de instalación en caliente** (``env.registry``, transiciones
  de estado) — no es alcance de ``account``, es una decisión de plataforma
  ya fijada (ADR-021, "schema compartido entre companies") con la que este
  archivo es coherente, no divergente.
- **Un catálogo de planes contables disponibles para UI**, si llega a
  necesitarse — se construye sobre ``ChartTemplate``, no sobre este archivo.
"""
