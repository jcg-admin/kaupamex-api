"""Referencias estructuradas de pago -- validacion y formato.

Adaptacion de ``odoo19c: addons/account/tools/structured_reference.py``
(``odoo-tools@622ddc2a``, LGPL-3 -- atribucion y aviso de licencia
preservados, DEC-KX-03). Todas las funciones publicas son puras: no
dependen de ningun modelo ni del ORM.

Cobertura del porte -- 11 de 11 simbolos publicos
==================================================

.. list-table::
   :header-rows: 1

   * - Simbolo
     - Estado
   * - ``sanitize_structured_reference``
     - portado verbatim
   * - ``format_structured_reference_iso``
     - portado verbatim (algoritmo local, ver divergencia)
   * - ``is_valid_structured_reference_iso``
     - portado verbatim (algoritmo local, ver divergencia)
   * - ``is_valid_structured_reference_be``
     - portado verbatim
   * - ``is_valid_structured_reference_dk``
     - portado verbatim (algoritmo local, ver divergencia)
   * - ``is_valid_structured_reference_fi``
     - portado verbatim
   * - ``is_valid_structured_reference_no_se``
     - portado verbatim (algoritmo local, ver divergencia)
   * - ``is_valid_structured_reference_nl``
     - portado verbatim
   * - ``is_valid_structured_reference_si``
     - portado verbatim
   * - ``is_valid_structured_reference``
     - portado verbatim
   * - ``is_valid_structured_reference_for_country``
     - portado verbatim

**Divergencia declarada -- sin la libreria ``stdnum``.** La fuente importa
``stdnum.iso11649``, ``stdnum.luhn`` y ``stdnum.iso7064.mod_97_10``
(``pip install python-stdnum``). Verificado en este arbol:
``uv run python -c "import stdnum"`` -> ``ModuleNotFoundError`` y
``pyproject.toml`` no la declara. Anadirla exige editar ``pyproject.toml``,
que no esta en la lista de archivos escribibles de la tarea #398 -- es la
pieza BLOQUEADA, pero con salida: los tres algoritmos que ``stdnum`` provee
son publicos y estandar (ISO/IEC 7064 MOD 97-10, el mismo checksum de IBAN;
y el algoritmo de Luhn, ISO/IEC 7812-1), asi que se implementan de forma
nativa aqui como ``_mod_97_10_calc_check_digits``, ``_mod_97_10_is_valid``,
``_iso11649_is_valid`` y ``_luhn_is_valid``. Verificados contra los ejemplos
del propio docstring de la fuente:

- ``format_structured_reference_iso('123456789')`` -> ``'RF18 1234 5678 9'``
  -- el ejemplo exacto del docstring de la fuente (``odoo19c:
  addons/account/tools/structured_reference.py:28``), verificado ejecutando
  la funcion en este arbol: coincide caracter a caracter.
- ``is_valid_structured_reference_iso('RF18 1234 5678 9')`` -> ``True`` --
  el resultado formateado arriba round-tripea como valido bajo el mismo
  MOD 97-10, confirmando que el ``calc_check_digits`` y el ``is_valid``
  vendorizados son consistentes entre si.

Si en el futuro un segundo consumidor necesita mas superficie de ``stdnum``
(otros paises, otros checksums), anadir la dependencia real es el camino
correcto -- tarea **#402**, DESCONOCIDA hasta que ese segundo consumidor
aparezca y alguien con permiso sobre ``pyproject.toml`` la declare.
"""
import re
from itertools import zip_longest


def _to_base36_digits(value):
    """Convierte cada caracter alfanumerico a su valor base-36 (ISO 7064).

    ``'0'``..``'9'`` -> 0..9; ``'A'``..``'Z'`` (o minusculas) -> 10..35.
    Es el paso "letter-to-digit" que el MOD 97-10 de ISO 7064 exige antes
    de calcular el resto -- el mismo mecanismo que usa el digito de control
    de un IBAN.
    """
    return ''.join(str(int(char, 36)) for char in value)


def _mod_97_10_calc_check_digits(value):
    """Calcula los 2 digitos de control MOD 97-10 (ISO 7064) para ``value``.

    Equivalente a ``stdnum.iso7064.mod_97_10.calc_check_digits``. El
    algoritmo: se le apendan ``'00'`` a ``value``, se convierte todo a
    digitos base-36, se calcula el resto modulo 97, y el digito de control
    es ``98 - resto`` con 2 posiciones (relleno de ceros a la izquierda).
    """
    numeric = _to_base36_digits(value.upper() + '00')
    remainder = int(numeric) % 97
    return f'{98 - remainder:02d}'


def _mod_97_10_is_valid(value):
    """Valida un numero (ya con sus digitos de control incluidos) bajo
    MOD 97-10 (ISO 7064): valido si su forma numerica en base-36 es
    congruente con 1 modulo 97 -- el mismo criterio que valida un IBAN.
    """
    cleaned = re.sub(r'\s', '', value or '').upper()
    if not cleaned or not all(char.isalnum() for char in cleaned):
        return False
    try:
        numeric = _to_base36_digits(cleaned)
    except ValueError:
        return False
    return int(numeric) % 97 == 1


def _iso11649_is_valid(reference):
    """Valida una Structured Creditor Reference ISO 11649.

    Equivalente a ``stdnum.iso11649.is_valid``. Formato: ``RF`` + 2 digitos
    de control + hasta 21 caracteres alfanumericos. La validacion mueve los
    primeros 4 caracteres (``RF`` + digitos de control) al final de la
    cadena y aplica el mismo MOD 97-10 que valida un IBAN.
    """
    cleaned = re.sub(r'\s', '', reference or '').upper()
    if not re.fullmatch(r'RF[0-9]{2}[A-Z0-9]{1,21}', cleaned):
        return False
    rearranged = cleaned[4:] + cleaned[:4]
    return _mod_97_10_is_valid(rearranged)


def _luhn_is_valid(number):
    """Valida un numero bajo el algoritmo de Luhn (ISO/IEC 7812-1).

    Equivalente a ``stdnum.luhn.is_valid``. Duplica cada segundo digito
    desde la derecha; si el doble supera 9, resta 9. Valido si la suma de
    todos los digitos resultantes es multiplo de 10.
    """
    if not number or not number.isdigit():
        return False
    total = 0
    for index, char in enumerate(reversed(number)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def sanitize_structured_reference(reference):
    """Quita espacios y caracteres especificos de las referencias
    estructuradas belgas.

    Ejemplo: `` RF18 1234 5678 9  `` -> ``RF18123456789``
             ``+++020/3430/57642+++`` -> ``020343057642``
             ``***020/3430/57642***`` -> ``020343057642``
    """
    ref = re.sub(r'\s', '', reference)
    if re.fullmatch(r'(\+{3}|\*{3}|)\d{3}/\d{4}/\d{5}\1', ref):
        return re.sub(r'[+*/]', '', ref)
    return ref


def format_structured_reference_iso(number):
    """Formatea una cadena como Structured Creditor Reference.

    La Creditor Reference es un estandar internacional (ISO 11649).
    Ejemplo: ``123456789`` -> ``RF18 1234 5678 9``
    """
    check_digits = _mod_97_10_calc_check_digits(f"{number}RF")
    return 'RF{} {}'.format(
        check_digits,
        ' '.join(''.join(x) for x in zip_longest(*[iter(str(number))] * 4, fillvalue=''))
    )


def is_valid_structured_reference_iso(reference):
    """Verifica si la referencia dada es una Structured Creditor Reference
    valida (ISO).

    :param reference: la referencia a verificar
    """
    ref = sanitize_structured_reference(reference)
    return _iso11649_is_valid(ref)


def is_valid_structured_reference_be(reference):
    """Verifica si la referencia dada es una referencia estructurada valida
    para Belgica.

    :param reference: la referencia a verificar
    """
    ref = sanitize_structured_reference(reference)
    be_ref = re.fullmatch(r'(\d{10})(\d{2})', ref)
    return bool(be_ref) and int(be_ref.group(1)) % 97 == int(be_ref.group(2)) % 97


def is_valid_structured_reference_dk(reference):
    """Verifica si la referencia dada es una referencia estructurada valida
    para Dinamarca.
    Ejemplo: +71<022646321691221+88655702<

    :param reference: la referencia a verificar
    """
    ref = sanitize_structured_reference(reference)
    match = re.fullmatch(r'\+?(?:71<(\d{15})|75<(\d{16}))\+\d{8}<', ref)
    if not match:
        return False

    payment_ref = match.group(1) or match.group(2)
    return _luhn_is_valid(payment_ref)


def is_valid_structured_reference_fi(reference):
    """Verifica si la referencia dada es una referencia estructurada valida
    para Finlandia.

    :param reference: la referencia a verificar
    """
    ref = sanitize_structured_reference(reference)
    fi_ref = re.fullmatch(r'(\d{1,19})(\d)', ref)
    if not fi_ref:
        return False
    total = sum((7, 3, 1)[idx % 3] * int(val) for idx, val in enumerate(fi_ref.group(1)[::-1]))
    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(fi_ref.group(2))


def is_valid_structured_reference_no_se(reference):
    """Verifica si la referencia dada es una referencia estructurada valida
    para Noruega o Suecia.

    :param reference: la referencia a verificar
    """
    ref = sanitize_structured_reference(reference)
    no_se_ref = re.fullmatch(r'\d+', ref)
    return bool(no_se_ref) and _luhn_is_valid(ref)


def is_valid_structured_reference_nl(reference):
    """Genera una referencia de pago estructurada holandesa valida
    (betalingskenmerk) verificando que sigue el formato correcto.

    Longitudes de referencia validas:
    - 7 digitos: referencia simple sin digito de control.
    - 9-14 digitos: incluye digito de control y codigo de longitud.
    - 16 digitos: solo digito de control, comun en transferencias.

    :param reference: la referencia a verificar
    :return: True si la referencia es una referencia estructurada, False en
        otro caso
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
    """Valida una referencia estructurada eslovena usando el Modelo 01
    (SI01).

    Formato: SI01 (P1-P2-P3)K
    - Empieza con 'SI01'
    - P1, P2, P3 son segmentos numericos (max 20 digitos en total, hasta 2
      guiones)
    - K es un digito de control calculado con MOD 11

    :param reference: la referencia a verificar
    :return: True si la referencia es una referencia estructurada, False en
        otro caso
    """
    sanitized_reference = sanitize_structured_reference(reference)

    if sanitized_reference.startswith('SI01'):
        sanitized_reference = sanitized_reference[4:]  # Quita SI01
    else:
        return False

    # Maximo dos guiones
    if sanitized_reference.count('-') > 2:
        return False

    # Valida las partes con guion via regex: 3 partes numericas (la ultima
    # termina en el digito de control)
    match = re.match(r'^(\d+)-(\d+)-(\d+)$', sanitized_reference)
    if not match:
        return False

    # Separa digitos principales y digito de control
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
    """Verifica si la referencia dada es una referencia estructurada valida.
    Cubre actualmente los paises habilitados para SEPA. Mas especificamente
    los paises cubiertos por las funciones de este archivo.

    :param reference: la referencia a verificar
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


def is_valid_structured_reference_for_country(reference, country_code=''):
    """Verifica la validez estructural de la referencia para un pais
    especifico, o ISO 11649 como respaldo.

    :param reference: la referencia a verificar
    :param country_code: el codigo de pais contra el que verificar
    :return: True si la referencia es una referencia estructurada para el
        pais dado o ISO 11649, False en otro caso
    """
    check_per_country = {
        'BE': is_valid_structured_reference_be,
        'FI': is_valid_structured_reference_fi,
        'NO': is_valid_structured_reference_no_se,
        'SE': is_valid_structured_reference_no_se,
        'NL': is_valid_structured_reference_nl,
        'SI': is_valid_structured_reference_si,
    }

    reference = sanitize_structured_reference(reference or '')
    check = check_per_country.get(country_code.upper())
    if check:
        return check(reference)
    return is_valid_structured_reference_iso(reference)
