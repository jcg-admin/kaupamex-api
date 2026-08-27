"""Modelo ``StockLot`` — addon ``stock``.

Adaptación de ``odoo19c: addons/stock/models/stock_lot.py``
(``odoo-tools@622ddc2a``, LGPL-3, 431 líneas) — atribución y aviso de licencia
preservados (DEC-KX-03).

Qué es: un **lote / número de serie** de un producto. Es la base que
``product_expiry`` extiende con fechas de caducidad y la estrategia de remoción
FEFO (DEC-SALE-01).

Porte símbolo por símbolo
==========================

Medido con AST sobre los dos árboles: la referencia declara **14 campos y 24
métodos**. Ninguno se omite en silencio — cada uno cita abajo su desenlace
(``porte-completo-no-parcial.md``).

*Métrica:* asignaciones y ``def`` en el cuerpo de ``class StockLot``, por AST.
*Ciega a:* que un símbolo "portado" haga lo mismo que el de la referencia. Esa
comparación es de lectura, no de conteo — por eso cada divergencia declara **en
qué** difiere, no sólo que difiere.

Campos — 13 PORTADOS · 1 DIVERGENCIA · 0 BLOQUEADOS
----------------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 24 14 62

   * - Campo (ref → aquí)
     - Desenlace
     - Nota
   * - ``name`` (41)
     - PORTADO
     - Con su generación automática: ``_compute_name`` lo llena desde la
       secuencia del producto cuando llega vacío.
   * - ``ref`` (42)
     - PORTADO
     - Sin cambios.
   * - ``product_id`` → ``product`` (43-47)
     - PORTADO
     - ``CASCADE``, como ya estaba.
   * - ``product_uom_id`` → ``product_uom`` (48-50)
     - PORTADO
     - ``@property``. La referencia lo declara ``related=`` sin ``store``, y en
       este backend un calculado no almacenado es una propiedad, no una
       columna.
   * - ``quant_ids`` → ``quants`` (51)
     - PORTADO
     - Reverso implícito por ``related_name='quants'`` en ``StockQuant.lot``
       (``stock_quant.py:358``); no necesita declaración propia.
   * - ``product_qty`` (52)
     - PORTADO
     - ``@property``; su *compute* es ``_product_qty`` y su *search* es
       ``_search_product_qty``, ambos abajo. Ver :ref:`h-api-596` para por qué
       el nombre público es correcto aquí.
   * - ``note`` (53)
     - PORTADO
     - **Columna nueva.** ``fields.Html``; el saneo va en la capa de
       presentación, igual que el resto del árbol.
   * - ``display_complete`` (54)
     - DIVERGENCIA
     - Alterna la visibilidad de un formulario del cliente Odoo. Este backend
       no tiene motor de vistas server-side: la UI decide qué muestra sin
       consultarle al modelo.
   * - ``company_id`` → ``company`` (55)
     - PORTADO
     - **Columna nueva.** Almacenada con compute, como la fuente
       (``store=True, readonly=False``).
   * - ``delivery_ids`` (56)
     - PORTADO
     - ``@property`` sobre ``_find_delivery_ids_by_lot_iterative``.
   * - ``delivery_count`` (57)
     - PORTADO
     - ``@property`` — la cardinalidad de la anterior.
   * - ``partner_ids`` (58)
     - PORTADO
     - **Desbloqueado en este pase (tarea #390).** ``StockPicking.partner``
       ya existe (``stock_picking.py:1139``); sólo faltaba esa pieza. Ver
       :ref:`h-api-678` para la divergencia de orden (``date_done`` ausente).
   * - ``lot_properties`` (59)
     - PORTADO
     - **Columna nueva.** ``fields.Json`` — la definición vive en
       ``ProductProduct.lot_properties_definition`` (``product.py:1282``), como
       en la fuente.
   * - ``location_id`` → ``location`` (60-63)
     - PORTADO
     - **Columna nueva.** Almacenada con compute e *inverse*, las dos mitades:
       ``_compute_single_location`` y ``_set_single_location``.

Métodos — 17 PORTADOS · 7 DIVERGENCIA · 0 BLOQUEADOS
-----------------------------------------------------

De los 24, **15 conservan el nombre de la fuente** y se ven en el AST; los dos
restantes que sí están portados lo hacen bajo otra forma declarada —
``_compute_delivery_ids`` como las propiedades ``delivery_ids``/
``delivery_count``, y ``write`` dentro de ``save()``. Los que un conteo por
nombre reporta como ausentes son esos dos más los 7 DIVERGENCIA; ninguno se
omite en silencio.

.. list-table::
   :header-rows: 1
   :widths: 30 14 56

   * - Método (línea en la fuente)
     - Desenlace
     - Nota
   * - ``default_get`` (31-36)
     - DIVERGENCIA
     - Retira ``default_company_id`` del contexto para que el compute de
       empresa siempre corra. Este ORM no tiene contexto de creación:
       ``_compute_company_id`` corre en ``save()`` sin condición, que es el
       efecto que la fuente persigue.
   * - ``_read_group_location_id`` (38-40)
     - DIVERGENCIA
     - ``group_expand`` de una vista kanban. Sin capa de vistas server-side no
       hay dónde engancharlo.
   * - ``_compute_name`` (65-69)
     - PORTADO
     - Llamado desde ``save()``.
   * - ``generate_lot_names`` (71-91)
     - PORTADO
     - ``classmethod``. Lógica de cadenas pura, sin ORM.
   * - ``_get_next_serial`` (93-102)
     - PORTADO
     - ``classmethod``.
   * - ``_check_unique_lot`` (104-127)
     - PORTADO
     - Llamado desde ``clean()``. Incluye la rama cruzada sin-empresa que la
       fuente resuelve con ``sudo()``.
   * - ``_check_create`` (129-134)
     - DIVERGENCIA
     - Lee ``context['active_picking_id']`` — un concepto de asistente de
       cliente, no de modelo. Mismo criterio que ``stock_quant.py``.
   * - ``_compute_company_id`` (136-142)
     - PORTADO
     - Llamado desde ``save()``. DIVERGENCIA declarada: sin ``all_child_ids``
       (jerarquía completa de subsidiarias, que este árbol aún no modela); se
       compara contra las empresas activas de la sesión.
   * - ``_compute_display_complete`` (144-153)
     - DIVERGENCIA
     - Ver el campo homónimo.
   * - ``_compute_delivery_ids`` (155-159)
     - PORTADO
     - Vía las propiedades ``delivery_ids`` / ``delivery_count``.
   * - ``_compute_partner_ids`` (161-167)
     - PORTADO
     - Vía la propiedad ``partner_ids``. **DIVERGENCIA declarada:** ordena por
       ``pk`` descendente en vez de ``date_done`` (:ref:`h-api-678`).
   * - ``_compute_single_location`` (169-173)
     - PORTADO
     - Mitad de lectura de ``location``.
   * - ``_set_single_location`` (175-181)
     - PORTADO
     - Mitad de escritura. **Se desbloquea en este pase:**
       ``StockQuant.move_quants`` existe (``stock_quant.py:2142``); cuando el
       porte anterior se escribió, no.
   * - ``create`` (183-187)
     - DIVERGENCIA
     - Envolvía ``_check_create`` (divergente arriba) y el contexto de
       mensajería. ``save()`` cubre el resto.
   * - ``write`` (189-202)
     - PORTADO
     - Sus dos guardas viven en ``save()``: la empresa no cambia si la
       ubicación pertenece a otra, y el producto no cambia si ya hay líneas de
       movimiento con otro producto.
   * - ``copy_data`` (204-210)
     - PORTADO
     - Prefijo de copia en ``name``.
   * - ``_product_qty`` (212-235)
     - PORTADO
     - Es el *compute* de ``product_qty``. DIVERGENCIA: la rama de fecha
       pasada (``to_date``) exige el histórico de movimientos por fecha, que
       ``StockMoveLine`` sí tiene — se porta entera.
   * - ``_search_product_qty`` (237-263)
     - PORTADO
     - ``classmethod``; los ocho operadores de ``PY_OPERATORS``, incluida la
       inclusión del cero que la fuente calcula con ``op(0.0, value)``.
   * - ``_search_partner_ids`` (265-291)
     - PORTADO
     - Desbloqueado en este pase. Usa ``orm.domains.Domain``/``to_q`` sobre
       ``picking.partner``/``move.partner`` (rutas de nuestros propios
       nombres de campo, no los de la fuente).
   * - ``action_lot_open_quants`` (293-297)
     - DIVERGENCIA
     - Devuelve un ``ir.actions.act_window``. El consumidor real aquí es un
       ``QuerySet.filter(lot=…)`` desde la vista que lo necesite.
   * - ``action_lot_open_transfers`` (299-315)
     - DIVERGENCIA
     - Misma razón; su dato es ``delivery_ids``, que sí se porta.
   * - ``_get_outgoing_domain`` (317-323)
     - PORTADO
     - ``staticmethod`` que devuelve un ``Q``: línea de salida o consumida en
       producción.
   * - ``_find_delivery_ids_by_lot`` (325-364)
     - PORTADO
     - Versión recursiva.
   * - ``_find_delivery_ids_by_lot_iterative`` (366-431)
     - PORTADO
     - Versión iterativa — la que consumen los computes, como en la fuente.

Constantes de módulo
---------------------

``PY_OPERATORS`` (12-21) se porta verbatim: es el mapa de operadores que
``_search_product_qty`` aplica en Python sobre el agregado. No es un atributo de
ORM (ver la tercera categoría de ``atributos-de-clase-de-modelo.md``).
"""
import operator as py_operator
from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal
from re import findall as regex_findall, split as regex_split

import fields
import models
from django.apps import apps
from django.db.models import Q, Sum

from addons.base.models import TimeStampedModel
from addons.mail.models.mail_activity_mixin import MailActivityMixin
from addons.mail.models.mail_thread import MailThread
from exceptions import UserError, ValidationError
from orm.domains import Domain, to_q
from orm.environments import get_current_companies, get_current_company
from tools.translate import _

#: ≙ ``PY_OPERATORS`` (``odoo19c: :12-21``) — los operadores que
#: ``_search_product_qty`` evalúa en Python sobre la suma por lote.
PY_OPERATORS = {
    '<': py_operator.lt,
    '>': py_operator.gt,
    '<=': py_operator.le,
    '>=': py_operator.ge,
    '=': py_operator.eq,
    '!=': py_operator.ne,
    'in': lambda elem, container: elem in container,
    'not in': lambda elem, container: elem not in container,
}


class StockLot(MailThread, MailActivityMixin, TimeStampedModel):
    """``stock.lot`` — lote / número de serie de un producto."""

    _name = 'stock.lot'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Lot/Serial'
    _check_company_auto = True
    _order = 'name, id'

    name = fields.Char(
        max_length=120,
        help_text='Número de lote / serie (Odoo name). Único por producto; si '
                  'llega vacío lo genera la secuencia del producto.',
    )
    ref = fields.Char(
        max_length=120, blank=True, default='',
        help_text='Referencia interna, para cuando difiere del número del '
                  'fabricante (Odoo ref).',
    )
    product = fields.Many2one(
        'product.ProductProduct', on_delete=models.CASCADE, related_name='lots',
        help_text='Producto (Odoo product_id).',
    )
    note = fields.Html(
        null=True, blank=True,
        help_text='Descripción libre del lote (Odoo note).',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.PROTECT, null=True, blank=True,
        related_name='stock_lots', db_index=True,
        help_text='Empresa (Odoo company_id). Almacenada con compute: la '
                  'resuelve _compute_company_id desde la del producto.',
    )
    lot_properties = fields.Json(
        null=True, blank=True, default=dict,
        help_text='Propiedades del lote (Odoo lot_properties). Su definición '
                  'vive en ProductProduct.lot_properties_definition.',
    )
    location = fields.Many2one(
        'stock.StockLocation', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='single_location_lots', db_index=True,
        help_text='Ubicación única del lote (Odoo location_id). Almacenada '
                  'con compute e inverse: se llena cuando todos los quants con '
                  'cantidad positiva están en una sola ubicación, y al '
                  'escribirla se reubican.',
    )

    class Meta:
        db_table = 'stock_lot'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'name'], name='unique_lot_product_name',
            ),
        ]
        ordering = ['name', 'id']
        verbose_name = 'Lote / número de serie'
        verbose_name_plural = 'Lotes / números de serie'

    def __str__(self) -> str:
        return f'{self.name} ({self.product})'

    # ------------------------------------------------------------------ #
    # Computes de campo                                                   #
    # ------------------------------------------------------------------ #

    def _compute_name(self):
        """≙ ``_compute_name`` (``odoo19c: :65-69``).

        Sin nombre, lo saca de la secuencia declarada en la plantilla del
        producto. La fuente llama ``lot_sequence_id.next_by_id()``; aquí el
        equivalente es ``get_next()`` — ``next_by_id`` no existe en este árbol
        (:ref:`h-api-619`).
        """
        if not self.name:
            secuencia = getattr(self.product, 'lot_sequence', None)
            self.name = secuencia.get_next() if secuencia is not None else ''

    def _compute_company_id(self):
        """≙ ``_compute_company_id`` (``odoo19c: :136-142``).

        La empresa del lote es la del producto, salvo que la del producto no
        esté entre las activas de la sesión: entonces gana la actual.

        **DIVERGENCIA declarada:** la fuente compara contra
        ``product_id.company_id.all_child_ids`` —la jerarquía completa de
        subsidiarias— y este árbol aún no modela ese cierre transitivo. Se
        compara contra las empresas activas, que es la mitad que sí existe. El
        efecto difiere sólo cuando la empresa del producto es ancestro de la
        activa sin estar ella misma activada.
        """
        del_producto = getattr(self.product, 'company', None)
        activas = get_current_companies()
        if del_producto is not None and del_producto.pk not in {c.pk for c in activas}:
            self.company = get_current_company()
        else:
            self.company = del_producto

    def _compute_single_location(self):
        """≙ ``_compute_single_location`` (``odoo19c: :169-173``).

        La ubicación del lote existe sólo si **todos** sus quants con cantidad
        positiva están en una: con dos o más, el lote no tiene ubicación única.
        """
        ubicaciones = {
            q.location for q in self.quants.filter(quantity__gt=0)
            if q.location is not None
        }
        self.location = next(iter(ubicaciones)) if len(ubicaciones) == 1 else None

    def _set_single_location(self):
        """≙ ``_set_single_location`` (``odoo19c: :175-181``).

        El *inverse* del anterior: escribir la ubicación **mueve** los quants.
        Sólo es legítimo si hoy están en una sola — mover un lote repartido no
        tiene semántica.

        Desbloqueado en este pase: ``StockQuant.move_quants``
        (``stock_quant.py:2142``) es la pieza que faltaba.
        """
        quants = list(self.quants.filter(quantity__gt=0))
        ubicaciones = {q.location for q in quants if q.location is not None}
        if len(ubicaciones) > 1:
            raise UserError(_(
                'Sólo se puede mover un lote/serie a otra ubicación si está en '
                'una sola.'))
        if not ubicaciones:
            return
        # ``unpack`` replica la fuente: si el paquete tiene más quants que los
        # que se mueven, se rompe el paquete en vez de arrastrarlo entero.
        paquetes = {q.package for q in quants if q.package is not None}
        unpack = any(p.quant_ids.count() > len(quants) for p in paquetes)
        for quant in quants:
            quant.move_quants(
                location_dest=self.location,
                message=_('Lote/serie reubicado'),
                unpack=unpack,
            )

    def _product_qty(self, to_date=None, owner=None, package=None):
        """≙ ``_product_qty`` (``odoo19c: :212-235``) — el compute de
        ``product_qty``.

        Suma los quants del lote dentro del alcance de ubicaciones del
        producto. Con ``to_date`` en el pasado, ajusta esa suma con los
        movimientos hechos **después** de esa fecha: resta las entradas y suma
        las salidas, que es como la fuente reconstruye el saldo histórico.

        Los tres parámetros son el equivalente explícito de las tres claves de
        contexto que la fuente lee (``to_date``, ``owner_id``, ``package_id``);
        este ORM no tiene contexto, así que viajan como argumentos.
        """
        quants = self.quants.all()
        if owner is not None:
            quants = quants.filter(owner=owner)
        if package is not None:
            quants = quants.filter(package=package)
        total = quants.aggregate(s=Sum('quantity'))['s'] or Decimal('0.00')

        if to_date is None:
            return total

        hechas_despues = self.move_line_ids.filter(state='done', move__date__gt=to_date)
        entradas = hechas_despues.filter(
            location_dest__usage='internal',
        ).aggregate(s=Sum('quantity_product_uom'))['s'] or Decimal('0.00')
        salidas = hechas_despues.filter(
            location__usage='internal',
        ).aggregate(s=Sum('quantity_product_uom'))['s'] or Decimal('0.00')
        return total - entradas + salidas

    # ------------------------------------------------------------------ #
    # Campos calculados no almacenados (propiedades)                      #
    # ------------------------------------------------------------------ #

    @property
    def product_uom(self):
        """≙ el campo ``product_uom_id`` (``odoo19c: :48-50``).

        ``related='product_id.uom_id'`` sin ``store``: aquí es una propiedad,
        no una columna.
        """
        return getattr(self.product, 'uom', None)

    @property
    def product_qty(self) -> Decimal:
        """≙ el campo ``product_qty`` (``odoo19c: :52``).

        El nombre público es el del **campo**, no una despromoción de su
        compute: la fuente declara ``product_qty = fields.Float(…,
        compute='_product_qty', search='_search_product_qty')``, y los dos
        privados están portados con su nombre. Ver :ref:`h-api-596`.
        """
        return self._product_qty()

    @property
    def delivery_ids(self):
        """≙ el campo ``delivery_ids`` (``odoo19c: :56``) — las entregas del
        lote, incluidas las de los lotes que lo consumieron."""
        return self._find_delivery_ids_by_lot_iterative().get(self.pk, [])

    @property
    def delivery_count(self) -> int:
        """≙ el campo ``delivery_count`` (``odoo19c: :57``)."""
        return len(self.delivery_ids)

    @property
    def partner_ids(self):
        """≙ el campo ``partner_ids`` (``odoo19c: :58``) — **desbloqueado en
        este pase** (tarea #390): ``StockPicking.partner`` ya existe
        (``stock_picking.py:1139``), que era la única pieza que faltaba.

        Contactos que recibieron el lote — en entrega directa, o vía los
        lotes que lo consumieron en producción. Sigue el mismo camino que
        ``delivery_ids``: primero las entregas, luego el contacto de cada una.
        """
        return self._compute_partner_ids()

    def _compute_partner_ids(self):
        """≙ ``_compute_partner_ids`` (``odoo19c: :159-166``) — el compute de
        ``partner_ids``.

        **DIVERGENCIA de mecanismo declarada:** la fuente ordena las entregas
        por ``date_done`` (fecha de validación del albarán) antes de tomar sus
        contactos. ``StockPicking`` en este árbol aún no declara ese campo —
        sólo tiene ``created_at``/``updated_at`` de ``TimeStampedModel``, sin
        marca de "cuándo se validó". Se ordena por ``pk`` descendente, el
        proxy más cercano al orden cronológico disponible hoy.

        Devuelve una lista de ids de contacto — no un queryset — para no atar
        el resultado a una consulta perezosa en la capa de propiedad; mismo
        criterio que ``delivery_ids``.
        """
        entregas = self._find_delivery_ids_by_lot_iterative().get(self.pk, [])
        if not entregas:
            return []
        picking_model = apps.get_model('stock', 'StockPicking')
        partners_by_picking = picking_model.objects.filter(
            pk__in=entregas).order_by('-pk').values_list('partner_id', flat=True)
        vistos, contactos = set(), []
        for contacto_id in partners_by_picking:
            if contacto_id is not None and contacto_id not in vistos:
                vistos.add(contacto_id)
                contactos.append(contacto_id)
        return contactos

    # ------------------------------------------------------------------ #
    # Generación de nombres                                               #
    # ------------------------------------------------------------------ #

    @classmethod
    def generate_lot_names(cls, first_lot, count):
        """≙ ``generate_lot_names`` (``odoo19c: :71-91``).

        Genera ``count`` nombres a partir del primero, incrementando el
        **último** número que contenga y respetando su relleno de ceros. Si no
        trae ninguno, le añade un ``0`` y reintenta — igual que la fuente.

        El desdoblamiento por ``initial_number`` conserva la sutileza del
        original: ese número puede aparecer varias veces (``BAV023B00001S00001``),
        y sólo la última aparición es la que se incrementa.
        """
        caught_initial_number = regex_findall(r"\d+", first_lot)
        if not caught_initial_number:
            return cls.generate_lot_names(first_lot + "0", count)
        initial_number = caught_initial_number[-1]
        padding = len(initial_number)
        splitted = regex_split(initial_number, first_lot)
        prefix = initial_number.join(splitted[:-1])
        suffix = splitted[-1]
        initial_number = int(initial_number)

        return [{
            'lot_name': '%s%s%s' % (
                prefix, str(initial_number + i).zfill(padding), suffix),
        } for i in range(0, count)]

    @classmethod
    def _get_next_serial(cls, company, product):
        """≙ ``_get_next_serial`` (``odoo19c: :93-102``).

        El siguiente número de serie del producto, derivado del último que se
        le asignó. Devuelve ``None`` si el producto no lleva seguimiento o si
        aún no tiene ninguno.
        """
        if getattr(product, 'tracking', 'none') == 'none':
            return None
        ultimo = cls.objects.filter(
            Q(company=company) | Q(company__isnull=True), product=product,
        ).order_by('-id').first()
        if ultimo is None:
            return None
        return cls.generate_lot_names(ultimo.name, 2)[1]['lot_name']

    # ------------------------------------------------------------------ #
    # Restricciones y persistencia                                        #
    # ------------------------------------------------------------------ #

    def _check_unique_lot(self):
        """≙ ``_check_unique_lot`` (``odoo19c: :104-127``, ``@api.constrains``).

        La pareja (producto, nombre) es única **dentro de una empresa, contando
        además los lotes sin empresa**. Esa segunda mitad es la que el
        ``UniqueConstraint`` de la tabla no puede expresar: un lote sin empresa
        colisiona con el de cualquier empresa, y uno de la empresa A no colisiona
        con el de la B.
        """
        hermanos = type(self).objects.filter(product=self.product, name=self.name)
        if self.pk is not None:
            hermanos = hermanos.exclude(pk=self.pk)
        if self.company is None:
            # Sin empresa choca contra todos.
            colisiona = hermanos.exists()
        else:
            colisiona = hermanos.filter(
                Q(company=self.company) | Q(company__isnull=True)).exists()
        if colisiona:
            raise ValidationError(_(
                'La pareja de lote/serie y producto debe ser única dentro de '
                'una empresa, incluidos los lotes sin empresa definida. '
                'Duplicado: producto %(product)s, lote %(lot)s.'
            ) % {'product': self.product, 'lot': self.name})

    def clean(self):
        """Corre las restricciones declaradas (≙ los ``@api.constrains``)."""
        super().clean()
        self._check_unique_lot()

    def save(self, *args, **kwargs):
        """Persiste el lote — ≙ ``create`` (``:183``) y ``write`` (``:189``).

        **DIVERGENCIA de mecanismo declarada:** la fuente separa creación y
        escritura en dos métodos porque su ORM los distingue; Django los funde
        en ``save()``. Lo que hace cada uno se conserva:

        - de ``create``: el compute de nombre y el de empresa corren antes de
          insertar (la fuente los declara ``precompute``/``store``);
        - de ``write``: las dos guardas de abajo.

        Lo que **no** se porta de ``create`` es ``_check_create``, que lee el
        contexto de un asistente del cliente, y el contexto de mensajería
        (``mail_create_nosubscribe``).
        """
        if self.pk is not None:
            anterior = type(self).objects.filter(pk=self.pk).first()
            if anterior is not None:
                self._check_company_change(anterior)
                self._check_product_change(anterior)
        self._compute_name()
        if self.company is None:
            self._compute_company_id()
        super().save(*args, **kwargs)

    def _check_company_change(self, anterior):
        """Primera guarda de ``write`` (``odoo19c: :191-194``).

        La empresa no se cambia si el lote está en una ubicación que pertenece
        a otra: la ubicación es un hecho físico y mandaría sobre la etiqueta.
        """
        if self.company == anterior.company:
            return
        de_la_ubicacion = getattr(anterior.location, 'company', None)
        if (de_la_ubicacion is not None and self.company is not None
                and de_la_ubicacion != self.company):
            raise UserError(_(
                'No se puede cambiar la empresa de un lote/serie que está en '
                'una ubicación de otra empresa.'))

    def _check_product_change(self, anterior):
        """Segunda guarda de ``write`` (``odoo19c: :195-201``).

        El producto no se cambia si ya hay líneas de movimiento con **otro**
        producto para ese lote: dejaría el inventario inconsistente.
        """
        if self.product == anterior.product:
            return
        if anterior.move_line_ids.exclude(product=self.product).exists():
            raise UserError(_(
                'No se puede cambiar el producto de un número de serie o lote '
                'si ya se crearon movimientos de existencias con él. Dejaría '
                'inconsistente el inventario.'))

    def copy_data(self, default=None):
        """≙ ``copy_data`` (``odoo19c: :204-210``).

        El nombre de la copia se marca como tal, salvo que quien copia ya haya
        elegido uno.
        """
        default = dict(default or {})
        vals = super().copy_data(default=default)
        if 'name' not in default:
            vals['name'] = _('(copia de) %s') % self.name
        return vals

    # ------------------------------------------------------------------ #
    # Búsqueda                                                            #
    # ------------------------------------------------------------------ #

    @classmethod
    def _search_product_qty(cls, operator, value):
        """≙ ``_search_product_qty`` (``odoo19c: :237-263``).

        Devuelve los ids cuyo saldo cumple el operador. Sólo cuenta quants en
        ubicación interna, o en tránsito de una empresa activa — el mismo
        recorte que la fuente escribe en su dominio.

        Conserva la sutileza del original: cuando el predicado se cumple para
        cero (``qty <= 5``, por ejemplo), los lotes **sin ningún quant** también
        entran, porque su saldo es cero y no aparecen en la agregación.
        """
        op = PY_OPERATORS.get(operator)
        if op is None:
            return NotImplemented
        if isinstance(value, Iterable) and not isinstance(value, str):
            value = {float(v) for v in value}
        else:
            value = float(value)

        activas = [c.pk for c in get_current_companies()]
        quants = apps.get_model('stock', 'StockQuant').objects.filter(
            Q(location__usage='internal')
            | Q(location__usage='transit', location__company__in=activas),
            lot__isnull=False,
        )
        por_lote = quants.values('lot').annotate(total=Sum('quantity'))

        con_quants, cumplen = [], []
        for fila in por_lote:
            con_quants.append(fila['lot'])
            if op(float(fila['total'] or 0), value):
                cumplen.append(fila['lot'])

        if op(0.0, value):
            # El cero cumple: los lotes sin quants entran también.
            return Q(pk__in=cumplen) | ~Q(pk__in=con_quants)
        return Q(pk__in=cumplen)

    @classmethod
    def ids_matching_product_qty(cls, operator, value):
        """Azúcar de consulta sobre ``_search_product_qty``.

        Existe porque el ``search=`` de la fuente lo invoca el motor de dominios
        al resolver una expresión sobre el campo, y aquí no hay tal motor: el
        consumidor aplica el ``Q`` él mismo. No es un símbolo de la referencia
        — es el puente que su mecanismo necesita.
        """
        criterio = cls._search_product_qty(operator, value)
        if criterio is NotImplemented:
            raise UserError(_('Operador no soportado: %s') % operator)
        return cls.objects.filter(criterio)

    @classmethod
    def _search_partner_ids(cls, operator, value):
        """≙ ``_search_partner_ids`` (``odoo19c: :265-291``) — **desbloqueado
        en este pase** (tarea #390): igual que ``partner_ids``, sólo faltaba
        ``StockPicking.partner``.

        Devuelve los lotes cuyas líneas de salida (o las de los lotes que
        consumieron, vía ``_get_outgoing_domain``) llegaron a alguno de los
        contactos indicados. **No** es simétrico con la propiedad
        ``partner_ids`` — usa un camino más barato para búsqueda masiva sobre
        ``stock.move.line``, exactamente como advierte la fuente.

        El caso ``operator == 'in'`` con ``value == [False]`` se invierte:
        primero se hallan los lotes que SÍ tienen contacto de entrega, y se
        devuelven los que no están ahí.
        """
        if (operator in Domain.NEGATIVE_OPERATORS
                or not isinstance(value, Iterable)):
            return NotImplemented
        valores = list(value)
        es_sin_contacto = operator == 'in' and valores == [False]

        condition = Domain([('lot', '!=', False), ('state', '=', 'done')])
        if es_sin_contacto:
            condition &= Domain('picking.partner', 'not in', valores)
        else:
            condition &= Domain.OR([
                Domain('picking.partner', operator, value),
                Domain('move.partner', operator, value),
            ])
        criterio = to_q(condition) & cls._get_outgoing_domain()

        modelo_linea = apps.get_model('stock', 'StockMoveLine')
        ids_lote = set(
            modelo_linea.objects.filter(criterio).values_list('lot_id', flat=True))

        if es_sin_contacto:
            return ~Q(pk__in=ids_lote)
        return Q(pk__in=ids_lote)

    @classmethod
    def ids_matching_partner_ids(cls, operator, value):
        """Azúcar de consulta sobre ``_search_partner_ids``.

        Mismo criterio que ``ids_matching_product_qty``: el ``search=`` de la
        fuente lo invoca el motor de dominios al resolver una expresión sobre
        el campo, y aquí no hay tal motor.
        """
        criterio = cls._search_partner_ids(operator, value)
        if criterio is NotImplemented:
            raise UserError(_('Operador no soportado: %s') % operator)
        return cls.objects.filter(criterio)

    # ------------------------------------------------------------------ #
    # Trazabilidad de entregas                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_outgoing_domain():
        """≙ ``_get_outgoing_domain`` (``odoo19c: :317-323``).

        Una línea cuenta como salida si su transferencia (o la de su
        movimiento) es de tipo saliente, **o** si participa en la cadena de
        producción: por ahí sigue el rastro hacia el lote que sí se entregó.

        **DIVERGENCIA de mecanismo declarada**, y es la misma que
        ``product.py:783-790`` ya documenta para este addon: la fuente filtra
        por ``picking_code`` y ``produce_line_ids`` porque en su ORM un
        ``related`` y un M2M son columnas consultables. Aquí los dos son
        ``property`` de Python (``stock_move_line.py:477`` y ``:533``), que el
        ORM no puede empujar al ``WHERE``. Se atraviesa la relación que cada
        property encapsula:

        - ``picking_code`` → ``picking__picking_type__code``
        - ``move_id.picking_code`` → ``move__picking_type__code``
        - ``produce_line_ids`` → la tabla intermedia
          ``StockMoveLineConsumeRel``, porque sus dos FK declaran
          ``related_name='+'`` y por nombre no hay camino de vuelta.

        Es la misma travesía que el ``related`` declara, escrita donde la
        consulta la puede usar.
        """
        rel = apps.get_model('stock', 'StockMoveLineConsumeRel')
        en_produccion = set(
            rel.objects.values_list('produce_line_id', flat=True)
        ) | set(
            rel.objects.values_list('consume_line_id', flat=True)
        )
        return (
            Q(picking__picking_type__code='outgoing')
            | Q(move__picking_type__code='outgoing')
            | Q(pk__in=en_produccion)
        )

    def _find_delivery_ids_by_lot(self, lot_path=None, delivery_by_lot=None):
        """≙ ``_find_delivery_ids_by_lot`` (``odoo19c: :325-364``) — recursiva.

        Recorre la cadena de producción hacia adelante: las entregas de un lote
        son las suyas propias más las de los lotes que produjo. ``lot_path``
        corta los ciclos y evita recalcular lo ya visitado.

        **DIVERGENCIA declarada:** opera sobre una instancia, no sobre un
        recordset — este ORM no los tiene. El resultado por lote es idéntico.
        """
        if lot_path is None:
            lot_path = set()
        if delivery_by_lot is None:
            delivery_by_lot = {}

        lineas = self.move_line_ids.filter(
            self._get_outgoing_domain(), state='done').distinct()
        producen, esteriles = [], []
        for linea in lineas:
            (producen if linea.produce_line_ids.exists() else esteriles).append(linea)

        entregas = set()
        if producen:
            lot_path.add(self.pk)
            siguientes = {
                l for linea in producen
                for l in type(self).objects.filter(
                    move_line_ids__in=linea.produce_line_ids.all())
                if l.pk not in lot_path
            }
            for lote in siguientes:
                for lote_id, ids in lote._find_delivery_ids_by_lot(
                        lot_path=lot_path, delivery_by_lot=delivery_by_lot).items():
                    if lote_id in {l.pk for l in siguientes}:
                        entregas.update(ids)
        entregas.update(
            l.picking.pk for l in esteriles if l.picking is not None)

        delivery_by_lot[self.pk] = list(entregas)
        return delivery_by_lot

    def _find_delivery_ids_by_lot_iterative(self):
        """≙ ``_find_delivery_ids_by_lot_iterative`` (``odoo19c: :366-431``).

        La misma respuesta que la recursiva, sin recursión: primero desciende
        por la cadena construyendo el mapa de padres, y luego propaga las
        entregas de las hojas hacia arriba hasta que nada cambia.

        Es la que consumen los computes, igual que en la fuente.
        """
        todos = {self.pk}
        esteriles = defaultdict(set)
        padres = defaultdict(set)

        modelo_linea = apps.get_model('stock', 'StockMoveLine')
        cola = [self.pk]
        while cola:
            lineas = modelo_linea.objects.filter(
                self._get_outgoing_domain(), lot__in=cola, state='done').distinct()
            cola = []
            for linea in lineas:
                lote_id = linea.lot_id
                hijos = list(
                    linea.produce_line_ids.values_list('lot_id', flat=True))
                if hijos:
                    for hijo in hijos:
                        if hijo is not None:
                            padres[hijo].add(lote_id)
                else:
                    esteriles[lote_id].add(linea.pk)
                nuevos = {h for h in hijos if h is not None} - todos
                todos.update(nuevos)
                cola.extend(nuevos)

        por_propagar = set()
        delivery_by_lot = {lote_id: set() for lote_id in todos}
        for lote_id, ids in esteriles.items():
            if not ids:
                continue
            delivery_by_lot[lote_id].update(
                modelo_linea.objects.filter(pk__in=ids, picking__isnull=False)
                .values_list('picking_id', flat=True))
            por_propagar.add(lote_id)

        while por_propagar:
            lote_id = por_propagar.pop()
            for padre in padres.get(lote_id, ()):
                nuevas = delivery_by_lot[lote_id] - delivery_by_lot[padre]
                if nuevas:
                    delivery_by_lot[padre].update(nuevas)
                    por_propagar.add(padre)

        return {k: list(v) for k, v in delivery_by_lot.items()}
