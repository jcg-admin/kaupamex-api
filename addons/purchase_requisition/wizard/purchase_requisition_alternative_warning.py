"""``purchase.requisition.alternative.warning`` — qué hacer con las cotizaciones
alternativas al confirmar (Odoo ``purchase_requisition``).

Adaptación de Odoo
``purchase_requisition/wizard/purchase_requisition_alternative_warning.py``
(``odoo19c: addons/purchase_requisition/wizard/
purchase_requisition_alternative_warning.py``, 23 líneas, LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: la pregunta que ``PurchaseOrder.button_confirm`` dispara cuando se va a
confirmar una orden que todavía tiene alternativas abiertas. Dos salidas —
mantenerlas o cancelarlas—, y las dos terminan confirmando la orden.

Porte símbolo por símbolo — 5 de 5
====================================

*Métrica:* entradas del cuerpo de ``class PurchaseRequisitionAlternativeWarning``
contadas por AST sobre la fuente, descontando ``_name`` y ``_description``. Son
**5**: 2 campos y 3 métodos.
*Ciega a:* si el asistente se comporta igual en ejecución.

======================================  =====================================
Símbolo de la referencia (línea)        Dónde queda en este puerto
======================================  =====================================
``po_ids`` (``:12``)                    parámetro ``po_ids`` de los tres métodos
``alternative_po_ids`` (``:13``)        parámetro ``alternative_po_ids``
``action_keep_alternatives`` (``:15``)  ``@classmethod`` homónimo
``action_cancel_alternatives`` (``:18``) ``@classmethod`` homónimo
``_action_done`` (``:22-23``)           ``@classmethod`` homónimo
======================================  =====================================

Divergencia declarada — los campos son parámetros
===================================================

``TransientModel`` en este árbol es abstracto y ``managed = False``
(``src/orm/models_transient.py:29-36``): **no tiene tabla**. El idioma ya
fijado por los ocho asistentes de ``account`` —``AccountAutomaticEntryWizard``
(``addons/account/wizard/account_automatic_entry_wizard.py:130-140``) es el
canónico— es declarar la clase con sus atributos de modelo y convertir los
campos en **argumentos explícitos de ``@classmethod``**. Se repite aquí sin
inventar una segunda forma.

Consecuencia: los dos ``fields.Many2many`` de la fuente
(``warning_purchase_order_rel`` y ``warning_purchase_order_alternative_rel``)
no producen tabla intermedia. No hace falta: el asistente es efímero por
definición y sus dos conjuntos llegan del contexto que ``button_confirm``
arma (``default_po_ids`` / ``default_alternative_po_ids``).

Nota de la fuente que se conserva
===================================

El comentario de ``action_cancel_alternatives`` (``:19``) explica el guard que
de otro modo parece redundante: *«in theory alternative_po_ids shouldn't have
any po_ids in it, but it's possible by accident/forcing it, so avoid cancelling
them to be safe»*. Por eso se excluyen las órdenes que están en las dos listas
antes de cancelar.
"""
from orm.environments import context_scope
from orm.models_transient import TransientModel


class PurchaseRequisitionAlternativeWarning(TransientModel):
    """``purchase.requisition.alternative.warning`` — «Wizard in case PO still
    has open alternative requests for quotation»."""

    # Atributos de clase de modelo — los DOS que la fuente declara
    # (``odoo19c: :9-10``), verbatim.
    _name = 'purchase.requisition.alternative.warning'
    _description = ('Wizard in case PO still has open alternative requests '
                    'for quotation')

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def action_keep_alternatives(cls, po_ids, alternative_po_ids=()):
        """≙ ``action_keep_alternatives`` (``odoo19c: :15-16``).

        Mantener las alternativas: se confirma la orden y las demás siguen
        vivas. ``alternative_po_ids`` se recibe por simetría con su hermano y
        no se usa — igual que en la fuente.
        """
        return cls._action_done(po_ids)

    @classmethod
    def action_cancel_alternatives(cls, po_ids, alternative_po_ids=()):
        """≙ ``action_cancel_alternatives`` (``odoo19c: :18-20``).

        Cancela las alternativas abiertas y después confirma. El guard de la
        fuente se conserva: una orden que esté en **las dos** listas no se
        cancela (ver la nota del docstring del módulo).
        """
        to_confirm = {getattr(po, 'pk', po) for po in po_ids}
        for po in alternative_po_ids:
            if getattr(po, 'pk', po) in to_confirm:
                continue
            if po.state in (type(po).STATE_DRAFT, type(po).STATE_SENT):
                po.button_cancel()
        return cls._action_done(po_ids)

    @classmethod
    def _action_done(cls, po_ids):
        """≙ ``_action_done`` (``odoo19c: :22-23``).

        Confirma las órdenes **saltándose la guarda de alternativas**: es el
        propio asistente el que ya la resolvió. La fuente lo consigue con
        ``with_context({'skip_alternative_check': True})``; aquí el equivalente
        exacto es ``context_scope`` (``orm/environments.py:230-240``), que
        **suma** la clave a las que ya hubiera y la restaura al salir del
        bloque — mismo alcance acotado que el ``with_context`` de la fuente.
        """
        with context_scope(skip_alternative_check=True):
            return [po.button_confirm() for po in po_ids]
