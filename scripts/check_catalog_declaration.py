#!/usr/bin/env python3
"""Gate estático de la declaración del catálogo L0 (SOL-100 punto 2).

**Qué vigila.** Que las declaraciones distribuidas en
``src/addons/*/authz_catalog.py`` sean coherentes **entre sí y con el árbol**,
sin necesidad de base de datos ni de arrancar Django. Es el análogo de
``check_addon_cycles.py``: deriva del árbol con AST en vez de creerle a una
lista escrita a mano.

**Por qué estático y sin Django.** ``seed_authz`` ya corre estos checks en
runtime (``orphan_capabilities`` / ``unknown_depends``), pero sólo cuando
alguien lo ejecuta contra una DB. Un gate que corre en CI y en pre-commit
detecta el problema **al escribir la declaración**, no al desplegarla. Los dos
niveles son complementarios: éste dice "la declaración es coherente"; el
comando ``reconcile_catalog`` dice "la DB coincide con la declaración".

**Los cinco checks:**

1. **Sintaxis y forma** — el ``authz_catalog.py`` parsea y sus ``MODULES`` /
   ``CAPABILITIES`` son literales analizables.
2. **Addon instalado** — el addon que declara está en ``INSTALLED_APPS``. Sin
   esto la declaración es letra muerta: ``discover()`` recorre
   ``get_app_configs()`` y nunca la vería. No es hipotético — ``returns`` y
   ``reviews`` son carpetas de ``src/addons/`` que **no** son Django apps, y la
   primera versión de SOL-100 les asignó módulos ahí por error.
3. **Sin dueño duplicado** — dos addons no declaran el mismo ``code``.
4. **Sin capacidades huérfanas** — toda capacidad cuelga de un módulo declarado.
5. **Sin ``depends`` colgantes** — toda arista apunta a un módulo declarado. Es
   el check que habría cazado H-API-106: al retirar el addon ``orders``
   (``api@77bd1f0``) cuatro aristas quedaron apuntando a un código sin dueño y
   nada falló.

Uso::

    python3 scripts/check_catalog_declaration.py            # reporte + gate
    python3 scripts/check_catalog_declaration.py --report   # sólo reporte, exit 0
"""
import ast
import os
import re
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.join(BASE, 'src', 'addons')
SETTINGS = os.path.join(BASE, 'src', 'config', 'settings', 'base.py')
ARCHIVO = 'authz_catalog.py'


def addons_instalados():
    """Códigos de addon presentes en ``INSTALLED_APPS`` de ``base.py``.

    Se lee con regex sobre el bloque literal en vez de importar el settings:
    el gate debe correr sin Django configurado ni base de datos, igual que
    ``check_addon_cycles.py``.
    """
    fuente = open(SETTINGS, encoding='utf-8').read()
    bloque = re.search(r'INSTALLED_APPS\s*=\s*\[(.*?)\n\]', fuente, re.S)
    if not bloque:
        raise SystemExit('No se encontró el bloque INSTALLED_APPS en base.py')
    return set(re.findall(r"['\"]addons\.([a-z_0-9]+)['\"]", bloque.group(1)))


def _kwargs(nodo):
    """Extrae los kwargs literales de una llamada ``ModuleSpec``/``CapabilitySpec``.

    Devuelve ``None`` para lo que no sea literal: la declaración es **dato**, y
    un valor computado no se puede auditar estáticamente. El caller lo reporta.
    """
    datos = {}
    for kw in nodo.keywords:
        try:
            datos[kw.arg] = ast.literal_eval(kw.value)
        except ValueError:
            datos[kw.arg] = None
    return datos


def leer_declaraciones():
    """Devuelve ``(modulos, capacidades, no_literales)`` leídos con AST.

    ``modulos``/``capacidades`` mapean ``code -> (addon, datos)``; cuando un
    código está declarado dos veces se conserva la **lista** de dueños para
    poder reportar el conflicto completo, no sólo el primero.
    """
    modulos = defaultdict(list)
    capacidades = defaultdict(list)
    no_literales = []
    for addon in sorted(os.listdir(RAIZ)):
        ruta = os.path.join(RAIZ, addon, ARCHIVO)
        if not os.path.isfile(ruta):
            continue
        arbol = ast.parse(open(ruta, encoding='utf-8').read(), filename=ruta)
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call) or not isinstance(nodo.func, ast.Name):
                continue
            if nodo.func.id not in ('ModuleSpec', 'CapabilitySpec'):
                continue
            datos = _kwargs(nodo)
            code = datos.get('code')
            if not isinstance(code, str):
                no_literales.append(f'{addon}/{ARCHIVO}:{nodo.lineno}')
                continue
            destino = modulos if nodo.func.id == 'ModuleSpec' else capacidades
            destino[code].append((addon, datos))
    return modulos, capacidades, no_literales


def analizar():
    """Corre los cinco checks y devuelve la lista de fallos con su detalle."""
    instalados = addons_instalados()
    modulos, capacidades, no_literales = leer_declaraciones()
    fallos = []

    if no_literales:
        fallos.append((
            'Declaración no literal (el catálogo es dato, no código)',
            no_literales,
        ))

    declarantes = {a for dueños in modulos.values() for a, _ in dueños}
    declarantes |= {a for dueños in capacidades.values() for a, _ in dueños}
    huerfanos = sorted(declarantes - instalados)
    if huerfanos:
        fallos.append((
            'Addons que declaran catálogo y NO están en INSTALLED_APPS '
            '(discover() nunca los verá)',
            huerfanos,
        ))

    duplicados = []
    for tipo, tabla in (('módulo', modulos), ('capacidad', capacidades)):
        for code, dueños in sorted(tabla.items()):
            if len(dueños) > 1:
                duplicados.append(
                    f'{tipo} {code!r}: ' + ', '.join(a for a, _ in dueños)
                )
    if duplicados:
        fallos.append(('Códigos con más de un dueño', duplicados))

    sin_modulo = []
    for code, dueños in sorted(capacidades.items()):
        _, datos = dueños[0]
        propietario = datos.get('module') or code.split('.', 1)[0]
        if propietario not in modulos:
            sin_modulo.append(f'{code} → módulo {propietario!r} no declarado')
    if sin_modulo:
        fallos.append(('Capacidades huérfanas', sin_modulo))

    colgantes = []
    for code, dueños in sorted(modulos.items()):
        _, datos = dueños[0]
        for dep in (datos.get('depends') or ()):
            if dep not in modulos:
                colgantes.append(f'{code} → depends {dep!r} no declarado')
    if colgantes:
        fallos.append(('Aristas depends hacia un módulo inexistente', colgantes))

    return modulos, capacidades, instalados, fallos


def main():
    solo_reporte = '--report' in sys.argv
    modulos, capacidades, instalados, fallos = analizar()

    declarantes = sorted({a for d in modulos.values() for a, _ in d}
                         | {a for d in capacidades.values() for a, _ in d})
    print(f'Declaración del catálogo L0 — {len(modulos)} módulos y '
          f'{len(capacidades)} capacidades en {len(declarantes)} addons '
          f'(de {len(instalados)} instalados).')

    if not fallos:
        print('Coherencia: OK (5/5 checks).')
        return 0

    for titulo, detalle in fallos:
        print(f'\nFALLA — {titulo}:')
        for linea in detalle:
            print(f'  - {linea}')
    print(f'\n{len(fallos)} check(s) en falla.')
    return 0 if solo_reporte else 1


if __name__ == '__main__':
    sys.exit(main())
