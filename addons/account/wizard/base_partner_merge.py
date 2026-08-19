"""``base.partner.merge.automatic.wizard`` — la extensión de ``account``.

Adaptación de Odoo ``addons/account/wizard/base_partner_merge.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

La referencia es una **extensión** (``_inherit``, sin ``_name`` propio) del
wizard de fusión de contactos que ``base`` declara en
``odoo19c: odoo/addons/base/wizard/base_partner_merge.py``. Declara un solo
símbolo: ``_get_summable_fields``, que suma ``customer_rank`` y
``supplier_rank`` a la lista de campos que la fusión agrega en vez de
sobreescribir.

Bloqueado por el wizard padre de ``base`` (dos piezas)
=======================================================

1. **La clase que se extiende no existe aún**: ``src/addons/base/`` no tiene
   directorio ``wizard/`` (medido: ``ls src/addons/base/`` → ``models``,
   ``data``, …, sin ``wizard``). Por eso ``_get_summable_fields`` no puede
   hacer ``super()``: devuelve **sólo la aportación de account**, y quien
   porte el wizard padre compone ambas listas — el ``+`` de la referencia,
   con los operandos invertidos.
2. **Los campos sumados tampoco existen**: ``customer_rank`` /
   ``supplier_rank`` son de la extensión de ``res.partner`` de ``account``
   (``odoo19c: addons/account/models/partner.py``), no portada — el propio
   docstring de ``src/addons/base/models/res_partner.py:37`` los declara
   fuera de ``base``. La lista se devuelve verbatim igualmente: es el
   contrato de este archivo, y el consumidor (el wizard padre) decide qué
   hacer con un campo aún ausente.
"""
from orm.models_transient import TransientModel


class BasePartnerMergeAutomaticWizard(TransientModel):
    """≙ la extensión de ``base.partner.merge.automatic.wizard`` que hace
    ``account``. Sin ``_name`` propio, igual que la fuente."""

    _inherit = 'base.partner.merge.automatic.wizard'

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def _get_summable_fields(cls):
        """Add to summable fields list, fields created in this module.
         - customer_rank and supplier_rank will have a better ranking for the merged partner

        (Docstring verbatim de la referencia.) Aquí sin ``super()`` — ver
        "Bloqueado por el wizard padre" en el docstring del módulo: se
        devuelve sólo la aportación de ``account``.
        """
        return ['customer_rank', 'supplier_rank']
