"""``helpdesk.tag`` — etiqueta de ticket de la mesa de ayuda.

Reimplementación nativa de Odoo 19 Enterprise ``helpdesk/models/
helpdesk_tag.py`` (``odoo19e:``, ``OEEL-1``): mismo modelo, campos, orden,
restricción y conducta, escritos aquí sin copiar el texto propietario
(``porte-completo-no-parcial.md``). Sus dos símbolos se portan:
``_get_default_color`` y ``name_create``. Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/basemodel-adoption-helpdesk.md``.
"""

from random import randint

import fields
import models
from addons.base.models import TimeStampedModel


def _get_default_color():
    """≙ ``_get_default_color`` (``odoo19e: helpdesk_tag.py:14-15``).

    Un color entero entre 1 y 11. En la fuente es un método que el
    ``default=`` del campo recibe; el ``default`` de Django llama a un
    invocable sin argumentos, así que aquí es una función de módulo con el
    mismo nombre y guion bajo (precedente: ``utm.tag``).
    """
    return randint(1, 11)


class HelpdeskTag(models.BaseModel, TimeStampedModel):
    """``helpdesk.tag`` (``odoo19e: helpdesk_tag.py:9-30``)."""

    _name = 'helpdesk.tag'
    _description = 'Helpdesk Tags'
    _order = 'name'

    name = fields.Char(max_length=255, required=True, translate=True)
    color = fields.Integer('Color', default=_get_default_color)

    class Meta:
        db_table = 'helpdesk_tag'
        ordering = ['name']
        constraints = [
            # ≙ ``_name_uniq = models.Constraint('unique (name)', …)``.
            models.UniqueConstraint(
                fields=['name'],
                name='helpdesk_tag_name_uniq',
                violation_error_message=(
                    'A tag with the same name already exists.'),
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def name_create(cls, name):
        """≙ ``name_create`` (``odoo19e: helpdesk_tag.py:26-30``).

        Si ya hay una etiqueta con ese nombre, sin distinguir mayúsculas y
        sin los espacios de los extremos, se devuelve ésa en vez de crear
        otra.
        """
        existing_tag = cls.search([('name', '=ilike', name.strip())], limit=1)
        if existing_tag:
            return existing_tag.id, existing_tag.display_name
        return super().name_create(name)
