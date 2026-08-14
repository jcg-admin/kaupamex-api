"""``res.partner.bank`` extendido por ``account`` — el orquestador del QR de pago.

Adaptación de Odoo ``addons/account/models/res_partner_bank.py`` (bloque QR,
odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03).

Qué es este archivo
===================

La referencia declara aquí **el terminal** de cinco puntos de extensión que los
satélites ``account_qr_code_*`` sobreescriben. Sin ese terminal el mecanismo no
existe: cada satélite atiende *su* método de QR y delega el resto en
``super()``, y ese ``super()`` **es** lo que hay abajo. Un satélite instalado
sobre un modelo sin terminal es una cadena sin fondo.

Aquí es la parte de la Ola B que ``account_qr_code_{sepa,emv}`` necesitaba y que
no se portó con ellos: los satélites entraron declarando su propio
``NotImplementedError`` como si fueran el fondo de la cadena. No lo son — y con
dos satélites instalados, el que va primero decidía por el otro. Ver
:ref:`h-api-364`.

Los once símbolos del bloque QR de la referencia
=================================================

Se portan **diez**; el ausente se declara con su medición:

============================================  ==========================================
Símbolo                                       Estado
============================================  ==========================================
``_build_qr_code_vals``                       portado
``build_qr_code_url``                         portado
``build_qr_code_base64``                      portado
``_get_qr_vals``                              portado (terminal: ``None``)
``_get_qr_code_generation_params``            portado (terminal: ``NotImplementedError``)
``_get_qr_code_url``                          portado (``urlencode`` de la stdlib)
``_get_qr_code_base64``                       **bloqueado** — ver abajo
``_get_available_qr_methods``                 portado (terminal: ``[]``)
``get_available_qr_methods_in_sequence``      portado
``_get_error_messages_for_qr``                portado (terminal: ``None``)
``_check_for_qr_code_errors``                 portado (terminal: ``None``)
============================================  ==========================================

**``_get_qr_code_base64`` — desenlace 2 de** ``porte-completo-no-parcial`` (
bloqueado por algo medido, con sucesor nombrado). Necesita dos piezas que no
existen en este árbol, ambas verificadas: ``ir.actions.report.barcode``
(``grep -n "def barcode" src/addons/base/models/ir_actions_report.py`` → 0 hits)
e ``image_data_uri`` (``grep -rn image_data_uri src/tools/`` → 0 hits). No es una
divergencia de mecanismo: es el renderizador de códigos de barras, que sigue sin
portarse. Sucesor: tarea #192. Mientras tanto ``build_qr_code_base64`` levanta
``NotImplementedError`` nombrando la pieza, en vez de devolver ``None`` — un
``None`` silencioso se leería como "esta cuenta no admite QR".

Divergencia declarada (DEC-KX-03)
==================================

**``werkzeug.urls.url_encode`` → ``urllib.parse.urlencode``.** ``werkzeug`` no
está instalado (``python3 -c "import werkzeug"`` → ``ModuleNotFoundError``) y no
hay razón para instalarlo: la función codifica un diccionario a *query string*,
que es exactamente lo que hace la de la stdlib. Es sustitución de utilería, no
cambio de comportamiento.
"""
from urllib.parse import urlencode

from addons.base.models.res_partner_bank import ResPartnerBank
from exceptions import UserError
from orm.method_chain import chain_method
from tools.translate import _


def _build_qr_code_vals(self, amount, free_communication, structured_communication,
                        currency, debtor_partner, qr_method=None, silent_errors=True):
    """Elige el método de QR aplicable y devuelve sus parámetros — ≙
    ``odoo19c: account/models/res_partner_bank.py:137-176``.

    Recorre los métodos disponibles **en orden de secuencia** y devuelve el
    primero que supere los dos filtros (elegibilidad y consistencia de datos).
    Con ``silent_errors=False`` levanta el primer error en vez de seguir
    buscando, que es lo que quiere una pantalla al pedir un QR concreto.
    """
    if self.pk is None:
        return None
    if not currency:
        raise UserError(_('Siempre hay que indicar la divisa para generar un código QR.'))

    available_qr_methods = self.get_available_qr_methods_in_sequence()
    if qr_method:
        candidate_methods = [(qr_method, dict(available_qr_methods)[qr_method])]
    else:
        candidate_methods = available_qr_methods

    for candidate_method, candidate_name in candidate_methods:
        error_message = self._get_error_messages_for_qr(
            candidate_method, debtor_partner, currency)
        if not error_message:
            error_message = self._check_for_qr_code_errors(
                candidate_method, amount, currency, debtor_partner,
                free_communication, structured_communication)
            if not error_message:
                return {
                    'qr_method': candidate_method,
                    'amount': amount,
                    'currency': currency,
                    'debtor_partner': debtor_partner,
                    'free_communication': free_communication,
                    'structured_communication': structured_communication,
                }

        if not silent_errors:
            raise UserError(_(
                "El siguiente error impidió generar el código QR '%(candidate)s' "
                'aunque se detectó como elegible: ') % {'candidate': candidate_name}
                + error_message)

    return None


def build_qr_code_url(self, amount, free_communication, structured_communication,
                      currency, debtor_partner, qr_method=None, silent_errors=True):
    """URL del reporte que dibuja el QR — ≙ ``odoo19c: res_partner_bank.py:178-182``."""
    vals = self._build_qr_code_vals(amount, free_communication, structured_communication,
                                    currency, debtor_partner, qr_method, silent_errors)
    if vals:
        return self._get_qr_code_url(**vals)
    return None


def build_qr_code_base64(self, amount, free_communication, structured_communication,
                         currency, debtor_partner, qr_method=None, silent_errors=True):
    """El QR ya renderizado como data URI — ≙ ``odoo19c: res_partner_bank.py:184-188``.

    Bloqueado mientras no exista el renderizador (ver el docstring del módulo).
    """
    vals = self._build_qr_code_vals(amount, free_communication, structured_communication,
                                    currency, debtor_partner, qr_method, silent_errors)
    if vals:
        return self._get_qr_code_base64(**vals)
    return None


def _get_qr_vals(self, qr_method, amount, currency, debtor_partner,
                 free_communication, structured_communication):
    """Terminal de la cadena — ≙ ``odoo19c: res_partner_bank.py:190-191``.

    ``None`` significa "ningún addon instalado sabe armar este método".
    """
    return None


def _get_qr_code_generation_params(self, qr_method, amount, currency, debtor_partner,
                                   free_communication, structured_communication):
    """Terminal de la cadena — ≙ ``odoo19c: res_partner_bank.py:193-194``.

    **Éste es el ``NotImplementedError`` legítimo**: el fondo de la cadena, no un
    eslabón intermedio. Un satélite que no atiende un ``qr_method`` devuelve
    ``None`` y deja que la cadena siga; si nadie lo atiende, se llega aquí.
    """
    raise NotImplementedError()


def _get_qr_code_url(self, qr_method, amount, currency, debtor_partner,
                     free_communication, structured_communication):
    """URL del reporte de barcode — ≙ ``odoo19c: res_partner_bank.py:196-210``.

    ``urlencode`` de la stdlib en lugar de ``werkzeug.urls.url_encode``
    (divergencia declarada en el docstring del módulo).
    """
    params = self._get_qr_code_generation_params(
        qr_method, amount, currency, debtor_partner,
        free_communication, structured_communication)
    return '/report/barcode/?' + urlencode(params) if params else None


def _get_qr_code_base64(self, qr_method, amount, currency, debtor_partner,
                        free_communication, structured_communication):
    """≙ ``odoo19c: res_partner_bank.py:212-231`` — **bloqueado**, no divergente.

    La referencia llama a ``self.env['ir.actions.report'].barcode(**params)`` y
    envuelve el resultado con ``image_data_uri``. Ninguna de las dos existe aquí
    (medido: 0 hits de ``def barcode`` en ``ir_actions_report.py`` y 0 de
    ``image_data_uri`` en ``src/tools/``). Sucesor: tarea #192.

    Levanta en vez de devolver ``None`` para que la ausencia del renderizador no
    se confunda con "esta cuenta no admite QR" — que es lo que ``None`` significa
    en el resto de la cadena.
    """
    raise NotImplementedError(
        'El renderizador de códigos de barras (ir.actions.report.barcode) no '
        'está portado; usar build_qr_code_url mientras tanto. Tarea #192.')


def _get_available_qr_methods(self):
    """Terminal acumulativo — ≙ ``odoo19c: res_partner_bank.py:233-242``.

    Cada satélite añade su ``(código, nombre, secuencia)`` sobre esta lista
    vacía. La secuencia menor se evalúa primero, para que dos métodos aplicables
    a la misma cuenta no se tapen entre sí.
    """
    return []


def get_available_qr_methods_in_sequence(self):
    """Los métodos disponibles ya ordenados — ≙ ``odoo19c: res_partner_bank.py:244-251``."""
    all_available = self._get_available_qr_methods()
    all_available.sort(key=lambda x: x[2])
    return [(code, name) for (code, name, sequence) in all_available]


def _get_error_messages_for_qr(self, qr_method, debtor_partner, currency):
    """Terminal de la cadena — ≙ ``odoo19c: res_partner_bank.py:253-262``.

    ``None`` = elegible. Comprueba que este *tipo* de QR **debería** poder
    generarse; la consistencia de los datos concretos la mira
    ``_check_for_qr_code_errors``.
    """
    return None


def _check_for_qr_code_errors(self, qr_method, amount, currency, debtor_partner,
                              free_communication, structured_communication):
    """Terminal de la cadena — ≙ ``odoo19c: res_partner_bank.py:264-271``.

    ``None`` = sin errores; si no, el primer error encontrado, en texto.
    """
    return None


def apply_account_extensions():
    """Cuelga el bloque QR sobre ``res.partner.bank`` — ≙ ``_inherit``.

    Se invoca desde ``AccountConfig.ready()`` — **antes** que los satélites
    ``account_qr_code_*``, que van después en ``INSTALLED_APPS``. Ese orden es el
    que hace de esto el fondo de la cadena y no un eslabón que los tapa.

    Vía ``chain_method`` y no ``setattr`` con guarda: aunque hoy nadie más
    contribuya a estos hooks desde ``account``, la guarda ``if not hasattr`` es
    justo el defecto que :ref:`h-api-364` registra — correcta para campos,
    silenciosa para overrides.
    """
    for nombre, funcion in (
        ('_build_qr_code_vals', _build_qr_code_vals),
        ('build_qr_code_url', build_qr_code_url),
        ('build_qr_code_base64', build_qr_code_base64),
        ('_get_qr_vals', _get_qr_vals),
        ('_get_qr_code_generation_params', _get_qr_code_generation_params),
        ('_get_qr_code_url', _get_qr_code_url),
        ('_get_qr_code_base64', _get_qr_code_base64),
        ('_get_available_qr_methods', _get_available_qr_methods),
        ('get_available_qr_methods_in_sequence', get_available_qr_methods_in_sequence),
        ('_get_error_messages_for_qr', _get_error_messages_for_qr),
        ('_check_for_qr_code_errors', _check_for_qr_code_errors),
    ):
        chain_method(ResPartnerBank, nombre, funcion)
