"""Dirección estructurada — RELATED de la extensión que Odoo pone en ``res.partner``.

Odoo ``base_address_extended/models/res_partner.py`` extiende ``res.partner``
vía ``_inherit`` con ``street_name`` / ``street_number`` / ``street_number2``
(compute/inverse desde ``street``) + ``city_id`` (FK ``res.city``) +
``country_enforce_cities`` (related de ``country_id.enforce_cities``).

En este proyecto el "partner" con dirección es ``users.Address`` (no
``res.partner``). El ``_inherit`` cross-app se modela como RELATED OneToOne
(DEC-SALE-01): ``AddressStructured`` cuelga de ``users.Address`` sin inyectar
columnas en su tabla, y aloja la descomposición estructurada de la calle + el
enlace al catálogo ``res.city``.
"""
import fields
import models

from addons.base_address_extended.services import street_split


class AddressStructured(models.Model):
    """Descomposición estructurada de una ``users.Address`` (Odoo res_partner
    ``street_name``/``street_number``/``street_number2`` + ``city_id``).
    """

    address        = models.OneToOneField(
        'users.Address', on_delete=models.CASCADE, related_name='structured',
        help_text='Dirección a la que pertenece (Odoo res.partner).',
    )
    city          = fields.Many2one(
        'base_address_extended.ResCity', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='addresses',
        help_text='Ciudad del catálogo (Odoo city_id → res.city).',
    )
    street_name    = fields.Char(
        max_length=200, blank=True, default='',
        help_text='Nombre de la calle (Odoo street_name).',
    )
    street_number  = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Número exterior (Odoo street_number / House).',
    )
    street_number2 = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Número interior / puerta (Odoo street_number2 / Door).',
    )

    class Meta:
        db_table = 'res_partner_address_structured'
        verbose_name = 'Dirección estructurada'
        verbose_name_plural = 'Direcciones estructuradas'

    def __str__(self) -> str:
        return self.inverse_to_street()

    # -- Odoo _compute_street_data (street -> parts) ------------------------
    def compute_from_street(self, street):
        """Descompone ``street`` en las tres sub-partes (Odoo
        ``_compute_street_data`` → ``tools.street_split``)."""
        parts = street_split(street)
        self.street_name = parts['street_name']
        self.street_number = parts['street_number']
        self.street_number2 = parts['street_number2']
        return parts

    # -- Odoo _inverse_street_data (parts -> street) ------------------------
    def inverse_to_street(self):
        """Recompone la calle desde las sub-partes (Odoo
        ``_inverse_street_data``): ``name number`` y ``- number2`` si existe."""
        street = ((self.street_name or '') + ' ' + (self.street_number or '')).strip()
        if self.street_number2:
            street = street + ' - ' + self.street_number2
        return street

    def get_street_split(self):
        """Devuelve las tres sub-partes (Odoo ``_get_street_split``)."""
        return {
            'street_name': self.street_name,
            'street_number': self.street_number,
            'street_number2': self.street_number2,
        }

    @property
    def country_enforce_cities(self):
        """Related de ``country_id.enforce_cities`` (Odoo): la política del país
        de la ciudad enlazada. ``False`` si no hay ciudad o país sin política."""
        if self.city_id is None:
            return False
        policy = getattr(self.city.country, 'address_policy', None)
        return bool(policy and policy.enforce_cities)
