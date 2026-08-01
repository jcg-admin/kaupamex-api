"""``res.company`` — entidad legal, con jerarquía de sucursales.

Adaptación de ``odoo/addons/base/models/res_company.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 521 líneas).

Colisión con ``company.Company`` — declarada, no resuelta aquí
==============================================================

Este árbol ya tiene ``company.Company``: el **tenant L1** que contrata la
plataforma (DEC-KX-05, ADR-021), con su ``status`` comercial, sus
``CompanySetting`` y el aislamiento de fila L3. ``res.company`` de la
referencia es otra cosa: la **entidad legal** que emite documentos —con su
razón social, su RFC, su moneda funcional y su membrete de reporte— y que
puede tener **sucursales**.

No son el mismo objeto y por eso no se colapsan: un tenant L1 podría operar
más de una entidad legal, y una entidad legal no contrata nada. Se porta el
archivo completo con el nombre de la referencia (``ResCompany``, tabla
``res_company``); reconciliar ambos ejes —o decidir que uno referencia al
otro— es decisión de producto y va en su propio pase, no de rebote desde
``base``.

La delegación al partner, que es la idea estructural del archivo
================================================================

En la referencia una compañía **es un partner** más los datos de compañía:
``name``, ``email``, ``phone``, ``website``, ``vat``, ``company_registry`` y
``logo`` son campos ``related`` a ``partner_id``, no columnas propias. Los de
dirección (``street``, ``street2``, ``zip``, ``city``, ``state_id``,
``country_id``) son ``compute`` **con inverse**: se leen del partner y al
escribirlos se escriben en el partner.

Eso se porta como propiedades con *setter*, que es el equivalente exacto del
par ``compute``/``inverse``: leer delega, escribir propaga. Duplicar las
columnas rompería la invariante de que el partner es la única fuente de la
identidad — la misma razón por la que ``res_users.py`` delega en el partner.

La jerarquía y su ruta materializada
====================================

``parent_path`` es una **ruta materializada** (``'1/4/9/'``): la lista de
ancestros codificada en una columna, para que obtener la cadena completa sea
leer un campo en vez de N consultas. De ahí salen ``parent_ids`` (todos los
ancestros, el propio incluido) y ``root_id`` (el primero). Se porta con su
mantenimiento en ``save()``, que la fuente delega a su ORM.

``_get_company_root_delegated_field_names`` es el mecanismo por el que una
sucursal **hereda de su raíz**: los campos que lista se copian de la raíz y
salen de sólo lectura en el formulario. En la referencia la lista es
``['currency_id']`` — una sucursal no puede tener otra moneda funcional que su
matriz. Se porta como está, incluido el hecho de que sea un método y no una
constante: un addon la extiende añadiendo campos.

Detalles pequeños que un port ingenuo pierde
============================================

- ``_compute_color`` cae a ``root_id.id % 12`` cuando el partner no declara
  color: un color estable derivado del id, no un default fijo. Doce es el
  tamaño de la paleta.
- ``_compute_logo_web`` redimensiona a ``(180, 0)``: **ancho 180, alto libre**.
  El cero no es "sin alto", es "el que salga al preservar la proporción".
- ``uses_default_logo`` compara contra el logotipo por defecto, no contra
  vacío: una compañía que nunca cambió el logo cuenta como "por defecto"
  aunque tenga bytes.
- ``_onchange_country_id`` fija la moneda desde el país. Se porta como método
  explícito porque aquí no hay ``onchange`` del ORM.

Qué NO se porta, con su medición
================================

- **``ZeepOrmCache``** — caché de WSDL para el cliente SOAP ``zeep``, que la
  referencia usa en localizaciones fiscales. Medido:
  ``grep -rn "zeep" src/ | grep -v res_company.py`` → **0**. No hay cliente
  SOAP en este árbol.
- **``install_l10n_modules`` / ``uninstalled_l10n_module_ids``** — instalan
  paquetes de localización en caliente. Es el instalador, cuya ausencia
  ``ir_module.py`` ya declara y justifica.
- **``external_report_layout_id``** (``ir.ui.view``) y ``_get_view`` — capa de
  vistas. ``grep -rn "class IrUiView" src/`` → **0**; es el mismo pendiente
  que ``report_layout.py`` ya declara.
- **``bank_ids``** — ``related`` a ``partner_id.bank_ids``; llega solo cuando
  ``res_partner`` declare el reverso de ``res.bank``.
"""
import logging

import fields
import models

from addons.base.models.report_paperformat import ReportPaperformat
from addons.base.models.res_country import ResCountry, ResCountryState
from addons.base.models.res_currency import ResCurrency
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers
from addons.base.models.timestamped_mixin import TimeStampedModel

_logger = logging.getLogger(__name__)

#: Ancho al que se reduce el logotipo para la cabecera — ``(180, 0)`` de la
#: fuente: ancho fijo, alto el que resulte de preservar la proporción.
LOGO_WEB_WIDTH = 180

#: Tamaño de la paleta del color derivado (``id % 12`` en la fuente).
COLOR_PALETTE_SIZE = 12

#: Tipografías del membrete, verbatim de la referencia.
FONT_CHOICES = [
    ('Lato', 'Lato'),
    ('Roboto', 'Roboto'),
    ('Open_Sans', 'Open Sans'),
    ('Montserrat', 'Montserrat'),
    ('Oswald', 'Oswald'),
    ('Raleway', 'Raleway'),
    ('Tajawal', 'Tajawal'),
    ('Fira_Mono', 'Fira Mono'),
]

LAYOUT_BACKGROUND_CHOICES = [
    ('Blank', 'En blanco'),
    ('Demo logo', 'Logotipo de demostración'),
    ('Custom', 'Personalizado'),
]


class ResCompany(TimeStampedModel):
    """Entidad legal que emite documentos (``res.company``).

    No confundir con ``company.Company``, el tenant L1 que contrata la
    plataforma — ver el docstring del módulo.
    """

    #: Campos que una sucursal hereda de su raíz. Es un método en la fuente
    #: para que un addon lo extienda; aquí, un ``classmethod`` por lo mismo.
    _ROOT_DELEGATED_FIELDS = ('currency',)

    #: Campos de dirección que viven en el partner y se leen a través de él.
    _ADDRESS_FIELDS = (
        'street', 'street2', 'city', 'zip', 'state', 'country',
    )

    partner = fields.Many2one(
        ResPartner, on_delete=models.PROTECT, db_index=True,
        related_name='companies', verbose_name='Partner',
        help_text='Odoo partner_id. La identidad de la compañía vive aquí.',
    )
    active = fields.Boolean(default=True, verbose_name='Activa')
    sequence = fields.Integer(
        default=10, verbose_name='Secuencia',
        help_text='Ordena las compañías en el selector (Odoo sequence).',
    )
    parent = fields.Many2one(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        db_index=True, related_name='child_ids', verbose_name='Compañía matriz',
        help_text='Odoo parent_id, con ondelete restrict.',
    )
    parent_path = fields.Char(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name='Ruta de ancestros',
        help_text="Ruta materializada '1/4/9/' — evita N consultas para "
                  'obtener la cadena de matrices.',
    )
    currency = fields.Many2one(
        ResCurrency, on_delete=models.PROTECT, db_index=True,
        related_name='companies', verbose_name='Moneda',
    )
    user_ids = fields.Many2many(
        ResUsers, blank=True, related_name='company_ids',
        db_table='res_company_users_rel', verbose_name='Usuarios aceptados',
    )

    # — Membrete de los documentos impresos —
    report_header = fields.Html(
        blank=True, default='', verbose_name='Lema de la compañía',
        help_text='Se incluye en la cabecera o el pie del documento impreso, '
                  'según el diseño elegido.',
    )
    report_footer = fields.Html(
        blank=True, default='', verbose_name='Pie de reporte')
    company_details = fields.Html(
        blank=True, default='', verbose_name='Detalles de la compañía')
    paperformat = fields.Many2one(
        ReportPaperformat, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='companies', verbose_name='Formato de papel',
    )
    font = fields.Selection(
        max_length=32, choices=FONT_CHOICES, default='Lato',
        verbose_name='Tipografía')
    primary_color = fields.Char(
        max_length=32, blank=True, default='', verbose_name='Color primario')
    secondary_color = fields.Char(
        max_length=32, blank=True, default='', verbose_name='Color secundario')
    layout_background = fields.Selection(
        max_length=16, choices=LAYOUT_BACKGROUND_CHOICES, default='Blank',
        verbose_name='Fondo del diseño')
    layout_background_image = fields.Image(
        upload_to='company/layout/', null=True, blank=True,
        verbose_name='Imagen de fondo')

    class Meta:
        db_table = 'res_company'
        ordering = ['sequence', 'name', 'id']
        verbose_name = 'Compañía'
        verbose_name_plural = 'Compañías'
        constraints = [
            # ``_name_uniq`` de la fuente: "The company name must be unique!".
            # El nombre vive en el partner, así que la unicidad se declara
            # sobre el partner: una entidad legal por partner.
            models.UniqueConstraint(
                fields=['partner'], name='res_company_partner_uniq'),
        ]

    def __str__(self):
        return self.name

    # === Delegación al partner ===========================================

    @property
    def name(self):
        """``related='partner_id.name'`` — la razón social vive en el partner."""
        return self.partner.name

    @name.setter
    def name(self, value):
        self.partner.name = value

    @property
    def email(self):
        return self.partner.email

    @email.setter
    def email(self, value):
        self.partner.email = value

    @property
    def phone(self):
        return self.partner.phone

    @phone.setter
    def phone(self, value):
        self.partner.phone = value

    @property
    def website(self):
        return getattr(self.partner, 'website', '')

    @property
    def vat(self):
        """``related='partner_id.vat'`` — el identificador fiscal."""
        return getattr(self.partner, 'vat', '')

    @property
    def logo(self):
        """``related='partner_id.image_1920'``."""
        return getattr(self.partner, 'image_1920', None)

    # === Dirección: compute + inverse =====================================

    def _address_get(self, fname):
        return getattr(self.partner, fname, None)

    def _address_set(self, fname, value):
        """El *inverse* de la fuente: escribir en la compañía escribe el partner."""
        setattr(self.partner, fname, value)

    @property
    def street(self):
        return self._address_get('street')

    @street.setter
    def street(self, value):
        self._address_set('street', value)

    @property
    def street2(self):
        return self._address_get('street2')

    @street2.setter
    def street2(self, value):
        self._address_set('street2', value)

    @property
    def zip(self):
        return self._address_get('zip')

    @zip.setter
    def zip(self, value):
        self._address_set('zip', value)

    @property
    def city(self):
        return self._address_get('city')

    @city.setter
    def city(self, value):
        self._address_set('city', value)

    @property
    def state(self):
        return self._address_get('state')

    @state.setter
    def state(self, value):
        self._address_set('state', value)

    @property
    def country(self):
        return self._address_get('country')

    @country.setter
    def country(self, value):
        self._address_set('country', value)

    @property
    def country_code(self):
        """``related='country_id.code'``."""
        country = self.country
        return getattr(country, 'code', '') if country else ''

    # === Jerarquía ========================================================

    def _compute_parent_path(self):
        """Ruta materializada del ancestro, terminada en ``/``."""
        if self.parent_id is None:
            return f'{self.pk}/'
        return f'{self.parent.parent_path}{self.pk}/'

    @property
    def parent_ids(self):
        """Todos los ancestros, el propio incluido — ``_compute_parent_ids``.

        Sale de leer ``parent_path``, no de recorrer la cadena: ése es el
        propósito de la ruta materializada.
        """
        model = type(self)
        if not self.parent_path:
            return model.objects.filter(pk=self.pk)
        ids = [int(i) for i in self.parent_path.split('/') if i]
        return model.objects.filter(pk__in=ids)

    @property
    def root_id(self):
        """La raíz de la jerarquía — el primero de ``parent_ids``."""
        return self.parent_ids.order_by('pk').first() or self

    @classmethod
    def get_company_root_delegated_field_names(cls):
        """Campos que una sucursal copia de su raíz.

        La fuente devuelve ``['currency_id']``: una sucursal no puede tener
        otra moneda funcional que su matriz. Es un método —no una constante—
        para que un addon lo extienda.
        """
        return list(cls._ROOT_DELEGATED_FIELDS)

    def apply_root_delegation(self):
        """Copia desde la raíz los campos delegados, como hace la fuente."""
        root = self.root_id
        if root.pk == self.pk:
            return
        for fname in self.get_company_root_delegated_field_names():
            setattr(self, fname, getattr(root, fname))

    # === Derivados de presentación ========================================

    @property
    def color(self):
        """Color del partner de la raíz, o uno estable derivado de su id.

        El respaldo ``id % 12`` de la fuente da un color **estable** por
        compañía en vez de un default fijo; 12 es el tamaño de la paleta.
        """
        root = self.root_id
        declared = getattr(root.partner, 'color', None)
        if declared:
            return declared
        return (root.pk or 0) % COLOR_PALETTE_SIZE

    @property
    def logo_web(self):
        """Logotipo reducido a 180 px de **ancho**, alto proporcional.

        El ``(180, 0)`` de la fuente no significa "sin alto": significa el que
        resulte de preservar la proporción.
        """
        return getattr(self.partner, 'image_256', None) or self.logo

    def uses_default_logo(self, default_logo=None):
        """¿La compañía sigue con el logotipo por defecto?

        Compara contra el logotipo por defecto, no contra vacío: una compañía
        que nunca lo cambió cuenta como "por defecto" aunque tenga bytes.
        """
        logo = self.logo
        return not logo or (default_logo is not None and logo == default_logo)

    # === Reglas de coherencia =============================================

    def onchange_state(self):
        """Fijar el estado fija el país — ``_onchange_state``."""
        state = self.state
        if state is not None and getattr(state, 'country_id', None):
            self.country = state.country

    def onchange_country(self):
        """Fijar el país fija la moneda — ``_onchange_country_id``."""
        country = self.country
        if country is not None and getattr(country, 'currency_id', None):
            self.currency = country.currency

    def save(self, *args, **kwargs):
        """Mantiene la ruta materializada, que allá mantiene el ORM."""
        super().save(*args, **kwargs)
        path = self._compute_parent_path()
        if path != self.parent_path:
            self.parent_path = path
            super().save(update_fields=['parent_path'])
