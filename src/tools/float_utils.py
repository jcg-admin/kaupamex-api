"""``tools.float_utils`` — fiel a ``odoo/tools/float_utils.py`` (Odoo 19).

Aritmética de punto flotante con precisión declarada. Es la base sobre la que
``uom`` convierte cantidades y precios entre unidades: sin ella, convertir una
docena a unidades da ``12.00000000000047`` y el redondeo lo sube a 13 — la
regresión que la propia referencia documenta en ``uom/tests/test_uom.py``.

Se porta el subconjunto que ``uom`` consume (DEC-AF-03: lo que no se consume,
no se porta): ``float_round``, ``float_compare``, ``float_is_zero`` y el
auxiliar ``float_invert``. Quedan fuera ``float_repr``, ``float_split`` y
``float_split_str``, que son de presentación y hoy no tienen consumidor.
"""
import builtins
import math
from typing import Literal

__all__ = ['float_compare', 'float_is_zero', 'float_round', 'float_invert']

RoundingMethod = Literal['UP', 'DOWN', 'HALF-UP', 'HALF-DOWN', 'HALF-EVEN']


def _round_half_away(f: float) -> float:
    """Redondeo con empate **alejándose de cero**, y preservando el signo.

    El ``round`` interno de Python redondea el empate al par más cercano y
    pierde el signo de ``-0.``; la referencia mantiene este shim por eso mismo.
    """
    roundf = builtins.round(f)
    if builtins.round(f + 1) - roundf != 1:
        return f + math.copysign(0.5, f)
    # copysign asegura que round(-0.) -> -0 y que el resultado sea float
    return math.copysign(roundf, f)


_INVERTDICT = {
    1e-1: 1e+1, 1e-2: 1e+2, 1e-3: 1e+3, 1e-4: 1e+4, 1e-5: 1e+5,
    1e-6: 1e+6, 1e-7: 1e+7, 1e-8: 1e+8, 1e-9: 1e+9, 1e-10: 1e+10,
    2e-1: 5e+0, 2e-2: 5e+1, 2e-3: 5e+2, 2e-4: 5e+3, 2e-5: 5e+4,
    2e-6: 5e+5, 2e-7: 5e+6, 2e-8: 5e+7, 2e-9: 5e+8, 2e-10: 5e+9,
    5e-1: 2e+0, 5e-2: 2e+1, 5e-3: 2e+2, 5e-4: 2e+3, 5e-5: 2e+4,
    5e-6: 2e+5, 5e-7: 2e+6, 5e-8: 2e+7, 5e-9: 2e+8, 5e-10: 2e+9,
}


def float_invert(value: float) -> float:
    """Invierte un flotante con precisión aumentada."""
    result = _INVERTDICT.get(value)
    if result is None:
        coefficient, exponent = f'{value:.15e}'.split('e')
        # invierte el exponente cambiando el signo, y el coeficiente por su cuadrado
        result = float(f'{coefficient}e{-int(exponent)}') / float(coefficient) ** 2
    return result


def _float_check_precision(
    precision_digits: int | None = None,
    precision_rounding: float | None = None,
) -> float:
    if precision_rounding is not None and precision_digits is None:
        assert precision_rounding > 0, (
            f'precision_rounding debe ser positivo, se recibió {precision_rounding}'
        )
    elif precision_digits is not None and precision_rounding is None:
        assert float(precision_digits).is_integer() and precision_digits >= 0, (
            f'precision_digits debe ser un entero no negativo, '
            f'se recibió {precision_digits}'
        )
        precision_rounding = 10 ** -precision_digits
    else:
        raise AssertionError(
            'se debe indicar exactamente uno de precision_digits o precision_rounding'
        )
    return precision_rounding


def float_round(
    value: float,
    precision_digits: int | None = None,
    precision_rounding: float | None = None,
    rounding_method: RoundingMethod = 'HALF-UP',
) -> float:
    """Redondea ``value`` a la precisión dada, minimizando el error IEEE-754.

    La precisión se indica con ``precision_digits`` **o** con
    ``precision_rounding``, nunca con ambos.

    Métodos: ``HALF-UP`` (empate se aleja de cero, por defecto), ``HALF-DOWN``
    (empate hacia cero), ``HALF-EVEN`` (empate al par más cercano), ``UP``
    (siempre se aleja de cero) y ``DOWN`` (siempre hacia cero).
    """
    rounding_factor = _float_check_precision(
        precision_digits=precision_digits, precision_rounding=precision_rounding,
    )
    if rounding_factor == 0 or value == 0:
        return 0.0

    # NORMALIZA - REDONDEA - DESNORMALIZA. Normalizar antes de redondear como
    # entero permite redondear a "pasos" arbitrarios (p. ej. valores de moneda):
    # float_round(1.3, precision_rounding=.5) == 1.5
    def normalize(val):
        return val / rounding_factor

    def denormalize(val):
        return val * rounding_factor

    # invertir factores pequeños reduce el error de redondeo
    if rounding_factor < 1:
        rounding_factor = float_invert(rounding_factor)
        normalize, denormalize = denormalize, normalize

    normalized_value = normalize(value)

    # La aproximación IEEE-754 del valor real puede quedar justo por debajo del
    # límite del empate, produciendo un error de 1 ulp tras redondear (2.675 se
    # representa como 2.6749999999999998). Se suma un epsilon escalado al orden
    # de magnitud del valor para inclinar el empate hacia el lado correcto.
    epsilon_magnitude = math.log2(abs(normalized_value))
    # 2**(magnitud - 52) sería el mínimo; se amplía para tolerar el error
    # acumulado tras varias operaciones en coma flotante
    epsilon = 2 ** (epsilon_magnitude - 50)

    match rounding_method:
        case 'HALF-UP':      # el empate se aleja de cero
            result = _round_half_away(
                normalized_value + math.copysign(epsilon, normalized_value)
            )
        case 'HALF-EVEN':    # el empate va al par más cercano
            integral = math.floor(normalized_value)
            remainder = abs(normalized_value - integral)
            is_half = abs(0.5 - remainder) < epsilon
            result = (
                integral + (integral & 1) if is_half
                else _round_half_away(normalized_value)
            )
        case 'HALF-DOWN':    # el empate va hacia cero
            result = _round_half_away(
                normalized_value - math.copysign(epsilon, normalized_value)
            )
        case 'UP':           # siempre al más lejano de cero
            result = math.trunc(
                normalized_value + math.copysign(1 - epsilon, normalized_value)
            )
        case 'DOWN':         # siempre al más cercano a cero
            result = math.trunc(
                normalized_value + math.copysign(epsilon, normalized_value)
            )
        case _:
            raise ValueError(f'método de redondeo desconocido: {rounding_method}')

    return denormalize(result)


def float_is_zero(
    value: float,
    precision_digits: int | None = None,
    precision_rounding: float | None = None,
) -> bool:
    """``True`` si ``value`` es lo bastante pequeño para tratarse como cero.

    La precisión (``10**-precision_digits`` o ``precision_rounding``) actúa de
    *epsilon*: por debajo de ella el valor se considera cero.

    Cuidado: ``float_is_zero(v1 - v2)`` **no** equivale a
    ``float_compare(v1, v2) == 0`` — el primero redondea después de restar y el
    segundo antes, lo que difiere para 0.006 y 0.002 a dos decimales.
    """
    epsilon = _float_check_precision(
        precision_digits=precision_digits, precision_rounding=precision_rounding,
    )
    return value == 0.0 or abs(float_round(value, precision_rounding=epsilon)) < epsilon


def float_compare(
    value1: float,
    value2: float,
    precision_digits: int | None = None,
    precision_rounding: float | None = None,
) -> Literal[-1, 0, 1]:
    """Compara ``value1`` y ``value2`` **tras** redondearlos a la precisión dada.

    Dos valores son distintos si su valor redondeado difiere, lo que no es lo
    mismo que tener una diferencia no nula: 1.432 y 1.431 son iguales a dos
    decimales, pero 0.006 y 0.002 son distintos (redondean a 0.01 y 0.0) aunque
    su diferencia, 0.004, se consideraría cero a esa misma precisión.

    :return: -1, 0 o 1 si ``value1`` es menor, igual o mayor que ``value2``.
    """
    rounding_factor = _float_check_precision(
        precision_digits=precision_digits, precision_rounding=precision_rounding,
    )
    # los números iguales redondean igual; se corta antes, ya validados los parámetros
    if value1 == value2:
        return 0
    value1 = float_round(value1, precision_rounding=rounding_factor)
    value2 = float_round(value2, precision_rounding=rounding_factor)
    delta = value1 - value2
    if float_is_zero(delta, precision_rounding=rounding_factor):
        return 0
    return -1 if delta < 0.0 else 1
