"""``utm.tag`` — categoría de campaña UTM (marketing, newsletter…).

Adaptación fiel de Odoo ``utm/models/utm_tag.py`` (``odoo-tools@622ddc2a``,
``odoo19c:``, LGPL-3). Su único símbolo —``_default_color``— se porta con su
guion bajo: la fuente lo declara privado y ese guion es contrato, no adorno
(``porte-completo-no-parcial.md``).
"""
from random import randint

import fields
import models
from addons.base.models import TimeStampedModel


def _default_color():
    """≙ ``_default_color`` (``odoo19c: utm_tag.py:16-17``).

    En la fuente es un método de instancia que el ``default=lambda self:`` del
    campo invoca. Aquí es una función de módulo porque el ``default`` de
    Django recibe un invocable **sin argumentos** — misma semántica, distinta
    firma que exige el stack. El nombre y su guion bajo se conservan.
    """
    return randint(1, 11)


class UtmTag(TimeStampedModel):
    """``utm.tag`` — etiqueta de campaña (``odoo19c: utm_tag.py:9-27``)."""

    _name = 'utm.tag'
    _description = 'UTM Tag'
    _order = 'name'

    # ≙ ``name`` (requerido, traducible en la referencia).
    name = fields.Char(
        max_length=255, verbose_name='Nombre',
        help_text='Nombre de la etiqueta.',
    )
    # ≙ ``color``. Sin color la etiqueta no se muestra en la vista kanban, que
    # es como se distinguen las internas de las de categorización pública.
    color = fields.Integer(
        default=_default_color, verbose_name='Índice de color',
        help_text='Color de la etiqueta.',
    )

    class Meta:
        db_table = 'utm_tag'
        # ≙ ``_order = 'name'`` (``odoo19c: :14``).
        ordering = ['name']
        verbose_name = 'Etiqueta UTM'
        verbose_name_plural = 'Etiquetas UTM'
        constraints = [
            # ≙ ``_name_uniq = models.Constraint('unique (name)', 'Tag name
            # already exists!')`` (``odoo19c: :24-27``). El nombre de la
            # restricción se conserva para que el error sea rastreable.
            models.UniqueConstraint(
                fields=['name'], name='utm_tag_name_uniq',
                violation_error_message='Tag name already exists!',
            ),
        ]

    def __str__(self) -> str:
        return self.name
