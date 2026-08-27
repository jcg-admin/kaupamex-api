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
from collections import defaultdict
from random import randint

import fields
import models

from addons.base.models.avatar_mixin import AvatarMixin
from addons.base.models.res_country import ADDRESS_FORMAT_KEYS
from exceptions import ValidationError
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
      field_name que sí existe.
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

    Los tres enganches que Enterprise usa sobre este modelo
    ========================================================

    Medido sobre ``19.x/odoo19-enterprise-main``, clases con
    ``_inherit = 'res.partner'``, cruzado con lo que ``odoo19c:
    res_partner.py`` declara:

    - ``_compute_application_statistics_hook`` — **portado** abajo, con su
      compute y su propiedad. Es el único de los tres que era un hueco: un
      campo cuya base devuelve vacío y que existe **para** que otros lo
      llenen.
    - ``_default_category`` (``odoo19c: :197-198``) — **divergencia de
      mecanismo**. Lee ``category_id`` del ``env.context``, la bolsa de
      contexto por petición del ORM de la referencia. Aquí no hay ``env``:
      el valor inicial de un M2M lo pasa quien crea el registro, y el sitio
      donde se decide es el serializer, no un default del modelo. Portarlo
      con la firma de la fuente exigiría inventar la bolsa de contexto.
    - ``_compute_display_name`` — **divergencia de mecanismo**, y ya
      declarada arriba: los computados quedan fuera y el enganche de nombre
      para mostrar de Django es ``__str__``, que sí está y sí se hereda. La
      diferencia de **contenido** es real: la fuente encadena el nombre
      completo con la empresa; ``__str__`` da ``nombre (tipo)`` para una
      dirección y el nombre a secas para un contacto.

    *Métrica:* nombres declarados en el cuerpo de las clases de Enterprise
    que heredan de ``res.partner``, intersectados con los que la referencia
    declara y este archivo no.
    *Ciega a:* un enganche que Enterprise consuma por ``super()`` de un
    tercero sin declararlo.
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

    # ---- El campo que existe para que otros addons lo llenen -------------

    @classmethod
    def _compute_application_statistics_hook(cls, partners):
        """≙ ``_compute_application_statistics_hook`` (``odoo19c:
        res_partner.py:320-324``).

        Docstring de la fuente: *"Hook for override, as overriding compute
        method does not update cache accordingly. All overrides receive False
        instead of previously assigned value."* Es decir: el enganche existe
        **porque sobreescribir el compute no sirve** allá; aquí no hay motor
        de compute que invalidar, pero el enganche se porta igual, y por la
        misma razón práctica: es el único punto por el que un addon aporta
        estadísticas sin tocar este archivo.

        Devuelve un mapa ``{pk: [estadística, …]}``. La base no aporta
        ninguna — igual que la fuente, que devuelve un ``defaultdict`` vacío.

        Recibe ``partners`` en vez de operar sobre ``self`` porque aquí no
        hay recordset: el lote es explícito. Es la misma divergencia de firma
        que ``IrModelFields._reflect_field_params``.
        """
        return defaultdict(list)

    @classmethod
    def _compute_application_statistics(cls, partners):
        """≙ ``_compute_application_statistics`` (``:315-318``).

        Reparte por ``pk`` lo que el enganche devuelva, dando lista vacía al
        partner que nadie mencionó. La fuente escribe el resultado en el
        campo; aquí lo devuelve, porque el campo es una propiedad derivada y
        no una columna.
        """
        result = cls._compute_application_statistics_hook(partners)
        return {p.pk: result.get(p.pk, []) for p in partners}

    @property
    def application_statistics(self):
        """≙ el campo ``application_statistics`` (``:313``).

        Allá es ``fields.Json`` con ``compute=`` y **sin** ``store``: un
        derivado que se recalcula al leerlo. Aquí eso es una propiedad, que
        es lo mismo sin columna que mantener.
        """
        return type(self)._compute_application_statistics([self])[self.pk]

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

        ≙ ``_compute_contact_address`` (``odoo19c: base/models/res_partner.py``).
        """
        return ', '.join(
            part for part in (self.street, self.city, self.zip) if part)

    # === Entidad comercial ================================================
    # Adaptación de ``_compute_commercial_partner`` /
    # ``_compute_commercial_company_name`` — ``odoo19c: res_partner.py:515-521``
    # y ``:523-526``; idénticos en ``odoo18c: :450-456``. Allá son campos
    # ``compute=... store=True``; aquí son propiedades, que es como este árbol
    # expresa un computado (mismo patrón que ``ResCompany.name``).

    # ------------------------------------------------------------------
    # Puntos de enganche del contacto — ``odoo19c: res_partner.py:660-700``.
    # Enterprise 19 los extiende 5 veces (tarea #78); cada addon SUMA a lo que
    # devuelve el ``super()``, así que sin base que extender dos addons se
    # pisarían. Mismo criterio con que se cerraron ``SELF_READABLE_FIELDS`` y
    # ``_load_menus_blacklist`` (:ref:`h-api-819`).
    # ------------------------------------------------------------------
    @classmethod
    def _address_fields(cls):
        """≙ ``_address_fields`` (``odoo19c: res_partner.py:659-662``).

        Docstring de la fuente, verbatim: *"Returns the list of address fields
        that are synced from the parent."*

        La fuente devuelve ``list(ADDRESS_FIELDS)``, su tupla de módulo. Aquí
        el nombre del campo cambia por la convención de este árbol —``state_id``
        y ``country_id`` son ``state`` y ``country``—, y esa correspondencia es
        la única divergencia.
        """
        return ['street', 'street2', 'zip', 'city', 'state', 'country']

    @classmethod
    def _formatting_address_fields(cls):
        """≙ ``_formatting_address_fields`` (``odoo19c: res_partner.py:664-667``).

        Docstring de la fuente, verbatim: *"Returns the list of address fields
        usable to format addresses."*

        Delega en :meth:`_address_fields`, como la fuente. Existe aparte porque
        es **otro** punto de extensión: un addon puede querer más campos para
        **formatear** que los que sincroniza del padre, y la fuente le da dos
        ganchos distintos para no obligarle a elegir.
        """
        return cls._address_fields()

    @classmethod
    def _synced_commercial_fields(cls):
        """≙ ``_synced_commercial_fields`` (``odoo19c: res_partner.py:695-700``).

        Docstring de la fuente, verbatim: *"Returns the list of fields that are
        managed by the commercial entity to which a partner belongs. When
        modified on a children, update is propagated until the commercial
        entity."*

        Los que se propagan **hacia arriba**: cambiarlos en un hijo actualiza a
        la entidad comercial. Es el subconjunto estricto de
        :meth:`_commercial_fields`, y por eso se declara antes.
        """
        return ['vat']

    @classmethod
    def _commercial_fields(cls):
        """≙ ``_commercial_fields`` (``odoo19c: res_partner.py:685-693``).

        Docstring de la fuente, verbatim: *"Returns the list of fields that are
        managed by the commercial entity to which a partner belongs. These
        fields are meant to be hidden on partners that aren't `commercial
        entities` themselves, or synchronized at update (if present in
        _synced_commercial_fields), and will be delegated to the parent
        `commercial entity`. The list is meant to be extended by inheriting
        classes."*

        La última frase es el contrato: **está pensado para extenderse**.

        La fuente compone los sincronizados **más dos campos propios**,
        ``company_registry`` e ``industry_id``, y aquí **ninguno de los dos
        existe**: medido, ``company_registry`` sólo aparece en
        ``_rec_names_search`` sin campo que lo respalde, e ``industry_id``
        necesita ``res.partner.industry``, que está sin portar. Así que la
        lista es hoy la de sincronizados a secas, y las dos ausencias se
        nombran aquí en vez de fabricar una lista con campos que no existen.
        Portar los dos campos es la tarea **#48**.
        """
        return list(cls._synced_commercial_fields())

    @property
    def commercial_partner(self):
        """El partner que representa la **entidad comercial** del contacto.

        Sube por la cadena de padres hasta la primera company. Un contacto
        suelto (sin padre) es su propia entidad comercial — por eso el corte
        es ``is_company or not parent``, no sólo ``is_company``.

        ≙ ``_compute_commercial_partner`` (``odoo19c: base/models/res_partner.py``).
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

        ≙ ``_compute_commercial_company_name`` (``odoo19c: base/models/res_partner.py``).
        """
        p = self.commercial_partner
        return p.name if p.is_company else self.company_name


class FormatVatLabelMixin:
    """``format.vat.label.mixin`` — ≙ ``FormatVatLabelMixin``
    (``odoo19c: odoo/addons/base/models/res_partner.py:45-58``).

    El identificador fiscal no se llama igual en todas partes: «RFC» en
    Mexico, «NIF» en Espana. La fuente resuelve la etiqueta desde el pais de
    la empresa (``env.company.country_id.vat_label``) y la **inyecta en el XML
    de la vista**, tanto en el ``<field name="vat">`` como en su ``<label>``.

    DIVERGENCIA DE MECANISMO, medida y declarada. Medido en este arbol:

    - el **dato** SI esta: ``ResCountry.vat_label``
      (``res_country.py:84``), portado con su ``help_text``;
    - el **mecanismo** de la fuente NO: ``_get_view`` da **0 hits** en todo
      el arbol (``grep -rn "def _get_view\b" src/ addons/``). No hay arch XML
      que mutar porque la interfaz es React y consume JSON.

    Por eso el mixin porta el metodo que **calcula** la etiqueta —que es la
    decision— y no el que la escribe en un arbol XML que aqui no existe. Un
    serializer que exponga ``vat`` lee ``vat_label_for`` y manda la etiqueta
    en la respuesta; ese cableado es la tarea **#47**.
    """

    _name = 'format.vat.label.mixin'
    _description = 'Country Specific VAT Label'

    @staticmethod
    def vat_label_for(company):
        """La etiqueta del identificador fiscal segun el pais de la empresa.

        ≙ la condicion ``if vat_label := self.env.company.country_id.vat_label``
        de la fuente (``:49``). Devuelve cadena vacia cuando el pais no
        declara tag, que es cuando la fuente no toca nada.
        """
        country = getattr(company, 'country', None)
        return getattr(country, 'vat_label', '') or ''


class FormatAddressMixin:
    """``format.address.mixin`` — ≙ ``FormatAddressMixin``
    (``odoo19c: odoo/addons/base/models/res_partner.py:61-136``).

    Una direccion no se escribe en el mismo orden en todos los paises: en unos
    va «codigo postal, ciudad, estado» y en otros «ciudad, estado, codigo
    postal». La fuente lee ``country.address_format`` y **reordena los nodos
    del XML** de la vista para que el usuario vea el orden al que esta
    acostumbrado.

    DIVERGENCIA DE MECANISMO, medida y declarada — la misma que el mixin de
    arriba y por la misma razon:

    - el **dato** SI esta: ``ResCountry.address_format``
      (``res_country.py:74``) con sus once claves admitidas en
      ``ADDRESS_FORMAT_KEYS``;
    - el **mecanismo** NO: ``_get_view``, ``_get_view_cache_key`` y
      ``postprocess_and_fields`` dan **0 hits**; ``ir.ui.view`` no tiene arch
      que postprocesar en este arbol.

    Lo que SI se porta es ``_extract_fields_from_address``, que es **trabajo
    de cadena puro** y por tanto independiente del canal: dice en que orden
    van los campos, que es exactamente lo que una interfaz React necesita
    recibir para pintarlos bien. Su consumidor —el serializer que exponga ese
    orden— es la tarea **#47**.

    Lo que NO se porta, y su razon: ``_view_get_address`` (muta nodos
    ``//div[hasclass('o_address_format')]`` con XPath), ``_get_view`` y
    ``_get_view_cache_key``. Los tres operan sobre un arbol XML de vista Odoo;
    no hay conducta que replicar porque no hay arbol.
    """

    _name = 'format.address.mixin'
    _description = 'Address Format'

    #: ≙ ``ADDRESS_FIELDS + ('state_code', 'state_name')`` de la fuente
    #: (``:71``). Se toma de ``res_country.ADDRESS_FORMAT_KEYS``, que ya porta
    #: la lista completa con sus derivados.
    @staticmethod
    def _extract_fields_from_address(address_line):
        """≙ ``_extract_fields_from_address`` (``:65-72``).

        Docstring de la fuente, verbatim: *"Extract keys from the address
        line. For example, if the address line is ``"zip: %(zip)s, city:
        %(city)s."``, this method will return ``['zip', 'city']``."*

        El orden de salida es el de **aparicion en la linea**, no el de la
        lista de claves: por eso la fuente ordena por ``address_line.index``.
        Es lo unico que importa del metodo — decir en que orden van.
        """
        candidates = ['%(' + field_name + ')s'
                      for field_name in ADDRESS_FORMAT_KEYS]
        return sorted(
            [c[2:-2] for c in candidates if c in address_line],
            key=address_line.index)

    @classmethod
    def field_order_for(cls, country):
        """El orden de ``zip`` / ``city`` / ``state`` que pide ``country``.

        Es la decision que ``_view_get_address`` toma antes de mover nodos
        (``:105-108``): busca la **linea del formato que contiene la ciudad**
        y de ahi saca el orden. Sin el XML de por medio, esa decision es todo
        lo que hay que portar.

        Devuelve lista vacia cuando el pais no declara formato, que es cuando
        la fuente no reordena nada.
        """
        fmt = getattr(country, 'address_format', '') or ''
        lines = [cls._extract_fields_from_address(line)
                  for line in fmt.split('\n') if 'city' in line]
        return lines[0] if lines else []



class ResPartnerCategory(TimeStampedModel):
    """``res.partner.category`` — ≙ ``ResPartnerCategory``
    (``odoo19c: odoo/addons/base/models/res_partner.py:139-181``).

    Las etiquetas con que se clasifica un contacto, y son **jerarquicas**: una
    tag puede colgar de otra, y su nombre para mostrar es la cadena
    completa (``'Clientes / Mayoristas / Norte'``). Esa jerarquia es lo que
    hace que el modelo no sea una tabla de dos columnas.

    Estaba ausente de este arbol: ``res_partner.py`` declaraba **una** clase
    contra las cuatro de la referencia.
    """

    _name = 'res.partner.category'
    _description = 'Partner Tags'
    _order = 'name, id'
    _parent_store = True

    #: Tope del reparto de color — ``randint(1, 11)`` de la fuente (``:144``).
    COLOR_MAX = 11

    name = fields.Char(max_length=120, verbose_name='Nombre')
    color = fields.Integer(
        default=0, verbose_name='Color',
        help_text='Odoo color. Un entero de 1 a 11 repartido al azar al crear.')
    parent = fields.Many2one(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        db_index=True, related_name='child_ids', verbose_name='Categoría',
        help_text='Odoo parent_id, con ondelete cascade.')
    active = fields.Boolean(
        default=True,
        help_text='Permite ocultar la categoría sin borrarla (Odoo active).')
    parent_path = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Ruta de ancestros',
        help_text="Ruta materializada '1/4/9/' — sostiene _parent_store.")
    partners = fields.Many2many(
        ResPartner, blank=True, related_name='category_ids',
        verbose_name='Contactos',
        help_text='Odoo partner_ids, con column1=category_id.')

    class Meta:
        db_table = 'res_partner_category'
        ordering = ['name', 'id']
        verbose_name = 'Etiqueta de contacto'
        verbose_name_plural = 'Etiquetas de contacto'

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        """Siembra el color al azar y mantiene la ruta materializada.

        El color solo se reparte **al crear** y solo si nadie lo puso, que es
        lo que hace el ``default=_get_default_color`` de la fuente: un default
        callable corre una vez, no en cada escritura.
        """
        creating = self._state.adding
        if creating and not self.color:
            self.color = self._get_default_color()
        self._check_parent_id()
        result = super().save(*args, **kwargs)
        path = self._compute_parent_path()
        if self.parent_path != path:
            type(self).objects.filter(pk=self.pk).update(parent_path=path)
            self.parent_path = path
        return result

    @staticmethod
    def _get_default_color():
        """≙ ``_get_default_color`` (``:143-144``).

        La fuente reparte un color al azar entre once para que las etiquetas
        se distingan de un vistazo. Alla es el ``default=`` callable del campo;
        aqui lo llama ``save()`` al crear, que es cuando ese default corre.
        """
        return randint(1, ResPartnerCategory.COLOR_MAX)

    def _check_parent_id(self):
        """≙ ``_check_parent_id`` (``:157-160``) — ``@api.constrains``.

        Mensaje de la fuente, verbatim: *"You can not create recursive tags."*
        La fuente lo resuelve con ``_has_cycle()`` del ORM; aqui se recorre la
        cadena, que es lo que ese helper hace por dentro.
        """
        seen = set()
        current = self.parent
        while current is not None:
            if current.pk == self.pk or current.pk in seen:
                raise ValidationError('No se pueden crear etiquetas recursivas.')
            seen.add(current.pk)
            current = current.parent

    def _compute_parent_path(self):
        """Ruta materializada del ancestro, terminada en ``/``.

        Mismo mecanismo que ``ResCompany._compute_parent_path`` — el
        ``_parent_store`` de la referencia se sostiene sobre esta columna.
        """
        if self.parent_id is None:
            return f'{self.pk}/'
        return f'{self.parent.parent_path}{self.pk}/'

    @property
    def display_name(self):
        """≙ ``_compute_display_name`` (``:162-172``).

        Docstring de la fuente: *"Return the categories' display name,
        including their direct parent by default."* La cadena completa
        separada por ``' / '``, de la raiz hacia abajo.
        """
        names = []
        current = self
        while current is not None:
            names.append(current.name or '')
            current = current.parent
        return ' / '.join(reversed(names))

    @classmethod
    def _search_display_name(cls, operator, value):
        """≙ ``_search_display_name`` (``:174-181``).

        Buscar por nombre para mostrar devuelve la etiqueta **y toda su
        descendencia** —el ``child_of`` de la fuente—, porque quien busca
        "Clientes" espera tambien "Clientes / Mayoristas".

        DIVERGENCIA declarada: la fuente devuelve ``NotImplemented`` para los
        operadores negados (``not like``), porque su dominio no sabe negar un
        ``child_of``. Aqui se conserva esa negativa: un ``not`` sobre la
        jerarquia pediria el complemento de un arbol, que no es lo mismo que
        negar cada nombre.
        """
        if not operator.endswith('like'):
            return models.Q(name__iexact=value)
        if operator.startswith('not'):
            return NotImplemented
        roots = cls.objects.filter(name__icontains=value)
        paths = [r.parent_path for r in roots if r.parent_path]
        condition = models.Q(pk__in=[r.pk for r in roots])
        for path in paths:
            condition |= models.Q(parent_path__startswith=path)
        return condition
