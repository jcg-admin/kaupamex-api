"""Modelo ``website.menu`` — menú de la cara pública.

Adaptación de Odoo ``addons/website/models/website_menu.py``
(``odoo-tools@bf077302``, ``odoo19c:``). Mismo nombre de archivo que la
referencia.

La referencia mantiene **dos modelos de menú separados** en vez de un campo de
audiencia: ``ir.ui.menu`` para el backoffice (en ``base``) y ``website.menu``
para el sitio (aquí). Este árbol replica esa partición.

Contrato medido de la fuente (AST, 346 líneas): **1 clase, 4 atributos de
clase, 15 campos, 15 métodos**. La tabla de cobertura vive en el docstring de
la clase.
"""
from django.apps import apps
from django.db import models

from addons.base.models import TimeStampedModel
from addons.base.models.ir_ui_menu import (
    CapabilityPrunedMenuManager,
    _bump_menu_epoch,
)
from exceptions import UserError
from tools.translate import _


def default_sequence():
    """El valor inicial de ``sequence`` — ≙ ``default=_default_sequence``.

    Función de módulo con nombre y no referencia directa al ``classmethod``
    porque Django serializa los ``default=`` dentro de la migración, y un
    ``classmethod`` de una clase que aún no existe al evaluar el cuerpo no se
    puede citar ahí (mismo patrón que los ``default_*`` de ``website.py``).
    """
    return WebsiteMenu._default_sequence()


class WebsiteMenu(TimeStampedModel):
    """Menú de la cara pública (``website.menu``).

    Adaptación de Odoo ``addons/website/models/website_menu.py``
    (``odoo-tools@bf077302``, ``odoo19c:``). La referencia mantiene **dos
    modelos de menú separados** en vez de un campo de audiencia:
    ``ir.ui.menu`` para el backoffice (en ``base``) y ``website.menu`` para el
    sitio (aquí). Este árbol replica esa partición: aquí vive el menú de la
    **cuenta del comprador** (DEC-AUTHZ-BUYER) y, desde #543, el árbol de
    menús **por sitio** que ``Website.copy_menu_hierarchy`` clona.

    Cobertura contra la fuente — 15 campos, 15 métodos, 4 atributos de clase
    =========================================================================

    Los 4 atributos de clase de la fuente (``:16-21``) se declaran verbatim
    abajo. ``_parent_store`` no tiene motor en este ORM: su invariante —la
    ruta materializada ``parent_path``— se sostiene en ``save()``, el mismo
    mecanismo declarado en ``stock_location.py`` (tarea #191 lo promueve a
    mecanismo del ORM).

    Campos (fuente ``:41-57``):

    - ``name`` · ``sequence`` · ``parent_id`` → idénticos (``parent`` con
      ``CASCADE``, que es el ``ondelete`` de la referencia — nota la
      diferencia con ``ir.ui.menu``, que usa ``restrict``). ``sequence``
      lleva el ``default=_default_sequence`` de la fuente (``:46``).
    - ``url`` → ``route``: en la referencia es una URL del sitio; aquí es la
      ruta del router React. Mismo papel. El tramo ``compute="_compute_url"``
      NO se porta — depende de ``page_id``/``is_mega_menu`` (abajo).
    - ``website_id`` (``:47``) → ``website``: **portado en #543** (el sufijo
      ``_id`` se cae en los FK, :ref:`h-api-579`; Django ya emite la columna
      ``website_id``). Revierte la exclusión que este archivo declaraba —
      ``Website.copy_menu_hierarchy`` existe para poblar justo este campo, y
      sin él quedaba bloqueado (B2, #535). ``null=True`` es el contrato de la
      fuente: un menú sin sitio es la plantilla que ``copy_menu_hierarchy``
      clona por sitio.
    - ``child_id`` (One2many, ``:49``) → ``related_name='child'`` del FK.
    - ``parent_path`` (``:50``) → idéntico; lo materializa ``save()``.
    - ``new_window`` (``:45``) → idéntico; no depende de nada ausente.
    - ``group_ids`` (M2M a ``res.groups``) → ``group`` FK singular a
      ``authz.Capability``, igual que en ``base.IrUiMenu`` y por la misma
      razón (DEC-11).
    - ``is_visible`` (computed, ``:51``) → lo resuelve el manager al podar;
      no se persiste.
    - ``page_id`` (``:43``) → ``page``: **portado en #104** (el sufijo
      ``_id`` se cae en los FK, :ref:`h-api-579`; la columna sigue siendo
      ``page_id``). Su reverso es el ``menu_ids`` de ``website.page``. El
      FK va por cadena (``'website.WebsitePage'``) para conservar el sentido
      del import página → menú.
    - ``controller_page_id`` (``:44``) → BLOQUEADO por
      ``website.controller.page`` — el modelo no existe en este árbol
      (0 clases, medido en el porte de ``website.py``).
    - ``is_mega_menu`` · ``mega_menu_content`` · ``mega_menu_classes``
      (``:55-57``) → **no se portan**: pertenecen al editor de sitios de
      Odoo, que este árbol no tiene (el cliente es un SPA React). Divergencia
      declarada, no bloqueo.
    - ``key`` · ``active`` · ``web_icon`` → extensiones propias: ``key`` es
      el ``xmlid`` (identificador estable para el seed idempotente).

    Métodos (fuente ``:23-291``) — 5 portados, 10 declarados fuera:

    ========================================  =====================================
    Fuente                                    Aquí
    ========================================  =====================================
    ``_default_sequence`` (``:23``)           portado (classmethod + ``default=``)
    ``_compute_display_name`` (``:61``)       portado — el contexto
                                              ``display_website`` es el parámetro
                                              ``display_website``; el escalón del
                                              grupo multi-sitio necesita el
                                              registro de datos por módulo (#467)
    ``_validate_parent_menu`` (``:80``)       portado — 2 de sus 3 reglas; la de
                                              mega menú cae con los campos no
                                              portados (arriba). Lo invoca
                                              ``clean()``
    ``_clean_url`` (``:198``)                 portado — lee ``route`` (la
                                              equivalencia ``url`` → ``route`` de
                                              arriba)
    ``get_tree`` (``:266``)                   portado — sin la clave
                                              ``is_mega_menu`` (campo no portado);
                                              la portada del sitio se resuelve con
                                              la consulta de
                                              ``Website._compute_menu``
    ``_compute_field_is_mega_menu`` (``:28``) no — mega menú (divergencia SPA)
    ``_set_field_is_mega_menu`` (``:32``)     no — mega menú (divergencia SPA)
    ``_compute_url`` (``:72``)                no — necesita ``page_id`` y
                                              ``is_mega_menu``. Sucesor: #104
    ``create`` (``:111``)                     no — duplica el menú por sitio vía
                                              ``env.ref('website.main_menu')``:
                                              necesita el registro de datos por
                                              módulo. Sucesor: #467
    ``write`` (``:154``)                      no — ``env.ref`` del grupo designer
                                              + caché de plantillas. Sucesor: #467
    ``unlink`` / ``_unlink_except_master_tags``
    (``:163`` / ``:174``)                     no — ambos giran sobre
                                              ``env.ref('website.main_menu')``.
                                              Sucesor: #467
    ``_compute_visible`` (``:179``)           no — aquí poda el manager
                                              (divergencia declarada)
    ``_is_active`` (``:209``)                 no — necesita
                                              ``ir.http._unslug_url`` (medido: 0
                                              hits en ``ir_http.py``). Sucesor:
                                              #545
    ``save`` (``:291``, endpoint del editor)  no — necesita ``website.page`` y
                                              ``ir.http._match``. Sucesores:
                                              #104 / #545. OJO: su nombre choca
                                              con el ``save()`` de instancia de
                                              Django; al portarlo necesitará su
                                              propia decisión de forma
    ========================================  =====================================

    El podado lo hace ``CapabilityPrunedMenuManager``, compartido con
    ``base.IrUiMenu`` — ver allí por qué se comparte pese a que la referencia
    tiene dos implementaciones.
    """

    # Atributos de clase de modelo — los cuatro que la referencia declara
    # (``odoo19c: addons/website/models/website_menu.py:16-21``), verbatim.
    _name = 'website.menu'
    _description = "Website Menu"
    _parent_store = True
    _order = "sequence, id"

    name = models.CharField(max_length=80, verbose_name='Menú')
    active = models.BooleanField(default=True, verbose_name='Activa')
    sequence = models.PositiveIntegerField(
        default=default_sequence, verbose_name='Secuencia',
        help_text='Odoo sequence (default=_default_sequence): el menú nuevo '
                  'entra al final.',
    )
    new_window = models.BooleanField(
        default=False, verbose_name='Ventana nueva',
        help_text='Odoo new_window. Abrir el destino en una pestaña nueva.',
    )
    website = models.ForeignKey(
        'website.Website', on_delete=models.CASCADE, null=True, blank=True,
        related_name='menus', verbose_name='Sitio',
        help_text='Odoo website_id (ondelete=cascade). Null = menú plantilla '
                  'sin sitio, el que copy_menu_hierarchy clona por sitio.',
    )
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='child', verbose_name='Menú padre',
        help_text='Null = sección de nivel 0.',
    )
    parent_path = models.CharField(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Ruta del árbol',
        help_text='Odoo parent_path (index=True). Ruta materializada '
                  '«1/4/9/»; la mantiene save() — es el invariante de '
                  '_parent_store, cuyo motor este ORM no tiene (#191).',
    )
    group = models.ForeignKey(
        'authz.Capability', on_delete=models.PROTECT, null=True, blank=True,
        related_name='website_menu_items', verbose_name='Capacidad requerida',
        help_text=(
            'Odoo group_ids. Lleva la capacidad que enforce el endpoint del '
            'destino, no la del ítem. Null en secciones.'
        ),
    )
    page = models.ForeignKey(
        'website.WebsitePage', on_delete=models.CASCADE, null=True,
        blank=True, db_index=True, related_name='menu_ids',
        db_column='page_id', verbose_name='Página relacionada',
        help_text="Odoo page_id ('website.page', ondelete='cascade', "
                  'index=btree_not_null). Null = el menú apunta a una ruta, '
                  'no a una página.',
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
        # ≙ ``_order = "sequence, id"`` (``odoo19c: :21``).
        ordering = ['sequence', 'id']
        verbose_name = 'Entrada de menú del sitio'
        verbose_name_plural = 'Entradas de menú del sitio'
        indexes = [
            models.Index(fields=['parent', 'sequence']),
        ]

    def __str__(self):
        return self.name

    # ── Defaults ─────────────────────────────────────────────────────────────

    @classmethod
    def _default_sequence(cls):
        """≙ ``_default_sequence`` (``odoo19c: :23-25``).

        La secuencia más alta existente, o 0: el menú nuevo entra al final del
        árbol, que es lo que la fuente obtiene con
        ``search([], limit=1, order="sequence DESC")``.
        """
        last = cls.objects.order_by('-sequence', '-pk').first()
        return (last.sequence or 0) if last else 0

    # ── Computes ─────────────────────────────────────────────────────────────

    def _compute_display_name(self, display_website=False):
        """≙ ``_compute_display_name`` (``odoo19c: :61-69``).

        El nombre del menú, con el sitio entre corchetes cuando se pide
        desambiguar (``Tienda [Sitio B]``).

        Dos divergencias declaradas: (1) el contexto ``display_website`` de la
        fuente es aquí el parámetro homónimo — mismo dato, canal explícito;
        (2) el escalón ``user.has_group('website.group_multi_website')`` no se
        porta: resolver un grupo por external ID necesita el registro de datos
        por módulo (#467).
        """
        menu_name = self.name or ""
        if display_website and self.website_id:
            menu_name += f' [{self.website.name}]'
        return menu_name

    def _compute_parent_path(self):
        """Materializa ``parent_path`` — ≙ el ``_parent_store`` de la referencia.

        El formato es el suyo: los ids de los ancestros y el propio, separados
        por ``/`` y con ``/`` final, de modo que «descendiente de» sea un
        ``startswith``. Mismo mecanismo declarado que ``stock_location.py``;
        promoverlo a motor del ORM es la tarea #191.

        **Divergencia declarada frente a ``_parent_store``:** el motor de la
        referencia re-materializa también a los **descendientes** al mover un
        nodo; aquí sólo se recalcula el propio registro, y cada descendiente
        se corrige en su siguiente ``save()``. Con la profundidad máxima de
        dos niveles que ``_validate_parent_menu`` impone, el desfase posible
        es de un nivel. El cierre completo es el motor de #191 — misma
        limitación, mismo sucesor que ``stock_location.py``.
        """
        if self.pk is None:
            return self.parent_path
        if self.parent_id:
            root = self.parent.parent_path or self.parent._compute_parent_path()
            self.parent_path = f'{root}{self.pk}/'
        else:
            self.parent_path = f'{self.pk}/'
        return self.parent_path

    # ── Restricciones ────────────────────────────────────────────────────────

    def _validate_parent_menu(self):
        """≙ ``_validate_parent_menu`` (``odoo19c: :79-108``).

        Reglas de la fuente que se conservan:

        - un menú no supera los dos niveles de anidación;
        - un menú con hijos no puede colgarse como submenú (ni bajo un padre
          que ya es submenú, ni conservando nietos).

        La tercera regla de la fuente —un mega menú no tiene padre ni hijos—
        cae con los campos ``is_mega_menu``/``mega_menu_content``, no portados
        (editor de sitios; ver la tabla de cobertura de la clase).
        """
        parent_menu = self.parent
        level = 0
        current_menu = parent_menu
        while current_menu is not None:
            level += 1
            current_menu = current_menu.parent
            if level > 2:
                raise UserError(_(
                    "Menus cannot have more than two levels of hierarchy."))

        if parent_menu is not None and self.pk is not None:
            has_children = self.child.exists()
            has_grandchildren = self.child.filter(child__isnull=False).exists()
            if has_children and (parent_menu.parent_id or has_grandchildren):
                raise UserError(_(
                    "Menus with child menus cannot be added as a submenu."))

    def clean(self):
        """Puerta de la ``@api.constrains`` de la fuente.

        Django concentra la validación de instancia en ``clean()``; el
        ``_validate_parent_menu`` conserva su nombre y su cuerpo, y aquí se
        invoca — mismo patrón que ``website.py``.
        """
        super().clean()
        self._validate_parent_menu()

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def save(self, *args, **kwargs):
        """Persistencia + los dos invariantes que la fuente delega a su ORM.

        1. ``parent_path`` se recalcula **después** del ``INSERT`` porque la
           ruta incluye el propio ``id``, y se persiste con ``update_fields``
           para no reescribir el resto (mismo esquema que
           ``stock_location.py``).
        2. El epoch del menú se bumpea para invalidar la caché del manager
           compartido con ``base.IrUiMenu``.
        """
        super().save(*args, **kwargs)
        stored_path = self.parent_path
        if self._compute_parent_path() != stored_path:
            super().save(update_fields=['parent_path'])
        _bump_menu_epoch()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        _bump_menu_epoch()
        return result

    # ── Helpers de URL y árbol ───────────────────────────────────────────────

    def _clean_url(self):
        """≙ ``_clean_url`` (``odoo19c: :198-207``).

        Normaliza la ruta con la heurística de la fuente: un valor con ``@``
        se convierte en ``mailto:``, y uno que no empieza por ``/`` ni por
        ``http`` (y no es un ancla ``#top``/``#bottom``) se vuelve relativo.
        Lee ``route``, que es el ``url`` de la fuente (equivalencia declarada
        en la tabla de cobertura).
        """
        url = self.route
        if url and not url.startswith('/') and url not in ('#top', '#bottom'):
            if '@' in self.route:
                if not self.route.startswith('mailto'):
                    url = 'mailto:%s' % self.route
            elif not self.route.startswith('http'):
                url = '/%s' % self.route
        return url

    @classmethod
    def get_tree(cls, website_id, menu_id=None):
        """≙ ``get_tree`` (``odoo19c: :265-288``).

        El árbol de menús del sitio como dicts anidados, con el mismo esquema
        de la fuente (``fields`` + ``children`` + ``is_homepage``) salvo la
        clave ``is_mega_menu``, cuyo campo no está portado (divergencia
        declarada en la tabla de cobertura). ``url`` emite ``route`` por la
        equivalencia ya declarada.

        Sin ``menu_id``, la raíz es la que ``Website._compute_menu`` resuelve:
        el primer menú sin padre del sitio. Se consulta aquí directamente en
        vez de leer el campo no almacenado ``menu`` del sitio para no acoplar
        este método al mecanismo ``NonStored``.

        ``Website`` se resuelve por ``apps.get_model`` — importarlo aquí sería
        circular (``website.py`` importa este módulo). Es una llamada a
        función, no un import perezoso, mismo criterio que
        ``stock_location.py``.
        """
        Website = apps.get_model('website', 'Website')
        website = Website.objects.filter(pk=website_id).first()
        homepage_url = (website.homepage_url if website else None) or '/'

        def make_tree(node):
            return {
                'fields': {
                    'id': node.pk,
                    'name': node.name,
                    'url': node.route,
                    'new_window': node.new_window,
                    'sequence': node.sequence,
                    'parent_id': node.parent_id,
                },
                'children': [make_tree(child) for child in node.child.all()],
                'is_homepage': node.route == homepage_url,
            }

        if menu_id:
            menu = cls.objects.filter(pk=menu_id).first()
        else:
            menu = (cls.objects
                    .filter(website_id=website_id, parent__isnull=True)
                    .order_by('sequence', 'pk')
                    .first())
        return make_tree(menu) if menu is not None else None

    @property
    def is_section(self):
        """Un nodo sin ``route`` es contenedor: no se muestra por sí solo."""
        return not self.route
