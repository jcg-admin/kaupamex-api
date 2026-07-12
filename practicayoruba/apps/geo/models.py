"""Models — apps.geo

CatalogPostalCode: catálogo nacional de códigos postales de México (SEPOMEX /
Correos de México). Espejo 1:1 de las 15 columnas oficiales del dataset, con
los nombres en inglés. Un código postal mapea a N asentamientos (colonias),
así que la clave natural de una fila es ``(postal_code, settlement_consecutive_id)``
y la PK es surrogada (SOL-016, DEC-02, H-API-PARTY-01).

``Address`` (apps.users, party model) referencia una fila de este catálogo
por su asentamiento concreto; el catálogo también alimenta el trabajo de
direcciones de envío / zonas.
"""
from django.db import models


class CatalogPostalCode(models.Model):
    """Un asentamiento (colonia) dentro de un código postal — fila del
    Catálogo Nacional de Códigos Postales (SEPOMEX)."""

    ZONE_URBANO = 'Urbano'
    ZONE_SEMIURBANO = 'Semiurbano'
    ZONE_RURAL = 'Rural'
    ZONE_CHOICES = [
        (ZONE_URBANO, 'Urbano'),
        (ZONE_SEMIURBANO, 'Semiurbano'),
        (ZONE_RURAL, 'Rural'),
    ]

    # d_codigo — CP del asentamiento (el que referencia address). No único:
    # un CP tiene N asentamientos.
    postal_code = models.CharField(
        max_length=5, db_index=True,
        verbose_name='Código postal',
        help_text='CP del asentamiento (SEPOMEX d_codigo).',
    )
    # d_asenta — nombre del asentamiento (colonia).
    settlement_name = models.CharField(max_length=64, verbose_name='Asentamiento')
    # d_tipo_asenta — tipo de asentamiento (Colonia, Fraccionamiento, ...).
    settlement_type = models.CharField(max_length=32, verbose_name='Tipo de asentamiento')
    # D_mnpio — municipio / alcaldía.
    municipality = models.CharField(max_length=64, verbose_name='Municipio')
    # d_estado — estado.
    state = models.CharField(max_length=40, verbose_name='Estado')
    # d_ciudad — ciudad (puede ir vacío).
    city = models.CharField(max_length=64, blank=True, default='', verbose_name='Ciudad')
    # d_CP — CP de la oficina postal administradora.
    office_postal_code = models.CharField(max_length=5, verbose_name='CP de oficina')
    # c_estado — clave del estado.
    state_code = models.CharField(max_length=2, verbose_name='Clave de estado')
    # c_oficina — clave de la oficina postal.
    office_code = models.CharField(max_length=5, verbose_name='Clave de oficina')
    # c_CP — clave interna de CP (vacío en el export oficial; se conserva 1:1).
    postal_code_internal_code = models.CharField(
        max_length=4, blank=True, default='', verbose_name='Clave interna de CP',
    )
    # c_tipo_asenta — clave del tipo de asentamiento.
    settlement_type_code = models.CharField(max_length=2, verbose_name='Clave tipo de asentamiento')
    # c_mnpio — clave del municipio.
    municipality_code = models.CharField(max_length=3, verbose_name='Clave de municipio')
    # id_asenta_cpcons — ID consecutivo del asentamiento dentro del CP.
    settlement_consecutive_id = models.CharField(max_length=4, verbose_name='ID consecutivo de asentamiento')
    # d_zona — zona.
    zone = models.CharField(max_length=12, choices=ZONE_CHOICES, verbose_name='Zona')
    # c_cve_ciudad — clave de la ciudad (puede ir vacío).
    city_code = models.CharField(max_length=2, blank=True, default='', verbose_name='Clave de ciudad')

    class Meta:
        db_table = 'catalog_postal_code'
        verbose_name = 'Código postal (SEPOMEX)'
        verbose_name_plural = 'Códigos postales (SEPOMEX)'
        constraints = [
            models.UniqueConstraint(
                fields=['postal_code', 'settlement_consecutive_id'],
                name='uq_catalog_postal_code_natural_key',
            ),
        ]
        indexes = [
            models.Index(fields=['postal_code', 'settlement_name']),
        ]

    def __str__(self):
        return f'{self.postal_code} — {self.settlement_name} ({self.municipality}, {self.state})'
