r"""``uom.uom`` extendido por ``account`` — un campo ya portado, dos métodos bloqueados.

Adaptación de ``addons/account/models/uom_uom.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 59 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 de 3, ya portado por OTRO archivo
====================================================================

.. list-table::
   :header-rows: 1
   :widths: 40 20 40

   * - Símbolo
     - Estado
     - Nota
   * - ``fiscal_country_codes`` / ``_compute_fiscal_country_codes``
     - **YA PORTADO** — sin duplicar aquí
     - lo cuelga ``res_company.py`` de este mismo addon
   * - ``_get_unece_code``
     - **bloqueado**
     - requiere lectura inversa de identificador externo, ausente
   * - ``_get_uom_from_unece_code`` (``@api.model``)
     - **bloqueado**
     - requiere resolución de identificador externo, ausente

SITIO — este símbolo no se declara dos veces
===============================================

``fiscal_country_codes`` (``odoo19c: account/uom_uom.py:41-46``) **ya está
portado**, colgado desde ``addons/account/models/res_company.py`` de este
mismo pase de trabajo:

.. code-block:: python

    # res_company.py, apply_account_extensions():
    for model, funcion in (
        (ResCurrency, session_fiscal_country_codes),
        (ResBank, session_fiscal_country_codes),
        (ResPartnerBank, session_fiscal_country_codes),
        (Uom, session_fiscal_country_codes),          # <- este símbolo
        ...
    ):
        if not hasattr(model, 'fiscal_country_codes'):
            model.add_to_class('fiscal_country_codes', ...)

Ese mismo archivo cita explícitamente esta procedencia: *"``Uom`` es
``uom.uom`` (``odoo19c: account/models/uom_uom.py:41-46``): allá la clase se
llama ``UomUom`` y aquí ``Uom``[…]"*. Declararlo OTRA vez aquí —con
``add_to_class`` guardado por ``hasattr``— sería inofensivo por la
idempotencia del guard, pero duplicaría la documentación de un mismo símbolo
en dos archivos, que es exactamente lo que la cláusula de SITIO de
``atributos-de-clase-de-modelo.md`` existe para evitar: un símbolo, un dueño.
Este archivo **no** cuelga nada para él; sólo lo señala.

Bloqueo — sin resolutor de identificador externo genérico
===============================================================

``_get_unece_code`` y ``_get_uom_from_unece_code`` traducen entre el código
UNECE de comercio internacional (``C62``, ``KGM``…) y una unidad de medida,
usando el identificador externo (XML ID) de la unidad como llave —
``self._get_external_ids()`` en un sentido, ``self.env.ref(xmlid)`` en el
otro. Medido en este mismo pase: no existe un resolutor de identificador
externo genérico sobre cualquier modelo en este árbol —
``src/addons/base/models/res_groups.py`` ya declara ``get_external_id``
explícitamente fuera de alcance por el mismo motivo que otros símbolos
vecinos [PROVEN]. El patrón que sí existe (``ir.model.data`` consultado por
``module``/``name``, usado en ``res_company.py`` y ``res_users.py`` de este
mismo pase) resuelve **un** identificador a la vez, conocido de antemano —no
sirve para el sentido inverso que ``_get_unece_code`` necesita (record →
lista de sus propios identificadores externos).

**Desenlace: (b) bloqueado por pieza concreta**, con sucesor: un resolutor
inverso de identificador externo genérico (``ir.model.data`` filtrado por
``model``/``res_id``, agregado por registro) es trabajo de plataforma
(``ir.model.data``), no de ``account`` — se registra como hallazgo.
"""
