"""``terms`` — la página pública de términos y condiciones de factura.

Adaptación de Odoo ``addons/account/controllers/terms.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

Dos símbolos de la referencia (1 función + 1 clase con 1 def) — ambos se
portan; el cableado de la URL (``/terms``, ``auth='public'``) es del
orquestador (``urls.py`` queda fuera de este pase por directiva).

Divergencias declaradas
========================

- ``request.render('account.account_terms_conditions_page', …)`` /
  ``request.render('http_routing.http_error', …)``: QWeb no es superficie
  de este árbol (SPA + DRF). ``terms_conditions`` devuelve el dict de
  contexto (``{'use_invoice_terms', 'company'}`` — las mismas claves que la
  referencia pasa al template) o ``None`` cuando la página no aplica; la
  vista DRF que lo cablee serializa eso (404 para el ``None``, que es lo
  que el ``http_error`` de la referencia comunica).
- ``company.terms_type == 'html'``: ``terms_type`` (texto plano vs página
  HTML) no está portado en ``res.company`` — **bloqueado por ese campo**.
  Mientras no exista, la condición se reduce a ``use_invoice_terms`` solo:
  la mitad del guard que sí tiene contraparte. Al aterrizar el campo, el
  ``and`` recupera su segunda mitad sin cambiar firmas.
- ``env['ir.config_parameter'].sudo().get_param(...)`` ≙
  ``SystemParameter.get_param(...)`` — mismo parámetro
  ``account.use_invoice_terms``, mismo nombre.
"""
from addons.base.models import SystemParameter
from tools.misc import str2bool


def sitemap_terms(qs, company):
    """≙ ``sitemap_terms`` — el generador que publica ``/terms`` en el
    sitemap sólo cuando los términos están activos (``terms_type`` —
    bloqueado, ver el docstring del módulo)."""
    if qs and qs.lower() not in '/terms':
        return
    use_invoice_terms = SystemParameter.get_param('account.use_invoice_terms')
    if use_invoice_terms and str2bool(str(use_invoice_terms), default=False):
        yield {'loc': '/terms'}


class TermsController:
    """≙ ``TermsController`` — la página ``/terms``. El cableado de la URL
    es del orquestador (ver el docstring del módulo)."""

    def terms_conditions(self, request, **kwargs):
        """≙ ``GET /terms`` — el contexto de la página, o ``None`` si los
        términos por página no están activos (≙ el ``http_error`` de la
        referencia)."""
        use_invoice_terms = SystemParameter.get_param(
            'account.use_invoice_terms')
        active = bool(use_invoice_terms) and str2bool(
            str(use_invoice_terms), default=False)
        if not active:
            return None
        return {
            'use_invoice_terms': use_invoice_terms,
            'company': getattr(request, 'company', None),
        }
