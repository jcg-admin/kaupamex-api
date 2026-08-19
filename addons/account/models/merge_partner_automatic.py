"""``base.partner.merge.automatic.wizard`` colgado por ``account`` — bypass de auditoría al fusionar.

Adaptación de ``addons/account/models/merge_partner_automatic.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3 — atribución y aviso de
licencia preservados, DEC-KX-03).

.. code-block:: python

   class BasePartnerMergeAutomaticWizard(models.TransientModel):
       _inherit = 'base.partner.merge.automatic.wizard'

       def _update_reference_fields(self, src_partners, dst_partner):
           return super(BasePartnerMergeAutomaticWizard,
               self.with_context(bypass_audit=bypass_token)
           )._update_reference_fields(src_partners, dst_partner)

No confundir con la extensión hermana de ``wizard/base_partner_merge.py``
============================================================================

El árbol de la referencia declara **dos** contribuciones distintas de
``account`` al mismo wizard, en dos archivos: ``account/wizard/
base_partner_merge.py`` (``_get_summable_fields``, ya portada en
``api: addons/account/wizard/base_partner_merge.py``) y ``account/models/
merge_partner_automatic.py`` (este archivo, ``_update_reference_fields``).
Cada una vive en su hogar espejado — ``wizard/`` aquí, ``models/`` allá — no
se fusionan en un solo archivo.

**El wizard base SÍ existe aquí** (corrige la premisa del hermano). El
docstring de ``wizard/base_partner_merge.py`` mide, a su fecha, que
``src/addons/base/`` no tenía directorio ``wizard/`` — desde entonces
aterrizó: ``src/addons/base/wizard/base_partner_merge.py`` declara la clase
``PartnerMerge`` con ``_update_reference_fields`` (classmethod, línea 347) y
``_update_reference_fields_generic`` (línea 300) — el método real que este
archivo debía envolver.

Por qué el envoltorio de la referencia no aporta nada aquí — medido
=======================================================================

``_update_reference_fields_generic`` repunta las referencias genéricas por
**UPDATE en bloque** (``queryset.update(...)``) o **SQL crudo**
(``cursor.execute("UPDATE ...")``, líneas 279-297 de la fuente local) — nunca
por ``instancia.save()``. El guard de auditoría de ``mail_message.py`` (este
mismo pase) cuelga de ``save()`` vía ``chain_method`` — un ``UPDATE`` en
bloque o SQL crudo **no lo dispara nunca**, por diseño: es la vía rápida que
una fusión masiva necesita, y pasar por ``save()`` fila-a-fila la haría
inviable a escala.

Consecuencia: el ``bypass_audit=bypass_token`` que la referencia enhebra por
``self.with_context(...)`` no tiene nada que anular en este árbol — el
camino que protegería (``save()``) nunca está en la ruta de
``_update_reference_fields_generic``. Por esa razón este archivo **no**
declara un ``bypass_token`` en ``mail_message.py``: sería un sentinel sin
consumidor, y ``mail_message.py`` ya no lo importa (medido:
``grep -n bypass_token addons/account/models/mail_message.py`` → 0 hits,
correcto).

Sigue habiendo algo que portar
================================

Lo que SÍ sobrevive del método es la *forma*: la referencia envuelve la
llamada al padre — aquí, encadenar sobre el ``_update_reference_fields`` real
de ``PartnerMerge`` es el equivalente estructural, aunque el cuerpo quede
vacío de lógica propia (documentado, no relleno). Se implementa con
``chain_method`` en semántica de relevo: esta función no hace nada y
devuelve ``None``, así que la implementación real de ``PartnerMerge`` corre
sin modificación — que es, medido, el comportamiento correcto dado que no
hay nada que anular.
"""
from addons.base.wizard.base_partner_merge import PartnerMerge
from orm.method_chain import chain_method


def _update_reference_fields(cls, src_partners, dst_partner):
    """≙ ``_update_reference_fields`` (``odoo19c: account/models/
    merge_partner_automatic.py:8-10``).

    Sin cuerpo propio a propósito — ver "Por qué el envoltorio... no aporta
    nada aquí" en el docstring del módulo. Devuelve ``None``: bajo
    ``chain_method`` (relevo) eso invoca la implementación previa
    (``PartnerMerge._update_reference_fields`` real) sin alterarla.
    """
    return None


def apply_account_extensions():
    """Cuelga la extensión (vacía, documentada) sobre ``PartnerMerge`` — ≙ ``_inherit``.

    **Todavía no cableado** en ``AccountConfig._EXTENSIONES`` — mismo estado
    declarado que ``mail_message.py``/``mail_template.py``/
    ``mail_tracking_value.py`` de este mismo pase. ``_update_reference_fields``
    es ``@classmethod`` en ``PartnerMerge`` (línea 346-347 del wizard base);
    se encadena como tal para que ``chain_method`` reinstale el mismo tipo de
    descriptor (ver la tabla de ``orm/method_chain.py``).
    """
    chain_method(PartnerMerge, '_update_reference_fields',
                 classmethod(_update_reference_fields))
