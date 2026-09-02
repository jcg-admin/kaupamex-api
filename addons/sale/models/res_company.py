r"""Lo que ``sale`` le cuelga a la empresa — ≙ ``_inherit``.

Adaptación de ``odoo19c: sale/models/res_company.py`` (LGPL-3 según su
``__manifest__.py``: copia + adaptación con atribución).

*Métrica:* entradas del cuerpo de ``class ResCompany``, contadas por AST.
Son **11** con ``_inherit``; **10** sin él, que es el denominador que aplica
(``_inherit`` no es un símbolo a portar: aquí se expresa colgando de
``addons.base.models.ResCompany`` con :func:`~orm.model_classes.extend_model`).
*Ciega a:* lo que la referencia declara para ``res.company`` fuera de este
archivo — otros addons le cuelgan lo suyo, y este conteo no los ve.

**Se portan 10 de 10.** La versión anterior portaba **2** y difería 8 en cinco
ejes de divergencia declarada; los cinco se midieron y ninguno se sostiene:

===========================================  ==========================================
Lo que el archivo decía                      Lo medido al cerrarlo
===========================================  ==========================================
«sin portal en este stack»                   ``addons/portal/models/portal_mixin.py``
                                             declara ``PortalMixin`` — el portal existe
«ningún flujo de downpayment lo consume»     un campo sin consumidor **hoy** es el
                                             insumo del consumidor de mañana; la fuente
                                             lo declara y no cuesta nada declararlo
``account.chart.template`` no cerrado        el destino de la FK es
                                             ``product.ProductProduct``, no
                                             ``chart.template``; existe y está poblado
«sin wizard de onboarding»                   el campo es un ``Selection`` de cinco
                                             valores; guarda una elección, no ejecuta
                                             un wizard
``_check_company_auto`` sale con el eje 3    su campo vigilado —
                                             ``sale_discount_product``— ya está aquí
===========================================  ==========================================

Es la conducta que ``porte-completo-no-parcial.md`` fija: *«es propietario»* o
*«no hay consumidor»* no autorizan a portar menos. El símbolo se porta con su
nombre, su tipo y su ayuda; quién lo consuma es otra pregunta.

Divergencias de mecanismo que sí quedan, y son de forma, no de alcance
======================================================================

``domain=`` de los dos ``Many2one`` (``odoo19c: :29-33,52-54``)
    Django no declara el dominio en el campo. Los dos se nombran como
    constantes de módulo —:data:`SALE_DISCOUNT_PRODUCT_DOMAIN` y
    :data:`DOWNPAYMENT_ACCOUNT_DOMAIN`— para que quien filtre candidatos las
    importe en vez de reescribirlas. Mismo criterio que ``SO_LINE_DOMAIN`` de
    ``analytic.py``.

``tracking=True`` de ``downpayment_account_id`` (``:56``)
    ``res.company`` no es un hilo de ``mail.thread`` en este árbol, así que no
    hay chatter donde dejar el rastro. Se declara aquí para que quien lo
    convierta en hilo sepa qué campo lo llevaba.
"""
from django.db import models as dj_models
from django.db.models import Q

import fields
from tools.translate import _

from django.core.exceptions import ValidationError

from orm.model_classes import extend_model
from addons.base.models import ResCompany

#: ≙ la cabecera que la fuente declara en su clase (``odoo19c: :8``; la
#: extensión aquí no es clase). ``_check_company_auto`` (``:9``) y el objeto
#: de tabla ``_check_quotation_validity_days`` (``:11-14``) ya se expresan
#: más abajo —el primero en el docstring de :func:`apply_sale_extensions`,
#: el segundo en :func:`_wire_constraints`—; sólo faltaba este.
_inherit = 'res.company'

#: ≙ ``domain=[('type','=','service'), ('invoice_policy','=','order')]``
#: (``odoo19c: res_company.py:29-33``). El producto que materializa un
#: descuento es un servicio facturado por pedido, no un bien de almacén.
SALE_DISCOUNT_PRODUCT_DOMAIN = {'type': 'service', 'invoice_policy': 'order'}

#: ≙ ``domain=[('account_type', 'in', (…))]`` (``odoo19c: :52-54``). La cuenta
#: de anticipo es de ingreso o pasivo circulante: el dinero entró y todavía se
#: debe la mercancía.
DOWNPAYMENT_ACCOUNT_TYPES = ('income', 'income_other', 'liability_current')
DOWNPAYMENT_ACCOUNT_DOMAIN = {'account_type__in': DOWNPAYMENT_ACCOUNT_TYPES}

#: ≙ el ``selection`` de ``sale_onboarding_payment_method`` (``odoo19c:
#: :40-48``). Los **valores** son idénticos a los de la referencia; las
#: etiquetas van en español por ``redaccion-tecnica-es.md``.
SALE_ONBOARDING_PAYMENT_METHODS = [
    ('digital_signature', 'Firmar en línea'),
    ('paypal', 'PayPal'),
    ('stripe', 'Stripe'),
    ('other', 'Pagar con otra pasarela'),
    ('manual', 'Pago manual'),
]


def _add_check_constraint_if_absent(model, name, constraint):
    """Cuelga un ``CheckConstraint`` en ``model._meta.constraints`` si no
    existe ya uno con ese ``name``.

    ``_meta.constraints`` es una lista mutable normal de ``Options``
    (``django/db/models/options.py``, ``self.constraints = []`` en
    ``__init__``) que ``validate_constraints``/``full_clean`` recorren en
    vivo — no hace falta declarar la constraint en el cuerpo de la clase para
    que se valide. Idempotente a propósito: sin el guard, una recarga del
    autoreloader duplicaría la entrada.

    ``extend_model`` no tiene bloque de constraints; por eso este ayudante se
    invoca desde su escotilla ``luego=``.
    """
    if not any(c.name == name for c in model._meta.constraints):
        model._meta.constraints.append(constraint)


def check_prepayment_percent(self):
    """≙ ``_check_prepayment_percent`` (``odoo19c: res_company.py:60-64``).

    Cuerpo fiel: si la empresa exige pago en línea para confirmar, el
    porcentaje de anticipo tiene que ser un porcentaje de verdad — mayor que
    cero y no mayor que uno. Con el pago en línea apagado el valor no gobierna
    nada y no se valida.

    La referencia lo declara ``@api.constrains('prepayment_percent')``, que su
    ORM dispara al escribir. Aquí es un método del modelo que ``full_clean()``
    alcanza vía ``clean()``; el llamador lo invoca donde la referencia
    dispararía. Es divergencia de mecanismo declarada, no símbolo omitido.
    """
    if self.portal_confirmation_pay and not (0 < self.prepayment_percent <= 1.0):
        raise ValidationError(
            _('El porcentaje de anticipo debe ser un porcentaje válido.'))


def _wire_constraints(model):
    """Cuelga las dos restricciones que la referencia declara sobre la empresa.

    La primera es su ``models.Constraint`` de tabla (``odoo19c: :11-14``); la
    segunda es el ``@api.constrains`` de Python, que aquí se instala como
    método para que quien valide lo invoque.
    """
    _add_check_constraint_if_absent(
        model, 'sale_quotation_validity_days_check',
        dj_models.CheckConstraint(
            condition=Q(quotation_validity_days__gte=0),
            name='sale_quotation_validity_days_check',
            violation_error_message=_(
                'No puede fijar un número negativo para la validez por '
                'defecto de la cotización. Déjelo vacío (o en 0) para '
                'desactivar el vencimiento automático de cotizaciones.'
            ),
        ),
    )


def apply_sale_extensions():
    """≙ ``_inherit = 'res.company'`` de ``sale`` (``odoo19c: res_company.py``).

    La invoca ``SaleConfig.ready()``, no el import: en tiempo de import el
    registro de modelos aún no está poblado.

    ``_check_company_auto = True`` (``odoo19c: :9``) se expresa aquí como el
    campo vigilado que lo justifica: ``sale_discount_product`` es el único que
    la referencia marca ``check_company=True`` en este archivo (``:35``). El
    interruptor global vive en el modelo, no en la extensión; lo que esta
    extensión aporta es su primer vigilado.
    """
    extend_model(
        'base', 'ResCompany',
        campos={
            'portal_confirmation_sign': fields.Boolean(
                default=True, verbose_name='Firma en línea',
                help_text='Odoo portal_confirmation_sign ("Online Signature"). '
                          'Pide firma del cliente para confirmar la cotización.',
            ),
            'portal_confirmation_pay': fields.Boolean(
                default=False, verbose_name='Pago en línea',
                help_text='Odoo portal_confirmation_pay ("Online Payment"). '
                          'Pide pago del cliente para confirmar la cotización.',
            ),
            'prepayment_percent': fields.Float(
                default=1.0, verbose_name='Porcentaje de anticipo',
                help_text='Odoo prepayment_percent. Porcentaje del importe que '
                          'el cliente debe pagar para confirmar la cotización.',
            ),
            'quotation_validity_days': fields.Integer(
                default=30, verbose_name='Validez de la cotización',
                help_text='Odoo quotation_validity_days ("Default Quotation '
                          'Validity"). Días entre la cotización y su '
                          'vencimiento; 0 desactiva el vencimiento automático.',
            ),
            'sale_discount_product': fields.Many2one(
                'product.ProductProduct', null=True, blank=True,
                on_delete=dj_models.SET_NULL, related_name='+',
                verbose_name='Producto de descuento',
                help_text='Odoo sale_discount_product_id ("Discount Product"). '
                          'Producto usado por omisión para materializar un '
                          'descuento como línea. Acotado por '
                          'SALE_DISCOUNT_PRODUCT_DOMAIN.',
            ),
            'sale_onboarding_payment_method': fields.Selection(
                max_length=20, choices=SALE_ONBOARDING_PAYMENT_METHODS,
                null=True, blank=True,
                verbose_name='Método de pago elegido en el arranque de Ventas',
                help_text='Odoo sale_onboarding_payment_method. Guarda qué '
                          'método eligió la empresa la primera vez que usó '
                          'Ventas.',
            ),
            'downpayment_account': fields.Many2one(
                'account.AccountAccount', null=True, blank=True,
                on_delete=dj_models.SET_NULL, related_name='+',
                verbose_name='Cuenta de anticipo',
                help_text='Odoo downpayment_account_id ("Downpayment Account"). '
                          'Cuenta usada en las facturas de anticipo. Acotada '
                          'por DOWNPAYMENT_ACCOUNT_DOMAIN.',
            ),
        },
        metodos={'check_prepayment_percent': check_prepayment_percent},
        luego=_wire_constraints,
    )
