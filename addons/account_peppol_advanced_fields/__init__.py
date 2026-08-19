"""``account_peppol_advanced_fields`` — referencias documentales de Peppol BIS.

Adaptación de Odoo ``account_peppol_advanced_fields``
(``odoo19c: addons/account_peppol_advanced_fields/``, licencia ``LGPL-3``
declarada en su ``__manifest__.py``) — atribución y aviso de licencia
preservados (DEC-KX-03).

Qué es: siete campos de texto sobre ``account.move`` que la factura
electrónica europea admite como referencias documentales (contrato, proyecto,
pedido de origen, albarán, documento adicional, centro de costo, GLN de
entrega). Sin métodos, sin lógica: **el addon sólo aporta datos** que el
generador UBL vuelca en sus ``cac:*DocumentReference``.

El addon está DEPRECADO en la propia fuente
==============================================

Su ``__manifest__.py`` se titula ``"[DEPRECATED] Account Peppol Advanced
Fields"`` y su ``summary`` dice, verbatim: *"Merged prematurly, not working
correctly. Please don't use. Better solution coming soon."*

Se porta igualmente —el porte es completo o declara su cobertura
(``porte-completo-no-parcial.md``), y la sustitución que la fuente anuncia
todavía no existe en el árbol de referencia— **conservando la marca
``[DEPRECATED]`` en las siete etiquetas**, que es lo que hace que el aviso
viaje con el dato.

Layout — contra el de la referencia
=====================================

La referencia trae ``models/``, ``views/`` e ``i18n/``. Aquí:

- ``models/`` — se porta entero: un archivo, siete campos, cero métodos.
- ``views/account_move_views.xml`` — **no se porta**: es el formulario del
  cliente web de Odoo (una pestaña con los siete campos), y el cliente de este
  proyecto es React. Criterio ya establecido en el árbol.
- ``i18n/`` — los ``.po`` son del harness de traducción de Odoo.

``depends`` — diverge de la referencia, con razón medida
==========================================================

La referencia declara ``['account', 'account_edi_ubl_cii']``. Aquí **no se
declara ``account_edi_ubl_cii``**: ese addon **se está portando en otro pase,
en paralelo**, y —lo que decide el caso— **este addon no lo necesita**. Sus
siete campos son ``Char`` planos: no leen ni escriben nada de él. La
dependencia existe en la referencia porque el generador UBL de ese addon es
quien los **consume**, no porque este addon lo importe; medido, su único
archivo de modelo importa sólo ``fields`` y ``models`` de Odoo
(``odoo19c: addons/account_peppol_advanced_fields/models/account_move.py:1``).

Consecuencia declarada: los siete campos existen y se pueden llenar, pero **no
alimentan ningún XML** hasta que ``account_edi_ubl_cii` aterrice. Eso es
exactamente lo que pasa en la referencia si se instala este addon sin usar
Peppol.

Este archivo NO importa ``models`` — el patrón local (``addons/utm``,
``addons/project_account``) deja el ``__init__.py`` raíz sin imports; la
extensión corre en ``AccountPeppolAdvancedFieldsConfig.ready()``.
"""
