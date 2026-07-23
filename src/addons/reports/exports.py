"""
Report exports — UC-RPT-04 / UC-REP-05.

Each report is first normalized to a tabular shape ``(title, headers, rows)``
that reproduces exactly the columns/values of the report view (FR-RPT-04.02:
"las columnas del archivo reproducen las metricas de la vista, sin anadir ni
omitir ninguna"). The normalized table is then rendered to one of three
server-side formats:

- CSV  — streaming, text/csv.
- XLSX — real spreadsheet via the ``xlsxwriter`` library (BSD-licensed),
         application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.
- PDF  — real document via the libharu helper ``tools/pdf/pdf_report``
         invoked out of process (ADR-017, crash-isolated like the receipt).
"""
import csv
import io
from datetime import datetime, timezone as _tz

import xlsxwriter
from django.http import HttpResponse, StreamingHttpResponse

from .pdf_report import (
    PdfGenerationError, build_report_payload, render_report_pdf,
)

_XLSX_CONTENT_TYPE = (
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)


# ───────────────────────── Renderers ────────────────────────────────────────

def _streaming_csv(rows, headers, filename):
    """Yield a CSV file as a streaming response."""

    def row_iter():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        yield buf.getvalue()
        buf.seek(0); buf.truncate(0)
        for row in rows:
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0); buf.truncate(0)

    response = StreamingHttpResponse(row_iter(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _xlsx_response(rows, headers, filename, sheet_name='Report'):
    """Build a real .xlsx workbook in memory and return it as a download."""
    buf = io.BytesIO()
    workbook = xlsxwriter.Workbook(buf, {'in_memory': True})
    worksheet = workbook.add_worksheet(sheet_name[:31] or 'Report')
    header_fmt = workbook.add_format({'bold': True})

    for col, head in enumerate(headers):
        worksheet.write(0, col, str(head), header_fmt)
    for r, row in enumerate(rows, start=1):
        for col, value in enumerate(row):
            worksheet.write(r, col, '' if value is None else str(value))

    workbook.close()
    buf.seek(0)
    response = HttpResponse(buf.getvalue(), content_type=_XLSX_CONTENT_TYPE)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _pdf_response(title, headers, rows, filename, subtitle=''):
    """Render a real PDF table via the libharu helper (ADR-017)."""
    payload = build_report_payload(
        title=title, columns=headers, rows=rows,
        subtitle=subtitle, generated_at=_iso_now(),
    )
    pdf_bytes = render_report_pdf(payload)  # raises PdfGenerationError on failure
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _ts_suffix():
    return datetime.now(_tz.utc).strftime('%Y%m%d-%H%M%S')


def _iso_now():
    return datetime.now(_tz.utc).strftime('%Y-%m-%dT%H:%M:%S')


# ─────────────────── Report → normalized table builders ─────────────────────
#
# Each builder returns (title, headers, rows). The exporter functions below
# pick the renderer by format. CSV/XLSX/PDF all consume the SAME table, so the
# three formats are guaranteed to share columns and values (FR-RPT-04.02).

def _sales_table(payload):
    headers = ['Metric', 'Value']
    rows = [
        ['Revenue', payload['totals']['revenue']],
        ['Orders', payload['totals']['orders']],
        ['Average ticket', payload['totals']['average_ticket']],
        ['Previous revenue', payload['comparison']['previous_revenue']],
    ]
    return 'Sales report', headers, rows


def _top_sellers_table(payload):
    headers = ['product_id', 'product_name', 'sku', 'units_sold', 'revenue']
    rows = [(r['product_id'], r['product_name'], r['sku'],
             r['units_sold'], r['revenue'])
            for r in payload['results']]
    return 'Top sellers report', headers, rows


def _customers_rfm_table(payload):
    headers = ['user_id', 'email', 'recency_days',
               'frequency', 'monetary', 'segment']
    rows = [(r['user_id'], r['email'], r['recency_days'],
             r['frequency'], r['monetary'], r['segment'])
            for r in payload['results']]
    return 'Customers RFM report', headers, rows


def _dashboard_table(payload):
    headers = ['metric', 'value']
    rows = [
        ('today_revenue', payload['today']['revenue']),
        ('today_orders', payload['today']['orders']),
        ('open_tickets', payload['open_tickets']),
        ('low_stock_alerts', payload['low_stock_alerts']),
    ]
    return 'Dashboard report', headers, rows


def _render(table, base, fmt):
    """Route a normalized (title, headers, rows) table to the chosen format."""
    title, headers, rows = table
    fmt = (fmt or 'csv').lower()
    if fmt == 'csv':
        return _streaming_csv(rows, headers, f'{base}.csv')
    if fmt == 'xlsx':
        return _xlsx_response(rows, headers, f'{base}.xlsx')
    if fmt == 'pdf':
        return _pdf_response(title, headers, rows, f'{base}.pdf')
    return None


# ────────────────────────── Exporters ───────────────────────────────────────

def export_sales(payload: dict, fmt: str):
    return _render(_sales_table(payload), f'sales-{_ts_suffix()}', fmt)


def export_top_sellers(payload: dict, fmt: str):
    return _render(_top_sellers_table(payload), f'top-sellers-{_ts_suffix()}', fmt)


def export_customers_rfm(payload: dict, fmt: str):
    return _render(_customers_rfm_table(payload),
                   f'customers-rfm-{_ts_suffix()}', fmt)


def export_dashboard(payload: dict, fmt: str):
    return _render(_dashboard_table(payload), f'dashboard-{_ts_suffix()}', fmt)


EXPORTERS = {
    'sales': export_sales,
    'top-sellers': export_top_sellers,
    'customers-rfm': export_customers_rfm,
    'dashboard': export_dashboard,
}

# Re-export for callers/tests that want to detect helper failures.
__all__ = ['EXPORTERS', 'PdfGenerationError']
