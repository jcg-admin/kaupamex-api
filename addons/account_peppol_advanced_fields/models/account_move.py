"""``account.move`` — las siete referencias avanzadas de Peppol BIS.

Adaptación de Odoo ``account_peppol_advanced_fields/models/account_move.py``
(``odoo19c: addons/account_peppol_advanced_fields/models/account_move.py``,
34 líneas, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: siete campos de texto que la factura electrónica europea (EN 16931 /
Peppol BIS Billing 3.0) admite como referencias documentales —al contrato, al
proyecto, al pedido de origen, al albarán— y que el generador UBL vuelca en
sus ``cac:*DocumentReference`` correspondientes. Sin métodos: el addon **sólo
aporta datos**.

Los siete llevan ``[DEPRECATED]`` en la propia fuente
==========================================================

No es una lectura nuestra: el ``__manifest__.py`` de la referencia se titula
``"[DEPRECATED] Account Peppol Advanced Fields"`` y su ``summary`` dice
*"Merged prematurly, not working correctly. Please don't use. Better solution
coming soon."* Cada una de las siete etiquetas empieza igual.

**Se portan de todos modos**, y por dos razones que se sostienen solas:

1. El porte es completo o declara su cobertura
   (``porte-completo-no-parcial.md``); un addon existente en la referencia se
   porta o se declara por qué no, y «está deprecado» no es una de las tres
   salidas válidas — la sustitución que la fuente anuncia todavía no existe.
2. La marca ``[DEPRECATED]`` **se conserva verbatim en cada etiqueta**, que es
   lo que hace que el aviso viaje con el dato en vez de quedarse en una nota
   de porte que nadie lee.

Porte símbolo por símbolo — 7 símbolos, los 7 portados
=======================================================

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - Campo (línea)
     - Qué referencia, según la fuente
   * - ``peppol_contract_document_reference`` (``:7-10``)
     - el documento de contrato.
   * - ``peppol_project_reference`` (``:11-14``)
     - el proyecto.
   * - ``peppol_originator_document_reference`` (``:15-18``)
     - el documento que originó el pedido.
   * - ``peppol_despatch_document_reference`` (``:19-22``)
     - el albarán de envío.
   * - ``peppol_additional_document_reference`` (``:23-26``)
     - un documento de soporte adicional — **uno solo**, como la fuente
       advierte en su ``help``.
   * - ``peppol_accounting_cost`` (``:27-30``)
     - el centro de costo contable, como texto o código.
   * - ``peppol_delivery_location_id`` (``:31-34``)
     - el GLN (*Global Location Number*) del lugar de entrega.

Divergencias declaradas
=========================

1. **``peppol_delivery_location_id`` conserva su sufijo ``_id`` aunque sea un
   ``Char``.** En este árbol el sufijo ``_id`` marca el accesor de una FK, no
   un campo de texto — pero el nombre **es el contrato** con el generador UBL
   de la referencia, y renombrarlo rompería la correspondencia símbolo a
   símbolo sin ganar nada. Se declara aquí en vez de corregirlo en silencio.
   (En la fuente es igual de anómalo: también es ``fields.Char``.)
2. **``string=`` → ``verbose_name=``**, la forma de este árbol. El texto va en
   español salvo el prefijo ``[DEPRECATED]``, que se conserva verbatim porque
   es una marca, no prosa.
3. **``max_length`` explícito.** ``fields.Char`` de la referencia no lo lleva
   (Odoo lo mapea a ``varchar`` sin límite); aquí el ``CharField`` de Django
   exige uno. Se fija en 255, que es el ancho por defecto del árbol para
   referencias documentales.
"""
import fields
from addons.account.models.account_move import AccountMove
from orm.model_classes import add_field_if_absent

#: Ancho de las siete referencias. La fuente no declara ninguno (``varchar``
#: sin límite en Odoo); ver divergencia 3.
_REFERENCE_MAX_LENGTH = 255


def _fields():
    """Los siete campos que este addon cuelga sobre ``account.AccountMove``.

    El prefijo ``[DEPRECATED]`` de cada etiqueta es **verbatim de la fuente**
    (``odoo19c: :8,12,16,20,24,28,32``): viaja con el dato para que el aviso
    llegue a quien lo vea en un formulario, no sólo a quien lea este archivo.
    """
    return {
        'peppol_contract_document_reference': fields.Char(
            max_length=_REFERENCE_MAX_LENGTH, blank=True, default='',
            verbose_name='[DEPRECATED] Referencia al documento de contrato',
            help_text='Una referencia al documento de contrato (Odoo '
                      'peppol_contract_document_reference).',
        ),
        'peppol_project_reference': fields.Char(
            max_length=_REFERENCE_MAX_LENGTH, blank=True, default='',
            verbose_name='[DEPRECATED] Referencia al proyecto',
            help_text='Una referencia al proyecto (Odoo peppol_project_reference).',
        ),
        'peppol_originator_document_reference': fields.Char(
            max_length=_REFERENCE_MAX_LENGTH, blank=True, default='',
            verbose_name='[DEPRECATED] Referencia al documento originador',
            help_text='Una referencia al documento que originó el pedido (Odoo '
                      'peppol_originator_document_reference).',
        ),
        'peppol_despatch_document_reference': fields.Char(
            max_length=_REFERENCE_MAX_LENGTH, blank=True, default='',
            verbose_name='[DEPRECATED] Referencia al albarán',
            help_text='Una referencia al documento de envío (Odoo '
                      'peppol_despatch_document_reference).',
        ),
        'peppol_additional_document_reference': fields.Char(
            max_length=_REFERENCE_MAX_LENGTH, blank=True, default='',
            verbose_name='[DEPRECATED] Referencia a documento adicional',
            help_text='Una referencia a un documento de soporte adicional. Sólo '
                      'se puede referenciar UN documento (Odoo '
                      'peppol_additional_document_reference).',
        ),
        'peppol_accounting_cost': fields.Char(
            max_length=_REFERENCE_MAX_LENGTH, blank=True, default='',
            verbose_name='[DEPRECATED] Centro de costo contable',
            help_text='Descripción textual o código que identifica el centro de '
                      'costo contable (Odoo peppol_accounting_cost).',
        ),
        # Sufijo `_id` conservado aunque sea texto — ver divergencia 1 del módulo.
        'peppol_delivery_location_id': fields.Char(
            max_length=_REFERENCE_MAX_LENGTH, blank=True, default='',
            verbose_name='[DEPRECATED] GLN del lugar de entrega',
            help_text='El Global Location Number (GLN) del lugar de entrega (Odoo '
                      'peppol_delivery_location_id, Char pese al sufijo _id).',
        ),
    }


def apply_account_peppol_advanced_fields_account_move_extensions():
    """Cuelga sobre ``account.AccountMove`` las siete referencias avanzadas —
    ≙ ``_inherit = "account.move"``. La llama
    ``AccountPeppolAdvancedFieldsConfig.ready()``.

    ``add_field_if_absent`` es idempotente: si otro addon ya colgó el mismo
    nombre, no lo duplica (el idioma de extensión por ``add_to_class`` no tiene
    MRO).
    """
    for name, field in _fields().items():
        add_field_if_absent(AccountMove, name, field)


__all__ = ['apply_account_peppol_advanced_fields_account_move_extensions']
