"""Reparte la deuda en lo que se traduce con un mapa y lo que exige juicio.

El censo por palabra lo dominan CONECTORES (``de``, ``el``, ``con``, ``por``),
no sustantivos. Un conector dentro de un identificador significa que el
identificador es una **frase**, y una frase no se traduce palabra a palabra:
``test_crea_la_linea_con_el_producto`` no es ``test_creates_the_line_with_the_
product`` sino ``test_it_creates_the_line_for_the_product``.

Por eso el reparto no es por raiz sino por FORMA:

- **mecanica** — el identificador no lleva conectores: es un sustantivo o un
  compuesto corto (``nombre``, ``linea_de_venta``). Lo cierra el mapa mas
  ``scripts/rename_identifiers.py``.
- **juicio** — lleva al menos un conector: es una frase, casi siempre un nombre
  de test. Se reescribe leyendo que mide, no sustituyendo.

*Metrica:* entradas del baseline con y sin conector espanol en su nombre.
*Ciega a:* la frase sin conectores (``test_producto_borrado_falla``), que cae
en «mecanica» y no lo es; es una cota inferior de la clase que exige juicio.
"""
import collections
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ / 'scripts'))

#: Conectores del lexico del gate. Se listan porque son el DISCRIMINADOR de
#: esta sonda, no porque sean deuda distinta: su presencia dice «esto es una
#: frase», que es lo unico que la sonda decide.
CONNECTORS = {'de', 'el', 'la', 'los', 'las', 'del', 'con', 'por', 'para',
              'en', 'una', 'un', 'que', 'al', 'y', 'o', 'su', 'sus'}


def main():
    try:
        from check_identifier_language import spanish_words_in
    except ImportError as exc:
        print(f'ERROR — falta el lexico del gate: {exc}\n'
              'NO se emite conteo.', file=sys.stderr)
        raise SystemExit(2) from exc

    baseline = RAIZ / 'scripts' / 'identifier_language_baseline.txt'
    mechanical, judgement = [], []
    for line in baseline.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        archivo, _, nombre = line.partition('::')
        if not nombre:
            continue
        if CONNECTORS & set(spanish_words_in(nombre)):
            judgement.append((archivo, nombre))
        else:
            mechanical.append((archivo, nombre))

    total = len(mechanical) + len(judgement)
    print(f'total: {total}')
    print(f'  mecanica (sin conector): {len(mechanical):5d}  '
          f'{len(mechanical) * 100 // total} %')
    print(f'  juicio   (con conector): {len(judgement):5d}  '
          f'{len(judgement) * 100 // total} %')

    for etiqueta, grupo in (('mecanica', mechanical), ('juicio', judgement)):
        por_raiz = collections.Counter(a.split('/', 1)[0] for a, _ in grupo)
        print(f'\n{etiqueta} por raiz: {dict(por_raiz.most_common())}')

    print('\nmuestra mecanica:')
    for archivo, nombre in mechanical[:8]:
        print(f'  {nombre}   ({archivo})')
    print('\nmuestra juicio:')
    for archivo, nombre in judgement[:8]:
        print(f'  {nombre}   ({archivo})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
