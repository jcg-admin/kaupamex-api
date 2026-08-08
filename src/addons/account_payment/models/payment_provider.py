"""``payment.provider`` (≙ ``PaymentGateway`` aquí) — lo que ``account_payment``
le cuelga (≙ ``_inherit``).

Adaptación de ``odoo19c: account_payment/models/payment_provider.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3, 148
líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

10 símbolos en la referencia (1 campo + 9 métodos). Portados 2, no
portados 8 — la mayoría depende de infraestructura contable (plantillas de
plan de cuentas, auto-alta de líneas de método de pago por compañía) que no
existe en este núcleo.

Portado
========

===================================  ==================================================
Símbolo de la referencia              Aquí
===================================  ==================================================
``journal_id``                        propiedad ``journal`` (get/set) vía
                                       ``PaymentGatewayJournal`` — **sin** el
                                       ``_compute_journal_id``/``_inverse_journal_id``
                                       de la referencia (ver ``models/links.py``,
                                       docstring de ``PaymentGatewayJournal``):
                                       asignación directa, no derivada.
``_get_provider_payment_method``      método homónimo (búsqueda trivial por ``code``)
===================================  ==================================================

No portado (declarado, no improvisado)
=========================================

- **``_ensure_payment_method_line`` / ``_compute_journal_id`` /
  ``_inverse_journal_id``** — auto-crean/actualizan una
  ``account.payment.method.line`` elegible cada vez que cambia el diario o
  el estado del proveedor, buscando líneas existentes por compañía y
  código. Depende de ``account.payment.method.line._check_company_domain``
  (multicompañía jerárquica) y de un patrón de búsqueda/creación que este
  núcleo no modela — el enlace ``PaymentGatewayJournal`` de aquí es
  deliberadamente más simple (ver su docstring).
- **``_get_payment_method_outstanding_account_id``** — resuelve la cuenta
  puente vía ``account.chart.template.ref(...)`` (una referencia por
  identificador externo a una cuenta del plan) con fallback a
  ``company.transfer_account_id``. ``api: account/models/chart_template.py``
  existe pero no expone un ``.ref()`` por identificador externo genérico
  sobre cuentas de plantilla (medido: es un cargador de 1537 líneas
  orientado a poblar el plan, no un resolver de referencias por xmlid). El
  fallback (``company.transfer_account``) SÍ existe
  (``api: account/models/res_company.py``, campo ``transfer_account``) pero
  portar sólo el fallback sin el camino principal cambiaría el
  comportamiento observable (siempre usaría la cuenta de transferencia
  genérica, nunca la cuenta específica del método de pago) — se declara en
  vez de fabricar una aproximación silenciosa.
- **``_setup_provider`` / ``_setup_payment_method`` / ``_remove_provider``**
  — hooks de instalación/desinstalación de módulo Odoo (``_setup_provider``
  se dispara al activar un addon de proveedor de pago vía
  ``env['ir.module.module']``). Este stack no tiene ciclo de vida de
  instalación de addons en runtime — los addons se activan por
  ``INSTALLED_APPS``, fuera del alcance de este agente.
- **``_check_existing_payment``** — cuenta ``account.payment`` por
  ``payment_method_id``. ``api: account/models/account_payment.py`` (9
  campos, medido) no declara ``payment_method``/``payment_method_line``:
  el pago no navega a un método de pago en este núcleo (mismo hueco que
  documenta ``models/account_payment.py``, sección "No portado").
"""
from addons.account.models.account_payment_method import AccountPaymentMethod
from addons.account_payment.models.links import PaymentGatewayJournal
from addons.payment.models import PaymentGateway


def _get_link(gateway):
    """El enlace de ``gateway``, o ``None`` si nunca se creó uno.

    Guard de ``pk`` por la misma razón que en ``account_payment_method_line``
    y ``account_payment``: una pasarela sin insertar no puede tener satélite,
    y filtrar por una instancia sin ``pk`` aborta con ``ValueError: Model
    instances passed to related filters must be saved.``
    """
    if gateway.pk is None:
        return None
    return PaymentGatewayJournal.objects.filter(gateway=gateway).first()


def _get_or_create_link(gateway):
    link, _created = PaymentGatewayJournal.objects.get_or_create(gateway=gateway)
    return link


def _get_journal(self):
    link = _get_link(self)
    return link.journal if link is not None else None


def _set_journal(self, value):
    link = _get_or_create_link(self)
    link.journal = value
    link.save(update_fields=['journal'])


def _get_provider_payment_method(code):
    """≙ ``odoo19c: account_payment/models/payment_provider.py:113-115``
    (``@api.model``, sin ``self`` — es una búsqueda de catálogo, no depende
    de la instancia del proveedor)."""
    return AccountPaymentMethod.objects.filter(code=code).first()


def apply_account_payment_extensions():
    """≙ ``_inherit = 'payment.provider'`` de ``account_payment`` (sobre
    ``PaymentGateway``, ver ``models/links.py``).

    Se llama desde ``AccountPaymentConfig.ready()``.
    """
    if not hasattr(PaymentGateway, 'journal'):
        setattr(PaymentGateway, 'journal', property(_get_journal, _set_journal))
    if not hasattr(PaymentGateway, '_get_provider_payment_method'):
        PaymentGateway._get_provider_payment_method = staticmethod(
            _get_provider_payment_method)
