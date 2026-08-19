r"""``res.config.settings`` — la pestaña «Comercio electrónico»: NO PORTADA.

Adaptación de ``odoo19c: addons/website_sale/models/res_config_settings.py``
(``odoo-tools@622ddc2a``, LGPL-3, 182 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Porte BLOQUEADO — 0 de 25 símbolos

Una sola clase, ``ResConfigSettings(_inherit='res.config.settings')``, con 17
campos y 8 métodos. **Ninguna de sus 182 líneas es dato**: existen para pintar
la pestaña «Comercio electrónico» de la pantalla de Ajustes del cliente web de
Odoo. El dato real vive en otros tres sitios —``website``, los grupos de acceso
y el catálogo de módulos— y este archivo sólo lo expone.

Los 17 campos, por lo que hacen
================================

.. list-table::
   :header-rows: 1
   :widths: 10 56 34

   * - Cuántos
     - Qué son
     - Dónde vive su dato aquí
   * - 11
     - ``related='website_id.<campo>'`` — pasarela de escritura al sitio
     - **4 ya portados**, ver abajo
   * - 3
     - ``group_*`` con ``implied_group`` — activan un grupo de acceso
     - grupos de ``authz``; el mecanismo de grupo implicado no está construido
   * - 2
     - ``module_*`` — instalan un addon al guardar
     - catálogo de módulos; ninguno de los 2 addons está portado
   * - 1
     - ``account_on_checkout`` — ``compute``/``inverse`` sobre el sitio
     - ``website.account_on_checkout`` — **no existe** (medido: 0 hits)

*Métrica:* asignaciones del cuerpo de ``class ResConfigSettings`` en el archivo
de la referencia, clasificadas por el argumento que las distingue (``related=``,
``implied_group=``, prefijo ``module_``, ``compute=``). 11+3+2+1 = 17.
*Ciega a:* si algún ``group_*`` o ``module_*`` tuviera además lógica propia — no
la tienen: los cinco son declaraciones de una o dos líneas.

Atributos de clase — 1, y también bloqueado
--------------------------------------------

Medido con el comando de ``atributos-de-clase-de-modelo.md``: la clase declara
**uno**, ``_inherit = 'res.config.settings'`` (``odoo19c: :7``). Sin ``_name``
ni ``_description`` — es una extensión, no un modelo propio.

Ese atributo tampoco se porta, y por la misma causa que los 25 símbolos: se
expresaría como la clase concreta que este archivo no declara. Portarlo suelto
sería nombrar una extensión que no existe.

Los 11 ``related``: 4 tienen su dato, 7 no
-------------------------------------------

Los cuatro cuyo dato **sí** está portado son exactamente la rebanada que este
addon ya cubrió, y los cuatro viven en ``WebsiteSaleSettings``
(``models/website.py``):

===================================  ==========================================
Campo de la referencia               Dónde está su dato aquí
===================================  ==========================================
``cart_recovery_mail_template``      ``WebsiteSaleSettings.cart_recovery_mail_template``
``cart_abandoned_delay``             ``WebsiteSaleSettings.cart_abandoned_delay``
``send_abandoned_cart_email``        ``WebsiteSaleSettings.send_abandoned_cart_email``
``salesteam_id``                     ``WebsiteSaleSettings.salesteam`` (este pase)
===================================  ==========================================

Los siete restantes —``add_to_cart_action``, ``salesperson_id``,
``website_sale_prevent_zero_price_sale``, ``website_sale_contact_us_button_url``,
``show_line_subtotals_tax_selection``, ``confirmation_email_template_id``,
``ecommerce_access``— pertenecen a rebanadas de
``odoo19c: website_sale/models/website.py`` que este addon todavía no portó.
Medido: ``grep -rn "<campo>" addons/ src/ --include=*.py`` → **0 hits** para
los siete.

Es decir: de la configuración de tienda del sitio falta dato, sí — pero eso es
alcance de ``models/website.py``, no de este archivo. Lo que falta **aquí** es
el formulario, y eso es capa de presentación.

Por qué NO se porta la clase — el precedente ya medido, cuatro veces
=====================================================================

``src/addons/base/models/res_config.py:199-200`` declara ``ResConfigSettings``
con ``Meta: abstract = True``: es una **base para que cada addon cree su propia
subclase concreta**, no un modelo único donde varios addons cuelguen campos
como sí se hace con ``ResCompany``. Un campo colgado sobre una clase abstracta
de Django **no genera columna**: el ajuste existiría en el registro y no en la
base, y el primer ``.save()`` fallaría.

Medido en este pase:

.. code-block:: text

    grep -rn "^class .*(ResConfigSettings)" src/addons addons --include=*.py
      → addons/web/models/res_config_settings.py:67         WebConfigSettings
      → addons/base_setup/models/res_config_settings.py:108 SiteConfigSettings

**Dos** subclases concretas, las dos de otros addons, y ninguna declara ningún
campo de ``website_sale`` (medido: ``grep -rn "website_sale\|cart_abandoned\|
group_show_uom" addons/base_setup/ addons/web/ --include=*.py`` → 0 hits).
Fabricar aquí una tercera clase paralela produciría un formulario **sin
lector** — la superficie inventada que ``porte-completo-no-parcial.md`` prohíbe
expresamente.

.. note::

   El conteo anterior corrige una cifra que había quedado atrás en la prosa del
   árbol: ``addons/stock/models/res_config_settings.py`` afirma *"**Una sola**
   subclase concreta en todo el árbol"*, y ya son dos —``web`` estrenó la suya
   después—. Es el caso exacto del corolario de
   ``calibration-verified-numbers.md``: una cifra que es **propiedad de un
   artefacto vivo** fue correcta al escribirse y falsa después, sin que nadie
   tocara el documento. Aquí se cita **el comando**, y la cifra que se lee es
   la que ese comando devuelve hoy.

Este es el **quinto** caso idéntico del árbol, con el mismo desenlace:

=============================  =========  =========================
Addon                          Símbolos   Archivo
=============================  =========  =========================
``l10n_mx``                    1 campo    ``models/res_config_settings.py``
``account_check_printing``     6 campos   ídem
``product_expiry``             4          ídem
``stock``                      41+7       ídem
``website_sale`` (éste)        17+8       ídem
=============================  =========  =========================

La repetición es la señal de que el patrón necesita **una** decisión, no una
sexta declaración más — por eso la tarea **#278** existe, y por eso este
archivo no inventa una forma nueva.

Los 8 métodos, y por qué ninguno sobrevive sin el formulario
=============================================================

.. list-table::
   :header-rows: 1
   :widths: 44 56

   * - Método (línea)
     - De qué depende
   * - ``_compute_account_on_checkout`` (``:94-96``)
     - ``website.account_on_checkout`` — 0 hits en el árbol
   * - ``_inverse_account_on_checkout`` (``:98-108``)
     - ídem, más ``website.auth_signup_uninvited``
   * - ``set_values`` (``:112-131``)
     - ``product.feed`` y ``website._populate_product_feeds``/
       ``enabled_gmc_src`` — 0 hits los tres
   * - ``action_view_delivery_provider_modules`` (``:135-136``)
     - ``delivery.carrier.install_more_provider`` — 0 hits
   * - ``action_open_abandoned_cart_mail_template`` (``:139-147``)
     - ``ir.actions.act_window``
   * - ``action_open_extra_info`` (``:149-155``)
     - ``website.get_client_action`` — acción de cliente web
   * - ``action_open_sale_mail_templates`` (``:157-166``)
     - ``ir.actions.act_window``
   * - ``action_open_product_feeds`` (``:168-182``)
     - ``ir.actions.act_window`` + ``product.feed``

Los **cinco** ``action_*`` son navegación pura: devuelven un diccionario que
sólo un cliente web sabe interpretar. Medido: ``find addons/ src/ -name
"*.xml"`` → **0 archivos**; este árbol es *headless* y sirve su superficie por
DRF. Es el mismo criterio con que ``models/crm_team.py`` deja fuera
``get_abandoned_carts`` y ``models/sale_order.py`` deja fuera
``action_recovery_email_send`` — y por eso los tres comparten sucesor.

``set_values`` es el único con lógica de negocio propia —siembra los *feeds*
del sitio si no hay ninguno, y propaga el flag GMC a **todos** los sitios con
un comentario que reconoce el defecto de origen (*"the GMC feature flag was
implemented as website-specific, even though a group-based feature flag is
global"*)— pero opera sobre tres cosas ausentes. Esa regla **sí** merece vivir
en el modelo el día que ``product.feed`` exista; hoy no tiene sobre qué operar.

Lo que este archivo NO cierra
==============================

- **La decisión del patrón**, que es de arquitectura y no derivable: si
  ``res.config.settings`` se expone con una subclase por addon (y entonces
  ``website_sale`` merece la suya), o con un único formulario DRF de ajustes al
  que cada addon aporte campos. Quinta ocurrencia — tarea **#278**.
- **Los 7 campos de configuración de tienda del sitio** que aún no tienen dato
  (``add_to_cart_action``, ``salesperson_id``, ``ecommerce_access``, …).
  BLOQUEADOS por ``WebsiteSaleSettings`` — su hogar es ``models/website.py``,
  que portó una rebanada nombrada y dejó el resto con su superficie. Tarea
  **#568**.
- **``product.feed``**, que ``set_values`` y ``action_open_product_feeds``
  necesitan y que no existe en el árbol (medido: 0 clases). El addon que lo
  declara en la referencia es ``website_sale`` mismo, en un archivo que esta
  tarea no cubre. Tarea **#569**.
"""
