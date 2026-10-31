"""Catálogo técnico y solicitudes de ciclo de vida por base.

Adaptado de Odoo Community 19 ir.module.module (LGPL-3), revisión
abe4040ec1a45beee90fb694e4eae4453e46b389. Las solicitudes administrativas
programan estados transitorios; no sustituyen la ejecución del loader,
la preparación del esquema, los hooks ni la composición efectiva del registro.
"""
import shutil

import fields
import models
from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import router, transaction

from addons.base.models.timestamped_mixin import TimeStampedModel
from modules.module import adapt_version, check_python_external_dependency, load_manifest
from modules.module_graph import ModuleGraph
from orm.environments import is_system


class IrModuleCategory(TimeStampedModel):
    """Aplicación: la categoría bajo la que se agrupan los addons.

    Adaptación de ``ir.module.category`` (``ir_module.py:76-91`` de la
    referencia), que vive en este mismo archivo allá. Es un árbol
    (``parent_id`` self-FK) y es lo que el instalador presenta como
    "Aplicaciones".

    Procedencia: ``name`` · ``description`` · ``sequence`` · ``visible``
    (default True) · ``exclusive`` idénticos. ``parent_id`` → ``parent``;
    ``child_ids``/``module_ids``/``privilege_ids`` → los ``related_name``
    correspondientes. ``xml_id`` **SÍ se porta** — ver :meth:`_compute_xml_id`.

    .. note:: Este párrafo decía que el campo *"no se porta: se computa desde
       ``ir.model.data``, el registro de datos declarativos XML de Odoo, que
       este árbol no tiene"*. La segunda mitad es falsa desde el porte de
       ``ir_model.py``: ``ir.model.data`` se declara en ``:2848`` con los
       cuatro campos que el cómputo necesita (``model``, ``res_id``,
       ``module``, ``name``). Ver :ref:`h-api-983`.
    """

    _name = 'ir.module.category'
    _description = "Application"
    _order = 'sequence, name, id'
    _allow_sudo_commands = False

    name        = fields.Char()
    parent      = fields.Many2one(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        db_index=True, related_name='child',
        help_text='Odoo parent_id. Null = aplicación de nivel 0.',
    )
    description = fields.Text(blank=True, default='')
    sequence    = fields.Integer(null=True, blank=True)
    visible     = fields.Boolean(default=True)
    exclusive   = fields.Boolean(default=False)

    #: ≙ ``xml_id`` (``odoo19c: ir_module.py:91``):
    #: ``fields.Char(string='External ID', compute='_compute_xml_id')``.
    #:
    #: **No persistido**, como allá: el dato vive en ``ir.model.data`` y una
    #: columna aquí sería una copia que esa tabla puede desmentir. El
    #: mecanismo es ``orm.fields_nonstored.NonStored``, el mismo con que
    #: ``ir_actions.warning`` porta su ``compute`` sin columna.
    xml_id = fields.NonStored(
        default=lambda category: category._compute_xml_id(),
        help_text='Odoo xml_id. Identificador externo "modulo.nombre", '
                  'tomado de ir.model.data.',
    )

    class Meta:
        db_table = 'ir_module_category'
        ordering = ['sequence', 'name', 'id']   # derivado de _order
        verbose_name = 'Aplicación'
        verbose_name_plural = 'Aplicaciones'

    def _compute_xml_id(self):
        """≙ ``_compute_xml_id`` (``odoo19c: ir_module.py:93-99``).

        El identificador externo de una categoria es ``"<modulo>.<nombre>"``,
        y sale de ``ir.model.data`` — no de esta tabla.

        Dos fidelidades que conviene senalar porque no se leen solas:

        - **la cadena vacia cuando nadie lo declaro**, no ``None``: es el
          ``xml_ids.get(cat.id, [''])[0]`` de ``:99``, y es lo que deja al
          consumidor sin ramificar;
        - **el primero cuando hay varios**. Un mismo registro puede llevar
          identificador de mas de un modulo —lo dice el propio
          ``_process_end_unlink_record`` de la fuente— y el campo es ``Char``,
          asi que entrega uno.

        DIVERGENCIA declarada, y es la que este arbol ya tenia tomada: la
        fuente busca por ``('model', '=', self._name)`` —el nombre Odoo— y
        aqui ``ir.model.data`` guarda el **label de Django**
        (``ir_model.py:3423`` escribe ``model_cls._meta.label``). Se consulta
        por el label para no crear una segunda convencion en la misma columna.
        """
        fila = (apps.get_model('base', 'IrModelData').objects
                .filter(model=type(self)._meta.label, res_id=self.pk)
                .values_list('module', 'name').first())
        return f'{fila[0]}.{fila[1]}' if fila else ''

    def _check_parent_not_circular(self):
        """≙ ``_check_parent_not_circular`` (``odoo19c: ir_module.py:102-105``).

        Mensaje de la fuente, verbatim: *"You cannot create recursive
        categories."* Las categorias anidan —una aplicacion tiene
        sub-aplicaciones—, asi que la guarda distingue profundidad de ciclo
        recorriendo hacia arriba, no prohibiendo el padre.

        Con un ciclo persistido, cualquier recorrido del arbol de categorias
        —el que el instalador presenta agrupado— no termina.
        """
        seen = set()
        current = self.parent
        while current is not None:
            if current.pk == self.pk or current.pk in seen:
                raise ValidationError(
                    'No se pueden crear categorías recursivas.')
            seen.add(current.pk)
            current = current.parent

    def save(self, *args, **kwargs):
        """``@api.constrains('parent_id')`` de la fuente."""
        self._check_parent_not_circular()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class IrModule(TimeStampedModel):
    """Un addon del árbol, con la metadata que declara su ``__manifest__.py``.

    ``name`` es el **nombre técnico** —la carpeta—, igual que en la referencia.
    Es lo que lo distingue del catálogo comercial, cuyo ``code`` es un nombre de
    dominio que puede no coincidir con ninguna carpeta.

    Ningún ``Char`` de aquí lleva tope (H-API-750)
    ==============================================

    Los **16** ``fields.Char`` de ``odoo19c: odoo/addons/base/models/ir_module.py``
    se declaran sin tamaño, así que la columna es un ``varchar`` sin límite. Los
    nuestros llevaban topes inventados —``summary`` 255, ``shortdesc`` 200,
    ``name`` 100, ``version`` 32— y el primero ya había truncado datos reales.

    El tope no se subió: se **retiró**, porque este stack expresa exactamente lo
    que la referencia tiene. Medido en el entorno, no de memoria::

        supports_unlimited_charfield = True      # backend PostgreSQL de Django 6
        CharField(max_length=None).db_type()  -> 'varchar'
        CharField(max_length=255).db_type()   -> 'varchar(255)'

    Que el tope era arbitrario lo dice la propia referencia: su ``summary`` más
    largo mide **251** caracteres (``account_add_gln``, de 328 manifiestos con
    ``summary``) — cuatro por debajo del techo que teníamos. Un límite que la
    fuente no impone y que su propio corpus casi toca no protege de nada; sólo
    espera para romper.

    La ruta fuente de categoría también se conserva sin un tope arbitrario.

    Cobertura de campos — 8 de 31, declarada
    =========================================

    ``odoo19c: odoo/addons/base/models/ir_module.py:158-330`` declara **31**
    campos; de ellos coinciden por nombre **8** (``name``, ``shortdesc``,
    ``summary``, ``sequence``, ``application``, ``auto_install``, ``state``,
    ``license``). Otros **2** son formas nuestras: ``category``, la relación
    que la fuente llama ``category_id``, y ``version``, que conserva metadata
    del manifiesto. ``installed_version`` conserva por separado la versión
    realmente instalada (``latest_version`` persistido de la referencia).
    Su valor histórico desconocido permanece NULL: no se infiere del catálogo.

    Quedan **23 ausentes**, y la mayoría **no** está bloqueada por nada — son
    ``Char`` planos del manifest (``author``, ``maintainer``, ``website``,
    ``url``, ``icon``). El resto sí depende de mecanismos que este árbol todavía
    no tiene: ``description_html`` (QWeb), ``icon_image`` (Binary servido), los
    tres ``*_by_module`` (introspección de menús/vistas/reportes), y
    ``exclusion_ids`` (``ir.module.module.exclusion``, sin portar).

    **No se portan en este pase por alcance, no por imposibilidad** — el pase
    es la corrección del tope de ``Char`` (:ref:`h-api-756`). Su porte es la
    tarea **#452**, que ya cubre la reestructuración de ``category`` a FK.
    """

    _name = 'ir.module.module'
    _rec_name = "shortdesc"
    _rec_names_search = ['name', 'shortdesc', 'summary']
    _description = "Module"
    _order = 'application desc,sequence,name'
    _allow_sudo_commands = False

    # Estado persistido por base: las transiciones programan el trabajo del loader.
    STATE_UNINSTALLABLE = 'uninstallable'
    STATE_UNINSTALLED   = 'uninstalled'
    STATE_INSTALLED     = 'installed'
    STATE_TO_INSTALL = 'to install'
    STATE_TO_UPGRADE = 'to upgrade'
    STATE_TO_REMOVE = 'to remove'
    STATES = [
        (STATE_UNINSTALLABLE, 'No instalable'),
        (STATE_UNINSTALLED,   'No instalado'),
        (STATE_INSTALLED,     'Instalado'),
        (STATE_TO_INSTALL, 'Pendiente de instalación'),
        (STATE_TO_UPGRADE, 'Pendiente de actualización'),
        (STATE_TO_REMOVE, 'Pendiente de desinstalación'),
    ]

    # Las diez licencias del titular, verbatim de la referencia. NO se recorta
    # la lista a las que hoy usamos: recortarla obligaría a re-etiquetar una
    # fuente el día que aparezca, que es lo que DEC-KX-03 prohíbe.
    LICENSES = [
        ('GPL-2', 'GPL Version 2'),
        ('GPL-2 or any later version', 'GPL-2 o posterior'),
        ('GPL-3', 'GPL Version 3'),
        ('GPL-3 or any later version', 'GPL-3 o posterior'),
        ('AGPL-3', 'Affero GPL-3'),
        ('LGPL-3', 'LGPL Version 3'),
        ('Other OSI approved licence', 'Otra licencia aprobada por OSI'),
        ('OEEL-1', 'Odoo Enterprise Edition License v1.0'),
        ('OPL-1', 'Odoo Proprietary License v1.0'),
        ('Other proprietary', 'Otra propietaria'),
        # Añadida: un addon escrito por nosotros, sin código copiado de una
        # fuente externa. No está en la referencia porque allá todo addon
        # declara una de las suyas.
        ('Confidential', 'Propietaria de Kaupamex'),
    ]

    name         = fields.Char(
        unique=True, db_index=True,
        help_text='Nombre técnico = carpeta del addon (Odoo ir.module.module.name).',
    )
    shortdesc    = fields.Char(
        blank=True, default='',
        help_text='Nombre legible del manifest (Odoo shortdesc ← manifest name).',
    )
    summary      = fields.Char(blank=True, default='')
    description  = fields.Text(
        blank=True, default='',
        help_text='Descripción larga del manifest (Odoo description).',
    )
    author       = fields.Char(
        blank=True, default='',
        help_text='Odoo author. NO cae a "Unknown": modules.module ya rellena '
                  'el autor del proyecto cuando el manifest calla, así que '
                  'ese literal guardaría un dato falso para un addon propio.',
    )
    maintainer   = fields.Char(blank=True, default='')
    contributors = fields.Text(
        blank=True, default='',
        help_text='Odoo contributors. La fuente la declara Text porque la '
                  'lista se aplana a una cadena separada por comas.',
    )
    website      = fields.Char(blank=True, default='')
    url          = fields.Char(
        blank=True, default='',
        help_text='Odoo url, con respaldo a live_test_url del manifest.',
    )
    icon         = fields.Char(
        blank=True, default='',
        help_text='Odoo icon: la RUTA del icono, no el binario. El binario es '
                  'icon_image, computado, y ése no se porta (ver el docstring).',
    )
    to_buy       = fields.Boolean(
        default=False,
        help_text='Odoo to_buy. Siempre False aquí: marca un módulo del '
                  'catálogo comercial de la fuente, que este árbol no consulta.',
    )
    demo         = fields.Boolean(
        default=False,
        help_text='Odoo demo: el addon tiene datos de demostración cargados.',
    )
    category = fields.Many2one(
        IrModuleCategory, on_delete=models.PROTECT, null=True, blank=True,
        related_name='modules',
        help_text='Odoo category_id: hoja del árbol técnico de categorías.',
    )
    category_path = fields.Char(
        blank=True, default='Uncategorized', editable=False,
        help_text='Ruta original del manifiesto; preserva historia y contrato HTTP.',
    )
    version      = fields.Char(blank=True, default='1.0')
    installed_version = fields.Char(
        blank=True, null=True, default=None, editable=False,
        help_text='Versión realmente instalada; NULL si no existe evidencia de instalación.',
    )
    # Lo nombra ``_order``; sin él el atributo describiría un orden que este
    # modelo no puede cumplir. ``odoo19c: …/ir_module.py:294`` — default 100.
    sequence     = fields.Integer(default=100)
    license      = fields.Selection(
        max_length=32, choices=LICENSES, default='LGPL-3',
        help_text='Licencia declarada por el manifest. NO se re-etiqueta (DEC-KX-03).',
    )
    application  = fields.Boolean(
        default=False,
        help_text='Addon vendible como aplicación, no técnico (Odoo application).',
    )
    auto_install = fields.Boolean(default=False)
    state        = fields.Selection(
        max_length=16, choices=STATES, default=STATE_UNINSTALLED, db_index=True,
        help_text='Estado de instalación persistido en la base del módulo.',
    )

    class Meta:
        db_table     = 'ir_module_module'
        # Derivado de _order. ``application desc`` es ``-application``: las
        # aplicaciones vendibles primero, luego la secuencia, luego el nombre.
        ordering     = ['-application', 'sequence', 'name']
        verbose_name = 'Módulo técnico'

    def __str__(self):
        """Consume ``_rec_name``, con respaldo al nombre técnico.

        La referencia etiqueta el registro por ``shortdesc`` (el nombre legible
        del manifest). Aquí ese campo admite vacío —hay filas sembradas desde
        carpetas sin manifest—, así que se cae al ``name`` técnico en vez de
        devolver una cadena vacía.
        """
        return getattr(self, self._rec_name, '') or self.name

    def button_install(self):
        """Programa instalación y dependencias; no declara ejecutado el loader."""
        return self._request_module_change('install')

    def button_upgrade(self):
        """Programa actualización y dependientes instalados de esta base."""
        return self._request_module_change('upgrade')

    def button_uninstall(self):
        """Programa retirada de dependientes sin borrar datos ni esquema aún."""
        return self._request_module_change('uninstall')

    def _request_module_change(self, operation):
        if not is_system():
            raise PermissionDenied('Module changes require system administration')
        if self.pk is None:
            raise ValidationError('A persisted module is required')
        using = self._state.db or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            # Orden estable y mismo cerrojo para operaciones incompatibles.
            rows = {row.name: row for row in type(self).objects.using(using)
                    .select_for_update().order_by('pk')}
            current = rows.get(self.name)
            if current is None or current.pk != self.pk:
                raise ValidationError('Module does not exist in the selected database')
            active_states = {self.STATE_INSTALLED, self.STATE_TO_UPGRADE}
            requested = {self.name}
            if operation != 'install':
                if current.state not in active_states:
                    raise ValidationError(f'Module {self.name} is not installed')
                if operation == 'uninstall' and self.name == 'base':
                    raise ValidationError('The base module cannot be uninstalled')
                requested.update(self.downstream_dependencies(
                    exclude_states=(self.STATE_UNINSTALLED, self.STATE_UNINSTALLABLE,
                                    self.STATE_TO_INSTALL, self.STATE_TO_REMOVE)
                ).values_list('name', flat=True))
                if operation == 'uninstall':
                    if 'base' in requested:
                        raise ValidationError('The base module cannot be uninstalled')
                    type(self).objects.using(using).filter(name__in=requested).update(
                        state=self.STATE_TO_REMOVE)
                    self.state = self.STATE_TO_REMOVE
                    return sorted(requested)

                if self.name == 'base':
                    requested.update(name for name, row in rows.items()
                                     if row.state in active_states)
            graph = ModuleGraph()
            available = ModuleGraph()
            available.extend(tuple(rows))
            active = {name for name, row in rows.items() if row.state in
                      active_states | {self.STATE_TO_INSTALL}}
            while True:
                graph.extend(tuple(requested))
                ordered = list(graph)  # Rechaza ciclos antes de escribir estados.
                for node in ordered:
                    row = rows.get(node.name)
                    if row is None or not node.manifest:
                        raise ValidationError(f'Missing module dependency: {node.name}')
                    if not node.manifest.get('installable', True):
                        raise ValidationError(f'Module is not installable: {node.name}')
                    if row.state in {self.STATE_UNINSTALLABLE, self.STATE_TO_REMOVE}:
                        raise ValidationError(f'Invalid module state: {node.name}: {row.state}')
                    self._check_module_dependencies(node.manifest)
                active.update(node.name for node in ordered)
                automatic = set(available.auto_installable(active)) - requested
                if not automatic:
                    break
                requested |= automatic
            selected = {node.name for node in ordered}
            exclusions = IrModuleExclusion.objects.using(using).filter(
                module__name__in=active, name__in=active)
            if exclusions.exists():
                raise ValidationError('Incompatible modules in the selected database')
            if operation == 'upgrade':
                type(self).objects.using(using).filter(name__in=requested,
                    state__in=active_states).update(state=self.STATE_TO_UPGRADE)
            type(self).objects.using(using).filter(name__in=selected,
                state=self.STATE_UNINSTALLED).update(state=self.STATE_TO_INSTALL)
            self.state = type(self).objects.using(using).get(pk=self.pk).state
            return [node.name for node in ordered]

    @staticmethod
    def _check_module_dependencies(manifest):
        external = manifest.get('external_dependencies', {})
        for dependency in external.get('python', ()):
            check_python_external_dependency(dependency)
        for dependency in external.get('bin', ()):
            if shutil.which(dependency) is None:
                raise ValidationError(f'Missing executable dependency: {dependency}')

    @classmethod
    def get_module_info(cls, name):
        """≙ ``get_module_info`` (``odoo19c: ir_module.py:165-173``).

        La fuente admite tres formas de ``name``: una cadena, un ``Manifest``
        ya resuelto, o cualquier otra cosa (que devuelve ``{}``). Se portan las
        tres.

        **Divergencia de mecanismo:** allá el resolutor es
        ``modules.Manifest.for_addon``; aquí es ``modules.module.load_manifest``,
        que es la pieza equivalente de este árbol y ya evalúa el archivo con
        ``ast.literal_eval`` en vez de importarlo. El contrato —dict, o ``{}``
        si el addon no existe o no declara manifest— es el mismo.
        """
        if isinstance(name, str):
            # Igual que la fuente: la ausencia de manifest es "no es un
            # módulo", no un error. Un addon importado no se encuentra por
            # esta vía, y eso allá también es así.
            return load_manifest(name) or {}
        if isinstance(name, dict):
            return name
        return {}

    def _get_latest_version(self):
        """≙ ``_get_latest_version`` (``odoo19c: ir_module.py:211-215``).

        Devuelve la versión que el manifest declara **en disco**, que puede
        diferir de la metadata guardada por el catálogo y de la versión
        instalada. Este getter no acredita una instalación.

        La fuente asigna su campo computado ``installed_version`` desde el
        manifiesto; guarda lo instalado en ``latest_version``. Aquí el getter
        devuelve la versión del manifiesto y nuestro campo persistido
        ``installed_version`` conserva por separado lo realmente instalado.
        """
        return self.get_module_info(self.name).get(
            'version', adapt_version('1.0'))

    @classmethod
    def _get_id(cls, name):
        """≙ ``_get_id`` (``odoo19c: ir_module.py:906-909``).

        La fuente lo resuelve con SQL crudo para saltarse la caché del ORM.
        Aquí basta ``values_list``: la razón de aquel SQL es el ``flush_model``
        previo, que es un mecanismo de su ORM y no del nuestro.
        """
        return cls.objects.filter(name=name).values_list('pk', flat=True).first()

    @classmethod
    def _get(cls, name):
        """≙ ``_get`` (``odoo19c: ir_module.py:898-903``).

        Devuelve ``None`` cuando el módulo no existe, que es lo que aquí
        significa el *recordset vacío* de la fuente.

        El ``.sudo()`` de la fuente **no se porta**: aquí la autorización
        efectiva es por capacidad (DEC-11, ``HasCapability``, fail-closed), no
        un escalado de privilegio colgado del propio registro.
        """
        if not name:
            return None
        return cls.objects.filter(name=name).first()

    def downstream_dependencies(self,
                                exclude_states=(STATE_UNINSTALLED,
                                                STATE_UNINSTALLABLE,
                                                STATE_TO_REMOVE)):
        """≙ ``downstream_dependencies`` (``odoo19c: ir_module.py:531-555``).

        Reutiliza el recorrido por oleadas del catálogo de la misma base.
        Excluye módulos retirados o ya programados para retirada; conserva
        la distinción entre programar una operación y ejecutarla.
        """
        return self._walk_dependencies(forward=False,
                                       exclude_states=exclude_states)

    def upstream_dependencies(self,
                              exclude_states=(STATE_INSTALLED,
                                              STATE_UNINSTALLABLE)):
        """≙ ``upstream_dependencies`` (``odoo19c: ir_module.py:556-580``).

        De quién dependo, directa o indirectamente. La fuente la usa antes de
        instalar; el default de estados a excluir es el simétrico del anterior
        —lo ya instalado no hace falta traerlo—, y por eso los dos defaults
        difieren en un solo valor.
        """
        return self._walk_dependencies(forward=True,
                                       exclude_states=exclude_states)

    def _walk_dependencies(self, forward, exclude_states):
        """El recorrido que comparten los dos sentidos.

        La fuente los escribe como dos métodos recursivos con dos consultas SQL
        casi idénticas —difieren en qué columna cruza con cuál—. Aquí el
        recorrido es uno y el sentido es un parámetro: la duplicación de allá no
        expresa nada que aquí no exprese el booleano, y dos copias divergen.

        Se recorre por oleadas y con marca de visitado, no por recursión: el
        grafo admite ciclos —dos addons pueden declararse mutuamente— y una
        recursión ingenua no terminaría. Es la misma razón que en
        ``IrModuleDependency.all_dependencies``.
        """
        using = self._state.db or router.db_for_read(type(self), instance=self)
        modules = type(self).objects.using(using)
        dependencies = IrModuleDependency.objects.using(using)
        seen = set()
        frontier = {self.name} if forward else {self.pk}

        while frontier:
            if forward:
                names = list(dependencies.filter(
                    module__name__in=frontier).values_list('name', flat=True))
                found = modules.filter(name__in=names)
            else:
                names = list(modules.filter(
                    pk__in=frontier).values_list('name', flat=True))
                found = modules.filter(
                    dependencies__name__in=names)

            found = found.exclude(state__in=exclude_states).exclude(
                pk__in=seen | {self.pk})
            fresh = {module.pk for module in found}
            if not fresh:
                break
            seen |= fresh
            frontier = ({module.name for module in
                         modules.filter(pk__in=fresh)}
                        if forward else fresh)

        return modules.filter(pk__in=seen)


class IrModuleDependency(TimeStampedModel):
    """Una arista ``depends`` declarada por el manifest de un addon.

    Tabla aparte y no un M2M a ``IrModule``, igual que la referencia: la
    dependencia se declara por **nombre**, y el nombre puede apuntar a un addon
    que todavía no está en el catálogo. Un M2M exigiría que el destino exista, y
    perdería justamente el caso que interesa detectar.

    **Divergencia declarada en** ``_log_access``. La referencia lo pone en
    ``False`` —*"inserts are done manually, create and write uid, dates are
    always null"*— y aquí la clase hereda ``TimeStampedModel``, que sí escribe
    esas columnas. No se retira: nuestra siembra **no** inserta a mano, pasa por
    el ORM, así que las columnas llevan un valor real y no el ``null`` que la
    fuente describe. El atributo se declara verbatim para que la divergencia sea
    greppeable, no para que el ORM lo obedezca.
    """

    _name = 'ir.module.module.dependency'
    _description = "Module dependency"
    _log_access = False   # ver la divergencia declarada en el docstring
    _allow_sudo_commands = False

    module = fields.Many2one(
        IrModule, on_delete=models.CASCADE, related_name='dependencies',
        help_text='El addon que declara la dependencia.',
    )
    name   = fields.Char(
        db_index=True,
        help_text='Nombre técnico del addon del que depende.',
    )

    #: ≙ ``DEP_STATES`` (``odoo19c: ir_module.py:995``): los estados del módulo
    #: más ``unknown``, que es lo que vale una dependencia cuya contraparte no
    #: está en el catálogo. Se construye igual que allá —desde ``STATES``— para
    #: que añadir un estado al módulo no deje esta lista atrás.
    DEP_STATES = IrModule.STATES + [('unknown', 'Desconocido')]

    auto_install_required = fields.Boolean(
        default=True,
        help_text='Odoo auto_install_required: si esta dependencia bloquea la '
                  'instalación automática del addon que la declara.',
    )

    class Meta:
        db_table            = 'ir_module_module_dependency'
        unique_together     = [('module', 'name')]
        ordering            = ['name']
        verbose_name        = 'Dependencia de módulo'
        verbose_name_plural = 'Dependencias de módulo'

    def __str__(self):
        return f'{self.module.name} → {self.name}'
    def _compute_depend(self):
        """≙ ``_compute_depend`` (``odoo19c: ir_module.py:1021-1030``).

        Resuelve el nombre de la dependencia contra el catálogo. Devuelve
        ``None`` cuando el addon nombrado no está en él — que es el caso que
        justifica que esta tabla guarde un nombre y no una FK: la arista existe
        aunque su destino todavía no.

        **Divergencia de mecanismo, declarada:** la fuente lo declara campo
        computado (``depend_id``) y aquí es un método. Un campo computado no
        almacenado necesita ``fields.NonStored``, y ése resuelve **por
        registro**; la fuente resuelve **el lote entero con una consulta** e
        indexa por nombre, que es justo lo que evita el N+1. Se conserva la
        forma de la fuente: el lote se resuelve con ``_compute_depend_batch``,
        y este método es su caso de un elemento.
        """
        return type(self)._compute_depend_batch([self])[self.pk]

    @classmethod
    def _compute_depend_batch(cls, dependencies):
        """El lote de ``_compute_depend``, con una sola consulta.

        Es la forma de la fuente —``search`` de todos los nombres, índice por
        nombre, asignación en bucle— y la razón de portarla es medible: sin
        ella, resolver N aristas cuesta N consultas.
        """
        dependencies = list(dependencies)
        if not dependencies:
            return {}
        aliases = {dependency._state.db or router.db_for_read(IrModule, instance=dependency)
                   for dependency in dependencies}
        if len(aliases) != 1:
            raise ValidationError('A dependency batch must belong to one database')
        using = aliases.pop()
        names = {dependency.name for dependency in dependencies}
        by_name = {module.name: module
                   for module in IrModule.objects.using(using).filter(name__in=names)}
        return {dependency.pk: by_name.get(dependency.name)
                for dependency in dependencies}

    @classmethod
    def _search_depend(cls, value):
        """≙ ``_search_depend`` (``odoo19c: ir_module.py:1032-1037``).

        Traduce una búsqueda por módulo destino a una búsqueda por nombre, que
        es la columna que esta tabla sí tiene.

        La fuente recibe además un ``operator`` y devuelve ``NotImplemented``
        para todo lo que no sea ``in``/``any``. Aquí el operador no es
        parámetro: el único que este stack construye es la pertenencia, y
        aceptar uno para rechazarlo declararía una superficie que no existe.
        """
        names = list(IrModule.objects.filter(
            pk__in=[getattr(module, 'pk', module) for module in value]
        ).values_list('name', flat=True))
        return cls.objects.filter(name__in=names)

    def _compute_state(self):
        """≙ ``_compute_state`` (``odoo19c: ir_module.py:1038-1041``).

        El estado de la dependencia **es** el del módulo al que apunta; si no
        apunta a ninguno, es ``unknown``. Sin esta caída, una arista huérfana
        heredaría el default del campo y se leería como "no instalado", que es
        un estado distinto de "no sé si existe".
        """
        depend = self._compute_depend()
        return depend.state if depend is not None else 'unknown'

    @classmethod
    def all_dependencies(cls, module_names):
        """≙ ``all_dependencies`` (``odoo19c: ir_module.py:1043-1060``).

        Cierre transitivo hacia abajo: ``{addon: [sus dependencias directas]}``
        para los nombres dados **y** para todo lo que alcancen. La fuente lo
        resuelve por oleadas —resolver las directas, encolar las nuevas,
        repetir— y esa forma se conserva: el grafo puede tener ciclos, y una
        recursión ingenua no terminaría.

        **Divergencia de mecanismo:** la fuente consulta con
        ``web_search_read``, que es su superficie RPC. Aquí es una consulta del
        ORM: el dato es el mismo y el canal no aporta nada al cálculo.
        """
        to_search = dict.fromkeys(module_names, True)
        result = {}

        while to_search:
            searching = list(to_search)
            edges = cls.objects.filter(
                module__name__in=searching
            ).values_list('module__name', 'name')
            to_search.clear()
            for module_name, dependency_name in edges:
                if (dependency_name not in result
                        and dependency_name not in to_search
                        and dependency_name not in searching):
                    to_search[dependency_name] = True
                result.setdefault(module_name, []).append(dependency_name)

        return result


class IrModuleExclusion(TimeStampedModel):
    """Una arista ``excludes`` — el addon que este otro no admite al lado.

    ≙ ``ir.module.module.exclusion`` (``odoo19c: ir_module.py:1065-1102``).
    Tabla aparte por la misma razón que la dependencia: la exclusión se declara
    por **nombre**, y el nombre puede apuntar a un addon ausente del catálogo.

    **Su lector existe aunque el instalador no.** Que aquí no se pueda instalar
    en caliente no borra el hecho que la tabla registra: que dos addons del
    árbol se declaran incompatibles. Ese hecho hoy no vive en ninguna parte —
    es la misma medición que fundó este archivo, aplicada a la otra arista.
    """

    _name = 'ir.module.module.exclusion'
    _description = "Module exclusion"
    _allow_sudo_commands = False

    module    = fields.Many2one(
        IrModule, on_delete=models.CASCADE, related_name='exclusions',
        help_text='El addon que declara la exclusión.',
    )
    name      = fields.Char(
        db_index=True,
        help_text='Nombre técnico del addon excluido.',
    )

    class Meta:
        db_table            = 'ir_module_module_exclusion'
        unique_together     = [('module', 'name')]
        ordering            = ['name']
        verbose_name        = 'Exclusión de módulo'
        verbose_name_plural = 'Exclusiones de módulo'

    def _compute_exclusion(self):
        """≙ ``_compute_exclusion`` (``odoo19c: ir_module.py:1082-1090``).

        Misma forma que ``_compute_depend`` de la dependencia, sobre la otra
        arista. La fuente las declara por separado y no las factoriza; se
        conserva esa separación en vez de inventar un mixin que allá no existe.
        """
        using = self._state.db or router.db_for_read(IrModule, instance=self)
        return IrModule.objects.using(using).filter(name=self.name).first()

    @classmethod
    def _search_exclusion(cls, value):
        """≙ ``_search_exclusion`` (``odoo19c: ir_module.py:1092-1096``)."""
        names = list(IrModule.objects.filter(
            pk__in=[getattr(module, 'pk', module) for module in value]
        ).values_list('name', flat=True))
        return cls.objects.filter(name__in=names)

    def _compute_state(self):
        """≙ ``_compute_state`` (``odoo19c: ir_module.py:1098-1102``)."""
        excluded = self._compute_exclusion()
        return excluded.state if excluded is not None else 'unknown'

    def __str__(self):
        return f'{self.module.name} ⊥ {self.name}'
