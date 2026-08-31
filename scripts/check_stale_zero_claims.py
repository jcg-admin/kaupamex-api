#!/usr/bin/env python3
"""Gate — un reclamo de cero que un porte posterior dejó falso (#228).

El árbol declina portes con razones **medidas**, y las escribe citando su
propio comando::

    ``grep -rn "^class IrUiView" src/`` → **0**.

Esa forma es correcta al escribirse y **caduca sola**: el día que alguien
porta ``ir_ui_view.py``, la razón sigue en el docstring diciendo cero y ya no
lo es. Nadie lo nota, porque una frase dentro de un docstring no aparece en
ninguna lista de trabajo.

Este gate re-ejecuta cada comando citado y compara con el cero que la prosa
afirma. No interpreta la razón ni adivina qué símbolo se buscaba: **corre lo
que el texto dice haber corrido**, que es lo único que no puede equivocarse
sobre la intención del autor.

Los cuatro episodios de los que sale
====================================

Barriendo la prosa que declina un porte (#250), cuatro declinaciones seguidas
resultaron apoyarse en un cero caducado:

============  =================================================  ==============
Hallazgo      Reclamo                                            Medido después
============  =================================================  ==============
H-API-981     ``def _get_view`` da 0 en todo el árbol            **4**
H-API-982     ``ir.actions.actions`` no está portado             existe
H-API-983     ``ir.model.data`` "este árbol no tiene"            existe
H-API-984     el runner del cron "DIFERIDO"                      PORTADO
============  =================================================  ==============

Los cuatro se encontraron **leyendo**, archivo por archivo. Éste es el
instrumento que los ve sin leer.

Dos correcciones que la primera versión necesitó, y por qué
============================================================

La primera ejecución publicó **29 de 33** re-ejecutables como caducos. Esa
proporción era la señal: un instrumento que marca el 88 % de lo que mide se
está midiendo a sí mismo. Lo estaba, por dos vías distintas:

**La auto-coincidencia.** El docstring que cita ``grep -rln "…wkhtmltopdf…"
src/`` **vive dentro de** ``src/``. Al escribirse, el archivo aún no contenía
esa cadena y el conteo era cero honesto; hoy el grep encuentra su propia cita.
La re-ejecución descarta las líneas que apuntan al archivo que reclama —
reproduce la población que el autor midió, no una mayor.

**El conteo de ``grep -c``.** Su salida **es** el número, no las
coincidencias: ``grep -ic stdnum uv.lock`` imprime ``0`` en una línea, y
contar líneas da 1. Cinco reclamos se publicaron como caducos midiendo cero.
El modo ``-c`` se detecta y su salida se suma como entero.

Ambos son el sub-patrón A de ``metrica-decide-la-conclusion.md``: un
encabezado —«cuántas coincidencias»— sobre dos métricas distintas.

Qué NO puede ver
================

- **El reclamo sin comando.** H-API-982, H-API-983 y H-API-984 no citan un
  ``grep``: dicen "ya existe", "no tiene", "DIFERIDO". Este gate sólo alcanza
  la forma con comando — la de H-API-981. El resto sigue siendo trabajo de
  lectura (#250).
- **El comando contra la referencia.** Un ``grep`` sobre ``$ODOO19C`` mide el
  árbol de Odoo, no el nuestro: ahí un cero no caduca con nuestros portes. Se
  omiten y se cuentan aparte.
- **La prosa de OTRO archivo.** Se descarta la auto-coincidencia, no la cita
  que un tercer docstring hace del mismo término. Un conteo que sube por eso
  es un falso positivo que este guion no distingue de código real.
- **La razón detrás del cero.** Que el conteo suba no dice que la declinación
  esté mal — dice que **su premisa cambió** y hay que releerla. El veredicto
  es de quien la escribió, no de este guion.
"""
import argparse
import glob
import os
import pathlib
import re
import shlex
import subprocess
import sys

ROOTS = ('src', 'addons')

REPO = pathlib.Path(__file__).resolve().parents[1]

#: La deuda heredada se congela por ``archivo::comando``: el comando forma
#: parte de la clave porque reescribir la cita **es** el arreglo — un reclamo
#: re-medido con otro comando es otro reclamo, y vuelve a bloquear.
BASELINE = pathlib.Path(os.environ.get(
    'STALE_ZERO_BASELINE', REPO / 'scripts' / 'stale_zero_claims_baseline.txt'))

#: La cita y su cero, con la ventana entre los dos acotada: sin el límite, el
#: recorrido enlaza un ``grep`` con el ``**0**`` de tres párrafos más abajo.
CITATION = re.compile(r'``(grep\b[^`]{3,300}?)``[^\n]{0,90}?(?:da|→|->)\s*\*\*0\*\*',
                  re.S)

#: Un comando que apunta a OTRO árbol —la referencia, o el repo hermano de
#: ``ui``— no mide el nuestro: ahí un cero no caduca con nuestros portes.
ANOTHER_TREE = re.compile(
    r'\$?ODOO1[89][CE]|odoo1[89][ce]:|odoo-tools|\$ODOO|(?<![\w/])ui/', re.I)


def locate(command, raw, used):
    """La línea del archivo crudo donde vive esta cita, para poder abrirla.

    Se ancla en el **token más largo** del comando, no en su prefijo: un
    archivo con varias citas tiene varias que empiezan por ``grep -rn``, y
    anclarse ahí devuelve siempre la primera. El docstring además envuelve la
    cita en varias líneas, así que el comando completo no se busca entero.

    ``used`` retiene las líneas ya asignadas: un archivo puede repetir la
    misma cita —medido, dos lo hacen— y las dos apariciones son reclamos
    distintos que merecen su propia línea.
    """
    tokens = sorted(re.findall(r'[A-Za-z_][A-Za-z_0-9]{3,}', command),
                    key=len, reverse=True)
    lines = list(enumerate(raw.splitlines(), 1))
    # Primero la línea que trae el ``grep`` junto al token: es la cita misma.
    # Sólo si el docstring la envolvió y las separó se acepta el token solo.
    for require_grep in (True, False):
        for token in tokens[:3]:
            for i, text in lines:
                if i in used or token not in text:
                    continue
                if require_grep and 'grep' not in text:
                    continue
                used.add(i)
                return i
    return 0


def claims_in(path):
    """Cada ``(comando, linea, cita)`` que el archivo declara con cero.

    El texto se aplana antes de buscar: la cita se parte en varias líneas
    cuando el docstring la envuelve, y un patrón por línea la perdería.

    La **cita entera** viaja junto al comando porque el árbol que se midió no
    siempre está dentro del comando: ``grep -rn "…" `` sobre ``odoo19c:`` da
    **0** declara su población en la prosa que une las dos partes. Medirla
    sólo por el comando la re-ejecuta contra el árbol equivocado.
    """
    raw = path.read_text(errors='ignore')
    flat = re.sub(r'\n\s*#?:?\s*', ' ', raw)
    found, used = [], set()
    for match in CITATION.finditer(flat):
        command = ' '.join(match.group(1).split())
        found.append((command, locate(command, raw, used), match.group(0)))
    return found


def lists_files_only(parts):
    """¿El comando pide ``-l``? Entonces no emite líneas, sólo rutas.

    Se le quita la ``l`` para poder leer el texto de cada coincidencia — sin
    él no hay forma de distinguir la línea que **cita** el comando de la que
    lo contradice — y el conteo vuelve a rutas distintas al final.
    """
    for i, token in enumerate(parts):
        if token.startswith('-') and not token.startswith('--') and 'l' in token[1:]:
            without_l = '-' + token[1:].replace('l', '')
            return i, (without_l if len(without_l) > 1 else None)
    return None, None


def counts_instead_of_matching(parts):
    """¿El comando pide ``-c``? Entonces su salida ES el número.

    ``--include=*.py`` empieza con dos guiones y nunca es una bandera corta;
    ``-ic``, ``-ci`` y ``-rc`` sí llevan la ``c`` agrupada.
    """
    for token in parts:
        if token == '--count':
            return True
        if token.startswith('-') and not token.startswith('--'):
            if 'c' in token[1:]:
                return True
    return False


def is_its_own_citation(line, claiming):
    """¿Esta coincidencia es el reclamo repitiéndose a sí mismo?

    El docstring que cita ``grep -rn "…" src/`` **vive dentro de** ``src/``, y
    al escribirse la cita el archivo aún no la contenía: hoy el grep encuentra
    su propio texto. Esa línea no es evidencia de nada.

    La exclusión es por **línea de cita**, no por archivo. Un archivo que
    declina portar algo y **luego lo porta** contradice su propia prosa desde
    su propio código — que es el caso más interesante de todos — y excluirlo
    entero lo silenciaría. El discriminador es el literal RST: toda cita de
    este árbol va entre dobles acentos graves; ninguna línea de código los
    lleva.
    """
    path, _, text = line.partition(':')
    if path != str(claiming):
        return False
    return '``' in text


def rerun(command, claiming):
    """Corre el comando citado y devuelve cuántas coincidencias emite.

    Sin shell: la cadena viene de nuestro propio árbol, pero un ``grep`` con
    comodines no necesita intérprete y no dárselo cierra la vía entera.

    Devuelve ``(conteo, None)`` o ``(None, motivo)`` cuando no se puede
    correr — el motivo se agrega para que la ceguera del guion quede medida
    y no como un cubo sin nombre.
    """
    try:
        parts = shlex.split(command)
    except ValueError:
        return None, 'comilla sin cerrar'
    if any(p in ('&&', ';', '>') for p in parts):
        return None, 'encadenamiento'

    # ``grep … | grep -v X`` — la forma que dos autores ya escribieron a mano
    # para excluir su propio archivo. Se sostiene el filtro en Python en vez
    # de dar un intérprete al comando.
    excluded = []
    while '|' in parts:
        cut = parts.index('|')
        tail = parts[cut + 1:]
        parts = parts[:cut]
        if len(tail) < 3 or tail[0] != 'grep' or '-v' not in tail[1]:
            return None, 'tubería que no es `grep -v`'
        excluded.append(tail[-1])

    # El shell expande ``src/orm/*.py``; sin shell, grep recibe el asterisco
    # literal y sale 2. Se expande aquí, y un patrón sin correspondencia se
    # deja tal cual para que el grep lo reporte como el archivo ausente que es.
    parts = [x for p in parts
             for x in (sorted(glob.glob(p)) or [p])
             if not (p.startswith('-') and p != x)]

    # ``-l`` sólo emite rutas; para separar la cita de su contradicción hace
    # falta el texto de cada línea, así que se le retira y se reagrupa después.
    position, without_l = lists_files_only(parts)
    paths_only = position is not None
    if paths_only:
        parts = parts[:position] + ([without_l] if without_l else []) + parts[position + 1:]

    try:
        done = subprocess.run(parts, capture_output=True, text=True,
                              timeout=60)
    except FileNotFoundError:
        return None, 'ejecutable ausente'
    except subprocess.TimeoutExpired:
        return None, 'excede el tiempo'
    except (OSError, subprocess.SubprocessError) as error:
        return None, type(error).__name__
    if done.returncode not in (0, 1):
        if 'No such file' in done.stderr:
            return None, 'la ruta citada ya no existe'
        return None, f'grep sale {done.returncode}'

    lines = [l for l in done.stdout.splitlines() if l.strip()]
    if paths_only:
        lines = [l for l in lines if not is_its_own_citation(l, claiming)]
        return len({l.split(':', 1)[0] for l in lines}), None
    for pattern in excluded:
        lines = [l for l in lines if pattern not in l]
    if counts_instead_of_matching(parts):
        total = 0
        for line in lines:
            # ``path:N`` cuando son varios archivos; ``N`` a secas con uno.
            digits = line.rsplit(':', 1)[-1].strip()
            if digits.isdigit():
                total += int(digits)
        return total, None

    return len([l for l in lines if not is_its_own_citation(l, claiming)]), None


def load_baseline():
    if not BASELINE.is_file():
        return set()
    return {line.strip() for line in BASELINE.read_text().splitlines()
            if line.strip() and not line.startswith('#')}


def python_files(only=()):
    """Los ``.py`` a inspeccionar: los que se pasen, o las dos raíces enteras.

    El **alcance del reclamo** y el **alcance del comando** son distintos: un
    pre-commit acota de qué archivos se leen las citas, nunca sobre qué árbol
    barre el grep que citan — reducir eso segundo mediría otra cosa.
    """
    if only:
        return [p for p in (pathlib.Path(x) for x in only)
                if p.suffix == '.py' and p.is_file()]
    return [p for root in ROOTS
            for p in sorted(pathlib.Path(root).rglob('*.py'))]


def survey(only=()):
    """Cada reclamo medido, con su conteo de hoy y el reparto del alcance."""
    claims, skipped, stale, unrunnable = 0, 0, [], []
    for path in python_files(only):
        for command, line, quote in claims_in(path):
            claims += 1
            if ANOTHER_TREE.search(quote):
                skipped += 1
                continue
            count, why = rerun(command, path)
            if count is None:
                unrunnable.append((path, line, why))
            elif count > 0:
                stale.append((path, line, command, count))
    return claims, skipped, stale, unrunnable


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 si hay un reclamo caducado fuera del baseline')
    parser.add_argument('--verbose', action='store_true',
                        help='nombra también los que este guion no sabe correr')
    parser.add_argument('--write-baseline', action='store_true',
                        help='congela la deuda heredada de hoy')
    parser.add_argument('files', nargs='*',
                        help='acota de qué archivos se leen las citas')
    args = parser.parse_args()

    claims, skipped, stale, unrunnable = survey(args.files)
    # El rehúse sólo aplica al barrido del árbol. Con una lista de archivos
    # explícita —que es como lo invoca el `pre-commit`— un cero es un
    # resultado legítimo: esos archivos no citan ningún cero. Rehusar ahí
    # bloquea todo commit que no toque prosa de porte, y eso no mide nada.
    if claims == 0 and not args.files:
        print('ERROR — 0 reclamos de cero encontrados. El recorrido no puede '
              'estar midiendo el árbol: publicar "0 caducados" aquí sería un '
              'verde falso. Revisar el patrón antes de confiar en la cifra.',
              file=sys.stderr)
        return 2

    if args.write_baseline:
        if args.files:
            print('ERROR — el baseline se escribe sobre el árbol entero. Uno '
                  'derivado de un subconjunto borraría la deuda que no midió.',
                  file=sys.stderr)
            return 2
        BASELINE.write_text(
            '# Reclamos de cero que un porte dejó falsos, congelados como deuda\n'
            '# heredada. Uno listado no bloquea; uno nuevo sí. Se paga al tocar\n'
            '# el archivo — el triaje es la tarea #250.\n'
            '# Clave: <archivo>::<comando citado>\n'
            + ''.join(f'{path}::{command}\n'
                      for path, _, command, _ in sorted(stale)))
        print(f'baseline escrito: {len(stale)} reclamo(s)')
        return 0

    baseline = load_baseline()
    fresh = [row for row in stale if f'{row[0]}::{row[2]}' not in baseline]

    for path, line, command, count in fresh:
        print(f'{path}:{line}  el reclamo dice 0 y hoy da {count}\n'
              f'    {command}')

    if unrunnable and args.verbose:
        print('\nfuera del alcance de este guion:')
        for path, line, why in unrunnable:
            print(f'  {path}:{line}  {why}')

    runnable = claims - skipped - len(unrunnable)
    print(f'{len(fresh)} reclamo(s) de cero caducado(s) fuera del baseline'
          f'  ·  en baseline: {len(stale) - len(fresh)}'
          f'  (alcance medido: {claims} cita(s) con comando; '
          f'{runnable} re-ejecutable(s), {skipped} contra otro árbol, '
          f'{len(unrunnable)} que este guion no sabe correr)')
    return 1 if (fresh and args.strict) else 0


if __name__ == '__main__':
    sys.exit(main())
