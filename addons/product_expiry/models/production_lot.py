"""``stock.lot`` — las cuatro fechas del lote y su alerta.

Adaptación de Odoo ``product_expiry/models/production_lot.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Porte símbolo por símbolo — 11 de la referencia, 11 aquí
=========================================================

``odoo19c: addons/product_expiry/models/production_lot.py`` (107 líneas):
6 campos + 5 métodos.

=========================================  ============================================
Símbolo de la referencia (línea)           Dónde queda en este puerto
=========================================  ============================================
``use_expiration_date`` (12, related)      property ``use_expiration_date``
``expiration_date`` (13-16)                campo homónimo (``add_to_class``)
``use_date`` (17-19)                       campo homónimo (``add_to_class``)
``removal_date`` (20-22)                   campo homónimo (``add_to_class``)
``alert_date`` (23-25)                     campo homónimo (``add_to_class``)
``product_expiry_reminded`` (27)           campo homónimo (``add_to_class``)
``product_expiry_alert`` (26, compute)     property ``product_expiry_alert``
``_compute_display_name`` (29-38)          ``chain_method`` sobre ``display_name``
``_compute_product_expiry_alert`` (40-45)  ≡ la property ``product_expiry_alert``
``_compute_expiration_date`` (47-56)       ``compute_expiration_date``
``_compute_dates`` (58-77)                 ``compute_dates``
``_alert_date_exceeded`` (79-107)          ``alert_date_exceeded`` (classmethod)
=========================================  ============================================

Ningún símbolo se omite.

Las cuatro fechas son **columnas del propio ``stock.lot``**, no de un modelo
satélite. Es la corrección de forma de :ref:`h-api-576`: la versión anterior
de este addon inventaba ``StockLotExpiry`` (OneToOne al lote) y
``ProductExpiryConfig`` (OneToOne al producto), dos modelos que la referencia
no tiene. El porte entrega ahora los mismos símbolos en el mismo sitio.

``_compute_dates`` — las dos ramas, y por qué importan
========================================================

La referencia distingue **crear** de **cambiar**, y no es un detalle::

    for lot in self:
        if len(lot._origin) == 0:               # creación
            for field, ... in _fields.items():  # las cuatro se derivan
                ...
        elif 'expiration_date' in ...:          # cambió la caducidad
            for field, ... in _fields.items():  # las tres se desplazan
                ...

Al **crear**, cada fecha sale de la caducidad menos sus días. Al **editar la
caducidad de un lote existente**, las otras tres se desplazan *el mismo
delta* que se movió la caducidad — no se recalculan desde cero, porque el
usuario pudo haberlas ajustado a mano y recalcular las pisaría. Este puerto
implementa las dos ramas: ``compute_dates(lot, previous_expiration=...)``.

``_alert_date_exceeded`` — qué se porta y qué diverge
=======================================================

Los tres pasos de la referencia se portan enteros: (1) buscar lotes con
``alert_date <= hoy`` y ``product_expiry_reminded = False``; (2) **intersectar
con los que tienen existencia > 0 en ubicación interna**; (3) marcar
``product_expiry_reminded = True``.

Diverge el cuarto: la referencia agenda además una ``mail.activity``
(``activity_schedule('mail.mail_activity_data_todo', ...)``) sobre el
responsable del producto. Este árbol no tiene el chatter de la referencia
—medido: ``grep -rn "mail_activity_data_todo" addons/ src/`` → 0—, así que la
notificación se reduce al flag idempotente. Sucesor registrado: tarea **#89**
(integrar el envío a la familia ``mail``).
"""
import datetime

import fields
from django.utils import timezone

from addons.stock.models import StockLot, StockQuant
from orm.method_chain import chain_method

#: Los tres desplazamientos derivados de la caducidad, con el campo del
#: producto que da los días. ≙ ``_fields`` de ``_compute_dates``
#: (``odoo19c: production_lot.py:60-64``), mismo orden.
_DERIVED_DATES = (
    ('use_date', 'use_time'),
    ('removal_date', 'removal_time'),
    ('alert_date', 'alert_time'),
)


def _add_if_absent(model, name, field):
    """Añade el campo sólo si el modelo no lo tiene ya — ver ``account_fleet``."""
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


# -- properties (≙ los dos campos computados de la referencia) --


def use_expiration_date(self):
    """≙ ``use_expiration_date`` (related a ``product_id``, ``:12``)."""
    producto = self.product
    return bool(producto is not None and producto.use_expiration_date)


def product_expiry_alert(self):
    """≙ ``_compute_product_expiry_alert`` (``odoo19c: production_lot.py:40-45``).

    ``True`` cuando la caducidad ya se alcanzó. La referencia compara contra
    ``fields.Datetime.now()``; aquí, ``timezone.now()``.
    """
    if not self.expiration_date:
        return False
    return self.expiration_date <= timezone.now()


def display_name(self):
    """≙ ``_compute_display_name`` (``odoo19c: production_lot.py:29-38``).

    La referencia antepone la fecha de caducidad al nombre::

        super()._compute_display_name()
        for lot in self:
            if ...formatted_display_name and lot.expiration_date:
                lot.display_name = f"{lot.name}\\t--{lot.expiration_date.date()}--"

    Devuelve ``None`` cuando el lote no caduca: ése es el **relevo** de
    ``chain_method`` — el equivalente exacto del ``super()`` de la referencia,
    que atiende el caso que este override no cubre. No se pisa el método
    previo con una guarda ``if not hasattr``: es el defecto que
    :ref:`h-api-364` registra.

    El condicionante ``formatted_display_name`` de la referencia es una clave
    del contexto de su cliente web; este árbol no tiene ese contexto (medido:
    ``grep -rn formatted_display_name addons/ src/`` → 0), así que el formato
    se aplica siempre que haya caducidad. Es la única lectura posible sin
    inventar un contexto.
    """
    if self.expiration_date:
        return f'{self.name}\t--{self.expiration_date.date()}--'
    return None


def _display_name_base(self):
    """Shim del ``display_name`` que el núcleo del ORM aún no porta.

    La referencia lo hereda de ``models.Model._compute_display_name``; medido
    aquí, **no existe**::

        grep -rn "display_name" src/orm/*.py  → 0

    Sin una base, el relevo de ``display_name`` no tendría a quién delegar y un
    lote sin caducidad devolvería ``None``. Este shim entrega lo que la base de
    la referencia entrega (``rec.name``), y se instala **sólo si falta**: el día
    que el núcleo lo porte, esta función deja de instalarse y el relevo pasa a
    delegar en la real. Sucesor registrado: tarea **#291** (medir ``src/orm``
    contra ``odoo/orm``), que es donde vive ese símbolo.
    """
    return self.name


# -- el cálculo de las fechas (≙ los dos computes de escritura) --


def compute_expiration_date(self):
    """≙ ``_compute_expiration_date`` (``odoo19c: production_lot.py:47-56``).

    Sólo fija la caducidad si el producto la usa **y** el lote aún no la
    tiene: la referencia respeta el valor ya presente
    (``if lot.product_id.use_expiration_date and not lot.expiration_date``).
    Sin ``expiration_time`` configurado no hay fecha que derivar.
    """
    producto = self.product
    if producto is None or not producto.use_expiration_date:
        return
    if self.expiration_date:
        return
    dias = producto.expiration_time
    if not dias:
        return
    self.expiration_date = timezone.now() + datetime.timedelta(days=dias)


def compute_dates(self, previous_expiration=None):
    """≙ ``_compute_dates`` (``odoo19c: production_lot.py:58-77``).

    Dos ramas, las de la referencia:

    - **creación** (``previous_expiration is None``) — cada fecha derivada sale
      de la caducidad menos los días que el producto declara.
    - **cambio de caducidad** (``previous_expiration`` dado) — las tres se
      desplazan el **mismo delta**, preservando el ajuste manual del usuario.
      Es la rama ``elif`` de la referencia, que usa ``lot._origin`` para
      distinguir el registro nuevo del ya persistido; aquí el llamador pasa la
      caducidad anterior, que es la misma información sin depender de un
      ``_origin`` que este ORM no tiene.
    """
    producto = self.product
    if producto is None or not producto.use_expiration_date:
        return
    if not self.expiration_date:
        return

    if previous_expiration is not None:
        delta = self.expiration_date - previous_expiration
        for campo, _dias in _DERIVED_DATES:
            actual = getattr(self, campo)
            if actual:
                setattr(self, campo, actual + delta)
        return

    for campo, dias_campo in _DERIVED_DATES:
        dias = getattr(producto, dias_campo, 0)
        if dias:
            setattr(self, campo, self.expiration_date - datetime.timedelta(days=dias))


def alert_date_exceeded(cls):
    """≙ ``_alert_date_exceeded`` (``odoo19c: production_lot.py:79-107``).

    Devuelve los lotes marcados. Ver la divergencia del ``mail.activity`` en el
    docstring del módulo.
    """
    ahora = timezone.now()
    candidatos = cls.objects.filter(
        alert_date__isnull=False,
        alert_date__lte=ahora,
        product_expiry_reminded=False,
    )
    # ≙ la intersección con `quant_ids` de ubicación interna y `quantity > 0`
    # (`production_lot.py:92-99`): un lote agotado no genera aviso.
    con_existencia = set(
        StockQuant.objects
        .filter(lot__in=candidatos, quantity__gt=0,
                location__usage='internal')
        .values_list('lot_id', flat=True)
    )
    marcados = []
    for lote in candidatos:
        if lote.pk not in con_existencia:
            continue
        lote.product_expiry_reminded = True
        lote.save(update_fields=['product_expiry_reminded', 'updated_at'])
        marcados.append(lote)
    return marcados


def apply_product_expiry_extensions():
    """Cuelga las cuatro fechas, el recordatorio y los métodos sobre ``stock.lot``."""
    _add_if_absent(StockLot, 'expiration_date', fields.Datetime(
        null=True, blank=True,
        help_text='Fecha en que el lote deja de ser consumible '
                  '(Odoo expiration_date).',
    ))
    _add_if_absent(StockLot, 'use_date', fields.Datetime(
        null=True, blank=True,
        help_text='Fecha desde la que el producto empieza a deteriorarse — '
                  'consumo preferente (Odoo use_date).',
    ))
    _add_if_absent(StockLot, 'removal_date', fields.Datetime(
        null=True, blank=True,
        help_text='Fecha en que el lote debe retirarse del stock; clave del '
                  'orden FEFO (Odoo removal_date).',
    ))
    _add_if_absent(StockLot, 'alert_date', fields.Datetime(
        null=True, blank=True,
        help_text='Fecha en que se levanta la alerta de caducidad '
                  '(Odoo alert_date).',
    ))
    _add_if_absent(StockLot, 'product_expiry_reminded', fields.Boolean(
        default=False,
        help_text='La alerta de caducidad ya se notificó '
                  '(Odoo product_expiry_reminded).',
    ))

    if not hasattr(StockLot, 'use_expiration_date'):
        StockLot.use_expiration_date = property(use_expiration_date)
    if not hasattr(StockLot, 'product_expiry_alert'):
        StockLot.product_expiry_alert = property(product_expiry_alert)

    for nombre, funcion in (
        ('compute_expiration_date', compute_expiration_date),
        ('compute_dates', compute_dates),
    ):
        if not hasattr(StockLot, nombre):
            setattr(StockLot, nombre, funcion)
    if not hasattr(StockLot, 'alert_date_exceeded'):
        StockLot.alert_date_exceeded = classmethod(alert_date_exceeded)

    # La base primero (shim del núcleo ausente), el override después: así el
    # relevo de `chain_method` tiene a quién delegar cuando el lote no caduca.
    if not hasattr(StockLot, 'display_name'):
        StockLot.display_name = _display_name_base
    # `display_name` se ENCADENA, no se instala con guarda: su propósito es
    # añadirse a lo que ya hay. Es exactamente el defecto que :ref:`h-api-364`
    # registra — la guarda `if not hasattr` es correcta para campos y
    # catastrófica para overrides.
    chain_method(StockLot, 'display_name', display_name)


__all__ = [
    'alert_date_exceeded',
    'apply_product_expiry_extensions',
    'compute_dates',
    'compute_expiration_date',
    'display_name',
    'product_expiry_alert',
    'use_expiration_date',
]
