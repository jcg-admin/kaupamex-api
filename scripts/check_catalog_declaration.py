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
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.join(BASE, 'src'))
from addons_roots import addon_dirs
from modules.module import get_modules
DECLARATION_FILE = 'authz_catalog.py'


def installed_addons():
    """Códigos de addon que ``INSTALLED_APPS`` contiene, leídos de su fuente.

    Se lee **el mismo grafo del que** ``LOCAL_APPS`` **se deriva**, no el texto
    de ``base.py``. Sigue sin necesitar Django ni base de datos —
    ``modules.module`` no importa Django— igual que ``check_addon_cycles.py``.

    Este gate ha muerto DOS veces por leer la forma del literal en vez de su
    contenido, y la segunda es la que obliga a cambiar de fuente:

    1. La primera versión casaba un regex contra ``INSTALLED_APPS = [...]`` y
       murió cuando la lista pasó a ser una suma de tuplas.
    2. La segunda recorría con ``ast`` toda asignación ``*_APPS`` buscando
       constantes ``'addons.<x>'``, y murió el 2026-08-14 cuando ``LOCAL_APPS``
       dejó de ser un literal y pasó a derivarse del grafo (#320): el gate
       publicó **0 addons instalados** y acusó a los 11 que declaran catálogo.
       Un cero de instrumento leído como cero del mundo — la ceguera que
       ``metrica-decide-la-conclusion.md`` describe.

    La lección de las dos es la misma: mientras la fuente sea el TEXTO del
    settings, el gate mide su sintaxis. Ahora mide la población.

    *Métrica:* addons con ``__manifest__.py`` bajo las dos raíces
    (``get_modules()``), que es exactamente el conjunto que ``_local_apps()``
    convierte en ``LOCAL_APPS``.
    *Ciega a:* un addon añadido por vía dinámica fuera del grafo
    (``INSTALLED_APPS +=`` bajo un ``if``, como hace ``development.py`` con
    ``django_extensions``); y a un addon del árbol **sin** manifiesto, que hoy
    no existe — son 91 de 91 desde #296.
    """
    codigos = set(get_modules())
    if not codigos:
        raise SystemExit(
            'get_modules() no devolvió ningún addon: las raíces de '
            '`modules.module` no apuntan al árbol.')
    return codigos


def _kwargs(node):
    """Extrae los kwargs literales de una llamada ``ModuleSpec``/``CapabilitySpec``.

    Devuelve ``None`` para lo que no sea literal: la declaración es **dato**, y
    un valor computado no se puede auditar estáticamente. El caller lo reporta.
    """
    data = {}
    for kw in node.keywords:
        try:
            data[kw.arg] = ast.literal_eval(kw.value)
        except ValueError:
            data[kw.arg] = None
    return data


def read_declarations():
    """Devuelve ``(modules, capabilities, non_literal)`` leídos con AST.

    ``modules``/``capabilities`` mapean ``code -> (addon, data)``; cuando un
    código está declarado dos veces se conserva la **lista** de dueños para
    poder reportar el conflicto completo, no sólo el primero.
    """
    modules = defaultdict(list)
    capabilities = defaultdict(list)
    non_literal = []
    for _p in sorted(addon_dirs()):
        addon = _p.name
        path = os.path.join(str(_p), DECLARATION_FILE)
        if not os.path.isfile(path):
            continue
        tree = ast.parse(open(path, encoding='utf-8').read(), filename=path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in ('ModuleSpec', 'CapabilitySpec'):
                continue
            data = _kwargs(node)
            code = data.get('code')
            if not isinstance(code, str):
                non_literal.append(f'{addon}/{DECLARATION_FILE}:{node.lineno}')
                continue
            target = modules if node.func.id == 'ModuleSpec' else capabilities
            target[code].append((addon, data))
    return modules, capabilities, non_literal


def analyze():
    """Corre los cinco checks y devuelve la lista de fallos con su detalle."""
    installed = installed_addons()
    modules, capabilities, non_literal = read_declarations()
    failures = []

    if non_literal:
        failures.append((
            'Declaración no literal (el catálogo es dato, no código)',
            non_literal,
        ))

    declarers = {a for owners in modules.values() for a, _ in owners}
    declarers |= {a for owners in capabilities.values() for a, _ in owners}
    uninstalled = sorted(declarers - installed)
    if uninstalled:
        failures.append((
            'Addons que declaran catálogo y NO están en INSTALLED_APPS '
            '(discover() nunca los verá)',
            uninstalled,
        ))

    duplicates = []
    for kind, table in (('módulo', modules), ('capacidad', capabilities)):
        for code, owners in sorted(table.items()):
            if len(owners) > 1:
                duplicates.append(
                    f'{kind} {code!r}: ' + ', '.join(a for a, _ in owners)
                )
    if duplicates:
        failures.append(('Códigos con más de un dueño', duplicates))

    orphans = []
    for code, owners in sorted(capabilities.items()):
        _, data = owners[0]
        owner_code = data.get('module') or code.split('.', 1)[0]
        if owner_code not in modules:
            orphans.append(f'{code} → módulo {owner_code!r} no declarado')
    if orphans:
        failures.append(('Capacidades huérfanas', orphans))

    dangling = []
    for code, owners in sorted(modules.items()):
        _, data = owners[0]
        for dep in (data.get('depends') or ()):
            if dep not in modules:
                dangling.append(f'{code} → depends {dep!r} no declarado')
    if dangling:
        failures.append(('Aristas depends hacia un módulo inexistente', dangling))

    return modules, capabilities, installed, failures


def main():
    report_only = '--report' in sys.argv
    modules, capabilities, installed, failures = analyze()

    declarers = sorted({a for d in modules.values() for a, _ in d}
                         | {a for d in capabilities.values() for a, _ in d})
    print(f'Declaración del catálogo L0 — {len(modules)} módulos y '
          f'{len(capabilities)} capacidades en {len(declarers)} addons '
          f'(de {len(installed)} instalados).')

    if not failures:
        print('Coherencia: OK (5/5 checks).')
        return 0

    for title, detail in failures:
        print(f'\nFALLA — {title}:')
        for line in detail:
            print(f'  - {line}')
    print(f'\n{len(failures)} check(s) en falla.')
    return 0 if report_only else 1


if __name__ == '__main__':
    sys.exit(main())
