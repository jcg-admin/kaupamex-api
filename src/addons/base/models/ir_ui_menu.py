"""Modelo ``ir.ui.menu`` — árbol de navegación podado por permisos.

Adaptación fiel de Odoo ``odoo/addons/base/models/ir_ui_menu.py``
(``odoo-tools@bf077302``, ``odoo19c:``). Vive en ``base`` por la misma razón
que allá: el árbol de menú es un **modelo de datos del núcleo**, no una feature
opcional.

**El mecanismo vive en el modelo, no en el controlador.** En la referencia,
``_visible_menu_ids`` / ``_filter_visible_menus`` / ``load_menus`` son métodos
de ``ir.ui.menu``; el controlador (``web/controllers/home.py:85``) es de tres
líneas y sólo llama ``request.env["ir.ui.menu"].load_web_menus(...)``. Aquí el
análogo de "método a nivel de conjunto" es el **Manager**, así que los tres
viven en ``CapabilityPrunedMenuManager`` y la vista DRF vuelve a ser un thin
controller.

**Procedencia de cada campo** (izquierda la referencia, derecha lo nuestro):

===========================  ==================================================
``ir.ui.menu``               ``base.IrUiMenu``
===========================  ==================================================
``name``                     ``name`` — idéntico
``active``                   ``active`` — idéntico
``sequence`` (default 10)    ``sequence`` — idéntico
``parent_id`` (restrict)     ``parent`` — ``PROTECT`` es el ``ondelete``
                             ``restrict`` de la referencia
``child_id`` (One2many)      ``related_name='child'``
``web_icon``                 ``web_icon`` — idéntico
``complete_name`` (computed) ``complete_name`` — property, misma semántica y
                             mismo corte por nivel
``group_ids`` M2M            ``group`` FK **singular** → ``authz.Capability``
                             (DEC-11: aquí se autoriza por capacidad, no por
                             grupo; y una entrada de menú abre **una** cosa)
``action`` (Reference a
``ir.actions.*``)            ``route`` — la ruta del SPA. **No** se renombra a
                             ``action``: un campo con el nombre de la
                             referencia pero con contenido estructuralmente
                             distinto engaña más de lo que documenta
``parent_path``              no se porta — sostiene ``_parent_store``, la
                             optimización de búsqueda jerárquica del ORM de
                             Odoo, que Django no tiene
``web_icon_data`` (Binary)   no se porta — el SPA resuelve el icono por nombre;
                             la referencia lo embebe en base64 en el payload
—                            ``key`` — cumple el papel del ``xmlid`` de Odoo:
                             identificador estable para el seed idempotente
===========================  ==================================================

**Este modelo es SÓLO el menú del backoffice.** La referencia no tiene ningún
campo de audiencia en ``ir.ui.menu`` (medido: 0 hits de
``audience``/``portal``/``frontend``/``backend``); separa por **modelo
distinto** — el menú de la cara pública es ``website.menu``, en el addon
``website``. Aquí se replica esa partición: el menú de la cuenta del comprador
vive en ``website.WebsiteMenu``. El campo ``audience`` que tenía el modelo
anterior era una invención nuestra que colapsaba los dos.

**Sobre el gate y el destino.** La referencia declara en el ``help`` de
``group_ids``: *"If this field is empty, Odoo will compute visibility based on
the related object's read access."* El gate declarativo es un **pre-filtro**;
la visibilidad real la decide el acceso al **destino** — ``_visible_menu_ids``
resuelve el ``action``, saca su modelo y llama
``ir.model.access.check(model, 'read')``. **No hay un segundo campo**, y aquí
tampoco: ``group`` lleva la capacidad que enforce el endpoint de ``route``, no
la del ítem. Así lo siembra ``seed_menu``.
"""
from django.core.cache import cache
from django.db import models

from addons.base.models.timestamped_mixin import TimeStampedModel

_MENU_CACHE_PREFIX = 'ir_ui_menu:visible'
_MENU_CACHE_EPOCH_KEY = 'ir_ui_menu:epoch'
_MENU_CACHE_TTL = 300


def _menu_epoch():
    """Contador que invalida el caché entero al mutar el árbol.

    La referencia llama ``self.env.registry.clear_cache()`` en ``create`` /
    ``write`` / ``unlink`` (``ir_ui_menu.py:152,159,179``). Aquí no hay
    registry, así que la invalidación global se hace versionando la clave: al
    mutar una fila el epoch sube y todas las entradas previas quedan
    inalcanzables sin recorrer el keyspace.
    """
    epoch = cache.get(_MENU_CACHE_EPOCH_KEY)
    if epoch is None:
        epoch = 1
        cache.set(_MENU_CACHE_EPOCH_KEY, epoch, None)
    return epoch


def _bump_menu_epoch():
    try:
        cache.incr(_MENU_CACHE_EPOCH_KEY)
    except ValueError:
        # La clave no existía todavía: sembrarla ya deja el caché coherente.
        cache.set(_MENU_CACHE_EPOCH_KEY, 1, None)


class CapabilityPrunedMenuManager(models.Manager):
    """Manager con el mecanismo de podado — el equivalente de los métodos de
    ``ir.ui.menu`` en la referencia.

    Nombres alineados uno a uno con la referencia, **guion bajo incluido**:
    ``_visible_menu_ids``, ``_filter_visible_menus`` y ``load_menus``. Los
    dos primeros nacieron aquí sin él —promoviendo a API pública lo que la
    fuente reserva—; se corrigió al medir que Enterprise extiende
    ``_visible_menu_ids`` por su nombre privado
    (``porte-completo-no-parcial.md``, «el guion bajo se porta»).

    **Compartido entre los dos modelos de menú, y por qué.** La referencia
    tiene dos implementaciones distintas porque sus contextos difieren:
    ``ir.ui.menu._visible_menu_ids`` consulta ``ir.model.access`` del modelo de
    la acción, mientras que ``website.menu._compute_visible`` sólo mira si la
    página está publicada (su podado por ``group_ids`` lo hace el template
    QWeb). En este árbol **ambos menús se podan por capacidad**, así que el
    algoritmo es literalmente el mismo y separarlo en dos copias sería
    duplicación sin diferencia. La divergencia se declara aquí en vez de
    esconderse.
    """

    def _load_menus_blacklist(self):
        """≙ ``_load_menus_blacklist`` (``odoo19c: ir_ui_menu.py:209-211``).

        Los ids que **no** se sirven aunque el usuario los pudiera ver. La
        fuente lo declara devolviendo ``[]`` y lo consume antes de filtrar por
        visibilidad (``:237-241``): es un punto de extensión puro, cuyo cuerpo
        aquí es el mismo vacío.

        **Se declara aunque nadie lo extienda todavía.** Enterprise 19 lo
        extiende **7 veces**, más que ningún otro símbolo de ``ir.ui.menu``
        (tarea #67), y cada addon **suma** sus ids a los del ``super()``. Sin
        base que extender, dos addons que lo declararan se pisarían — el mismo
        defecto que ``SELF_READABLE_FIELDS`` tenía antes de :ref:`h-api-819`,
        y por eso se cierra con él y no cuando aparezca el primer consumidor.

        El punto está en el **queryset** porque el filtro que lo consume
        también lo está; una extensión lo sobreescribe sobre la clase, igual
        que ``hr`` hace con las listas de ``res.users``.

        **La caché no lo ve, y hay que decirlo.** La clave de
        :meth:`_visible_menu_ids` se compone de la generación y del conjunto de
        capacidades; la lista negra **no** entra en ella. Es correcto mientras
        sea estática por instalación —un addon la fija al cargarse— y deja de
        serlo el día que alguien la calcule por usuario o por empresa. Ese día
        la lista entra en la clave; hasta entonces, un cambio se propaga
        renovando la generación, que es lo que ya hace cualquier escritura de
        menú.
        """
        return []

    def _visible_menu_ids(self, user, capabilities, superadmin=False):
        """Ids de los ítems visibles para ``user`` (``_visible_menu_ids``).

        Cacheado por **conjunto de capacidades**, no por usuario — igual que la
        referencia cachea por ``frozenset(user._get_group_ids())``
        (``ir_ui_menu.py:74``). Mil usuarios con el mismo perfil comparten una
        entrada. La clave *es* el input del cálculo, así que un cambio de
        permisos produce otra clave por construcción: no puede servir de más.

        Dos filtros, como la referencia:

        1. **Por el sujeto** — el ítem pasa si no declara ``group`` o si el
           usuario tiene esa capacidad. Un sustantivo graduado (sin punto)
           gatea por lectura (``noun.view``); una acción nombrada (con punto),
           por membresía.
        2. **Por el destino** — ``group`` lleva la capacidad que enforce el
           endpoint de ``route``, no la del ítem (ver el docstring del módulo).
           Un menú visible cuyo destino daría 403 enseña que la funcionalidad
           existe, que es justo lo que el podado evita.

        Y la **regla de ancestros**: un ítem visible arrastra a sus padres; un
        contenedor sin descendiente visible se descarta.
        """
        key = (
            f'{_MENU_CACHE_PREFIX}:{_menu_epoch()}:{self.model._meta.db_table}:'
            f'{"su" if superadmin else hash(frozenset(capabilities))}'
        )
        cached = cache.get(key)
        if cached is not None:
            return cached

        # La fuente descuenta la lista negra ANTES de filtrar por
        # visibilidad (``odoo19c: ir_ui_menu.py:237-241``): un id vetado no
        # entra aunque el usuario tuviera la capacidad.
        items = list(
            self.filter(active=True)
            .exclude(pk__in=self._load_menus_blacklist())
            .select_related('group')
            .order_by('parent_id', 'sequence', 'id')
        )
        by_id = {item.pk: item for item in items}

        def allowed(item):
            code = item.group.code if item.group_id else None
            if superadmin or code is None:
                return True
            needed = code if '.' in code else f'{code}.view'
            return needed in capabilities

        visible = set()
        for item in items:
            # Sólo un ítem con destino puede ser visible por sí mismo. La
            # referencia hace lo mismo: ``if not action …: continue`` — una
            # sección entra únicamente arrastrada como ancestro.
            if item.is_section or not allowed(item):
                continue
            node = item
            while node is not None and node.pk not in visible:
                visible.add(node.pk)
                node = by_id.get(node.parent_id)

        visible = frozenset(visible)
        cache.set(key, visible, _MENU_CACHE_TTL)
        return visible

    def _filter_visible_menus(self, user, capabilities, superadmin=False):
        """Los ítems visibles, ya materializados (``_filter_visible_menus``)."""
        visible = self._visible_menu_ids(user, capabilities, superadmin)
        return list(
            self.filter(pk__in=visible)
            .select_related('group')
            .order_by('parent_id', 'sequence', 'id')
        )

    def load_menus(self, user, capabilities, superadmin=False):
        """Diccionario **plano** de los menús visibles (``load_menus``).

        Réplica de la forma de la referencia (``ir_ui_menu.py:236-313``): un
        dict indexado por id, ``children`` como lista de ids, ``app_id``
        propagado a cada descendiente, y la entrada ``root``. Tres decisiones
        que se copian tal cual:

        - **plano con ids**, no anidado: el cliente indexa sin recorrer;
        - **``app_id`` propagado**: cada nodo sabe a qué aplicación raíz
          pertenece sin subir por ``parent``;
        - **segundo filtro post-ensamblado**: si el padre se podó, el huérfano
          se descarta (*"Filter out menus not related to an app"*).

        El endpoint ``me/menu/`` **no** sirve hoy esta forma — devuelve el
        árbol anidado que ya consume el SPA. Migrarlo es un cambio del contrato
        público, que se decide aparte y toca ``kaupamex-ui``; no se hace de
        rebote al adaptar el modelo.
        """
        menus = self._filter_visible_menus(user, capabilities, superadmin)

        children_by_parent = {}
        for menu in menus:
            children_by_parent.setdefault(menu.parent_id, []).append(menu.pk)

        app_info = {}

        def _set_app_id(app_id, menu_id):
            app_info[menu_id] = app_id
            for child_id in children_by_parent.get(menu_id, []):
                _set_app_id(app_id, child_id)

        for root_id in children_by_parent.get(None, []):
            _set_app_id(root_id, root_id)

        menus_dict = {
            menu.pk: {
                'id': menu.pk,
                'name': menu.name,
                'app_id': app_info[menu.pk],
                'route': menu.route,
                'web_icon': menu.web_icon,
                'key': menu.key,
                'capability': menu.group.code if menu.group_id else None,
                'children': children_by_parent.get(menu.pk, []),
            }
            for menu in menus
            if menu.pk in app_info
        }
        menus_dict['root'] = {
            'id': False,
            'name': 'root',
            'children': children_by_parent.get(None, []),
        }
        return menus_dict

    def load_menus_tree(self, user, capabilities, superadmin=False):
        """Las raíces visibles, con ``_visible_children`` anidado en cada nodo.

        Misma entrada que ``load_menus`` y mismo podado; cambia sólo la
        **forma** de salida — anidada en vez de plana. Existe porque el
        consumidor es un SPA React que renderiza el árbol directo, mientras
        que el cliente OWL de la referencia indexa por id. Vive aquí, con el
        resto del mecanismo, para que el controlador siga siendo thin.
        """
        menus = self._filter_visible_menus(user, capabilities, superadmin)

        children_by_parent = {}
        for menu in menus:
            children_by_parent.setdefault(menu.parent_id, []).append(menu)

        def build(parent_id):
            out = []
            for menu in children_by_parent.get(parent_id, []):
                menu._visible_children = build(menu.pk)
                out.append(menu)
            return out

        return build(None)


class IrUiMenu(TimeStampedModel):
    """Entrada del árbol de menú (``ir.ui.menu``).

    Una **sección** es un nodo sin ``route``: no se muestra por sí misma, sólo
    si le sobrevive algún descendiente visible. Es la regla de ancestros de la
    referencia (``ir_ui_menu.py:132-136``), que evita que una carpeta vacía
    delate la existencia de lo que hay debajo.

    El podado **no es cosmético**: un menú que se dibuja y luego se oculta en
    el cliente filtra la existencia de la funcionalidad; uno que no se envía,
    no.

    Los atributos de clase son los cinco de la fuente
    (``odoo19c: ir_ui_menu.py`` — ``atributos-de-clase-de-modelo.md``).
    ``_parent_store`` declara el árbol materializado, cuyo ``parent_path`` aquí
    lo mantiene ``save()``; ``_order`` convive con ``Meta.ordering``.
    """

    _name = 'ir.ui.menu'
    _description = 'Menu'
    _order = 'sequence,id'
    _parent_store = True
    _allow_sudo_commands = False

    name = models.CharField(max_length=80, verbose_name='Menú')
    active = models.BooleanField(default=True, verbose_name='Activa')
    sequence = models.PositiveIntegerField(default=10, verbose_name='Secuencia')
    parent = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='child', verbose_name='Menú padre',
        help_text='Null = sección de nivel 0.',
    )
    group = models.ForeignKey(
        'authz.Capability', on_delete=models.PROTECT, null=True, blank=True,
        related_name='menu_items', verbose_name='Capacidad requerida',
        help_text=(
            'Odoo group_ids. Lleva la capacidad que enforce el endpoint del '
            'destino, no la del ítem: sin ella el menú mostraría una entrada '
            'que al pulsarla da 403. Null en secciones.'
        ),
    )
    route = models.CharField(
        max_length=160, blank=True, default='', verbose_name='Ruta SPA',
        help_text=(
            "Odoo action. Ruta del router React (p.ej. '/admin/products'); "
            'vacío en secciones.'
        ),
    )
    web_icon = models.CharField(
        max_length=40, blank=True, default='', verbose_name='Icono',
        help_text='Odoo web_icon. Nombre que el SPA resuelve con su librería.',
    )
    key = models.CharField(
        max_length=80, unique=True, verbose_name='Clave',
        help_text='Odoo xmlid. Slug estable del item, para seed idempotente.',
    )

    objects = CapabilityPrunedMenuManager()

    class Meta:
        db_table = 'ir_ui_menu'
        verbose_name = 'Entrada de menú'
        verbose_name_plural = 'Entradas de menú'
        ordering = ['sequence', 'id']
        indexes = [
            models.Index(fields=['parent', 'sequence']),
        ]

    def __str__(self):
        return self.complete_name

    def save(self, *args, **kwargs):
        # ``create``/``write`` de la referencia llaman ``registry.clear_cache()``.
        super().save(*args, **kwargs)
        _bump_menu_epoch()

    def delete(self, *args, **kwargs):
        # ``unlink`` de la referencia hace lo mismo (``ir_ui_menu.py:179``).
        result = super().delete(*args, **kwargs)
        _bump_menu_epoch()
        return result

    @property
    def complete_name(self):
        """Ruta completa del menú (``ir.ui.menu.complete_name``).

        ≙ ``_compute_complete_name`` (``odoo19c: base/models/ir_ui_menu.py``).
        """
        return self._get_full_name()

    def _get_full_name(self, level=6):
        """Nombre completo hasta cierto nivel; corta con ``'...'`` al agotarlo.

        El corte no es decorativo: acota el recorrido si el árbol quedara
        accidentalmente circular. Va verbatim de la referencia (``:48-55``).
        """
        if level <= 0:
            return '...'
        if self.parent_id:
            return f'{self.parent._get_full_name(level - 1) or ""}/{self.name or ""}'
        return self.name

    @property
    def is_section(self):
        """Un nodo sin ``route`` es contenedor: no se muestra por sí solo."""
        return not self.route
