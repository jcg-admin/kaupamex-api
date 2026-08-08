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

    name        = fields.Char(max_length=120)
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
        ordering = ['sequence', 'name', 'id']
        verbose_name = 'Aplicación'
        verbose_name_plural = 'Aplicaciones'

    def __str__(self):
        return self.name


class IrModule(TimeStampedModel):
    """Un addon del árbol, con la metadata que declara su ``__manifest__.py``.

    ``name`` es el **nombre técnico** —la carpeta—, igual que en la referencia.
    Es lo que lo distingue del catálogo comercial, cuyo ``code`` es un nombre de
    dominio que puede no coincidir con ninguna carpeta.
    """

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
        max_length=100, unique=True, db_index=True,
        help_text='Nombre técnico = carpeta del addon (Odoo ir.module.module.name).',
    )
    shortdesc    = fields.Char(
        max_length=200, blank=True, default='',
        help_text='Nombre legible del manifest (Odoo shortdesc ← manifest name).',
    )
    summary      = fields.Char(max_length=255, blank=True, default='')
    category     = fields.Char(max_length=100, blank=True, default='Uncategorized')
    version      = fields.Char(max_length=32, blank=True, default='1.0')
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
        ordering     = ['name']
        verbose_name = 'Módulo técnico'

    def __str__(self):
        return f'{self.name} ({self.state})'


class IrModuleDependency(TimeStampedModel):
    """Una arista ``depends`` declarada por el manifest de un addon.

    Tabla aparte y no un M2M a ``IrModule``, igual que la referencia: la
    dependencia se declara por **nombre**, y el nombre puede apuntar a un addon
    que todavía no está en el catálogo. Un M2M exigiría que el destino exista, y
    perdería justamente el caso que interesa detectar.
    """

    module = fields.Many2one(
        IrModule, on_delete=models.CASCADE, related_name='dependencies',
        help_text='El addon que declara la dependencia.',
    )
    name   = fields.Char(
        max_length=100, db_index=True,
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
