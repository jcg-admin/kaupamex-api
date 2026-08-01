"""``ir.demo_failure`` — módulos cuyos datos de demostración no se pudieron cargar.

Adaptación fiel de ``odoo/addons/base/models/ir_demo_failure.py``
(``odoo-tools@bf077302``, ``odoo19c:``). La referencia declara **dos** modelos
en este archivo, y aquí también:

- ``ir.demo_failure`` — una fila por módulo que falló, con su mensaje de error.
- ``ir.demo_failure.wizard`` — el asistente que las agrupa para mostrarlas
  juntas al terminar la instalación, con un contador computado.

Procedencia de los campos:

- ``module_id`` (Many2one a ``ir.module.module``, ``required``) → ``module``,
  FK a ``IrModule`` (``ir_module.py``), que **sí** está portado.
- ``error`` (Char) → ``error``.
- ``wizard_id`` (Many2one al asistente) → ``wizard``, con ``related_name``
  ``failure_ids`` — el mismo nombre que el ``One2many`` de la referencia, para
  que el consumidor lea igual que su fuente.
- ``failures_count`` (Integer, ``compute='_compute_failures_count'``) →
  propiedad ``failures_count``. En la referencia es un computado **sin**
  ``store``, así que aquí es derivado, no columna.
- ``done()`` de la referencia llama ``self.env['ir.module.module'].next()`` —
  el paso siguiente del instalador. Aquí no hay instalador con pasos (ver
  ``ir_module.py``: las tres transiciones ``to install``/``to upgrade``/
  ``to remove`` no se portan por la misma razón), así que ``done()`` no tiene
  a qué encadenar y **no se porta**. Registrar un paso que nadie puede
  alcanzar sería inventar una capacidad.

**Divergencia de persistencia.** En la referencia ambos son
``TransientModel``: se escriben a tabla real y su vacuum los recolecta. Aquí
``TransientModel`` es ``managed = False`` (sin tabla, ver
``orm/models_transient.py``) y estas dos filas **sí** necesitan persistir
entre la corrida del seed y su lectura por el asistente. Por eso heredan de
``TimeStampedModel`` con tabla propia: el fallo es un dato que se consulta
después, no un estado de formulario. La limpieza queda a cargo del mismo
barrido que ``ir_autovacuum.py`` declara.
"""
import fields
import models

from addons.base.models.ir_module import IrModule
from addons.base.models.timestamped_mixin import TimeStampedModel


class IrDemoFailureWizard(TimeStampedModel):
    """Agrupa los fallos de una corrida (``ir.demo_failure.wizard``)."""

    class Meta:
        db_table = 'ir_demo_failure_wizard'
        ordering = ['-id']
        verbose_name = 'Asistente de fallos de demostración'
        verbose_name_plural = 'Asistentes de fallos de demostración'

    @property
    def failures_count(self):
        """Cuántos módulos fallaron — ``_compute_failures_count`` de la referencia."""
        return self.failure_ids.count()

    def __str__(self):
        return f'Fallos de demostración #{self.pk}'


class IrDemoFailure(TimeStampedModel):
    """Un módulo cuyos datos de demostración fallaron (``ir.demo_failure``)."""

    module = fields.Many2one(
        IrModule, on_delete=models.CASCADE, related_name='demo_failures',
        verbose_name='Módulo',
        help_text='Odoo module_id. El addon cuyo seed de demostración falló.',
    )
    error = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Error',
    )
    wizard = fields.Many2one(
        IrDemoFailureWizard, on_delete=models.CASCADE, null=True, blank=True,
        related_name='failure_ids', verbose_name='Asistente',
        help_text='Odoo wizard_id; el related_name conserva el nombre del One2many.',
    )

    class Meta:
        db_table = 'ir_demo_failure'
        ordering = ['id']
        verbose_name = 'Fallo de datos de demostración'
        verbose_name_plural = 'Fallos de datos de demostración'

    def __str__(self):
        return f'{self.module.name}: {self.error}'
