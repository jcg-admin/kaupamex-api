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
import datetime
import re
from base64 import b64encode
from collections import defaultdict
from random import randint
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import fields
import models
from orm.domains import Domain
from django.apps import apps
from django.conf import settings
from django.utils.translation import get_language

from addons.base.models.avatar_mixin import AvatarMixin
from addons.base.models.res_country import (ADDRESS_FORMAT_KEYS,
                                            DEFAULT_ADDRESS_FORMAT)
from addons.base.models.res_lang import ResLang
from exceptions import RedirectWarning, ValidationError
from django.db import DEFAULT_DB_ALIAS
from orm.environments import (company_scope, context_scope, execute_query,
                              get_context, get_current_company,
                              get_current_user, sudo)
from orm.utils import SUPERUSER_ID
from addons.base.models.timestamped_mixin import TimeStampedModel
from tools.mail import (email_normalize_all, formataddr,
                        parse_contact_from_email)
from tools.misc import OrderedSet, street_split
from tools.sql import SQL
from tools.translate import _


# put POSIX 'Etc/*' entries at the end to avoid confusing users - see bug 1086728
#
# El comentario va verbatim de ``odoo19c: odoo/addons/base/models/res_partner.py:39``:
# es el contrato del orden, no una nota de color. La lista y su invocable son
# los dos simbolos que la fuente declara (``:40-42``), y ``_tz_get`` NO es
# adorno — medido sobre ``odoo19c``, lo consumen 14 archivos / 30 referencias
# (``lunch``, ``hr_holidays``, ``event``, ``resource``, ``mail``, ``website``,
# ``calendar``, mas ``base``): es API compartida del arbol.
#
# DIVERGENCIA DE STACK, declarada: la fuente puebla la lista con
# ``pytz.all_timezones`` y ``pytz`` NO esta instalado aqui (medido:
# ``ModuleNotFoundError``). La poblacion sale de
# ``zoneinfo.available_timezones()`` de la biblioteca estandar — 498 zonas en
# este contenedor, 35 de ellas ``Etc/*``. Es la misma divergencia que
# ``_compute_tz_offset`` ya declaraba para leer el desfase; aqui se aplica a
# escribirlo, que es la mitad que faltaba.
#
# ``localtime`` se descarta, y NO es capricho. ``available_timezones()``
# recorre ``TZPATH`` y admite todo archivo que empiece con la firma ``TZif``;
# su propio codigo retira ``posixrules``, ``right/`` y ``posix/`` — y NO
# ``localtime``, que en Debian es el enlace de la maquina
# (``/usr/share/zoneinfo/localtime -> /etc/localtime -> Etc/UTC``, medido).
# ``pytz.all_timezones`` no lo tiene: es una lista curada, no un barrido del
# disco. Ofrecerlo en la Selection publicaria «la zona de este servidor», que
# cambia de significado entre maquinas.
_LOCAL_LINK = 'localtime'

# La CLAVE del orden diverge de la fuente, y el motivo es medible. La fuente
# ordena con ``tz if not tz.startswith('Etc/') else '_'``: todas las ``Etc/*``
# colapsan a la misma clave, asi que su posicion RELATIVA la decide el orden de
# entrada. Alli eso es determinista —``pytz.all_timezones`` es una LISTA con
# orden fijo—; aqui ``available_timezones()`` devuelve un ``set``, cuyo
# recorrido cambia entre procesos por la aleatorizacion del hash de cadenas.
#
# Medido: con la clave literal de la fuente, dos ``makemigrations`` seguidos
# producen bloques ``Etc/*`` distintos (``Etc/GMT-4, Etc/GMT+6, Etc/GMT+1`` vs
# ``Etc/GMT-12, Etc/GMT+3, Etc/GMT+5``), asi que ``makemigrations --check``
# JAMAS quedaria limpio y CI pediria una migracion nueva en cada corrida.
#
# La clave de tupla conserva el contrato observable —todas las ``Etc/*`` al
# final, que es lo que el comentario de la fuente fija— y ademas las ordena
# entre si. Es un superconjunto de la garantia, no una divergencia de conducta.
_tzs = [(tz, tz) for tz in sorted(available_timezones() - {_LOCAL_LINK},
                                  key=lambda tz: (tz.startswith('Etc/'), tz))]


def _tz_get(self):
    """La poblacion de zonas — ≙ ``_tz_get`` (``odoo19c: res_partner.py:41-42``).

    Recibe ``self`` y lo ignora, como la fuente: alli es un metodo suelto que
    el ``Selection`` invoca con el recordset. Se conserva la firma porque los
    14 archivos que lo importan lo llaman asi.
    """
    return _tzs


def _default_tz():
    """El ``default`` del campo ``tz`` — ≙ ``lambda self: self.env.context.get('tz')``.

    Funcion con nombre y NO un ``lambda``: el serializador de migraciones de
    Django rehusa con ``ValueError: Cannot serialize function: lambda``
    (``django/db/migrations/serializer.py:192``), asi que un invocable anonimo
    aqui deja el modelo sin migracion posible. Medido al intentarlo.

    Cae a ``''`` y no a ``None`` porque la columna es NOT NULL en este arbol.
    """
    return get_context().get('tz') or ''


class ResPartner(AvatarMixin, models.OriginMixin, models.DefaultGetMixin,
                 models.CopyMixin, TimeStampedModel):
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

    Cobertura del porte — los símbolos que NO llevan contraparte por nombre
    =======================================================================

    Medido con el gate de porte sobre ``odoo19c: res_partner.py``: **89
    símbolos en la referencia**. Los que el gate reporta ausentes se reparten
    en cuatro desenlaces, y ninguno queda en silencio:

    **Portados con otro nombre — divergencia de stack.**

    - ``create`` (``:926``) y ``write`` (``:856``) → :meth:`save`. Django
      unifica los dos caminos en un solo enganche y el propio docstring de
      ``save`` los cita; ``_state.adding`` distingue el alta de la escritura.
    - los cinco ``_compute_avatar_<n>`` → las cinco ``property`` de
      ``AvatarMixin`` (``avatar_mixin.py``), que es donde la referencia los
      declara. Aquí no llevan ``store``, igual que allá.

    **Desbloqueado en la tarea #111.** ``_check_barcode_unicity`` (``:647``)
    estuvo detenido por ``barcode``, que la fuente declara
    ``company_dependent=True``. El mecanismo se construyó
    (``orm/fields_company_dependent.py``) y hoy el campo y su guarda están
    portados con su firma.

    **Detenidos, cada uno por un símbolo que se nombra.**

    - ``_check_partner_company`` (``:551``) y ``_onchange_company_id``
      (``:596``): BLOQUEADO por ``company_id`` — el campo no existe en este
      puerto, así que no hay contra qué comparar. Tarea **#110**.
    - ``copy_data`` (``:565``): **portado** (tarea #114). El ORM ya tiene su
      ``copy``/``copy_data`` (``models.CopyMixin``), así que el sufijo
      ``(copy)`` que este override añade tiene por fin quién lo dispare.
    - ``default_get`` (``:201``): **portado en su mitad viable** (tarea #113).
      El saneo del ``type`` que se cuela del contexto está escrito; la herencia
      del padre sigue BLOQUEADO por ``company_id`` — el campo no existe en
      este puerto. Tarea **#110**. La base —``models.DefaultGetMixin``— ya
      está portada, y con ella la guarda del correo de :meth:`name_create` es
      observable.

    **Divergencia de mecanismo, ya declarada en su sitio.**

    - ``_get_view``, ``_get_view_cache_key`` y ``_view_get_address`` — mutan
      el arch XML de una vista Odoo con XPath. Razón medida en
      :class:`FormatAddressMixin` y :class:`FormatVatLabelMixin`, más abajo:
      el **dato** está (``vat_label``, ``address_format``) y el árbol XML no.
    - ``get_import_templates`` y ``_check_import_consistency`` — el asistente
      de importación CSV, con su razón medida junto a
      ``_extract_fields_from_address``. Desenlace: decisión del ejecutor,
      tarea **#103**.

    Los tres enganches que Enterprise usa sobre este modelo
    ========================================================

    Medido sobre ``19.x/odoo19-enterprise-main``, clases con
    ``_inherit = 'res.partner'``, cruzado con lo que ``odoo19c:
    res_partner.py`` declara:

    - ``_compute_application_statistics_hook`` — **portado** abajo, con su
      compute y su propiedad. Es el único de los tres que era un hueco: un
      campo cuya base devuelve vacío y que existe **para** que otros lo
      llenen.
    - ``_default_category`` (``odoo19c: :197-198``) — **portado**, abajo.
      Estuvo declarado como divergencia de mecanismo con esta razón: *"Aquí
      no hay ``env``… portarlo con la firma de la fuente exigiría inventar la
      bolsa de contexto"*. La bolsa **existe** desde que se portó el bloque de
      ``display_name`` (``orm.environments.get_context``), y este mismo
      archivo la consulta con cinco claves en ``_compute_display_name``. La
      divergencia se retiró en el mismo pase que lo destapó — estado heredado
      incorrecto, Clausula 2 del principio rector.
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

    def copy_data(self, default=None, seen=None):
        """≙ ``copy_data`` (``odoo19c: res_partner.py:564-569``).

        Añade el sufijo ``(copy)`` al nombre, **salvo** que el llamador traiga
        uno propio. El ``if default.get('name')`` de la fuente es esa guarda, y
        no es cosmética: sin ella un duplicado con nombre dado saldría como
        ``"Nombre nuevo (copy)"``.
        """
        default = dict(default or {})
        values = super().copy_data(default, seen=seen)
        if values is None or default.get('name'):
            return values
        return dict(values, name=_('%s (copy)') % self.name)

    @classmethod
    def default_get(cls, fields):
        """≙ ``default_get`` (``odoo19c: res_partner.py:201-211``).

        Docstring de la fuente, verbatim: *"Add the company of the parent as
        default if we are creating a child partner."*

        La fuente hace **dos** cosas, y aquí sólo una está detenida:

        1. Heredar el ``company_id`` del padre. **BLOQUEADO por ``company_id``**
           — el campo no existe en este puerto, así que no hay valor que
           heredar ni columna donde ponerlo. Tarea **#110**; cuando el campo
           llegue, esta mitad se escribe y su caso con él.
        2. Sanear un ``type`` inválido que se cuele del contexto de una acción
           de menú. Su comentario lo dice: *"protection for ``default_type``
           values leaking from menu action context"*. Esta mitad **no** está
           bloqueada: el vocabulario está portado (:attr:`TYPES`), así que el
           saneo se hace contra las mismas cuatro opciones.

        Por qué el saneo hace falta aunque el campo tenga ``choices``: el
        contexto entra por el paso 1 de la base, **antes** de que ninguna
        validación mire el valor. Sin este filtro, un ``default_type`` basura
        llega a ``create`` y revienta en el ``full_clean``, lejos de su causa
        — o peor, se escribe si el alta no valida.
        """
        values = super().default_get(fields)
        if 'type' in fields and values.get('type'):
            if values['type'] not in {code for code, _label in cls.TYPES}:
                values['type'] = None
        return values

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
    complete_name = fields.Char(
        max_length=512, blank=True, default='', db_index=True,
        help_text=(
            'Nombre para listas: «Empresa, Persona» (Odoo complete_name). '
            'Es store=True en la fuente — se escribe al guardar, no se '
            'calcula al leer.'
        ),
    )
    company_registry = fields.Char(
        max_length=64, blank=True, default='', db_index=True,
        help_text=(
            'Identificador de la empresa en su registro mercantil '
            '(Odoo company_registry). store=True y readonly=False: se '
            'captura a mano y las localizaciones lo pueden derivar.'
        ),
    )
    partner_share = fields.Boolean(
        default=True, db_index=True,
        help_text=(
            'Cliente sin acceso, o usuario compartido (Odoo partner_share). '
            'Es store=True en la fuente — se escribe al guardar. False solo '
            'cuando algun usuario suyo es interno.'
        ),
    )
    company_name = fields.Char(
        max_length=150, blank=True, default='',
        help_text='Razón social escrita a mano cuando el contacto NO cuelga '
                  'de una empresa (Odoo ``company_name``, '
                  '``odoo19c: res_partner.py:308``).',
    )
    # ``barcode`` — el primer campo DEPENDIENTE DE EMPRESA del arbol.
    #
    # La fuente lo declara ``company_dependent=True``
    # (``odoo19c: res_partner.py:309``), y eso no es un adorno: el mismo
    # contacto lleva un codigo de barras distinto en cada empresa del grupo, y
    # ninguna ve el de la otra. Con una columna escalar eso no se expresa — o
    # se duplica el contacto por empresa, o las empresas se pisan el valor.
    #
    # El mecanismo se construyo en ``orm/fields_company_dependent.py`` (tarea
    # **#111**): la columna es ``jsonb`` con la forma ``{empresa: valor}`` y el
    # descriptor devuelve el valor de la empresa activa al leer. El sitio de
    # declaracion queda identico al de la fuente, incluido su ``help``.
    #
    # ``copy=False`` de la fuente NO se transcribe: el propio campo lo fija
    # —el valor es de la empresa, no del registro— igual que allá lo fija
    # ``_setup_attrs`` (``odoo19c: odoo/orm/fields.py:473``).
    barcode     = fields.Char(
        company_dependent=True,
        help_text='Use a barcode to identify this contact.',
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
    # ≙ ``tz = fields.Selection(_tzs, string='Timezone', ...)``
    # (``odoo19c: res_partner.py:223``). El ``help`` va verbatim de la fuente.
    #
    # ``default`` — la fuente usa ``lambda self: self.env.context.get('tz')``;
    # aqui el mecanismo equivalente ya existe (``orm.environments.get_context``),
    # asi que se porta en vez de dejarlo en blanco. Cae a ``''`` y no a ``None``
    # porque la columna es NOT NULL en este arbol.
    #
    # LO QUE ESTO NO CIERRA: ``choices`` en Django es **validacion, no DDL** —
    # el mismo hecho que desbloqueo la tarea #118. PostgreSQL no recibe ningun
    # ``CHECK``, asi que un ``objects.create(tz='No/Existe')`` sigue escribiendo
    # la fila y solo ``full_clean()`` la rechaza. Por eso el respaldo a GMT de
    # ``_compute_tz_offset`` se queda: cubre el dato viejo y la escritura que
    # esquiva la validacion.
    tz          = fields.Char(
        max_length=64, blank=True, choices=_tzs,
        default=_default_tz,
        verbose_name='Timezone',
        help_text='When printing documents and exporting/importing data, time '
                  'values are computed according to this timezone. If the '
                  'timezone is not set, UTC (Coordinated Universal Time) is '
                  'used. Anywhere else, time values are computed according to '
                  'the time offset of your web client (Odoo tz).',
    )
    comment     = fields.Text(blank=True, default='')

    # Aviso de la fuente, verbatim (``odoo19c: res_partner.py:230``):
    # *"Warning: user_id is a Salesperson, not the inverse of partner_id in
    # res.users. For the latter, see user_ids and main_user_id."* Aqui son
    # ``user`` (el vendedor, esta columna) y ``users``/``main_user`` (el
    # inverso). Confundirlos hace que asignar un comercial cambie de quien es
    # la cuenta.
    #
    # ``related_name='+'`` es divergencia de STACK declarada: la fuente NO
    # declara inverso para este campo, y Django fabricaria uno que alla no
    # existe. El ``+`` es lo mas cercano a no tenerlo.
    user        = fields.Many2one(
        'base.ResUsers', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
        help_text='Vendedor: el usuario interno a cargo de este contacto '
                  '(Odoo user_id). store=True con compute y readonly=False: '
                  'se hereda del padre al crear y se reescribe a mano.')

    # --- Etiquetas calculadas, SIN columna --------------------------------
    #
    # Diez de los trece campos de este bloque NO son columnas: la fuente los
    # declara ``compute=`` sin ``store=True`` — existen para leerse, no para
    # consultarse. Aqui eso es ``fields.NonStored``
    # (``src/orm/fields_nonstored.py``), el mecanismo que este arbol ya
    # construyo para ``store=False``.
    #
    # Los TRES que si llevan columna estan arriba con los demas campos:
    # ``complete_name`` (``odoo19c: res_partner.py:214``), ``company_registry``
    # (``:241``) y ``partner_share`` (``:295``). Medido sobre las trece
    # declaraciones de la fuente, no estimado.
    #
    # El ``default`` es un invocable que recibe la instancia: el descriptor lo
    # llama al leer. La fuente ASIGNA dentro del compute
    # (``partner.tz_offset = ...``); aqui el metodo DEVUELVE y el descriptor
    # guarda. Divergencia de mecanismo, misma lectura en el sitio de consumo.
    active_lang_count = fields.NonStored(
        default=lambda partner: partner._compute_active_lang_count(),
        help_text='Cuantos idiomas activos hay (Odoo active_lang_count).')
    tz_offset = fields.NonStored(
        default=lambda partner: partner._compute_tz_offset(),
        help_text='Desfase de la zona horaria, en la forma +HHMM '
                  '(Odoo tz_offset).')
    vat_label = fields.NonStored(
        default=lambda partner: partner._compute_vat_label(),
        help_text='Como se llama el identificador fiscal en el pais de la '
                  'empresa activa (Odoo vat_label).')
    company_registry_label = fields.NonStored(
        default=lambda partner: partner._compute_company_registry_label(),
        help_text='Como se llama el registro mercantil en su pais '
                  '(Odoo company_registry_label).')
    company_registry_placeholder = fields.NonStored(
        default=lambda partner: partner._compute_company_registry_placeholder(),
        help_text='Texto guia del campo de registro mercantil '
                  '(Odoo company_registry_placeholder).')
    type_address_label = fields.NonStored(
        default=lambda partner: partner._compute_type_address_label(),
        help_text='Como se llama esta direccion (Odoo type_address_label).')
    email_formatted = fields.NonStored(
        default=lambda partner: partner._compute_email_formatted(),
        help_text='Lo que va en la cabecera To: de un correo '
                  '(Odoo email_formatted).')
    company_type = fields.NonStored(
        default=lambda partner: partner._compute_company_type(),
        help_text='Interfaz de is_company: "company" o "person" '
                  '(Odoo company_type). NO usar en logica de negocio — la '
                  'fuente lo dice en un comentario propio (``:281``).')
    is_public = fields.NonStored(
        default=lambda partner: partner._compute_is_public(),
        help_text='True si algun usuario suyo es el visitante anonimo '
                  '(Odoo is_public). compute_sudo en la fuente: la respuesta '
                  'no depende de quien pregunte.')
    self = fields.NonStored(
        default=lambda partner: partner._compute_get_ids(),
        help_text='Alias del propio registro (Odoo self, un Many2one a '
                  'res.partner con compute _compute_get_ids). Existe para '
                  'que una vista se refiera al partner actual con el mismo '
                  'vocabulario con que referiria a otro.')
    same_vat_partner_id = fields.NonStored(
        default=lambda partner: partner._compute_same_vat_partner_id(),
        help_text='Otro partner con el mismo identificador fiscal '
                  '(Odoo same_vat_partner_id). BLOQUEADO por ``EU_EXTRA_VAT_CODES`` — '
                  'falta la tabla de codigos de IVA; ver tarea #105.')
    same_company_registry_partner_id = fields.NonStored(
        default=lambda partner: partner._compute_same_company_registry_partner_id(),
        help_text='Otro partner con el mismo registro mercantil '
                  '(Odoo same_company_registry_partner_id). '
                  'BLOQUEADO por ``partner.company_id`` — ver tarea #105.')
    main_user = fields.NonStored(
        default=lambda partner: partner._compute_main_user_id(),
        help_text='De las cuentas que apuntan a este partner, la mas '
                  'apropiada (Odoo main_user_id). NO es el vendedor: ese es '
                  '``user``, y la fuente avisa de la confusion en un '
                  'comentario propio (``:230``).')

    class Meta:
        db_table            = 'res_partner'
        # Derivado de ``_order = 'complete_name ASC, id DESC'``, ahora
        # VERBATIM: ``complete_name`` es una columna real desde que se porto
        # su bloque, asi que ya no hace falta sustituir el primer tramo por
        # ``name``. El comentario anterior decia que era «un compute que este
        # puerto no trae» — cierto al escribirlo, falso desde este commit.
        ordering            = ['complete_name', '-id']
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

        **Su hermano multilínea ya existe:** :meth:`_display_address` es el
        porte fiel —rellena la plantilla del país— y desde 2026-08-27 está en
        este archivo. Esta property NO delega en él y la divergencia se
        sostiene con su consumidor medido: los cinco sitios que la leen
        (``sale/report/report_catalog.py:66,83`` y
        ``sale/data/report_templates.py:36,43``) imprimen **una** línea en un
        PDF, y ``_display_address`` devuelve cuatro con saltos. Quien necesite
        el formato del país llama al otro; quien necesite la línea, a ésta.

        El campo publico es ``contact_address``; el computo privado es
        :meth:`_compute_contact_address`, que es donde se engancha quien
        quiera otra forma de linea.

        ≙ el campo ``contact_address``
        (``odoo19c: base/models/res_partner.py:506``).
        """
        return self._compute_contact_address()

    def _compute_contact_address(self):
        """≙ ``_compute_contact_address`` (``odoo19c: res_partner.py:506``).

        DIVERGENCIA DE CONTENIDO declarada, no de forma: la fuente devuelve
        ``partner._display_address()`` —la plantilla del pais, con saltos de
        linea— y aqui se unen con coma las partes presentes.

        La razon esta medida y sigue viva: los cinco consumidores
        (``sale/report/report_catalog.py:66,83`` y
        ``sale/data/report_templates.py:36,43``) imprimen UNA linea en un PDF,
        y ``_display_address`` devuelve cuatro. El hermano fiel existe desde
        2026-08-27 y esta en este archivo: quien necesite el formato del pais
        llama a :meth:`_display_address`; quien necesite la linea, a este.
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

    # ------------------------------------------------------------------
    # Sincronización en la jerarquía — ``odoo19c: res_partner.py:653-843``.
    #
    # **Por qué no es un campo relacionado.** Una dirección es un partner
    # hijo, y para que la de facturación lleve la calle de su empresa la
    # fuente sincroniza **valores** en las tres direcciones —del padre al
    # hijo, del hijo al padre y del padre a los nietos— en vez de declarar un
    # ``related``. La razón es que el hijo debe poder **divergir**: una bodega
    # tiene su propia calle y no la pierde cuando alguien edita la empresa.
    # Un campo relacionado no admite esa excepción; un sincronizador sí,
    # porque decide caso por caso cuándo copiar.
    #
    # **Las dos fronteras, que es lo que un porte ingenuo se salta:** la
    # dirección baja sólo a los hijos de tipo contacto (una de entrega es
    # distinta a propósito), y los campos comerciales no cruzan otra empresa
    # (una filial tiene su propio RFC).
    #
    # Divergencias de mecanismo, todas del mismo origen —aquí ``self`` es una
    # fila y el ORM es Django—:
    #
    # - ``super().write(vals)`` de la fuente evita el ``write`` sobrecargado
    #   para no recursar. El equivalente exacto es ``QuerySet.update()``, que
    #   **no** llama a ``save()`` ni dispara señales; además se asignan los
    #   atributos en memoria, que es lo que allá hace la caché del registro.
    # - ``self._fields[fname]`` es ``self._meta.get_field(fname)``.
    # - ``_convert_to_write`` no tiene análogo: el valor que se asigna a una
    #   FK en Django **es** el objeto, así que el diccionario se arma con
    #   ``getattr`` directo.
    # - ``child_ids`` / ``parent_id`` / ``commercial_partner_id`` son aquí
    #   ``children`` / ``parent`` / ``commercial_partner``.
    # ------------------------------------------------------------------
    def _convert_fields_to_values(self, field_names):
        """≙ ``_convert_fields_to_values`` (``odoo19c: res_partner.py:653-657``).

        Docstring de la fuente, verbatim: *"Returns dict of write() values for
        synchronizing ``field_names``"*.

        La guarda contra el ``one2many`` se porta con su motivo intacto:
        sincronizar una relación inversa copiaría la lista de hijos del padre
        al hijo, que es un ciclo y no una dirección. Aquí un ``one2many`` es
        un ``ManyToOneRel`` —el reverso de una FK— o un ``ManyToManyField``.
        """
        for fname in field_names:
            field = self._meta.get_field(fname)
            if isinstance(field, (models.ManyToOneRel, models.ManyToManyRel,
                                  models.ManyToManyField)):
                raise AssertionError(
                    'Los campos one2many no se pueden sincronizar como parte '
                    'de `commercial_fields` o `address fields`')
        return {fname: getattr(self, fname) for fname in field_names}

    def _get_address_values(self):
        """≙ ``_get_address_values`` (``odoo19c: res_partner.py:669-675``).

        Docstring de la fuente, verbatim: *"Get address values from record if
        at least one value is set. Otherwise it is considered empty and
        nothing is returned."*

        Devolver ``{}`` y no un diccionario de vacíos es la diferencia entre
        «este partner no tiene dirección» y «su dirección es la cadena vacía»:
        lo segundo, propagado al padre, **borraría** la del padre.
        """
        address_fields = self._address_fields()
        if any(getattr(self, key) for key in address_fields):
            return self._convert_fields_to_values(address_fields)
        return {}

    def _update_address(self, vals):
        """≙ ``_update_address`` (``odoo19c: res_partner.py:677-683``).

        Docstring de la fuente, verbatim: *"Filter values from vals that are
        liked to address definition, and update recordset using super().write
        to avoid loops and side effects due to synchronization of address
        fields through partner hierarchy."*

        El ``super().write`` es la mitad importante: escribe **saltándose** el
        ``write`` sobrecargado, que volvería a sincronizar. Aquí ese salto lo
        da ``QuerySet.update()``, que no invoca ``save()`` ni emite señales.
        Los atributos se asignan además en memoria porque allá el registro
        queda actualizado en caché tras el ``write``.
        """
        addr_vals = {key: vals[key] for key in self._address_fields()
                     if key in vals}
        if not addr_vals:
            return
        type(self).objects.filter(pk=self.pk).update(**addr_vals)
        for key, value in addr_vals.items():
            setattr(self, key, value)

    def _get_commercial_values(self):
        """≙ ``_get_commercial_values`` (``odoo19c: res_partner.py:702-709``).

        Docstring de la fuente, verbatim: *"Get commercial values from record.
        Return only set values, as they are considered individually, and only
        set values should be taken into account."*
        """
        set_commercial_fields = [fname for fname in self._commercial_fields()
                                 if getattr(self, fname)]
        if set_commercial_fields:
            return self._convert_fields_to_values(set_commercial_fields)
        return {}

    def _get_synced_commercial_values(self):
        """≙ ``_get_synced_commercial_values`` (``odoo19c: res_partner.py:711-718``).

        Docstring de la fuente, verbatim (con su errata *"from ercord"*):
        *"Get synchronized commercial values from ercord. Return only set
        values as for other commercial values."*
        """
        set_synced_fields = [fname for fname in self._synced_commercial_fields()
                             if getattr(self, fname)]
        if set_synced_fields:
            return self._convert_fields_to_values(set_synced_fields)
        return {}

    @classmethod
    def _company_dependent_commercial_fields(cls):
        """≙ ``_company_dependent_commercial_fields`` (``odoo19c: :720-724``).

        El filtro de la fuente, verbatim: los campos comerciales que además son
        dependientes de empresa. Su ``self._fields[fname].company_dependent``
        se lee aquí del propio campo de Django — el atributo existe desde que
        se construyó el mecanismo (``orm/fields_company_dependent.py``, tarea
        **#111**) y ``CompanyDependent`` lo declara ``True`` como la fuente
        (``odoo19c: odoo/orm/fields.py:291``).

        > Hasta ``#111`` este método devolvía la lista vacía con una
        > divergencia declarada — *"el atributo no existe: 0 apariciones de
        > ``company_dependent`` en ``src/orm/``"*—. La divergencia se retira
        > con el mecanismo, no se actualiza: era estado heredado correcto en su
        > momento y falso hoy (Clausula 2 del principio rector).

        Devuelve vacío **por dato, no por construcción**: hoy ningún campo de
        :meth:`_commercial_fields` es dependiente de empresa. El día que uno lo
        sea, entra solo.
        """
        fields_by_name = {f.name: f for f in cls._meta.get_fields()}
        return [
            fname for fname in cls._commercial_fields()
            if getattr(fields_by_name.get(fname), 'company_dependent', False)
        ]

    def _commercial_sync_from_company(self):
        """≙ ``_commercial_sync_from_company`` (``odoo19c: :726-735``).

        Docstring de la fuente, verbatim: *"Handle sync of commercial fields
        when a new parent commercial entity is set, as if they were related
        fields"*.

        El ``!= self`` es el corte: una entidad comercial no hereda de sí
        misma. Sin él, una empresa se sincronizaría consigo y bajaría sus
        propios valores a los descendientes en cada escritura.
        """
        commercial_partner = self.commercial_partner
        if commercial_partner.pk == self.pk:
            return
        sync_vals = commercial_partner._get_commercial_values()
        if sync_vals:
            type(self).objects.filter(pk=self.pk).update(**sync_vals)
            for key, value in sync_vals.items():
                setattr(self, key, value)
            self._commercial_sync_to_descendants()
        self._company_dependent_commercial_sync()

    def _company_dependent_commercial_sync(self):
        """≙ ``_company_dependent_commercial_sync`` (``odoo19c: :737-749``).

        Docstring de la fuente, verbatim: *"Propagate sync of company dependant
        commercial fields to other commpanies."* (la errata *"commpanies"* es
        de la fuente).

        Qué hace, y por qué hace falta: ``_commercial_sync_from_company`` baja
        los valores comerciales **de la empresa activa**. Un campo dependiente
        de empresa tiene un valor por cada una, así que ese único paso deja a
        las demás sin sincronizar. Este método recorre el resto y baja el valor
        que a cada una le corresponde.

        > Hasta la tarea **#111** este cuerpo levantaba ``NotImplementedError``
        > tras la guarda temprana, porque el mecanismo de campo por empresa no
        > existía. Hoy existe y el recorrido se porta entero: la guarda sigue
        > siendo la de la fuente, y lo que había debajo deja de ser una excusa.

        Las dos divergencias de mecanismo, ambas de nombre: la fuente cambia de
        empresa con ``with_company`` —que devuelve otro *recordset* atado a
        ella—; aquí la empresa activa vive en un ``ContextVar`` y se cambia con
        ``company_scope``, que es la misma idea con el estado en otro sitio. Y
        su ``sudo().search([])`` es ``objects.all()``: el recorrido de empresas
        no se filtra por permisos porque el sincronizador es del sistema.
        """
        if not (fields_to_sync := self._company_dependent_commercial_fields()):
            return

        ResCompany = apps.get_model('base', 'ResCompany')
        active_company_id = get_current_company()
        for company_id in ResCompany.objects.values_list('pk', flat=True):
            if company_id == active_company_id:
                continue      # ≙ *"already handled by _commercial_sync_from_company"*
            with company_scope(company_id):
                # La entidad comercial se resuelve DENTRO del alcance: sus
                # valores dependientes de empresa son los de esta empresa, no
                # los de la activa de fuera.
                sync_vals = (self.commercial_partner
                             ._convert_fields_to_values(fields_to_sync))
                for key, value in sync_vals.items():
                    setattr(self, key, value)
                type(self).objects.filter(pk=self.pk).update(
                    **{fname: type(self)._meta.get_field(fname)
                       .raw_company_values(self)
                       for fname in sync_vals})

    def _commercial_sync_to_descendants(self, fields_to_sync=None):
        """≙ ``_commercial_sync_to_descendants`` (``odoo19c: :751-768``).

        Docstring de la fuente, verbatim: *"Handle sync of commercial fields to
        descendants"*.

        **La frontera es ``is_company``**, y es la mitad que un recorrido
        ingenuo se salta: una filial tiene su propio RFC, y heredar el de la
        matriz es un error fiscal, no cosmético. El recorrido sí desciende
        *dentro* de la filial —la fuente llama recursivamente sobre cada hijo
        no-empresa— pero la filial misma no recibe nada.

        Escribe **una sola vez** sobre los que de verdad difieren, no sobre
        todos: allá con un ``OrderedSet`` de ids, aquí con el mismo conjunto y
        un ``update`` por lote.
        """
        commercial_partner = self.commercial_partner
        if fields_to_sync is None:
            fields_to_sync = self._commercial_fields()
        fields_to_sync = list(fields_to_sync)
        if not fields_to_sync:
            return
        sync_vals = commercial_partner._convert_fields_to_values(fields_to_sync)
        children_ids_to_sync = OrderedSet()
        for child in self.children.all():
            if child.is_company:
                continue
            if any(getattr(child, fname) != sync_vals[fname]
                   for fname in fields_to_sync):
                children_ids_to_sync.add(child.pk)
            child._commercial_sync_to_descendants(fields_to_sync)
        if children_ids_to_sync:
            type(self).objects.filter(
                pk__in=list(children_ids_to_sync)).update(**sync_vals)

    # ------------------------------------------------------------------
    # Restricciones y onchange — ``odoo19c: res_partner.py:546-599`` y ``:647``.
    #
    # Son dos mecanismos y no se confunden. La **restriccion** corre al
    # guardar y rechaza un estado imposible; el **onchange** corre con el
    # formulario abierto y propone un valor coherente antes de guardar. Un
    # estado de otro pais no es imposible —se persiste sin error—, sólo es
    # falso: por eso hace falta el segundo.
    #
    # DOS de los siete simbolos de este bloque no se portan, y su motivo. El
    # tercero, ``_check_barcode_unicity`` (``:647-651``), quedo portado en la
    # tarea **#111**: su bloqueo era ``barcode``, y el mecanismo
    # ``company_dependent`` ya existe (``orm/fields_company_dependent.py``).
    #
    # - ``_check_partner_company`` (``:551-561``) —
    #   BLOQUEADO por ``company_id`` — el campo ``res.partner.company_id``
    #   (``odoo19c: :285``) no existe en este puerto (medido: 0 declaraciones
    #   en este archivo). Sin el no hay que comparar contra que.
    # - ``_onchange_company_id`` (``:596-599``) —
    #   BLOQUEADO por ``company_id`` — mismo campo ausente.
    #   Los dos se desbloquean juntos; sucesor: tarea **#110**.
    # ------------------------------------------------------------------
    def _check_parent_id(self):
        """≙ ``_check_parent_id`` (``odoo19c: res_partner.py:546-549``).

        Mensaje de la fuente, verbatim: *"You cannot create recursive Partner
        hierarchies."*

        La fuente lo resuelve con ``_has_cycle()`` del ORM; aqui se recorre la
        cadena, que es lo que ese ayudante hace por dentro — mismo mecanismo
        que :meth:`ResPartnerCategory._check_parent_id`, ya portado.

        **Por que es una restriccion y no un aviso:** con un ciclo
        persistido, ``_compute_complete_name``, ``_compute_parent_path`` y
        ``_children_sync`` recorren el arbol sin condicion de parada. Medido
        antes de portarla: guardar un partner como padre de si mismo levanta
        ``RecursionError``, no un error de datos.
        """
        seen = set()
        current = self.parent
        while current is not None:
            if current.pk == self.pk or current.pk in seen:
                raise ValidationError(
                    'No se pueden crear jerarquias recursivas de contactos.')
            seen.add(current.pk)
            current = current.parent

    def _check_barcode_unicity(self):
        """≙ ``_check_barcode_unicity`` (``odoo19c: res_partner.py:647-651``).

        Mensaje de la fuente, verbatim: *"Another partner already has this
        barcode"*.

        Estuvo BLOQUEADO por ``barcode`` hasta la tarea **#111**: la fuente lo
        declara ``company_dependent=True`` y ese mecanismo de campo no existia
        aqui. Hoy existe (``orm/fields_company_dependent.py``), y con el la
        guarda se porta con su firma y su mensaje.

        **La unicidad es POR EMPRESA, y ahi esta el punto.** El ``search_count``
        de la fuente corre bajo la empresa activa, asi que dos contactos con el
        mismo codigo en empresas distintas **no** colisionan — es exactamente
        lo que ``company_dependent`` compra. Aqui la lectura del atributo ya
        resuelve por la empresa activa (el descriptor), asi que comparar el
        valor leido reproduce ese alcance sin nombrarlo dos veces.

        La comparacion la emite ``Field.to_sql`` (``orm/fields.py``), que para
        un campo dependiente de empresa devuelve
        ``COALESCE((columna->>empresa)::varchar, fallback)`` — el mismo
        fragmento que el ``search_count`` de la fuente compila por dentro. Por
        eso la guarda no filtra con el ORM de Django: ``get_prep_value``
        rechaza un escalar a proposito (la columna guarda el mapa), y filtrar
        por el mapa entero mediria otra cosa.

        DIVERGENCIA DE MECANISMO, declarada: la fuente cuenta con
        ``search_count(...) > 1`` porque su ``self`` ya esta persistido cuando
        el constrain corre. Aqui la guarda tambien se llama antes de insertar,
        asi que se excluye la propia fila por ``pk`` en vez de contar hasta dos
        — con ``pk`` nulo el ``exclude`` es un no-op y la cuenta es la misma.
        """
        barcode = self.barcode
        if not barcode:
            return
        table = type(self)._meta.db_table
        column = type(self)._meta.get_field('barcode').to_sql(self, table)
        rows = execute_query(SQL(
            "SELECT id FROM %s WHERE %s = %s AND id IS DISTINCT FROM %s LIMIT 1",
            SQL.identifier(table), column, barcode, self.pk,
        ), using=self._state.db or None)
        if rows:
            raise ValidationError('Another partner already has this barcode')

    def onchange_parent_id(self):
        """≙ ``onchange_parent_id`` (``odoo19c: res_partner.py:571-583``).

        Comentario de la fuente, verbatim: *"return values in result, as this
        method is used by _fields_sync()"* — devuelve, no muta. Y el suyo
        sobre el cuerpo: *"for contacts: copy the parent address, if set (aka,
        at least one value is set in the address: otherwise, keep the one from
        the contact)"*.

        **``self._origin``** — la fuente lee el tipo **guardado**, no el del
        formulario: ``(partner.type or self.type)`` con
        ``partner = self._origin``. Un contacto que esta en la base como
        ``invoice`` y al que el formulario acaba de cambiar el tipo NO toma la
        direccion del padre hasta que se guarde.

        > **Actualizado (tarea #112).** Este metodo hacia la lectura a mano
        > —``objects.filter(pk=self.pk).values_list('type')``— porque
        > ``_origin`` no existia todavia, y el docstring lo declaraba con su
        > sucesor. Ya existe: ``models.OriginMixin`` en ``src/orm/models.py``,
        > que es su hogar (segunda clausula de
        > ``atributos-de-clase-de-modelo.md``). El cuerpo se lee ahora como el
        > de la fuente, y la lectura a mano —que era la misma consulta con
        > otro nombre— desaparece.
        """
        if not self.parent_id:
            return
        result = {}
        partner = self._origin
        if (partner.type or self.type) == self.TYPE_CONTACT:
            address_values = self.parent._get_address_values()
            if address_values:
                result['value'] = address_values
        return result

    def _onchange_country_id(self):
        """≙ ``_onchange_country_id`` (``odoo19c: res_partner.py:586-589``).

        Cambiar el pais invalida el estado que pertenecia a otro. La guarda
        ``if self.country_id`` es de la fuente y no es cosmetica: **borrar**
        el pais no puede arrastrar al estado, o quien lo reescriba pierde lo
        que ya habia puesto.
        """
        if self.country_id and self.country_id != (
                self.state.country_id if self.state is not None else None):
            self.state = None

    def _onchange_state(self):
        """≙ ``_onchange_state`` (``odoo19c: res_partner.py:591-594``).

        El sentido contrario: el estado **manda** sobre el pais, porque un
        estado sólo pertenece a uno.

        **Divergencia de stack, declarada.** La fuente escribe
        ``self.state_id.country_id`` sobre un Many2one que puede estar vacio;
        alla eso es un recordset vacio y el acceso devuelve falso. Aqui
        ``self.state`` es ``None`` y el mismo acceso levantaria
        ``AttributeError``, asi que la guarda se hace explicita.
        """
        if self.state is None:
            return
        if self.state.country_id and self.country_id != self.state.country_id:
            self.country = self.state.country

    def _fields_sync(self, values):
        """≙ ``_fields_sync`` (``odoo19c: res_partner.py:770-814``).

        Docstring de la fuente, verbatim: *"Sync commercial fields and address
        fields from company and to children. Also synchronize address to
        parent. This somehow mimics related fields to the parent, with more
        control. This method should be called after updating values in cache
        e.g. self should contain new values."*

        Las tres direcciones, en el orden de la fuente:

        1. **Del padre** — al fijarse un padre nuevo o pasar a tipo contacto,
           bajan los comerciales y la dirección.
        2. **Al padre** — para un contacto la dirección **es** la de su
           empresa, así que corregirla en cualquiera de los dos lados la
           corrige en ambos. Es el sentido que sorprende, y es deliberado.
        3. **A los hijos** — vía :meth:`_children_sync`.

        :param dict values: los valores que acaban de cambiar y disparan la
            sincronización.
        """
        # 1. Del padre hacia aquí
        if values.get('parent') or values.get('type') == self.TYPE_CONTACT:
            if values.get('parent'):
                self._commercial_sync_from_company()
            if self.parent_id and self.type == self.TYPE_CONTACT:
                address_values = self.parent._get_address_values()
                if address_values:
                    self._update_address(address_values)

        # 2. De aquí hacia el padre
        address_fields = self._address_fields()
        address_to_upstream = (
            bool(self.parent_id) and self.type == self.TYPE_CONTACT
            and (any(field in values for field in address_fields)
                 or 'parent' in values)
            and any(getattr(self, fname) != getattr(self.parent, fname)
                    for fname in address_fields)
        )
        if address_to_upstream:
            # La fuente escribe ``self.parent_id.write(new_address)`` y su
            # propio comentario dice *"is going to trigger _fields_sync
            # again"*: tolera la reentrada porque converge cuando los valores
            # ya coinciden. Aquí ``write`` **todavía no está portado** (sigue
            # entre los ausentes de este archivo), así que el efecto se compone
            # con las dos piezas que sí existen —escribir sin recursar y bajar
            # a los hijos— en vez de inventar un símbolo público que la
            # referencia no declara (la clase de :ref:`h-api-578`). Cuando
            # ``write`` se porte, estas dos líneas son una: su llamada.
            new_address = self._get_address_values()
            self.parent._update_address(new_address)
            self.parent._children_sync(new_address)
        synced_fields = self._synced_commercial_fields()
        commercial_to_upstream = (
            bool(self.parent_id)
            and self.commercial_partner.pk != self.pk
            and (any(field in values for field in synced_fields)
                 or 'parent' in values)
            and any(getattr(self, fname) != getattr(self.parent, fname)
                    for fname in synced_fields)
        )
        if commercial_to_upstream:
            new_synced = self._get_synced_commercial_values()
            if new_synced:
                type(self).objects.filter(pk=self.parent_id).update(**new_synced)

        # 3. De aquí hacia los hijos
        self._children_sync(values)

    def _children_sync(self, values):
        """≙ ``_children_sync`` (``odoo19c: res_partner.py:816-827``).

        **La dirección baja sólo a los hijos de tipo contacto.** Una dirección
        de entrega es distinta a propósito; pisarla con la de la empresa
        destruye el dato que alguien capturó — y es el control que separa este
        porte de un ``children.update(**vals)``.
        """
        if not self.children.exists():
            return
        # Comerciales: sólo si este partner ES la entidad comercial
        if self.commercial_partner.pk == self.pk:
            fields_to_sync = [fname for fname in self._commercial_fields()
                              if fname in values]
            if fields_to_sync:
                self._commercial_sync_to_descendants(fields_to_sync)
        # Dirección: sólo si cambió, y sólo a los contactos
        address_fields = self._address_fields()
        if any(field in values for field in address_fields):
            for contact in self.children.filter(type=self.TYPE_CONTACT):
                contact._update_address(values)

    def _handle_first_contact_creation(self):
        """≙ ``_handle_first_contact_creation`` (``odoo19c: :829-841``).

        Docstring de la fuente, verbatim: *"On creation of first contact for a
        company (or root) that has no address, assume contact address was
        meant to be company address"*.

        Es una **heurística de captura**, y sus tres condiciones son lo que la
        hace segura: el padre es empresa o raíz, el padre **no** tiene
        dirección, y éste es su **único** hijo. Con dos hijos la suposición ya
        no se sostiene —¿la de cuál?— y con el padre ya direccionado, aplicarla
        pisaría un dato existente.
        """
        parent = self.parent
        if parent is None:
            return
        address_fields = self._address_fields()
        if (
            (parent.is_company or not parent.parent_id)
            and any(getattr(self, f) for f in address_fields)
            and not any(getattr(parent, f) for f in address_fields)
            and parent.children.count() == 1
        ):
            parent._update_address(
                self._convert_fields_to_values(address_fields))

    @classmethod
    def _load_records_create(cls, vals_list, using=DEFAULT_DB_ALIAS):
        """≙ ``_load_records_create`` (``odoo19c: res_partner.py:966-1001``).

        El enganche del cargador de datos para el alta **masiva**: crea los
        partners con la sincronización de campos **apagada** y luego la hace en
        lote, agrupando por la pareja ``(entidad comercial, padre de
        dirección)``. Sin él, sembrar cien contactos de una empresa dispararía
        cien sincronizaciones idénticas hacia los mismos hijos.

        Estuvo BLOQUEADO por ``el cargador de data XML`` — no existía aquí —
        hasta la tarea **#115**, que construyó ``orm.models.RecordLoaderMixin``
        y cerró la arista. El
        escape que usa —el contexto ``_partners_skip_fields_sync``— ya estaba
        portado en :meth:`save` desde antes; lo que faltaba era quien lo
        activara.

        Los tres pasos de la fuente, en su orden:

        1. ``super()._load_records_create`` bajo el contexto que salta la
           sincronización por registro.
        2. La **primera mitad** de ``_fields_sync`` en lote: los campos
           comerciales del partner comercial y los de dirección del padre, cada
           grupo escrito de una vez sobre sus hijos comunes.
        3. La **segunda mitad** por registro —``_children_sync`` y
           ``_handle_first_contact_creation``—, que la fuente hace *"the
           'normal' way"* porque dependen del estado ya escrito.

        Los nombres de campo son los de este árbol (``parent`` / ``children`` /
        ``commercial_partner`` en vez de ``parent_id`` / ``child_ids`` /
        ``commercial_partner_id``), que es la traducción ya declarada arriba en
        este mismo archivo.
        """
        with context_scope(_partners_skip_fields_sync=True):
            partners = super()._load_records_create(vals_list, using=using)

        # batch up first part of _fields_sync
        # group partners by commercial_partner (if not self) and parent (if
        # type == contact)
        groups = defaultdict(list)
        for partner, vals in zip(partners, vals_list):
            cp_id = None
            if vals.get('parent') and partner.commercial_partner.pk != partner.pk:
                cp_id = partner.commercial_partner.pk

            add_id = None
            if partner.parent_id and partner.type == cls.TYPE_CONTACT:
                add_id = partner.parent_id
            groups[(cp_id, add_id)].append(partner.pk)

        for (cp_id, add_id), children in groups.items():
            # values from parents (commercial, regular) written to their common
            # children
            to_write = {}
            # commercial fields from commercial partner
            if cp_id:
                to_write = cls.objects.using(using).get(
                    pk=cp_id)._convert_fields_to_values(cls._commercial_fields())
            # address fields from parent
            if add_id:
                parent = cls.objects.using(using).get(pk=add_id)
                for fname in cls._address_fields():
                    value = getattr(parent, fname)
                    if value:
                        to_write[fname] = value
            if to_write:
                with sudo():
                    cls.objects.using(using).filter(
                        pk__in=children).update(**to_write)

        # do the second half of _fields_sync the "normal" way
        for partner, vals in zip(partners, vals_list):
            partner._children_sync(vals)
            partner._handle_first_contact_creation()
        return partners

    @property
    def commercial_partner(self):
        """El partner que representa la **entidad comercial** del contacto.

        Sube por la cadena de padres hasta la primera company. Un contacto
        suelto (sin padre) es su propia entidad comercial — por eso el corte
        es ``is_company or not parent``, no sólo ``is_company``.

        El campo publico es ``commercial_partner``; el computo privado es
        :meth:`_compute_commercial_partner`. La fuente parte cada campo en
        dos y esa frontera ES el punto de extension: un addon que cambie
        como se deriva la entidad comercial sobreescribe el computo, no la
        lectura.

        ≙ el campo ``commercial_partner_id``
        (``odoo19c: base/models/res_partner.py:515``).
        """
        return self._compute_commercial_partner()

    def _compute_commercial_partner(self):
        """≙ ``_compute_commercial_partner`` (``odoo19c: res_partner.py:515``).

        Sube por la cadena de padres hasta la primera company. El corte es
        ``is_company or not parent_id`` verbatim de la fuente: un contacto
        suelto es su propia entidad comercial.
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

        El campo publico es ``commercial_company_name``; el computo privado
        es :meth:`_compute_commercial_company_name`.

        ≙ el campo ``commercial_company_name``
        (``odoo19c: base/models/res_partner.py:523``).
        """
        return self._compute_commercial_company_name()

    def _compute_commercial_company_name(self):
        """≙ ``_compute_commercial_company_name``
        (``odoo19c: res_partner.py:523``).

        La fuente lo resuelve con ``p.is_company and p.name or
        partner.company_name``: si la entidad comercial es empresa, su
        nombre; si no, la razon social escrita a mano en este contacto.
        """
        p = self.commercial_partner
        return p.name if p.is_company else self.company_name

    # ------------------------------------------------------------------
    # El punto de entrada de escritura — ``odoo19c: res_partner.py:856-948``.
    #
    # La referencia parte en dos lo que Django unifica: ``create(vals_list)`` y
    # ``write(vals)``. Aquí los dos caminos viven en ``save()`` y se distinguen
    # por ``self._state.adding``, que es como este ORM dice «esta fila es
    # nueva». Lo que ambos hacen es idéntico en la fuente y aquí también:
    # limpiar la web, borrar ``company_name`` si se fijó un padre, y **llamar a
    # `_fields_sync`** — que hasta este porte existía sin llamador, la forma que
    # :ref:`h-api-836` registró.
    # ------------------------------------------------------------------
    #: Campos cuyo cambio dispara la sincronización — los que ``_fields_sync``
    #: consulta en sus tres pasos. Se deriva de los tres métodos que ya
    #: declaran su lista en vez de repetirla aquí: una cuarta copia sería un
    #: sitio más donde olvidar añadir un campo.
    @classmethod
    def _sync_trigger_fields(cls):
        return list(dict.fromkeys(
            cls._address_fields() + cls._commercial_fields()
            + ['parent', 'type']))

    @staticmethod
    def _clean_website(website):
        """≙ ``_clean_website`` (``odoo19c: res_partner.py:843-849``).

        Una web capturada como ``kaupamex.mx`` no es un enlace: el navegador
        la resuelve como ruta relativa. La fuente le antepone el esquema, y su
        rodeo por ``netloc``/``path`` es porque un parseo sin esquema mete todo
        en ``path``. Aquí lo hace ``urlsplit`` de la stdlib, que expone las
        mismas piezas.
        """
        if not website:
            return website
        partes = urlsplit(website)
        if partes.scheme:
            return website
        if not partes.netloc:
            partes = partes._replace(netloc=partes.path, path='')
        return urlunsplit(partes._replace(scheme='http'))

    def save(self, *args, **kwargs):
        """Escribe y sincroniza — ≙ ``create`` (``:926``) y ``write`` (``:856``).

        Las dos preparaciones que la fuente hace en ambos caminos, y el porqué
        de cada una:

        - **la web se limpia** para que ``kaupamex.mx`` sea un enlace y no una
          ruta relativa;
        - **``company_name`` se borra al fijar un padre**, porque ese campo es
          la razón social escrita a mano de un contacto **suelto**; con padre,
          la razón social la da la entidad comercial y tener las dos es tener
          dos verdades.

        Después escribe y **sincroniza sólo lo que de verdad cambió**. Ese
        filtro es de la fuente y no es una optimización: su comentario lo dice
        —*"we should avoid infinite loops in case same value is updated due to
        cycles"*—. Sincronizar un valor que no cambió puede reentrar por el
        ciclo padre/hijo y no terminar.

        Escape declarado, ≙ el contexto ``_partners_skip_fields_sync`` de la
        fuente (``:942``): dentro de un ``context_scope`` con esa clave, la
        escritura no sincroniza. Existe para la carga masiva de datos, donde
        sincronizar fila a fila es cuadrático y el cargador ya escribe los
        valores finales.
        """
        creating = self._state.adding
        # ``@api.constrains('parent_id')`` de la fuente. Va ANTES de tocar
        # nada: un ciclo hace que ``_compute_complete_name`` mas abajo recurse
        # sin condicion de parada, asi que el rechazo tiene que llegar
        # primero.
        self._check_parent_id()
        # ``@api.constrains('barcode')`` de la fuente (``:646-651``). Va aqui
        # y no en ``clean``: la unicidad es POR EMPRESA y su lectura depende de
        # la empresa activa, asi que tiene que correr en el mismo camino que
        # persiste el valor.
        self._check_barcode_unicity()
        if self.website:
            self.website = self._clean_website(self.website)
        if self.parent_id:
            self.company_name = ''

        watched = self._sync_trigger_fields()
        pre_values = {}
        if not creating:
            fila = type(self).objects.filter(pk=self.pk).first()
            if fila is not None:
                pre_values = {fname: getattr(fila, fname) for fname in watched}

        # Las DOS columnas calculadas del bloque de etiquetas. La tercera,
        # ``company_registry``, tiene un compute que es no-op deliberado en la
        # fuente (*"exists to allow overrides"*), asi que no se cablea aqui:
        # se captura a mano y una localizacion lo deriva sobreescribiendo
        # ``_compute_company_registry``.
        self.complete_name = self._compute_complete_name()
        # Los dos computos con columna del bloque de usuario e idioma. Van
        # ANTES del ``super().save`` porque ``store=True`` en la fuente: el
        # valor se persiste, no se deriva en cada lectura.
        self.lang = self._compute_lang()
        self.user = self._compute_user_id()
        if not creating:
            # ``partner_share`` mira ``self.users``, que necesita PK. Al crear
            # no hay usuarios todavia y queda en su default (True = cliente
            # sin acceso), que es lo que la fuente calcula para un partner sin
            # ``user_ids``.
            #
            # COBERTURA PARCIAL DECLARADA: la fuente lo declara
            # ``@api.depends('user_ids.share', 'user_ids.active')`` — recalcula
            # cuando cambian los USUARIOS, no cuando cambia el partner. Aqui
            # se recalcula en el lado del partner; el lado del usuario
            # (crear/borrar/mover de grupo un ``ResUsers`` de este partner) NO
            # dispara todavia. Sucesor: tarea **#108**.
            self.partner_share = self._compute_partner_share()

        result = super().save(*args, **kwargs)

        if get_context().get('_partners_skip_fields_sync'):
            return result

        if creating:
            updated = {fname: getattr(self, fname) for fname in watched
                       if getattr(self, fname)}
        else:
            updated = {fname: getattr(self, fname) for fname in watched
                       if getattr(self, fname) != pre_values.get(fname)}
        if updated:
            self._fields_sync(updated)
        return result

    # ------------------------------------------------------------------
    # Alta desde un texto, promocion a empresa, y guarda del borrado —
    # ``odoo19c: res_partner.py:951-961``, ``:1004-1021`` y ``:1072-1120``.
    #
    # ``ensure_one()`` de la fuente NO aparece en los cuerpos de abajo: es
    # divergencia de STACK, no una omision. Alla ``self`` es un recordset que
    # puede traer N registros y el metodo exige uno; aqui una instancia de
    # Django **es** un registro, asi que la comprobacion no tiene sobre que
    # fallar.
    # ------------------------------------------------------------------
    def open_commercial_entity(self):
        """≙ ``open_commercial_entity`` (``odoo19c: res_partner.py:1023-1031``).

        Docstring de la fuente, verbatim: *"Utility method used to add an
        "Open Company" button in partner views"*.

        Devuelve el **descriptor** de la ventana, no la abre: es un dato, y
        por eso se porta verbatim aunque la interfaz sea otra. La forma
        —``ir.actions.act_window`` con modelo, vista, registro y destino— ya
        vive en este arbol (``base/wizard/wizard_ir_model_menu_create.py:58``),
        asi que no se inventa nada.
        """
        return {'type': 'ir.actions.act_window',
                'res_model': 'res.partner',
                'view_mode': 'form',
                'res_id': self.commercial_partner.pk,
                'target': 'current',
                }

    @classmethod
    def view_header_get(cls, view_id, view_type):
        """≙ ``view_header_get`` (``odoo19c: res_partner.py:1204-1210``).

        El titulo de la lista cuando esta filtrada por etiqueta. Sin clave en
        contexto no hay cabecera: una lista sin filtro con titulo de filtro
        promete un recorte que no existe.

        **Divergencia de stack, declarada:** la fuente cae a
        ``super().view_header_get(...)``, definido en su ``models.Model``. Ese
        metodo **no existe** en ``src/orm`` (medido: 0 definiciones de
        ``def view_header_get``), y su cuerpo alla devuelve ``False``. Aqui el
        equivalente es ``None``, que es lo que el llamador distingue.

        **Y una divergencia de conducta, tambien declarada:** la fuente hace
        ``browse(id).name`` sobre un id que puede no existir, y su recordset
        vacio devuelve ``False`` sin reventar. Un ``get`` de Django levantaria
        ``DoesNotExist``. La cabecera es decoracion: que un id muerto en el
        contexto tumbe la lista seria peor que no ponerla.
        """
        category_id = get_context().get('category_id')
        if not category_id:
            return None
        category = ResPartnerCategory.objects.filter(pk=category_id).first()
        if category is None:
            return None
        return f'Contactos: {category.name}'

    @classmethod
    def name_create(cls, name):
        """≙ ``name_create`` (``odoo19c: res_partner.py:1072-1093``).

        Docstring de la fuente, verbatim: *"Override of orm's name_create
        method for partners. The purpose is to handle some basic formats to
        create partners using the name_create. If only an email address is
        received and that the regex cannot find a name, the name will have the
        email value. If 'force_email' key in context: must find the email
        address."*

        La asimetria que importa: el nombre cae al correo cuando no hay
        nombre — una fila sin nada legible no sirve en ninguna lista.

        **La guarda ``if email_normalized`` ya es observable** (tarea #113).
        Su comentario en la fuente lo dice: *"keep default_email in
        context"*. Cuando el nombre no trae correo, la clave no se escribe, y
        entonces el ``default_email`` del contexto llega a la fila por
        ``default_get`` — que es lo que hace :meth:`create` de
        ``DefaultGetMixin``, el mismo paso que la fuente da en
        ``odoo19c: odoo/orm/models.py:4796``. Antes de #113 no habia base a
        la que preguntar, asi que la guarda se conservaba por fidelidad y no
        cambiaba nada.

        **Divergencia de mecanismo, declarada:** la fuente empieza limpiando
        un ``default_type`` invalido del contexto
        (``self._fields['type'].get_values(self.env)``). Aqui el tipo lo
        valida el ``choices`` del campo en el propio ``save``, asi que un
        valor invalido no llega a escribirse; no hay contexto que limpiar.

        :return: la tupla ``(id, display_name)`` de la fuente.
        """
        name, email_normalized = parse_contact_from_email(name)
        if get_context().get('force_email') and not email_normalized:
            raise ValidationError(
                'No se puede crear un contacto sin direccion de correo.')

        create_values = {cls._rec_name: name or email_normalized}
        if email_normalized:   # keep default_email in context
            create_values['email'] = email_normalized
        partner = cls.create(**create_values)
        return partner.pk, partner.display_name

    @classmethod
    def find_or_create(cls, email, assert_valid_email=False):
        """≙ ``find_or_create`` (``odoo19c: res_partner.py:1095-1120``).

        Docstring de la fuente, verbatim: *"Find a partner with the given
        ``email`` or use :meth:`name_create` to create a new one."*

        :param str email: texto tipo correo, que debe traer al menos una
            direccion — p. ej. ``"Raoul Grosbedon <r.g@grosbedon.fr>"``.
        :param bool assert_valid_email: revienta si no encuentra una valida.

        La busqueda es ``=ilike`` en la fuente, y eso **no** es descuido: un
        correo escrito en mayusculas crearia un segundo partner para la misma
        persona, que es justo el duplicado que este metodo existe para evitar.
        """
        if not email:
            raise ValueError(
                'find_or_create necesita una direccion de correo.')

        parsed_name, parsed_email_normalized = parse_contact_from_email(email)
        if not parsed_email_normalized and assert_valid_email:
            raise ValueError(
                'find_or_create necesita una direccion de correo valida.')

        if parsed_email_normalized:
            partner = cls.objects.filter(
                email__iexact=parsed_email_normalized).first()
            if partner is not None:
                return partner

        create_values = {'name': parsed_name or parsed_email_normalized}
        if parsed_email_normalized:
            create_values['email'] = parsed_email_normalized
        return cls.objects.create(**create_values)

    def create_company(self):
        """≙ ``create_company`` (``odoo19c: res_partner.py:1004-1012``).

        Promueve la razon social escrita a mano de un contacto suelto a un
        partner **padre real**, y le cuelga el contacto y sus hijos.

        Mover a los hijos no es cosmetico: sin ese paso las direcciones se
        quedan colgando del contacto en vez de de la empresa, y la jerarquia
        acaba con dos niveles donde la fuente deja uno.

        **Divergencia de mecanismo, declarada:** la fuente lo hace en un solo
        ``write`` con ``Command.update`` sobre ``child_ids``. ``write`` no
        esta portado (sigue entre los ausentes de este archivo), asi que el
        efecto se compone con las dos piezas que si existen — guardar el
        propio registro y un ``update`` en bloque sobre los hijos. Cuando
        ``write`` se porte, las dos son una.
        """
        new_company = self._create_contact_parent_company()
        if new_company is not None:
            children_ids = list(
                self.children.values_list('pk', flat=True))
            self.parent = new_company
            self.save()
            if children_ids:
                type(self).objects.filter(pk__in=children_ids).update(
                    parent=new_company)
        return True

    def _create_contact_parent_company(self):
        """≙ ``_create_contact_parent_company`` (``odoo19c: :1014-1021``).

        La empresa nueva se lleva el nombre, el identificador fiscal y la
        direccion del contacto. Sin ``company_name`` devuelve ``None`` — la
        fuente devuelve ``self.browse()``, un recordset vacio, y el llamador
        distingue ese caso: crear un padre sin nombre dejaria un partner vacio
        colgando de cada contacto que pulse el boton por error.
        """
        if not self.company_name:
            return None
        values = dict(name=self.company_name, is_company=True, vat=self.vat)
        values.update(self._convert_fields_to_values(self._address_fields()))
        return type(self).objects.create(**values)

    def delete(self, *args, **kwargs):
        """Guarda del borrado — ≙ ``_unlink_except_user`` (``:951-961``).

        La fuente lo declara ``@api.ondelete(at_uninstall=False)``; el enganche
        equivalente de Django es sobreescribir ``delete``.
        """
        self._unlink_except_user()
        return super().delete(*args, **kwargs)

    def _unlink_except_user(self):
        """≙ ``_unlink_except_user`` (``odoo19c: res_partner.py:951-961``).

        Un partner con cuenta **activa** no se borra. Su comentario propio dice
        el caso contrario —*"no linked user, operation is allowed"*— y su
        mensaje da el consejo: archivar el usuario primero.

        Nombrar las cuentas en el mensaje es parte del contrato, no adorno: sin
        el ``names=`` de la fuente, quien lo lee no sabe **cual** archivar y el
        consejo no se puede seguir.

        **Divergencia de mecanismo, declarada:** la fuente adjunta al
        ``RedirectWarning`` la accion ``users._action_show()``, una ventana de
        ``ir.actions.act_window``. Ese simbolo no existe aqui (medido: 0
        definiciones; su unica aparicion es la lista de ausentes del docstring
        de ``res_users.py``), y este arbol no tiene consumidor de acciones de
        ventana. Se levanta la misma excepcion sin accion; el mensaje, que es
        lo que el usuario lee, va entero.
        """
        if not self.pk:
            return
        users = list(self.users.all())
        if not users:
            return
        names = ', '.join(str(user) for user in users)
        raise RedirectWarning(
            'No se pueden borrar contactos ligados a un usuario activo.\n'
            'Conviene archivarlos despues de archivar su usuario asociado.\n\n'
            f'Usuarios activos ligados: {names}',
            button_text='Ir a usuarios')

    # ------------------------------------------------------------------
    # Dirección — ``odoo19c: res_partner.py:1120-1250``.
    #
    # **El formato lo pone el PAÍS, no el código.** La referencia no formatea
    # una dirección en Python: pide al país su ``address_format`` —una
    # plantilla de ``%(campo)s``— y la rellena. Es la diferencia entre servir
    # a México y servir a Japón, donde el orden se invierte; un formateador
    # cableado es correcto en uno y falso en el otro, y el error no se ve
    # hasta que hay un cliente allá.
    #
    # **Divergencia de nombre, única y declarada:** la referencia usa
    # ``state_id`` / ``country_id`` / ``parent_id`` / ``child_ids``; aquí son
    # ``state`` / ``country`` / ``parent`` / ``children`` (la convención de FK
    # de Django, ya declarada en :meth:`_address_fields`). Y donde la fuente
    # escribe ``self[campo]`` —el ``__getitem__`` de su recordset— aquí va
    # ``getattr(self, campo)``: ``models.Model`` de Django no lo declara.
    #
    # **Cobertura del bloque: 10 de 12 símbolos.** Los dos que NO se portan
    # son del asistente de importación CSV, y su razón es medida, no de
    # conveniencia:
    #
    # - ``get_import_templates`` (``odoo19c: res_partner.py:1215-1220``)
    #   devuelve la ruta de un ``.xlsx`` bajo ``/base/static/xls/``. Ese
    #   archivo no existe en este árbol y el asistente que lo ofrece tampoco.
    # - ``_check_import_consistency`` (``:1222-1240``) sólo se invoca desde
    #   ``create`` cuando el contexto trae ``import_file`` (``:928-929``) —
    #   la ruta del asistente, que aquí no hay. Además su cuerpo **no puede
    #   rechazar nada**: deriva ``country_id`` del mismo estado que luego
    #   compara contra ``state.country_id.id``, así que la condición es
    #   siempre falsa. Idéntico en 18 (``odoo18c: :1097-1104``), o sea que
    #   no es una regresión de 19 sino un no-op estable de la fuente. Cuál
    #   de los dos desenlaces toca —portarlo verbatim con su defecto, o
    #   divergir arreglándolo— es decisión del ejecutor: **tarea #103**.
    # ------------------------------------------------------------------
    def _compute_is_public(self):
        """¿Algun usuario de este partner es el visitante anonimo?

        ≙ ``_compute_is_public`` (``odoo19c: res_partner.py:851``):
        ``users and any(user._is_public() for user in users)``.

        Sin esto nada distingue un cliente real del registro que representa a
        «cualquiera que entre sin sesion». El ``and`` de la fuente no es
        redundante con ``any([])``: declara que la pregunta se hace sobre un
        conjunto no vacio.

        Dos divergencias de mecanismo, ninguna de conducta:

        - ``with_context(active_test=False)`` — la fuente desactiva el filtro
          implicito de ``active`` para contar tambien usuarios archivados.
          Aqui ese filtro no existe: ``self.users.all()`` no filtra por
          ``active``, asi que el conjunto ya es el que la fuente busca.
        - ``compute_sudo=True`` — la respuesta no depende de quien pregunte.
          Aqui la lectura de la relacion inversa no pasa por regla de fila,
          asi que el efecto ya se cumple.
        """
        users = list(self.users.all()) if self.pk else []
        return bool(users) and any(user._is_public() for user in users)

    def _compute_get_ids(self):
        """El propio registro — ≙ ``_compute_get_ids``
        (``odoo19c: res_partner.py:510``).

        La fuente escribe ``partner.self = partner.id`` sobre un campo
        declarado ``Many2one('res.partner')`` (``:312``), asi que el valor
        que se lee es el REGISTRO, no su entero: quien lo consume puede
        atravesar a sus campos.

        Aqui se devuelve ``self`` directo. El campo publico se llama ``self``
        igual que alla; no colisiona con el parametro porque el descriptor
        vive en la clase y el parametro en el ambito del metodo.
        """
        return self

    # ------------------------------------------------------------------
    # display_name — el nombre enriquecido segun quien lo pide
    # ≙ ``odoo19c: odoo/addons/base/models/res_partner.py:1038-1069``
    # ------------------------------------------------------------------
    def _compute_display_name(self):
        """El nombre completo, enriquecido segun cinco claves de contexto.

        ≙ ``_compute_display_name`` (``odoo19c: res_partner.py:1038``).

        ``complete_name`` es el nombre para una lista; ``display_name`` es ese
        nombre **adaptado a quien lo pide**: el mismo partner se muestra
        distinto en un selector de correo (con el buzon), en una pantalla de
        soporte (con el id de base) o en un documento fiscal (con el RFC). La
        fuente resuelve eso con cinco claves y dos formas.

        La rama ``formatted_display_name`` no anexa: cambia la FORMA entera a
        «Empresa \t --Persona--». Dentro de ella el correo y el id son
        **alternativos** (``elif`` en la fuente), no acumulativos como en la
        otra rama — es una diferencia real y el test la mide.

        El ``with_context(lang=...)`` de la fuente no se porta: fija el idioma
        del hilo para la traduccion de la etiqueta del tipo. Aqui el catalogo
        esta vacio (0 archivos ``.po``, medido) y ``_get_complete_name`` lee
        ``TYPES``, que es una lista literal — no hay traduccion que fijar. Se
        cierra con el catalogo, no antes.
        """
        contexto = get_context()
        type_description = dict(self.TYPES)

        if contexto.get('formatted_display_name'):
            name = self.name or ''
            if self.parent_id or self.company_name:
                company = self.company_name or (
                    self.parent.name if self.parent_id else '')
                own = self.name or type_description.get(self.type, '')
                name = f"{company} \t --{own}--"
            if contexto.get('show_email') and self.email:
                name = f"{name} \t --{self.email}--"
            elif contexto.get('partner_show_db_id'):
                name = f"{name} \t --{self.pk}--"
        else:
            name = self._get_complete_name()
            if contexto.get('partner_show_db_id'):
                name = f"{name} ({self.pk})"
            if contexto.get('show_email') and self.email:
                name = f"{name} <{self.email}>"
            if contexto.get('show_address'):
                name = name + "\n" + self._display_address(without_company=True)
            if contexto.get('show_vat') and self.vat:
                if contexto.get('show_address'):
                    name = f"{name} \n {self.vat}"
                else:
                    name = f"{name} - {self.vat}"

        # ≙ *"Remove extra empty lines"* de la fuente (``:1067``): la plantilla
        # del pais deja blancos delante del salto cuando una parte va vacia.
        name = re.sub(r'\s+\n', '\n', name)
        return name.strip()

    # ------------------------------------------------------------------
    # El avatar y su relleno por tipo de direccion
    # ≙ ``odoo19c: odoo/addons/base/models/res_partner.py:334-377``
    # ------------------------------------------------------------------
    def _avatar_get_placeholder_path(self):
        """Que dibujo le toca a este partner cuando no hay imagen.

        ≙ ``_avatar_get_placeholder_path`` (``odoo19c: res_partner.py:367``),
        cascada verbatim incluido su ORDEN: ``is_company`` se pregunta ANTES
        que el tipo, asi que una empresa marcada como direccion de entrega es
        un edificio y no un camion.

        El motivo es de producto: una bodega no es una persona, y ponerle la
        inicial «B» sobre un color aleatorio no comunica nada. Un camion si.
        """
        if self.is_company:
            return 'base/static/img/company_image.png'
        if self.type == self.TYPE_DELIVERY:
            return 'base/static/img/truck.png'
        if self.type == self.TYPE_INVOICE:
            return 'base/static/img/bill.png'
        if self.type == self.TYPE_OTHER:
            return 'base/static/img/puzzle.png'
        return super()._avatar_get_placeholder_path()

    def _compute_avatar(self, image_field):
        """Reenruta la decision del mixin en tres ramas.

        ≙ ``_compute_avatar`` (``odoo19c: res_partner.py:355``). El mixin
        resuelve «imagen si la hay, si no la inicial»; ``res.partner`` lo
        reenruta porque no todos sus registros son personas:

        1. **Con usuario interno, o de tipo ``contact``** → lo del mixin. Es
           una persona: su inicial sirve.
        2. **Sin usuario interno y sin imagen** → el relleno de SU TIPO
           (camion, factura, pieza, edificio).
        3. **Sin usuario interno pero con imagen** → su propia imagen.

        DIVERGENCIA DE FIRMA declarada: la fuente recibe
        ``(avatar_field, image_field)`` y ASIGNA sobre un conjunto de
        registros; el mixin de aqui recibe ``(image_field)`` y DEVUELVE para
        uno solo, porque los cinco ``avatar_NNNN`` son ``property``. La
        particion en tres es la misma; lo que cambia es que aqui no hay
        conjunto que filtrar.

        ``user.share`` de la fuente es lo contrario de interno; aqui eso es
        ``user._is_internal()`` (``res_users.py:1625``) — la misma
        equivalencia que usa ``_compute_partner_share``.
        """
        has_internal_user = bool(
            self.pk and any(user._is_internal() for user in self.users.all()))
        if has_internal_user or self.type == self.TYPE_CONTACT:
            return super()._compute_avatar(image_field)
        imagen = getattr(self, image_field, None)
        if not imagen:
            return b64encode(self._avatar_get_placeholder())
        return imagen

    # Los cinco ``_compute_avatar_NNNN`` (``:334-353``) NO se portan, y es
    # divergencia declarada, no omision: en la fuente su cuerpo es UNA linea
    # —``super()._compute_avatar_NNNN()``— y existen solo para redeclarar
    # ``@api.depends`` con ``name``, ``user_ids.share``, ``is_company`` y
    # ``type``, porque su ORM necesita saber de que depende el computo para
    # invalidarlo. Aqui los cinco ``avatar_NNNN`` son ``property``: se
    # calculan al leer, asi que no hay grafo de dependencias que declarar y
    # el mecanismo que los justifica no tiene receptor.
    #
    # *Metrica:* el cuerpo de los cinco en ``odoo19c: res_partner.py:334-353``.
    # *Ciega a:* un addon que sobreescriba uno de los cinco para hacer algo
    # mas que delegar. Medido en la referencia: ninguno lo hace en ``base``.

    # ------------------------------------------------------------------
    # El nombre completo y las etiquetas calculadas
    # ≙ ``odoo19c: odoo/addons/base/models/res_partner.py:378-544, 602-648``
    # ------------------------------------------------------------------
    def _get_complete_name(self):
        """El nombre que se muestra en una lista — «Empresa, Persona».

        ≙ ``_get_complete_name`` (``odoo19c: res_partner.py:378``). Sin esta
        anteposicion una lista con contactos de varias empresas es ilegible:
        salen tres «Ana» sin decir de quien es cada una.

        Dos divergencias de mecanismo, ambas medidas:

        - El catalogo de tipos: la fuente lo pide con
          ``self._fields['type']._description_selection(self.env)`` porque su
          Selection puede ser un invocable; aqui ``TYPES`` es una lista
          literal en la clase y ``dict(self.TYPES)`` es la misma tabla.
        - ``self.sudo().parent_id.name``: el ``sudo()`` de la fuente esquiva
          la regla de fila para poder anteponer el nombre de una empresa que
          el lector no puede ver. Aqui se lee ``self.parent.name`` directo —
          el confinamiento por fila de este arbol vive en el queryset del
          endpoint, no en el atravesar la FK, asi que no hay nada que
          esquivar.
        """
        displayed_types = self._complete_name_displayed_types
        type_description = dict(self.TYPES)

        name = self.name or ''
        if self.company_name or self.parent_id:
            if not name and self.type in displayed_types:
                name = type_description[self.type]
            if (not self.is_company
                    and not get_context().get(
                        'partner_display_name_hide_company')):
                padre = self.parent.name if self.parent_id else ''
                name = f"{self.commercial_company_name or padre}, {name}"
        return name.strip()

    def _compute_complete_name(self):
        """El valor que se escribe en la columna ``complete_name``.

        ≙ ``_compute_complete_name`` (``:393``). La fuente lo calcula
        ``with_context({})`` — vaciando el contexto — para que el valor
        ALMACENADO nunca dependa de ``partner_display_name_hide_company``,
        que es una clave de vista.

        DIVERGENCIA DECLARADA: aqui no se vacia el contexto.

        *Metrica:* consumidores de esa clave, ``grep -rn`` sobre ``src/``,
        ``addons/`` y ``tests/``.
        *Resultado:* **0**. En la fuente el unico que la fija es
        ``crm/views/crm_lead_views.xml`` — una vista XML, y aqui la interfaz
        es React y no hay arch XML que la ponga. Vaciar un contexto que nadie
        puebla no cambia ningun valor.
        *Ciega a:* un consumidor futuro. Cuando alguien fije esa clave, este
        metodo necesita un ambito que la limpie — registrado como tarea
        **#106**.
        """
        return self._get_complete_name()

    def _compute_active_lang_count(self):
        """Cuantos idiomas activos hay instalados.

        ≙ ``_compute_active_lang_count`` (``:408``), que hace
        ``len(self.env['res.lang'].get_installed())``.

        ``get_installed`` todavia no esta portado (tarea **#104**), pero el
        NUMERO no depende de el: ``get_installed`` devuelve los idiomas
        ``active`` y lo unico que la fuente usa es su longitud. Se cuenta
        directo. Cuando **#104** aterrice, el cuerpo delega en el.
        """
        return ResLang.objects.filter(active=True).count()

    def _compute_tz_offset(self):
        """El desfase de la zona horaria, en la forma ``+HHMM``.

        ≙ ``_compute_tz_offset`` (``:414``):
        ``datetime.datetime.now(pytz.timezone(partner.tz or 'GMT')).strftime('%z')``

        DIVERGENCIA DE STACK: ``pytz`` no esta instalado (medido:
        ``ModuleNotFoundError``). Se usa ``zoneinfo`` de la biblioteca
        estandar, que da el mismo ``%z``.

        El respaldo a GMT se queda, y ahora por una razon MAS ESTRECHA que
        antes. La tarea **#107** ya acoto ``tz`` a la Selection de la fuente
        (``choices=_tzs``), pero eso **no** hace imposible la basura: en
        Django ``choices`` es **validacion, no DDL** —el mismo hecho que
        desbloqueo la tarea #118—, asi que PostgreSQL no recibe ningun
        ``CHECK`` y un ``objects.create(tz='No/Existe')`` escribe la fila.
        Solo ``full_clean()`` la rechaza.

        Quedan por tanto dos vias por las que una zona invalida llega hasta
        aqui: un dato anterior al acotamiento, y una escritura que no pase por
        ``full_clean()``. Cualquiera de las dos levantaria
        ``ZoneInfoNotFoundError`` al **LEER** el partner, no al escribirlo —
        que es el peor sitio donde puede reventar.
        """
        try:
            zona = ZoneInfo(self.tz or 'GMT')
        except (ZoneInfoNotFoundError, ValueError):
            zona = ZoneInfo('GMT')
        return datetime.datetime.now(zona).strftime('%z')

    def _compute_vat_label(self):
        """Como se llama el identificador fiscal: «RFC» en Mexico, «NIF» en
        Espana.

        ≙ ``_compute_vat_label`` (``:490``):
        ``self.env.company.country_id.vat_label or _("Tax ID")``.

        Es del pais de la **empresa activa**, no del pais del partner: un
        operador mexicano ve «RFC» en toda ficha, sea de quien sea. El
        ``env.company`` de la fuente es aqui ``get_current_company()``
        (``src/orm/environments.py:153``), y la etiqueta la resuelve
        ``FormatVatLabelMixin.vat_label_for``, que ya existe.
        """
        company_id = get_current_company()
        if company_id:
            # ``apps.get_model`` y no un import al top: ``res_company.py:97``
            # importa ``ResPartner``, asi que el import directo cierra un
            # ciclo REAL (medido con grep en ambos sentidos). Es la excepcion
            # #3 de ``no-lazy-imports.md`` resuelta como manda —refactor al
            # mecanismo de Django— y no con un import perezoso: es una
            # llamada, no un statement.
            ResCompany = apps.get_model('base', 'ResCompany')
            company = ResCompany.objects.filter(pk=company_id).first()
            if company is not None:
                etiqueta = FormatVatLabelMixin.vat_label_for(company)
                if etiqueta:
                    return etiqueta
        return _('Tax ID')

    def _compute_type_address_label(self):
        """Como se llama esta direccion.

        ≙ ``_compute_type_address_label`` (``:494``), verbatim incluidos los
        cuatro literales, que van por ``_()`` como en la fuente.

        Salen en INGLES, y es correcto: el arbol declara
        ``LANGUAGE_CODE = 'es-mx'`` y ``USE_I18N = True`` pero tiene **0**
        catalogos ``.po``/``.mo`` (medido con ``find src -name '*.po'``), asi
        que ``_()`` devuelve el literal de la fuente. Traducirlos es poblar el
        catalogo, no cambiar el codigo.
        """
        if self.type == self.TYPE_INVOICE:
            return _('Invoice Address')
        if self.type == self.TYPE_DELIVERY:
            return _('Delivery Address')
        if self.type == self.TYPE_CONTACT and self.parent_id:
            return _('Company Address')
        return _('Address')

    def _compute_company_registry(self):
        """No-op deliberado — ≙ ``_compute_company_registry`` (``:528``).

        La fuente escribe ``company.company_registry = company.company_registry``
        y lo explica en su propio comentario: *"exists to allow overrides"*.
        El campo es ``store=True, readonly=False``: se captura a mano, y el
        compute existe solo para que una localizacion lo pueda derivar
        sobreescribiendo este metodo. Se porta con esa forma para que el
        punto de extension exista.
        """
        return self.company_registry

    def _compute_company_registry_label(self):
        """Como se llama el registro mercantil en su pais.

        ≙ ``_compute_company_registry_label`` (``:534``). Lee el pais del
        **partner** (la fuente nombra ``company`` a la variable del bucle,
        pero itera sobre ``self``, que son partners).
        """
        label_by_country = self._get_company_registry_labels()
        country_code = self.country.code if self.country_id else None
        return label_by_country.get(country_code, _('Company ID'))

    @classmethod
    def _get_company_registry_labels(cls):
        """El mapa pais → etiqueta, VACIO por diseno.

        ≙ ``_get_company_registry_labels`` (``:540``), que devuelve ``{}``.
        Lo pueblan las localizaciones (``l10n_*``) sobreescribiendolo. Que lo
        haria fallar: inventar entradas que ninguna localizacion portada
        respalde.
        """
        return {}

    def _compute_company_registry_placeholder(self):
        """``False`` por diseno — ≙ ``_compute_company_registry_placeholder``
        (``:543``). Lo llenan las localizaciones, igual que el mapa."""
        return False

    def _compute_email_formatted(self):
        """Lo que va en la cabecera ``To:`` de un correo.

        ≙ ``_compute_email_formatted`` (``:602``). El docstring de la fuente
        enumera los defensivos y todos se portan, porque cada uno tapa un
        fallo real de envio:

        - **doble formato**: si ``email`` ya trae ``'Ana' <ana@x>``, componer
          sobre el daria ``"Ana" <"Ana" <ana@x>>``, que ningun servidor
          acepta. Lo evita ``email_normalize_all``, que extrae la direccion.
        - **multi-buzon**: a veces el campo lleva dos direcciones. Se
          conservan las dos, sin formato individual.
        - **correo invalido**: se conserva TAL CUAL en vez de vaciarlo —
          facilita diagnosticar por que fallo el envio en vez de esconderlo.
        - **correo vacio**: ``False``, porque no hay nada que hacer con el.
        """
        if not self.email:
            return False
        emails_normalized = email_normalize_all(self.email)
        if emails_normalized:
            return formataddr((self.name or 'False',
                               ','.join(emails_normalized)))
        return formataddr((self.name or 'False', self.email))

    def _compute_company_type(self):
        """``'company'`` o ``'person'`` — ≙ ``_compute_company_type``
        (``:635``). Es la cara legible de ``is_company``."""
        return 'company' if self.is_company else 'person'

    def _write_company_type(self):
        """El inverso — mueve ``is_company`` desde ``company_type``.

        ≙ ``_write_company_type`` (``:639``). Sin el, ``company_type`` seria
        de solo lectura y el formulario que lo ofrece no cambiaria nada.
        """
        self.is_company = self.company_type == 'company'

    def onchange_company_type(self):
        """≙ ``onchange_company_type`` (``:644``) — el mismo movimiento, en el
        momento en que el usuario cambia el selector, antes de guardar.

        La fuente declara ambos (``inverse`` y ``@api.onchange``) y hacen lo
        mismo; se portan los dos porque cubren dos momentos distintos.
        """
        self.is_company = self.company_type == 'company'

    def _compute_lang(self):
        """≙ ``_compute_lang`` (``odoo19c: res_partner.py:398-405``).

        Docstring de la fuente, verbatim: *"While creating / updating child
        contact, take the parent lang by default if any. 0therwise, fallback
        to default context / DB lang"* (el cero es de la fuente).

        La asimetria del ``if``/``elif`` importa y no es cosmetica: **con
        padre, el idioma del padre gana** sobre el que el hijo ya tuviera; sin
        padre, sólo se rellena si esta vacio. Un contacto de una empresa
        japonesa recibe su correspondencia en japones aunque alguien le
        hubiera puesto otro idioma a mano.

        La cascada de respaldo de la fuente es
        ``partner.default_get(['lang']).get('lang') or partner.env.lang``, y
        **se porta entera** desde la tarea #113: ``default_get`` ya existe
        (``models.DefaultGetMixin``). La unica pieza adaptada es ``env.lang``,
        que alla es el idioma activo de la peticion; aqui lo lleva Django, con
        ``get_language()`` y el ``LANGUAGE_CODE`` de ``settings`` de respaldo.

        > **Actualizado (tarea #113).** Este parrafo decia que ``default_get``
        > *"no esta portado (sigue entre los ausentes de este archivo)"*, y
        > por eso el cuerpo se saltaba el primer escalon de la cascada.
        """
        fallback = (type(self).default_get(['lang']).get('lang')
                    or get_language() or settings.LANGUAGE_CODE)
        if self.parent_id:
            return self.parent.lang or fallback
        return self.lang or fallback

    def _compute_user_id(self):
        """≙ ``_compute_user_id`` (``odoo19c: res_partner.py:419-423``).

        Docstring de la fuente, verbatim: *"Synchronize sales rep with parent
        if partner is a person"*.

        Tres condiciones, y las tres discriminan: sólo si **no** hay vendedor
        propio (el computo no pisa una reasignacion manual), sólo si el
        partner es una **persona** (una filial es entidad comercial propia y
        lleva el suyo), y sólo si el padre **tiene** uno.

        Devuelve el vendedor que corresponde — el propio cuando no toca
        heredar—, no ``None``, para que el llamador asigne sin guarda.
        """
        if (not self.user_id
                and self._compute_company_type() == 'person'
                and self.parent_id
                and self.parent.user_id):
            return self.parent.user
        return self.user

    def _compute_main_user_id(self):
        """≙ ``_compute_main_user_id`` (``odoo19c: res_partner.py:426-441``).

        De las cuentas que apuntan a este partner, la mas apropiada. **No es
        el vendedor** — ese es ``user``, y son campos distintos que la fuente
        se molesta en desambiguar en un comentario propio.

        Tres reglas, en el orden de la fuente:

        1. **Quien mira gana.** Si el partner es el del usuario en curso, el
           principal es el — antes de ordenar nada.
        2. **Sólo cuentas activas.** Una archivada no puede ser la principal:
           el correo iria a quien ya no esta.
        3. **Interno antes que compartido; entre internos, el mas antiguo.**
           Es lo que dice ``sorted(key=lambda u: (not u.share, -u.id),
           reverse=True)[:1]`` de la fuente, desenvuelto: descendente por
           ``not share`` pone al interno primero, y descendente por ``-id``
           deja arriba el id mas bajo.

        **Divergencia de mecanismo, declarada:** el caso especial de la fuente
        —*"Special case for OdooBot as its user might be archived"*— ancla la
        cuenta raiz por ``xmlid`` (``base.partner_root`` / ``base.user_root``).
        Aqui esos identificadores no estan sembrados (medido: 0 apariciones de
        ``partner_root``); el ancla equivalente es ``SUPERUSER_ID``, el mismo
        que ya usa :meth:`_compute_partner_share`.
        """
        if not self.pk:
            return None
        current = get_current_user()
        if current is not None and getattr(current, 'partner_id', None) == self.pk:
            return current.pk
        active_users = [user for user in self.users.all() if user.active]
        if not active_users:
            root_partner = type(self).objects.filter(
                users__pk=SUPERUSER_ID).values_list('pk', flat=True).first()
            if root_partner == self.pk:
                return SUPERUSER_ID
            return None
        active_users.sort(key=lambda user: (not user.share, -user.pk),
                          reverse=True)
        return active_users[0].pk

    @classmethod
    def _default_category(cls):
        """≙ ``_default_category`` (``odoo19c: res_partner.py:197-198``).

        La categoria inicial la pone quien abre el formulario, por contexto:
        ``self.env['res.partner.category'].browse(self.env.context.get(
        'category_id'))``. ``browse(None)`` es un recordset **vacio**, no el
        conjunto entero — por eso sin clave devuelve nada.

        **Este simbolo estaba declarado como divergencia de mecanismo, y la
        razon que se daba ya no se sostiene.** Decia *"Aqui no hay ``env``"*;
        la bolsa de contexto existe desde que se porto el bloque de
        ``display_name``: ``orm.environments.get_context``, que el propio
        ``_compute_display_name`` de este archivo consulta con cinco claves.
        Estado heredado incorrecto, corregido en el mismo pase (Clausula 2 del
        principio rector).
        """
        category_id = get_context().get('category_id')
        if not category_id:
            return ResPartnerCategory.objects.none()
        return ResPartnerCategory.objects.filter(pk=category_id)

    def _compute_partner_share(self):
        """¿Este partner es un cliente sin acceso, o un usuario compartido?

        ≙ ``_compute_partner_share`` (``:443``):
        ``not partner.user_ids or not any(not user.share for user in
        partner.user_ids)``, con el partner del super-usuario forzado a
        ``False``.

        ``user.share`` todavia no esta portado como campo (tarea **#104**),
        pero su definicion en la fuente es
        ``not user.has_group('base.group_user')`` — lo contrario de interno.
        Aqui eso es ``user._is_internal()`` (``res_users.py:1625``), que SI
        existe. Asi que la expresion se porta sin degradar: «comparte» =
        ningun usuario suyo es interno.
        """
        if self.pk and self.users.filter(pk=SUPERUSER_ID).exists():
            return False
        usuarios = list(self.users.all()) if self.pk else []
        if not usuarios:
            return True
        return not any(user._is_internal() for user in usuarios)

    def _compute_same_vat_partner_id(self):
        """BLOQUEADO por ``EU_EXTRA_VAT_CODES`` — otro partner con el mismo
        identificador fiscal.

        ≙ ``_compute_same_vat_partner_id`` (``:451``). Su cuerpo necesita dos
        piezas que este arbol NO tiene, medidas:

        - ``EU_EXTRA_VAT_CODES`` — la tabla de codigos de IVA europeos que la
          fuente consulta para decidir si el VAT se valida por pais;
        - ``partner.company_id`` — el campo de empresa del partner, que aqui
          no existe todavia (el confinamiento por empresa vive en el
          queryset, no en una FK del partner).

        Devolver ``None`` es la conducta declarada mientras eso siga asi: NO
        es «no hay ningun partner con el mismo VAT», es «no se puede
        responder». Sucesor registrado: tarea **#105**.
        """
        return None

    def _compute_same_company_registry_partner_id(self):
        """BLOQUEADO por ``partner.company_id`` — la fuente resuelve los dos
        en ``_compute_same_vat_partner_id`` (``:451-487``), y la mitad del
        registro mercantil depende de ese campo, que aqui no existe.
        Sucesor: tarea **#105**."""
        return None

    def _get_street_split(self):
        """≙ ``_get_street_split`` (``odoo19c: res_partner.py:331-333``).

        Delega en :func:`tools.misc.street_split`, como la fuente. El
        ``ensure_one()`` de allá no se porta: aquí ``self`` es **una** fila
        por construcción, no un recordset de N.
        """
        return street_split(self.street or '')

    @classmethod
    def _get_default_address_format(cls):
        """≙ ``_get_default_address_format`` (``odoo19c: res_partner.py:1169-1171``).

        La fuente repite el literal aquí y en el ``default`` de
        ``res.country.address_format`` (``odoo19c: res_country.py:52``). Aquí
        la cadena vive **una sola vez**, en ``DEFAULT_ADDRESS_FORMAT``, y los
        dos sitios la leen de ahí: dos copias de la misma plantilla es dos
        sitios donde se puede corregir una y olvidar la otra.
        """
        return DEFAULT_ADDRESS_FORMAT

    def _get_address_format(self):
        """≙ ``_get_address_format`` (``odoo19c: res_partner.py:1173-1175``).

        El país manda; si no hay país —o su plantilla está vacía— cae al
        formato por defecto.
        """
        country_format = self.country.address_format if self.country else ''
        return country_format or self._get_default_address_format()

    def _prepare_display_address(self, without_company=False):
        """≙ ``_prepare_display_address`` (``odoo19c: res_partner.py:1177-1194``).

        Devuelve la pareja ``(plantilla, argumentos)`` que
        :meth:`_display_address` aplica. El ``defaultdict(str)`` es de la
        fuente y es lo que hace que una plantilla de un país que pida un
        campo que aquí no existe rinda cadena vacía en vez de reventar con
        ``KeyError`` — un país mal configurado no debe tumbar una factura.
        """
        address_format = self._get_address_format()
        args = defaultdict(str, {
            'state_code': (self.state.code if self.state else '') or '',
            'state_name': (self.state.name if self.state else '') or '',
            'country_code': (self.country.code if self.country else '') or '',
            'country_name': self._get_country_name(),
            'company_name': self.commercial_company_name or '',
        })
        for field in self._formatting_address_fields():
            args[field] = getattr(self, field) or ''
        if without_company:
            args['company_name'] = ''
        elif self.commercial_company_name:
            address_format = '%(company_name)s\n' + address_format
        return address_format, args

    def _display_address(self, without_company=False):
        """≙ ``_display_address`` (``odoo19c: res_partner.py:1196-1207``).

        Docstring de la fuente, verbatim: *"The purpose of this function is to
        build and return an address formatted accordingly to the standards of
        the country where it belongs."*

        :param without_company: si la dirección lleva la razón social encima.
        :returns: la dirección con las costumbres de su país (o las del
            formato por defecto si no se especificó país).
        """
        address_format, args = self._prepare_display_address(without_company)
        return address_format % args

    @classmethod
    def _display_address_depends(cls):
        """≙ ``_display_address_depends`` (``odoo19c: res_partner.py:1209-1213``).

        Los campos de los que depende :meth:`_display_address`. Allá alimenta
        un ``@api.depends`` de un campo computado y almacenado; aquí
        :attr:`contact_address` es una property que se calcula al leerla, así
        que la lista **no invalida ninguna caché**. Se porta igual porque es
        el punto de extensión: un addon que añada un campo a la dirección lo
        declara aquí, y quien sí guarde el valor —una vista materializada, un
        índice— sabrá qué mirar.
        """
        return cls._formatting_address_fields() + [
            'country', 'company_name', 'state',
        ]

    def _get_country_name(self):
        """≙ ``_get_country_name`` (``odoo19c: res_partner.py:1242-1243``).

        Cadena vacía, nunca ``None``: el valor entra en un ``%(…)s`` y un
        ``None`` se imprimiría literalmente como «None» en la dirección.
        """
        return (self.country.name if self.country else '') or ''

    def _get_all_addr(self):
        """≙ ``_get_all_addr`` (``odoo19c: res_partner.py:1245-1254``).

        La forma que consume el cálculo de impuestos por dirección. La fuente
        devuelve **una** entrada; existe como lista y como punto de extensión
        porque un addon de localización puede tener varias direcciones
        fiscales para el mismo partner.

        El ``ensure_one()`` de la fuente no se porta (``self`` es una fila).
        """
        return [{
            'contact_type': self.street,
            'street': self.street,
            'zip': self.zip,
            'city': self.city,
            'country': self.country.code if self.country else False,
        }]

    @classmethod
    def _get_res_city_by_name(cls, name, country_id):
        """≙ ``_get_res_city_by_name`` (``odoo19c: res_partner.py:1256-1258``).

        Gancho vacío en la fuente (su cuerpo es ``pass``): lo implementa
        ``base_address_city``, que añade el modelo ``res.city``. Se porta con
        el mismo cuerpo para que ese addon tenga qué extender — un gancho
        ausente obliga al addon a declararlo, y entonces dos addons que lo
        necesiten se pisan (el criterio de :ref:`h-api-819`).
        """
        return None

    def address_get(self, adr_pref=None):
        """≙ ``address_get`` (``odoo19c: res_partner.py:1120-1158``).

        Docstring de la fuente, verbatim: *"Find contacts/addresses of the
        right type(s) by doing a depth-first-search through descendants within
        company boundaries (stop at entities flagged ``is_company``) then
        continuing the search at the ancestors that are within the same company
        boundaries. Defaults to partners of type ``'default'`` when the exact
        type is not found, or to the provided partner itself if no type
        ``'default'`` is found either."*

        **Es una búsqueda, no un getter**, y las dos mitades importan:

        - **desciende en profundidad** por los hijos, así que encuentra la
          bodega colgada de una sucursal colgada de la empresa; un
          ``children.filter(type=…)`` plano pasa el caso de un nivel y falla
          en el de tres, que es para el que existe;
        - **no cruza la frontera de otra empresa** (``is_company``): la
          dirección de una filial no es la de su matriz.

        Si tras el descenso no encuentra el tipo y este partner **no** es una
        empresa, sube al padre y repite.

        Divergencias de mecanismo, las tres del mismo origen —aquí ``self`` es
        una fila y no un recordset—: el bucle exterior ``for partner in self``
        se colapsa a una pasada; ``visited`` guarda claves primarias en vez de
        registros (dos instancias distintas de la misma fila no son iguales en
        Django); y el ``fetch`` previo de la fuente —que precarga columnas para
        no pagar N+1— se resuelve con ``select_related`` sobre los hijos.
        """
        adr_pref = set(adr_pref or [])
        if 'contact' not in adr_pref:
            adr_pref.add('contact')
        result = {}
        visited = set()
        current_partner = self
        while current_partner:
            to_scan = [current_partner]
            # Descenso en profundidad
            while to_scan:
                record = to_scan.pop(0)
                visited.add(record.pk)
                if record.type in adr_pref and not result.get(record.type):
                    result[record.type] = record.pk
                if len(result) == len(adr_pref):
                    return result
                children = record.children.select_related('parent').all()
                to_scan = [child for child in children
                           if child.pk not in visited
                           if not child.is_company] + to_scan

            # Sigue por el ancestro si este partner no es entidad comercial
            if current_partner.is_company or not current_partner.parent_id:
                break
            current_partner = current_partner.parent

        # Por defecto el contacto, y si tampoco hay, el propio partner
        default = result.get('contact', self.pk or False)
        for adr_type in adr_pref:
            result[adr_type] = result.get(adr_type) or default
        return result


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

    def _compute_display_name(self):
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

        DIVERGENCIA declarada, la primera: la fuente devuelve
        ``NotImplemented`` para los operadores negados (``not like``), porque
        su dominio no sabe negar un ``child_of``. Aqui se conserva esa
        negativa: un ``not`` sobre la jerarquia pediria el complemento de un
        arbol, que no es lo mismo que negar cada nombre.

        DIVERGENCIA declarada, la segunda — de MECANISMO, no de alcance: la
        fuente expresa la descendencia con ``('id', 'child_of', ids)`` y
        ``_operator_hierarchy`` la traduce. Ese optimizador aun no esta
        portado (tarea **#225**), asi que la descendencia se expresa con el
        arbol materializado que este puerto ya mantiene: ``parent_path``
        empieza por el de cada raiz. Es la misma conducta por el camino que la
        propia fuente deja construido — su ``child_of`` compila a un
        ``parent_path LIKE`` cuando el modelo declara ``_parent_store``.

        Devuelve un ``Domain``, no un ``Q``: asi se compone dentro de un
        ``any`` y lo puede optimizar el resto del arbol.
        """
        if not operator.endswith('like'):
            return Domain('name', '=', value)
        if operator.startswith('not'):
            return NotImplemented
        roots = cls.objects.filter(name__icontains=value)
        domain = Domain('id', 'in', [root.pk for root in roots])
        for path in [root.parent_path for root in roots if root.parent_path]:
            domain |= Domain('parent_path', '=like', f'{path}%')
        return domain
