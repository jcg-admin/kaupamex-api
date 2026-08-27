"""``portal`` — "Mis facturas" del portal de clientes.

Adaptación de Odoo ``addons/account/controllers/portal.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

La referencia extiende ``portal.CustomerPortal``; este árbol porta ese
controller como **funciones sueltas** en
``addons/portal/controllers/portal.py`` (``document_check_access``,
``pager``, ``get_records_pager`` — ver su docstring), no como clase. Por
eso ``PortalAccount`` aquí no hereda: consume esas funciones y declara
localmente lo mínimo del padre que usa (``_items_per_page = 80``, verbatim
de ``odoo19c: portal/controllers/portal.py:144``). El cableado de URLs
(``/my/invoices`` → vista DRF con ``IsAuthenticated`` + capacidad, patrón
``portal/controllers/main.py``) es del orquestador — ``urls.py`` queda
fuera de este pase por directiva.

Doce defs de la referencia — el desglose
=========================================

===================================  ======================================
Símbolo de la referencia              Qué pasa aquí
===================================  ======================================
``_prepare_home_portal_values``       PORTADO (parcial declarado: sin el
                                       ``super()`` del padre no-clase; los
                                       tres contadores se portan; el check
                                       ``has_access('read')`` ≙ la capa DRF)
``_get_overdue_invoice_count``        PORTADO
``_invoice_get_page_view_values``     PORTADO (parcial declarado:
                                       ``_get_invoice_portal_extra_values``
                                       de ``account.move`` no está portado
                                       — se devuelven los valores base;
                                       ``custom_amount`` se conserva)
``_get_invoices_domain``              PORTADO — como ``Q`` de Django
``_get_overdue_invoices_domain``      PORTADO (parcial declarado, abajo)
``_get_account_searchbar_sortings``   PORTADO (``order`` en vocabulario
                                       Django: ``-date`` ≙ ``date desc``)
``_get_account_searchbar_filters``    PORTADO
``portal_my_invoices``                PORTADO (la sesión
                                       ``my_invoices_history`` y el
                                       ``request.render`` QWeb son del
                                       cliente Odoo — devuelve el dict de
                                       valores con el pager resuelto)
``_prepare_my_invoices_values``       PORTADO
``portal_my_invoice_detail``          PORTADO (parcial declarado, abajo)
``portal_my_journal_unsubscribe``     NO — bloqueado por TRES piezas:
                                       ``verify_hash_signed`` (tokens
                                       firmados de ``odoo.tools.misc``, no
                                       portado), ``journal.incoming_
                                       einvoice_notification_email`` +
                                       ``_unsubscribe_invoice_notification_
                                       email`` (la suscripción de correo
                                       e-invoice del diario, no portada) y
                                       el render QWeb de
                                       ``portal_my_journal_mail_
                                       notifications``.
``_prepare_my_account_rendering_values``  NO — su super es el padre
                                       no-clase y su aporte propio lee
                                       ``res.partner.invoice_edi_format``
                                       (selection de partner no portado).
===================================  ======================================

Divergencias declaradas transversales:

- ``invoice_date`` / ``invoice_date_due`` / ``create_date`` no existen en
  el puerto de ``account.move`` — ordenar/filtrar por vencimiento usa
  ``date`` (la fecha contable), y el filtro por rango de creación usa
  ``date``. Al aterrizar esos campos, los strings de orden de
  ``_get_account_searchbar_sortings`` se re-mapean sin tocar firmas.
- ``partner_id`` del asiento: el puerto declara ``partner`` →
  ``AUTH_USER_MODEL`` (res.partner ≡ party), así que "mis facturas" filtra
  por ``partner=request.user``.
- ``payment_state`` sí está portado (los 7 valores) — el filtro de vencidas
  lo usa verbatim.
- ``portal_my_invoice_detail``: la rama de descarga PDF/zip está bloqueada
  por ``_get_invoice_legal_documents_all`` (misma pieza que declara
  ``download_docs.py``); la rama de render de reporte
  (``_show_report``/``invoice_pdf_report_id``/plantilla por partner/RTL)
  es del motor de reportes QWeb, no portado. Se porta la rama de valores de
  página con el control de acceso real (``document_check_access`` requiere
  ``access_token`` en el modelo — ``account.move`` aún no incorpora
  ``portal.mixin``, así que el acceso por token queda bloqueado por ese
  mixin y el acceso normal es "el asiento es del usuario").
"""
from collections import OrderedDict

from django.db.models import Q
from django.utils import timezone

from addons.account.models.account_move import AccountMove
from addons.portal.controllers.portal import pager as portal_pager
from exceptions import AccessDenied, MissingError
from tools.translate import _


class PortalAccount:
    """≙ ``PortalAccount(CustomerPortal)`` — sin el padre (ver el docstring
    del módulo)."""

    #: ≙ ``CustomerPortal._items_per_page`` (verbatim de la referencia).
    _items_per_page = 80

    def _prepare_home_portal_values(self, request, counters):
        """≙ ``_prepare_home_portal_values`` — los contadores del home del
        portal (sin ``super()``: el padre aquí no es clase)."""
        values = {}
        if 'overdue_invoice_count' in counters:
            values['overdue_invoice_count'] = \
                self._get_overdue_invoice_count(request)
        if 'invoice_count' in counters:
            values['invoice_count'] = AccountMove.objects.filter(
                self._get_invoices_domain('out'),
                partner=request.user,
            ).count()
        if 'bill_count' in counters:
            values['bill_count'] = AccountMove.objects.filter(
                self._get_invoices_domain('in'),
                partner=request.user,
            ).count()
        return values

    # ------------------------------------------------------------
    # My Invoices
    # ------------------------------------------------------------

    def _get_overdue_invoice_count(self, request):
        """≙ ``_get_overdue_invoice_count``."""
        return AccountMove.objects.filter(
            self._get_overdue_invoices_domain(request)).count()

    def _invoice_get_page_view_values(self, invoice, access_token, **kwargs):
        """≙ ``_invoice_get_page_view_values`` (parcial declarado — sin
        ``_get_invoice_portal_extra_values``, ver la tabla del módulo)."""
        custom_amount = None
        if kwargs.get('amount'):
            custom_amount = float(kwargs['amount'])
        return {
            'page_name': 'invoice',
            'invoice': invoice,
            'custom_amount': custom_amount,
        }

    def _get_invoices_domain(self, m_type=None):
        """≙ ``_get_invoices_domain`` — como ``Q``: publicadas o pagadas
        (nunca borrador/cancelada), del sentido pedido."""
        if m_type in ['in', 'out']:
            move_type = [m_type + move
                         for move in ('_invoice', '_refund', '_receipt')]
        else:
            move_type = ('out_invoice', 'out_refund', 'in_invoice',
                         'in_refund', 'out_receipt', 'in_receipt')
        return (~Q(state__in=('cancel', 'draft'))
                & Q(move_type__in=move_type))

    def _get_overdue_invoices_domain(self, request, partner_id=None):
        """≙ ``_get_overdue_invoices_domain`` (parcial declarado — el
        vencimiento usa ``date``: ``invoice_date_due`` no está portado;
        ver la tabla del módulo)."""
        return (
            ~Q(state__in=('cancel', 'draft'))
            & Q(move_type__in=('out_invoice', 'out_receipt'))
            & ~Q(payment_state__in=('in_payment', 'paid', 'reversed',
                                    'blocked', 'invoicing_legacy'))
            & Q(date__lt=timezone.now().date())
            & Q(partner_id=partner_id or request.user.pk)
        )

    def _get_account_searchbar_sortings(self):
        """≙ ``_get_account_searchbar_sortings`` — ``order`` en vocabulario
        Django (``invoice_date``/``invoice_date_due`` → ``date``, campos no
        portados; ver la tabla del módulo)."""
        return {
            'date': {'label': _('Date'), 'order': '-date'},
            'duedate': {'label': _('Due Date'), 'order': '-date'},
            'name': {'label': _('Reference'), 'order': '-name'},
            'state': {'label': _('Status'), 'order': 'payment_state'},
        }

    def _get_account_searchbar_filters(self, request):
        """≙ ``_get_account_searchbar_filters`` — como ``Q``."""
        return {
            'all': {'label': _('All'), 'domain': Q()},
            'overdue_invoices': {
                'label': _('Overdue invoices'),
                'domain': self._get_overdue_invoices_domain(request),
            },
            'invoices': {
                'label': _('Invoices'),
                'domain': Q(move_type__in=('out_invoice', 'out_refund',
                                           'out_receipt')),
            },
            'bills': {
                'label': _('Bills'),
                'domain': Q(move_type__in=('in_invoice', 'in_refund',
                                           'in_receipt')),
            },
        }

    def portal_my_invoices(self, request, page=1, date_begin=None,
                            date_end=None, sortby=None, filterby=None, **kw):
        """≙ ``GET /my/invoices`` — la lista paginada. La sesión
        ``my_invoices_history`` y el render QWeb son del cliente Odoo (ver
        la tabla del módulo); devuelve el dict de valores con el pager
        resuelto y las facturas de la página."""
        values = self._prepare_my_invoices_values(
            request, page, date_begin, date_end, sortby, filterby)
        pager = portal_pager(**values['pager'])
        invoices = values['invoices'](pager['offset'])
        values.update({
            'invoices': invoices,
            'pager': pager,
        })
        return values

    def _prepare_my_invoices_values(self, request, page, date_begin,
                                     date_end, sortby, filterby,
                                     domain=None, url="/my/invoices"):
        """≙ ``_prepare_my_invoices_values`` — el domain compuesto, el
        orden elegido y el pager con lambda de página (misma forma que la
        referencia: ``values['invoices'](offset)``)."""
        domain = (domain or Q()) & self._get_invoices_domain() \
            & Q(partner=request.user)

        searchbar_sortings = self._get_account_searchbar_sortings()
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        searchbar_filters = self._get_account_searchbar_filters(request)
        if not filterby:
            filterby = 'all'
        domain &= searchbar_filters[filterby]['domain']

        if date_begin and date_end:
            # ``create_date`` no está portado — el rango filtra por la
            # fecha contable (divergencia declarada en el módulo).
            domain &= Q(date__gt=date_begin) & Q(date__lte=date_end)

        queryset = AccountMove.objects.filter(domain).order_by(order)
        total = queryset.count()
        return {
            'date': date_begin,
            # ≙ la lambda de la referencia: el recordset de la página se
            # resuelve cuando el pager ya fijó el offset.
            'invoices': lambda pager_offset: list(
                queryset[pager_offset:pager_offset + self._items_per_page]),
            'page_name': 'invoice',
            'pager': {
                'url': url,
                'url_args': {'date_begin': date_begin, 'date_end': date_end,
                             'sortby': sortby, 'filterby': filterby},
                'total': total,
                'page': page,
                'step': self._items_per_page,
            },
            'default_url': url,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': OrderedDict(
                sorted(searchbar_filters.items())),
            'filterby': filterby,
            'overdue_invoice_count': self._get_overdue_invoice_count(request),
        }

    def portal_my_invoice_detail(self, request, invoice_id,
                                  access_token=None, report_type=None,
                                  download=False, **kw):
        """≙ ``GET /my/invoices/<id>`` (parcial declarado — las ramas de
        descarga/render de reporte están bloqueadas; ver la tabla del
        módulo). El control de acceso: el asiento es del usuario; el acceso
        por ``access_token`` queda bloqueado por ``portal.mixin`` sobre
        ``account.move`` (el campo no existe ahí todavía)."""
        try:
            invoice = AccountMove.objects.get(pk=invoice_id)
        except AccountMove.DoesNotExist:
            raise MissingError(_('This document does not exist.'))
        if invoice.partner_id != request.user.pk:
            # ≙ el redirect a /my de la referencia ante AccessError.
            raise AccessDenied(
                _('You are not allowed to access this document.'))
        return self._invoice_get_page_view_values(
            invoice, access_token, **kw)
