"""Historial de búsquedas del sitio.

El pariente más cercano en la referencia es ``website.track`` (páginas
visitadas por ``website.visitor``), que registra navegación, no consultas.
No es el mismo modelo; ver ``alinear-addon-website-referencia``.
"""
from django.conf import settings
from django.db import models

from addons.base.models import TimeStampedModel


class SearchEntry(TimeStampedModel):
    """Append-only search history entry."""
    user           = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='search_entries',
    )
    query          = models.CharField(max_length=200)
    normalized_query = models.CharField(max_length=200, db_index=True)
    results_count  = models.PositiveIntegerField(default=0)

    class Meta:
        db_table     = 'search_history_entry'
        ordering     = ['-created_at']
        verbose_name = 'Entrada de historial de busqueda'

    def __str__(self):
        return f'{self.user.email}: {self.normalized_query!r}'


class WebsiteMenu(TimeStampedModel):
    """Menú de la cara pública (``website.menu``).

    Adaptación de Odoo ``addons/website/models/website_menu.py``
    (``odoo-tools@bf077302``, ``odoo19c:``). La referencia mantiene **dos
    modelos de menú separados** en vez de un campo de audiencia:
    ``ir.ui.menu`` para el backoffice (en ``base``) y ``website.menu`` para el
    sitio (aquí). Este árbol replica esa partición: aquí vive el menú de la
    **cuenta del comprador** (DEC-AUTHZ-BUYER).

    Procedencia de los campos:

    - ``name`` · ``sequence`` · ``parent_id`` → idénticos (``parent`` con
      ``CASCADE``, que es el ``ondelete`` de la referencia — nota la diferencia
      con ``ir.ui.menu``, que usa ``restrict``).
    - ``url`` → ``route``: en la referencia es una URL del sitio; aquí es la
      ruta del router React. Mismo papel.
    - ``group_ids`` (M2M a ``res.groups``) → ``group`` FK singular a
      ``authz.Capability``, igual que en ``base.IrUiMenu`` y por la misma razón
      (DEC-11).
    - ``website_id`` → **no se porta**: la referencia lo usa para servir varios
      sitios desde una instancia; aquí el equivalente de esa separación es la
      ``Company`` (L1), y el menú de cuenta no está segmentado por sitio.
    - ``page_id`` · ``controller_page_id`` · ``new_window`` · ``mega_menu_*``
      → **no se portan**: pertenecen al editor de sitios de Odoo, que este
      árbol no tiene (el cliente es un SPA React).
    - ``is_visible`` (computed) → lo resuelve el manager al podar; no se
      persiste.
    - ``key`` → extensión propia, mismo papel que el ``xmlid``: identificador
      estable para el seed idempotente.

    El podado lo hace ``CapabilityPrunedMenuManager``, compartido con
    ``base.IrUiMenu`` — ver allí por qué se comparte pese a que la referencia
    tiene dos implementaciones.
    """

    name = models.CharField(max_length=80, verbose_name='Menú')
    active = models.BooleanField(default=True, verbose_name='Activa')
    sequence = models.PositiveIntegerField(default=10, verbose_name='Secuencia')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='child', verbose_name='Menú padre',
        help_text='Null = sección de nivel 0.',
    )
    group = models.ForeignKey(
        'authz.Capability', on_delete=models.PROTECT, null=True, blank=True,
        related_name='website_menu_items', verbose_name='Capacidad requerida',
        help_text=(
            'Odoo group_ids. Lleva la capacidad que enforce el endpoint del '
            'destino, no la del ítem. Null en secciones.'
        ),
    )
    route = models.CharField(
        max_length=160, blank=True, default='', verbose_name='Ruta SPA',
        help_text="Odoo url. Ruta del router React (p.ej. '/account/orders').",
    )
    web_icon = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Icono',
    )
    key = models.CharField(
        max_length=80, unique=True, verbose_name='Clave',
        help_text='Slug estable del item, para seed idempotente.',
    )

    objects = CapabilityPrunedMenuManager()

    class Meta:
        db_table = 'website_menu'
        ordering = ['sequence', 'id']
        verbose_name = 'Entrada de menú del sitio'
        verbose_name_plural = 'Entradas de menú del sitio'
        indexes = [
            models.Index(fields=['parent', 'sequence']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        _bump_menu_epoch()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        _bump_menu_epoch()
        return result

    @property
    def is_section(self):
        """Un nodo sin ``route`` es contenedor: no se muestra por sí solo."""
        return not self.route
