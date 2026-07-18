"""Models — addons.authz_menu (catálogo de navegación, DEC-08/09).

App de feature opcional separada del core ``addons.authz`` (SOL-094 frente B,
DEC-01), análoga a ``ir.ui.menu`` de Odoo: el árbol de menú es un modelo de
datos aparte del motor de permisos. La FK ``required_capability`` apunta a
``authz.Capability`` (referencia por string para no acoplar la carga de apps).
La tabla física ``authz_menu_item`` NO cambia: la mudanza entre app labels se
hace con ``SeparateDatabaseAndState`` (migración ``authz.0012`` la borra del
*state* de ``authz``; ``0001`` de esta app la re-declara).
"""
from django.db import models

from core.models import TimeStampedModel


class MenuItem(TimeStampedModel):
    """Entrada del menú del panel admin (DEC-08/09).

    Proyección UX del catálogo de capacidades: el árbol de navegación se
    **persiste** (``authz_menu_item``, adjacency list vía ``parent``) y cada
    entrada se etiqueta con la ``Capability`` requerida para verla. La sección
    es un ``MenuItem`` de nivel 0 (``parent`` null, sin ``route``); sus hijos
    llevan la capacidad del dominio.

    NO es autorización: el candado real es ``HasCapability`` en cada vista
    (:ref:`analisis-enforcement-hascapability-isowner`). El menú solo decide
    **qué se muestra**; el endpoint ``me/menu/`` poda el árbol con
    ``resolve_capabilities`` para no filtrar destinos inaccesibles.

    ``audience`` separa el menú del **panel admin** del menú de **cuenta del
    comprador** (DEC-AUTHZ-BUYER): ambos son registro-dirigidos y podados por
    capacidad, pero se sirven por separado (``me/menu/?audience=account``). Así
    agregar una entrada de cualquiera de los dos menús es sembrar una fila —
    sin tocar la navegación del UI (que ya no lleva la lista fija ni la
    negación).
    """
    AUDIENCE_ADMIN = 'admin'
    AUDIENCE_ACCOUNT = 'account'
    AUDIENCE_CHOICES = [
        (AUDIENCE_ADMIN, 'Panel admin'),
        (AUDIENCE_ACCOUNT, 'Cuenta del comprador'),
    ]

    audience = models.CharField(
        max_length=10, choices=AUDIENCE_CHOICES, default=AUDIENCE_ADMIN,
        db_index=True, verbose_name='Audiencia',
        help_text="'admin' = panel; 'account' = menú de cuenta del comprador.",
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children', verbose_name='Sección padre',
        help_text='Null = sección de nivel 0.',
    )
    key = models.CharField(
        max_length=80, unique=True, verbose_name='Clave',
        help_text='Slug estable del item (para seed idempotente).',
    )
    label = models.CharField(max_length=80, verbose_name='Etiqueta')
    route = models.CharField(
        max_length=160, blank=True, default='', verbose_name='Ruta SPA',
        help_text="Ruta del router React (p.ej. '/admin/products'). Vacío en secciones.",
    )
    icon = models.CharField(max_length=40, blank=True, default='', verbose_name='Icono')
    order = models.PositiveIntegerField(default=0, verbose_name='Orden')
    required_capability = models.ForeignKey(
        'authz.Capability', on_delete=models.PROTECT, null=True, blank=True,
        related_name='menu_items', verbose_name='Capacidad requerida',
        help_text='Null = visible para cualquier admin (p.ej. secciones).',
    )
    is_active = models.BooleanField(default=True, verbose_name='Activa')

    class Meta:
        db_table = 'authz_menu_item'
        verbose_name = 'Entrada de menú'
        verbose_name_plural = 'Entradas de menú'
        ordering = ['parent_id', 'order', 'id']
        indexes = [
            models.Index(fields=['parent', 'order']),
        ]

    def __str__(self):
        return f'{self.key} ({self.label})'
