"""Modelo ``CrmTag`` — addon ``sales_team``.

Adaptación fiel de ``sales_team/models/crm_tag.py`` (``crm.tag``): etiqueta
reutilizable para clasificar oportunidades/órdenes. ``sale.order`` la referencia
vía ``tag_ids`` (Many2many). Núcleo: ``name`` único + ``color``.
"""
from random import randint

import fields
import models

from addons.base.models import TimeStampedModel


def _get_default_color():
    """≙ ``CrmTag._get_default_color`` (crm_tag.py:11-12).

    La referencia lo declara como método de instancia y lo pasa como
    ``default=`` del campo; aquí es una función de módulo porque el ``default``
    de Django se resuelve sin instancia. Mismo rango, 1 a 11 inclusive.
    """
    return randint(1, 11)


class CrmTag(TimeStampedModel):
    """``crm.tag`` — etiqueta de CRM/ventas."""

    _name = 'crm.tag'
    _description = "CRM Tag"

    def _get_default_color():
        """≙ ``_get_default_color`` (crm_tag.py:11-12).

        Se declara DENTRO de la clase, donde la fuente lo declara. Sin ``self``:
        el ``default`` de Django resuelve sin instancia, y en el cuerpo de la
        clase el nombre todavía es una función suelta cuando el campo lo toma.
        Mismo rango, 1 a 11 inclusive.
        """
        return randint(1, 11)

    # Odoo crm.tag.name (crm_tag.py:15, required, translate, unique).
    name  = fields.Char(
        max_length=100, unique=True,
        help_text='Nombre de la etiqueta (Odoo crm.tag.name).',
    )
    # Odoo color (crm_tag.py:16).
    color = fields.Integer(
        default=_get_default_color,
        help_text='Índice de color (Odoo crm.tag.color).',
    )

    class Meta:
        db_table = 'crm_tag'
        ordering = ['name']
        verbose_name = 'Etiqueta de venta'
        verbose_name_plural = 'Etiquetas de venta'

    def __str__(self) -> str:
        return self.name
