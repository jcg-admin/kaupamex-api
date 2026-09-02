"""Ajustes generales del sitio — formulario, no tabla.

Adaptación fiel de ``res.config.settings`` de la referencia: en ``odoo19c:``
y ``odoo18c:`` (medido por símbolo, ``odoo/addons/base/models/res_config.py``)
la clase es ``models.TransientModel`` — **no almacena**. Es el formulario que
compone los ajustes; los valores viven en tres destinos, medidos sobre
``base_setup/models/res_config_settings.py`` de la referencia:

======================================  ==================  ========  ========
Destino                                 Declarado como      odoo19c:  odoo18c:
======================================  ==================  ========  ========
parámetro global clave-valor            ``config_parameter``       2         3
campo de la compañía                    ``related=company_id``     5         4
grupo implícito                         ``implied_group``          1         1
======================================  ==================  ========  ========

Aquí se usan los mismos tres destinos con los análogos vivos del árbol:

- ``config_parameter`` → ``SystemParameter`` (``ir.config_parameter``),
  ámbito **L0** — política de la plataforma.
- campo de la compañía → ``CompanySetting``, ámbito **L1/L3** — configuración
  del tenant. Django no tiene ``related=`` sobre un formulario transitorio;
  el destino se atendería por los hooks que la propia referencia deja
  abiertos (``get_values``/``set_values``, categoría ``other``).
  **Hoy no es alcanzable**: ver "El destino per-company está bloqueado".
- ``implied_group`` → ``ResGroups.apply_group`` — ya soportado por el motor
  portado en ``base/models/res_config.py``; hoy sin campos que lo usen.

**Por qué esto reemplaza a ``SiteSettings``.** Aquella era una fila tipada y
persistente con 13 campos de 10 dominios distintos: 10 razones para cambiar
en una tabla, y una migración de esquema por cada cambio de política. Ver
``analisis-sitesettings-viola-srp-vs-res-config-settings`` (H-API-265) para
la medición completa.

**Clasificación L0 vs L1 (DEC-KX-05).** Infra/ops y plazos de la plataforma
→ L0; lo que un tenant configura para su tienda (identidad, fiscalidad,
umbrales comerciales, contacto) → L1. El criterio no se inventa aquí: es el
que DEC-KX-05 ya fija, aplicado campo por campo.

**El destino per-company está bloqueado — medido, no supuesto.**
``CompanySetting.set_setting`` exige una company resoluble, y
``CompanySetting._resolve_company_id(None)`` devuelve ``None`` en un request
admin: el resolutor subdominio→company (UC-PLT-06) **no existe todavía**, y
el propio docstring de ``get_setting`` lo dice ("mientras el resolutor
subdominio→company no exista"). Escribir ahí hoy sería perder el valor en
silencio — exactamente lo que ``check_silent_oks`` prohíbe.

Por eso **los trece campos usan el destino de parámetro** (``SystemParameter``)
con su clave prefijada por dominio dueño. Esto **ya cumple el objetivo de
SRP**: no hay una tabla con diez razones para cambiar, sino trece claves
independientes — ``account.iva_rate`` cambia sin tocar
``delivery.free_shipping_threshold`` ni migrar esquema. Lo que queda
pendiente es **de qué ámbito** es cada clave, y eso se decide cuando el
resolutor exista: mover una clave de ``SystemParameter`` a ``CompanySetting``
es un cambio de una línea en la declaración, no un refactor.
"""
from decimal import Decimal, InvalidOperation

import fields
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from addons.base.models.ir_model import IrModelData
from addons.base.models.res_company import ResCompany
from addons.base.models.res_config import ResConfigSettings as BaseResConfigSettings
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_lang import ResLang
from addons.base.models.res_users import ResUsers
from orm.environments import get_current_company, sudo
from orm.fields_nonstored import NonStored

#: ≙ ``config_parameter='base_setup.show_effect'`` (``odoo19c: :38``).
SHOW_EFFECT_PARAM = 'base_setup.show_effect'

#: ≙ ``config_parameter='base.profiling_enabled_until'`` (``odoo19c: :46``).
PROFILING_ENABLED_UNTIL_PARAM = 'base.profiling_enabled_until'

#: ≙ ``implied_group='base.group_multi_currency'`` (``odoo19c: :35``).
MULTI_CURRENCY_GROUP = 'base.group_multi_currency'

#: Los dos identificadores externos que ``open_new_user_default_groups``
#: resuelve, verbatim de la fuente (``odoo19c: :59`` y ``:77``).
DEFAULT_USER_GROUP_XMLID = 'base.default_user_group'
DEFAULT_GROUPS_FORM_XMLID = 'base.view_default_groups_form'

#: Clave y conversor por campo. La clave lleva el **prefijo del dominio
#: dueño** — el mismo criterio con el que la referencia nombra sus
#: ``config_parameter`` (``base_setup.show_effect``) — y es lo que da el SRP:
#: cada dominio cambia la suya sin tocar las demás ni migrar esquema.
#:
#: El conversor existe porque la clave-valor no tiene esquema:
#: ``SystemParameter`` guarda cadenas y el contrato publicado promete el tipo
#: del campo (la referencia hace lo mismo con ``convert_to_cache``).
#:
#: La columna de ámbito es la clasificación DEC-KX-05; hoy todas escriben en
#: ``SystemParameter`` porque el destino per-company no es alcanzable (ver el
#: docstring del módulo). Las marcadas **L1** son las que se moverán a
#: ``CompanySetting`` cuando exista el resolutor (UC-PLT-06).
CONFIG_CASTERS = {
    # ámbito L0 — política de la plataforma
    'payment_timeout_minutes': ('payment.timeout_minutes', int),
    'order_timeout_minutes': ('sale.order_timeout_minutes', int),
    # ámbito L1 (pendiente de resolutor) — configuración de la tienda
    'site_name': ('website.site_name', str),
    'iva_rate': ('account.iva_rate', Decimal),
    'max_return_days': ('stock.max_return_days', int),
    'min_stock_threshold': ('stock.min_stock_threshold', int),
    'free_shipping_threshold': ('delivery.free_shipping_threshold', Decimal),
    'support_email': ('crm.support_email', str),
    'phone': ('crm.phone', str),
    'address': ('crm.address', str),
}


def _coerce(raw, caster, default):
    """Convierte el valor crudo de la clave-valor al tipo del formulario.

    Un valor ilegible equivale a "no configurado": el formulario cae al
    default en vez de reventar, porque la clave-valor no tiene esquema que
    garantice el tipo.
    """
    if raw is None or raw == '':
        return default
    try:
        return caster(raw)
    except (TypeError, ValueError, InvalidOperation):
        return default


class ResConfigSettings(BaseResConfigSettings):
    """≙ ``ResConfigSettings`` (``odoo19c: base_setup/models/res_config_settings.py:8-136``).

    Adaptación del addon ``base_setup`` de la referencia
    (``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia
    preservados, DEC-KX-03; mecanismo: **copia + adaptación**).

    Allá la clase es ``_inherit = 'res.config.settings'``: **cuelga sus campos
    del formulario compartido**, no crea uno nuevo. Aquí el análogo del
    ``_inherit`` sobre un modelo abstracto es la herencia nativa —el mismo
    criterio que ``addons/utm/models/ir_http.py`` ya declara—, así que esta
    clase es abstracta y :class:`SiteConfigSettings`, el único formulario
    concreto del árbol, la hereda. Ése es el punto: los campos aterrizan en el
    formulario que la superficie DRF sirve, no en uno paralelo que nadie
    navegaría.

    Los tres destinos de un campo de ajustes los resuelve el motor de
    ``base/models/res_config.py``; aquí sólo se declaran los campos con su
    metadato en :attr:`field_attrs`.

    Divergencias declaradas, símbolo a símbolo
    ==========================================

    - **``company_id``** — la fuente lo declara ``required=True``. Aquí el
      formulario no tiene tabla (``managed = False``), así que ``null`` no
      describe ninguna columna: se declara ``blank=False`` —la validación de
      formulario, que es lo que ``required`` significa allá— y ``null=True``
      porque el árbol arranca **sin ninguna empresa sembrada**
      (``BOOTSTRAP_COMPANY_CODE`` trae ``default=''`` y ``seed()`` es un
      no-op), y un default que no puede resolverse no debe reventar la
      instanciación. El default es ``get_current_company``, que devuelve la PK
      —no el registro— porque el ``__init__`` de Django asigna el defecto al
      ``attname`` de la FK.
    - **``external_report_layout_id`` y ``edit_external_header``** —
      BLOQUEADO por ``res.company.external_report_layout_id``: el campo no
      tiene columna en este árbol y su propio archivo lo declara
      (``src/addons/base/models/res_company.py:82-90``). Sucesor: tarea
      **#257**, que es la que le da columna.
    - **``report_footer``** se declara con :class:`NonStored` en vez de
      ``fields.Html(related=…)``: ``Html`` es la única de las tres textuales
      que **no** lleva el despachador de ``store``
      (``src/orm/fields_textual.py:20-21``), y ``src/orm`` está fuera del
      alcance de este pase. El objeto resultante es **el mismo** que el
      despachador devolvería —un ``related`` sin ``store`` no tiene columna en
      ningún caso—, así que la conducta no diverge: sólo el sitio de la
      declaración. Sucesor: tarea **#454**, dar a ``Html`` su despachador.
    - **Los nombres de la cadena ``related``.** ``company_id.country_id.code``
      de la fuente es aquí ``company_id.country.code``: la FK de la empresa al
      país se llama ``country`` en este árbol (``res_company.py:553``), y la
      cadena se escribe con el nombre que existe.
    - **``group_multi_currency``** se declara verbatim con su
      ``implied_group``. Que hoy no resuelva es del motor, no de este campo:
      ``ResConfigSettings._group_is_implied`` resuelve los grupos **por
      nombre** y la fuente los nombra por ``xml_id``; esa divergencia ya la
      declara ``base/models/res_config.py``.
    - **``_compute_*``** — la fuente recorre ``self`` (un *recordset*) y
      asigna a cada registro; aquí ``self`` **es** un registro y el valor lo
      asigna el descriptor :class:`NonStored` al leerlo, así que el cómputo
      **devuelve** el valor en vez de escribirlo. Es la misma conducta
      observable: leer el campo da el valor calculado.

    Lo que este archivo no cierra
    =============================

    ``external_report_layout_id`` y ``edit_external_header``, ambos con el
    sucesor **#257** declarado arriba.
    """

    _inherit = 'res.config.settings'

    class Meta:
        abstract = True

    # === La empresa sobre la que se configura =============================

    company_id = fields.Many2one(
        ResCompany, on_delete=models.PROTECT, db_column='company_id',
        related_name='+', null=True, blank=False,
        default=get_current_company, verbose_name='Company',
        help_text='Odoo company_id — la empresa que el formulario configura.')

    is_root_company = fields.Boolean(
        store=False, verbose_name='Is Root Company',
        default=lambda record: record._compute_is_root_company())

    # === Los quince módulos opcionales ====================================
    # Prefijo ``module_``: ``classify_fields`` los clasifica como módulo y
    # ``current_values`` refleja si están instalados. El efecto de escritura
    # —instalar en caliente— no existe en este árbol y su ausencia la declara
    # ``base/models/res_config.py``, no este archivo.

    module_base_import = fields.Boolean(
        default=False,
        verbose_name='Allow users to import data from CSV/XLS/XLSX/ODS files')
    module_google_calendar = fields.Boolean(
        default=False,
        verbose_name='Allow the users to synchronize their calendar  with Google Calendar')
    module_microsoft_calendar = fields.Boolean(
        default=False,
        verbose_name='Allow the users to synchronize their calendar with Outlook Calendar')
    module_mail_plugin = fields.Boolean(
        default=False, verbose_name='Allow integration with the mail plugins')
    module_auth_oauth = fields.Boolean(
        default=False,
        verbose_name='Use external authentication providers (OAuth)')
    module_auth_ldap = fields.Boolean(
        default=False, verbose_name='LDAP Authentication')
    module_account_inter_company_rules = fields.Boolean(
        default=False, verbose_name='Manage Inter Company')
    module_voip = fields.Boolean(default=False, verbose_name='Phone')
    module_web_unsplash = fields.Boolean(
        default=False, verbose_name='Unsplash Image Library')
    module_sms = fields.Boolean(default=False, verbose_name='SMS')
    module_partner_autocomplete = fields.Boolean(
        default=False, verbose_name='Partner Autocomplete')
    module_base_geolocalize = fields.Boolean(
        default=False, verbose_name='GeoLocalize')
    module_google_recaptcha = fields.Boolean(
        default=False, verbose_name='reCAPTCHA')
    module_website_cf_turnstile = fields.Boolean(
        default=False, verbose_name='Cloudflare Turnstile')
    module_google_address_autocomplete = fields.Boolean(
        default=False, verbose_name='Google Address Autocomplete')

    # === Los que viajan a la empresa ======================================

    #: ≙ ``report_footer`` (``:33``) — ver la divergencia de ``Html`` arriba.
    report_footer = NonStored(
        'Custom Report Footer', related='company_id.report_footer',
        readonly=False,
        help_text='Footer text displayed at the bottom of all reports.')

    company_name = fields.Char(
        related='company_id.display_name', verbose_name='Company Name')
    company_country_code = fields.Char(
        related='company_id.country.code', readonly=True,
        verbose_name='Company Country Code')
    company_country_group_codes = fields.Json(
        related='company_id.country.country_group_codes')

    # === Grupo implicado y parámetros de sistema ==========================

    group_multi_currency = fields.Boolean(
        default=False, verbose_name='Multi-Currencies',
        help_text='Allows to work in a multi currency environment')
    show_effect = fields.Boolean(default=False, verbose_name='Show Effect')
    profiling_enabled_until = fields.Datetime(
        null=True, blank=True, verbose_name='Profiling enabled until')

    # === Los cuatro contadores del panel ==================================

    company_count = fields.Integer(
        store=False, verbose_name='Number of Companies',
        default=lambda record: record._compute_company_count())
    active_user_count = fields.Integer(
        store=False, verbose_name='Number of Active Users',
        default=lambda record: record._compute_active_user_count())
    language_count = fields.Integer(
        store=False, verbose_name='Number of Languages',
        default=lambda record: record._compute_language_count())
    company_informations = fields.Text(
        store=False,
        default=lambda record: record._compute_company_informations())

    #: El metadato que el motor lee para clasificar los tres campos que no van
    #: por prefijo. ``SiteConfigSettings`` lo **amplía**, no lo sustituye.
    field_attrs = {
        'group_multi_currency': {'implied_group': MULTI_CURRENCY_GROUP},
        'show_effect': {'config_parameter': SHOW_EFFECT_PARAM},
        'profiling_enabled_until': {
            'config_parameter': PROFILING_ENABLED_UNTIL_PARAM},
    }

    # --- Acciones ---------------------------------------------------------

    def open_company(self):
        """≙ ``open_company`` (``odoo19c: :48-56``) — abre la ficha de la empresa.

        La acción sale verbatim de la fuente; su ``res_id`` es el de la
        empresa activa (``self.env.company.id`` allá, ``get_current_company()``
        aquí), no el del campo del formulario — la fuente lee el ambiente
        también en este punto.
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'My Company',
            'view_mode': 'form',
            'res_model': 'res.company',
            'res_id': get_current_company(),
            'target': 'current',
        }

    def open_new_user_default_groups(self):
        """≙ ``open_new_user_default_groups`` (``odoo19c: :58-79``).

        Resuelve el grupo por defecto de los usuarios nuevos y, si no existe,
        lo crea **con su identificador externo** — que es lo que la fuente
        hace en dos pasos (``res.groups.create`` + ``ir.model.data.create``).
        Aquí el segundo paso es :meth:`IrModelData.set_xmlid`, el escritor que
        este árbol ya declara para eso: un ``create`` a mano de la fila no
        siembra la caché de identificadores ni registra el cargado.
        """
        default_group = IrModelData.ref(DEFAULT_USER_GROUP_XMLID,
                                        raise_if_not_found=False)
        if not default_group:
            default_group = ResGroups.objects.create(
                name='Default access for new users')
            IrModelData.set_xmlid(default_group, DEFAULT_USER_GROUP_XMLID,
                                  noupdate=True)
        action = {
            'type': 'ir.actions.act_window',
            'name': 'Edit new user default group',
            'view_mode': 'form',
            'res_model': 'res.groups',
            'res_id': default_group.pk,
            'target': 'new',
        }
        # La fuente fija la vista con ``self.env.ref(...)`` sin salvavidas: ese
        # identificador lo siembra su ``base/views/res_groups_views.xml``, que
        # aquí no tiene contraparte — este árbol no porta las vistas XML.
        # Medido: ``grep -rn "view_default_groups_form" src/ addons/`` → 1 hit,
        # la constante de este archivo. Sin el registro, ``ref`` levantaría y
        # la acción entera sería inalcanzable; con el salvavidas la acción
        # abre el formulario por defecto, que es la degradación mínima.
        # Sucesor: tarea **#458**, la siembra de las vistas de ``base``.
        form_view = IrModelData.ref(DEFAULT_GROUPS_FORM_XMLID,
                                    raise_if_not_found=False)
        if form_view is not None:
            action['views'] = [(form_view.pk, 'form')]
        return action

    @classmethod
    def _prepare_report_view_action(cls, template):
        """≙ ``_prepare_report_view_action`` (``odoo19c: :81-89``).

        La acción que abre la vista cuyo identificador externo es ``template``.
        ``@api.model`` de la fuente ≙ ``classmethod``: no lee el registro.
        """
        template_id = IrModelData.ref(template)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ir.ui.view',
            'view_mode': 'form',
            'res_id': template_id.pk,
        }

    def edit_external_header(self):
        """BLOQUEADO por ``res.company.external_report_layout_id`` — razón: el
        campo no tiene columna en este árbol, y quien lo declara es su propio
        archivo (``src/addons/base/models/res_company.py:82-90``: *"El campo
        sigue sin columna aquí y su desenlace es la tarea #257"*). Sin él no
        hay ``key`` de vista que pasarle a
        :meth:`_prepare_report_view_action`. Sucesor: tarea **#257**.
        """
        raise NotImplementedError(
            'edit_external_header está bloqueado: '
            'res.company.external_report_layout_id no tiene columna en este '
            'árbol (tarea #257).')

    # --- Cómputos ---------------------------------------------------------
    # NOTA de la fuente, verbatim (``:96-97``): *"These fields depend on the
    # context, if we want them to be computed we have to make them depend on a
    # field. This is because we are on a TransientModel."*

    def _compute_company_count(self):
        """≙ ``_compute_company_count`` (``odoo19c: :98-102``)."""
        with sudo():
            return ResCompany.objects.count()

    def _compute_active_user_count(self):
        """≙ ``_compute_active_user_count`` (``odoo19c: :104-108``).

        La fuente filtra ``('share', '=', False)`` en la consulta. Aquí
        ``ResUsers.share`` es una **propiedad** —no una columna: es la negación
        de ``_is_internal()`` (``res_users.py:1842``)—, así que el filtro no
        puede viajar al SQL y se aplica en Python. La población es la misma:
        los usuarios que no son de tipo interno.
        """
        with sudo():
            return sum(1 for user in ResUsers.objects.all() if not user.share)

    def _compute_language_count(self):
        """≙ ``_compute_language_count`` (``odoo19c: :110-114``)."""
        return len(ResLang.get_installed())

    def _compute_company_informations(self):
        """≙ ``_compute_company_informations`` (``odoo19c: :116-131``).

        La concatenación es verbatim de la fuente, con los nombres que este
        árbol declara: ``state_id`` → ``state``, ``country_id`` → ``country``.
        """
        company = self.company_id
        if company is None:
            return ''
        informations = '%s\n' % company.street if company.street else ''
        informations += '%s\n' % company.street2 if company.street2 else ''
        informations += '%s' % company.zip if company.zip else ''
        informations += '\n' if company.zip and not company.city else ''
        informations += ' - ' if company.zip and company.city else ''
        informations += '%s\n' % company.city if company.city else ''
        informations += '%s\n' % company.state.display_name if company.state else ''
        informations += '%s' % company.country.display_name if company.country else ''
        vat_display = (company.country and company.country.vat_label) or 'VAT'
        vat_display = '\n' + vat_display + ': '
        informations += '%s %s' % (vat_display, company.vat) if company.vat else ''
        return informations

    def _compute_is_root_company(self):
        """≙ ``_compute_is_root_company`` (``odoo19c: :133-136``).

        ``parent_id`` de la fuente es aquí el ``attname`` de la FK ``parent``
        de ``res.company``: la misma columna con el nombre que Django le da.
        """
        return not self.company_id or not self.company_id.parent_id

class SiteConfigSettings(ResConfigSettings):
    """``res.config.settings`` del sitio — formulario de ajustes (UC-CFG-03).

    No crea tabla (``managed = False``). Se instancia con los datos del
    request y ``apply_values()`` escribe cada campo en su destino.
    """

    # — L0: política de la plataforma → SystemParameter —
    payment_timeout_minutes = models.PositiveIntegerField(default=30)
    order_timeout_minutes = models.PositiveIntegerField(default=60)

    # — L1: configuración del tenant → CompanySetting —
    #: Sin default de tenant: ``PracticaYoruba`` es el L1 de ejemplo, no el
    #: nombre de la plataforma. Vacío = lo pone cada Company (en la
    #: referencia el nombre sale de ``res.company.name``).
    site_name = models.CharField(max_length=100, blank=True, default='')
    iva_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal('0.16'),
        validators=[MinValueValidator(Decimal('0')),
                    MaxValueValidator(Decimal('1'))],
    )
    max_return_days = models.PositiveIntegerField(default=30)
    min_stock_threshold = models.PositiveIntegerField(default=5)
    free_shipping_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('999.00'),
        validators=[MinValueValidator(Decimal('0'))],
    )
    support_email = models.EmailField(max_length=254, blank=True, default='')
    phone = models.CharField(max_length=30, blank=True, default='')
    address = models.TextField(blank=True, default='')

    #: Derivado de ``CONFIG_CASTERS`` — una sola fuente para la clave, para
    #: que el mapa y el metadato no puedan divergir.
    field_attrs = dict(
        #: Lo que el porte de ``base_setup`` ya declara —el grupo implicado y
        #: los dos parámetros de sistema— **se conserva**: este diccionario
        #: amplía el de la clase padre, no lo sustituye. Sustituirlo dejaría
        #: sin metadato a ``show_effect``, ``profiling_enabled_until`` y
        #: ``group_multi_currency``, y el motor los clasificaría como ``other``
        #: — o sea, el formulario los mostraría y no los guardaría.
        ResConfigSettings.field_attrs,
        **{name: {'config_parameter': key}
           for name, (key, _caster) in CONFIG_CASTERS.items()},
    )

    class Meta:
        # El equivalente Django del ``TransientModel``: la clase existe y se
        # instancia en memoria, pero NO tiene tabla — Django no la crea ni la
        # consulta. Un ``abstract = True`` no serviría: no se puede
        # instanciar, y el formulario necesita instanciarse para aplicar.
        managed = False
        db_table = 'base_setup_siteconfigsettings_unmanaged'
        verbose_name = 'Ajustes generales del sitio'

    @classmethod
    def current_values(cls, fnames=None):
        """El estado actual, con cada valor en el tipo de su campo.

        La clave-valor no tiene esquema: ``SystemParameter`` devuelve el
        parámetro como cadena. La referencia resuelve esto con
        ``convert_to_cache`` (el campo conoce su tipo); aquí se castea con el
        mismo criterio, porque el contrato publicado promete
        ``payment_timeout_minutes`` entero, no ``'45'``.
        """
        values = super().current_values(fnames)
        for name, (_key, caster) in CONFIG_CASTERS.items():
            if name in values:
                default = cls._meta.get_field(name).get_default()
                values[name] = _coerce(values[name], caster, default)
        return values

    def set_values(self):
        """Sin campos de la categoría ``other``: todos son ``config``.

        El hook se conserva porque es el punto de enganche del destino
        per-company: cuando exista el resolutor (UC-PLT-06), las claves de
        ámbito L1 se atenderán aquí contra ``CompanySetting`` en vez de en
        ``SystemParameter``.
        """
        return None
