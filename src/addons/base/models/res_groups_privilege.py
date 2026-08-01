"""Modelo ``res.groups.privilege`` — agrupación de grupos por privilegio.

Adaptación fiel de Odoo ``odoo/addons/base/models/res_groups_privilege.py``
(``odoo-tools@bf077302``, ``odoo19c:``).

Agrupa varios ``res.groups`` bajo una etiqueta que el formulario de usuario
presenta como un selector: "Ventas: Usuario / Responsable / —". El
``placeholder`` es el texto de la opción vacía, por defecto ``"No"``.

Procedencia: ``name`` · ``description`` · ``placeholder`` (default ``'No'``) ·
``sequence`` (default 100) idénticos. ``category_id`` → ``category``, FK a
``base.IrModuleCategory``, que **ya está portado** (``ir_module.py``).
``group_ids`` (One2many) → lo declara ``res_groups.py`` como
``related_name='group_ids'`` en su FK ``privilege``, conservando el nombre de
la referencia.

*Corrección:* esta nota predecía ``related_name='groups'``. Al portar
``res_groups.py`` la fuente resultó nombrarlo ``group_ids``
(``res_groups_privilege.py:14`` de ``odoo19c:``), y manda la fuente. Una
predicción sobre un archivo aún sin portar es especulación, no diseño — el
nombre se lee de la referencia cuando llega, no se anticipa.
"""
from django.db import models

from addons.base.models.timestamped_mixin import TimeStampedModel


class ResGroupsPrivilege(TimeStampedModel):
    """Etiqueta que agrupa grupos en el formulario (``res.groups.privilege``)."""

    name = models.CharField(max_length=120, verbose_name='Nombre')
    description = models.TextField(
        blank=True, default='', verbose_name='Descripción',
    )
    placeholder = models.CharField(
        max_length=60, blank=True, default='No', verbose_name='Marcador',
        help_text='Texto de la opción vacía en el selector del formulario.',
    )
    sequence = models.IntegerField(default=100, verbose_name='Secuencia')
    category = models.ForeignKey(
        'base.IrModuleCategory', on_delete=models.PROTECT,
        null=True, blank=True, db_index=True,
        related_name='privileges', verbose_name='Categoría',
    )

    class Meta:
        db_table = 'res_groups_privilege'
        ordering = ['sequence', 'name', 'id']
        verbose_name = 'Privilegio'
        verbose_name_plural = 'Privilegios'

    def __str__(self):
        return self.name
