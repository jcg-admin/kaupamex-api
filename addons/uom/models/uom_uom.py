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

Nombre de la clase — divergencia declarada
==========================================

La referencia llama a la clase ``UomUom``; aquí es ``Uom``. Renombrar un modelo
de Django exige una ``RenameModel`` en migraciones, que migra la tabla, así que
va en su propio pase — mismo criterio que ``BusMessage``/``BusBus`` y que las
columnas ``Char`` que esperan su FK.

La protección de datos maestros
===============================

Se completó en este pase. La referencia impide **borrar** las unidades que
vienen de sus datos maestros —salvo tres explícitamente liberadas— y avisa al
**editar** una de ellas si el registro tiene más de un día. Las dos piezas
faltaban.

Su mecanismo consulta ``ir.model.data`` por ``module='uom'``, y esa tabla
**ya existe** (``api@b618a6b``), así que se porta tal cual en vez de inventar
un booleano paralelo. Durante un tiempo la guarda quedó **inerte** porque nadie
poblaba la tabla; se activó sola al llegar el escritor
(``IrModelData.set_xmlid``, ``api@6ff52ca``… ver :ref:`h-api-347`) **sin tocar
este archivo**, que era lo que aquella nota predijo. La llave que este lector
usa —``model=cls._meta.label``— es la que fijó la convención del resolutor.

Lo que sigue faltando es el **sembrado** de las unidades maestras: la guarda
funciona, y protegerá lo que se siembre con identificador del módulo ``uom``.
"""
import datetime

import fields
import models
from addons.base.models import DecimalPrecision, IrModelData, TimeStampedModel
from django.utils import timezone
from exceptions import UserError
from tools.float_utils import float_compare, float_is_zero, float_round

#: Nombre de la precisión decimal que gobierna el redondeo de cantidades
#: (``uom/data/uom_data.xml``: ``decimal_product_uom`` → "Product Unit").
PRODUCT_UNIT_PRECISION = 'Product Unit'

#: Módulo cuyos datos maestros de unidad están protegidos.
UOM_MASTER_MODULE = 'uom'

#: Las tres unidades que la referencia **libera** explícitamente
#: (``_unprotected_uom_xml_ids``, verbatim). Se copian enteras: recortar la
#: lista protegería de más, y protegerlas es impedir que alguien las borre.
UNPROTECTED_UOM_XML_IDS = (
    'product_uom_hour',
    'product_uom_dozen',
    'product_uom_pack_6',
)

#: La referencia sólo avisa al editar una unidad protegida si el registro
#: tiene más de un día — recién creada, editarla es parte de configurarla.
CRITICAL_CHANGE_GRACE = datetime.timedelta(days=1)


def _as_float(value):
    """Frontera entre el dominio ``Decimal`` de este árbol y ``float_utils``.

    En la referencia toda cantidad es ``Float`` (``product_uom_qty``,
    ``quantity``, ``product_qty``…), así que ``float_round``/``float_compare``
    son float-only por construcción — su algoritmo normaliza dividiendo por el
    factor de redondeo, y ``Decimal / float`` levanta ``TypeError``. Aquí esos
    campos son ``DecimalField`` (dinero y cantidad exactos, ADR-028), de modo
    que un ``Decimal`` llega a ``uom.compare(...)`` en cuanto alguien compara
    dos cantidades reales — medido: ``stock_rule._run_pull`` ordenando por
    ``product_uom.compare(proc.product_qty, 0.0)``.

    La conversión se hace **aquí y no dentro de ``float_utils``**: aquel es
    puerto verbatim de un algoritmo de coma flotante y aceptar ``Decimal`` en
    silencio lo volvería mentiroso sobre lo que devuelve. ``Uom`` ya es la capa
    de adaptación (declara ``_precision_digits()``, que la referencia no
    tiene), así que es su sitio.
    """
    return float(value) if value is not None else value


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
    relative_uom_id = fields.Many2one(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='related_uoms', db_index=True,
        help_text='Unidad de referencia de la que cuelga (Odoo relative_uom_id).',
        db_column='relative_uom_id',
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
        ordering = ['sequence', 'relative_uom_id_id', 'id']
        verbose_name = 'Unidad de medida'
        verbose_name_plural = 'Unidades de medida'
        constraints = [
            # ``_factor_gt_zero``: el ratio de conversión no puede ser 0.
            # Estaba sólo como chequeo de Python (``clean_business``); la
            # referencia lo declara **también** en la base, y ahí es donde
            # aguanta una escritura que no pase por el modelo.
            models.CheckConstraint(
                condition=~models.Q(relative_factor=0),
                name='uom_uom_factor_gt_zero',
            ),
        ]

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
            self.relative_factor * self.relative_uom_id.factor
            if self.relative_uom_id else self.relative_factor
        )
        super().save(*args, **kwargs)

        parent_path = (
            f'{self.relative_uom_id.parent_path}{self.pk}/'
            if self.relative_uom_id else f'{self.pk}/'
        )
        if self.parent_path != parent_path:
            self.parent_path = parent_path
            super().save(update_fields=['parent_path'])

        # El `factor` de la referencia es un compute recursivo: al cambiar el de
        # un padre, los hijos quedarían obsoletos si no se repropaga.
        for child in self.related_uoms.all():
            child.save()

    # === PROTECCIÓN DE DATOS MAESTROS ======================================

    @classmethod
    def filter_protected_uoms(cls, uoms):
        """``_filter_protected_uoms`` — cuáles de ``uoms`` están protegidas.

        Una unidad está protegida si tiene un identificador externo del módulo
        ``uom`` **y** su nombre no está entre los tres liberados. Se porta la
        consulta de la referencia contra ``ir.model.data``, no un booleano
        paralelo. Cubierto de punta a punta en
        ``tests/unit/base/test_ir_model_data_xmlid.py``, que siembra un
        identificador y comprueba que esta guarda lo ve.
        """
        ids = [uom.pk for uom in uoms if uom.pk is not None]
        if not ids:
            return []
        protected_ids = set(
            IrModelData.objects.filter(
                model=cls._meta.label, res_id__in=ids,
                module=UOM_MASTER_MODULE,
            ).exclude(
                name__in=UNPROTECTED_UOM_XML_IDS,
            ).values_list('res_id', flat=True)
        )
        return [uom for uom in uoms if uom.pk in protected_ids]

    def check_can_delete(self):
        """``_unlink_except_master_data`` — no se borra una unidad del sistema.

        La referencia no se limita a impedirlo: **nombra** las unidades que
        bloquean y ofrece la alternativa (archivarlas, que para eso está
        ``active``). Se conserva porque un error que sólo dice "no puedes"
        deja al operador sin saber qué hacer.
        """
        protected = type(self).filter_protected_uoms([self])
        if not protected:
            return
        names = ', '.join(uom.name for uom in protected)
        raise UserError(
            'Las siguientes unidades de medida las usa el sistema y no se '
            'pueden eliminar: %s\nPuede archivarlas en su lugar.' % names
        )

    def critical_change_warning(self):
        """``_onchange_critical_fields`` — aviso al tocar una unidad del sistema.

        Devuelve el texto del aviso, o ``None`` si no aplica. **No** levanta:
        en la referencia es un ``warning`` de formulario, no un error — cambiar
        una unidad maestra está permitido y es peligroso, que no es lo mismo
        que estar prohibido.

        La ventana de gracia de un día es de la referencia y tiene sentido:
        una unidad recién creada se está configurando, y avisar entonces sería
        ruido en el flujo normal.
        """
        if not type(self).filter_protected_uoms([self]):
            return None
        if self.created_at is None:
            return None
        if self.created_at >= timezone.now() - CRITICAL_CHANGE_GRACE:
            return None
        return (
            'Se han modificado campos críticos de %s.\n'
            'Los datos existentes NO se actualizarán con este cambio.\n\n'
            'Como las unidades de medida afectan a todo el sistema, esto '
            'puede causar problemas graves. Cambiar unidades de medida '
            'básicas en una base en marcha no es recomendable.' % self.name
        )

    # === MÉTODOS DE NEGOCIO ================================================

    def round(self, value: float, rounding_method: str = 'HALF-UP') -> float:
        """Redondea con la precisión "Product Unit" (Odoo ``:118-122``).

        ``value`` admite ``Decimal`` además de ``float`` — ver ``_as_float``.
        """
        return float_round(
            _as_float(value), precision_digits=self._precision_digits(),
            rounding_method=rounding_method,
        )

    def compare(self, value1: float, value2: float) -> int:
        """Compara dos medidas tras redondearlas (Odoo ``:124-133``)."""
        return float_compare(
            _as_float(value1), _as_float(value2),
            precision_digits=self._precision_digits(),
        )

    def is_zero(self, value: float) -> bool:
        """``True`` si el valor es cero a la precisión declarada (Odoo ``:135-139``)."""
        return float_is_zero(
            _as_float(value), precision_digits=self._precision_digits())

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
