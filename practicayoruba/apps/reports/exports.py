"""
Report exports — UC-REP-05.

CSV and minimal PDF (text/plain placeholder) renderers. Real PDF rendering
requires a separate dependency; the placeholder satisfies the streaming
contract expected by the UI (Content-Disposition with .pdf filename).
"""
import csv
import io
from datetime import datetime, timezone as _tz
from django.http import HttpResponse, StreamingHttpResponse



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


def _placeholder_pdf(text, filename):
    """
    Minimal PDF-ish payload. Real PDF rendering needs reportlab/weasyprint.
    Returned as application/pdf with a text placeholder body so the UI can
    still trigger a download flow.
    """
    body = (
        '%PDF-1.4\n%placeholder\n'
        + text
        + '\n%%EOF\n'
    ).encode('utf-8')
    response = HttpResponse(body, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _ts_suffix():
    return datetime.now(_tz.utc).strftime('%Y%m%d-%H%M%S')


# ────────────────────────── Sales export ───────────────────────────────────

def export_sales(payload: dict, fmt: str):
    fmt = (fmt or 'csv').lower()
    base = f'sales-{_ts_suffix()}'
    if fmt == 'csv':
        rows = [
            ['Metric', 'Value'],
            ['Revenue', payload['totals']['revenue']],
            ['Orders', payload['totals']['orders']],
            ['Average ticket', payload['totals']['average_ticket']],
            ['Previous revenue', payload['comparison']['previous_revenue']],
        ]
        return _streaming_csv(rows[1:], rows[0], f'{base}.csv')
    if fmt == 'pdf':
        text = (
            f"Sales report\n"
            f"Revenue: {payload['totals']['revenue']}\n"
            f"Orders: {payload['totals']['orders']}\n"
        )
        return _placeholder_pdf(text, f'{base}.pdf')
    return None


def export_top_sellers(payload: dict, fmt: str):
    fmt = (fmt or 'csv').lower()
    base = f'top-sellers-{_ts_suffix()}'
    if fmt == 'csv':
        rows = [(r['product_id'], r['product_name'], r['sku'],
                 r['units_sold'], r['revenue'])
                for r in payload['results']]
        return _streaming_csv(
            rows, ['product_id', 'product_name', 'sku', 'units_sold', 'revenue'],
            f'{base}.csv',
        )
    if fmt == 'pdf':
        lines = [f"{r['product_name']} ({r['sku']}): {r['units_sold']}"
                 for r in payload['results']]
        return _placeholder_pdf('Top sellers\n' + '\n'.join(lines), f'{base}.pdf')
    return None


def export_customers_rfm(payload: dict, fmt: str):
    fmt = (fmt or 'csv').lower()
    base = f'customers-rfm-{_ts_suffix()}'
    if fmt == 'csv':
        rows = [(r['user_id'], r['email'], r['recency_days'],
                 r['frequency'], r['monetary'], r['segment'])
                for r in payload['results']]
        return _streaming_csv(
            rows, ['user_id', 'email', 'recency_days',
                   'frequency', 'monetary', 'segment'],
            f'{base}.csv',
        )
    if fmt == 'pdf':
        lines = [f"{r['email']}: {r['segment']} (M={r['monetary']})"
                 for r in payload['results']]
        return _placeholder_pdf('Customers RFM\n' + '\n'.join(lines),
                                f'{base}.pdf')
    return None


def export_dashboard(payload: dict, fmt: str):
    fmt = (fmt or 'csv').lower()
    base = f'dashboard-{_ts_suffix()}'
    if fmt == 'csv':
        rows = [
            ('today_revenue', payload['today']['revenue']),
            ('today_orders', payload['today']['orders']),
            ('open_tickets', payload['open_tickets']),
            ('low_stock_alerts', payload['low_stock_alerts']),
        ]
        return _streaming_csv(rows, ['metric', 'value'], f'{base}.csv')
    if fmt == 'pdf':
        text = (
            f"Dashboard\nToday revenue: {payload['today']['revenue']}\n"
            f"Today orders: {payload['today']['orders']}\n"
            f"Open tickets: {payload['open_tickets']}\n"
        )
        return _placeholder_pdf(text, f'{base}.pdf')
    return None


EXPORTERS = {
    'sales': export_sales,
    'top-sellers': export_top_sellers,
    'customers-rfm': export_customers_rfm,
    'dashboard': export_dashboard,
}
