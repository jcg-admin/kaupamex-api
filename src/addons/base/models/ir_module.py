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

from addons.base.models.timestamped_mixin import TimeStampedModel


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

    class Meta:
        db_table            = 'ir_module_module_dependency'
        unique_together     = [('module', 'name')]
        ordering            = ['name']
        verbose_name        = 'Dependencia de módulo'
        verbose_name_plural = 'Dependencias de módulo'

    def __str__(self):
        return f'{self.module.name} → {self.name}'
