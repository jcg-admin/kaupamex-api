"""``stock.move.line`` — la línea de movimiento y sus dos fechas.

Adaptación de Odoo ``product_expiry/models/stock_move_line.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 8 de 8
====================================

``odoo19c: addons/product_expiry/models/stock_move_line.py`` (62 líneas):
4 campos + 4 métodos, todos sobre ``stock.move.line``.

**Estaba BLOQUEADO y ya no lo está.** Hasta hoy este archivo era un no-op
declarado: los ocho símbolos extienden ``stock.move.line``, y ese modelo no
existía en el árbol. Se portó en el mismo pase
(``api: addons/stock/models/stock_move_line.py``), así que el bloqueo cae y el
archivo se llena entero — que es lo que su propia sección "Qué desbloquea el
porte" prometía.

=========================================  ==========================================
Símbolo de la referencia (línea)           Aquí
=========================================  ==========================================
``expiration_date`` (13-16, compute+store) campo homónimo (``add_to_class``)
``removal_date`` (17, compute+store)       campo homónimo (``add_to_class``)
``is_expired`` (18, related)               property ``is_expired``
``use_expiration_date`` (19-20, related)   property ``use_expiration_date``
``_auto_init`` (22-32)                     **divergencia declarada** — ver abajo
``_compute_expiration_date`` (34-44)       ``_compute_expiration_date``
``_compute_removal_date`` (46-56)          ``_compute_removal_date``
``_prepare_new_lot_vals`` (58-62)          ``chain_method`` sobre el homónimo
=========================================  ==========================================

Divergencia declarada — ``_auto_init``
========================================

La referencia crea las dos columnas **a mano** con SQL antes de que el ORM las
compute, y su docstring dice por qué: *"to avoid MemoryError when letting the
ORM compute it after module installation"*. Es una defensa contra su propio
mecanismo de instalación, que recomputaría el campo para cada línea existente
—decenas de millones en una instancia grande— dentro de una sola transacción.

Aquí ese mecanismo no existe: las columnas las crea una **migración de
Django**, que es DDL puro y no dispara ningún cómputo. El símbolo se porta como
lo que su cuerpo hace —crear las dos columnas— y su hogar es la migración, no
un método. No es un recorte: es que la defensa protege de un problema que este
stack no tiene.

Su segunda mitad —``return super()._auto_init()``— tampoco tiene contraparte:
``_auto_init`` es el gancho de creación de tablas del ORM de la referencia.

Por qué el ``compute`` de las dos fechas es un ``save()`` y no un motor
========================================================================

La referencia declara las dos con ``compute=… store=True`` y
``@api.depends('product_id', 'lot_id.expiration_date', 'picking_id.scheduled_date',
'quant_id')``. Este árbol no tiene el motor de ``@api.depends`` con invalidación
cruzada (DECISIÓN de arquitectura, tarea **#191**), así que las dos se
recalculan en el ``save()`` de la línea — el mismo idioma que ``stock.quant``
usa para sus cuatro campos almacenados.

**Lo que la divergencia cuesta, dicho:** si alguien cambia la
``expiration_date`` del **lote** sin tocar la línea, la línea conserva la fecha
vieja hasta su próximo ``save()``. En la referencia el ``depends`` la
invalidaría. Es la misma deuda que la tarea #191 cierra para todo el árbol; no
se abre una segunda.
"""
import datetime

import fields
from django.utils import timezone

from addons.stock.models import StockMoveLine
from orm.method_chain import chain_method


def _add_if_absent(model, name, field):
    """Cuelga el campo sólo si el modelo aún no lo declara.

    La guarda es correcta para **campos** —volver a colgarlo reventaría el
    registro de Django— y sería catastrófica para un override, que es lo que
    :ref:`h-api-364` registra. Por eso ``_prepare_new_lot_vals`` no la usa.
    """
    if not hasattr(model, name):
        model.add_to_class(name, field)


# -- properties (≙ los dos `related` de la referencia) --


def is_expired(self):
    """≙ ``is_expired`` (``related='lot_id.product_expiry_alert'``, ``:18``)."""
    return bool(self.lot is not None and self.lot.product_expiry_alert)


def use_expiration_date(self):
    """≙ ``use_expiration_date`` (``related='product_id.use_expiration_date'``, ``:19-20``)."""
    producto = self.product
    return bool(producto is not None and producto.use_expiration_date)


# -- los dos computes almacenados (≙ :34-56) --


def _compute_expiration_date(self):
    """≙ ``_compute_expiration_date`` (``odoo19c: :34-44``).

    Tres caminos, y el orden es el de la referencia:

    1. hay lote (el del quant elegido gana sobre el de la línea) → su fecha;
    2. el tipo de operación **crea** lotes y el producto caduca → se proyecta
       desde la fecha planeada del albarán sumando ``expiration_time``, pero
       sólo si la línea aún no tiene fecha (una puesta a mano sobrevive);
    3. el tipo crea lotes y el producto **no** caduca → se limpia.
    """
    quant = self.quant
    lote = (quant.lot if quant is not None else None) or self.lot
    if lote is not None:
        self.expiration_date = lote.expiration_date
        return
    if not self.picking_type_use_create_lots:
        return
    producto = self.product
    if producto is not None and producto.use_expiration_date:
        if not self.expiration_date:
            desde = self.scheduled_date or timezone.now()
            self.expiration_date = desde + datetime.timedelta(
                days=producto.expiration_time or 0)
    else:
        self.expiration_date = None


def _compute_removal_date(self):
    """≙ ``_compute_removal_date`` (``odoo19c: :46-56``).

    La fecha de retiro es la del lote si la tiene; si no, la de caducidad menos
    ``removal_time`` — el margen con el que la mercancía debe salir **antes**
    de caducar, que es lo que FEFO ordena.
    """
    if self.lot is not None and self.lot.removal_date:
        self.removal_date = self.lot.removal_date
        return
    if not self.picking_type_use_create_lots:
        return
    producto = self.product
    if producto is not None and producto.use_expiration_date and self.expiration_date:
        self.removal_date = self.expiration_date - datetime.timedelta(
            days=producto.removal_time or 0)
    else:
        self.removal_date = None


def _save_with_expiry(self, *args, **kwargs):
    """Recalcula las dos fechas antes de escribir.

    Es el equivalente del ``compute … store=True`` de la referencia bajo la
    ausencia del motor de ``@api.depends`` (tarea #191). Se instala con
    ``chain_method`` sobre ``save`` para no pisar el ``save()`` de la base, que
    ya recalcula los cinco campos almacenados de ``stock.move.line``.
    """
    _compute_expiration_date(self)
    _compute_removal_date(self)
    return None


def _prepare_new_lot_vals(self):
    """≙ ``_prepare_new_lot_vals`` (``odoo19c: :58-62``).

    Propaga la caducidad de la línea al lote que se está creando. Devuelve
    sólo **su** aporte; el relevo de ``chain_method`` lo funde con el de la
    base, que es la traducción literal del ``super()`` de la referencia.
    """
    if not self.expiration_date:
        return None
    return {'expiration_date': self.expiration_date}


def _merge_lot_vals(propios, de_la_base):
    """``combine`` de ``_prepare_new_lot_vals``: la base primero, el aporte encima."""
    fusion = dict(de_la_base or {})
    fusion.update(propios or {})
    return fusion


def apply_product_expiry_extensions():
    """Cuelga las dos fechas, las dos properties y los dos overrides."""
    _add_if_absent(StockMoveLine, 'expiration_date', fields.Datetime(
        null=True, blank=True,
        help_text='Fecha en que la mercancía de esta línea deja de ser '
                  'consumible (Odoo expiration_date).',
    ))
    _add_if_absent(StockMoveLine, 'removal_date', fields.Datetime(
        null=True, blank=True,
        help_text='Fecha en que la mercancía debe retirarse; clave del orden '
                  'FEFO (Odoo removal_date).',
    ))

    for nombre, funcion in (
        ('is_expired', is_expired),
        ('use_expiration_date', use_expiration_date),
    ):
        if not hasattr(StockMoveLine, nombre):
            setattr(StockMoveLine, nombre, property(funcion))

    for nombre, funcion in (
        ('_compute_expiration_date', _compute_expiration_date),
        ('_compute_removal_date', _compute_removal_date),
    ):
        if not hasattr(StockMoveLine, nombre):
            setattr(StockMoveLine, nombre, funcion)

    # Los dos se ENCADENAN, no se instalan con guarda: su propósito es añadirse
    # a lo que ya hay (:ref:`h-api-364`).
    chain_method(StockMoveLine, 'save', _save_with_expiry)
    chain_method(StockMoveLine, '_prepare_new_lot_vals', _prepare_new_lot_vals,
                 combine=_merge_lot_vals)


__all__ = [
    'apply_product_expiry_extensions',
    'is_expired',
    '_compute_expiration_date',
    '_compute_removal_date',
    '_prepare_new_lot_vals',
    'use_expiration_date',
]
