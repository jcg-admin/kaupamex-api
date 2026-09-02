#!/usr/bin/env python3
"""¿La premisa de una ficha, o de una pieza de banco, sigue siendo cierta?

Una premisa se escribe una vez y el árbol cambia todos los días. Entre las dos
fechas envejece sin que nada lo reporte: la ficha sigue pidiendo construir algo
que ya existe, citar un archivo que se movió, o esperar a un bloqueador que ya
cerró. Este guion mide esas tres formas y emite ``RE-ENCUADRAR``.

Qué NO afirma
-------------

Una señal **no dice que el trabajo esté hecho**. Dice que la premisa cita algo
que ya existe, y por tanto que **el encuadre debe re-medirse antes de
despachar**. La distinción es el valor entero del guion: un símbolo puede
existir con la mitad de su cuerpo portado (``porte-completo-no-parcial.md``), y
cerrar automáticamente sobre esa señal sería el porte parcial silencioso que
esa regla prohíbe. Por eso el veredicto es ``RE-ENCUADRAR``, nunca ``CERRAR``,
y por eso sale 0 salvo ``--strict``.

De dónde viene, y en qué diverge
---------------------------------

Es la adaptación a ``api`` de ``docs: .claude/scripts/gates/verificar_premisa.py``.
Aquélla ya medía **este** árbol —sus ``CODE_ROOTS`` apuntan a
``kaupamex-api/src`` y ``kaupamex-api/addons``— desde el repo de al lado,
resolviendo la raíz con cinco saltos de ``dirname`` que su propio docstring
declara frágiles. Aquí el árbol es local y la premisa se mide desde donde vive.

Cuatro divergencias, las cuatro con su motivo medido:

1. **Las raíces se derivan, no se teclean.** ``addons_roots`` las lee de
   ``src/modules/module.py``, que es la fuente única. Un gate con su copia de
   la ruta es la segunda fuente de verdad que
   ``calibration-verified-numbers.md`` prohíbe, y falla en silencio: apuntado
   a una raíz vacía publica «0 incumplidores» y parece sano (H-API-335).

2. **El índice ve el campo declarado por asignación.** Aquél sólo casa
   ``def``/``class`` al principio de línea. Medido sobre ``src`` + ``addons``:
   **11070** declaraciones de función o clase y **3127** campos por asignación
   — el 22 % del universo, y justo la forma de la que hablan las fichas de
   porte (``barcode = fields.Char(...)``). Sin esa mitad, una ficha que pide
   construir un campo que ya existe salía «premisa firme».

3. **Rehúsa en vez de publicar el cero.** Con el índice vacío ninguna señal
   dispara y el informe diría «0 piden re-encuadre». Ese cero no distingue
   «premisa firme» de «no pude medir», que es el sub-patrón D de
   ``metrica-decide-la-conclusion.md``. Con ``--strict`` el índice exige haber
   medido al menos un archivo y, si no, sale 2 **sin emitir conteo**.

4. **El motor toma TEXTO, no una ficha.** Aquél sólo sabe leer el tablero.
   Aquí la premisa de una pieza de ``scripts/workbench/`` es una fuente de
   primera clase: su ``manifest.json`` declara ``question`` y, cuando lo hay,
   ``corrected_premise``, que es exactamente lo que envejece.

Y una divergencia de juicio, no de mecanismo: la señal de ruta fantasma sólo se
emite sobre una ruta que **este repo posee** (``src``, ``addons``, ``tests``,
``scripts``). Una ruta de un repo hermano se resuelve si el clon está en el
árbol y, si no está, se calla: no poder decidir NO es «no existe».

Métrica: señales sintácticas sobre el texto de la premisa, contrastadas contra
el árbol de código y contra el estado del tablero.

Ciega a: la premisa que envejeció **sin dejar rastro léxico** — una descrita en
prosa, sin nombrar símbolo ni ruta, no produce señal aunque sea falsa. Ciega
también al homónimo: un identificador corriente puede existir en otro addon sin
relación con la premisa, y por eso cada señal imprime su ``file:line`` para que
el juicio lo haga quien lee.

Y ciega a **cuándo** se declaró el símbolo, que es lo que separa los dos modos:

- ``--manifest`` sobre la pieza que se está **redactando** es el modo útil: ahí
  una señal dice que la pregunta ya la contestó el árbol.
- ``--workbench`` barre el archivo, y sobre una pieza **ya cerrada** una señal
  S1 es la huella de su propio trabajo, no una premisa envejecida — igual que
  en una ficha cerrada del tablero.

La diferencia es que una ficha declara su ``status`` y una pieza no. Se
consideró derivarlo de que el manifiesto declare ``findings`` u ``outputs`` y
**se descartó por medición**: de las 13 piezas del banco, 4 han cerrado sin
declarar ninguna de las dos claves, así que ese marcador daría por abiertas
piezas que no lo están. Antes que inventar un estado, el guion declara la
ceguera y el veredicto se lee con la fecha de la pieza a la vista.

Uso:
    verify_premise.py --task 273 305        # esas fichas del tablero
    verify_premise.py --top 10              # las primeras no cerradas
    verify_premise.py --all                 # todas las no cerradas
    verify_premise.py --manifest scripts/workbench/<slug>/manifest.json
    verify_premise.py --workbench           # todas las piezas del banco
    verify_premise.py --all --strict        # exit 1 si alguna tiene señal
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import addons_roots  # noqa: E402

DONE = 'completed'

#: Las raíces de código, derivadas de ``src/modules/module.py`` por
#: ``addons_roots`` — nunca tecleadas (divergencia 1 del docstring).
CODE_ROOTS = (addons_roots.REPO_ROOT / 'src', *addons_roots.ADDONS_PATHS)

#: Los directorios de primer nivel que ESTE repo posee. Una ruta citada que
#: empiece por otro es de un repo hermano, y sobre ésa el guion se calla si el
#: clon no está en el árbol.
OWN_ROOTS = ('src', 'addons', 'tests', 'scripts')

#: Un símbolo declarado como función o clase.
DECLARATION = re.compile(r'^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)')

#: Un campo declarado por asignación al nivel de la clase — la forma que la
#: mitad de las fichas de porte nombra, y la que el gate hermano no ve.
#: La sangría de exactamente cuatro espacios es lo que la distingue de un
#: local dentro de un método, que no es una declaración del modelo.
FIELD_DECLARATION = re.compile(
    r'^ {4}([a-z_]\w*)\s*=\s*(?:fields\.|models\.)')

#: Verbos que convierten la mención de un símbolo en una afirmación de
#: ausencia. Sin verbo no hay señal: nombrar un símbolo no es decir que falta.
BUILD_VERB = re.compile(
    r'\b(construir|portar|crear|a[nñ]adir|anadir|implementar|declarar|'
    r'completar|reponer|restaurar|cablear)\b', re.I)

#: Identificador desnudo — ``snake_case`` o ``dotted.name``, que es la forma
#: con que el tablero nombra el código. Se exige al menos un separador para no
#: capturar palabras corrientes del español.
BARE_IDENTIFIER = re.compile(r'\b([a-z_]{3,}(?:[_.][a-z_]{2,})+)\b')

#: Ruta de archivo citada en la premisa.
FILE_PATH = re.compile(
    r'\b((?:src|addons|tests|scripts|source|provisioners|config|utils)/'
    r'[\w./-]+\.(?:py|sh|rst|js|jsx|sql|conf|json))')

#: Por encima de este número de declaraciones, un identificador es vocabulario
#: corriente del árbol y no la pieza concreta que la premisa nombra.
GENERIC_SYMBOL_THRESHOLD = 2

#: Cita de tarea con verbo de bloqueo, en su forma estrecha.
BLOCKER_CITE = re.compile(
    r'\b(bloquead[ao]s?\s+por|bloqueada\s+por|depende\s+de|precursor\s+de)\b'
    r'[^#\n]{0,40}#(\d+)', re.I)

#: Las claves del manifiesto que llevan premisa. ``metric`` y ``blind_to``
#: describen el instrumento, no lo que se creía del árbol, así que no entran.
PREMISE_KEYS = ('question', 'corrected_premise')


def build_symbol_index(roots=None, require_files=False):
    """Dónde se declara cada símbolo: nombre → lista de ``(forma, file:line)``.

    Un índice en una pasada, no un ``grep`` por símbolo: una premisa cita
    decenas de identificadores y el árbol tiene miles de archivos.

    ``require_files`` es el guard del sub-patrón D. Sin él, un índice de cero
    archivos hace que **ninguna** señal dispare y el informe publique su cero
    como si fuera salud. Con él, el guion sale 2 sin emitir conteo.
    """
    roots = CODE_ROOTS if roots is None else roots
    index = collections.defaultdict(list)
    files = 0
    for root in roots:
        if not os.path.isdir(root):
            continue
        for directory, _, names in os.walk(root):
            if '__pycache__' in directory:
                continue
            for name in names:
                if not name.endswith('.py'):
                    continue
                path = os.path.join(directory, name)
                files += 1
                try:
                    lines = open(path, encoding='utf-8').read().splitlines()
                except (OSError, UnicodeDecodeError):
                    continue
                for number, line in enumerate(lines, 1):
                    declared = DECLARATION.match(line)
                    if declared:
                        index[declared.group(1)].append(
                            ('def/class', f'{path}:{number}'))
                        continue
                    declared = FIELD_DECLARATION.match(line)
                    if declared:
                        index[declared.group(1)].append(
                            ('campo', f'{path}:{number}'))
    if require_files and not files:
        print('verify-premise: el índice midió 0 archivos. NO se emite un '
              'conteo — un 0 aquí no distingue «premisa firme» de «no pude '
              f'medir». Raíces pedidas: {[str(r) for r in roots]}',
              file=sys.stderr)
        raise SystemExit(2)
    return dict(index), files


def resolve_path(cited, path_roots=None):
    """Dónde existe la ruta citada, o ``None`` si en ninguna raíz."""
    roots = path_roots if path_roots is not None else _default_path_roots()
    for root in roots:
        if os.path.exists(os.path.join(root, cited)):
            return os.path.join(root, cited)
    return None


def _default_path_roots():
    """Este repo primero, y los clones hermanos que estén en el árbol."""
    repo = addons_roots.REPO_ROOT
    roots = [repo]
    for sibling in sorted(repo.parent.glob('kaupamex-*')):
        if sibling.is_dir() and sibling != repo:
            roots.append(sibling)
    return roots


def signals_for_text(text, symbols, tasks=None, path_roots=None):
    """Las señales de premisa envejecida de un texto, con su evidencia.

    Toma **texto**, no una ficha: así la misma medición sirve al tablero y al
    ``manifest.json`` de una pieza de ``scripts/workbench/`` (divergencia 4).
    """
    found = []

    if BUILD_VERB.search(text):
        seen = []
        for identifier in dict.fromkeys(BARE_IDENTIFIER.findall(text)):
            # El punto separa modelo de campo en la notación de la referencia
            # (``res.users``); el símbolo declarado en Python nunca lo lleva.
            name = (identifier.replace('.', '_') if '.' not in identifier
                    else identifier.split('.')[-1])
            for candidate in (identifier, name):
                where = symbols.get(candidate)
                if not where or candidate in seen:
                    continue
                # Un identificador declarado en muchos sitios es vocabulario
                # corriente del árbol, no la pieza que la premisa nombra.
                if len(where) > GENERIC_SYMBOL_THRESHOLD:
                    continue
                seen.append(candidate)
                kind, place = where[0]
                found.append((
                    'S1',
                    f'«{candidate}» ya está declarado ({kind}) — {place}'
                    + (f' (+{len(where) - 1} más)' if len(where) > 1 else '')))
                break

    for cited in dict.fromkeys(FILE_PATH.findall(text)):
        if resolve_path(cited, path_roots) is not None:
            continue
        if cited.split('/', 1)[0] not in OWN_ROOTS:
            # De un repo hermano que no está en el árbol: no poder decidir NO
            # es «no existe». Se calla.
            continue
        found.append(('S2', f'la ruta citada no existe: {cited}'))

    if tasks is not None:
        for _, blocker in BLOCKER_CITE.findall(text):
            blocking = tasks.get(blocker)
            if blocking is not None and blocking['status'] == DONE:
                found.append((
                    'S3',
                    f'su bloqueador #{blocker} ya está cerrado — '
                    f'{blocking["subject"][:52]}'))

    return found


def premise_of_manifest(path):
    """La premisa que un ``manifest.json`` declara: pregunta y premisa
    corregida, y nada más — ``metric`` y ``blind_to`` describen el instrumento.
    """
    try:
        declared = json.loads(open(path, encoding='utf-8').read())
    except (OSError, ValueError) as error:
        print(f'verify-premise: no se pudo leer {path}: {error}',
              file=sys.stderr)
        return ''
    partes = []
    for key in PREMISE_KEYS:
        value = declared.get(key)
        if isinstance(value, str):
            partes.append(value)
        elif isinstance(value, list):
            partes.extend(str(item) for item in value)
    return ' '.join(partes)


def newest_session_dir(root):
    """La sesión con más tareas — la activa, si hay varias en el disco."""
    if not os.path.isdir(root):
        return root
    candidates = [os.path.join(root, name) for name in os.listdir(root)]
    candidates = [c for c in candidates if os.path.isdir(c)]
    if not candidates:
        return root
    return max(candidates,
               key=lambda c: len(glob.glob(os.path.join(c, '*.json'))))


def load_tasks(source):
    """Las fichas del tablero, indexadas por su id como cadena.

    Una ficha ilegible se avisa por stderr en vez de desaparecer del universo
    con un ``continue`` silencioso, que es la forma pequeña del cero falso.
    """
    tasks = {}
    for path in sorted(glob.glob(os.path.join(source, '*.json'))):
        try:
            record = json.loads(open(path, encoding='utf-8').read())
        except (OSError, ValueError) as error:
            print(f'verify-premise: ficha ilegible {path}: {error}',
                  file=sys.stderr)
            continue
        if 'id' in record:
            tasks[str(record['id'])] = record
    return tasks


def workbench_manifests():
    """Los manifiestos de las piezas del banco, ordenados."""
    banco = addons_roots.REPO_ROOT / 'scripts' / 'workbench'
    return sorted(banco.glob('*/manifest.json'))


def report(label, status, title, found):
    """Imprime el veredicto de una premisa. Devuelve True si pide acción.

    En una tarea ya cerrada la señal S1 es **esperada** —su trabajo declaró
    esos símbolos— así que el veredicto lo dice en vez de presentarla como
    hallazgo. Sin esa distinción el guion daría por envejecida toda ficha
    cumplida, que es la lectura opuesta a la que existe para dar.
    """
    if not found:
        verdict = 'premisa firme'
    elif status == DONE:
        verdict = 'señal esperada (ya cerró: declaró esos símbolos)'
    else:
        verdict = 'RE-ENCUADRAR'
    print(f'{label} [{status}] {title[:64]}')
    print(f'   veredicto: {verdict}')
    for code, detail in found:
        print(f'   {code}  {detail}')
    return bool(found) and status != DONE


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('--task', nargs='*', metavar='ID',
                        help='ids de ficha del tablero')
    parser.add_argument('--tasks-dir', default=None,
                        help='directorio de fichas')
    parser.add_argument('--top', type=int,
                        help='verifica las N primeras no cerradas por id')
    parser.add_argument('--all', action='store_true',
                        help='verifica todas las fichas no cerradas')
    parser.add_argument('--manifest', nargs='*', metavar='RUTA',
                        help='manifiestos de pieza de banco')
    parser.add_argument('--workbench', action='store_true',
                        help='verifica todas las piezas del banco')
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 si alguna premisa tiene señal')
    args = parser.parse_args()

    symbols, files = build_symbol_index(require_files=True)
    print(f'verify-premise: índice de {len(symbols)} símbolos sobre {files} '
          f'archivos')

    premises = []
    if args.manifest or args.workbench:
        rutas = (args.manifest if args.manifest else workbench_manifests())
        for ruta in rutas:
            premises.append((f'banco:{os.path.basename(os.path.dirname(ruta))}',
                             'pieza', str(ruta),
                             premise_of_manifest(ruta), None))

    quiere_tablero = args.task is not None or args.top or args.all
    if quiere_tablero:
        tasks_dir = args.tasks_dir or newest_session_dir(
            os.path.expanduser('~/.claude/tasks'))
        tasks = load_tasks(tasks_dir)
        if not tasks:
            # Un tablero vacío es «nada que verificar», no un fallo: con exit
            # 1 quien lo invoque no podría distinguirlo de un guion que
            # reventó.
            print(f'verify-premise: sin tareas en {tasks_dir}')
        else:
            pending = sorted((i for i, t in tasks.items()
                              if t['status'] != DONE), key=int)
            if args.task:
                selected = [i for i in args.task if i in tasks]
                for absent in (i for i in args.task if i not in tasks):
                    print(f'#{absent} no está en el tablero')
            else:
                selected = pending if args.all else pending[:args.top or 10]
            for task_id in selected:
                task = tasks[task_id]
                text = f"{task.get('subject', '')} " \
                       f"{task.get('description', '') or ''}"
                premises.append((f'#{task_id}', task['status'],
                                 task.get('subject', ''), text, tasks))

    if not premises:
        parser.print_help()
        return 0

    print(f'verify-premise: {len(premises)} premisa(s) medida(s)')
    print()

    flagged = 0
    for label, status, title, text, tasks in premises:
        if report(label, status, title,
                  signals_for_text(text, symbols, tasks=tasks)):
            flagged += 1

    print()
    print(f'{flagged} de {len(premises)} premisa(s) piden re-encuadre antes '
          f'de despachar')
    if any(status == 'pieza' for _, status, _, _, _ in premises):
        print('   (en una pieza YA cerrada del banco, una señal S1 es la '
              'huella de su propio trabajo — ver «Ciega a» en el docstring)')
    return 1 if (args.strict and flagged) else 0


if __name__ == '__main__':
    sys.exit(main())
