"""Servicios de ``base_address_extended`` — parsing estructurado de calle.

Portación **fiel** de ``odoo.tools.misc.street_split`` (Odoo base, byte-idéntico
en 18 ``odoo/tools/misc.py:1902-1911`` y 19 ``odoo/tools/misc.py:1913-1922``).
En Odoo esta función vive en ``tools`` y la usa ``base_address_extended`` para
descomponer ``res.partner.street`` en ``street_name`` / ``street_number`` /
``street_number2``. Aquí es un servicio puro (sin modelo) reutilizable por
cualquier addon que estructure una dirección.
"""
import re

# ADDRESS_REGEX — idéntico a Odoo (``odoo/tools/misc.py``). Captura:
#   grupo 1: nombre de la calle (todo lo previo al número, no-greedy).
#   grupo 2: número (empieza por dígito, precedido de espacio) — opcional.
#   grupo 3: segundo número / puerta tras `` - `` — opcional.
ADDRESS_REGEX = re.compile(r'^(.*?)(\s[0-9][0-9\S]*)?(?: - (.+))?$', flags=re.DOTALL)


def street_split(street):
    """Descompone ``street`` en ``street_name`` / ``street_number`` /
    ``street_number2`` (fiel a ``odoo.tools.street_split``).

    Retorna siempre las tres claves (cadenas ya recortadas); si ``street`` es
    vacío o ``None``, todas quedan vacías.
    """
    match = ADDRESS_REGEX.match(street or '')
    results = match.groups('') if match else ('', '', '')
    return {
        'street_name': results[0].strip(),
        'street_number': results[1].strip(),
        'street_number2': results[2],
    }
