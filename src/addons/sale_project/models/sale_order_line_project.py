"""Modelo ``SaleOrderLineProject`` — addon ``sale_project``.

Adaptación de Odoo ``sale_project``, que **extiende** ``sale.order.line`` con
``project_id`` + ``task_id``: al confirmar una orden con una línea de producto
de tipo *servicio*, Odoo crea una ``project.task`` (o proyecto) y la enlaza a la
línea. Como módulo-extensión (DEC-SALE-01), en Django es una app propia con
**modelo relacionado** (OneToOne a ``sale.SaleOrderLine``) que porta los dos
enlaces + el generador de tarea.

Bridge ``sale`` + ``project``: atribuye a cada línea de servicio la tarea/proyecto
que su venta origina.
"""
import fields
import models

from addons.project.models import ProjectTask
from addons.base.models import TimeStampedModel


class SaleOrderLineProject(TimeStampedModel):
    """Vincula una ``sale.order.line`` a su proyecto/tarea (Odoo project_id/task_id)."""

    line    = models.OneToOneField(
        'sale.SaleOrderLine', on_delete=models.CASCADE, related_name='project_link',
        help_text='Línea de orden (Odoo sale.order.line).',
    )
    project = fields.Many2one(
        'project.Project', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sale_order_lines', help_text='Proyecto (Odoo project_id).',
    )
    task    = fields.Many2one(
        'project.ProjectTask', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sale_order_lines', help_text='Tarea (Odoo task_id).',
    )

    class Meta:
        db_table = 'sale_order_line_project'
        verbose_name = 'Proyecto de línea de orden de venta'
        verbose_name_plural = 'Proyectos de líneas de orden de venta'

    def __str__(self) -> str:
        return f'{self.line} → {self.task or self.project or "sin proyecto"}'

    @classmethod
    def generate_task(cls, line, project):
        """Crea la tarea de ``project`` para ``line`` y persiste el vínculo.

        Réplica del alta de tarea de Odoo ``sale_project`` al confirmar una línea
        de servicio: la tarea toma el nombre del producto de la línea y queda
        enlazada. Idempotente por línea (``update_or_create``): una sola tarea de
        confirmación por línea.
        """
        task = ProjectTask.objects.create(
            project=project, name=(line.name or str(line.product)),
        )
        link, _created = cls.objects.update_or_create(
            line=line, defaults={'project': project, 'task': task},
        )
        return link
