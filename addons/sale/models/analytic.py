"""Extensiones de la familia ``analytic`` que escribe ``sale`` — ≙ ``_inherit``.

Origen: ``odoo19c: sale/models/analytic.py`` (LGPL-3 según su
``__manifest__.py``, así que el mecanismo es copia + adaptación con
atribución). Dos clases, y las dos son extensiones: el plan analítico no sabe
que existen las ventas; es la venta quien se anota en él.

``AccountAnalyticLine.so_line`` (``:6-9``)
    La línea de venta que originó el apunte. Sus tres atributos:

    - ``comodel_name='sale.order.line'`` → ``'sale.SaleOrderLine'``
    - ``string='Sales Order Item'``      → ``verbose_name``
    - ``domain=[('qty_delivered_method', '=', 'analytic')]`` →
      :data:`SO_LINE_DOMAIN`, que se aplica donde se consulta. Django no
      declara el dominio en el campo, así que se nombra una vez y se importa.
    - ``index='btree_not_null'`` → índice **parcial** ``WHERE … IS NOT NULL``,
      :data:`SO_LINE_INDEX`. Se cuelga del ``Meta`` del modelo ajeno con
      ``extend_model(indexes=…)``, y su DDL lo emite
      ``analytic/migrations/0006`` porque el modelo es de esa app.
      ``db_index=True`` daría un btree entero, que es otro índice.

``AccountAnalyticApplicability.business_domain`` (``:12-20``)
    ``selection_add=[('sale_order', 'Sale Order')]`` — amplía el vocabulario
    del campo que ``analytic`` declara, vía ``extend_model(selection_add=…)``.
    Redeclarar el campo perdería los valores que ya trae, que es exactamente
    lo que ``selection_add`` existe para evitar.

    Su ``ondelete={'sale_order': 'cascade'}`` (``:19``) gobierna qué pasa con
    las filas que guardan el valor **al desinstalar el módulo que lo aportó**.
    Aquí no hay desinstalación de módulo que retire un valor de ``choices``:
    la app se declara en ``INSTALLED_APPS`` y su vocabulario vive con ella. Es
    divergencia de mecanismo, no símbolo omitido, y se declara aquí.

Este archivo cierra un bloqueo raíz declarado: ``analytic/migrations/0004``
decía verbatim *"so_line no existe en este árbol"* al portar el ``order`` de
``sale_timesheet``, que es ``related=so_line.order_id``.
"""
import fields
import models

from orm.model_classes import extend_model

#: ≙ la cabecera de ``AccountAnalyticLine`` (``odoo19c: :7``; la extensión
#: aquí no es clase). Dos constantes y no una porque el archivo extiende DOS
#: modelos: el sufijo nombra a cuál pertenece cada una.
_INHERIT_ACCOUNT_ANALYTIC_LINE = 'account.analytic.line'

#: ≙ la cabecera de ``AccountAnalyticApplicability`` (``odoo19c: :13-14``).
#: La fuente declara DOS atributos en esta clase, no uno —``_inherit`` y
#: ``_description``—; el segundo se porta verbatim aunque el modelo base
#: (``addons/analytic/models/analytic_plan.py``) ya declare su propio
#: ``Meta.verbose_name`` en español: son atributos distintos que no se
#: sustituyen entre sí (``atributos-de-clase-de-modelo.md``).
_INHERIT_ACCOUNT_ANALYTIC_APPLICABILITY = 'account.analytic.applicability'
_DESCRIPTION_ACCOUNT_ANALYTIC_APPLICABILITY = "Analytic Plan's Applicabilities"

#: ≙ el ``domain`` del ``Many2one`` (``odoo19c: :9``). Django no declara el
#: dominio en el campo, así que la restricción se aplica donde se consulta y
#: éste es su nombre único — quien filtre líneas candidatas lo importa.
SO_LINE_DOMAIN = {'qty_delivered_method': 'analytic'}

#: ≙ ``index='btree_not_null'`` (``odoo19c: :9``). En 19 ese valor pide un
#: btree **parcial**: la mayoría de los apuntes analíticos no nace de una
#: venta, y un índice completo pagaría por todas esas filas nulas. Vive aquí
#: —no en el ``Meta`` de ``analytic``— porque es ``sale`` quien aporta la
#: columna; el ``Meta`` del modelo ajeno lo recibe por ``indexes=``.
SO_LINE_INDEX = models.Index(
    fields=['so_line'],
    condition=models.Q(so_line__isnull=False),
    name='analytic_line_so_line_nn',
)

#: ≙ ``selection_add=[('sale_order', 'Sale Order')]`` (``odoo19c: :14-16``).
#: El valor —lo que se guarda y se compara— es idéntico al de la referencia;
#: la etiqueta va en español por ``redaccion-tecnica-es.md``, igual que los
#: dos que ``account`` ya suma a este mismo campo.
BUSINESS_DOMAIN_SELECTION_ADD = [
    ('sale_order', 'Pedido de venta'),
]

#: ≙ ``ondelete={'sale_order': 'cascade'}`` (``odoo19c: sale/models/analytic.py:20``).
#: ``business_domain`` es ``required=True`` en la raíz
#: (``odoo19c: analytic/models/analytic_plan.py:416``), y la fuente rechaza un
#: valor nuevo sin política sobre un campo requerido: dejarlo vacío no sería un
#: estado válido. Por eso la política es ``cascade`` — la fila de
#: aplicabilidad se va con el dominio que la nombra.
BUSINESS_DOMAIN_ONDELETE = {'sale_order': 'cascade'}


def apply_sale_analytic_extensions():
    """Cuelga sobre la familia analítica lo que ``sale`` le añade.

    La invoca ``SaleConfig.ready()``: en tiempo de import el registro de
    modelos aún no está poblado, y ``extend_model`` difiere la aplicación
    hasta que la clase destino exista.
    """
    extend_model(
        'analytic', 'AccountAnalyticLine',
        campos={
            'so_line': fields.Many2one(
                'sale.SaleOrderLine', null=True, blank=True,
                on_delete=models.SET_NULL,
                related_name='analytic_lines',
                verbose_name='Línea de pedido de venta',
                help_text='Odoo so_line ("Sales Order Item"). Acotado a las '
                          'líneas con qty_delivered_method=analytic; ver '
                          'SO_LINE_DOMAIN. El índice parcial que la fuente '
                          'pide con index=btree_not_null lo declara la '
                          'migración de analytic.',
            ),
        },
        indexes=[SO_LINE_INDEX],
    )
    extend_model(
        'analytic', 'AccountAnalyticApplicability',
        selection_add={'business_domain': BUSINESS_DOMAIN_SELECTION_ADD},
        ondelete={'business_domain': BUSINESS_DOMAIN_ONDELETE},
    )

