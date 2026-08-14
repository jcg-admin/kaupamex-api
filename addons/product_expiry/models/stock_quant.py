"""``stock.quant`` — la existencia sabe cuándo caduca, y FEFO la ordena.

Adaptación de Odoo ``product_expiry/models/stock_quant.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 8 de la referencia, 6 aquí
=======================================================

``odoo19c: addons/product_expiry/models/stock_quant.py`` (42 líneas):
4 campos + 4 métodos.

========================================  =============================================
Símbolo de la referencia (línea)          Dónde queda en este puerto
========================================  =============================================
``expiration_date`` (10, related+store)   property ``expiration_date``
``removal_date`` (11, related+store)      property ``removal_date``
``use_expiration_date`` (12, related)     property ``use_expiration_date``
``available_quantity`` (13, help)         ``available_qty`` ya existe; ver la nota
``_get_removal_strategy_order`` (24-28)   ``chain_method`` sobre el homónimo de la base
``_compute_available_quantity`` (30-36)   ``expired_qty`` + ``combine`` sobre ``available_qty``
``_get_gs1_barcode`` (16-22)              **bloqueado** — ver "Lo que no cierra"
``_set_view_context`` (38-42)             **bloqueado** — ver "Lo que no cierra"
========================================  =============================================

``related`` → property, no columna
------------------------------------

La referencia declara ``expiration_date``/``removal_date`` como
``related='lot_id.…', store=True``: una columna desnormalizada que el ORM
mantiene sincronizada. Aquí se portan como **property que navega el FK**
(``self.lot.expiration_date``). La diferencia es de rendimiento, no de
semántica: el valor es el mismo y siempre está fresco. Desnormalizar exigiría
el motor de ``@api.depends`` con invalidación cruzada, que este árbol aún no
tiene — DECISIÓN de arquitectura registrada en la tarea **#191**; el día que
exista, estas dos properties se convierten en columnas con su migración.

FEFO — el orden que este addon aporta
=======================================

La estrategia ``fefo`` (*first expired, first out*) **no vive en la base**:
``api: addons/stock/models/stock_quant.py`` porta ``fifo``, ``lifo``,
``least_packages`` y ``closest`` en ``_get_removal_strategy_order``; ``fefo``
la añade este satélite. La forma es la de la referencia — devuelve el orden de
``fefo`` y delega en ``super()`` para el resto::

    @api.model
    def _get_removal_strategy_order(self, removal_strategy):
        if removal_strategy == 'fefo':
            return 'removal_date, in_date, id'
        return super()._get_removal_strategy_order(removal_strategy)

Aquí el equivalente encadena sobre **el mismo símbolo** con relevo por
``None``: la función atiende ``fefo`` y devuelve ``None`` para el resto, con lo
que ``chain_method`` delega en el ``_get_removal_strategy_order`` de la base.
Es la traducción literal del ``super()``, no una reescritura.

Hasta 2026-08-14 encadenaba sobre ``gather``, un símbolo propio de firma
recortada, porque la base no tenía portado el método real. Ya lo tiene
(``api@<este commit>``), y la extensión se repuntó — :ref:`h-api-581`.

``_compute_available_quantity`` — la existencia caducada vale cero
====================================================================

La referencia pone en cero la cantidad disponible del quant cuya
``removal_date`` ya pasó (``:30-36``): mercancía retirable no es mercancía
disponible. Se porta encadenando ``available_qty``.

Lo que este archivo no cierra
===============================

Dos símbolos, los dos bloqueados por una pieza ausente y nombrada:

- ``_get_gs1_barcode`` — antepone los identificadores de aplicación GS1 ``17``
  (caducidad) y ``15`` (consumo preferente) al código de barras del quant. El
  método base no existe aquí (medido: ``grep -rn "_get_gs1_barcode" addons/
  src/`` → 0) porque el addon ``barcodes_gs1_nomenclature`` no está portado.
  Sucesor: tarea **#192** (portar el renderizador de códigos de barras).
- ``_set_view_context`` — activa la columna «fecha de retiro» en la vista del
  cliente Odoo. Este stack no tiene esa capa de vistas; el equivalente es una
  decisión de la API REST, no de este modelo. Sucesor: tarea **#279**
  (``stock`` no declara ningún ``ReportSpec``/vista propia todavía).
"""
from decimal import Decimal

from django.utils import timezone

from addons.stock.models import StockQuant
from orm.method_chain import chain_method

#: ≙ ``'removal_date, in_date, id'`` (``odoo19c: stock_quant.py:27``) — el
#: orden de la estrategia FEFO, traducido al vocabulario de ``order_by``. El
#: lote que se retira antes sale antes; los quants sin lote (sin
#: ``removal_date``) caen al final por ser ``NULL``, y desempatan por
#: ``in_date`` igual que en la referencia.
FEFO_ORDER = ('lot__removal_date', 'in_date', 'id')


# -- properties (≙ los tres `related` de la referencia) --


def expiration_date(self):
    """≙ ``expiration_date`` (related a ``lot_id``, ``:10``)."""
    return self.lot.expiration_date if self.lot is not None else None


def removal_date(self):
    """≙ ``removal_date`` (related a ``lot_id``, ``:11``)."""
    return self.lot.removal_date if self.lot is not None else None


def use_expiration_date(self):
    """≙ ``use_expiration_date`` (related a ``product_id``, ``:12``)."""
    producto = self.product
    return bool(producto is not None and producto.use_expiration_date)


# -- los dos overrides (≙ los dos métodos portables de la referencia) --


def _get_removal_strategy_order(cls, removal_strategy):
    """≙ ``_get_removal_strategy_order`` para ``fefo`` (``:24-28``).

    Devuelve ``None`` para las estrategias que no son suyas — el relevo de
    ``chain_method``, que es el ``super()`` de la referencia.

    **Corregido 2026-08-14.** Hasta hoy esto encadenaba sobre ``gather``, un
    símbolo propio con la firma recortada, porque la base no tenía portado
    ``_get_removal_strategy_order``. Ya lo tiene, así que la extensión cuelga
    del símbolo **que la referencia extiende** — y con el mismo nombre y la
    misma visibilidad (:ref:`h-api-581`).
    """
    if removal_strategy != 'fefo':
        return None
    return FEFO_ORDER


def expired_qty(cls, product, location):
    """≙ ``_compute_available_quantity`` (``odoo19c: stock_quant.py:30-36``).

    Devuelve **la parte caducada** de la existencia: la suma de
    ``quantity − reserved_quantity`` de los quants cuya ``removal_date`` ya
    venció. La referencia pone ese quant en cero
    (``quant.available_quantity = 0``); aquí se descuenta del agregado que el
    puerto de ``stock`` expone, con el mismo efecto observable — lo retirable
    deja de contar como disponible.

    Se instala con ``combine`` (no con el relevo por ``None``) porque la
    semántica es de **fusión**, no de sustitución: hacen falta los dos valores,
    el de la base y el descuento. Es la distinción que ``orm/method_chain.py``
    documenta, y aquí evita reimplementar el trato de las ubicaciones que
    puentean la reserva — que es de la base y sólo de ella.
    """
    ahora = timezone.now()
    vencidos = cls.objects.filter(
        product=product, location=location,
        lot__removal_date__isnull=False, lot__removal_date__lte=ahora,
    )
    return sum(
        (quant.quantity - quant.reserved_quantity for quant in vencidos),
        start=Decimal('0.00'),
    )


def _subtract_expired(caducado, disponible):
    """``combine`` de ``available_qty``: la disponible menos la caducada, nunca
    negativa (la referencia acota en cero, no invierte el signo)."""
    restante = disponible - caducado
    cero = type(restante)(0)
    return restante if restante > cero else cero


def apply_product_expiry_extensions():
    """Cuelga las tres properties y encadena los dos métodos sobre ``stock.quant``."""
    for nombre, funcion in (
        ('expiration_date', expiration_date),
        ('removal_date', removal_date),
        ('use_expiration_date', use_expiration_date),
    ):
        if not hasattr(StockQuant, nombre):
            setattr(StockQuant, nombre, property(funcion))

    chain_method(StockQuant, '_get_removal_strategy_order',
                 classmethod(_get_removal_strategy_order))
    chain_method(StockQuant, 'available_qty', classmethod(expired_qty),
                 combine=_subtract_expired)


__all__ = [
    'FEFO_ORDER',
    'apply_product_expiry_extensions',
    'expiration_date',
    'expired_qty',
    '_get_removal_strategy_order',
    'removal_date',
    'use_expiration_date',
]
