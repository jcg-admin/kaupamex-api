"""
PDF receipt generation — UC-PAY-10.

Builds the JSON descriptor for an order and invokes the compiled libharu
helper (``tools/pdf/pdf_receipt``) via subprocess, returning the PDF bytes.
See ADR-017 (adr-017-libreria-pdf-libharu): the native helper is run out of
process so a libharu fault cannot take down the mod_wsgi worker.
"""
import json
import logging
import subprocess
from decimal import Decimal

from addons.sale.amounts import order_amounts
from pathlib import Path

from django.conf import settings

logger = logging.getLogger('apps')

# The helper binary is built by the server provisioner next to its source
# (see tools/pdf/Makefile). BASE_DIR == practicayoruba/ (config/settings/base.py).
HELPER_PATH = Path(settings.BASE_DIR) / 'tools' / 'pdf' / 'pdf_receipt'

# Hard ceiling so a hung helper cannot block the WSGI worker. UC-PAY-10 SLO is
# P95 < 2 s; 15 s is a generous failsafe.
HELPER_TIMEOUT_SECONDS = 15


class PdfGenerationError(Exception):
    """Raised when the libharu helper fails to produce a valid PDF."""


def _money(value) -> str:
    """Format a Decimal/number as a fixed 2-decimal string for the helper."""
    if value is None:
        return ''
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return f'{value:.2f}'


def build_receipt_payload(order, items, address, payment, site) -> dict:
    """Arma el descriptor JSON que consume el helper en C.

    Recibe objetos ORM ya cargados; los números llegan preformateados como
    string para que no haya deriva de punto flotante.

    El parámetro ``value`` desapareció con el espejo (SOL-098): los importes
    ya no viven en una entidad de cabecera aparte, se derivan de las líneas.
    """
    issuer = {
        'name':      site.site_name if site else 'PracticaYoruba',
        'address':   (site.address if site else '') or '',
        'email':     (site.support_email if site else '') or '',
        'phone':     (site.phone if site else '') or '',
        # H-API-PAY10-01: SiteSettings.logo (ImageField) feeds the receipt
        # logo. The helper treats an empty logo_path as "no logo", so an
        # unset logo degrades gracefully.
        'logo_path': _resolve_logo_path(site),
    }

    buyer_name = address.recipient_name if address else ''
    buyer_addr = ''
    if address:
        buyer_addr = (
            f'{address.street}, {address.city}, '
            f'{address.state} {address.zip_code}, {address.country}'
        )

    # El importe por renglón es el **bruto** de la línea (``price_total``,
    # IVA incluido como en el precio de catálogo), no el neto: la suma de los
    # renglones tiene que cuadrar con el total del recibo.
    item_rows = [
        {
            'name':       it.name,
            'sku':        it.product.sku if it.product_id else '',
            'quantity':   str(it.product_uom_qty),
            'unit_price': _money(it.price_unit),
            'amount':     _money(it.price_total()),
        }
        for it in items
    ]

    # Los importes del recibo se derivan de las líneas de la venta. Mismas
    # etiquetas del contrato, otra fuente que las columnas retiradas. El IVA
    # ahora incluye el envío en su base (H-API-41): el total no cambia, se
    # reparte distinto entre base e impuesto — que es la forma que el CFDI
    # necesita (H-API-35).
    _a = order_amounts(order)
    totals = {
        'subtotal': _money(_a['subtotal']),
        'tax':      _money(_a['tax']),
        'shipping': _money(_a['shipping_cost']),
        'discount': _money(_a['discount']),
        'total':    _money(_a['total']),
    }

    payment_block = {
        'method': payment.get_gateway_display() if payment else '',
        'status': payment.get_status_display() if payment else '',
    }

    return {
        'issuer':       issuer,
        'buyer':        {'name': buyer_name, 'address': buyer_addr},
        'order_number': order.name,
        'date':         order.created_at.isoformat() if order.created_at else '',
        'currency':     site.currency if site else 'MXN',
        'items':        item_rows,
        'totals':       totals,
        'payment':      payment_block,
    }


def _resolve_logo_path(site) -> str:
    """
    Resolve the issuer logo to an absolute PNG path for the helper.

    H-API-PAY10-01: reads SiteSettings.logo (ImageField). Returns '' when no
    logo is set so the receipt is generated without a logo. Kept as a seam so
    REP-05/LOG-10 plug in here without touching the helper.
    """
    logo = getattr(site, 'logo', None) if site else None
    if not logo:
        return ''
    try:
        return str(logo.path)
    except (ValueError, AttributeError):
        return ''


def render_receipt_pdf(payload: dict) -> bytes:
    """
    Invoke the libharu helper with the JSON payload on stdin and return the
    PDF bytes from stdout. Raises PdfGenerationError on any failure.
    """
    if not HELPER_PATH.exists():
        logger.error('PDF helper binary missing at %s', HELPER_PATH)
        raise PdfGenerationError(
            f'PDF helper not built at {HELPER_PATH}. Run '
            f'`make` in practicayoruba/tools/pdf/ (ADR-017).'
        )

    stdin_bytes = json.dumps(payload).encode('utf-8')
    try:
        proc = subprocess.run(
            [str(HELPER_PATH)],
            input=stdin_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=HELPER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error('PDF helper timed out after %ss', HELPER_TIMEOUT_SECONDS)
        raise PdfGenerationError('PDF helper timed out') from exc
    except OSError as exc:
        logger.error('PDF helper failed to execute: %s', exc)
        raise PdfGenerationError(f'PDF helper exec failed: {exc}') from exc

    if proc.returncode != 0:
        logger.error(
            'PDF helper exit=%s stderr=%s',
            proc.returncode, proc.stderr.decode('utf-8', 'replace')[:500],
        )
        raise PdfGenerationError(
            f'PDF helper exited {proc.returncode}'
        )

    pdf_bytes = proc.stdout
    if not pdf_bytes or not pdf_bytes.startswith(b'%PDF'):
        logger.error('PDF helper produced no valid PDF (len=%d)', len(pdf_bytes))
        raise PdfGenerationError('PDF helper produced invalid output')

    return pdf_bytes
