"""Registro L0 de bases por empresa — ``CompanyDatabase`` (SOL-091, T-091-02).

Catálogo *"qué bases ``company_<N>_db`` existen"* (``code`` -> ``db_name`` ->
``status``). Vive en la base ``default`` (plano de control L0). Es el equivalente
Django del listado de bases de Odoo (``service/db.list_dbs`` -> ``pg_database``;
``http.py`` ``db_list``); el loader dinámico de ``DATABASES`` (T-091-04) lo lee
para componer las conexiones por empresa.

**NO** es la ``Company``/res.company (el perfil L1 que vive DENTRO de cada
``company_<N>_db``): es sólo el catálogo de bases. Ver
``analisis-adaptacion-odoo-multidb`` (F-ODOO-01/02) y
``at-aislamiento-multi-db-per-company`` (D-091-1).
"""
from django.db import models


class CompanyDatabase(models.Model):
    """Una fila por base de empresa provisionada en el operador L0."""

    STATUS_TRIAL = 'trial'
    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_TRIAL, 'Trial'),
        (STATUS_ACTIVE, 'Activa'),
        (STATUS_SUSPENDED, 'Suspendida'),
        (STATUS_CANCELLED, 'Cancelada'),
    ]
    # Estados en los que la base debe existir y aceptar migraciones (empresa
    # viva). Mismo vocabulario canónico que Company.status (DEC-T7).
    _PROVISIONABLE = frozenset({STATUS_TRIAL, STATUS_ACTIVE})

    code = models.CharField(
        max_length=63, unique=True,
        help_text='Slug estable de la empresa; llave del alias company_<code>_db.',
    )
    db_name = models.CharField(
        max_length=63, unique=True,
        help_text='Nombre físico de la base MariaDB (p. ej. company_1_db).',
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_TRIAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orm_company_database'
        verbose_name = 'Registro de base por empresa (L0)'
        verbose_name_plural = 'Registro de bases por empresa (L0)'
        ordering = ['code']

    def __str__(self):
        return '%s -> %s (%s)' % (self.code, self.db_name, self.status)

    @property
    def is_provisionable(self):
        """``True`` si la empresa está viva (trial/active) — su base se
        crea/migra; ``False`` en suspended/cancelled."""
        return self.status in self._PROVISIONABLE
