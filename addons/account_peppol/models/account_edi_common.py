"""``account.edi.common`` extendido por ``account_peppol``. BLOQUEADO.

Adaptación de Odoo ``account_peppol/models/account_edi_common.py``
(``odoo19c: addons/account_peppol/models/account_edi_common.py``, 18 líneas,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Este módulo no instala nada** y no exporta función ``apply_*``: sus dos
símbolos están bloqueados. Existe para conservar el SITIO del archivo contra
la referencia y dejar el desenlace greppeable.

Porte símbolo por símbolo — 2 símbolos, los 2 bloqueados
==========================================================

Los dos **BLOQUEADOS por ``account_edi_ubl_cii``**, que es quien declara
``account.edi.common`` y los dos métodos que la fuente extiende con
``super()``. La propia fuente lo dice en un comentario por método:
``# EXTENDS 'account_edi_ubl_cii'``. Medido en este árbol: 0 declaraciones de
``account.edi.common``. **Ese addon se está portando en otro pase, en
paralelo**; este addon no lo importa ni lo declara en ``depends``.

- ``_add_logs_import_invoice_ubl_cii`` (``:7-12``) — antepone al registro de
  importación una línea con el UUID Peppol del documento
  (``invoice.peppol_message_uuid``, campo que **sí** se porta en
  ``models/account_move.py``).
- ``_log_import_invoice_ubl_cii`` (``:14-18``) — cambia el título del registro
  a «Factura Peppol recibida» cuando el documento entró por la red.

Los dos son cosmética del registro de importación, pero su valor está en que
el asiento importado quede trazado a su mensaje Peppol — por eso se declaran
en vez de descartarse.

**Sucesor:** tarea PENDIENTE DE ASIGNAR (resumen de este pase) — mismo pase en
que aterrice ``account_edi_ubl_cii``.
"""
