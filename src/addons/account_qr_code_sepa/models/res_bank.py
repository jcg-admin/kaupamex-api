r"""``res.partner.bank`` — lo que ``account_qr_code_sepa`` le cuelga (≙ ``_inherit``).

Adaptación de Odoo ``account_qr_code_sepa/models/res_bank.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``,
LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

Cinco métodos, cero campos: qué se porta
=========================================

La referencia reabre ``res.partner.bank`` (ya en ``base.ResPartnerBank``, sin
declarar ningún campo nuevo) y le cuelga cinco métodos — los cinco se portan
íntegros:

===============================  ==============================================
Método                            Qué hace
===============================  ==============================================
``_get_qr_vals``                  Arma la lista de 12 valores del formato EPC
                                   (``BCD``/versión/charset/``SCT``/BIC/
                                   titular/IBAN/divisa+monto/vacío/
                                   comunicación estructurada/comunicación
                                   libre/vacío) cuando ``qr_method == 'sct_qr'``.
``_get_qr_code_generation_params``Envuelve lo anterior en los parámetros de
                                   generación de barcode (``barcode_type``,
                                   ``width``/``height``, ``value``).
``_get_error_messages_for_qr``    Rechaza el método ``sct_qr`` si la divisa no
                                   es EUR, el tipo de cuenta no es IBAN, o el
                                   IBAN no es de la zona SEPA (excluyendo los
                                   territorios sin código IBAN propio).
``_check_for_qr_code_errors``     Rechaza si no hay titular (ni propio ni del
                                   partner).
``_get_available_qr_methods``     Registra ``sct_qr`` con secuencia 20.
===============================  ==============================================

El mecanismo de porte — monkeypatch, no ``super()``
=====================================================

Este ORM es Django puro (``import fields``/``import models`` en
``base.ResPartnerBank`` son alias del vocabulario Odoo sobre
``django.db.models`` — ver el docstring de ``orm/models.py``): no tiene el
registro dinámico de clases de Odoo que fusiona ``_inherit`` en una MRO real.
El patrón que este árbol ya usa para "una clase reabre a otra sin declarar
campos" es el de ``account/models/res_company.py``: funciones a nivel de
módulo colgadas con ``setattr(Modelo, nombre, funcion) if not
hasattr(Modelo, nombre)`` desde ``AppConfig.ready()`` — aplicado aquí
literalmente igual, sin campos de por medio.

Divergencias declaradas
========================

1. **El ``super()`` de la referencia no tiene contraparte real.** Cada uno de
   los cinco métodos de la referencia empieza con ``if qr_method == 'sct_qr':
   ...; return super()...`` — el ``super()`` encadena con
   ``account/models/res_partner_bank.py``, que declara los defaults base
   (``_get_qr_vals`` → ``None``; ``_get_qr_code_generation_params`` → alza
   ``NotImplementedError()``; ``_get_error_messages_for_qr`` → ``None``;
   ``_check_for_qr_code_errors`` → ``None``; ``_get_available_qr_methods`` →
   ``[]``). Ese archivo **no existe en este árbol** (medido: ``find
   src/addons/account -iname "*partner_bank*"`` → 0 hits; mismo hallazgo que
   ``account_qr_code_emv`` ya documentó para su propio puente). Cada método
   de aquí reproduce el default base **directamente** en la rama
   ``qr_method != 'sct_qr'`` en vez de encadenar un ``super()`` que no
   existe — el resultado observable es idéntico al de la referencia
   (``super()`` con la cadena vacía **es** ese default), y no hay ningún otro
   addon en este árbol que contribuya a estos hooks todavía.

   **Condición de cierre:** cuando ``account/models/res_partner_bank.py`` se
   porte con ``_build_qr_code_vals``/``get_available_qr_methods_in_sequence``
   (el orquestador que de verdad recorre los métodos registrados), este
   archivo debe re-cablearse para que sus cinco funciones cooperen con ese
   dispatcher real (probablemente colgándose sólo si ``not hasattr`` sobre un
   default ya presente, en vez de definir el default ellas mismas). Hasta
   entonces, ``_get_qr_vals``/etc. son invocables directamente sobre una
   instancia de ``ResPartnerBank`` — igual que el propio test de la
   referencia los invoca (``self.acc_sepa_iban._get_qr_vals(...)``) — pero no
   hay un ``_build_qr_code_vals`` que los orqueste automáticamente desde
   ``account.move``.

2. **``self.bank_bic``** en la referencia es un ``related='bank_id.bic'``
   declarado por ``account/models/res_partner_bank.py`` (otro campo de ese
   mismo archivo no portado). Aquí se navega la FK directamente:
   ``self.bank.bic if self.bank_id else ''`` — mismo criterio que
   ``base/models/res_partner_bank.py`` ya fija en su divergencia 3
   (``bank_name``/``bank_bic``/``country_code`` no se portan como columna,
   se navegan por la FK).

3. **``is_valid_structured_reference``/``sanitize_structured_reference``** y
   el código de países de la zona SEPA se importan de ``tools.py``, vendor
   local de ese subconjunto — ver su docstring para la medición completa y
   la condición de cierre.

4. **``float_repr(currency.round(amount), currency.decimal_places)``** no se
   porta como llamada: ``base.ResCurrency.round(amount)`` (ya portado) hace
   MÁS que su homónimo Odoo — devuelve un ``Decimal`` ya cuantizado a
   ``decimal_places`` (``base/models/res_currency.py``, docstring de
   ``round()``: "se normaliza la escala del resultado a ``decimal_places``").
   ``str()`` sobre ese ``Decimal`` produce el mismo string de salida que
   ``float_repr`` sobre el ``float`` de la referencia (verificado:
   ``str(currency.round(100.0))`` con ``rounding=0.01``/``decimal_places=2``
   da ``'100.00'``, igual que el vector del test de la referencia). No hace
   falta vendorizar ``tools.float_utils.float_repr`` (excluido allí por
   DEC-AF-03, "sin consumidor" — ahora tendría uno, pero ese archivo está
   fuera de este alcance) porque el propio ``round()`` ya resuelve el
   formato.
"""
from addons.account_qr_code_sepa.tools import (
    SEPA_ZONE_COUNTRY_CODES,
    is_valid_structured_reference,
    sanitize_structured_reference,
)
from addons.base.models.res_partner_bank import ResPartnerBank
from orm.method_chain import chain_method, extend_list
from tools.translate import _

#: Territorios de la zona SEPA cuyo código IBAN de país difiere de su propio
#: código ISO — ≙ el comentario de la referencia: "Some countries share the
#: same IBAN country code (e.g. Åland Islands and Finland IBANs are 'FI', but
#: Åland Islands' code is 'AX')". Literal de ``odoo19c: account_qr_code_sepa/
#: models/res_bank.py`` (parte del archivo que SÍ se porta, no un vendor).
_NON_IBAN_SEPA_CODES = frozenset({
    'AX', 'NC', 'YT', 'TF', 'BL', 'RE', 'MF', 'GP', 'PM', 'PF', 'GF', 'MQ',
    'JE', 'GG', 'IM',
})


def _get_qr_vals(self, qr_method, amount, currency, debtor_partner,
                  free_communication, structured_communication):
    """Los 12 valores del código QR EPC (formato SEPA Credit Transfer) — ≙
    ``odoo19c: account_qr_code_sepa/models/res_bank.py:11-36``.
    """
    if qr_method != 'sct_qr':
        # ≙ el default de ``account/models/res_partner_bank.py`` — ver
        # divergencia 1 del docstring del módulo.
        return None

    if structured_communication and is_valid_structured_reference(
            structured_communication):
        structured_communication = sanitize_structured_reference(
            structured_communication)
        comment = ''
    else:
        structured_communication = ''
        comment = free_communication or ''

    formatted_amount = str(currency.round(amount))
    holder_name = self.acc_holder_name or self.partner.name
    return [
        'BCD',                                                  # Service Tag
        '002',                                                  # Version
        '1',                                                    # Character Set
        'SCT',                                                  # Identification Code
        self.bank.bic if self.bank_id else '',                  # BIC of the Beneficiary Bank
        (holder_name or '')[:71],                                # Name of the Beneficiary
        self.sanitized_acc_number,                              # Account Number of the Beneficiary
        currency.name + formatted_amount,                       # Currency + Amount of the Transfer in EUR
        '',                                                     # Purpose of the Transfer
        structured_communication,                               # Remittance Information (Structured)
        comment[:141],                                          # Remittance Information (Unstructured)
        '',                                                     # Beneficiary to Originator Information
    ]


def _get_qr_code_generation_params(self, qr_method, amount, currency,
                                    debtor_partner, free_communication,
                                    structured_communication):
    """Parámetros de generación del barcode QR — ≙
    ``odoo19c: account_qr_code_sepa/models/res_bank.py:38-48``.
    """
    if qr_method != 'sct_qr':
        # ``None`` delega en el eslabón anterior de la cadena — ≙ el
        # ``return super()._get_qr_code_generation_params(...)`` de la
        # referencia. El ``NotImplementedError()`` es del **terminal**
        # (``account/models/res_partner_bank.py``), no de un eslabón
        # intermedio: alzarlo aquí impedía que ``account_qr_code_emv``
        # atendiera lo suyo. Ver :ref:`h-api-364`.
        return None
    return {
        'barcode_type': 'QR',
        'quiet': 0,
        'width': 128,
        'height': 128,
        'humanreadable': 1,
        'value': '\n'.join(_get_qr_vals(
            self, qr_method, amount, currency, debtor_partner,
            free_communication, structured_communication)),
    }


def _get_error_messages_for_qr(self, qr_method, debtor_partner, currency):
    """¿Es elegible ``sct_qr`` para esta cuenta/divisa? — ≙
    ``odoo19c: account_qr_code_sepa/models/res_bank.py:50-67``.

    Tres condiciones, cualquiera basta para rechazar: divisa distinta de EUR,
    tipo de cuenta distinto de IBAN, o IBAN fuera de la zona SEPA (excluyendo
    los territorios que comparten código IBAN con otro país de la lista).

    **Observación sobre el segundo check.** ``self.acc_type`` en este árbol
    es siempre ``'bank'`` hasta que ``base_iban`` (no portado, Ola 0 · T-06)
    detecte IBANs — ``base/models/res_partner_bank.py``, divergencia 2. En
    consecuencia, **toda** cuenta rechaza aquí por este check mientras
    ``base_iban`` no exista; no es un defecto de este archivo, es el estado
    conocido de la infraestructura de la que depende.
    """
    if qr_method != 'sct_qr':
        return None

    sepa_iban_codes = SEPA_ZONE_COUNTRY_CODES - _NON_IBAN_SEPA_CODES
    error_messages = []
    if currency.name != 'EUR':
        error_messages.append(
            _("Can't generate a SEPA QR Code with the %s currency.")
            % currency.name)
    if self.acc_type != 'iban':
        error_messages.append(
            _("Can't generate a SEPA QR code if the account type isn't IBAN."))
    if not (self.sanitized_acc_number
            and self.sanitized_acc_number[:2] in sepa_iban_codes):
        error_messages.append(
            _("Can't generate a SEPA QR code with a non SEPA iban."))
    if error_messages:
        return '\r\n'.join(str(message) for message in error_messages)
    return None


def _check_for_qr_code_errors(self, qr_method, amount, currency,
                               debtor_partner, free_communication,
                               structured_communication):
    """Consistencia de datos previa a generar — ≙
    ``odoo19c: account_qr_code_sepa/models/res_bank.py:69-74``.
    """
    if qr_method != 'sct_qr':
        return None
    if not self.acc_holder_name and not self.partner.name:
        return _(
            'The account receiving the payment must have an account '
            'holder name or partner name set.')
    return None


def _get_available_qr_methods(self):
    """Registra ``sct_qr`` (secuencia 20) — ≙
    ``odoo19c: account_qr_code_sepa/models/res_bank.py:76-80``.

    La referencia hace ``rslt = super()._get_available_qr_methods();
    rslt.append(...); return rslt`` — encadenando sobre el default base
    (``[]``). Como ese default no tiene contraparte real aquí (divergencia
    1) y ningún otro addon de este árbol contribuye a este hook todavía,
    ``[] + [('sct_qr', ..., 20)]`` y este cuerpo producen el mismo resultado
    observable.
    """
    return [('sct_qr', _('SEPA Credit Transfer QR'), 20)]


def apply_account_qr_code_sepa_extensions():
    """≙ ``_inherit = 'res.partner.bank'`` de ``account_qr_code_sepa``
    (``odoo19c: account_qr_code_sepa/models/res_bank.py``).

    Se llama desde ``AccountQrCodeSepaConfig.ready()``, no al importar: en
    tiempo de import el registro de modelos aún no está poblado.
    """
    # Se ENCADENA, no se instala "sólo si falta". ``account_qr_code_emv``
    # extiende los mismos cinco hooks de este modelo: con la guarda
    # ``if not hasattr(...)`` ganaba el primero en INSTALLED_APPS y los cinco
    # métodos de este addon no se instalaban nunca (:ref:`h-api-364`).
    # ``chain_method`` es el ``super()`` que el idioma de ``setattr`` no
    # tiene — ver ``orm/method_chain.py``.
    for nombre, funcion in (
        ('_get_qr_vals', _get_qr_vals),
        ('_get_qr_code_generation_params', _get_qr_code_generation_params),
        ('_get_error_messages_for_qr', _get_error_messages_for_qr),
        ('_check_for_qr_code_errors', _check_for_qr_code_errors),
    ):
        chain_method(ResPartnerBank, nombre, funcion)

    # ``_get_available_qr_methods`` ACUMULA: la referencia hace
    # ``rslt = super()._get_available_qr_methods(); rslt.append(...)``
    # (``odoo19c: account_qr_code_sepa/models/res_bank.py:76-80``), así que
    # cada addon suma su método en vez de reemplazar la lista.
    chain_method(ResPartnerBank, '_get_available_qr_methods',
                 _get_available_qr_methods, combine=extend_list)
