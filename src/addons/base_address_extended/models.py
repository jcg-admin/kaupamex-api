"""Modelos de ``base_address_extended`` — catálogo de ciudades + política de país.

Portación fiel del addon ``base_address_extended`` de Odoo (18/19, modelos
idénticos salvo el rename cosmético ``City`` → ``ResCity`` en 19):

- ``ResCity`` ← ``res.city`` (``res_city.py``): ``name`` (requerido),
  ``zipcode``, ``country`` FK (requerido), ``state`` FK (dominio país).
  ``display_name`` de Odoo (``name (zipcode)``) → ``__str__``.
- ``CountryAddressPolicy`` ← ``enforce_cities`` que Odoo agrega vía
  ``_inherit = 'res.country'`` (``res_country.py``). Cross-app en Django →
  RELATED OneToOne sobre ``base.ResCountry`` (DEC-SALE-01).

El street-split (``street_name``/``street_number``/``street_number2`` que Odoo
añade a ``res.partner``) vive como servicio puro en ``services.street_split``;
su cableado como RELATED sobre la dirección del proyecto (``users.Address``) es
un nodo posterior de la espina base (cuando account/sale lo requieran).
"""
from django.db import models


class ResCity(models.Model):
    """``res.city`` — ciudad de un país (Odoo base_address_extended).

    Fiel a ``res_city.py`` (18:9-22 / 19:8-21, campos idénticos).
    """

    name    = models.CharField(
        max_length=120, help_text='Nombre de la ciudad (Odoo res.city.name).',
    )
    zipcode = models.CharField(
        max_length=16, blank=True, default='',
        help_text='Código postal (Odoo zipcode).',
    )
    country = models.ForeignKey(
        'base.ResCountry', on_delete=models.CASCADE, related_name='cities',
        help_text='País (Odoo country_id, requerido).',
    )
    state   = models.ForeignKey(
        'base.ResCountryState', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cities',
        help_text='Estado/provincia (Odoo state_id, dominio country_id).',
    )

    class Meta:
        db_table = 'res_city'
        ordering = ['name']
        verbose_name = 'Ciudad'
        verbose_name_plural = 'Ciudades'

    def __str__(self) -> str:
        # Fiel a _compute_display_name (o18/o19): 'name' o 'name (zipcode)'.
        return self.name if not self.zipcode else f'{self.name} ({self.zipcode})'


class CountryAddressPolicy(models.Model):
    """Política de dirección por país — RELATED de ``enforce_cities``.

    Odoo agrega ``enforce_cities`` a ``res.country`` vía ``_inherit``
    (``res_country.py``:9-13). En Django el ``_inherit`` cross-app se modela
    como OneToOne RELATED sobre ``base.ResCountry`` (DEC-SALE-01): si está en
    ``True``, toda dirección de ese país debe elegir una ``ResCity`` del
    catálogo.
    """

    country         = models.OneToOneField(
        'base.ResCountry', on_delete=models.CASCADE, related_name='address_policy',
        help_text='País al que aplica la política (Odoo res.country).',
    )
    enforce_cities  = models.BooleanField(
        default=False,
        help_text='Exigir ciudad del catálogo en direcciones (Odoo enforce_cities).',
    )

    class Meta:
        db_table = 'res_country_address_policy'
        verbose_name = 'Política de dirección por país'
        verbose_name_plural = 'Políticas de dirección por país'

    def __str__(self) -> str:
        return f'{self.country.name} (enforce_cities={self.enforce_cities})'
