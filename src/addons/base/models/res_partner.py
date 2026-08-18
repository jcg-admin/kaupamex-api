"""``res.partner`` — el party (Odoo ``base``).

Portación fiel de ``odoo19c: odoo/addons/base/models/res_partner.py``
(LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

**Por qué vive aquí y no en un addon propio.** La referencia declara
``res.partner`` en el núcleo ``base``, junto a ``res.company``, ``res.country``
y ``res.currency``. No es una elección de gusto: **170 addons de Community 19
lo extienden** por ``_inherit``. Un modelo con esa gravedad no puede vivir en
una hoja — todos dependerían de esa hoja. Ver H-API-119.

**Una persona, una empresa y una dirección son el mismo modelo.** Es la
decisión de diseño que más sorprende al llegar de un esquema normalizado, y es
deliberada en la referencia: ``is_company`` distingue empresa de persona, y una
dirección es un partner **hijo** (``parent_id``) con ``type`` en
``invoice``/``delivery``. Así una dirección de facturación puede tener su
propio email y teléfono sin duplicar tablas, y un contacto puede promoverse a
cliente sin migrar filas.

**Lo que Django no tiene.** ``_inherits`` (herencia por delegación) no existe;
``ResUsers`` la reimplementa con una FK requerida más propiedades que
reenvían. Ver ``res_users.py``.
"""
import fields
import models

from addons.base.models.avatar_mixin import AvatarMixin
from addons.base.models.timestamped_mixin import TimeStampedModel


class ResPartner(AvatarMixin, TimeStampedModel):
    """``res.partner`` — persona, empresa o dirección.

    Fiel a ``odoo19c: odoo/addons/base/models/res_partner.py:213-309``. Se
    portan los campos **estructurales**; los computados (``display_name``,
    ``email_formatted``, ``company_type``) y los que pertenecen a otros addons
    (``customer_rank`` es de ``account``, no de ``base``) quedan fuera: portar
    aquí un campo que la referencia declara en otro módulo sería inventar una
    dependencia que ella no tiene.

    **Hereda ``avatar.mixin``**, igual que la referencia
    (``res_partner.py:187``: ``_inherit = [… 'avatar.mixin' …]``). De ahí
    salen ``image_1920`` y sus cuatro reducciones más el avatar generado —
    y con ellas el ``logo`` de ``res.company``, que es ``related`` a
    ``partner_id.image_1920``. El hueco se destapó al portar ``res_company``:
    la delegación del logotipo no tenía de dónde leer.

    ``TimeStampedModel`` se conserva **explícitamente** en la lista de bases:
    ``AvatarMixin`` hereda de ``ImageMixin``, y ``ImageMixin`` hereda de
    ``models.Model``, **no** de ``TimeStampedModel``. Sustituir una base por la
    otra habría borrado las marcas de tiempo en silencio.

    Atributos de clase — 8 de los 9 que la fuente declara
    ======================================================

    Medido sobre ``odoo19c: res_partner.py:185-195`` (tarea #385) y
    ``:326`` (tarea #504). Se portan verbatim los ocho que no exigen un
    símbolo ausente **en este archivo**:

    - ``_name`` / ``_description`` — el nombre punteado y su etiqueta. El
      primero es lo que registra ``orm.registry.MODELS_BY_NAME``, y sin él
      la delegación ``_inherits`` de ``res.users`` no puede resolver a quién
      delega: pide ``'res.partner'`` por nombre, no por clase.
    - ``_inherit`` — los cuatro mixins de la fuente. Aquí sólo ``avatar.mixin``
      está construido; los otros tres se declaran igual porque el atributo
      **nombra la extensión aunque el mixin aún no exista**, que es lo que hace
      greppeable el hueco.
    - ``_order`` — verbatim. ``Meta.ordering`` **no** puede derivarse tal cual:
      ``complete_name`` es un campo computado que este puerto no trae (medido:
      0 apariciones en este archivo), así que la forma Django ordena por el
      campo que sí existe.
    - ``_rec_names_search`` — los cinco campos que ``name_search`` considera.
    - ``_allow_sudo_commands`` / ``_check_company_auto`` — verbatim.
    - ``_complete_name_displayed_types`` (``:195``) — constante de clase, no
      atributo de ORM (categoría 3 de ``atributos-de-clase-de-modelo.md``).
      Se porta aunque su único consumidor —el compute de ``complete_name``—
      no esté construido: la regla exige portar la constante en sí, no su
      consumidor.
    - el objeto de tabla ``_check_name`` (``:326``) — vive en
      ``Meta.constraints`` como ``models.CheckConstraint``, con el nombre de
      la referencia conservado: ``full_name()`` en
      ``odoo19c: odoo/orm/table_objects.py:55-58`` compone
      ``f"{model._table}_{self.name}"`` con ``self.name`` = el atributo sin
      guion bajo (``__set_name__``, ``:40-46``), así que el nombre real de la
      fuente es ``res_partner_check_name`` — el mismo que aquí.

    **El único que NO se porta, y por qué** (``hallazgo-abierto-genera-sucesor``):

    - ``_check_company_domain = models.check_company_domain_parent_of``
      (``odoo19c: :192``) referencia un símbolo de
      ``odoo19c: odoo/orm/models.py:169`` que **no existe** en ``src/orm`` —
      y su hogar correcto **es** ``src/orm/models.py`` (raíz espejada;
      segunda cláusula de ``atributos-de-clase-de-modelo.md``), no este
      archivo. Escribirlo aquí sería fabricar el símbolo en el sitio
      equivocado, el mismo defecto que ``H-API-578``. El bloqueo es de
      **alcance de escritura de la tarea #504** (sólo este archivo, sus
      migraciones y sus tests — no ``src/orm/**``), no de capacidad: el
      mecanismo consumidor (el check de coherencia de empresa en ``save()``)
      tampoco existe en ninguna parte de ``src/orm`` (medido: 0 apariciones
      de ``check_company`` fuera de este docstring), así que construirlo
      exige tocar el ORM espejado — mecanismo transversal que usan **21
      clases** de la referencia, no sólo ``res.partner``.
    """

    _name                = 'res.partner'
    _description         = 'Contact'
    _inherit             = ['format.address.mixin', 'format.vat.label.mixin',
                            'avatar.mixin', 'properties.base.definition.mixin']
    _order               = 'complete_name ASC, id DESC'
    _rec_names_search    = ['complete_name', 'email', 'ref', 'vat',
                            'company_registry']
    _allow_sudo_commands = False
    _check_company_auto  = True

    # Los tipos de partner que se anexan al nombre completo (Odoo
    # ``odoo19c: res_partner.py:195``). Constante de clase, no atributo de
    # ORM (categoría 3, ``atributos-de-clase-de-modelo.md``) — se porta aunque
    # su consumidor (compute de ``complete_name``) no esté construido aquí.
    _complete_name_displayed_types = ('invoice', 'delivery', 'other')

    # ``type`` — un partner hijo es una dirección; el padre es el titular.
    TYPE_CONTACT  = 'contact'
    TYPE_INVOICE  = 'invoice'
    TYPE_DELIVERY = 'delivery'
    TYPE_OTHER    = 'other'
    TYPES = [
        (TYPE_CONTACT,  'Contacto'),
        (TYPE_INVOICE,  'Facturación'),
        (TYPE_DELIVERY, 'Entrega'),
        (TYPE_OTHER,    'Otra'),
    ]

    name        = fields.Char(
        max_length=200, db_index=True,
        help_text='Nombre de la persona o empresa (Odoo res.partner.name).',
    )
    parent      = fields.Many2one(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children', db_index=True,
        help_text=(
            'Titular del que este partner es contacto o dirección '
            '(Odoo parent_id). Su reverso ``children`` es Odoo child_ids.'
        ),
    )
    type        = fields.Selection(
        max_length=16, choices=TYPES, default=TYPE_CONTACT,
        help_text='Tipo de dirección (Odoo res.partner.type).',
    )
    is_company  = fields.Boolean(
        default=False,
        help_text='True = empresa; False = persona física (Odoo is_company).',
    )
    active      = fields.Boolean(
        default=True, db_index=True,
        help_text='Archivado sin borrar (Odoo active).',
    )

    # --- Contacto ---
    email       = fields.Char(max_length=254, blank=True, default='')
    phone       = fields.Char(max_length=32,  blank=True, default='')
    website     = fields.Char(max_length=255, blank=True, default='')
    vat         = fields.Char(
        max_length=32, blank=True, default='', db_index=True,
        help_text='RFC / Tax ID (Odoo vat). Lo valida ``base_vat``.',
    )
    function    = fields.Char(
        max_length=120, blank=True, default='',
        help_text='Puesto (Odoo function).',
    )
    company_name = fields.Char(
        max_length=150, blank=True, default='',
        help_text='Razón social escrita a mano cuando el contacto NO cuelga '
                  'de una empresa (Odoo ``company_name``, '
                  '``odoo19c: res_partner.py:308``).',
    )
    employee    = fields.Boolean(
        default=False,
        help_text='Marca de contacto empleado (Odoo employee).',
    )

    # --- Dirección. Plana, como la referencia: no hay tabla de direcciones. ---
    street      = fields.Char(max_length=255, blank=True, default='')
    street2     = fields.Char(max_length=255, blank=True, default='')
    zip         = fields.Char(max_length=16,  blank=True, default='', db_index=True)
    city        = fields.Char(max_length=120, blank=True, default='')
    state       = fields.Many2one(
        'base.ResCountryState', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='partners',
        help_text='Estado/provincia (Odoo state_id).',
    )
    country     = fields.Many2one(
        'base.ResCountry', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='partners',
        help_text='País (Odoo country_id).',
    )

    # Índice de color de la paleta del cliente. La referencia lo declara en
    # ``res.partner`` con ``default=0`` (``res_partner.py:286``) — no confundir
    # con el ``color`` de ``res.partner.category``, que allá es aleatorio
    # (``randint(1, 11)``) y pertenece a otra clase del mismo archivo.
    # ``res.company._compute_color`` lo lee y, si es 0, cae a ``id % 12``.
    color       = fields.Integer(
        default=0, verbose_name='Índice de color',
        help_text='Odoo color. 0 = sin color declarado.',
    )

    # --- Localización ---
    lang        = fields.Char(
        max_length=16, blank=True, default='',
        help_text='Idioma preferido (Odoo lang).',
    )
    tz          = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Zona horaria (Odoo tz).',
    )
    comment     = fields.Text(blank=True, default='')

    class Meta:
        db_table            = 'res_partner'
        # Derivado de ``_order = 'complete_name ASC, id DESC'``. ``complete_name``
        # es un compute que este puerto no trae, así que el primer tramo se
        # sustituye por ``name`` — el campo que lo alimenta en la fuente. El
        # segundo tramo se conserva verbatim.
        ordering            = ['name', '-id']
        verbose_name        = 'Partner'
        verbose_name_plural = 'Partners'
        constraints         = [
            # ``_check_name`` de la fuente (``odoo19c: res_partner.py:326``).
            # Un partner ``type='contact'`` requiere ``name``; una dirección
            # (``invoice``/``delivery``/``other``) puede carecer de él.
            # Nombre conservado: ``full_name()`` compone
            # ``f"{_table}_{atributo sin guion bajo}"``
            # (``odoo19c: odoo/orm/table_objects.py:55-58``).
            models.CheckConstraint(
                condition=(
                    # 'contact' == TYPE_CONTACT; el atributo de clase no es
                    # visible aquí (``class Meta`` no hereda el namespace de
                    # ``ResPartner`` — la scoping de clases de Python no
                    # anida, verificado con un repro mínimo).
                    models.Q(type='contact', name__isnull=False)
                    | ~models.Q(type='contact')
                ),
                name='res_partner_check_name',
                violation_error_message='Contacts require a name',
            ),
        ]

    def __str__(self) -> str:
        if self.parent_id and self.type != self.TYPE_CONTACT:
            return f'{self.name} ({self.get_type_display()})'
        return self.name

    @property
    def is_address(self) -> bool:
        """Un partner hijo con ``type`` distinto de contacto es una dirección."""
        return bool(self.parent_id) and self.type != self.TYPE_CONTACT

    @property
    def contact_address(self) -> str:
        """Dirección en una línea — el ``contact_address`` de la referencia.

        En Odoo es un compute sobre ``_display_address`` con formato por
        país (``odoo19c: res_partner.py``, campo ``contact_address``); aquí
        el consumidor es el descriptor del PDF, que imprime UNA línea, así
        que se unen las partes presentes con coma. La lógica vivía inline en
        el builder del recibo (``sale/report/report_catalog.py``); ahora la
        dueña es el partner y tanto el builder como la plantilla en BD la
        leen de aquí.
        """
        return ', '.join(
            part for part in (self.street, self.city, self.zip) if part)

    # === Entidad comercial ================================================
    # Adaptación de ``_compute_commercial_partner`` /
    # ``_compute_commercial_company_name`` — ``odoo19c: res_partner.py:515-521``
    # y ``:523-526``; idénticos en ``odoo18c: :450-456``. Allá son campos
    # ``compute=... store=True``; aquí son propiedades, que es como este árbol
    # expresa un computado (mismo patrón que ``ResCompany.name``).

    @property
    def commercial_partner(self):
        """El partner que representa la **entidad comercial** del contacto.

        Sube por la cadena de padres hasta la primera empresa. Un contacto
        suelto (sin padre) es su propia entidad comercial — por eso el corte
        es ``is_company or not parent``, no sólo ``is_company``.
        """
        if self.is_company or not self.parent_id:
            return self
        return self.parent.commercial_partner

    @property
    def commercial_company_name(self):
        """Razón social de la entidad comercial.

        Si la entidad comercial es una empresa, su ``name``; si no, el
        ``company_name`` escrito a mano en este contacto. La referencia lo
        resuelve con ``p.is_company and p.name or partner.company_name``.
        """
        p = self.commercial_partner
        return p.name if p.is_company else self.company_name
