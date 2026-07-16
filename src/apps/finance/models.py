"""
Models — apps.finance (MOD-028, capa-3 en arquitectura-tecnica/modulos/finance).

Primer slice del modulo financiero: ``CashConcept`` (UC-FIN-06), el catalogo
maestro de conceptos de caja que clasifica todo ingreso/egreso. Jerarquico
(``parent``), con cuenta contable (``account``), ``kind`` income/expense y flags
``editable``/``leaf``. Enums/choices en INGLES (canon-idioma).

Entidades restantes del modelo de dominio (GatewaySettlement, CashMovement,
CashClose, CarrierInvoice, CashFlowProjection, PeriodClose) llegan en slices
posteriores del loop.
"""
from django.db import models

from apps.core.models import TimeStampedModel


class CashConceptKind(models.TextChoices):
    """Clase del concepto de caja (UC-FIN-06)."""
    INCOME = 'income', 'Ingreso'
    EXPENSE = 'expense', 'Egreso'


class CashConcept(TimeStampedModel):
    """Concepto de caja del catalogo (UC-FIN-06).

    ``code`` y ``kind`` son inmutables una vez creado el concepto (para no
    reinterpretar la clasificacion historica). El catalogo es jerarquico:
    un concepto ``leaf`` cuelga de una categoria via ``parent``.
    """
    code = models.CharField(
        max_length=64, unique=True,
        verbose_name='Codigo',
        help_text='Codigo unico e inmutable del concepto (p. ej. FREIGHT_OUT).',
    )
    name = models.CharField(max_length=160, verbose_name='Nombre')
    kind = models.CharField(
        max_length=8, choices=CashConceptKind.choices,
        verbose_name='Clase',
        help_text='income (ingreso) o expense (egreso); inmutable tras crear.',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='children', verbose_name='Concepto padre',
    )
    account = models.CharField(
        max_length=32, blank=True, default='',
        verbose_name='Cuenta contable',
        help_text='Cuenta contable asociada (opcional).',
    )
    editable = models.BooleanField(
        default=True, verbose_name='Editable',
        help_text='Un concepto de sistema (False) no admite cambios.',
    )
    leaf = models.BooleanField(
        default=True, verbose_name='Hoja',
        help_text='True si es el ultimo nivel (clasifica movimientos).',
    )
    active = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        db_table = 'finance_cash_concept'
        ordering = ['kind', 'code']
        verbose_name = 'Concepto de caja'
        verbose_name_plural = 'Conceptos de caja'

    def __str__(self):
        return f'{self.code} ({self.kind})'

    def is_used(self):
        """¿El concepto esta referenciado por algun movimiento de caja?

        Placeholder del slice: ``CashMovement`` aun no existe, asi que ningun
        concepto esta "en uso" todavia. Cuando aterrice ``CashMovement`` esta
        query pasa a ``self.movements.exists()`` y habilita el gate
        ``CONCEPT_IN_USE`` del borrado fisico (UC-FIN-06 EX-03).
        """
        return False
