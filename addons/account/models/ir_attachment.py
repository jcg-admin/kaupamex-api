r"""``ir.attachment`` extendido por ``account`` — un método portado, cuatro bloqueados.

Adaptación de ``addons/account/models/ir_attachment.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 90 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 1 de 5
=====================================

.. list-table::
   :header-rows: 1
   :widths: 35 15 50

   * - Símbolo
     - Estado
     - Nota
   * - ``_build_zip_from_attachments``
     - **portado** (adaptado)
     - se adapta a ``datas`` (FileField, no ``raw``) y a función de módulo
       (no hay recordset que iterar con ``self``)
   * - ``_except_audit_trail``
     - **bloqueado**
     - ``ResCompany.restrictive_audit_trail`` no existe
   * - ``write`` (override)
     - **bloqueado**
     - envuelve a ``_except_audit_trail``
   * - ``unlink`` (override)
     - **bloqueado**
     - misma razón — protege el mismo campo ausente
   * - ``_post_add_create``
     - **bloqueado**
     - ``AccountMove._to_files_data``/``_unwrap_attachments``/
       ``_extend_with_attachments`` no existen

Bloqueo — el eje de "audit trail restrictivo" no está portado
==================================================================

Cuatro de los cinco símbolos giran sobre **una** pieza ausente:
``company_id.restrictive_audit_trail``, el campo que activa el modo de
retención legal de adjuntos de factura (México y otras jurisdicciones con
requisito de auditoría fiscal estricta). Medido en este mismo pase:

.. code-block:: text

    grep -rln "restrictive_audit_trail" src/ addons/ --include=*.py
    → 0 hits

[PROVEN]. Sin el campo, ``_except_audit_trail`` no tiene qué comprobar —
fabricar la validación sin el dato que la activa produciría un guard que
**siempre** deja pasar, indistinguible en el código de "no implementado" pero
peligroso porque parece que sí protege. **Desenlace: (b) bloqueado por pieza
concreta**, con sucesor: el Bloque 1 de ``res.company`` (tarea **#137**, ya
registrada en ``res_company.py`` de este mismo addon) es la precondición —
``restrictive_audit_trail`` es uno de los 70 campos que esa tarea cierra.

``write``/``unlink`` envuelven exactamente a ese guard (y, en el caso de
``unlink``, además protegen los PDF de factura mientras el candado esté
activo) — caen con él por transitividad.

``_post_add_create`` depende de una pieza distinta y también ausente:
``account.move._to_files_data`` / ``_unwrap_attachments`` /
``_extend_with_attachments`` — medido: ``grep -rn
"_to_files_data\|_unwrap_attachments\|_extend_with_attachments"
addons/account/models/*.py`` → 0 hits [PROVEN]. Es el pipeline de
reconocimiento automático de adjuntos como facturas entrantes (OCR / email
gateway); no tiene contraparte portada.

Lo que SÍ se porta
=====================

``build_zip_from_attachments`` (≙ ``_build_zip_from_attachments``) es
autocontenido: comprime en memoria el contenido de los adjuntos recibidos en
un ``.zip``. No depende de ninguna de las dos piezas ausentes.

Divergencia declarada — ``datas`` (FileField) en vez de ``raw`` (bytes)
=============================================================================

``IrAttachment.raw`` de la referencia es un campo binario en memoria; este
árbol declara ``datas`` como ``django.db.models.FileField`` (backend de
almacenamiento de Django, no el filestore sha1-sharded propio de Odoo — ver
el docstring de ``src/addons/base/models/ir_attachment.py``). Leer el
contenido exige abrir el archivo del storage backend
(``attachment.datas.open('rb')`` / ``.read()``) en vez de acceder a un
atributo de bytes ya en memoria. El contrato —bytes del adjunto, por
registro— es el mismo; cambia sólo cómo se obtienen.

``display_name`` tampoco existe como campo propio (es un compute de UI en la
referencia); se usa ``name``, que sí es el campo real y cumple el mismo rol
dentro del ``.zip`` (nombre visible de cada entrada).

Segunda divergencia declarada — sin recordset, no hay ``self`` sobre varios
=================================================================================

La referencia invoca esto como ``some_attachments._build_zip_from_attachments()``,
donde ``self`` puede ser un recordset de N filas — es el modelo de Odoo. Este
ORM es Django puro: una instancia de modelo es UNA fila, nunca un conjunto.
Colgar el método como método de instancia (``IrAttachment.method =
funcion``) e iterar ``for x in self`` fallaría en cuanto ``self`` fuera una
sola fila (``TypeError: 'IrAttachment' object is not iterable``).

Se porta como **función de módulo** que recibe explícitamente el iterable de
adjuntos (``build_zip_from_attachments(attachments)``, un queryset o
cualquier iterable de ``IrAttachment``) en vez de colgarse del modelo. El
contrato es el mismo función-por-función; lo que cambia es que el "self
recordset" de la referencia se vuelve un parámetro explícito, mismo criterio
que ``res_currency.assert_rounding_can_change`` recibe el valor nuevo en vez
de leerlo de un ``write(vals)`` ambiente.
"""
import io
import zipfile


def build_zip_from_attachments(attachments):
    """≙ ``_build_zip_from_attachments``
    (``odoo19c: account/models/ir_attachment.py:14-19``).

    Comprime el contenido de ``attachments`` (queryset o iterable de
    ``IrAttachment``) en un ``.zip`` y devuelve los bytes resultantes. Ver
    las dos divergencias declaradas del módulo (``datas`` FileField en vez
    de ``raw``; función de módulo en vez de método de instancia — no hay
    recordset que iterar con ``self``).
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for adjunto in attachments:
            if not adjunto.datas:
                continue
            adjunto.datas.open('rb')
            try:
                zf.writestr(adjunto.name, adjunto.datas.read())
            finally:
                adjunto.datas.close()
    return buffer.getvalue()


def apply_account_extensions():
    """≙ ``_inherit = 'ir.attachment'`` de ``account`` — no-op documentado.

    ``build_zip_from_attachments`` se porta como función de módulo, no como
    método de instancia (ver la segunda divergencia declarada del módulo):
    no hay ``add_to_class``/``setattr`` que aplicar sobre ``IrAttachment``.
    Se conserva esta función vacía sólo para que ``AccountConfig.ready()``
    pueda seguir invocando ``apply_account_extensions()`` de forma uniforme
    sobre todos los módulos de ``_EXTENSIONES``, igual que
    ``res_config_settings.py`` de este mismo pase no la declara en absoluto
    por no tener ningún símbolo colgable.
    """

