"""Cada orden por ``created_at`` sigue el contrato que su fuente declara.

Las fechas de ``TimeStampedModel`` son la hora de la transacción
(``cr.now()``, ``odoo19c@abe4040ec1: odoo/orm/models.py:4394-4396`` y
``:4801-4805``; ``odoo/sql_db.py:271-278``): las filas escritas en una misma
transacción comparten ``created_at``. Qué hace cada consulta con ese empate
no se decide en bloque: se deriva, consulta por consulta, de su fuente.

Tres clases, y cada consulta encontrada tiene que estar en una:

``reference-id``
    El modelo de la referencia desempata su ``_order`` por ``id`` en el
    mismo sentido (``'..., id desc'``). El puerto desempata igual.
``reference-untied``
    La referencia ordena por la fecha **sin** desempate; el puerto conserva
    esa forma literal y no inventa uno.
``consumer``
    Sin contraparte 1:1 en la referencia: el orden es contrato propio del
    Consumer, y el desempate por ``id`` lo hace determinista para la
    paginación de la interfaz.

*Métrica:* llamadas ``order_by`` cuyos argumentos literales incluyen
``created_at`` o ``-created_at``, en ``src/`` y ``addons/`` sin pruebas ni
migraciones, identificadas por archivo y función contenedora.
*Ciega a:* órdenes construidos con variables, ``Meta.ordering`` y
``F('created_at')``; y al orden **principal** de cada consulta, que en varias
diverge del ``_order`` de la referencia y es otra obligación.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
DATE = {'created_at', '-created_at'}
TIE = {'id', '-id', 'pk', '-pk'}

REF_C = 'odoo19c@abe4040ec1'
REF_E = 'odoo19e@abe4040ec1'

# Clave: ``ruta::función``. Valor: (clase, fuente que la decide).
REGISTRY = {
    'addons/crm/controllers/main.py::AdminContactMessageListView.get':
        ('reference-id', f"{REF_C}: crm/models/crm_lead.py:87 "
                         "'priority desc, id desc'"),
    'addons/delivery/controllers/main.py::ShipmentGuideListCreateView.get':
        ('consumer', 'guía de envío propia; stock.picking no es 1:1'),
    'addons/helpdesk/controllers/main.py::_annotate_first_response':
        ('consumer', 'primera respuesta: cronología propia del Consumer'),
    'addons/helpdesk/controllers/main.py::SupportTicketListCreateView.get':
        ('reference-id', f"{REF_E}: helpdesk/models/helpdesk_ticket.py:27 "
                         "'priority desc, id desc'"),
    'addons/helpdesk/controllers/main.py::SupportTicketListCreateView.post':
        ('reference-id', f"{REF_E}: helpdesk/models/helpdesk_ticket.py:27"),
    'addons/helpdesk/controllers/main.py::AdminSupportTicketListView.get':
        ('consumer', 'cola FIFO de soporte, contrato propio'),
    'addons/helpdesk/controllers/main.py::'
    'AdminSupportTicketExportCSVView.get':
        ('consumer', 'exportación FIFO de soporte, contrato propio'),
    'addons/helpdesk/controllers/serializers.py::'
    'SupportTicketDetailSerializer.get_replies':
        ('consumer', 'hilo cronológico ascendente; el chatter de la '
                     "referencia es mail.message 'id desc'"),
    'addons/loyalty/controllers/admin_main.py::VoucherViewSet':
        ('consumer', f'voucher sin contraparte 1:1 en {REF_C}: loyalty'),
    'addons/mail/controllers/main.py::NotificationListView.get':
        ('reference-id', f"{REF_C}: mail/models/mail_message.py:74 'id desc'"),
    'addons/mass_mailing/controllers/subscribers.py::'
    'AdminSubscriberExportCSVView.get':
        ('consumer', 'exportación de suscriptores, contrato propio'),
    'addons/mass_mailing/services.py::list_subscriptions':
        ('consumer', 'listado de suscripciones, contrato propio'),
    'addons/payment/controllers/portal.py::payment_status':
        ('reference-id', f"{REF_C}: payment/models/payment_transaction.py:27 "
                         "'id desc'"),
    'addons/payment/controllers/portal.py::payment_history':
        ('reference-id', f"{REF_C}: payment/models/payment_transaction.py:27"),
    'addons/rating/controllers/main.py::ProductReviewsView.get':
        ('reference-id', f"{REF_C}: rating/models/rating.py:15 "
                         "'write_date desc, id desc'"),
    'addons/rating/controllers/main.py::ReviewAdminListView.get':
        ('consumer', 'cola FIFO de moderación, contrato propio'),
    'addons/sale/controllers/main.py::_own_orders':
        ('reference-id', f"{REF_C}: sale/models/sale_order.py:38 "
                         "'date_order desc, id desc'"),
    'addons/sale/services.py::get_or_create_draft_order':
        ('consumer', 'carrito en borrador, contrato propio'),
    'addons/sale_management/controllers/admin_views.py::_admin_orders':
        ('reference-id', f"{REF_C}: sale/models/sale_order.py:38"),
    'addons/sale_subscription/controllers/views.py::CompanyViewSet.invoices':
        ('consumer', 'factura de suscripción L0, contrato propio'),
    'addons/stock/models/stock_quant.py::StockQuant._onchange_product_id':
        ('reference-untied', f"{REF_C}: stock/models/stock_quant.py:985-987 "
                             "order='create_date desc', limit=1"),
    'addons/website/controllers/search_history.py::'
    'SearchHistoryViewSet.get_queryset':
        ('consumer', 'historial de búsqueda propio; website.track no es 1:1'),
}


def _orderings():
    for base in ('src', 'addons'):
        for path in sorted((ROOT / base).rglob('*.py')):
            if {'tests', 'migrations'} & set(path.parts):
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            yield from _visit(tree, [], path.relative_to(ROOT))


def _visit(node, stack, path):
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            yield from _visit(child, stack + [child.name], path)
            continue
        if (isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == 'order_by'):
            keys = [a.value for a in child.args
                    if isinstance(a, ast.Constant)
                    and isinstance(a.value, str)]
            if DATE & set(keys):
                yield f"{path}::{'.'.join(stack)}", keys
        yield from _visit(child, stack, path)


def _conforms(cls, keys):
    tie = [key for key in keys if key in TIE]
    if cls == 'reference-untied':
        return not tie
    date = next(key for key in keys if key in DATE)
    return bool(tie) and tie[-1].startswith('-') == date.startswith('-')


def test_the_scan_sees_the_orderings():
    """Control: el recorrido encuentra órdenes por ``created_at``; un cero
    aquí sería un instrumento ciego, no un árbol sano."""
    assert len(list(_orderings())) >= 20


def test_every_ordering_is_classified_against_its_source():
    unclassified = sorted(
        {where for where, __ in _orderings()} - set(REGISTRY))
    assert unclassified == []


def test_the_registry_has_no_stale_entries():
    assert sorted(set(REGISTRY) - {w for w, __ in _orderings()}) == []


def test_every_ordering_follows_its_class():
    wrong = [(where, keys) for where, keys in _orderings()
             if not _conforms(REGISTRY[where][0], keys)]
    assert wrong == []
