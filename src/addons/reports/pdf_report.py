"""
PDF report-table generation — UC-RPT-04 / UC-REP-05.

Builds the JSON descriptor for a tabular report and invokes the compiled
libharu helper (``tools/pdf/pdf_report``) via subprocess, returning the PDF
bytes. Sibling of ``addons.payments.pdf_receipt``; see ADR-017
(adr-017-libreria-pdf-libharu): the native helper is run out of process so a
libharu fault cannot take down the mod_wsgi worker.
"""
import json
import logging
import subprocess
from pathlib import Path

from django.conf import settings

logger = logging.getLogger('apps')

# The helper binary is built by the server provisioner next to its source
# (see tools/pdf/Makefile). BASE_DIR == practicayoruba/ (config/settings/base.py).
HELPER_PATH = Path(settings.BASE_DIR) / 'tools' / 'pdf' / 'pdf_report'

# Hard ceiling so a hung helper cannot block the WSGI worker.
HELPER_TIMEOUT_SECONDS = 20


class PdfGenerationError(Exception):
    """Raised when the libharu helper fails to produce a valid PDF."""


def build_report_payload(title, columns, rows, subtitle='', generated_at=''):
    """
    Assemble the JSON descriptor consumed by the C helper. All cell values
    are coerced to strings to avoid float/Decimal drift; the helper only
    lays them out.
    """
    return {
        'title': str(title),
        'subtitle': str(subtitle or ''),
        'generated_at': str(generated_at or ''),
        'columns': [str(c) for c in columns],
        'rows': [[('' if v is None else str(v)) for v in row] for row in rows],
    }


def render_report_pdf(payload: dict) -> bytes:
    """
    Invoke the libharu helper with the JSON payload on stdin and return the
    PDF bytes from stdout. Raises PdfGenerationError on any failure.
    """
    if not HELPER_PATH.exists():
        logger.error('PDF report helper binary missing at %s', HELPER_PATH)
        raise PdfGenerationError(
            f'PDF report helper not built at {HELPER_PATH}. Run '
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
        logger.error('PDF report helper timed out after %ss',
                     HELPER_TIMEOUT_SECONDS)
        raise PdfGenerationError('PDF report helper timed out') from exc
    except OSError as exc:
        logger.error('PDF report helper failed to execute: %s', exc)
        raise PdfGenerationError(f'PDF report helper exec failed: {exc}') from exc

    if proc.returncode != 0:
        logger.error(
            'PDF report helper exit=%s stderr=%s',
            proc.returncode, proc.stderr.decode('utf-8', 'replace')[:500],
        )
        raise PdfGenerationError(f'PDF report helper exited {proc.returncode}')

    pdf_bytes = proc.stdout
    if not pdf_bytes or not pdf_bytes.startswith(b'%PDF'):
        logger.error('PDF report helper produced no valid PDF (len=%d)',
                     len(pdf_bytes))
        raise PdfGenerationError('PDF report helper produced invalid output')

    return pdf_bytes
