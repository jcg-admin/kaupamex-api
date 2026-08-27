"""``account.edi.xml.ubl_bis3`` extendido por ``account_peppol``. BLOQUEADO.

Adaptación de Odoo ``account_peppol/models/account_edi_xml_ubl_bis3.py``
(``odoo19c: addons/account_peppol/models/account_edi_xml_ubl_bis3.py``,
29 líneas, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no instala nada** y no exporta función ``apply_*``: su único
símbolo está bloqueado. Existe para conservar el SITIO del archivo contra la
referencia y dejar el desenlace greppeable.

Porte símbolo por símbolo — 1 símbolo, bloqueado
==================================================

``_invoice_constraints_peppol_en16931_ubl`` (``:7-29``) — **BLOQUEADO por
``account_edi_ubl_cii``**: extiende con ``super()`` el método homónimo de
``account.edi.xml.ubl_bis3``, el constructor de UBL BIS Billing 3.0 de ese
addon. Medido: 0 declaraciones de ``account.edi.xml.ubl_bis3`` en este árbol.
**Ese addon se está portando en otro pase, en paralelo**; este addon no lo
importa ni lo declara en ``depends``.

Qué añade en la referencia, para cuando se retome: dos restricciones de
validación que **sólo aplican cuando el documento sale por Peppol** —lo
distingue por ``context.get('from_peppol')``—, con sus códigos oficiales:

- ``[PEPPOL-EN16931-R010]`` — el cliente debe tener dirección electrónica
  (EAS); se lee de ``cac:AccountingCustomerParty/cac:Party/cbc:EndpointID``.
- ``[PEPPOL-EN16931-R020]`` — la empresa emisora, igual; se lee de
  ``cac:AccountingSupplierParty``.

El comentario de la fuente explica por qué van aquí y no en el constructor
genérico: el mismo XML puede usarse en operaciones B2C **fuera** de Peppol,
para que el contador lo importe en otro sistema, y ahí esas dos direcciones no
son obligatorias.

**Sucesor:** tarea PENDIENTE DE ASIGNAR (resumen de este pase) — mismo pase en
que aterrice ``account_edi_ubl_cii``.
"""
