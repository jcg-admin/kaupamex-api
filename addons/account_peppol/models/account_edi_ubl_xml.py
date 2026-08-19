"""``account.edi.ubl`` extendido por ``account_peppol``. BLOQUEADO, no se instala.

Adaptación de Odoo ``account_peppol/models/account_edi_ubl_xml.py``
(``odoo19c: addons/account_peppol/models/account_edi_ubl_xml.py``, 16 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no instala nada** y no exporta función ``apply_*``: su único
símbolo está bloqueado. Existe para conservar el SITIO del archivo contra la
referencia y dejar el desenlace greppeable.

Porte símbolo por símbolo — 1 símbolo, bloqueado
==================================================

``_ubl_add_values_supplier`` (``:7-16``) — **BLOQUEADO por
``account_edi_ubl_cii``** en dos frentes, los dos medidos:

1. **El modelo que extiende no existe.** ``_inherit = 'account.edi.ubl'`` es
   un modelo abstracto de ese addon; medido, ``grep -rn "account.edi.ubl"
   addons/ src/ --include=*.py`` no devuelve ninguna declaración en este árbol.
   **Ese addon se está portando en otro pase, en paralelo**, así que este
   addon no lo importa ni lo declara en ``depends``: la arista la reconcilia
   el orquestador al consolidar.
2. **El campo que consulta tampoco.** El cuerpo lee
   ``company.peppol_parent_company_id``, cuyo ``compute`` compara
   ``peppol_eas`` / ``peppol_endpoint`` — los dos, campos de
   ``account_edi_ubl_cii``
   (``odoo19c: account_edi_ubl_cii/models/res_partner.py:43,51``). Ver
   ``models/res_company.py`` para ese desenlace.

Qué hace en la referencia, para cuando se retome: cuando una empresa emite a
través de la conexión Peppol de su empresa matriz, el XML debe declarar como
proveedor a **la matriz**, no a la filial. Son tres líneas, y todo su valor
está en esa regla de negocio.

**Sucesor:** tarea PENDIENTE DE ASIGNAR (resumen de este pase) — se porta en
el mismo pase en que ``account_edi_ubl_cii`` aterrice y ``res_company`` reciba
``peppol_parent_company``.
"""
