"""Dirección estructurada — RELATED de la extensión que Odoo pone en ``res.partner``.

Odoo ``base_address_extended/models/res_partner.py`` extiende ``res.partner``
vía ``_inherit`` con ``street_name`` / ``street_number`` / ``street_number2``
(compute/inverse desde ``street``) + ``city_id`` (FK ``res.city``) +
``country_enforce_cities`` (related de ``country_id.enforce_cities``).

El destino del ``_inherit`` es ``base.ResPartner`` — el mismo modelo que la
referencia extiende. El ``_inherit`` se modela como RELATED OneToOne
(DEC-SALE-01): ``AddressStructured`` cuelga de ``res.partner`` sin inyectar
columnas en su tabla, y aloja la descomposición estructurada de la calle + el
enlace al catálogo ``res.city``.

**Corrección (H-API-210).** Hasta ``api@e2c3022`` este FK apuntaba a
``users.Address``, un modelo que la referencia no tiene: allí la dirección son
**campos** de ``res.partner`` (``ADDRESS_FIELDS`` en
``odoo19c: base/models/res_partner.py:25``), no un modelo aparte. Al disolverse
``users`` en ``base`` el apuntador quedó colgado; se re-apunta al destino fiel.
"""
import fields
import models

from addons.base.models.res_partner import ResPartner
from addons.base_address_extended.models.res_city import ResCity
from addons.base_address_extended.services import street_split
from orm.method_chain import chain_method, wrap_method


class AddressStructured(models.Model):
    """Descomposición estructurada de la calle de un ``res.partner`` (Odoo
    ``street_name``/``street_number``/``street_number2`` + ``city_id``).
    """
    _inherit = 'res.partner'

    partner        = models.OneToOneField(
        'base.ResPartner', on_delete=models.CASCADE, related_name='structured',
        help_text='Partner al que pertenece (Odoo _inherit res.partner).',
    )
    city_id       = fields.Many2one(
        'base_address_extended.ResCity', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='addresses',
        help_text='Ciudad del catálogo (Odoo city_id → res.city).',
        db_column='city_id',
    )
    street_name    = fields.Char(
        max_length=200, blank=True, default='',
        help_text='Nombre de la calle (Odoo street_name).',
    )
    street_number  = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Número exterior (Odoo street_number / House).',
    )
    street_number2 = fields.Char(
        max_length=32, blank=True, default='',
        help_text='Número interior / puerta (Odoo street_number2 / Door).',
    )

    class Meta:
        db_table = 'res_partner_address_structured'
        verbose_name = 'Dirección estructurada'
        verbose_name_plural = 'Direcciones estructuradas'

    def __str__(self) -> str:
        return self.inverse_to_street()

    # -- ≙ _compute_street_data (street -> partes) --------------------------
    def _compute_street_data(self, street):
        """Descompone ``street`` en las tres sub-partes — ≙ ``:32-37``.

        Conserva el nombre de la fuente con su guion bajo: allá es el
        ``compute`` de los tres campos, superficie que el ORM invoca. Se
        llamaba ``compute_from_street``, que lo publicaba como API.

        La fuente itera el recordset y llama ``partner.update(...)``; aquí
        ``self`` es una instancia y recibe ``street`` como argumento, porque la
        calle vive en ``base.ResPartner`` y esta fila es su RELATED.
        """
        parts = street_split(street)
        self.street_name = parts['street_name']
        self.street_number = parts['street_number']
        self.street_number2 = parts['street_number2']
        return parts

    # -- ≙ _inverse_street_data (partes -> street) --------------------------
    def _inverse_street_data(self):
        """Recompone la calle desde las sub-partes — ≙ ``:24-30``.

        ``name number`` y ``- number2`` si existe, con el mismo ``strip()`` de
        la fuente. Se llamaba ``inverse_to_street``; el guion bajo se restituye
        por la misma razón que en :meth:`_compute_street_data`.

        La fuente asigna a ``partner.street``; aquí lo **devuelve**, porque la
        columna ``street`` es de ``base.ResPartner`` y quien la escriba decide
        cuándo.
        """
        street = ((self.street_name or '') + ' ' + (self.street_number or '')).strip()
        if self.street_number2:
            street = street + ' - ' + self.street_number2
        return street

    def _get_street_split(self):
        """Las tres sub-partes — ≙ ``_get_street_split`` (``:39-45``).

        El ``ensure_one()`` de la fuente no se porta: aquí ``self`` es **una**
        instancia por construcción. Mismo criterio que
        ``src/addons/base/models/res_company.py:744``.

        Homónimo de ``base.ResPartner._get_street_split``
        (``src/addons/base/models/res_partner.py:2419``) y con el mismo
        contrato, en otro receptor: allá las partes salen de partir la calle al
        vuelo, aquí de las tres columnas ya descompuestas.
        """
        return {
            'street_name': self.street_name,
            'street_number': self.street_number,
            'street_number2': self.street_number2,
        }

    @property
    def country_enforce_cities(self):
        """Related de ``country_id.enforce_cities`` (Odoo): la política del país
        de la ciudad enlazada. ``False`` si no hay ciudad o país sin política."""
        if self.city_id is None:
            return False
        policy = getattr(self.city_id.country_id, 'address_policy', None)
        return bool(policy and policy.enforce_cities)


# ---------------------------------------------------------------------------
# Lo que el addon cuelga de ``base.ResPartner`` — ≙ el ``_inherit`` de la fuente
# ---------------------------------------------------------------------------
#
# Los cuatro símbolos de abajo están declarados en la fuente sobre
# ``res.partner``, no sobre un modelo propio, así que su receptor aquí es
# ``base.ResPartner`` y no ``AddressStructured``. Lo que cambia es de dónde sale
# ``city_id``: allá es una columna más de ``res.partner``; aquí vive en el
# RELATED (DEC-SALE-01), y estos cuerpos lo alcanzan por ``partner.structured``.


def _structured_of(partner):
    """La fila RELATED del contacto, o ``None`` si todavía no tiene.

    El OneToOne inverso levanta ``RelatedObjectDoesNotExist`` cuando no hay
    fila; devolver ``None`` es lo que deja a los cuerpos de abajo leerse como
    los de la fuente, donde la columna siempre está.
    """
    try:
        return partner.structured
    except AddressStructured.DoesNotExist:
        return None


def _address_fields(cls):
    """Añade ``city_id`` a los campos que se heredan del padre — ≙ ``:20-22``.

    ACUMULA: la fuente escribe ``super()._address_fields() + ['city_id']``, así
    que se cuelga con ``combine=extend_list`` y el terminal de ``base``
    conserva los seis suyos (medido: ``['street', 'street2', 'zip', 'city',
    'state', 'country']``).
    """
    return ['city_id']


def _onchange_city_id(self):
    """Propaga la ciudad elegida al contacto — ≙ ``:47-56``.

    Copia ``name``/``zipcode``/``state_id`` de la ciudad al contacto, y los
    limpia si la ciudad se retira. El nombre del campo de estado es ``state``
    en este árbol (``src/addons/base/models/res_partner.py:454``), que es la
    única correspondencia que cambia.

    La rama ``elif self._origin`` de la fuente distingue un registro ya
    guardado de uno en formulario nuevo — su ``_origin`` es el registro
    original del onchange. Aquí el equivalente es ``self.pk``: una fila sin
    clave todavía no tiene nada guardado que limpiar.
    """
    structured = _structured_of(self)
    city = structured.city_id if structured is not None else None
    if city is not None:
        self.city = city.name
        self.zip = city.zipcode
        self.state = city.state_id
    elif self.pk:
        self.city = ''
        self.zip = ''
        self.state = None


def _onchange_country_id(self, previous):
    """Suelta la ciudad si ya no pertenece al país — ≙ ``:58-62``.

    Va por ``overrides=`` (``orm.method_chain.wrap_method``) y no por
    ``metodos=``, porque la fuente llama a ``super()`` **primero** y luego hace
    lo suyo; ningún mecanismo que fije el orden por el resultado replica eso.

    El receptor previo existe y hace su trabajo: ``base.ResPartner
    ._onchange_country_id`` (``src/addons/base/models/res_partner.py:1191``)
    invalida el estado que pertenecía a otro país. Este cuerpo añade la mitad
    del addon: soltar también la ciudad.
    """
    previous()
    structured = _structured_of(self)
    if structured is None or structured.city_id is None:
        return
    if self.country is not None and (
            structured.city_id.country_id_id != self.country.pk):
        structured.city_id = None


def _get_res_city_by_name(cls, name, country_id):
    """La ciudad de ese país cuyo nombre coincide — ≙ ``:64-76``.

    ``=ilike`` de la fuente es igualdad sin distinguir mayúsculas, que aquí es
    ``name__iexact``; ``limit=1`` es ``.first()``. Devuelve ``None`` cuando no
    hay nombre o país, donde la fuente devuelve el recordset vacío — el valor
    «nada» de cada ORM.

    El ``sudo()`` que la fuente aplica al usuario público **no se porta**: allá
    el catálogo de ciudades está sujeto a reglas de registro y el usuario
    público no las pasa. Aquí ``res.city`` es catálogo global de instancia
    (``MULTIDB_CONTROL_PLANE_APPS``, ver ``apps.py``) y no lleva regla de fila
    que elevar, así que no hay privilegio que pedir.
    """
    if not name or not country_id:
        return None
    return ResCity.objects.filter(
        name__iexact=name,
        country_id=getattr(country_id, 'pk', country_id),
    ).first()


def _combine_address_fields(new, previous):
    """≙ ``super()._address_fields() + ['city_id']`` — el orden de la fuente.

    ``extend_list`` de ``orm.method_chain`` concatena con el eslabón nuevo
    delante; la fuente pone el suyo **detrás**, y el orden de esta lista se
    consume tal cual al sincronizar la dirección del padre. Por eso el
    combinador es propio y no el genérico.
    """
    return list(previous) + list(new)


def _compute_street_data(self):
    """Descompone ``street`` del contacto en sus tres partes — ≙ ``:32-37``.

    Es el mismo símbolo que :meth:`AddressStructured._compute_street_data`, con
    el receptor de la fuente: allá vive en ``res.partner``, porque ``street`` y
    las tres partes son columnas de la misma fila. Aquí ``street`` es de
    ``base.ResPartner`` y las partes del RELATED, así que este cuerpo es el que
    cruza y el del RELATED el que escribe.

    Sin fila RELATED no hay dónde escribir y devuelve ``None``; crearla es
    decisión de quien tenga el contacto, no de un compute.
    """
    structured = _structured_of(self)
    if structured is None:
        return None
    return structured._compute_street_data(self.street)


def _inverse_street_data(self):
    """Recompone ``street`` desde las tres partes — ≙ ``:24-30``.

    La fuente **asigna** ``partner.street``; aquí también, porque el receptor
    es el contacto y la columna es suya. El armado del texto lo hace el RELATED,
    que es donde viven las partes.
    """
    structured = _structured_of(self)
    if structured is None:
        return None
    self.street = structured._inverse_street_data()
    return self.street


def _get_street_split(self):
    """Las tres partes ya descompuestas — ≙ ``:39-45``.

    **Sobreescribe** el ``_get_street_split`` de ``base.ResPartner``
    (``src/addons/base/models/res_partner.py:2419``), igual que en la fuente:
    allá el método está declarado en ``base/models/res_partner.py:331`` y este
    addon lo redefine en su propio ``res_partner.py:39``. Los dos existen y el
    del addon gana — no es un homónimo accidental.

    La diferencia es de dónde salen las partes: el de ``base`` parte la calle al
    vuelo; éste devuelve las columnas ya guardadas, que es lo que la fuente
    hace. Sin fila RELATED no hay columnas guardadas, así que delega en la
    implementación previa devolviendo ``None`` — el relevo de ``chain_method``.
    """
    structured = _structured_of(self)
    if structured is None:
        return None
    return structured._get_street_split()


def apply_base_address_extended_extensions():
    """Cuelga los cuatro símbolos sobre ``base.ResPartner``.

    La llama ``BaseAddressExtendedConfig.ready()``, no el import del módulo: en
    tiempo de import el registro de modelos aún no está poblado.

    Tres mecanismos distintos, uno por la forma que la fuente usa:

    - ``_address_fields`` **acumula** (``super() + [...]``) → ``chain_method``
      con ``combine``;
    - ``_onchange_country_id`` necesita el ``super()`` **primero** →
      ``wrap_method``;
    - los otros dos son nuevos sobre ``res.partner`` → ``chain_method`` a secas.
    """
    chain_method(ResPartner, '_address_fields', classmethod(_address_fields),
                 combine=_combine_address_fields)
    chain_method(ResPartner, '_onchange_city_id', _onchange_city_id)
    chain_method(ResPartner, '_get_res_city_by_name',
                 classmethod(_get_res_city_by_name))
    wrap_method(ResPartner, '_onchange_country_id', _onchange_country_id)

    # Los tres de la calle: la fuente los declara sobre ``res.partner``, así
    # que su receptor es el contacto. ``_get_street_split`` SOBREESCRIBE al de
    # ``base`` —igual que allá— con el relevo por ``None`` cuando no hay fila
    # RELATED de la que leer.
    chain_method(ResPartner, '_compute_street_data', _compute_street_data)
    chain_method(ResPartner, '_inverse_street_data', _inverse_street_data)
    chain_method(ResPartner, '_get_street_split', _get_street_split)
