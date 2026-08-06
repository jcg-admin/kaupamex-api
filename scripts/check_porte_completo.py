#!/usr/bin/env python3
"""Mide la cobertura de símbolos de cada puerto contra su archivo de referencia.

Origen: directiva del ejecutor 2026-08-06 — *"¿se están integrando todas las
clases y métodos completos de los archivos de la referencia?"*. La respuesta
medida era **no se verifica**: había gates de layout, nombres, ciclos e
``_inherits``, pero ninguno que comparara los símbolos. ``porte-completo-no-parcial.md``
pide mecanizar la métrica cuando se pueda; esto lo hace.

Qué mide
--------

Empareja ``src/addons/<addon>/**/<archivo>.py`` con el mismo camino bajo el
árbol de la referencia y clasifica **cada archivo de la referencia** en uno de
tres estados:

- ``COMPLETO`` — todas sus clases y métodos tienen homólogo aquí;
- ``PARCIAL`` — el archivo existe pero le faltan clases o métodos;
- ``NO PORTADO`` — ninguna de sus clases existe en el addon.

El tercer estado es el que importa declarar: una primera versión de este gate
**saltaba** los archivos sin contraparte, así que su denominador era la
intersección y lo más ausente de todo le resultaba invisible. Es la ceguera
que ``metrica-decide-la-conclusion.md`` describe, aplicada al instrumento.

Medido 2026-08-06 sobre los 79 addons compartidos: **638 archivos de
referencia** — 11 completos, 147 parciales, 480 sin portar.

Esa cifra corrige una anterior (15 / 141 / 482): la rama de "archivo sin
contraparte" comparaba **sólo nombres de clase**, así que un archivo que en la
referencia extiende (``_inherit``) una clase ya portada salía COMPLETO con cero
métodos portados. El caso que lo destapó —``account_journal_dashboard.py``, 50
métodos allá y 0 aquí— es el peor error posible en un instrumento de cobertura:
un COMPLETO falso. Ver :ref:`h-api-350`.

Qué NO puede ver
-----------------

- Un método presente con el mismo nombre pero que **hace menos** — el conteo
  generoso que ``porte-completo-no-parcial.md`` documenta. Este gate mide
  nombres, no comportamiento.
- Un símbolo portado a **otro archivo** del mismo addon. Por eso el
  emparejamiento es por addon, no por archivo: se buscan los nombres en TODO
  el addon antes de declararlos ausentes. El precio de esa tolerancia es que
  el gate **no ve el sitio de declaración** — una función suelta donde la
  referencia tiene un método de clase pasa el conteo. Sucesor #159.
- Un renombre que el mapa de alias no declare. Los renombres conocidos van en
  ``PORTE_ALIAS``; lo no declarado sale como ausente, que es el lado seguro.

Uso
---

    python3 scripts/check_porte_completo.py                  # reporte
    python3 scripts/check_porte_completo.py --addon account  # un addon
    python3 scripts/check_porte_completo.py --mapa           # inventario por archivo
    python3 scripts/check_porte_completo.py --quiet          # sólo el conteo
    python3 scripts/check_porte_completo.py --strict         # exit 1 si hay ausentes
"""
import argparse
import ast
import os
import pathlib
import sys

#: Raíz del árbol que gobierna (``odoo19c``). Ver
#: ``referencia-odoo-gobierna-las-decisiones.md``: 19 desempata, y las rutas de
#: una versión NO son válidas en la otra.
ODOO19C = pathlib.Path(
    os.environ.get(
        'ODOO19C',
        '/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0',
    )
)

SRC = pathlib.Path(__file__).resolve().parent.parent / 'src' / 'addons'

#: Renombres declarados: ``nombre en la referencia -> nombre aquí``. Cada
#: entrada es una decisión, no una conveniencia — si el nombre cambió sin
#: motivo, la entrada correcta es arreglar el nombre, no añadir el alias.
PORTE_ALIAS = {
    # El prefijo ``action_`` de la referencia marca lo invocable desde su UI;
    # aquí no hay esa UI, así que el método se llama por lo que hace.
    'action_set_manual': 'set_manual',
    'action_set_auto_reconcile': 'set_auto_reconcile',
    # ``_compute_<campo>`` es la convención de su ORM para un campo calculado.
    '_compute_partner_mapping': 'compute_mapped_partner',
    # El cargador no es un modelo aquí, así que no lleva el prefijo del addon.
    'AccountChartTemplate': 'ChartTemplate',
}


def simbolos(ruta):
    """``{clase: {métodos}}`` de un archivo Python, o ``None`` si no parsea."""
    try:
        arbol = ast.parse(ruta.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return None
    return {
        n.name: {m.name for m in n.body
                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for n in arbol.body if isinstance(n, ast.ClassDef)
    }


def simbolos_del_addon(raiz):
    """Todos los símbolos del addon, para no declarar ausente lo que se movió.

    Recoge funciones a nivel de módulo **además** de métodos de clase, y eso es
    una concesión de alcance, no una justificación: un símbolo que la
    referencia declara dentro de una clase y aquí vive suelto **es una
    divergencia**, no una equivalencia. La primera versión de este docstring
    la excusaba con "su ORM lo exige"; era una racionalización — explicaba por
    qué la referencia lo hace así, no por qué nosotros lo haríamos distinto. Si
    Django no ofrece el mecanismo, se analiza y se construye (precedentes:
    ``api.depends``, ``fields``, ``Command``, ``_inherits``, ``sequence.mixin``).
    El caso que la motivó —las plantillas de ``template_base.py``— se corrigió
    moviéndolas a ``ChartTemplate``, donde la referencia las tiene.

    Se conserva el barrido de funciones sueltas, pero **ya no absuelve**: desde
    #159 un símbolo que existe aquí fuera de la clase que le toca se reporta
    como ``FUERA DE SITIO``, no se descarta. Este conjunto pasó de ser el
    criterio de "está portado" a ser el que distingue *portado en otro sitio*
    de *ausente del todo* — dos estados que el gate devolvía como uno solo.
    """
    todos = set()
    for py in raiz.rglob('*.py'):
        if 'migrations' in py.parts or '__pycache__' in py.parts:
            continue
        try:
            arbol = ast.parse(py.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        for n in ast.walk(arbol):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                todos.add(n.name)
    return todos


def clases_del_addon(raiz):
    """``{clase_normalizada: {métodos}}`` de TODO el addon.

    Un archivo de la referencia puede estar portado **repartido** en varios
    archivos nuestros; buscar la clase en todo el addon antes de declararla
    ausente evita contar como no-portado lo que sólo cambió de casa.

    Devuelve **los métodos, no sólo el nombre**. Una versión anterior devolvía
    un conjunto de nombres, y con eso la rama de "archivo sin contraparte"
    declaraba COMPLETO cualquier archivo cuyas clases existieran aquí —
    aunque no se hubiera portado ni un método. Medido sobre
    ``account_journal_dashboard.py``: **50 métodos** en la referencia, **0**
    portados, y el gate lo daba por completo, porque su clase ``AccountJournal``
    existe en otro archivo. Es un COMPLETO falso, la forma más cara de error en
    un instrumento de cobertura. Ver :ref:`h-api-350`.
    """
    por_clase = {}
    for py in raiz.rglob('*.py'):
        if 'migrations' in py.parts or '__pycache__' in py.parts:
            continue
        for clase, metodos in (simbolos(py) or {}).items():
            por_clase.setdefault(normaliza(clase), set()).update(metodos)
    return por_clase


def normaliza(nombre):
    """El nombre comparable: alias declarado, y sin guiones bajos de borde."""
    return PORTE_ALIAS.get(nombre, nombre).strip('_')


def compara(addon):
    """Devuelve ``(pares_medidos, [hallazgo, ...])`` para un addon."""
    ref_raiz = ODOO19C / 'addons' / addon
    mio_raiz = SRC / addon
    if not ref_raiz.is_dir() or not mio_raiz.is_dir():
        return 0, []

    propios = {normaliza(x) for x in simbolos_del_addon(mio_raiz)}
    por_clase = clases_del_addon(mio_raiz)
    pares, hallazgos = 0, []

    for ref_py in sorted((ref_raiz / 'models').glob('*.py')):
        if ref_py.name == '__init__.py':
            continue
        mio_py = mio_raiz / 'models' / ref_py.name
        if not mio_py.exists():
            # Un archivo sin contraparte NO se salta: saltarlo dejaba el
            # denominador en la intersección, que es la ceguera que
            # ``metrica-decide-la-conclusion.md`` describe — el instrumento no
            # veía lo más ausente de todo. Se busca por nombre de clase en todo
            # el addon, porque un puerto puede repartir un archivo en varios.
            #
            # Y se comparan **los métodos**, no sólo el nombre de la clase: en
            # la referencia muchos archivos son extensiones (``_inherit``) de
            # una clase que aquí ya existe, así que casar por nombre los daba
            # por completos con cero métodos portados.
            pares += 1
            ref_clases = simbolos(ref_py) or {}
            # Si NINGUNA de sus clases existe aquí, el archivo entero está sin
            # portar; si alguna existe, es una extensión (``_inherit``) cubierta
            # a medias. Los dos estados se cuentan distinto en el mapa.
            if ref_clases and not any(
                    normaliza(c) in por_clase for c in ref_clases):
                hallazgos.append(
                    (addon, ref_py.name, '(archivo)', 'ARCHIVO NO PORTADO',
                     sorted(ref_clases)))
                continue
            for clase, metodos in ref_clases.items():
                aqui = por_clase.get(normaliza(clase))
                if aqui is None:
                    hallazgos.append(
                        (addon, ref_py.name, clase, 'CLASE AUSENTE',
                         sorted(metodos)))
                    continue
                aqui_norm = {normaliza(m) for m in aqui}
                faltan = [m for m in sorted(metodos)
                          if normaliza(m) not in aqui_norm]
                if faltan:
                    hallazgos.append(
                        (addon, ref_py.name, clase, 'MÉTODOS AUSENTES', faltan))
            continue
        pares += 1
        ref_clases = simbolos(ref_py) or {}
        mias = simbolos(mio_py) or {}
        mias_norm = {normaliza(c): ms for c, ms in mias.items()}

        for clase, metodos in ref_clases.items():
            aqui = mias_norm.get(normaliza(clase))
            if aqui is None:
                hallazgos.append(
                    (addon, ref_py.name, clase, 'CLASE AUSENTE', sorted(metodos)))
                continue
            aqui_norm = {normaliza(m) for m in aqui}
            faltan, fuera_de_sitio = [], []
            for m in sorted(metodos):
                n = normaliza(m)
                if n in aqui_norm:
                    continue
                # El símbolo existe en el addon pero NO en la clase que le
                # toca: función suelta, o método de otra clase. Antes esto se
                # descartaba en silencio y el método contaba como portado —
                # el gate medía **presencia del nombre**, no su sitio. Es la
                # ceguera que #159 cierra: dos estados distintos que el
                # instrumento devolvía como uno.
                (fuera_de_sitio if n in propios else faltan).append(m)
            if faltan:
                hallazgos.append(
                    (addon, ref_py.name, clase, 'MÉTODOS AUSENTES', faltan))
            if fuera_de_sitio:
                hallazgos.append(
                    (addon, ref_py.name, clase, 'FUERA DE SITIO',
                     fuera_de_sitio))
    return pares, hallazgos


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--addon', help='medir sólo este addon')
    p.add_argument('--mapa', action='store_true',
                   help='inventario por archivo con su estado')
    p.add_argument('--quiet', action='store_true')
    p.add_argument('--strict', action='store_true')
    args = p.parse_args()

    if not ODOO19C.is_dir():
        print(f'AVISO: no está el árbol de referencia en {ODOO19C}; '
              'sin él este gate no puede medir nada.')
        return 0

    addons = [args.addon] if args.addon else sorted(
        d.name for d in SRC.iterdir() if d.is_dir())

    pares_total, todos = 0, []
    for addon in addons:
        pares, hallazgos = compara(addon)
        pares_total += pares
        todos += hallazgos

    if args.mapa:
        # El inventario completo: cada archivo de la referencia con su estado.
        # Es lo que convierte el gate en un mapa — sin él sólo se ve la deuda,
        # no la superficie sobre la que se mide.
        estado = {}
        for addon, archivo, _clase, tipo, _s in todos:
            previo = estado.get((addon, archivo))
            estado[(addon, archivo)] = (
                'NO PORTADO' if tipo == 'ARCHIVO NO PORTADO'
                else previo or 'PARCIAL')
        for addon in addons:
            ref_dir = ODOO19C / 'addons' / addon / 'models'
            if not ref_dir.is_dir() or not (SRC / addon).is_dir():
                continue
            for ref_py in sorted(ref_dir.glob('*.py')):
                if ref_py.name == '__init__.py':
                    continue
                print(f'{estado.get((addon, ref_py.name), "COMPLETO"):>11}  '
                      f'{addon}/models/{ref_py.name}')
    elif args.quiet:
        print(len(todos))
    else:
        for addon, archivo, clase, tipo, simbolos_ in todos:
            print(f'{addon}/models/{archivo} :: {clase} — {tipo} ({len(simbolos_)})')
            print(f'    {", ".join(simbolos_)}')
        # El denominador va SIEMPRE junto al conteo: un 0 sin alcance medido no
        # distingue "no hay deuda" de "el instrumento no vio nada".
        #
        # Y los dos estados van **separados**: uno es trabajo de porte, el otro
        # de reubicación. Sumarlos vuelve a esconder lo que #159 destapó.
        fuera = [h for h in todos if h[3] == 'FUERA DE SITIO']
        simb_fuera = sum(len(h[4]) for h in fuera)
        print(f'\nporte incompleto: {len(todos)} hallazgos '
              f'({len(todos) - len(fuera)} de porte · {len(fuera)} de sitio, '
              f'{simb_fuera} símbolos) '
              f'(alcance medido: {pares_total} pares de archivo, '
              f'{len(addons)} addons)')
    return 1 if (args.strict and todos) else 0


if __name__ == '__main__':
    sys.exit(main())
