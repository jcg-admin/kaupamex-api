r"""``res.partner.bank`` — vocabulario EMV Merchant-Presented (≙ ``_inherit``).

Adaptación de Odoo ``account_qr_code_emv/models/res_bank.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3) — atribución y aviso de
licencia preservados (DEC-KX-03).

Portado 1:1 — 5 campos, 14 métodos, cita PROVEN de cada uno
=============================================================

``odoo19c: addons/account_qr_code_emv/models/res_bank.py`` (medido con
``wc -l``: **134 líneas**): **5 campos** (líneas 13-17) y **14 métodos**
(líneas 19-134). Los 19 símbolos están aquí, línea por línea:

===================================  =======================================
Símbolo de la referencia (línea)     Dónde queda en este puerto
===================================  =======================================
``display_qr_setting`` (13)          campo, ``NonStored``
``include_reference`` (14)           campo, ``fields.Boolean``
``proxy_type`` (15)                  campo, ``fields.Selection``
``country_proxy_keys`` (16)          campo, ``NonStored`` vía ``fields.Char``
``proxy_value`` (17)                 campo, ``fields.Char``
``_serialize`` (19-24)               método homónimo
``_remove_accents`` (26-28)          método homónimo — delega en ``strip_accents``
``_compute_country_proxy_keys`` (30-32) → ``compute_country_proxy_keys``
``_compute_display_qr_setting`` (34-37) → ``compute_display_qr_setting``
``_get_crc16`` (39-49)               método homónimo
``_get_merchant_account_info`` (51-52) método homónimo
``_get_additional_data_field`` (54-55) método homónimo
``_get_merchant_category_code`` (57-58) método homónimo
``_get_qr_code_vals_list`` (60-84)   método homónimo
``_get_qr_vals`` (86-95)             método homónimo
``_get_qr_code_generation_params`` (97-107) método homónimo
``_check_for_qr_code_errors`` (109-119) método homónimo
``_get_available_qr_methods`` (121-125) método homónimo
``_get_error_messages_for_qr`` (127-134) método homónimo
===================================  =======================================

Ningún símbolo se omite. Los cinco últimos (los "hooks" que en la referencia
llaman ``super()``) tienen una divergencia de FORMA declarada en el punto 3
de abajo — no de contenido: hacen exactamente lo que la referencia hace
cuando es el ÚNICO addon que provee el mecanismo, que es el caso de este
árbol.

Divergencias declaradas
========================

1. **Sin capa de vistas — ``views/res_bank_views.xml`` no se porta.** Medido:
   ``find src/addons -iname "*.xml" | wc -l`` da **0** en todo el árbol — este
   producto es headless (DRF), no el cliente web de Odoo, y no hay a quién
   dibujarle el ``page`` "EMV QR Settings" ni el widget
   ``dynamic_selection``. Los DOS campos que esa vista consumía
   (``display_qr_setting`` para mostrar/ocultar la página,
   ``country_proxy_keys`` para acotar las opciones del widget) se portan
   igual como datos — no porque un cliente los vaya a pintar, sino porque
   son el contrato que las localizaciones EMV (``l10n_br``, ``l10n_hk``…)
   ``@api.depends``/leen al decidir su propio comportamiento.

2. **``country_code`` no es una columna en este árbol — se navega por la
   FK.** ``base/models/res_partner_bank.py`` (divergencia 3 de ESE archivo)
   ya declara que ``country_code`` es un ``related=`` de la referencia, no
   una columna aquí. Donde la referencia escribe ``self.country_code``, este
   puerto escribe ``self.partner.country.code`` (con guardas ``None``) —
   exactamente la ruta que aquel docstring anticipa.

3. **Los cinco métodos "hook" pliegan el terminal del ``super()`` ausente —
   DESCONOCIDO, con condición de cierre.** En la referencia, ``_get_qr_vals``,
   ``_get_qr_code_generation_params``, ``_check_for_qr_code_errors``,
   ``_get_available_qr_methods`` y ``_get_error_messages_for_qr``
   SOBREESCRIBEN homónimos de ``account/models/res_partner_bank.py``
   (``odoo19c:``, líneas 190-271) vía ``_inherit`` real, con ``super()``.
   Medido: ``find src/addons/account -iname "*partner_bank*"`` da **0** —
   ese archivo no existe en este árbol, así que no hay a qué encadenar.

   Los cinco terminan exactamente donde el ``super()`` de la referencia
   termina cuando NINGÚN otro addon instalado provee el método (que es
   nuestro caso, medido) — citado método por método:

   - ``_get_qr_vals`` → ``None`` (``odoo19c: res_partner_bank.py:190-191``).
   - ``_get_qr_code_generation_params`` → ``NotImplementedError()``
     (``:193-194``).
   - ``_get_available_qr_methods`` → ``[]`` (``:234-243``).
   - ``_check_for_qr_code_errors`` → ``None`` (``:264-271``).
   - ``_get_error_messages_for_qr`` → ``None`` (``:253-262``).

   Esto hace que el puente funcione standalone — no es una invención: es el
   comportamiento REAL del ``super()`` en el único escenario que este árbol
   tiene hoy. **DESCONOCIDO — condición de cierre:** cuando
   ``account/models/res_partner_bank.py`` porte el mecanismo base con
   recordset multi-método (``_build_qr_code_vals``, ``build_qr_code_url``,
   ``get_available_qr_methods_in_sequence``…), estos cinco deben
   reconciliarse contra el registro real en vez del terminal fijo —
   probablemente cambiando ``depends`` a incluir ``account`` y encadenando
   por ``hasattr``/registro en vez de retornar el literal. Este agente tiene
   prohibido escribir fuera de ``account_qr_code_emv/`` (no puede tocar
   ``account/`` para cerrarlo ni registrar el hallazgo en ``docs``) — queda
   para el orquestador.

4. **Migración pendiente — fuera del alcance de este addon.** Los tres campos
   ALMACENADOS (``include_reference``, ``proxy_type``, ``proxy_value``) son
   columnas nuevas sobre ``res_partner_bank``, tabla del app ``base`` (Django
   exige que la migración que agrega una columna viva en el app dueño del
   modelo — mismo criterio que ``base/migrations/
   0015_resbank_l10n_mx_edi_code_and_more.py`` para los dos campos que
   ``l10n_mx`` cuelga sobre este mismo modelo). Este agente tiene prohibido
   escribir fuera de ``account_qr_code_emv/`` y sus tests — la migración en
   ``base/migrations/`` y el alta de ``'addons.account_qr_code_emv'`` en
   ``INSTALLED_APPS`` (``config/settings/base.py``) quedan pendientes del
   orquestador. Sin ellas, ``AccountQrCodeEmvConfig.ready()`` no se dispara
   automáticamente — los tests de este addon llaman
   ``apply_account_qr_code_emv_extensions()`` explícitamente (idempotente,
   ver abajo) para no depender de ese wiring.

5. **``strip_accents``/``_add_if_absent`` se duplican, no se importan.**
   Mismo criterio que ``addons/mail/models/mail_alias.py`` (``remove_accents``,
   NFKD verbatim) y que CADA addon que cuelga campos
   (``account/models/{product,res_company,res_currency}.py``,
   ``l10n_mx/models/res_bank.py``): un helper de ~10 líneas se reimplica en
   el addon que lo necesita en vez de importarlo cruzado — este addon
   declara ``depends: ['base']``, no ``mail`` ni ningún otro addon con una
   copia ya escrita.
"""
import re
import unicodedata

import fields
from addons.base.models.res_partner_bank import ResPartnerBank
from orm.method_chain import chain_method, extend_list
from tools.translate import _

from ..const import CURRENCY_MAPPING


def _add_if_absent(model, name, field):
    """Cuelga ``field`` sólo si ``model`` no lo tiene ya (campo CON columna).

    Idéntico al de ``account``/``l10n_mx``: ``ready()`` puede correr más de
    una vez en el mismo proceso (recarga del autoreloader), y
    ``add_to_class`` sobre un campo ya existente rompe con ``FieldError``.
    """
    if not any(f.name == name for f in model._meta.get_fields()):
        model.add_to_class(name, field)


def strip_accents(input_str):
    """Quita los diacríticos de ``input_str`` (NFKD + descarte combinante).

    Odoo lo importa de ``odoo.tools.misc.remove_accents``; aquí se porta
    como función de módulo — mismo criterio y misma implementación que
    ``addons/mail/models/mail_alias.py::remove_accents`` (no se importa
    cruzado: este addon no depende de ``mail``).
    """
    if not input_str:
        return input_str
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    return ''.join(c for c in nkfd_form if not unicodedata.combining(c))


# -- las 14 funciones del archivo — se cuelgan por nombre en
#    apply_account_qr_code_emv_extensions() -----------------------------


def compute_display_qr_setting(self):
    """≙ ``_compute_display_qr_setting`` (``odoo19c: res_bank.py:34-37``).

    Constante ``False`` en el puente: cada localización que quiera mostrar
    su sección de ajustes EMV sobreescribe este cómputo (o el campo
    directamente). ``@api.depends('country_code') @api.depends_context
    ('company')`` de la referencia no tiene análogo — este campo es
    ``NonStored``, se recalcula en cada lectura, no hay caché que invalidar.
    """
    return False


def compute_country_proxy_keys(self):
    """≙ ``_compute_country_proxy_keys`` (``odoo19c: res_bank.py:30-32``).

    Constante ``''`` en el puente — mismo criterio que
    ``compute_display_qr_setting``.
    """
    return ''


def _serialize(self, header, value):
    """≙ ``_serialize`` — el campo TLV EMV: ``<tag 2><len 2><valor>``.

    ``@api.model`` en la referencia: no usa ``self`` salvo para el binding.
    Un ``value`` ausente (``None`` o cadena vacía) serializa a ``''`` — así
    es como ``(tag, merchant_account_info)`` con ambos ``None`` (el caso
    base, sin localización) no rompe la cadena.
    """
    if value is not None and value != '':
        return f'{header:02}{len(str(value)):02}{value}'
    return ''


def _remove_accents(self, string):
    """≙ ``_remove_accents`` (``odoo19c: res_bank.py:26-28``).

    NFKD (vía ``strip_accents``) más las dos sustituciones que el vietnamita
    necesita: ``đ``/``Đ`` no son letras con diacrítico combinante — son
    letras propias del alfabeto, así que NFKD no las toca y hace falta el
    reemplazo explícito.
    """
    return strip_accents(string).replace('đ', 'd').replace('Đ', 'D')


def _get_crc16(self, data, poly=0x1021, init=0xFFFF):
    """CRC16/CCITT-FALSE — ≙ ``_get_crc16`` (``odoo19c: res_bank.py:39-49``).

    Verbatim, incluido el ``__`` del bucle interno (en vez de ``_``): la
    referencia lo hace a propósito para no ensombrecer ``_`` (traducción),
    y este puerto conserva la misma razón — importa ``_`` de
    ``tools.translate`` para los mensajes de error de abajo.
    """
    crc = init
    for byte in data:
        crc = crc ^ (byte << 8)
        for __ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc = crc << 1
    return crc & 0xFFFF


def _get_merchant_account_info(self):
    """≙ ``_get_merchant_account_info`` (``odoo19c: res_bank.py:51-52``).

    Hook de extensión: el puente no resuelve ningún país, así que no hay ni
    tag EMV ni payload que ofrecer. Cada localización sobreescribe este
    método devolviendo ``(tag, payload)`` — p. ej. ``l10n_br`` lo resuelve
    con el payload Pix; ``l10n_sg`` con PayNow.
    """
    return None, None


def _get_additional_data_field(self, comment):
    """≙ ``_get_additional_data_field`` (``odoo19c: res_bank.py:54-55``).

    Hook de extensión — la referencia y su campo 62 (Additional Data Field,
    con la referencia/comunicación) sólo tiene sentido por país; el puente
    lo deja en ``None`` aun cuando ``include_reference`` esté activo (ver
    ``_get_qr_code_vals_list``: la condición se evalúa, pero mientras nadie
    sobreescriba este hook el resultado sigue siendo ``None``).
    """
    return None


def _get_merchant_category_code(self):
    """≙ ``_get_merchant_category_code`` (``odoo19c: res_bank.py:57-58``).

    ``'0000'`` — categoría MCC genérica ("miscellaneous"), el valor que la
    referencia usa cuando ninguna localización especializa el rubro.
    """
    return '0000'


def _get_qr_code_vals_list(self, qr_method, amount, currency, debtor_partner,
                            free_communication, structured_communication):
    """≙ ``_get_qr_code_vals_list`` (``odoo19c: res_bank.py:60-84``).

    Arma los 10 campos EMV como pares ``(tag, valor)`` — ``_get_qr_vals`` los
    serializa después con ``_serialize``. La navegación ``self.partner.*``
    en vez de ``self.partner_id.*`` es sólo el nombre de campo de este ORM
    (sin sufijo ``_id`` — ``base/models/res_partner_bank.py``); el campo 58
    (``country_code``) usa la ruta ``self.partner.country.code`` por la
    divergencia 2 de este archivo.
    """
    tag, merchant_account_info = self._get_merchant_account_info()
    currency_code = CURRENCY_MAPPING[currency.name]
    if not currency.is_zero(amount):
        # ``amount.is_integer()`` (la referencia) asume ``float``. Este
        # árbol pasa dinero como ``Decimal`` (convención del proyecto —
        # ``base/models/res_currency.py::round`` lo exige), y
        # ``Decimal.is_integer()`` no existe en Python 3.12 (medido:
        # ``.venv/bin/python3 -c "from decimal import Decimal;
        # Decimal(1).is_integer()"`` → ``AttributeError`` en 3.12.3, el
        # intérprete fijado por este repo). ``% 1 == 0`` es el mismo
        # predicado y funciona igual en ``float`` y en ``Decimal`` sin
        # depender de esa versión — mismo resultado que la referencia
        # para todo valor que esta pueda recibir.
        amount = int(amount) if amount % 1 == 0 else amount
    else:
        amount = None
    # ``getattr(self, 'partner', None)`` y no ``self.partner`` desnudo:
    # cuando la FK está vacía, el descriptor de Django levanta
    # ``RelatedObjectDoesNotExist`` en vez de devolver ``None`` (medido:
    # ``ResPartnerBank().partner`` → la excepción, no un valor falsy). Esa
    # excepción SÍ hereda de ``AttributeError`` (medido: ``.__mro__``), que
    # es precisamente lo que hace que ``getattr(..., None)`` la trague — es
    # el mecanismo real de Django para este caso, no un truco. La
    # referencia no necesita esto: un recordset vacío (``self.partner_id``
    # ahí) es falsy por sí solo, sin excepción que atrapar.
    partner = getattr(self, 'partner', None)
    partner_country = getattr(partner, 'country', None) if partner else None
    merchant_name = (
        partner and partner.name
        and self._remove_accents(partner.name)[:25]
    ) or 'NA'
    merchant_city = (
        partner and partner.city
        and self._remove_accents(partner.city)[:15]
    ) or ''
    comment = structured_communication or free_communication or ''
    comment = re.sub(
        r'[^ A-Za-z0-9_@.\\/#&+-]+', '', self._remove_accents(comment))
    additional_data_field = (
        self._get_additional_data_field(comment)
        if self.include_reference else None
    )
    merchant_category_code = self._get_merchant_category_code()
    country_code = partner_country.code if partner_country else None
    return [
        (0, '01'),                                 # Payload Format Indicator
        (1, '12'),                                 # Dynamic QR Codes
        (tag, merchant_account_info),              # Merchant Account Information
        (52, merchant_category_code),              # Merchant Category Code
        (53, currency_code),                       # Transaction Currency
        (54, amount),                               # Transaction Amount
        (58, country_code),                          # Country Code
        (59, merchant_name),                        # Merchant Name
        (60, merchant_city),                        # Merchant City
        (62, additional_data_field),                # Additional Data Field
    ]


def _get_qr_vals(self, qr_method, amount, currency, debtor_partner,
                  free_communication, structured_communication):
    """≙ ``_get_qr_vals`` (``odoo19c: res_bank.py:86-95``).

    Para ``'emv_qr'``: serializa los campos TLV, cierra con ``'6304'`` (tag
    63, longitud 04 — el propio campo CRC anuncia su longitud) y el CRC16
    en hex mayúsculas de 4 dígitos. Para cualquier otro método: ``None`` —
    el terminal del ``super()`` (divergencia 3, no ``account`` en este
    árbol).
    """
    if qr_method == 'emv_qr':
        qr_code_vals = self._get_qr_code_vals_list(
            qr_method, amount, currency, debtor_partner,
            free_communication, structured_communication)
        qr_code_str = ''.join(self._serialize(*val) for val in qr_code_vals)
        qr_code_str += '6304'
        crc = self._get_crc16(bytes(qr_code_str, 'utf-8'))
        qr_code_str += format(crc, '04x').upper()
        return qr_code_str

    return None


def _get_qr_code_generation_params(self, qr_method, amount, currency,
                                    debtor_partner, free_communication,
                                    structured_communication):
    """≙ ``_get_qr_code_generation_params`` (``odoo19c: res_bank.py:97-107``).

    Los parámetros que un generador de barcode (``ir.actions.report.barcode``
    en la referencia — no portado, capa de reporting PDF fuera de alcance de
    este addon) necesita para dibujar el QR. Para cualquier método distinto
    de ``'emv_qr'``: ``None``, que delega en el eslabón anterior de la cadena
    — ≙ el ``return super()._get_qr_code_generation_params(...)`` de la
    referencia. El terminal que alza ``NotImplementedError`` vive en
    ``account/models/res_partner_bank.py``. Ver :ref:`h-api-364`.
    """
    if qr_method == 'emv_qr':
        return {
            'barcode_type': 'QR',
            'quiet': 0,
            'width': 128,
            'height': 128,
            'humanreadable': 1,
            'value': self._get_qr_vals(
                qr_method, amount, currency, debtor_partner,
                free_communication, structured_communication),
        }
    return None


def _check_for_qr_code_errors(self, qr_method, amount, currency,
                               debtor_partner, free_communication,
                               structured_communication):
    """≙ ``_check_for_qr_code_errors`` (``odoo19c: res_bank.py:109-119``).

    El primer chequeo (``_get_merchant_account_info()`` faltante) NUNCA
    dispara en el puente puro: el hook base devuelve ``(None, None)``, una
    tupla de longitud 2 — truthy en Python aunque sus dos elementos sean
    ``None``. Es el comportamiento REAL de la referencia (no un bug de este
    puerto): sólo se activa cuando una localización sobreescribe el hook
    devolviendo algo falsy explícitamente.
    """
    if qr_method == 'emv_qr':
        if not self._get_merchant_account_info():
            return _('Falta la información de cuenta del comercio.')
        # ``getattr(self, 'partner', None)`` — mismo motivo que
        # ``_get_qr_code_vals_list``: la FK vacía levanta
        # ``RelatedObjectDoesNotExist`` en vez de ser falsy.
        partner = getattr(self, 'partner', None)
        if not (partner and partner.city):
            return _('Falta la ciudad del comercio.')
        if not self.proxy_type:
            return _('Falta el tipo de proxy.')
        if not self.proxy_value:
            return _('Falta el valor del proxy.')
    return None


def _get_available_qr_methods(self):
    """≙ ``_get_available_qr_methods`` (``odoo19c: res_bank.py:121-125``).

    ``@api.model`` en la referencia — no necesita ``self`` con datos, sólo
    el binding. El terminal del ``super()`` ausente es ``[]`` (divergencia
    3), así que la lista resultante es sólo la entrada de este puente.
    """
    result = []
    result.append((
        'emv_qr',
        _('Código QR EMV presentado por el comercio'),
        30,
    ))
    return result


def _get_error_messages_for_qr(self, qr_method, debtor_partner, currency):
    """≙ ``_get_error_messages_for_qr`` (``odoo19c: res_bank.py:127-134``).

    Para ``'emv_qr'`` SIEMPRE devuelve un mensaje (nunca ``None``) salvo que
    una localización sobreescriba este método — es la forma en que el
    puente se anuncia disponible (``_get_available_qr_methods``) sin nunca
    ser elegible por sí solo.

    ``if self is None`` traduce el ``if not self:`` de la referencia (ahí,
    "recordset vacío" — ningún ``res.partner.bank`` elegido). En este ORM
    un método de instancia siempre recibe un ``self`` real (no hay
    recordsets vacíos que invocar un método), así que la rama es código
    muerto bajo la convención de llamada de Django — se conserva por
    fidelidad al símbolo, no porque se alcance en este árbol.
    """
    if qr_method == 'emv_qr':
        if self is None:
            return _(
                'Se requiere una cuenta bancaria para generar el código '
                'QR EMV.')
        return _(
            'No hay código QR EMV disponible para el país de la cuenta '
            '%(account_number)s.') % {'account_number': self.acc_number}

    return None


def apply_account_qr_code_emv_extensions():
    """≙ ``_inherit = 'res.partner.bank'`` de ``account_qr_code_emv``.

    Se llama desde ``AccountQrCodeEmvConfig.ready()``, no al importar: en
    tiempo de import el registro de modelos aún no está poblado.

    Idempotente en las dos formas que el árbol ya usa: ``_add_if_absent``
    (campos CON columna, ``_meta.get_fields()``) y ``hasattr`` (campos
    ``NonStored`` — no aparecen en ``_meta``, así que ``_add_if_absent`` los
    volvería a agregar en cada llamada; mismo criterio que
    ``fiscal_country_codes`` en ``account/models/res_company.py``).
    """
    # -- los dos campos NonStored (sin columna) --------------------------
    if not hasattr(ResPartnerBank, 'display_qr_setting'):
        ResPartnerBank.add_to_class('display_qr_setting', fields.NonStored(
            default=compute_display_qr_setting,
            help_text='Visibilidad de la sección de ajustes EMV (Odoo '
                      'display_qr_setting, compute, store=False). '
                      'Constante False en el puente: cada localización que '
                      'active su método EMV decide cuándo mostrarla.',
        ))
    if not hasattr(ResPartnerBank, 'country_proxy_keys'):
        ResPartnerBank.add_to_class('country_proxy_keys', fields.Char(
            store=False, default=compute_country_proxy_keys,
            help_text='Claves de proxy válidas para el país de la cuenta '
                      '(Odoo country_proxy_keys, compute, store=False). '
                      'Cadena vacía en el puente.',
        ))

    # -- los tres campos CON columna (migración pendiente — divergencia 4) --
    _add_if_absent(ResPartnerBank, 'include_reference', fields.Boolean(
        default=False,
        help_text='Incluye la referencia/comunicación en el código QR '
                  '(Odoo include_reference). Sin efecto en el puente puro: '
                  '``_get_additional_data_field`` sigue devolviendo None '
                  'hasta que una localización lo sobreescriba.',
    ))
    _add_if_absent(ResPartnerBank, 'proxy_type', fields.Selection(
        max_length=32, choices=[('none', 'Ninguno')], default='none',
        help_text='Tipo de proxy del método EMV activo (Odoo proxy_type). '
                  'El único valor del puente es "none" — cada localización '
                  'agrega los suyos (teléfono, CLABE, RFC…).',
    ))
    _add_if_absent(ResPartnerBank, 'proxy_value', fields.Char(
        max_length=255, blank=True, default='',
        help_text='Valor del proxy (teléfono, CLABE, RFC…) que el método '
                  'EMV activo usa (Odoo proxy_value).',
    ))

    # -- los 14 métodos — se ENCADENAN sobre lo que ya hubiera -------------
    # NO ``if not hasattr(...)``: esa guarda es correcta para campos (no
    # duplicar columna) y catastrófica para overrides. ``account_qr_code_sepa``
    # extiende los mismos cinco hooks; con la guarda, el primero en
    # INSTALLED_APPS ganaba y el segundo no se instalaba nunca
    # (:ref:`h-api-364`). ``chain_method`` es el ``super()`` que este idioma
    # no tiene — ver ``orm/method_chain.py``.
    for nombre, funcion in (
        ('_serialize', _serialize),
        ('_remove_accents', _remove_accents),
        ('_get_crc16', _get_crc16),
        ('_get_merchant_account_info', _get_merchant_account_info),
        ('_get_additional_data_field', _get_additional_data_field),
        ('_get_merchant_category_code', _get_merchant_category_code),
        ('_get_qr_code_vals_list', _get_qr_code_vals_list),
        ('_get_qr_vals', _get_qr_vals),
        ('_get_qr_code_generation_params', _get_qr_code_generation_params),
        ('_check_for_qr_code_errors', _check_for_qr_code_errors),
        ('_get_error_messages_for_qr', _get_error_messages_for_qr),
    ):
        chain_method(ResPartnerBank, nombre, funcion)

    # ``_get_available_qr_methods`` ACUMULA en vez de relevar: la referencia
    # hace ``rslt = super()._get_available_qr_methods(); rslt.append(...)``
    # (``odoo19c: res_bank.py:121-125``), así que cada addon suma su método
    # en vez de reemplazar la lista.
    chain_method(ResPartnerBank, '_get_available_qr_methods',
                 _get_available_qr_methods, combine=extend_list)
