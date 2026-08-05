"""Reportes de ``sale`` — declaración del addon dueño.

Espeja ``odoo19c: sale/report/ir_actions_report.xml``, que declara **dos**
registros sobre ``sale.order`` (medido, ``odoo-tools@622ddc2a``):

.. code-block:: text

   action_report_saleorder          qweb-pdf  sale.order  sale.report_saleorder
   action_report_pro_forma_invoice  qweb-pdf  sale.order  sale.report_saleorder_pro_forma

Los dos comparten modelo y tipo; se distinguen por el documento — que es
exactamente el punto de la cadena: la declaración apunta al documento por
``report_name``, y el motor no conoce ninguno de los dos.

Aquí la proforma **no se declara todavía**: su diferencia con la orden es el
encabezado y la ausencia de número fiscal, y ese matiz depende de la
numeración de ``account``, que no está resuelta. Declararla ahora sería
inventar la diferencia. Se nombra la ausencia en vez de rellenarla.
"""
import base64
from decimal import Decimal

from addons.base.models.ir_actions_report import REPORT_TYPE_PDF
from addons.base.report_catalog import ReportSpec

#: Moneda del descriptor cuando la compañía no declara una. El helper sólo la
#: imprime; no convierte.
DEFAULT_CURRENCY = 'MXN'


def _money(value):
    """Formatea un importe como string de 2 decimales.

    Los números viajan **preformateados** al helper: su contrato lo dice
    explícito (*"All numeric fields are passed as already-formatted strings
    from Django to avoid float/Decimal drift"*). El helper sólo los coloca.
    """
    if value is None:
        return ''
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f'{value:.2f}'


def _issuer(company):
    """Emisor del documento — la compañía L1 dueña de la orden.

    La identidad vive en ``ResCompany.partner``, no en la compañía: es la
    forma de la referencia (``odoo19c: res_company.py:296-300`` fabrica el
    ``res.partner`` dentro del ``create``), y ``ResCompany.name`` es una
    propiedad que lee de ahí.

    Sin compañía —órdenes previas al backfill L3, que la FK admite como
    ``NULL``— el emisor sale vacío en vez de reventar: un descriptor
    incompleto produce un PDF incompleto, que es mejor diagnóstico que una
    excepción a 200 líneas del dato faltante.
    """
    if company is None:
        return {'name': '', 'address': '', 'email': '', 'phone': '',
                'logo': ''}
    partner = getattr(company, 'partner', None)
    address = ', '.join(part for part in (
        getattr(partner, 'street', ''), getattr(partner, 'city', ''),
        getattr(partner, 'zip', ''),
    ) if part)
    return {
        'name': company.name or '',
        'address': address,
        'email': getattr(partner, 'email', '') or '',
        'phone': getattr(partner, 'phone', '') or '',
        # T-006: el logo viaja DENTRO del descriptor (base64 de un PNG) y el
        # helper lo incrusta con LoadPngImageFromMem — no toca el filesystem.
        # Cadena vacía = "sin logo"; la ausencia degrada sola.
        'logo': _logo_b64(company),
    }


def _logo_b64(company):
    """Bytes del logo como base64, o ``''`` si no hay o no es PNG.

    ``ResCompany.logo`` es ``related`` a ``partner.image_1920`` (ImageField).
    El helper sólo acepta PNG (ADR-017): otro formato degrada a "sin logo"
    aquí, no en C — el descriptor nunca lleva bytes que el helper no pueda
    incrustar. La firma se comprueba sobre los bytes reales, no sobre la
    extensión del archivo.
    """
    logo = getattr(company, 'logo', None)
    if not logo:
        return ''
    try:
        logo.open('rb')
        data = logo.read()
        logo.close()
    except (OSError, ValueError):
        # silent OK because un archivo perdido en disco no debe tumbar el
        # recibo: el logo es adorno, el documento es el entregable.
        return ''
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        return ''
    return base64.b64encode(data).decode('ascii')


def _buyer(order):
    """Comprador — partner registrado, o el email del comprador anónimo.

    ``guest_email`` existe porque el checkout anónimo (BR-011) no crea
    partner; en la referencia el invitado es un partner efímero de
    ``website_sale``. Aquí el snapshot del email es lo único que hay.
    """
    partner = getattr(order.partner, 'partner', None) if order.partner else None
    if partner is not None:
        return {'name': partner.name or '', 'address': ', '.join(
            part for part in (partner.street, partner.city, partner.zip)
            if part)}
    return {'name': order.guest_email or '', 'address': ''}


def build_sale_order(records, **ctx):
    """Descriptor de ``sale.report_saleorder`` para **una** orden.

    Un solo registro, no un recordset: el helper ``pdf_receipt`` produce un
    documento por invocación. Rendir N órdenes en un PDF exige fusionar
    (``_merge_pdfs`` de la referencia, paso 6), que aquí no existe todavía —
    ver el motor en ``base/models/ir_actions_report.py``.
    """
    order = records[0] if isinstance(records, (list, tuple)) else records
    lines = order.order_line.select_related('product').all()
    return {
        'issuer': _issuer(order.company),
        'buyer': _buyer(order),
        'order_number': order.name or f'#{order.pk}',
        'date': (order.date_order or order.created_at).isoformat(
            timespec='seconds'),
        'currency': ctx.get('currency', DEFAULT_CURRENCY),
        'items': [
            {
                'name': line.name or str(line.product),
                'sku': getattr(line.product, 'default_code', '') or '',
                'quantity': str(line.product_uom_qty),
                'unit_price': _money(line.price_unit),
                'amount': _money(line.price_unit * line.product_uom_qty),
            }
            for line in lines
        ],
        'totals': {
            'subtotal': _money(order.amount_untaxed),
            'tax': _money(order.amount_tax),
            'total': _money(order.amount_total),
        },
        # ``payment`` se omite deliberadamente: una orden de venta no es un
        # comprobante de pago. El helper lo guarda tras ``if (payment)``
        # (``pdf_receipt.c:496``), así que su ausencia no dibuja la sección.
    }


REPORTS = (
    ReportSpec(
        report_name='sale.report_saleorder',
        model='sale.SaleOrder',
        name='Orden de venta',
        builder=build_sale_order,
        report_type=REPORT_TYPE_PDF,
        helper='pdf_receipt',
    ),
)
