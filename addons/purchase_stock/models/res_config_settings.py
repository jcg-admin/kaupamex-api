r"""``res.config.settings`` — la pestaña de ajustes de ``purchase_stock``: NO PORTADA.

Adaptación de Odoo ``purchase_stock/models/res_config_settings.py``
(``odoo19c: addons/purchase_stock/models/res_config_settings.py``, 21 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Este archivo existe **sin código a propósito**. El desenlace es el mismo que
``addons/stock/models/res_config_settings.py`` ya fijó para el archivo hermano
—y por la misma razón—, así que aquí no se decide nada nuevo: se declara.

Los 4 símbolos de la fuente, uno por uno
=========================================

*Métrica:* entradas del cuerpo de ``class ResConfigSettings`` contadas por AST
sobre la fuente. Son **5** con ``_inherit``; **4** sin él: 3 campos y 1 método.
*Ciega a:* nada relevante — el archivo entero son 21 líneas y se lee completo.

.. list-table::
   :header-rows: 1
   :widths: 34 20 46

   * - Símbolo (línea)
     - Desenlace
     - Por qué
   * - ``module_stock_dropshipping`` (``:10``)
     - **bloqueado por el catálogo de módulos**
     - Un campo ``module_*`` INSTALA un addon al guardar. ``stock_dropshipping``
       no está portado (medido: ``ls addons/ | grep dropship`` → 0), y el
       mecanismo que traduce el check a una instalación tampoco.
   * - ``days_to_purchase`` (``:11-12``)
     - **el dato SÍ está; falta el formulario**
     - Es ``related='company_id.days_to_purchase'``: una pasarela de escritura
       a la empresa. La columna la porta ``res_company.py`` de este mismo
       addon, en este mismo pase. No falta ningún dato — falta la pantalla.
   * - ``is_installed_sale`` (``:13``)
     - **divergencia de mecanismo**
     - Es una bandera que la pantalla lee para mostrar u ocultar un bloque
       según si ``sale`` está instalado. Aquí ``sale`` es una app de Django;
       ``django.apps.apps.is_installed('addons.sale')`` responde lo mismo sin
       columna. No hay nada que persistir.
   * - ``get_values`` (``:15-21``)
     - **bloqueado por lo anterior**
     - Su cuerpo entero rellena ``is_installed_sale`` consultando
       ``ir.module.module``. Sin ese modelo (medido: ``grep -rn "ir.module.module"
       src/addons/base/models/ir_module.py`` da el modelo, pero su tabla de
       estados de instalación no se puebla en este árbol) y sin el formulario
       que lea el resultado, el método no tiene ni entrada ni salida.

Por qué no se fabrica la clase — el precedente, medido de nuevo aquí
=====================================================================

``src/addons/base/models/res_config.py:196`` declara ``ResConfigSettings`` con
``Meta: abstract = True``: es una **base para que cada addon derive su propia
subclase concreta**, no un modelo único donde varios addons cuelguen campos
como sí ocurre con ``ResCompany``. Medido en este pase:

.. code-block:: text

    grep -rn "class .*(ResConfigSettings)" src/addons addons --include=*.py
      → addons/base_setup/models/res_config_settings.py:108  SiteConfigSettings

**Una sola** subclase concreta en todo el árbol, consumida por
``base_setup/controllers/`` (DRF), y no declara ningún campo de compras.
Fabricar aquí una segunda clase paralela produciría un formulario **sin
lector** — la superficie inventada que ``porte-completo-no-parcial.md``
prohíbe expresamente.

Es la **quinta** ocurrencia idéntica del árbol —``l10n_mx`` (1 campo),
``account_check_printing`` (6), ``account`` , ``stock`` (41) y ésta (3)—, y la
decisión que las cierra a todas es la misma: **tarea #278**. Repetirla aquí
como una sexta declaración no la acerca; por eso este archivo apunta a la
tarea en vez de inventar una salida propia.

Lo que este archivo NO cierra
==============================

- **La decisión del patrón** (subclase por addon vs. un formulario DRF único al
  que cada addon aporte campos): es de arquitectura, no derivable. Sucesor ya
  registrado: tarea **#278**.
- **El addon ``stock_dropshipping``**, que ``module_stock_dropshipping``
  instalaría. No está portado y no hay tarea suya en este lote; su ausencia se
  declara aquí para que el día que se porte alguien encuentre este puntero.
"""
