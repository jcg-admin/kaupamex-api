#!/usr/bin/env python3
"""Gate: ninguna cadena declara una secuencia de escape que Python no conoce.

``"\\ "`` y ``"\\|"`` no son escapes de Python. Hasta 3.11 el intérprete los
dejaba pasar con un ``DeprecationWarning``; desde 3.12 emite
``SyntaxWarning``, y la documentación anuncia que pasarán a ser
``SyntaxError``. Un docstring con markup RST o con un comando ``grep`` citado
los produce sin que nadie lo note: el módulo importa, la suite pasa, y el aviso
se pierde entre la salida.

**El arreglo es el prefijo ``r`` en la cadena, no duplicar la barra.** Los dos
casos que originaron este gate lo muestran:

- ``addons/stock/models/product_strategy.py`` usaba ``\\`` + espacio, que es el
  **escape de espacio de RST** — el que pega markup a texto sin dejar hueco.
  Escribirlo ``\\\\`` rompería el renderizado.
- ``addons/website_sale/models/crm_team.py`` citaba
  ``grep -rn "salesteam\\|salesperson"``. Duplicar la barra deja un comando que
  no se puede copiar y pegar, que es justo para lo que se cita.

Es el idioma de la referencia, no una invención: ``odoo19c`` declara ``r\"\"\"``
en **85 archivos / 165 ocurrencias** (``odoo-tools@622ddc2a``), y donde se mira
el contenido son regex y SQL — el mismo motivo.

*Métrica:* advertencias ``SyntaxWarning`` de tipo *invalid escape sequence* que
emite ``compile()`` sobre cada archivo.
*Ciega a:* un escape inválido dentro de un archivo que no compila por otra
razón — ése lo atrapa el ``SyntaxError``, antes y más ruidosamente. Y ciega a
un ``r`` puesto donde el autor **sí** quería el escape: el gate mide que Python
entienda la cadena, no que diga lo que su autor pensaba.

Uso:

    python3 scripts/check_escape_sequences.py                # todo el árbol
    python3 scripts/check_escape_sequences.py <archivos>     # sólo esos
"""
import pathlib
import sys
import warnings

#: Directorios que no son código del proyecto.
EXCLUDED = {'.venv', '.git', 'node_modules', '__pycache__', 'build', 'dist'}


def find_invalid_escapes(path):
    """Devuelve ``[(lineno, mensaje)]`` de los escapes inválidos del archivo.

    Un ``SyntaxError`` devuelve lista vacía a propósito: ese archivo ya está
    roto por una causa mayor, y reportarlo aquí sería ruido sobre ruido.
    """
    try:
        source = path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return []

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:
            compile(source, str(path), 'exec')
        except SyntaxError:
            return []
        return [
            (w.lineno, str(w.message))
            for w in caught
            if 'escape sequence' in str(w.message)
        ]


def collect(argv):
    """Los archivos a medir: los pedidos por ruta, o todo el árbol."""
    if argv:
        return [pathlib.Path(a) for a in argv if a.endswith('.py')]
    return sorted(
        p for p in pathlib.Path('.').rglob('*.py')
        if not EXCLUDED & set(p.parts)
    )


def main(argv):
    files = collect(argv)
    findings = []
    for path in files:
        findings.extend(
            (path, lineno, message)
            for lineno, message in find_invalid_escapes(path)
        )

    scope = (
        f'{len(files)} archivos pedidos por ruta' if argv
        else f'{len(files)} archivos del árbol'
    )

    if not findings:
        print(f'OK: sin secuencias de escape inválidas (alcance medido: {scope}).')
        return 0

    print(f'ERROR: {len(findings)} secuencia(s) de escape inválida(s):',
          file=sys.stderr)
    for path, lineno, message in findings:
        print(f'  {path}:{lineno} — {message}', file=sys.stderr)
    print('', file=sys.stderr)
    print('Arreglo: prefijo r en la cadena (r"""..."""), NO duplicar la barra.',
          file=sys.stderr)
    print(f'(alcance medido: {scope})', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
