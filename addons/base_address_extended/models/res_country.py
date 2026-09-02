"""``res.country`` extendido — ``enforce_cities`` (Odoo ``base_address_extended``).

Odoo agrega ``enforce_cities`` a ``res.country`` vía ``_inherit`` cross-app
(``res_country.py``:9-13). En Django el ``_inherit`` cross-app se modela como
RELATED OneToOne sobre ``base.ResCountry`` (DEC-SALE-01: Django no inyecta
columnas cross-app).
"""
import fields
import models


class CountryAddressPolicy(models.Model):
    """Política de dirección por país — RELATED de ``enforce_cities``.

    Si está en ``True``, toda dirección de ese país debe elegir una ``ResCity``
    del catálogo (Odoo ``enforce_cities``).
    """

    #: ≙ ``_inherit = 'res.country'`` de la fuente
    #: (``odoo19c: base_address_extended/models/res_country.py:8``). Se declara
    #: verbatim aunque el mecanismo diverja: allá inyecta la columna en
    #: ``res_country``, aquí la extensión vive en una tabla RELATED
    #: (DEC-SALE-01). El atributo nombra a quién extiende, que es la
    #: información que la divergencia de almacén no debe borrar
    #: (``atributos-de-clase-de-modelo.md``). Mismo idioma que
    #: ``AddressStructured`` en el archivo hermano ``res_partner.py``.
    _inherit = 'res.country'

    country         = models.OneToOneField(
        'base.ResCountry', on_delete=models.CASCADE, related_name='address_policy',
        help_text='País al que aplica la política (Odoo res.country).',
    )
    enforce_cities  = fields.Boolean(
        default=False,
        help_text='Exigir ciudad del catálogo en direcciones (Odoo enforce_cities).',
    )

    class Meta:
        db_table = 'res_country_address_policy'
        verbose_name = 'Política de dirección por país'
        verbose_name_plural = 'Políticas de dirección por país'

    def __str__(self) -> str:
        return f'{self.country.name} (enforce_cities={self.enforce_cities})'
