r"""``digest.digest`` extendido por ``account`` — el KPI de ingresos.

Adaptación de ``addons/account/models/digest.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 39 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Porte — 4 de 4 símbolos, 0 bloqueados
======================================

(4 = 2 métodos + 2 campos.) Los dos métodos estaban **bloqueados** hasta la
tarea #158, que portó ``_compute_kpis_actions`` y ``compute_kpi_value`` en
la base (``addons/digest/models/digest.py``); este pase (tarea #279) los
desbloquea y reescribe la instalación con ``extend_model`` como ``crm`` y
``hr_recruitment``.

.. list-table::
   :header-rows: 1
   :widths: 40 15 45

   * - Símbolo
     - Estado
     - Nota
   * - ``kpi_account_total_revenue`` (``:11``)
     - portado
     - columna ``Boolean`` (migración ``digest/0002``)
   * - ``kpi_account_total_revenue_value`` (``:12``)
     - portado
     - ``compute`` sin ``store`` → campo no persistido; lo sirve su
       ``_compute_…_value`` vía ``compute_kpi_value``
   * - ``_compute_kpi_account_total_revenue_value`` (``:14-27``)
     - portado
     - suma de ``balance`` de líneas publicadas de cuentas ``income``, negada
   * - ``_compute_kpis_actions`` (``:29-32``)
     - portado
     - ``overrides=`` (:mod:`orm.method_chain`) sobre el método base

Qué es
======

``digest.digest`` es el resumen periódico por correo (``addons/digest``).
Cada KPI que un addon suma al digest declara un booleano (¿se muestra?), un
campo monetario ``*_value`` computado, y opcionalmente una entrada en el
diccionario de acciones que ``_compute_kpis_actions`` arma. ``account`` suma
el ingreso total del período: la suma de ``balance`` de las líneas de
asientos **publicados** cuya cuenta es de grupo interno ``'income'``, en
negativo (una cuenta de ingreso tiene saldo natural acreedor, negativo en la
convención de signo de este ORM — igual que la referencia).

Divergencias declaradas — de forma, no de alcance
=================================================

- **``_compute_kpi_account_total_revenue_value(self, start, end)`` recibe la
  ventana por parámetro y DEVUELVE el valor.** La fuente la obtiene de
  ``self._get_kpi_compute_parameters()`` y escribe ``record.<campo>`` en un
  bucle sobre ``self``. Es el contrato que ``compute_kpi_value``
  (``addons/digest/models/digest.py``) fija para todos los KPIs de este
  árbol — el mismo que ``crm`` y ``hr_recruitment`` ya cumplen — y por eso
  el agregado se hace para **una** compañía (la del digest, o la actual) en
  vez de agruparse por ``company_id`` para N registros.
- **La ventana es ``date > start`` y ``date <= end``**, verbatim de la fuente
  (``:22-23``): no se normaliza al ``>= / <`` de
  ``_calculate_company_based_kpi``, porque ése es otro método con otro
  dominio.
- **``parent_state = 'posted'`` se expresa como ``move__state``.** Este
  árbol no materializa ``parent_state`` en la línea; el estado vive en el
  asiento y se atraviesa la FK.
- **``_compute_kpis_actions`` no resuelve ``?menu_id=<id>``.** La fuente
  concatena el id de ``account.menu_finance`` porque el correo enlaza al
  cliente web de Odoo, que resuelve el menú al navegar. Este árbol no tiene
  ese cliente: el valor es el xml_id **sin resolver**, la misma forma que
  ``crm`` y ``hr_recruitment`` ya usan para sus acciones.
- **La guarda de grupo levanta ``AccessError`` igual que la fuente**, con el
  mismo identificador externo y el mismo mensaje. Si
  ``account.group_account_invoice`` no está sembrado, ``has_group`` devuelve
  falso y la guarda niega — fail-closed, el desenlace correcto de un permiso
  que no se puede afirmar.

``has_group`` — sí existe, y con la forma correcta
===================================================

``ResUsers.has_group(group_ext_id)`` (``src/addons/base/models/res_users.py``)
es un método de instancia sobre el usuario — misma firma que
``self.env.user.has_group(...)`` de la referencia. Se porta verbatim.
"""
import fields
from django.db.models import Sum

from addons.account.models.account_move_line import AccountMoveLine
from exceptions import AccessError
from orm.environments import get_current_company, get_current_user
from orm.model_classes import extend_model
from tools.translate import _

#: El identificador externo que la fuente consulta, verbatim (``:15``).
GROUP_ACCOUNT_INVOICE = 'account.group_account_invoice'

#: El xml_id que la fuente concatena con ``?menu_id=...`` — aquí sin
#: resolver (ver la divergencia declarada arriba).
ACTION_OUT_INVOICE = 'account.action_move_out_invoice_type'


def _assert_invoicing_user():
    """≙ el ``if not self.env.user.has_group(...): raise AccessError``
    (``:15-16``). Mensaje verbatim de la fuente."""
    user = get_current_user()
    if not (user is not None and user.has_group(GROUP_ACCOUNT_INVOICE)):
        raise AccessError(
            _("Do not have access, skip this data for user's digest email"))


def _compute_kpi_account_total_revenue_value(self, start, end):
    """≙ ``_compute_kpi_account_total_revenue_value`` (``:14-27``).

    Suma de ``balance`` de las líneas de asientos **publicados** con cuenta
    de grupo ``'income'`` en la ventana ``(start, end]``, acotada a la
    compañía del digest (o a la actual si el digest no fija una), y negada:
    la fuente invierte el signo porque una cuenta de ingreso tiene saldo
    natural acreedor.

    ``AccountMoveLine`` lleva ``company_id`` propio (materializado del
    asiento en ``save()``, como el ``related store=True`` de la fuente);
    ``date`` y ``state`` viven en el asiento y se atraviesa ``move``.
    """
    _assert_invoicing_user()
    company = self.company_id or get_current_company()
    companies = [company.pk] if company is not None else []
    total = (
        AccountMoveLine.objects
        .filter(
            company_id__in=companies,
            move__date__gt=start,
            move__date__lte=end,
            account__internal_group='income',
            move__state='posted',
        )
        .aggregate(total=Sum('balance'))['total']
    )
    return -(total or 0)


def _compute_kpis_actions(self, previous, company, user):
    """≙ ``_compute_kpis_actions`` de ``account`` (``:29-32``).

    Encadena con ``previous`` —el ``_compute_kpis_actions`` que ya esté
    instalado (la base, o el de otro addon que se colgó antes)— y añade la
    clave de este addon: el xml_id de la acción de facturas de cliente, sin
    resolver (ver la divergencia declarada en el docstring del módulo).
    """
    res = previous(company, user)
    res['kpi_account_total_revenue'] = ACTION_OUT_INVOICE
    return res


def apply_account_extensions():
    """≙ ``_inherit = 'digest.digest'`` de ``account``.

    Cuelga los dos campos, el compute y la acción. La llama
    ``AccountConfig.ready()``. ``_compute_kpis_actions`` va por
    ``overrides=`` (:func:`orm.method_chain.wrap_method`): necesita el
    diccionario que la implementación previa ya devolvió, para mutarlo. Un
    ``if not hasattr: setattr`` —la forma anterior de este archivo— no
    instala nada cuando la base ya declara el método, que es exactamente
    el caso desde la tarea #158: la clave de ``account`` desaparecía del
    correo en silencio.
    """
    extend_model(
        'digest', 'DigestDigest',
        campos={
            'kpi_account_total_revenue': fields.Boolean(
                default=False, verbose_name='Ingresos',
                help_text='Muestra el KPI de ingreso total del período en '
                          'el digest (Odoo kpi_account_total_revenue).',
            ),
            'kpi_account_total_revenue_value': fields.Monetary(
                store=False, null=True, blank=True,
                verbose_name='Ingreso total del período (valor)',
                help_text='Odoo kpi_account_total_revenue_value — compute '
                          'sin store; lo sirve '
                          '_compute_kpi_account_total_revenue_value.',
            ),
        },
        metodos={
            '_compute_kpi_account_total_revenue_value':
                _compute_kpi_account_total_revenue_value,
        },
        overrides={
            '_compute_kpis_actions': _compute_kpis_actions,
        },
    )
