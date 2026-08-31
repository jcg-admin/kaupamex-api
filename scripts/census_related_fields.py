#!/usr/bin/env python3
"""Censo de ``related=`` en la referencia — el denominador, no de memoria.

``calibration-verified-numbers.md`` prohíbe transcribir a prosa una cifra que
vive en código: **la prosa nombra el comando, no el número**. Este guion es ese
comando. Publica tres cortes que gobiernan decisiones distintas:

- **cuántos hay** en los addons que este árbol porta — el universo;
- **cuántos NO llevan** ``store`` — el reparto que explica por qué el defecto
  de ``store`` es ``False`` para un ``related`` (``odoo19c:
  odoo/orm/fields.py:455``);
- **cuántos son de un tipo que el despachador de aquí todavía no acepta** — el
  trabajo que queda.

Por qué el patrón equilibra paréntesis
=======================================

Una declaración de campo contiene llamadas anidadas — ``digits=(10, 7)``,
``domain=[('a', '=', b)]``, ``string=_("X")``. Un ``[^)]*`` corta en el primer
paréntesis interno y **parte la declaración**, así que ve unas y no otras según
qué argumento venga antes. Aquí el patrón admite un nivel de anidamiento, que
es el que cubre el corpus medido.

*Ciega a:* una declaración con **dos** niveles de anidamiento
(``domain=[('a', 'in', f(x))]``). Medido al escribirlo: el patrón laxo ve 797 y
éste 791, así que la diferencia son 6 declaraciones. El número que publica es
por tanto una **cota inferior**, y lo dice al imprimirlo.
"""
import argparse
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import addons_roots
import reference_roots

#: La sonda de conducta construye campos reales, y eso exige el registro de
#: Django en pie. Se levanta aqui y no dentro de :func:`accepts_related` para
#: que el costo se pague una vez, y para que un fallo de arranque reviente
#: antes de emitir cifra.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'src'))
import django
django.setup()

#: Argumentos posicionales mínimos por tipo — un ``Many2one`` sin comodelo no
#: se construye, y sin ellos la sonda mediría «rechaza» por el motivo
#: equivocado.
PROBE_ARGUMENTS = {
    'Many2one': ('base.ResPartner',),
    'Many2many': ('base.ResPartner',),
    'One2many': ('base.ResPartner',),
}


def accepts_related(field_type):
    """¿El constructor de ``field_type`` acepta ``related=`` **y hace algo**?

    Se mide **por conducta**, construyendo el campo — no leyendo una lista.
    Una lista enumerada aquí es la segunda fuente de verdad que
    ``calibration-verified-numbers.md`` prohíbe, y ya falló: la primera
    versión de este guion enumeraba seis tipos y se saltaba ``Date`` y
    ``Datetime``, que ``make_dispatcher`` fabrica igual que los otros cinco.

    **Aceptar no basta.** ``One2many`` traga ``**kwargs`` y devolvía un campo
    sin la clave puesta: acepta y no hace nada, que es peor que rechazar
    porque el sitio de declaración se lee correcto. Por eso la sonda no
    pregunta si el constructor no revienta, sino si el campo **queda con la
    ruta declarada** — el sub-patrón D de
    ``metrica-decide-la-conclusion.md`` aplicado al propio instrumento.
    """
    import fields as fields_facade
    constructor = getattr(fields_facade, field_type, None)
    if constructor is None:
        return False
    try:
        field = constructor(*PROBE_ARGUMENTS.get(field_type, ()),
                            related='probe.chain')
    except Exception:
        return False
    return getattr(field, 'related', None) == 'probe.chain'

#: Una llamada ``fields.X(...)`` que admite un nivel de anidamiento dentro.
FIELD_CALL = re.compile(r'fields\.(\w+)\(((?:[^()]|\([^()]*\))*)\)', re.S)
DECLARES_STORE = re.compile(r'\bstore\s*=')


def declarations_in(tree_root, addons):
    """Cada ``related=`` de la referencia, con su tipo y si declara ``store``."""
    for path in sorted(tree_root.rglob('addons/*/models/*.py')):
        parts = path.parts
        addon = parts[parts.index('addons') + 1]
        if addon not in addons:
            continue
        source = path.read_text(errors='ignore')
        for match in FIELD_CALL.finditer(source):
            field_type, arguments = match.group(1), match.group(2)
            if 'related=' not in arguments:
                continue
            line = source.count('\n', 0, match.start()) + 1
            yield {
                'addon': addon,
                'path': path,
                'line': line,
                'type': field_type,
                'stored': bool(DECLARES_STORE.search(arguments)),
                'dispatched': accepts_related(field_type),
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alias', default='ODOO19C',
                        help='raíz de la referencia (default: la que gobierna)')
    parser.add_argument('--pendientes', action='store_true',
                        help='listar los que ningún constructor de aquí acepta')
    options = parser.parse_args()

    exported = subprocess.run(
        [sys.executable, str(pathlib.Path(__file__).parent / 'reference_roots.py'),
         '--env'], capture_output=True, text=True, check=True).stdout
    for assignment in re.findall(r'(\w+)=(\S+)', exported):
        os.environ.setdefault(assignment[0], assignment[1].strip('"'))
    tree_root = pathlib.Path(os.environ[options.alias])

    addons = set(addons_roots.addon_names())
    rows = list(declarations_in(tree_root, addons))
    if not rows:
        print(f'ERROR — 0 declaraciones medidas bajo {tree_root}. '
              'NO se emite reparto: un 0 aquí sería un verde falso.',
              file=sys.stderr)
        raise SystemExit(2)

    unstored = [r for r in rows if not r['stored']]
    pending = [r for r in rows if not r['dispatched']]

    if options.pendientes:
        for row in pending:
            relative = row['path'].relative_to(tree_root)
            print(f"{relative}:{row['line']}  fields.{row['type']}")

    by_type = {}
    for row in pending:
        by_type[row['type']] = by_type.get(row['type'], 0) + 1
    print(f'\nrelated= declarados: {len(rows)} en {len(addons)} addons portados')
    print(f'  sin store:  {len(unstored)}  '
          f'({100 * len(unstored) / len(rows):.0f} %)')
    print(f'  con store:  {len(rows) - len(unstored)}')
    print(f'  que ningun constructor de aqui acepta todavia: {len(pending)}  '
          f'({100 * len(pending) / len(rows):.0f} %)')
    for field_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f'      {field_type:12} {count}')
    print('\n(cota inferior: el patrón admite un nivel de anidamiento; una '
          'declaración con dos niveles no se cuenta)')


if __name__ == '__main__':
    main()
