"""``res.city`` — ciudad de un país (Odoo ``base_address_extended``).

Portación fiel de ``res_city.py`` (18:9-22 / 19:8-21, campos idénticos; en 19 la
clase se renombró ``City`` → ``ResCity``, sólo cosmético).
"""
import fields
import models


class ResCity(models.Model):
    """``res.city`` — ciudad de un país.

    ``name`` (requerido), ``zipcode``, ``country`` FK (requerido), ``state`` FK
    (dominio país).

    Los cuatro atributos de clase que la fuente declara se portan verbatim —
    medido con el recorrido AST de ``.claude/rules/atributos-de-clase-de-modelo.md``
    sobre ``odoo19c: base_address_extended/models/res_city.py``::

        ResCity ['_name', '_description', '_order', '_rec_names_search']

    No sustituyen a su forma Django: ``_description`` convive con
    ``Meta.verbose_name`` y ``_order`` con ``Meta.ordering``.
    """

    _name = 'res.city'
    _description = 'City'
    _order = 'name'
    _rec_names_search = ['name', 'zipcode']

    name    = fields.Char(
        max_length=120, help_text='Nombre de la ciudad (Odoo res.city.name).',
    )
    zipcode = fields.Char(
        max_length=16, blank=True, default='',
        help_text='Código postal (Odoo zipcode).',
    )
    country_id = fields.Many2one(
        'base.ResCountry', on_delete=models.CASCADE, related_name='cities',
        help_text='País (Odoo country_id, requerido).',
        db_column='country_id',
    )
    state_id   = fields.Many2one(
        'base.ResCountryState', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cities',
        help_text='Estado/provincia (Odoo state_id, dominio country_id).',
        db_column='state_id',
    )

    class Meta:
        db_table = 'res_city'
        ordering = ['name']
        verbose_name = 'Ciudad'
        verbose_name_plural = 'Ciudades'

    def _compute_display_name(self):
        """≙ ``_compute_display_name`` (``odoo19c: res_city.py:17-21``).

        Conserva el nombre de la fuente, guion bajo incluido: allá es el
        ``compute`` del campo ``display_name``, es decir superficie interna que
        el ORM invoca. Quitarle el guion promovería a API pública un contrato
        que la fuente nunca ofreció.

        La fuente itera ``for city in self`` porque su ``self`` es un recordset
        y asigna a ``city.display_name``; aquí ``self`` es una instancia y el
        valor se **devuelve**, que es lo que ``__str__`` consume.
        """
        return self.name if not self.zipcode else f'{self.name} ({self.zipcode})'

    def __str__(self) -> str:
        """El nombre visible — lo sirve :meth:`_compute_display_name`."""
        return self._compute_display_name()
