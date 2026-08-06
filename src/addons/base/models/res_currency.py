"""``res.currency`` — moneda ISO 4217 (Odoo ``base``).

Portación fiel de ``res_currency.py`` (Odoo 18:23-47 / 19:21-49, arquitectura
idéntica). Espina base de la adaptación de familias (SOL-096):
account/sale/pricing dependen de moneda.

``round``/``compare_amounts``/``is_zero`` — centralizados aquí (H-API-325,
tarea #115). Fieles a ``odoo19c: res_currency.py:216-261`` con una
divergencia deliberada: la referencia opera sobre ``float`` con
``tools.float_round`` (normaliza dividiendo entre ``rounding``, redondea el
entero más cercano compensando el error de representación IEEE-754 con un
épsilon, y desnormaliza). Este proyecto usa ``Decimal`` para dinero — nunca
``float`` (ver ``account/models/account_tax.py::_d``) — y ``Decimal`` es
exacto en base 10, así que el épsilon de compensación no tiene nada que
corregir: el algoritmo se reduce a dividir entre ``rounding``, redondear el
cociente al entero con ``ROUND_HALF_UP`` (empate se aleja de 0, misma
semántica que el HALF-UP por defecto de la referencia) y multiplicar de
vuelta. Es el mismo algoritmo que ``AccountCashRounding.round()``
(``account/models/account_cash_rounding.py``) ya usa para su propio
``rounding``/``rounding_method`` — aquí se le añade la normalización de
escala a ``decimal_places`` (la división Decimal no preserva por sí sola el
número de decimales visibles, aunque el valor numérico ya sea exacto).

No portado de la clase de la referencia, declarado (fuera del alcance de
H-API-325 — centralizar el redondeo, no portar ``res.currency`` entera):

- ``rate``/``inverse_rate``/``rate_string``/``rate_ids``/``_compute_current_rate``/
  ``_get_rates``/``_get_conversion_rate``/``_convert``: motor de tipos de cambio
  multi-divisa. Sin consumidor — este núcleo aún no tiene una segunda divisa
  activa (tarea #114, :ref:`h-api-324`).
- ``format``/``amount_to_text``: presentación (formato de importe, monto en
  palabras) — sin consumidor de UI en este core de backend.
- ``get_all_currencies``: caché de listado para el selector de divisa del
  formulario Odoo — sin análogo de formulario aquí.
- ``create``/``unlink``/``write`` (toggle de ``group_multi_currency``),
  ``_get_view``/``_get_view_cache_key``: infraestructura de vistas/grupos de
  Odoo — sin análogo en este ORM (Django, sin vistas XML ni grupos de acceso
  por *record rule*).
- Constraint ``rounding>0`` (``odoo19c: :53-56``, ``_rounding_gt_zero``): no
  portada — el guard de división por cero en ``round()``/``is_zero()`` cubre
  la ausencia a nivel de método (``not self.rounding`` corta antes de
  dividir), pero no impide un ``write`` que deje ``rounding<=0`` en la fila.
  Requiere una migración de ``CheckConstraint``. **DESCONOCIDO declarado, sin
  tarea propia todavía** (no se fabrica un ID de tracking desde este pase —
  ver ``porte-completo-no-parcial.md``); condición de cierre: se registra
  cuando exista un endpoint de escritura de ``rounding`` que lo amerite. Ver
  la entrega de la tarea #115 para el registro formal de este pendiente.
"""
import math
from decimal import ROUND_HALF_UP, Decimal

import fields
import models


class ResCurrency(models.Model):
    """``res.currency`` — moneda ISO 4217 (Odoo base).

    Fiel a ``res_currency.py`` (18:23-47 / 19:21-49): ``name`` (código ISO 4217,
    3 letras), ``full_name``, ``symbol``, ``rounding`` (factor), ``decimal_places``
    (compute = ``ceil(log10(1/rounding))``, o18:41 / o19:39), ``position``
    (before/after), ``active``, ``currency_unit_label``. Más ``round``/
    ``compare_amounts``/``is_zero`` (o19:216-261, ver docstring del módulo).
    """

    POSITION_AFTER  = 'after'
    POSITION_BEFORE = 'before'
    POSITION_CHOICES = [
        (POSITION_AFTER, 'Después del importe'),
        (POSITION_BEFORE, 'Antes del importe'),
    ]

    name                = fields.Char(
        max_length=3, unique=True,
        help_text='Código de moneda ISO 4217 (Odoo res.currency.name).',
    )
    full_name           = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Nombre de la moneda (Odoo full_name).',
    )
    symbol              = fields.Char(
        max_length=8,
        help_text='Signo de la moneda (Odoo symbol).',
    )
    rounding            = fields.Monetary(
        max_digits=12, decimal_places=6, default=Decimal('0.01'),
        help_text='Factor de redondeo (Odoo rounding).',
    )
    decimal_places      = fields.Integer(
        default=2,
        help_text='Decimales, computado de rounding (Odoo decimal_places).',
    )
    position            = fields.Selection(
        max_length=6, choices=POSITION_CHOICES, default=POSITION_AFTER,
        help_text='Posición del símbolo (Odoo position).',
    )
    active              = fields.Boolean(
        default=True, help_text='Moneda activa (Odoo active).',
    )
    currency_unit_label = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Etiqueta de la unidad (Odoo currency_unit_label).',
    )

    class Meta:
        db_table = 'res_currency'
        ordering = ['name']
        verbose_name = 'Moneda'
        verbose_name_plural = 'Monedas'

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        """Computa ``decimal_places`` desde ``rounding`` (Odoo _compute_decimal_places).

        o18:163-168 / o19:163-168: si ``0 < rounding <= 1`` →
        ``ceil(log10(1/rounding))``; en otro caso 0.
        """
        r = float(self.rounding or 0)
        if 0 < r <= 1:
            self.decimal_places = int(math.ceil(math.log10(1 / r)))
        else:
            self.decimal_places = 0
        return super().save(*args, **kwargs)

    def round(self, amount):
        """Redondea ``amount`` al múltiplo de ``self.rounding`` más cercano
        (Odoo ``round``, o18:216-223 / o19:216-223).

        Divergencia deliberada con ``float``: ver docstring del módulo. El
        algoritmo se reduce a dividir entre ``rounding``, redondear el
        cociente al entero con ``ROUND_HALF_UP`` (empate se aleja de 0) y
        multiplicar de vuelta — luego se normaliza la escala del resultado a
        ``decimal_places``, porque la división ``Decimal`` no la preserva
        por sí sola (p. ej. ``300`` en vez de ``300.00``, aunque el valor
        numérico ya sea exacto).

        :param amount: importe a redondear (``Decimal`` o convertible).
        :return: ``Decimal`` redondeado a la precisión de ``self.rounding``.
        """
        amount = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        if amount == 0 or not self.rounding:
            return Decimal('0')
        rounding = Decimal(str(self.rounding))
        quantized = (amount / rounding).to_integral_value(rounding=ROUND_HALF_UP) * rounding
        quantum = Decimal('1').scaleb(-self.decimal_places)
        return quantized.quantize(quantum)

    def compare_amounts(self, amount1, amount2):
        """Compara ``amount1`` y ``amount2`` ya redondeados según ``self``
        (Odoo ``compare_amounts``, o18:225-246 / o19:225-246).

        Redondea AMBOS montos antes de comparar — no la diferencia entre
        ellos (ver la advertencia en ``is_zero`` abajo, heredada de la
        referencia: no son equivalentes). Con ``Decimal``, ``round()``
        devuelve siempre un múltiplo exacto de ``rounding``, así que
        comparar por igualdad tras redondear basta; la referencia necesita
        además ``float_is_zero(delta)`` porque la desnormalización en
        ``float`` puede introducir un error de representación incluso
        después de "redondear" — ``Decimal`` no lo tiene.

        :param amount1: primer importe a comparar.
        :param amount2: segundo importe a comparar.
        :return: ``-1``, ``0`` o ``1`` según ``amount1`` sea menor, igual o
            mayor que ``amount2``, a la precisión de ``self.rounding``.
        """
        a1 = self.round(amount1)
        a2 = self.round(amount2)
        if a1 == a2:
            return 0
        return -1 if a1 < a2 else 1

    def is_zero(self, amount):
        """``True`` si ``amount`` redondea a 0 según ``self.rounding`` (Odoo
        ``is_zero``, o18:248-261 / o19:248-261).

        Advertencia heredada de la referencia: ``is_zero(a1 - a2)`` NO
        equivale a ``compare_amounts(a1, a2) == 0`` — éste redondea ANTES
        de restar, aquél redondea la diferencia. Ejemplo (precisión de 2
        decimales): ``0.006`` y ``0.002`` son "iguales" para
        ``is_zero(0.006 - 0.002)`` (``0.004`` redondea a ``0.00``), pero
        distintos para ``compare_amounts(0.006, 0.002)`` (``0.01`` vs
        ``0.00``, redondeados por separado).

        :param amount: importe a comparar contra el cero de esta moneda.
        :return: ``True`` si ``amount`` es lo bastante pequeño para
            tratarse como cero a la precisión de ``self.rounding``.
        """
        return self.round(amount) == 0
