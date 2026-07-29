"""Modelo ``Uom`` — addon ``uom`` (fundación de nivel 0 del árbol).

Adaptación fiel de ``uom.uom`` (``uom/models/uom_uom.py:18-22``, verificado en
la referencia 19). Es la **única** clase del addon: cero extensiones de modelos
ajenos, así que su superficie completa es este archivo (DEC-AF-03).

Jerarquía relativa, no categorías
=================================

La referencia 19 ya **no** tiene ``uom.category``: una unidad cuelga de otra por
``relative_uom_id`` (``:41``) y su ``factor`` absoluto es el producto de la
cadena (``:69-75``). Dos unidades son convertibles si comparten raíz — lo
resuelve ``has_common_reference`` leyendo ``parent_path``.

Adaptación de los ``compute`` a Django
======================================

En la referencia ``factor``, ``sequence`` y ``parent_path`` son campos
``compute``/``_parent_store``; el ORM los recalcula solo. Aquí se recalculan en
``save()``, que además **repropaga a los descendientes** — sin eso, cambiar el
factor de un padre dejaría a sus hijos con un ``factor`` obsoleto.

``rounding`` (``:36``) es un ``compute`` **no** almacenado: aquí es una
propiedad que lee la precisión declarada de ``decimal.precision``.
"""
import fields
import models
from addons.base.models import DecimalPrecision, TimeStampedModel
from exceptions import UserError
from tools.float_utils import float_compare, float_is_zero, float_round

#: Nombre de la precisión decimal que gobierna el redondeo de cantidades
#: (``uom/data/uom_data.xml``: ``decimal_product_uom`` → "Product Unit").
PRODUCT_UNIT_PRECISION = 'Product Unit'


class Uom(TimeStampedModel):
    """``uom.uom`` — unidad de medida de producto."""

    name            = fields.Char(
        max_length=100,
        help_text='Nombre de la unidad (Odoo uom.uom.name).',
    )
    sequence        = models.PositiveIntegerField(
        default=0,
        help_text='Orden de presentación (Odoo sequence). Se deriva del factor.',
    )
    relative_factor = fields.Float(
        default=1.0,
        help_text='Cuánto mayor o menor es esta unidad respecto a su unidad de '
                  'referencia (Odoo relative_factor).',
    )
    active          = fields.Boolean(
        default=True,
        help_text='Desmarcar para deshabilitar la unidad sin borrarla (Odoo active).',
    )
    relative_uom    = fields.Many2one(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='related_uoms', db_index=True,
        help_text='Unidad de referencia de la que cuelga (Odoo relative_uom_id).',
    )
    factor          = fields.Float(
        default=1.0,
        help_text='Cantidad absoluta: producto de la cadena de factores '
                  'relativos (Odoo factor, compute recursivo almacenado).',
    )
    parent_path     = fields.Char(
        max_length=255, db_index=True, blank=True, default='',
        help_text='Ruta materializada de la jerarquía (Odoo _parent_store).',
    )

    class Meta:
        db_table = 'uom_uom'
        ordering = ['sequence', 'relative_uom_id', 'id']
        verbose_name = 'Unidad de medida'
        verbose_name_plural = 'Unidades de medida'

    def __str__(self) -> str:
        return self.name

    # === PRECISIÓN =========================================================

    @property
    def rounding(self) -> float:
        """Precisión mínima de redondeo (Odoo ``_compute_rounding``, ``:60-66``).

        Todas las unidades comparten la precisión declarada en "Product Unit";
        la referencia lo resuelve igual, con un ``compute`` no almacenado.
        """
        return 10 ** -self._precision_digits()

    @staticmethod
    def _precision_digits() -> int:
        precision = DecimalPrecision.objects.filter(
            name=PRODUCT_UNIT_PRECISION,
        ).first()
        return precision.digits if precision else 2

    # === PERSISTENCIA ======================================================

    def clean_business(self) -> None:
        """Las dos restricciones de la referencia.

        - ``_factor_gt_zero`` (``:47-50``): el factor de conversión no puede
          ser 0.
        - ``_check_factor`` (``:97-101``): sin unidad de referencia, el factor
          relativo tiene que ser 1.
        """
        if self.relative_factor == 0:
            raise UserError(
                'El factor de conversión de una unidad de medida no puede ser 0.'
            )
        if not self.relative_uom_id and self.relative_factor != 1.0:
            raise UserError('Falta la unidad de medida de referencia.')

    def save(self, *args, **kwargs):
        self.clean_business()
        if not self.sequence:
            # Odoo `_compute_sequence` (:54-58): sólo antes de existir el registro.
            self.sequence = min(int(self.relative_factor * 100.0), 1000)
        self.factor = (
            self.relative_factor * self.relative_uom.factor
            if self.relative_uom_id else self.relative_factor
        )
        super().save(*args, **kwargs)

        parent_path = (
            f'{self.relative_uom.parent_path}{self.pk}/'
            if self.relative_uom_id else f'{self.pk}/'
        )
        if self.parent_path != parent_path:
            self.parent_path = parent_path
            super().save(update_fields=['parent_path'])

        # El `factor` de la referencia es un compute recursivo: al cambiar el de
        # un padre, los hijos quedarían obsoletos si no se repropaga.
        for child in self.related_uoms.all():
            child.save()

    # === MÉTODOS DE NEGOCIO ================================================

    def round(self, value: float, rounding_method: str = 'HALF-UP') -> float:
        """Redondea con la precisión "Product Unit" (Odoo ``:118-122``)."""
        return float_round(
            value, precision_digits=self._precision_digits(),
            rounding_method=rounding_method,
        )

    def compare(self, value1: float, value2: float) -> int:
        """Compara dos medidas tras redondearlas (Odoo ``:124-133``)."""
        return float_compare(
            value1, value2, precision_digits=self._precision_digits(),
        )

    def is_zero(self, value: float) -> bool:
        """``True`` si el valor es cero a la precisión declarada (Odoo ``:135-139``)."""
        return float_is_zero(value, precision_digits=self._precision_digits())

    def compute_quantity(
        self,
        qty: float,
        to_unit: 'Uom',
        round: bool = True,
        rounding_method: str = 'UP',
    ) -> float:
        """Convierte ``qty`` de esta unidad a ``to_unit`` (Odoo ``:148-176``).

        La conversión pasa por el ``factor`` absoluto de ambas, que es lo que
        permite convertir entre unidades de la misma cadena sin acumular error.
        """
        if not qty:
            return qty
        if self == to_unit:
            amount = qty
        else:
            amount = qty * self.factor
            if to_unit:
                amount = amount / to_unit.factor
        if to_unit and round:
            amount = float_round(
                amount, precision_rounding=to_unit.rounding,
                rounding_method=rounding_method,
            )
        return amount

    def compute_price(self, price: float, to_unit: 'Uom') -> float:
        """Convierte un precio a la unidad destino (Odoo ``:196-203``).

        Inverso de la cantidad: si la unidad destino es mayor, su precio sube.
        """
        if not price or not to_unit or self == to_unit:
            return price
        return price * to_unit.factor / self.factor

    def check_qty(
        self,
        product_qty: float,
        uom: 'Uom',
        rounding_method: str = 'HALF-UP',
    ) -> float:
        """Ajusta ``product_qty`` a un múltiplo de la cantidad por empaque
        (Odoo ``:178-194``).

        No usa el operador módulo: la cantidad por empaque puede ser flotante y
        daría resultados falsos (``8 % 1.6 == 1.5999999999999996``).
        """
        packaging_qty = self.compute_quantity(1, uom)
        if self == uom:
            return product_qty
        if product_qty and packaging_qty:
            product_qty = float_round(
                product_qty / packaging_qty, precision_rounding=1.0,
                rounding_method=rounding_method,
            ) * packaging_qty
        return product_qty

    def has_common_reference(self, other_uom: 'Uom') -> bool:
        """``True`` si ambas cuelgan de la misma raíz (Odoo ``:216-227``).

        Es la condición de convertibilidad: sustituye a la comparación de
        ``uom.category`` que la referencia tenía antes de 19.
        """
        if not self.parent_path or not other_uom.parent_path:
            return False
        return self.parent_path.split('/')[0] == other_uom.parent_path.split('/')[0]
