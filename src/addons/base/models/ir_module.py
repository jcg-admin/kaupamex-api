"""``ir.module.module`` — catálogo técnico de addons (Odoo ``base``).

Adaptado de ``odoo/addons/base/models/ir_module.py`` (Odoo Community, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

**Por qué existe, y por qué no existía.** Un análisis previo concluyó que este
modelo *"no se portó — no por olvido: no tiene a qué apuntar"*, razonando que
sin instalación en caliente no hay nada que registrar. Era falso, y el error
fue medir un trabajo del modelo y concluir sobre los dos: el original **declara
metadata** (nombre, licencia, categoría, dependencias) *y* **sostiene el estado
de instalación**. Sólo el segundo depende del instalador.

Lo que ese hueco costaba es medible: **4 carpetas de** ``src/addons/`` **no
están en** ``INSTALLED_APPS`` — ``contact``, ``referral``, ``returns``,
``reviews``. Están en disco, no cargan, y ese hecho no vivía en ninguna tabla:
sólo en la cabeza de quien lo supiera.

**Los dos catálogos, y por qué hacen falta los dos.** La referencia tiene
``ir.module.module`` (técnico: qué está instalado) y el eje comercial que en
Kaupamex es ``authz.Module`` (qué contrata una company). No coinciden —medido,
18 de 25 códigos comerciales no llevan el nombre de su carpeta, y dos addons
declaran dos módulos cada uno— así que no se colapsan: se tienen los dos, cada
uno sobre su eje.

**Qué se porta y qué no.** Se portan los campos de declaración y los tres
estados **alcanzables** en este árbol. Las transiciones de Odoo
(``to install`` / ``to upgrade`` / ``to remove``) **no** se portan: son la
máquina de estados de un instalador que aquí no existe — el registro de apps de
Django se congela en ``django.setup()`` y el schema es compartido entre
companies (ADR-021). Registrar un estado que nadie puede alcanzar sería
inventar una capacidad.

Los cuatro enganches que Enterprise usa sobre este modelo
==========================================================

Medido sobre Enterprise 19 (``odoo19e:``, ``odoo-tools@bf077302``): **4
archivos** con ``_inherit = 'ir.module.module'``, con **3** nombres de método
distintos. El árbol viene duplicado en el repo —``odoo19-enterprise-main/`` y
``odoo19pro-main/`` son la misma población— así que el grep crudo da 8 rutas y
la población es 4.

Ninguno se porta, y los cuatro caen **dentro de la divergencia ya declarada
arriba**: los tres primeros son la transición ``to remove`` vista desde fuera,
y el cuarto crea un módulo que ningún registro cargó.

============================  =========================  ==========================
Addon                         Método                     Qué hace, y por qué no aplica
============================  =========================  ==========================
``pos_blackbox_be``           ``module_uninstall``       veta la desinstalación si hay una caja certificada. Sin desinstalador no hay qué vetar.
``helpdesk``                  ``module_uninstall``       apaga por SQL las banderas de ``helpdesk_team`` del addon que se va. Misma transición.
``timesheet_grid``            ``button_uninstall``       arrastra ``hr_timesheet``/``sale_timesheet`` a la desinstalación — extiende el **conjunto**, no el registro.
``web_studio``                ``get_studio_module``      crea al vuelo un módulo ``imported=True`` con ``state='installed'``. Aquí ``state`` es **derivado** de ``INSTALLED_APPS`` (ver el ``help_text`` del campo): no hay dónde escribirlo, y ``imported`` no se declara.
============================  =========================  ==========================

*Métrica:* archivos de Enterprise 19 con ``_inherit`` a ``ir.module.module``,
y los ``def`` de nivel de clase que declaran.
*Ciega a:* una extensión que llegue por un mixin intermedio sin nombrar el
modelo, y a Enterprise 18 — que no se midió en este pase.
"""
import fields
import models
from django.core.exceptions import ValidationError

from addons.base.models.timestamped_mixin import TimeStampedModel
from modules.module import adapt_version, load_manifest


class IrModuleCategory(TimeStampedModel):
    """Aplicación: la categoría bajo la que se agrupan los addons.

    Adaptación de ``ir.module.category`` (``ir_module.py:76-91`` de la
    referencia), que vive en este mismo archivo allá. Es un árbol
    (``parent_id`` self-FK) y es lo que el instalador presenta como
    "Aplicaciones".

    Procedencia: ``name`` · ``description`` · ``sequence`` · ``visible``
    (default True) · ``exclusive`` idénticos. ``parent_id`` → ``parent``;
    ``child_ids``/``module_ids``/``privilege_ids`` → los ``related_name``
    correspondientes. ``xml_id`` **no se porta**: se computa desde
    ``ir.model.data``, el registro de datos declarativos XML de Odoo, que este
    árbol no tiene — su papel de identificador estable lo cumple el ``name``
    técnico del módulo.
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

    class Meta:
        db_table = 'ir_module_category'
        ordering = ['sequence', 'name', 'id']   # derivado de _order
        verbose_name = 'Aplicación'
        verbose_name_plural = 'Aplicaciones'

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

    ``category`` es la excepción declarada, y su comentario dice por qué.

    Cobertura de campos — 8 de 31, declarada
    =========================================

    ``odoo19c: odoo/addons/base/models/ir_module.py:158-330`` declara **31**
    campos; de ellos coinciden por nombre **8** (``name``, ``shortdesc``,
    ``summary``, ``sequence``, ``application``, ``auto_install``, ``state``,
    ``license``). Otros **2** son formas nuestras: ``category``, un
    desnormalizado de su ``category_id``, y ``version``, que colapsa sus tres
    (``installed_version`` / ``latest_version`` / ``published_version``).

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

    # Sólo los estados que este árbol puede producir. Odoo declara seis; las
    # tres transiciones restantes pertenecen a su instalador.
    STATE_UNINSTALLABLE = 'uninstallable'
    STATE_UNINSTALLED   = 'uninstalled'
    STATE_INSTALLED     = 'installed'
    STATES = [
        (STATE_UNINSTALLABLE, 'No instalable'),
        (STATE_UNINSTALLED,   'No instalado'),
        (STATE_INSTALLED,     'Instalado'),
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
    # ``category`` NO pierde su tope: no tiene contraparte de esta forma en la
    # referencia, que declara ``category_id`` como FK a ``ir.module.category``.
    # Es un desnormalizado nuestro y provisional — su reestructuración es #452.
    category     = fields.Char(max_length=100, blank=True, default='Uncategorized')
    version      = fields.Char(blank=True, default='1.0')
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
        help_text='Derivado de INSTALLED_APPS; no hay instalador que lo escriba.',
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
        diferir de la que el catálogo guardó la última vez que se sembró. Ésa es
        toda su razón de ser: distinguir lo instalado de lo publicado.

        La fuente escribe ``installed_version``, uno de los tres campos de
        versión que aquí colapsan en ``version`` (declarado en el docstring de
        la clase). Por eso aquí **devuelve** el valor en vez de asignarlo: sin
        los tres campos separados no hay dónde escribir la distinción.
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
                                                STATE_UNINSTALLABLE)):
        """≙ ``downstream_dependencies`` (``odoo19c: ir_module.py:531-555``).

        Quién depende de mí, directa o indirectamente. Es la pregunta que la
        fuente hace antes de desinstalar; aquí no hay desinstalador, pero la
        pregunta sigue siendo la que responde *"si retiro este addon, qué se
        rompe"*, y hoy no la responde nada.

        **La lista de estados a excluir diverge, y su razón está medida.** La
        fuente excluye ``('uninstalled', 'uninstallable', 'to remove')``; aquí
        el tercero no existe —es una transición de su instalador, declarada
        fuera del porte en el docstring del módulo—, así que enumerarlo sería
        declarar un estado inalcanzable.

        **El parámetro ``known_deps`` de la fuente no se porta, y es
        deliberado.** Allá es el acumulador de una recursión: cada nivel lo
        pasa al siguiente para no revisitar. Aquí el recorrido es por oleadas
        con marca de visitado interna, así que un parámetro para acumular no
        tiene receptor — declararlo sería una superficie que ningún llamador
        puede usar. Ver ``_walk_dependencies``.
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
        seen = set()
        frontier = {self.name} if forward else {self.pk}

        while frontier:
            if forward:
                names = list(IrModuleDependency.objects.filter(
                    module__name__in=frontier).values_list('name', flat=True))
                found = type(self).objects.filter(name__in=names)
            else:
                names = list(type(self).objects.filter(
                    pk__in=frontier).values_list('name', flat=True))
                found = type(self).objects.filter(
                    dependencies__name__in=names)

            found = found.exclude(state__in=exclude_states).exclude(
                pk__in=seen | {self.pk})
            fresh = {module.pk for module in found}
            if not fresh:
                break
            seen |= fresh
            frontier = ({module.name for module in
                         type(self).objects.filter(pk__in=fresh)}
                        if forward else fresh)

        return type(self).objects.filter(pk__in=seen)


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
        names = {dependency.name for dependency in dependencies}
        by_name = {module.name: module
                   for module in IrModule.objects.filter(name__in=names)}
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
        return IrModule.objects.filter(name=self.name).first()

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
