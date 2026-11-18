"""``res.city`` — ciudad de un país (Odoo ``base_address_extended``).

Portación fiel de ``res_city.py`` (18:9-22 / 19:8-21, campos idénticos; en 19
la
clase se renombró ``City`` → ``ResCity``, sólo cosmético).
"""

import api
import fields
import models
from addons.base.models import TimeStampedModel


class ResCity(models.BaseModel, TimeStampedModel):
    """``res.city`` — ciudad de un país.

    ``name`` (requerido), ``zipcode``, ``country`` FK (requerido), ``state`` FK
    (dominio país).

    Los cuatro atributos de clase que la fuente declara se portan verbatim —
    medido con el recorrido AST de
    ``.claude/rules/atributos-de-clase-de-modelo.md``
    sobre ``odoo19c: base_address_extended/models/res_city.py``::

        ResCity ['_name', '_description', '_order', '_rec_names_search']

    No sustituyen a su forma Django: ``_description`` convive con
    ``Meta.verbose_name`` y ``_order`` con ``Meta.ordering``.
    """

    _name = 'res.city'
    _description = 'City'
    _order = 'name'
    _rec_names_search = ['name', 'zipcode']

    name = fields.Char(
        max_length=120,
        help_text='Nombre de la ciudad (Odoo res.city.name).',
    )
    zipcode = fields.Char(
        max_length=16,
        blank=True,
        default='',
        help_text='Código postal (Odoo zipcode).',
    )
    #: Obligatorio sin ``ondelete`` en la fuente (``res_city.py:14``): su
    #: defecto es ``restrict``; borrar un país con ciudades falla.
    country_id = fields.Many2one(
        'base.ResCountry',
        null=False, on_delete=models.PROTECT,
        related_name='cities',
        help_text='País (Odoo country_id, requerido).',
        db_column='country_id',
    )
    state_id = fields.Many2one(
        'base.ResCountryState',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cities',
        help_text='Estado/provincia (Odoo state_id, dominio country_id).',
        db_column='state_id',
    )

    class Meta:
        db_table = 'res_city'
        ordering = ['name']
        verbose_name = 'Ciudad'
        verbose_name_plural = 'Ciudades'

    @api.depends('zipcode')
    def _compute_display_name(self):
        """≙ ``_compute_display_name``
        (``odoo19c: addons/base_address_extended/models/res_city.py:17-21``).

        Conserva el nombre de la fuente, guion bajo incluido: allá es el
        ``compute`` del campo ``display_name``, superficie interna que el ORM
        invoca. Como en la fuente, asigna ``display_name`` por registro.
        """
        for city in self:
            name = (city.name if not city.zipcode
                    else f'{city.name} ({city.zipcode})')
            city.display_name = name

    def __str__(self) -> str:
        """El nombre visible: el ``display_name`` que calcula la fuente."""
        return self.display_name
