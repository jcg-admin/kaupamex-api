#!/usr/bin/env python3
"""Gate: una marca de bloqueo cuya causa ya existe está CADUCADA.

``check_bloqueo_declarado.py`` mide la **forma** de la marca y declara su
propia ceguera: *"que el ``code-span`` nombre un símbolo que exista de verdad:
el gate lee la forma, no resuelve el destino"*. Este guion resuelve el destino.

El defecto que cierra
=====================

Una marca de bloqueo se lee como una propiedad del símbolo —*"esto no se puede
portar"*— y en realidad es una **afirmación de estado fechada**: dice que en un
momento dado faltaba un destino. Su verdad depende de un árbol que cambia en
cada pase, así que **envejece sola y en silencio**. Nada falla, nada se pone en
rojo, y el símbolo deja de portarse para siempre.

Y es peor que un hueco sin declarar, porque el hueco declarado **sale de la
lista de pendientes**: el gate de forma lo cuenta como marca válida y el de
porte lo absuelve.

Episodio que lo origina (:ref:`h-api-1021`): ``image_shape`` de ``html_editor``
estaba bloqueado por tres símbolos de ``tools/image.py`` *"que este árbol no
tiene"*. La tarea #285 los portó. Nadie re-midió la marca, y el símbolo siguió
sin portar hasta que un pase posterior tropezó con él por casualidad.

Qué se resuelve, y qué se declara NO MEDIBLE
=============================================

El destino de una arista es texto libre dentro de un ``code-span``, así que no
todos se pueden resolver. Resolver de más es peor que no resolver: un ``0``
falso de caducadas es un verde que no discrimina, y un ``journal`` que existe
en cuarenta archivos daría por caducada una marca viva.

Sólo se resuelven las cuatro formas cuyo destino es inequívoco:

=====================  ==========================================  =========================
Forma                  Ejemplo                                     Cómo se resuelve
=====================  ==========================================  =========================
addon                  ``calendar``                                ``addons/<x>/`` existe
modelo                 ``mail.ice.server``                         algún ``_name = '<x>'``
modelo + símbolo       ``ir.ui.view.save``                         el ``_name`` y el ``def``
ruta                   ``src/addons/base/migrations``              **sólo en negativo**
=====================  ==========================================  =========================

La cuarta fila resuelve **sólo hacia «viva»**: una ruta que no existe confirma
el bloqueo, pero una que sí existe no lo levanta. Medido: la marca de
``html_editor/models/ir_attachment.py`` nombra ``src/addons/base/migrations``,
que existe desde siempre, porque su bloqueo es de **alcance** —el ``AddField``
aterriza en la migración de otro puerto— y no de artefacto ausente. Contarla
como caducada habría sido el primer falso positivo del guion, y un guion que
absuelve por error es peor que ninguno.

Todo lo demás —un nombre de campo suelto (``so_line``), una clase sin su
modelo (``ResConfigSettings``), o prosa (``el motor de compute``)— sale como
**NO MEDIBLE** y se cuenta aparte. No es un fallo del árbol: es el alcance de
este instrumento, y publicarlo es lo que impide leer su cero como cobertura.

Qué decide que algo es un modelo o un addon: **la referencia**, no este árbol.
Sin ese filtro, cualquier par de palabras en minúsculas separadas por un punto
—``self.env``, ``partner.company_id``— entraba como modelo y salía como bloqueo
VIVO. Nunca absolvía de más, pero inflaba el conteo de vivas y vaciaba el de no
medibles, que es el denominador con que se lee la cobertura del guion.

La clave del baseline es ``ruta::destino``, no la línea: el número de línea se
mueve con cualquier edición y el destino no. Esa elección **funde las
repeticiones** del mismo destino en el mismo archivo — medido al congelar, 30
marcas caducadas colapsan en 19 claves. Corregir una de un grupo deja las otras
sin bloquear hasta que su destino cambie; por eso el resumen publica las dos
cifras.

Uso:
    check_bloqueo_vigente.py                    # todo el árbol
    check_bloqueo_vigente.py --quiet            # sólo el conteo de caducadas
    check_bloqueo_vigente.py --strict           # exit 1 si hay caducadas nuevas
    check_bloqueo_vigente.py --write-baseline   # congela las caducadas de hoy
"""
import argparse
import functools
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_bloqueo_declarado as forma
import reference_roots

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'bloqueo_vigente_baseline.txt')

#: El último ``code-span`` de la arista es el destino. La expresión de la
#: arista ya garantiza que hay al menos uno.
SPAN = re.compile(r'``([^`]+)``')

#: Un nombre de modelo: minúsculas y puntos, al menos dos segmentos. Excluye
#: CamelCase (``ResConfigSettings``) y los nombres de un solo segmento, que
#: son campos y no modelos.
MODEL_NAME = re.compile(r'^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$')

#: Un addon: un solo segmento en minúsculas, sin puntos ni barras.
ADDON_NAME = re.compile(r'^[a-z][a-z0-9_]*$')

#: Modelo + símbolo: el modelo en minúsculas y el último segmento con guion
#: bajo inicial o en minúsculas. ``ir.ui.view.save``, ``ir.module.module.imported``.
MODEL_AND_SYMBOL = re.compile(
    r'^(?P<modelo>[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)\.(?P<simbolo>_?[a-z][a-z0-9_]*)$')

RAICES = ('src', 'addons')


@functools.lru_cache(maxsize=1)
def declared_model_names():
    """Todo ``_name = '<x>'`` del árbol, por AST no: por literal.

    El literal basta y es cien veces más barato: ``_name`` se declara siempre
    como constante de cadena en una línea, y un falso positivo aquí sólo puede
    venir de una cadena que diga ``_name = '...'`` sin serlo.
    """
    patron = re.compile(r"^\s*_name\s*=\s*['\"]([^'\"]+)['\"]", re.M)
    nombres = set()
    for raiz in RAICES:
        for base, dirs, files in os.walk(raiz):
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
            for nombre in files:
                if not nombre.endswith('.py'):
                    continue
                ruta = os.path.join(base, nombre)
                try:
                    texto = open(ruta, encoding='utf-8').read()
                except (OSError, UnicodeDecodeError):
                    continue
                nombres.update(patron.findall(texto))
    return frozenset(nombres)


DEF = re.compile(r'^\s*(?:async\s+)?def\s+(\w+)', re.M)

#: Una clave instalada por ``extend_model``: ``'nombre': funcion``. El gate de
#: porte lee esto por AST; aquí basta el literal, porque sólo se consulta en
#: los archivos que ya se sabe que son de ese modelo.
INSTALLED_KEY = re.compile(r"^\s*'([A-Za-z_]\w*)'\s*:", re.M)


@functools.lru_cache(maxsize=1)
def _model_files():
    """``_name`` -> los archivos que lo declaran o lo extienden.

    Es la pieza que hace estrecha la forma «modelo + símbolo». Un conjunto de
    ``def`` de todo el árbol **sobre-resuelve**: medido, ``_render_template``
    existe —en ``ir.actions.report``— y ``ir.ui.view._render_template`` seguía
    bloqueado igual. Preguntarle al árbol entero daba por caducadas once
    marcas vivas, incluida la que la tarea #274 declara como su bloqueo raíz.
    """
    declara = re.compile(r"^\s*_name\s*=\s*['\"]([^'\"]+)['\"]", re.M)
    extiende = re.compile(r"extend_model\(\s*['\"]([^'\"]+)['\"]")
    mapa = {}
    for raiz in RAICES:
        for base, dirs, files in os.walk(raiz):
            dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
            for nombre in files:
                if not nombre.endswith('.py'):
                    continue
                ruta = os.path.join(base, nombre)
                try:
                    texto = open(ruta, encoding='utf-8').read()
                except (OSError, UnicodeDecodeError):
                    continue
                for modelo in set(declara.findall(texto)) | set(extiende.findall(texto)):
                    mapa.setdefault(modelo, []).append(ruta)
    return mapa


def symbols_of_model(modelo):
    """Los símbolos que este árbol cuelga de ``modelo``, por sus archivos.

    *Métrica:* ``def <nombre>`` y claves de diccionario de instalación en los
    archivos que declaran ``_name = '<modelo>'`` o llaman
    ``extend_model('<modelo>', …)``.
    *Ciega a:* un símbolo que llegue por herencia de una clase base —el
    ``save`` de Django está en todos los modelos y no aparece aquí—, y a una
    instalación cuyo receptor no sea literal, que es la misma ceguera que
    :ref:`h-api-1022` registra para el gate de porte. Las dos empujan hacia
    «bloqueo vivo», que es el lado seguro.
    """
    simbolos = set()
    for ruta in _model_files().get(modelo, ()):
        try:
            texto = open(ruta, encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue
        simbolos.update(DEF.findall(texto))
        simbolos.update(INSTALLED_KEY.findall(texto))
    return simbolos


@functools.lru_cache(maxsize=1)
def _reference_root():
    """La raiz de ``odoo19c``, por el modulo que ya declara las raices.

    No se teclea la ruta larga: el arbol esta triplicado en ``odoo-tools`` por
    un artefacto de empaquetado, y una copia de esa ruta aqui seria la segunda
    fuente de verdad que ``calibration-verified-numbers.md`` prohibe.
    """
    return str(reference_roots.tree('odoo19c'))


@functools.lru_cache(maxsize=1)
def reference_model_names():
    """Los ``_name`` que declara la REFERENCIA, no este arbol.

    Es el discriminador de «esto es un modelo». Sin el, cualquier par de
    palabras en minusculas separadas por un punto —``self.env``,
    ``partner.company_id``— entraba como modelo y salia como bloqueo VIVO:
    nunca absolvia de mas, pero inflaba el conteo de vivas y vaciaba el de no
    medibles, que es el denominador con que se lee la cobertura del guion.

    Medido: 1351 nombres distintos en 8566 archivos, en 0.6 s.
    """
    patron = re.compile(r"^\s*_name\s*=\s*['\"]([^'\"]+)['\"]", re.M)
    nombres = set()
    for base, dirs, files in os.walk(_reference_root()):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
        for nombre in files:
            if not nombre.endswith('.py'):
                continue
            try:
                texto = open(os.path.join(base, nombre),
                             encoding='utf-8', errors='ignore').read()
            except OSError:
                continue
            nombres.update(patron.findall(texto))
    return frozenset(nombres)


@functools.lru_cache(maxsize=1)
def reference_addons():
    """Los addons que declara la referencia. Discrimina «addon» de «campo».

    ``so_line`` y ``journal`` son nombres de campo y encajan igual de bien que
    ``calendar`` en la forma «una palabra en minusculas». Lo que los separa es
    que uno es un directorio de la referencia y los otros no.
    """
    # Community declara DOS raices de addon —``addons/`` y ``odoo/addons/``—
    # y ``base`` vive en la segunda. Mirar solo la primera dejaria fuera al
    # addon del que cuelga todo el arranque.
    nombres = set()
    for raiz in reference_roots.addons_de('odoo19c'):
        if not os.path.isdir(raiz):
            continue
        nombres.update(d for d in os.listdir(raiz)
                       if os.path.isdir(os.path.join(raiz, d)))
    return frozenset(nombres)


def resolve(destino):
    """``(estado, explicacion)`` del destino de una arista.

    ``estado`` es ``'existe'``, ``'falta'`` o ``'no-medible'``. El tercero no
    es un fallo: es la declaración de que este instrumento no alcanza esa
    forma, y se publica junto al conteo para que su cero no se lea como
    cobertura.
    """
    d = destino.strip()

    if '/' in d:
        # La ruta resuelve SOLO en negativo. Que exista no dice que el bloqueo
        # se haya levantado: medido, la marca de ``html_editor`` nombra
        # ``src/addons/base/migrations`` —que existe desde siempre— porque su
        # bloqueo es de ALCANCE (la migracion es de otro puerto), no de
        # artefacto ausente. Leer esa existencia como caducidad es el falso
        # positivo que este guion no puede permitirse.
        if not os.path.exists(d.rstrip('/')):
            return 'falta', f'la ruta {d} no existe'
        return 'no-medible', f'la ruta {d} existe, y eso no levanta el bloqueo'

    m = MODEL_AND_SYMBOL.match(d)
    if (m and m.group('modelo') in reference_model_names()
            and m.group('modelo') in declared_model_names()):
        modelo, simbolo = m.group('modelo'), m.group('simbolo')
        if simbolo in symbols_of_model(modelo):
            return 'existe', f'{modelo} declara {simbolo}'
        return 'falta', f'{modelo} existe, sin {simbolo}'

    if MODEL_NAME.match(d) and d in reference_model_names():
        if d in declared_model_names():
            return 'existe', f'_name = {d!r}'
        return 'falta', f'ningun _name declara {d!r}'

    if ADDON_NAME.match(d) and d in reference_addons():
        ruta = os.path.join('addons', d)
        if os.path.isdir(ruta):
            return 'existe', f'{ruta}/ existe'
        return 'falta', f'{ruta}/ no existe'

    return 'no-medible', 'la forma del destino no se resuelve'


def edges(paths):
    """Las aristas bien formadas del árbol, con su destino."""
    salida = []
    for ruta in forma.source_files(paths):
        try:
            lineas = open(ruta, encoding='utf-8').read().split('\n')
        except (OSError, UnicodeDecodeError):
            continue
        for n, linea in enumerate(lineas, 1):
            if not forma.MARKER.search(linea):
                continue
            texto = linea
            if not forma.EDGE.search(texto):
                texto = forma.join_wrapped(
                    linea, lineas[n] if n < len(lineas) else '')
            m = forma.EDGE.search(texto)
            if not m:
                continue
            spans = SPAN.findall(m.group(0))
            if spans:
                salida.append((ruta, n, spans[-1], linea.strip()))
    return salida


def load_baseline():
    if not os.path.exists(BASELINE):
        return set()
    with open(BASELINE, encoding='utf-8') as handle:
        return {row.strip() for row in handle
                if row.strip() and not row.startswith('#')}


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('paths', nargs='*')
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--strict', action='store_true')
    parser.add_argument('--write-baseline', action='store_true')
    args = parser.parse_args(argv)

    aristas = edges(args.paths)
    caducadas, vivas, no_medibles = [], 0, 0
    for ruta, n, destino, texto in aristas:
        estado, porque = resolve(destino)
        if estado == 'existe':
            caducadas.append((f'{ruta}::{destino}', ruta, n, destino, porque, texto))
        elif estado == 'falta':
            vivas += 1
        else:
            no_medibles += 1

    if args.write_baseline:
        with open(BASELINE, 'w', encoding='utf-8') as handle:
            handle.write(
                '# Marcas de bloqueo cuya causa YA existe en el arbol.\n'
                '# Una listada no bloquea; una NUEVA si. Se paga al tocar el\n'
                '# archivo: se retira la marca y se porta el simbolo, o se\n'
                '# reescribe la marca con la causa que de verdad falta.\n')
            for clave, *_ in sorted(caducadas):
                handle.write(clave + '\n')
        print(f'baseline escrito: {len(caducadas)} marca(s) caducada(s) '
              f'(alcance medido: {len(aristas)} aristas)')
        return 0

    baseline = load_baseline()
    nuevas = [c for c in caducadas if c[0] not in baseline]

    if args.quiet:
        print(len(nuevas))
        return 1 if (nuevas and args.strict) else 0

    for _, ruta, n, destino, porque, texto in nuevas:
        print(f'{ruta}:{n}: bloqueo CADUCADO — su causa ya existe ({porque})')
        print(f'    {texto[:110]}')
    if nuevas:
        print()
        print('  Una marca caducada se resuelve de dos formas, no de tres:')
        print('    portar el simbolo, ahora que su destino existe; o')
        print('    reescribir la marca con la causa que de verdad falta.')
    veredicto = 'FALLA' if (nuevas and args.strict) else 'OK'
    claves = len({c[0] for c in caducadas})
    print(f'{veredicto}: {len(nuevas)} marca(s) caducada(s) nueva(s) '
          f'· {len(caducadas)} caducada(s) en {claves} clave(s) '
          f'· {vivas} viva(s) · {no_medibles} de forma no medible '
          f'(alcance medido: {len(aristas)} aristas bien formadas; '
          f'{len(baseline)} clave(s) en baseline)')
    return 1 if (nuevas and args.strict) else 0


if __name__ == '__main__':
    sys.exit(main())
