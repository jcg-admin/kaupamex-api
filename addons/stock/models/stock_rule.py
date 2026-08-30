"""``stock.rule`` — addon ``stock``.

Adaptación de Odoo ``stock/models/stock_rule.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: la **regla** es la unidad ejecutable del ruteo. Una ruta
(``stock.route``) no mueve nada; agrupa reglas, y cada regla dice *qué hacer*
cuando falta producto en una ubicación o cuando llega producto a otra. Sus dos
direcciones son opuestas y conviven en el mismo modelo:

- **``pull``** — la necesidad *tira*. Falta producto en el destino, así que se
  crea un movimiento que lo trae desde ``location_src_id``. Es el camino que
  recorre ``run`` → ``_get_rule`` → ``_run_pull``.
- **``push``** — la llegada *empuja*. El producto aterrizó en
  ``location_src_id`` y la regla genera el siguiente salto hacia
  ``location_dest_id``. Lo dispara ``stock.move._push_apply``, no ``run``.

Y el tercer eje, ortogonal a esos dos, es **``procure_method``**: qué hacer
cuando el origen no tiene existencia — tomarla igual (``make_to_stock``),
disparar otra regla que la traiga (``make_to_order``), o lo primero con
respaldo de lo segundo (``mts_else_mto``).

Por qué este archivo importa más de lo que su tamaño sugiere
==============================================================

**Era un esbozo de 80 líneas contra 748 de la referencia.** Declaraba 5 campos
de 22 y 2 métodos de 31, y su ``run(product, qty, picking=None)`` era una firma
que la referencia no tiene: aplicaba *una* regla ya elegida, en vez de resolver
qué regla aplica. Toda la parte difícil —encontrar la regla subiendo por el
árbol de ubicaciones, respetar la precedencia entre rutas de producto,
categoría, almacén y embalaje— no existía.

Y lo consume el almacén: ``stock_warehouse.py`` crea reglas en seis sitios con
``rule_model.objects.create(**vals)``, pasando ``picking_type_id``,
``location_src_id``, ``location_dest_id``, ``route_id``, ``action``,
``procure_method``, ``propagate_cancel``, ``auto``, ``warehouse_id`` y
``company_id`` — nueve campos que el esbozo no declaraba.

Porte símbolo por símbolo — 32 de 32
======================================

Medido sobre ``odoo19c: addons/stock/models/stock_rule.py`` (748 líneas):
**2 clases de módulo** (``ProcurementException``, ``Procurement``) más
``StockRule`` con **4 atributos de clase**, **22 campos** y **31 métodos**;
32 métodos contando el ``__init__`` de la excepción.

*Métrica:* clases, asignaciones y métodos por AST sobre el cuerpo de cada
clase del archivo de la referencia.
*Ciega a:* las funciones locales declaradas dentro de un método —aquí hay tres
(``raise_exception`` en ``run``; ``extract_rule`` y ``get_rule_for_routes`` en
``_get_rule``)— que se portan dentro de su método, igual que en la fuente.

Atributos de clase — 4 de 4
-----------------------------

Los cuatro de ORM (``:44-47``), verbatim. No hay objetos de tabla en esta
clase, así que ``Meta`` sólo lleva ``db_table`` y ``ordering``
(``atributos-de-clase-de-modelo.md``).

.. list-table::
   :header-rows: 1
   :widths: 34 22 44

   * - Símbolo (línea)
     - Qué es
     - Aquí
   * - ``_name`` (44)
     - atributo de ORM
     - verbatim
   * - ``_description`` (45)
     - atributo de ORM
     - verbatim
   * - ``_order`` (46)
     - atributo de ORM
     - verbatim + ``Meta.ordering``
   * - ``_check_company_auto`` (47)
     - atributo de ORM
     - verbatim + el check en ``save()``

Más ``Procurement = Procurement`` (``:56``), que no es atributo de ORM sino el
``NamedTuple`` del módulo colgado de la clase para que ``StockRule.Procurement``
resuelva como en la fuente. Es la misma mezcla que
``metrica-decide-la-conclusion.md`` describe: el AST devuelve 27 asignaciones y
sólo 22 son campos.

Campos — 22 de 22
-------------------

El FK va sin el sufijo ``_id`` porque Django ya expone la columna como
``<campo>_id``; así ``stock_warehouse.py`` sigue creando reglas con
``location_src_id=…`` sin cambiar una línea.

``name`` · ``active`` · ``action`` · ``sequence`` · ``company`` ·
``location_dest`` · ``location_src`` · ``location_dest_from_rule`` · ``route`` ·
``route_company`` · ``procure_method`` · ``route_sequence`` · ``picking_type`` ·
``picking_type_code_domain`` · ``delay`` · ``partner_address`` ·
``propagate_cancel`` · ``propagate_carrier`` · ``warehouse`` · ``auto`` ·
``rule_message`` · ``push_domain``.

Tres de ellos no son columnas, porque en la referencia tampoco lo son:
``route_company``, ``picking_type_code_domain`` y ``rule_message`` se declaran
``NonStored`` (≙ el ``compute`` sin ``store=True`` de la fuente), el mecanismo
que ``orm/fields_nonstored.py`` construyó para exactamente este caso.
``route_sequence`` **sí** es columna: la referencia lo declara
``related='route_id.sequence', store=True`` porque el ``_read_group`` de
``_search_rule_for_warehouses`` ordena por él.

Métodos — 32 de 32
--------------------

Todos con su nombre y su visibilidad: ``run``, ``run_scheduler`` y
``copy_data`` siguen siendo públicos; los 28 restantes conservan su guion bajo
(``porte-completo-no-parcial.md``, :ref:`h-api-581`).

Igual que en ``stock_warehouse.py``: un método que la fuente escribe con
``self.ensure_one()`` o que lee un solo registro es **método de instancia**;
uno decorado ``@api.model`` —que en Odoo se llama sobre el modelo, no sobre un
registro— es **``classmethod``**. ``_get_lead_days`` y
``_check_company_consistency`` filtran ``self`` como recordset, así que son
``classmethod`` que reciben ``rules``.

Divergencias declaradas
=========================

**D-1 — ``env.ref`` es ``IrModelData.ref``.** ``_get_rule``,
``_check_intercomp_location`` y ``_get_rule_domain`` resuelven
``stock.stock_location_customers`` y ``stock.stock_location_inter_company`` por
XML ID. Aquí lo hace ``IrModelData.ref(xml_id, raise_if_not_found=False)``, con
el mismo fallback que la referencia. Mismo criterio que ``stock_warehouse.py``.

**D-2 — ``_read_group`` no existe; el agrupado se hace en Python.**
``_search_rule_for_warehouses`` (``:507-532``) pide al ORM un
``_read_group(groupby=[...], aggregates=['id:recordset'], order='route_sequence:min, sequence:min')``
— un agrupado que devuelve **recordsets** por grupo, no agregados escalares. El
``values(...).annotate(...)`` de Django agrega escalares; no hay contraparte
directa. Se porta con una sola consulta ordenada por ``(route_sequence,
sequence)`` y el agrupado hecho en Python, que produce el mismo
``rule_dict[(location_dest, route)][warehouse] = regla`` con el mismo criterio
de desempate. Es divergencia de mecanismo, no de conducta.

**D-3 — ``location_final_id`` no existe en este ``StockMove``.**
``_get_stock_move_values`` (``:324-384``) escribe el destino **final** en
``location_final_id`` y deja ``location_dest_id`` al tipo de operación, salvo
cuando ``location_dest_from_rule``. Este ``StockMove`` es todavía un esbozo (16
símbolos contra 210 de la referencia) y no declara ``location_final_id``, así
que ``_run_pull`` escribe el destino en ``location_dest_id``. El diccionario que
``_get_stock_move_values`` devuelve **conserva las dos claves**: el contrato de
la referencia se porta entero, y la proyección al modelo ocurre en un solo
sitio, ``_move_values_for_model``.

**D-4 — ``_run_pull`` proyecta los valores sobre los campos declarados.** Del
mismo esbozo se sigue que 15 de las 22 claves del diccionario no tienen columna
(``rule_id``, ``picking_type_id``, ``procurement_values``, ``reference_ids``,
``route_ids``, ``warehouse_id``, ``date``, ``date_deadline``,
``propagate_cancel``, ``priority``, ``orderpoint_id``, …). La proyección es
**explícita y ruidosa**: ``_move_values_for_model`` registra en ``DEBUG`` cada
clave descartada, con el nombre del modelo. No es un filtro silencioso.
Sucesor: la tarea **#330**, cuyo siguiente archivo es ``stock_move.py``.

**D-5 — el planificador corre sin orderpoint ni barra de progreso.**
``_run_scheduler_tasks`` (``:691-724``) hace tres cosas: recalcular los puntos
de pedido, asignar los movimientos confirmados y fusionar quants. La segunda y
la tercera se portan enteras. La primera necesita
``stock.warehouse.orderpoint``, que **no existe en este árbol** —medido:
``grep -rn "StockWarehouseOrderpoint" addons/ src/`` → 0—, así que el bloque
registra un ``warning`` con el nombre del modelo ausente en vez de fallar en
silencio. Y ``ir.cron._commit_progress``, que la referencia usa para la barra
de progreso del cliente, tampoco existe (medido igual: 0 hits); el parámetro
``use_new_cursor`` se conserva en la firma y los puntos de commit quedan como
``debug``. Sucesor: la tarea **#330** para el orderpoint (``stock_orderpoint``
es uno de sus 25 archivos) y la **#124** para el contador de progreso.

**D-6 — ``relativedelta`` → ``datetime.timedelta``.** La referencia desplaza las
fechas con ``relativedelta(days=…)`` (``:331``, ``:335``), de ``python-dateutil``,
que **no es dependencia de este proyecto** (medido: 0 hits en ``pyproject.toml``;
``django`` lo declara opcional y no lo instala). Para un desplazamiento **sólo en
días** ambos son idénticos —``relativedelta`` sólo se separa del ``timedelta`` en
``months``/``years``, que aquí no se usan—, así que se sustituye por el stdlib.
Mismo criterio y mismo precedente que ``account_payment_term.py`` y ``digest.py``.

**D-7 — ``Command`` aquí es ejecutivo, no declarativo.** La referencia coloca
tuplas-comando **dentro** del diccionario de valores
(``'reference_ids': [Command.set(ids)]``, ``:365``; ``'route_ids':
[Command.clear()] + [Command.link(id) …]``, ``:370``) y el ORM las interpreta al
crear. El ``Command`` de este árbol (``src/orm/commands.py:38-45``) **actúa sobre
un related manager de Django en el momento de llamarlo** —``set(manager, objs)``,
``clear(manager)``— así que la forma declarativa no existe: llamarlo dentro del
literal levanta ``TypeError`` por el ``manager`` que falta, que es como se
detectó.

La conducta se conserva sin pérdida: ambas claves llevan la semántica «este
conjunto y ningún otro», que en un diccionario de **creación** es exactamente una
lista de ids —no hay estado previo que limpiar—. Se emiten como lista de ``pk``
y el cableado del m2m queda del lado del consumidor. Hoy ese consumidor no
existe: este ``StockMove`` no declara ni ``reference_ids`` ni ``route_ids``, así
que ``_move_values_for_model`` los descarta registrándolo en ``DEBUG`` (D-4).
Sucesor: la misma tarea **#330**, al portar ``stock_move.py``.
"""
import datetime
import logging
from collections import OrderedDict, defaultdict
from decimal import Decimal
from functools import partial
from typing import NamedTuple

import fields
import models
from django.apps import apps
from django.db.models import Q
from django.utils import timezone

from addons.base.models import TimeStampedModel
from exceptions import UserError, ValidationError
from orm.environments import get_current_company, is_su
from osv import expression
from tools.float_utils import float_is_zero
from tools.misc import split_every
from tools.translate import _

_logger = logging.getLogger(__name__)

#: XML IDs que la referencia resuelve con ``env.ref`` dentro de este archivo.
XMLID_CUSTOMERS = 'stock.stock_location_customers'
XMLID_INTER_COMPANY = 'stock.stock_location_inter_company'


class ProcurementException(Exception):
    """≙ ``ProcurementException`` (``odoo19c: :19-28``).

    «An exception raised by StockRule ``run`` containing all the faulty
    procurements.»
    """

    def __init__(self, procurement_exceptions):
        """≙ ``__init__`` (``:23-28``).

        :param procurement_exceptions: lista de tuplas ``(procurement, mensaje)``
            con las necesidades que no se pudieron satisfacer.
        """
        super().__init__(procurement_exceptions)
        self.procurement_exceptions = procurement_exceptions


class Procurement(NamedTuple):
    """≙ ``Procurement`` (``odoo19c: :31-39``) — la necesidad, como dato.

    Ocho campos, en el mismo orden: es lo que ``run`` recibe y lo que
    ``_get_stock_move_values`` desempaqueta con ``*procurement``. Las
    anotaciones son las de la fuente —clases de campo del ORM usadas como pista
    de tipo—, no tipos de Python.
    """

    product_id: fields.Many2one
    product_qty: fields.Float
    product_uom: fields.Many2one
    location_id: fields.Many2one
    name: fields.Char
    origin: fields.Char
    company_id: fields.Many2one
    values: dict


def _move_values_for_model(values):
    """Proyecta los valores de un movimiento sobre los campos que existen hoy.

    **No es un símbolo de la referencia**: es la divergencia D-3/D-4 hecha
    explícita en un solo sitio. ``_get_stock_move_values`` porta el diccionario
    entero de la fuente; este ayudante decide qué parte de él este ``StockMove``
    —todavía un esbozo— puede recibir, y **deja constancia en el log de lo que
    descarta**, con el nombre de cada clave.

    ``location_final_id`` se mapea a ``location_dest_id`` cuando la regla no
    fijó un destino explícito: sin ``location_final_id`` en el modelo, el
    destino final es el único destino que hay.
    """
    move_model = apps.get_model('stock', 'StockMove')
    campos = move_model._meta.get_fields()
    muchos_a_muchos = {f.name for f in campos if f.many_to_many}
    concrete = {f.name for f in campos} - muchos_a_muchos
    concrete |= {f'{f.name}_id' for f in campos
                 if f.is_relation and not f.many_to_many}

    # Relaciones por nombre: la referencia entrega el **pk bajo el nombre del
    # campo** (``'product_uom': product_uom.id``, ``odoo19c: stock_rule.py:359``)
    # porque su ORM lo admite; Django exige la instancia, o el pk bajo
    # ``<campo>_id``. Sin esta traducción el valor pasa el filtro por nombre y
    # revienta al asignar (``Cannot assign "187": … must be a "Uom" instance``).
    relacionales = {f.name for f in campos
                    if f.is_relation and not f.many_to_many}

    # ``False`` como vacío: la referencia lo usa para TODO campo sin valor
    # —``date_deadline = False`` (``odoo19c: stock_rule.py:334``),
    # ``'picking_id': False`` (``:365``)— porque su ORM no distingue el falso
    # del nulo. Django sí: un ``DateTimeField`` que recibe ``False`` revienta
    # en ``fromisoformat: argument must be str``. Se traduce a ``None`` salvo
    # donde el campo de destino sea booleano de verdad.
    booleanos = {f.name for f in campos
                 if getattr(f, 'get_internal_type', None)
                 and f.get_internal_type() == 'BooleanField'}

    projected, dropped = {}, []
    for key, value in values.items():
        if key == 'location_final_id':
            continue
        # Los Many2many NO viajan en ``create()`` — Django los rechaza en el
        # constructor (``Direct assignment to the reverse side … is
        # prohibited``). La referencia sí los entrega ahí, en forma de comando
        # (``'move_dest_ids': [(4, x.id) …]``, ``odoo19c: stock_rule.py:340,364``)
        # porque su ``create`` los interpreta. Aquí los aplica ``_create_move``
        # después de tener la fila.
        if key in muchos_a_muchos:
            continue
        if value is False and key.removesuffix('_id') not in booleanos:
            value = None
        if key in relacionales and isinstance(value, (int, str)):
            projected[f'{key}_id'] = value
        elif key in concrete:
            projected[key] = value
        else:
            dropped.append(key)

    if not projected.get('location_dest_id') and values.get('location_final_id'):
        projected['location_dest_id'] = values['location_final_id']

    if dropped:
        _logger.debug(
            'stock.rule: %s no declara %s; se descartan de los valores del '
            'movimiento (divergencia D-4, tarea #330)',
            move_model.__name__, ', '.join(sorted(dropped)))
    return projected


def _create_move(values):
    """Crea el ``stock.move`` y **después** enlaza sus Many2many.

    **No es un símbolo de la referencia**: allá ``create`` acepta los comandos
    del Many2many en el mismo diccionario (``[(4, id)]``), así que crear y
    enlazar es una sola llamada. Django separa las dos fases —la fila tiene que
    existir antes de que su tabla intermedia pueda apuntarla—, y por eso el
    enlace vive aquí y no en ``_move_values_for_model``, que sólo proyecta.
    """
    move_model = apps.get_model('stock', 'StockMove')
    muchos_a_muchos = {f.name for f in move_model._meta.get_fields()
                       if f.many_to_many}
    move = move_model.objects.create(**_move_values_for_model(values))
    for nombre in muchos_a_muchos & set(values):
        relacionados = values[nombre]
        if relacionados:
            getattr(move, nombre).set(relacionados)
    return move


def _orderpoint_model():
    """Devuelve ``stock.warehouse.orderpoint`` si existe, o ``None`` con aviso.

    **No es un símbolo de la referencia**: es la divergencia D-5 hecha
    explícita. El planificador de la fuente arranca por los puntos de pedido, y
    ese modelo todavía no está en el árbol; devolver ``None`` **con un
    ``warning``** deja el hueco visible en el log en vez de esconderlo dentro de
    un ``try`` mudo.
    """
    try:
        return apps.get_model('stock', 'StockWarehouseOrderpoint')
    except LookupError:
        _logger.warning(
            'stock.rule: el planificador omite el recálculo de puntos de pedido '
            '— stock.warehouse.orderpoint no está portado (divergencia D-5, '
            'tarea #330)')
        return None


class StockRule(TimeStampedModel):
    """``stock.rule`` — «A rule describe what a procurement should do; produce, buy, move, ...»"""

    # Atributos de clase de modelo — los cuatro que la referencia declara
    # (``odoo19c: addons/stock/models/stock_rule.py:44-47``), verbatim.
    _name = 'stock.rule'
    _description = "Stock Rule"
    _order = "sequence, id"
    _check_company_auto = True

    #: ≙ ``Procurement = Procurement`` (``:56``) — el mismo ``NamedTuple`` del
    #: módulo, colgado aquí para que ``StockRule.Procurement(...)`` resuelva
    #: como en la fuente.
    Procurement = Procurement

    ACTION_PULL      = 'pull'
    ACTION_PUSH      = 'push'
    ACTION_PULL_PUSH = 'pull_push'
    ACTION_CHOICES = [
        (ACTION_PULL, 'Pull From'),
        (ACTION_PUSH, 'Push To'),
        (ACTION_PULL_PUSH, 'Pull & Push'),
    ]

    PROCURE_MTS = 'make_to_stock'
    PROCURE_MTO = 'make_to_order'
    PROCURE_MTS_ELSE_MTO = 'mts_else_mto'
    PROCURE_CHOICES = [
        (PROCURE_MTS, 'Take From Stock'),
        (PROCURE_MTO, 'Trigger Another Rule'),
        (PROCURE_MTS_ELSE_MTO,
         'Take From Stock, if unavailable, Trigger Another Rule'),
    ]

    AUTO_MANUAL = 'manual'
    AUTO_TRANSPARENT = 'transparent'
    AUTO_CHOICES = [
        (AUTO_MANUAL, 'Manual Operation'),
        (AUTO_TRANSPARENT, 'Automatic No Step Added'),
    ]

    name                     = fields.Char(
        max_length=255,
        help_text='Nombre de la regla; rellena el origen del albarán y el '
                  'nombre de sus movimientos (Odoo name, translate=True).',
    )
    active                   = fields.Boolean(
        default=True,
        help_text='Si se desmarca, la regla se oculta sin borrarla (Odoo active).',
    )
    action                   = fields.Selection(
        max_length=16, choices=ACTION_CHOICES, default=ACTION_PULL,
        db_index=True, required=True,
        help_text='Dirección de la regla (Odoo action).',
    )
    sequence                 = fields.Integer(
        default=20, help_text='Secuencia dentro de la ruta (Odoo sequence).',
    )
    company                  = fields.Many2one(
        'base.ResCompany', null=True, blank=True, on_delete=models.CASCADE,
        related_name='stock_rules', db_index=True,
        help_text='Empresa (Odoo company_id; su dominio la ata a la empresa de '
                  'la ruta — ver _check_company_consistency).',
    )
    location_dest            = fields.Many2one(
        'stock.StockLocation', on_delete=models.CASCADE, related_name='rules_in',
        db_index=True,
        help_text='Ubicación destino (Odoo location_dest_id, required, '
                  'check_company).',
    )
    location_src             = fields.Many2one(
        'stock.StockLocation', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='rules_out', db_index=True,
        help_text='Ubicación origen (Odoo location_src_id, check_company).',
    )
    location_dest_from_rule  = fields.Boolean(
        default=False,
        help_text='Si es verdadero, el destino del movimiento lo fija la regla; '
                  'si no, lo toma del tipo de operación (Odoo '
                  'location_dest_from_rule).',
    )
    route                    = fields.Many2one(
        'stock.StockRoute', on_delete=models.CASCADE, related_name='rule_ids',
        db_index=True, help_text='Ruta a la que pertenece (Odoo route_id, required).',
    )
    procure_method           = fields.Selection(
        max_length=16, choices=PROCURE_CHOICES, default=PROCURE_MTS,
        help_text='Método de suministro (Odoo procure_method).',
    )
    route_sequence           = fields.Integer(
        default=0, db_index=True,
        help_text='Secuencia de la ruta, replicada aquí para poder ordenar por '
                  'ella (Odoo route_sequence, related+store=True).',
    )
    picking_type             = fields.Many2one(
        'stock.StockPickingType', null=True, blank=True, on_delete=models.CASCADE,
        related_name='rule_ids', db_index=True,
        help_text='Tipo de operación que la regla usa al crear el movimiento '
                  '(Odoo picking_type_id, required, check_company).',
    )
    delay                    = fields.Integer(
        default=0,
        help_text='Plazo en días que se resta a la fecha prevista del '
                  'movimiento creado (Odoo delay).',
    )
    partner_address          = fields.Many2one(
        'base.ResPartner', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='stock_rules',
        help_text='Dirección de entrega, opcional (Odoo partner_address_id).',
    )
    propagate_cancel         = fields.Boolean(
        default=False,
        help_text='Si se cancela el movimiento que crea esta regla, se cancela '
                  'también el siguiente (Odoo propagate_cancel).',
    )
    propagate_carrier        = fields.Boolean(
        default=False,
        help_text='Propaga el transportista al movimiento siguiente (Odoo '
                  'propagate_carrier).',
    )
    warehouse                = fields.Many2one(
        'stock.StockWarehouse', null=True, blank=True, on_delete=models.CASCADE,
        related_name='rule_ids', db_index=True,
        help_text='Almacén al que la regla queda acotada (Odoo warehouse_id, '
                  'check_company).',
    )
    auto                     = fields.Selection(
        max_length=16, choices=AUTO_CHOICES, default=AUTO_MANUAL,
        help_text='«Manual Operation» crea un movimiento nuevo tras el actual; '
                  '«Automatic No Step Added» sustituye la ubicación en el '
                  'movimiento original (Odoo auto).',
    )
    push_domain              = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Dominio extra de aplicabilidad de la regla push (Odoo '
                  'push_domain).',
    )

    #: ≙ ``route_company_id`` (``:77``) — ``related='route_id.company_id'`` sin
    #: ``store``. Devuelve el registro de empresa de la ruta, como la fuente.
    route_company = fields.NonStored(
        default=lambda rule: rule.route.company if rule.route_id else None,
        help_text='Empresa de la ruta (Odoo route_company_id, related).',
    )
    #: ≙ ``picking_type_code_domain`` (``:91``) — ``fields.Json`` computado sin
    #: ``store``.
    picking_type_code_domain = fields.NonStored(
        default=lambda rule: rule._compute_picking_type_code_domain(),
        help_text='Códigos de tipo de operación admisibles (Odoo '
                  'picking_type_code_domain).',
    )
    #: ≙ ``rule_message`` (``:110``) — ``fields.Html`` computado sin ``store``.
    rule_message = fields.NonStored(
        default=lambda rule: rule._compute_action_message(),
        help_text='Descripción legible del propósito de la regla (Odoo '
                  'rule_message).',
    )

    class Meta:
        db_table = 'stock_rule'
        ordering = ['sequence', 'id']
        verbose_name = 'Regla de aprovisionamiento'
        verbose_name_plural = 'Reglas de aprovisionamiento'

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """Mantiene ``route_sequence`` y aplica ``_check_company_auto``.

        La referencia obtiene ``route_sequence`` con ``related=… store=True``:
        el ORM lo recalcula al guardar. Aquí se hace explícito, en el mismo
        punto. Y ``_check_company_auto = True`` es el atributo que ordena
        validar la coherencia de empresa al escribir — el ``@api.constrains``
        de ``_check_company_consistency``.
        """
        if self.route_id:
            self.route_sequence = self.route.sequence or 0
        type(self)._check_company_consistency([self])
        return super().save(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Defaults y copia (≙ :49-118)                                         #
    # ------------------------------------------------------------------ #

    @classmethod
    def default_get(cls, field_names, values=None):
        """≙ ``default_get`` (``odoo19c: :49-54``).

        Sin empresa explícita, la regla nace en la empresa del contexto — el
        ``self.env.company`` de la fuente, que aquí es ``get_current_company()``.
        """
        res = dict(values or {})
        if 'company_id' in field_names and not res.get('company_id'):
            res['company_id'] = get_current_company()
        return res

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``odoo19c: :113-118``).

        Sin un nombre explícito, la copia se marca como tal para que dos reglas
        idénticas se distingan en la lista de la ruta.
        """
        default = dict(default or {})
        vals = {
            'name': self.name,
            'active': self.active,
            'action': self.action,
            'sequence': self.sequence,
            'company_id': self.company_id,
            'location_dest_id': self.location_dest_id,
            'location_src_id': self.location_src_id,
            'location_dest_from_rule': self.location_dest_from_rule,
            'route_id': self.route_id,
            'procure_method': self.procure_method,
            'picking_type_id': self.picking_type_id,
            'delay': self.delay,
            'partner_address_id': self.partner_address_id,
            'propagate_cancel': self.propagate_cancel,
            'propagate_carrier': self.propagate_carrier,
            'warehouse_id': self.warehouse_id,
            'auto': self.auto,
            'push_domain': self.push_domain,
        }
        vals.update(default)
        if 'name' not in default:
            vals['name'] = _("%s (copy)", self.name)
        return [vals]

    # ------------------------------------------------------------------ #
    # Coherencia y onchange (≙ :120-148)                                   #
    # ------------------------------------------------------------------ #

    @classmethod
    def _check_company_consistency(cls, rules):
        """≙ ``_check_company_consistency`` (``odoo19c: :120-130``).

        Una regla no puede pertenecer a una empresa distinta de la de su ruta:
        sería una regla que su propia ruta no puede aplicar.
        """
        for rule in rules:
            route = rule.route if rule.route_id else None
            if route is None or not route.company_id:
                continue
            if rule.company_id != route.company_id:
                raise ValidationError(_(
                    "Rule %(rule)s belongs to %(rule_company)s while the route "
                    "belongs to %(route_company)s.",
                    rule=str(rule),
                    rule_company=str(rule.company) if rule.company_id else '',
                    route_company=str(route.company),
                ))

    def _onchange_picking_type(self):
        """≙ ``_onchange_picking_type`` (``odoo19c: :132-139``).

        Al elegir el tipo de operación, sus ubicaciones por defecto pasan a ser
        las de la regla.
        """
        if not self.picking_type_id:
            return
        self.location_src_id = self.picking_type.default_location_src_id
        self.location_dest_id = self.picking_type.default_location_dest_id

    def _onchange_route(self):
        """≙ ``_onchange_route`` (``odoo19c: :141-147``).

        «Ensure that the rule's company is the same than the route's company.»
        Y si el tipo de operación pertenece a un almacén de otra empresa, se
        descarta: sería incoherente al guardar.
        """
        if self.route_id and self.route.company_id:
            self.company_id = self.route.company_id
        if self.picking_type_id:
            warehouse = self.picking_type.warehouse
            route_company = self.route.company_id if self.route_id else None
            if warehouse is not None and warehouse.company_id != route_company:
                self.picking_type_id = None

    # ------------------------------------------------------------------ #
    # El mensaje que describe la regla (≙ :149-210)                        #
    # ------------------------------------------------------------------ #

    def _get_message_values(self):
        """≙ ``_get_message_values`` (``odoo19c: :149-159``).

        Devuelve origen, destino, destino directo y operación. Existe para que
        ``_get_message_dict`` —y sus extensiones en ``mrp`` y
        ``purchase_stock``— no repitan la misma resolución.
        """
        source = str(self.location_src) if self.location_src_id else _('Source Location')
        destination = (str(self.location_dest) if self.location_dest_id
                       else _('Destination Location'))
        direct_destination = False
        if self.picking_type_id:
            default_dest = self.picking_type.default_location_dest
            if default_dest is not None and default_dest.pk != self.location_dest_id:
                direct_destination = str(default_dest)
        operation = str(self.picking_type) if self.picking_type_id else _('Operation Type')
        return source, destination, direct_destination, operation

    def _get_message_dict(self):
        """≙ ``_get_message_dict`` (``odoo19c: :161-193``).

        Un mensaje por acción (salvo la combinada). «This function is override
        in mrp and purchase_stock in order to complete the dictionary.»
        """
        message_dict = {}
        source, destination, direct_destination, operation = self._get_message_values()
        if self.action not in (self.ACTION_PUSH, self.ACTION_PULL, self.ACTION_PULL_PUSH):
            return message_dict

        suffix = ""
        if (self.action in (self.ACTION_PULL, self.ACTION_PULL_PUSH)
                and direct_destination and not self.location_dest_from_rule):
            suffix = _(
                "<br>The products will be moved towards <b>%(destination)s</b>, "
                "<br/> as specified from <b>%(operation)s</b> destination.",
                destination=direct_destination, operation=operation)
        if self.procure_method == self.PROCURE_MTO and self.location_src_id:
            suffix += _("<br>A need is created in <b>%s</b> and a rule will be "
                        "triggered to fulfill it.", source)
        if self.procure_method == self.PROCURE_MTS_ELSE_MTO and self.location_src_id:
            suffix += _("<br>If the products are not available in <b>%s</b>, a "
                        "rule will be triggered to bring the missing quantity "
                        "in this location.", source)
        return {
            'pull': _(
                'When products are needed in <b>%(destination)s</b>, <br> '
                '<b>%(operation)s</b> are created from <b>%(source_location)s</b> '
                'to fulfill the need. %(suffix)s',
                destination=destination, operation=operation,
                source_location=source, suffix=suffix),
            'push': _(
                'When products arrive in <b>%(source_location)s</b>, <br> '
                '<b>%(operation)s</b> are created to send them to '
                '<b>%(destination)s</b>.',
                source_location=source, operation=operation,
                destination=destination),
        }

    def _compute_action_message(self):
        """≙ ``_compute_action_message`` (``odoo19c: :194-207``).

        «Generate dynamicaly a message that describe the rule purpose to the
        end user.» Sin acción no hay mensaje — la fuente pone ``None``.
        """
        if not self.action:
            return None
        message_dict = self._get_message_dict()
        message = message_dict.get(self.action) or ""
        if self.action == self.ACTION_PULL_PUSH:
            message = message_dict['pull'] + "<br/><br/>" + message_dict['push']
        return message

    def _compute_picking_type_code_domain(self):
        """≙ ``_compute_picking_type_code_domain`` (``odoo19c: :209-211``).

        Vacío en ``stock``: son los addons que extienden la regla (``mrp``,
        ``purchase_stock``) los que acotan qué códigos admite cada acción.
        """
        return []

    # ------------------------------------------------------------------ #
    # La dirección push (≙ :212-286)                                       #
    # ------------------------------------------------------------------ #

    def _get_push_new_date(self, move):
        """≙ ``_get_push_new_date`` (``odoo19c: :212-220``).

        :param move: el movimiento que se está procesando (``stock.move``).
        :return: la fecha nueva, ya desplazada por el plazo de la regla.
        """
        return move.date + datetime.timedelta(days=self.delay)

    def _run_push(self, move):
        """≙ ``_run_push`` (``odoo19c: :222-254``).

        Aplica una regla push a un movimiento. Con ``auto='transparent'``
        reescribe el destino del movimiento existente; con ``'manual'`` crea el
        movimiento siguiente. «Care this function is not call by method run. It
        is called explicitely in stock_move.py inside the method _push_apply.»
        """
        new_date = self._get_push_new_date(move)
        if self.auto == self.AUTO_TRANSPARENT:
            old_dest_location = move.location_dest
            move.date = new_date
            move.location_dest_id = self.location_dest_id
            move.save()
            # El destino de las líneas tiene que seguir al del movimiento.
            for line in move.move_line_ids.all() if hasattr(move, 'move_line_ids') else []:
                strategy = move.location_dest._get_putaway_strategy(move.product)
                line.location_dest = strategy or move.location_dest
                line.save()
            # Evita el bucle si la regla push está mal configurada; si el
            # destino cambió, se vuelve a aplicar por si hay otro salto.
            if old_dest_location is None or old_dest_location.pk != self.location_dest_id:
                pushed = move._push_apply()
                return pushed[0] if pushed else None
            return None

        new_move_vals = self._push_prepare_move_copy_values(move, new_date)
        new_move = _create_move(new_move_vals)
        if hasattr(new_move, '_skip_push') and new_move._skip_push():
            new_move.location_dest_id = new_move_vals.get(
                'location_final_id') or new_move.location_dest_id
            new_move.save()
        if hasattr(new_move, '_should_bypass_reservation') and new_move._should_bypass_reservation():
            new_move.procure_method = self.PROCURE_MTS
            new_move.save()
        if not new_move.location.should_bypass_reservation():
            move.move_dest_ids.add(new_move) if hasattr(move, 'move_dest_ids') else None
            new_move.move_orig_ids.add(move)
        return new_move

    def _push_prepare_move_copy_values(self, move_to_copy, new_date):
        """≙ ``_push_prepare_move_copy_values`` (``odoo19c: :256-286``).

        Los valores del movimiento que continúa la cadena. Se porta entero, con
        las claves de la referencia; la proyección al modelo la hace
        ``_move_values_for_model`` (divergencia D-4).
        """
        company_id = self.company_id
        copied_quantity = move_to_copy.quantity
        final_location_id = False
        location_dest_id = self.location_dest_id

        final_location = getattr(move_to_copy, 'location_final', None)
        if final_location is not None:
            if not move_to_copy.location_dest.child_of(final_location):
                final_location_id = final_location.pk
            if final_location.child_of(self.location_dest):
                location_dest_id = final_location.pk

        if move_to_copy.product_uom_qty < Decimal('0'):
            copied_quantity = move_to_copy.product_uom_qty
        if not company_id:
            warehouse = self.warehouse
            if warehouse is not None:
                company_id = warehouse.company_id
            elif self.picking_type_id and self.picking_type.warehouse is not None:
                company_id = self.picking_type.warehouse.company_id

        return {
            'product_uom_qty': copied_quantity,
            'origin': (move_to_copy.origin if hasattr(move_to_copy, 'origin') else None)
                      or (str(move_to_copy.picking) if move_to_copy.picking_id else "/"),
            'location_id': move_to_copy.location_dest_id,
            'location_dest_id': location_dest_id,
            'location_final_id': final_location_id,
            'rule_id': self.pk,
            'date': new_date,
            'date_deadline': getattr(move_to_copy, 'date_deadline', None),
            'company_id': company_id,
            'picking_id': False,
            'picking_type_id': self.picking_type_id,
            'propagate_cancel': self.propagate_cancel,
            'warehouse_id': (self.warehouse_id
                             or move_to_copy.location_dest.warehouse_id),
            'procure_method': self.PROCURE_MTO,
        }

    # ------------------------------------------------------------------ #
    # La dirección pull (≙ :288-408)                                       #
    # ------------------------------------------------------------------ #

    @classmethod
    def _run_pull(cls, procurements):
        """≙ ``_run_pull`` (``odoo19c: :287-316``).

        Convierte cada par ``(procurement, rule)`` en un ``stock.move`` y lo
        confirma. El bucle preliminar existe por ``mts_else_mto``: la referencia
        aísla ahí los productos cuya cantidad prevista habría que leer, y
        aprovecha para exigir que la regla tenga origen.
        """
        moves_values_by_company = defaultdict(list)

        for procurement, rule in procurements:
            if not rule.location_src_id:
                msg = _('No source location defined on stock rule: %s!', rule.name)
                raise ProcurementException([(procurement, msg)])

        # Las salidas (cantidad > 0) van al final: así una entrada del mismo
        # producto ya creó su movimiento cuando la salida busca existencia.
        procurements = sorted(
            procurements,
            key=lambda proc: proc[0].product_uom.compare(proc[0].product_qty, 0.0) > 0)

        for procurement, rule in procurements:
            procure_method = rule.procure_method
            if rule.procure_method == cls.PROCURE_MTS_ELSE_MTO:
                procure_method = cls.PROCURE_MTS

            move_values = rule._get_stock_move_values(*procurement)
            move_values['procure_method'] = procure_method
            company = procurement.company_id
            key = company.pk if hasattr(company, 'pk') else company
            moves_values_by_company[key].append(move_values)

        for _company_id, moves_values in moves_values_by_company.items():
            moves = [_create_move(vals) for vals in moves_values]
            # ``_action_confirm`` dispara a su vez el grupo de aprovisionamiento.
            for move in moves:
                move._action_confirm()
        return True

    def _get_custom_move_fields(self):
        """≙ ``_get_custom_move_fields`` (``odoo19c: :318-322``).

        «The purpose of this method is to be override in order to easily add
        fields from procurement 'values' argument to move data.»
        """
        return []

    def _get_stock_move_values(self, product_id, product_qty, product_uom,
                               location_dest_id, name, origin, company_id, values):
        """≙ ``_get_stock_move_values`` (``odoo19c: :324-384``).

        Los valores con los que se crea el ``stock.move`` que satisface una
        necesidad. «This function assumes that the given procurement has a rule
        (action == 'pull' or 'pull_push') set on it.»

        Se porta **entero**, con las 22 claves de la fuente: es el contrato que
        los addons extienden vía ``_get_custom_move_fields``. La proyección
        sobre los campos que este ``StockMove`` declara ocurre en
        ``_move_values_for_model`` (divergencias D-3 y D-4).
        """
        date_planned = values['date_planned']
        if isinstance(date_planned, str):
            date_planned = datetime.datetime.fromisoformat(date_planned)
        date_scheduled = date_planned - datetime.timedelta(days=self.delay or 0)
        date_deadline = False
        if values.get('date_deadline'):
            deadline = values['date_deadline']
            if isinstance(deadline, str):
                deadline = datetime.datetime.fromisoformat(deadline)
            date_deadline = deadline - datetime.timedelta(days=self.delay or 0)

        partner = self.partner_address_id or values.get('partner_id', False)
        # Puede haber cantidad ya hecha; se crea el movimiento por lo que falta.
        qty_left = product_qty

        move_dest = values.get('move_dest_ids')
        # ``(4, x.id)`` en la fuente (``:340``) — enlazar; aquí lista de pk (D-7).
        move_dest_ids = [m.pk for m in move_dest] if move_dest else []

        # En traslados entre almacenes, los almacenes hacen de contacto.
        if move_dest_ids:
            internal_transit = getattr(company_id, 'internal_transit_location', None)
            if internal_transit is not None and location_dest_id.pk == internal_transit.pk:
                if not partner:
                    partners = {m.location_dest.warehouse_id for m in move_dest
                                if m.location_dest.warehouse_id}
                    if len(partners) == 1:
                        partner = partners.pop()
                src_warehouse = self.location_src.warehouse if self.location_src_id else None
                counterpart = (src_warehouse.partner_id if src_warehouse is not None
                               else None) or getattr(self.company, 'partner_id', None)
                for move in move_dest:
                    move.partner_id = counterpart
                    move.save()

        # Cantidad negativa = devolución.
        if product_uom.compare(product_qty, 0.0) < 0:
            values['to_refund'] = True

        move_values = {
            'company_id': (self.company_id
                           or (self.location_src.company_id if self.location_src_id else None)
                           or (self.location_dest.company_id if self.location_dest_id else None)
                           or getattr(company_id, 'pk', company_id)),
            'product_id': product_id.pk,
            'product_uom': product_uom.pk,
            'product_uom_qty': qty_left,
            'partner_id': getattr(partner, 'pk', partner),
            'location_id': self.location_src_id,
            'location_final_id': location_dest_id.pk,
            'move_dest_ids': move_dest_ids,
            'rule_id': self.pk,
            'reference_ids': [r.pk for r in values.get('reference_ids', [])],
            'procure_method': self.procure_method,
            'origin': origin,
            'name': name,
            'picking_type_id': self.picking_type_id,
            'procurement_values': self._serialize_procurement_values(values),
            'route_ids': [route.pk for route in values.get('route_ids', [])],
            'never_product_template_attribute_value_ids':
                values.get('never_product_template_attribute_value_ids'),
            'warehouse_id': self.warehouse_id,
            'date': date_scheduled,
            'date_deadline': date_deadline,
            'propagate_cancel': self.propagate_cancel,
            'priority': values.get('priority', "0"),
            'orderpoint_id': (values.get('orderpoint_id').pk
                              if values.get('orderpoint_id') else None),
        }
        if self.location_dest_from_rule:
            move_values['location_dest_id'] = self.location_dest_id
        for field in self._get_custom_move_fields():
            if field in values:
                move_values[field] = values.get(field)
        return move_values

    def _serialize_procurement_values(self, values):
        """≙ ``_serialize_procurement_values`` (``odoo19c: :386-408``).

        «Helper method to serialize procurement values for storage»: los
        registros se guardan como ids, las fechas como cadena ISO, y el resto
        tal cual.
        """
        serialized = {}
        for key, value in values.items():
            if isinstance(value, models.Model):
                serialized[key] = [value.pk]
            elif isinstance(value, (list, tuple)) and value and all(
                    isinstance(v, models.Model) for v in value):
                serialized[key] = [v.pk for v in value]
            elif isinstance(value, (datetime.datetime, datetime.date)):
                serialized[key] = value.isoformat()
            else:
                serialized[key] = value
        return serialized

    # ------------------------------------------------------------------ #
    # Plazos (≙ :410-443)                                                  #
    # ------------------------------------------------------------------ #

    @classmethod
    def _get_lead_days(cls, rules, product, **values):
        """≙ ``_get_lead_days`` (``odoo19c: :410-443``).

        «Returns the cumulative delay and its description encountered by a
        procurement going through the rules in `self`.»

        La fuente opera sobre un recordset (``self.filtered(...)``), así que
        aquí es ``classmethod`` que recibe ``rules`` — misma convención que
        ``stock_warehouse.py``.

        :return: ``(defaultdict(float), [(título, texto), …])``
        """
        delays = defaultdict(float)
        delay_description = []
        bypass_delay_description = values.get('bypass_delay_description')

        delaying_rules = [r for r in rules
                          if r.action in (cls.ACTION_PULL, cls.ACTION_PULL_PUSH) and r.delay]
        if delaying_rules:
            delays['total_delay'] += sum(r.delay for r in delaying_rules)
            if not bypass_delay_description:
                delay_description = [
                    (_('Delay on %s', rule.name), _('+ %d day(s)', rule.delay))
                    for rule in delaying_rules
                ]

        if values.get('bypass_global_horizon_days'):
            return delays, delay_description

        orderpoint_model = _orderpoint_model()
        global_horizon_days = (orderpoint_model.get_horizon_days()
                               if orderpoint_model is not None else 0)
        if global_horizon_days:
            delays['horizon_time'] += global_horizon_days
            if not bypass_delay_description:
                delay_description.append(
                    (_('Time Horizon'), _('+ %d day(s)', global_horizon_days)))
        return delays, delay_description

    # ------------------------------------------------------------------ #
    # El punto de entrada: run (≙ :445-505)                                #
    # ------------------------------------------------------------------ #

    @classmethod
    def _skip_procurement(cls, procurement):
        """≙ ``_skip_procurement`` (``odoo19c: :445-449``).

        Un servicio no se mueve, y una cantidad nula no genera movimiento.
        """
        if procurement.product_id.type != "consu":
            return True
        return float_is_zero(
            float(procurement.product_qty),
            precision_rounding=procurement.product_uom.rounding)

    @classmethod
    def run(cls, procurements, raise_user_error=True):
        """≙ ``run`` (``odoo19c: :451-505``).

        «Fulfil `procurements` with the help of stock rules.»

        Las necesidades son productos requeridos en una ubicación; para
        satisfacerlas hay que crear documentos (``stock.move`` por defecto, pero
        las extensiones de ``_run_*`` permiten crear cualquier tipo).

        :param procurements: lista de ``Procurement``.
        :param raise_user_error: si es verdadero levanta ``UserError``; si no,
            ``ProcurementException`` con todas las necesidades fallidas.
        :raises UserError: con ``raise_user_error=True`` y una necesidad no
            satisfecha.
        :raises ProcurementException: con ``raise_user_error=False``.
        """
        def raise_exception(procurement_errors):
            if raise_user_error:
                _dummy, errors = zip(*procurement_errors)
                raise UserError('\n'.join(errors))
            raise ProcurementException(procurement_errors)

        actions_to_run = defaultdict(list)
        procurement_errors = []
        for procurement in procurements:
            procurement.values.setdefault(
                'company_id', procurement.location_id.company)
            procurement.values.setdefault('priority', '0')
            procurement.values.setdefault(
                'date_planned',
                procurement.values.get('date_planned') or timezone.now())
            if cls._skip_procurement(procurement):
                continue
            rule = cls._get_rule(
                procurement.product_id, procurement.location_id, procurement.values)
            if not rule:
                error = _(
                    'No rule has been found to replenish "%(product)s" in '
                    '"%(location)s".\nVerify the routes configuration on the '
                    'product.',
                    product=str(procurement.product_id),
                    location=str(procurement.location_id))
                procurement_errors.append((procurement, error))
            else:
                action = 'pull' if rule.action == cls.ACTION_PULL_PUSH else rule.action
                actions_to_run[action].append((procurement, rule))

        if procurement_errors:
            raise_exception(procurement_errors)

        for action, action_procurements in actions_to_run.items():
            runner = getattr(cls, '_run_%s' % action, None)
            if runner is not None:
                try:
                    runner(action_procurements)
                except ProcurementException as exc:
                    procurement_errors += exc.procurement_exceptions
            else:
                _logger.error(
                    "The method _run_%s doesn't exist on the procurement rules",
                    action)

        if procurement_errors:
            raise_exception(procurement_errors)
        return True

    # ------------------------------------------------------------------ #
    # Búsqueda de la regla aplicable (≙ :507-678)                          #
    # ------------------------------------------------------------------ #

    @classmethod
    def _search_rule_for_warehouses(cls, route_ids, packaging_uom_id, product_id,
                                    warehouse_ids, domain):
        """≙ ``_search_rule_for_warehouses`` (``odoo19c: :507-532``).

        Devuelve ``{(location_dest, route): {warehouse: regla}}`` para todas las
        rutas candidatas de una vez, que es lo que evita una consulta por
        ubicación al subir el árbol.

        **Divergencia D-2:** la fuente lo resuelve con
        ``_read_group(..., aggregates=['id:recordset'], order='route_sequence:min, sequence:min')``.
        Aquí se hace con una sola consulta ordenada por ``(route_sequence,
        sequence)`` y el agrupado en Python: la primera regla de cada grupo es
        la que gana, que es el mismo desempate.
        """
        domain = domain if domain is not None else Q()
        if warehouse_ids:
            domain = expression.AND([
                domain,
                Q(warehouse__isnull=True) | Q(warehouse__in=warehouse_ids),
            ])

        valid_route_ids = set()
        if route_ids:
            valid_route_ids |= {r.pk for r in route_ids}
        if packaging_uom_id is not None and packaging_uom_id:
            packaging_routes = packaging_uom_id.package_type.route_ids.all()
            valid_route_ids |= {r.pk for r in packaging_routes}
        valid_route_ids |= {r.pk for r in product_id.route_ids.all()}
        if product_id.categ is not None:
            valid_route_ids |= {r.pk for r in product_id.categ.total_route_ids}
        if warehouse_ids:
            filter_function = partial(cls._filter_warehouse_routes, product_id, warehouse_ids)
            for warehouse in warehouse_ids:
                valid_route_ids |= {r.pk for r in warehouse.route_ids.all()
                                    if filter_function(r)}
        if valid_route_ids:
            domain = expression.AND([domain, Q(route__in=list(valid_route_ids))])

        rules = cls.objects.filter(domain).order_by('route_sequence', 'sequence', 'id')

        rule_dict = defaultdict(OrderedDict)
        for rule in rules:
            key = (rule.location_dest_id, rule.route_id)
            # La primera que llega gana: la consulta ya viene ordenada por el
            # mismo criterio que la fuente aplica con ``sorted``.
            rule_dict[key].setdefault(rule.warehouse_id, rule)
        return rule_dict

    @classmethod
    def _filter_warehouse_routes(cls, product, warehouses, route):
        """≙ ``_filter_warehouse_routes`` (``odoo19c: :534-535``).

        Devuelve la ruta tal cual. Existe como punto de extensión: los addons
        que acotan qué rutas de almacén aplican a un producto lo sobrescriben.
        """
        return route

    @classmethod
    def _search_rule(cls, route_ids, packaging_uom_id, product_id, warehouse_id, domain):
        """≙ ``_search_rule`` (``odoo19c: :537-563``).

        «First find a rule among the ones defined on the procurement group, then
        try on the routes defined for the product, finally fallback on the
        default behavior.» El orden de los cuatro intentos **es** la precedencia
        entre rutas y no se altera.
        """
        domain = domain if domain is not None else Q()
        if warehouse_id is not None and warehouse_id:
            domain = expression.AND([
                domain,
                Q(warehouse__isnull=True) | Q(warehouse=warehouse_id),
            ])

        def first_by_route(routes):
            route_pks = [r.pk for r in routes]
            if not route_pks:
                return None
            return cls.objects.filter(
                expression.AND([Q(route__in=route_pks), domain])
            ).order_by('route_sequence', 'sequence', 'id').first()

        res = None
        if route_ids:
            res = first_by_route(route_ids)
        if not res and packaging_uom_id is not None and packaging_uom_id:
            res = first_by_route(packaging_uom_id.package_type.route_ids.all())
        if not res:
            product_routes = list(product_id.route_ids.all())
            if product_id.categ is not None:
                product_routes += list(product_id.categ.total_route_ids)
            res = first_by_route(product_routes)
        if not res and warehouse_id is not None and warehouse_id:
            res = first_by_route(warehouse_id.route_ids.all())
        return res

    @classmethod
    def _get_rule(cls, product_id, location_id, values):
        """≙ ``_get_rule`` (``odoo19c: :565-639``).

        «Find a pull rule for the location_id, fallback on the parent locations
        if it could not be found.»

        Dos recorridos del árbol de ubicaciones, y el segundo es el que decide:
        el primero junta la jerarquía para pedir todas las reglas de una vez, y
        el segundo la vuelve a subir parándose en la primera regla válida.
        """
        if not location_id:
            return None

        # La jerarquía, de la ubicación a su raíz.
        locations = [location_id]
        while locations[-1].location_id:
            locations.append(locations[-1].location)

        domain = cls._get_rule_domain(locations, values)
        warehouses = values.get('warehouse_id')
        if warehouses is None:
            warehouses = [loc.warehouse for loc in locations if loc.warehouse_id]
        elif not isinstance(warehouses, (list, tuple, set)):
            warehouses = [warehouses] if warehouses else []

        rule_dict = cls._search_rule_for_warehouses(
            values.get("route_ids", False),
            values.get("packaging_uom_id", False),
            product_id,
            warehouses,
            domain,
        )

        def extract_rule(rule_dict, route_ids, warehouse_id, location_dest_id):
            """≙ la función local ``extract_rule`` (``:585-598``)."""
            rule = None
            product_route_pks = {r.pk for r in product_id.route_ids.all()}
            for route in sorted(route_ids,
                                key=lambda r: (r.pk not in product_route_pks, r.sequence)):
                sub_dict = rule_dict.get((location_dest_id.pk, route.pk))
                if not sub_dict:
                    continue
                if not warehouse_id:
                    rule = sub_dict[next(iter(sub_dict))]
                else:
                    warehouse_pk = getattr(warehouse_id, 'pk', warehouse_id)
                    rule = sub_dict.get(warehouse_pk) or sub_dict.get(None)
                if rule:
                    break
            return rule

        def get_rule_for_routes(rule_dict, route_ids, packaging_uom_id, product_id,
                                warehouse_id, location_dest_id):
            """≙ la función local ``get_rule_for_routes`` (``:600-610``)."""
            res = None
            if route_ids:
                res = extract_rule(rule_dict, route_ids, warehouse_id, location_dest_id)
            if not res and packaging_uom_id:
                res = extract_rule(rule_dict, packaging_uom_id.package_type.route_ids.all(),
                                   warehouse_id, location_dest_id)
            if not res:
                routes = list(product_id.route_ids.all())
                if product_id.categ is not None:
                    routes += list(product_id.categ.total_route_ids)
                res = extract_rule(rule_dict, routes, warehouse_id, location_dest_id)
            if not res and warehouse_id:
                res = extract_rule(rule_dict, warehouse_id.route_ids.all(),
                                   warehouse_id, location_dest_id)
            return res

        data_model = apps.get_model('base', 'IrModelData')
        result = None
        location = location_id
        inter_comp_location_checked = False
        while (not result) and location is not None:
            candidate_locations = [location]
            if not inter_comp_location_checked and cls._check_intercomp_location([location]):
                # El dominio ya incluyó la ubicación de clientes en
                # ``_get_rule_domain``; aquí se añade como candidata.
                inter_comp_location = data_model.ref(
                    XMLID_CUSTOMERS, raise_if_not_found=False)
                if inter_comp_location is not None:
                    candidate_locations.append(inter_comp_location)
                inter_comp_location_checked = True
            for candidate_location in candidate_locations:
                result = get_rule_for_routes(
                    rule_dict,
                    values.get("route_ids") or [],
                    values.get("packaging_uom_id"),
                    product_id,
                    values.get("warehouse_id", candidate_location.warehouse),
                    candidate_location,
                )
                if result:
                    break
            else:
                location = location.location
        return result

    @classmethod
    def _check_intercomp_location(cls, locations):
        """≙ ``_check_intercomp_location`` (``odoo19c: :641-645``).

        Verdadero si alguna de las ubicaciones es la de tránsito entre empresas.
        """
        if not any(loc.usage == 'transit' for loc in locations):
            return False
        data_model = apps.get_model('base', 'IrModelData')
        inter_comp_location = data_model.ref(
            XMLID_INTER_COMPANY, raise_if_not_found=False)
        return (inter_comp_location is not None
                and inter_comp_location.pk in {loc.pk for loc in locations})

    @classmethod
    def _get_rule_domain(cls, locations, values):
        """≙ ``_get_rule_domain`` (``odoo19c: :647-664``).

        El dominio con el que se buscan las reglas pull de una jerarquía.

        Si la búsqueda va hacia la ubicación entre empresas, también entra la de
        clientes: así no hay que duplicar cada regla de entrega para cubrir la
        parte inter-empresa.
        """
        location_ids = [loc.pk for loc in locations]
        data_model = apps.get_model('base', 'IrModelData')
        if cls._check_intercomp_location(locations):
            customers = data_model.ref(XMLID_CUSTOMERS, raise_if_not_found=False)
            if customers is not None:
                location_ids.append(customers.pk)

        domain = expression.AND([
            Q(location_dest__in=location_ids),
            ~Q(action=cls.ACTION_PUSH),
        ])
        # Elevado, no hay regla de registro que acote por empresa: se acota aquí.
        if is_su() and values.get('company_id'):
            company = values['company_id']
            company_ids = {getattr(company, 'pk', company)}
            if values.get('route_ids'):
                company_ids |= {r.company_id for r in values['route_ids'] if r.company_id}
            domain = expression.AND([
                domain,
                Q(company__isnull=True) | Q(company__in=list(company_ids)),
            ])
        return domain

    @classmethod
    def _get_push_rule(cls, product_id, location_dest_id, values):
        """≙ ``_get_push_rule`` (``odoo19c: :666-678``).

        «Find a push rule for the location_dest_id, with a fallback to the
        parent locations if none could be found.»
        """
        found_rule = None
        location = location_dest_id
        while (not found_rule) and location is not None:
            domain = expression.AND([
                Q(location_src=location),
                Q(action__in=(cls.ACTION_PUSH, cls.ACTION_PULL_PUSH)),
            ])
            if values.get('domain') is not None:
                domain = expression.AND([domain, values['domain']])
            found_rule = cls._search_rule(
                values.get('route_ids'), values.get('packaging_uom_id'),
                product_id, values.get('warehouse_id'), domain)
            location = location.location
        return found_rule

    # ------------------------------------------------------------------ #
    # El planificador (≙ :680-748)                                         #
    # ------------------------------------------------------------------ #

    @classmethod
    def _get_moves_to_assign_domain(cls, company_id):
        """≙ ``_get_moves_to_assign_domain`` (``odoo19c: :680-689``).

        Los movimientos que el planificador intenta reservar: confirmados o
        parcialmente disponibles, con cantidad, y cuya fecha de reserva ya
        llegó — o cuyo tipo de operación reserva al confirmar.
        """
        domain = expression.AND([
            Q(state__in=['confirmed', 'partially_available']),
            ~Q(product_uom_qty=Decimal('0.00')),
            (Q(reservation_date__lte=timezone.now().date())
             | Q(picking_type__reservation_method='at_confirm')),
        ])
        if company_id:
            domain = expression.AND([domain, Q(company=company_id)])
        return domain

    @classmethod
    def _run_scheduler_tasks(cls, use_new_cursor=False, company_id=False):
        """≙ ``_run_scheduler_tasks`` (``odoo19c: :691-724``).

        Tres tareas, en este orden: recalcular los puntos de pedido y lanzar sus
        aprovisionamientos, reservar los movimientos confirmados, y fusionar los
        quants duplicados.

        **Divergencia D-5:** la primera tarea necesita
        ``stock.warehouse.orderpoint``, que no está portado; el bloque registra
        un ``warning`` nombrando el modelo ausente. Los puntos de
        ``_commit_progress`` de la fuente —la barra de progreso del cliente
        Odoo— quedan como ``debug``: ``ir.cron`` no expone ese contador aquí.
        """
        move_model = apps.get_model('stock', 'StockMove')
        quant_model = apps.get_model('stock', 'StockQuant')

        if use_new_cursor:
            _logger.debug('stock.rule: %s tareas de planificador por hacer',
                          cls._get_scheduler_tasks_to_do())

        # 1. Puntos de pedido.
        orderpoint_model = _orderpoint_model()
        if orderpoint_model is not None:
            domain = cls._get_orderpoint_domain(company_id=company_id)
            orderpoints = orderpoint_model.objects.filter(domain)
            orderpoint_model._compute_qty_to_order_computed(orderpoints)
            orderpoint_model._compute_deadline_date(orderpoints)
            orderpoint_model._procure_orderpoint_confirm(
                orderpoints, use_new_cursor=use_new_cursor,
                company_id=company_id, raise_user_error=False)

        # 2. Reservar lo confirmado, en lotes de 1000.
        domain = cls._get_moves_to_assign_domain(company_id)
        moves_to_assign = move_model.objects.filter(domain).order_by(
            'reservation_date', '-priority', 'date', 'id'
        ) if _has_field(move_model, 'reservation_date') else move_model.objects.filter(
            domain).order_by('id')
        for moves_chunk in split_every(1000, list(moves_to_assign.values_list('pk', flat=True))):
            for move in move_model.objects.filter(pk__in=moves_chunk):
                move._action_assign()
            if use_new_cursor:
                _logger.info("A batch of %d moves are assigned and committed",
                             len(moves_chunk))

        # 3. Fusionar quants duplicados.
        quant_model._quant_tasks()

    @classmethod
    def _get_scheduler_tasks_to_do(cls):
        """≙ ``_get_scheduler_tasks_to_do`` (``odoo19c: :726-730``).

        «Number of task to be executed by the stock scheduler. This number will
        be given in log message to know how many tasks succeeded.»
        """
        return 3

    @classmethod
    def run_scheduler(cls, use_new_cursor=False, company_id=False):
        """≙ ``run_scheduler`` (``odoo19c: :732-742``).

        «Call the scheduler in order to check the running procurements, to check
        the minimum stock rules and the availability of moves.» Pensado para
        correr sobre todas las empresas a la vez, por eso la fuente lo eleva.
        """
        try:
            cls._run_scheduler_tasks(use_new_cursor=use_new_cursor,
                                     company_id=company_id)
        except Exception:
            _logger.error("Error during stock scheduler", exc_info=True)
            raise
        return {}

    @classmethod
    def _get_orderpoint_domain(cls, company_id=False):
        """≙ ``_get_orderpoint_domain`` (``odoo19c: :744-748``).

        Sólo los puntos de pedido automáticos de productos activos.
        """
        domain = expression.AND([Q(trigger='auto'), Q(product__active=True)])
        if company_id:
            domain = expression.AND([domain, Q(company=company_id)])
        return domain


def _has_field(model, name):
    """¿El modelo declara este campo? — usado por ``_run_scheduler_tasks``.

    No es un símbolo de la referencia: en Odoo ``reservation_date`` siempre
    existe en ``stock.move``. Aquí ``StockMove`` es todavía un esbozo, así que
    el orden del planificador se degrada a ``id`` mientras el campo no esté.
    Sucesor: la tarea **#330** (``stock_move.py``).
    """
    return any(f.name == name for f in model._meta.get_fields())


__all__ = ['Procurement', 'ProcurementException', 'StockRule']
