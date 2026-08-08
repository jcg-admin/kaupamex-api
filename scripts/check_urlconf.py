#!/usr/bin/env python3
"""Gate: la URLConf del proyecto resuelve entera.

Origen: :ref:`h-api-376`. ``api@31c2470`` dejó ``HEAD`` sin arrancar su
URLConf —``urls.py`` importaba tres símbolos que su ``session.py`` no
definía— y **ningún gate lo vio**, porque el que se corrió fue
``django.setup()``.

Por qué ``django.setup()`` no sirve para esto
----------------------------------------------

Leído del binario (``django/__init__.py``, Django 6.0.5), ``setup()`` hace
exactamente tres cosas::

    configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)
    set_script_prefix(...)          # sólo guarda un string en thread-local
    apps.populate(settings.INSTALLED_APPS)

Ninguna toca ``ROOT_URLCONF``; ``django/apps/registry.py`` no menciona urls.
La URLConf de Django es **perezosa**: se importa al resolver la primera ruta,
no al arrancar. Así que un ``ImportError`` entre módulos de rutas sobrevive a
un ``setup()`` verde y sólo aparece en la primera petición — o en el primer
test que use el cliente HTTP.

Qué mide este gate
------------------

Fuerza la resolución (``get_resolver().url_patterns``) y **publica su
denominador**: cuántos patrones resolvió. Un conteo sin denominador no es un
resultado (``hallazgo-abierto-genera-sucesor.md``): sin él, un gate que
resuelve 3 rutas y uno que resuelve 600 imprimen el mismo OK.

*Métrica:* el árbol de patrones de ``ROOT_URLCONF`` se importa y expande sin
excepción. *Ciega a:* que una vista **exista pero esté rota por dentro** —
esto valida el cableado, no el cuerpo; y a rutas registradas dinámicamente
después del arranque, si las hubiera.

Uso
---

    python3 scripts/check_urlconf.py           # reporte + exit 1 si rompe
    python3 scripts/check_urlconf.py --quiet   # sólo el conteo
"""
import argparse
import importlib.util
import os
import sys
import traceback

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(RAIZ, 'src')
VENV = os.path.join(RAIZ, '.venv', 'bin', 'python3')


def reexec_en_venv():
    """Re-lanzarse bajo el intérprete del venv si Django no está aquí.

    Los otros gates (``check_no_lazy_imports``, ``check_silent_oks``) son
    AST puro y corren con el ``python3`` del sistema, que es el que usa
    ``.githooks/pre-commit``. Éste necesita Django importable.

    Sin esto el gate daba ``ModuleNotFoundError`` **en los dos sentidos** —
    con la URLConf sana y con la rota— es decir, exit 1 siempre y ninguna
    capacidad de distinguirlas. Un instrumento que devuelve el mismo
    veredicto en ambos estados no mide: sólo falla de forma fiable.
    """
    if importlib.util.find_spec('django') is not None:
        return
    if not os.path.exists(VENV) or os.path.realpath(sys.executable) == os.path.realpath(VENV):
        print(f'FAIL — Django no es importable y no hay venv usable en {VENV}',
              file=sys.stderr)
        raise SystemExit(1)
    os.execv(VENV, [VENV, os.path.abspath(__file__), *sys.argv[1:]])


def cuenta_patrones(lista):
    """Patrones hoja del árbol, descendiendo por cada ``include()``."""
    total = 0
    for p in lista:
        hijos = getattr(p, 'url_patterns', None)
        total += cuenta_patrones(hijos) if hijos is not None else 1
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    reexec_en_venv()
    sys.path.insert(0, SRC)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')

    import django
    from django.urls import get_resolver

    try:
        django.setup()
    except Exception:
        print('FAIL — el registro de apps no arranca:\n', file=sys.stderr)
        traceback.print_exc()
        return 1

    # El paso que setup() NO hace. Aquí es donde revienta un import cruzado
    # entre módulos de rutas.
    try:
        patrones = get_resolver().url_patterns
    except Exception:
        print('FAIL — la URLConf no resuelve. Un módulo de rutas importa algo '
              'que su origen no define, o el import revienta:\n', file=sys.stderr)
        traceback.print_exc()
        return 1

    n = cuenta_patrones(patrones)
    if args.quiet:
        print(n)
    else:
        print(f'OK: la URLConf resuelve ({n} patrones alcanzables desde '
              f'ROOT_URLCONF, {len(patrones)} en la raíz).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
