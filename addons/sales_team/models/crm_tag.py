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

    DIVERGENCIA DE MECANISMO declarada, no un descuido de sitio. La fuente lo
    declara **dentro** de la clase y lo pasa como ``default=`` del campo. Aquí
    no puede ir ahí: Django serializa un ``default`` callable **por su ruta de
    import** al escribir la migración, y una función del cuerpo de una clase no
    tiene ninguna. Medido: al moverlo dentro, la migración ya escrita deja de
    resolverlo y el árbol entero cae con ``AttributeError`` — 435 errores.

    Queda a nivel de módulo, sin ``self`` porque el ``default`` de Django
    resuelve sin instancia. Mismo rango, 1 a 11 inclusive. Registrada en
    ``scripts/divergencias_declaradas.txt``.
    """
    return randint(1, 11)


class CrmTag(TimeStampedModel):
    """``crm.tag`` — etiqueta de CRM/ventas."""

    _name = 'crm.tag'
    _description = "CRM Tag"

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
