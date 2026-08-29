"""``res.partner`` — lo que ``sale`` le cuelga al cliente (≙ ``_inherit``).

Adaptación de ``odoo19c: addons/sale/models/res_partner.py``
(``odoo-tools@622ddc2a``, LGPL-3, 110 líneas, 7 ``def`` + 4 asignaciones de
clase). Licencia LGPL-3 → **copia + adaptación con atribución** (DEC-KX-03):
el cuerpo se adapta del fuente, no se reimplementa.

Cobertura: 4 campos + 7 métodos — **10 portados, 1 bloqueado**
==============================================================

.. list-table::
   :header-rows: 1
   :widths: 42 12 46

   * - Símbolo
     - Estado
     - Nota
   * - ``sale_order_count`` (campo, ``:11``)
     - portado
     - ``compute`` sin ``store`` → ``property``
   * - ``sale_order_ids`` (campo, ``:16``)
     - portado
     - ``One2many`` inverso → ``property``; cruza el puente usuario→partner
   * - ``sale_warn_msg`` (campo, ``:17``)
     - portado
     - ``fields.Text`` → columna real (migración en ``base``)
   * - ``_check_company_auto`` — **no aplica**
     - n/a
     - la fuente NO lo declara en este archivo; se enumera para que su
       ausencia sea medida y no supuesta
   * - ``_get_sale_order_domain_count`` (``:19``)
     - portado
     - gancho de dominio → ``Q()`` vacío
   * - ``_compute_sale_order_count`` (``:22``)
     - portado
     - ``_read_group`` + subida por ``parent_id`` → ``annotate(Count())``
   * - ``_compute_application_statistics_hook`` (``:44``)
     - portado
     - ``chain_method`` con ``combine=``, como en ``crm``
   * - ``_has_order`` (``:54``)
     - portado
     - ``search(limit=1)`` → ``.exists()``
   * - ``_can_edit_country`` (``:67``)
     - portado
     - encadena sobre la guarda de ``portal`` (ver "El eslabón de portal")
   * - ``can_edit_vat`` (``:77``)
     - portado
     - ídem, con ``child_of`` sobre la entidad comercial
   * - ``_compute_credit_to_invoice`` (``:83``)
     - **BLOQUEADO por ``res.partner.credit_to_invoice``**
     - el campo que acumula no existe aquí; ver abajo

Lo que este archivo NO cierra
=============================

**BLOQUEADO por ``res.partner.credit_to_invoice``** — el campo que este método
acumula lo declara ``account/models/partner.py`` de la fuente y aquí da **0
declaraciones** (medido: ``grep -rn 'credit_to_invoice' addons/ src/
--include=*.py`` → 0). Su segundo insumo, ``sale.order.amount_to_invoice``,
tampoco existe todavía: ``sale_order.py`` lo enumera entre sus ocho no
almacenados bloqueados. Sucesor: **#116** (cablear el aviso de límite de
crédito en ``account.move``), que es donde vive el consumidor real de la cifra.

  ``_compute_credit_to_invoice``  (``:83-110``)  el crédito ya comprometido
  por pedidos confirmados y aún no facturados, convertido a la divisa de la
  empresa.

Lo que **sí** quedó cerrado en este pase y era su gemelo:
``_get_partner_credit_warning_exclude_amount`` ya existe en
``addons/account/models/account_move.py`` — el gancho que ``sale`` reemplaza
para descontar ese mismo importe.

El puente usuario→partner: ``SaleOrder.partner`` NO es ``res.partner``
=====================================================================

La fuente declara ``sale.order.partner_id`` como ``Many2one('res.partner')``,
y por eso su ``sale_order_ids`` es un ``One2many`` directo. **Aquí no lo es**:
``SaleOrder.partner`` apunta a ``settings.AUTH_USER_MODEL``
(``sale_order.py:370-374``, ``related_name='sale_orders'``), es decir a
``res.users``. El partner se alcanza por ``ResUsers.partner``
(``src/addons/base/models/res_users.py:694``).

Consecuencia para los cinco símbolos que consultan pedidos de un cliente: el
filtro cruza el puente — ``partner__partner=<partner>``, no
``partner=<partner>``.

**Y omitir el puente falla de DOS maneras distintas, sólo una de ellas
ruidosa.** Medido saboteando el archivo y corriendo su suite:

.. list-table::
   :header-rows: 1

   * - Forma
     - Qué pasa sin el puente
     - Casos que caen
   * - ``filter(partner=<instancia>)``
     - ``ValueError: Must be "ResUsers" instance`` — Django valida el tipo
     - 2, y **con excepción**
   * - ``filter(partner_id=<pk>)`` / ``partner_id__in=[…]``
     - **nada**: compara la PK del partner contra la del usuario
     - 6, **sin excepción**

La segunda es la que obliga a declarar esto en el docstring en vez de dejarlo
al lector: el conteo sale 0 —o el de otro cliente— y nada lo delata. La suite
lo discrimina en los dos frentes (``tests/unit/sale/test_sale_res_partner.py``,
saboteo verificado y revertido).

**El eje divergente NO se corrige en este pase** — repuntar la FK a
``res.partner`` toca el modelo, su migración y todos sus consumidores, y es una
decisión de forma que excede el porte de este archivo. Sucesor: tarea **#993**.

Y una segunda diferencia del mismo eje: la fuente lee
``commercial_partner_id`` como campo; aquí ``commercial_partner`` es una
``property`` que sube por la cadena de padres
(``res_partner.py:1404``). ``can_edit_vat`` la consulta por su nombre real.

El eslabón de ``portal``: dos guardas que eran función y ahora son método
=========================================================================

La fuente escribe ``super()._can_edit_country()`` y ``super().can_edit_vat()``:
``sale`` **encadena** sobre lo que ``portal`` ya decidió. Aquí ``portal`` las
había portado como funciones de módulo (``portal/models/res_partner.py``), y
una función de módulo no admite ``super()``.

En este pase se promueven a **métodos de ``ResPartner``**, colgados por
``portal`` con ``extend_model(metodos=…)`` desde su ``ready()``; los dos
consumidores vivos (``portal/controllers/main.py``) pasan a invocar el método,
así que recorren la cadena completa en vez de quedarse con el eslabón de abajo.
Sin esa promoción ``wrap_method`` levantaría ``TypeError`` —no hay previa que
entregar— y, aun instalándose, el método de ``sale`` sería correcto y **nadie
lo llamaría**: la forma de defecto que :ref:`h-api-346` registró.

El orden está garantizado por construcción: ``LOCAL_APPS`` se deriva del grafo
de ``depends`` y sitúa ``addons.portal`` en la posición 67 y ``addons.sale`` en
la 93, así que el eslabón base está instalado cuando ``sale`` lo envuelve.

Divergencias declaradas
=======================

- **``groups='sales_team.group_sale_salesman'`` es guarda de cuerpo**, no
  metadata del campo — misma razón y mismo sucesor que en ``crm/res_partner.py``
  y en ``utm.py``: el grupo no está sembrado, ``has_group`` devuelve ``False``
  y el conteo sale 0. Sucesor: **#157**.
- **``lifetime_value`` no es de la fuente.** Es un agregado propio del L0 que
  este archivo ya declaraba; se conserva verbatim (no se borra, se transforma)
  y se marca como tal para que nadie lo busque en ``odoo19c``.
- **``_read_group`` → ``annotate``.** La fuente agrupa con su motor y luego
  sube por ``parent_id`` sumando en cada ancestro. Aquí el conteo sale de un
  ``values('partner').annotate(Count('pk'))`` y la subida es el mismo bucle
  ``while partner`` de la fuente, recorrido sobre la FK.
"""
from decimal import Decimal

from django.db.models import Count, Q, Sum

from orm.environments import get_current_user
from orm.method_chain import chain_method
from orm.model_classes import extend_model
from tools.translate import _

import fields

from addons.base.models.res_partner import ResPartner

from .sale_order import SaleOrder

#: ≙ la cabecera que la fuente declara en su clase (la extensión aquí no es clase).
_inherit = 'res.partner'

#: El identificador externo que la fuente consulta, verbatim.
GROUP_SALE_SALESMAN = 'sales_team.group_sale_salesman'

#: Los dos estados que la fuente considera "hay pedido emitido" en
#: ``_has_order`` (``:59-61``): enviado o confirmado. El borrador no cuenta.
STATES_WITH_ORDER = (SaleOrder.STATE_SENT, SaleOrder.STATE_SALE)


def _user_is_salesman():
    """¿El usuario en contexto es vendedor? ``False`` sin usuario (fail-closed).

    Misma forma que ``crm/models/res_partner.py`` — se repite el cuerpo y no
    se importa de ``crm`` porque ``sale`` no depende de ``crm``.
    """
    user = get_current_user()
    return bool(user is not None and user.has_group(GROUP_SALE_SALESMAN))


def _sale_order_ids(self):
    """≙ el campo ``sale_order_ids`` (``:16``).

    ``One2many('sale.order', 'partner_id')``. **El inverso no es directo
    aquí**: ``SaleOrder.partner`` apunta a ``res.users``, no a ``res.partner``
    (ver "El puente usuario→partner" en el docstring del módulo), así que el
    filtro cruza el puente ``ResUsers.partner``.
    """
    return SaleOrder.objects.filter(partner__partner=self)


def _get_sale_order_domain_count(self):
    """≙ ``_get_sale_order_domain_count`` (``:19-21``).

    Gancho de dominio: la fuente devuelve ``[]``, el dominio vacío. Aquí el
    equivalente es un ``Q()`` sin condiciones, que ``filter()`` ignora. Quien
    quiera acotar el conteo reemplaza este método.
    """
    return Q()


def _compute_sale_order_count(self):
    """≙ ``_compute_sale_order_count`` (``:22-42``).

    Cuenta los pedidos de ``self`` **y de toda su descendencia**, sumando en
    cada ancestro que esté en el conjunto consultado. La fuente lo hace con
    ``child_of`` + ``_read_group`` y luego sube por ``parent_id``; aquí el
    descendiente sale del recorrido por niveles ya establecido en ``crm``
    (``ResPartner`` no declara ``parent_path``) y el conteo de un
    ``annotate(Count())``.

    La guarda de grupo es de la fuente: sin ``group_sale_salesman`` devuelve
    0 sin consultar (``:24-26``).
    """
    if not _user_is_salesman():
        return 0
    descendants = _descendant_ids(self)
    groups = (SaleOrder.objects
              .filter(_get_sale_order_domain_count(self),
                      partner__partner_id__in=descendants)
              .values('partner__partner_id')
              .annotate(total=Count('pk')))
    return sum(row['total'] for row in groups)


def _descendant_ids(partner):
    """``self`` y toda su descendencia — el ``child_of`` de la fuente.

    Recorrido por niveles, misma forma que
    ``crm._fetch_children_partners_for_hierarchy`` y que
    ``BasePartnerMerge._descendant_ids``: ``ResPartner`` no declara
    ``parent_path``, así que no hay prefijo materializado que consultar.

    La ``exclude(pk__in=seen)`` corta el ciclo si la jerarquía tuviera uno.
    """
    model = type(partner)
    seen = {partner.pk}
    frontier = [partner.pk]
    while frontier:
        children = list(model.objects
                        .filter(parent_id__in=frontier)
                        .exclude(pk__in=seen)
                        .values_list('pk', flat=True))
        if not children:
            break
        seen.update(children)
        frontier = children
    return seen


def _compute_application_statistics_hook(cls, partners):
    """≙ ``_compute_application_statistics_hook`` (``:44-52``).

    Aporta la estadística de pedidos de cada partner que tenga alguno. Recibe
    ``partners`` y devuelve ``{pk: [estadística, …]}`` — la firma que este
    árbol declara para el enganche (divergencia de ``base``, no de aquí).

    El ``iconClass``/``tagClass`` se portan verbatim: son el contrato visual
    que el consumidor de la estadística espera.
    """
    contributed = {}
    if not _user_is_salesman():
        return contributed
    for partner in partners:
        count = partner.sale_order_count
        if count:
            contributed[partner.pk] = [{
                'iconClass': 'fa-usd',
                'value': count,
                'label': _('Pedidos de venta'),
                'tagClass': 'o_tag_color_2',
            }]
    return contributed


def _merge_application_statistics(new, previous):
    """``combine`` del enganche: funde lo aportado con lo que ya había.

    La fuente escribe ``data_list = super()...`` y luego hace ``append``. Aquí
    el eslabón previo devuelve su propio mapa y esta función los funde, que es
    la misma suma expresada sin mutación. Idéntica a la de ``crm`` — se repite
    porque ``sale`` no depende de ``crm``.
    """
    merged = dict(previous or {})
    for pk, stats in (new or {}).items():
        merged.setdefault(pk, [])
        merged[pk] = list(merged[pk]) + list(stats)
    return merged


def _has_order(self, partner_filter):
    """≙ ``_has_order`` (``:54-65``).

    ¿Hay algún pedido emitido (enviado o confirmado) que case con el filtro?
    La fuente usa ``sudo()`` y ``limit=1``; aquí el gestor ``objects`` es el
    de acceso cruzado (equivalente del ``sudo``) y ``.exists()`` es el
    ``limit=1``.
    """
    return SaleOrder.objects.filter(
        partner_filter, state__in=STATES_WITH_ORDER,
    ).exists()


def _can_edit_country(self, previous):
    """≙ ``_can_edit_country`` (``:67-75``).

    *"Can't edit ``country_id`` if there is (non draft) issued SO."* Encadena
    sobre la guarda de ``portal``: la previa llega en la mano como ``previous`` (``overrides=``
    de ``extend_model``), que es el ``super()`` de la fuente.

    El dominio de la fuente es ``partner_invoice_id = self OR partner_id =
    self``; aquí el ``|`` de ``Q``.
    """
    if not previous():
        return False
    return not _has_order(
        self, Q(partner_invoice_id=self.pk) | Q(partner__partner_id=self.pk))


def can_edit_vat(self, previous):
    """≙ ``can_edit_vat`` (``:77-81``).

    *"Can't edit ``vat`` if there is (non draft) issued SO."* El dominio de la
    fuente es ``partner_id child_of commercial_partner_id``: todo pedido de la
    entidad comercial o de cualquiera de sus hijos.
    """
    if not previous():
        return False
    commercial = self.commercial_partner
    return not _has_order(
        self, Q(partner__partner_id__in=_descendant_ids(commercial)))


# ----------------------------------------------------------------------
# Agregado propio del L0 — NO está en la fuente
# ----------------------------------------------------------------------

def lifetime_value(partner) -> Decimal:
    """Valor de vida del cliente: suma de sus ventas confirmadas.

    **No tiene contraparte en ``odoo19c``** — es un agregado que este árbol
    declaró antes de portar el archivo, y se conserva verbatim.

    ``state=sale`` deja fuera dos cosas distintas: las ventas **canceladas** y
    los **carritos** (``draft``). Un carrito abandonado no es valor de vida.

    ``amount_total`` es columna real (H-API-30): ``Sum`` directo.
    """
    agg = SaleOrder.objects.filter(
        partner__partner=partner, state=SaleOrder.STATE_SALE,
    ).aggregate(total=Sum('amount_total'))
    return agg['total'] or Decimal('0.00')


def sale_order_count(partner) -> int:
    """Número de ventas confirmadas del cliente.

    **No es** ``sale_order_count`` de la fuente, que cuenta *todos* los
    pedidos del partner y su descendencia sin filtrar por estado. Se conserva
    con su nombre histórico porque hay consumidores; el de la fuente vive como
    la ``property`` del mismo nombre sobre ``ResPartner``.
    """
    return SaleOrder.objects.filter(
        partner__partner=partner, state=SaleOrder.STATE_SALE).count()


def apply_sale_partner_extensions():
    """Cuelga los cuatro campos y los cinco métodos. La llama ``SaleConfig.ready()``."""
    extend_model(
        _inherit,
        campos={
            'sale_warn_msg': fields.Text(
                null=True, blank=True,
                help_text='Odoo sale_warn_msg ("Message for Sales Order"). '
                          'Aviso interno que se muestra al vender a este '
                          'cliente.',
            ),
        },
        propiedades={
            'sale_order_ids': _sale_order_ids,
            'sale_order_count': _compute_sale_order_count,
        },
        metodos={
            '_get_sale_order_domain_count': _get_sale_order_domain_count,
            '_compute_sale_order_count': _compute_sale_order_count,
            '_has_order': _has_order,
        },
        overrides={
            '_can_edit_country': _can_edit_country,
            'can_edit_vat': can_edit_vat,
        },
    )
    chain_method(ResPartner, '_compute_application_statistics_hook',
                 classmethod(_compute_application_statistics_hook),
                 combine=_merge_application_statistics)
