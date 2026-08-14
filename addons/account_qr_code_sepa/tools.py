r"""Dependencias vendorizadas de ``account.tools`` + datos de ``base.sepa_zone``.

**Alcance de este archivo (no confundir con "el porte de ``account.tools``").**
``_get_qr_vals`` (``models/res_bank.py``) depende de dos símbolos que en la
referencia viven fuera de ``account_qr_code_sepa``:

1. ``is_valid_structured_reference``/``sanitize_structured_reference`` —
   ``odoo19c: account/tools/structured_reference.py`` (209 líneas, LGPL-3,
   ``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de`` — atribución y
   aviso de licencia preservados, DEC-KX-03). Módulo **compartido**: lo
   importan también ``account/models/account_move.py`` y varios addons EDI
   UBL/CII y de localización (medido: ``grep -rln "from odoo.addons.account
   .tools import\|is_valid_structured_reference\|sanitize_structured_
   reference" odoo19c --include=*.py | grep -v /account/tools/`` da 12
   archivos fuera de ``account/tools/``). Portarlo entero es trabajo de
   ``account`` como addon propio, no de este puente — la instrucción de esta
   tarea es explícita: "no toques ningún otro addon".
2. El código de países de la zona SEPA — ``odoo19c: odoo/addons/base/data/
   res_country_data.xml``, registro ``res.country.group`` con id ``sepa_zone``
   (``env.ref('base.sepa_zone').country_ids.mapped('code')`` en la
   referencia). Es un fixture XML de ``base``, y ``base`` en este árbol no
   tiene todavía el modelo ``res.country.group`` ni esa data cargada (medido:
   ``grep -rl "res.country.group\|ResCountryGroup" src/addons/base/`` da 0
   hits) — otro addon fuera de este alcance.

**Qué se porta aquí, y con qué método.** Sólo lo que ``_get_qr_vals`` llama,
no el archivo ``structured_reference.py`` completo: se omiten
``format_structured_reference_iso`` (no es un validador; formatea) y
``is_valid_structured_reference_for_country`` (la referencia usa la forma
agregada ``is_valid_structured_reference``, no ésta). Las siete funciones
``is_valid_structured_reference_{be,dk,fi,no_se,nl,si,iso}`` y
``sanitize_structured_reference`` se portan **verbatim** — no llaman a nada
Odoo-específico (ni ``self``, ni ``env``, ni ``fields``), así que el único
divergente real es su dependencia de ``python-stdnum`` (paquete ``stdnum``),
que no es una dependencia de este proyecto (verificado:
``python3 -c "import stdnum"`` → ``ModuleNotFoundError``; no está en
``pyproject.toml``). Por directiva del ejecutor ("si el ORM no tiene el
mecanismo, se construye — API pública primero, luego internos, luego
Postgres nativo") se reimplementan en Python puro los dos primitivos que
``stdnum`` aportaba (``iso11649.is_valid``, ``luhn.is_valid``) siguiendo sus
algoritmos publicados — sin agregar una dependencia nueva al proyecto.

El código de la zona SEPA se vendoriza como constante estática
(``SEPA_ZONE_COUNTRY_CODES``), transcrita del fixture citado arriba.

**Condición de cierre (DESCONOCIDO declarado, no una omisión silenciosa).**
Cuando ``account`` porte ``account/tools/structured_reference.py`` como
módulo propio, y/o ``base`` porte ``res.country.group`` con la data de
``sepa_zone``, este archivo debe retirarse y ``models/res_bank.py`` debe
consumir esos símbolos en su lugar. Hasta entonces, este vendor local es la
implementación completa y correcta del subconjunto que el addon usa — no un
stub.
"""
import re

__all__ = [
    'SEPA_ZONE_COUNTRY_CODES',
    'is_valid_structured_reference',
    'sanitize_structured_reference',
]

#: Códigos ISO 3166-1 alfa-2 de los 49 países/territorios de la zona SEPA —
#: transcrito de ``odoo19c: odoo/addons/base/data/res_country_data.xml``,
#: registro ``res.country.group`` ``id="sepa_zone"`` (``code="SEPA"``). Los
#: ids XML de la referencia están en minúscula (p. ej. ``ref('uk')``); el
#: campo ``code`` real del país referenciado —el que ``ResCountry.save()``
#: normaliza a mayúscula en este puerto (``base/models/res_country.py``,
#: ``self.code = self.code.upper()``)— es lo que se transcribe aquí (medido
#: registro por registro en el fixture; ``uk`` → ``code="gb"``, no ``"UK"``).
SEPA_ZONE_COUNTRY_CODES = frozenset({
    'AD', 'AT', 'AX', 'BE', 'BG', 'BL', 'CH', 'CY', 'CZ', 'DE',
    'DK', 'EE', 'ES', 'FI', 'FR', 'GB', 'GF', 'GG', 'GI', 'GP',
    'GR', 'HR', 'HU', 'IE', 'IM', 'IS', 'IT', 'JE', 'LI', 'LT',
    'LU', 'LV', 'MC', 'MF', 'MQ', 'MT', 'NL', 'NO', 'PL', 'PM',
    'PT', 'RE', 'RO', 'SE', 'SI', 'SK', 'SM', 'VA', 'YT',
})


def _luhn_is_valid(number: str) -> bool:
    """Checksum de Luhn (mod 10) — sustituye ``stdnum.luhn.is_valid``.

    Usado por los validadores de Dinamarca y Noruega/Suecia. Algoritmo
    estándar: se dobla cada segundo dígito contando desde la derecha: si el
    doblado excede 9, se le resta 9; la suma de todos los dígitos (doblados o
    no) debe ser múltiplo de 10.
    """
    if not number or not number.isdigit():
        return False
    checksum = 0
    for index, char in enumerate(reversed(number)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


_ISO11649_PATTERN = re.compile(r'RF\d{2}[A-Z0-9]{1,21}')


def _iso11649_is_valid(reference: str) -> bool:
    r"""Checksum ISO 11649 (Structured Creditor Reference) — sustituye
    ``stdnum.iso11649.is_valid``.

    Formato: ``RF`` + 2 dígitos de control + hasta 21 alfanuméricos (longitud
    total 5-25). Válido cuando, tras mover ``RF`` + los 2 dígitos de control
    al final y sustituir cada letra por su valor numérico (``A``\ =10 …
    ``Z``\ =35), el número resultante es congruente con 1 módulo 97 — el
    mismo algoritmo ISO 7064 MOD 97-10 que valida el dígito de control del
    IBAN.
    """
    ref = (reference or '').strip().upper()
    if not _ISO11649_PATTERN.fullmatch(ref):
        return False
    rearranged = ref[4:] + ref[:4]
    numeric = ''.join(
        str(ord(char) - 55) if char.isalpha() else char
        for char in rearranged
    )
    return int(numeric) % 97 == 1


def sanitize_structured_reference(reference):
    """Removes whitespace and specific characters from Belgian structured references:

    Example: ` RF18 1234 5678 9  ` -> `RF18123456789`
             `+++020/3430/57642+++` -> `020343057642`
             `***020/3430/57642***` -> `020343057642`
    """
    ref = re.sub(r'\s', '', reference)
    if re.fullmatch(r'(\+{3}|\*{3}|)\d{3}/\d{4}/\d{5}\1', ref):
        return re.sub(r'[+*/]', '', ref)
    return ref


def is_valid_structured_reference_iso(reference):
    """Check whether the provided reference is a valid Structured Creditor Reference (ISO).

    :param reference: the reference to check
    """
    ref = sanitize_structured_reference(reference)
    return _iso11649_is_valid(ref)


def is_valid_structured_reference_be(reference):
    """Check whether the provided reference is a valid structured reference for Belgium.

    :param reference: the reference to check
    """
    ref = sanitize_structured_reference(reference)
    be_ref = re.fullmatch(r'(\d{10})(\d{2})', ref)
    return be_ref and int(be_ref.group(1)) % 97 == int(be_ref.group(2)) % 97


def is_valid_structured_reference_dk(reference):
    """Check whether the provided reference is a valid structured reference for Denmark.
    Example: +71<022646321691221+88655702<

    :param reference: the reference to check
    """
    ref = sanitize_structured_reference(reference)
    match = re.fullmatch(r'\+?(?:71<(\d{15})|75<(\d{16}))\+\d{8}<', ref)
    if not match:
        return False

    payment_ref = match.group(1) or match.group(2)
    return _luhn_is_valid(payment_ref)


def is_valid_structured_reference_fi(reference):
    """Check whether the provided reference is a valid structured reference for Finland.

    :param reference: the reference to check
    """
    ref = sanitize_structured_reference(reference)
    fi_ref = re.fullmatch(r'(\d{1,19})(\d)', ref)
    if not fi_ref:
        return False
    total = sum((7, 3, 1)[idx % 3] * int(val) for idx, val in enumerate(fi_ref.group(1)[::-1]))
    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(fi_ref.group(2))


def is_valid_structured_reference_no_se(reference):
    """Check whether the provided reference is a valid structured reference for Norway or Sweden.

    :param reference: the reference to check
    """
    ref = sanitize_structured_reference(reference)
    no_se_ref = re.fullmatch(r'\d+', ref)
    return no_se_ref and _luhn_is_valid(ref)


def is_valid_structured_reference_nl(reference):
    """ Generates a valid Dutch structured payment reference (betalingskenmerk)
        by ensuring it follows the correct format.

        Valid reference lengths:
        - 7 digits: Simple reference with no check digit.
        - 9-14 digits: Includes a check digit and a length code.
        - 16 digits: Contains only a check digit, commonly used for wire transfers.

        :param reference: the reference to check
        :return: True if reference is a structured reference, False otherwise
    """
    sanitized_reference = sanitize_structured_reference(reference)

    if re.fullmatch(r'\d{7}', sanitized_reference):
        return True

    if not re.fullmatch(r'\d{9,16}', sanitized_reference):
        return False

    if len(sanitized_reference) == 15:
        return False

    check, reference_to_check = sanitized_reference[0], sanitized_reference[1:]
    weigths = [2, 4, 8, 5, 10, 9, 7, 3, 6, 1]
    reference_to_check = reference_to_check.zfill(16)[::-1]

    total = sum(
        int(digit) * weigths[index % len(weigths)]
        for index, digit in enumerate(reference_to_check)
    )
    computed_check = 11 - (total % 11)
    if computed_check == 11:
        computed_check = 0
    elif computed_check == 10:
        computed_check = 1

    return computed_check == int(check)


def is_valid_structured_reference_si(reference):
    """ Validates a Slovenian structured reference using Model 01 (SI01).

        Format: SI01 (P1-P2-P3)K
        - Starts with 'SI01'
        - P1, P2, P3 are numeric segments (max 20 digits total, up to 2 hyphens)
        - K is a check digit calculated using MOD 11

        :param reference: the reference to check
        :return: True if reference is a structured reference, False otherwise
    """
    sanitized_reference = sanitize_structured_reference(reference)

    if sanitized_reference.startswith('SI01'):
        sanitized_reference = sanitized_reference[4:]  # Remove SI01
    else:
        return False

    # Contains maximum of two hyphens
    if sanitized_reference.count('-') > 2:
        return False

    # Validate hyphenated parts using regex: 3 numeric parts (last ends with check digit)
    match = re.match(r'^(\d+)-(\d+)-(\d+)$', sanitized_reference)
    if not match:
        return False

    # Split into main digits and check digit
    core = sanitized_reference.replace('-', '')
    if not core.isdigit() or len(core) < 2:
        return False

    digits, given_check_digit = core[:-1], core[-1]

    weights = list(range(2, 14))
    weights = weights[0:len(digits)]
    weighted_sum = sum(int(d) * w for d, w in zip(reversed(digits), weights))

    expected_check_digit = 11 - (weighted_sum % 11)
    if expected_check_digit in (10, 11):
        expected_check_digit = 0

    return given_check_digit == str(expected_check_digit)


def is_valid_structured_reference(reference):
    """Check whether the provided reference is a valid structured reference.
    This is currently supporting SEPA enabled countries. More specifically countries covered by functions in this file.

    :param reference: the reference to check
    """
    reference = sanitize_structured_reference(reference or '')

    return (
        is_valid_structured_reference_be(reference) or
        is_valid_structured_reference_dk(reference) or
        is_valid_structured_reference_fi(reference) or
        is_valid_structured_reference_no_se(reference) or
        is_valid_structured_reference_si(reference) or
        is_valid_structured_reference_nl(reference) or
        is_valid_structured_reference_iso(reference)
    ) if reference else False
